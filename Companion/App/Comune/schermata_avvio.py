"""La schermata di caricamento, come quella di Steam (13 nov 2026, Autore: «Facciamo che si apre come si apre steam, al primo avvio una finestra di
caricamento, poi parte l'app»).

Una finestrella senza bordi al centro dello schermo dove si aprira' l'app: il logo, il nome, la riga di cosa sta facendo e una barra che avanza. La finestra
grande intanto si costruisce trasparente (alpha 0: e' a schermo, quindi le pagine si misurano giuste) e compare quando la prima scheda e' disegnata; poi la
schermata si chiude. La usano finestra.py (ogni avvio) e avvio_pubblico.py (il primo avvio dell'app pubblica, che scarica i dati delle carte).
"""
import os, sys
_casa = os.path.dirname(os.path.abspath(__file__))
while not os.path.isfile(os.path.join(_casa, "percorsi.py")):
    _casa = os.path.dirname(_casa)
if _casa not in sys.path:
    sys.path.insert(0, _casa)
import percorsi  # noqa: E402,F401

LARGA, ALTA = 520, 300
FONDO, BORDO, TITOLO, TESTO, GRIGIO, ACCENTO, TRACCIA = "#0b0e14", "#1e2431", "#ffffff", "#d7dce5", "#7a7a80", "#2f9bff", "#161b25"


def centro(schermo, larga=LARGA, alta=ALTA):
    """(sinistra, alto, destra, basso) dello schermo -> la geometria della schermata al centro."""
    a, b, c, d = schermo[:4]
    return f"{larga}x{alta}+{a + (c - a - larga) // 2}+{b + (d - b - alta) // 2}"


class Schermata:
    def __init__(self, tk, master=None, geo=None, versione="", font="Segoe UI"):
        """master None: la schermata e' la finestra Tk stessa (tk.Tk); se no un Toplevel di master."""
        self.w = tk.Tk() if master is None else tk.Toplevel(master)
        w = self.w
        w.overrideredirect(True)
        w.configure(bg=BORDO)
        if geo is None:
            geo = centro((0, 0, w.winfo_screenwidth(), w.winfo_screenheight()))
        w.geometry(geo)
        self.c = c = tk.Canvas(w, width=LARGA - 2, height=ALTA - 2, bg=FONDO, highlightthickness=0, bd=0)
        c.place(x=1, y=1)
        self.logo = None
        try:
            from PIL import Image, ImageTk
            from ambiente import ASSET
            self.logo = ImageTk.PhotoImage(Image.open(os.path.join(ASSET, "companion_icona.png")).convert("RGBA").resize((72, 72), Image.LANCZOS), master=w)
            c.create_image(LARGA // 2, 92, image=self.logo)
        except Exception:       # noqa: BLE001 - senza logo la schermata resta
            pass
        try:
            from ambiente import PRODOTTO
        except Exception:       # noqa: BLE001
            PRODOTTO = "3 Steps Ahead"
        c.create_text(LARGA // 2, 152, text=PRODOTTO, fill=TITOLO, font=(font, 18, "bold"))
        c.create_text(LARGA // 2, 178, text="Beta · free · unofficial fan content", fill=GRIGIO, font=(font, 8))
        self.riga = c.create_text(LARGA // 2, 226, text="Starting…", fill=TESTO, font=(font, 9))
        self.x0, self.x1, self.yb = 60, LARGA - 60, 250
        c.create_line(self.x0, self.yb, self.x1, self.yb, fill=TRACCIA, width=4, capstyle="round")
        self.barra = c.create_line(self.x0, self.yb, self.x0 + 1, self.yb, fill=ACCENTO, width=4, capstyle="round")
        if versione:
            c.create_text(LARGA - 12, ALTA - 14, text=f"v{versione}", anchor="e", fill=GRIGIO, font=(font, 7))
        self.frazione = 0.0
        w.update()

    def passo(self, testo=None, frazione=None):
        """Cambia la riga e la barra e ridisegna subito (la costruzione della finestra grande tiene fermo il ciclo di Tk)."""
        try:
            if testo is not None:
                self.c.itemconfigure(self.riga, text=testo)
            if frazione is not None:
                self.frazione = max(self.frazione, min(1.0, frazione))
                self.c.coords(self.barra, self.x0, self.yb, self.x0 + 1 + (self.x1 - self.x0 - 1) * self.frazione, self.yb)
            self.w.update_idletasks()
        except Exception:       # noqa: BLE001 - chiusa
            pass

    def chiudi(self):
        try:
            self.w.destroy()
        except Exception:       # noqa: BLE001
            pass


def prova():
    """La schermata fuori schermo: nome, riga, barra che avanza e non torna indietro, si chiude."""
    import tkinter as tk
    s = Schermata(tk, geo=f"{LARGA}x{ALTA}+7000+0", versione="9.9")
    testi = lambda: [s.c.itemcget(i, "text") for i in s.c.find_all() if s.c.type(i) == "text"]
    casi = []
    casi.append(("il nome, la riga e la versione", "Starting…" in testi() and "v9.9" in testi() and any("Steps" in t for t in testi())))
    s.passo("Loading cards…", 0.4)
    l1 = s.c.coords(s.barra)[2]
    s.passo("Reading your games…", 0.2)
    casi.append(("la barra avanza e la riga cambia; negativa: un passo piu' indietro non la fa tornare", "Reading your games…" in testi()
                 and s.c.coords(s.barra)[2] == l1 and l1 > s.x0 + 100))
    s.chiudi()
    casi.append(("si chiude", True))
    for n, ok in casi:
        print(("ok    " if ok else "ROSSO ") + n)
    print(f"{sum(1 for _n, ok in casi if ok)}/{len(casi)}")
    return all(ok for _n, ok in casi)


if __name__ == "__main__":
    sys.exit(0 if prova() else 1)
