"""La condivisione COMPLETA delle partite: il log di ogni partita e il nome Arena di chi gioca (21 nov 2026; Autore: «imposta i log, voglio il 1000% dei dati»).

E' una seconda scelta, separata dalla condivisione di prima (condividi.py) e SPENTA di partenza: chi la accende dice di si' a due cose in piu', il suo nome
in gioco e il log della partita. Il consenso sta in utente.json sotto l'account («completa»), come «condividi».

Cosa NON esce mai, anche col si': il nome dell'avversario (e il suo id), gli id degli account (nostro e suo), le chat, e-mail, token e indirizzi di rete.
Gli avversari non hanno detto di si': nel log il loro nome diventa «OPPONENT», il loro id «ID-n». `pulisci` e' l'unica via per cui un log esce dal PC e
`pulita` lo controlla (esce None se dopo la pulizia resta traccia del nome dell'avversario: la partita allora non parte).

La coda e' locale (Log_Arena/condivisione/completa.jsonl, un log compresso per riga) e si svuota verso POST /logs del server dei dati
(Distribuzione/server_dati/worker.js, i log in R2). Finche' il Worker vero non ha il bucket R2 e la tabella logs il server risponde 404 e i log restano
in coda: non esce niente.

    py -I -X utf8 Companion/App/Comune/condividi_completa.py --prova
"""
import os, sys
_casa = os.path.dirname(os.path.abspath(__file__))
while not os.path.isfile(os.path.join(_casa, "percorsi.py")):
    _casa = os.path.dirname(_casa)
if _casa not in sys.path:
    sys.path.insert(0, _casa)
import percorsi  # noqa: E402
import base64  # noqa: E402
import gzip  # noqa: E402
import json  # noqa: E402
import re  # noqa: E402

VERSIONE = 1
MAX_LOG_B64 = 1_500_000       # i limiti del Worker (worker.js): un log, e i log di una richiesta
MAX_RIGHE_LOG, MAX_BYTE_PACCO = 3, 2_900_000
ID_ARENA = re.compile(r"\b[A-Z2-7]{26}\b")                      # gli id di Arena (base32, 26 caratteri), come AAAAAAAAAAAAAAAAAAAAAAAAAA
UUID = re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.I)
EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
JWT = re.compile(r"eyJ[\w-]+\.[\w-]+\.[\w-]+")
RETE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
CAMPI_NOME = re.compile(r'("(?:playerName|screenName|opponentScreenName|displayName|friendName)"\s*:\s*")[^"]*(")', re.I)


def consenso(conto=None):
    import account
    import condividi
    return (account.leggi()["conti"].get(condividi._chi(conto)) or {}).get("completa")


def imposta_consenso(si, conto=None):
    import account
    import condividi
    d = account.leggi()
    d["conti"].setdefault(condividi._chi(conto) or "?", {})["completa"] = bool(si)
    account.salva(d)


def pulisci(testo, mio_nome, avversario):
    """Il log della partita senza i dati di chi non ha acconsentito. -> (testo pulito, id sostituiti)."""
    ids = {}

    def id_(m):
        ids.setdefault(m.group(0), f"ID-{len(ids) + 1}")
        return ids[m.group(0)]

    # i nomi: ogni campo «playerName» & co. prende il nome di chi gioca o OPPONENT; poi ogni altra occorrenza del nome dell'avversario (anche col #12345)
    def nome(m):
        v = m.group(0)[len(m.group(1)):-len(m.group(2))]
        return m.group(1) + (mio_nome if mio_nome and v.split("#")[0] == mio_nome.split("#")[0] else "OPPONENT") + m.group(2)
    t = CAMPI_NOME.sub(nome, testo)
    if avversario:
        base = re.escape(avversario.split("#")[0])
        t = re.sub(base + r"(?:#\d+)?", "OPPONENT", t, flags=re.I)
    t = JWT.sub("TOKEN", t)
    t = EMAIL.sub("EMAIL", t)
    t = RETE.sub("0.0.0.0", t)
    t = ID_ARENA.sub(id_, t)
    t = UUID.sub(id_, t)
    return t, len(ids)


def pulita(testo, mio_nome, avversario):
    """Il log pulito, o None se dopo la pulizia c'e' ancora il nome dell'avversario (non si manda)."""
    t, _n = pulisci(testo, mio_nome, avversario)
    if avversario and len(avversario.split("#")[0]) >= 3 and avversario.split("#")[0].lower() in t.lower() \
            and avversario.split("#")[0].lower() not in (mio_nome or "").lower():
        return None
    return t


def impacchetta(testo):
    return base64.b64encode(gzip.compress(testo.encode("utf-8"), 6)).decode("ascii")


def accoda_partita(cartella, mio_nome, id_account):
    """Mette in coda il log pulito di UNA partita finita (la sua cartella in Log_Arena/partite), col consenso. -> True se in coda."""
    try:
        meta = json.load(open(os.path.join(cartella, "partita.json"), encoding="utf-8"))
        log = open(os.path.join(cartella, "arena.log"), encoding="utf-8", errors="replace").read()
    except (OSError, ValueError):
        return False
    if not meta.get("finita") or "Sparky" in (meta.get("avversario") or ""):
        return False
    import condividi
    t = pulita(log, mio_nome, meta.get("avversario"))
    if t is None:
        return False
    cod = condividi.codice(meta.get("matchId"))
    f = os.path.join(condividi.CARTELLA[0], "completa.jsonl")
    os.makedirs(condividi.CARTELLA[0], exist_ok=True)
    if os.path.exists(f) and any(json.loads(r).get("partita") == cod for r in open(f, encoding="utf-8") if r.strip()):
        return False
    pacco = impacchetta(t)
    if len(pacco) > MAX_LOG_B64 or not (mio_nome or "").strip():      # oltre il limite del server la partita resterebbe in coda per sempre
        return False
    # il codice del giocatore e' lo stesso di condividi.riga: lega il log al riassunto della stessa partita e al suo nome
    riga = dict(v=VERSIONE, partita=cod, giocatore=condividi.codice(id_account), nome=mio_nome, evento=meta.get("evento"), log=pacco)
    with open(f, "a", encoding="utf-8") as g:
        g.write(json.dumps(riga, ensure_ascii=False) + "\n")
    return True


def accoda_tutte(limite=200):
    """Le partite finite in Log_Arena/partite, dalle piu' recenti, degli account che hanno acceso la condivisione completa. -> quante nuove in coda."""
    import account
    import condividi
    d = account.leggi()
    conti = {i: c for i, c in d["conti"].items() if c.get("completa") is True and c.get("nome")}
    if not conti:
        return 0
    base = os.path.join(percorsi.ROOT, "Log_Arena", "partite")
    if not os.path.isdir(base):
        return 0
    n = 0
    for nome_c in sorted(os.listdir(base))[-limite:]:
        # una partita e' dell'account il cui id e' nel suo log (il log tiene solo la sua cartella: un PC con piu' account non mescola i nomi)
        try:
            log = open(os.path.join(base, nome_c, "arena.log"), encoding="utf-8", errors="replace").read(400000)
        except OSError:
            continue
        for i, c in conti.items():
            if i in log and accoda_partita(os.path.join(base, nome_c), c["nome"], i):
                n += 1
                break
    return n


def endpoint_logs(endpoint):
    """L'indirizzo dei log dal quello delle partite («.../games» -> «.../logs»); "" se non c'e' o non e' https."""
    e = (endpoint or "").strip()
    return e[:-len("/games")] + "/logs" if e.startswith("https://") and e.endswith("/games") else ""


def pacchi(righe):
    """Le righe della coda a pacchi che il server accetta (worker.js: 3 log e 3 MB a richiesta)."""
    pacco, peso = [], 0
    for r in righe:
        n = len(r.encode("utf-8")) + 1
        if pacco and (len(pacco) >= MAX_RIGHE_LOG or peso + n > MAX_BYTE_PACCO):
            yield pacco
            pacco, peso = [], 0
        pacco.append(r)
        peso += n
    if pacco:
        yield pacco


def invia(endpoint, timeout=60):
    """Manda la coda dei log completi (POST, JSON lines) solo con un account col consenso e un indirizzo https. Ogni pacco arrivato esce dalla coda; un log
    scartato dal server o un pacco caduto resta per il giro dopo. -> quanti mandati, o None se non si manda niente."""
    import account
    url = endpoint_logs(endpoint)
    if not url or not any(c.get("completa") is True for c in account.leggi()["conti"].values()):
        return None
    import condividi
    f = os.path.join(condividi.CARTELLA[0], "completa.jsonl")
    f_fatte = os.path.join(condividi.CARTELLA[0], "completa_inviate.json")
    if not os.path.exists(f):
        return 0
    righe = [r for r in open(f, encoding="utf-8").read().splitlines() if r.strip()]
    if not righe:
        return 0
    import urllib.request
    try:
        import ssl, certifi
        ctx = ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        ctx = None
    mandate = []
    try:
        for pacco in pacchi(righe):
            req = urllib.request.Request(url, data="\n".join(pacco).encode("utf-8"), method="POST",
                                         headers={"Content-Type": "application/x-ndjson", "User-Agent": "companion-magic-arena/1.0"})
            with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
                if r.status >= 300:
                    break
                try:
                    scartate = int(json.loads(r.read().decode("utf-8") or "{}").get("rejected") or 0)
                except (ValueError, AttributeError):
                    scartate = 0
            if scartate:
                print("condivisione completa: il server ha scartato", scartate, "log su", len(pacco), "- restano in coda")
                break
            mandate += pacco
    finally:
        if mandate:
            fatte = set(json.load(open(f_fatte, encoding="utf-8"))) if os.path.exists(f_fatte) else set()
            fatte |= {json.loads(r)["partita"] for r in mandate}
            json.dump(sorted(fatte), open(f_fatte, "w", encoding="utf-8"))
            with open(f, "w", encoding="utf-8") as c:
                c.write("".join(r + "\n" for r in righe[len(mandate):]))
    return len(mandate) if mandate else None


def prova():
    mio, opp = "Player1#12345", "Windregon#98765"
    log = ('{"playerName":"Player1","userId":"AAAAAAAAAAAAAAAAAAAAAAAAAA","systemSeatId":1}\n'
           '{"playerName":"Windregon","userId":"FPK6PIA6X5FPNDBYHZBUCH3J2I"}\n'
           'chat: Windregon#98765 says hi, mail a@b.it, ip 10.1.2.3, id 4d0cdba8-86f4-464f-be53-c954bde2edc0 eyJabc.def.ghi\n')
    t, n = pulisci(log, mio, "Windregon#98765")
    casi = [("il nome dell'avversario non c'e' piu'", "windregon" not in t.lower()),
            ("il nome di chi condivide resta", "Player1" in t),
            ("niente id Arena, e-mail, indirizzi di rete, token", not any(x in t for x in ("EVIULOS5", "FPK6PIA6", "a@b.it", "10.1.2.3", "eyJabc"))),
            ("lo stesso id resta lo stesso (la partita si legge ancora)", n == 3 and t.count("ID-1") == 1),
            ("il log si impacchetta e si rilegge uguale", gzip.decompress(base64.b64decode(impacchetta(t))).decode() == t),
            ("il controllo finale: nel log pulito non c'e' piu' il nome", pulita(log, mio, "Windregon#98765") is not None)]
    # negativa: con una pulizia rotta (non toglie niente) il controllo finale ferma la partita
    vera = globals()["pulisci"]
    globals()["pulisci"] = lambda testo, m, a: (testo, 0)
    try:
        casi.append(("negativa: pulizia rotta -> la partita non parte", pulita(log, mio, "Windregon#98765") is None))
    finally:
        globals()["pulisci"] = vera
    for nome, ok in casi:
        print(("ok    " if ok else "ROSSO ") + nome)
    print(f"{sum(1 for _n, ok in casi if ok)}/{len(casi)}")
    return all(ok for _n, ok in casi)


if __name__ == "__main__":
    if "--prova" in sys.argv:
        sys.exit(0 if prova() else 1)
