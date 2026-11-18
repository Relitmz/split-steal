"""
Tests del paso 5: formato "todos contra todos" y clasificación final común.
"""

import pytest
from typer.testing import CliRunner

from split_steal.analysis import final_ranking
from split_steal.cli import app
from split_steal.register import PRESETS
from split_steal.runner import TournamentConfig, load_run, run_tournament, save_run


def rr(**kw):
    return TournamentConfig(format="round_robin", rounds=20, **kw)


def test_round_robin_plays_every_pair_once():
    result = run_tournament(rr(roster="clasicas"))
    n = len(PRESETS["clasicas"])
    assert len(result.matches) == n * (n - 1) // 2
    assert set(result.matches.season) == {0} and set(result.matches.league) == {0}
    assert sorted(result.standings.position) == list(range(1, n + 1))


def test_round_robin_accepts_any_number_of_strategies():
    """Sin ligas no hace falta que el número cuadre: 13 estrategias valen."""
    result = run_tournament(rr(roster="cooperativas, Extortioner"))
    assert len(result.final_ranking) == 13


def test_round_robin_ignores_league_settings():
    a = run_tournament(rr(roster="clasicas"))
    b = run_tournament(rr(roster="clasicas", n_leagues=3, n_per_league=4, n_seasons=7))
    assert a.standings.equals(b.standings)


def test_round_robin_reproducible_and_seed_sensitive():
    a = run_tournament(rr(roster="clasicas", noise=0.05, seed=1))
    b = run_tournament(rr(roster="clasicas", noise=0.05, seed=1))
    c = run_tournament(rr(roster="clasicas", noise=0.05, seed=2))
    assert a.matches.equals(b.matches)
    assert not a.matches.equals(c.matches)


def test_unknown_format_raises():
    with pytest.raises(ValueError, match="Formato desconocido"):
        run_tournament(TournamentConfig(format="eliminatoria"))


def test_final_ranking_for_leagues_puts_league_one_first():
    cfg = TournamentConfig(roster="clasicas", n_leagues=2, n_per_league=6, n_seasons=3, rounds=10)
    result = run_tournament(cfg)
    fr = result.final_ranking
    assert list(fr["rank"]) == list(range(1, 13))
    assert list(fr.league) == [1] * 6 + [2] * 6
    last = result.standings[result.standings.season == 3]
    champion = last[(last.league == 1) & (last.position == 1)].name.item()
    assert fr.iloc[0]["name"] == champion


def test_final_ranking_matches_single_table_in_round_robin():
    result = run_tournament(rr(roster="clasicas"))
    fr = final_ranking(result.standings)
    assert list(fr.name) == list(result.standings.sort_values("position").name)


def test_round_robin_save_load_and_cli(tmp_path):
    result = run_tournament(rr(roster="clasicas"))
    loaded = load_run(save_run(result, out_dir=tmp_path, name="rr"))
    assert loaded.config.format == "round_robin"

    runner = CliRunner()
    out = runner.invoke(app, ["tournament", "--format", "round_robin", "--roster", "clasicas",
                              "--rounds", "5", "--out-dir", str(tmp_path), "--name", "cli"])
    assert out.exit_code == 0, out.output
    out = runner.invoke(app, ["stats", str(tmp_path / "cli")])
    assert out.exit_code == 0 and "Clasificación final (round_robin)" in out.output
