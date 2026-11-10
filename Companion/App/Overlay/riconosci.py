"""Riconosce le carte nella schermata di costruzione di un draft di Arena, solo dallo schermo (3 nov 2026, Magic 07).

Autore, 2 nov 2026: «possiamo evolvere l'app per fare in modo che vada in sovrimpressione al gioco e che evidenzi le
carte da tenere e da scartare per la costruzione del mazzo? In stile Untapped». Questo modulo e' la parte che guarda:
prende un'immagine dello schermo (o della finestra di Arena) e dice quali carte ci sono e dove. Non legge la memoria del
client, non tocca i suoi file, non clicca: guarda i pixel, come farebbe una persona.

La schermata (campione `campioni/costruzione_20261103_000537_schermo0.png`, 1920x1080):
- in alto le carte FUORI dal mazzo, intere, col titolo grande;
- sotto la barra «Draft Deck · 53/40 Cards» il MAZZO, in colonne per costo: carte impilate di cui si vede la barra del
  nome (e «x2», «x3» sotto la barra per le copie), l'ultima della colonna intera.

Come si riconosce:
1. OCR di Windows (ocr.py) sulla zona alta e su quella del mazzo, ingrandite 3x, in due versioni (grigio a contrasto pieno
   e maschera del testo bianco): le righe che somigliano a un nome possibile danno le colonne e il passo delle barre.
2. Secondo giro barra per barra: ogni posto della griglia (colonna x passo) che il primo giro non ha letto si ritaglia, si
   ingrandisce 4x e si legge da solo, tutti insieme in un'immagine sola (una chiamata all'OCR).
3. Il nome si sceglie per somiglianza (difflib) fra i nomi possibili: prima le carte del pool (dal Player.log), poi le
   carte del set, piu' le terre base. Il motore OCR del PC di Autore e' it-IT: i nomi escono sporchi («Yar*le.
   Goliath of Otaria») e la somiglianza li rimette a posto; una riga che somiglia poco a tutto si scarta.

    py -I -X utf8 Companion/App/Overlay/riconosci.py [IMMAGINE] [--pool]    stampa le carte con le coordinate
"""
import os, sys
_casa = os.path.dirname(os.path.abspath(__file__))      # si sale fino a percorsi.py, che mette nel sys.path tutte le cartelle del Companion
while not os.path.isfile(os.path.join(_casa, "percorsi.py")):
    _casa = os.path.dirname(_casa)
if _casa not in sys.path:
    sys.path.insert(0, _casa)
import percorsi  # noqa: E402
import difflib
import json
import re
import time

import numpy as np
from PIL import Image, ImageOps

QUI = os.path.dirname(os.path.abspath(__file__))
RADICE = percorsi.ROOT
from ocr import Ocr  # noqa: E402

CAMPIONE = os.path.join(QUI, "campioni", "costruzione_20261103_000537_schermo0.png")
BASI = ["Plains", "Island", "Swamp", "Mountain", "Forest", "Wastes"]
PLAYER_LOG = os.path.join(os.environ.get("LOCALAPPDATA", ""), "..", "LocalLow", "Wizards Of The Coast", "MTGA", "Player.log")


# ------------------------------------------------------------------ i nomi possibili
def nomi_set(sigla="FRA"):
    """I nomi delle carte del set dall'anagrafe (Espansioni/<SET>/Comune/anagrafe.json), con la faccia davanti delle carte
    a due facce: la barra del nome di Arena mostra la faccia davanti. -> {nome mostrato: nome dell'anagrafe}"""
    f = os.path.join(RADICE, "Espansioni", sigla, "Comune", "anagrafe.json")
    out = {b: b for b in BASI}
    if not os.path.exists(f):
        return out
    a = json.load(open(f, encoding="utf-8"))
    for n in a.get("per_nome", {}):
        out[n] = n
        if " // " in n:
            out[n.split(" // ")[0]] = n
    for c in a.get("carte", {}).values():
        if c.get("nome"):
            out.setdefault(c["nome"], c["nome"])
    return out


def _oggetti_json(riga):
    i = riga.find("{")
    if i < 0:
        return
    try:
        yield json.loads(riga[i:])
    except Exception:
        return


def _cerca_corsi(o, out):
    if isinstance(o, dict):
        if "InternalEventName" in o and "CardPool" in o:
            out.append(o)
        for v in o.values():
            _cerca_corsi(v, out)
    elif isinstance(o, list):
        for v in o:
            _cerca_corsi(v, out)


def pool_dal_log(log=PLAYER_LOG, sigla="FRA"):
    """Il pool dell'ultimo draft (o sealed) nel Player.log: CardPool del corso, piu' mazzo e sideboard se il pool e' vuoto.
    -> (evento, {nome: copie}); i grpId senza nome nell'anagrafe si saltano (sono le basi: le copre BASI)."""
    if not os.path.exists(log):
        return None, {}
    f = os.path.join(RADICE, "Espansioni", sigla, "Comune", "anagrafe.json")
    a = json.load(open(f, encoding="utf-8")) if os.path.exists(f) else {"carte": {}, "alias": {}}
    nome = {int(k): v["nome"] for k, v in a.get("carte", {}).items()}
    for k, v in a.get("alias", {}).items():
        if int(v) in nome:
            nome[int(k)] = nome[int(v)]
    ultimo = None
    with open(log, encoding="utf-8", errors="ignore") as fh:
        for riga in fh:
            if "CardPool" not in riga or "Draft" not in riga and "Sealed" not in riga:
                continue
            corsi = []
            for o in _oggetti_json(riga):
                _cerca_corsi(o, corsi)
            for c in corsi:
                ev = c.get("InternalEventName") or ""
                if ("Draft" in ev or "Sealed" in ev) and (c.get("CardPool") or (c.get("CourseDeck") or {}).get("MainDeck")):
                    ultimo = c
    if not ultimo:
        return None, {}
    ids = list(ultimo.get("CardPool") or [])
    if not ids:
        d = ultimo.get("CourseDeck") or {}
        for e in (d.get("MainDeck") or []) + (d.get("Sideboard") or []):
            ids += [e["cardId"]] * int(e.get("quantity") or 1)
    pool = {}
    for g in ids:
        n = nome.get(int(g))
        if n:
            pool[n] = pool.get(n, 0) + 1
    return ultimo.get("InternalEventName"), pool


def _norm(s):
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", "", s.lower().replace("-", " "))).strip()


class Nomi:
    """La scelta del nome: prima fra le carte del pool, poi fra quelle del set."""

    def __init__(self, pool=(), set_nomi=None):
        self.set = set_nomi or nomi_set()
        self.pool = {m: self.set.get(m, m) for m in list(pool) + BASI}
        for m in list(pool):            # la faccia davanti delle carte a due facce del pool
            if " // " in m:
                self.pool[m.split(" // ")[0]] = m
        self._np = [(_norm(m), m) for m in self.pool]
        self._ns = [(_norm(m), m) for m in self.set]

    @staticmethod
    def _voto(o, n):
        if not o or not n:
            return 0.0
        r = difflib.SequenceMatcher(None, o, n).ratio()
        if len(o) >= 6 and len(o) < len(n):     # barra tagliata o parola persa: la somiglianza col pezzo che c'e'
            sm = difflib.SequenceMatcher(None, o, n)
            m = sum(b.size for b in sm.get_matching_blocks())
            r = max(r, 0.92 * m / len(o) * min(1.0, (len(o) + 4) / len(n)) ** 0.5)
        return r

    def scegli(self, testo):
        """-> (nome dell'anagrafe, voto, da_pool) oppure None."""
        o = _norm(testo)
        if sum(ch.isalpha() for ch in o) < 4:
            return None
        for lista, soglia, da_pool in ((self._np, 0.70, True), (self._ns, 0.82, False)):
            voti = sorted(((self._voto(o, n), m) for n, m in lista), reverse=True)
            if not voti:
                continue
            v, m = voti[0]
            secondo = next((w for w, mm in voti[1:] if (self.pool if da_pool else self.set).get(mm) !=
                            (self.pool if da_pool else self.set).get(m)), 0.0)
            if v >= soglia and (v - secondo >= 0.06 or v >= 0.93):
                return (self.pool if da_pool else self.set)[m], round(v, 3), da_pool
        return None


# ------------------------------------------------------------------ le immagini per l'OCR
def grigio(img, k):
    g = ImageOps.autocontrast(ImageOps.grayscale(img))
    return g.resize((g.width * k, g.height * k), Image.LANCZOS)


def bianco(img, k):
    """Il testo bianco dei nomi in nero su bianco: luminoso e poco saturo."""
    a = np.asarray(img.convert("RGB")).astype(np.int16)
    mx, mn = a.max(2), a.min(2)
    m = (mx > 170) & (mx - mn < 60)
    out = Image.fromarray(np.where(m, 0, 255).astype(np.uint8))
    return out.resize((out.width * k, out.height * k), Image.LANCZOS)


def righe_ocr(ocr, img, box, k, versione):
    """OCR di un ritaglio ingrandito; le parole tornano in coordinate dello schermo."""
    cr = img.crop(box)
    r = ocr.leggi(versione(cr, k))
    out = []
    for rg in r:
        for p in rg["p"]:
            out.append(dict(t=p["t"], x=box[0] + p["x"] / k, y=box[1] + p["y"] / k, w=p["w"] / k, h=p["h"] / k))
    return out


def unisci_parole(parole, salto):
    """Le parole sulla stessa riga e vicine diventano una riga (il motore a volte spezza «Undulatin» «Witness»)."""
    parole = sorted(parole, key=lambda p: (round(p["y"] / 4), p["x"]))
    righe = []
    for p in sorted(parole, key=lambda p: p["x"]):
        for r in righe:
            if abs((r["y"] + r["h"] / 2) - (p["y"] + p["h"] / 2)) < max(r["h"], p["h"]) * 0.6 and \
                    -2 <= p["x"] - (r["x"] + r["w"]) <= salto:
                r["t"] += " " + p["t"]
                fine = p["x"] + p["w"]
                r["y"], r["h"] = min(r["y"], p["y"]), max(r["y"] + r["h"], p["y"] + p["h"]) - min(r["y"], p["y"])
                r["w"] = fine - r["x"]
                break
        else:
            righe.append(dict(p))
    return righe


COPIE = re.compile(r"^[^0-9a-wyz]{0,2}[xX×]\s?([2-9])\W?$|^[^0-9]{0,2}[xX×]([2-9])$")


def _copie(t):
    m = COPIE.match(t.strip())
    if m:
        return int(m.group(1) or m.group(2))
    m = re.fullmatch(r".?[xX×]([2-9])", t.strip())
    return int(m.group(1)) if m else None


# ------------------------------------------------------------------ le copie: «x2», «x3» sotto la barra
# L'OCR legge male un «x4» da solo (3 nov 2026: 2 su 9 sul campione, in ogni versione). Il «xN» e' bianco pieno col bordo
# scuro: la «x» si trova come macchia bianca della sua misura, la cifra accanto si confronta di forma con le cifre 2-9
# disegnate con sei font serif in grassetto di Windows, e vince la cifra scelta da piu' font. Sul campione: 9 su 9, e
# nessun «xN» trovato sulle 6 carte senza copie. Le cifre 5, 7, 8, 9 non ci sono nel campione: non provate su Arena.
FONT_CIFRE = ["georgiab.ttf", "timesbd.ttf", "cambriab.ttf", "BOOKOSB.TTF", "constanb.ttf", "GeorgiaPro-Bold.ttf"]
_MODELLI = None


def _norm_cifra(b):
    ys, xs = np.where(b)
    if len(ys) == 0:
        return None
    b = b[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    v = np.asarray(Image.fromarray((b * 255).astype(np.uint8)).resize((12, 18), Image.BILINEAR)).astype(np.float32) / 255
    v = v.ravel() - v.mean()
    n = np.linalg.norm(v)
    return v / n if n else None


def _modelli():
    global _MODELLI
    if _MODELLI is None:
        from PIL import ImageDraw, ImageFont
        _MODELLI = []
        for f in FONT_CIFRE:
            p = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", f)
            if not os.path.exists(p):
                continue
            ft = ImageFont.truetype(p, 40)
            for d in "x23456789":
                im = Image.new("L", (60, 60), 0)
                ImageDraw.Draw(im).text((10, 5), d, font=ft, fill=255)
                _MODELLI.append((f, 0 if d == "x" else int(d), _norm_cifra(np.asarray(im) > 128)))
    return _MODELLI


def _macchie(m):
    """Le macchie 8-connesse di una maschera piccola: [(y0, y1, x0, x1, pixel)]."""
    H, W = m.shape
    vis = np.zeros_like(m, dtype=bool)
    out = []
    for y in range(H):
        for x in range(W):
            if m[y, x] and not vis[y, x]:
                st, pts = [(y, x)], []
                vis[y, x] = True
                while st:
                    cy, cx = st.pop()
                    pts.append((cy, cx))
                    for yy in (cy - 1, cy, cy + 1):
                        for xx in (cx - 1, cx, cx + 1):
                            if 0 <= yy < H and 0 <= xx < W and m[yy, xx] and not vis[yy, xx]:
                                vis[yy, xx] = True
                                st.append((yy, xx))
                ys, xs = [p[0] for p in pts], [p[1] for p in pts]
                out.append((min(ys), max(ys), min(xs), max(xs), len(pts)))
    return out


def cifra_copie(arr, grig, destra, y, s):
    """arr (RGB int16) e grig (grigio) dello schermo; destra = bordo destro della colonna, y = alto del nome.
    -> il numero di copie (2-9) se sotto la barra c'e' un «xN», altrimenti None."""
    # la zona del «xN» portata alla scala del campione (1080 righe), dove le misure sono tarate
    x0, y0 = int(destra - 64 * s), int(y + 12 * s)
    x1, y1 = int(destra - 10 * s), int(y + 50 * s)
    if x0 < 0 or y1 > arr.shape[0] or x1 > arr.shape[1]:
        return None
    rgb, g = arr[y0:y1, x0:x1], grig[y0:y1, x0:x1]
    if abs(s - 1) > 0.05:
        dim = (x1 - x0) / s, (y1 - y0) / s
        dim = int(round(dim[0])), int(round(dim[1]))
        rgb = np.asarray(Image.fromarray(rgb.astype(np.uint8)).resize(dim, Image.BILINEAR)).astype(np.int16)
        g = np.asarray(Image.fromarray(g.astype(np.uint8)).resize(dim, Image.BILINEAR)).astype(np.float32)
    mx, mn = rgb.max(2), rgb.min(2)
    m = (mx > 200) & (mx - mn < 45)
    xs = [c for c in _macchie(m) if 7 <= c[1] - c[0] + 1 <= 14 and 7 <= c[3] - c[2] + 1 <= 15 and 6 <= c[2] <= 32 and c[4] >= 15]
    for (cy0, cy1, cx0, cx1, _) in sorted(xs, key=lambda c: -c[4]):
        # e' una «x» se ne ha la forma e l'alone scuro del bordo (sul campione: forma 0,68-0,85 e alone 0,77-0,88 sulle
        # 9 vere, 0,11 e 0,19 sul rumore dell'illustrazione di Tether Technician)
        v = _norm_cifra(m[cy0:cy1 + 1, cx0:cx1 + 1])
        forma = max((float(v @ t) for f, d, t in _modelli() if d == 0), default=0) if v is not None else 0
        a0, b0 = max(0, cy0 - 3), max(0, cx0 - 3)
        anello, dentro = g[a0:cy1 + 4, b0:cx1 + 4], m[a0:cy1 + 4, b0:cx1 + 4]
        alone = float(np.mean(anello[~dentro] < 80)) if (~dentro).any() else 0
        if forma < 0.5 or alone < 0.5:
            continue
        box = g[max(0, cy1 - 17):cy1 + 2, cx1 + 1:cx1 + 15] > 130
        if box.shape[1] < 8 or box.sum() < 20:
            continue
        ys_ = np.where(box.any(1))[0]
        if ys_.max() - ys_.min() + 1 < 12:
            continue
        v = _norm_cifra(box)
        if v is None:
            continue
        migliori = {}
        for f, d, t in _modelli():
            if d == 0:
                continue
            c = float(v @ t)
            if c > migliori.get(f, (-2, 0))[0]:
                migliori[f] = (c, d)
        voti = {}
        for c, d in migliori.values():
            voti[d] = voti.get(d, 0) + 1
        d, n = max(voti.items(), key=lambda kv: kv[1])
        if n >= len(migliori) / 2 and max(c for c, dd in migliori.values() if dd == d) > 0.4:
            return d
    return None


# ------------------------------------------------------------------ la schermata
def leggi_schermo(img, ocr, nomi, debug=False):
    """img: la schermata (PIL, la finestra di Arena o lo schermo). -> dict con
    mazzo: [{nome, letto, voto, x, y, w, h, copie, colonna}], fuori: [...], divisorio: y, scala, tempi"""
    t0 = time.time()
    img = img.convert("RGB")
    W, H = img.size
    s = H / 1080.0
    # 1. la barra «Draft Deck · NN/40 Cards» divide le due zone; se non si legge, la proporzione del campione
    testa = righe_ocr(ocr, img, (0, int(0.52 * H), int(0.30 * W), int(0.66 * H)), 2, grigio)
    div, contate, contatore = None, None, None
    for p in testa:
        m = re.search(r"(\d+)\s*/\s*\d+", p["t"])
        if m or re.search(r"card", p["t"], re.I):
            div = max(div or 0, p["y"] + p["h"] + 8 * s)
        if m:
            contate = int(m.group(1))       # le carte nel mazzo secondo Arena: «53/40 Cards»
            contatore = (p["x"], p["y"], p["w"], p["h"])      # dove sta: cambia solo quando cambia il mazzo (la lettura rapida, impronte.py)
    if div is None:
        div = 0.635 * H
    # 2. primo giro sulle due zone
    zone = {"fuori": (0, int(0.17 * H), W, int(div - 40 * s)), "mazzo": (int(0.03 * W), int(div), int(0.83 * W), H)}
    lette = {"fuori": [], "mazzo": []}
    badge = []
    for z, box in zone.items():
        if box[3] <= box[1] + 10:
            continue
        for versione in (grigio, bianco):
            parole = righe_ocr(ocr, img, box, 3, versione)
            for p in parole:
                c = _copie(p["t"])
                if c and z == "mazzo":
                    badge.append(dict(p, copie=c))
            for r in unisci_parole(parole, 30 * s):
                if r["h"] < 7 * s:      # testo delle regole: piu' piccolo dei nomi
                    continue
                sc = nomi.scegli(r["t"])
                if sc:
                    lette[z].append(dict(r, nome=sc[0], voto=sc[1], da_pool=sc[2], giro=1))
    # stesse barre lette due volte (grigio e bianco): una sola, la piu' sicura
    for z in lette:
        tenute = []
        for r in sorted(lette[z], key=lambda r: -r["voto"]):
            if not any(abs(r["y"] - q["y"]) < 12 * s and abs(r["x"] - q["x"]) < 60 * s for q in tenute):
                tenute.append(r)
        lette[z] = tenute
    # 3. le colonne del mazzo e il passo delle barre
    passo = 32 * s
    larg = 180 * s
    colx = []
    for r in sorted(lette["mazzo"], key=lambda r: r["x"]):
        if colx and r["x"] - colx[-1][-1] < 80 * s:
            colx[-1].append(r["x"])
        else:
            colx.append([r["x"]])
    cols = [float(np.median(c)) for c in colx]
    if len(cols) >= 2:          # una colonna senza letture in mezzo: la si rimette col passo delle altre
        d = np.diff(cols)
        dm = float(np.median([x for x in d if x < 260 * s] or [211 * s]))
        piene = [cols[0]]
        for c in cols[1:]:
            while c - piene[-1] > 1.5 * dm:
                piene.append(piene[-1] + dm)
            piene.append(c)
        while piene[-1] + dm + larg * 0.7 < zone["mazzo"][2]:
            piene.append(piene[-1] + dm)
        cols = piene
    for r in lette["mazzo"]:
        r["colonna"] = int(np.argmin([abs(r["x"] - c) for c in cols])) if cols else 0
    ys = sorted(r["y"] for r in lette["mazzo"])
    y0 = min(ys) if ys else div + 15 * s
    # passo: la differenza piu' comune fra barre vicine della stessa colonna
    diffe = []
    for ci in range(len(cols)):
        yy = sorted(r["y"] for r in lette["mazzo"] if r["colonna"] == ci)
        diffe += [b - a for a, b in zip(yy, yy[1:]) if 20 * s < b - a < 45 * s]
    if diffe:
        passo = float(np.median(diffe))
    # 4. secondo giro: i posti della griglia non letti, uno per uno
    posti = []
    for ci, cx in enumerate(cols):
        prese = [r for r in lette["mazzo"] if r["colonna"] == ci]
        fondo = max([r["y"] for r in prese], default=y0) + 2.5 * passo     # sotto l'ultima barra letta c'e' solo la carta intera
        k = 0
        while True:
            y = y0 + k * passo
            if y + 14 * s > H or y > fondo:
                break
            if not any(abs(r["y"] - y) < passo * 0.45 for r in prese):
                posti.append((ci, cx, y))
            k += 1
    if posti:
        k = 4
        alto = int(round(22 * s))
        larg_r = int(round(larg - 8 * s))
        tela = Image.new("L", ((larg_r + 20) * k, len(posti) * (alto + 16) * k), 255)
        for i, (ci, cx, y) in enumerate(posti):
            cr = img.crop((int(cx - 4 * s), int(y - 5 * s), int(cx - 4 * s) + larg_r, int(y - 5 * s) + alto))
            tela.paste(grigio(cr, k), (10 * k, i * (alto + 16) * k + 8 * k))
        parole = ocr.leggi(tela)
        per_posto = {}
        for rg in parole:
            for p in rg["p"]:
                i = int((p["y"] + p["h"] / 2) / k // (alto + 16))
                if 0 <= i < len(posti):
                    per_posto.setdefault(i, []).append(p)
        for i, pp in per_posto.items():
            pp.sort(key=lambda p: p["x"])
            testo = " ".join(p["t"] for p in pp)
            ci, cx, y = posti[i]
            c = _copie(testo)
            sc = nomi.scegli(testo)
            if sc:
                x = cx - 4 * s + (pp[0]["x"] / k - 10)
                ylocale = pp[0]["y"] / k - i * (alto + 16) - 8
                lette["mazzo"].append(dict(t=testo, x=x, y=y - 5 * s + ylocale, w=sum(p["w"] for p in pp) / k,
                                           h=max(p["h"] for p in pp) / k, nome=sc[0], voto=sc[1], da_pool=sc[2], giro=2,
                                           colonna=ci))
            elif c:
                badge.append(dict(t=testo, x=cx + larg * 0.7, y=y, w=10, h=10, copie=c))
    # 5. le copie. Nella pila una carta con piu' copie occupa due posti: la barra e sotto la striscia col «xN». Si leggono
    # solo le carte con un posto libero sotto (o l'ultima della colonna), tutte insieme in un'immagine sola.
    for r in lette["mazzo"]:
        r["cx"] = cols[r["colonna"]] if cols else r["x"]
        r["copie"] = 1
    da_leggere = []
    for ci in range(len(cols)):
        cc = sorted((r for r in lette["mazzo"] if r["colonna"] == ci), key=lambda r: r["y"])
        for a, b in zip(cc, cc[1:] + [None]):
            if b is None or b["y"] - a["y"] > 1.5 * passo:
                da_leggere.append(a)
    if da_leggere:
        arr = np.asarray(img).astype(np.int16)
        grig = np.asarray(img.convert("L")).astype(np.float32)
        for r in da_leggere:
            c = cifra_copie(arr, grig, r["cx"] + larg, r["y"], s)
            if c:
                r["copie"] = c
            else:
                # la forma non si legge: il primo giro dell'OCR per posizione, se l'ha visto
                cand = [b for b in badge if r["cx"] + larg * 0.45 < b["x"] < r["cx"] + larg + 10 * s and
                        0 < b["y"] - r["y"] < passo * 1.6]
                if cand:
                    r["copie"] = cand[0]["copie"]
                    r["copie_da"] = "ocr"
    # in alto: il titolo e' la prima riga della carta; le righe sotto (regole, tipo, artista) si buttano, e cosi' quelle
    # fuori dalla riga dei titoli
    tenute = []
    for r in sorted(lette["fuori"], key=lambda r: r["y"]):
        if not any(abs(r["x"] - q["x"]) < 150 * s and 0 <= r["y"] - q["y"] < 380 * s for q in tenute):
            tenute.append(r)
    sicure = [r["y"] for r in tenute if r["voto"] >= 0.85]
    if sicure:
        tenute = [r for r in tenute if min(abs(r["y"] - y) for y in sicure) < 15 * s]
    lette["fuori"] = tenute
    for r in lette["fuori"]:
        r["copie"] = 1
        r["cx"] = r["x"]
    out = dict(mazzo=sorted(lette["mazzo"], key=lambda r: (r["colonna"], r["y"])),
               fuori=sorted(lette["fuori"], key=lambda r: r["x"]), divisorio=div, contate=contate, contatore=contatore, scala=s, passo=passo, colonne=cols,
               larghezza=larg, secondi=round(time.time() - t0, 2), posti_riletti=len(posti))
    if debug:
        out["badge"] = badge
    return out


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    f = args[0] if args else CAMPIONE
    usa_pool = "--pool" in sys.argv
    ev, pool = pool_dal_log() if usa_pool else (None, {})
    if usa_pool:
        print(f"pool dal log: {ev}, {sum(pool.values())} carte, {len(pool)} nomi")
    nomi = Nomi(pool)
    with Ocr() as o:
        r = leggi_schermo(Image.open(f), o, nomi, debug=True)
    print(f"{f}: {r['secondi']} s, divisorio y {r['divisorio']:.0f}, passo {r['passo']:.1f}, colonne "
          + ", ".join(f"{c:.0f}" for c in r["colonne"]) + f", posti riletti {r['posti_riletti']}")
    for z in ("fuori", "mazzo"):
        tot = sum(x["copie"] for x in r[z])
        print(f"\n{z.upper()}: {len(r[z])} barre, {tot} carte")
        for x in r[z]:
            print(f"  col {x.get('colonna', '-')!s:>2} ({x['x']:5.0f},{x['y']:5.0f}) x{x['copie']}  {x['nome']:34} "
                  f"voto {x['voto']:.2f} giro {x['giro']}{'' if x['da_pool'] else ' (dal set)'}  <- {x['t']!r}")


if __name__ == "__main__":
    main()
