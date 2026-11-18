"""
Tests de la simulación evolutiva (dinámica del replicador).
"""

import numpy as np
import pandas as pd
import pytest
from typer.testing import CliRunner

from split_steal.cli import app
from split_steal.evolution import (EvolutionConfig, evolve, initial_shares, load_evolution,
                                   payoff_matrix, run_evolution, save_evolution)

SMALL = EvolutionConfig(roster="TitForTat, AlwaysSteal, AlwaysSplit", rounds=20, n_seeds=3,
                        generations=200)


def test_payoff_matrix_includes_self_play_and_known_values():
    m = payoff_matrix(SMALL, workers=1)
    assert list(m.index) == list(m.columns) == ["TitForTat", "AlwaysSteal", "AlwaysSplit"]
    assert m.loc["TitForTat", "TitForTat"] == 3.0                    # cooperan siempre
    assert m.loc["AlwaysSteal", "AlwaysSteal"] == 1.0
    assert m.loc["AlwaysSteal", "AlwaysSplit"] == 5.0
    assert m.loc["TitForTat", "AlwaysSteal"] == pytest.approx(19 / 20)   # 0 + 19 × 1


def test_matrix_does_not_depend_on_workers():
    noisy = EvolutionConfig(roster="clasicas", rounds=20, n_seeds=2, noise=0.05)
    pd.testing.assert_frame_equal(payoff_matrix(noisy, workers=1), payoff_matrix(noisy, workers=3))


def test_shares_stay_a_distribution():
    shares = run_evolution(SMALL, workers=1).shares
    assert len(shares) == SMALL.generations + 1
    np.testing.assert_allclose(shares.sum(axis=1), 1.0)
    assert (shares >= 0).all().all()


def test_cooperation_invades_a_world_of_defectors():
    """El resultado clásico: unos pocos TitForTat bastan para desplazar a AlwaysSteal,
    y sin ellos AlwaysSteal elimina a los ingenuos (AlwaysSplit)."""
    m = payoff_matrix(SMALL, workers=1)
    world = evolve(m, {"AlwaysSteal": 0.95, "TitForTat": 0.05}, 300).iloc[-1]
    assert world["TitForTat"] > 0.99
    naive = evolve(m, {"AlwaysSteal": 0.5, "AlwaysSplit": 0.5}, 300).iloc[-1]
    assert naive["AlwaysSteal"] > 0.99


def test_extinct_strategies_stay_extinct():
    m = payoff_matrix(SMALL, workers=1)
    shares = evolve(m, {"AlwaysSteal": 0.5, "AlwaysSplit": 0.5}, 400)
    dead = shares.index[shares["AlwaysSplit"] == 0]
    assert len(dead) and (shares.loc[dead[0]:, "AlwaysSplit"] == 0).all()


def test_initial_shares_validation():
    names = ["A", "B"]
    np.testing.assert_allclose(initial_shares(names), [0.5, 0.5])
    np.testing.assert_allclose(initial_shares(names, {"A": 3}), [1.0, 0.0])
    with pytest.raises(ValueError, match="no están"):
        initial_shares(names, {"C": 1})
    with pytest.raises(ValueError):
        initial_shares(names, {"A": 0})


def test_negative_payoffs_are_handled():
    cfg = EvolutionConfig(roster="TitForTat, AlwaysSteal", rounds=10, n_seeds=1,
                          payoff={"R": 3, "S": -2, "T": 5, "P": 0}, generations=50)
    shares = run_evolution(cfg, workers=1).shares
    assert (shares >= 0).all().all()


def test_save_load_and_cli(tmp_path):
    result = run_evolution(SMALL, workers=1)
    loaded = load_evolution(save_evolution(result, tmp_path, "e"))
    assert loaded.config == SMALL
    pd.testing.assert_frame_equal(loaded.shares, result.shares, check_exact=False, atol=1e-7)

    out = CliRunner().invoke(app, ["evolve", "--roster", "TitForTat, AlwaysSteal, AlwaysSplit",
                                   "--initial", "AlwaysSteal=0.95,TitForTat=0.05",
                                   "--rounds", "20", "--n-seeds", "2", "--generations", "100",
                                   "--workers", "1", "--out-dir", str(tmp_path), "--name", "cli"])
    assert out.exit_code == 0, out.output
    assert "TitForTat" in out.output and (tmp_path / "cli" / "figs" / "evolution.png").exists()
