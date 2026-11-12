"""La scheda Performance: l'analizzatore di partite e di situazioni (Autore, 12 nov 2026: «riusciamo a modificarla per farla diventare come un analizzatore di
partite ma anche di situazioni come in holdem manager? la possibilita' di aggiungere variabili che ci mostrano come i grafici cambiano», poi «Sì, costruiscila» sulla
proposta). Fino a quel giorno la scheda erano le pagine Limited e Standard con la tendina Mode (pagina_limited, pagina_standard: le classi restano, Your decks
eredita da PaginaStandard).

In testa Constructed o Limited. A sinistra le variabili: ogni tendina filtra (Any = tutte), coi conti delle partite di ogni valore sotto gli altri filtri; sotto, le
situazioni salvate. A destra i numeri della situazione (win rate con l'intervallo di Wilson, record, turni, mulligan, play e draw, quante partite), il grafico
(win rate, partite, turni medi, mulligan; per partite o per data; cumulativo o sulle ultime N; diviso per una variabile, una linea per valore), e il report
raggruppato per una variabile: il clic su una riga la mette fra i filtri, il clic su una colonna ordina. Sotto 15 partite una riga e' grigia: un indizio.
Le viste stanno in cartelle (Chart, Spots, Report, Matchups, Compare), e ognuna si stacca in una finestra sua (12 nov 2026, Autore: «questi falli a modo di
cartelle e poi tira via il sotto testo / poi procedi con i confronti situazionali / ogni sezione di ogni cartella si puo' staccare dal quadro e renderla una
finestra a se stante»). Compare mette la situazione (A) contro il resto, tutte le partite o una situazione salvata (B), con la significativita'.
I dati: dati_analizzatore (i nostri log, dal 22 set 2026)."""
import datetime
import math
import threading

import dati_analizzatore as DA
import disegni as DG
from tema import CI as C
from widget import Tendina, pulsante_solido

LINEE = ("#d8d8dc", "#24baff", "#f0ad4e", "#a58cff", "#5cb85c", "#ee8a87")      # All, poi i valori: lontani fra loro anche per i daltonici (come il resto dell'app)
COLONNE = (("nome", "", 250), ("n", "GAMES", 70), ("wl", "W-L", 80), ("wr", "WIN RATE", 180), ("play", "PLAY", 70), ("draw", "DRAW", 70), ("mull", "MULL.", 70),
           ("turni", "AVG T", 70), ("delta", "Δ VS ALL", 90))
TIPI = ("Constructed", "Limited")
VISTE = (("chart", "Chart"), ("spots", "Spots"), ("report", "Report"), ("matchups", "Matchups"), ("compare", "Compare"))
DISEGNI = {"chart": "disegna_grafico", "spots": "disegna_spot", "report": "disegna_report", "matchups": "disegna_matchup", "compare": "disegna_confronto"}
GRIGI = ("#2a2a30", "#3a3a42", "#0f86cc")       # i pulsanti a pillola grigi, azzurri se scelti
ALTO_TAB, LARGA_TAB = 34, 132                   # le cartelle
LARGA_DECK = 1000                               # la finestra By deck
# per fasi della partita (12 nov 2026, Autore: «il menu a tendine creiamolo per macro fasi partita: formato evento e deck - poi start e mulligan - lands in
# hand / cards in hand possiamo toglierlo, their card anche»): prima della partita (con By deck), l'apertura, l'avversario, com'e' finita, quando.
# «deck» e' il pulsante By deck; Card in hand e Their card non sono tendine (restano in Split by, Group by e negli Spots)
FASI = (("BEFORE THE GAME", ("miei_colori",)),
        ("OPENING AND FIRST TURNS", ("economiche", "crea_mano", "sit:io_terra", "sit:lui_terra", "sit:io_curva", "sit:io_crea2", "sit:lui_crea2")),
        ("THE OPPONENT AND THE FIGHT", ("sit:io_primo", "sit:io_nel_suo", "sit:lui_nel_mio", "sit:lui_bersagli", "sit:io_att_aperto", "sit:io_att_chiuso",
                                        "sit:lui_att_aperto", "sit:io_passa_aperto", "sit:lui_passa_aperto")),
        ("THE END OF THE GAME", ("fine", "sit:io_morti", "sit:lui_morti")),
        ("WHEN", ("giorno", "pausa")))      # i filtri in piu' di ogni fase, nel suo +
LARGA_FASE = 780
SEZIONI_FILTRI = (("formato", "evento", "deck"), ("partenza", "mull", "terre"), ("suo", "colori"), ("lunga", "rango"), ("data", "fascia", "sessione"))


def _cartella(x0, x1, top, H, sl=6, r=5):
    """Il contorno di una linguetta da cartella: i fianchi un po' inclinati e gli angoli in alto arrotondati, da (x0, H) a (x1, H)."""
    pts = [(x0, H)]
    cx, cy = x0 + sl + r, top + r
    for i in range(7):
        a = math.pi - (math.pi / 2) * i / 6
        pts.append((cx + r * math.cos(a), cy - r * math.sin(a)))
    cx = x1 - sl - r
    for i in range(7):
        a = math.pi / 2 - (math.pi / 2) * i / 6
        pts.append((cx + r * math.cos(a), cy - r * math.sin(a)))
    pts.append((x1, H))
    return pts


def _segno_stacca(d, cx, cy, colore, fuori):
    """Il segno per staccare una cartella: un riquadro con la freccia che esce in alto a destra; staccata, la freccia rientra."""
    d.rett(cx - 6, cy - 3, cx + 4, cy + 7, bordo=colore, larghezza=1.2, raggio=1.5)
    if fuori:
        d.linea([(cx + 6, cy - 6), (cx, cy)], colore, 1.3)
        d.linea([(cx - 0.5, cy - 4), (cx, cy), (cx + 4, cy + 0.5)], colore, 1.3)
    else:
        d.linea([(cx - 1, cy + 1), (cx + 6, cy - 6)], colore, 1.3)
        d.linea([(cx + 1.5, cy - 6), (cx + 6, cy - 6), (cx + 6, cy - 1.5)], colore, 1.3)


def _colore_wr(w):
    """Il fondo di una cella della matrice: dal rosso (sotto il 50%) all'azzurro (sopra), scuro vicino al 50."""
    t = max(-1.0, min(1.0, (w - 50) / 25))
    a, b = ((36, 186, 255) if t > 0 else (217, 83, 79)), (32, 32, 38)
    k = abs(t) * 0.75
    return "#%02x%02x%02x" % tuple(round(b[i] + (a[i] - b[i]) * k) for i in range(3))


def modo_iniziale(draft, partite, aperto):
    """Da dove parte Performance: Limited con un draft aperto, se no il formato dell'ultima partita giocata (a pari merito o senza partite, Limited)."""
    if aperto:
        return "Limited"
    ultimo = lambda xs: max((x["quando"].timestamp() for x in xs), default=0)
    return "Standard" if ultimo(partite or []) > ultimo(draft or []) else "Limited"


class _Ricevitore:
    """Al posto delle pagine Limited e Standard di prima: la finestra grande le chiama coi dati nuovi; qui vuol dire «ci sono partite nuove, rileggi i log»."""

    def __init__(self, pagina):
        self.pagina, self.premi, self.aperto, self.sporca = pagina, None, None, False

    def aggiorna(self, *a, **k):
        self.pagina.ricarica()

    def apri(self, chi):
        return None


class PaginaPerformance:
    MODI = ("Limited", "Standard")

    def __init__(self, tk, padre, F, mana):
        self.tk, self.F = tk, F
        self.fr = tk.Frame(padre, bg=C["fondo"])
        self.limited, self.standard = _Ricevitore(self), _Ricevitore(self)
        self.tipo = "Constructed"
        self.filtri = {}
        self.metrica, self.asse, self.finestra, self.dividi, self.per, self.ordina = "wr", "games", "20", None, "suo", "n"
        self.basso, self.solo_meta, self.vista = "report", False, "chart"       # la vista del pannello: chart, spots, report, matchups o compare
        self.con, self.staccate, self.vs_modo = "rest", {}, "all"        # B del confronto (rest, all, s<i>); le viste staccate: {vista: dict(win, o, l)}
        self.righe, self.sporca, self.deciso, self.modo = None, True, False, "Standard"
        self._lavoro = None
        self.costruisci()
        self.fr.bind("<<Davanti>>", lambda e: self.se_sporca(), add="+")
        self.fr.bind("<Map>", lambda e: self.se_sporca(), add="+")
        self.ricarica()

    # ------------------------------------------------------------ la finestra grande
    def segna(self):
        self.sporca = True

    def se_sporca(self):
        if self.sporca and self.righe is not None:
            self.disegna()

    def parti(self, draft, partite, aperto):
        if not self.deciso:
            self.deciso = True
            self.scegli(modo_iniziale(draft, partite, aperto))

    def scegli(self, modo):
        """Limited o Standard (le chiavi di prima, --scheda limited|standard) o direttamente Constructed / Limited."""
        self.deciso = True
        self.modo = modo
        self.cambia_tipo("Limited" if modo == "Limited" else "Constructed")

    def mostra(self, modo):
        self.scegli(modo)

    def ricarica(self):
        """Le partite dai log, su un filo: la pagina resta viva."""
        if self._lavoro is not None and self._lavoro.is_alive():
            self._di_nuovo = True
            return
        self._di_nuovo = False
        esito = {}

        def lavora():
            try:
                esito["r"] = DA.righe()
            except Exception as e:      # noqa: BLE001 - senza log la pagina lo dice
                esito["r"], esito["e"] = [], e
        self._lavoro = threading.Thread(target=lavora, daemon=True)
        self._lavoro.start()

        def aspetta():
            if self._lavoro.is_alive():
                self.fr.after(150, aspetta)
                return
            self.righe = esito.get("r") or []
            self.disegna()
            if self._di_nuovo:
                self.ricarica()
        self.fr.after(150, aspetta)

    # ------------------------------------------------------------ la costruzione
    def costruisci(self):
        tk, F = self.tk, self.F
        testa = tk.Frame(self.fr, bg=C["cap"]); testa.pack(fill="x")
        tk.Label(testa, text="PERFORMANCE", bg=C["cap"], fg=C["titolo"], font=F(11, True)).pack(side="left", padx=(16, 6), pady=10)
        tk.Label(testa, text="analyzer · games and situations from your Arena logs", bg=C["cap"], fg=C["grigio"], font=F(8)).pack(side="left", padx=(0, 18))
        self.b_tipi = {}
        for t in TIPI:
            b = pulsante_solido(tk, F, testa, t, t == self.tipo, lambda t=t: self.cambia_tipo(t), alto=26, bg=C["cap"],
                                colori=("#2a2a30", "#3a3a42", "#0f86cc"))
            b.configure(width=118); b.pack(side="left", padx=(0, 6), pady=8)
            self.b_tipi[t] = b
        # il reset globale (12 nov 2026, Autore: «aggiungiamo anche un reset global che ci porta a tutte le partite di default»): filtri, situazioni, grafico e
        # vista in basso come all'apertura; Constructed o Limited resta
        self.b_reset = pulsante_solido(tk, F, testa, "Reset all", False, self.reset, alto=26, bg=C["cap"], colori=("#2a2a30", "#3a3a42", "#0f86cc"))
        self.b_reset.configure(width=100); self.b_reset.pack(side="right", padx=(8, 16), pady=8)
        self.l_info = tk.Label(testa, text="Reading your logs…", bg=C["cap"], fg=C["grigio"], font=F(8))
        self.l_info.pack(side="right", padx=(16, 4))
        corpo = tk.Frame(self.fr, bg=C["fondo"]); corpo.pack(fill="both", expand=True, padx=10, pady=10)
        corpo.columnconfigure(0, weight=0, minsize=300); corpo.columnconfigure(1, weight=1); corpo.rowconfigure(0, weight=1)
        # a sinistra: le variabili e le situazioni salvate, in una colonna che scorre
        sx = tk.Frame(corpo, bg=C["scheda"], highlightthickness=1, highlightbackground=C["filo"]); sx.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        rs = tk.Frame(sx, bg=C["scheda"]); rs.pack(fill="x", padx=12, pady=(10, 4))
        # «Smart filters» (12 nov 2026, Autore: «i filtri a sinistra potremmo chiamarli smart filters»); il pulsante Add filters (le situazioni) non c'e' piu':
        # le situazioni stanno nel + della loro fase
        tk.Label(rs, text="SMART FILTERS", bg=C["scheda"], fg=C["muto"], font=F(7, True)).pack(side="left")
        via = tk.Label(rs, text="Clear all", bg=C["scheda"], fg=C["accento"], font=F(7, True), cursor="hand2"); via.pack(side="right")
        via.bind("<Button-1>", lambda e: self.pulisci())
        # la colonna scorre: con la rotella sopra qualunque sua parte, e con la barra sottile a destra (fino al 12 nov la rotella andava solo sul fondo vuoto e
        # le ultime tendine e le situazioni salvate restavano tagliate in fondo: Autore, «la finestra degli smart filters e' tagliata sul fondo»)
        riga_sx = tk.Frame(sx, bg=C["scheda"]); riga_sx.pack(fill="both", expand=True)
        barra = tk.Canvas(riga_sx, width=6, bg=C["traccia"], highlightthickness=0, cursor="hand2"); barra.pack(side="right", fill="y", padx=(0, 4), pady=4)

        def segna(a, b_):
            barra.delete("all"); a, b_ = float(a), float(b_)
            if b_ - a < 0.999:
                H_ = barra.winfo_height(); barra.create_rectangle(0, H_ * a, 6, H_ * b_, fill=C["grigio"], width=0)
        self.cv_sx = tk.Canvas(riga_sx, bg=C["scheda"], highlightthickness=0, bd=0, width=280, yscrollcommand=segna); self.cv_sx.pack(side="left", fill="both", expand=True)
        barra.bind("<Button-1>", lambda e: self.cv_sx.yview_moveto(e.y / max(barra.winfo_height(), 1)))
        barra.bind("<B1-Motion>", lambda e: self.cv_sx.yview_moveto(e.y / max(barra.winfo_height(), 1)))
        self.col_sx = tk.Frame(self.cv_sx, bg=C["scheda"])
        self.cv_sx.create_window(0, 0, window=self.col_sx, anchor="nw")
        self.col_sx.bind("<Configure>", lambda e: self.cv_sx.configure(scrollregion=(0, 0, 0, self.col_sx.winfo_reqheight() + 16)))

        def rotella(e):
            w = str(e.widget)
            if (w.startswith(str(self.cv_sx)) or w.startswith(str(barra))) and self.col_sx.winfo_reqheight() > self.cv_sx.winfo_height():
                self.cv_sx.yview_scroll(-2 if e.delta > 0 else 2, "units")
        self.cv_sx.bind_all("<MouseWheel>", rotella, add="+")
        # una riga per filtro, il nome a sinistra e il campo a destra (12 nov 2026, Autore: «impaginiamo meglio, holdem manager tiene tutto non tagliato e
        # sulla stessa pagina»): 15 filtri in ~440 pixel invece di ~870, tutti a vista senza scorrere
        self.tendine = {}
        griglia = tk.Frame(self.col_sx, bg=C["scheda"]); griglia.pack(fill="x", padx=(12, 4))
        griglia.columnconfigure(0, minsize=104)
        # My deck non e' fra le tendine: il mazzo si sceglie con By deck, in fondo (12 nov 2026, Autore: «togli dalle tendine my deck e crea un pulsante in
        # fondo: by deck»)
        # in sezioni separate da una lineetta (stesso giorno, Autore: «opponent, opponent colors e their card spostale insieme dopo lands in hand in una
        # sezione loro separata da una lineetta / poi tutto cio' che ha a che fare con date e orario uguale in fondo / card in hand prima di lands in hand /
        # format e event in una loro sezione»)
        nomi_var = {k_: n_ for k_, n_, _f in DA.VARIABILI}
        riga_g = 0
        self.testate = []
        for j_, sezione in enumerate(SEZIONI_FILTRI):
            # la testa della fase: la lineetta, il nome e il + dei suoi filtri in piu' (12 nov 2026, Autore: «aggiungere a ogni tendina un set di filtri
            # aggiuntivi per ogni step», «Sì, costruiscili»)
            t_ = tk.Canvas(griglia, bg=C["scheda"], highlightthickness=0, bd=0, width=262, height=24 if j_ == 0 else 34, cursor="hand2")
            t_.grid(row=riga_g, column=0, columnspan=2, sticky="ew", pady=(0, 2))
            t_.bind("<Button-1>", lambda e, j=j_: self.apri_fase(j))
            t_.bind("<Configure>", lambda e, j=j_: self.disegna_testata(j))
            self.testate.append(t_)
            riga_g += 1
            for k in sezione:
                if k == "deck":
                    self.b_deck = pulsante_solido(tk, F, griglia, "By deck  ·  all decks vs all", False, self.apri_deck, alto=28, bg=C["scheda"])
                    self.b_deck.configure(width=262); self.b_deck.grid(row=riga_g, column=0, columnspan=2, sticky="ew", pady=(4, 2))
                else:
                    self.riga_filtro(griglia, riga_g, k, nomi_var[k])
                riga_g += 1
        tk.Frame(self.col_sx, bg=C["filo"], height=1).pack(fill="x", padx=12, pady=(10, 8))
        tk.Label(self.col_sx, text="SAVED SITUATIONS", bg=C["scheda"], fg=C["muto"], font=F(7, True)).pack(anchor="w", padx=12)
        self.b_salva_sit = pulsante_solido(tk, F, self.col_sx, "Save this situation", False, self.salva_situazione, alto=26, bg=C["scheda"])
        self.b_salva_sit.configure(width=262); self.b_salva_sit.pack(anchor="w", padx=12, pady=(6, 6))
        self.f_sit = tk.Frame(self.col_sx, bg=C["scheda"]); self.f_sit.pack(fill="x", padx=12, pady=(0, 12))
        # a destra: i numeri in alto, sotto le cartelle (12 nov 2026, Autore: «questi falli a modo di cartelle e poi tira via il sotto testo»): Chart, Spots,
        # Report, Matchups e Compare, una alla volta; il segno a destra di ogni linguetta la stacca in una finestra sua («ogni sezione di ogni cartella si puo'
        # staccare dal quadro e renderla una finestra a se stante»), chiusa torna qui
        dx = tk.Frame(corpo, bg=C["fondo"]); dx.grid(row=0, column=1, sticky="nsew")
        dx.columnconfigure(0, weight=1); dx.rowconfigure(2, weight=1)
        self.cv_num = tk.Canvas(dx, bg=C["scheda"], highlightthickness=1, highlightbackground=C["filo"], height=86, bd=0)
        self.cv_num.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        self.cv_num.bind("<Configure>", lambda e: self.disegna_numeri())
        self.cv_tab = tk.Canvas(dx, bg=C["fondo"], highlightthickness=0, bd=0, height=ALTO_TAB)
        self.cv_tab.grid(row=1, column=0, sticky="ew")
        self.cv_tab.bind("<Configure>", lambda e: self.disegna_cartelle())
        self.cv_tab.bind("<Button-1>", self.clic_cartella)
        self.cv_tab.bind("<Motion>", self.sopra_cartella)
        self.cv_tab.bind("<Leave>", lambda e: self.sopra_cartella(None))
        bordo = tk.Frame(dx, bg=C["filo"]); bordo.grid(row=2, column=0, sticky="nsew")      # il bordo del pannello sui fianchi e sotto: sopra lo fanno le cartelle
        self.pan = pan = tk.Frame(bordo, bg=C["scheda"]); pan.pack(fill="both", expand=True, padx=1, pady=(0, 1))
        self.ospiti = {k: self.fai_vista(k, pan) for k, _n in VISTE}
        o = self.ospiti
        self.cv_gr, self.cv_sp, self.cv_rp, self.cv_mt, self.cv_cf = (o[k]["tela"] for k in ("chart", "spots", "report", "matchups", "compare"))
        self.b_metr = o["chart"]["ctl"]["metr"]
        self.t_asse, self.t_fin, self.t_dividi = (o["chart"]["ctl"][k] for k in ("asse", "fin", "dividi"))
        self.t_per, self.b_meta = o["report"]["ctl"]["per"], o["matchups"]["ctl"]["meta"]
        # la cartella che sta nella sua finestra: qui lo si dice, coi due pulsanti
        self.f_fuori = tk.Frame(pan, bg=C["scheda"])
        self.l_fuori = tk.Label(self.f_fuori, text="", bg=C["scheda"], fg=C["grigio"], font=F(10, True)); self.l_fuori.pack(pady=(70, 14))
        rb = tk.Frame(self.f_fuori, bg=C["scheda"]); rb.pack()
        b = pulsante_solido(tk, F, rb, "Show its window", False, lambda: self.stacca(self.vista), alto=28, bg=C["scheda"], colori=GRIGI)
        b.configure(width=150); b.pack(side="left", padx=4)
        b = pulsante_solido(tk, F, rb, "Bring it back here", False, lambda: self.riattacca(self.vista), alto=28, bg=C["scheda"])
        b.configure(width=170); b.pack(side="left", padx=4)
        self.mostra_vista()
        self.disegna_situazioni()

    def riga_filtro(self, griglia, i, k, nome):
        """Una riga degli smart filters: il nome a sinistra e la tendina a destra."""
        tk, F = self.tk, self.F
        corto = {"Opp. colors (contains)": "Opp. colors", "Lands in opening hand": "Lands in hand", "Game length (your turns)": "Game length",
                 "Card in opening hand": "Card in hand", "Their card seen": "Their card"}.get(nome, nome)
        lab = tk.Label(griglia, text=corto.upper(), bg=C["scheda"], fg=C["grigio"], font=F(7, True), anchor="w"); lab.grid(row=i, column=0, sticky="w", pady=2)
        self.lab_filtri = getattr(self, "lab_filtri", {}); self.lab_filtri[k] = lab
        t = Tendina(tk, griglia, "", F, larga=156, bg=C["scheda"])
        t.fr.winfo_children()[0].pack_forget()        # il nome sta a sinistra, sulla stessa riga
        t.campo.configure(height=24)
        t.fr.grid(row=i, column=1, sticky="w", pady=2)
        t.opzioni(["Any"], lambda v, k=k: self.metti_filtro(k, v)); t.set("Any")
        self.tendine[k] = t

    def fai_vista(self, k, padre):
        """Una vista dentro padre (il pannello o la sua finestra): la riga dei comandi e la tela. -> dict(fr, tela, ctl). Le scelte sono della pagina: due copie
        della stessa vista dicono le stesse cose (sincronizza)."""
        tk, F = self.tk, self.F
        fr = tk.Frame(padre, bg=C["scheda"])
        riga = tk.Frame(fr, bg=C["scheda"]); riga.pack(fill="x", padx=12, pady=(8, 0))
        ctl = {}
        sit_k = ["sit:" + s_ for s_, _n in DA.SIT]
        et_var = {**DA.NOME, **{k_: DA.nome_var(k_) for k_ in sit_k}}

        def asse_e_finestra():
            ctl["fin"] = Tendina(tk, riga, "Window", F, larga=140, bg=C["scheda"]); ctl["fin"].fr.pack(side="right", padx=(10, 0))
            ctl["fin"].opzioni([k_ for k_, _n in DA.FINESTRE], lambda v: self.cambia("finestra", v), etichette=dict(DA.FINESTRE)); ctl["fin"].set(self.finestra)
            ctl["asse"] = Tendina(tk, riga, "X axis", F, larga=100, bg=C["scheda"]); ctl["asse"].fr.pack(side="right", padx=(10, 0))
            ctl["asse"].opzioni(["games", "date"], lambda v: self.cambia("asse", v), etichette={"games": "Games", "date": "Date"}); ctl["asse"].set(self.asse)
        if k == "chart":
            ctl["metr"] = {}
            for m, n in DA.METRICHE:
                b = pulsante_solido(tk, F, riga, n, m == self.metrica, lambda m=m: self.cambia("metrica", m), alto=26, bg=C["scheda"], colori=GRIGI)
                b.configure(width=104); b.pack(side="left", padx=(0, 6), anchor="s", pady=(0, 2))
                ctl["metr"][m] = b
            ctl["dividi"] = Tendina(tk, riga, "Split by", F, larga=180, bg=C["scheda"]); ctl["dividi"].fr.pack(side="right", padx=(10, 0))
            ctl["dividi"].opzioni(["None"] + [k_ for k_, _n, _f in DA.VARIABILI if k_ not in ("data",)] + ["vs"] + [k_ for k_, _n, _f in DA.EXTRA] + sit_k,
                                  lambda v: self.cambia("dividi", None if v == "None" else v), etichette={"None": "None", **et_var})
            ctl["dividi"].set(self.dividi or "None")
            asse_e_finestra()
        elif k == "report":
            ctl["per"] = Tendina(tk, riga, "Group by", F, larga=220, bg=C["scheda"]); ctl["per"].fr.pack(side="right")
            ctl["per"].opzioni([k_ for k_, _n, _f in DA.VARIABILI if k_ != "data"] + ["vs"] + [k_ for k_, _n, _f in DA.EXTRA] + sit_k, lambda v: self.cambia("per", v), etichette=et_var)
            ctl["per"].set(self.per)
        elif k == "matchups":
            ctl["meta"] = pulsante_solido(tk, F, riga, "Meta decks only", self.solo_meta, self.cambia_meta, alto=26, bg=C["scheda"], colori=GRIGI)
            ctl["meta"].configure(width=140); ctl["meta"].pack(side="right", anchor="s", pady=(0, 2))
        elif k == "compare":
            ctl["con"] = Tendina(tk, riga, "Compare A with (B)", F, larga=260, bg=C["scheda"]); ctl["con"].fr.pack(side="left")
            ctl["con"].opzioni(["rest"], lambda v: self.cambia("con", v), etichette={"rest": "Everything else"}); ctl["con"].set(self.con)
            asse_e_finestra()
        c = tk.Canvas(fr, bg=C["scheda"], highlightthickness=0, bd=0, height=120)
        c.pack(fill="both", expand=True, padx=8, pady=(4, 6))
        c.bind("<Configure>", lambda e, k=k: self.tela(k) is e.widget and self.disegna_vista(k))
        if k in ("chart", "compare"):
            c.bind("<Motion>", self.punta)
            c.bind("<Leave>", lambda e: e.widget.delete("punta"))
        elif k == "spots":
            c.bind("<Button-1>", self.clic_spot)
        elif k == "report":
            c.bind("<Button-1>", self.clic_report)
            c.configure(yscrollincrement=24)       # la rotella scorre di una riga intera
            c.bind("<MouseWheel>", lambda e: (e.widget.yview_scroll(-1 if e.delta > 0 else 1, "units"), self.maschera_rp(e.widget)))
        elif k == "matchups":
            c.bind("<Button-1>", self.clic_matchup)
            c.bind("<MouseWheel>", lambda e: e.widget.yview_scroll(-2 if e.delta > 0 else 2, "units"))
        return dict(fr=fr, tela=c, ctl=ctl)

    def ospite(self, k):
        """La copia della vista che si vede: quella della sua finestra se e' staccata, se no quella del pannello."""
        s_ = self.staccate.get(k)
        return s_["o"] if s_ else self.ospiti[k]

    def tela(self, k):
        return self.ospite(k)["tela"]

    def copie(self, k=None):
        """Tutte le copie vive delle viste (o della vista k): nel pannello e nelle finestre."""
        out = [o for k_, o in self.ospiti.items() if k in (None, k_)]
        return out + [s_["o"] for k_, s_ in self.staccate.items() if k in (None, k_)]

    def visibili(self):
        return {self.vista} | set(self.staccate)

    def disegna_vista(self, k):
        getattr(self, DISEGNI[k])()

    def sincronizza(self):
        """I comandi di ogni copia di ogni vista dicono le scelte di adesso."""
        for o in self.copie():
            ctl = o["ctl"]
            for m, b in ctl.get("metr", {}).items():
                b.metti(dict(DA.METRICHE)[m], m == self.metrica)
            for k, v in (("asse", self.asse), ("fin", self.finestra), ("dividi", self.dividi or "None"), ("per", self.per), ("con", self.con)):
                if k in ctl:
                    ctl[k].set(v)
            if "meta" in ctl:
                ctl["meta"].metti("Meta decks only", self.solo_meta)

    # ------------------------------------------------------------ le cartelle
    def disegna_cartelle(self):
        """Le linguette da cartella sopra il pannello: quella scelta si fonde col pannello, le altre piu' scure; a destra di ognuna il segno per staccarla."""
        c = self.cv_tab
        c.delete("all")
        F = self.F
        W, H = max(c.winfo_width(), 600), ALTO_TAB
        d = DG.Disegno(W, H)
        sopra = getattr(self, "_tab_sopra", None)
        self._box_tab, att, testi, segni = [], None, [], []
        x = 0
        for k, n in VISTE:
            x0, x1 = x, x + LARGA_TAB
            fuori = k in self.staccate
            top = 3 if k == self.vista else 8
            if k == self.vista:
                att = (x0, x1)
            else:
                pts = _cartella(x0, x1, top, H + 1)
                d.poligono(pts, riempi="#202026" if sopra and sopra[0] == k else "#18181c")
                d.linea(pts, "#2e2e34", 1.0)
            su_segno = sopra == (k, "segno")
            segni.append((x1 - 22, (top + H) / 2, C["titolo"] if su_segno else C["accento"] if fuori else C["muto"], fuori))
            testi.append(((x0 + x1 - 26) / 2, (top + H) / 2 + 1, n + ("  ↗" if fuori else ""), k == self.vista))
            self._box_tab.append((x0, top, x1, H, k, (x1 - 34, top, x1 - 6, H)))
            x = x1 + 3
        if att:
            x0, x1 = att
            d.linea([(0, H - 0.5), (x0 + 0.5, H - 0.5)], C["filo"], 1.0)       # il bordo alto del pannello, aperto sotto la cartella scelta
            d.linea([(x1 - 0.5, H - 0.5), (W, H - 0.5)], C["filo"], 1.0)
            pts = _cartella(x0, x1, 3, H + 1)
            d.poligono(pts, riempi=C["scheda"])
            d.linea(pts, C["filo"], 1.0)
        else:
            d.linea([(0, H - 0.5), (W, H - 0.5)], C["filo"], 1.0)
        for sx_, sy_, col, fuori in segni:        # sopra le cartelle, anche su quella aperta
            _segno_stacca(d, sx_, sy_, col, fuori)
        self._img_tab = d.foto()
        c.create_image(0, 0, image=self._img_tab, anchor="nw")
        for tx, ty, t, on in testi:
            c.create_text(tx, ty, text=t, fill=C["titolo"] if on else C["grigio"], font=F(8, True))

    def _cartella_a(self, x, y):
        """(vista, «segno» o «tab») sotto il punto, o None."""
        for x0, y0, x1, y1, k, (a, b, c_, d_) in getattr(self, "_box_tab", []):
            if a <= x <= c_ and b <= y <= d_:
                return k, "segno"
            if x0 <= x <= x1 and y0 <= y <= y1:
                return k, "tab"
        return None

    def sopra_cartella(self, e):
        q = None if e is None else self._cartella_a(e.x, e.y)
        self.cv_tab.configure(cursor="hand2" if q else "")
        if q != getattr(self, "_tab_sopra", None):
            self._tab_sopra = q
            self.disegna_cartelle()

    def clic_cartella(self, e):
        q = self._cartella_a(e.x, e.y)
        if q is None:
            return
        k, dove = q
        if dove == "segno":
            if k in self.staccate:
                self.riattacca(k)
            else:
                self.stacca(k)
        elif k in self.staccate:      # una cartella staccata: qui il segnaposto, e la sua finestra davanti
            self.vista = k
            self.mostra_vista()
            self.staccate[k]["win"].lift()
        else:
            self.cambia_vista(k)

    # ------------------------------------------------------------ staccare una cartella in una finestra sua
    def stacca(self, k):
        """La vista k in una finestra sua (non sopra la grande: si porta anche su un altro schermo), coi suoi comandi e la situazione di adesso; chiusa, torna
        nel pannello. Nel pannello passa alla prima cartella rimasta."""
        if k in self.staccate:
            w = self.staccate[k]["win"]
            w.deiconify(); w.lift()
            return w
        tk, F = self.tk, self.F
        nome = dict(VISTE)[k]
        w = tk.Toplevel(self.fr)
        w.title(f"Performance · {nome}")
        w.configure(bg=C["scheda"])
        pw, ph = max(self.pan.winfo_width(), 900), max(self.pan.winfo_height(), 520) + 60
        w.geometry(f"{pw}x{ph}+{self.pan.winfo_rootx() + 40}+{max(0, self.pan.winfo_rooty() - 40)}")
        testa = tk.Frame(w, bg=C["cap"]); testa.pack(fill="x")
        tk.Label(testa, text=f"PERFORMANCE · {nome.upper()}", bg=C["cap"], fg=C["titolo"], font=F(10, True)).pack(side="left", padx=(16, 10), pady=10)
        l_ = tk.Label(testa, text="", bg=C["cap"], fg=C["grigio"], font=F(8), anchor="w"); l_.pack(side="left", fill="x", expand=True)
        b = pulsante_solido(tk, F, testa, "Bring it back", False, lambda: self.riattacca(k), alto=26, bg=C["cap"], colori=GRIGI)
        b.configure(width=120); b.pack(side="right", padx=(8, 16), pady=8)
        o = self.fai_vista(k, w)
        o["fr"].pack(fill="both", expand=True)
        self.staccate[k] = dict(win=w, o=o, l=l_)
        w.protocol("WM_DELETE_WINDOW", lambda: self.riattacca(k, scegli=self.vista == k))
        if self.vista == k:
            libere = [k_ for k_, _n in VISTE if k_ not in self.staccate]
            if libere:
                self.vista = libere[0]
                if self.vista in ("report", "matchups"):
                    self.basso = self.vista
        self.sincronizza()
        self.mostra_vista()
        self.aggiorna_fuori()
        if self.righe is not None:
            self.disegna_vista(self.vista)
            w.after(60, lambda: w.winfo_exists() and self.disegna_vista(k))
        return w

    def riattacca(self, k, scegli=True):
        """La finestra si chiude e la vista torna nel pannello (scegli: e diventa la cartella aperta)."""
        s_ = self.staccate.pop(k, None)
        if s_ is not None:
            try:
                s_["win"].destroy()
            except Exception:      # noqa: BLE001 - gia' chiusa
                pass
        if scegli:
            self.vista = k
            if k in ("report", "matchups"):
                self.basso = k
        self.mostra_vista()
        if self.righe is not None and self.vista == k:
            self.disegna_vista(k)

    def aggiorna_fuori(self):
        """Nella testa di ogni finestra staccata: la situazione e quante partite."""
        if not self.staccate:
            return
        n = len(self.scelte()) if self.righe is not None else 0
        for s_ in self.staccate.values():
            s_["l"].configure(text=f"{n} games · " + self.descrivi(self.filtri))

    def descrivi(self, filtri, tipo=None):
        on = [(k, v) for k, v in filtri.items() if v is not None]
        if not on:
            return f"all your {(tipo or self.tipo).lower()} games"
        return " · ".join(DA.etichetta(k, v) if k.startswith("sit:") else f"{DA.nome_var(k)}: {DA.etichetta(k, v)}" for k, v in on)

    # ------------------------------------------------------------ i comandi
    def cambia_tipo(self, t):
        self.tipo = t
        for k, b in self.b_tipi.items():
            b.metti(k, k == t)
        self.filtri = {}
        for tnd in self.tendine.values():
            tnd.set("Any")
        self.disegna()

    def metti_filtro(self, k, v):
        self.filtri[k] = None if v == "Any" else v
        self.disegna()

    def pulisci(self):
        self.filtri = {}
        self.disegna()

    PARTENZA = dict(metrica="wr", asse="games", finestra="20", dividi=None, per="suo", ordina="n", basso="report", solo_meta=False, vista="chart", con="rest", vs_modo="all")

    def reset(self):
        """Tutte le partite, come all'apertura: niente filtri ne' situazioni, il grafico e la cartella di partenza (le finestre staccate restano)."""
        self.filtri = {}
        for k, v in self.PARTENZA.items():
            setattr(self, k, v)
        self.sincronizza()
        self.mostra_vista()
        self.cv_sx.yview_moveto(0)
        self.disegna()

    def cambia(self, cosa, v):
        setattr(self, cosa, v)
        self.sincronizza()
        if cosa in ("metrica", "asse", "finestra", "dividi"):
            self.disegna_grafico()
            if cosa in ("asse", "finestra") and "compare" in self.visibili():
                self.disegna_confronto()
        elif cosa == "con":
            self.disegna_confronto()
        else:
            self.disegna_report()

    def cambia_vista(self, k):
        self.vista = k
        if k in ("report", "matchups"):
            self.basso = k
        self.mostra_vista()
        if self.righe is not None:
            self.disegna_vista(k)

    def cambia_basso(self, k):      # il nome di prima (le prove, il reset): Report o Matchups
        self.cambia_vista(k)

    def mostra_vista(self):
        """Nel pannello la cartella scelta; se sta nella sua finestra, il segnaposto coi due pulsanti."""
        for o in self.ospiti.values():
            o["fr"].pack_forget()
        self.f_fuori.pack_forget()
        if self.vista in self.staccate:
            self.l_fuori.configure(text=f"{dict(VISTE)[self.vista]} is in its own window")
            self.f_fuori.pack(fill="both", expand=True)
        else:
            self.ospiti[self.vista]["fr"].pack(fill="both", expand=True)
        self.disegna_cartelle()

    def cambia_meta(self):
        self.solo_meta = not self.solo_meta
        self.sincronizza()
        self.disegna_matchup()

    def scelte(self):
        """Le partite del tipo e della situazione."""
        return DA.filtra(self.righe or [], self.filtri, self.tipo)

    # ------------------------------------------------------------ il disegno
    def disegna(self):
        if self.righe is None:
            return
        self.sporca = False
        tutte = [x for x in self.righe if x["tipo"] == self.tipo]
        if tutte:
            self.l_info.configure(text=f"{len(tutte):,} {self.tipo.lower()} games · {tutte[0]['quando']:%d %b} – {tutte[-1]['quando']:%d %b}")
        else:
            self.l_info.configure(text=f"No {self.tipo.lower()} games in your logs yet")
        for k, t in self.tendine.items():      # ogni tendina: i valori coi conti sotto gli altri filtri
            altri = {k2: v for k2, v in self.filtri.items() if k2 != k}
            vv = DA.valori(DA.filtra(self.righe, altri, self.tipo), k)
            sc = self.filtri.get(k)
            voci = ["Any"] + [v for v, _n in vv]
            if sc is not None and sc not in voci:
                voci.append(sc)
            # solo le voci, senza i conti (12 nov 2026, Autore: «nei menu a tendina non mettere anche i numeri solo le voci, i numeri li vogliamo come risultato
            # sui dati»): i valori restano quelli che hanno partite sotto gli altri filtri
            t.opzioni(voci, lambda v, k=k: self.metti_filtro(k, v), etichette={"Any": "Any", **{v: DA.etichetta(k, v) for v, _n in vv}})
            t.set(sc if sc is not None else "Any")
            self.evidenzia(k, sc is not None)
        for j_ in range(len(FASI)):
            self.disegna_testata(j_)
        self.disegna_finestra_fase()
        self.aggiorna_bottone_deck()
        self.disegna_finestra_deck()
        self.disegna_numeri()
        for k, _n in VISTE:         # solo le cartelle che si vedono: le altre si disegnano quando si aprono
            if k in self.visibili():
                self.disegna_vista(k)
        self.aggiorna_fuori()

    def evidenzia(self, k, on):
        """Una tendina con un valore scelto: il campo azzurro scuro col bordo azzurro e il nome in azzurro (12 nov 2026, Autore: «le tendine dove ho dati
        inseriti le evidenzi in azzurro»); il bordo resta azzurro anche quando il puntatore se ne va."""
        t = self.tendine[k]
        bordo = C["accento"] if on else "#3a3a40"
        t.campo.configure(bg="#0f2a38" if on else "#101014", highlightbackground=bordo)
        t.campo.bind("<Leave>", lambda e, b=bordo: t.campo.configure(highlightbackground=b))
        lab = getattr(self, "lab_filtri", {}).get(k)
        if lab is not None:
            lab.configure(fg=C["accento"] if on else C["grigio"])

    def disegna_numeri(self):
        c = self.cv_num
        c.delete("all")
        if self.righe is None:
            return
        F = self.F
        r = self.scelte()
        tot = DA.conti([x for x in self.righe if x["tipo"] == self.tipo])
        k = DA.conti(r)
        W = max(c.winfo_width(), 600)
        n_f = sum(1 for v in self.filtri.values() if v is not None)
        c.create_text(16, 14, text=(f"THIS SITUATION · {k['n']} GAMES" if n_f else f"ALL {self.tipo.upper()} GAMES · {k['n']}"), anchor="w", fill=C["muto"], font=F(7, True))
        xd = W - 16
        if n_f:
            i_ = c.create_text(xd, 14, text=f"vs all your {self.tipo.lower()} games: {tot['wr'] if tot['wr'] is not None else '-'}%", anchor="e", fill=C["grigio"], font=F(7))
            xd = (c.bbox(i_) or (xd, 0, xd, 0))[0] - 14
        if k["n"] and k["n"] < 30:      # in alto, accanto: in fondo usciva dalla tela
            c.create_text(xd, 14, text="under 30 games: a hint, not a fact", anchor="e", fill=C["arancio"], font=F(7, True))
        col_wr = lambda v: C["muto"] if v is None else (C["azzurro"] if v >= 50 else C["rosso"])
        tess = [("WIN RATE", f"{k['wr']:.0f}%" if k["wr"] is not None else "-", col_wr(k["wr"]),
                 f"95% CI {k['ic'][0]}–{k['ic'][1]}%" if k["ic"] else ""),
                ("RECORD", f"{k['vinte']}-{k['perse']}", C["testo"], f"Δ {k['wr'] - tot['wr']:+.1f} vs all" if n_f and k["wr"] is not None and tot["wr"] is not None else ""),
                ("AVG TURNS", f"T{k['turni']}" if k["turni"] else "-", C["testo"], f"wins T{k['turni_v'] or '-'} · losses T{k['turni_p'] or '-'}"),
                ("MULLIGAN", f"{k['mull']:.0f}%" if k["mull"] is not None else "-", C["testo"], "games with a mulligan"),
                ("ON THE PLAY", f"{k['play']:.0f}%" if k["play"] is not None else "-", col_wr(k["play"]), f"{k['n_play']} games"),
                ("ON THE DRAW", f"{k['draw']:.0f}%" if k["draw"] is not None else "-", col_wr(k["draw"]), f"{k['n_draw']} games")]
        cw = (W - 32) / len(tess)
        for i, (a, v, col, s) in enumerate(tess):
            x = 16 + i * cw
            c.create_line(x, 30, x, 86, fill=col, width=2)
            c.create_text(x + 10, 34, text=a, anchor="nw", fill=C["muto"], font=F(7, True))
            c.create_text(x + 10, 60, text=v, anchor="w", fill=col, font=F(17, True))
            c.create_text(x + 10, 80, text=s, anchor="w", fill=C["grigio"], font=F(7))

    def traccia(self, c, lin, box, metrica, asse, colori, titolo, vuoto="No games in this situation"):
        """Il grafico a linee su una tela qualsiasi (la cartella Chart, il confronto): assi, griglia, le linee in un'immagine nitida, il nome in fondo a ogni
        linea. Tiene sulla tela quel che serve al puntatore (_linee, _scala, _metrica, _asse, _colori)."""
        F = self.F
        W, H = max(c.winfo_width(), 400), max(c.winfo_height(), 160)
        x0, y0, x1, y1 = box
        c._linee, c._metrica, c._asse, c._colori, c._scala = lin, metrica, asse, colori, None
        if not lin:
            c.create_text((x0 + x1) / 2, (y0 + y1) / 2, text=vuoto, fill=C["grigio"], font=F(9))
            return None
        xs = [x for _n, p in lin for x, _y in p]
        ys = [y for _n, p in lin for _x, y in p]
        if metrica in ("wr", "mull"):
            ya, yb = 0.0, 100.0
            if metrica == "wr":
                ya, yb = max(0.0, min(ys) // 10 * 10 - 10), min(100.0, (max(ys) // 10 + 1) * 10 + 10)
        else:
            ya, yb = 0.0, max(ys) * 1.15 or 1.0
        xa, xb = min(xs), max(xs) if max(xs) > min(xs) else min(xs) + 1
        c._scala = (x0, y0, x1, y1, xa, xb, ya, yb)
        sx = lambda x: x0 + (x - xa) / (xb - xa) * (x1 - x0)
        sy = lambda y: y1 - (y - ya) / (yb - ya) * (y1 - y0)
        passo = 10 if metrica in ("wr", "mull") else max(1, round((yb - ya) / 5))
        v = ya
        while v <= yb + 1e-9:
            yy = sy(v)
            c.create_line(x0, yy, x1, yy, fill="#3a3a42" if metrica == "wr" and abs(v - 50) < 1e-9 else "#26262c")
            c.create_text(x0 - 8, yy, text=f"{v:.0f}{'%' if metrica in ('wr', 'mull') else ''}", anchor="e", fill=C["muto"], font=F(7))
            v += passo
        etx = (lambda x: f"game {int(x)}") if asse == "games" else (lambda x: datetime.date.fromordinal(int(x)).strftime("%d %b"))
        c.create_text(x0, y1 + 12, text=etx(xa), anchor="w", fill=C["muto"], font=F(7))
        c.create_text(x1, y1 + 12, text=etx(xb), anchor="e", fill=C["muto"], font=F(7))
        tratti = []
        for i, (n, p) in enumerate(lin):
            col = colori[i % len(colori)]
            pts = [(sx(x), sy(y)) for x, y in p]
            if len(pts) == 1:
                pts = [pts[0], (pts[0][0] + 1, pts[0][1])]
            # sottili (12 nov 2026, Autore: «le linee dei grafici le voglio piu' sottili»; erano 2,4 / 2,0 / 1,6)
            tratti.append((pts, col, 1.4 if n == "All" and len(lin) == 1 else 1.2 if n != "All" else 1.0, None))
            c.create_text(x1 + 8, pts[-1][1], text=f"{n}  {p[-1][1]:.0f}{'%' if metrica in ('wr', 'mull') else ''}", anchor="w", fill=col, font=F(7, True))
        c._img = DG.tratti(W, H, linee=tratti)
        c.create_image(0, 0, image=c._img, anchor="nw")
        c.create_text((x0 + x1) / 2, y0 - 12, text=titolo, anchor="n", fill=C["grigio"], font=F(7))
        return sx, sy

    def disegna_grafico(self):
        c = self.tela("chart")
        c.delete("all")
        c._img, c._linee, c._scala = None, [], None
        if self.righe is None:
            return
        W, H = max(c.winfo_width(), 400), max(c.winfo_height(), 160)
        r = self.scelte()
        lin = [(n, p) for n, p in DA.linee(r, self.metrica, self.asse, self.finestra, self.dividi) if p]
        tit = {"wr": "win rate", "n": "games", "turni": "average length in your turns", "mull": "mulligan rate"}[self.metrica]
        fin = "" if self.metrica == "n" else (", cumulative" if self.finestra == "cum" else f", last {self.finestra} games")
        tit = f"{tit}{fin}" + (f" · split by {DA.nome_var(self.dividi).lower()}" if self.dividi else "")
        vuoto = "No games in this situation" if not r else f"{len(r)} games: too few for this chart (a moving window starts at 5)"
        sc = self.traccia(c, lin, (52, 16, W - 120, H - 24), self.metrica, self.asse, LINEE, tit, vuoto)
        if sc and self.asse == "games" and len(lin) == 1:       # i cambi di lega, come nel grafico di prima
            sx, _sy = sc
            for i_, rango in DA.cambi_rango(r):
                xx = sx(i_)
                c.create_line(xx, 16, xx, H - 24, fill="#3a3a42", dash=(3, 3))
                c.create_text(xx + 4, 18, text=rango, anchor="nw", fill=C["grigio"], font=self.F(7, True))

    def punta(self, e):
        """Il puntatore su un grafico (Chart o Compare): la linea verticale e il valore di ogni linea in quel punto."""
        c = e.widget
        c.delete("punta")
        if not getattr(c, "_linee", None) or not getattr(c, "_scala", None):
            return
        x0, y0, x1, y1, xa, xb, _ya, _yb = c._scala
        if not x0 <= e.x <= x1:
            return
        xv = xa + (e.x - x0) / (x1 - x0) * (xb - xa)
        c.create_line(e.x, y0, e.x, y1, fill="#4a4a52", tags="punta")
        righe = []
        pc = "%" if c._metrica in ("wr", "mull") else ""
        for i, (n, p) in enumerate(c._linee):
            q = min(p, key=lambda t: abs(t[0] - xv))
            righe.append((f"{n}: {q[1]:.1f}{pc}", c._colori[i % len(c._colori)]))
        etx = f"game {round(xv)}" if c._asse == "games" else datetime.date.fromordinal(int(round(xv))).strftime("%d %b %Y")
        bx = e.x + 12 if e.x < (x0 + x1) / 2 else e.x - 170
        c.create_rectangle(bx, y0 + 4, bx + 160, y0 + 22 + 15 * len(righe), fill="#101014", outline="#3a3a42", tags="punta")
        c.create_text(bx + 8, y0 + 12, text=etx, anchor="w", fill=C["titolo"], font=self.F(7, True), tags="punta")
        for j, (t, col) in enumerate(righe):
            c.create_text(bx + 8, y0 + 27 + 15 * j, text=t, anchor="w", fill=col, font=self.F(7), tags="punta")

    def disegna_basso(self):
        """Report o Matchups, l'ultima delle due aperta (il nome di prima)."""
        self.disegna_vista(self.basso)

    def disegna_spot(self):
        """Dove vinci e dove perdi di piu': due elenchi (affiancati a tutta larghezza), quanti ne stanno nell'altezza (niente si taglia), gli spot che reggono in
        testa (l'intervallo sta tutto dalla loro parte: «strong»). Il clic mette le condizioni fra i filtri."""
        c = self.tela("spots")
        c.delete("all")
        c._spot_box = []
        if self.righe is None:
            return
        F = self.F
        r = self.scelte()
        W, H = max(c.winfo_width(), 300), max(c.winfo_height(), 200)
        alto = 38
        affiancati = W >= 800        # a tutta larghezza: dove vinci a sinistra, dove perdi a destra
        per_lista = max(1, int((H - 22 - 8) // (alto + 4))) if affiancati else max(1, int((H - 2 * 22 - 8) // 2 // (alto + 4)))
        minimo = 15 if len(r) >= 90 else max(6, len(r) // 6)
        meglio, peggio = DA.spot(r, minimo=minimo, quanti=per_lista, gia=self.filtri)
        base = DA.conti(r)["wr"]
        corto = lambda t, n: t if len(t) <= n else t[:n - 1] + "…"
        y = 2
        larga = (W - 12) / 2 if affiancati else W
        for j_, (tit, lista, col) in enumerate((("WHERE YOU WIN MOST", meglio, C["azzurro"]), ("WHERE YOU LOSE MOST", peggio, C["rosso"]))):
            x0 = j_ * (larga + 12) if affiancati else 0
            if affiancati:
                y = 2
            c.create_text(x0 + 4, y + 8, text=tit, anchor="w", fill=col, font=F(7, True))
            c.create_text(x0 + larga - 4, y + 8, text=f"vs {base:.0f}% here" if base is not None else "", anchor="e", fill=C["muto"], font=F(7))
            y += 20
            if not lista:
                c.create_text(x0 + 4, y + 12, text=f"nothing yet: no spot with {minimo}+ games that stands out", anchor="w", fill=C["grigio"], font=F(7))
                y += 28
            for s in lista:
                c.create_rectangle(x0, y, x0 + larga - 1, y + alto, fill="#202024", outline=col if s["forte"] else "#2c2c32")
                c.create_text(x0 + 10, y + 12, text=corto(s["nome"], int((larga - 90) / 6.4)), anchor="w", fill=C["titolo"], font=F(8, True))
                c.create_text(x0 + 10, y + 27, text=f"{s['n']} games · {s['vinte']}-{s['perse']} · 95% CI {s['ic'][0]}–{s['ic'][1]}%"
                              + ("  ·  strong" if s["forte"] else "  ·  a hint"), anchor="w", fill=C["grigio"] if s["forte"] else C["muto"], font=F(7))
                c.create_text(x0 + larga - 12, y + 12, text=f"{s['wr']:.0f}%", anchor="e", fill=col, font=F(11, True))
                c.create_text(x0 + larga - 12, y + 28, text=f"{s['delta']:+.0f}", anchor="e", fill=col, font=F(7, True))
                c._spot_box.append((x0, y, x0 + larga, y + alto, s))
                y += alto + 4
            y += 6

    def clic_spot(self, e):
        """Uno spot: le sue condizioni fra i filtri."""
        c = getattr(e, "widget", None) or self.tela("spots")
        for x0, y0, x1, y1, s in getattr(c, "_spot_box", []):
            if x0 <= e.x <= x1 and y0 <= e.y <= y1:
                for k, v in s["condizioni"]:
                    self.filtri[k] = v
                self.disegna()
                return

    def disegna_matchup(self):
        """La matrice: i tuoi mazzi in riga, gli archetipi incontrati in colonna (o solo quelli del meta), in ogni cella win rate e partite."""
        c = self.tela("matchups")
        c.delete("all")
        c._celle = []
        if self.righe is None:
            return
        F = self.F
        mazzi, archi, celle, per_m, per_a = DA.matrice(self.scelte(), solo_meta=self.solo_meta)
        if not mazzi or not archi:
            c.create_text(12, 30, text="No matchups in this situation" + (" against meta decks" if self.solo_meta else ""), anchor="w", fill=C["grigio"], font=F(8))
            return
        W = max(c.winfo_width(), 700)
        x0, cw, rh = 230, max(70, min(120, (W - 230 - 90) / max(1, len(archi)))), 30
        corto = lambda t, n: t if len(t) <= n else t[:n - 1] + "…"
        for j, a in enumerate(archi):
            x = x0 + j * cw
            c.create_text(x + cw / 2, 12, text=corto(a, int(cw / 6.5)), anchor="center", fill=C["titolo"], font=F(7, True))
            n, wr = per_a[a]
            c.create_text(x + cw / 2, 26, text=f"{wr:.0f}% · {n}", anchor="center", fill=C["grigio"], font=F(7))
        c.create_text(x0 + len(archi) * cw + 40, 12, text="ALL", anchor="center", fill=C["titolo"], font=F(7, True))
        y = 38
        for m in mazzi:
            n, wr = per_m[m]
            c.create_text(8, y + rh / 2 - 6, text=corto(m, 30), anchor="w", fill=C["titolo"], font=F(8, True))
            c.create_text(8, y + rh / 2 + 7, text=f"{n} games · {wr:.0f}%", anchor="w", fill=C["grigio"], font=F(7))
            for j, a in enumerate(archi):
                x = x0 + j * cw
                v = celle.get((m, a))
                if v is None:
                    c.create_rectangle(x + 2, y + 2, x + cw - 2, y + rh - 2, fill="#18181c", outline="#26262c")
                    continue
                nn, _vv, w = v
                poche = nn < 5
                fondo = "#26262c" if poche else _colore_wr(w)
                c.create_rectangle(x + 2, y + 2, x + cw - 2, y + rh - 2, fill=fondo, outline="#26262c")
                c.create_text(x + cw / 2, y + rh / 2 - 5, text=f"{w:.0f}%", fill=C["muto"] if poche else C["titolo"], font=F(8, True))
                c.create_text(x + cw / 2, y + rh / 2 + 8, text=f"{nn}", fill=C["muto"] if poche else "#d8d8dc", font=F(6))
                c._celle.append((x, y, x + cw, y + rh, m, a))
            c.create_text(x0 + len(archi) * cw + 40, y + rh / 2, text=f"{wr:.0f}%", fill=C["azzurro"] if wr >= 50 else C["rosso"], font=F(8, True))
            y += rh + 2
        c.create_text(8, y + 12, text="grey: under 5 games, a hint", anchor="w", fill=C["muto"], font=F(7))
        c.configure(scrollregion=(0, 0, W, y + 26))

    def clic_matchup(self, e):
        """Una cella: il tuo mazzo e il suo archetipo fra i filtri."""
        c = getattr(e, "widget", None) or self.tela("matchups")
        y = c.canvasy(e.y)
        for x0, y0, x1, y1, m, a in getattr(c, "_celle", []):
            if x0 <= e.x <= x1 and y0 <= y <= y1:
                self.filtri["mio"], self.filtri["suo"] = m, a
                self.disegna()
                return

    def disegna_report(self):
        c = self.tela("report")
        c.delete("all")
        c._righe_rp, c._n = [], 0
        if self.righe is None:
            return
        F = self.F
        rep = DA.report(self.scelte(), self.per, self.ordina if self.ordina != "wl" else "vinte")
        W = max(c.winfo_width(), 700)
        x = 8
        c._col_x = []
        for k, t, w in COLONNE:
            c.create_text(x, 10, text=t or DA.nome_var(self.per).upper()[:32], anchor="w", fill=C["accento"] if k == self.ordina else C["titolo"], font=F(7, True))
            c._col_x.append((x, x + w, k))
            x += w
        y = 26
        for i, r in enumerate(rep):
            if i % 2 == 0:
                c.create_rectangle(0, y - 2, W, y + 22, fill="#202024", outline="")
            gr_ = r["poche"]
            x = 8
            for k, _t, w in COLONNE:
                if k == "wr":
                    col = C["muto"] if gr_ or r["wr"] is None else (C["azzurro"] if r["wr"] >= 50 else C["rosso"])
                    c.create_rectangle(x, y + 5, x + 120, y + 15, fill="#2c2c32", outline="")
                    if r["wr"] is not None:
                        c.create_rectangle(x, y + 5, x + 1.2 * r["wr"], y + 15, fill=col, outline="")
                    c.create_line(x + 60, y + 2, x + 60, y + 18, fill="#d8d8dc")
                    c.create_text(x + 128, y + 10, text=f"{r['wr']:.0f}%" if r["wr"] is not None else "-", anchor="w", fill=col, font=F(8, True))
                else:
                    v = {"nome": r["nome"], "n": str(r["n"]), "wl": f"{r['vinte']}-{r['perse']}", "play": f"{r['play']:.0f}%" if r["play"] is not None else "-",
                         "draw": f"{r['draw']:.0f}%" if r["draw"] is not None else "-", "mull": f"{r['mull']:.0f}%" if r["mull"] is not None else "-",
                         "turni": f"T{r['turni']}" if r["turni"] else "-", "delta": f"{r['delta']:+.1f}" if r["delta"] is not None else "-"}[k]
                    col = (C["muto"] if gr_ else (C["azzurro"] if (r["delta"] or 0) > 0 else C["rosso"] if (r["delta"] or 0) < 0 else C["testo"])) if k == "delta" \
                        else (C["muto"] if gr_ else C["titolo"] if k == "nome" else C["testo"])
                    if k == "nome" and len(v) > 34:
                        v = v[:33] + "…"
                    c.create_text(x, y + 10, text=v, anchor="w", fill=col, font=F(8, k == "nome"))
                x += w
            c._righe_rp.append((y - 2, y + 22, r["valore"]))
            y += 24
        c._n = len(rep)
        if not rep:
            c.create_text(12, 40, text="No games in this situation", anchor="w", fill=C["grigio"], font=F(8))
        c.create_text(8, y + 10, text="grey: under 15 games, a hint", anchor="w", fill=C["muto"], font=F(7))
        c.configure(scrollregion=(0, 0, W, y + 24))
        self.maschera_rp(c)

    def maschera_rp(self, c=None):
        """La riga che in fondo starebbe a meta' si copre: in vista solo righe intere (12 nov 2026: «tutto non tagliato»); sopra la copertura quante righe restano
        sotto (la riga d'aiuto sotto le cartelle non c'e' piu')."""
        c = c or self.tela("report")
        c.delete("maschera")
        top, h = c.canvasy(0), max(c.winfo_height(), 60)
        fondo = top + h
        W = max(c.winfo_width(), 700)
        ultimo = 24 + int((fondo - 24) // 24) * 24       # le righe cominciano a 24 e sono alte 24
        fine = 24 + 24 * getattr(c, "_n", 0)
        sotto = (fine - ultimo) // 24 if fine > ultimo else 0
        if sotto and fondo - ultimo < 18 and ultimo - 24 > top + 24:       # serve posto per la scritta: si copre una riga in piu'
            ultimo -= 24
            sotto += 1
        if ultimo < fondo:
            c.create_rectangle(0, ultimo, W + 10, fondo + 2, fill=C["scheda"], outline="", tags="maschera")
        if sotto:
            c.create_text(W - 12, (ultimo + fondo) / 2, text=f"{sotto} more row{'s' if sotto > 1 else ''} below · scroll", anchor="e", fill=C["grigio"],
                          font=self.F(7, True), tags="maschera")

    def clic_report(self, e):
        c = getattr(e, "widget", None) or self.tela("report")
        y = c.canvasy(e.y)
        if y < 22:      # le intestazioni: ordina
            for a, b, k in getattr(c, "_col_x", []):
                if a <= e.x < b:
                    self.ordina = "nome" if k == "nome" else k
                    self.disegna_report()
                    return
            return
        for a, b, v in getattr(c, "_righe_rp", []):
            if a <= y < b:
                self.filtri[self.per] = v
                self.disegna()
                return

    # ------------------------------------------------------------ il confronto situazionale (12 nov 2026, «procedi con i confronti situazionali»)
    def b_confronto(self):
        """B: il resto delle partite (rest), tutte (all) o una situazione salvata (s<i>). -> (partite, nome, descrizione)."""
        tutte = [x for x in self.righe if x["tipo"] == self.tipo]
        if self.con.startswith("s") and self.con[1:].isdigit():
            sal = DA.situazioni()
            i = int(self.con[1:])
            if i < len(sal):
                s_ = sal[i]
                t = s_.get("tipo") or self.tipo
                return DA.filtra(self.righe, s_.get("filtri") or {}, t), s_.get("nome") or f"Situation {i + 1}", self.descrivi(s_.get("filtri") or {}, t)
            self.con = "rest"
        if self.con == "all":
            return tutte, f"All {self.tipo.lower()} games", f"all your {self.tipo.lower()} games, A included"
        dentro = {id(x) for x in self.scelte()}
        return [x for x in tutte if id(x) not in dentro], "Everything else", f"your {self.tipo.lower()} games outside A"

    def disegna_confronto(self):
        """A (la situazione dei filtri) contro B: le due schede, la tabella delle misure con la differenza e se regge (test z, p sotto 5%), la frase, e sotto il
        win rate dei due nel tempo."""
        c = self.tela("compare")
        c.delete("all")
        c._img, c._linee, c._scala = None, [], None
        if self.righe is None:
            return
        F = self.F
        sal = DA.situazioni()
        voci = ["rest", "all"] + [f"s{i}" for i in range(len(sal))]
        if self.con not in voci:
            self.con = "rest"
        et = {"rest": "Everything else", "all": f"All {self.tipo.lower()} games", **{f"s{i}": (s_.get("nome") or f"Situation {i + 1}") for i, s_ in enumerate(sal)}}
        for o in self.copie("compare"):
            o["ctl"]["con"].opzioni(voci, lambda v: self.cambia("con", v), etichette=et)
            o["ctl"]["con"].set(self.con)
        W, H = max(c.winfo_width(), 600), max(c.winfo_height(), 240)
        n_f = sum(1 for v in self.filtri.values() if v is not None)
        if not n_f and self.con in ("rest", "all"):
            c.create_text(16, 30, text="A is the situation you build with the smart filters (and the + of each phase).", anchor="w", fill=C["titolo"], font=F(9, True))
            c.create_text(16, 52, text="Set some, then compare it here with everything else, with all your games or with a saved situation.", anchor="w",
                          fill=C["grigio"], font=F(8))
            return
        a = self.scelte()
        b, nome_b, descr_b = self.b_confronto()
        res = DA.confronta(a, b)
        corto = lambda t, n: t if len(t) <= n else t[:n - 1] + "…"
        meta = (W - 16 - 12) / 2
        for i, (lett, tit, descr, k_, col) in enumerate((("A", "THIS SITUATION", self.descrivi(self.filtri), res["a"], C["azzurro"]),
                                                         ("B", nome_b.upper(), descr_b, res["b"], C["arancio"]))):
            x0 = 8 + i * (meta + 12)
            c.create_rectangle(x0, 4, x0 + meta, 52, fill="#202024", outline="#2c2c32")
            c.create_rectangle(x0, 4, x0 + 3, 52, fill=col, outline="")
            c.create_text(x0 + 14, 17, text=corto(f"{lett} · {tit}", int((meta - 150) / 6.6)), anchor="w", fill=col, font=F(8, True))
            c.create_text(x0 + meta - 10, 17, text=f"{k_['n']} games · {k_['vinte']}-{k_['perse']}", anchor="e", fill=C["titolo"], font=F(8, True))
            c.create_text(x0 + 14, 37, text=corto(descr, int((meta - 24) / 5.6)), anchor="w", fill=C["grigio"], font=F(7))
        # la tabella: misura, A, B, A meno B, se regge
        cx = (16, 250, 420, 580, 700)
        y = 64
        for x_, t in zip(cx, ("MEASURE", "A", "B", "A − B", "DOES IT HOLD?")):
            c.create_text(x_, y + 8, text=t, anchor="w", fill=C["azzurro"] if t == "A" else C["arancio"] if t == "B" else C["titolo"], font=F(7, True))
        y += 20
        pf = lambda p: "p < 0.001" if p < 0.001 else f"p {p:.3f}" if p < 0.1 else f"p {p:.2f}"
        for i, r in enumerate(res["righe"]):
            if i % 2 == 0:
                c.create_rectangle(0, y, W, y + 24, fill="#202024", outline="")
            c.create_text(cx[0], y + 12, text=r["nome"], anchor="w", fill=C["titolo"], font=F(8, True))
            for x_, v, n, ic, col in ((cx[1], r["a"], r["na"], r["ic_a"], C["azzurro"]), (cx[2], r["b"], r["nb"], r["ic_b"], C["arancio"])):
                if v is None:
                    t = "-"
                elif r["unita"] == "%":
                    t = f"{v:.0f}%" + (f"  ({ic[0]}–{ic[1]})" if r["k"] == "wr" and ic else "") + f"  · {n} g"
                else:
                    t = f"T{v}  · {n} g"
                c.create_text(x_, y + 12, text=t, anchor="w", fill=col if v is not None else C["muto"], font=F(8))
            d = r["delta"]
            buono = r["k"] in ("wr", "play", "draw")
            if d is None:
                td, cd = "-", C["muto"]
            else:
                td = f"{d:+.1f} pts" if r["unita"] == "%" else f"{d:+.1f} turns"
                cd = (C["azzurro"] if d > 0 else C["rosso"] if d < 0 else C["testo"]) if buono else C["testo"]
            c.create_text(cx[3], y + 12, text=td, anchor="w", fill=cd, font=F(8, True))
            if r["p"] is None:
                tv, cv, fv = "too few games (5 a side)", C["muto"], F(7)
            elif r["p"] < 0.05:
                tv, cv, fv = f"holds · {pf(r['p'])}", C["accento"], F(8, True)
            else:
                tv, cv, fv = f"could be chance · {pf(r['p'])}" + (f" · ~{r['servono']:,} games a side to tell" if r["servono"] and r["servono"] <= 3000
                                                                   else " · no real difference" if r["unita"] == "%" else ""), C["grigio"], F(7)
            c.create_text(cx[4], y + 12, text=tv, anchor="w", fill=cv, font=fv)
            y += 24
        # la frase sul win rate
        w = res["righe"][0]
        if w["p"] is None:
            fr, cf = "Too few games on one side to compare the win rate: 5 at least on each.", C["grigio"]
        else:
            piu = f"{abs(w['delta']):.1f} points {'more' if w['delta'] > 0 else 'less'}" if w["delta"] else "the same"
            if w["p"] < 0.05:
                fr, cf = f"In A you win {piu} than in B, and it holds: {pf(w['p'])}, under 5% it is not chance.", C["accento"]
            else:
                fr, cf = (f"In A you win {piu} than in B, but it could still be chance ({pf(w['p'])})"
                          + (f": about {w['servono']:,} games on each side would tell." if w["servono"] and w["servono"] <= 3000
                             else ": so small that it is no real difference." if w["servono"] else "."), C["titolo"])
        c.create_text(16, y + 16, text=fr, anchor="w", fill=cf, font=F(9, True), width=W - 32)
        y += 40
        if H - y >= 130:        # sotto, il win rate di A e di B nel tempo
            lin = [(n, p) for n, p in (("A", DA.serie(a, "wr", self.asse, self.finestra)), ("B", DA.serie(b, "wr", self.asse, self.finestra))) if p]
            fin = "cumulative" if self.finestra == "cum" else f"last {self.finestra} games"
            self.traccia(c, lin, (52, y + 18, W - 120, H - 24), "wr", self.asse, (C["azzurro"], C["arancio"]), f"win rate of A and B, {fin}")

    # ------------------------------------------------------------ i filtri in piu' di ogni fase (12 nov 2026: le situazioni di Add filters stanno qui)
    def disegna_testata(self, j):
        """La testa di una fase: la lineetta (non sulla prima), il nome e a destra il «+ more», azzurro con quanti ne sono accesi."""
        c = self.testate[j]
        c.delete("all")
        F = self.F
        W = max(c.winfo_width(), 262)
        H = int(c.cget("height"))
        if j:
            c.create_line(0, 5, W, 5, fill=C["filo"])
        nome, chiavi = FASI[j]
        on = sum(1 for k in chiavi if self.filtri.get(k) is not None)
        c.create_text(0, H - 10, text=nome, anchor="w", fill=C["accento"] if on else C["muto"], font=F(7, True))
        t = f"+ {on} on" if on else "+ more"
        c.create_rectangle(W - 62, H - 19, W - 2, H - 1, fill="#0f86cc" if on else "#202024", outline="#0f86cc" if on else "#3a3a40")
        c.create_text(W - 32, H - 10, text=t, fill="#ffffff" if on else C["grigio"], font=F(7, True))

    def apri_fase(self, j):
        """La finestra dei filtri in piu' di una fase: per ognuno Any o un valore (per le situazioni Yes o No), si applica subito. Una finestra sola: un'altra fase
        la riempie."""
        tk, F = self.tk, self.F
        self.fase = j
        f = getattr(self, "fin_fase", None)
        if f is None or not f.winfo_exists():
            f = self.fin_fase = tk.Toplevel(self.fr); f.configure(bg=C["scheda"])
            f.transient(self.fr.winfo_toplevel())
            f.geometry(f"+{self.cv_sx.winfo_rootx() + self.cv_sx.winfo_width() + 16}+{self.cv_sx.winfo_rooty()}")
            f.bind("<Escape>", lambda e: f.destroy())
            self.l_fase = tk.Label(f, text="", bg=C["scheda"], fg=C["titolo"], font=F(9, True)); self.l_fase.pack(anchor="w", padx=14, pady=(12, 2))
            tk.Label(f, text="More filters for this phase of the game. Yes: only the games where it happened; No: only those where it did not. "
                     "They apply at once, like the smart filters.", bg=C["scheda"], fg=C["grigio"], font=F(7), wraplength=LARGA_FASE - 20,
                     justify="left").pack(anchor="w", padx=14, pady=(0, 8))
            self.cv_fase = tk.Canvas(f, bg=C["scheda"], highlightthickness=0, bd=0, width=LARGA_FASE, height=200)
            self.cv_fase.pack(padx=8, pady=(0, 12))
            self.cv_fase.bind("<Button-1>", self.clic_fase)
        f.title("More filters · " + FASI[j][0].capitalize())
        self.l_fase.configure(text="MORE FILTERS · " + FASI[j][0])
        self.disegna_finestra_fase()
        f.lift()
        return f

    def disegna_finestra_fase(self):
        c = getattr(self, "cv_fase", None)
        if c is None or not c.winfo_exists():
            return
        F = self.F
        c.delete("all")
        self._box_fase = []
        tutte = [x for x in (self.righe or []) if x["tipo"] == self.tipo]
        from tkinter import font as tkfont
        misura = tkfont.Font(font=F(7, True))
        y = 4
        for k in FASI[getattr(self, "fase", 0)][1]:
            sc = self.filtri.get(k)
            vv = ["Yes", "No"] if k.startswith("sit:") else [v for v, _n in DA.valori(tutte, k)]
            c.create_text(8, y + 13, text=DA.nome_var(k), anchor="w", fill=C["titolo"] if sc else C["testo"], font=F(8, bool(sc)), width=290)
            x = 310
            for v in [None] + vv:
                t = "Any" if v is None else DA.etichetta(k, v) if k in ("miei_colori",) else v
                w = max(50, misura.measure(t) + 22)
                if x + w > LARGA_FASE - 6:      # va a capo: i valori restano tutti leggibili
                    x, y = 310, y + 30
                on = sc == v
                c.create_rectangle(x, y + 2, x + w, y + 24, fill="#0f86cc" if on else "#202024", outline="#0f86cc" if on else "#3a3a40")
                c.create_text(x + w / 2, y + 13, text=t, fill="#ffffff" if on else C["grigio"], font=F(7, True))
                self._box_fase.append((x, y + 2, x + w, y + 24, k, v))
                x += w + 6
            y += 34
        c.configure(height=y + 4)

    def clic_fase(self, e):
        for x0, y0, x1, y1, k, v in getattr(self, "_box_fase", []):
            if x0 <= e.x <= x1 and y0 <= e.y <= y1:
                self.filtri[k] = v
                self.disegna()
                return

    # ------------------------------------------------------------ By deck (12 nov 2026, Autore: «crea un pulsante in fondo: by deck: si apre una finestra e
    # scegli il tuo deck, sempre nella finestra di default e' vs all - si puo' spuntare vs colors e flaggare i colori di vs - da qui troviamo un modo intelligente
    # per fare l'analisi in base al monocolore fino al pentacolore o incolore - in ogni caso sempre un deck contro un'unica variante colore mazzo»)
    def lista(self):
        """I simboli di mana (capsule), fatti una volta."""
        if getattr(self, "_lista", None) is None:
            from capsule import Liste
            self._lista = Liste(self.tk, self.F)
        return self._lista

    def aggiorna_bottone_deck(self):
        mio, vs = self.filtri.get("mio"), self.filtri.get("vs")
        t = f"By deck  ·  {(mio or 'all decks').strip()} vs {DA.nome_vs(vs) if vs else 'all'}"
        self.b_deck.metti(t if len(t) <= 40 else t[:39] + "…", bool(mio or vs))

    def apri_deck(self):
        """La finestra By deck: a sinistra il tuo mazzo (o tutti), a destra contro chi: vs all, o vs colors coi colori da spuntare (una variante esatta, dal
        monocolore al pentacolore, o incolore), e sotto il mazzo contro ogni variante di colore incontrata, per gruppi; il clic su una riga la sceglie."""
        tk, F = self.tk, self.F
        f = getattr(self, "fin_deck", None)
        if f is not None and f.winfo_exists():
            f.lift(); return f
        f = self.fin_deck = tk.Toplevel(self.fr); f.title("By deck"); f.configure(bg=C["scheda"])
        f.transient(self.fr.winfo_toplevel())
        f.geometry(f"+{self.cv_sx.winfo_rootx() + self.cv_sx.winfo_width() + 16}+{max(0, self.cv_sx.winfo_rooty() - 80)}")
        f.bind("<Escape>", lambda e: f.destroy())
        tk.Label(f, text="BY DECK", bg=C["scheda"], fg=C["titolo"], font=F(9, True)).pack(anchor="w", padx=14, pady=(12, 2))
        tk.Label(f, text="One of your decks against everyone, or against one exact color variant of their deck: mono-color to five colors, or colorless. "
                 "The table below is your deck against every variant you met: click a row to pick it.", bg=C["scheda"], fg=C["grigio"], font=F(7),
                 wraplength=960, justify="left").pack(anchor="w", padx=14, pady=(0, 8))
        self.cv_deck = tk.Canvas(f, bg=C["scheda"], highlightthickness=0, bd=0, width=LARGA_DECK, height=560)
        self.cv_deck.pack(padx=8, pady=(0, 12), fill="both", expand=True)
        self.cv_deck.bind("<Button-1>", self.clic_deck)
        self.cv_deck.bind("<MouseWheel>", lambda e: e.widget.yview_scroll(-2 if e.delta > 0 else 2, "units"))
        self.disegna_finestra_deck()
        return f

    def disegna_finestra_deck(self):
        c = getattr(self, "cv_deck", None)
        if c is None or not c.winfo_exists() or self.righe is None:
            return
        F = self.F
        c.delete("all")
        self._box_deck = []
        corto = lambda t, n: t if len(t) <= n else t[:n - 1] + "…"
        mio, vs = self.filtri.get("mio"), self.filtri.get("vs")
        modo = "colors" if vs else self.vs_modo
        pc = lambda v: f"{v:.0f}%" if v is not None else "-"
        # a sinistra il tuo mazzo: contati sotto gli altri filtri (contro chi compreso)
        base_m = DA.filtra(self.righe, {k: v for k, v in self.filtri.items() if k != "mio"}, self.tipo)
        mazzi = [v for v, _n in DA.valori(base_m, "mio", massimo=80)]
        if mio and mio not in mazzi:
            mazzi.append(mio)
        y = 4
        c.create_text(4, y + 8, text="YOUR DECK", anchor="w", fill=C["muto"], font=F(7, True))
        y += 22
        for v in [None] + mazzi:
            sub = base_m if v is None else [x for x in base_m if x.get("mio") == v]
            k_ = DA.conti(sub)
            on = mio == v
            c.create_rectangle(0, y, 270, y + 26, fill="#0f2a38" if on else "#202024", outline=C["accento"] if on else "#2c2c32")
            c.create_text(10, y + 13, text=corto((v or "All decks").strip(), 24), anchor="w", fill=C["titolo"] if on else C["testo"], font=F(8, on))
            c.create_text(262, y + 13, text=f"{k_['n']} g · {pc(k_['wr'])}", anchor="e", fill=C["accento"] if on else C["grigio"], font=F(7))
            self._box_deck.append((0, y, 270, y + 26, "mio", v))
            y += 30
        fine_sx = y
        # a destra: contro chi
        X = 296
        y = 4
        c.create_text(X, y + 8, text="AGAINST", anchor="w", fill=C["muto"], font=F(7, True))
        y += 22
        for i, (m, t) in enumerate((("all", "vs all"), ("colors", "vs colors"))):
            x = X + i * 118
            on = modo == m
            c.create_rectangle(x, y, x + 110, y + 28, fill="#0f86cc" if on else "#202024", outline="#0f86cc" if on else "#3a3a40")
            c.create_text(x + 55, y + 14, text=t, fill="#ffffff" if on else C["grigio"], font=F(8, True))
            self._box_deck.append((x, y, x + 110, y + 28, "modo", m))
        y += 40
        flag = set() if not vs else ({"C"} if vs == "C" else set(vs))
        for i, k in enumerate("WUBRGC"):
            x = X + i * 48
            on = k in flag
            c.create_rectangle(x, y, x + 40, y + 36, fill="#0f2a38" if on else "#202024", outline=C["accento"] if on else "#2c2c32", width=2 if on else 1)
            img = self.lista().simbolo(k, 22)
            if img is not None:
                c.create_image(x + 20, y + 18, image=img)
            else:
                c.create_text(x + 20, y + 18, text=k, fill=C["titolo"], font=F(9, True))
            self._box_deck.append((x, y, x + 40, y + 36, "colore", k))
        base_vs = DA.filtra(self.righe, {k: v for k, v in self.filtri.items() if k != "vs"}, self.tipo)
        x = X + 6 * 48 + 8
        if vs:
            kk = DA.conti(DA.filtra(base_vs, {"vs": vs}))
            c.create_text(x, y + 10, text=f"{(mio or 'All decks').strip()} vs {DA.etichetta('vs', vs)}", anchor="w", fill=C["titolo"], font=F(9, True))
            c.create_text(x, y + 28, text=f"{kk['n']} games · {kk['vinte']}-{kk['perse']} · {pc(kk['wr'])}"
                          + (f"  (95% CI {kk['ic'][0]}–{kk['ic'][1]}%)" if kk["ic"] else ""), anchor="w", fill=C["accento"], font=F(8, True))
        elif modo == "colors":
            c.create_text(x, y + 18, text="Flag the colors of their deck: exactly those, one variant.", anchor="w", fill=C["grigio"], font=F(8))
        else:
            kk = DA.conti(base_vs)
            c.create_text(x, y + 10, text=f"{(mio or 'All decks').strip()} vs everyone", anchor="w", fill=C["titolo"], font=F(9, True))
            c.create_text(x, y + 28, text=f"{kk['n']} games · {kk['vinte']}-{kk['perse']} · {pc(kk['wr'])}", anchor="w", fill=C["grigio"], font=F(8))
        y += 52
        # la tabella: il mazzo contro ogni variante, per gruppi dal monocolore al pentacolore e incolore
        c.create_text(X, y + 8, text="AGAINST EVERY COLOR VARIANT YOU MET", anchor="w", fill=C["muto"], font=F(7, True))
        col = dict(var=X, n=X + 280, wl=X + 336, wr=X + 400, play=X + 560, draw=X + 620)
        y += 22
        for k, t in (("var", "VARIANT"), ("n", "GAMES"), ("wl", "W-L"), ("wr", "WIN RATE"), ("play", "PLAY"), ("draw", "DRAW")):
            c.create_text(col[k], y + 6, text=t, anchor="w", fill=C["titolo"], font=F(7, True))
        y += 18
        gruppi = DA.per_varianti(base_vs)
        if not gruppi:
            c.create_text(X, y + 16, text="No games with their colors in this situation", anchor="w", fill=C["grigio"], font=F(8))
            y += 34

        def barra(x, yy, wr, colore):
            c.create_rectangle(x, yy + 8, x + 100, yy + 16, fill="#2c2c32", outline="")
            if wr is not None:
                c.create_rectangle(x, yy + 8, x + wr, yy + 16, fill=colore, outline="")
            c.create_line(x + 50, yy + 5, x + 50, yy + 19, fill="#d8d8dc")
            c.create_text(x + 108, yy + 12, text=pc(wr), anchor="w", fill=colore, font=F(8, True))
        for g in gruppi:
            k_ = g["conti"]
            c.create_rectangle(X - 4, y, LARGA_DECK, y + 24, fill="#26262c", outline="")
            c.create_text(col["var"], y + 12, text=g["gruppo"].upper(), anchor="w", fill=C["titolo"], font=F(8, True))
            c.create_text(col["n"], y + 12, text=str(k_["n"]), anchor="w", fill=C["titolo"], font=F(8, True))
            c.create_text(col["wl"], y + 12, text=f"{k_['vinte']}-{k_['perse']}", anchor="w", fill=C["testo"], font=F(8))
            barra(col["wr"], y, k_["wr"], C["azzurro"] if (k_["wr"] or 0) >= 50 else C["rosso"])
            c.create_text(col["play"], y + 12, text=pc(k_["play"]), anchor="w", fill=C["testo"], font=F(8))
            c.create_text(col["draw"], y + 12, text=pc(k_["draw"]), anchor="w", fill=C["testo"], font=F(8))
            y += 26
            for i, (v, k_) in enumerate(g["varianti"]):
                on, poche = v == vs, k_["n"] < 5
                fondo = "#0f2a38" if on else ("#202024" if i % 2 == 0 else C["scheda"])
                c.create_rectangle(X - 4, y, LARGA_DECK, y + 24, fill=fondo, outline=C["accento"] if on else "")
                for j, ch in enumerate(v):
                    img = self.lista().simbolo(ch, 14)
                    if img is not None:
                        c.create_image(col["var"] + 8 + j * 16, y + 12, image=img)
                testo = C["muto"] if poche else C["titolo"]
                c.create_text(col["var"] + 8 + 5 * 16 + 4, y + 12, text=DA.nome_vs(v), anchor="w", fill=testo, font=F(8, on))
                c.create_text(col["n"], y + 12, text=str(k_["n"]), anchor="w", fill=testo, font=F(8))
                c.create_text(col["wl"], y + 12, text=f"{k_['vinte']}-{k_['perse']}", anchor="w", fill=C["muto"] if poche else C["testo"], font=F(8))
                barra(col["wr"], y, k_["wr"], C["muto"] if poche else (C["azzurro"] if (k_["wr"] or 0) >= 50 else C["rosso"]))
                c.create_text(col["play"], y + 12, text=pc(k_["play"]), anchor="w", fill=C["muto"] if poche else C["testo"], font=F(8))
                c.create_text(col["draw"], y + 12, text=pc(k_["draw"]), anchor="w", fill=C["muto"] if poche else C["testo"], font=F(8))
                self._box_deck.append((X - 4, y, LARGA_DECK, y + 24, "vs", v))
                y += 26
            y += 6
        if gruppi:
            c.create_text(X, y + 8, text="grey: under 5 games, a hint", anchor="w", fill=C["muto"], font=F(7))
            y += 22
        alto = max(y, fine_sx) + 8
        c.configure(scrollregion=(0, 0, LARGA_DECK, alto), height=min(alto, 720))

    def clic_deck(self, e):
        c = getattr(e, "widget", None) or self.cv_deck
        y = c.canvasy(e.y)
        for x0, y0, x1, y1, cosa, v in getattr(self, "_box_deck", []):
            if not (x0 <= e.x <= x1 and y0 <= y <= y1):
                continue
            vs = self.filtri.get("vs")
            if cosa == "mio":
                self.filtri["mio"] = v
            elif cosa == "modo":
                self.vs_modo = v
                if v == "all":
                    self.filtri["vs"] = None
            elif cosa == "colore":     # vs colors: i colori spuntati sono una variante esatta; incolore sta da solo
                self.vs_modo = "colors"
                flag = set() if not vs else ({"C"} if vs == "C" else set(vs))
                if v == "C":
                    flag = set() if "C" in flag else {"C"}
                else:
                    flag.discard("C")
                    flag ^= {v}
                self.filtri["vs"] = ("C" if "C" in flag else "".join(k for k in "WUBRG" if k in flag)) or None
            elif cosa == "vs":
                self.vs_modo = "colors"
                self.filtri["vs"] = None if vs == v else v
            self.disegna()
            return

    # ------------------------------------------------------------ le situazioni salvate
    def salva_situazione(self):
        DA.salva_situazione(self.tipo, dict(self.filtri))
        self.disegna_situazioni()
        if "compare" in self.visibili():       # le situazioni salvate sono anche i B del confronto
            self.disegna_confronto()
        self.b_salva_sit.metti("Saved", False); self.b_salva_sit.after(1800, lambda: self.b_salva_sit.winfo_exists() and self.b_salva_sit.metti("Save this situation", False))

    def disegna_situazioni(self):
        tk, F = self.tk, self.F
        for w in self.f_sit.winfo_children():
            w.destroy()
        sit = DA.situazioni()
        if not sit:
            tk.Label(self.f_sit, text="Set some filters, then save the situation to come back to it.", bg=C["scheda"], fg=C["grigio"], font=F(7), wraplength=250,
                     justify="left").pack(anchor="w")
            return
        for i, s in enumerate(sit):
            r = tk.Frame(self.f_sit, bg="#101014", highlightthickness=1, highlightbackground=C["filo"]); r.pack(fill="x", pady=(0, 4))
            n = s.get("nome") or "Situation"
            lab = tk.Label(r, text=(n if len(n) <= 38 else n[:37] + "…"), bg="#101014", fg=C["testo"], font=F(8), anchor="w", cursor="hand2", padx=8, pady=4)
            lab.pack(side="left", fill="x", expand=True)
            lab.bind("<Button-1>", lambda e, s=s: self.applica(s))
            x = tk.Label(r, text="✕", bg="#101014", fg=C["grigio"], font=F(8, True), cursor="hand2", padx=8)
            x.pack(side="right")
            x.bind("<Button-1>", lambda e, i=i: (DA.togli_situazione(i), self.disegna_situazioni()))

    def applica(self, s):
        self.tipo = s.get("tipo") or self.tipo
        for k, b in self.b_tipi.items():
            b.metti(k, k == self.tipo)
        self.filtri = dict(s.get("filtri") or {})
        self.disegna()
