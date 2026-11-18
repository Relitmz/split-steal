"""
Personajes en pixel art para el informe: uno por estrategia del roster oficial.

Cada personaje es el mismo muñeco (cuerpo crema con contorno negro) y lo que cambia es
lo que dice su personalidad: el accesorio (sombrero, gafas, antifaz...) y la cara
(sonrisa, ceño fruncido, sonrisa pícara...). Se dibujan píxel a píxel en una rejilla
pequeña (32 x 40) y se amplían sin suavizar, con fondo azul y líneas de "pantalla antigua".

    python docs/informe/personajes.py      -> docs/informe/figs/personajes/*.png y portada.png

Solo usa Pillow (viene con matplotlib).
"""

from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
OUT = HERE / "figs" / "personajes"

W, H = 32, 40           # rejilla de píxeles
SCALE = 8               # cada píxel -> 8 x 8
BG = (143, 206, 232)
BG_LINE = (128, 192, 220)
INK = (20, 20, 20)
SKIN = (255, 248, 220)
SHADOW = (98, 160, 190)

# Colores de accesorios
RED, DRED = (214, 58, 52), (150, 34, 40)
BLUE, DBLUE = (44, 110, 200), (28, 70, 140)
GREEN, DGREEN = (60, 170, 80), (30, 110, 50)
YELLOW, GOLD = (250, 210, 60), (230, 170, 30)
PURPLE = (130, 80, 190)
BROWN, DBROWN = (160, 100, 55), (110, 65, 35)
GREY, DGREY = (170, 170, 170), (90, 90, 90)
WHITE, BLACK = (250, 250, 250), (30, 30, 30)
ORANGE, PINK = (240, 130, 40), (240, 120, 160)


class Pix:
    """Pequeño lienzo de píxeles con primitivas cómodas."""

    def __init__(self):
        self.img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        self.d = ImageDraw.Draw(self.img)

    def p(self, x, y, c):
        if 0 <= x < W and 0 <= y < H:
            self.d.point((x, y), fill=c)

    def r(self, x0, y0, x1, y1, c):
        self.d.rectangle([x0, y0, x1, y1], fill=c)

    def box(self, x0, y0, x1, y1, c):
        """Rectángulo relleno con contorno negro."""
        self.d.rectangle([x0, y0, x1, y1], fill=c, outline=INK)

    def ell(self, x0, y0, x1, y1, c, outline=INK):
        self.d.ellipse([x0, y0, x1, y1], fill=c, outline=outline)


# =============================================================================
# El muñeco base
# =============================================================================

def body(c: Pix):
    c.ell(9, 28 + 9, 23, 30 + 9, None, outline=None)          # (sombra: se pinta aparte)
    # piernas
    c.box(12, 30, 15, 38, SKIN)
    c.box(17, 30, 20, 38, SKIN)
    # brazos
    c.box(8, 21, 10, 29, SKIN)
    c.box(22, 21, 24, 29, SKIN)
    # tronco
    c.box(10, 20, 22, 31, SKIN)
    c.r(11, 30, 21, 30, SKIN)
    # cabeza
    c.ell(9, 7, 23, 21, SKIN)


def face(c: Pix, mood="smile"):
    """Ojos y boca. moods: smile, big, neutral, frown, angry, smirk, sly, calm, worried."""
    eyes = {"sly": [(13, 14), (14, 14), (18, 14), (19, 14)],
            "calm": [(13, 14), (14, 14), (18, 14), (19, 14)]}
    for x, y in eyes.get(mood, [(13, 13), (13, 14), (19, 13), (19, 14)]):
        c.p(x, y, INK)
    if mood in ("angry", "sly"):
        for x, y in [(12, 11), (13, 12), (14, 12), (20, 11), (19, 12), (18, 12)]:
            c.p(x, y, INK)
    if mood == "worried":
        for x, y in [(12, 12), (13, 11), (20, 12), (19, 11)]:
            c.p(x, y, INK)
    mouths = {
        "smile": [(14, 17), (15, 18), (16, 18), (17, 18), (18, 17)],
        "big": [(13, 17), (14, 18), (15, 18), (16, 18), (17, 18), (18, 18), (19, 17), (15, 17), (16, 17), (17, 17)],
        "neutral": [(14, 18), (15, 18), (16, 18), (17, 18), (18, 18)],
        "frown": [(14, 19), (15, 18), (16, 18), (17, 18), (18, 19)],
        "angry": [(14, 19), (15, 18), (16, 18), (17, 18), (18, 19)],
        "smirk": [(14, 18), (15, 18), (16, 18), (17, 18), (18, 17)],
        "sly": [(14, 18), (15, 18), (16, 18), (17, 18), (18, 17), (19, 16)],
        "calm": [(15, 18), (16, 18), (17, 18)],
        "worried": [(14, 18), (15, 17), (16, 18), (17, 17), (18, 18)],
    }
    for x, y in mouths[mood]:
        c.p(x, y, INK)


# =============================================================================
# Accesorios
# =============================================================================

def cap(c, color, visor="right"):
    c.box(10, 5, 22, 9, color)
    c.r(11, 6, 21, 8, color)
    if visor == "right":
        c.box(21, 8, 27, 9, color)
    else:
        c.box(5, 8, 11, 9, color)


def beanie(c, color, pom=None, pattern=None):
    c.box(9, 4, 23, 10, color)
    c.r(10, 3, 22, 4, color)
    c.r(9, 9, 23, 10, tuple(max(0, v - 40) for v in color))
    if pom:
        c.ell(14, 0, 18, 4, pom)
    if pattern:
        for x, y in pattern:
            c.p(x, y, YELLOW)


def bowler(c, color):
    c.ell(11, 2, 21, 10, color)
    c.box(7, 8, 25, 9, color)


def tophat(c, color, band):
    c.box(11, 0, 21, 8, color)
    c.r(12, 6, 20, 7, band)
    c.box(7, 8, 25, 9, color)


def halo(c):
    c.d.ellipse([10, 1, 22, 5], outline=GOLD)
    c.d.ellipse([11, 2, 21, 4], outline=YELLOW)


def mask(c, color, y=12):
    c.box(9, y, 23, y + 3, color)
    c.r(12, y + 1, 14, y + 2, SKIN)
    c.r(18, y + 1, 20, y + 2, SKIN)
    c.p(13, y + 1, INK)
    c.p(19, y + 1, INK)


def glasses(c, color, sun=False):
    for x0 in (11, 17):
        c.box(x0, 12, x0 + 4, 15, BLACK if sun else SKIN)
        c.d.rectangle([x0, 12, x0 + 4, 15], outline=color)
    c.r(15, 13, 17, 13, color)


def round_glasses(c):
    for x0 in (10, 17):
        c.d.ellipse([x0, 11, x0 + 5, 16], outline=INK)
    c.r(15, 13, 17, 13, INK)
    c.p(13, 14, INK)
    c.p(20, 14, INK)


def headband(c, color, stripes=0, knot=False):
    c.box(9, 9, 23, 11, color)
    for k in range(stripes):
        c.r(12 + 3 * k, 10, 12 + 3 * k, 10, WHITE)
    if knot:
        c.box(23, 10, 26, 11, color)
        c.box(24, 12, 27, 13, color)


def wig(c, color):
    for x, y in [(8, 9), (8, 13), (8, 17), (24, 9), (24, 13), (24, 17)]:
        c.ell(x - 2, y - 2, x + 2, y + 2, color)
    c.ell(9, 3, 23, 11, color)
    for x in (11, 15, 19):
        c.ell(x - 2, 2, x + 2, 6, color)


def mortarboard(c):
    c.box(10, 5, 22, 9, BLACK)
    c.d.polygon([(6, 5), (16, 1), (26, 5), (16, 8)], fill=BLACK, outline=INK)
    c.r(24, 5, 24, 10, YELLOW)
    c.r(23, 10, 25, 11, YELLOW)


def fez(c):
    c.box(12, 2, 20, 9, RED)
    c.r(16, 0, 16, 2, BLACK)
    c.r(16, 2, 21, 2, BLACK)
    c.r(21, 2, 21, 5, GOLD)


def wizard(c):
    c.d.polygon([(16, 0), (10, 9), (22, 9)], fill=PURPLE, outline=INK)
    c.box(7, 8, 25, 9, PURPLE)
    for x, y in [(15, 4), (17, 6), (13, 7)]:
        c.p(x, y, YELLOW)


def propeller(c):
    cap(c, YELLOW)
    c.r(16, 1, 16, 4, BLACK)
    c.r(12, 1, 15, 1, RED)
    c.r(17, 1, 20, 1, BLUE)


def antenna(c):
    headband(c, GREY)
    for x in (12, 20):
        c.r(x, 3, x, 8, DGREY)
        c.ell(x - 1, 1, x + 1, 3, RED)


def cat_ears(c, color):
    for pts in ([(9, 10), (10, 2), (15, 8)], [(23, 10), (22, 2), (17, 8)]):
        c.d.polygon(pts, fill=color, outline=INK)
    c.p(11, 6, PINK)
    c.p(21, 6, PINK)


def headphones(c):
    c.d.arc([9, 3, 23, 17], 180, 360, fill=BLACK)
    c.box(7, 12, 9, 17, RED)
    c.box(23, 12, 25, 17, RED)


def deerstalker(c):
    c.ell(9, 3, 23, 11, BROWN)
    for x in range(10, 23, 3):
        c.r(x, 5, x, 9, DBROWN)
    c.box(5, 8, 11, 10, BROWN)
    c.box(21, 8, 27, 10, BROWN)


def helmet(c):
    c.ell(9, 3, 23, 15, WHITE)
    c.box(10, 11, 22, 13, (120, 190, 230))


def punk(c):
    for k, x in enumerate(range(10, 23, 3)):
        c.d.polygon([(x, 9), (x + 1, 1 + (k % 2) * 2), (x + 3, 9)], fill=RED, outline=INK)


def beret(c, color):
    c.ell(8, 3, 22, 9, color)
    c.r(15, 1, 15, 3, BLACK)


def bucket(c, color):
    c.box(11, 3, 21, 8, color)
    c.d.polygon([(7, 10), (11, 7), (21, 7), (25, 10)], fill=color, outline=INK)


def boxing(c):
    c.d.ellipse([8, 4, 24, 22], outline=RED, width=2)
    c.box(9, 4, 23, 9, RED)
    c.box(8, 13, 10, 18, RED)
    c.box(22, 13, 24, 18, RED)


def mustache(c, villain=False):
    c.r(13, 16, 19, 16, BLACK)
    c.p(12, 17, BLACK)
    c.p(20, 17, BLACK)
    if villain:
        c.p(11, 16, BLACK)
        c.p(21, 16, BLACK)
        c.p(11, 15, BLACK)
        c.p(21, 15, BLACK)


def cape(c, color):
    c.d.polygon([(10, 20), (6, 33), (26, 33), (22, 20)], fill=color, outline=INK)


def heart(c, color=RED, big=False):
    pts = [(14, 23), (15, 23), (17, 23), (18, 23), (14, 24), (15, 24), (16, 24), (17, 24), (18, 24),
           (15, 25), (16, 25), (17, 25), (16, 26)]
    for x, y in pts:
        c.p(x, y, color)


def scarf(c, color):
    c.box(10, 19, 22, 21, color)
    c.box(18, 21, 20, 26, color)


def bandage(c):
    c.box(18, 8, 23, 10, WHITE)
    c.r(20, 9, 21, 9, PINK)


def question(c):
    for x, y in [(25, 1), (26, 0), (27, 0), (28, 1), (28, 2), (27, 3), (26, 4), (26, 6)]:
        c.p(x, y, WHITE)


def bulb(c):
    c.ell(13, -1, 19, 5, YELLOW)
    c.box(14, 5, 18, 6, GREY)
    for x, y in [(11, 0), (21, 0), (10, 3), (22, 3)]:
        c.p(x, y, YELLOW)


def goggles(c):
    c.r(9, 7, 23, 8, BROWN)
    c.ell(11, 5, 15, 9, (120, 190, 230))
    c.ell(17, 5, 21, 9, (120, 190, 230))


def white_hair(c):
    for x, y in [(9, 9), (23, 9), (8, 12), (24, 12)]:
        c.ell(x - 1, y - 1, x + 1, y + 1, WHITE)


def dice_on_cap(c):
    cap(c, BLUE)
    c.box(14, 1, 18, 5, WHITE)
    c.p(15, 2, BLACK)
    c.p(17, 4, BLACK)


def yin_yang(c):
    c.box(9, 4, 23, 10, WHITE)
    c.r(16, 4, 23, 10, BLACK)
    c.r(10, 3, 22, 4, WHITE)
    c.r(16, 3, 22, 4, BLACK)
    c.d.rectangle([9, 3, 23, 10], outline=INK)


def mask_up(c):
    mask(c, BLACK, y=6)


def rainbow_beanie(c):
    beanie(c, ORANGE, pom=PINK)
    for k, col in enumerate([RED, YELLOW, GREEN, BLUE]):
        c.r(10 + 3 * k, 6, 12 + 3 * k, 7, col)


# =============================================================================
# Reparto: estrategia -> (apodo, cómo juega, cara, accesorios)
# =============================================================================

CHARACTERS = {
    # ---- amables
    "AlwaysSplit": ("La santa", "Coopera siempre, pase lo que pase.", "big", [halo]),
    "TitForTat": ("La justa", "Empieza cooperando y después copia lo último que hizo el rival.", "smile",
                  [lambda c: cap(c, BLUE)]),
    "GrimTrigger": ("La rencorosa", "Coopera hasta la primera traición. Después, nunca más.", "angry",
                    [lambda c: bowler(c, BLACK)]),
    "WinStayLoseShift": ("La pragmática (Pavlov)", "Si le fue bien, repite; si le fue mal, cambia.", "smile",
                         [white_hair, goggles]),
    "TwoTitsForTat": ("La boxeadora", "Si le roban, devuelve dos golpes.", "angry", [boxing]),
    "ForgivingTitForTat": ("La justa con margen", "Como TitForTat, pero perdona 1 de cada 10 traiciones.",
                           "smile", [lambda c: cap(c, DBLUE), heart]),
    "GenerousTitForTat": ("La generosa", "Como TitForTat, pero perdona 1 de cada 3 traiciones.", "big",
                          [lambda c: cap(c, GREEN), lambda c: scarf(c, GREEN)]),
    "MimicMajority": ("La jueza", "Hace lo que el rival ha hecho más veces en todo el partido.", "calm",
                      [lambda c: wig(c, WHITE)]),
    "ProbTitForTat": ("La justa a ratos", "Copia al rival el 80 % de las veces; si no, coopera.", "smile",
                      [dice_on_cap]),
    "ForgiveAfter3": ("La de los tres castigos", "Si le roban, castiga 3 rondas y luego perdona.", "neutral",
                      [lambda c: headband(c, DBLUE, stripes=3)]),
    "RandomAfterLoss": ("La desconcertada", "Coopera, pero tras ser traicionada responde al azar.", "worried",
                        [bandage, question]),
    "Mirror2Rounds": ("La paciente", "Solo castiga dos traiciones seguidas (Tit for Two Tats).", "calm",
                      [round_glasses]),
    "CautiousStart": ("La prudente", "Si el rival roba en las dos primeras rondas, no vuelve a cooperar.",
                      "neutral", [helmet]),
    "CopycatDelayed": ("La imitadora lenta", "Copia lo que hizo el rival hace dos rondas.", "smile",
                       [lambda c: cat_ears(c, GREY)]),
    "SplitUntilBetrayedTwice": ("La de los dos avisos", "Aguanta una traición; a la segunda, roba para siempre.",
                                "neutral", [lambda c: bucket(c, DGREEN)]),
    "RevengeMode": ("La vengadora", "Si le roban dos veces seguidas, se venga durante tres rondas.", "angry",
                    [lambda c: headband(c, RED, knot=True)]),
    "ConditionalRandom": ("La indecisa", "Coopera, pero tras un robo lanza una moneda al aire.", "worried",
                          [wizard]),
    "Gradual": ("La escalonada", "Castiga más cuanto más reincide el rival, y luego ofrece la paz.", "smile",
                [mortarboard]),
    # ---- otras (azar)
    "RandomP": ("La moneda al aire", "Coopera o roba al 50 %, sin mirar al rival.", "big", [propeller]),
    "RandomCycle": ("La de los ritmos", "Sortea un patrón de 3 jugadas y lo repite en bucle.", "smile",
                    [rainbow_beanie]),
    "NoisyTitForTat": ("La despistada", "TitForTat, pero se equivoca el 5 % de las veces.", "worried",
                       [headphones]),
    # ---- traicioneras
    "AlwaysSteal": ("El ladrón", "Traiciona siempre.", "smirk",
                    [lambda c: beanie(c, BLACK), lambda c: mask(c, BLACK)]),
    "Alternator": ("La de una sí, una no", "Alterna cooperar y robar, ronda a ronda.", "neutral", [yin_yang]),
    "AlwaysOpposite": ("La llevacontrarias", "Hace justo lo contrario de lo que hizo el rival.", "smirk",
                       [lambda c: cap(c, RED, visor="left")]),
    "FirstStealThenSplit": ("La arrepentida", "Roba en la primera ronda y luego coopera siempre.", "worried",
                            [mask_up]),
    "SplitEvery4": ("La tacaña", "Solo coopera una de cada cuatro rondas.", "frown",
                    [lambda c: beanie(c, PURPLE, pattern=[(11, 6), (14, 8), (17, 6), (20, 8)])]),
    "DoubleStealStart": ("La que entra fuerte", "Roba las dos primeras rondas y luego copia al rival.", "angry",
                         [punk]),
    "BackstabAfter10": ("La traidora tardía", "Coopera 10 rondas para ganarse tu confianza… y luego roba siempre.",
                        "sly", [lambda c: cape(c, PURPLE), lambda c: mustache(c, villain=True)]),
    "GreedyStart": ("La codiciosa", "Roba las 3 primeras rondas; si no te defiendes, te explota.", "sly",
                    [lambda c: tophat(c, BLACK, GREEN)]),
    "EveryThirdSplit": ("La de cada tercera", "Solo coopera una de cada tres rondas.", "neutral", [fez]),
    "SplitSplitSteal": ("La de dos y una", "Coopera dos rondas y roba la tercera, en bucle.", "smirk",
                        [lambda c: beret(c, DRED)]),
    "SuspiciousTitForTat": ("La desconfiada", "Empieza robando y luego copia al rival.", "sly", [deerstalker]),
    "Prober": ("La sonda", "Tantea con un robo; si no respondes, te explota.", "smirk", [antenna]),
    "Joss": ("La sigilosa", "Parece TitForTat, pero roba por sorpresa el 10 % de las veces.", "smirk",
             [lambda c: glasses(c, BLACK, sun=True)]),
    "Adaptive": ("La que aprende", "Prueba las dos jugadas y se queda con la que más le da.", "neutral", [bulb]),
    "HardMajority": ("La jueza severa", "Como la jueza, pero empieza robando y en caso de empate roba.",
                     "frown", [lambda c: wig(c, DGREY)]),
}

# Accesorios que van DETRÁS del cuerpo (la capa)
BEHIND = {"BackstabAfter10"}


def render(name: str, scale: int = SCALE) -> Image.Image:
    """Dibuja el personaje de `name` y lo devuelve ampliado sobre el fondo azul."""
    _, _, mood, extras = CHARACTERS[name]
    c = Pix()
    if name in BEHIND:
        extras[0](c)
    body(c)
    face(c, mood)
    for i, draw in enumerate(extras):
        if name in BEHIND and i == 0:
            continue
        draw(c)
    big = c.img.resize((W * scale, H * scale), Image.NEAREST)
    bg = Image.new("RGB", big.size, BG)
    d = ImageDraw.Draw(bg)
    for y in range(0, big.size[1], 4):                     # líneas de "pantalla"
        d.line([(0, y), (big.size[0], y)], fill=BG_LINE)
    d.ellipse([9 * scale, 37 * scale, 23 * scale, 40 * scale - 2], fill=SHADOW)   # sombra
    bg.paste(big, (0, 0), big)
    return bg


def portada(names, path):
    """Fila de personajes para la portada."""
    tiles = [render(n, scale=6) for n in names]
    w, h = tiles[0].size
    gap = 6
    sheet = Image.new("RGB", (len(tiles) * w + (len(tiles) - 1) * gap, h), (255, 255, 255))
    for i, t in enumerate(tiles):
        sheet.paste(t, (i * (w + gap), 0))
    sheet.save(path)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for name in CHARACTERS:
        render(name).save(OUT / f"{name}.png")
    portada(["AlwaysSplit", "TitForTat", "MimicMajority", "Gradual", "GrimTrigger",
             "Joss", "AlwaysSteal"], HERE / "figs" / "portada.png")
    print(f"{len(CHARACTERS)} personajes en {OUT}")


if __name__ == "__main__":
    main()
