"""La collezione di adesso: lo scarico di Untapped piu' le carte che i log di Arena registrano dopo l'ora dello scarico.

Autore, 8 nov 2026: «controlla bene anche l'algoritmo che legge la collection dal mio log / non vede alcune carte che in realta'
posseggo», poi «fallo leggere dal mio log e' meglio». Fino a quel giorno le copie venivano solo da Collezione/collezione.json, lo scarico
di Untapped, che si aggiorna solo quando Untapped sincronizza: lo scarico era del 6 nov alle 13:11 e mancavano le 40 carte del Quick Draft
FRA del 6 nov sera e due premi del Mastery Pass.

Arena nel Player.log non scrive la collezione intera (scrive il conto: oro, gemme, jolly, token, cosmetici). Scrive le carte che entrano:
i pool dei draft e dei sealed (EventGrantCardPool) e le carte dei premi (GrantedCards nei movimenti dell'inventario: pass, eventi). Le
legge gia' risorse.raccogli, coi suoi tempi, dai log archiviati in Log_Arena e dai due log vivi, ognuna una volta. Qui si sommano allo
scarico quelle dopo il suo last_updated (UTC, portato all'ora del PC come i tempi del log), al massimo 4 copie per stampa come in Arena.
Non entrano, perche' il log non le scrive: le carte delle buste aperte e quelle craftate coi jolly. Arrivano col prossimo scarico di
Untapped (Collezione/scarica_collezione.py, ogni 6 ore nel giro dello scout).

L'aggiornamento lo fa l'app, direttamente (Autore, stesso giorno: «si e' fondamentale che l'aggiornamento della collection sia svolto
dall'app / direttamente»): la finestra grande, nel filo che rilegge il saldo, rifa' le carte dei log al massimo ogni 5 minuti (stato) e
ogni 20 minuti riscarica da Untapped la sola collezione (aggiorna_scarico: una richiesta, ~190 KB; i nomi dal database delle carte gia' sul
PC, come scarica_collezione). Se cambia qualcosa, Collection e mazzi si ridisegnano. Lo scarico intero con Riepilogo.md resta nel giro dello
scout. Lo scarico di Untapped cambia solo quando Untapped ha sincronizzato la tua collezione.

Chi la legge: la scheda Collection (collezione_carte), i mazzi e il builder (finestra_schede.collezione), il Farmer (risorse.set_mancanti).
Il drafter e il suggeritore no: sono blindati e leggono lo scarico come prima.

    py -I -X utf8 Companion/App/Schede/Collection/collezione_viva.py           # le carte aggiunte dai log dopo lo scarico
    py -I -X utf8 Companion/App/Schede/Collection/collezione_viva.py --prova   # i casi, con la prova negativa
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
import threading
import time

import risorse as RS

ROOT = percorsi.ROOT
import account as _ACC  # noqa: E402
# nell'app pubblica la collezione e' dell'account (10 nov 2026, Magic 12: il link di Untapped e' per account); nell'app di Autore Collezione/, come sempre
F_COLL = _ACC.lega(globals(), "F_COLL", "collezione.json", autore=os.path.join(ROOT, "Collezione", "collezione.json"))
F_NOMI = _ACC.lega(globals(), "F_NOMI", "collezione_nomi.json", autore=os.path.join(ROOT, "Collezione", "collezione_nomi.json"))
F_CARTE = os.path.join(ROOT, "Dati", "untapped", "arena_cards", "cards.json")
F_LOC = os.path.join(ROOT, "Dati", "untapped", "arena_cards", "loc_en.json")
MAX = 4                 # Arena tiene al massimo 4 copie di una stampa
OGNI = 300              # i log vivi crescono di continuo in partita: si rileggono al massimo ogni 5 minuti (o se cambia lo scarico)
_CACHE = dict(chiave=None, quando=0.0, d=None)
_DB = {}
_LOCK = threading.Lock()


def soglia(col):
    """L'ora dello scarico nel formato dei tempi del log (ora del PC), o "" se lo scarico non la dice."""
    lu = col.get("last_updated") or ""
    if not lu:
        return ""
    return datetime.datetime.fromisoformat(lu.replace("Z", "+00:00")).astimezone().strftime("%Y-%m-%d %H:%M:%S")


def entrate(foto, pool, dopo):
    """Le carte entrate dopo l'ora data: [(ora, fonte, grpid)], prima i pool dei draft e poi i premi, in ordine di tempo."""
    out = []
    for ora, ev, carte in pool:
        if ora > dopo:
            out += [(ora, ev or "EventGrantCardPool", g) for g in carte]
    for f in foto:
        if f["t"] > dopo:
            for m in f["mov"]:
                if m.get("f") == "EventGrantCardPool":       # i pool si contano una volta sola, da pool
                    continue
                out += [(f["t"], m.get("f") or "reward", g) for g in m.get("g") or []]
    return sorted(out, key=lambda x: x[0])


def somma(base, nuove):
    """base {grpid: copie} piu' le carte nuove, al massimo MAX per stampa. -> (copie, aggiunte davvero [(ora, fonte, grpid)])."""
    copie, piu = dict(base), []
    for ora, fonte, g in nuove:
        if copie.get(g, 0) < MAX:
            copie[g] = copie.get(g, 0) + 1
            piu.append((ora, fonte, g))
    return copie, piu


def _db():
    """grpid -> nome, dal database delle carte di Arena (lo stesso della Collection)."""
    if not _DB:
        try:
            loc = {e["id"]: e["text"] for e in json.load(open(F_LOC, encoding="utf-8"))}
            _DB.update({c["grpid"]: loc.get(c.get("titleId")) for c in json.load(open(F_CARTE, encoding="utf-8"))})
        except (OSError, ValueError):
            pass
    return _DB


def _chiave():
    out = []
    for f in [F_COLL, F_NOMI]:
        try:
            out.append((f, os.path.getmtime(f)))
        except OSError:
            out.append((f, None))
    return tuple(out)


def stato(forza=False):
    """-> dict(copie {grpid: n}, piu [(ora, fonte, grpid)], soglia, quando): lo scarico piu' le carte dei log. Rifatto quando cambia lo scarico,
    se no al massimo ogni OGNI secondi. Senza scarico None."""
    with _LOCK:
        k = _chiave()
        if not forza and _CACHE["d"] is not None and _CACHE["chiave"] == k and time.time() - _CACHE["quando"] < OGNI:
            return _CACHE["d"]
        try:
            col = json.load(open(F_COLL, encoding="utf-8"))
        except (OSError, ValueError):
            return None
        base = {}
        for x in col.get("cards") or []:        # con All accounts le copie dei due account si sommano; un account solo ha ogni grpid una volta
            base[x["grpid"]] = base.get(x["grpid"], 0) + x.get("quantity", 0)
        so = soglia(col)
        try:
            foto, pool = RS.raccogli(aggiorna_cache=False)
        except Exception:
            foto, pool = [], []
        copie, piu = somma(base, entrate(foto, pool, so)) if so else (base, [])
        d = dict(copie=copie, piu=piu, soglia=so, quando=col.get("last_updated") or "", col=col)
        _CACHE.update(chiave=k, quando=time.time(), d=d)
        return d


def url_coll():
    """La collezione del profilo pubblico di Untapped di chi usa l'app (account.py): Autore, o l'utente dell'app pubblica che ha collegato il suo; None se non c'e'."""
    import account
    a = account.account()
    if not (a.get("untapped_user") and a.get("untapped_player")):
        return None
    return f"https://api.mtga.untapped.gg/api/v1/account/collections/{a['untapped_player']}?user_id={a['untapped_user']}"


def _scrivi(path, dati, **kw):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(dati, f, **kw)
    os.replace(tmp, path)


def nomi_da(col):
    """{nome: copie} di uno scarico, come scarica_collezione: il nome dal titleId, sommato su tutte le stampe; le stampe che il database non conosce si saltano."""
    db, nomi = _db(), {}
    for x in col.get("cards") or []:
        n = db.get(x["grpid"])
        if n:
            nomi[n] = nomi.get(n, 0) + x.get("quantity", 0)
    return nomi


def aggiorna_scarico(timeout=20):
    """Riscarica da Untapped la sola collezione; se e' piu' nuova di quella sul PC la scrive (collezione.json e collezione_nomi.json).
    -> True se e' cambiata, False se no, None se Untapped non ha risposto (si tiene quella di prima)."""
    import urllib.request
    url = url_coll()
    if url is None:         # nessun profilo di Untapped collegato: la collezione resta quella dei log
        return None
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "companion-magic-arena/1.0", "Accept": "application/json"})
        col = json.load(urllib.request.urlopen(req, timeout=timeout))
    except Exception:
        return None
    if not isinstance(col, dict) or not col.get("cards"):
        return None              # una risposta vuota non va sopra la collezione buona (3 nov 2026: i trofei vuoti del Quick)
    try:
        vecchia = json.load(open(F_COLL, encoding="utf-8"))
    except (OSError, ValueError):
        vecchia = {}
    if col.get("last_updated") == vecchia.get("last_updated") and len(col["cards"]) == len(vecchia.get("cards") or []):
        return False
    nomi = nomi_da(col)
    if not nomi:
        return None
    _scrivi(F_COLL, col, indent=1)
    _scrivi(F_NOMI, nomi, indent=1, ensure_ascii=False)
    with _LOCK:
        _CACHE.update(chiave=None, d=None)
    return True


def righe():
    """Le carte nel formato dello scarico, [{"grpid", "quantity"}], con quelle dei log: per collezione_carte."""
    s = stato()
    return [dict(grpid=g, quantity=q) for g, q in s["copie"].items()] if s else []


def copie_nomi():
    """{nome: copie} come Collezione/collezione_nomi.json, piu' le carte dei log (per nome, sommate su tutte le stampe)."""
    try:
        nomi = dict(json.load(open(F_NOMI, encoding="utf-8")))
    except (OSError, ValueError):
        nomi = {}
    s = stato()
    if s and s["piu"]:
        db = _db()
        for _ora, _f, g in s["piu"]:
            n = db.get(g)
            if n:
                nomi[n] = nomi.get(n, 0) + 1
    return nomi


def prova():
    """Lo scarico piu' le carte dei log: dopo l'ora contano, prima no; il tetto delle 4 copie; i pool non si contano due volte."""
    esiti = []
    foto = [dict(t="2026-11-06 10:00:00", mov=[dict(f="CampaignGraphTieredRewardNode", g=[1])]),
            dict(t="2026-11-07 14:30:30", mov=[dict(f="CampaignGraphTieredRewardNode", g=[2]), dict(f="EventGrantCardPool", g=[3, 3])])]
    pool = [["2026-11-06 12:00:00", "QuickDraft_FRA", [9, 9]], ["2026-11-06 19:13:23", "QuickDraft_FRA", [3, 3, 4, 5]]]
    nuove = entrate(foto, pool, "2026-11-06 13:11:20")
    esiti.append(("dopo lo scarico si', prima no", sorted(g for _o, _f, g in nuove) == [2, 3, 3, 4, 5]))
    copie, piu = somma({3: 3, 4: 4}, nuove)
    esiti.append(("al massimo 4 copie per stampa", copie == {3: 4, 4: 4, 5: 1, 2: 1} and len(piu) == 3))
    esiti.append(("lo scarico senza ora non somma niente", entrate(foto, pool, "9999") == []))
    # negativa: senza il filtro dell'ora le carte di prima dello scarico si conterebbero due volte
    tutte = entrate(foto, pool, "")
    esiti.append(("negativa: senza l'ora si conterebbero anche le vecchie", len(tutte) > len(nuove)))
    _DB.clear(); _DB.update({10: "Carta A", 11: "Carta A", 12: "Carta B"})
    esiti.append(("i nomi dello scarico sommano le stampe e saltano le ignote", nomi_da({"cards": [dict(grpid=10, quantity=2), dict(grpid=11, quantity=1), dict(grpid=12, quantity=4), dict(grpid=99, quantity=1)]})
                  == {"Carta A": 3, "Carta B": 4}))
    _DB.clear()
    so = soglia({"last_updated": "2026-11-06T12:11:20Z"})
    esiti.append(("l'ora di Untapped (UTC) diventa l'ora del PC", len(so) == 19 and so[:10] == "2026-11-06"))
    for nome, ok in esiti:
        print(("  ok    " if ok else "  ROSSO ") + nome)
    print(f"{sum(ok for _n, ok in esiti)}/{len(esiti)}")
    return all(ok for _n, ok in esiti)


def main():
    if "--prova" in sys.argv:
        return 0 if prova() else 1
    if "--scarica" in sys.argv:
        print({True: "collezione aggiornata da Untapped", False: "Untapped: nessuna novita'", None: "Untapped non ha risposto"}[aggiorna_scarico()])
    s = stato(forza=True)
    if not s:
        print("nessuno scarico della collezione")
        return 1
    db = _db()
    print(f"scarico di Untapped: {s['quando']} (ora del PC {s['soglia']}); carte aggiunte dai log dopo: {len(s['piu'])}")
    for ora, fonte, g in s["piu"]:
        print(f"  {ora}  {fonte:32}  {db.get(g) or g}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
