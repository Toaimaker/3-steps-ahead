"""La scheda Drafter durante una partita: i dati della partita, la forza dei mazzi, lui e cosa si vede. Mixin di Finestra (App/finestra.py)."""
import tkinter as tk

import chiudi_draft as CD

from dati_drafter import _COLORI, _TIPI, forza, voti_carte
from tema import C, CI


class DrafterPartita:
    """La scheda Drafter durante una partita: i dati della partita, la forza dei mazzi, lui e cosa si vede."""

    def disegna_dati(self):
        """Dai draft di Untapped: i colori e il record del draft in corso (il resto sta nella finestra del set)."""
        D = self.stato["draft"]
        if D:
            ultimo = D[-1]
            self.stato["draft_colori"] = ultimo["colori"] if ultimo["w"] < 7 and ultimo["l"] < 3 else self.stato["draft_colori"]
            if self.rec["w"] is None and ultimo["w"] < 7 and ultimo["l"] < 3:
                self.rec.update(w=ultimo["w"], l=ultimo["l"], seq=list(ultimo["seq"]))
            self.disegna_record()
            self.v_ev.set(f"{ultimo['tipo'].replace('Draft', ' Draft')} {ultimo['set']}")
            fine = CD.ultima_chiusura()      # un draft chiuso col pulsante Closed session non si riapre da Untapped; uno nuovo ha la prima partita dopo
            aperto = ultimo["w"] < 7 and ultimo["l"] < 3 and not (fine and ultimo["quando"] <= fine)
            if aperto != self.stato["untapped_in_corso"]:
                self.stato["untapped_in_corso"] = aperto; self.disegna_mazzi()


    def disegna_partita(self):
        """La scheda della partita: contro chi, vite, turno, carte in mano e nel grimorio, la forza dei due mazzi. Non si mostra piu' (Autore, 5 nov 2026: «togli la sezione game che tanto non serve»)."""
        return
        for w in self.b7.winfo_children():
            w.destroy()
        pz = self.pescate
        set_ = self.P.evento.split("_")[1] if "_" in self.P.evento else self.stato["set"]
        voti = voti_carte(set_)
        mio = {}
        for _, q, n in self.mazzo_inviato(self.inviato["d"]):
            mio[n] = mio.get(n, 0) + q
        mia, nm = forza(mio, voti)
        sua, ns = forza(self.P.sue_carte, voti)
        avv = pz.avv or self.P.avversario
        if not pz.in_partita:       # nessun dato senza una partita in corso (Autore, 17 ott 2026)
            self.v_part_dx.set("")
            tk.Label(self.b7, text="No game in progress", bg=CI["scheda"], fg=CI["grigio"], font=self.F(9), anchor="w").pack(fill="x")
            return
        self.v_part_dx.set((f"contro {avv}" if avv else "") + (f" · turno {pz.turno}" if pz.turno else ""))
        # una tabella come nei tracker che esistono (Untapped, il client di Arena): colonne TU e AVVERSARIO, righe coi nomi del
        # client in italiano (Autore, 17 ott 2026: «chi e' LUI? dai, prendi da software gia' esistenti, non improvvisare»)
        vite = pz.vite or self.P.vite
        mazzo = self.mazzo_inviato(self.inviato["d"])
        lib = self.pescate.elenco(mazzo)[1] if mazzo else pz.lib
        mano = sum(pz.sez.get("mano", {}).values()) if pz.sez.get("mano") is not None else None
        num = lambda x, d=0: "-" if x is None else (f"{x:.1f}" if d else str(x))
        righe = []
        if pz.in_partita or avv:
            righe += [("Life", num(vite and vite[0]), num(vite and vite[1])),
                      ("Cards in library", num(lib), num(pz.lib_sua)),
                      ("Cards in hand", num(mano), num(pz.mano_sua))]
        righe.append(("Deck strength", num(mia, 1), num(sua, 1)))
        g = tk.Frame(self.b7, bg=CI["scheda"]); g.pack(fill="x")
        g.columnconfigure(0, weight=1)
        for j_, t in enumerate(("", "YOU", "OPPONENT")):
            tk.Label(g, text=t, bg=CI["scheda"], fg=CI["titolo"], font=self.F(7, True), pady=3, padx=8,
                     anchor="w" if j_ == 0 else "e").grid(row=0, column=j_, sticky="nsew")
        for i_, (nome, tu, lui) in enumerate(righe, 1):
            bgr = CI["cap"] if i_ % 2 else CI["scheda"]
            tk.Label(g, text=nome, bg=bgr, fg=CI["testo"], font=self.F(9), pady=4, padx=8, anchor="w").grid(row=i_, column=0, sticky="nsew")
            tk.Label(g, text=tu, bg=bgr, fg=CI["titolo"], font=self.F(11, True), pady=4, padx=8, width=6, anchor="e").grid(row=i_, column=1, sticky="nsew")
            tk.Label(g, text=lui, bg=bgr, fg=CI["titolo"], font=self.F(11, True), pady=4, padx=8, width=10, anchor="e").grid(row=i_, column=2, sticky="nsew")
        # la forza: voto medio delle carte (17Lands) del tuo mazzo inviato contro le carte dell'avversario viste finora
        nota = f"Deck strength: average card rating; opponent on {ns} cards seen" if sua else "Deck strength: average card rating"
        if mia and sua:
            d_ = round(mia - sua, 1) + 0.0
            tk.Label(self.b7, text=("Your deck is stronger by " if d_ >= 0 else "The opposing deck is stronger by ") + f"{abs(d_):.1f} points",
                     bg=CI["scheda"], fg=CI["verde_t"] if d_ >= 0 else CI["rosso_t"], font=self.F(9, True), anchor="w").pack(fill="x", pady=(6, 0))
        tk.Label(self.b7, text=nota + (" (few: the comparison will change)" if sua and ns < 5 else ""), bg=CI["scheda"], fg=CI["muto"],
                 font=self.F(7), anchor="w", justify="left", wraplength=380).pack(fill="x")


    def disegna_forza(self):
        set_ = self.P.evento.split("_")[1] if "_" in self.P.evento else self.stato["set"]
        voti = voti_carte(set_)
        # il mazzo inviato al cancello, come la scheda «Partita» a destra (17 ott 2026: prima l'ultimo draft di Untapped, che
        # durante un draft nuovo e' il mazzo di prima, e i due numeri sullo schermo non coincidevano); Untapped se manca
        mio = {}
        for _, q, n in self.mazzo_inviato(self.inviato["d"]):
            mio[n] = mio.get(n, 0) + q
        if not mio and self.stato["draft"]:
            mio = self.stato["draft"][-1].get("mazzo") or {}
        mia, nm = forza(mio, voti)
        suoi = "".join(k for k in "WUBRG" if any(k in _COLORI.get(set_, {}).get(n, "") for n in self.P.sue_carte))
        miei = self.stato["draft_colori"] or ""
        for fr, cc in ((self.col_mio, miei), (self.col_suo, suoi)):
            if getattr(fr, "_cc", None) != cc:
                for w in fr.winfo_children():
                    w.destroy()
                self.mana_label(fr, cc, C["cap"]).pack()
                fr._cc = cc
        sua, ns = forza(self.P.sue_carte, voti)
        self.tp["n_mio"].configure(text=f"{nm} cards" if mia else "")
        self.tp["n_suo"].configure(text=f"{ns} seen" if sua else "")
        self.tp["nota"].configure(text="few seen" if sua and ns < 5 else "")
        if mia and sua:
            d = mia - sua
            self.tp["mio"].configure(text=f"{mia:.1f}"); self.tp["vs"].configure(text="vs"); self.tp["suo"].configure(text=f"{sua:.1f}")
            d = round(d, 1) + 0.0          # niente «-0.0» quando i mazzi sono pari
            self.tp["d"].configure(text=f"{'+' if d >= 0 else '-'}{abs(d):.1f}", fg=C["verde_t"] if d >= 0 else C["rosso_t"])
        else:
            self.tp["mio"].configure(text=f"{mia:.1f}" if mia else ""); self.tp["vs"].configure(text=""); self.tp["suo"].configure(text=""); self.tp["d"].configure(text="")


    def disegna_lui(self):
        """Il riquadro di lui sta sotto il mazzo inviato solo durante la partita."""
        ora = bool(self.P.avversario) and not self.P.esito
        if ora != self.in_partita["v"]:
            self.in_partita["v"] = ora
            if ora and self.scelta["avviato"]:
                self.mostra("corso")
        if not ora: return
        for w in self.righe_lui.winfo_children(): w.destroy()
        u = self.P.suo; self.v_lui.set(self.P.avversario)
        def riga(etichetta, testo, col=None):
            r = tk.Frame(self.righe_lui, bg=CI["scheda"]); r.pack(fill="x", pady=1)
            tk.Label(r, text=etichetta, width=13, anchor="w", bg=CI["scheda"], fg=CI["grigio"], font=self.F(8)).pack(side="left")
            tk.Label(r, text=testo, anchor="w", justify="left", wraplength=290, bg=CI["scheda"], fg=col or CI["testo"], font=self.F(9)).pack(side="left", fill="x")
        vista = u.get("in_mano") or []
        riga("Mano", (f"{u['mano']} carte" + (f", {len(vista)} viste" if vista else ", nascoste")) if u["mano"] is not None else "-")
        if vista: riga("Viste in mano", ", ".join(vista), CI["arancio"])
        riga("Terre", f"{u['terre']}, libere {u['libere']}" if u["terre"] is not None else "-", CI["arancio"] if (u["libere"] or 0) >= 1 else None)
        if u["pronte"]: riga("Magie pronte", ", ".join(sorted(set(u["pronte"]), key=u["pronte"].index)))
        for n, pt, tap in u["creature"][:6]:
            kw = u["kw"].get(n, "")
            riga("In campo" if (n, pt, tap) == u["creature"][0] else "", f"{n} {pt}" + (f" · {kw.strip()}" if kw.strip() else "") + (" · tappata" if tap else ""),
                 CI["rosso_t"] if "flying" in kw else None)
        trucchi = [n for n in u["viste"] if "Instant" in _TIPI.get(n, "") or "flash" in _TIPI.get(n, "")]
        if trucchi: riga("Trucchi visti", ", ".join(trucchi), CI["rosso_t"])
        riga("Cimitero", f"{u['cimitero']} carte")
