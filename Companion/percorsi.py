"""I percorsi dell'app pubblica (Companion Magic Arena). Sostituisce Companion/percorsi.py del progetto di Autore, che trova la radice salendo fino a
CLAUDE.md: qui la radice e' la cartella col file PUBBLICA.txt (la scrive Distribuzione/costruisci.py). Le costanti e le funzioni sono le stesse."""
import os
import sys


def _radice():
    d = os.path.dirname(os.path.abspath(__file__))
    while not os.path.isfile(os.path.join(d, "PUBBLICA.txt")):
        su = os.path.dirname(d)
        if su == d:
            raise RuntimeError("percorsi: nessuna cartella con PUBBLICA.txt sopra " + __file__)
        d = su
    return d


def _con_codice(cartella):
    out = []
    for d, sotto, fs in os.walk(cartella):
        sotto[:] = sorted(x for x in sotto if x not in ("__pycache__", "campioni"))
        if any(f.endswith(".py") for f in fs):
            out.append(d)
    return tuple(out)


ROOT = _radice()
COMPANION = os.path.join(ROOT, "Companion")
DRAFTER = os.path.join(COMPANION, "Drafter")
SUGGERITORE = os.path.join(COMPANION, "Suggeritore")
COMUNE = os.path.join(COMPANION, "Comune")
APP = os.path.join(COMPANION, "App")
STRUMENTI = os.path.join(COMPANION, "Strumenti")
GRAFICA = os.path.join(COMPANION, "Grafica")
MOTORE = os.path.join(ROOT, "Motore")
CARTELLE = tuple(c for c in (COMPANION, DRAFTER, SUGGERITORE, COMUNE) + _con_codice(APP) + (STRUMENTI, MOTORE) if os.path.isdir(c))
for _c in reversed(CARTELLE):
    if _c not in sys.path:
        sys.path.insert(0, _c)


def set_attivo(predefinito="FRA"):
    a = sys.argv
    if "--set" in a and a.index("--set") + 1 < len(a):
        return a[a.index("--set") + 1].upper()
    return (os.environ.get("MAGIC_SET") or predefinito).upper()


def programma(nome):
    for c in CARTELLE:
        f = os.path.join(c, nome)
        if os.path.isfile(f):
            return f
    raise FileNotFoundError(f"percorsi: {nome} non c'e' in questa versione dell'app")
