"""
Registro de estrategias: decide QUIÉN participa en un torneo.

Un "roster" (plantilla) es un diccionario `{nombre: instancia_de_estrategia}`.
El simulador trabaja siempre con nombres (para tablas, ascensos y CSV) y usa el
diccionario para recuperar el objeto que juega.

Tres piezas:

- `CATALOG`: TODAS las estrategias que existen en `strategies.py` (también las que
  no están en el roster oficial, como Extortioner o UserStrategy).
- `PRESETS`: grupos con nombre listos para usar ("full", "clasicas"...).
- `build_roster(seleccion)`: construye un roster a partir de un preset o de una
  lista de estrategias escritas como texto, con parámetros si se quiere:

      build_roster("clasicas")
      build_roster(["TitForTat", "AlwaysSteal", "ForgivingTitForTat(p=0.2)"])
      build_roster("TitForTat, AlwaysSteal, ForgivingTitForTat(p=0.2)")   # igual, en un texto

Decisiones de diseño:
- Cada llamada crea instancias NUEVAS. Las estrategias acumulan estadísticas
  mientras juegan, así que dos torneos no deben compartir objetos (si no, el
  segundo heredaría los contadores del primero).
- Los nombres deben ser únicos. Se comprueba sobre la LISTA antes de construir el
  dict, porque un dict descartaría el duplicado en silencio.
- Los presets se guardan como TEXTO (no como objetos): así son fáciles de leer,
  se pueden copiar tal cual en un archivo de experimento y siempre dan instancias nuevas.
"""

import ast
import inspect
import re
from typing import Dict, List, Sequence, Type, Union

from . import strategies as _strategies_module
from .strategies import Strategy

Roster = Dict[str, Strategy]
Selection = Union[str, Sequence[str]]


# ------------------------------------------------------------------ catálogo
def _discover_strategies() -> Dict[str, Type[Strategy]]:
    """Todas las clases concretas que heredan de Strategy en `strategies.py`."""
    return {
        name: cls
        for name, cls in inspect.getmembers(_strategies_module, inspect.isclass)
        if issubclass(cls, Strategy) and not inspect.isabstract(cls)
        and cls.__module__ == _strategies_module.__name__
    }


CATALOG: Dict[str, Type[Strategy]] = _discover_strategies()


# ------------------------------------------------------------------ presets
_FULL = [
    # Las 29 originales
    "AlwaysSplit", "AlwaysSteal", "TitForTat", "RandomP", "GrimTrigger",
    "WinStayLoseShift", "TwoTitsForTat", "ForgivingTitForTat", "Alternator",
    "MimicMajority", "AlwaysOpposite", "FirstStealThenSplit", "SplitEvery4",
    "DoubleStealStart", "ProbTitForTat", "ForgiveAfter3", "RandomAfterLoss",
    "Mirror2Rounds", "BackstabAfter10", "RandomCycle", "CautiousStart",
    "CopycatDelayed", "SplitUntilBetrayedTwice", "RevengeMode", "NoisyTitForTat",
    "GreedyStart", "EveryThirdSplit", "ConditionalRandom", "SplitSplitSteal",
    # 7 clásicas de la literatura
    "GenerousTitForTat", "SuspiciousTitForTat", "Gradual", "Prober", "Joss",
    "Adaptive", "HardMajority",
]

PRESETS: Dict[str, List[str]] = {
    # Roster oficial: 36 estrategias (6 ligas × 6).
    "full": _FULL,

    # Las más conocidas de la literatura (12 = 2 ligas × 6).
    "clasicas": [
        "AlwaysSplit", "AlwaysSteal", "TitForTat", "GrimTrigger", "WinStayLoseShift",
        "RandomP", "GenerousTitForTat", "Mirror2Rounds", "SuspiciousTitForTat",
        "Gradual", "Prober", "Joss",
    ],

    # Solo estrategias "amables" (nunca traicionan primero). Sin traidores, ¿todas empatan?
    "cooperativas": [
        "AlwaysSplit", "TitForTat", "GrimTrigger", "WinStayLoseShift", "TwoTitsForTat",
        "ForgivingTitForTat", "GenerousTitForTat", "Mirror2Rounds", "Gradual",
        "ForgiveAfter3", "SplitUntilBetrayedTwice", "MimicMajority",
    ],

    # 9 amables + 3 traicioneras: ¿quién protege mejor al grupo de los aprovechados?
    "cooperativas_con_traidores": [
        "AlwaysSplit", "TitForTat", "GrimTrigger", "WinStayLoseShift",
        "ForgivingTitForTat", "GenerousTitForTat", "Mirror2Rounds", "Gradual",
        "MimicMajority",
        "AlwaysSteal", "Joss", "Prober",
    ],

    # Roster antiguo de pruebas (25 = 5 × 5), con la plantilla UserStrategy.
    "prueba": [
        "AlwaysSplit", "AlwaysSteal", "TitForTat", "RandomP", "GrimTrigger",
        "WinStayLoseShift", "Alternator", "MimicMajority", "AlwaysOpposite",
        "FirstStealThenSplit", "SplitEvery4", "SuspiciousTitForTat", "DoubleStealStart",
        "ForgiveAfter3", "RandomAfterLoss", "Mirror2Rounds", "BackstabAfter10",
        "RandomCycle", "CautiousStart", "CopycatDelayed", "SplitUntilBetrayedTwice",
        "RevengeMode", "GreedyStart", "EveryThirdSplit", "UserStrategy",
    ],
}


# ------------------------------------------------------------------ de texto a estrategia
_SPEC_RE = re.compile(r"^\s*(\w+)\s*(?:\((.*)\))?\s*$")


def make_strategy(spec: str) -> Strategy:
    """
    Crea UNA estrategia a partir de su texto: "TitForTat" o "ForgivingTitForTat(p=0.2)".

    Los parámetros se escriben `nombre=valor` separados por comas; los valores se
    interpretan como literales de Python (números, True/False, textos entre comillas).
    """
    match = _SPEC_RE.match(spec)
    if not match:
        raise ValueError(f"Estrategia mal escrita: '{spec}'. Formato: Nombre o Nombre(param=valor, ...)")
    class_name, args_text = match.groups()
    if class_name not in CATALOG:
        raise ValueError(f"Estrategia desconocida '{class_name}'. "
                         f"Usa `split-steal catalog` para ver las disponibles.")
    cls = CATALOG[class_name]

    kwargs = {}
    if args_text and args_text.strip():
        valid = cls.default_params()
        for part in _split_top_level(args_text):
            key, sep, value = part.partition("=")
            key = key.strip()
            if not sep or not key:
                raise ValueError(f"En '{spec}': los parámetros van como nombre=valor ('{part}')")
            if key not in valid:
                opciones = ", ".join(valid) or "(no tiene parámetros)"
                raise ValueError(f"{class_name} no tiene el parámetro '{key}'. Parámetros: {opciones}")
            try:
                kwargs[key] = ast.literal_eval(value.strip())
            except (ValueError, SyntaxError):
                raise ValueError(f"En '{spec}': valor no válido para '{key}': {value.strip()}") from None
    return cls(**kwargs)


def _split_top_level(text: str) -> List[str]:
    """Separa por comas que NO estén dentro de paréntesis.

    "A, B(x=1, y=2), C" -> ["A", "B(x=1, y=2)", "C"]
    """
    parts, depth, current = [], 0, []
    for char in text:
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        if char == "," and depth == 0:
            parts.append("".join(current))
            current = []
        else:
            current.append(char)
    parts.append("".join(current))
    return [p.strip() for p in parts if p.strip()]


def resolve_selection(selection: Selection) -> List[str]:
    """
    Convierte una selección en la lista de textos de estrategias que la forman.

    - Un nombre de preset ("clasicas") -> su lista.
    - Un texto con comas ("TitForTat, AlwaysSteal") -> esa lista.
    - Una lista -> cada elemento puede ser una estrategia o, a su vez, un preset
      (así se puede escribir ["cooperativas", "Extortioner"]).
    """
    if isinstance(selection, str):
        if selection.strip() in PRESETS:
            return list(PRESETS[selection.strip()])
        items = _split_top_level(selection)
    else:
        items = list(selection)
    specs: List[str] = []
    for item in items:
        specs.extend(PRESETS[item] if item in PRESETS else [item])
    return specs


def build_roster(selection: Selection = "full") -> Roster:
    """Construye un roster nuevo (instancias nuevas) a partir de un preset o una lista."""
    return _to_roster([make_strategy(spec) for spec in resolve_selection(selection)])


def _to_roster(strategies: List[Strategy]) -> Roster:
    """Convierte una lista de estrategias en `{nombre: estrategia}`, exigiendo nombres únicos."""
    names = [s.name for s in strategies]
    duplicates = sorted({n for n in names if names.count(n) > 1})
    if duplicates:
        raise ValueError(f"Estrategias con nombre repetido: {', '.join(duplicates)}")
    if not strategies:
        raise ValueError("La selección no contiene ninguna estrategia")
    return {s.name: s for s in strategies}


# ------------------------------------------------------------------ atajos
def Registry() -> Roster:
    """Roster oficial (36 estrategias), con instancias nuevas en cada llamada."""
    return build_roster("full")


def PruebaRegistry() -> Roster:
    """Roster de prueba (25 estrategias, incluye UserStrategy)."""
    return build_roster("prueba")
