"""La finestra dettagliata di Analysis (12 nov 2026, Autore: «mettiamo un pulsante che permette a questa sezione di espandersi in una finestra piu' dettagliata dove
tutte le sottosezioni presenti qui in piccolo hanno maggiore dettaglio di dati. Pensa ai dati piu' utili per un giocatore competitivo»).

Dai nostri log (analisi_mazzo e matchup_log), sulle partite del mazzo, col filtro ALL GAMES / ON THE PLAY / ON THE DRAW suo:
- in testa: partite, win rate con l'intervallo di Wilson, play e draw, mulligan, turni medi delle vinte e delle perse;
- CARDS: ogni carta del mazzo, ordinabile: copie, vista (in quante partite e in che quota), lanciata, win rate quando la lanci e la differenza col mazzo, win rate
  quando la vedi, rimasta in mano (quota) e il win rate quando resta in mano. E' la tabella che un competitivo usa per decidere cosa tagliare;
- MATCHUPS: ogni archetipo incontrato (matchup_log), partite, record, win rate con l'intervallo, play, draw, mulligan, turni;
- MULLIGANS e GAME LENGTH: il win rate tenendo 7 carte, con un mulligan, con due o piu'; per lunghezza della partita (i turni di tutti e due);
- TREND: settimana per settimana, partite e win rate;
- le liste intere di Analysis: best performers, hard to cast, weak in losses, their cards, their combos, your clunky pairs.
Con meno di analisi_mazzo.POCHE partite: indizi, non dati, e lo dice.

    py -I -X utf8 Companion/App/Schede/Your_decks/analisi_dettaglio.py --prova
"""
import os, sys
_casa = os.path.dirname(os.path.abspath(__file__))
while not os.path.isfile(os.path.join(_casa, "percorsi.py")):
    _casa = os.path.dirname(_casa)
if _casa not in sys.path:
    sys.path.insert(0, _casa)
import percorsi  # noqa: E402,F401
import collections  # noqa: E402
import datetime  # noqa: E402
import threading  # noqa: E402

import analisi_mazzo as AM  # noqa: E402
import matchup_log as MU  # noqa: E402

ORDINI = (("cast", "WIN WHEN CAST"), ("delta", "VS DECK"), ("lanciate", "CAST"), ("viste", "SEEN"), ("blocc", "STUCK"), ("nome", "NAME"))
LUNGHEZZE = (("≤ 8 turns", 0, 8), ("9-11", 9, 11), ("12-14", 12, 14), ("15-17", 15, 17), ("18+", 18, 999))


def _wr(v, n):
    return v / n if n else None


def calcola(partite, lista, e_terra, partite_log=None, idx=None):
    """partite: quelle del mazzo (analisi_mazzo.partite_mazzo, gia' filtrate); lista: {nome: copie}; partite_log: le partite del log (per i matchup, i mulligan e
    i turni). -> dict(a, carte, matchup, mulligan, lunghezze, settimane, testa)."""
    a = AM.analizza(partite, lista, e_terra, idx=idx, righe=20)     # le liste intere fino a 20: oltre e' rumore di partite singole
    n, wr = a.get("con_dati") or 0, a.get("wr")
    carte = []
    for nome, q in sorted(lista.items()):
        if e_terra(nome):
            continue
        st = (a.get("carte") or {}).get(nome) or dict(nv=0, vv=0, nl=0, vl=0, nb=0, vb=0)
        w_l = _wr(st["vl"], st["nl"])
        carte.append(dict(nome=nome, copie=q, viste=st["nv"], q_viste=st["nv"] / n if n else 0, lanciate=st["nl"], q_lanciate=st["nl"] / n if n else 0,
                          cast=w_l, delta=(w_l - wr) if (w_l is not None and wr is not None) else None, w_viste=_wr(st["vv"], st["nv"]),
                          blocc=st["nb"] / st["nv"] if st["nv"] else 0, n_blocc=st["nb"], w_blocc=_wr(st["vb"], st["nb"])))
    ids = {p["matchId"] for p in partite}
    if partite_log is None:
        from dati_app import partite_dal_log
        partite_log, _n = partite_dal_log()
    recs = MU.records([p for p in partite_log if p.get("matchId") in ids])
    mull = collections.OrderedDict((k, [0, 0]) for k in ("Kept 7", "1 mulligan", "2+ mulligans"))
    lung = collections.OrderedDict((k, [0, 0]) for k, _a, _b in LUNGHEZZE)
    sett = collections.defaultdict(lambda: [0, 0])
    for r in recs:
        k = "Kept 7" if not r["mulligan"] else "1 mulligan" if r["mulligan"] == 1 else "2+ mulligans"
        mull[k][0] += 1; mull[k][1] += r["vinta"]
        if r["turni"]:
            kl = next(k for k, a_, b_ in LUNGHEZZE if a_ <= r["turni"] <= b_)
            lung[kl][0] += 1; lung[kl][1] += r["vinta"]
        g = datetime.date.fromisoformat(r["giorno"])
        lun = g - datetime.timedelta(days=g.weekday())
        sett[lun][0] += 1; sett[lun][1] += r["vinta"]
    tutte = MU._conta(recs) if recs else None
    return dict(a=a, n=n, wr=wr, carte=carte, matchup=MU.campo(recs), mulligan=mull, lunghezze=lung,
                settimane=sorted(sett.items())[-12:], testa=tutte, recs=len(recs))


class FinestraAnalisi:
    """La finestra: pagina e' la PaginaStandard (tabella, cella, flag_partenza, mazzo_arena); padre la finestra del mazzo."""

    def __init__(self, pagina, padre, chi, nome, lista, carte_db, partenza=None):
        import dati_mazzo as DM
        self.p, self.tk, self.F = pagina, pagina.tk, pagina.F
        self.nome, self.lista, self.carte_db = nome, lista, carte_db or {}
        self.e_terra = lambda n: DM.e_terra(n, self.carte_db)
        self.am = pagina.mazzo_arena(chi)
        self.partenza, self.ordine = partenza, "cast"
        tk = self.tk
        from tema import CI as C
        self.C = C
        f = self.fin = tk.Toplevel(padre); f.withdraw()
        f.title(f"Analysis · {nome}"); f.configure(bg=C["fondo"])
        try:
            f.transient(padre)
        except Exception:
            pass
        L = min(1400, f.winfo_screenwidth() - 80); H = min(980, f.winfo_screenheight() - 80)
        f.geometry(f"{L}x{H}+{max(0, padre.winfo_rootx() - 60)}+{max(0, padre.winfo_rooty() - 30)}")
        f.bind("<Escape>", lambda e: f.destroy())
        testa = tk.Frame(f, bg=C["cap"]); testa.pack(fill="x")
        tk.Label(testa, text=f"ANALYSIS · {nome.upper()}", bg=C["cap"], fg=C["titolo"], font=self.F(13, True)).pack(side="left", padx=16, pady=10)
        self.l_stato = tk.Label(testa, text="", bg=C["cap"], fg=C["grigio"], font=self.F(8)); self.l_stato.pack(side="right", padx=16)
        cv = self.cv = tk.Canvas(f, bg=C["scheda"], highlightthickness=0); cv.pack(fill="both", expand=True)
        self.corpo = tk.Frame(cv, bg=C["scheda"], padx=18, pady=12)
        win = cv.create_window(0, 0, window=self.corpo, anchor="nw")
        self.corpo.bind("<Configure>", lambda e: cv.configure(scrollregion=(0, 0, 0, self.corpo.winfo_reqheight() + 20)))
        cv.bind("<Configure>", lambda e: cv.itemconfigure(win, width=e.width))
        f.bind("<MouseWheel>", lambda e: cv.yview_scroll(-1 if e.delta > 0 else 1, "units"))
        self.dati = None
        self.ricalcola()
        f.deiconify()

    def partite(self, partenza="?"):
        """Le partite del mazzo dal log, col filtro: «primo» dice chi ha cominciato (None: non si sa, fuori dai due filtri)."""
        partenza = self.partenza if partenza == "?" else partenza
        pp = AM.partite_mazzo(self.am["id"]) if self.am else []
        return pp if not partenza else [x for x in pp if x.get("primo") is (partenza == "play")]

    def ricalcola(self):
        """I conti in un filo (le partite del log si leggono una volta), poi il disegno."""
        self.l_stato.configure(text="Reading your logs…")
        box = {}

        def fa():
            try:
                box["d"] = calcola(self.partite(), self.lista, self.e_terra)
            except Exception as e:      # noqa: BLE001 - la finestra lo dice
                box["e"] = str(e)
        threading.Thread(target=fa, daemon=True).start()

        def guarda():
            if not self.fin.winfo_exists():
                return
            if not box:
                return self.fin.after(80, guarda)
            if "e" in box:
                self.l_stato.configure(text="Could not read the logs: " + box["e"])
                return
            self.dati = box["d"]
            self.disegna()
        self.fin.after(80, guarda)

    def filtra(self, v):
        self.partenza = v
        self.ricalcola()

    def scegli_ordine(self, k):
        self.ordine = k
        self.disegna()

    # ------------------------------------------------ il disegno
    def disegna(self):
        tk, F, C, p = self.tk, self.F, self.C, self.p
        import widget
        widget.svuota(self.corpo)
        d = self.dati
        n = d["n"]
        self.flag = p.flag_partenza(self.corpo, self.partenza, self.filtra, len(self.partite(None)), len(self.partite("play")), len(self.partite("draw")))
        self.l_stato.configure(text=f"{n} games with their cards in your Arena logs" + ("  ·  few games: hints, not data" if n < AM.POCHE else ""))
        pct = lambda x: "-" if x is None else f"{round(100 * x)}%"
        wr_col = lambda x, rif=0.5: C["muto"] if x is None else C["verde_t"] if x > rif + 0.005 else C["rosso_t"] if x < rif - 0.005 else C["testo"]

        def titolo(t, sotto=""):
            r = tk.Frame(self.corpo, bg=C["scheda"]); r.pack(fill="x", pady=(16, 4))
            tk.Label(r, text=t, bg=C["scheda"], fg=C["titolo"], font=F(11, True)).pack(side="left")
            if sotto:
                tk.Label(r, text=sotto, bg=C["scheda"], fg=C["muto"], font=F(8)).pack(side="left", padx=(10, 0))
            return r
        c_ = p.cella
        # in testa
        t = d["testa"]
        if t:
            voci = [("games vs players", f"{t['partite']}", None, f"{t['vinte']} won · {t['perse']} lost · no Sparky"),
                    ("win rate", pct(t["vinte"] / t["partite"]), wr_col(t["vinte"] / t["partite"]), f"95%: {t['basso']}-{t['alto']}%"),
                    ("on the play", pct(_wr(t["play"][1], t["play"][0])), wr_col(_wr(t["play"][1], t["play"][0])), f"{t['play'][1]}-{t['play'][0] - t['play'][1]}"),
                    ("on the draw", pct(_wr(t["draw"][1], t["draw"][0])), wr_col(_wr(t["draw"][1], t["draw"][0])), f"{t['draw'][1]}-{t['draw'][0] - t['draw'][1]}"),
                    ("mulligans", f"{t['mulligan']}%" if t["mulligan"] is not None else "-", None, "of games"),
                    ("wins on", f"T{t['turni_vinte']}" if t["turni_vinte"] else "-", None, "game turns, both players"),
                    ("losses on", f"T{t['turni_perse']}" if t["turni_perse"] else "-", None, "game turns, both players")]
            p.tessere(self.corpo, voci, colonne=7)
        # CARDS, ordinabile
        r = titolo("CARDS", "every spell of the deck in your games · sort by")
        cs = tk.Canvas(r, height=24, bg=C["scheda"], highlightthickness=0, cursor="hand2"); cs.pack(side="left", padx=(8, 0))
        x = 0
        cs.voci = []
        for k, testo in ORDINI:
            on = k == self.ordine
            lg = 16 + 7 * len(testo)
            cs.create_rectangle(x, 2, x + lg, 22, fill=C["sel"] if on else C["scheda"], outline=C["accento"] if on else C["filo"])
            cs.create_text(x + lg / 2, 12, text=testo, fill=C["accento"] if on else C["grigio"], font=F(7, True))
            cs.voci.append((x, x + lg, k)); x += lg + 4
        cs.configure(width=x)
        cs.bind("<Button-1>", lambda e: next((self.scegli_ordine(k) for x0, x1, k in cs.voci if x0 <= e.x <= x1), None))
        self.c_ordine = cs
        poche = lambda z: z["lanciate"] < AM.MIN_LANCIATE       # lanciata in meno di 3 partite: in fondo e in grigio quando si ordina per win rate
        chiave = {"cast": lambda z: (poche(z), z["cast"] is None, -(z["cast"] or 0), -z["lanciate"]), "delta": lambda z: (poche(z), z["delta"] is None, -(z["delta"] or 0)),
                  "lanciate": lambda z: -z["lanciate"], "viste": lambda z: -z["viste"], "blocc": lambda z: (-z["blocc"], -z["n_blocc"]), "nome": lambda z: z["nome"]}[self.ordine]
        carte = sorted(d["carte"], key=chiave)
        self.righe_carte = [z["nome"] for z in carte]
        wr = d["wr"]
        righe = [[c_(z["nome"], C["muto"] if poche(z) else C["titolo"], not poche(z), lato="left"), c_(f"{z['copie']}"), c_(f"{z['viste']} · {pct(z['q_viste'])}"), c_(f"{z['lanciate']} · {pct(z['q_lanciate'])}"),
                  c_(pct(z["cast"]), wr_col(z["cast"], wr or 0.5), True), c_("-" if z["delta"] is None else f"{'+' if z['delta'] >= 0 else ''}{round(100 * z['delta'])}",
                                                                              wr_col(z["cast"], wr or 0.5), True),
                  c_(pct(z["w_viste"]), wr_col(z["w_viste"], wr or 0.5)), c_(f"{z['n_blocc']} · {pct(z['blocc'])}", C["arancio"] if z["blocc"] >= 0.5 else None),
                  c_(pct(z["w_blocc"]), wr_col(z["w_blocc"], wr or 0.5))] for z in carte]
        if righe:
            p.tabella(self.corpo, [("card", "w"), ("copies", "e"), ("seen", "e"), ("cast", "e"), ("win when cast", "e"), ("vs deck", "e"), ("win when seen", "e"),
                                   ("stuck in hand", "e"), ("win when stuck", "e")], righe, allarga=0)
        # MATCHUPS
        titolo("MATCHUPS", f"their deck from the cards they showed · under {MU.MIN_PARTITE} games it is a hint")
        mu = d["matchup"]
        if mu:
            p.tabella(self.corpo, [("their deck", "w"), ("share", "e"), ("games", "e"), ("record", "e"), ("win rate", "e"), ("95% range", "e"), ("play", "e"), ("draw", "e"),
                                   ("mulligans", "e"), ("wins on", "e"), ("losses on", "e")],
                      [[c_(x["suo"], C["muto"] if x["poche"] else C["titolo"], not x["poche"], lato="left"), c_(f"{x['quota']}%"), c_(f"{x['partite']}"),
                        c_(f"{x['vinte']}-{x['perse']}"), c_(f"{round(x['wr'])}%", C["muto"] if x["poche"] else wr_col(x["wr"] / 100), True),
                        c_(f"{x['basso']}-{x['alto']}%", C["grigio"]), c_(self.pd(x["play"])), c_(self.pd(x["draw"])),
                        c_(f"{round(x['mulligan'])}%" if x["mulligan"] is not None else "-"), c_(f"T{x['turni_vinte']}" if x["turni_vinte"] else "-"),
                        c_(f"T{x['turni_perse']}" if x["turni_perse"] else "-")] for x in mu])
        else:
            tk.Label(self.corpo, text="No matchups yet", bg=C["scheda"], fg=C["muto"], font=F(8), anchor="w").pack(fill="x")
        # MULLIGANS e GAME LENGTH, affiancati
        due = tk.Frame(self.corpo, bg=C["scheda"]); due.pack(fill="x")
        sx = tk.Frame(due, bg=C["scheda"]); sx.pack(side="left", fill="x", expand=True, padx=(0, 20))
        dx = tk.Frame(due, bg=C["scheda"]); dx.pack(side="left", fill="x", expand=True)
        for padre, tit, sotto, voci in ((sx, "MULLIGANS", "the hand you kept", d["mulligan"]), (dx, "GAME LENGTH", "game turns, both players", d["lunghezze"])):
            r_ = tk.Frame(padre, bg=C["scheda"]); r_.pack(fill="x", pady=(16, 4))
            tk.Label(r_, text=tit, bg=C["scheda"], fg=C["titolo"], font=F(11, True)).pack(side="left")
            tk.Label(r_, text=sotto, bg=C["scheda"], fg=C["muto"], font=F(8)).pack(side="left", padx=(10, 0))
            p.tabella(padre, [("", "w"), ("games", "e"), ("record", "e"), ("win rate", "e")],
                      [[c_(k, C["titolo"], True, lato="left"), c_(f"{nv[0]}"), c_(f"{nv[1]}-{nv[0] - nv[1]}"), c_(pct(_wr(nv[1], nv[0])), wr_col(_wr(nv[1], nv[0])), True)]
                       for k, nv in voci.items()])
        # TREND
        titolo("TREND", "week by week")
        if d["settimane"]:
            p.tabella(self.corpo, [("week of", "w"), ("games", "e"), ("record", "e"), ("win rate", "e")],
                      [[c_(f"{g:%d %b %Y}", C["titolo"], True, lato="left"), c_(f"{nv[0]}"), c_(f"{nv[1]}-{nv[0] - nv[1]}"), c_(pct(_wr(nv[1], nv[0])), wr_col(_wr(nv[1], nv[0])), True)]
                       for g, nv in reversed(d["settimane"])])
        # le liste intere di Analysis
        a = d["a"]
        liste = [("BEST PERFORMERS", "win rate in the games you cast it", [("card", "w"), ("cast", "e"), ("win rate", "e"), ("vs deck", "e")],
                  [[c_(x["nome"], C["titolo"], True, lato="left"), c_(f"{x['n']}"), c_(pct(x["wr"]), wr_col(x["wr"], wr or 0.5), True), c_(f"{'+' if x['delta'] >= 0 else ''}{round(100 * x['delta'])}")]
                   for x in a["migliori"]]),
                 ("HARD TO CAST", "seen, then never cast in that game", [("card", "w"), ("stuck", "e"), ("of seen", "e"), ("win rate", "e")],
                  [[c_(x["nome"], C["titolo"], True, lato="left"), c_(f"{x['bloccata']}/{x['viste']}"), c_(pct(x["quota"])), c_(pct(x["wr"]), wr_col(x["wr"], wr or 0.5))]
                   for x in a["fatica"]]),
                 ("WEAK IN YOUR LOSSES", "your cards that win less than the deck when they show up", [("card", "w"), ("seen", "e"), ("record", "e"), ("vs deck", "e")],
                  [[c_(x["nome"], C["titolo"], True, lato="left"), c_(f"{x['n']}"), c_(f"{x['v']}-{x['perse']}"), c_(f"{round(100 * x['delta'])}", C["rosso_t"])] for x in a["perse"]]),
                 ("THEIR CARDS THAT BEAT YOU", "more losses than the deck loses anyway", [("card", "w"), ("seen", "e"), ("losses", "e"), ("loss rate", "e")],
                  [[c_(x["nome"], C["titolo"], True, lato="left"), c_(f"{x['n']}"), c_(f"{x['perse']}", C["rosso_t"]), c_(pct(x["quota"]), C["rosso_t"])] for x in a["sue"]]),
                 ("UNPLAYABLE · THEIR COMBOS", "two of their cards together, worse than each alone", [("cards", "w"), ("losses", "e")],
                  [[c_(" + ".join(x["carte"]), C["titolo"], True, lato="left"), c_(f"{x['perse']}/{x['n']}", C["rosso_t"])] for x in a["combo_sue"]]),
                 ("UNPLAYABLE · YOUR CLUNKY PAIRS", "stuck in hand together", [("cards", "w"), ("losses", "e")],
                  [[c_(" + ".join(x["carte"]), C["titolo"], True, lato="left"), c_(f"{x['perse']}/{x['n']}", C["rosso_t"])] for x in a["combo_mie"]])]
        for tit, sotto, intest, righe_ in liste:
            titolo(tit, sotto)
            if righe_:
                p.tabella(self.corpo, intest, righe_)
            else:
                tk.Label(self.corpo, text="Nothing stands out yet", bg=C["scheda"], fg=C["muto"], font=F(8), anchor="w").pack(fill="x")
        tk.Label(self.corpo, text="Seen = out of the library (drawn, milled or surveiled). Cast = cast or played. Stuck = seen and never cast in that game. Win rates "
                 "against the deck's own win rate. Games since 22 Sep 2026, from your Player.log.", bg=C["scheda"], fg=C["muto"], font=F(7), anchor="w",
                 justify="left", wraplength=1100).pack(fill="x", pady=(16, 0))

    @staticmethod
    def pd(x):
        n, v = x
        return f"{v}-{n - v}" if n else "-"


def prova():
    """I conti su partite finte: la tabella delle carte, i mulligan, la lunghezza, le settimane; le negative."""
    import tempfile
    casi = []
    partite = [dict(matchId=f"m{i}", vinta=i % 3 != 0, primo=True) for i in range(9)]
    idx = {f"m{i}": dict(esito="vinta" if i % 3 != 0 else "persa", viste={"Asso", "Muro"}, lanciate={"Asso"} if i < 6 else set(), sue=set()) for i in range(9)}
    log = [dict(matchId=f"m{i}", evento="Ladder", vinta=i % 3 != 0, inizio=int(datetime.datetime(2026, 11, 2 + i).timestamp() * 1000), inizia=1, seat=1,
                turni=7 + i, mani=[[1]] * (1 + (i == 4)), sue=[], carte=[], nome_mazzo="X") for i in range(9)]
    d = calcola(partite, {"Asso": 4, "Muro": 2, "Plains": 18}, lambda n: n == "Plains", partite_log=log, idx=idx)
    asso = next(z for z in d["carte"] if z["nome"] == "Asso")
    casi.append(("carte: Asso vista 9, lanciata 6 (vince 4 su 6), rimasta in mano 3", asso["viste"] == 9 and asso["lanciate"] == 6 and abs(asso["cast"] - 4 / 6) < 1e-9
                 and asso["n_blocc"] == 3))
    casi.append(("negativa: le terre non sono nella tabella delle carte", all(z["nome"] != "Plains" for z in d["carte"])))
    casi.append(("mulligan: 8 tenute da 7, 1 con un mulligan", d["mulligan"]["Kept 7"][0] == 8 and d["mulligan"]["1 mulligan"][0] == 1 and d["mulligan"]["2+ mulligans"][0] == 0))
    casi.append(("lunghezza: le 9 partite nelle fasce", sum(v[0] for v in d["lunghezze"].values()) == 9 and d["lunghezze"]["≤ 8 turns"][0] == 2))
    casi.append(("settimane: le partite per lunedi'", sum(v[0] for _g, v in d["settimane"]) == 9 and all(g.weekday() == 0 for g, _v in d["settimane"])))
    casi.append(("in testa: 6-3 e l'intervallo", d["testa"]["vinte"] == 6 and d["testa"]["perse"] == 3 and d["testa"]["basso"] < 66.7 < d["testa"]["alto"]))
    vuoto = calcola([], {"Asso": 4}, lambda n: False, partite_log=[], idx={})
    casi.append(("negativa: senza partite niente numeri, niente errori", vuoto["n"] == 0 and vuoto["testa"] is None and not vuoto["matchup"]))
    _ = tempfile
    for n, v in casi:
        print(("ok    " if v else "ROSSO ") + n)
    ok = sum(1 for _n, v in casi if v)
    print(f"{ok}/{len(casi)}")
    return ok == len(casi)


if __name__ == "__main__":
    sys.exit(0 if prova() else 1)
