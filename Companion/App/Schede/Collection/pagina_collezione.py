"""La scheda Collection: le carte a figura piena o in lista, la ricerca, Settings, il trascinamento nel builder."""
import os

import capsule as CAP
import carta_tela
import collezione_carte as CC
import disegni as DG
import mazzi_salvati as MS
import prezzi_carte as PZ
import risorse as RS

from finestra_mazzo import FinestraMazzo
from icone import icona_set, nome_set
from pagina_base import Pagina, prepara_capsule
from tema import CI as C, TEND
from widget import Scelte, Tendina, pulsante_solido

import account as _ACC
OPZIONI = ""
_ACC.lega(globals(), "OPZIONI", "collezione_opzioni.json")      # le scelte di come si vede la Collection (il retino), per l'account


def leggi_opzioni():
    import json
    try:
        with open(OPZIONI, encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def salva_opzioni(d):
    import json
    try:
        os.makedirs(os.path.dirname(OPZIONI), exist_ok=True)
        with open(OPZIONI + ".tmp", "w", encoding="utf-8") as f:
            json.dump(d, f)
        os.replace(OPZIONI + ".tmp", OPZIONI)
    except OSError:
        pass


class PaginaCollezione(Pagina):
    """La collezione: in cima la ricerca, sotto le carte in una pagina sola che scorre. Dati da collezione_carte.py. Le carte si vedono a figura piena (Autore, 5 nov 2026:
    «ma se mostrassimo direttamente le carte a figura piena?»), o come le capsule dei mazzi con la tendina View. I filtri stanno in un pannello nascosto che si apre dal pulsante
    Settings, coi set da flaggare (stesso giorno: «ricreiamolo in un menu nascosto che si richiama da un pulsante settings in modo che possiamo incrociare anche le espansioni»).
    Scorre tutto in una pagina (stesso giorno: «possiamo tenere tutto in una stessa pagina scrollabile invece dei pulsanti next e prev?»): esistono solo le carte a vista, piu' una riga
    sopra e una sotto. Scorrendo si fanno le nuove e si tolgono le altre: 3.300 tele con la loro immagine sarebbero 700 MB."""

    ALTO_SET = 28
    COL_RARITA = dict(M="#f0ad4e", R="#e6c65c", U="#9fb4c8", C="#a7a9ad", L="#707074")

    def __init__(self, tk, padre, F, mana):
        super().__init__(tk, padre, F, mana)
        self.esp.fr.pack_forget()
        self.col[1].grid_remove(); self.col[0].grid(row=2, column=0, columnspan=2, sticky="nsew", padx=0)
        self.d, self.trovate, self.timer, self.sporco, self.colonne, self.largo = None, [], None, False, 0, 0
        self.viste, self.vedi_atteso = {}, False
        self.sets_on, self.sets_lista, self.spunte_set, self.aperto = set(), None, {}, False
        self.lista = CAP.Liste(tk, F)
        self.lista.dati_hover = False       # qui l'hover e' la sola carta (Autore, 5 nov 2026: «si', togli anche quelli»)
        fondo = C["scheda"]
        # in cima solo la ricerca e il pulsante Settings
        PaginaCollezione.ISTANZA = self
        self.drag = None
        self.b_set = pulsante_solido(tk, F, self.barra_menu, "Settings", False, lambda: self.pannello(), alto=34, bg=C["fondo"])
        self.b_set.configure(width=150); self.b_set.pack(side="right", anchor="s", padx=(10, 0))
        # il builder si apre da qui, sopra le carte (Autore, 7 nov 2026: «facciamo che il deck builder è una finestra che si apre dalla sezione collection»)
        self.b_bld = pulsante_solido(tk, F, self.barra_menu, "Deck builder", False, self.apri_builder, alto=34, bg=C["fondo"])
        self.b_bld.configure(width=150); self.b_bld.pack(side="right", anchor="s", padx=(10, 0))
        f = tk.Frame(self.barra_menu, bg=C["fondo"]); f.pack(side="left", fill="x", expand=True)
        tk.Label(f, text="NAME, TYPE OR CARD TEXT", bg=C["fondo"], fg=C["titolo"], font=F(7, True), pady=0).pack(anchor="w", pady=(0, 3))
        c = tk.Frame(f, bg=TEND["campo"], highlightthickness=1, highlightbackground=TEND["bordo"], height=32); c.pack(fill="x"); c.pack_propagate(False)
        self.v_testo = tk.StringVar()
        self.e = tk.Entry(c, textvariable=self.v_testo, bg=TEND["campo"], fg=TEND["testo"], insertbackground=TEND["testo"], font=F(9), bd=0, highlightthickness=0)
        self.e.pack(fill="both", expand=True, padx=8)
        self.v_testo.trace_add("write", lambda *a: self.chiedi())
        # il pannello nascosto: sta sopra le carte e si apre dal pulsante
        self.pan = tk.Frame(self.fr, bg=C["accento"], padx=1, pady=1)
        dentro = tk.Frame(self.pan, bg=fondo); dentro.pack(fill="both", expand=True)
        cap = tk.Frame(dentro, bg=C["cap"]); cap.pack(fill="x")
        tk.Label(cap, text="SETTINGS", bg=C["cap"], fg=C["capo"], font=F(8, True)).pack(side="left", padx=10, pady=5)
        via = tk.Label(cap, text="\u2715", bg=C["cap"], fg=C["testo"], font=F(9, True), padx=10, cursor="hand2"); via.pack(side="right")
        via.bind("<Button-1>", lambda e: self.pannello(False))
        tk.Frame(dentro, bg=C["filo"], height=1).pack(fill="x")
        corpo = tk.Frame(dentro, bg=fondo); corpo.pack(fill="both", expand=True, padx=12, pady=10)
        corpo.columnconfigure(1, weight=1); corpo.rowconfigure(0, weight=1)
        b = tk.Frame(corpo, bg=fondo); b.grid(row=0, column=0, sticky="n", padx=(0, 16))
        # due flag, non una tendina (Autore, 7 nov 2026: «owned e non owned devono essere semplicemente due flag fuori da quella tendina»): nessuno acceso o tutti e due vuol dire tutte le carte
        self.s_mostra = Scelte(tk, b, "Show", (("O", "Owned"), ("N", "Not owned")), F, self.chiedi, fondo, colonne=2); self.s_mostra.fr.pack(fill="x", pady=(0, 8))
        # il retino sulle carte che non hai (Autore, 11 nov 2026: «con spunta in settings per attivare il retino su non owned»): acceso di partenza, si ricorda
        # per l'account (OPZIONI); Clear all non lo tocca, e' come si vede, non un filtro
        self.s_retino = Scelte(tk, b, "Not owned cards", (("R", "Pattern on not owned"),), F, self.cambia_retino, fondo, colonne=1); self.s_retino.fr.pack(fill="x", pady=(0, 8))
        CAP.RETINO_ACCESO[0] = leggi_opzioni().get("retino", True)
        if CAP.RETINO_ACCESO[0]:
            self.s_retino.on = {"R"}; self.s_retino.disegna()
        r = tk.Frame(b, bg=fondo); r.pack(fill="x", pady=(0, 8))
        self.t_formato = Tendina(tk, r, "Format", F, larga=150, bg=fondo); self.t_formato.fr.pack(side="left")
        # tutti i formati di Arena (Autore, 9 nov 2026: «nella collection aggiungi il filtro per i formati standard historic ecc»); prima c'erano solo All e Standard
        self.t_formato.opzioni(self.FORMATI_COLL, lambda o: self.chiedi()); self.t_formato.set("All")
        self.t_copie = Tendina(tk, r, "Copies owned", F, larga=150, bg=fondo); self.t_copie.fr.pack(side="right")
        self.t_copie.opzioni(CC.COPIE, lambda o: self.chiedi()); self.t_copie.set("Any")
        # la legalita' nel formato scelto (Autore, 10 nov 2026: «in collection nei settings metti un ulteriore filtro per formato standard ecc e colora di rosso le carte
        # bannate per ogni relativo formato»): due flag come Show, nessuno o tutti e due vuol dire tutte; con All non conta
        self.s_legale = Scelte(tk, b, "Legality in the format", (("L", "Legal"), ("B", "Banned")), F, self.chiedi, fondo, colonne=2); self.s_legale.fr.pack(fill="x", pady=(0, 8))
        self.s_colori = Scelte(tk, b, "Colors", [(k, k) for k in "WUBRGC"], F, self.chiedi, fondo, colonne=6, immagini=dict(mana, C=self.lista.simbolo("C", 16))); self.s_colori.fr.pack(fill="x", pady=(0, 4))
        self.t_modo = Tendina(tk, b, "Color match", F, larga=320, bg=fondo); self.t_modo.fr.pack(anchor="w", pady=(0, 8))
        self.t_modo.opzioni(CC.MODI, lambda o: self.chiedi()); self.t_modo.set(CC.MODI[0])
        self.s_rarita = Scelte(tk, b, "Rarity", (("M", "Mythic"), ("R", "Rare"), ("U", "Uncommon"), ("C", "Common")), F, self.chiedi, fondo, colonne=4); self.s_rarita.fr.pack(fill="x", pady=(0, 6))
        self.s_tipi = Scelte(tk, b, "Type", [(t, t) for t in CC.TIPI], F, self.chiedi, fondo, colonne=3); self.s_tipi.fr.pack(fill="x", pady=(0, 6))
        self.s_costi = Scelte(tk, b, "Mana value", [(i, "7+" if i == 7 else str(i)) for i in range(8)], F, self.chiedi, fondo, colonne=8); self.s_costi.fr.pack(fill="x", pady=(0, 6))
        r = tk.Frame(b, bg=fondo); r.pack(fill="x", pady=(0, 8))
        self.t_ordine = Tendina(tk, r, "Sort by", F, larga=150, bg=fondo); self.t_ordine.fr.pack(side="left")
        self.t_ordine.opzioni(CC.ORDINI, lambda o: self.chiedi()); self.t_ordine.set("Color")
        self.t_vista = Tendina(tk, r, "View", F, larga=150, bg=fondo); self.t_vista.fr.pack(side="right")
        self.t_vista.opzioni(("Cards", "List"), lambda o: self.cambia_vista()); self.t_vista.set("Cards")
        azzera = pulsante_solido(tk, F, b, "Clear all", False, lambda: self.azzera(), alto=30, bg=fondo, colori=("#3a3a40", "#4a4a52", "#2c2c30"))      # stile S3 (14 nov 2026)
        azzera.pack(fill="x")
        # i set, da flaggare: piu' d'uno si incrociano
        ds = tk.Frame(corpo, bg=fondo); ds.grid(row=0, column=1, sticky="nsew")
        t = tk.Frame(ds, bg=fondo); t.pack(fill="x", pady=(0, 3))
        self.v_sets = tk.StringVar(value="SETS")
        tk.Label(t, textvariable=self.v_sets, bg=fondo, fg=C["titolo"], font=F(7, True), pady=0).pack(side="left")
        togli = tk.Label(t, text="CLEAR", bg=fondo, fg=C["accento"], font=F(7, True), pady=0, cursor="hand2"); togli.pack(side="right")
        togli.bind("<Button-1>", lambda e: self.togli_sets())
        qs = tk.Frame(ds, bg=TEND["bordo"], padx=1, pady=1); qs.pack(fill="both", expand=True)
        self.cv_sets = cs = tk.Canvas(qs, bg=TEND["campo"], highlightthickness=0, height=1, width=1); cs.pack(fill="both", expand=True)
        cs.configure(cursor="hand2")
        cs.bind("<Configure>", lambda e: [cs.coords(i, e.width - 10, cs.coords(i)[1]) for i in cs.find_withtag("conti")])
        cs.bind("<Button-1>", self.clic_set)
        def rotella_sets(e):
            if e.widget == cs:
                cs.yview_scroll(-3 if e.delta > 0 else 3, "units")
        cs.bind_all("<MouseWheel>", rotella_sets, add="+")
        cima = self.fr.winfo_toplevel()
        cima.bind("<Button-1>", self.fuori, add="+")
        cima.bind("<Escape>", lambda e: self.pannello(False), add="+")
        self.fr.bind("<Configure>", lambda e: self.metti_pannello() if self.aperto else None, add="+")
        b_car, _ = self.scheda("Cards", espandi=True)
        self.titolo_carte = self.cap_tit
        barra = tk.Canvas(b_car, width=8, bg=C["traccia"], highlightthickness=0, cursor="hand2"); barra.pack(side="right", fill="y", padx=(6, 0))
        def segna(a, b_):
            barra.delete("all"); a, b_ = float(a), float(b_)
            if b_ - a < 0.999:
                H_ = barra.winfo_height(); barra.create_rectangle(0, H_ * a, 8, max(H_ * b_, H_ * a + 24), fill=C["grigio"], width=0)
            self.chiedi_vedi()
        self.cv = cv = tk.Canvas(b_car, bg=fondo, highlightthickness=0, yscrollcommand=segna); cv.pack(side="left", fill="both", expand=True)
        # le carte a figura piena si disegnano su questa tela, non in una tela ciascuna: lo smistatore passa gli eventi alla carta sotto il puntatore (11 nov 2026)
        self.smista = carta_tela.Smistatore(cv)
        cv.bind("<Configure>", lambda e: self.adatta(e.width))
        def trascina(e):
            a, b_ = cv.yview()
            cv.yview_moveto(e.y / max(barra.winfo_height(), 1) - (b_ - a) / 2)
        barra.bind("<Button-1>", trascina); barra.bind("<B1-Motion>", trascina)
        def rotella(e):
            if str(e.widget).startswith(str(cv)):
                cv.yview_scroll(-3 if e.delta > 0 else 3, "units")
        cv.bind_all("<MouseWheel>", rotella, add="+")
        self.da_cercare = False
        self.al_davanti(lambda e: self.cerca() if self.da_cercare else (self.disegna() if self.sporco else self.chiedi_vedi()))      # dietro, le carte a vista non si fanno

    def alto_riga(self):
        return CAP.ALTA_CARTA + CAP.SOTTO_CARTA + 8 if self.t_vista.get() == "Cards" else CAP.ALTO + 2

    # ------------------------------------------------ verso il builder: trascinare una carta, o doppio clic
    def apri_builder(self):
        import account
        if account.sola_lettura():      # All accounts: i mazzi si guardano e basta (10 nov 2026, Magic 12)
            self.b_bld.metti("Choose an account first", True)
            self.b_bld.after(2500, lambda: self.b_bld.winfo_exists() and self.b_bld.metti("Deck builder", False))
            return None
        import costruttore_mazzi
        aperto = costruttore_mazzi.Costruttore.APERTO
        if aperto is not None and aperto.w.winfo_exists():
            aperto.w.lift(); return aperto
        return FinestraMazzo.MAZZI.builder("build") if FinestraMazzo.MAZZI else None

    def builder_aperto(self):
        import costruttore_mazzi
        b = costruttore_mazzi.Costruttore.APERTO
        return b if b is not None and b.w.winfo_exists() else None

    def lega_trascina(self, w, nome):
        w.bind("<ButtonPress-1>", lambda e: self.prendi(e, nome), add="+")
        w.bind("<B1-Motion>", self.muovi, add="+")
        w.bind("<ButtonRelease-1>", self.lascia, add="+")
        w.bind("<Double-Button-1>", lambda e: self.al_builder(nome), add="+")

    def al_builder(self, nome):
        b = self.builder_aperto()
        if b is not None:
            b.metti(nome, 1)

    def prendi(self, e, nome):
        self.drag = dict(nome=nome, x=e.x_root, y=e.y_root, ombra=None)

    def muovi(self, e):
        d = self.drag
        b = self.builder_aperto()
        if d is None or b is None:
            return
        if d["ombra"] is None:
            if abs(e.x_root - d["x"]) + abs(e.y_root - d["y"]) < 10:
                return
            self.lista.esci()
            d["ombra"] = self.ombra(d["nome"])
        d["ombra"].geometry(f"+{e.x_root + 14}+{e.y_root + 14}")      # accanto al puntatore, non sotto: se no la finestra sotto il puntatore sarebbe lei
        t = b.tavolo_aperto() if hasattr(b, "tavolo_aperto") else None
        if t is not None and t.sopra(e.x_root, e.y_root):        # sul tavolo delle carte intere: la pila dove cadrebbe si accende (9 nov 2026)
            t.evidenzia(e.x_root, e.y_root); b.evidenzia(False)
        else:
            if t is not None:
                t.evidenzia(0, 0, on=False)
            b.evidenzia(b.sopra(e.x_root, e.y_root))

    def lascia(self, e):
        d, self.drag = self.drag, None
        if d is None or d["ombra"] is None:
            return
        d["ombra"].destroy()
        b = self.builder_aperto()
        if b is not None:
            b.evidenzia(False)
            t = b.tavolo_aperto() if hasattr(b, "tavolo_aperto") else None
            if t is not None and t.sopra(e.x_root, e.y_root):       # lasciata sul tavolo: cade dove la lasci
                t.ricevi(d["nome"], e.x_root, e.y_root)
            elif b.sopra(e.x_root, e.y_root):
                b.metti(d["nome"], 1)

    def ombra(self, nome):
        """La carta che segue il puntatore mentre la trascini: la miniatura cotta, se c'e', se no il nome."""
        tk = self.tk
        o = tk.Toplevel(self.fr); o.overrideredirect(True); o.configure(bg=C["accento"])
        img = None
        f = CAP.file_mini(nome)
        if os.path.exists(f):
            try:
                from PIL import Image, ImageTk
                im = Image.open(f); im = im.resize((110, round(im.height * 110 / im.width)))
                img = ImageTk.PhotoImage(im)
            except Exception:
                img = None
        if img is not None:
            l = tk.Label(o, image=img, bd=0, bg=C["accento"]); l.image = img; l.pack(padx=2, pady=2)
        else:
            tk.Label(o, text=nome, bg=C["cap"], fg=C["titolo"], font=self.F(9, True), padx=8, pady=6).pack(padx=2, pady=2)
        return o

    def cambia_vista(self):
        self.colonne = 0
        self.cv.yview_moveto(0)
        self.adatta(self.cv.winfo_width())

    def aggiorna(self, d):
        if d is None or d is self.d:
            return
        self.d = d
        prepara_capsule(d)
        self.sets_on &= set(CC.elenco_set(d))
        if self.davanti():
            self.cerca()
        else:           # filtrare 15.000 carte per una pagina che nessuno guarda: quando torna
            self.da_cercare = True

    # ------------------------------------------------ il pannello Settings
    def pannello(self, apri=None):
        """Apre o chiude il pannello; senza argomento lo scambia."""
        self.aperto = not self.aperto if apri is None else apri
        if self.aperto:
            self.riempi_sets()
            self.metti_pannello()
        else:
            self.pan.place_forget()
        self.segna_tasto()

    def metti_pannello(self):
        self.fr.update_idletasks()
        y = self.barra_menu.winfo_y() + self.barra_menu.winfo_height() + 2
        larga = min(self.fr.winfo_width(), 820)
        self.pan.place(x=self.fr.winfo_width() - larga, y=y, width=larga, height=min(self.pan.winfo_reqheight(), self.fr.winfo_height() - y))
        self.pan.tkraise()

    def fuori(self, e):
        """Un clic fuori dal pannello lo chiude; le tendine aperte dentro sono sue figlie."""
        if self.aperto and not str(e.widget).startswith((str(self.pan), str(self.b_set))):
            self.pannello(False)

    def riempi_sets(self):
        """Le righe dei set, disegnate su una tela sola: 200 righe di etichette ci mettevano tre secondi alla prima apertura. Si fanno a pannello aperto e solo se i set sono cambiati."""
        tk, F, cs = self.tk, self.F, self.cv_sets
        sets = CC.elenco_set(self.d) if self.d else []
        if sets == self.sets_lista:
            return
        self.sets_lista = sets
        cs.delete("all")
        self.spunte_set = {}
        nomi = RS.nomi_set()
        tutte, mie = {}, {}
        for c in self.d["carte"]:
            for x, q in c["sets"].items():
                tutte[x] = tutte.get(x, 0) + 1
                mie[x] = mie.get(x, 0) + bool(q)
        for i, k in enumerate(sets):
            y = (i + 0.5) * self.ALTO_SET
            if ("set", k) not in self.loghi:
                f = icona_set(k, 16)
                self.loghi[("set", k)] = tk.PhotoImage(file=f) if f else None
            if self.loghi[("set", k)] is not None:
                cs.create_image(50, y, image=self.loghi[("set", k)])
            cs.create_text(80, y, text=f"{nomi.get(k) or nome_set(k) or k} ({k})", anchor="w", fill=TEND["testo"], font=F(9))
            cs.create_text(cs.winfo_width() - 10, y, text=f"{mie.get(k, 0):,} / {tutte.get(k, 0):,}", anchor="e", fill=C["muto"], font=F(8), tags="conti")
            self.spunte_set[k] = i
            self.spunta_set(k)
        cs.configure(scrollregion=(0, 0, 0, len(sets) * self.ALTO_SET))

    def mostra(self):
        """I due flag nel valore che capisce collezione_carte.filtra."""
        on = self.s_mostra.on
        return CC.MOSTRA[1] if on == {"O"} else CC.MOSTRA[2] if on == {"N"} else CC.MOSTRA[0]

    def spunta_set(self, k):
        cs, i, on = self.cv_sets, self.spunte_set.get(k), k in self.sets_on
        if i is None:
            return
        t = f"spunta{i}"
        cs.delete(t)
        y = (i + 0.5) * self.ALTO_SET - 7
        cs.create_image(8, y, image=DG.spunta(14, on, C["accento"], TEND["campo"], C["grigio"], C["fondo"]), anchor="nw", tags=t)

    def clic_set(self, e):
        i = int(self.cv_sets.canvasy(e.y) // self.ALTO_SET)
        if self.sets_lista and 0 <= i < len(self.sets_lista):
            self.scegli_set(self.sets_lista[i])

    def scegli_set(self, k):
        self.sets_on ^= {k}
        self.spunta_set(k)
        self.segna_tasto()
        self.chiedi()

    def togli_sets(self):
        for k in list(self.sets_on):
            self.sets_on.discard(k)
            self.spunta_set(k)
        self.segna_tasto()
        self.chiedi()

    def attivi(self):
        """Quanti filtri sono accesi: Sort by e View non filtrano."""
        return sum(map(bool, (self.sets_on, self.mostra() != CC.MOSTRA[0], self.t_formato.get() != "All", self.t_formato.get() != "All" and len(self.s_legale.on) == 1, self.s_colori.on, self.s_rarita.on, self.s_tipi.on, self.s_costi.on, self.t_copie.get() != "Any")))

    def segna_tasto(self):
        n = self.attivi()
        self.v_sets.set(f"SETS · {len(self.sets_on)} SELECTED" if self.sets_on else "SETS")
        self.b_set.metti(f"Settings · {n}" if n else "Settings", self.aperto)

    def cambia_retino(self):
        """La spunta del retino: si salva e le carte a vista si rifanno."""
        CAP.RETINO_ACCESO[0] = "R" in self.s_retino.on
        d = leggi_opzioni(); d["retino"] = CAP.RETINO_ACCESO[0]; salva_opzioni(d)
        self.cerca()

    def chiedi(self):
        """Si cerca poco dopo l'ultimo tasto: scrivendo non si ridisegna a ogni lettera."""
        if self.timer is not None:
            self.fr.after_cancel(self.timer)
        self.timer = self.fr.after(220, self.cerca)

    def azzera(self):
        self.v_testo.set("")
        for x in (self.s_mostra, self.s_legale, self.s_colori, self.s_rarita, self.s_tipi, self.s_costi):
            x.vuota()
        for k in list(self.sets_on):
            self.sets_on.discard(k)
            self.spunta_set(k)
        self.t_formato.set("All"); self.t_modo.set(CC.MODI[0]); self.t_copie.set("Any"); self.t_ordine.set("Color")
        self.cerca()

    FORMATI_COLL = ("All", "Standard", "Alchemy", "Explorer", "Historic", "Timeless", "Brawl", "Standard Brawl")

    def nel_formato(self, fmt):
        """Le carte del formato: le legali e, dal 10 nov 2026, anche le bandite (in rosso, il filtro Legality le separa). Standard dal pool e dalla ban list (la carta lo sa,
        c["standard"] e c["ban_std"], da Regole/Ban_Standard.md); gli altri dai formati di Scryfall, come la legalita' dei mazzi (mazzi_salvati.SCRYFALL; Explorer e' Pioneer, e qui
        sono tutte carte di Arena). Una carta che Scryfall non conosce (carte per principianti, 33 su 15.755 il 9 nov 2026) sta solo in All. Le liste si fanno una volta per
        collezione e formato: 0,05 s per tutto."""
        carte = self.d["carte"]
        if fmt == "All" or (fmt != "Standard" and fmt not in MS.SCRYFALL):
            return carte
        k = (id(self.d), fmt)
        cache = self.__dict__.setdefault("_formati", {})
        if k not in cache:
            cache.clear()
            cache[k] = [c for c in carte if self.legalita(c, fmt) is not None]
        return cache[k]

    def legalita(self, c, fmt=None):
        """«legal», «banned» o None (fuori dal formato) per la carta c nel formato (quello scelto se fmt e' None); con All sempre «legal»."""
        fmt = fmt or self.t_formato.get()
        if fmt == "All":
            return "legal"
        if fmt == "Standard":
            return "banned" if c.get("ban_std") else "legal" if c.get("standard") else None
        chiave = MS.SCRYFALL.get(fmt)
        x = PZ.carta(c["nome"].replace(" /// ", " // ")) if chiave else None       # Arena scrive le split con tre barre, Scryfall con due
        if not x:
            return None
        if chiave in (x.get("b") or "").split():
            return "banned"
        return "legal" if chiave in x["l"].split() or chiave in x["r"].split() else None

    def cerca(self):
        if self.timer is not None:
            self.fr.after_cancel(self.timer)
        self.timer = None
        self.da_cercare = False
        if not self.d:
            return
        carte = self.nel_formato(self.t_formato.get())
        leg = self.s_legale.on
        if self.t_formato.get() != "All" and len(leg) == 1:        # un flag solo: solo le legali o solo le bandite
            voluta = "banned" if "B" in leg else "legal"
            carte = [c for c in carte if self.legalita(c) == voluta]
        self.trovate = CC.ordina(CC.filtra(carte, self.v_testo.get(), self.sets_on, False, self.s_colori.on, self.t_modo.get(),
                                           self.s_rarita.on, self.s_tipi.on, self.s_costi.on, self.t_copie.get(), self.mostra()), self.t_ordine.get(), self.v_testo.get())
        self.cv.yview_moveto(0)
        self.segna_tasto()
        self.disegna()

    def adatta(self, larga):
        n = max(1, larga // (CAP.LARGA_CARTA + 10 if self.t_vista.get() == "Cards" else 330))
        if n != self.colonne or larga != self.largo:
            self.colonne, self.largo = n, larga
            self.disegna()
        else:
            self.chiedi_vedi()

    def disegna(self):
        """Riparte da zero: l'altezza di tutta la pagina e le carte a vista. A pagina nascosta aspetta: tanto nessuno le vede."""
        if not self.d:
            return
        if not self.davanti():
            self.sporco = True
            return
        self.sporco = False
        self.smista.svuota(); self.svuota(self.cv); self.cv.delete("all"); self.viste = {}
        self.lista.nuova_pagina()
        n = max(1, self.colonne)
        self.cv.configure(scrollregion=(0, 0, self.cv.winfo_width(), (len(self.trovate) + n - 1) // n * self.alto_riga()))
        self.titolo_carte.configure(text=f"CARDS · {len(self.trovate):,}")
        if not self.trovate:
            self.cv.create_text(self.cv.winfo_width() / 2, 40, text="No cards", fill=C["testo"], font=self.F(9))
        self.vedi()

    def chiedi_vedi(self):
        """Scorrendo arrivano tanti avvisi: basta guardare una volta sola, a fine giro."""
        if not self.vedi_atteso:
            self.vedi_atteso = True
            self.fr.after_idle(self.vedi)

    def vedi(self):
        """Fa le carte delle righe a vista, con una riga in piu' sopra e sotto, e toglie le altre."""
        self.vedi_atteso = False
        if not self.d or not self.davanti():
            return
        cv, n, alto, s = self.cv, max(1, self.colonne), self.alto_riga(), self.sets_on
        figure = self.t_vista.get() == "Cards"
        y0 = cv.canvasy(0)
        da, a = max(0, int(y0 // alto) - 1) * n, min(len(self.trovate), (int((y0 + cv.winfo_height()) // alto) + 2) * n)
        for i in [i for i in self.viste if not da <= i < a]:
            self.viste.pop(i).destroy()
        cella = cv.winfo_width() / n
        for i in range(da, a):
            if i in self.viste:
                continue
            c = self.trovate[i]
            x, y = (i % n) * cella, (i // n) * alto
            if figure:
                quante = CC.copie_in(c, s)
                bandita = self.legalita(c) == "banned"     # bandita nel formato scelto: il bordo rosso e BANNED sotto
                # sulla tela della griglia, non una finestra di Windows per carta (11 nov 2026, sessione Magic 13): la rotella faceva fino a 8 quadri a pezzi per
                # scatto e fermava la finestra fino a 190 ms (Note/Motore_Grafico_App.md)
                w = self.lista.carta_piena(cv, c["nome"], f"x{quante}" + ("  ·  BANNED" if bandita else ""), C["scheda"], spenta=not quante, bandita=bandita,
                                           su=(round(x + cella / 2), y, self.smista))      # le carte che non hai, opache
            else:
                sets_ = CC.RS.ordina_set([k for k in c["sets"] if not s or k in s])
                bandita = self.legalita(c) == "banned"
                # anche la lista sulla tela della griglia, una riga disegnata per carta (11 nov 2026): prima una tela di Tk per riga
                larga = max(60, round(cella - 8))
                w = carta_tela.CartaTela(cv, round(x), y, larga, CAP.ALTO, self.smista)
                self.lista.disegna_riga(w, larga, c["nome"], CC.copie_in(c, s), destra="BANNED" if bandita else f"{c['r']} {sets_[0]}",
                                        col_destra=C["rosso"] if bandita else self.COL_RARITA.get(c["r"], C["testo"]), colonna="M WOE")
                w.bind("<Enter>", lambda e, w=w, n=c["nome"]: self.lista.entra(w, n)); w.bind("<Leave>", self.lista.esci); w.bind("<Destroy>", self.lista.esci, add=True)
            self.lega_trascina(w, c["nome"])
            self.viste[i] = w
        self.lista.solo(self.trovate[i]["nome"] for i in self.viste)
