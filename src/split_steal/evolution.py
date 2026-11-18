"""
Evolución: ¿qué estrategias sobreviven si las que ganan más puntos se multiplican?

Hasta ahora cada estrategia era UNA jugadora. Aquí pensamos en una POBLACIÓN: hay
muchas jugadoras de cada tipo y lo que cambia es la proporción (la "cuota") de cada
estrategia. Cada generación:

  1. Cada jugadora juega contra la población actual. Su "aptitud" (fitness) es lo que
     gana de media por ronda contra un rival elegido al azar de esa población:
         f_i = sum_j  M[i, j] * x_j
     donde x_j es la cuota de la estrategia j y M[i, j] los puntos por ronda de i contra j.
  2. Las que ganan más que la media crecen y las que ganan menos se reducen
     (dinámica del replicador, versión discreta):
         x_i(siguiente) = x_i * f_i / media(f)

Es la simulación "ecológica" de Axelrod (1984): no hay mutaciones, solo selección.
Responde preguntas como: ¿la cooperación puede abrirse paso en un mundo de egoístas?
¿las traicioneras que viven de explotar a otras sobreviven cuando sus víctimas desaparecen?

Pasos del cálculo:
  - `payoff_matrix`: juega TODAS las parejas, incluida cada estrategia contra una copia
    de sí misma (en una población te puedes cruzar con alguien igual que tú), con varias
    semillas, y promedia los puntos por ronda -> matriz M (N x N).
  - `evolve`: aplica la regla de arriba generación a generación. Es determinista y muy
    rápido (solo multiplica matrices), así que se pueden probar muchos escenarios con
    la misma matriz.

Resultados (`results/evolution/<nombre>/`): config.json, matrix.csv (M) y shares.csv
(una fila por generación, una columna por estrategia).
"""

import json
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Union

import numpy as np
import pandas as pd

from .multiseed import default_workers
from .register import build_roster, resolve_selection
from .simulator import Payoff, play_match

# Por debajo de esta cuota una estrategia se considera extinguida (se pone a 0).
EXTINCTION = 1e-9


@dataclass
class EvolutionConfig:
    """Todo lo que define una simulación evolutiva. Mismo config => mismo resultado."""

    roster: Union[str, List[str]] = "full"   # estrategias presentes (ver register.build_roster)
    rounds: int = 100                         # rondas por partido al calcular la matriz
    noise: float = 0.0
    payoff: Dict[str, int] = field(default_factory=lambda: Payoff().as_dict())
    n_seeds: int = 20                         # partidos por pareja para promediar M
    seed: int = 42
    generations: int = 500
    # Cuotas iniciales {nombre: peso}; las no citadas empiezan en 0. None = todas iguales.
    initial: Optional[Dict[str, float]] = None


# =============================================================================
# Matriz de pagos entre estrategias
# =============================================================================

def _pair_scores(task: dict):
    """Lo que calcula cada proceso: puntos por ronda medios de i contra j y de j contra i."""
    from .register import make_strategy
    payoff = Payoff(**task["payoff"])
    total_i = total_j = 0.0
    for s in task["seeds"]:
        # Semilla propia de cada partido, derivada de (semilla, i, j): no depende del
        # orden en que se calculen las parejas ni del número de procesos.
        match_seed = int(np.random.default_rng([s, task["i"], task["j"]]).integers(0, 2**31 - 1))
        a, b = make_strategy(task["spec_i"]), make_strategy(task["spec_j"])   # instancias nuevas
        m = play_match(a, b, rounds=task["rounds"], seed=match_seed, payoff=payoff,
                       noise=task["noise"])
        total_i += m.pa
        total_j += m.pb
    n = len(task["seeds"]) * task["rounds"]
    return task["i"], task["j"], total_i / n, total_j / n


def payoff_matrix(config: EvolutionConfig, workers: Optional[int] = None) -> pd.DataFrame:
    """
    Matriz M (N x N, filas = estrategia, columnas = rival): puntos medios por ronda.
    Incluye la diagonal (cada estrategia contra una copia de sí misma).
    """
    specs = resolve_selection(config.roster)
    names = list(build_roster(config.roster))           # valida y da los nombres
    seeds = [config.seed + k for k in range(config.n_seeds)]
    tasks = [dict(spec_i=specs[i], spec_j=specs[j], i=i, j=j, rounds=config.rounds,
                  noise=config.noise, payoff=config.payoff, seeds=seeds)
             for i in range(len(specs)) for j in range(i, len(specs))]
    workers = min(workers or default_workers(), len(tasks))
    if workers <= 1:
        results = [_pair_scores(t) for t in tasks]
    else:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            results = list(pool.map(_pair_scores, tasks, chunksize=8))
    M = np.zeros((len(names), len(names)))
    for i, j, s_ij, s_ji in results:
        if i == j:
            M[i, i] = (s_ij + s_ji) / 2          # dos copias: simétrico por definición
        else:
            M[i, j], M[j, i] = s_ij, s_ji
    return pd.DataFrame(M, index=names, columns=names)


# =============================================================================
# Dinámica de poblaciones
# =============================================================================

def initial_shares(names: List[str], initial: Optional[Dict[str, float]] = None) -> np.ndarray:
    """Cuotas iniciales normalizadas a 1. Sin `initial`, todas iguales."""
    if not initial:
        return np.full(len(names), 1.0 / len(names))
    unknown = sorted(set(initial) - set(names))
    if unknown:
        raise ValueError(f"cuotas iniciales para estrategias que no están: {', '.join(unknown)}")
    x = np.array([float(initial.get(n, 0.0)) for n in names])
    if (x < 0).any() or x.sum() <= 0:
        raise ValueError("las cuotas iniciales deben ser >= 0 y no todas 0")
    return x / x.sum()


def evolve(matrix: pd.DataFrame, initial: Optional[Dict[str, float]] = None,
           generations: int = 500) -> pd.DataFrame:
    """
    Dinámica del replicador: devuelve una tabla con una fila por generación (0 = inicio)
    y una columna por estrategia con su cuota (cada fila suma 1).
    """
    names = list(matrix.index)
    M = matrix.to_numpy(dtype=float)
    # La regla necesita aptitudes positivas: si hay pagos negativos, se desplazan todos
    # por igual (no cambia quién gana a quién, solo evita "cuotas negativas").
    shift = max(0.0, -M.min()) + 1e-12
    x = initial_shares(names, initial)
    history = [x]
    for _ in range(generations):
        fitness = (M + shift) @ x
        x = x * fitness / (x @ fitness)
        x[x < EXTINCTION] = 0.0                   # extinguida: ya no vuelve
        x = x / x.sum()
        history.append(x)
    shares = pd.DataFrame(history, columns=names)
    shares.index.name = "generation"
    return shares


@dataclass
class EvolutionResult:
    config: EvolutionConfig
    matrix: pd.DataFrame
    shares: pd.DataFrame

    @property
    def final(self) -> pd.Series:
        """Cuotas en la última generación, de mayor a menor (solo las supervivientes)."""
        last = self.shares.iloc[-1]
        return last[last > 0].sort_values(ascending=False)


def run_evolution(config: EvolutionConfig, workers: Optional[int] = None,
                  matrix: Optional[pd.DataFrame] = None) -> EvolutionResult:
    """Calcula la matriz (o reutiliza la que se pase) y simula la evolución."""
    if matrix is None:
        matrix = payoff_matrix(config, workers)
    shares = evolve(matrix, config.initial, config.generations)
    return EvolutionResult(config, matrix, shares)


def save_evolution(result: EvolutionResult, out_dir: Union[str, Path], name: str) -> Path:
    run_dir = Path(out_dir) / name
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "config.json").write_text(
        json.dumps({"config": asdict(result.config)}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8", newline="\n")
    result.matrix.to_csv(run_dir / "matrix.csv", lineterminator="\n", float_format="%.6f")
    result.shares.to_csv(run_dir / "shares.csv", lineterminator="\n", float_format="%.8f")
    return run_dir


def load_evolution(run_dir: Union[str, Path]) -> EvolutionResult:
    run_dir = Path(run_dir)
    meta = json.loads((run_dir / "config.json").read_text(encoding="utf-8"))
    return EvolutionResult(EvolutionConfig(**meta["config"]),
                           pd.read_csv(run_dir / "matrix.csv", index_col=0),
                           pd.read_csv(run_dir / "shares.csv", index_col="generation"))
