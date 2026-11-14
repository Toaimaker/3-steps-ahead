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
        # il campo e' una tela sola (11 nov 2026, sessione Magic 13, Note/Motore_Grafico_App.md): il testo, l'icona e la freccia disegnati; prima una cornice,
        # un'etichetta e una tela (le tendine sono una ventina nell'app). self.lab resta per chi mette l'icona (configure(image=, compound=))
        self.larga, self._aperta, self._img = larga, False, None
        self.campo = tk.Canvas(self.fr, bg=TEND["campo"], highlightthickness=1, highlightbackground=TEND["bordo"], width=larga - 2, height=30, bd=0, cursor="hand2")
        self.campo.pack(anchor="w")
        self.vista_var = tk.StringVar(value="")     # quel che si legge nel campo (il nome); self.var tiene il valore (il codice)
        self.vista_var.trace_add("write", lambda *a: self.disegna_campo())
        self.lab = _Etichetta(self)
        self.campo.bind("<Configure>", lambda e: self.disegna_campo())
        self.campo.bind("<Button-1>", lambda e: self.apri())
        self.campo.bind("<Enter>", lambda e: self.campo.configure(highlightbackground=C["grigio"]))
        self.campo.bind("<Leave>", lambda e: self.campo.configure(highlightbackground=TEND["bordo"]))
        self.disegna_campo()

    def disegna_campo(self):
        """Il campo: l'icona se c'e', il testo (tagliato con «…» se non entra), la V a destra."""
        from tkinter import font as tkfont
        c = self.campo
        c.delete("all")
        W = max(c.winfo_width(), int(c.cget("width")) + 2) - 2
        H = int(c.cget("height"))
        x = 12
        if self._img:
            c.create_image(x, H / 2, image=self._img, anchor="w")
            x += self._img.width() + 6
        t = self.vista_var.get().strip()
        f = self.__dict__.get("_font")
        if f is None:
            f = self._font = tkfont.Font(font=self.F(9))
        spazio = W - x - 28
        if t and f.measure(t) > spazio:
            while t and f.measure(t + "…") > spazio:
                t = t[:-1]
            t = t.rstrip() + "…"
        c.create_text(x, H / 2, text=t, anchor="w", fill=TEND["testo"], font=self.F(9))
        c.create_image(W - 26, (H - 30) / 2 + 2.5, image=DG.chevron(25, not self._aperta, TEND["muto"]), anchor="nw")      # la V capovolta a menu aperto

    def freccia(self, aperta):
        self._aperta = aperta
        self.disegna_campo()

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


class _Etichetta:
    """Al posto dell'etichetta del campo di prima: configure(image=, compound=) mette l'icona nel campo disegnato."""

    def __init__(self, t):
        self.t = t

    def configure(self, image=None, compound=None, **k):
        self.t._img = image or None
        self.t.disegna_campo()


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
    """Un numero da scegliere: il nome sopra in maiuscolo bianco, il campo squadrato come la Tendina, − e + ai lati, si puo' anche scrivere. Dall'11 nov 2026
    (sessione Magic 13) una tela sola col titolo, il riquadro, − e +, il reset disegnati, e dentro la sola casella vera: prima 8 widget per numero. Quel che
    sta accanto al riquadro (le spunte di come si paga) entra con accanto()."""

    def __init__(self, tk, padre, nome, F, cb, val=0, passo=1, massimo=999999, larga=126, bg=None):
        from tkinter import font as tkfont
        self.passo, self.massimo, self.cb, self.bloccato = passo, massimo, cb, False
        self.bg, self.F, self.tk = bg or C["fondo"], F, tk
        self.larga, self.reset, self.x_dopo = larga, None, larga
        self.h_tit = tkfont.Font(font=F(7, True)).metrics("linespace")
        self.y0 = self.h_tit + 3                    # il riquadro sotto il titolo
        self.fr = cv = tk.Canvas(padre, bg=self.bg, highlightthickness=0, bd=0, width=larga, height=self.y0 + 32)
        cv.create_text(0, 0, text=nome.upper(), anchor="nw", fill=C["titolo"], font=F(7, True))
        cv.create_rectangle(0, self.y0, larga - 1, self.y0 + 31, fill=TEND["campo"], outline=TEND["bordo"])
        self.lato = tkfont.Font(font=F(11, True)).measure("0") * 2 + 4      # quanto occupavano − e + (width=2)
        self.t_meno = cv.create_text(1 + self.lato / 2, self.y0 + 16, text="−", fill=TEND["testo"], font=F(11, True))
        self.t_piu = cv.create_text(larga - 1 - self.lato / 2, self.y0 + 16, text="+", fill=TEND["testo"], font=F(11, True))
        self.var = tk.StringVar(value=str(val))
        self.e = tk.Entry(cv, textvariable=self.var, bg=TEND["campo"], fg=TEND["testo"], insertbackground=TEND["testo"], font=F(9), justify="center", bd=0, highlightthickness=0)
        cv.create_window(1 + self.lato, self.y0 + 1, window=self.e, anchor="nw", width=larga - 2 - 2 * self.lato, height=30)
        cv.bind("<ButtonPress-1>", lambda e: self.clic(e.x, e.y))
        cv.bind("<Motion>", lambda e: cv.configure(cursor="hand2" if self.zona(e.x, e.y) else ""))
        self.e.bind("<Return>", lambda e: None if self.bloccato else self.metti(self.get()))
        self.e.bind("<KeyRelease>", lambda e: self.cb() if self.cb and not self.bloccato else None)       # il conto segue mentre scrivi: cliccare altrove non toglie il fuoco
        self.e.bind("<FocusOut>", lambda e: None if self.bloccato else self.metti(self.get()))

    def zona(self, x, y):
        """Il pulsante sotto il puntatore: «meno», «piu», «reset» o None (bloccato: nessuno)."""
        if self.bloccato or not self.y0 <= y <= self.y0 + 31:
            return None
        if 0 <= x < 1 + self.lato:
            return "meno"
        if self.larga - 1 - self.lato <= x < self.larga:
            return "piu"
        if self.reset and self.reset[0] <= x < self.reset[1]:
            return "reset"
        return None

    def clic(self, x, y):
        z = self.zona(x, y)
        if z == "meno":
            self.metti(self.get() - self.passo)
        elif z == "piu":
            self.metti(self.get() + self.passo)
        elif z == "reset":
            self.reset[2]()

    def col_reset(self, azione):
        """Il pulsantino di reset accanto al riquadro."""
        from tkinter import font as tkfont
        L = tkfont.Font(font=self.F(11, True)).measure("0") * 2 + 4
        x0 = self.x_dopo + 2
        self.t_reset = self.fr.create_text(x0 + L / 2, self.y0 + 16, text="↺", fill=C["azzurro"], font=self.F(11, True))
        self.reset = (x0, x0 + L, azione)
        self.x_dopo = x0 + L
        self.fr.configure(width=self.x_dopo)

    def accanto(self, w, padx=6):
        """Un widget accanto al riquadro, centrato in altezza (le spunte di come si paga): sulla tela, non in un'altra riga."""
        w.update_idletasks()
        x0 = self.x_dopo + padx
        self.fr.create_window(x0, self.y0 + 16, window=w, anchor="w")
        self.x_dopo = x0 + w.winfo_reqwidth()
        self.fr.configure(width=self.x_dopo)

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
        for t in (self.t_meno, self.t_piu):
            self.fr.itemconfigure(t, fill=TEND["campo"] if si else TEND["testo"])
        if self.reset:
            self.fr.itemconfigure(self.t_reset, fill=self.bg if si else C["azzurro"])
        if si:
            self.fr.configure(cursor="")


class Spunte:
    """Una scelta sola fra poche voci, come piccole spunte in fila: sotto ogni voce del calcolatore, come si paga. Dall'11 nov 2026 (sessione Magic 13) una tela
    sola per tutte le voci, non tre widget per voce: il clic sceglie la voce sotto il puntatore. self.fr e' la tela."""

    def __init__(self, tk, padre, voci, F, cb, bg):
        from tkinter import font as tkfont
        self.voci, self.cb, self.tk, self.val, self.bloccato = voci, cb, tk, voci[0][0], False
        self.F, self.bg = F, bg
        f = tkfont.Font(font=F(7))
        self.alto = max(13, f.metrics("linespace"))
        self.zone, x = [], 0
        for k, nome in voci:
            L = 11 + 1 + f.measure(nome) + 2
            self.zone.append((x, x + L, k, nome))
            x += L + 1
        self.fr = tk.Canvas(padre, width=max(1, x - 1), height=self.alto, bg=bg, highlightthickness=0, cursor="hand2")
        self.fr.bind("<Button-1>", lambda e: self.clic(e.x))
        self.cv = {k: None for k, _n in voci}       # le voci che ci sono (metti lo legge)
        self.disegna()

    def clic(self, x):
        for x0, x1, k, _n in self.zone:
            if x0 <= x < x1:
                self.scegli(k)
                return

    def disegna(self):
        c, H = self.fr, self.alto
        c.delete("all")
        for x0, _x1, k, nome in self.zone:
            on = k == self.val
            c.create_image(x0, (H - 11) // 2, image=DG.spunta(11, on, C["azzurro"], TEND["campo"], TEND["bordo"], C["fondo"], raggio=1.5), anchor="nw")
            c.create_text(x0 + 12, H / 2, text=nome, anchor="w", fill=C["testo"], font=self.F(7))

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


def pronta_poi(f):
    """Una finestra nuova nascosta finche' chi la crea non l'ha riempita: si mostra al primo momento libero del ciclo di Tk, a contenuto fatto, e non compare
    vuota per poi riempirsi a pezzi (11 nov 2026, sessione Magic 13). Si chiama subito dopo il Toplevel."""
    f.withdraw()

    def mostra():
        try:
            if f.winfo_exists():
                f.update_idletasks()
                f.deiconify()
        except Exception:
            pass
    f.after_idle(mostra)
    return f


def a_riposo(w, f, ms=100):
    """Il gestore di <Configure> di un disegno pesante (i grafici, con l'antialias di PIL): la prima volta subito, poi una volta sola quando la misura smette di
    cambiare da ms (11 nov 2026, sessione Magic 13): trascinando il bordo della finestra Windows manda decine di <Configure> al secondo e ognuno rifaceva il
    grafico, 0,1-0,2 s l'uno. Note/Motore_Grafico_App.md."""
    stato = {"id": None, "fatto": False}

    def poi():
        stato["id"] = None
        f(None)

    def gestore(e=None):
        if not stato["fatto"]:
            stato["fatto"] = True
            f(e)
            return
        if stato["id"] is not None:
            try:
                w.after_cancel(stato["id"])
            except Exception:
                pass
        stato["id"] = w.after(ms, poi)
    return gestore


ROSSO_P = ("#b8433f", "#d9534f", "#8e322f")     # normale, sotto il mouse, premuto: le azioni che tolgono qualcosa (Delete; 12 nov 2026)
# Save sempre verde, in tutta l'app (13 nov 2026, Autore: «save ovunque sull'app sempre verde»): il builder, il Board, la domanda «Save the changes?», Save as
# my filter, Save file, le note e i gruppi. Il verde e' piu' scuro del verde dei dati (#5cb85c) perche' il testo bianco si legga: 4,5 sul normale
VERDE_P = ("#2b8541", "#35a04f", "#216632")      # normale, sotto il mouse, premuto


def conferma(tk, F, padre, titolo, testo, si, fa, colori=ROSSO_P, altro=None):
    """Una domanda prima di un'azione che non si torna indietro (Autore, 12 nov 2026: «quando premiamo delete sui cestini in your deck chiediamo sempre
    prima la conferma di voler cancellare il mazzo»): una finestrella nei colori dell'app al centro della finestra di padre, col titolo, il testo, il pulsante
    dell'azione (rosso) e Cancel. Invio conferma, Esc o Cancel annullano; finche' e' aperta il resto della finestra non prende clic. altro: (testo, azione) un
    terzo pulsante fra i due (Don't save, quando si chiude con modifiche non salvate). -> la finestrella, con .si(), .no() e .altro() (anche per le prove)."""
    radice = padre.winfo_toplevel()
    f = tk.Toplevel(radice); f.overrideredirect(True); f.configure(bg="#24baff")
    try:
        f.transient(radice)
    except tk.TclError:
        pass
    dentro = tk.Frame(f, bg="#202024"); dentro.pack(padx=1, pady=1)
    tk.Label(dentro, text=titolo, bg="#202024", fg="#ffffff", font=F(11, True), anchor="w").pack(fill="x", padx=18, pady=(16, 4))
    tk.Label(dentro, text=testo, bg="#202024", fg="#bebec2", font=F(9), anchor="w", justify="left", wraplength=360).pack(fill="x", padx=18, pady=(0, 14))
    riga = tk.Frame(dentro, bg="#202024"); riga.pack(fill="x", padx=18, pady=(0, 16))
    fatto = {"v": False}

    def chiudi():
        try:
            f.grab_release()
        except tk.TclError:
            pass
        if f.winfo_exists():
            f.destroy()

    def ok(_e=None):
        if fatto["v"]:
            return
        fatto["v"] = True
        chiudi()
        fa()

    def no(_e=None):
        fatto["v"] = True
        chiudi()
    b_no = pulsante_solido(tk, F, riga, "Cancel", False, no, alto=32, bg="#202024", colori=("#3a3a40", "#4a4a52", "#2c2c30"))
    b_no.configure(width=110); b_no.pack(side="right")

    def terzo(_e=None):
        if fatto["v"]:
            return
        fatto["v"] = True
        chiudi()
        altro[1]()
    if altro:
        b_al = pulsante_solido(tk, F, riga, altro[0], False, terzo, alto=32, bg="#202024", colori=("#3a3a40", "#4a4a52", "#2c2c30"))
        b_al.configure(width=110); b_al.pack(side="right", padx=(0, 8))
    b_si = pulsante_solido(tk, F, riga, si, False, ok, alto=32, bg="#202024", colori=colori)
    b_si.configure(width=110); b_si.pack(side="right", padx=(0, 8))
    f.bind("<Return>", ok); f.bind("<Escape>", no)
    f.update_idletasks()
    x = radice.winfo_rootx() + (radice.winfo_width() - f.winfo_reqwidth()) // 2
    y = radice.winfo_rooty() + (radice.winfo_height() - f.winfo_reqheight()) // 3
    f.geometry(f"+{x}+{y}")
    import piattaforma
    piattaforma.sopra_di(f, radice)     # sempre sopra la sua finestra: senza, un clic dietro la copriva e lei, col grab, lasciava l'app ferma (13 nov 2026)
    try:
        f.grab_set()
    except tk.TclError:       # un'altra finestra tiene gia' il mouse: la domanda resta lo stesso
        pass
    f.focus_force()
    f.si, f.no, f.altro = ok, no, terzo
    return f


def _hex(c):
    c = c.lstrip("#")
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))


def _mischia(c, verso, t):
    """c verso il colore verso per la frazione t (0 = c)."""
    a, b = _hex(c), _hex(verso)
    return "#%02x%02x%02x" % tuple(round(x + (y - x) * t) for x, y in zip(a, b))


def saturo(c):
    """Lo stesso colore piu' saturo e piu' acceso: la luce del blocco icona (stile S3, 14 nov 2026). Un grigio resta quasi grigio."""
    import colorsys
    h, s, v = colorsys.rgb_to_hsv(*(x / 255 for x in _hex(c)))
    r, g, b = colorsys.hsv_to_rgb(h, min(1.0, s * 1.5), min(1.0, v * 1.12))
    return "#%02x%02x%02x" % (round(r * 255), round(g * 255), round(b * 255))


RAGGIO_P = 4            # gli angoli dei pulsanti
_SFONDI = {}            # le immagini dei pulsanti, per misura, colori e stato (si rifanno al passaggio del mouse: costano una volta sola)


def _sfondo(w, h, sopra_, sotto_, linea, blocco=0, b_sopra=None, b_sotto=None):
    """Il pulsante come immagine: la luce dall'alto (sopra_ in cima, sotto_ in fondo), il filo chiaro in cima (linea: alfa 0-255), il blocco icona largo blocco
    a sinistra coi suoi colori e il filo che lo separa, gli angoli arrotondati con l'antialias. -> PhotoImage, in cache."""
    chiave = (w, h, sopra_, sotto_, linea, blocco, b_sopra, b_sotto)
    if chiave in _SFONDI:
        return _SFONDI[chiave]
    from PIL import Image, ImageDraw, ImageTk

    def rampa(l, a, b):
        col = Image.new("RGBA", (1, h))
        ca, cb = _hex(a), _hex(b)
        col.putdata([tuple(round(x + (y - x) * (j / max(1, h - 1))) for x, y in zip(ca, cb)) + (255,) for j in range(h)])
        return col.resize((l, h), Image.NEAREST)
    im = rampa(w, sopra_, sotto_)
    if blocco:
        im.paste(rampa(blocco, b_sopra, b_sotto), (0, 0))
        im.alpha_composite(Image.new("RGBA", (1, h), (255, 255, 255, 34)), (blocco - 1, 0))
    im.alpha_composite(Image.new("RGBA", (w, 1), (255, 255, 255, linea)), (0, 0))
    s = 4
    maschera = Image.new("L", (w * s, h * s), 0)
    ImageDraw.Draw(maschera).rounded_rectangle((0, 0, w * s - 1, h * s - 1), radius=RAGGIO_P * s, fill=255)
    im.putalpha(maschera.resize((w, h), Image.LANCZOS))
    if len(_SFONDI) > 600:      # via il piu' vecchio: chi lo mostra ancora lo tiene vivo nella sua tela (c._s3)
        _SFONDI.pop(next(iter(_SFONDI)))
    _SFONDI[chiave] = ImageTk.PhotoImage(im)
    return _SFONDI[chiave]


def disegna_s3(c, x0, y0, x1, y1, testo, font, colori=None, sopra=False, premuto=False, icona=None, tags=(), scritta="#ffffff"):
    """Un pulsante stile S3 disegnato su una tela che c'e' gia' (le tele della Performance, le schede dei mazzi, il pulsante della versione...): lo stesso
    disegno di pulsante_solido, nel riquadro (x0, y0, x1, y1). colori (normale, sotto il mouse, premuto); icona None dal testo, False nessuna, o un nome di
    icone_pulsanti. Le immagini restano vive nella tela (c._s3). -> la larghezza del blocco icona (0 senza)."""
    import icone_pulsanti as IP
    x0, y0, x1, y1 = (int(round(v)) for v in (x0, y0, x1, y1))
    w, alto = max(2, x1 - x0), max(2, y1 - y0)
    nor, su, giu = colori or ("#0f86cc", "#2ba3ea", "#0b5f94")
    if premuto:        # scelto o abbassato: la luce parte poco sopra il colore del premuto
        sopra_, sotto_, linea = _mischia(giu, "#ffffff", 0.14), giu, 60
    elif sopra:
        sopra_, sotto_, linea = _mischia(su, "#ffffff", 0.15), su, 110
    else:
        sopra_, sotto_, linea = su, nor, 85
    nome = IP.per_testo(testo) if icona is None else (icona or None)
    blocco, lato = 0, 0
    if nome:
        blocco = alto + (6 if sopra else 0)
        lato = max(10, round(alto * 0.47)) + (2 if sopra else 0)
        try:
            largo_testo = int((c.tk if hasattr(c, "tk") else c.cv.tk).call("font", "measure", font, testo))      # una CartaTela misura sulla sua tela
        except Exception:       # noqa: BLE001
            largo_testo = 7 * len(testo)
        if w < alto + 6 + largo_testo + 16:     # non ci stanno tutti e due: resta la scritta
            nome, blocco = None, 0
    if blocco:
        s_ = saturo(su)
        b_sopra, b_sotto = (_mischia(s_, "#ffffff", 0.15), s_) if sopra else (sopra_, sotto_)
    else:
        b_sopra = b_sotto = None
    tags = tuple(tags) if not isinstance(tags, str) else (tags,)
    fondo = c.create_rectangle(x0 + 2, y0 + 2, x1 - 2, y1 - 2, fill=giu if premuto else nor, width=0, tags=tags + ("s3_fondo",))      # il colore pieno, sotto
    refs = c.__dict__.setdefault("_s3", [])
    try:
        f_ = _sfondo(w, alto, sopra_, sotto_, linea, blocco, b_sopra, b_sotto)
        refs.append(f_)
        c.create_image(x0, y0, image=f_, anchor="nw", tags=tags)
        if nome:
            ic = IP.icona(nome, lato)
            refs.append(ic)
            c.create_image(x0 + blocco / 2, y0 + alto / 2, image=ic, tags=tags)
    except Exception:       # noqa: BLE001 - senza PIL resta il colore pieno, come prima del 14 nov
        try:
            c.coords(fondo, x0, y0, x1, y1)
        except Exception:       # noqa: BLE001
            pass
        blocco = 0
    if len(refs) > 300:
        del refs[:len(refs) - 300]
    c.create_text(x0 + blocco + (w - blocco) / 2, y0 + alto / 2, text=testo, fill=scritta, font=font, tags=tags + ("testo",))
    return blocco


def pulsante_solido(tk, F, padre, testo, premuto, azione, alto=40, bg="#18181c", colori=None, icona=None):
    """Il pulsante dell'app, stile S3 (Autore, 14 nov 2026: «monta S3 su tutta l'app», scelto fra cinque stili e le loro varianti; poi «ogni pulsante
    esistente deve avere il redesign in linea con lo stile»): satinato, la luce dall'alto che scende fino al colore e mai sotto (niente rampa scura: «è sempre
    luce nera»), un filo chiaro in cima, gli angoli tondi. A sinistra il blocco icona: da fermo come la scritta, sotto il mouse si allarga e si accende del
    colore del pulsante piu' saturo («usa una luce del colore del pulsante ma più satura»), l'icona cresce di due pixel. Fino al 13 nov 2026 era un rettangolo
    pieno che si schiariva (6 nov: «pieni con light hover»). Su una tela che c'e' gia' lo stesso disegno lo fa disegna_s3.
    colori: (normale, sotto il mouse, premuto); premuto e' lo stato scelto (le linguette: GRIGI ha l'azzurro) o abbassato. icona: None la sceglie dal testo
    (icone_pulsanti.per_testo), False nessuna, un nome di icone_pulsanti.NOMI quella. Il pulsante che non e' largo abbastanza per testo e icona perde l'icona.
    c.metti(testo, premuto) lo cambia; c.colori dice i suoi colori (per le prove)."""
    import icone_pulsanti as IP
    c = tk.Canvas(padre, height=alto, bg=bg, highlightthickness=0, bd=0, cursor="hand2")
    stato = {"sopra": False, "testo": testo, "premuto": premuto, "icona": IP.per_testo(testo) if icona is None else (icona or None), "spento": False}
    c.colori = colori or ("#0f86cc", "#2ba3ea", "#0b5f94")

    def disegna(e=None):
        c.delete("all"); c._s3 = []
        disegna_s3(c, 0, 0, max(c.winfo_width(), 2), alto, stato["testo"], F(9, True), c.colori, stato["sopra"] and not stato["spento"], stato["premuto"],
                   stato["icona"] or False, scritta="#6c6c74" if stato["spento"] else "#ffffff")

    def spegni(v):
        """Spento (Undo senza niente da annullare): la scritta grigia, niente luce sotto il mouse. Il clic arriva lo stesso: decide chi lo riceve."""
        if bool(v) != stato["spento"]:
            stato["spento"] = bool(v)
            disegna()
    c.spegni = spegni
    c.testo = lambda: stato["testo"]

    def sopra(v):
        stato["sopra"] = v
        disegna()

    def metti(testo, premuto):
        if (testo, premuto) != (stato["testo"], stato["premuto"]):
            if icona is None:       # un testo di passaggio («Saved», «Click again to confirm») tiene l'icona di prima
                stato["icona"] = IP.per_testo(testo) or stato["icona"]
            stato.update(testo=testo, premuto=premuto)
            disegna()
    c.metti = metti
    c.bind("<Configure>", disegna); c.bind("<Button-1>", lambda e: azione())
    c.bind("<Enter>", lambda e: sopra(True)); c.bind("<Leave>", lambda e: sopra(False))
    return c


def smonta(w, quanti=25, prima=250):
    """Distrugge w un pezzo alla volta, quando la finestra e' libera: dopo prima ms, le foglie per prime a gruppi di quanti, poi w. Un widget gia' distrutto si
    salta. Fino all'11 nov 2026 il primo gruppo partiva subito e il primo figlio si portava dietro tutto il contenuto (~100 widget, 30 ms dentro il clic che
    apriva il mazzo nuovo)."""
    def foglie(x):
        try:
            figli = x.winfo_children()
        except Exception:
            return []
        return [y for f in figli for y in foglie(f)] + [x]

    def giro(resto):
        n = 0
        while resto and n < quanti:
            x = resto.pop(0)
            try:
                if x.winfo_exists():
                    x.destroy(); n += 1
            except Exception:
                pass
        if resto:
            try:
                resto[-1].after(15, lambda: giro(resto))
            except Exception:       # la radice non c'e' piu': i pezzi sono gia' andati con lei
                pass
    try:
        w.via = True        # segnato: chi scorre i widget (le prove) sa che sta per andarsene
        if w.winfo_exists():
            w.after(prima, lambda: giro(foglie(w)))
    except Exception:
        pass


def svuota(contenitore):
    """Toglie subito dalla vista i figli di contenitore e li distrugge dopo, a pezzi (11 nov 2026): distruggere 50 widget costava ~50 ms dentro il clic
    che rifa' il contenuto (il builder a ogni carta)."""
    for x in contenitore.winfo_children():
        try:
            m = x.winfo_manager()
            if m == "pack":
                x.pack_forget()
            elif m == "grid":
                x.grid_forget()
            elif m == "place":
                x.place_forget()
            smonta(x)
        except Exception:
            pass


class PulsanteVista:
    """Il pulsante che passa fra due viste (la Meta, 11 nov 2026, Autore: «la view da decks a charts non deve essere una tendina ma un pulsante da premere
    che cambia forma da charts a grid e lo mettiamo sulla destra nello stesso spazio delle tendine»): dice la vista in cui porta, con la sua icona disegnata
    (Charts con le barre, Grid coi riquadri). Come una Tendina per chi lo usa: .fr, get() (la vista di adesso), set(v), opzioni(viste, cb). Alto come il
    campo di una Tendina, con lo spazio del nome sopra, cosi' sta in riga."""

    def __init__(self, tk, padre, F, viste=("Decks", "Charts"), etichette=None, bg=None, larga=128):
        self.F, self.viste, self.cb = F, list(viste), None
        self.etichette = etichette or {"Decks": ("Charts", "barre"), "Charts": ("Grid", "griglia")}       # vista di adesso -> (cosa dice, icona)
        bg = bg or C["fondo"]
        self.fr = tk.Frame(padre, bg=bg)
        tk.Label(self.fr, text="VIEW", bg=bg, fg=C["titolo"], font=F(7, True), pady=0).pack(anchor="w", pady=(0, 3))
        self.c = tk.Canvas(self.fr, bg=bg, highlightthickness=0, width=larga, height=32, bd=0, cursor="hand2")
        self.c.pack(anchor="w")
        self.v, self.sopra = self.viste[0], False
        self.c.bind("<Button-1>", lambda e: self.premi())
        self.c.bind("<Enter>", lambda e: self._sopra(True)); self.c.bind("<Leave>", lambda e: self._sopra(False))
        self.c.bind("<Configure>", lambda e: self.disegna())
        self.disegna()

    def _sopra(self, v):
        self.sopra = v
        self.disegna()

    def disegna(self):
        """Stile S3 (14 nov 2026), col blocco icona: le barre per Charts, i riquadri per Grid."""
        c = self.c
        c.delete("all"); c._s3 = []
        w, h = max(c.winfo_width(), int(c.cget("width"))), int(c.cget("height"))
        testo, icona = self.etichette.get(self.v, (self.v, "griglia"))
        disegna_s3(c, 0, 0, w, h, testo, self.F(9, True), sopra=self.sopra, icona="barre" if icona == "barre" else "griglia")
        self.testo = testo

    def opzioni(self, viste, cb):
        self.viste, self.cb = list(viste), cb

    def get(self):
        return self.v

    def set(self, v):
        if v in self.viste:
            self.v = v
            self.disegna()

    def premi(self):
        """Passa all'altra vista e lo dice a chi ascolta."""
        i = self.viste.index(self.v) if self.v in self.viste else 0
        self.set(self.viste[(i + 1) % len(self.viste)])
        if self.cb:
            self.cb(self.v)
