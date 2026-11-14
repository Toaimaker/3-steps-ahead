"""La scheda Meta: i mazzi piu' giocati di ogni formato, come schede."""
import collections
import os

import capsule as CAP
import collezione_carte as CC
import prezzi_carte as PZ

from account import PUBBLICA
from dati_app import RANGHI_META, nome_rango, rango_da_nome
from dati_meta import FORMATI_META, formati_con_dati, meta_mazzi, ranghi_formato
from pagina_base import Pagina, prepara_capsule
from pagina_mazzi import PaginaMazzi
import disegni as DG
import mazzi_salvati as MS
import dati_grafici as DGR
from icone import icona_set, nome_set
from vista_grafici import VistaGrafici
from tema import CI as C, FN, PERSA, RD, VINTA
from widget import PulsanteVista, Tendina

# la pagina senza dati: nell'app pubblica non c'e' il meta di terzi (Untapped e MTGGoldfish vietano di ridistribuirlo, Distribuzione/Business_Model.md
# sezione 5, 11 nov 2026): arrivera' dalle partite che gli utenti condividono
VUOTO = "The meta built from the games 3 Steps Ahead players share is coming soon" if PUBBLICA else "No meta data for this format yet"


class PaginaMeta(PaginaMazzi):
    """Meta, la prima scheda (Autore, 7 nov 2026: «una scheda nuova che sara' la prima di tutte: una scheda che parla dei mazzi meta di ogni formato / tipo mtgo goldfish /
    tutti i mazzi hanno la loro scheda cosi' come la abbiamo appena fatta»). In cima la tendina Format, coi formati di Arena (Untapped, rango platinum) e quelli di carta e di
    Magic Online (MTGGoldfish); sotto i mazzi piu' giocati come schede, come Your decks: la copertina, i colori, la quota, il win rate (o la forza, o i mazzi nei tornei), il
    prezzo delle carte vere. Il clic apre la finestra del mazzo, la stessa dei tuoi."""

    ORDINI = ("Meta share", "Win rate", "Price", "Cards you own", "Name")
    VISTE = ("Decks", "Charts")
    MARGINE_SU = 32     # 12 nov 2026, Autore: «in meta le schede mazzo partono troppo alte abbassiamo un po'» (in Your decks resta 14: sopra c'e' il titolo del gruppo)

    def __init__(self, tk, padre, F, mana):
        Pagina.__init__(self, tk, padre, F, mana)
        self.esp.fr.pack_forget()
        self.t_fmt = Tendina(tk, self.barra_menu, "Format", F, larga=170); self.t_fmt.fr.pack(side="left")
        formati = formati_con_dati()
        self.t_fmt.opzioni(formati, lambda o: self.cambia_formato()); self.t_fmt.set("Standard" if "Standard" in formati else formati[0])
        # la tendina Rank (11 nov 2026, Autore: «in meta dobbiamo aggiungere una tendina che ci mostra il meta anche per rank della classifica», «cioe' quali
        # mazzi si giocano di piu' in quale fascia di rank e con quale win rate»): i ranghi che Untapped da' gratis, Bronze-Platinum; c'e' solo nei formati di Arena
        # che hanno le partite per rango, e la scelta resta cambiando formato
        self.t_rango = Tendina(tk, self.barra_menu, "Rank", F, larga=170)
        self.t_rango.opzioni([nome_rango(r) for r in RANGHI_META], lambda o: self.cambia_formato(), icone=self.loghi_ranghi()); self.t_rango.set("Platinum")
        self.t_ord = Tendina(tk, self.barra_menu, "Sort by", F, larga=170); self.t_ord.fr.pack(side="left", padx=(10, 0))
        self.t_ord.opzioni(self.ORDINI, lambda o: self.riordina()); self.t_ord.set(self.ORDINI[0])
        # la vista Charts e il meta del limited (10 nov 2026, Autore: «una seconda sezione che non e' visualizzata a scacchiera ma a elenchi e ci fa vedere il
        # meta giocato per mazzo in termini di grafici», «includendo anche il meta del limited ovviamente»): View sceglie fra schede e grafici; nella tendina Format
        # in fondo Quick Draft e Premier Draft, coi set che hanno i dati (la tendina Set compare solo li'); il limited e' solo a grafici
        # dall'11 nov 2026 un pulsante, non una tendina, a destra sulla riga delle tendine: dice la vista in cui porta (Charts o Grid) e cambia forma
        # (Autore: «la view da decks a charts non deve essere una tendina ma un pulsante da premere che cambia forma da charts a grid»)
        self.t_vista = PulsanteVista(tk, self.barra_menu, F, self.VISTE); self.t_vista.fr.pack(side="right", padx=(10, 0))
        self.t_vista.opzioni(self.VISTE, lambda o: self.cambia_formato())
        self.t_set = Tendina(tk, self.barra_menu, "Set", F, larga=220)
        self.formati_lim = [f for f, k in DGR.LIMITED if DGR.set_limited(k)]
        if self.formati_lim:
            self.t_fmt.opzioni(list(self.t_fmt.voci) + self.formati_lim, lambda o: self.cambia_formato())
        self.vista_g = None; self.larga_g = 0
        self.col[1].grid_remove(); self.col[0].grid(row=2, column=0, columnspan=2, sticky="nsew", padx=0)
        self.dati = None; self.pp = []; self.aperto = None; self.premi = None; self.farm = []; self.fin = self.det = None
        self.arena = {}
        self.mazzi, self.scatole, self.foto, self.colonne, self.sporco = [], [], {}, 0, True
        self.da_cuocere, self.cotte, self.cottura = collections.deque(), collections.deque(), None
        self.lista = CAP.Liste(tk, F)
        self.area("Meta")
        self.sotto = ""
        self.firma_file = self.firma()
        self.cv.after(self.OGNI_MS, self.guarda_file)

    OGNI_MS = 60000

    @staticmethod
    def firma():
        """L'ora dei file del meta (Untapped e MTGGoldfish, Note/): cambia quando il giro dello scout li riscrive (ogni 6 ore)."""
        import glob
        from ambiente import ROOT
        out = []
        for p in sorted(glob.glob(os.path.join(ROOT, "Note", "meta_untapped*.json")) + glob.glob(os.path.join(ROOT, "Note", "meta_goldfish_*.json"))):
            try:
                out.append((os.path.basename(p), os.path.getmtime(p)))
            except OSError:
                pass
        return tuple(out)

    def guarda_file(self):
        """Ogni minuto: se il giro ha riscritto il meta, la pagina si rifa' (subito se e' davanti, se no quando ci torni). Fino al 10 nov 2026 il
        meta si leggeva solo al primo disegno e al cambio di formato: un giro con l'app aperta non si vedeva fino al riavvio."""
        try:
            f = self.firma()
            if f != self.firma_file:
                self.firma_file = f
                self.aggiorna()
        except Exception as e:      # la pagina non deve mai fermare il giro della finestra
            print("meta, controllo dei file:", e)
        try:
            self.cv.after(self.OGNI_MS, self.guarda_file)
        except Exception:
            pass

    def mazzo_arena(self, chi):
        return None

    def aggiorna(self, dati=None):
        self.sporco = True
        self.disegna()

    def cambia_formato(self):
        self.sporco = True
        self.disegna()
        self.cv.yview_moveto(0)

    # ------------------------------------------------------------------ la vista Charts (10 nov 2026)
    def limited(self):
        return dict(DGR.LIMITED).get(self.t_fmt.get())

    def grafici(self):
        return bool(self.limited()) or self.t_vista.get() == "Charts"

    def metti_set(self):
        """Nel limited la tendina Set, coi set che hanno il meta di quel formato (dal piu' nuovo, col simbolo); fuori la tendina sparisce. View si nasconde
        nel limited: li' ci sono solo i grafici (Untapped non da' le liste dei mazzi per coppia)."""
        lim = self.limited()
        if not lim:
            self.t_set.fr.pack_forget()
            if not self.t_vista.fr.winfo_manager():
                self.t_vista.fr.pack(side="right", padx=(10, 0))
            return
        self.t_vista.fr.pack_forget()
        sets = DGR.set_limited(lim)
        if not hasattr(self, "_loghi_set"):
            self._loghi_set = {}
        icone = {}
        for s in sets:
            if s not in self._loghi_set:
                f = icona_set(s, 16)
                self._loghi_set[s] = self.tk.PhotoImage(file=f) if f else None
            if self._loghi_set[s] is not None:
                icone[s] = self._loghi_set[s]
        scelto = self.t_set.get()
        self.t_set.opzioni(sets, lambda o: self.cambia_formato(), icone, {s: f"{nome_set(s)} ({s})" if nome_set(s) else s for s in sets})
        if scelto not in sets:
            self.t_set.set(self.set_iniziale(sets))
        if not self.t_set.fr.winfo_manager():
            self.t_set.fr.pack(side="left", padx=(10, 0), after=self.t_fmt.fr)

    def loghi_ranghi(self, alto=18):
        """I loghi delle leghe di Arena accanto ai ranghi della tendina (Autore, 11 nov 2026: «sulle leghe anche se in tendina mettiamo i loro loghi»);
        Diamond + Mythic coi due loghi affiancati. Un logo che manca lascia la voce senza."""
        from PIL import Image, ImageTk
        from icone import logo_lega
        out = {}
        for r in RANGHI_META:
            leghe = ("Diamond", "Mythic") if r == "mythic" else (r.capitalize(),)
            imm = [Image.open(f).convert("RGBA") for f in (logo_lega("constructed", lg, alto) for lg in leghe) if f]
            if not imm:
                continue
            tela = Image.new("RGBA", (sum(i.width for i in imm) + 2 * (len(imm) - 1), alto), (0, 0, 0, 0))
            x = 0
            for i in imm:
                tela.alpha_composite(i, (x, (alto - i.height) // 2)); x += i.width + 2
            out[nome_rango(r)] = ImageTk.PhotoImage(tela)
        self._loghi_ranghi = out       # le PhotoImage vivono finche' la pagina le tiene
        return out

    def rango(self):
        """Il rango scelto, se la tendina c'e' (formati di Arena con le partite per rango), se no None: il rango dello scarico."""
        return rango_da_nome(self.t_rango.get()) if self.t_rango.fr.winfo_manager() else None

    def metti_rango(self):
        """La tendina Rank c'e' nella vista a schede dei formati di Arena che hanno le partite per rango; nei formati di carta, nel limited e nei grafici no."""
        ranghi = [] if self.grafici() else ranghi_formato(self.t_fmt.get())
        if not ranghi:
            self.t_rango.fr.pack_forget()
            return
        voci = [nome_rango(r) for r in ranghi]
        if self.t_rango.get() not in voci:
            self.t_rango.set("Platinum" if "Platinum" in voci else voci[-1])
        if not self.t_rango.fr.winfo_manager():
            self.t_rango.fr.pack(side="left", padx=(10, 0), after=self.t_fmt.fr)

    @staticmethod
    def set_iniziale(sets):
        """Il set del drafter (percorsi.set_attivo: l'evento in corso, se no FRA) se ha i dati, se no il piu' nuovo."""
        try:
            import percorsi
            s = percorsi.set_attivo()
        except Exception:
            s = None
        return s if s in sets else (sets[0] if sets else "")

    def chiave_grafico(self, m):
        o = self.t_ord.get()
        if o == "Win rate":
            return (m.get("wr") is None, -(m.get("wr") or 0), m.get("forza") or 999, -m["quota"])
        if o == "Price":
            return (-(m.get("eur") or 0), -m["quota"])
        if o == "Cards you own" and m.get("carte"):
            return (-(m.get("possedute") or 0) / max(m["carte"], 1), -m["quota"])
        if o == "Name":
            return (m["nome"].lower(),)
        return (-m["quota"],)

    def disegna_grafici(self):
        """La vista a elenco coi grafici (vista_grafici.py): costruito con le righe della vista a schede, limited con le coppie del set."""
        fmt, lim = self.t_fmt.get(), self.limited()
        self.alto_carte = 0
        if lim:
            s = self.t_set.get()
            righe = DGR.righe_limited(s, lim)
            st = DGR.storico(DGR.chiave_storico(fmt, s))
            self.storia_l = DGR.storia_17lands(s) if lim == "premier" else None      # 12 nov 2026: il Premier ha la storia intera dai dati pubblici di 17Lands
            if self.storia_l:
                st = DGR.storico("17lands_premier_" + s) or st
            self.sotto = f"{nome_set(s) or s} · {sum(r['partite'] for r in righe):,} games" if righe else ""
            self.mazzi = []
        else:
            self.storia_l = None
            righe, self.sotto = DGR.righe_costruito(fmt)
            st = DGR.storico(DGR.chiave_storico(fmt))
            self.mazzi = righe
        righe = sorted(righe, key=self.chiave_grafico)
        self.titolo.configure(text=f"{(fmt + (' ' + self.t_set.get() if lim else '')).upper()} META · {len(righe)} DECKS"
                              + (f" · {self.sotto.upper()}" if self.sotto else ""))
        if not righe:
            self.tk.Label(self.griglia_b, text=VUOTO, bg=C["scheda"], fg=C["grigio"], font=self.F(9)).pack(anchor="w")
            self.vista_g = None
            return
        self.larga_g = self.cv.winfo_width()
        self.vista_g = VistaGrafici(self, righe, not lim, st, self.larga_g)
        self.vista_g.disegna()
        self.alto_carte = 0         # 12 nov 2026: l'altezza delle schede della vista a griglia non vale qui (la pagina scorreva nel vuoto)
        self.griglia_b.update_idletasks()
        self.regione()

    def disponi(self, larga, forza=False):
        """In vista Charts i grafici si rifanno quando la larghezza cambia di molto; nelle schede la griglia di sempre."""
        if self.vista_g is not None:
            if abs(larga - self.larga_g) > 40:
                self.sporco = True
                self.cv.after_idle(self.disegna)
            return
        PaginaMazzi.disponi(self, larga, forza)

    def riordina(self):
        if self.grafici():
            self.sporco = True
            self.disegna()
            self.cv.yview_moveto(0)
            return
        PaginaMazzi.riordina(self)

    def disegna(self):
        if not self.davanti() and not Pagina.SUBITO:
            self.sporco = True
            return
        if not self.sporco and self.scatole:
            return
        self.sporco = False
        self.smista.svuota(); self.cv.delete("gruppo")
        self.svuota(self.griglia_b)
        # un Frame di Tk a cui si tolgono tutti i figli non si rimpicciolisce da solo: tornando da Charts a Grid restava alto quanto i grafici (546 pixel), vuoto,
        # sopra la prima riga di schede (Autore, 12 nov 2026: «quando passo da chart a grid la pagina grid si bugga»)
        self.griglia_b.configure(height=1)
        self.scatole = []
        if len(self.foto) > 150:         # le copertine di prima: le tele sono appena state distrutte, oltre 150 (30 MB) si liberano
            self.foto.clear()
        prepara_capsule(CC.carica())
        fmt = self.t_fmt.get()
        self.metti_set()
        self.metti_rango()
        if self.grafici():
            return self.disegna_grafici()
        self.vista_g = None
        mm, self.sotto = meta_mazzi(fmt, self.rango())
        self.mazzi = sorted(mm, key=self.chiave)
        self.titolo.configure(text=f"{fmt.upper()} META · {len(self.mazzi)} DECKS" + (f" · {self.sotto.upper()}" if self.sotto else ""))
        if not self.mazzi:
            self.tk.Label(self.griglia_b, text=VUOTO, bg=C["scheda"], fg=C["grigio"], font=self.F(9)).pack(anchor="w")
        for m in self.mazzi:
            self.scatole.append(self.scatola(m))
        self.disponi(self.cv.winfo_width(), forza=True)
        if self.aperto:
            self.disegna_dettaglio()

    def chiave(self, m):
        o = self.t_ord.get()
        if o == "Win rate":
            return (m.get("wr") is None, -(m.get("wr") or 0), m.get("forza") or 999, -m["quota"])
        if o == "Price":
            return (-(m.get("eur") or 0),)
        if o == "Cards you own":
            return (-(m.get("possedute") or 0) / max(m["carte"], 1), -m["quota"])
        if o == "Name":
            return (m["nome"].lower(),)
        return (-m["quota"],)

    def scatola(self, m):
        """Una scheda del meta, come quelle di Your decks: copertina, colori e posto, nome, tre dati sotto un filo, in fondo le carte che hai e il pulsante."""
        tk, F = self.tk, self.F
        L, H = self.LARGA, self.ALTA
        c = self.nuova_scatola()
        carta = dict(FORMATI_META).get(self.t_fmt.get()) == "carta"

        def disegna():
            c.delete("all")
            c.create_rectangle(0, 0, L - 1, H - 1, fill=RD["p0"], outline=RD["filo2"], tags="corpo")      # i colori del redesign del 14 nov 2026
            f = CAP.file_cover(m["arte"], *self.COVER) if m["arte"] else None
            if f and os.path.exists(f):
                if f not in self.foto:
                    from PIL import Image, ImageTk
                    self.foto[f] = ImageTk.PhotoImage(Image.open(f))
                c.create_image(1, 1, image=self.foto[f], anchor="nw")
            elif m["arte"]:
                self.cuoci(m, disegna)
            alto = self.COVER[1] + 1
            c.create_line(0, alto, L, alto, fill=RD["filo2"])
            x, dx_ = 14, L - 14
            y = alto + 20
            sx = x
            for k in [z for z in "WUBRG" if z in (m.get("colori") or "")]:
                img = self.lista.simbolo(k, 14)
                if img:
                    c.create_image(sx + 7, y, image=img)
                    sx += 17
            c.create_text(sx + (5 if sx > x else 0), y, text=CAP.nome_mazzo(m.get("colori") or "").upper(), anchor="w", fill=C["acciaio"], font=F(7, True))
            prezzo = PZ.euro(m["eur"]) if m.get("eur") else ""        # il prezzo di carta accanto al posto
            c.create_text(dx_, y, text=f"#{m['posto']}" + (f"  ·  {prezzo}" if prezzo else ""), anchor="e", fill=C["grigio"], font=F(8, True))
            nome = m["nome"] if len(m["nome"]) <= 30 else m["nome"][:29] + "…"
            c.create_text(x, y + 22, text=nome, anchor="w", fill=C["titolo"], font=FN(14))
            y0 = y + 42
            c.create_line(x, y0, dx_, y0, fill=RD["filo2"])
            if m.get("wr") is not None:
                secondo = ("WIN RATE", f"{m['wr']:.1f}%", VINTA if m["wr"] >= 50 else PERSA)
            elif m.get("forza"):
                secondo = ("STRENGTH", f"{m['forza']}°", C["testo"])
            elif m.get("rango_meta"):        # un rango scelto, fuori dallo Standard: le partite in quel rango
                secondo = ("GAMES", f"{m['partite']:,}", C["testo"])
            else:
                secondo = ("DECKS", f"{m['mazzi']:,}" if m.get("mazzi") else "-", C["testo"])
            # niente jolly e niente «x/60 owned» (o «on Arena») sulle schede del Meta (Autore, 10 nov 2026: «sulle schede di anteprima togliamo: wc necessarie /
            # x/x owned»): stanno nella finestra del mazzo. Quota e win rate grandi, sulla riga del pulsante (stesso giorno: «I dati di meta e win rate un po' piu'
            # grandi e tutto proporzionato anche al pulsante»)
            for xc, (t, v, col) in zip((x, x + 0.31 * (dx_ - x)), (("META", f"{m['quota']:.1f}%", C["accento"]), secondo)):
                c.create_text(xc, H - 52, text=t, anchor="w", fill=C["muto"], font=F(7, True))
                DG.numero(c, xc, H - 27, v, col, 18)      # Bahnschrift, il % piu' piccolo (redesign del 14 nov 2026)
            self.pulsante_scheda(c, dx_, H, "View deck")
            c.in_wish = None        # la wishlist si rilegge a ogni disegno della scheda, non a ogni movimento del mouse
            self.metti_stella(c, m, 0)
        disegna()
        if m["arte"]:
            self.lista.chiedi_arte(c, m["arte"], disegna)
        c.bind("<Enter>", lambda e: c.itemconfigure("corpo", fill=RD["p1"], outline=C["accento"]))
        c.bind("<Leave>", lambda e: (c.itemconfigure("corpo", fill=RD["p0"], outline=RD["filo2"]), self.metti_stella(c, m, 0)))
        c.bind("<Motion>", lambda e: self.metti_stella(c, m, 1 if self.su_stella(e) else 0))

        def clic(e):
            if self.su_stella(e):
                return self.cambia_wishlist(c, m)
            self.apri(("meta", m))
        c.bind("<Button-1>", clic)
        return c

    # la stellina della wishlist in alto a destra sulla copertina (Autore, 12 nov 2026: «sulle schede meta mettiamo in alto a destra un pulsante per wishlist»,
    # proposta D, «stellina»): vuota se il mazzo non e' in wishlist, piena d'oro se c'e'; il clic lo mette o lo toglie, senza aprire la finestra del mazzo
    STELLA = 30

    def box_stella(self):
        L = self.LARGA
        return L - 12 - self.STELLA, 10, L - 12, 10 + self.STELLA

    def su_stella(self, e):
        x0, y0, x1, y1 = self.box_stella()
        return x0 <= e.x <= x1 and y0 <= e.y <= y1

    def base_wishlist(self, m):
        """Il mazzo del meta come lo salva Add to wishlist della finestra del mazzo: lista, sideboard, comandante, compagno, formato, la pagina d'origine."""
        fmt = self.t_fmt.get()
        base = dict(nome=m["nome"], lista=dict(m.get("lista") or {}), side=dict(m.get("side") or {}), comandante=dict(m.get("comandante") or {}),
                    compagno=dict(m.get("compagno") or {}), formato=fmt if fmt in MS.FORMATI else "Standard")
        if m.get("url"):
            base["fonte"] = m["url"]
        return base

    def metti_stella(self, c, m, sotto):
        import account
        if account.sola_lettura() or not (m.get("lista") or {}):        # All accounts: la wishlist e' in sola lettura; senza lista non c'e' niente da salvare
            return
        if getattr(c, "in_wish", None) is None:
            c.in_wish = MS.in_wishlist(self.base_wishlist(m)) is not None
        stato = 2 if c.in_wish else sotto
        if stato == getattr(c, "stato_stella", None) and c.find_withtag("stella"):
            return
        c.stato_stella = stato
        x0, y0, _x1, _y1 = self.box_stella()
        c.delete("stella")
        c.create_image(x0, y0, image=DG.stellina(self.STELLA, stato), anchor="nw", tags="stella")

    def cambia_wishlist(self, c, m):
        """Il clic sulla stellina: il mazzo entra nella wishlist, o ne esce se c'era. -> True se ora e' in wishlist."""
        import account
        if account.sola_lettura():
            return None
        base = self.base_wishlist(m)
        w = MS.in_wishlist(base)
        if w is not None:
            MS.togli("wish", w["id"])
        else:
            MS.aggiungi("wish", base)
        c.in_wish = w is None
        self.metti_stella(c, m, 1)
        return w is None
