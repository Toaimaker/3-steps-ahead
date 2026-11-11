"""Una carta disegnata sulla tela della griglia, non in una tela sua (11 nov 2026, sessione Magic 13, `Note/Motore_Grafico_App.md`; Autore: «aggiorna il
motore grafico dell'app, valuta se conviene passare tutto a scheda video perché è scattosa e refresha male»).

Fino a quel giorno ogni carta di Collection era una tela di Tk messa nella tela grande con create_window: su Windows ogni widget e' una finestra, e a ogni scatto di
rotella Windows spostava e ridipingeva una finestra per carta, una alla volta. Misurato (Strumenti/metro_grafico.py, metro_griglie.py): 187 quadri per 24 scatti,
il ciclo fermo fino a 192 ms; con le carte disegnate sulla tela sola un quadro pulito per scatto e 52 ms.

CartaTela fa la parte della tela di una carta che il resto del codice usa (capsule.Liste.carta_piena, l'immagine che arriva dopo in raccogli, la carta grande in
hover, il trascinamento verso il builder, le prove): create_text, create_rectangle, create_line, create_image, delete, bbox, find_all, find_withtag, type,
itemcget, itemconfigure, tag_raise, bind, winfo_* e after. Fa anche le schede dei mazzi di Your decks e Meta (stessa storia: una tela di Tk per scheda):
sposta (la griglia la mette al suo posto), grid_info (riga e colonna, come la griglia di Tk), il cursore sotto il puntatore, gli eventi coi x e y della
scheda. Distrutta, non disegna piu' niente (una copertina cotta dopo arriva su una scheda che non c'e' piu'). Gli elementi stanno sulla tela grande, spostati di (x, y), con un tag per carta; un tag interno («ban», «sotto») diventa «<carta>:ban».
Smistatore lega gli eventi alla tela grande e li passa alla carta sotto il puntatore, con <Enter> e <Leave> quando cambia carta; i tasti premuti restano della
carta dove la pressione e' cominciata, come la presa implicita di Tk.

`--prova`: elementi e tag, posizione, l'immagine che arriva dopo, eventi smistati (entra, esci, presa, doppio clic), distruggi, con le negative."""
import os, sys
_casa = os.path.dirname(os.path.abspath(__file__))      # si sale fino a percorsi.py, che mette nel sys.path tutte le cartelle del Companion
while not os.path.isfile(os.path.join(_casa, "percorsi.py")):
    _casa = os.path.dirname(_casa)
if _casa not in sys.path:
    sys.path.insert(0, _casa)
import percorsi  # noqa: E402,F401
import itertools  # noqa: E402

_NUMERO = itertools.count(1)
# i nomi dello stesso evento: per Tk <Button-1> e <1> sono <ButtonPress-1>. Lo Smistatore manda <ButtonPress-1>: senza l'alias una scheda legata a <Button-1>
# non riceveva il clic vero (11 nov 2026: le schede di Meta e Your decks, trovato dalla prova delle tabelle)
_ALIAS = {"<Button-1>": "<ButtonPress-1>", "<1>": "<ButtonPress-1>", "<B1-ButtonRelease>": "<ButtonRelease-1>"}


def _seq(s):
    return _ALIAS.get(s, s)


class Evento:
    def __init__(self, **kw):
        self.__dict__.update(kw)


class CartaTela:
    """Una carta sulla tela grande cv, con l'angolo in alto a sinistra in (x, y) di coordinate della tela e la misura (larga, alta)."""

    def __init__(self, cv, x, y, larga, alta, smistatore=None, cursore=""):
        self.cv, self.x, self.y, self.larga, self.alta = cv, x, y, larga, alta
        self.tag = f"ct{next(_NUMERO)}"
        self.legami = {}
        self.cursore, self.morta, self.cella = cursore, False, {}
        self.sm = smistatore
        if smistatore is not None:
            smistatore.carte[self.tag] = self

    # ---- gli elementi, nelle coordinate della carta
    def _tags(self, tags):
        if isinstance(tags, str):
            tags = (tags,)
        return (self.tag, "cartatela") + tuple(f"{self.tag}:{t}" for t in tags or ())

    def create_text(self, x, y, tags=(), **k):
        if self.morta:
            return None
        return self.cv.create_text(self.x + x, self.y + y, tags=self._tags(tags), **k)

    def create_image(self, x, y, tags=(), **k):
        if self.morta:
            return None
        return self.cv.create_image(self.x + x, self.y + y, tags=self._tags(tags), **k)

    def create_rectangle(self, x0, y0, x1, y1, tags=(), **k):
        if self.morta:
            return None
        return self.cv.create_rectangle(self.x + x0, self.y + y0, self.x + x1, self.y + y1, tags=self._tags(tags), **k)

    def create_line(self, *c, tags=(), **k):
        if self.morta:
            return None
        c = c[0] if len(c) == 1 else c
        return self.cv.create_line(*[v + (self.x if i % 2 == 0 else self.y) for i, v in enumerate(c)], tags=self._tags(tags), **k)

    def delete(self, t):
        """«all»: tutti gli elementi della carta (la carta resta viva e si ridisegna); un tag interno o un id: quelli."""
        self.cv.delete(self.tag if t == "all" else f"{self.tag}:{t}" if isinstance(t, str) else t)

    def bbox(self, i):
        b = self.cv.bbox(i)
        return None if b is None else (b[0] - self.x, b[1] - self.y, b[2] - self.x, b[3] - self.y)

    def sposta(self, x, y):
        """La carta al suo posto sulla tela (la griglia la mette li')."""
        if (x, y) != (self.x, self.y):
            self.cv.move(self.tag, x - self.x, y - self.y)
            self.x, self.y = x, y

    def grid_info(self):
        return dict(self.cella)

    def find_all(self):
        return self.cv.find_withtag(self.tag)

    def find_withtag(self, t):
        if isinstance(t, int):
            return (t,) if t in self.find_all() else ()
        return self.cv.find_withtag(f"{self.tag}:{t}")

    def type(self, i):
        return self.cv.type(i)

    def itemcget(self, i, k):
        if isinstance(i, str):
            i = (self.find_withtag(i) or (None,))[0]
        return self.cv.itemcget(i, k)

    def itemconfigure(self, i, **k):
        return self.cv.itemconfigure(f"{self.tag}:{i}" if isinstance(i, str) else i, **k)

    def tag_raise(self, t):
        if self.find_withtag(t):
            self.cv.tag_raise(f"{self.tag}:{t}")

    # ---- quello che una tela sa di se'
    def winfo_exists(self):
        try:
            return bool(self.cv.winfo_exists() and self.cv.find_withtag(self.tag))
        except Exception:
            return False

    def winfo_rootx(self):
        return self.cv.winfo_rootx() + int(self.x - self.cv.canvasx(0))

    def winfo_rooty(self):
        return self.cv.winfo_rooty() + int(self.y - self.cv.canvasy(0))

    def winfo_width(self):
        return self.larga

    def winfo_height(self):
        return self.alta

    def winfo_toplevel(self):
        return self.cv.winfo_toplevel()

    def after(self, ms, f=None, *a):
        return self.cv.after(ms, f, *a)

    def after_cancel(self, i):
        return self.cv.after_cancel(i)

    def contiene(self, cx, cy):
        return self.x <= cx < self.x + self.larga and self.y <= cy < self.y + self.alta

    # ---- gli eventi: li manda lo Smistatore
    def bind(self, seq, f=None, add=None):
        seq = _seq(seq)
        if f is None:
            return self.legami.get(seq)
        if add:
            self.legami.setdefault(seq, []).append(f)
        else:
            self.legami[seq] = [f]
        return seq

    def manda(self, seq, e=None):
        """L'evento coi x e y della carta, come lo darebbe la sua tela."""
        if e is None:
            e = Evento(widget=self, x=0, y=0, x_root=self.winfo_rootx(), y_root=self.winfo_rooty())
        elif getattr(e, "widget", None) is not self:
            try:
                cx, cy = self.cv.canvasx(e.x), self.cv.canvasy(e.y)
            except Exception:
                cx, cy = self.x, self.y
            e = Evento(widget=self, x=cx - self.x, y=cy - self.y, x_root=getattr(e, "x_root", 0), y_root=getattr(e, "y_root", 0),
                       state=getattr(e, "state", 0), delta=getattr(e, "delta", 0))
        for f in list(self.legami.get(_seq(seq), ())):
            f(e)

    def event_generate(self, seq, **kw):
        """Per le prove e i metri: come generare l'evento sulla tela della carta."""
        self.manda(seq, Evento(widget=self, x=kw.get("x", 0), y=kw.get("y", 0), x_root=self.winfo_rootx() + kw.get("x", 0), y_root=self.winfo_rooty() + kw.get("y", 0)))

    def destroy(self):
        self.morta = True
        if self.sm is not None:
            self.sm.carte.pop(self.tag, None)
            if self.sm.sopra is self:
                self.sm.sopra = None
                try:
                    self.cv.configure(cursor="")      # tolta sotto il puntatore: il cursore della carta non resta
                except Exception:
                    pass
            if self.sm.presa is self:
                self.sm.presa = None
        try:
            self.cv.delete(self.tag)
        except Exception:
            pass
        self.manda("<Destroy>")
        self.legami = {}


class Smistatore:
    """Gli eventi della tela grande, alla carta sotto il puntatore. Una pressione resta della sua carta fino al rilascio."""

    def __init__(self, cv):
        self.cv, self.carte, self.sopra, self.presa = cv, {}, None, None
        cv.bind("<Motion>", self.muovi, add="+")
        cv.bind("<Leave>", lambda e: self.cambia(None, e), add="+")
        cv.bind("<ButtonPress-1>", lambda e: self.premi(e), add="+")
        cv.bind("<B1-Motion>", lambda e: self.presa.manda("<B1-Motion>", e) if self.presa else None, add="+")
        cv.bind("<ButtonRelease-1>", self.rilascia, add="+")
        cv.bind("<Double-Button-1>", self.doppio, add="+")

    def doppio(self, e):
        c = self.sotto(e)
        if c is not None:
            c.manda("<Double-Button-1>", e)

    def sotto(self, e):
        cx, cy = self.cv.canvasx(e.x), self.cv.canvasy(e.y)
        for i in reversed(self.cv.find_overlapping(cx, cy, cx, cy)):
            for t in self.cv.gettags(i):
                c = self.carte.get(t)
                if c is not None and c.contiene(cx, cy):
                    return c
        return None

    def cambia(self, c, e):
        if c is self.sopra:
            return
        vecchia, self.sopra = self.sopra, c
        if vecchia is not None:
            vecchia.manda("<Leave>", e)
        try:
            self.cv.configure(cursor=c.cursore if c is not None else "")
        except Exception:
            pass
        if c is not None:
            c.manda("<Enter>", e)

    def muovi(self, e):
        c = self.sotto(e)
        self.cambia(c, e)
        if c is not None and "<Motion>" in c.legami:
            c.manda("<Motion>", e)

    def premi(self, e):
        self.presa = self.sotto(e)
        if self.presa is not None:
            self.presa.manda("<ButtonPress-1>", e)

    def rilascia(self, e):
        c, self.presa = self.presa, None
        if c is not None:
            c.manda("<ButtonRelease-1>", e)
        self.muovi(e)

    def svuota(self):
        for c in list(self.carte.values()):
            c.destroy()


def prova():
    import tkinter as tk
    root = tk.Tk(); root.geometry("600x400+5000+20")
    cv = tk.Canvas(root, width=600, height=400); cv.pack(); root.update()
    sm = Smistatore(cv)
    a = CartaTela(cv, 10, 10, 100, 140, sm); b = CartaTela(cv, 200, 10, 100, 140, sm)
    a.create_rectangle(0, 0, 100, 120, fill="#202024"); ia = a.create_text(50, 130, text="x2", tags="sotto")
    b.create_text(50, 130, text="x0", tags="sotto"); b.create_rectangle(2, 2, 98, 118, outline="red", tags="ban")
    visti = []
    for c, n in ((a, "a"), (b, "b")):
        c.bind("<Enter>", lambda e, n=n: visti.append("entra " + n)); c.bind("<Leave>", lambda e, n=n: visti.append("esci " + n))
        c.bind("<ButtonPress-1>", lambda e, n=n: visti.append("premi " + n), add="+"); c.bind("<ButtonRelease-1>", lambda e, n=n: visti.append("lascia " + n), add="+")
        c.bind("<Double-Button-1>", lambda e, n=n: visti.append("doppio " + n), add="+")
    E = lambda x, y: Evento(x=x, y=y, x_root=x, y_root=y, widget=cv)
    casi = []
    casi.append(("gli elementi sono della carta", len(a.find_all()) == 2 and len(b.find_all()) == 2))
    casi.append(("il testo sotto e' al suo posto sulla tela", cv.coords(ia) == [60.0, 140.0] and a.itemcget(a.find_withtag("sotto")[0], "text") == "x2"))
    casi.append(("il tag interno e' della carta", bool(b.find_withtag("ban")) and not a.find_withtag("ban")))
    casi.append(("la posizione sullo schermo", a.winfo_rootx() == cv.winfo_rootx() + 10 and b.winfo_rooty() == cv.winfo_rooty() + 10))
    im = tk.PhotoImage(width=100, height=120); im.put("#ff0000", to=(0, 0, 100, 120))
    b.create_image(0, 0, image=im, anchor="nw"); b.tag_raise("ban")
    casi.append(("l'immagine arrivata dopo resta sotto il bordo rosso", cv.find_all().index(b.find_withtag("ban")[0]) > cv.find_all().index([i for i in b.find_all() if cv.type(i) == "image"][0])))
    sm.muovi(E(50, 50)); sm.muovi(E(60, 60)); sm.muovi(E(250, 50)); sm.muovi(E(150, 50))
    casi.append(("entra ed esci solo quando cambia carta", visti == ["entra a", "esci a", "entra b", "esci b"]))
    del visti[:]
    sm.premi(E(50, 50)); sm.rilascia(E(250, 50))       # col tasto premuto Tk manda <B1-Motion>, non <Motion>: la carta sotto non cambia fino al rilascio
    casi.append(("la presa resta della carta dove comincia", visti[:2] == ["premi a", "lascia a"]))
    clic = []
    b.bind("<Button-1>", lambda e: clic.append("b"), add=True)        # legata col nome di Tk piu' comune: il clic vero arriva come <ButtonPress-1>
    sm.premi(E(250, 50)); sm.rilascia(E(250, 50))
    casi.append(("<Button-1> riceve la pressione vera dello smistatore", clic == ["b"]))
    del visti[:]
    sm.premi(E(150, 50)); sm.rilascia(E(150, 50))
    casi.append(("negativa: fra le carte non si preme niente", "premi a" not in visti and "premi b" not in visti))
    sm.doppio(E(250, 50))       # Tk non genera i doppi clic finti: si chiama quello che il doppio clic chiama
    casi.append(("il doppio clic va alla carta sotto", "doppio b" in visti))
    via = []
    a.bind("<Destroy>", lambda e: via.append(1), add="+")
    a.destroy()
    casi.append(("distrutta: niente elementi, non esiste, ha avvisato", not cv.find_withtag(a.tag) and not a.winfo_exists() and via == [1] and a.tag not in sm.carte))
    casi.append(("negativa: l'altra carta resta", b.winfo_exists() and len(b.find_all()) == 3))
    d = CartaTela(cv, 400, 200, 100, 140, sm, cursore="hand2")
    il = d.create_line(0, 10, 100, 10, fill="#ffffff"); d.create_rectangle(0, 0, 99, 139, fill="#101014", tags="corpo")
    locali = []
    d.bind("<Motion>", lambda e: locali.append((round(e.x), round(e.y))))
    d.sposta(300, 100)
    casi.append(("sposta porta con se' tutti gli elementi", cv.coords(il) == [300.0, 110.0, 400.0, 110.0]))
    sm.muovi(E(320, 130))
    casi.append(("gli eventi arrivano coi x e y della carta, col cursore della carta", locali == [(20, 30)] and cv.cget("cursor") == "hand2"))
    casi.append(("itemcget per tag interno", d.itemcget("corpo", "fill") == "#101014"))
    d.delete("all"); d.create_rectangle(0, 0, 10, 10)
    casi.append(("delete all e ridisegno: la carta resta viva", d.winfo_exists() and len(d.find_all()) == 1))
    d.destroy(); d.create_rectangle(0, 0, 10, 10)
    casi.append(("negativa: distrutta non disegna piu' niente", not cv.find_withtag(d.tag)))
    sm.muovi(E(590, 390))
    casi.append(("fuori dalle carte il cursore torna normale", cv.cget("cursor") == ""))
    sm.svuota()
    casi.append(("svuota le toglie tutte", not cv.find_withtag("cartatela") and not sm.carte))
    root.destroy()
    for n, ok in casi:
        print(("OK   " if ok else "ROSSO") + " " + n)
    print(f"{sum(ok for _, ok in casi)}/{len(casi)}")
    return 0 if all(ok for _, ok in casi) else 1


if __name__ == "__main__":
    if "--prova" in sys.argv:
        sys.exit(prova())
