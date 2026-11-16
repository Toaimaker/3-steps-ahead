"""Il marchio di 3 Steps Ahead: le tre carte del logo, il nome dell'app e sotto l'indirizzo del sito.

Autore, 16 nov 2026: «aggiungiamo i loghi di 3 step ahead: in basso a destra delle schede mazzo anche editor / in basso a destra della board e board
editor, posizione fissa anche se la board trasla o zooma e sempre dietro le carte se ci vanno sopra, si deve vedere il logo e ben visibile il nome
dell'app». Lo usano la finestra del mazzo (scheda_mazzo), il builder (costruttore_mazzi) e il Board (tavolo_carte); il tappeto del replayer ha il suo, stampato
sul feltro (disegno_tappeto), con le stesse tre carte di logo_carte.

Disegnato a 4x e ridotto (antialias), trasparente fuori dal disegno: le carte del logo si riempiono col colore del fondo su cui sta, cosi' quella davanti copre
il filo di quella dietro.

    py -I -X utf8 Companion/App/Comune/marchio.py --prova
"""
import os, sys

_casa = os.path.dirname(os.path.abspath(__file__))
while not os.path.isfile(os.path.join(_casa, "percorsi.py")):
    _casa = os.path.dirname(_casa)
if _casa not in sys.path:
    sys.path.insert(0, _casa)
import percorsi  # noqa: E402,F401

from PIL import Image, ImageDraw, ImageFont  # noqa: E402

NOME, SITO = "3 STEPS AHEAD", "toaimaker.github.io/3-steps-ahead"
BLU = (36, 186, 255)
COL_NOME, COL_SITO = (236, 242, 250), (140, 178, 210)
SUP = 4
_FONT, _PIL, _FOTO = {}, {}, {}


def _font_file():
    """Bahnschrift (Windows 10 e 11, il carattere dei numeri dell'app); dove non c'e' (Mac) il Poppins dell'app."""
    for f in (os.path.join(os.environ.get("WINDIR", "C:" + os.sep + "Windows"), "Fonts", "bahnschrift.ttf"),
              os.path.join(_casa, "Grafica", "Poppins-SemiBold.ttf"), os.path.join(_casa, "Grafica", "Poppins-Medium.ttf")):
        if os.path.isfile(f):
            return f
    return "DejaVuSans.ttf"


def font(px, peso="Bold SemiCondensed"):
    k = (round(px), peso)
    if k not in _FONT:
        f = ImageFont.truetype(_font_file(), max(6, k[0]))
        try:
            f.set_variation_by_name(peso)
        except Exception:      # noqa: BLE001 - un font senza varianti
            pass
        _FONT[k] = f
    return _FONT[k]


def logo_carte(d, cx, cy, lato, filo, fondo=(24, 24, 30)):
    """Le tre carte del logo (Distribuzione/logo.py) centrate in (cx, cy), nel quadrato da 150 scalato a lato."""
    k = lato / 150
    for (x, y), f in zip([(26, 56), (48, 42), (70, 28)], [(70, 70, 80), (120, 120, 132), BLU]):
        x0, y0 = cx - lato / 2 + x * k, cy - lato / 2 + y * k
        d.rounded_rectangle((x0, y0, x0 + 44 * k, y0 + 62 * k), radius=6 * k, fill=fondo, outline=f, width=max(1, round(filo)))


def _rgb(c):
    if isinstance(c, str):
        c = c.lstrip("#")
        return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))
    return tuple(c[:3])


def immagine(alto=40, fondo="#101014", sito=True, alfa=1.0):
    """Il marchio alto `alto` pixel: il logo a sinistra, il nome e sotto il sito. RGBA, trasparente intorno. Tenuto per (alto, fondo, sito, alfa)."""
    k = (alto, _rgb(fondo), sito, alfa)
    if k in _PIL:
        return _PIL[k]
    s = SUP
    A = alto * s
    fn, fs = font(A * (0.40 if sito else 0.56)), font(A * 0.25, "SemiBold SemiCondensed")
    m = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    bn, bs = m.textbbox((0, 0), NOME, font=fn), m.textbbox((0, 0), SITO, font=fs)
    lato = A
    gap = round(A * 0.22)
    larga = lato + gap + max(bn[2] - bn[0], (bs[2] - bs[0]) if sito else 0) + 2 * s
    im = Image.new("RGBA", (larga, A), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    logo_carte(d, lato / 2, A / 2, lato * 1.06, max(1.5 * s, A * 0.045), fondo=_rgb(fondo))
    x = lato + gap
    if sito:
        hn, hs = bn[3] - bn[1], bs[3] - bs[1]
        sp = round(A * 0.10)
        y0 = (A - hn - sp - hs) / 2
        d.text((x - bn[0], y0 - bn[1]), NOME, font=fn, fill=COL_NOME + (255,))
        d.text((x - bs[0], y0 + hn + sp - bs[1]), SITO, font=fs, fill=COL_SITO + (255,))
    else:
        d.text((x - bn[0], (A - (bn[3] - bn[1])) / 2 - bn[1]), NOME, font=fn, fill=COL_NOME + (255,))
    out = im.resize((max(1, round(larga / s)), alto), Image.LANCZOS)
    if alfa < 1.0:
        out.putalpha(out.getchannel("A").point(lambda v: int(v * alfa)))
    _PIL[k] = out
    return out


def foto(widget, alto=40, fondo="#101014", sito=True, alfa=1.0):
    """La PhotoImage del marchio per la radice di Tk del widget (una per radice), registrata anche per la tela sulla scheda video."""
    from PIL import ImageTk
    root = widget._root()
    k = (id(root), alto, _rgb(fondo), sito, alfa)
    v = _FOTO.get(k)
    if v is not None and v[0] is root:
        return v[1]
    pil = immagine(alto, fondo, sito, alfa)
    f = ImageTk.PhotoImage(pil, master=root)
    try:
        import tela_gpu         # la sorgente per la tela sulla scheda video (il Board): non carica pyglet
        tela_gpu.registra(f, pil)
    except Exception:          # noqa: BLE001
        pass
    _FOTO[k] = (root, f)
    return f


def piede(tk, padre, bg, alto=38):
    """La riga in fondo alle finestre dei mazzi (scheda e builder): il marchio a destra. -> il Frame (da mettere col pack)."""
    fr = tk.Frame(padre, bg=bg)
    lb = tk.Label(fr, image=foto(fr, alto, bg), bg=bg, bd=0, highlightthickness=0)
    lb.pack(side="right", padx=(0, 14), pady=(2, 8))
    fr.marchio = lb             # per le prove
    return fr


def _px(im):
    return im.get_flattened_data() if hasattr(im, "get_flattened_data") else im.getdata()


def _prova():
    casi = []
    im = immagine(40, "#101014")
    casi.append(("alto 40, piu' largo che alto, RGBA", im.size[1] == 40 and im.size[0] > 120 and im.mode == "RGBA"))
    a = im.getchannel("A")
    casi.append(("trasparente agli angoli, pieno nel disegno", a.getpixel((im.size[0] - 1, 0)) == 0 and max(_px(a)) == 255))
    # il nome ben visibile: pixel chiari (quasi bianchi) nella parte del testo
    chiari = sum(1 for p in _px(im.crop((44, 0, im.size[0], 40))) if p[3] > 200 and min(p[:3]) > 200)
    casi.append(("il nome in chiaro (pixel quasi bianchi nel testo)", chiari > 80))
    blu = sum(1 for p in _px(im.crop((0, 0, 40, 40))) if p[3] > 150 and p[2] > 200 and p[0] < 120)
    casi.append(("il logo con la carta azzurra", blu > 10))
    casi.append(("tenuta: la stessa immagine alla seconda chiamata", immagine(40, "#101014") is im))
    casi.append(("senza sito: un altro disegno (il solo nome)", immagine(40, "#101014", sito=False).tobytes() != im.tobytes()))
    m = immagine(40, "#101014", alfa=0.5)
    casi.append(("alfa 0.5 dimezza la trasparenza", max(_px(m.getchannel("A"))) <= 128))
    ok = all(v for _, v in casi)
    for n, v in casi:
        print(("OK   " if v else "ROSSO"), n)
    print(f"{sum(v for _, v in casi)}/{len(casi)}")
    return ok


if __name__ == "__main__":
    if "--prova" in sys.argv:
        sys.exit(0 if _prova() else 1)
    out = sys.argv[1] if len(sys.argv) > 1 else "marchio.png"
    immagine(80, "#101014").save(out)
    print(out)
