"""Il primo avvio dell'app pubblica (10 nov 2026, Autore: «far scaricare l'app al pubblico … aggiornabile da noi»): i dati che l'app legge e che non stanno
nello zip. Nell'app di Autore non fa niente: i dati ci sono gia'.

Cosa serve e da dove viene:
- il database delle carte di Arena: Dati/untapped/arena_cards/cards.json e loc_en.json (mtgajson.untapped.gg, pubblico, ~19 MB; lo usano tutti i tracker);
- i bulk di Scryfall (scaricati dal PC di chi usa l'app, gratis, come chiedono le regole dell'API: i dati non stanno dietro un pagamento):
  Default Cards (~81 MB, prezzi, tipi, legalita': prezzi_carte.scarica) e Oracle Cards (~25 MB, gli indirizzi delle immagini: capsule.indirizzi);
- il nostro pacchetto dati (dati_pacchetto.zip, nello zip dell'app e poi dal canale degli aggiornamenti): Regole (pool e ban dello Standard, set, calendari),
  il meta dei formati, i quaderni dei set; si estrae se e' piu' nuovo di quello estratto (Dati/pacchetto_versione.txt);
- la collezione: senza un profilo di Untapped collegato (account.py) parte vuota ({"cards": []}) e cresce coi log;
- i nomi delle carte per grpId (Collezione/arena_cards_cache.json: nome, rarita' C U R M, set; lo leggono tavolo.py, i premi e i jolly) e le copie per nome
  (Collezione/collezione_nomi.json), rifatti dal database di Arena quando cambia: nel progetto di Autore li scrive Collezione/scarica_collezione.py.
  Il formato e' lo stesso, controllato il 10 nov 2026: 27.720 carte su 27.720 col nome uguale, rarita' 2 3 4 5 -> C U R M, il resto «?».
Ogni passo che manca si rifa' al prossimo avvio; uno che non riesce non ferma l'app (le schede dicono quello che non hanno).

    py -I -X utf8 Companion/App/Comune/primo_avvio.py --prova     su una cartella vuota, senza rete (i download finti)
"""
import os, sys
_casa = os.path.dirname(os.path.abspath(__file__))      # si sale fino a percorsi.py, che mette nel sys.path tutte le cartelle del Companion
while not os.path.isfile(os.path.join(_casa, "percorsi.py")):
    _casa = os.path.dirname(_casa)
if _casa not in sys.path:
    sys.path.insert(0, _casa)
import percorsi  # noqa: E402
import glob  # noqa: E402
import json  # noqa: E402
import urllib.request  # noqa: E402
import zipfile  # noqa: E402

AGENTE = "companion-magic-arena/1.0"
MTGAJSON = "https://mtgajson.untapped.gg/v1/latest/"


def cartelle(root=None):
    r = root or percorsi.ROOT
    return dict(root=r, arena=os.path.join(r, "Dati", "untapped", "arena_cards"), oracle=os.path.join(r, "Dati", "scryfall", "oracle_cards"),
                default=os.path.join(r, "Dati", "scryfall", "default_cards"), coll=os.path.join(r, "Collezione", "collezione.json"),
                pacchetto=os.path.join(r, "dati_pacchetto.zip"), versione=os.path.join(r, "Dati", "pacchetto_versione.txt"))


def scarica_file(url, dest, timeout=600):
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": AGENTE})
    with urllib.request.urlopen(req, timeout=timeout) as r, open(dest + ".part", "wb") as g:
        while True:
            b = r.read(1 << 20)
            if not b:
                break
            g.write(b)
    os.replace(dest + ".part", dest)


def arena_db(c):
    for n in ("cards.json", "loc_en.json"):
        scarica_file(MTGAJSON + n, os.path.join(c["arena"], n))


def oracle(c):
    req = urllib.request.Request("https://api.scryfall.com/bulk-data/oracle-cards", headers={"User-Agent": AGENTE, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        info = json.load(r)
    url = info.get("jsonl_download_uri") or info["download_uri"]
    scarica_file(url, os.path.join(c["oracle"], os.path.basename(url)))


def default_cards(c):
    import prezzi_carte
    prezzi_carte.scarica()


def versione_pacchetto(zip_):
    try:
        with zipfile.ZipFile(zip_) as z:
            return json.loads(z.read("pacchetto.json")).get("versione")
    except (OSError, KeyError, ValueError, zipfile.BadZipFile):
        return None


def pacchetto(c):
    """Estrae il pacchetto dati nella cartella dell'app se e' piu' nuovo di quello gia' estratto; solo i percorsi dentro la cartella."""
    v = versione_pacchetto(c["pacchetto"])
    if v is None:
        return
    with zipfile.ZipFile(c["pacchetto"]) as z:
        radice = os.path.realpath(c["root"])
        for n in z.namelist():
            dest = os.path.realpath(os.path.join(c["root"], n))
            if not dest.startswith(radice + os.sep):        # un nome come ../x non esce mai dalla cartella
                raise ValueError(f"pacchetto: percorso fuori dalla cartella: {n}")
        z.extractall(c["root"])
    os.makedirs(os.path.dirname(c["versione"]), exist_ok=True)
    open(c["versione"], "w", encoding="utf-8").write(v)


def collezione_vuota(c):
    os.makedirs(os.path.dirname(c["coll"]), exist_ok=True)
    json.dump({"cards": []}, open(c["coll"], "w", encoding="utf-8"))


RARITA = {2: "C", 3: "U", 4: "R", 5: "M"}


def nomi_carte(c):
    """Collezione/arena_cards_cache.json e collezione_nomi.json dal database di Arena e dalla collezione (come scarica_collezione.py)."""
    carte = json.load(open(os.path.join(c["arena"], "cards.json"), encoding="utf-8"))
    loc = {e["id"]: e["text"] for e in json.load(open(os.path.join(c["arena"], "loc_en.json"), encoding="utf-8"))}
    cache = {str(x["grpid"]): dict(n=loc.get(x.get("titleId"), f"grp{x['grpid']}"), r=RARITA.get(x.get("rarity"), "?"), set=x.get("set")) for x in carte}
    cartella = os.path.dirname(c["coll"])
    os.makedirs(cartella, exist_ok=True)
    json.dump(cache, open(os.path.join(cartella, "arena_cards_cache.json"), "w", encoding="utf-8"), ensure_ascii=False)
    nomi = {}
    try:
        for x in json.load(open(c["coll"], encoding="utf-8")).get("cards") or []:
            n = cache.get(str(x.get("grpid")), {}).get("n")
            if n:
                nomi[n] = nomi.get(n, 0) + x.get("quantity", 0)
    except (OSError, ValueError):
        pass
    json.dump(nomi, open(os.path.join(cartella, "collezione_nomi.json"), "w", encoding="utf-8"), ensure_ascii=False)


def nomi_vecchi(c):
    f, db = os.path.join(os.path.dirname(c["coll"]), "arena_cards_cache.json"), os.path.join(c["arena"], "cards.json")
    return os.path.exists(db) and (not os.path.exists(f) or os.path.getmtime(f) < os.path.getmtime(db))


def passi(c):
    """[(nome, che cosa fa, manca?, funzione)] nell'ordine."""
    estratto = open(c["versione"], encoding="utf-8").read().strip() if os.path.exists(c["versione"]) else None
    nuovo = versione_pacchetto(c["pacchetto"])
    return [("pacchetto", "Our data pack (rules, meta, set notes)", nuovo is not None and nuovo != estratto, pacchetto),
            ("arena", "Arena card database (19 MB)", not all(os.path.exists(os.path.join(c["arena"], n)) for n in ("cards.json", "loc_en.json")), arena_db),
            ("oracle", "Scryfall card images index (25 MB)", not glob.glob(os.path.join(c["oracle"], "*.jsonl.gz")), oracle),
            ("default", "Scryfall prices and formats (81 MB)", not glob.glob(os.path.join(c["default"], "*.jsonl.gz")), default_cards),
            ("collezione", "Empty collection (link Untapped to fill it)", not os.path.exists(c["coll"]), collezione_vuota)]


def passi_dopo(c):
    """I passi che vogliono il database di Arena gia' scaricato: si guardano dopo gli altri."""
    return [("nomi", "Card names", nomi_vecchi(c), nomi_carte)]


def esegui(root=None, avviso=print):
    """Fa i passi che mancano; avviso(testo) a ogni passo. -> {nome: None se fatto, o il testo dell'errore}."""
    c = cartelle(root)
    esito = {}
    for gruppo in (passi, passi_dopo):      # i nomi delle carte vogliono il database di Arena: si guardano dopo che e' arrivato
        for nome, testo, manca, f in gruppo(c):
            if not manca:
                continue
            avviso(testo + "…")
            try:
                f(c)
                esito[nome] = None
            except Exception as e:      # noqa: BLE001 - un passo che non riesce si rifa' al prossimo avvio
                esito[nome] = f"{type(e).__name__}: {e}"
    return esito


def prova():
    import tempfile
    d = tempfile.mkdtemp()
    c = cartelle(d)
    z = zipfile.ZipFile(c["pacchetto"], "w")
    z.writestr("pacchetto.json", json.dumps({"versione": "2026.11.10"}))
    z.writestr("Regole/Set_Legali.md", "| x |")
    z.close()
    finti = {}
    for k in ("arena_db", "oracle", "default_cards"):
        finti[k] = globals()[k]
    def arena_finto(c_):
        os.makedirs(c_["arena"], exist_ok=True)
        json.dump([dict(grpid=10, titleId=1, rarity=4, set="FRA"), dict(grpid=11, titleId=2, rarity=1, set="FRA")], open(os.path.join(c_["arena"], "cards.json"), "w"))
        json.dump([dict(id=1, text="Asso"), dict(id=2, text="Plains")], open(os.path.join(c_["arena"], "loc_en.json"), "w"))
    globals()["arena_db"] = arena_finto
    globals()["oracle"] = lambda c_: (os.makedirs(c_["oracle"], exist_ok=True), open(os.path.join(c_["oracle"], "o.jsonl.gz"), "wb").write(b""))
    globals()["default_cards"] = lambda c_: (_ for _ in ()).throw(OSError("rete assente"))
    try:
        e1 = esegui(d, avviso=lambda t: None)
        e2 = esegui(d, avviso=lambda t: None)
    finally:
        globals().update(finti)
    casi = [("il pacchetto si estrae", os.path.exists(os.path.join(d, "Regole", "Set_Legali.md")) and open(c["versione"]).read() == "2026.11.10"),
            ("il database di Arena e l'indice delle immagini", e1.get("arena") is None and e1.get("oracle") is None and "arena" not in e2),
            ("la collezione vuota", json.load(open(c["coll"])) == {"cards": []}),
            ("un passo che non riesce non ferma gli altri e si rifa' al giro dopo", "OSError" in (e1.get("default") or "") and "default" in e2),
            ("negativa: lo stesso pacchetto non si estrae due volte", "pacchetto" not in e2),
            ("i nomi delle carte dal database di Arena, una volta", json.load(open(os.path.join(d, "Collezione", "arena_cards_cache.json")))
             == {"10": dict(n="Asso", r="R", set="FRA"), "11": dict(n="Plains", r="?", set="FRA")} and e1.get("nomi") is None and "nomi" not in e2)]
    cattivo = os.path.join(d, "cattivo.zip")
    z = zipfile.ZipFile(cattivo, "w"); z.writestr("pacchetto.json", json.dumps({"versione": "9"})); z.writestr("../fuori.txt", "x"); z.close()
    try:
        pacchetto(dict(c, pacchetto=cattivo))
        fuori = False
    except ValueError:
        fuori = True
    casi.append(("negativa: un pacchetto con un percorso fuori dalla cartella si rifiuta", fuori and not os.path.exists(os.path.join(os.path.dirname(d), "fuori.txt"))))
    ok = sum(1 for _n, v in casi if v)
    for n, v in casi:
        print(("ok    " if v else "ROSSO ") + n)
    print(f"{ok}/{len(casi)}")
    return ok == len(casi)


if __name__ == "__main__":
    if "--prova" in sys.argv:
        sys.exit(0 if prova() else 1)
    print(esegui())
