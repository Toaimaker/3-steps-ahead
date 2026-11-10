"""Il registro degli errori della finestra grande (Autore, 7 nov 2026: «fai un profondo debug stabilizzatore ottimizzatore
di performance di tutto»).

La finestra gira con pythonw: sys.stdout e sys.stderr sono None, e fino al 7 nov 2026 ogni errore (le righe «giro: ...»,
«pagina X: ...», le eccezioni dentro i clic di Tk, i fili dei dati) finiva nel vuoto. Da qui:
- stdout e stderr, quando mancano, vanno in Log_Arena/finestra_AAAAMMGG.txt con l'ora davanti a ogni riga;
- le eccezioni non prese (programma, fili, callback di Tk) ci vanno col traceback intero;
- un crash dentro Tk (access violation, 4 nov 2026) lascia il suo traceback in Log_Arena/finestra_crash.txt (faulthandler).
Il file non supera 5 MB: oltre, si riparte da uno nuovo e il vecchio diventa .1.

    py -I -X utf8 Companion/App/Comune/registro_errori.py --prova
"""
import os, sys
_casa = os.path.dirname(os.path.abspath(__file__))      # si sale fino a percorsi.py, che mette nel sys.path tutte le cartelle del Companion
while not os.path.isfile(os.path.join(_casa, "percorsi.py")):
    _casa = os.path.dirname(_casa)
if _casa not in sys.path:
    sys.path.insert(0, _casa)
import percorsi  # noqa: E402
import datetime
import faulthandler
import threading
import traceback

QUI = os.path.dirname(os.path.abspath(__file__))
LOGDIR = os.path.join(percorsi.ROOT, "Log_Arena")
MASSIMO = 5 * 1024 * 1024
_crash = None          # il file di faulthandler resta aperto finche' vive il processo


class Righe:
    """Un file che mette l'ora davanti a ogni riga e non cresce oltre MASSIMO."""

    def __init__(self, percorso):
        self.percorso = percorso
        self.lock = threading.Lock()
        self.a_capo = True
        self.f = None
        self.apri()

    def apri(self):
        try:
            if os.path.getsize(self.percorso) > MASSIMO:
                os.replace(self.percorso, self.percorso + ".1")
        except OSError:
            pass
        self.f = open(self.percorso, "a", encoding="utf-8", buffering=1)

    def write(self, s):
        if not s:
            return 0
        with self.lock:
            try:
                ora = datetime.datetime.now().strftime("%H:%M:%S ")
                pezzi = s.split("\n")
                out = []
                for i, p in enumerate(pezzi):
                    if self.a_capo and p:
                        out.append(ora)
                    out.append(p)
                    if i < len(pezzi) - 1:
                        out.append("\n"); self.a_capo = True
                    elif p:
                        self.a_capo = False
                self.f.write("".join(out))
                if self.f.tell() > MASSIMO:
                    self.f.close(); self.apri()
            except (OSError, ValueError):
                pass
        return len(s)

    def flush(self):
        try:
            self.f.flush()
        except (OSError, ValueError):
            pass

    def isatty(self):
        return False


def scrivi_errore(titolo, tipo, valore, tb):
    try:
        testo = "".join(traceback.format_exception(tipo, valore, tb))
        print(f"ERRORE {titolo}:\n{testo}", file=sys.stderr, flush=True)
    except Exception:
        pass


def installa(nome="finestra", forza=False):
    """Da chiamare all'avvio. Con pythonw (o forza) stdout e stderr vanno nel file del giorno; le eccezioni non prese ci
    vanno sempre. Restituisce il percorso del file (None se le uscite erano gia' una console)."""
    global _crash
    percorso = None
    try:
        os.makedirs(LOGDIR, exist_ok=True)
    except OSError:
        return None
    if forza or sys.stdout is None or sys.stderr is None:
        percorso = os.path.join(LOGDIR, f"{nome}_{datetime.date.today():%Y%m%d}.txt")
        try:
            f = Righe(percorso)
            sys.stdout = sys.stdout if (sys.stdout is not None and not forza) else f
            sys.stderr = f
            print(f"--- avvio {nome}, pid {os.getpid()} ---")
        except OSError:
            percorso = None
    sys.excepthook = lambda t, v, tb: scrivi_errore("non presa", t, v, tb)
    threading.excepthook = lambda a: scrivi_errore(f"nel filo {a.thread.name if a.thread else '?'}", a.exc_type, a.exc_value, a.exc_traceback)
    try:
        _crash = open(os.path.join(LOGDIR, f"{nome}_crash.txt"), "a", encoding="utf-8")
        _crash.write(f"--- avvio {datetime.datetime.now():%Y-%m-%d %H:%M:%S}, pid {os.getpid()} ---\n"); _crash.flush()
        faulthandler.enable(file=_crash, all_threads=True)
    except (OSError, RuntimeError):
        pass
    return percorso


def lega_tk(root):
    """Le eccezioni dentro i callback di Tk (clic, after, bind): col traceback, e la finestra va avanti."""
    root.report_callback_exception = lambda t, v, tb: scrivi_errore("in Tk", t, v, tb)


def prova():
    import tempfile
    casi = []
    d = tempfile.mkdtemp()
    p = os.path.join(d, "x.txt")
    r = Righe(p)
    r.write("uno\ndue"); r.write(" tre\n"); r.write("")
    r.flush()
    righe = open(p, encoding="utf-8").read().splitlines()
    casi.append(("l'ora su ogni riga, una sola", len(righe) == 2 and righe[0].endswith("uno") and righe[1].endswith("due tre") and righe[1].count(":") == 2))
    vecchio = sys.stderr
    sys.stderr = r
    try:
        try:
            1 / 0
        except ZeroDivisionError:
            scrivi_errore("prova", *sys.exc_info())
    finally:
        sys.stderr = vecchio
    r.flush()
    t = open(p, encoding="utf-8").read()
    casi.append(("il traceback intero", "ERRORE prova" in t and "ZeroDivisionError" in t and "1 / 0" in t))
    global MASSIMO
    m0 = MASSIMO
    MASSIMO = 200
    try:
        for i in range(40):
            r.write(f"riga {i} che fa crescere il file\n")
    finally:
        MASSIMO = m0
    casi.append(("oltre il massimo si riparte", os.path.exists(p + ".1") and os.path.getsize(p) < 400))
    r.f.close()
    ok = all(v for _, v in casi)
    for n, v in casi:
        print(("ok  " if v else "NO  ") + n)
    print(f"{sum(1 for _, v in casi if v)}/{len(casi)}")
    return ok


if __name__ == "__main__":
    if "--prova" in sys.argv:
        sys.exit(0 if prova() else 1)
