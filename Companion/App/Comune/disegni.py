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
    """Il lucchetto delle terre nel builder: l'arco chiuso o aperto a destra, il corpo pieno."""
    def fa():
        d = Disegno(lato, lato)
        k = lato / 18
        if chiuso:
            d.arco(5 * k, 2 * k, 13 * k, 13 * k, 180, 360, colore, 2 * k)
            d.linea([(5 * k, 7.5 * k), (5 * k, 10 * k)], colore, 2 * k, tondo=False)
            d.linea([(13 * k, 7.5 * k), (13 * k, 10 * k)], colore, 2 * k, tondo=False)
        else:
            d.arco(8 * k, 0, 16 * k, 11 * k, 180, 360, colore, 2 * k)
            d.linea([(16 * k, 5.5 * k), (16 * k, 8 * k)], colore, 2 * k, tondo=False)
        if chiuso:
            d.rett(3 * k, 9 * k, 15 * k, 17 * k, riempi=colore, raggio=1.5 * k)
        else:
            d.rett(3 * k, 9 * k, 15 * k, 17 * k, bordo=colore, larghezza=2 * k, raggio=1.5 * k)
        return d
    return _icona(("lucchetto", lato, chiuso, colore), fa)


def punto(diametro, colore, bordo=None, larghezza=0.0):
    """Un punto pieno (il led dell'ultima partita, i punti dei grafici), col bordo se serve."""
    def fa():
        d = Disegno(diametro, diametro)
        r = diametro / 2
        d.cerchio(r, r, r - 0.1, riempi=colore, bordo=bordo, larghezza=larghezza if bordo else 0)
        return d
    return _icona(("punto", diametro, colore, bordo, larghezza), fa)


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
