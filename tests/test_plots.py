"""
Tests del paso 8: matriz de enfrentamientos y gráficas (comprobación de humo: se
generan sin error y producen PNG; la estética se revisa a ojo).
"""

import numpy as np
import pytest
from typer.testing import CliRunner

from split_steal.analysis import head_to_head
from split_steal.cli import app
from split_steal.experiment import load_experiment, run_experiment, save_experiment
from split_steal.multiseed import run_seeds, save_multi
from split_steal.plots import plot_sweep, plot_variants
from split_steal.runner import TournamentConfig, run_tournament, save_run

SMALL = dict(roster="clasicas", n_leagues=2, n_per_league=6, n_seasons=2, rounds=10)


def test_head_to_head_is_antisymmetric_and_ordered():
    matches = run_tournament(TournamentConfig(format="round_robin", roster="clasicas",
                                              rounds=30, noise=0.05)).matches
    t = head_to_head(matches)
    assert list(t.index) == list(t.columns) and len(t) == 12
    assert np.isnan(np.diag(t.values)).all()
    np.testing.assert_allclose(t.values, -t.values.T, equal_nan=True)   # A gana lo que B pierde
    means = t.mean(axis=1).tolist()
    assert means == sorted(means, reverse=True)
    pts = head_to_head(matches, value="points")
    assert ((pts.stack() >= 0) & (pts.stack() <= 5)).all()


def test_head_to_head_leaves_unplayed_pairs_empty():
    """En ligas sin clasificatoria, las de ligas distintas nunca se enfrentan."""
    r = run_tournament(TournamentConfig(**SMALL, n_ascend_descend=0, qualifying=False))
    t = head_to_head(r.matches)
    assert t.isna().sum().sum() == 12 + 2 * 36        # diagonal + parejas de ligas distintas
    with pytest.raises(ValueError):
        head_to_head(r.matches, value="nope")


def test_plot_command_for_run_multiseed_and_experiment(tmp_path):
    runner = CliRunner()
    run_dir = save_run(run_tournament(TournamentConfig(**SMALL)), tmp_path, "run")
    out = runner.invoke(app, ["plot", str(run_dir)])
    assert out.exit_code == 0, out.output
    assert {p.name for p in (run_dir / "figs").iterdir()} == {
        "leagues_by_season.png", "qualifying_points.png", "cooperation_vs_payoff.png",
        "head_to_head.png"}

    multi_dir = save_multi(run_seeds(TournamentConfig(**SMALL), n_seeds=2, workers=1), tmp_path, "m")
    out = runner.invoke(app, ["plot", str(multi_dir)])
    assert out.exit_code == 0 and (multi_dir / "figs" / "head_to_head.png").exists()

    toml = tmp_path / "e.toml"
    toml.write_text('name = "e"\nseeds = 2\n[base]\nformat = "round_robin"\n'
                    'roster = "clasicas"\nrounds = 10\n[sweep]\nnoise = [0.0, 0.1]\n'
                    '"Joss.p" = [0.1, 0.3]\n', encoding="utf-8")
    exp_dir = save_experiment(run_experiment(load_experiment(toml), workers=1),
                              tmp_path / "experiments", index=False)
    out = runner.invoke(app, ["plot", str(exp_dir), "--metric", "rank_mean",
                              "--strategies", "Joss,TitForTat"])
    assert out.exit_code == 0, out.output
    figs = {p.name for p in (exp_dir / "figs").iterdir()}
    assert "sweep_rank_mean.png" in figs
    assert sum(f.startswith("head_to_head__") for f in figs) == 4


def test_series_cap_is_enforced(tmp_path):
    import pandas as pd
    summary = pd.DataFrame({"strategy": [f"S{i}" for i in range(9)], "variant": "v",
                            "x": 1.0, "rank_mean": range(9), "rank_ci95": 0.1})
    with pytest.raises(ValueError, match="como mucho 8"):
        plot_sweep(summary, x="x", strategies=list(summary.strategy))
    many = summary.assign(variant=[f"v{i}" for i in range(9)])
    with pytest.raises(ValueError, match="como mucho 8"):
        plot_variants(many)
