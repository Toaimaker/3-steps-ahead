"""Il Leak Finder chiuso mentre si gioca, nell'app pubblica (15 nov 2026, Autore: «il leak finder non deve essere utilizzabile quando arena o mtgo sono
aperti, solo la mia versione ma non quella pubblica, sono sistemi di analisi non devono diventare suggeritori in partita»).

Nell'app pubblica (account.PUBBLICA), finche' Arena (MTGA.exe) o Magic Online (MTGO.exe) e' aperto, la pagina e' coperta da un riquadro che dice perche', e le
sue finestre aperte (il replayer, Advanced filters, By deck, le cartelle staccate...) si nascondono; chiuso il gioco, il riquadro va via e le finestre tornano
come erano. Nell'app di Autore non succede niente: e' una sua scelta (la regola delle due app identiche cede a una decisione sua). Il controllo dei
processi gira su un filo ogni CADENZA secondi (tasklist costa ~100 ms e non deve fermare la finestra). Per provarlo: LEAK_BLOCCO=1 nell'ambiente lo accende
anche nell'app di Autore, LEAK_BLOCCO=0 lo spegne anche nella pubblica.

attacca(pagina) lo collega a una PaginaPerformance (usa pagina.tk, pagina.F, pagina.fr). prova() con la negativa.
"""
import os, sys
_casa = os.path.dirname(os.path.abspath(__file__))
while not os.path.isfile(os.path.join(_casa, "percorsi.py")):
    _casa = os.path.dirname(_casa)
if _casa not in sys.path:
    sys.path.insert(0, _casa)
import percorsi  # noqa: E402,F401
import threading  # noqa: E402
from tema import C  # noqa: E402

CADENZA = 4.0
TITOLO = "LEAK FINDER IS CLOSED WHILE YOU PLAY"
TESTO = ("Arena or Magic Online is open. The Leak Finder is an analysis tool for after your games, not an advisor during them: "
         "it comes back as soon as you close the game. Your games are still being recorded.")


def attivo():
    """Il blocco vale? Nell'app pubblica si', in quella di Autore no; LEAK_BLOCCO lo forza per le prove."""
    v = os.environ.get("LEAK_BLOCCO")
    if v in ("0", "1"):
        return v == "1"
    try:
        import account
        return bool(account.PUBBLICA)
    except Exception:       # noqa: BLE001 - senza il modulo dell'account e' l'app di Autore
        return False


def gioco_aperto():
    import piattaforma as P
    return P.arena_aperta() or P.mtgo_aperto()


class Blocco:
    def __init__(self, pagina, controllo=gioco_aperto):
        self.p, self.controllo = pagina, controllo
        self.aperto = False             # il gioco era aperto all'ultimo controllo
        self._letto = None              # l'esito del filo, preso dal giro di Tk
        self.velo, self.nascoste = None, []
        self._filo = None

    # il controllo dei processi su un filo, l'interfaccia dal giro di Tk
    def giro(self):
        try:
            if not self.p.fr.winfo_exists():
                return
        except Exception:       # noqa: BLE001 - la pagina distrutta: il giro finisce
            return
        if self._letto is not None:
            self.applica(self._letto)
            self._letto = None
        if self.velo is not None:
            self.velo.lift()                # la pagina che si ridisegna non passa sopra il velo
            for f in self.finestre():       # e una finestra della pagina aperta nel frattempo si nasconde
                f.withdraw()
                self.nascoste.append(f)
        if self._filo is None or not self._filo.is_alive():
            self._filo = threading.Thread(target=self._leggi, daemon=True)
            self._filo.start()
        self.p.fr.after(int(CADENZA * 1000), self.giro)

    def _leggi(self):
        try:
            self._letto = bool(self.controllo())
        except Exception:       # noqa: BLE001 - un controllo che cade non chiude la pagina
            self._letto = False

    def finestre(self):
        """Le finestre della pagina (Toplevel discendenti della sua cornice), quelle a vista."""
        out, coda = [], [self.p.fr]
        while coda:
            w = coda.pop()
            for f in w.winfo_children():
                if isinstance(f, self.p.tk.Toplevel):
                    try:
                        if f.winfo_exists() and f.state() != "withdrawn":
                            out.append(f)
                    except Exception:       # noqa: BLE001 - una finestra che si sta chiudendo
                        pass
                coda.append(f)
        return out

    def applica(self, aperto):
        if aperto and not self.aperto:
            self.chiudi()
        elif not aperto and self.aperto:
            self.riapri()
        self.aperto = aperto

    def chiudi(self):
        tk, F = self.p.tk, self.p.F
        for f in self.finestre():
            try:
                f.withdraw()
                self.nascoste.append(f)
            except Exception:       # noqa: BLE001
                pass
        v = self.velo = tk.Frame(self.p.fr, bg=C["fondo"])
        v.place(x=0, y=0, relwidth=1, relheight=1)
        v.lift()
        box = tk.Frame(v, bg=C["scheda"], highlightthickness=1, highlightbackground=C["azzurro"])
        box.place(relx=0.5, rely=0.42, anchor="center")
        tk.Label(box, text=TITOLO, bg=C["scheda"], fg=C["titolo"], font=F(14, True)).pack(padx=40, pady=(28, 10))
        tk.Label(box, text=TESTO, bg=C["scheda"], fg=C["testo"], font=F(10), wraplength=520, justify="center").pack(padx=40, pady=(0, 28))

    def riapri(self):
        if self.velo is not None:
            try:
                self.velo.destroy()
            except Exception:       # noqa: BLE001
                pass
            self.velo = None
        for f in self.nascoste:
            try:
                if f.winfo_exists():
                    f.deiconify()
            except Exception:       # noqa: BLE001 - chiusa nel frattempo
                pass
        self.nascoste = []


def attacca(pagina):
    """Collega il blocco alla pagina se vale (app pubblica); None se no."""
    if not attivo():
        return None
    b = Blocco(pagina)
    pagina.fr.after(1500, b.giro)
    return b


def prova():
    import tkinter as tk
    casi = []
    root = tk.Tk(); root.withdraw()
    F = lambda s, b=False: ("Segoe UI", s, "bold" if b else "normal")

    class Pag:
        pass
    p = Pag(); p.tk, p.F = tk, F
    p.fr = tk.Frame(root); p.fr.pack()
    fin = tk.Toplevel(p.fr); fin.withdraw(); fin.deiconify(); root.update()
    stato = {"aperto": False}
    b = Blocco(p, controllo=lambda: stato["aperto"])
    b.applica(False); root.update()
    casi.append(("negativa: col gioco chiuso niente velo e la finestra resta", b.velo is None and fin.state() != "withdrawn"))
    b.applica(True); root.update()
    casi.append(("col gioco aperto: il velo copre la pagina e la sua finestra si nasconde", b.velo is not None and b.velo.winfo_exists()
                 and fin.state() == "withdrawn" and fin in b.nascoste))
    b.applica(True); root.update()
    casi.append(("ancora aperto: niente di doppio", len(b.nascoste) == 1))
    b.applica(False); root.update()
    casi.append(("chiuso il gioco: il velo va via e la finestra torna", b.velo is None and fin.state() != "withdrawn" and not b.nascoste))
    vecchio = os.environ.get("LEAK_BLOCCO")
    try:
        os.environ["LEAK_BLOCCO"] = "0"
        casi.append(("LEAK_BLOCCO=0: spento", attivo() is False and attacca(p) is None))
        os.environ["LEAK_BLOCCO"] = "1"
        casi.append(("LEAK_BLOCCO=1: acceso", attivo() is True))
        os.environ.pop("LEAK_BLOCCO")
        import account
        casi.append(("senza la variabile segue l'app: pubblica si', quella di Autore no", attivo() is bool(account.PUBBLICA)))
    finally:
        if vecchio is None:
            os.environ.pop("LEAK_BLOCCO", None)
        else:
            os.environ["LEAK_BLOCCO"] = vecchio
    casi.append(("il controllo vero risponde senza errori", isinstance(gioco_aperto(), bool)))
    root.destroy()
    for n, ok in casi:
        print(("ok    " if ok else "ROSSO ") + n)
    print(f"{sum(1 for _n, ok in casi if ok)}/{len(casi)}")
    return all(ok for _n, ok in casi)


if __name__ == "__main__":
    sys.exit(0 if prova() else 1)
