"""Gli aggiornamenti dell'app (Autore, 10 nov 2026: «se facciamo degli update come facciamo a farli arrivare a chi usa l'app? … se arriva un pulsante in quella
pagina comunica di scaricare l'update»; scelta sua: prima il meccanismo, il canale dopo).

L'app legge un piccolo file JSON, il «manifest», da un indirizzo scritto in `aggiornamenti.json` accanto a questo file (la chiave `manifest`). Il manifest dice:

    {"version": "1.1", "date": "2026-11-20", "notes": "What's new, one line or more", "download": "https://..."}

Se `version` e' piu' alta della versione dell'app (`ambiente.VERSIONE`), la scheda Help mostra il pulsante per scaricare l'aggiornamento, che apre il link nel
browser: l'app non scarica e non installa niente da sola. Il link si apre solo se e' http o https. Senza indirizzo il canale non c'e' e Help lo dice.
Il controllo gira in sottofondo all'avvio e ogni 6 ore; l'ultimo esito sta in Log_Arena/aggiornamenti_stato.json.
Dove mettere il manifest (GitHub Releases o Pages, una cartella condivisa con un link pubblico) e' una scelta ancora da fare.

    py -I -X utf8 Companion/App/Schede/Help/aggiornamenti.py            controlla adesso e stampa l'esito
    py -I -X utf8 Companion/App/Schede/Help/aggiornamenti.py --prova    le prove, con le negative
"""
import os, sys
_casa = os.path.dirname(os.path.abspath(__file__))      # si sale fino a percorsi.py, che mette nel sys.path tutte le cartelle del Companion
while not os.path.isfile(os.path.join(_casa, "percorsi.py")):
    _casa = os.path.dirname(_casa)
if _casa not in sys.path:
    sys.path.insert(0, _casa)
import percorsi  # noqa: E402,F401
import json
import re
import time
import urllib.request

from ambiente import LOGDIR, VERSIONE

IMPOSTAZIONI = os.path.join(os.path.dirname(os.path.abspath(__file__)), "aggiornamenti.json")
STATO = os.path.join(LOGDIR, "aggiornamenti_stato.json")
OGNI = 6 * 3600         # ogni quanto si ricontrolla, in secondi


def canale(f=None):
    """L'indirizzo del manifest, o "" se il canale non c'e' ancora."""
    try:
        with open(f or IMPOSTAZIONI, encoding="utf-8") as g:
            return str(json.load(g).get("manifest") or "").strip()
    except (OSError, ValueError):
        return ""


def tupla(v):
    """«1.10.2» -> (1, 10, 2): le versioni si confrontano numero per numero (1.10 viene dopo 1.9)."""
    return tuple(int(x) for x in re.findall(r"\d+", str(v))) or (0,)


def leggi_manifest(url, timeout=8):
    ctx = None
    if url.startswith("https://"):
        try:
            import capsule
            ctx = capsule.contesto()
        except Exception:
            ctx = None
    req = urllib.request.Request(url, headers={"User-Agent": "CompanionApp"})
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
        return json.loads(r.read().decode("utf-8"))


def controlla(url=None, attuale=VERSIONE, f=None):
    """-> dict(stato = "senza_canale" | "aggiornata" | "nuova" | "errore", attuale, ultima, note, download, data, errore, quando)."""
    url = canale(f) if url is None else url
    base = dict(attuale=attuale, quando=time.time())
    if not url:
        return dict(base, stato="senza_canale")
    try:
        m = leggi_manifest(url)
    except Exception as e:
        return dict(base, stato="errore", errore=f"could not read the update file ({type(e).__name__})")
    if not isinstance(m, dict) or not str(m.get("version") or "").strip():
        return dict(base, stato="errore", errore="the update file has no version")
    ultima = str(m["version"]).strip()
    link = str(m.get("download") or "").strip()
    note = str(m.get("notes") or "").strip()
    if tupla(ultima) <= tupla(attuale):
        return dict(base, stato="aggiornata", ultima=ultima, note=note, data=str(m.get("date") or ""))
    if not link.lower().startswith(("https://", "http://")):        # un link che non e' una pagina web non si apre
        return dict(base, stato="errore", ultima=ultima, errore="the update has no valid download link")
    return dict(base, stato="nuova", ultima=ultima, note=note, download=link, data=str(m.get("date") or ""))


def salva(stato, f=None):
    try:
        os.makedirs(os.path.dirname(f or STATO), exist_ok=True)
        with open(f or STATO, "w", encoding="utf-8") as g:
            json.dump(stato, g, ensure_ascii=False, indent=1)
    except OSError:
        pass


def carica(f=None):
    try:
        with open(f or STATO, encoding="utf-8") as g:
            d = json.load(g)
        return d if isinstance(d, dict) else None
    except (OSError, ValueError):
        return None


def da_ricontrollare(stato, adesso=None):
    return not stato or (adesso or time.time()) - float(stato.get("quando") or 0) >= OGNI


def prova():
    import tempfile
    import pathlib
    d = tempfile.mkdtemp()

    def manifest(nome, dato):
        p = os.path.join(d, nome)
        with open(p, "w", encoding="utf-8") as g:
            g.write(dato if isinstance(dato, str) else json.dumps(dato))
        return pathlib.Path(p).as_uri()
    imp = os.path.join(d, "imp.json")
    with open(imp, "w", encoding="utf-8") as g:
        json.dump({"manifest": ""}, g)
    casi = []
    casi.append(("senza indirizzo il canale non c'e'", controlla(f=imp)["stato"] == "senza_canale"))
    casi.append(("le versioni si confrontano numero per numero", tupla("1.10") > tupla("1.9") and tupla("1.0") == tupla("1.0") and tupla("v2") > tupla("1.99")))
    nuova = controlla(url=manifest("n.json", {"version": "1.1", "notes": "Board outliner", "download": "https://example.org/companion-1.1.zip"}), attuale="1.0")
    casi.append(("una versione piu' alta: nuova, con le note e il link", nuova["stato"] == "nuova" and nuova["ultima"] == "1.1" and nuova["download"].startswith("https://")
                 and nuova["note"] == "Board outliner"))
    casi.append(("la stessa versione: aggiornata", controlla(url=manifest("s.json", {"version": "1.0", "download": "https://x"}), attuale="1.0")["stato"] == "aggiornata"))
    casi.append(("negativa: una versione piu' vecchia non e' un aggiornamento", controlla(url=manifest("v.json", {"version": "0.9", "download": "https://x"}), attuale="1.0")["stato"] == "aggiornata"))
    casi.append(("negativa: un link che non e' http o https non si propone", controlla(url=manifest("l.json", {"version": "2.0", "download": "file:///C:/x.exe"}),
                                                                                       attuale="1.0")["stato"] == "errore"))
    casi.append(("negativa: un file rotto o senza versione e' un errore, non un aggiornamento",
                  controlla(url=manifest("r.json", "{non json"), attuale="1.0")["stato"] == "errore"
                  and controlla(url=manifest("z.json", {"download": "https://x"}), attuale="1.0")["stato"] == "errore"))
    casi.append(("negativa: un indirizzo che non risponde e' un errore", controlla(url=pathlib.Path(os.path.join(d, "manca.json")).as_uri(), attuale="1.0")["stato"] == "errore"))
    fs = os.path.join(d, "stato.json")
    salva(nuova, fs)
    casi.append(("l'esito si salva e si rilegge; dopo 6 ore si ricontrolla", carica(fs) == nuova and not da_ricontrollare(nuova, nuova["quando"] + 60)
                 and da_ricontrollare(nuova, nuova["quando"] + OGNI + 1) and da_ricontrollare(None)))
    ok = sum(1 for _n, v in casi if v)
    for n, v in casi:
        print(("ok    " if v else "ROSSO ") + n)
    print(f"{ok}/{len(casi)}")
    return ok == len(casi)


if __name__ == "__main__":
    if "--prova" in sys.argv:
        sys.exit(0 if prova() else 1)
    print(json.dumps(controlla(), ensure_ascii=False, indent=1))
