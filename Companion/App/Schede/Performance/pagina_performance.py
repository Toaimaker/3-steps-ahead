"""La scheda Performance: Limited e Standard in una scheda sola, con la tendina Mode."""
from pagina_limited import PaginaLimited
from pagina_standard import PaginaStandard
from tema import CI as C
from widget import Tendina


def modo_iniziale(draft, partite, aperto):
    """Da dove parte Performance: Limited con un draft aperto, se no il formato dell'ultima partita giocata (a pari merito o senza partite, Limited)."""
    if aperto:
        return "Limited"
    ultimo = lambda xs: max((x["quando"].timestamp() for x in xs), default=0)
    return "Standard" if ultimo(partite or []) > ultimo(draft or []) else "Limited"


class PaginaPerformance:
    """Performance: Limited e Standard in una scheda sola, si passa dall'una all'altra con la tendina Mode (Autore, 4 nov 2026: «le tab limited e standard
    potrebbero essere accorpate in un unica tab che si chiama performance / si switcha da una tendina e quindi si aggiornano i dati in base al formato scelto»).
    Le due pagine restano quelle di sempre, una al posto dell'altra, ognuna con la sua tendina Mode in testa alla riga dei menu."""

    MODI = ("Limited", "Standard")

    def __init__(self, tk, padre, F, mana):
        self.fr = tk.Frame(padre, bg=C["fondo"])
        self.limited = PaginaLimited(tk, self.fr, F, mana)
        self.standard = PaginaStandard(tk, self.fr, F, mana)
        self.pagine = dict(Limited=self.limited, Standard=self.standard)
        self.tendine = {}
        self.deciso = False         # dopo la prima decisione, o dopo una tua scelta, il modo non cambia piu' da solo
        for m, pg in self.pagine.items():
            t = Tendina(tk, pg.barra_menu, "Mode", F, larga=150)
            t.fr.pack(side="left", padx=(0, 12), before=pg.esp.fr)
            t.opzioni(self.MODI, self.scegli)
            self.tendine[m] = t
        self.modo = None
        self.mostra("Limited")
        self.fr.bind("<Map>", lambda e: self.se_sporca(), add="+")
        self.fr.bind("<<Davanti>>", lambda e: self.se_sporca(), add="+")       # la finestra la porta davanti alle altre schede (9 nov 2026)     # la pagina dentro non riceve il Map quando torna la scheda

    def se_sporca(self):
        self.pagine[self.modo].se_sporca()

    def segna(self):
        for pg in self.pagine.values():
            pg.sporca = True

    def mostra(self, modo):
        self.modo = modo
        for pg in self.pagine.values():
            pg.fr.pack_forget()
        self.pagine[modo].fr.pack(fill="both", expand=True)
        for m, t in self.tendine.items():       # ogni pagina ha la sua tendina: quella nascosta torna al suo nome
            t.set(m)

    def scegli(self, modo):
        self.deciso = True
        self.mostra(modo)

    def parti(self, draft, partite, aperto):
        """Il modo di partenza, una volta sola, appena ci sono i dati."""
        if not self.deciso:
            self.deciso = True
            self.mostra(modo_iniziale(draft, partite, aperto))

    def disegna(self):
        for pg in self.pagine.values():
            pg.disegna()
