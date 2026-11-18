"""
Interfaz de línea de comandos (Typer).

Tras `pip install -e .` queda disponible el comando `split-steal`
(también `python -m split_steal`):

    split-steal catalog                      # TODAS las estrategias que existen (y sus parámetros)
    split-steal presets                      # grupos de estrategias con nombre
    split-steal list clasicas                # estrategias de un preset o selección
    split-steal tournament --seed 42         # juega un torneo y lo guarda en results/runs/
    split-steal stats  results/runs/<run>    # tabla resumen por estrategia
    split-steal plot   results/runs/<run>    # genera las gráficas en <run>/figs/

Typer convierte los parámetros de cada función en opciones de terminal
(`n_leagues` -> `--n-leagues`) y sus docstrings en la ayuda (`--help`).
"""

import sys
import time
from datetime import datetime
from pathlib import Path
from typing import List

import pandas as pd
import typer

# En Windows, si la salida se redirige (a un archivo o pipe) Python usa la
# codificación cp1252, que no tiene algunos caracteres (p. ej. "→"). Con
# errors="replace" se sustituyen por "?" en lugar de abortar el programa.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(errors="replace")

from .register import CATALOG, PRESETS, build_roster
from .experiment import (Variant, compare, index_path_for, load_experiment, run_experiment,
                         save_experiment, update_index, variant_row)
from .multiseed import load_multi, run_seeds, save_multi
from .runner import TournamentConfig, load_run, run_tournament, save_run
from .simulator import Payoff

app = typer.Typer(help="Torneos de estrategias Split/Steal con ligas, ascensos y descensos.",
                  no_args_is_help=True)


def summarize(matches: pd.DataFrame) -> pd.DataFrame:
    """
    Resumen por estrategia a partir de la tabla de partidos (columnas A, B, pa, pb).

    Cada partido aparece una vez con A y B; lo "desdoblamos" en dos filas (una por
    estrategia, con su puntuación y la del rival) para poder agrupar por nombre.
    """
    side_a = matches[["A", "pa", "pb"]].rename(columns={"A": "name", "pa": "score", "pb": "opp"})
    side_b = matches[["B", "pb", "pa"]].rename(columns={"B": "name", "pb": "score", "pa": "opp"})
    u = pd.concat([side_a, side_b], ignore_index=True)

    return (u.assign(win=(u["score"] > u["opp"]).astype(int),
                     loss=(u["score"] < u["opp"]).astype(int),
                     tie=(u["score"] == u["opp"]).astype(int))
             .groupby("name", as_index=False)
             .agg(matches=("score", "size"),
                  wins=("win", "sum"),
                  losses=("loss", "sum"),
                  ties=("tie", "sum"),
                  mean_payoff=("score", "mean"),
                  median_payoff=("score", "median"))
             .sort_values(["mean_payoff", "wins"], ascending=[False, False], ignore_index=True))


ROSTER_HELP = ('Preset (full, clasicas, cooperativas, cooperativas_con_traidores, prueba) '
               'o lista separada por comas, p. ej. "TitForTat, ForgivingTitForTat(p=0.2)". '
               'Se pueden sumar y restar: "clasicas, -AlwaysSteal, +Extortioner"')


def _build(selection: str):
    """build_roster con los errores convertidos en mensajes de la CLI."""
    try:
        return build_roster(selection)
    except ValueError as e:
        raise typer.BadParameter(str(e))


@app.command("catalog")
def catalog():
    """Muestra TODAS las estrategias disponibles, sus parámetros y si están en el roster oficial."""
    official = set(PRESETS["full"])
    typer.echo(f"{len(CATALOG)} estrategias ({len(official)} en el roster oficial 'full'; * = fuera de él)")
    for name, cls in sorted(CATALOG.items()):
        params = ", ".join(f"{k}={v!r}" for k, v in cls.default_params().items())
        mark = " " if name in official else "*"
        typer.echo(f" {mark}{name}" + (f"({params})" if params else ""))
        typer.echo(f"   [{', '.join(sorted(cls.tags))}] {cls.description()}")


@app.command("presets")
def presets():
    """Muestra los presets (grupos de estrategias con nombre)."""
    for name, specs in PRESETS.items():
        typer.echo(f"{name} ({len(specs)}): {', '.join(specs)}\n")


@app.command("list")
def list_strategies(roster: str = typer.Argument("full", help=ROSTER_HELP)):
    """Muestra las estrategias de un preset o selección, con etiquetas y descripción."""
    members = _build(roster)
    typer.echo(f"Selección '{roster}': {len(members)} estrategias")
    for name, strategy in members.items():
        tags = ", ".join(sorted(strategy.tags))
        typer.echo(f"  {name:<24} [{tags}]")
        typer.echo(f"  {'':<24} {strategy.description()}")


def _parse_payoff(text: str) -> dict:
    """'R=3,S=0,T=5,P=1' -> {'R': 3, 'S': 0, 'T': 5, 'P': 1} (las que falten, por defecto)."""
    values = Payoff().as_dict()
    for part in filter(None, (p.strip() for p in text.split(","))):
        key, _, value = part.partition("=")
        key = key.strip().upper()
        if key not in values:
            raise typer.BadParameter(f"pago desconocido '{key}': usa R, S, T y P")
        try:
            values[key] = int(value)
        except ValueError:
            raise typer.BadParameter(f"el pago {key} debe ser un entero ('{value.strip()}')")
    return values


@app.command()
def tournament(
    roster: str = typer.Option("full", help=ROSTER_HELP),
    format: str = typer.Option("leagues", "--format", "-f",
                               help="leagues (ligas con ascensos) | round_robin (todos contra "
                                    "todos; ignora las opciones de ligas)"),
    n_leagues: int = typer.Option(6, help="Número de ligas"),
    n_per_league: int = typer.Option(6, help="Estrategias por liga"),
    rounds: int = typer.Option(100, help="Rondas por partido"),
    n_seasons: int = typer.Option(20, help="Temporadas (sin contar la clasificatoria)"),
    k: int = typer.Option(2, help="Cuántas estrategias suben y bajan por liga"),
    seed: int = typer.Option(42, help="Semilla maestra"),
    qualifying: bool = typer.Option(True, help="Jugar temporada 0 clasificatoria"),
    noise: float = typer.Option(0.0, help="Probabilidad de que una jugada se invierta (0 = sin ruido)"),
    payoff: str = typer.Option("R=3,S=0,T=5,P=1",
                               help="Pagos: R ambos SPLIT, S me traicionan, T traiciono, P ambos STEAL"),
    save_rounds: bool = typer.Option(False, help="Guardar también cada jugada (rounds.csv.gz)"),
    seeds: int = typer.Option(1, help="Repetir el torneo con N semillas (seed, seed+1, ...) y resumir"),
    workers: int = typer.Option(None, help="Procesos en paralelo con --seeds > 1 (por defecto, todos los núcleos)"),
    out_dir: Path = typer.Option(Path("results/runs"), help="Carpeta donde guardar"),
    name: str = typer.Option(None, help="Nombre de la carpeta del run (por defecto, fecha y hora)"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Mostrar ascensos y descensos"),
):
    """Juega un torneo (o el mismo con varias semillas) y guarda sus resultados."""
    config = TournamentConfig(roster=roster, format=format, n_leagues=n_leagues,
                              n_per_league=n_per_league,
                              rounds=rounds, n_seasons=n_seasons, n_ascend_descend=k,
                              seed=seed, qualifying=qualifying, noise=noise,
                              payoff=_parse_payoff(payoff), save_rounds=save_rounds)
    name = name or datetime.now().strftime("tournament_%Y%m%d_%H%M%S")
    try:
        if seeds > 1:
            start = time.perf_counter()
            multi = run_seeds(config, n_seeds=seeds, workers=workers)
            run_dir = save_multi(multi, out_dir=out_dir, name=name)
            typer.echo(f"{seeds} torneos en {time.perf_counter() - start:.1f} s")
            _echo_summary(multi.summary)
        else:
            run_dir = save_run(run_tournament(config, verbose=verbose), out_dir=out_dir, name=name)
    except ValueError as e:
        raise typer.BadParameter(str(e))
    row = variant_row(Variant(name=name, config=config), seeds)
    update_index(index_path_for(out_dir), f"tournament/{name}",
                 [{**row, "path": Path(run_dir).as_posix()}])
    typer.echo(f"Resultados guardados en: {run_dir}")


@app.command()
def experiment(
    file: Path = typer.Argument(..., help="Archivo .toml del experimento (ver experiments/)"),
    out_dir: Path = typer.Option(Path("results/experiments"), help="Carpeta donde guardar"),
    workers: int = typer.Option(None, help="Procesos en paralelo (por defecto, todos los núcleos)"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Solo mostrar las variantes, sin jugar"),
):
    """Ejecuta un experimento: todas sus variantes × semillas, y guarda la comparación."""
    try:
        exp = load_experiment(file)
        variants = exp.expand()
    except (ValueError, OSError) as e:
        raise typer.BadParameter(str(e))
    typer.echo(f"Experimento '{exp.name}': {len(variants)} variantes × {exp.seeds} semillas "
               f"= {len(variants) * exp.seeds} torneos")
    for v in variants:
        typer.echo(f"  - {v.name}")
    if dry_run:
        return
    start = time.perf_counter()
    result = run_experiment(exp, workers=workers)
    exp_dir = save_experiment(result, out_dir=out_dir)
    typer.echo(f"Hecho en {time.perf_counter() - start:.1f} s. Resultados en: {exp_dir}")
    typer.echo("\nPosición media por variante (mejores 12):")
    typer.echo(compare([exp_dir]).head(12).round(1).to_string())


@app.command("compare")
def compare_cmd(
    exp_dirs: List[Path] = typer.Argument(..., help="Una o varias carpetas de experimento"),
    metric: str = typer.Option("rank_mean", help="Columna de summary.csv: rank_mean, title_rate, "
                                                  "league1_rate, points_per_round, coop_rate..."),
    strategies: str = typer.Option(None, help="Solo estas estrategias (separadas por comas)"),
    top: int = typer.Option(None, help="Mostrar solo las N primeras filas"),
    transpose: bool = typer.Option(False, "--transpose", "-t",
                                   help="Variantes en filas y estrategias en columnas"),
):
    """Compara una métrica entre variantes: una fila por estrategia, una columna por variante."""
    names = [s.strip() for s in strategies.split(",")] if strategies else None
    try:
        table = compare(exp_dirs, metric=metric, strategies=names)
    except (ValueError, OSError) as e:
        raise typer.BadParameter(str(e))
    table = table.head(top) if top else table
    if transpose:
        typer.echo(f"{metric} (filas: variantes, columnas: estrategias)")
        typer.echo(table.T.round(2).to_string())
    else:
        typer.echo(f"{metric} (filas: estrategias, columnas: variantes)")
        typer.echo(table.round(2).to_string())


@app.command("index")
def index_cmd(results_dir: Path = typer.Option(Path("results"), help="Carpeta raíz de resultados")):
    """Muestra el catálogo de todo lo simulado (results/index.csv)."""
    path = results_dir / "index.csv"
    if not path.exists():
        raise typer.BadParameter(f"todavía no existe {path}")
    cols = ["experiment", "variant", "created", "format", "roster", "n_strategies",
            "n_seeds", "noise", "rounds"]
    typer.echo(pd.read_csv(path)[cols].to_string(index=False))


def _echo_summary(summary: pd.DataFrame, top: int = 12) -> None:
    """Imprime las columnas principales del resumen entre semillas."""
    cols = ["name", "rank_mean", "rank_ci95", "rank_best", "rank_worst", "title_rate",
            "league1_rate", "points_per_round", "coop_rate"]
    typer.echo(summary[cols].head(top).round(2).to_string(index=False))
    if len(summary) > top:
        typer.echo(f"... ({len(summary) - top} más en summary.csv)")


@app.command()
def stats(run_dir: Path = typer.Argument(..., help="Carpeta de un run")):
    """Resumen por estrategia y clasificación final (o resumen entre semillas)."""
    if (Path(run_dir) / "summary.csv").exists():          # carpeta de varias semillas
        multi = load_multi(run_dir)
        typer.echo(f"{len(multi.seeds)} semillas ({multi.seeds[0]}..{multi.seeds[-1]}), "
                   f"formato {multi.config.format}:")
        _echo_summary(multi.summary, top=len(multi.summary))
        return
    result = load_run(run_dir)

    typer.echo("Resumen de todos los partidos (incluida la clasificatoria):")
    typer.echo(summarize(result.matches).round(1).to_string(index=False))

    typer.echo(f"\nClasificación final ({result.config.format}):")
    typer.echo(result.final_ranking.to_string(index=False))


@app.command()
def plot(
    run_dir: Path = typer.Argument(..., help="Carpeta de un torneo, de varias semillas o de un experimento"),
    metric: List[str] = typer.Option(["rank_mean", "title_rate"],
                                     help="Experimentos: métricas a dibujar (se puede repetir)"),
    strategies: str = typer.Option(None, help="Experimentos: estrategias a dibujar (por comas, máx. 8 en líneas)"),
):
    """Genera las gráficas en <carpeta>/figs/ (detecta el tipo de carpeta)."""
    # import diferido: matplotlib solo se carga cuando hace falta
    from .plots import _save, plot_all, plot_experiment, plot_head_to_head

    run_dir = Path(run_dir)
    names = [s.strip() for s in strategies.split(",")] if strategies else None
    try:
        if (run_dir / "experiment.toml").exists():
            paths = plot_experiment(run_dir, metrics=metric, strategies=names)
        elif (run_dir / "summary.csv").exists():                 # varias semillas
            multi = load_multi(run_dir)
            (run_dir / "figs").mkdir(exist_ok=True)
            fig = plot_head_to_head(multi.matches, title_note=f"{len(multi.seeds)} semillas")
            paths = [_save(fig, run_dir / "figs" / "head_to_head.png")]
        else:
            paths = plot_all(load_run(run_dir), run_dir / "figs")
    except (ValueError, OSError) as e:
        raise typer.BadParameter(str(e))
    for path in paths:
        typer.echo(f"  {path}")


if __name__ == "__main__":
    app()
