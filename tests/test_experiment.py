"""
Tests del paso 7: archivos de experimento, variantes, barridos, catálogo y comparación.
"""

from pathlib import Path

import pandas as pd
import pytest
from typer.testing import CliRunner

from split_steal.cli import app
from split_steal.experiment import (compare, load_experiment, run_experiment,
                                    save_experiment)
from split_steal.register import set_strategy_param, spec_of, make_strategy

ROOT = Path(__file__).resolve().parents[1]


def write(tmp_path, text, name="exp.toml"):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


SWEEP = """
name = "mini"
seeds = 2
[base]
format = "round_robin"
roster = "clasicas, ForgivingTitForTat"
rounds = 10
[sweep]
noise = [0.0, 0.1]
"ForgivingTitForTat.p" = [0.0, 0.5]
"""


# ------------------------------------------------------------------ definición
def test_sweep_expands_to_all_combinations(tmp_path):
    variants = load_experiment(write(tmp_path, SWEEP)).expand()
    assert [v.name for v in variants] == [
        "noise=0__ForgivingTitForTat.p=0", "noise=0__ForgivingTitForTat.p=0.5",
        "noise=0.1__ForgivingTitForTat.p=0", "noise=0.1__ForgivingTitForTat.p=0.5"]
    v = variants[3]
    assert v.config.noise == 0.1 and "ForgivingTitForTat(p=0.5)" in v.config.roster
    assert v.labels == {"noise": 0.1, "ForgivingTitForTat.p": 0.5}


def test_manual_variants_combined_with_sweep(tmp_path):
    exp = load_experiment(write(tmp_path, """
name = "fmt"
seeds = 1
[base]
roster = "clasicas"
rounds = 5
n_leagues = 2
n_seasons = 1
[[variants]]
name = "ligas"
format = "leagues"
[[variants]]
name = "rr"
format = "round_robin"
[sweep]
"payoff.T" = [5, 6]
"""))
    variants = exp.expand()
    assert [v.name for v in variants] == ["ligas__payoff.T=5", "ligas__payoff.T=6",
                                          "rr__payoff.T=5", "rr__payoff.T=6"]
    assert variants[3].config.format == "round_robin"
    assert variants[3].config.payoff == {"R": 3, "S": 0, "T": 6, "P": 1}


@pytest.mark.parametrize("text, message", [
    ('seeds = 2', "falta `name`"),
    ('name = "x"\nfoo = 1', "claves desconocidas"),
    ('name = "x"\n[base]\nnoize = 0.1', "ajustes desconocidos"),
    ('name = "x"\n[sweep]\nnoise = 0.1', "debe ser una lista"),
    ('name = "x"\n[sweep]\n"Nope.p" = [1]', "clave desconocida"),
    ('name = "x"\n[base]\nroster = "clasicas"\n[sweep]\n"Extortioner.p" = [1]', "no tiene el parámetro"),
    ('name = "x"\n[base]\nroster = "clasicas"\n[sweep]\n"ForgivingTitForTat.p" = [0.2]', "no está en la selección"),
    ('name = "x"\n[base]\nroster = "clasicas"', "6 × 6 = 36"),      # ligas por defecto: no cuadra
    ('name = "mal nombre"', "solo puede tener"),
    ('name = "x"\n[base\n', "TOML mal escrito"),
])
def test_invalid_experiments_fail_early_with_clear_message(tmp_path, text, message):
    with pytest.raises(ValueError, match=message):
        load_experiment(write(tmp_path, text))


@pytest.mark.parametrize("path", sorted((ROOT / "experiments").glob("*.toml")))
def test_example_experiments_are_valid(path):
    assert load_experiment(path).expand()


def test_set_strategy_param_and_spec_roundtrip():
    specs = set_strategy_param("cooperativas", "ForgivingTitForTat", "p", 1 / 3)
    assert "ForgivingTitForTat(p=0.3333333333333333)" in specs      # sin redondear
    assert "GenerousTitForTat" in specs                             # otra clase: intacta
    s = make_strategy("Alternator(start=1)")
    assert spec_of(make_strategy(spec_of(s))) == spec_of(s) == "Alternator(start=1)"


# ------------------------------------------------------------------ ejecución
def test_run_save_compare_and_index(tmp_path):
    exp = load_experiment(write(tmp_path, SWEEP))
    result = run_experiment(exp, workers=2)
    out = save_experiment(result, out_dir=tmp_path / "results" / "experiments")

    for f in ("experiment.toml", "variants.csv", "summary.csv"):
        assert (out / f).exists()
    assert (out / "experiment.toml").read_text(encoding="utf-8") == SWEEP
    assert len(list((out / "variants").iterdir())) == 4

    summary = pd.read_csv(out / "summary.csv")
    assert list(summary.columns[:4]) == ["variant", "noise", "ForgivingTitForTat.p", "name"]
    assert summary.groupby("variant").size().eq(13).all()
    # la estrategia barrida conserva su nombre real en `name`, pero no en `strategy`
    assert "ForgivingTitForTat(p=0.5)" in set(summary.name)
    assert "ForgivingTitForTat(p=0.5)" not in set(summary.strategy)

    table = compare([out], strategies=["ForgivingTitForTat", "TitForTat"])
    assert list(table.index) == sorted(table.index, key=lambda n: table.loc[n].mean())
    assert table.shape == (2, 4) and table.notna().all().all()

    index = pd.read_csv(tmp_path / "results" / "index.csv")
    assert len(index) == 4 and set(index.experiment) == {"mini"}
    # volver a guardar el mismo experimento REEMPLAZA sus filas (no las duplica)
    save_experiment(result, out_dir=tmp_path / "results" / "experiments")
    assert len(pd.read_csv(tmp_path / "results" / "index.csv")) == 4


def test_variants_share_seeds_and_results_do_not_depend_on_workers(tmp_path):
    exp = load_experiment(write(tmp_path, SWEEP))
    a = run_experiment(exp, workers=1)
    b = run_experiment(exp, workers=3)
    pd.testing.assert_frame_equal(a.summary, b.summary)
    assert {tuple(r.seeds) for r in a.results.values()} == {(42, 43)}


def test_compare_rejects_unknown_metric_or_strategy(tmp_path):
    out = save_experiment(run_experiment(load_experiment(write(tmp_path, SWEEP)), workers=1),
                          out_dir=tmp_path / "experiments", index=False)
    titles = compare([out], metric="title_rate")
    assert list(titles.index) == sorted(titles.index, key=lambda n: -titles.loc[n].mean())
    with pytest.raises(ValueError, match="métrica desconocida"):
        compare([out], metric="nope")
    with pytest.raises(ValueError, match="no aparecen"):
        compare([out], strategies=["Nope"])


def test_cli_experiment_compare_index(tmp_path):
    runner = CliRunner()
    exp_file = write(tmp_path, SWEEP)
    out_dir = tmp_path / "results" / "experiments"
    r = runner.invoke(app, ["experiment", str(exp_file), "--dry-run"])
    assert r.exit_code == 0 and "4 variantes × 2 semillas = 8 torneos" in r.output
    r = runner.invoke(app, ["experiment", str(exp_file), "--out-dir", str(out_dir), "--workers", "2"])
    assert r.exit_code == 0, r.output
    r = runner.invoke(app, ["compare", str(out_dir / "mini"), "--metric", "title_rate", "--top", "3"])
    assert r.exit_code == 0 and "title_rate" in r.output
    r = runner.invoke(app, ["index", "--results-dir", str(tmp_path / "results")])
    assert r.exit_code == 0 and "mini" in r.output
