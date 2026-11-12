"""La finestra di un mazzo."""
import mazzi_salvati as MS
import piattaforma
from widget import smonta

from pagina_base import Pagina
from tema import CI as C, barra_scura


def tk_frame(f):
    """Il contenitore vuoto della finestra del mazzo, montato."""
    import tkinter
    d = tkinter.Frame(f, bg=C["scheda"]); d.pack(fill="both", expand=True)
    return d



EDIT = "Edit this deck"     # il pulsante che porta al builder (12 nov 2026, Autore: «edit in edit this deck e affiancali» al Board view)

class FinestraMazzo:
    """La finestra di un mazzo, sopra il Companion: si apre col clic su un mazzo di Your decks, del Meta o di Performance, coi pulsanti delle azioni."""
    IN_VISTA = None     # la pagina che ha la finestra del mazzo aperta: una per volta in tutto il Companion
    MAZZI = None        # la pagina Your decks: il builder aperto da un'altra pagina salva li'

    def apri(self, chi):
        """chi: ("mio", nome), ("meta", archetipo del meta) o ("farm", mazzo del farming). None torna al grafico. Un altro mazzo riparte senza il filtro on the play / on the draw."""
        if chi != getattr(self, "aperto", None):
            self.partenza = self.partenza_an = self.partenza_wr = None
            import sezioni_mazzo
            sezioni_mazzo.nuovo_mazzo()     # un altro mazzo: le sezioni partono chiuse (12 nov 2026)
        self.aperto = chi
        self.disegna_dettaglio()
        self.disegna_mazzi()

    def finestra_mazzo(self, titolo):
        """La finestra del mazzo, sopra il Companion: una sola, un altro clic ne cambia il contenuto. transient: sta sopra la sua finestra, non sopra Arena (niente topmost)."""
        tk = self.tk
        altra = FinestraMazzo.IN_VISTA
        if altra is not None and altra is not self and altra.aperto:
            altra.apri(None)
        FinestraMazzo.IN_VISTA = self
        riposo = getattr(self, "fin_riposo", None)
        if (self.fin is None or not self.fin.winfo_exists()) and riposo is not None and riposo.winfo_exists():
            # la finestra chiusa prima e' rimasta, nascosta (11 nov 2026): si riusa. Gia' impaginata alla sua misura, il contenuto nuovo si impagina giusto
            # anche da nascosta, e si mostra a contenuto fatto
            self.fin, self.fin_riposo = riposo, None
            self.fin.riusata = True
            self.det = getattr(riposo, "det_vuoto", None)
        if getattr(self.fin, "riusata", False):        # al centro della finestra grande, come una finestra nuova
            L, H, posto = self.misura_fin(self.fin)
            self.fin.geometry(f"{L}x{H}{posto}")
            self.alto_fin = H
        if self.fin is None or not self.fin.winfo_exists():
            top = self.fr.winfo_toplevel()
            f = self.fin = tk.Toplevel(top, bg=C["fondo"])
            f.nuova = True
            f.transient(top)
            L, H, f.posto = self.misura_fin(f)
            if piattaforma.WINDOWS:
                # la prima volta si impagina fuori dallo schermo, alla sua misura vera, e poi si sposta al suo posto (11 nov 2026): una finestra nascosta si
                # impagina alla misura che il contenuto chiede, non alla sua (Windows le da' la misura solo quando compare), e la misura giusta costava un
                # secondo giro. Su Mac fuori schermo non si sa se resta fuori: nascosta come prima
                f.geometry(f"{L}x{H}+-12000+-12000")      # (-32000 e' il posto delle finestre ridotte a icona)
            else:
                f.withdraw()
                f.geometry(f"{L}x{H}{f.posto}")
            f.minsize(1000, 640)
            self.alto_fin = H
            f.protocol("WM_DELETE_WINDOW", lambda: self.apri(None))
            f.bind("<Escape>", lambda e: self.apri(None))
            barra_scura(f, C["fondo"], C["titolo"], C["filo"])
            self.det = tk.Frame(f, bg=C["scheda"]); self.det.pack(fill="both", expand=True)
        self.fin.title(titolo)
        # il contenuto di prima si stacca subito e si distrugge dopo, a pezzi (11 nov 2026, sessione Magic 13): distruggere ~200 widget costava 150 ms prima che il
        # mazzo nuovo potesse comparire
        vecchio = self.det
        self.det = tk.Frame(self.fin, bg=C["scheda"]); self.det.pack(fill="both", expand=True)
        if vecchio is not None:
            vecchio.pack_forget()
            smonta(vecchio)
        return self.fin

    def misura_fin(self, f):
        """La misura della finestra del mazzo e il suo posto, al centro della finestra grande: (L, H, «+x+y»)."""
        top = self.fr.winfo_toplevel()
        top.update_idletasks()
        L, H = max(1000, min(1320, top.winfo_width() - 60)), max(640, min(1000, top.winfo_height() - 40, f.winfo_screenheight() - 90))
        return L, H, f"+{top.winfo_rootx() + (top.winfo_width() - L) // 2}+{top.winfo_rooty() + (top.winfo_height() - H) // 2}"

    def disegna_dettaglio(self):
        """Un mazzo cliccato si apre nella sua finestra, sopra il Companion e piu' ordinata (Autore, 6 nov 2026: «i decks cliccati si aprono in una nuova finestra sovraimpressa piu' ordinata»): a sinistra
        la lista, a destra i dati dall'alto in basso. E' la stessa da Performance e da Your decks. Si chiude con la X o con Esc."""
        if not self.aperto:
            if self.fin is not None and self.fin.winfo_exists():
                # non si distrugge: si nasconde e si riusa al prossimo mazzo (11 nov 2026). Il contenuto se ne va a pezzi, a finestra libera
                f = self.fin
                f.withdraw()
                if self.det is not None:
                    vecchio = self.det
                    f.det_vuoto = tk_frame(f)
                    vecchio.pack_forget()
                    smonta(vecchio)
                self.fin_riposo = f
            self.fin = self.det = None
            return
        tipo_, chi_ = self.aperto
        am = self.mazzo_arena(chi_) if tipo_ == "mio" else None
        self.finestra_mazzo(am["nome"] if am else chi_ if tipo_ == "mio" else chi_.get("nome", "Deck"))
        self.scheda_mazzo()
        f = self.fin
        if getattr(f, "nuova", False):       # la prima volta: impaginata e disegnata fuori schermo (Windows) o nascosta, poi al suo posto
            f.nuova = False
            if piattaforma.WINDOWS:
                self.al_posto(f)
            else:
                f.update_idletasks()
                f.deiconify()
        elif getattr(f, "riusata", False):
            f.riusata = False
            f.deiconify()
        f.lift(); f.focus_set()

    def al_posto(self, f, n=0):
        """La finestra nuova, fuori schermo, va al suo posto quando Tk le ha dato la misura vera e le liste si sono disegnate (i loro timer da 1 ms): al
        massimo 0,4 s, poi ci va comunque."""
        try:
            if not f.winfo_exists():
                return
            if n < 25 and (self.det is None or self.det.winfo_width() <= 1):
                f.after(16, lambda: self.al_posto(f, n + 1))
                return
            f.after(5, lambda: f.winfo_exists() and f.geometry(f.posto))
        except Exception:
            pass

    def formato_mazzo(self, tipo, chi):
        """Il formato di un mazzo per i conti (legalita', meta simile) e per le copie: quello di Arena per i tuoi, quello scritto per meta, wishlist e build. Uno che non si conosce: Standard."""
        fmt = (chi.get("formato") if isinstance(chi, dict) else None) or (self.t_fmt.get() if hasattr(self, "t_fmt") else None) or "Standard"
        if tipo == "mio":
            am = self.mazzo_arena(chi) or {}
            fmt = {"TraditionalStandard": "Standard", "TraditionalExplorer": "Explorer", "HistoricBrawl": "Brawl", "StandardBrawl": "Standard Brawl"}.get(am.get("formato"), am.get("formato") or "Standard")
        return fmt if fmt in MS.FORMATI else "Standard"

    def azioni_mazzo(self, tipo, chi, nome, main, side, comandante, compagno):
        """I pulsanti sotto l'esportazione: dal meta in wishlist, ogni mazzo nelle build, la build si modifica. Si toglie col cestino sulla scheda, non da qui (Autore, 9 nov 2026).
        Con All accounts nessuno: wishlist e Deck building sono in sola lettura (10 nov 2026, Magic 12)."""
        import account
        if account.sola_lettura():
            return []
        base = dict(nome=nome, lista=main, side=side, comandante=comandante, compagno=compagno, formato=self.formato_mazzo(tipo, chi))
        if isinstance(chi, dict) and chi.get("url"):
            base["fonte"] = chi["url"]

        def a_wish():       # poi la finestra si rifa' senza il pulsante: il mazzo e' gia' in wishlist
            MS.aggiungi("wish", base); self.fin.after(1200, lambda: self.fin is not None and self.fin.winfo_exists() and self.aperto and self.apri(self.aperto)); return "Added to wishlist"

        def a_build():
            nuovo = MS.aggiungi("build", dict(base, nome=f"{nome} (lab)" if tipo != "build" else f"{nome} copy")); self.fin.after(10, lambda: self.apri(("build", nuovo))); return "Copied to Deck builder"

        def a_edit():
            # Edit su un mazzo che non e' tuo da cambiare (del Meta, di Arena, tuo su Arena): nasce subito la sua copia in Your decks > Deck builder e si apre nel
            # builder, editabile (Autore, 10 nov 2026: «a questi mazzi devi aggiungere un pulsante: edit / quando premo edit diventano editabili e nasce subito una
            # loro copia in your decks > deck building»). L'originale non cambia
            nuovo = MS.aggiungi("build", dict(base, nome=nome))
            if nuovo is not None:
                self.fin.after(10, lambda: self.builder("build", nuovo))
            return "Copied to Deck builder"

        gia = tipo != "wish" and MS.in_wishlist(base) is not None       # un mazzo gia' in wishlist non ha Add to wishlist
        if tipo == "meta":
            return [(EDIT, a_edit, False)] + ([] if gia else [("Add to wishlist", a_wish, False)])
        if tipo == "wish":
            return [(EDIT, lambda: (self.builder("wish", chi), None)[1], False), ("Copy to Deck builder", a_build, False)]      # togliere: il cestino sulla scheda (9 nov 2026)
        if tipo == "build":
            def a_clona():      # 12 nov 2026: la copia nasce in Deck builder e la finestra passa a lei
                pg = FinestraMazzo.MAZZI or self
                nuovo = pg.clona("build", chi) if hasattr(pg, "clona") else None
                if nuovo is not None:
                    self.fin.after(10, lambda: self.apri(("build", nuovo)))
                return "Cloned" if nuovo is not None else None
            return ([(EDIT, lambda: (self.builder("build", chi), None)[1], False)] + ([] if gia else [("Add to wishlist", a_wish, False)])
                    + [("Clone deck", a_clona, False)])
        if tipo == "mio":
            return [(EDIT, a_edit, False)]
        return []

    def builder(self, sez="build", m=None):
        """Il builder dei mazzi (costruttore_mazzi.py) sopra la Collection: la finestra grande passa alla Collection, da cui si trascinano le carte. La finestra del mazzo si chiude.
        Con All accounts no: si cambia il mazzo di un account, sceglilo nella tendina in alto."""
        import account
        if account.sola_lettura():
            return None
        import costruttore_mazzi
        pg = FinestraMazzo.MAZZI or self
        b = costruttore_mazzi.Costruttore.APERTO
        if b is not None and b.w.winfo_exists() and b.da_salvare():       # un builder aperto con modifiche: prima la sua domanda, poi il mazzo nuovo (12 nov 2026)
            b.chiudi(poi=lambda: self.builder(sez, m))
            return None
        if self.aperto:
            self.apri(None)
        if Pagina.MOSTRA_SCHEDA is not None:
            Pagina.MOSTRA_SCHEDA("collezione")
        return costruttore_mazzi.Costruttore(pg, sez, m)

    def cliccabile(self, riga, chi):
        """Un clic su una riga apre il mazzo a sinistra (un secondo clic sullo stesso lo chiude)."""
        if hasattr(riga, "cliccabile"):       # una riga della tabella su tela (tabella_tela.RigaTela)
            riga.cliccabile(lambda: self.apri(None if self.aperto == chi else chi), accesa=False)
            return
        for c in riga:
            for w in [c] + list(c.winfo_children()):
                w.configure(cursor="hand2")
                w.bind("<Button-1>", lambda e, chi=chi: self.apri(None if self.aperto == chi else chi))
