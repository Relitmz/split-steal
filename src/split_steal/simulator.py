"""
Motor de simulación: reglas del juego, ligas y torneo con ascensos/descensos.

Estructura en tres niveles (de menor a mayor):

0. `Payoff`: la matriz de pagos (configurable; por defecto 3/0/5/1).
1. `play_match(a, b, rounds, seed, payoff, noise)`: un partido de N rondas entre dos
   estrategias; devuelve un `MatchResult` con los puntos y todas las cuentas del partido.
2. `League`: una liga "todos contra todos" a una sola vuelta entre sus miembros.
3. `League_Tournament`: varias ligas jerarquizadas (Liga 1 = la mejor) que se
   juegan durante varias temporadas; al final de cada una, los `k` primeros de cada
   liga suben a la de arriba y los `k` últimos bajan a la de abajo.
4. `RoundRobinTournament`: formato alternativo, una única liga con todas (sin
   temporadas ni ascensos), como en los torneos de Axelrod.

Reproducibilidad: todo parte de UNA semilla. El torneo crea un generador con ella
y de ahí saca la semilla de cada temporada/liga; cada liga saca de la suya la de
cada partido; y cada partido crea su propio `rng`, que se pasa a las estrategias.
Misma semilla + mismos parámetros  =>  exactamente los mismos resultados.

Este módulo no escribe archivos ni imprime nada salvo con `verbose=True`;
guardar resultados es cosa de `runner.py`.
"""

import itertools
from dataclasses import asdict, dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np

from .strategies import SPLIT, STEAL, Strategy


# =============================================================================
# Reglas del juego: matriz de pagos
# =============================================================================

@dataclass(frozen=True)
class Payoff:
    """
    Puntos de cada resultado de una ronda, con los nombres clásicos:

        R (Reward)     ambos SPLIT                       -> R para cada uno
        S (Sucker)     yo SPLIT y el rival STEAL         -> S para mí ("el primo")
        T (Temptation) yo STEAL y el rival SPLIT         -> T para mí
        P (Punishment) ambos STEAL                       -> P para cada uno

    Por defecto 3/0/5/1, un dilema del prisionero:
    - Cooperar los dos (3, 3) es lo mejor para el grupo.
    - Pero a cada uno, individualmente, le conviene traicionar: T > R si el otro
      coopera y P > S si el otro traiciona.
    - Si ambos razonan así acaban en (1, 1), peor que (3, 3). En el juego REPETIDO
      la amenaza de represalias hace que cooperar pueda salir rentable.

    Se pueden poner otros valores para experimentar (incluso juegos que ya no son
    un dilema del prisionero, como el "juego del gallina": T > R > S > P).
    """

    R: int = 3
    S: int = 0
    T: int = 5
    P: int = 1

    def matrix(self) -> Dict[Tuple[int, int], Tuple[int, int]]:
        """(acción A, acción B) -> (puntos A, puntos B)."""
        return {
            (SPLIT, SPLIT): (self.R, self.R),
            (SPLIT, STEAL): (self.S, self.T),
            (STEAL, SPLIT): (self.T, self.S),
            (STEAL, STEAL): (self.P, self.P),
        }

    @property
    def is_prisoners_dilemma(self) -> bool:
        """T > R > P > S (traicionar tienta) y 2R > T + S (alternarse no compensa)."""
        return self.T > self.R > self.P > self.S and 2 * self.R > self.T + self.S

    def as_dict(self) -> Dict[str, int]:
        return asdict(self)


DEFAULT_PAYOFF = Payoff()
# Matriz por defecto, para quien solo necesita consultarla.
PAYOFF: Dict[Tuple[int, int], Tuple[int, int]] = DEFAULT_PAYOFF.matrix()

# Límite superior para las semillas derivadas (cabe en un int32 positivo).
_MAX_SEED = 2**31 - 1


def _new_seed(rng: np.random.Generator) -> int:
    """Saca una semilla entera del generador `rng` (para derivar semillas hijas)."""
    return int(rng.integers(0, _MAX_SEED))


def play_round(a: int, b: int, payoff: Payoff = DEFAULT_PAYOFF) -> Tuple[int, int]:
    """Puntos de una ronda dadas las acciones de A y B."""
    return payoff.matrix()[(a, b)]


# =============================================================================
# Un partido
# =============================================================================

@dataclass
class MatchResult:
    """
    Todo lo que se registra de un partido entre A y B.

    Las cuentas se hacen con las jugadas que REALMENTE ocurrieron (si hay ruido,
    pueden no ser las que la estrategia eligió). Letras: c = SPLIT, d = STEAL
    (de *cooperate* / *defect*), la primera de A y la segunda de B.
    """

    pa: int = 0                 # puntos de A
    pb: int = 0                 # puntos de B
    cc: int = 0                 # rondas: ambos SPLIT (cooperación mutua)
    cd: int = 0                 # rondas: A SPLIT, B STEAL  -> A es traicionado
    dc: int = 0                 # rondas: A STEAL, B SPLIT  -> A roba
    dd: int = 0                 # rondas: ambos STEAL (traición mutua)
    flips_a: int = 0            # jugadas de A invertidas por el ruido
    flips_b: int = 0
    first_steal_a: Optional[int] = None   # ronda (desde 1) del primer STEAL de A; None si nunca
    first_steal_b: Optional[int] = None
    # Reacciones (miden la "personalidad" observada, no la declarada):
    provoked_a: int = 0         # rondas en que B había robado en la ronda anterior
    retaliated_a: int = 0       # ...y A respondió robando (represalia)
    provoked_b: int = 0
    retaliated_b: int = 0
    after_dd: int = 0           # rondas que siguen a una traición mutua
    peace_a: int = 0            # ...y A ofreció la paz (SPLIT)
    peace_b: int = 0
    # Jugada a jugada (solo si se pide): [(ronda, jugada A, jugada B, ruido A, ruido B)]
    rounds: Optional[List[Tuple[int, int, int, bool, bool]]] = field(default=None, repr=False)

    @property
    def scores(self) -> Tuple[int, int]:
        return self.pa, self.pb

    def to_row(self) -> Dict[str, object]:
        """Las cuentas como dict plano (sin el detalle de rondas), para una tabla."""
        row = asdict(self)
        row.pop("rounds")
        return row


def play_match(strategy_a: Strategy, strategy_b: Strategy,
               rounds: int = 50, seed: int = 0,
               payoff: Payoff = DEFAULT_PAYOFF, noise: float = 0.0,
               record_rounds: bool = False) -> MatchResult:
    """
    Juega un partido de `rounds` rondas y devuelve un `MatchResult`.

    Las dos estrategias deciden a la vez en cada ronda (ninguna ve la jugada
    actual de la otra) y reciben las historias del partido desde su punto de vista.

    Ruido (`noise`): con esa probabilidad, la jugada elegida se invierte antes de
    jugarse (un error, un malentendido). Las historias guardan lo que REALMENTE se
    jugó: la estrategia no sabe si el rival se equivocó o la traicionó a propósito.

    Aleatoriedad: las estrategias usan un generador y el ruido OTRO distinto (ambos
    derivados de `seed`). Así, el mismo partido con y sin ruido usa exactamente los
    mismos números aleatorios para las estrategias, y las diferencias se deben solo
    al ruido. Con `noise=0` no se gasta ningún número en ruido.
    """
    if not 0.0 <= noise <= 1.0:
        raise ValueError(f"noise debe estar entre 0 y 1 (es {noise})")
    matrix = payoff.matrix()
    rng = np.random.default_rng(seed)
    noise_rng = np.random.default_rng([seed, 1]) if noise > 0 else None

    # Borrar el estado interno que pudiera quedar de un partido anterior.
    strategy_a.reset()
    strategy_b.reset()

    history_a: List[int] = []
    history_b: List[int] = []
    m = MatchResult(rounds=[] if record_rounds else None)

    for t in range(rounds):
        # Cada estrategia elige su acción (se les pasa una copia para que no
        # puedan modificar la historia real por error).
        a = strategy_a.act(list(history_a), list(history_b), rng)
        b = strategy_b.act(list(history_b), list(history_a), rng)

        flip_a = flip_b = False
        if noise_rng is not None:
            flip_a = bool(noise_rng.random() < noise)
            flip_b = bool(noise_rng.random() < noise)
            if flip_a:
                a = 1 - a
                m.flips_a += 1
            if flip_b:
                b = 1 - b
                m.flips_b += 1

        result_a, result_b = matrix[(a, b)]
        strategy_a.observe(a, result_a)
        strategy_b.observe(b, result_b)
        m.pa += result_a
        m.pb += result_b

        # --- contabilidad de la ronda
        if a == SPLIT:
            if b == SPLIT:
                m.cc += 1
            else:
                m.cd += 1
        elif b == SPLIT:
            m.dc += 1
        else:
            m.dd += 1
        if a == STEAL and m.first_steal_a is None:
            m.first_steal_a = t + 1
        if b == STEAL and m.first_steal_b is None:
            m.first_steal_b = t + 1
        if t > 0:
            prev_a, prev_b = history_a[-1], history_b[-1]
            if prev_b == STEAL:
                m.provoked_a += 1
                m.retaliated_a += a == STEAL
            if prev_a == STEAL:
                m.provoked_b += 1
                m.retaliated_b += b == STEAL
            if prev_a == STEAL and prev_b == STEAL:
                m.after_dd += 1
                m.peace_a += a == SPLIT
                m.peace_b += b == SPLIT
        if record_rounds:
            m.rounds.append((t + 1, a, b, flip_a, flip_b))

        history_a.append(a)
        history_b.append(b)

    return m


# =============================================================================
# Clasificación y desempate
# =============================================================================

TIEBREAKERS = ("points", "head_to_head", "point_diff", "draw")


def rank_league(matches: List[dict], lots: Dict[str, float]) -> List[dict]:
    """
    Ordena una liga a partir de sus partidos. Criterios, en este orden:

      1. points        más puntos en la liga.
      2. head_to_head  entre las empatadas a puntos: más puntos en los partidos
                       que jugaron ENTRE ELLAS (una "mini-liga" de las empatadas).
      3. point_diff    diferencia de puntos en toda la liga (a favor - en contra):
                       premia a quien gana más de lo que deja ganar.
      4. draw          sorteo (`lots`: un número aleatorio por estrategia; el
                       menor queda delante). Reproducible porque sale de la semilla.

    Simplificación: el enfrentamiento directo se calcula una vez sobre todo el grupo
    empatado a puntos (no se repite para los subgrupos que sigan empatados).

    Devuelve una fila por estrategia con: name, points, position, point_diff,
    tied (cuántas empataban a puntos con ella, incluida ella; 1 = nadie) y
    decided_by (qué criterio la separó de la SIGUIENTE en la tabla; "-" en la
    última). Con decided_by se puede contar, p. ej., cuántos descensos decidió el sorteo.
    """
    points: Dict[str, int] = {n: 0 for n in lots}
    against: Dict[str, int] = {n: 0 for n in lots}
    for m in matches:
        points[m["A"]] += m["pa"]
        points[m["B"]] += m["pb"]
        against[m["A"]] += m["pb"]
        against[m["B"]] += m["pa"]

    # Grupos de empatadas a puntos y, dentro de cada grupo, sus puntos entre ellas.
    groups: Dict[int, set] = {}
    for n, p in points.items():
        groups.setdefault(p, set()).add(n)
    h2h: Dict[str, int] = {n: 0 for n in points}
    for m in matches:
        a, b = m["A"], m["B"]
        if points[a] == points[b]:          # ambas en el mismo grupo de empate
            h2h[a] += m["pa"]
            h2h[b] += m["pb"]

    def key(n: str) -> Tuple[int, int, int, float]:
        # Tupla en el orden de TIEBREAKERS (negativos = "más es mejor").
        return (-points[n], -h2h[n], -(points[n] - against[n]), lots[n])

    order = sorted(points, key=key)
    rows = []
    for i, n in enumerate(order):
        decided_by = "-"           # la última no tiene a nadie debajo
        if i + 1 < len(order):
            mine, nxt = key(n), key(order[i + 1])
            decided_by = next(c for c, x, y in zip(TIEBREAKERS, mine, nxt) if x != y)
        rows.append({"name": n, "points": points[n], "position": i + 1,
                     "point_diff": points[n] - against[n], "tied": len(groups[points[n]]),
                     "decided_by": decided_by})
    return rows


class League:
    """
    Una liga: todos contra todos, una sola vuelta (cada pareja juega un partido).

    Con n miembros hay n·(n-1)/2 partidos. Los puntos de liga de una estrategia son
    la SUMA de los puntos obtenidos en todos sus partidos (no "victorias": en este
    juego lo que cuenta es cuánto acumulas, no a cuántos ganas).
    """

    def __init__(self, number: int, members: Dict[str, Strategy],
                 rounds: int, n_ascend_descend: int,
                 payoff: Payoff = DEFAULT_PAYOFF, noise: float = 0.0,
                 record_rounds: bool = False):
        self.id = number                      # 1 = liga superior, 2 = la siguiente…
        self.members = dict(members)          # {nombre: estrategia}
        self.league_rounds = rounds           # rondas por partido
        self.n_ascend_descend = n_ascend_descend
        self.payoff = payoff
        self.noise = noise
        self.record_rounds = record_rounds

        self.clasification: List[Tuple[str, int]] = []  # [(nombre, puntos)] ordenado
        self.result: List[dict] = []          # [{"name", "points", "position"}]
        self.matches: List[dict] = []         # un dict por partido de la última temporada
        self.round_rows: List[dict] = []      # jugada a jugada (solo con record_rounds)

    def play(self, season_seed: int, season: Optional[int] = None) -> List[dict]:
        """
        Juega la liga completa y devuelve la tabla final (`self.result`).

        Además rellena `self.matches` con una fila por partido: quién jugó, la
        semilla y todas las cuentas de `MatchResult` (puntos, cooperaciones, ruido...).
        """
        rng = np.random.default_rng(season_seed)
        points = {name: 0 for name in self.members}
        self.matches = []
        self.round_rows = []

        for a, b in itertools.combinations(self.members, 2):
            match_seed = _new_seed(rng)
            m = play_match(self.members[a], self.members[b], rounds=self.league_rounds,
                           seed=match_seed, payoff=self.payoff, noise=self.noise,
                           record_rounds=self.record_rounds)
            points[a] += m.pa
            points[b] += m.pb
            self.matches.append({"A": a, "B": b, **m.to_row(), "seed": match_seed})
            if m.rounds is not None:
                self.round_rows.extend(
                    {"A": a, "B": b, "round": r, "a": ma, "b": mb, "flip_a": fa, "flip_b": fb}
                    for r, ma, mb, fa, fb in m.rounds)

        # Sorteo para el último criterio de desempate. Se hace DESPUÉS de los
        # partidos con el mismo generador de la liga: es reproducible y no altera
        # las semillas de los partidos. Se sortea en orden alfabético para que el
        # resultado no dependa del orden en que llegaron los miembros.
        names = sorted(self.members)
        lots = dict(zip(names, rng.random(len(names))))

        self.result = rank_league(self.matches, lots)
        self.clasification = [(row["name"], row["points"]) for row in self.result]
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
                 verbose: bool = False, payoff: Payoff = DEFAULT_PAYOFF,
                 noise: float = 0.0, record_rounds: bool = False):
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
        if not 0.0 <= noise <= 1.0:
            raise ValueError(f"noise debe estar entre 0 y 1 (es {noise})")
        # Reglas comunes a todas las ligas (se pasan tal cual a cada League)
        self.rules = dict(payoff=payoff, noise=noise, record_rounds=record_rounds)

        self.leagues: List[League] = []
        self.matches: List[dict] = []    # filas: season, league, A, B, cuentas del partido, seed
        self.standings: List[dict] = []  # filas: season, league, position, name, points
        self.rounds: List[dict] = []     # filas: season, league, A, B, round, a, b... (opcional)

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
        for r in league.round_rows:
            self.rounds.append({"season": season, "league": league.id, **r})

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
                **self.rules,
            ))

    # ---------------------------------------------------------------- fases
    def simulate_first_season(self, seed: int) -> None:
        """Temporada 0: liga única con todos y reparto por bloques según la clasificación."""
        all_league = League(number=0, members=self.members,
                            rounds=self.league_rounds, n_ascend_descend=0, **self.rules)
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


class RoundRobinTournament:
    """
    Formato "todos contra todos": una única liga con TODAS las estrategias, sin
    temporadas ni ascensos. Cada pareja juega un partido y gana quien más puntos suma.

    Es el formato de los torneos de Axelrod. Sirve de referencia para responder:
    ¿cambia el ganador según el formato? (en ligas, cada estrategia solo se mide con
    las de su nivel; aquí, con todas).

    Expone la misma interfaz que `League_Tournament` (`run(seed)`, `matches`,
    `standings`, `rounds`) para que el resto del código no tenga que distinguirlos.
    Convención: se guarda como temporada 0, liga 0 (la "liga de todos").
    """

    def __init__(self, members: Dict[str, Strategy], rounds: int, verbose: bool = False,
                 payoff: Payoff = DEFAULT_PAYOFF, noise: float = 0.0,
                 record_rounds: bool = False):
        if len(members) < 2:
            raise ValueError("Se necesitan al menos 2 estrategias.")
        if not 0.0 <= noise <= 1.0:
            raise ValueError(f"noise debe estar entre 0 y 1 (es {noise})")
        self.members = dict(members)
        self.league_rounds = rounds
        self.verbose = verbose
        self.rules = dict(payoff=payoff, noise=noise, record_rounds=record_rounds)
        self.league: Optional[League] = None
        self.matches: List[dict] = []
        self.standings: List[dict] = []
        self.rounds: List[dict] = []

    def run(self, seed: int) -> "RoundRobinTournament":
        """Juega la liga única. La semilla de la liga sale de la maestra (como en ligas)."""
        rng = np.random.default_rng(seed)
        self.league = League(number=0, members=self.members, rounds=self.league_rounds,
                             n_ascend_descend=0, **self.rules)
        self.league.play(season_seed=_new_seed(rng), season=0)
        for m in self.league.matches:
            self.matches.append({"season": 0, "league": 0, **m})
        for row in self.league.result:
            self.standings.append({"season": 0, "league": 0, **row})
        for r in self.league.round_rows:
            self.rounds.append({"season": 0, "league": 0, **r})
        if self.verbose:
            print("Todos contra todos — clasificación:")
            for row in self.league.result:
                print(f"  {row['position']:>2}. {row['name']} ({row['points']})")
        return self
