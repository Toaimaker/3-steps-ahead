"""Il database delle carte di Arena (Dati/untapped/arena_cards/cards.json e loc_en.json) letto una volta per processo, ridotto e cotto su disco.

11 nov 2026, sessione Magic 13 (Autore: «migliora la gestione della memoria o come caricare e scaricare memoria velocemente»): quattro moduli della
finestra (collezione_carte, collezione_viva, mazzi_arena, deckstring_scrivi) leggevano ognuno per intero i due file, 14 MB e 5 MB di JSON con 27.720
carte e 45 campi l'una: quattro letture da 0,3-0,5 s e un picco di ~90 MB l'una, che la memoria del processo non restituisce tutta.

Qui una lettura sola, sotto lucchetto (i fili della finestra la chiedono insieme all'avvio), coi soli campi che quei moduli usano (CAMPI; delle abilita'
il solo TextId) e i soli testi che servono (titoli, tipi, sottotipi, abilita'). Una chiave che la carta non ha resta assente, come nel file: chi legge
con c.get() ottiene lo stesso di prima. La copia ridotta si cuoce in Log_Arena/cache/db_carte.marshal (marshal: solo dizionari, liste, stringhe e
numeri, niente codice) e si rifa' quando cambia uno dei due file (data e misura nella chiave). Prova: --prova (stessi valori del file su ogni carta e
ogni testo usato; la negativa: un campo tolto apposta si vede).
"""
import os, sys
_casa = os.path.dirname(os.path.abspath(__file__))      # si sale fino a percorsi.py, che mette nel sys.path tutte le cartelle del Companion
while not os.path.isfile(os.path.join(_casa, "percorsi.py")):
    _casa = os.path.dirname(_casa)
if _casa not in sys.path:
    sys.path.insert(0, _casa)
import percorsi  # noqa: E402
import marshal  # noqa: E402
import threading  # noqa: E402
import time  # noqa: E402

CARTELLA = os.path.join(percorsi.ROOT, "Dati", "untapped", "arena_cards")
F_CARTE = os.path.join(CARTELLA, "cards.json")
F_LOC = os.path.join(CARTELLA, "loc_en.json")
CACHE = os.path.join(percorsi.ROOT, "Log_Arena", "cache", "db_carte.marshal")
VERSIONE = 1
CAMPI = ("grpid", "titleId", "set", "cardTypeTextId", "subtypeTextId", "rarity", "castingcost", "cmc", "colors", "colorIdentity", "power", "toughness",
         "linkedFaces", "abilities", "isToken", "isSecondaryCard", "IsRebalanced", "IsDigitalOnly", "DigitalReleaseSet")
_LUCCHETTO = threading.Lock()
_D = {"chiave": None, "carte": None, "testi": None}


def _chiave():
    return tuple((os.path.getmtime(f), os.path.getsize(f)) for f in (F_CARTE, F_LOC)) + (VERSIONE,)


def riduci(carte, loc):
    """(carte ridotte, testi usati) dal contenuto dei due file."""
    out, usati = [], set()
    for c in carte:
        r = {k: c[k] for k in CAMPI if k in c}
        if "abilities" in r:
            r["abilities"] = [{"TextId": a["TextId"]} if "TextId" in a else {} for a in r["abilities"]]
            usati.update(a["TextId"] for a in r["abilities"] if "TextId" in a)
        usati.update(r[k] for k in ("titleId", "cardTypeTextId", "subtypeTextId") if k in r)
        out.append(r)
    testi = {e["id"]: e["text"] for e in loc if e["id"] in usati}
    return out, testi


def _dal_disco(chiave):
    try:
        with open(CACHE, "rb") as f:
            b = f.read()        # tutto in una volta: marshal.load dal file legge a pezzi (224 ms contro 50)
        with senza_gc():
            d = marshal.loads(b)
        if isinstance(d, dict) and d.get("chiave") == list(chiave):
            return d["carte"], d["testi"]
    except (OSError, ValueError, EOFError, TypeError, KeyError):
        pass
    return None


class senza_gc:
    """Il garbage collector fermo mentre nascono decine di migliaia di dizionari che restano vivi: scatterebbe ogni 700 e li ripasserebbe tutti
    (marshal da 50 a 29 ms, il JSON pieno da 200 a 125). Si riaccende anche se la lettura cade; dentro un altro senza_gc resta com'era."""

    def __enter__(self):
        import gc
        self.era = gc.isenabled()
        gc.disable()

    def __exit__(self, *a):
        import gc
        if self.era:
            gc.enable()


def _cuoci(chiave):
    import json
    with senza_gc():
        carte, testi = riduci(json.load(open(F_CARTE, encoding="utf-8")), json.load(open(F_LOC, encoding="utf-8")))
    try:
        os.makedirs(os.path.dirname(CACHE), exist_ok=True)
        tmp = CACHE + ".tmp"
        with open(tmp, "wb") as f:
            marshal.dump({"chiave": list(chiave), "carte": carte, "testi": testi}, f)
        os.replace(tmp, CACHE)
    except OSError:
        pass        # senza la copia cotta si legge dal JSON anche la prossima volta
    return carte, testi


def leggi():
    """(carte, testi): [carta ridotta] nell'ordine del file e {id del testo: testo}. Gli stessi oggetti finche' i file non cambiano: non si modificano."""
    try:
        chiave = _chiave()
    except OSError:
        return [], {}
    with _LUCCHETTO:
        if _D["chiave"] != chiave:
            ct = _dal_disco(chiave) or _cuoci(chiave)
            _D.update(chiave=chiave, carte=ct[0], testi=ct[1])
        _D["usato"] = time.time()
        _guardia()
        return _D["carte"], _D["testi"]


RIPOSO = 30         # secondi senza letture dopo i quali la copia in memoria si libera: chi la usa ne fa le sue tabelle all'avvio e quando cambia la collezione


def libera():
    """Toglie dalla memoria la copia ridotta (~38 MB): la prossima lettura la riprende dalla copia cotta in ~40 ms."""
    with _LUCCHETTO:
        _D.update(chiave=None, carte=None, testi=None)


def _guardia():
    """Un filo che guarda ogni 10 s: dopo RIPOSO secondi senza letture libera la copia in memoria. Uno per processo, si chiude da solo dopo averla liberata."""
    if _D.get("guardia"):
        return
    _D["guardia"] = True

    def gira():
        while True:
            time.sleep(10)
            with _LUCCHETTO:
                if _D["chiave"] is not None and time.time() - _D.get("usato", 0) >= RIPOSO:
                    _D.update(chiave=None, carte=None, testi=None, guardia=False)
                    return
    threading.Thread(target=gira, daemon=True, name="db_carte.guardia").start()


def carte():
    return leggi()[0]


def testi():
    return leggi()[1]


def prova():
    import json
    import tempfile
    casi = []
    pieno = json.load(open(F_CARTE, encoding="utf-8"))
    loc = {e["id"]: e["text"] for e in json.load(open(F_LOC, encoding="utf-8"))}
    global CACHE
    era = CACHE
    CACHE = os.path.join(tempfile.mkdtemp(), "db_carte.marshal")
    try:
        _D["chiave"] = None
        c1, t1 = leggi()                         # dal JSON, e si cuoce
        casi.append(("la copia cotta e' scritta", os.path.exists(CACHE)))
        _D["chiave"] = None
        c2, t2 = leggi()                         # dalla copia cotta
        casi.append(("dalla copia cotta gli stessi dati del JSON", c1 == c2 and t1 == t2))
        uguali = len(c1) == len(pieno) and all(all(r.get(k) == (p.get(k) if k != "abilities" else
                                                                  [{"TextId": a["TextId"]} if "TextId" in a else {} for a in p.get("abilities") or []] or p.get(k))
                                                       for k in CAMPI) and set(r) == {k for k in CAMPI if k in p} for r, p in zip(c1, pieno))
        casi.append((f"ogni carta ({len(c1)}) ha gli stessi campi del file, e le chiavi assenti restano assenti", uguali))
        usati = {r[k] for r in c1 for k in ("titleId", "cardTypeTextId", "subtypeTextId") if k in r} | {a["TextId"] for r in c1 for a in r.get("abilities") or [] if "TextId" in a}
        casi.append(("ogni testo usato e' quello del file", all(t1.get(i) == loc.get(i) for i in usati) and set(t1) <= usati))
        casi.append(("gli stessi oggetti a ogni chiamata (una lettura per processo)", leggi()[0] is c2))
        libera()
        casi.append(("liberata, la memoria non la tiene piu' e la lettura dopo la riprende uguale", _D["carte"] is None and leggi()[0] == c1))
        c_neg, _t = riduci([{k: v for k, v in pieno[0].items() if k != "set"}], [])
        casi.append(("negativa: un campo tolto nel file manca anche nella copia ridotta", "set" not in c_neg[0] and "set" in c1[0]))
        with open(CACHE, "wb") as f:
            f.write(b"rotto")
        _D["chiave"] = None
        casi.append(("una copia cotta rotta si rifa' dal JSON", leggi()[0] == c1))
    finally:
        CACHE = era
        _D["chiave"] = None
    for nome, ok in casi:
        print(("  ok    " if ok else "  ROSSO ") + nome)
    n = sum(1 for _, ok in casi if ok)
    print(f"{n}/{len(casi)}")
    return 0 if n == len(casi) else 1


if __name__ == "__main__":
    if "--prova" in sys.argv:
        sys.exit(prova())
