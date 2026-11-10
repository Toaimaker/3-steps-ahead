"""PROTOTIPO: il foglio di Card view disegnato dalla scheda video (Autore, 9 nov 2026: «e se spostassimo sulla scheda video?», poi «Sì, prototipo»).

Tk disegna col processore: a ogni movimento ricompone pixel per pixel le immagini trasparenti che la carta tocca (10-11 ms a movimento su UW Bouncer). Qui il foglio
e' una finestra pyglet (OpenGL, la RTX 3080): ogni carta e' una texture caricata una volta (immagine, angoli arrotondati, ombra e il numero delle copie gia' cotti,
a 2x con le mipmap: nitida a ogni zoom), le frecce e i pallini sono forme con l'antialias della scheda (MSAA 8x). Spostare, zoomare e pannare cambia solo numeri.

Cosa fa il prototipo: apre una disposizione salvata da Card view (`Log_Arena/tavoli_mazzi.json`, di default quella con piu' carte e connessioni) e la sua rete
(`Log_Arena/sinergie_mazzi.json`); trascini le carte (Maiuscolo: la pila), le impili lasciandole sopra un'altra pila, rotella = zoom intorno al puntatore, tasto
centrale = pan senza bordi; le frecce seguono la carta. In alto a sinistra il tempo di ogni fotogramma. NON salva niente: la disposizione vera resta com'e'.
Gira dentro un programma Tk (una finestrella accanto), pompata dal ciclo di Tk ogni 2 ms: e' la prova che i due motori convivono, come dovranno fare nell'app.
Esc chiude e stampa i tempi (anche in `Log_Arena/foglio_gpu_tempi.txt`). `--prova`: 120 movimenti simulati, i tempi e che carta e frecce si siano spostate; `--senza-tk` gira da solo; `--chiave K` un altro mazzo."""
import os, sys
_casa = os.path.dirname(os.path.abspath(__file__))      # si sale fino a percorsi.py, che mette nel sys.path tutte le cartelle del Companion
while not os.path.isfile(os.path.join(_casa, "percorsi.py")):
    _casa = os.path.dirname(_casa)
if _casa not in sys.path:
    sys.path.insert(0, _casa)
import percorsi  # noqa: E402
import json
import math
import statistics
import time

import capsule as CAP

W = 146                                     # la carta nel mondo (come Card view a zoom 1)
H = round(W * CAP.ALTA_CARTA / CAP.LARGA_CARTA)
OFF = round(H * 0.125)                      # lo sfalsamento della pila: nome e costo della carta sotto si leggono
K = 2                                       # le texture a 2x: nitide fino allo zoom 200%
OMBRA = 7                                   # l'ombra intorno alla carta (mondo)
SPORGE = 14                                 # il numero delle copie sporge a sinistra (mondo)
FASCIA_Y = -(H + 2 * OFF + 110)             # la sideboard sopra il mazzo (nel prototipo, alla stessa scala)
ORO = (214, 172, 46)
FONT = os.path.join(percorsi.ROOT, "Companion", "Grafica", "Poppins-Medium.ttf")


def carica_disposizione(chiave=None):
    """(chiave, disposizione, connessioni) dai file di Card view; senza chiave quella con piu' carte + connessioni."""
    tav = json.load(open(os.path.join(percorsi.ROOT, "Log_Arena", "tavoli_mazzi.json"), encoding="utf-8"))
    try:
        rete = json.load(open(os.path.join(percorsi.ROOT, "Log_Arena", "sinergie_mazzi.json"), encoding="utf-8"))
    except (OSError, ValueError):
        rete = {}
    def peso(k):
        t = tav[k]
        return sum(len(p["carte"]) for p in t.get("pile", [])) + len(rete.get(k, {}).get("figli", []))
    chiave = chiave or max((k for k in tav if tav[k].get("v") == 2), key=peso)
    figli = [(x[0], x[1]) for x in rete.get(chiave, {}).get("figli", [])]
    return chiave, tav[chiave], figli


def immagine_carta(nome, q):
    """La texture della carta, a K volte: immagine con gli angoli arrotondati, l'ombra morbida e la pillola «Nx» che sporge a sinistra. -> (PIL RGBA, sinistra, sopra)
    in pixel di texture: dove sta l'angolo della carta dentro l'immagine."""
    from PIL import Image, ImageDraw, ImageFilter, ImageFont
    w, h = W * K, H * K
    src = next((f for f in (CAP.file_immagine(nome), CAP.file_mini(nome)) if os.path.exists(f)), None)
    if src:
        im = Image.open(src).convert("RGBA").resize((w, h), Image.LANCZOS)
    else:
        im = Image.new("RGBA", (w, h), (40, 40, 46, 255))
        ImageDraw.Draw(im).text((20, 20), nome, fill=(230, 230, 230, 255))
    m = Image.new("L", (w * 3, h * 3), 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, w * 3 - 1, h * 3 - 1), radius=round(w * 3 * 0.047), fill=255)
    im.putalpha(m.resize((w, h), Image.LANCZOS))
    p, sx = OMBRA * K, SPORGE * K
    tela = Image.new("RGBA", (w + 2 * p + sx, h + 2 * p + p // 2), (0, 0, 0, 0))
    ombra = Image.new("L", tela.size, 0)
    ImageDraw.Draw(ombra).rounded_rectangle((sx + p, p + p // 3, sx + p + w - 1, p + h - 1 + p // 3), radius=round(w * 0.047), fill=170)
    nera = Image.new("RGBA", tela.size, (0, 0, 0, 255))
    nera.putalpha(ombra.filter(ImageFilter.GaussianBlur(p / 2.2)))
    tela = Image.alpha_composite(tela, nera)
    tela.alpha_composite(im, (sx + p, p))
    # la pillola del numero, sul bordo sinistro all'altezza del nome (come Card view)
    d = ImageDraw.Draw(tela)
    bl, bh = 26 * K, 17 * K
    x0, cy = sx + p - SPORGE * K, p + h * 0.072
    d.rounded_rectangle((x0, cy - bh / 2, x0 + bl, cy + bh / 2), radius=bh / 2, fill=(16, 16, 20, 235), outline=(36, 186, 255, 255), width=K)
    try:
        f = ImageFont.truetype(FONT, 8 * K + 2)
    except OSError:
        f = ImageFont.load_default()
    d.text((x0 + bl / 2, cy), f"{q}x", fill=(255, 255, 255, 255), font=f, anchor="mm")
    return tela, sx + p, p


class Foglio:
    """Il foglio sulla scheda video. Il mondo ha la y in giu' come Card view; pyglet ha la y in su: le carte stanno a y = -y_mondo."""

    def __init__(self, chiave=None, visibile=True):
        import pyglet
        from pyglet import gl
        self.pyglet, self.gl = pyglet, gl
        self.chiave, tav, self.figli = carica_disposizione(chiave)
        self.pile = []
        for pl in tav["pile"]:
            self.pile.append(dict(zona=pl["zona"], x=float(pl["x"]), y=float(pl["y"]) + (FASCIA_Y if pl["zona"] != "main" else 0), carte=[(n, q) for n, q in pl["carte"]]))
        try:
            cfg = gl.Config(sample_buffers=1, samples=8, double_buffer=True)
            self.w = pyglet.window.Window(1500, 950, caption=f"Card view GPU (prototype) · {self.chiave}", resizable=True, vsync=False, config=cfg, visible=visibile)
        except Exception:           # niente MSAA: la finestra comunque
            self.w = pyglet.window.Window(1500, 950, caption=f"Card view GPU (prototype) · {self.chiave}", resizable=True, vsync=False, visible=visibile)
        self.zoom, self.ox, self.oy = 0.6, -40.0, FASCIA_Y - 60
        self.batch = pyglet.graphics.Batch()
        self.sopra = pyglet.graphics.Batch()           # frecce e pallini, sopra le carte
        self.hud = pyglet.graphics.Batch()
        self.tex, self.spr, self.ordine = {}, {}, 0
        t0 = time.perf_counter()
        for pl in self.pile:
            for n, q in pl["carte"]:
                self.carta_sprite(n, q, pl["zona"])
        self.t_carico = time.perf_counter() - t0
        self.frecce, self.pallini, self.evid = [], {}, None
        self.info = pyglet.text.Label("", x=12, y=12, font_size=11, color=(220, 220, 228, 255), batch=self.hud)
        self.aiuto = pyglet.text.Label("drag a card · Shift: the pile · wheel: zoom · middle button: pan · Esc: close and print the times · prototype: nothing is saved",
                                       x=12, y=34, font_size=9, color=(150, 150, 160, 255), batch=self.hud)
        self.drag, self.pan, self.sporco, self.fermo = None, False, True, False
        self.tempi, self.mossa = [], 0
        self.disponi_sprite()
        w = self.w
        w.on_draw = self.disegna
        w.on_mouse_press = self.premi
        w.on_mouse_drag = self.trascina
        w.on_mouse_release = self.rilascia
        w.on_mouse_scroll = self.rotella
        w.on_resize = self.misura
        w.on_key_press = self.tasto
        w.on_close = self.chiudi

    # ------------------------------------------------ le carte
    def carta_sprite(self, nome, q, zona):
        pyglet = self.pyglet
        k = (nome, zona)
        im, sx, sy = immagine_carta(nome, q)
        data = pyglet.image.ImageData(im.width, im.height, "RGBA", im.tobytes(), pitch=-im.width * 4)
        tex = data.get_texture()            # le mipmap le genera la scheda: con get_mipmapped_texture i livelli restavano vuoti e sotto il 100% le carte erano nere
        gl = self.gl
        gl.glBindTexture(tex.target, tex.id)
        gl.glGenerateMipmap(tex.target)
        gl.glTexParameteri(tex.target, gl.GL_TEXTURE_MIN_FILTER, gl.GL_LINEAR_MIPMAP_LINEAR)
        gl.glTexParameteri(tex.target, gl.GL_TEXTURE_MAG_FILTER, gl.GL_LINEAR)
        self.ordine += 1
        s = pyglet.sprite.Sprite(tex, batch=self.batch, group=pyglet.graphics.Group(order=self.ordine))
        s.scale = 1 / K
        self.spr[k] = dict(s=s, sx=sx / K, sy=sy / K, h=im.height / K)

    def posizioni(self, pl):
        return [pl["y"] + i * OFF for i in range(len(pl["carte"]))]

    def metti(self, k, x, y):
        """Lo sprite della carta k con l'angolo in alto a sinistra in (x, y) del mondo."""
        d = self.spr[k]
        d["s"].update(x=x - d["sx"], y=-(y - d["sy"]) - d["h"])
        d["x"], d["y"] = x, y

    def disponi_sprite(self):
        """Ogni sprite al suo posto dal modello, nell'ordine di disegno: le pile in ordine, dentro la pila dall'alto."""
        o = 0
        for pl in self.pile:
            for (n, _q), y in zip(pl["carte"], self.posizioni(pl)):
                k = (n, pl["zona"])
                o += 1
                self.spr[k]["s"].group = self.pyglet.graphics.Group(order=o)
                self.metti(k, pl["x"], y)
        self.rifai_frecce()
        self.sporco = True

    # ------------------------------------------------ frecce e pallini: forme con l'antialias della scheda
    def nodo(self, k):
        """(x, y, raggio) del pallino della carta nel mondo: alla base se e' l'ultima della pila, se no sul bordo destro della barra del nome."""
        for pl in self.pile:
            for i, (n, _q) in enumerate(pl["carte"]):
                if (n, pl["zona"]) == k:
                    d = self.spr[k]
                    if i == len(pl["carte"]) - 1:
                        return d["x"] + W / 2, d["y"] + H + 9, 8
                    return d["x"] + W, d["y"] + OFF * 0.5, 5
        return None

    def chiave_nome(self, n):
        return next(((nn, z) for (nn, z) in self.spr if nn == n and z == "main"), None) or next(((nn, z) for (nn, z) in self.spr if nn == n), None)

    def geometria(self, ka, kb):
        """La freccia da pallino a pallino: (inizio, fine della linea, tre punti della punta) in coordinate pyglet (y in su), o None se i pallini si toccano."""
        na, nb = self.nodo(ka), self.nodo(kb)
        if not na or not nb:
            return None
        dx, dy = nb[0] - na[0], nb[1] - na[1]
        lung = math.hypot(dx, dy)
        if lung < na[2] + nb[2] + 10:
            return None
        ux, uy = dx / lung, dy / lung
        A = (na[0] + ux * (na[2] + 2), na[1] + uy * (na[2] + 2))
        B = (nb[0] - ux * (nb[2] + 2), nb[1] - uy * (nb[2] + 2))
        base = (B[0] - ux * 10, B[1] - uy * 10)
        px, py = -uy, ux
        return ((A[0], -A[1]), (base[0], -base[1]),
                ((B[0], -B[1]), (base[0] - px * 5, -(base[1] - py * 5)), (base[0] + px * 5, -(base[1] + py * 5))))

    def rifai_frecce(self):
        """Tutte le frecce e i pallini da capo (dopo un rilascio). Mentre trascini si aggiornano solo quelli della carta presa (aggiorna_frecce)."""
        from pyglet import shapes
        for a in self.frecce:
            a["linea"].delete(); a["punta"].delete()
        for cc in self.pallini.values():
            for c in cc:
                c.delete()
        self.frecce, self.pallini = [], {}
        legate = set()
        for a, b in self.figli:
            ka, kb = self.chiave_nome(a), self.chiave_nome(b)
            if not ka or not kb:
                continue
            linea = shapes.Line(0, 0, 1, 1, thickness=2.2, color=ORO, batch=self.sopra)
            punta = shapes.Triangle(0, 0, 1, 0, 0, 1, color=ORO, batch=self.sopra)
            self.frecce.append(dict(ka=ka, kb=kb, linea=linea, punta=punta))
            legate.update((ka, kb))
        for pl in self.pile:
            for i, (n, _q) in enumerate(pl["carte"]):
                k = (n, pl["zona"])
                if i == len(pl["carte"]) - 1 or k in legate:
                    self.pallini[k] = [shapes.Circle(0, 0, 8, color=(16, 16, 20), batch=self.sopra), shapes.Circle(0, 0, 6.6, color=ORO, batch=self.sopra),
                                       shapes.Circle(0, 0, 2.4, color=(255, 244, 205), batch=self.sopra)]
        self.aggiorna_frecce(None)

    def aggiorna_frecce(self, chiavi):
        """La geometria delle frecce e dei pallini delle carte date (None: tutte), senza ricrearli: solo numeri."""
        for a in self.frecce:
            if chiavi is not None and a["ka"] not in chiavi and a["kb"] not in chiavi:
                continue
            g = self.geometria(a["ka"], a["kb"])
            a["linea"].visible = a["punta"].visible = g is not None
            if g:
                ln = a["linea"]
                ln.x, ln.y, ln.x2, ln.y2 = g[0][0], g[0][1], g[1][0], g[1][1]
                (a["punta"].x, a["punta"].y), (a["punta"].x2, a["punta"].y2), (a["punta"].x3, a["punta"].y3) = g[2]
        for k, cc in self.pallini.items():
            if chiavi is not None and k not in chiavi:
                continue
            nd = self.nodo(k)
            if nd:
                x, y, r = nd
                for c, rr in zip(cc, (r, r - 1.4, r * 0.3)):
                    c.x, c.y, c.radius = x, -y, rr

    # ------------------------------------------------ il disegno
    def vista(self):
        from pyglet.math import Mat4, Vec3
        z = self.zoom
        return Mat4.from_translation(Vec3(-z * self.ox, self.w.height + z * self.oy, 0)) @ Mat4.from_scale(Vec3(z, z, 1))

    def disegna(self):
        from pyglet.math import Mat4
        self.gl.glClearColor(24 / 255, 24 / 255, 28 / 255, 1)
        self.w.clear()
        self.w.view = self.vista()
        self.batch.draw()
        self.sopra.draw()
        self.w.view = Mat4()
        self.hud.draw()

    def misura(self, larg, alt):
        self.sporco = True

    def mondo(self, x, y):
        return x / self.zoom + self.ox, (self.w.height - y) / self.zoom + self.oy

    # ------------------------------------------------ il mouse
    def carta_a(self, wx, wy):
        """La carta sotto il punto del mondo, dalla geometria delle pile; vince quella sopra."""
        for pl in reversed(self.pile):
            ys = self.posizioni(pl)
            for i in range(len(pl["carte"]) - 1, -1, -1):
                if pl["x"] - SPORGE <= wx <= pl["x"] + W and ys[i] <= wy <= ys[i] + H:
                    return pl, i
        return None, None

    def ingombro(self, pl):
        return pl["x"], pl["y"], pl["x"] + W, self.posizioni(pl)[-1] + H

    def premi(self, x, y, bottone, mod):
        mouse = self.pyglet.window.mouse
        if bottone == mouse.MIDDLE:
            self.pan = True
            return
        if bottone != mouse.LEFT:
            return
        wx, wy = self.mondo(x, y)
        pl, i = self.carta_a(wx, wy)
        if pl is None:
            return
        tutte = bool(mod & self.pyglet.window.key.MOD_SHIFT)
        prese = pl["carte"][:] if tutte else [pl["carte"][i]]
        chiavi = [(n, pl["zona"]) for n, _q in prese]
        for k in chiavi:            # sopra a tutto mentre la porti
            self.ordine += 1
            self.spr[k]["s"].group = self.pyglet.graphics.Group(order=10000 + self.ordine)
        self.drag = dict(da=pl, prese=prese, chiavi=chiavi, dx=0.0, dy=0.0, t0=time.perf_counter())

    def trascina(self, x, y, dx, dy, bottoni, mod):
        t0 = time.perf_counter()
        if self.pan or (bottoni & self.pyglet.window.mouse.MIDDLE):
            self.ox -= dx / self.zoom
            self.oy += dy / self.zoom
            self.sporco = True
            return
        d = self.drag
        if d is None:
            return
        mx, my = dx / self.zoom, -dy / self.zoom
        d["dx"] += mx; d["dy"] += my
        for k in d["chiavi"]:
            s = self.spr[k]
            self.metti(k, s["x"] + mx, s["y"] + my)
        self.muovi_frecce()
        wx, wy = self.mondo(x, y)
        self.accendi(wx, wy)
        self.sporco = True
        self.mossa = time.perf_counter() - t0

    def muovi_frecce(self):
        """Solo le frecce e i pallini della carta presa: si cambiano i numeri, non si ricrea niente."""
        self.aggiorna_frecce(set(self.drag["chiavi"]) if self.drag else None)

    def bersaglio(self, wx, wy):
        d = self.drag
        for pl in reversed(self.pile):
            if d and pl is d["da"] and len(d["prese"]) == len(pl["carte"]):
                continue
            x0, y0, x1, y1 = self.ingombro(pl)
            if x0 - 4 <= wx <= x1 + 4 and y0 - 4 <= wy <= y1 + 4:
                return pl
        return None

    def accendi(self, wx, wy):
        from pyglet import shapes
        b = self.bersaglio(wx, wy)
        if self.evid is not None:
            self.evid.delete(); self.evid = None
        if b is not None:
            x0, y0, x1, y1 = self.ingombro(b)
            self.evid = shapes.Box(x0 - 4, -(y1 + 4), x1 - x0 + 8, y1 - y0 + 8, thickness=2, color=(36, 186, 255), batch=self.sopra)

    def rilascia(self, x, y, bottone, mod):
        if bottone == self.pyglet.window.mouse.MIDDLE:
            self.pan = False
            return
        d, self.drag = self.drag, None
        if d is None:
            return
        if self.evid is not None:
            self.evid.delete(); self.evid = None
        wx, wy = self.mondo(x, y)
        b = self.bersaglio(wx, wy)
        da = d["da"]
        primo = d["chiavi"][0]
        for c in d["prese"]:
            da["carte"].remove(c)
        if b is not None:
            b["carte"].extend(d["prese"])
        else:           # libera, dove l'hai lasciata
            self.pile.append(dict(zona=da["zona"], x=round(self.spr[primo]["x"]), y=round(self.spr[primo]["y"]), carte=list(d["prese"])))
        if not da["carte"]:
            self.pile.remove(da)
        self.disponi_sprite()

    def rotella(self, x, y, sx, sy):
        wx, wy = self.mondo(x, y)
        self.zoom = max(0.3, min(2.0, self.zoom * (1.12 if sy > 0 else 1 / 1.12)))
        self.ox, self.oy = wx - x / self.zoom, wy - (self.w.height - y) / self.zoom       # il punto sotto il puntatore resta li'
        self.sporco = True

    def tasto(self, simbolo, mod):
        if simbolo == self.pyglet.window.key.ESCAPE:
            self.chiudi()
            return True

    def chiudi(self):
        self.fermo = True
        return True

    # ------------------------------------------------ il giro: un fotogramma quando serve
    def giro(self):
        """Eventi, e se qualcosa e' cambiato un fotogramma (disegno + flip): il tempo di ogni fotogramma va in tempi."""
        w = self.w
        w.switch_to()
        w.dispatch_events()
        if self.fermo:
            return False
        if self.sporco:
            t0 = time.perf_counter()
            w.dispatch_event("on_draw")
            w.flip()
            ms = (time.perf_counter() - t0 + self.mossa) * 1000
            self.mossa = 0
            if self.drag is not None or self.pan:
                self.tempi.append(ms)
            self.info.text = f"frame {ms:.1f} ms · {len(self.spr)} cards · {len(self.figli)} links · zoom {round(self.zoom * 100)}% · textures {self.t_carico:.2f} s"
            self.sporco = False
        return True

    def riassunto(self):
        if not self.tempi:
            return "nessun fotogramma durante un trascinamento"
        t = sorted(self.tempi)
        return (f"{len(t)} fotogrammi trascinando: mediana {statistics.median(t):.2f} ms, 95% {t[int(len(t) * 0.95) - 1]:.2f} ms, massimo {t[-1]:.2f} ms "
                f"(texture caricate in {self.t_carico:.2f} s)")


def con_tk(f):
    """Il foglio dentro un programma Tk: una finestrella Tk accanto e il giro di pyglet chiamato dal ciclo di Tk ogni 2 ms, come dovra' essere nell'app."""
    import tkinter as tk
    root = tk.Tk()
    root.title("Companion (Tk)")
    root.geometry("360x90+40+40")
    tk.Label(root, text="Tk is running next to the GPU sheet.\nClose the sheet with Esc.", font=("Segoe UI", 10)).pack(expand=True)

    def pompa():
        if f.giro():
            root.after(2, pompa)
        else:
            root.destroy()
    root.after(2, pompa)
    root.mainloop()


def senza_tk(f):
    while f.giro():
        time.sleep(0.001)


def prova():
    """120 movimenti simulati di una carta col suo giro vero (disegno e flip): la carta e le sue frecce si spostano, e i tempi."""
    f = Foglio(visibile=True)
    f.giro()
    k = next(k for k in f.spr if any(k[0] in (a, b) for a, b in f.figli))      # una carta con le frecce
    pl = next(p for p in f.pile if any((n, p["zona"]) == k for n, _q in p["carte"]))
    sx, sy = f.spr[k]["x"], f.spr[k]["y"]
    px, py = (sx + W / 2 - f.ox) * f.zoom, f.w.height - (sy + 20 - f.oy) * f.zoom
    mie = [a for a in f.frecce if k in (a["ka"], a["kb"])]
    prima_frecce = [(a["linea"].x, a["linea"].y, a["linea"].x2, a["linea"].y2) for a in mie]
    f.premi(px, py, f.pyglet.window.mouse.LEFT, 0)
    for _ in range(120):
        f.trascina(px, py, 3, -1, f.pyglet.window.mouse.LEFT, 0)
        f.giro()
    mossa = (round(f.spr[k]["x"] - sx), round(f.spr[k]["y"] - sy))
    dopo_frecce = [(a["linea"].x, a["linea"].y, a["linea"].x2, a["linea"].y2) for a in mie]
    f.rilascia(px + 360, py - 120, f.pyglet.window.mouse.LEFT, 0)
    f.giro()
    casi = [("la carta segue il mouse", mossa == (round(360 / f.zoom), round(120 / f.zoom))),
            ("le frecce della carta la seguono", bool(mie) and all(p_ != d_ for p_, d_ in zip(prima_frecce, dopo_frecce))),
            ("lasciata, la carta resta nel modello", any((n, p["zona"]) == k for p in f.pile for n, _q in p["carte"])),
            ("la pila di partenza non perde le altre carte", sum(len(p["carte"]) for p in f.pile) == len(f.spr))]
    # convivenza con Tk: il giro chiamato dal ciclo di Tk
    import tkinter as tk
    root = tk.Tk(); root.withdraw()
    giri = []

    def pompa():
        f.sporco = True
        if f.giro():
            giri.append(1)
        if len(giri) < 30:
            root.after(2, pompa)
        else:
            root.quit()
    root.after(2, pompa)
    root.mainloop()
    root.destroy()
    casi.append(("il foglio gira dentro il ciclo di Tk", len(giri) == 30))
    foto = os.environ.get("FOGLIO_FOTO")
    if foto:            # la foto del foglio, per guardarlo
        f.sporco = True
        f.w.switch_to(); f.w.dispatch_event("on_draw")
        f.pyglet.image.get_buffer_manager().get_color_buffer().save(foto)
        f.w.flip()
    print(f.riassunto())
    ok = sum(1 for _n, v in casi if v)
    for n, v in casi:
        print(("ok    " if v else "ROSSO ") + n)
    print(f"{ok}/{len(casi)}")
    f.w.close()
    return ok == len(casi) and pl is not None


if __name__ == "__main__":
    if "--prova" in sys.argv:
        sys.exit(0 if prova() else 1)
    chiave = sys.argv[sys.argv.index("--chiave") + 1] if "--chiave" in sys.argv else None
    foglio = Foglio(chiave)
    (senza_tk if "--senza-tk" in sys.argv else con_tk)(foglio)
    print(foglio.riassunto())
    with open(os.path.join(percorsi.ROOT, "Log_Arena", "foglio_gpu_tempi.txt"), "a", encoding="utf-8") as g:      # anche lanciato senza console
        g.write(time.strftime("%Y-%m-%d %H:%M  ") + foglio.chiave + "  " + foglio.riassunto() + chr(10))
    foglio.w.close()
