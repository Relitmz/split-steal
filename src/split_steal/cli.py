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
from pathlib import Path

import pandas as pd
import typer

# En Windows, si la salida se redirige (a un archivo o pipe) Python usa la
# codificación cp1252, que no tiene algunos caracteres (p. ej. "→"). Con
# errors="replace" se sustituyen por "?" en lugar de abortar el programa.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(errors="replace")

from .register import CATALOG, PRESETS, build_roster
from .runner import TournamentConfig, load_run, run_tournament, save_run

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


@app.command()
def tournament(
    roster: str = typer.Option("full", help=ROSTER_HELP),
    n_leagues: int = typer.Option(6, help="Número de ligas"),
    n_per_league: int = typer.Option(6, help="Estrategias por liga"),
    rounds: int = typer.Option(100, help="Rondas por partido"),
    n_seasons: int = typer.Option(20, help="Temporadas (sin contar la clasificatoria)"),
    k: int = typer.Option(2, help="Cuántas estrategias suben y bajan por liga"),
    seed: int = typer.Option(42, help="Semilla maestra"),
    qualifying: bool = typer.Option(True, help="Jugar temporada 0 clasificatoria"),
    out_dir: Path = typer.Option(Path("results/runs"), help="Carpeta donde guardar"),
    name: str = typer.Option(None, help="Nombre de la carpeta del run (por defecto, fecha y hora)"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Mostrar ascensos y descensos"),
):
    """Juega un torneo y guarda sus resultados (config.json + CSV)."""
    config = TournamentConfig(roster=roster, n_leagues=n_leagues, n_per_league=n_per_league,
                              rounds=rounds, n_seasons=n_seasons, n_ascend_descend=k,
                              seed=seed, qualifying=qualifying)
    try:
        result = run_tournament(config, verbose=verbose)
    except ValueError as e:
        raise typer.BadParameter(str(e))
    run_dir = save_run(result, out_dir=out_dir, name=name)
    typer.echo(f"Resultados guardados en: {run_dir}")


@app.command()
def stats(run_dir: Path = typer.Argument(..., help="Carpeta de un run")):
    """Resumen por estrategia y clasificación de la última temporada."""
    result = load_run(run_dir)

    typer.echo("Resumen de todos los partidos (incluida la clasificatoria):")
    typer.echo(summarize(result.matches).round(1).to_string(index=False))

    st = result.standings
    final = st[st["season"] == st["season"].max()]
    typer.echo(f"\nClasificación de la temporada {st['season'].max()}:")
    typer.echo(final[["league", "position", "name", "points"]].to_string(index=False))


@app.command()
def plot(run_dir: Path = typer.Argument(..., help="Carpeta de un run")):
    """Genera las gráficas del run en <run_dir>/figs/."""
    from .plots import plot_all  # import diferido: matplotlib solo cuando hace falta

    for path in plot_all(load_run(run_dir), Path(run_dir) / "figs"):
        typer.echo(f"  {path}")


if __name__ == "__main__":
    app()
