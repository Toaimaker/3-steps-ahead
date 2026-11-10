"""L'avvio dell'app pubblica (10 nov 2026): una finestrella che prepara i dati del primo avvio (primo_avvio.py), chiede una volta il consenso alla
condivisione (condividi.py, spenta di partenza), poi apre la finestra grande. Lo lancia Avvia.bat dello zip pubblico. Nell'app di Autore non serve.

    py -I -X utf8 Companion/App/avvio_pubblico.py [--senza-finestra]     --senza-finestra: prepara e si ferma (collaudo)
"""
import os, sys
_casa = os.path.dirname(os.path.abspath(__file__))      # si sale fino a percorsi.py, che mette nel sys.path tutte le cartelle del Companion
while not os.path.isfile(os.path.join(_casa, "percorsi.py")):
    _casa = os.path.dirname(_casa)
if _casa not in sys.path:
    sys.path.insert(0, _casa)
import percorsi  # noqa: E402
import json  # noqa: E402
import threading  # noqa: E402
import webbrowser  # noqa: E402

FONDO, TESTO, TITOLO, ACCENTO, GRIGIO = "#101014", "#bebec2", "#ffffff", "#24baff", "#7a7a80"
CANALE = os.path.join(percorsi.ROOT, "canale.json")


def canale():
    """Gli indirizzi del canale (scritti da Distribuzione/costruisci.py): manifest, endpoint_log, sostegno, sito, privacy. Vuoti finche' non ci sono."""
    try:
        return json.load(open(CANALE, encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def prepara(root):
    import tkinter as tk
    import condividi
    import primo_avvio
    stato = {"testo": "Preparing…", "fine": False, "esito": {}}

    def lavoro():
        stato["esito"] = primo_avvio.esegui(avviso=lambda t: stato.update(testo=t))
        stato["fine"] = True
    threading.Thread(target=lavoro, daemon=True).start()
    from ambiente import PRODOTTO
    root.title(PRODOTTO)
    root.configure(bg=FONDO)
    root.geometry("560x320" + ("+-4000+0" if "--fuori-schermo" in sys.argv else ""))      # le prove non si aprono mai davanti a chi lavora
    from ambiente import ASSET
    from tema import icona_finestra
    root.after(50, lambda: icona_finestra(root, os.path.join(ASSET, "companion.ico")))       # il logo nella barra, non la piuma di Tk
    tk.Label(root, text=PRODOTTO, bg=FONDO, fg=TITOLO, font=("Segoe UI", 16, "bold")).pack(pady=(24, 4))
    tk.Label(root, text="Alpha · free · unofficial fan content", bg=FONDO, fg=GRIGIO, font=("Segoe UI", 9)).pack()
    riga = tk.Label(root, text="", bg=FONDO, fg=TESTO, font=("Segoe UI", 10)); riga.pack(pady=(28, 6))
    tk.Label(root, text="The first start downloads card data (about 125 MB). Next starts are instant.", bg=FONDO, fg=GRIGIO, font=("Segoe UI", 8)).pack()
    sotto = tk.Frame(root, bg=FONDO); sotto.pack(pady=18, fill="x")

    def chiedi_consenso():
        for w in sotto.winfo_children():
            w.destroy()
        tk.Label(sotto, text="Share your game data to improve the app?", bg=FONDO, fg=TITOLO, font=("Segoe UI", 10, "bold")).pack()
        tk.Label(sotto, text="Only cards, results, mulligans and turns. Never your name, your account or your opponents' names.\nOff unless you say yes. You can change it in Help.",
                 bg=FONDO, fg=TESTO, font=("Segoe UI", 8), justify="center").pack(pady=(4, 8))
        b = tk.Frame(sotto, bg=FONDO); b.pack()
        tk.Button(b, text="Yes, share", bg=ACCENTO, fg=FONDO, relief="flat", padx=14, command=lambda: scelta(True)).pack(side="left", padx=6)
        tk.Button(b, text="No, thanks", bg="#303034", fg=TESTO, relief="flat", padx=14, command=lambda: scelta(False)).pack(side="left", padx=6)
        url = canale().get("privacy")
        if url:
            l_ = tk.Label(sotto, text="Privacy notice ↗", bg=FONDO, fg=ACCENTO, font=("Segoe UI", 8), cursor="hand2"); l_.pack(pady=(6, 0))
            l_.bind("<Button-1>", lambda e: webbrowser.open(url))

    def scelta(si):
        condividi.imposta_consenso(si)
        root.destroy()

    def guarda():
        riga.configure(text=stato["testo"])
        if not stato["fine"]:
            root.after(150, guarda)
            return
        errori = {k: v for k, v in stato["esito"].items() if v}
        riga.configure(text="Ready" if not errori else f"Ready, without: {', '.join(errori)} (retried next start)")
        if condividi.consenso() is None:
            chiedi_consenso()
        else:
            root.after(400, root.destroy)
    guarda()
    root.mainloop()


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
                                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "BELOW_NORMAL_PRIORITY_CLASS", 0),
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
    prepara(tk.Tk())
    if "--senza-finestra" in sys.argv:
        return
    manutenzione()
    condividi_in_fondo()
    import finestra
    finestra.avvia()


if __name__ == "__main__":
    main()
