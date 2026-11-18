"""
Experimentos: comparar varias condiciones (variantes) repitiendo cada una con N semillas.

Un experimento se describe en un archivo TOML (un formato de configuración legible,
que Python lee con `tomllib`). Ejemplo, `experiments/ruido.toml`:

    name = "efecto_del_ruido"
    description = "¿Qué estrategias resisten los errores?"
    seeds = 50                       # semillas por variante

    [base]                           # ajustes comunes (los de TournamentConfig)
    format = "leagues"
    roster = "full"

    [sweep]                          # barrido: una variante por cada combinación
    noise = [0.0, 0.01, 0.05, 0.1]

Tres formas de definir variantes (se pueden combinar):
  - `[base]`: lo que comparten todas.
  - `[sweep]`: listas de valores; se prueban TODAS las combinaciones. Claves válidas:
      * un ajuste del torneo:            noise = [0, 0.05]
      * un pago:                         "payoff.T" = [5, 6, 7]
      * el parámetro de una estrategia:  "ForgivingTitForTat.p" = [0.1, 0.2, 0.33]
  - `[[variants]]`: variantes escritas a mano (cada una con `name` y los ajustes que
    cambia respecto a `[base]`), para comparaciones que no son un barrido simple:

        [[variants]]
        name = "ligas"
        format = "leagues"

        [[variants]]
        name = "todos_contra_todos"
        format = "round_robin"

    Si hay variantes a mano Y barrido, el barrido se aplica a cada una.

Resultados (`results/experiments/<name>/`):
    experiment.toml        copia exacta del archivo ejecutado (para poder repetirlo)
    variants.csv           una fila por variante con todos sus ajustes
    summary.csv            resumen por variante y estrategia (posición media, títulos...)
                           con una columna por cada ajuste barrido: listo para comparar
    variants/<variante>/   los datos completos de esa variante (ver multiseed.save_multi)

Además se añade una fila por variante a `results/index.csv`, el catálogo de todo lo
que se ha simulado (ver `update_index`).
"""

import itertools
import re
import tomllib
from dataclasses import asdict, dataclass, field, fields, replace
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import pandas as pd

from .multiseed import MultiSeedResult, combine, run_many, save_multi, seeds_for
from .register import CATALOG, make_strategy, set_strategy_param
from .runner import TournamentConfig, check_config

CONFIG_FIELDS = [f.name for f in fields(TournamentConfig)]
PAYOFF_KEYS = ("R", "S", "T", "P")
TOP_LEVEL_KEYS = {"name", "description", "seeds", "base", "sweep", "variants"}


# =============================================================================
# Definición
# =============================================================================

@dataclass
class Variant:
    """Una condición del experimento: su nombre, su config y qué valores la definen."""

    name: str
    config: TournamentConfig
    labels: Dict[str, Any] = field(default_factory=dict)   # p. ej. {"noise": 0.05}


@dataclass
class Experiment:
    name: str
    description: str = ""
    seeds: int = 50
    base: Dict[str, Any] = field(default_factory=dict)
    sweep: Dict[str, List[Any]] = field(default_factory=dict)
    variants: List[Dict[str, Any]] = field(default_factory=list)
    source: str = ""              # texto del TOML (se copia a los resultados)

    def expand(self) -> List[Variant]:
        """Todas las variantes: (variantes a mano o solo la base) × combinaciones del barrido."""
        manual = self.variants or [{"name": "base"}]
        keys = list(self.sweep)
        combos = list(itertools.product(*self.sweep.values())) if keys else [()]
        out = []
        for v in manual:
            v = dict(v)
            vname = v.pop("name", "base")
            for combo in combos:
                config = _apply(TournamentConfig(), {**self.base, **v})
                labels = {"variant": vname} if len(manual) > 1 else {}
                for key, value in zip(keys, combo):
                    config = _apply_sweep(config, key, value)
                    labels[key] = value
                parts = ([vname] if len(manual) > 1 or not keys else []) + \
                        [f"{k}={_fmt(val)}" for k, val in zip(keys, combo)]
                out.append(Variant(name=_safe("__".join(parts)), config=config, labels=labels))
        names = [v.name for v in out]
        if len(set(names)) != len(names):
            raise ValueError("Hay variantes con el mismo nombre; revisa los `name` de [[variants]]")
        return out


def load_experiment(path: Union[str, Path]) -> Experiment:
    """Lee y valida un archivo de experimento TOML."""
    path = Path(path)
    source = path.read_text(encoding="utf-8")
    try:
        data = tomllib.loads(source)
    except tomllib.TOMLDecodeError as e:
        raise ValueError(f"{path.name}: TOML mal escrito: {e}") from None

    unknown = set(data) - TOP_LEVEL_KEYS
    if unknown:
        raise ValueError(f"{path.name}: claves desconocidas {sorted(unknown)}. "
                         f"Válidas: {sorted(TOP_LEVEL_KEYS)}")
    if "name" not in data:
        raise ValueError(f"{path.name}: falta `name`")
    exp = Experiment(name=data["name"], description=data.get("description", ""),
                     seeds=int(data.get("seeds", 50)), base=data.get("base", {}),
                     sweep=data.get("sweep", {}), variants=data.get("variants", []),
                     source=source)
    if exp.seeds < 1:
        raise ValueError("`seeds` debe ser al menos 1")
    if not re.fullmatch(r"[A-Za-z0-9_\-]+", exp.name):
        raise ValueError(f"`name` solo puede tener letras, números, '_' y '-' (es '{exp.name}')")
    for key, values in exp.sweep.items():
        if not isinstance(values, list) or not values:
            raise ValueError(f"[sweep] {key} debe ser una lista de valores no vacía")
    for v in exp.variants:
        if "name" not in v:
            raise ValueError("cada [[variants]] necesita un `name`")
    # Expandir ya valida claves; comprobar cada config detecta errores antes de jugar.
    for variant in exp.expand():
        try:
            check_config(variant.config)
        except ValueError as e:
            raise ValueError(f"variante '{variant.name}': {e}") from None
    return exp


def _apply(config: TournamentConfig, settings: Dict[str, Any]) -> TournamentConfig:
    """Aplica ajustes de [base] / [[variants]] a un config."""
    unknown = set(settings) - set(CONFIG_FIELDS)
    if unknown:
        raise ValueError(f"ajustes desconocidos {sorted(unknown)}. Válidos: {', '.join(CONFIG_FIELDS)}")
    if "payoff" in settings:
        settings = {**settings, "payoff": {**config.payoff, **settings["payoff"]}}
    return replace(config, **settings)


def _apply_sweep(config: TournamentConfig, key: str, value: Any) -> TournamentConfig:
    """Aplica UN valor de una clave del barrido."""
    if key in CONFIG_FIELDS:
        return _apply(config, {key: value})
    head, _, tail = key.partition(".")
    if head == "payoff" and tail in PAYOFF_KEYS:
        return replace(config, payoff={**config.payoff, tail: value})
    if head in CATALOG and tail:
        return replace(config, roster=set_strategy_param(config.roster, head, tail, value))
    raise ValueError(f"[sweep] clave desconocida '{key}'. Usa un ajuste del torneo "
                     f"({', '.join(CONFIG_FIELDS)}), 'payoff.R/S/T/P' o 'Estrategia.parametro'")


def _unswept_name(name: str, sweep: Dict[str, List[Any]]) -> str:
    """
    Nombre de la estrategia SIN los parámetros que barre el experimento, para poder
    seguirla de una variante a otra: con "ForgivingTitForTat.p" en el barrido,
    "ForgivingTitForTat(p=0.2)" -> "ForgivingTitForTat". El resto no cambia.
    """
    strategy = make_strategy(name)
    cls = type(strategy).__name__
    swept = {key.partition(".")[2] for key in sweep if key.partition(".")[0] == cls}
    if not swept:
        return name
    defaults = strategy.default_params()
    kept = {k: (defaults[k] if k in swept else v) for k, v in strategy.params.items()}
    return type(strategy)(**kept).name


def _fmt(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:g}"
    if isinstance(value, list):
        return "+".join(map(str, value))
    return str(value)


def _safe(name: str) -> str:
    """Nombre válido como carpeta en cualquier sistema."""
    return re.sub(r"[^A-Za-z0-9_.=,+\-]", "_", name) or "base"


# =============================================================================
# Ejecución y guardado
# =============================================================================

@dataclass
class ExperimentResult:
    experiment: Experiment
    variants: List[Variant]
    results: Dict[str, MultiSeedResult]      # nombre de variante -> resultados
    summary: pd.DataFrame                    # todas las variantes juntas


def run_experiment(exp: Experiment, workers: Optional[int] = None) -> ExperimentResult:
    """
    Juega todas las variantes × semillas. Todos los torneos van a la MISMA bolsa de
    procesos (así el paralelo se aprovecha aunque haya muchas variantes pequeñas).
    Cada variante usa las mismas semillas (seed, seed+1, ...): las diferencias entre
    variantes no se deben a haber tenido "otra suerte".
    """
    variants = exp.expand()
    plan = [(v, seeds_for(v.config, exp.seeds)) for v in variants]
    configs = [replace(v.config, seed=s) for v, seeds in plan for s in seeds]
    flat = run_many(configs, workers)

    # Columnas que identifican la variante en summary.csv: su nombre, el grupo de
    # [[variants]] (si hay varias a mano) y una columna por cada clave del barrido.
    label_cols = ["variant"] + (["variant_group"] if len(exp.variants) > 1 else []) + list(exp.sweep)

    results, summaries, i = {}, [], 0
    for v, seeds in plan:
        multi = combine(v.config, seeds, flat[i:i + len(seeds)])
        i += len(seeds)
        results[v.name] = multi
        labels = {"variant": v.name}
        if "variant" in v.labels:
            labels["variant_group"] = v.labels["variant"]
        labels.update({k: _fmt(x) if isinstance(x, list) else x
                       for k, x in v.labels.items() if k != "variant"})
        summary_v = multi.summary.assign(**labels)
        summary_v.insert(summary_v.columns.get_loc("name") + 1, "strategy",
                         [_unswept_name(n, exp.sweep) for n in summary_v["name"]])
        summaries.append(summary_v)
    summary = pd.concat(summaries, ignore_index=True)
    summary = summary[label_cols + [c for c in summary.columns if c not in label_cols]]
    return ExperimentResult(exp, variants, results, summary)


def variant_row(v: Variant, n_seeds: int) -> Dict[str, Any]:
    """Una fila plana con todos los ajustes de una variante (para variants.csv / index.csv)."""
    c = asdict(v.config)
    roster = c.pop("roster")
    payoff = c.pop("payoff")
    return {"variant": v.name, "n_seeds": n_seeds,
            "roster": roster if isinstance(roster, str) else ", ".join(roster),
            "n_strategies": check_config(v.config),
            **c, **{f"payoff_{k}": payoff[k] for k in PAYOFF_KEYS}}


def save_experiment(result: ExperimentResult, out_dir: Union[str, Path] = "results/experiments",
                    index: bool = True) -> Path:
    """Guarda el experimento en `out_dir/<name>/` y (si index) lo apunta en el catálogo."""
    exp = result.experiment
    exp_dir = Path(out_dir) / exp.name
    exp_dir.mkdir(parents=True, exist_ok=True)
    # newline fijo: el archivo es idéntico en Windows y Linux (como los CSV)
    (exp_dir / "experiment.toml").write_text(exp.source, encoding="utf-8", newline="\n")
    rows = [variant_row(v, exp.seeds) for v in result.variants]
    pd.DataFrame(rows).to_csv(exp_dir / "variants.csv", index=False, lineterminator="\n")
    result.summary.to_csv(exp_dir / "summary.csv", index=False, lineterminator="\n")
    for v in result.variants:
        save_multi(result.results[v.name], exp_dir / "variants", v.name)
    if index:
        update_index(index_path_for(out_dir), exp.name, [
            {**row, "path": (exp_dir / "variants" / row["variant"]).as_posix()} for row in rows])
    return exp_dir


def load_summary(exp_dir: Union[str, Path]) -> pd.DataFrame:
    """El summary.csv de un experimento guardado."""
    return pd.read_csv(Path(exp_dir) / "summary.csv")


# =============================================================================
# Catálogo y comparación
# =============================================================================

def index_path_for(out_dir: Union[str, Path]) -> Path:
    """
    Dónde va el catálogo: en la carpeta `results` que contiene a `out_dir` (o que es
    `out_dir`), así `results/runs`, `results/experiments` y `results` comparten
    `results/index.csv`. Si no hay ninguna `results` por encima, junto a `out_dir`.
    """
    out_dir = Path(out_dir)
    for folder in [out_dir, *out_dir.parents]:
        if folder.name == "results":
            return folder / "index.csv"
    return out_dir.parent / "index.csv"


def update_index(index_path: Union[str, Path], experiment: str, rows: List[Dict[str, Any]]) -> Path:
    """
    Añade (o reemplaza, si el experimento ya estaba) las filas de un experimento en el
    catálogo `index.csv`. Es la "base de datos" de todo lo simulado: una fila por
    variante con su ruta y sus ajustes, para buscar y comparar sin abrir carpetas.
    """
    index_path = Path(index_path)
    new = pd.DataFrame(rows).assign(experiment=experiment,
                                    created=datetime.now().isoformat(timespec="seconds"))
    if index_path.exists():
        old = pd.read_csv(index_path)
        new = pd.concat([old[old["experiment"] != experiment], new], ignore_index=True)
    first = ["experiment", "variant", "created", "path"]
    new = new[first + [c for c in new.columns if c not in first]]
    index_path.parent.mkdir(parents=True, exist_ok=True)
    new.to_csv(index_path, index=False, lineterminator="\n")
    return index_path


def compare(exp_dirs: List[Union[str, Path]], metric: str = "rank_mean",
            strategies: Optional[List[str]] = None) -> pd.DataFrame:
    """
    Tabla para comparar: una fila por estrategia, una columna por variante (de uno o
    varios experimentos) y en cada celda la métrica elegida (columna de summary.csv).
    Las filas son la columna `strategy` (el nombre sin los parámetros barridos), así una
    estrategia cuyo parámetro cambia entre variantes sigue en la misma fila.
    Ordenada por la media de la métrica en todas las variantes, de mejor a peor: de
    menor a mayor para las posiciones (rank_*), de mayor a menor para el resto.
    """
    frames = []
    for d in exp_dirs:
        s = load_summary(d)
        if metric not in s.columns:
            raise ValueError(f"métrica desconocida '{metric}'. Opciones: {', '.join(s.columns)}")
        prefix = f"{Path(d).name}/" if len(exp_dirs) > 1 else ""
        frames.append(s.assign(column=prefix + s["variant"]))
    s = pd.concat(frames, ignore_index=True)
    if strategies:
        missing = sorted(set(strategies) - set(s["strategy"]))
        if missing:
            raise ValueError(f"estrategias que no aparecen: {', '.join(missing)}")
        s = s[s["strategy"].isin(strategies)]
    order = list(dict.fromkeys(s["column"]))           # columnas en el orden del experimento
    table = s.pivot_table(index="strategy", columns="column", values=metric, aggfunc="first")[order]
    best_first_ascending = metric.startswith("rank")
    return table.loc[table.mean(axis=1).sort_values(ascending=best_first_ascending).index]
