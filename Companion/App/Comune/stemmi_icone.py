"""Gli stemmi del pick, disegnati (Autore, 8 nov 2026: «lo stemma deve essere di fuoco per il pick di valore, poi oro argento
bronzo»; «fai un quadrato con dentro il value della carta, attorno al quadrato il fuoco per il pick e poi scudi con numero oro
argento e bronzo»; «facciamoli piu' in stile dell'app, piu' high tech»; «il fuoco fallo a modo di corona»; «gli altri stemmi non
farli finire a punta»; «ok vanno bene»).

Il pick: un quadrato con gli angoli tagliati, il valore dentro e sopra una corona di cinque fiamme con una gemma sulle punte. Le
altre tre: scudi a fondo piatto, oro, argento e bronzo. Bordo sottile luminoso coi colori del metallo, fondo delle schede
(#18181c), numero in Poppins come la finestra. Si disegna 4 volte piu' grande e si rimpicciolisce.

    py -I -X utf8 Companion/App/Comune/stemmi_icone.py --prova      le quattro forme, con la prova negativa (valori diversi, immagini diverse)
"""
import os, sys
_casa = os.path.dirname(os.path.abspath(__file__))      # si sale fino a percorsi.py, che mette nel sys.path tutte le cartelle del Companion
while not os.path.isfile(os.path.join(_casa, "percorsi.py")):
    _casa = os.path.dirname(_casa)
if _casa not in sys.path:
    sys.path.insert(0, _casa)
import percorsi  # noqa: E402
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

FONTI = percorsi.GRAFICA

K = 4
FONDO = (24, 24, 28)          # #18181c, le schede
COLORI = {"fuoco": [(255, 214, 90), (255, 122, 26), (232, 52, 30)],      # dal giallo al rosso
          "oro": [(255, 236, 150), (240, 192, 64), (176, 128, 20)],
          "argento": [(240, 244, 250), (196, 204, 218), (120, 128, 144)],
          "bronzo": [(246, 196, 150), (208, 136, 80), (130, 74, 34)]}


def font(h, medio=True):
    return ImageFont.truetype(os.path.join(FONTI, "Poppins-Medium.ttf" if medio else "Poppins-Regular.ttf"), h)


def sfuma(L, cols, verticale=True):
    """Una sfumatura dall'alto in basso fra tre colori."""
    im = Image.new("RGBA", (L, L))
    d = ImageDraw.Draw(im)
    for y in range(L):
        t = y / (L - 1)
        a, b, u = (cols[0], cols[1], t * 2) if t < 0.5 else (cols[1], cols[2], (t - 0.5) * 2)
        d.line([(0, y), (L, y)], fill=tuple(int(a[i] + (b[i] - a[i]) * u) for i in range(3)) + (255,))
    return im


def smussato(c, r, taglio):
    """Un quadrato coi quattro angoli tagliati (ottagono stretto)."""
    x0, y0, x1, y1 = c - r, c - r, c + r, c + r
    return [(x0 + taglio, y0), (x1 - taglio, y0), (x1, y0 + taglio), (x1, y1 - taglio), (x1 - taglio, y1), (x0 + taglio, y1), (x0, y1 - taglio), (x0, y0 + taglio)]


def scudo_forma(c, w, h, top):
    """Lo scudo tecnico: spalle tagliate, fianchi dritti, punta in basso."""
    x0, x1 = c - w / 2, c + w / 2
    t = w * 0.16
    # senza punta (Autore, 8 nov 2026: «gli altri stemmi non farli finire a punta»): fondo piatto, angoli di sotto tagliati piu' larghi
    b = w * 0.24
    return [(x0 + t, top), (x1 - t, top), (x1, top + t), (x1, top + h - b), (x1 - b, top + h), (x0 + b, top + h), (x0, top + h - b), (x0, top + t)]


def bagliore(maschera, col, r):
    g = Image.new("RGBA", maschera.size, col + (0,))
    g.putalpha(maschera.filter(ImageFilter.GaussianBlur(r)))
    return g


def disegna(tipo, valore, lato=48, spento=False):
    """L'immagine PIL dello stemma: tipo fuoco (il pick, con la corona), oro, argento o bronzo; spento = i pick passati, piu' tenui."""
    L = lato * K
    cols = COLORI[tipo]
    im = Image.new("RGBA", (L, L), (0, 0, 0, 0))
    c = L / 2
    if tipo == "fuoco":
        c0 = c
        c = c0 + L * 0.10                       # il quadrato scende: sopra c'e' posto per le fiamme
        forma = smussato(c, L * 0.27, L * 0.08)
        # le fiamme: tre lingue geometriche sopra, a punta, come un'icona e non un disegno
        fi = Image.new("L", (L, L), 0); df = ImageDraw.Draw(fi)
        top = c - L * 0.27
        # la corona di fuoco: una fascia sopra il quadrato e cinque punte a fiamma, simmetriche, la piu' alta al centro;
        # ogni punta e' una lingua che si piega verso l'esterno, con una gemma luminosa sulla cima
        larg = L * 0.27
        df.rectangle([c - larg, top - L * 0.045, c + larg, top + 2], fill=255)
        punte = [(-0.22, 0.12, 0.055), (-0.11, 0.18, 0.06), (0.0, 0.25, 0.07), (0.11, 0.18, 0.06), (0.22, 0.12, 0.055)]
        cime = []
        for dx, h, w in punte:
            x = c + dx * L; base = top - L * 0.04; hh = h * L; ww = w * L
            piega = (1 if dx > 0 else -1 if dx < 0 else 0) * ww * 0.45
            pts = [(x - ww, base)]
            for t in (0.25, 0.5, 0.75):
                pts.append((x - ww * (1 - t) + piega * t * t, base - hh * t))
            pts.append((x + piega, base - hh))
            for t in (0.75, 0.5, 0.25):
                pts.append((x + ww * (1 - t) * 0.85 + piega * t * t, base - hh * t * 0.92))
            pts.append((x + ww, base))
            df.polygon(pts, fill=255)
            cime.append((x + piega, base - hh))
        lingue = sfuma(L, cols); lingue.putalpha(fi)
        im.alpha_composite(bagliore(fi, cols[1], K * 3))
        im.alpha_composite(lingue)
        dg = ImageDraw.Draw(im)
        for x, y in cime:                       # le gemme sulle punte
            g = Image.new("L", (L, L), 0); ImageDraw.Draw(g).ellipse([x - K * 2.2, y - K * 2.2, x + K * 2.2, y + K * 2.2], fill=255)
            im.alpha_composite(bagliore(g, cols[0], K * 2))
            dg.ellipse([x - K * 1.3, y - K * 1.3, x + K * 1.3, y + K * 1.3], fill=(255, 246, 200, 255))
    else:
        forma = scudo_forma(c, L * 0.62, L * 0.70, L * 0.14)
    # il bordo luminoso: maschera del contorno, sfumato nei colori del metallo, col bagliore fuori
    m_pieno = Image.new("L", (L, L), 0); ImageDraw.Draw(m_pieno).polygon(forma, fill=255)
    m_dentro = Image.new("L", (L, L), 0)
    dentro = [((x - c) * 0.90 + c, (y - c) * 0.90 + c + (L * 0.01 if tipo != "fuoco" else 0)) for x, y in forma]
    ImageDraw.Draw(m_dentro).polygon(dentro, fill=255)
    bordo = ImageChops.subtract(m_pieno, m_dentro)
    im.alpha_composite(bagliore(m_pieno, cols[1], K * 4))
    fondo = Image.new("RGBA", (L, L), FONDO + (255,)); fondo.putalpha(m_dentro)
    # una velatura del colore dall'alto, come un vetro
    vel = sfuma(L, [tuple(int(v * 0.35) for v in cols[1]), FONDO, FONDO]); vel.putalpha(m_dentro)
    im.alpha_composite(fondo); im.alpha_composite(vel)
    lin = sfuma(L, cols); lin.putalpha(bordo)
    im.alpha_composite(lin)
    # le tacche da HUD: due trattini sottili sotto il numero
    d = ImageDraw.Draw(im)
    cy = c + (L * 0.0 if tipo == "fuoco" else -L * 0.02)
    s = f"{valore:.1f}"
    f = font(int(L * (0.22 if tipo == "fuoco" else 0.20)))
    b = d.textbbox((0, 0), s, font=f)
    d.text((c - (b[2] + b[0]) / 2, cy - (b[3] + b[1]) / 2), s, font=f, fill=(255, 255, 255, 255))
    y = cy + L * 0.15
    for k in (-1, 1):
        d.line([(c + k * L * 0.03, y), (c + k * L * 0.11, y)], fill=cols[1] + (220,), width=K)
    im = im.resize((lato, lato), Image.LANCZOS)
    if spento:
        im.putalpha(im.getchannel("A").point(lambda a: a * 45 // 100))
    return im


def prova():
    ok = tot = 0

    def caso(n, v):
        nonlocal ok, tot
        tot += 1; ok += bool(v); print(("  ok  " if v else "  NO  ") + n)
    im = {k: disegna(k, 55.1, 40) for k in COLORI}
    caso("quattro stemmi da 40 pixel", all(x.size == (40, 40) for x in im.values()))
    caso("il fuoco ha la corona: pixel pieni nella fascia alta", any(im["fuoco"].getpixel((x, 4))[3] > 120 for x in range(40)))
    caso("gli scudi non finiscono a punta: il fondo e' largo", sum(1 for x in range(40) if im["oro"].getpixel((x, 30))[3] > 200) > 12)
    caso("spento e' piu' tenue", disegna("oro", 55.1, 40, spento=True).getchannel("A").getextrema()[1] < im["oro"].getchannel("A").getextrema()[1])
    caso("prova negativa: un altro valore da' un'altra immagine", disegna("oro", 51.0, 40).tobytes() != im["oro"].tobytes())
    print(f"stemmi_icone --prova: {ok}/{tot}")
    return ok == tot


if __name__ == "__main__":
    if "--prova" in sys.argv:
        sys.exit(0 if prova() else 1)
    print(__doc__)
