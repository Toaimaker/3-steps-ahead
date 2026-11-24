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
import copy  # noqa: E402
import json  # noqa: E402

import mana_aperto as MA  # noqa: E402
import re  # noqa: E402
import testi_arena as TA  # noqa: E402

VISIBILI = {"AnnotationType_ZoneTransfer", "AnnotationType_DamageDealt", "AnnotationType_ModifiedLife", "AnnotationType_TokenCreated",
            "AnnotationType_CounterAdded", "AnnotationType_NewTurnStarted",
            # dal debug del 12 nov 2026: i segnalini tolti (i poteri dei planeswalker), lo scry, aure ed equipaggiamenti attaccati, i potenziamenti, le abilita'
            # che vanno in pila
            "AnnotationType_CounterRemoved", "AnnotationType_Scry", "AnnotationType_AttachmentCreated", "AnnotationType_PowerToughnessModCreated",
            # dal censimento del 14 nov 2026: le carte rivelate, il grimorio rimescolato, la carta che cambia controllore
            "AnnotationType_RevealedCardCreated", "AnnotationType_Shuffle", "AnnotationType_ControllerChanged", "AnnotationType_ChoiceResult",
            "AnnotationType_AbilityInstanceCreated", "AnnotationType_CardRevealed"}
CATEGORIE = {"PlayLand": "played", "CastSpell": "cast", "Resolve": "resolved", "Draw": "drew", "Discard": "discarded", "Destroy": "destroyed",
             "Sacrifice": "sacrificed", "SBA_Damage": "died", "SBA_ZeroToughness": "died", "SBA_Deathtouch": "died", "SBA_UnattachedAura": "fell off",
             "SBA_LegendRule": "left (legend rule)", "Exile": "exiled", "Countered": "countered", "Return": "returned to hand", "Put": "put onto the battlefield",
             "Mill": "milled", "Surveil": "surveilled", "Separate": "put into a pile", "Bounce": "returned to hand",
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
            percorso = dove[0][1:] if str(dove[0]).startswith("@") else os.path.join(MA.LOGDIR, dove[0])
            with open(percorso, "rb") as h:
                h.seek(dove[1])
                righe = h.read(dove[2] - dove[1]).decode("utf-8", "replace").splitlines()
            if any(mid in r_ for r_ in righe[:400]) or any(mid in r_ for r_ in righe[-400:]):
                return righe
        except OSError:
            pass
        return MA.trova_righe(mid)        # il log di adesso e' cresciuto o ha cambiato nome: la partita si cerca per matchId (18 nov 2026)
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


_KW = None
COLORI_MANA = {1: "W", 2: "U", 3: "B", 4: "R", 5: "G"}          # il colore di ManaPaid (Color di Arena)
COLORI_RISERVA = {"ManaColor_White": "W", "ManaColor_Blue": "U", "ManaColor_Black": "B", "ManaColor_Red": "R", "ManaColor_Green": "G"}


def parole_chiave():
    """{grpId di un'abilita': parola chiave} dalla tabella delle abilita' di Arena (Regole/abilita_combattimento.json, abilita_arena.py)."""
    global _KW
    if _KW is None:
        try:
            d = json.load(open(os.path.join(percorsi.ROOT, "Regole", "abilita_combattimento.json"), encoding="utf-8"))
            _KW = {int(k): v["kw"] for k, v in (d.get("abilita") or {}).items() if isinstance(v, dict) and v.get("kw")}
        except (OSError, ValueError):
            _KW = {}
    return _KW


# i tipi di designazione di Arena (DesignationType), dedotti il 14 nov 2026 dalle carte che li fanno nei log (il database non li elenca): 24 la magia
# preparata (Reality Fracture), 19 e 20 le porte sbloccate di una Room, 18 la carta complottata (plot), 15 il caso risolto, 16 sospettato, 21 la
# velocita' del giocatore (Start your engines!, col valore), 22 imbrigliata (The Soul Stone)
DESIGNAZIONI = {24: "PREPARED", 19: "DOOR UNLOCKED", 20: "DOOR UNLOCKED", 18: "PLOTTED", 15: "SOLVED", 16: "SUSPECTED", 22: "HARNESSED"}


# le parole d'abilita' di Arena (AbilityWordActive, AbilityWordName) coi nomi da giocatore; le altre si leggono spezzando il CamelCase
PAROLE_ABILITA = {"CollectEvidenceCount": "Evidence", "LifeGainedThisTurn": "Life gained", "NumberOfMountainsYouControl": "Mountains",
                  "ToSolveCondition": "To solve", "NumberOfSpellsCast": "Spells cast", "TriggeringAmountLifeChange": "Life change",
                  "NumberOfLessonCardsInYourGraveyard": "Lessons", "NumberOfTimesResolvedThisTurn": "Resolved", "Descend4": "Descend 4",
                  "Descend8": "Descend 8"}


def nome_parola(n):
    if n in PAROLE_ABILITA:
        return PAROLE_ABILITA[n]
    t = re.sub(r"(?<=[a-z])(?=[A-Z0-9])", " ", n or "").replace("Number Of ", "").replace(" You Control", "")
    return t[:1].upper() + t[1:].lower() if t else ""


# Il tipo di Qualification di Arena -> (scritta sulla carta, genere): «no» un divieto (rosso), «si» un permesso (blu). Letti il 15 nov 2026 sulle ultime 300
# partite col testo dell'abilita' che li da' (testi_arena.abilita del «grpid»): 21 «doesn't untap», 30 «can't attack or block», 31 «can't block», 32 «can't be
# blocked», 39 «can't be blocked by more than one creature», 49 «can attack as though it didn't have defender», 11 «activated abilities ... can't be
# activated», 10 «this spell can't be countered». Gli altri (costi ridotti, effetti su tutto il tavolo, 47 giocabile, 40 menace) non sono uno stato della carta.
STATI_QUAL = {21: ("NO UNTAP", "no"), 30: ("NO ATTACK/BLOCK", "no"), 31: ("CAN'T BLOCK", "no"), 32: ("UNBLOCKABLE", "si"), 39: ("1 BLOCKER MAX", "si"),
              49: ("CAN ATTACK", "si"), 11: ("ABILITIES OFF", "no"), 10: ("UNCOUNTERABLE", "si")}


def metti_stato(x, i, st):
    """Lo stato (scritta, genere) sulla carta i, una volta sola; il livello di una Classe sostituisce quello di prima."""
    lst = x.setdefault(i, {}).setdefault("st", [])
    if st[1] == "liv":
        lst[:] = [e_ for e_ in lst if e_[1] != "liv"]
    if list(st) not in lst and len(lst) < 5:
        lst.append(list(st))


CLIENTE = "[CLIENTE] "
RICHIESTE_RIGA = ("declareAttackersReq", "declareBlockersReq", "selectTargetsReq", "castingTimeOptionsReq", "selectNReq", "onChat", "dieRollResultsResp",
                  "optionalActionMessage", CLIENTE)


def condizione_gioco(det, obj, zona, chi):
    """Il permesso di giocare una carta esiliata con una condizione (16 nov 2026, Autore: «le carte esiliate utilizzabili da Gandalf solo quando un wizard
    e' sul campo ... le vedo sempre esiliate playabili anche se non ho un wizard»): Arena tiene il permesso finche' la carta resta in esilio (Flameshape:
    «you may play them if you control a Wizard»), anche quando la condizione non c'e'. Se il testo dell'abilita' dice «if you control a(n) X», la carta e'
    giocabile solo con una carta di quel tipo nel campo di chi la gioca. Senza condizione, o senza testo, vale il permesso."""
    import re
    try:
        import testi_arena as TA_
        tx_ = TA_.abilita((det.get("grpid") or [0])[0]) or ""
    except Exception:      # noqa: BLE001 - senza database vale il permesso di Arena
        return True
    m_ = re.search(r"if you control an? ([A-Z][a-z]+)", tx_)
    if not m_:
        return True
    tipo_ = m_.group(1)
    for o_ in obj.values():
        if o_.get("controllerSeatId") == chi and zona(o_) == "ZoneType_Battlefield" and \
                (f"SubType_{tipo_}" in (o_.get("subtypes") or []) or f"CardType_{tipo_}" in (o_.get("cardTypes") or [])):
            return True
    return False


def segni(pers, obj, ricordo, tutti, zona=lambda o: None, scelte=None):
    """I segni che restano sul tavolo (14 nov 2026, il censimento: «poi i segni che restano sul tavolo»), dalle annotazioni persistenti di Arena:
    {id: dict(tmp=1 se se ne va a fine turno, sotto=[grpId delle carte sotto di lei], kw=[parole chiave date], des=[designazioni])}, e la velocita'
    dei giocatori {posto: valore}."""
    x, vel, kw = {}, {}, parole_chiave()
    for i, t_ in (scelte or {}).items():       # la scelta fatta resta sulla carta (il tipo di Cavern of Souls)
        x.setdefault(i, {})["ch"] = t_
    for a in pers.values():
        ty = a.get("type") or []
        det = {d_.get("key"): d_.get("valueInt32") or d_.get("valueString") or [] for d_ in a.get("details") or []}
        aff = a.get("affectedIds") or []
        if "AnnotationType_ModifiedColor" in ty and det.get("color"):
            # il colore cambiato (15 nov 2026, il censimento): le terre Restless che diventano creature, Witness Protection; i colori di Arena 1-5 = WUBRG
            col_ = " · ".join({1: "WHITE", 2: "BLUE", 3: "BLACK", 4: "RED", 5: "GREEN"}.get(c_, "?") for c_ in det["color"][:3])
            for i in aff:
                if i not in (1, 2):
                    metti_stato(x, i, ("NOW " + col_, "col"))
        if "AnnotationType_ModifiedType" in ty:
            for i in aff:       # la terra diventata creatura (le terre Restless, earthbend di TLA): resta una terra ma attacca e blocca
                ct_ = (obj.get(i) or {}).get("cardTypes") or []
                if i not in (1, 2) and "CardType_Creature" in ct_ and "CardType_Land" in ct_:
                    metti_stato(x, i, ("NOW A CREATURE", "si"))
        if "AnnotationType_TemporaryPermanent" in ty:
            for i in aff:
                x.setdefault(i, {})["tmp"] = 1
        elif "AnnotationType_DisplayCardUnderCard" in ty and not (det.get("Disable") or [0])[0] and a.get("affectorId"):
            for i in aff:
                o = obj.get(i) or ricordo.get(i)
                if o and o.get("grpId"):
                    lst = x.setdefault(a["affectorId"], {}).setdefault("sotto", [])
                    g_ = MA.grp_vero(o, tutti)
                    if len(lst) < 8:
                        lst.append(g_)
        elif "AnnotationType_AddAbility" in ty:
            date = [kw[g_] for g_ in det.get("grpid") or [] if g_ in kw]
            altre = [g_ for g_ in det.get("grpid") or [] if g_ not in kw]      # le abilita' date che non sono parole chiave (il loro grpId)
            for i in aff:
                for k_ in date:
                    lst = x.setdefault(i, {}).setdefault("kw", [])
                    if k_ not in lst:
                        lst.append(k_)
                for g_ in altre:
                    lst = x.setdefault(i, {}).setdefault("ab", [])
                    if g_ not in lst and len(lst) < 4:
                        lst.append(g_)
        elif "AnnotationType_ReplacementEffect" in ty:
            # la sostituzione che una carta mette su un'altra (16 nov 2026, Autore: «nel log esistono ulteriori note che fino ad adesso non sono state
            # considerate?»; Scorching Dragonfire, Fiery Annihilation: «if that creature would die this turn, exile it instead»): il suo testo sulla carta
            # che la subisce, finche' vale. Le sostituzioni della carta su se stessa («as it enters...», Fog Bank) si vedono gia' dal risultato
            ric_ = (det.get("replacedEffectRecipient") or [None])[0]
            src_ = (det.get("replacedEffectSource") or [None])[0]
            g_r = (det.get("grpid") or [None])[0]
            if ric_ and g_r and ric_ != src_ and ric_ != a.get("affectorId"):
                try:
                    import testi_arena as TA_
                    tx_r = TA_.abilita(g_r) or ""
                except Exception:      # noqa: BLE001 - senza database niente testo
                    tx_r = ""
                if "would" in tx_r:
                    lst = x.setdefault(ric_, {}).setdefault("ab", [])
                    if g_r not in lst and len(lst) < 4:
                        lst.append(g_r)
        elif "AnnotationType_LoyaltyActivationsRemaining" in ty:       # il potere del planeswalker ancora da usare in questo turno (16 nov 2026)
            for i in aff:
                x.setdefault(i, {})["lar"] = (det.get("ActivationsRemaining") or [0])[0]
        elif "AnnotationType_Attachment" in ty and a.get("affectorId") and aff:
            # l'aura o l'equipaggiamento attaccato (15 nov 2026, Autore: «quando una carta riceve un incantesimo aura o indossa un artefatto, non dovremmo
            # vedere quelle carte al di sotto di chi l'ha ricevuta?»): Arena lo scrive come annotazione persistente, l'aura (affector) sulla carta (affected)
            x.setdefault(a["affectorId"], {})["su"] = aff[0]
            o = obj.get(a["affectorId"]) or ricordo.get(a["affectorId"]) or {}
            lst = x.setdefault(aff[0], {}).setdefault("porta", [])
            if not any(e_[0] == a["affectorId"] for e_ in lst) and len(lst) < 6:
                lst.append([a["affectorId"], MA.grp_vero(o, tutti) if o.get("grpId") else 0])
        elif "AnnotationType_AbilityWordActive" in ty and det.get("AbilityWordName"):
            # la parola d'abilita' attiva (14 nov 2026, il censimento: 3.860 volte nei log): il nome e, se Arena li scrive, il conto e la soglia
            n_aw = nome_parola(det["AbilityWordName"][0])
            v_aw = (det.get("value") or [None])[0]
            s_aw = (det.get("threshold") or [None])[0]
            for i in aff:
                if i in (1, 2):
                    continue
                lst = x.setdefault(i, {}).setdefault("aw", [])
                if len(lst) < 2 and not any(e_[0] == n_aw for e_ in lst):
                    lst.append([n_aw, v_aw, s_aw])
        elif "AnnotationType_Qualification" in ty and (det.get("QualificationType") or [None])[0] == 47:
            # «puoi giocare questa carta» (14 nov 2026, Autore: «Exiled and playable ... sono situazioni molto importanti per la partita»): Arena lo
            # scrive per le carte esiliate e giocabili (impulse, avventura, foretell, plot, warp) e per quelle giocabili dal cimitero, finche' vale
            for i in aff:
                o = obj.get(i) or {}
                z_ = zona(o)
                # chi puo' giocarla: chi controlla la fonte del permesso (una tua carta che ti fa giocare le sue esiliate), se no il proprietario
                fonte_ = obj.get(a.get("affectorId")) or ricordo.get(a.get("affectorId")) or {}
                chi_g = fonte_.get("controllerSeatId") if fonte_.get("controllerSeatId") in (1, 2) else o.get("ownerSeatId")
                if z_ in ("ZoneType_Exile", "ZoneType_Graveyard") and chi_g in (1, 2) and condizione_gioco(det, obj, zona, chi_g):
                    # senza grpId: a faccia in giu' (il suo foretell)
                    x.setdefault(i, {})["gioca"] = [MA.grp_vero(o, tutti) if o.get("grpId") else 0, chi_g, "esi" if z_ == "ZoneType_Exile" else "cim"]
        elif "AnnotationType_Qualification" in ty and (det.get("QualificationType") or [None])[0] in STATI_QUAL:
            # lo stato della carta (15 nov 2026, il censimento: 1.048 passi coi divieti e i permessi che non si vedevano): non si stappa, non puo' bloccare,
            # non bloccabile... il tipo lo dice Arena, l'abilita' che lo da' e' «grpid» (letti sulle partite vere col testo del database di Arena)
            for i in aff:
                if i not in (1, 2):
                    metti_stato(x, i, STATI_QUAL[det["QualificationType"][0]])
        elif ("AnnotationType_CrewedThisTurn" in ty or "AnnotationType_SaddledThisTurn" in ty) and a.get("affectorId"):
            # equipaggiato o sellato in questo turno (15 nov 2026, il censimento): il veicolo o la cavalcatura (affector) e chi l'ha fatto (affected)
            cr_ = "AnnotationType_CrewedThisTurn" in ty
            if a["affectorId"] not in (1, 2):
                metti_stato(x, a["affectorId"], ("CREWED" if cr_ else "SADDLED", "si"))
            for i in aff:
                if i not in (1, 2) and i != a["affectorId"]:
                    metti_stato(x, i, ("CREWING" if cr_ else "SADDLING", "off"))
        elif "AnnotationType_CopiedObject" in ty:
            for i in aff:       # la carta originale sotto la copia: la pillola COPY OF
                o = obj.get(i) or ricordo.get(i) or {}
                if i not in (1, 2) and o.get("grpId"):
                    x.setdefault(i, {})["copia_di"] = MA.grp_vero(o, tutti)
        elif "AnnotationType_AbilityExhausted" in ty and not (det.get("UsesRemaining") or [1])[0]:
            # l'abilita' gia' usata: exhaust (una volta per partita) o «only once each turn» (Exemplar of Light), dal testo dell'abilita'
            try:
                import testi_arena as TA
                t_ab = (TA.abilita((det.get("AbilityGrpId") or [0])[0]) or "").lower()
            except Exception:      # noqa: BLE001 - senza database: la scritta generica
                t_ab = ""
            st_ab = ("EXHAUSTED", "off") if "exhaust" in t_ab else ("USED THIS TURN", "off")
            for i in aff:
                if i not in (1, 2):
                    metti_stato(x, i, st_ab)
        elif "AnnotationType_RemoveAbility" in ty and any("all" in (v_ or []) for v_ in det.values() if isinstance(v_, list)):
            for i in aff:       # «loses all abilities», data da un'altra carta (la carta su se stessa e' il suo modo di cambiare tipo: Multiversal Passage)
                if i not in (1, 2) and i != a.get("affectorId"):
                    metti_stato(x, i, ("NO ABILITIES", "no"))
        elif "AnnotationType_ClassLevel" in ty and det.get("Level"):
            for i in aff:       # il livello raggiunto da una Classe
                if i not in (1, 2):
                    metti_stato(x, i, (f"LEVEL {det['Level'][0]}", "liv"))
        elif "AnnotationType_Designation" in ty:
            dt = (det.get("DesignationType") or [None])[0]
            for i in aff:
                if i in (1, 2):
                    if dt == 21 and det.get("value"):
                        vel[i] = det["value"][0]
                elif dt in DESIGNAZIONI:
                    lst = x.setdefault(i, {}).setdefault("des", [])
                    if DESIGNAZIONI[dt] not in lst:
                        lst.append(DESIGNAZIONI[dt])
    return x, vel


def con_client(righe):
    """Le righe del log con i messaggi del tuo client (scritti su piu' righe: «... to Match: ClientToGremessage» e poi il JSON) raccolti ognuno in una riga
    sola, «[CLIENTE] {json}», al loro posto (16 nov 2026, Autore: «montiamo ... gli altri messaggi del client»)."""
    out, buf = [], None
    for k, l in enumerate(righe):
        if buf is None:
            if l.strip() == "{" and k > 0 and " to Match: " in righe[k - 1]:
                buf = [l]
            else:
                out.append(l)
            continue
        buf.append(l)
        if l.rstrip() == "}":
            try:
                out.append(CLIENTE + json.dumps(json.loads("\n".join(buf)).get("payload") or {}))
            except ValueError:
                pass
            buf = None
    return out



def azioni(righe, nome=lambda g: None, interni=False):
    """Le righe del log di una partita -> [dict(t, step, att, foto, ev=[(posto o None, testo)], danni=[(bersaglio, quanto)], rel)]: una foto a ogni azione che
    si vede. nome(grpId) da' il nome di una carta (per i testi); le foto portano i grpId come quelle di mana_aperto.
    Debug del 12 nov 2026 (Autore: «riguarda in maniera approfondita come il replayer legge i log e le azioni, debugga tutto»): le cancellazioni da
    diffDeletedInstanceIds; ogni oggetto visto resta ricordato (una pedina sacrificata o morta cambia id e sparisce nello stesso messaggio: senza il ricordo era
    «a card» senza chi); l'annullamento di Arena toglie le azioni annullate (prima una terra e una magia annullate e rifatte contavano due volte); le vite a 0;
    emblemi e inneschi ritardati col nome della carta; dove Arena ha riassunto un messaggio, l'azione lo dice."""
    obj, zone, zown, zids, vite, ti = {}, {}, {}, {}, {}, {}
    pers = {}           # le annotazioni persistenti: i segnalini (14 nov 2026)
    frames, bersagli, att_prima = [], {}, None
    # cio' che una magia o un'abilita' toglie dal campo, per le frecce (13 nov 2026, Settle the Wreckage: il bersaglio e' il giocatore, le creature esiliate
    # le dice l'affectorId delle ZoneTransfer): {id in pila: dict(prima=id in campo quando e' entrata, fatti=id che ha spostato lei, rels=[rel delle foto])}
    in_pila, risolve = {}, set()       # risolve: fra ResolutionStart e ResolutionComplete (Arena sposta i permanenti con la magia ancora in pila)
    ricordo, origine = {}, {}         # {id: oggetto com'era l'ultima volta}, {id nuovo: id di prima} (ObjectIdChanged)
    scelte_carte, riserva, sorv = {}, {}, None      # la scelta fatta per carta (il censimento); il mana in riserva per posto; il surveil in attesa
    sorv_suo = {}                                   # il surveil che non chiede niente a te (il suo): per abilita', chi, quante, quelle al cimitero
    riassunto, finita, veleno = False, False, {}
    annunciate = set()      # le abilita' gia' raccontate «on the stack» (15 nov 2026, il verificatore della pila)
    pila_msg = []           # la pila del messaggio prima: chi la lascia senza un'altra azione ha un passo suo (16 nov 2026)
    pila_storia = {}        # {gameStateId: la pila dopo quel messaggio}: l'annullamento rimette la pila di prima dello stato a cui torna
    da_preparata = {}       # {id in pila: id della creatura}: la copia preparata lanciata dalla creatura che perde PREPARED (15 nov 2026)
    da_zona = {}            # {id in pila: [zona, posto del proprietario]}: la magia lanciata fuori dalla mano (cimitero, esilio, grimorio; 15 nov 2026)

    class _Tutti:       # gli oggetti di adesso e quelli ricordati, per trovare il padre di un'abilita'
        @staticmethod
        def get(k, d=None):
            return obj.get(k) or ricordo.get(k) or d
    tutti = _Tutti()

    def scattata_da(ab_id, o_ab):
        """Chi ha fatto scattare l'abilita' in pila (15 nov 2026, il censimento: TriggeringObject, 5.345 volte): gli oggetti dell'annotazione persistente,
        tolta la fonte dell'abilita' (la sua freccia c'e' gia': «Ability of X»)."""
        fonte = (o_ab or {}).get("parentId")
        return [i for a_ in pers.values() if "AnnotationType_TriggeringObject" in (a_.get("type") or []) and a_.get("affectorId") == ab_id
                for i in a_.get("affectedIds") or [] if i != fonte and i not in (1, 2)][:4]

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
        seg = MA.segnalini(pers)
        # la carta che e' una copia (15 nov 2026, il censimento: CopiedObject): Arena lascia il grpId dell'originale e scrive in copyFromGrpid cosa copia;
        # in campo si vede cio' che copia (la carta originale sta nei segni, «copia_di»)
        copie = {}
        for a_ in pers.values():
            if "AnnotationType_CopiedObject" in (a_.get("type") or []):
                g_c = next((d_.get("valueInt32") or [None])[0] for d_ in a_.get("details") or [] if d_.get("key") == "copyFromGrpid")                     if any(d_.get("key") == "copyFromGrpid" for d_ in a_.get("details") or []) else None
                if g_c:
                    for i in a_.get("affectedIds") or []:
                        copie[i] = g_c
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
                        c[o["controllerSeatId"] - 1].append([copie.get(i, o["grpId"]), 1 if o.get("isTapped") else 0, 1 if o["type"] == "GameObjectType_Token" else 0,
                                                             valore(o, "power") if crea else None, valore(o, "toughness") if crea else None, i, seg.get(i) or None])
            elif tp == "ZoneType_Hand" and zown.get(zid) in (1, 2):
                k = zown[zid] - 1
                n[k] = len(ids)
                m[k] = [obj[i]["grpId"] for i in ids if i in obj and obj[i].get("grpId")]
        pl = []         # la pila intera, dalla cima (14 nov 2026, Autore: «ora le carte si rispondono in maniera corretta impilandosi ma l'area pila sparisce»)
        for zid, tp in zone.items():
            if tp == "ZoneType_Stack":
                for i in zids.get(zid, []):
                    o = obj.get(i)
                    # una terra non sta mai in pila (le terre si giocano, non si lanciano): quelle rivelate che Arena mette per un attimo nella zona della
                    # pila (Solstice Revelations, Improvisation Capstone) non si mostrano come magie (16 nov 2026)
                    if o and o.get("controllerSeatId") in (1, 2) and not (o.get("type") == "GameObjectType_Card" and "CardType_Land" in (o.get("cardTypes") or [])):
                        pl.append([MA.grp_vero(o, tutti), o["controllerSeatId"], 1 if o.get("type") == "GameObjectType_Ability" else 0, i])
        pl_ids = {e_[3] for e_ in pl}
        x, vel = segni(pers, obj, ricordo, tutti, lambda o: zone.get(o.get("zoneId")), scelte_carte)
        for i_d in ids_di("ZoneType_Battlefield"):       # il danno gia' segnato sulla creatura fino a fine turno (16 nov 2026)
            dm_ = (obj.get(i_d) or {}).get("damage")
            if dm_:
                metti_stato(x, i_d, (f"{dm_} DAMAGE", "no"))
        # il potere del planeswalker nel turno del suo controllore (16 nov 2026, «vai monta»): ancora da usare o gia' usato
        for i_w in ids_di("ZoneType_Battlefield"):
            o_w = obj.get(i_w) or {}
            if "CardType_Planeswalker" in (o_w.get("cardTypes") or []) and o_w.get("controllerSeatId") == ti.get("activePlayer"):
                metti_stato(x, i_w, ("POWER USED", "off") if (ti.get("turnNumber"), i_w) in pw_usati else ("POWER READY", "si"))
        # le copie senza CopiedObject (le pedine copia, le magie copiate) e le carte a faccia in giu' in campo (15 nov 2026, le meta' del censimento: Arena
        # le segna sull'oggetto, isCopy e isFacedown; a faccia in giu' il proprietario ne vede il nome, l'altro un dorso)
        for lato_c in c:
            for e_c in lato_c:
                o_c = obj.get(e_c[5]) or {}
                if o_c.get("isCopy") and not (x.get(e_c[5]) or {}).get("copia_di"):
                    metti_stato(x, e_c[5], ("COPY", "si"))
                if o_c.get("isFacedown"):
                    metti_stato(x, e_c[5], ("FACE DOWN", "off"))
        out = dict(c=c, m=m, n=n, v=[vite.get(1), vite.get(2)], g=g, e=e, p=pl)
        abt_ = {str(e_[3]): obj[e_[3]].get("grpId") for e_ in pl if e_[2] and obj.get(e_[3], {}).get("grpId")}
        if abt_:        # quale abilita' e' in pila (il potere del planeswalker): l'id della sua abilita', il testo dal database di Arena (16 nov 2026)
            out["abt"] = abt_
        # le copie in pila (707.10: risolte smettono di esistere, non vanno in nessuna zona) e da dove parte la copia preparata
        copie_p = [e_[3] for e_ in pl if (obj.get(e_[3]) or {}).get("isCopy")]
        if copie_p:
            out["pc"] = copie_p
        pd_ = {e_[3]: da_preparata[e_[3]] for e_ in pl if e_[3] in da_preparata}
        if pd_:
            out["pd"] = pd_
        pz_ = {e_[3]: da_zona[e_[3]] for e_ in pl if e_[3] in da_zona}
        if pz_:
            out["pz"] = pz_
        # come e' stata lanciata la magia in pila (15 nov 2026, il censimento: CastingTimeOption, 479 volte): kicker, il valore di X, il costo alternativo o
        # aggiuntivo; {id in pila: [scritte]}
        op = {}
        for a_ in pers.values():
            if "AnnotationType_CastingTimeOption" in (a_.get("type") or []):
                d_ = {e_.get("key"): e_.get("valueInt32") or e_.get("valueString") or [] for e_ in a_.get("details") or []}
                t_ = (d_.get("type") or [None])[0]
                sc_ = {3: "KICKED", 5: "EXTRA COST", 11: "EXTRA COST"}.get(t_)
                if t_ == 2 and d_.get("value"):
                    sc_ = f"X = {d_['value'][0]}"
                elif t_ == 13 and d_.get("alternateCostGrpId"):
                    # il costo alternativo dal testo della sua abilita' (letti sui log: 149 gratis, flashback, plot, la vita); senza testo niente scritta
                    try:
                        import testi_arena as TA
                        t_alt = (TA.abilita(d_["alternateCostGrpId"][0]) or "").lower()
                    except Exception:      # noqa: BLE001 - senza database niente scritta
                        t_alt = ""
                    sc_ = ("FREE" if "without paying" in t_alt else "FLASHBACK" if t_alt.startswith("flashback") else "FROM PLOT" if t_alt.startswith("plot")
                           else "PAID WITH LIFE" if t_alt.startswith("pay life") else None)
                for i in a_.get("affectedIds") or []:
                    if sc_ and i in pl_ids and sc_ not in op.setdefault(i, []):
                        op[i].append(sc_)
        for e_p in pl:      # la magia copiata in pila (una copia di Twinned Vision, di un'abilita'): COPY sulla carta in cima
            if (obj.get(e_p[3]) or {}).get("isCopy") and "COPY" not in op.setdefault(e_p[3], []):
                op[e_p[3]].insert(0, "COPY")
        op = {k_: v_ for k_, v_ in op.items() if v_}
        if op:
            out["op"] = op
        # gli emblemi (15 nov 2026): gli oggetti Emblem della zona Command, col grpId della carta che li ha creati, per posto
        em = [[], []]
        for zid, tp in zone.items():
            if tp == "ZoneType_Command":
                for i in zids.get(zid) or []:
                    o_e = obj.get(i) or {}
                    if o_e.get("type") == "GameObjectType_Emblem" and o_e.get("controllerSeatId") in (1, 2) and o_e.get("objectSourceGrpId"):
                        em[o_e["controllerSeatId"] - 1].append(o_e["objectSourceGrpId"])
        if em[0] or em[1]:
            out["em"] = em
        # la carta in cima al grimorio che si conosce (15 nov 2026, Autore: «quando effettuiamo azioni che ci permettono di conoscere la prossima pescata
        # ... dovrebbe restare visibile la carta in testa al mazzo / se poi la conosce anche l'avversario, allora dovrebbe avere il logo dell'occhio aperto»):
        # Arena la manda col grpId (privata: la conosce solo il proprietario; pubblica: tutti e due), per posto [grpId, 1 se pubblica] o None
        cm = [None, None]
        lb = [None, None]       # quante carte nel grimorio di ognuno: la zona elenca anche le carte coperte (24 nov 2026, il «?» dell'Opponent)
        for zid, tp in zone.items():
            if tp == "ZoneType_Library" and zown.get(zid) in (1, 2):
                lb[zown[zid] - 1] = len(zids.get(zid) or [])
                ids_l = zids.get(zid) or []
                o_l = obj.get(ids_l[0]) if ids_l else None
                if o_l and o_l.get("grpId"):
                    cm[zown[zid] - 1] = [MA.grp_vero(o_l, tutti), 1 if o_l.get("visibility") == "Visibility_Public" else 0]
        if cm[0] or cm[1]:
            out["cm"] = cm
        if lb[0] is not None or lb[1] is not None:
            out["lb"] = lb
        # le carte della mano mostrate all'altro giocatore (15 nov 2026, il censimento: InstanceRevealedToOpponent, 698 volte): i grpId per posto
        mostrate = {i for a_ in pers.values() if "AnnotationType_InstanceRevealedToOpponent" in (a_.get("type") or []) for i in a_.get("affectedIds") or []}
        if mostrate:
            mv = [[], []]
            for zid, tp in zone.items():
                if tp == "ZoneType_Hand" and zown.get(zid) in (1, 2):
                    mv[zown[zid] - 1] += [obj[i]["grpId"] for i in zids.get(zid, []) if i in mostrate and i in obj and obj[i].get("grpId")]
            if mv[0] or mv[1]:
                out["mv"] = mv
        if riserva.get(1) or riserva.get(2):      # il mana in riserva (fluttua): [[colori del posto 1], [del posto 2]]
            out["mp"] = [list(riserva.get(1) or []), list(riserva.get(2) or [])]
        if x:
            out["x"] = x
        if vel:
            out["vel"] = vel
        return out

    def fonti_di(gs, cima):
        """Le fonti di mana che hanno pagato la magia (o l'abilita') cima in questo messaggio: {affectorId di ManaPaid: [colori]} (W U B R G, C)."""
        out = {}
        for a in gs.get("annotations") or []:
            if "AnnotationType_ManaPaid" in (a.get("type") or []) and cima in (a.get("affectedIds") or []):
                out.setdefault(a.get("affectorId"), []).append(COLORI_MANA.get(_dettaglio(a, "color"), "C"))
        return out

    def dest_mana(x):
        """Dove va il mana speso per x, se non e' una magia dalla mano: il permanente che attiva l'abilita', o il permanente in campo che si paga."""
        o_c = ogg(x) if x is not None else {}
        if o_c.get("type") == "GameObjectType_Ability":
            return o_c.get("parentId") or o_c.get("objectSourceId")
        if x in ids_di("ZoneType_Battlefield"):
            return x
        return None

    def paga(fonti, pagato=None):
        """Il passo del pagamento prima del lancio (14 nov 2026, Autore: «abbiamo ancora il problema della spell prima del mana»): la foto del passo
        prima, con le fonti di mana tappate e la carta ancora in mano; poi il lancio la porta in pila. Una volta per lancio."""
        if not fonti or len(frames) < 2 or frames[-1].get("_pagato"):
            return
        lancio = frames[-1]
        cima = pagato if pagato is not None else lancio.get("_cima")
        pagati_qui.add(cima)        # una volta per messaggio (16 nov 2026: Food pagata due volte, all'abilita' in pila e al sacrificio)
        f2 = copy.deepcopy(frames[-2]["foto"])
        f2.pop("r", None), f2.pop("s", None), f2.pop("sc", None), f2.pop("mn", None), f2.pop("pt", None), f2.pop("hv", None), f2.pop("ch", None), f2.pop("pdd", None), f2.pop("sp", None), f2.pop("pf", None), f2.pop("trz", None), f2.pop("hvm", None), f2.pop("conc", None)
        for lato in f2["c"]:
            for c_ in lato:
                if len(c_) > 5 and c_[5] in fonti:
                    c_[1] = 1
        lancio["_pagato"] = True
        f2["mn"] = [[i_, col_] for i_, cols_ in (fonti.items() if isinstance(fonti, dict) else []) for col_ in cols_]      # il mana che vola alla magia
        # dove va il mana speso (15 nov 2026, il verificatore del mana): l'abilita' attivata sul permanente che la attiva, il pagamento sul permanente in campo
        # (la porta della Room che si apre) su di lui; la magia lanciata resta com'era (dalla mano alla pila)
        if dest_mana(cima) is not None:
            f2["mnd"] = dest_mana(cima)
        # se in pila c'era gia' una magia (lui risponde alla tua), mentre paga resta a vista (14 nov 2026, Autore: «se gioco una carta e oppo si tappa
        # per giocare la sua, la mia pila sparisce e riappare solo con la giocata di oppo»)
        sotto, rel_s = frames[-2].get("_cima"), None
        if sotto is not None and sotto != cima and (frames[-2].get("rel") or {}).get("k") == "spell":
            rel_s = copy.deepcopy(frames[-2]["rel"])
            if sotto in in_pila:
                in_pila[sotto]["rels"].append(rel_s)
        frames.insert(len(frames) - 1, dict(t=lancio["t"], step=lancio["step"], att=lancio["att"], foto=f2, ev=[(chi_(cima), f"paid mana for {n_(cima)}")],
                                            danni=[], rel=rel_s, _s=lancio["_s"], _att=False, _cima=sotto if rel_s else None, _pagato=True, _pag=cima, _pag_s=sid))

    pagati_qui = set()
    giocate, richieste, dado = {}, {}, {}
    pw_usati = set()
    mulligan, effetti_pt = {}, {}
    mull_scelte, parte_scelta = [], []
    for r in con_client(righe):
        if r.startswith(CLIENTE):
            try:
                p_c = json.loads(r[len(CLIENTE):])
            except ValueError:
                continue
            t_c = (p_c.get("type") or "").replace("ClientMessageType_", "")
            s_c = p_c.get("gameStateId") or 0
            if t_c == "UIMessage" and ((p_c.get("uiMessage") or {}).get("onHover") or {}).get("objectId") and frames:
                hm_ = frames[-1]["foto"].setdefault("hvm", [])       # le carte che guardavi tu
                o_h = p_c["uiMessage"]["onHover"]["objectId"]
                if o_h not in hm_ and len(hm_) < 3:
                    hm_.append(o_h)
            elif t_c == "ConcedeReq" and frames:
                frames[-1]["foto"]["conc"] = 1
            elif t_c == "CancelActionReq":
                richieste.setdefault(s_c, {})["canc"] = 1
            elif t_c == "PerformAutoTapActionsResp":
                richieste.setdefault(s_c, {})["auto"] = 1
            elif t_c == "MulliganResp":
                mull_scelte.append((p_c.get("mulliganResp") or {}).get("decision", "").replace("MulliganOption_", ""))
            elif t_c == "ChooseStartingPlayerResp":
                parte_scelta.append((p_c.get("chooseStartingPlayerResp") or {}).get("systemSeatId"))
            elif t_c == "OptionalActionResp":
                richieste.setdefault(s_c, {})["opr"] = (p_c.get("optionalResp") or {}).get("response", "").replace("OptionResponse_", "")
            elif t_c == "SearchResp":
                richieste.setdefault(s_c, {})["cerca"] = [MA.grp_vero(ogg(i_), tutti) if ogg(i_).get("grpId") else 0
                                                          for i_ in (p_c.get("searchResp") or {}).get("itemsFound") or []]
            elif t_c == "AssignDamageResp":
                richieste.setdefault(s_c, {})["div"] = [[MA.grp_vero(ogg(a_.get("instanceId")), tutti) or 0,
                                                         [[MA.grp_vero(ogg(b_.get("instanceId")), tutti) or 0, b_.get("assignedDamage", 0)]
                                                          for b_ in a_.get("assignments") or []]]
                                                        for a_ in (p_c.get("assignDamageResp") or {}).get("assigners") or []]
            elif t_c == "PerformActionResp" and any(a_.get("actionType") == "ActionType_Pass" for a_ in (p_c.get("performActionResp") or {}).get("actions") or []):
                richieste.setdefault(s_c, {})["pp"] = 1
            continue
        if r.startswith(MA.RIASSUNTO):
            riassunto = True
            continue
        if "gameStateMessage" not in r and "GroupingContext_Surveil" not in r and "ActionsAvailableReq" not in r and "onHover" not in r \
                and not any(k_r in r for k_r in RICHIESTE_RIGA):
            continue
        i = r.find("{")
        if i < 0:
            continue
        try:
            d = json.loads(r[i:])
        except ValueError:
            continue
        for msg in (d.get("greToClientEvent") or {}).get("greToClientMessages") or []:
            u_ = msg.get("uiMessage") or {}
            if (u_.get("onHover") or {}).get("objectId") and frames:
                # dove guarda l'avversario (16 nov 2026, Autore: «nel log esistono ulteriori note che fino ad adesso non sono state considerate?», poi
                # «ok» al cursore dell'avversario): Arena ti manda la carta che lui ha sotto il mouse; resta sul passo in cui succede, al massimo tre carte
                chi_h = (u_.get("seatIds") or [None])[0]
                if chi_h is not None and chi_h != (msg.get("systemSeatIds") or [None])[0]:
                    hv_ = frames[-1]["foto"].setdefault("hv", [])
                    o_h = u_["onHover"]["objectId"]
                    if o_h not in hv_ and len(hv_) < 3:
                        hv_.append(o_h)
                continue
            if (u_.get("onChat") or {}).get("text") and frames:      # le emote (16 nov 2026, «vai monta»): chi e la frase
                frames[-1]["foto"].setdefault("ch", []).append([(u_.get("seatIds") or [None])[0], u_["onChat"]["text"]])
                continue
            if msg.get("dieRollResultsResp"):       # il dado per chi comincia
                dado.update({d_.get("systemSeatId"): d_.get("rollValue") for d_ in msg["dieRollResultsResp"].get("playerDieRolls") or []})
                continue
            chi_q = (msg.get("systemSeatIds") or [None])[0]
            sid_q = msg.get("gameStateId") or 0
            if msg.get("declareAttackersReq"):     # chi poteva attaccare (16 nov 2026, «vai monta»)
                q_ = msg["declareAttackersReq"]
                richieste.setdefault(sid_q, {})["pa"] = dict(chi=chi_q, ids=[a_.get("attackerInstanceId") for a_ in (q_.get("attackers") or q_.get("qualifiedAttackers") or [])
                                                                            if a_.get("attackerInstanceId")])
                continue
            if msg.get("declareBlockersReq"):      # chi poteva bloccare, e chi
                richieste.setdefault(sid_q, {})["pb"] = dict(chi=chi_q, b=[[b_.get("blockerInstanceId"), list(b_.get("attackerInstanceIds") or [])]
                                                                          for b_ in msg["declareBlockersReq"].get("blockers") or [] if b_.get("blockerInstanceId")])
                continue
            if msg.get("selectTargetsReq"):        # i bersagli legali
                lt_ = [t_.get("targetInstanceId") for g_ in msg["selectTargetsReq"].get("targets") or [] for t_ in g_.get("targets") or []
                       if t_.get("targetInstanceId")]
                if lt_:
                    richieste.setdefault(sid_q, {})["lt"] = dict(chi=chi_q, ids=list(dict.fromkeys(lt_)))
                continue
            if msg.get("optionalActionMessage"):       # «puoi farlo»: la carta che lo chiede (la risposta e' del tuo client)
                src_o = (msg["optionalActionMessage"] or {}).get("sourceId")
                richieste.setdefault(sid_q, {})["opz"] = dict(chi=chi_q, g=MA.grp_vero(ogg(src_o), tutti) if src_o and ogg(src_o).get("grpId") else 0)
                continue
            if msg.get("castingTimeOptionsReq"):   # le opzioni del lancio (kicker, X, costi alternativi)
                op_ = [o_.get("castingTimeOptionType", "").replace("CastingTimeOptionType_", "") for o_ in
                       msg["castingTimeOptionsReq"].get("castingTimeOptionReq") or []]
                op_ = [o_ for o_ in op_ if o_ and o_ != "Done"]
                if op_:
                    richieste.setdefault(sid_q, {})["op"] = dict(chi=chi_q, o=op_)
                continue
            if msg.get("selectNReq") and "Stacking" not in str(msg["selectNReq"].get("optionContext")):       # «scegli N»
                q_ = msg["selectNReq"]
                if q_.get("idType") == "IdType_InstanceId" and q_.get("ids"):
                    richieste.setdefault(sid_q, {})["sn"] = dict(chi=chi_q, ids=list(q_["ids"])[:12], mn=q_.get("minSel"), mx=q_.get("maxSel"),
                                                                 g=[MA.grp_vero(ogg(i_), tutti) if ogg(i_).get("grpId") else 0 for i_ in list(q_["ids"])[:12]])
                continue
            if msg.get("type") == "GREMessageType_ActionsAvailableReq":
                # le giocate che avevi (16 nov 2026, Autore: «nel log esistono ulteriori note che fino ad adesso non sono state considerate?»): a ogni
                # priorita' Arena ti manda le azioni legali, lanci, terre, abilita' non di mana; il passo le mostra accese sulle carte
                zona_di = {**{i_: "campo" for i_ in ids_di("ZoneType_Battlefield")}, **{i_: "esi" for i_ in ids_di("ZoneType_Exile")},
                           **{i_: "cim" for i_ in ids_di("ZoneType_Graveyard")}, **{i_: "mano" for i_ in ids_di("ZoneType_Hand")}}
                lst_ = []
                for a_ in (msg.get("actionsAvailableReq") or {}).get("actions") or []:
                    k_ = {"ActionType_Cast": "C", "ActionType_Play": "P", "ActionType_Activate": "A"}.get(a_.get("actionType"))
                    i_ = a_.get("instanceId")
                    # solo quello che puoi pagare (21 nov 2026, Autore: «quando gioco terre che hanno due mana differenti ... mi dice che posso giocare
                    # cose a un costo superiore»): Arena manda ogni lancio legale, anche quelli che le tue terre non pagano; pagabile = Arena ha la soluzione
                    # di pagamento automatica (autoTapSolution) o il costo non ha mana, come le «disponibili» di mana_aperto
                    if k_ in ("C", "A") and a_.get("manaCost") and not a_.get("autoTapSolution"):
                        continue
                    if k_ and i_ and zona_di.get(i_) and [i_, k_] not in [x_[:2] for x_ in lst_]:
                        lst_.append([i_, k_, zona_di[i_], MA.grp_vero(ogg(i_), tutti) or a_.get("grpId") or 0, a_.get("abilityGrpId") or 0,
                                     1 if "CardType_Instant" in (ogg(i_).get("cardTypes") or []) else 0])
                giocate[msg.get("gameStateId") or 0] = dict(chi=(msg.get("systemSeatIds") or [None])[0], a=lst_)
                continue
            gq = msg.get("groupReq") or {}
            if gq.get("context") == "GroupingContext_Surveil" and gq.get("instanceIds"):     # il tuo surveil: le carte guardate (il censimento)
                sorv = dict(ids=list(gq["instanceIds"]), chi=(msg.get("systemSeatIds") or [None])[0], s=msg.get("gameStateId") or 0,
                            g=[MA.grp_vero(ogg(i_), tutti) if ogg(i_).get("grpId") else 0 for i_ in gq["instanceIds"]])
                for v_s in sorv_suo.values():            # chi ha la richiesta e' il tuo surveil: lo racconta sorv
                    if v_s["chi"] == sorv["chi"]:
                        v_s["mio"] = True
            gs = msg.get("gameStateMessage")
            if not gs:
                continue
            sid = gs.get("gameStateId") or 0
            if gs.get("update") == "GameStateUpdate_Undo" and gs.get("prevGameStateId"):     # l'annullamento: via le azioni da quello stato in poi
                frames = [f for f in frames if f["_s"] < gs["prevGameStateId"]]
                # e la pila di prima di quello stato (16 nov 2026, il giro: Jace che si risolve, Arena annulla e riscrive la stessa risoluzione; senza,
                # l'uscita dalla pila non si vedeva piu' e l'abilita' spariva dentro il turno dopo)
                prima_p = [k_ for k_ in pila_storia if k_ < gs["prevGameStateId"]]
                pila_msg = list(pila_storia[max(prima_p)]) if prima_p else []
                att_prima = None
            if gs.get("type") == "GameStateType_Full":
                obj, zone, zown, zids = {}, {}, {}, {}
            for z in gs.get("zones") or []:
                zone[z.get("zoneId")] = z.get("type")
                zown[z.get("zoneId")] = z.get("ownerSeatId")
                zids[z.get("zoneId")] = z.get("objectInstanceIds") or []
            MA.vite_da(gs, vite)
            MA.persistenti_da(gs, pers)
            for pl in gs.get("players") or []:
                if pl.get("systemSeatNumber") in (1, 2):
                    if pl.get("mulliganCount"):     # i mulligan esatti di tutti e due (16 nov 2026)
                        mulligan[pl["systemSeatNumber"]] = max(mulligan.get(pl["systemSeatNumber"], 0), pl["mulliganCount"])
                    veleno[pl["systemSeatNumber"]] = pl.get("poisonCounters", 0)
                    riserva[pl["systemSeatNumber"]] = [COLORI_RISERVA.get(m_.get("color"), "C") for m_ in pl.get("manaPool") or [] for _q in range(m_.get("count", 1) or 1)]
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
            for a in gs.get("persistentAnnotations") or []:        # quale effetto cambia forza e costituzione di chi (per sapere chi torna come prima)
                ty_e = a.get("type") or []
                if ("AnnotationType_ModifiedPower" in ty_e or "AnnotationType_ModifiedToughness" in ty_e) and _dettaglio(a, "effect_id"):
                    effetti_pt[_dettaglio(a, "effect_id")] = list(a.get("affectedIds") or [])
            for a in gs.get("annotations") or []:       # la fine di un potenziamento (16 nov 2026): l'effetto finisce, la carta torna come prima
                if frames and "AnnotationType_LayeredEffectDestroyed" in (a.get("type") or []):
                    for e_ in a.get("affectedIds") or []:
                        for x_ in effetti_pt.pop(e_, []):
                            if x_ in ids_di("ZoneType_Battlefield"):
                                pf_ = frames[-1]["foto"].setdefault("pf", [])
                                if x_ not in pf_:
                                    pf_.append(x_)
            for a in (gs.get("annotations") or []) + (gs.get("persistentAnnotations") or []):        # il danno previsto e gli avvisi di Arena (16 nov 2026)
                if frames and "AnnotationType_PredictedDirectDamage" in (a.get("type") or []) and a.get("affectorId"):
                    frames[-1]["foto"].setdefault("pdd", {})[str(a["affectorId"])] = [MA.grp_vero(ogg(a["affectorId"]), tutti) or 0, _dettaglio(a, "value") or 0]
                if frames and "AnnotationType_ShouldntPlay" in (a.get("type") or []):
                    rg_ = next((d_.get("valueString") or [""] for d_ in a.get("details") or [] if d_.get("key") == "Reason"), [""])[0]
                    for x_ in a.get("affectedIds") or []:
                        sp_ = frames[-1]["foto"].setdefault("sp", [])
                        if [x_, rg_] not in [e_[:2] for e_ in sp_] and len(sp_) < 4:
                            sp_.append([x_, rg_, MA.grp_vero(ogg(x_), tutti) or 0])
            # i bersagli scelti dopo il lancio (14 nov 2026, Autore: «pila erode - freccia su creatura oppo - creatura oppo nel cimitero - erode nel
            # cimitero»): Arena scrive TargetSpec in un messaggio a parte, dopo la magia in pila (o l'abilita'), e la freccia compariva solo con la risoluzione
            # (Erode) o mai (l'abilita' di Seam Rip). Si attaccano al passo della magia in pila, cosi' la freccia si vede prima che il bersaglio sparisca
            ult_ = frames[-1] if frames else None
            if ult_ and ult_.get("_cima") in bersagli and (ult_.get("rel") or {}).get("k") == "spell" and not ult_["rel"]["bers"]:
                ult_["rel"]["bers"] = list(bersagli[ult_["_cima"]])
                ult_["rel"]["fuori"] = MA.fuori_campo(bersagli[ult_["_cima"]], zone, zids, zown, tutti)
            pila_ora = ids_di("ZoneType_Stack")
            campo_ora = set(ids_di("ZoneType_Battlefield"))
            finite = set()
            for a in gs.get("annotations") or []:
                if "AnnotationType_ResolutionStart" in (a.get("type") or []):
                    risolve.add(a.get("affectorId"))
                elif "AnnotationType_ResolutionComplete" in (a.get("type") or []):
                    finite.add(a.get("affectorId"))
            for a in gs.get("annotations") or []:
                if "AnnotationType_ZoneTransfer" in (a.get("type") or []) and a.get("affectorId") in in_pila                         and (a["affectorId"] in risolve or a["affectorId"] not in pila_ora)                         and zone.get(_dettaglio(a, "zone_src")) == "ZoneType_Battlefield":       # alla risoluzione: un sacrificio come costo no
                    in_pila[a["affectorId"]]["fatti"].update(origine.get(x, x) for x in a.get("affectedIds") or [])
            risolve -= finite
            for x in [x for x in in_pila if x not in pila_ora]:        # ha lasciato la pila: cosa manca dal campo di quando ci e' entrata
                p_ = in_pila.pop(x)
                for rel_ in p_["rels"]:
                    rel_["colpiti"] = sorted(y for y in p_["prima"] if y not in campo_ora)
                    rel_["fatti"] = sorted(y for y in p_["fatti"] if y in p_["prima"])
            for x in pila_ora:
                if x not in in_pila:
                    in_pila[x] = dict(prima=set(campo_ora), fatti=set(), rels=[])
            ev, danni = [], []
            sv_ora = None
            if sorv and sid > sorv["s"]:       # il surveil risolto: le guardate che non vanno al cimitero restano sopra
                via_ = {origine.get(x_, x_) for a in gs.get("annotations") or [] if "AnnotationType_ZoneTransfer" in (a.get("type") or [])
                        and _dettaglio(a, "category") == "Surveil" for x_ in a.get("affectedIds") or []}
                via_ |= {x_ for a in gs.get("annotations") or [] if "AnnotationType_ZoneTransfer" in (a.get("type") or [])
                         and _dettaglio(a, "category") == "Surveil" for x_ in a.get("affectedIds") or []}
                sv_ora = [[g_, sorv["chi"], 0 if i_ in via_ else 1, 1] for i_, g_ in zip(sorv["ids"], sorv["g"])]
                sorv = None
            # il surveil dell'avversario (15 nov 2026, Autore: «ho guardato il replay di una creatura che fa surveil ma nessun'animazione si e'
            # palesata»): Arena non gli manda la richiesta con le carte, ma segna l'effetto (MultistepEffectStarted/Complete, SubCategory 11) e sposta
            # al cimitero le carte che non tiene (ZoneTransfer «Surveil»). Quante ne guarda lo dice il testo dell'abilita' («surveil 2»); quelle tenute
            # sopra restano coperte
            for a in gs.get("annotations") or []:
                tp_ = a.get("type") or []
                if ("AnnotationType_MultistepEffectStarted" in tp_ or "AnnotationType_MultistepEffectComplete" in tp_) and _dettaglio(a, "SubCategory") == 11:
                    aff_ = a.get("affectorId")
                    if "AnnotationType_MultistepEffectStarted" in tp_:
                        t_ab = TA.abilita(ogg(aff_).get("grpId")) if ogg(aff_).get("grpId") else None
                        m_n = re.search(r"[Ss]urveil (\d+)", t_ab or "")
                        sorv_suo[aff_] = dict(chi=(a.get("affectedIds") or [None])[0], n=int(m_n.group(1)) if m_n else 1, via=[],
                                              mio=bool(sorv and sorv["chi"] == (a.get("affectedIds") or [None])[0]))
                elif "AnnotationType_ZoneTransfer" in tp_ and _dettaglio(a, "category") == "Surveil":
                    for v_s in sorv_suo.values():
                        v_s["via"].extend(x_ for x_ in a.get("affectedIds") or [] if x_ not in v_s["via"])
            for a in gs.get("annotations") or []:
                if "AnnotationType_MultistepEffectComplete" in (a.get("type") or []) and _dettaglio(a, "SubCategory") == 11 and a.get("affectorId") in sorv_suo:
                    v_s = sorv_suo.pop(a["affectorId"])
                    if v_s["mio"] or v_s["chi"] not in (1, 2) or sv_ora:
                        continue
                    giu_ = [[MA.grp_vero(ogg(x_), tutti) if ogg(x_).get("grpId") else 0, v_s["chi"], 0, 1] for x_ in v_s["via"]]
                    sv_ora = [[0, v_s["chi"], 1, 1] for _ in range(max(0, v_s["n"] - len(giu_)))] + giu_
            colpiti_vita, perdite = set(), []          # chi ha preso danno; le vite perse senza danno (Perforating Artist: «perde 3 vite a meno che…»)
            effetti_abilita = []                       # (abilita', bersagli): un'abilita' che fa effetto adesso, senza essere mai stata in pila in un passo
            rivelate, mescola, potenzia = [], [], []
            da_zona_ab = []                 # [grpId, proprietario] delle carte rivelate; i giocatori che rimescolano il grimorio (il censimento)
            anns_msg = gs.get("annotations") or []
            guardate = []                              # lo scry: [grpId o 0 se non si vede, chi, 1 sopra / 0 sotto], nell'ordine in cui restano
            if sv_ora:                                 # il surveil: [grpId, chi, 1 sopra / 0 al cimitero, 1]
                guardate = sv_ora
                k_su = sum(1 for e_ in sv_ora if e_[2])
                ev.append((sv_ora[0][1], f"surveilled {len(sv_ora)}: {k_su} on top, {len(sv_ora) - k_su} into the graveyard"))
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
                        if not verbo and cat == "nil" and zone.get(_dettaglio(a, "zone_src")) == "ZoneType_Stack" \
                                and zone.get(_dettaglio(a, "zone_dest")) in ("ZoneType_Graveyard", "ZoneType_Exile"):
                            # la magia che lascia la pila senza risolversi perche' non ha piu' un bersaglio legale (608.2b; 16 nov 2026, Autore: «errori
                            # di cose messe nella sbagliata sequenza soprattutto in pila»: Ethereal Armor col bersaglio morto finiva nel passo dell'attacco)
                            ev.append((chi_(x), f"{n_(x)} had no legal target"))
                            continue
                        if not verbo:
                            continue
                        if cat == "Draw":       # di chi e' la mano dove arriva (la sua pescata non si vede: «a card»)
                            dest = _dettaglio(a, "zone_dest")
                            ev.append((zown.get(dest) or chi_(x), "drew " + (n_(x) if ogg(x).get("grpId") else "a card")))
                        else:
                            if cat == "Separate":       # le carte divise in mucchi (Bilbo's Gambit): dove va il mucchio lo dice la zona d'arrivo (15 nov 2026)
                                verbo = {"ZoneType_Hand": "put into hand from a pile", "ZoneType_Graveyard": "put into the graveyard from a pile"}.get(
                                    zone.get(_dettaglio(a, "zone_dest")), verbo)
                            if cat in ("Return", "Put", "Bounce"):     # dove va lo dice la zona d'arrivo (Teacher's Pest torna dal cimitero in campo, non in mano)
                                verbo = {"ZoneType_Hand": "returned to hand", "ZoneType_Battlefield": "returned to the battlefield" if cat == "Return"
                                         else "put onto the battlefield", "ZoneType_Library": "put into the library", "ZoneType_Graveyard": "put into the graveyard",
                                         "ZoneType_Exile": "exiled"}.get(zone.get(_dettaglio(a, "zone_dest")), verbo)
                            chi_x = chi_(x)
                            dz_ = _dettaglio(a, "zone_dest")
                            if zone.get(dz_) == "ZoneType_Library" and x in (zids.get(dz_) or []):
                                # dove finisce nel grimorio (15 nov 2026, i gruppi del censimento: «sopra o sotto non si distingue»): Arena non lo scrive
                                # nell'annotazione, ma la lista del grimorio va dalla cima al fondo; il proprietario del grimorio e' chi lo dice
                                ids_d = zids[dz_]
                                k_d = ids_d.index(x)
                                verbo = ("put on top of the library" if k_d == 0 else "put on the bottom of the library" if k_d == len(ids_d) - 1
                                         else f"put into the library, {k_d + 1}{'nd' if k_d == 1 else 'rd' if k_d == 2 else 'th'} from the top")
                                chi_x = zown.get(dz_) or chi_x
                            # la terra giocata o la magia lanciata dalla cima del grimorio lo dice (16 nov 2026: «Opponent played Forest» volava dal grimorio
                            # e sembrava un errore)
                            dal_g = " from the top of the library" if cat in ("PlayLand", "CastSpell") and zone.get(_dettaglio(a, "zone_src")) == "ZoneType_Library" else ""
                            ev.append((chi_x, f"{verbo} {n_(x)}{dal_g}" if cat in ("PlayLand", "CastSpell", "Discard", "Sacrifice") else f"{n_(x)} {verbo}"))
                elif "AnnotationType_DamageDealt" in tipi:
                    q = _dettaglio(a, "damage") or 0
                    for x in aff:
                        bers = f"{{P{x}}}" if x in (1, 2) else n_(x)
                        src = a.get("affectorId")
                        ev.append((chi_(src), f"{n_(src)} dealt {q} to {bers}"))
                        danni.append((x, q, src))
                        if x in (1, 2):
                            colpiti_vita.add(x)
                elif "AnnotationType_ModifiedLife" in tipi:
                    q = _dettaglio(a, "life") or 0
                    for x in aff:
                        ev.append((x, f"{'gained' if q > 0 else 'lost'} {abs(q)} life"))
                        if q < 0:
                            perdite.append((x, -q, a.get("affectorId")))
                    o_ab = ogg(a.get("affectorId")) if a.get("affectorId") else {}
                    if o_ab.get("type") == "GameObjectType_Ability":
                        effetti_abilita.append((a["affectorId"], [x for x in aff if x in (1, 2)]))
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
                    for ids_s, su in ((sopra, 1), (sotto, 0)):
                        for i_s in ids_s:
                            o_s = ogg(i_s)
                            guardate.append([MA.grp_vero(o_s, tutti) if o_s.get("grpId") else 0, chi_s, su])
                elif "AnnotationType_ChoiceResult" in tipi:      # la scelta fatta (il censimento): il tipo, il colore, il nome, la modalita'
                    tx_ch = TA.scelta(_dettaglio(a, "Choice_Domain"), _dettaglio(a, "Choice_Value"))
                    o_ch = ogg(a.get("affectorId"))
                    carta_ch = o_ch.get("parentId") if o_ch.get("type") == "GameObjectType_Ability" and o_ch.get("parentId") else a.get("affectorId")
                    if tx_ch:
                        ev.append((chi_(carta_ch), f"chose {tx_ch} ({n_(carta_ch)})"))
                        scelte_carte[carta_ch] = tx_ch
                elif "AnnotationType_RevealedCardCreated" in tipi:      # (14 nov 2026, il censimento: 961 volte nei log, mai viste nel replayer)
                    for x in aff:
                        o_r = ogg(x)
                        if o_r.get("grpId") and o_r.get("ownerSeatId") in (1, 2):
                            ev.append((o_r["ownerSeatId"], f"revealed {n_(x)}"))
                            rivelate.append([MA.grp_vero(o_r, tutti), o_r["ownerSeatId"]])
                elif "AnnotationType_CardRevealed" in tipi:      # la carta mostrata senza la copia rivelata (15 nov 2026): la stessa animazione, una volta
                    for x in aff:
                        o_r = ogg(x)
                        if o_r.get("grpId") and o_r.get("ownerSeatId") in (1, 2) and [MA.grp_vero(o_r, tutti), o_r["ownerSeatId"]] not in rivelate                                 and not any("AnnotationType_RevealedCardCreated" in (a2.get("type") or []) for a2 in anns_msg):
                            ev.append((o_r["ownerSeatId"], f"revealed {n_(x)}"))
                            rivelate.append([MA.grp_vero(o_r, tutti), o_r["ownerSeatId"]])
                elif "AnnotationType_Shuffle" in tipi:
                    for x in aff:
                        if x in (1, 2) and x not in mescola:
                            ev.append((x, "shuffled their library"))
                            mescola.append(x)
                elif "AnnotationType_ControllerChanged" in tipi:
                    for x in aff:
                        ev.append((chi_(x), f"gained control of {n_(x)}"))
                elif "AnnotationType_AttachmentCreated" in tipi:
                    for x in aff:
                        ev.append((chi_(a.get("affectorId")), f"{n_(a.get('affectorId'))} attached to {n_(x)}"))
                elif "AnnotationType_PowerToughnessModCreated" in tipi:
                    p_, t_ = _dettaglio(a, "power") or 0, _dettaglio(a, "toughness") or 0
                    for x in aff:
                        if x not in con_segnalino:
                            ev.append((chi_(x), f"{n_(x)} got {p_:+d}/{t_:+d}"))
                            potenzia.append([x, p_, t_])        # l'impulso sulla carta (16 nov 2026)
                elif "AnnotationType_AbilityInstanceCreated" in tipi:        # solo le abilita' che vanno in pila (non quelle di mana)
                    pila_ora = set(ids_di("ZoneType_Stack"))
                    src_pw = ogg(a.get("affectorId"))
                    zs_ = zone.get(_dettaglio(a, "source_zone"))       # l'innesco partito dal cimitero, dall'esilio o dalla mano (16 nov 2026)
                    if zs_ in ("ZoneType_Graveyard", "ZoneType_Exile", "ZoneType_Hand") and any(x in pila_ora for x in aff):
                        da_zona_ab.append([MA.grp_vero(src_pw, tutti) or 0, {"ZoneType_Graveyard": "graveyard", "ZoneType_Exile": "exile",
                                                                             "ZoneType_Hand": "hand"}[zs_]])
                    if "CardType_Planeswalker" in (src_pw.get("cardTypes") or []) and any(x in pila_ora for x in aff):
                        pw_usati.add((t, a.get("affectorId")))      # il potere del planeswalker usato in questo turno (16 nov 2026)
                    for x in aff:
                        if x in pila_ora:
                            ev.append((chi_(x) or chi_(a.get("affectorId")), f"ability of {n_(a.get('affectorId'))} on the stack"))
                            annunciate.add(x)
            # gli inneschi che scattano insieme (15 nov 2026, il verificatore della pila: 88 abilita' su 1.145 oggetti in 40 partite mai mostrate in pila;
            # Unholy Annex, Unstoppable Slasher, Haliya...): Arena li crea nella zona Pending e li mette in pila nel messaggio dopo, senza annotazioni, e
            # il replayer non ne faceva un passo; ora ogni abilita' che arriva in pila senza essere stata raccontata e' un'azione sua, prima di risolversi
            # e lo stesso per le magie che entrano in pila senza essere lanciate dal giocatore: la copia di una magia (ZoneTransfer «Copy», 15 nov 2026)
            lanciate_ = {x for a in anns_msg if "AnnotationType_ZoneTransfer" in (a.get("type") or []) and _dettaglio(a, "category") == "CastSpell"
                         for x in a.get("affectedIds") or []}
            for x in ids_di("ZoneType_Stack"):
                o_x = obj.get(x) or {}
                if x in annunciate or x in lanciate_:
                    annunciate.add(x)
                    continue
                annunciate.add(x)
                chi_s = o_x.get("controllerSeatId") if o_x.get("controllerSeatId") in (1, 2) else None
                if o_x.get("type") == "GameObjectType_Ability":
                    fonte_x = o_x.get("parentId") or o_x.get("objectSourceId")
                    n_x = n_(fonte_x) if fonte_x and ogg(fonte_x) else (nome(o_x.get("objectSourceGrpId")) or "a card")
                    ev.append((chi_s, f"ability of {n_x} on the stack"))
                elif o_x:
                    ev.append((chi_s, f"{'a copy of ' if o_x.get('isCopy') else ''}{n_(x)} on the stack"))
            # il pagamento arriva nel messaggio dopo il lancio (14 nov 2026, Autore: «vedo che scende prima la creatura e poi il mana per pagarla, dovrebbe
            # essere l'inverso»): Arena scrive prima la magia che va in pila, poi ManaPaid con le terre tappate. Se questo messaggio non e' un'azione nuova,
            # la foto del lancio (l'ultimo passo, con la magia ancora in pila) si rifa' col pagamento
            # chi lascia la pila in questo messaggio (16 nov 2026, Autore: «errori di cose messe nella sbagliata sequenza soprattutto in pila»): un
            # innesco che si risolve senza un effetto da raccontare (il «puoi» rifiutato di Strongbox Raider, Slumbering Cerberus a fine turno) spariva
            # dentro l'azione dopo (il turno nuovo, un blocco, un'altra magia); ora, se il messaggio non ha altre azioni, la sua risoluzione e' un passo
            pila_adesso = ids_di("ZoneType_Stack")
            usciti_sil = [x for x in pila_msg if x not in pila_adesso]
            pila_msg = list(pila_adesso)
            pila_storia[sid] = list(pila_adesso)
            n_fr = len(frames)
            # la magia preparata (Seed Suture e le altre di SOS; 15 nov 2026, la caccia ai glitch): una copia lanciata dalla creatura, che nello stesso
            # messaggio perde PREPARED (LoseDesignation 24); vola da lei alla pila, non dalla mano
            for a in anns_msg:
                if "AnnotationType_ZoneTransfer" in (a.get("type") or []) and _dettaglio(a, "category") == "CastSpell":
                    z_src = _dettaglio(a, "zone_src")
                    zona_ = {"ZoneType_Graveyard": "cim", "ZoneType_Exile": "esi", "ZoneType_Library": "lib"}.get(zone.get(z_src))
                    for x in a.get("affectedIds") or []:
                        # lanciata dal cimitero, dall'esilio, dal grimorio: vola da li'; anche la copia del Paradigm dall'esilio (Improvisation Capstone, 16
                        # nov 2026); la magia preparata vola dalla sua creatura (vince «pd», nel replayer)
                        if zona_:
                            da_zona[x] = [zona_, zown.get(z_src)]
                        if (obj.get(x) or {}).get("isCopy"):
                            src_p = next((a2.get("affectorId") for a2 in anns_msg if "AnnotationType_LoseDesignation" in (a2.get("type") or [])
                                          and _dettaglio(a2, "DesignationType") == 24 and a2.get("affectorId")), None)
                            if src_p:
                                da_preparata[x] = src_p
            # il pagamento a mano, una terra alla volta (15 nov 2026, il verificatore del mana: Winter, Team Player pagata con cinque terre in cinque
            # messaggi): i messaggi dopo aggiungono le loro fonti al passo di pagamento gia' aperto per la stessa magia, invece di farne altri
            pagati_ora = [x for a in anns_msg if "AnnotationType_ManaPaid" in (a.get("type") or []) for x in a.get("affectedIds") or []]
            continua_pag = False
            pagati_qui.clear()
            if pagati_ora and not ev and not danni and frames and len(set(pagati_ora)) == 1:
                pf_ = next((f_ for f_ in reversed(frames[-2:]) if f_.get("_pag") == pagati_ora[0] and f_["foto"].get("mn") is not None), None)
                # solo nei messaggi di fila: un pagamento piu' tardi della stessa magia (il ward pagato quando scatta) e' un passo suo
                if pf_ is not None and sid - pf_.get("_pag_s", -9) <= 1:
                    pf_["_pag_s"] = sid
                    nuove_f = fonti_di(gs, pagati_ora[0])
                    pf_["foto"]["mn"] += [[i_, col_] for i_, cols_ in nuove_f.items() for col_ in cols_]
                    for f_ in frames[frames.index(pf_):]:
                        for lato in f_["foto"]["c"]:
                            for c_ in lato:
                                if len(c_) > 5 and c_[5] in nuove_f:
                                    c_[1] = 1
                    continua_pag = True
            # il pagamento fatto mentre un innesco si risolve e crea un'abilita' nuova (16 nov 2026, Spellbook Vendor: «puoi pagare {1}», poi l'abilita'
            # riflessa): e' il passo della nuova abilita' a riceverlo (il ciclo in fondo), non l'innesco che era gia' in pila: si contava due volte
            _tipi = lambda a_: a_.get("type") or []
            _creati = {x for a in anns_msg if "AnnotationType_AbilityInstanceCreated" in _tipi(a) for x in a.get("affectedIds") or []}
            _cancellati = {x for a in anns_msg if "AnnotationType_AbilityInstanceDeleted" in _tipi(a) for x in a.get("affectedIds") or []}
            paga_dopo = bool(_creati - _cancellati) and any("AnnotationType_ResolutionComplete" in _tipi(a) for a in anns_msg)
            if continua_pag or paga_dopo:
                pass
            elif not ev and not danni and frames and frames[-1]["t"] == t and frames[-1].get("_cima") in ids_di("ZoneType_Stack") \
                    and any("AnnotationType_ManaPaid" in (a.get("type") or []) for a in gs.get("annotations") or []):
                f_n = foto()
                f_n.update({k_: frames[-1]["foto"][k_] for k_ in ("r", "s", "sc") if k_ in frames[-1]["foto"]})
                frames[-1]["foto"] = f_n
                paga(fonti_di(gs, frames[-1]["_cima"]))
            elif frames and frames[-1]["t"] == t and frames[-1].get("_cima") is not None:
                # il pagamento arrivato insieme alla risoluzione (un istantaneo senza risposte): le fonti di mana di quella magia (affectorId di ManaPaid)
                # si tappano nella foto del lancio
                fonti = fonti_di(gs, frames[-1]["_cima"])
                if fonti:
                    for lato in frames[-1]["foto"]["c"]:
                        for c_ in lato:
                            if len(c_) > 5 and c_[5] in fonti:
                                c_[1] = 1
                    paga(fonti)
            # il pagamento da solo (15 nov 2026, il verificatore del mana): il costo del ward pagato mentre si risolve il suo innesco, il «puoi pagare»
            # di un innesco, la porta della Room che si apre pagando; il messaggio non ha altre azioni e il replayer non ne faceva un passo
            pagati_msg = [x for a in anns_msg if "AnnotationType_ManaPaid" in (a.get("type") or []) for x in a.get("affectedIds") or []]
            solo_pag = None
            if pagati_msg and not ev and not danni and len(frames) == n_fr and not continua_pag:
                solo_pag = pagati_msg[0]
                fonti_s = fonti_di(gs, solo_pag)
                ev.append((chi_(next(iter(fonti_s), None)) or chi_(solo_pag), f"paid mana for {n_(solo_pag)}"))
            # il combattimento: attaccanti e blocchi dichiarati (chi e' in campo lo dicono le zone)
            sul = [obj[i] for i in ids_di("ZoneType_Battlefield") if i in obj]
            att_ids = [[o["instanceId"], (o.get("attackInfo") or {}).get("targetId")] for o in sul
                       if o.get("attackState") in ("AttackState_Declared", "AttackState_Attacking")]
            # un blocco conta quando Arena lo conferma (15 nov 2026, il verificatore del combattimento: 9 blocchi su 1.329 combattimenti mostrati e mai fatti):
            # mentre chi difende sceglie, la scelta e' BlockState_Declared e puo' essere tolta nel messaggio dopo (Surveillance Phantasm messo e tolto)
            blocchi = [[o["instanceId"], (o.get("blockInfo") or {}).get("attackerIds") or []] for o in sul if (o.get("blockInfo") or {}).get("attackerIds")
                       and o.get("blockState") != "BlockState_Declared"]
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
            elif not att_ids and not ev and not usciti_sil:
                att_prima = None        # finito il combattimento: le stesse creature che riattaccano al turno dopo sono un attacco nuovo
                continue
            if not att_ids:
                att_prima = None
            if usciti_sil and not ev and not danni:
                for x in usciti_sil:
                    o_x = ogg(x)
                    if o_x.get("type") == "GameObjectType_Ability":
                        fonte_x = o_x.get("parentId") or o_x.get("objectSourceId")
                        n_x = n_(fonte_x) if fonte_x and ogg(fonte_x) else (nome(o_x.get("objectSourceGrpId")) or "a card")
                        ev.append((o_x.get("controllerSeatId") if o_x.get("controllerSeatId") in (1, 2) else None, f"ability of {n_x} resolved"))
                    elif o_x:
                        ev.append((chi_(x), f"{n_(x)} left the stack"))
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
                if scattata_da(cima, o):
                    rel["da"] = scattata_da(cima, o)
                if cima in in_pila:
                    in_pila[cima]["rels"].append(rel)
            for x, q, src in perdite:
                if x not in colpiti_vita:
                    danni.append((x, q, src))
            passo = (ti.get("step") or ti.get("phase") or "").replace("Step_", "").replace("Phase_", "")
            if effetti_abilita and not (rel and rel.get("k") == "spell"):
                # (14 nov 2026, Autore: «esistono carte in campo che richiedono il compimento di azioni come Perforating Artist ma nel replayer non si vede
                # cosa accade»): l'abilita' va in pila e si risolve nello stesso messaggio; prima del suo effetto un passo con lei in pila e la freccia
                ab_id, bers_ab = effetti_abilita[0]
                o_ab = ogg(ab_id)
                f_ab = copy.deepcopy(frames[-1]["foto"]) if frames else foto()
                f_ab.pop("r", None), f_ab.pop("s", None), f_ab.pop("sc", None), f_ab.pop("mn", None)
                f_ab["p"] = [[MA.grp_vero(o_ab, tutti), o_ab.get("controllerSeatId"), 1, ab_id]]
                frames.append(dict(t=t, step=passo, att=att, foto=f_ab, ev=[(o_ab.get("controllerSeatId"), f"Ability of {n_(ab_id)} on the stack")],
                                   danni=[], rel=dict(k="spell", g=MA.grp_vero(o_ab, tutti), chi=o_ab.get("controllerSeatId"), ab=True, bers=list(bers_ab),
                                                      colpiti=[], fuori=[], fatti=[], **({"da": scattata_da(ab_id, o_ab)} if scattata_da(ab_id, o_ab) else {})),
                                   _s=sid, _att=False, _cima=None))
            if solo_att and frames and frames[-1].get("_att") and frames[-1]["t"] == t and frames[-1]["step"] == passo:     # attaccanti scelti uno alla volta: resta l'ultima scelta
                frames.pop()
            frames.append(dict(t=t, step=(ti.get("step") or ti.get("phase") or "").replace("Step_", "").replace("Phase_", ""), att=att, foto=foto(), ev=ev,
                               danni=danni, rel=rel, _s=sid, _att=solo_att, _cima=pila[0] if pila else None))       # anche in combattimento (un istantaneo prima del danno)
            annunciate.update(pila)         # quello che un passo mostra in pila e' raccontato
            if rivelate:
                frames[-1]["foto"]["r"] = rivelate
            if mescola:
                frames[-1]["foto"]["s"] = mescola
            if potenzia:
                frames[-1]["foto"]["pt"] = potenzia
            if da_zona_ab:
                frames[-1]["foto"]["trz"] = da_zona_ab
            if guardate:
                frames[-1]["foto"]["sc"] = guardate
            # pagata nello stesso messaggio del lancio (15 nov 2026, il verificatore del mana: anche quando un innesco le va subito sopra, e le abilita'
            # attivate col mana, e la porta della Room pagata in campo): ogni oggetto che questo messaggio paga, non solo la cima della pila
            if solo_pag is not None:        # il passo e' il pagamento stesso: le fonti appena tappate, il mana che vola
                frames[-1]["foto"]["mn"] = [[i_, col_] for i_, cols_ in fonti_di(gs, solo_pag).items() for col_ in cols_]
                if dest_mana(solo_pag) is not None:
                    frames[-1]["foto"]["mnd"] = dest_mana(solo_pag)
                frames[-1]["_pagato"], frames[-1]["_pag"], frames[-1]["_pag_s"] = True, solo_pag, sid
            # prima cio' che sta in pila: il pagamento di un'abilita' di mana (Three Tree City pagata per dare tre mana a Traveling Chocobo) viene dopo
            pila_m = set(ids_di("ZoneType_Stack"))
            for x in ([] if solo_pag is not None else sorted((x_ for x_ in dict.fromkeys(pagati_msg) if x_ not in pagati_qui), key=lambda x_: x_ not in pila_m)):
                paga(fonti_di(gs, x), x)
                break
            # un attaccante che qui risulta tappato e nel passo dell'attacco no: Arena ha scritto la tappatura in un messaggio dopo; era gia' tappato quando
            # ha attaccato (14 nov 2026: nel replayer le creature si tappavano una alla volta nel passo dei bloccanti, ad attacco gia' fatto)
            nuovo_ = frames[-1]
            tappati_ = {cc[5] for lato in nuovo_["foto"]["c"] for cc in lato if len(cc) > 5 and cc[1]}
            if tappati_:
                for q_ in range(len(frames) - 2, -1, -1):
                    fq_ = frames[q_]
                    if fq_["t"] != nuovo_["t"]:
                        break
                    att_q = {a_ for a_, _tg in ((fq_.get("rel") or {}).get("att") or [])} if (fq_.get("rel") or {}).get("k") == "comb" else set()
                    da_tappare = att_q & tappati_
                    if not da_tappare:
                        continue
                    for f_ in frames[q_:len(frames) - 1]:
                        for lato in f_["foto"]["c"]:
                            for cc in lato:
                                if len(cc) > 5 and cc[5] in da_tappare:
                                    cc[1] = 1
                    break
    fine_campo = set(ids_di("ZoneType_Battlefield"))
    for p_ in in_pila.values():     # la partita finita con la magia ancora in pila (13 nov 2026: concessa subito dopo Settle the Wreckage)
        for rel_ in p_["rels"]:
            rel_["colpiti"] = sorted(y for y in p_["prima"] if y not in fine_campo)
            rel_["fatti"] = sorted(y for y in p_["fatti"] if y in p_["prima"])
    s_fr = [f["_s"] for f in frames]
    for k_, f in enumerate(frames):     # le giocate che avevi in questo passo: le richieste fra il suo stato e quello del passo dopo con uno stato piu' alto
        dopo_ = next((s_ for s_ in s_fr[k_ + 1:] if s_ > f["_s"]), None)
        if dopo_ is not None and any(s2 == f["_s"] for s2 in s_fr[k_ + 1:]):
            continue        # un altro passo dello stesso stato viene dopo: le prende lui
        gs_ = [s_ for s_ in giocate if s_ >= f["_s"] and (dopo_ is None or s_ < dopo_)]
        if gs_:
            g_ = giocate[max(gs_)]
            f["foto"]["gi"] = dict(chi=g_["chi"], a=g_["a"])
        for s_ in sorted(s_ for s_ in richieste if s_ >= f["_s"] and (dopo_ is None or s_ < dopo_)):
            f["foto"].update(richieste[s_])
    if frames and dado:
        frames[0]["foto"]["dado"] = {str(k_): v_ for k_, v_ in dado.items()}
    if frames:
        frames[0]["foto"]["mul"] = {str(k_): mulligan.get(k_, 0) for k_ in (1, 2)}
        if mull_scelte:
            frames[0]["foto"]["mdec"] = mull_scelte
        if parte_scelta:
            frames[0]["foto"]["parte"] = parte_scelta[-1]
    for f in ([] if interni else frames):      # interni: tiene il gameStateId e le altre chiavi di lavoro (Strumenti/verifica_pila.py)
        f.pop("_s", None)
        f.pop("_att", None)
        f.pop("_cima", None)
        f.pop("_pagato", None)
        f.pop("_pag", None)
        f.pop("_pag_s", None)
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
            ("la magia in pila col suo bersaglio (e il bersaglio morto, quando si risolve)",
             fr[2]["rel"] == dict(k="spell", g=200, chi=1, ab=False, bers=[9], colpiti=[9], fatti=[], fuori=[])),
            ("la foto dopo la terra ha la terra in campo con il suo id", fr[1]["foto"]["c"][0] == [[100, 0, 0, None, None, 3, None]]),
            ("i danni (con chi li infligge) e le vite dopo la risoluzione; la vita persa senza danno e' anche lei una goccia", [d_[:2] for d_ in fr[3]["danni"]] == [(9, 3), (2, 3)] and fr[3]["danni"][0][2] == 4 and fr[3]["foto"]["v"] == [20, 17] and fr[3]["foto"]["c"][1] == []),
            ("negativa: righe senza stato del gioco, nessuna foto", azioni(["niente", "{rotto"]) == [])]
    # il pagamento nel messaggio dopo il lancio (14 nov 2026): la foto del lancio ha la terra tappata; negativa: senza ManaPaid resta stappata
    paga = gs(type="GameStateType_Diff", gameObjects=[carta(3, 100, 28, 1, isTapped=True)],
              annotations=[dict(type=["AnnotationType_ManaPaid"], affectorId=3, affectedIds=[4]), dict(type=["AnnotationType_TappedUntappedPermanent"], affectedIds=[3])])
    tap_ = gs(type="GameStateType_Diff", gameObjects=[carta(3, 100, 28, 1, isTapped=True)])
    fp_ = azioni(righe[:4] + [paga] + righe[4:], nomi.get)
    fn_ = azioni(righe[:4] + [tap_] + righe[4:], nomi.get)
    casi.append(("prima il mana, poi la magia: un passo «paid mana for Shock» con la Mountain tappata e Shock ancora in mano, poi «cast Shock» (tappata)",
                 len(fp_) == 5 and [tx for _c, tx in fp_[2]["ev"]] == ["paid mana for Shock"] and fp_[2]["foto"]["c"][0][0][1] == 1
                 and 200 in fp_[2]["foto"]["m"][0] and [tx for _c, tx in fp_[3]["ev"]] == ["cast Shock"] and fp_[3]["foto"]["c"][0][0][1] == 1))
    casi.append(("negativa: un messaggio senza ManaPaid non cambia la foto del lancio e non fa il passo del pagamento", len(fn_) == 4 and fn_[2]["foto"]["c"][0][0][1] == 0))
    # le giocate offerte (21 nov 2026, Autore: le terre a due colori, «mi dice che posso giocare cose a un costo superiore»): Arena elenca anche i lanci
    # che le tue terre non pagano; resta solo chi ha la soluzione di pagamento (autoTapSolution) o un costo senza mana. Due carte in mano: 1 pagabile, 2 no
    def aar(acts):
        return "[UnityCrossThreadLogger]x " + json.dumps(dict(greToClientEvent=dict(greToClientMessages=[dict(
            type="GREMessageType_ActionsAvailableReq", systemSeatIds=[1], actionsAvailableReq=dict(actions=acts))])))
    mano2 = gs(type="GameStateType_Full", zones=[dict(zoneId=31, type="ZoneType_Hand", ownerSeatId=1, objectInstanceIds=[1, 2])],
               players=[dict(systemSeatNumber=1, lifeTotal=20), dict(systemSeatNumber=2, lifeTotal=20)], turnInfo=dict(turnNumber=3, activePlayer=1),
               gameObjects=[carta(1, 100, 31, 1), carta(2, 200, 31, 1)], annotations=[dict(type=["AnnotationType_NewTurnStarted"], affectedIds=[1])])
    costo = [dict(color=["ManaColor_Generic"], count=3)]
    fg_ = azioni([mano2, aar([dict(actionType="ActionType_Cast", instanceId=1, grpId=100, manaCost=costo, autoTapSolution=dict(autoTapActions=[])),
                              dict(actionType="ActionType_Cast", instanceId=2, grpId=200, manaCost=costo),
                              dict(actionType="ActionType_Pass")])], nomi.get)
    gi_ = [e_[0] for e_ in ((fg_[-1]["foto"].get("gi") or {}).get("a") or [])] if fg_ else None
    casi.append(("le giocate offerte: la carta pagabile c'e'; negativa: quella offerta senza soluzione di pagamento no (la terra doppia non da' due mana)",
                 gi_ == [1]))
    # il bersaglio scelto in un messaggio dopo il lancio (14 nov 2026: Erode, l'abilita' di Seam Rip): la freccia sta nel passo della magia in pila
    import json as _j
    lancio_ = _j.loads(righe[3].split(" ", 1)[1])
    gsm_ = lancio_["greToClientEvent"]["greToClientMessages"][0]["gameStateMessage"]
    pers_ = gsm_.pop("persistentAnnotations")
    senza_t = gs(**gsm_)
    poi_t = gs(type="GameStateType_Diff", persistentAnnotations=pers_)
    ft_ = azioni(righe[:3] + [senza_t, poi_t] + righe[4:], nomi.get)
    fz_ = azioni(righe[:3] + [senza_t] + righe[4:], nomi.get)
    casi.append(("il bersaglio scelto dopo il lancio va nel passo della magia in pila (la freccia prima della risoluzione); negativa: senza TargetSpec nessun "
                 "bersaglio", ft_[2]["rel"]["bers"] == [9] and fz_[2]["rel"]["bers"] == []))
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
    # gli inneschi che scattano insieme (15 nov 2026, il verificatore della pila): Arena li crea in Pending e li mette in pila nel messaggio dopo senza
    # annotazioni; ogni abilita' che arriva in pila senza essere raccontata e' un passo suo, e una copia di magia pure; negativa: la stessa pila gia' raccontata
    # non fa un passo nuovo
    abil = lambda i, src, **k: dict(instanceId=i, grpId=9001, type="GameObjectType_Ability", zoneId=27, controllerSeatId=1, ownerSeatId=1, parentId=src,
                                    objectSourceGrpId=100, **k)
    pend = base + [gz(50, type="GameStateType_Diff", zones=[campo(3)], gameObjects=[carta(3, 100, 28, 1)], annotations=[zt(3, "PlayLand")]),
                   gz(51, type="GameStateType_Diff", zones=[pila(9, 8)], gameObjects=[abil(8, 3), abil(9, 3)]),
                   gz(52, type="GameStateType_Diff", zones=[pila(9, 8)]),
                   gz(53, type="GameStateType_Diff", zones=[pila(10, 9, 8)], gameObjects=[carta(10, 200, 27, 1, isCopy=True, cardTypes=["CardType_Instant"])])]
    fr_p = azioni(pend, {100: "Island", 200: "Shock"}.get)
    in_p = [[e_[3] for e_ in f["foto"]["p"]] for f in fr_p if f["foto"].get("p")]
    casi.append(("gli inneschi messi in pila senza annotazioni hanno il loro passo, la copia pure; negativa: la stessa pila due volte, un passo solo",
                 in_p == [[9, 8], [10, 9, 8]] and any("a copy of Shock on the stack" in tx for f in fr_p for _c, tx in f["ev"])))
    # lui risponde alla tua magia e paga nel messaggio dopo: nel passo del suo pagamento la tua magia resta in pila (14 nov 2026, Autore: «se gioco
    # una carta e oppo si tappa per giocare la sua, la mia pila sparisce e riappare solo con la giocata di oppo»); negativa: senza magia sotto, niente pila
    pg_ = lambda *aff: [dict(type=["AnnotationType_ManaPaid"], affectorId=7, affectedIds=list(aff)), dict(type=["AnnotationType_TappedUntappedPermanent"], affectedIds=[7])]
    risp = base + [gz(40, type="GameStateType_Diff", zones=[pila(4), mano(1, 5)], gameObjects=[carta(4, 200, 27, 1, cardTypes=["CardType_Instant"])],
                      annotations=[zt(4, "CastSpell")]),
                   gz(41, type="GameStateType_Diff", zones=[pila(6, 4)], gameObjects=[carta(6, 300, 27, 2, cardTypes=["CardType_Instant"])],
                      annotations=[zt(6, "CastSpell")]),
                   gz(42, type="GameStateType_Diff", gameObjects=[carta(7, 100, 28, 2, isTapped=True)], annotations=pg_(6))]
    fr_r = azioni(risp, {100: "Island", 200: "Shock", 300: "Opt"}.get)
    pag_r = [f for f in fr_r if any("paid mana for Opt" in tx for _c, tx in f["ev"])]
    sola = base + [gz(39, type="GameStateType_Diff", zones=[campo(3), mano(2, 5)], gameObjects=[carta(3, 100, 28, 1)], annotations=[zt(3, "PlayLand")]),
                   gz(41, type="GameStateType_Diff", zones=[pila(6)], gameObjects=[carta(6, 300, 27, 2, cardTypes=["CardType_Instant"])],
                      annotations=[zt(6, "CastSpell")]),
                   gz(42, type="GameStateType_Diff", gameObjects=[carta(7, 100, 28, 2, isTapped=True)], annotations=pg_(6))]
    pag_s = [f for f in azioni(sola, {100: "Island", 300: "Opt"}.get) if any("paid mana for Opt" in tx for _c, tx in f["ev"])]
    casi.append(("lui paga per rispondere: nel passo del suo pagamento la tua magia resta in pila; negativa: senza magia sotto il pagamento non ha pila",
                 len(pag_r) == 1 and (pag_r[0]["rel"] or {}).get("g") == 200 and len(pag_s) == 1 and pag_s[0]["rel"] is None))
    # un'abilita' che va in pila e si risolve nello stesso messaggio (Perforating Artist: l'avversario perde 3 vite): prima un passo con lei in pila e la
    # freccia, poi la perdita come goccia (14 nov 2026); negativa: la perdita senza abilita' non fa il passo in piu'
    ml_ = lambda aff_: dict(type=["AnnotationType_ModifiedLife"], affectorId=aff_, affectedIds=[2], details=[dict(key="life", valueInt32=[-3])])
    abil = base + [gz(50, type="GameStateType_Diff", gameObjects=[carta(60, 700, 27, 1, tipo="GameObjectType_Ability")], annotations=[ml_(60)])]
    fa_ = azioni(abil, {700: "Perforating Artist"}.get)
    senza = base + [gz(50, type="GameStateType_Diff", annotations=[ml_(None)])]
    fs_ = azioni(senza, {700: "Perforating Artist"}.get)
    casi.append(("l'abilita' che si risolve subito: un passo con lei in pila (e il giocatore come bersaglio), poi la vita persa come goccia; negativa: "
                 "senza abilita' niente passo in piu'",
                 len(fa_) >= 2 and (fa_[-2]["rel"] or {}).get("ab") is True and (fa_[-2]["rel"] or {}).get("bers") == [2]
                 and [d_[:2] for d_ in fa_[-1]["danni"]] == [(2, 3)] and not any((f_["rel"] or {}).get("ab") for f_ in fs_)))
    # il censimento (14 nov 2026): la carta rivelata, il grimorio rimescolato e la carta che cambia controllore entrano nel passo; negativa: una
    # rivelata senza grpId (mai mandata) non c'e', e il passo dopo (il pagamento rifatto) non ripete rivelate e rimescolate
    riv_ = base + [gz(60, type="GameStateType_Diff", zones=[dict(zoneId=35, type="ZoneType_Revealed", ownerSeatId=2, objectInstanceIds=[61, 62])],
                      gameObjects=[carta(61, 400, 35, 2, tipo="GameObjectType_RevealedCard"), dict(instanceId=62, type="GameObjectType_RevealedCard",
                                                                                                  zoneId=35, ownerSeatId=2)],
                      annotations=[dict(type=["AnnotationType_RevealedCardCreated"], affectorId=61, affectedIds=[61, 62]),
                                   dict(type=["AnnotationType_Shuffle"], affectorId=9, affectedIds=[2], details=[])]),
                   gz(61, type="GameStateType_Diff", zones=[campo(3)], gameObjects=[carta(3, 100, 28, 2)],
                      annotations=[dict(type=["AnnotationType_ControllerChanged"], affectorId=9, affectedIds=[3])])]
    fv_ = azioni(riv_, {100: "Island", 400: "Forest"}.get)
    casi.append(("la carta rivelata, il grimorio rimescolato, il cambio di controllore; negativa: la rivelata senza grpId non c'e', il passo dopo non le ripete",
                 len(fv_) == 2 and fv_[0]["foto"].get("r") == [[400, 2]] and fv_[0]["foto"].get("s") == [2]
                 and [tx for _c, tx in fv_[0]["ev"]] == ["revealed Forest", "shuffled their library"]
                 and fv_[1]["ev"] == [(2, "gained control of Island")] and "r" not in fv_[1]["foto"] and "s" not in fv_[1]["foto"]))
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
    # il blocco scelto e tolto (15 nov 2026, il verificatore del combattimento): BlockState_Declared non e' un blocco; confermato (Blocking) si'
    scelto = lambda sid, st_: gz(sid, type="GameStateType_Diff", zones=[campo(9, 10, 14)], turnInfo=dict(t3, phase="Phase_Combat", step="Step_DeclareBlock"),
                                 gameObjects=[att_(9), att_(10), carta(14, 800, 28, 2, cardTypes=["CardType_Creature"], blockState=st_,
                                                                       blockInfo=dict(attackerIds=[9]))])
    fd = azioni(base + [uno(50, 9), uno(51, 9, 10), scelto(52, "BlockState_Declared")], {500: "Goblin", 800: "Wall"}.get)
    fc = azioni(base + [uno(50, 9), uno(51, 9, 10), scelto(52, "BlockState_Blocking")], {500: "Goblin", 800: "Wall"}.get)
    casi.append(("il blocco confermato si racconta; negativa: il blocco ancora in scelta (Declared) no",
                 any((2, "Wall blocked Goblin") in f["ev"] for f in fc) and not any((2, "Wall blocked Goblin") in f["ev"] for f in fd)))
    # il mana (15 nov 2026, il verificatore del mana): il pagamento da solo (la porta della Room pagata in campo, il ward) e' un passo suo col mana che vola
    # sul permanente; l'abilita' attivata col mana manda il mana sulla carta che la attiva; negativa: un messaggio senza ManaPaid non fa passi di mana
    mp_ = lambda fonte, x: dict(type=["AnnotationType_ManaPaid"], affectorId=fonte, affectedIds=[x], details=[dict(key="color", valueInt32=[3])])
    porta = base + [gz(60, type="GameStateType_Diff", zones=[campo(3, 21)], gameObjects=[carta(3, 100, 28, 1, isTapped=True), carta(21, 600, 28, 1)],
                       annotations=[mp_(3, 21)])]
    fp_ = [f for f in azioni(porta, {100: "Swamp", 600: "Unholy Annex"}.get, interni=True) if f["foto"].get("mn")]
    abil_ = dict(instanceId=22, grpId=9002, type="GameObjectType_Ability", zoneId=27, controllerSeatId=1, ownerSeatId=1, parentId=21, objectSourceGrpId=600)
    attiva = base + [gz(59, type="GameStateType_Diff", zones=[campo(3)], gameObjects=[carta(3, 100, 28, 1)], annotations=[zt(3, "PlayLand")]),
                     gz(61, type="GameStateType_Diff", zones=[campo(3, 21), pila(22)], gameObjects=[carta(3, 100, 28, 1, isTapped=True), carta(21, 600, 28, 1),
                                                                                                   abil_], annotations=[mp_(3, 22)])]
    fa_ = [f for f in azioni(attiva, {100: "Swamp", 600: "Unholy Annex"}.get, interni=True) if f["foto"].get("mn")]
    nulla = base + [gz(62, type="GameStateType_Diff", zones=[campo(3)], gameObjects=[carta(3, 100, 28, 1, isTapped=True)])]
    casi.append(("il pagamento da solo e' un passo, il mana va sul permanente; l'abilita' manda il mana sulla carta che la attiva; negativa: niente ManaPaid, "
                 "niente mana", [(f["foto"]["mn"], f["foto"].get("mnd")) for f in fp_] == [([[3, "B"]], 21)]
                 and [(f["foto"]["mn"], f["foto"].get("mnd")) for f in fa_] == [([[3, "B"]], 21)]
                 and not any(f["foto"].get("mn") for f in azioni(nulla, interni=True))))
    fine_c = gz(53, type="GameStateType_Diff", zones=[campo(9, 10)], turnInfo=dict(turnNumber=5, activePlayer=1, phase="Phase_Main1"),
                gameObjects=[carta(9, 500, 28, 1, cardTypes=["CardType_Creature"]), carta(10, 500, 28, 1, cardTypes=["CardType_Creature"])])
    ancora = gz(54, type="GameStateType_Diff", zones=[campo(9, 10)], gameObjects=[att_(9), att_(10)],
                turnInfo=dict(turnNumber=5, activePlayer=1, phase="Phase_Combat", step="Step_DeclareAttack"))
    fr2 = azioni(base + [uno(51, 9, 10), fine_c, ancora], {500: "Goblin"}.get)
    casi.append(("le stesse creature che riattaccano due turni dopo: un attacco nuovo", [f["t"] for f in fr2 if f["ev"][0][1].startswith("attacked")] == [3, 5]))
    zero_ = base + [gz(95, type="GameStateType_Diff", zones=[campo(15)], gameObjects=[carta(15, 510, 28, 2, cardTypes=["CardType_Creature"], power={},
                                                                                         toughness=dict(value=2))], annotations=[zt(15, "Resolve")])]
    casi.append(("la creatura 0/2: Arena non scrive la forza a zero, resta una creatura 0/2", azioni(zero_)[-1]["foto"]["c"][1] == [[510, 0, 0, 0, 2, 15, None]]))
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
    # il surveil dell'avversario (15 nov 2026): l'effetto senza richiesta a te; guarda 2 (dal testo dell'abilita'), una al cimitero, l'altra resta sopra
    # coperta; negativa: l'effetto cominciato e non finito non fa niente, e il tuo surveil (con la richiesta) non si conta due volte
    sub11 = lambda tp_, aff: dict(type=[tp_], affectorId=aff, affectedIds=[2], details=[dict(key="SubCategory", valueInt32=[11])])
    ab_s = dict(instanceId=14, grpId=7002, type="GameObjectType_Ability", zoneId=27, controllerSeatId=2, ownerSeatId=2)
    sorv_a = base + [gz(95, type="GameStateType_Diff", zones=[pila(14)], gameObjects=[ab_s], annotations=[sub11("AnnotationType_MultistepEffectStarted", 14)])]
    sorv_b = [gz(96, type="GameStateType_Diff", zones=[pila(), dict(zoneId=37, type="ZoneType_Graveyard", ownerSeatId=2, objectInstanceIds=[15])],
                 gameObjects=[carta(15, 800, 37, 2)], annotations=[zt(15, "Surveil"), sub11("AnnotationType_MultistepEffectComplete", 14)])]
    ab_vero = TA.abilita
    TA.abilita = lambda g_: "When it enters, surveil 2." if g_ == 7002 else ab_vero(g_)
    try:
        fs_ = azioni(sorv_a + sorv_b, {800: "Swamp"}.get)
        fs_meta = azioni(sorv_a, {800: "Swamp"}.get)
        req_ = "[UnityCrossThreadLogger]x " + json.dumps(dict(greToClientEvent=dict(greToClientMessages=[dict(
            systemSeatIds=[2], gameStateId=95, groupReq=dict(context="GroupingContext_Surveil", instanceIds=[15]))])))
        fs_mio = azioni(sorv_a + [req_] + sorv_b, {800: "Swamp"}.get)
    finally:
        TA.abilita = ab_vero
    casi.append(("il surveil dell'avversario: guarda 2, una resta sopra coperta, l'altra al cimitero",
                 fs_[-1]["foto"].get("sc") == [[0, 2, 1, 1], [800, 2, 0, 1]] and (2, "surveilled 2: 1 on top, 1 into the graveyard") in fs_[-1]["ev"]))
    casi.append(("negativa: l'effetto cominciato e non finito non fa lo sguardo; col tuo surveil (la richiesta) lo racconta la richiesta, una volta",
                 not any(f_.get("foto", {}).get("sc") for f_ in fs_meta) and len(fs_mio[-1]["foto"].get("sc") or []) == 1
                 and not any("surveilled 2" in tx_ for _c, tx_ in fs_mio[-1]["ev"])))
    # la spalla da un diario finto (in una cartella di partita finta)
    import tempfile
    # Settle the Wreckage (13 nov 2026): il bersaglio e' il giocatore, la magia esilia la sua creatura (ZoneTransfer con affectorId = la magia); nello stesso
    # messaggio un'altra creatura muore per altro (nessun affectorId): la freccia va alla prima, non alla seconda, ne' alle vite
    def esilio(nuovo, affettore):
        return dict(type=["AnnotationType_ZoneTransfer"], affectedIds=[nuovo], **(dict(affectorId=affettore) if affettore else {}),
                    details=[dict(key="zone_src", valueInt32=[28]), dict(key="category", valueString=["Exile"])])

    def settle(affettore, concede=False):
        righe_ = base + [gz(30, type="GameStateType_Diff", zones=[campo(9, 11)],
                            gameObjects=[carta(9, 900, 28, 2, cardTypes=["CardType_Creature"], power=dict(value=3), toughness=dict(value=3)),
                                         carta(11, 901, 28, 2, cardTypes=["CardType_Creature"], power=dict(value=1), toughness=dict(value=1))]),
                         gz(31, type="GameStateType_Diff", zones=[pila(4), mano(1, 5)], gameObjects=[carta(4, 200, 27, 1, cardTypes=["CardType_Instant"])],
                            diffDeletedInstanceIds=[2], annotations=[zt(4, "CastSpell")],
                            persistentAnnotations=[dict(type=["AnnotationType_TargetSpec"], affectorId=4, affectedIds=[2])]),
                         gz(32, type="GameStateType_Diff", zones=[campo()] if concede else [pila(), campo()], diffDeletedInstanceIds=[9, 11] if concede else [4, 9, 11],
                            annotations=[dict(type=["AnnotationType_ResolutionStart"], affectorId=4, affectedIds=[4]),
                                         dict(type=["AnnotationType_ObjectIdChanged"], affectedIds=[9], details=[dict(key="orig_id", valueInt32=[9]),
                                                                                                                 dict(key="new_id", valueInt32=[10])]),
                                         esilio(10, affettore), zt(11, "SBA_Damage")])]
        f_ = [f for f in azioni(righe_, {200: "Settle the Wreckage", 900: "Bear", 901: "Elf"}.get) if f["rel"]]
        return f_[0]["rel"] if f_ else {}
    import dati_analizzatore as DA_
    rs = settle(4)
    casi.append(("Settle the Wreckage: bersaglio il giocatore, colpita la creatura che ha esiliato, non quella morta per altro",
                 rs.get("bers") == [2] and rs.get("colpiti") == [9, 11] and rs.get("fatti") == [9] and DA_.colpiti_di(rs) == [9]))
    casi.append(("negativa: senza l'affectorId nessuna creatura e' della magia", DA_.colpiti_di(settle(None)) == []))
    casi.append(("la partita concessa con la magia ancora in pila (Arena non la toglie): la creatura esiliata resta colpita", DA_.colpiti_di(settle(4, True)) == [9]))
    # lo stato della carta (15 nov 2026): divieti, permessi, abilita' tolte, livello; le negative: la carta che toglie le abilita' a se stessa
    # (Multiversal Passage), la Qualification che non e' uno stato (costo ridotto, tipo 1), l'abilita' con usi rimasti
    q_ = lambda t, i: dict(type=["AnnotationType_Qualification"], affectedIds=[i], details=[dict(key="QualificationType", valueInt32=[t])])
    pers_st = {1: q_(21, 50), 2: q_(31, 50), 3: q_(32, 51), 4: q_(1, 52),
               5: dict(type=["AnnotationType_RemoveAbility", "AnnotationType_LayeredEffect"], affectorId=60, affectedIds=[53], details=[dict(key="53", valueString=["all"])]),
               6: dict(type=["AnnotationType_RemoveAbility", "AnnotationType_ModifiedType"], affectorId=54, affectedIds=[54], details=[dict(key="54", valueString=["all"])]),
               7: dict(type=["AnnotationType_ClassLevel"], affectorId=55, affectedIds=[55], details=[dict(key="Level", valueInt32=[2])]),
               8: dict(type=["AnnotationType_ClassLevel"], affectorId=55, affectedIds=[55], details=[dict(key="Level", valueInt32=[3])]),
               9: dict(type=["AnnotationType_AbilityExhausted"], affectedIds=[56], details=[dict(key="UsesRemaining", valueInt32=[1])])}
    xs_, _v = segni(pers_st, {}, {}, {})
    st_ = {i: [tuple(e_) for e_ in v_.get("st") or []] for i, v_ in xs_.items()}
    casi.append(("lo stato: NO UNTAP e CAN'T BLOCK sulla stessa carta, UNBLOCKABLE, NO ABILITIES data da un'altra, il livello piu' alto della Classe",
                 st_.get(50) == [("NO UNTAP", "no"), ("CAN'T BLOCK", "no")] and st_.get(51) == [("UNBLOCKABLE", "si")]
                 and st_.get(53) == [("NO ABILITIES", "no")] and st_.get(55) == [("LEVEL 3", "liv")]))
    casi.append(("negativa: niente stato per il costo ridotto, la carta che cambia tipo da se', l'abilita' con usi rimasti",
                 not st_.get(52) and not st_.get(54) and not st_.get(56)))
    # la carta della mano mostrata all'avversario (15 nov 2026): solo quella col segno, non l'altra in mano
    fr_mv = azioni([gs(type="GameStateType_Full", zones=[dict(zoneId=31, type="ZoneType_Hand", ownerSeatId=1, objectInstanceIds=[1, 2])],
                       players=[dict(systemSeatNumber=1, lifeTotal=20), dict(systemSeatNumber=2, lifeTotal=20)],
                       turnInfo=dict(turnNumber=2, activePlayer=1, step="Step_Upkeep"), gameObjects=[carta(1, 100, 31, 1), carta(2, 200, 31, 1)],
                       annotations=[dict(type=["AnnotationType_NewTurnStarted"], affectedIds=[1])],
                       persistentAnnotations=[dict(id=77, type=["AnnotationType_InstanceRevealedToOpponent"], affectorId=1, affectedIds=[1])])], nomi.get)
    casi.append(("la carta della tua mano mostrata a lui: nella foto c'e' lei sola (negativa: l'altra carta in mano no)",
                 bool(fr_mv) and fr_mv[-1]["foto"].get("mv") == [[100], []]))
    # la cima del grimorio che si conosce (15 nov 2026): la tua, privata, col nome; la sua, pubblica; negative: la carta senza nome in cima e quella
    # conosciuta ma non in cima (in fondo dopo uno scry) non sono la cima
    fr_cm = azioni([gs(type="GameStateType_Full", zones=[dict(zoneId=32, type="ZoneType_Library", ownerSeatId=1, objectInstanceIds=[5, 6]),
                                                          dict(zoneId=36, type="ZoneType_Library", ownerSeatId=2, objectInstanceIds=[7, 8]),
                                                          dict(zoneId=37, type="ZoneType_Library", ownerSeatId=3, objectInstanceIds=[])],
                       players=[dict(systemSeatNumber=1, lifeTotal=20), dict(systemSeatNumber=2, lifeTotal=20)],
                       turnInfo=dict(turnNumber=2, activePlayer=1, step="Step_Upkeep"),
                       gameObjects=[carta(5, 100, 32, 1, visibility="Visibility_Private"), dict(instanceId=6, zoneId=32, type="GameObjectType_Card"),
                                    carta(7, 200, 36, 2, visibility="Visibility_Public")],
                       annotations=[dict(type=["AnnotationType_NewTurnStarted"], affectedIds=[1])])], nomi.get)
    fr_cm2 = azioni([gs(type="GameStateType_Full", zones=[dict(zoneId=32, type="ZoneType_Library", ownerSeatId=1, objectInstanceIds=[6, 5])],
                        players=[dict(systemSeatNumber=1, lifeTotal=20), dict(systemSeatNumber=2, lifeTotal=20)],
                        turnInfo=dict(turnNumber=2, activePlayer=1, step="Step_Upkeep"),
                        gameObjects=[carta(5, 100, 32, 1, visibility="Visibility_Private"), dict(instanceId=6, zoneId=32, type="GameObjectType_Card")],
                        annotations=[dict(type=["AnnotationType_NewTurnStarted"], affectedIds=[1])])], nomi.get)
    # quante carte nei grimori (24 nov 2026): due e due, contate anche le coperte; negativa: la zona di un terzo posto non conta
    casi.append(("i grimori contati dalla zona, anche le carte coperte (2 e 2); negativa: il posto 3 non entra",
                 bool(fr_cm) and fr_cm[-1]["foto"].get("lb") == [2, 2]))
    # dove finisce la carta messa nel grimorio (15 nov 2026): in cima, in fondo, a meta'; negativa: rimessa in mano non dice il grimorio
    def messa_(lista, dest_tipo="ZoneType_Library"):
        r_ = azioni([gs(type="GameStateType_Full", zones=[dict(zoneId=32, type=dest_tipo, ownerSeatId=1, objectInstanceIds=lista)],
                        players=[dict(systemSeatNumber=1, lifeTotal=20), dict(systemSeatNumber=2, lifeTotal=20)],
                        turnInfo=dict(turnNumber=3, activePlayer=1, step="Step_Main1"), gameObjects=[carta(5, 100, 32, 1)],
                        annotations=[dict(type=["AnnotationType_ZoneTransfer"], affectedIds=[5],
                                          details=[dict(key="category", valueString=["Put"]), dict(key="zone_dest", valueInt32=[32])])])], nomi.get)
        return " ".join(tx for f_ in r_ for _c, tx in f_["ev"])
    # copie e legami (15 nov 2026): l'abilita' scattata per un'altra carta (negativa: la fonte non e' la causa), la copia mostra cio' che copia, crew
    righe_cl = [gs(type="GameStateType_Full", zones=[dict(zoneId=28, type="ZoneType_Battlefield", objectInstanceIds=[10, 11, 12, 13]),
                                                      dict(zoneId=27, type="ZoneType_Stack", objectInstanceIds=[20])],
                   players=[dict(systemSeatNumber=1, lifeTotal=20), dict(systemSeatNumber=2, lifeTotal=20)],
                   turnInfo=dict(turnNumber=3, activePlayer=1, step="Step_Main1"),
                   gameObjects=[carta(10, 100, 28, 1), carta(11, 200, 28, 1), carta(12, 900, 28, 1), carta(13, 100, 28, 1),
                                dict(instanceId=20, grpId=555, type="GameObjectType_Ability", zoneId=27, controllerSeatId=1, ownerSeatId=1, parentId=10)],
                   annotations=[dict(type=["AnnotationType_NewTurnStarted"], affectedIds=[1])],
                   persistentAnnotations=[dict(id=81, type=["AnnotationType_TriggeringObject"], affectorId=20, affectedIds=[11, 10]),
                                          dict(id=82, type=["AnnotationType_CopiedObject", "AnnotationType_LayeredEffect"], affectorId=12, affectedIds=[12],
                                               details=[dict(key="copyFromGrpid", valueInt32=[200])]),
                                          dict(id=83, type=["AnnotationType_CrewedThisTurn"], affectorId=13, affectedIds=[10])])]
    f_cl = azioni(righe_cl, nomi.get)[-1]
    camp_ = {e_[5]: e_[0] for e_ in f_cl["foto"]["c"][0]}
    x_cl = f_cl["foto"].get("x") or {}
    casi.append(("l'abilita' in pila scattata per un'altra carta: da [11] (negativa: la sua fonte, 10, no)", (f_cl["rel"] or {}).get("da") == [11]))
    casi.append(("la copia mostra cio' che copia, con l'originale nei segni (negativa: la carta che non copia resta lei)",
                 camp_.get(12) == 200 and x_cl.get(12, {}).get("copia_di") == 900 and camp_.get(11) == 200 and camp_.get(10) == 100))
    # gli emblemi (15 nov 2026): l'emblema della zona Command col nome della sua carta; negativa: un altro oggetto della zona no
    f_em = azioni([gs(type="GameStateType_Full", zones=[dict(zoneId=40, type="ZoneType_Command", objectInstanceIds=[30, 31])],
                      players=[dict(systemSeatNumber=1, lifeTotal=20), dict(systemSeatNumber=2, lifeTotal=20)],
                      turnInfo=dict(turnNumber=3, activePlayer=1, step="Step_Main1"),
                      gameObjects=[dict(instanceId=30, grpId=2, type="GameObjectType_Emblem", zoneId=40, controllerSeatId=2, ownerSeatId=2, objectSourceGrpId=900),
                                   dict(instanceId=31, grpId=5, type="GameObjectType_Ability", zoneId=40, controllerSeatId=1, ownerSeatId=1, objectSourceGrpId=100)],
                      annotations=[dict(type=["AnnotationType_NewTurnStarted"], affectedIds=[1])])], nomi.get)
    casi.append(("l'emblema suo col nome della carta che l'ha creato; negativa: un'abilita' nella stessa zona no",
                 bool(f_em) and f_em[-1]["foto"].get("em") == [[], [900]]))
    # le carte che cambiano (15 nov 2026): colore e tipo nella stessa annotazione (una terra Restless); negativa: ModifiedType su una creatura non terra
    ann_cm = {1: dict(type=["AnnotationType_ModifiedType", "AnnotationType_ModifiedColor", "AnnotationType_LayeredEffect"], affectorId=60, affectedIds=[60],
                      details=[dict(key="color", valueInt32=[1, 3])]),
              2: dict(type=["AnnotationType_ModifiedType"], affectedIds=[61])}
    obj_cm = {60: dict(cardTypes=["CardType_Land", "CardType_Creature"]), 61: dict(cardTypes=["CardType_Creature"])}
    x_cm, _v = segni(ann_cm, obj_cm, {}, {})
    casi.append(("colore e tipo insieme sulla terra animata: NOW WHITE · BLACK e NOW A CREATURE; negativa: la creatura che non e' terra niente",
                 [tuple(e_) for e_ in x_cm.get(60, {}).get("st", [])] == [("NOW WHITE · BLACK", "col"), ("NOW A CREATURE", "si")] and not x_cm.get(61)))
    # come e' stata lanciata la magia in pila (15 nov 2026): kicker e X; negativa: la stessa annotazione su una carta in campo non scrive niente
    cto_ = lambda i, t, **k: dict(id=90 + i + t, type=["AnnotationType_CastingTimeOption"], affectedIds=[i],
                                  details=[dict(key="type", valueInt32=[t])] + [dict(key=k_, valueInt32=[v_]) for k_, v_ in k.items()])
    f_op = azioni([gs(type="GameStateType_Full", zones=[dict(zoneId=27, type="ZoneType_Stack", objectInstanceIds=[21]),
                                                         dict(zoneId=28, type="ZoneType_Battlefield", objectInstanceIds=[22])],
                      players=[dict(systemSeatNumber=1, lifeTotal=20), dict(systemSeatNumber=2, lifeTotal=20)],
                      turnInfo=dict(turnNumber=3, activePlayer=1, step="Step_Main1"),
                      gameObjects=[carta(21, 200, 27, 1, cardTypes=["CardType_Instant"]), carta(22, 100, 28, 1)],
                      annotations=[dict(type=["AnnotationType_NewTurnStarted"], affectedIds=[1])],
                      persistentAnnotations=[cto_(21, 3), cto_(21, 2, value=3), cto_(22, 3)])], nomi.get)
    f_cp = azioni([gs(type="GameStateType_Full", zones=[dict(zoneId=27, type="ZoneType_Stack", objectInstanceIds=[23]),
                                                         dict(zoneId=28, type="ZoneType_Battlefield", objectInstanceIds=[24, 25, 26])],
                      players=[dict(systemSeatNumber=1, lifeTotal=20), dict(systemSeatNumber=2, lifeTotal=20)],
                      turnInfo=dict(turnNumber=3, activePlayer=1, step="Step_Main1"),
                      gameObjects=[carta(23, 200, 27, 1, cardTypes=["CardType_Instant"], isCopy=True), carta(24, 100, 28, 1, isCopy=True),
                                   carta(25, 900, 28, 1, isFacedown=True), carta(26, 100, 28, 1)],
                      annotations=[dict(type=["AnnotationType_NewTurnStarted"], affectedIds=[1])])], nomi.get)
    x_cp = (f_cp[-1]["foto"].get("x") or {}) if f_cp else {}
    casi.append(("la magia copiata in pila COPY, la pedina copia COPY, la carta a faccia in giu' FACE DOWN; negativa: la carta normale niente",
                 bool(f_cp) and f_cp[-1]["foto"].get("op") == {23: ["COPY"]} and ["COPY", "si"] in x_cp.get(24, {}).get("st", [])
                 and ["FACE DOWN", "off"] in x_cp.get(25, {}).get("st", []) and not x_cp.get(26)))
    casi.append(("la magia in pila col kicker e X = 3; negativa: la carta in campo niente", bool(f_op) and f_op[-1]["foto"].get("op") == {21: ["KICKED", "X = 3"]}))
    casi.append(("crew: CREWED sul veicolo, CREWING su chi lo equipaggia", ["CREWED", "si"] in x_cl.get(13, {}).get("st", [])
                 and ["CREWING", "off"] in x_cl.get(10, {}).get("st", [])))
    casi.append(("la carta messa nel grimorio: in cima, in fondo, terza dalla cima; negativa: messa in mano non dice il grimorio",
                 "on top of the library" in messa_([5, 6, 7, 8]) and "on the bottom of the library" in messa_([6, 7, 8, 5])
                 and "3rd from the top" in messa_([6, 7, 5, 8]) and "library" not in messa_([5, 6], "ZoneType_Hand")))
    casi.append(("la cima conosciuta: la tua privata, la sua pubblica; negativa: la carta conosciuta che non e' in cima no",
                 bool(fr_cm) and fr_cm[-1]["foto"].get("cm") == [[100, 0], [200, 1]] and bool(fr_cm2) and "cm" not in fr_cm2[-1]["foto"]))
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
