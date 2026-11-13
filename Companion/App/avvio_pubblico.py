"""L'avvio dell'app pubblica (10 nov 2026): la schermata di caricamento che prepara i dati del primo avvio (primo_avvio.py), poi la finestra grande, che a
prima scheda disegnata chiede una volta il consenso alla condivisione (spenta di partenza) e il link di Untapped (Schede/Settings/benvenuto.py, dal 13 nov 2026). Lo lancia Avvia.bat dello zip pubblico. Nell'app di Autore non serve.

    py -I -X utf8 Companion/App/avvio_pubblico.py [--senza-finestra]     --senza-finestra: prepara e si ferma (collaudo)
"""
import os, sys
_casa = os.path.dirname(os.path.abspath(__file__))      # si sale fino a percorsi.py, che mette nel sys.path tutte le cartelle del Companion
while not os.path.isfile(os.path.join(_casa, "percorsi.py")):
    _casa = os.path.dirname(_casa)
if _casa not in sys.path:
    sys.path.insert(0, _casa)
import percorsi  # noqa: E402
import piattaforma  # noqa: E402  (Windows e Mac: flag dei processi, Python, percorsi)
import json  # noqa: E402
import threading  # noqa: E402


CANALE = os.path.join(percorsi.ROOT, "canale.json")


def canale():
    """Gli indirizzi del canale (scritti da Distribuzione/costruisci.py): manifest, endpoint_log, sostegno, sito, privacy. Vuoti finche' non ci sono."""
    try:
        return json.load(open(CANALE, encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def prepara(root=None):
    """La schermata di caricamento del primo avvio (la stessa della finestra grande, schermata_avvio.py: 13 nov 2026, «come si apre steam»): prepara i dati
    (primo_avvio.py) con la riga di cosa sta facendo, poi si chiude. Il consenso alla condivisione e il link di Untapped li chiede la finestra di benvenuto,
    dopo che l'app e' partita (Schede/Settings/benvenuto.py); fino al 13 nov 2026 il consenso lo chiedeva questa finestrella."""
    import tkinter as tk
    import primo_avvio
    import schermata_avvio as SA
    from ambiente import ASSET, VERSIONE
    stato = {"testo": "Preparing…", "fine": False, "esito": {}, "n": 0}

    def lavoro():
        stato["esito"] = primo_avvio.esegui(avviso=lambda t: stato.update(testo=t, n=stato["n"] + 1))
        stato["fine"] = True
    threading.Thread(target=lavoro, daemon=True).start()
    geo = f"{SA.LARGA}x{SA.ALTA}+-4000+0" if "--fuori-schermo" in sys.argv else None      # le prove non si aprono mai davanti a chi lavora
    s = SA.Schermata(tk, None, geo=geo, versione=VERSIONE)
    from tema import icona_finestra
    s.w.after(50, lambda: icona_finestra(s.w, os.path.join(ASSET, "companion.ico")))       # il logo nella barra, non la piuma di Tk

    def guarda():
        s.passo(stato["testo"], min(0.9, 0.05 + 0.08 * stato["n"]))
        if not stato["fine"]:
            s.w.after(150, guarda)
            return
        errori = {k: v for k, v in stato["esito"].items() if v}
        s.passo("Ready" if not errori else f"Ready, without: {', '.join(errori)} (retried next start)", 1.0)
        s.w.after(300, s.chiudi)
    guarda()
    s.w.mainloop()


def condividi_in_fondo():
    """Col consenso: mette in coda le partite nuove e le manda all'indirizzo del canale, se c'e'. In un filo: l'app parte subito."""
    def lavoro():
        try:
            import condividi
            condividi.accoda()
            condividi.invia(canale().get("endpoint_log"))
        except Exception:       # noqa: BLE001 - la condivisione non ferma mai l'app
            pass
    threading.Thread(target=lavoro, daemon=True).start()


def manutenzione(ogni=1800):
    """In sottofondo e a priorita' bassa, all'avvio e poi ogni mezz'ora: copia il Player.log in Log_Arena prima che Arena lo sovrascriva (archivia_log.py) e rifa'
    l'archivio delle partite (archivio_partite.py, Partite/: serve all'analisi del mazzo e ai turni). Nell'app di Autore lo fanno lo scout e il companion."""
    import subprocess
    import time

    def lavoro():
        while True:
            for prog, arg in (("archivia_log.py", []), ("archivio_partite.py", [])):
                try:
                    subprocess.run([sys.executable, "-I", "-X", "utf8", percorsi.programma(prog), *arg], cwd=percorsi.ROOT, timeout=1800,
                                   **piattaforma.flag("sotto", "muto"),
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                except Exception:       # noqa: BLE001 - la manutenzione non ferma mai l'app
                    pass
            time.sleep(ogni)
    threading.Thread(target=lavoro, daemon=True).start()


def main():
    import tkinter as tk
    from tema import id_app
    from ambiente import PRODOTTO
    id_app(PRODOTTO)        # il logo nella barra delle applicazioni, gia' dalla finestrella del primo avvio
    prepara()
    if "--senza-finestra" in sys.argv:
        return
    manutenzione()
    condividi_in_fondo()
    import finestra
    finestra.avvia()


if __name__ == "__main__":
    main()
