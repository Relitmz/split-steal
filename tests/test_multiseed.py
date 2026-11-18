"""
Tests del paso 6: repetir el torneo con varias semillas, en serie o en paralelo.
"""

import pandas as pd
import pytest
from typer.testing import CliRunner

from split_steal.cli import app
from split_steal.multiseed import load_multi, run_seeds, save_multi, seeds_for
from split_steal.runner import TournamentConfig, run_tournament

SMALL = TournamentConfig(roster="clasicas", n_leagues=2, n_per_league=6, n_seasons=2,
                         rounds=10, noise=0.05, seed=7)


def test_seeds_are_consecutive_from_master():
    assert seeds_for(SMALL, 4) == [7, 8, 9, 10]
    with pytest.raises(ValueError):
        seeds_for(SMALL, 0)


def test_each_replica_equals_the_single_tournament_with_that_seed():
    multi = run_seeds(SMALL, n_seeds=3, workers=1)
    for s in multi.seeds:
        single = run_tournament(TournamentConfig(**{**SMALL.__dict__, "seed": s}))
        got = multi.final_rankings[multi.final_rankings.seed == s].drop(columns="seed")
        pd.testing.assert_frame_equal(got.reset_index(drop=True), single.final_ranking)


def test_parallel_gives_identical_results_to_serial():
    serial = run_seeds(SMALL, n_seeds=4, workers=1)
    parallel = run_seeds(SMALL, n_seeds=4, workers=2)
    for table in ("final_rankings", "standings", "strategy_stats", "matches", "summary"):
        pd.testing.assert_frame_equal(getattr(serial, table), getattr(parallel, table))


def test_summary_is_consistent():
    multi = run_seeds(SMALL, n_seeds=5, workers=1)
    s = multi.summary
    assert len(s) == 12 and (s.n_seeds == 5).all()
    assert (s.rank_best <= s.rank_mean).all() and (s.rank_mean <= s.rank_worst).all()
    assert s.title_rate.sum() == pytest.approx(1.0)        # un campeón por semilla
    assert s.podium_rate.sum() == pytest.approx(3.0)
    assert s.league1_rate.between(0, 1).all()
    assert list(s.rank_mean) == sorted(s.rank_mean)        # ordenado: mejor primero


def test_round_robin_has_no_league1_rate():
    multi = run_seeds(TournamentConfig(format="round_robin", roster="clasicas", rounds=10),
                      n_seeds=2, workers=1)
    assert multi.summary.league1_rate.isna().all()


def test_save_load_roundtrip_is_byte_identical(tmp_path):
    a = save_multi(run_seeds(SMALL, n_seeds=3, workers=1), tmp_path, "a")
    b = save_multi(run_seeds(SMALL, n_seeds=3, workers=2), tmp_path, "b")
    for f in ("config.json", "summary.csv", "final_rankings.csv", "standings.csv",
              "strategy_stats.csv", "matches.csv.gz"):
        assert (a / f).read_bytes() == (b / f).read_bytes(), f
    loaded = load_multi(a)
    assert loaded.seeds == [7, 8, 9] and loaded.config == SMALL
    assert len(loaded.matches) == 3 * len(run_tournament(SMALL).matches)


def test_save_rounds_not_allowed_with_many_seeds():
    with pytest.raises(ValueError, match="save_rounds"):
        run_seeds(TournamentConfig(**{**SMALL.__dict__, "save_rounds": True}), n_seeds=2)


def test_cli_seeds_and_stats(tmp_path):
    runner = CliRunner()
    out = runner.invoke(app, ["tournament", "--roster", "clasicas", "--n-leagues", "2",
                              "--n-seasons", "1", "--rounds", "5", "--seeds", "3",
                              "--workers", "2", "--out-dir", str(tmp_path), "--name", "m"])
    assert out.exit_code == 0, out.output
    assert "3 torneos" in out.output and (tmp_path / "m" / "summary.csv").exists()
    out = runner.invoke(app, ["stats", str(tmp_path / "m")])
    assert out.exit_code == 0 and "3 semillas (42..44)" in out.output
