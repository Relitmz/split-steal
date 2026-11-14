"""
Registro de estrategias: decide QUIÉN participa en un torneo.

Un "roster" (plantilla) es un diccionario `{nombre: instancia_de_estrategia}`.
El simulador trabaja siempre con nombres (para tablas, ascensos y CSV) y usa el
diccionario para recuperar el objeto que juega.

Decisiones de diseño:
- Cada llamada a `Registry()` / `PruebaRegistry()` crea instancias NUEVAS. Las
  estrategias acumulan estadísticas mientras juegan, así que dos torneos no deben
  compartir objetos (si no, el segundo heredaría los contadores del primero).
- Los nombres deben ser únicos. Se comprueba sobre la LISTA antes de construir el
  dict, porque un dict descartaría el duplicado en silencio.
- El roster oficial tiene 30 estrategias para poder repartirlas en ligas iguales
  (5 ligas × 6 o 3 ligas × 10).
"""

from typing import Callable, Dict, List

from .strategies import (
    Alternator, AlwaysOpposite, AlwaysSplit, AlwaysSteal, BackstabAfter10,
    CautiousStart, ConditionalRandom, CopycatDelayed, DoubleStealStart,
    EveryThirdSplit, FirstStealThenSplit, ForgiveAfter3, ForgivingTitForTat,
    GreedyStart, GrimTrigger, MimicMajority, Mirror2Rounds, NoisyTitForTat,
    ProbTitForTat, RandomAfterLoss, RandomCycle, RandomP, RevengeMode,
    RevengeOneRound, SplitEvery4, SplitSplitSteal, SplitUntilBetrayedTwice,
    Strategy, TitForTat, TwoTitsForTat, UserStrategy, WinStayLoseShift,
)

Roster = Dict[str, Strategy]


def _full_roster() -> List[Strategy]:
    """Roster oficial: 30 estrategias."""
    return [
        AlwaysSplit(),
        AlwaysSteal(),
        TitForTat(),
        RandomP(0.5),
        GrimTrigger(),
        WinStayLoseShift(),
        TwoTitsForTat(),
        ForgivingTitForTat(0.1),
        Alternator(),
        MimicMajority(),
        AlwaysOpposite(),
        FirstStealThenSplit(),
        SplitEvery4(),
        RevengeOneRound(),
        DoubleStealStart(),
        ProbTitForTat(0.8),
        ForgiveAfter3(),
        RandomAfterLoss(),
        Mirror2Rounds(),
        BackstabAfter10(),
        RandomCycle(),
        CautiousStart(),
        CopycatDelayed(),
        SplitUntilBetrayedTwice(),
        RevengeMode(),
        NoisyTitForTat(0.05),
        GreedyStart(),
        EveryThirdSplit(),
        ConditionalRandom(),
        SplitSplitSteal(),
    ]


def _test_roster() -> List[Strategy]:
    """
    Roster de prueba: 25 estrategias (cabe en 5 ligas × 5). Respecto al oficial
    no incluye TwoTitsForTat, ForgivingTitForTat, ProbTitForTat, NoisyTitForTat,
    ConditionalRandom ni SplitSplitSteal, y añade `UserStrategy` para probar una
    estrategia propia.
    """
    return [
        AlwaysSplit(),
        AlwaysSteal(),
        TitForTat(),
        RandomP(0.5),
        GrimTrigger(),
        WinStayLoseShift(),
        Alternator(),
        MimicMajority(),
        AlwaysOpposite(),
        FirstStealThenSplit(),
        SplitEvery4(),
        RevengeOneRound(),
        DoubleStealStart(),
        ForgiveAfter3(),
        RandomAfterLoss(),
        Mirror2Rounds(),
        BackstabAfter10(),
        RandomCycle(),
        CautiousStart(),
        CopycatDelayed(),
        SplitUntilBetrayedTwice(),
        RevengeMode(),
        GreedyStart(),
        EveryThirdSplit(),
        UserStrategy(),
    ]


def _to_roster(strategies: List[Strategy]) -> Roster:
    """Convierte una lista de estrategias en `{nombre: estrategia}`, exigiendo nombres únicos."""
    names = [s.name for s in strategies]
    duplicates = sorted({n for n in names if names.count(n) > 1})
    if duplicates:
        raise ValueError(f"Estrategias con nombre repetido: {', '.join(duplicates)}")
    return {s.name: s for s in strategies}


def Registry() -> Roster:
    """Roster oficial (30 estrategias), con instancias nuevas en cada llamada."""
    return _to_roster(_full_roster())


def PruebaRegistry() -> Roster:
    """Roster de prueba (25 estrategias, incluye UserStrategy)."""
    return _to_roster(_test_roster())


# Nombre corto -> función que construye el roster (lo usa la CLI: --roster full|prueba)
ROSTERS: Dict[str, Callable[[], Roster]] = {
    "full": Registry,
    "prueba": PruebaRegistry,
}
