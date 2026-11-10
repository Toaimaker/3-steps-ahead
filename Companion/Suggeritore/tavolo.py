"""Il tavolo della partita in corso, letto dal Player.log di Arena. Per la modalita' «spalla» (CLAUDE.md, regola 3):
gioca Autore, l'agente legge il tavolo e propone la linea prima del click.

Uso:  python Companion/Suggeritore/tavolo.py           (stato attuale: turno, fase, vite, la tua mano, i due campi, cimiteri, esilio)
      python Companion/Suggeritore/tavolo.py --testi   (aggiunge il testo di ogni carta non terra in vista, da Regole/reality_fracture.json)

Il log manda lo stato a pezzi (un messaggio pieno, poi solo le differenze): qui si rimettono insieme.
Della mano avversaria si vede solo quante carte ha: Arena non scrive nel log le carte coperte.
"""
import os, sys; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); import percorsi  # la casa del Companion: i percorsi stanno in Companion/percorsi.py (13 ott 2026)
import progetto as PR  # i file del set e del formato: Espansioni/<SET>/<Formato>/progetto.json (16 ott 2026)
import os, re, sys, json
try: sys.stdout.reconfigure(encoding="utf-8")
except Exception: pass
ROOT=percorsi.ROOT
LOG=os.path.expandvars(r"%USERPROFILE%\AppData\LocalLow\Wizards Of The Coast\MTGA\Player.log")
import account as _ACC  # l'app pubblica: chi usa l'app (account.py)
ME=_ACC.account()["nome"] or ""
DB=json.load(open(os.path.join(ROOT,"Collezione","arena_cards_cache.json"),encoding="utf-8"))
TESTI={}
sp=PR.file("carte_lista","FRA")
if os.path.exists(sp):
    for c in json.load(open(sp,encoding="utf-8")):
        TESTI[c["name"].split(" // ")[0]]=c
def nome(g): return DB.get(str(g),{}).get("n",f"grp{g}")

class Tracker:
    """Ricostruisce lo stato della partita riga per riga: serve sia a rileggere il log intero (leggi) sia a seguirlo in diretta."""
    def __init__(self): self.stato=None; self.on_msg=None   # on_msg(stato) dopo OGNI messaggio di stato: una riga del log ne contiene piu' d'uno
    def feed(self,riga):
        """Ritorna True se la riga ha cambiato lo stato."""
        stato=self.stato
        if "matchGameRoomStateChangedEvent" in riga:
            i=riga.find("{")
            try: info=json.loads(riga[i:])["matchGameRoomStateChangedEvent"]["gameRoomInfo"]
            except Exception: return False
            mid=info["gameRoomConfig"]["matchId"]
            if not stato or stato["mid"]!=mid:
                stato=self.stato={"mid":mid,"obj":{},"zone":{},"pl":{},"turno":{},"me":None,"avv":"?","fine":None,"evento":"","mio_team":None,"pann":{},"mire":{}}
            for p in info["gameRoomConfig"].get("reservedPlayers",[]):
                if p["playerName"]==ME: stato["me"]=p["systemSeatId"]; stato["evento"]=p.get("eventId",""); stato["mio_team"]=p.get("teamId")
                else: stato["avv"]=p["playerName"]
            res=info.get("finalMatchResult")
            if res: stato["fine"]=res
            return True
        if "greToClientEvent" not in riga or not stato: return False
        i=riga.find("{")
        try: ev=json.loads(riga[i:])
        except Exception: return False
        cambiato=False
        for m in ev.get("greToClientEvent",{}).get("greToClientMessages",[]):
            if m.get("type")=="GREMessageType_GroupReq":
                # surveil/scry tuo: Arena chiede dove mettere le carte guardate, e quelle carte sono gia' nello stato (9 ott 2026)
                g=m.get("groupReq",{})
                stato["guarda"]={"msg":m.get("msgId"),"ids":g.get("instanceIds",[]),"ctx":(g.get("context") or "").replace("GroupingContext_",""),"fonte":g.get("sourceId")}
                if stato["guarda"]["ctx"] in ("Surveil","Scry"): stato["guardato_turno"]=stato["turno"].get("turnNumber")   # Surveillance Phantasm puo' attaccare
                cambiato=True
                if self.on_msg: self.on_msg(stato)
                continue
            gs=m.get("gameStateMessage")
            if not gs: continue
            cambiato=True
            if gs.get("type")=="GameStateType_Full" and gs.get("gameInfo",{}).get("stage")=="GameStage_Start":
                stato["obj"]={}; stato["zone"]={}
            for z in gs.get("zones",[]): stato["zone"][z["zoneId"]]=z
            for o in gs.get("gameObjects",[]): stato["obj"][o["instanceId"]]=o
            for iid in gs.get("diffDeletedInstanceIds",[]): stato["obj"].pop(iid,None)
            for p in gs.get("players",[]): stato["pl"].setdefault(p.get("systemSeatNumber") or p.get("systemSeatId"),{}).update(p)   # il log usa systemSeatNumber
            if gs.get("turnInfo"): stato["turno"].update(gs["turnInfo"])
            # segnalini (+1/+1, stordimento...) e bersagli delle magie/abilita' in pila (8 ott 2026)
            pann=stato.setdefault("pann",{}); mire=stato.setdefault("mire",{})
            for a in gs.get("persistentAnnotations",[]): pann[a["id"]]=a
            for aid in gs.get("diffDeletedPersistentAnnotationIds",[]): pann.pop(aid,None)
            for a in list(gs.get("annotations",[]))+list(gs.get("persistentAnnotations",[])):
                if "AnnotationType_TargetSpec" in a.get("type",[]) and a.get("affectorId"):
                    mire[a["affectorId"]]=a.get("affectedIds",[])
                # la terra del turno (10 ott 2026): ZoneTransfer «PlayLand» dalla mano del giocatore. La proposta GIOCA
                # non deve proporre una seconda terra nello stesso turno (HANDOFF_Feedback_Veloce_Spalla §5.0 punto 4)
                if "AnnotationType_ZoneTransfer" in a.get("type",[]):
                    det={d.get("key"):(d.get("valueString") or d.get("valueInt32") or [None])[0] for d in a.get("details",[])}
                    if det.get("category")=="PlayLand":
                        chi=(stato["zone"].get(det.get("zone_src")) or {}).get("ownerSeatId")
                        if chi: stato.setdefault("terra_turno",{})[chi]=stato["turno"].get("turnNumber")
            for iid in gs.get("diffDeletedInstanceIds",[]): mire.pop(iid,None)
            if self.on_msg: self.on_msg(stato)
        return cambiato

def inizio_partita(path=None):
    """Byte da cui parte l'ultima partita del log: la prima riga che nomina il suo matchId.
    Regola di Autore, 9 ott 2026: si leggono solo le righe della partita in corso, non i 38 MB del log intero."""
    try: data=open(path or LOG,"rb").read()
    except OSError: return 0
    i=data.rfind(b'"matchId"')
    if i<0: return 0
    m=re.match(rb'"matchId"\s*:\s*"([^"]+)"',data[i:i+120])
    if not m: return 0
    j=data.find(m.group(1))
    return data.rfind(b"\n",0,j)+1 if j>=0 else 0

def leggi(stop=None,intera=False):
    """stop: funzione che riceve lo stato e ritorna True per fermarsi li' (riguardare un momento passato della partita).
    Dal 9 ott 2026 legge solo la partita in corso; intera=True rilegge tutto il log."""
    t=Tracker()
    with open(LOG,"rb") as f:
        if not intera: f.seek(inizio_partita())
        for b in f:
            riga=b.decode("utf-8","ignore")
            if t.feed(riga) and stop and t.stato and stop(t.stato): return t.stato
    return t.stato

TIPI_SEGNALINO={1:"+1/+1",7:None,172:"STORDIMENTO"}   # 7 = fedelta', gia' mostrata; gli altri si mostrano col numero finche' non si sa il nome

def segnalini(o):
    out=[]
    for a in ((ST or {}).get("pann") or {}).values():
        if "AnnotationType_Counter" not in a.get("type",[]) or o.get("instanceId") not in a.get("affectedIds",[]): continue
        d={x["key"]:(x.get("valueInt32") or [None])[0] for x in a.get("details",[])}
        tipo=TIPI_SEGNALINO.get(d.get("counter_type"),f"segnalino tipo {d.get('counter_type')}")
        if tipo: out.append(f"{d.get('count')}x {tipo}")
    return out

def nome_oggetto(iid):
    o=((ST or {}).get("obj") or {}).get(iid)
    if not o: return "giocatore" if iid in (1,2) else f"#{iid}"
    if o.get("type")=="GameObjectType_Ability": return "abilita' di "+nome(o.get("objectSourceGrpId"))
    return nome(o.get("grpId"))

def carta(o,testi=False):
    n=nome(o.get("grpId")); bits=[]
    if o.get("type")=="GameObjectType_Ability":
        n="abilita' di "+nome(o.get("objectSourceGrpId"))
    if o.get("type")=="GameObjectType_Token": n+=" (pedina)"
    bits+=segnalini(o)
    mira=((ST or {}).get("mire") or {}).get(o.get("instanceId"))
    if mira:
        me=(ST or {}).get("me")
        bits.append("BERSAGLIO -> "+", ".join("te" if t==me else ("lui" if t in (1,2) else nome_oggetto(t)) for t in mira))
    pw=o.get("power",{}).get("value"); th=o.get("toughness",{}).get("value")
    if pw is not None and th is not None: bits.append(f"{pw}/{th}")
    if o.get("loyalty",{}).get("value") is not None: bits.append(f"fedelta' {o['loyalty']['value']}")
    if o.get("damage"): bits.append(f"{o['damage']} danni")
    if o.get("isTapped"): bits.append("TAPPATA")
    if o.get("hasSummoningSickness"): bits.append("appena entrata")
    if o.get("attackState") in ("AttackState_Attacking",):
        tid=(o.get("attackInfo") or {}).get("targetId")
        dove="te" if tid==ST["me"] else ("lui" if tid in (1,2) else nome(ST["obj"].get(tid,{}).get("grpId")) if tid else "?")
        bits.append(f"ATTACCA -> {dove}")
    if o.get("blockState") in ("BlockState_Blocking",): bits.append("BLOCCA")
    s=n+(f"  [{', '.join(bits)}]" if bits else "")
    if testi:
        t=TESTI.get(n.split(" // ")[0])
        if t and "Land" not in (t.get("type") or ""): s+=f"\n        {t['mana_cost']} | {(t.get('oracle') or '').replace(chr(10),' ')}"
    return s

def mostra(st,testi):
    me=st["me"]; avv=3-me if me in (1,2) else None
    t=st["turno"]
    attivo="TU" if t.get("activePlayer")==me else "LUI"
    print(f"Partita contro {st['avv']} | {st['evento']} | turno Arena {t.get('turnNumber','?')} (tocca a {attivo}) | {t.get('phase','').replace('Phase_','')} {t.get('step','').replace('Step_','')}")
    if st["fine"]: print("PARTITA FINITA:",json.dumps(st["fine"].get("resultList",[]))[:300])
    for s,chi in ((me,"TU"),(avv,"LUI")):
        p=st["pl"].get(s,{}); print(f"  {chi}: vita {p.get('lifeTotal','?')}")
    def zona(tipo,seat):
        for z in st["zone"].values():
            if z.get("type")==tipo and z.get("ownerSeatId")==seat: return z
        return {}
    def oggetti(tipo,seat=None,controller=None):
        out=[]
        for z in st["zone"].values():
            if z.get("type")!=tipo: continue
            if seat is not None and z.get("ownerSeatId") not in (seat,None): continue
            for iid in z.get("objectInstanceIds",[]):
                o=st["obj"].get(iid)
                if not o: continue
                if controller is not None and o.get("controllerSeatId")!=controller: continue
                out.append(o)
        return out
    mano=oggetti("ZoneType_Hand",me)
    print(f"\nLA TUA MANO ({len(mano)}):"); [print("   ",carta(o,testi)) for o in mano]
    na=len(zona("ZoneType_Hand",avv).get("objectInstanceIds",[])) if avv else "?"
    print(f"Mano avversaria: {na} carte | librerie: tu {len(zona('ZoneType_Library',me).get('objectInstanceIds',[]))}, lui {len(zona('ZoneType_Library',avv).get('objectInstanceIds',[])) if avv else '?'}")
    for s,chi in ((me,"IL TUO CAMPO"),(avv,"IL SUO CAMPO")):
        ob=oggetti("ZoneType_Battlefield",controller=s)
        terre=[o for o in ob if "CardType_Land" in o.get("cardTypes",[])]; altre=[o for o in ob if o not in terre]
        lib=sum(1 for o in terre if not o.get("isTapped"))
        print(f"\n{chi}: terre {len(terre)} ({lib} stappate): {', '.join(sorted(nome(o['grpId']) for o in terre))}")
        for o in altre: print("   ",carta(o,testi))
    pila=oggetti("ZoneType_Stack")
    if pila: print("\nPILA:"); [print("   ",carta(o,testi),"(di",("te" if o.get("controllerSeatId")==me else "lui")+")") for o in pila]
    for s,chi in ((me,"tuo"),(avv,"suo")):
        cim=[nome(o["grpId"]) for o in oggetti("ZoneType_Graveyard",s)]
        if cim: print(f"\nCimitero {chi}: {', '.join(cim)}")
    es=[nome(o["grpId"])+(" (tuo)" if o.get("ownerSeatId")==me else " (suo)") for o in oggetti("ZoneType_Exile")]
    if es: print(f"Esilio: {', '.join(es)}")

ST=None
if __name__=="__main__":
    st=leggi(); ST=st
    if not st: print("Nessuna partita nel log."); sys.exit(1)
    mostra(st,"--testi" in sys.argv)
