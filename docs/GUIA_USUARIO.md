# Guía de usuario

Cómo usar el simulador de principio a fin: elegir estrategias, jugar torneos, lanzar
experimentos y analizar los resultados. Todos los comandos se escriben en una terminal
con el entorno activado (ver *Instalación*). `split-steal ...` y `python -m split_steal ...`
son equivalentes.

## Índice

1. [Instalación](#1-instalación)
2. [Conceptos](#2-conceptos)
3. [Ver las estrategias](#3-ver-las-estrategias)
4. [Elegir quién juega](#4-elegir-quién-juega)
5. [Jugar un torneo](#5-jugar-un-torneo)
6. [Repetir con varias semillas](#6-repetir-con-varias-semillas)
7. [Experimentos](#7-experimentos)
8. [Dónde quedan los resultados y qué contienen](#8-dónde-quedan-los-resultados-y-qué-contienen)
9. [Analizar los resultados](#9-analizar-los-resultados)
10. [Recetas: pregunta → comando](#10-recetas-pregunta--comando)
11. [Problemas frecuentes](#11-problemas-frecuentes)

---

## 1. Instalación

```bash
conda env create -f environment.yml    # una sola vez: crea el entorno "splitsteal"
conda activate splitsteal              # cada vez que abras una terminal
pytest                                 # opcional: comprobar que todo funciona
```

Sin conda: `pip install -e ".[dev]"` en un Python ≥ 3.11.

## 2. Conceptos

| Concepto | Qué es |
|---|---|
| **Ronda** | Los dos jugadores eligen a la vez SPLIT (cooperar) o STEAL (traicionar) y reciben puntos. |
| **Partido** | N rondas seguidas entre dos estrategias (por defecto 100). Cada una ve lo ocurrido antes en ese partido. |
| **Estrategia** | Una regla que decide la siguiente jugada mirando el historial. Puede tener parámetros. |
| **Roster / selección** | Qué estrategias participan. |
| **Preset** | Una selección con nombre (`full`, `clasicas`...). |
| **Formato** | `leagues` (ligas con ascensos y descensos) o `round_robin` (todos contra todos). |
| **Semilla** | Número que fija todo el azar. Misma configuración + misma semilla = mismo resultado exacto. |
| **Ruido** | Probabilidad de que una jugada salga al revés de lo que la estrategia quería (un error). |
| **Variante** | Una condición de un experimento (p. ej. "ruido = 5 %"). |
| **Experimento** | Varias variantes, cada una repetida con N semillas, descritas en un archivo `.toml`. |

**Pagos por defecto** (puntos para mí, puntos para el rival):

|  | Rival SPLIT | Rival STEAL |
|---|---|---|
| **Yo SPLIT** | R = 3, 3 | S = 0, 5 |
| **Yo STEAL** | T = 5, 0 | P = 1, 1 |

**Formato `leagues`**: la temporada 0 (clasificatoria) es una liga con todas; su
clasificación las reparte en ligas (las mejores a la Liga 1). Después, en cada temporada
se juegan todas las ligas y a la vez los `k` primeros de cada liga suben y los `k` últimos
bajan. Los puntos de liga son la suma de puntos de todos los partidos (no las victorias).

**Desempate**: puntos → puntos en los partidos entre las empatadas → diferencia de puntos
(a favor − en contra) → sorteo con la semilla.

## 3. Ver las estrategias

```bash
split-steal catalog            # TODAS las estrategias, sus parámetros y etiquetas
                               # (* = no está en el roster oficial)
split-steal presets            # los grupos con nombre
split-steal list clasicas      # detalle de un preset o de cualquier selección
```

**Etiquetas**: `amable` (nunca traiciona primero), `traicionera` (puede traicionar sin
provocación), `vengativa`, `rencorosa` (castigo permanente), `perdona`, `aleatoria`, `fija`
(no reacciona al rival), `con_memoria`, `adaptativa`, `clasica` (de la literatura).

**Presets**:

| Preset | Nº | Contenido |
|---|---|---|
| `full` | 36 | El roster oficial |
| `clasicas` | 12 | Las más conocidas de la literatura |
| `cooperativas` | 12 | Solo amables |
| `cooperativas_con_traidores` | 12 | 9 amables + AlwaysSteal, Joss, Prober |
| `prueba` | 25 | Roster de pruebas, con la plantilla `UserStrategy` |

## 4. Elegir quién juega

Una selección es un texto (o una lista en los `.toml`) con elementos separados por comas
que se aplican **en orden**:

| Escribes | Significa |
|---|---|
| `clasicas` | el preset entero |
| `TitForTat, AlwaysSteal` | esas estrategias |
| `+Extortioner` (o sin `+`) | añadir una estrategia o un preset |
| `-AlwaysSteal` | quitar una estrategia (o `-clasicas`: todo un preset) |
| `ForgivingTitForTat(p=0.2)` | una estrategia con un parámetro distinto del de por defecto |

Ejemplos:

```bash
split-steal list "clasicas, -AlwaysSteal, +Extortioner"
split-steal list "full, -clasicas"                       # las 24 que no son clásicas
split-steal list "cooperativas, -ForgivingTitForTat, ForgivingTitForTat(p=0.3)"
```

- Los parámetros **no se cambian en el código**: se escriben en la selección.
  `strategies.py` solo define los valores por defecto.
- Dos versiones de la misma estrategia pueden jugar juntas: `ForgivingTitForTat` y
  `ForgivingTitForTat(p=0.3)` tienen nombres distintos.
- Quitar algo que no está, o escribir mal un nombre o un parámetro, da un error que dice
  qué falla.

## 5. Jugar un torneo

```bash
split-steal tournament --name prueba1                       # canónico: full, ligas 6×6
split-steal tournament --roster clasicas --n-leagues 2 --name clasicas_ligas
split-steal tournament --format round_robin --roster "cooperativas, AlwaysSteal" --name rr
split-steal tournament --noise 0.05 --payoff "T=6" --rounds 200 --name variado
```

| Opción | Por defecto | Qué hace |
|---|---|---|
| `--roster` | `full` | Quién juega (sección 4) |
| `--format`, `-f` | `leagues` | `leagues` o `round_robin` |
| `--n-leagues` / `--n-per-league` | 6 / 6 | Ligas y estrategias por liga (su producto debe ser el nº de estrategias) |
| `--k` | 2 | Cuántas suben y bajan por liga (2·k ≤ estrategias por liga) |
| `--n-seasons` | 20 | Temporadas tras la clasificatoria |
| `--qualifying / --no-qualifying` | sí | Jugar la clasificatoria (si no, se reparte en el orden de la selección) |
| `--rounds` | 100 | Rondas por partido |
| `--noise` | 0 | Probabilidad de que una jugada se invierta |
| `--payoff` | `R=3,S=0,T=5,P=1` | Pagos (las que no escribas, por defecto) |
| `--seed` | 42 | Semilla maestra |
| `--save-rounds` | no | Guardar también cada jugada (`rounds.csv.gz`, ~0,7 MB) |
| `--seeds` / `--workers` | 1 / todos | Repetir con N semillas (sección 6) |
| `--name`, `--out-dir` | fecha, `results/runs` | Dónde guardar |
| `-v` | no | Mostrar ascensos y descensos por pantalla |

En `round_robin` se ignoran las opciones de ligas y vale cualquier número de estrategias.

## 6. Repetir con varias semillas

Un solo torneo puede dar un campeón "con suerte". Repetirlo con muchas semillas muestra
qué es robusto:

```bash
split-steal tournament --seeds 50 --noise 0.05 --name ruido5_50
split-steal stats results/runs/ruido5_50
```

- Usa las semillas `seed, seed+1, ...` (42..91). La repetición `i` es exactamente
  `tournament --seed 42+i`, así que cualquier caso raro se puede reproducir solo.
- Se juega en paralelo con todos los núcleos (`--workers N` para limitarlo). El resultado
  no depende del número de procesos.
- `summary.csv` resume cada estrategia: posición media y su margen de error, mejor y peor
  posición, % de títulos, etc. (sección 8).

## 7. Experimentos

Un experimento compara varias condiciones. Se describe en un archivo `.toml`
(hay ejemplos en `experiments/`):

```toml
name = "mi_experimento"          # nombre de la carpeta de resultados (letras, números, _ y -)
description = "Qué quiero averiguar"
seeds = 50                       # semillas por variante

[base]                           # ajustes comunes a todas las variantes
format = "leagues"
roster = "full"                  # o una lista: ["clasicas", "-AlwaysSteal", "Extortioner"]
rounds = 100
noise = 0.0
payoff = { R = 3, S = 0, T = 5, P = 1 }

[sweep]                          # barrido: UNA variante por cada combinación de valores
noise = [0.0, 0.01, 0.05]
"ForgivingTitForTat.p" = [0.1, 0.3]
```

**Ajustes válidos** (en `[base]` y `[[variants]]`): `roster`, `format`, `n_leagues`,
`n_per_league`, `rounds`, `n_seasons`, `n_ascend_descend`, `seed`, `qualifying`, `payoff`,
`noise`.

**Claves del barrido** (`[sweep]`, siempre listas):

| Clave | Ejemplo |
|---|---|
| un ajuste del torneo | `noise = [0, 0.05]`, `rounds = [50, 100, 200]` |
| un pago | `"payoff.T" = [4, 5, 6]` |
| el parámetro de una estrategia | `"ForgivingTitForTat.p" = [0.1, 0.2]` (la estrategia debe estar en la selección) |

Con varias claves se prueban **todas las combinaciones** (3 × 2 = 6 variantes en el ejemplo).

**Variantes a mano**, para comparaciones que no son un barrido simple:

```toml
[[variants]]
name = "ligas"
format = "leagues"

[[variants]]
name = "todos_contra_todos"
format = "round_robin"
```

Cada `[[variants]]` cambia lo que quiera respecto a `[base]`. Si además hay `[sweep]`, el
barrido se aplica a cada una.

**Ejecutar:**

```bash
split-steal experiment experiments/ruido.toml --dry-run   # ver las variantes, sin jugar
split-steal experiment experiments/ruido.toml             # jugar y guardar
```

El archivo se valida entero antes de empezar: si algo no cuadra (un ajuste mal escrito, una
estrategia que no está, ligas que no suman), falla con un mensaje claro. Todas las variantes
usan las mismas semillas, así que sus diferencias no se deben a "otra suerte".

**Experimentos de ejemplo:** `ruido` (ruido creciente), `perdon_optimo` (cuánto perdonar),
`formatos` (ligas frente a todos contra todos) y `tentacion` (pago T).

## 8. Dónde quedan los resultados y qué contienen

```
results/
  canonical/canonical/      el torneo de referencia (versionado en git)
  runs/<nombre>/            torneos sueltos de `tournament` (solo en tu equipo)
  experiments/<nombre>/     experimentos (en git solo los resúmenes y las gráficas)
  index.csv                 catálogo de todo lo simulado (solo en tu equipo)
```

**Un torneo** (`results/runs/<nombre>/`):

| Archivo | Contenido (una fila por...) |
|---|---|
| `config.json` | la configuración completa y la lista de estrategias (para repetirlo) |
| `matches.csv` | ...partido: `season, league, A, B`, puntos `pa, pb`; rondas `cc` (ambos cooperan), `cd` (A cooperó y B le robó), `dc` (A robó), `dd` (ambos roban); `flips_a/b` (errores del ruido), `first_steal_a/b` (ronda de la primera traición), `provoked_*`/`retaliated_*` (veces que le robaron / que respondió robando), `after_dd`, `peace_*` (ofertas de paz tras una traición mutua), `seed` |
| `standings.csv` | ...estrategia, liga y temporada: `position, points, point_diff, tied` (cuántas empataban a puntos), `decided_by` (qué criterio la separó de la siguiente) |
| `strategy_stats.csv` | ...estrategia, liga y temporada: partidos, rondas, puntos a favor/en contra, victorias, `betrayed` (veces traicionada), `stole` (veces que robó), tasas `coop_rate`, `betrayed_rate`, `retaliation_rate`, `peace_rate`, `first_steal_mean` |
| `rounds.csv.gz` | (solo con `--save-rounds`) ...jugada: `round, a, b, flip_a, flip_b` |
| `figs/` | gráficas (`split-steal plot`) |

Convención: temporada 0 / liga 0 = clasificatoria (o la liga única de `round_robin`);
Liga 1 = la mejor.

**Varias semillas** (`--seeds N`): las mismas tablas, pero todas las semillas juntas con una
columna `seed` (`matches.csv.gz` comprimido), más:

| Archivo | Contenido |
|---|---|
| `final_rankings.csv` | clasificación final (1 = campeón) de cada semilla |
| `summary.csv` | por estrategia: `rank_mean` (posición media), `rank_ci95` (margen del intervalo de confianza del 95 %: la media está en `rank_mean ± rank_ci95`), `rank_std`, `rank_median`, `rank_best`, `rank_worst`, `title_rate` (% de títulos), `podium_rate` (% top 3), `league1_rate` (% de temporadas en la Liga 1), `points_per_round`, `coop_rate`, `win_rate`, `retaliation_rate`, `peace_rate` |

**Un experimento** (`results/experiments/<nombre>/`):

| Archivo | Contenido |
|---|---|
| `experiment.toml` | copia exacta del archivo ejecutado |
| `variants.csv` | una fila por variante con todos sus ajustes |
| `summary.csv` | el `summary` de cada variante, todos juntos: columnas `variant`, una por cada clave del barrido, `name` (nombre real) y `strategy` (nombre sin el parámetro barrido, para seguir a la misma estrategia entre variantes) |
| `variants/<variante>/` | los datos completos de cada variante (como "varias semillas") |
| `figs/` | gráficas (`split-steal plot`) |

## 9. Analizar los resultados

**Desde la terminal:**

```bash
split-steal stats results/runs/prueba1                 # resumen de un torneo o de varias semillas
split-steal compare results/experiments/ruido          # posición media: estrategia × variante
split-steal compare results/experiments/ruido --metric title_rate --top 10
split-steal compare results/experiments/perdon_optimo --strategies ForgivingTitForTat -t
split-steal compare results/experiments/ruido results/experiments/tentacion   # varios a la vez
split-steal index                                      # catálogo de todo lo simulado
```

`--metric` admite cualquier columna de `summary.csv`; las tablas van de mejor a peor
(`-t` intercambia filas y columnas).

**Gráficas** (`split-steal plot <carpeta>` detecta el tipo de carpeta y guarda en `figs/`):

| Carpeta | Gráficas |
|---|---|
| un torneo | liga de cada estrategia por temporada, puntos en la clasificatoria, cooperación frente a puntos, **heatmap "¿quién gana a quién?"** |
| varias semillas | heatmap con todas las semillas |
| un experimento | `sweep_<métrica>.png` (líneas frente al parámetro barrido, con banda de error) o `variants_<métrica>.png` (puntos por variante), y un heatmap por variante |

```bash
split-steal plot results/experiments/perdon_optimo --metric rank_mean --metric title_rate \
    --strategies "ForgivingTitForTat,TitForTat,AlwaysSteal"
```

**Desde Python o un notebook:**

```python
import pandas as pd
from split_steal.experiment import compare
from split_steal.runner import load_run
from split_steal.analysis import head_to_head
from split_steal import plots

s = pd.read_csv("results/experiments/ruido/summary.csv")
s[s.strategy == "TitForTat"][["noise", "rank_mean", "rank_ci95", "title_rate"]]

compare(["results/experiments/ruido"], metric="coop_rate")

run = load_run("results/canonical/canonical")
head_to_head(run.matches)                  # matriz N×N
plots.plot_sweep(s, x="noise", strategies=["TitForTat", "MimicMajority"])
```

Los notebooks de `notebooks/` son documentos de presentación: `01_torneo_canonico` explica
un torneo paso a paso y `02_experimentos` presenta los experimentos. Se ejecutan a mano
(Jupyter) y guardan los resultados dentro, para que se vean en GitHub.

## 10. Recetas: pregunta → comando

| Pregunta | Cómo |
|---|---|
| ¿Qué estrategias hay y qué hacen? | `split-steal catalog` |
| ¿Quién gana el torneo de referencia? | `split-steal stats results/canonical/canonical` |
| ¿El ganador lo es por suerte? | `split-steal tournament --seeds 50 --name s50` y mira `rank_ci95` y `title_rate` |
| ¿Qué pasa con errores? | `split-steal experiment experiments/ruido.toml` |
| ¿Mi estrategia nueva es buena? | añádela a `strategies.py` y `split-steal tournament --format round_robin --roster "full, MiEstrategia" --seeds 50 --name mia` |
| ¿Cuál es el mejor valor de un parámetro? | un `.toml` con `"Estrategia.param" = [...]` en `[sweep]` |
| ¿Cómo responde una estrategia a otra? | `split-steal plot <run>` y mira el heatmap |
| ¿Qué he simulado ya? | `split-steal index` |
| ¿Cómo reproduzco un torneo concreto? | su `config.json` tiene todos los ajustes y la semilla |

## 11. Problemas frecuentes

- **"Se esperaban n_leagues × n_per_league = ... estrategias, pero hay ..."**: en formato
  `leagues`, el número de estrategias debe ser ligas × estrategias por liga. Ajusta
  `--n-leagues`/`--n-per-league` o usa `--format round_robin`.
- **"n_ascend_descend no válido"**: una liga intermedia pierde `k` por arriba y `k` por abajo,
  así que `2·k` no puede superar las estrategias por liga.
- **Python se cierra sin mensaje al hacer gráficas (Windows)**: el entorno no está activado.
  numpy usa la librería MKL, que necesita las carpetas del entorno en el PATH; ejecuta
  `conda activate splitsteal` antes.
- **Quiero guardar cada jugada de muchos torneos**: no está permitido con `--seeds` (ocuparía
  demasiado); usa `--save-rounds` en torneos sueltos.
- **Mi estrategia da resultados distintos cada vez**: usa siempre `rng` para el azar (nunca
  `random`) y borra su estado en `reset()`.
