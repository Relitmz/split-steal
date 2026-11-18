"""
Tests del paso 3: pagos configurables, ruido, cuentas por partido, estadísticas
derivadas y guardado jugada a jugada.
"""

import pandas as pd
import pytest

from split_steal.analysis import perspective, strategy_stats
from split_steal.runner import TournamentConfig, load_run, run_tournament, save_run
from split_steal.simulator import Payoff, play_match
from split_steal.strategies import (SPLIT, STEAL, AlwaysSplit, AlwaysSteal, GrimTrigger,
                                    RandomP, TitForTat, WinStayLoseShift)


SMALL = dict(roster="clasicas", n_leagues=2, n_per_league=6, n_seasons=2, rounds=20)


# ------------------------------------------------------------------ pagos
def test_payoff_default_and_custom():
    assert Payoff().is_prisoners_dilemma
    chicken = Payoff(R=3, S=1, T=5, P=0)          # juego del gallina: T > R > S > P
    assert not chicken.is_prisoners_dilemma
    assert play_match(AlwaysSteal(), AlwaysSteal(), rounds=10, payoff=chicken).scores == (0, 0)
    assert play_match(AlwaysSplit(), AlwaysSteal(), rounds=10, payoff=chicken).scores == (10, 50)


# ------------------------------------------------------------------ cuentas del partido
def test_match_counts_tit_for_tat_vs_always_steal():
    m = play_match(TitForTat(), AlwaysSteal(), rounds=10)
    assert (m.cc, m.cd, m.dc, m.dd) == (0, 1, 0, 9)
    assert m.cc + m.cd + m.dc + m.dd == 10
    assert (m.first_steal_a, m.first_steal_b) == (2, 1)
    # TFT fue provocada 9 veces (rondas 2..10) y respondió siempre; AlwaysSteal lo fue 8 veces
    assert (m.provoked_a, m.retaliated_a) == (9, 9)
    assert (m.provoked_b, m.retaliated_b) == (8, 8)
    assert (m.after_dd, m.peace_a, m.peace_b) == (8, 0, 0)


def test_never_stealing_leaves_first_steal_empty():
    m = play_match(AlwaysSplit(), TitForTat(), rounds=5)
    assert m.first_steal_a is None and m.first_steal_b is None and m.cc == 5


def test_wsls_offers_peace_after_mutual_steal():
    """Pavlov: tras un St/St vuelve a cooperar (es su forma de romper la espiral)."""
    m = play_match(WinStayLoseShift(), AlwaysSteal(), rounds=10)
    assert m.after_dd > 0 and m.peace_a == m.after_dd and m.peace_b == 0


# ------------------------------------------------------------------ ruido
def test_noise_zero_changes_nothing():
    """noise=0 no consume números aleatorios: mismo resultado que sin pasar el argumento."""
    assert (play_match(RandomP(), TitForTat(), rounds=50, seed=5)
            == play_match(RandomP(), TitForTat(), rounds=50, seed=5, noise=0.0))


def test_noise_flips_moves_and_is_reproducible():
    m = play_match(AlwaysSplit(), AlwaysSplit(), rounds=1000, seed=3, noise=0.1)
    assert 50 < m.flips_a < 150 and 50 < m.flips_b < 150      # ~10 %
    assert m.cd == m.flips_b - (m.dd) and m.dc == m.flips_a - m.dd   # todo robo es un error
    assert m == play_match(AlwaysSplit(), AlwaysSplit(), rounds=1000, seed=3, noise=0.1)
    assert play_match(AlwaysSplit(), AlwaysSplit(), rounds=10, noise=1.0).dd == 10


def test_noise_breaks_grim_trigger_cooperation():
    """El hallazgo nº 1 en pequeño: sin ruido dos GrimTrigger cooperan siempre;
    con ruido, un solo error las condena a traicionarse para siempre."""
    clean = play_match(GrimTrigger(), GrimTrigger(), rounds=200, seed=1)
    noisy = play_match(GrimTrigger(), GrimTrigger(), rounds=200, seed=1, noise=0.02)
    assert clean.cc == 200
    assert noisy.dd > 100


def test_noise_uses_separate_random_stream():
    """Las estrategias reciben los MISMOS números aleatorios con y sin ruido."""
    rec = {}

    class Recorder(RandomP):
        def act(self, h_self, h_opp, rng):
            rec.setdefault(self.tag, []).append(rng.random())
            return SPLIT

    a, b = Recorder(), Recorder()
    a.tag, b.tag = "clean", "noisy"
    play_match(a, AlwaysSplit(), rounds=30, seed=9)
    play_match(b, AlwaysSplit(), rounds=30, seed=9, noise=0.3)
    assert rec["clean"] == rec["noisy"]


def test_invalid_noise_raises():
    with pytest.raises(ValueError):
        play_match(AlwaysSplit(), AlwaysSplit(), noise=1.5)
    with pytest.raises(ValueError):
        run_tournament(TournamentConfig(**SMALL, noise=-0.1))


# ------------------------------------------------------------------ estadísticas derivadas
def test_perspective_swaps_roles_for_b():
    matches = pd.DataFrame([{"A": "X", "B": "Y", "pa": 9, "pb": 14, "cc": 0, "cd": 1, "dc": 0,
                             "dd": 9, "flips_a": 0, "flips_b": 0, "first_steal_a": 2,
                             "first_steal_b": 1, "provoked_a": 9, "retaliated_a": 9,
                             "provoked_b": 8, "retaliated_b": 8, "after_dd": 8,
                             "peace_a": 0, "peace_b": 0}])
    view = perspective(matches).set_index("name")
    assert view.loc["X", "betrayed"] == 1 and view.loc["Y", "stole"] == 1
    assert view.loc["X", "result"] == -1 and view.loc["Y", "result"] == 1


def test_strategy_stats_are_consistent():
    result = run_tournament(TournamentConfig(**SMALL, noise=0.05))
    s = result.strategy_stats
    assert (s.times_split + s.times_steal == s.rounds_played).all()
    assert (s.score_split + s.score_steal == s.points).all()
    assert (s.wins + s.draws + s.losses == s.matches_played).all()
    # los puntos coinciden con la clasificación
    merged = s.merge(result.standings, on=["season", "league", "name"])
    assert (merged.points_x == merged.points_y).all()
    # todo lo que una estrategia roba, a otra se lo roban
    for (season, league), g in s.groupby(["season", "league"]):
        assert g.stole.sum() == g.betrayed.sum()
    assert s.noise_flips.sum() > 0
    assert s.coop_rate.between(0, 1).all()


def test_strategy_stats_use_configured_payoff():
    payoff = {"R": 4, "S": -1, "T": 6, "P": 0}
    result = run_tournament(TournamentConfig(**SMALL, payoff=payoff))
    s = result.strategy_stats
    assert (s.score_split + s.score_steal == s.points).all()
    assert result.config.payoff == payoff


# ------------------------------------------------------------------ guardado
def test_save_rounds_roundtrip_and_is_byte_identical(tmp_path):
    config = TournamentConfig(**SMALL, noise=0.05, save_rounds=True)
    result = run_tournament(config)
    rounds = result.rounds
    assert len(rounds) == result.matches.shape[0] * config.rounds
    assert set(rounds.columns) >= {"season", "league", "A", "B", "round", "a", "b", "flip_a", "flip_b"}

    d1 = save_run(result, out_dir=tmp_path, name="r1")
    d2 = save_run(run_tournament(config), out_dir=tmp_path, name="r2")
    for f in ("matches.csv", "strategy_stats.csv", "rounds.csv.gz"):
        assert (d1 / f).read_bytes() == (d2 / f).read_bytes(), f

    loaded = load_run(d1)
    assert len(loaded.rounds) == len(rounds)
    assert loaded.config == config


def test_rounds_not_saved_by_default(tmp_path):
    result = run_tournament(TournamentConfig(**SMALL))
    assert result.rounds is None
    run_dir = save_run(result, out_dir=tmp_path, name="r")
    assert not (run_dir / "rounds.csv.gz").exists()
    assert load_run(run_dir).rounds is None
