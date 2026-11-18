"""
Tests del desempate: puntos -> enfrentamiento directo -> diferencia de puntos -> sorteo.
Los casos se construyen a mano para que cada criterio sea el que decide.
"""

from split_steal.runner import TournamentConfig, run_tournament
from split_steal.simulator import TIEBREAKERS, League, rank_league
from split_steal.strategies import AlwaysSplit, TitForTat

EVEN_LOTS = {"W": 0.5, "X": 0.5, "Y": 0.5}   # sin sorteo útil: que decidan los otros criterios


def match(a, b, pa, pb):
    return {"A": a, "B": b, "pa": pa, "pb": pb}


def order(rows):
    return [r["name"] for r in rows]


def test_points_first():
    rows = rank_league([match("X", "Y", 0, 5)], {"X": 0.0, "Y": 0.9})
    assert order(rows) == ["Y", "X"] and rows[0]["decided_by"] == "points"
    assert rows[0]["tied"] == 1


def test_head_to_head_breaks_points_tie():
    # X e Y empatan a 5 puntos, pero X ganó el partido entre ambas (5-0).
    rows = rank_league([match("X", "Y", 5, 0), match("X", "W", 0, 10), match("Y", "W", 5, 3)],
                       EVEN_LOTS)
    assert order(rows) == ["W", "X", "Y"]
    by_name = {r["name"]: r for r in rows}
    assert by_name["X"]["decided_by"] == "head_to_head"
    assert by_name["X"]["tied"] == by_name["Y"]["tied"] == 2


def test_point_diff_when_head_to_head_is_even():
    # X e Y empatan a 7 y entre ellas 3-3; X dejó ganar menos (diferencia +4 frente a -2).
    rows = rank_league([match("X", "Y", 3, 3), match("X", "W", 4, 0), match("Y", "W", 4, 6)],
                       EVEN_LOTS)
    assert order(rows)[:2] == ["X", "Y"]
    assert rows[0]["decided_by"] == "point_diff"
    assert (rows[0]["point_diff"], rows[1]["point_diff"]) == (4, -2)


def test_draw_as_last_resort():
    # Empate total: decide el sorteo (el número menor queda delante).
    matches = [match("X", "Y", 3, 3)]
    assert order(rank_league(matches, {"X": 0.7, "Y": 0.2})) == ["Y", "X"]
    rows = rank_league(matches, {"X": 0.1, "Y": 0.2})
    assert order(rows) == ["X", "Y"] and rows[0]["decided_by"] == "draw"
    assert rows[-1]["decided_by"] == "-"


def test_league_draw_is_reproducible_and_depends_on_seed():
    """Dos cooperadoras empatan en todo: el sorteo decide, igual con la misma semilla
    y distinto según la semilla (ya no gana siempre la primera por orden alfabético)."""
    def winner(seed):
        members = {s.name: s for s in [TitForTat(), AlwaysSplit()]}
        league = League(1, members, rounds=5, n_ascend_descend=1)
        table = league.play(season_seed=seed)
        assert table[0]["decided_by"] == "draw"
        return table[0]["name"]

    assert winner(3) == winner(3)
    assert {winner(seed) for seed in range(20)} == {"TitForTat", "AlwaysSplit"}


def test_standings_record_tiebreak_columns():
    result = run_tournament(TournamentConfig(roster="cooperativas", n_leagues=2, n_per_league=6,
                                             n_seasons=2, rounds=20))
    st = result.standings
    assert {"point_diff", "tied", "decided_by"} <= set(st.columns)
    assert set(st.decided_by) <= set(TIEBREAKERS) | {"-"}
    # Entre cooperativas sin ruido hay muchos empates que tiene que resolver el sorteo
    assert (st.decided_by == "draw").any()
