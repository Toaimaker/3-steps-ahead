"""I mini-menu del Board, tutti uguali (13 nov 2026 sera, Autore: «sistema i minimenù, voglio tutto molto più ordinato e dal tono più esport»).

Fino a quel giorno ogni finestrella del Board (Arrange, Groups, il ≡ di un gruppo, la tavolozza delle linee, la nota, il ⇄) era fatta a mano: titoli in
minuscolo, azioni come scritte colorate sparse su una riga, colori diversi. Qui uno stile solo, da scena esport: fondo quasi nero, bordo azzurro neon, una
testata con la barra azzurra a sinistra, il titolo in maiuscolo e la ✕; sezioni in maiuscolo azzurro col filo che le chiude; righe con la barra azzurra che si
accende sotto il mouse; azioni come pulsanti pieni e squadrati (azzurro, verde per Save, rosso per togliere, grigio per il resto); campi col bordo che si
accende quando scrivi. Ogni finestrella sta sopra la sua finestra (piattaforma.sopra_di).

Uso: m = Menu(tk, F, padre, "Groups", chiudi); m.sezione("NEW"); m.voce(...); m.pulsanti([...]); m.piede("..."); m.posa(sotto=widget). Prova: --prova.
"""
import os, sys
_casa = os.path.dirname(os.path.abspath(__file__))      # si sale fino a percorsi.py, che mette nel sys.path tutte le cartelle del Companion
while not os.path.isfile(os.path.join(_casa, "percorsi.py")):
    _casa = os.path.dirname(_casa)
if _casa not in sys.path:
    sys.path.insert(0, _casa)
import percorsi  # noqa: E402,F401
import piattaforma  # noqa: E402

from tema import CI as C  # noqa: E402
from widget import ROSSO_P, VERDE_P, pulsante_solido  # noqa: E402

FONDO = "#0a0d12"           # il corpo: piu' scuro del foglio, cosi' il menu si stacca
TESTA = "#121722"           # la testata
RIGA_SU = "#18202c"         # la riga sotto il mouse
NEON = C["accento"]         # #24baff
NEON_TENUE = "#6fb6ff"      # le sezioni
AZZURRO_P = ("#0f86cc", "#2ba3ea", "#0b5f94")
GRIGIO_P = ("#2a2a32", "#383842", "#1f1f25")
COLORI_P = dict(primario=AZZURRO_P, salva=VERDE_P, pericolo=ROSSO_P, secondario=GRIGIO_P)


class Menu:
    """Una finestrella del Board nello stile comune. chiudi: chi la chiude (la ✕, Esc); senza, si distrugge da sola."""

    def __init__(self, tk, F, padre, titolo, chiudi=None, colore=None, larga=None):
        self.tk, self.F, self.padre = tk, F, padre
        self.chiudi = chiudi or self.distruggi
        self.colore = colore or NEON
        p = self.p = tk.Toplevel(padre)
        p.overrideredirect(True)
        p.configure(bg=self.colore)
        self.dentro = tk.Frame(p, bg=FONDO)
        self.dentro.pack(padx=1, pady=1, fill="both", expand=True)
        testa = tk.Frame(self.dentro, bg=TESTA)
        testa.pack(fill="x")
        tk.Frame(testa, bg=self.colore, width=3).pack(side="left", fill="y")
        self.l_titolo = tk.Label(testa, text=titolo.upper(), bg=TESTA, fg="#ffffff", font=F(9, True), anchor="w")
        self.l_titolo.pack(side="left", padx=(10, 24), pady=8)
        x = self.x = tk.Label(testa, text="✕", bg=TESTA, fg=C["muto"], font=F(9, True), cursor="hand2", padx=10)
        x.pack(side="right")
        x.bind("<Enter>", lambda e: x.configure(fg="#ffffff"))
        x.bind("<Leave>", lambda e: x.configure(fg=C["muto"]))
        x.bind("<Button-1>", lambda e: self.chiudi())
        tk.Frame(self.dentro, bg=C["filo"], height=1).pack(fill="x")
        self.corpo = tk.Frame(self.dentro, bg=FONDO)
        self.corpo.pack(fill="both", expand=True, pady=(4, 6))
        if larga:
            tk.Frame(self.corpo, bg=FONDO, width=larga, height=0).pack()
        p.bind("<Escape>", lambda e: self.chiudi())
        self.voci = {}      # testo -> azione: le prove le chiamano da qui

    def distruggi(self):
        try:
            self.p.destroy()
        except Exception:       # noqa: BLE001 - gia' chiusa
            pass

    def sezione(self, nome):
        """Il nome della sezione in maiuscolo azzurro, col filo che arriva al bordo."""
        tk = self.tk
        r = tk.Frame(self.corpo, bg=FONDO)
        r.pack(fill="x", padx=12, pady=(10, 3))
        tk.Label(r, text=nome.upper(), bg=FONDO, fg=NEON_TENUE, font=self.F(7, True)).pack(side="left")
        tk.Frame(r, bg=C["filo"], height=1).pack(side="left", fill="x", expand=True, padx=(8, 0), pady=(2, 0))
        return r

    def voce(self, titolo, riga, fa, colore=None, spenta=False, chiudi=True, destra=None):
        """Una riga che si sceglie: il titolo, sotto la riga che dice cosa fa; la barra azzurra a sinistra si accende sotto il mouse. spenta: grigia, senza clic
        (la riga dice cosa manca). destra: un testo piccolo a destra (un conto). -> la riga."""
        tk, F = self.tk, self.F
        r = tk.Frame(self.corpo, bg=FONDO, cursor="arrow" if spenta else "hand2")
        r.pack(fill="x", padx=(8, 8), pady=1)
        barra = tk.Frame(r, bg=FONDO, width=3)
        barra.pack(side="left", fill="y")
        testi = tk.Frame(r, bg=FONDO)
        testi.pack(side="left", fill="x", expand=True, padx=(8, 6), pady=4)
        a = tk.Label(testi, text=titolo, bg=FONDO, fg=C["muto"] if spenta else (colore or "#ffffff"), font=F(9, True), anchor="w")
        a.pack(fill="x")
        b = tk.Label(testi, text=riga, bg=FONDO, fg=C["muto"] if spenta else C["grigio"], font=F(7), anchor="w", justify="left")
        b.pack(fill="x")
        tutti = [r, testi, a, b]
        if destra:
            d = tk.Label(r, text=destra, bg=FONDO, fg=C["grigio"], font=F(8, True))
            d.pack(side="right", padx=(0, 6))
            tutti.append(d)
        self.voci[titolo] = fa
        if spenta:
            return r

        def acc(on):
            for w_ in tutti:
                w_.configure(bg=RIGA_SU if on else FONDO)
            barra.configure(bg=(colore or NEON) if on else FONDO)

        def clic(_e=None):
            if chiudi:
                self.chiudi()
            fa()
        for w_ in tutti:
            w_.bind("<Button-1>", clic)
            w_.bind("<Enter>", lambda e: acc(True))
            w_.bind("<Leave>", lambda e: acc(False))
        return r

    def riga(self, padx=12, pady=(2, 2)):
        """Una riga libera dentro il corpo, per i contenuti propri (colori, slider, liste)."""
        r = self.tk.Frame(self.corpo, bg=FONDO)
        r.pack(fill="x", padx=padx, pady=pady)
        return r

    def etichetta(self, padre, testo):
        """Il nome di un campo, in maiuscolo grigio."""
        lb = self.tk.Label(padre, text=testo.upper(), bg=FONDO, fg=C["muto"], font=self.F(7, True), anchor="w")
        lb.pack(fill="x", pady=(4, 2))
        return lb

    def campo(self, padre, var, larga=28, righe=None):
        """Una casella di testo (righe: un Text su piu' righe) col bordo che si accende di azzurro quando ci scrivi. -> la casella."""
        tk = self.tk
        kw = dict(bg=TESTA, fg="#ffffff", insertbackground="#ffffff", relief="flat", font=self.F(10), highlightthickness=1,
                  highlightbackground=C["filo"], highlightcolor=NEON)
        if righe:
            e = tk.Text(padre, width=larga, height=righe, wrap="word", padx=8, pady=6, **kw)
        else:
            e = tk.Entry(padre, textvariable=var, width=larga, **kw)
        e.pack(fill="x", ipady=0 if righe else 5)
        return e

    def lista(self, padre, righe=8, larga=40):
        """Una lista (Listbox) nello stile: fondo scuro, riga scelta azzurra, niente bordi. -> la lista."""
        lb = self.tk.Listbox(padre, bg=TESTA, fg=C["testo"], selectbackground=NEON, selectforeground="#ffffff", relief="flat", bd=0, highlightthickness=1,
                             highlightbackground=C["filo"], highlightcolor=C["filo"], font=self.F(10), activestyle="none", height=righe, width=larga)
        lb.pack(fill="x", pady=(6, 0))
        return lb

    def pulsanti(self, voci, padre=None):
        """Una riga di pulsanti pieni e squadrati, a destra il primo: voci [(testo, azione, tipo)] con tipo primario, salva, pericolo, secondario. -> {testo: pulsante}."""
        tk, F = self.tk, self.F
        r = tk.Frame(padre or self.corpo, bg=FONDO)
        r.pack(fill="x", padx=12, pady=(8, 4))
        out = {}
        for i, (testo, fa, tipo) in enumerate(voci):
            b = pulsante_solido(tk, F, r, testo, False, fa, alto=28, bg=FONDO, colori=COLORI_P.get(tipo, AZZURRO_P))
            b.configure(width=max(76, 12 + 8 * len(testo)))
            b.pack(side="right", padx=(6 if i else 0, 0))
            out[testo] = b
            self.voci[testo] = fa
        return out

    def piede(self, testo):
        """La riga d'aiuto in fondo, piccola e grigia, sopra un filo."""
        tk = self.tk
        tk.Frame(self.corpo, bg=C["filo2"], height=1).pack(fill="x", padx=12, pady=(10, 0))
        tk.Label(self.corpo, text=testo, bg=FONDO, fg=C["muto"], font=self.F(7), anchor="w", justify="left", wraplength=330).pack(fill="x", padx=12, pady=(6, 2))

    def posa(self, sotto=None, xy=None, fuoco=None):
        """La mette sotto il widget sotto (allineata a sinistra), o in xy (coordinate dello schermo), o accanto al puntatore; dentro lo schermo; sopra la sua
        finestra. fuoco: il widget che prende la tastiera (se no la finestrella)."""
        p = self.p
        p.update_idletasks()
        if sotto is not None and sotto.winfo_ismapped():
            x, y = sotto.winfo_rootx(), sotto.winfo_rooty() + sotto.winfo_height() + 4
        elif xy is not None:
            x, y = xy
        else:
            x, y = self.padre.winfo_pointerx() + 12, self.padre.winfo_pointery() + 12
        # dentro la finestra da cui nasce, non dentro lo schermo (13 nov 2026, Autore: «se apro i menu di board editor le loro tendine si aprono da un'altra
        # parte»): winfo_screenwidth di Tk e' il solo monitor principale (1920), e con l'app sul secondo monitor ogni menu tornava sul primo
        L, H = p.winfo_reqwidth(), p.winfo_reqheight()
        top = self.padre.winfo_toplevel()
        X0, Y0 = top.winfo_rootx(), top.winfo_rooty()
        X1, Y1 = X0 + max(top.winfo_width(), L), Y0 + max(top.winfo_height(), H)
        x = max(X0, min(int(x), X1 - L - 4))
        y = max(Y0, min(int(y), Y1 - H - 4))
        p.geometry(f"+{x}+{y}")
        piattaforma.sopra_di(p, self.padre)
        (fuoco or p).focus_force()
        return p


def prova():
    """Fuori schermo: la testata col titolo in maiuscolo e la ✕, la sezione, la voce che chiude e fa, la voce spenta senza clic, i pulsanti coi colori, Esc."""
    import tkinter as tk
    root = tk.Tk(); root.geometry("300x200+-3000+0"); root.update()
    F = lambda s, b=False: ("Segoe UI", s, "bold" if b else "normal")
    casi, fatto = [], []
    m = Menu(tk, F, root, "Groups")
    m.sezione("New")
    m.voce("Group the selection", "Name and color", lambda: fatto.append("sel"))
    m.voce("Spenta", "manca qualcosa", lambda: fatto.append("spenta"), spenta=True)
    bb = m.pulsanti([("Save", lambda: fatto.append("save"), "salva"), ("Delete", lambda: None, "pericolo")])
    m.piede("Esc closes")
    m.posa(xy=(-2800, 10))
    root.update()
    testi = [w.cget("text") for w in _tutti(m.p) if isinstance(w, tk.Label)]
    casi.append(("la testata: il titolo in maiuscolo e la ✕", "GROUPS" in testi and "✕" in testi))
    casi.append(("la sezione in maiuscolo", "NEW" in testi))
    riga_spenta = [w for w in _tutti(m.p) if isinstance(w, tk.Label) and w.cget("text") == "Spenta"][0]
    riga_spenta.event_generate("<Button-1>"); root.update()
    casi.append(("negativa: la voce spenta non fa niente", "spenta" not in fatto and m.p.winfo_exists()))
    voce = [w for w in _tutti(m.p) if isinstance(w, tk.Label) and w.cget("text") == "Group the selection"][0]
    voce.event_generate("<Button-1>"); root.update()
    casi.append(("la voce chiude la finestrella e fa la sua azione", fatto == ["sel"] and not m.p.winfo_exists()))
    casi.append(("Save nei colori verdi, Delete in quelli rossi", "Save" in bb and "Delete" in bb))
    m2 = Menu(tk, F, root, "Line"); m2.posa(xy=(-2800, 10)); root.update()
    m2.p.event_generate("<Escape>"); root.update()
    casi.append(("Esc la chiude", not m2.p.winfo_exists()))
    # sul secondo monitor: la finestra a x -3000 (fuori dal monitor principale); il menu resta dove lo chiedi, dentro la sua finestra (prima tornava a x 0)
    big = tk.Toplevel(root); big.geometry("900x600+-3000+0"); root.update()
    pul = tk.Frame(big, width=120, height=28, bg="#24baff"); pul.place(x=200, y=40); root.update()
    m3 = Menu(tk, F, big, "Groups"); m3.voce("x", "y", lambda: None); m3.posa(sotto=pul); root.update()
    casi.append(("sotto il suo pulsante anche fuori dal monitor principale (la finestra a x -3000)", abs(m3.p.winfo_rootx() - pul.winfo_rootx()) <= 2
                 and m3.p.winfo_rooty() >= pul.winfo_rooty() + pul.winfo_height()))
    m3.distruggi()
    m4 = Menu(tk, F, big, "Groups"); m4.posa(xy=(-2000, 50)); root.update()
    casi.append(("negativa: chiesto oltre il bordo destro della finestra, resta dentro di lei", m4.p.winfo_rootx() + m4.p.winfo_width() <= big.winfo_rootx() + 900
                 and m4.p.winfo_rootx() >= big.winfo_rootx()))
    m4.distruggi(); big.destroy()
    root.destroy()
    for nome, ok in casi:
        print(("ok   " if ok else "ROSSO") + " " + nome)
    print(f"{sum(ok for _n, ok in casi)}/{len(casi)}")
    return all(ok for _n, ok in casi)


def _tutti(w):
    yield w
    for x in w.winfo_children():
        yield from _tutti(x)


if __name__ == "__main__":
    sys.exit(0 if (prova() if "--prova" in sys.argv else True) else 1)
