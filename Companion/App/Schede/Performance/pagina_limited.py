"""Performance, modo Limited: win rate, numeri, mazzi, meta e campo dei draft."""
import datetime
import sys
import webbrowser

import premi_eventi as PE

import ambiente      # DECK_URL si legge a ogni uso: cambia con l'account (10 nov 2026)
from dati_app import FORMATI_LIMITED, TUTTI_FORMATI, coppie, numeri, saldo_draft
from dati_drafter import calendario as calendario_draft, campo
from icone import nome_set
from pagina_base import Pagina
from tema import CI as C, PERSA, VINTA
from widget import Tendina


class PaginaLimited(Pagina):
    """Limited: tutti i draft e i sealed di Arena in una scheda, con i menu Espansione e Formato in cima. A sinistra il
    grafico del win rate e il calendario del formato, a destra i tuoi numeri e il meta (meta, i tuoi draft, il campo)."""

    def __init__(self, tk, padre, F, mana):
        super().__init__(tk, padre, F, mana)
        # il menu del formato, accanto a quello dell'espansione
        self.fmt = Tendina(tk, self.barra_menu, "Format", F, larga=200)
        self.fmt.fr.pack(side="left", padx=(12, 0))
        self.opzioni_fmt = []
        self.formato = "quick"
        # a sinistra il grafico e il calendario, a destra i dati
        self.b_and, self.v_and = self.scheda("Win rate", col=0, espandi=True)      # il calendario sta nella scheda Drafter dal 6 nov 2026
        self.b_and.v_testata = self.v_and
        self.b_num, self.v_num = self.scheda("Your numbers", col=1)
        b, self.v_fonte = self.scheda("Meta and drafts", espandi=True, col=1)
        bott = tk.Frame(b, bg=C["scheda"]); bott.pack(fill="x", pady=(0, 6))
        self.lista = tk.Frame(b, bg=C["scheda"]); self.lista.pack(fill="both", expand=True)
        self.vista = sys.argv[sys.argv.index("--vista") + 1] if "--vista" in sys.argv else "meta"   # --vista: collaudo
        self.pulsanti = {}
        for testo, k in (("Meta", "meta"), ("Your drafts", "tuoi"), ("Field", "campo")):
            p = tk.Label(bott, text=testo, bg=C["cap"], fg=C["testo"], font=F(9, True), padx=12, pady=3, cursor="hand2",
                         highlightthickness=0)
            p.pack(side="left", padx=(0, 8))
            p.bind("<Button-1>", lambda e, k=k: (setattr(self, "vista", k), self.disegna_lista()))
            self.pulsanti[k] = p
        self.stato = dict(draft=[], set="FRA", coppie={}, campo=None, colori="", premi=None)

    def aggiorna(self, **kw):
        self.stato.update(kw)
        if "coppie" in kw or "campo" in kw:
            self.__dict__.pop("_altri", None)     # dati nuovi: meta e campo degli altri set si rileggono
        self.ridisegna()

    def formati(self, draft):
        """[(nome, prefissi)]: i formati limited di Arena e quelli trovati nelle tue partite che non sono in elenco."""
        noti = {x for _, pr in FORMATI_LIMITED for x in pr}
        altri = sorted({d["tipo"] for d in draft} - noti)
        return list(FORMATI_LIMITED) + [(t, (t,)) for t in altri]

    def opzioni_formato(self, draft):
        tk = self.tk
        fm = self.formati(draft)
        opz = [TUTTI_FORMATI] + [n for n, _ in fm]
        if opz != self.opzioni_fmt:
            self.opzioni_fmt = opz
            self.fmt.opzioni(opz, lambda o: (setattr(self, "scelto_fmt", True), self.disegna()))
        if not getattr(self, "scelto_fmt", False) or self.fmt.get() not in opz:
            # il formato dell'ultimo draft giocato, finche' non ne scegli uno tu
            ultimo = draft[-1]["tipo"] if draft else "QuickDraft"
            self.fmt.set(next((n for n, pr in fm if ultimo in pr), TUTTI_FORMATI))
            if "--formato" in sys.argv:      # collaudo
                self.fmt.set(sys.argv[sys.argv.index("--formato") + 1].replace("_", " "))
        return fm

    def disegna(self):
        tk, F, st = self.tk, self.F, self.stato
        fm = self.opzioni_formato(st["draft"])
        nome_fmt = self.fmt.get()
        prefissi = None if nome_fmt == TUTTI_FORMATI else dict(fm).get(nome_fmt, (nome_fmt,))
        self.formato = {"Quick Draft": "quick", "Premier Draft": "premier", TUTTI_FORMATI: "tutti"}.get(nome_fmt, "altro")
        tutti = [d for d in st["draft"] if prefissi is None or d["tipo"] in prefissi]
        # le espansioni: quelle dei tuoi draft piu' quelle del calendario dei draft di Arena (Regole/calendario_set.json), anche
        # senza partite (Autore, 18 ott 2026: «aggiungi l'espansione Aetherdrift che arriva oggi»); dalla piu' recente
        cal = calendario_draft()
        quando = {}
        for d in tutti:
            quando[d["set"]] = max(quando.get(d["set"], 0), d["quando"].timestamp())
        for s, v in cal.items():
            try:
                quando[s] = max(quando.get(s, 0), datetime.datetime.fromisoformat(v.get("inizio")).timestamp())
            except (TypeError, ValueError):
                quando.setdefault(s, 0)
        quando.setdefault(st["set"], 0)
        self.opzioni_menu(sorted(quando, key=lambda x: -quando[x]), st["set"])
        fs = self.filtro()
        mie = [d for d in tutti if fs is None or d["set"] == fs]
        self.mie = mie
        self.v_num.set(" · ".join(x for x in (fs or "all sets", nome_fmt if nome_fmt != TUTTI_FORMATI else "") if x))
        w, n, nd, tro = numeri(mie)
        if n:
            l = n - w
            voci = [("win rate", f"{round(100 * w / n)}%", VINTA if w / n >= 0.5 else PERSA), ("games", str(n), None), ("trophies", tro, None),
                    ("wins", str(w), VINTA), ("losses", str(l), PERSA), ("win/loss ratio", f"{w / l:.2f}" if l else "-", None)]
            nota = ""
            if st["premi"] is not None:
                r = PE.riepilogo(st["premi"], prefissi, fs)
                pt = lambda x: f"{x:,}"
                if r["premi"] or r["ingressi"]:
                    voci += [("gems won", f"+{pt(r['gemme_vinte'])}", None),
                             ("packs won", str(r["buste"]), None), ("rares · mythics", f"{r['rare']} · {r['mitiche']}", None)]
                    nota = (f"entries paid: {pt(r['gemme_spese'])} gems and {pt(r['oro_speso'])} gold · gems, packs, rares and mythics: "
                            f"{r['premi']} events claimed since {PE.dal()}")
                else:
                    voci += [("gems won", "-", C["muto"]), ("packs won", "-", C["muto"]), ("rares · mythics", "-", C["muto"])]
                    nota = f"gems, packs, rares and mythics are tracked since {PE.dal()}: these events are older"
            # il rango dopo l'ultimo draft mostrato, col suo logo (Autore, 6 nov 2026: «nel pannellino che indica la lega di appartenenza mettici il logo», «Sì, aggiungilo»). Quattro colonne: l'altezza resta quella di prima
            ultimo = max((d for d in mie if d.get("rango")), key=lambda d: d["quando"], default=None)
            rango = ultimo["rango"] if ultimo else None
            voci.insert(2, ("rank", rango or "-", C["acciaio"], "", self.logo_rango(rango, "limited", 22)))
            self.griglia(self.b_num, voci, colonne=4, grande=14, stretta=True, nota=nota)
        else:
            self.svuota(self.b_num)
            tk.Label(self.b_num, text="No " + (f"{nome_fmt} " if nome_fmt != TUTTI_FORMATI else "") + "games" + (f" in {fs}" if fs else ""),
                     bg=C["scheda"], fg=C["grigio"], font=F(9), anchor="w").pack(fill="x")
        # il grafico, a sinistra e piu' alto
        self.grafico(self.b_and, *saldo_draft(mie), vuoto="No games to show", altezza=640)   # riempie la colonna sinistra
        self.disegna_lista()

    def set_dati(self):
        """Il set di cui parlano meta e campo: quello scelto nel menu, o il set in corso con «tutte le espansioni»."""
        return self.filtro() or self.stato["set"]

    def altro_set(self, chiave, set_, leggi):
        """Meta o campo di un set diverso da quello in corso, letti una volta dai file locali e tenuti finche' arrivano dati nuovi."""
        cache = self.__dict__.setdefault("_altri", {})
        if (chiave, set_, self.formato) not in cache:
            try:
                cache[(chiave, set_, self.formato)] = leggi()
            except Exception as e:
                print(f"{chiave} {set_}: {type(e).__name__}: {e}")
                cache[(chiave, set_, self.formato)] = ([], "") if chiave == "coppie" else None
        return cache[(chiave, set_, self.formato)]

    def disegna_lista(self):
        tk, F, st = self.tk, self.F, self.stato
        for k, b in self.pulsanti.items():
            on = k == self.vista
            b.configure(fg=C["fondo"] if on else C["testo"], bg=C["titolo"] if on else C["cap"])
        self.svuota(self.lista)
        if self.vista == "meta":
            ms = self.set_dati()
            if ms == st["set"]:
                cp, fonte = (st["coppie"] or {}).get("premier" if self.formato == "premier" else "quick", ([], ""))
            else:       # un altro set scelto nel menu: il suo meta, non quello del set in corso (18 ott 2026)
                cp, fonte = self.altro_set("coppie", ms, lambda: coppie(ms, "premier" if self.formato == "premier" else "quick"))
            if self.formato == "altro":
                cp = []
            self.v_fonte.set(f"updated {fonte[:5]}" if fonte and cp else "")

            righe, ev = [], []
            for i, (cop, wr, tr) in enumerate(cp):
                mio = set(cop) == set(st["colori"]) and len(st["colori"]) == 2
                if mio:
                    ev.append(i)
                celle = [self.cella_mana(cop, numero=i + 1),
                         self.cella_barra((wr - 50) / 6, C["accento"] if mio else C["acciaio"]),
                         self.cella(f"{wr:.1f}%", C["titolo"], True)]
                if self.formato != "premier":
                    celle.append(self.cella(str(tr) if tr else "-", C["testo"] if tr else C["muto"]))
                righe.append(celle)
            if righe:
                self.tabella(self.lista, [("pair", "w"), ("", "w"), ("win rate", "e")] + ([("trophies", "e")] if self.formato != "premier" else []),
                             righe, allarga=1, evidenzia=ev)
            else:
                tk.Label(self.lista, text="No meta for this format" if self.formato == "altro" else f"No meta for {nome_set(ms)} yet",
                         bg=C["scheda"], fg=C["grigio"], font=F(8)).pack(anchor="w")
        elif self.vista == "campo":
            self.disegna_campo()
        else:
            self.disegna_tuoi()

    def disegna_tuoi(self):
        tk, F, st = self.tk, self.F, self.stato
        self.v_fonte.set("click opens the deck")
        mie = list(getattr(self, "mie", []))
        mie.sort(key=lambda d: (-d["w"], d["l"], -d["quando"].timestamp()))
        if not mie:
            tk.Label(self.lista, text="No drafts", bg=C["scheda"], fg=C["grigio"], font=F(8)).pack(anchor="w")
            return

        def esito(d):
            if d["w"] >= 7:     # una riga e' un draft: o e' trofeo o no, la coppa da sola (Autore, 18 ott 2026: niente «× 1»)
                return self.cella_img(self.coppa[16]) if self.coppa.get(16) else self.cella_img(None, "TROPHY", C["arancio"])
            if d["l"] < 3:
                return self.cella_img(None, "IN PROGRESS", C["azzurro"])
            return self.cella_img(None, "")
        righe = [[self.cella_mana(d["colori"], numero=i + 1),
                  self.cella(f"{d['w']}-{d['l']}", C["titolo"], True, lato="left"),
                  esito(d),
                  self.cella(f"{d['quando']:%d/%m}  ↗", C["grigio"], grande=8)] for i, d in enumerate(mie)]
        for riga, d in zip(self.tabella(self.lista, [("colors", "w"), ("record", "w"), ("", "w"), ("date", "e")], righe, allarga=2), mie):
            url = ambiente.DECK_URL.format(id=d["id"], set=d["set"])
            if hasattr(riga, "cliccabile"):       # la riga su tela (11 nov 2026)
                riga.cliccabile(lambda u=url: webbrowser.open(u), accesa=False)
                continue
            for c in riga:
                for w in [c] + list(c.winfo_children()):
                    w.configure(cursor="hand2"); w.bind("<Button-1>", lambda e, u=url: webbrowser.open(u))


    def disegna_campo(self):
        tk, F, st = self.tk, self.F, self.stato
        if self.formato not in ("quick", "tutti"):
            self.v_fonte.set("")
            tk.Label(self.lista, text="The opponents' field is for Quick Draft only", bg=C["scheda"], fg=C["grigio"], font=F(8)).pack(anchor="w")
            return
        ms = self.set_dati()
        cp = st.get("campo") if ms == st["set"] else self.altro_set("campo", ms, lambda: campo(ms))
        if cp and not cp.get("partite"):
            cp = None; testo = f"No Quick Draft games in {ms}"
        else:
            testo = "The field shows up once there is data"
        self.v_fonte.set(f"{cp['partite']} Quick games {ms}" if cp else "")
        if not cp:
            tk.Label(self.lista, text=testo, bg=C["scheda"], fg=C["grigio"], font=F(8)).pack(anchor="w")
            return
        r = tk.Frame(self.lista, bg=C["scheda"]); r.pack(fill="x")
        for t, w, a_ in (("against", 0, "w"), ("", 6, "e"), ("wins", 6, "e"), ("games", 7, "e")):
            tk.Label(r, text=t, width=w if w else None, anchor=a_, bg=C["scheda"], fg=C["muto"], font=F(7)).pack(side="left" if not w else "right")
        for cc, (n, v) in sorted(cp["per_col"].items(), key=lambda kv: (-kv[1][0], kv[0]))[:5]:
            r = tk.Frame(self.lista, bg=C["scheda"]); r.pack(fill="x")
            self.mana_label(r, cc if cc != "?" else "", C["scheda"]).pack(side="left", pady=1)
            pc_ = round(100 * v / n) if n else 0
            tk.Label(r, text=f"{pc_}%", width=6, anchor="e", bg=C["scheda"], fg=C["verde_t"] if pc_ >= 50 else C["rosso_t"], font=F(8, True)).pack(side="right")
            tk.Label(r, text=f"{v}", width=6, anchor="e", bg=C["scheda"], fg=C["testo"], font=F(8)).pack(side="right")
            tk.Label(r, text=f"{n}", width=7, anchor="e", bg=C["scheda"], fg=C["testo"], font=F(8)).pack(side="right")
        tk.Frame(self.lista, bg=C["filo2"], height=1).pack(fill="x", pady=5)
        nomi_f = {"0": "at 0 wins", "1-2": "at 1-2 wins", "3+": "at 3+ wins"}
        r = tk.Frame(self.lista, bg=C["scheda"]); r.pack(fill="x")
        for k in ("0", "1-2", "3+"):
            n, v = cp["per_rec"].get(k, (0, 0)); fz = cp["forze"].get(k)
            tk.Label(r, text=f"{nomi_f[k]}  {v}/{n}" + (f" · {fz:.1f}" if fz else ""), bg=C["scheda"], fg=C["testo"], font=F(8)).pack(side="left", padx=(0, 12))
        tk.Frame(self.lista, bg=C["filo2"], height=1).pack(fill="x", pady=5)
        tk.Label(self.lista, text="Cards you see the most", bg=C["scheda"], fg=C["grigio"], font=F(7), anchor="w").pack(fill="x")
        g_ = tk.Frame(self.lista, bg=C["scheda"]); g_.pack(fill="x")
        for i, (nome, k) in enumerate(cp["carte"]):
            rm = nome in cp["rimozioni"]
            tk.Label(g_, text=f"{nome}  ×{k}" + ("  removal" if rm else ""), bg=C["scheda"], fg=C["rosso_t"] if rm else C["testo"],
                     font=F(8), anchor="w").grid(row=i // 2, column=i % 2, sticky="w", padx=(0, 14))
