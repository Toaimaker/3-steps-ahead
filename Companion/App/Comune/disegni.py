"""Le grafiche disegnate dall'app, nitide (Autore, 9 nov 2026: «ci sono molte grafiche da te disegnate che sono piene di aliasing o imprecise / voglio il massimo della
qualita' visiva»). La tela di Tk su Windows non ha l'antialiasing: una linea obliqua, un cerchio o un triangolo escono a scalini. Qui ogni forma si disegna con PIL a SCALA
volte la misura vera e si riduce col filtro Lanczos, con la trasparenza: sulla tela va come immagine. Le linee orizzontali e verticali e i testi di Tk sono gia' nitidi e restano
sulla tela.

    Disegno(l, h)              una tela trasparente; .linea, .poligono, .cerchio, .rett, .arco in pixel veri; .foto() -> PhotoImage
    spunta, tondo, chevron, triangolo, piu, cestino, lucchetto, punto, pomello    le icone dei comandi, fatte una volta per misura e colori (CACHE)
    tratti(l, h, ...)          lo strato dei grafici: linee, punti e poligoni in un'immagine sola

    py -I -X utf8 Companion/App/Comune/disegni.py --prova     le icone su un foglio e le prove (misure, trasparenza, la negativa: senza la riduzione i bordi restano duri)
"""
import os, sys
_casa = os.path.dirname(os.path.abspath(__file__))      # si sale fino a percorsi.py, che mette nel sys.path tutte le cartelle del Companion
while not os.path.isfile(os.path.join(_casa, "percorsi.py")):
    _casa = os.path.dirname(_casa)
if _casa not in sys.path:
    sys.path.insert(0, _casa)
import percorsi  # noqa: E402,F401
import math  # noqa: E402

from PIL import Image, ImageDraw  # noqa: E402

SCALA = 4           # 4 campioni per pixel per lato: 16 per pixel, oltre non si vede differenza
CACHE = {}          # le PhotoImage delle icone: devono restare vive finche' la tela le usa


def _rgba(c, alfa=255):
    """«#24baff» o un nome di Tk -> (r, g, b, a). None: trasparente."""
    if c is None or c == "":
        return (0, 0, 0, 0)
    if isinstance(c, tuple):
        return c if len(c) == 4 else (*c, alfa)
    c = c.lstrip("#")
    if len(c) == 3:
        c = "".join(x * 2 for x in c)
    return (int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16), alfa)


class Disegno:
    """Una tela PIL trasparente grande l x h pixel veri, disegnata a SCALA volte."""

    def __init__(self, l, h, fondo=None):
        self.l, self.h = max(1, int(round(l))), max(1, int(round(h)))
        self.im = Image.new("RGBA", (self.l * SCALA, self.h * SCALA), _rgba(fondo))
        self.d = ImageDraw.Draw(self.im)

    def _p(self, pts):
        return [(x * SCALA, y * SCALA) for x, y in pts]

    def linea(self, pts, colore, larghezza=1.0, tondo=True, tratteggio=None):
        """Una spezzata: pts [(x, y)]. tondo: estremi e giunti arrotondati. tratteggio: (pieno, vuoto) in pixel."""
        if len(pts) < 2:
            return
        if tratteggio:      # trattini con le estremita' dritte: quelle tonde chiudevano i vuoti e la linea sembrava piena
            for a, b in _tratti(pts, *tratteggio):
                self.linea([a, b], colore, larghezza, tondo=False)
            return
        w = max(1, round(larghezza * SCALA))
        self.d.line(self._p(pts), fill=_rgba(colore), width=w, joint="curve" if tondo else None)
        if tondo and w > 2:
            r = w / 2
            for x, y in (pts[0], pts[-1]):
                self.d.ellipse((x * SCALA - r, y * SCALA - r, x * SCALA + r, y * SCALA + r), fill=_rgba(colore))

    def poligono(self, pts, riempi=None, bordo=None, larghezza=1.0):
        if riempi:
            self.d.polygon(self._p(pts), fill=_rgba(riempi))
        if bordo:
            self.linea(list(pts) + [pts[0]], bordo, larghezza)

    def cerchio(self, cx, cy, r, riempi=None, bordo=None, larghezza=1.0):
        s = SCALA
        if bordo and larghezza:
            self.d.ellipse(((cx - r) * s, (cy - r) * s, (cx + r) * s, (cy + r) * s), fill=_rgba(bordo))
            ri = r - larghezza
            if ri > 0:
                self.d.ellipse(((cx - ri) * s, (cy - ri) * s, (cx + ri) * s, (cy + ri) * s), fill=_rgba(riempi) if riempi else (0, 0, 0, 0))
        elif riempi:
            self.d.ellipse(((cx - r) * s, (cy - r) * s, (cx + r) * s, (cy + r) * s), fill=_rgba(riempi))

    def rett(self, x0, y0, x1, y1, riempi=None, bordo=None, larghezza=1.0, raggio=0.0):
        s = SCALA
        box = (x0 * s, y0 * s, x1 * s - 1, y1 * s - 1)
        self.d.rounded_rectangle(box, radius=raggio * s, fill=_rgba(riempi) if riempi else None, outline=_rgba(bordo) if bordo else None,
                                 width=max(1, round(larghezza * s)) if bordo else 0)

    def arco(self, x0, y0, x1, y1, inizio, fine, colore, larghezza=1.0):
        """Un arco della cornice (x0, y0, x1, y1), da inizio a fine gradi in senso orario da ore 3 (come PIL)."""
        s = SCALA
        self.d.arc((x0 * s, y0 * s, x1 * s, y1 * s), inizio, fine, fill=_rgba(colore), width=max(1, round(larghezza * s)))

    def immagine(self, veloce=False):
        """L'immagine PIL alla misura vera, ridotta col filtro Lanczos. veloce: la media di ogni blocco SCALA x SCALA in alfa premoltiplicata (il
        sovracampionamento puro, 4 volte piu' veloce: 16 ms contro 62 su un grafico di 1200 x 320; differenza media 1,2 su 255): per i grafici, che si rifanno
        spesso e sono grandi (11 nov 2026, sessione Magic 13). Le icone, piccole e in cache, restano col Lanczos."""
        if veloce:
            return self.im.convert("RGBa").reduce(SCALA).convert("RGBA")
        return self.im.resize((self.l, self.h), Image.LANCZOS)

    def foto(self, veloce=False):
        from PIL import ImageTk
        im = self.immagine(veloce)
        f = ImageTk.PhotoImage(im)
        import tela_gpu         # la sorgente, per la tela sulla scheda video (Card view): non carica pyglet
        tela_gpu.registra(f, im)
        return f


def _tratti(pts, pieno, vuoto):
    """Una spezzata a tratti: [(a, b)] dei pezzi pieni, con la fase che continua da un segmento all'altro."""
    out, fase, dentro = [], 0.0, True
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        lun = math.hypot(x1 - x0, y1 - y0)
        t = 0.0
        while t < lun:
            passo = (pieno if dentro else vuoto) - fase
            fino = min(lun, t + passo)
            if dentro:
                a, b = t / lun if lun else 0, fino / lun if lun else 0
                out.append(((x0 + (x1 - x0) * a, y0 + (y1 - y0) * a), (x0 + (x1 - x0) * b, y0 + (y1 - y0) * b)))
            fase = fase + (fino - t)
            if fase >= (pieno if dentro else vuoto) - 1e-9:
                fase, dentro = 0.0, not dentro
            t = fino
    return out


def _icona(chiave, fa):
    """Una PhotoImage fatta una volta per chiave (misura e colori): le icone si ridisegnano spesso, si cuociono una volta sola."""
    if chiave not in CACHE:
        CACHE[chiave] = fa().foto()
    return CACHE[chiave]


def spunta(lato, on, colore, campo, bordo, segno, raggio=2.0):
    """La spunta quadrata: piena del colore con il segno di spunta se accesa, il campo col bordo se spenta."""
    def fa():
        d = Disegno(lato, lato)
        d.rett(0, 0, lato, lato, riempi=colore if on else campo, bordo=colore if on else bordo, larghezza=1, raggio=raggio)
        if on:
            k = lato / 13
            d.linea([(3.2 * k, 6.6 * k), (5.6 * k, 9.2 * k), (10 * k, 3.8 * k)], segno, larghezza=max(1.6, 1.9 * k))
        return d
    return _icona(("spunta", lato, on, colore, campo, bordo, segno, raggio), fa)


def tondo(lato, on, colore, campo, bordo, punto):
    """La scelta tonda (una sola accesa): piena del colore col punto in mezzo se accesa."""
    def fa():
        d = Disegno(lato, lato)
        r = lato / 2
        d.cerchio(r, r, r - 0.2, riempi=colore if on else campo, bordo=colore if on else bordo, larghezza=1)
        if on:
            d.cerchio(r, r, lato * 0.17, riempi=punto)
        return d
    return _icona(("tondo", lato, on, colore, campo, bordo, punto), fa)


def chevron(lato, giu, colore, larghezza=1.5):
    """La freccia a V delle tendine: in giu' chiusa, in su aperta."""
    def fa():
        d = Disegno(lato, lato)
        k = lato / 25
        d.linea([(8 * k, 10 * k), (12.5 * k, 14.5 * k), (17 * k, 10 * k)] if giu else [(8 * k, 14.5 * k), (12.5 * k, 10 * k), (17 * k, 14.5 * k)], colore, larghezza)
        return d
    return _icona(("chevron", lato, giu, colore, larghezza), fa)


def freccia_destra(lato, colore, larghezza=1.5):
    """La freccia sottile a destra (>) delle sezioni chiuse, sorella di chevron (redesign del 14 nov 2026)."""
    def fa():
        d = Disegno(lato, lato)
        k = lato / 25
        d.linea([(10 * k, 8 * k), (14.5 * k, 12.5 * k), (10 * k, 17 * k)], colore, larghezza)
        return d
    return _icona(("freccia_destra", lato, colore, larghezza), fa)


def triangolo(lato, giu, colore):
    """Il triangolo pieno dei gruppi a tendina: in giu' aperto, a destra chiuso."""
    def fa():
        d = Disegno(lato, lato)
        k = lato / 22
        d.poligono([(4 * k, 7 * k), (18 * k, 7 * k), (11 * k, 16 * k)] if giu else [(7 * k, 4 * k), (16 * k, 11 * k), (7 * k, 18 * k)], riempi=colore)
        return d
    return _icona(("triangolo", lato, giu, colore), fa)


def piu(lato, colore, larghezza=2.0):
    """Il cerchio col «+» delle schede vuote."""
    def fa():
        d = Disegno(lato, lato)
        r = lato / 2
        d.cerchio(r, r, r - 0.5, bordo=colore, larghezza=larghezza)
        b = lato * 0.2
        d.linea([(r - b, r), (r + b, r)], colore, larghezza * 1.5)
        d.linea([(r, r - b), (r, r + b)], colore, larghezza * 1.5)
        return d
    return _icona(("piu", lato, colore, larghezza), fa)


def barre(lato, colore):
    """L'icona dei grafici: tre barre di altezze diverse su una linea di base (il pulsante View della Meta, 11 nov 2026)."""
    def fa():
        d = Disegno(lato, lato)
        b = lato * 0.86
        w = lato * 0.2
        for i, h in enumerate((0.42, 0.72, 0.56)):
            x0 = lato * 0.12 + i * lato * 0.29
            d.rett(x0, b - lato * h, x0 + w, b, riempi=colore, raggio=lato * 0.04)
        d.linea([(lato * 0.06, b + 0.5), (lato * 0.94, b + 0.5)], colore, 1.2)
        return d
    return _icona(("barre", lato, colore), fa)


def rotella(lato, colore, fondo):
    """La rotella delle impostazioni (13 nov 2026, Autore: «ridisegna la rotellina che così è terribile»; prima era il carattere ⚙ del font): otto denti
    squadrati e smussati attorno a un anello, il foro al centro nel colore del fondo."""
    import math as _m

    def fa():
        d = Disegno(lato, lato)
        c = lato / 2
        r_est, r_int, denti = lato * 0.48, lato * 0.36, 8
        pts = []
        for i in range(denti):
            a = 2 * _m.pi * i / denti
            for da, r in ((-0.30, r_int), (-0.17, r_est), (0.17, r_est), (0.30, r_int)):
                aa = a + da * 2 * _m.pi / denti
                pts.append((c + r * _m.cos(aa), c + r * _m.sin(aa)))
        d.poligono(pts, riempi=colore)
        d.cerchio(c, c, lato * 0.34, riempi=colore)
        d.cerchio(c, c, lato * 0.15, riempi=fondo)
        return d
    return _icona(("rotella", lato, colore, fondo), fa)


def griglia(lato, colore):
    """L'icona della griglia: quattro riquadri (il pulsante View della Meta, 11 nov 2026)."""
    def fa():
        d = Disegno(lato, lato)
        s = lato * 0.38
        for i in (0, 1):
            for j in (0, 1):
                x0, y0 = lato * 0.08 + i * lato * 0.46, lato * 0.08 + j * lato * 0.46
                d.rett(x0, y0, x0 + s, y0 + s, riempi=colore, raggio=lato * 0.06)
        return d
    return _icona(("griglia", lato, colore), fa)


def cestino(lato, colore, fondo, bordo):
    """Il cestino sulla copertina di una scheda: il quadrato scuro, il coperchio col manico, il secchio a righe."""
    def fa():
        d = Disegno(lato, lato)
        d.rett(0, 0, lato, lato, riempi=fondo, bordo=bordo, larghezza=1, raggio=lato * 0.16)
        k = lato / 26
        cx = lato / 2
        d.linea([(cx - 8 * k, 8 * k), (cx + 8 * k, 8 * k)], colore, 1.8 * k)
        d.linea([(cx - 3 * k, 8 * k), (cx - 3 * k, 5.5 * k), (cx + 3 * k, 5.5 * k), (cx + 3 * k, 8 * k)], colore, 1.5 * k)
        d.poligono([(cx - 6.5 * k, 10 * k), (cx + 6.5 * k, 10 * k), (cx + 5.5 * k, 21 * k), (cx - 5.5 * k, 21 * k)], bordo=colore, larghezza=1.5 * k)
        for dx in (-2.5, 0, 2.5):
            d.linea([(cx + dx * k, 12.5 * k), (cx + dx * k, 18.5 * k)], colore, 1.2 * k)
        return d
    return _icona(("cestino", lato, colore, fondo, bordo), fa)


def lucchetto(lato, chiuso, colore):
    """Il lucchetto (le terre nel builder, le label della Board, i mazzi privati). Ridisegnato il 12 nov 2026 (Autore: «un redesign piu' definito dei
    lucchetti»): l'arco spesso a U che entra nel corpo, il corpo pieno con gli angoli tondi e il buco della chiave forato (trasparente); aperto, l'arco
    alzato e girato a destra con la gamba sinistra libera. Su una griglia di 20 unita', una scala per ogni misura."""
    def fa():
        d = Disegno(lato, lato)
        k = lato / 20
        s = SCALA
        sp = 2.6 * k            # lo spessore dell'arco
        if chiuso:
            d.arco(5.2 * k, 1.6 * k, 14.8 * k, 11.2 * k, 180, 360, colore, sp)
            d.linea([(5.2 * k + sp / 2, 6.4 * k), (5.2 * k + sp / 2, 9.6 * k)], colore, sp, tondo=False)
            d.linea([(14.8 * k - sp / 2, 6.4 * k), (14.8 * k - sp / 2, 9.6 * k)], colore, sp, tondo=False)
        else:
            d.arco(9.6 * k, 0.4 * k, 19.2 * k, 10.0 * k, 180, 360, colore, sp)
            d.linea([(19.2 * k - sp / 2, 5.2 * k), (19.2 * k - sp / 2, 9.6 * k)], colore, sp, tondo=False)
            d.linea([(9.6 * k + sp / 2, 5.2 * k), (9.6 * k + sp / 2, 6.6 * k)], colore, sp, tondo=True)
        d.rett(3.0 * k, 9.0 * k, 17.0 * k, 19.4 * k, riempi=colore, raggio=2.4 * k)
        # il buco della chiave: un tondo e una gamba, forati nel corpo
        cx, cy, r = 10 * k, 13.2 * k, 1.7 * k
        d.d.ellipse(((cx - r) * s, (cy - r) * s, (cx + r) * s, (cy + r) * s), fill=(0, 0, 0, 0))
        d.d.polygon([((cx - 0.9 * k) * s, (cy + 0.6 * k) * s), ((cx + 0.9 * k) * s, (cy + 0.6 * k) * s), ((cx + 1.2 * k) * s, 17.2 * k * s),
                     ((cx - 1.2 * k) * s, 17.2 * k * s)], fill=(0, 0, 0, 0))
        return d
    return _icona(("lucchetto2", lato, chiuso, colore), fa)


def occhio(lato, colore, barrato=False):
    """L'occhio di pubblico/privato (Autore, 12 nov 2026, scelta A fra cinque proposte: «le icone public / private ... cosi' non mi piacciono»): la mandorla
    e la pupilla piena; barrato (privato) con la barra in diagonale e lo stacco trasparente intorno. Su una griglia di 20 unita'."""
    def fa():
        d = Disegno(lato, lato)
        k = lato / 20
        s = SCALA
        cx, cy, w, h = 10 * k, 10 * k, 8.6 * k, 5.4 * k
        pts = [(cx + w * math.cos(t), cy - h * math.sin(t)) for t in [i * math.pi / 24 for i in range(25)]]
        pts += [(cx + w * math.cos(t), cy + h * math.sin(t)) for t in [math.pi - i * math.pi / 24 for i in range(25)]]
        d.linea(pts, colore, 1.7 * k)
        d.cerchio(cx, cy, 2.7 * k, riempi=colore)
        if barrato:
            a, b = (3.0 * k, 17.0 * k), (17.0 * k, 3.0 * k)
            d.d.line([(a[0] * s, a[1] * s), (b[0] * s, b[1] * s)], fill=(0, 0, 0, 0), width=round(4.6 * k * s))
            d.linea([a, b], colore, 1.8 * k)
        return d
    return _icona(("occhio", lato, colore, barrato), fa)


def clona(lato, testo, fondo, bordo):
    """Clona (12 nov 2026, Autore: «in deck builder crea sia sulla deck cover che dentro la possibilita' di clonare il mazzo»): sul quadrato scuro come il
    cestino, due schede sovrapposte, quella davanti col +."""
    def fa():
        d = Disegno(lato, lato)
        k = lato / 26
        d.rett(0.5, 0.5, lato - 0.5, lato - 0.5, riempi=fondo, bordo=bordo, larghezza=1, raggio=3 * k)
        d.rett(6 * k, 5 * k, 16 * k, 17 * k, bordo=testo, larghezza=1.4 * k, raggio=1.6 * k)
        d.rett(10 * k, 9 * k, 20 * k, 21 * k, riempi=fondo, bordo=testo, larghezza=1.4 * k, raggio=1.6 * k)
        d.linea([(15 * k, 12 * k), (15 * k, 18 * k)], testo, 1.4 * k)
        d.linea([(12 * k, 15 * k), (18 * k, 15 * k)], testo, 1.4 * k)
        return d
    return _icona(("clona", lato, testo, fondo, bordo), fa)


def stellina(lato, stato):
    """La stellina della wishlist sulle schede della Meta (Autore, 12 nov 2026, proposta D fra quattro: «stellina»): un quadrato smussato scuro
    semitrasparente e la stella a cinque punte; stato 0 vuota bianca, 1 (sotto il mouse) vuota d'oro col bordo d'oro, 2 (in wishlist) piena d'oro."""
    def fa():
        d = Disegno(lato, lato)
        oro = (240, 190, 60, 255)
        d.rett(0.5, 0.5, lato - 0.5, lato - 0.5, riempi=(14, 14, 18, 215 if stato != 1 else 240), bordo=oro if stato == 1 else None, larghezza=1.3,
               raggio=lato * 0.2)
        cx, cy, r1 = lato / 2, lato / 2 + lato * 0.03, lato * 0.34
        pts = []
        for i in range(10):
            r = r1 if i % 2 == 0 else r1 / 2.3
            a = -math.pi / 2 + i * math.pi / 5
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
        if stato == 2:
            d.poligono(pts, riempi=oro)
        else:
            d.poligono(pts, bordo=oro if stato == 1 else (240, 240, 244, 255), larghezza=lato * 0.055)
        return d
    return _icona(("stellina", lato, stato), fa)


def pillola(l, h, bordo, fondo, larghezza=1.2):
    """Una pillola arrotondata (raggio meta' altezza) col bordo, in antialias: il fondo della pillola pubblico/privato."""
    def fa():
        d = Disegno(l, h)
        d.rett(0.5, 0.5, l - 0.5, h - 0.5, riempi=fondo, bordo=bordo, larghezza=larghezza, raggio=(h - 1) / 2)
        return d
    return _icona(("pillola", l, h, bordo, fondo, larghezza), fa)


def interruttore(l, h, on, colore_on, fondo_off, bordo_off, pomello, pomello_off=None):
    """L'interruttore on/off (13 nov 2026, Data sharing: «fai in modo che il pulsante di datasharing sia uno switcher on off»): una pillola, piena del colore
    se accesa col pomello a destra, scura col bordo se spenta col pomello a sinistra."""
    def fa():
        d = Disegno(l, h)
        r = (h - 1) / 2
        d.rett(0.5, 0.5, l - 0.5, h - 0.5, riempi=colore_on if on else fondo_off, bordo=colore_on if on else bordo_off, larghezza=1.2, raggio=r)
        rp = h / 2 - 3
        cx = l - h / 2 if on else h / 2
        d.cerchio(cx, h / 2, rp, riempi=pomello if on else (pomello_off or pomello))
        return d
    return _icona(("interruttore", l, h, on, colore_on, fondo_off, bordo_off, pomello, pomello_off), fa)


def punto(diametro, colore, bordo=None, larghezza=0.0):
    """Un punto pieno (il led dell'ultima partita, i punti dei grafici), col bordo se serve."""
    def fa():
        d = Disegno(diametro, diametro)
        r = diametro / 2
        d.cerchio(r, r, r - 0.1, riempi=colore, bordo=bordo, larghezza=larghezza if bordo else 0)
        return d
    return _icona(("punto", diametro, colore, bordo, larghezza), fa)


def _mescola(a, b, t):
    """Il colore a verso b per la frazione t (0 = a)."""
    ra, rb = _rgba(a), _rgba(b)
    return "#%02x%02x%02x" % tuple(round(x + (y - x) * t) for x, y in zip(ra[:3], rb[:3]))


def sfumatura(im, x0, y0, x1, y1, sopra, sotto):
    """Riempie (in pixel della tela grande) il rettangolo con la sfumatura verticale da sopra a sotto: una riga per riga di pixel."""
    a, b = _rgba(sopra), _rgba(sotto)
    alto = max(1, y1 - y0)
    col = Image.new("RGBA", (1, alto))
    for y in range(alto):
        t = y / max(1, alto - 1)
        col.putpixel((0, y), tuple(round(p + (q - p) * t) for p, q in zip(a, b)))
    im.paste(col.resize((max(1, x1 - x0), alto)), (x0, y0))


def pannello(l, h, sopra, sotto, bordo, luce=None, raggio=6.0, fondo=None, ombra=0, bagliore=None, alfa_bagliore=70, larghezza=1.0):
    """Il pannello del redesign (14 nov 2026, Note/Redesign_Grafico): la sfumatura appena percettibile dall'alto al basso, un filo di luce sul bordo alto,
    il bordo sottile, gli angoli tondi e, se chiesti, l'ombra morbida sotto (ombra: pixel) e un bagliore leggero del colore dato.
    fondo: il colore dietro (i quattro angoli); None = trasparente. -> l'immagine PIL alla misura vera.
    Il corpo si fa alla misura vera (la sfumatura e' verticale: una colonna allargata); solo la forma e il bordo, in scala di grigi, si disegnano a SCALA
    volte e si riducono: un pannello largo 1300 pixel costava 50-60 ms tutto a 4x, ora pochi ms."""
    from PIL import ImageFilter
    s = SCALA
    L, H = max(2, int(l)), max(2, int(h))
    im = Image.new("RGBA", (L, H), _rgba(fondo))
    m = ombra + (6 if bagliore else 0)
    if ombra or bagliore:        # l'ombra e il bagliore escono dal pannello: si disegnano sotto, sfocati, dentro la sua misura (il pannello si stringe di m)
        alone = Image.new("RGBA", (L, H), (0, 0, 0, 0))
        da = ImageDraw.Draw(alone)
        if ombra:
            da.rounded_rectangle((m, m + ombra * 0.5, L - m, H - m + ombra * 0.6), radius=raggio, fill=(0, 0, 0, 150))
        if bagliore:
            r, g, b, _a = _rgba(bagliore)
            da.rounded_rectangle((m - 2, m - 2, L - m + 2, H - m + 2), radius=raggio + 2, fill=(r, g, b, alfa_bagliore))
        im.alpha_composite(alone.filter(ImageFilter.GaussianBlur((ombra or 4) * 0.55)))
    w_, h_ = L - 2 * m, H - 2 * m
    a, b = _rgba(sopra), _rgba(sotto)
    col = Image.new("RGBA", (1, h_))
    for y in range(h_):
        t = y / max(1, h_ - 1)
        col.putpixel((0, y), tuple(round(p + (q - p) * t) for p, q in zip(a, b)))
    corpo = col.resize((w_, h_), Image.NEAREST)
    if luce:        # il filo di luce in cima, dentro il bordo, fra gli angoli
        ImageDraw.Draw(corpo).line(((round(raggio), 1), (w_ - 1 - round(raggio), 1)), fill=_rgba(luce))
    forma = Image.new("L", (w_ * s, h_ * s), 0)
    ImageDraw.Draw(forma).rounded_rectangle((0, 0, w_ * s - 1, h_ * s - 1), radius=raggio * s, fill=255)
    filo = Image.new("L", (w_ * s, h_ * s), 0)
    ImageDraw.Draw(filo).rounded_rectangle((0, 0, w_ * s - 1, h_ * s - 1), radius=raggio * s, outline=255, width=max(1, round(larghezza * s)))
    forma, filo = forma.resize((w_, h_), Image.BOX), filo.resize((w_, h_), Image.BOX)
    corpo.putalpha(forma)
    corpo.paste(Image.new("RGBA", (w_, h_), _rgba(bordo)), (0, 0), filo)
    pezzo = Image.new("RGBA", (L, H), (0, 0, 0, 0))
    pezzo.paste(corpo, (m, m))
    im.alpha_composite(pezzo)
    return im


def foto_pannello(l, h, sopra, sotto, bordo, **k):
    """pannello() come PhotoImage, una volta per misura e colori (le tessere e le schede si ridisegnano spesso)."""
    chiave = ("pannello", int(l), int(h), sopra, sotto, bordo, tuple(sorted(k.items())))
    if chiave not in CACHE:
        from PIL import ImageTk
        im = pannello(l, h, sopra, sotto, bordo, **k)
        f = ImageTk.PhotoImage(im)
        import tela_gpu
        tela_gpu.registra(f, im)
        if len(CACHE) > 900:        # via il piu' vecchio dei pannelli: chi lo mostra ancora lo tiene vivo nella sua tela
            vecchio = next((c_ for c_ in CACHE if c_[0] == "pannello"), None)
            if vecchio is not None:
                CACHE.pop(vecchio)
        CACHE[chiave] = f
    return CACHE[chiave]


def puntini(l, h, passo, colore, fondo):
    """Il foglio a puntini del Board (redesign del 14 nov 2026): un puntino di un pixel ogni passo, sul fondo. -> PhotoImage, una volta per misura."""
    chiave = ("puntini", int(l), int(h), int(passo), colore, fondo)
    if chiave not in CACHE:
        from PIL import ImageTk
        im = Image.new("RGBA", (max(1, int(l)), max(1, int(h))), _rgba(fondo))      # RGBA: una texture RGB con righe non multiple di 4 byte faceva cadere pyglet
        px, col = im.load(), _rgba(colore)
        for y in range(passo // 2, im.size[1], passo):
            for x in range(passo // 2, im.size[0], passo):
                px[x, y] = col
        f = ImageTk.PhotoImage(im)
        import tela_gpu         # la sorgente, per il Board sulla scheda video
        tela_gpu.registra(f, im)
        vecchie = [c_ for c_ in CACHE if c_[0] == "puntini"]
        if len(vecchie) > 12:       # le misure di prima (zoom, finestra): via le piu' vecchie
            CACHE.pop(vecchie[0])
        CACHE[chiave] = f
    return CACHE[chiave]


def numero(c, x, y, testo, colore, misura=18, anchor="w", tags=()):
    """Un numero grande del redesign (14 nov 2026) su una tela di Tk o una CartaTela: Bahnschrift, e il «%» in fondo piu' piccolo accanto, come nei mockup.
    anchor «w» o «e» (a destra il numero finisce in x); il «%» ha il tag «unita». -> l'id del numero."""
    from tema import FN
    t = str(testo)
    unita = "%" if t.endswith("%") and len(t) > 1 else ""
    corpo = t[:-1] if unita else t
    if anchor == "e" and unita:
        i_u = c.create_text(x, y + misura * 0.18, text=unita, anchor="e", fill=colore, font=FN(max(7, round(misura * 0.55)), False), tags=tuple(tags) + ("unita",))
        x = (c.bbox(i_u) or (x - 10, 0, x, 0))[0] + 2
        return c.create_text(x, y, text=corpo, anchor="e", fill=colore, font=FN(misura), tags=tags)
    i_n = c.create_text(x, y, text=corpo, anchor=anchor, fill=colore, font=FN(misura), tags=tags)
    if unita:
        c.create_text((c.bbox(i_n) or (0, 0, x + 30, 0))[2] - 2, y + misura * 0.18, text=unita, anchor="w", fill=colore, font=FN(max(7, round(misura * 0.55)), False),
                      tags=tuple(tags) + ("unita",))      # «unita»: chi legge i testi in ordine la porta in fondo (tag_raise), il numero resta dov'era
    return i_n


def tratti(l, h, linee=(), punti=(), poligoni=()):
    """Lo strato di un grafico in un'immagine sola: linee [(pts, colore, larghezza, tratteggio)], punti [(x, y, r, riempi, bordo, larghezza)],
    poligoni [(pts, riempi, bordo, larghezza)]. -> PhotoImage (chi la mette sulla tela ne tiene il riferimento)."""
    d = Disegno(l, h)
    for pts, riempi, bordo, larghezza in poligoni:
        d.poligono(pts, riempi, bordo, larghezza)
    for pts, colore, larghezza, tratteggio in linee:
        d.linea(pts, colore, larghezza, tratteggio=tratteggio)
    for x, y, r, riempi, bordo, larghezza in punti:
        d.cerchio(x, y, r, riempi, bordo, larghezza)
    return d.foto(veloce=True)


def prova():
    """Le icone su un foglio (Log_Arena/disegni_prova.png, da guardare) e i controlli: misure, trasparenza fuori dalla forma, bordi morbidi; la negativa: senza la riduzione no."""
    import tkinter as tk
    root = tk.Tk(); root.withdraw()
    casi = []
    d = Disegno(20, 20)
    d.cerchio(10, 10, 8, riempi="#24baff")
    im = d.immagine()
    px = im.load()
    casi.append(("la misura vera", im.size == (20, 20)))
    casi.append(("fuori dalla forma e' trasparente", px[0, 0][3] == 0))
    casi.append(("dentro e' pieno", px[10, 10][3] == 255))
    bordo = [px[x, 10][3] for x in range(20)]
    casi.append(("il bordo del cerchio ha toni intermedi (antialias)", any(0 < a < 255 for a in bordo)))
    pv = d.immagine(veloce=True).load()
    casi.append(("anche la riduzione veloce: toni intermedi, e il colore del bordo non si scurisce", any(0 < pv[x, 10][3] < 255 for x in range(20))
                 and all(pv[x, 10][3] == 0 or pv[x, 10][:3] == (0x24, 0xBA, 0xFF) or abs(pv[x, 10][2] - 255) <= 2 for x in range(20))))
    duro = Image.new("RGBA", (20, 20), (0, 0, 0, 0)); ImageDraw.Draw(duro).ellipse((2, 2, 18, 18), fill=(36, 186, 255, 255))
    casi.append(("senza la riduzione il bordo e' duro (prova negativa)", not any(0 < duro.load()[x, 10][3] < 255 for x in range(20))))
    casi.append(("i tratti continuano la fase da un segmento all'altro", len(_tratti([(0, 0), (10, 0), (20, 0)], 4, 2)) == 4))
    casi.append(("le icone si fanno una volta", spunta(13, True, "#24baff", "#101014", "#3a3a40", "#101014") is spunta(13, True, "#24baff", "#101014", "#3a3a40", "#101014")))
    # il pannello del redesign (14 nov 2026): sfumatura dall'alto al basso, filo di luce, bordo, angoli trasparenti; l'ombra esce sotto
    pn = pannello(120, 60, "#131720", "#0e1117", "#2a303b", luce="#30384a", raggio=6).load()
    casi.append(("pannello: l'angolo e' trasparente, il centro pieno", pn[0, 0][3] <= 2 and pn[60, 30][3] == 255))
    casi.append(("pannello: sopra piu' chiaro che sotto (la sfumatura)", sum(pn[60, 8][:3]) > sum(pn[60, 52][:3])))
    casi.append(("pannello: il filo di luce in cima e' piu' chiaro del corpo subito sotto", sum(pn[60, 1][:3]) > sum(pn[60, 4][:3])))
    po = pannello(120, 60, "#131720", "#0e1117", "#2a303b", ombra=6).load()
    casi.append(("pannello con l'ombra: sotto il corpo c'e' l'ombra semitrasparente", 0 < po[60, 58][3] < 255))
    casi.append(("pannello senza ombra: sotto il corpo niente (prova negativa)", pannello(120, 60, "#131720", "#0e1117", "#2a303b").load()[60, 59][3] == 255
                 and pannello(120, 60, "#131720", "#0e1117", "#2a303b").load()[0, 59][3] <= 2))
    # il foglio da guardare: ogni icona a misura vera e ingrandita
    pezzi = [Disegno(13, 13), Disegno(13, 13), Disegno(25, 25), Disegno(22, 22), Disegno(60, 60), Disegno(26, 26), Disegno(18, 18)]
    ff = [lambda d: (d.rett(0, 0, 13, 13, riempi="#24baff", raggio=2), d.linea([(3.2, 6.6), (5.6, 9.2), (10, 3.8)], "#101014", 1.9)),
          lambda d: (d.cerchio(6.5, 6.5, 6.3, riempi="#24baff"), d.cerchio(6.5, 6.5, 2.2, riempi="#101014")),
          lambda d: d.linea([(8, 10), (12.5, 14.5), (17, 10)], "#7c7c84", 1.5),
          lambda d: d.poligono([(4, 7), (18, 7), (11, 16)], riempi="#24baff"),
          lambda d: (d.cerchio(30, 30, 29.5, bordo="#24baff", larghezza=2), d.linea([(18, 30), (42, 30)], "#24baff", 3), d.linea([(30, 18), (30, 42)], "#24baff", 3)),
          lambda d: d.rett(0, 0, 26, 26, riempi="#101014", bordo="#303034", raggio=4),
          lambda d: (d.arco(5, 2, 13, 13, 180, 360, "#bebec2", 2), d.rett(3, 9, 15, 17, riempi="#bebec2", raggio=1.5))]
    foglio = Image.new("RGBA", (12 + sum(p.l * 5 + 12 for p in pezzi), 12 + max(p.h * 5 for p in pezzi) + 12 + max(p.h for p in pezzi)), (24, 24, 28, 255))
    x = 12
    for p, f in zip(pezzi, ff):
        f(p)
        im = p.immagine()
        foglio.alpha_composite(im.resize((p.l * 5, p.h * 5), Image.NEAREST), (x, 12))
        foglio.alpha_composite(im, (x, 24 + max(q.h * 5 for q in pezzi)))
        x += p.l * 5 + 12
    out = os.path.join(percorsi.ROOT, "Log_Arena", "disegni_prova.png")
    foglio.save(out)
    root.destroy()
    for n, ok in casi:
        print(("  ok    " if ok else "  ROSSO ") + n)
    print(f"{sum(ok for _n, ok in casi)}/{len(casi)} · foglio in {out}")
    return 0 if all(ok for _n, ok in casi) else 1


if __name__ == "__main__":
    if "--prova" in sys.argv:
        sys.exit(prova())
