"""La condivisione dei dati delle partite con noi, solo col consenso di chi usa l'app (10 nov 2026, Autore: «raccogliere dati dai loro log»).

Regole (sono anche nell'informativa, Distribuzione/modelli/PRIVACY.md):
- spenta finche' l'utente non dice di si' (il primo avvio lo chiede; si cambia dalla scheda Help); il consenso sta in Log_Arena/utente.json («condividi»);
- per ogni partita finita si manda solo: evento, giorno (senza ora), esito, chi comincia, mulligan, turni, le carte del mazzo, la mano tenuta, le carte
  dell'avversario viste. Mai il nome in gioco, mai quello dell'avversario, mai l'id dell'account: al suo posto un codice (SHA-256 dell'id con un sale fisso
  dell'app), lo stesso per le partite della stessa persona: dati pseudonimi, non anonimi, e l'informativa lo dice;
- prima si mette in coda (Log_Arena/condivisione/coda.jsonl, si puo' leggere), poi si manda all'indirizzo del canale (manifest «endpoint_log»); finche' il
  canale non ne ha uno, resta in coda e non esce niente dal PC;
- una partita si manda una volta (Log_Arena/condivisione/inviate.json);
- il consenso e' di ogni account di Arena (10 nov 2026, Magic 12: due persone sullo stesso PC): sta in utente.json sotto il suo account («conti»), e si mettono in
  coda solo le partite degli account che hanno detto si'. Un account nuovo non ha ancora risposto: il primo avvio glielo chiede.

    py -I -X utf8 Companion/App/Comune/condividi.py --prova     partite finte: niente nomi e niente id nella coda; senza consenso niente coda
"""
import os, sys
_casa = os.path.dirname(os.path.abspath(__file__))      # si sale fino a percorsi.py, che mette nel sys.path tutte le cartelle del Companion
while not os.path.isfile(os.path.join(_casa, "percorsi.py")):
    _casa = os.path.dirname(_casa)
if _casa not in sys.path:
    sys.path.insert(0, _casa)
import percorsi  # noqa: E402
import datetime  # noqa: E402
import hashlib  # noqa: E402
import json  # noqa: E402
import re  # noqa: E402

SALE = "companion-magic-arena/condivisione/v1"
VERSIONE_DATI = 1
CARTELLA = [os.path.join(percorsi.ROOT, "Log_Arena", "condivisione")]


def codice(x):
    return hashlib.sha256((SALE + "|" + str(x)).encode()).hexdigest()[:16]


def _chi(conto):
    import account
    if conto:
        return conto
    if not account.PUBBLICA:
        return account.AUTORE["id"]
    return account.attivo() or account.leggi().get("ultimo")


def consenso(conto=None):
    """True, False o None (non ancora chiesto), dell'account (None: quello mostrato)."""
    import account
    return (account.leggi()["conti"].get(_chi(conto)) or {}).get("condividi")


def imposta_consenso(si, conto=None):
    import account
    d = account.leggi()
    d["conti"].setdefault(_chi(conto) or "?", {})["condividi"] = bool(si)
    account.salva(d)


def qualcuno():
    """Almeno un account ha detto si'."""
    import account
    return any(c.get("condividi") is True for c in account.leggi()["conti"].values())


def nomi(grp):
    """[grpId] -> {nome: copie} col database delle carte."""
    import deckstring_scrivi as DS
    try:
        from deckstring import TITOLI
    except Exception:       # noqa: BLE001 - senza nomi la partita non si manda
        return None
    out = {}
    for t, q in DS.da_grp(grp).items():
        n = TITOLI.get(str(t))
        if n:
            out[n] = out.get(n, 0) + q
    return out


def riga(p, id_account):
    """La riga di una partita del log (partite_log.partite) da mandare, o None se non e' finita."""
    if p.get("vinta") is None:
        return None
    mazzo = nomi(p.get("carte") or [])
    if mazzo is None:
        return None
    mani = p.get("mani") or []
    return dict(v=VERSIONE_DATI, partita=codice(p["matchId"]), giocatore=codice(id_account or "?"), evento=p.get("evento"),
                giorno=datetime.date.fromtimestamp(p["inizio"] / 1000).isoformat(), vinta=bool(p["vinta"]),
                inizia=(p.get("inizia") == p.get("seat")) if p.get("inizia") is not None else None, mulligan=max(0, len(mani) - 1), turni=p.get("turni"),
                mazzo=mazzo, side=nomi(p.get("side") or []), mano=sorted(nomi(mani[-1]) if mani else {}), sue=sorted(nomi(p.get("sue") or []) or {}),
                limited=bool(re.search(r"Draft|Sealed|Cube", p.get("evento") or "")))


def accoda(partite=None, id_account=None):
    """Mette in coda le partite finite non ancora in coda, solo col consenso del loro account. -> quante. partite None: quelle di tutti gli account del PC."""
    if partite is None:
        import account
        import partite_log
        partite, _n = partite_log.partite(conto=account.TUTTI)
        partite = [p for p in partite if consenso(p.get("conto")) is True]
    elif consenso(id_account) is not True:
        return 0
    if not partite:
        return 0
    os.makedirs(CARTELLA[0], exist_ok=True)
    f_coda, f_fatte = os.path.join(CARTELLA[0], "coda.jsonl"), os.path.join(CARTELLA[0], "inviate.json")
    gia = set()
    for f in (f_coda,):
        if os.path.exists(f):
            gia |= {json.loads(r)["partita"] for r in open(f, encoding="utf-8") if r.strip()}
    if os.path.exists(f_fatte):
        gia |= set(json.load(open(f_fatte, encoding="utf-8")))
    n = 0
    with open(f_coda, "a", encoding="utf-8") as g:
        for p in partite:
            r = riga(p, id_account or p.get("conto"))
            if r and r["partita"] not in gia:
                g.write(json.dumps(r, ensure_ascii=False) + "\n")
                gia.add(r["partita"]); n += 1
    return n


def endpoint():
    """L'indirizzo a cui mandare le partite: nell'app pubblica da canale.json («endpoint_log»), in quella di Autore da Distribuzione/config.json (11 nov 2026:
    anche le sue partite si condividono, col consenso dato in Help come tutti). "" finche' il server dei dati non e' online (Distribuzione/server_dati)."""
    for f in (os.path.join(percorsi.ROOT, "canale.json"), os.path.join(percorsi.ROOT, "Distribuzione", "config.json")):
        try:
            return str(json.load(open(f, encoding="utf-8")).get("endpoint_log") or "").strip()
        except (OSError, ValueError):
            continue
    return ""


def invia(endpoint, timeout=30):
    """Manda la coda all'indirizzo (POST, JSON lines), solo col consenso e con un indirizzo https. -> quante mandate, o None se non si manda."""
    if not qualcuno() or not endpoint or not endpoint.startswith("https://"):
        return None
    import urllib.request
    f_coda, f_fatte = os.path.join(CARTELLA[0], "coda.jsonl"), os.path.join(CARTELLA[0], "inviate.json")
    if not os.path.exists(f_coda):
        return 0
    righe = [r for r in open(f_coda, encoding="utf-8").read().splitlines() if r.strip()]
    if not righe:
        return 0
    req = urllib.request.Request(endpoint, data="\n".join(righe).encode("utf-8"), method="POST",
                                 headers={"Content-Type": "application/x-ndjson", "User-Agent": "companion-magic-arena/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        if r.status >= 300:
            return None
    fatte = set(json.load(open(f_fatte, encoding="utf-8"))) if os.path.exists(f_fatte) else set()
    fatte |= {json.loads(r)["partita"] for r in righe}
    json.dump(sorted(fatte), open(f_fatte, "w", encoding="utf-8"))
    open(f_coda, "w", encoding="utf-8").close()
    return len(righe)


def prova():
    import tempfile
    import account
    d = tempfile.mkdtemp()
    vero_c, vero_f = CARTELLA[0], account.FILE[0]
    CARTELLA[0], account.FILE[0] = os.path.join(d, "cond"), os.path.join(d, "utente.json")
    import deckstring_scrivi as DS
    t = DS.titoli()
    grp = list(t)[:3]
    pp = [dict(matchId="m-1", inizio=1794224501827, evento="Ladder", vinta=True, inizia=1, seat=1, turni=9, carte=grp * 2, side=[], mani=[grp[:2]], sue=[grp[2]],
               avversario="NomeAvversario"),
          dict(matchId="m-2", inizio=1794224501827, evento="Play", vinta=None, inizia=1, seat=2, turni=3, carte=grp, mani=[], sue=[], avversario="Altro")]
    casi = []
    try:
        casi.append(("negativa: senza consenso niente in coda", accoda(pp, "AAAAAAAAAAAAAAAAAAAAAAAAAA") == 0 and not os.path.exists(os.path.join(d, "cond", "coda.jsonl"))))
        imposta_consenso(True)
        n = accoda(pp, "AAAAAAAAAAAAAAAAAAAAAAAAAA")
        testo = open(os.path.join(d, "cond", "coda.jsonl"), encoding="utf-8").read()
        r = json.loads(testo.splitlines()[0])
        casi.append(("col consenso la partita finita va in coda, quella senza esito no", n == 1))
        casi.append(("niente nomi e niente id: ne' il tuo, ne' quello dell'avversario", "AAAAAAAAAAAAAAAAAAAAAAAAAA" not in testo and "NomeAvversario" not in testo
                     and "m-1" not in testo and r["giocatore"] == codice("AAAAAAAAAAAAAAAAAAAAAAAAAA")))
        casi.append(("il giorno senza l'ora, il mazzo coi nomi delle carte", len(r["giorno"]) == 10 and sum(r["mazzo"].values()) == 6 and r["mulligan"] == 0 and r["inizia"] is True))
        casi.append(("una partita non si mette in coda due volte", accoda(pp, "AAAAAAAAAAAAAAAAAAAAAAAAAA") == 0))
        casi.append(("negativa: senza indirizzo https non si manda niente", invia("") is None and invia("http://x") is None))
        imposta_consenso(False)
        casi.append(("negativa: tolto il consenso non si manda", invia("https://example.invalid/x") is None))
    finally:
        CARTELLA[0], account.FILE[0] = vero_c, vero_f
        account._C.clear()
    ok = sum(1 for _n, v in casi if v)
    for n, v in casi:
        print(("ok    " if v else "ROSSO ") + n)
    print(f"{ok}/{len(casi)}")
    return ok == len(casi)


if __name__ == "__main__":
    if "--prova" in sys.argv:
        sys.exit(0 if prova() else 1)
    print("consenso:", consenso())
