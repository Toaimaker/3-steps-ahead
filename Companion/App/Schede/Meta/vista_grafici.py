"""La vista Charts della scheda Meta (12 nov 2026, ridisegnata su indicazione di Autore: «i grafici devono essere leggibili / i deck top 10 li mettiamo sulla
sinistra incolonnati lunghi e stretti con i flag accanto / sulla destra un solo grafico di andamento per ogni deck flaggato e ogni deck col suo colore /
vogliamo i grafici dei deck piu' giocati e win quotidianamente e gli stessi dati per season»; poi «nell'ordine che decidi tu»).

- A sinistra, stretta e lunga, la colonna dei 10 mazzi in testa (nell'ordine di Sort by): la spunta nel colore della sua linea, il posto, i colori, il nome,
  sotto quota e win rate di adesso. Il clic spunta o toglie il mazzo dal grafico; il doppio clic su un mazzo costruito apre la sua finestra (nel limited
  niente: e' una coppia di colori). Partono spuntati i primi 3; le spunte restano per formato finche' la finestra e' aperta (PaginaMeta.flag_grafici).
- A destra un grafico solo: una linea per mazzo spuntato, col suo colore e il nome in fondo alla linea. Sopra due scelte: META SHARE o WIN RATE (il win
  rate solo dove la fonte lo da': Standard e il limited), DAILY o BY SEASON (la stagione classificata di Arena, un mese: la media dei giorni,
  dati_grafici.per_stagione). I dati sono lo storico di Motore/meta_storico.py, una foto al giorno. Il puntatore dice mazzo, giorno e valore.
Linee e punti passano da disegni.py (antialias); testi e linee dritte sono della tela. Fino all'11 nov 2026 qui c'erano il grafico quota x win rate, i sei
mazzi piu' giocati nel tempo e la tabella di tutti i mazzi.
"""
import datetime
import math

import disegni as DG

from dati_grafici import matrice, nome_stagione, per_stagione, serie_di
from tema import CI as C, PERSA, VINTA

TOP = 10
SPUNTATI = 3
LINEE = ("#24baff", "#f0ad4e", "#5cb85c", "#ee8a87", "#c39bd3", "#e8d36a", "#4fd1b5", "#ff8fc8", "#9fa8ff", "#d0a070")   # una per posto, distinte sul fondo scuro
ALTA_RIGA = 50
LARGA_LISTA = 300
CITAZIONE = "Data: 17Lands public datasets ↗ (CC BY 4.0), aggregated by 3 Steps Ahead · not endorsed by 17Lands"
URL_17LANDS = "https://www.17lands.com/public_datasets"
ETICHETTE = 150         # lo spazio a destra del grafico per i nomi in fondo alle linee


def _mischia(a, b, t):
    """Il colore a sfumato verso b di t (0-1)."""
    a, b = a.lstrip("#"), b.lstrip("#")
    return "#" + "".join(f"{round(int(a[k:k + 2], 16) * (1 - t) + int(b[k:k + 2], 16) * t):02x}" for k in (0, 2, 4))


class VistaGrafici:
    """Disegna in pagina.griglia_b. pagina: la PaginaMeta (tk, F, lista dei simboli, apri, t_fmt, flag_grafici)."""

    def __init__(self, pagina, righe, costruito, st, larga):
        self.p, self.tk, self.F = pagina, pagina.tk, pagina.F
        self.righe, self.costruito, self.st = righe, costruito, st
        self.top = righe[:TOP]
        self.W = max(760, larga - 30)
        self.foto = []          # le immagini dei tratti: vive finche' la tela c'e'
        self.tele = []
        if not hasattr(pagina, "flag_grafici"):
            pagina.flag_grafici = {}
        self.chiave = self.chiave_formato()
        nomi = [r["nome"] for r in self.top]
        scelti = pagina.flag_grafici.get(self.chiave)
        self.spuntati = [n for n in nomi if n in scelti] if scelti is not None else nomi[:SPUNTATI]
        self.ha_wr = any(r.get("wr") is not None for r in self.top) and any(serie_di(st, n, 1) for n in nomi)
        stato = getattr(pagina, "scelte_grafico", {"metrica": 0, "periodo": "daily"})
        pagina.scelte_grafico = stato
        self.metrica = stato["metrica"] if self.ha_wr else 0
        self.periodo = stato["periodo"]

    def chiave_formato(self):
        try:
            fmt = self.p.t_fmt.get()
            lim = self.p.limited() if hasattr(self.p, "limited") else None
            return fmt + (" " + self.p.t_set.get() if lim else "")
        except Exception:       # noqa: BLE001 - una pagina finta nelle prove
            return "?"

    def colore(self, nome):
        i = [r["nome"] for r in self.top].index(nome)
        return LINEE[i % len(LINEE)]

    # ------------------------------------------------------------------ disegno
    def disegna(self):
        padre = self.p.griglia_b
        H = max(460, 34 + ALTA_RIGA * len(self.top) + 10)
        fila = self.tk.Frame(padre, bg=C["scheda"]); fila.pack(fill="x", anchor="w")
        self.lista_c = self.tk.Canvas(fila, width=LARGA_LISTA, height=H, bg=C["scheda"], highlightthickness=0)
        self.lista_c.pack(side="left", anchor="n")
        self.lg = self.W - LARGA_LISTA - 16
        destra = self.tk.Frame(fila, bg=C["scheda"]); destra.pack(side="left", anchor="n", padx=(16, 0))
        self.scelte_c = self.tk.Canvas(destra, width=self.lg, height=34, bg=C["scheda"], highlightthickness=0)
        self.scelte_c.pack(anchor="w")
        self.grafico_c = self.tk.Canvas(destra, width=self.lg, height=H - 34, bg=C["fondo"], highlightthickness=1, highlightbackground=C["filo"])
        self.grafico_c.pack(anchor="w")
        self.tele += [self.lista_c, self.scelte_c, self.grafico_c]
        self.tabella_c = self.lista_c        # il nome di prima, per chi lo cerca
        self.storia = getattr(self.p, "storia_l", None)
        self.matrice_c = None
        if self.storia:
            self.matrice_c = self.tk.Canvas(destra, width=self.lg, height=10, bg=C["fondo"], highlightthickness=1, highlightbackground=C["filo"])
            self.matrice_c.pack(anchor="w", pady=(14, 0))
            self.tele.append(self.matrice_c)
        self.disegna_lista()
        self.disegna_scelte()
        self.disegna_grafico()
        if self.matrice_c is not None:
            self.disegna_matrice()

    def cita(self, c, x, y, coda=""):
        """La citazione di 17Lands, in vista e col link (le loro linee guida, 17lands.com/usage_guidelines, e la licenza CC BY 4.0 dei dati pubblici: la
        fonte, la licenza, il link; senza far credere che ci appoggino). Il clic apre la pagina dei dati pubblici."""
        t = c.create_text(x, y, text=CITAZIONE + coda, anchor="e", fill=C["link"] if "link" in C else C["accento"], font=self.F(8), tags=("cita",))
        c.tag_bind("cita", "<Button-1>", lambda e: __import__("webbrowser").open(URL_17LANDS))
        c.tag_bind("cita", "<Enter>", lambda e: c.configure(cursor="hand2"))
        c.tag_bind("cita", "<Leave>", lambda e: c.configure(cursor=""))
        return t

    def disegna_matrice(self):
        """La matrice coppia contro coppia dei 10 in testa, dai dati pubblici di 17Lands (12 nov 2026): il win rate della riga contro la colonna; sotto 200
        partite la cella e' grigia (rumore)."""
        c, F = self.matrice_c, self.F
        c.delete("all")
        nomi = [r["nome"] for r in self.top]
        m = matrice(self.storia, nomi)
        self.celle = m
        n = len(nomi)
        x0, y0, cel_h = 150, 64, 26
        cel_l = (self.lg - x0 - 14) / max(n, 1)
        c.configure(height=y0 + cel_h * n + 34)
        c.create_text(16, 18, text="MATCHUPS · ROW VS COLUMN", anchor="w", fill=C["titolo"], font=F(10, True))
        self.cita(c, self.lg - 14, 18, f" · Premier · {self.storia.get('dal', '')[8:10]}/{self.storia.get('dal', '')[5:7]}"
                  f"–{self.storia.get('al', '')[8:10]}/{self.storia.get('al', '')[5:7]} · {self.storia.get('partite', 0):,} games")
        cc = self.storia["coppie"].values()
        media = 100 * sum(x.get("w", 0) for x in cc) / max(sum(x.get("n", 0) for x in cc), 1)      # chi usa 17Lands vince piu' della media: i colori partono da qui
        self.media_matrice = media
        sugg = []
        for j, b in enumerate(nomi):
            c.create_text(x0 + cel_l * (j + 0.5), y0 - 10, text=b[:9], anchor="s", fill=LINEE[j % len(LINEE)], font=F(8, True))
        for i, a in enumerate(nomi):
            y = y0 + i * cel_h
            c.create_text(x0 - 10, y + cel_h / 2, text=a, anchor="e", fill=LINEE[i % len(LINEE)], font=F(9, True))
            for j, b in enumerate(nomi):
                x = x0 + j * cel_l
                nw = m.get((a, b))
                if nw and nw[0] >= 200:
                    wr = 100 * nw[1] / nw[0]
                    k = max(0.0, min(1.0, abs(wr - media) / 7))
                    base = VINTA if wr >= media else PERSA
                    fondo = _mischia(C["fondo"], base, 0.15 + 0.7 * k)
                    c.create_rectangle(x + 1, y + 1, x + cel_l - 1, y + cel_h - 1, fill=fondo, width=0)
                    c.create_text(x + cel_l / 2, y + cel_h / 2, text=f"{wr:.0f}", fill=C["titolo"], font=F(9, True))
                    sugg.append((x + cel_l / 2, y + cel_h / 2, f"{a} vs {b} · {wr:.1f}% · {nw[0]:,} games"))
                else:
                    c.create_rectangle(x + 1, y + 1, x + cel_l - 1, y + cel_h - 1, fill=C["scheda"], width=0)
                    c.create_text(x + cel_l / 2, y + cel_h / 2, text="·", fill=C["muto"], font=F(9))
        c.create_text(16, y0 + cel_h * n + 18, text=f"Win rate of the row deck against the column deck. 17Lands players win more than the average player "
                      f"({media:.1f}% here): blue is above that, red below. Grey: under 200 games.", anchor="w", fill=C["muto"], font=F(8))
        self.suggerimenti(c, sugg)

    def disegna_lista(self):
        c, F = self.lista_c, self.F
        c.delete("all")
        c.create_text(2, 12, text=f"TOP {len(self.top)}", anchor="w", fill=C["titolo"], font=F(8, True))
        c.create_text(LARGA_LISTA - 4, 12, text="tick to chart" + (" · double-click opens" if self.costruito else ""), anchor="e", fill=C["muto"], font=F(7))
        c.create_line(0, 26, LARGA_LISTA, 26, fill=C["filo"])
        for i, r in enumerate(self.top):
            y0 = 30 + i * ALTA_RIGA
            on = r["nome"] in self.spuntati
            col = LINEE[i % len(LINEE)]
            c.create_rectangle(0, y0, LARGA_LISTA, y0 + ALTA_RIGA - 2, fill=C["fondo"] if i % 2 else C["scheda"], width=0, tags=("fascia", f"r{i}"))
            c.create_image(6, y0 + ALTA_RIGA / 2 - 1, image=DG.spunta(16, on, col, C["fondo"], C["grigio"], C["fondo"]), anchor="w")
            c.create_text(32, y0 + 16, text=str(i + 1), anchor="w", fill=C["grigio"], font=F(9, True))
            x = 52
            for k in [z for z in "WUBRG" if z in (r.get("colori") or "")]:
                img = self.p.lista.simbolo(k, 13)
                if img:
                    c.create_image(x + 6, y0 + 16, image=img)
                    x += 15
            nome = r["nome"] if len(r["nome"]) <= 24 else r["nome"][:23] + "…"
            c.create_text(x + 4, y0 + 16, text=nome, anchor="w", fill=C["titolo"] if on else C["testo"], font=F(10, True))
            sotto = f"{r['quota']:.1f}% share"
            if r.get("wr") is not None:
                c.create_text(LARGA_LISTA - 6, y0 + 34, text=f"{r['wr']:.1f}% WR", anchor="e", fill=VINTA if r["wr"] >= 50 else PERSA, font=F(9, True))
            c.create_text(52, y0 + 34, text=sotto, anchor="w", fill=col if on else C["grigio"], font=F(9, True))
        sopra = {"i": None}

        def riga(e):
            i = int((e.y - 30) // ALTA_RIGA)
            return i if 0 <= i < len(self.top) and e.y >= 30 else None

        def colora(i, acceso):
            if i is not None:
                c.itemconfigure(f"r{i}", fill=C["cap"] if acceso else (C["fondo"] if i % 2 else C["scheda"]))

        def muovi(e):
            i = riga(e)
            if i != sopra["i"]:
                colora(sopra["i"], False); sopra["i"] = i; colora(i, True)
                c.configure(cursor="hand2" if i is not None else "")

        def esci(_e=None):
            colora(sopra["i"], False); sopra["i"] = None

        def clic(e):
            i = riga(e)
            if i is not None:
                self.spunta(self.top[i]["nome"])
                sopra["i"] = None
                colora(i, True); sopra["i"] = i

        def doppio(e):
            i = riga(e)
            if i is not None and self.costruito:
                self.spunta(self.top[i]["nome"])        # il primo clic del doppio ha cambiato la spunta: si rimette
                self.p.apri(("meta", self.top[i]))
        c.bind("<Motion>", muovi)
        c.bind("<Leave>", esci)
        c.bind("<Button-1>", clic)
        c.bind("<Double-Button-1>", doppio)
        self.clic, self.doppio = clic, doppio      # le prove li chiamano (Tk non genera il doppio clic)

    def spunta(self, nome):
        if nome in self.spuntati:
            self.spuntati.remove(nome)
        else:
            self.spuntati.append(nome)
        self.p.flag_grafici[self.chiave] = list(self.spuntati)
        self.disegna_lista()
        self.disegna_grafico()

    def disegna_scelte(self):
        """Due scelte a segmenti: la metrica e il periodo."""
        c, F = self.scelte_c, self.F
        c.delete("all")
        self.bottoni = {}
        x = 0
        gruppi = [("metrica", [(0, "META SHARE")] + ([(1, "WIN RATE")] if self.ha_wr else [])), ("periodo", [("daily", "DAILY"), ("season", "BY SEASON")])]
        for chiave, voci in gruppi:
            for v, testo in voci:
                on = getattr(self, chiave) == v
                lg = 14 + 8 * len(testo)
                t = f"b_{chiave}_{v}"
                c.create_rectangle(x, 4, x + lg, 28, fill=C["azzurro"] if on else C["fondo"], outline=C["azzurro"] if on else C["filo"], tags=(t,))
                c.create_text(x + lg / 2, 16, text=testo, fill=C["fondo"] if on else C["testo"], font=F(8, True), tags=(t,))
                c.tag_bind(t, "<Button-1>", lambda e, k=chiave, v=v: self.scegli(k, v))
                c.tag_bind(t, "<Enter>", lambda e: c.configure(cursor="hand2"))
                c.tag_bind(t, "<Leave>", lambda e: c.configure(cursor=""))
                self.bottoni[(chiave, v)] = t
                x += lg
            x += 18

    def scegli(self, chiave, v):
        setattr(self, chiave, v)
        self.p.scelte_grafico[chiave] = v
        self.disegna_scelte()
        self.disegna_grafico()

    def dati(self):
        """{nome: [(chiave, valore)]} dei mazzi spuntati, per metrica e periodo."""
        st = per_stagione(self.st) if self.periodo == "season" else self.st
        return {n: serie_di(st, n, self.metrica) for n in self.spuntati}

    def disegna_grafico(self):
        c, F = self.grafico_c, self.F
        c.delete("all")
        l, h = self.lg, int(c.cget("height"))
        nome_m = "WIN RATE" if self.metrica else "META SHARE"
        c.create_text(16, 18, text=f"{nome_m} · {'BY SEASON' if self.periodo == 'season' else 'DAILY'}", anchor="w", fill=C["titolo"], font=F(10, True))
        if getattr(self, "storia", None):
            self.cita(c, l - 14, 18)
        ss = {n: s for n, s in self.dati().items() if s}
        self.serie_disegnate = ss
        if not self.spuntati:
            c.create_text(l / 2, h / 2, text="Tick a deck on the left to chart it", fill=C["grigio"], font=F(10))
            return
        if not ss:
            c.create_text(l / 2, h / 2, text="No history for these decks yet: one snapshot a day builds it", fill=C["grigio"], font=F(10))
            return
        chiavi = sorted({k for s in ss.values() for k, _v in s})
        x0, y0, x1, y1 = 62, 44, l - ETICHETTE, h - 40
        vv = [v for s in ss.values() for _k, v in s]
        if self.metrica:
            lo, hi = min(min(vv), 50) - 2, max(max(vv), 50) + 2
            passo = 2 if hi - lo <= 16 else 5
        else:
            lo, hi = 0, max(vv) * 1.15 or 1
            passo = 1 if hi <= 6 else 2 if hi <= 14 else 5 if hi <= 35 else 10
        lo, hi = math.floor(lo / passo) * passo, math.ceil(hi / passo) * passo       # l'asse sui passi: la linea piu' alta ha la sua etichetta sopra
        Y = lambda v: y1 - (y1 - y0) * (v - lo) / (hi - lo)
        if self.periodo == "season":
            pos = {k: i for i, k in enumerate(chiavi)}
            X = lambda k: x0 + 30 + (x1 - x0 - 60) * (pos[k] / max(len(chiavi) - 1, 1)) if len(chiavi) > 1 else (x0 + x1) / 2
            etichette = [(k, nome_stagione(k)) for k in chiavi]
        else:
            o = lambda g: datetime.date.fromisoformat(g).toordinal()
            a, b = o(chiavi[0]), max(o(chiavi[-1]), o(chiavi[0]) + 1)
            X = lambda g: x0 + 10 + (x1 - x0 - 20) * (o(g) - a) / (b - a) if len(chiavi) > 1 else (x0 + x1) / 2
            scelte = chiavi if len(chiavi) <= 8 else chiavi[::max(1, len(chiavi) // 7)] + [chiavi[-1]]
            etichette = [(g, f"{g[8:10]}/{g[5:7]}") for g in dict.fromkeys(scelte)]
        v = lo
        while v <= hi + 1e-9:
            c.create_line(x0, Y(v), x1, Y(v), fill=C["filo"] if (self.metrica and v == 50) or (not self.metrica and v == 0) else C["filo2"])
            c.create_text(x0 - 10, Y(v), text=f"{v:g}%", anchor="e", fill=C["grigio"], font=F(9))
            v += passo
        presi_x = []
        for k, t in etichette:
            if all(abs(X(k) - p) > 44 for p in presi_x):
                presi_x.append(X(k))
                c.create_text(X(k), y1 + 14, text=t, anchor="n", fill=C["grigio"], font=F(9))
        linee, punti, sugg, fine = [], [], [], []
        if self.metrica:
            linee.append(([(x0, Y(50)), (x1, Y(50))], C["grigio"], 1.0, (5, 4)))
        for n, s in ss.items():
            col = self.colore(n)
            pts = [(X(k), Y(v)) for k, v in s]
            if len(pts) > 1:
                linee.append((pts, col, 3.0, None))
            punti += [(x, y, 4.5, col, C["fondo"], 1.5) for x, y in pts]
            et = nome_stagione if self.periodo == "season" else (lambda g: f"{g[8:10]}/{g[5:7]}")
            sugg += [(X(k), Y(v), f"{n} · {et(k)} · {v:.1f}%" + (" win rate" if self.metrica else " share")) for k, v in s]
            fine.append((pts[-1][1], n, col, s[-1][1]))
        im = DG.tratti(l, h, linee=linee, punti=punti)
        self.foto.append(im)
        c.create_image(0, 0, image=im, anchor="nw")
        presi = []
        for y, n, col, val in sorted(fine):
            while any(abs(y - p) < 30 for p in presi):
                y += 30
            presi.append(y)
            nome = n if len(n) <= 17 else n[:16] + "…"
            c.create_text(x1 + 12, y - 7, text=nome, anchor="w", fill=col, font=F(9, True))
            c.create_text(x1 + 12, y + 8, text=f"{val:.1f}%", anchor="w", fill=col, font=F(8))
        self.suggerimenti(c, sugg)

    def suggerimenti(self, c, punti):
        """Il nome e i numeri del punto sotto il puntatore."""
        def muovi(e):
            c.delete("sugg")
            vicino = min(punti, key=lambda p: (p[0] - e.x) ** 2 + (p[1] - e.y) ** 2, default=None)
            if not vicino or (vicino[0] - e.x) ** 2 + (vicino[1] - e.y) ** 2 > 196:
                return
            x, y, t = vicino
            ancora = "sw" if x < int(c.cget("width")) - 300 else "se"
            i = c.create_text(x + (10 if ancora == "sw" else -10), y - 10, text=t, anchor=ancora, fill=C["titolo"], font=self.F(9, True), tags="sugg")
            bb = c.bbox(i)
            r = c.create_rectangle(bb[0] - 7, bb[1] - 4, bb[2] + 7, bb[3] + 4, fill=C["cap"], outline=C["accento"], tags="sugg")
            c.tag_lower(r, i)
        c.bind("<Motion>", muovi)
        c.bind("<Leave>", lambda e: c.delete("sugg"))
