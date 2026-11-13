"""Le tabelle disegnate su una tela sola (11 nov 2026, sessione Magic 13, `Note/Motore_Grafico_App.md`; Autore: «aggiorna il motore grafico dell'app, valuta
se conviene passare tutto a scheda video perché è scattosa e refresha male»).

Pagina.tabella faceva una tabella con una cornice di Tk per cella e un'etichetta dentro: su Windows ogni widget e' una finestra, e una tabella di 12 righe per 5
colonne erano ~130 finestre (Performance, Resources, la finestra di un mazzo). Qui la tabella e' una tela: le intestazioni in maiuscolo bianco sopra le colonne,
le righe a fasce alterne, la colonna «allarga» che prende lo spazio in piu', le righe evidenziate, come prima.

Le celle si dichiarano, non si disegnano a mano:
- Testo(testo, col, forte, grande, lato): un testo («right» a destra, «left» a sinistra della cella);
- Righe([(testo, col, forte, grande)], lato): piu' righe una sotto l'altra (le due carte di una mano);
- WR(vinte, partite): la barra del win rate da 0 a 100 con la tacca al 50% e il numero;
- Barra(q, colore): una barra che riempie la cella per q (0-1);
- Mana(colori, testo, numero): i simboli di mana, poi un testo (un mazzo, un archetipo), con un numero davanti se serve;
- Immagine(immagine, testo): un'immagine e un testo accanto (la coppa del trofeo).
Ognuna resta anche una funzione f(cornice) che disegna nella cornice di Tk come prima: una tabella con una cella fatta a mano torna la tabella di prima.

Le righe sono RigaTela (carta_tela.CartaTela su tutta la riga): bind per tutta la riga, accendi() e spegni() per il fondo, cella_a(x) per sapere su che cella
sta il puntatore, testi(). La tela ha .righe e .testi().

`--prova`: misure e allineamenti, fasce, evidenzia, allarga, clic e accensione di una riga, la cella sotto il puntatore, con le negative."""
import os, sys
_casa = os.path.dirname(os.path.abspath(__file__))      # si sale fino a percorsi.py, che mette nel sys.path tutte le cartelle del Companion
while not os.path.isfile(os.path.join(_casa, "percorsi.py")):
    _casa = os.path.dirname(_casa)
if _casa not in sys.path:
    sys.path.insert(0, _casa)
import percorsi  # noqa: E402,F401

import carta_tela  # noqa: E402

_FONT = {}      # (radice, font) -> tkfont.Font: le misure dei testi


_MISURE = {}    # (radice, font, testo) -> (larghezza, alto della riga): ogni misura e' una chiamata a Tk


def misura(tk_w, font, testo):
    from tkinter import font as tkfont
    r = id(tk_w.winfo_toplevel())
    km = (r, repr(font), testo)
    m = _MISURE.get(km)
    if m is None:
        k = (r, repr(font))
        f = _FONT.get(k)
        if f is None:
            f = _FONT[k] = (tkfont.Font(root=tk_w, font=font), None)
        if f[1] is None:
            f = _FONT[k] = (f[0], f[0].metrics("linespace"))
        if len(_MISURE) > 20000:
            _MISURE.clear()
        m = _MISURE[km] = (f[0].measure(testo), f[1])
    return m


class Cella:
    """Una cella dichiarata. tk, F, C e mana arrivano dalla pagina (Pagina.cella e le altre)."""

    def __init__(self, pg):
        self.pg = pg

    def dimensioni(self, cv):
        raise NotImplementedError

    def disegna(self, cv, x0, x1, ym, tags):
        raise NotImplementedError


class Testo(Cella):
    def __init__(self, pg, testo, col=None, forte=False, grande=9, lato="right"):
        super().__init__(pg)
        self.testo, self.col, self.forte, self.grande, self.lato = str(testo), col, forte, grande, lato

    def font(self):
        return self.pg.F(self.grande, self.forte)

    def dimensioni(self, cv):
        return misura(cv, self.font(), self.testo)

    def disegna(self, cv, x0, x1, ym, tags):
        a_destra = self.lato == "right"
        cv.create_text(x1 if a_destra else x0, ym, text=self.testo, anchor="e" if a_destra else "w", fill=self.col or self.pg.C["testo"], font=self.font(), tags=tags)

    def __call__(self, c):
        self.pg.tk.Label(c, text=self.testo, bg=c["bg"], fg=self.col or self.pg.C["testo"], font=self.font(), pady=0).pack(side=self.lato)


class Righe(Cella):
    def __init__(self, pg, righe, lato="left"):
        super().__init__(pg)
        self.righe = [(str(t), col, forte, grande) for t, col, forte, grande in righe]
        self.lato = lato

    def dimensioni(self, cv):
        dd = [misura(cv, self.pg.F(g, f), t) for t, _c, f, g in self.righe] or [(0, 0)]
        return max(d[0] for d in dd), sum(d[1] for d in dd)

    def disegna(self, cv, x0, x1, ym, tags):
        _l, alto = self.dimensioni(cv)
        y = ym - alto / 2
        for t, col, forte, grande in self.righe:
            _w, h = misura(cv, self.pg.F(grande, forte), t)
            cv.create_text(x0 if self.lato == "left" else x1, y + h / 2, text=t, anchor="w" if self.lato == "left" else "e", fill=col or self.pg.C["titolo"],
                           font=self.pg.F(grande, forte), tags=tags)
            y += h

    def __call__(self, c):
        for t, col, forte, grande in self.righe:
            self.pg.tk.Label(c, text=t, bg=c["bg"], fg=col or self.pg.C["titolo"], font=self.pg.F(grande, forte), anchor="w", pady=0).pack(fill="x")


class WR(Cella):
    """Il win rate come barra da 0 a 100 con la tacca al 50%: azzurra sopra il 50, rossa sotto; il numero accanto."""

    def __init__(self, pg, w, n):
        super().__init__(pg)
        self.w, self.n = w, n

    def dimensioni(self, cv):
        cifre, h = misura(cv, self.pg.F(9, True), "0000")
        return 80 + 4 + cifre, max(h, 8)

    def disegna(self, cv, x0, x1, ym, tags):
        C = self.pg.C
        q = self.w / self.n if self.n else 0
        cv.create_text(x1, ym, text=f"{round(100 * q)}%" if self.n else "-", anchor="e", fill=C["titolo"], font=self.pg.F(9, True), tags=tags)
        cifre, _h = misura(cv, self.pg.F(9, True), "0000")
        bx1 = x1 - cifre - 4
        bx0 = bx1 - 80
        cv.create_rectangle(bx0, ym - 3, bx1, ym + 3, fill=C["traccia"], width=0, tags=tags)
        cv.create_rectangle(bx0, ym - 3, bx0 + 80 * q, ym + 3, fill=self.pg.VINTA if q >= 0.5 else self.pg.PERSA, width=0, tags=tags)
        cv.create_line(bx0 + 40, ym - 4, bx0 + 40, ym + 4, fill=C["muto"], tags=tags)

    def __call__(self, c):
        self.pg.barra_wr(c, self.w, self.n)


class Barra(Cella):
    """Una barra che riempie la larghezza della cella per q (0-1)."""

    def __init__(self, pg, q, colore):
        super().__init__(pg)
        self.q, self.colore = max(0.0, min(1.0, q)), colore

    def dimensioni(self, cv):
        return 40, 8

    def disegna(self, cv, x0, x1, ym, tags):
        cv.create_rectangle(x0, ym - 3, x1, ym + 3, fill=self.pg.C["traccia"], width=0, tags=tags)
        cv.create_rectangle(x0, ym - 3, x0 + (x1 - x0) * self.q, ym + 3, fill=self.colore, width=0, tags=tags)

    def __call__(self, c):
        cv = self.pg.tk.Canvas(c, height=8, bg=c["bg"], highlightthickness=0); cv.pack(fill="x", expand=True, pady=4)
        cv.bind("<Configure>", lambda e: (cv.delete("all"), cv.create_rectangle(0, 1, e.width, 7, fill=self.pg.C["traccia"], width=0),
                                          cv.create_rectangle(0, 1, e.width * self.q, 7, fill=self.colore, width=0)))


class Mana(Cella):
    """I simboli di mana dei colori, poi un testo; davanti un numero grigio se c'e' (la posizione in una classifica)."""

    def __init__(self, pg, colori, testo="", numero=None, col=None, grande=9, forte=False):
        super().__init__(pg)
        self.colori, self.testo, self.numero, self.col, self.grande, self.forte = colori or "", testo or "", numero, col, grande, forte

    def immagini(self):
        return [(self.pg.mana.get(k), k) for k in self.colori]

    def dimensioni(self, cv):
        L, h = 0, 16
        if self.numero is not None:
            L += misura(cv, self.pg.F(8), "00")[0] + 2
        for img, k in self.immagini():
            L += (img.width() if img else misura(cv, self.pg.F(8), k)[0]) + 2
        if self.testo:
            w, hh = misura(cv, self.pg.F(self.grande, self.forte), self.testo)
            L += 6 + w; h = max(h, hh)
        return L, h

    def disegna(self, cv, x0, x1, ym, tags):
        C, x = self.pg.C, x0
        if self.numero is not None:
            cv.create_text(x, ym, text=str(self.numero), anchor="w", fill=C["grigio"], font=self.pg.F(8), tags=tags)
            x += misura(cv, self.pg.F(8), "00")[0] + 2
        for img, k in self.immagini():
            if img:
                cv.create_image(x, ym, image=img, anchor="w", tags=tags); x += img.width() + 2
            else:
                cv.create_text(x, ym, text=k, anchor="w", fill=C["testo"], font=self.pg.F(8), tags=tags); x += misura(cv, self.pg.F(8), k)[0] + 2
        if self.testo:
            cv.create_text(x + (6 if self.colori or self.numero is not None else 0), ym, text=self.testo, anchor="w", fill=self.col or C["titolo"],
                           font=self.pg.F(self.grande, self.forte), tags=tags)

    def __call__(self, c):
        tk = self.pg.tk
        if self.numero is not None:
            tk.Label(c, text=str(self.numero), width=2, anchor="w", bg=c["bg"], fg=self.pg.C["grigio"], font=self.pg.F(8), pady=0).pack(side="left")
        self.pg.mana_label(c, self.colori, c["bg"]).pack(side="left")
        if self.testo:
            tk.Label(c, text=self.testo, bg=c["bg"], fg=self.col or self.pg.C["titolo"], font=self.pg.F(self.grande, self.forte), pady=0).pack(side="left", padx=(6, 0))


class Immagine(Cella):
    def __init__(self, pg, immagine=None, testo="", col=None, grande=7, forte=True):
        super().__init__(pg)
        self.img, self.testo, self.col, self.grande, self.forte = immagine, testo, col, grande, forte

    def dimensioni(self, cv):
        L = self.img.width() if self.img else 0
        h = self.img.height() if self.img else 0
        if self.testo:
            w, hh = misura(cv, self.pg.F(self.grande, self.forte), self.testo)
            L += (4 if self.img else 0) + w; h = max(h, hh)
        return L, h

    def disegna(self, cv, x0, x1, ym, tags):
        x = x0
        if self.img:
            cv.create_image(x, ym, image=self.img, anchor="w", tags=tags); x += self.img.width() + 4
        if self.testo:
            cv.create_text(x, ym, text=self.testo, anchor="w", fill=self.col or self.pg.C["testo"], font=self.pg.F(self.grande, self.forte), tags=tags)

    def __call__(self, c):
        if self.img:
            self.pg.tk.Label(c, image=self.img, bg=c["bg"]).pack(side="left")
        if self.testo:
            self.pg.tk.Label(c, text=self.testo, bg=c["bg"], fg=self.col or self.pg.C["testo"], font=self.pg.F(self.grande, self.forte), pady=0).pack(side="left")


class RigaTela(carta_tela.CartaTela):
    """Una riga della tabella: la CartaTela su tutta la riga, col fondo («fondo») da accendere."""

    def accendi(self, colore=None):
        self.itemconfigure("fondo", fill=colore or self.tab.C["sel"])

    def spegni(self):
        self.itemconfigure("fondo", fill=self.colore)

    def cella_a(self, x):
        """La colonna sotto x (coordinate della riga), o None."""
        for j, (a, b) in enumerate(self.tab.colonne_x):
            if a <= x < b:
                return j
        return None

    def testi(self):
        return [self.itemcget(i, "text") for i in self.find_all() if self.type(i) == "text"]

    def cliccabile(self, azione, accesa=True, cursore="hand2"):
        """Tutta la riga fa azione() al clic, col puntatore a mano e accesa sotto il puntatore."""
        self.cursore = cursore
        self.bind("<Button-1>", lambda e: azione(), add=True)
        if accesa:
            self.bind("<Enter>", lambda e: self.accendi(), add=True)
            self.bind("<Leave>", lambda e: self.spegni(), add=True)


class TabellaTela:
    def __init__(self, pg, padre, intestazioni, righe, allarga=0, evidenzia=(), padx=6):
        self.pg, self.C = pg, pg.C
        self.intest, self.celle, self.allarga, self.ev, self.padx = list(intestazioni), [list(r) for r in righe], allarga, set(evidenzia), padx
        tk = pg.tk
        self.cv = cv = tk.Canvas(padre, bg=self.C["scheda"], highlightthickness=0, bd=0, height=1); cv.pack(fill="x")
        cv.tabella = self
        self.sm = carta_tela.Smistatore(cv)
        self.righe = [RigaTela(cv, 0, 0, 1, 1, self.sm) for _ in self.celle]
        for i, r in enumerate(self.righe):
            r.tab, r.indice = self, i
        cv.righe = self.righe
        cv.testi = lambda: [cv.itemcget(i, "text") for i in cv.find_all() if cv.type(i) == "text"]
        self.misure()
        cv.bind("<Configure>", self.disegna)
        self.disegna()

    def misure(self):
        cv, n = self.cv, max([len(self.intest)] + [len(r) for r in self.celle])
        self.larghe = [0] * n
        _w, self.alto_testa = misura(cv, self.pg.F(7, True), "Ag")
        self.alto_testa += 6
        for j, (t, _al) in enumerate(self.intest):
            self.larghe[j] = max(self.larghe[j], misura(cv, self.pg.F(7, True), t.upper())[0] + 2 * self.padx)
        self.alti = []
        for riga in self.celle:
            h = 0
            for j, c in enumerate(riga):
                w, hh = c.dimensioni(cv)
                self.larghe[j] = max(self.larghe[j], w + 2 * self.padx)
                h = max(h, hh)
            self.alti.append(h + 4)

    def disegna(self, e=None):
        cv = self.cv
        W = cv.winfo_width()
        if W < 50:      # non ancora a vista: la larghezza del contenitore, se no la naturale; si rifa' quando arriva la vera
            W = cv.master.winfo_width() if cv.master.winfo_width() >= 50 else sum(self.larghe)
        if W == getattr(self, "fatta", None):
            return
        self.fatta = W
        cv.delete("testa")
        larghe = list(self.larghe)
        resto = W - sum(larghe)
        if resto > 0 and self.allarga < len(larghe):
            larghe[self.allarga] += resto
        xs, x = [], 0
        for L in larghe:
            xs.append((x, x + L)); x += L
        self.colonne_x = xs
        for j, (t, al) in enumerate(self.intest):
            a, b = xs[j]
            if t:
                cv.create_text(a + self.padx if al == "w" else b - self.padx, self.alto_testa / 2, text=t.upper(), anchor="w" if al == "w" else "e",
                               fill=self.C["titolo"], font=self.pg.F(7, True), tags="testa")
        y = self.alto_testa
        for i, (riga, r, h) in enumerate(zip(self.celle, self.righe, self.alti)):
            r.colore = self.C["sel"] if i in self.ev else (self.C["cap"] if i % 2 == 0 else self.C["scheda"])
            r.delete("all")
            r.x, r.y, r.larga, r.alta = 0, y, x, h
            r.create_rectangle(0, 0, x, h, fill=r.colore, width=0, tags="fondo")
            for j, c in enumerate(riga):
                a, b = xs[j]
                c.disegna(cv, a + self.padx, b - self.padx, y + h / 2, (r.tag, "cartatela"))
            y += h
        cv.configure(height=max(1, y))


def prova():
    import tkinter as tk
    from tema import CI, PERSA, VINTA
    root = tk.Tk(); root.geometry("600x400+5000+20")

    class Pg:
        pass
    pg = Pg(); pg.tk, pg.C, pg.VINTA, pg.PERSA, pg.mana = tk, CI, VINTA, PERSA, {}
    pg.F = lambda n, b=False: ("Segoe UI", n, "bold" if b else "normal")
    fr = tk.Frame(root, width=600); fr.pack(fill="both", expand=True); root.update()
    righe = [[Mana(pg, "", "Mazzo lungo", numero=1), Testo(pg, "12-8"), WR(pg, 12, 20)], [Mana(pg, "", "Corto", numero=2), Testo(pg, "3-7"), WR(pg, 3, 10)]]
    t = TabellaTela(pg, fr, [("deck", "w"), ("record", "e"), ("win rate", "e")], righe, allarga=0, evidenzia=(1,))
    root.update()
    cv = t.cv
    casi = []
    casi.append(("la tabella prende la larghezza, la colonna allarga lo spazio in piu'", abs(t.colonne_x[-1][1] - cv.winfo_width()) <= 1 and t.colonne_x[0][1] - t.colonne_x[0][0] > t.larghe[0]))
    testi = cv.testi()
    casi.append(("intestazioni in maiuscolo e celle", testi[:3] == ["DECK", "RECORD", "WIN RATE"] and "Mazzo lungo" in testi and "60%" in testi and "30%" in testi))
    casi.append(("fasce alterne e la riga evidenziata", t.righe[0].itemcget("fondo", "fill") == CI["cap"] and t.righe[1].itemcget("fondo", "fill") == CI["sel"]))
    rec = [i for i in t.righe[0].find_all() if cv.type(i) == "text" and cv.itemcget(i, "text") == "12-8"][0]
    casi.append(("un testo a destra finisce al bordo della sua colonna", abs(cv.bbox(rec)[2] - (t.colonne_x[1][1] - t.padx)) <= 2))
    visti = []
    t.righe[0].cliccabile(lambda: visti.append("clic"))
    E = lambda x, y: carta_tela.Evento(x=x, y=y, x_root=x, y_root=y, widget=cv)
    ym = t.righe[0].y + t.righe[0].alta / 2
    t.sm.muovi(E(20, ym))
    casi.append(("sotto il puntatore la riga si accende", t.righe[0].itemcget("fondo", "fill") == CI["sel"] and cv.cget("cursor") == "hand2"))
    t.sm.premi(E(20, ym)); t.sm.rilascia(E(20, ym))
    casi.append(("il clic sulla riga", visti == ["clic"]))
    t.sm.muovi(E(20, t.righe[1].y + 3))
    casi.append(("lasciata, torna com'era", t.righe[0].itemcget("fondo", "fill") == CI["cap"]))
    t.sm.premi(E(20, t.righe[1].y + 3)); t.sm.rilascia(E(20, t.righe[1].y + 3))
    casi.append(("negativa: la riga senza azione non fa niente", visti == ["clic"]))
    casi.append(("la cella sotto il puntatore", t.righe[0].cella_a(t.colonne_x[2][0] + 5) == 2 and t.righe[0].cella_a(-5) is None))
    root.geometry("400x400+5000+20"); root.update()
    casi.append(("piu' stretta: si rifa' alla misura nuova", abs(t.colonne_x[-1][1] - cv.winfo_width()) <= 1 and cv.winfo_width() < 500))
    cel = Testo(pg, "vecchio modo", lato="left")
    f2 = tk.Frame(root, bg="#000000"); f2.pack(); cel(f2)
    casi.append(("una cella resta anche una funzione per la tabella di prima", f2.winfo_children()[0].cget("text") == "vecchio modo"))
    root.destroy()
    for n, ok in casi:
        print(("OK   " if ok else "ROSSO") + " " + n)
    print(f"{sum(ok for _, ok in casi)}/{len(casi)}")
    return 0 if all(ok for _, ok in casi) else 1


if __name__ == "__main__":
    if "--prova" in sys.argv:
        sys.exit(prova())
