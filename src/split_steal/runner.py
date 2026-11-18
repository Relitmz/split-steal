"""
Ejecutar un torneo y guardar / cargar sus resultados.

Separa la *configuración* (qué torneo jugar) del *motor* (`simulator.py`) y de
la *persistencia* (archivos en disco):

    TournamentConfig --run_tournament()--> TournamentResult --save_run()--> carpeta
                                                            <--load_run()--

Cada ejecución se guarda en una carpeta `results/runs/<nombre>/` con:
  - config.json         parámetros + semilla + lista de estrategias (para poder repetirlo)
  - matches.csv         un partido por fila: season, league, A, B, puntos (pa, pb),
                        recuento de rondas cc/cd/dc/dd, ruido, primera traición,
                        represalias y ofertas de paz, seed (ver simulator.MatchResult)
  - standings.csv       clasificación por temporada y liga: season, league, position, name, points
  - strategy_stats.csv  cómo jugó cada estrategia en cada liga (calculado a partir de
                        matches.csv con analysis.strategy_stats)
  - rounds.csv.gz       OPCIONAL (save_rounds=True): cada jugada de cada ronda

Convención: la temporada 0 es la clasificatoria (liga 0, con todas las estrategias).
"""

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Union

import pandas as pd

from .analysis import strategy_stats as compute_strategy_stats
from .register import build_roster
from .simulator import League_Tournament, Payoff


@dataclass
class TournamentConfig:
    """Todos los parámetros que definen un torneo. Mismo config  =>  mismo resultado."""

    # Quién juega: un preset ("full", "clasicas"...) o una lista de estrategias,
    # p. ej. ["TitForTat", "ForgivingTitForTat(p=0.2)"]. Ver register.build_roster.
    roster: Union[str, List[str]] = "full"
    n_leagues: int = 6
    n_per_league: int = 6
    rounds: int = 100             # rondas por partido
    n_seasons: int = 20           # temporadas tras la clasificatoria
    n_ascend_descend: int = 2     # k: cuántos suben y bajan por liga
    seed: int = 42                # semilla maestra
    qualifying: bool = True       # jugar la temporada 0 clasificatoria
    # Matriz de pagos: R (ambos SPLIT), S (me traicionan), T (traiciono), P (ambos STEAL)
    payoff: Dict[str, int] = field(default_factory=lambda: Payoff().as_dict())
    noise: float = 0.0            # prob. de que una jugada se invierta (0 = sin ruido)
    save_rounds: bool = False     # guardar también cada jugada (rounds.csv.gz)


@dataclass
class TournamentResult:
    """Resultados de un torneo en forma de tablas de pandas."""

    config: TournamentConfig
    matches: pd.DataFrame
    standings: pd.DataFrame
    strategy_stats: pd.DataFrame
    strategies: List[str] = field(default_factory=list)
    rounds: Optional[pd.DataFrame] = None   # solo con save_rounds=True


def run_tournament(config: TournamentConfig, verbose: bool = False) -> TournamentResult:
    """Construye el roster, juega el torneo y devuelve sus tablas de resultados."""
    members = build_roster(config.roster)   # instancias nuevas en cada torneo

    tournament = League_Tournament(
        n_seasons=config.n_seasons,
        n_leagues=config.n_leagues,
        members=members,
        rounds=config.rounds,
        n_per_league=config.n_per_league,
        n_ascend_descend=config.n_ascend_descend,
        verbose=verbose,
        payoff=Payoff(**config.payoff),
        noise=config.noise,
        record_rounds=config.save_rounds,
    )
    tournament.run(seed=config.seed, qualifying=config.qualifying)

    matches = _tidy_matches(pd.DataFrame(tournament.matches))
    return TournamentResult(
        config=config,
        matches=matches,
        standings=pd.DataFrame(tournament.standings),
        strategy_stats=compute_strategy_stats(matches, config.payoff),
        strategies=list(members),
        rounds=pd.DataFrame(tournament.rounds) if config.save_rounds else None,
    )


def _tidy_matches(matches: pd.DataFrame) -> pd.DataFrame:
    """Tipos limpios: la ronda del primer robo es un entero que puede faltar (Int64)."""
    for col in ("first_steal_a", "first_steal_b"):
        matches[col] = matches[col].astype("Int64")
    return matches


def save_run(result: TournamentResult, out_dir: Union[str, Path] = "results/runs",
             name: Optional[str] = None) -> Path:
    """
    Guarda los resultados en `out_dir/name/` y devuelve esa ruta.

    Sin `name` se usa una marca de tiempo. Con un nombre fijo, volver a ejecutar
    el mismo config sobrescribe los archivos con contenido idéntico (útil para
    comprobar la reproducibilidad con `git diff`).
    """
    name = name or datetime.now().strftime("tournament_%Y%m%d_%H%M%S")
    run_dir = Path(out_dir) / name
    run_dir.mkdir(parents=True, exist_ok=True)

    meta = {"config": asdict(result.config), "strategies": result.strategies}
    (run_dir / "config.json").write_text(
        json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # lineterminator fijo: así los CSV son idénticos en Windows y Linux.
    for table in ("matches", "standings", "strategy_stats"):
        getattr(result, table).to_csv(run_dir / f"{table}.csv", index=False, lineterminator="\n")
    if result.rounds is not None:
        # Comprimido (puede ser grande). mtime=0: el .gz no guarda la hora, y así
        # el archivo sale idéntico byte a byte al repetir el mismo torneo.
        result.rounds.to_csv(run_dir / "rounds.csv.gz", index=False, lineterminator="\n",
                             compression={"method": "gzip", "mtime": 0})
    return run_dir


def load_run(run_dir: Union[str, Path]) -> TournamentResult:
    """Carga una carpeta creada por `save_run`."""
    run_dir = Path(run_dir)
    meta = json.loads((run_dir / "config.json").read_text(encoding="utf-8"))
    return TournamentResult(
        config=TournamentConfig(**meta["config"]),
        matches=pd.read_csv(run_dir / "matches.csv"),
        standings=pd.read_csv(run_dir / "standings.csv"),
        strategy_stats=pd.read_csv(run_dir / "strategy_stats.csv"),
        strategies=meta["strategies"],
        rounds=(pd.read_csv(run_dir / "rounds.csv.gz")
                if (run_dir / "rounds.csv.gz").exists() else None),
    )
