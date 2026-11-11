"""Il contenuto della finestra di un mazzo."""
import threading
import piattaforma  # (la rotella su Windows e su Mac)
import webbrowser

import capsule as CAP
import dati_mazzo as DM
import disegni as DG
import mazzi_salvati as MS
import prezzi_carte as PZ

from dati_app import BASI, COL_RARITA, NOMI_RARITA, _PREZZI_AGGIORNATI, collezione, collezione_nota, craft, jolly, rarita_nome, saldo_partite
from dati_meta import FORMATI_META, meta_mazzi
from icone import icona_azione, icona_jolly
from tema import CI as C, PERSA, VINTA


_RADAR = {}       # (lato, assi) -> l'immagine del grafo dell'archetipo


class SchedaMazzo:
    """Il contenuto della finestra del mazzo: testata, lista, dati, jolly, archetipo, mani, terre in mano, grafico."""

    def radar(self, padre, assi, lato=112):
        """Il grafo dell'archetipo: quattro assi, il poligono dei punti. Il massimo del disegno e' il 60%: un mazzo puro non esce dal quadro."""
        tk, F = self.tk, self.F
        L, A = lato + 116, lato + 34       # i nomi degli assi stanno fuori dal rombo
        c = tk.Canvas(padre, width=L, height=A, bg=C["cap"], highlightthickness=0, bd=0)
        cx, cy, r = L / 2, A / 2, lato / 2 - 4
        dirs = {0: (0, -1), 1: (1, 0), 2: (0, 1), 3: (-1, 0)}
        chiave = (id(padre._root()), lato, tuple(assi.items()))       # (la radice: un'immagine vale solo nella sua) lo stesso grafo si ridisegna uguale: l'immagine si ricorda (11 nov 2026: 58 ms ad apertura)
        cache = _RADAR
        if chiave in cache:
            c.foto_ = cache[chiave]
            c.create_image(0, 0, image=c.foto_, anchor="nw")
            for i, (nome, val) in enumerate(assi.items()):
                dx, dy = dirs[i]
                c.create_text(cx + dx * (r + 4), cy + dy * (r + 4), text=f"{nome} {val}", anchor={0: "s", 1: "w", 2: "n", 3: "e"}[i], fill=C["testo"], font=F(7))
            return c
        d = DG.Disegno(L, A)            # i rombi, gli assi e il poligono nitidi (disegni.py); i nomi degli assi restano testo di Tk
        for k in (1.0, 0.5):
            d.poligono([(cx + dirs[i][0] * r * k, cy + dirs[i][1] * r * k) for i in range(4)], bordo=C["filo"], larghezza=1)
        punti = []
        for i, (nome, val) in enumerate(assi.items()):
            dx, dy = dirs[i]
            d.linea([(cx, cy), (cx + dx * r, cy + dy * r)], C["filo"], 1, tondo=False)
            q = min(1, val / 60)
            punti.append((cx + dx * r * q, cy + dy * r * q))
        d.poligono(punti, riempi=C["azzurro_s"], bordo=C["accento"], larghezza=2)
        c.foto_ = d.foto()
        if len(cache) > 60:
            cache.clear()
        cache[chiave] = c.foto_
        c.create_image(0, 0, image=c.foto_, anchor="nw")
        for i, (nome, val) in enumerate(assi.items()):
            dx, dy = dirs[i]
            ancora = {0: "s", 1: "w", 2: "n", 3: "e"}[i]
            c.create_text(cx + dx * (r + 4), cy + dy * (r + 4), text=f"{nome} {val}", anchor=ancora, fill=C["testo"], font=F(7))
        return c

    def quadro_mazzo(self, padre, an, arch):
        """Sotto i numeri: a sinistra il grafo dell'archetipo, a destra le mani (Autore, 7 nov 2026: «le best starting hand che hanno decretato lo snowball della partita»)."""
        tk, F = self.tk, self.F
        padre.columnconfigure(1, weight=1)
        sx = tk.Frame(padre, bg=C["cap"], padx=6, pady=4); sx.grid(row=0, column=0, sticky="ns", padx=(0, 6))
        self.etichetta(sx, "archetype", C["cap"]).pack(anchor="w")
        if arch:
            tk.Label(sx, text=arch[0], bg=C["cap"], fg=C["acciaio"], font=F(9, True), pady=0).pack(anchor="w")
            self.radar(sx, arch[1]).pack()
        else:
            tk.Label(sx, text="-", bg=C["cap"], fg=C["grigio"], font=F(9)).pack(anchor="w")
        if an is None:
            return
        # mani, vittorie veloci e terre come tabelle, non come righe di testo (Autore, 8 nov 2026: «la scheda starting hands fa schifo, e' un blocco di testo disordinato»):
        # una colonna per dato con l'intestazione sopra, le righe a fasce alterne, tutta la riga cliccabile e accesa sotto il puntatore
        dx = tk.Frame(padre, bg=C["cap"], padx=8, pady=6); dx.grid(row=0, column=1, sticky="nsew")
        carte = getattr(self, "carte_db", None) or {}

        def corto(n, k=28):
            return n if len(n) <= k else n[:k - 1].rstrip() + "…"

        def titolo(t, primo=False):
            self.etichetta(dx, t, C["cap"]).pack(anchor="w", pady=(0 if primo else 10, 3))

        def vuoto(t):
            tk.Label(dx, text=t, bg=C["cap"], fg=C["grigio"], font=F(8), anchor="w", pady=0).pack(fill="x")

        def record(v, n):
            return self.cella(f"{v}-{n - v}", C["verde_t"] if 2 * v > n else C["rosso_t"] if 2 * v < n else C["testo"], True)

        def nomi_cella(nomi):
            return self.cella_righe([(corto(n), C["titolo"], True, 8) for n in nomi])

        freccia = self.cella("›", C["acciaio"], True, 12)

        def cliccabile(riga, azione):
            """Tutta la riga apre la mano; accesa finche' il puntatore sta su uno dei suoi pezzi (passare da una cella all'altra non la spegne)."""
            if hasattr(riga, "cliccabile"):       # una riga della tabella su tela (11 nov 2026)
                riga.cliccabile(azione)
                return
            pezzi = [w for c in riga for w in [c, *c.winfo_children()]]
            fondo = {w: w["bg"] for w in pezzi}

            def accendi(e=None):
                for w in pezzi:
                    w.configure(bg=C["sel"])

            def forse_spegni(e=None):
                def dopo():
                    try:
                        sotto = riga[0].winfo_containing(*riga[0].winfo_pointerxy())
                    except Exception:
                        sotto = None
                    if sotto not in pezzi:
                        for w in pezzi:
                            if w.winfo_exists():
                                w.configure(bg=fondo[w])
                riga[0].after(30, dopo)
            for w in pezzi:
                w.configure(cursor="hand2")
                w.bind("<Enter>", accendi); w.bind("<Leave>", forse_spegni); w.bind("<Button-1>", lambda e: azione())

        titolo("best starting hands", True)
        if an["mani"]:
            righe = self.tabella(dx, [("hand", "w"), ("record", "e"), ("closes on", "e"), ("", "e")],
                                 [[nomi_cella(m["carte"]), record(m["v"], m["n"]), self.cella(f"T{m['turno']:.1f}" if m["turno"] else "-", C["titolo"], True), freccia]
                                  for m in an["mani"]], allarga=0)
            for m, r in zip(an["mani"], righe):
                if m.get("esempi"):
                    cliccabile(r, lambda m=m: self.finestra_mani(f"{m['carte'][0]} + {m['carte'][1]}", m["esempi"], m["carte"]))
        else:
            vuoto("No pair of cards seen in 3 games yet")

        titolo("snowball · fastest wins")
        if an["veloci"]:
            def chiave(n):
                c = carte.get(n) or carte.get(n.split(" // ")[0].strip()) or {}
                return (-c.get("cmc", 0), n)

            def magie_cella(x):
                d = sorted(dict.fromkeys(x["magie"]), key=chiave)       # le piu' care in testa: sono le minacce della mano
                return self.cella_righe([(corto(n, 26) + (f"  +{len(d) - 2}" if i == 1 and len(d) > 2 else ""), C["titolo"], True, 8) for i, n in enumerate(d[:2])])
            righe = self.tabella(dx, [("turn", "w"), ("start", "w"), ("lands", "e"), ("hand", "w"), ("", "e")],
                                 [[self.cella(f"T{x['turno']}", C["verde_t"], True, 11, "left"), self.cella("play" if x["primo"] else "draw", lato="left"),
                                   self.cella(str(x["terre"])), magie_cella(x), freccia] for x in an["veloci"]], allarga=3)
            for x, r in zip(an["veloci"], righe):
                if x.get("mano"):
                    cliccabile(r, lambda x=x: self.finestra_mani(f"Won on T{x['turno']}", [x], ()))
        else:
            vuoto("No wins with turn data yet")

        self.etichetta(sx, "lands in opening hand", C["cap"]).pack(anchor="w", pady=(8, 3))
        if not an["terre"]:
            tk.Label(sx, text="No games yet", bg=C["cap"], fg=C["grigio"], font=F(8), anchor="w", pady=0).pack(fill="x")
        else:
            g = tk.Frame(sx, bg=C["cap"]); g.pack(fill="x")
            voci = sorted(an["terre"].items())
            for j in range(2):
                g.columnconfigure(j, weight=1, uniform="terre")
            for j, (k, (v, n)) in enumerate(voci):
                b = tk.Frame(g, bg=C["scheda"], padx=6, pady=3); b.grid(row=j // 2, column=j % 2, sticky="nsew", padx=(0, 4 if j % 2 == 0 else 0), pady=(0, 4))
                self.etichetta(b, f"{k} land" + ("" if k == 1 else "s"), C["scheda"]).pack(anchor="w")
                q = round(100 * v / n)
                tk.Label(b, text=f"{q}%", bg=C["scheda"], fg=C["verde_t"] if q > 50 else C["rosso_t"] if q < 50 else C["titolo"], font=F(11, True), pady=0).pack(anchor="w")
                tk.Label(b, text=f"{v}-{n - v} · {n} games" if n != 1 else f"{v}-{n - v} · 1 game", bg=C["scheda"], fg=C["grigio"], font=F(7), pady=0).pack(anchor="w")

    def scheda_mazzo(self):
        tk, F = self.tk, self.F
        dentro = tk.Frame(self.det, bg=C["scheda"]); dentro.pack(fill="both", expand=True)
        tipo, chi = self.aperto
        comandante, compagno = {}, {}
        coll, quando_coll = collezione()
        jl, quando_jl = jolly()
        if tipo == "mio":
            partite = [x for x in self.pp if x["nome"] == chi or (not x["nome"] and chi.startswith("Unnamed"))]
            ultima = max((x for x in partite if x["ds"]), key=lambda x: x["quando"], default=None)
            main, side = {}, {}
            if ultima:
                from deckstring import decodifica
                try:
                    main = decodifica(ultima["ds"]); side = dict(getattr(decodifica, "side", {}) or {})
                except Exception:
                    main, side = {}, {}
            nome, colori = chi, (ultima or {}).get("colori", "")
            am = self.mazzo_arena(chi)
            if am:      # la lista vera, anche di un mazzo mai giocato; le partite sono quelle di questo mazzo
                partite, nome, colori = am["partite"], am["nome"], am["colori"]
                main, side, comandante, compagno = dict(am["main"]), dict(am["side"]), dict(am["comandante"]), dict(am["compagno"])
        elif tipo == "farm":
            m = chi
            main, side = {}, {}
            if m.get("ds"):
                from deckstring import decodifica
                try:
                    main = decodifica(m["ds"]); side = dict(decodifica.side or {})
                    comandante, compagno = dict(decodifica.comandanti), dict(decodifica.compagni)
                except Exception:
                    main, side = {}, {}
            nome, colori = m["nome"], m.get("colori", "")
            partite = [x for x in self.pp if x["nome"] == nome]
        else:       # meta, wishlist e build: il mazzo e' un dizionario con la sua lista
            m = chi
            main, side = dict(m.get("lista") or {}), dict(m.get("side") or {})
            comandante, compagno = dict(m.get("comandante") or {}), dict(m.get("compagno") or {})   # Brawl, Explorer
            nome, colori, partite = m["nome"], m.get("colori", ""), []
        # la testata: colori e nome, a destra le azioni
        cap = tk.Frame(dentro, bg=C["cap"]); cap.pack(fill="x")
        self.mana_label(cap, colori, C["cap"]).pack(side="left", padx=(12, 8), pady=10)
        tk.Label(cap, text=nome, bg=C["cap"], fg=C["titolo"], font=F(14, True)).pack(side="left")
        tk.Frame(dentro, bg=C["filo"], height=1).pack(fill="x")
        # a sinistra la lista, in due colonne (Autore, 7 nov 2026: «la lista a sx le terre in una sotto lista e la side a sx / tutto piu' piccolo e meglio organizzato»), a destra i dati dall'alto in basso
        corpo = tk.Frame(dentro, bg=C["scheda"]); corpo.pack(fill="both", expand=True, padx=10, pady=8)
        corpo.columnconfigure(0, weight=11, uniform="det"); corpo.columnconfigure(1, weight=10, uniform="det"); corpo.rowconfigure(0, weight=1)
        sx_l = tk.Frame(corpo, bg=C["scheda"]); sx_l.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        dx_d = tk.Frame(corpo, bg=C["scheda"]); dx_d.grid(row=0, column=1, sticky="nsew")
        lista = CAP.Liste(tk, F, alto=20)
        # i jolly sopra il nome del mazzo, l'esportazione sotto la lista (Autore, 7 nov 2026: «sposta le wildcards sopra il nome del mazzo / sotto il mazzo invece tutte le opzioni di esportazione compreso magic online»)
        barra_jolly = tk.Frame(sx_l, bg=C["cap"], padx=8, pady=4); barra_jolly.pack(fill="x", pady=(0, 6))
        esporta = tk.Frame(sx_l, bg=C["scheda"]); esporta.pack(side="bottom", fill="x", pady=(6, 0))
        if main or side or comandante:      # il Board, sotto la lista al centro, da guardare: si personalizza solo in modalita' edit (Autore, 10 nov 2026: «il pulsante per
            # vedere la lista in carte sara' sotto le pillow al centro ma non avra' i tool di editing del mazzo», «card view cambia nome in lavagna in inglese»)
            from widget import ARANCIO, pulsante_solido
            sotto_l = tk.Frame(sx_l, bg=C["scheda"]); sotto_l.pack(side="bottom", fill="x", pady=(6, 0))
            b_carte = pulsante_solido(tk, F, sotto_l, "Board", False, lambda: self.vista_carte(tipo, chi, nome, main, side, comandante, compagno), alto=28, bg=C["scheda"],
                                      colori=ARANCIO)       # in arancio come nel builder (10 nov 2026)
            b_carte.configure(width=150); b_carte.pack(anchor="center")
        if not _PREZZI_AGGIORNATI:
            _PREZZI_AGGIORNATI.append(1)
            threading.Thread(target=PZ.aggiorna, daemon=True).start()
        carte_db = DM.tabella_carte()
        if tipo == "meta" and m.get("carte_info"):      # le carte che Arena non ha (Modern, Legacy...): tipo, mana e testo da Scryfall
            carte_db = {**{n: dict(nome=n, tipo=v["tipo"], cmc=v["cmc"], testo=v.get("testo", "")) for n, v in m["carte_info"].items()}, **carte_db}
        # on the play e on the draw si premono e filtrano la scheda (Autore, 10 nov 2026: «sulle schede del mazzo fai che i dati di analytics varino in base al
        # premere on the draw on the play»): Performance, Analysis, mani, snowball, terre in mano e grafico leggono solo quelle partite; le due tessere restano su tutte
        tutte_p = partite
        partenza = getattr(self, "partenza", None)
        partite = DM.per_partenza(tutte_p, partenza)
        an_tutte = DM.analizza(tutte_p, carte_db) if tutte_p else None
        an = (an_tutte if not partenza else DM.analizza(partite, carte_db)) if partite else None
        self.carte_db = carte_db
        # i numeri del mazzo
        tutte = dict(main)
        for n, q in list(side.items()) + list(comandante.items()) + list(compagno.items()):
            tutte[n] = tutte.get(n, 0) + q
        manca, si = craft(tutte, coll, jl)
        # il valore delle carte vere (Autore, 7 nov 2026: «alle carte aggiungiamo anche il valore economico della carta reale e diamo anche il dato di costo totale del mazzo»)
        eur, usd, senza = PZ.totale(tutte)
        tix = sum(q * ((PZ.prezzo(n) or {}).get("tix") or 0) for n, q in tutte.items())
        v_carta = ("paper price", PZ.euro(eur) if len(senza) < len(tutte) else "-", None, (f"${usd:,.0f}" if usd >= 100 else f"${usd:.2f}") + (f" · {sum(tutte[n] for n in senza)} digital only" if senza else ""))
        v_mtgo = ("mtgo price", f"{tix:,.1f} tix" if tix else "-", None)
        # le stesse voci per ogni mazzo, da qualunque scheda lo apri (Autore, 9 nov 2026: «ogni mazzo nell'app, in qualunque scheda, quando li apro devono avere sempre la stessa
        # identica configurazione scheda mazzo e usiamo quella assolutamente piu' completa che abbiamo»): le partite, la costruzione e il meta, i prezzi; un dato che non c'e' esce «-»
        v_part = self.voci_partite(partite, an, nome, an_tutte=an_tutte)
        v_build = self.voci_build(dict(formato=self.formato_mazzo(tipo, chi)), main, side, comandante, compagno, coll, carte_db, meta=m if tipo == "meta" else None)
        # i jolly stanno in alto a sinistra sul grafico, come su Untapped (Autore, 18 ott 2026): il riquadro sotto
        if collezione_nota():
            self.riquadro_jolly(barra_jolly, manca, si, jl)
        else:       # l'app pubblica senza la collezione (10 nov 2026): i jolly non si sanno
            tk.Label(barra_jolly, text="WILDCARDS  ·  link your Untapped profile in Help to see the cards you own and the wildcards you need", bg=C["cap"],
                     fg=C["grigio"], font=F(8), anchor="w").pack(fill="x")
        # l'esportazione, sotto la lista: Arena e Magic Online, da copiare o da salvare in un file
        self.esportazione(esporta, nome, main, side, comandante, compagno, self.azioni_mazzo(tipo, chi, nome, main, side, comandante, compagno))
        if tipo == "meta" and m.get("url"):     # la pagina originale del mazzo (Autore: «sempre linkati ai dati originali»)
            orig = tk.Label(cap, text="MTGGOLDFISH ↗" if "mtggoldfish" in m["url"] else "UNTAPPED ↗", bg=C["cap"], fg=C["accento"], font=F(7, True), cursor="hand2", padx=10)
            orig.pack(side="right"); orig.bind("<Button-1>", lambda e, u=m["url"]: webbrowser.open(u))
        d_pz = PZ.data()
        nota = " · ".join(x for x in ((f"collection of {quando_coll:%d/%m}" if quando_coll else ""), (f"wildcards of {quando_jl:%d/%m %H:%M}" if quando_jl else ""),
                                      (f"prices of {d_pz[8:10]}/{d_pz[5:7]}, cheapest paper printing" if d_pz else "")) if x)
        tk.Label(dx_d, text=nota, bg=C["scheda"], fg=C["muto"], font=F(7), anchor="w").pack(side="bottom", fill="x")
        # a destra i dati in sezioni a tendina, una sotto l'altra, in una colonna che scorre (Autore, 10 nov 2026: «riorganizziamo i dati in maniera piu' elegante nelle
        # schede mazzo, parlo di quelli messi in tesserine non dei grafici / mettiamoli su tendine espandibili / aggiungiamo una sezione di analisi»). Aperte o chiuse
        # restano per tutti i mazzi; la stessa scheda per ogni mazzo, da qualunque sezione (9 nov 2026)
        cv_d = tk.Canvas(dx_d, bg=C["scheda"], highlightthickness=0, bd=0); cv_d.pack(fill="both", expand=True)
        col = tk.Frame(cv_d, bg=C["scheda"]); win_d = cv_d.create_window(0, 0, window=col, anchor="nw")
        col.bind("<Configure>", lambda e: cv_d.configure(scrollregion=(0, 0, 0, col.winfo_reqheight())))
        cv_d.bind("<Configure>", lambda e: cv_d.itemconfigure(win_d, width=e.width))
        self.colonna_dati = cv_d

        def rotella_d(e):
            if col.winfo_reqheight() > cv_d.winfo_height():
                cv_d.yview_scroll(piattaforma.scatti(e.delta) * 2, "units")

        def rilega(w=None):
            """La rotella su tutta la colonna, anche sui pezzi nati dopo (una sezione aperta, l'analisi arrivata)."""
            w = w or cv_d
            w.bind("<MouseWheel>", rotella_d)
            for x in w.winfo_children():
                rilega(x)
            if w is cv_d:
                cv_d.after_idle(lambda: cv_d.configure(scrollregion=(0, 0, 0, col.winfo_reqheight())) if cv_d.winfo_exists() else None)
        n_ = len(partite)
        nome_p = {"play": "on the play", "draw": "on the draw"}.get(partenza)
        if partenza:        # la riga del filtro in cima: si vede sempre che la scheda e' filtrata, e si toglie da li'
            fb = tk.Frame(col, bg=C["sel"], highlightthickness=1, highlightbackground=C["accento"]); fb.pack(fill="x", pady=(0, 8))
            tk.Label(fb, text=f"SHOWING ONLY GAMES {nome_p.upper()}  ·  {n_} of {len(tutte_p)}", bg=C["sel"], fg=C["accento"], font=F(8, True), padx=10, pady=6,
                     anchor="w").pack(side="left")
            via = tk.Label(fb, text="Show all games  ✕", bg=C["sel"], fg=C["titolo"], font=F(8, True), padx=10, cursor="hand2"); via.pack(side="right")
            via.bind("<Button-1>", lambda e: self.filtra_partenza(None))
            self.riga_filtro = fb
        else:
            self.riga_filtro = None
        clic = {"on the play": lambda: self.filtra_partenza("play"), "on the draw": lambda: self.filtra_partenza("draw")} if tutte_p else {}
        self.tessere_partite = self.tessere(self.sezione_tendina(col, "prestazioni", "Performance", (f"{n_} game{'s' if n_ != 1 else ''}" + (f" {nome_p}" if nome_p else ""))
                                                                 if n_ else ("no games " + nome_p if nome_p else "no games yet"), dopo=rilega),
                                            v_part[:4], colonne=4, clic=clic, scelta=nome_p)
        s_an = self.sezione_tendina(col, "analisi", "Analysis", "from your Arena logs" + (f" · {nome_p}" if nome_p else ""), dopo=rilega)
        # in Performance solo la prima riga (win rate, games played, on the play, on the draw); closes on e loses on in cima ad Analysis (Autore, 10 nov 2026:
        # «nei dati schede mazzo in performance tieni solo la prima riga, il resto dei dati va in analytics»)
        self.tessere_analisi = self.tessere(s_an, v_part[4:], colonne=4)
        self.sezione_analisi(s_an, tipo, chi, main, side, comandante, compagno, carte_db, lista, dopo=rilega, partenza=partenza)
        # le mani, lo snowball e le terre in mano ci sono sempre, vuote se il mazzo non ha partite: la stessa scheda per ogni mazzo (9 nov 2026)
        arch = DM.archetipo({**comandante, **main}, carte_db, an["chiude"] if an else None)
        self.quadro_mazzo(self.sezione_tendina(col, "mani", "Archetype & hands", arch[0] if arch else "", dopo=rilega), an or dict(mani=[], veloci=[], terre={}), arch)
        gf = tk.Frame(self.sezione_tendina(col, "grafico", "Win rate", "", dopo=rilega), bg=C["scheda"]); gf.pack(fill="x")      # il grafico c'e' sempre: senza partite lo dice
        pt_, ini, lg, _ = saldo_partite(partite, ev=None) if partite else ([], [], [], None)
        self.grafico(gf, pt_, ini, lg, (), vuoto="No games with this deck yet", altezza=170, tipo_lega="constructed")
        s_b = self.sezione_tendina(col, "costruzione", "Deck build", f"{v_build[0][1]} · " + ("legal" if not self._problemi else f"{len(self._problemi)} issue{'s' if len(self._problemi) > 1 else ''}"),
                           dopo=rilega)
        self.tessere(s_b, v_build, colonne=4)
        if self._problemi:      # i problemi di legalita', uno per riga, sotto i numeri
            tk.Label(s_b, text="\n".join(self._problemi[:6]) + (f"\n+{len(self._problemi) - 6} more" if len(self._problemi) > 6 else ""), bg=C["scheda"], fg=C["rosso_t"],
                     font=F(8), anchor="w", justify="left").pack(fill="x", pady=(0, 6))
        self.tessere(self.sezione_tendina(col, "prezzi", "Prices", v_carta[1], aperta=False, dopo=rilega), [v_carta, v_mtgo], colonne=4)
        cv_d.after(50, rilega)
        # l'elenco delle carte a sinistra, lungo (se non ci sta tutto, scorre con la rotella)
        cv = tk.Canvas(sx_l, bg=C["scheda"], highlightthickness=0, bd=0); cv.pack(fill="both", expand=True)
        dentro_l = tk.Frame(cv, bg=C["scheda"]); win = cv.create_window(0, 0, window=dentro_l, anchor="nw")
        dentro_l.bind("<Configure>", lambda e: cv.configure(scrollregion=(0, 0, 0, dentro_l.winfo_reqheight())))
        cv.bind("<Configure>", lambda e: cv.itemconfigure(win, width=e.width))

        def elenco(padre, titolo, carte):
            """Una sottolista col suo titolo. Le capsule come in Arena, per costo dall'alto in basso. Rarita', copie che hai e prezzo stanno
            sulla scheda della carta in hover, non piu' accanto alla capsula (Autore, 7 nov 2026)."""
            tk.Label(padre, text=f"{titolo} · {sum(carte.values())}", bg=C["scheda"], fg=C["titolo"], font=F(7, True), anchor="w").pack(fill="x", pady=(0, 3))
            voci_ = CAP.ordina(list(carte.items()))
            for n_, q in voci_:
                lista.schede[n_] = self.dati_carta(n_, tutte.get(n_, q), coll)     # le copie di tutte le zone: la sideboard non riscrive quelle del mazzo
            lista.elenco(padre, voci_, bg=C["scheda"]).pack(fill="x", pady=0)      # una tela per sottolista, non una per carta (11 nov 2026)
            tk.Frame(padre, bg=C["scheda"], height=8).pack(fill="x")
        if main:
            voci_m = [(q, n) for n, q in main.items()]
            tinte = {k for _q, n in voci_m for k in CAP.info(n)[1]}
            tot = sum(main.values())
            lista.testata(dentro_l, nome or "Deck", tot, 100 if comandante else 60, CAP.curva(voci_m), CAP.copertina(voci_m), [k for k in "WUBRG" if k in tinte], bg=C["scheda"]).pack(fill="x", pady=(0, 6))
            colonne = tk.Frame(dentro_l, bg=C["scheda"]); colonne.pack(fill="x")
            colonne.columnconfigure(0, weight=1, uniform="lista"); colonne.columnconfigure(1, weight=1, uniform="lista")
            c_magie = tk.Frame(colonne, bg=C["scheda"]); c_magie.grid(row=0, column=0, sticky="new", padx=(0, 8))
            c_resto = tk.Frame(colonne, bg=C["scheda"]); c_resto.grid(row=0, column=1, sticky="new")
            for titolo, zona in (("COMMANDER", comandante), ("COMPANION", compagno)):
                if zona:
                    elenco(c_magie, titolo, zona)
            terre = {n_: q for n_, q in main.items() if DM.e_terra(n_, carte_db) or n_ in BASI}
            elenco(c_magie, "SPELLS", {n_: q for n_, q in main.items() if n_ not in terre})
            if terre:
                elenco(c_resto, "LANDS", terre)
            if side:
                elenco(c_resto, "SIDEBOARD", side)
        else:
            tk.Label(dentro_l, text="This deck has no list", bg=C["scheda"], fg=C["grigio"], font=F(9)).pack(anchor="w")

        def rotella(e):
            if dentro_l.winfo_reqheight() > cv.winfo_height():
                cv.yview_scroll(piattaforma.scatti(e.delta) * 2, "units")

        def lega(w):
            w.bind("<MouseWheel>", rotella)
            for x in w.winfo_children():
                lega(x)
        cv.after(50, lambda: lega(cv))

    def vista_carte(self, tipo, chi, nome, main, side, comandante, compagno):
        """Il Board del mazzo (tavolo_carte.py), da guardare: la disposizione, le connessioni, i dot e le label come li hai fatti in modalita' edit (stessa chiave del
        builder), con zoom e pan, ma niente strumenti (Autore, 10 nov 2026: «sara' personalizzabile solo dopo essere andati in modalita' edit»). Si cambia dal
        builder: Edit, poi Board."""
        import tavolo_carte as TC
        vecchio = getattr(self, "tavolo", None)
        if vecchio is not None and vecchio.fin.winfo_exists():
            vecchio.chiudi()
        salvato = tipo in MS.SEZIONI and isinstance(chi, dict) and chi.get("id")
        chiave = f"{tipo}:{chi['id']}" if salvato else f"mio:{(self.mazzo_arena(chi) or {}).get('id') or chi}" if tipo == "mio" else f"{tipo}:{nome}"
        self.tavolo = TC.TavoloCarte(self.tk, self.F, self.fin, nome, main, side, comandante, compagno, carte_db=getattr(self, "carte_db", None), chiave=chiave,
                                     formato=self.formato_mazzo(tipo, chi), sola_lettura=True)
        return self.tavolo

    def dati_carta(self, nome, q, coll):
        """I dati di una carta del mazzo per la scheda in hover: rarita', copie che hai su quelle che servono, prezzo di carta e su MTGO."""
        voci = []
        if nome not in BASI:
            r, hai = rarita_nome(nome), coll.get(nome, 0)
            voci += [("RARITY", NOMI_RARITA.get(r, "-"), COL_RARITA.get(r)),
                     ("OWNED", f"{min(hai, q)}/{q}", C["verde_t"] if hai >= min(q, 4) else C["rosso_t"])]
        pz = PZ.prezzo(nome)
        if pz and (pz.get("eur") is not None or pz.get("usd") is not None):
            voci.append(("PAPER", " · ".join(x for x in (PZ.euro(pz.get("eur")) if pz.get("eur") is not None else "", f"${pz['usd']:.2f}" if pz.get("usd") is not None else "") if x), None))
        else:
            voci.append(("PAPER", "digital only", C["grigio"]))
        if pz and pz.get("tix"):
            voci.append(("MTGO", f"{pz['tix']:.2f} tix", None))
        return voci

    def filtra_partenza(self, partenza):
        """Il filtro on the play / on the draw della finestra del mazzo: premuto di nuovo si toglie. La finestra si rifa' e la colonna dei dati torna dov'era."""
        self.partenza = None if partenza is None or getattr(self, "partenza", None) == partenza else partenza
        cv = getattr(self, "colonna_dati", None)
        y = cv.yview()[0] if cv is not None and cv.winfo_exists() else 0
        self.disegna_dettaglio()
        cv = getattr(self, "colonna_dati", None)
        if cv is not None and cv.winfo_exists():
            cv.after(120, lambda: cv.winfo_exists() and cv.yview_moveto(y))

    def voci_partite(self, partite, an, nome, an_tutte=None):
        """Le voci delle partite di un mazzo: win rate, games played (partite, con vinte e perse sotto), on the play e on the draw (le prime quattro, in Performance), closes on e
        loses on (in Analysis).
        Senza partite «-». an_tutte: l'analisi di tutte le partite, per le due tessere on the play e on the draw, che restano su tutte anche col filtro acceso.
        Prima e ultima partita e premi degli eventi non ci sono piu' (Autore, 10 nov 2026: «togli le date di primo e ultimo game ed event prizes»)."""
        w = sum(x["vinta"] for x in partite); n = len(partite)
        partenza = lambda z: (f"{round(100 * z[0] / z[1])}%", f"{z[0]}-{z[1] - z[0]}", VINTA if z[0] / z[1] >= 0.5 else PERSA) if z[1] else ("-", "", None)
        turno = lambda z: (f"T{z[0]:.1f}", f"{z[1]} game{'s' if z[1] != 1 else ''}") if z else ("-", "")
        base = an_tutte or an
        pl, dr = partenza(base["play"] if base else (0, 0)), partenza(base["draw"] if base else (0, 0))
        ch, pe = turno(an["chiude"] if an else None), turno(an["perde"] if an else None)
        return [("win rate", f"{round(100 * w / n)}%" if n else "-", (VINTA if w / n >= 0.5 else PERSA) if n else None),
                ("games played", str(n) if n else "-", None, f"{w} won · {n - w} lost" if n else ""),     # al posto di record (10 nov 2026: «games total lo metti nella
                # schedina games played con loss e win al posto di record»)
                ("on the play", pl[0], pl[2], pl[1]), ("on the draw", dr[0], dr[2], dr[1]),
                ("closes on", ch[0], None, ch[1]), ("loses on", pe[0], None, pe[1])]

    def voci_build(self, m, main, side, comandante, compagno, coll, carte_db, meta=None):
        """I dati di una build o di un mazzo in wishlist prima di giocarlo (Autore, 7 nov 2026: «build your deck dove possiamo testare delle build e guadagnare dati in anticipo»):
        formato e legalita', carte che hai, terre e la probabilita' di averne una per turno sul play (conto esatto), il mazzo del meta piu' simile col suo win rate."""
        fmt = m.get("formato") or "Standard"
        self._problemi = MS.legalita(main, side, fmt, comandante, compagno)
        mn = MS.mana({**comandante, **main})
        tot = sum(main.values()) + sum(comandante.values())
        own = sum(min(q, coll.get(n, 0)) if n not in BASI else q for n, q in {**comandante, **main}.items())
        pct = lambda x: f"{round(100 * x)}%"
        voci = [("format", fmt, None),
                ("legal", "✓ yes" if not self._problemi else f"✗ {len(self._problemi)} issue{'s' if len(self._problemi) > 1 else ''}", VINTA if not self._problemi else PERSA),
                ("cards owned", f"{own}/{tot}", VINTA if own == tot else None),
                ("lands", f"{mn['terre']}/{mn['carte']}", None, "2-5 in hand: " + pct(sum(mn["mano"].get(k, 0) for k in range(2, 6))) if mn["carte"] else "")]
        for t in (2, 3, 4):
            voci.append((f"land drop t{t}", pct(mn["curva"][t]) if mn["curva"] else "-", None, "on the play"))
        fonti = " ".join(f"{k}{mn['fonti'].get(k, 0)}" for k in "WUBRG" if mn["simboli"].get(k))
        voci.append(("sources", fonti or "-", None, "lands per color"))
        if meta is not None:        # un mazzo del meta: la sua quota e il suo win rate (o la forza, o i mazzi nei tornei), e quante carte ci sono su Arena
            wr = meta.get("wr")
            sotto = f"WR {wr:.1f}%" if wr is not None else f"strength {meta['forza']}°" if meta.get("forza") else f"{meta['mazzi']:,} decks" if meta.get("mazzi") else ""
            if meta.get("su_arena") is not None:
                sotto += f" · {meta['su_arena']}/{meta['carte']} on Arena"
            voci.append(("meta share", f"{meta.get('quota', 0):.1f}%", None, sotto.strip(" ·")))
            return voci
        vicino, quota = (None, 0)
        if fmt in dict(FORMATI_META):
            vicino, quota = MS.simile(main, meta_mazzi(fmt)[0])
        if vicino is not None and quota >= 0.3:
            stima = f"WR {vicino['wr']:.0f}%" if vicino.get("wr") is not None else f"meta {vicino['quota']:.0f}%"
            voci.append(("closest meta", vicino["nome"], None, f"{round(100 * quota)}% same · {stima}"))
        else:
            voci.append(("closest meta", "none", C["grigio"], "under 30% same cards"))
        return voci

    def riquadro_jolly(self, padre, manca, si, jl, stretto=False):
        """Il costo in jolly del mazzo, come su Untapped: per ogni rarita' l'icona del jolly di Arena, quanti ne servono per
        completare il mazzo (grande) e quanti ne hai (piccolo); accanto il martelletto verde se lo puoi craftare coi jolly che
        hai, «completo» se hai gia' tutte le carte, rosso se i jolly non bastano (Autore, 18 ott 2026)."""
        tk, F = self.tk, self.F
        bg = padre["bg"]
        # una riga sola: il nome a sinistra, le quattro icone allineate, lo stato in fondo a destra
        if not stretto:     # nel builder la colonna e' stretta: bastano le icone dei jolly
            tk.Label(padre, text="WILDCARDS", bg=bg, fg=C["titolo"], font=F(7, True), pady=0).pack(side="left", padx=(0, 10))
        r = tk.Frame(padre, bg=bg); r.pack(side="left", fill="x", expand=True)
        for k in "MRUC":
            img = self.loghi.get(("jolly", k))
            if img is None:
                f = icona_jolly(k, 24)
                if f:
                    img = self.loghi[("jolly", k)] = tk.PhotoImage(file=f)
            c = tk.Frame(r, bg=bg); c.pack(side="left", padx=(0, 5))
            if img:
                tk.Label(c, image=img, bg=bg).pack(side="left")
            else:
                tk.Label(c, text=k, bg=bg, fg=COL_RARITA.get(k), font=F(10, True)).pack(side="left")
            num = tk.Frame(c, bg=bg); num.pack(side="left", padx=(4, 0))
            serve, hai = manca.get(k, 0), (jl or {}).get(k)
            col = C["muto"] if not serve else (C["rosso_t"] if hai is not None and serve > hai else C["titolo"])
            tk.Label(num, text=str(serve), bg=bg, fg=col, font=F(11, True), pady=0).pack(anchor="w")
            tk.Label(num, text=f"own {hai}" if hai is not None else "", bg=bg, fg=C["grigio"], font=F(7), pady=0).pack(anchor="w")
        stato = tk.Frame(r, bg=bg); stato.pack(side="right", padx=(6, 0))
        if not any(manca.values()):
            tk.Label(stato, text="✓ OK", bg=bg, fg=C["verde_t"], font=F(8, True)).pack(side="left")
        elif si:
            img = self.loghi.get("martello")
            if img is None:
                img = self.loghi["martello"] = tk.PhotoImage(file=icona_azione("martello", C["verde"], 22))
            tk.Label(stato, image=img, bg=bg).pack(side="left")
            tk.Label(stato, text="CRAFTABLE", bg=bg, fg=C["verde_t"], font=F(8, True)).pack(side="left", padx=(4, 0))
        elif si is False:
            tk.Label(stato, text="NOT ENOUGH" if stretto else "NOT ENOUGH WILDCARDS", bg=bg, fg=C["rosso_t"], font=F(8, True)).pack(side="left")
