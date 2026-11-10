"""La vista Charts della scheda Meta: il meta giocato mazzo per mazzo, a elenco e coi grafici (Autore, 10 nov 2026: «una seconda sezione che non e'
visualizzata a scacchiera ma a elenchi e ci fa vedere il meta giocato per mazzo in termini di grafici», «includendo anche il meta del limited»).

In alto due grafici, quando hanno i dati: META SHARE × WIN RATE (un punto per mazzo, la linea del 50%; solo dove c'e' il win rate: Standard e il limited)
e META SHARE OVER TIME (i sei mazzi piu' giocati giorno per giorno, dallo storico di Motore/meta_storico.py, da due giorni in su). Sotto la tabella, un
mazzo per riga: posto, colori e nome, la quota con la barra, il win rate con la barra centrata sul 50% (o la forza, o i mazzi nei tornei), il win rate per
rango, partite (o draft), il turno medio delle vittorie (limited) o il prezzo (costruito), l'andamento della quota. Il clic su un mazzo costruito apre la
sua finestra, come nelle schede. Linee e punti passano da disegni.py (antialias); testi e linee dritte sono della tela.
"""
import disegni as DG
import prezzi_carte as PZ

from dati_grafici import RANGHI, serie
from tema import CI as C, PERSA, VINTA

MANA = dict(W="#efe3b8", U="#3fa3e8", B="#a08fc2", R="#e5533d", G="#46b56e", C="#9a9794")     # i punti dei grafici, leggibili sul fondo scuro
LINEE = ("#24baff", "#f0ad4e", "#5cb85c", "#ee8a87", "#c39bd3", "#61cdff")                    # le linee dell'andamento, una per mazzo
ALTA_RIGA = 40
ALTO_GRAFICO = 300


def colore(col, i=0):
    k = [c for c in "WUBRG" if c in (col or "")] or ["C"]
    return MANA[k[min(i, len(k) - 1)]]


class VistaGrafici:
    """Disegna in pagina.griglia_b. pagina: la PaginaMeta (tk, F, lista dei simboli, apri, foto)."""

    def __init__(self, pagina, righe, costruito, st, larga):
        self.p, self.tk, self.F = pagina, pagina.tk, pagina.F
        self.righe, self.costruito, self.st = righe, costruito, st
        self.W = max(760, larga - 30)
        self.foto = []          # le immagini dei tratti: vive finche' la tela c'e'
        self.tele = []

    def disegna(self):
        padre = self.p.griglia_b
        wr = [r for r in self.righe if r.get("wr") is not None]
        giorni = [g for g in sorted(self.st) if isinstance(self.st[g], dict)]
        alto = []
        if len(wr) >= 3:
            alto.append(self.dispersione)
        if len(giorni) >= 2:
            alto.append(self.andamento)
        if alto:
            fila = self.tk.Frame(padre, bg=C["scheda"]); fila.pack(fill="x", pady=(0, 14))
            lg = (self.W - 14 * (len(alto) - 1)) // len(alto)
            for i, f in enumerate(alto):
                c = self.tk.Canvas(fila, width=lg, height=ALTO_GRAFICO, bg=C["fondo"], highlightthickness=1, highlightbackground=C["filo"])
                c.pack(side="left", padx=(0 if i == 0 else 14, 0))
                f(c, lg, ALTO_GRAFICO)
                self.tele.append(c)
        self.tabella(padre)

    # ------------------------------------------------------------------ i grafici
    def cornice(self, c, titolo, l, h):
        c.create_text(14, 16, text=titolo, anchor="w", fill=C["titolo"], font=self.F(8, True))
        return 54, 38, l - 20, h - 32          # x0, y0, x1, y1 dell'area del grafico

    def dispersione(self, c, l, h):
        x0, y0, x1, y1 = self.cornice(c, "META SHARE × WIN RATE", l, h)
        rr = [r for r in self.righe if r.get("wr") is not None]
        qm = max(r["quota"] for r in rr) * 1.12
        wmin = min(min(r["wr"] for r in rr), 50) - 1.5
        wmax = max(max(r["wr"] for r in rr), 50) + 1.5
        X = lambda q: x0 + (x1 - x0) * q / qm
        Y = lambda w: y1 - (y1 - y0) * (w - wmin) / (wmax - wmin)
        passo = 2 if wmax - wmin <= 14 else 5
        w = int(wmin // passo + 1) * passo
        while w < wmax:
            c.create_line(x0, Y(w), x1, Y(w), fill=C["filo2"] if w != 50 else C["filo"])
            c.create_text(x0 - 8, Y(w), text=f"{w}%", anchor="e", fill=C["muto"], font=self.F(7))
            w += passo
        pq = 1 if qm <= 8 else 2 if qm <= 16 else 5
        q = pq
        while q < qm:
            c.create_text(X(q), y1 + 12, text=f"{q}%", anchor="n", fill=C["muto"], font=self.F(7))
            q += pq
        c.create_line(x0, y1, x1, y1, fill=C["filo"])
        linee = [([(x0, Y(50)), (x1, Y(50))], C["grigio"], 1.0, (5, 4))]
        punti = []
        for r in sorted(rr, key=lambda r: r["quota"]):
            punti.append((X(r["quota"]), Y(r["wr"]), 6, colore(r["colori"]), colore(r["colori"], 1), 2.0))
        im = DG.tratti(l, h, linee=linee, punti=punti)
        self.foto.append(im)
        c.create_image(0, 0, image=im, anchor="nw")
        c.create_text(x1, Y(50) - 7, text="50%", anchor="e", fill=C["grigio"], font=self.F(7, True))
        c.create_text(x1, y1 - 5, text="meta share →", anchor="se", fill=C["muto"], font=self.F(7))
        presi = []          # i nomi dei mazzi piu' giocati accanto al punto, senza sovrapporsi
        for r in sorted(rr, key=lambda r: -r["quota"])[:10]:
            x, y = X(r["quota"]) + 9, Y(r["wr"])
            ancora = "w"
            if x + 7 * len(r["nome"]) > x1:
                x, ancora = X(r["quota"]) - 9, "e"
            box = (x - (7 * len(r["nome"]) if ancora == "e" else 0), y - 7, x + (7 * len(r["nome"]) if ancora == "w" else 0), y + 7)
            if any(not (box[2] < b[0] or box[0] > b[2] or box[3] < b[1] or box[1] > b[3]) for b in presi):
                continue
            presi.append(box)
            c.create_text(x, y, text=r["nome"], anchor=ancora, fill=C["testo"], font=self.F(7))
        self.suggerimenti(c, [(X(r["quota"]), Y(r["wr"]), f"{r['nome']} · {r['quota']:.1f}% · {r['wr']:.1f}% win rate") for r in rr])

    def andamento(self, c, l, h):
        x0, y0, x1, y1 = self.cornice(c, "META SHARE OVER TIME", l, h)
        giorni = [g for g in sorted(self.st) if isinstance(self.st[g], dict)]
        primi = [r for r in self.righe][:6]
        ss = [(r, serie(self.st, r["nome"])) for r in primi]
        ss = [(r, s) for r, s in ss if s]
        if not ss:
            c.create_text(l / 2, h / 2, text="No history yet", fill=C["muto"], font=self.F(8))
            return
        qm = max(q for _r, s in ss for _g, q in s) * 1.15
        import datetime
        d = lambda g: datetime.date.fromisoformat(g).toordinal()
        a, b = d(giorni[0]), max(d(giorni[-1]), d(giorni[0]) + 1)
        X = lambda g: x0 + (x1 - x0 - 110) * (d(g) - a) / (b - a)
        Y = lambda q: y1 - (y1 - y0) * q / qm
        pq = 2 if qm <= 12 else 5 if qm <= 30 else 10
        q = 0
        while q < qm:
            c.create_line(x0, Y(q), x1 - 110, Y(q), fill=C["filo2"] if q else C["filo"])
            c.create_text(x0 - 8, Y(q), text=f"{q}%", anchor="e", fill=C["muto"], font=self.F(7))
            q += pq
        for g in (giorni[0], giorni[-1]) if len(giorni) < 6 else giorni[::max(1, len(giorni) // 5)] + [giorni[-1]]:
            c.create_text(X(g), y1 + 12, text=f"{g[8:10]}/{g[5:7]}", anchor="n", fill=C["muto"], font=self.F(7))
        linee, punti = [], []
        for i, (r, s) in enumerate(ss):
            col = LINEE[i % len(LINEE)]
            pts = [(X(g), Y(q)) for g, q in s]
            if len(pts) > 1:
                linee.append((pts, col, 2.0, None))
            punti += [(x, y, 3, col, None, 0) for x, y in pts]
        im = DG.tratti(l, h, linee=linee, punti=punti)
        self.foto.append(im)
        c.create_image(0, 0, image=im, anchor="nw")
        presi = []
        for i, (r, s) in sorted(enumerate(ss), key=lambda t: -Y(t[1][1][-1][1])):
            y = Y(s[-1][1])
            while any(abs(y - p) < 13 for p in presi):
                y -= 13
            presi.append(y)
            c.create_text(x1 - 104, y, text=r["nome"][:16], anchor="w", fill=LINEE[i % len(LINEE)], font=self.F(7, True))
        self.suggerimenti(c, [(X(g), Y(q), f"{r['nome']} · {g[8:10]}/{g[5:7]} · {q:.1f}%") for r, s in ss for g, q in s])

    def suggerimenti(self, c, punti):
        """Il nome e i numeri del punto sotto il puntatore."""
        def muovi(e):
            c.delete("sugg")
            vicino = min(punti, key=lambda p: (p[0] - e.x) ** 2 + (p[1] - e.y) ** 2, default=None)
            if not vicino or (vicino[0] - e.x) ** 2 + (vicino[1] - e.y) ** 2 > 144:
                return
            x, y, t = vicino
            ancora = "sw" if x < int(c.cget("width")) - 260 else "se"
            i = c.create_text(x + (8 if ancora == "sw" else -8), y - 8, text=t, anchor=ancora, fill=C["titolo"], font=self.F(8, True), tags="sugg")
            bb = c.bbox(i)
            r = c.create_rectangle(bb[0] - 6, bb[1] - 3, bb[2] + 6, bb[3] + 3, fill=C["cap"], outline=C["accento"], tags="sugg")
            c.tag_lower(r, i)
        c.bind("<Motion>", muovi)
        c.bind("<Leave>", lambda e: c.delete("sugg"))

    # ------------------------------------------------------------------ la tabella
    def colonne(self):
        W = self.W
        wr = any(r.get("wr") is not None for r in self.righe)
        per_rango = any(r.get("wr_ranghi") for r in self.righe)
        cols = [("#", 14, 30), ("DECK", 44, int(W * 0.22)), ("META SHARE", 0, int(W * 0.16)),
                ("WIN RATE" if wr else ("STRENGTH" if any(r.get("forza") for r in self.righe) else "DECKS"), 0, int(W * 0.15))]
        if per_rango:
            cols.append(("BY RANK", 0, int(W * 0.12)))
        cols.append(("GAMES" if self.costruito else "DRAFTS", 0, int(W * 0.08)))
        cols.append(("PRICE" if self.costruito else "WINS ON", 0, int(W * 0.08)))
        cols.append(("TREND", 0, int(W * 0.08)))
        x = 0
        out = {}
        for nome, x_, larga in cols:
            x = x_ or x
            out[nome] = (x, larga)
            x += larga + 12
        return out

    def tabella(self, padre):
        tk, F = self.tk, self.F
        col = self.colonne()
        H = 30 + ALTA_RIGA * len(self.righe) + 6
        c = tk.Canvas(padre, width=self.W, height=H, bg=C["scheda"], highlightthickness=0)
        c.pack(anchor="w")
        self.tele.append(c)
        for nome, (x, _l) in col.items():
            c.create_text(x, 14, text=nome, anchor="w", fill=C["titolo"], font=F(7, True))
        c.create_line(0, 28, self.W, 28, fill=C["filo"])
        qm = max([r["quota"] for r in self.righe] or [1])
        giorni = sorted(g for g in self.st if isinstance(self.st[g], dict))
        rk = [k for k in RANGHI if any(k in (r.get("wr_ranghi") or {}) for r in self.righe)]      # i ranghi che la fonte da' (Standard 4, limited 6)
        linee, punti = [], []
        for i, r in enumerate(self.righe):
            y0 = 30 + i * ALTA_RIGA
            ym = y0 + ALTA_RIGA / 2
            c.create_rectangle(0, y0, self.W, y0 + ALTA_RIGA, fill=C["fondo"] if i % 2 else C["scheda"], width=0, tags=("fascia", f"r{i}"))
            c.create_text(col["#"][0], ym, text=str(i + 1), anchor="w", fill=C["grigio"], font=F(9, True))
            x = col["DECK"][0]
            for k in [z for z in "WUBRG" if z in (r.get("colori") or "")]:
                img = self.p.lista.simbolo(k, 14)
                if img:
                    c.create_image(x + 7, ym, image=img)
                    x += 17
            nome = r["nome"] if len(r["nome"]) <= 28 else r["nome"][:27] + "…"
            c.create_text(x + 5, ym, text=nome, anchor="w", fill=C["titolo"], font=F(10, True))
            # la quota: barra sulla quota piu' alta
            x, lg = col["META SHARE"]
            lb = lg - 52
            c.create_rectangle(x, ym - 4, x + lb, ym + 4, fill=C["traccia"], width=0)
            c.create_rectangle(x, ym - 4, x + max(2, lb * r["quota"] / qm), ym + 4, fill=C["accento"], width=0)
            c.create_text(x + lg, ym, text=f"{r['quota']:.1f}%", anchor="e", fill=C["accento"], font=F(10, True))
            # il win rate: barra dal 50%, da 40 a 60
            nome_wr = [k for k in col if k in ("WIN RATE", "STRENGTH", "DECKS")][0]
            x, lg = col[nome_wr]
            if r.get("wr") is not None:
                lb = lg - 56
                cx = x + lb / 2
                dw = max(-10.0, min(10.0, r["wr"] - 50))
                cc = VINTA if r["wr"] >= 50 else PERSA
                c.create_rectangle(x, ym - 4, x + lb, ym + 4, fill=C["traccia"], width=0)
                c.create_rectangle(min(cx, cx + lb / 2 * dw / 10), ym - 4, max(cx, cx + lb / 2 * dw / 10), ym + 4, fill=cc, width=0)
                c.create_line(cx, ym - 7, cx, ym + 7, fill=C["grigio"])
                c.create_text(x + lg, ym, text=f"{r['wr']:.1f}%", anchor="e", fill=cc, font=F(10, True))
            elif r.get("forza"):
                c.create_text(x, ym, text=f"{r['forza']}°", anchor="w", fill=C["testo"], font=F(10, True))
            elif r.get("mazzi"):
                c.create_text(x, ym, text=f"{r['mazzi']:,}", anchor="w", fill=C["testo"], font=F(10, True))
            else:
                c.create_text(x, ym, text="-", anchor="w", fill=C["muto"], font=F(10))
            # il win rate per rango: un punto per rango, la linea del 50%
            if "BY RANK" in col:
                x, lg = col["BY RANK"]
                pr = [(k, r["wr_ranghi"][k]) for k in RANGHI if k in (r.get("wr_ranghi") or {})]
                if len(pr) >= 2:
                    c.create_line(x, ym, x + lg, ym, fill=C["filo"])
                    pts = [(x + lg * rk.index(k) / max(len(rk) - 1, 1), ym - max(-13, min(13, (w - 50) * 1.3))) for k, w in pr]
                    linee.append((pts, C["acciaio"], 1.5, None))
                    punti += [(px, py, 2.5, C["acciaio"], None, 0) for px, py in pts]
            # partite o draft
            x, lg = col["GAMES" if self.costruito else "DRAFTS"]
            n = r.get("partite") if self.costruito else r.get("draft")
            c.create_text(x, ym, text=f"{n:,}" if n else "-", anchor="w", fill=C["testo"], font=F(9))
            # prezzo o turno delle vittorie
            x, lg = col["PRICE" if self.costruito else "WINS ON"]
            if self.costruito:
                t = PZ.euro(r["eur"]) if r.get("eur") else "-"
            else:
                t = f"T{r['turni']:.1f}" if r.get("turni") else "-"
            c.create_text(x, ym, text=t, anchor="w", fill=C["testo"], font=F(9))
            # l'andamento della quota
            x, lg = col["TREND"]
            s = serie(self.st, r["nome"])
            if len(s) >= 2 and len(giorni) >= 2:
                import datetime
                a = datetime.date.fromisoformat(giorni[0]).toordinal(); b = max(datetime.date.fromisoformat(giorni[-1]).toordinal(), a + 1)
                mq = max(q for _g, q in s) or 1
                pts = [(x + lg * (datetime.date.fromisoformat(g).toordinal() - a) / (b - a), ym + 11 - 22 * q / mq) for g, q in s]
                su = s[-1][1] >= s[-2][1]
                linee.append((pts, VINTA if su else PERSA, 1.5, None))
                punti.append((pts[-1][0], pts[-1][1], 2.5, VINTA if su else PERSA, None, 0))
            else:
                c.create_text(x, ym, text="-", anchor="w", fill=C["muto"], font=F(9))
        if linee or punti:
            im = DG.tratti(self.W, H, linee=linee, punti=punti)
            self.foto.append(im)
            c.create_image(0, 0, image=im, anchor="nw")
        # passaggio del mouse e clic
        sopra = {"i": None}

        def riga(e):
            i = int((c.canvasy(e.y) - 30) // ALTA_RIGA)
            return i if 0 <= i < len(self.righe) and e.y >= 30 else None

        def muovi(e):
            i = riga(e)
            if i == sopra["i"]:
                return
            if sopra["i"] is not None:
                c.itemconfigure(f"r{sopra['i']}", fill=C["fondo"] if sopra["i"] % 2 else C["scheda"], outline="", width=0)
            sopra["i"] = i
            if i is not None:
                c.itemconfigure(f"r{i}", fill=C["cap"], outline=C["accento"] if self.costruito else "", width=1 if self.costruito else 0)
            c.configure(cursor="hand2" if i is not None and self.costruito else "")

        def esci(e):
            if sopra["i"] is not None:
                c.itemconfigure(f"r{sopra['i']}", fill=C["fondo"] if sopra["i"] % 2 else C["scheda"], outline="", width=0)
            sopra["i"] = None

        c.bind("<Motion>", muovi)
        c.bind("<Leave>", esci)
        if self.costruito:
            c.bind("<Button-1>", lambda e: riga(e) is not None and self.p.apri(("meta", self.righe[riga(e)])))
        self.tabella_c = c
