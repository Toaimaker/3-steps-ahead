"""Il replay azione per azione (12 nov 2026, Autore: «e noi non possiamo migliorare il nostro rispetto a quello di MTGO, farlo piu' efficiente e
performante? cosi' da avere il replayer migliore in circolazione?», poi «basta che non perdiamo assolutamente cio' che abbiamo adesso ma lavoriamo solo per
aumentare la qualita'»).

I «Moments» di mana_aperto restano come sono. Qui, solo per la partita che apri, si rilegge il suo pezzo di log (il pezzo in Log_Arena/partite/<ID>/arena.log,
o il ritaglio dell'archivio che mana_aperto ricorda in «dove») e si fa una foto a ogni azione che si vede: una carta che cambia zona (pescata, terra, magia,
risoluzione, morte, esilio...), un danno, le vite, una pedina, un segnalino, l'inizio di un turno, attaccanti e bloccanti dichiarati. Ogni foto ha la stessa
forma di quelle di mana_aperto (le stesse funzioni la disegnano) piu' cosa e' successo («ev»), i danni («danni») e le relazioni (il combattimento, la magia in
pila coi bersagli). Niente copia su disco: una partita si legge in qualche decina di millisecondi.

    py -I -X utf8 Companion/App/Schede/Performance/replay_log.py --prova
"""
import os, sys
_casa = os.path.dirname(os.path.abspath(__file__))
while not os.path.isfile(os.path.join(_casa, "percorsi.py")):
    _casa = os.path.dirname(_casa)
if _casa not in sys.path:
    sys.path.insert(0, _casa)
import percorsi  # noqa: E402,F401
import json  # noqa: E402

import mana_aperto as MA  # noqa: E402

VISIBILI = {"AnnotationType_ZoneTransfer", "AnnotationType_DamageDealt", "AnnotationType_ModifiedLife", "AnnotationType_TokenCreated",
            "AnnotationType_CounterAdded", "AnnotationType_NewTurnStarted"}
CATEGORIE = {"PlayLand": "played", "CastSpell": "cast", "Resolve": "resolved", "Draw": "drew", "Discard": "discarded", "Destroy": "destroyed",
             "Sacrifice": "sacrificed", "SBA_Damage": "died", "SBA_ZeroToughness": "died", "SBA_Deathtouch": "died", "SBA_UnattachedAura": "fell off",
             "SBA_LegendRule": "left (legend rule)", "Exile": "exiled", "Countered": "countered", "Return": "returned to hand", "Put": "put onto the battlefield",
             "Mill": "milled", "Surveil": "surveiled", "Bounce": "returned to hand"}


def righe_partita(mid, dove=None):
    """Le righe del log di una partita: dal suo pezzo, se c'e', se no dal ritaglio dell'archivio («dove» di mana_aperto). [] se non si trova."""
    cart = MA.indice().get(mid)
    if cart:
        try:
            with open(os.path.join(cart, "arena.log"), encoding="utf-8", errors="replace") as h:
                return h.read().splitlines()
        except OSError:
            pass
    if dove:
        try:
            with open(os.path.join(MA.LOGDIR, dove[0]), "rb") as h:
                h.seek(dove[1])
                return h.read(dove[2] - dove[1]).decode("utf-8", "replace").splitlines()
        except OSError:
            pass
    return []


# le righe della spalla da mostrare accanto al replay (12 nov 2026, «Sì, prosegui»: «nei limited, i consigli della spalla accanto all'azione»): la mano, la
# giocata, il piano, l'attacco, il suo attacco col blocco, il pericolo, il letale, il Cercatore; l'etichetta in inglese, il resto con la traduzione della chat
ETICHETTE_SPALLA = (("MANO", "HAND"), ("GIOCA ORA", "PLAY NOW"), ("GIOCA", "PLAY"), ("PIANO ORA", "PLAN NOW"), ("PIANO", "PLAN"), ("TURNO INTERO", "WHOLE TURN"),
                    ("ATTACCO SCELTO IN P", "ATTACK (BY WIN CHANCE)"), ("ATTACCO SUO", "THEIR ATTACK"), ("ATTACCO (EV)", "ATTACK"), ("ATTACCO", "ATTACK"),
                    ("PERICOLO", "DANGER"), ("LETALE", "LETHAL"), ("CERCATORE", "SEARCH"), ("SURVEIL", "SURVEIL"), ("PW TUO", "YOUR PW"), ("PW SUO", "THEIR PW"),
                    ("SUO MANA", "THEIR MANA"))


FRASI_SPALLA = (("win condition misurate nel mazzo: nessuna, si vince col board", "measured win conditions in the deck: none, the board wins"),
                ("niente in campo", "nothing on the battlefield"), ("in campo", "on the battlefield"), ("forza in campo", "power on the battlefield"),
                ("win condition misurate nel mazzo", "measured win conditions in the deck"), ("(segui questo)", "(follow this)"),
                ("dell'attacco qui sopra", "of the attack above"), ("con la sua risposta peggiore per te", "with their worst answer for you"),
                ("la differenza vale circa la meta'", "the difference is worth about half"), ("restare a casa vale", "staying home is worth"),
                ("risposta sua", "their answer"), ("nessun blocco", "no block"), ("p trucco", "trick chance"), ("prior grado C", "grade C prior"),
                ("grado C", "grade C"), ("grado B", "grade B"), ("attacchi con", "attack with"), ("tu chiudi in", "you close in"), ("lui in", "opponent in"),
                ("dopo GIOCA", "after PLAY"), ("creature: dopo l'attacco", "creatures: after the attack"), ("le creature adesso", "creatures now"),
                ("niente attacco", "no attack"), ("tieni", "keep"), ("TIENI", "KEEP"), ("MULLIGAN", "MULLIGAN"), ("contro", "vs"), ("forza", "power"),
                ("blocca con", "block with"), ("non bloccare", "don't block"), ("nessun attacco", "no attack"), ("sue terre libere", "their open lands"),
                ("tue terre libere", "your open lands"), ("trucchi possibili", "possible tricks"), ("punti sul mulligan", "points over a mulligan"),
                ("lascialo stare", "leave it"), ("attacca lui", "attack the player"), ("regola dell'11 ott", "rule of 11 Oct"), ("salvo", "except"),
                ("e' a corto di mana", "is short on mana"), ("spingi adesso, prima che sblocchi", "push now, before they recover"), ("terre dopo", "lands after"),
                ("ne ha saltate", "missed"), ("turni", "turns"), ("turno", "turn"), ("vite", "life"), ("tue", "your"), ("sue", "their"))


def spalla(mid):
    """Cosa diceva la spalla in quella partita, turno per turno di Arena, dal diario della partita (Log_Arena/partite/<ID>/diario.txt: c'e' solo nei limited
    seguiti dal companion). -> {turno: [testo]}; la mano iniziale sta al turno 0. {} senza diario."""
    import re
    cart = MA.indice().get(mid)
    if not cart:
        return {}
    try:
        with open(os.path.join(cart, "diario.txt"), encoding="utf-8", errors="replace") as h:
            righe = h.read().splitlines()
    except OSError:
        return {}
    try:
        from chat_testi import en
    except Exception:      # noqa: BLE001 - senza la traduzione restano in italiano
        en = lambda x: x
    out, turno = {}, None
    for r in righe:
        corpo = r[9:] if len(r) > 9 and r[2] == ":" and r[5] == ":" else r
        dentro = corpo.startswith("  ")
        testo = corpo.strip()
        if not dentro:
            m = re.match(r"TURNO (\d+)\b", testo) or re.search(r"\bT(\d+)\b", testo)
            turno = int(m.group(1)) if m else (0 if testo.startswith("MANO") else None)
        if turno is None:
            continue
        for it, inglese in ETICHETTE_SPALLA:
            if testo.startswith(it) and (dentro or it in ("MANO", "ATTACCO SUO", "LETALE", "PERICOLO", "CERCATORE", "SURVEIL")):
                resto = testo[len(it):].lstrip(" :")
                resto = re.sub(r"^T\d+\b[:]?\s*", "", resto)
                for a_, b_ in FRASI_SPALLA:      # prima le frasi intere della spalla, poi la traduzione parola per parola della chat
                    resto = resto.replace(a_, b_)
                out.setdefault(turno, []).append(f"{inglese}: {en(resto)}")
                break
    return out


def _dettaglio(a, k):
    for x in a.get("details") or []:
        if x.get("key") == k:
            return (x.get("valueInt32") or x.get("valueString") or [None])[0]
    return None


def azioni(righe, nome=lambda g: None):
    """Le righe del log di una partita -> [dict(t, step, att, foto, ev=[(posto o None, testo)], danni=[(bersaglio, quanto)], rel)]: una foto a ogni azione che
    si vede. nome(grpId) da' il nome di una carta (per i testi); le foto portano i grpId come quelle di mana_aperto."""
    obj, zone, zown, zids, vite, ti = {}, {}, {}, {}, {}, {}
    frames, bersagli, att_prima = [], {}, None

    def n_(i):
        o = obj.get(i) or {}
        g = o.get("grpId")
        if o.get("type") == "GameObjectType_Ability":
            g = (obj.get(o.get("parentId")) or {}).get("grpId") or o.get("objectSourceGrpId") or g
        return nome(g) or ("a token" if o.get("type") == "GameObjectType_Token" else "a card")

    chi_prima = {}

    def chi_(i):
        o = obj.get(i)
        if o is None:
            return chi_prima.get(i)
        return o.get("controllerSeatId") or o.get("ownerSeatId")

    def valore(o, k):
        v = o.get(k)
        return v.get("value") if isinstance(v, dict) else v

    def foto():
        c, m, n, g, e = [[], []], [[], []], [0, 0], [[], []], [[], []]
        for zid, tp in zone.items():
            ids = zids.get(zid, [])
            if tp in ("ZoneType_Graveyard", "ZoneType_Exile"):
                for i in ids:
                    o = obj.get(i)
                    if o and o.get("grpId") and o.get("type") == "GameObjectType_Card" and o.get("ownerSeatId") in (1, 2):
                        (g if tp == "ZoneType_Graveyard" else e)[o["ownerSeatId"] - 1].append(o["grpId"])
            elif tp == "ZoneType_Battlefield":
                for i in ids:
                    o = obj.get(i)
                    if o and o.get("grpId") and o.get("type") in ("GameObjectType_Card", "GameObjectType_Token") and o.get("controllerSeatId") in (1, 2):
                        crea = "CardType_Creature" in (o.get("cardTypes") or [])
                        c[o["controllerSeatId"] - 1].append([o["grpId"], 1 if o.get("isTapped") else 0, 1 if o["type"] == "GameObjectType_Token" else 0,
                                                             valore(o, "power") if crea else None, valore(o, "toughness") if crea else None, i])
            elif tp == "ZoneType_Hand" and zown.get(zid) in (1, 2):
                k = zown[zid] - 1
                n[k] = len(ids)
                m[k] = [obj[i]["grpId"] for i in ids if i in obj and obj[i].get("grpId")]
        return dict(c=c, m=m, n=n, v=[vite.get(1), vite.get(2)], g=g, e=e)

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
        for msg in (d.get("greToClientEvent") or {}).get("greToClientMessages") or []:
            gs = msg.get("gameStateMessage")
            if not gs:
                continue
            if gs.get("type") == "GameStateType_Full":
                obj, zone, zown, zids = {}, {}, {}, {}
            for z in gs.get("zones") or []:
                zone[z.get("zoneId")] = z.get("type")
                zown[z.get("zoneId")] = z.get("ownerSeatId")
                zids[z.get("zoneId")] = z.get("objectInstanceIds") or []
            for pl in gs.get("players") or []:
                if pl.get("systemSeatNumber") in (1, 2) and pl.get("lifeTotal") is not None:
                    vite[pl["systemSeatNumber"]] = pl["lifeTotal"]
            # i nomi delle carte che lasciano la tavola si leggono prima di toglierle
            nomi_prima = {i: n_(i) for i in gs.get("deletedInstanceIds") or [] if i in obj}
            chi_prima = {i: chi_(i) for i in gs.get("deletedInstanceIds") or [] if i in obj}
            for o in gs.get("gameObjects") or []:
                obj[o.get("instanceId")] = o
            for x in gs.get("deletedInstanceIds") or []:
                obj.pop(x, None)
            if gs.get("turnInfo"):
                if "phase" in gs["turnInfo"] and "step" not in gs["turnInfo"]:     # nelle fasi principali Arena non scrive lo step: non resta quello di prima
                    ti.pop("step", None)
                ti.update(gs["turnInfo"])
            t, att = ti.get("turnNumber"), ti.get("activePlayer")
            if t is None or att is None:
                continue
            for a in gs.get("persistentAnnotations") or []:
                if "AnnotationType_TargetSpec" in (a.get("type") or []):
                    bersagli[a.get("affectorId")] = a.get("affectedIds") or []
            ev, danni = [], []
            for a in gs.get("annotations") or []:
                tipi = set(a.get("type") or [])
                if not tipi & VISIBILI:
                    continue
                aff = a.get("affectedIds") or []
                if "AnnotationType_NewTurnStarted" in tipi:
                    ev.append((att, f"turn {(t + 1) // 2} begins"))
                elif "AnnotationType_ZoneTransfer" in tipi:
                    cat = _dettaglio(a, "category") or ""
                    for x in aff:
                        verbo = CATEGORIE.get(cat)
                        if not verbo:
                            continue
                        if cat == "Draw":       # di chi e' la mano dove arriva (la sua pescata non si vede: «a card»)
                            dest = _dettaglio(a, "zone_dest")
                            ev.append((zown.get(dest) or chi_(x), "drew " + (n_(x) if (obj.get(x) or {}).get("grpId") else "a card")))
                        else:
                            ev.append((chi_(x), f"{verbo} {nomi_prima.get(x) or n_(x)}" if cat in ("PlayLand", "CastSpell", "Discard", "Sacrifice")
                                       else f"{nomi_prima.get(x) or n_(x)} {verbo}"))
                elif "AnnotationType_DamageDealt" in tipi:
                    q = _dettaglio(a, "damage") or 0
                    for x in aff:
                        bers = f"{{P{x}}}" if x in (1, 2) else (nomi_prima.get(x) or n_(x))
                        src = a.get("affectorId")
                        ev.append((chi_(src), f"{nomi_prima.get(src) or n_(src)} dealt {q} to {bers}"))
                        danni.append((x, q))
                elif "AnnotationType_ModifiedLife" in tipi:
                    q = _dettaglio(a, "life") or 0
                    for x in aff:
                        ev.append((x, f"{'gained' if q > 0 else 'lost'} {abs(q)} life"))
                elif "AnnotationType_TokenCreated" in tipi:
                    for x in aff:
                        ev.append((chi_(x), f"created a token: {n_(x)}"))
                elif "AnnotationType_CounterAdded" in tipi:
                    q = _dettaglio(a, "transaction_amount") or 1
                    for x in aff:
                        ev.append((chi_(x), f"{n_(x)} got {q} counter{'s' if q != 1 else ''}"))
            # il combattimento: attaccanti e blocchi dichiarati
            sul = [o for o in obj.values() if zone.get(o.get("zoneId")) == "ZoneType_Battlefield"]
            att_ids = [[o["instanceId"], (o.get("attackInfo") or {}).get("targetId")] for o in sul
                       if o.get("attackState") in ("AttackState_Declared", "AttackState_Attacking")]
            blocchi = [[o["instanceId"], (o.get("blockInfo") or {}).get("attackerIds") or []] for o in sul if (o.get("blockInfo") or {}).get("attackerIds")]
            comb = (tuple(map(tuple, att_ids)), tuple((b, tuple(a_)) for b, a_ in blocchi))
            if att_ids and comb != att_prima:
                if not ev:
                    ev.append((att, f"attacked with {len(att_ids)} creature{'s' if len(att_ids) != 1 else ''}" + (f", {len(blocchi)} block{'s' if len(blocchi) != 1 else ''}" if blocchi else "")))
            elif not att_ids and not ev:
                att_prima = comb if not att_ids else att_prima
                continue
            att_prima = comb
            if not ev and not danni:
                continue
            # la pila: la magia o l'abilita' in cima, coi bersagli
            pila = [i for zid, tp in zone.items() if tp == "ZoneType_Stack" for i in zids.get(zid, [])]
            rel = None
            if att_ids and ti.get("step") in ("Step_DeclareAttack", "Step_DeclareBlock", "Step_FirstStrikeDamage", "Step_CombatDamage"):
                rel = dict(k="comb", att=att_ids, blocchi=blocchi)
            elif pila:
                cima = pila[0]
                o = obj.get(cima) or {}
                g = o.get("grpId")
                ab = o.get("type") == "GameObjectType_Ability"
                if ab:
                    g = (obj.get(o.get("parentId")) or {}).get("grpId") or o.get("objectSourceGrpId") or g
                rel = dict(k="spell", g=g, chi=o.get("controllerSeatId"), ab=ab, bers=list(bersagli.get(cima, [])), colpiti=[])
            frames.append(dict(t=t, step=(ti.get("step") or ti.get("phase") or "").replace("Step_", "").replace("Phase_", ""), att=att, foto=foto(), ev=ev,
                               danni=danni, rel=rel))
    return frames


def prova():
    """Un log finto: inizio turno, una terra, una magia sul suo bersaglio che si risolve, danno e vite; un messaggio senza niente che si veda non fa foto."""
    def gs(**k):
        return "[UnityCrossThreadLogger]x " + json.dumps(dict(greToClientEvent=dict(greToClientMessages=[dict(gameStateMessage=k)])))
    carta = lambda i, g, z, seat, **k: dict(instanceId=i, grpId=g, type=k.pop("tipo", "GameObjectType_Card"), zoneId=z, controllerSeatId=seat, ownerSeatId=seat, **k)
    zt = lambda aid, cat: dict(type=["AnnotationType_ZoneTransfer"], affectedIds=[aid], details=[dict(key="category", valueString=[cat])])
    righe = [gs(type="GameStateType_Full", zones=[dict(zoneId=28, type="ZoneType_Battlefield"), dict(zoneId=31, type="ZoneType_Hand", ownerSeatId=1,
                                                                                                   objectInstanceIds=[1, 2]), dict(zoneId=27, type="ZoneType_Stack")],
                players=[dict(systemSeatNumber=1, lifeTotal=20), dict(systemSeatNumber=2, lifeTotal=20)], turnInfo=dict(turnNumber=3, activePlayer=1, step="Step_Upkeep"),
                gameObjects=[carta(1, 100, 31, 1), carta(2, 200, 31, 1), carta(9, 900, 28, 2, cardTypes=["CardType_Creature"], power=dict(value=2),
                                                                                                      toughness=dict(value=2))],
                annotations=[dict(type=["AnnotationType_NewTurnStarted"], affectedIds=[1])]),
             gs(type="GameStateType_Diff", turnInfo=dict(step="Step_Main1")),        # niente che si veda: nessuna foto
             gs(type="GameStateType_Diff", zones=[dict(zoneId=28, type="ZoneType_Battlefield", objectInstanceIds=[9, 3]), dict(zoneId=31, type="ZoneType_Hand",
                                                                                                                                ownerSeatId=1, objectInstanceIds=[2])],
                gameObjects=[carta(3, 100, 28, 1)], deletedInstanceIds=[1], annotations=[zt(3, "PlayLand")]),
             gs(type="GameStateType_Diff", zones=[dict(zoneId=27, type="ZoneType_Stack", objectInstanceIds=[4]), dict(zoneId=31, type="ZoneType_Hand",
                                                                                                                       ownerSeatId=1)],
                gameObjects=[carta(4, 200, 27, 1, cardTypes=["CardType_Instant"])], deletedInstanceIds=[2], annotations=[zt(4, "CastSpell")],
                persistentAnnotations=[dict(type=["AnnotationType_TargetSpec"], affectorId=4, affectedIds=[9])]),
             gs(type="GameStateType_Diff", zones=[dict(zoneId=27, type="ZoneType_Stack"), dict(zoneId=28, type="ZoneType_Battlefield", objectInstanceIds=[3])],
                deletedInstanceIds=[4, 9], players=[dict(systemSeatNumber=2, lifeTotal=17)],
                annotations=[dict(type=["AnnotationType_DamageDealt"], affectorId=4, affectedIds=[9], details=[dict(key="damage", valueInt32=[3])]),
                             zt(9, "SBA_Damage"), dict(type=["AnnotationType_ModifiedLife"], affectedIds=[2], details=[dict(key="life", valueInt32=[-3])])])]
    nomi = {100: "Mountain", 200: "Shock", 900: "Goblin"}
    fr = azioni(righe, nomi.get)
    testi = [tx for f in fr for _c, tx in f["ev"]]
    casi = [("quattro foto: l'inizio del turno, la terra, la magia, la risoluzione (il messaggio senza niente non conta)", len(fr) == 4),
            ("i testi: turno, terra, magia, danno, morte, vite", testi == ["turn 2 begins", "played Mountain", "cast Shock", "Shock dealt 3 to Goblin", "Goblin died",
                                                                         "lost 3 life"]),
            ("la magia in pila col suo bersaglio", fr[2]["rel"] == dict(k="spell", g=200, chi=1, ab=False, bers=[9], colpiti=[])),
            ("la foto dopo la terra ha la terra in campo con il suo id", fr[1]["foto"]["c"][0] == [[100, 0, 0, None, None, 3]]),
            ("i danni e le vite dopo la risoluzione", fr[3]["danni"] == [(9, 3)] and fr[3]["foto"]["v"] == [20, 17] and fr[3]["foto"]["c"][1] == []),
            ("negativa: righe senza stato del gioco, nessuna foto", azioni(["niente", "{rotto"]) == [])]
    # la spalla da un diario finto (in una cartella di partita finta)
    import tempfile
    vecchia = MA.CARTELLA
    MA.CARTELLA = tempfile.mkdtemp()
    try:
        cart = os.path.join(MA.CARTELLA, "x")
        os.makedirs(cart)
        with open(os.path.join(cart, "partita.json"), "w", encoding="utf-8") as h:
            json.dump(dict(matchId="m1"), h)
        with open(os.path.join(cart, "diario.txt"), "w", encoding="utf-8") as h:
            h.write("02:17:20 MANO (7) contro X: Shock, Mountain | terre 3/7 -> TIENI\n02:17:30 TURNO 4 | vite tu 20 lui 20\n02:17:30   GIOCA: Mountain\n"
                    "02:17:30   PIANO: tu chiudi in 5 turni\n02:18:00 STATO Partita contro X\n02:18:18 ATTACCO SUO T5: Goblin 2/1 = 2 su 20 vite\n")
        sp = spalla("m1")
        casi.append(("la spalla turno per turno: la mano al turno 0, giocata e piano al 4, il suo attacco al 5; lo STATO no",
                     list(sp) == [0, 4, 5] and sp[4][0] == "PLAY: Mountain" and sp[4][1].startswith("PLAN:") and sp[5][0].startswith("THEIR ATTACK: Goblin")))
        casi.append(("negativa: una partita senza diario, niente spalla", spalla("nessuna") == {}))
    finally:
        MA.CARTELLA = vecchia
    for n, ok in casi:
        print(("ok    " if ok else "ROSSO ") + n)
    print(f"{sum(1 for _n, ok in casi if ok)}/{len(casi)}")
    return all(ok for _n, ok in casi)


if __name__ == "__main__":
    if "--prova" in sys.argv:
        sys.exit(0 if prova() else 1)
    import time
    d = MA.tutti(archivi=False)
    mid = next(iter(MA.indice()), None)
    t0 = time.time()
    fr = azioni(righe_partita(mid))
    print(mid, len(fr), "azioni,", round(time.time() - t0, 2), "s")
