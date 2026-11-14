"""
Gráficas de un torneo (PNG estáticos con matplotlib).

Cada función recibe un `TournamentResult` (ver runner.py) y devuelve la figura,
para poder usarlas tanto desde la CLI (`split-steal plot <run>`) como desde los
notebooks. `plot_all` genera y guarda las tres:

1. leagues_by_season.png  — en qué liga estuvo cada estrategia cada temporada
                            (la "historia" del torneo: quién sube, quién baja).
2. qualifying_points.png  — puntos por ronda en la clasificatoria (todos contra
                            todos): la comparación más justa entre estrategias.
3. cooperation_vs_payoff.png — ¿cooperar más hace ganar más? % de SPLIT frente a
                            puntos por ronda, en la clasificatoria.

Decisiones de estilo: un solo tono (azul) porque en ninguna gráfica el color
distingue series; en el mapa de ligas el azul va de oscuro (Liga 1) a claro
(última liga) y cada celda lleva además el número de liga, para no depender
solo del color.
"""

from pathlib import Path
from typing import List

import matplotlib

matplotlib.use("Agg")  # backend sin ventana: genera archivos aunque no haya pantalla
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.colors import BoundaryNorm, ListedColormap

from .runner import TournamentResult

# --- Paleta (valores de la paleta de referencia, modo claro) ---------------------
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"
BLUE = "#2a78d6"
# Escala ordinal azul para las ligas: Liga 1 la más oscura.
LEAGUE_RAMP = ["#104281", "#1c5cab", "#2a78d6", "#5598e7", "#86b6ef",
               "#b7d3f6", "#cde2fb"]

plt.rcParams.update({
    "figure.facecolor": SURFACE,
    "axes.facecolor": SURFACE,
    "savefig.facecolor": SURFACE,
    "font.family": ["Segoe UI", "DejaVu Sans"],
    "font.size": 10,
    "text.color": INK,
    "axes.labelcolor": INK_2,
    "axes.edgecolor": AXIS,
    "axes.titlesize": 13,
    "axes.titleweight": "bold",
    "axes.titlelocation": "left",
    "xtick.color": MUTED,
    "ytick.color": MUTED,
    "xtick.labelcolor": INK_2,
    "ytick.labelcolor": INK_2,
    "axes.spines.top": False,
    "axes.spines.right": False,
})


def _subtitle(ax, text: str) -> None:
    ax.text(0, 1.01, text, transform=ax.transAxes, color=INK_2, fontsize=9, va="bottom")


def _qualifying_table(result: TournamentResult) -> pd.DataFrame:
    """Por estrategia, en la temporada 0: puntos por ronda y % de rondas jugando SPLIT."""
    s = result.strategy_stats
    q = s[s["season"] == 0].copy()
    q["points_per_round"] = (q["score_split"] + q["score_steal"]) / q["rounds_played"]
    q["split_rate"] = q["times_split"] / q["rounds_played"]
    return q.set_index("name")[["points_per_round", "split_rate"]]


# =============================================================================
def plot_leagues_by_season(result: TournamentResult):
    """Mapa de calor: filas = estrategias, columnas = temporadas, color = liga."""
    st = result.standings
    seasons = st[st["season"] > 0]
    grid = seasons.pivot(index="name", columns="season", values="league")

    # Orden de filas: liga media en todo el torneo (las más "de primera" arriba);
    # en empate, la posición media dentro de la liga.
    order = (seasons.assign(rank=seasons["league"] * 100 + seasons["position"])
             .groupby("name")["rank"].mean().sort_values().index)
    grid = grid.loc[order]

    n_leagues = int(st["league"].max())
    cmap = ListedColormap(LEAGUE_RAMP[:n_leagues])
    norm = BoundaryNorm([i + 0.5 for i in range(n_leagues + 1)], n_leagues)

    n_rows, n_cols = grid.shape
    fig, ax = plt.subplots(figsize=(max(7, 0.38 * n_cols + 3), 0.27 * n_rows + 1.6))
    ax.imshow(grid.values, cmap=cmap, norm=norm, aspect="auto")

    # Separación de 2 px entre celdas (líneas del color del fondo).
    ax.set_xticks([x - 0.5 for x in range(1, n_cols)], minor=True)
    ax.set_yticks([y - 0.5 for y in range(1, n_rows)], minor=True)
    ax.grid(which="minor", color=SURFACE, linewidth=2)
    ax.tick_params(which="minor", length=0)

    # Número de liga dentro de cada celda (blanco sobre los tonos oscuros).
    for y in range(n_rows):
        for x in range(n_cols):
            league = int(grid.values[y, x])
            ax.text(x, y, str(league), ha="center", va="center", fontsize=7,
                    color="#ffffff" if league <= 3 else INK)

    ax.set_xticks(range(n_cols), grid.columns)
    ax.set_yticks(range(n_rows), grid.index)
    ax.tick_params(length=0)
    for side in ("left", "bottom"):
        ax.spines[side].set_visible(False)
    ax.set_xlabel("Temporada")
    ax.set_title("Liga de cada estrategia por temporada", pad=22)
    _subtitle(ax, f"1 = liga superior · {result.config.n_leagues} ligas × "
                  f"{result.config.n_per_league} · suben/bajan {result.config.n_ascend_descend} · "
                  f"semilla {result.config.seed}")
    fig.tight_layout()
    return fig


def plot_qualifying_points(result: TournamentResult):
    """Barras horizontales: puntos por ronda en la clasificatoria (todos contra todos)."""
    q = _qualifying_table(result).sort_values("points_per_round")

    fig, ax = plt.subplots(figsize=(8, 0.26 * len(q) + 1.6))
    ax.barh(q.index, q["points_per_round"], height=0.72, color=BLUE)

    # Referencias: lo que se gana por ronda con cooperación mutua (3) o traición mutua (1).
    for value, label in [(3, "cooperación mutua (3)"), (1, "traición mutua (1)")]:
        ax.axvline(value, color=INK_2, linewidth=1, linestyle=(0, (3, 3)))
        ax.text(value, len(q) - 0.3, label, color=INK_2, fontsize=8, ha="center", va="bottom")

    ax.set_xlim(0, max(3.4, q["points_per_round"].max() * 1.05))
    ax.set_ylim(-0.6, len(q) + 0.4)
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.tick_params(axis="y", length=0)
    ax.spines["left"].set_visible(False)
    ax.set_xlabel("Puntos medios por ronda")
    ax.set_title("Clasificatoria: rendimiento contra todas las estrategias", pad=22)
    _subtitle(ax, f"Temporada 0 · cada estrategia juega {len(q) - 1} partidos de "
                  f"{result.config.rounds} rondas")
    fig.tight_layout()
    return fig


def plot_cooperation_vs_payoff(result: TournamentResult):
    """Dispersión: % de rondas con SPLIT frente a puntos por ronda (clasificatoria)."""
    q = _qualifying_table(result)

    fig, ax = plt.subplots(figsize=(8, 5.5))
    ax.scatter(q["split_rate"] * 100, q["points_per_round"], s=48, color=BLUE,
               edgecolor=SURFACE, linewidth=1.5, zorder=3)

    # Etiquetas selectivas: las 3 mejores, las 3 peores y las clásicas de referencia.
    ranked = q.sort_values("points_per_round")
    to_label = set(ranked.index[:3]) | set(ranked.index[-3:])
    to_label |= {"AlwaysSplit", "AlwaysSteal", "TitForTat"} & set(q.index)
    for name in sorted(to_label):
        x, y = q.loc[name, "split_rate"] * 100, q.loc[name, "points_per_round"]
        ax.annotate(name, (x, y), xytext=(6, 4), textcoords="offset points",
                    fontsize=8, color=INK_2)

    ax.set_xlim(-4, 108)
    ax.grid(color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.set_xlabel("% de rondas jugando SPLIT (cooperar)")
    ax.set_ylabel("Puntos medios por ronda")
    ax.set_title("¿Cooperar más hace ganar más?", pad=22)
    _subtitle(ax, "Clasificatoria (temporada 0), una estrategia por punto")
    fig.tight_layout()
    return fig


def plot_all(result: TournamentResult, out_dir) -> List[Path]:
    """Genera las tres gráficas en `out_dir` y devuelve sus rutas."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    figures = {
        "leagues_by_season.png": plot_leagues_by_season,
        "qualifying_points.png": plot_qualifying_points,
        "cooperation_vs_payoff.png": plot_cooperation_vs_payoff,
    }
    paths = []
    for filename, make in figures.items():
        fig = make(result)
        path = out_dir / filename
        # metadata sin fecha de creación: el PNG es idéntico si los datos lo son.
        fig.savefig(path, dpi=150, bbox_inches="tight", metadata={"Software": None})
        plt.close(fig)
        paths.append(path)
    return paths
