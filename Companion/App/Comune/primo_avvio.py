"""Il primo avvio dell'app pubblica (10 nov 2026, Autore: «far scaricare l'app al pubblico … aggiornabile da noi»): i dati che l'app legge e che non stanno
nello zip. Nell'app di Autore non fa niente: i dati ci sono gia'.

Cosa serve e da dove viene:
- il database delle carte di Arena: Dati/untapped/arena_cards/cards.json e loc_en.json, dalla 0.1.10 esportati dal client di Arena di questo PC
  (Raw_CardDatabase_*.mtga, arena_db) e rifatti quando Arena ne scarica uno nuovo; fino alla 0.1.8 da mtgajson.untapped.gg (la cartella ha tenuto il nome);
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
import piattaforma  # noqa: E402  (i percorsi di Arena su Windows e su Mac)
import glob  # noqa: E402
import json  # noqa: E402
import urllib.request  # noqa: E402
import zipfile  # noqa: E402

AGENTE = "companion-magic-arena/1.0"


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
    """Il database delle carte di Arena. Dalla 0.1.10 (11 nov 2026, sessione Magic 14, Distribuzione/Business_Model.md sezione 5) si legge dal client di
    Arena installato su questo PC, non piu' da mtgajson.untapped.gg: i termini di Untapped (untapped.gg/legal/terms-of-service) danno i loro servizi solo
    per uso personale e non commerciale e vietano di ridistribuirli, e quell'indirizzo non ha una licenza sua. Si scrivono gli stessi due file, nello
    stesso formato (cards.json, loc_en.json), quindi chi li legge non cambia: confrontati l'11 nov 2026 con quelli di mtgajson su 27.720 carte, nomi,
    rarita', colori, costi, tipi, abilita' e facce uguali; il valore di mana diverso solo su 2 carte coi simboli {C/W}, che mtgajson lascia vuoto."""
    db = db_locale()
    if not db:
        raise FileNotFoundError("MTG Arena's card database was not found on this PC: start MTG Arena once, then reopen the app")
    esporta_db(db, c["arena"])


# --- il database delle carte dal client di Arena (Raw_CardDatabase_*.mtga, SQLite, letto in sola lettura) ---

ARENA_LOG = piattaforma.cartella_arena()
ARENA_DIRS = [r"C:\Program Files\Wizards of the Coast\MTGA\MTGA_Data", r"C:\Program Files (x86)\Wizards of the Coast\MTGA\MTGA_Data",
              r"C:\Program Files\Epic Games\MagicTheGathering\MTGA_Data", r"C:\Program Files (x86)\Steam\steamapps\common\MTGA\MTGA_Data"]
# Mac (11 nov 2026, non provato su un Mac vero: Distribuzione/Mac.md): la cartella dei dati di Unity dentro l'app e quella dei dati dell'utente che le fonti
# indicano per Arena (~/Library/Application Support/com.wizards.mtga). Dove stia di preciso il Raw_CardDatabase su Mac nessuna fonte lo dice: si cerca.
ARENA_DIRS_MAC = ["/Applications/MTGA.app/Contents/Resources/Data", os.path.expanduser("~/Library/Application Support/com.wizards.mtga")]


def db_locale(log_dir=None, altre=None):
    """Il Raw_CardDatabase piu' recente: la cartella di Arena la scrive il Player.log nelle prime righe (E:/SteamLibrary/MTGA/MTGA_Data sul PC di prova),
    poi le cartelle di installazione solite. None se non c'e'."""
    import re
    dirs = []
    for n in ("Player.log", "Player-prev.log"):
        try:
            with open(os.path.join(log_dir or ARENA_LOG, n), encoding="utf-8", errors="ignore") as f:
                for i, r in enumerate(f):
                    m = re.search(r"([A-Za-z]:[\\/][^\"'\n]*?MTGA_Data)", r)
                    if m:
                        dirs.append(m.group(1)); break
                    m = None if piattaforma.WINDOWS else re.search(r"Mono path\[0\] = '(/[^'\n]*?)/Managed'", r)      # Mac: .../MTGA.app/Contents/Resources/Data
                    if m:
                        dirs.append(m.group(1)); break
                    if i > 3000:
                        break
        except OSError:
            pass
    dirs += (ARENA_DIRS if piattaforma.WINDOWS else ARENA_DIRS_MAC) if altre is None else altre
    for d in dirs:
        f = sorted(glob.glob(os.path.join(d, "Downloads", "Raw", "Raw_CardDatabase_*.mtga")), key=os.path.getmtime)
        if not f and not piattaforma.WINDOWS:       # su Mac la cartella esatta non e' nota: si cerca sotto (la cartella dei dati di Arena)
            f = sorted(glob.glob(os.path.join(d, "**", "Raw_CardDatabase_*.mtga"), recursive=True), key=os.path.getmtime)
        if f:
            return f[-1]
    return None


def _lista(s):
    return [int(x) for x in str(s or "").split(",") if x.strip().lstrip("-").isdigit()]


def _abilita(s):
    out = []
    for x in str(s or "").split(","):
        if ":" in x:
            a, b = x.split(":", 1)
            if a.strip().isdigit() and b.strip().isdigit():
                out.append({"Id": int(a), "TextId": int(b)})
    return out


def _cmc(costo):
    """Il valore di mana dal costo di Arena («o6oGoG» -> 8): un numero vale se stesso, X zero, l'ibrido {2/W} 2 (202.3f), ogni altro simbolo (colore,
    ibrido, phyrexiano, {C/W}) 1."""
    n = 0
    for t in str(costo or "").split("o"):
        t = t.strip()
        if not t:
            continue
        if t.isdigit():
            n += int(t)
        elif t.startswith("(2/"):
            n += 2
        elif t != "X":
            n += 1
    return n


def carte_da_db(db):
    """[carta] nel formato di cards.json (lo stesso nome dei campi del database di mtgajson, che ne e' una copia). Solo i campi che servono a chi li legge."""
    import sqlite3
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    out = []
    for r in con.execute("SELECT * FROM Cards"):
        x = {"grpid": r["GrpId"], "titleId": r["TitleId"], "artId": r["ArtId"], "set": r["ExpansionCode"] or "", "collectorNumber": r["CollectorNumber"],
             "cardTypeTextId": r["TypeTextId"], "artistCredit": r["ArtistCredit"]}
        for chiave, col in (("types", "Types"), ("frameColors", "FrameColors"), ("colorIdentity", "ColorIdentity"), ("colors", "Colors"),
                            ("subtypes", "Subtypes"), ("supertypes", "Supertypes"), ("linkedFaces", "LinkedFaceGrpIds")):
            v = _lista(r[col])
            if v:
                x[chiave] = v
        if x.get("subtypes"):
            x["subtypeTextId"] = r["SubtypeTextId"]
        if r["Rarity"]:
            x["rarity"] = r["Rarity"]
        if r["OldSchoolManaText"]:
            x["castingcost"] = r["OldSchoolManaText"]
            if _cmc(r["OldSchoolManaText"]):         # come mtgajson: un valore di mana zero non si scrive
                x["cmc"] = _cmc(r["OldSchoolManaText"])
        for chiave, col in (("power", "Power"), ("toughness", "Toughness"), ("collectorMax", "CollectorMax"), ("DigitalReleaseSet", "DigitalReleaseSet"),
                            ("watermark", "Watermark")):
            if r[col]:
                x[chiave] = r[col]
        for chiave, col in (("abilities", "AbilityIds"), ("hiddenAbilities", "HiddenAbilityIds")):
            v = _abilita(r[col])
            if v:
                x[chiave] = v
        for chiave, col in (("isToken", "IsToken"), ("IsDigitalOnly", "IsDigitalOnly"), ("IsRebalanced", "IsRebalanced"), ("usesSideboard", "UsesSideboard")):
            if r[col]:
                x[chiave] = True
        if not r["IsPrimaryCard"]:
            x["isSecondaryCard"] = True
        for chiave, col in (("linkedFaceType", "LinkedFaceType"), ("altDeckLimit", "AlternateDeckLimit"), ("altTitleId", "AltTitleId"),
                            ("interchangeableTitleId", "InterchangeableTitleId"), ("DefunctRebalancedCardLink", "DefunctRebalancedCardGrpId")):
            if r[col]:
                x[chiave] = r[col]
        out.append(x)
    return out


def testi_da_db(db):
    """[{"id", "text"}] nel formato di loc_en.json: i testi inglesi senza la formattazione (Formatted 0 se c'e', se no il primo)."""
    import sqlite3
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    testi = {}
    for loc, fmt, t in con.execute("SELECT LocId, Formatted, Loc FROM Localizations_enUS ORDER BY LocId, Formatted"):
        if loc not in testi or fmt == 0:
            testi[loc] = t or ""
    return [{"id": k, "text": v} for k, v in sorted(testi.items())]


def esporta_db(db, cartella):
    os.makedirs(cartella, exist_ok=True)
    for nome, dati in (("cards.json", carte_da_db(db)), ("loc_en.json", testi_da_db(db))):
        dest = os.path.join(cartella, nome)
        json.dump(dati, open(dest + ".part", "w", encoding="utf-8"), ensure_ascii=False)
        os.replace(dest + ".part", dest)
    json.dump({"db": os.path.basename(db), "mtime": os.path.getmtime(db)}, open(os.path.join(cartella, "fonte.json"), "w", encoding="utf-8"))


def db_nuovo(c, db=None):
    """Vero se manca il database esportato o se Arena ne ha uno piu' nuovo (un aggiornamento del gioco, un set nuovo)."""
    if not all(os.path.exists(os.path.join(c["arena"], n)) for n in ("cards.json", "loc_en.json", "fonte.json")):
        return True
    db = db or db_locale()
    if not db:
        return False
    try:
        f = json.load(open(os.path.join(c["arena"], "fonte.json"), encoding="utf-8"))
    except (OSError, ValueError):
        return True
    return f.get("db") != os.path.basename(db) or os.path.getmtime(db) > f.get("mtime", 0) + 1


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
        dentro = set(z.namelist())
    for pat in USCITI:       # i file che un pacchetto di prima portava e questo no: via, se no restano sul PC e la finestra li legge ancora
        for f in glob.glob(os.path.join(c["root"], pat)):
            if os.path.relpath(f, c["root"]).replace(os.sep, "/") not in dentro:
                os.remove(f)
    os.makedirs(os.path.dirname(c["versione"]), exist_ok=True)
    open(c["versione"], "w", encoding="utf-8").write(v)


# usciti dal pacchetto con la 0.1.5 (10 nov 2026, Autore: «Sì, toglili»): il meta e le note del Quick presi da Untapped.gg, i cui termini vietano di
# ridistribuirli. I quaderni delle carte (anagrafe.json) li sovrascrive il pacchetto nuovo, gia' senza il campo «untapped».
# Con la 0.1.10 (11 nov 2026, sessione Magic 14, Distribuzione/Business_Model.md sezione 5) anche il meta di MTGGoldfish: i loro termini (mtggoldfish.com/
# policies/terms-of-use) danno i contenuti solo per uso personale e non commerciale. I quaderni del pacchetto nuovo non hanno piu' i numeri di 17Lands.
USCITI = ["Note/meta_untapped*.json", "Espansioni/*/Quick/Quick_Draft.md", "Note/meta_goldfish_*.json"]


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
            ("arena", "Arena card database (from your MTG Arena install)", db_nuovo(c), arena_db),
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
        json.dump({"db": "finto", "mtime": 0}, open(os.path.join(c_["arena"], "fonte.json"), "w"))
    finti["db_locale"] = db_locale
    globals()["db_locale"] = lambda *a, **k: None          # nessun Arena su questo PC finto: il database esportato resta quello
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
    # un'installazione di prima con il meta di Untapped: il pacchetto nuovo lo toglie, e tiene quello che porta lui (negativa: il file di MTGGoldfish resta)
    for n in ("Note/meta_untapped.json", "Note/meta_untapped_historic.json", "Espansioni/FRA/Quick/Quick_Draft.md", "Note/meta_goldfish_modern.json"):
        os.makedirs(os.path.dirname(os.path.join(d, n)), exist_ok=True)
        open(os.path.join(d, n), "w").write("vecchio")
    nuovo = os.path.join(d, "nuovo.zip")
    z = zipfile.ZipFile(nuovo, "w"); z.writestr("pacchetto.json", json.dumps({"versione": "2026.11.11"})); z.writestr("Note/meta_goldfish_modern.json", "[]"); z.close()
    pacchetto(dict(c, pacchetto=nuovo))
    casi.append(("il meta di Untapped di un'installazione vecchia se ne va", not glob.glob(os.path.join(d, "Note", "meta_untapped*.json"))
                 and not os.path.exists(os.path.join(d, "Espansioni", "FRA", "Quick", "Quick_Draft.md"))))
    casi.append(("negativa: il file che il pacchetto porta resta, nuovo", open(os.path.join(d, "Note", "meta_goldfish_modern.json")).read() == "[]"))
    casi += prova_db(d)
    ok = sum(1 for _n, v in casi if v)
    for n, v in casi:
        print(("ok    " if v else "ROSSO ") + n)
    print(f"{ok}/{len(casi)}")
    return ok == len(casi)


def prova_db(d):
    """L'esportazione dal client di Arena su un database finto con le tabelle vere (Cards, Localizations_enUS): i campi come mtgajson."""
    import sqlite3
    import time
    db = os.path.join(d, "Raw", "Raw_CardDatabase_finto.mtga")
    os.makedirs(os.path.dirname(db), exist_ok=True)
    con = sqlite3.connect(db)
    col = ["GrpId", "ArtId", "TitleId", "TypeTextId", "SubtypeTextId", "ArtistCredit", "Rarity", "ExpansionCode", "DigitalReleaseSet", "IsToken",
           "IsPrimaryCard", "IsDigitalOnly", "IsRebalanced", "AlternateDeckLimit", "CollectorNumber", "CollectorMax", "UsesSideboard", "OldSchoolManaText",
           "LinkedFaceType", "Watermark", "Power", "Toughness", "Colors", "ColorIdentity", "FrameColors", "Types", "Subtypes", "Supertypes", "AbilityIds",
           "HiddenAbilityIds", "LinkedFaceGrpIds", "AltTitleId", "InterchangeableTitleId", "DefunctRebalancedCardGrpId"]
    con.execute(f"CREATE TABLE Cards({', '.join(col)})")
    con.execute("CREATE TABLE Localizations_enUS(LocId INT, Formatted INT, Loc TEXT)")
    riga = dict.fromkeys(col, ""); riga.update({k: 0 for k in ("IsToken", "IsDigitalOnly", "IsRebalanced", "AlternateDeckLimit", "UsesSideboard", "LinkedFaceType",
                                                               "AltTitleId", "InterchangeableTitleId", "DefunctRebalancedCardGrpId", "SubtypeTextId", "Rarity")})
    a = dict(riga, GrpId=6873, ArtId=1837, TitleId=2929, TypeTextId=8, SubtypeTextId=738, ArtistCredit="Steve White", Rarity=2, ExpansionCode="MIR",
             IsPrimaryCard=1, CollectorNumber="210", OldSchoolManaText="o6oGoG", Power="8", Toughness="4", Colors="5", ColorIdentity="5", Types="2",
             Subtypes="55", AbilityIds="14:28")
    b = dict(riga, GrpId=95700, TitleId=3000, IsPrimaryCard=0, OldSchoolManaText="o(2/R)o(2/W)o(2/B)", Types="10", LinkedFaceGrpIds="95701,95702")
    for r in (a, b):
        con.execute(f"INSERT INTO Cards VALUES ({', '.join('?' * len(col))})", [r[k] for k in col])
    con.executemany("INSERT INTO Localizations_enUS VALUES (?, ?, ?)", [(2929, 1, "Crash of <b>Rhinos</b>"), (2929, 0, "Crash of Rhinos"), (3000, 1, "Tre ibridi")])
    con.commit(); con.close()
    c = cartelle(d)
    esporta_db(db, c["arena"])
    carte = {x["grpid"]: x for x in json.load(open(os.path.join(c["arena"], "cards.json"), encoding="utf-8"))}
    testi = {e["id"]: e["text"] for e in json.load(open(os.path.join(c["arena"], "loc_en.json"), encoding="utf-8"))}
    attesa = {"grpid": 6873, "titleId": 2929, "artId": 1837, "set": "MIR", "collectorNumber": "210", "cardTypeTextId": 8, "artistCredit": "Steve White",
              "types": [2], "colorIdentity": [5], "colors": [5], "subtypes": [55], "subtypeTextId": 738, "rarity": 2, "castingcost": "o6oGoG", "cmc": 8,
              "power": "8", "toughness": "4", "abilities": [{"Id": 14, "TextId": 28}]}
    casi = [("il database del client: una carta come in mtgajson", carte.get(6873) == attesa),
            ("ibridi {2/X} a 2 (202.3f), la faccia secondaria, le facce collegate", carte.get(95700, {}).get("cmc") == 6
             and carte[95700].get("isSecondaryCard") is True and carte[95700].get("linkedFaces") == [95701, 95702]),
            ("i testi senza la formattazione", testi == {2929: "Crash of Rhinos", 3000: "Tre ibridi"}),
            ("il Player.log dice dove sta Arena", db_locale_finto(d, db)),
            ("Mac: il database si trova anche in una sottocartella della cartella dei dati", db_locale_mac(d, db))]
    nuovo = db_nuovo(c, db)
    os.utime(db, (time.time() + 60, time.time() + 60))           # Arena scarica un database nuovo
    casi.append(("negativa: lo stesso database non si riesporta, uno piu' nuovo si'", not nuovo and db_nuovo(c, db)))
    rotto = os.path.join(d, "Raw", "Raw_CardDatabase_rotto.mtga")
    sqlite3.connect(rotto).close()
    try:
        carte_da_db(rotto); rifiuta = False
    except sqlite3.Error:
        rifiuta = True
    casi.append(("negativa: un database senza la tabella Cards non scrive niente", rifiuta))
    return casi


def db_locale_mac(d, db):
    """Su Mac la cartella esatta del Raw_CardDatabase non e' nota: db_locale lo cerca sotto la cartella dei dati di Arena. La riga «Mono path» del Player.log
    del Mac (senza lettera di unita') si riconosce. Negativa: su Windows la ricerca nelle sottocartelle non si fa."""
    import re
    import shutil
    casa = os.path.join(d, "mac", "com.wizards.mtga", "Qualcosa", "Raw")
    os.makedirs(casa, exist_ok=True)
    shutil.copy2(db, casa)
    era = piattaforma.WINDOWS
    try:
        piattaforma.WINDOWS = False
        trovato = db_locale(os.path.join(d, "niente"), altre=[os.path.join(d, "mac", "com.wizards.mtga")])
        piattaforma.WINDOWS = True
        a_windows = db_locale(os.path.join(d, "niente"), altre=[os.path.join(d, "mac", "com.wizards.mtga")])
    finally:
        piattaforma.WINDOWS = era
    riga = "Mono path[0] = '/Applications/MTGA.app/Contents/Resources/Data/Managed'"
    m = re.search(r"Mono path\[0\] = '(/[^'\n]*?)/Managed'", riga)
    return (trovato is not None and os.path.basename(trovato) == os.path.basename(db) and a_windows is None
            and m is not None and m.group(1) == "/Applications/MTGA.app/Contents/Resources/Data")


def db_locale_finto(d, db):
    """db_locale trova il database dalla cartella che il Player.log nomina (finta: d/Raw sta in d/X/MTGA_Data/Downloads/Raw)."""
    import shutil
    casa = os.path.join(d, "X", "MTGA_Data", "Downloads", "Raw")
    os.makedirs(casa, exist_ok=True)
    shutil.copy2(db, casa)
    logd = os.path.join(d, "log")
    os.makedirs(logd, exist_ok=True)
    riga = "Mono path[0] = '" + os.path.join(d, "X", "MTGA_Data").replace(os.sep, "/") + "/Managed'"
    open(os.path.join(logd, "Player.log"), "w", encoding="utf-8").write(riga + chr(10))
    trovato = db_locale(logd, altre=[])
    return trovato is not None and os.path.basename(trovato) == os.path.basename(db) and db_locale(os.path.join(d, "niente"), altre=[]) is None


if __name__ == "__main__":
    if "--prova" in sys.argv:
        sys.exit(0 if prova() else 1)
    print(esegui())
