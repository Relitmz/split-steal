from abc import ABC, abstractmethod
from typing import List
from strategies import *


strategy_strategies = [
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
]

strategies = {s.name: s for s in strategy_strategies}

def Registry():
    # Detectar duplicados (por si en el futuro strategies se construye dinámicamente)
    names = list(strategies.keys())
    duplicates = [name for name in set(names) if names.count(name) > 1]

    if duplicates:
        print(f"⚠️ Aviso: hay estrategias repetidas: {', '.join(duplicates)}")

    return strategies

# Borrar en version final

strategy_prueba = [
    AlwaysSplit(),
    AlwaysSteal(),
    TitForTat(),
    RandomP(0.5),
    GrimTrigger(),
    WinStayLoseShift(),
    #TwoTitsForTat(),
    #ForgivingTitForTat(0.1),
    Alternator(),
    MimicMajority(),
    AlwaysOpposite(),
    FirstStealThenSplit(),
    SplitEvery4(),
    RevengeOneRound(),
    DoubleStealStart(),
    #ProbTitForTat(0.8),
    ForgiveAfter3(),
    RandomAfterLoss(),
    Mirror2Rounds(),
    BackstabAfter10(),
    RandomCycle(),
    CautiousStart(),
    CopycatDelayed(),
    SplitUntilBetrayedTwice(),
    RevengeMode(),
    #NoisyTitForTat(0.05),
    GreedyStart(),
    EveryThirdSplit(),
    #ConditionalRandom(),
    UserStrategy()
]

prueba = {strategy.name: strategy for strategy in strategy_prueba}

def PruebaRegistry():
    return prueba