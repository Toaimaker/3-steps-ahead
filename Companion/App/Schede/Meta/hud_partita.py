"""La partita in corso letta dal Player.log, per l'HUD del mazzo avversario (sessione Magic 15, 12 nov 2026).

Autore, 12 nov 2026: «e se schedassimo i mazzi e non i giocatori? come la celebre app per il poker che ha un hud per i giocatori, se noi facessimo la
stessa cosa per i mazzi?». Questo modulo legge solo il tavolo della partita di adesso e lo tiene in memoria: niente si scrive su disco.

Cosa legge (dal Player.log, a pezzi: si legge solo quello che Arena aggiunge):
- la partita (matchId), l'evento, il tuo posto (l'account che ha fatto l'ultimo accesso: authenticateResponse; se manca, account.account()), il tuo mazzo (l'ultimo
  scelto per quell'evento: EventSetDeckV3 o la copia del corso, come partite_log);
- il turno, chi e' di turno, chi ha cominciato;
- le carte sue viste in una zona pubblica (campo, cimitero, esilio, pila, rivelate), nell'ordine in cui le vedi, e le sue terre in campo, stappate e no.
- Il nome dell'avversario e il suo id **non si tengono**: Arena li scrive nel log, qui non entrano nello stato (Termini d'uso di Wizards §2.2, Codice di condotta
  §2, GDPR: si scheda il mazzo, mai il giocatore).

    py -I -X utf8 Companion/App/Schede/Meta/hud_partita.py            lo stato della partita in corso (o dell'ultima)
    py -I -X utf8 Companion/App/Schede/Meta/hud_partita.py --prova    un log finto, con le negative
"""
import os, sys
_casa = os.path.dirname(os.path.abspath(__file__))      # si sale fino a percorsi.py, che mette nel sys.path tutte le cartelle del Companion
while not os.path.isfile(os.path.join(_casa, "percorsi.py")):
    _casa = os.path.dirname(_casa)
if _casa not in sys.path:
    sys.path.insert(0, _casa)
import percorsi  # noqa: E402,F401
import json  # noqa: E402
import re  # noqa: E402
import threading  # noqa: E402
import piattaforma  # noqa: E402

PUBBLICHE = ("ZoneType_Battlefield", "ZoneType_Graveyard", "ZoneType_Exile", "ZoneType_Stack", "ZoneType_Revealed", "ZoneType_Command")
COMPETITIVO = re.compile(r"Championship|Qualifier|Arena_?Open|Worlds|Regional|Pro_?Tour|Metropolis|Cup", re.I)     # lo stesso filtro della spalla
RX_AUTH = re.compile(rb'"authenticateResponse": \{ "clientId": "([A-Z0-9]+)"')
RX_CORSO = re.compile(rb'"InternalEventName":"([^"]+)"[^\n]{0,600}?"CourseDeckSummary":\{"DeckId":"[0-9a-f-]{36}","Name":"((?:[^"\\]|\\.)*)"')
RX_SETDECK = re.compile(rb'EventSetDeckV\d \{"id":"[^"]*","request":"\{\\"EventName\\":\\"([^\\"]+)\\",\\"Summary\\":\{\\"DeckId\\":\\"[0-9a-f-]{36}\\"(?:.{0,400}?)\\"Name\\":\\"((?:[^\\"]|\\\\.)*)\\"')
RX_DECK = re.compile(rb'"deckMessage": \{ "deckCards": \[([0-9, ]*)\]')
_NOMI = {}
_LOCK = threading.Lock()


def nome_grp(g):
    """Il nome di una carta dal suo grpId (database di Arena; le due facce col nome davanti)."""
    with _LOCK:
        if not _NOMI:
            import db_carte
            t = db_carte.testi()
            for c in db_carte.carte():
                n = t.get(c.get("titleId"))
                if n and c.get("grpid"):
                    _NOMI[c["grpid"]] = n.split(" // ")[0]
    return _NOMI.get(g)


def nuovo(mid=None):
    return dict(matchId=mid, evento="", seat=None, mazzo=None, turno=0, attivo=None, inizia=None, finita=False, vinta=None, gioco=1,
                sue=[], terre=0, aperte=0, mano_sua=None, mie_fuori={}, grimorio=None, _ogg={}, _zone={}, _visti=set())


class Seguito:
    """Segue un Player.log: aggiorna() legge solo i byte nuovi e rida' lo stato della partita in corso (o dell'ultima, finita=True); None se nel log non c'e'
    una partita. Un log piu' corto di prima (Arena ripartita) si rilegge da capo."""

    def __init__(self, file=None, io=None):
        self.file = file or os.path.join(piattaforma.cartella_arena(), "Player.log")
        self.io = io            # (id, nome) di chi gioca: per le prove; di norma l'ultimo accesso del log, poi l'account dell'app
        self.pos = 0
        self.resto = b""
        self.st = None
        self.chi = None
        self.mazzi = {}         # evento -> nome dell'ultimo mazzo scelto
        self.mio_mazzo = None
        self.lucchetto = getattr(self, "lucchetto", None) or threading.RLock()

    def _io(self):
        if self.io:
            return self.io
        if self.chi:
            return (self.chi, None)
        try:
            import account
            a = account.account()
            return (a.get("id"), a.get("nome"))
        except Exception:      # noqa: BLE001 - senza account: si riconosce il posto dal nome, se c'e'
            return (None, None)

    def aggiorna(self):
        with self.lucchetto:        # la prima lettura gira in un filo, la finestra legge dal suo giro
            return self._aggiorna()

    def _aggiorna(self):
        try:
            n = os.path.getsize(self.file)
        except OSError:
            return self.stato()
        if n < self.pos:
            self.__init__(self.file, self.io)
        if n == self.pos:
            return self.stato()
        with open(self.file, "rb") as f:
            f.seek(self.pos)
            b = f.read(n - self.pos)
        primo = self.pos == 0
        self.pos = n
        if primo:
            self.primo(b)
        else:
            self.leggi(b)
        return self.stato()

    def primo(self, b):
        """La prima lettura di un log intero (decine di MB): accessi e mazzi scelti con le espressioni su tutto il file, i messaggi del gioco solo dall'ultima
        partita (dal suo «Playing», e il tuo mazzo poco prima)."""
        for m in RX_AUTH.finditer(b):
            self.chi = m.group(1).decode()
        scelte = [(m.start(), m.group(1), m.group(2)) for m in RX_CORSO.finditer(b)] + [(m.start(), m.group(1), m.group(2)) for m in RX_SETDECK.finditer(b)]
        for _p, ev, nome in sorted(scelte):
            self.mazzi[ev.decode()] = nome.decode("utf-8", "replace")
        i = b.rfind(b"MatchGameRoomStateType_Playing")
        if i < 0:
            self.resto = b[b.rfind(b"\n") + 1:]
            return
        da = b.rfind(b"\n", 0, i) + 1
        j = b.rfind(b'"deckMessage"', max(0, da - 400000), da)
        if j >= 0:
            self.riga(b[b.rfind(b"\n", 0, j) + 1:b.find(b"\n", j)])
        self.leggi(b[da:])

    def leggi(self, b):
        b = self.resto + b
        fine = b.rfind(b"\n")
        if fine < 0:
            self.resto = b
            return
        self.resto = b[fine + 1:]
        for riga in b[:fine].split(b"\n"):
            self.riga(riga)

    def riga(self, r):
        if b"authenticateResponse" in r:
            m = RX_AUTH.search(r)
            if m:
                self.chi = m.group(1).decode()
            return
        if b"CourseDeckSummary" in r:
            for m in RX_CORSO.finditer(r):
                self.mazzi[m.group(1).decode()] = m.group(2).decode("utf-8", "replace")
            return
        if b"EventSetDeckV" in r:
            m = RX_SETDECK.search(r)
            if m:
                self.mazzi[m.group(1).decode()] = m.group(2).decode("utf-8", "replace")
            return
        if b'"deckMessage"' in r:          # il tuo mazzo della partita (ConnectResp), poco prima della riga «Playing»: serve ai colori nel limited
            m = RX_DECK.search(r)
            if m:
                self.mio_mazzo = [int(x) for x in re.findall(rb"\d+", m.group(1))]
                if self.st is not None and not self.st["finita"]:
                    self.st["mio_mazzo"] = self.mio_mazzo
            return
        if b"matchGameRoomStateChangedEvent" in r:
            self.stanza(r)
            return
        if self.st is not None and b"greToClientEvent" in r and (b"gameStateMessage" in r):
            try:
                d = json.loads(r[r.find(b"{"):])
            except ValueError:
                return
            for msg in (d.get("greToClientEvent") or {}).get("greToClientMessages") or []:
                gs = msg.get("gameStateMessage")
                if gs:
                    self.stato_gioco(gs)

    def stanza(self, r):
        try:
            info = json.loads(r[r.find(b"{"):])["matchGameRoomStateChangedEvent"]["gameRoomInfo"]
        except (ValueError, KeyError, TypeError):
            return
        cfg = info.get("gameRoomConfig") or {}
        mid = cfg.get("matchId")
        if not mid:
            return
        if self.st is None or self.st["matchId"] != mid:
            self.st = nuovo(mid)
            self.st["mio_mazzo"] = self.mio_mazzo
        i, n = self._io()
        posti = cfg.get("reservedPlayers") or []
        io = next((p for p in posti if i and p.get("userId") == i), None) or next((p for p in posti if n and p.get("playerName") == n), None)
        if io:
            self.st["seat"], self.st["team"] = io.get("systemSeatId"), io.get("teamId")
            self.st["evento"] = io.get("eventId") or ""
            self.st["mazzo"] = self.mazzi.get(self.st["evento"])
        if info.get("stateType") == "MatchGameRoomStateType_MatchCompleted":
            self.st["finita"] = True
            for x in (info.get("finalMatchResult") or {}).get("resultList") or []:
                if x.get("scope") == "MatchScope_Match" and x.get("winningTeamId") is not None and self.st.get("team") is not None:
                    self.st["vinta"] = x["winningTeamId"] == self.st["team"]

    def stato_gioco(self, gs):
        s = self.st
        for z in gs.get("zones") or []:
            s["_zone"][z.get("zoneId")] = (z.get("type"), z.get("ownerSeatId"), z.get("objectInstanceIds") or [])
        for o in gs.get("gameObjects") or []:
            s["_ogg"][o.get("instanceId")] = o
        for i in gs.get("diffDeletedInstanceIds") or []:
            s["_ogg"].pop(i, None)
        ti = gs.get("turnInfo") or {}
        if ti.get("turnNumber") and ti["turnNumber"] < s["turno"]:     # il game dopo di un Bo3: tavolo nuovo, le sue carte viste restano (sono nelle sue 75)
            s["turno"], s["inizia"], s["gioco"] = 0, None, s.get("gioco", 1) + 1
            vivi = {o.get("instanceId") for o in gs.get("gameObjects") or []}
            s["_ogg"] = {i: o for i, o in s["_ogg"].items() if i in vivi}
        if ti.get("turnNumber"):
            s["turno"] = max(s["turno"], ti["turnNumber"])
            s["attivo"] = ti.get("activePlayer", s["attivo"])
            if ti["turnNumber"] == 1 and s["inizia"] is None and ti.get("activePlayer"):
                s["inizia"] = ti["activePlayer"]
        if s["seat"] is None:
            return
        zt = {zid: z[0] for zid, z in s["_zone"].items()}
        for iid, o in s["_ogg"].items():
            if o.get("type") != "GameObjectType_Card" or o.get("ownerSeatId") in (None, s["seat"]) or not o.get("grpId"):
                continue
            if zt.get(o.get("zoneId")) in PUBBLICHE and o["grpId"] not in s["_visti"]:
                s["_visti"].add(o["grpId"])
                s["sue"].append(o["grpId"])
        terre = [o for o in s["_ogg"].values() if o.get("type") == "GameObjectType_Card" and zt.get(o.get("zoneId")) == "ZoneType_Battlefield"
                 and o.get("controllerSeatId", o.get("ownerSeatId")) not in (None, s["seat"]) and "CardType_Land" in (o.get("cardTypes") or [])]
        s["terre"] = len(terre)
        s["aperte"] = sum(1 for o in terre if not o.get("isTapped"))
        s["mano_sua"] = next((len(ids) for t, own, ids in s["_zone"].values() if t == "ZoneType_Hand" and own not in (None, s["seat"])), s["mano_sua"])
        # le tue carte fuori dal grimorio (mano, campo, cimitero, esilio, pila: quelle che le zone elencano adesso, cosi' una carta che cambia zona e id non
        # si conta due volte) e quante ne restano nel grimorio: servono al pannello del tuo mazzo
        fuori = {}
        for t, own, ids in s["_zone"].values():
            if t in (None, "ZoneType_Library", "ZoneType_Limbo", "ZoneType_Sideboard"):
                continue
            for i in ids:
                o = s["_ogg"].get(i)
                if o and o.get("type") == "GameObjectType_Card" and o.get("ownerSeatId") == s["seat"] and o.get("grpId"):
                    fuori[o["grpId"]] = fuori.get(o["grpId"], 0) + 1
        s["mie_fuori"] = fuori
        s["grimorio"] = next((len(ids) for t, own, ids in s["_zone"].values() if t == "ZoneType_Library" and own == s["seat"]), s.get("grimorio"))

    def stato(self):
        """Lo stato pubblico: senza le tabelle interne e senza niente dell'avversario oltre alle sue carte e alle sue terre."""
        if self.st is None:
            return None
        s = {k: v for k, v in self.st.items() if not k.startswith("_") and k != "team"}
        s["sue"] = list(s["sue"])
        s["sue_nomi"] = [n for n in (nome_grp(g) for g in s["sue"]) if n]
        s["mio_mazzo_nomi"] = [n for n in (nome_grp(g) for g in s.get("mio_mazzo") or []) if n]
        s["sul_play"] = None if s["inizia"] is None or s["seat"] is None else s["inizia"] == s["seat"]
        s["suo_turno"] = s["attivo"] is not None and s["seat"] is not None and s["attivo"] != s["seat"]
        s["competitivo"] = bool(COMPETITIVO.search(s["evento"] or ""))
        return s


def prova():
    import tempfile
    ME, LUI = "AAAAAAAAAAAAAAAAAAAAAAAAAA", "ZZZZOPPONENTIDZZZZ"
    posti = ('[{"userId": "%s", "playerName": "Io", "systemSeatId": 1, "teamId": 1, "eventId": "%%s"}, {"userId": "%s", "playerName": "NomeDelGiocatore", '
             '"systemSeatId": 2, "teamId": 2, "eventId": "%%s"}]') % (ME, LUI)

    def stanza(mid, ev, tipo, vince=None):
        fine = (', "finalMatchResult": {"resultList": [{"scope": "MatchScope_Match", "winningTeamId": %d}]}' % vince) if vince else ""
        return ('{"timestamp": "1", "matchGameRoomStateChangedEvent": {"gameRoomInfo": {"gameRoomConfig": {"reservedPlayers": %s, "matchId": "%s"}, '
                '"stateType": "MatchGameRoomStateType_%s"%s}}}\n') % (posti % (ev, ev), mid, tipo, fine)

    def gs(zone, ogg, turno=None, attivo=None, cancella=()):
        ti = (', "turnInfo": {"turnNumber": %d, "activePlayer": %d}' % (turno, attivo)) if turno else ""
        canc = (', "diffDeletedInstanceIds": [%s]' % ",".join(map(str, cancella))) if cancella else ""
        return ('{ "transactionId": "g", "greToClientEvent": { "greToClientMessages": [ { "type": "GREMessageType_GameStateMessage", "gameStateMessage": '
                '{ "zones": [ %s ], "gameObjects": [ %s ]%s%s } } ] } }\n') % (zone, ogg, ti, canc)
    zona = lambda zid, tipo, own, ids: '{ "zoneId": %d, "type": "%s", "ownerSeatId": %d, "objectInstanceIds": [ %s ] }' % (zid, tipo, own, ", ".join(map(str, ids)))

    def ogg(iid, grp, own, zid, terra=False, tappata=False):
        return ('{ "instanceId": %d, "grpId": %d, "type": "GameObjectType_Card", "zoneId": %d, "ownerSeatId": %d, "controllerSeatId": %d%s%s }'
                % (iid, grp, zid, own, own, ', "cardTypes": ["CardType_Land"]' if terra else "", ', "isTapped": true' if tappata else ""))
    auth = '[UnityCrossThreadLogger]<== Authenticate {"authenticateResponse": { "clientId": "%s", "sessionId": "s", "screenName":"Io" }}\n' % ME
    setdeck = ('[UnityCrossThreadLogger]==> EventSetDeckV3 {"id":"z","request":"{\\"EventName\\":\\"Ladder\\",\\"Summary\\":{\\"DeckId\\":\\"'
               'd2d2d2d2-0000-0000-0000-000000000002\\",\\"Mana\\":\\"\\",\\"Name\\":\\"UW Bouncer\\",\\"Attributes\\":[]}}"}\n')
    connetti = '{ "greToClientEvent": { "greToClientMessages": [ { "type": "GREMessageType_ConnectResp", "connectResp": { "deckMessage": { "deckCards": [ 801, 801, 802 ] } } } ] } }\n'
    log1 = (auth + setdeck + connetti + stanza("m1", "Ladder", "Playing")
            + gs(zona(10, "ZoneType_Battlefield", 1, [5, 6, 7]) + ", " + zona(11, "ZoneType_Hand", 2, [20, 21, 22]) + ", " + zona(12, "ZoneType_Library", 2, [30]),
                 ogg(5, 900, 2, 10, terra=True) + ", " + ogg(6, 901, 2, 10, terra=True, tappata=True) + ", " + ogg(7, 902, 2, 10) + ", " + ogg(30, 903, 2, 12)
                 + ", " + ogg(40, 904, 1, 10) + ", " + ogg(41, 801, 1, 14) + ", " + ogg(42, 801, 1, 15) + ", " + ogg(43, 802, 1, 15), turno=1, attivo=2)
            + gs(zona(14, "ZoneType_Hand", 1, [41]) + ", " + zona(15, "ZoneType_Library", 1, [42, 43]), ""))
    log2 = (gs(zona(13, "ZoneType_Graveyard", 2, [8]), ogg(8, 905, 2, 13) + ", " + ogg(6, 901, 2, 10, terra=True), turno=3, attivo=1)
            + stanza("m1", "Ladder", "MatchCompleted", vince=1))
    d = tempfile.mkdtemp()
    f = os.path.join(d, "Player.log")
    open(f, "w", encoding="utf-8").write(log1)
    S = Seguito(f)
    S.io = (ME, None)
    a = S.aggiorna()
    casi = [("il tuo posto, l'evento e il tuo mazzo, con le carte", a["seat"] == 1 and a["evento"] == "Ladder" and a["mazzo"] == "UW Bouncer"
             and a["mio_mazzo"] == [801, 801, 802]),
            ("chi comincia: lui (sei sul draw), turno 1", a["inizia"] == 2 and a["sul_play"] is False and a["turno"] == 1),
            ("le sue carte in campo nell'ordine, non quella nel grimorio ne' la tua", a["sue"] == [900, 901, 902]),
            ("le sue terre: 2, una aperta", a["terre"] == 2 and a["aperte"] == 1),
            ("negativa: la sua mano non si vede, solo il numero", a["mano_sua"] == 3 and 20 not in a["sue"]),
            ("le tue carte fuori dal grimorio (la mano) e quante ne restano dentro", a["mie_fuori"] == {801: 1} and a["grimorio"] == 2)]
    with open(f, "a", encoding="utf-8") as fh:
        fh.write(log2)
    b = S.aggiorna()
    casi += [("si leggono solo i byte nuovi: il cimitero si aggiunge in fondo", b["sue"] == [900, 901, 902, 905] and S.pos == os.path.getsize(f)),
             ("la terra stappata torna aperta", b["aperte"] == 2),
             ("la fine: finita e vinta", b["finita"] and b["vinta"] is True)]
    testo = json.dumps(b)
    casi.append(("negativa: niente nome ne' id dell'avversario nello stato", "NomeDelGiocatore" not in testo and LUI not in testo))
    open(f, "w", encoding="utf-8").write(auth + setdeck.replace("Ladder", "Arena_Championship_Qualifier") + stanza("m2", "Arena_Championship_Qualifier", "Playing"))
    c = Seguito(f, io=(ME, None)).aggiorna()
    casi.append(("un evento competitivo si riconosce (l'HUD li' tace)", c["competitivo"] and c["matchId"] == "m2"))
    S2 = Seguito(f, io=("ALTRO", None))
    casi.append(("negativa: senza il tuo account nel posto, nessun posto ne' carte", S2.aggiorna()["seat"] is None))
    for n_, ok in casi:
        print(("ok    " if ok else "ROSSO ") + n_)
    print(f"{sum(ok for _n, ok in casi)}/{len(casi)}")
    return all(ok for _n, ok in casi)


if __name__ == "__main__":
    if "--prova" in sys.argv:
        sys.exit(0 if prova() else 1)
    s = Seguito().aggiorna()
    print(json.dumps(s, indent=1, ensure_ascii=False) if s else "nessuna partita nel Player.log")
