"""Cuoce in anticipo le miniature della scheda Collection (Autore, 6 nov 2026: «si possono bakare le carte per rendere tutto piu' veloce?»): capsule.cuoci, una jpg da 200x279 gia' con gli
angoli arrotondati in Log_Arena/carte_img/mini. Misurato il 6 nov 2026: da 22 ms a meno di 1 ms a carta, e pesa 22 KB.

Prima le carte che hai, poi le altre dal set piu' nuovo. Riprende da dove si e' fermato: le carte gia' cotte si saltano. Dell'immagine scaricata tiene solo la miniatura: quella grande dell'hover
si scarica quando serve. Gira a priorita' bassa, una copia sola, e con Arena aperto aspetta: niente lavori pesanti durante una partita. La finestra grande lo lancia all'avvio; finito il lavoro
esce subito, quindi un set nuovo si cuoce da solo. Scrive il punto in Log_Arena/cuoci_log.txt.

    py -I -X utf8 Companion/App/Schede/Collection/cuoci_carte.py [--max N]
"""
import os, sys
_casa = os.path.dirname(os.path.abspath(__file__))      # si sale fino a percorsi.py, che mette nel sys.path tutte le cartelle del Companion
while not os.path.isfile(os.path.join(_casa, "percorsi.py")):
    _casa = os.path.dirname(_casa)
if _casa not in sys.path:
    sys.path.insert(0, _casa)
import percorsi  # noqa: E402
import ctypes, datetime, io, msvcrt, subprocess, time, urllib.error, urllib.request
from concurrent.futures import ThreadPoolExecutor
import capsule as CAP
import collezione_carte as CC
import risorse as RS

LOG = os.path.join(percorsi.ROOT, "Log_Arena", "cuoci_log.txt")
BLOCCO = os.path.join(percorsi.ROOT, "Log_Arena", "cuoci.lock")
OPERAI, GRUPPO = 3, 30


def scrivi(testo):
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(f"{datetime.datetime.now():%Y-%m-%d %H:%M:%S} {testo}\n")


def arena_aperta():
    r = subprocess.run(["tasklist", "/FI", "IMAGENAME eq MTGA.exe", "/NH"], capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)     # in byte: Windows risponde nella sua codifica
    return b"mtga.exe" in r.stdout.lower()


def ordine(d):
    """Prima le tue, poi dal set piu' nuovo."""
    date = RS.date_uscita()
    nuovo = lambda c: max((date.get(s, "") for s in c["sets"]), default="")
    return [c["nome"] for c in sorted(sorted(d["carte"], key=nuovo, reverse=True), key=lambda c: not c["copie"])]


def fai(nome):
    """-> "cotta", "saltata" (nessun indirizzo: la fara' la pagina se la mostra) o "pausa" (Scryfall chiede di aspettare)."""
    if os.path.exists(CAP.file_mini(nome)):
        return "cotta"
    try:
        if os.path.exists(CAP.file_immagine(nome)):
            CAP.cuoci(nome)
            return "cotta"
        u = CAP.indirizzo(nome)
        if not u:
            return "saltata"
        r = urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "magic-arena-companion/1.0", "Accept": "image/*"}), timeout=20, context=CAP.contesto())
        CAP.cuoci(nome, io.BytesIO(r.read()))
        time.sleep(0.05)
        return "cotta"
    except urllib.error.HTTPError as e:
        return "pausa" if e.code == 429 else "saltata"
    except Exception:
        return "saltata"


def main():
    os.makedirs(CAP.MINI, exist_ok=True)
    blocco = open(BLOCCO, "w")
    try:
        msvcrt.locking(blocco.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError:
        return 0        # ce n'e' gia' uno
    ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000)     # sotto la norma
    d = CC.carica()
    if not d:
        return 1
    nomi = [n for n in ordine(d) if not os.path.exists(CAP.file_mini(n))]
    if "--max" in sys.argv:
        nomi = nomi[:int(sys.argv[sys.argv.index("--max") + 1])]
    if not nomi:
        return 0
    scrivi(f"da cuocere {len(nomi)} su {len(d['carte'])}")
    t0, fatte, saltate = time.time(), 0, 0
    with ThreadPoolExecutor(OPERAI) as ex:
        for i in range(0, len(nomi), GRUPPO):
            while arena_aperta():
                time.sleep(60)
            esiti = list(ex.map(fai, nomi[i:i + GRUPPO]))
            fatte += esiti.count("cotta"); saltate += esiti.count("saltata")
            if "pausa" in esiti:
                time.sleep(60)
            if i % (GRUPPO * 50) == 0:
                scrivi(f"{fatte} cotte, {saltate} saltate, {time.time() - t0:.0f} s")
    scrivi(f"finito: {fatte} cotte, {saltate} saltate, {time.time() - t0:.0f} s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
