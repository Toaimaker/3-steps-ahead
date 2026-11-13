"""Pubblico o privato: la regola di ogni gruppo di Your decks e l'eccezione di ogni mazzo (12 nov 2026, Autore: «ogni tendina gruppo / categoria deve avere un
pulsante individuale per indicare se la relativa tendina gruppo e' pubblica o privata con suoi mazzi contenuti a rispetto della regola. Le box dei mazzi poi
devono avere un pulsante individuale per indicare se il mazzo e' pubblico o privato di default secondo la regola della tendina gruppo relativo o se
individualmente un mazzo puo' violare la regola della tendina. Gruppo e mazzi arena decks esclusi da questa modifica»).

- Un gruppo (Standard, Wishlist, Deck builder...) e' pubblico o privato; di partenza pubblico, cosi' la condivisione dei dati resta com'era.
- Un mazzo segue la regola del suo gruppo finche' non la viola col suo pulsante; ripremuto, se torna uguale al gruppo l'eccezione sparisce.
- Il gruppo Arena decks (i mazzi che Arena ti ha dato) non ha la regola: segue la condivisione di sempre.
- Cosa vuol dire oggi: le partite di un mazzo privato non escono con la condivisione dei dati (condividi.accoda le salta). Domani anche la colonna social.
I dati stanno in Log_Arena/mazzi_visibilita.json, dell'account (account.lega): {"gruppi": {nome: "public"|"private"}, "mazzi": {chiave: "public"|"private"}}.

    py -I -X utf8 Companion/App/Schede/Your_decks/visibilita_mazzi.py --prova
"""
import os, sys
_casa = os.path.dirname(os.path.abspath(__file__))      # si sale fino a percorsi.py, che mette nel sys.path tutte le cartelle del Companion
while not os.path.isfile(os.path.join(_casa, "percorsi.py")):
    _casa = os.path.dirname(_casa)
if _casa not in sys.path:
    sys.path.insert(0, _casa)
import percorsi  # noqa: E402,F401
import json  # noqa: E402
import account as _ACC  # noqa: E402

FILE = ""
_ACC.lega(globals(), "FILE", "mazzi_visibilita.json")
PUBBLICO, PRIVATO = "public", "private"
DEFAULT = PUBBLICO
ESCLUSO = "Arena decks"


def leggi():
    try:
        with open(FILE, encoding="utf-8") as f:
            d = json.load(f)
        return {"gruppi": dict(d.get("gruppi") or {}), "mazzi": dict(d.get("mazzi") or {})}
    except (OSError, ValueError, AttributeError):
        return {"gruppi": {}, "mazzi": {}}


def salva(d):
    os.makedirs(os.path.dirname(FILE), exist_ok=True)
    with open(FILE + ".tmp", "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
    os.replace(FILE + ".tmp", FILE)


def chiave(m):
    """La chiave di un mazzo: la sezione (mine, wish, build) e il suo id (o il nome)."""
    return f"{m.get('_sez') or 'mine'}:{m.get('id') or m.get('nome')}"


def gruppo(nome, d=None):
    """La regola del gruppo: public o private (il gruppo Arena decks non ne ha: None)."""
    if nome == ESCLUSO or nome is None:
        return None
    return (d or leggi())["gruppi"].get(nome, DEFAULT)


def mazzo(m, d=None):
    """(stato, eccezione) di un mazzo: lo stato vale la regola del suo gruppo o la sua eccezione; None per Arena decks."""
    d = d or leggi()
    g = gruppo(m.get("_gruppo"), d)
    if g is None:
        return None, False
    e = d["mazzi"].get(chiave(m))
    return (e or g), bool(e and e != g)


def cambia_gruppo(nome):
    if gruppo(nome) is None:
        return None
    d = leggi()
    d["gruppi"][nome] = PRIVATO if gruppo(nome, d) == PUBBLICO else PUBBLICO
    salva(d)
    return d["gruppi"][nome]


def cambia_mazzo(m):
    """Gira lo stato del mazzo; se torna come il gruppo, l'eccezione sparisce. -> lo stato nuovo."""
    d = leggi()
    stato, _ecc = mazzo(m, d)
    if stato is None:
        return None
    nuovo = PRIVATO if stato == PUBBLICO else PUBBLICO
    if nuovo == gruppo(m.get("_gruppo"), d):
        d["mazzi"].pop(chiave(m), None)
    else:
        d["mazzi"][chiave(m)] = nuovo
    salva(d)
    return nuovo


def privato_arena(id_mazzo, d=None):
    """Vero se il mazzo di Arena con quell'id e' privato (per la condivisione): il gruppo e' il suo formato, come in Your decks."""
    if not id_mazzo:
        return False
    d = d or leggi()
    if not d["gruppi"] and not d["mazzi"]:
        return False
    try:
        from dati_app import mazzi_arena_o_niente
        from gruppi_mazzi import nome_formato
        am = next((x for x in (mazzi_arena_o_niente() or []) if x.get("id") == id_mazzo), None)
    except Exception:       # noqa: BLE001 - senza i mazzi di Arena vale la regola di partenza
        am = None
    if not am or am.get("precon"):
        return False
    m = dict(id=id_mazzo, _sez="mine", _gruppo=nome_formato(am.get("formato")))
    return mazzo(m, d)[0] == PRIVATO


def prova():
    import tempfile
    casi = []
    vero = FILE
    globals()["FILE"] = os.path.join(tempfile.mkdtemp(), "v.json")
    try:
        a = dict(id="A", _sez="mine", _gruppo="Standard")
        b = dict(id="B", _sez="mine", _gruppo="Standard")
        casi.append(("di partenza pubblico, senza eccezione", mazzo(a) == (PUBBLICO, False)))
        cambia_gruppo("Standard")
        casi.append(("il gruppo privato: i suoi mazzi diventano privati", mazzo(a) == (PRIVATO, False) and mazzo(b) == (PRIVATO, False)))
        cambia_mazzo(a)
        casi.append(("un mazzo viola la regola: pubblico con l'eccezione, l'altro resta privato", mazzo(a) == (PUBBLICO, True) and mazzo(b) == (PRIVATO, False)))
        cambia_mazzo(a)
        casi.append(("ripremuto torna come il gruppo e l'eccezione sparisce", mazzo(a) == (PRIVATO, False) and not leggi()["mazzi"]))
        cambia_mazzo(a); cambia_gruppo("Standard")
        casi.append(("il gruppo torna pubblico: il mazzo pubblico per eccezione e ora uguale al gruppo, niente eccezione a vista",
                     mazzo(a) == (PUBBLICO, False) and mazzo(b) == (PUBBLICO, False)))
        w = dict(id="W", _sez="wish", _gruppo="Wishlist")
        casi.append(("la stessa id in un'altra sezione e' un altro mazzo", chiave(w) != chiave(dict(id="W", _sez="mine")) and mazzo(w) == (PUBBLICO, False)))
        p = dict(id="P", _sez="mine", _gruppo=ESCLUSO)
        casi.append(("negativa: Arena decks non ha la regola ne' il pulsante", mazzo(p) == (None, False) and cambia_mazzo(p) is None and cambia_gruppo(ESCLUSO) is None))
    finally:
        globals()["FILE"] = vero
    for n, v in casi:
        print(("ok    " if v else "ROSSO ") + n)
    ok = sum(1 for _n, v in casi if v)
    print(f"{ok}/{len(casi)}")
    return ok == len(casi)


if __name__ == "__main__":
    sys.exit(0 if prova() else 1)
