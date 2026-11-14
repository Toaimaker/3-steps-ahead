"""Il mana aperto nelle partite (Autore, 12 nov 2026: «situazioni piu' specifiche, come x esempio vs mana untapped / with mana untapped»): dai pezzi di log di
ogni partita (Log_Arena/partite/<ID>/arena.log, partite_separate) si segue lo stato del gioco di Arena (oggetti, zone, turno) e si annota:
- a ogni turno con un attacco, le terre stappate di chi difende quando gli attaccanti sono dichiarati (la prima volta nel turno);
- alla fine di ogni turno (passo End), le terre stappate di chi era di turno;
- le foto della partita (12 nov 2026, Autore: «proprio come holdem manager, sotto al grafico una tabella con la nostra mano in una colonna e il board in
  un'altra: premendo su quel dato si apre una board dedicata che ci mostra le carte in quello spot in mano o sul tavolo»): la mano tenuta all'inizio del primo
  turno, la board alla fine di ogni turno e all'ultimo stato: per ogni posto le carte in campo [grpId, tappata, pedina], la mano (la sua: solo quante), le vite.
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

VERSIONE = 15       # 15 (13 nov 2026, Autore: «Sì, aggiungilo», la Reliquia rotta dopo il suo draw step): «attivate», ogni abilita' attivata (non di mana) di tutti e due, [turno, posto, grpId della carta, fase, step, chi e' di turno]; 14 (i leak L3 e L6): «fasi», la fase di ogni tua e sua magia lanciata ([turno, posto, grpId, fase di Arena]); 2: le foto della partita; 3: cimitero, esilio, forza e costituzione; 4: i momenti del combattimento e delle magie coi bersagli;
#                    5: ogni istantaneo e stregoneria in pila (anche senza bersagli) e i permanenti che ha tolto dal campo (i board wipe);
#                    6: per le partite lette dagli archivi, dove stanno («dove»: archivio, byte di inizio e di fine), per il replay azione per azione;
#                    7: debug del 12 nov 2026: le cancellazioni, chi e' in campo dalle zone, le vite a 0, l'annullamento, emblemi e inneschi, i riassunti;
#                    8: i bersagli fuori dal campo («fuori»: cimitero, esilio, pila); 9: l'emblema risale alla carta;
#                    10: forza e costituzione a zero; 11: «fatti», i permanenti che la magia ha spostato lei (affectorId), e le abilita' coi bersagli;
#                    12: «azioni» (terre giocate e magie lanciate turno per turno, col tipo) e nel combattimento «pot» e «aperte»
#                    13: nelle «azioni» anche le pescate («pesca», di chi riceve la carta)
CARTELLA = os.path.join(LOGDIR, "partite")
COPIA = os.path.join(LOGDIR, "mana_aperto.json")


def grp_vero(o, obj):
    """Il grpId da mostrare di un oggetto: la carta per carte e pedine (3 = a faccia in giu', come lo scrive Arena), la carta d'origine per un'abilita' (il
    padre) e per emblemi e inneschi ritardati, che Arena scrive con grpId finti (2, 5: objectSourceGrpId e' la carta)."""
    for _ in range(6):         # un'abilita' di un emblema: si risale fino alla carta (l'abilita' -> l'emblema -> la carta che l'ha creato)
        if not o:
            return None
        if o.get("type") in ("GameObjectType_Card", "GameObjectType_Token"):
            return o.get("grpId")
        padre = obj.get(o.get("parentId"))
        if padre is None or padre is o:
            return o.get("objectSourceGrpId") or o.get("grpId")
        o = padre
    return None


def cancellati(gs):
    """Gli oggetti che un messaggio toglie: Arena li scrive in diffDeletedInstanceIds (fino al 12 nov 2026 si leggeva deletedInstanceIds, che nei log non c'e':
    nessun oggetto veniva mai tolto e le creature morte restavano «in campo» con l'attacco dichiarato)."""
    return (gs.get("diffDeletedInstanceIds") or []) + (gs.get("deletedInstanceIds") or [])


def vite_da(gs, vite):
    """Le vite dei giocatori di un messaggio: un giocatore senza lifeTotal ha 0 vite (Arena non scrive i valori a zero)."""
    for pl in gs.get("players") or []:
        if pl.get("systemSeatNumber") in (1, 2):
            vite[pl["systemSeatNumber"]] = pl.get("lifeTotal", 0)


def turno_da(gs, ti):
    """turnInfo: nelle fasi principali Arena non scrive lo step, quindi quello di prima non resta."""
    t_ = gs.get("turnInfo")
    if t_:
        if "phase" in t_ and "step" not in t_:
            ti.pop("step", None)
        ti.update(t_)


ZONE_FUORI = {"ZoneType_Graveyard": "cim", "ZoneType_Exile": "esi", "ZoneType_Stack": "pila", "ZoneType_Hand": "mano", "ZoneType_Library": "grimorio"}


def fuori_campo(bers, zone, zids, zown, obj):
    """I bersagli che non sono in campo (12 nov 2026, il debug del replayer: 410 bersagli nel cimitero, una rianimazione, e 79 in pila, una contromagia, non
    avevano la freccia): [[id, «cim»|«esi»|«pila»|«mano»|«grimorio», posto del proprietario, grpId]]."""
    out = []
    for b in bers:
        if b in (1, 2):
            continue
        for zid, tp in zone.items():
            if tp in ZONE_FUORI and b in zids.get(zid, []):
                o = obj.get(b) or {}
                out.append([b, ZONE_FUORI[tp], zown.get(zid) or o.get("ownerSeatId"), grp_vero(o, obj) if o else None])
                break
    return out


RIASSUNTO = "[Message summarized because"
TIPI_LETTERA = {"CardType_Creature": "C", "CardType_Instant": "I", "CardType_Sorcery": "S", "CardType_Artifact": "A", "CardType_Enchantment": "E",
                "CardType_Planeswalker": "P", "CardType_Battle": "B", "CardType_Land": "L"}       # Arena non scrive i messaggi oltre 50 oggetti o 50 azioni: solo i conteggi


def leggi(righe):
    """Le righe di un pezzo di log -> dict(attacchi=[[turno, chi attacca, terre stappate di chi difende, sue terre]], fine=[[turno, chi, stappate, terre]],
    mano0=foto all'inizio del primo turno, foto=[[turno, chi e' di turno, foto]] alla fine di ogni turno, ultima=[turno, chi, foto] all'ultimo stato,
    riassunti=quanti messaggi Arena ha riassunto).
    Una foto: dict(c=[campo del posto 1, del posto 2] con [grpId, tappata, pedina, forza, costituzione], m=[mano 1, mano 2] coi grpId che si vedono, n=[carte in
    mano], v=[vite], g=[cimitero 1, 2], e=[esilio 1, 2]) (cimitero ed esilio per proprietario, 12 nov 2026: «aggiungiamo cimitero e esilio»). Una carta che Arena
    ha messo in un cimitero o in un esilio senza mandarne i dati (un messaggio riassunto) ha grpId 0: si vede che c'e', non quale e'.
    Debug del 12 nov 2026 (Autore: «riguarda in maniera approfondita come il replayer legge i log e le azioni, debugga tutto»): gli oggetti cancellati si
    leggono da diffDeletedInstanceIds; chi e' in campo lo dicono le zone, non la zona scritta nell'oggetto; le vite a 0; l'annullamento di Arena (undo: uno
    stato Full con prevGameStateId che torna indietro) toglie quello che era stato annotato da quello stato in poi; lo step vecchio nelle fasi principali."""
    obj, zone, ti = {}, {}, {}
    zown, zids, vite = {}, {}, {}
    # ogni cosa annotata porta lo stato del gioco in cui e' nata, cosi' un annullamento la toglie: [(stato, elemento)]
    st = dict(attacchi=[], fine=[], foto=[], momenti=[], mano0=None, pend=None, azioni=[], fasi=[], attivate=[])
    riassunti = 0
    visti_ts = {}               # {id dell'annotazione TargetSpec: stato}
    # i momenti in ordine (12 nov 2026, Autore: «una freccia che definisce quali carte interagiscono con quali altre, per vedere come si e' bloccato in
    # combattimento o contro cosa e' stato lanciato uno spot removal»): ["fine", t, chi, foto, None], ["comb", t, chi, foto, dict(att=[[id, bersaglio]],
    # blocchi=[[id, [attaccanti]]])] coi blocchi dichiarati, ["spell", t, chi, foto, dict(g=grpId, chi=posto, ab=abilita', bers=[id o posto])] quando una magia o
    # un'abilita' sceglie i bersagli (TargetSpec)
    # gli istantanei e le stregonerie in pila (12 nov 2026, Autore: «per le carte come day of judgement che distruggono grandi quantita' di board dovremmo
    # inventarci qualcosa che le mostri nel turno prima che finiscano nel cimitero e contro cosa hanno effetto di massa»): il momento nasce quando la magia
    # entra in pila, e quando lascia la pila si guarda cosa manca dal campo di allora («colpiti»)
    in_pila, mom_di = {}, {}       # {id della magia: (stato, momento, id in campo allora)}, {id della magia: (stato, momento)}
    # i permanenti che una magia ha tolto lei dal campo (13 nov 2026, Autore: «la carta settle the wreckage dovrebbe esiliare le creature attaccanti ma nel
    # replayer la freccia punta ai punti vita del giocatore»): Arena scrive in ogni ZoneTransfer chi l'ha causata (affectorId); il bersaglio di Settle the
    # Wreckage e' il giocatore, quello che esilia sono le sue creature. {id della magia: {id in campo prima di lasciarlo}}
    fatti_da, risolve = {}, set()      # risolve: le magie fra ResolutionStart e ResolutionComplete

    def valore(o, k):
        """Forza o costituzione di una creatura: Arena non scrive i valori a zero (power {} o assente), quindi una 0/2 e' 0/2, non una non creatura."""
        v = o.get(k)
        return v.get("value", 0) if isinstance(v, dict) else (v if v is not None else 0)

    def ids_di(tipo):
        return [i for zid, tp in zone.items() if tp == tipo for i in zids.get(zid, [])]

    def foto():
        c, m, n, g, e = [[], []], [[], []], [0, 0], [[], []], [[], []]
        for zid, tp in zone.items():
            ids = zids.get(zid, [])
            if tp in ("ZoneType_Graveyard", "ZoneType_Exile"):
                lato = (g if tp == "ZoneType_Graveyard" else e)
                for i in ids:
                    o = obj.get(i)
                    if o is None and zown.get(zid) in (1, 2):         # in una zona pubblica ma mai mandata (messaggio riassunto)
                        lato[zown[zid] - 1].append(0)
                    elif o and o.get("grpId") and o.get("type") == "GameObjectType_Card" and o.get("ownerSeatId") in (1, 2):
                        lato[o["ownerSeatId"] - 1].append(o["grpId"])
            elif tp == "ZoneType_Battlefield":
                for i in ids:
                    o = obj.get(i)
                    if o and o.get("grpId") and o.get("type") in ("GameObjectType_Card", "GameObjectType_Token") and o.get("controllerSeatId") in (1, 2):
                        crea = "CardType_Creature" in (o.get("cardTypes") or [])
                        c[o["controllerSeatId"] - 1].append([o["grpId"], 1 if o.get("isTapped") else 0, 1 if o["type"] == "GameObjectType_Token" else 0,
                                                             valore(o, "power") if crea else None, valore(o, "toughness") if crea else None,
                                                             o.get("instanceId")])
            elif tp == "ZoneType_Hand" and zown.get(zid) in (1, 2):
                k = zown[zid] - 1
                n[k] = len(ids)
                m[k] = [obj[i]["grpId"] for i in ids if i in obj and obj[i].get("grpId")]
        return dict(c=c, m=m, n=n, v=[vite.get(1), vite.get(2)], g=g, e=e)

    def terre(seat, campo):
        tot = stap = 0
        for i in campo:
            o = obj.get(i) or {}
            if o.get("controllerSeatId") == seat and "CardType_Land" in (o.get("cardTypes") or []):
                tot += 1
                stap += 0 if o.get("isTapped") else 1
        return stap, tot

    def annulla(fino):
        """L'annullamento di Arena: via quello che e' nato da questo stato in poi (lo stato Full che segue lo rimanda)."""
        for k in ("attacchi", "fine", "foto", "momenti", "azioni", "fasi", "attivate"):
            st[k] = [x for x in st[k] if x[0] < fino]
        for dd in (mom_di, in_pila):
            for k in [k for k, v in dd.items() if v[0] >= fino]:
                dd.pop(k)
        for k in [k for k, v in visti_ts.items() if v >= fino]:
            visti_ts.pop(k)
        if st["mano0"] is not None and st["mano0"][0] >= fino:
            st["mano0"] = None
        if st["pend"] and st["pend"][1] >= fino:
            st["pend"] = None

    for r in righe:
        if r.startswith(RIASSUNTO):
            riassunti += 1
            continue
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
            sid = gs.get("gameStateId") or 0
            if gs.get("update") == "GameStateUpdate_Undo" and gs.get("prevGameStateId"):
                annulla(gs["prevGameStateId"])
            if gs.get("type") == "GameStateType_Full":
                obj, zone, zown, zids = {}, {}, {}, {}
            for z in gs.get("zones") or []:
                zone[z.get("zoneId")] = z.get("type")
                zown[z.get("zoneId")] = z.get("ownerSeatId")
                zids[z.get("zoneId")] = z.get("objectInstanceIds") or []     # una zona vuota arriva senza la lista
            vite_da(gs, vite)
            for o in gs.get("gameObjects") or []:
                obj[o.get("instanceId")] = o
            for x in cancellati(gs):
                obj.pop(x, None)
            turno_da(gs, ti)
            orig = {}
            for a in gs.get("annotations") or []:
                if "AnnotationType_ObjectIdChanged" in (a.get("type") or []):
                    det = {x.get("key"): (x.get("valueInt32") or [None])[0] for x in a.get("details") or []}
                    if det.get("orig_id") and det.get("new_id"):
                        orig[det["new_id"]] = det["orig_id"]
            pila_ora = set(ids_di("ZoneType_Stack"))
            finite = set()
            for a in gs.get("annotations") or []:
                if "AnnotationType_ResolutionStart" in (a.get("type") or []):
                    risolve.add(a.get("affectorId"))
                elif "AnnotationType_ResolutionComplete" in (a.get("type") or []):
                    finite.add(a.get("affectorId"))
            for a in gs.get("annotations") or []:
                # solo mentre la magia si risolve (Arena esilia nel messaggio di ResolutionStart, con la magia ancora in pila) o quando lascia la pila: un
                # sacrificio come costo (Eaten Alive, Cathar Commando) si paga mentre entra in pila e non e' il suo effetto
                if "AnnotationType_ZoneTransfer" in (a.get("type") or []) and a.get("affectorId") in in_pila                         and (a["affectorId"] in risolve or a["affectorId"] not in pila_ora):
                    src = next(((x.get("valueInt32") or [None])[0] for x in a.get("details") or [] if x.get("key") == "zone_src"), None)
                    if zone.get(src) == "ZoneType_Battlefield":
                        fatti_da.setdefault(a["affectorId"], set()).update(orig.get(x, x) for x in a.get("affectedIds") or [])
            risolve -= finite
            t, att = ti.get("turnNumber"), ti.get("activePlayer")
            if t is None or att is None:
                continue
            campo = ids_di("ZoneType_Battlefield")
            sul = [obj[i] for i in campo if i in obj]
            # le azioni del turno (13 nov 2026, Autore: «filtri avanzati per noi e per oppo ... che tipo di carte giochiamo: es t1 instant oppure T3 play creature
            # attack w 2 creature»): ogni terra giocata e ogni magia lanciata, [turno, posto, «terra»|«magia», grpId, tipi in lettere (C creatura, I istantaneo,
            # S stregoneria, A artefatto, E incantesimo, P planeswalker, B battaglia, L terra)]
            # le abilita' attivate (VERSIONE 15, 13 nov 2026, Autore: «io posso dirti che saccare reliquia dopo draw step di Oppo migliora le mie
            # possibilita' di vittoria ... non credo proprio sia una cosa che un programma riesce a stimare», poi «Sì, aggiungilo»): Arena scrive ogni azione
            # del giocatore in UserActionTaken, actionType 1 lanciare, 2 attivare un'abilita' (non di mana), 3 giocare una terra, 4 un'abilita' di mana;
            # affectorId e' il posto, affectedIds l'abilita' in pila, che risale alla sua carta. [turno, posto, grpId della carta, fase, step, chi e' di turno]
            for a in gs.get("annotations") or []:
                if "AnnotationType_UserActionTaken" not in (a.get("type") or []) or a.get("affectorId") not in (1, 2):
                    continue
                if next(((x.get("valueInt32") or [None])[0] for x in a.get("details") or [] if x.get("key") == "actionType"), None) != 2:
                    continue
                for x in a.get("affectedIds") or []:
                    o = obj.get(x)
                    g_ = (grp_vero(o, obj) if o else 0) or 0
                    st["attivate"].append((sid, [t, a["affectorId"], g_, ti.get("phase") or "", ti.get("step") or "", att]))
            for a in gs.get("annotations") or []:
                if "AnnotationType_ZoneTransfer" not in (a.get("type") or []):
                    continue
                cat = next(((x.get("valueString") or [None])[0] for x in a.get("details") or [] if x.get("key") == "category"), None)
                if cat == "Draw":       # le pescate (13 nov 2026): di chi e' la mano in cui arriva la carta; la sua carta e' nascosta, grpId 0
                    dest = next(((x.get("valueInt32") or [None])[0] for x in a.get("details") or [] if x.get("key") == "zone_dest"), None)
                    chi = zown.get(dest)
                    if chi in (1, 2):
                        for x in a.get("affectedIds") or []:
                            o = obj.get(x)
                            st["azioni"].append((sid, [t, chi, "pesca", (grp_vero(o, obj) if o else 0) or 0, ""]))
                    continue
                if cat not in ("PlayLand", "CastSpell"):
                    continue
                for x in a.get("affectedIds") or []:
                    o = obj.get(x)
                    if o and o.get("controllerSeatId") in (1, 2):
                        st["azioni"].append((sid, [t, o["controllerSeatId"], "terra" if cat == "PlayLand" else "magia", grp_vero(o, obj) or 0,
                                                "".join(TIPI_LETTERA[k] for k in o.get("cardTypes") or [] if k in TIPI_LETTERA)]))
                        if cat == "CastSpell":      # la fase in cui e' stata lanciata (VERSIONE 14): prima o dopo il combattimento, nel turno di chi
                            st["fasi"].append((sid, [t, o["controllerSeatId"], grp_vero(o, obj) or 0, ti.get("phase") or ti.get("step") or ""]))
            attaccanti = [o for o in sul if o.get("attackState") in ("AttackState_Declared", "AttackState_Attacking")]
            if t not in {a[1][0] for a in st["attacchi"]} and any(o.get("controllerSeatId") == att for o in attaccanti):
                difende = 2 if att == 1 else 1
                s, n = terre(difende, campo)
                st["attacchi"].append((sid, [t, att, s, n]))
            if t == 1 and st["mano0"] is None:
                st["mano0"] = (sid, foto())
            # il combattimento: attaccanti e blocchi dichiarati; si tiene l'ultimo stato prima del danno, al suo posto fra i momenti
            pend = st["pend"]
            in_comb = ti.get("step") in ("Step_DeclareAttack", "Step_DeclareBlock")
            if in_comb and t not in {x[1][1] for x in st["momenti"] if x[1][0] == "comb"}:
                att_ids = [[o["instanceId"], (o.get("attackInfo") or {}).get("targetId")] for o in attaccanti]
                if att_ids:
                    blocchi = [[o["instanceId"], (o.get("blockInfo") or {}).get("attackerIds") or []] for o in sul if (o.get("blockInfo") or {}).get("attackerIds")]
                    posto = pend[0] if pend else len(st["momenti"])
                    # chi poteva attaccare (gli attaccanti e le sue creature stappate senza debolezza da evocazione) e le terre stappate di chi difende: per
                    # «ha attaccato con tutto» e «contro mana aperto» (13 nov 2026)
                    pot = sum(1 for o in sul if o.get("controllerSeatId") == att and "CardType_Creature" in (o.get("cardTypes") or [])
                              and (o in attaccanti or (not o.get("isTapped") and not o.get("hasSummoningSickness"))))
                    aperte = terre(2 if att == 1 else 1, campo)[0]
                    st["pend"] = (posto, pend[1] if pend else sid, ["comb", t, att, foto(), dict(att=att_ids, blocchi=blocchi, pot=pot, aperte=aperte)])
            elif pend:
                st["momenti"].insert(pend[0], (pend[1], pend[2]))
                st["pend"] = None
            pila_ids = set(ids_di("ZoneType_Stack"))
            in_campo = set(campo)
            for i in list(in_pila):         # una magia che ha lasciato la pila: cosa manca dal campo di quando e' stata lanciata
                if i not in pila_ids:
                    _s, m_, prima_ = in_pila.pop(i)
                    m_[4]["colpiti"] = sorted(x for x in prima_ if x not in in_campo)
                    m_[4]["fatti"] = sorted(x for x in fatti_da.pop(i, ()) if x in prima_)
            for i in pila_ids:              # un istantaneo o una stregoneria appena entrati in pila
                o = obj.get(i)
                if i in mom_di or not o or o.get("type") != "GameObjectType_Card" or not o.get("grpId"):
                    continue
                if not {"CardType_Instant", "CardType_Sorcery"} & set(o.get("cardTypes") or []):
                    continue
                m_ = ["spell", t, att, foto(), dict(g=o["grpId"], chi=o.get("controllerSeatId"), ab=False, bers=[], colpiti=[])]
                st["momenti"].append((sid, m_))
                mom_di[i] = (sid, m_)
                in_pila[i] = (sid, m_, set(in_campo))
            # le magie e le abilita' coi bersagli (una magia gia' in pila prende i suoi bersagli)
            for a in (gs.get("persistentAnnotations") or []) + (gs.get("annotations") or []):
                if "AnnotationType_TargetSpec" in (a.get("type") or []) and a.get("id") not in visti_ts:
                    visti_ts[a.get("id")] = sid
                    if a.get("affectorId") in mom_di:
                        mom_di[a["affectorId"]][1][4]["bers"] = a.get("affectedIds") or []
                        mom_di[a["affectorId"]][1][4]["fuori"] = fuori_campo(a.get("affectedIds") or [], zone, zids, zown, obj)
                        continue
                    sp = obj.get(a.get("affectorId"))
                    if not sp:
                        continue
                    ab = sp.get("type") == "GameObjectType_Ability"
                    g = grp_vero(sp, obj)
                    if g:
                        m_ = ["spell", t, att, foto(), dict(g=g, chi=sp.get("controllerSeatId"), ab=ab, bers=a.get("affectedIds") or [], colpiti=[],
                                                            fuori=fuori_campo(a.get("affectedIds") or [], zone, zids, zown, obj))]
                        st["momenti"].append((sid, m_))
                        if not ab:
                            mom_di[a["affectorId"]] = (sid, m_)
                        if a["affectorId"] not in in_pila:      # anche un'abilita' (un sacrificio, un esilio): cosa toglie quando lascia la pila
                            in_pila[a["affectorId"]] = (sid, m_, set(in_campo))
            if ti.get("step") == "Step_End" and t not in {x[1][0] for x in st["fine"]}:
                s, n = terre(att, campo)
                st["fine"].append((sid, [t, att, s, n]))
                f_ = foto()
                st["foto"].append((sid, [t, att, f_]))
                st["momenti"].append((sid, ["fine", t, att, f_, None]))
    if st["pend"]:
        st["momenti"].insert(st["pend"][0], (st["pend"][1], st["pend"][2]))
    fine_campo = set(ids_di("ZoneType_Battlefield"))
    for i, (_s, m_, prima_) in in_pila.items():     # la partita finita con la magia ancora in pila (concessa subito dopo l'esilio): si chiude qui
        m_[4]["colpiti"] = sorted(x for x in prima_ if x not in fine_campo)
        m_[4]["fatti"] = sorted(x for x in fatti_da.get(i, ()) if x in prima_)
    ultima = [ti.get("turnNumber"), ti.get("activePlayer"), foto()] if ti.get("turnNumber") else None
    via = lambda lst: [x[1] for x in lst]
    return dict(azioni=via(st["azioni"]), fasi=via(st["fasi"]), attivate=via(st["attivate"]), attacchi=via(st["attacchi"]), fine=via(st["fine"]), mano0=st["mano0"][1] if st["mano0"] else None, foto=via(st["foto"]), ultima=ultima,
                momenti=via(st["momenti"]), riassunti=riassunti)


_INDICE = {}        # {file partita.json: matchId}: un pezzo di log non cambia, si legge una volta per processo (13 nov 2026: 450 file a ogni rilettura)


def indice():
    """{matchId: cartella} dei pezzi di log."""
    out = {}
    for f in glob.glob(os.path.join(CARTELLA, "*", "partita.json")):
        if f not in _INDICE:
            try:
                with open(f, encoding="utf-8") as h:
                    _INDICE[f] = json.load(h).get("matchId")
            except (OSError, ValueError):
                continue
        mid = _INDICE[f]
        if mid:
            out[mid] = os.path.dirname(f)
    return out


_COPIA_MEM = {}     # la copia su disco gia' letta: {"chiave": (mtime, misura), "c": contenuto}


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
                d["dove"] = [chiave, i, j]      # il replay azione per azione rilegge solo questo pezzo (replay_log.righe_partita)
                dati[mid] = d
                nuove += 1
        letti[chiave] = misura
    return nuove


def tutti(ids=None, archivi=True):
    """{matchId: dato}: dalla copia, le nuove dai pezzi di log e (archivi) dai log archiviati, poi salvate. ids: solo queste partite."""
    try:        # la copia (13 MB) si rilegge solo se il file e' cambiato
        st_ = os.stat(COPIA)
        chiave = (st_.st_mtime, st_.st_size)
        if _COPIA_MEM.get("chiave") == chiave:
            c = _COPIA_MEM["c"]
        else:
            with open(COPIA, encoding="utf-8") as h:
                c = json.load(h)
            _COPIA_MEM.update(chiave=chiave, c=c)
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
            st_ = os.stat(COPIA)
            _COPIA_MEM.update(chiave=(st_.st_mtime, st_.st_size), c=dict(versione=VERSIONE, partite=dati, archivi=letti))
        except OSError:
            pass
    return dati


def situazioni(d, seat):
    """Le situazioni del mana aperto di una partita, dal tuo posto: {chiave: True, False o None}."""
    chiavi = ("io_att_aperto", "io_att_chiuso", "lui_att_aperto", "io_passa_aperto", "lui_passa_aperto", "io_blocca", "io_difende", "io_tutto",
              "io_tutto_aperto")
    if not d or seat is None:
        return {k: None for k in chiavi}
    mie = [a for a in d["attacchi"] if a[1] == seat]
    sue = [a for a in d["attacchi"] if a[1] != seat]
    fm = [f for f in d["fine"] if f[1] == seat and f[3] >= 3]      # dal momento che hai almeno 3 terre: prima passare con 2 aperte non e' una scelta
    fs = [f for f in d["fine"] if f[1] != seat and f[3] >= 3]
    # i combattimenti (13 nov 2026, Autore: «win / loss in difesa ... non attaccare con tutto se avversario ha mana stappato»), dai momenti della VERSIONE 12:
    # chi attacca, quanti attaccanti, chi poteva attaccare (pot), i blocchi, le terre stappate di chi difende (aperte). None quando la situazione non c'e' stata
    comb = [(att == seat, info) for kind, _t, att, _f, info in d.get("momenti") or [] if kind == "comb" and info and info.get("att")]
    suoi = [i for mio, i in comb if not mio]
    miei = [i for mio, i in comb if mio and (i.get("pot") or 0) >= 2]          # attacchi in cui avevi almeno 2 creature che potevano attaccare
    miei_ap = [i for i in miei if (i.get("aperte") or 0) >= 2]
    tutto = lambda i: len(i["att"]) >= i["pot"]
    n_s, n_m = len(suoi), sum(1 for mio, _i in comb if mio)
    return dict(io_att_aperto=any(a[2] >= 2 for a in mie), io_att_chiuso=any(a[2] == 0 and a[3] >= 2 for a in mie), lui_att_aperto=any(a[2] >= 2 for a in sue),
                io_passa_aperto=any(f[2] >= 2 for f in fm), lui_passa_aperto=any(f[2] >= 2 for f in fs),
                io_blocca=any(i.get("blocchi") for i in suoi) if suoi else None,
                io_difende=(n_s > n_m) if n_s != n_m else None,
                io_tutto=any(tutto(i) for i in miei) if miei else None,
                io_tutto_aperto=any(tutto(i) for i in miei_ap) if miei_ap else None)


def prova():
    """Un log finto: tu (seat 1) attacchi al turno 3 con lui a 2 terre stappate, lui attacca al 4 con te tappato; i passi End."""
    def gs(**k):
        return "[UnityCrossThreadLogger]x " + json.dumps(dict(greToClientEvent=dict(greToClientMessages=[dict(gameStateMessage=k)])))
    terra = lambda i, seat, tap: dict(instanceId=i, controllerSeatId=seat, cardTypes=["CardType_Land"], zoneId=28, **({"isTapped": True} if tap else {}))
    crea = lambda i, seat, att: dict(instanceId=i, controllerSeatId=seat, cardTypes=["CardType_Creature"], zoneId=28, **({"attackState": "AttackState_Declared"} if att else {}))
    campo = lambda *ids: [dict(zoneId=28, type="ZoneType_Battlefield", objectInstanceIds=list(ids))]       # chi e' in campo lo dice la zona, come nei log veri
    righe = [gs(type="GameStateType_Full", zones=campo(1, 2, 3, 4, 5, 10), turnInfo=dict(turnNumber=3, activePlayer=1, step="Step_BeginCombat"),
                gameObjects=[terra(1, 1, False), terra(2, 1, False), terra(3, 1, True), terra(4, 2, False), terra(5, 2, False), crea(10, 1, False)]),
             gs(type="GameStateType_Diff", turnInfo=dict(step="Step_DeclareAttack"), gameObjects=[crea(10, 1, True)]),
             gs(type="GameStateType_Diff", turnInfo=dict(step="Step_End"), gameObjects=[crea(10, 1, False)]),
             gs(type="GameStateType_Diff", turnInfo=dict(turnNumber=4, activePlayer=2, step="Step_DeclareAttack"), zones=campo(1, 2, 3, 4, 5, 10, 11),
                gameObjects=[terra(1, 1, True), terra(2, 1, True), terra(3, 1, True), dict(crea(11, 2, True))]),
             gs(type="GameStateType_Diff", turnInfo=dict(step="Step_End"), gameObjects=[terra(4, 2, True)])]
    d = leggi(righe)
    casi = [("gli attacchi: al T3 attacchi tu e lui ha 2 terre stappate su 2; al T4 attacca lui e tu hai 0 stappate su 3", d["attacchi"] == [[3, 1, 2, 2], [4, 2, 0, 3]]),
            ("la fine dei turni: T3 tu con 2 stappate su 3, T4 lui con 1 su 2", d["fine"] == [[3, 1, 2, 3], [4, 2, 1, 2]])]
    s = situazioni(d, 1)
    casi.append(("situazioni dal tuo posto: attacchi contro 2 aperte, lui attacca contro te tappato, passi con 2 aperte", s["io_att_aperto"] and not s["io_att_chiuso"]
                 and not s["lui_att_aperto"] and s["io_passa_aperto"] and not s["lui_passa_aperto"]))
    casi.append(("negativa: senza log niente situazioni", all(v is None for v in situazioni(None, 1).values())))
    vuoto = leggi(["niente", "{rotto"])
    casi.append(("negativa: le righe senza stato del gioco non contano", vuoto["attacchi"] == [] and vuoto["fine"] == [] and not vuoto["foto"] and vuoto["ultima"] is None))
    # le foto: la mano tenuta al primo turno, la board alla fine del turno (la pedina, la carta tappata), le vite; la sua mano solo contata
    carta = lambda i, g, z, seat, **k: dict(instanceId=i, grpId=g, type=k.pop("tipo", "GameObjectType_Card"), zoneId=z, controllerSeatId=seat, ownerSeatId=seat, **k)
    fz = [gs(type="GameStateType_Full", zones=[dict(zoneId=28, type="ZoneType_Battlefield"), dict(zoneId=31, type="ZoneType_Hand", ownerSeatId=1, objectInstanceIds=[1, 2]),
                                               dict(zoneId=35, type="ZoneType_Hand", ownerSeatId=2, objectInstanceIds=[7, 8, 9])],
             players=[dict(systemSeatNumber=1, lifeTotal=20), dict(systemSeatNumber=2, lifeTotal=20)], turnInfo=dict(turnNumber=1, activePlayer=1, step="Step_Upkeep"),
             gameObjects=[carta(1, 100, 31, 1), carta(2, 200, 31, 1)]),
          gs(type="GameStateType_Diff", zones=[dict(zoneId=28, type="ZoneType_Battlefield", objectInstanceIds=[3, 4]), dict(zoneId=31, type="ZoneType_Hand", ownerSeatId=1,
                                                objectInstanceIds=[2])], players=[dict(systemSeatNumber=2, lifeTotal=17)], turnInfo=dict(step="Step_End"),
             gameObjects=[carta(3, 100, 28, 1, isTapped=True), carta(4, 900, 28, 1, tipo="GameObjectType_Token")])]
    df = leggi(fz)
    casi.append(("le foto: la mano tenuta al primo turno (la sua solo contata), la board a fine turno con tappata e pedina, le vite",
                 df["mano0"]["m"] == [[100, 200], []] and df["mano0"]["n"] == [2, 3] and df["foto"][0][:2] == [1, 1]
                 and df["foto"][0][2]["c"] == [[[100, 1, 0, None, None, 3], [900, 0, 1, None, None, 4]], []] and df["foto"][0][2]["m"][0] == [200] and df["foto"][0][2]["v"] == [20, 17]
                 and df["ultima"][0] == 1))
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
        ar, i0, j0 = dati[a]["dove"]
        with open(os.path.join(LOGDIR, ar), "rb") as h_:
            pezzo = h_.read()[i0:j0].decode("utf-8")
        casi.append(("dagli archivi: «dove» porta al pezzo della partita", ar == "2026-11-01_Player.log" and a in pezzo and b not in pezzo))
        casi.append(("negativa: un archivio gia' guardato non si rilegge", dagli_archivi(dati, letti, None) == 0 and "2026-11-01_Player.log" in letti))
    finally:
        LOGDIR = vecchio
    # i momenti del combattimento e della magia col bersaglio: tu (1) attacchi con 10, lui blocca con 20; poi lanci 555 su 20
    cr = lambda i, seat, **k: dict(instanceId=i, grpId=100 + i, type="GameObjectType_Card", zoneId=28, controllerSeatId=seat, ownerSeatId=seat,
                                   cardTypes=["CardType_Creature"], **k)
    fc = [gs(type="GameStateType_Full", zones=[dict(zoneId=28, type="ZoneType_Battlefield", objectInstanceIds=[10, 20]), dict(zoneId=27, type="ZoneType_Stack")],
             turnInfo=dict(turnNumber=5, activePlayer=1, step="Step_DeclareAttack"),
             gameObjects=[cr(10, 1, attackState="AttackState_Attacking", attackInfo=dict(targetId=2)), cr(20, 2)]),
          gs(type="GameStateType_Diff", turnInfo=dict(step="Step_DeclareBlock"), gameObjects=[cr(20, 2, blockState="BlockState_Blocking", blockInfo=dict(attackerIds=[10]))]),
          gs(type="GameStateType_Diff", turnInfo=dict(step="Step_CombatDamage")),
          gs(type="GameStateType_Diff", turnInfo=dict(step="Step_Main2"), gameObjects=[dict(instanceId=30, grpId=555, type="GameObjectType_Card", zoneId=27,
                                                                                            controllerSeatId=1, ownerSeatId=1)],
             persistentAnnotations=[dict(id=9, type=["AnnotationType_TargetSpec"], affectorId=30, affectedIds=[20])]),
          gs(type="GameStateType_Diff", turnInfo=dict(step="Step_End"))]
    dm = leggi(fc)["momenti"]
    # chi poteva attaccare e le terre stappate di chi difende (13 nov 2026): la 10 attacca, la 11 stappata poteva, la 12 e' appena entrata, la 13 e' tappata;
    # chi difende ha 2 terre, una stappata
    tl = lambda i, seat, **k: dict(instanceId=i, grpId=1, type="GameObjectType_Card", zoneId=28, controllerSeatId=seat, ownerSeatId=seat, cardTypes=["CardType_Land"], **k)
    fp = [gs(type="GameStateType_Full", zones=[dict(zoneId=28, type="ZoneType_Battlefield", objectInstanceIds=[10, 11, 12, 13, 40, 41]), dict(zoneId=27, type="ZoneType_Stack")],
             turnInfo=dict(turnNumber=5, activePlayer=1, step="Step_DeclareAttack"),
             gameObjects=[cr(10, 1, attackState="AttackState_Attacking", attackInfo=dict(targetId=2), isTapped=True), cr(11, 1), cr(12, 1, hasSummoningSickness=True),
                          cr(13, 1, isTapped=True), tl(40, 2), tl(41, 2, isTapped=True)]),
          gs(type="GameStateType_Diff", turnInfo=dict(step="Step_CombatDamage"))]
    cp = [m_[4] for m_ in leggi(fp)["momenti"] if m_[0] == "comb"]
    casi.append(("il combattimento: chi poteva attaccare (l'attaccante e la creatura stappata) e le terre stappate di chi difende",
                 len(cp) == 1 and cp[0]["pot"] == 2 and cp[0]["aperte"] == 1))
    casi.append(("negativa: la creatura appena entrata e quella tappata non potevano attaccare", cp and cp[0]["pot"] != 4 and cp[0]["pot"] != 3))
    # le situazioni dei combattimenti per le ricerche di Spots: tu (1) attacchi con tutto (2 su 2) contro 3 terre stappate; lui attacca due volte, blocchi una
    cb = lambda att, n, pot, ap, blk: ["comb", 3, att, None, dict(att=[[k, 2] for k in range(n)], blocchi=[[9, [0]]] if blk else [], pot=pot, aperte=ap)]
    sd = situazioni(dict(attacchi=[], fine=[], momenti=[cb(1, 2, 2, 3, False), cb(2, 1, 1, 0, True), cb(2, 2, 2, 0, False)]), 1)
    casi.append(("le situazioni del combattimento: hai bloccato, hai difeso piu' che attaccato, hai attaccato con tutto contro mana aperto",
                 sd["io_blocca"] is True and sd["io_difende"] is True and sd["io_tutto"] is True and sd["io_tutto_aperto"] is True))
    sn = situazioni(dict(attacchi=[], fine=[], momenti=[cb(1, 1, 3, 3, False)]), 1)
    casi.append(("negativa: un attacco con 1 creatura su 3 contro mana aperto e' No; senza suoi attacchi il blocco non si sa (None)",
                 sn["io_tutto_aperto"] is False and sn["io_tutto"] is False and sn["io_blocca"] is None and sn["io_difende"] is False))
    # le azioni del turno: una terra giocata, una creatura lanciata; una terra messa in campo da un effetto no
    def zt_(i, cat):
        return dict(type=["AnnotationType_ZoneTransfer"], affectedIds=[i], details=[dict(key="category", valueString=[cat])])
    fa = [gs(type="GameStateType_Full", zones=[dict(zoneId=28, type="ZoneType_Battlefield"), dict(zoneId=27, type="ZoneType_Stack")],
             turnInfo=dict(turnNumber=3, activePlayer=2, phase="Phase_Main1")),
          gs(type="GameStateType_Diff", zones=[dict(zoneId=28, type="ZoneType_Battlefield", objectInstanceIds=[50, 52])], gameObjects=[tl(50, 2), tl(52, 2)],
             annotations=[zt_(50, "PlayLand"), zt_(52, "Put")]),
          gs(type="GameStateType_Diff", zones=[dict(zoneId=27, type="ZoneType_Stack", objectInstanceIds=[51])],
             gameObjects=[dict(cr(51, 2), zoneId=27, cardTypes=["CardType_Artifact", "CardType_Creature"])], annotations=[zt_(51, "CastSpell")])]
    az = leggi(fa)["azioni"]
    casi.append(("le azioni del turno: la terra giocata e la creatura artefatto lanciata, col turno, il posto e i tipi",
                 az == [[3, 2, "terra", 1, "L"], [3, 2, "magia", 151, "AC"]]))
    # le pescate (VERSIONE 13): chi riceve la carta lo dice la mano di destinazione; la sua carta e' nascosta (niente grpId)
    zd = lambda i, dest: dict(type=["AnnotationType_ZoneTransfer"], affectedIds=[i], details=[dict(key="zone_dest", valueInt32=[dest]),
                                                                                              dict(key="category", valueString=["Draw"])])
    fd = [gs(type="GameStateType_Full", zones=[dict(zoneId=31, type="ZoneType_Hand", ownerSeatId=1), dict(zoneId=35, type="ZoneType_Hand", ownerSeatId=2)],
             turnInfo=dict(turnNumber=2, activePlayer=2, phase="Phase_Beginning")),
          gs(type="GameStateType_Diff", gameObjects=[dict(instanceId=60, grpId=300, type="GameObjectType_Card", zoneId=31, controllerSeatId=1, ownerSeatId=1)],
             annotations=[zd(60, 31), zd(61, 35), zd(62, 99)])]
    casi.append(("le pescate: la tua col grpId, la sua nascosta col suo posto; una verso una zona che non e' una mano no",
                 leggi(fd)["azioni"] == [[2, 1, "pesca", 300, ""], [2, 2, "pesca", 0, ""]]))
    casi.append(("i momenti: il combattimento coi blocchi, la magia col bersaglio, la fine del turno, in ordine",
                 [m_[0] for m_ in dm] == ["comb", "spell", "fine"] and {k: dm[0][4][k] for k in ("att", "blocchi")} == dict(att=[[10, 2]], blocchi=[[20, [10]]])
                 and dm[1][4]["g"] == 555 and dm[1][4]["bers"] == [20]))
    # un board wipe: una stregoneria senza bersagli entra in pila, si risolve, e dal campo mancano le due creature
    sw = lambda i, **k: dict(instanceId=i, grpId=777, type="GameObjectType_Card", zoneId=27, controllerSeatId=2, ownerSeatId=2, cardTypes=["CardType_Sorcery"], **k)
    fw = [gs(type="GameStateType_Full", zones=[dict(zoneId=28, type="ZoneType_Battlefield", objectInstanceIds=[10, 20]), dict(zoneId=27, type="ZoneType_Stack")],
             turnInfo=dict(turnNumber=6, activePlayer=2, step="Step_Main1"), gameObjects=[cr(10, 1), cr(20, 2)]),
          gs(type="GameStateType_Diff", zones=[dict(zoneId=27, type="ZoneType_Stack", objectInstanceIds=[50])], gameObjects=[sw(50)]),
          gs(type="GameStateType_Diff", zones=[dict(zoneId=27, type="ZoneType_Stack"), dict(zoneId=28, type="ZoneType_Battlefield")], deletedInstanceIds=[10, 20, 50])]
    mw = [m_ for m_ in leggi(fw)["momenti"] if m_[0] == "spell"]
    casi.append(("un board wipe: il suo momento in pila, la tavola di prima e i due permanenti tolti", len(mw) == 1 and mw[0][4]["g"] == 777
                 and mw[0][4]["colpiti"] == [10, 20] and len(mw[0][3]["c"][0]) == 1))
    casi.append(("negativa: senza attaccanti niente momento di combattimento", not [m_ for m_ in leggi(fz)["momenti"] if m_[0] == "comb"]))
    # Settle the Wreckage (13 nov 2026): il bersaglio e' il giocatore 1; la magia esilia la creatura 10 (affectorId, col cambio d'id), la 20 muore per altro
    def settle(affettore, costo=False):
        es = dict(type=["AnnotationType_ZoneTransfer"], affectedIds=[11], details=[dict(key="zone_src", valueInt32=[28]), dict(key="category", valueString=["Exile"])])
        if affettore:
            es["affectorId"] = affettore
        fs = [gs(type="GameStateType_Full", zones=[dict(zoneId=28, type="ZoneType_Battlefield", objectInstanceIds=[10, 20]), dict(zoneId=27, type="ZoneType_Stack")],
                 turnInfo=dict(turnNumber=6, activePlayer=1, step="Step_DeclareBlock"), gameObjects=[cr(10, 1), cr(20, 1)]),
              gs(type="GameStateType_Diff", zones=[dict(zoneId=27, type="ZoneType_Stack", objectInstanceIds=[60])],
                 gameObjects=[dict(sw(60), cardTypes=["CardType_Instant"])],
                 persistentAnnotations=[dict(id=70, type=["AnnotationType_TargetSpec"], affectorId=60, affectedIds=[1])]),
              gs(type="GameStateType_Diff", zones=[dict(zoneId=27, type="ZoneType_Stack", objectInstanceIds=[60] if costo else [])]
                 + ([] if costo else [dict(zoneId=28, type="ZoneType_Battlefield")]),
                 diffDeletedInstanceIds=[10] if costo else [10, 20, 60],
                 annotations=[dict(type=["AnnotationType_ObjectIdChanged"], affectedIds=[10], details=[dict(key="orig_id", valueInt32=[10]),
                                                                                                      dict(key="new_id", valueInt32=[11])]), es])]
        if costo:       # la creatura sacrificata mentre la magia e' ancora in pila (un costo), poi la magia si risolve senza togliere niente
            fs.append(gs(type="GameStateType_Diff", zones=[dict(zoneId=27, type="ZoneType_Stack")], diffDeletedInstanceIds=[60]))
        return [m_[4] for m_ in leggi(fs)["momenti"] if m_[0] == "spell"]
    import dati_analizzatore as DA_
    ms = settle(60)
    casi.append(("Settle the Wreckage: bersaglio il giocatore, «fatti» la creatura esiliata dalla magia, non quella morta per altro",
                 len(ms) == 1 and ms[0]["bers"] == [1] and ms[0]["colpiti"] == [10, 20] and ms[0]["fatti"] == [10] and DA_.colpiti_di(ms[0]) == [10]))
    casi.append(("negativa: senza l'affectorId la magia non ha tolto niente", [DA_.colpiti_di(m_) for m_ in settle(None)] == [[]]))
    casi.append(("negativa: un sacrificio pagato mentre la magia e' in pila (un costo) non e' il suo effetto", [m_.get("fatti") for m_ in settle(60, costo=True)] == [[]]))
    # il debug del 12 nov 2026: l'annullamento toglie la magia annullata e lascia nascere il momento di quella vera, che riusa lo stesso id
    zt = lambda aid, cat: dict(type=["AnnotationType_ZoneTransfer"], affectedIds=[aid], details=[dict(key="category", valueString=[cat])])
    pl = lambda *ids: dict(zoneId=27, type="ZoneType_Stack", objectInstanceIds=list(ids))
    ist = lambda i, g: dict(instanceId=i, grpId=g, type="GameObjectType_Card", zoneId=27, controllerSeatId=1, ownerSeatId=1, cardTypes=["CardType_Instant"])
    t5 = dict(turnNumber=5, activePlayer=1, phase="Phase_Main1")
    fu = [gs(gameStateId=1, type="GameStateType_Full", zones=[dict(zoneId=28, type="ZoneType_Battlefield"), pl()], turnInfo=t5),
          gs(gameStateId=10, type="GameStateType_Diff", zones=[pl(4)], gameObjects=[ist(4, 200)], annotations=[zt(4, "CastSpell")]),
          gs(gameStateId=11, type="GameStateType_Full", update="GameStateUpdate_Undo", prevGameStateId=10, turnInfo=t5,
             zones=[dict(zoneId=28, type="ZoneType_Battlefield"), pl()]),
          gs(gameStateId=12, type="GameStateType_Diff", zones=[pl(4)], gameObjects=[ist(4, 300)], annotations=[zt(4, "CastSpell")])]
    mu = [m_[4]["g"] for m_ in leggi(fu)["momenti"] if m_[0] == "spell"]
    casi.append(("l'annullamento: via la magia annullata, il momento della magia vera c'e' (anche con lo stesso id)", mu == [300]))
    casi.append(("le fasi delle magie (VERSIONE 14): la magia lanciata in Main1, col turno, il posto e il grpId; negativa: quella annullata no",
                 leggi(fu)["fasi"] == [[5, 1, 300, "Phase_Main1"]] and leggi(fa)["fasi"] == [[3, 2, 151, "Phase_Main1"]]))
    # le abilita' attivate (VERSIONE 15): la Reliquia rotta dal posto 1 nel draw step del turno del posto 2; negative: l'abilita' di mana (actionType 4) e
    # quella annullata non ci sono
    uat = lambda chi, ab, tipo: dict(type=["AnnotationType_UserActionTaken"], affectorId=chi, affectedIds=[ab],
                                     details=[dict(key="actionType", valueInt32=[tipo]), dict(key="abilityGrpId", valueInt32=[9001])])
    rel = dict(instanceId=40, grpId=700, type="GameObjectType_Card", zoneId=28, controllerSeatId=1, ownerSeatId=1, cardTypes=["CardType_Artifact"])
    abi = lambda i: dict(instanceId=i, grpId=9001, type="GameObjectType_Ability", zoneId=27, controllerSeatId=1, parentId=40, objectSourceGrpId=700)
    td = dict(turnNumber=4, activePlayer=2, phase="Phase_Beginning", step="Step_Draw")
    fr = [gs(gameStateId=1, type="GameStateType_Full", zones=[dict(zoneId=28, type="ZoneType_Battlefield", objectInstanceIds=[40]), pl()], turnInfo=td,
             gameObjects=[rel]),
          gs(gameStateId=2, type="GameStateType_Diff", zones=[pl(50)], gameObjects=[abi(50)], annotations=[uat(1, 50, 4)]),
          gs(gameStateId=3, type="GameStateType_Diff", zones=[pl(51)], gameObjects=[abi(51)], annotations=[uat(1, 51, 2)]),
          gs(gameStateId=4, type="GameStateType_Full", update="GameStateUpdate_Undo", prevGameStateId=3, turnInfo=td,
             zones=[dict(zoneId=28, type="ZoneType_Battlefield", objectInstanceIds=[40]), pl()], gameObjects=[rel]),
          gs(gameStateId=5, type="GameStateType_Diff", zones=[pl(52)], gameObjects=[abi(52)], diffDeletedInstanceIds=[40], annotations=[uat(1, 52, 2)])]
    casi.append(("le abilita' attivate (VERSIONE 15): la carta dal padre anche se e' andata via, il passo e chi e' di turno; negative: la sola abilita' di "
                 "mana e quella annullata non ci sono", leggi(fr)["attivate"] == [[4, 1, 700, "Phase_Beginning", "Step_Draw", 2]]
                 and leggi(fr[:3])["attivate"] == [[4, 1, 700, "Phase_Beginning", "Step_Draw", 2]] and leggi(fr[:2])["attivate"] == []))
    # chi e' in campo lo dice la zona: un oggetto che resta in memoria con la zona del campo ma non e' nella lista non attacca e non e' una terra
    vecchio = [gs(type="GameStateType_Full", zones=campo(1), turnInfo=dict(turnNumber=7, activePlayer=1, step="Step_DeclareAttack"),
                  gameObjects=[terra(1, 1, False), dict(crea(10, 1, True)), terra(4, 2, False)])]
    dv = leggi(vecchio)
    casi.append(("negativa: un oggetto fuori dalla lista del campo non attacca e non conta fra le terre", dv["attacchi"] == [] and dv["fine"] == []))
    # le vite a zero e gli oggetti cancellati (diffDeletedInstanceIds)
    zz = [gs(type="GameStateType_Full", zones=campo(10), turnInfo=dict(turnNumber=2, activePlayer=1, step="Step_Upkeep"), gameObjects=[crea(10, 1, False)],
             players=[dict(systemSeatNumber=1, lifeTotal=3), dict(systemSeatNumber=2, lifeTotal=5)]),
          gs(type="GameStateType_Diff", zones=campo(), diffDeletedInstanceIds=[10], players=[dict(systemSeatNumber=1, status="PlayerStatus_PendingLoss")])]
    u = leggi(zz)["ultima"][2]
    casi.append(("le vite a zero (lifeTotal assente) e la creatura cancellata", u["v"] == [0, 5] and u["c"] == [[], []]))
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
