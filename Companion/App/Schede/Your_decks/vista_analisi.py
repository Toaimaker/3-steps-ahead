"""La sezione Analysis della finestra di un mazzo: le tabelle di analisi_mazzo.py (Autore, 10 nov 2026: «serve un tool che permetta di fare analisi vera del mazzo»,
«questi dati devono venire dal nostro log non da untapped»). Si calcola in un filo, la finestra si apre subito e la sezione si riempie quando e' pronta. I nomi delle carte
mostrano la carta in hover, come le capsule."""
import threading

import analisi_mazzo as AM
import dati_mazzo as DM

from tema import CI as C


class VistaAnalisi:
    """La sezione Analysis (mixin di PaginaStandard)."""

    def sezione_analisi(self, padre, tipo, chi, main, side, comandante, compagno, carte_db, lista, dopo=None, partenza=None):
        """Riempie padre (il corpo della sezione) con l'analisi del mazzo; i mazzi che non sono tuoi su Arena (meta, wishlist, build) non hanno partite."""
        tk, F = self.tk, self.F
        am = self.mazzo_arena(chi) if tipo == "mio" else None
        if not am:
            tk.Label(padre, text="The analysis reads the games of this deck in your Arena logs: play it on Arena and it fills in.", bg=C["scheda"], fg=C["grigio"],
                     font=F(8), anchor="w", justify="left", wraplength=520).pack(fill="x")
            return
        attesa = tk.Label(padre, text="Reading your logs…", bg=C["scheda"], fg=C["grigio"], font=F(8), anchor="w"); attesa.pack(fill="x")
        lista_mazzo = {**main, **side, **comandante, **compagno}
        box = {}

        def calcola():
            try:
                pp = AM.partite_mazzo(am["id"])
                if partenza:        # il filtro on the play / on the draw della finestra (10 nov 2026): le partite di cui il log non dice chi comincia restano fuori
                    pp = [p for p in pp if p.get("primo") is (partenza == "play")]
                box["a"] = AM.analizza(pp, lista_mazzo, lambda n: DM.e_terra(n, carte_db))
            except Exception as e:      # noqa: BLE001 - la sezione dice cosa e' andato storto, la finestra resta
                box["errore"] = str(e)
        threading.Thread(target=calcola, daemon=True).start()

        def guarda():
            if not padre.winfo_exists():
                return
            if "a" not in box and "errore" not in box:
                padre.after(80, guarda)
                return
            attesa.destroy()
            if "errore" in box:
                tk.Label(padre, text=f"The analysis could not read the logs: {box['errore']}", bg=C["scheda"], fg=C["rosso_t"], font=F(8), anchor="w").pack(fill="x")
            else:
                self.disegna_analisi(padre, box["a"], lista, dopo)
            if dopo:
                dopo()
        padre.after(80, guarda)

    def disegna_analisi(self, padre, a, lista, dopo=None):
        """Ogni categoria e' una mini tendina, chiusa di partenza, col primo della lista nella testata (Autore, 10 nov 2026: «metti ogni categoria in delle mini
        tendine espandibili cosi' non abbiamo tutti i dati in un colpo solo ma possiamo aprire dopo aver aperto analisi quelli che ci interessano»)."""
        tk, F = self.tk, self.F
        self.ultima_analisi = a

        def pct(x):
            return f"{round(100 * x)}%"

        def corto(n, k=30):
            return n if len(n) <= k else n[:k - 1].rstrip() + "…"

        # le celle dichiarate (tabella_tela, 11 nov 2026): la tabella si disegna su una tela; la carta grande in hover la mette la riga (carte_in_hover)
        def nome(n):
            c_ = self.cella_righe([(corto(n), C["titolo"], True, 8)])
            c_.carte = [n]
            return c_

        def coppia(cc):
            c_ = self.cella_righe([(corto(n), C["titolo"], True, 8) for n in cc])
            c_.carte = list(cc)
            return c_

        def carte_in_hover(righe_t, righe_c):
            """Sopra una riga, la carta grande della carta su cui sta il puntatore (in una coppia: la riga di sopra o quella di sotto)."""
            if lista is None:
                return
            for r, celle in zip(righe_t, righe_c):
                carte = getattr(celle[0], "carte", None)
                if not carte or not hasattr(r, "cliccabile"):
                    continue

                def sopra(e, r=r, carte=carte):
                    n = carte[min(len(carte) - 1, int(e.y / max(r.alta, 1) * len(carte)))]
                    if getattr(r, "in_hover", None) != n:
                        r.in_hover = n
                        lista.entra(r, n)
                r.cursore = "hand2"
                r.bind("<Motion>", sopra)
                r.bind("<Leave>", lambda e, r=r: (setattr(r, "in_hover", None), lista.esci()))
                r.bind("<Destroy>", lista.esci, add=True)

        def scarto(d):
            return self.cella(f"{'+' if d >= 0 else ''}{round(100 * d)}", C["verde_t"] if d > 0.005 else C["rosso_t"] if d < -0.005 else C["testo"], True)

        def wr_col(x):
            return C["verde_t"] if x > 0.5 else C["rosso_t"] if x < 0.5 else C["testo"]

        def blocco(chiave, titolo, spiega, intest, righe, primo, vuoto="Nothing stands out yet"):
            """Una categoria: la mini tendina, chiusa la prima volta; nella testata il primo della lista, o «none»."""
            corpo = self.sezione_tendina(padre, "analisi_" + chiave, titolo, corto(primo, 34) if righe else "none", aperta=False, dopo=dopo, mini=True, spiega=spiega)
            if righe:        # la tabella si fa alla prima apertura della mini tendina (partono chiuse)
                corpo.poi(lambda: carte_in_hover(self.tabella(corpo, intest, righe, allarga=0), righe))
            else:
                tk.Label(corpo, text=vuoto, bg=C["scheda"], fg=C["muto"], font=F(8), anchor="w", pady=2).pack(fill="x")

        def prima(lista_, f):
            return f(lista_[0]) if lista_ else ""

        if not a["con_dati"]:
            tk.Label(padre, text=f"No game of this deck has its cards in the logs yet ({a['n']} games found).", bg=C["scheda"], fg=C["grigio"], font=F(8),
                     anchor="w").pack(fill="x")
            return
        testa = tk.Frame(padre, bg=C["scheda"]); testa.pack(fill="x")
        tk.Label(testa, text=f"{a['con_dati']} games from your Arena logs", bg=C["scheda"], fg=C["testo"], font=F(8, True), pady=0).pack(side="left")
        tk.Label(testa, text=f"deck win rate {pct(a['wr'])}", bg=C["scheda"], fg=wr_col(a["wr"]), font=F(8, True), pady=0).pack(side="right")
        if a["con_dati"] < AM.POCHE:
            tk.Label(padre, text="Few games: read these as hints, not data.", bg=C["scheda"], fg=C["arancio"], font=F(7, True), anchor="w").pack(fill="x")
        tk.Frame(padre, bg=C["scheda"], height=6).pack(fill="x")
        blocco("migliori", "Best performers", "win rate in the games you cast it",
               [("card", "w"), ("cast", "e"), ("win rate", "e"), ("vs deck", "e")],
               [[nome(x["nome"]), self.cella(f"{x['n']}"), self.cella(pct(x["wr"]), wr_col(x["wr"]), True), scarto(x["delta"])] for x in a["migliori"]],
               prima(a["migliori"], lambda x: f"{x['nome']} · {pct(x['wr'])}"))
        blocco("fatica", "Hard to cast", "seen, then never cast in that game",
               [("card", "w"), ("stuck", "e"), ("of seen", "e"), ("win rate", "e")],
               [[nome(x["nome"]), self.cella(f"{x['bloccata']}/{x['viste']}"), self.cella(pct(x["quota"]), C["arancio"] if x["quota"] >= 0.5 else C["testo"], True),
                 self.cella(pct(x["wr"]), wr_col(x["wr"]), True)] for x in a["fatica"]],
               prima(a["fatica"], lambda x: f"{x['nome']} · {x['bloccata']}/{x['viste']}"))
        blocco("perse", "Weak in your losses", "your cards that win less than the deck when they show up",
               [("card", "w"), ("seen", "e"), ("record", "e"), ("vs deck", "e")],
               [[nome(x["nome"]), self.cella(f"{x['n']}"), self.cella(f"{x['v']}-{x['perse']}", C["rosso_t"], True), scarto(x["delta"])] for x in a["perse"]],
               prima(a["perse"], lambda x: f"{x['nome']} · {x['v']}-{x['perse']}"))
        blocco("sue", "Their cards that beat you", "more losses than the deck loses anyway",
               [("card", "w"), ("seen", "e"), ("losses", "e"), ("loss rate", "e")],
               [[nome(x["nome"]), self.cella(f"{x['n']}"), self.cella(f"{x['perse']}", C["rosso_t"], True), self.cella(pct(x["quota"]), C["rosso_t"], True)] for x in a["sue"]],
               prima(a["sue"], lambda x: f"{x['nome']} · {x['perse']}/{x['n']}"))
        blocco("combo_sue", "Unplayable · their combos", "two of their cards together, worse than each alone",
               [("cards", "w"), ("losses", "e")],
               [[coppia(x["carte"]), self.cella(f"{x['perse']}/{x['n']}", C["rosso_t"], True)] for x in a["combo_sue"]],
               prima(a["combo_sue"], lambda x: f"{x['carte'][0]} + …"))
        blocco("combo_mie", "Unplayable · your clunky pairs", "stuck in hand together",
               [("cards", "w"), ("losses", "e")],
               [[coppia(x["carte"]), self.cella(f"{x['perse']}/{x['n']}", C["rosso_t"], True)] for x in a["combo_mie"]],
               prima(a["combo_mie"], lambda x: f"{x['carte'][0]} + …"))
        tk.Label(padre, text="Seen = out of the library (drawn, milled or surveiled). Cast = cast or played. One row per card, not per copy; lands are left out. "
                 "Games since 22 Sep 2026, from your Player.log.", bg=C["scheda"], fg=C["muto"], font=F(7), anchor="w", justify="left", wraplength=560).pack(fill="x", pady=(10, 0))
