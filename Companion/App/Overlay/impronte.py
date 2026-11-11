"""Le impronte delle barre: la lettura rapida dell'overlay della costruzione (Autore, 6 nov 2026: «l'hud ci mette un sacco ad
aggiornarsi quando rimuovo le carte», «come fa untapped gg ad avere un hud interattivo al ms? possiamo averlo anche noi?», «Sì, costruiscilo»).

Il log di Arena non scrive le carte tolte durante la costruzione: una sola riga, EventSetDeck, all'invio del mazzo. Resta lo schermo, e li'
il tempo se ne andava tutto nell'OCR (2,5-3,9 s a lettura; la foto 50 ms). Ma la barra di una carta e' sempre la stessa immagine: basta
leggerla una volta. Dopo una lettura OCR buona, impara() tiene l'immagine del nome di ogni barra; leggi() rifa' la lettura confrontando le
immagini sui posti della griglia, senza OCR. Solo pixel dello schermo: niente memoria del client.

La lettura rapida non sostituisce l'OCR: lo anticipa. Una barra mai vista non si riconosce (una carta rimessa dall'alto), e la lettura OCR
che segue a schermo fermo corregge tutto e impara. Una griglia cambiata (finestra ridimensionata, mazzo scorso) non da' corrispondenze:
leggi() torna None e si aspetta l'OCR.

    py -I -X utf8 Companion/App/Overlay/impronte.py --prova     il campione, una carta tolta per finta, le prove negative
"""
import os, sys
_casa = os.path.dirname(os.path.abspath(__file__))      # si sale fino a percorsi.py, che mette nel sys.path tutte le cartelle del Companion
while not os.path.isfile(os.path.join(_casa, "percorsi.py")):
    _casa = os.path.dirname(_casa)
if _casa not in sys.path:
    sys.path.insert(0, _casa)
import percorsi  # noqa: E402
import hashlib
import time

import numpy_leggero  # noqa: E402
np = numpy_leggero.carica()      # senza i 600 MB di OpenBLAS su un PC con tanti processori (numpy_leggero)
from PIL import Image

QUI = os.path.dirname(os.path.abspath(__file__))
import riconosci as R  # noqa: E402

LARGO, ALTO = 150, 18       # il ritaglio del nome, alla scala del campione (1080 righe): la colonna delle barre e' larga 180
RIDUZIONE = 2               # si confronta la media di 2 x 2 pixel: regge una barra ridisegnata a mezzo pixel di distanza (le barre stanno ogni 32,5 pixel)
MARGINE_Y = 5               # la barra puo' stare qualche pixel sopra o sotto il suo posto
DIST_MAX = 14.0             # sopra questa distanza media (0-255) non e' la stessa barra: a mezzo pixel la giusta arriva a 10,8
SCARTO_MIN = 1.6            # e la seconda carta deve stare almeno cosi' lontana (a mezzo pixel, sul campione, almeno 2 volte)
QUOTA_MIN = 0.5             # meno della meta' delle barre di prima riconosciute: non e' la stessa schermata


def _grigio(img):
    return np.asarray(img.convert("L"), dtype=np.uint8)


def ridotta(a):
    """La media a blocchi di RIDUZIONE pixel, anche su una pila di ritagli (l'ultimo asse e' la larghezza)."""
    k = RIDUZIONE
    h, w = a.shape[-2] // k * k, a.shape[-1] // k * k
    a = a[..., :h, :w].astype(np.float32)
    return a.reshape(a.shape[:-2] + (h // k, k, w // k, k)).mean((-3, -1))


class Impronte:
    def __init__(self):
        self.mazzo, self.sopra, self.geo = {}, {}, None
        self.cache, self.cache_copie, self.copie_ocr = {}, {}, {}

    def pronte(self):
        return self.geo is not None and bool(self.mazzo)

    def impara(self, img, let):
        """Da una lettura OCR buona: una immagine per ogni nome letto con sicurezza. Una griglia diversa ricomincia da capo."""
        if not let.get("colonne") or not let.get("mazzo"):
            return False
        g = _grigio(img)
        H, W = g.shape
        s = let["scala"]
        geo = dict(dim=(W, H), s=s, cols=[float(c) for c in let["colonne"]], passo=float(let["passo"]), y0=float(min(r["y"] for r in let["mazzo"])),
                   w=int(round(LARGO * s)), h=int(round(ALTO * s)), larg=float(let["larghezza"]), div=float(let["divisorio"]), m=int(round(MARGINE_Y * s)), let=let)
        vecchia = self.geo
        if vecchia is None or vecchia["dim"] != geo["dim"] or abs(vecchia["passo"] - geo["passo"]) > 1 or abs(vecchia["y0"] - geo["y0"]) > 3 or \
                len(vecchia["cols"]) != len(geo["cols"]) or max(abs(a - b) for a, b in zip(vecchia["cols"], geo["cols"])) > 3:
            self.mazzo, self.sopra, self.cache, self.cache_copie, self.copie_ocr = {}, {}, {}, {}, {}
        else:       # la griglia di prima resta: le barre vecchie stanno sui suoi posti
            geo["y0"], geo["cols"], geo["passo"] = vecchia["y0"], vecchia["cols"], vecchia["passo"]
        self.geo = geo
        for r in let["mazzo"]:
            if r.get("voto", 0) < 0.8:
                continue
            x0, y0 = int(round(r["cx"] - 3 * s)), int(round(r["y"] - 3 * s))
            cr = g[y0:y0 + geo["h"], x0:x0 + geo["w"]]
            if cr.shape != (geo["h"], geo["w"]):
                continue
            if r.get("copie_da") == "ocr":      # un «xN» che la forma non legge: resta quello dell'OCR (Mountain x6 sul campione)
                self.copie_ocr[r["nome"]] = r["copie"]
            self.mazzo.setdefault(r["nome"], []).append(dict(a=ridotta(cr), ox=r["x"] - x0, oy=r["y"] - y0, w=r["w"], h=r["h"], t=r.get("t", ""), da_pool=r.get("da_pool", True)))
            del self.mazzo[r["nome"]][:-3]      # le ultime tre viste
        xs = sorted(r["x"] for r in let["fuori"])
        geo["sopra_passo"] = float(np.median(np.diff(xs))) if len(xs) >= 2 else 266 * s
        geo["sopra_x0"] = xs[0] if xs else None
        geo["sopra_y"] = float(np.median([r["y"] for r in let["fuori"]])) if xs else None
        for r in let["fuori"]:
            if r.get("voto", 0) < 0.8:
                continue
            x0, y0 = int(round(r["x"] - 3 * s)), int(round(r["y"] - 3 * s))
            cr = g[y0:y0 + geo["h"], x0:x0 + geo["w"]]
            if cr.shape == (geo["h"], geo["w"]):
                self.sopra[r["nome"]] = dict(a=ridotta(cr), ox=r["x"] - x0, oy=r["y"] - y0, w=r["w"], h=r["h"], t=r.get("t", ""), da_pool=r.get("da_pool", True))
        self.cache.clear()
        return True

    def _confronta(self, regione, modelli, dy_max, dx_max=0):
        """regione: il ritaglio col margine attorno al posto. -> (nome, modello, dy, dx, distanza) o None."""
        g = self.geo
        h, w = g["h"], g["w"]
        finestre, dove = [], []
        for dy in range(0, 2 * dy_max + 1):
            for dx in range(0, 2 * dx_max + 1):
                f = regione[dy:dy + h, dx:dx + w]
                if f.shape == (h, w):
                    finestre.append(f); dove.append((dy - dy_max, dx - dx_max))
        if not finestre or not modelli:
            return None
        F = ridotta(np.stack(finestre))                   # finestre x altezza x larghezza
        M = np.stack([m["a"] for _n, m in modelli])       # modelli x altezza x larghezza
        d = np.abs(F[:, None] - M[None]).mean((2, 3))     # finestre x modelli
        per = {}
        for j, (n, m) in enumerate(modelli):
            i = int(d[:, j].argmin())
            if n not in per or d[i, j] < per[n][0]:
                per[n] = (float(d[i, j]), m, dove[i])
        ord_ = sorted(per.items(), key=lambda kv: kv[1][0])
        n, (dist, m, (dy, dx)) = ord_[0]
        secondo = ord_[1][1][0] if len(ord_) > 1 else 99.0
        if dist > DIST_MAX or secondo < dist * SCARTO_MIN:
            return None
        return n, m, dy, dx, dist

    def leggi(self, img):
        """La schermata, senza OCR. -> un dizionario come riconosci.leggi_schermo, con «rapida»: True, o None se non e' la stessa griglia."""
        t0 = time.perf_counter()
        ge = self.geo
        if not self.pronte() or img.size != ge["dim"]:
            return None
        rgb = np.asarray(img.convert("RGB"))
        g = np.asarray(img.convert("L"), dtype=np.uint8)
        H, W = g.shape
        s, passo, m_, h, w = ge["s"], ge["passo"], ge["m"], ge["h"], ge["w"]
        modelli = [(n, x) for n, xs in self.mazzo.items() for x in xs]
        per_nome = {}
        for ci, cx in enumerate(ge["cols"]):
            x0 = int(round(cx - 3 * s))
            k = 0
            while True:
                y = int(round(ge["y0"] + k * passo - 3 * s))
                k += 1
                if y + h + m_ > H:
                    break
                y1, y2 = max(0, y - m_), y + h + m_
                reg = g[y1:y2, x0:x0 + w]
                if reg.shape[1] != w:
                    break
                chiave = hashlib.blake2b(reg.tobytes(), digest_size=8).digest()
                if chiave in self.cache:
                    esito = self.cache[chiave]
                else:
                    esito = self.cache[chiave] = self._confronta(reg, modelli, m_)
                if not esito:
                    continue
                n, mod, dy, _dx, dist = esito
                b = dict(t=mod["t"], x=x0 + mod["ox"], y=y + dy + mod["oy"], w=mod["w"], h=mod["h"], nome=n, voto=round(1 - dist / 100, 3), da_pool=mod["da_pool"], giro=0, colonna=ci, cx=cx, copie=1, dist=dist)
                if n not in per_nome or dist < per_nome[n]["dist"]:
                    per_nome[n] = b
        mazzo = sorted(per_nome.values(), key=lambda r: (r["colonna"], r["y"]))
        base = ge["let"]
        if len(mazzo) < QUOTA_MIN * len(base["mazzo"]):
            return None
        # le copie: come nella lettura OCR, solo le barre con un posto libero sotto; lo stesso «xN» non si rilegge due volte
        arr, grig = None, None
        for a, b in zip(mazzo, mazzo[1:] + [None]):
            if b is not None and b["colonna"] == a["colonna"] and b["y"] - a["y"] <= 1.5 * passo:
                continue
            x_, y_ = int(a["cx"] + ge["larg"] - 64 * s), int(a["y"] + 12 * s)
            zona = g[y_:y_ + int(38 * s), x_:x_ + int(54 * s)]
            ch = hashlib.blake2b(zona.tobytes(), digest_size=8).digest()
            if ch not in self.cache_copie:
                if arr is None:
                    arr, grig = rgb.astype(np.int16), g.astype(np.float32)
                self.cache_copie[ch] = R.cifra_copie(arr, grig, a["cx"] + ge["larg"], a["y"], s)
            a["copie"] = self.cache_copie[ch] or self.copie_ocr.get(a["nome"], 1)
        fuori = self._sopra(g, W)
        return dict(mazzo=mazzo, fuori=fuori, divisorio=ge["div"], contate=None, scala=s, passo=passo, colonne=ge["cols"], larghezza=ge["larg"], contatore=base.get("contatore"),
                    secondi=round(time.perf_counter() - t0, 3), posti_riletti=0, rapida=True)

    def _sopra(self, g, W):
        """Le carte in alto: stessa cosa sui posti della riga."""
        ge = self.geo
        if not self.sopra or ge.get("sopra_x0") is None:
            return []
        s, h, w = ge["s"], ge["h"], ge["w"]
        modelli = list(self.sopra.items())
        m_ = int(round(6 * s))
        visti = {}
        i = 0
        while True:
            x0 = int(round(ge["sopra_x0"] + i * ge["sopra_passo"] - 3 * s))
            i += 1
            if x0 + w + m_ > W:
                break
            y0 = int(round(ge["sopra_y"] - 3 * s))
            reg = g[max(0, y0 - m_):y0 + h + m_, max(0, x0 - m_):x0 + w + m_]
            chiave = hashlib.blake2b(reg.tobytes(), digest_size=8).digest()
            if chiave not in self.cache:
                self.cache[chiave] = self._confronta(reg, modelli, m_, m_)
            e = self.cache[chiave]
            if not e:
                continue
            n, mod, dy, dx, dist = e
            b = dict(t=mod["t"], x=x0 + dx + mod["ox"], y=y0 + dy + mod["oy"], w=mod["w"], h=mod["h"], nome=n, voto=round(1 - dist / 100, 3), da_pool=mod["da_pool"], copie=1, cx=x0 + dx + mod["ox"], dist=dist)
            if n not in visti or dist < visti[n]["dist"]:
                visti[n] = b
        return sorted(visti.values(), key=lambda r: r["x"])


class Seguito:
    """Quando rileggere. Si guarda solo il contatore «NN/40 Cards»: cambia quando cambia il mazzo, non quando il mouse passa sopra una carta, e fotografarlo
    costa pochi millisecondi. Quando cambia, per FINESTRA secondi si rilegge tutto a ogni giro: le carte scivolano al loro posto e i primi fotogrammi sono a meta'.
    Si accetta una lettura che si scosta al massimo di SCARTO carte da quelle di prima: di piu' e' una schermata coperta, non una carta tolta."""
    FINESTRA, SCARTO, UGUALE = 0.7, 2, 2.5

    def __init__(self, impronte):
        self.I = impronte
        self.rif, self.fino, self.n0 = None, 0.0, 0

    def passo(self, base, ritaglio, adesso, foto, giudica):
        """base: dict(n, firma) dell'ultima lettura; ritaglio: il contatore adesso (grigio); foto(): la schermata; giudica(let) -> (segni, righe, riepilogo).
        -> (let, segni, righe, rie) se c'e' una lettura nuova da disegnare, se no None."""
        if self.rif is None or self.rif.shape != ritaglio.shape:
            self.rif = ritaglio
            return None
        if float(np.abs(ritaglio.astype(np.int16) - self.rif.astype(np.int16)).mean()) >= self.UGUALE:
            self.rif = ritaglio
            if adesso >= self.fino:
                self.n0 = base["n"]
            self.fino = adesso + self.FINESTRA
        if adesso >= self.fino:
            return None
        let = self.I.leggi(foto())
        if let is None:
            return None
        segni, righe, rie = giudica(let)
        firma = impronta_lettura(let)
        if abs(rie["nel_mazzo"] - self.n0) > self.SCARTO or firma == base.get("firma"):
            return None
        return let, segni, righe, rie


def impronta_lettura(let):
    """Quello che si disegna: due letture uguali non si ridisegnano."""
    return tuple(sorted((b["nome"], b["copie"], round(b["y"] / 4)) for b in let["mazzo"])), tuple(sorted(b["nome"] for b in let["fuori"]))


def togli_barra(img, let, nome, passo=None):
    """Una carta tolta per finta, sul campione: la colonna sotto la barra sale, come fa Arena."""
    r = next(b for b in let["mazzo"] if b["nome"] == nome)
    s = let["scala"]
    p = int(round(passo or let["passo"]))
    a = np.array(img.convert("RGB"))
    x0, x1 = int(r["cx"] - 16 * s), int(r["cx"] + 186 * s)
    y0 = int(round(r["y"] - 7 * s))
    a[y0:a.shape[0] - p, x0:x1] = a[y0 + p:, x0:x1].copy()
    return Image.fromarray(a)


def prova():
    from ocr import Ocr
    import confronto
    img = Image.open(R.CAMPIONE).convert("RGB")
    pool = confronto.pool_campione()       # il pool del campione, non quello dell'ultimo draft del Player.log (7 nov 2026: rossa ad Arena ripartita)
    with Ocr() as o:
        let = R.leggi_schermo(img, o, R.Nomi(pool))
    casi = []
    I = Impronte()
    casi.append(("impara dalla lettura OCR", I.impara(img, let) and I.pronte()))
    casi.append(("la barra del contatore si trova", bool(let.get("contatore"))))
    t = time.perf_counter(); r0 = I.leggi(img); ms = 1000 * (time.perf_counter() - t)
    t = time.perf_counter(); I.leggi(img); ms2 = 1000 * (time.perf_counter() - t)
    print(f"  prima lettura {ms:.0f} ms, seconda (posti gia' visti) {ms2:.0f} ms; OCR {1000 * let['secondi']:.0f} ms")
    nomi_o = {b["nome"]: b for b in let["mazzo"]}
    nomi_r = {b["nome"]: b for b in r0["mazzo"]}
    mancanti = sorted(n for n, b in nomi_o.items() if b.get("voto", 0) >= 0.8 and n not in nomi_r)
    print(f"  barre OCR {len(nomi_o)}, rapide {len(nomi_r)}, mancanti {mancanti}, in piu' {sorted(set(nomi_r) - set(nomi_o))}")
    d = sorted(b["dist"] for b in r0["mazzo"])
    print(f"  distanze sullo stesso schermo: {d[0]:.1f}-{d[-1]:.1f}")
    # quanto dista una barra dalle altre: il margine delle soglie
    ge = I.geo
    altre = []
    nomi = list(I.mazzo)
    for i, a in enumerate(nomi):
        for b in nomi[i + 1:]:
            altre.append(float(np.abs(I.mazzo[a][0]["a"] - I.mazzo[b][0]["a"]).mean()))
    print(f"  fra carte diverse: minimo {min(altre):.1f}, mediana {np.median(altre):.1f}")
    casi.append(("stessi nomi dell'OCR", not mancanti and not (set(nomi_r) - set(nomi_o))))
    casi.append(("stesse copie dell'OCR", all(nomi_o[n]["copie"] == b["copie"] for n, b in nomi_r.items())))
    casi.append(("stessi posti dell'OCR, entro 3 pixel", all(abs(nomi_o[n]["y"] - b["y"]) <= 3 and abs(nomi_o[n]["x"] - b["x"]) <= 3 for n, b in nomi_r.items())))
    casi.append(("le carte in alto", {b["nome"] for b in r0["fuori"]} == {b["nome"] for b in let["fuori"]}))
    casi.append(("sotto i 200 ms la prima volta, sotto i 50 dopo", ms < 200 and ms2 < 50))
    # una carta tolta: «Gallia, Tragic Host» sta in mezzo a una colonna, quelle sotto salgono di un posto
    VOID = next(n for n in nomi_r if n.startswith("Void Extrapolator"))      # col pool del log era il nome intero della carta a due facce
    finta = togli_barra(img, let, "Gallia, Tragic Host")
    r1 = I.leggi(finta)
    n1 = {b["nome"]: b for b in r1["mazzo"]}
    casi.append(("la carta tolta sparisce", "Gallia, Tragic Host" not in n1))
    casi.append(("le altre restano", len(n1) >= len(nomi_r) - 1))
    casi.append(("quella sotto sale di un posto", abs(n1[VOID]["y"] - (nomi_r[VOID]["y"] - let["passo"])) <= 3))
    # mezzo pixel di differenza: le barre stanno ogni 32,5 pixel, quindi una barra che sale di un posto si ridisegna a meta' fra due righe
    for nome_v, dx, dy in (("in alto", 0, 0.5), ("di lato", 0.5, 0), ("di un terzo", 0, 0.33)):
        sf = finta.transform(finta.size, Image.AFFINE, (1, 0, dx, 0, 1, dy), Image.BILINEAR)
        I.cache.clear()
        r2 = I.leggi(sf)
        n2 = len(r2["mazzo"]) if r2 else 0
        giuste = sum(1 for x in (r2["mazzo"] if r2 else []) if x["nome"] in n1 and abs(x["y"] - n1[x["nome"]]["y"]) <= 3)
        print(f"  sfalsata {nome_v}: {n2} su {len(n1)}, giuste {giuste}")
        casi.append((f"regge mezzo pixel {nome_v}", n2 >= len(n1) - 2 and giuste == n2))
    # le negative
    nero = Image.new("RGB", img.size, (12, 12, 16))
    casi.append(("negativa: un'altra schermata non da' niente", I.leggi(nero) is None))
    casi.append(("negativa: un'altra misura non da' niente", I.leggi(img.resize((1600, 900))) is None))
    a = np.array(img); b = nomi_o["Icy Reception"]
    a[int(b["y"]) - 2:int(b["y"]) + 16, int(b["cx"]):int(b["cx"]) + 150] = 40
    r3 = I.leggi(Image.fromarray(a))
    casi.append(("negativa: una barra coperta non si inventa", "Icy Reception" not in {x["nome"] for x in r3["mazzo"]}))
    Sc = Impronte(); Sc.impara(img, let)
    nn = list(Sc.mazzo); Sc.mazzo[nn[0]], Sc.mazzo[nn[1]] = Sc.mazzo[nn[1]], Sc.mazzo[nn[0]]
    r4 = Sc.leggi(img)
    casi.append(("negativa: due immagini scambiate si vedono", {x["nome"]: round(x["y"]) for x in r4["mazzo"]}.get(nn[0]) != round(nomi_o[nn[0]]["y"])))
    # il seguito: il contatore comanda. Il mouse sopra una carta non cambia niente, una carta tolta si', anche se il primo fotogramma e' a meta'
    conta = lambda v: np.full((19, 60), v, dtype=np.uint8)
    giudica = lambda l: ([], [], dict(nel_mazzo=sum(b["copie"] for b in l["mazzo"])))
    n_ = sum(b["copie"] for b in r0["mazzo"])
    base = dict(n=n_, firma=impronta_lettura(r0))
    Se = Impronte(); Se.impara(img, let)
    Sg = Seguito(Se)
    casi.append(("seguito: il primo sguardo non fa niente", Sg.passo(base, conta(50), 0.0, lambda: finta, giudica) is None))
    casi.append(("seguito: schermo cambiato, contatore fermo: niente (il mouse sopra una carta)", Sg.passo(base, conta(50), 0.05, lambda: finta, giudica) is None))
    meta = np.array(finta); meta[690:1000, 300:500] = 15          # a meta' scivolata la colonna non si legge
    meta[690:1000, 510:1130] = 15
    e1 = Sg.passo(base, conta(120), 0.10, lambda: Image.fromarray(meta), giudica)
    casi.append(("seguito: fotogramma a meta' scartato", e1 is None))
    e2 = Sg.passo(base, conta(120), 0.15, lambda: finta, giudica)
    casi.append(("seguito: la carta tolta arriva", e2 is not None and "Gallia, Tragic Host" not in {b["nome"] for b in e2[0]["mazzo"]}))
    casi.append(("seguito: passata la finestra si ferma", Sg.passo(base, conta(120), 1.2, lambda: finta, giudica) is None))
    for nome, ok in casi:
        print(("  ok   " if ok else "  ROSSO ") + nome)
    print(f"{sum(1 for _, ok in casi if ok)}/{len(casi)}")
    return 0 if all(ok for _, ok in casi) else 1


if __name__ == "__main__":
    if "--prova" in sys.argv:
        sys.exit(prova())
