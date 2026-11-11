"""I tuoi mazzi come stanno su Arena, dal Player.log (Autore, 7 nov 2026: «la sezione deck non sta prendendo i deck dal mio log ma da untapped credo / infatti molti non corrispondono»).

Untapped conosce solo i mazzi giocati in partite che ha visto, e tiene anche quelli cancellati: il 7 nov 2026 dei suoi 39 mazzi di Ladder e Play ne esistevano ancora 6.
Arena invece scrive all'accesso (StartHook) l'elenco intero: DeckSummaries (nome, formato, ultima partita) e DecksInternal (le liste); poi ogni mazzo salvato (DeckUpsertDeckV3) e cancellato
(DeckDeleteDeck). Qui si rifa' lo stato in quell'ordine. L'ultimo stato buono resta in Log_Arena/mazzi_arena.json: all'avvio di Arena, prima dell'accesso, il Player.log non ha ancora l'elenco.
I mazzi che Arena ti ha dato (Autore, 7 nov 2026: «quelli di default forniti da arena») hanno la descrizione «Decks/Precon/...» e il nome vero (anche quello che gli hai dato tu):
escono col campo «precon» e vanno in Arena decks. Le liste col nome da tradurre («?=?Loc/Decks/Precon/...», 93 il 7 nov 2026: starter, World Championship, Gladiator, Brawl,
storie) hanno «IsNetDeck» e una cartella di Arena: sono modelli che Arena manda, non mazzi tuoi, e non escono. Il primo giro le metteva in Arena decks e lasciava i mazzi dati
fra i tuoi (Autore: «i mazzi in arena decks forniti di default dal gioco sono sbagliati»). Un modello che hai giocato esce, fra i mazzi dati, col nome inglese letto in sola
lettura dalle traduzioni di Arena (Raw_ClientLocalization_*.mtga, tabella Loc, colonna enUS), come gia' il database delle carte; copia in Log_Arena/nomi_precon.json.
Un profilo per ogni account di Arena (10 nov 2026, Magic 12): l'elenco che il Player.log scrive all'accesso e' dell'account appena entrato. Nell'app pubblica la
copia sta nella cartella del suo account (account.lega: Log_Arena/conti/<id>/mazzi_arena.json); se l'app mostra un altro account, l'elenco del log va nella copia
di chi l'ha scritto e si mostra la copia dell'account scelto; con All accounts le copie di tutti, unite. Nell'app di Autore Log_Arena/mazzi_arena.json, come prima.

    py -I -X utf8 Companion/App/Schede/Your_decks/mazzi_arena.py            l'elenco
    py -I -X utf8 Companion/App/Schede/Your_decks/mazzi_arena.py --prova    i casi su un log scritto apposta
"""
import os, sys
_casa = os.path.dirname(os.path.abspath(__file__))      # si sale fino a percorsi.py, che mette nel sys.path tutte le cartelle del Companion
while not os.path.isfile(os.path.join(_casa, "percorsi.py")):
    _casa = os.path.dirname(_casa)
if _casa not in sys.path:
    sys.path.insert(0, _casa)
import percorsi  # noqa: E402
import datetime
import json
import re

QUI = os.path.dirname(os.path.abspath(__file__))
RADICE = percorsi.ROOT
LOG = os.path.expandvars(r"%USERPROFILE%\AppData\LocalLow\Wizards Of The Coast\MTGA\Player.log")
import account as _ACC  # noqa: E402
CACHE = _ACC.lega(globals(), "CACHE", "mazzi_arena.json")       # Log_Arena/mazzi_arena.json, nell'app pubblica nella cartella dell'account
F_CARTE = os.path.join(RADICE, "Dati", "untapped", "arena_cards", "cards.json")
F_LOC = os.path.join(RADICE, "Dati", "untapped", "arena_cards", "loc_en.json")
COLORI = {1: "W", 2: "U", 3: "B", 4: "R", 5: "G"}
NOMI_PRECON = os.path.join(RADICE, "Log_Arena", "nomi_precon.json")
_T = {}
_NOMI = {}


def nomi_precon():
    """{chiave «Decks/Precon/...»: nome inglese} dalle traduzioni di Arena (sola lettura), con la copia in Log_Arena."""
    if _NOMI:
        return _NOMI
    import glob
    import sqlite3
    cartelle = {r"C:\Program Files\Wizards of the Coast\MTGA\MTGA_Data", r"C:\Program Files (x86)\Steam\steamapps\common\MTGA\MTGA_Data",
                r"C:\Program Files\Epic Games\MagicTheGathering\MTGA_Data"}       # le installazioni standard; la cartella vera si legge dal Player.log (10 nov 2026:
    # prima c'era scritta quella di un disco del PC di Autore, che l'app pubblica non deve avere)
    try:
        with open(LOG, encoding="utf-8", errors="ignore") as f:
            for i, r in enumerate(f):
                m = re.search(r"([A-Za-z]:[\/][^\"'\n]*?MTGA_Data)", r)
                if m:
                    cartelle.add(m.group(1)); break
                if i > 2000:
                    break
    except OSError:
        pass
    for d in cartelle:
        f = sorted(glob.glob(os.path.join(d, "Downloads", "Raw", "Raw_ClientLocalization_*.mtga")), key=os.path.getmtime)
        if not f:
            continue
        try:
            c = sqlite3.connect("file:" + f[-1].replace("\\", "/") + "?mode=ro", uri=True)
            _NOMI.update({k: v for k, v in c.execute("select Key, enUS from Loc where Key like 'Decks/Precon/%'") if v})
            c.close()
        except sqlite3.Error:
            continue
        if _NOMI:
            try:
                with open(NOMI_PRECON + ".tmp", "w", encoding="utf-8") as g:
                    json.dump(_NOMI, g, ensure_ascii=False)
                os.replace(NOMI_PRECON + ".tmp", NOMI_PRECON)
            except OSError:
                pass
            return _NOMI
    try:
        with open(NOMI_PRECON, encoding="utf-8") as g:
            _NOMI.update(json.load(g))
    except (OSError, ValueError):
        pass
    return _NOMI


def nome_precon(n):
    """«?=?Loc/Decks/Precon/2022_WC/Player_GregO» -> «WC 2022 · Greg Orange»; senza traduzione l'ultimo pezzo della chiave."""
    k = n[len("?=?Loc/"):] if n.startswith("?=?Loc/") else n
    nome = nomi_precon().get(k) or k.rsplit("/", 1)[-1].replace("_", " ")
    wc = re.search(r"/(\d{4})_WC/", k)
    return f"WC {wc.group(1)} · {nome}" if wc else nome


def tabella():
    """{grpId: (nome, colori, terra)} dal database delle carte di Arena, letto una volta."""
    if not _T:
        import db_carte         # il database di Arena letto una volta per processo, ridotto e cotto (11 nov 2026)
        loc = db_carte.testi()
        for c in db_carte.carte():
            _T[c["grpid"]] = (loc.get(c.get("titleId")) or str(c["grpid"]), "".join(k for i, k in COLORI.items() if i in (c.get("colors") or [])), "Land" in (loc.get(c.get("cardTypeTextId")) or ""))
    return _T


def nome_pulito(n):
    """Il nome come lo mostra Arena: i mazzi importati da un sito si portano dietro righe vuote e la descrizione. I mazzi di base hanno il nome da tradurre: si tiene l'ultimo pezzo."""
    n = n or ""
    if n.startswith("?=?Loc"):
        return nome_precon(n)
    return next((r.strip() for r in re.split(r"[\r\n]+", n) if r.strip()), "")


def data(attr, chiave):
    v = (attr.get(chiave) or "").strip('"')
    if not v or v.startswith("0001"):
        return None
    try:
        return datetime.datetime.fromisoformat(re.sub(r"(\.\d{6})\d+", r"\1", v).replace("Z", "+00:00")).replace(tzinfo=None).isoformat(timespec="seconds")
    except ValueError:
        return None


def voce(s):
    """Dal riassunto di Arena (DeckSummaries o Summary del salvataggio)."""
    a = {x["name"]: x["value"] for x in s.get("Attributes") or []}
    return dict(nome=s.get("Name") or "", formato=(a.get("Format") or "").strip('"'), ultima=data(a, "LastPlayed"), aggiornato=data(a, "LastUpdated"), precon=(s.get("Name") or "").startswith("?=?Loc"),
                dato=(s.get("Description") or "").startswith("Decks/Precon/"), netdeck=bool(s.get("IsNetDeck")), cartella=s.get("NetDeckFolderIdInternal"),
                chiave=chiave_precon(s))


def chiave_precon(s):
    """«Precon_EPPFDN_UG» per un mazzo dato (dalla descrizione «Decks/Precon/Precon_EPPFDN_UG_desc») e per il suo modello (dal nome «?=?Loc/Decks/Precon/Precon_EPPFDN_UG»)."""
    for t in (s.get("Description") or "", s.get("Name") or ""):
        m = re.search(r"Decks/Precon/(.+?)(?:_desc)?$", t)
        if m:
            return m.group(1)
    return None


RX_ACCESSO = re.compile(r'"authenticateResponse": \{ "clientId": "([A-Z0-9]+)"')


def elenchi(testo):
    """-> ([(posizione, account)] degli elenchi dei mazzi del log, [(posizione, account, "")] degli accessi). L'elenco e' dell'ultimo accesso prima di lui."""
    acc = [(m.start(), m.group(1), "") for m in RX_ACCESSO.finditer(testo)]
    return [(m.start(), _ACC.conto_a(acc, m.start())) for m in re.finditer('"DeckSummaries"', testo)], acc


def stato_da(testo, conto=None):
    """Il testo di un log -> {id: dict(voce, carte={MainDeck: [...], ...})}, None se non c'e' l'elenco dell'accesso. conto: l'ultimo elenco di quell'account, coi
    salvataggi fino all'accesso dopo (10 nov 2026, Magic 12); None: l'ultimo elenco del log, coi salvataggi fino in fondo, come prima."""
    limite = len(testo)
    if conto is None:
        i = testo.rfind('"DeckSummaries"')
    else:
        el, acc = elenchi(testo)
        mie = [p for p, c in el if c == conto]
        i = mie[-1] if mie else -1
        limite = next((p for p, _c, _n in acc if p > i), len(testo))
    if i < 0:
        return None
    ini = testo.rfind("\n", 0, i) + 1
    fine = testo.find("\n", i)
    riga = testo[ini:fine if fine > 0 else len(testo)]
    try:
        d = json.loads(riga[riga.index("{"):])
    except ValueError:
        return None
    interni = d.get("DecksInternal") or {}
    mazzi = {}
    for s in d.get("DeckSummaries") or []:
        k = s.get("DeckIdInternal")
        if k:
            mazzi[k] = dict(voce(s), id=k, carte=interni.get(k) or {})
    for m in re.finditer(r"==> (DeckUpsertDeckV\d+|DeckDeleteDeck) (\{[^\r\n]*)", testo[fine if fine > 0 else len(testo):limite]):
        try:
            q = json.loads(json.loads(m.group(2))["request"])
        except (ValueError, KeyError):
            continue
        if m.group(1) == "DeckDeleteDeck":
            mazzi.pop(q.get("DeckId"), None)
            continue
        s = q.get("Summary") or {}
        k = s.get("DeckId")
        if k:
            prima = mazzi.get(k) or {}
            v = voce(s)
            v["dato"] = v["dato"] or bool(prima.get("dato"))       # il salvataggio puo' non riportare la descrizione: un mazzo dato resta dato
            mazzi[k] = dict(v, id=k, carte=q.get("Deck") or prima.get("carte") or {})
    return mazzi


def per_account(log):
    """L'app pubblica: ogni elenco dei mazzi dei log vivi (Player-prev.log, poi Player.log) va nella copia del suo account; -> l'elenco dell'account mostrato
    (None se i log non ne hanno uno: vale la sua copia). Con All accounts None: si leggono le copie unite."""
    mostrato, trovati = _ACC.attivo(), {}
    for f in ([os.path.join(os.path.dirname(log), "Player-prev.log")] if os.path.basename(log) == "Player.log" else []) + [log]:
        try:
            with open(f, "rb") as h:
                testo = h.read().decode("utf-8", "ignore")
        except OSError:
            continue
        for c in {c for _p, c in elenchi(testo)[0] if c}:
            g = stato_da(testo, c)
            if g is not None:
                trovati[c] = g          # il Player.log viene dopo: vince sul Player-prev.log
    for c, g in trovati.items():
        if c == mostrato:
            continue
        proprio = _ACC.percorso("mazzi_arena.json", i=c)
        completa(g, proprio)
        os.makedirs(os.path.dirname(proprio), exist_ok=True)
        with open(proprio + ".tmp", "w", encoding="utf-8") as h:
            json.dump(g, h, ensure_ascii=False)
        os.replace(proprio + ".tmp", proprio)
    if mostrato is None:
        _ACC.unisci()
    return trovati.get(mostrato) if mostrato else None


def lista(voci, T):
    out = {}
    for x in voci or []:
        n = T.get(x.get("cardId"), (str(x.get("cardId")),))[0]
        out[n] = out.get(n, 0) + int(x.get("quantity") or 1)
    return out


def colori_di(voci, T):
    trovati = set()
    for x in voci or []:
        t = T.get(x.get("cardId"))
        if t and not t[2]:
            trovati |= set(t[1])
    return "".join(k for k in "WUBRG" if k in trovati)


def completa(grezzi, cache, archivio=None):
    """Le liste che il log non ha. Quando la copia dei mazzi sul PC e' gia' aggiornata (stesso DecksCacheVersion), Arena all'accesso scrive l'elenco dei mazzi con
    DecksInternal vuoto: le liste stanno nel client. Visto il 7 nov 2026 alle 15:40 (117 mazzi, 0 liste): la copia era stata riscritta vuota e Your decks era senza
    copertine e colori. Una lista che manca si prende dalla copia di prima e, se non c'e' nemmeno li', dall'ultimo log archiviato che ce l'ha (Log_Arena/*.log)."""
    mancano = {k for k, v in grezzi.items() if not v.get("carte")}
    if not mancano:
        return
    try:
        prima = json.load(open(cache, encoding="utf-8"))
    except (OSError, ValueError):
        prima = {}
    for k in list(mancano):
        if (prima.get(k) or {}).get("carte"):
            grezzi[k]["carte"] = prima[k]["carte"]
            mancano.discard(k)
    if not mancano:
        return
    import glob
    cartella = archivio or os.path.join(RADICE, "Log_Arena")
    for f in sorted(glob.glob(os.path.join(cartella, "*.log")), key=os.path.getmtime, reverse=True)[:40]:
        try:
            with open(f, "rb") as h:
                vecchi = stato_da(h.read().decode("utf-8", "ignore")) or {}
        except OSError:
            continue
        for k in list(mancano):
            if (vecchi.get(k) or {}).get("carte"):
                grezzi[k]["carte"] = vecchi[k]["carte"]
                mancano.discard(k)
        if not mancano:
            return
    da_partite(grezzi, mancano)


def da_partite(grezzi, mancano, partite=None):
    """L'ultimo ripiego (10 nov 2026, l'app pubblica: chi la installa non ha ne' la copia ne' i log archiviati): la lista dell'ultima partita giocata con quel
    mazzo, dal deckMessage del log (partite_log.py: carte, side, cmd in grpId). Un mazzo mai giocato resta senza lista finche' Arena non la scrive."""
    if partite is None:
        try:
            import partite_log
            partite, _n = partite_log.partite()
        except (OSError, ValueError):
            return
    ultima = {}
    for p in partite:
        if p.get("mazzo") in mancano and p.get("carte"):
            ultima[p["mazzo"]] = p
    voci = lambda grp: [dict(cardId=g, quantity=q) for g, q in sorted({g: grp.count(g) for g in grp}.items())]
    for k, p in ultima.items():
        grezzi[k]["carte"] = dict(MainDeck=voci(p["carte"]), Sideboard=voci(p.get("side") or []), CommandZone=voci(p.get("cmd") or []))
        mancano.discard(k)


def mazzi(log=None, cache=False):
    """-> [dict(id, nome, formato, ultima, aggiornato, colori, main, side, comandante, compagno, precon, chiave)]; None se non si sa niente.
    chiave: «Precon_EPPFDN_BW» per un mazzo di Arena (dato o modello): la copia che i Dual Color Precons fanno giocare ha la stessa chiave (9 nov 2026).
    precon: il mazzo te l'ha dato Arena (Arena decks). I modelli di Arena mai giocati non escono. cache: la copia (False: quella dell'account mostrato; None:
    nessuna)."""
    log = log or LOG
    if cache is False:
        cache = CACHE
    grezzi = None
    if _ACC.PUBBLICA and cache:
        grezzi = per_account(log)
    else:
        try:
            with open(log, "rb") as f:
                grezzi = stato_da(f.read().decode("utf-8", "ignore"))
        except OSError:
            pass
    if grezzi is None:
        try:
            grezzi = json.load(open(cache, encoding="utf-8"))
        except (OSError, ValueError):
            return None
    elif cache:
        completa(grezzi, cache)
        os.makedirs(os.path.dirname(cache), exist_ok=True)
        tmp = cache + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(grezzi, f, ensure_ascii=False)
        os.replace(tmp, cache)
    T = tabella()
    # i modelli della stessa cartella dei mazzi che Arena ti ha dato (Autore, 7 nov 2026: «dai deck di arena vedo che manca orzov»): dei 10 mazzi base di Foundations
    # ne avevi 8, e Orzhov e Izzet stavano solo fra i modelli. Escono i modelli delle cartelle dei tuoi mazzi dati, tranne quelli che hai gia' (stessa chiave)
    dati = {m.get("chiave") for m in grezzi.values() if m.get("dato") and m.get("chiave")}
    cartelle = {m.get("cartella") for m in grezzi.values() if m.get("netdeck") and m.get("chiave") in dati and m.get("cartella")}
    formato_dati = next((m["formato"] for m in grezzi.values() if m.get("dato")), None)
    out = []
    for m in grezzi.values():
        modello = m.get("netdeck", m["precon"])      # una copia vecchia senza «netdeck»: vale il nome da tradurre
        sorella = modello and m.get("cartella") in cartelle and m.get("chiave") not in dati
        if modello and not m["ultima"] and not sorella:
            continue
        if sorella and formato_dati:
            m = dict(m, formato=formato_dati)       # il modello dice Alchemy; i tuoi mazzi della stessa cartella dicono il formato in cui li giochi
        c = m["carte"]
        principali = (c.get("MainDeck") or []) + (c.get("CommandZone") or [])
        out.append(dict(id=m["id"], nome=nome_pulito(m["nome"]) or "Unnamed", formato=m["formato"], ultima=m["ultima"], aggiornato=m["aggiornato"], colori=colori_di(principali, T), precon=bool(m.get("dato")) or modello, chiave=m.get("chiave"),
                        main=lista(c.get("MainDeck"), T), side=lista(c.get("Sideboard"), T), comandante=lista(c.get("CommandZone"), T), compagno=lista(c.get("Companions"), T)))
    return out


def prova():
    import tempfile
    def salvataggio(k, nome, carte):
        return "==> DeckUpsertDeckV3 " + json.dumps({"id": "x", "request": json.dumps({"Summary": {"DeckId": k, "Name": nome, "Attributes": [{"name": "Format", "value": "Standard"}]}, "Deck": carte})})
    def via(k):
        return "==> DeckDeleteDeck " + json.dumps({"id": "x", "request": json.dumps({"DeckId": k})})
    a = {"name": "LastPlayed", "value": '"2026-11-05T03:13:49.2668661+01:00"'}
    b = {"name": "LastPlayed", "value": '"0001-01-01T00:00:00"'}
    un = {"MainDeck": [{"cardId": 1, "quantity": 2}]}
    hook = json.dumps({"InventoryInfo": {}, "DeckSummaries": [{"DeckIdInternal": "A", "Name": "UW Bouncer", "Attributes": [a]}, {"DeckIdInternal": "B", "Name": "Via", "Attributes": [b]},
                                                               {"DeckIdInternal": "C", "Name": "?=?Loc/Decks/Precon/Precon_X", "Attributes": [b], "IsNetDeck": True}, {"DeckIdInternal": "D", "Name": "?=?Loc/Decks/Precon/Precon_Y", "Attributes": [a], "IsNetDeck": True},
                                                               {"DeckIdInternal": "G", "Name": "Learn from the Land", "Attributes": [b], "Description": "Decks/Precon/Precon_EPPFDN_UG_desc"},
                                                               {"DeckIdInternal": "E", "Name": "\r\nDIMIR DECEIT\r\ndescrizione", "Attributes": [b]}],
                       "DecksInternal": {"A": un, "B": un, "C": un, "D": un, "E": un, "G": un}})
    testo = "\n".join(["prima", hook, via("B"), salvataggio("F", "Nuovo", {"MainDeck": [{"cardId": 2, "quantity": 4}]}), salvataggio("A", "UW Bouncer 2", {"MainDeck": [{"cardId": 2, "quantity": 1}]}),
                       salvataggio("G", "Il mio Learn", {"MainDeck": [{"cardId": 2, "quantity": 2}]})])
    _T.update({1: ("Plains", "", True), 2: ("Unsummon", "U", False)})
    with tempfile.TemporaryDirectory() as td:
        f, c = os.path.join(td, "p.log"), os.path.join(td, "c.json")
        open(f, "w", encoding="utf-8", newline="").write(testo)
        r = {m["id"]: m for m in mazzi(f, c)}
        open(f, "w", encoding="utf-8").write("appena partito")
        dopo = mazzi(f, c)
        vuoto = mazzi(f, os.path.join(td, "manca.json"))
    casi = [("un mazzo cancellato sparisce", "B" not in r), ("un mazzo nuovo c'e'", r.get("F", {}).get("main") == {"Unsummon": 4}),
            ("un mazzo salvato ha la lista nuova", r.get("A", {}).get("main") == {"Unsummon": 1} and r["A"]["nome"] == "UW Bouncer 2"),
            ("mai giocati i mazzi di base non si vedono", "C" not in r), ("giocati si'", "D" in r and r["D"]["nome"] == "Precon Y"),
            ("un mazzo che Arena ti ha dato va in Arena decks, anche mai giocato", r.get("G", {}).get("precon") is True),
            ("rinominato e salvato resta dato", r.get("G", {}).get("nome") == "Il mio Learn" and r["G"]["precon"]),
            ("i tuoi mazzi non sono dati (prova negativa)", r["A"]["precon"] is False and r["E"]["precon"] is False),
            ("il nome senza righe vuote ne' descrizione", r.get("E", {}).get("nome") == "DIMIR DECEIT"), ("i colori non contano le terre", r["A"]["colori"] == "U" and r["E"]["colori"] == ""),
            ("senza elenco nel log vale la copia", dopo is not None and len(dopo) == len(r)), ("senza niente: None", vuoto is None)]
    # Arena con la copia gia' aggiornata: l'elenco senza liste. Le liste vengono dalla copia o da un log archiviato
    vuoto = json.dumps({"DeckSummaries": [{"DeckIdInternal": "A", "Name": "UW Bouncer", "Attributes": [a]}, {"DeckIdInternal": "H", "Name": "Solo archivio", "Attributes": [a]}], "DecksInternal": {}})
    pieno = json.dumps({"DeckSummaries": [{"DeckIdInternal": "H", "Name": "Solo archivio", "Attributes": [a]}], "DecksInternal": {"H": {"MainDeck": [{"cardId": 2, "quantity": 3}]}}})
    with tempfile.TemporaryDirectory() as td:
        f, c, arch = os.path.join(td, "p.log"), os.path.join(td, "c.json"), os.path.join(td, "arch")
        os.makedirs(arch)
        open(os.path.join(arch, "vecchio.log"), "w", encoding="utf-8").write("x\n" + pieno + "\n")
        json.dump({"A": dict(nome="UW Bouncer", formato="Standard", ultima=None, aggiornato=None, precon=False, id="A", carte={"MainDeck": [{"cardId": 2, "quantity": 2}]})}, open(c, "w", encoding="utf-8"))
        open(f, "w", encoding="utf-8").write("x\n" + vuoto + "\n")
        g = stato_da(open(f, encoding="utf-8").read())
        completa(g, c, arch)
        casi += [("log senza liste: la lista dalla copia", g["A"]["carte"] == {"MainDeck": [{"cardId": 2, "quantity": 2}]}),
                 ("e se la copia non ce l'ha, dal log archiviato", g["H"]["carte"] == {"MainDeck": [{"cardId": 2, "quantity": 3}]})]
        g2 = stato_da(open(f, encoding="utf-8").read())
        casi.append(("senza copia ne' archivio resta vuota (prova negativa)", (completa(g2, os.path.join(td, "manca.json"), os.path.join(td, "niente")) or True) and not g2["A"]["carte"]))
        g3 = {"A": dict(carte={}), "Z": dict(carte={})}
        pp_ = [dict(mazzo="A", carte=[5, 5, 6], side=[7], cmd=[]), dict(mazzo="A", carte=[5, 6, 6, 6], side=[], cmd=[]), dict(mazzo="Y", carte=[9])]
        da_partite(g3, {"A", "Z"}, pp_)
        casi.append(("senza copia ne' archivio: la lista dell'ultima partita giocata col mazzo (l'app pubblica)",
                     g3["A"]["carte"]["MainDeck"] == [{"cardId": 5, "quantity": 1}, {"cardId": 6, "quantity": 3}] and not g3["Z"]["carte"]))
    # i modelli della cartella dei mazzi dati: escono quelli che non hai, non i doppioni
    hook3 = json.dumps({"DeckSummaries": [{"DeckIdInternal": "G", "Name": "Learn from the Land", "Attributes": [b, {"name": "Format", "value": "Standard"}], "Description": "Decks/Precon/Precon_EPPFDN_UG_desc"},
                                          {"DeckIdInternal": "N1", "Name": "?=?Loc/Decks/Precon/Precon_EPPFDN_UG", "Attributes": [{"name": "Format", "value": "Alchemy"}], "IsNetDeck": True, "NetDeckFolderIdInternal": "F"},
                                          {"DeckIdInternal": "N2", "Name": "?=?Loc/Decks/Precon/Precon_EPPFDN_BW", "Attributes": [{"name": "Format", "value": "Alchemy"}], "IsNetDeck": True, "NetDeckFolderIdInternal": "F"},
                                          {"DeckIdInternal": "N3", "Name": "?=?Loc/Decks/Precon/Player_X", "Attributes": [], "IsNetDeck": True, "NetDeckFolderIdInternal": "ALTRA"}],
                        "DecksInternal": {k: un for k in ("G", "N1", "N2", "N3")}})
    with tempfile.TemporaryDirectory() as td:
        f = os.path.join(td, "p.log")
        open(f, "w", encoding="utf-8").write("x\n" + hook3 + "\n")
        r3 = {m["id"]: m for m in mazzi(f, None)}
    casi += [("il modello che non hai della cartella dei tuoi mazzi dati esce, col formato dei tuoi", "N2" in r3 and r3["N2"]["precon"] and r3["N2"]["formato"] == "Standard"),
             ("il modello che hai gia' no (prova negativa)", "N1" not in r3), ("i modelli di altre cartelle no", "N3" not in r3)]
    casi += prova_conti()
    _T.clear()
    for n, v in casi:
        print(("  ok   " if v else "  ROSSO ") + n)
    print(f"{sum(1 for _, v in casi if v)}/{len(casi)}")
    return 0 if all(v for _, v in casi) else 1


def prova_conti():
    """Due account (10 nov 2026, Magic 12): l'elenco del log va nella copia di chi l'ha scritto; l'altro account vede i suoi mazzi, All accounts tutti e due."""
    import tempfile
    A, B = "AAAA1111BBBB2222CCCC3333DD", "ZZZZ1111BBBB2222CCCC3333DD"
    acc = lambda i: '{ "authenticateResponse": { "clientId": "%s", "sessionId": "s", "screenName":"X" } }' % i
    elenco = lambda k, n: json.dumps({"DeckSummaries": [{"DeckIdInternal": k, "Name": n, "Attributes": []}], "DecksInternal": {k: {"MainDeck": [{"cardId": 2, "quantity": 4}]}}})
    vero = (_ACC.PUBBLICA, _ACC.FILE[0], _ACC.CONTI[0], list(_ACC.VIVI), list(_ACC._LEGATI), globals()["CACHE"], _ACC.LOGDIR)
    casi = []
    with tempfile.TemporaryDirectory() as td:
        f = os.path.join(td, "Player.log")
        try:
            _ACC.PUBBLICA, _ACC.LOGDIR = True, td      # mai la Log_Arena vera
            _ACC.FILE[0], _ACC.CONTI[0], _ACC.VIVI[:] = os.path.join(td, "utente.json"), os.path.join(td, "conti"), [f]
            _ACC._LEGATI[:] = [(globals(), "CACHE", "mazzi_arena.json", None)]
            _ACC._C.clear(); _ACC._L.clear()
            open(f, "w", encoding="utf-8").write("\n".join([acc(A), elenco("DA", "Mazzo di A")]) + "\n")
            _ACC.aggiorna(); _ACC.applica()
            ra = {m["nome"] for m in mazzi(f) or []}
            open(f, "w", encoding="utf-8").write("\n".join([acc(B), elenco("DB", "Mazzo di B")]) + "\n")
            _ACC.aggiorna(); _ACC.applica()
            rb = {m["nome"] for m in mazzi(f) or []}
            _ACC.scegli(A)
            ra2 = {m["nome"] for m in mazzi(f) or []}
            _ACC.scegli(_ACC.TUTTI)
            rt = {m["nome"] for m in mazzi(f) or []}
            _ACC.PUBBLICA = False       # il codice di prima: una copia sola per tutti
            json.dump(dict(DA=dict(nome="Mazzo di A", formato="Standard", ultima=None, aggiornato=None, precon=False, id="DA", carte={})), open(os.path.join(td, "unica.json"), "w"))
            unica = {m["nome"] for m in mazzi(f, os.path.join(td, "unica.json")) or []}
            casi += [("due account: ognuno i suoi mazzi", ra == {"Mazzo di A"} and rb == {"Mazzo di B"}),
                     ("scelto A col log di B: i mazzi di A, dalla sua copia", ra2 == {"Mazzo di A"}),
                     ("All accounts: tutti e due", rt == {"Mazzo di A", "Mazzo di B"}),
                     ("negativa: senza profili (una copia sola) il log di B cancella i mazzi di A", unica == {"Mazzo di B"})]
        finally:
            _ACC.PUBBLICA, _ACC.FILE[0], _ACC.CONTI[0] = vero[0], vero[1], vero[2]
            _ACC.VIVI[:], _ACC._LEGATI[:] = vero[3], vero[4]
            globals()["CACHE"] = vero[5]
            _ACC.LOGDIR = vero[6]
            _ACC._C.clear(); _ACC._L.clear()
    return casi


if __name__ == "__main__":
    if "--prova" in sys.argv:
        sys.exit(prova())
    m = mazzi(cache=None) or []      # l'elenco del Player.log, senza copia
    print(len(m), "mazzi")
    for x in sorted(m, key=lambda z: z["ultima"] or "", reverse=True)[:25]:
        print(f"  {(x['ultima'] or '-')[:10]:<11}{x['formato']:<20}{x['colori']:<6}{sum(x['main'].values()):>3}  {x['nome']}")
