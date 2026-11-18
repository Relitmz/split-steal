"""
Repetir el mismo torneo con varias semillas (en paralelo) y resumir los resultados.

¿Por qué? Muchas estrategias usan el azar, y en ligas el sorteo decide empates. Un
solo torneo puede dar un campeón "con suerte". Repitiendo el torneo N veces con
semillas distintas se ve qué es robusto (posición media, % de títulos) y qué es ruido.

Semillas: con semilla maestra 42 y 50 repeticiones se usan 42, 43, ..., 91. Es
transparente (la repetición i es exactamente `tournament --seed 42+i`) y los
generadores de numpy dan secuencias independientes aunque las semillas sean consecutivas.

Paralelo
--------
Cada torneo es independiente de los demás, así que se reparten entre varios
PROCESOS (no hilos: en Python solo un hilo ejecuta código a la vez dentro de un
proceso, por el GIL; con procesos cada núcleo de la CPU trabaja de verdad a la vez).
`ProcessPoolExecutor.map` devuelve los resultados EN EL ORDEN de las semillas, no en
el que terminan, así que el resultado es idéntico con 1 proceso o con 20.

Guardado ("datos ordenados"): en lugar de 50 carpetas, una tabla por tipo con una
columna `seed`. Así un `groupby("seed")` o un filtro basta para analizar.

    <carpeta>/config.json         config del torneo + lista de semillas
             /summary.csv         resumen por estrategia (analysis.summarize_seeds)
             /final_rankings.csv  clasificación final de cada semilla
             /standings.csv       clasificaciones por temporada y liga (+ seed)
             /strategy_stats.csv  estadísticas por estrategia y liga (+ seed)
             /matches.csv.gz      todos los partidos (+ seed), comprimido
"""

import json
import os
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import List, Optional, Union

import pandas as pd

from .analysis import summarize_seeds
from .runner import TournamentConfig, TournamentResult, run_tournament

# gzip con mtime=0: el .gz no guarda la hora y el archivo es idéntico al repetirlo.
_GZIP = {"method": "gzip", "mtime": 0}


def seeds_for(config: TournamentConfig, n_seeds: int) -> List[int]:
    """Semillas de las repeticiones: la maestra y las siguientes (42, 43, ...)."""
    if n_seeds < 1:
        raise ValueError("n_seeds debe ser al menos 1")
    return [config.seed + i for i in range(n_seeds)]


def default_workers() -> int:
    """Por defecto, todos los núcleos lógicos de la CPU."""
    return os.cpu_count() or 1


def _run_one(config: TournamentConfig) -> TournamentResult:
    """Lo que ejecuta cada proceso. Debe ser una función de módulo (no lambda) para
    que se pueda enviar a otro proceso (pickle)."""
    return run_tournament(config)


@dataclass
class MultiSeedResult:
    """El mismo torneo jugado con varias semillas: tablas con una columna `seed`."""

    config: TournamentConfig            # config base (su `seed` es la maestra)
    seeds: List[int]
    final_rankings: pd.DataFrame
    standings: pd.DataFrame
    strategy_stats: pd.DataFrame
    matches: pd.DataFrame
    summary: pd.DataFrame = field(default=None)

    def __post_init__(self):
        if self.summary is None:
            self.summary = summarize_seeds(self.final_rankings, self.standings,
                                           self.strategy_stats)


def run_seeds(config: TournamentConfig, n_seeds: int = 50,
              workers: Optional[int] = None) -> MultiSeedResult:
    """
    Juega `config` con `n_seeds` semillas consecutivas desde `config.seed`.

    workers: nº de procesos (por defecto, todos los núcleos). Con 1 se juega en
    serie en este mismo proceso (más fácil de depurar). El resultado no depende de él.
    """
    seeds = seeds_for(config, n_seeds)
    results = run_many([replace(config, seed=s) for s in seeds], workers)
    return combine(config, seeds, results)


def run_many(configs: List[TournamentConfig],
             workers: Optional[int] = None) -> List[TournamentResult]:
    """Juega una lista de torneos (en paralelo si workers > 1) y devuelve sus
    resultados EN EL MISMO ORDEN que `configs`. Lo usan run_seeds y los experimentos."""
    if any(c.save_rounds for c in configs):
        raise ValueError("save_rounds no está soportado con varias semillas (ocuparía demasiado)")
    workers = min(workers or default_workers(), len(configs))
    if workers <= 1:
        return [_run_one(c) for c in configs]
    with ProcessPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(_run_one, configs))   # map conserva el orden


def combine(config: TournamentConfig, seeds: List[int],
            results: List[TournamentResult]) -> MultiSeedResult:
    """Apila los resultados de cada semilla en tablas con columna `seed`."""

    def stack(table: str) -> pd.DataFrame:
        frames = [getattr(r, table).assign(seed=s) for s, r in zip(seeds, results)]
        out = pd.concat(frames, ignore_index=True)
        return out[["seed"] + [c for c in out.columns if c != "seed"]]

    final = pd.concat([r.final_ranking.assign(seed=s) for s, r in zip(seeds, results)],
                      ignore_index=True)
    final = final[["seed"] + [c for c in final.columns if c != "seed"]]
    # En matches ya hay una columna `seed` (la del partido): la renombramos.
    matches = pd.concat([r.matches.rename(columns={"seed": "match_seed"}).assign(seed=s)
                         for s, r in zip(seeds, results)], ignore_index=True)
    matches = matches[["seed"] + [c for c in matches.columns if c != "seed"]]

    return MultiSeedResult(config=config, seeds=seeds, final_rankings=final,
                           standings=stack("standings"),
                           strategy_stats=stack("strategy_stats"), matches=matches)


def save_multi(result: MultiSeedResult, out_dir: Union[str, Path], name: str) -> Path:
    """Guarda un MultiSeedResult en `out_dir/name/` (ver formato arriba)."""
    run_dir = Path(out_dir) / name
    run_dir.mkdir(parents=True, exist_ok=True)
    meta = {"config": asdict(result.config), "n_seeds": len(result.seeds), "seeds": result.seeds}
    (run_dir / "config.json").write_text(
        json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    for table in ("summary", "final_rankings", "standings", "strategy_stats"):
        getattr(result, table).to_csv(run_dir / f"{table}.csv", index=False, lineterminator="\n")
    result.matches.to_csv(run_dir / "matches.csv.gz", index=False, lineterminator="\n",
                          compression=_GZIP)
    return run_dir


def load_multi(run_dir: Union[str, Path]) -> MultiSeedResult:
    """Carga una carpeta creada por `save_multi`."""
    run_dir = Path(run_dir)
    meta = json.loads((run_dir / "config.json").read_text(encoding="utf-8"))
    read = lambda f: pd.read_csv(run_dir / f)
    return MultiSeedResult(
        config=TournamentConfig(**meta["config"]), seeds=meta["seeds"],
        final_rankings=read("final_rankings.csv"), standings=read("standings.csv"),
        strategy_stats=read("strategy_stats.csv"), matches=read("matches.csv.gz"),
        summary=read("summary.csv"),
    )
