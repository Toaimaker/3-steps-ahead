"""Il ROI del piano del Farmer."""
import risorse as RS

from tema import CI as C, PERSA, VINTA
from widget import pulsante_solido


class Roi:
    """Il conto del piano del Farmer: costi, value for, cambio dell'oro, ROI e note."""

    def disegna_calcolo(self, grafico=True):
        """Il farmer: a sinistra Goal e voci, con un obiettivo perche' quella rotta; a destra solo quanto costa sostenerlo (Autore, 4 nov 2026: «nella parte destra
        mettiamo solo cosa costa sostenere il goal»), in oro, gemme e token veri. Sotto il ROI, e nella colonna dei dati le risorse attese al mese."""
        tk, F, R = self.tk, self.F, self.R
        self.svuota(self.b_esi); self.svuota(self.b_roi); self.svuota(self.b_nota)
        if R is None or not R.foto:
            return
        pt = lambda x: f"{round(x):,}"
        volte_sett = lambda n: max(1, round(n / settimane)) if n else 0        # una cosa fatta nel mese vale almeno 1 a settimana: niente 0,5 volte
        win = self.win_l()      # i premi dei draft seguono il win rate limited, spostato verso la media se le partite sono poche
        self.disegna_spunte_cambio(R.cambio_oro(win, self.win_cc())["gpo"])
        cambio = self.applica_cambio()      # l'oro vale le gemme vere che ti torna (8 nov 2026), o il prezzo di una busta con la spunta Pack price
        pi = self.applica_goal(win)
        con_pass = pi["pass"] if pi else True
        oro_m = R.base(con_pass)["oro"]
        win_c = self.win_cc()
        calcola = lambda w_, wc_: R.simula(self.n_quick.get(), self.n_premier.get(), self.n_buste.get(), self.n_mitiche.get(), {k: x.get() for k, x in self.paga.items()}, w_, oro_m,
                                           buste_gemme=pi["buste_gemme"] if pi else 0, costruiti=self.n_costruiti.get(), win_c=wc_, gemme_mese=R.base(con_pass)["gemme"], gemme_voci=pi["gemme_voci"] if pi else None, con_pass=con_pass)
        e = calcola(win, win_c)
        self.calcolo = (e, win, win_c)
        gem, oro = self.icona("gemma", 16), self.icona("oro", 16)
        buono = e["saldo"] > 0
        oro_f, gem_f = e["oro_fine"], e["gem_fine"]
        in_gemme = lambda x: f"= {pt(x * R.gpo)} gems"
        self.griglia(self.b_esi, [("gold cost", pt(e["oro_speso"]), None, in_gemme(e["oro_speso"]), oro), ("gems cost", pt(e["gemme_spese"]), None, "", gem),
                                  ("draft tokens", pt(e["token_usati"]), None, "")], colonne=3, grande=12, stretta=True)
        nomi = {"quick": "Quick Draft", "premier": "Premier Draft", "costruiti": "Constructed", "buste": "Packs", "mitiche": "Mythic packs", "buste_gemme": "Gem packs",
                "quick_gemme": "Quick (gems)", "premier_gemme": "Premier (gems)", "costruiti_gemme": "Constructed (gems)"}
        cif = lambda x: self.cella(pt(x) if x else "-", C["testo"] if x else C["muto"], grande=8)
        settimane = 365.25 / 12 / 7
        righe = [r for r in e["righe"] if r["volte"]]
        if righe:
            self.tabella(self.b_esi, [("item", "w"), ("a week", "e"), ("a month", "e"), ("gold", "e"), ("gems", "e"), ("tokens", "e")],
                         [[self.cella(nomi[r["nome"]], C["titolo"], grande=8, lato="left"), cif(volte_sett(r["volte"])), cif(r["volte"]), cif(r["oro"]), cif(r["gemme"]), cif(r["token"])] for r in righe], padx=3)
        # chi conviene al tuo win rate, col cambio: la stessa spesa in oro o in gemme, eventi contro buste
        righe_c = R.convenienza(win, win_c)
        r_cv = tk.Frame(self.b_esi, bg=C["scheda"]); r_cv.pack(fill="x", pady=(8, 0))
        migliore_o, migliore_g = max(x["oro"] for x in righe_c), max(x["gemme"] for x in righe_c)
        self.tabella(r_cv, [("value for", "w"), ("1,000 gold", "e"), ("100 gems", "e"), ("swing", "e")],
                     [[self.cella(x["nome"], C["titolo"], grande=8, lato="left"), self.cella(pt(x["oro"]), VINTA if x["oro"] == migliore_o else None, x["oro"] == migliore_o, grande=8),
                       self.cella(pt(x["gemme"]), VINTA if x["gemme"] == migliore_g else None, x["gemme"] == migliore_g, grande=8), self.cella(f"±{pt(x['sd'])}" if x["sd"] else "-", C["grigio"], grande=8)] for x in righe_c], padx=3)
        # l'oro in gemme: vale quel che costa? rende come la voce migliore?
        cb = R.cambio(e, win, win_c)
        if cb["oro"]:
            sp = round(cb["spreco"])
            nome_v = lambda k: RS.NOMI_VOCE[k].lower()
            r_c = tk.Frame(self.b_esi, bg=C["scheda"]); r_c.pack(fill="x", pady=(8, 0))
            self.griglia(r_c, [("gold is worth", pt(cb["in_gemme"]), None, "", gem), ("you get in value", pt(cb["valore"]), None, "", gem),
                               ("gems wasted", pt(sp), PERSA if sp else VINTA, "", gem)], colonne=3, grande=12, stretta=True)
            testo = (f"Same gold on {nome_v(cb['meglio'])} would be worth {pt(cb['valore_meglio'])} gems" if sp else f"Best use of this gold at your win rate: {nome_v(cb['meglio'])}")
            tk.Label(self.b_esi, text=testo, bg=C["scheda"], fg=C["azzurro"], font=F(7, True), anchor="w", justify="left", wraplength=self.largo_f).pack(fill="x", pady=(3, 0))
            tk.Label(self.b_esi, text=f"Real gems back: {pt(cb['gemme'])} · {nome_v(cb['meglio_gemme'])} would return {pt(cb['gemme_meglio'])}", bg=C["scheda"], fg=C["azzurro"], font=F(7, True),
                     anchor="w", justify="left", wraplength=self.largo_f).pack(fill="x", pady=(3, 0))
        # il ROI: quanto spendi e quanto ottieni, tutto in gemme, e com'e' finita (Autore, 6 nov 2026: «in gemme + oro convertito in gemme quanto spendo vs quanto guadagno per capire se ho un valore roi
        # positivo o negativo alla fine»); sotto gli asset che ottieni. Il conto e' in Risorse.simula
        ri = e["ritorno"]
        saldo = ("roi positive in gems" if buono else "roi negative in gems", f"{'+' if buono else ''}{pt(e['saldo'])}", VINTA if buono else PERSA, "", self.icona_doppia())
        righe_b = [("spent in gems", pt(e["spende"]), None, "", gem), ("gained in gems", pt(e["ottiene"]), None, "", gem)]
        r_sp = tk.Frame(self.b_roi, bg=C["scheda"]); r_sp.pack(fill="x")
        if self.stretta:           # a finestra stretta il saldo ha la sua riga: i due loghi e il numero in un terzo di colonna si tagliano
            self.griglia(r_sp, righe_b, colonne=2, grande=12, stretta=True)
            r_sa = tk.Frame(self.b_roi, bg=C["scheda"]); r_sa.pack(fill="x")
            self.griglia(r_sa, [saldo], colonne=1, grande=12, stretta=True)
        else:
            self.griglia(r_sp, righe_b + [saldo], colonne=3, grande=12, stretta=True)
        # spesa, varianza e win rate: fra quanto oscilla il ROI e cosa diventa se il tuo win rate vero e' quello basso
        sd = R.rischio(e, win, win_c)
        if e["spende"]:
            basso = lambda p_, n_: max(0.05, p_ - 1.96 * (p_ * (1 - p_) / n_) ** 0.5) if n_ else p_
            w_b, wc_b = basso(win, self.n_wr["limited"]), basso(win_c, self.n_wr["constructed"])
            giu = calcola(w_b, wc_b)["saldo"]
            segno = lambda x: f"{'+' if x >= 0 else ''}{pt(x)}"
            tk.Label(self.b_roi, text=f"Variance: {segno(e['saldo'] - sd)} to {segno(e['saldo'] + sd)} in 2 runs out of 3 · gains {e['ottiene'] / e['spende']:.2f} gems per gem spent", bg=C["scheda"], fg=C["azzurro"], font=F(7, True),
                     anchor="w", justify="left", wraplength=self.largo_f).pack(fill="x", pady=(3, 0))
            tk.Label(self.b_roi, text=f"At your low win rate ({100 * w_b:.0f}% limited, {100 * wc_b:.0f}% constructed): ROI {segno(giu)}", bg=C["scheda"], fg=C["rosso_t"] if giu < 0 else C["azzurro"], font=F(7, True),
                     anchor="w", justify="left", wraplength=self.largo_f).pack(fill="x", pady=(1, 4))
        r_ot = tk.Frame(self.b_roi, bg=C["scheda"]); r_ot.pack(fill="x")
        self.griglia(r_ot, [("gems", pt(ri["gemme"]), None, "", gem), ("packs", pt(ri["buste"]), None, "", self.icona("busta", 16)), ("rare wc", pt(ri["jolly_r"]), None, "", self.icona_j("R")),
                            ("mythic wc", pt(ri["jolly_m"]), None, "", self.icona_j("M")), ("cards", pt(ri["carte"]), None, "", self.icona("carte", 16))], colonne=3 if self.stretta else 5, grande=12, stretta=True)
        # il dettaglio: la roadmap contro la cassa vera, in una finestra col grafico (9 nov 2026)
        r_bt = tk.Frame(self.b_roi, bg=C["scheda"]); r_bt.pack(fill="x", pady=(2, 0))
        self.b_andamento = pulsante_solido(tk, F, r_bt, "Roadmap check", False, self.finestra_andamento, alto=28, bg=C["scheda"])
        self.b_andamento.configure(width=170); self.b_andamento.pack(side="right")
        tk.Label(r_bt, text="Are you above or below the roadmap?" if self.piano else "Create a plan to check it against your real balance", bg=C["scheda"], fg=C["grigio"], font=F(7), anchor="w", justify="left",
                 wraplength=max(110, self.largo_f - 185)).pack(side="left", fill="x", expand=True)      # a capo, mai tagliata dal pulsante
        nota = []
        if pi:
            obiettivo, set_ = self.goal.get(), self.g_set.get()
            tk.Label(self.b_nota, text="Mastery Pass: " + ("buy it, this plan pays for it" if con_pass else "skip it, this goal does better without"), bg=C["scheda"], fg=C["azzurro"], font=F(7, True), anchor="w",
                     justify="left", wraplength=self.largo_f).pack(fill="x", pady=(3, 0))
            if len(obiettivo) > 1:        # il mix: quanto di ogni obiettivo si porta a casa rispetto a farlo da solo
                q = pi["esito"]["quote"]
                tk.Label(self.b_nota, text="Mix: " + " · ".join(f"{self.GOAL_CORTI[g]} {round(100 * q[g])}%" for g in obiettivo) + " of what each goal gets alone", bg=C["scheda"], fg=C["azzurro"], font=F(7, True),
                         anchor="w", justify="left", wraplength=self.largo_f).pack(fill="x", pady=(3, 0))
            for t in self.righe_soglie(win, win_c) if len(obiettivo) == 1 else ():      # nel mix la voce in testa cambia quasi a ogni punto di win rate: rumore
                tk.Label(self.b_nota, text=t, bg=C["scheda"], fg=C["azzurro"], font=F(7, True), anchor="w", justify="left", wraplength=self.largo_f).pack(fill="x", pady=(3, 0))
            if "carte" in obiettivo:
                m = RS.set_mancanti(set_)
                if m:
                    nota.append(f"{set_}: {100 * m['fatte'] / m['tutte']:.0f}% of the set at 4 copies · {m['rare_mancanti']} rares and mythics missing")
        if pi and "mazzo" in self.goal.get():
            m, need = self.bisogno()
            if m is None:
                t_m = "Add a deck to the Wishlist or to Deck building to target it"
            elif not (need["R"] or need["M"]):
                t_m = f"{m['nome']}: you can craft it now with the wildcards you have" if not (m["oltre"]["U"] or m["oltre"]["C"]) else f"{m['nome']}: your rare and mythic wildcards already cover it"
            else:
                jl_ = m["jolly"] or {}
                t_m = f"{m['nome']}: {need['R']} rare and {need['M']} mythic wildcards to go (it needs {m['manca']['R']} and {m['manca']['M']}, you have {jl_.get('R', 0)} and {jl_.get('M', 0)})"
                sett = pi["esito"].get("settimane_mazzo")
                t_m += " · at this pace " + ("never: this plan gets no wildcards" if sett is None or sett == float("inf") else f"about {max(1, round(sett))} weeks")
            if m is not None and (m["oltre"]["U"] or m["oltre"]["C"]):
                t_m += f" · still {m['oltre']['U']} uncommon and {m['oltre']['C']} common wildcards to go, not planned"
            tk.Label(self.b_nota, text=t_m, bg=C["scheda"], fg=C["azzurro"], font=F(7, True), anchor="w", justify="left", wraplength=self.largo_f).pack(fill="x", pady=(3, 0))
        # le gemme sono la moneta vera (Autore, 8 nov 2026): il cambio dell'oro al tuo win rate, il win rate usato e il pareggio in gemme di ogni evento
        vie = {"quick": "Quick Draft", "premier": "Premier Draft", "costruiti": "Constructed event"}
        t_c = (f"Gold to gems at your win rate: 1,000 gold = {round(1000 * cambio['gpo'])} gems, through {vie[cambio['via']]}" if cambio["via"] != "busta"
               else "Gold at pack price: 1,000 gold = 200 gems of cards and packs, not gems you can spend")
        tk.Label(self.b_nota, text=t_c, bg=C["scheda"], fg=C["azzurro"], font=F(7, True),
                 anchor="w", justify="left", wraplength=self.largo_f).pack(fill="x", pady=(3, 0))
        def usato(k, w):
            mio, n_ = self.wr[k], self.n_wr[k]
            return f"{round(100 * w)}%" + (f" ({round(100 * mio)}% on {n_:,} games)" if mio is not None and n_ else " (no games: the average)")
        nota.append(f"Win rate used: limited {usato('limited', win)}, constructed {usato('constructed', win_c)}")
        ch_ = (round(win, 3), round(win_c, 3))
        if ch_ not in self._pareggi:
            self._pareggi[ch_] = R.pareggi(win, win_c)
        pg_ = self._pareggi[ch_]
        nota.append("A gem entry pays itself back in gems from: " + " · ".join(f"{vie[k].replace(' event', '')} {round(100 * w)}%" if w else f"{vie[k]} never" for k, w in pg_.items()))
        d = R.taglio()
        if d["giorni"] < 14 or not d["bu_ap"] or not d["c_draft"]:
            nota.append("Few data so far: these estimates will change")
        for t in nota:
            tk.Label(self.b_nota, text=t, bg=C["scheda"], fg=C["muto"], font=F(7), anchor="w", justify="left", wraplength=self.largo_f).pack(fill="x", pady=(3, 0))
        avvisi = []
        if oro_f < 0 or gem_f < 0:
            avvisi.append("Not enough gold or gems for this plan")
        if e["token_mancati"] and not pi:       # col goal i token li conta gia' il piano: quel che manca e' in oro nella tabella
            avvisi.append(f"Only {e['token_usati']} draft tokens: the other {e['token_mancati']} paid with gold")
        if avvisi:
            tk.Label(self.b_esi, text=" · ".join(avvisi), bg=C["scheda"], fg=C["rosso_t"], font=F(7, True), anchor="w", justify="left", wraplength=self.largo_f).pack(fill="x", pady=(3, 0))
        if grafico and self.confronta:      # il grafico segue il piano mentre lo scrivi
            self.disegna_grafico()
