"""Il builder dei mazzi (Autore, 7 nov 2026: «build deve essere un builder che mi permette di mettere insieme delle carte e costruire e vedere la scheda deck che mi da dei dati /
ci serve un pulsante di import che copi i deck in questa applicazione, come per arena»; poi «le build dei deck devono avere un save, un export to arena, un counter delle wc»; poi
«in deck builder invece di selezionare le carte da una lista a elenco sarebbe utile poterle vedere anche per immagine e testo e anche la ricerca dovrebbe funzionare per testo /
facciamo che il deck builder è una finestra che si apre dalla sezione collection così abbiamo la collezione sotto e la finestra permette di trascinare le carte dentro a se e mostrare dati»).

Le carte si scelgono nella Collection, a figura piena o in lista, con la sua ricerca per nome, tipo e testo e i suoi filtri: il builder e' una finestra sopra il Companion (transient,
niente topmost), sul lato destro, e una carta trascinata dalla Collection dentro la finestra (o un doppio clic sulla carta) entra nel mazzo, nella zona di «Add to». Aprendolo da Your decks
la finestra grande passa da sola alla Collection. Al centro il mazzo, come in Arena: clic su una carta = una copia in meno, tasto destro = una in piu'. Oltre 4 copie (1 nel Brawl) no,
tranne le basi e le carte senza limite. A destra i jolly e i dati, rifatti a ogni carta. In alto: nome, formato, Add to, Import, Export to Arena, Export to MTGO, Clear (due clic), Save.
Il builder e' gia' la scheda del mazzo (Autore, 8 nov 2026: «nel deck builder vedo che c'e' il pulsante deck sheet / no facciamo in modo che gia' il builder sia un deck sheet con
grafo ecc cosi' abbiamo un passaggio in meno»): accanto ai dati il grafo dell'archetipo, la curva di mana e le terre nella mano iniziale, tutto rifatto a ogni carta; il pulsante Deck
sheet non c'e' piu' e al suo posto c'e' Export to MTGO.
Chiudendo, una build cambiata e non vuota si salva. La Collection ha le carte di Arena: per Pioneer, Modern, Legacy, Vintage e Pauper le carte che Arena non ha entrano con Import.
Un builder alla volta (Costruttore.APERTO): aprirne un altro chiude il primo, salvandolo.
"""
import os, sys
_casa = os.path.dirname(os.path.abspath(__file__))      # si sale fino a percorsi.py, che mette nel sys.path tutte le cartelle del Companion
while not os.path.isfile(os.path.join(_casa, "percorsi.py")):
    _casa = os.path.dirname(_casa)
if _casa not in sys.path:
    sys.path.insert(0, _casa)
import percorsi  # noqa: E402
import capsule as CAP
import collezione_carte as CC
import dati_mazzo as DM
import disegni as DG
import mazzi_salvati as MS
import prezzi_carte as PZ

from dati_app import collezione, craft, jolly
from dati_meta import FORMATI_META, meta_mazzi
from esporta_mazzo import lista_arena, lista_mtgo
from pagina_base import prepara_capsule
from pagina_collezione import PaginaCollezione
from pagina_standard import PaginaStandard
from tema import CI as C, barra_scura
from widget import ARANCIO, Tendina, pronta_poi, pulsante_solido, svuota

DOVE = ("Deck", "Sideboard", "Commander")
LARGA, ALTA = 1180, 900


def limite(nome, fmt, carte_db):
    if nome in MS.BASI:
        return 10 ** 6
    c = carte_db.get(nome) or {}
    if MS.QUALSIASI.search(c.get("testo") or ""):
        return 10 ** 6
    if fmt in MS.SINGLETON:
        return 1
    s = PZ.carta(nome)
    if s and MS.SCRYFALL.get(fmt) in (s.get("r") or "").split():
        return 1
    return 4


class Costruttore:
    APERTO = None       # il builder aperto: la Collection gli manda le carte trascinate

    def __init__(self, pagina, sez="build", m=None):
        if Costruttore.APERTO is not None and Costruttore.APERTO.w.winfo_exists():
            Costruttore.APERTO.chiudi()
        Costruttore.APERTO = self
        self.pg, self.sez = pagina, sez
        tk, F = pagina.tk, pagina.F
        self.tk, self.F = tk, F
        self.m = dict(m) if m else None
        self.zone = {z: dict((m or {}).get(k) or {}) for z, k in (("Deck", "lista"), ("Sideboard", "side"), ("Commander", "comandante"))}
        self.compagno = dict((m or {}).get("compagno") or {})
        # le terre col lucchetto, che Fix mana base non tocca, e se la mana base e' gia' stata fatta (Autore, 8 nov 2026); si salvano con la build
        self.lucchetti = set((m or {}).get("lucchetti") or [])
        self.base_fatta = bool((m or {}).get("base_fatta"))
        self.cambiato = False
        self.carte_db = DM.tabella_carte()
        self.coll, _ = collezione()
        self.jl, _ = jolly()
        self.meta = {}
        self.t_nome = None
        madre = pagina.fr.winfo_toplevel()
        w = self.w = pronta_poi(tk.Toplevel(madre)); w.transient(madre); w.title("Deck builder")
        w.configure(bg=C["scheda"])
        barra_scura(w, C["fondo"], C["titolo"], C["filo"])
        madre.update_idletasks()
        # impaginato come la scheda di un mazzo delle altre sezioni (Autore, 8 nov 2026: «la pagina di deck builder impaginala come una qualsiasi altra pagina deck
        # delle altre sezioni»): sul lato destro della finestra grande, cosi' a sinistra resta un pezzo di Collection da cui trascinare
        L = min(LARGA, max(1000, madre.winfo_width() - 40))
        x = max(madre.winfo_rootx(), madre.winfo_rootx() + madre.winfo_width() - L - 10)
        w.geometry(f"{L}x{min(ALTA, max(640, madre.winfo_height() - 40))}+{x}+{madre.winfo_rooty() + 20}")
        w.minsize(1000, 640)
        w.protocol("WM_DELETE_WINDOW", self.chiudi); w.bind("<Escape>", lambda e: self.chiudi())
        w.bind("<MouseWheel>", self.rotella)
        prepara_capsule(CC.carica())
        self.lista_m = CAP.Liste(tk, F, alto=20)
        self.b = {}
        self.rapporto_terre = None
        self.aree = []
        # la testata, come nella scheda del mazzo: i colori e il nome (qui si scrive), a destra il formato e dove vanno le carte
        cap = tk.Frame(w, bg=C["cap"]); cap.pack(fill="x")
        self.f_colori = tk.Frame(cap, bg=C["cap"]); self.f_colori.pack(side="left", padx=(12, 8), pady=10)
        self.v_nome = tk.StringVar(value=(m or {}).get("nome") or "New build")
        e = tk.Entry(cap, textvariable=self.v_nome, bg=C["cap"], fg=C["titolo"], insertbackground=C["titolo"], relief="flat", font=F(14, True),
                     highlightthickness=1, highlightbackground=C["cap"], highlightcolor=C["accento"])
        e.pack(side="left", fill="x", expand=True, ipady=2); self.v_nome.trace_add("write", lambda *a: self.nome_cambiato())
        self.t_dove = Tendina(tk, cap, "Add to", F, larga=120, bg=C["cap"]); self.t_dove.fr.pack(side="right", padx=(8, 12), pady=(4, 6))
        self.t_dove.opzioni(DOVE, lambda o: None); self.t_dove.set("Deck")
        self.t_fmt = Tendina(tk, cap, "Format", F, larga=150, bg=C["cap"]); self.t_fmt.fr.pack(side="right", pady=(4, 6))
        self.t_fmt.opzioni(MS.FORMATI, lambda o: self.cambia_formato()); self.t_fmt.set((m or {}).get("formato") or "Standard")
        # il mazzo a carte intere anche qui (Autore, 9 nov 2026: «questa option la voglio anche nell'editor di creazione mazzo, solo che anche qui posso trascinare dentro
        # le carte direttamente dalla collezione o avere una tab di ricerca veloce per i nomi»): tavolo_carte.py, sopra il builder, sul suo mazzo
        self.tavolo, self._da_tavolo, self._nomi = None, False, {}
        tk.Frame(w, bg=C["filo"], height=1).pack(fill="x")
        # a sinistra la lista (riceve le carte), a destra i dati dall'alto in basso: le stesse proporzioni della scheda del mazzo
        corpo = tk.Frame(w, bg=C["scheda"]); corpo.pack(fill="both", expand=True, padx=10, pady=8)
        corpo.columnconfigure(0, weight=11, uniform="det"); corpo.columnconfigure(1, weight=10, uniform="det"); corpo.rowconfigure(0, weight=1)
        sx = tk.Frame(corpo, bg=C["scheda"]); sx.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        dx = tk.Frame(corpo, bg=C["scheda"]); dx.grid(row=0, column=1, sticky="nsew")
        self.barra_jolly = tk.Frame(sx, bg=C["cap"], padx=8, pady=4); self.barra_jolly.pack(fill="x", pady=(0, 6))     # i jolly sopra la lista, come nella scheda
        self.f_esporta = tk.Frame(sx, bg=C["scheda"]); self.f_esporta.pack(side="bottom", fill="x", pady=(6, 0))      # l'esportazione sotto la lista
        # il Board sotto il mazzo, al centro, in arancio (Autore, 10 nov 2026: «anche nell'editor board mettilo come colore diverso sotto al mazzo»): qui e' la
        # modalita' edit, col Board con tutti gli strumenti; nella finestra del mazzo lo stesso pulsante apre il Board da guardare
        sotto_l = tk.Frame(sx, bg=C["scheda"]); sotto_l.pack(side="bottom", fill="x", pady=(6, 0))
        self.b_board = pulsante_solido(tk, F, sotto_l, "Board", False, self.vista_carte, alto=28, bg=C["scheda"], colori=ARANCIO)
        self.b_board.configure(width=150); self.b_board.pack(anchor="center")
        tk.Label(sx, text="Drag cards here from the Collection, or double click them there · click a card to remove one copy, right click to add one",
                 bg=C["scheda"], fg=C["grigio"], font=F(8), anchor="w").pack(fill="x", pady=(0, 4))
        self.area_lista = tk.Frame(sx, bg=C["scheda"], highlightthickness=2, highlightbackground=C["scheda"]); self.area_lista.pack(fill="both", expand=True)
        self.cv_m, self.dentro_m = self.scorre(self.area_lista)
        self.msg = tk.Label(dx, text="", bg=C["scheda"], fg=C.get("giallo", C["accento"]), font=F(8, True), anchor="w"); self.msg.pack(fill="x")
        self.cv_d, self.dentro_d = self.scorre(dx)
        self.formato_collezione()
        self.ridisegna()

    # ------------------------------------------------------------ le aree che scorrono
    def scorre(self, padre):
        tk = self.tk
        cv = tk.Canvas(padre, bg=C["scheda"], highlightthickness=0, bd=0); cv.pack(fill="both", expand=True)
        d = tk.Frame(cv, bg=C["scheda"]); win = cv.create_window(0, 0, window=d, anchor="nw")
        d.bind("<Configure>", lambda e: cv.configure(scrollregion=(0, 0, 0, d.winfo_reqheight())))
        cv.bind("<Configure>", lambda e: cv.itemconfigure(win, width=e.width))
        self.aree.append((cv, d))
        return cv, d

    def rotella(self, e):
        """Una rotella sola per la finestra: scorre la colonna sotto il mouse."""
        for cv, d in self.aree:
            if str(e.widget).startswith(str(cv)) and d.winfo_reqheight() > cv.winfo_height():
                cv.yview_scroll(-2 if e.delta > 0 else 2, "units")
                return

    # ------------------------------------------------------------ dalla Collection
    def sopra(self, x_root, y_root):
        """Il punto dello schermo sta sopra il builder? (la Collection lo chiede mentre trascini)"""
        try:
            w = self.w.winfo_containing(x_root, y_root)
        except Exception:
            return False
        return w is not None and str(w).startswith(str(self.w))

    def evidenzia(self, on):
        """Mentre una carta passa sopra la finestra, il mazzo si accende: e' li' che cade."""
        self.area_lista.configure(highlightbackground=C["accento"] if on else C["scheda"])

    def formato_collezione(self):
        """La Collection mostra le carte del formato del builder: dal 9 nov 2026 sa farlo per tutti i formati di Arena (PaginaCollezione.FORMATI_COLL); per Pioneer, Modern e gli altri
        di carta tutte le carte."""
        col = getattr(PaginaCollezione, "ISTANZA", None)
        if col is None or not col.fr.winfo_exists():      # una Collection chiusa (le prove ne aprono e chiudono): niente da allineare
            return
        voluto = self.t_fmt.get() if self.t_fmt.get() in PaginaCollezione.FORMATI_COLL else "All"
        if col.t_formato.get() != voluto:
            col.t_formato.set(voluto); col.chiedi()

    # ------------------------------------------------------------ il mazzo
    def disegna_mazzo(self):
        tk, F = self.tk, self.F
        self.t_nome = None
        svuota(self.dentro_m)
        main = self.zone["Deck"]
        voci = [(q, n) for n, q in {**self.zone["Commander"], **main}.items()]
        tinte = [k for k in "WUBRG" if k in {k for _q, n in voci for k in CAP.info(n)[1]}]
        svuota(self.f_colori)
        self.pg.mana_label(self.f_colori, "".join(tinte), C["cap"]).pack(side="left")
        if voci:
            self.lista_m.testata(self.dentro_m, self.v_nome.get() or "Deck", sum(main.values()) + sum(self.zone["Commander"].values()),
                                 100 if self.t_fmt.get() == "Brawl" else 60, CAP.curva(voci), CAP.copertina(voci), tinte, bg=C["scheda"]).pack(fill="x", pady=(0, 6))
        else:
            tk.Label(self.dentro_m, text="Empty: drag cards from the Collection, or Import a list you copied", bg=C["scheda"], fg=C["grigio"], font=F(9),
                     anchor="w").pack(fill="x", pady=10)
        colonne = tk.Frame(self.dentro_m, bg=C["scheda"]); colonne.pack(fill="x")
        colonne.columnconfigure(0, weight=1, uniform="lista"); colonne.columnconfigure(1, weight=1, uniform="lista")
        c_magie = tk.Frame(colonne, bg=C["scheda"]); c_magie.grid(row=0, column=0, sticky="new", padx=(0, 8))
        c_resto = tk.Frame(colonne, bg=C["scheda"]); c_resto.grid(row=0, column=1, sticky="new")
        terre = {n: q for n, q in main.items() if MS.e_terra(n, self.carte_db)}
        magie = any(n not in terre for n in main) or bool(self.zone["Commander"])
        parti = [(c_magie, "COMMANDER", "Commander", self.zone["Commander"]), (c_magie, "SPELLS", "Deck", {n: q for n, q in main.items() if n not in terre}),
                 (c_resto, "LANDS", "Deck", terre), (c_resto, "SIDEBOARD", "Sideboard", self.zone["Sideboard"])]
        for padre, titolo, zona, carte in parti:
            lands = titolo == "LANDS"
            if not carte and not (lands and magie):
                continue
            if lands:
                # la sezione delle terre ha il suo pulsante (Autore, 8 nov 2026: «il pulsante manabase spostalo e mettilo nella sezione lands dell'editor, quando lo si
                # preme genera la mana base, se il giocatore fa modifiche puo' mettere un lucchettino alle terre da tenere e sopra le terre ci sara' il pulsante fix
                # manabase che corregge dopo i cambiamenti del giocatore tenendo pero' le terre con il lucchettino»)
                h = tk.Frame(padre, bg=C["scheda"]); h.pack(fill="x", pady=(0, 3))
                tk.Label(h, text=f"{titolo} · {sum(carte.values())}", bg=C["scheda"], fg=C["titolo"], font=F(7, True), anchor="w").pack(side="left")
                casa = {}
                casa["b"] = pulsante_solido(tk, F, h, "Fix mana base" if self.base_fatta else "Mana base", False, lambda casa=casa: self.terre_fix(casa["b"]),
                                               alto=22, bg=C["scheda"])
                casa["b"].configure(width=120); casa["b"].pack(side="right")
                self.b["Mana base"] = casa["b"]
            else:
                tk.Label(padre, text=f"{titolo} · {sum(carte.values())}", bg=C["scheda"], fg=C["titolo"], font=F(7, True), anchor="w").pack(fill="x", pady=(0, 3))
            voci = CAP.ordina(list(carte.items()))
            for n, q in voci:
                self.lista_m.schede[n] = self.pg.dati_carta(n, sum(self.zone[k].get(n, 0) for k in self.zone), self.coll)
            if not lands:       # magie, comandante e sideboard: una tela per la lista, non una per capsula (11 nov 2026); clic toglie una copia, destro ne aggiunge una
                el = self.lista_m.elenco(padre, voci, bg=C["scheda"]); el.pack(fill="x")
                for r, n, _q, _o in el.righe:
                    r.cursore = "hand2"
                    r.bind("<Button-1>", lambda e, n=n, z=zona: self.metti(n, -1, z), add=True)
                    r.bind("<Button-3>", lambda e, n=n, z=zona: self.metti(n, 1, z), add=True)
                tk.Frame(padre, bg=C["scheda"], height=8).pack(fill="x")
                continue
            for n, q in voci:
                if lands:      # il lucchetto a sinistra della terra: chiuso = Fix mana base la tiene
                    fr = tk.Frame(padre, bg=C["scheda"]); fr.pack(fill="x")
                    self.lucchetto(fr, n).pack(side="left", padx=(0, 3))
                    r = self.lista_m.riga(fr, n, q, bg=C["scheda"])
                    r.pack(side="left", fill="x", expand=True)
                else:
                    r = self.lista_m.riga(padre, n, q, bg=C["scheda"])
                    r.pack(fill="x")
                r.bind("<Button-1>", lambda e, n=n, z=zona: self.metti(n, -1, z), add="+")
                r.bind("<Button-3>", lambda e, n=n, z=zona: self.metti(n, 1, z), add="+")
            tk.Frame(padre, bg=C["scheda"], height=8).pack(fill="x")
        # l'esportazione sotto la lista, la stessa della scheda del mazzo, piu' le azioni del builder
        svuota(self.f_esporta)
        PaginaStandard.esportazione(self.pg, self.f_esporta, self.v_nome.get() or "Deck", dict(main), dict(self.zone["Sideboard"]), dict(self.zone["Commander"]),
                                       dict(self.compagno), [("Import", self.importa, False), ("Clear", self.svuota_ora, True), ("Save", lambda: self.salva() and "Saved", False)])

    def lucchetto(self, padre, nome):
        """Il lucchetto disegnato (i simboli si disegnano, non si scrivono, 7 nov 2026): chiuso e azzurro, o aperto e grigio. Clic = cambia."""
        tk = self.tk
        chiuso = nome in self.lucchetti
        c = tk.Canvas(padre, width=18, height=20, bg=C["scheda"], highlightthickness=0, bd=0, cursor="hand2")
        col = C["accento"] if chiuso else C["grigio"]
        c.create_image(0, 1, image=DG.lucchetto(18, chiuso, col), anchor="nw")      # aperto: l'arco alzato e spostato, una gamba sola, il corpo vuoto

        def cambia(e=None):
            self.lucchetti ^= {nome}
            self.segna(); self.disegna_mazzo()
        c.bind("<Button-1>", cambia)
        return c

    def metti(self, nome, d, zona=None):
        """Una copia in piu' (d=1) o in meno (d=-1) nella zona; oltre il limite del formato non si va."""
        zona = zona or self.t_dove.get()
        z = self.zone[zona]
        self.rapporto_terre = None          # il rapporto della Mana base vale finche' il mazzo non cambia a mano
        if d > 0:
            tutte = sum(self.zone[k].get(nome, 0) for k in self.zone)
            lim = limite(nome, self.t_fmt.get(), self.carte_db)
            if tutte >= lim:
                self.avviso(f"{nome}: max {lim} in {self.t_fmt.get()}")
                return False
            z[nome] = z.get(nome, 0) + 1
        elif nome in z:
            z[nome] -= 1
            if z[nome] <= 0:
                del z[nome]
        self.segna()
        self.ridisegna()
        if d > 0:
            self.avviso(f"+1 {nome}")
        return True

    # ------------------------------------------------------------ i dati
    def avviso(self, t):
        self.msg.configure(text=t)
        self.w.after(3000, lambda: self.msg.winfo_exists() and self.msg.cget("text") == t and self.msg.configure(text=""))

    def disegna_dati(self):
        tk, F = self.tk, self.F
        d = self.dentro_d
        svuota(d)
        fmt = self.t_fmt.get()
        main, side, com = self.zone["Deck"], self.zone["Sideboard"], self.zone["Commander"]
        tutte = dict(main)
        for z in (side, com):
            for n, q in z.items():
                tutte[n] = tutte.get(n, 0) + q
        manca, si = craft(tutte, self.coll, self.jl)
        svuota(self.barra_jolly)
        self.pg.riquadro_jolly(self.barra_jolly, manca, si, self.jl)
        magie = [(n, q) for n, q in main.items() if not MS.e_terra(n, self.carte_db)]
        mn = MS.mana({**com, **main}, self.carte_db)
        # i numeri: la stessa griglia della scheda di una build (PaginaStandard.voci_build), coi prezzi in fondo
        eur, usd, senza = PZ.totale(tutte)
        tix = sum(q * ((PZ.prezzo(n) or {}).get("tix") or 0) for n, q in tutte.items())
        voci = PaginaStandard.voci_build(self.pg, dict(formato=fmt), main, side, com, self.compagno, self.coll, self.carte_db)
        problemi = self.pg._problemi
        voci += [("paper price", PZ.euro(eur) if tutte and len(senza) < len(tutte) else "-", None,
                  ((f"${usd:,.0f}" if usd >= 100 else f"${usd:.2f}") if tutte else "") + (f" · {sum(tutte[n] for n in senza)} digital only" if senza else "")),
                 ("mtgo price", f"{tix:,.1f} tix" if tix else "-", None)]
        self.pg.griglia(d, voci, colonne=4, grande=11, stretta=True)
        if problemi:      # i problemi di legalita', uno per riga, sotto i numeri
            tk.Label(d, text="\n".join(problemi[:6]) + (f"\n+{len(problemi) - 6} more" if len(problemi) > 6 else ""), bg=C["scheda"], fg=C["rosso_t"],
                     font=F(8), anchor="w", justify="left").pack(fill="x", pady=(0, 6))
        r = self.rapporto_terre
        if r:
            lf = tk.Frame(d, bg=C["cap"], padx=8, pady=6); lf.pack(fill="x", pady=(0, 8))
            self.pg.etichetta(lf, "mana base", C["cap"]).pack(anchor="w")
            agg = ", ".join(f"{q} {n}" for n, q in sorted(r["aggiungi"].items(), key=lambda x: (x[0] in ("Plains", "Island", "Swamp", "Mountain", "Forest"), x[0])))
            righe_r = []
            for t, col in ((f"{r['terre']} lands for {r['carte']} cards · {r['obiettivo']}", C["azzurro"]),
                           ("Added: " + (agg or "nothing"), C["testo"]),
                           ("Sources (have / need, Karsten): " + "  ".join(f"{k} {h}/{s_}{' ✓' if h >= s_ else ' ✗'}" for k, (h, s_) in r["fonti"].items()), C["testo"]),
                           ("To craft: " + ", ".join(f"{q} {n}" for n, q in r["mancano"].items()) if r["mancano"] else "You own all the lands added", C["rosso_t"] if r["mancano"] else C["verde_t"])):
                l_ = tk.Label(lf, text=t, bg=C["cap"], fg=col, font=F(8), anchor="w", justify="left", wraplength=420); l_.pack(fill="x"); righe_r.append(l_)
            lf.bind("<Configure>", lambda e: [x.configure(wraplength=max(200, e.width - 20)) for x in righe_r if x.winfo_exists()])
        # il grafo dell'archetipo, come nella scheda (quadro_mazzo: senza partite restano solo l'archetipo e il suo grafo)
        media = tk.Frame(d, bg=C["scheda"]); media.pack(fill="x", pady=(0, 6))
        PaginaStandard.quadro_mazzo(self.pg, media, None, DM.archetipo({**com, **main}, self.carte_db) if main else None)
        self.pg.etichetta(d, "mana curve · spells", C["scheda"]).pack(anchor="w", pady=(10, 3))
        conti = [0] * 8
        for n, q in magie:
            conti[min(7, int(CAP.info(n)[2] or 0))] += q
        cv = tk.Canvas(d, height=104, bg=C["scheda"], highlightthickness=0); cv.pack(fill="x")

        def curva(e=None):
            cv.delete("all")
            L = cv.winfo_width()
            if L < 50:
                return
            alto, top = 70, max(conti) or 1
            passo = L / 8
            for i, q in enumerate(conti):
                h = alto * q / top
                x0 = i * passo + 6
                cv.create_rectangle(x0, 16 + alto - h, x0 + passo - 12, 16 + alto, fill=C["accento"] if q else C["filo"], width=0)
                if q:
                    cv.create_text(x0 + (passo - 12) / 2, 16 + alto - h - 1, text=str(q), anchor="s", fill=C["testo"], font=F(7, True))
                cv.create_text(x0 + (passo - 12) / 2, 16 + alto + 10, text="7+" if i == 7 else str(i), fill=C["grigio"], font=F(7))
        cv.bind("<Configure>", curva)
        # le terre nella mano iniziale: la probabilita' esatta di 0-7 terre nelle prime 7 carte (ipergeometrica, mazzi_salvati.mana)
        if mn["carte"]:
            self.pg.etichetta(d, "lands in opening hand · 7 cards", C["scheda"]).pack(anchor="w", pady=(10, 3))
            cm = tk.Canvas(d, height=104, bg=C["scheda"], highlightthickness=0); cm.pack(fill="x")
            prob = [mn["mano"].get(k, 0.0) for k in range(8)]

            def mano(e=None):
                cm.delete("all")
                L = cm.winfo_width()
                if L < 50:
                    return
                alto, top = 70, max(prob) or 1
                passo = L / 8
                for i, p in enumerate(prob):
                    h = alto * p / top
                    x0 = i * passo + 6
                    buona = 2 <= i <= 5
                    cm.create_rectangle(x0, 16 + alto - h, x0 + passo - 12, 16 + alto, fill=(C["accento"] if buona else C["grigio"]) if p >= 0.005 else C["filo"], width=0)
                    if p >= 0.005:
                        cm.create_text(x0 + (passo - 12) / 2, 16 + alto - h - 1, text=f"{round(100 * p)}%", anchor="s", fill=C["testo"], font=F(7, True))
                    cm.create_text(x0 + (passo - 12) / 2, 16 + alto + 10, text=str(i), fill=C["grigio"], font=F(7))
            cm.bind("<Configure>", mano)

    # ------------------------------------------------------------ azioni
    def ridisegna(self):
        self.disegna_mazzo()
        self.disegna_dati()
        t = self.tavolo_aperto()
        if t is not None and not self._da_tavolo:       # cambiato qui (o dalla Collection col doppio clic): il tavolo si allinea
            t.allinea(self.zone["Deck"], self.zone["Sideboard"], {**self.zone["Commander"], **self.compagno})

    # ------------------------------------------------------------ il tavolo delle carte intere
    def tavolo_aperto(self):
        t = getattr(self, "tavolo", None)
        try:
            return t if t is not None and t.fin.winfo_exists() else None
        except Exception:
            return None

    def vista_carte(self):
        """Il mazzo del builder a carte intere: il tavolo copre il builder alla sua misura, cosi' a sinistra resta la Collection da cui trascinare. Ogni cambio sul tavolo
        torna qui (dal_tavolo), ogni cambio qui torna sul tavolo (ridisegna)."""
        import tavolo_carte as TC
        t = self.tavolo_aperto()
        if t is not None:
            t.fin.lift(); return t
        self.w.update_idletasks()
        # la stessa disposizione della scheda del mazzo (Autore, 9 nov 2026: «alla riapertura mantenga il posizionamento che ho creato»); prima il builder ne
        # teneva una sua, «builder:<id>», che resta come ripiego
        chiave = f"{self.sez}:{self.m['id']}" if self.m and self.m.get("id") else None
        self.tavolo = TC.TavoloCarte(self.tk, self.F, self.w, self.v_nome.get() or "Deck", dict(self.zone["Deck"]), dict(self.zone["Sideboard"]),
                                     dict(self.zone["Commander"]), dict(self.compagno), carte_db=self.carte_db, chiave=chiave, editore=self.dal_tavolo,
                                     limite=lambda n: limite(n, self.t_fmt.get(), self.carte_db), formato=self.t_fmt.get(), nomi_ricerca=self.nomi_formato,
                                     geometria=self.w.geometry(), chiave_rete=chiave, chiave_vecchia=f"builder:{self.m['id']}" if chiave else None)
        return self.tavolo

    def dal_tavolo(self, lista, side):
        """Il tavolo ha cambiato il mazzo: il builder prende la lista nuova (salva lui, come sempre)."""
        self.zone["Deck"], self.zone["Sideboard"] = dict(lista), dict(side)
        self.rapporto_terre = None
        self.segna()
        self._da_tavolo = True
        try:
            self.ridisegna()
        finally:
            self._da_tavolo = False

    def nomi_formato(self):
        """I nomi per la ricerca veloce: le carte del formato del builder, come le mostra la Collection (Standard: il pool; gli altri: Scryfall). Una volta per formato."""
        fmt = self.t_fmt.get()
        if self._nomi.get("fmt") != fmt:
            col = getattr(PaginaCollezione, "ISTANZA", None)
            carte = None
            try:
                if col is not None and col.d and fmt in PaginaCollezione.FORMATI_COLL:
                    carte = col.nel_formato(fmt)
                    if fmt == "Standard":
                        carte = [c for c in carte if c.get("standard")]
            except Exception:
                carte = None
            nomi = sorted({c["nome"] for c in carte}) if carte else sorted(self.carte_db)
            self._nomi = dict(fmt=fmt, nomi=nomi)
        return self._nomi["nomi"]

    def segna(self):
        self.cambiato = True

    def nome_cambiato(self):
        """La testata del mazzo segue il nome, senza ridisegnare a ogni lettera."""
        self.segna()
        if self.t_nome is not None:
            self.w.after_cancel(self.t_nome)
        self.t_nome = self.w.after(400, self.disegna_mazzo)

    def cambia_formato(self):
        self.segna()
        self.formato_collezione()
        self.ridisegna()

    def campi(self):
        return dict(nome=self.v_nome.get().strip() or "New build", formato=self.t_fmt.get(), lista=dict(self.zone["Deck"]), side=dict(self.zone["Sideboard"]),
                    comandante=dict(self.zone["Commander"]), compagno=dict(self.compagno), lucchetti=sorted(self.lucchetti), base_fatta=self.base_fatta)

    def importa(self, b=None):
        """La lista negli appunti al posto di quella di adesso, come l'Import di Arena."""
        try:
            testo = self.w.clipboard_get()
        except Exception:
            testo = ""
        z = MS.leggi_lista(testo)
        if not z["lista"] and not z["comandante"]:
            self.avviso("Nothing to import: copy a deck list first")
            return
        self.zone = {"Deck": z["lista"], "Sideboard": z["side"], "Commander": z["comandante"]}
        self.compagno = z["compagno"]
        if z["nome"]:
            self.v_nome.set(z["nome"])
        if z["comandante"] and self.t_fmt.get() not in MS.SINGLETON:
            self.t_fmt.set("Brawl")
        self.segna()
        self.ridisegna()
        self.avviso(f"Imported {sum(z['lista'].values()) + sum(z['comandante'].values())} cards")

    def esporta(self, b=None):
        """La lista negli appunti nel formato che Arena importa (Decks › Import), come «Copy for Arena» della finestra del mazzo."""
        if not self.zone["Deck"] and not self.zone["Commander"]:
            self.avviso("The deck is empty")
            return
        self.w.clipboard_clear()
        self.w.clipboard_append(lista_arena(self.zone["Deck"], self.zone["Sideboard"], self.zone["Commander"], self.compagno))
        self.w.update()
        if b is not None:
            b.metti("Copied", False); b.after(2500, lambda: b.winfo_exists() and b.metti("Export to Arena", False))
        self.avviso("Copied: in Arena, Decks › Import")

    def terre_fix(self, b=None):
        """Mana base (Autore, 8 nov 2026, il pulsante prima chiamato Land fix: «fai solo un pulsante che si chiama land fix che aggiunge tutte le terre mancanti migliori per il deck»): le terre che
        ci sono restano, si aggiungono quelle che mancano (Companion/App/Schede/Collection/terre_auto.py), possedute o no; nei dati restano quante, perche', le fonti e cosa craftare.
        Dopo la prima volta il pulsante e' Fix mana base (8 nov 2026): le terre senza lucchetto si tolgono e la mana base si rifa' intorno a quelle col lucchetto."""
        import terre_auto as TA
        fmt = self.t_fmt.get()
        if self.base_fatta:          # Fix mana base: restano solo le terre col lucchetto
            for n in [n for n in self.zone["Deck"] if MS.e_terra(n, self.carte_db) and n not in self.lucchetti]:
                del self.zone["Deck"][n]
        deck = dict(self.zone["Deck"])
        for n, q in self.zone["Commander"].items():
            deck[n] = deck.get(n, 0) + q
        if not any(not MS.e_terra(n, self.carte_db) for n in deck):
            self.avviso("Add some spells first: the lands follow the spells")
            return
        if fmt not in self.meta and fmt in dict(FORMATI_META):
            self.meta[fmt] = meta_mazzi(fmt)[0]
        liste = [m.get("lista") or {} for m in self.meta.get(fmt) or []]

        def legale(n):
            return not [p for p in MS.legalita({n: 1}, {}, fmt) if n in p]

        base = {v: k for k, v in TA.BASE_DI.items()}

        def prodotti(n):
            """I colori che la terra produce: le basi dal nome, le altre da Scryfall (produced_mana), se no dai colori della carta su Arena."""
            return base.get(n) or (PZ.carta(n) or {}).get("p") or (self.carte_db.get(n) or {}).get("colori") or ""
        r = TA.fix(deck, fmt, self.carte_db, legale, prodotti,
                   lambda n: MS.e_terra(n, self.carte_db), lambda n: CAP.info(n)[2] or 0, self.coll, liste,
                   N=100 if fmt == "Brawl" else 60, copie_max=1 if fmt in MS.SINGLETON else 4)
        for n, q in r["aggiungi"].items():
            self.zone["Deck"][n] = self.zone["Deck"].get(n, 0) + q
        fix = self.base_fatta
        self.base_fatta = True
        self.rapporto_terre = r
        self.segna(); self.ridisegna()       # il pulsante si ridisegna col nome nuovo
        self.avviso(("Fix mana base" if fix else "Mana base") + (f": +{sum(r['aggiungi'].values())} lands" if r["aggiungi"] else ": the lands are already enough"))

    def esporta_mtgo(self, b=None):
        """La lista negli appunti nel formato di MTGO e dei siti («4 Nome», riga vuota, sideboard), come «Copy for MTGO / text» della scheda del mazzo."""
        if not self.zone["Deck"] and not self.zone["Commander"]:
            self.avviso("The deck is empty")
            return
        self.w.clipboard_clear()
        self.w.clipboard_append(lista_mtgo(self.zone["Deck"], self.zone["Sideboard"], self.zone["Commander"], self.compagno))
        self.w.update()
        if b is not None:
            b.metti("Copied", False); b.after(2500, lambda: b.winfo_exists() and b.metti("Export to MTGO", False))
        self.avviso("Copied: MTGO / text list")

    def svuota(self, b):
        if not getattr(self, "_armato", False):
            self._armato = True
            b.metti("Click again", True)
            b.after(2500, lambda: b.winfo_exists() and (setattr(self, "_armato", False), b.metti("Clear", False)))
            return
        self._armato = False
        b.metti("Clear", False)
        self.zone = {"Deck": {}, "Sideboard": {}, "Commander": {}}
        self.compagno = {}
        self.segna()
        self.ridisegna()

    def svuota_ora(self):
        """Clear dall'esportazione della scheda: il secondo clic di conferma lo chiede gia' il pulsante."""
        self.zone = {"Deck": {}, "Sideboard": {}, "Commander": {}}
        self.compagno = {}
        self.segna()
        self.ridisegna()

    def salva(self, b=None):
        if self.m:
            self.m = MS.cambia(self.sez, self.m["id"], **self.campi()) or MS.aggiungi(self.sez, self.campi())
        else:
            self.m = MS.aggiungi(self.sez, self.campi())
        t = self.tavolo_aperto()
        if t is not None and self.m and self.m.get("id"):       # il primo Save da' l'id: il tavolo aperto salva da qui sotto la chiave del mazzo
            t.nuova_chiave(f"{self.sez}:{self.m['id']}", f"{self.sez}:{self.m['id']}")
        self.cambiato = False
        self.pg.sporco = True
        if hasattr(self.pg, "sezione") and self.pg.davanti():
            self.pg.disegna()
        if b is not None:
            b.metti("Saved", False); b.after(2000, lambda: b.winfo_exists() and b.metti("Save", False))
        return self.m

    def chiudi(self):
        t = self.tavolo_aperto()
        if t is not None:
            t.chiudi()
        if self.cambiato and (self.zone["Deck"] or self.zone["Commander"]):
            self.salva()
        self.lista_m.esci()
        if Costruttore.APERTO is self:
            Costruttore.APERTO = None
        self.w.destroy()
