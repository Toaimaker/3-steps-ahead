"""Archivio permanente delle partite: una scheda JSON per partita in Partite/.

Regola di Autore, 8 ott 2026 23:10: «voglio che teniamo sempre tutte le partite e continuiamo
a costruire analisi anche sulle carte giocate e come sono giocate dagli altri giocatori».

Legge il Player.log attuale, il Player-prev.log e tutti i log archiviati in Log_Arena/ (fuori da
git, pesanti), separa le partite per matchId e salva di ognuna, in piccolo e in git:
- chi, quando, evento, esito, il tuo mazzo visto;
- la cronologia: ogni magia lanciata e ogni abilita' con bersaglio (di entrambi), le terre giocate,
  gli attacchi col bersaglio, i blocchi, le creature morte, le vite, con turno, fase e mana libero
  di chi agisce.
Una partita gia' archiviata si riscrive solo se la nuova lettura ha piu' eventi (log piu' completo).
Ogni file di log si legge per conto suo; se la stessa partita sta in piu' file, per ogni turno si tiene
la lettura piu' completa (fino al 9 ott 2026 gli eventi si accodavano e le partite uscivano doppie).

Debug del 13 nov 2026 (i difetti trovati nel replayer il 12 nov, `mana_aperto.py`): l'annullamento di Arena (uno stato Full con
update GameStateUpdate_Undo e prevGameStateId = lo stato a cui si torna) toglie gli eventi nati dopo quello stato, prima una magia
annullata e rilanciata contava due volte; «terra» e' solo la terra giocata (ZoneTransfer PlayLand), una terra messa in campo da un
effetto (Put, Return...) e' «terra_messa» con la categoria in «come»; le vite a 0 (Arena non scrive lifeTotal quando e' 0, quindi
vite_finali restava all'ultimo valore sopra zero). Stato, annullamento, categorie e vite si leggono dalla riga a parte (`info_riga`):
`tavolo.Tracker` e' blindato e non e' toccato.

Uso: python -I Companion/Strumenti/archivio_partite.py          (tutte le fonti)
     python -I Companion/Strumenti/archivio_partite.py --solo-attuale
     python -I Companion/Strumenti/archivio_partite.py --ripara   (toglie i doppioni dalle schede gia' archiviate)
     python -I Companion/Strumenti/archivio_partite.py --misura   (rilegge tutto e confronta con le schede, senza scrivere)
     python -I Companion/Strumenti/archivio_partite.py --rifai    (riscrive le schede che la lettura nuova cambia)
     python -I Companion/Strumenti/archivio_partite.py --prova
"""
import os, sys
_casa = os.path.dirname(os.path.abspath(__file__))      # si sale fino a percorsi.py, che mette nel sys.path tutte le cartelle del Companion
while not os.path.isfile(os.path.join(_casa, "percorsi.py")):
    _casa = os.path.dirname(_casa)
if _casa not in sys.path:
    sys.path.insert(0, _casa)
import percorsi  # noqa: E402
import piattaforma  # noqa: E402  (i percorsi di Arena su Windows e su Mac)
import datetime
import glob
import json
import re
from pathlib import Path

import tavolo  # noqa: E402

ROOT = Path(percorsi.ROOT)
DEST = ROOT / "Partite"
DEST.mkdir(exist_ok=True)
SRC = Path(piattaforma.cartella_arena())
TS = re.compile(r'"timestamp": "(\d{13})"')


def tipo_zona(st, zid):
    return (st["zone"].get(zid) or {}).get("type", "")


def info_riga(riga):
    """Per ogni chiamata di on_msg che il Tracker fara' su questa riga, nello stesso ordine: None per una richiesta di surveil/scry
    (GroupReq), se no dict(sid, annulla=stato a cui si torna o None, zt={id: categoria della ZoneTransfer}, vite={posto: vite}).
    Rispecchia il giro di tavolo.Tracker.feed sui greToClientMessages, senza toccarlo."""
    if "greToClientEvent" not in riga:
        return []
    try:
        d = json.loads(riga[riga.find("{"):])
    except ValueError:
        return []
    out = []
    for m in (d.get("greToClientEvent") or {}).get("greToClientMessages") or []:
        if m.get("type") == "GREMessageType_GroupReq":
            out.append(None)
            continue
        gs = m.get("gameStateMessage")
        if not gs:
            continue
        zt = {}
        for a in gs.get("annotations") or []:
            if "AnnotationType_ZoneTransfer" in (a.get("type") or []):
                cat = next(((x.get("valueString") or [None])[0] for x in a.get("details") or [] if x.get("key") == "category"), None)
                for i in a.get("affectedIds") or []:
                    zt[i] = cat
        # Arena non scrive i valori a zero: un giocatore nel messaggio senza lifeTotal ha 0 vite (come mana_aperto.vite_da)
        vite = {p.get("systemSeatNumber"): p.get("lifeTotal", 0) for p in gs.get("players") or [] if p.get("systemSeatNumber") in (1, 2)}
        annulla = gs.get("prevGameStateId") if gs.get("update") == "GameStateUpdate_Undo" else None
        out.append(dict(sid=gs.get("gameStateId") or 0, annulla=annulla, zt=zt, vite=vite))
    return out


def terre_libere(st, seat):
    n = 0
    for z in st["zone"].values():
        if z.get("type") != "ZoneType_Battlefield":
            continue
        for iid in z.get("objectInstanceIds", []):
            o = st["obj"].get(iid)
            if o and o.get("controllerSeatId") == seat and "CardType_Land" in o.get("cardTypes", []) and not o.get("isTapped"):
                n += 1
    return n


class Registro:
    def __init__(self):
        self.partite = {}   # mid -> scheda
        self.prima = {}     # mid -> {iid: (zona, attackState, blockState)}
        self.ts = None
        self.grp = {}       # iid -> grpId, per riconoscere chi lascia il campo
        self.coda = []      # info_riga della riga che il Tracker sta leggendo, una voce per chiamata di on_msg
        self.info = None    # l'ultima voce: lo stato del gioco degli eventi che nascono adesso
        self.annullati = 0
        self.avanzi = 0     # righe in cui le voci di info_riga e le chiamate di on_msg non tornano

    def chi(self, st, seat):
        return "io" if seat == st["me"] else "lui"

    def scheda(self, st):
        mid = st["mid"]
        if mid not in self.partite:
            self.partite[mid] = {"matchId": mid, "inizio": self.ts, "evento": st.get("evento"), "avversario": st.get("avv"),
                                 "esito": None, "motivo": None, "turni": 0, "vite_finali": {}, "mio_mazzo_visto": [],
                                 "sue_carte_viste": [], "eventi": []}
            self.prima[mid] = {}
        return self.partite[mid]

    def on_msg(self, st):
        if not st or not st.get("me"):
            return
        s = self.scheda(st)
        if self.coda:
            voce = self.coda.pop(0)
            if voce is not None:
                self.info = voce
                if voce["annulla"]:
                    # l'annullamento: via gli eventi nati dopo lo stato a cui si torna (lo stato Full li rimanda se restano)
                    n = len(s["eventi"])
                    s["eventi"] = [e for e in s["eventi"] if e.get("_s", 0) <= voce["annulla"]]
                    self.annullati += n - len(s["eventi"])
        info = self.info or dict(sid=0, zt={}, vite={})
        s["avversario"] = st.get("avv") or s["avversario"]
        s["evento"] = st.get("evento") or s["evento"]
        tu = st["turno"]
        turno = tu.get("turnNumber", 0)
        ph = (tu.get("phase") or "").replace("Phase_", "")
        fase = ph if ph in ("Main1", "Main2", "Beginning", "Ending") or not tu.get("step") else tu["step"].replace("Step_", "")
        s["turni"] = max(s["turni"], turno or 0)
        prima = self.prima[st["mid"]]
        ora = {}
        for z in st["zone"].values():
            for iid in z.get("objectInstanceIds", []):
                o = st["obj"].get(iid)
                if o:
                    ora[iid] = (z.get("type"), o.get("attackState"), o.get("blockState"))
        tavolo.ST = st
        # chi e' uscito dal campo in questo messaggio: serve a distinguere «muore» da «finisce al cimitero» (surveil, scarto)
        usciti = {st["obj"].get(i, {}).get("grpId") for i, v in prima.items() if v[0] == "ZoneType_Battlefield" and ora.get(i, ("",))[0] != "ZoneType_Battlefield"}
        usciti |= {self.grp.get(i) for i, v in prima.items() if v[0] == "ZoneType_Battlefield" and i not in ora}
        for iid, (zona, att, blo) in ora.items():
            o = st["obj"][iid]
            p = prima.get(iid)
            base = {"_s": info["sid"], "t": turno, "fase": fase, "chi": self.chi(st, o.get("controllerSeatId") or o.get("ownerSeatId"))}
            nm = tavolo.nome(o.get("grpId"))
            if o.get("ownerSeatId") == st["me"] and o.get("type") != "GameObjectType_Ability" and zona != "ZoneType_Library":
                if nm not in s["mio_mazzo_visto"] and not nm.startswith("grp"):
                    s["mio_mazzo_visto"].append(nm)
            if o.get("ownerSeatId") not in (None, st["me"]) and o.get("type") == "GameObjectType_Card" and zona not in ("ZoneType_Library", "ZoneType_Hand"):
                if nm not in s["sue_carte_viste"] and not nm.startswith("grp"):
                    s["sue_carte_viste"].append(nm)
            if p is None:
                if zona == "ZoneType_Stack":
                    if o.get("type") == "GameObjectType_Ability":
                        ev = dict(base, tipo="abilita", carta=tavolo.nome(o.get("objectSourceGrpId")))
                    else:
                        ev = dict(base, tipo="lancia", carta=nm,
                                  tipi=[x.replace("CardType_", "") for x in o.get("cardTypes", [])])
                    ev["mana_libero_dopo"] = terre_libere(st, o.get("controllerSeatId"))
                    s["eventi"].append(ev)
                elif zona == "ZoneType_Battlefield" and "CardType_Land" in o.get("cardTypes", []):
                    come = info["zt"].get(iid)
                    if come == "PlayLand":
                        s["eventi"].append(dict(base, tipo="terra", carta=nm))
                    elif come:          # messa in campo da un effetto: Evolving Wilds, un ritorno dal cimitero
                        s["eventi"].append(dict(base, tipo="terra_messa", carta=nm, come=come))
                    # senza ZoneTransfer (il log che comincia a partita in corso, un messaggio riassunto) non si sa: niente evento
                elif zona == "ZoneType_Battlefield" and o.get("type") == "GameObjectType_Token":
                    s["eventi"].append(dict(base, tipo="pedina", carta=nm))
                elif zona == "ZoneType_Graveyard" and "CardType_Creature" in o.get("cardTypes", []) and o.get("grpId") in usciti:
                    s["eventi"].append(dict(base, tipo="muore", carta=nm, chi=self.chi(st, o.get("ownerSeatId"))))
            else:
                if att == "AttackState_Attacking" and p[1] != "AttackState_Attacking":
                    tid = (o.get("attackInfo") or {}).get("targetId")
                    dove = "io" if tid == st["me"] else ("lui" if tid in (1, 2) else tavolo.nome_oggetto(tid))
                    s["eventi"].append(dict(base, tipo="attacca", carta=nm, pt=f"{o.get('power',{}).get('value')}/{o.get('toughness',{}).get('value')}", bersaglio=dove))
                if blo == "BlockState_Blocking" and p[2] != "BlockState_Blocking":
                    bl = [tavolo.nome_oggetto(a) for a in (o.get("blockInfo") or {}).get("attackerIds", [])]
                    s["eventi"].append(dict(base, tipo="blocca", carta=nm, pt=f"{o.get('power',{}).get('value')}/{o.get('toughness',{}).get('value')}", blocca=bl))
        # bersagli delle magie e abilita' in pila
        for aff, bers in (st.get("mire") or {}).items():
            for ev in reversed(s["eventi"][-12:]):
                o = st["obj"].get(aff)
                if not o or "bersagli" in ev:
                    continue
                abil = o.get("type") == "GameObjectType_Ability"
                if (abil and ev["tipo"] == "abilita" and tavolo.nome(o.get("objectSourceGrpId")) == ev["carta"]) or                    (not abil and ev["tipo"] == "lancia" and tavolo.nome(o.get("grpId")) == ev["carta"]):
                    if True:
                        ev["bersagli"] = [("io" if b == st["me"] else "lui" if b in (1, 2) else tavolo.nome_oggetto(b)) for b in bers]
                        ev["bersagli_di"] = [("io" if b == st["me"] else "lui" if b in (1, 2) else
                                              self.chi(st, (st["obj"].get(b) or {}).get("controllerSeatId") or (st["obj"].get(b) or {}).get("ownerSeatId"))) for b in bers]
                        break
        self.prima[st["mid"]] = ora
        for i in ora:
            self.grp[i] = st["obj"][i].get("grpId")
        for seat, v in info["vite"].items():      # dal messaggio, non da st["pl"]: li' un lifeTotal a 0 non arriva e resta il vecchio
            s["vite_finali"][self.chi(st, seat)] = v
        if st.get("fine"):
            for r in st["fine"].get("resultList", []):
                if r.get("scope") == "MatchScope_Match":
                    s["esito"] = "vinta" if r.get("winningTeamId") == st.get("mio_team") else "persa"
                    s["motivo"] = (r.get("reason") or "").replace("ResultReason_", "")


def leggi_file(path, reg):
    t = tavolo.Tracker()
    t.on_msg = reg.on_msg
    righe = open(path, encoding="utf-8", errors="ignore") if isinstance(path, (str, Path)) else path
    for riga in righe:
        m = TS.search(riga[:200])
        if m:
            reg.ts = datetime.datetime.fromtimestamp(int(m.group(1)) / 1000).strftime("%Y-%m-%dT%H:%M")
        reg.coda = info_riga(riga)
        t.feed(riga)
        if reg.coda:            # il Tracker ha chiamato on_msg meno volte di quante voci ha la riga: non deve succedere
            reg.avanzi += 1
        reg.coda = []
        if t.stato and t.stato.get("fine") and t.stato["mid"] in reg.partite:
            reg.on_msg(t.stato)


def pulisci(n):
    return re.sub(r"[^A-Za-z0-9]+", "", n or "")[:20] or "anonimo"


def pezzi(eventi):
    """Divide una lista di eventi nei pezzi letti da file diversi: dentro un file il turno non torna mai indietro."""
    out, cur, ultimo = [], [], -1
    for e in eventi:
        if e["t"] < ultimo:
            out.append(cur)
            cur = []
        cur.append(e)
        ultimo = e["t"]
    if cur:
        out.append(cur)
    return out


def unisci_pezzi(lista):
    """Per ogni turno tiene gli eventi del pezzo che ne ha di piu' (la lettura piu' completa di quel turno).
    Fino al 9 ott 2026 i pezzi si accodavano: una partita presente in due log usciva doppia
    (106 schede su 252, fra cui il Quick Draft con booflord copiato per intero)."""
    per_turno = {}
    for i, p in enumerate(lista):
        for e in p:
            per_turno.setdefault(e["t"], {}).setdefault(i, []).append(e)
    eventi = []
    for t in sorted(per_turno):
        scelto = max(per_turno[t].items(), key=lambda kv: (len(kv[1]), -kv[0]))[1]
        eventi += scelto
    return eventi


def unisci_schede(schede):
    """Piu' letture della stessa partita (una per file di log) -> una scheda sola, senza doppioni."""
    base = max(schede, key=lambda s: (s["turni"], len(s["eventi"])))
    s = dict(base)
    s["eventi"] = unisci_pezzi([x["eventi"] for x in schede if x["eventi"]])
    s["turni"] = max(x["turni"] for x in schede)
    s["esito"] = next((x["esito"] for x in schede if x.get("esito")), None)
    s["motivo"] = next((x["motivo"] for x in schede if x.get("esito")), None)
    s["inizio"] = min((x["inizio"] for x in schede if x.get("inizio")), default=None)
    for k in ("mio_mazzo_visto", "sue_carte_viste"):
        s[k] = list(dict.fromkeys(n for x in schede for n in x[k]))
    return s


def ripara_archivio():
    """Toglie i doppioni dalle schede gia' archiviate (i loro log vecchi spesso non ci sono piu')."""
    riparate = 0
    for p in sorted(DEST.glob("*.json")):
        s = json.load(open(p, encoding="utf-8"))
        nuovi = unisci_pezzi(pezzi(s["eventi"]))
        if len(nuovi) != len(s["eventi"]):
            print(f"  {p.name}: {len(s['eventi'])} -> {len(nuovi)} eventi")
            s["eventi"] = nuovi
            json.dump(s, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            riparate += 1
    print(f"schede riparate {riparate}")


def pulita(s):
    """La scheda da scrivere: senza lo stato del gioco degli eventi («_s» serve solo all'annullamento)."""
    s = dict(s)
    s["eventi"] = [{k: v for k, v in e.items() if k != "_s"} for e in s["eventi"]]
    return s


def leggi_fonti(solo_attuale=False):
    fonti = [SRC / "Player.log", SRC / "Player-prev.log"]
    if not solo_attuale:
        fonti += sorted(Path(p) for p in glob.glob(str(ROOT / "Log_Arena" / "*.log")))
    letture, annullati = {}, 0
    for f in fonti:
        if f.exists():
            r = Registro()  # un registro per file: la stessa partita in due log non si accoda due volte
            leggi_file(f, r)
            annullati += r.annullati
            if r.avanzi:
                print(f"  {f.name}: {r.avanzi} righe con le voci che non tornano col Tracker")
            for mid, s in r.partite.items():
                letture.setdefault(mid, []).append(s)
    return {mid: pulita(unisci_schede(v)) for mid, v in letture.items()}, annullati


def conta(s):
    c = {}
    for e in s.get("eventi") or []:
        c[e["tipo"]] = c.get(e["tipo"], 0) + 1
    return c


def confronta_archivio(scrivi=False):
    """--misura (scrivi=False) e --rifai: ogni scheda in Partite/ contro la lettura di oggi dei log. Una scheda si riscrive solo se
    la lettura nuova ha tutti i turni con eventi della vecchia (un log perso non toglie niente) e lo stesso esito."""
    nuove, annullati = leggi_fonti()
    tot = dict(schede=0, senza_log=0, uguali=0, cambiate=0, turni_persi=0, riscritte=0)
    delta = {}                  # tipo di evento -> (vecchie, nuove) sulle schede rilette
    vite0 = terre_messe = doppie = 0
    esempi = []
    for p in sorted(DEST.glob("*.json")):
        try:
            v = json.load(open(p, encoding="utf-8"))
        except Exception:
            continue
        tot["schede"] += 1
        n = nuove.get(v.get("matchId"))
        if not n or not n["eventi"]:
            tot["senza_log"] += 1
            continue
        n = dict(n, avversario=n.get("avversario") or v.get("avversario"))
        cv, cn = conta(v), conta(n)
        for k in set(cv) | set(cn):
            a, b = delta.get(k, (0, 0))
            delta[k] = (a + cv.get(k, 0), b + cn.get(k, 0))
        if v.get("eventi") == n["eventi"] and v.get("vite_finali") == n["vite_finali"]:
            tot["uguali"] += 1
            continue
        if not {e["t"] for e in v.get("eventi") or []} <= {e["t"] for e in n["eventi"]} or (v.get("esito") and v.get("esito") != n.get("esito")):
            tot["turni_persi"] += 1
            continue
        tot["cambiate"] += 1
        if 0 in n["vite_finali"].values() and 0 not in (v.get("vite_finali") or {}).values():
            vite0 += 1
        terre_messe += cn.get("terra_messa", 0) > 0
        doppie += cn.get("lancia", 0) < cv.get("lancia", 0)
        if len(esempi) < 8:
            esempi.append(f"  {p.name}: lancia {cv.get('lancia', 0)}->{cn.get('lancia', 0)}, terra {cv.get('terra', 0)}->{cn.get('terra', 0)}"
                          f" (+{cn.get('terra_messa', 0)} messe), vite {v.get('vite_finali')} -> {n['vite_finali']}")
        if scrivi:
            n = dict(n, inizio=v.get("inizio") or n.get("inizio"))
            json.dump(n, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            tot["riscritte"] += 1
    print(f"schede {tot['schede']} | senza log {tot['senza_log']} | uguali {tot['uguali']} | cambiate {tot['cambiate']}"
          f" | non riscrivibili (turni o esito che il log di oggi non ha) {tot['turni_persi']}" + (f" | riscritte {tot['riscritte']}" if scrivi else ""))
    print(f"eventi annullati letti nei log: {annullati}")
    print(f"fra le cambiate: vite a 0 nuove {vite0}, con terre messe da un effetto {terre_messe}, con magie doppie tolte {doppie}")
    print("eventi per tipo sulle schede rilette (prima -> dopo):")
    for k in sorted(delta):
        a, b = delta[k]
        print(f"  {k:12} {a:7} -> {b:7}  ({b - a:+d})")
    print("\n".join(esempi))
    return tot


def prova():
    """I tre difetti del 12 nov 2026 su un log finto, ognuno con la negativa."""
    def stanza():
        return json.dumps({"matchGameRoomStateChangedEvent": {"gameRoomInfo": {"gameRoomConfig": {"matchId": "prova-1", "reservedPlayers": [
            dict(playerName=tavolo.ME, systemSeatId=1, eventId="Prova", teamId=1), dict(playerName="Avversario", systemSeatId=2, teamId=2)]}}}})

    def riga(*msgs):
        return "[UnityCrossThreadLogger] " + json.dumps({"greToClientEvent": {"greToClientMessages": list(msgs)}}) + "\n"

    def gs(**k):
        return {"type": "GREMessageType_GameStateMessage", "gameStateMessage": k}

    def zone(mano=(), campo=(), pila=()):
        return [dict(zoneId=31, type="ZoneType_Hand", ownerSeatId=1, objectInstanceIds=list(mano)), dict(zoneId=28, type="ZoneType_Battlefield", objectInstanceIds=list(campo)),
                dict(zoneId=27, type="ZoneType_Stack", objectInstanceIds=list(pila))]

    def carta(i, tipo, zona):
        return dict(instanceId=i, grpId=900000 + i, type="GameObjectType_Card", zoneId=zona, ownerSeatId=1, controllerSeatId=1, cardTypes=[tipo])

    def zt(i, cat):
        return dict(id=500 + i, affectedIds=[i], type=["AnnotationType_ZoneTransfer"], details=[dict(key="category", type="KeyValuePairValueType_string", valueString=[cat])])

    t1 = dict(turnNumber=1, activePlayer=1, phase="Phase_Main1")
    vite = [dict(systemSeatNumber=1, lifeTotal=20), dict(systemSeatNumber=2, lifeTotal=20)]

    def partita(annulla="GameStateUpdate_Undo", cat_terra2="Put", senza_vite=True):
        righe = [stanza() + "\n",
                 riga(gs(type="GameStateType_Full", gameStateId=1, gameInfo=dict(stage="GameStage_Start"), turnInfo=t1, players=vite,
                         zones=zone(mano=[10, 15]), gameObjects=[carta(10, "CardType_Instant", 31), carta(15, "CardType_Land", 31)])),
                 riga(gs(type="GameStateType_Diff", gameStateId=2, prevGameStateId=1, zones=zone(mano=[10], campo=[20]),
                         gameObjects=[carta(20, "CardType_Land", 28)], annotations=[zt(20, "PlayLand")])),
                 riga(gs(type="GameStateType_Diff", gameStateId=3, prevGameStateId=2, zones=zone(campo=[20], pila=[11]),
                         gameObjects=[carta(11, "CardType_Instant", 27)], annotations=[zt(11, "CastSpell")])),
                 # Arena annulla il lancio: lo stato Full torna a 2, la carta torna in mano (un surveil chiesto nella stessa riga, prima)
                 riga({"type": "GREMessageType_GroupReq", "groupReq": {}},
                      gs(type="GameStateType_Full", gameStateId=4, prevGameStateId=2, update=annulla, turnInfo=t1, players=vite,
                         zones=zone(mano=[10], campo=[20]), gameObjects=[carta(10, "CardType_Instant", 31), carta(20, "CardType_Land", 28)])),
                 riga(gs(type="GameStateType_Diff", gameStateId=5, prevGameStateId=4, zones=zone(campo=[20], pila=[12]),
                         gameObjects=[carta(12, "CardType_Instant", 27)], annotations=[zt(12, "CastSpell")])),
                 # una terra messa in campo da un effetto, e l'avversario che va a 0 (Arena non scrive lifeTotal)
                 riga(gs(type="GameStateType_Diff", gameStateId=6, prevGameStateId=5, zones=zone(campo=[20, 21]),
                         gameObjects=[carta(21, "CardType_Land", 28)], annotations=[zt(21, cat_terra2)],
                         players=[dict(systemSeatNumber=1, lifeTotal=20), dict(systemSeatNumber=2)] if senza_vite else [dict(systemSeatNumber=1, lifeTotal=20)]))]
        r = Registro()
        leggi_file(righe, r)
        s = r.partite["prova-1"]
        return conta(s), s["vite_finali"], r

    casi = []
    c, v, r = partita()
    casi.append(("il lancio annullato e rilanciato conta una volta", c.get("lancia") == 1 and r.annullati == 1))
    casi.append(("la terra giocata resta dopo l'annullamento", c.get("terra") == 1))
    casi.append(("la terra messa da un effetto e' terra_messa, non terra", c.get("terra_messa") == 1))
    casi.append(("l'avversario senza lifeTotal ha 0 vite", v.get("lui") == 0 and v.get("io") == 20))
    c, v, r = partita(annulla="GameStateUpdate_Send")
    casi.append(("negativa: senza l'annullamento il lancio conta due volte", c.get("lancia") == 2))
    c, v, r = partita(cat_terra2="PlayLand")
    casi.append(("negativa: con PlayLand sono due terre giocate", c.get("terra") == 2 and not c.get("terra_messa")))
    c, v, r = partita(senza_vite=False)
    casi.append(("negativa: se il messaggio non nomina l'avversario le sue vite restano 20", v.get("lui") == 20))
    for nome, ok in casi:
        print(("OK   " if ok else "ROSSO") + " " + nome)
    rossi = sum(1 for _, ok in casi if not ok)
    print(f"{len(casi) - rossi}/{len(casi)}")
    return 1 if rossi else 0


def main():
    if "--ripara" in sys.argv:
        ripara_archivio()
        return
    if "--prova" in sys.argv:
        sys.exit(prova())
    if "--misura" in sys.argv or "--rifai" in sys.argv:
        confronta_archivio(scrivi="--rifai" in sys.argv)
        return
    reg = Registro()
    reg.partite, _ = leggi_fonti("--solo-attuale" in sys.argv)
    nuove = aggiornate = 0
    esistenti = {}
    for p in DEST.glob("*.json"):
        try:
            esistenti[json.load(open(p, encoding="utf-8"))["matchId"]] = p
        except Exception:
            pass
    for mid, s in reg.partite.items():
        if not s["eventi"] or not s.get("avversario") or s["avversario"] == "?":
            continue
        if mid in esistenti:
            vecchia = json.load(open(esistenti[mid], encoding="utf-8"))
            if len(vecchia.get("eventi", [])) >= len(s["eventi"]) and vecchia.get("esito"):
                continue
            percorso = esistenti[mid]; aggiornate += 1
        else:
            data = (s["inizio"] or "0000-00-00T00:00").replace(":", "").replace("T", "_")
            percorso = DEST / f"{data}_{pulisci(s['evento'])}_{pulisci(s['avversario'])}_{mid[:8]}.json"
            nuove += 1
        json.dump(s, open(percorso, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"partite lette {len(reg.partite)} | nuove {nuove} | aggiornate {aggiornate} | in archivio {len(list(DEST.glob('*.json')))}")


if __name__ == "__main__":
    main()
