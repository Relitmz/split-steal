"""
Motor de simulación: reglas del juego, ligas y torneo con ascensos/descensos.

Estructura en tres niveles (de menor a mayor):

1. `play_match(a, b, rounds, seed)`: un partido de N rondas entre dos estrategias.
2. `League`: una liga "todos contra todos" a una sola vuelta entre sus miembros.
3. `League_Tournament`: varias ligas jerarquizadas (Liga 1 = la mejor) que se
   juegan durante varias temporadas; al final de cada una, los `k` primeros de cada
   liga suben a la de arriba y los `k` últimos bajan a la de abajo.

Reproducibilidad: todo parte de UNA semilla. El torneo crea un generador con ella
y de ahí saca la semilla de cada temporada/liga; cada liga saca de la suya la de
cada partido; y cada partido crea su propio `rng`, que se pasa a las estrategias.
Misma semilla + mismos parámetros  =>  exactamente los mismos resultados.

Este módulo no escribe archivos ni imprime nada salvo con `verbose=True`;
guardar resultados es cosa de `runner.py`.
"""

import itertools
from typing import Dict, List, Optional, Tuple

import numpy as np

from .strategies import SPLIT, STEAL, Strategy

# Matriz de pagos (puntos de A, puntos de B). Es un dilema del prisionero:
# - Cooperar los dos (3, 3) es lo mejor para el grupo.
# - Pero a cada uno, individualmente, le conviene traicionar: 5 > 3 si el otro
#   coopera y 1 > 0 si el otro traiciona.
# - Si ambos razonan así acaban en (1, 1), peor que (3, 3). En el juego REPETIDO
#   la amenaza de represalias hace que cooperar pueda salir rentable.
PAYOFF: Dict[Tuple[int, int], Tuple[int, int]] = {
    (SPLIT, SPLIT): (3, 3),
    (SPLIT, STEAL): (0, 5),
    (STEAL, SPLIT): (5, 0),
    (STEAL, STEAL): (1, 1),
}

# Límite superior para las semillas derivadas (cabe en un int32 positivo).
_MAX_SEED = 2**31 - 1


def _new_seed(rng: np.random.Generator) -> int:
    """Saca una semilla entera del generador `rng` (para derivar semillas hijas)."""
    return int(rng.integers(0, _MAX_SEED))


def play_round(a: int, b: int) -> Tuple[int, int]:
    """Puntos de una ronda dadas las acciones de A y B."""
    return PAYOFF[(a, b)]


def play_match(strategy_a: Strategy, strategy_b: Strategy,
               rounds: int = 50, seed: int = 0) -> Tuple[int, int]:
    """
    Juega un partido de `rounds` rondas y devuelve (puntos_A, puntos_B).

    Las dos estrategias deciden a la vez en cada ronda (ninguna ve la jugada
    actual de la otra) y reciben las historias del partido desde su punto de vista.
    """
    rng = np.random.default_rng(seed)

    # Borrar el estado interno que pudiera quedar de un partido anterior.
    strategy_a.reset()
    strategy_b.reset()

    history_a: List[int] = []
    history_b: List[int] = []
    points_a = points_b = 0

    for _ in range(rounds):
        # Cada estrategia elige su acción (se les pasa una copia para que no
        # puedan modificar la historia real por error).
        a = strategy_a.act(list(history_a), list(history_b), rng)
        b = strategy_b.act(list(history_b), list(history_a), rng)

        result_a, result_b = play_round(a, b)

        strategy_a.update_stats(a, result_a)
        strategy_b.update_stats(b, result_b)

        points_a += result_a
        points_b += result_b
        history_a.append(a)
        history_b.append(b)

    return points_a, points_b


class League:
    """
    Una liga: todos contra todos, una sola vuelta (cada pareja juega un partido).

    Con n miembros hay n·(n-1)/2 partidos. Los puntos de liga de una estrategia son
    la SUMA de los puntos obtenidos en todos sus partidos (no "victorias": en este
    juego lo que cuenta es cuánto acumulas, no a cuántos ganas).
    """

    def __init__(self, number: int, members: Dict[str, Strategy],
                 rounds: int, n_ascend_descend: int):
        self.id = number                      # 1 = liga superior, 2 = la siguiente…
        self.members = dict(members)          # {nombre: estrategia}
        self.league_rounds = rounds           # rondas por partido
        self.n_ascend_descend = n_ascend_descend

        self.clasification: List[Tuple[str, int]] = []  # [(nombre, puntos)] ordenado
        self.result: List[dict] = []          # [{"name", "points", "position"}]
        self.matches: List[dict] = []         # un dict por partido de la última temporada

    def play(self, season_seed: int, season: Optional[int] = None) -> List[dict]:
        """
        Juega la liga completa y devuelve la tabla final (`self.result`).

        Además rellena `self.matches` con cada partido (A, B, puntos y semilla) y
        abre/cierra las estadísticas por liga de cada estrategia.
        """
        rng = np.random.default_rng(season_seed)
        points = {name: 0 for name in self.members}
        self.matches = []

        for strategy in self.members.values():
            strategy.league_started(season, self.id)

        for a, b in itertools.combinations(self.members, 2):
            match_seed = _new_seed(rng)
            pa, pb = play_match(self.members[a], self.members[b],
                                rounds=self.league_rounds, seed=match_seed)
            points[a] += pa
            points[b] += pb
            self.matches.append({"A": a, "B": b, "pa": pa, "pb": pb, "seed": match_seed})

        for strategy in self.members.values():
            strategy.league_finished()

        # Orden: más puntos primero; en empate, orden alfabético (desempate
        # determinista, para que la clasificación sea reproducible).
        self.clasification = sorted(points.items(), key=lambda kv: (-kv[1], kv[0]))
        self.result = [{"name": n, "points": p, "position": i + 1}
                       for i, (n, p) in enumerate(self.clasification)]
        return self.result

    # ---------------------------------------------- ascensos y descensos
    def _k(self) -> int:
        return max(0, int(self.n_ascend_descend))

    def get_top(self) -> Dict[str, Strategy]:
        """Los k primeros de la última clasificación (candidatos a subir)."""
        return {n: self.members[n] for n, _ in self.clasification[:self._k()]}

    def get_bottom(self) -> Dict[str, Strategy]:
        """Los k últimos de la última clasificación (candidatos a bajar)."""
        k = self._k()
        return {n: self.members[n] for n, _ in (self.clasification[-k:] if k else [])}

    def remove_top(self) -> Dict[str, Strategy]:
        """Quita de la liga a los k primeros."""
        for name in self.get_top():
            self.members.pop(name)
        return self.members

    def remove_bottom(self) -> Dict[str, Strategy]:
        """Quita de la liga a los k últimos."""
        for name in self.get_bottom():
            self.members.pop(name)
        return self.members

    def add_members(self, new_members: Dict[str, Strategy]) -> None:
        """Añade estrategias (las que llegan por ascenso o descenso)."""
        self.members.update(new_members)


class League_Tournament:
    """
    Torneo de varias temporadas con ligas jerarquizadas y ascensos/descensos.

    Flujo de `run(seed)`:
      1. Temporada 0 (clasificatoria): una única liga con TODAS las estrategias.
         Su clasificación se corta en bloques de `n_per_league`: los mejores van a
         la Liga 1, los siguientes a la Liga 2, etc. (Alternativa: `qualifying=False`
         reparte en el orden del roster, sin jugar la clasificatoria.)
      2. Temporadas 1..n_seasons: se juegan todas las ligas y después, a la vez,
         los k primeros de cada liga (salvo la Liga 1) suben una categoría y los k
         últimos (salvo la última liga) bajan una.

    Todo lo jugado queda en `self.matches` y `self.standings` (listas de dicts,
    una fila por partido / por estrategia y liga) para poder guardarlo y analizarlo.
    """

    def __init__(self, n_seasons: int, n_leagues: int, members: Dict[str, Strategy],
                 rounds: int, n_per_league: int, n_ascend_descend: int,
                 verbose: bool = False):
        # --- Validación: mejor fallar pronto con un mensaje claro que simular mal.
        if n_leagues < 1 or n_per_league < 2:
            raise ValueError("Se necesita al menos 1 liga y 2 estrategias por liga.")
        if len(members) != n_leagues * n_per_league:
            raise ValueError(
                f"Se esperaban n_leagues × n_per_league = {n_leagues} × {n_per_league} = "
                f"{n_leagues * n_per_league} estrategias, pero hay {len(members)}.")
        if n_ascend_descend < 0 or 2 * n_ascend_descend > n_per_league:
            # Una liga intermedia pierde k por arriba y k por abajo: deben ser distintos.
            raise ValueError(
                f"n_ascend_descend={n_ascend_descend} no válido: debe cumplirse "
                f"0 ≤ 2·k ≤ n_per_league ({n_per_league}).")

        self.seasons = n_seasons
        self.n_leagues = n_leagues
        self.members = dict(members)
        self.league_rounds = rounds
        self.n_per_league = n_per_league
        self.n_ascend_descend = n_ascend_descend
        self.verbose = verbose

        self.leagues: List[League] = []
        self.matches: List[dict] = []    # filas: season, league, A, B, pa, pb, seed
        self.standings: List[dict] = []  # filas: season, league, position, name, points

    # ---------------------------------------------------------------- utilidades
    def _log(self, msg: str = "") -> None:
        if self.verbose:
            print(msg)

    def _record(self, season: int, league: League) -> None:
        """Guarda los partidos y la clasificación de una liga recién jugada."""
        for m in league.matches:
            self.matches.append({"season": season, "league": league.id, **m})
        for row in league.result:
            self.standings.append({"season": season, "league": league.id, **row})

    def _split_into_leagues(self, ordered_names: List[str]) -> None:
        """Crea las ligas cortando `ordered_names` en bloques consecutivos de `n_per_league`."""
        self.leagues = []
        for i in range(self.n_leagues):
            block = ordered_names[i * self.n_per_league:(i + 1) * self.n_per_league]
            self.leagues.append(League(
                number=i + 1,
                members={name: self.members[name] for name in block},
                rounds=self.league_rounds,
                n_ascend_descend=self.n_ascend_descend,
            ))

    # ---------------------------------------------------------------- fases
    def simulate_first_season(self, seed: int) -> None:
        """Temporada 0: liga única con todos y reparto por bloques según la clasificación."""
        all_league = League(number=0, members=self.members,
                            rounds=self.league_rounds, n_ascend_descend=0)
        all_league.play(season_seed=seed, season=0)
        self._record(0, all_league)

        sorted_global = [name for name, _ in all_league.clasification]
        self._split_into_leagues(sorted_global)

        self._log("Temporada 0 (clasificatoria) — reparto inicial:")
        for league in self.leagues:
            self._log(f"  Liga {league.id}: {', '.join(league.members)}")

    def initialize_spread_leagues(self) -> None:
        """Alternativa a la clasificatoria: reparte en el orden del roster."""
        self._split_into_leagues(list(self.members))
        self._log("Reparto inicial por orden del roster:")
        for league in self.leagues:
            self._log(f"  Liga {league.id}: {', '.join(league.members)}")

    def simulate_seasons(self, seed: int) -> None:
        """Temporadas 1..n_seasons con ascensos/descensos entre ligas adyacentes."""
        rng = np.random.default_rng(seed)
        last = self.n_leagues - 1

        for season in range(1, self.seasons + 1):
            # 1) Jugar todas las ligas
            for league in self.leagues:
                league.play(season_seed=_new_seed(rng), season=season)
                self._record(season, league)

            # 2) Decidir quién sube y quién baja ANTES de mover a nadie, para que
            #    los movimientos sean simultáneos.
            ascends = [league.get_top() for league in self.leagues]
            descends = [league.get_bottom() for league in self.leagues]

            # 3) Sacar de su liga a los que se van (la Liga 1 no tiene a dónde subir
            #    y la última no tiene a dónde bajar).
            for x, league in enumerate(self.leagues):
                if x > 0:
                    league.remove_top()
                if x < last:
                    league.remove_bottom()

            # 4) Meterlos en su nueva liga: a la liga x llegan los que bajan de la
            #    x-1 y los que suben de la x+1.
            for x, league in enumerate(self.leagues):
                if x > 0:
                    league.add_members(descends[x - 1])
                if x < last:
                    league.add_members(ascends[x + 1])

            if self.verbose:
                self._log(f"\nTemporada {season}")
                for x, league in enumerate(self.leagues):
                    up = ", ".join(ascends[x]) if x > 0 else "-"
                    down = ", ".join(descends[x]) if x < last else "-"
                    self._log(f"  Liga {league.id}: sube [{up}]  baja [{down}]")

    def run(self, seed: int, qualifying: bool = True) -> "League_Tournament":
        """
        Ejecuta el torneo completo a partir de UNA semilla maestra.

        De la semilla maestra salen (en este orden fijo) la semilla de la
        clasificatoria y la de las temporadas; así basta guardar `seed` para
        poder repetir el torneo idéntico.
        """
        rng = np.random.default_rng(seed)
        qualifying_seed, seasons_seed = _new_seed(rng), _new_seed(rng)

        if qualifying:
            self.simulate_first_season(qualifying_seed)
        else:
            self.initialize_spread_leagues()
        self.simulate_seasons(seasons_seed)
        return self
