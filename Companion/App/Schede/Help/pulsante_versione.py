"""Il pulsante della versione in fondo a destra, in ogni scheda (13 nov 2026, Autore: «fai in modo che l'utente possa uploadare all'ultima versione da un
pulsante ben visibile in basso a destra nell'app. se la versione e aggiornata il pulsante dice aggiornato all'ultima versione, altrimenti dice download n
versione»).

Legge l'esito del controllo degli aggiornamenti che fa la scheda Help (aggiornamenti.py: all'avvio e ogni 6 ore, Log_Arena/aggiornamenti_stato.json):
- versione nuova: arancio «Download version X» con la freccia, il clic apre il link dell'aggiornamento nel browser (PaginaHelp.scarica: l'app non scarica e
  non installa niente da sola);
- aggiornata: verde «Up to date · latest version X» con la spunta, il clic ricontrolla;
- non ancora controllata, errore, nessun canale: grigio «Check for updates · vX» con la freccia che gira, il clic controlla; durante il controllo
  «Checking for updates…».
Dal 14 nov 2026 nello stile S3 dei pulsanti (widget.disegna_s3; Autore: «ogni pulsante esistente deve avere il redesign in linea con lo stile»): fino a
quel giorno era una pillola col bordo.
"""
import os, sys
_casa = os.path.dirname(os.path.abspath(__file__))
while not os.path.isfile(os.path.join(_casa, "percorsi.py")):
    _casa = os.path.dirname(_casa)
if _casa not in sys.path:
    sys.path.insert(0, _casa)
import percorsi  # noqa: E402,F401
from ambiente import VERSIONE  # noqa: E402
from tema import CI as C  # noqa: E402
from widget import ARANCIO, VERDE_P, disegna_s3  # noqa: E402

GRIGIO_V = ("#3a3a40", "#4a4a52", "#2c2c30")
STILE = {"nuova": (ARANCIO, "download"), "aggiornata": (VERDE_P, "spunta")}       # gli altri: grigio, la freccia che gira

ALTO = 26


def testo_e_stile(stato, controllo=False, attuale=VERSIONE):
    """-> (testo, tipo) per l'esito del controllo: tipo «nuova», «aggiornata», «controllo» o «altro»."""
    st = stato or {}
    if st.get("stato") == "nuova" and st.get("download"):
        return f"Download version {st.get('ultima')}", "nuova"
    if controllo:
        return "Checking for updates…", "controllo"
    if st.get("stato") == "aggiornata":
        return f"Up to date · latest version {attuale}", "aggiornata"
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
        c.delete("all"); c._s3 = []
        larga = int(c.tk.call("font", "measure", F(9, True), self.testo)) + 30 + ALTO + 6
        c.configure(width=larga)
        self.colori, icona = STILE.get(self.tipo, (GRIGIO_V, "ricarica"))
        disegna_s3(c, 0, 0, larga, ALTO, self.testo, F(9, True), self.colori, self.sopra, icona=icona)

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
    casi.append(("aggiornata: «Up to date · latest version X», verde", scritta() == f"Up to date · latest version {VERSIONE}" and p.colori == VERDE_P))
    h.stato = {"stato": "nuova", "ultima": "9.9.9", "download": "https://example.org/x.exe"}
    p.aggiorna(); root.update()
    larga_n = int(p.c.cget("width"))
    casi.append(("versione nuova: «Download version 9.9.9», bianco su arancio, il clic apre il link", scritta() == "Download version 9.9.9"
                 and p.colori == ARANCIO and p.c.itemcget(p.c.find_withtag("testo")[0], "fill") == "#ffffff" and p.clic() and h.scaricati == ["https://example.org/x.exe"]))
    casi.append(("la pillola e' larga quanto la scritta", 140 < larga_n < 400))
    h.stato = {"stato": "nuova", "ultima": "9.9.9"}
    p.aggiorna(); root.update()
    casi.append(("negativa: una versione nuova senza link non e' un Download", not scritta().startswith("Download")))
    root.destroy()
    for n, ok in casi:
        print(("ok    " if ok else "ROSSO ") + n)
    print(f"{sum(1 for _n, ok in casi if ok)}/{len(casi)}")
    return all(ok for _n, ok in casi)


if __name__ == "__main__":
    sys.exit(0 if prova() else 1)
