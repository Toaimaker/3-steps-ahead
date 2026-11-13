"""Le icone: leghe, jolly, risorse, simboli dei set, mana, azioni della chat, emoji."""
import json
import os

from ambiente import ASSET
from dati_drafter import calendario as calendario_draft


LEGHE_DIR = os.path.join(ASSET, "leghe")


def logo_lega(tipo, lega, alto=22):
    """Il png del logo della lega (tipo: limited o constructed) alto «alto» pixel, fatto una volta dall'icona di Arena."""
    sorg = os.path.join(LEGHE_DIR, f"{tipo}_{lega}.png")
    if not os.path.exists(sorg):
        return None
    out = os.path.join(LEGHE_DIR, f"{tipo}_{lega}_{alto}.png")
    if not os.path.exists(out):
        from PIL import Image
        im = Image.open(sorg).convert("RGBA")
        im.resize((max(1, round(im.width * alto / im.height)), alto), Image.LANCZOS).save(out)
    return out


JOLLY_DIR = os.path.join(ASSET, "jolly")



def icona_jolly(k, alto=28):
    """Il png del jolly di Arena (k: M, R, U, C) alto «alto» pixel. Le icone sono ritagliate, col suo ok (18 ott 2026),
    dall'immagine ufficiale dei jolly di Wizards (PlayMTGArena.com, «Wildcards») pubblicata nell'articolo di Draftsim sui
    wildcard (draftsim.com/wp-content/uploads/2019/12/wildcard-pic.png): Companion/Grafica/jolly/jolly_<k>.png."""
    sorg = os.path.join(JOLLY_DIR, f"jolly_{k}.png")
    if not os.path.exists(sorg):
        return None
    out = os.path.join(JOLLY_DIR, f"jolly_{k}_{alto}.png")
    if not os.path.exists(out):
        from PIL import Image
        im = Image.open(sorg).convert("RGBA")
        im.resize((max(1, round(im.width * alto / im.height)), alto), Image.LANCZOS).save(out)
    return out


RISORSE_DIR = os.path.join(ASSET, "risorse")


def icona_risorsa(nome, alto=18):
    """Il png dell'icona di Arena (oro, gemma, busta) alto «alto» pixel, o None se il file non c'e'."""
    sorg = os.path.join(RISORSE_DIR, f"{nome}.png")
    if not os.path.exists(sorg):
        return None
    out = os.path.join(RISORSE_DIR, f"{nome}_{alto}.png")
    if not os.path.exists(out):
        from PIL import Image
        im = Image.open(sorg).convert("RGBA")
        im.resize((max(1, round(im.width * alto / im.height)), alto), Image.LANCZOS).save(out)
    return out


SET_DIR = os.path.join(ASSET, "set")


def icona_set(codice, alto=16, colore=(190, 190, 194)):
    """Il simbolo originale dell'espansione (Scryfall, svgs.scryfall.io/sets/<codice>.svg, scaricato col suo ok il 18 ott
    2026 in Companion/Grafica/set/) reso in png alto «alto» pixel, nel grigio chiaro del testo: i simboli sono neri e il
    fondo della finestra e' scuro. None se il simbolo non c'e'."""
    sorg = os.path.join(SET_DIR, f"{codice.lower()}.svg")
    if not os.path.exists(sorg):
        return None
    out = os.path.join(SET_DIR, f"{codice.lower()}_{alto}.png")
    if not os.path.exists(out):
        try:
            import pymupdf as fitz
        except ImportError:
            import fitz
        import io
        from PIL import Image
        doc = fitz.open(sorg); pg = doc[0]; z = 4 * alto / max(pg.rect.height, 1)
        im = Image.open(io.BytesIO(pg.get_pixmap(matrix=fitz.Matrix(z, z), alpha=True).tobytes("png"))).convert("RGBA")
        a = im.getchannel("A")
        tinta = Image.new("RGBA", im.size, colore + (255,)); tinta.putalpha(a)
        tinta.resize((max(1, round(im.width * alto / im.height)), alto), Image.LANCZOS).save(out)
    return out


_NOMI_SET = None


def nome_set(codice):
    """Il nome dell'espansione: dal calendario dei draft (Regole/calendario_set.json) o da Companion/Grafica/set/nomi.json
    (i nomi di Scryfall scaricati insieme ai simboli, 18 ott 2026). None se non si sa."""
    global _NOMI_SET
    if _NOMI_SET is None:
        try:
            _NOMI_SET = json.load(open(os.path.join(SET_DIR, "nomi.json"), encoding="utf-8"))
        except (OSError, ValueError):
            _NOMI_SET = {}
        for k, v in calendario_draft().items():
            if v.get("nome"):
                _NOMI_SET[k] = v["nome"]
    return _NOMI_SET.get(codice)


def icone_mana(lato=16):
    """I simboli veri di Scryfall (svg in Companion/finestra), resi in png con PyMuPDF."""
    out = {}
    try:
        for k in "WUBRG":
            png = os.path.join(ASSET, f"mana_{k}_{lato}.png")
            if not os.path.exists(png):
                try:        # PyMuPDF solo se un png manca davvero: importarlo costava 0,1 s a ogni avvio (11 nov 2026)
                    import pymupdf as fitz
                except ImportError:
                    import fitz
                doc = fitz.open(os.path.join(ASSET, f"mana_{k}.svg"))
                pg = doc[0]; z = lato / pg.rect.width
                pg.get_pixmap(matrix=fitz.Matrix(z, z), alpha=True).save(png)
            out[k] = png
    except Exception:
        pass
    return out


# Le icone delle azioni: tratti in stile Tabler (licenza MIT), disegnate in svg e rese in png con PyMuPDF.
ICONE = {
    "gioca": "<rect x='6' y='3' width='12' height='18' rx='2'/><path d='M10 12l2 -3l2 3l-2 3z'/>",
    "magia": "<rect x='6' y='3' width='12' height='18' rx='2'/><path d='M10 12l2 -3l2 3l-2 3z'/>",
    "attacca": "<path d='M21 3v5l-11 9l-4 4l-3 -3l4 -4l9 -11z'/><path d='M5 13l6 6'/><path d='M14.32 17.32l3.68 3.68l3 -3l-3.365 -3.365'/><path d='M10 5.5l-2 -2.5h-5v5l3 2.5'/>",
    "difendi": "<path d='M12 3a12 12 0 0 0 8.5 3a12 12 0 0 1 -8.5 15a12 12 0 0 1 -8.5 -15a12 12 0 0 0 8.5 -3'/>",
    "scoperto": "<path d='M12 3a12 12 0 0 0 8.5 3a12 12 0 0 1 -8.5 15a12 12 0 0 1 -8.5 -15a12 12 0 0 0 8.5 -3'/><path d='M3 3l18 18'/>",
    "occhio": "<path d='M10 12a2 2 0 1 0 4 0a2 2 0 0 0 -4 0'/><path d='M21 12c-2.4 4 -5.4 6 -9 6c-3.6 0 -6.6 -2 -9 -6c2.4 -4 5.4 -6 9 -6c3.6 0 6.6 2 9 6'/>",
    "mano": "<rect x='3' y='6' width='9' height='14' rx='1.5'/><rect x='12' y='4' width='9' height='14' rx='1.5'/>",
    "pick": "<rect x='6' y='3' width='12' height='18' rx='2'/><path d='M9 12h6M12 9v6'/>",
    "mazzo": "<rect x='7' y='7' width='12' height='14' rx='2'/><path d='M5 17V5a2 2 0 0 1 2 -2h8'/>",
    "controllo": "<path d='M3 12a9 9 0 1 0 18 0a9 9 0 1 0 -18 0'/><path d='M9 12l2 2l4 -4'/>",
    "avviso": "<path d='M12 9v4'/><path d='M10.363 3.591l-8.106 13.534a1.914 1.914 0 0 0 1.636 2.871h16.214a1.914 1.914 0 0 0 1.636 -2.87l-8.106 -13.536a1.914 1.914 0 0 0 -3.274 0z'/><path d='M12 16h.01'/>",
    "vinta": "<path d='M8 21h8M12 17v4M7 4h10v5a5 5 0 0 1 -10 0z'/><path d='M7 6H4a3 3 0 0 0 3 4M17 6h3a3 3 0 0 1 -3 4'/>",
    "persa": "<path d='M18 6l-12 12M6 6l12 12'/>",
    "pw": "<path d='M12 3l2.2 5.3l5.8 .5l-4.4 3.8l1.4 5.6l-5 -3l-5 3l1.4 -5.6l-4.4 -3.8l5.8 -.5z'/>",
    "mana": "<path d='M13 3l0 7l6 0l-8 11l0 -7l-6 0l8 -11'/>",
    "catena": "<path d='M9 15l6 -6'/><path d='M11 6l.463 -.536a5 5 0 0 1 7.071 7.072l-.534 .464'/><path d='M13 18l-.397 .534a5.068 5.068 0 0 1 -7.127 0a4.972 4.972 0 0 1 0 -7.071l.524 -.463'/>",
    "ventaglio": "<rect x='8' y='5' width='8' height='13' rx='1.4' transform='rotate(-24 12 19)'/><rect x='8' y='5' width='8' height='13' rx='1.4' transform='rotate(24 12 19)'/>",
    "cambio": "<path d='M20 11a8.1 8.1 0 0 0 -15.5 -2m-.5 -4v4h4'/><path d='M4 13a8.1 8.1 0 0 0 15.5 2m.5 4v-4h-4'/>",
}
# il martelletto del craft, nello stile Tabler delle altre icone della finestra (icona «hammer», licenza MIT)
ICONE.setdefault("martello", "<path d='M11.414 10l-7.383 7.418a2.091 2.091 0 0 0 0 2.967a2.11 2.11 0 0 0 2.976 0l7.407 -7.385'/>"
                                "<path d='M18.121 15.293l2.586 -2.586a1 1 0 0 0 0 -1.414l-7.586 -7.586a1 1 0 0 0 -1.414 0l-2.586 2.586"
                                "a1 1 0 0 0 0 1.414l7.586 7.586a1 1 0 0 0 1.414 0z'/>")


def icona_azione(nome, colore, lato=16):
    png = os.path.join(ASSET, f"az_{nome}_{colore[1:]}_{lato}.png")
    if not os.path.exists(png):
        try:
            import pymupdf as fitz
        except ImportError:
            import fitz
        import io
        from PIL import Image
        svg = (f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='{colore}' stroke-width='2.1' "
               f"stroke-linecap='round' stroke-linejoin='round'>{ICONE[nome]}</svg>")
        doc = fitz.open(stream=svg.encode(), filetype="svg"); pg = doc[0]; z = 4 * lato / pg.rect.width
        big = Image.open(io.BytesIO(pg.get_pixmap(matrix=fitz.Matrix(z, z), alpha=True).tobytes("png")))
        big.resize((lato, lato), Image.LANCZOS).save(png)
    return png


MEDAGLIE = {"fuoco": ("\U0001F525", "fuoco"), "oro": ("\U0001F947", "oro"), "argento": ("\U0001F948", "argento"), "bronzo": ("\U0001F949", "bronzo")}


def emoji_png(car, nome, lato=20):
    """Un'emoji a colori (Segoe UI Emoji di Windows) resa in png: Tk da solo non disegna le emoji fuori dal piano base."""
    png = os.path.join(ASSET, f"emoji_{nome}_{lato}.png")
    if not os.path.exists(png):
        from PIL import Image, ImageDraw, ImageFont
        f = ImageFont.truetype(os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", "seguiemj.ttf"), 109)
        im = Image.new("RGBA", (220, 220), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
        d.text((40, 40), car, font=f, embedded_color=True)
        im = im.crop(im.getbbox())
        q = max(im.size); sq = Image.new("RGBA", (q, q), (0, 0, 0, 0)); sq.paste(im, ((q - im.size[0]) // 2, (q - im.size[1]) // 2))
        sq.resize((lato, lato), Image.LANCZOS).save(png)
    return png


def icona_omino(colore, lato=14):
    """L'omino dei turni (testa e spalle), disegnato qui e reso in png con PyMuPDF."""
    png = os.path.join(ASSET, f"omino_{colore[1:]}_{lato}.png")
    if not os.path.exists(png):
        try:
            import pymupdf as fitz
        except ImportError:
            import fitz
        svg = (f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'><circle cx='12' cy='7' r='4.6' fill='{colore}'/>"
               f"<path d='M3 23c0-5.2 4-8.6 9-8.6s9 3.4 9 8.6z' fill='{colore}'/></svg>")
        doc = fitz.open(stream=svg.encode(), filetype="svg"); pg = doc[0]; z = lato / pg.rect.width
        pg.get_pixmap(matrix=fitz.Matrix(z, z), alpha=True).save(png)
    return png
