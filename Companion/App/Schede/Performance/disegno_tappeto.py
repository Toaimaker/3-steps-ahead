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
from collections import Counter

_casa = os.path.dirname(os.path.abspath(__file__))
while not os.path.isfile(os.path.join(_casa, "percorsi.py")):
    _casa = os.path.dirname(_casa)
if _casa not in sys.path:
    sys.path.insert(0, _casa)
import percorsi  # noqa: E402,F401

from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter, ImageFont  # noqa: E402

DW, DH = 1600, 1000                     # le coordinate del progetto: tutto si scala sulla misura vera
BLU, ARANCIO, VIOLA, ROSSO, GIALLO = (36, 186, 255), (240, 173, 78), (181, 140, 255), (255, 93, 93), (255, 210, 63)
FONDO = (16, 16, 20)
RAPP = 279 / 200
CREA_FILA = 6                            # oltre 6 gruppi di creature su un lato: due file
MIN_FILA = 0.8                           # le carte di una fila non scendono sotto l'80% della misura piena: poi si sovrappongono


def _font_file():
    """Bahnschrift (Windows 10 e 11, condensato); dove non c'e' (Mac) il Poppins dell'app."""
    for f in (os.path.join(os.environ.get("WINDIR", "C:" + os.sep + "Windows"), "Fonts", "bahnschrift.ttf"),
              os.path.join(_casa, "Grafica", "Poppins-Medium.ttf")):
        if os.path.isfile(f):
            return f
    return "DejaVuSans.ttf"


BAHN = _font_file()
# le colonne e le righe del tappeto, nelle coordinate del progetto
MEZZO = DH / 2
SPLIT = 0.56                            # nella fila dietro: le terre fino al 56% della larghezza
# la riserva di mana (15 nov 2026, Autore: «costruiamolo invece in basso a sx poco sotto l'area your lands cosi' vediamo il mana accumulato e poi
# speso»): una vaschetta sotto le tue terre (la sua sopra le sue), dove arrivano i simboli dalle terre e da dove partono verso la magia
POOL_W, POOL_TESTO = 236, 64            # larga; lo spazio della scritta MANA a sinistra, poi i simboli
POOL_MAX_SOLI = 6                       # oltre, i simboli uguali si impilano col numero (15 nov 2026)
SCUDO_W, SCUDO_H = 34, 41               # gli scudi degli emblemi sotto il cerchio delle vite (15 nov 2026)
# i colori degli scudi: il colore della carta (W U B R G), oro se multicolore, grigio se incolore
COLORI_SCUDO = dict(W=(236, 226, 186), U=(52, 132, 226), B=(64, 56, 72), R=(214, 58, 46), G=(36, 150, 84), M=(214, 170, 60), C=(150, 156, 168))
_PARADIGMI = None


def paradigmi():
    """{nome della carta: i suoi colori} delle carte con Paradigm, dal pool dello Standard (15 nov 2026, Autore: «cerca tutti i paradigm e crea i loro
    scudi»). Paradigm (SOS): dopo la prima risoluzione la carta resta in esilio e a ogni tua prima fase principale puoi lanciarne una copia gratis; quindi
    una carta con Paradigm nell'esilio del suo proprietario e' un Paradigm attivo (grado C: un esilio da un altro effetto non si distingue). I set nuovi
    con la parola entrano da soli dopo aggiorna_standard.py."""
    global _PARADIGMI
    if _PARADIGMI is None:
        _PARADIGMI = {}
        try:
            import json
            with open(os.path.join(percorsi.ROOT, "Regole", "standard_carte.json"), encoding="utf-8") as fh:
                for c_ in json.load(fh):
                    if "Paradigm" in (c_.get("oracle") or ""):
                        _PARADIGMI[c_["name"]] = c_.get("colors") or ""
                        _PARADIGMI[c_["name"].split(" // ")[0]] = c_.get("colors") or ""
        except (OSError, ValueError):
            pass
    return _PARADIGMI


_FINCHE = None


def finche():
    """I nomi delle carte che esiliano «finche' questa lascia il campo» (610.3), dal pool dello Standard (15 nov 2026, il censimento: «esilia_finche»):
    Seam Rip, Deep-Cavern Bat, Sheltered by Ghosts, Banishing Light... Arena mette la carta esiliata sotto la fonte (DisplayCardUnderCard, 196 esili su
    196 nelle ultime 400 partite); la fonte che ne tiene una porta la catena. Grado C dal testo."""
    global _FINCHE
    if _FINCHE is None:
        _FINCHE = set()
        try:
            import json, re
            rx = re.compile(r"until (?:~|this|it|that|.{0,40}?) leaves the battlefield", re.I)
            with open(os.path.join(percorsi.ROOT, "Regole", "standard_carte.json"), encoding="utf-8") as fh:
                for c_ in json.load(fh):
                    if rx.search(c_.get("oracle") or ""):
                        _FINCHE.add(c_["name"])
                        _FINCHE.add(c_["name"].split(" // ")[0])
        except (OSError, ValueError):
            pass
    return _FINCHE


_CATENE = {}


def icona_catena(px):
    """La catena della fonte che tiene una carta in esilio «finche'» (15 nov 2026): due anelli viola intrecciati su un tondo scuro col bordo bianco,
    disegnati a 4x. -> immagine px x px."""
    if px in _CATENE:
        return _CATENE[px]
    k = 4
    W = px * k
    im = Image.new("RGBA", (W, W), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.ellipse((k, k, W - k, W - k), fill=(22, 18, 38, 240), outline=(255, 255, 255, 230), width=max(2, round(W * 0.06)))
    lw = max(3, round(W * 0.10))
    a, b = W * 0.30, W * 0.18          # gli anelli: ovali inclinati, uno sopra l'altro sfalsato
    for cx_, cy_ in ((W * 0.40, W * 0.40), (W * 0.60, W * 0.60)):
        anello = Image.new("RGBA", (W, W), (0, 0, 0, 0))
        ImageDraw.Draw(anello).ellipse((cx_ - a, cy_ - b, cx_ + a, cy_ + b), outline=(196, 160, 255, 255), width=lw)
        im.alpha_composite(anello.rotate(45, center=(cx_, cy_), resample=Image.BICUBIC))
    im = im.resize((px, px), Image.LANCZOS)
    _CATENE[px] = im
    return im


def colore_scudo(colori):
    colori = [c_ for c_ in (colori or "") if c_ in "WUBRG"]
    return COLORI_SCUDO["M" if len(colori) > 1 else (colori[0] if colori else "C")]


def disposizione(mano=True):
    """Le zone del tappeto nelle coordinate del progetto (DW x DH), nei due modi del replayer.

    14 nov 2026 (Autore: «spostiamo pt vita e turni in maniera ordinata nell'area a destra e ingrandiamo tutto scalando nello spazio rimasto a sx»): a
    destra, per ogni giocatore, il triangolo di grimorio, cimitero ed esilio (stesso giorno: «possiamo disporre mazzo cimitero e esilio a triangolo e
    aumentare le dimensioni?»), col cerchio delle vite nell'angolo accanto al grimorio e nell'altro angolo il nome con le carte in mano e nel grimorio; il
    turno sulla linea di mezzo fra i due triangoli; la pila accanto al campo. Il campo parte quasi dal bordo sinistro (fino a quel giorno le vite e il turno
    stavano a sinistra, XB0 170).
    mano=False (stesso giorno: «permetti lo zoom dinamico > in hand e' la versione attuale e se va off la mano a ventaglio scompare e si sposta lo zoom sul
    tavolo ingrandendo tutto e la mano viene messa in riga piu' piccola»): niente ventaglio; le file del campo prendono l'altezza delle mani e le carte
    crescono (WMAX), la tua mano e' una riga di carte piccole in fondo, la sua una riga di dorsi in cima."""
    # la pila non ha piu' una colonna sua: compare al centro del tavolo solo quando c'e' una magia o un'abilita' (14 nov 2026, Autore: «la pila falla
    # apparire solo quando si gioca al centro del tavolo e poi sparisce quando non serve, cosi' aumentiamo lo spazio per le aree»); il campo arriva all'area
    # di destra (era fino a 1096, con la pila accanto)
    XB0, LC = 24, 1216
    ZX0, ZX1 = 1232, 1584
    ZXM = (ZX0 + ZX1) / 2
    # a sinistra del campo, sulla linea di mezzo, grande (stesso giorno: «falla piu' grande la pila, falla apparire a sx del campo di battaglia»)
    STACK = (XB0 + 10, MEZZO - 150, XB0 + 10 + 196, MEZZO + 150)
    if mano:
        su, giu = 96, 904           # dove finiscono le mani a ventaglio
        Z = dict(suo_dietro=(XB0, 104, LC, 236), suo_crea=(XB0, 244, LC, MEZZO - 14),
                 mio_crea=(XB0, MEZZO + 14, LC, MEZZO + 240), mio_dietro=(XB0, MEZZO + 248, LC, MEZZO + 370),
                 pool_suo=(XB0, 64, XB0 + POOL_W, 98), pool_mio=(XB0, MEZZO + 376, XB0 + POOL_W, MEZZO + 410))
        wmax = dict(crea=140, terre=100, altri=110)
    else:
        # la mano al centro della fila dietro, fra le terre (piu' strette) e gli altri permanenti (14 nov 2026, Autore: «stringendo area terre la mano la
        # mettiamo al centro tra i permanenti di dx e le terre di sx»); prima stava in una riga piccola in fondo, e la sua in cima
        su, giu = 24, 976
        Z = dict(suo_dietro=(XB0, 58, LC, 184), suo_crea=(XB0, 192, LC, MEZZO - 10),
                 mio_crea=(XB0, MEZZO + 10, LC, MEZZO + 308), mio_dietro=(XB0, MEZZO + 316, LC, MEZZO + 442),
                 pool_suo=(XB0, 16, XB0 + POOL_W, 50), pool_mio=(XB0, MEZZO + 450, XB0 + POOL_W, MEZZO + 484))
        wmax = dict(crea=180, terre=124, altri=134, mano=124)
    alto_lib = (MEZZO - 40 - su) / 2        # il triangolo: il grimorio verso il bordo, cimitero ed esilio verso la linea di mezzo
    Z.update(lib_suo=(ZXM - 64, su, ZXM + 64, su + alto_lib - 3), cim_suo=(ZX0, su + alto_lib + 3, ZXM - 2, MEZZO - 40),
             esi_suo=(ZXM + 2, su + alto_lib + 3, ZX1, MEZZO - 40),
             cim_mio=(ZX0, MEZZO + 40, ZXM - 2, MEZZO + 40 + alto_lib - 3), esi_mio=(ZXM + 2, MEZZO + 40, ZX1, MEZZO + 40 + alto_lib - 3),
             lib_mio=(ZXM - 64, MEZZO + 40 + alto_lib + 3, ZXM + 64, giu))
    yl_s = (Z["lib_suo"][1] + Z["lib_suo"][3]) / 2
    yl_m = (Z["lib_mio"][1] + Z["lib_mio"][3]) / 2
    # la fila dietro: le terre a sinistra e gli altri permanenti a destra; col tavolo ingrandito in mezzo la mano
    dietro = (("terre", 0.0, SPLIT), ("altri", SPLIT, 1.0)) if mano else (("terre", 0.0, 0.36), ("mano", 0.36, 0.62), ("altri", 0.62, 1.0))
    return dict(XB0=XB0, LC=LC, ZX0=ZX0, ZX1=ZX1, ZXM=ZXM, STACK=STACK, ZONE=Z, WMAX=wmax, mano=mano, DIETRO=dietro,
                VITA=dict(vita_suo=((ZX0 + ZXM - 64) / 2, yl_s), vita_mio=((ZX0 + ZXM - 64) / 2, yl_m)),
                NOMI=dict(vita_suo=((ZX1 + ZXM + 64) / 2, yl_s), vita_mio=((ZX1 + ZXM + 64) / 2, yl_m)),
                TURNO=(ZXM, MEZZO), MANO=(XB0 + (LC - XB0) / 2, su, giu))


_D = disposizione(True)          # per chi legge le zone da fuori (le prove): il modo con la mano
XB0, LC, ZX0, ZX1, ZXM, STACK, ZONE, VITA = (_D[k] for k in ("XB0", "LC", "ZX0", "ZX1", "ZXM", "STACK", "ZONE", "VITA"))


def e_terra(nome):
    import mazzi_salvati as MS
    return MS.e_terra(nome)


_FONT = {}
_ICONE_AB = {}


STATO_COLORI = {"no": (196, 44, 56, 245), "si": (15, 134, 204, 245), "off": (84, 88, 98, 245), "liv": (176, 132, 30, 245), "col": (52, 58, 70, 245)}
_ICONE_ST = {}


def icona_stato(genere, lato):
    """Il segno dello stato della carta, bianco, disegnato a 4x (15 nov 2026): divieto = cerchio barrato, permesso = freccia, esausta = cerchio vuoto
    col trattino, livello = due chevron in su."""
    k = (genere, lato)
    if k not in _ICONE_ST:
        L = lato * 4
        im = Image.new("RGBA", (L, L), (255, 255, 255, 0))
        d = ImageDraw.Draw(im)
        w = max(4, L // 8)
        b = (255, 255, 255, 255)
        if genere == "no":
            d.ellipse((w // 2, w // 2, L - w // 2, L - w // 2), outline=b, width=w)
            d.line((L * 0.24, L * 0.76, L * 0.76, L * 0.24), fill=b, width=w)
        elif genere == "si":
            d.line((L * 0.14, L * 0.5, L * 0.8, L * 0.5), fill=b, width=w)
            d.polygon([(L * 0.92, L * 0.5), (L * 0.56, L * 0.18), (L * 0.56, L * 0.82)], fill=b)
        elif genere == "col":       # il colore cambiato: una goccia di colore piena
            d.ellipse((L * 0.16, L * 0.16, L * 0.84, L * 0.84), fill=b)
        elif genere == "off":
            d.ellipse((w // 2, w // 2, L - w // 2, L - w // 2), outline=b, width=w)
            d.line((L * 0.3, L * 0.5, L * 0.7, L * 0.5), fill=b, width=w)
        else:
            for y_ in (0.62, 0.32):
                d.line([(L * 0.18, L * (y_ + 0.2)), (L * 0.5, L * y_), (L * 0.82, L * (y_ + 0.2))], fill=b, width=w, joint="curve")
        _ICONE_ST[k] = im.resize((lato, lato), Image.LANCZOS)
    return _ICONE_ST[k]


def icona_abilita(nome, lato):
    """Il simbolo di una parola chiave (15 nov 2026, Autore: «accanto ai testi che mettiamo sulle carte come life link e trample possiamo inserire i
    loghi originali?»): gli svg delle abilita' del font Mana di Andrew Gioia (github.com/andrewgioia/mana, simboli di Wizards of the Coast; font OFL), in
    Companion/Grafica/abilita/, resi bianchi a 4x con PyMuPDF e ridotti. «first strike» -> firststrike.svg. None se la parola non ha un simbolo."""
    f_ = os.path.join(_casa, "Grafica", "abilita", nome.lower().replace(" ", "").replace("-", "") + ".svg")
    k = (f_, lato)
    if k not in _ICONE_AB:
        _ICONE_AB[k] = None
        if os.path.isfile(f_):
            try:
                import re
                try:
                    import pymupdf as fitz
                except ImportError:
                    import fitz
                testo = re.sub(r'fill="#[0-9a-fA-F]{3,6}"', 'fill="#000000"', open(f_, encoding="utf-8").read())
                pg = fitz.open(stream=testo.encode("utf-8"), filetype="svg")[0]
                z = lato * 4 / max(pg.rect.width, pg.rect.height)
                pm = pg.get_pixmap(matrix=fitz.Matrix(z, z), alpha=True)
                a = Image.frombytes("RGBA", (pm.width, pm.height), pm.samples).getchannel("A")
                w_, h_ = max(1, round(pm.width / 4)), max(1, round(pm.height / 4))
                out = Image.new("RGBA", (w_, h_), (255, 255, 255, 0))
                out.putalpha(a.resize((w_, h_), Image.LANCZOS))
                _ICONE_AB[k] = out
            except Exception:      # noqa: BLE001 - senza PyMuPDF la pillola resta senza simbolo
                pass
    return _ICONE_AB[k]
_LISCI = {}          # le forme lisce gia' ridotte (liscio)


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

from marchio import logo_carte  # noqa: E402  le tre carte del logo, le stesse del marchio di scheda mazzo, builder e Board (16 nov 2026)


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
PEDINE_ATTESA = set()       # le pedine disegnate col riquadro perche' l'immagine non e' ancora arrivata: chi disegna ridisegna quando c'e' (pedine.py)


def faccia(nome, w, tappata=False, pedina=None):
    """La carta vera larga w (girata se tappata), angoli arrotondati; dall'immagine intera se c'e', se no dalla miniatura cotta; senza immagine un
    riquadro col nome. pedina: il grpId di una pedina, che prende l'immagine della pedina vera da Scryfall (pedine.py; 14 nov 2026, Autore: «troviamo
    delle immagini arena per i token o le pedine»); una pedina che copia una carta ha il nome della carta e ne usa l'immagine. Finche' l'immagine della
    pedina non e' scaricata resta il riquadro col nome (e non si tiene: al prossimo disegno c'e')."""
    w = max(8, int(w))
    k = (nome, w, tappata, pedina)
    if k in _FACCE:
        return _FACCE[k]
    import capsule
    h = round(w * RAPP)
    im = None
    file_ = [capsule.file_immagine(nome), capsule.file_mini(nome)]
    if pedina and not any(nome and os.path.isfile(f) for f in file_):
        import pedine
        fp = pedine.immagine(pedina, nome)
        if fp is None:
            if pedine.file(pedina) not in ("", None) and pedine._indice().get(int(pedina)) != "":
                PEDINE_ATTESA.add(int(pedina))
            return carta_angoli(carta_vuota(nome, w, h), w, h, tappata)
        file_ = [fp]
    for f in file_:
        if nome and os.path.isfile(f):
            try:
                im = Image.open(f).convert("RGBA").resize((w, h), Image.LANCZOS)
                break
            except Exception:      # noqa: BLE001 - un file rotto: il riquadro
                im = None
    if im is None:
        im = carta_vuota(nome, w, h)
    _FACCE[k] = carta_angoli(im, w, h, tappata)
    return _FACCE[k]


def carta_angoli(im, w, h, tappata):
    m = Image.new("L", (w * 3, h * 3), 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, w * 3 - 1, h * 3 - 1), radius=w * 3 * 0.048, fill=255)
    im.putalpha(ImageChops.multiply(im.getchannel("A"), m.resize((w, h), Image.LANCZOS)))
    if tappata:
        im = im.rotate(90, expand=True)
        vel = Image.new("RGBA", im.size, (0, 0, 0, 70))
        vel.putalpha(ImageChops.multiply(vel.getchannel("A"), im.getchannel("A")))
        im = Image.alpha_composite(im, vel)
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


BLU_PT, ROSSO_PT, NEUTRO_PT = (28, 118, 220, 250), (205, 52, 52, 250), (20, 22, 28, 240)
_PT = {}


def pt_stampati(grp):
    """(forza, costituzione) stampate sulla carta di Arena grp (database di Arena, db_carte), None se non si sanno. Una volta per grpId."""
    if grp is None:
        return None
    if grp not in _PT:
        try:
            if "indice" not in _PT:     # l'indice per grpId, una volta per processo
                import db_carte
                _PT["indice"] = {c_.get("grpid"): c_ for c_ in db_carte.carte()}
            c = _PT["indice"].get(grp)
            _PT[grp] = (int(c.get("power") or 0), int(c.get("toughness") or 0)) if c and c.get("toughness") not in (None, "") else None
        except (Exception, ValueError):      # noqa: BLE001 - * o X: non si confronta
            _PT[grp] = None
    return _PT[grp]


FACCIA_GIU = "Face-down card"
ORO_G = (240, 192, 64)          # le carte giocabili da fuori della mano (E1)
VERDE_W = (46, 180, 92)         # la parola d'abilita' attiva (W2)


def giocabile_esilio(nome):
    """Una carta in esilio che chi la possiede puo' ancora giocare (grado C, dal testo: foretell, plot, warp, suspend, avventura; cimitero.DALL_ESILIO), o
    una carta esiliata a faccia in giu' (di solito il foretell)."""
    if nome == FACCIA_GIU:
        return True
    try:
        import cimitero as CM
        import dati_analizzatore as DA
        c = DA._carta(nome) or {}
    except Exception:      # noqa: BLE001 - senza i dati delle carte non si sa
        return False
    return bool(CM.DALL_ESILIO.search(c.get("testo") or "")) or "Adventure" in (c.get("tipo") or "")


def dall_esilio(im):
    """La carta giocabile da fuori della mano (esilio o cimitero), nella fila accanto alla mano: il bordo d'oro e PLAYABLE in testa (14 nov 2026, E1
    scelto da Autore fra tre disegni: «accanto alla mano oro»; prima il bordo viola e EXILE)."""
    k = 3
    w, h = im.size
    out = im.copy()
    st = Image.new("RGBA", (w * k, h * k), (0, 0, 0, 0))
    d = ImageDraw.Draw(st)
    d.rounded_rectangle((k, k, w * k - k, h * k - k), radius=max(4, w // 12) * k, outline=ORO_G + (255,), width=max(3, w // 26) * k)
    st = st.resize((w, h), Image.LANCZOS)
    out.alpha_composite(st)
    d2 = ImageDraw.Draw(out)
    f = font(max(8, w // 9), "Bold")
    tw = d2.textlength("PLAYABLE", font=f)
    bh = max(10, w // 7)
    d2.rounded_rectangle(((w - tw) / 2 - 5, 3, (w + tw) / 2 + 5, 3 + bh), radius=bh // 2, fill=ORO_G + (250,), outline=(255, 255, 255, 230))
    bb = d2.textbbox((0, 0), "PLAYABLE", font=f)
    d2.text(((w - tw) / 2 - bb[0], 3 + (bh - (bb[3] - bb[1])) / 2 - bb[1]), "PLAYABLE", font=f, fill=(58, 37, 0))
    return out


_TRIANGOLI = {}


def icona_triangolo(lato, su):
    """Il triangolo scuro a 4x, in su (in cima) o in giu' (in fondo): il font non ha i segni (15 nov 2026)."""
    k = (lato, su)
    if k not in _TRIANGOLI:
        L = lato * 4
        im = Image.new("RGBA", (L, L), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        pt = [(L * 0.5, L * 0.12), (L * 0.95, L * 0.88), (L * 0.05, L * 0.88)] if su else [(L * 0.05, L * 0.12), (L * 0.95, L * 0.12), (L * 0.5, L * 0.88)]
        d.polygon(pt, fill=(58, 37, 0, 255))
        _TRIANGOLI[k] = im.resize((lato, lato), Image.LANCZOS)
    return _TRIANGOLI[k]


_OCCHI = {}


def icona_occhio(lato, aperto):
    """L'occhio bianco a 4x: aperto (lo vedono tutti e due) o chiuso, una palpebra (lo sai solo tu). 15 nov 2026."""
    k = (lato, aperto)
    if k not in _OCCHI:
        L = lato * 4
        im = Image.new("RGBA", (L, L), (255, 255, 255, 0))
        d = ImageDraw.Draw(im)
        w = max(3, L // 10)
        b = (255, 255, 255, 255)
        if aperto:
            d.chord((L * 0.04, L * 0.18, L * 0.96, L * 0.82), 200, 340, outline=b, width=w)
            d.chord((L * 0.04, L * 0.18, L * 0.96, L * 0.82), 20, 160, outline=b, width=w)
            d.ellipse((L * 0.34, L * 0.34, L * 0.66, L * 0.66), fill=b)
        else:
            d.arc((L * 0.04, L * 0.05, L * 0.96, L * 0.75), 20, 160, fill=b, width=w)
            for x_ in (0.22, 0.5, 0.78):
                d.line((L * x_, L * 0.68, L * (x_ + (x_ - 0.5) * 0.3), L * 0.88), fill=b, width=max(2, w * 2 // 3))
        _OCCHI[k] = im.resize((lato, lato), Image.LANCZOS)
    return _OCCHI[k]


def frase_sostituzione(t):
    """Di un testo con una sostituzione («...If that creature would die this turn, exile it instead.») la sola frase della sostituzione (16 nov 2026);
    gli altri testi restano come sono."""
    import re
    for f_ in re.split(r"(?<=\.)\s+", t or ""):
        if "would" in f_ and "instead" in f_:
            return f_.strip()
    return t


def giocabile(im):
    """La carta della tua mano che in questo passo potevi giocare (16 nov 2026, le azioni legali che Arena manda a ogni tua priorita'): il bordo luminoso
    azzurro come in Arena, dentro la carta."""
    from PIL import ImageFilter
    k = 3
    w, h = im.size
    out = im.copy()
    st = Image.new("RGBA", (w * k, h * k), (0, 0, 0, 0))
    d = ImageDraw.Draw(st)
    r_ = max(4, w // 12) * k
    d.rounded_rectangle((k, k, w * k - k, h * k - k), radius=r_, outline=(90, 205, 255, 230), width=max(5, w // 14) * k)
    alone = st.filter(ImageFilter.GaussianBlur(4 * k))
    d2 = ImageDraw.Draw(alone)
    d2.rounded_rectangle((k, k, w * k - k, h * k - k), radius=r_, outline=(170, 235, 255, 255), width=max(2, w // 45) * k)
    out.alpha_composite(alone.resize((w, h), Image.LANCZOS))
    return out


def mostrata(im):
    """La carta della tua mano che l'avversario ha visto (15 nov 2026): il bordo azzurro e, in fondo, la pillola con l'occhio e SHOWN."""
    k = 3
    w, h = im.size
    out = im.copy()
    st = Image.new("RGBA", (w * k, h * k), (0, 0, 0, 0))
    d = ImageDraw.Draw(st)
    d.rounded_rectangle((k, k, w * k - k, h * k - k), radius=max(4, w // 12) * k, outline=(47, 155, 255, 255), width=max(3, w // 30) * k)
    bh = max(12, w // 6) * k
    y0 = int(h * 0.13) * k       # sotto la barra del nome, a sinistra: nel ventaglio la carta accanto copre la destra
    f = font(max(8, w // 9) * k, "Bold")
    tw = d.textlength("SHOWN", font=f)
    occ = bh * 0.9
    x0 = 6 * k
    d.rounded_rectangle((x0, y0, x0 + tw + occ + 16 * k, y0 + bh), radius=bh // 2, fill=(15, 70, 140, 245), outline=(255, 255, 255, 230), width=k)
    ex, ey, er = x0 + 8 * k + occ / 2, y0 + bh / 2, occ / 2
    d.ellipse((ex - er, ey - er * 0.55, ex + er, ey + er * 0.55), outline=(255, 255, 255, 255), width=max(2, k * 2))
    d.ellipse((ex - er * 0.28, ey - er * 0.28, ex + er * 0.28, ey + er * 0.28), fill=(255, 255, 255, 255))
    bb = d.textbbox((0, 0), "SHOWN", font=f)
    d.text((ex + er + 4 * k - bb[0], ey - (bb[3] - bb[1]) / 2 - bb[1]), "SHOWN", font=f, fill=(255, 255, 255, 255))
    out.alpha_composite(st.resize((w, h), Image.LANCZOS))
    return out


def gruppi(carte, soli=(), segni=None):
    """Le carte del campo: [nome, tappata, pedina, forza, costituzione, quante, [id], grpId, segnalini] nell'ordine di arrivo. Le pedine uguali e le terre
    uguali (stessi segnalini compresi) stanno insieme col ×N; ogni altra carta sta da sola anche se ce n'e' un'altra uguale (14 nov 2026, Autore: «se ci
    sono carte non pedina doppie sul tavolo non impiliamole ma che siano ognuna individuale», poi «terre possono restare impilate se sono simili»). soli: gli
    id che stanno da soli comunque (chi attacca o blocca: ognuno ha la sua freccia e il suo colpo; stesso giorno: «2 attaccanti si impilano nascondendo uno
    sotto l'altro»).
    La regola delle pedine (15 nov 2026, Autore: «se piu' asset come pedine sono uguali e di pari forza e costituzione allora li teniamo impilati con un
    numero quantita' mentre se hanno differenti forze o costituzioni li sleghiamo, e li sleghiamo nei combattimenti / vedo che non accade sempre»): stanno
    insieme le pedine con lo stesso nome, la stessa forza e costituzione, gli stessi segnalini, gli stessi segni (segni: {id: dict}, i segni del tappeto) e
    la stessa posizione (tappate o no); una diversa in una di queste cose sta a parte. Fino a quel giorno le pedine creatura stavano insieme solo da 4 in su
    (14 nov 2026, contro la fila che si rifaceva di colpo: ora le carte scivolano al posto nuovo) e una pedina con un segno stava sempre da sola."""
    out, idx = [], {}
    segni = segni or {}
    for c in carte:
        seg = c[7] if len(c) > 7 else None
        sg_ = segni.get(c[5]) if len(c) > 5 else None
        k = (c[0], c[1], c[2], c[3] if len(c) > 3 else None, c[4] if len(c) > 4 else None, tuple(sorted((seg or {}).items())),
             repr(sorted(sg_.items(), key=lambda kv: str(kv[0]))) if sg_ else None)
        da_solo = (len(c) > 5 and c[5] in soli) or (bool(sg_) and not c[2])
        if (c[2] or e_terra(c[0])) and k in idx and not da_solo:
            g = out[idx[k]]
            g[5] += 1
        else:
            if not da_solo:
                idx[k] = len(out)
            g = [k[0], k[1], k[2], k[3], k[4], 1, [], c[6] if len(c) > 6 else None, seg]
            out.append(g)
        if len(c) > 5 and c[5] is not None:
            g[6].append(c[5])
    return out


# ---------------------------------------------------------------- il tappeto

class Tappeto:
    """Un tappeto di misura W x H. disegna(...) -> (immagine RGB, scatole), le scatole per il passaggio del mouse e i clic."""

    def __init__(self, W, H, mano=True):
        self.W, self.H = int(W), int(H)
        self.mano = bool(mano)
        self.L = disposizione(self.mano)
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
            g2 = Tappeto(self.W * 2, self.H * 2, self.mano)
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
        xc = self.L["XB0"] + (self.L["LC"] - self.L["XB0"]) / 2        # il centro del campo
        logo_carte(ImageDraw.Draw(fil), self.X(xc - 10), self.Y(MEZZO), self.K(300), self.K(3), fondo=(0, 0, 0, 0))
        fil.putalpha(fil.getchannel("A").point(lambda v: int(v * 0.035)))       # piu' leggero (14 nov 2026: «il logo al centro meno visibile»)
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
        for x0, x1 in ((self.L["XB0"], xc - 60), (xc + 60, self.L["LC"])):
            d.line((self.X(x0), self.Y(MEZZO), self.X(x1), self.Y(MEZZO)), fill=(150, 190, 230, 55), width=max(1, round(self.K(1.5))))
        # il medaglione col logo sulla linea di mezzo, su uno strato a parte e al 40% (14 nov 2026, Autore: «il logo al centro del tappetino meno visibile
        # e' troppo invasivo»): fino a quel giorno pieno, col cerchio azzurro
        cxm, cym = self.X(xc), self.Y(MEZZO)
        med = Image.new("RGBA", (L, A), (0, 0, 0, 0))
        dm = ImageDraw.Draw(med)
        for rr, fi, ou in ((46, None, (150, 190, 230, 50)), (36, (14, 18, 24, 200), BLU + (110,))):
            dm.ellipse((cxm - self.K(rr), cym - self.K(rr), cxm + self.K(rr), cym + self.K(rr)), fill=fi, outline=ou, width=max(1, round(self.K(1.5))))
        logo_carte(dm, cxm + self.K(1), cym, self.K(54), self.K(1.5), fondo=(22, 24, 30))
        med.putalpha(med.getchannel("A").point(lambda v: int(v * 0.4)))
        t.alpha_composite(med)
        # il marchio in basso a destra (15 nov 2026, Autore: «nel tappetino del replayer in basso a destra mettiamo il logo e il nome del prodotto»): le
        # tre carte del logo e 3 STEPS AHEAD, come stampati sul feltro, discreti
        mar = Image.new("RGBA", (L, A), (0, 0, 0, 0))
        dmr = ImageDraw.Draw(mar)
        # e sotto l'indirizzo del sito (stesso giorno: «e sotto ancora l'indirizzo internet»; Distribuzione/config.json: github_utente e github_repo)
        fmr = font(max(10 * self.sup, self.K(14)), "Bold")
        fur = font(max(8 * self.sup, self.K(10)))
        testo_mr, url_mr = "3 STEPS AHEAD", "toaimaker.github.io/3-steps-ahead"
        bb_mr = dmr.textbbox((0, 0), testo_mr, font=fmr)
        bb_ur = dmr.textbbox((0, 0), url_mr, font=fur)
        larga_mr = max(bb_mr[2] - bb_mr[0], bb_ur[2] - bb_ur[0])
        lato_mr = self.K(36)
        y_c = A - self.K(36)
        x_t = L - self.K(34) - larga_mr
        lib_ = self.box(self.L["ZONE"]["lib_mio"])
        if lib_[3] > y_c - self.K(22) and lib_[2] > x_t - lato_mr - self.K(10):
            # col tavolo ingrandito il grimorio arriva fino in fondo: il marchio va sotto l'area dei tuoi artefatti e incantesimi, al centro (stesso giorno,
            # Autore: «nella versione zoomata il marchio spostalo sotto area ench e artifacts»)
            ax0, _ay0, ax1, _ay1 = self.box(self.dietro("mio")["altri"])
            x_t = (ax0 + ax1) / 2 - (larga_mr - lato_mr - self.K(8)) / 2
        logo_carte(dmr, x_t - self.K(8) - lato_mr / 2, y_c, lato_mr, self.K(1.6), fondo=(16, 20, 28))
        dmr.text((x_t - bb_mr[0], y_c - self.K(3) - bb_mr[3]), testo_mr, font=fmr, fill=(200, 215, 230, 255))
        dmr.text((x_t - bb_ur[0], y_c + self.K(3) - bb_ur[1]), url_mr, font=fur, fill=(150, 185, 215, 255))
        mar.putalpha(mar.getchannel("A").point(lambda v: int(v * 0.55)))
        t.alpha_composite(mar)
        d = ImageDraw.Draw(t)
        # le zone stampate
        Z = self.L["ZONE"]
        for chi, col, nome in (("suo", ARANCIO, "OPPONENT · "), ("mio", BLU, "YOUR ")):
            self.slot(d, Z[f"{chi}_crea"], f"{nome}CREATURES", col, fl, 40)
            nomi_d = dict(terre=f"{nome}LANDS", mano="YOUR HAND" if chi == "mio" else "OPPONENT'S HAND",
                          altri=f"{nome}{'ARTIFACTS · ENCHANTMENTS · PLANESWALKERS' if self.mano else 'OTHER PERMANENTS'}")
            for k_, (bx0, _y0, bx1, _y1) in self.dietro(chi).items():
                self.slot(d, (bx0, _y0, bx1, _y1), nomi_d[k_], col, fl, 40)
            for z in ("lib", "cim", "esi"):
                self.slot(d, Z[f"{z}_{chi}"], None, col, fl, 55)
            if f"pool_{chi}" in Z:     # la vaschetta del mana: bordo tondo, MANA POOL a sinistra
                x0_p, y0_p, x1_p, y1_p = self.box(Z[f"pool_{chi}"])
                d.rounded_rectangle((x0_p, y0_p, x1_p, y1_p), radius=(y1_p - y0_p) / 2, fill=(8, 10, 14, 150), outline=col + (90,),
                                    width=max(1, round(self.K(1.2))))
                fp_ = font(max(9, self.K(11)))
                for k_t, r_t in enumerate(("MANA", "POOL")):
                    bb_ = d.textbbox((0, 0), r_t, font=fp_)
                    d.text((x0_p + self.K(15), (y0_p + y1_p) / 2 + (k_t - 1) * self.K(12) + self.K(1) - bb_[1]), r_t, font=fp_, fill=col + (215,))
        return t

    def posti_pool(self, chi, n):
        """Dove stanno i simboli nella vaschetta di chi (in pixel): n centri da sinistra, e il lato del simbolo; oltre quanti ne stanno si accavallano."""
        x0, y0, x1, y1 = self.box(self.L["ZONE"][f"pool_{chi}"])
        lato = round((y1 - y0) * 0.78)
        xa, xb = x0 + self.K(POOL_TESTO - 6) + lato / 2, x1 - self.K(10) - lato / 2
        passo = lato + self.K(4)
        if n > 1 and passo * (n - 1) > xb - xa:
            passo = (xb - xa) / (n - 1)
        return [(xa + k * passo, (y0 + y1) / 2) for k in range(n)], lato

    def posti_pool_gruppi(self, chi, colori):
        """Come posti_pool, per una lista di colori (15 nov 2026, Autore: «se in mana pool accumuliamo piu' di 6 palline contemporaneamente comincia a
        impilare le simili con numero di quantita'»): fino a POOL_MAX_SOLI un posto per simbolo; oltre, un posto per colore, nell'ordine in cui arrivano.
        -> ([(x, y) per simbolo], lato, [indice del posto per simbolo])."""
        colori = list(colori)
        if len(colori) <= POOL_MAX_SOLI:
            posti, lato = self.posti_pool(chi, len(colori))
            return posti, lato, list(range(len(colori)))
        ordine = []
        for c_ in colori:
            if c_ not in ordine:
                ordine.append(c_)
        posti, lato = self.posti_pool(chi, len(ordine))
        idx = [ordine.index(c_) for c_ in colori]
        return [posti[i] for i in idx], lato, idx

    def scudo_carta(self, nome, colore, acceso):
        """Lo scudo araldico con dentro l'arte della carta (15 nov 2026, Autore: «gli emblem falli piu' larghi con il disegno della loro carta dentro e
        niente testo, si illuminano quando si attivano e basta»): bordo nel colore della carta; acceso, l'alone del colore e il bordo bianco. -> immagine
        (con l'alone attorno, il centro dello scudo al centro dell'immagine)."""
        w, h = round(self.K(SCUDO_W)), round(self.K(SCUDO_H))
        chiave = ("scudo", nome, w, colore, acceso)
        if chiave in _FACCE:
            return _FACCE[chiave]
        k = 4
        W, H = w * k, h * k
        pts = [(0, H * 0.10), (W / 2, 0), (W, H * 0.10), (W, H * 0.56), (W / 2, H), (0, H * 0.56)]
        mask = Image.new("L", (W, H), 0)
        ImageDraw.Draw(mask).polygon(pts, fill=255)
        carta = faccia(nome, round(W * 1.28))          # l'arte: il riquadro dell'illustrazione della carta, allargato fino a riempire lo scudo
        cw, ch = carta.size
        arte = carta.crop((round(cw * 0.09), round(ch * 0.11), round(cw * 0.91), round(ch * 0.55)))
        sc_ = max(W / arte.width, H / arte.height)
        arte = arte.resize((max(W, round(arte.width * sc_)), max(H, round(arte.height * sc_))), Image.LANCZOS)
        arte = arte.crop(((arte.width - W) // 2, (arte.height - H) // 2, (arte.width - W) // 2 + W, (arte.height - H) // 2 + H))
        sc = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        sc.paste(arte, (0, 0), mask)
        dd = ImageDraw.Draw(sc)
        bordo = (255, 255, 255, 255) if acceso else colore + (255,)
        dd.line(pts + [pts[0]], fill=bordo, width=max(2, round(W * (0.075 if acceso else 0.06))), joint="curve")
        if not acceso:        # spento appena velato: acceso ha tutta la luce
            vel = Image.new("RGBA", (W, H), (0, 0, 0, 70))
            vel.putalpha(ImageChops.multiply(vel.getchannel("A"), mask))
            sc = Image.alpha_composite(sc, vel)
        sc = sc.resize((w, h), Image.LANCZOS)
        m = round(self.K(10))
        out = Image.new("RGBA", (w + 2 * m, h + 2 * m), (0, 0, 0, 0))
        if acceso:
            alone = Image.new("RGBA", out.size, colore + (0,))
            ma = Image.new("L", out.size, 0)
            ma.paste(mask.resize((w, h), Image.LANCZOS), (m, m))
            alone.putalpha(ma.filter(ImageFilter.GaussianBlur(self.K(5))).point(lambda v: min(255, v * 2)))
            out.alpha_composite(alone)
        else:
            o_, p_ = ombra_sprite(w, h, self.K(4), 120)
            out.alpha_composite(o_, (m - p_, m - p_ + round(self.K(2))))
        out.alpha_composite(sc, (m, m))
        if len(_FACCE) > 4000:
            _FACCE.clear()
        _FACCE[chiave] = out
        return out

    def scudi(self, tela, chiave, voci, accesi=(), scatole=None):
        """Gli scudi degli emblemi di un giocatore, in fila sotto il suo cerchio delle vite (15 nov 2026, Autore: «semplicemente appoggiati in fila»):
        un Paradigm attivo (la carta nell'esilio del suo proprietario) nel colore della carta, un emblema vero col bordo viola; acceso quando la sua
        abilita' e' in pila. voci: [(«paradigm»|«emblem», nome, colori)]; in hover la carta."""
        if not voci:
            return
        x, y = self.L["VITA"][chiave]
        cx, cy = self.X(x), self.Y(y)
        w, h = self.K(SCUDO_W), self.K(SCUDO_H)
        passo = w + self.K(4)
        largo = self.K(110)
        if len(voci) > 1 and passo * (len(voci) - 1) > largo - w:
            passo = (largo - w) / (len(voci) - 1)
        x0 = cx - (passo * (len(voci) - 1)) / 2
        yc = cy + self.K(42) + self.K(8) + h / 2
        for k_, (tipo, nome, colori) in enumerate(voci):
            col = colore_scudo(colori) if tipo == "paradigm" else VIOLA
            im = self.scudo_carta(nome, col, nome in accesi)
            xs = x0 + k_ * passo
            tela.alpha_composite(im, (max(0, round(xs - im.width / 2)), max(0, round(yc - im.height / 2))))
            if scatole is not None:
                scatole.append((xs - w / 2, yc - h / 2, xs + w / 2, yc + h / 2, nome))

    def dietro(self, chi):
        """I riquadri della fila dietro di chi, nelle coordinate del progetto: {«terre»|«mano»|«altri»: (x0, y0, x1, y1)}."""
        x0, y0, x1, y1 = self.L["ZONE"][f"{chi}_dietro"]
        out, L_ = {}, x1 - x0
        for k_, a, b in self.L["DIETRO"]:
            out[k_] = (x0 + L_ * a + (6 if a > 0 else 0), y0, x0 + L_ * b - (6 if b < 1 else 0), y1)
        return out

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
        b = ((x0 - ox) * k, (y0 - oy) * k, (x1 - ox) * k, (y1 - oy) * k)
        w = max(1, round(width * k)) if outline else 0
        # la stessa forma (pillole, cerchi delle vite, cornici) torna a ogni passo: la riduzione si ricorda (15 nov 2026, il debug del replayer: un
        # terzo del disegno di un passo era qui)
        chiave = (forma, L, A, tuple(round(v_, 1) for v_ in b), fill, outline, w, round(radius * k, 1))
        lay = _LISCI.get(chiave)
        if lay is None:
            lay = Image.new("RGBA", (L * k, A * k), (0, 0, 0, 0))
            dd = ImageDraw.Draw(lay)
            if forma == "ell":
                dd.ellipse(b, fill=fill, outline=outline, width=w)
            else:
                dd.rounded_rectangle(b, radius=radius * k, fill=fill, outline=outline, width=w)
            lay = lay.resize((L, A), Image.LANCZOS)
            if len(_LISCI) > 3000:
                _LISCI.clear()
            _LISCI[chiave] = lay
        cx0, cy0 = max(0, -ox), max(0, -oy)          # il pezzo che esce dall'immagine si taglia
        lay = lay.crop((cx0, cy0, min(L, im.width - ox), min(A, im.height - oy)))
        if lay.width > 0 and lay.height > 0:
            im.alpha_composite(lay, (ox + cx0, oy + cy0))

    def pillola(self, d, cx, cy, testo, f, fondo=(12, 12, 16, 235), bordo=(230, 230, 236, 255), colore=(255, 255, 255), pad=6, icona=None):
        """La pillola col testo; icona (PIL RGBA, il simbolo dell'abilita') a sinistra del testo, dentro la pillola."""
        bb = d.textbbox((0, 0), testo, font=f)
        tw, th = bb[2] - bb[0], bb[3] - bb[1]
        p = self.K(pad)
        gi = (icona.width + self.K(3)) if icona is not None else 0
        x0, y0, x1, y1 = cx - (tw + gi) / 2 - p, cy - th / 2 - p * 0.55, cx + (tw + gi) / 2 + p, cy + th / 2 + p * 0.55
        self.liscio(d, "rr", (x0, y0, x1, y1), fill=fondo, outline=bordo, width=max(1.0, self.K(1.2)), radius=(y1 - y0) / 2)
        if icona is not None:
            d._image.alpha_composite(icona, (max(0, round(x0 + p)), max(0, round(cy - icona.height / 2))))
        d.text((cx - (tw + gi) / 2 + gi - bb[0], cy - th / 2 - bb[1]), testo, font=f, fill=colore)
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

    def fila(self, tela, d, lista, b, wmax, colore, nuove, scatole, pos, zkey, seg_prima=None):
        """Una fila di carte nel riquadro b (pixel), alla misura piu' grande che ci sta, centrata. Ogni carta e' un pezzo: ombra, carta, forza e
        costituzione, ×N (le pedine uguali), i segnalini, il filo azzurro e NEW se e' arrivata dal passo prima. Le carte non si rimpiccioliscono sotto
        MIN_FILA della misura piena: se non ci stanno si sovrappongono, come le terre in Arena (14 nov 2026: ogni carta non pedina sta da sola).
        seg_prima: {id: segnalini} del passo prima, per accendere la carta che ne ha appena ricevuti."""
        if not lista:
            return
        x0, y0, x1, y1 = b
        larga, alta = x1 - x0, y1 - y0
        gap = self.K(10)
        w = int(self.K(wmax))
        while w > 18 and round(w * RAPP) > alta:       # la misura piena: quella che ci sta in altezza
            w -= 2
        piena = w
        while w > 18:
            h = round(w * RAPP)
            tot = sum((h if g[1] else w) for g in lista) + gap * (len(lista) - 1)
            if tot <= larga or w <= piena * MIN_FILA:
                break
            w -= 2
        h = round(w * RAPP)
        larghe = [(h if g[1] else w) for g in lista]
        tot = sum(larghe) + gap * (len(lista) - 1)
        passo = 1.0
        if tot > larga and len(lista) > 1:      # si sovrappongono: ognuna avanza di meno, l'ultima intera
            passo = max(0.0, (larga - larghe[-1]) / (tot - larghe[-1]))
            tot = larga
        x = x0 + (larga - tot) / 2
        fpt, fn, fnew = font(max(8, self.K(12)), "Bold"), font(max(15, self.K(18)), "Bold"), font(max(7, self.K(8.5)), "Bold")
        fseg = font(max(10, self.K(13)), "Bold")
        for i_, g in enumerate(lista):
            ww, hh = (h, w) if g[1] else (w, h)
            y = y0 + (alta - h) / 2 + (h - hh)
            im = faccia(g[0], w, g[1], pedina=g[7] if g[2] else None)
            o, p = ombra_sprite(im.width, im.height, self.K(10), 150)
            sg, sid = {}, None
            for id_ in g[6]:
                if (getattr(self, "_segni", {}) or {}).get(id_):
                    sg, sid = self._segni[id_], id_
            # A1 (14 nov 2026, scelto da Autore fra tre disegni): le carte che questa ha esiliato «sotto di se'», sfalsate dietro di lei
            dietro = []
            # le aure e gli equipaggiamenti che porta: dietro di lei, sfalsati in alto, col nome a vista (15 nov 2026)
            porta_ = [n_p for i_p, n_p in (sg.get("porta") or []) if i_p not in (getattr(self, "_porta_nuove", None) or set())][:4]
            for k_, n_p in enumerate(reversed(porta_)):
                im_p = faccia(n_p, w, False)
                livello = len(porta_) - k_
                dietro.append((im_p, self.K(5) * livello, -self.K(22) * livello))
            # la carta esiliata sotto di lei in questo passo non c'e' ancora: ci arriva volando (anima_board) e resta li' (15 nov 2026, «esilia finche'»)
            # anche le carte sotto le aure che porta (Sheltered by Ghosts esilia finche' resta in campo): l'aura sta dietro di lei, le sue carte pure
            segni_d = getattr(self, "_segni", {}) or {}
            fonti_s = [sid] + [i_p for i_p, _n in (sg.get("porta") or [])]
            nuove_s = Counter(n_ for i_f in fonti_s for n_ in ((getattr(self, "_sotto_nuove", None) or {}).get(i_f) or []))
            tutte_s = [n_ for i_f in fonti_s for n_ in ((segni_d.get(i_f) or {}).get("sotto") or [])]
            catena_ = any((segni_d.get(i_f) or {}).get("sotto") and n_f in finche()
                          for i_f, n_f in [(sid, g[0])] + [(i_p, n_p) for i_p, n_p in (sg.get("porta") or [])])
            sotto_ = []
            for n_s in reversed(tutte_s):
                if nuove_s[n_s] > 0:
                    nuove_s[n_s] -= 1
                    continue
                sotto_.append(n_s)
            sotto_ = list(reversed(sotto_))[:3]
            for k_, n_s in enumerate(sotto_):
                im_s = faccia(n_s, w, g[1])
                off = self.K(9) * (len(sotto_) - k_)
                dietro.append((ImageEnhance.Brightness(im_s).enhance(0.72) if im_s.mode == "RGBA" else im_s, off, off))
            sp, (ox, oy) = self.componi([(o, -p, -p + self.K(6))] + dietro + [(im, 0, 0), (Image.new("RGBA", (ww + 8, hh + 8)), -4, -4)])
            ds = ImageDraw.Draw(sp)
            cx, cy = -ox, -oy           # l'angolo della carta dentro il pezzo
            nuova = nuove.get(g[0], 0) > 0
            if nuova:
                nuove[g[0]] -= 1
                self.liscio(ds, "rr", (cx - 3, cy - 3, cx + ww + 3, cy + hh + 3), outline=BLU + (255,), width=max(2.0, self.K(2.5)), radius=self.K(6))
                self.pillola(ds, cx + self.K(22), cy + hh - self.K(14), "NEW", fnew, fondo=(15, 134, 204, 240), bordo=(15, 134, 204, 255))
            seg = g[8] or {}
            prima_seg = {}
            for id_ in g[6]:
                for k_, q_ in ((seg_prima or {}).get(id_) or {}).items():
                    prima_seg[k_] = max(prima_seg.get(k_, 0), q_)
            nuovi = {k_: q_ - prima_seg.get(k_, 0) for k_, q_ in seg.items() if seg_prima is not None and q_ > prima_seg.get(k_, 0)}
            if nuovi and not nuova:     # segnalini appena arrivati: la carta si accende d'oro
                self.liscio(ds, "rr", (cx - 4, cy - 4, cx + ww + 4, cy + hh + 4), outline=GIALLO + (255,), width=max(2.5, self.K(3.5)), radius=self.K(7))
            if sg.get("tmp"):        # B1: la clessidra in alto a sinistra, se ne va a fine turno
                self.clessidra(ds, cx + self.K(14), cy + self.K(14), self.K(13))
            if catena_:
                # la catena (15 nov 2026, il censimento: «esilia finche'»): questa carta tiene in esilio quella sotto di lei finche' resta in campo; in basso
                # al centro, sul bordo verso la carta che sporge
                ic_ = icona_catena(max(12, round(self.K(24))))
                sp.alpha_composite(ic_, (round(cx + ww / 2 - ic_.width / 2), round(cy + hh - ic_.height * 0.75)))
            fkw = font(max(8, self.K(10.5)), "Bold")
            for k_, kw_ in enumerate((sg.get("kw") or [])[:4]):     # C2: le parole chiave date da altre carte, pillole verdi sul bordo sinistro
                self.pillola(ds, cx + self.K(30), cy + hh * 0.66 - k_ * self.K(22), "+" + kw_.title(), fkw, fondo=(30, 138, 79, 240), bordo=(255, 255, 255, 230),
                             icona=icona_abilita(kw_, max(8, round(self.K(12)))))
            for k_, de_ in enumerate((sg.get("des") or [])[:2]):    # D3: la pillola viola col nome (preparata, porta sbloccata, complottata...)
                self.pillola(ds, cx + ww / 2, cy + hh * 0.78 - k_ * self.K(22), de_, fkw, fondo=(122, 79, 208, 245), bordo=(255, 255, 255, 230))
            # la copia (15 nov 2026, il censimento: CopiedObject): la carta mostra cio' che copia, e in fondo la pillola azzurra col nome dell'originale
            if sg.get("copia_di") and sg["copia_di"] != g[0]:
                n_or = sg["copia_di"] if len(sg["copia_di"]) <= 16 else sg["copia_di"][:15] + "."
                self.pillola(ds, cx + ww / 2, cy + hh * 0.60, "COPY · " + n_or.upper(), font(max(7, self.K(8.5)), "Bold"),
                             fondo=(15, 134, 204, 245), bordo=(255, 255, 255, 230), pad=5)
            # lo stato della carta (15 nov 2026): divieti rossi col cerchio barrato, permessi blu con la freccia, l'abilita' esausta grigia, il livello della
            # Classe oro; in testa alla carta, sotto la scelta fatta, al massimo due e «+N»
            st_ = sg.get("st") or []
            fst = font(max(7, self.K(9)), "Bold")
            y_st = cy + max(self.K(18), hh * 0.19) + (self.K(24) if sg.get("ch") else 0)      # sotto la barra del nome, che resta leggibile
            for k_, (tx_st, ge_st) in enumerate(st_[:2]):
                tx_ = tx_st + (f" +{len(st_) - 2}" if k_ == 1 and len(st_) > 2 else "")
                self.pillola(ds, cx + ww / 2, y_st + k_ * self.K(20), tx_, fst, fondo=STATO_COLORI.get(ge_st, STATO_COLORI["off"]),
                             bordo=(255, 255, 255, 230), pad=5, icona=icona_stato(ge_st, max(7, round(self.K(10)))))
            # W2 (14 nov 2026, scelto da Autore fra tre disegni): la parola d'abilita' come anello nell'angolo in alto a destra, pieno quanto il conto
            # sulla soglia (5/7), verde quando e' attiva; sotto, piccolo, il suo nome
            for k_, (n_aw, v_aw, s_aw) in enumerate((sg.get("aw") or [])[:1]):
                attiva = s_aw is None or (v_aw is not None and v_aw >= s_aw)
                frac = 1.0 if s_aw in (None, 0) else max(0.0, min(1.0, (v_aw or 0) / s_aw))
                tx_aw = "ON" if s_aw is None and v_aw is None else (f"{v_aw}/{s_aw}" if s_aw is not None else str(v_aw))
                ra = self.K(15)
                xa, ya = cx + ww - ra - self.K(2), cy + ra + self.K(2)
                self.anello(sp, xa, ya, ra, frac, VERDE_W if attiva else BLU)
                fa = font(max(8, self.K(10 if len(tx_aw) <= 3 else 8.5)), "Bold")
                bb = ds.textbbox((0, 0), tx_aw, font=fa)
                ds.text((xa - (bb[2] - bb[0]) / 2 - bb[0], ya - (bb[3] - bb[1]) / 2 - bb[1]), tx_aw, font=fa, fill=(255, 255, 255))
                self.pillola(ds, xa - self.K(4), ya + ra + self.K(10), n_aw.upper()[:12], font(max(7, self.K(8)), "Bold"),
                             fondo=(12, 14, 18, 235), bordo=(VERDE_W if attiva else BLU) + (230,), pad=4)
            # A2: il testo dell'abilita' data da un'altra carta (non una parola chiave), corto, sulla carta; con piu' abilita' «+N»
            if sg.get("ab"):
                try:
                    import testi_arena as TA
                    testi_ab = [frase_sostituzione(t_) for t_ in (TA.abilita(g_) for g_ in sg["ab"]) if t_]
                except Exception:      # noqa: BLE001 - senza database niente testo
                    testi_ab = []
                if testi_ab:
                    # sopra le pillole verdi delle parole chiave date, se ci sono (la prima foto: il riquadro e le pillole si coprivano)
                    n_kw = len((sg.get("kw") or [])[:4])
                    y_ab = cy + hh * 0.36 if not n_kw else max(cy + self.K(36), cy + hh * 0.66 - n_kw * self.K(22) - self.K(34))
                    self.testo_abilita(ds, cx, y_ab, ww, "+ " + testi_ab[0], len(testi_ab) - 1)
            # C1: la scelta fatta (il tipo, il colore, il nome, la modalita') in un fumetto bianco in testa alla carta
            if sg.get("ch"):
                self.fumetto(ds, cx + ww / 2, cy + self.K(16), str(sg["ch"]), font(max(9, self.K(11)), "Bold"), ww)
            altri_seg = {k_: q_ for k_, q_ in seg.items() if k_ not in (1, 2, 7)}
            if altri_seg:
                self.segnalini(ds, altri_seg, nuovi, cx, cy, ww, hh, fseg, fnew)
            # i segnalini di forza e costituzione e la fedelta' come pallini blu col numero bianco al posto della pillola (14 nov 2026, Autore: «invece di
            # aggiungere segnalini in testa alla carta mettili colorati al posto di forza e costituzione come pallini blu con testo bianco, uno per la forza
            # uno per la costituzione: se un 1/1 guadagna 2 segnalini avra' 2 pallini con scritto 3 e 3»)
            # poi, stesso giorno: «colora semplicemente di blu a o entrambe che hanno ricevuto segnalini + e di rosso se gli hanno ridotto attacco o difesa»:
            # ogni valore contro quello stampato sulla carta (database di Arena), blu se e' piu' alto, rosso se e' piu' basso, normale se e' uguale
            r_p = self.K(13)
            base_ = pt_stampati(g[7]) if g[3] is not None else None
            diversi = base_ is not None and (g[3] != base_[0] or g[4] != base_[1])
            if g[3] is not None and g[4] is not None and diversi:
                for k_, (v_, b_v) in enumerate(((g[4], base_[1]), (g[3], base_[0]))):          # da destra: la costituzione, poi la forza
                    px_, py_ = cx + ww - self.K(16) - k_ * (2 * r_p + self.K(4)), cy + hh - self.K(16)
                    self.pallino(ds, px_, py_, r_p, str(v_), fpt, colore=BLU_PT if v_ > b_v else ROSSO_PT if v_ < b_v else NEUTRO_PT)
            elif g[3] is not None and g[4] is not None:
                self.pillola(ds, cx + ww - self.K(24), cy + hh - self.K(16), f"{g[3]}/{g[4]}", fpt)
            if 7 in seg:
                self.pallino(ds, cx + ww - self.K(16), cy + hh - self.K(16) - (2 * r_p + self.K(4) if g[3] is not None else 0), r_p, str(seg[7]), fpt)
            if g[5] > 1:
                self.pillola(ds, cx + ww - self.K(26), cy + self.K(22), f"×{g[5]}", fn, fondo=colore + (245,), bordo=(255, 255, 255, 230),
                             colore=(10, 12, 16), pad=7)
            r_ = (x, y, x + ww, y + hh)
            avanza = (ww + gap) * passo
            vis = r_ if i_ == len(lista) - 1 or passo >= 1 else (x, y, x + min(ww, avanza), y + hh)      # la parte che si vede, per il passaggio del mouse
            self.posa(tela, sp, ox, oy, x, y, dict(zkey=zkey, nome=g[0], box=r_, vis=vis, tap=g[1], ped=g[2], ids=list(g[6]), nuova=nuova, grp=g[7]))
            scatole.append(vis + (g[0],))
            for id_ in g[6]:
                pos[id_] = r_
            x += avanza

    def anello(self, im, cx, cy, r, frac, colore):
        """W2: il tondo scuro con l'anello di avanzamento (frac da 0 a 1, dall'alto in senso orario), disegnato a 4x e ridotto."""
        k = 4
        L = int(2 * r + 6)
        lay = Image.new("RGBA", (L * k, L * k), (0, 0, 0, 0))
        d = ImageDraw.Draw(lay)
        c0, R = L * k / 2, r * k
        w = max(2, int(r * 0.28)) * k
        d.ellipse((c0 - R, c0 - R, c0 + R, c0 + R), fill=(12, 14, 18, 245), outline=(255, 255, 255, 200), width=max(1, k))
        d.arc((c0 - R + w / 2 + k, c0 - R + w / 2 + k, c0 + R - w / 2 - k, c0 + R - w / 2 - k), 0, 360, fill=(70, 78, 92, 255), width=w)
        if frac > 0:
            d.arc((c0 - R + w / 2 + k, c0 - R + w / 2 + k, c0 + R - w / 2 - k, c0 + R - w / 2 - k), -90, -90 + 360 * frac, fill=colore + (255,), width=w)
        lay = lay.resize((L, L), Image.LANCZOS)
        im.alpha_composite(lay, (max(0, round(cx - L / 2)), max(0, round(cy - L / 2))))

    def testo_abilita(self, d, cx, y, ww, testo, altre):
        """A2: il testo corto dell'abilita' data, in un riquadro scuro col bordo verde, al massimo due righe; «+N more» se ce ne sono altre."""
        f = font(max(8, self.K(9)), "Bold")
        larga = ww - self.K(10)
        parole, righe, r_ = testo.split(), [], ""
        for p_ in parole:
            prova_ = (r_ + " " + p_).strip()
            if d.textlength(prova_, font=f) <= larga:
                r_ = prova_
            else:
                righe.append(r_)
                r_ = p_
            if len(righe) == 2:
                break
        if r_ and len(righe) < 2:
            righe.append(r_)
        if len(righe) == 2 and " ".join(righe) != testo.strip():
            while d.textlength(righe[1] + "…", font=f) > larga and len(righe[1]) > 3:
                righe[1] = righe[1][:-1]
            righe[1] += "…"
        if altre > 0:
            righe.append(f"+{altre} more")
        hr = self.K(12)
        box = (cx + self.K(3), y, cx + ww - self.K(3), y + hr * len(righe) + self.K(8))
        self.liscio(d, "rr", box, fill=(10, 30, 20, 235), outline=(46, 160, 82, 255), width=max(1.2, self.K(1.4)), radius=self.K(5))
        for i_, r_ in enumerate(righe):
            d.text((box[0] + self.K(5), box[1] + self.K(4) + i_ * hr), r_, font=f, fill=(190, 240, 205))

    def fumetto(self, d, cx, cy, testo, f, ww):
        """C1: il fumetto bianco col testo scuro (la scelta fatta) e la punta verso il basso, in testa alla carta."""
        while d.textlength(testo, font=f) > ww - self.K(16) and len(testo) > 3:
            testo = testo[:-2].rstrip() + "…" if not testo.endswith("…") else testo[:-2] + "…"
        bb = d.textbbox((0, 0), testo, font=f)
        tw, th = bb[2] - bb[0], bb[3] - bb[1]
        p = self.K(7)
        box = (cx - tw / 2 - p, cy - th / 2 - p * 0.7, cx + tw / 2 + p, cy + th / 2 + p * 0.7)
        self.liscio(d, "rr", box, fill=(255, 255, 255, 250), outline=(40, 40, 60, 255), width=1, radius=self.K(7))
        d.polygon([(cx - self.K(5), box[3] - 1), (cx + self.K(5), box[3] - 1), (cx, box[3] + self.K(7))], fill=(255, 255, 255, 250))
        d.text((cx - tw / 2 - bb[0], cy - th / 2 - bb[1]), testo, font=f, fill=(38, 33, 92))

    def clessidra(self, d, cx, cy, r):
        """La clessidra (il permanente che se ne va a fine turno): un tondo arancio col bordo bianco e la clessidra scura."""
        self.liscio(d, "ell", (cx - r, cy - r, cx + r, cy + r), fill=(224, 160, 48, 250), outline=(255, 255, 255, 255), width=max(1.2, self.K(1.6)))
        a, h = r * 0.48, r * 0.58
        c_ = (58, 37, 0, 255)
        w_ = max(1, round(self.K(1.8)))
        d.line((cx - a, cy - h, cx + a, cy - h), fill=c_, width=w_)
        d.line((cx - a, cy + h, cx + a, cy + h), fill=c_, width=w_)
        d.line((cx - a * 0.8, cy - h, cx + a * 0.8, cy + h), fill=c_, width=w_)
        d.line((cx + a * 0.8, cy - h, cx - a * 0.8, cy + h), fill=c_, width=w_)

    def pallino(self, d, cx, cy, r, testo, f, colore=None):
        """Un pallino pieno col numero bianco: forza o costituzione (blu piu' alta dello stampato, rossa piu' bassa, scura uguale), la fedelta' (blu)."""
        self.liscio(d, "ell", (cx - r, cy - r, cx + r, cy + r), fill=colore or BLU_PT, outline=(255, 255, 255, 255), width=max(1.2, self.K(1.6)))
        bb = d.textbbox((0, 0), testo, font=f)
        d.text((cx - (bb[2] - bb[0]) / 2 - bb[0], cy - (bb[3] - bb[1]) / 2 - bb[1]), testo, font=f, fill=(255, 255, 255))

    def segnalini(self, ds, seg, nuovi, cx, cy, ww, hh, fseg, fnew):
        """I segnalini sulla carta, ben visibili (14 nov 2026, Autore: «quando a una carta vengono aggiunti segnalini rendiamolo visibilmente piu'
        chiaro»): in alto una pillola per tipo, piena e grande: +1/+1 verde con «+N/+N», -1/-1 rossa con «-N/-N», la fedelta' d'oro col numero, gli altri
        viola col numero e il nome; sotto, in giallo, «+N» quando sono appena arrivati."""
        import nomi_segnalini as NS
        y = cy + self.K(16)
        for k_, q_ in sorted(seg.items(), key=lambda kv: (kv[0] not in (1, 2, 7), kv[0])):
            if k_ == 1:
                t, fondo = f"+{q_}/+{q_}", (40, 170, 90, 245)
            elif k_ == 2:
                t, fondo = f"-{q_}/-{q_}", (200, 60, 60, 245)
            elif k_ == 7:
                t, fondo = f"LOYALTY {q_}", (200, 150, 40, 245)
            else:
                t, fondo = f"{q_} {NS.nome(k_).upper()}", (120, 80, 200, 245)
            bx = self.pillola(ds, cx + ww / 2, y, t, fseg, fondo=fondo, bordo=(255, 255, 255, 255), colore=(255, 255, 255), pad=7)
            if k_ in nuovi:
                self.pillola(ds, bx[2] + self.K(4) + self.K(14), y, f"+{nuovi[k_]}", fnew, fondo=GIALLO + (250,), bordo=(255, 255, 255, 255), colore=(20, 16, 4))
            y += (bx[3] - bx[1]) + self.K(4)

    def riga_mano(self, tela, immagini, nomi, b, scatole, zkey):
        """Una mano in riga nel riquadro b (pixel; il tavolo ingrandito, nel mezzo della fila dietro): le carte alte quanto il riquadro, centrate, che si
        sovrappongono se non ci stanno. -> la larghezza."""
        if not immagini:
            return 0
        x0_, y0, x1_, y1 = b
        h = max(10, int(y1 - y0))
        w = round(h / RAPP)
        if w > x1_ - x0_:
            w = int(x1_ - x0_); h = round(w * RAPP)
        gap = self.K(6)
        larga_max = x1_ - x0_
        passo = min(w + gap, (larga_max - w) / max(1, len(immagini) - 1)) if len(immagini) > 1 else w + gap
        tot = passo * (len(immagini) - 1) + w
        x = (x0_ + x1_) / 2 - tot / 2
        for i_, (im, n) in enumerate(zip(immagini, nomi)):
            im = im.resize((w, h), Image.LANCZOS) if im.size != (w, h) else im
            o, p = ombra_sprite(w, h, self.K(6), 140)
            sp, (ox, oy) = self.componi([(o, -p, -p + self.K(3)), (im, 0, 0)])
            box = (x, y0, x + w, y0 + h)
            vis = box if i_ == len(immagini) - 1 else (x, y0, x + min(w, passo), y0 + h)
            self.posa(tela, sp, ox, oy, x, y0, dict(zkey=zkey, nome=n, box=box, vis=vis, tap=False, ped=False, ids=[], nuova=False))
            if n:
                scatole.append(vis + (n,))
            x += passo
        return tot

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

    def pannello_pila(self, titolo="STACK", piede=""):
        """Il riquadro della pila, vuoto: (immagine, x0, y0). Lo stesso della pila disegnata, perche' l'app lo mostri prima che una carta ci arrivi e dopo
        che l'ultima e' uscita (14 nov 2026, Autore: «la pila ancora appare e scompare, il bambino non capisce»)."""
        x0, y0, x1, y1 = self.box(self.L["STACK"])
        fs = font(max(10, self.K(10)))
        pan = Image.new("RGBA", (round(x1 - x0) + 2, round(y1 - y0) + 2), (0, 0, 0, 0))
        dp = ImageDraw.Draw(pan)
        self.liscio(dp, "rr", (0, 0, x1 - x0, y1 - y0), fill=(14, 12, 24, 228), outline=VIOLA + (230,), width=max(1.5, self.K(2)), radius=self.K(10))
        tw = dp.textlength(titolo, font=fs)
        dp.text(((x1 - x0) / 2 - tw / 2, self.K(8)), titolo, font=fs, fill=VIOLA + (255,))
        if piede:
            tw = dp.textlength(piede, font=fs)
            dp.text(((x1 - x0) / 2 - tw / 2, (y1 - y0) - self.K(18)), piede, font=fs, fill=VIOLA + (230,))
        return pan, x0, y0

    def pila_zona(self, tela, d, chiave, carte, colore, n=None, retro=False, scatole=None, zone=None, cima=None, messa=None):
        x0, y0, x1, y1 = self.box(self.L["ZONE"][chiave])
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
                if cima:        # la carta in cima che si conosce: scoperta sul mazzo; l'occhio aperto se la conosce anche l'altro (15 nov 2026)
                    n_c, pub_c = cima
                    im_c = faccia(n_c, w)
                    self.metti(tela, im_c, cx - w / 2, yc, raggio=8)
                    self.liscio(d, "rr", (cx - w / 2 - 2, yc - 2, cx + w / 2 + 2, yc + h + 2), outline=colore + (255,), width=max(2.0, self.K(2.5)),
                                radius=self.K(6))
                    fk = font(max(8, self.K(9)), "Bold")
                    self.pillola(d, cx, yc + h - self.K(12), "BOTH SEE IT" if pub_c else "ONLY YOU KNOW" if chiave == "lib_mio" else "KNOWN", fk,
                                 fondo=(15, 70, 140, 245) if pub_c else (12, 14, 18, 235), bordo=(255, 255, 255, 230), pad=5,
                                 icona=icona_occhio(max(8, round(self.K(13))), pub_c))
                    if scatole is not None:
                        scatole.append((cx - w / 2, yc, cx + w / 2, yc + h, n_c))
                if messa:       # la carta messa nel grimorio in questo passo: dove e' finita, in testa al mazzo (15 nov 2026)
                    self.pillola(d, cx, yc + self.K(14), {"top": "ON TOP", "bottom": "ON THE BOTTOM"}.get(messa, "INTO THE LIBRARY"),
                                 font(max(8, self.K(9)), "Bold"), fondo=ORO_G + (245,), bordo=(255, 255, 255, 230), colore=(58, 37, 0), pad=5,
                                 icona=icona_triangolo(max(7, round(self.K(9))), messa != "bottom") if messa in ("top", "bottom") else None)
        elif carte:
            if len(carte) > 1:
                dietro = ruotata(faccia(carte[1], w), 4, ("pila", carte[1], w))
                tela.alpha_composite(dietro, (round(cx - dietro.width / 2 + self.K(3)), round(yc + self.K(1))))
            im = faccia(carte[0], w)       # in cima la piu' recente: Arena scrive la pila dalla carta arrivata per ultima
            self.metti(tela, im, cx - w / 2, yc, raggio=8)
            self._carte_pile[chiave] = (cx - w / 2, yc, cx + w / 2, yc + h)       # da qui e verso qui scorrono le carte (anima_board)
            if scatole is not None:
                scatole.append((cx - w / 2, yc, cx + w / 2, yc + h, carte[0]))
        else:
            self._carte_pile[chiave] = (cx - w / 2, yc, cx + w / 2, yc + h)
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

    def giocatore(self, tela, d, chiave, chi, colore, vite, mano, grimorio, sopra, pos, vel=None, emblemi=(), scatole=None):
        """Il cerchio delle vite nell'angolo accanto al suo grimorio; nell'altro angolo il nome, e sotto le carte in mano e nel grimorio (14 nov 2026: le vite
        a destra, in ordine)."""
        x, y = self.L["VITA"][chiave]
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
        xn, yn = self.L["NOMI"][chiave]
        xn, yn = self.X(xn), self.Y(yn)
        fn = font(max(13, self.K(15)))
        tw = d.textlength(chi, font=fn)
        d.text((xn - tw / 2, yn - self.K(24)), chi, font=fn, fill=colore + (255,))
        fv = font(max(12, self.K(13)), "SemiBold")
        for i, (ic, v) in enumerate((("hand", mano), ("library", grimorio))):
            yy = yn + self.K(2) + i * self.K(22)
            self.icona(d, ic, xn - self.K(14), yy + self.K(8))
            d.text((xn - self.K(2), yy), str(v), font=fv, fill=(214, 218, 226))
        if vel:         # V3 (14 nov 2026, scelto da Autore): la velocita' di Aetherdrift (Start your engines!), la pillola arancio sotto i conti
            self.pillola(d, xn, yn + self.K(62), f"SPEED {vel}" + (" · MAX" if vel >= 4 else ""), font(max(9, self.K(10.5)), "Bold"),
                         fondo=(224, 160, 48, 250), bordo=(255, 255, 255, 230), colore=(58, 37, 0))
        # gli emblemi del giocatore (15 nov 2026, il censimento: «gli emblemi non sono sul tavolo»): la pillola viola col nome della carta che l'ha creato,
        # sotto i conti; nella zona Command di Arena, che il tavolo non ha
        for k_, n_e0 in enumerate(list(emblemi)[:3]):
            n_e = n_e0 if len(n_e0) <= 16 else n_e0[:15] + "."
            bx_e = self.pillola(d, xn, yn + self.K(62) + (self.K(24) if vel else 0) + k_ * self.K(22), "EMBLEM · " + n_e.upper(),
                         font(max(8, self.K(9)), "Bold"), fondo=(122, 79, 208, 245), bordo=(255, 255, 255, 230), pad=5)
            if scatole is not None:     # in hover la carta che l'ha creato
                scatole.append(tuple(bx_e) + (n_e0,))

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
        self._etichette, self._grimori, self._carte_pile, self._mani = {}, {}, {}, {}
        tela = self.fondo().copy()
        d = ImageDraw.Draw(tela)
        scatole, zone, pos = [], {}, {}
        # il turno, a destra sulla linea di mezzo fra i due triangoli (14 nov 2026: «spostiamo pt vita e turni ... nell'area a destra»)
        ft = font(max(15, self.K(16)))
        col_t = BLU if mio_turno else ARANCIO
        parti = titolo.split(" · ", 1)
        xt, yt = self.X(self.L["TURNO"][0]), self.Y(self.L["TURNO"][1])
        bx_t = self.pillola(d, xt - (self.K(60) if len(parti) > 1 else 0), yt, parti[0].upper(), ft,
                            fondo=(10, 30, 44, 235) if mio_turno else (40, 28, 12, 235), bordo=col_t + (255,), pad=9)
        if len(parti) > 1:
            fp = font(max(11, self.K(11)), "SemiBold")
            t2 = parti[1].upper()
            larga_t = self.X(self.L["ZX1"]) - self.K(8) - (bx_t[2] + self.K(10))        # accanto alla pillola, dentro l'area di destra
            while d.textlength(t2, font=fp) > larga_t and len(t2) > 4:
                t2 = t2[:-2].rstrip(" .…") + "…"
            bb_ = d.textbbox((0, 0), t2, font=fp)
            d.text((bx_t[2] + self.K(10), yt - (bb_[3] - bb_[1]) / 2 - bb_[1]), t2, font=fp, fill=col_t + (220,))
        conta = lambda lst: {n: sum(1 for c in lst if c[0] == n) for n in {c[0] for c in lst}}
        vite = f.get("vite") or (None, None)
        cim, esi = f.get("cim") or ([], []), f.get("esi") or ([], [])
        # le aure e gli equipaggiamenti attaccati non stanno fra gli altri permanenti: stanno dietro la carta che li porta, sfalsati in alto (come in
        # Arena; 15 nov 2026), e chi li cerca (frecce, voli) li trova sul riquadro di quella carta
        segni_tutti = f.get("segni") or {}
        in_campo = {c[5] for lato in ("mio", "suo") for c in f[lato] if len(c) > 5}
        attaccati = {i_: v_["su"] for i_, v_ in segni_tutti.items() if v_.get("su") in in_campo and i_ in in_campo}
        # quelle attaccate in questo passo: la carta che le porta si disegna senza, l'aura ci arriva volando (anima_board) e resta dietro di lei
        segni_prima = (prima or {}).get("segni") or {}
        self._porta_nuove = {i_ for i_, h_ in attaccati.items() if (segni_prima.get(i_) or {}).get("su") != h_} if prima is not None else set()
        # le carte esiliate sotto una fonte in questo passo (15 nov 2026, «esilia finche'»): la fonte si disegna senza, la carta ci arriva volando
        self._sotto_nuove = {}
        if prima is not None:
            for i_, v_ in segni_tutti.items():
                d_ = Counter(v_.get("sotto") or []) - Counter((segni_prima.get(i_) or {}).get("sotto") or [])
                if d_:
                    self._sotto_nuove[i_] = list(d_.elements())
        for chi, col in (("suo", ARANCIO), ("mio", BLU)):
            in_comb = set()
            if rel and rel.get("tipo") == "comb":
                in_comb = {a_[0] for a_ in rel.get("att") or []} | {b_[0] for b_ in rel.get("blocchi") or []}
            segni_ = f.get("segni") or {}
            gg = gruppi([c for c in f[chi] if not (len(c) > 5 and c[5] in attaccati)], in_comb, segni_)      # chi combatte sta da solo; le pedine uguali anche nei segni stanno insieme
            self._segni = segni_
            seg_prima = {c[5]: (c[7] if len(c) > 7 else None) for c in prima[chi] if len(c) > 5} if prima is not None else None
            nuove = {}
            if prima is not None:
                ora_n, prima_n = conta(f[chi]), conta(prima[chi])
                nuove = {n: q - prima_n.get(n, 0) for n, q in ora_n.items() if q > prima_n.get(n, 0)}
            crea = [g for g in gg if g[3] is not None]
            terre = [g for g in gg if g[3] is None and e_terra(g[0])]
            altri = [g for g in gg if g[3] is None and not e_terra(g[0])]
            Z, WM = self.L["ZONE"], self.L["WMAX"]
            x0, y0, x1, y1 = self.box(Z[f"{chi}_crea"])
            b_ = (x0 + self.K(10), y0 + self.K(18), x1 - self.K(10), y1 - self.K(6))
            if len(crea) > CREA_FILA:       # oltre 6 creature due file, e le carte un po' piu' piccole (14 nov 2026, Autore: «se ci sono piu' di 6 creature
                meta = (len(crea) + 1) // 2      # in campo si crea una seconda fila e tutto si riduce un po'»); la prima fila verso la linea di mezzo
                ym = (b_[1] + b_[3]) / 2
                alta, bassa = (b_[0], b_[1], b_[2], ym - self.K(3)), (b_[0], ym + self.K(3), b_[2], b_[3])
                file_ = ((crea[:meta], bassa), (crea[meta:], alta)) if chi == "suo" else ((crea[:meta], alta), (crea[meta:], bassa))
                for lista_, bb_ in file_:
                    self.fila(tela, d, lista_, bb_, WM["crea"], col, nuove, scatole, pos, chi, seg_prima)
            else:
                self.fila(tela, d, crea, b_, WM["crea"], col, nuove, scatole, pos, chi, seg_prima)
            for k_, (bx0, by0, bx1, by1) in self.dietro(chi).items():
                if k_ in ("terre", "altri"):
                    self.fila(tela, d, terre if k_ == "terre" else altri, self.box((bx0 + 10, by0 + 18, bx1 - 10, by1 - 6)), WM[k_], col, nuove, scatole, pos, chi,
                              seg_prima)
        for i_, host_ in attaccati.items():         # l'aura si trova sul riquadro della carta che la porta
            if host_ in pos:
                pos[i_] = pos[host_]
        cima_ = f.get("cima") or (None, None)
        messa_ = f.get("messa") or {}
        self.pila_zona(tela, d, "lib_suo", [], ARANCIO, n="?", retro=True, cima=cima_[1], scatole=scatole, messa=messa_.get("suo"))
        self.pila_zona(tela, d, "cim_suo", cim[1], ARANCIO, scatole=scatole, zone=zone)
        self.pila_zona(tela, d, "esi_suo", esi[1], ARANCIO, scatole=scatole, zone=zone)
        self.pila_zona(tela, d, "lib_mio", [], BLU, n=grimorio if grimorio is not None else "?", retro=True, cima=cima_[0], scatole=scatole, messa=messa_.get("mio"))
        self.pila_zona(tela, d, "cim_mio", cim[0], BLU, scatole=scatole, zone=zone)
        self.pila_zona(tela, d, "esi_mio", esi[0], BLU, scatole=scatole, zone=zone)
        vel_ = f.get("vel") or (None, None)
        emb_ = f.get("emblemi") or ((), ())
        self.giocatore(tela, d, "vita_suo", "OPPONENT", ARANCIO, vite[1], f.get("n_suo", 0), "?", False, pos, vel_[1], (), scatole)
        self.giocatore(tela, d, "vita_mio", "YOU", BLU, vite[0], len(f.get("mano") or []), grimorio if grimorio is not None else "?", True, pos, vel_[0],
                       (), scatole)
        # gli scudi sotto il cerchio delle vite: i Paradigm attivi (le carte con Paradigm nell'esilio del proprietario) e gli emblemi veri (15 nov 2026)
        par_ = paradigmi()
        for k_t, chi_t in ((0, "mio"), (1, "suo")):
            voci_t, visti_t = [], set()
            for n_t in esi[k_t]:
                n_t = n_t[0] if isinstance(n_t, (tuple, list)) else n_t
                if n_t in par_ and n_t not in visti_t:
                    visti_t.add(n_t)
                    voci_t.append(("paradigm", n_t, par_[n_t]))
            voci_t += [("emblem", n_e, "") for n_e in emb_[k_t]]
            accesi_t = {q[0] for q in (f.get("pila") or [])} | ({rel.get("nome")} if rel and rel.get("tipo") == "spell" else set())
            self.scudi(tela, "vita_" + chi_t, voci_t, accesi_t, scatole)
        # la pila: la magia o l'abilita' di questo momento
        pila_box, pila_rel = None, None
        # la pila intera della foto (14 nov 2026, Autore: «ora le carte si rispondono in maniera corretta impilandosi ma l'area pila sparisce»): la cima
        # e sotto le altre, impilate, ognuna con la sua barra del nome a vista; c'e' anche nei passi senza la magia come relazione (un combattimento con
        # un istantaneo in pila, un pagamento)
        pila_f = list(f.get("pila") or [])
        if rel and rel.get("tipo") == "spell":
            pila_rel = rel
        elif pila_f:
            pila_rel = dict(nome=pila_f[0][0], mio=pila_f[0][1], ab=pila_f[0][2], g=pila_f[0][3])
        sotto = []
        if pila_rel:
            sotto = pila_f[1:] if pila_f and pila_f[0][0] == pila_rel["nome"] else [q for q in pila_f if q[0] != pila_rel["nome"]]
            sotto = sotto[:3]
        self._pila_sotto = {}
        if pila_rel:      # la pila si disegna per ultima (sopra le carte), qui solo dove sta
            x0, y0, x1, y1 = self.box(self.L["STACK"])
            passo_s = self.K(20)
            h = (y1 - y0) - self.K(48) - passo_s * len(sotto)
            w = round(h / RAPP)
            cx = (x0 + x1) / 2
            ys = y0 + self.K(26)
            for j_, q in enumerate(reversed(sotto)):        # la piu' in fondo in alto, la prossima a risolversi subito sopra la cima
                yq = ys + j_ * passo_s
                self._pila_sotto[q[4]] = (cx - w / 2, yq, cx + w / 2, yq + passo_s)
            pila_box = (cx - w / 2, ys + passo_s * len(sotto), cx + w / 2, ys + passo_s * len(sotto) + h)
        # le mani: la tua a ventaglio dal bordo basso, la sua di dorso dal bordo alto; col tavolo ingrandito (In hand spento) in riga, piccole
        cxm = self.X(self.L["MANO"][0])
        fl = font(max(11, self.K(10.5)))
        mano = f.get("mano") or []
        n_suo = f.get("n_suo") or 0
        # le carte giocabili dall'esilio (14 nov 2026, Autore: «carte esiliate che in realta' il giocatore puo' giocare non si vedono ne' per immagine ne'
        # come condizione giocabile, dovrebbero stare a parte nella sua mano e distinguersi se rivelate o meno»): a parte, accanto alla mano, col bordo viola;
        # le sue a faccia in giu' (non rivelate) di dorso
        esi_ = f.get("esi") or ([], [])
        if "segni" in f:        # il replay azione per azione: quelle che Arena dice giocabili, dall'esilio e dal cimitero, di chi puo' giocarle (14 nov 2026)
            gioca_ = [v_["gioca"] for v_ in (f.get("segni") or {}).values() if v_.get("gioca")]
            esi_mie = [n for n, mio_, _z in gioca_ if mio_]
            esi_sue = [n for n, mio_, _z in gioca_ if not mio_]
        else:                   # i Moments (le foto di mana_aperto non hanno i permessi): dal testo, grado C
            esi_mie = [n for n in esi_[0] if giocabile_esilio(n)]
            esi_sue = [n for n in esi_[1] if giocabile_esilio(n)]
        self._esilio_mano = dict(mio=list(esi_mie), suo=list(esi_sue))
        if self.mano:
            wm = int(self.K(158))
            # la carta che hai mostrato all'avversario (15 nov 2026, il censimento: InstanceRevealedToOpponent): l'occhio e SHOWN in fondo alla carta
            mostrate_ = list(f.get("mostrate") or [])
            gioc_ = [g_[0] for g_ in f.get("gioc") or [] if g_[3] == "mano"]      # le carte che potevi giocare (16 nov 2026)
            mie = []
            for n in mano:
                k_g = n in gioc_
                if k_g:
                    gioc_.remove(n)
                if n in mostrate_:
                    mostrate_.remove(n)
                    im_ = mostrata(faccia(n, wm))
                    mie.append(((n, wm, "shown") + (("play",) if k_g else ()), giocabile(im_) if k_g else im_))
                else:
                    mie.append(((n, wm) + (("play",) if k_g else ()), giocabile(faccia(n, wm)) if k_g else faccia(n, wm)))
            self.ventaglio(tela, mie, cxm, self.H + wm * RAPP / 2 - self.K(130), wm, 6, 0.30, False, scatole, self.K(760), "mano")
            wr = int(self.K(92))
            self.ventaglio(tela, [(("dorso", wr), dorso(wr))] * n_suo, cxm, -wr * RAPP / 2 + self.K(100), wr, 6, 0.42, True, [], self.K(560), "mano_suo")
            larga_mano = min(len(mano) * wm * 0.7, self.K(760))
            larga_suo = min(n_suo * wr * 0.58, self.K(560))
            y_mia, y_sua = self.H - self.K(50), self.K(50)
            we = int(self.K(104))       # piu' grandi (15 nov 2026, Autore: «le famose carte esiliate dorate in mano non le vedo mai»; erano 84)
            he = round(we * RAPP)
            if esi_mie:         # a destra del tuo ventaglio
                x0e = cxm + max(larga_mano, wm) / 2 + self.K(30)
                x1e = min(x0e + len(esi_mie) * (we + self.K(8)), self.X(self.L["ZONE"]["cim_mio"][0]) - self.K(16))
                self.riga_mano(tela, [dall_esilio(faccia(n, we)) for n in esi_mie], esi_mie, (x0e, self.H - he - self.K(16), x1e, self.H - self.K(16)),
                               scatole, "esi_mano_mio")
                self.pillola(d, (x0e + x1e) / 2, self.H - he - self.K(30), f"PLAYABLE · {len(esi_mie)}", fl, fondo=(44, 32, 6, 230), bordo=ORO_G + (220,),
                             colore=ORO_G)
            if esi_sue:         # a sinistra del suo
                x1e = cxm - max(larga_suo, wr) / 2 - self.K(30)
                x0e = max(x1e - len(esi_sue) * (we + self.K(8)), self.X(self.L["XB0"]) + self.K(8))
                imgs_ = [dall_esilio(dorso(we) if n == FACCIA_GIU else faccia(n, we)) for n in esi_sue]
                self.riga_mano(tela, imgs_, [None if n == FACCIA_GIU else n for n in esi_sue], (x0e, self.K(16), x1e, self.K(16) + he), scatole, "esi_mano_suo")
                self.pillola(d, (x0e + x1e) / 2, self.K(16) + he + self.K(14), f"PLAYABLE · {len(esi_sue)}", fl, fondo=(44, 32, 6, 230),
                             bordo=ORO_G + (220,), colore=ORO_G)
        else:
            w9 = int(self.K(90))
            mostrate_, mie9 = list(f.get("mostrate") or []), []
            gioc9 = [g_[0] for g_ in f.get("gioc") or [] if g_[3] == "mano"]
            for n in mano:
                k_g = n in gioc9
                if k_g:
                    gioc9.remove(n)
                if n in mostrate_:
                    mostrate_.remove(n)
                    im_ = mostrata(faccia(n, w9))
                else:
                    im_ = faccia(n, w9)
                mie9.append(giocabile(im_) if k_g else im_)
            for chi, carte_, nomi_, col_ in (("mio", mie9 + [dall_esilio(faccia(n, w9)) for n in esi_mie], mano + esi_mie, BLU),
                                             ("suo", [dorso(w9)] * n_suo + [dall_esilio(dorso(w9) if n == FACCIA_GIU else faccia(n, w9)) for n in esi_sue],
                                              [None] * n_suo + [None if n == FACCIA_GIU else n for n in esi_sue], ARANCIO)):
                bx0, by0, bx1, by1 = self.box(self.dietro(chi)["mano"])
                self._mani[chi] = (bx0, by0, bx1, by1)
                self.riga_mano(tela, carte_, nomi_, (bx0 + self.K(10), by0 + self.K(18), bx1 - self.K(10), by1 - self.K(6)), scatole if chi == "mio" else [],
                               "mano" if chi == "mio" else "mano_suo")
                q_ = len(mano) if chi == "mio" else n_suo
                self.pillola(d, bx1 - self.K(26), by0 + self.K(10), str(q_), fl, fondo=(10, 22, 32, 230) if chi == "mio" else (24, 18, 10, 230),
                             bordo=col_ + (200,), colore=col_)
        if self.mano:
            self.pillola(d, cxm - larga_mano / 2 - self.K(110), y_mia, f"YOUR HAND · {len(mano)}", fl, fondo=(10, 22, 32, 220), bordo=BLU + (180,), colore=BLU)
            self.pillola(d, cxm + larga_suo / 2 + self.K(110), y_sua, f"OPPONENT'S HAND · {n_suo}", fl, fondo=(24, 18, 10, 220), bordo=ARANCIO + (160,),
                         colore=ARANCIO)
        if pila_rel:        # la pila al centro del tavolo, sopra le carte: il riquadro scuro col filo viola, STACK, la carta, di chi e'
            x0, y0, x1, y1 = self.box(self.L["STACK"])
            fs = font(max(10, self.K(10)))
            pan = Image.new("RGBA", (round(x1 - x0) + 2, round(y1 - y0) + 2), (0, 0, 0, 0))
            dp = ImageDraw.Draw(pan)
            self.liscio(dp, "rr", (0, 0, x1 - x0, y1 - y0), fill=(14, 12, 24, 228), outline=VIOLA + (230,), width=max(1.5, self.K(2)), radius=self.K(10))
            tw = dp.textlength("STACK", font=fs)
            tit_s = "STACK" if not sotto else f"STACK · {len(sotto) + 1}"
            tw = dp.textlength(tit_s, font=fs)
            dp.text(((x1 - x0) / 2 - tw / 2, self.K(8)), tit_s, font=fs, fill=VIOLA + (255,))
            # chi prende di mira una carta gia' in pila (una contromagia; 14 nov 2026, Autore: «se una carta interagisce su un'altra carta gia' in pila,
            # crea il metodo visivo per capire che quell'azione si risolve nella pila»)
            in_pila_bers = {i_ for i_, v_ in ((rel or {}).get("fuori") or {}).items() if v_[0] == "pila"}
            et = ("YOURS" if pila_rel.get("mio") else "OPPONENT'S") + (" · ABILITY" if pila_rel.get("ab") else "")
            if in_pila_bers & set(self._pila_sotto):
                et = "RESOLVES ON THE STACK"
            tw = dp.textlength(et, font=fs)
            dp.text(((x1 - x0) / 2 - tw / 2, (y1 - y0) - self.K(18)), et, font=fs, fill=VIOLA + (230,))
            im = faccia(pila_rel["nome"], round(pila_box[2] - pila_box[0]), pedina=pila_rel.get("g"))      # una pedina in pila (un potere di Jace): la sua immagine
            # come e' stata lanciata (15 nov 2026): KICKED, X = 3, ALT. COST, EXTRA COST, pillole oro in fondo alla carta in cima
            id_cima = pila_f[0][4] if pila_f and pila_f[0][0] == pila_rel["nome"] and len(pila_f[0]) > 4 else None
            op_ = list((f.get("opzioni") or {}).get(id_cima) or [])
            op_ += [t_s for t_s, _g in (((f.get("segni") or {}).get(id_cima) or {}).get("st") or [])]       # lo stato della magia (UNCOUNTERABLE)
            if op_:
                im = im.copy()
                di = ImageDraw.Draw(im)
                for k_, t_op in enumerate(op_[:2]):
                    self.pillola(di, im.width / 2, im.height * 0.56 - k_ * self.K(24), t_op, font(max(9, self.K(11)), "Bold"), fondo=ORO_G + (250,),
                                 bordo=(255, 255, 255, 235), colore=(58, 37, 0), pad=6)
            o, p_ = ombra_sprite(im.width, im.height, self.K(12), 190)
            strati = [(o, pila_box[0] - x0 - p_, pila_box[1] - y0 - p_ + self.K(6)), (pan, 0, 0)]
            fsb = font(max(8, self.K(8)), "Bold")
            for q in reversed(sotto):           # le carte sotto: un po' scure, la barra del nome a vista; il bersaglio in viola con TARGET
                bq = self._pila_sotto[q[4]]
                iq = faccia(q[0], round(pila_box[2] - pila_box[0]), pedina=q[3]).copy()
                scuro = Image.new("RGBA", iq.size, (6, 6, 12, 90 if q[4] not in in_pila_bers else 0))
                iq.alpha_composite(scuro)
                if q[4] in in_pila_bers:
                    dq = ImageDraw.Draw(iq)
                    dq.rounded_rectangle((1, 1, iq.width - 2, iq.height - 2), radius=max(4, iq.width // 12), outline=VIOLA + (255,), width=max(2, iq.width // 40))
                    tw_ = dq.textlength("TARGET", font=fsb)
                    hb = round(passo_s) - 4
                    dq.rounded_rectangle((iq.width - tw_ - 14, 3, iq.width - 4, 3 + hb), radius=hb // 2, fill=(60, 30, 100, 240), outline=VIOLA + (255,))
                    dq.text((iq.width - tw_ - 9, 3 + (hb - self.K(8)) / 2 - 1), "TARGET", font=fsb, fill=(240, 230, 255))
                strati.append((iq, bq[0] - x0, bq[1] - y0))
            strati.append((im, pila_box[0] - x0, pila_box[1] - y0))
            sp, (ox, oy) = self.componi(strati)
            self.posa(tela, sp, ox, oy, x0, y0, dict(zkey="pila", nome=pila_rel["nome"], box=pila_box, tap=False, ped=False, ids=[], nuova=False))
            scatole.append(tuple(pila_box) + (pila_rel["nome"],))
        if pezzi:       # l'app mette i pezzi come oggetti della tela; frecce e danni li disegna lei
            pz, self._pezzi = self._pezzi, None
            fuori = [s_ for s_ in scatole if not any(s_[:4] in (tuple(q["box"]), tuple(q.get("vis") or q["box"])) for q in pz)]
            return tela.convert("RGB"), pz, dict(vite={k: pos[k] for k in ("vita_mio", "vita_suo")}, pile=zone, pila=pila_box, scatole=fuori,
                                                 pila_sotto=dict(self._pila_sotto),
                                                 etichette=self._etichette, grimori=self._grimori, carte_pile=self._carte_pile, attaccati=attaccati,
                                                 attaccati_nuovi={i_: attaccati[i_] for i_ in self._porta_nuove},
                                                 sotto_nuovi=dict(self._sotto_nuove),
                                                 mani=self._mani)
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


def _pixel(im):
    """I pixel RGB di un'immagine come terne (getdata sparisce in Pillow 14)."""
    b = im.convert("RGB").tobytes()
    return zip(b[0::3], b[1::3], b[2::3])


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
    # 14 nov 2026: le carte non pedina doppie una per una; le pedine uguali ancora insieme col ×N
    gg = gruppi([("Bear", False, False, 2, 2, 1), ("Bear", False, False, 2, 2, 2)] + [("Cat", False, True, 1, 1, i_, 9001) for i_ in (3, 4, 5, 6)]
                + [("Treasure", False, True, None, None, i_, 9002) for i_ in (7, 8)])
    casi.append(("due carte uguali stanno separate; le pedine creatura uguali insieme da 4 in su, le altre pedine sempre",
                 [(g[0], g[5]) for g in gg] == [("Bear", 1), ("Bear", 1), ("Cat", 4), ("Treasure", 2)]))
    gg = gruppi([("Cat", False, True, 1, 1, i_, 9001) for i_ in (3, 4, 5)])
    casi.append(("tre pedine creatura uguali stanno insieme col ×3 (15 nov 2026: la regola di Autore, anche sotto le 4)", [g[5] for g in gg] == [3]))
    gg = gruppi([("Cat", False, True, 1, 1, 3, 9001), ("Cat", False, True, 2, 2, 4, 9001), ("Cat", False, True, 1, 1, 5, 9001)])
    casi.append(("negativa: la pedina con forza e costituzione diverse sta a parte", [(g[3], g[5]) for g in gg] == [(1, 2), (2, 1)]))
    seg_ = {3: dict(tmp=True), 4: dict(tmp=True), 5: dict(kw=["Flying"])}
    gg = gruppi([("Cat", False, True, 1, 1, i_, 9001) for i_ in (3, 4, 5)], segni=seg_)
    casi.append(("le pedine con gli stessi segni insieme, con un segno diverso a parte; una carta non pedina col segno da sola",
                 [g[5] for g in gg] == [2, 1] and [g[5] for g in gruppi([("Plains", False, False, None, None, i_) for i_ in (1, 2)], segni={1: dict(tmp=True)})] == [1, 1]))
    gg = gruppi([("Plains", False, False, None, None, 1), ("Plains", False, False, None, None, 2), ("Plains", True, False, None, None, 3)])
    casi.append(("le terre uguali stanno insieme col ×N (la tappata a parte)", [(g[0], g[1], g[5]) for g in gg] == [("Plains", False, 2), ("Plains", True, 1)]))
    gg = gruppi([("Cat", False, True, 1, 1, 3, 9001, {1: 1}), ("Cat", False, True, 1, 1, 4, 9001, None)])
    casi.append(("negativa: due pedine con segnalini diversi non stanno insieme", len(gg) == 2))
    # le carte giocabili dall'esilio accanto alla mano (14 nov 2026): la sua a faccia in giu' di dorso, a parte; negativa: una carta qualsiasi in esilio no
    for mano_on in (True, False):
        te = Tappeto(1500, 900, mano_on)
        fe = dict(vuota, mano=["Shock"], n_suo=2, esi=(["Lightning Bolt"], [FACCIA_GIU]))
        _im, _sc, _z = te.disegna(fe)
        casi.append((f"esilio giocabile ({'In hand' if mano_on else 'riga'}): la sua carta a faccia in giu' accanto alla sua mano, la tua carta qualsiasi no",
                     te._esilio_mano == dict(mio=[], suo=[FACCIA_GIU])))
    casi.append(("negativa: una carta qualsiasi non e' giocabile dall'esilio, una a faccia in giu' si'", not giocabile_esilio("Lightning Bolt") and giocabile_esilio(FACCIA_GIU)))
    te = Tappeto(1500, 900, True)
    fe = dict(vuota, mano=["Shock"], n_suo=2, esi=(["Lightning Bolt", "Mountain"], []), cim=(["Abrade"], []),
              segni={7: dict(gioca=("Mountain", True, "esi")), 8: dict(gioca=("Abrade", True, "cim")), 9: dict(gioca=(FACCIA_GIU, False, "esi"))})
    te.disegna(fe)
    casi.append(("le giocabili dal permesso di Arena (dall'esilio e dal cimitero, di chi puo' giocarle); negativa: Lightning Bolt in esilio senza permesso no",
                 te._esilio_mano == dict(mio=["Mountain", "Abrade"], suo=[FACCIA_GIU])))
    # la pila intera (14 nov 2026): due magie, la cima e quella sotto con la barra a vista; la contromagia la prende di mira e si risolve nella pila;
    # negativa: senza pila nella foto e senza magia come relazione niente pila
    tp_ = Tappeto(1500, 900, True)
    fp_ = dict(vuota, pila=[("Negate", False, False, 1, 61), ("Shock", True, False, 2, 60)])
    _im, _pz, inf_ = tp_.disegna(fp_, None, dict(tipo="spell", nome="Negate", mio=False, ab=False, g=1, bers=[60], fuori={60: ("pila", "mio", "Shock")}),
                                 pezzi=True)
    _im, _pz, inf0_ = tp_.disegna(fp_, pezzi=True)
    _im, _pz, inf1_ = tp_.disegna(vuota, pezzi=True)
    casi.append(("la pila intera: la cima e sotto la magia presa di mira (anche senza la relazione); negativa: senza pila niente",
                 inf_["pila"] and 60 in inf_["pila_sotto"] and inf_["pila_sotto"][60][3] <= inf_["pila"][1] + 1 and inf0_["pila"] and inf1_["pila"] is None))
    tre = [("Cat", True, True, 1, 1, i_, 9001) for i_ in (3, 4, 5, 6, 7)]
    gg, gn = gruppi(tre, {3, 4}), gruppi(tre)
    casi.append(("le pedine uguali che combattono stanno ognuna da sola, le altre insieme; negativa: senza combattimento tutte col ×5",
                 [(g[5], g[6]) for g in gg] == [(1, [3]), (1, [4]), (3, [5, 6, 7])] and [(g[5], g[6]) for g in gn] == [(5, [3, 4, 5, 6, 7])]))
    # i segnalini disegnati: la carta col +1/+1 ha piu' verde della stessa carta senza
    _PT[777001] = (2, 2)        # una 2/2 stampata
    f3 = dict(vuota, mio=[("Bear", False, False, 3, 3, 1, 777001, {1: 1})])
    f4 = dict(vuota, mio=[("Bear", False, False, 2, 2, 1, 777001, None)])
    im3, sc3, _z = t.disegna(f3)
    im4, _sc4, _z = t.disegna(f4)
    b3 = tuple(round(v) for v in sc3[0][:4])
    blu = lambda im: sum(1 for r_, g_, b_ in _pixel(im.crop(b3)) if b_ > 190 and r_ < 70 and 90 < g_ < 150)
    rossi = lambda im: sum(1 for r_, g_, b_ in _pixel(im.crop(b3)) if r_ > 180 and g_ < 80 and b_ < 80)
    im6 = t.disegna(dict(vuota, mio=[("Bear", False, False, 1, 1, 1, 777001, {2: 1})]))[0]
    casi.append(("forza e costituzione sopra lo stampato in blu, sotto in rosso; negativa: uguali allo stampato niente pallini colorati",
                 blu(im3) > blu(im4) + 30 and rossi(im6) > rossi(im4) + 30 and blu(im6) <= blu(im4) + 5))
    im5, _s5, _z = t.disegna(f3, prima=f4)
    oro = lambda im: sum(1 for r_, g_, b_ in _pixel(im.crop((b3[0] - 6, b3[1] - 6, b3[2] + 6, b3[3] + 6))) if r_ > 220 and g_ > 180 and b_ < 100)
    casi.append(("un segnalino appena arrivato accende la carta d'oro; negativa: gia' c'era, niente oro", oro(im5) > oro(t.disegna(f3, prima=f3)[0]) + 40))
    # grimorio, cimitero ed esilio a triangolo: cimitero ed esilio affiancati, il grimorio dalla parte del bordo, a meta' fra i due
    _im, _sc, zz = t.disegna(dict(vuota, cim=(["Bear"], ["Cat"]), esi=(["Bear"], ["Cat"])))
    cm, em, cs = zz["cim_mio"][0], zz["esi_mio"][0], zz["cim_suo"][0]
    lm = t.box(ZONE["lib_mio"])
    casi.append(("a triangolo: cimitero ed esilio sulla stessa riga, il tuo grimorio sotto e in mezzo, quello dell'avversario sopra",
                 abs(cm[1] - em[1]) < 1 and cm[2] <= em[0] and lm[1] > cm[3] - 1 and cm[0] < (lm[0] + lm[2]) / 2 < em[2] and t.box(ZONE["lib_suo"])[3] < cs[1] + 1))
    casi.append(("piu' grandi: la carta del cimitero larga almeno 100 pixel del progetto", (cm[2] - cm[0]) >= t.K(100)))
    # tante carte uguali: non scendono sotto il MIN_FILA della misura piena, si sovrappongono
    f6 = dict(vuota, mio=[(f"Relic {i}", False, False, None, None, i) for i in range(14)])
    _im, sc6, _z = t.disegna(f6)
    larghe = [s_[2] - s_[0] for s_ in sc6]
    xb0, _y0, xb1, _y1 = t.box(ZONE["mio_dietro"])
    una = t.disegna(dict(vuota, mio=[("Relic 0", False, False, None, None, 1)]))[1][0]
    casi.append(("14 permanenti diversi: restano grandi (l'ultimo almeno l'80% di uno solo) e si sovrappongono dentro la loro zona",
                 len(sc6) == 14 and larghe[-1] >= 0.8 * (una[2] - una[0]) - 2
                 and max(larghe[:-1]) < larghe[-1] and sc6[0][0] >= xb0 + (xb1 - xb0) * SPLIT - 1 and sc6[-1][2] <= xb1 + 1))
    # 14 nov 2026: le vite a destra del campo; col tavolo ingrandito (In hand spento) le creature piu' grandi e la mano in riga piccola
    fz = dict(vuota, mio=[("Bear", False, False, 2, 2, 1)], mano=["Bear", "Bear"])
    _im, scm, _z = t.disegna(fz)
    tz = Tappeto(1560, 940, mano=False)
    _im, scz, _z = tz.disegna(fz)
    _b, pz_, info_ = t.disegna(fz, pezzi=True)
    larga = lambda sc_: max(s_[2] - s_[0] for s_ in sc_ if s_[4] == "Bear" and s_[1] < t.Y(MEZZO + 300))
    mani_m = [s_ for s_ in scm if s_[1] > t.Y(MEZZO + 300)]
    mani_z = [s_ for s_ in scz if s_[1] > tz.Y(MEZZO + 300)]
    casi.append(("le vite a destra del campo (fino al 14 nov 2026 stavano a sinistra)", info_["vite"]["vita_mio"][0] > t.X(LC)))
    casi.append(("tavolo ingrandito: la creatura piu' grande che con la mano a ventaglio", larga(scz) > larga(scm) * 1.15))
    mb = tz.box(tz.dietro("mio")["mano"])
    casi.append(("tavolo ingrandito: la mano in mezzo alla fila dietro, piu' piccola del ventaglio; negativa: col ventaglio la mano sta fuori dal campo",
                 len(mani_z) == 2 and all(mb[0] - 1 <= s_[0] and s_[2] <= mb[2] + 1 and mb[1] <= s_[1] for s_ in mani_z)
                 and max(s_[2] - s_[0] for s_ in mani_z) < 0.8 * max(s_[2] - s_[0] for s_ in mani_m)
                 and min(s_[1] for s_ in mani_m) > t.Y(ZONE["mio_dietro"][3]) - t.K(60)))
    # oltre 6 creature due file (14 nov 2026: «se ci sono piu' di 6 creature in campo si crea una seconda fila e tutto si riduce un po'»)
    righe_y = lambda n: {round(s_[1]) for s_ in t.disegna(dict(vuota, mio=[(f"Bear {i}", False, False, 2, 2, i) for i in range(n)]))[1]}
    casi.append(("7 creature: due file; negativa: 6 creature una fila", len(righe_y(7)) == 2 and len(righe_y(6)) == 1))
    # la vaschetta del mana oltre 6 simboli (15 nov 2026): i colori uguali nello stesso posto; negativa: fino a 6 un posto per simbolo
    p8, _l8, i8 = t.posti_pool_gruppi("mio", list("RRRRRRGG"))
    p6, _l6, i6 = t.posti_pool_gruppi("mio", list("RRRRRR"))
    casi.append(("pool: 8 simboli R R R R R R G G in due posti; negativa: 6 R in sei posti",
                 sorted(set(i8)) == [0, 1] and len({p_ for p_ in p8}) == 2 and i6 == list(range(6)) and len(set(p6)) == 6))
    # la targa EMBLEMS: lo scudo del Paradigm attivo nell'esilio del proprietario; negativa: un'altra carta in esilio non lo fa
    par_ = paradigmi()
    casi.append(("i cinque Paradigm di SOS letti dallo Standard", {"Restoration Seminar", "Germination Practicum"} <= set(par_) and len(par_) >= 5))
    _im, sc_p, _z = t.disegna(dict(vuota, esi=(["Restoration Seminar"], [])))
    _im, sc_n, _z = t.disegna(dict(vuota, esi=(["Shock"], [])))
    vx, vy = t.X(t.L["VITA"]["vita_mio"][0]), t.Y(t.L["VITA"]["vita_mio"][1])
    sotto = lambda sc, n: [s_ for s_ in sc if s_[4] == n and s_[1] > vy + t.K(42) and abs((s_[0] + s_[2]) / 2 - vx) < t.K(60)]
    casi.append(("Restoration Seminar in esilio: lo scudo sotto il tuo cerchio delle vite; negativa: Shock in esilio no",
                 bool(sotto(sc_p, "Restoration Seminar")) and not sotto(sc_n, "Shock")))
    vis_ = lambda im: im.getchannel("A").point(lambda v: 255 if v > 40 else 0).histogram()[255]
    spento, acceso = t.scudo_carta("Restoration Seminar", COLORI_SCUDO["W"], False), t.scudo_carta("Restoration Seminar", COLORI_SCUDO["W"], True)
    casi.append(("lo scudo acceso ha l'alone (piu' pixel visibili) dello spento",
                 vis_(acceso) > vis_(spento)))
    # «esilia finche'» (15 nov 2026, il censimento): le fonti lette dal testo, la carta nuova sotto la fonte non c'e' finche' non arriva, la catena viola
    fi_ = finche()
    casi.append(("esilia finche': Seam Rip, Deep-Cavern Bat, Banishing Light fra le fonti; negativa: Shock no",
                 {"Seam Rip", "Deep-Cavern Bat", "Banishing Light"} <= fi_ and "Shock" not in fi_))
    f_s = dict(vuota, suo=[("Seam Rip", False, False, None, None, 900)], esi=([], ["Bear"]), segni={900: dict(sotto=["Bear"])})
    f_0 = dict(vuota, suo=[("Seam Rip", False, False, None, None, 900)])
    casi.append(("la carta esiliata sotto la fonte in questo passo e' «nuova» (ci arriva volando); negativa: gia' sotto nel passo prima, no",
                 t.disegna(f_s, prima=f_0, pezzi=True)[2].get("sotto_nuovi") == {900: ["Bear"]}
                 and not t.disegna(f_s, prima=f_s, pezzi=True)[2].get("sotto_nuovi")))
    global _FINCHE
    con_ = t.disegna(f_s)[0]
    vero_, _FINCHE = _FINCHE, set()          # la stessa carta, letta come non «finche'»: niente catena
    senza_ = t.disegna(f_s)[0]
    _FINCHE = vero_
    diff_ = ImageChops.difference(con_.convert("RGB"), senza_.convert("RGB")).convert("L").point(lambda v: 255 if v > 30 else 0).histogram()[255]
    casi.append(("la fonte che tiene una carta «finche'» porta la catena; negativa: la stessa carta non letta come «finche'», niente", diff_ > 60))
    casi.append(("la catena: un'immagine tonda della misura chiesta", icona_catena(24).size == (24, 24)))
    for n, v in casi:
        print(("OK   " if v else "ROSSO") + " " + n)
    print(f"{sum(v for _n, v in casi)}/{len(casi)}")
    return all(v for _n, v in casi)


if __name__ == "__main__":
    if "--prova" in sys.argv:
        sys.exit(0 if prova() else 1)
