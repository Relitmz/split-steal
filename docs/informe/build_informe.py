"""
Monta el informe en Word (docs/informe/Informe_SplitSteal.docx).

Las cifras salen de `cifras.json` y las gráficas de `figs/`, ambos generados por
`notebooks/03_informe.ipynb`. Así el texto y los datos no pueden contradecirse:
si cambian los resultados, se re-ejecuta el notebook y luego este script.

    python docs/informe/build_informe.py

Requiere `python-docx` (pip install python-docx). El índice es un campo de Word: se
rellena al abrir el documento (Word pregunta si actualizar campos) o con F9.
"""

import json
import re
from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

HERE = Path(__file__).resolve().parent
FIGS = HERE / "figs"
C = json.loads((HERE / "cifras.json").read_text(encoding="utf-8"))
OUT = HERE / "Informe_SplitSteal.docx"

AUTHOR = "Jacobo Migoya"
DATE = "Noviembre de 2026"

INK = RGBColor(0x0B, 0x0B, 0x0B)
INK_2 = RGBColor(0x52, 0x51, 0x4E)
BLUE = RGBColor(0x1C, 0x5C, 0xAB)
ORANGE = RGBColor(0xC2, 0x4E, 0x1F)
FONT = "Calibri"


# =============================================================================
# Utilidades de formato
# =============================================================================

def pct(x):
    return f"{x:.0f} %"


def num(x, d=1):
    return f"{x:.{d}f}".replace(".", ",")


def shade(cell, hex_color):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_color)
    tcPr.append(shd)


def cell_borders(cell, color="FFFFFF"):
    tcPr = cell._tc.get_or_add_tcPr()
    borders = OxmlElement("w:tcBorders")
    for side in ("top", "left", "bottom", "right"):
        b = OxmlElement(f"w:{side}")
        b.set(qn("w:val"), "single")
        b.set(qn("w:sz"), "4")
        b.set(qn("w:color"), color)
        borders.append(b)
    tcPr.append(borders)


def add_runs(par, text, size=None, color=None, italic=False):
    """Texto con **negritas** y `código` (letra monoespaciada) sencillos."""
    for chunk in re.split(r"(`[^`]+`)", text):
        if chunk.startswith("`") and chunk.endswith("`") and len(chunk) > 1:
            r = par.add_run(chunk[1:-1])
            r.font.name = "Consolas"
            r.font.size = Pt((size or 11) - 1)
            r.font.color.rgb = color or INK_2
            continue
        for i, part in enumerate(chunk.split("**")):
            if not part:
                continue
            r = par.add_run(part)
            r.bold = i % 2 == 1
            r.italic = italic
            if size:
                r.font.size = Pt(size)
            if color:
                r.font.color.rgb = color
    return par


class Informe:
    def __init__(self):
        self.doc = Document()
        self.fig_n = 0
        self._styles()

    # ---------------------------------------------------------------- estilos
    def _styles(self):
        d = self.doc
        sec = d.sections[0]
        sec.page_width, sec.page_height = Cm(21), Cm(29.7)
        sec.left_margin = sec.right_margin = Cm(2.3)
        sec.top_margin, sec.bottom_margin = Cm(2.2), Cm(2.2)
        normal = d.styles["Normal"]
        normal.font.name = FONT
        normal.font.size = Pt(11)
        normal.font.color.rgb = INK
        normal.element.rPr.rFonts.set(qn("w:eastAsia"), FONT)
        pf = normal.paragraph_format
        pf.space_after = Pt(6)
        pf.line_spacing = 1.15
        for name, size, color, before, after in [("Heading 1", 20, BLUE, 18, 8),
                                                 ("Heading 2", 14, BLUE, 12, 4),
                                                 ("Heading 3", 12, INK, 10, 3),
                                                 ("Title", 32, INK, 0, 6)]:
            st = d.styles[name]
            st.font.name = FONT
            st.element.rPr.rFonts.set(qn("w:eastAsia"), FONT)
            st.font.size = Pt(size)
            st.font.bold = True
            st.font.color.rgb = color
            st.paragraph_format.space_before = Pt(before)
            st.paragraph_format.space_after = Pt(after)
            st.paragraph_format.keep_with_next = True
        # Número de página en el pie
        footer = sec.footer.paragraphs[0]
        footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
        self._field(footer, "PAGE")

    def _field(self, par, instr):
        run = par.add_run()
        for tag, text in [("begin", None), (None, instr), ("separate", None), (None, ""), ("end", None)]:
            if tag:
                el = OxmlElement("w:fldChar")
                el.set(qn("w:fldCharType"), tag)
                run._r.append(el)
            else:
                t = OxmlElement("w:instrText" if text else "w:t")
                t.set(qn("xml:space"), "preserve")
                t.text = text
                run._r.append(t)
        run.font.size = Pt(9)
        run.font.color.rgb = INK_2

    # ---------------------------------------------------------------- bloques
    def h1(self, text, tag=None):
        self.doc.add_heading(text, level=1)
        if tag:
            self.tag(tag)

    def plain_title(self, text):
        """Título con aspecto de Heading 1 pero que NO entra en el índice."""
        par = self.doc.add_paragraph()
        r = par.add_run(text)
        r.bold = True
        r.font.size = Pt(20)
        r.font.color.rgb = BLUE
        par.paragraph_format.space_after = Pt(8)

    def h2(self, text):
        self.doc.add_heading(text, level=2)

    def h3(self, text):
        self.doc.add_heading(text, level=3)

    def tag(self, kind):
        """Etiqueta de lectura bajo un título."""
        label = {"ligera": ("LECTURA LIGERA", BLUE),
                 "tecnica": ("PARA CURIOSOS · puedes saltarlo", ORANGE)}[kind]
        p = self.doc.add_paragraph()
        r = p.add_run(label[0])
        r.bold = True
        r.font.size = Pt(8.5)
        r.font.color.rgb = label[1]
        p.paragraph_format.space_after = Pt(4)

    def p(self, text, **kw):
        return add_runs(self.doc.add_paragraph(), text, **kw)

    def bullets(self, items):
        for it in items:
            add_runs(self.doc.add_paragraph(style="List Bullet"), it)

    def numbered(self, items):
        """Lista numerada que empieza siempre en 1 (con sangría francesa)."""
        for k, it in enumerate(items, start=1):
            par = self.doc.add_paragraph()
            par.paragraph_format.left_indent = Cm(0.8)
            par.paragraph_format.first_line_indent = Cm(-0.6)
            add_runs(par, f"{k}.	" + it)
            par.paragraph_format.tab_stops.add_tab_stop(Cm(0.8))

    def box(self, title, text, fill="EAF2FC", title_color=BLUE):
        """Recuadro de color (una tabla de una celda)."""
        t = self.doc.add_table(rows=1, cols=1)
        t.alignment = WD_TABLE_ALIGNMENT.CENTER
        cell = t.cell(0, 0)
        shade(cell, fill)
        cell_borders(cell, fill)
        cell.width = Cm(16.4)
        p = cell.paragraphs[0]
        r = p.add_run(title)
        r.bold = True
        r.font.color.rgb = title_color
        paragraphs = text if isinstance(text, list) else [text]
        for para in paragraphs:
            add_runs(cell.add_paragraph(), para)
        self.doc.add_paragraph().paragraph_format.space_after = Pt(2)

    def vida_real(self, text):
        self.box("En la vida real", text)

    def curiosos(self, text):
        self.box("Para curiosos (técnico)", text, fill="FDF0EA", title_color=ORANGE)

    def fig(self, name, caption, width=16.0):
        self.fig_n += 1
        self.doc.add_picture(str(FIGS / f"{name}.png"), width=Cm(width))
        self.doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
        cap = self.doc.add_paragraph()
        cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
        add_runs(cap, f"**Figura {self.fig_n}.** {caption}", size=9, color=INK_2)

    def table(self, header, rows, widths):
        t = self.doc.add_table(rows=1 + len(rows), cols=len(header))
        t.alignment = WD_TABLE_ALIGNMENT.CENTER
        for j, h in enumerate(header):
            c = t.cell(0, j)
            shade(c, "1C5CAB")
            cell_borders(c, "FFFFFF")
            run = c.paragraphs[0].add_run(h)
            run.bold = True
            run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
            run.font.size = Pt(9.5)
        for i, row in enumerate(rows, start=1):
            for j, val in enumerate(row):
                c = t.cell(i, j)
                shade(c, "F4F3EF" if i % 2 else "FFFFFF")
                cell_borders(c, "FFFFFF")
                add_runs(c.paragraphs[0], str(val), size=9.5)
        for j, w in enumerate(widths):
            for row in t.rows:
                row.cells[j].width = Cm(w)
        self.doc.add_paragraph().paragraph_format.space_after = Pt(2)

    def page_break(self):
        self.doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)

    def toc(self):
        p = self.doc.add_paragraph()
        self._field(p, 'TOC \\o "1-1" \\h \\z \\u')

    def save(self):
        self.doc.save(OUT)
        return OUT


# =============================================================================
# Contenido
# =============================================================================

def e(strategy, noise, world):
    return C["entornos"][f"{strategy}|{noise}|{world}"]


def build():
    R = Informe()
    d = R.doc

    # ------------------------------------------------------------------ portada
    for _ in range(5):
        d.add_paragraph()
    t = d.add_paragraph(style="Title")
    t.add_run("Cooperar, traicionar o perdonar")
    sub = d.add_paragraph()
    add_runs(sub, "Lo que 36 estrategias y miles de torneos simulados nos cuentan sobre "
                  "el dilema del prisionero… y sobre la vida real", size=15, color=INK_2)
    d.add_paragraph()
    add_runs(d.add_paragraph(), f"**{AUTHOR}**", size=12)
    add_runs(d.add_paragraph(), DATE, size=11, color=INK_2)
    for _ in range(8):
        d.add_paragraph()
    add_runs(d.add_paragraph(),
             "Informe del proyecto Split/Steal: un simulador en Python de torneos del juego "
             "Split/Steal iterado. Código, datos y notebooks en el repositorio del proyecto.",
             size=9.5, color=INK_2)
    R.page_break()

    # ------------------------------------------------------------------ cómo leer
    R.plain_title("Cómo leer este informe")
    R.p("Este informe está pensado para leerse como quien ve un vídeo de divulgación: "
        "sin fórmulas y yendo al grano. Cada sección lleva una etiqueta:")
    R.bullets([
        "**LECTURA LIGERA:** la idea, las gráficas y qué significa en la vida real. Si solo "
        "quieres las conclusiones, quédate con estas.",
        "**PARA CURIOSOS:** cómo está hecho por dentro y los detalles de las simulaciones. "
        "Se pueden saltar sin perder el hilo.",
    ])
    R.p("Además, cada sección responde a **una pregunta**. Si vienes a por una respuesta "
        "concreta, búscala aquí:")
    R.table(["Si te preguntas…", "Ve a"], [
        ["¿Qué es esto y por qué importa?", "1. ¿De qué va esto?"],
        ["¿Quién gana, cooperar o traicionar?", "4. ¿Quién gana?"],
        ["¿Hay que ganar a los demás para ganar?", "5. ¿Ganar cada partido es ganar el torneo?"],
        ["¿Qué tienen en común las que ganan?", "6. Las 4 cualidades"],
        ["¿Influye con quién me rodeo?", "7. ¿Depende de con quién te juntes?"],
        ["¿Qué pasa cuando hay malentendidos?", "8. Malentendidos"],
        ["¿Cuándo conviene perdonar? ¿Cuánto?", "9. ¿Cuándo conviene perdonar?"],
        ["¿Juzgo por el último gesto o por la trayectoria?", "10. Memoria"],
        ["¿Es lo mismo una liga que un todos contra todos?", "11. ¿Liga o todos contra todos?"],
        ["¿Y si traicionar compensa más?", "12. La tentación"],
        ["¿Puede la cooperación surgir entre egoístas?", "13. Evolución"],
        ["¿Qué me llevo de todo esto?", "14. Lecciones para la vida real"],
    ], widths=[10.2, 6.2])
    R.page_break()
    R.plain_title("Índice")
    R.p("(Si el índice aparece vacío, haz clic derecho sobre él y elige «Actualizar campo».)",
        size=9, color=INK_2)
    R.toc()
    R.page_break()

    # ------------------------------------------------------------------ 0 resumen
    R.h1("0. Resumen en 2 minutos", "ligera")
    R.p("Dos personas eligen a la vez entre **cooperar** o **traicionar**. Si las dos cooperan, "
        "ganan bastante; si una traiciona a la otra, la traidora gana mucho y la otra nada; si las "
        "dos traicionan, ganan muy poco. Es el famoso **dilema del prisionero**, y aparece por todas "
        "partes: países, empresas, compañeros de piso, animales…")
    R.p("He programado **36 personalidades** distintas (desde la que coopera siempre hasta la que "
        "traiciona siempre, pasando por vengativas, rencorosas, perdonadoras o tramposas) y las he "
        "puesto a competir en **miles de torneos simulados**. Esto es lo que sale:")
    R.numbered([
        "**Ser amable funciona.** Las que nunca traicionan primero ocupan de media el puesto "
        f"{num(C['rank_amables'])}; las demás, el {num(C['rank_no_amables'])}.",
        f"**Ganar a los demás no es ganar.** AlwaysSteal (traicionar siempre) gana el "
        f"{C['alwayssteal_win_rate']} % de sus partidos y acaba a mitad de tabla. TitForTat no gana "
        f"ni uno y está siempre arriba.",
        "**Hay que saber responder.** Ser bueno sin defenderse sale caro: AlwaysSplit, que coopera "
        f"siempre, queda de media en el puesto {num(C['alwayssplit_rank'])} de 36.",
        "**Con malentendidos, hay que perdonar un poco.** Lo óptimo es perdonar alrededor de "
        "**1 de cada 10 traiciones**. Ni nunca, ni siempre.",
        "**Mejor juzgar por la trayectoria que por el último gesto.** Con errores, la estrategia "
        f"que mira todo el historial (MimicMajority) gana el {C['mimic_titulos_ruido5']} % de los torneos.",
        "**El entorno lo es todo.** La misma estrategia puede ser la mejor en un sitio y la peor "
        "en otro. Traicionar siempre es lo peor entre gente amable… y está entre lo mejor entre traidores.",
        "**La cooperación puede conquistar un mundo egoísta.** Basta con que empiece un "
        f"{num(C['masa_critica_pct'], 1)} % de cooperadoras para que acaben siendo el 100 %.",
    ])
    R.p("La idea de fondo: casi nada en la vida es un juego de suma cero. Para ganar no hace falta "
        "que otro pierda; hace falta encontrar con quién crear valor juntos.")
    R.page_break()

    # ------------------------------------------------------------------ 1
    R.h1("1. ¿De qué va esto? El juego y por qué está en todas partes", "ligera")
    R.h2("El juego en 30 segundos")
    R.p("En cada ronda, dos jugadores eligen en secreto y a la vez: **SPLIT** (compartir, cooperar) o "
        "**STEAL** (robar, traicionar). Los puntos son estos:")
    R.table(["", "El otro coopera (SPLIT)", "El otro traiciona (STEAL)"], [
        ["**Yo coopero (SPLIT)**", "3 para cada uno", "Yo 0, el otro 5"],
        ["**Yo traiciono (STEAL)**", "Yo 5, el otro 0", "1 para cada uno"],
    ], widths=[4.8, 5.8, 5.8])
    R.p("Míralo desde tu lado. Si el otro coopera, te conviene traicionar (5 mejor que 3). Si el otro "
        "traiciona, también te conviene traicionar (1 mejor que 0). O sea: **pase lo que pase, traicionar "
        "parece lo listo**. Pero si los dos pensáis igual, acabáis con 1 punto cada uno, cuando cooperando "
        "habríais tenido 3. Lo individualmente lógico lleva a un resultado peor para los dos. Ese es el dilema.")
    R.h2("El truco: jugar muchas veces")
    R.p("Si solo juegas una vez con un desconocido, traicionar tiene sentido. Pero en la vida real casi "
        "nunca es así: vuelves a ver a tu compañero de trabajo mañana, a tu vecino la semana que viene y a tu "
        "cliente el mes que viene. Cuando se juega **muchas rondas seguidas con la misma persona**, cada uno "
        "puede castigar la traición del otro… y de repente cooperar puede salir rentable. En este proyecto cada "
        "partido son **100 rondas** seguidas.")
    R.vida_real([
        "**La Guerra Fría.** EE. UU. y la URSS gastaron billones en armas nucleares que nunca podían usar. "
        "Los dos habrían estado mejor sin esa carrera, pero ninguno quería ser el que se desarmaba primero.",
        "**Compañeros de piso.** Fregar cuesta. Lo cómodo es que friegue el otro… pero si los dos pensáis "
        "así, la cocina acaba hecha un desastre.",
        "**Empresas y precios.** Bajar precios te quita clientes de la competencia, pero si las dos lo hacéis, "
        "ganáis menos las dos (una «guerra de precios»).",
        "**Golden Balls.** El nombre Split/Steal viene de un concurso de la televisión británica en el que, al "
        "final, dos concursantes elegían «Split» o «Steal» para repartirse (o no) un bote de dinero.",
    ])
    R.h2("¿Qué es una estrategia?")
    R.p("Una **estrategia** es una regla para decidir qué hacer, mirando lo que ha pasado antes en el "
        "partido. Por ejemplo, **TitForTat** («ojo por ojo») empieza cooperando y después copia lo último que "
        "hizo el rival. **GrimTrigger** coopera hasta la primera traición y desde entonces traiciona para "
        "siempre. **AlwaysSteal** traiciona siempre. Son como personalidades.")
    R.h2("De dónde viene la idea")
    R.p("En 1980, el politólogo **Robert Axelrod** organizó un torneo: invitó a expertos a enviar programas "
        "que jugaran a esto entre sí. Ganó el más simple de todos, TitForTat. Este proyecto repite esa idea con "
        "36 estrategias y añade cosas que Axelrod no tenía tan a mano: miles de repeticiones, errores, ligas "
        "con ascensos y descensos, y simulaciones de evolución. El vídeo de Veritasium sobre teoría de juegos "
        "(ver Referencias) cuenta esa historia muy bien y ha servido de inspiración.")

    # ------------------------------------------------------------------ 2
    R.h1("2. ¿Cómo funciona el simulador?", "tecnica")
    R.p("Es un programa en Python que juega millones de rondas siguiendo reglas simples:")
    R.bullets([
        "**Partido:** dos estrategias juegan 100 rondas seguidas. Cada una solo ve lo que ha pasado en ese partido.",
        "**Todos contra todos:** cada estrategia juega un partido contra cada una de las demás. Gana la que "
        "más puntos **suma** (no la que más partidos gana: eso será importante).",
        "**Ligas:** como en el fútbol. Primero, una clasificatoria de todos contra todos reparte a las 36 en "
        "6 ligas de 6. Después se juegan 20 temporadas: cada temporada, las 2 primeras de cada liga suben y "
        "las 2 últimas bajan.",
        "**Errores (ruido):** con cierta probabilidad (por ejemplo, el 5 %), una jugada sale al revés de lo que "
        "la estrategia quería. Es un malentendido: el otro no sabe si fue a propósito.",
        "**Semillas:** algunas estrategias usan el azar. Para no fiarnos de un torneo con suerte, cada "
        "experimento se repite **50 veces** con semillas distintas y se miran las medias.",
        "**Evolución:** en vez de 36 jugadoras, imaginamos una población enorme. Las estrategias que más "
        "puntúan se multiplican y las que menos desaparecen, generación tras generación.",
    ])
    R.curiosos([
        "El código está organizado en capas: las estrategias solo deciden (`strategies.py`); el motor juega "
        "y registra lo que pasa en cada partido (`simulator.py`); las estadísticas se calculan después a "
        "partir de esos registros (`analysis.py`); los experimentos se describen en archivos `.toml` y se "
        "ejecutan en paralelo en todos los núcleos del ordenador (`experiment.py`, `multiseed.py`); la "
        "evolución usa la «dinámica del replicador» (`evolution.py`).",
        "Todo es **reproducible**: con la misma configuración y la misma semilla, los resultados son "
        "idénticos byte a byte. Más de 120 tests automáticos comprueban las reglas, las estrategias y la "
        "reproducibilidad. Uno de ellos detectó dos estrategias que, pese a su nombre, jugaban exactamente "
        "como TitForTat (se corrigieron).",
        "Este informe usa cinco experimentos de 50 semillas cada uno (ruido, perdón, formatos, tentación y "
        "entornos) y simulaciones de evolución. Las gráficas y cifras salen del notebook `03_informe.ipynb`.",
    ])

    # ------------------------------------------------------------------ 3
    R.h1("3. Las 36 personalidades", "ligera")
    R.p(f"Cada estrategia tiene rasgos. Hay **{C['n_amables']} amables** (nunca traicionan primero) y "
        f"**{C['n_traicioneras']} traicioneras** (pueden traicionar sin motivo); el resto usan el azar sin "
        "llegar a ninguno de los dos extremos. Algunas de las más importantes en esta historia:")
    R.table(["Estrategia", "Cómo juega", "En humano"], [
        ["TitForTat", "Empieza cooperando y copia lo último que hizo el rival", "Justa: me tratas, te trato"],
        ["GrimTrigger", "Coopera hasta la primera traición; luego, nunca más", "Rencorosa: no perdona nunca"],
        ["GenerousTitForTat", "Como TitForTat, pero perdona 1 de cada 3 traiciones", "Generosa"],
        ["ForgivingTitForTat", "Como TitForTat, pero perdona 1 de cada 10", "Justa con margen"],
        ["Gradual", "Castiga más cuanto más le traicionan y luego ofrece paz", "Firme pero conciliadora"],
        ["MimicMajority", "Hace lo que el rival ha hecho más veces en el partido", "Juzga por la trayectoria"],
        ["WinStayLoseShift", "Si le fue bien, repite; si le fue mal, cambia", "Pragmática (Pavlov)"],
        ["AlwaysSplit", "Coopera siempre", "La santa (o la ingenua)"],
        ["AlwaysSteal", "Traiciona siempre", "El aprovechado"],
        ["Prober / Joss", "Tantean o traicionan por sorpresa de vez en cuando", "Las tramposas"],
    ], widths=[3.8, 7.4, 5.2])
    R.fig("f01_personalidades", "Los rasgos de cada una de las 36 estrategias del roster oficial.", width=12.5)

    # ------------------------------------------------------------------ 4
    R.h1("4. ¿Quién gana?", "ligera")
    top = C["top5_sin_ruido"]
    R.p(f"Repitiendo 50 veces el torneo de ligas sin errores, las cinco mejores de media son **{top[0]}, "
        f"{top[1]}, {top[2]}, {top[3]} y {top[4]}**. Todas tienen algo en común: **cooperan, pero responden "
        f"si las traicionan**. De hecho, las {C['top10_amables']} primeras son todas amables.")
    R.fig("f03_quien_gana", "Posición media de cada estrategia en 50 torneos de ligas sin errores. Azul: "
                            "amables; naranja: traicioneras; gris: otras. La línea es el margen de error.")
    R.p(f"Por grupos: las amables quedan de media en el puesto **{num(C['rank_medio_grupo']['Amable'])}**, "
        f"las traicioneras en el **{num(C['rank_medio_grupo']['Traicionera'])}**. Y ojo a AlwaysSplit, la que "
        f"coopera siempre: puesto **{num(C['alwayssplit_rank'])}**. Ser bueno no basta; hay que saber defenderse.")
    R.h2("Un torneo por dentro")
    R.p("Así se ve un torneo concreto, temporada a temporada. Las cooperadoras se asientan en las ligas de "
        "arriba (color oscuro) y las traicioneras se mueven por las de abajo:")
    R.fig("f02_canonico_ligas", "En qué liga juega cada estrategia en cada una de las 20 temporadas "
                                "(un torneo, semilla 42). 1 = la mejor liga.", width=13)

    # ------------------------------------------------------------------ 5
    R.h1("5. ¿Ganar cada partido es ganar el torneo?", "ligera")
    h2h = C["alwayssteal_h2h"]
    R.p(f"Esta es la paradoja más bonita del juego. **AlwaysSteal**, que traiciona siempre, **no pierde "
        f"nunca** un enfrentamiento: contra {h2h['gana']} rivales gana, contra {h2h['empata']} empata y "
        f"contra {h2h['pierde']} pierde. Gana el **{C['alwayssteal_win_rate']} %** de sus partidos. Y sin "
        f"embargo acaba de media en el puesto **{num(C['alwayssteal_rank'])}** de 36.")
    R.p(f"Al revés le pasa a **TitForTat**: sin errores **no puede ganar ni un solo partido** (solo traiciona "
        f"después de que le traicionen, así que como mucho empata). Gana el {C['tft_win_rate']} % de sus "
        f"partidos… y queda de media en el puesto **{num(C['tft_rank'])}**.")
    R.fig("f04_ganar_partidos", "Porcentaje de partidos ganados frente a posición media. Las que más ganan "
                                "partidos (derecha) no son las que mejor quedan (arriba).", width=14)
    R.p("¿Cómo puede ser? Porque los puntos no te los da el rival: te los da el juego. Cuando AlwaysSteal "
        "juega contra alguien que se defiende, los dos acaban sacando 1 punto por ronda. Dos cooperadoras, en "
        "cambio, se llevan 3 cada una. Contra TitForTat, AlwaysSteal «gana» por 1,04 a 0,99 puntos por ronda; dos TitForTat «empatan» a 3.")
    R.fig("f05_heatmap", "¿Quién gana a quién? Cada celda: puntos por ronda de la fila menos los de la "
                         "columna. Azul: la fila gana; rojo: pierde. Las de arriba ganan a casi todas… y "
                         "aun así no son las mejores del torneo.", width=15.5)
    R.vida_real("Casi nada en la vida es de suma cero, como el ajedrez o el póker, donde lo que gana uno lo "
                "pierde el otro. En el trabajo, en los negocios o en la amistad, el «premio» lo pone el mundo "
                "(el banquero del juego), no el otro jugador. El que necesita ganar cada discusión o exprimir "
                "cada trato acaba sin socios. El que busca acuerdos donde ganan los dos, acumula.")

    # ------------------------------------------------------------------ 6
    R.h1("6. ¿Qué tienen en común las ganadoras? Las 4 cualidades", "ligera")
    q = C["cualidades"]
    R.p("Axelrod resumió el secreto de las estrategias ganadoras en cuatro cualidades. Con nuestros datos "
        "las podemos **medir**:")
    R.fig("f06_cualidades", "Posición media de las estrategias con y sin cada cualidad (más bajo = mejor).")
    R.bullets([
        f"**Amable** (no traicionar primero): puesto {num(q['Amables'][0])} frente a {num(q['Amables'][1])}. "
        "La diferencia más clara.",
        f"**Responde** (castigar la traición): {num(q['Responden'][0])} frente a {num(q['Responden'][1])}. Entre "
        f"las amables es aún más fuerte: las que se defienden quedan en el {num(C['amables_vengativas'][0])}; "
        f"las que no ({', '.join(C['amables_no_vengativas'])}), en el {num(C['amables_vengativas'][1])}.",
        f"**Perdona** (volver a cooperar tras castigar): {num(q['Perdonan'][0])} frente a {num(q['Perdonan'][1])}.",
        f"**Clara** (ser predecible): {num(q['Sin azar'][0])} frente a {num(q['Sin azar'][1])}. Aquí casi no hay "
        "diferencia. En nuestro simulador ser impredecible apenas penaliza; quizá porque nuestras estrategias "
        "aleatorias son pocas y sencillas.",
    ])
    R.vida_real("Es casi un manual de convivencia: **empieza confiando, no te dejes pisar, no guardes rencor y "
                "que se te entienda**. Es una moral de «ojo por ojo» suavizada, muy parecida a normas que "
                "aparecen en muchas culturas. Y nadie la ha diseñado: sale sola de las reglas del juego.")

    # ------------------------------------------------------------------ 7
    R.h1("7. ¿Depende de con quién te juntes?", "ligera")
    R.p("Hasta ahora todas jugaban contra todas. Pero ¿y si cambiamos el **entorno**? Tomamos 8 estrategias "
        "de referencia y las metemos en tres mundos: uno **amable** (rodeadas de estrategias que nunca "
        "traicionan primero), uno **mixto** (las 36) y uno **hostil** (rodeadas de traicioneras).")
    R.fig("f07_entornos", "Posición relativa de 8 estrategias en tres mundos (100 % = la primera; 0 % = la "
                          "última). Cuanto más larga la línea gris, más depende del entorno.")
    R.bullets([
        f"**AlwaysSteal** es la última en el mundo amable (puesto {num(e('AlwaysSteal', 0.0, 'amable'))} de "
        f"{C['entornos_n']['amable']}), pero en el hostil sube al {num(e('AlwaysSteal', 0.0, 'hostil'))} de "
        f"{C['entornos_n']['hostil']}, y con errores al {num(e('AlwaysSteal', 0.05, 'hostil'))}. Entre traidores, "
        "traicionar es casi lo normal.",
        f"**AlwaysSplit**, la santa, con errores es la {num(e('AlwaysSplit', 0.05, 'amable'), 0)}ª en el mundo "
        f"amable: entre buena gente, perdonarlo todo funciona. En el hostil cae al {num(e('AlwaysSplit', 0.05, 'hostil'))}.",
        f"**GrimTrigger**, la rencorosa, es de las mejores en el mundo amable sin errores "
        f"({num(e('GrimTrigger', 0.0, 'amable'))}ª), pero con errores cae al {num(e('GrimTrigger', 0.05, 'amable'))}: "
        "el rencor es letal entre amigos que se equivocan.",
        f"**Gradual** es la más todoterreno en los mundos duros: {num(e('Gradual', 0.0, 'hostil'))}ª en el hostil.",
    ])
    R.p("Esto encaja con lo que encontró Axelrod: una estrategia que habría ganado su primer torneo "
        "(Tit for Two Tats) quedó la 24ª en el segundo, porque los rivales habían cambiado. **No existe la "
        "estrategia perfecta: la mejor depende de con quién juegues.**")
    R.vida_real("La misma persona puede triunfar en un equipo y hundirse en otro. Ser muy confiado es una "
                "virtud en un entorno sano y un riesgo en uno tóxico. Antes de preguntarte «¿qué estrategia es "
                "la mejor?», pregúntate «¿con quién estoy jugando?». Y si puedes elegir tu entorno, elígelo bien.")

    # ------------------------------------------------------------------ 8
    R.h1("8. ¿Qué pasa cuando hay malentendidos?", "ligera")
    R.p("En la vida real hay errores: un mensaje que se malinterpreta, un despiste, alguien que quería "
        "ayudar y no pudo. En 1983 el sistema de alerta soviético confundió reflejos del sol en las nubes con "
        "misiles estadounidenses; un oficial, Stanislav Petrov, decidió que era un error. Para simularlo, "
        "hacemos que cada jugada salga al revés con una pequeña probabilidad.")
    p = C["parejas"]
    R.fig("f08_ruido_parejas", "Porcentaje de rondas en que ambos cooperan cuando una estrategia juega contra "
                               "una copia de sí misma, con 0 %, 1 % y 5 % de errores.")
    R.p(f"Con solo **un 1 % de errores**, dos TitForTat pasan de cooperar el 100 % del tiempo al "
        f"**{p['TitForTat|0.01']} %**, y dos GrimTrigger al **{p['GrimTrigger|0.01']} %**. ¿Por qué? Un error "
        "basta para que TitForTat responda con una traición, el otro le responda a él… y entran en una cadena "
        "de venganzas, un «eco» que solo otro error puede romper. GrimTrigger, peor: un error y no vuelve a "
        f"cooperar nunca. En cambio, Pavlov ({p['WinStayLoseShift|0.01']} %), GenerousTitForTat "
        f"({p['GenerousTitForTat|0.01']} %) y MimicMajority ({p['MimicMajority|0.01']} %) apenas lo notan: "
        "tienen una forma de volver a la paz.")
    R.fig("f09_ruido_torneo", "Posición media en el torneo según el porcentaje de errores (50 semillas por nivel).")
    cm = C["coop_media_por_ruido"]
    R.p(f"En el torneo completo, al subir los errores la cooperación media baja del {cm['0.0']} % al "
        f"{cm['0.1']} %, y AlwaysSteal sube del puesto {num(C['ruido_rank']['AlwaysSteal|0.0'])} al "
        f"{num(C['ruido_rank']['AlwaysSteal|0.1'])}. **Los malentendidos erosionan la ventaja de cooperar.**")
    R.vida_real("Muchos conflictos no empiezan por maldad, sino por un malentendido al que se responde con "
                "dureza, y la respuesta a la respuesta… En relaciones, empresas o países, las cadenas de "
                "represalias suelen tener un origen tonto. Lo que las corta no es tener razón: es que alguien "
                "dé un paso atrás.")

    # ------------------------------------------------------------------ 9
    R.h1("9. ¿Cuándo conviene perdonar? ¿Cuánto?", "ligera")
    R.p("Si los errores provocan cadenas de venganza, la solución parece ser perdonar. Pero ¿cuánto? Si "
        "perdonas demasiado, te explotan. Probamos una versión de TitForTat que perdona cada traición con una "
        "probabilidad **p**: desde 0 (nunca perdona, es TitForTat) hasta 1 (siempre perdona, es AlwaysSplit). "
        "La pusimos con 9 amables y 3 traicioneras, con y sin errores.")
    pr = C["perdon"]
    R.fig("f10_perdon", "Posición media de ForgivingTitForTat según cuánto perdona (p), sin errores y con un "
                        "5 % de errores. Las bandas son el margen de error.")
    R.table(["Perdona (p)", "0 (nunca)", "0,1", "0,2", "1/3", "0,5", "1 (siempre)"], [
        ["Sin errores"] + [num(pr[f"{k}|0.0"]) for k in ["0.0", "0.1", "0.2", "0.333333", "0.5", "1.0"]],
        ["5 % de errores"] + [num(pr[f"{k}|0.05"]) for k in ["0.0", "0.1", "0.2", "0.333333", "0.5", "1.0"]],
    ], widths=[3.4] + [2.17] * 6)
    R.p("El resultado: **lo mejor es perdonar poco, alrededor de 1 de cada 10 traiciones** (p = 0,1), con y "
        "sin errores. No perdonar nunca es algo peor, y perdonar mucho es claramente peor. Es justo el número "
        "que menciona el vídeo de Veritasium para romper los ecos: un 10 % de perdón.")
    a5 = C["alwayssteal_segun_perdon_ruido5"]
    R.p(f"Además, **el perdón tiene efectos sobre los demás**: con errores, cuanto más perdona esta estrategia, "
        f"mejor le va a AlwaysSteal (del puesto {num(a5['0.0'])} al {num(a5['1.0'])}). El perdón ilimitado "
        "alimenta a los aprovechados.")
    R.curiosos("La teoría (Nowak y Sigmund, 1992) dice que el perdón óptimo con estos puntos es 1/3. Pero ese "
               "1/3 es el perdón MÁXIMO que una población de «generosas» se puede permitir sin que un traidor "
               "la invada: es un techo, no el punto ideal. Con traidores presentes, cada perdón de más es un "
               "regalo. Matiz honesto: entre p = 0,1 y p = 0,2 la diferencia es pequeña y cae dentro del margen "
               "de error.")
    R.vida_real("Perdona, pero no a ciegas. Dar segundas oportunidades rompe espirales de conflicto; darlas "
                "siempre invita a que se aprovechen de ti (y de los demás).")

    # ------------------------------------------------------------------ 10
    R.h1("10. ¿Juzgar por el último gesto o por la trayectoria?", "ligera")
    R.p(f"Con un 5 % de errores, la gran ganadora es **MimicMajority**: gana el **{C['mimic_titulos_ruido5']} %** "
        "de los torneos. Su regla es sencilla: hace lo que el rival ha hecho **más veces** en todo el partido.")
    mm = C["memoria"]
    R.fig("f11_memoria", "Puntos por ronda contra una copia de sí misma y contra AlwaysSteal, con un 5 % de "
                         "errores.", width=14)
    R.p(f"La clave está en la memoria. TitForTat solo mira la **última** jugada: un error aislado desata la "
        f"venganza (contra sí misma saca {num(mm['TitForTat|misma'], 2)} puntos por ronda). MimicMajority mira "
        f"**toda la historia**: un error aislado no cambia la mayoría, así que lo ignora "
        f"({num(mm['MimicMajority|misma'], 2)} puntos, casi la cooperación perfecta). Pero si alguien traiciona "
        f"de forma constante, la mayoría sí cambia y castiga: contra AlwaysSteal no se deja explotar "
        f"({num(mm['MimicMajority|AlwaysSteal'], 2)} puntos, frente a {num(mm['WinStayLoseShift|AlwaysSteal'], 2)} "
        "de Pavlov, que cada dos rondas vuelve a confiar).")
    R.p(f"Un detalle importante: su gemela **HardMajority**, que empieza desconfiando, se hunde contra sí misma "
        f"({num(mm['HardMajority|misma'], 2)} puntos). Juzgar por la trayectoria funciona… si empiezas con buena fe.")
    R.vida_real("Juzgar a alguien por su último gesto es frágil cuando hay malentendidos. Juzgarlo por su "
                "trayectoria (su reputación) tolera los fallos puntuales y castiga los patrones. Es lo que "
                "hacemos con los amigos de verdad: un mal día no borra años de confianza.")

    # ------------------------------------------------------------------ 11
    R.h1("11. ¿Liga o todos contra todos?", "ligera")
    R.p("¿Importa cómo se organiza la competición? Mucho. Comparamos el formato de ligas con ascensos y "
        "descensos con un todos contra todos de toda la vida.")
    fm, fd = C["formatos_max_titulos"], C["formatos_campeones_distintos"]
    R.fig("f12_formatos", "Porcentaje de torneos ganados por cada estrategia en cada formato, con y sin errores "
                          "(50 semillas por variante).", width=14)
    R.bullets([
        f"**Todos contra todos, sin errores:** {fm['todos_contra_todos__noise=0'][0]} gana el "
        f"{fm['todos_contra_todos__noise=0'][1]} % de las veces. Hay una mejor clara.",
        f"**Ligas, sin errores:** ninguna pasa del {fm['ligas__noise=0'][1]} % y {fd['ligas__noise=0']} "
        "estrategias distintas ganan algún título. El campeón es casi una lotería.",
        f"**Con errores:** en todos contra todos domina {fm['todos_contra_todos__noise=0.05'][0]} "
        f"({fm['todos_contra_todos__noise=0.05'][1]} %), que en ligas no gana ni un título; en ligas manda "
        f"{fm['ligas__noise=0.05'][0]} ({fm['ligas__noise=0.05'][1]} %).",
    ])
    R.h2("La lotería de la élite")
    R.p("¿Por qué en ligas el título es una lotería? Porque en la Liga 1 se juntan las cooperadoras, y entre "
        "ellas cooperan siempre: empatan en **todo**, en puntos, en el enfrentamiento directo y en la diferencia "
        f"de puntos. El desempate final es un sorteo. Sin errores, el **{C['sorteo_liga1']['0.0']} %** de los "
        f"descensos de la Liga 1 se decide por sorteo. Con un 5 % de errores, el **{C['sorteo_liga1']['0.05']} %**: "
        "los errores separan a las que se recuperan bien de las que no.")
    R.fig("f14_sorteo", "Qué criterio decide quién baja de la Liga 1, sin errores y con un 5 % de errores.", width=13)
    R.h2("El ascensor de las traicioneras")
    R.p("Las traicioneras viven en un ascensor. Suben desde las ligas de abajo, donde hay ingenuas a las que "
        "explotar; al llegar a la zona media se encuentran con estrategias que se defienden, y bajan. Y vuelta a empezar:")
    R.fig("f13_ascensor", "Liga de cuatro estrategias temporada a temporada en un torneo (semilla 42).", width=14)
    R.vida_real("Las reglas de la competición deciden quién gana tanto como los competidores. Un sistema de "
                "ascensos premia ganar a los de tu nivel; un todos contra todos premia ser bueno contra todos. Y "
                "el aprovechado prospera donde hay ingenuos, pero choca con un techo donde la gente sabe defenderse.")

    # ------------------------------------------------------------------ 12
    R.h1("12. ¿Y si traicionar tienta más?", "ligera")
    R.p("Hasta ahora, traicionar a quien coopera daba 5 puntos. ¿Qué pasa si da 4, 6 u 8? Es como subir o bajar "
        "la tentación.")
    tt = C["tentacion"]
    R.fig("f15_tentacion", "Posición media según los puntos por traicionar a quien coopera (T). Lo normal es T = 5.")
    R.p(f"Con mucha tentación (T = 8), **TitForTat** sube al puesto **{num(tt['TitForTat|8'])}** de media y "
        f"**MimicMajority** se hunde al **{num(tt['MimicMajority|8'])}** (con T = 4 era el "
        f"{num(tt['MimicMajority|4'])}). La razón: cuanto más vale una traición, más caro sale tardar en "
        "responderla. TitForTat responde en la ronda siguiente; MimicMajority necesita que las traiciones sean "
        "mayoría antes de castigar. **La virtud que la hacía campeona con errores (tolerar) es un defecto cuando "
        "la tentación es grande.**")
    R.vida_real("Donde hay mucho que ganar traicionando (mucho dinero en juego, poca vigilancia), conviene "
                "responder rápido a los abusos. Donde lo que más hay son malentendidos, conviene ser tolerante. "
                "No hay una estrategia buena en abstracto: depende del entorno.")

    # ------------------------------------------------------------------ 13
    R.h1("13. ¿Puede la cooperación conquistar un mundo egoísta?", "ligera")
    R.p("Ahora cambiamos de escala. Imagina una población enorme con muchas jugadoras de cada estrategia. Cada "
        "generación, las estrategias que más puntúan **se multiplican** y las que menos **desaparecen**. Es lo "
        "que hizo Axelrod para ver qué estrategias sobrevivirían a largo plazo.")
    ev0, ev5 = C["evo_sin_ruido"], C["evo_ruido5"]
    R.fig("f16_evo_tipos", "Cuota de la población de amables, traicioneras y otras, generación a generación. "
                           "Empiezan las 36 a partes iguales.")
    R.p(f"Sin errores, en unas 40 generaciones las traicioneras son prácticamente cero: al final sobreviven "
        f"**{ev0['supervivientes']} estrategias y todas son amables**. Con un 5 % de errores tardan mucho más, "
        f"pero al final las amables son el **{num(ev5['amables'])} %**, y las que dominan son perdonadoras "
        f"(ProbTitForTat, ForgivingTitForTat, GenerousTitForTat).")
    R.fig("f20_evo_supervivientes", "Las 10 estrategias más abundantes al final de la simulación.")
    R.h2("Auge y caída de las depredadoras")
    ad, al = C["depredadora_adaptive"], C["depredadora_alternator"]
    R.p(f"Algunas traicioneras viven un momento de gloria. **Adaptive**, que aprende a explotar a quien se deja, "
        f"crece del {num(ad['inicio'])} % al {num(ad['pico'])} % en las primeras generaciones… y se extingue en "
        f"la generación {ad['extinta_gen']}. Con errores, **Alternator** llega al **{num(al['pico'])} %** de la "
        f"población antes de desplomarse. Crecen mientras tienen víctimas; cuando las víctimas desaparecen, "
        "se quedan sin comida.")
    R.fig("f17_evo_depredadoras", "Cuota de la población de dos traicioneras a lo largo de las generaciones.")
    R.h2("La masa crítica")
    R.p(f"La prueba definitiva: un mundo con un **98 % de AlwaysSteal** y solo un **2 % de TitForTat**. En "
        f"{C['invasion_gen_50pct']} generaciones las cooperadoras ya son mayoría y en {C['invasion_gen_99pct']} "
        "lo son casi todo. ¿Cómo? Cuando dos TitForTat se encuentran, ganan 3 puntos por ronda; cuando se cruzan "
        "con un egoísta, apenas pierden nada. Los egoístas, entre ellos, solo sacan 1.")
    R.fig("f18_evo_invasion", "Evolución de una población que empieza con 98 % de AlwaysSteal y 2 % de TitForTat.")
    R.p(f"Y no hace falta ni un 2 %: basta con superar una **masa crítica de alrededor del "
        f"{num(C['masa_critica_pct'], 2)} %**. Por debajo, las cooperadoras se encuentran demasiado poco entre "
        "ellas y desaparecen; por encima, conquistan el mundo.")
    R.fig("f19_masa_critica", "Cuota final de TitForTat según con cuánto empieza (el resto, AlwaysSteal).")
    R.curiosos("Es una simulación «ecológica»: no hay mutaciones, solo selección. Se calcula una matriz con los "
               "puntos medios por ronda de cada estrategia contra cada otra (incluida contra sí misma, 20 partidos "
               "por pareja) y en cada generación la cuota de cada estrategia se multiplica por sus puntos medios "
               "frente a la población, dividida por la media de todas (dinámica del replicador). La población está "
               "«bien mezclada»: cada una se cruza con todas en proporción a su cuota. En la vida real los grupos "
               "suelen estar más agrupados, lo que haría la cooperación aún más fácil.")
    R.vida_real("No hace falta que todo el mundo sea bueno para que la cooperación gane. Basta con un grupo "
                "pequeño de gente que coopere entre sí y se defienda de los abusos. Así es como pueden surgir la "
                "confianza en una empresa, las normas de un barrio o, según algunos biólogos, la cooperación entre "
                "animales: sin que nadie la imponga, solo porque funciona mejor.")

    # ------------------------------------------------------------------ 14
    R.h1("14. Lecciones para la vida real", "ligera")
    R.p("Si hubiera que resumir todo el proyecto en una lista, sería esta:")
    R.numbered([
        "**Empieza confiando.** Las amables ganan de media, y de largo.",
        "**No te dejes pisar.** Ser bueno sin defenderte te convierte en la víctima favorita.",
        "**Perdona, pero poco.** Romper las cadenas de venganza vale la pena; perdonar siempre, no.",
        "**Juzga por la trayectoria, no por el último gesto**, sobre todo cuando hay malentendidos.",
        "**Mira con quién juegas.** La mejor estrategia depende del entorno. Si puedes, elige bien tu entorno.",
        "**No necesitas ganar a nadie para ganar.** La vida casi nunca es de suma cero: busca acuerdos donde ganéis los dos.",
        "**Las reglas importan.** El formato de la competición decide quién gana tanto como los jugadores.",
        "**Unos pocos pueden cambiar el sistema.** Un pequeño grupo de cooperadores puede imponerse en un mundo de egoístas.",
    ])
    R.p("Un último ejemplo del vídeo de Veritasium: EE. UU. y la URSS no se desarmaron con un único gran "
        "acuerdo (eso habría sido una sola partida, donde traicionar es tentador), sino **poco a poco**: unas "
        "pocas armas cada año, comprobando que el otro también cumplía, y repitiendo al año siguiente. "
        "Convirtieron un dilema de una vez en un juego repetido. Esa es, quizá, la lección más práctica de todas.")

    # ------------------------------------------------------------------ 15
    R.h1("15. Límites del estudio y próximos pasos", "tecnica")
    R.bullets([
        "**Las estrategias las he elegido yo.** Con otro conjunto de rivales, los resultados cambiarían (es, de "
        "hecho, una de las conclusiones).",
        "**Los partidos duran siempre 100 rondas**, aunque las estrategias no lo saben. En la vida real no sabes "
        "cuándo será la última vez.",
        "**Solo hay errores de ejecución** (hacer lo contrario de lo que querías), no de percepción (ver mal lo "
        "que hizo el otro).",
        "**La evolución no tiene mutaciones ni espacio**: no aparecen estrategias nuevas y todo el mundo se cruza "
        "con todo el mundo.",
        "**Cincuenta repeticiones** dan márgenes de error pequeños, pero algunas diferencias (por ejemplo, perdonar "
        "un 10 % o un 20 %) quedan dentro de ese margen.",
    ])
    R.p("Próximos pasos posibles: partidos de duración aleatoria, errores de percepción, evolución con "
        "mutaciones, poblaciones en un espacio (vecindarios), torneos con estrategias propuestas por otras "
        "personas y una pequeña interfaz gráfica para jugar con el simulador sin programar.")

    # ------------------------------------------------------------------ anexo
    R.h1("Anexo: cómo reproducir cada resultado", "tecnica")
    R.p("Todo se puede regenerar desde el repositorio. Con el entorno instalado (ver la guía de usuario, "
        "`docs/GUIA_USUARIO.md`):")
    R.table(["Resultado", "Comando"], [
        ["Torneo de referencia", "split-steal tournament --name canonical --out-dir results"],
        ["Ruido (sección 8)", "split-steal experiment experiments/ruido.toml"],
        ["Perdón (sección 9)", "split-steal experiment experiments/perdon_optimo.toml"],
        ["Formatos (sección 11)", "split-steal experiment experiments/formatos.toml"],
        ["Tentación (sección 12)", "split-steal experiment experiments/tentacion.toml"],
        ["Entornos (sección 7)", "split-steal experiment experiments/entornos.toml"],
        ["Evolución (sección 13)", 'split-steal evolve --initial "AlwaysSteal=0.98,TitForTat=0.02"'],
        ["Gráficas y cifras del informe", "ejecutar notebooks/03_informe.ipynb"],
        ["Este documento", "python docs/informe/build_informe.py"],
    ], widths=[5.0, 11.4])

    R.h1("Referencias")
    R.bullets([
        "Axelrod, R. (1980). «Effective Choice in the Prisoner's Dilemma». Journal of Conflict Resolution, 24(1).",
        "Axelrod, R. (1984). The Evolution of Cooperation. Basic Books.",
        "Nowak, M. y Sigmund, K. (1992). «Tit for tat in heterogeneous populations». Nature, 355.",
        "Nowak, M. y Sigmund, K. (1993). «A strategy of win-stay, lose-shift that outperforms tit-for-tat in "
        "the Prisoner's Dilemma game». Nature, 364.",
        "Beaufils, B., Delahaye, J.-P. y Mathieu, P. (1996). «Our Meeting with Gradual: A Good Strategy for the "
        "Iterated Prisoner's Dilemma». Artificial Life V.",
        "Press, W. H. y Dyson, F. J. (2012). «Iterated Prisoner's Dilemma contains strategies that dominate any "
        "evolutionary opponent». PNAS, 109(26).",
        "Veritasium (2023). «What Game Theory Reveals About Life, The Universe, and Everything» [vídeo]. YouTube.",
    ])
    return R.save()


if __name__ == "__main__":
    print(f"Informe guardado en {build()}")
