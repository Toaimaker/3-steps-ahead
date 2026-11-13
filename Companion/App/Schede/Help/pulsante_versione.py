"""Il pulsante della versione in fondo a destra, in ogni scheda (13 nov 2026, Autore: «fai in modo che l'utente possa uploadare all'ultima versione da un
pulsante ben visibile in basso a destra nell'app. se la versione e aggiornata il pulsante dice aggiornato all'ultima versione, altrimenti dice download n
versione»).

Legge l'esito del controllo degli aggiornamenti che fa la scheda Help (aggiornamenti.py: all'avvio e ogni 6 ore, Log_Arena/aggiornamenti_stato.json):
- versione nuova: pillola arancio piena «Download version X», il clic apre il link dell'aggiornamento nel browser (PaginaHelp.scarica: l'app non scarica e
  non installa niente da sola);
- aggiornata: pillola col bordo verde «Up to date · latest version X», il clic ricontrolla;
- non ancora controllata, errore, nessun canale: pillola grigia «Check for updates · vX», il clic controlla; durante il controllo «Checking for updates…».
"""
import os, sys
_casa = os.path.dirname(os.path.abspath(__file__))
while not os.path.isfile(os.path.join(_casa, "percorsi.py")):
    _casa = os.path.dirname(_casa)
if _casa not in sys.path:
    sys.path.insert(0, _casa)
import percorsi  # noqa: E402,F401
import disegni as DG  # noqa: E402
from ambiente import VERSIONE  # noqa: E402
from tema import CI as C  # noqa: E402
from widget import ARANCIO  # noqa: E402

ALTO = 26


def testo_e_stile(stato, controllo=False, attuale=VERSIONE):
    """-> (testo, tipo) per l'esito del controllo: tipo «nuova», «aggiornata», «controllo» o «altro»."""
    st = stato or {}
    if st.get("stato") == "nuova" and st.get("download"):
        return f"⬇  Download version {st.get('ultima')}", "nuova"
    if controllo:
        return "Checking for updates…", "controllo"
    if st.get("stato") == "aggiornata":
        return f"✓  Up to date · latest version {attuale}", "aggiornata"
    return f"Check for updates · v{attuale}", "altro"


class PulsanteVersione:
    def __init__(self, tk, F, padre, help_pagina, bg=None):
        self.F, self.help = F, help_pagina
        self.bg = bg or C["fondo"]
        self.c = tk.Canvas(padre, height=ALTO, width=200, bg=self.bg, highlightthickness=0, bd=0, cursor="hand2")
        self.sopra = False
        self.controllo = False
        self.testo, self.tipo = "", ""
        self.c.bind("<Button-1>", lambda e: self.clic())
        self.c.bind("<Enter>", lambda e: self._sopra(True))
        self.c.bind("<Leave>", lambda e: self._sopra(False))
        self.aggiorna()

    def _sopra(self, v):
        self.sopra = v
        self.disegna()

    def aggiorna(self):
        """L'esito nuovo della scheda Help (la chiama la finestra quando Help ha controllato)."""
        self.controllo = False      # Help chiama mostra_stato solo a controllo finito
        self.testo, self.tipo = testo_e_stile(getattr(self.help, "stato", None), False)
        self.disegna()

    def disegna(self):
        c, F = self.c, self.F
        c.delete("all")
        i_ = c.create_text(0, 0, text=self.testo, font=F(9, True), anchor="nw")
        bb = c.bbox(i_)
        c.delete(i_)
        larga = (bb[2] - bb[0]) + 30 if bb else 200
        c.configure(width=larga)
        if self.tipo == "nuova":
            fondo = ARANCIO[1] if self.sopra else ARANCIO[0]
            bordo, scritta = fondo, "#ffffff"
        elif self.tipo == "aggiornata":
            fondo = "#17301f" if self.sopra else C["fondo"]
            bordo, scritta = C["verde"], C["verde_t"]
        else:
            fondo = C["cap"] if self.sopra else C["fondo"]
            bordo, scritta = C["filo"] if not self.sopra else C["grigio"], C["grigio"] if not self.sopra else C["testo"]
        c.create_image(0, 0, anchor="nw", image=DG.pillola(larga, ALTO, bordo, fondo), tags="fondo")
        c.create_text(larga / 2, ALTO / 2, text=self.testo, fill=scritta, font=F(9, True), tags="testo")

    def clic(self):
        """Versione nuova: il link nel browser. Altrimenti un controllo adesso."""
        if self.tipo == "nuova":
            return self.help.scarica()
        if self.tipo == "controllo":
            return False
        self.controllo = True
        self.testo, self.tipo = testo_e_stile(None, True)
        self.disegna()
        self.help.controlla_ora()
        return True


def prova():
    """Fuori schermo, con una scheda Help finta: i tre testi, il colore, il clic (scarica o controlla); negative: senza link niente Download, durante il
    controllo il clic non rilancia."""
    import tkinter as tk
    root = tk.Tk(); root.geometry("600x80+7000+0")
    F = lambda n, g=False: ("Segoe UI", n, "bold" if g else "normal")

    class Help:
        stato = None
        def __init__(self):
            self.scaricati, self.controlli = [], []
        def scarica(self):
            self.scaricati.append(self.stato["download"]); return True
        def controlla_ora(self, url=None):
            self.controlli.append(1)
    h = Help()
    p = PulsanteVersione(tk, F, root, h); p.c.pack(); root.update()
    scritta = lambda: p.c.itemcget(p.c.find_withtag("testo")[0], "text")
    casi = []
    casi.append(("mai controllato: «Check for updates · vX», il clic controlla e dice Checking", scritta() == f"Check for updates · v{VERSIONE}"
                 and p.clic() and h.controlli == [1] and scritta() == "Checking for updates…"))
    casi.append(("negativa: durante il controllo il clic non rilancia", p.clic() is False and h.controlli == [1]))
    h.stato = {"stato": "aggiornata", "ultima": VERSIONE}
    p.aggiorna(); root.update()
    casi.append(("aggiornata: «Up to date · latest version X», verde", scritta() == f"✓  Up to date · latest version {VERSIONE}"
                 and p.c.itemcget(p.c.find_withtag("testo")[0], "fill") == C["verde_t"]))
    h.stato = {"stato": "nuova", "ultima": "9.9.9", "download": "https://example.org/x.exe"}
    p.aggiorna(); root.update()
    larga_n = int(p.c.cget("width"))
    casi.append(("versione nuova: «Download version 9.9.9», bianco su arancio, il clic apre il link", scritta() == "⬇  Download version 9.9.9"
                 and p.c.itemcget(p.c.find_withtag("testo")[0], "fill") == "#ffffff" and p.clic() and h.scaricati == ["https://example.org/x.exe"]))
    casi.append(("la pillola e' larga quanto la scritta", 140 < larga_n < 400))
    h.stato = {"stato": "nuova", "ultima": "9.9.9"}
    p.aggiorna(); root.update()
    casi.append(("negativa: una versione nuova senza link non e' un Download", not scritta().startswith("⬇")))
    root.destroy()
    for n, ok in casi:
        print(("ok    " if ok else "ROSSO ") + n)
    print(f"{sum(1 for _n, ok in casi if ok)}/{len(casi)}")
    return all(ok for _n, ok in casi)


if __name__ == "__main__":
    sys.exit(0 if prova() else 1)
