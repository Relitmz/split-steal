"""
Tests del registro: catálogo, presets y construcción de rosters a partir de texto.
"""

import pytest

from split_steal.register import (CATALOG, PRESETS, Registry, build_roster, make_strategy,
                                  resolve_selection)
from split_steal.runner import TournamentConfig, run_tournament
from split_steal.strategies import Extortioner, ForgivingTitForTat, TitForTat


def test_catalog_contains_every_strategy_including_off_roster_ones():
    assert {"TitForTat", "Extortioner", "UserStrategy", "HardMajority"} <= set(CATALOG)
    assert "Strategy" not in CATALOG          # la clase abstracta no es una estrategia


def test_official_roster_is_36_and_excludes_extortioner():
    roster = Registry()
    assert len(roster) == 36
    assert "Extortioner" not in roster and "UserStrategy" not in roster


@pytest.mark.parametrize("preset", list(PRESETS))
def test_presets_build_and_only_use_known_strategies(preset):
    roster = build_roster(preset)
    assert len(roster) == len(PRESETS[preset])


def test_preset_sizes_fit_leagues_of_six():
    for name in ("full", "clasicas", "cooperativas", "cooperativas_con_traidores"):
        assert len(PRESETS[name]) % 6 == 0, name


def test_cooperativas_preset_is_all_amable():
    assert all("amable" in s.tags for s in build_roster("cooperativas").values())


def test_cooperativas_con_traidores_has_three_traitors():
    roster = build_roster("cooperativas_con_traidores")
    assert sum("traicionera" in s.tags for s in roster.values()) == 3


def test_make_strategy_parses_params():
    s = make_strategy("ForgivingTitForTat(p=0.2)")
    assert isinstance(s, ForgivingTitForTat) and s.p == 0.2
    assert s.name == "ForgivingTitForTat(p=0.2)"
    assert isinstance(make_strategy("  TitForTat "), TitForTat)
    assert make_strategy("Alternator(start=1)").start == 1


@pytest.mark.parametrize("bad, message", [
    ("NoExiste", "desconocida"),
    ("ForgivingTitForTat(q=0.2)", "no tiene el parámetro"),
    ("ForgivingTitForTat(p=abc)", "valor no válido"),
    ("ForgivingTitForTat(0.2)", "nombre=valor"),
])
def test_make_strategy_errors_are_clear(bad, message):
    with pytest.raises(ValueError, match=message):
        make_strategy(bad)


def test_selection_from_text_list_and_mixed_presets():
    text = "TitForTat, ForgivingTitForTat(p=0.2), ForgivingTitForTat"
    assert resolve_selection(text) == ["TitForTat", "ForgivingTitForTat(p=0.2)", "ForgivingTitForTat"]
    roster = build_roster(text)
    assert list(roster) == ["TitForTat", "ForgivingTitForTat(p=0.2)", "ForgivingTitForTat"]
    mixed = build_roster(["cooperativas", "Extortioner"])
    assert len(mixed) == 13 and isinstance(mixed["Extortioner"], Extortioner)


def test_duplicates_are_rejected():
    with pytest.raises(ValueError, match="repetido"):
        build_roster("TitForTat, TitForTat")
    # Mismos parámetros escritos explícitamente = mismo nombre = duplicado
    with pytest.raises(ValueError, match="repetido"):
        build_roster("ForgivingTitForTat, ForgivingTitForTat(p=0.1)")


def test_build_roster_returns_fresh_instances():
    a, b = build_roster("clasicas"), build_roster("clasicas")
    assert all(a[n] is not b[n] for n in a)


def test_tournament_with_custom_selection():
    config = TournamentConfig(roster=["clasicas"], n_leagues=2, n_per_league=6,
                              n_seasons=2, rounds=10)
    result = run_tournament(config)
    assert sorted(result.strategies) == sorted(PRESETS["clasicas"])
    with pytest.raises(ValueError, match="2 × 6"):
        run_tournament(TournamentConfig(roster="cooperativas_con_traidores, Extortioner",
                                        n_leagues=2, n_per_league=6, n_seasons=1, rounds=5))
