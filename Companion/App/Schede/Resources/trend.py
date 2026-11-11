"""Il grafico Trend di Resources."""
import tkinter.font as tkfont

import disegni as DG

from tema import CI as C, PERSA, SALDO, SFONDO_FASCIA, SFONDO_LINEA, TEND, VINTA
from widget import a_riposo


class Trend:
    """Il grafico Trend: le risorse flaggate, le opzioni sotto, il confronto col Farmer."""

    def disegna_sp_far(self):
        c = self.sp_far
        c.delete("all")
        c.create_image(0, 0, image=DG.spunta(14, self.confronta, C["azzurro"], TEND["campo"], TEND["bordo"], C["fondo"]), anchor="nw")

    def scambia_confronto(self):
        self.confronta = not self.confronta
        self.disegna_sp_far()
        if self.R is not None and self.R.foto:
            self.disegna_grafico()

    def voci_serie(self, ris):
        """Le voci del grafico per una risorsa: [(nome, chiave, colore, entra o esce)]."""
        return {"Oro": [("farmed", "oro_piu", VINTA, "entra"), ("spent", "oro_meno", PERSA, "esce")],
                "Gemme": [("earned", "gem_piu", VINTA, "entra"), ("spent", "gem_meno", PERSA, "esce")],
                "Buste": [("earned", "bu_ott", VINTA, "entra"), ("opened", "bu_ap", PERSA, "esce")],
                "Carte": [("earned", "carte", VINTA, "entra")],
                "Jolly": [("rare", "jolly_r", VINTA, "entra"), ("mythic", "jolly_m", C["testo"], "entra"), ("rare used", "jolly_ru", PERSA, "esce"), ("mythic used", "jolly_mu", PERSA, "esce")]}[ris]

    def saldi_serie(self, ris):
        """Il saldo a fine periodo di una risorsa: [(nome, come si legge dal conto)]. Delle carte il conto non c'e'."""
        return {"Oro": [("balance", lambda x: x["oro"])], "Gemme": [("balance", lambda x: x["gem"])], "Buste": [("balance", lambda x: x["buste"])],
                "Jolly": [("rare balance", lambda x: x["jolly"][2]), ("mythic balance", lambda x: x["jolly"][3])]}.get(ris, [])

    def serie(self, ris, righe, con=None):
        """Le linee di una risorsa secondo le opzioni: [(nome, valori, colore, stile)], stile "" una linea piena, "tratto" tratteggiata coi punti, "media" tratteggiata senza punti. con (Risorse.confronto):
        la vista Farmer, gli stessi periodi coi valori del piano; il saldo li' non c'e', il conto vero non dice cosa sarebbe stato."""
        op, out = self.op, []
        for nome, k, col, verso in self.voci_serie(ris):
            if op[verso]:
                vals = [con[k] * x[2]["giorni"] for x in righe] if con else [x[2][k] for x in righe]
                if op["cumula"]:
                    vals = [sum(vals[:i + 1]) for i in range(len(vals))]
                out.append((nome, vals, col, "tratto" if nome == "mythic used" else ""))
        if op["media"] and not op["cumula"]:         # la media di una somma che sale non dice niente
            out += [(f"{nome} avg", [sum(vals) / len(vals)] * len(vals), col, "media") for nome, vals, col, _ in list(out) if vals]
        if op["saldo"] and not con:
            out += [(nome, [leggi(self.R.saldo(x[2]["fine"])) for x in righe], SALDO, "tratto" if j else "") for j, (nome, leggi) in enumerate(self.saldi_serie(ris))]
        return out

    def riassunto(self, ris, grana, k, righe, c, corto=False):
        """Di quanto cambia col Farmer ogni voce accesa: al mese secondo Period, o in totale con un Range scelto. corto: solo la differenza, quando le risorse sono piu' d'una."""
        pt = lambda x: f"{round(x):,}"
        unita, coda = {"Settimana": (7, "a week"), "Mese": (365.25 / 12, "a month"), "Anno": (365.25, "a year")}[grana]
        out = []
        for nome, ch, _, verso in self.voci_serie(ris):
            if not self.op[verso]:
                continue
            a, b = (c["senza"][ch] * unita, c["con"][ch] * unita) if k is None else (sum(x[2][ch] for x in righe), c["con"][ch] * sum(x[2]["giorni"] for x in righe))
            d, q = round(b) - round(a), f", {100 * (b - a) / a:+,.0f}%" if a else ""
            delta = f"({d:+,}{q})" if d else "(no change)"
            out.append(f"{nome} {delta}" if corto else f"{nome} {coda if k is None else 'in this period'}: {pt(a)} → {pt(b)}  {delta}")
        return out

    def disegna_opzioni(self):
        """Le opzioni sotto il grafico: si flaggano, il grafico si rifa' e loro restano."""
        tk, F = self.tk, self.F
        r = tk.Frame(self.b_gra, bg=C["scheda"]); r.pack(side="bottom", fill="x", pady=(6, 0))
        voci = (("entra", "Earned"), ("esce", "Spent"), ("saldo", "Balance"), ("cumula", "Cumulative"), ("media", "Average"))
        n = 3 if self.stretta else 5
        for i, (k, nome) in enumerate(voci):
            spento = (k == "saldo" and self.confronta) or (k == "media" and self.op["cumula"])       # in quella vista non si possono mostrare
            f = tk.Frame(r, bg=C["scheda"], cursor="hand2"); f.grid(row=i // n, column=i % n, sticky="w", padx=(0, 12), pady=(0, 2))
            on = self.op[k] and not spento
            c = tk.Canvas(f, width=13, height=13, bg=C["scheda"], highlightthickness=0, cursor="hand2"); c.pack(side="left", padx=(0, 4))
            c.create_image(0, 0, image=DG.spunta(13, on, C["azzurro"], TEND["campo"], TEND["bordo"], C["fondo"]), anchor="nw")
            l = tk.Label(f, text=nome, bg=C["scheda"], fg=C["muto"] if spento else C["testo"], font=F(8), pady=0, cursor="hand2"); l.pack(side="left")
            for w in (f, c, l):
                w.bind("<Button-1>", lambda e, k=k: self.scambia_op(k))

    def scambia_op(self, k):
        self.op[k] = not self.op[k]
        self.disegna_grafico()

    def disegna_grafico(self):
        """I grafici: uno per ogni risorsa flaggata, ognuno con la sua scala (oro e buste su una scala sola non si leggerebbero), le opzioni sotto. Col Farmer i valori sono quelli del piano."""
        self.svuota(self.b_gra)
        self.disegna_opzioni()
        grana, k, risorse = self.gr.get(), self.mappa.get(self.qual.get()), self.ser.get()
        righe = self.R.righe(grana, k)
        c = self.dati_farmer() if self.confronta else None
        tk, F = self.tk, self.F
        if self.confronta and c is None:
            tk.Label(self.b_gra, text="Set a plan in the Farmer to see this view", bg=C["scheda"], fg=C["grigio"], font=F(8), anchor="w").pack(fill="x", pady=(0, 4))
        if c:
            finisce = [f"the {n} runs out in about {c['finisce'][x]} days" for x, n in (("oro", "gold"), ("gem", "gems")) if c["finisce"][x] is not None and c["finisce"][x] <= 180]
            if finisce:
                tk.Label(self.b_gra, text="At this pace " + " and ".join(finisce), bg=C["scheda"], fg=C["rosso_t"], font=F(7, True), anchor="w").pack(fill="x", pady=(0, 4))
        molte = len(risorse) > 1
        for ris in risorse:
            f = tk.Frame(self.b_gra, bg=C["scheda"]); f.pack(fill="both", expand=True, pady=(0, 4 if molte else 0))
            testa = self.riassunto(ris, grana, k, righe, c, corto=molte) if c else []
            if molte:
                testa = [self.NOMI_RISORSE[ris].upper() + ("  " + " · ".join(testa) if testa else "")]
            self.grafico_periodi(f, righe, self.serie(ris, righe, c["con"] if c else None), lambda x: f"{round(x):,}", altezza=64 if molte else 120, testa=testa, compatto=molte)

    def grafico_periodi(self, padre, righe, serie, pt, altezza=120, testa=(), compatto=False):
        """Il grafico cartesiano di una risorsa: in orizzontale i periodi, in verticale le quantita' da zero, una linea per serie con un punto per periodo. Una scala sola; legenda con due linee o piu',
        il puntatore legge tutti i valori del periodo. serie: [(nome, valori, colore, stile)] di PaginaRisorse.serie. testa: le righe di testo in cima, che il puntatore sostituisce.
        compatto: con piu' risorse la legenda sta sulla riga del titolo, per lasciare l'altezza ai grafici; il puntatore la toglie finche' legge."""
        tk, F = self.tk, self.F
        import math
        riposo = "\n".join(testa)
        v_info = tk.StringVar(value=riposo)
        r_info = tk.Frame(padre, bg=C["scheda"]); r_info.pack(fill="x", pady=(0, 2))
        info = tk.Label(r_info, textvariable=v_info, bg=C["scheda"], fg=C["testo"], font=F(8), anchor="w", justify="left", height=max(1, len(testa)))
        info.pack(side="left")
        piene = [x for x in serie if x[3] != "media"]
        r_leg = None
        if len(serie) > 1:
            # la legenda: sulla riga del titolo se ci sta, se no sotto, su piu' righe; delle voci si misura la larghezza, se no la prima si taglia
            voci = [(nome, col, stile) for nome, _, col, stile in piene] + ([("average", C["testo"], "media")] if len(piene) < len(serie) else [])
            f_l = tkfont.Font(font=F(8))
            largo = lambda v: 18 + 4 + f_l.measure(v[0]) + 10
            spazio = max(self.b_gra.winfo_width() - 4, 280)
            nella_testa = compatto and sum(map(largo, voci)) + f_l.measure(riposo) + 16 <= spazio
            file_l, q, u = [], [], 0
            for v in voci:
                if q and u + largo(v) > spazio:
                    file_l.append(q); q, u = [], 0
                q.append(v); u += largo(v)
            file_l.append(q)
            for q in file_l:
                r = tk.Frame(r_info if nella_testa else padre, bg=C["scheda"])
                r.pack(side="right") if nella_testa else r.pack(fill="x", pady=(0, 2))
                if nella_testa:
                    r_leg = r
                for nome, col, stile in reversed(q):
                    tk.Label(r, text=nome, bg=C["scheda"], fg=C["testo"], font=F(8)).pack(side="right", padx=(4, 0 if nome == q[-1][0] else 10))
                    cam = tk.Canvas(r, width=18, height=10, bg=C["scheda"], highlightthickness=0); cam.pack(side="right")
                    cam.create_line(0, 5, 18, 5, fill=col, width=2, dash=(3, 3) if stile == "media" else (4, 2) if stile else ())
                    if stile != "media":
                        cam.create_image(9, 5, image=DG.punto(9, col, C["scheda"], 1))
        cv = tk.Canvas(padre, height=altezza, bg=C["scheda"], highlightthickness=0); cv.pack(fill="both", expand=True)
        massimo = max([max(x[1]) for x in serie if x[1]] + [0])
        if not massimo:
            cv.configure(height=40); cv.create_text(4, 20, text="Nothing to show in this period" if serie else "Flag something below", anchor="w", fill=C["grigio"], font=F(9))
            return
        ordine = 10 ** math.floor(math.log10(massimo))
        passo = next(p * ordine for p in (0.1, 0.2, 0.25, 0.5, 1, 2, 2.5, 5, 10) if massimo / (p * ordine) <= 6)
        passo = max(passo, 1)         # niente tacche a mezza busta
        alto = math.ceil(massimo / passo) * passo
        n = len(righe)
        geo = {}

        def disegna(e=None):
            cv.delete("all")
            W, H = cv.winfo_width(), cv.winfo_height(); sx, dx_, su, giu = 50, 16, 10, 24
            larg, alt = W - sx - dx_, H - su - giu
            X = lambda i: sx + (larg * i / (n - 1) if n > 1 else larg / 2)
            Y = lambda v: su + alt * (alto - v) / alto
            geo.update(X=X, Y=Y, sx=sx, larg=larg, H=H)
            gradini = [passo * i for i in range(int(round(alto / passo)) + 1)]
            for j, v in enumerate(gradini[:-1]):
                if j % 2 == 0:
                    cv.create_rectangle(sx, Y(v + passo), W - dx_, Y(v), fill=SFONDO_FASCIA, width=0)
            salta = 2 if alt / max(1, len(gradini) - 1) < 18 else 1        # in un grafico basso le tacche si accavallano: una si' e una no
            for j, v in enumerate(gradini):
                cv.create_line(sx, Y(v), W - dx_, Y(v), fill=C["muto"] if v == 0 else SFONDO_LINEA)
                if j % salta == 0:
                    cv.create_text(sx - 6, Y(v), text=pt(v), anchor="e", fill=C["muto"], font=F(7))
            ultima = -999
            f_ = tkfont.Font(font=F(7))
            for i, r in enumerate(righe):
                x = X(i)
                cv.create_line(x, H - giu, x, H - giu + 4, fill=C["muto"])
                w = f_.measure(r[1])
                # le etichette non si accavallano; alle due estremita' stanno dentro il grafico
                x0 = min(max(x - w / 2, 2), W - w - 2)
                if x0 > ultima + 8:
                    cv.create_text(x0, H - giu + 6, text=r[1], anchor="nw", fill=C["muto"], font=F(7)); ultima = x0 + w
            linee, punti_ = [], []           # le linee e i punti in uno strato nitido sopra la griglia (disegni.py)
            for _, vals, col, stile in serie:
                if len(vals) > 1:
                    linee.append(([(X(i), Y(v)) for i, v in enumerate(vals)], col, 1 if stile == "media" else 2, (3, 3) if stile == "media" else (6, 3) if stile else None))
                if stile != "media":
                    punti_ += [(X(i), Y(v), 5, col, C["scheda"], 2) for i, v in enumerate(vals)]
            cv.strato_ = DG.tratti(W, H, linee, punti_)
            cv.create_image(0, 0, image=cv.strato_, anchor="nw")

        def sopra(e):
            if not geo:
                return
            i = max(0, min(n - 1, round((e.x - geo["sx"]) / geo["larg"] * (n - 1)))) if n > 1 else 0
            cv.delete("cursore")
            x = geo["X"](i)
            cv.create_line(x, 10, x, geo["H"] - 24, fill=C["grigio"], tags="cursore")
            for _, vals, col, stile in serie:
                if stile != "media":
                    cv.create_image(x, geo["Y"](vals[i]), image=DG.punto(11, C["titolo"], col, 2), tags="cursore")
            v_info.set(f"{righe[i][0]} · " + " · ".join(f"{nome} {pt(vals[i])}" for nome, vals, _, stile in serie if stile != "media"))
            if compatto and r_leg is not None:
                r_leg.pack_forget()
        cv.bind("<Configure>", a_riposo(cv, disegna)); cv.bind("<Motion>", sopra)      # trascinando il bordo: una volta, a misura ferma
        cv.bind("<Leave>", lambda e: (cv.delete("cursore"), v_info.set(riposo), r_leg.pack(side="right") if compatto and r_leg is not None else None))
