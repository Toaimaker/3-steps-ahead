"""Le icone dei pulsanti dell'app, disegnate da noi (Autore, 14 nov 2026: lo stile S3 dei pulsanti, col blocco icona a sinistra, e «Disegnale tu» al posto
di un set di terzi). Ogni icona e' un tratto a un colore solo su una griglia di 24 unita', come i set a contorno (tratto di 2 unita', estremi tondi), disegnata
con disegni.Disegno a 4x e ridotta col Lanczos: nitida a ogni misura.

    icona(nome, lato, colore)   -> PhotoImage (in cache per nome, misura e colore), None se il nome non c'e'
    per_testo(testo)            -> il nome dell'icona che va col testo di un pulsante («Save», «Delete», «Export ▾»...), None se nessuna
    NOMI                        i nomi disegnati

    py -I -X utf8 Companion/App/Comune/icone_pulsanti.py --prova     ogni icona disegnata e non vuota, il testo -> icona, le negative
    py -I -X utf8 Companion/App/Comune/icone_pulsanti.py --foglio F  tutte le icone su un foglio png (per guardarle)
"""
import os, sys, math, re
_casa = os.path.dirname(os.path.abspath(__file__))
while not os.path.isfile(os.path.join(_casa, "percorsi.py")):
    _casa = os.path.dirname(_casa)
if _casa not in sys.path:
    sys.path.insert(0, _casa)
import percorsi  # noqa: E402,F401
import disegni as DG  # noqa: E402


class _Penna:
    """Le forme in unita' della griglia 24 x 24, su un Disegno di lato pixel."""

    def __init__(self, lato, colore):
        self.d, self.k, self.col = DG.Disegno(lato, lato), lato / 24, colore
        self.lw = max(1.25, 2 * self.k)

    def p(self, pts):
        return [(x * self.k, y * self.k) for x, y in pts]

    def L(self, *pts):
        self.d.linea(self.p(pts), self.col, self.lw)

    def R(self, x0, y0, x1, y1, r=2.0):
        k = self.k
        self.d.rett(x0 * k, y0 * k, x1 * k, y1 * k, bordo=self.col, larghezza=self.lw, raggio=r * k)

    def C(self, cx, cy, r, pieno=False):
        k = self.k
        if pieno:
            self.d.cerchio(cx * k, cy * k, r * k, riempi=self.col)
        else:
            self.d.cerchio(cx * k, cy * k, r * k, bordo=self.col, larghezza=self.lw)


def _cuore(P):
    pts = []
    for i in range(61):
        t = 2 * math.pi * i / 60
        x = 16 * math.sin(t) ** 3
        y = -(13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t))
        pts.append((12 + x * 0.52, 12.6 + y * 0.52))
    P.L(*pts)


def _stella(P):
    pts = []
    for i in range(11):
        a = -math.pi / 2 + i * math.pi / 5
        r = 8.8 if i % 2 == 0 else 3.9
        pts.append((12 + r * math.cos(a), 12.8 + r * math.sin(a)))
    P.L(*pts)


def _occhio(P):
    alto, basso = [], []
    for i in range(25):
        x = 2.5 + 19 * i / 24
        h = 6.2 * (1 - ((x - 12) / 9.5) ** 2)
        alto.append((x, 12 - h)); basso.append((x, 12 + h))
    P.L(*(alto + basso[::-1] + [alto[0]]))
    P.C(12, 12, 2.8)


def _goccia(P):
    pts = [(12, 3)]
    for i in range(0, 47):
        a = math.radians(-28 + i * 236 / 46)
        pts.append((12 + 5.8 * math.cos(a), 14.6 + 5.8 * math.sin(a)))
    pts.append((12, 3))
    P.L(*pts)


def _ingranaggio(P):
    """Otto denti col dorso piatto intorno al foro."""
    pts = []
    for i in range(8):
        a = i * math.pi / 4
        for da, r in ((-0.36, 6.9), (-0.2, 9.4), (0.2, 9.4), (0.36, 6.9)):
            pts.append((12 + r * math.cos(a + da), 12 + r * math.sin(a + da)))
    P.L(*(pts + [pts[0]]))
    P.C(12, 12, 2.9)


def _ruotato(P, cx, cy, l, h, gradi, copre=False):
    """Il contorno di un rettangolo l x h centrato in (cx, cy), girato di gradi. copre: prima cancella quello che c'e' sotto (la carta davanti nasconde
    quella dietro)."""
    a = math.radians(gradi)
    ca, sa = math.cos(a), math.sin(a)
    pts = [(cx + x * ca - y * sa, cy + x * sa + y * ca) for x, y in ((-l / 2, -h / 2), (l / 2, -h / 2), (l / 2, h / 2), (-l / 2, h / 2))]
    if copre:
        P.d.d.polygon(P.d._p(P.p(pts)), fill=(0, 0, 0, 0))
    P.L(*(pts + [pts[0]]))


def _martello(P):
    """Il manico di traverso e la testa perpendicolare."""
    P.L((12.2, 11.8), (4, 20))
    cx, cy = 14.6, 9.4
    ux, uy = 0.7071, 0.7071        # lungo la testa
    vx, vy = 0.7071, -0.7071       # lungo il manico
    pts = [(cx + s1 * 6.2 * ux + s2 * 2.6 * vx, cy + s1 * 6.2 * uy + s2 * 2.6 * vy) for s1, s2 in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
    P.L(*(pts + [pts[0]]))


def _ricarica(P):
    k, lw = P.k, P.lw
    P.d.arco(4.5 * k, 4.5 * k, 19.5 * k, 19.5 * k, 30, 300, P.col, lw)
    P.L((12.6, 2.4), (15.9, 5.5), (12.8, 8.7))


def _annulla(P, specchio=False):
    """La freccia che torna indietro (Undo); specchio: quella che va avanti (Redo)."""
    X = (lambda x: 24 - x) if specchio else (lambda x: x)
    arco = [(15 + 5 * math.cos(math.radians(a)), 14 + 5 * math.sin(math.radians(a))) for a in range(-90, 91, 10)]
    P.L(*[(X(x), y) for x, y in [(5, 9)] + arco + [(8, 19)]])
    P.L((X(9), 5), (X(5), 9), (X(9), 13))


def _vassoio(P):
    P.L((4, 16), (4, 19), (5, 20), (19, 20), (20, 19), (20, 16))


def _disegna(nome, P):
    L, R, C = P.L, P.R, P.C
    if nome == "salva":         # un dischetto
        R(4, 4, 20, 20, 2); L((8, 4), (8, 9), (15, 9), (15, 4)); C(12, 15, 2.2)
    elif nome == "cestino":
        L((4, 7), (20, 7)); L((9, 7), (9, 4.5), (10, 4), (14, 4), (15, 4.5), (15, 7))
        L((6, 7), (7, 19), (8, 20), (16, 20), (17, 19), (18, 7)); L((10, 11), (10, 16.5)); L((14, 11), (14, 16.5))
    elif nome == "x":
        L((6.5, 6.5), (17.5, 17.5)); L((17.5, 6.5), (6.5, 17.5))
    elif nome == "matita":
        L((4, 20), (4, 16), (15, 5), (19, 9), (8, 20), (4, 20)); L((12.5, 7.5), (16.5, 11.5))
    elif nome == "griglia":
        R(4, 4, 10.5, 10.5, 1.5); R(13.5, 4, 20, 10.5, 1.5); R(4, 13.5, 10.5, 20, 1.5); R(13.5, 13.5, 20, 20, 1.5)
    elif nome == "stella":
        _stella(P)
    elif nome == "copia":
        R(9, 9, 20, 20, 2); L((15, 9), (15, 5.5), (13.5, 4), (5.5, 4), (4, 5.5), (4, 13.5), (5.5, 15), (9, 15))
    elif nome == "upload":
        _vassoio(P); L((7.5, 8.5), (12, 4), (16.5, 8.5)); L((12, 4), (12, 15))
    elif nome == "download":
        _vassoio(P); L((7.5, 10.5), (12, 15), (16.5, 10.5)); L((12, 4), (12, 15))
    elif nome == "ingranaggio":
        _ingranaggio(P)
    elif nome == "martello":
        _martello(P)
    elif nome == "carte":       # due carte aperte a ventaglio
        _ruotato(P, 9.6, 12.4, 9.5, 14, -14); _ruotato(P, 14.6, 11.6, 9.5, 14, 12, copre=True)
    elif nome == "occhio":
        _occhio(P)
    elif nome == "goccia":
        _goccia(P)
    elif nome == "bacchetta":   # la bacchetta e le scintille: aggiusta
        L((4, 20), (14.5, 9.5)); L((18, 3), (18, 7)); L((16, 5), (20, 5)); L((20, 11), (20, 14)); L((18.5, 12.5), (21.5, 12.5)); L((11, 4), (11, 6.5))
    elif nome == "play":
        L((7, 4.5), (19, 12), (7, 19.5), (7, 4.5))
    elif nome == "uscita":      # la porta e la freccia che esce
        L((13, 8), (13, 5.5), (11.5, 4), (5.5, 4), (4, 5.5), (4, 18.5), (5.5, 20), (11.5, 20), (13, 18.5), (13, 16))
        L((9, 12), (21, 12)); L((17.5, 8.5), (21, 12), (17.5, 15.5))
    elif nome == "barre":
        L((6, 20), (6, 13)); L((12, 20), (12, 8)); L((18, 20), (18, 4))
    elif nome == "trend":
        L((3.5, 17.5), (9, 12), (13, 15.5), (20, 7.5)); L((15, 7.5), (20, 7.5), (20, 12.5))
    elif nome == "ricarica":
        _ricarica(P)
    elif nome == "filtro":
        L((4, 4.5), (20, 4.5), (14, 12), (14, 19.5), (10, 17.5), (10, 12), (4, 4.5))
    elif nome == "filtro_x":
        L((3, 4.5), (17, 4.5), (12, 11), (12, 18.5), (8.5, 16.8), (8.5, 11), (3, 4.5)); L((15.5, 14.5), (20.5, 19.5)); L((20.5, 14.5), (15.5, 19.5))
    elif nome == "segnalibro":
        L((7, 5.5), (8.5, 4), (15.5, 4), (17, 5.5), (17, 20), (12, 16.5), (7, 20), (7, 5.5))
    elif nome == "nota":
        R(5, 3, 19, 21, 2); L((9, 8), (15, 8)); L((9, 12), (15, 12)); L((9, 16), (12.5, 16))
    elif nome == "finestra":
        R(3, 5, 21, 19, 2); L((3, 9), (21, 9))
    elif nome == "indietro":
        L((19, 12), (5, 12)); L((10, 7), (5, 12), (10, 17))
    elif nome == "lista":
        L((9.5, 6), (20, 6)); L((9.5, 12), (20, 12)); L((9.5, 18), (20, 18))
        for y in (6, 12, 18):
            C(5, y, 1.3, pieno=True)
    elif nome == "layout":
        R(4, 4, 10.5, 20, 1.5); R(13.5, 4, 20, 10.5, 1.5); R(13.5, 13.5, 20, 20, 1.5)
    elif nome == "pila":
        L((12, 4), (20, 8), (12, 12), (4, 8), (12, 4)); L((4, 12), (12, 16), (20, 12)); L((4, 16), (12, 20), (20, 16))
    elif nome == "cuore":
        _cuore(P)
    elif nome == "link":
        L((9.5, 14.5), (14.5, 9.5))
        L((11, 6.5), (13.5, 4.5), (15.5, 3.8), (17.8, 4.2), (19.8, 6.2), (20.2, 8.5), (19.5, 10.5), (17.5, 13))
        L((13, 17.5), (10.5, 19.5), (8.5, 20.2), (6.2, 19.8), (4.2, 17.8), (3.8, 15.5), (4.5, 13.5), (6.5, 11))
    elif nome == "annulla":
        _annulla(P)
    elif nome == "ripeti":
        _annulla(P, specchio=True)
    elif nome == "spunta":
        L((5, 12.5), (10, 17.5), (19.5, 7))
    elif nome == "piu":
        L((12, 5), (12, 19)); L((5, 12), (19, 12))
    else:
        return False
    return True


NOMI = ("salva", "cestino", "x", "matita", "griglia", "stella", "copia", "upload", "download", "ingranaggio", "martello", "carte", "occhio", "goccia",
        "bacchetta", "play", "uscita", "barre", "trend", "ricarica", "filtro", "filtro_x", "segnalibro", "nota", "finestra", "indietro", "lista", "layout",
        "pila", "cuore", "link", "piu", "spunta", "annulla", "ripeti")


def immagine(nome, lato, colore="#ffffff"):
    """L'icona come immagine PIL (RGBA), None se il nome non c'e'."""
    if nome not in NOMI:
        return None
    P = _Penna(lato, colore)
    _disegna(nome, P)
    return P.d.immagine()


def icona(nome, lato, colore="#ffffff"):
    """L'icona come PhotoImage, fatta una volta per nome, misura e colore. None se il nome non c'e'."""
    if nome not in NOMI:
        return None
    chiave = ("icona_pulsante", nome, lato, colore)
    if chiave not in DG.CACHE:
        from PIL import ImageTk
        DG.CACHE[chiave] = ImageTk.PhotoImage(immagine(nome, lato, colore))
    return DG.CACHE[chiave]


# il testo del pulsante -> l'icona: la prima regola che combacia, sul testo in minuscolo senza segni davanti (il ⚙ di Settings) e senza ▾ in fondo. I pulsanti
# che scelgono una vista o un valore (Constructed, Win rate, Combat ›, Every action...) non hanno icona: restano satinati senza il blocco
REGOLE = (
    (r"^save file", "download"), (r"^save", "salva"), (r"^(delete|remove)", "cestino"), (r"^(cancel|dismiss)$", "x"), (r"^edit", "matita"),
    (r"^board", "griglia"), (r"^add to wishlist", "stella"), (r"^(copy|clone)", "copia"), (r"^import", "upload"), (r"^(export|download)", "download"),
    (r"^settings", "ingranaggio"), (r"^deck builder", "martello"), (r"^(select deck|by deck)", "carte"), (r"^hud on arena", "occhio"), (r"mana base", "goccia"),
    (r"^fix$", "bacchetta"), (r"^launch", "play"), (r"^closed session", "uscita"), (r"^open full analysis", "barre"), (r"^roadmap check", "trend"),
    (r"^(reset|check now|check again)", "ricarica"), (r"^clear all( filters)?$", "filtro_x"), (r"filters$", "filtro"), (r"^bookmark", "segnalibro"),
    (r"^note$", "nota"), (r"^show its window", "finestra"), (r"^bring it back", "indietro"), (r"^rows$", "lista"), (r"^arrange", "layout"),
    (r"^groups", "pila"), (r"^undo", "annulla"), (r"^redo", "ripeti"), (r"^(full page|restore)$", "finestra"), (r"^donate", "cuore"), (r"^link$", "link"), (r"^create", "piu"),
)


def pulito(testo):
    """Il testo senza i segni davanti (⚙), il ▾ in fondo e quello che segue un « · » (By deck · mazzo vs variante)."""
    t = (testo or "").split(" · ")[0].split("  ·  ")[0]
    t = re.sub(r"^[^\w]+", "", t).replace("▾", "").strip()
    return t


def per_testo(testo):
    t = pulito(testo).lower()
    for regola, nome in REGOLE:
        if re.search(regola, t):
            return nome
    return None


def prova():
    casi = []
    vuote = [n for n in NOMI if immagine(n, 18).getchannel("A").getextrema()[1] < 200]
    casi.append(("ogni icona disegnata e piena a 18 pixel", not vuote, vuote))
    piccole = [n for n in NOMI if immagine(n, 12).getchannel("A").getextrema()[1] < 120]
    casi.append(("ogni icona si vede anche a 12 pixel", not piccole, piccole))
    attese = {"Save": "salva", "Save file for Arena": "download", "Save as my filter": "salva", "Delete": "cestino", "Cancel": "x", "Edit this deck": "matita",
              "Board view": "griglia", "⚙  Settings": "ingranaggio", "Settings · 3": "ingranaggio", "Export ▾": "download", "Groups ▾": "pila",
              "Fix mana base": "goccia", "Fix": "bacchetta", "Clear all filters": "filtro_x", "Advanced filters": "filtro", "Reset · Your attacks": "ricarica",
              "By deck  ·  all decks vs all": "carte", "Copy for MTGO / text": "copia", "Donate": "cuore"}
    sbagliate = {t: per_testo(t) for t, n in attese.items() if per_testo(t) != n}
    casi.append(("il testo trova la sua icona", not sbagliate, sbagliate))
    senza = [t for t in ("Constructed", "Limited", "Win rate", "Combat ›", "Every action", "Moments", "Keys: both", "◀ Game", "Meta decks only", "Don't save")
             if per_testo(t) is not None]
    casi.append(("negativa: i pulsanti che scelgono una vista non hanno icona", not senza, senza))
    casi.append(("negativa: un nome che non c'e' da' None", immagine("niente", 18) is None))
    # la nitidezza: i bordi hanno valori intermedi (l'antialias), non solo 0 e 255
    a = immagine("stella", 18).getchannel("A").tobytes()
    casi.append(("antialias: bordi a mezzi toni", sum(1 for v in a if 0 < v < 255) > 10))
    ok = all(c[1] for c in casi)
    for c in casi:
        print(("OK   " if c[1] else "ROSSO") + " " + c[0] + ("" if c[1] or len(c) < 3 else f"  {c[2]}"))
    print(f"{sum(1 for c in casi if c[1])}/{len(casi)}")
    return ok


def foglio(f, lato=18):
    from PIL import Image
    cols = 8
    righe = (len(NOMI) + cols - 1) // cols
    im = Image.new("RGBA", (cols * (lato * 3), righe * (lato * 3)), (24, 24, 28, 255))
    for i, n in enumerate(NOMI):
        x, y = (i % cols) * lato * 3 + lato, (i // cols) * lato * 3 + lato
        im.alpha_composite(immagine(n, lato), (x, y))
    im.save(f)


if __name__ == "__main__":
    if "--foglio" in sys.argv:
        foglio(sys.argv[sys.argv.index("--foglio") + 1], int(sys.argv[sys.argv.index("--foglio") + 2]) if len(sys.argv) > sys.argv.index("--foglio") + 2 else 18)
    else:
        sys.exit(0 if prova() else 1)
