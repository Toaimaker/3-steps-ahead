"""La scheda Performance: l'analizzatore di partite e di situazioni (Autore, 12 nov 2026: «riusciamo a modificarla per farla diventare come un analizzatore di
partite ma anche di situazioni come in holdem manager? la possibilita' di aggiungere variabili che ci mostrano come i grafici cambiano», poi «Sì, costruiscila» sulla
proposta). Fino a quel giorno la scheda erano le pagine Limited e Standard con la tendina Mode (pagina_limited, pagina_standard: le classi restano, Your decks
eredita da PaginaStandard).

In testa Constructed o Limited. A sinistra le variabili: ogni tendina filtra (Any = tutte), coi conti delle partite di ogni valore sotto gli altri filtri; sotto, le
situazioni salvate. A destra i numeri della situazione (win rate con l'intervallo di Wilson, record, turni, mulligan, play e draw, quante partite), il grafico
(win rate, partite, turni medi, mulligan; per partite o per data; cumulativo o sulle ultime N; diviso per una variabile, una linea per valore), e il report
raggruppato per una variabile: il clic su una riga la mette fra i filtri, il clic su una colonna ordina. Sotto 15 partite una riga e' grigia: un indizio.
I dati: dati_analizzatore (i nostri log, dal 22 set 2026)."""
import datetime
import threading

import dati_analizzatore as DA
import disegni as DG
from tema import CI as C
from widget import Tendina, pulsante_solido

LINEE = ("#d8d8dc", "#24baff", "#f0ad4e", "#a58cff", "#5cb85c", "#ee8a87")      # All, poi i valori: lontani fra loro anche per i daltonici (come il resto dell'app)
COLONNE = (("nome", "", 250), ("n", "GAMES", 70), ("wl", "W-L", 80), ("wr", "WIN RATE", 180), ("play", "PLAY", 70), ("draw", "DRAW", 70), ("mull", "MULL.", 70),
           ("turni", "AVG T", 70), ("delta", "Δ VS ALL", 90))
TIPI = ("Constructed", "Limited")


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
        self.basso, self.solo_meta = "spots", False       # la parte bassa: spots, report o matchups
        self.righe, self.sporca, self.deciso, self.modo = None, True, False, "Standard"
        self._lavoro, self._img = None, None
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
        # «Smart filters» (12 nov 2026, Autore: «i filtri a sinistra potremmo chiamarli smart filters»), e sotto il pulsante della finestra delle situazioni
        tk.Label(rs, text="SMART FILTERS", bg=C["scheda"], fg=C["muto"], font=F(7, True)).pack(side="left")
        via = tk.Label(rs, text="Clear all", bg=C["scheda"], fg=C["accento"], font=F(7, True), cursor="hand2"); via.pack(side="right")
        via.bind("<Button-1>", lambda e: self.pulisci())
        self.b_sit = pulsante_solido(tk, F, sx, "Situations in the game  ·  none", False, self.apri_situazioni, alto=30, bg=C["scheda"])
        self.b_sit.pack(fill="x", padx=12, pady=(2, 8))
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
        self.tendine = {}
        for k, nome, _f in DA.VARIABILI:
            t = Tendina(tk, self.col_sx, nome, F, larga=262, bg=C["scheda"])
            t.fr.pack(anchor="w", padx=12, pady=(0, 8))
            t.opzioni(["Any"], lambda v, k=k: self.metti_filtro(k, v)); t.set("Any")
            self.tendine[k] = t
        tk.Frame(self.col_sx, bg=C["filo"], height=1).pack(fill="x", padx=12, pady=(6, 8))
        tk.Label(self.col_sx, text="SAVED SITUATIONS", bg=C["scheda"], fg=C["muto"], font=F(7, True)).pack(anchor="w", padx=12)
        self.b_salva_sit = pulsante_solido(tk, F, self.col_sx, "Save this situation", False, self.salva_situazione, alto=28, bg=C["scheda"])
        self.b_salva_sit.configure(width=262); self.b_salva_sit.pack(anchor="w", padx=12, pady=(6, 6))
        self.f_sit = tk.Frame(self.col_sx, bg=C["scheda"]); self.f_sit.pack(fill="x", padx=12, pady=(0, 12))
        # a destra: i numeri, il grafico, il report
        dx = tk.Frame(corpo, bg=C["fondo"]); dx.grid(row=0, column=1, sticky="nsew")
        dx.columnconfigure(0, weight=1); dx.rowconfigure(1, weight=3); dx.rowconfigure(2, weight=2)
        self.cv_num = tk.Canvas(dx, bg=C["scheda"], highlightthickness=1, highlightbackground=C["filo"], height=96, bd=0)
        self.cv_num.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        self.cv_num.bind("<Configure>", lambda e: self.disegna_numeri())
        gr = tk.Frame(dx, bg=C["scheda"], highlightthickness=1, highlightbackground=C["filo"]); gr.grid(row=1, column=0, sticky="nsew", pady=(0, 10))
        bar = tk.Frame(gr, bg=C["scheda"]); bar.pack(fill="x", padx=12, pady=(8, 2))
        self.b_metr = {}
        for k, n in DA.METRICHE:
            b = pulsante_solido(tk, F, bar, n, k == self.metrica, lambda k=k: self.cambia("metrica", k), alto=26, bg=C["scheda"],
                                colori=("#2a2a30", "#3a3a42", "#0f86cc"))
            b.configure(width=112); b.pack(side="left", padx=(0, 6), pady=(14, 0))
            self.b_metr[k] = b
        self.t_dividi = Tendina(tk, bar, "Split by", F, larga=190, bg=C["scheda"]); self.t_dividi.fr.pack(side="right")
        sit_k = ["sit:" + s for s, _n in DA.SIT]
        self.t_dividi.opzioni(["None"] + [k for k, _n, _f in DA.VARIABILI if k not in ("data",)] + sit_k, lambda v: self.cambia("dividi", None if v == "None" else v),
                              etichette={"None": "None", **DA.NOME, **{k: DA.nome_var(k) for k in sit_k}}); self.t_dividi.set("None")
        self.t_fin = Tendina(tk, bar, "Window", F, larga=150, bg=C["scheda"]); self.t_fin.fr.pack(side="right", padx=(0, 10))
        self.t_fin.opzioni([k for k, _n in DA.FINESTRE], lambda v: self.cambia("finestra", v), etichette=dict(DA.FINESTRE)); self.t_fin.set(self.finestra)
        self.t_asse = Tendina(tk, bar, "X axis", F, larga=110, bg=C["scheda"]); self.t_asse.fr.pack(side="right", padx=(0, 10))
        self.t_asse.opzioni(["games", "date"], lambda v: self.cambia("asse", v), etichette={"games": "Games", "date": "Date"}); self.t_asse.set(self.asse)
        self.cv_gr = tk.Canvas(gr, bg=C["scheda"], highlightthickness=0, bd=0, height=220); self.cv_gr.pack(fill="both", expand=True, padx=8, pady=(4, 8))
        self.cv_gr.bind("<Configure>", lambda e: self.disegna_grafico())
        self.cv_gr.bind("<Motion>", self.punta)
        self.cv_gr.bind("<Leave>", lambda e: self.cv_gr.delete("punta"))
        rp = tk.Frame(dx, bg=C["scheda"], highlightthickness=1, highlightbackground=C["filo"]); rp.grid(row=2, column=0, sticky="nsew")
        bar2 = tk.Frame(rp, bg=C["scheda"]); bar2.pack(fill="x", padx=12, pady=(8, 2))
        # tre viste (12 nov 2026, Autore: «aiutare i giocatori a leggere gli spot dove vincono di piu' dove perdono di piu' e potranno incastrare anche i mazzi che
        # utilizzano vs i mazzi del meta o trovati in partite»): gli spot trovati da soli, il report per una variabile, la matrice dei matchup
        self.b_basso = {}
        for k, n in (("spots", "Spots"), ("report", "Report"), ("matchups", "Matchups")):
            b = pulsante_solido(tk, F, bar2, n, k == self.basso, lambda k=k: self.cambia_basso(k), alto=26, bg=C["scheda"], colori=("#2a2a30", "#3a3a42", "#0f86cc"))
            b.configure(width=104); b.pack(side="left", padx=(0, 6), pady=(14, 0))
            self.b_basso[k] = b
        self.t_per = Tendina(tk, bar2, "Group by", F, larga=220, bg=C["scheda"])
        self.t_per.opzioni([k for k, _n, _f in DA.VARIABILI if k != "data"] + sit_k, lambda v: self.cambia("per", v),
                           etichette={**DA.NOME, **{k: DA.nome_var(k) for k in sit_k}}); self.t_per.set(self.per)
        self.b_meta = pulsante_solido(tk, F, bar2, "Meta decks only", self.solo_meta, self.cambia_meta, alto=26, bg=C["scheda"], colori=("#2a2a30", "#3a3a42", "#0f86cc"))
        self.b_meta.configure(width=140)
        self.l_basso = tk.Label(bar2, text="", bg=C["scheda"], fg=C["grigio"], font=F(7)); self.l_basso.pack(side="right", pady=(14, 0))
        self.cv_rp = tk.Canvas(rp, bg=C["scheda"], highlightthickness=0, bd=0, height=160); self.cv_rp.pack(fill="both", expand=True, padx=8, pady=(4, 8))
        self.cv_rp.bind("<Configure>", lambda e: self.disegna_basso())
        self.cv_rp.bind("<Button-1>", self.clic_report)
        self.cv_rp.bind("<MouseWheel>", lambda e: self.cv_rp.yview_scroll(-2 if e.delta > 0 else 2, "units"))
        self.disegna_situazioni()

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

    PARTENZA = dict(metrica="wr", asse="games", finestra="20", dividi=None, per="suo", ordina="n", basso="spots", solo_meta=False)

    def reset(self):
        """Tutte le partite, come all'apertura: niente filtri ne' situazioni, il grafico e la vista in basso di partenza."""
        self.filtri = {}
        for k, v in self.PARTENZA.items():
            setattr(self, k, v)
        for k, b in self.b_metr.items():
            b.metti(dict(DA.METRICHE)[k], k == self.metrica)
        for k, b in self.b_basso.items():
            b.metti(dict(spots="Spots", report="Report", matchups="Matchups")[k], k == self.basso)
        self.b_meta.metti("Meta decks only", False)
        self.t_asse.set(self.asse); self.t_fin.set(self.finestra); self.t_dividi.set("None"); self.t_per.set(self.per)
        self.cv_sx.yview_moveto(0)
        self.disegna()

    def cambia(self, cosa, v):
        setattr(self, cosa, v)
        if cosa == "metrica":
            for k, b in self.b_metr.items():
                b.metti(dict(DA.METRICHE)[k], k == v)
        if cosa in ("metrica", "asse", "finestra", "dividi"):
            self.disegna_grafico()
        else:
            self.disegna_basso()

    def cambia_basso(self, k):
        self.basso = k
        for k2, b in self.b_basso.items():
            b.metti(dict(spots="Spots", report="Report", matchups="Matchups")[k2], k2 == k)
        self.disegna_basso()

    def cambia_meta(self):
        self.solo_meta = not self.solo_meta
        self.b_meta.metti("Meta decks only", self.solo_meta)
        self.disegna_basso()

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
            t.campo.configure(highlightbackground=C["accento"] if sc is not None else "#3a3a40")
        self.aggiorna_bottone_sit()
        self.disegna_finestra_sit()
        self.disegna_numeri()
        self.disegna_grafico()
        self.disegna_basso()

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
        if n_f:
            c.create_text(W - 16, 14, text=f"vs all your {self.tipo.lower()} games: {tot['wr'] if tot['wr'] is not None else '-'}%", anchor="e", fill=C["grigio"], font=F(7))
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
        if k["n"] and k["n"] < 30:
            c.create_text(W - 16, 86, text=f"under 30 games: a hint, not a fact", anchor="e", fill=C["arancio"], font=F(7, True))

    def disegna_grafico(self):
        c = self.cv_gr
        c.delete("all")
        self._img = None
        if self.righe is None:
            return
        F = self.F
        W, H = max(c.winfo_width(), 400), max(c.winfo_height(), 160)
        x0, y0, x1, y1 = 52, 16, W - 120, H - 24
        r = self.scelte()
        lin = [(n, p) for n, p in DA.linee(r, self.metrica, self.asse, self.finestra, self.dividi) if p]
        self._linee = lin
        if not lin:
            c.create_text(W / 2, H / 2, text="No games in this situation", fill=C["grigio"], font=F(9))
            return
        xs = [x for _n, p in lin for x, _y in p]
        ys = [y for _n, p in lin for _x, y in p]
        if self.metrica in ("wr", "mull"):
            ya, yb = 0.0, 100.0
            if self.metrica == "wr":
                ya, yb = max(0.0, min(ys) // 10 * 10 - 10), min(100.0, (max(ys) // 10 + 1) * 10 + 10)
        else:
            ya, yb = 0.0, max(ys) * 1.15 or 1.0
        xa, xb = min(xs), max(xs) if max(xs) > min(xs) else min(xs) + 1
        self._scala = (x0, y0, x1, y1, xa, xb, ya, yb)
        sx = lambda x: x0 + (x - xa) / (xb - xa) * (x1 - x0)
        sy = lambda y: y1 - (y - ya) / (yb - ya) * (y1 - y0)
        passo = 10 if self.metrica in ("wr", "mull") else max(1, round((yb - ya) / 5))
        v = ya
        while v <= yb + 1e-9:
            yy = sy(v)
            c.create_line(x0, yy, x1, yy, fill="#3a3a42" if self.metrica == "wr" and abs(v - 50) < 1e-9 else "#26262c")
            c.create_text(x0 - 8, yy, text=f"{v:.0f}{'%' if self.metrica in ('wr', 'mull') else ''}", anchor="e", fill=C["muto"], font=F(7))
            v += passo
        etx = (lambda x: f"game {int(x)}") if self.asse == "games" else (lambda x: datetime.date.fromordinal(int(x)).strftime("%d %b"))
        c.create_text(x0, y1 + 12, text=etx(xa), anchor="w", fill=C["muto"], font=F(7))
        c.create_text(x1, y1 + 12, text=etx(xb), anchor="e", fill=C["muto"], font=F(7))
        tratti = []
        for i, (n, p) in enumerate(lin):
            col = LINEE[i % len(LINEE)]
            pts = [(sx(x), sy(y)) for x, y in p]
            if len(pts) == 1:
                pts = [pts[0], (pts[0][0] + 1, pts[0][1])]
            # sottili (12 nov 2026, Autore: «le linee dei grafici le voglio piu' sottili»; erano 2,4 / 2,0 / 1,6)
            tratti.append((pts, col, 1.4 if n == "All" and len(lin) == 1 else 1.2 if n != "All" else 1.0, None))
            c.create_text(x1 + 8, pts[-1][1], text=f"{n}  {p[-1][1]:.0f}{'%' if self.metrica in ('wr', 'mull') else ''}", anchor="w", fill=col, font=F(7, True))
        self._img = DG.tratti(W, H, linee=tratti)
        c.create_image(0, 0, image=self._img, anchor="nw")
        if self.asse == "games" and len(lin) == 1:       # i cambi di lega, come nel grafico di prima
            for i_, rango in DA.cambi_rango(r):
                xx = sx(i_)
                c.create_line(xx, y0, xx, y1, fill="#3a3a42", dash=(3, 3))
                c.create_text(xx + 4, y0 + 2, text=rango, anchor="nw", fill=C["grigio"], font=F(7, True))
        tit = {"wr": "win rate", "n": "games", "turni": "average length in your turns", "mull": "mulligan rate"}[self.metrica]
        fin = "" if self.metrica == "n" else (", cumulative" if self.finestra == "cum" else f", last {self.finestra} games")
        c.create_text((x0 + x1) / 2, 4, text=f"{tit}{fin}" + (f" · split by {DA.nome_var(self.dividi).lower()}" if self.dividi else ""), anchor="n", fill=C["grigio"], font=F(7))

    def punta(self, e):
        """Il puntatore sul grafico: la linea verticale e il valore di ogni linea in quel punto."""
        c = self.cv_gr
        c.delete("punta")
        if not getattr(self, "_linee", None) or not getattr(self, "_scala", None):
            return
        x0, y0, x1, y1, xa, xb, _ya, _yb = self._scala
        if not x0 <= e.x <= x1:
            return
        xv = xa + (e.x - x0) / (x1 - x0) * (xb - xa)
        c.create_line(e.x, y0, e.x, y1, fill="#4a4a52", tags="punta")
        righe = []
        for i, (n, p) in enumerate(self._linee):
            q = min(p, key=lambda t: abs(t[0] - xv))
            righe.append((f"{n}: {q[1]:.1f}{'%' if self.metrica in ('wr', 'mull') else ''}", LINEE[i % len(LINEE)]))
        etx = f"game {round(xv)}" if self.asse == "games" else datetime.date.fromordinal(int(round(xv))).strftime("%d %b %Y")
        bx = e.x + 12 if e.x < (x0 + x1) / 2 else e.x - 170
        c.create_rectangle(bx, y0 + 4, bx + 160, y0 + 22 + 15 * len(righe), fill="#101014", outline="#3a3a42", tags="punta")
        c.create_text(bx + 8, y0 + 12, text=etx, anchor="w", fill=C["titolo"], font=self.F(7, True), tags="punta")
        for j, (t, col) in enumerate(righe):
            c.create_text(bx + 8, y0 + 27 + 15 * j, text=t, anchor="w", fill=col, font=self.F(7), tags="punta")

    def disegna_basso(self):
        """La parte bassa: la vista scelta, coi suoi comandi accanto alle linguette."""
        self.t_per.fr.pack_forget(); self.b_meta.pack_forget()
        if self.basso == "report":
            self.t_per.fr.pack(side="left", padx=(16, 0), after=self.b_basso["matchups"])
            self.l_basso.configure(text="click a row: add it as a filter · click a column: sort")
            self.disegna_report()
        elif self.basso == "matchups":
            self.b_meta.pack(side="left", padx=(16, 0), pady=(14, 0), after=self.b_basso["matchups"])
            self.l_basso.configure(text="your decks against the archetypes you met · click a cell: filter it · grey: under 5 games")
            self.disegna_matchup()
        else:
            self.l_basso.configure(text="found by themselves in this situation, one or two variables, at least 15 games · click one: filter it")
            self.disegna_spot()

    def disegna_spot(self):
        """Dove vinci e dove perdi di piu': due colonne, gli spot che reggono in testa (l'intervallo sta tutto dalla loro parte: «strong»)."""
        c = self.cv_rp
        c.delete("all")
        self._spot_box = []
        if self.righe is None:
            return
        F = self.F
        r = self.scelte()
        minimo = 15 if len(r) >= 90 else max(6, len(r) // 6)
        meglio, peggio = DA.spot(r, minimo=minimo, quanti=7, gia=self.filtri)
        base = DA.conti(r)["wr"]
        W = max(c.winfo_width(), 700)
        meta = (W - 24) / 2
        for j, (tit, lista, col) in enumerate((("WHERE YOU WIN MOST", meglio, C["azzurro"]), ("WHERE YOU LOSE MOST", peggio, C["rosso"]))):
            x = 8 + j * (meta + 8)
            c.create_text(x, 10, text=tit, anchor="w", fill=col, font=F(7, True))
            c.create_text(x + meta - 8, 10, text=f"vs {base:.0f}% in this situation" if base is not None else "", anchor="e", fill=C["muto"], font=F(7))
            y = 26
            if not lista:
                c.create_text(x, y + 12, text=f"nothing yet: no spot with {minimo}+ games that stands out", anchor="w", fill=C["grigio"], font=F(8))
            for s in lista:
                c.create_rectangle(x, y, x + meta - 8, y + 40, fill="#202024", outline=col if s["forte"] else "#2c2c32")
                nome = s["nome"] if len(s["nome"]) <= 70 else s["nome"][:69] + "…"
                c.create_text(x + 10, y + 13, text=nome, anchor="w", fill=C["titolo"], font=F(8, True))
                c.create_text(x + 10, y + 29, text=f"{s['n']} games · {s['vinte']}-{s['perse']} · 95% CI {s['ic'][0]}–{s['ic'][1]}%"
                              + ("  ·  strong" if s["forte"] else "  ·  a hint"), anchor="w", fill=C["grigio"] if s["forte"] else C["muto"], font=F(7))
                c.create_text(x + meta - 20, y + 13, text=f"{s['wr']:.0f}%", anchor="e", fill=col, font=F(12, True))
                c.create_text(x + meta - 20, y + 30, text=f"{s['delta']:+.0f}", anchor="e", fill=col, font=F(8, True))
                self._spot_box.append((x, y, x + meta - 8, y + 40, s))
                y += 46
        c.configure(scrollregion=(0, 0, W, 26 + 46 * max(len(meglio), len(peggio), 1) + 10))

    def disegna_matchup(self):
        """La matrice: i tuoi mazzi in riga, gli archetipi incontrati in colonna (o solo quelli del meta), in ogni cella win rate e partite."""
        c = self.cv_rp
        c.delete("all")
        self._celle = []
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
                self._celle.append((x, y, x + cw, y + rh, m, a))
            c.create_text(x0 + len(archi) * cw + 40, y + rh / 2, text=f"{wr:.0f}%", fill=C["azzurro"] if wr >= 50 else C["rosso"], font=F(8, True))
            y += rh + 2
        c.configure(scrollregion=(0, 0, W, y + 10))

    def disegna_report(self):
        c = self.cv_rp
        c.delete("all")
        self._righe_rp = []
        if self.righe is None:
            return
        F = self.F
        rep = DA.report(self.scelte(), self.per, self.ordina if self.ordina != "wl" else "vinte")
        W = max(c.winfo_width(), 700)
        x = 8
        self._col_x = []
        for k, t, w in COLONNE:
            c.create_text(x, 10, text=t or DA.nome_var(self.per).upper()[:32], anchor="w", fill=C["accento"] if k == self.ordina else C["titolo"], font=F(7, True))
            self._col_x.append((x, x + w, k))
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
            self._righe_rp.append((y - 2, y + 22, r["valore"]))
            y += 24
        if not rep:
            c.create_text(12, 40, text="No games in this situation", anchor="w", fill=C["grigio"], font=F(8))
        c.create_text(8, y + 10, text="grey: under 15 games, a hint", anchor="w", fill=C["muto"], font=F(7))
        c.configure(scrollregion=(0, 0, W, y + 24))

    def clic_report(self, e):
        y = self.cv_rp.canvasy(e.y)
        if self.basso == "spots":       # uno spot: le sue condizioni fra i filtri
            for x0, y0, x1, y1, s in getattr(self, "_spot_box", []):
                if x0 <= e.x <= x1 and y0 <= y <= y1:
                    for k, v in s["condizioni"]:
                        self.filtri[k] = v
                    self.disegna()
                    return
            return
        if self.basso == "matchups":        # una cella: il tuo mazzo e il suo archetipo fra i filtri
            for x0, y0, x1, y1, m, a in getattr(self, "_celle", []):
                if x0 <= e.x <= x1 and y0 <= y <= y1:
                    self.filtri["mio"], self.filtri["suo"] = m, a
                    self.disegna()
                    return
            return
        if y < 22:      # le intestazioni: ordina
            for a, b, k in getattr(self, "_col_x", []):
                if a <= e.x < b:
                    self.ordina = "nome" if k == "nome" else k
                    self.disegna_report()
                    return
            return
        for a, b, v in getattr(self, "_righe_rp", []):
            if a <= y < b:
                self.filtri[self.per] = v
                self.disegna()
                return

    # ------------------------------------------------------------ le situazioni dentro la partita (12 nov 2026)
    def apri_situazioni(self):
        """La finestra delle situazioni (Autore, 12 nov 2026: «una finestra di filtri da flaggare che aggiungono agli smart situazioni piu' specifiche»): per
        ognuna Any, Yes o No, coi conti delle partite sotto gli altri filtri; si applica subito. Accanto alla colonna dei filtri, sopra la finestra grande."""
        tk, F = self.tk, self.F
        f = getattr(self, "fin_sit", None)
        if f is not None and f.winfo_exists():
            f.lift(); return f
        f = self.fin_sit = tk.Toplevel(self.fr); f.title("Situations in the game"); f.configure(bg=C["scheda"])
        f.transient(self.fr.winfo_toplevel())
        f.geometry(f"+{self.cv_sx.winfo_rootx() + self.cv_sx.winfo_width() + 16}+{self.cv_sx.winfo_rooty()}")
        f.bind("<Escape>", lambda e: f.destroy())
        tk.Label(f, text="SITUATIONS IN THE GAME", bg=C["scheda"], fg=C["titolo"], font=F(9, True)).pack(anchor="w", padx=14, pady=(12, 2))
        tk.Label(f, text="From the games' turn by turn records. Yes: only the games where it happened; No: only those where it did not.", bg=C["scheda"],
                 fg=C["grigio"], font=F(7), wraplength=470, justify="left").pack(anchor="w", padx=14, pady=(0, 8))
        self.cv_fsit = tk.Canvas(f, bg=C["scheda"], highlightthickness=0, bd=0, width=500, height=40 + 34 * len(DA.SIT))
        self.cv_fsit.pack(padx=8, pady=(0, 12))
        self.cv_fsit.bind("<Button-1>", self.clic_situazione)
        self.disegna_finestra_sit()
        return f

    def disegna_finestra_sit(self):
        c = getattr(self, "cv_fsit", None)
        if c is None or not c.winfo_exists():
            return
        F = self.F
        c.delete("all")
        self._box_sit = []
        y = 6
        for k, nome in DA.SIT:
            kk = "sit:" + k
            sc = self.filtri.get(kk)
            c.create_text(8, y + 14, text=nome, anchor="w", fill=C["titolo"] if sc else C["testo"], font=F(8, bool(sc)))
            x = 300
            for v, t in ((None, "Any"), ("Yes", "Yes"), ("No", "No")):     # senza i conti, come le tendine (12 nov 2026)
                on = sc == v
                w = 50 if v is None else 66
                c.create_rectangle(x, y + 3, x + w, y + 25, fill="#0f86cc" if on else "#202024", outline="#0f86cc" if on else "#3a3a40")
                c.create_text(x + w / 2, y + 14, text=t, fill="#ffffff" if on else C["grigio"], font=F(7, True))
                self._box_sit.append((x, y + 3, x + w, y + 25, kk, v))
                x += w + 6
            y += 34

    def clic_situazione(self, e):
        for x0, y0, x1, y1, kk, v in getattr(self, "_box_sit", []):
            if x0 <= e.x <= x1 and y0 <= e.y <= y1:
                self.filtri[kk] = v
                self.disegna()
                return

    def aggiorna_bottone_sit(self):
        on = [(k, v) for k, v in self.filtri.items() if k.startswith("sit:") and v is not None]
        self.b_sit.metti("Situations in the game  ·  " + (f"{len(on)} on" if on else "none"), bool(on))

    # ------------------------------------------------------------ le situazioni salvate
    def salva_situazione(self):
        DA.salva_situazione(self.tipo, dict(self.filtri))
        self.disegna_situazioni()
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
