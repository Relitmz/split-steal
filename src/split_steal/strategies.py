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

Parámetros y nombres
--------------------
Algunas estrategias tienen parámetros (p. ej. la probabilidad de perdonar de
`ForgivingTitForTat`). Regla: cada argumento de `__init__` se guarda en un atributo
con el MISMO nombre (`self.p = p`). Así la clase base puede leerlos (`params`) y
construir el nombre automáticamente:

    ForgivingTitForTat()       -> nombre "ForgivingTitForTat"         (valores por defecto)
    ForgivingTitForTat(p=0.2)  -> nombre "ForgivingTitForTat(p=0.2)"  (parámetro cambiado)

Gracias a eso dos versiones de la misma estrategia pueden jugar en el mismo torneo
sin que sus nombres choquen.

Etiquetas
---------
Cada estrategia declara `tags`: rasgos de su "personalidad" (ver `TAGS`). Sirven
para describirlas, agruparlas en presets y filtrar en los análisis.
"""

import inspect
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, FrozenSet, List, Optional

# Codificamos las acciones como enteros: así "cambiar de acción" es `1 - accion`
# y la matriz de pagos se indexa con tuplas (a, b).
SPLIT, STEAL = 0, 1

# Vocabulario de etiquetas. Una estrategia puede tener varias.
TAGS: Dict[str, str] = {
    "amable":      "Nunca traiciona primero: contra alguien que siempre coopera, coopera siempre.",
    "traicionera": "Puede traicionar sin que la provoquen (ataca, tantea o explota).",
    "vengativa":   "Responde a una traición con una traición (castiga).",
    "rencorosa":   "Su castigo puede ser permanente: deja de cooperar para siempre.",
    "perdona":     "Tras castigar, puede volver a cooperar con quien la traicionó.",
    "aleatoria":   "Usa el azar para decidir.",
    "fija":        "Sigue un plan fijado de antemano; no reacciona a lo que hace el rival.",
    "con_memoria": "Guarda estado interno durante el partido (además de las historias).",
    "adaptativa":  "Ajusta su forma de jugar según lo que va aprendiendo del rival.",
    "clasica":     "Estrategia conocida de la literatura (torneos de Axelrod y posteriores).",
}


def _format_value(value) -> str:
    """Formato corto para nombres: 0.2 -> '0.2', 1/3 -> '0.333333'."""
    return f"{value:g}" if isinstance(value, float) else str(value)


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

    # Rasgos de la estrategia (claves de TAGS). Cada subclase define los suyos.
    tags: FrozenSet[str] = frozenset()

    def __init__(self, name: Optional[str] = None):
        # El nombre identifica a la estrategia en registros, tablas y CSV: debe ser único.
        # Si no se da, se genera a partir de la clase y sus parámetros (ver `name`).
        self._name = name

        # Totales de todo el torneo
        self.rounds_played = 0
        self.times_split = 0
        self.times_steal = 0
        self.score_split = 0
        self.score_steal = 0

        # Historial por liga: lista de LeagueStats (una entrada por liga jugada)
        self.season_info: List[LeagueStats] = []
        self.actual_league = LeagueStats()

    # ------------------------------------------------------------------ identidad
    @classmethod
    def default_params(cls) -> Dict[str, object]:
        """Parámetros de `__init__` con sus valores por defecto: {'p': 0.1, ...}."""
        sig = inspect.signature(cls.__init__)
        return {n: p.default for n, p in sig.parameters.items()
                if n != "self" and p.default is not inspect.Parameter.empty}

    @property
    def params(self) -> Dict[str, object]:
        """Valores actuales de los parámetros (leídos de los atributos homónimos)."""
        return {n: getattr(self, n) for n in self.default_params()}

    @property
    def name(self) -> str:
        """Nombre de la clase y, si algún parámetro no es el de por defecto, entre paréntesis."""
        if self._name is None:
            defaults = self.default_params()
            changed = {k: v for k, v in self.params.items() if v != defaults[k]}
            suffix = ", ".join(f"{k}={_format_value(v)}" for k, v in changed.items())
            self._name = type(self).__name__ + (f"({suffix})" if suffix else "")
        return self._name

    @classmethod
    def description(cls) -> str:
        """Descripción en una línea (el primer párrafo del docstring)."""
        doc = inspect.getdoc(cls) or ""
        return " ".join(doc.split("\n\n")[0].split())

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
    tags = frozenset({"amable", "fija", "clasica"})

    def __init__(self):
        super().__init__()

    def act(self, h_self, h_opp, rng):
        return SPLIT


class AlwaysSteal(Strategy):
    """Traiciona siempre. Nunca pierde un partido individual, pero contra
    cooperadores condicionales acaba en el 1-1 de la traición mutua."""
    tags = frozenset({"traicionera", "fija", "clasica"})

    def __init__(self):
        super().__init__()

    def act(self, h_self, h_opp, rng):
        return STEAL


class TitForTat(Strategy):
    """Ojo por ojo: empieza cooperando y después copia la última jugada del rival.
    Es la estrategia clásica ganadora de los torneos de Axelrod (1980)."""
    tags = frozenset({"amable", "vengativa", "perdona", "clasica"})

    def __init__(self):
        super().__init__()

    def act(self, h_self, h_opp, rng):
        return SPLIT if not h_opp else h_opp[-1]


class RandomP(Strategy):
    """Juega SPLIT con probabilidad `p_split` (por defecto 0.5) en cada ronda."""
    tags = frozenset({"aleatoria", "fija", "clasica"})

    def __init__(self, p_split: float = 0.5):
        super().__init__()
        self.p_split = float(p_split)

    def act(self, h_self, h_opp, rng):
        return SPLIT if rng.random() < self.p_split else STEAL


class GrimTrigger(Strategy):
    """Coopera hasta que el rival traiciona UNA vez; desde entonces, STEAL para
    siempre (castigo permanente)."""
    tags = frozenset({"amable", "vengativa", "rencorosa", "clasica"})

    def __init__(self):
        super().__init__()

    def act(self, h_self, h_opp, rng):
        return STEAL if STEAL in h_opp else SPLIT


class WinStayLoseShift(Strategy):
    """
    Pavlov: empieza con SPLIT. Si en la ronda anterior ambos hicieron lo mismo
    (S/S o St/St) repite su acción; si fueron distintas, cambia.
    """
    tags = frozenset({"amable", "vengativa", "perdona", "clasica"})

    def __init__(self):
        super().__init__()

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
    tags = frozenset({"amable", "vengativa", "perdona", "clasica"})

    def __init__(self):
        super().__init__()

    def act(self, h_self, h_opp, rng):
        return STEAL if STEAL in h_opp[-2:] else SPLIT


class ForgivingTitForTat(Strategy):
    """Tit-for-Tat que perdona: imita al rival, pero si este robó, con probabilidad
    `p` (10 % por defecto) le perdona y coopera. Ayuda a salir de cadenas de venganza.

    `p` es el parámetro pensado para experimentar: con p = 0 es TitForTat puro y
    con p = 1 es AlwaysSplit. ¿Cuál es el perdón óptimo? (ver GenerousTitForTat).
    """
    tags = frozenset({"amable", "vengativa", "perdona", "aleatoria"})

    def __init__(self, p: float = 0.1):
        super().__init__()
        self.p = float(p)

    def act(self, h_self, h_opp, rng):
        if not h_opp:
            return SPLIT
        if h_opp[-1] == STEAL and rng.random() < self.p:
            return SPLIT           # perdona
        return h_opp[-1]           # imita


class GenerousTitForTat(ForgivingTitForTat):
    """Generous Tit-for-Tat (Nowak y Sigmund, 1992): igual que ForgivingTitForTat
    pero perdona con p = 1/3.

    Ese 1/3 sale de la teoría: el perdón máximo que no deja que un traidor se
    aproveche es min(1 - (T-R)/(R-S), (R-P)/(T-P)) = min(1 - 2/3, 2/4) = 1/3 con
    nuestros pagos (T=5, R=3, P=1, S=0). Hereda la lógica; solo cambia el valor por defecto.
    """
    tags = frozenset({"amable", "vengativa", "perdona", "aleatoria", "clasica"})

    def __init__(self, p: float = 1 / 3):
        super().__init__(p)


class Alternator(Strategy):
    """Alterna SPLIT/STEAL cada ronda, empezando por `start` (SPLIT por defecto)."""
    tags = frozenset({"traicionera", "fija", "clasica"})

    def __init__(self, start: int = SPLIT):
        super().__init__()
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
    tags = frozenset({"traicionera"})

    def __init__(self):
        super().__init__()

    def act(self, h_self, h_opp, rng):
        if not h_opp:
            return STEAL
        return 1 - h_opp[-1]


class FirstStealThenSplit(Strategy):
    """Roba en la primera ronda y coopera en todas las demás."""
    tags = frozenset({"traicionera", "fija"})

    def __init__(self):
        super().__init__()

    def act(self, h_self, h_opp, rng):
        return STEAL if not h_self else SPLIT


class SplitEvery4(Strategy):
    """SPLIT en las rondas 1, 5, 9, … (una de cada cuatro) y STEAL en el resto."""
    tags = frozenset({"traicionera", "fija"})

    def __init__(self):
        super().__init__()

    def act(self, h_self, h_opp, rng):
        # len(h_self) = nº de rondas ya jugadas = índice (desde 0) de la ronda actual
        return SPLIT if len(h_self) % 4 == 0 else STEAL


class DoubleStealStart(Strategy):
    """Roba las dos primeras rondas y después juega TitForTat."""
    tags = frozenset({"traicionera", "vengativa", "perdona"})

    def __init__(self):
        super().__init__()

    def act(self, h_self, h_opp, rng):
        if len(h_self) < 2:
            return STEAL
        return h_opp[-1]


class ProbTitForTat(Strategy):
    """Con probabilidad `p` imita la última jugada del rival; con probabilidad
    1 - p coopera (SPLIT). Empieza cooperando."""
    tags = frozenset({"amable", "vengativa", "perdona", "aleatoria"})

    def __init__(self, p: float = 0.8):
        super().__init__()
        self.p = float(p)

    def act(self, h_self, h_opp, rng):
        if not h_opp or rng.random() > self.p:
            return SPLIT
        return h_opp[-1]


class ForgiveAfter3(Strategy):
    """Cada vez que el rival roba, responde con 3 rondas seguidas de STEAL
    (el contador se reinicia si vuelve a robar) y después perdona."""
    tags = frozenset({"amable", "vengativa", "perdona", "con_memoria"})

    def __init__(self):
        super().__init__()
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
    tags = frozenset({"amable", "perdona", "aleatoria"})

    def __init__(self):
        super().__init__()

    def act(self, h_self, h_opp, rng):
        if not h_self:
            return SPLIT
        if h_self[-1] == SPLIT and h_opp[-1] == STEAL:
            return SPLIT if rng.random() < 0.5 else STEAL
        return SPLIT


class Mirror2Rounds(Strategy):
    """Mira las dos últimas jugadas del rival: si cooperó en al menos una,
    coopera; solo roba si el rival robó en ambas.

    Es la clásica *Tit for Two Tats* de Axelrod: tolera una traición aislada y solo
    castiga dos seguidas. (No confundir con TwoTitsForTat, que castiga el doble.)
    """
    tags = frozenset({"amable", "vengativa", "perdona", "clasica"})

    def __init__(self):
        super().__init__()

    def act(self, h_self, h_opp, rng):
        if len(h_opp) < 2:
            return SPLIT
        return SPLIT if SPLIT in h_opp[-2:] else STEAL


class BackstabAfter10(Strategy):
    """Coopera las primeras 10 rondas para ganarse la confianza y después roba siempre."""
    tags = frozenset({"traicionera", "fija"})

    def __init__(self):
        super().__init__()

    def act(self, h_self, h_opp, rng):
        return SPLIT if len(h_self) < 10 else STEAL


class RandomCycle(Strategy):
    """Al empezar cada partido sortea un patrón de 3 jugadas y lo repite en bucle."""
    tags = frozenset({"aleatoria", "fija", "con_memoria"})

    def __init__(self):
        super().__init__()
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
    tags = frozenset({"amable", "vengativa", "rencorosa"})

    def __init__(self):
        super().__init__()

    def act(self, h_self, h_opp, rng):
        if len(h_opp) < 2:
            return SPLIT
        if h_opp[0] == STEAL and h_opp[1] == STEAL:
            return STEAL
        return SPLIT


class CopycatDelayed(Strategy):
    """Imita la jugada que hizo el rival hace dos rondas (TitForTat con retraso)."""
    tags = frozenset({"amable", "vengativa", "perdona"})

    def __init__(self):
        super().__init__()

    def act(self, h_self, h_opp, rng):
        if len(h_opp) < 2:
            return SPLIT
        return h_opp[-2]


class SplitUntilBetrayedTwice(Strategy):
    """Coopera hasta que el rival ha robado dos veces (en total); luego roba siempre.
    Un GrimTrigger más tolerante."""
    tags = frozenset({"amable", "vengativa", "rencorosa"})

    def __init__(self):
        super().__init__()

    def act(self, h_self, h_opp, rng):
        return STEAL if h_opp.count(STEAL) >= 2 else SPLIT


class RevengeMode(Strategy):
    """Si el rival roba dos rondas seguidas, entra en 'modo venganza': 3 rondas de STEAL."""
    tags = frozenset({"amable", "vengativa", "perdona", "con_memoria"})

    def __init__(self):
        super().__init__()
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
    tags = frozenset({"vengativa", "perdona", "aleatoria"})

    def __init__(self, noise: float = 0.05):
        super().__init__()
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
    tags = frozenset({"traicionera", "vengativa", "rencorosa"})

    def __init__(self):
        super().__init__()

    def act(self, h_self, h_opp, rng):
        if len(h_self) < 3:
            return STEAL
        return SPLIT if STEAL not in h_opp[:3] else STEAL


class EveryThirdSplit(Strategy):
    """SPLIT en las rondas 3, 6, 9, … y STEAL en el resto (patrón St, St, S)."""
    tags = frozenset({"traicionera", "fija"})

    def __init__(self):
        super().__init__()

    def act(self, h_self, h_opp, rng):
        return SPLIT if (len(h_self) + 1) % 3 == 0 else STEAL


class ConditionalRandom(Strategy):
    """Si el rival cooperó en la última ronda, coopera; si robó, elige al azar (50 %)."""
    tags = frozenset({"amable", "perdona", "aleatoria"})

    def __init__(self):
        super().__init__()

    def act(self, h_self, h_opp, rng):
        if not h_opp:
            return SPLIT
        if h_opp[-1] == STEAL:
            return SPLIT if rng.random() < 0.5 else STEAL
        return SPLIT


class MimicMajority(Strategy):
    """Juega la acción que el rival ha usado más veces en el partido (empate: SPLIT)."""
    tags = frozenset({"amable", "vengativa", "perdona", "clasica"})

    def __init__(self):
        super().__init__()

    def act(self, h_self, h_opp, rng):
        if not h_opp:
            return SPLIT
        return SPLIT if h_opp.count(SPLIT) >= h_opp.count(STEAL) else STEAL


class SplitSplitSteal(Strategy):
    """Estrategia propuesta por Irene: patrón fijo S, S, St (roba en las rondas
    3, 6, 9, …). Es la complementaria de EveryThirdSplit."""
    tags = frozenset({"traicionera", "fija"})

    def __init__(self):
        super().__init__()

    def act(self, h_self, h_opp, rng):
        return STEAL if (len(h_self) + 1) % 3 == 0 else SPLIT


# =============================================================================
# Estrategias clásicas de la literatura
# =============================================================================

class SuspiciousTitForTat(Strategy):
    """TitForTat desconfiado: empieza robando y después copia la última jugada del rival.

    Contra TitForTat cae en una alternancia eterna de venganzas (St/S, S/St, ...):
    muestra lo caro que sale un mal primer paso.
    """
    tags = frozenset({"traicionera", "vengativa", "perdona", "clasica"})

    def __init__(self):
        super().__init__()

    def act(self, h_self, h_opp, rng):
        return STEAL if not h_opp else h_opp[-1]


class Gradual(Strategy):
    """Castigo proporcional (Beaufils et al., 1996): coopera; cuando el rival roba
    por n-ésima vez en el partido, responde con n rondas de STEAL y después ofrece
    la paz con 2 rondas de SPLIT.

    Cuanto más reincide el rival, más largo es el castigo, pero siempre deja la
    puerta abierta a reconciliarse. Durante el castigo y la "paz" no mira al rival.
    """
    tags = frozenset({"amable", "vengativa", "perdona", "con_memoria", "clasica"})

    def __init__(self):
        super().__init__()
        self.punish_left = 0   # rondas de castigo pendientes
        self.calm_left = 0     # rondas de "paz" pendientes tras el castigo

    def reset(self):
        self.punish_left = 0
        self.calm_left = 0

    def _punish(self):
        """Juega una ronda de castigo; al terminarlo, programa las 2 de paz."""
        self.punish_left -= 1
        if self.punish_left == 0:
            self.calm_left = 2
        return STEAL

    def act(self, h_self, h_opp, rng):
        if self.punish_left > 0:
            return self._punish()
        if self.calm_left > 0:
            self.calm_left -= 1
            return SPLIT
        if h_opp and h_opp[-1] == STEAL:
            # n-ésima traición -> n rondas de castigo (contando esta)
            self.punish_left = h_opp.count(STEAL)
            return self._punish()
        return SPLIT


class Prober(Strategy):
    """Tanteadora: abre con St, S, S. Si el rival cooperó en las rondas 2 y 3 (no
    respondió a su robo), lo considera un ingenuo y roba siempre; si respondió,
    juega TitForTat.

    Explota a los cooperadores incondicionales sin enfadar del todo a los vengativos.
    """
    tags = frozenset({"traicionera", "vengativa", "adaptativa", "clasica"})

    OPENING = (STEAL, SPLIT, SPLIT)

    def __init__(self):
        super().__init__()

    def act(self, h_self, h_opp, rng):
        turn = len(h_self)
        if turn < len(self.OPENING):
            return self.OPENING[turn]
        if h_opp[1] == SPLIT and h_opp[2] == SPLIT:
            return STEAL           # no se defendió: explotarlo
        return h_opp[-1]           # se defendió: TitForTat


class Joss(Strategy):
    """TitForTat sigiloso (Joss, primer torneo de Axelrod): copia al rival, pero
    cuando tocaría cooperar, con probabilidad `p` (10 %) roba por sorpresa.

    Parece fiable, pero sus traiciones ocasionales desencadenan espirales de
    venganza contra los vengativos.
    """
    tags = frozenset({"traicionera", "vengativa", "perdona", "aleatoria", "clasica"})

    def __init__(self, p: float = 0.1):
        super().__init__()
        self.p = float(p)

    def act(self, h_self, h_opp, rng):
        intended = SPLIT if not h_opp else h_opp[-1]
        if intended == SPLIT and rng.random() < self.p:
            return STEAL
        return intended


class Adaptive(Strategy):
    """Aprende por prueba y error (Tzafestas, 2000): juega 6 rondas SPLIT y 5 STEAL
    para probar ambas acciones, y después elige siempre la que más puntos medios por
    ronda le ha dado hasta ahora en el partido.

    Usa los puntos REALES que recibe (no supone ninguna matriz de pagos), así que
    sigue funcionando si se cambian los pagos o hay ruido.
    """
    tags = frozenset({"traicionera", "adaptativa", "con_memoria", "clasica"})

    OPENING = (SPLIT,) * 6 + (STEAL,) * 5

    def __init__(self):
        super().__init__()
        self._reset_scores()

    def _reset_scores(self):
        # puntos acumulados y veces jugadas por acción en el partido actual
        self.match_score = {SPLIT: 0, STEAL: 0}
        self.match_count = {SPLIT: 0, STEAL: 0}

    def reset(self):
        self._reset_scores()

    def update_stats(self, action: int, points: int) -> None:
        super().update_stats(action, points)   # mantener la contabilidad general
        self.match_score[action] += points
        self.match_count[action] += 1

    def act(self, h_self, h_opp, rng):
        turn = len(h_self)
        if turn < len(self.OPENING):
            return self.OPENING[turn]
        avg = {a: self.match_score[a] / self.match_count[a] for a in (SPLIT, STEAL)}
        return SPLIT if avg[SPLIT] >= avg[STEAL] else STEAL


class Extortioner(Strategy):
    """Extorsionadora "Zero-Determinant" (Press y Dyson, 2012): decide al azar con
    una probabilidad de cooperar que depende de lo que pasó en la ronda anterior:

        ambos SPLIT -> 8/9   yo SPLIT, rival STEAL -> 1/2
        yo STEAL, rival SPLIT -> 1/3   ambos STEAL -> 0

    Con pagos 3/0/5/1 estas probabilidades fuerzan matemáticamente que sus puntos
    por encima del castigo mutuo (1) sean el DOBLE que los del rival: nunca pierde
    un partido... pero suele ganarlos por poco y con pocos puntos. Empieza cooperando.
    """
    tags = frozenset({"traicionera", "vengativa", "perdona", "aleatoria", "clasica"})

    # (mi última jugada, la del rival) -> probabilidad de SPLIT
    P_SPLIT = {(SPLIT, SPLIT): 8 / 9, (SPLIT, STEAL): 1 / 2,
               (STEAL, SPLIT): 1 / 3, (STEAL, STEAL): 0.0}

    def __init__(self):
        super().__init__()

    def act(self, h_self, h_opp, rng):
        if not h_self:
            return SPLIT
        p = self.P_SPLIT[(h_self[-1], h_opp[-1])]
        return SPLIT if rng.random() < p else STEAL


# =============================================================================
# Plantilla para el usuario
# =============================================================================

class UserStrategy(Strategy):
    """
    Plantilla para que escribas tu propia estrategia y la enfrentes al resto.
    Edita `act` usando `h_self`, `h_opp` y `rng` (y `reset` si guardas estado).
    Ahora mismo coopera siempre, por eso no está en el roster oficial.
    """
    tags = frozenset({"amable", "fija"})

    def __init__(self):
        super().__init__()

    def act(self, h_self, h_opp, rng):
        return SPLIT
