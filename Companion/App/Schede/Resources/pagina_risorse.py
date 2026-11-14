"""La scheda Resources: il saldo, il Trend, il Farmer col ROI, la roadmap."""
import os
import sys

import disegni as DG
import risorse as RS

from dati_app import numeri
from farmer import Farmer, MenuGoal
from icone import RISORSE_DIR, icona_jolly, icona_risorsa, icona_set
from pagina_base import Pagina
from roadmap import Roadmap
from roadmap_check import RoadmapCheck
from roi import Roi
from tema import CI as C, FN, TEND
from trend import Trend
from widget import Numero, Spunte, Tendina, TendinaMulti, pulsante_solido


class PaginaRisorse(Farmer, Roadmap, Roi, RoadmapCheck, Trend, Pagina):
    """Risorse: quanto oro, gemme, buste, carte e jolly entrano nel conto e dove vanno oro e gemme. A sinistra il grafico, sotto Income e la spesa per evento; a destra il Farmer col ROI
    sotto (Autore, 6 nov 2026: «sotto il grafo al posto delle sottosezioni resources e monthly income mettiamo una sezione che dice solo l'income delle varie risorse in base all'incrocio
    delle tendine e sotto ancora dove si e' speso di piu' per eventi e se si e' comprata mastery / roi lo mettiamo come sezione sotto il farmer»). Create lancia il piano: al posto del Farmer
    nasce la roadmap, che scorre in verticale dal giorno del piano, e il pulsante diventa Dismiss («una volta lanciato il piano, il pulsante create diventa dismiss se si volesse abbandonare e ricreare un nuovo piano»)."""

    VOCI_GRAFICO = ("Oro", "Gemme", "Buste", "Carte", "Jolly")
    # Most packs non c'e' piu' (Autore, 8 nov 2026: «most rare mythics e most pack sono praticamente lo stesso obiettivo quindi accorpali in un unico most wc R - M»): le buste
    # servono per i jolly rari e mitici, e i due goal davano lo stesso piano. Il calcolo tiene «buste»; un piano salvato con Most packs si riprende su Most wildcards
    # Convert gold to gems in cima (Autore, 8 nov 2026: «convert gold to gems per primo»): le gemme sono la moneta vera
    # «Reach a deck» tolto (Autore, 9 nov 2026: «il reach a deck tiralo via»): un piano salvato con quel goal si riprende senza (MenuGoal.metti tiene solo i goal che ci sono)
    GOAL = (("gemme", "Convert gold to gems"), ("valore", "Best return: events or packs"), ("jolly", "Most wildcards (R · M)"), ("carte", "Most cards from a set"))
    GOAL_CORTI = dict(mazzo="Deck", valore="Best return", jolly="Wildcards", buste="Packs", gemme="Gems", carte="Cards")
    ICONE = {"Oro": "oro", "Gemme": "gemma", "Buste": "busta", "Carte": "carte"}
    TUTTI = {"Settimana": "All years", "Mese": "All years", "Anno": "All years"}
    NOMI_RISORSE = {"Oro": "Gold", "Gemme": "Gems", "Buste": "Packs", "Carte": "Cards", "Jolly": "Wildcards"}
    NOMI_GRANA = {"Settimana": "Week", "Mese": "Month", "Anno": "Year"}
    PADRE_SALDO = None      # la riga delle schede della finestra; None: la riga delle tendine (le prove)
    LARGA_PAGINA = 1500     # sotto, il ROI va su tre colonne: a finestra normale le cifre si taglierebbero
    FILE_PIANO = None       # il collaudo ne usa uno suo; None: Log_Arena/piano_farmer.json

    def __init__(self, tk, padre, F, mana):
        super().__init__(tk, padre, F, mana)
        self.esp.fr.pack_forget()      # qui si filtra per periodo, non per espansione
        self.R = None
        self.mappa = {}
        self.gr = Tendina(tk, self.barra_menu, "Period", F, larga=130); self.gr.fr.pack(side="left")
        self.qual = Tendina(tk, self.barra_menu, "Range", F, larga=170); self.qual.fr.pack(side="left", padx=(12, 0))
        self.ser = TendinaMulti(tk, self.barra_menu, "Resource", F, larga=170); self.ser.fr.pack(side="left", padx=(12, 0))
        self.gr.opzioni(RS.GRANA, lambda o: (self.qual.set(self.TUTTI[o]), self.disegna(solo_periodo=True)), etichette=self.NOMI_GRANA)
        self.ser.opzioni(self.VOCI_GRAFICO, lambda o: self.disegna(solo_periodo=True), {n: i for n, i in list((n, self.icona(f)) for n, f in self.ICONE.items()) + [("Jolly", self.icona_j("R"))] if i}, self.NOMI_RISORSE)
        arg = lambda k, d: sys.argv[sys.argv.index(k) + 1].replace("_", " ") if k in sys.argv else d      # collaudo
        self.gr.set(arg("--periodo", "Mese")); self.ser.set(arg("--grafico", "Oro")); self.qual.set(self.TUTTI[self.gr.get()])
        self.quale_arg = arg("--quale", None)
        # la spunta accanto alle tendine (Autore, 4 nov 2026: «attiviamo questa voce con una spunta flaggabile accanto alle
        # tendine»): accende il valore in gemme accanto all'oro; parte spenta
        self.gemme_on = "--senza-gemme" not in sys.argv      # accesa alla partenza (Autore, 6 nov 2026: «dobbiamo sempre mantenere un corrispettivo tra oro e gemme»)
        sp = tk.Frame(self.barra_menu, bg=C["fondo"], cursor="hand2"); sp.pack(side="left", padx=(16, 0), anchor="s")
        tk.Label(sp, text="GOLD IN GEMS", bg=C["fondo"], fg=C["titolo"], font=F(7, True), pady=0).pack(anchor="w", pady=(0, 3))
        self.spunta = tk.Canvas(sp, width=32, height=32, bg=C["fondo"], highlightthickness=0, cursor="hand2"); self.spunta.pack(anchor="w")
        self.disegna_spunta()
        for w in (sp, self.spunta) + tuple(sp.winfo_children()):
            w.bind("<Button-1>", lambda e: self.scambia_gemme())
        # il conto del giocatore, in alto a destra sulla riga delle tendine (Autore, 4 nov 2026: «il balance di tutte le risorse che ha il player mettiamolo in alto a
        # destra sulla stessa riga delle tendine: tokens, gold, gems, wc ecc»): e' sempre quello di adesso, non segue le tendine
        # poi sulla riga delle schede, solo oro, gemme, token, jolly rari e mitici e vault (Autore, 6 nov 2026: «i dati di balance spostali in alto sulla riga delle schede per intenderci e
        # togli la quantita' di packs, di carte e tieni solo le wc gold e mythic, dai al vault il logo di un bauletto»)
        self.b_saldo = tk.Frame(self.PADRE_SALDO or self.barra_menu, bg=C["fondo"]); self.b_saldo.pack(side="right", anchor="center", padx=(0, 6))
        self.saldo_celle = []
        self.fr.columnconfigure(0, weight=1, uniform="pg"); self.fr.columnconfigure(1, weight=2, uniform="pg")      # a destra stanno due sezioni affiancate
        self.b_gra, _ = self.scheda("Trend", col=0, espandi=True)
        # l'opzione Farmer sul grafico (Autore, 6 nov 2026: «sul graf mettiamo l'opzione farmer per vedere in base alle risorse come possono cambiare i graph grazie al piano impostato»), spenta alla partenza;
        # sostituisce la vista: «la spunta farmer non si sovrappone piu' ma sostituisce la vista»
        # sotto il grafico le sue opzioni (stesso giorno: «diamo piu' opzioni sul grafico flaggabili anche sotto il grafico per avere un quadro piu' personalizzabile dei dati»)
        self.op = dict(entra=True, esce=True, saldo=False, cumula=False, media=False)
        self.confronta = "--farmer" in sys.argv
        cap = self.cap_tit.master
        self.sp_far = tk.Canvas(cap, width=14, height=14, bg=C["cap"], highlightthickness=0, cursor="hand2")
        l_far = tk.Label(cap, text="FARMER", bg=C["cap"], fg=C["capo"], font=F(8, True), cursor="hand2"); l_far.pack(side="right", padx=(0, 10))
        self.sp_far.pack(side="right", padx=(0, 5))
        for w in (self.sp_far, l_far):
            w.bind("<Button-1>", lambda e: self.scambia_confronto())
        self.disegna_sp_far()
        self.b_ris, _ = self.scheda("Average income", col=0)
        self.b_spe, _ = self.scheda("Event spending", col=0)
        # a destra il Farmer e la roadmap affiancati, sotto il ROI (Autore, 6 nov 2026: «nel farmer sposta i dati di spesa sotto ai settaggi e il piano lo mettiamo in una nuova
        # sezione accanto / cosi' abbiamo due sezioni affiancate e quando premiamo create, e' la sezione accanto ad aggiornarsi»)
        destra = tk.Frame(self.col[1], bg=C["fondo"]); destra.pack(fill="both", expand=True)
        destra.columnconfigure(0, weight=1, uniform="fr"); destra.columnconfigure(1, weight=1, uniform="fr"); destra.rowconfigure(0, weight=1)
        # il Farmer alto tutta la colonna, il ROI sotto la roadmap (Autore, 9 nov 2026: «la sezione roi sotto roadmap cosi' che farmer si legga di piu' in altezza»; dal 6 nov stava sotto il Farmer)
        self.c_far = c_far = tk.Frame(destra, bg=C["fondo"]); c_far.grid(row=0, column=0, rowspan=2, sticky="nsew", padx=(0, 4))
        self.c_road = tk.Frame(destra, bg=C["fondo"]); self.c_road.grid(row=0, column=1, sticky="nsew", padx=(4, 0))
        c_roi = tk.Frame(destra, bg=C["fondo"]); c_roi.grid(row=1, column=1, sticky="ew", padx=(4, 0))
        self.stretta = None
        self.largo_f = 300      # quanto va a capo il testo del Farmer
        # il farmer calculator, a destra: gli ingressi restano, solo gli esiti si ridisegnano
        # (Autore, 4 nov 2026: «la sezione goal planner viene integrata nel farmer, si parte da nessun obiettivo»)
        corpo_f, _ = self.scheda("Farmer", col=c_far, espandi=True)
        r_c = tk.Frame(corpo_f, bg=C["scheda"]); r_c.pack(side="bottom", fill="x", pady=(8, 0))       # il pulsante resta a vista anche se le voci scorrono
        self.b_crea = pulsante_solido(tk, F, r_c, "Create", False, self.crea, alto=34, bg=C["scheda"]); self.b_crea.configure(width=180); self.b_crea.pack(side="right")
        self.b_togli = pulsante_solido(tk, F, r_c, "Dismiss", False, self.togli, alto=34, bg=C["scheda"]); self.b_togli.configure(width=180)      # il pulsante cambia, la roadmap si aggiorna accanto
        # il Farmer scorre con la rotella: con un obiettivo le tabelle non entrano sempre nella colonna; a destra una barra sottile, come nella chat
        def tela(padre):
            """Una tela che scorre con la rotella, con la barra sottile a destra."""
            barra = tk.Canvas(padre, width=5, bg=C["scheda"], highlightthickness=0); barra.pack(side="right", fill="y", padx=(4, 0))
            def segna(a, b):
                barra.delete("all"); a, b = float(a), float(b)
                if b - a < 0.999:
                    H_ = barra.winfo_height(); barra.create_rectangle(0, H_ * a, 5, H_ * b, fill=C["filo"], width=0)
            cv = tk.Canvas(padre, bg=C["scheda"], highlightthickness=0, yscrollcommand=segna); cv.pack(side="left", fill="both", expand=True)
            def rotella(e):
                if str(e.widget).startswith(str(cv)) and cv.bbox("all") and cv.bbox("all")[3] > cv.winfo_height():
                    cv.yview_scroll(-1 if e.delta > 0 else 1, "units")
            cv.bind_all("<MouseWheel>", rotella, add="+")
            return cv
        cv_f = tela(corpo_f)
        b_cal = tk.Frame(cv_f, bg=C["scheda"])
        id_f = cv_f.create_window(0, 0, anchor="nw", window=b_cal)
        b_cal.bind("<Configure>", lambda e: cv_f.configure(scrollregion=cv_f.bbox("all")))
        cv_f.bind("<Configure>", lambda e: (cv_f.itemconfigure(id_f, width=e.width), setattr(self, "largo_f", max(240, e.width - 8))))
        # sopra i settaggi, sotto quanto costa sostenerli
        self.f_voci = tk.Frame(b_cal, bg=C["scheda"]); self.f_voci.pack(fill="x")
        self.f_esi = tk.Frame(b_cal, bg=C["scheda"]); self.f_esi.pack(fill="x", pady=(10, 0))
        # il valore dell'oro, in testa al Farmer (Autore, 8 nov 2026: «diamo dei flag in testa: gold gems rate o personal wr to gems»): col tuo win rate (le gemme che ti tornano davvero, di
        # partenza) o al prezzo di una busta (valore in carte). Una sola accesa; cambia i conti e le scelte del piano
        self.modo_cambio = "wr"
        r_c = tk.Frame(self.f_voci, bg=C["scheda"]); r_c.pack(fill="x", pady=(0, 8))
        tk.Label(r_c, text="GOLD VALUE", bg=C["scheda"], fg=C["titolo"], font=F(7, True), pady=0).pack(anchor="w", pady=(0, 4))
        self.c_cambio, self.l_cambio = {}, {}
        for k, nome in (("wr", "My win rate"), ("busta", "Pack price")):
            rr = tk.Frame(r_c, bg=C["scheda"], cursor="hand2"); rr.pack(anchor="w", pady=(0, 3))
            c = tk.Canvas(rr, width=13, height=13, bg=C["scheda"], highlightthickness=0, cursor="hand2"); c.pack(side="left", padx=(0, 6))
            l = tk.Label(rr, text=nome, bg=C["scheda"], fg=C["testo"], font=F(8), pady=0, cursor="hand2"); l.pack(side="left")
            for w in (rr, c, l):
                w.bind("<Button-1>", lambda e, k=k: self.scegli_cambio(k))
            self.c_cambio[k], self.l_cambio[k] = c, l
        self.disegna_spunte_cambio()
        r_g = tk.Frame(self.f_voci, bg=C["scheda"]); r_g.pack(fill="x", pady=(0, 6))
        # il menu dei goal, si possono mischiare (Autore, 4 nov 2026: «a sinistra costruiamo il menu dei goal in modo da poterli costruire misti se vogliamo»)
        # dall'8 nov 2026 slider a percentuale, con la spunta delle buste in oro (MenuGoal)
        self.goal = MenuGoal(tk, r_g, self.GOAL, F, lambda: self.cambia_goal(), C["scheda"]); self.goal.fr.pack(fill="x", anchor="n")
        self.g_set = Tendina(tk, r_g, "Set", F, larga=150, bg=C["scheda"])
        sets = RS.set_farmer()      # anche i set col draft in arrivo (Star Trek, 9 nov 2026)
        icone = {}
        for c, _n in sets:
            f = icona_set(c, 16)
            self.loghi[("set", c)] = tk.PhotoImage(file=f) if f else None
            if self.loghi[("set", c)] is not None:
                icone[c] = self.loghi[("set", c)]
        self.g_set.corte = {c: c for c, _n in sets}
        self.g_set.opzioni([c for c, _n in sets], lambda o: self.disegna_calcolo(), icone, {c: f"{n} ({c})" for c, n in sets})
        self.g_set.set(sets[0][0] if sets else "")
        # il mazzo da raggiungere: Wishlist e Laboratory (Autore, 8 nov 2026, «ok» al goal «arriva a questo mazzo»)
        self.g_mazzo = Tendina(tk, r_g, "Target deck", F, larga=270, bg=C["scheda"])
        self.g_mazzo.opzioni([], lambda o: self.disegna_calcolo())
        self.default_fatto = False
        self._pareggi = {}
        self.liberi = None
        g = tk.Frame(self.f_voci, bg=C["scheda"]); g.pack(fill="x", pady=(0, 4))
        rifai = lambda: self.disegna_calcolo()
        self.n_quick = Numero(tk, g, "Quick Drafts a month", F, rifai, bg=C["scheda"])
        self.n_premier = Numero(tk, g, "Premier Drafts a month", F, rifai, bg=C["scheda"])
        self.n_costruiti = Numero(tk, g, "Constructed a month", F, rifai, bg=C["scheda"])
        self.n_buste = Numero(tk, g, "Packs a month", F, rifai, passo=5, bg=C["scheda"])
        self.n_mitiche = Numero(tk, g, "Mythic packs a month", F, rifai, bg=C["scheda"])
        # il win rate viene dai dati, non si scrive, ed e' separato per eventi limited e constructed (Autore, 4 nov 2026); a video non si mostra piu' (stesso giorno: «togli questi dati»)
        self.wr = dict(limited=None, constructed=None)
        self.n_wr = dict(limited=0, constructed=0)
        # sotto ogni voce come si paga (Autore, 4 nov 2026: «sotto a ogni voce una spunta per gemme o oro o token cosi' ogni evento puo' essere pagato in maniera diversa»)
        draft = (("oro", "Gold"), ("gemme", "Gems"), ("token", "Token"))
        busta = (("oro", "Gold"), ("gemme", "Gems"))
        solo_oro = (("oro", "Gold"),)       # le buste solo in oro: le gemme non comprano mai buste (Autore, 9 nov 2026: «le gemme non devono essere contate per l'acquisto buste mai»)
        self.paga = {}
        for k, n, voci in (("quick", self.n_quick, busta), ("premier", self.n_premier, draft), ("costruiti", self.n_costruiti, busta), ("buste", self.n_buste, solo_oro), ("mitiche", self.n_mitiche, solo_oro)):
            # i riquadri in colonna, col reset accanto (Autore, 6 nov 2026: «mettiamo in colonna i riquadri data entry del farmer e un pulsantino di reset accanto»); accanto anche come si paga, se no la colonna non entra
            n.col_reset(lambda k=k: self.azzera(k))
            self.paga[k] = Spunte(tk, n.fr, voci, F, rifai, C["scheda"]); n.accanto(self.paga[k].fr)
        self.g_voci = g
        self.b_nota = tk.Frame(self.f_voci, bg=C["scheda"]); self.b_nota.pack(fill="x")       # sotto le voci, perche' quella rotta
        self.b_esi = tk.Frame(self.f_esi, bg=C["scheda"]); self.b_esi.pack(fill="x")
        # la sezione ROI, sotto il calcolatore (Autore, 4 nov 2026: «una sezione roi molto piu' sintetica e facile da leggere, non possiamo ottenere numeri decimali»):
        # cosa spendi, cosa ottieni, com'e' finita; numeri interi, arrotondati
        self.b_roi, _ = self.scheda("ROI", col=c_roi)
        # la roadmap: la testa, sotto i giorni su una tela sola
        corpo_r, _ = self.scheda("Roadmap", col=self.c_road, espandi=True)
        t_r = tk.Frame(corpo_r, bg=C["scheda"]); t_r.pack(fill="x", pady=(0, 8))
        self.l_piano = tk.Label(t_r, bg=C["scheda"], fg=C["titolo"], font=F(10, True), anchor="w", pady=0); self.l_piano.pack(anchor="w")
        self.l_stato = tk.Label(t_r, bg=C["scheda"], fg=C["grigio"], font=F(8), anchor="w", pady=0); self.l_stato.pack(anchor="w", pady=(2, 0))
        self.cv_r = tela(corpo_r)
        self.largo_r = 0
        self.cv_r.bind("<Configure>", lambda e: self.disegna_road() if e.width != self.largo_r else None)
        self.calcolo = None
        self.piano = RS.leggi_piano(self.FILE_PIANO)
        self.ripreso = False
        self.adatta(0)
        self.fr.bind("<Configure>", lambda e: self.adatta(e.width), add="+")

    def adatta(self, larga):
        """La pagina secondo la larghezza: si ridisegna solo passando la soglia, e a pagina visibile (distruggere etichette con immagini su una pagina nascosta fa cadere Tk)."""
        st = larga < self.LARGA_PAGINA
        if st == self.stretta or 0 < larga < 200:
            return
        self.stretta = st
        for i, x in enumerate((self.n_quick, self.n_premier, self.n_costruiti, self.n_buste, self.n_mitiche)):
            x.fr.grid(row=i, column=0, sticky="nw", pady=(0, 4))
        if larga and self.R:
            self.fr.after(60, lambda: self.disegna() if self.davanti() else None)

    def aggiorna(self, R):
        # il Player.log si rilegge ogni 30 s se e' cambiato, e con Arena aperta cambia sempre: se le foto del conto e i movimenti sono gli stessi
        # la pagina non si segna da ridisegnare (9 nov 2026: le schede dietro si preparano da sole, e Resources costa quasi un secondo)
        firma = (len(R.foto), R.foto[-1].get("t") if R.foto else None, len(R.voci)) if R else None
        if firma is not None and firma == getattr(self, "firma_R", None) and self.R is not None:
            self.R = R
            return
        self.firma_R = firma
        self.R = R
        self.disegna_saldo()           # sta sulla riga delle schede: si vede anche a pagina nascosta
        # con un piano lanciato il Farmer mostra quel piano; se no parte dal mazzo da raggiungere, o da zero (goal_iniziale)
        if R and R.foto and self.piano and not self.ripreso:      # il Farmer riparte da com'era quando hai lanciato il piano
            self.ripreso = True
            self.riprendi(self.piano)
        elif R and R.foto and not self.piano and not self.default_fatto:
            self.default_fatto = True
            self.goal_iniziale()
            self.cambia_goal()
        self.mostra_piano()
        self.ridisegna()

    def aggiorna_draft(self, draft):
        """Il win rate degli eventi limited, dalle tue partite."""
        w, n, _, _ = numeri(draft)
        self.wr["limited"] = w / n if n else None
        self.n_wr["limited"] = n
        if self.a_vista():
            self.disegna_calcolo()

    def aggiorna_costruite(self, dati):
        """Il win rate degli eventi constructed, classificata e libera insieme."""
        if dati:
            w = dati["ladder"][0] + dati["play"][0]; n = dati["ladder"][1] + dati["play"][1]
            self.wr["constructed"] = w / n if n else None
            self.n_wr["constructed"] = n
        if self.a_vista():
            self.disegna_calcolo()

    def disegna_saldo(self):
        """Il conto di adesso, come nella barra in cima ad Arena: icona e numero. Il gettone del draft token e' ritagliato, col suo ok (6 nov 2026), dall'immagine di draftsim.com/mtg-arena-draft-token/. Sta sulla riga delle schede, quindi si vede sempre: si aggiorna anche a
        pagina nascosta. Le voci si fanno una volta e poi cambia solo il numero: distruggere queste etichette con la scheda nascosta faceva cadere tutta la finestra all'avvio (access violation
        dentro Tk, 4 nov 2026)."""
        tk, F, R = self.tk, self.F, self.R
        if R is None or not R.foto:
            return
        sa = R.saldo()
        pt = lambda x: f"{round(x):,}"
        voci = [(self.icona("oro"), "", pt(sa["oro"])), (self.icona("gemma"), "", pt(sa["gem"])), (self.icona("token"), "", pt(sa["token"])),
                (self.icona_j("R"), "", pt(sa["jolly"][2])), (self.icona_j("M"), "", pt(sa["jolly"][3])), (self.icona("vault"), "", f"{round(sa['vault'])}%")]
        if not self.saldo_celle:
            for c, (img, nome, _) in enumerate(voci):
                a_ = tk.Label(self.b_saldo, image=img, bg=C["fondo"], pady=0) if img is not None else tk.Label(self.b_saldo, text=nome, bg=C["fondo"], fg=C["titolo"], font=F(7, True), pady=0)
                b_ = tk.Label(self.b_saldo, bg=C["fondo"], fg=C["titolo"], font=FN(11), pady=0)        # i numeri in Bahnschrift bianco (redesign del 14 nov 2026)
                if c:       # un filo fra una voce e l'altra, come i chip del mockup
                    tk.Frame(self.b_saldo, bg=C["filo"], width=1, height=20).grid(row=0, column=3 * c - 1, padx=(10, 0))
                a_.grid(row=0, column=3 * c, sticky="e", padx=(10 if c else 0, 5)); b_.grid(row=0, column=3 * c + 1, sticky="w")
                self.saldo_celle.append((a_, b_))
        for (_, lab), (_, _, val) in zip(self.saldo_celle, voci):
            lab.configure(text=val)

    def disegna_spunta(self):
        c = self.spunta
        c.delete("all")
        c.create_image(0, 0, image=DG.spunta(32, self.gemme_on, C["azzurro"], TEND["campo"], TEND["bordo"], C["fondo"], raggio=3), anchor="nw")

    def scambia_gemme(self):
        self.gemme_on = not self.gemme_on
        self.disegna_spunta()
        self.disegna()

    def icona(self, nome, alto=16):
        """L'immagine di un'icona di Arena, fatta una volta; None se il file non c'e'."""
        if (nome, alto) not in self.loghi:
            f = icona_risorsa(nome, alto)
            self.loghi[(nome, alto)] = self.tk.PhotoImage(file=f) if f else None
        return self.loghi[(nome, alto)]

    def icona_doppia(self):
        """Oro e gemma affiancati: il ROI conta oro e gemme insieme, in gemme (Autore, 6 nov 2026). Il file e' fatto una volta dalle due icone."""
        if "oro_gemma" not in self.loghi:
            f = os.path.join(RISORSE_DIR, "oro_gemma_16.png")
            self.loghi["oro_gemma"] = self.tk.PhotoImage(file=f) if os.path.exists(f) else self.icona("gemma", 16)
        return self.loghi["oro_gemma"]

    def icona_j(self, k_):
        if ("jolly", k_) not in self.loghi:
            f = icona_jolly(k_, 16)
            self.loghi[("jolly", k_)] = self.tk.PhotoImage(file=f) if f else None
        return self.loghi[("jolly", k_)]

    def disegna(self, solo_periodo=False):
        """solo_periodo: Period, Range e Resource cambiano solo il grafico, l'Average income e l'Event spending; Farmer, ROI, Roadmap e saldo restano (7 nov 2026: ogni tendina
        rifaceva tutta la pagina, 0,47 s). Il Farmer deve essere gia' stato disegnato: la vista Farmer del grafico legge il suo piano."""
        tk, F, R = self.tk, self.F, self.R
        solo_periodo = solo_periodo and self.calcolo is not None and R is not None and bool(R.foto)
        for b in ((self.b_gra, self.b_ris, self.b_spe) if solo_periodo else (self.b_gra, self.b_ris, self.b_spe, self.b_esi, self.b_roi, self.b_nota)):
            self.svuota(b)
        if not solo_periodo:
            self.disegna_saldo()
        if R is None or not R.foto:
            tk.Label(self.b_gra, text="Data shows up once the logs are read", bg=C["scheda"], fg=C["grigio"], font=F(9), anchor="w").pack(fill="x")
            return
        grana = self.gr.get()
        # Range mostra solo i periodi dell'anno in corso; il resto si misura con «All years» (Autore, 4 nov 2026: «la tendina range
        # mostra solo i mesi dell'anno in corso, i dati fuori dall'anno in corso si possono misurare alla voce totale tutti gli anni»)
        self.mappa = {RS.nome_periodo(k, grana): k for k in reversed(R.periodi(grana)) if grana == "Anno" or R.al.year in (k.year, RS.fine(k, grana).year)}
        opz = [self.TUTTI[grana]] + list(self.mappa)
        if opz != getattr(self, "opz_quale", None):
            self.opz_quale = opz
            self.qual.opzioni(opz, lambda o: self.disegna(solo_periodo=True))
        if self.quale_arg in opz:
            self.qual.set(self.quale_arg)
        self.quale_arg = None
        if self.qual.get() not in opz:
            self.qual.set(opz[0])
        k = self.mappa.get(self.qual.get())
        s = R.taglio(grana, k)
        pt = lambda x: f"{round(x):,}"
        self.applica_cambio()
        in_gemme = lambda x: pt(x * R.gpo)
        # tutti i conti seguono le tendine (Autore, 4 nov 2026: «tutti i conti dei valori risorse devono sempre essere aggiornati
        # alle tendine e voci selezionate e incrociate dalle tendine»): anche la cassa e' quella a fine del periodo scelto
        if not solo_periodo:
            self.disegna_calcolo(grafico=False)
        self.disegna_grafico()       # dopo il Farmer: la vista Farmer legge il suo piano
        if not solo_periodo:
            self.estendi_piano()
            self.adatta_piano()
            self.disegna_road()
        # Income: quel che e' entrato, risorsa per risorsa (Autore, 6 nov 2026: «una sezione che dice solo l'income delle varie risorse in base all'incrocio delle tendine»). Un periodo scelto
        # dice il totale di quel periodo; «All years» la media a settimana, al mese o all'anno secondo Period. La risorsa scelta in Resource e' azzurra
        fattore = 1 if k else {"Settimana": 7, "Mese": 365.25 / 12, "Anno": 365.25}[grana] / s["giorni"]
        coda = "" if k else {"Settimana": " /wk", "Mese": " /mo", "Anno": " /yr"}[grana]      # la colonna a sinistra e' stretta: «mythic wc a month» si tagliava
        ris = self.ser.get()
        accesa = lambda n: C["azzurro"] if n in ris else None
        voci = [("gold" + coda, pt(s["oro_piu"] * fattore), accesa("Oro"), f"{in_gemme(s['oro_piu'] * fattore)} gems" if self.gemme_on else "", self.icona("oro", 16)),
                ("gems" + coda, pt(s["gem_piu"] * fattore), accesa("Gemme"), "", self.icona("gemma", 16)),
                ("packs" + coda, pt(s["bu_ott"] * fattore), accesa("Buste"), "", self.icona("busta", 16)),
                ("rare wc" + coda, pt(s["jolly_piu"][2] * fattore), accesa("Jolly"), "", self.icona_j("R")),
                ("mythic wc" + coda, pt(s["jolly_piu"][3] * fattore), accesa("Jolly"), "", self.icona_j("M")),
                ("cards" + coda, ("≈ " if s["c_buste"] else "") + pt(s["carte"] * fattore), accesa("Carte"), "", self.icona("carte", 16))]
        self.griglia(self.b_ris, voci, colonne=3, grande=12, stretta=True)
        # dove si e' speso di piu' negli eventi, e il Mastery Pass
        spese = R.spese_eventi(s)
        cif = lambda x: self.cella(pt(x) if x else "-", C["testo"] if x else C["muto"], grande=8)
        if spese:
            self.tabella(self.b_spe, [("event", "w"), ("entries", "e"), ("gold", "e"), ("gems", "e")],
                         [[self.cella(x["nome"], C["titolo"], grande=8, lato="left"), cif(x["volte"]), cif(x["oro"]), cif(x["gemme"])] for x in spese[:6]], padx=3)
        else:
            tk.Label(self.b_spe, text="No events in this period", bg=C["scheda"], fg=C["grigio"], font=F(8), anchor="w").pack(fill="x")
        pas = R.pass_comprati(k, RS.fine(k, grana)) if k else R.pass_comprati()
        testo = " · ".join(f"bought {x['data'].day} {x['data']:%b} for {pt(x['gemme'])} gems" for x in pas) or "not bought in this period"
        r_p = tk.Frame(self.b_spe, bg=C["scheda"]); r_p.pack(fill="x", pady=(6, 0))
        self.etichetta(r_p, "Mastery Pass").pack(side="left")
        tk.Label(r_p, text=testo, bg=C["scheda"], fg=C["testo"] if pas else C["grigio"], font=F(8), pady=0).pack(side="left", padx=(8, 0))
