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
            "AnnotationType_CounterAdded", "AnnotationType_NewTurnStarted",
            # dal debug del 12 nov 2026: i segnalini tolti (i poteri dei planeswalker), lo scry, aure ed equipaggiamenti attaccati, i potenziamenti, le abilita'
            # che vanno in pila
            "AnnotationType_CounterRemoved", "AnnotationType_Scry", "AnnotationType_AttachmentCreated", "AnnotationType_PowerToughnessModCreated",
            "AnnotationType_AbilityInstanceCreated"}
CATEGORIE = {"PlayLand": "played", "CastSpell": "cast", "Resolve": "resolved", "Draw": "drew", "Discard": "discarded", "Destroy": "destroyed",
             "Sacrifice": "sacrificed", "SBA_Damage": "died", "SBA_ZeroToughness": "died", "SBA_Deathtouch": "died", "SBA_UnattachedAura": "fell off",
             "SBA_LegendRule": "left (legend rule)", "Exile": "exiled", "Countered": "countered", "Return": "returned to hand", "Put": "put onto the battlefield",
             "Mill": "milled", "Surveil": "surveiled", "Bounce": "returned to hand",
             # dal debug del 12 nov 2026 (categorie che i log hanno e il replay saltava): il planeswalker senza fedelta', il warp, la carta a faccia in giu'
             "SBA_ZeroLoyalty": "died (no loyalty left)", "Warp": "exiled (warp)", "ManifestLike": "put onto the battlefield face down"}


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


def fine_partita(motivo, a_zero, avvelenato, grimorio_vuoto):
    """La frase della fine dal motivo di Arena: concessione, tempo, o la partita (vite a 0, veleno, grimorio vuoto, o un'altra regola: una carta che vince)."""
    if motivo == "ResultReason_Concede":
        return "conceded the game"
    if motivo == "ResultReason_Timeout":
        return "lost the game on time"
    if a_zero:
        return "lost the game at 0 life"
    if avvelenato:
        return "lost the game to poison"
    if grimorio_vuoto:
        return "lost the game drawing from an empty library"
    return "lost the game"


RIASSUNTO_EV = "Arena's log left out part of this step (a message too large to write): some actions and cards are missing"


def azioni(righe, nome=lambda g: None):
    """Le righe del log di una partita -> [dict(t, step, att, foto, ev=[(posto o None, testo)], danni=[(bersaglio, quanto)], rel)]: una foto a ogni azione che
    si vede. nome(grpId) da' il nome di una carta (per i testi); le foto portano i grpId come quelle di mana_aperto.
    Debug del 12 nov 2026 (Autore: «riguarda in maniera approfondita come il replayer legge i log e le azioni, debugga tutto»): le cancellazioni da
    diffDeletedInstanceIds; ogni oggetto visto resta ricordato (una pedina sacrificata o morta cambia id e sparisce nello stesso messaggio: senza il ricordo era
    «a card» senza chi); l'annullamento di Arena toglie le azioni annullate (prima una terra e una magia annullate e rifatte contavano due volte); le vite a 0;
    emblemi e inneschi ritardati col nome della carta; dove Arena ha riassunto un messaggio, l'azione lo dice."""
    obj, zone, zown, zids, vite, ti = {}, {}, {}, {}, {}, {}
    frames, bersagli, att_prima = [], {}, None
    ricordo, origine = {}, {}         # {id: oggetto com'era l'ultima volta}, {id nuovo: id di prima} (ObjectIdChanged)
    riassunto, finita, veleno = False, False, {}

    class _Tutti:       # gli oggetti di adesso e quelli ricordati, per trovare il padre di un'abilita'
        @staticmethod
        def get(k, d=None):
            return obj.get(k) or ricordo.get(k) or d
    tutti = _Tutti()

    def ogg(i):
        """L'oggetto di un id: com'e' adesso, se no com'era (anche sotto l'id di prima)."""
        seen = set()
        while i is not None and i not in seen:
            seen.add(i)
            o = obj.get(i) or ricordo.get(i)
            if o:
                return o
            i = origine.get(i)
        return {}

    def n_(i):
        o = ogg(i)
        g = MA.grp_vero(o, tutti) if o else None
        return nome(g) or ("a token" if o.get("type") == "GameObjectType_Token" else "a card")

    def chi_(i):
        o = ogg(i)
        return o.get("controllerSeatId") or o.get("ownerSeatId")

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
                    if o is None and zown.get(zid) in (1, 2):         # mai mandata (messaggio riassunto): c'e', non si sa quale
                        lato[zown[zid] - 1].append(0)
                    elif o and o.get("grpId") and o.get("type") == "GameObjectType_Card" and o.get("ownerSeatId") in (1, 2):
                        lato[o["ownerSeatId"] - 1].append(o["grpId"])
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
        if r.startswith(MA.RIASSUNTO):
            riassunto = True
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
        for msg in (d.get("greToClientEvent") or {}).get("greToClientMessages") or []:
            gs = msg.get("gameStateMessage")
            if not gs:
                continue
            sid = gs.get("gameStateId") or 0
            if gs.get("update") == "GameStateUpdate_Undo" and gs.get("prevGameStateId"):     # l'annullamento: via le azioni da quello stato in poi
                frames = [f for f in frames if f["_s"] < gs["prevGameStateId"]]
                att_prima = None
            if gs.get("type") == "GameStateType_Full":
                obj, zone, zown, zids = {}, {}, {}, {}
            for z in gs.get("zones") or []:
                zone[z.get("zoneId")] = z.get("type")
                zown[z.get("zoneId")] = z.get("ownerSeatId")
                zids[z.get("zoneId")] = z.get("objectInstanceIds") or []
            MA.vite_da(gs, vite)
            for pl in gs.get("players") or []:
                if pl.get("systemSeatNumber") in (1, 2):
                    veleno[pl["systemSeatNumber"]] = pl.get("poisonCounters", 0)
            for a in gs.get("annotations") or []:
                if "AnnotationType_ObjectIdChanged" in (a.get("type") or []):
                    vecchio, nuovo = _dettaglio(a, "orig_id"), _dettaglio(a, "new_id")
                    if vecchio and nuovo:
                        origine[nuovo] = vecchio
            for o in gs.get("gameObjects") or []:
                obj[o.get("instanceId")] = o
                ricordo[o.get("instanceId")] = o
            for x in MA.cancellati(gs):
                obj.pop(x, None)
            MA.turno_da(gs, ti)
            t, att = ti.get("turnNumber"), ti.get("activePlayer")
            if t is None or att is None:
                continue
            for a in gs.get("persistentAnnotations") or []:
                if "AnnotationType_TargetSpec" in (a.get("type") or []):
                    bersagli[a.get("affectorId")] = a.get("affectedIds") or []
            ev, danni = [], []
            # un segnalino +1/+1 arriva anche come potenziamento: si dice una volta sola (il segnalino)
            con_segnalino = {x for a in gs.get("annotations") or [] if "AnnotationType_CounterAdded" in (a.get("type") or []) for x in a.get("affectedIds") or []}
            if riassunto:
                ev.append((None, RIASSUNTO_EV))
                riassunto = False
            for res in (gs.get("gameInfo") or {}).get("results") or []:     # come e' finita (12 nov 2026: senza danni la fine non si capiva)
                if res.get("scope") == "MatchScope_Game" and not finita and res.get("winningTeamId") in (1, 2):
                    finita = True
                    perde = 2 if res["winningTeamId"] == 1 else 1
                    ev.append((perde, fine_partita(res.get("reason"), (vite.get(perde) or 0) <= 0, veleno.get(perde, 0) >= 10,
                                                   any(not zids.get(z) for z, tp in zone.items() if tp == "ZoneType_Library" and zown.get(z) == perde))))
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
                            ev.append((zown.get(dest) or chi_(x), "drew " + (n_(x) if ogg(x).get("grpId") else "a card")))
                        else:
                            if cat in ("Return", "Put", "Bounce"):     # dove va lo dice la zona d'arrivo (Teacher's Pest torna dal cimitero in campo, non in mano)
                                verbo = {"ZoneType_Hand": "returned to hand", "ZoneType_Battlefield": "returned to the battlefield" if cat == "Return"
                                         else "put onto the battlefield", "ZoneType_Library": "put into the library", "ZoneType_Graveyard": "put into the graveyard",
                                         "ZoneType_Exile": "exiled"}.get(zone.get(_dettaglio(a, "zone_dest")), verbo)
                            ev.append((chi_(x), f"{verbo} {n_(x)}" if cat in ("PlayLand", "CastSpell", "Discard", "Sacrifice") else f"{n_(x)} {verbo}"))
                elif "AnnotationType_DamageDealt" in tipi:
                    q = _dettaglio(a, "damage") or 0
                    for x in aff:
                        bers = f"{{P{x}}}" if x in (1, 2) else n_(x)
                        src = a.get("affectorId")
                        ev.append((chi_(src), f"{n_(src)} dealt {q} to {bers}"))
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
                        ev.append((chi_(x), f"{n_(x)} got {q} {'loyalty' if _dettaglio(a, 'counter_type') == 7 else 'counter' + ('s' if q != 1 else '')}"))
                elif "AnnotationType_CounterRemoved" in tipi:        # counter_type 7: la fedelta' (il costo di un potere del planeswalker)
                    q = _dettaglio(a, "transaction_amount") or 1
                    for x in aff:
                        ev.append((chi_(x), f"{n_(x)} lost {q} {'loyalty' if _dettaglio(a, 'counter_type') == 7 else 'counter' + ('s' if q != 1 else '')}"))
                elif "AnnotationType_Scry" in tipi:
                    sopra = [d_ for x_ in a.get("details") or [] if x_.get("key") == "topIds" for d_ in x_.get("valueInt32") or []]
                    sotto = [d_ for x_ in a.get("details") or [] if x_.get("key") == "bottomIds" for d_ in x_.get("valueInt32") or []]
                    chi_s = chi_(a.get("affectorId")) or att
                    ev.append((chi_s, f"scried {len(sopra) + len(sotto)}: {len(sopra)} on top, {len(sotto)} to the bottom"))
                elif "AnnotationType_AttachmentCreated" in tipi:
                    for x in aff:
                        ev.append((chi_(a.get("affectorId")), f"{n_(a.get('affectorId'))} attached to {n_(x)}"))
                elif "AnnotationType_PowerToughnessModCreated" in tipi:
                    p_, t_ = _dettaglio(a, "power") or 0, _dettaglio(a, "toughness") or 0
                    for x in aff:
                        if x not in con_segnalino:
                            ev.append((chi_(x), f"{n_(x)} got {p_:+d}/{t_:+d}"))
                elif "AnnotationType_AbilityInstanceCreated" in tipi:        # solo le abilita' che vanno in pila (non quelle di mana)
                    pila_ora = set(ids_di("ZoneType_Stack"))
                    for x in aff:
                        if x in pila_ora:
                            ev.append((chi_(x) or chi_(a.get("affectorId")), f"ability of {n_(a.get('affectorId'))} on the stack"))
            # il combattimento: attaccanti e blocchi dichiarati (chi e' in campo lo dicono le zone)
            sul = [obj[i] for i in ids_di("ZoneType_Battlefield") if i in obj]
            att_ids = [[o["instanceId"], (o.get("attackInfo") or {}).get("targetId")] for o in sul
                       if o.get("attackState") in ("AttackState_Declared", "AttackState_Attacking")]
            blocchi = [[o["instanceId"], (o.get("blockInfo") or {}).get("attackerIds") or []] for o in sul if (o.get("blockInfo") or {}).get("attackerIds")]
            comb = (tuple(map(tuple, att_ids)), tuple((b, tuple(a_)) for b, a_ in blocchi))
            solo_att = False
            if att_ids and comb != att_prima:
                if not ev:      # chi attacca, con forza e costituzione, e chi blocca chi (12 nov 2026: come diceva la scheda della partita)
                    pt = lambda i: (lambda o: f" ({valore(o, 'power')}/{valore(o, 'toughness')})" if valore(o, "power") is not None else "")(obj.get(i) or {})
                    if not att_prima or att_prima[0] != comb[0]:        # gli attaccanti cambiati: la riga d'attacco
                        ev.append((att, "attacked with " + ", ".join(n_(i) + pt(i) for i, _tg in att_ids)))
                        solo_att = not danni
                    gia = set(att_prima[1]) if att_prima else set()
                    for b_, aa in blocchi:          # i blocchi nuovi
                        if (b_, tuple(aa)) not in gia:
                            ev.append((chi_(b_), f"{n_(b_)} blocked {', '.join(n_(a_) for a_ in aa)}"))
                            solo_att = False
            elif not att_ids and not ev:
                att_prima = None        # finito il combattimento: le stesse creature che riattaccano al turno dopo sono un attacco nuovo
                continue
            att_prima = comb if att_ids else None
            if not ev and not danni:
                continue
            # la pila: la magia o l'abilita' in cima, coi bersagli
            pila = ids_di("ZoneType_Stack")
            rel = None
            if att_ids and ti.get("step") in ("Step_DeclareAttack", "Step_DeclareBlock", "Step_FirstStrikeDamage", "Step_CombatDamage"):
                rel = dict(k="comb", att=att_ids, blocchi=blocchi)
            elif pila:
                cima = pila[0]
                o = ogg(cima)
                rel = dict(k="spell", g=MA.grp_vero(o, tutti), chi=o.get("controllerSeatId"), ab=o.get("type") == "GameObjectType_Ability",
                           bers=list(bersagli.get(cima, [])), colpiti=[], fuori=MA.fuori_campo(bersagli.get(cima, []), zone, zids, zown, tutti))
            passo = (ti.get("step") or ti.get("phase") or "").replace("Step_", "").replace("Phase_", "")
            if solo_att and frames and frames[-1].get("_att") and frames[-1]["t"] == t and frames[-1]["step"] == passo:     # attaccanti scelti uno alla volta: resta l'ultima scelta
                frames.pop()
            frames.append(dict(t=t, step=(ti.get("step") or ti.get("phase") or "").replace("Step_", "").replace("Phase_", ""), att=att, foto=foto(), ev=ev,
                               danni=danni, rel=rel, _s=sid, _att=solo_att))
    for f in frames:
        f.pop("_s", None)
        f.pop("_att", None)
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
                gameObjects=[carta(3, 100, 28, 1)], diffDeletedInstanceIds=[1], annotations=[zt(3, "PlayLand")]),
             gs(type="GameStateType_Diff", zones=[dict(zoneId=27, type="ZoneType_Stack", objectInstanceIds=[4]), dict(zoneId=31, type="ZoneType_Hand",
                                                                                                                       ownerSeatId=1)],
                gameObjects=[carta(4, 200, 27, 1, cardTypes=["CardType_Instant"])], diffDeletedInstanceIds=[2], annotations=[zt(4, "CastSpell")],
                persistentAnnotations=[dict(type=["AnnotationType_TargetSpec"], affectorId=4, affectedIds=[9])]),
             gs(type="GameStateType_Diff", zones=[dict(zoneId=27, type="ZoneType_Stack"), dict(zoneId=28, type="ZoneType_Battlefield", objectInstanceIds=[3])],
                diffDeletedInstanceIds=[4, 9], players=[dict(systemSeatNumber=2, lifeTotal=17)],
                annotations=[dict(type=["AnnotationType_DamageDealt"], affectorId=4, affectedIds=[9], details=[dict(key="damage", valueInt32=[3])]),
                             zt(9, "SBA_Damage"), dict(type=["AnnotationType_ModifiedLife"], affectedIds=[2], details=[dict(key="life", valueInt32=[-3])])])]
    nomi = {100: "Mountain", 200: "Shock", 900: "Goblin"}
    fr = azioni(righe, nomi.get)
    testi = [tx for f in fr for _c, tx in f["ev"]]
    casi = [("quattro foto: l'inizio del turno, la terra, la magia, la risoluzione (il messaggio senza niente non conta)", len(fr) == 4),
            ("i testi: turno, terra, magia, danno, morte, vite", testi == ["turn 2 begins", "played Mountain", "cast Shock", "Shock dealt 3 to Goblin", "Goblin died",
                                                                         "lost 3 life"]),
            ("la magia in pila col suo bersaglio", fr[2]["rel"] == dict(k="spell", g=200, chi=1, ab=False, bers=[9], colpiti=[], fuori=[])),
            ("la foto dopo la terra ha la terra in campo con il suo id", fr[1]["foto"]["c"][0] == [[100, 0, 0, None, None, 3]]),
            ("i danni e le vite dopo la risoluzione", fr[3]["danni"] == [(9, 3)] and fr[3]["foto"]["v"] == [20, 17] and fr[3]["foto"]["c"][1] == []),
            ("negativa: righe senza stato del gioco, nessuna foto", azioni(["niente", "{rotto"]) == [])]
    # il debug del 12 nov 2026, un caso per ogni difetto trovato sui log veri (con la negativa dove serve)
    gz = lambda sid, **k: gs(gameStateId=sid, **k)
    campo = lambda *ids: dict(zoneId=28, type="ZoneType_Battlefield", objectInstanceIds=list(ids))
    mano = lambda *ids: dict(zoneId=31, type="ZoneType_Hand", ownerSeatId=1, objectInstanceIds=list(ids))
    pila = lambda *ids: dict(zoneId=27, type="ZoneType_Stack", objectInstanceIds=list(ids))
    t3 = dict(turnNumber=3, activePlayer=1, phase="Phase_Main1")
    base = [gz(1, type="GameStateType_Full", zones=[campo(), mano(1, 2, 5), pila()], turnInfo=t3,
               players=[dict(systemSeatNumber=1, lifeTotal=20), dict(systemSeatNumber=2, lifeTotal=20)],
               gameObjects=[carta(1, 100, 31, 1), carta(2, 200, 31, 1, cardTypes=["CardType_Instant"]), carta(5, 300, 31, 1, cardTypes=["CardType_Instant"])])]
    # l'annullamento: la terra, una magia cominciata e annullata (Arena torna allo stato della terra e lo rimanda intero), poi la magia vera
    undo = base + [gz(10, type="GameStateType_Diff", zones=[campo(3), mano(2, 5)], gameObjects=[carta(3, 100, 28, 1)], annotations=[zt(3, "PlayLand")]),
                   gz(11, type="GameStateType_Diff", zones=[pila(4), mano(5)], gameObjects=[carta(4, 200, 27, 1, cardTypes=["CardType_Instant"])],
                      annotations=[zt(4, "CastSpell")]),
                   gz(12, type="GameStateType_Full", update="GameStateUpdate_Undo", prevGameStateId=10, turnInfo=t3,
                      zones=[campo(3), mano(2, 5), pila()], gameObjects=[carta(3, 100, 28, 1), carta(2, 200, 31, 1, cardTypes=["CardType_Instant"]),
                                                                         carta(5, 300, 31, 1, cardTypes=["CardType_Instant"])], annotations=[zt(3, "PlayLand")]),
                   gz(13, type="GameStateType_Diff", zones=[pila(4), mano(2)], gameObjects=[carta(4, 300, 27, 1, cardTypes=["CardType_Instant"])],
                      annotations=[zt(4, "CastSpell")])]
    tu = [tx for f in azioni(undo, {100: "Island", 200: "Shock", 300: "Opt"}.get) for _c, tx in f["ev"]]
    casi.append(("l'annullamento di Arena: la terra una volta sola, la magia annullata no, quella vera si'", tu == ["played Island", "cast Opt"]))
    # la pedina sacrificata: cambia id e sparisce nello stesso messaggio (diffDeletedInstanceIds); il nome e chi resta dal ricordo
    sac = base + [gz(20, type="GameStateType_Diff", zones=[campo(7)], gameObjects=[carta(7, 900, 28, 2, tipo="GameObjectType_Token")]),
                  gz(21, type="GameStateType_Diff", zones=[campo()], diffDeletedInstanceIds=[7],
                     annotations=[dict(type=["AnnotationType_ObjectIdChanged"], affectedIds=[7], details=[dict(key="orig_id", valueInt32=[7]),
                                                                                                          dict(key="new_id", valueInt32=[8])]), zt(8, "Sacrifice")])]
    fs = azioni(sac, {900: "Soldier"}.get)
    casi.append(("la pedina sacrificata col nome e di chi e', anche se l'id nuovo non arriva mai", fs and fs[-1]["ev"] == [(2, "sacrificed Soldier")]
                 and fs[-1]["foto"]["c"] == [[], []]))
    # un oggetto cancellato non resta in campo: la creatura morta con l'attacco dichiarato non attacca piu' al turno dopo
    att_ = lambda i: carta(i, 500, 28, 1, cardTypes=["CardType_Creature"], attackState="AttackState_Attacking", power=dict(value=2), toughness=dict(value=2))
    morta = base + [gz(30, type="GameStateType_Diff", zones=[campo(9)], gameObjects=[att_(9)], turnInfo=dict(t3, phase="Phase_Combat", step="Step_DeclareAttack")),
                    gz(31, type="GameStateType_Diff", zones=[campo()], diffDeletedInstanceIds=[9], turnInfo=dict(turnNumber=4, activePlayer=2, phase="Phase_Main1"),
                       annotations=[dict(type=["AnnotationType_NewTurnStarted"], affectedIds=[2])])]
    fm = azioni(morta)
    casi.append(("negativa: la creatura cancellata non e' un attaccante al turno dopo", fm[-1]["rel"] is None and fm[-1]["foto"]["c"] == [[], []]))
    # le vite a zero: Arena non scrive lifeTotal quando e' 0
    zero = base + [gz(40, type="GameStateType_Diff", players=[dict(systemSeatNumber=2, status="PlayerStatus_PendingLoss")],
                      annotations=[dict(type=["AnnotationType_ModifiedLife"], affectedIds=[2], details=[dict(key="life", valueInt32=[-20])])])]
    casi.append(("le vite a zero (lifeTotal assente) sono 0, non l'ultimo valore", azioni(zero)[-1]["foto"]["v"] == [20, 0]))
    # gli attaccanti scelti uno alla volta: un'azione sola, con l'ultima scelta
    uno = lambda sid, *ids: gz(sid, type="GameStateType_Diff", zones=[campo(*ids)], gameObjects=[att_(i) for i in ids],
                               turnInfo=dict(t3, phase="Phase_Combat", step="Step_DeclareAttack"))
    fa = azioni(base + [uno(50, 9), uno(51, 9, 10)])
    casi.append(("gli attaccanti scelti uno alla volta: un'azione sola con l'ultima scelta", len([f for f in fa if f["rel"]]) == 1
                 and fa[-1]["ev"] == [(1, "attacked with a card (2/2), a card (2/2)")]))
    blocco = lambda sid: gz(sid, type="GameStateType_Diff", zones=[campo(9, 10, 14)], turnInfo=dict(t3, phase="Phase_Combat", step="Step_DeclareBlock"),
                            gameObjects=[att_(9), att_(10), carta(14, 800, 28, 2, cardTypes=["CardType_Creature"], blockInfo=dict(attackerIds=[9]))])
    fb = azioni(base + [uno(50, 9), uno(51, 9, 10), blocco(52)], {500: "Goblin", 800: "Wall"}.get)
    casi.append(("l'attacco e poi il blocco: due azioni, la seconda dice solo chi blocca chi", [f["ev"] for f in fb] ==
                 [[(1, "attacked with Goblin (2/2), Goblin (2/2)")], [(2, "Wall blocked Goblin")]]))
    fine_c = gz(53, type="GameStateType_Diff", zones=[campo(9, 10)], turnInfo=dict(turnNumber=5, activePlayer=1, phase="Phase_Main1"),
                gameObjects=[carta(9, 500, 28, 1, cardTypes=["CardType_Creature"]), carta(10, 500, 28, 1, cardTypes=["CardType_Creature"])])
    ancora = gz(54, type="GameStateType_Diff", zones=[campo(9, 10)], gameObjects=[att_(9), att_(10)],
                turnInfo=dict(turnNumber=5, activePlayer=1, phase="Phase_Combat", step="Step_DeclareAttack"))
    fr2 = azioni(base + [uno(51, 9, 10), fine_c, ancora], {500: "Goblin"}.get)
    casi.append(("le stesse creature che riattaccano due turni dopo: un attacco nuovo", [f["t"] for f in fr2 if f["ev"][0][1].startswith("attacked")] == [3, 5]))
    zero_ = base + [gz(95, type="GameStateType_Diff", zones=[campo(15)], gameObjects=[carta(15, 510, 28, 2, cardTypes=["CardType_Creature"], power={},
                                                                                         toughness=dict(value=2))], annotations=[zt(15, "Resolve")])]
    casi.append(("la creatura 0/2: Arena non scrive la forza a zero, resta una creatura 0/2", azioni(zero_)[-1]["foto"]["c"][1] == [[510, 0, 0, 0, 2, 15]]))
    cimz = dict(zoneId=33, type="ZoneType_Graveyard", ownerSeatId=1)
    ritorno = base + [gz(96, type="GameStateType_Diff", zones=[campo(16), cimz], gameObjects=[carta(16, 520, 28, 1, cardTypes=["CardType_Creature"],
                                                                                                    power=dict(value=1), toughness=dict(value=1))],
                         annotations=[dict(type=["AnnotationType_ZoneTransfer"], affectedIds=[16], details=[dict(key="category", valueString=["Return"]),
                                                                                                           dict(key="zone_dest", valueInt32=[28])]),
                                      dict(type=["AnnotationType_CounterAdded"], affectedIds=[16], details=[dict(key="counter_type", valueInt32=[1])]),
                                      dict(type=["AnnotationType_PowerToughnessModCreated"], affectedIds=[16], details=[dict(key="power", valueInt32=[1]),
                                                                                                                       dict(key="toughness", valueInt32=[1])])])]
    casi.append(("il ritorno dal cimitero in campo (non in mano) e il segnalino +1/+1 detto una volta sola",
                 [tx for _c, tx in azioni(ritorno, {520: "Pest"}.get)[-1]["ev"]] == ["Pest returned to the battlefield", "Pest got 1 counter"]))
    # un messaggio che Arena ha riassunto: l'azione dopo lo dice
    fr_r = azioni(base + ["[Message summarized because one or more GameStateMessages exceeded the 50 GameObject or 50 Annotation limit.]",
                          gz(60, type="GameStateType_Diff", zones=[campo(3)], gameObjects=[carta(3, 100, 28, 1)], annotations=[zt(3, "PlayLand")])])
    casi.append(("un messaggio riassunto da Arena: l'azione dopo dice che manca qualcosa", fr_r[-1]["ev"][0] == (None, RIASSUNTO_EV)))
    # il bersaglio nel cimitero (una rianimazione): fuori dal campo, con la zona e di chi e'
    cim = dict(zoneId=33, type="ZoneType_Graveyard", ownerSeatId=2, objectInstanceIds=[11])
    rian = base + [gz(70, type="GameStateType_Diff", zones=[cim, pila(4), mano(5)], gameObjects=[carta(11, 600, 33, 2), carta(4, 200, 27, 1)],
                      annotations=[zt(4, "CastSpell")], persistentAnnotations=[dict(type=["AnnotationType_TargetSpec"], affectorId=4, affectedIds=[11])])]
    casi.append(("il bersaglio nel suo cimitero: fuori dal campo, con la zona, il posto e la carta", azioni(rian)[-1]["rel"]["fuori"] == [[11, "cim", 2, 600]]))
    # l'abilita' di un emblema: il nome e' della carta che l'ha creato (Arena scrive l'emblema col grpId 2)
    o_ = {50: dict(instanceId=50, grpId=777, type="GameObjectType_Card"), 51: dict(instanceId=51, grpId=2, type="GameObjectType_Emblem", parentId=50,
                                                                                      objectSourceGrpId=776),
          52: dict(instanceId=52, grpId=1234, type="GameObjectType_Ability", parentId=51)}
    casi.append(("l'abilita' di un emblema risale alla carta, l'innesco senza padre alla carta d'origine", MA.grp_vero(o_[52], o_) == 777
                 and MA.grp_vero(dict(type="GameObjectType_TriggerHolder", grpId=5, objectSourceGrpId=888), o_) == 888))
    lib = lambda n: dict(zoneId=36, type="ZoneType_Library", ownerSeatId=2, objectInstanceIds=list(range(500, 500 + n)))
    fine_ = lambda motivo, n: azioni(base + [gz(80, type="GameStateType_Diff", zones=[lib(n)],
                                                gameInfo=dict(results=[dict(scope="MatchScope_Game", winningTeamId=1, reason=motivo)]))])[-1]["ev"]
    casi.append(("come e' finita: grimorio vuoto, concessione; negativa: con carte nel grimorio e vite non dice grimorio vuoto",
                 fine_("ResultReason_Game", 0) == [(2, "lost the game drawing from an empty library")]
                 and fine_("ResultReason_Concede", 30) == [(2, "conceded the game")] and fine_("ResultReason_Game", 30) == [(2, "lost the game")]))
    pw = carta(12, 700, 28, 1, cardTypes=["CardType_Planeswalker"])
    ab_ = dict(instanceId=13, grpId=7001, type="GameObjectType_Ability", zoneId=27, controllerSeatId=1, parentId=12)
    poteri = base + [gz(90, type="GameStateType_Diff", zones=[campo(12), pila(13)], gameObjects=[pw, ab_],
                        annotations=[dict(type=["AnnotationType_CounterRemoved"], affectorId=12, affectedIds=[12], details=[dict(key="counter_type", valueInt32=[7]),
                                                                                                                         dict(key="transaction_amount", valueInt32=[3])]),
                                     dict(type=["AnnotationType_AbilityInstanceCreated"], affectorId=12, affectedIds=[13])]),
                     gz(91, type="GameStateType_Diff", zones=[pila()], annotations=[dict(type=["AnnotationType_Scry"], affectorId=12, affectedIds=[2],
                                                                                         details=[dict(key="bottomIds", valueInt32=[2])])])]
    tp = [tx for f in azioni(poteri, {700: "Jace"}.get) for _c, tx in f["ev"]]
    casi.append(("il potere del planeswalker (fedelta' tolta e abilita' in pila) e lo scry", tp == ["Jace lost 3 loyalty", "ability of Jace on the stack",
                                                                                                    "scried 1: 0 on top, 1 to the bottom"]))
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
