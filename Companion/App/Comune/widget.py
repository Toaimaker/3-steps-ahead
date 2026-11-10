"""I comandi dell'interfaccia: tendine, scelte, numeri, spunte, il pulsante pieno."""
import disegni as DG
import tk_sicuro

from tema import CI as C, TEND

tk_sicuro.applica()        # un widget distrutto cancella i suoi after (l'errore dei bind chiamati senza evento, 10 nov 2026)


class Tendina:
    """Una tendina  scuro: il nome sopra in
    maiuscolo bianco, il campo squadrato col bordo sottile e la freccia a V, il menu che si apre sotto il campo con voci piatte
    e la fascia chiara sotto il puntatore. Al posto della OptionMenu di Windows (Autore, 18 ott 2026)."""

    def __init__(self, tk, padre, nome, F, larga=200, bg=None):
        self.tk, self.F, self.var, self.voci, self.cb, self.menu = tk, F, tk.StringVar(value=""), [], None, None
        self.fr = tk.Frame(padre, bg=bg or C["fondo"])
        tk.Label(self.fr, text=nome.upper(), bg=bg or C["fondo"], fg=C["titolo"], font=F(7, True), pady=0).pack(anchor="w", pady=(0, 3))
        self.campo = tk.Frame(self.fr, bg=TEND["campo"], highlightthickness=1, highlightbackground=TEND["bordo"], width=larga, height=32,
                              cursor="hand2")
        self.campo.pack(anchor="w"); self.campo.pack_propagate(False)
        self.vista_var = tk.StringVar(value="")     # quel che si legge nel campo (il nome); self.var tiene il valore (il codice)
        self.lab = tk.Label(self.campo, textvariable=self.vista_var, bg=TEND["campo"], fg=TEND["testo"], font=F(9), anchor="w", padx=12, cursor="hand2")
        self.lab.pack(side="left", fill="both", expand=True)
        self.v = tk.Canvas(self.campo, width=26, height=30, bg=TEND["campo"], highlightthickness=0, cursor="hand2"); self.v.pack(side="right")
        self.freccia(False)
        for w in (self.campo, self.lab, self.v):
            w.bind("<Button-1>", lambda e: self.apri())
        self.campo.bind("<Enter>", lambda e: self.campo.configure(highlightbackground=C["grigio"]))
        self.campo.bind("<Leave>", lambda e: self.campo.configure(highlightbackground=TEND["bordo"]))

    def freccia(self, aperta):
        self.v.delete("all")      # la V capovolta quando il menu e' aperto, come sul sito; disegnata nitida (disegni.py)
        self.v.create_image(0, 2.5, image=DG.chevron(25, not aperta, TEND["muto"]), anchor="nw")

    def opzioni(self, voci, cb, icone=None, etichette=None):
        """icone: {voce: PhotoImage} da mettere accanto al nome (il simbolo dell'espansione, 18 ott 2026); etichette:
        {voce: testo da leggere} (il nome dell'espansione accanto al codice)."""
        self.voci, self.cb = list(voci), cb
        if icone is not None:
            self.icone = icone
        if etichette is not None:
            self.etichette = etichette
        self.set(self.var.get())

    def get(self):
        return self.var.get()

    def testo(self, v):
        return getattr(self, "etichette", {}).get(v, v)

    def attiva(self, v):
        return v == self.var.get()

    def voce_menu(self, v):
        return self.testo(v)

    def set(self, v):
        self.var.set(v)
        self.vista_var.set(("  " if getattr(self, "icone", {}).get(v) else "") + getattr(self, "corte", {}).get(v, self.testo(v)))   # corte: nel campo stretto, il codice
        img = getattr(self, "icone", {}).get(v)
        self.lab.configure(image=img or "", compound="left" if img else "none")

    def chiudi(self, e=None):
        if self.menu is not None:
            self.menu.destroy(); self.menu = None; self.freccia(False)

    def apri(self):
        tk, F = self.tk, self.F
        if self.menu is not None:
            self.chiudi(); return
        m = self.menu = tk.Toplevel(self.campo)
        m.overrideredirect(True)
        m.configure(bg=TEND["bordo"])
        dentro = tk.Frame(m, bg=TEND["campo"]); dentro.pack(fill="both", expand=True, padx=1, pady=1)
        cv = None
        if len(self.voci) > 14:     # tante voci: scorrono con la rotella, se no il menu esce dallo schermo
            cv = tk.Canvas(dentro, bg=TEND["campo"], highlightthickness=0, height=430); cv.pack(fill="both", expand=True)
            dentro = tk.Frame(cv, bg=TEND["campo"]); cv.create_window(0, 0, anchor="nw", window=dentro)
            m.bind("<MouseWheel>", lambda e: cv.yview_scroll(-3 if e.delta > 0 else 3, "units"))
        for voce in self.voci:
            sel = self.attiva(voce)
            img = getattr(self, "icone", {}).get(voce)
            l = tk.Label(dentro, text=("  " + self.voce_menu(voce)) if img else self.voce_menu(voce), image=img or "", compound="left" if img else "none",
                         bg=TEND["sopra"] if sel else TEND["campo"], fg=TEND["testo"] if sel else C["grigio"],
                         font=F(9), anchor="w", padx=12, pady=6, cursor="hand2")
            l.pack(fill="x")
            l.bind("<Enter>", lambda e, l=l: l.configure(bg=TEND["sopra"], fg=TEND["testo"]))
            l.bind("<Leave>", lambda e, l=l, sel=sel: l.configure(bg=TEND["sopra"] if sel else TEND["campo"], fg=TEND["testo"] if sel else C["grigio"]))
            l.bind("<Button-1>", lambda e, voce=voce: self.scegli(voce))
        self.campo.update_idletasks()
        if cv is not None:
            cv.configure(width=dentro.winfo_reqwidth(), scrollregion=(0, 0, dentro.winfo_reqwidth(), dentro.winfo_reqheight()))
            m.update_idletasks()
        x, y = self.campo.winfo_rootx(), self.campo.winfo_rooty() + self.campo.winfo_height()
        m.geometry(f"{max(self.campo.winfo_width(), m.winfo_reqwidth())}x{m.winfo_reqheight()}+{x}+{y}")
        m.bind("<FocusOut>", self.chiudi); m.bind("<Escape>", self.chiudi)
        m.focus_force()
        self.freccia(True)

    def scegli(self, voce):
        self.chiudi()
        self.set(voce)        # set aggiorna anche il testo del campo e il simbolo (con var.set da solo restava la voce di prima)
        if self.cb:
            self.cb(voce)


class TendinaMulti(Tendina):
    """Una tendina con le voci flaggabili (Autore, 6 nov 2026: «rendiamo la tendina delle risorse con le risorse flaggabili per incrociare piu' dati»): il menu resta aperto mentre si flagga,
    get da' la lista nell'ordine delle voci, almeno una resta sempre accesa."""

    scelti = ()
    parola = "resources"       # nel campo: «All resources», «3 resources»

    def opzioni(self, voci, cb, icone=None, etichette=None):
        self.voci, self.cb = list(voci), cb
        if icone is not None:
            self.icone = icone
        if etichette is not None:
            self.etichette = etichette
        self.set(self.scelti)

    def get(self):
        return [v for v in self.voci if v in self.scelti]

    def attiva(self, v):
        return v in self.scelti

    def voce_menu(self, v):
        return ("✓  " if v in self.scelti else "     ") + self.testo(v)

    def set(self, v):
        self.scelti = [v] if isinstance(v, str) else list(v)
        q = self.get()
        tutte = len(q) > 2 and len(q) == len(self.voci)
        self.vista_var.set(f"All {self.parola}" if tutte else self.testo(q[0]) if len(q) == 1 else " + ".join(self.testo(x) for x in q) if len(q) == 2 else f"{len(q)} {self.parola}")
        img = getattr(self, "icone", {}).get(q[0]) if len(q) == 1 else None
        self.vista_var.set(("  " if img else "") + self.vista_var.get())
        self.lab.configure(image=img or "", compound="left" if img else "none")

    def scegli(self, voce):
        aperto = self.menu is not None
        if voce in self.scelti and len(self.scelti) > 1:
            self.set([x for x in self.scelti if x != voce])
        elif voce not in self.scelti:
            self.set(list(self.scelti) + [voce])
        if aperto:         # si rifa' il menu coi segni nuovi, resta aperto
            self.chiudi(); self.apri()
        if self.cb:
            self.cb(voce)


class Scelte:
    """Una fila di pulsanti accesi o spenti, piu' d'uno insieme: il nome sopra in maiuscolo bianco. Nessuno acceso vuol dire tutti."""

    def __init__(self, tk, padre, nome, voci, F, cb, bg, colonne=4, immagini=None):
        self.on, self.cb, self.tasti = set(), cb, {}
        self.fr = tk.Frame(padre, bg=bg)
        tk.Label(self.fr, text=nome.upper(), bg=bg, fg=C["titolo"], font=F(7, True), pady=0).pack(anchor="w", pady=(0, 3))
        g = tk.Frame(self.fr, bg=bg); g.pack(fill="x")
        for j in range(colonne):
            g.columnconfigure(j, weight=1, uniform="scelte")
        for i, (k, testo) in enumerate(voci):
            img = (immagini or {}).get(k)
            l = tk.Label(g, text="" if img else testo, image=img or "", bg=TEND["campo"], fg=C["grigio"], font=F(8, True), pady=5 if not img else 4, cursor="hand2",
                         highlightthickness=1, highlightbackground=TEND["bordo"])
            l.grid(row=i // colonne, column=i % colonne, sticky="ew", padx=(0, 3), pady=(0, 3))
            l.bind("<Button-1>", lambda e, k=k: self.scegli(k))
            self.tasti[k] = l

    def scegli(self, k):
        self.on ^= {k}
        self.disegna()
        self.cb()

    def disegna(self):
        for k, l in self.tasti.items():
            acceso = k in self.on
            l.configure(bg=C["accento"] if acceso else TEND["campo"], fg=C["fondo"] if acceso else C["grigio"], highlightbackground=C["accento"] if acceso else TEND["bordo"])

    def vuota(self):
        self.on = set()
        self.disegna()


class Numero:
    """Un numero da scegliere: il nome sopra in maiuscolo bianco, il campo squadrato come la Tendina, − e + ai lati, si puo' anche scrivere."""

    def __init__(self, tk, padre, nome, F, cb, val=0, passo=1, massimo=999999, larga=126, bg=None):
        self.passo, self.massimo, self.cb, self.bloccato = passo, massimo, cb, False
        self.fr = tk.Frame(padre, bg=bg or C["fondo"])
        tk.Label(self.fr, text=nome.upper(), bg=bg or C["fondo"], fg=C["titolo"], font=F(7, True), pady=0).pack(anchor="w", pady=(0, 3))
        self.riga = tk.Frame(self.fr, bg=bg or C["fondo"]); self.riga.pack(anchor="w")        # il riquadro, e accanto quel che gli serve
        self.bg, self.F, self.tk = bg or C["fondo"], F, tk
        self.l_reset = None
        c = tk.Frame(self.riga, bg=TEND["campo"], highlightthickness=1, highlightbackground=TEND["bordo"], width=larga, height=32)
        c.pack(side="left"); c.pack_propagate(False)
        meno = tk.Label(c, text="−", bg=TEND["campo"], fg=TEND["testo"], font=F(11, True), width=2, cursor="hand2"); meno.pack(side="left", fill="y")
        piu = tk.Label(c, text="+", bg=TEND["campo"], fg=TEND["testo"], font=F(11, True), width=2, cursor="hand2"); piu.pack(side="right", fill="y")
        self.var = tk.StringVar(value=str(val))
        self.e = tk.Entry(c, textvariable=self.var, bg=TEND["campo"], fg=TEND["testo"], insertbackground=TEND["testo"], font=F(9), justify="center", bd=0, highlightthickness=0)
        self.e.pack(side="left", fill="both", expand=True)
        self.tasti = (meno, piu)
        meno.bind("<Button-1>", lambda e: None if self.bloccato else self.metti(self.get() - self.passo))
        piu.bind("<Button-1>", lambda e: None if self.bloccato else self.metti(self.get() + self.passo))
        self.e.bind("<Return>", lambda e: None if self.bloccato else self.metti(self.get()))
        self.e.bind("<KeyRelease>", lambda e: self.cb() if self.cb and not self.bloccato else None)       # il conto segue mentre scrivi: cliccare altrove non toglie il fuoco
        self.e.bind("<FocusOut>", lambda e: None if self.bloccato else self.metti(self.get()))

    def col_reset(self, azione):
        """Il pulsantino di reset accanto al riquadro."""
        self.l_reset = self.tk.Label(self.riga, text="↺", bg=self.bg, fg=C["azzurro"], font=self.F(11, True), width=2, cursor="hand2")
        self.l_reset.pack(side="left", padx=(2, 0))
        self.l_reset.bind("<Button-1>", lambda e: None if self.bloccato else azione())

    def get(self):
        try:
            return max(0, min(self.massimo, int(self.var.get().replace(",", "").replace(".", "").strip() or 0)))
        except ValueError:
            return 0

    def metti(self, v, zitto=False):
        self.var.set(str(max(0, min(self.massimo, v))))
        if not zitto and self.cb:
            self.cb()

    def blocca(self, si):
        """Con un obiettivo il numero lo decide il farmer: si legge e non si scrive."""
        self.bloccato = si
        self.e.configure(state="disabled" if si else "normal", disabledbackground=TEND["campo"], disabledforeground=C["azzurro"])
        for t in self.tasti:
            t.configure(fg=TEND["campo"] if si else TEND["testo"], cursor="arrow" if si else "hand2")
        if self.l_reset:
            self.l_reset.configure(fg=self.bg if si else C["azzurro"], cursor="arrow" if si else "hand2")


class Spunte:
    """Una scelta sola fra poche voci, come piccole spunte in fila: sotto ogni voce del calcolatore, come si paga."""

    def __init__(self, tk, padre, voci, F, cb, bg):
        self.voci, self.cb, self.tk, self.val, self.bloccato = voci, cb, tk, voci[0][0], False
        self.fr = tk.Frame(padre, bg=bg); self.cv = {}
        for k, nome in voci:
            r = tk.Frame(self.fr, bg=bg, cursor="hand2"); r.pack(side="left", padx=(0, 1))
            c = tk.Canvas(r, width=11, height=11, bg=bg, highlightthickness=0, cursor="hand2"); c.pack(side="left", padx=(0, 1))
            l = tk.Label(r, text=nome, bg=bg, fg=C["testo"], font=F(7), pady=0, cursor="hand2"); l.pack(side="left")
            self.cv[k] = c
            for w in (r, c, l):
                w.bind("<Button-1>", lambda e, k=k: self.scegli(k))
        self.disegna()

    def disegna(self):
        for k, c in self.cv.items():
            on = k == self.val
            c.delete("all")
            c.create_image(0, 0, image=DG.spunta(11, on, C["azzurro"], TEND["campo"], TEND["bordo"], C["fondo"], raggio=1.5), anchor="nw")

    def get(self):
        return self.val

    def scegli(self, k):
        if self.bloccato:
            return
        self.val = k
        self.disegna()
        if self.cb:
            self.cb()

    def metti(self, k):
        self.val = k if k in self.cv else self.voci[0][0]      # un piano salvato con le buste in gemme torna in oro (9 nov 2026)
        self.disegna()


ARANCIO = ("#c8741f", "#e08a33", "#9a5816")     # normale, sotto il mouse, premuto: le azioni principali di un mazzo (Edit, Add to wishlist; 10 nov 2026)


def pulsante_solido(tk, F, padre, testo, premuto, azione, alto=40, bg="#18181c", colori=None):
    """Un pulsante azzurro pieno, senza sfumature, che si schiarisce al passaggio del mouse (Autore, 6 nov 2026: «i pulsanti non facciamogli la sfumatura ma facciamoli pieni con light hover»;
    dal 5 nov erano sfumati con riflesso). Premuto e' piu' scuro. c.metti(testo, premuto) lo cambia."""
    c = tk.Canvas(padre, height=alto, bg=bg, highlightthickness=0, bd=0, cursor="hand2")
    stato = {"sopra": False, "testo": testo, "premuto": premuto}

    def disegna(e=None):
        c.delete("all"); w = max(c.winfo_width(), 2)
        nor, su, giu = colori or ("#0f86cc", "#2ba3ea", "#0b5f94")
        col = giu if stato["premuto"] else su if stato["sopra"] else nor
        c.create_rectangle(0, 0, w, alto, fill=col, width=0)
        c.create_text(w / 2, alto / 2, text=stato["testo"], fill="#ffffff", font=F(9, True))

    def sopra(v):
        stato["sopra"] = v
        disegna()

    def metti(testo, premuto):
        if (testo, premuto) != (stato["testo"], stato["premuto"]):
            stato.update(testo=testo, premuto=premuto)
            disegna()
    c.metti = metti
    c.bind("<Configure>", disegna); c.bind("<Button-1>", lambda e: azione())
    c.bind("<Enter>", lambda e: sopra(True)); c.bind("<Leave>", lambda e: sopra(False))
    return c
