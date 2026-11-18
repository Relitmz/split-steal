"""
Tests de humo de la CLI: cada comando arranca y responde como se espera.
"""

from typer.testing import CliRunner

from split_steal.cli import app

runner = CliRunner()


def test_catalog_and_presets_commands():
    out = runner.invoke(app, ["catalog"])
    assert out.exit_code == 0 and "*Extortioner" in out.output
    out = runner.invoke(app, ["presets"])
    assert out.exit_code == 0 and "cooperativas_con_traidores (12)" in out.output


def test_list_accepts_presets_and_custom_selections():
    out = runner.invoke(app, ["list", "TitForTat, ForgivingTitForTat(p=0.2)"])
    assert out.exit_code == 0 and "ForgivingTitForTat(p=0.2)" in out.output
    out = runner.invoke(app, ["list", "TitForTat, NoExiste"])
    assert out.exit_code != 0 and "desconocida" in out.output


def test_tournament_command_with_selection(tmp_path):
    out = runner.invoke(app, ["tournament", "--roster", "clasicas", "--n-leagues", "2",
                              "--n-seasons", "1", "--rounds", "5",
                              "--out-dir", str(tmp_path), "--name", "t"])
    assert out.exit_code == 0, out.output
    assert (tmp_path / "t" / "matches.csv").exists()
