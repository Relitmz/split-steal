"""
Tests del motor. Ejecutar con:  pytest

Cada test comprueba UNA propiedad que el simulador debe cumplir; si alguno falla
tras un cambio, sabes exactamente qué garantía se ha roto.
"""

import pandas as pd
import pytest

from split_steal.register import PruebaRegistry, Registry
from split_steal.runner import TournamentConfig, load_run, run_tournament, save_run
from split_steal.simulator import PAYOFF, League, League_Tournament, play_match
from split_steal.strategies import (SPLIT, STEAL, AlwaysSplit, AlwaysSteal, ForgiveAfter3,
                                    RandomCycle, TitForTat)


# ------------------------------------------------------------------ reglas del juego
def test_payoff_is_prisoners_dilemma():
    """T > R > P > S  y  2R > T + S: las condiciones del dilema del prisionero."""
    R = PAYOFF[(SPLIT, SPLIT)][0]   # recompensa por cooperar
    T = PAYOFF[(STEAL, SPLIT)][0]   # tentación de traicionar
    P = PAYOFF[(STEAL, STEAL)][0]   # castigo mutuo
    S = PAYOFF[(SPLIT, STEAL)][0]   # el "primo" que coopera y es traicionado
    assert T > R > P > S
    assert 2 * R > T + S
    for (a, b), (pa, pb) in PAYOFF.items():   # simetría
        assert PAYOFF[(b, a)] == (pb, pa)


def test_known_match_scores():
    assert play_match(AlwaysSplit(), AlwaysSplit(), rounds=10) == (30, 30)
    assert play_match(AlwaysSplit(), AlwaysSteal(), rounds=10) == (0, 50)
    # TitForTat coopera en la 1.ª ronda y luego roba siempre: 0 + 9·1 vs 5 + 9·1
    assert play_match(TitForTat(), AlwaysSteal(), rounds=10) == (9, 14)


def test_match_is_deterministic_given_seed():
    reg1, reg2 = Registry(), Registry()
    for a, b in [("RandomP", "NoisyTitForTat"), ("RandomCycle", "ConditionalRandom")]:
        assert (play_match(reg1[a], reg1[b], rounds=50, seed=7)
                == play_match(reg2[a], reg2[b], rounds=50, seed=7))


# ------------------------------------------------------------------ estado por partido
def test_reset_prevents_state_leaking_between_matches():
    """El resultado de un partido no debe depender de los partidos anteriores."""
    fresh = play_match(ForgiveAfter3(), TitForTat(), rounds=20, seed=1)

    used = ForgiveAfter3()
    play_match(used, AlwaysSteal(), rounds=20, seed=1)   # termina con castigo pendiente
    assert play_match(used, TitForTat(), rounds=20, seed=1) == fresh


def test_random_cycle_draws_new_pattern_each_match():
    s = RandomCycle()
    patterns = set()
    for seed in range(20):
        play_match(s, AlwaysSplit(), rounds=3, seed=seed)
        patterns.add(tuple(s.pattern))
    assert len(patterns) > 1


def test_registry_returns_fresh_instances():
    a, b = Registry(), Registry()
    assert len(a) == 36 and len(PruebaRegistry()) == 25
    assert all(a[n] is not b[n] for n in a)


# ------------------------------------------------------------------ ligas
def test_league_round_robin_and_ordering():
    members = {s.name: s for s in [AlwaysSplit(), AlwaysSteal(), TitForTat()]}
    league = League(1, members, rounds=10, n_ascend_descend=1)
    table = league.play(season_seed=0, season=1)

    assert len(league.matches) == 3                       # n·(n-1)/2
    points = [row["points"] for row in table]
    assert points == sorted(points, reverse=True)
    assert [row["position"] for row in table] == [1, 2, 3]
    # AlwaysSteal: 50 contra AlwaysSplit + 14 contra TitForTat
    assert dict(league.clasification)["AlwaysSteal"] == 64


def test_ties_broken_alphabetically():
    members = {s.name: s for s in [TitForTat(), AlwaysSplit()]}   # empatan siempre
    league = League(1, members, rounds=5, n_ascend_descend=1)
    league.play(season_seed=0)
    assert [n for n, _ in league.clasification] == ["AlwaysSplit", "TitForTat"]


# ------------------------------------------------------------------ torneo
def test_tournament_validates_sizes():
    with pytest.raises(ValueError):
        League_Tournament(3, 4, Registry(), 10, 6, 2)     # 4·6 != 36
    with pytest.raises(ValueError):
        League_Tournament(3, 6, Registry(), 10, 6, 4)     # 2·4 > 6


def test_promotion_relegation_preserves_leagues():
    cfg = TournamentConfig(n_seasons=5, rounds=20)
    t = League_Tournament(cfg.n_seasons, cfg.n_leagues, Registry(), cfg.rounds,
                          cfg.n_per_league, cfg.n_ascend_descend).run(seed=0)
    names = [n for league in t.leagues for n in league.members]
    assert all(len(league.members) == cfg.n_per_league for league in t.leagues)
    assert sorted(names) == sorted(Registry())            # nadie se pierde ni se duplica

    st = pd.DataFrame(t.standings)
    s4 = st[st.season == 4].set_index("name")
    s5 = st[st.season == 5].set_index("name")
    moved = (s5.league - s4.league)
    assert set(moved.unique()) <= {-1, 0, 1}              # solo se mueve una categoría
    assert (moved == -1).sum() == (moved == 1).sum() == cfg.n_ascend_descend * (cfg.n_leagues - 1)


def test_tournament_reproducible_and_seed_sensitive():
    cfg = TournamentConfig(n_seasons=3, rounds=30, seed=123)
    r1, r2 = run_tournament(cfg), run_tournament(cfg)
    pd.testing.assert_frame_equal(r1.matches, r2.matches)
    pd.testing.assert_frame_equal(r1.standings, r2.standings)

    other = run_tournament(TournamentConfig(n_seasons=3, rounds=30, seed=124))
    assert not r1.matches["seed"].equals(other.matches["seed"])


def test_save_and_load_roundtrip(tmp_path):
    result = run_tournament(TournamentConfig(n_seasons=2, rounds=10))
    run_dir = save_run(result, out_dir=tmp_path, name="demo")
    loaded = load_run(run_dir)
    assert loaded.config == result.config
    pd.testing.assert_frame_equal(loaded.standings, result.standings)
    pd.testing.assert_frame_equal(loaded.strategy_stats, result.strategy_stats)


def test_strategy_stats_are_consistent():
    """Cada ronda jugada debe contarse exactamente una vez como SPLIT o STEAL."""
    result = run_tournament(TournamentConfig(n_seasons=2, rounds=10))
    s = result.strategy_stats
    assert (s.times_split + s.times_steal == s.rounds_played).all()
    # rondas por liga = (rivales en la liga) × rondas por partido
    q = s[s.season == 0]
    assert (q.rounds_played == 35 * 10).all()
