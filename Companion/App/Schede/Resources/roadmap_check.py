"""Roadmap check: la roadmap contro la cassa vera e le risorse del piano, voce per voce."""
import datetime

import disegni as DG
import risorse as RS

from dati_app import data_corta
from tema import CI as C, PERSA, SFONDO_FASCIA, SFONDO_LINEA, TEND, VINTA, barra_scura
from widget import a_riposo, pronta_poi


class RoadmapCheck:
    """Roadmap check: la roadmap contro la cassa vera, giorno per giorno."""

    # le voci del grafico: il ROI acceso di default, poi le voci della tendina Resource del Trend (Autore, 9 nov 2026: «nel grafico della roadmap ne usiamo solo uno
    # con i flag sotto: di default segna il roi di andamento atteso, coi flag che poi sono le stesse voci del menu a tendina della tabella trend controlliamo ogni voce quanto
    # sta sopra o sotto all'andamento atteso»). Colori: azzurro per il ROI, gli altri lontani fra loro e dai rossi e verdi dei numeri
    VOCI_AND = (("ROI", "ROI", "#2f9bff"), ("Oro", "Gold", "#e8c15a"), ("Gemme", "Gems", "#a58cff"), ("Buste", "Packs", "#7fd1c7"), ("Carte", "Cards", "#d7dce5"),
                ("Jolly", "Wildcards", "#ff7a3d"))

    def finestra_andamento(self):
        """Roadmap check (Autore, 9 nov 2026: «creiamo un pulsante nella sezione ROI che apre in dettaglio i dati con un grafo e ci aiuta a capire se siamo sopra o sotto la road map nel periodo
        di gioco e in che %»). Una finestra sopra il Companion, transient, Esc chiude: come si conta l'oro, i riquadri di oggi, un grafico solo della % sopra o sotto l'atteso giorno per giorno
        su tutto il periodo del piano, e sotto le spunte delle voci: il ROI (acceso) e le voci del Trend. Il conto e' Risorse.andamento con le attese del piano."""
        tk, F, R = self.tk, self.F, self.R
        vecchia = getattr(self, "fin_and", None)
        if vecchia is not None and vecchia.winfo_exists():
            vecchia.destroy()
        padre = self.fr.winfo_toplevel()
        f = self.fin_and = pronta_poi(tk.Toplevel(padre, bg=C["fondo"]))
        f.transient(padre)
        f.title("Roadmap check")
        barra_scura(f, C["fondo"], C["titolo"], C["filo"])
        f.bind("<Escape>", lambda e: f.destroy())
        testa = tk.Frame(f, bg=C["cap"]); testa.pack(fill="x")
        tk.Label(testa, text="Roadmap check", bg=C["cap"], fg=C["titolo"], font=F(13, True)).pack(side="left", padx=(14, 10), pady=10)
        info = tk.Label(testa, text="", bg=C["cap"], fg=C["grigio"], font=F(9)); info.pack(side="left")
        tk.Frame(f, bg=C["filo"], height=1).pack(fill="x")
        corpo = tk.Frame(f, bg=C["scheda"], padx=16, pady=12); corpo.pack(fill="both", expand=True)
        attese = (self.piano or {}).get("attese") or (R.attese(self.calcolo[0]) if R is not None and self.calcolo else None)
        an = R.andamento(self.piano, attese=attese) if R is not None and self.piano else None
        L_, H_ = 1040, 820
        if an is None:
            tk.Label(corpo, text="No plan yet: create one in the Farmer, then come back to see how your real balance follows it.", bg=C["scheda"], fg=C["grigio"], font=F(10), anchor="w").pack(fill="x", pady=20)
            L_, H_ = 640, 160
        else:
            info.configure(text=f"Plan {data_corta(an['dal'])} – {data_corta(an['al'])}  ·  last balance reading {R.foto[-1]['t'][:16].replace('-', '/')}")
            if set(getattr(self, "flag_and", {})) != {k for k, _n, _c in self.VOCI_AND}:
                self.flag_and = {k: k == "ROI" for k, _n, _c in self.VOCI_AND}
            if getattr(self, "cambio_and", None) not in ("wr", "busta"):
                self.cambio_and = "busta" if self.modo_cambio == "busta" else "wr"
            gpo_wr = R.cambio_oro(self.win_l(), self.win_cc())["gpo"]
            dentro = tk.Frame(corpo, bg=C["scheda"]); dentro.pack(fill="both", expand=True)

            def ridisegna():
                self.svuota(dentro)
                self.disegna_andamento(dentro, an, gpo_wr, ridisegna)
            ridisegna()
        # la finestra sta dentro lo schermo e dentro il Companion (9 nov 2026, «impaginala meglio perche' sul fondo e' tagliata»): il grafico ha un'altezza minima e prende quel
        # che resta, quindi una finestra piu' bassa lo stringe invece di tagliarlo
        f.update_idletasks()
        alto_max = f.winfo_screenheight() - 110
        if padre.winfo_height() > 400:
            alto_max = min(alto_max, padre.winfo_height() - 20)
        L_ = min(max(L_, f.winfo_reqwidth()), f.winfo_screenwidth() - 80)
        H_ = min(max(H_, f.winfo_reqheight()), alto_max)
        x_ = padre.winfo_rootx() + max(0, (padre.winfo_width() - L_) // 2)
        y_ = padre.winfo_rooty() + max(0, (padre.winfo_height() - H_) // 2)
        f.minsize(760, min(520, alto_max))
        f.geometry(f"{L_}x{H_}+{x_}+{y_}")
        f.lift(); f.focus_set()
        return f

    def spunta_and(self, padre, testo, on, colore, azione, tondo=False, spiega=""):
        """Una spunta di Roadmap check: quadrata per le voci, tonda per il cambio dell'oro (una sola accesa)."""
        tk, F = self.tk, self.F
        r_ = tk.Frame(padre, bg=C["scheda"], cursor="hand2")
        c = tk.Canvas(r_, width=13, height=13, bg=C["scheda"], highlightthickness=0, cursor="hand2"); c.pack(side="left", padx=(0, 6))
        c.create_image(0, 0, image=(DG.tondo if tondo else DG.spunta)(13, on, colore, TEND["campo"], TEND["bordo"], C["fondo"]), anchor="nw")
        l1 = tk.Label(r_, text=testo, bg=C["scheda"], fg=C["titolo"] if on else C["testo"], font=F(9, True), cursor="hand2"); l1.pack(side="left")
        ws = [r_, c, l1]
        if spiega:
            l2 = tk.Label(r_, text="  ·  " + spiega, bg=C["scheda"], fg=C["grigio"], font=F(8), cursor="hand2"); l2.pack(side="left"); ws.append(l2)
        for w in ws:
            w.bind("<Button-1>", lambda e: azione())
        return r_

    def disegna_andamento(self, padre, an, gpo_wr, ridisegna):
        """Il contenuto di Roadmap check: come si conta l'oro, i riquadri di oggi per le voci accese, il grafico della % e le spunte delle voci sotto."""
        tk, F = self.tk, self.F
        segno = lambda x, d=0: (f"+{x:,.{d}f}" if x >= 0 else f"{x:,.{d}f}").replace("+-", "-")
        oggi_ = an["giorni"][-1]
        gpo = gpo_wr if self.cambio_and == "wr" else RS.GEMME_PER_ORO
        # come si conta l'oro nel ROI: le gemme che ti torna al win rate di adesso, o il prezzo di una busta
        r_f = tk.Frame(padre, bg=C["scheda"]); r_f.pack(fill="x", pady=(0, 8))
        self.etichetta(r_f, "gold counted at").pack(anchor="w", pady=(0, 3))

        def cambio(k):
            self.cambio_and = k; ridisegna()
        for k, nome, spiega in (("wr", "My win rate", f"1,000 gold = {round(1000 * gpo_wr)} gems back at your win rate now (limited {round(100 * self.win_l())}%, constructed {round(100 * self.win_cc())}%)"),
                                ("busta", "Pack price", "1,000 gold = 200 gems in cards and packs")):
            self.spunta_and(r_f, nome, self.cambio_and == k, C["azzurro"], lambda k=k: cambio(k), tondo=True, spiega=spiega).pack(anchor="w", pady=1)
        accese = [(k, n, c) for k, n, c in self.VOCI_AND if self.flag_and[k] and RS.scarto_voce(oggi_, k, gpo) is not None]
        # oggi: quanto sta sopra o sotto ogni voce accesa, coi numeri veri e attesi
        icone = {"Oro": self.icona("oro", 16), "Gemme": self.icona("gemma", 16), "Buste": self.icona("busta", 16), "Carte": self.icona("carte", 16), "Jolly": self.icona_j("R")}
        unita = {"ROI": " gems", "Oro": "", "Gemme": "", "Buste": "", "Carte": "", "Jolly": ""}
        voci = []
        for k, nome, _c in accese:
            v_, a_, pc = RS.scarto_voce(oggi_, k, gpo)
            voci.append((f"{nome} vs expected", f"{segno(pc, 1)}%" if pc is not None else "-", None if pc is None else VINTA if pc >= 0 else PERSA,
                         f"{round(v_):,} real · {round(a_):,} expected{unita[k]}", icone.get(k)))
        az = an["azioni"]
        voci.append(("roadmap actions", f"{az.get('fatta', 0)} done", None, f"{az.get('ritardo', 0)} late · {az.get('da_fare', 0)} to do"))
        r_g = tk.Frame(padre, bg=C["scheda"]); r_g.pack(fill="x")
        self.griglia(r_g, voci, colonne=min(len(voci), 4), grande=14, stretta=True)
        spiega = ("Expected = the roadmap's cash that day (plus the money of actions not done yet, minus prizes of events not played); packs, cards and wildcards: what the plan brings "
                  "in a day, times the days since it started. ROI = gold at the rate above, gems, and packs got at 200 gems each.")
        nota = f"On {data_corta(oggi_['data'])}, your last reading. " + spiega
        if len(an["giorni"]) == 1:
            nota = (f"No balance reading since the plan started on {data_corta(an['dal'])}: Arena writes your balance when you log in, and the plan starts from your reading of "
                    f"{data_corta(self.R.foto[-1]['t'])}. " + spiega)
        l_n = tk.Label(padre, text=nota, bg=C["scheda"], fg=C["muto"], font=F(7), anchor="w", justify="left", wraplength=900); l_n.pack(fill="x", pady=(0, 8))
        l_n.bind("<Configure>", lambda e: l_n.configure(wraplength=max(300, e.width - 4)))
        # un grafico solo: una linea per voce accesa, lo zero e' l'atteso
        date = [(datetime.date.fromisoformat(an["dal"]) + datetime.timedelta(days=t)).isoformat() for t in range(len(an["piano"]))]
        serie = [(nome, [(RS.scarto_voce(g, k, gpo) or (0, 0, None))[2] for g in an["giorni"]], col, "") for k, nome, col in accese]
        self.etichetta(padre, "above or below what the plan expects, %").pack(anchor="w", pady=(4, 2))
        # le spunte delle voci sotto il grafico: si impaccano prima, dal fondo, cosi' il grafico prende quel che resta
        r_v = tk.Frame(padre, bg=C["scheda"]); r_v.pack(side="bottom", fill="x", pady=(8, 0))

        def scambia(k):
            if sum(self.flag_and.values()) > 1 or not self.flag_and[k]:      # almeno una resta accesa
                self.flag_and[k] = not self.flag_and[k]
                ridisegna()
        for k, nome, col in self.VOCI_AND:
            possibile = RS.scarto_voce(oggi_, k, gpo) is not None
            s_ = self.spunta_and(r_v, nome if possibile else nome + " (no plan data)", self.flag_and[k] and possibile, col, (lambda k=k: scambia(k)) if possibile else (lambda: None))
            s_.pack(side="left", padx=(0, 16))
        self.grafico_linee(padre, date, serie, lambda x: f"{segno(x, 1)}%", altezza=160, zero="expected", legenda=False)

    def grafico_linee(self, padre, date, serie, fmt, altezza=160, zero=None, legenda=True):
        """Un grafico a linee sui giorni del piano: date = tutti i giorni (l'asse x), serie = [(nome, valori dal primo giorno, colore, «tratto»|"")], una serie puo' fermarsi prima della fine.
        La legenda sopra, l'oggi segnato, lo zero marcato col suo nome se c'e'. Il puntatore mostra il giorno e i valori di ogni serie."""
        tk, F = self.tk, self.F
        import math
        r_l = tk.Frame(padre, bg=C["scheda"]); r_l.pack(fill="x", pady=(0, 2))
        for nome, _, col, tratto in serie if legenda else ():
            c = tk.Canvas(r_l, width=18, height=10, bg=C["scheda"], highlightthickness=0); c.pack(side="left", padx=(0, 4))
            c.create_line(0, 5, 18, 5, fill=col, width=2, dash=(4, 3) if tratto else None)
            tk.Label(r_l, text=nome, bg=C["scheda"], fg=C["testo"], font=F(8)).pack(side="left", padx=(0, 12))
        v_info = tk.StringVar(value="")
        tk.Label(padre, textvariable=v_info, bg=C["scheda"], fg=C["titolo"], font=F(8), anchor="w").pack(fill="x")
        cv = tk.Canvas(padre, height=altezza, bg=C["scheda"], highlightthickness=0); cv.pack(fill="both", expand=True)
        tutti = [v for _, vs, _, _ in serie for v in vs if v is not None] + ([0.0] if zero else [])
        if not tutti:
            return cv
        lo, hi = min(tutti), max(tutti)
        if hi - lo < 1e-9:
            lo, hi = lo - 1, hi + 1
        passo = 10 ** math.floor(math.log10((hi - lo) / 4)) if hi > lo else 1
        for m in (1, 2, 2.5, 5, 10):
            if (hi - lo) / (passo * m) <= 5:
                passo *= m; break
        lo, hi = math.floor(lo / passo) * passo, math.ceil(hi / passo) * passo
        oggi_i = (datetime.date.today() - datetime.date.fromisoformat(date[0])).days
        geo = {}

        def disegna(e=None):
            cv.delete("all")
            W, H = cv.winfo_width(), cv.winfo_height()
            sx, dx_, su, giu = 52, 10, 8, 20
            larg, alt = W - sx - dx_, H - su - giu
            X = lambda i: sx + larg * i / max(len(date) - 1, 1)
            Y = lambda v: su + alt * (hi - v) / (hi - lo)
            geo.update(X=X, sx=sx, larg=larg, su=su, H=H)
            k, v = 0, lo
            salta = 2 if alt * passo / (hi - lo) < 18 else 1       # a grafico basso un numero si' e uno no, se no si toccano
            while v <= hi + 1e-9:
                if k % 2 == 0 and v + passo <= hi + 1e-9:
                    cv.create_rectangle(sx, Y(v + passo), W - dx_, Y(v), fill=SFONDO_FASCIA, width=0)
                cv.create_line(sx, Y(v), W - dx_, Y(v), fill=SFONDO_LINEA)
                if k % salta == 0:
                    cv.create_text(sx - 6, Y(v), text=fmt(v), anchor="e", fill=C["muto"], font=F(7))
                v += passo; k += 1
            if zero is not None:
                cv.create_line(sx, Y(0), W - dx_, Y(0), fill=C["grigio"], width=1)
                cv.create_text(W - dx_ - 2, Y(0) - 2, text=zero, anchor="se", fill=C["grigio"], font=F(7, True))
            cv.create_line(sx, su, sx, H - giu, fill=C["filo"])
            ultima_x = -99
            for i, d in enumerate(date):
                if i in (0, len(date) - 1) or i % 5 == 0:
                    x = X(i)
                    if x - ultima_x > 40 or i == len(date) - 1:
                        cv.create_line(x, H - giu, x, H - giu + 4, fill=C["muto"])
                        cv.create_text(x, H - giu + 5, text=data_corta(d), anchor="ne" if i == len(date) - 1 else "nw" if i == 0 else "n", fill=C["muto"], font=F(7)); ultima_x = x
            if 0 <= oggi_i < len(date):         # oggi: da qui in poi la roadmap e' solo un piano
                cv.create_line(X(oggi_i), su, X(oggi_i), H - giu, fill=C["muto"], dash=(2, 3))
                cv.create_text(X(oggi_i) + 3, su, text="today", anchor="nw", fill=C["muto"], font=F(7))
            linee, punti_ = [], []           # le linee e i punti in uno strato nitido sopra la griglia (disegni.py)
            for nome, vs, col, tratto in serie:
                xy = [(X(i), Y(v)) for i, v in enumerate(vs) if v is not None]
                if len(xy) >= 2:
                    linee.append((xy, col, 2, (4, 3) if tratto else None))
                if xy and not tratto:       # l'ultimo punto: dove sei adesso
                    punti_.append((xy[-1][0], xy[-1][1], 5, col, C["scheda"], 2))
            cv.strato_ = DG.tratti(W, H, linee, punti_)
            cv.create_image(0, 0, image=cv.strato_, anchor="nw")

        def sopra(e):
            if not geo:
                return
            i = max(0, min(len(date) - 1, round((e.x - geo["sx"]) / max(geo["larg"], 1) * max(len(date) - 1, 1))))
            cv.delete("cursore")
            cv.create_line(geo["X"](i), geo["su"], geo["X"](i), geo["H"] - 20, fill=C["grigio"], tags="cursore")
            parti = [f"{nome} {fmt(vs[i])}" for nome, vs, _, _ in serie if i < len(vs) and vs[i] is not None]
            v_info.set(f"{data_corta(date[i])}  ·  " + ("  ·  ".join(parti) if parti else "no reading yet"))
        cv.bind("<Configure>", a_riposo(cv, disegna)); cv.bind("<Motion>", sopra)      # trascinando il bordo: una volta, a misura ferma
        cv.bind("<Leave>", lambda e: (cv.delete("cursore"), v_info.set("")))
        return cv
