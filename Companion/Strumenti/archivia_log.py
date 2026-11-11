"""Archivia il Player.log di Arena prima che il client lo sovrascriva.
Copia Player.log e Player-prev.log in Log_Arena/ con data e ora, solo se il contenuto e' cambiato (hash).
Lanciato dal giro dello scout ogni 6 ore (Motore/scout_giro.bat). Da qui nasce il parser delle partite.
"""
import os, sys
_casa = os.path.dirname(os.path.abspath(__file__))      # si sale fino a percorsi.py, che mette nel sys.path tutte le cartelle del Companion
while not os.path.isfile(os.path.join(_casa, "percorsi.py")):
    _casa = os.path.dirname(_casa)
if _casa not in sys.path:
    sys.path.insert(0, _casa)
import percorsi  # noqa: E402
import piattaforma  # noqa: E402  (i percorsi di Arena su Windows e su Mac)
import shutil, hashlib, datetime, glob
ROOT = percorsi.ROOT
DEST = os.path.join(ROOT, "Log_Arena"); os.makedirs(DEST, exist_ok=True)
SRC = piattaforma.cartella_arena()
noti = {os.path.basename(p).split("_")[-1].replace(".log", "") for p in glob.glob(os.path.join(DEST, "*.log"))}
for nome in ("Player.log", "Player-prev.log"):
    p = os.path.join(SRC, nome)
    if not os.path.exists(p) or os.path.getsize(p) < 1000:
        continue
    h = hashlib.md5(open(p, "rb").read()).hexdigest()[:10]
    if h in noti:
        print(nome, "gia' archiviato", h); continue
    out = os.path.join(DEST, f"{datetime.datetime.now():%Y-%m-%d_%H%M}_{nome.replace('.log','')}_{h}.log")
    shutil.copy2(p, out); print("archiviato", out, os.path.getsize(p) // 1024, "KB")
