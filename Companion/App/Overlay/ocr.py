"""L'OCR di Windows da Python: un processo PowerShell sempre acceso (Companion/App/Overlay/ocr_windows.ps1) a cui si passa
un'immagine e che risponde con le parole e i loro riquadri.

Perche' cosi' (3 nov 2026, sessione Magic 07): Windows.Media.Ocr e' gia' nel sistema (lo usa lo strumento di cattura) e
non richiede di installare niente; dal Python senza il pacchetto winrt ci si arriva solo da PowerShell. Il processo resta
acceso per non pagare l'avvio (~0,3 s) a ogni lettura dello schermo. Sul PC di Autore il motore e' it-IT (l'inglese
non e' installato): i nomi delle carte escono sporchi e la corrispondenza la fa riconosci.py fra i nomi possibili.

    from ocr import Ocr
    with Ocr() as o:
        righe = o.leggi(immagine_pil)   # [{"t": testo della riga, "p": [{"t", "x", "y", "w", "h"}, ...]}, ...]
"""
import os, sys
_casa = os.path.dirname(os.path.abspath(__file__))      # si sale fino a percorsi.py, che mette nel sys.path tutte le cartelle del Companion
while not os.path.isfile(os.path.join(_casa, "percorsi.py")):
    _casa = os.path.dirname(_casa)
if _casa not in sys.path:
    sys.path.insert(0, _casa)
import percorsi  # noqa: E402
import json
import subprocess
import tempfile
import threading

QUI = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(QUI, "ocr_windows.ps1")


class Ocr:
    def __init__(self, lingua="en-US"):
        self.p = subprocess.Popen(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", SCRIPT, lingua],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), encoding="utf-8", bufsize=1)
        testa = json.loads(self.p.stdout.readline() or '{"errore": "OCR non partito"}')
        if "errore" in testa:
            raise RuntimeError(testa["errore"])
        self.lingua = testa["pronto"]
        self.blocco = threading.Lock()
        self.cartella = tempfile.mkdtemp(prefix="overlay_ocr_")
        self.n = 0

    def leggi(self, img):
        """img: un'immagine PIL. Le coordinate tornano in pixel di quell'immagine."""
        with self.blocco:
            self.n += 1
            # un nome nuovo a ogni lettura: WinRT tiene aperto il file per un po' e riscriverlo da' «Invalid argument»
            f = os.path.join(self.cartella, f"o{self.n}.png")
            img.save(f)
            try:
                os.remove(os.path.join(self.cartella, f"o{self.n - 3}.png"))
            except OSError:
                pass
            self.p.stdin.write(f + "\n")
            self.p.stdin.flush()
            r = json.loads(self.p.stdout.readline() or '{"errore": "OCR chiuso"}')
        if "errore" in r:
            raise RuntimeError(r["errore"])
        righe = r.get("righe") or []
        if isinstance(righe, dict):     # ConvertTo-Json di PowerShell 5.1 toglie l'array quando c'e' un elemento solo
            righe = [righe]
        for rg in righe:
            if isinstance(rg.get("p"), dict):
                rg["p"] = [rg["p"]]
        return righe

    def chiudi(self):
        try:
            self.p.stdin.write("\n")
            self.p.stdin.flush()
            self.p.wait(3)
        except Exception:
            self.p.kill()

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.chiudi()
