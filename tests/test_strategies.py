"""
Tests de las estrategias: identidad (nombres, parámetros, etiquetas) y que cada
estrategia nueva haga exactamente lo que dice su descripción.
"""

import numpy as np
import pytest

from split_steal.register import Registry
from split_steal.simulator import play_match
from split_steal.strategies import (SPLIT, STEAL, TAGS, Adaptive, AlwaysSplit, AlwaysSteal,
                                    Extortioner, ForgivingTitForTat, GenerousTitForTat,
                                    Gradual, Joss, Mirror2Rounds, Prober, Strategy,
                                    SuspiciousTitForTat, TitForTat)


class Scripted(Strategy):
    """Estrategia de prueba: juega una secuencia fija (y luego repite la última jugada)."""
    def __init__(self, moves=(SPLIT,)):
        super().__init__()
        self.moves = tuple(moves)

    def act(self, h_self, h_opp, rng):
        return self.moves[min(len(h_self), len(self.moves) - 1)]


def moves_of(strategy, opponent, rounds=20, seed=0):
    """Juega un partido y devuelve la lista de jugadas de `strategy`."""
    played = []
    original_act = strategy.act

    def recording_act(h_self, h_opp, rng):
        move = original_act(h_self, h_opp, rng)
        played.append(move)
        return move

    strategy.act = recording_act
    play_match(strategy, opponent, rounds=rounds, seed=seed)
    return played


# ------------------------------------------------------------------ identidad
def test_names_include_only_non_default_params():
    assert ForgivingTitForTat().name == "ForgivingTitForTat"
    assert ForgivingTitForTat(p=0.2).name == "ForgivingTitForTat(p=0.2)"
    assert ForgivingTitForTat().params == {"p": 0.1}
    assert GenerousTitForTat().name == "GenerousTitForTat"
    assert GenerousTitForTat().params["p"] == pytest.approx(1 / 3)


def test_every_init_param_is_stored_as_attribute():
    """La regla de la que dependen `params` y `name`: cada argumento se guarda con su nombre."""
    for s in Registry().values():
        for param in type(s).default_params():
            assert hasattr(s, param), f"{s.name} no guarda el parámetro '{param}'"


def test_every_strategy_has_description_and_valid_tags():
    for s in Registry().values():
        assert s.description(), f"{s.name} sin descripción"
        assert s.tags, f"{s.name} sin etiquetas"
        assert s.tags <= set(TAGS), f"{s.name}: etiquetas desconocidas {s.tags - set(TAGS)}"
        assert not {"amable", "traicionera"} <= s.tags, f"{s.name}: amable y traicionera a la vez"


@pytest.mark.parametrize("seed", range(3))
def test_tags_amable_and_traicionera_match_behaviour(seed):
    """'amable' = nunca roba contra AlwaysSplit; 'traicionera' = roba alguna vez."""
    for s in Registry().values():
        stole = STEAL in moves_of(s, AlwaysSplit(), rounds=100, seed=seed)
        if "amable" in s.tags:
            assert not stole, f"{s.name} es 'amable' pero ha robado"
        if "traicionera" in s.tags:
            assert stole, f"{s.name} es 'traicionera' pero no ha robado nunca"


# ------------------------------------------------------------------ estrategias nuevas
def test_forgiving_extremes():
    """p=0 es TitForTat puro; p=1 nunca castiga."""
    assert (moves_of(ForgivingTitForTat(p=0), AlwaysSteal(), rounds=10)
            == moves_of(TitForTat(), AlwaysSteal(), rounds=10))
    assert set(moves_of(ForgivingTitForTat(p=1), AlwaysSteal(), rounds=10)) == {SPLIT}


def test_suspicious_tft_vs_tft_alternates():
    assert moves_of(SuspiciousTitForTat(), TitForTat(), rounds=6) == [1, 0, 1, 0, 1, 0]


def test_mirror2rounds_is_tit_for_two_tats():
    """Solo castiga dos traiciones seguidas."""
    opp = Scripted([STEAL, SPLIT, STEAL, STEAL, SPLIT, SPLIT])
    assert moves_of(Mirror2Rounds(), opp, rounds=7) == [0, 0, 0, 0, 1, 0, 0]


def test_gradual_punishes_proportionally_then_makes_peace():
    # El rival roba en las rondas 1 y 5 (índices 0 y 4); Gradual reacciona en la ronda siguiente.
    opp = Scripted([STEAL, SPLIT, SPLIT, SPLIT, STEAL] + [SPLIT] * 10)
    # 1.ª traición -> 1 castigo + 2 paz; 2.ª traición (ya van 2) -> 2 castigos + 2 paz.
    assert moves_of(Gradual(), opp, rounds=12) == [0, 1, 0, 0, 0, 1, 1, 0, 0, 0, 0, 0]


def test_prober_exploits_naive_and_respects_retaliators():
    assert moves_of(Prober(), AlwaysSplit(), rounds=6) == [1, 0, 0, 1, 1, 1]
    assert moves_of(Prober(), TitForTat(), rounds=6) == [1, 0, 0, 0, 0, 0]


def test_joss_only_defects_when_it_would_cooperate():
    assert set(moves_of(Joss(p=0), AlwaysSplit(), rounds=50)) == {SPLIT}
    assert set(moves_of(Joss(p=1), AlwaysSplit(), rounds=5)) == {STEAL}
    # Contra AlwaysSteal juega igual que TitForTat (no hay cooperación que traicionar)
    assert moves_of(Joss(), AlwaysSteal(), rounds=20) == [0] + [1] * 19


def test_adaptive_learns_best_reply():
    opening = [0] * 6 + [1] * 5
    # Contra AlwaysSplit robar da 5 > 3: tras probar, roba siempre.
    assert moves_of(Adaptive(), AlwaysSplit(), rounds=15) == opening + [1] * 4
    # Contra AlwaysSteal robar da 1 > 0: también roba.
    assert moves_of(Adaptive(), AlwaysSteal(), rounds=15) == opening + [1] * 4


def test_adaptive_state_is_reset_between_matches():
    fresh = play_match(Adaptive(), TitForTat(), rounds=30, seed=3)
    used = Adaptive()
    play_match(used, AlwaysSteal(), rounds=30, seed=3)
    assert play_match(used, TitForTat(), rounds=30, seed=3) == fresh


@pytest.mark.parametrize("opponent", [AlwaysSplit, TitForTat, ForgivingTitForTat])
def test_extortioner_enforces_two_to_one_surplus(opponent):
    """Propiedad Zero-Determinant: (mis puntos - 1) ≈ 2 · (puntos del rival - 1) por ronda."""
    rounds = 50_000
    pe, po = play_match(Extortioner(), opponent(), rounds=rounds, seed=11)
    surplus_e, surplus_o = pe / rounds - 1, po / rounds - 1
    assert surplus_e == pytest.approx(2 * surplus_o, abs=0.05)
    assert pe >= po
