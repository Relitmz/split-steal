import itertools, time
from abc import ABC, abstractmethod
from typing import List
SPLIT, STEAL = 0, 1

class LeagueStats:
    def __init__(self):
        self.league = None
        self.rounds_played = 0
        self.times_split = 0
        self.times_steal = 0
        self.score_split = 0
        self.score_steal = 0

class Strategy(ABC):
    def __init__(self, name):
        #  Atributo común a todas las estrategias
        self.name = name
        self.rounds_played = 0
        self.times_split = 0
        self.times_steal = 0
        self.score_split = 0
        self.score_steal = 0

        self.season_info = []
        self.actual_league = LeagueStats()

    def league_started(self): # Llamar al iniciar una liga, guardar info
        self.actual_league.league = LeagueStats()

    def update_stats(self, action, points): # Llamar tras cada ronda
        self.actual_league.rounds_played += 1
        self.rounds_played += 1
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
        
    def league_finished(self): # Llamar al finalizar una liga, guardar estadísticas, resetear
        self.season_info.append(self.actual_league)
        self.actual_league = LeagueStats()
    
    @abstractmethod # Método que debe implementar cada estrategia
    def act(self, history_self: List[int], history_opp: List[int], rng):
        ...

class AlwaysSplit(Strategy):
    def __init__(self):
        super().__init__("AlwaysSplit")

    def act(self, h_self, h_opp, rng): return SPLIT

class AlwaysSteal(Strategy):
    def __init__(self):
        super().__init__("AlwaysSteal")

    def act(self, h_self, h_opp, rng): return STEAL

class TitForTat(Strategy):
    def __init__(self):
        super().__init__("TitForTat")

    def act(self, h_self, h_opp, rng):
        return SPLIT if not h_opp else h_opp[-1]

# --- Estrategias nuevas ---

class RandomP(Strategy):
    """
    Juega SPLIT con probabilidad p_split (por defecto 0.5).
    """
    def __init__(self, p_split: float = 0.5):
        super().__init__("RandomP")
        self.p_split = float(p_split)

    def act(self, h_self, h_opp, rng):
        return SPLIT if rng.random() < self.p_split else STEAL

class GrimTrigger(Strategy):
    """
    Empieza cooperando (SPLIT). Si el rival roba (STEAL) alguna vez en la historia,
    a partir de entonces siempre STEAL (castigo permanente).
    """
    def __init__(self):
        super().__init__("GrimTrigger")

    def act(self, h_self, h_opp, rng):
        return STEAL if any(a == STEAL for a in h_opp) else SPLIT

class WinStayLoseShift(Strategy):
    """
    Pavlov: empieza en SPLIT. Si la ronda anterior “fue bien”, repite acción;
    si no, cambia. Implementación sin payoffs:
      - Si en la ronda anterior ambos hicieron lo mismo (S/S o St/St): repetir.
      - Si fueron diferentes: cambiar.
    """
    def __init__(self):
        super().__init__("WinStayLoseShift")

    def act(self, h_self, h_opp, rng):
        if not h_self:
            return SPLIT
        last_self, last_opp = h_self[-1], h_opp[-1]
        if last_self == last_opp:
            return last_self  # repetir
        return 1 - last_self  # cambiar

class TwoTitsForTat(Strategy):
    """
    Castigo “doble”: responde con STEAL si el rival ha hecho STEAL en
    cualquiera de las dos últimas rondas; en otro caso SPLIT.
    (Equivale a castigar un STEAL con dos rondas seguidas de STEAL.)
    """
    def __init__(self):
        super().__init__("TwoTitsForTat")

    def act(self, h_self, h_opp, rng):
        if not h_opp:
            return SPLIT
        if h_opp[-1] == STEAL:
            return STEAL
        if len(h_opp) >= 2 and h_opp[-2] == STEAL:
            return STEAL
        return SPLIT

class ForgivingTitForTat(Strategy):
    """
    Tit-for-Tat “generoso”: normalmente imita la última acción del rival,
    pero con probabilidad eps perdona (coopera) aunque el rival haya robado.
    """
    def __init__(self, eps: float = 0.1):
        super().__init__("ForgivingTitForTat")
        self.eps = float(eps)

    def act(self, h_self, h_opp, rng):
        if not h_opp:
            return SPLIT
        if h_opp[-1] == STEAL and rng.random() < self.eps:
            return SPLIT  # perdona
        return h_opp[-1]  # imita

class Alternator(Strategy):
    """
    Alterna SPLIT/STEAL cada ronda. Por defecto empieza con SPLIT.
    """
    def __init__(self, start=SPLIT):
        super().__init__("Alternator")
        self.start = SPLIT if start == SPLIT else STEAL

    def act(self, h_self, h_opp, rng):
        if not h_self:
            return self.start
        return 1 - h_self[-1]  # alterna respecto a tu última acción

# --- Estrategias nuevas ---

class AlwaysOpposite(Strategy):
    """Hace siempre lo contrario de la última jugada del oponente."""
    def __init__(self):
        super().__init__("AlwaysOpposite")

    def act(self, h_self, h_opp, rng):
        if not h_opp:
            return STEAL
        return 1 - h_opp[-1]

class FirstStealThenSplit(Strategy):
    """Empieza robando, luego coopera siempre."""
    def __init__(self):
        super().__init__("FirstStealThenSplit")

    def act(self, h_self, h_opp, rng):
        return STEAL if not h_self else SPLIT

class SplitEvery4(Strategy):
    """Juega SPLIT cada 4 rondas (1,5,9,...) y STEAL el resto."""
    def __init__(self):
        super().__init__("SplitEvery4")

    def act(self, h_self, h_opp, rng):
        return SPLIT if len(h_self) % 4 == 0 else STEAL

class RevengeOneRound(Strategy):
    """Castiga un STEAL del rival con un STEAL solo en la siguiente ronda."""
    def __init__(self):
        super().__init__("RevengeOneRound")

    def act(self, h_self, h_opp, rng):
        if len(h_opp) >= 1 and h_opp[-1] == STEAL:
            return STEAL
        return SPLIT

class DoubleStealStart(Strategy):
    """Roba las dos primeras rondas y luego juega TitForTat."""
    def __init__(self):
        super().__init__("DoubleStealStart")

    def act(self, h_self, h_opp, rng):
        if len(h_self) < 2:
            return STEAL
        return h_opp[-1] if h_opp else SPLIT

class ProbTitForTat(Strategy):
    """Imita la última acción del rival con probabilidad p."""
    def __init__(self, p: float = 0.8):
        super().__init__("ProbTitForTat")
        self.p = p

    def act(self, h_self, h_opp, rng):
        if not h_opp or rng.random() > self.p:
            return SPLIT
        return h_opp[-1]

class ForgiveAfter3(Strategy):
    """Castiga hasta 3 veces seguidas tras un STEAL, luego perdona."""
    def __init__(self):
        super().__init__("ForgiveAfter3")
        self.punish = 0

    def act(self, h_self, h_opp, rng):
        if h_opp and h_opp[-1] == STEAL:
            self.punish = 3
        if self.punish > 0:
            self.punish -= 1
            return STEAL
        return SPLIT

class RandomAfterLoss(Strategy):
    """Si perdió la última ronda (hizo SPLIT y el rival STEAL), elige al azar la siguiente."""
    def __init__(self):
        super().__init__("RandomAfterLoss")

    def act(self, h_self, h_opp, rng):
        if not h_self:
            return SPLIT
        if h_self[-1] == SPLIT and h_opp[-1] == STEAL:
            return SPLIT if rng.random() < 0.5 else STEAL
        return SPLIT

class Mirror2Rounds(Strategy):
    """Imita la acción más común del rival en las dos últimas rondas."""
    def __init__(self):
        super().__init__("Mirror2Rounds")

    def act(self, h_self, h_opp, rng):
        if len(h_opp) < 2:
            return SPLIT
        return SPLIT if h_opp[-2:].count(SPLIT) >= 1 else STEAL

class BackstabAfter10(Strategy):
    """Coopera las primeras 10 rondas, luego roba siempre."""
    def __init__(self):
        super().__init__("BackstabAfter10")

    def act(self, h_self, h_opp, rng):
        return SPLIT if len(h_self) < 10 else STEAL

class RandomCycle(Strategy):
    """Ciclo aleatorio de 3 rondas decidido al inicio."""
    def __init__(self):
        super().__init__("RandomCycle")
        self.pattern = None

    def act(self, h_self, h_opp, rng):
        if self.pattern is None:
            self.pattern = [SPLIT if rng.random() < 0.5 else STEAL for _ in range(3)]
        return self.pattern[len(h_self) % 3]

class CautiousStart(Strategy):
    """Empieza cooperando, pero roba si el rival roba en las dos primeras."""
    def __init__(self):
        super().__init__("CautiousStart")

    def act(self, h_self, h_opp, rng):
        if len(h_opp) < 2:
            return SPLIT
        if h_opp[0] == STEAL and h_opp[1] == STEAL:
            return STEAL
        return SPLIT

class CopycatDelayed(Strategy):
    """Imita la acción que el rival hizo hace dos rondas (retraso de 2)."""
    def __init__(self):
        super().__init__("CopycatDelayed")

    def act(self, h_self, h_opp, rng):
        if len(h_opp) < 2:
            return SPLIT
        return h_opp[-2]

class SplitUntilBetrayedTwice(Strategy):
    """Coopera hasta que el rival roba dos veces; luego roba siempre."""
    def __init__(self):
        super().__init__("SplitUntilBetrayedTwice")

    def act(self, h_self, h_opp, rng):
        if h_opp.count(STEAL) >= 2:
            return STEAL
        return SPLIT

class RevengeMode(Strategy):
    """Si el rival roba dos veces seguidas, entra en modo STEAL 3 rondas."""
    def __init__(self):
        super().__init__("RevengeMode")
        self.revenge = 0

    def act(self, h_self, h_opp, rng):
        if len(h_opp) >= 2 and h_opp[-1] == STEAL and h_opp[-2] == STEAL:
            self.revenge = 3
        if self.revenge > 0:
            self.revenge -= 1
            return STEAL
        return SPLIT

class NoisyTitForTat(Strategy):
    """Tit-for-Tat con ruido: a veces se equivoca."""
    def __init__(self, noise: float = 0.05):
        super().__init__("NoisyTitForTat")
        self.noise = noise

    def act(self, h_self, h_opp, rng):
        if not h_opp:
            return SPLIT
        intended = h_opp[-1]
        if rng.random() < self.noise:
            return 1 - intended
        return intended

class GreedyStart(Strategy):
    """Empieza robando las primeras 3 rondas, luego coopera si el rival no se vengó."""
    def __init__(self):
        super().__init__("GreedyStart")

    def act(self, h_self, h_opp, rng):
        if len(h_self) < 3:
            return STEAL
        if STEAL not in h_opp[:3]:
            return SPLIT
        return STEAL

class EveryThirdSplit(Strategy):
    """Hace SPLIT en las rondas 3,6,9,... y STEAL el resto."""
    def __init__(self):
        super().__init__("EveryThirdSplit")

    def act(self, h_self, h_opp, rng):
        return SPLIT if (len(h_self) + 1) % 3 == 0 else STEAL

class ConditionalRandom(Strategy):
    """Si el rival robó la última vez, juega al azar; si cooperó, coopera."""
    def __init__(self):
        super().__init__("ConditionalRandom")

    def act(self, h_self, h_opp, rng):
        if not h_opp:
            return SPLIT
        if h_opp[-1] == STEAL:
            return SPLIT if rng.random() < 0.5 else STEAL
        return SPLIT

class MimicMajority(Strategy):
    """Juega la acción más frecuente del rival en todo el historial."""
    def __init__(self):
        super().__init__("MimicMajority")

    def act(self, h_self, h_opp, rng):
        if not h_opp:
            return SPLIT
        return SPLIT if h_opp.count(SPLIT) >= h_opp.count(STEAL) else STEAL
    """Juega la acción más frecuente del rival en todo el historial."""
    def act(self, h_self, h_opp, rng):
        if not h_opp:
            return SPLIT
        return SPLIT if h_opp.count(SPLIT) >= h_opp.count(STEAL) else STEAL
    
class SplitSplitSteal(Strategy):
    """Estrategia personalizada de Irene: empieza cooperando, pero roba si el rival roba más del 50% de las veces."""
    def __init__(self):
        super().__init__("SplitSplitSteal")

    def act(self, h_self, h_opp, rng):
        if (len(h_self)+1)%3 == 0:
            return STEAL
        else:
            return SPLIT
        
class UserStrategy(Strategy):
    """Here you must write a strategy that takes inputs to decide whether to SPLIT or STEAL. This allows you to play against the other strategies in the tournament."""
    def __init__(self):
        super().__init__("UserStrategy")

    def act(self, h_self, h_opp, rng):
        return SPLIT