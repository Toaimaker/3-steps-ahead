"""Il tappetino da gioco del replayer (13-14 nov 2026, Autore: «un vero tappetino da gioco con la vista delle mie carte in mano e quelle
in mano all'avversario di dorso con copertina carte dell'app 3 Steps Ahead», poi «metti le terre a sinistra e incantesimi artefatti ecc a destra»,
«ricostruiscimi qui l'app replayer con queste modifiche, funzionante, poi se va bene la montiamo nell'app»).

Disegna un momento della partita (una foto di dati_analizzatore.foto_partita o azioni_partita) su un'immagine PIL della misura chiesta:
- il feltro (blu ardesia, grana, reticolo esagonale che svanisce, le meta' tinte coi colori dei giocatori, bordo cucito), le zone stampate, il medaglione
  col logo sulla linea di mezzo: si disegna a 2x una volta per misura e si tiene;
- sopra, a 1x: le carte (miniature ridotte e tenute), le tappate girate e un filo piu' scure, forza/costituzione, ×N, le carte arrivate dal passo prima
  col filo azzurro, la tua mano a ventaglio dal bordo basso, la sua di dorso dal bordo alto, grimorio, cimitero ed esilio, la pila, le frecce.

Il campo come al tavolo: davanti, verso la linea di mezzo, le creature; dietro le terre a sinistra e artefatti, incantesimi, planeswalker e battaglie a
destra; il lato dell'avversario e' speculare. Nato come prototipo (Companion/Prototipi/tappeto: le 240 prove del replayer uguali all'app, prova per
prova), montato nel replayer di Performance lo stesso giorno (Autore: «Sì, montalo»): pagina_performance.disegna_board chiama disegna(..., pezzi=True),
mette il fondo come immagine e ogni carta come oggetto della tela (_tappeto_disegno), cosi' animazioni, frecce, danni e hover restano quelli di prima.

    py -I -X utf8 Companion/App/Schede/Performance/disegno_tappeto.py --prova
"""
import math, os, sys

_casa = os.path.dirname(os.path.abspath(__file__))
while not os.path.isfile(os.path.join(_casa, "percorsi.py")):
    _casa = os.path.dirname(_casa)
if _casa not in sys.path:
    sys.path.insert(0, _casa)
import percorsi  # noqa: E402,F401

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont  # noqa: E402

DW, DH = 1600, 1000                     # le coordinate del progetto: tutto si scala sulla misura vera
BLU, ARANCIO, VIOLA, ROSSO, GIALLO = (36, 186, 255), (240, 173, 78), (181, 140, 255), (255, 93, 93), (255, 210, 63)
FONDO = (16, 16, 20)
RAPP = 279 / 200


def _font_file():
    """Bahnschrift (Windows 10 e 11, condensato); dove non c'e' (Mac) il Poppins dell'app."""
    for f in (os.path.join(os.environ.get("WINDIR", "C:" + os.sep + "Windows"), "Fonts", "bahnschrift.ttf"),
              os.path.join(_casa, "Grafica", "Poppins-Medium.ttf")):
        if os.path.isfile(f):
            return f
    return "DejaVuSans.ttf"


BAHN = _font_file()
# le colonne e le righe del tappeto, nelle coordinate del progetto
XB0, LC = 170, 1240                     # il campo (a destra la pila)
ZX0, ZX1 = 1400, 1572                   # grimorio, cimitero, esilio
MEZZO = DH / 2
SPLIT = 0.56                            # nella fila dietro: le terre fino al 56% della larghezza
STACK = (1250, MEZZO - 64, 1370, MEZZO + 64)
ZONE = dict(       # chiave -> (x0, y0, x1, y1)
    suo_dietro=(XB0, 112, LC, 216), suo_crea=(XB0, 224, LC, MEZZO - 14),
    mio_crea=(XB0, MEZZO + 14, LC, MEZZO + 226), mio_dietro=(XB0, MEZZO + 236, LC, MEZZO + 336),
    lib_suo=(ZX0, 104, ZX1, 224), cim_suo=(ZX0, 232, ZX1, 362), esi_suo=(ZX0, 370, ZX1, MEZZO - 14),
    lib_mio=(ZX0, MEZZO + 14, ZX1, MEZZO + 144), cim_mio=(ZX0, MEZZO + 152, ZX1, MEZZO + 282), esi_mio=(ZX0, MEZZO + 290, ZX1, MEZZO + 400))
VITA = dict(vita_suo=(86, 300), vita_mio=(86, DH - 290))


def e_terra(nome):
    import mazzi_salvati as MS
    return MS.e_terra(nome)


_FONT = {}


def font(px, peso="Bold SemiCondensed"):
    k = (round(px * 2) / 2, peso)
    if k not in _FONT:
        f = ImageFont.truetype(BAHN, max(6, round(k[0])))
        try:
            f.set_variation_by_name(peso)
        except Exception:      # noqa: BLE001 - un font senza varianti
            pass
        _FONT[k] = f
    return _FONT[k]


# ---------------------------------------------------------------- disegni comuni

def logo_carte(d, cx, cy, lato, filo, fondo=(24, 24, 30)):
    """Le tre carte del logo (Distribuzione/logo.py) centrate in (cx, cy), nel quadrato da 150 scalato a lato."""
    k = lato / 150
    for (x, y), f in zip([(26, 56), (48, 42), (70, 28)], [(70, 70, 80), (120, 120, 132), BLU]):
        x0, y0 = cx - lato / 2 + x * k, cy - lato / 2 + y * k
        d.rounded_rectangle((x0, y0, x0 + 44 * k, y0 + 62 * k), radius=6 * k, fill=fondo, outline=f, width=max(1, round(filo)))


_DORSI = {}


def dorso(w):
    """Il dorso delle carte di 3 Steps Ahead, largo w: bordo nero come le carte vere, pannello scuro col tratteggio fine, cornice azzurra con le tacche, il
    medaglione col logo, «3 STEPS AHEAD» in alto e capovolto in basso (girato di 180 gradi si legge uguale, tranne il logo). Disegnato a 4x, tenuto."""
    w = max(8, int(w))
    if w in _DORSI:
        return _DORSI[w]
    k = 4
    L, A = w * k, round(w * RAPP) * k
    im = Image.new("RGBA", (L, A), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    r = L * 0.05
    d.rounded_rectangle((0, 0, L - 1, A - 1), radius=r, fill=(8, 8, 10))
    m = L * 0.045
    pan = Image.new("RGBA", (L, A), (0, 0, 0, 0))
    pd = ImageDraw.Draw(pan)
    for yy in range(0, A, 2):
        t = abs(yy / A - 0.5) * 2
        c = tuple(round(a + (b - a) * t) for a, b in zip((30, 38, 52), (14, 16, 22)))
        pd.rectangle((0, yy, L, yy + 1), fill=c + (255,))
    passo = L * 0.035
    i = -A
    while i < L + A:
        pd.line((i, 0, i + A, A), fill=(255, 255, 255, 10), width=max(1, k // 2))
        pd.line((i + A, 0, i, A), fill=(255, 255, 255, 6), width=max(1, k // 2))
        i += passo
    maschera = Image.new("L", (L, A), 0)
    ImageDraw.Draw(maschera).rounded_rectangle((m, m, L - m, A - m), radius=r * 0.6, fill=255)
    im.paste(pan, (0, 0), maschera)
    c1, c2, t = L * 0.085, L * 0.11, L * 0.07
    d.rounded_rectangle((c1, c1, L - c1, A - c1), radius=r * 0.4, outline=BLU + (150,), width=max(2, round(L * 0.006)))
    d.rounded_rectangle((c2, c2, L - c2, A - c2), radius=r * 0.3, outline=BLU + (45,), width=max(1, round(L * 0.003)))
    for (x, y, sx, sy) in ((c1, c1, 1, 1), (L - c1, c1, -1, 1), (c1, A - c1, 1, -1), (L - c1, A - c1, -1, -1)):
        d.line((x, y + sy * t, x, y, x + sx * t, y), fill=BLU + (255,), width=max(2, round(L * 0.012)))
    cx, cy, R = L / 2, A / 2, L * 0.31
    for rr, a in ((R * 1.18, 25), (R * 1.06, 60)):
        d.ellipse((cx - rr, cy - rr, cx + rr, cy + rr), outline=BLU + (a,), width=max(1, round(L * 0.004)))
    alone = Image.new("RGBA", (L, A), (0, 0, 0, 0))
    ImageDraw.Draw(alone).ellipse((cx - R, cy - R, cx + R, cy + R), fill=BLU + (70,))
    im.alpha_composite(alone.filter(ImageFilter.GaussianBlur(L * 0.06)))
    d.ellipse((cx - R, cy - R, cx + R, cy + R), fill=(14, 16, 22), outline=BLU + (220,), width=max(2, round(L * 0.008)))
    logo_carte(d, cx + L * 0.01, cy, R * 1.55, L * 0.012, fondo=(26, 28, 36))
    f = font(L * 0.062)
    testo = "3  STEPS  AHEAD"
    bb = d.textbbox((0, 0), testo, font=f)
    tw, th = bb[2] - bb[0], bb[3] - bb[1]
    y_t = A * 0.16
    d.text((cx - tw / 2 - bb[0], y_t - th / 2 - bb[1]), testo, font=f, fill=(225, 232, 240, 230))
    giu = Image.new("RGBA", (L, A), (0, 0, 0, 0))
    ImageDraw.Draw(giu).text((cx - tw / 2 - bb[0], y_t - th / 2 - bb[1]), testo, font=f, fill=(225, 232, 240, 230))
    im.alpha_composite(giu.rotate(180))
    for yy in (y_t + th * 1.3, A - y_t - th * 1.3):
        d.line((cx - L * 0.18, yy, cx + L * 0.18, yy), fill=BLU + (120,), width=max(1, round(L * 0.004)))
    _DORSI[w] = im.resize((w, round(w * RAPP)), Image.LANCZOS)
    return _DORSI[w]


_FACCE, _ROT, _OMBRE = {}, {}, {}


def faccia(nome, w, tappata=False):
    """La carta vera larga w (girata se tappata), angoli arrotondati; dall'immagine intera se c'e', se no dalla miniatura cotta; senza immagine un
    riquadro col nome."""
    w = max(8, int(w))
    k = (nome, w, tappata)
    if k in _FACCE:
        return _FACCE[k]
    import capsule
    h = round(w * RAPP)
    im = None
    for f in (capsule.file_immagine(nome), capsule.file_mini(nome)):
        if nome and os.path.isfile(f):
            try:
                im = Image.open(f).convert("RGBA").resize((w, h), Image.LANCZOS)
                break
            except Exception:      # noqa: BLE001 - un file rotto: il riquadro
                im = None
    if im is None:
        im = carta_vuota(nome, w, h)
    m = Image.new("L", (w * 3, h * 3), 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, w * 3 - 1, h * 3 - 1), radius=w * 3 * 0.048, fill=255)
    im.putalpha(ImageChops.multiply(im.getchannel("A"), m.resize((w, h), Image.LANCZOS)))
    if tappata:
        im = im.rotate(90, expand=True)
        vel = Image.new("RGBA", im.size, (0, 0, 0, 70))
        vel.putalpha(ImageChops.multiply(vel.getchannel("A"), im.getchannel("A")))
        im = Image.alpha_composite(im, vel)
    _FACCE[k] = im
    return im


def carta_vuota(nome, w, h):
    """Una pedina o una carta senza immagine: carta scura, bordo, il nome."""
    im = Image.new("RGBA", (w, h), (30, 30, 36, 255))
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, w - 1, h - 1), outline=(90, 90, 100), width=max(1, w // 60))
    d.ellipse((w * 0.3, h * 0.28, w * 0.7, h * 0.28 + w * 0.4), outline=(201, 168, 76), width=max(1, w // 40))
    f = font(max(7, w * 0.085), "SemiBold")
    parole, righe, r_ = (nome or "?").split(), [], ""
    for p in parole:
        if d.textlength((r_ + " " + p).strip(), font=f) > w * 0.86 and r_:
            righe.append(r_)
            r_ = p
        else:
            r_ = (r_ + " " + p).strip()
    righe.append(r_)
    y = h * 0.66
    for r_ in righe[:3]:
        tw = d.textlength(r_, font=f)
        d.text(((w - tw) / 2, y), r_, font=f, fill=(235, 235, 240))
        y += f.size * 1.15
    return im


def ruotata(im, ang, chiave):
    k = (chiave, im.size, round(ang * 10))
    if k not in _ROT:
        _ROT[k] = im.rotate(ang, expand=True, resample=Image.BICUBIC)
    return _ROT[k]


def ombra_sprite(w, h, raggio, alfa):
    """L'ombra morbida di una carta w x h, tenuta per misura: (immagine, margine)."""
    k = (int(w), int(h), int(raggio), alfa)
    if k not in _OMBRE:
        p = int(raggio * 2) + 2
        o = Image.new("L", (int(w) + 2 * p, int(h) + 2 * p), 0)
        ImageDraw.Draw(o).rounded_rectangle((p, p, p + w, p + h), radius=min(w, h) * 0.06, fill=alfa)
        o = o.filter(ImageFilter.GaussianBlur(max(1, raggio / 2)))
        nero = Image.new("RGBA", o.size, (0, 0, 0, 255))
        nero.putalpha(o)
        _OMBRE[k] = (nero, p)
    return _OMBRE[k]


def gruppi(carte):
    """Le stesse carte insieme: [nome, tappata, pedina, forza, costituzione, quante, [id]] nell'ordine di arrivo."""
    out, idx = [], {}
    for c in carte:
        k = (c[0], c[1], c[2], c[3] if len(c) > 3 else None, c[4] if len(c) > 4 else None)
        if k in idx:
            g = out[idx[k]]
            g[5] += 1
        else:
            idx[k] = len(out)
            g = [k[0], k[1], k[2], k[3], k[4], 1, []]
            out.append(g)
        if len(c) > 5 and c[5] is not None:
            g[6].append(c[5])
    return out


# ---------------------------------------------------------------- il tappeto

class Tappeto:
    """Un tappeto di misura W x H. disegna(...) -> (immagine RGB, scatole), le scatole per il passaggio del mouse e i clic."""

    def __init__(self, W, H):
        self.W, self.H = int(W), int(H)
        self.kx, self.ky = self.W / DW, self.H / DH
        self.k = min(self.kx, self.ky)
        self._fondo = None
        self._pezzi = None
        self.sup = 1                    # il fondo si disegna a 2x: i minimi dei testi raddoppiano

    def X(self, v):
        return v * self.kx

    def Y(self, v):
        return v * self.ky

    def K(self, v):
        return v * self.k

    def box(self, b):
        return (self.X(b[0]), self.Y(b[1]), self.X(b[2]), self.Y(b[3]))

    # -- il fondo, a 2x una volta
    def fondo(self):
        if self._fondo is None:
            g2 = Tappeto(self.W * 2, self.H * 2)
            g2.sup = 2
            self._fondo = g2._disegna_fondo().resize((self.W, self.H), Image.LANCZOS)
        return self._fondo

    def _disegna_fondo(self):
        L, A = self.W, self.H
        t = Image.new("RGBA", (L, A), FONDO + (255,))
        g = Image.radial_gradient("L").resize((L, A), Image.BICUBIC)
        feltro = Image.composite(Image.new("RGBA", (L, A), (10, 12, 16, 255)), Image.new("RGBA", (L, A), (26, 34, 46, 255)), g)
        rum = Image.effect_noise((max(1, L // 2), max(1, A // 2)), 40).resize((L, A), Image.BICUBIC)
        feltro.alpha_composite(Image.merge("RGBA", (rum, rum, rum, Image.new("L", (L, A), 14))))
        hx = Image.new("RGBA", (L, A), (0, 0, 0, 0))
        hd = ImageDraw.Draw(hx)
        r = self.K(26)
        dx, dy = r * math.sqrt(3), r * 1.5
        row, y = 0, 0.0
        while y < A + r:
            x = dx / 2 if row % 2 else 0.0
            while x < L + r:
                hd.polygon([(x + r * math.cos(math.radians(60 * k + 30)), y + r * math.sin(math.radians(60 * k + 30))) for k in range(6)],
                           outline=(140, 190, 230, 34))
                x += dx
            y += dy
            row += 1
        hx.putalpha(ImageChops.multiply(hx.getchannel("A"), Image.eval(g, lambda v: max(0, 255 - v * 2))))
        feltro.alpha_composite(hx)
        for col, cy in ((ARANCIO, 160), (BLU, DH - 160)):        # le meta' tinte coi colori dei giocatori
            al = Image.new("RGBA", (L, A), (0, 0, 0, 0))
            ImageDraw.Draw(al).ellipse((self.X(200), self.Y(cy - 260), self.X(1300), self.Y(cy + 260)), fill=col + (16,))
            feltro.alpha_composite(al.filter(ImageFilter.GaussianBlur(self.K(90))))
        fil = Image.new("RGBA", (L, A), (0, 0, 0, 0))     # il logo in filigrana
        logo_carte(ImageDraw.Draw(fil), self.X(DW / 2 - 60), self.Y(MEZZO), self.K(300), self.K(3), fondo=(0, 0, 0, 0))
        fil.putalpha(fil.getchannel("A").point(lambda v: int(v * 0.07)))
        feltro.alpha_composite(fil)
        m = self.K(8)
        mk = Image.new("L", (L, A), 0)
        ImageDraw.Draw(mk).rounded_rectangle((m, m, L - m, A - m), radius=self.K(26), fill=255)
        t.paste(feltro, (0, 0), mk)
        d = ImageDraw.Draw(t)
        d.rounded_rectangle((m, m, L - m, A - m), radius=self.K(26), outline=(4, 4, 6, 255), width=max(1, round(self.K(3))))
        c = self.K(15)
        for (x0, y0, x1, y1) in ((c + self.K(20), c, L - c - self.K(20), c), (c + self.K(20), A - c, L - c - self.K(20), A - c),
                                 (c, c + self.K(20), c, A - c - self.K(20)), (L - c, c + self.K(20), L - c, A - c - self.K(20))):
            lung = math.hypot(x1 - x0, y1 - y0)
            n = max(2, int(lung // self.K(9)))
            for i in range(0, n, 2):
                a0, a1 = i / n, (i + 1) / n
                d.line((x0 + (x1 - x0) * a0, y0 + (y1 - y0) * a0, x0 + (x1 - x0) * a1, y0 + (y1 - y0) * a1), fill=(90, 110, 130, 90),
                       width=max(1, round(self.K(1.2))))
        fl = font(max(11 * self.sup, self.K(13)))       # a 2x: diventa ~11 pixel, mai meno
        # la linea di mezzo e il medaglione
        for x0, x1 in ((XB0, DW / 2 - 110), (DW / 2 + 10, STACK[0] - 14)):
            d.line((self.X(x0), self.Y(MEZZO), self.X(x1), self.Y(MEZZO)), fill=(150, 190, 230, 55), width=max(1, round(self.K(1.5))))
        cxm, cym = self.X(DW / 2 - 50), self.Y(MEZZO)
        for rr, fi, ou in ((46, None, (150, 190, 230, 50)), (36, (14, 18, 24, 200), BLU + (110,))):
            d.ellipse((cxm - self.K(rr), cym - self.K(rr), cxm + self.K(rr), cym + self.K(rr)), fill=fi, outline=ou, width=max(1, round(self.K(1.5))))
        logo_carte(d, cxm + self.K(1), cym, self.K(54), self.K(1.5), fondo=(22, 24, 30))
        # le zone stampate
        self.slot(d, STACK, "STACK", VIOLA, fl, 60, tratteggio=True)
        for chi, col, nome in (("suo", ARANCIO, "OPPONENT · "), ("mio", BLU, "YOUR ")):
            self.slot(d, ZONE[f"{chi}_crea"], f"{nome}CREATURES", col, fl, 40)
            x0, y0, x1, y1 = ZONE[f"{chi}_dietro"]
            xm = x0 + (x1 - x0) * SPLIT
            self.slot(d, (x0, y0, xm - 6, y1), f"{nome}LANDS", col, fl, 40)
            self.slot(d, (xm + 6, y0, x1, y1), f"{nome}ARTIFACTS · ENCHANTMENTS · PLANESWALKERS", col, fl, 40)
            for z in ("lib", "cim", "esi"):
                self.slot(d, ZONE[f"{z}_{chi}"], None, col, fl, 55)
        return t

    def slot(self, d, b, etichetta, colore, f, alfa, tratteggio=False):
        x0, y0, x1, y1 = self.box(b)
        w = max(1, round(self.K(1.2)))
        if tratteggio:
            passo = self.K(7)
            for (a, b_, c_, e) in ((x0, y0, x1, y0), (x0, y1, x1, y1), (x0, y0, x0, y1), (x1, y0, x1, y1)):
                n = max(1, int(math.hypot(c_ - a, e - b_) // passo))
                for i in range(0, n, 2):
                    u0, u1 = i / n, min(1, (i + 1) / n)
                    d.line((a + (c_ - a) * u0, b_ + (e - b_) * u0, a + (c_ - a) * u1, b_ + (e - b_) * u1), fill=colore + (alfa,), width=w)
        else:
            d.rounded_rectangle((x0, y0, x1, y1), radius=self.K(10), outline=colore + (alfa,), width=w)
        if etichetta:
            d.text((x0 + self.K(8), y0 + self.K(5)), etichetta, font=f, fill=colore + (min(255, alfa + 70),))

    # -- i pezzi a 1x
    @staticmethod
    def liscio(d, forma, box, fill=None, outline=None, width=0, radius=0):
        """Una forma senza scalini (14 nov 2026, Autore: «migliora l'aliasing dei disegni»): disegnata a 4x su un ritaglio, ridotta col Lanczos e messa
        sopra l'immagine di d. forma: «ell» (ellisse) o «rr» (rettangolo arrotondato)."""
        im = d._image
        k = 4
        x0, y0, x1, y1 = box
        m = width + 2
        ox, oy = math.floor(x0 - m), math.floor(y0 - m)
        L, A = math.ceil(x1 + m) - ox, math.ceil(y1 + m) - oy
        if L <= 0 or A <= 0:
            return
        lay = Image.new("RGBA", (L * k, A * k), (0, 0, 0, 0))
        dd = ImageDraw.Draw(lay)
        b = ((x0 - ox) * k, (y0 - oy) * k, (x1 - ox) * k, (y1 - oy) * k)
        w = max(1, round(width * k)) if outline else 0
        if forma == "ell":
            dd.ellipse(b, fill=fill, outline=outline, width=w)
        else:
            dd.rounded_rectangle(b, radius=radius * k, fill=fill, outline=outline, width=w)
        lay = lay.resize((L, A), Image.LANCZOS)
        cx0, cy0 = max(0, -ox), max(0, -oy)          # il pezzo che esce dall'immagine si taglia
        lay = lay.crop((cx0, cy0, min(L, im.width - ox), min(A, im.height - oy)))
        if lay.width > 0 and lay.height > 0:
            im.alpha_composite(lay, (ox + cx0, oy + cy0))

    def pillola(self, d, cx, cy, testo, f, fondo=(12, 12, 16, 235), bordo=(230, 230, 236, 255), colore=(255, 255, 255), pad=6):
        bb = d.textbbox((0, 0), testo, font=f)
        tw, th = bb[2] - bb[0], bb[3] - bb[1]
        p = self.K(pad)
        x0, y0, x1, y1 = cx - tw / 2 - p, cy - th / 2 - p * 0.55, cx + tw / 2 + p, cy + th / 2 + p * 0.55
        self.liscio(d, "rr", (x0, y0, x1, y1), fill=fondo, outline=bordo, width=max(1.0, self.K(1.2)), radius=(y1 - y0) / 2)
        d.text((cx - tw / 2 - bb[0], cy - th / 2 - bb[1]), testo, font=f, fill=colore)
        return (x0, y0, x1, y1)

    def metti(self, tela, im, x, y, ombra=True, raggio=10, alfa=150, sposta=6):
        if ombra:
            o, p = ombra_sprite(im.width, im.height, self.K(raggio), alfa)
            tela.alpha_composite(o, (round(x) - p, round(y) - p + round(self.K(sposta))))
        tela.alpha_composite(im, (round(x), round(y)))

    @staticmethod
    def componi(parti):
        """Un pezzo da piu' immagini [(immagine, dx, dy)] relative a un'origine -> (immagine, (ox, oy)): ox, oy dove sta l'angolo del pezzo rispetto
        all'origine."""
        x0 = min(dx for _i, dx, _dy in parti)
        y0 = min(dy for _i, _dx, dy in parti)
        x1 = max(dx + im.width for im, dx, _dy in parti)
        y1 = max(dy + im.height for im, _dx, dy in parti)
        sp = Image.new("RGBA", (math.ceil(x1 - x0) + 1, math.ceil(y1 - y0) + 1), (0, 0, 0, 0))
        for im, dx, dy in parti:
            sp.alpha_composite(im, (round(dx - x0), round(dy - y0)))
        return sp, (x0, y0)

    def posa(self, tela, sp, ox, oy, x, y, voce):
        """Il pezzo sul tappeto (o, in modo pezzi, nella lista dei pezzi: l'app lo mette come oggetto della tela)."""
        if self._pezzi is not None:
            voce.update(img=sp, xy=(x + ox, y + oy))
            self._pezzi.append(voce)
        else:
            tela.alpha_composite(sp, (round(x + ox), round(y + oy)))

    def fila(self, tela, d, lista, b, wmax, colore, nuove, scatole, pos, zkey):
        """Una fila di carte nel riquadro b (pixel), alla misura piu' grande che ci sta, centrata. Ogni carta e' un pezzo: ombra, carta, forza e
        costituzione, ×N, il filo azzurro e NEW se e' arrivata dal passo prima."""
        if not lista:
            return
        x0, y0, x1, y1 = b
        larga, alta = x1 - x0, y1 - y0
        gap = self.K(10)
        w = int(self.K(wmax))
        while w > 18:
            h = round(w * RAPP)
            tot = sum((h if g[1] else w) for g in lista) + gap * (len(lista) - 1)
            if h <= alta and tot <= larga:
                break
            w -= 2
        h = round(w * RAPP)
        tot = sum((h if g[1] else w) for g in lista) + gap * (len(lista) - 1)
        x = x0 + (larga - tot) / 2
        fpt, fn, fnew = font(max(8, self.K(12)), "Bold"), font(max(15, self.K(18)), "Bold"), font(max(7, self.K(8.5)), "Bold")
        for g in lista:
            ww, hh = (h, w) if g[1] else (w, h)
            y = y0 + (alta - h) / 2 + (h - hh)
            im = faccia(g[0], w, g[1])
            o, p = ombra_sprite(im.width, im.height, self.K(10), 150)
            sp, (ox, oy) = self.componi([(o, -p, -p + self.K(6)), (im, 0, 0), (Image.new("RGBA", (ww + 8, hh + 8)), -4, -4)])
            ds = ImageDraw.Draw(sp)
            cx, cy = -ox, -oy           # l'angolo della carta dentro il pezzo
            nuova = nuove.get(g[0], 0) > 0
            if nuova:
                nuove[g[0]] -= 1
                self.liscio(ds, "rr", (cx - 3, cy - 3, cx + ww + 3, cy + hh + 3), outline=BLU + (255,), width=max(2.0, self.K(2.5)), radius=self.K(6))
                self.pillola(ds, cx + self.K(22), cy + hh - self.K(14), "NEW", fnew, fondo=(15, 134, 204, 240), bordo=(15, 134, 204, 255))
            if g[3] is not None and g[4] is not None:
                self.pillola(ds, cx + ww - self.K(24), cy + hh - self.K(16), f"{g[3]}/{g[4]}", fpt)
            if g[5] > 1:
                self.pillola(ds, cx + ww - self.K(26), cy + self.K(22), f"×{g[5]}", fn, fondo=colore + (245,), bordo=(255, 255, 255, 230),
                             colore=(10, 12, 16), pad=7)
            r_ = (x, y, x + ww, y + hh)
            self.posa(tela, sp, ox, oy, x, y, dict(zkey=zkey, nome=g[0], box=r_, tap=g[1], ped=g[2], ids=list(g[6]), nuova=nuova))
            scatole.append(r_ + (g[0],))
            for id_ in g[6]:
                pos[id_] = r_
            x += ww + gap

    def ventaglio(self, tela, carte, cx, base_y, w, apertura, sovrap, capovolto, scatole, larga_max, zkey):
        """Una mano a ventaglio: le immagini [(chiave, immagine)], il perno sotto la base; capovolto per l'avversario. Ogni carta e' un pezzo."""
        n = len(carte)
        if not n:
            return
        passo = min(w * (1 - sovrap), larga_max / max(1, n))
        apertura = min(apertura, 40 / max(1, n))
        raggio = w * 7
        for i, (chiave, im) in enumerate(carte):
            u = i - (n - 1) / 2
            ang = u * apertura
            px = cx + u * passo
            py = base_y + (1 - math.cos(math.radians(ang))) * raggio * (-1 if capovolto else 1)
            r = ruotata(im, (180 - ang) if capovolto else -ang, chiave)
            x, y = px - r.width / 2, py - r.height / 2
            o, p = ombra_sprite(r.width - self.K(12), r.height - self.K(12), self.K(14), 170)
            sp, (ox, oy) = self.componi([(o, self.K(6) - p, self.K(6) - p + self.K(8 if capovolto else -8)), (r, 0, 0)])
            nome = chiave[0] if chiave and not capovolto else None
            box = (x + self.K(8), max(y, 0), x + r.width - self.K(8), min(self.H, y + r.height))
            self.posa(tela, sp, ox, oy, x, y, dict(zkey=zkey, nome=nome, box=box, tap=False, ped=False, ids=[], nuova=False))
            if nome:
                scatole.append(box + (nome,))

    def pila_zona(self, tela, d, chiave, carte, colore, n=None, retro=False, scatole=None, zone=None):
        x0, y0, x1, y1 = self.box(ZONE[chiave])
        tit = {"lib": "LIBRARY", "cim": "GRAVEYARD", "esi": "EXILE"}[chiave[:3]]
        q = n if n is not None else len(carte)
        h = (y1 - y0) - self.K(30)
        w = round(h / RAPP)
        if w > (x1 - x0) - self.K(22):
            w = round((x1 - x0) - self.K(22))
            h = round(w * RAPP)
        cx, yc = (x0 + x1) / 2, y0 + self.K(8)
        fl = font(max(10, self.K(10)))
        if retro:
            b = dorso(w)
            self._grimori[chiave] = (cx - w / 2, yc, cx + w / 2, yc + h)       # da qui parte la carta pescata
            strati = (min(5, max(1, q // 8)) if isinstance(q, int) else 3) if q else 0
            if q:
                o, p = ombra_sprite(b.width, b.height, self.K(8), 150)
                tela.alpha_composite(o, (round(cx - w / 2) - p, round(yc) - p + round(self.K(5))))
                for i in range(strati, 0, -1):
                    tela.alpha_composite(b, (round(cx - w / 2 + self.K(i * 1.2)), round(yc + self.K(i * 1.2))))
                tela.alpha_composite(b, (round(cx - w / 2), round(yc)))
        elif carte:
            if len(carte) > 1:
                dietro = ruotata(faccia(carte[1], w), 4, ("pila", carte[1], w))
                tela.alpha_composite(dietro, (round(cx - dietro.width / 2 + self.K(3)), round(yc + self.K(1))))
            im = faccia(carte[0], w)       # in cima la piu' recente: Arena scrive la pila dalla carta arrivata per ultima
            self.metti(tela, im, cx - w / 2, yc, raggio=8)
            if scatole is not None:
                scatole.append((cx - w / 2, yc, cx + w / 2, yc + h, carte[0]))
        else:
            fe = font(self.K(10), "SemiBold")
            tw = d.textlength("empty", font=fe)
            d.text((cx - tw / 2, yc + h / 2 - self.K(6)), "empty", font=fe, fill=(120, 126, 138, 160))
        et = f"{tit}  {q}"
        if self._pezzi is not None and chiave[:3] in ("cim", "esi"):       # nell'app la scritta e' un testo della tela, come nel replayer di prima
            self._etichette[chiave] = (cx, y1 - self.K(10), f"{tit} · {q}", colore)
        else:
            tw = d.textlength(et, font=fl)
            d.text((cx - tw / 2, y1 - self.K(17)), et, font=fl, fill=colore + (220,))
        if zone is not None:
            zone[chiave] = ((x0, y0, x1, y1), list(carte))

    def giocatore(self, tela, d, chiave, chi, colore, vite, mano, grimorio, sopra, pos):
        x, y = VITA[chiave]
        R = self.K(42)
        cx, cy = self.X(x), self.Y(y)
        o, p = ombra_sprite(R * 2.6, R * 2.6, self.K(28), 60)
        alone = Image.new("RGBA", o.size, colore + (0,))
        alone.putalpha(o.getchannel("A"))
        tela.alpha_composite(alone, (round(cx - R * 1.3) - p, round(cy - R * 1.3) - p))
        self.liscio(d, "ell", (cx - R, cy - R, cx + R, cy + R), fill=(12, 14, 18, 255), outline=colore + (255,), width=max(2.0, self.K(3)))
        self.liscio(d, "ell", (cx - R + self.K(6), cy - R + self.K(6), cx + R - self.K(6), cy + R - self.K(6)), outline=colore + (70,), width=1)
        pos[chiave] = (cx - R, cy - R, cx + R, cy + R)
        f = font(self.K(34), "Bold")
        t = "-" if vite is None else str(vite)
        bb = d.textbbox((0, 0), t, font=f)
        d.text((cx - (bb[2] - bb[0]) / 2 - bb[0], cy - (bb[3] - bb[1]) / 2 - bb[1] - self.K(3)), t, font=f, fill=(255, 255, 255))
        fl = font(self.K(8.5), "SemiBold")
        tw = d.textlength("LIFE", font=fl)
        d.text((cx - tw / 2, cy + self.K(17)), "LIFE", font=fl, fill=colore + (230,))
        fn = font(max(13, self.K(15)))
        tw = d.textlength(chi, font=fn)
        yn = cy - R - self.K(24) if sopra else cy + R + self.K(10)
        d.text((cx - tw / 2, yn), chi, font=fn, fill=colore + (255,))
        fv = font(max(12, self.K(13)), "SemiBold")
        yv = yn + (-self.K(26) if sopra else self.K(24))
        for i, (ic, v) in enumerate((("hand", mano), ("library", grimorio))):
            xx = cx - self.K(38) + i * self.K(46)
            self.icona(d, ic, xx, yv + self.K(8))
            d.text((xx + self.K(12), yv), str(v), font=fv, fill=(214, 218, 226))

    def icona(self, d, k, x, y):
        g = (150, 156, 168, 255)
        s = self.K
        w = max(1.0, s(1))
        if k == "hand":
            for i, dx in enumerate((-3, 2)):
                self.liscio(d, "rr", (x + s(dx) - s(4), y - s(6) + s(i), x + s(dx) + s(4), y + s(6) + s(i)), fill=(26, 28, 34, 255), outline=g, width=w, radius=s(1.5))
        else:
            for i in range(3):
                self.liscio(d, "rr", (x - s(4) + s(i), y - s(6) - s(i), x + s(4) + s(i), y + s(6) - s(i)), fill=(26, 28, 34, 255), outline=g, width=w, radius=s(1.5))

    # -- il momento
    def disegna(self, f, prima=None, rel=None, danni=None, grimorio=None, titolo="", mio_turno=True, pezzi=False):
        """Un momento: f la foto (dal tuo lato), prima la foto del passo prima (le carte nuove), rel la magia in pila o il combattimento, danni
        [(bersaglio, quanti)] dell'azione. -> (immagine RGB, scatole [(x0, y0, x1, y1, nome)], zone {chiave: (riquadro, carte)})."""
        self._pezzi = [] if pezzi else None
        self._etichette, self._grimori = {}, {}
        tela = self.fondo().copy()
        d = ImageDraw.Draw(tela)
        scatole, zone, pos = [], {}, {}
        # il passo, a sinistra sulla linea di mezzo
        ft = font(max(15, self.K(16)))
        col_t = BLU if mio_turno else ARANCIO
        parti = titolo.split(" · ", 1)
        self.pillola(d, self.X(86), self.Y(MEZZO), parti[0].upper(), ft, fondo=(10, 30, 44, 235) if mio_turno else (40, 28, 12, 235),
                     bordo=col_t + (255,), pad=9)
        if len(parti) > 1:
            fp = font(max(11, self.K(11)), "SemiBold")
            t2 = parti[1].upper()
            larga_t = min(self.K(150), 2 * (self.X(86) - self.K(18)))     # mai oltre il bordo del tappeto
            while d.textlength(t2, font=fp) > larga_t and len(t2) > 4:
                t2 = t2[:-2].rstrip(" .…") + "…"
            tw = d.textlength(t2, font=fp)
            d.text((self.X(86) - tw / 2, self.Y(MEZZO) + self.K(20)), t2, font=fp, fill=col_t + (220,))
        conta = lambda lst: {n: sum(1 for c in lst if c[0] == n) for n in {c[0] for c in lst}}
        vite = f.get("vite") or (None, None)
        cim, esi = f.get("cim") or ([], []), f.get("esi") or ([], [])
        for chi, col in (("suo", ARANCIO), ("mio", BLU)):
            gg = gruppi(f[chi])
            nuove = {}
            if prima is not None:
                ora_n, prima_n = conta(f[chi]), conta(prima[chi])
                nuove = {n: q - prima_n.get(n, 0) for n, q in ora_n.items() if q > prima_n.get(n, 0)}
            crea = [g for g in gg if g[3] is not None]
            terre = [g for g in gg if g[3] is None and e_terra(g[0])]
            altri = [g for g in gg if g[3] is None and not e_terra(g[0])]
            x0, y0, x1, y1 = self.box(ZONE[f"{chi}_crea"])
            self.fila(tela, d, crea, (x0 + self.K(10), y0 + self.K(18), x1 - self.K(10), y1 - self.K(6)), 140, col, nuove, scatole, pos, chi)
            x0, y0, x1, y1 = ZONE[f"{chi}_dietro"]
            xm = x0 + (x1 - x0) * SPLIT
            self.fila(tela, d, terre, self.box((x0 + 10, y0 + 18, xm - 16, y1 - 6)), 80, col, nuove, scatole, pos, chi)
            self.fila(tela, d, altri, self.box((xm + 16, y0 + 18, x1 - 10, y1 - 6)), 96, col, nuove, scatole, pos, chi)
        self.pila_zona(tela, d, "lib_suo", [], ARANCIO, n="?", retro=True)
        self.pila_zona(tela, d, "cim_suo", cim[1], ARANCIO, scatole=scatole, zone=zone)
        self.pila_zona(tela, d, "esi_suo", esi[1], ARANCIO, scatole=scatole, zone=zone)
        self.pila_zona(tela, d, "lib_mio", [], BLU, n=grimorio if grimorio is not None else "?", retro=True)
        self.pila_zona(tela, d, "cim_mio", cim[0], BLU, scatole=scatole, zone=zone)
        self.pila_zona(tela, d, "esi_mio", esi[0], BLU, scatole=scatole, zone=zone)
        self.giocatore(tela, d, "vita_suo", "OPPONENT", ARANCIO, vite[1], f.get("n_suo", 0), "?", False, pos)
        self.giocatore(tela, d, "vita_mio", "YOU", BLU, vite[0], len(f.get("mano") or []), grimorio if grimorio is not None else "?", True, pos)
        # la pila: la magia o l'abilita' di questo momento
        pila_box = None
        if rel and rel.get("tipo") == "spell":
            x0, y0, x1, y1 = self.box(STACK)
            h = (y1 - y0) - self.K(26)
            w = round(h / RAPP)
            im = faccia(rel["nome"], w)
            cx = (x0 + x1) / 2
            self.metti(tela, im, cx - w / 2, y0 + self.K(20), raggio=12, alfa=190)
            pila_box = (cx - w / 2, y0 + self.K(20), cx + w / 2, y0 + self.K(20) + h)
            scatole.append(pila_box + (rel["nome"],))
            fs = font(max(10, self.K(10)))
            et = ("YOURS" if rel.get("mio") else "OPPONENT'S") + (" · ABILITY" if rel.get("ab") else "")
            tw = d.textlength(et, font=fs)
            d.text((cx - tw / 2, y1 + self.K(4)), et, font=fs, fill=VIOLA + (230,))
        # le mani: la tua a ventaglio dal bordo basso, la sua di dorso dal bordo alto
        cxm = self.X(XB0 + (LC - XB0) / 2)
        fl = font(max(11, self.K(10.5)))
        mano = f.get("mano") or []
        wm = int(self.K(158))
        mie = [((n, wm), faccia(n, wm)) for n in mano]
        self.ventaglio(tela, mie, cxm, self.H + wm * RAPP / 2 - self.K(150), wm, 6, 0.30, False, scatole, self.K(760), "mano")
        n_suo = f.get("n_suo") or 0
        wr = int(self.K(92))
        self.ventaglio(tela, [(("dorso", wr), dorso(wr))] * n_suo, cxm, -wr * RAPP / 2 + self.K(100), wr, 6, 0.42, True, [], self.K(560), "mano_suo")
        larga_mano = min(len(mano) * wm * 0.7, self.K(760))
        self.pillola(d, cxm - larga_mano / 2 - self.K(110), self.H - self.K(50), f"YOUR HAND · {len(mano)}", fl, fondo=(10, 22, 32, 220),
                     bordo=BLU + (180,), colore=BLU)
        larga_suo = min(n_suo * wr * 0.58, self.K(560))
        self.pillola(d, cxm + larga_suo / 2 + self.K(110), self.K(50), f"OPPONENT'S HAND · {n_suo}", fl, fondo=(24, 18, 10, 220), bordo=ARANCIO + (160,),
                     colore=ARANCIO)
        if pezzi:       # l'app mette i pezzi come oggetti della tela; frecce e danni li disegna lei
            pz, self._pezzi = self._pezzi, None
            fuori = [s_ for s_ in scatole if not any(s_[:4] == q["box"] for q in pz)]
            return tela.convert("RGB"), pz, dict(vite={k: pos[k] for k in ("vita_mio", "vita_suo")}, pile=zone, pila=pila_box, scatole=fuori,
                                                 etichette=self._etichette, grimori=self._grimori)
        # le frecce: chi blocca chi, chi attacca chi, cosa bersaglia la magia in pila; i permanenti tolti; i danni
        self.frecce(tela, rel, pila_box, pos, zone)
        d = ImageDraw.Draw(tela)
        fd = font(self.K(14), "Bold")
        for bers, q in danni or []:
            r_ = pos.get(bers)
            if not r_ or not q:
                continue
            cx, cy = (r_[2] + self.K(18), (r_[1] + r_[3]) / 2) if str(bers).startswith("vita") else (r_[2] - self.K(4), r_[1] + self.K(4))
            R = self.K(17)
            self.liscio(d, "ell", (cx - R, cy - R, cx + R, cy + R), fill=(217, 83, 79, 255), outline=(255, 255, 255, 255), width=max(2.0, self.K(2)))
            t = f"-{q}"
            bb = d.textbbox((0, 0), t, font=fd)
            d.text((cx - (bb[2] - bb[0]) / 2 - bb[0], cy - (bb[3] - bb[1]) / 2 - bb[1]), t, font=fd, fill=(255, 255, 255))
        return tela.convert("RGB"), scatole, zone

    def frecce(self, tela, rel, pila_box, pos, zone):
        if not rel:
            return
        fr = []
        if rel.get("tipo") == "comb":
            bloccati = {a for _b, aa in rel["blocchi"] for a in aa}
            for b_, aa in rel["blocchi"]:
                for a in aa:
                    if pos.get(b_) and pos.get(a):
                        fr.append((pos[b_], pos[a], GIALLO))
            for a, tg in rel["att"]:
                if a not in bloccati and pos.get(a) and pos.get(tg):
                    fr.append((pos[a], pos[tg], ROSSO))
        elif rel.get("tipo") == "spell" and pila_box:
            sui_perm = bool(rel.get("colpiti")) and all(isinstance(tg, str) and tg.startswith("vita") for tg in rel["bers"])
            for tg in rel["bers"]:
                if sui_perm:
                    continue
                if pos.get(tg):
                    fr.append((pila_box, pos[tg], VIOLA))
                else:
                    z = (rel.get("fuori") or {}).get(tg, (None,))[0]
                    if z in zone:
                        fr.append((pila_box, zone[z][0], VIOLA))
            for k_ in rel.get("colpiti") or []:
                if k_ not in rel["bers"] and pos.get(k_):
                    fr.append((pila_box, pos[k_], ROSSO))
        colpiti = [pos[k_] for k_ in rel.get("colpiti") or [] if pos.get(k_)]
        if not fr and not colpiti:
            return
        S = 2
        lay = Image.new("RGBA", (self.W * S, self.H * S), (0, 0, 0, 0))
        d = ImageDraw.Draw(lay)

        def bordo(r, verso):
            cx, cy = (r[0] + r[2]) / 2, (r[1] + r[3]) / 2
            dx, dy = verso[0] - cx, verso[1] - cy
            if dx == 0 and dy == 0:
                return cx, cy
            sx = (r[2] - r[0]) / 2 / abs(dx) if dx else float("inf")
            sy = (r[3] - r[1]) / 2 / abs(dy) if dy else float("inf")
            k = min(sx, sy)
            return cx + dx * k, cy + dy * k
        for a, b, col in fr:
            ca, cb = ((a[0] + a[2]) / 2, (a[1] + a[3]) / 2), ((b[0] + b[2]) / 2, (b[1] + b[3]) / 2)
            p0, p2 = bordo(a, cb), bordo(b, ca)
            dx, dy = p2[0] - p0[0], p2[1] - p0[1]
            ctrl = ((p0[0] + p2[0]) / 2 - dy * 0.18, (p0[1] + p2[1]) / 2 + dx * 0.18)
            pts = [(((1 - u) ** 2 * p0[0] + 2 * (1 - u) * u * ctrl[0] + u * u * p2[0]) * S, ((1 - u) ** 2 * p0[1] + 2 * (1 - u) * u * ctrl[1] + u * u * p2[1]) * S)
                   for u in (i / 40 for i in range(41))]
            d.line(pts, fill=(0, 0, 0, 150), width=round(self.K(7) * S), joint="curve")
            d.line(pts, fill=col + (255,), width=round(self.K(3.5) * S), joint="curve")
            ux, uy = pts[-1][0] - pts[-4][0], pts[-1][1] - pts[-4][1]
            ul = max(1e-6, math.hypot(ux, uy))
            ux, uy = ux / ul, uy / ul
            t, L_, M_ = pts[-1], self.K(18) * S, self.K(9) * S
            d.polygon([t, (t[0] - L_ * ux + M_ * uy, t[1] - L_ * uy - M_ * ux), (t[0] - L_ * ux - M_ * uy, t[1] - L_ * uy + M_ * ux)], fill=col + (255,))
            r0 = self.K(5) * S
            d.ellipse((p0[0] * S - r0, p0[1] * S - r0, p0[0] * S + r0, p0[1] * S + r0), fill=col + (255,))
        fr_t = font(self.K(8) * S, "Bold")
        for r_ in colpiti:      # i permanenti che la magia ha tolto
            x0, y0, x1, y1 = (v * S for v in r_)
            d.rounded_rectangle((x0 - 4 * S, y0 - 4 * S, x1 + 4 * S, y1 + 4 * S), radius=self.K(6) * S, outline=ROSSO + (255,), width=round(self.K(3) * S))
            tw = d.textlength("REMOVED", font=fr_t)
            d.rounded_rectangle(((x0 + x1) / 2 - tw / 2 - 6 * S, y1 - self.K(26) * S, (x0 + x1) / 2 + tw / 2 + 6 * S, y1 - self.K(10) * S), radius=4 * S,
                                fill=ROSSO + (255,))
            d.text(((x0 + x1) / 2 - tw / 2, y1 - self.K(25) * S), "REMOVED", font=fr_t, fill=(255, 255, 255, 255))
        tela.alpha_composite(lay.resize((self.W, self.H), Image.LANCZOS))


def prova():
    """Disegna i momenti di una partita vera con le foto, alla misura del replayer: ogni passo senza errori, le carte in scatole dentro il tappeto,
    le terre sempre a sinistra degli altri permanenti; negative: una foto vuota disegna il tappeto senza carte."""
    import time
    import dati_analizzatore as DA
    casi = []
    R = [x for x in DA.righe() if DA.foto_partita(x)]
    casi.append(("ci sono partite con le foto", bool(R)))
    t = Tappeto(1560, 940)
    x = R[0]
    fo = DA.foto_partita(x)
    tempi, ok = [], True
    for _t, _m, f, _k, rel in fo["turni"][:12]:
        if not f:
            continue
        t0 = time.perf_counter()
        im, sc, _z = t.disegna(f, rel=rel)
        tempi.append(time.perf_counter() - t0)
        ok = ok and im.size == (1560, 940) and all(0 <= s_[0] and s_[2] <= 1560 + 40 for s_ in sc)
    casi.append((f"ogni momento disegnato ({len(tempi)}), le carte dentro il tappeto", ok and bool(tempi)))
    casi.append((f"un momento in meno di 0,6 s (mediana {sorted(tempi)[len(tempi) // 2] * 1000:.0f} ms)", sorted(tempi)[len(tempi) // 2] < 0.6))
    vuota = dict(mio=[], suo=[], mano=[], n_suo=0, vite=(20, 20), cim=([], []), esi=([], []))
    im, sc, _z = t.disegna(vuota)
    casi.append(("negativa: una foto vuota non mette carte", sc == []))
    f2 = dict(vuota, mio=[("Plains", False, False, None, None, 1), ("Sol Ring", False, False, None, None, 2)])
    _im, sc, _z = t.disegna(f2)
    xs = {s_[4]: s_[0] for s_ in sc}
    casi.append(("le terre a sinistra degli artefatti", xs.get("Plains", 9e9) < xs.get("Sol Ring", -1)))
    for n, v in casi:
        print(("OK   " if v else "ROSSO") + " " + n)
    print(f"{sum(v for _n, v in casi)}/{len(casi)}")
    return all(v for _n, v in casi)


if __name__ == "__main__":
    if "--prova" in sys.argv:
        sys.exit(0 if prova() else 1)
