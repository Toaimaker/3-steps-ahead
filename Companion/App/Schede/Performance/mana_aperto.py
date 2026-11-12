"""Il mana aperto nelle partite (Autore, 12 nov 2026: «situazioni piu' specifiche, come x esempio vs mana untapped / with mana untapped»): dai pezzi di log di
ogni partita (Log_Arena/partite/<ID>/arena.log, partite_separate) si segue lo stato del gioco di Arena (oggetti, zone, turno) e si annota:
- a ogni turno con un attacco, le terre stappate di chi difende quando gli attaccanti sono dichiarati (la prima volta nel turno);
- alla fine di ogni turno (passo End), le terre stappate di chi era di turno.
Le terre sono gli oggetti in campo col tipo Land; stappate = senza isTapped. Una copia su disco (Log_Arena/mana_aperto.json, VERSIONE) evita di rileggere: una partita
si legge una volta sola. Le partite senza il pezzo di log (l'app pubblica non li scrive: costano centinaia di MB) si leggono dai log archiviati
(Log_Arena/20*_Player*.log, archivia_log), ritagliate in memoria come fa partite_separate; ogni archivio si guarda una volta (la copia ricorda nome e misura).

    py -I -X utf8 Companion/App/Schede/Performance/mana_aperto.py --prova
"""
import os, sys
_casa = os.path.dirname(os.path.abspath(__file__))
while not os.path.isfile(os.path.join(_casa, "percorsi.py")):
    _casa = os.path.dirname(_casa)
if _casa not in sys.path:
    sys.path.insert(0, _casa)
import percorsi  # noqa: E402,F401
import glob  # noqa: E402
import json  # noqa: E402
import re  # noqa: E402

from ambiente import LOGDIR  # noqa: E402

VERSIONE = 1
CARTELLA = os.path.join(LOGDIR, "partite")
COPIA = os.path.join(LOGDIR, "mana_aperto.json")


def leggi(righe):
    """Le righe di un pezzo di log -> dict(attacchi=[[turno, chi attacca, terre stappate di chi difende, sue terre]], fine=[[turno, chi, stappate, terre]])."""
    obj, zone, ti = {}, {}, {}
    attacchi, fine, visti_att, visti_fine = [], [], set(), set()

    def terre(seat):
        tot = stap = 0
        for o in obj.values():
            if o.get("controllerSeatId") == seat and "CardType_Land" in (o.get("cardTypes") or []) and zone.get(o.get("zoneId")) == "ZoneType_Battlefield":
                tot += 1
                stap += 0 if o.get("isTapped") else 1
        return stap, tot
    for r in righe:
        if "gameStateMessage" not in r:
            continue
        i = r.find("{")
        if i < 0:
            continue
        try:
            d = json.loads(r[i:])
        except ValueError:
            continue
        for m in (d.get("greToClientEvent") or {}).get("greToClientMessages") or []:
            gs = m.get("gameStateMessage")
            if not gs:
                continue
            if gs.get("type") == "GameStateType_Full":
                obj, zone = {}, {}
            for z in gs.get("zones") or []:
                zone[z.get("zoneId")] = z.get("type")
            for o in gs.get("gameObjects") or []:
                obj[o.get("instanceId")] = o
            for x in gs.get("deletedInstanceIds") or []:
                obj.pop(x, None)
            if gs.get("turnInfo"):
                ti.update(gs["turnInfo"])
            t, att = ti.get("turnNumber"), ti.get("activePlayer")
            if t is None or att is None:
                continue
            if t not in visti_att and any(o.get("attackState") in ("AttackState_Declared", "AttackState_Attacking") and o.get("controllerSeatId") == att
                                          and zone.get(o.get("zoneId")) == "ZoneType_Battlefield" for o in obj.values()):
                visti_att.add(t)
                difende = 2 if att == 1 else 1
                s, n = terre(difende)
                attacchi.append([t, att, s, n])
            if ti.get("step") == "Step_End" and t not in visti_fine:
                visti_fine.add(t)
                s, n = terre(att)
                fine.append([t, att, s, n])
    return dict(attacchi=attacchi, fine=fine)


def indice():
    """{matchId: cartella} dei pezzi di log."""
    out = {}
    for f in glob.glob(os.path.join(CARTELLA, "*", "partita.json")):
        try:
            with open(f, encoding="utf-8") as h:
                mid = json.load(h).get("matchId")
        except (OSError, ValueError):
            continue
        if mid:
            out[mid] = os.path.dirname(f)
    return out


MID = re.compile(rb'"matchId"\s*:\s*"([0-9a-f-]{36})"|Connecting to matchId ([0-9a-f-]{36})')


def dagli_archivi(dati, letti, ids):
    """Le partite che mancano, dai log archiviati: ogni archivio non ancora guardato (nome e misura in letti), le sue partite ritagliate in memoria.
    -> quante nuove."""
    nuove = 0
    for f in sorted(glob.glob(os.path.join(LOGDIR, "20*_Player*.log")), reverse=True):     # dal piu' nuovo
        chiave = os.path.basename(f)
        try:
            misura = os.path.getsize(f)
        except OSError:
            continue
        if letti.get(chiave) == misura:
            continue
        if ids is not None and not (set(ids) - set(dati)):     # nessuna partita che serve manca: gli archivi restano da guardare un'altra volta
            break
        try:
            with open(f, "rb") as h:
                data = h.read()
        except OSError:
            continue
        for mid in dict.fromkeys((a or b).decode() for a, b in MID.findall(data)):
            if mid in dati or (ids is not None and mid not in ids):
                continue
            m = mid.encode()
            i = data.find(m); i = data.rfind(b"\n", 0, i) + 1
            j = data.rfind(m); j = data.find(b"\n", j); j = len(data) if j < 0 else j + 1
            d = leggi(data[i:j].decode("utf-8", "replace").splitlines())
            if d["attacchi"] or d["fine"]:
                dati[mid] = d
                nuove += 1
        letti[chiave] = misura
    return nuove


def tutti(ids=None, archivi=True):
    """{matchId: dato}: dalla copia, le nuove dai pezzi di log e (archivi) dai log archiviati, poi salvate. ids: solo queste partite."""
    try:
        with open(COPIA, encoding="utf-8") as h:
            c = json.load(h)
        if c.get("versione") != VERSIONE:
            c = {}
    except (OSError, ValueError):
        c = {}
    dati = c.get("partite") or {}
    letti = c.get("archivi") or {}
    nuove = 0
    for mid, cart in indice().items():
        if mid in dati or (ids is not None and mid not in ids):
            continue
        try:
            with open(os.path.join(cart, "arena.log"), encoding="utf-8", errors="replace") as h:
                dati[mid] = leggi(h)
            nuove += 1
        except OSError:
            continue
    prima = len(letti)
    if archivi:
        nuove += dagli_archivi(dati, letti, ids)
    if nuove or len(letti) != prima:
        try:
            os.makedirs(os.path.dirname(COPIA), exist_ok=True)
            with open(COPIA + ".tmp", "w", encoding="utf-8") as h:
                json.dump(dict(versione=VERSIONE, partite=dati, archivi=letti), h)
            os.replace(COPIA + ".tmp", COPIA)
        except OSError:
            pass
    return dati


def situazioni(d, seat):
    """Le situazioni del mana aperto di una partita, dal tuo posto: {chiave: True, False o None}."""
    chiavi = ("io_att_aperto", "io_att_chiuso", "lui_att_aperto", "io_passa_aperto", "lui_passa_aperto")
    if not d or seat is None:
        return {k: None for k in chiavi}
    mie = [a for a in d["attacchi"] if a[1] == seat]
    sue = [a for a in d["attacchi"] if a[1] != seat]
    fm = [f for f in d["fine"] if f[1] == seat and f[3] >= 3]      # dal momento che hai almeno 3 terre: prima passare con 2 aperte non e' una scelta
    fs = [f for f in d["fine"] if f[1] != seat and f[3] >= 3]
    return dict(io_att_aperto=any(a[2] >= 2 for a in mie), io_att_chiuso=any(a[2] == 0 and a[3] >= 2 for a in mie), lui_att_aperto=any(a[2] >= 2 for a in sue),
                io_passa_aperto=any(f[2] >= 2 for f in fm), lui_passa_aperto=any(f[2] >= 2 for f in fs))


def prova():
    """Un log finto: tu (seat 1) attacchi al turno 3 con lui a 2 terre stappate, lui attacca al 4 con te tappato; i passi End."""
    def gs(**k):
        return "[UnityCrossThreadLogger]x " + json.dumps(dict(greToClientEvent=dict(greToClientMessages=[dict(gameStateMessage=k)])))
    terra = lambda i, seat, tap: dict(instanceId=i, controllerSeatId=seat, cardTypes=["CardType_Land"], zoneId=28, **({"isTapped": True} if tap else {}))
    crea = lambda i, seat, att: dict(instanceId=i, controllerSeatId=seat, cardTypes=["CardType_Creature"], zoneId=28, **({"attackState": "AttackState_Declared"} if att else {}))
    righe = [gs(type="GameStateType_Full", zones=[dict(zoneId=28, type="ZoneType_Battlefield")], turnInfo=dict(turnNumber=3, activePlayer=1, step="Step_BeginCombat"),
                gameObjects=[terra(1, 1, False), terra(2, 1, False), terra(3, 1, True), terra(4, 2, False), terra(5, 2, False), crea(10, 1, False)]),
             gs(type="GameStateType_Diff", turnInfo=dict(step="Step_DeclareAttack"), gameObjects=[crea(10, 1, True)]),
             gs(type="GameStateType_Diff", turnInfo=dict(step="Step_End"), gameObjects=[crea(10, 1, False)]),
             gs(type="GameStateType_Diff", turnInfo=dict(turnNumber=4, activePlayer=2, step="Step_DeclareAttack"),
                gameObjects=[terra(1, 1, True), terra(2, 1, True), terra(3, 1, True), dict(crea(11, 2, True))]),
             gs(type="GameStateType_Diff", turnInfo=dict(step="Step_End"), gameObjects=[terra(4, 2, True)])]
    d = leggi(righe)
    casi = [("gli attacchi: al T3 attacchi tu e lui ha 2 terre stappate su 2; al T4 attacca lui e tu hai 0 stappate su 3", d["attacchi"] == [[3, 1, 2, 2], [4, 2, 0, 3]]),
            ("la fine dei turni: T3 tu con 2 stappate su 3, T4 lui con 1 su 2", d["fine"] == [[3, 1, 2, 3], [4, 2, 1, 2]])]
    s = situazioni(d, 1)
    casi.append(("situazioni dal tuo posto: attacchi contro 2 aperte, lui attacca contro te tappato, passi con 2 aperte", s["io_att_aperto"] and not s["io_att_chiuso"]
                 and not s["lui_att_aperto"] and s["io_passa_aperto"] and not s["lui_passa_aperto"]))
    casi.append(("negativa: senza log niente situazioni", all(v is None for v in situazioni(None, 1).values())))
    casi.append(("negativa: le righe senza stato del gioco non contano", leggi(["niente", "{rotto"]) == dict(attacchi=[], fine=[])))
    # dagli archivi: un archivio finto con due partite, ritagliate per matchId; guardato una volta sola
    import tempfile
    global LOGDIR
    vecchio = LOGDIR
    LOGDIR = tempfile.mkdtemp()
    try:
        a, b = "11111111-1111-1111-1111-111111111111", "22222222-2222-2222-2222-222222222222"
        testo = "\n".join([f'Connecting to matchId {a}'] + righe + [f'"matchId": "{a}" fine', f'Connecting to matchId {b}', "niente di utile", f'"matchId": "{b}"'])
        with open(os.path.join(LOGDIR, "2026-11-01_Player.log"), "w", encoding="utf-8") as h:
            h.write(testo)
        dati, letti = {}, {}
        n1 = dagli_archivi(dati, letti, None)
        casi.append(("dagli archivi: la partita col gioco ritagliata e letta, quella vuota no", n1 == 1 and dati[a]["attacchi"] == [[3, 1, 2, 2], [4, 2, 0, 3]] and b not in dati))
        casi.append(("negativa: un archivio gia' guardato non si rilegge", dagli_archivi(dati, letti, None) == 0 and "2026-11-01_Player.log" in letti))
    finally:
        LOGDIR = vecchio
    for n, ok in casi:
        print(("ok    " if ok else "ROSSO ") + n)
    print(f"{sum(1 for _n, ok in casi if ok)}/{len(casi)}")
    return all(ok for _n, ok in casi)


if __name__ == "__main__":
    if "--prova" in sys.argv:
        sys.exit(0 if prova() else 1)
    import time
    t0 = time.time()
    d = tutti()
    print(len(d), "partite,", round(time.time() - t0, 1), "s")
