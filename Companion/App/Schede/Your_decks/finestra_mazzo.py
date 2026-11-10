"""La finestra di un mazzo."""
import mazzi_salvati as MS

from pagina_base import Pagina
from tema import CI as C, barra_scura


class FinestraMazzo:
    """La finestra di un mazzo, sopra il Companion: si apre col clic su un mazzo di Your decks, del Meta o di Performance, coi pulsanti delle azioni."""
    IN_VISTA = None     # la pagina che ha la finestra del mazzo aperta: una per volta in tutto il Companion
    MAZZI = None        # la pagina Your decks: il builder aperto da un'altra pagina salva li'

    def apri(self, chi):
        """chi: ("mio", nome), ("meta", archetipo del meta) o ("farm", mazzo del farming). None torna al grafico."""
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
        if self.fin is None or not self.fin.winfo_exists():
            top = self.fr.winfo_toplevel()
            f = self.fin = tk.Toplevel(top, bg=C["fondo"])
            f.transient(top)
            top.update_idletasks()
            L, H = max(1000, min(1320, top.winfo_width() - 60)), max(640, min(1000, top.winfo_height() - 40, f.winfo_screenheight() - 90))
            f.geometry(f"{L}x{H}+{top.winfo_rootx() + (top.winfo_width() - L) // 2}+{top.winfo_rooty() + (top.winfo_height() - H) // 2}")
            f.minsize(1000, 640)
            self.alto_fin = H
            f.protocol("WM_DELETE_WINDOW", lambda: self.apri(None))
            f.bind("<Escape>", lambda e: self.apri(None))
            barra_scura(f, C["fondo"], C["titolo"], C["filo"])
            self.det = tk.Frame(f, bg=C["scheda"]); self.det.pack(fill="both", expand=True)
        self.fin.title(titolo)
        for w in self.det.winfo_children():
            w.destroy()
        return self.fin

    def disegna_dettaglio(self):
        """Un mazzo cliccato si apre nella sua finestra, sopra il Companion e piu' ordinata (Autore, 6 nov 2026: «i decks cliccati si aprono in una nuova finestra sovraimpressa piu' ordinata»): a sinistra
        la lista, a destra i dati dall'alto in basso. E' la stessa da Performance e da Your decks. Si chiude con la X o con Esc."""
        if not self.aperto:
            if self.fin is not None and self.fin.winfo_exists():
                self.fin.destroy()
            self.fin = self.det = None
            return
        tipo_, chi_ = self.aperto
        am = self.mazzo_arena(chi_) if tipo_ == "mio" else None
        self.finestra_mazzo(am["nome"] if am else chi_ if tipo_ == "mio" else chi_.get("nome", "Deck"))
        self.scheda_mazzo()
        self.fin.lift(); self.fin.focus_set()

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
            nuovo = MS.aggiungi("build", dict(base, nome=f"{nome} (lab)" if tipo != "build" else f"{nome} copy")); self.fin.after(10, lambda: self.apri(("build", nuovo))); return "Copied to Deck building"

        gia = tipo != "wish" and MS.in_wishlist(base) is not None       # un mazzo gia' in wishlist non ha Add to wishlist
        if tipo == "meta":
            return ([] if gia else [("Add to wishlist", a_wish, False)]) + [("Copy to Deck building", a_build, False)]
        if tipo == "wish":
            return [("Edit", lambda: (self.builder("wish", chi), None)[1], False), ("Copy to Deck building", a_build, False)]      # togliere: il cestino sulla scheda (9 nov 2026)
        if tipo == "build":
            return [("Edit", lambda: (self.builder("build", chi), None)[1], False)] + ([] if gia else [("Add to wishlist", a_wish, False)])
        if tipo == "mio":
            return [("Copy to Deck building", a_build, False)]
        return []

    def builder(self, sez="build", m=None):
        """Il builder dei mazzi (costruttore_mazzi.py) sopra la Collection: la finestra grande passa alla Collection, da cui si trascinano le carte. La finestra del mazzo si chiude.
        Con All accounts no: si cambia il mazzo di un account, sceglilo nella tendina in alto."""
        import account
        if account.sola_lettura():
            return None
        import costruttore_mazzi
        pg = FinestraMazzo.MAZZI or self
        if self.aperto:
            self.apri(None)
        if Pagina.MOSTRA_SCHEDA is not None:
            Pagina.MOSTRA_SCHEDA("collezione")
        return costruttore_mazzi.Costruttore(pg, sez, m)

    def cliccabile(self, riga, chi):
        """Un clic su una riga apre il mazzo a sinistra (un secondo clic sullo stesso lo chiude)."""
        for c in riga:
            for w in [c] + list(c.winfo_children()):
                w.configure(cursor="hand2")
                w.bind("<Button-1>", lambda e, chi=chi: self.apri(None if self.aperto == chi else chi))
