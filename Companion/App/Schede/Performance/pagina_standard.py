"""Performance, modo Standard: win rate in classificata, numeri, mazzi, meta e farming."""
import collections
import sys
import webbrowser

from dati_app import EVENTI_BASE, EVENTI_TUTTI, FARMING, FORMATI_COSTRUITI, MOSTRA_MAZZI, SUPER_FORMATO, farming, mazzi_costruiti, meta_formato, saldo_partite
from esporta_mazzo import EsportaMazzo
from finestra_mazzo import FinestraMazzo
from mani_mazzo import ManiMazzo
from pagina_base import Pagina
from sezioni_mazzo import SezioniMazzo
from vista_analisi import VistaAnalisi
from scheda_mazzo import SchedaMazzo
from tema import CI as C, PERSA, VINTA
from widget import Tendina


class PaginaStandard(FinestraMazzo, SchedaMazzo, SezioniMazzo, VistaAnalisi, ManiMazzo, EsportaMazzo, Pagina):

    """Standard, impaginata come Limited: a sinistra il grafico del win rate in classificata, a destra i tuoi numeri e la
    scheda «Mazzi» con le tendine «Mostra» (i tuoi mazzi, il meta) e «Formato»."""

    CON_EVENTI = True

    def filtra_eventi(self, tutte):
        """Le partite dell'evento scelto. In testa il default di sempre, classificata e libera; poi ogni evento in cui hai giocato, dal piu' giocato."""
        conti = collections.Counter(x["evento"] for x in tutte)
        opz = [EVENTI_BASE] + [n for n, _ in conti.most_common()] + [EVENTI_TUTTI]
        if opz != self.opzioni_ev:
            self.opzioni_ev = opz
            self.ev.opzioni(opz, lambda o: self.disegna())
        if self.ev.get() not in opz:
            self.ev.set(EVENTI_BASE)
        e = self.ev.get()
        scelte = tutte if e == EVENTI_TUTTI else [x for x in tutte if x["ev"] in ("Ladder", "Play")] if e == EVENTI_BASE else [x for x in tutte if x["evento"] == e]
        if e != "Constructed Event":
            self.sub.fr.pack_forget()
            return scelte
        nomi = lambda r: r.replace("_", " ")
        voci = ["All"] + sorted({x["raw"] for x in scelte}, reverse=True)
        if voci != self.opzioni_sub:
            self.opzioni_sub = voci
            self.sub.opzioni(voci, lambda o: self.disegna(), etichette={v: nomi(v) for v in voci})
        if self.sub.get() not in voci:
            self.sub.set("All")
        self.sub.fr.pack(side="left", padx=(12, 0), after=self.ev.fr)
        return scelte if self.sub.get() == "All" else [x for x in scelte if x["raw"] == self.sub.get()]

    def __init__(self, tk, padre, F, mana):
        super().__init__(tk, padre, F, mana)
        # il menu degli eventi, accanto a quello dell'espansione, come il Format di Limited (Autore, 6 nov 2026: «come per limited anche per standard metti la tendina eventi nella scheda performance»)
        self.ev = None
        if self.CON_EVENTI:
            self.ev = Tendina(tk, self.barra_menu, "Event", F, larga=200); self.ev.fr.pack(side="left", padx=(12, 0))
            self.ev.set(EVENTI_BASE)
            self.opzioni_ev = []
            # dentro un evento, quale: i nomi veri su Arena (Autore, 6 nov 2026: «aggiungere una sottotendina a constructed events che ci fa scegliere quale evento tra i constructed»)
            self.sub = Tendina(tk, self.barra_menu, "Which event", F, larga=220)
            self.opzioni_sub = []
        self.b_and, self.v_and = self.scheda("Ranked win rate", col=0)
        self.tit_and = self.cap_tit
        self.b_and.v_testata = self.v_and
        self.b_num, self.v_num = self.scheda("Your numbers", col=1)
        b, self.v_maz = self.scheda("Decks", espandi=True, col=1)
        menu = tk.Frame(b, bg=C["scheda"]); menu.pack(fill="x", pady=(0, 8))
        self.mostra = Tendina(tk, menu, "Show", F, larga=170, bg=C["scheda"]); self.mostra.fr.pack(side="left")
        self.formato = Tendina(tk, menu, "Format", F, larga=170, bg=C["scheda"]); self.formato.fr.pack(side="left", padx=(12, 0))
        self.mostra.opzioni(MOSTRA_MAZZI, lambda o: self.disegna_mazzi())   # «Farming» si aggiunge in disegna() se ha dati
        self.formato.opzioni(FORMATI_COSTRUITI, lambda o: self.disegna_mazzi())
        self.mostra.set(MOSTRA_MAZZI[0]); self.formato.set(FORMATI_COSTRUITI[0])
        if "--mostra" in sys.argv:        # collaudo: la lista si apre su «Meta» o «Farming»
            self.mostra.set(sys.argv[sys.argv.index("--mostra") + 1])
        self.b_maz = tk.Frame(b, bg=C["scheda"]); self.b_maz.pack(fill="both", expand=True)
        self.dati = None; self.pp = []; self.aperto = None; self.premi = None; self.farm = []
        self.fin = self.det = None      # la finestra del mazzo aperto

    def aggiorna(self, dati=None):
        if dati is not None:
            self.dati = dati
        self.ridisegna()

    def mazzo_arena(self, chi):
        """Il mazzo di Arena dietro a una scheda: solo in Your decks (PaginaMazzi). Da Performance i mazzi restano quelli delle partite."""
        return None

    def disegna(self):
        tk, F = self.tk, self.F
        d = self.dati
        tutte = (d or {}).get("partite") or []
        e_sc = None
        if self.ev is not None:
            tutte = self.filtra_eventi((d or {}).get("tutte") or tutte)
            e_sc = self.ev.get()
        solo_lega = e_sc in (None, EVENTI_BASE, "Ranked")       # la lega esiste solo in classificata: il grafico di sempre
        self.tit_and.configure(text="RANKED WIN RATE" if solo_lega else f"WIN RATE · {e_sc.upper()}")
        ordine = {}
        for x in tutte:
            ordine[x["set"]] = max(ordine.get(x["set"], 0), x["quando"].timestamp())
        sets = sorted(ordine, key=lambda k: -ordine[k])
        self.opzioni_menu(sets, sets[0] if sets else self.TUTTE)
        fs = self.filtro()
        pp = self.pp = [x for x in tutte if fs is None or x["set"] == fs]
        self.v_num.set(fs or "all sets")
        if pp:
            w = sum(x["vinta"] for x in pp); n = len(pp); l = n - w
            lad = [x for x in pp if x["ev"] == "Ladder"]; wl = sum(x["vinta"] for x in lad)
            lib = [x for x in pp if x["ev"] == "Play"]; wp = sum(x["vinta"] for x in lib)
            rango = next((x["rango"] for x in reversed(lad) if x["rango"]), None)
            voci = [("win rate", f"{round(100 * w / n)}%", VINTA if w / n >= 0.5 else PERSA), ("games", str(n), None),
                    ("rank", rango or "-", C["acciaio"], "", self.logo_rango(rango)),
                    ("wins", str(w), VINTA), ("losses", str(l), PERSA), ("win/loss ratio", f"{w / l:.2f}" if l else "-", None),
                    (f"ranked, {wl}-{len(lad) - wl}", f"{round(100 * wl / len(lad))}%" if lad else "-", None),
                    (f"play, {wp}-{len(lib) - wp}", f"{round(100 * wp / len(lib))}%" if lib else "-", None)]
            self.griglia(self.b_num, voci)
        else:
            self.svuota(self.b_num)
            tk.Label(self.b_num, text="Numbers show up once there is data", bg=C["scheda"], fg=C["grigio"],
                     font=F(9), anchor="w").pack(fill="x")
        self.grafico(self.b_and, *saldo_partite(pp, "Ladder" if solo_lega else None), vuoto="No ranked games" if solo_lega else "No games", altezza=640, tipo_lega="constructed")
        self.farm = farming(self.premi)
        self.mostra.opzioni(MOSTRA_MAZZI + ((FARMING,) if self.farm else ()), lambda o: self.disegna_mazzi())
        if self.mostra.get() not in self.mostra.voci:
            self.mostra.set(MOSTRA_MAZZI[0])
        if "--mazzo" in sys.argv and not getattr(self, "_mazzo_argv", False) and pp:   # collaudo: si apre su un mazzo
            self._mazzo_argv = True; self.aperto = ("mio", sys.argv[sys.argv.index("--mazzo") + 1].replace("_", " "))
        self.disegna_mazzi()
        if self.aperto:
            self.disegna_dettaglio()

    def disegna_mazzi(self):
        """La lista dei mazzi della tendina «Mostra»: i tuoi (gli otto piu' giocati, per win rate), il meta del formato o
        il farming (i tuoi mazzi negli eventi costruiti a premi, prima chi ha reso di piu' in gemme)."""
        tk, F = self.tk, self.F
        self.svuota(self.b_maz)
        fmt = self.formato.get()
        if self.mostra.get() == FARMING:
            self.v_maz.set("all constructed events · click a deck")
            if not self.farm:
                tk.Label(self.b_maz, text="No prizes from constructed events", bg=C["scheda"], fg=C["grigio"], font=F(9), anchor="w").pack(fill="x")
                return
            pt = lambda x: f"{x:,}"

            ev = [i for i, r in enumerate(self.farm) if self.aperto and self.aperto[0] == "farm" and self.aperto[1]["nome"] == r["nome"]]
            righe = []
            for r in self.farm:
                netto = r["gemme_vinte"] - r["gemme_spese"]
                righe.append([self.cella_mana(r["colori"], r["nome"] if len(r["nome"]) <= 22 else r["nome"][:21] + "…"), self.cella(str(r["eventi"])),
                              self.cella(f"{'+' if netto >= 0 else ''}{pt(netto)}", VINTA if netto >= 0 else PERSA, True), self.cella(str(r["buste"]))])
            tab = self.tabella(self.b_maz, [("deck", "w"), ("events", "e"), ("gem balance", "e"), ("packs", "e")], righe, evidenzia=ev)
            for riga, r in zip(tab, self.farm):
                self.cliccabile(riga, ("farm", r))
            return
        if self.mostra.get() == "Field":
            # il campo: chi hai incontrato davvero in questo evento e come ci vai contro. E' il solo meta per evento che esista: Untapped pubblica il meta delle code classificate, non degli eventi
            g = {}
            for x in self.pp:
                r = g.setdefault(x["avv"] or "?", [0, 0]); r[0] += 1; r[1] += x["vinta"]
            if not g:
                tk.Label(self.b_maz, text="No games against anyone here", bg=C["scheda"], fg=C["grigio"], font=F(9), anchor="w").pack(fill="x")
                return
            quante = sum(r[0] for r in g.values())
            ord_ = sorted(g.items(), key=lambda t: -t[1][0])[:14]

            def nome_avv(col):
                return self.cella("unknown", C["grigio"], lato="left") if col == "?" else self.cella_mana(col)
            self.tabella(self.b_maz, [("opponent colors", "w"), ("share", "e"), ("record", "e"), ("win rate", "e")],
                         [[nome_avv(col), self.cella(f"{100 * r[0] / quante:.0f}%"), self.cella(f"{r[1]}-{r[0] - r[1]}"), self.cella_wr(r[1], r[0])] for col, r in ord_])
            return
        if self.mostra.get() == "Meta":
            if self.ev is not None and self.ev.get() not in (EVENTI_BASE, "Ranked", "Play"):
                self.v_maz.set("")
                tk.Label(self.b_maz, text="No public meta for a single event: see Field, the decks you met here", bg=C["scheda"], fg=C["grigio"], font=F(9), anchor="w", justify="left", wraplength=420).pack(fill="x")
                return
            meta, sotto = meta_formato(fmt, 12)
            if not meta:
                self.v_maz.set("")
                tk.Label(self.b_maz, text=f"No meta for {fmt}", bg=C["scheda"], fg=C["grigio"], font=F(9), anchor="w").pack(fill="x")
                return
            self.v_maz.set(sotto)
            con_wr = all(m.get("wr") is not None for m in meta)

            def nome_arch(m):
                lim = 26 - 3 * len(m.get("colori", ""))      # accanto a molti simboli di mana il nome si accorcia
                nm = m["nome"] if len(m["nome"]) <= lim else m["nome"][:lim - 1] + "…"
                return self.cella_mana(m.get("colori", ""), nm, grande=8)
            righe = []
            for m in meta:
                pos, tot = m.get("possedute"), m.get("carte")
                wr = m.get("wr") or 0
                righe.append([nome_arch(m), self.cella(f"{m.get('quota', 0):.1f}%"),
                              self.cella(f"{wr:.1f}%", C["titolo"], True) if con_wr else
                              self.cella(f"{m['forza']}°" if m.get("forza") else "-", C["titolo"] if m.get("forza") else C["grigio"], True),
                              self.cella(f"{pos}/{tot}" if pos is not None else "-", C["verde_t"] if pos is not None and tot and pos >= tot - 2 else C["grigio"]),
                              self.cella("↗" if m.get("url") else "", C["acciaio"], True)])
            if righe:
                ev = [i for i, m in enumerate(meta) if self.aperto and self.aperto[0] == "meta" and self.aperto[1].get("nome") == m["nome"]]
                for riga, m in zip(self.tabella(self.b_maz, [("archetype", "w"), ("share", "e"), ("win rate" if con_wr else "strength", "e"), ("cards owned", "e"), ("source", "e")], righe, evidenzia=ev), meta):
                    if hasattr(riga, "cliccabile"):       # la riga su tela: la freccia (l'ultima colonna) apre la pagina originale, il resto la scheda
                        def clic(e, riga=riga, m=m):
                            if m.get("url") and riga.cella_a(e.x) == len(riga.tab.colonne_x) - 1:
                                webbrowser.open(m["url"])
                            else:
                                self.apri(None if self.aperto == ("meta", m) else ("meta", m))
                        riga.cursore = "hand2"
                        riga.bind("<Button-1>", clic)
                        continue
                    self.cliccabile(riga, ("meta", m))
                    if m.get("url"):      # la freccia apre la pagina originale su Untapped, il resto della riga apre la scheda
                        for w in [riga[-1]] + list(riga[-1].winfo_children()):
                            w.bind("<Button-1>", lambda e, u=m["url"]: webbrowser.open(u))
            else:
                tk.Label(self.b_maz, text="No meta yet", bg=C["scheda"], fg=C["grigio"], font=F(8)).pack(anchor="w")
            return
        self.v_maz.set("most played, by win rate · click a deck")
        cod = SUPER_FORMATO.get(fmt)
        vivi = {m["id"] for m in (self.dati or {}).get("arena") or []}      # i mazzi cancellati da Arena restano nei numeri, non in questa lista (Autore, 7 nov 2026)
        righe = mazzi_costruiti([x for x in self.pp if cod is not None and x.get("formato") == cod and (not vivi or x.get("id") in vivi)])
        if not righe:
            tk.Label(self.b_maz, text=f"No games recognized in {fmt}", bg=C["scheda"], fg=C["grigio"], font=F(9), anchor="w").pack(fill="x")
            return
        if righe:
            ev = [i for i, r in enumerate(righe) if self.aperto == ("mio", r[0])]
            tab = self.tabella(self.b_maz, [("deck", "w"), ("last", "e"), ("record", "e"), ("win rate", "e")],
                               [[self.cella_mana(col, nome if len(nome) <= 22 else nome[:21] + "…"), self.cella(f"{ultima:%d/%m}", C["grigio"], grande=8),
                                 self.cella(f"{w}-{n - w}"), self.cella_wr(w, n)] for nome, col, n, w, ultima in righe], evidenzia=ev)
            for riga, r in zip(tab, righe):
                self.cliccabile(riga, ("mio", r[0]))
        else:
            tk.Label(self.b_maz, text="No Standard games", bg=C["scheda"], fg=C["grigio"],
                     font=F(9), anchor="w").pack(fill="x")
