"""
Tablas derivadas: de los datos en bruto (un partido por fila) a estadísticas.

Idea: el motor solo registra HECHOS (qué pasó en cada partido, en `matches`).
Todo lo demás se calcula aquí a partir de ellos, con pandas. Así hay una única
fuente de verdad y cualquier estadística nueva se puede calcular también sobre
resultados ya guardados.

Funciones:
- `perspective(matches)`: cada partido visto desde cada jugador (2 filas por partido).
- `strategy_stats(matches, payoff)`: cómo jugó cada estrategia en cada liga.
"""

from typing import Dict, Mapping, Union

import numpy as np
import pandas as pd

from .simulator import Payoff

# Columnas "de A" y "de B" en `matches` -> nombre desde el punto de vista del jugador.
_MINE = {"pa": "points", "pb": "points_against",
         "cc": "mutual_split", "cd": "betrayed", "dc": "stole", "dd": "mutual_steal",
         "flips_a": "noise_flips", "first_steal_a": "first_steal",
         "provoked_a": "provoked", "retaliated_a": "retaliated",
         "after_dd": "after_mutual_steal", "peace_a": "peace_offers"}
# Para B se intercambian los papeles: lo que para A es "traicionado" (cd) para B es "robó".
_THEIRS = {"pb": "points", "pa": "points_against",
           "cc": "mutual_split", "dc": "betrayed", "cd": "stole", "dd": "mutual_steal",
           "flips_b": "noise_flips", "first_steal_b": "first_steal",
           "provoked_b": "provoked", "retaliated_b": "retaliated",
           "after_dd": "after_mutual_steal", "peace_b": "peace_offers"}
_KEYS = ["season", "league"]


def perspective(matches: pd.DataFrame) -> pd.DataFrame:
    """
    Duplica cada partido para verlo desde cada jugador.

    Devuelve columnas: season, league, name, opponent, points, points_against,
    mutual_split, betrayed (yo SPLIT, él STEAL), stole (yo STEAL, él SPLIT),
    mutual_steal, noise_flips, first_steal, provoked, retaliated,
    after_mutual_steal, peace_offers, result (+1 gana / 0 empata / -1 pierde).
    """
    keys = [k for k in _KEYS if k in matches.columns]
    as_a = matches[keys + ["A", "B"] + list(_MINE)].rename(
        columns={"A": "name", "B": "opponent", **_MINE})
    as_b = matches[keys + ["B", "A"] + list(_THEIRS)].rename(
        columns={"B": "name", "A": "opponent", **_THEIRS})
    view = pd.concat([as_a, as_b], ignore_index=True)
    view["result"] = np.sign(view["points"] - view["points_against"]).astype(int)
    return view


def _rate(num: pd.Series, den: pd.Series) -> pd.Series:
    """num / den, con NaN donde den = 0 (p. ej. nadie la provocó nunca)."""
    return num / den.where(den > 0)


def strategy_stats(matches: pd.DataFrame,
                   payoff: Union[Payoff, Mapping[str, int], None] = None) -> pd.DataFrame:
    """
    Estadísticas de cada estrategia en cada liga de cada temporada.

    Recuentos (sumas sobre sus partidos):
      matches_played, rounds_played, points, points_against, wins, draws, losses,
      mutual_split, betrayed, stole, mutual_steal, times_split, times_steal,
      score_split / score_steal (puntos ganados en rondas en que jugó SPLIT / STEAL),
      noise_flips, provoked, retaliated, after_mutual_steal, peace_offers.

    Tasas (0-1, NaN si no hubo ocasión):
      coop_rate         % de rondas en que jugó SPLIT
      betrayed_rate     % de sus SPLIT que fueron traicionados
      retaliation_rate  tras un robo del rival, % de veces que respondió robando
      peace_rate        tras una traición mutua, % de veces que ofreció la paz (SPLIT)
      first_steal_mean  ronda media de su primer robo (en los partidos en que robó)
    """
    if isinstance(payoff, Mapping):
        payoff = Payoff(**payoff)
    payoff = payoff or Payoff()

    view = perspective(matches)
    keys = [k for k in _KEYS if k in view.columns] + ["name"]
    view["wins"] = view["result"] == 1
    view["draws"] = view["result"] == 0
    view["losses"] = view["result"] == -1

    counts = ["points", "points_against", "wins", "draws", "losses",
              "mutual_split", "betrayed", "stole", "mutual_steal", "noise_flips",
              "provoked", "retaliated", "after_mutual_steal", "peace_offers"]
    g = view.groupby(keys, sort=True)
    s = g[counts].sum().astype(int)
    s.insert(0, "matches_played", g.size())
    s["first_steal_mean"] = g["first_steal"].mean().astype("float64")
    s = s.reset_index()

    s["rounds_played"] = s[["mutual_split", "betrayed", "stole", "mutual_steal"]].sum(axis=1)
    s["times_split"] = s["mutual_split"] + s["betrayed"]
    s["times_steal"] = s["stole"] + s["mutual_steal"]
    s["score_split"] = payoff.R * s["mutual_split"] + payoff.S * s["betrayed"]
    s["score_steal"] = payoff.T * s["stole"] + payoff.P * s["mutual_steal"]

    s["coop_rate"] = _rate(s["times_split"], s["rounds_played"])
    s["betrayed_rate"] = _rate(s["betrayed"], s["times_split"])
    s["retaliation_rate"] = _rate(s["retaliated"], s["provoked"])
    s["peace_rate"] = _rate(s["peace_offers"], s["after_mutual_steal"])

    first = keys + ["matches_played", "rounds_played", "times_split", "times_steal",
                    "score_split", "score_steal"]
    return s[first + [c for c in s.columns if c not in first]]


def final_ranking(standings: pd.DataFrame) -> pd.DataFrame:
    """
    Clasificación final del torneo, de 1 (campeón) a N, sea cual sea el formato.

    Se toma la ÚLTIMA temporada jugada y se ordena por liga y posición: primero toda
    la Liga 1, luego la 2... En "todos contra todos" (una sola liga) es esa tabla.
    Así se pueden comparar formatos y promediar posiciones entre semillas.

    Columnas: rank, name, league, position, points.
    """
    last = standings[standings["season"] == standings["season"].max()]
    ranked = last.sort_values(["league", "position"], ignore_index=True)
    ranked.insert(0, "rank", range(1, len(ranked) + 1))
    return ranked[["rank", "name", "league", "position", "points"]]
