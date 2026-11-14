"""
Estrategias para el juego Split/Steal iterado.

Idea general
------------
En cada ronda dos jugadores eligen a la vez SPLIT (cooperar) o STEAL (traicionar).
Una *estrategia* es simplemente una regla que, mirando lo que ha pasado hasta ahora
en el partido, decide la siguiente jugada.

Todas las estrategias heredan de la clase abstracta `Strategy` y solo tienen que
implementar un método:

    act(history_self, history_opp, rng) -> SPLIT | STEAL

- `history_self`: lista con mis jugadas anteriores en ESTE partido (0 = SPLIT, 1 = STEAL).
- `history_opp`:  lista con las jugadas anteriores del rival en ESTE partido.
- `rng`: generador aleatorio de numpy (`np.random.Generator`) que proporciona el
  simulador. Toda la aleatoriedad DEBE salir de aquí (nunca de `random` o
  `np.random` globales); así, con la misma semilla, el torneo da siempre el mismo
  resultado (reproducibilidad).

Las historias se pasan "desde mi punto de vista": el simulador llama a
`a.act(hist_a, hist_b)` y `b.act(hist_b, hist_a)`, de modo que cada estrategia
siempre recibe primero su propia historia.

Estado interno
--------------
La mayoría de estrategias son "sin memoria propia": todo lo que necesitan está en
las historias. Algunas guardan un contador o patrón (`ForgiveAfter3`, `RevengeMode`,
`RandomCycle`). Como cada estrategia es UN objeto que juega muchos partidos, ese
estado debe borrarse al empezar cada partido: para eso existe `reset()`, que el
simulador llama antes de cada partido.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional

# Codificamos las acciones como enteros: así "cambiar de acción" es `1 - accion`
# y la matriz de pagos se indexa con tuplas (a, b).
SPLIT, STEAL = 0, 1


@dataclass
class LeagueStats:
    """Estadísticas de una estrategia durante UNA liga de UNA temporada."""

    season: Optional[int] = None
    league: Optional[int] = None
    rounds_played: int = 0
    times_split: int = 0
    times_steal: int = 0
    score_split: int = 0  # puntos obtenidos en rondas en las que jugó SPLIT
    score_steal: int = 0  # puntos obtenidos en rondas en las que jugó STEAL


class Strategy(ABC):
    """
    Clase base de todas las estrategias.

    Además de la decisión (`act`), lleva la contabilidad de cómo juega:
    - Totales acumulados en todo el torneo (`rounds_played`, `times_split`...).
    - Estadísticas por liga: el simulador llama a `league_started(season, league)`
      al empezar cada liga y a `league_finished()` al terminarla; cada liga jugada
      queda guardada como un `LeagueStats` en `season_info`.
    """

    def __init__(self, name: str):
        # El nombre identifica a la estrategia en registros, tablas y CSV: debe ser único.
        self.name = name

        # Totales de todo el torneo
        self.rounds_played = 0
        self.times_split = 0
        self.times_steal = 0
        self.score_split = 0
        self.score_steal = 0

        # Historial por liga: lista de LeagueStats (una entrada por liga jugada)
        self.season_info: List[LeagueStats] = []
        self.actual_league = LeagueStats()

    # ------------------------------------------------------------------ ciclo de vida
    def reset(self) -> None:
        """
        Borra el estado propio de un partido. El simulador lo llama ANTES de cada
        partido. Por defecto no hace nada; las estrategias con memoria interna lo
        sobrescriben. (No toca las estadísticas: esas sí deben acumularse.)
        """

    def league_started(self, season: int, league: int) -> None:
        """Llamar al iniciar una liga: abre un nuevo bloque de estadísticas."""
        self.actual_league = LeagueStats(season=season, league=league)

    def update_stats(self, action: int, points: int) -> None:
        """Llamar tras cada ronda con la acción jugada y los puntos obtenidos."""
        self.rounds_played += 1
        self.actual_league.rounds_played += 1
        if action == SPLIT:
            self.times_split += 1
            self.score_split += points
            self.actual_league.times_split += 1
            self.actual_league.score_split += points
        else:
            self.times_steal += 1
            self.score_steal += points
            self.actual_league.times_steal += 1
            self.actual_league.score_steal += points

    def league_finished(self) -> None:
        """Llamar al terminar una liga: guarda sus estadísticas y empieza un bloque vacío."""
        self.season_info.append(self.actual_league)
        self.actual_league = LeagueStats()

    # ------------------------------------------------------------------ decisión
    @abstractmethod
    def act(self, history_self: List[int], history_opp: List[int], rng) -> int:
        """Devuelve SPLIT o STEAL para la ronda actual."""
        ...

    def __repr__(self) -> str:
        return f"<{self.name}>"


# =============================================================================
# Estrategias básicas
# =============================================================================

class AlwaysSplit(Strategy):
    """Coopera siempre. Máximo beneficio mutuo… y totalmente explotable."""
    def __init__(self):
        super().__init__("AlwaysSplit")

    def act(self, h_self, h_opp, rng):
        return SPLIT


class AlwaysSteal(Strategy):
    """Traiciona siempre. Nunca pierde un partido individual, pero contra
    cooperadores condicionales acaba en el 1-1 de la traición mutua."""
    def __init__(self):
        super().__init__("AlwaysSteal")

    def act(self, h_self, h_opp, rng):
        return STEAL


class TitForTat(Strategy):
    """Ojo por ojo: empieza cooperando y después copia la última jugada del rival.
    Es la estrategia clásica ganadora de los torneos de Axelrod (1980)."""
    def __init__(self):
        super().__init__("TitForTat")

    def act(self, h_self, h_opp, rng):
        return SPLIT if not h_opp else h_opp[-1]


class RandomP(Strategy):
    """Juega SPLIT con probabilidad `p_split` (por defecto 0.5) en cada ronda."""
    def __init__(self, p_split: float = 0.5):
        super().__init__("RandomP")
        self.p_split = float(p_split)

    def act(self, h_self, h_opp, rng):
        return SPLIT if rng.random() < self.p_split else STEAL


class GrimTrigger(Strategy):
    """Coopera hasta que el rival traiciona UNA vez; desde entonces, STEAL para
    siempre (castigo permanente)."""
    def __init__(self):
        super().__init__("GrimTrigger")

    def act(self, h_self, h_opp, rng):
        return STEAL if STEAL in h_opp else SPLIT


class WinStayLoseShift(Strategy):
    """
    Pavlov: empieza con SPLIT. Si en la ronda anterior ambos hicieron lo mismo
    (S/S o St/St) repite su acción; si fueron distintas, cambia.
    """
    def __init__(self):
        super().__init__("WinStayLoseShift")

    def act(self, h_self, h_opp, rng):
        if not h_self:
            return SPLIT
        last_self, last_opp = h_self[-1], h_opp[-1]
        if last_self == last_opp:
            return last_self       # repetir
        return 1 - last_self       # cambiar


class TwoTitsForTat(Strategy):
    """Castigo doble: STEAL si el rival robó en cualquiera de las dos últimas
    rondas; en otro caso SPLIT."""
    def __init__(self):
        super().__init__("TwoTitsForTat")

    def act(self, h_self, h_opp, rng):
        return STEAL if STEAL in h_opp[-2:] else SPLIT


class ForgivingTitForTat(Strategy):
    """Tit-for-Tat generoso: imita al rival, pero si este robó, con probabilidad
    `eps` le perdona y coopera. Ayuda a salir de cadenas de venganza."""
    def __init__(self, eps: float = 0.1):
        super().__init__("ForgivingTitForTat")
        self.eps = float(eps)

    def act(self, h_self, h_opp, rng):
        if not h_opp:
            return SPLIT
        if h_opp[-1] == STEAL and rng.random() < self.eps:
            return SPLIT           # perdona
        return h_opp[-1]           # imita


class Alternator(Strategy):
    """Alterna SPLIT/STEAL cada ronda, empezando por `start` (SPLIT por defecto)."""
    def __init__(self, start: int = SPLIT):
        super().__init__("Alternator")
        self.start = SPLIT if start == SPLIT else STEAL

    def act(self, h_self, h_opp, rng):
        if not h_self:
            return self.start
        return 1 - h_self[-1]


# =============================================================================
# Variantes y estrategias "con personalidad"
# =============================================================================

class AlwaysOpposite(Strategy):
    """Empieza robando y después hace siempre lo contrario de lo que hizo el rival."""
    def __init__(self):
        super().__init__("AlwaysOpposite")

    def act(self, h_self, h_opp, rng):
        if not h_opp:
            return STEAL
        return 1 - h_opp[-1]


class FirstStealThenSplit(Strategy):
    """Roba en la primera ronda y coopera en todas las demás."""
    def __init__(self):
        super().__init__("FirstStealThenSplit")

    def act(self, h_self, h_opp, rng):
        return STEAL if not h_self else SPLIT


class SplitEvery4(Strategy):
    """SPLIT en las rondas 1, 5, 9, … (una de cada cuatro) y STEAL en el resto."""
    def __init__(self):
        super().__init__("SplitEvery4")

    def act(self, h_self, h_opp, rng):
        # len(h_self) = nº de rondas ya jugadas = índice (desde 0) de la ronda actual
        return SPLIT if len(h_self) % 4 == 0 else STEAL


class RevengeOneRound(Strategy):
    """Si el rival robó en la ronda anterior, roba; si no, coopera.
    (En la práctica se comporta igual que TitForTat.)"""
    def __init__(self):
        super().__init__("RevengeOneRound")

    def act(self, h_self, h_opp, rng):
        if h_opp and h_opp[-1] == STEAL:
            return STEAL
        return SPLIT


class DoubleStealStart(Strategy):
    """Roba las dos primeras rondas y después juega TitForTat."""
    def __init__(self):
        super().__init__("DoubleStealStart")

    def act(self, h_self, h_opp, rng):
        if len(h_self) < 2:
            return STEAL
        return h_opp[-1]


class ProbTitForTat(Strategy):
    """Con probabilidad `p` imita la última jugada del rival; con probabilidad
    1 - p coopera (SPLIT). Empieza cooperando."""
    def __init__(self, p: float = 0.8):
        super().__init__("ProbTitForTat")
        self.p = float(p)

    def act(self, h_self, h_opp, rng):
        if not h_opp or rng.random() > self.p:
            return SPLIT
        return h_opp[-1]


class ForgiveAfter3(Strategy):
    """Cada vez que el rival roba, responde con 3 rondas seguidas de STEAL
    (el contador se reinicia si vuelve a robar) y después perdona."""
    def __init__(self):
        super().__init__("ForgiveAfter3")
        self.punish = 0  # rondas de castigo pendientes (estado interno)

    def reset(self):
        self.punish = 0

    def act(self, h_self, h_opp, rng):
        if h_opp and h_opp[-1] == STEAL:
            self.punish = 3
        if self.punish > 0:
            self.punish -= 1
            return STEAL
        return SPLIT


class RandomAfterLoss(Strategy):
    """Coopera, salvo justo después de haber sido traicionado (yo SPLIT, rival
    STEAL): entonces elige al azar (50 %)."""
    def __init__(self):
        super().__init__("RandomAfterLoss")

    def act(self, h_self, h_opp, rng):
        if not h_self:
            return SPLIT
        if h_self[-1] == SPLIT and h_opp[-1] == STEAL:
            return SPLIT if rng.random() < 0.5 else STEAL
        return SPLIT


class Mirror2Rounds(Strategy):
    """Mira las dos últimas jugadas del rival: si cooperó en al menos una,
    coopera; solo roba si el rival robó en ambas."""
    def __init__(self):
        super().__init__("Mirror2Rounds")

    def act(self, h_self, h_opp, rng):
        if len(h_opp) < 2:
            return SPLIT
        return SPLIT if SPLIT in h_opp[-2:] else STEAL


class BackstabAfter10(Strategy):
    """Coopera las primeras 10 rondas para ganarse la confianza y después roba siempre."""
    def __init__(self):
        super().__init__("BackstabAfter10")

    def act(self, h_self, h_opp, rng):
        return SPLIT if len(h_self) < 10 else STEAL


class RandomCycle(Strategy):
    """Al empezar cada partido sortea un patrón de 3 jugadas y lo repite en bucle."""
    def __init__(self):
        super().__init__("RandomCycle")
        self.pattern = None  # patrón del partido actual (estado interno)

    def reset(self):
        # Sin esto, el patrón sorteado en el primer partido se usaría todo el torneo.
        self.pattern = None

    def act(self, h_self, h_opp, rng):
        if self.pattern is None:
            self.pattern = [SPLIT if rng.random() < 0.5 else STEAL for _ in range(3)]
        return self.pattern[len(h_self) % 3]


class CautiousStart(Strategy):
    """Coopera, pero si el rival robó en las dos primeras rondas, roba siempre."""
    def __init__(self):
        super().__init__("CautiousStart")

    def act(self, h_self, h_opp, rng):
        if len(h_opp) < 2:
            return SPLIT
        if h_opp[0] == STEAL and h_opp[1] == STEAL:
            return STEAL
        return SPLIT


class CopycatDelayed(Strategy):
    """Imita la jugada que hizo el rival hace dos rondas (TitForTat con retraso)."""
    def __init__(self):
        super().__init__("CopycatDelayed")

    def act(self, h_self, h_opp, rng):
        if len(h_opp) < 2:
            return SPLIT
        return h_opp[-2]


class SplitUntilBetrayedTwice(Strategy):
    """Coopera hasta que el rival ha robado dos veces (en total); luego roba siempre.
    Un GrimTrigger más tolerante."""
    def __init__(self):
        super().__init__("SplitUntilBetrayedTwice")

    def act(self, h_self, h_opp, rng):
        return STEAL if h_opp.count(STEAL) >= 2 else SPLIT


class RevengeMode(Strategy):
    """Si el rival roba dos rondas seguidas, entra en 'modo venganza': 3 rondas de STEAL."""
    def __init__(self):
        super().__init__("RevengeMode")
        self.revenge = 0  # rondas de venganza pendientes (estado interno)

    def reset(self):
        self.revenge = 0

    def act(self, h_self, h_opp, rng):
        if len(h_opp) >= 2 and h_opp[-1] == STEAL and h_opp[-2] == STEAL:
            self.revenge = 3
        if self.revenge > 0:
            self.revenge -= 1
            return STEAL
        return SPLIT


class NoisyTitForTat(Strategy):
    """TitForTat que, con probabilidad `noise`, se equivoca y juega lo contrario."""
    def __init__(self, noise: float = 0.05):
        super().__init__("NoisyTitForTat")
        self.noise = float(noise)

    def act(self, h_self, h_opp, rng):
        if not h_opp:
            return SPLIT
        intended = h_opp[-1]
        if rng.random() < self.noise:
            return 1 - intended
        return intended


class GreedyStart(Strategy):
    """Roba las 3 primeras rondas. Si el rival no robó en ninguna de ellas
    (no se defendió), coopera el resto; si robó alguna vez, roba siempre."""
    def __init__(self):
        super().__init__("GreedyStart")

    def act(self, h_self, h_opp, rng):
        if len(h_self) < 3:
            return STEAL
        return SPLIT if STEAL not in h_opp[:3] else STEAL


class EveryThirdSplit(Strategy):
    """SPLIT en las rondas 3, 6, 9, … y STEAL en el resto (patrón St, St, S)."""
    def __init__(self):
        super().__init__("EveryThirdSplit")

    def act(self, h_self, h_opp, rng):
        return SPLIT if (len(h_self) + 1) % 3 == 0 else STEAL


class ConditionalRandom(Strategy):
    """Si el rival cooperó en la última ronda, coopera; si robó, elige al azar (50 %)."""
    def __init__(self):
        super().__init__("ConditionalRandom")

    def act(self, h_self, h_opp, rng):
        if not h_opp:
            return SPLIT
        if h_opp[-1] == STEAL:
            return SPLIT if rng.random() < 0.5 else STEAL
        return SPLIT


class MimicMajority(Strategy):
    """Juega la acción que el rival ha usado más veces en el partido (empate: SPLIT)."""
    def __init__(self):
        super().__init__("MimicMajority")

    def act(self, h_self, h_opp, rng):
        if not h_opp:
            return SPLIT
        return SPLIT if h_opp.count(SPLIT) >= h_opp.count(STEAL) else STEAL


class SplitSplitSteal(Strategy):
    """Estrategia propuesta por Irene: patrón fijo S, S, St (roba en las rondas
    3, 6, 9, …). Es la complementaria de EveryThirdSplit."""
    def __init__(self):
        super().__init__("SplitSplitSteal")

    def act(self, h_self, h_opp, rng):
        return STEAL if (len(h_self) + 1) % 3 == 0 else SPLIT


class UserStrategy(Strategy):
    """
    Plantilla para que escribas tu propia estrategia y la enfrentes al resto.
    Edita `act` usando `h_self`, `h_opp` y `rng` (y `reset` si guardas estado).
    Ahora mismo coopera siempre, por eso no está en el roster oficial.
    """
    def __init__(self):
        super().__init__("UserStrategy")

    def act(self, h_self, h_opp, rng):
        return SPLIT
