"""Le tue partite lette dal Player.log, non da Untapped (Autore, 9 nov 2026: «io vedo che gioco i mazzi default di arena ma
non scarica i dati … è una vergogna, visto che sappiamo che l'app serve a questo», poi «ma le devi salvare tu no untapped»).

Untapped riceve le partite solo dal suo programma, Untapped.gg Companion: se non e' acceso non le ha (il 9 nov 2026 l'ultima
era del 6 nov alle 12:58, e le 12 partite di quel giorno mancavano). Qui le legge l'app, da ogni log di Arena che c'e' sul PC:
Player.log, Player-prev.log e le copie in Log_Arena. Per ogni partita:
- matchId, inizio (il timestamp del messaggio di Arena), evento (eventId del posto riservato), avversario;
- il mazzo: l'ultimo scelto per quell'evento prima della partita, dalla copia del corso («CourseDeckSummary» delle risposte
  sui corsi: nei Dual Color Precons Arena fa giocare una copia del mazzo, col suo id e il nome «?=?Loc/Decks/Precon/...») o
  dalla richiesta EventSetDeckV3 (le code col mazzo scelto da te);
  contro Sparky dalla richiesta EventAiBotMatch (deckId);
- l'esito della partita intera (finalMatchResult, scope MatchScope_Match), chi comincia (activePlayer del turno 1), i turni;
- dal 10 nov 2026 (Autore: «Si, passa al log»: quello che prima veniva solo da Untapped) anche: il mazzo giocato nella prima partita (il deckMessage del
  ConnectResp, poco prima della riga «Playing»: `carte`, `side`, `cmd` in grpId), le mani viste a ogni richiesta di mulligan prima del turno 1 (`mani`: l'ultima
  e' quella tenuta, prima di mettere le carte in fondo, come player_opening_hands di Untapped; lo stato del gioco si segue dall'inizio, perche' la richiesta non
  porta la mano), le carte dell'avversario viste fuori da grimorio e mano (`sue`, grpId), e il rango. Arena scrive il rango quando lo chiede al server
  (RankGetCombinedRankInfo: all'accesso e a volte dopo una partita, 1.677 risposte nei log al 10 nov 2026): `rango_prima` e' l'ultima risposta prima della partita,
  `rango_dopo` la prima dopo (entro 3 ore) in cui le partite classificate del costruito o del limited sono cresciute, cioe' quella che conta questa partita; se non
  c'e', resta None (su 51 partite classificate confrontate con Untapped: 13 uguali, nessuna diversa, 38 senza risposta). I campi che Arena omette (la classe a
  inizio stagione) restano None.
Ogni log si legge una volta: i risultati stanno in Log_Arena/partite_log.json per nome, misura e data del file.
Un profilo per ogni account di Arena (10 nov 2026, sessione Magic 12): ogni partita porta «conto», l'account che l'ha giocata, cioe' l'ultimo accesso ad Arena
scritto nel log prima di lei (account.conto_a); il tuo posto e' quello con quell'userId. Le risposte sul rango portano anche loro l'account. La copia tiene le
partite di tutti gli account e partite() le filtra per l'account mostrato (account.attivo); con All accounts le da' tutte. Nell'app di Autore non si filtra
niente: c'e' solo il suo account, come prima.

    py -I -X utf8 Companion/App/Comune/partite_log.py            le ultime 15 partite
    py -I -X utf8 Companion/App/Comune/partite_log.py --prova    un log finto: mazzo dal corso e dalla coda, vinta e persa, chi comincia, doppioni
"""
import os, sys
_casa = os.path.dirname(os.path.abspath(__file__))      # si sale fino a percorsi.py, che mette nel sys.path tutte le cartelle del Companion
while not os.path.isfile(os.path.join(_casa, "percorsi.py")):
    _casa = os.path.dirname(_casa)
if _casa not in sys.path:
    sys.path.insert(0, _casa)
import percorsi  # noqa: E402
import piattaforma  # noqa: E402  (i percorsi di Arena su Windows e su Mac)
import datetime  # noqa: E402
import glob  # noqa: E402
import json  # noqa: E402
import re  # noqa: E402
import threading  # noqa: E402

LOGDIR = os.path.join(percorsi.ROOT, "Log_Arena")
ARENA = piattaforma.cartella_arena()
CACHE = os.path.join(LOGDIR, "partite_log.json")
import account as _ACC  # noqa: E402
IO = tuple(x for x in (_ACC.account()["id"], _ACC.account()["nome"]) if x)      # l'account di Arena e il nome in gioco (account.py: Autore, o chi usa l'app pubblica):
# il ripiego quando nel log non c'e' un accesso prima della partita
VERSIONE = 4        # si alza quando cambia la lettura: le copie vecchie si rileggono (3: mazzo, mani, carte sue; 4: ranghi interi; 10 nov 2026)

RX_CORSO = re.compile(rb'"CourseDeckSummary":\{"DeckId":"([0-9a-f-]{36})","Name":"((?:[^"\\]|\\.)*)"')
RX_EVENTO_CORSO = re.compile(rb'"InternalEventName":"([^"]+)"')
RX_SETDECK = re.compile(rb'EventSetDeckV\d \{"id":"[^"]*","request":"\{\\"EventName\\":\\"([^\\"]+)\\",\\"Summary\\":\{\\"DeckId\\":\\"([0-9a-f-]{36})\\"(.{0,400}?)\\"Name\\":\\"((?:[^\\"]|\\\\.)*)\\"')
RX_BOT = re.compile(rb'EventAiBotMatch \{"id":"[^"]*","request":"\{\\"deckId\\":\\"([0-9a-f-]{36})\\"')
RX_STANZA = re.compile(rb'^\{[^\n]*"MatchGameRoomStateType_(Playing|MatchCompleted)"[^\n]*$', re.M)
RX_TURNO = re.compile(rb'"turnInfo": *\{([^{}]*)\}')
RX_NUM = {k: re.compile(rb'"' + k.encode() + rb'": *(\d+)') for k in ("turnNumber", "activePlayer")}
RX_GRE = re.compile(rb'^\{ "transactionId"[^\n]*"greToClientEvent"[^\n]*$', re.M)
RX_DECK = re.compile(rb'"deckMessage": \{ "deckCards": \[([0-9, ]*)\](?:, "sideboardCards": \[([0-9, ]*)\])?(?:, "commandZoneGRPIds": \[([0-9, ]*)\])?')
RX_RANGO = re.compile(rb'(\d{2})/(\d{2})/(\d{4}) (\d{2}):(\d{2}):(\d{2})\s*<== RankGetCombinedRankInfo\([^)]*\)\s*(\{[^\n]*\})')
PUBBLICHE = ("ZoneType_Battlefield", "ZoneType_Graveyard", "ZoneType_Exile", "ZoneType_Stack", "ZoneType_Revealed", "ZoneType_Command")
_LOCK = threading.Lock()


def numeri(b):
    return [int(x) for x in re.findall(rb"\d+", b or b"")]


def dettagli(data, da, a, seat):
    """Fra da e a (la partita): il mazzo della prima partita, le mani a ogni mulligan prima del turno 1, le carte sue viste. -> dict(carte, side, cmd, mani, sue)."""
    out = dict(carte=None, side=None, cmd=None, mani=[], sue=[])
    m = RX_DECK.search(data, da, a)
    if m:
        out["carte"], out["side"], out["cmd"] = numeri(m.group(1)), numeri(m.group(2)), numeri(m.group(3))
    oggetti, zone, sue, iniziata = {}, {}, set(), False
    for r_ in RX_GRE.finditer(data, m.start() if m else da, a):
        riga = r_.group(0)
        if b'"gameStateMessage"' not in riga and b"MulliganReq" not in riga:
            continue
        try:
            r = json.loads(riga)
        except ValueError:
            continue
        for msg in (r.get("greToClientEvent") or {}).get("greToClientMessages") or []:
            gs = msg.get("gameStateMessage")
            if gs:
                for z in gs.get("zones") or []:
                    zone[z.get("zoneId")] = (z.get("type"), z.get("ownerSeatId"), z.get("objectInstanceIds") or [])
                for o in gs.get("gameObjects") or []:
                    oggetti[o.get("instanceId")] = o.get("grpId")
                    if o.get("ownerSeatId") not in (None, seat) and o.get("type") == "GameObjectType_Card" and zone.get(o.get("zoneId"), ("",))[0] in PUBBLICHE and o.get("grpId"):
                        sue.add(o["grpId"])
                if ((gs.get("turnInfo") or {}).get("turnNumber") or 0) >= 1:
                    iniziata = True
            if msg.get("type") == "GREMessageType_MulliganReq" and seat in (msg.get("systemSeatIds") or []) and not iniziata:
                out["mani"].append([oggetti[i] for t, own, ids in zone.values() if t == "ZoneType_Hand" and own == seat for i in ids if oggetti.get(i)])
    out["sue"] = sorted(sue)
    return out


def ranghi(data, acc=None):
    """Le risposte sul rango: [(ms, classe costruito, livello, partite classificate costruito, classe limited, livello, partite limited, account)]. L'ora e' quella
    locale del log (gg/mm/aaaa). Un campo che Arena omette resta None (la classe), 0 (i conti). L'account e' l'ultimo accesso prima della risposta."""
    out = []
    acc = _ACC.accessi(data) if acc is None else acc
    for m in RX_RANGO.finditer(data):
        g, me, an, o, mi, se = (int(x) for x in m.groups()[:6])
        try:
            ts = int(datetime.datetime(an, me, g, o, mi, se).timestamp() * 1000)
            d = json.loads(m.group(7))
        except ValueError:
            continue
        out.append((ts, d.get("constructedClass"), d.get("constructedLevel"), d.get("constructedMatchesWon", 0) + d.get("constructedMatchesLost", 0),
                    d.get("limitedClass"), d.get("limitedLevel"), d.get("limitedMatchesWon", 0) + d.get("limitedMatchesLost", 0), _ACC.conto_a(acc, m.start())))
    return out


def leggi(data, acc=None):
    """Le partite di un log (bytes) e i mazzi visti: -> (partite, {id mazzo: nome}). Una partita senza la fine resta con vinta None. Ogni partita e' dell'account
    dell'ultimo accesso prima di lei (acc: account.accessi del log); senza accessi nel log, di chi ha l'id o il nome in IO."""
    acc = _ACC.accessi(data) if acc is None else acc
    eventi = []          # (posizione, evento, id mazzo, nome)
    nomi = {}
    for m in RX_CORSO.finditer(data):
        ev = None
        for e in RX_EVENTO_CORSO.finditer(data, max(0, m.start() - 600), m.start()):
            ev = e.group(1).decode()
        nome = m.group(2).decode("utf-8", "replace")
        nomi[m.group(1).decode()] = nome
        if ev:
            eventi.append((m.start(), ev, m.group(1).decode(), nome))
    for m in RX_SETDECK.finditer(data):
        nome = m.group(4).decode("utf-8", "replace")
        nomi.setdefault(m.group(2).decode(), nome)
        eventi.append((m.start(), m.group(1).decode(), m.group(2).decode(), nome))
    for m in RX_BOT.finditer(data):          # contro Sparky: il mazzo sta nella richiesta della partita, senza il nome dell'evento
        eventi.append((m.start(), "AIBotMatch*", m.group(1).decode(), None))
    eventi.sort()
    partite = {}
    for m in RX_STANZA.finditer(data):
        try:
            r = json.loads(m.group(0))
        except ValueError:
            continue
        st = r.get("matchGameRoomStateChangedEvent", {}).get("gameRoomInfo", {})
        cfg = st.get("gameRoomConfig", {})
        mid = cfg.get("matchId")
        posti = cfg.get("reservedPlayers") or []
        chi = _ACC.conto_a(acc, m.start())
        io = next((p for p in posti if chi and p.get("userId") == chi), None) or next((p for p in posti if p.get("userId") in IO or p.get("playerName") in IO), None)
        if not mid or not io:
            continue
        p = partite.setdefault(mid, dict(matchId=mid, inizio=int(r.get("timestamp") or 0), pos=m.start(), fine_pos=None, evento=io.get("eventId") or "",
                                         seat=io.get("systemSeatId"), team=io.get("teamId"), avversario=next((x.get("playerName") for x in posti if x is not io), ""),
                                         bot=any(x.get("isBotPlayer") for x in posti), vinta=None, motivo=None, conto=io.get("userId") or chi))
        if m.group(1) == b"MatchCompleted":
            p["fine_pos"] = m.end()
            for x in (st.get("finalMatchResult") or {}).get("resultList") or []:
                if x.get("scope") == "MatchScope_Match":
                    p["vinta"] = x.get("winningTeamId") == p["team"] if x.get("winningTeamId") is not None else None
                    p["motivo"] = x.get("reason")
    out = []
    fini = sorted(p_["fine_pos"] for p_ in partite.values() if p_["fine_pos"])
    for p in partite.values():
        # il mazzo: l'ultimo scelto per quell'evento prima della partita
        scelti = [e for e in eventi if e[0] < p["pos"] and (e[1] == p["evento"] or (e[1] == "AIBotMatch*" and p["evento"].startswith("AIBotMatch")))]
        p["mazzo"], p["nome_mazzo"] = (scelti[-1][2], scelti[-1][3]) if scelti else (None, None)
        # chi comincia e i turni, fra l'inizio e la fine della partita
        primo, turni = None, 0
        for t in RX_TURNO.finditer(data, p["pos"], p["fine_pos"] or len(data)):
            n = RX_NUM["turnNumber"].search(t.group(1)); a = RX_NUM["activePlayer"].search(t.group(1))
            if n:
                turni = max(turni, int(n.group(1)))
                if int(n.group(1)) == 1 and a and primo is None:
                    primo = int(a.group(1))
        p["inizia"], p["turni"] = primo, turni or None
        da = max([f for f in fini if f <= p["pos"]] + [p["pos"] - 60000, 0])     # il mazzo sta poco prima della riga «Playing», dopo la fine della partita di prima
        p.update(dettagli(data, da, p["fine_pos"] or len(data), p["seat"]))
        p["finita"] = p.pop("fine_pos") is not None
        del p["pos"]
        out.append(p)
    return out, nomi


def leggi_tutto(data):
    """-> (partite, nomi, ranghi, accessi [(id, nome)]) di un log."""
    acc = _ACC.accessi(data)
    pp, nn = leggi(data, acc)
    return pp, nn, ranghi(data, acc), sorted({(i, n) for _p, i, n in acc})


def file_log():
    """Tutti i log di Arena sul PC, dal piu' vecchio: le copie in Log_Arena, poi Player-prev.log e Player.log."""
    archiviati = sorted(glob.glob(os.path.join(LOGDIR, "*.log")))
    archiviati = [f for f in archiviati if re.match(r"\d{4}-\d{2}-\d{2}_\d{4}_Player", os.path.basename(f))]
    return archiviati + [f for f in (os.path.join(ARENA, "Player-prev.log"), os.path.join(ARENA, "Player.log")) if os.path.exists(f)]


def partite(files=None, cache=CACHE, conto=False):
    """-> (partite, nomi dei mazzi): ogni partita una volta (per matchId: vince la lettura finita), dalla piu' vecchia. conto: l'account (False: quello che l'app
    mostra; None o account.TUTTI: tutti). Nell'app di Autore tutte, come prima del 10 nov 2026."""
    if conto is False:
        conto = _ACC.attivo() if _ACC.PUBBLICA else None
    if conto == _ACC.TUTTI:
        conto = None
    with _LOCK:
        try:
            c = json.load(open(cache, encoding="utf-8")) if cache else {}
        except (OSError, ValueError):
            c = {}
        if c.get("versione") != VERSIONE:
            c = {"versione": VERSIONE, "file": {}}
        cambiata = False
        per_mid, nomi, foto, visti = {}, {}, set(), set()
        for f in files if files is not None else file_log():
            try:
                st = os.stat(f)
            except OSError:
                continue
            firma = f"{st.st_size}:{int(st.st_mtime)}"
            k = os.path.basename(f) if os.path.dirname(f) == LOGDIR else f
            v = c["file"].get(k)
            if not v or v.get("firma") != firma or (_ACC.PUBBLICA and "accessi" not in v):     # l'app pubblica vuole l'account di ogni partita (10 nov 2026)
                try:
                    with open(f, "rb") as fh:
                        pp, nn, rr, aa = leggi_tutto(fh.read())
                except OSError:
                    continue
                v = c["file"][k] = dict(firma=firma, partite=pp, nomi=nn, ranghi=rr, accessi=aa)
                cambiata = True
            visti.update(tuple(x) for x in v.get("accessi") or ())
            nomi.update(v["nomi"])
            foto.update(tuple(x) for x in v.get("ranghi") or ())
            for p in v["partite"]:
                q = per_mid.get(p["matchId"])
                if q is None or (p["finita"] and not q["finita"]) or (p["mazzo"] and not q["mazzo"]):
                    per_mid[p["matchId"]] = p
        if cambiata and cache:
            tmp = cache + ".tmp"
            json.dump(c, open(tmp, "w", encoding="utf-8"))
            os.replace(tmp, cache)
    _ACC.registra(sorted(visti))        # la tendina degli account conosce anche quelli dei log archiviati
    foto = sorted((tuple(x[:7]) + (x[7] if len(x) > 7 else None,) for x in foto), key=lambda x: x[:7])
    out = sorted((p for p in per_mid.values() if conto is None or p.get("conto") == conto), key=lambda p: p["inizio"])
    for p in out:       # il rango prima della partita e quello che conta la partita, da qualunque log (nell'app pubblica dello stesso account)
        lim = bool(re.search(r"Draft|Sealed|Cube", p["evento"]))
        prima = [x for x in foto if x[0] <= p["inizio"] and (not _ACC.PUBBLICA or x[7] == p.get("conto"))]
        p["rango_prima"] = list(prima[-1][1:7]) if prima else None
        k = 6 if lim else 3                  # il conto delle partite classificate del limited o del costruito
        base = prima[-1][k] if prima else None
        dopo = next((x for x in foto if p["inizio"] < x[0] < p["inizio"] + 3 * 3600 * 1000 and base is not None and x[k] > base
                     and (not _ACC.PUBBLICA or x[7] == p.get("conto"))), None)
        p["rango_dopo"] = list(dopo[1:7]) if dopo else None
    return out, nomi


def prova_conti():
    """Due account di Arena sullo stesso PC (10 nov 2026, Magic 12): ogni partita al suo, All accounts le somma, il rango dell'uno non va all'altro."""
    import tempfile
    acc = lambda i, n: '{ "authenticateResponse": { "clientId": "%s", "sessionId": "s", "screenName":"%s" } }\n' % (i, n)
    A, B = "AAAA1111BBBB2222CCCC3333DD", "ZZZZ1111BBBB2222CCCC3333DD"
    posto = '{"userId": "%s", "playerName": "%s", "systemSeatId": %d, "teamId": %d, "eventId": "Play"}'

    def partita(mid, ts, io, nome, vince):
        posti = f'[{posto % (io, nome, 1, 1)}, {posto % ("X", "Lui", 2, 2)}]'
        testa = f'{{"transactionId": "t", "timestamp": "{ts}", "matchGameRoomStateChangedEvent": {{"gameRoomInfo": {{"gameRoomConfig": {{"reservedPlayers": {posti}, "matchId": "{mid}"}}, '
        return (testa + '"stateType": "MatchGameRoomStateType_Playing"}}}\n'
                + testa + f'"stateType": "MatchGameRoomStateType_MatchCompleted", "finalMatchResult": {{"resultList": [{{"scope": "MatchScope_Match", "winningTeamId": {vince}}}]}}}}}}}}\n')
    rango = lambda ts, classe, n: '[UnityCrossThreadLogger]%s\n<== RankGetCombinedRankInfo(x)\n{"constructedClass":"%s","constructedLevel":1,"constructedMatchesWon":%d,"limitedClass":"Bronze","limitedLevel":1,"limitedMatchesWon":0}\n' % (
        datetime.datetime.fromtimestamp(ts / 1000).strftime("%d/%m/%Y %H:%M:%S"), classe, n)
    t0 = 1794224501827
    uno = (acc(A, "Prima") + rango(t0 - 60000, "Gold", 5) + partita("m-a1", t0, A, "Prima", 1) + partita("m-a2", t0 + 10 ** 6, A, "Prima", 2)
           + acc(B, "Seconda") + rango(t0 + 2 * 10 ** 6, "Bronze", 1) + partita("m-b1", t0 + 3 * 10 ** 6, B, "Seconda", 1))
    due = acc(B, "Seconda") + partita("m-b2", t0 + 5 * 10 ** 6, B, "Seconda", 2)
    d = tempfile.mkdtemp()
    f1, f2 = os.path.join(d, "uno.log"), os.path.join(d, "due.log")
    open(f1, "w", encoding="utf-8").write(uno); open(f2, "w", encoding="utf-8").write(due)
    vero = _ACC.PUBBLICA
    try:
        _ACC.PUBBLICA = True
        reg = []
        vero_reg, _ACC.registra = _ACC.registra, reg.extend
        c = os.path.join(d, "c.json")
        pa = {p["matchId"]: p for p in partite([f1, f2], cache=c, conto=A)[0]}
        pb = {p["matchId"]: p for p in partite([f1, f2], cache=c, conto=B)[0]}
        pt = partite([f1, f2], cache=c, conto=_ACC.TUTTI)[0]
        casi = [("due account: ogni partita al suo", sorted(pa) == ["m-a1", "m-a2"] and sorted(pb) == ["m-b1", "m-b2"]),
                ("All accounts le somma", len(pt) == 4 and sum(1 for p in pt if p["vinta"]) == 2),
                ("il rango di un account non passa all'altro", pa["m-a1"]["rango_prima"][0] == "Gold" and pb["m-b1"]["rango_prima"][0] == "Bronze"),
                ("gli account dei log vanno alla tendina", sorted(set(reg)) == [(A, "Prima"), (B, "Seconda")]),
                ("negativa: senza il filtro per account (il codice di prima) le partite di A stanno con quelle di B",
                 {p["matchId"] for p in partite([f1, f2], cache=c, conto=None)[0]} > set(pb))]
        _ACC.registra = vero_reg
    finally:
        _ACC.PUBBLICA = vero
    return casi


def quando(p):
    return datetime.datetime.fromtimestamp(p["inizio"] / 1000)


def prova():
    import tempfile
    io = '{"userId": "AAAAAAAAAAAAAAAAAAAAAAAAAA", "playerName": "Player1", "systemSeatId": %d, "teamId": %d, "eventId": "%s"}'
    lui = '{"userId": "X", "playerName": "Lui", "systemSeatId": %d, "teamId": %d, "eventId": "%s"}'

    def stanza(mid, ev, tipo, ts, mio=1, vince=None):
        posti = f'[{io % (mio, mio, ev)}, {lui % (3 - mio, 3 - mio, ev)}]'
        fine = f', "finalMatchResult": {{"matchId": "{mid}", "resultList": [{{"scope": "MatchScope_Game", "winningTeamId": 2}}, {{"scope": "MatchScope_Match", "result": "ResultType_WinLoss", "winningTeamId": {vince}, "reason": "ResultReason_Game"}}]}}' if vince else ""
        return (f'{{"transactionId": "t", "timestamp": "{ts}", "matchGameRoomStateChangedEvent": {{"gameRoomInfo": {{"gameRoomConfig": {{"reservedPlayers": {posti}, '
                f'"matchId": "{mid}"}}, "stateType": "MatchGameRoomStateType_{tipo}"{fine}}}}}}}\n')
    turno = lambda n, a: f'{{"greToClientEvent": {{"x": [{{"gameStateMessage": {{"turnInfo": {{ "phase": "Phase_Main1", "turnNumber": {n}, "activePlayer": {a} }}}}}}]}}}}\n'
    e_ = "e" * 8 + "-5555-5555-5555-555555555555"
    a, b, c_ = "a" * 8 + "-1111-1111-1111-111111111111", "b" * 8 + "-2222-2222-2222-222222222222", "c" * 8 + "-3333-3333-3333-333333333333"
    d1, d2 = "d1d1d1d1-0000-0000-0000-000000000001", "d2d2d2d2-0000-0000-0000-000000000002"
    log = ('{"Courses":[{"CourseId":"x","InternalEventName":"DualColorPrecons","CurrentModule":"CreateMatch","ModulePayload":"","CourseDeckSummary":{"DeckId":"%s","Name":"?=?Loc/Decks/Precon/Precon_EPPFDN_BW"}}]}\n' % d1
           + stanza(a, "DualColorPrecons", "Playing", 1794224501827) + turno(1, 2) + turno(2, 1) + turno(7, 2)
           + stanza(a, "DualColorPrecons", "MatchCompleted", 1794224901827, vince=1)
           + '[UnityCrossThreadLogger]==> EventSetDeckV3 {"id":"z","request":"{\\"EventName\\":\\"Play\\",\\"Summary\\":{\\"DeckId\\":\\"%s\\",\\"Mana\\":\\"\\",\\"Name\\":\\"Mono Red\\",\\"Attributes\\":[]}}"}\n' % d2
           + stanza(b, "Play", "Playing", 1794225501827, mio=2) + turno(1, 2) + turno(4, 1)
           + stanza(b, "Play", "MatchCompleted", 1794225801827, mio=2, vince=1)
           + stanza(c_, "Play", "Playing", 1794226501827)
           + '[UnityCrossThreadLogger]==> EventAiBotMatch {"id":"q","request":"{\\"deckId\\":\\"%s\\",\\"botDeckId\\":\\"x\\",\\"botMatchType\\":1}"}\n' % d1
           + stanza(e_, "AIBotMatch_Rebalanced", "Playing", 1794227501827) + stanza(e_, "AIBotMatch_Rebalanced", "MatchCompleted", 1794227801827, vince=2))
    gre = lambda seat, corpo: '{ "transactionId": "g", "timestamp": "1", "greToClientEvent": { "greToClientMessages": [ %s ] } }\n' % corpo
    gs = lambda zone, ogg, turno=0: '{ "type": "GREMessageType_GameStateMessage", "systemSeatIds": [ 2 ], "gameStateMessage": { "type": "GameStateType_Full", "zones": [ %s ], "gameObjects": [ %s ]%s } }' % (
        zone, ogg, (', "turnInfo": { "turnNumber": %d }' % turno) if turno else "")
    zona = lambda zid, tipo, own, ids: '{ "zoneId": %d, "type": "%s", "ownerSeatId": %d, "objectInstanceIds": [ %s ] }' % (zid, tipo, own, ", ".join(map(str, ids)))
    ogg = lambda iid, grp, own, zid: '{ "instanceId": %d, "grpId": %d, "type": "GameObjectType_Card", "zoneId": %d, "ownerSeatId": %d }' % (iid, grp, zid, own)
    mull = '{ "type": "GREMessageType_MulliganReq", "systemSeatIds": [ 2 ] }'
    rango = '[UnityCrossThreadLogger]%s\n<== RankGetCombinedRankInfo(x)\n{"constructedSeasonOrdinal":95,"constructedClass":"%s","constructedLevel":%d,"constructedMatchesWon":%d,"limitedSeasonOrdinal":95,"limitedClass":"Bronze","limitedLevel":2,"limitedMatchesWon":0}\n'
    pezzo_b = ('{ "greToClientEvent": { "greToClientMessages": [ { "type": "GREMessageType_ConnectResp", "connectResp": { "deckMessage": { "deckCards": [ 501, 501, 502 ], "sideboardCards": [ 503 ] } } } ] } }\n'
               + gre(2, gs(zona(31, "ZoneType_Hand", 2, [1, 2]) + ", " + zona(28, "ZoneType_Battlefield", 1, [9]), ogg(1, 501, 2, 31) + ", " + ogg(2, 502, 2, 31) + ", " + ogg(9, 777, 1, 28)) + ", " + mull)
               + gre(2, gs(zona(31, "ZoneType_Hand", 2, [3]), ogg(3, 503, 2, 31)) + ", " + mull)
               + gre(2, gs(zona(31, "ZoneType_Hand", 2, [4]), ogg(4, 504, 2, 31), turno=1) + ", " + mull))       # dopo il turno 1 non conta
    log_r = log.replace(stanza(b, "Play", "Playing", 1794225501827, mio=2), pezzo_b + stanza(b, "Play", "Playing", 1794225501827, mio=2))
    log_r = (rango % (datetime.datetime.fromtimestamp(1794225501.827 - 3600).strftime("%d/%m/%Y %H:%M:%S"), "Silver", 3, 1)) + log_r + (rango % (datetime.datetime.fromtimestamp(1794225501.827 + 600).strftime("%d/%m/%Y %H:%M:%S"), "Gold", 4, 2))
    log_s = (rango % (datetime.datetime.fromtimestamp(1794225501.827 - 3600).strftime("%d/%m/%Y %H:%M:%S"), "Silver", 3, 1)) + log + (rango % (datetime.datetime.fromtimestamp(1794225501.827 + 600).strftime("%d/%m/%Y %H:%M:%S"), "Gold", 4, 1))      # dopo, nessuna partita in piu': non conta
    pr, _n, rr, _a = leggi_tutto(log_r.encode())
    q = next(x for x in pr if x["matchId"] == b)
    d0 = tempfile.mkdtemp()
    open(os.path.join(d0, "r.log"), "w", encoding="utf-8").write(log_r)
    pq = {x["matchId"]: x for x in partite([os.path.join(d0, "r.log")], cache=None)[0]}
    open(os.path.join(d0, "s.log"), "w", encoding="utf-8").write(log_s)
    ps = {x["matchId"]: x for x in partite([os.path.join(d0, "s.log")], cache=None)[0]}
    d = tempfile.mkdtemp()
    f1, f2 = os.path.join(d, "uno.log"), os.path.join(d, "due.log")
    open(f1, "w", encoding="utf-8").write(log)
    open(f2, "w", encoding="utf-8").write(log)       # lo stesso log copiato: le partite non si contano due volte
    pp, nomi = partite([f1, f2], cache=os.path.join(d, "c.json"))
    per = {p["matchId"]: p for p in pp}
    casi = [("quattro partite, nessun doppione", len(pp) == 4),
            ("contro Sparky il mazzo dalla richiesta della partita", per[e_]["mazzo"] == d1 and per[e_]["vinta"] is False),
            ("il mazzo dal corso dei Dual Color Precons", per[a]["mazzo"] == d1 and per[a]["nome_mazzo"].endswith("Precon_EPPFDN_BW")),
            ("vinta: la partita intera, non il primo game", per[a]["vinta"] is True),
            ("comincia lui (activePlayer 2 al turno 1), 7 turni", per[a]["inizia"] == 2 and per[a]["seat"] == 1 and per[a]["turni"] == 7),
            ("il mazzo dalla coda (EventSetDeckV3)", per[b]["mazzo"] == d2 and per[b]["nome_mazzo"] == "Mono Red"),
            ("persa col posto 2", per[b]["vinta"] is False and per[b]["seat"] == 2 and per[b]["inizia"] == 2),
            ("la partita senza fine resta senza esito", per[c_]["vinta"] is None and not per[c_]["finita"]),
            ("i nomi dei mazzi", nomi.get(d1, "").endswith("BW") and nomi.get(d2) == "Mono Red"),
            ("la copia si usa al secondo giro", partite([f1, f2], cache=os.path.join(d, "c.json"))[0] == pp)]
    casi += [("il mazzo dal deckMessage, con la sideboard", q["carte"] == [501, 501, 502] and q["side"] == [503]),
             ("le mani a ogni mulligan, fino al turno 1", q["mani"] == [[501, 502], [503]]),
             ("le carte sue viste in campo", q["sue"] == [777]),
             ("il mazzo di una partita non passa a quella prima (negativa)", next(x for x in pr if x["matchId"] == a)["carte"] is None),
             ("le risposte sul rango", [x[1:4] for x in rr] == [("Silver", 3, 1), ("Gold", 4, 2)]),
             ("senza accessi nel log la partita e' di chi ha l'id in IO", q["conto"] == "AAAAAAAAAAAAAAAAAAAAAAAAAA"),
             ("il rango prima e quello che conta la partita", pq[b]["rango_prima"][:2] == ["Silver", 3] and pq[b]["rango_dopo"][:2] == ["Gold", 4]),
             ("negativa: una risposta senza partite classificate in piu' non e' il rango dopo", ps[b]["rango_dopo"] is None and ps[b]["rango_prima"][:2] == ["Silver", 3])]
    casi += prova_conti()
    # la prova negativa: senza il corso il mazzo non si inventa
    pp2, _ = leggi(log.split("\n", 1)[1].encode())
    casi.append(("senza il corso il mazzo non si inventa (prova negativa)", next(p for p in pp2 if p["matchId"] == a)["mazzo"] is None))
    for n, ok in casi:
        print(("  ok    " if ok else "  ROSSO ") + n)
    print(f"{sum(ok for _n, ok in casi)}/{len(casi)}")
    return 0 if all(ok for _n, ok in casi) else 1


if __name__ == "__main__":
    if "--prova" in sys.argv:
        sys.exit(prova())
    import time
    t = time.time()
    pp, nomi = partite()
    print(f"{len(pp)} partite in {time.time() - t:.1f} s")
    for p in pp[-15:]:
        print(quando(p).strftime("%d/%m %H:%M"), p["evento"], (nomi.get(p["mazzo"]) or p["mazzo"] or "?")[:40], p["avversario"],
              {True: "vinta", False: "persa", None: "?"}[p["vinta"]], "turni", p["turni"], "comincia", "tu" if p["inizia"] == p["seat"] else "lui" if p["inizia"] else "?")
