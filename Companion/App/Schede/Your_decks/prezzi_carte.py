"""Il prezzo delle carte vere, quelle di carta (Autore, 7 nov 2026: «alle carte aggiungiamo anche il valore economico della
carta reale e diamo anche il dato di costo totale del mazzo»).

Fonte: il bulk «Default Cards» di Scryfall (ogni stampa inglese, coi prezzi del giorno: euro da Cardmarket, dollari da
TCGplayer, tix da MTGO), scaricato in Dati/scryfall/default_cards/ (fuori da git; consenso permanente di Autore per i
file di dati di Scryfall, 8 ott 2026). Per ogni carta si tiene la stampa di carta piu' economica, non foil (la foil solo se la
carta non esiste non foil): e' quanto costa davvero averla. Il riassunto sta in Dati/scryfall/prezzi.json, letto dalla finestra.
Le carte solo digitali (Alchemy «A-», le carte di Arena) non hanno un prezzo: escono None, e il totale del mazzo lo dice.
Il bulk si rinnova se ha piu' di 7 giorni (`aggiorna`, in sottofondo dalla finestra): i prezzi cambiano ogni giorno, il file
ne porta la data.

  py -I -X utf8 Companion/App/Schede/Your_decks/prezzi_carte.py            rifa' prezzi.json dall'ultimo bulk
  py -I -X utf8 Companion/App/Schede/Your_decks/prezzi_carte.py --scarica  scarica il bulk di oggi e rifa' prezzi.json
  py -I -X utf8 Companion/App/Schede/Your_decks/prezzi_carte.py --carta "Sheoldred, the Apocalypse"
  py -I -X utf8 Companion/App/Schede/Your_decks/prezzi_carte.py --prova
"""
import os, sys
_casa = os.path.dirname(os.path.abspath(__file__))      # si sale fino a percorsi.py, che mette nel sys.path tutte le cartelle del Companion
while not os.path.isfile(os.path.join(_casa, "percorsi.py")):
    _casa = os.path.dirname(_casa)
if _casa not in sys.path:
    sys.path.insert(0, _casa)
import percorsi  # noqa: E402
import datetime
import glob
import gzip
import json
import threading
import urllib.request

ROOT = percorsi.ROOT
CARTELLA = os.path.join(ROOT, "Dati", "scryfall", "default_cards")
PREZZI = os.path.join(ROOT, "Dati", "scryfall", "prezzi.json")
CARTE = os.path.join(ROOT, "Dati", "scryfall", "carte.json")      # costo, colori, mana, tipo, mana prodotto e formati di ogni carta di carta (7 nov 2026, per le build e i formati che Arena non ha)
FORMATI = ("standard", "alchemy", "explorer", "historic", "timeless", "brawl", "standardbrawl", "pioneer", "modern", "legacy", "vintage", "pauper", "commander")
GIORNI = 7
SALTA = {"token", "double_faced_token", "art_series", "emblem", "planar", "scheme", "vanguard"}
AGENTE = "MagicArenaCompanion/1.0"

_CACHE, _INFO, _CHIAVE = None, None, threading.Lock()


def _numero(x):
    try:
        return float(x) if x not in (None, "") else None
    except ValueError:
        return None


def _minimo(a, b):
    return b if a is None else a if b is None else min(a, b)


def costruisci(f=None):
    """Dal bulk: {nome: dict(eur, usd, tix, layout)} con la stampa di carta piu' economica per ogni valuta. Anche la faccia davanti."""
    f = f or sorted(glob.glob(os.path.join(CARTELLA, "*.jsonl.gz")))[-1]
    out, foil, info = {}, {}, {}
    with gzip.open(f, "rt", encoding="utf-8") as g:
        for r in g:
            d = json.loads(r)
            if d.get("layout") not in SALTA and d["name"] not in info:
                facce = d.get("card_faces") or [d]
                col = d.get("colors") if d.get("colors") is not None else sorted({k for x in facce for k in (x.get("colors") or [])})
                leg = d.get("legalities") or {}
                info[d["name"]] = dict(m=d.get("mana_cost") or " // ".join(x.get("mana_cost", "") for x in facce if x.get("mana_cost")),
                                       c="".join(k for k in "WUBRG" if k in col), v=d.get("cmc") or 0,
                                       t=d.get("type_line") or " // ".join(x.get("type_line", "") for x in facce),
                                       p="".join(k for k in "WUBRGC" if k in (d.get("produced_mana") or [])),
                                       l=" ".join(k for k in FORMATI if leg.get(k) == "legal"), r=" ".join(k for k in FORMATI if leg.get(k) == "restricted"),
                                       b=" ".join(k for k in FORMATI if leg.get(k) == "banned"))      # dove e' bandita (10 nov 2026: le bandite in rosso nella Collection)
            if d.get("layout") in SALTA or "paper" not in (d.get("games") or []) and "mtgo" not in (d.get("games") or []):
                continue
            p = d.get("prices") or {}
            v = out.setdefault(d["name"], dict(eur=None, usd=None, tix=None, layout=d.get("layout")))
            if "paper" in (d.get("games") or []):
                v["eur"], v["usd"] = _minimo(v["eur"], _numero(p.get("eur"))), _minimo(v["usd"], _numero(p.get("usd")))
                w = foil.setdefault(d["name"], [None, None])
                w[0], w[1] = _minimo(w[0], _numero(p.get("eur_foil"))), _minimo(w[1], _numero(p.get("usd_foil")))
            v["tix"] = _minimo(v["tix"], _numero(p.get("tix")))
    for n, (e, u) in foil.items():      # esiste solo foil: vale quella
        if out[n]["eur"] is None:
            out[n]["eur"] = e
        if out[n]["usd"] is None:
            out[n]["usd"] = u
    data = os.path.basename(f).split("-")[-1][:8]
    return dict(data=f"{data[:4]}-{data[4:6]}-{data[6:8]}", carte=out, info=info)


def scrivi(f=None):
    global _CACHE, _INFO
    d = costruisci(f)
    info = d.pop("info")
    for dest, dati in ((PREZZI, d), (CARTE, dict(data=d["data"], carte=info))):
        tmp = dest + ".tmp"
        with open(tmp, "w", encoding="utf-8") as g:
            json.dump(dati, g, ensure_ascii=False, separators=(",", ":"))
        os.replace(tmp, dest)
    with _CHIAVE:
        _CACHE = _INFO = None
    return d


def scarica():
    """Il bulk Default Cards di oggi (circa 80 MB), poi prezzi.json. I bulk vecchi si cancellano."""
    req = urllib.request.Request("https://api.scryfall.com/bulk-data/default-cards", headers={"User-Agent": AGENTE, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        info = json.load(r)
    url = info.get("jsonl_download_uri") or info["download_uri"]
    os.makedirs(CARTELLA, exist_ok=True)
    dest = os.path.join(CARTELLA, os.path.basename(url))
    if not os.path.exists(dest):
        req = urllib.request.Request(url, headers={"User-Agent": AGENTE})
        with urllib.request.urlopen(req, timeout=600) as r, open(dest + ".part", "wb") as g:
            while True:
                b = r.read(1 << 20)
                if not b:
                    break
                g.write(b)
        os.replace(dest + ".part", dest)
    for vecchio in glob.glob(os.path.join(CARTELLA, "*.jsonl.gz")):
        if vecchio != dest:
            os.remove(vecchio)
    return scrivi(dest)


def eta():
    """Giorni dall'ultimo bulk, o None se non c'e'."""
    f = sorted(glob.glob(os.path.join(CARTELLA, "*.jsonl.gz")))
    if not f:
        return None
    return (datetime.datetime.now() - datetime.datetime.fromtimestamp(os.path.getmtime(f[-1]))).days


def aggiorna():
    """Se il bulk ha piu' di GIORNI giorni lo riscarica; se prezzi.json manca o e' piu' vecchio del bulk lo rifa'. Per il sottofondo: non solleva."""
    try:
        e = eta()
        if e is None or e > GIORNI:
            scarica()
            return True
        f = sorted(glob.glob(os.path.join(CARTELLA, "*.jsonl.gz")))[-1]
        if not os.path.exists(PREZZI) or not os.path.exists(CARTE) or os.path.getmtime(PREZZI) < os.path.getmtime(f):
            scrivi(f)
            return True
    except Exception:
        pass
    return False


def condividi(carte):
    """{nome: {campo: valore}} con una copia sola di ogni valore uguale (11 nov 2026, sessione Magic 13): il lettore JSON fa un oggetto nuovo per ogni
    stringa e ogni numero, e 35.358 carte ripetono le stesse righe di tipo, gli stessi elenchi di formati, gli stessi prezzi. I formati da 21,7 a 13,8 MB,
    dati uguali. Un dizionario per tipo: 0 e 0.0 restano diversi."""
    memo = {}
    return {n: {k: (memo.setdefault((type(v), v), v) if isinstance(v, (str, float, int)) else v) for k, v in c.items()} if isinstance(c, dict) else c
            for n, c in carte.items()}


def tutti():
    global _CACHE
    with _CHIAVE:
        if _CACHE is None:
            try:
                with open(PREZZI, encoding="utf-8") as g:
                    _CACHE = json.load(g)
                _CACHE["carte"] = condividi(_CACHE.get("carte") or {})
            except (OSError, ValueError):
                _CACHE = dict(data=None, carte={})
                return _CACHE      # non si tiene: appena il file c'e' si rilegge
            fronte = {}
            for n, v in _CACHE["carte"].items():
                if " // " in n:
                    fronte.setdefault(n.split(" // ")[0], v)
            for n, v in fronte.items():
                _CACHE["carte"].setdefault(n, v)
        return _CACHE


def prezzo(nome):
    """dict(eur, usd, tix, layout) della carta, o None se la carta non esiste di carta (Alchemy, solo Arena) o il file manca."""
    c = tutti()["carte"]
    if nome.startswith("A-"):
        return None
    return c.get(nome) or c.get(nome.split(" // ")[0].strip())


def data():
    return tutti().get("data")


def carta(nome):
    """dict(m costo, c colori, v mana, t tipo, p mana prodotto, l formati dove e' legale, r dove e' ristretta, b dove e' bandita) dal bulk di Scryfall, o None.
    Anche per la faccia davanti. Le carte Alchemy (A-) non ci sono."""
    global _INFO
    with _CHIAVE:
        if _INFO is None:
            try:
                with open(CARTE, encoding="utf-8") as g:
                    _INFO = condividi(json.load(g)["carte"])
            except (OSError, ValueError, KeyError):
                return None
            for n, v in list(_INFO.items()):
                if " // " in n:
                    _INFO.setdefault(n.split(" // ")[0], v)
    return _INFO.get(nome) or _INFO.get(nome.split(" // ")[0].strip())


def totale(carte):
    """carte: {nome: copie} -> (euro, dollari, [nomi senza prezzo]). Le basi contano, al loro prezzo."""
    e = u = 0.0
    senza = []
    for n, q in carte.items():
        p = prezzo(n)
        if not p or p.get("eur") is None and p.get("usd") is None:
            senza.append(n)
            continue
        e += q * (p["eur"] or 0)
        u += q * (p["usd"] or 0)
    return e, u, senza


def euro(x):
    """Il prezzo da leggere: €0.25, €12.40, €1,240."""
    if x is None:
        return "-"
    return f"€{x:,.0f}" if x >= 1000 else f"€{x:.2f}"


def prova():
    righe = [{"name": "Prova A", "layout": "normal", "games": ["paper", "arena"], "prices": {"eur": "2.00", "usd": "3.00", "tix": "0.10"}},
             {"name": "Prova A", "layout": "normal", "games": ["paper"], "prices": {"eur": "0.50", "usd": None, "tix": None}},
             {"name": "Prova A", "layout": "normal", "games": ["arena"], "prices": {"eur": "0.01"}},      # una stampa solo digitale non ha prezzo di carta
             {"name": "Prova B // Retro", "layout": "transform", "games": ["paper"], "prices": {"eur": None, "eur_foil": "4.00", "usd": "1.00"}},
             {"name": "Prova B", "layout": "token", "games": ["paper"], "prices": {"eur": "0.05"}},
             {"name": "Prova C", "layout": "normal", "games": ["mtgo"], "prices": {"tix": "0.02"}}]
    import tempfile
    t = os.path.join(tempfile.mkdtemp(), "default-cards-20261107000000.jsonl.gz")
    with gzip.open(t, "wt", encoding="utf-8") as g:
        for r in righe:
            g.write(json.dumps(r) + "\n")
    d = costruisci(t)
    c = d["carte"]
    info_b = d["info"].get("Prova B // Retro") or {}
    global _CACHE
    salvata = _CACHE
    _CACHE = None
    with _CHIAVE:
        pass
    _CACHE = dict(data=d["data"], carte=dict(c))
    for n, v in list(c.items()):
        if " // " in n:
            _CACHE["carte"].setdefault(n.split(" // ")[0], v)
    tot = totale({"Prova A": 4, "Prova B // Retro": 1, "A-Prova A": 1, "Inesistente": 2})
    casi = [("la stampa di carta piu' economica", c["Prova A"]["eur"] == 0.5 and c["Prova A"]["usd"] == 3.0),
            ("una stampa solo digitale non abbassa il prezzo (prova negativa: 0,01 sarebbe il minimo)", c["Prova A"]["eur"] != 0.01),
            ("i tix dalla stampa di MTGO", c["Prova A"]["tix"] == 0.1 and c["Prova C"]["tix"] == 0.02 and c["Prova C"]["eur"] is None),
            ("la foil solo se non c'e' altro", c["Prova B // Retro"]["eur"] == 4.0),
            ("la pedina non e' la carta", "Prova B" not in c),
            ("la faccia davanti trova la carta", prezzo("Prova B") is not None),
            ("Alchemy senza prezzo", prezzo("A-Prova A") is None),
            ("il totale del mazzo", abs(tot[0] - 6.0) < 1e-9 and sorted(tot[2]) == ["A-Prova A", "Inesistente"]),
            ("la data del bulk", d["data"] == "2026-11-07"),
            ("le carte hanno tipo e formati", "Prova B" not in d["info"] and info_b.get("t", None) == "" and "Prova C" in d["info"]),
            ("il prezzo scritto", euro(0.5) == "€0.50" and euro(1240) == "€1,240" and euro(None) == "-")]
    _CACHE = salvata
    ok = True
    for nome, esito in casi:
        print(("OK   " if esito else "ROSSO") + " " + nome)
        ok &= esito
    print(f"{sum(e for _n, e in casi)}/{len(casi)}")
    return ok


if __name__ == "__main__":
    if "--prova" in sys.argv:
        sys.exit(0 if prova() else 1)
    if "--carta" in sys.argv:
        n = sys.argv[sys.argv.index("--carta") + 1]
        print(n, prezzo(n), "del", data())
        sys.exit(0)
    d = scarica() if "--scarica" in sys.argv else scrivi()
    print(f"prezzi.json: {len(d['carte'])} carte, bulk del {d['data']}")
