"""
Gráficas (PNG estáticos con matplotlib), para la CLI (`split-steal plot <carpeta>`) y
los notebooks. Cada función devuelve la figura.

De un torneo (`plot_all`, recibe un TournamentResult):
1. leagues_by_season.png  — en qué liga estuvo cada estrategia cada temporada.
2. qualifying_points.png  — puntos por ronda en la temporada 0 (todos contra todos).
3. cooperation_vs_payoff.png — ¿cooperar más hace ganar más?
4. head_to_head.png       — heatmap N×N: quién gana a quién (también para varias semillas).

De un experimento (`plot_experiment`, en <experimento>/figs/):
- sweep_<métrica>.png     — líneas: la métrica de cada estrategia frente al parámetro barrido
                            (paneles por la segunda clave del barrido, si la hay).
- variants_<métrica>.png  — puntos: una fila por estrategia, un punto por variante.
- head_to_head__<variante>.png — el heatmap de cada variante con todas sus semillas.

Decisiones de estilo: azul como tono único cuando el color no distingue series; escala
divergente rojo-gris-azul (centrada en 0) para el heatmap, porque el signo importa;
paleta categórica en orden fijo y como mucho 8 series por gráfica (más no se distinguen).
"""

from pathlib import Path
from typing import List, Optional

import matplotlib

matplotlib.use("Agg")  # backend sin ventana: genera archivos aunque no haya pantalla
import matplotlib.pyplot as plt
import numpy as np
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


def _stage(result: TournamentResult) -> str:
    """Nombre de la temporada 0 según el formato."""
    return "Todos contra todos" if result.config.format == "round_robin" else "Clasificatoria"


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
    ax.set_title(f"{_stage(result)}: rendimiento contra todas las estrategias", pad=22)
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
    _subtitle(ax, f"{_stage(result)} (temporada 0), una estrategia por punto")
    fig.tight_layout()
    return fig


# =============================================================================
# Enfrentamientos directos (heatmap N×N)
# =============================================================================

# Escala divergente: rojo (la fila pierde) - gris neutro (empate) - azul (la fila gana).
# Mismos pasos de luminosidad en los dos brazos para que ninguno "pese" más.
DIVERGING = ["#8a1f20", "#c73a39", "#f0a19f", "#f0efec", "#86b6ef", "#2a78d6", "#104281"]


def plot_head_to_head(matches: pd.DataFrame, title_note: str = ""):
    """
    Heatmap N×N: diferencia de puntos por ronda de la fila frente a la columna.

    Azul = la fila saca más puntos que la columna; rojo = menos; gris = igualados.
    Celdas vacías: parejas que no llegaron a enfrentarse (ligas distintas) y la diagonal.
    Con pocas estrategias (<= 14) cada celda lleva su valor escrito.
    """
    from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm
    from .analysis import head_to_head

    table = head_to_head(matches, value="diff")
    n = len(table)
    limit = float(np.nanmax(np.abs(table.values))) or 1.0
    cmap = LinearSegmentedColormap.from_list("split_steal_div", DIVERGING)
    cmap.set_bad(SURFACE)

    side = max(6.0, 0.24 * n + 2.5)
    fig, ax = plt.subplots(figsize=(side + 1.2, side))
    im = ax.imshow(np.ma.masked_invalid(table.values), cmap=cmap,
                   norm=TwoSlopeNorm(vcenter=0.0, vmin=-limit, vmax=limit),
                   interpolation="nearest")
    # 1 px de separación entre celdas (líneas del color de la superficie)
    ax.set_xticks(np.arange(-0.5, n, 1), minor=True)
    ax.set_yticks(np.arange(-0.5, n, 1), minor=True)
    ax.grid(which="minor", color=SURFACE, linewidth=1)
    ax.tick_params(which="minor", length=0)
    ax.set_xticks(range(n), table.columns, rotation=90, fontsize=7)
    ax.set_yticks(range(n), table.index, fontsize=7)
    ax.tick_params(length=0)
    for spine in ax.spines.values():
        spine.set_visible(False)

    if n <= 14:
        for y in range(n):
            for x in range(n):
                v = table.values[y, x]
                if not np.isnan(v):
                    dark = abs(v) > 0.55 * limit
                    ax.text(x, y, f"{v:+.1f}", ha="center", va="center", fontsize=7,
                            color="#ffffff" if dark else INK)

    cbar = fig.colorbar(im, ax=ax, fraction=0.035, pad=0.02)
    cbar.set_label("Puntos por ronda: fila − columna", color=INK_2)
    cbar.outline.set_visible(False)
    ax.set_title("¿Quién gana a quién?", pad=22)
    _subtitle(ax, "Azul: la fila saca más que la columna · rojo: menos · ordenadas de más a "
                  "menos ventaja media" + (f" · {title_note}" if title_note else ""))
    fig.tight_layout()
    return fig


# =============================================================================
# Comparación entre variantes de un experimento
# =============================================================================

# Paleta categórica de referencia, en orden fijo (nunca se reordena ni se cicla).
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
MAX_SERIES = len(SERIES)

METRIC_LABELS = {
    "rank_mean": "Posición media (1 = campeón)",
    "title_rate": "% de torneos ganados",
    "podium_rate": "% de podios (top 3)",
    "league1_rate": "% de temporadas en la Liga 1",
    "points_per_round": "Puntos medios por ronda",
    "coop_rate": "% de rondas cooperando",
    "win_rate": "% de partidos ganados",
}
PERCENT_METRICS = {"title_rate", "podium_rate", "league1_rate", "coop_rate", "win_rate"}

PARAM_LABELS = {
    "noise": "Ruido (probabilidad de que una jugada se invierta)",
    "rounds": "Rondas por partido",
    "n_ascend_descend": "Estrategias que suben y bajan por liga",
    "payoff.R": "R: puntos si ambos cooperan",
    "payoff.S": "S: puntos si me roban",
    "payoff.T": "T: puntos por robar a quien coopera",
    "payoff.P": "P: puntos si ambos roban",
}


def _param_label(key: str) -> str:
    """Nombre legible de una clave del barrido ("ForgivingTitForTat.p" -> "ForgivingTitForTat: p")."""
    if key in PARAM_LABELS:
        return PARAM_LABELS[key]
    head, _, tail = key.partition(".")
    return f"{head}: parámetro {tail}" if tail else key


def _label(metric: str) -> str:
    return METRIC_LABELS.get(metric, metric)


def _pick_strategies(summary: pd.DataFrame, metric: str, strategies, limit: int) -> List[str]:
    """Las estrategias a dibujar: las pedidas, o las `limit` mejores de media."""
    if strategies:
        return list(strategies)
    mean = summary.groupby("strategy")[metric].mean()
    mean = mean.sort_values(ascending=metric.startswith("rank"))
    return list(mean.index[:limit])


def _percent_axis(axis) -> None:
    from matplotlib.ticker import PercentFormatter
    axis.set_major_formatter(PercentFormatter(1.0, decimals=0))


def plot_sweep(summary: pd.DataFrame, x: str, metric: str = "rank_mean",
               strategies=None, facet: Optional[str] = None, title: str = ""):
    """
    Líneas: cómo cambia `metric` de cada estrategia al variar el parámetro barrido `x`.

    Una línea por estrategia (como mucho 8, colores en orden fijo; por defecto las 6
    mejores de media) con su banda de confianza del 95 % si la métrica es rank_mean.
    `facet`: otra clave del barrido -> un panel por valor (todos con el mismo eje Y).
    """
    names = _pick_strategies(summary, metric, strategies, limit=6)
    if len(names) > MAX_SERIES:
        raise ValueError(f"como mucho {MAX_SERIES} estrategias por gráfica (hay {len(names)})")
    facets = sorted(summary[facet].unique()) if facet else [None]
    fig, axes = plt.subplots(1, len(facets), figsize=(5.2 * len(facets) + 2.4, 4.8),
                             sharey=True, squeeze=False)
    for ax, fval in zip(axes[0], facets):
        data = summary if facet is None else summary[summary[facet] == fval]
        for color, name in zip(SERIES, names):
            d = data[data["strategy"] == name].sort_values(x)
            if d.empty:
                continue
            ax.plot(d[x], d[metric], color=color, linewidth=2, marker="o", markersize=5,
                    markeredgecolor=SURFACE, markeredgewidth=1.5, label=name, zorder=3)
            if metric == "rank_mean":
                ax.fill_between(d[x], d[metric] - d["rank_ci95"], d[metric] + d["rank_ci95"],
                                color=color, alpha=0.12, linewidth=0)
        ax.grid(color=GRID, linewidth=0.8)
        ax.set_axisbelow(True)
        ax.set_xlabel(_param_label(x))
        if facet:
            shown = f"{fval:g}" if isinstance(fval, float) else fval
            ax.set_title(f"{_param_label(facet)} = {shown}", fontsize=10,
                         fontweight="normal", loc="left")
        ax.margins(x=0.06)
    first = axes[0][0]
    first.set_ylabel(_label(metric))
    if metric.startswith("rank"):
        first.invert_yaxis()                     # el 1 (campeón) arriba
    if metric in PERCENT_METRICS:
        _percent_axis(first.yaxis)
    axes[0][-1].legend(loc="upper left", bbox_to_anchor=(1.02, 1), frameon=False, fontsize=8)
    fig.suptitle(title or f"{_label(metric)} según {x}", x=0.01, y=0.985, ha="left",
                 fontsize=13, fontweight="bold")
    note = f"las {len(names)} mejores de media" if not strategies else ""
    if metric == "rank_mean":
        note += (" · " if note else "") + "banda = intervalo de confianza del 95 % de la media"
    fig.text(0.01, 0.925, note, color=INK_2, fontsize=9)
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    return fig


def plot_variants(summary: pd.DataFrame, metric: str = "rank_mean", strategies=None,
                  title: str = ""):
    """
    Puntos (Cleveland): una fila por estrategia y un punto por variante, para
    comparaciones que no son un barrido numérico (p. ej. formatos distintos).
    Como mucho 8 variantes (una por color, en orden fijo). Por defecto, las 15 mejores.
    """
    variants = list(dict.fromkeys(summary["variant"]))
    if len(variants) > MAX_SERIES:
        raise ValueError(f"como mucho {MAX_SERIES} variantes por gráfica (hay {len(variants)})")
    names = _pick_strategies(summary, metric, strategies, limit=15)
    fig, ax = plt.subplots(figsize=(8.5, 0.32 * len(names) + 1.8))
    ypos = {n: i for i, n in enumerate(names)}
    for name in names:                         # guía gris que une los puntos de cada fila
        vals = summary.loc[summary["strategy"] == name, metric]
        ax.plot([vals.min(), vals.max()], [ypos[name]] * 2, color=GRID, linewidth=2, zorder=1)
    for color, v in zip(SERIES, variants):
        d = summary[(summary["variant"] == v) & (summary["strategy"].isin(names))]
        ax.scatter(d[metric], d["strategy"].map(ypos), s=46, color=color, label=v,
                   edgecolor=SURFACE, linewidth=1.5, zorder=3)
    ax.set_yticks(range(len(names)), names)
    ax.set_ylim(len(names) - 0.4, -0.6)        # la mejor arriba
    ax.tick_params(axis="y", length=0)
    ax.spines["left"].set_visible(False)
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.set_xlabel(_label(metric))
    if metric.startswith("rank"):
        ax.invert_xaxis()                      # mejor posición a la derecha
    if metric in PERCENT_METRICS:
        _percent_axis(ax.xaxis)
    ax.legend(loc="upper left", bbox_to_anchor=(1.01, 1), frameon=False, fontsize=8)
    ax.set_title(title or f"{_label(metric)} por variante", pad=22)
    _subtitle(ax, "un punto por variante · la línea gris une los de cada estrategia")
    fig.tight_layout()
    return fig


def _save(fig, path: Path) -> Path:
    # metadata sin fecha de creación: el PNG es idéntico si los datos lo son.
    fig.savefig(path, dpi=150, bbox_inches="tight", metadata={"Software": None})
    plt.close(fig)
    return path


def plot_experiment(exp_dir, metrics=("rank_mean", "title_rate"), strategies=None) -> List[Path]:
    """
    Gráficas de un experimento guardado, en `<exp_dir>/figs/`:
      - barrido con una clave numérica (y como mucho otra, que se usa para paneles):
        líneas `sweep_<métrica>.png`;
      - en otro caso (variantes a mano, varias claves...): puntos `variants_<métrica>.png`;
      - un heatmap de enfrentamientos por variante (todas sus semillas juntas).
    """
    from .experiment import load_experiment
    from .multiseed import load_multi

    exp_dir = Path(exp_dir)
    exp = load_experiment(exp_dir / "experiment.toml")
    summary = pd.read_csv(exp_dir / "summary.csv")
    out = exp_dir / "figs"
    out.mkdir(parents=True, exist_ok=True)
    numeric = [k for k in exp.sweep if pd.api.types.is_numeric_dtype(summary[k])]
    as_lines = bool(numeric) and not exp.variants and len(exp.sweep) <= 2
    paths = []
    for metric in metrics:
        title = f"{exp.name}: {_label(metric).lower()}"
        if as_lines:
            x = numeric[0]
            others = [k for k in exp.sweep if k != x]
            fig = plot_sweep(summary, x=x, metric=metric, strategies=strategies,
                             facet=others[0] if others else None, title=title)
            paths.append(_save(fig, out / f"sweep_{metric}.png"))
        else:
            fig = plot_variants(summary, metric=metric, strategies=strategies, title=title)
            paths.append(_save(fig, out / f"variants_{metric}.png"))
    for v in dict.fromkeys(summary["variant"]):
        multi = load_multi(exp_dir / "variants" / v)
        fig = plot_head_to_head(multi.matches, title_note=f"{v}, {len(multi.seeds)} semillas")
        paths.append(_save(fig, out / f"head_to_head__{v}.png"))
    return paths


def plot_all(result: TournamentResult, out_dir) -> List[Path]:
    """Genera las gráficas de un torneo en `out_dir` y devuelve sus rutas."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    figures = {
        "leagues_by_season.png": plot_leagues_by_season,
        "qualifying_points.png": plot_qualifying_points,
        "cooperation_vs_payoff.png": plot_cooperation_vs_payoff,
        "head_to_head.png": lambda r: plot_head_to_head(r.matches),
    }
    if result.config.format != "leagues":
        figures.pop("leagues_by_season.png")   # sin ligas no hay nada que dibujar
    return [_save(make(result), out_dir / filename) for filename, make in figures.items()]
