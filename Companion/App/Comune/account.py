"""Chi usa l'app: l'account di Arena e, se c'e', il profilo di Untapped (10 nov 2026, Autore: «far scaricare l'app al pubblico»).

Due modi:
- l'app di Autore (la cartella del progetto): i suoi id, come sempre (CLAUDE.md), e i file di Log_Arena dove sono sempre stati;
- l'app pubblica (la cartella ha il file PUBBLICA.txt, la scrive Distribuzione/costruisci.py): l'account di Arena si legge dal Player.log di chi la usa
  (authenticateResponse: clientId e screenName, scritti a ogni accesso); il profilo di Untapped e' facoltativo: chi lo vuole incolla il link del suo profilo
  pubblico (serve solo alla collezione completa, alle partite limited e alla colonna social). Senza, quelle parti restano vuote.

Un profilo per ogni account di Arena (10 nov 2026, sessione Magic 12): chi cambia account su Arena (o due persone sullo stesso PC) non deve vedere le partite e
i mazzi dell'altro mischiati ai suoi. Nell'app pubblica:
- ogni accesso scritto nei log segna di chi sono le righe che seguono, fino al prossimo accesso (accessi, conto_a): le partite, i premi e le foto del conto si
  attribuiscono cosi' (partite_log, premi_eventi, risorse), e le loro copie su disco tengono l'account di ogni voce;
- i file fatti dall'utente o per lui (wishlist e Deck building, Board, reti delle sinergie, copia dei mazzi di Arena, collezione e partite di Untapped) stanno in
  Log_Arena/conti/<id>/ (percorso, lega); quelli che c'erano prima in Log_Arena vanno all'account che li aveva (migra);
- Log_Arena/utente.json tiene gli account visti («conti»: nome, link di Untapped, consenso alla condivisione), l'ultimo entrato in Arena («ultimo») e la scelta
  della tendina in alto («scelta»: «auto» = segui Arena, un id, o «*» = All accounts). La scelta resta per questo PC; un accesso ad Arena con un altro account la
  riporta su «auto», cioe' sull'account appena entrato (aggiorna);
- All accounts: le partite, i premi e le risorse sommano tutti gli account; i file fatti a mano si uniscono in Log_Arena/conti/_tutti/ (unisci), in sola lettura
  (sola_lettura: wishlist e Deck building non si cambiano).

    py -I -X utf8 Companion/App/Comune/account.py --prova
"""
import os, sys
_casa = os.path.dirname(os.path.abspath(__file__))      # si sale fino a percorsi.py, che mette nel sys.path tutte le cartelle del Companion
while not os.path.isfile(os.path.join(_casa, "percorsi.py")):
    _casa = os.path.dirname(_casa)
if _casa not in sys.path:
    sys.path.insert(0, _casa)
import percorsi  # noqa: E402
import piattaforma  # noqa: E402  (i percorsi di Arena su Windows e su Mac)
import json  # noqa: E402
import re  # noqa: E402
import shutil  # noqa: E402
import threading  # noqa: E402

ROOT = percorsi.ROOT
PUBBLICA = os.path.exists(os.path.join(ROOT, "PUBBLICA.txt"))
# l'aspetto dell'app pubblica anche nell'app di Autore (11 nov 2026, Autore: «devo sempre avere tutte le funzioni sbloccate ma vedere l'app con tutto
# cio' che l'utente scarica e utilizza»): quello che si vede (la riga dell'artista sulle copertine, Your collection e Data sharing, in Settings dal 13 nov 2026) e' lo stesso,
# tranne le carte che non hai, che restano opache (stesso giorno: «si le voglio opache»); le funzioni e i dati in piu' (Drafter, Untapped, meta completo) restano sbloccati. MIO_ASPETTO=1 torna a quello di prima
ASPETTO_PUBBLICO = PUBBLICA or os.environ.get("MIO_ASPETTO") != "1"
LOGDIR = os.path.join(ROOT, "Log_Arena")
FILE = [os.path.join(LOGDIR, "utente.json")]
CONTI = [os.path.join(LOGDIR, "conti")]
ARENA = piattaforma.cartella_arena()
VIVI = [os.path.join(ARENA, "Player.log"), os.path.join(ARENA, "Player-prev.log")]
AUTORE = dict(id=None, nome=None, untapped_user=None, untapped_player=None)      # l'app pubblica: mai usato (PUBBLICA)
RX_AUTH = re.compile(rb'"authenticateResponse": \{ "clientId": "([A-Z0-9]+)"[^}]*?"screenName":"([^"]+)"')
RX_LINK = re.compile(r"profile/([0-9a-f-]{36})/([A-Z0-9]{20,32})")
AUTO, TUTTI = "auto", "*"
CAMPI = ("nome", "untapped_user", "untapped_player")
_C = {}             # utente.json letto (si svuota a ogni salvataggio)
_L = {}             # l'ultimo accesso nei log vivi, per versione dei file
_LEGATI = []        # (globals del modulo, variabile, nome del file, percorso nell'app di Autore)
_RICHIAMI = []      # le funzioni da chiamare quando cambia l'account (al_cambio): il nome in gioco, il profilo di Untapped
_LOCK = threading.RLock()


# ------------------------------------------------------------------ gli accessi nei log
def accessi(data):
    """Gli accessi scritti in un log (bytes): [(posizione, id, nome)], in ordine."""
    return [(m.start(), m.group(1).decode(), m.group(2).decode("utf-8", "replace")) for m in RX_AUTH.finditer(data)]


def conto_a(acc, pos):
    """L'account delle righe alla posizione pos: l'ultimo accesso prima di pos. Prima del primo accesso del file vale il primo (all'avvio Arena scrive qualche
    riga prima di entrare), senza accessi None."""
    chi = None
    for p, i, _n in acc:
        if p > pos:
            break
        chi = i
    return chi or (acc[0][1] if acc else None)


def dal_log(files=None):
    """(id, nome) dall'ultimo accesso scritto nei log di Arena, o (None, None)."""
    for f in files or VIVI:
        try:
            with open(f, "rb") as fh:
                data = fh.read()
        except OSError:
            continue
        m = None
        for m in RX_AUTH.finditer(data):
            pass
        if m:
            return m.group(1).decode(), m.group(2).decode("utf-8", "replace")
    return None, None


def _ultimo():
    """L'ultimo accesso nei log vivi, riletto solo quando un log cambia."""
    firma = []
    for f in VIVI:
        try:
            st = os.stat(f); firma.append((f, st.st_size, st.st_mtime))
        except OSError:
            firma.append((f, None))
    if _L.get("firma") != firma:
        _L.update(firma=firma, chi=dal_log(VIVI))
    return _L["chi"]


# ------------------------------------------------------------------ utente.json
def leggi():
    """utente.json, con gli account in «conti». Il file di prima (un account solo: id, nome, link di Untapped, consenso) diventa il primo account."""
    with _LOCK:
        if "d" in _C:
            return json.loads(json.dumps(_C["d"]))
        try:
            with open(FILE[0], encoding="utf-8") as f:
                d = json.load(f)
            d = d if isinstance(d, dict) else {}
        except (OSError, ValueError):
            d = {}
        if "conti" not in d:
            vecchio = {k: d.pop(k) for k in ("id",) + CAMPI if k in d}
            d["conti"] = {}
            if vecchio.get("id"):
                d["conti"][vecchio["id"]] = {k: vecchio.get(k) for k in CAMPI}
                d["ultimo"] = vecchio["id"]
                if "condividi" in d:
                    d["conti"][vecchio["id"]]["condividi"] = d.pop("condividi")
        d.setdefault("scelta", AUTO)
        _C["d"] = d
        return json.loads(json.dumps(d))


def salva(d):
    with _LOCK:
        os.makedirs(os.path.dirname(FILE[0]), exist_ok=True)
        tmp = FILE[0] + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=1)
        os.replace(tmp, FILE[0])
        _C.clear()


def aggiorna():
    """Guarda l'ultimo accesso ad Arena: un account nuovo entra in «conti»; se e' un altro account rispetto all'ultimo, la scelta torna «auto» e l'app passa a
    lui da sola. -> True se l'account mostrato e' cambiato."""
    if not PUBBLICA:
        return False
    with _LOCK:
        d = leggi()
        prima = _attivo(d)
        i, n = _ultimo()
        if i:
            c = d["conti"].setdefault(i, {})
            nuovo = c.get("nome") != n or i != d.get("ultimo")
            c["nome"] = n
            if i != d.get("ultimo"):
                if d.get("ultimo"):
                    d["scelta"] = AUTO       # un accesso con un altro account: si segue Arena
                d["ultimo"] = i
            if nuovo:
                try:
                    salva(d)
                except OSError:
                    _C["d"] = d
        _C["pronto"] = True
        return _attivo(d) != prima


def registra(visti):
    """Gli account trovati nei log archiviati [(id, nome)]: entrano nella tendina anche se oggi nessuno li usa. Non cambiano l'account scelto."""
    if not PUBBLICA:
        return
    with _LOCK:
        d = leggi()
        cambiato = False
        for i, n in visti:
            if i and i not in d["conti"]:
                d["conti"][i] = dict(nome=n); cambiato = True
            elif i and n and not d["conti"][i].get("nome"):
                d["conti"][i]["nome"] = n; cambiato = True
        if cambiato:
            try:
                salva(d)
            except OSError:
                pass


def _pronto():
    if PUBBLICA and not _C.get("pronto"):
        aggiorna()


def _attivo(d):
    s = d.get("scelta") or AUTO
    if s == TUTTI:
        return None
    if s != AUTO and s in d["conti"]:
        return s
    return d.get("ultimo")


# ------------------------------------------------------------------ la scelta
def conti():
    """[(id, nome)]: l'ultimo entrato in Arena per primo, poi per nome. Nell'app di Autore solo il suo."""
    if not PUBBLICA:
        return [(AUTORE["id"], AUTORE["nome"])]
    _pronto()
    d = leggi()
    u = d.get("ultimo")
    return sorted(((i, c.get("nome") or i[:6]) for i, c in d["conti"].items()), key=lambda x: (x[0] != u, x[1].lower()))


def scelta():
    """«auto», un id o «*»."""
    if not PUBBLICA:
        return AUTO
    _pronto()
    return leggi().get("scelta") or AUTO


def scegli(v):
    """La tendina: «auto», l'id di un account o «*» (All accounts). Rifa' i percorsi dei file."""
    if not PUBBLICA:
        return
    with _LOCK:
        d = leggi()
        d["scelta"] = v if v in (AUTO, TUTTI) or v in d["conti"] else AUTO
        salva(d)
    applica()


def attivo():
    """L'id dell'account che l'app mostra, None con All accounts. Nell'app di Autore il suo."""
    if not PUBBLICA:
        return AUTORE["id"]
    _pronto()
    return _attivo(leggi())


def tutti():
    return PUBBLICA and scelta() == TUTTI


def sola_lettura():
    """All accounts: wishlist e Deck building si guardano, non si cambiano."""
    return tutti()


def account():
    """dict(id, nome, untapped_user, untapped_player) dell'account mostrato (con All accounts, dell'ultimo entrato in Arena); i campi che non si sanno sono None."""
    if not PUBBLICA:
        return dict(AUTORE)
    _pronto()
    d = leggi()
    i = _attivo(d) or d.get("ultimo")
    c = d["conti"].get(i) or {}
    return dict(id=i, nome=c.get("nome"), untapped_user=c.get("untapped_user"), untapped_player=c.get("untapped_player"))


def collega_untapped(link):
    """Il link del profilo pubblico di Untapped (https://mtga.untapped.gg/profile/<utente>/<giocatore>) -> True se e' giusto; si salva sull'account mostrato."""
    m = RX_LINK.search(link or "")
    if not m:
        return False
    with _LOCK:
        d = leggi()
        i = (_attivo(d) or d.get("ultimo")) if PUBBLICA else AUTORE["id"]
        d["conti"].setdefault(i or "?", {}).update(untapped_user=m.group(1), untapped_player=m.group(2))
        salva(d)
    return True


# ------------------------------------------------------------------ i file di ogni account
def cartella(i=False):
    """La cartella dei file dell'account (i=False: quello mostrato; None: All accounts). Nell'app di Autore Log_Arena, come sempre."""
    if not PUBBLICA:
        return LOGDIR
    if i is False:
        i = attivo()
    return os.path.join(CONTI[0], "_tutti" if i is None else re.sub(r"[^A-Za-z0-9_-]", "_", i))


def percorso(nome, autore=None, i=False):
    """Il file «nome» dell'account. autore: dove sta nell'app di Autore, se non in Log_Arena."""
    if not PUBBLICA:
        return autore or os.path.join(LOGDIR, nome)
    return os.path.join(cartella(i), nome)


def lega(g, var, nome, autore=None):
    """Una variabile di un modulo (g = globals()) che e' il percorso di un file dell'account: si rifa' quando cambia l'account. -> il percorso di adesso."""
    _LEGATI.append((g, var, nome, autore))
    if PUBBLICA:
        migra([(g, var, nome, autore)])
    g[var] = percorso(nome, autore)
    return g[var]


def al_cambio(f):
    """f() si chiama a ogni cambio dell'account mostrato (applica): per i valori che un modulo tiene in memoria, come il profilo di Untapped."""
    if f not in _RICHIAMI:
        _RICHIAMI.append(f)


def unisci_json(a, b):
    """Due copie dello stesso file di due account: i dizionari si uniscono voce per voce, le liste si mettono in fila, il resto vince il secondo."""
    if isinstance(a, dict) and isinstance(b, dict):
        out = dict(a)
        for k, v in b.items():
            out[k] = unisci_json(out[k], v) if k in out else v
        return out
    if isinstance(a, list) and isinstance(b, list):
        return a + b
    return b


def unisci():
    """All accounts: i file legati di ogni account uniti in Log_Arena/conti/_tutti (si rifanno a ogni scelta di All accounts)."""
    nomi = {nome for _g, _v, nome, _f in _LEGATI}
    ids = [i for i, _n in conti()]
    dest = cartella(None)
    os.makedirs(dest, exist_ok=True)
    for nome in nomi:
        tot, c = None, 0
        for i in ids:
            try:
                with open(percorso(nome, i=i), encoding="utf-8") as f:
                    x = json.load(f)
            except (OSError, ValueError):
                continue
            tot = x if tot is None else unisci_json(tot, x); c += 1
        p = os.path.join(dest, nome)
        if tot is None:
            if os.path.exists(p):
                os.remove(p)
            continue
        with open(p + ".tmp", "w", encoding="utf-8") as f:
            json.dump(tot, f, ensure_ascii=False)
        os.replace(p + ".tmp", p)


def migra(legati=None):
    """I file di prima (Log_Arena/<nome>, o dove dice «autore», come Collezione/ per la collezione) si copiano all'account che c'era: l'ultimo entrato. Una
    volta per file («migrati»); se l'account ha gia' il suo, non si tocca. Si copia e non si sposta: il file vecchio resta dov'era (nessuno lo legge piu')."""
    if not PUBBLICA:
        return
    d = leggi()
    u = d.get("ultimo")
    fatti = d.get("migrati") if isinstance(d.get("migrati"), list) else []
    if not u:
        return
    nuovi = False
    for _g, _v, nome, fr in legati if legati is not None else _LEGATI:
        if nome in fatti:
            continue
        vecchio = fr or os.path.join(LOGDIR, nome)
        nuovo = percorso(nome, i=u)
        if os.path.exists(vecchio) and not os.path.exists(nuovo):
            os.makedirs(os.path.dirname(nuovo), exist_ok=True)
            try:
                shutil.copy2(vecchio, nuovo)
            except OSError:
                continue
        fatti.append(nome); nuovi = True
    if nuovi:
        d["migrati"] = fatti
        try:
            salva(d)
        except OSError:
            pass


def applica():
    """Rifa' i percorsi legati per l'account mostrato (dopo una scelta nella tendina o un accesso nuovo ad Arena)."""
    if not PUBBLICA:
        return
    with _LOCK:
        migra()
        if tutti():
            unisci()
        for g, var, nome, fr in _LEGATI:
            g[var] = percorso(nome, fr)
        for f in list(_RICHIAMI):
            try:
                f()
            except Exception as e:      # noqa: BLE001 - un modulo che non si rifa' non ferma gli altri
                print("account.applica:", f, e)


# ------------------------------------------------------------------ prove
def prova():
    import tempfile
    global PUBBLICA, LOGDIR
    casi = []
    d = tempfile.mkdtemp()
    log = os.path.join(d, "Player.log")
    open(log, "wb").write(b'x\n{ "authenticateResponse": { "clientId": "AAAA1111BBBB2222CCCC3333DD", "sessionId": "s", "screenName":"Prima" } }\n'
                          b'{ "authenticateResponse": { "clientId": "ZZZZ1111BBBB2222CCCC3333DD", "sessionId": "s", "screenName":"Seconda" } }\n')
    casi.append(("dal log l'ultimo accesso", dal_log([log]) == ("ZZZZ1111BBBB2222CCCC3333DD", "Seconda")))
    casi.append(("negativa: un log senza accesso non inventa niente", dal_log([os.path.join(d, "manca.log")]) == (None, None)))
    acc = accessi(open(log, "rb").read())
    casi.append(("ogni riga e' dell'ultimo accesso prima di lei", conto_a(acc, acc[1][0] - 1) == "AAAA1111BBBB2222CCCC3333DD" and conto_a(acc, acc[1][0] + 5) == "ZZZZ1111BBBB2222CCCC3333DD"
                 and conto_a(acc, 0) == "AAAA1111BBBB2222CCCC3333DD" and conto_a([], 10) is None))
    vero = (FILE[0], PUBBLICA, list(VIVI), CONTI[0], list(_LEGATI), LOGDIR)
    try:
        FILE[0] = os.path.join(d, "utente.json")
        casi.append(("il link di Untapped si legge e si salva", collega_untapped("https://mtga.untapped.gg/profile/00000000-0000-0000-0000-000000000000/AAAAAAAAAAAAAAAAAAAAAAAAAA")
                     and [c["untapped_player"] for c in leggi()["conti"].values()] == ["AAAAAAAAAAAAAAAAAAAAAAAAAA"]))
        casi.append(("negativa: un link sbagliato non si salva", not collega_untapped("https://example.com/qualcosa")))
        PUBBLICA = False
        _C.clear()
        casi.append(("nell'app di Autore i suoi id e Log_Arena", account()["nome"] == "Player1" and percorso("x.json") == os.path.join(LOGDIR, "x.json")))
        # l'app pubblica: due account, il file di prima, la scelta, il cambio in Arena
        PUBBLICA, LOGDIR = True, os.path.join(d, "pub")       # mai la Log_Arena vera: migra() copierebbe i file di Autore
        FILE[0] = os.path.join(d, "pub", "utente.json"); CONTI[0] = os.path.join(d, "pub", "conti")
        os.makedirs(os.path.dirname(FILE[0]))
        json.dump(dict(id="AAAA1111BBBB2222CCCC3333DD", nome="Prima", untapped_user="u", untapped_player="p", condividi=True), open(FILE[0], "w"))
        _C.clear(); _L.clear(); del _LEGATI[:]
        vivo = os.path.join(d, "vivo.log")
        open(vivo, "wb").write(b'{ "authenticateResponse": { "clientId": "AAAA1111BBBB2222CCCC3333DD", "sessionId": "s", "screenName":"Prima" } }\n')
        VIVI[:] = [vivo]
        vecchio = os.path.join(LOGDIR, "_prova_account_vecchio.json")
        json.dump({"wish": ["di prima"]}, open(vecchio, "w"))
        g = {}
        lega(g, "F", "_prova_account_vecchio.json")
        casi.append(("il file di prima si copia nell'account che c'era, e resta dov'era", json.load(open(g["F"])) == {"wish": ["di prima"]} and os.path.exists(vecchio)))
        casi.append(("il file di prima diventa il primo account, col suo link", account()["untapped_player"] == "p" and leggi()["conti"]["AAAA1111BBBB2222CCCC3333DD"]["condividi"] is True))
        casi.append(("i file dell'account in conti/<id>", g["F"] == os.path.join(CONTI[0], "AAAA1111BBBB2222CCCC3333DD", "_prova_account_vecchio.json")))
        open(vivo, "ab").write(b'{ "authenticateResponse": { "clientId": "ZZZZ1111BBBB2222CCCC3333DD", "sessionId": "s", "screenName":"Seconda" } }\n')
        cambiato = aggiorna(); applica()
        casi.append(("un accesso con un altro account: l'app passa a lui da sola", cambiato and attivo() == "ZZZZ1111BBBB2222CCCC3333DD" and account()["untapped_player"] is None
                     and g["F"].endswith(os.path.join("ZZZZ1111BBBB2222CCCC3333DD", "_prova_account_vecchio.json"))))
        scegli("AAAA1111BBBB2222CCCC3333DD")
        casi.append(("a mano si sceglie l'altro, e resta", attivo() == "AAAA1111BBBB2222CCCC3333DD" and not aggiorna() and attivo() == "AAAA1111BBBB2222CCCC3333DD"))
        for i, x in (("AAAA1111BBBB2222CCCC3333DD", {"wish": [1]}), ("ZZZZ1111BBBB2222CCCC3333DD", {"wish": [2], "build": [3]})):
            p = percorso("_prova_account_vecchio.json", i=i); os.makedirs(os.path.dirname(p), exist_ok=True); json.dump(x, open(p, "w"))
        scegli(TUTTI)
        casi.append(("All accounts: i file uniti, in sola lettura", attivo() is None and sola_lettura()
                     and sorted(json.load(open(g["F"]))["wish"]) == [1, 2] and json.load(open(g["F"]))["build"] == [3]))
        open(vivo, "ab").write(b'{ "authenticateResponse": { "clientId": "ZZZZ1111BBBB2222CCCC3333DD", "sessionId": "s", "screenName":"Seconda" } }\n')
        casi.append(("lo stesso account che rientra non cambia la scelta", not aggiorna() and tutti()))
        open(vivo, "ab").write(b'{ "authenticateResponse": { "clientId": "AAAA1111BBBB2222CCCC3333DD", "sessionId": "s", "screenName":"Prima" } }\n')
        casi.append(("un altro account che entra riporta la scelta su di lui", aggiorna() and scelta() == AUTO and attivo() == "AAAA1111BBBB2222CCCC3333DD"))
        casi.append(("la tendina: l'ultimo entrato per primo", [i for i, _n in conti()] == ["AAAA1111BBBB2222CCCC3333DD", "ZZZZ1111BBBB2222CCCC3333DD"]))
    finally:
        FILE[0], PUBBLICA, VIVI[:], CONTI[0], LOGDIR = vero[0], vero[1], vero[2], vero[3], vero[5]
        _LEGATI[:] = vero[4]
        _C.clear(); _L.clear()
    ok = sum(1 for _n, v in casi if v)
    for n, v in casi:
        print(("ok    " if v else "ROSSO ") + n)
    print(f"{ok}/{len(casi)}")
    return ok == len(casi)


if __name__ == "__main__":
    if "--prova" in sys.argv:
        sys.exit(0 if prova() else 1)
    print(account(), attivo(), scelta(), conti())
