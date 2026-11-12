"""La scheda Your decks: My decks e Arena decks, i gruppi per formato, Wishlist e Deck building."""
import collections
import datetime
import os
import threading

import capsule as CAP
import carta_tela
import collezione_carte as CC
import disegni as DG
import mazzi_salvati as MS
import prezzi_carte as PZ
import visibilita_mazzi as VM

from dati_app import BASI, collezione, collezione_nota, craft, jolly, mazzi_costruiti
from finestra_mazzo import FinestraMazzo
from gruppi_mazzi import GRUPPI_CHIUSI, MS_dict, nome_formato, ordine_formato, salva_gruppi
from pagina_base import Pagina, prepara_capsule
from pagina_standard import PaginaStandard
from tema import CI as C, PERSA, VINTA
from widget import ARANCIO, Tendina, pulsante_solido


def VIS(larga):
    """La pillola pubblico/privato su una scheda: in alto a sinistra, sulla copertina. -> (x0, y0, x1, y1)."""
    return 10, 10, 10 + 96, 10 + 26


def CESTINO(larga):
    """Il riquadro del cestino su una scheda larga «larga»: in alto a destra, sulla copertina. -> (x0, y0, x1, y1)."""
    return larga - 14 - 26, 10, larga - 14, 36


def CLONA(larga):
    """Il riquadro di Clona sulle schede di Deck builder: accanto al cestino, a sinistra (12 nov 2026). -> (x0, y0, x1, y1)."""
    return larga - 14 - 26 - 8 - 26, 10, larga - 14 - 26 - 8, 36


class PaginaMazzi(PaginaStandard):
    CON_EVENTI = False

    """Your decks: i tuoi mazzi come schede, dal piu' recente (Autore, 6 nov 2026: «ora facciamo la sezione your decks / un insieme di cofanetti dei mazzi dei giocatori, se si clicca si apre la
    finestra dati del mazzo», poi, dopo le prove 3D e 2D, «a schede tipo i corsi di un sito»): copertina 16:9, riga piccola, titolo, tre dati in colonna, in fondo il win rate e il pulsante.
    Dal 7 nov 2026 i mazzi sono quelli che Arena scrive nel Player.log (mazzi_arena.py), anche mai giocati, e le partite si agganciano per id del mazzo. Se il log e la sua copia non ci sono, si torna alle partite.
    Prima: i mazzi e la finestra aperta col clic sono quelli di Standard: stesse partite, stessa disegna_dettaglio. Sono i mazzi con almeno
    una partita Ladder o Play registrata da Untapped: di quelli mai giocati non c'e' traccia, e un mazzo senza lista ha il cofanetto scuro."""

    LARGA, ALTA = 300, 310      # la scheda
    COVER = (298, 168)
    ORDINI = ("Last game", "Win rate", "Games", "Name", "First game")
    ORDINI_S = ("Last change", "Name", "Price", "Cards you own")     # wishlist, build e mazzi di Arena: senza partite
    MOSTRA = ("Decks you own", "All decks")     # Autore, 7 nov 2026: «l'app legge ancora mazzi che non sono nella mia collezione»: i mazzi importati e mai completati si vedono solo con All decks
    # le sottosezioni (Autore, 7 nov 2026: «nella sezione i miei deck creiamo le sottosezioni: mazzi personali / quelli di default forniti da arena / add deck dove possiamo mettere
    # in wishlist altri mazzi quindi sezione wish list / build your deck dove possiamo testare delle build e guadagnare dati in anticipo»)
    # la linguetta Wishlist non c'e' piu': la wishlist e' un gruppo di My decks (Autore, 7 nov 2026: «Sì, toglila»)
    # Build si chiama Laboratory (Autore, 7 nov 2026: «la sezione build diventa laboratorio in inglese e li vengono salvati i deck dal deckbuilder»)
    # la linguetta Laboratory non c'e' piu': i mazzi del builder stanno nel gruppo Deck building di My decks, sotto la Wishlist (Autore, 9 nov 2026: «togli la sotto scheda laboratory e
    # mettila come sezione a tendina: deck building sotto wish list»). La chiave dei mazzi salvati resta «build»
    # la linguetta Arena decks non c'e' piu': i mazzi che Arena ti ha dato sono il gruppo Arena decks di My decks, prima della Wishlist (Autore, 9 nov 2026: «anche la sottoscheda arena
    # decks deve diventare una sottocategoria in tendina prima di wishlist in my decks»). Con una sezione sola la barra delle linguette non si disegna
    SEZIONI = (("mine", "My decks"),)
    GRUPPO_ARENA = "Arena decks"
    GRUPPO_BUILD = "Deck builder"      # «Deck building» fino al 10 nov 2026 (Autore: «rinominiamo deck building in deck builder»)


    def __init__(self, tk, padre, F, mana):
        Pagina.__init__(self, tk, padre, F, mana)
        FinestraMazzo.MAZZI = self      # il builder aperto dalla Collection salva qui
        self.esp.fr.pack_forget()
        self.sezione, self.linguette_s, self.versione = "mine", {}, -1
        barra_s = tk.Frame(self.barra_menu, bg=C["fondo"])
        if len(self.SEZIONI) > 1:
            barra_s.pack(side="left", anchor="s", padx=(0, 18))
        for k, t in self.SEZIONI if len(self.SEZIONI) > 1 else ():
            cella = tk.Frame(barra_s, bg=C["fondo"]); cella.pack(side="left", padx=(0, 4))
            lab = tk.Label(cella, text=t, bg=C["fondo"], fg=C["grigio"], font=F(10, True), padx=12, pady=6, cursor="hand2"); lab.pack()
            sotto = tk.Frame(cella, bg=C["fondo"], height=2); sotto.pack(fill="x")
            lab.bind("<Button-1>", lambda e, k=k: self.cambia_sezione(k))
            lab.bind("<Enter>", lambda e, k=k, lab=lab: lab.configure(fg=C["titolo"]) if self.sezione != k else None)
            lab.bind("<Leave>", lambda e, k=k, lab=lab: lab.configure(fg=C["grigio"]) if self.sezione != k else None)
            self.linguette_s[k] = (lab, sotto)
        self.t_ord = Tendina(tk, self.barra_menu, "Sort by", F, larga=170); self.t_ord.fr.pack(side="left")
        self.t_ord.opzioni(self.ORDINI, lambda o: self.riordina()); self.t_ord.set(self.ORDINI[0])
        self.t_mostra = Tendina(tk, self.barra_menu, "Show", F, larga=170); self.t_mostra.fr.pack(side="left", padx=(10, 0))
        self.t_mostra.opzioni(self.MOSTRA, lambda o: self.cambia_mostra()); self.t_mostra.set(self.MOSTRA[0])
        # Import, come in Arena (Autore, 7 nov 2026: «ci serve un pulsante di import che copi i deck in questa applicazione, come per arena»): la lista negli appunti diventa un mazzo
        casa = {}
        self.b_import = casa["b"] = pulsante_solido(tk, F, self.barra_menu, "Import", False, lambda: self.importa(casa["b"]), alto=32, bg=C["fondo"])
        self.b_import.configure(width=150)
        self.b_import.pack(side="right", anchor="s")      # la pagina parte da My decks: Import a vista subito, non solo dopo un cambio di linguetta (9 nov 2026)
        self.segna_sezione()
        self.col[1].grid_remove(); self.col[0].grid(row=2, column=0, columnspan=2, sticky="nsew", padx=0)
        self.dati = None; self.pp = []; self.aperto = None; self.premi = None; self.farm = []; self.fin = self.det = None
        self.arena = {}
        self.mazzi, self.scatole, self.foto, self.colonne, self.sporco = [], [], {}, 0, False
        self.da_cuocere, self.cotte, self.cottura = collections.deque(), collections.deque(), None
        self.lista = CAP.Liste(tk, F)
        self.area("Your decks")
        self.al_davanti(lambda e: self.salvati_cambiati())

    def segna_sezione(self):
        for k, (lab, sotto) in self.linguette_s.items():
            on = k == self.sezione
            lab.configure(fg=C["titolo"] if on else C["grigio"]); sotto.configure(bg=C["accento"] if on else C["fondo"])

    def cambia_sezione(self, k):
        if k == self.sezione:
            return
        self.sezione = k
        self.segna_sezione()
        if k == "mine":
            self.t_mostra.fr.pack(side="left", padx=(10, 0))
        else:
            self.t_mostra.fr.pack_forget()
        if k == "mine":
            self.b_import.pack(side="right", anchor="s")
        else:
            self.b_import.pack_forget()
        voci = self.ORDINI if k in ("mine", "arena") else self.ORDINI_S
        self.t_ord.opzioni(voci, lambda o: self.riordina()); self.t_ord.set(voci[0])
        self.sporco = True
        self.disegna()
        self.cv.yview_moveto(0)

    def importa(self, b):
        """La lista copiata (da Arena, MTGO, un sito) diventa un mazzo della wishlist o delle build, e si apre. Con All accounts no (sola lettura)."""
        import account
        if account.sola_lettura():
            b.metti("Choose an account first", True); b.after(2500, lambda: b.winfo_exists() and b.metti("Import", False))
            return
        try:
            testo = self.fr.clipboard_get()
        except Exception:
            testo = ""
        z = MS.leggi_lista(testo)
        if not z["lista"] and not z["comandante"]:
            b.metti("Copy a deck list first", True); b.after(2500, lambda: b.winfo_exists() and b.metti("Import", False))
            return None
        tot = sum(z["lista"].values()) + sum(z["comandante"].values())
        fmt = "Brawl" if z["comandante"] and tot >= 90 else "Standard Brawl" if z["comandante"] else "Standard"
        sez = "wish" if self.sezione == "mine" else self.sezione       # da My decks l'Import va nel gruppo Wishlist
        m = MS.aggiungi(sez, dict(nome=z["nome"] or "Imported deck", formato=fmt, lista=z["lista"], side=z["side"], comandante=z["comandante"], compagno=z["compagno"]))
        b.metti(f"Imported {tot} cards", False); b.after(2500, lambda: b.winfo_exists() and b.metti("Import", False))
        self.sporco = True
        self.disegna()
        self.apri((sez, m))
        return m

    def salvati_cambiati(self):
        """Tornando sulla pagina: se una wishlist o una build e' cambiata altrove (dal Meta), si ridisegna."""
        if self.sezione == "mine" and self.versione != MS.VERSIONE[0]:
            self.sporco = True
            self.disegna()

    MARGINE_SU = 14

    def area(self, titolo):
        """La scheda con la griglia delle schede che scorre, la barra sottile a destra e la rotella."""
        tk = self.tk
        b, _ = self.scheda(titolo, espandi=True)
        self.titolo = self.cap_tit
        barra = tk.Canvas(b, width=8, bg=C["traccia"], highlightthickness=0, cursor="hand2"); barra.pack(side="right", fill="y", padx=(6, 0))

        def segna(a, b_):
            barra.delete("all"); a, b_ = float(a), float(b_)
            if b_ - a < 0.999:
                H_ = barra.winfo_height(); barra.create_rectangle(0, H_ * a, 8, H_ * b_, fill=C["grigio"], width=0)
        self.cv = cv = tk.Canvas(b, bg=C["scheda"], highlightthickness=0, yscrollcommand=segna); cv.pack(side="left", fill="both", expand=True)
        # un margine fra il bordo della scheda e le schede dei mazzi in alto (Autore, 7 nov 2026: «in decks dai piu' margine tra il frame e le schede dei mazzi in alto»)
        su = self.MARGINE_SU
        # le schede dei mazzi si disegnano su questa tela, non una tela ciascuna (11 nov 2026, sessione Magic 13, Note/Motore_Grafico_App.md): griglia_b resta per
        # i testi e la vista Charts della Meta
        self.griglia_b = tk.Frame(cv, bg=C["scheda"]); id_g = self.id_griglia_b = cv.create_window(0, su, anchor="nw", window=self.griglia_b)
        self.smista, self.alto_carte = carta_tela.Smistatore(cv), 0
        self.griglia_b.bind("<Configure>", lambda e: self.regione())
        cv.bind("<Configure>", lambda e: (cv.itemconfigure(id_g, width=e.width), self.disponi(e.width)))
        barra.bind("<Button-1>", lambda e: cv.yview_moveto(e.y / max(barra.winfo_height(), 1))); barra.bind("<B1-Motion>", lambda e: cv.yview_moveto(e.y / max(barra.winfo_height(), 1)))

        def rotella(e):
            if str(e.widget).startswith(str(cv)) and self.alto_regione() > cv.winfo_height():
                cv.yview_scroll(-3 if e.delta > 0 else 3, "units")
        cv.bind_all("<MouseWheel>", rotella, add="+")
        self.al_davanti(lambda e: self.disegna() if self.sporco else None)

    def aggiorna(self, dati=None):
        if dati is not None:
            self.dati = dati
            # le partite di tutti gli eventi costruiti, non solo Ranked e Play: i mazzi che Arena ti ha dato si giocano in Dual Color Precons e contro il bot
            # (Autore, 7 nov 2026: «i mazzi standard di arena vedo che non raccolgono statistiche»: 115 partite fuori dal conto)
            self.pp = dati.get("tutte") or dati.get("partite") or []
            self.sporco = True
        self.disegna()

    def mazzo_arena(self, chi):
        return self.arena.get(chi)

    def cambia_mostra(self):
        self.sporco = True
        self.disegna()

    def elenco_arena(self, mazzi):
        """I mazzi del Player.log coi numeri delle loro partite. Il record e' quello delle partite col suo id: fra due mazzi con lo stesso nome il nome non basta."""
        per_id = collections.defaultdict(list)
        for x in self.pp:
            per_id[x.get("id")].append(x)
        coll, _ = collezione()
        jl, _q = jolly()
        self.arena, out = {}, []
        for m in mazzi:
            pp = per_id.get(m["id"], [])
            quando = [x["quando"] for x in pp]
            d = lambda k: datetime.datetime.fromisoformat(m[k]) if m.get(k) else None
            ultima = max([z for z in [d("ultima")] + quando if z], default=None)
            carte = {}
            for z in ("main", "side", "comandante", "compagno"):
                for n, q in m[z].items():
                    carte[n] = carte.get(n, 0) + q
            mancano = sum(max(0, min(q, 4) - coll.get(n, 0)) for n, q in carte.items() if n not in BASI)
            gioca = {}
            for z in ("main", "comandante", "compagno"):        # i jolly del mazzo, come per wishlist e build: senza la sideboard
                for n, q in m[z].items():
                    gioca[n] = gioca.get(n, 0) + q
            manca_j, si_j = craft(gioca, coll, jl)
            if not collezione_nota():      # l'app pubblica senza la collezione: i jolly non si sanno, la scheda dice «-»
                manca_j, si_j = None, None
            v = dict(m, manca=manca_j, si=si_j, jl=jl, partite=pp, n=len(pp), w=sum(x["vinta"] for x in pp), ultima=ultima, aggiornato=d("aggiornato"), prima=min(quando, default=None), mancano=mancano,
                     arte=CAP.copertina([(q, c) for c, q in {**m["comandante"], **m["main"]}.items()]))
            self.arena[m["id"]] = v
            out.append(v)
        return out

    def elenco_salvati(self):
        """Wishlist o build: [dict] con le carte che hai, i jolly che mancano e il prezzo, piu' la scheda «+» in testa."""
        return self.elenco_salvati_di(self.sezione)

    def elenco_salvati_di(self, sez):
        coll, _ = collezione()
        jl, _q = jolly()
        return [self.conta(dict(m, main=m["lista"]), coll, jl, salvato=True) for m in MS.carica()[sez]]

    def conta(self, m, coll, jl, salvato=False):
        """Carte che hai, jolly che mancano, prezzo e copertina di un mazzo senza partite (wishlist, build, mazzi di base di Arena)."""
        tutte = {}
        for z in ("main", "comandante", "compagno"):
            for n, q in (m.get(z) or {}).items():
                tutte[n] = tutte.get(n, 0) + q
        manca, si = craft(tutte, coll, jl)
        cambio = m.get("modificato") or m.get("aggiornato") or m.get("ultima")
        if not collezione_nota():
            manca, si = None, None
        return dict(m, tot=sum(tutte.values()), own=sum(q if n in BASI else min(q, coll.get(n, 0)) for n, q in tutte.items()), manca=manca, si=si, jl=jl,
                    eur=PZ.totale(tutte)[0], cambio=datetime.datetime.fromisoformat(cambio) if isinstance(cambio, str) else cambio,
                    arte=m.get("arte") or CAP.copertina([(q, n) for n, q in tutte.items()]), salvato=salvato)

    def elenco(self):
        """[dict(nome, colori, n, w, ultima, prima, arte)], dal piu' recente. L'arte e' la carta piu' rara dell'ultima lista giocata."""
        if self.sezione in ("wish", "build"):
            return self.elenco_salvati()
        if (self.dati or {}).get("arena"):
            tutti = self.elenco_arena(self.dati["arena"])
            if self.sezione == "arena":
                coll, _ = collezione()
                jl, _q = jolly()
                return [self.conta(m, coll, jl) for m in tutti if m.get("precon")]
            return tutti        # i tuoi e, nel loro gruppo, quelli che Arena ti ha dato
        if self.sezione == "arena":
            return []
        from deckstring import decodifica
        ultima_ds, prima = {}, {}
        for x in self.pp:
            if x["ds"]:
                ultima_ds[x["nome"]] = x["ds"]
            k = x["nome"] or ("Unnamed" + (f" {x['colori']}" if x["colori"] else ""))
            prima[k] = min(prima.get(k, x["quando"]), x["quando"])
        out = []
        for nome, col, n, w, quando in sorted(mazzi_costruiti(self.pp, 10 ** 6), key=lambda r: r[4], reverse=True):
            arte = None
            if ultima_ds.get(nome):
                try:
                    arte = CAP.copertina([(q, c) for c, q in decodifica(ultima_ds[nome]).items()])
                except Exception:
                    arte = None
            out.append(dict(nome=nome, colori=col, n=n, w=w, ultima=quando, prima=prima.get(nome, quando), arte=arte))
        return out

    def disegna(self):
        """I cofanetti. A pagina nascosta aspetta: tanto nessuno li vede."""
        if not self.dati and self.sezione in ("mine", "arena"):
            return
        if not self.davanti() and not Pagina.SUBITO:
            self.sporco = True
            return
        if not self.sporco and (self.scatole or self.sezione == "build"):
            return
        self.sporco = False
        self.versione = MS.VERSIONE[0]
        self.smista.svuota(); self.cv.delete("gruppo")
        self.svuota(self.griglia_b)
        self.scatole = []
        if len(self.foto) > 150:         # le copertine di prima: le tele sono appena state distrutte, oltre 150 (30 MB) si liberano
            self.foto.clear()
        prepara_capsule(CC.carica())
        self.mazzi = sorted(self.elenco(), key=self.chiave)
        if self.sezione == "mine" and self.t_mostra.get() == self.MOSTRA[0] and collezione_nota():       # senza i dati di Arena «mancano» non c'e': si vede tutto
            self.mazzi = [m for m in self.mazzi if not m.get("mancano") or m.get("precon")]       # i mazzi di Arena si vedono tutti, come nella linguetta di prima
        self.titolo.configure(text=f"{dict(self.SEZIONI)[self.sezione].upper()} · {len(self.mazzi)}")
        if self.sezione == "mine":      # la wishlist sta anche qui, nel suo gruppo in fondo (Autore, 7 nov 2026), e sotto i mazzi del builder (9 nov 2026)
            for sez_ in ("wish", "build"):
                for w_ in self.elenco_salvati_di(sez_):
                    self.mazzi.append(dict(w_, _sez=sez_, n=0, w=0, prima=None, ultima=w_.get("cambio")))
            # la scheda «+» in testa ai due gruppi, che ci sono anche vuoti: apre il builder. Con All accounts no: sola lettura (10 nov 2026, Magic 12)
            import account
            if not account.sola_lettura():
                self.mazzi.insert(0, dict(piu=True, nome="New deck", _sez="build"))
                self.mazzi.insert(0, dict(piu=True, nome="Add deck", _sez="wish"))
        if not self.mazzi:
            self.tk.Label(self.griglia_b, text="No decks yet", bg=C["scheda"], fg=C["grigio"], font=self.F(9)).pack(anchor="w")
        # i gruppi a tendina, uno per formato, col titolo grande (Autore, 7 nov 2026: «my decks > menu espandibile a tendine espandibili con titolo grande che gruppano i deck per ogni formato
        # e anche la wishlist li dentro»)
        self.box, self.quanti_g = {}, {}
        gruppi = {}
        for m in self.mazzi:
            m["_gruppo"] = ("Wishlist" if m.get("_sez") == "wish" else self.GRUPPO_BUILD if m.get("_sez") == "build" else None if m.get("piu")
                            else self.GRUPPO_ARENA if m.get("precon") else nome_formato(m.get("formato")))
            gruppi.setdefault(m["_gruppo"], []).append(m)
        if None in gruppi:
            self.box[None] = None
        for g in sorted((g for g in gruppi if g is not None), key=ordine_formato):      # i gruppi in ordine; i titoli li disegna disponi sulla tela
            self.box[g] = g
            self.quanti_g[g] = sum(1 for m in gruppi[g] if not m.get("piu"))
        self.piu_m, self.piu_c = [], []      # le schede «+» stanno fuori dall'elenco dei mazzi: non si contano e non si ordinano
        for m in self.mazzi:
            if m.get("piu"):
                self.piu_m.append(m); self.piu_c.append(self.scatola_piu(m))
            else:
                self.scatole.append(self.scatola_lista(m) if (self.sezione == "build" or m.get("_sez")) else self.scatola(m))      # i mazzi di Arena hanno partite: la scheda di My decks
        self.mazzi = [m for m in self.mazzi if not m.get("piu")]
        self.disponi(self.cv.winfo_width(), forza=True)
        if self.aperto:
            self.disegna_dettaglio()

    def scatola(self, m):
        """Una scheda: un riquadro col filo sottile, la copertina, poi i testi. Al passaggio del mouse si illumina (Autore, 6 nov 2026: «le schede devono illuminarsi in hover»)."""
        tk, F = self.tk, self.F
        L, H = self.LARGA, self.ALTA
        c = self.nuova_scatola()

        def disegna():
            c.delete("all")
            c.create_rectangle(0, 0, L - 1, H - 1, fill=C["fondo"], outline=C["filo"], tags="corpo")
            f = CAP.file_cover(m["arte"], *self.COVER)
            if os.path.exists(f):
                if f not in self.foto:
                    from PIL import Image, ImageTk
                    self.foto[f] = ImageTk.PhotoImage(Image.open(f))
                c.create_image(1, 1, image=self.foto[f], anchor="nw")
            else:
                self.cuoci(m, disegna)
            alto = self.COVER[1] + 1
            c.create_line(0, alto, L, alto, fill=C["filo"])
            x, dx_ = 14, L - 14
            # la riga piccola: i simboli, i colori, a destra l'ultima partita col suo pallino
            y = alto + 20
            sx = x
            for k in [z for z in "WUBRG" if z in (m["colori"] or "")]:
                img = self.lista.simbolo(k, 14)
                if img:
                    c.create_image(sx + 7, y, image=img)
                    sx += 17
            c.create_text(sx + (5 if sx > x else 0), y, text=CAP.nome_mazzo(m["colori"]).upper(), anchor="w", fill=C["acciaio"], font=F(7, True))
            if m["ultima"]:
                giorni = (datetime.datetime.now() - m["ultima"]).days
                data = c.create_text(dx_, y, text=f"{m['ultima']:%d/%m/%y}", anchor="e", fill=C["grigio"], font=F(7, True))
                xp = c.bbox(data)[0] - 9
                c.create_image(xp, y, image=DG.punto(7, C["verde"] if giorni <= 7 else C["muto"]))
            else:
                c.create_text(dx_, y, text="never played", anchor="e", fill=C["muto"], font=F(7, True))
            # il titolo
            nome = m["nome"] if len(m["nome"]) <= 30 else m["nome"][:29] + "…"
            c.create_text(x, y + 22, text=nome, anchor="w", fill=C["titolo"], font=F(11, True))
            # i tre dati, sotto un filo
            y0 = y + 42
            c.create_line(x, y0, dx_, y0, fill=C["filo"])
            for xc, (t, v) in zip(self.colonne_dati(x, dx_), (("RECORD", f"{m['w']}-{m['n'] - m['w']}" if m["n"] else "-"), ("GAMES", f"{m['n']:,}"))):
                c.create_text(xc, y0 + 14, text=t, anchor="w", fill=C["muto"], font=F(6, True))
                c.create_text(xc, y0 + 29, text=v, anchor="w", fill=C["testo"], font=F(9))
            # niente jolly sulle schede (Autore, 10 nov 2026: «sulle schede di anteprima togliamo: wc necessarie», poi «si anche li»): stanno nella finestra del mazzo
            # il piede: il win rate e il pulsante, alla stessa altezza
            wr = round(100 * m["w"] / m["n"]) if m["n"] else 0
            c.create_text(x, H - 27, text=f"{wr}%" if m["n"] else "-", anchor="w", fill=C["muto"] if not m["n"] else VINTA if wr >= 50 else PERSA, font=F(15, True))
            self.pulsante_scheda(c, dx_, H, "View deck")
            c.box_vis = self.vis_mazzo(c, m)
        disegna()
        self.lista.chiedi_arte(c, m["arte"], disegna)
        c.bind("<Enter>", lambda e: c.itemconfigure("corpo", fill=C["cap"], outline=C["accento"]))
        c.bind("<Leave>", lambda e: c.itemconfigure("corpo", fill=C["fondo"], outline=C["filo"]))
        c.bind("<Button-1>", lambda e: self.clic_vis(m, c, e) or self.apri(("mio", m.get("id") or m["nome"])))
        return c

    def pulsante_scheda(self, c, dx_, H, testo):
        """Il pulsante in basso a destra di una scheda di mazzo, in proporzione ai numeri grandi del piede (10 nov 2026)."""
        c.create_rectangle(dx_ - 104, H - 44, dx_, H - 10, fill=C["accento"], outline="")
        c.create_text(dx_ - 52, H - 27, text=testo, fill=C["fondo"], font=self.F(9, True))

    @staticmethod
    def colonne_dati(x, dx_):
        """Dove cominciano le tre colonne dei dati di una scheda: due strette, poi i jolly, che hanno bisogno di piu' posto."""
        w = dx_ - x
        return x, x + 0.25 * w, x + 0.49 * w

    def scatola_piu(self, m):
        """La scheda vuota col «+»: apre il builder (Add deck in wishlist, New build)."""
        tk, F = self.tk, self.F
        L, H = self.LARGA, self.ALTA
        c = self.nuova_scatola()
        c.create_rectangle(0, 0, L - 1, H - 1, fill=C["fondo"], outline=C["filo"], dash=(4, 3), tags="corpo")
        cx, cy = L / 2, H / 2 - 32       # un simbolo si disegna, non si scrive: un carattere di testo non sta mai al centro del cerchio (Autore, 7 nov 2026: «i simboli delle varie grafiche non devono essere disordinati»)
        c.create_image(cx, cy, image=DG.piu(61, C["accento"]))
        c.create_text(L / 2, H / 2 + 24, text=m["nome"], fill=C["titolo"], font=F(12, True))
        c.create_text(L / 2, H / 2 + 48, text="Opens the deck builder over your Collection", fill=C["grigio"], font=F(8))
        c.bind("<Enter>", lambda e: c.itemconfigure("corpo", fill=C["cap"], outline=C["accento"]))
        c.bind("<Leave>", lambda e: c.itemconfigure("corpo", fill=C["fondo"], outline=C["filo"]))
        c.bind("<Button-1>", lambda e: self.builder(m.get("_sez") or self.sezione))
        return c

    def scatola_lista(self, m):
        """Una scheda di un mazzo senza partite (Arena decks, Wishlist, Build): copertina, colori, nome, formato, carte che hai, jolly che mancano; in fondo il prezzo."""
        tk, F = self.tk, self.F
        L, H = self.LARGA, self.ALTA
        c = self.nuova_scatola()

        def disegna():
            c.delete("all")
            c.create_rectangle(0, 0, L - 1, H - 1, fill=C["fondo"], outline=C["filo"], tags="corpo")
            f = CAP.file_cover(m["arte"], *self.COVER) if m["arte"] else None
            if f and os.path.exists(f):
                if f not in self.foto:
                    from PIL import Image, ImageTk
                    self.foto[f] = ImageTk.PhotoImage(Image.open(f))
                c.create_image(1, 1, image=self.foto[f], anchor="nw")
            elif m["arte"]:
                self.cuoci(m, disegna)
            alto = self.COVER[1] + 1
            c.create_line(0, alto, L, alto, fill=C["filo"])
            x, dx_ = 14, L - 14
            y = alto + 20
            sx = x
            for k in [z for z in "WUBRG" if z in (m.get("colori") or "")]:
                img = self.lista.simbolo(k, 14)
                if img:
                    c.create_image(sx + 7, y, image=img)
                    sx += 17
            c.create_text(sx + (5 if sx > x else 0), y, text=CAP.nome_mazzo(m.get("colori") or "").upper(), anchor="w", fill=C["acciaio"], font=F(7, True))
            if m.get("cambio"):
                c.create_text(dx_, y, text=f"{m['cambio']:%d/%m/%y}", anchor="e", fill=C["grigio"], font=F(7, True))
            nome = m["nome"] if len(m["nome"]) <= 30 else m["nome"][:29] + "…"
            c.create_text(x, y + 22, text=nome, anchor="w", fill=C["titolo"], font=F(11, True))
            y0 = y + 42
            c.create_line(x, y0, dx_, y0, fill=C["filo"])
            fmt = m.get("formato") or ""
            fmt = {"TraditionalStandard": "Standard Bo3", "TraditionalExplorer": "Explorer Bo3", "HistoricBrawl": "Brawl"}.get(fmt, fmt)
            # niente jolly ne' carte possedute sulle schede (Autore, 10 nov 2026: «wc necessarie / x/x owned», «si anche li»): il formato, poi prezzo e pulsante
            c.create_text(x, y0 + 14, text="FORMAT", anchor="w", fill=C["muto"], font=F(6, True))
            c.create_text(x, y0 + 29, text=fmt or "-", anchor="w", fill=C["testo"], font=F(9))
            c.create_text(x, H - 27, text=PZ.euro(m["eur"]) if m.get("eur") else "-", anchor="w", fill=C["testo"], font=F(15, True))
            self.pulsante_scheda(c, dx_, H, "Edit" if sez == "build" and scrivibile else "View deck")
            if sez in ("wish", "build") and scrivibile:
                self.cestino(c, *CESTINO(L))
            if sez == "build" and scrivibile:      # clona il mazzo, accanto al cestino (12 nov 2026)
                c.create_image(CLONA(L)[0], CLONA(L)[1], image=self.icona_clona(False), anchor="nw", tags="clona")
            c.box_vis = self.vis_mazzo(c, m)
        sez = m.get("_sez") or self.sezione
        import account
        scrivibile = not account.sola_lettura()         # All accounts: niente cestino ne' Edit (10 nov 2026, Magic 12)
        disegna()
        if m["arte"]:
            self.lista.chiedi_arte(c, m["arte"], disegna)
        c.bind("<Enter>", lambda e: c.itemconfigure("corpo", fill=C["cap"], outline=C["accento"]))
        c.bind("<Leave>", lambda e: (c.itemconfigure("corpo", fill=C["fondo"], outline=C["filo"]), c.itemconfigure("cestino", image=self.icona_cestino(False)),
                                     c.itemconfigure("clona", image=self.icona_clona(False))))

        def sopra(e):
            if sez in ("wish", "build") and scrivibile:
                x0, y0, x1, y1 = CESTINO(L)
                c.itemconfigure("cestino", image=self.icona_cestino(x0 <= e.x <= x1 and y0 <= e.y <= y1))
            if sez == "build" and scrivibile:
                x0, y0, x1, y1 = CLONA(L)
                c.itemconfigure("clona", image=self.icona_clona(x0 <= e.x <= x1 and y0 <= e.y <= y1))
        c.bind("<Motion>", sopra)

        def clic(e):
            # il cestino in alto a destra: il mazzo va via subito e la pagina si ridisegna (Autore, 9 nov 2026: «cambiamo il modo di cancellare i mazzi, non da dentro il mazzo ma da
            # fuori metti un cestino in alto a destra sulla scheda e che il cancellamento sia immediato perche' vedo che devo cambiare e poi tornare alla pagina per vederlo cancellato»)
            if self.clic_vis(m, c, e):
                return
            x0, y0, x1, y1 = CESTINO(L)
            if sez in ("wish", "build") and scrivibile and x0 <= e.x <= x1 and y0 <= e.y <= y1:
                self.chiedi_cancella(sez, m); return
            x0, y0, x1, y1 = CLONA(L)
            if sez == "build" and scrivibile and x0 <= e.x <= x1 and y0 <= e.y <= y1:
                self.clona(sez, m); return
            # nel Laboratorio il pulsante Edit porta alla Collection col builder del mazzo acceso (Autore, 7 nov 2026: «premendo su edit l'app ti rimanda alla pagina collection con il deck builder del mazzo acceso»)
            if sez == "build" and scrivibile and L - 14 - 104 <= e.x <= L - 14 and H - 44 <= e.y <= H - 10:
                self.builder("build", MS_dict(m)); return
            self.apri((sez, MS_dict(m)) if sez in ("wish", "build") else ("mio", m["id"]))
        c.bind("<Button-1>", clic)
        return c

    def pillola_vis(self, c, x0, y0, stato, eccezione, tag, alta=26, sopra=False):
        """La pillola pubblico/privato (12 nov 2026, Autore; ridisegnata lo stesso giorno, la proposta A: «le icone public / private: dammi un redesign»):
        una pillola arrotondata col bordo del suo colore, l'occhio aperto azzurro e PUBLIC, o l'occhio barrato grigio e PRIVATE; il bordo arancio e un punto
        arancio in fondo quando il mazzo viola la regola del suo gruppo. Disegnata su c (una tela o una scheda della griglia) coi tag dati. -> la larghezza."""
        pub = stato == VM.PUBBLICO
        testo = "PUBLIC" if pub else "PRIVATE"
        col = C["accento"] if pub else C["grigio"]
        lg = round(38 + 7 * len(testo) + (14 if eccezione else 0))
        bordo = ARANCIO[1] if eccezione else col
        c.create_image(x0, y0, image=DG.pillola(lg, alta, bordo, C["fondo"]), anchor="nw", tags=tag)
        c.create_image(x0 + 9, y0 + (alta - 18) / 2, image=DG.occhio(18, col, barrato=not pub), anchor="nw", tags=tag)
        c.create_text(x0 + 31, y0 + alta / 2, text=testo, anchor="w", fill=col, font=self.F(7, True), tags=tag)
        if eccezione:       # il punto arancio: «own rule», la regola del mazzo e non quella del gruppo
            c.create_image(x0 + lg - 15, y0 + alta / 2 - 3.5, image=DG.punto(7, ARANCIO[1]), anchor="nw", tags=tag)
        return lg

    def vis_mazzo(self, c, m):
        """La pillola del mazzo sulla scheda (niente per Arena decks): stato e se viola la regola del gruppo."""
        stato, ecc = VM.mazzo(m)
        if stato is None:
            return None
        c.delete("vis")
        lg = self.pillola_vis(c, 10, 10, stato, ecc, ("vis",))
        return (10, 10, 10 + lg, 36)

    def clic_vis(self, m, c, e):
        """Vero se il clic e' sulla pillola: il mazzo cambia regola e la pillola si ridisegna."""
        box = getattr(c, "box_vis", None)
        if not box or not (box[0] <= e.x <= box[2] and box[1] <= e.y <= box[3]):
            return False
        import account
        if account.sola_lettura():
            return True
        VM.cambia_mazzo(m)
        c.box_vis = self.vis_mazzo(c, m)
        return True

    def cestino(self, c, x0, y0, x1, y1):
        """Il cestino disegnato, non scritto: un quadrato scuro sulla copertina col coperchio, il manico e il secchio a righe. Si accende di rosso sotto il puntatore."""
        c.create_image(x0, y0, image=self.icona_cestino(False, x1 - x0), anchor="nw", tags="cestino")

    def icona_cestino(self, acceso, lato=26):
        """Il cestino nitido (disegni.py): sul quadrato scuro, rosso sotto il puntatore."""
        return DG.cestino(lato, C["titolo"], PERSA if acceso else C["fondo"], PERSA if acceso else C["filo"])

    def icona_clona(self, acceso, lato=26):
        return DG.clona(lato, C["titolo"], C["accento"] if acceso else C["fondo"], C["accento"] if acceso else C["filo"])

    def clona(self, sez, m):
        """Clona un mazzo di Deck builder (Autore, 12 nov 2026: «in deck builder crea sia sulla deck cover che dentro la possibilita' di clonare il mazzo»): la copia
        nasce in testa al gruppo, «nome (copy)», con le carte, il formato, i lucchetti delle terre, la disposizione del Board e le connessioni. -> il mazzo nuovo."""
        orig = next((x for x in MS.carica()[sez] if x["id"] == m["id"]), None) or m
        campi = {k: orig.get(k) for k in ("formato", "lista", "side", "comandante", "compagno", "colori", "fonte", "lucchetti", "base_fatta") if orig.get(k) is not None}
        nuovo = MS.aggiungi(sez, dict(campi, nome=f"{orig.get('nome') or 'Deck'} (copy)"))
        if nuovo is None:
            return None
        try:        # il Board del mazzo: la disposizione e la rete passano alla copia
            import tavolo_carte as TC
            import rete_sinergie as RS
            vecchia, nuova = f"{sez}:{m['id']}", f"{sez}:{nuovo['id']}"
            t_ = TC.carica_tavoli().get(vecchia)
            if t_:
                TC.salva_tavolo(nuova, t_)
            r_ = RS.carica().get(vecchia)
            if r_:
                d_ = RS.carica(); d_[nuova] = r_; RS.scrivi(RS.FILE, d_)
        except Exception:       # noqa: BLE001 - senza Board la copia c'e' lo stesso
            pass
        self.sporco = True
        self.disegna()
        return nuovo

    def chiedi_cancella(self, sez, m):
        """Il cestino: prima la domanda, poi via (Autore, 12 nov 2026: «chiediamo sempre prima la conferma di voler cancellare il mazzo»). -> la finestrella."""
        from widget import conferma
        dove = "Wishlist" if sez == "wish" else "Deck builder"
        self.domanda = conferma(self.tk, self.F, self.fr, "Delete this deck?", f"«{m.get('nome') or 'Deck'}» goes out of your {dove}. This cannot be undone.",
                                "Delete", lambda: self.cancella(sez, m["id"]))
        return self.domanda

    def cancella(self, sez, mid):
        """Toglie un mazzo salvato (Wishlist o Deck building) e ridisegna subito la pagina; se la finestra di quel mazzo e' aperta si chiude."""
        MS.togli(sez, mid)
        if self.aperto and self.aperto[0] == sez and isinstance(self.aperto[1], dict) and self.aperto[1].get("id") == mid:
            self.apri(None)
        self.sporco = True
        self.disegna()

    def cuoci(self, m, disegna):
        """Le copertine si cuociono su un altro filo, una alla volta: la pagina resta viva."""
        self.da_cuocere.append((m["arte"], disegna))
        if self.cottura is None or not self.cottura.is_alive():
            self.cottura = threading.Thread(target=self.forno, daemon=True)
            self.cottura.start()
            self.fr.after(80, self.sforna)

    def forno(self):
        while self.da_cuocere:
            arte, disegna = self.da_cuocere.popleft()
            try:
                CAP.cover_mazzo(arte, *self.COVER)
                self.cotte.append(disegna)
            except Exception:
                pass

    def sforna(self):
        while self.cotte:
            try:
                self.cotte.popleft()()
            except self.tk.TclError:      # la scheda non c'e' piu' (cambio di formato o di sezione mentre la copertina cuoceva: collaudo del 7 nov 2026)
                pass
        if self.da_cuocere or self.cotte or (self.cottura is not None and self.cottura.is_alive()):
            self.fr.after(80, self.sforna)

    def chiave(self, m):
        o = self.t_ord.get()
        if o in self.ORDINI_S:
            if o == "Name":
                return (m["nome"].lower(),)
            if o == "Price":
                return (-(m.get("eur") or 0),)
            if o == "Cards you own":
                return (-m["own"] / max(m["tot"], 1), m["nome"].lower())
            return (m.get("cambio") is None, -(m["cambio"].timestamp() if m.get("cambio") else 0), m["nome"].lower())
        if o == "Win rate":
            return (-m["w"] / max(m["n"], 1), -m["n"])
        if o == "Games":
            return (-m["n"], m["nome"].lower())
        if o == "Name":
            return (m["nome"].lower(),)
        tempo = lambda z: -z.timestamp() if z else 0
        if o == "First game":      # chi non ha una data va in fondo
            return (m["prima"] is None, tempo(m["prima"]))
        return (m["ultima"] is None, tempo(m["ultima"]), tempo(m.get("aggiornato")))

    def riordina(self):
        """Le schede ci sono gia': cambia solo il posto. La scheda «+» resta in testa."""
        coppie = sorted(zip(self.mazzi, self.scatole), key=lambda x: self.chiave(x[0]))
        self.mazzi, self.scatole = [x[0] for x in coppie], [x[1] for x in coppie]
        self.disponi(self.cv.winfo_width(), forza=True)
        self.cv.yview_moveto(0)

    def nuova_scatola(self):
        """Una scheda di mazzo sulla tela della griglia (carta_tela.CartaTela), non una tela sua: disponi la mette al suo posto."""
        return carta_tela.CartaTela(self.cv, -10000, -10000, self.LARGA, self.ALTA, self.smista, cursore="hand2")

    def alto_regione(self):
        return max(self.griglia_b.winfo_reqheight() + self.MARGINE_SU if self.griglia_b.winfo_children() else 0, self.alto_carte)

    def regione(self):
        # griglia_b vuoto e' una finestra di Windows alta 1 pixel e larga quanto la pagina, proprio sulla riga del bordo alto della prima fila di schede: in
        # hover quel bordo non si accendeva (Autore, 12 nov 2026: «il bordo alto delle schede piu' alte non si illumina, e' tagliato»). Vuoto, si nasconde.
        if getattr(self, "id_griglia_b", None) is not None:
            self.cv.itemconfigure(self.id_griglia_b, state="normal" if self.griglia_b.winfo_children() else "hidden")
        self.cv.configure(scrollregion=(0, 0, 0, self.alto_regione()))

    def disponi(self, larga, forza=False):
        """La griglia sulla tela sola (11 nov 2026): i titoli dei gruppi disegnati, le schede al loro posto, centrate in colonne uguali come faceva la griglia di
        Tk. Si rifa' quando cambiano la larghezza, l'ordine o un gruppo; le schede di un gruppo chiuso stanno fuori dalla tela."""
        piu = list(zip(getattr(self, "piu_m", []), getattr(self, "piu_c", [])))
        coppie = piu + list(zip(self.mazzi, self.scatole))      # la scheda «+» in testa al suo gruppo
        n = max(1, larga // (self.LARGA + 14))
        if not forza and n == self.colonne and larga == getattr(self, "larga_disposta", None):
            return
        self.colonne, self.larga_disposta = n, larga
        self.cv.delete("gruppo")
        box = getattr(self, "box", None) or {None: None}        # la pagina Meta: una griglia sola, senza gruppi
        cw = larga / n
        y = self.MARGINE_SU
        for g in box:
            membri = [c for m, c in coppie if (m.get("_gruppo") if getattr(self, "box", None) else None) == g]
            aperto = True
            if g is not None:
                chiave = f"{self.sezione}:{g}"
                aperto = chiave not in GRUPPI_CHIUSI
                y = self.testa_gruppo(g, chiave, self.quanti_g.get(g, 0), y, larga, aperto)
            for i, c in enumerate(membri):
                r, k = divmod(i, n)
                c.cella = dict(row=r, column=k)
                c.sposta(round(k * cw + (cw - self.LARGA) / 2), y + r * (self.ALTA + 12)) if aperto else c.sposta(-10000, -10000)
            if aperto and membri:
                y += (len(membri) + n - 1) // n * (self.ALTA + 12) + 6
        self.alto_carte = y if coppie else 0
        self.regione()

    def testa_gruppo(self, nome, chiave, quanti, y, larga, aperto):
        """Il titolo di un gruppo a tendina, disegnato sulla tela: la freccia, il nome grande, quanti mazzi, il filo sotto. Un clic lo apre o lo chiude e la scelta
        resta (Log_Arena/mazzi_gruppi.json). -> la y dove cominciano le sue schede."""
        cv, F = self.cv, self.F
        t, tit_t = ("gruppo", f"gruppo:{chiave}"), f"titolo:{chiave}"
        y0 = y + 6
        cv.create_rectangle(0, y0, larga, y0 + 34, fill=C["scheda"], outline="", tags=t)        # tutta la riga si clicca, non solo le lettere
        # il triangolo disegnato, centrato: giu' aperto, a destra chiuso (un simbolo si disegna, non si scrive: Autore, 7 nov 2026)
        cv.create_image(4, y0 + 6, image=DG.triangolo(22, aperto, C["accento"]), anchor="nw", tags=t)
        tit = cv.create_text(32, y0 + 17, text=nome.upper(), anchor="w", fill=C["titolo"], font=F(16, True), tags=t + (tit_t,))
        cv.create_text(cv.bbox(tit)[2] + 12, y0 + 20, text=f"{quanti} deck{'s' if quanti != 1 else ''}", anchor="w", fill=C["grigio"], font=F(10, True), tags=t)
        yl = y0 + 40
        cv.create_line(0, yl, larga, yl, fill=C["filo"], tags="gruppo")
        regola = VM.gruppo(nome) if self.sezione == "mine" else None
        if regola is not None:       # la regola del gruppo, a destra della riga (12 nov 2026); Arena decks no
            tv = ("visg", f"visg:{chiave}")
            lg = self.pillola_vis(cv, 0, y0 + 4, regola, False, tv)
            cv.move(tv[1], larga - lg - 16, 0)
            cv.create_text(larga - lg - 26, y0 + 17, text="decks in this group:", anchor="e", fill=C["muto"], font=F(8), tags=tv)

            def gira(_e, nome=nome):
                import account
                if not account.sola_lettura():
                    VM.cambia_gruppo(nome)
                    self.ridisegna_vis()
            cv.tag_bind(tv[1], "<Button-1>", gira)
            cv.tag_bind(tv[1], "<Enter>", lambda e: cv.configure(cursor="hand2"))
            cv.tag_bind(tv[1], "<Leave>", lambda e: cv.configure(cursor=""))
        cv.tag_bind(t[1], "<Button-1>", lambda e: self.cambia_gruppo(chiave))
        cv.tag_bind(t[1], "<Enter>", lambda e: (cv.itemconfigure(tit_t, fill=C["accento"]), cv.configure(cursor="hand2")))
        cv.tag_bind(t[1], "<Leave>", lambda e: (cv.itemconfigure(tit_t, fill=C["titolo"]), cv.configure(cursor="")))
        return yl + 20      # aria fra il filo del gruppo e le schede (7 nov 2026)

    def ridisegna_vis(self):
        """Dopo un cambio di regola di un gruppo: le testate e le pillole dei mazzi, senza rifare le schede."""
        for m, c in zip(self.mazzi, self.scatole):
            if getattr(c, "box_vis", None) is not None:
                c.box_vis = self.vis_mazzo(c, m)
        self.disponi(self.cv.winfo_width(), forza=True)

    def cambia_gruppo(self, chiave):
        GRUPPI_CHIUSI.symmetric_difference_update({chiave})
        salva_gruppi()
        self.disponi(self.cv.winfo_width(), forza=True)

    def disegna_mazzi(self):
        pass
