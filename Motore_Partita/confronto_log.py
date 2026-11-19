"""Il passo 8.3 del motore di partita: le scelte di Autore nelle partite vere contro quelle del Cercatore (14 ott 2026).

Il piano e' nell'handoff (HANDOFF_Motore_Partita.md, §5, passo 8.3): le scelte di Autore nelle 44 partite di Quick Draft
FRA contro quelle del `Cercatore` (guarda_avanti.py) dallo stesso stato. Come si fa:
  1. i punti di scelta dal log di Arena (`punti`): la prima mossa della prima fase principale del suo turno (agisci), la
     dichiarazione degli attaccanti (attacca), quella dei bloccanti nel turno dell'avversario (blocca); per ognuno lo stato
     del log in quel momento e la risposta di Autore (la prima azione sua in quella fase: terra, magia coi bersagli,
     abilita', o niente; gli attaccanti e chi attaccano; i bloccanti e chi bloccano);
  2. lo stato rifatto col motore e con le carte vere (`DalLog`, il gancio `prepara` di simula.partita): la mano, il campo
     (tappati, danno, segnalini, debolezza da evocazione 302.6, aure e equipaggiamenti attaccati, pedine), il cimitero,
     l'esilio, le vite, quante carte in mano e nel grimorio; il grimorio di Autore e' il suo mazzo vero meno le carte
     viste nelle altre zone;
  3. la partita che riparte a meta' turno (`Riparti`): dal passo giusto, senza rifare le azioni del turno che il log ha gia'
     fatto (500.1, 703.4); per i bloccanti, gli attaccanti del log gia' dichiarati (508.1k);
  4. il controllo dello stato (`verifica`): prima di scegliere, il tavolo del motore deve essere quello del log (vite, carte
     per zona, per ogni permanente controllore, tappato, danno, segnalini, forza e costituzione, parole chiave): se no il
     punto si salta, col perche'. Un punto saltato non e' un punto verde;
  5. il `CercatoreLog`: al punto di scelta prova le sue candidate E la mossa vera di Autore negli stessi mondi (R a
     candidata), sceglie la migliore; poi, dove la sua scelta e' diversa da quella di Autore, le due si rigiocano in
     2R mondi NUOVI (la scelta fatta coi mondi di prima premia per caso la candidata fortunata: il confronto onesto e' su
     mondi che non hanno deciso niente) e si contano le coppie mondo per mondo (test dei segni).
Quello che il confronto sa e non sa, dichiarato:
  - il mazzo dell'avversario non si conosce: si conoscono le carte che ha mostrato nella partita (in campo, al cimitero, in
    esilio, in pila). Il mazzo modello e' quelle carte (il massimo di copie viste insieme) + le terre a 17 su 40 nelle
    proporzioni delle sue terre viste + le altre carte non terra a 23 ripescate a caso dalle sue non terra viste. E' un
    modello, non il suo mazzo: un'ipotesi scritta. Le carte che mostrera' piu' avanti nella partita fanno parte del modello
    (come nel passo 8.2 il Cercatore conosce la lista del mazzo dell'avversario, non l'ordine ne' la mano);
  - l'avversario e' il Semplice nelle partite di prova, non il giocatore vero;
  - dopo la mossa le partite le giocano due Semplice (come nel passo 8.2): il punteggio di una mossa dice quanto vince con
    quei giocatori, non con Autore;
  - un effetto temporaneo in corso, un segnalino sconosciuto, la pila non vuota, una pedina che il motore non sa fare, una
    carta preparata (723.3) che il log non dice, una mossa che il motore non sa scrivere: il punto si salta e si conta.

    py -I -X utf8 Motore_Partita/confronto_log.py --punti            i punti di scelta letti dai log e i saltati, col perche'
    py -I -X utf8 Motore_Partita/confronto_log.py --prova            le prove
    py -I -X utf8 Motore_Partita/confronto_log.py --spazzata         ogni punto rifatto e giocato fino alla fine con la mossa vera (arbitro acceso)
    py -I -X utf8 Motore_Partita/confronto_log.py --confronto [R]    il confronto, R prove a candidata (12), 2R mondi di conferma; scrive Confronto_Log_Quick_FRA.md
    py -I -X utf8 Motore_Partita/confronto_log.py --confronto R --turni K   lo stesso con le partite di prova troncate (passo 8.5),
                                                                     in Confronto_Log_Quick_FRA_Troncate.md
    py -I -X utf8 Motore_Partita/confronto_log.py --confronto R --turni K --valuta v1   lo stesso giudicato dalla V1 (passo 8.6),
                                                                     in Confronto_Log_Quick_FRA_Troncate_V1.md
    py -I -X utf8 Motore_Partita/confronto_log.py --rapporto [R]     riscrive il rapporto da confronto_log.json
"""
import json
import math
import os
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import carte_fra as F
import effetti as E
import guarda_avanti as G
import riscontro as R
import simula as S
from tavolo import PAROLE
from turno import FASI, SENZA_PRIORITA

QUI = os.path.dirname(os.path.abspath(__file__))
REPORT = os.path.join(QUI, "Confronto_Log_Quick_FRA.md")
ZONE = {"ZoneType_Battlefield": "campo", "ZoneType_Graveyard": "cimitero", "ZoneType_Exile": "esilio", "ZoneType_Hand": "mano",
        "ZoneType_Stack": "pila", "ZoneType_Library": "grimorio"}
TERRE_LIMITED, CARTE_LIMITED = 17, 40          # i 10 mazzi veri di Autore sono tutti 17 su 40 (mazzi_veri.json)


class Saltato(Exception):
    """Il punto non si puo' rifare con certezza: il perche' e' il messaggio."""


class Fermo(Exception):
    """Il Cercatore ha scelto al punto di scelta: la partita vera non serve oltre."""


# ====================================================================== 1. i punti di scelta dal log
def mio_posto(seq):
    """Il posto di Autore: quello di cui il log fa vedere la mano (400.2: la mano dell'avversario e' nascosta)."""
    for _, dopo, _ in seq:
        for s in (1, 2):
            z = dopo.zona("ZoneType_Hand", s)
            if z and any(i in dopo.obj for i in z.get("objectInstanceIds", [])): return s
    return None


def _chi_comincia(seq):
    for _, dopo, _ in seq:
        if dopo.turno.get("turnNumber") == 1 and dopo.turno.get("activePlayer"): return dopo.turno["activePlayer"]
    return None


def _nome(o):
    return R.nome(o.get("grpId")) if o else None


def in_zone(st, tipo):
    """Tutti gli oggetti delle zone di quel tipo (il cimitero e la mano sono una per giocatore: Stato.in_zona ne da' una)."""
    return [st.obj[i] for z in st.zone.values() if z["type"] == tipo for i in z.get("objectInstanceIds", []) if i in st.obj]


def _pubbliche(st, seat):
    """Le carte (non pedine, non copie) di proprieta' di seat nelle zone pubbliche: nome -> quante (400.2)."""
    c = Counter()
    for z, tipo in ZONE.items():
        if tipo in ("mano", "grimorio"): continue
        for o in in_zone(st, z):
            if o.get("ownerSeatId") != seat or o.get("type") != "GameObjectType_Card" or o.get("isCopy"): continue
            n = _nome(o)
            if n: c[n] += 1
    return c


SEGNAPOSTO = "Unsummon"                 # dal vivo: una magia di un altro set nel cimitero dell'avversario; senza abilita' da li'
BASI = {"W": "Plains", "U": "Island", "B": "Swamp", "R": "Mountain", "G": "Forest"}
COPIE_MASSIME = 3                       # nel modello, per una carta non vista (nel Limited non c'e' un limite: 100.2b; e' un'ipotesi)
_VISTE_AVV = None


def viste_avversario(seq, avv):
    """Le carte che l'avversario ha mostrato nella partita, ognuna col massimo di copie viste insieme (400.2)."""
    viste = Counter()
    for _, dopo, _ in seq:
        for n, k in _pubbliche(dopo, avv).items(): viste[n] = max(viste[n], k)
    return viste


def viste_di_tutti():
    """gid -> le carte mostrate dall'avversario di quella partita, su tutte le partite di Quick Draft FRA."""
    global _VISTE_AVV
    if _VISTE_AVV is None:
        _VISTE_AVV = {}
        for gid, path in R.partite():
            seq = list(R.messaggi(path))
            io = mio_posto(seq)
            if io: _VISTE_AVV[gid] = viste_avversario(seq, 3 - io)
    return _VISTE_AVV


def colori_carta(nome):
    """I colori del costo di mana (202.2, 105.2): le lettere WUBRG nei simboli, anche ibridi."""
    t = F.tutte().get(nome)
    import re
    return set(re.findall(r"[WUBRG]", (t.voce[2].get("costo") or "") if t else ""))


def mazzo_modello(seq, avv, gid, senza_terre=False):
    """Il mazzo modello dell'avversario (dichiarato nel docstring del modulo):
      - le carte che ha mostrato nella partita, ognuna col massimo di copie viste insieme;
      - le terre fino a 17 nelle proporzioni delle sue terre viste (i 10 mazzi di Autore sono tutti 17 su 40);
      - le non terra fino a 23 dal «pool del formato»: le non terra che gli avversari hanno mostrato in TUTTE le partite di
        Quick Draft FRA, pesate per quante partite le mostrano, solo nei colori di questo avversario (quelli delle sue terre
        e delle sue carte viste), al massimo 3 copie per carta. Se non bastano, le carte di FRA di quei colori, a pari peso.
    Fino al 14 ott 2026 18:30 le non terra mancanti si ripescavano dalle sue sole non terra viste: con due carte viste ne
    uscivano 13 copie di una (Tetsuko Umezawa, Pursuer), un mazzo che non esiste. -> (lista di nomi, informazioni)."""
    import probabilita as PR
    viste = viste_avversario(seq, avv)
    T = F.tutte()
    terre = Counter({n: k for n, k in viste.items() if n in T and "Land" in T[n].voce[1]})
    altre = Counter({n: k for n, k in viste.items() if n in T and "Land" not in T[n].voce[1]})
    fuori = sorted(n for n in viste if n not in T)                                              # restano fuori dal modello: un punto
    if not terre and not senza_terre: raise Saltato("l'avversario non ha mostrato terre")
    colori = set().union(*(PR.colori_terra(n) for n in terre)) | set().union(*(colori_carta(n) for n in altre)) if altre else \
        set().union(*(PR.colori_terra(n) for n in terre))
    rng = np.random.default_rng([abs(hash_stabile(gid)), 8303])
    mazzo = list(terre.elements()) + list(altre.elements())
    basi = sorted(terre.elements())
    if not terre:                                                                              # dal vivo: i primi turni di chi non ha mostrato terre
        colori = colori or set("WUBRG")                                                        # (un'ipotesi: i colori delle sue magie, se no tutti e cinque)
        basi = sorted(BASI[c] for c in colori)
    nomi_terra = set(terre) | set(basi)
    while sum(1 for n in mazzo if n in nomi_terra) < TERRE_LIMITED: mazzo.append(basi[int(rng.integers(len(basi)))])
    peso = Counter()
    for g, v in viste_di_tutti().items():
        for n in v:
            if n in T and "Land" not in T[n].voce[1] and colori_carta(n) <= colori: peso[n] += 1
    da_fra = sorted(n for n, t in T.items() if "Land" not in t.voce[1] and colori_carta(n) and colori_carta(n) <= colori
                    and "Basic" not in t.voce[1])
    usate_fra = 0
    while len(mazzo) < CARTE_LIMITED:
        dentro = Counter(mazzo)
        cand = sorted(n for n in peso if dentro[n] < max(COPIE_MASSIME, altre[n]))
        if cand:
            w = np.array([peso[n] for n in cand], dtype=float)
            mazzo.append(cand[int(rng.choice(len(cand), p=w / w.sum()))])
            continue
        cand = [n for n in da_fra if dentro[n] < COPIE_MASSIME]
        if not cand: raise Saltato("il modello dell'avversario non si riempie: nessuna carta dei suoi colori")
        mazzo.append(cand[int(rng.integers(len(cand)))]); usate_fra += 1
    return mazzo, {"viste": sum(viste.values()), "terre viste": sum(terre.values()), "non terra viste": sum(altre.values()),
                   "colori": "".join(sorted(colori)), "dal pool del formato": CARTE_LIMITED - sum(viste.values()) - (TERRE_LIMITED - sum(terre.values())) - usate_fra,
                   "da FRA a pari peso": usate_fra, "fuori da FRA": fuori}


def dettagli_lista(a, chiave):
    """Il valore intero di un dettaglio del log (R.dettagli ne prende solo il primo)."""
    for x in a.get("details", []):
        if x["key"] == chiave: return x.get("valueInt32") or x.get("valueString") or []
    return []


def hash_stabile(s):
    h = 0
    for ch in s: h = (h * 131 + ord(ch)) % (2 ** 61 - 1)
    return h


def _bersagli_log(seq):
    """601.2c: i bersagli dichiarati, per oggetto (AnnotationType_TargetSpec), come nel riscontro."""
    b = defaultdict(lambda: defaultdict(list))
    for _, _, ann in seq:
        for a in ann:
            if a["type"][0] == "AnnotationType_TargetSpec" and a.get("affectorId") is not None:
                idx = R.dettagli(a).get("index", 1)
                for x in a.get("affectedIds", []):
                    if x not in b[a["affectorId"]][idx]: b[a["affectorId"]][idx].append(x)
    return b


def _risposta_agisci(seq, k, io, bersagli):
    """La prima azione di Autore nella prima fase principale (UserActionTaken: 1 lancio confermato, 2 abilita', 3 terra;
    4 e' il mana). -> ("passa",) | ("terra", nome) | ("lancia", nome, zona, bersagli) | ("attiva", nome sorgente, grpId)."""
    turno = seq[k][1].turno.get("turnNumber")
    for j in range(k + 1, len(seq)):
        prima, dopo, ann = seq[j]
        for a in ann:
            if a["type"][0] != "AnnotationType_UserActionTaken" or a.get("affectorId") != io: continue
            t_ = R.dettagli(a).get("actionType")
            ids = a.get("affectedIds", [])
            if not ids or t_ not in (1, 2, 3): continue
            o = dopo.obj.get(ids[0]) or prima.obj.get(ids[0])
            if t_ == 3: return ("terra", _nome(o))
            if t_ == 1:
                zona = None
                for jj in range(j, max(-1, j - 30), -1):
                    for x in seq[jj][2]:
                        if x["type"][0] == "AnnotationType_ZoneTransfer" and R.dettagli(x).get("category") == "CastSpell" and ids[0] in x.get("affectedIds", []):
                            zona = seq[jj][0].tipo_zona(R.dettagli(x).get("zone_src")) or seq[jj][1].tipo_zona(R.dettagli(x).get("zone_src"))
                    if zona: break
                ber = {i_: list(v) for i_, v in bersagli.get(ids[0], {}).items()}
                return ("lancia", _nome(o), ZONE.get(zona, zona), ber)
            if t_ == 2:
                src = dopo.obj.get((o or {}).get("parentId")) or prima.obj.get((o or {}).get("parentId"))
                delta = None                                                                       # 606.4: il costo di fedelta' pagato,
                for jj in range(max(0, j - 1), min(j + 4, len(seq))):                               # dai segnalini fedelta' (tipo 7) tolti o
                    for x in seq[jj][2]:                                                           # messi dall'abilita'
                        dx = R.dettagli(x)
                        if x.get("affectorId") == ids[0] and dx.get("counter_type") == 7:
                            if x["type"][0] == "AnnotationType_CounterRemoved": delta = (delta or 0) - dx.get("transaction_amount", 0)
                            if x["type"][0] == "AnnotationType_CounterAdded": delta = (delta or 0) + dx.get("transaction_amount", 0)
                return ("attiva", _nome(src) if src else None, R.dettagli(a).get("abilityGrpId"), (o or {}).get("parentId"),
                        {i_: list(v) for i_, v in bersagli.get(ids[0], {}).items()}, delta)
        tu = dopo.turno
        if tu.get("turnNumber") != turno or tu.get("phase") != "Phase_Main1": return ("passa",)
    return ("passa",)


def _risposta_attacca(seq, k, io):
    """Gli attaccanti di Autore: le sue creature dichiarate nel passo (AttackState Declared o Attacking), col bersaglio
    (attackInfo.targetId: un posto o un planeswalker). -> {iid: bersaglio}."""
    turno, out = seq[k][1].turno.get("turnNumber"), {}
    for j in range(k, len(seq)):
        dopo = seq[j][1]
        tu = dopo.turno
        if tu.get("turnNumber") != turno or tu.get("phase") != "Phase_Combat": break
        for o in dopo.in_zona("ZoneType_Battlefield"):
            if o.get("controllerSeatId") == io and o.get("attackState") in ("AttackState_Declared", "AttackState_Attacking"):
                out.setdefault(o["instanceId"], (o.get("attackInfo") or {}).get("targetId"))
        if tu.get("step") not in ("Step_DeclareAttack", None) and out: break
    return out


def _risposta_blocca(seq, k, io):
    """I bloccanti di Autore: le sue creature col BlockState Declared o Blocking e gli attaccanti che bloccano."""
    turno, out = seq[k][1].turno.get("turnNumber"), {}
    for j in range(k, len(seq)):
        dopo = seq[j][1]
        tu = dopo.turno
        if tu.get("turnNumber") != turno or tu.get("phase") != "Phase_Combat": break
        for o in dopo.in_zona("ZoneType_Battlefield"):
            if o.get("controllerSeatId") == io and o.get("blockState") in ("BlockState_Declared", "BlockState_Blocking"):
                out.setdefault(o["instanceId"], list((o.get("blockInfo") or {}).get("attackerIds", [])))
        if tu.get("step") not in ("Step_DeclareBlock", None) and out: break
    return out


def descrivi_stato(st, io, avv, chi_comincia, turno, attivo, fase, passo, mazzo_io, sideboard_io, mazzo_avv, effetti=None):
    """Lo stato del log come dati semplici (si passano ai processi delle partite di prova). Saltato se il motore non lo
    puo' rifare con certezza. effetti: dal vivo, la lista dove raccogliere gli effetti temporanei; una sua carta fuori da
    FRA, magia al cimitero o in esilio, diventa un segnaposto."""
    perche = ignoto(st, effetti)
    if perche: raise Saltato(perche)
    if st.in_zona("ZoneType_Stack"): raise Saltato("la pila non e' vuota (500.2)")
    T = F.tutte()
    oggetti = []
    for z, tipo in ZONE.items():
        if tipo in ("grimorio", "pila") or (tipo == "mano"): continue
        for o in in_zone(st, z):
            n = _nome(o)
            d = {"iid": o["instanceId"], "nome": n, "zona": tipo, "proprietario": o["ownerSeatId"] - 1,
                 "controllore": o.get("controllerSeatId", o["ownerSeatId"]) - 1, "tappato": bool(o.get("isTapped")),
                 "danno": o.get("damage", 0) or 0, "malato": bool(o.get("hasSummoningSickness")), "pedina": None,
                 "forza": R.valore(o.get("power", {})) if "CardType_Creature" in o.get("cardTypes", []) else None,
                 "costituzione": R.valore(o.get("toughness", {})) if "CardType_Creature" in o.get("cardTypes", []) else None,
                 "parole": sorted(R.parole_log(o) & set(PAROLE)), "fedelta_usata": bool(o.get("loyaltyUsed")),
                 "segnalini": {R.SEGNALINI_LOG[c]: n_ for c, n_ in R.segnalini_log(st, o["instanceId"]).items() if c in R.SEGNALINI_LOG}}
            if o.get("isCopy") and tipo == "esilio" and n in magie_preparate():                    # 723.3c: la copia della magia
                d["preparata"] = n                                                                 # preparata, in esilio
                oggetti.append(d)
                continue
            if o.get("isCopy"): raise Saltato(f"una copia in {tipo} ({n}): il motore non sa da cosa copia")
            if o.get("type") == "GameObjectType_Token":
                if tipo != "campo": continue                                                       # 704.5d: cessa fuori dal campo
                d["pedina"] = pedina_di(n, o)
            elif o.get("type") != "GameObjectType_Card":
                raise Saltato(f"in {tipo} un oggetto {o.get('type')}")
            elif n not in T:
                magia = set(o.get("cardTypes", [])) & {"CardType_Instant", "CardType_Sorcery"}
                if effetti is None or not magia or tipo == "campo" or o["ownerSeatId"] == io:
                    raise Saltato(f"{n} in {tipo}: non e' fra le carte di FRA del motore")
                d["nome"] = SEGNAPOSTO                                                             # conta come una magia in quella zona
            oggetti.append(d)
    mani = []
    for s in (1, 2):
        z = st.zona("ZoneType_Hand", s) or {}
        ids = z.get("objectInstanceIds", [])
        mani.append([_nome(st.obj[i]) for i in ids] if s == io else len(ids))
    grimori = [len((st.zona("ZoneType_Library", s) or {}).get("objectInstanceIds", [])) for s in (1, 2)]
    attacchi = {}
    if passo == "bloccanti":
        for o in st.in_zona("ZoneType_Battlefield"):
            if o.get("attackState") in ("AttackState_Declared", "AttackState_Attacking"):
                attacchi[o["instanceId"]] = (o.get("attackInfo") or {}).get("targetId")
        if not attacchi: raise Saltato("nessun attaccante nel log al passo dei bloccanti")
    for a_, b_ in R.attaccamenti(st).items():
        for d in oggetti:
            if d["iid"] == a_: d["attaccato_a"] = b_
    per_iid = {d["iid"]: d for d in oggetti}
    for a in st.pann.values():
        tipi = a["type"]
        if "AnnotationType_TemporaryPermanent" in tipi or "AnnotationType_DelayedTriggerAffectees" in tipi:
            raise Saltato("un'abilita' ritardata in corso (603.7): il log non dice cosa fara'")
        if "AnnotationType_ColorProduction" in tipi:                                               # 105.4, 614.12a: il colore scelto
            for x in a.get("affectedIds", []):                                                       # (Room of Refuge) dai colori che produce
                if x in per_iid: per_iid[x]["colori"] = [R.COLORE.get(c) for c in dettagli_lista(a, "colors")]
        if "AnnotationType_AbilityExhausted" in tipi and R.dettagli(a).get("UsesRemaining") == 0:   # 603.1a: «only once each turn»
            for x in a.get("affectedIds", []):
                if x in per_iid: per_iid[x]["una_volta_usata"] = True
        if "AnnotationType_DisplayCardUnderCard" in tipi and a.get("affectorId") in per_iid:        # 610.3: esiliata finche' la fonte resta
            per_iid[a["affectorId"]].setdefault("sotto", []).extend(x for x in a.get("affectedIds", []) if x in per_iid)
    # i mazzi: quello vero di Autore, il modello dell'avversario; le carte che servono alle zone devono esserci
    io_i, avv_i = io - 1, avv - 1
    usate = [Counter(), Counter()]
    for d in oggetti:
        if d["pedina"] is None and not d.get("preparata"): usate[d["proprietario"]][d["nome"]] += 1
    usate[io_i].update(mani[io_i])
    resto_io = Counter(mazzo_io) - usate[io_i]
    manca = usate[io_i] - Counter(mazzo_io)
    if manca: raise Saltato(f"carte di Autore fuori dal suo mazzo: {sorted(manca.elements())[:3]} (dal sideboard?)")
    if sum(resto_io.values()) != grimori[io_i]:
        raise Saltato(f"il grimorio di Autore: {grimori[io_i]} nel log, {sum(resto_io.values())} dal mazzo vero")
    nascoste_avv = mani[avv_i] + grimori[avv_i]
    rng = np.random.default_rng([turno, len(oggetti), 8304])
    resto_avv = list((Counter(mazzo_avv) - usate[avv_i]).elements())
    rng.shuffle(resto_avv)
    pubbliche_avv = list(usate[avv_i].elements())
    if len(resto_avv) >= nascoste_avv: nasc = resto_avv[:nascoste_avv]
    else:                                                                                          # un mazzo da piu' di 40: si ripesca
        nasc = list(resto_avv)
        base = sorted(mazzo_avv)
        while len(nasc) < nascoste_avv: nasc.append(base[int(rng.integers(len(base)))])
    mazzi = [None, None]
    mazzi[io_i] = list(mazzo_io)
    mazzi[avv_i] = pubbliche_avv + nasc
    sideboard = [[], []]
    sideboard[io_i] = list(sideboard_io)
    return {"turno": turno, "attivo": attivo - 1, "primo": (chi_comincia or 1) - 1, "fase": fase, "passo": passo,
            "io": io_i, "oggetti": oggetti, "mani": mani, "grimori": grimori, "attacchi": attacchi,
            "vite": [st.pl.get(s, {}).get("lifeTotal", 20) for s in (1, 2)], "mazzi": mazzi, "sideboard": sideboard,
            "terre_giocate": None}


def ignoto(st, raccogli=None):
    """raccogli (dal vivo, 4 nov 2026): una lista dove mettere gli effetti temporanei invece di saltare il punto; li rifa' DalLog
    dai numeri del log, e `verifica` controlla che tornino. Quello che il motore non puo' rifare dal log: un segnalino sconosciuto (122.1), un effetto che non viene da
    un'abilita' statica di un permanente in campo (una magia o un'abilita' risolta: un effetto temporaneo, 611.2). Gli
    effetti delle statiche delle carte in campo (604, 613: Marwyn, i «Way of the») il motore li calcola da se', e
    `verifica` controlla che forza, costituzione e parole chiave tornino col log. Una carta senza abilita' statiche che
    figura come autore di un effetto lo ha creato con un'abilita' innescata o attivata: e' temporaneo."""
    campo = {o["instanceId"]: o for o in st.in_zona("ZoneType_Battlefield")}
    for a in st.pann.values():
        if "AnnotationType_Counter" in a["type"]:
            if R.dettagli(a).get("counter_type") not in R.SEGNALINI_LOG: return "un segnalino che il motore non conosce"
            continue
        if not (set(a["type"]) & R.EFFETTI) or R.effetto_letto(st, a): continue
        o = campo.get(a.get("affectorId"))
        tr = R.carta(o) if o else None
        if tr is not None and tr.intera and any(ab.get("tipo") == "statica" for ab in tr.voce[2].get("abilita") or []): continue
        if raccogli is not None and a.get("affectedIds"):
            raccogli.append(a)
            continue
        x = st.obj.get(a.get("affectorId")) or {}
        chi = _nome(x) if x.get("type") in ("GameObjectType_Card", "GameObjectType_Token") else R.nome(x.get("objectSourceGrpId"))
        return f"un effetto temporaneo in corso ({chi})"
    return None


def durate_effetti(seq, fine, effetti, turno):
    """iid -> «fine_turno» o None (per sempre), per le creature toccate dagli effetti raccolti. 611.2a: il log non scrive la durata.
    Un effetto gia' in corso in un turno passato non era «until end of turn» (514.2); uno nato in questo turno si tratta come tale:
    e' un'ipotesi, l'unica che i numeri del log permettono."""
    vecchi = set()
    for _, dopo, _ in seq[:fine]:
        if dopo.turno.get("turnNumber") != turno: vecchi |= set(dopo.pann)
    out = {}
    for a in effetti:
        for i in a["affectedIds"]:
            d = None if a["id"] in vecchi else "fine_turno"
            out[i] = None if i in out and out[i] is None else d
    return out


def storia(seq, fine, N, attivo, st):
    """La storia del turno N (fino al messaggio fine, escluso) e del turno prima, dal log, come eventi del motore: il
    motore la legge per le condizioni «this turn» e «last turn» (scry e surveil 701.22a/701.25a, pescate 121.1, morti
    700.4, magie lanciate 601.2i, vita 119, danni 120.3, scarti 701.9a, macinate 701.17, abilita' di fedelta' 606, chi e'
    entrato 603.6, chi attacca 508.1k). -> [(turno, dati dell'evento)]; i permanenti per numero del log («_iid»), da
    tradurre nel tavolo rifatto."""
    T = F.tutte()
    def carta_di(nome, o):
        if nome in T: return (nome, T[nome].voce[1])
        d = definizioni_pedine().get(nome)
        if d: return (d["nome"], d["tipo"])
        tipi = " ".join(x.replace("CardType_", "") for x in (o or {}).get("cardTypes", [])) or "Card"
        return (nome or "?", ("Token " if (o or {}).get("type") == "GameObjectType_Token" else "") + tipi)
    out = []
    inizio = next((j for j in range(len(seq)) if (seq[j][1].turno.get("turnNumber") or 0) >= N - 1), 0)
    for j in range(inizio, fine):
        prima, dopo, ann = seq[j]
        tn = dopo.turno.get("turnNumber")
        if tn not in (N - 1, N): continue
        for a in ann:
            tipo = a["type"][0]
            d = R.dettagli(a)
            if tipo == "AnnotationType_ZoneTransfer":
                ids = a.get("affectedIds", [])
                if not ids: continue
                o = dopo.obj.get(ids[0]) or prima.obj.get(ids[0]) or {}
                da = ZONE.get(prima.tipo_zona(d.get("zone_src")) or dopo.tipo_zona(d.get("zone_src")))
                verso = ZONE.get(dopo.tipo_zona(d.get("zone_dest")) or prima.tipo_zona(d.get("zone_dest")))
                cat = d.get("category")
                z_src = prima.zone.get(d.get("zone_src")) or dopo.zone.get(d.get("zone_src")) or {}
                z_dst = dopo.zone.get(d.get("zone_dest")) or prima.zone.get(d.get("zone_dest")) or {}
                prop = (o.get("ownerSeatId") or z_src.get("ownerSeatId") or z_dst.get("ownerSeatId") or 0) - 1   # nascosta: dalla zona
                nome, tipo_c = carta_di(_nome(o), o)
                conta = cat == "CastSpell" or (da, verso) in (("grimorio", "mano"), ("campo", "cimitero"), ("grimorio", "cimitero"), ("mano", "cimitero"))
                if conta and prop < 0: raise Saltato("un cambio di zona nel log di cui non si sa di chi e' la carta")
                if cat == "CastSpell":
                    out.append((tn, {"tipo": "lanciata", "giocatore": (o.get("controllerSeatId") or o.get("ownerSeatId")) - 1,
                                     "carta": (nome, tipo_c, prop), "causa": "601.2i"}))
                    continue
                causa = {"Draw": "121.1", "Discard": "701.9a", "Mill": "701.17a", "Surveil": "701.25a"}.get(cat, "log " + str(cat))
                if (da, verso) in (("grimorio", "mano"), ("campo", "cimitero"), ("grimorio", "cimitero"), ("mano", "cimitero")):
                    out.append((tn, {"tipo": "zona", "da": da, "a": verso, "giocatore": prop, "causa": causa, "carta": (nome, tipo_c, prop)}))
                if cat == "Surveil": out.append((tn, {"tipo": "guarda", "giocatore": prop, "a": "surveil", "causa": "701.25a"}))
            elif tipo == "AnnotationType_Scry":
                x = dopo.obj.get(a.get("affectorId")) or prima.obj.get(a.get("affectorId")) or {}
                chi = x.get("controllerSeatId")
                if chi is None:
                    lib = [z for z in list(dopo.zone.values()) + list(prima.zone.values()) if z["type"] == "ZoneType_Library"
                           and set(a.get("affectedIds", [])) & set(z.get("objectInstanceIds", []))]
                    chi = lib[0].get("ownerSeatId") if lib else None
                if chi is None: raise Saltato("uno scry nel log di cui non si sa chi l'ha fatto")
                out.append((tn, {"tipo": "guarda", "giocatore": chi - 1, "a": "scry", "causa": "701.22a"}))
            elif tipo == "AnnotationType_MultistepEffectStarted" and d.get("SubCategory") == 11:      # 701.25a: un surveil (anche
                x = dopo.obj.get(a.get("affectorId")) or prima.obj.get(a.get("affectorId")) or {}    # con la carta lasciata sopra:
                if x.get("controllerSeatId") is None: raise Saltato("un surveil nel log di cui non si sa chi l'ha fatto")   # niente ZoneTransfer)
                out.append((tn, {"tipo": "guarda", "giocatore": x["controllerSeatId"] - 1, "a": "surveil", "causa": "701.25a"}))
            elif tipo == "AnnotationType_ModifiedLife":
                for x in a.get("affectedIds", []):
                    if x in (1, 2): out.append((tn, {"tipo": "vite", "giocatore": x - 1, "quanto": d.get("life", 0), "causa": "119.3"}))
            elif tipo == "AnnotationType_DamageDealt":
                for x in a.get("affectedIds", []):
                    if x in (1, 2): out.append((tn, {"tipo": "danno", "giocatore": x - 1, "quanto": d.get("damage", 0), "a": f"G{x}",
                                                     "causa": "510.2" if d.get("type") == 1 else "120.3"}))
            elif tipo == "AnnotationType_UserActionTaken" and d.get("actionType") == 2:
                ab = dopo.obj.get((a.get("affectedIds") or [None])[0]) or {}
                src = dopo.obj.get(ab.get("parentId")) or prima.obj.get(ab.get("parentId")) or {}
                if "CardType_Planeswalker" in src.get("cardTypes", []):                            # 606: le attivate di un planeswalker
                    out.append((tn, {"tipo": "attivata", "a": "fedelta", "giocatore": a.get("affectorId") - 1, "causa": "606.4"}))
    for a in st.pann.values():                                                                     # chi e' entrato in campo in questo turno
        if "AnnotationType_EnteredZoneThisTurn" in a["type"] and st.tipo_zona(a.get("affectorId")) == "ZoneType_Battlefield":
            for x in a.get("affectedIds", []): out.append((N, {"tipo": "zona", "da": "log", "a": "campo", "nuovo_iid": x, "causa": "log"}))
    for o in st.in_zona("ZoneType_Battlefield"):                                                   # chi attacca (508.1k)
        if o.get("attackState") in ("AttackState_Declared", "AttackState_Attacking"):
            out.append((N, {"tipo": "attacca", "vecchio_iid": o["instanceId"], "giocatore": attivo - 1, "causa": "508.1k"}))
    campo = {o["instanceId"] for o in st.in_zona("ZoneType_Battlefield")}
    for _, dopo, ann in seq[:fine]:                                                                 # chi ha gia' fatto danno da combattimento
        for a in ann:                                                                              # (Ruric Thar, Magecrusher: in tutta la partita)
            if a["type"][0] == "AnnotationType_DamageDealt" and R.dettagli(a).get("type") == 1 and a.get("affectorId") in campo:
                out.append((N - 1, {"tipo": "danno", "vecchio_iid": a["affectorId"], "causa": "510.2", "quanto": R.dettagli(a).get("damage", 0)}))
    return out


_PEDINE, _PREPARATE = None, None


def magie_preparate():
    """723.3: i nomi delle magie che i permanenti di FRA preparano (la seconda faccia, «prepara» del testo letto)."""
    global _PREPARATE
    if _PREPARATE is None: _PREPARATE = {t.voce[2]["prepara"][0] for t in set(F.tutte().values()) if t.voce[2].get("prepara")}
    return _PREPARATE


def definizioni_pedine():
    """Le pedine che le carte di FRA creano, dal loro testo letto (le istruzioni «pedina» di carte_fra): nome -> istruzione."""
    global _PEDINE
    if _PEDINE is not None: return _PEDINE
    _PEDINE = {}
    def giro(x):
        if isinstance(x, dict):
            if x.get("fa") == "pedina" and x.get("nome"): _PEDINE.setdefault(x["nome"], x)
            for v in x.values(): giro(v)
        elif isinstance(x, (list, tuple)):
            for v in x: giro(v)
    for t in set(F.tutte().values()): giro(t.voce[2])
    return _PEDINE


def pedina_di(nome, o):
    """La pedina in campo nel log -> (nome, tipo, car) del motore: il Jace (701.71a) o una pedina che le carte di FRA
    creano, con le caratteristiche dell'istruzione (111.2-111.4)."""
    if nome == "Jace" and "SubType_Jace" in o.get("subtypes", []): return ("Jace", "Token Planeswalker — Jace", dict(E.JACE))
    d = definizioni_pedine().get(nome)
    if d is None: raise Saltato(f"pedina {nome}: nessuna carta di FRA la crea nel motore")
    car = {k: v for k, v in d.items() if k in ("forza", "costituzione", "parole", "abilita", "mana", "colori", "fedelta", "mana_sacrifica")}
    return (d["nome"], d["tipo"], car)


def tipo_scelta(prima, dopo, io, avv):
    """Il passaggio da uno stato all'altro apre una scelta di Autore? -> (tipo, stato da leggere, fase, passo) o None."""
    tu, tp = dopo.turno, prima.turno
    if (tu.get("turnNumber"), tu.get("phase"), tu.get("step")) == (tp.get("turnNumber"), tp.get("phase"), tp.get("step")): return None
    att = tu.get("activePlayer")
    if tu.get("phase") == "Phase_Main1" and att == io: return "agisci", dopo, "principale_1", None
    if tu.get("step") == "Step_DeclareAttack" and att == io: return "attacca", prima, "combattimento", "attaccanti"
    if tu.get("step") == "Step_DeclareBlock" and att == avv: return "blocca", prima, "combattimento", "bloccanti"
    return None


def punti(gid, path, mazzo_vero):
    """I punti di scelta di una partita. -> (lista di punti, conti dei saltati)."""
    return punti_seq(list(R.messaggi(path)), gid, mazzo_vero)


def punti_seq(seq, gid, mazzo_vero, da=1, risposta=None, vivo=False):
    """I punti di scelta da una sequenza di messaggi. da: il primo messaggio che conta (dal vivo l'ultimo arrivato: la
    sequenza finisce li' e il mazzo modello conosce solo quello che l'avversario ha mostrato fin qui). risposta: la mossa
    da mettere nel punto al posto di quella del log (dal vivo: tipo -> la proposta della spalla). vivo: copre anche gli effetti
    temporanei, l'avversario senza terre mostrate e le sue magie di altri set: il confronto dell'8.3 resta com'e'."""
    io = mio_posto(seq)
    if io is None: return [], Counter({"posto di Autore non trovato": 1})
    avv = 3 - io
    chi = _chi_comincia(seq)
    saltati = Counter()
    try: modello, info = mazzo_modello(seq, avv, gid, senza_terre=vivo)
    except Saltato as e: return [], Counter({str(e): 1})
    bers = _bersagli_log(seq)
    out = []
    terre = Counter()                                                                              # (turno, posto) -> terre giocate
    for k in range(1, len(seq)):
        prima, dopo, ann = seq[k]
        for a in ann:
            if a["type"][0] == "AnnotationType_UserActionTaken" and R.dettagli(a).get("actionType") == 3:
                terre[(dopo.turno.get("turnNumber"), a.get("affectorId"))] += 1
        if k < da: continue
        sc = tipo_scelta(prima, dopo, io, avv)
        if sc is None: continue
        tipo, st, fase, passo = sc
        tu, att = dopo.turno, dopo.turno.get("activePlayer")
        n_turno = tu.get("turnNumber")
        raccolti = [] if vivo else None
        try:
            if risposta is not None: mossa = risposta(tipo)
            elif tipo == "agisci": mossa = _risposta_agisci(seq, k, io, bers)
            elif tipo == "attacca": mossa = _risposta_attacca(seq, k, io)
            else: mossa = _risposta_blocca(seq, k, io)
            d = descrivi_stato(st, io, avv, chi, n_turno, att, fase, passo, mazzo_vero["mazzo"], mazzo_vero["sideboard"], modello, effetti=raccolti)
            if vivo: d["temporanei"] = durate_effetti(seq, k, raccolti, n_turno)
            d["storia"] = storia(seq, k + 1 if st is dopo else k, n_turno, att, st)
            d["terre_giocate"] = terre[(n_turno, att)] if tipo != "agisci" else 0
        except Saltato as e:
            saltati[f"{tipo}: {e}"] += 1
            continue
        d.update(gid=gid, k=k, tipo=tipo, risposta=mossa, modello=info, seme=(hash_stabile(gid) + 7919 * k) % (2 ** 31))
        out.append(d)
    return out, saltati


def tutti_i_punti(solo=None):
    mazzi = S.mazzi_veri()
    di = {g: m for m in mazzi for g in (m["partite"] if isinstance(m["partite"], list) else [])}
    out, saltati = [], Counter()
    for gid, path in R.partite():
        if solo and gid not in solo: continue
        if gid not in di:                         # una partita nuova (16 ott 2026): il mazzo dal suo log, senza toccare
            try:                                  # mazzi_veri.json (i 10 mazzi delle simulazioni: l'ordine decide i semi)
                mz, sb = S.mazzo_dal_log(path, gid)
                F.mazzo(mz); F.mazzo(sb)          # NonCoperto se una carta non e' intera
                di[gid] = {"mazzo": mz, "sideboard": sb, "partite": [gid]}
            except Exception as e:
                saltati[f"partita senza mazzo leggibile: {type(e).__name__}"] += 1
                continue
        p, s = punti(gid, path, di[gid])
        out += p
        saltati += s
    return out, saltati


# ====================================================================== 2. lo stato rifatto col motore
class DalLog:
    """Il gancio `prepara` di simula.partita: dopo l'inizio, il tavolo diventa quello del log (dati semplici, si passa ai
    processi delle partite di prova). Le carte fisiche vengono dai mazzi della partita; le azioni del turno che il log ha
    gia' fatto non si rifanno (Riparti)."""

    def __init__(self, punto):
        self.d = punto

    def __call__(self, p):
        d, t = self.d, p.t
        for g in t.giocatori:                                                                      # tutto nel grimorio
            for o in list(g.mano): t.sposta(o, "grimorio", posizione="fondo", causa="prova")
        mappa = {}
        def prendi(j, nome):
            o = next((o for o in t.giocatori[j].grimorio.carte if o.nome == nome), None)
            if o is None: raise Saltato(f"{nome}: non c'e' nel grimorio di G{j + 1} (mazzo della partita)")
            t._togli(o)
            return o
        campo = [x for x in d["oggetti"] if x["zona"] == "campo"]
        campo.sort(key=lambda x: x.get("attaccato_a") is not None)                                # prima chi non e' attaccato
        for x in campo:
            if x["pedina"] is not None:
                nome, tipo, car = x["pedina"]
                o = t.crea_pedina(x["controllore"], nome, tipo, causa="prova", car=dict(car))
            else:
                o = prendi(x["proprietario"], x["nome"])
                o = t._arriva(o, "grimorio", "mano", None, None, "prova")
                o = t.metti_in_campo(o, chi=x["controllore"], causa="prova")
            mappa[x["iid"]] = o
        for x in d["oggetti"]:
            if x["zona"] in ("cimitero", "esilio") and not x.get("preparata"):
                o = prendi(x["proprietario"], x["nome"])
                mappa[x["iid"]] = t._arriva(o, "grimorio", x["zona"], None, None, "prova")
        mie = d["mani"][d["io"]]
        for nome in mie: t._arriva(prendi(d["io"], nome), "grimorio", "mano", None, None, "prova")
        avv = 1 - d["io"]
        g = t.giocatori[avv]
        for _ in range(d["mani"][avv]):
            o = g.grimorio.carte[0]
            t._togli(o)
            t._arriva(o, "grimorio", "mano", None, None, "prova")
        p.in_attesa.clear()
        N = d["turno"]
        for x in campo:                                                                            # lo stato di ogni permanente
            o = mappa[x["iid"]]
            o.tappato, o.danno = x["tappato"], x["danno"]
            o.segnalini.clear()
            for k_, n_ in x["segnalini"].items(): o.segnalini[k_] = n_                           # 122.1: tutte le carte sono intere
            if "planeswalker" in o.carta.tipi and "fedelta" not in x["segnalini"]: o.segnalini["fedelta"] = 0
            o.controllo_dal = N if x["malato"] else -5                                             # 302.6
            if x["fedelta_usata"]: p.fedelta_usate.add((o.n, N))                                   # 606.3
        copie = Counter((y["controllore"], y["nome"]) for y in d["oggetti"] if y.get("preparata"))  # 723.3c: le copie in esilio
        for x in campo:                                                                            # dicono chi e' preparato
            o = mappa[x["iid"]]
            spell = o.carta.car.get("prepara")
            if not spell: continue
            vuole = copie[(x["controllore"], spell[0])] > 0
            if vuole: copie[(x["controllore"], spell[0])] -= 1
            if vuole and not getattr(o, "preparato", False): t.prepara(o, causa="prova")
            if not vuole and getattr(o, "preparato", False):
                o.preparato = False
                for y in [y for y in t.esilio if y.carta.car.get("copia_di") == o.n]:
                    t.esilio.remove(y); y.vivo = False
        if any(v > 0 for v in copie.values()): raise Saltato("una magia preparata in esilio senza il permanente che la prepara")
        for x in campo:
            if x.get("attaccato_a") is not None and x["attaccato_a"] in mappa:
                mappa[x["iid"]].attaccato_a = mappa[x["attaccato_a"]].n
        for i_, v in enumerate(d["vite"]): t.giocatori[i_].vite = v
        for x in campo:
            o = mappa[x["iid"]]
            if o.carta.car.get("mana_colore_scelto"):                                              # 105.4: il colore scelto entrando
                col = [c for c in x.get("colori") or [] if c]
                if len(col) != 1: raise Saltato(f"{x['nome']}: il colore scelto non si legge dal log")
                o.colore_scelto = col[0]
            if x.get("una_volta_usata"):                                                           # 603.1a: gia' innescata in questo turno
                ks = [k_ for k_, ab in t.abilita_di(o) if ab.get("una_volta_per_turno")]
                if len(ks) != 1: raise Saltato(f"{x['nome']}: l'abilita' «una volta per turno» usata non si sa quale")
                p.una_volta.add((o.n, ks[0], N))
            for y in x.get("sotto") or []:                                                         # 610.3: esiliata finche' la fonte resta
                if y not in mappa: raise Saltato(f"{x['nome']}: la carta esiliata sotto non e' nel tavolo rifatto")
                t.legami.setdefault(o.n, []).append(mappa[y])
        t.turno_numero = N - 1
        t.primo = d["primo"]
        storia_in(t, mappa, [e for tn, e in d.get("storia") or [] if tn == N - 1], N - 1, 1 - d["attivo"])
        p.attivo = d["attivo"]
        p.inizio_turno[1 - d["attivo"]] = N - 1 if N > 1 else None
        t._conta_bassi()
        t._versione += 1
        attacco = None
        if d["passo"] == "bloccanti":
            attacco = {}
            for a_, b_ in d["attacchi"].items():
                if a_ not in mappa: raise Saltato("un attaccante del log non e' nel tavolo rifatto")
                attacco[mappa[a_]] = (b_ - 1) if b_ in (1, 2) else mappa.get(b_)
        for x in campo:                                                                            # dal vivo: gli effetti in corso (611.2),
            if x["iid"] not in (d.get("temporanei") or {}) or x["forza"] is None: continue         # dai numeri del log; verifica li controlla
            o, durata = mappa[x["iid"]], d["temporanei"][x["iid"]]
            v = t.caratteristiche(o)
            dp, dt = x["forza"] - v["forza"], x["costituzione"] - v["costituzione"]
            if dp or dt: t.aggiungi_continuo("7c", {"p": dp, "t": dt}, chi=frozenset({o.n}), durata=durata)
            manca = sorted(set(x["parole"]) - set(v["parole"]))
            if manca: t.aggiungi_continuo("6", {"dai": manca}, chi=frozenset({o.n}), durata=durata)
        p._dal_log = mappa
        p._riparti = (d["fase"], d["passo"], d["terre_giocate"], attacco, [e for tn, e in d.get("storia") or [] if tn == N])


def storia_in(t, mappa, eventi, turno, chi):
    """Gli eventi della storia nel registro del motore, senza farli passare dagli inneschi (sono gia' successi: il log li
    ha risolti): un «turno» se serve, poi gli eventi. Le carte di passaggio sono pezzi nuovi, fuori da ogni zona."""
    from tavolo import Carta, Evento
    if turno is not None and turno >= 1:
        ev = Evento(next(t._eventi), "turno", giocatore=chi, quanto=turno, causa="500.1")
        ev.storia = True
        t.eventi.append(ev)
    for e in eventi:
        e = dict(e)
        if "carta" in e:
            nome, tipo, prop = e["carta"]
            e["carta"] = Carta(next(t._carte), nome, tipo, prop)
        if "nuovo_iid" in e:
            o = mappa.get(e.pop("nuovo_iid"))
            if o is None: continue                                                                  # entrato e poi uscito: non conta piu'
            e["nuovo"] = o.n
        if "vecchio_iid" in e:
            o = mappa.get(e.pop("vecchio_iid"))
            if o is None: continue
            e["vecchio"] = o.n
        if e.get("da") == "log": e["da"] = None
        ev = Evento(next(t._eventi), **e)
        ev.storia = True                                                                           # tavolo.controlla: non e' un cambio di zona qui
        t.eventi.append(ev)
    t._versione += 1


class Riparti(E.Partita):
    """La partita del passo 7 che riparte a meta' turno: il primo turno comincia dal passo del punto di scelta (fase,
    passo) senza rifare le azioni dei passi prima (gia' fatte nel log: stap, pescata, 502.3, 504.1); per i bloccanti gli
    attaccanti del log sono gia' dichiarati (508.1k: non si rifanno gli inneschi d'attacco, gia' risolti nel log)."""

    _riparti = None

    def turno(self, giocatori):
        r = self._riparti
        if r is None: return super().turno(giocatori)
        self._riparti = None
        fase0, passo0, terre, attacco, storia_ora = r
        t, i = self.t, self.attivo
        self.ultimo, self.chi = i, giocatori
        t.turno_numero += 1
        self.inizio_turno[i] = t.turno_numero
        t.giocatori[i].terre_giocate = terre
        t._evento("turno", giocatore=i, quanto=t.turno_numero, causa="500.1")
        storia_in(t, self._dal_log, storia_ora, None, None)                                        # quello che il log ha gia' fatto in questo turno
        nomi = [f for f, _ in FASI]
        saltando = True
        for fase, passi in FASI:
            if nomi.index(fase) < nomi.index(fase0): continue
            for passo in self._passi(fase, passi, i):
                if t.finita: return
                if saltando:
                    if (fase, passo) != (fase0, passo0):
                        if fase == "combattimento" and passo == "attaccanti" and attacco is not None: self._metti_attacco(i, attacco)
                        continue
                    saltando = False
                self.fase, self.passo = fase, passo
                t._evento("passo", giocatore=i, da=fase, a=passo or "", causa="500.1")
                self._azioni_del_turno(i, passo, giocatori)
                if passo not in SENZA_PRIORITA: self._priorita_del_passo(giocatori)
                if passo is not None: self._svuota_mana()
            if not saltando: self._svuota_mana()
        self.fase = self.passo = None
        self.attivo = (i + 1) % len(t.giocatori)

    def _metti_attacco(self, i, attacco):
        """508.1k: gli attaccanti del log, gia' dichiarati, tappati (lo dice il log) e in combattimento."""
        for o, b in attacco.items():
            if b is None: raise Saltato("l'attaccante del log attacca qualcosa che il tavolo rifatto non ha")
            self.attaccanti[o], self._ctrl[o] = b, o.controllore
            if not G.E._e_giocatore(b): self._ctrl[b] = b.controllore
        self.dichiarati = len(attacco)


def verifica(p, d):
    """Il tavolo del motore e' quello del log? -> None, o la prima differenza."""
    t, mappa = p.t, p._dal_log
    for i_, g in enumerate(t.giocatori):
        if g.vite != d["vite"][i_]: return f"vite di G{i_ + 1}: motore {g.vite}, log {d['vite'][i_]}"
        mano = d["mani"][i_]
        if len(g.mano) != (len(mano) if isinstance(mano, list) else mano): return f"mano di G{i_ + 1}: {len(g.mano)} contro {mano}"
        if len(g.grimorio.carte) != d["grimori"][i_]: return f"grimorio di G{i_ + 1}: {len(g.grimorio.carte)} contro {d['grimori'][i_]}"
        n_log = sum(1 for x in d["oggetti"] if x["zona"] == "cimitero" and x["proprietario"] == i_)
        if len(g.cimitero) != n_log: return f"cimitero di G{i_ + 1}: {len(g.cimitero)} contro {n_log}"
    n_es = sum(1 for x in d["oggetti"] if x["zona"] == "esilio")
    if len(t.esilio) != n_es: return f"esilio: {len(t.esilio)} nel motore, {n_es} nel log"
    n_campo = sum(1 for x in d["oggetti"] if x["zona"] == "campo")
    if len(t.campo) != n_campo: return f"campo: {len(t.campo)} permanenti, log {n_campo}"
    for x in d["oggetti"]:
        if x["zona"] != "campo": continue
        o = mappa.get(x["iid"])
        if o is None or not o.vivo or o.zona != "campo": return f"{x['nome']}: non e' in campo nel motore"
        if o.controllore != x["controllore"]: return f"{x['nome']}: controllore"
        if o.tappato != x["tappato"]: return f"{x['nome']}: tappato motore {o.tappato}, log {x['tappato']}"
        if o.danno != x["danno"]: return f"{x['nome']}: danno"
        if "creature" in o.carta.tipi:
            v = t.caratteristiche(o)
            if (v["forza"], v["costituzione"]) != (x["forza"], x["costituzione"]):
                return f"{x['nome']}: motore {v['forza']}/{v['costituzione']}, log {x['forza']}/{x['costituzione']} (613)"
            pm = set(v["parole"]) & set(PAROLE)
            if pm != set(x["parole"]): return f"{x['nome']}: parole chiave motore {sorted(pm)}, log {x['parole']}"
        elif x["forza"] is not None: return f"{x['nome']}: creatura nel log, non nel motore"
    return None


# ====================================================================== 3. la mossa vera di Autore, scritta per il motore
def mossa_vera(p, i, d):
    """La risposta di Autore nel log -> la mossa per il motore (la stessa forma delle candidate del Cercatore), o
    Saltato se il motore non la sa scrivere. Il motore la deve dire legale: se no e' una DISCORDANZA (Saltato con
    «DISCORDE»), da guardare come nel riscontro (prima la lettura del log, poi il motore)."""
    r, mappa, t = d["risposta"], p._dal_log, p.t
    def ogg(iid):
        if iid in (1, 2): return iid - 1
        o = mappa.get(iid)
        if o is None: raise Saltato(f"il bersaglio {iid} del log non e' nel tavolo rifatto")
        return o
    if d["tipo"] == "agisci":
        if r[0] == "passa": return None
        if r[0] == "terra":
            o = next((o for o in t.giocatori[i].mano if o.nome == r[1]), None)
            if o is None: raise Saltato(f"DISCORDE: la terra {r[1]} non e' in mano nel motore")
            if not p.puo_giocare_terra(i, o): raise Saltato(f"DISCORDE: il motore dice che {r[1]} non si gioca (305)")
            return ("terra", o)
        if r[0] == "lancia":
            _, nome, zona, ber = r
            dove = {"mano": t.giocatori[i].mano, "cimitero": t.giocatori[i].cimitero, "esilio": t.esilio}.get(zona)
            if dove is None: raise Saltato(f"lancio da {zona}")
            o = next((o for o in dove if o.nome == nome), None)
            if o is None: raise Saltato(f"DISCORDE: {nome} non e' in {zona} nel motore")
            car = o.carta.car
            if "{X}" in (car.get("costo") or ""): raise Saltato(f"{nome}: la X scelta non si legge dal log")
            if car.get("modi"): raise Saltato(f"{nome}: magia modale (il modo scelto non si scrive come mossa)")
            if not p.puo_lanciare(i, o, 0): raise Saltato(f"DISCORDE: il motore dice che {nome} non si lancia adesso")
            reqs = car.get("bersagli") or []
            if not reqs and not ber: return ("lancia", o, 0, None)
            if car.get("incanta"): raise Saltato(f"{nome}: aura (il bersaglio dell'aura non si scrive come mossa)")
            if len(reqs) != len(ber): raise Saltato(f"{nome}: {len(reqs)} bersagli nel motore, {len(ber)} nel log")
            gruppi = [[ogg(x) for x in ber[k_]] for k_ in sorted(ber)]
            for req, gr in zip(reqs, gruppi):
                legali = list(p.candidati(req, i, None, o))
                for x in gr:
                    if x not in legali: raise Saltato(f"DISCORDE: {nome}, il bersaglio del log non e' legale per il motore (115)")
            return ("lancia", o, 0, None, gruppi)
        if r[0] == "attiva":
            _, nome, ab_grp, pid, ber, delta = r
            o = mappa.get(pid)
            if o is None: raise Saltato(f"abilita' di {nome}: la sorgente non e' in campo nel tavolo rifatto")
            att = [k_ for k_, ab in t.abilita_di(o) if ab.get("tipo") == "attivata" and not all(x.get("fa") == "aggiungi_mana" for x in ab.get("fa") or [])]
            ab_ = dict(t.abilita_di(o))
            if len(att) > 1 and all("fedelta" in ab_[k_] for k_ in att):                           # 606.4: quella del costo pagato nel log
                att = [k_ for k_ in att if ab_[k_]["fedelta"] == delta]
            if len(att) != 1: raise Saltato(f"abilita' di {nome}: {len(att)} attivate nel motore, non si sa quale")
            ab = dict(t.abilita_di(o))[att[0]]
            if ab.get("bersagli") or ber: raise Saltato(f"abilita' di {nome} con bersagli")
            if isinstance(ab.get("fedelta"), str) or "{X}" in json.dumps(ab.get("costo", "")): raise Saltato(f"abilita' di {nome} con X")
            if not p.puo_attivare(i, o, att[0]): raise Saltato(f"DISCORDE: il motore dice che l'abilita' di {nome} non si attiva adesso")
            return ("attiva", o, att[0])
    if d["tipo"] == "attacca":
        out = {}
        for a_, b_ in r.items():
            o = mappa.get(a_)
            if o is None: raise Saltato("un attaccante di Autore non e' nel tavolo rifatto")
            out[o] = ogg(b_) if b_ is not None else p.difensore()
        dich, motivo = p._leggi_attacco(i, out)
        if dich is None: raise Saltato(f"DISCORDE: l'attacco di Autore e' illegale per il motore ({motivo})")
        return out
    if d["tipo"] == "blocca":
        out = {}
        for b_, att in r.items():
            if len(att) != 1: raise Saltato("un bloccante che blocca piu' attaccanti")
            o, a = mappa.get(b_), mappa.get(att[0])
            if o is None or a is None: raise Saltato("un bloccante o un attaccante non e' nel tavolo rifatto")
            out[o] = a
        dich, motivo = p._leggi_blocco(p.difensore(), out)
        if dich is None: raise Saltato(f"DISCORDE: il blocco di Autore e' illegale per il motore ({motivo})")
        return out
    raise Saltato(f"tipo {d['tipo']}")


def scrivi_mossa(m, gancio):
    """Una mossa leggibile."""
    if gancio == "agisci":
        if m is None: return "passa"
        if m[0] == "terra": return f"terra {m[1].nome}"
        if m[0] == "lancia":
            s = f"lancia {m[1].nome}"
            if len(m) > 4 and m[4]: s += " -> " + ", ".join(("G%d" % (x + 1)) if isinstance(x, int) else x.nome for g in m[4] for x in g)
            return s
        if m[0] == "attiva": return f"attiva {m[1].nome}"
    if gancio == "attacca":
        return "attacca con " + (", ".join(sorted(o.nome for o in m)) if m else "nessuno")
    if gancio == "blocca":
        return "blocca " + (", ".join(sorted(f"{a.nome} con {b.nome}" for b, a in m.items())) if m else "nessuno")
    return repr(m)


# ====================================================================== 4. il Cercatore al punto di scelta
class CercatoreLog(G.Cercatore):
    """Il Cercatore del passo 8.2 al punto di scelta del log: controlla lo stato (verifica), aggiunge alle sue candidate la
    mossa vera di Autore, le prova tutte negli stessi mondi, e ferma la partita (Fermo). Tiene gli esiti mondo per mondo."""

    def __init__(self, punto, **kw):
        super().__init__(**kw)
        self.punto, self.extra, self.esito = punto, None, None

    def _al_punto(self, gancio, p, i, fai):
        if self.esito is not None or gancio != self.punto["tipo"]: return fai()
        perche = verifica(p, self.punto)
        if perche: raise Saltato("stato non rifatto: " + perche)
        vera = mossa_vera(p, i, self.punto)
        self.extra = (vera,)
        self._cand, self._mondi_esiti = None, None
        scelta = fai()
        cand = self._cand or [(scelta, None)]
        codici = [json.dumps(c, sort_keys=True, default=str) for _, c in cand]
        cv = json.dumps(G.codifica(vera, G._indice(self._args)), sort_keys=True, default=str) if self._cand else None
        f_idx = codici.index(cv) if cv in codici else 0
        sc = next(j for j, (m, _) in enumerate(cand) if m is scelta) if self._cand else 0
        self.esito = {"candidate": [scrivi_mossa(m, gancio) for m, _ in cand], "codici": [c for _, c in cand],
                      "punti": list(self._punti) if self._mondi_esiti else None, "autore": f_idx, "cercatore": sc,
                      "esiti": self._mondi_esiti, "prefisso": self.contesto[4][:-1] if self._mondi_esiti else None}
        raise Fermo()

    def _codificate(self, mosse, args):
        cand = super()._codificate(mosse, args)
        if self.extra is not None:
            viste = {json.dumps(c, sort_keys=True, default=str) for _, c in cand}
            for m in self.extra:
                c = G.codifica(m, G._indice(args))
                if json.dumps(c, sort_keys=True, default=str) not in viste: cand.append((m, c))
            self._cand, self._args = cand, args
        return cand

    def _scegli(self, nome, cand):
        a, b, seme, i, nastro, kw = self.contesto
        k = len(nastro) - 1
        prefisso = nastro[:k]
        if any(v is None for v in prefisso): raise Saltato("dentro un'altra chiamata (il nastro ha una voce aperta)")
        mondi = [int(x) for x in np.random.default_rng([self.seme, k, 8202]).integers(0, 2 ** 63 - 1, size=self.prove)]
        lavori = [(a, b, seme, prefisso, i, nome, c, m, self.baro, self.kw_prova(kw)) for _, c in cand for m in mondi]
        esiti = self.pool.map(G._lavoro, lavori, chunksize=1) if self.pool else [G._lavoro(x) for x in lavori]
        self._mondi_esiti = [esiti[j * len(mondi):(j + 1) * len(mondi)] for j in range(len(cand))]
        self._punti = [sum(e) for e in self._mondi_esiti]
        migliore = max(range(len(cand)), key=lambda j: (self._punti[j], -j))
        self.diario.append((nome, k, [c for _, c in cand], self._punti, migliore))
        return cand[migliore][0]

    def agisci(self, p, i): return self._al_punto("agisci", p, i, lambda: super(CercatoreLog, self).agisci(p, i))
    def attacca(self, p, i): return self._al_punto("attacca", p, i, lambda: super(CercatoreLog, self).attacca(p, i))
    def blocca(self, p, i): return self._al_punto("blocca", p, i, lambda: super(CercatoreLog, self).blocca(p, i))


def _mazzi(d):
    return ({"nome": "G1", "mazzo": d["mazzi"][0], "sideboard": d["sideboard"][0]},
            {"nome": "G2", "mazzo": d["mazzi"][1], "sideboard": d["sideboard"][1]})


def al_punto(d, prove=12, pool=None, seme=None, turni=None, valuta="v0"):
    """Il Cercatore al punto d. -> l'esito (dict) o Saltato. turni = K: le partite di prova troncate (passo 8.5); valuta: la
    versione della valutazione che le giudica (passo 8.6)."""
    a, b = _mazzi(d)
    io = d["io"]
    c = CercatoreLog(d, seme=seme if seme is not None else d["seme"], prove=prove, pool=pool, turni=turni,
                     **({} if valuta == "v0" else {"valuta": valuta}))
    g = [c, S.Semplice(d["seme"] + 1)] if io == 0 else [S.Semplice(d["seme"] + 1), c]
    kw = {"prepara": DalLog(d), "P": Riparti}
    try:
        G.registra(a, b, d["seme"], g[0], g[1], **kw)
    except Fermo:
        return c.esito, (a, b, kw)
    raise Saltato("la partita non e' arrivata al punto di scelta")


def conferma(d, esito, contesto, prove=24, pool=None, turni=None):
    """La mossa di Autore e quella del Cercatore rigiocate in mondi NUOVI (non quelli che hanno scelto: la scelta fatta
    coi mondi di prima premia la candidata fortunata). -> (vinte da Autore, vinte dal Cercatore, coppie in cui vince
    solo il Cercatore, coppie in cui vince solo Autore)."""
    a, b, kw = contesto
    pref, i = esito["prefisso"], d["io"]
    cf, cc = esito["codici"][esito["autore"]], esito["codici"][esito["cercatore"]]
    mondi = [int(x) for x in np.random.default_rng([d["seme"], 8305]).integers(0, 2 ** 63 - 1, size=prove)]
    kw = kw if turni is None else {**kw, "turni": turni}
    lavori = [(a, b, d["seme"], pref, i, d["tipo"], c, m, False, kw) for c in (cf, cc) for m in mondi]
    es = pool.map(G._lavoro, lavori, chunksize=1) if pool else [G._lavoro(x) for x in lavori]
    ef, ec = es[:prove], es[prove:]
    return sum(ef), sum(ec), sum(1 for x, y in zip(ef, ec) if y > x), sum(1 for x, y in zip(ef, ec) if x > y)


def segni(n_piu, n_meno):
    """Il test dei segni a due code: p del conteggio piu' sbilanciato fra n_piu e n_meno (le pari non contano)."""
    n, k = n_piu + n_meno, max(n_piu, n_meno)
    if n == 0: return 1.0
    return min(1.0, 2 * sum(math.comb(n, j) for j in range(k, n + 1)) / 2 ** n)


# ====================================================================== 5. la spazzata e il confronto
class Vera(S.Semplice):
    """Il giocatore della spazzata: al punto di scelta gioca la mossa vera di Autore (dopo la verifica), poi il Semplice."""

    def __init__(self, punto, seme=0):
        super().__init__(seme)
        self.punto, self.fatto = punto, False

    def _al_punto(self, gancio, p, i, base):
        if self.fatto or gancio != self.punto["tipo"]: return base()
        self.fatto = True
        perche = verifica(p, self.punto)
        if perche: raise Saltato("stato non rifatto: " + perche)
        return mossa_vera(p, i, self.punto)

    def agisci(self, p, i): return self._al_punto("agisci", p, i, lambda: super(Vera, self).agisci(p, i))
    def attacca(self, p, i): return self._al_punto("attacca", p, i, lambda: super(Vera, self).attacca(p, i))
    def blocca(self, p, i): return self._al_punto("blocca", p, i, lambda: super(Vera, self).blocca(p, i))


def gioca_vera(d):
    """Il punto rifatto e la partita giocata fino alla fine con la mossa vera, arbitro acceso. -> (esito, None) o (None, perche')."""
    a, b = _mazzi(d)
    io = d["io"]
    v = Vera(d, d["seme"] + 2)
    g = [v, S.Semplice(d["seme"] + 1)] if io == 0 else [S.Semplice(d["seme"] + 1), v]
    try:
        p = S.partita(a, b, d["seme"], g[0], g[1], prepara=DalLog(d), P=Riparti)
    except Saltato as e: return None, str(e)
    except S.ArbitroFischia as e: return None, "FISCHIO: " + str(e)
    except E.NonCoperto as e: return None, "NonCoperto: " + str(e)
    if not v.fatto: return None, "la partita non e' arrivata al punto di scelta"
    return G.esito(p, io), None


def _lavoro_spazzata(d):
    try: return gioca_vera(d)
    except Exception as e: return None, f"ECCEZIONE {type(e).__name__}: {e}"


def spazzata(solo=None):
    t0 = time.time()
    pts, saltati = tutti_i_punti(solo)
    print(f"{len(pts)} punti letti, {sum(saltati.values())} saltati alla lettura ({time.time() - t0:.0f} s)", flush=True)
    pool = G.nuovo_pool()
    try: out = pool.map(_lavoro_spazzata, pts, chunksize=2)
    finally: pool.terminate()
    perche = Counter(_motivo(r[1]) for r in out if r[1])
    ok = sum(1 for r in out if r[1] is None)
    print(f"giocati fino alla fine {ok}/{len(pts)} in {time.time() - t0:.0f} s")
    for m, k in perche.most_common(40): print(f"  {k} x {m}")
    gravi = [r[1] for r in out if r[1] and (r[1].startswith("FISCHIO") or r[1].startswith("ECCEZIONE") or "DISCORDE" in r[1])]
    for g in gravi[:10]: print("  >>", g[:300])
    return pts, out


def _motivo(s):
    import re
    return re.sub(r"\d+", "#", s)[:140]


def _lavoro_punto(arg):
    d, prove = arg
    try:
        esito, ctx = al_punto(d, prove=prove)
        return d, esito, None
    except Saltato as e: return d, None, str(e)
    except S.ArbitroFischia as e: return d, None, "FISCHIO: " + str(e)
    except E.NonCoperto as e: return d, None, "NonCoperto: " + str(e)
    except G.Divergenza as e: return d, None, "DIVERGENZA: " + str(e)


def confronto(prove=12, conferme=24, solo=None, scrivi=True, turni=None, valuta="v0"):
    """Il confronto su tutti i punti: le partite di prova di ogni punto nel pool (un punto alla volta, le candidate in
    parallelo), poi le conferme dove Cercatore e Autore non coincidono."""
    t0 = time.time()
    pts, saltati_lettura = tutti_i_punti(solo)
    pool = G.nuovo_pool()
    risultati, saltati = [], Counter(saltati_lettura)
    try:
        for n, d in enumerate(pts):
            try:
                esito, ctx = al_punto(d, prove=prove, pool=pool, turni=turni, valuta=valuta)
            except Saltato as e:
                saltati[f"{d['tipo']}: {_motivo(str(e))}"] += 1; continue
            except S.ArbitroFischia as e:
                saltati[f"FISCHIO {d['tipo']}"] += 1; print("FISCHIO", d["gid"], d["k"], str(e)[:200], flush=True); continue
            except (E.NonCoperto, G.Divergenza) as e:
                saltati[f"{d['tipo']}: {type(e).__name__} {_motivo(str(e))}"] += 1; continue
            r = {"gid": d["gid"], "k": d["k"], "turno": d["turno"], "tipo": d["tipo"], **{k_: v for k_, v in esito.items() if k_ not in ("prefisso", "codici")}}
            if esito["punti"] is not None and esito["autore"] != esito["cercatore"]:
                # la conferma giudica sempre con le partite intere: con le troncate (primo giro del 15 ott 2026, 01:27)
                # la stessa valutazione che ha scelto giudicava, e il test dei segni su valori continui contava come
                # «netti» 176 punti, differenze piccole ma sistematiche della valutazione, non partite vinte in piu'
                r["conferma"] = conferma(d, esito, ctx, prove=conferme, pool=pool)
            risultati.append(r)
            if n % 20 == 0: print(f"{n + 1}/{len(pts)} punti, {len(risultati)} valutati, {time.time() - t0:.0f} s", flush=True)
    finally:
        pool.terminate()
    if scrivi: rapporto(risultati, saltati, prove, conferme, time.time() - t0, turni=turni, valuta=valuta,
                        comando=f"py -I -X utf8 Motore_Partita/confronto_log.py --confronto {prove}" + (f" --turni {turni}" if turni is not None else "")
                        + (f" --valuta {valuta}" if valuta != "v0" else ""))
    return risultati, saltati


def azioni_della_fase(seq, k, io):
    """Tutte le azioni di Autore nella prima fase principale del turno del punto k, in ordine: [(verbo, nome)]."""
    turno, out = seq[k][1].turno.get("turnNumber"), []
    for j in range(k + 1, len(seq)):
        prima, dopo, ann = seq[j]
        if dopo.turno.get("turnNumber") != turno or dopo.turno.get("phase") != "Phase_Main1": break
        for a in ann:
            if a["type"][0] != "AnnotationType_UserActionTaken" or a.get("affectorId") != io: continue
            t_, ids = R.dettagli(a).get("actionType"), a.get("affectedIds", [])
            if t_ not in (1, 2, 3) or not ids: continue
            o = dopo.obj.get(ids[0]) or prima.obj.get(ids[0]) or {}
            if t_ == 2: o = dopo.obj.get(o.get("parentId")) or prima.obj.get(o.get("parentId")) or {}
            out.append(({1: "lancia", 2: "attiva", 3: "terra"}[t_], _nome(o)))
    return out


def classifica_agisci(ris):
    """Per ogni scelta «agisci» diversa: il Cercatore propone di passare, oppure una mossa che Autore ha fatto DOPO nella
    stessa fase (stesso piano, altro ordine: il confronto misura il Semplice che continua al suo posto, non lui), oppure una
    mossa che Autore in quella fase non ha fatto."""
    paths, seqs = dict(R.partite()), {}
    for r in ris:
        if r["tipo"] != "agisci" or r["punti"] is None or r["autore"] == r["cercatore"]: continue
        if r["gid"] not in seqs: seqs[r["gid"]] = list(R.messaggi(paths[r["gid"]]))
        seq = seqs[r["gid"]]
        az = azioni_della_fase(seq, r["k"], mio_posto(seq))
        m = r["candidate"][r["cercatore"]]
        if m == "passa": r["genere"] = "il Cercatore passa"
        else:
            verbo, nome = m.split(" ", 1)
            r["genere"] = "stesso piano, altro ordine" if (verbo, nome.split(" -> ")[0]) in az[1:] else "una mossa che Autore non ha fatto"
        r["fase_vera"] = ", ".join(f"{v} {n}" for v, n in az) or "niente"


def _riga(r, conferme):
    c = r["conferma"]
    return (f"| {r['gid']} | {r['turno']} | {r['tipo']} | {r['candidate'][r['autore']]} | {r['candidate'][r['cercatore']]} | "
            f"{c[0]:.0f}/{conferme} - {c[1]:.0f}/{conferme} | {c[2]}, {c[3]} | {segni(c[2], c[3]):.3f} |")


def rapporto(ris, saltati, prove, conferme, secondi, comando=None, turni=None, valuta="v0"):
    """Il rapporto del confronto in Confronto_Log_Quick_FRA.md (e i risultati in confronto_log.json). Con le partite di
    prova troncate (passo 8.5) in Confronto_Log_Quick_FRA_Troncate.md e confronto_log_troncate.json: l'esito delle
    partite intere resta."""
    cercate = [r for r in ris if r["punti"] is not None]
    conta = [r for r in cercate if max(r["punti"]) - min(r["punti"]) >= prove / 4]       # la scelta cambia qualcosa
    uguali = [r for r in cercate if r["autore"] == r["cercatore"]]
    diverse = [r for r in cercate if r["autore"] != r["cercatore"]]
    ps = sorted(segni(r["conferma"][2], r["conferma"][3]) for r in diverse)                       # Benjamini-Hochberg al 5%:
    soglia = max([p for i, p in enumerate(ps, 1) if p <= 0.05 * i / len(ps)] or [0.0])          # con centinaia di confronti
    def netto(r, chi):                                                                             # una soglia fissa al 5% ne
        c = r["conferma"]                                                                          # darebbe «netti» una quindicina
        piu, meno = (c[2], c[3]) if chi == "C" else (c[3], c[2])                                   # per puro caso
        return piu > meno and segni(c[2], c[3]) <= soglia
    netti_c = [r for r in diverse if netto(r, "C")]
    netti_f = [r for r in diverse if netto(r, "F")]
    tipi = ("agisci", "attacca", "blocca")
    def per(lst): return ", ".join(f"{t_} {sum(1 for r in lst if r['tipo'] == t_)}" for t_ in tipi)
    scarto = [r["punti"][r["cercatore"]] - r["punti"][r["autore"]] for r in cercate]
    classifica_agisci(ris)
    def generi(lst): return ", ".join(f"{g} {k}" for g, k in Counter(r.get("genere") for r in lst if r["tipo"] == "agisci").most_common())
    combat_c = [r for r in netti_c if r["tipo"] != "agisci"]
    righe = [f"# Il confronto con le partite vere (passo 8.3)\n",
             f"Scritto il {datetime.now().strftime('%Y-%m-%d %H:%M')} da `{comando or f'py -I -X utf8 Motore_Partita/confronto_log.py --confronto {prove}'}`"
             + (f", in {secondi / 60:.0f} minuti" if secondi else "") + ". Le 44 partite di Quick Draft FRA; i punti di scelta di Autore "
             f"(la prima mossa della prima fase principale del suo turno, gli attaccanti, i bloccanti), lo stato rifatto dal log e "
             f"controllato (`verifica`), il Cercatore del passo 8.2 con {prove} partite di prova a candidata e la mossa di Autore fra "
             f"le candidate; dove le due scelte non coincidono, la conferma in {conferme} mondi nuovi (quelli che hanno scelto premiano per "
             f"caso la candidata fortunata) con il test dei segni mondo per mondo.\n",
             "**Cosa sa e cosa non sa il confronto** (il docstring di `confronto_log.py`): il mazzo dell'avversario e' un modello fatto "
             "dalle carte che ha mostrato nella partita, terre a 17 su 40; dopo la mossa le partite le giocano due Semplice fino alla fine; "
             "il punteggio dice se si vince, non quanto presto (con l'avversario a 5 vite e nessun bloccante anche non attaccare vince "
             "lo stesso, al turno dopo). Una simulazione resta una simulazione: l'avversario e' il Semplice, non chi giocava davvero.\n",
             "## In breve\n",
             f"- punti valutati: **{len(ris)}** ({per(ris)}); saltati: {sum(saltati.values())} (sotto, col perche')",
             f"- con piu' di una mossa sensata da provare: {len(cercate)} ({per(cercate)}); quelli in cui la scelta cambia il risultato "
             f"(fra la candidata migliore e la peggiore almeno un quarto delle partite di prova): **{len(conta)}** ({per(conta)})",
             f"- il Cercatore sceglie la stessa mossa di Autore: **{len(uguali)}/{len(cercate)}** ({per(uguali)})",
             f"- scelte diverse: {len(diverse)} ({per(diverse)}); nella conferma su mondi nuovi la mossa del Cercatore vince netto "
             f"(test dei segni con la correzione di Benjamini-Hochberg per i {len(diverse)} confronti, al 5%: p fino a {soglia:.4f}) "
             f"in **{len(netti_c)}** ({per(netti_c)}), quella di Autore in **{len(netti_f)}** "
             f"({per(netti_f)}), le altre {len(diverse) - len(netti_c) - len(netti_f)} non si distinguono",
             f"- di quanto la mossa del Cercatore batte quella di Autore nelle partite che hanno scelto, in media: "
             f"{sum(scarto) / max(len(scarto), 1):.2f} su {prove} (sopravvalutato: e' la misura che ha scelto)",
             "\n### Come si leggono, per tipo di scelta\n",
             f"- **Attaccanti e bloccanti** sono una scelta intera, fatta in un colpo: il confronto e' pulito (dopo, per tutte e due "
             f"le mosse, gioca il Semplice). Qui il Cercatore vince netto in **{len(combat_c)}** punti "
             f"({sum(1 for r in combat_c if r['tipo'] == 'attacca')} attacchi, {sum(1 for r in combat_c if r['tipo'] == 'blocca')} blocchi), "
             f"Autore in {sum(1 for r in netti_f if r['tipo'] != 'agisci')}: sono le scelte da riguardare, non errori certi. "
             f"L'avversario delle partite di prova e' il Semplice, che i trucchi in risposta a un attacco li usa poco: un attacco "
             f"del Cercatore che li rischia puo' sembrare migliore di quanto e' contro una persona che ha mana aperto.",
             f"- **La prima mossa della fase principale** NON e' la fase intera: si confronta la prima azione di Autore piu' il "
             f"Semplice che continua al posto suo con la prima azione del Cercatore piu' il Semplice. Delle {sum(1 for r in netti_c if r['tipo'] == 'agisci')} "
             f"vinte netto dal Cercatore: {generi(netti_c)}. «Stesso piano, altro ordine» vuol dire che Autore quella mossa l'ha fatta "
             f"subito dopo: la differenza la fa il Semplice che continua male (per esempio gioca un'altra carta al posto di quella "
             f"che Autore ha giocato), non Autore. Qui il segnale vero e' solo «una mossa che Autore non ha fatto», e anche "
             f"quello va letto con la fase intera accanto (colonna «la fase vera»). Il confronto giusto della fase intera viene "
             f"con la valutazione del tavolo (passo 8.5).",
             "\n## Attaccanti e bloccanti: dove la mossa del Cercatore vince netto, nei mondi nuovi\n",
             "| partita | turno | scelta | Autore | Cercatore | vinte F - C | coppie solo C, solo F | p |",
             "| :--- | ---: | :--- | :--- | :--- | :--- | :--- | ---: |"]
    righe += [_riga(r, conferme) for r in sorted(combat_c, key=lambda r: segni(r["conferma"][2], r["conferma"][3]))]
    righe += ["\n## La prima mossa della fase principale, dove il Cercatore vince netto\n",
              "| partita | turno | Autore, prima azione | la fase vera di Autore | Cercatore | genere | vinte F - C | p |",
              "| :--- | ---: | :--- | :--- | :--- | :--- | :--- | ---: |"]
    for r in sorted((r for r in netti_c if r["tipo"] == "agisci"), key=lambda r: (r.get("genere") or "", segni(r["conferma"][2], r["conferma"][3]))):
        c = r["conferma"]
        righe.append(f"| {r['gid']} | {r['turno']} | {r['candidate'][r['autore']]} | {r.get('fase_vera')} | {r['candidate'][r['cercatore']]} | "
                     f"{r.get('genere')} | {c[0]:.0f}/{conferme} - {c[1]:.0f}/{conferme} | {segni(c[2], c[3]):.3f} |")
    righe += ["\n## Dove la mossa di Autore vince netto, nei mondi nuovi\n",
              "| partita | turno | scelta | Autore | Cercatore | vinte F - C | coppie solo C, solo F | p |",
              "| :--- | ---: | :--- | :--- | :--- | :--- | :--- | ---: |"]
    righe += [_riga(r, conferme) for r in sorted(netti_f, key=lambda r: segni(r["conferma"][2], r["conferma"][3]))]
    righe += ["\n## I punti saltati, col perche'\n"] + [f"- {k} x {m}" for m, k in saltati.most_common()]
    righe += ["\n## Tutte le scelte diverse\n"]
    for r in diverse:
        c = r["conferma"]
        righe.append(f"- {r['gid']} t{r['turno']} {r['tipo']}: Autore «{r['candidate'][r['autore']]}» {r['punti'][r['autore']]:.0f}/{prove}, "
                     f"Cercatore «{r['candidate'][r['cercatore']]}» {r['punti'][r['cercatore']]:.0f}/{prove}; nei mondi nuovi {c[0]:.0f}-{c[1]:.0f} "
                     f"su {conferme} (p {segni(c[2], c[3]):.2f})")
    if turni is not None:
        righe[0] = f"# Il confronto con le partite vere, partite di prova troncate a {turni} turni (passo 8.5)\n"
        righe.insert(3, f"**Partite di prova troncate:** ogni partita di prova della scelta si ferma alla fine del turno della scelta "
                        f"+ {turni}; se non e' finita, il suo esito e' la probabilita' di vincere detta dalla valutazione del tavolo "
                        f"(`valuta.py`, `Valuta_Tavolo.md`): i punti della scelta sono somme di probabilita'. La conferma nei mondi "
                        f"nuovi invece gioca le partite fino in fondo: sceglie la valutazione, giudica il risultato vero.\n")
    coda = "" if valuta == "v0" else f"_{valuta.upper()}"                       # passo 8.6: l'esito con V0 resta
    if coda:
        righe[0] = righe[0].rstrip("\n").replace("(passo 8.5)", f"giudicate da {valuta.upper()} (passo 8.6)") + "\n"
    report = REPORT if turni is None else REPORT.replace(".md", f"_Troncate{coda}.md")
    with open(report, "w", encoding="utf-8") as h: h.write("\n".join(righe) + "\n")
    json.dump({"prove": prove, "conferme": conferme, "turni": turni, "valuta": valuta, "risultati": ris, "saltati": dict(saltati)},
              open(os.path.join(QUI, "confronto_log.json" if turni is None else f"confronto_log_troncate{coda.lower()}.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=0)
    print("\n".join(righe[:13]))


def rapporto_da_file(prove, conferme):
    """Riscrive il rapporto dai risultati salvati; i saltati si ricontano (lettura, poi stato e mossa)."""
    dati = json.load(open(os.path.join(QUI, "confronto_log.json"), encoding="utf-8"))
    ris = dati["risultati"] if isinstance(dati, dict) else dati
    if isinstance(dati, dict) and dati.get("saltati"): saltati = Counter(dati["saltati"])
    else:
        pts, saltati = tutti_i_punti()
        fatti = {(r["gid"], r["k"]) for r in ris}
        for d in pts:
            if (d["gid"], d["k"]) in fatti: continue
            esito, perche = _lavoro_verifica((d, "DalLog"))
            saltati[f"{d['tipo']}: {_motivo(perche or esito)}"] += 1
    rapporto(ris, saltati, prove, conferme, None, comando=f"py -I -X utf8 Motore_Partita/confronto_log.py --confronto {prove}")


# ====================================================================== le prove
class DalLogSenzaTappati(DalLog):
    """Rotto apposta: i permanenti restano stappati (il log dice tappati)."""
    def __call__(self, p):
        super().__call__(p)
        for o in p.t.campo: o.tappato = False


class DalLogSenzaStoria(DalLog):
    """Rotto apposta: senza la storia del turno (gli scry e i surveil, le pescate, le morti di questo turno)."""
    def __init__(self, punto):
        super().__init__(dict(punto, storia=[]))


class DalLogSenzaDanno(DalLog):
    """Rotto apposta: il danno segnato si perde (120.6)."""
    def __call__(self, p):
        super().__call__(p)
        for o in p.t.campo: o.danno = 0


def _rifatto(d, D=DalLog):
    """Il punto rifatto con D: -> (partita al punto di scelta, None) o (None, perche')."""
    a, b = _mazzi(d)
    class Fermati(S.Semplice):
        def __init__(s_, punto):
            super().__init__(1)
            s_.punto, s_.p = punto, None
        def _ferma(s_, gancio, p, i, base):
            if gancio != s_.punto["tipo"]: return base()
            s_.p = p
            raise Fermo()
        def agisci(s_, p, i): return s_._ferma("agisci", p, i, lambda: S.Semplice.agisci(s_, p, i))
        def attacca(s_, p, i): return s_._ferma("attacca", p, i, lambda: S.Semplice.attacca(s_, p, i))
        def blocca(s_, p, i): return s_._ferma("blocca", p, i, lambda: S.Semplice.blocca(s_, p, i))
    f = Fermati(d)
    g = [f, S.Semplice(2)] if d["io"] == 0 else [S.Semplice(2), f]
    try: S.partita(a, b, d["seme"], g[0], g[1], prepara=D(d), P=Riparti)
    except Fermo: return f.p, None
    except Saltato as e: return None, str(e)
    return None, "non arrivata al punto"


def _lavoro_verifica(arg):
    d, nome_D = arg
    D = {"DalLog": DalLog, "SenzaTappati": DalLogSenzaTappati, "SenzaStoria": DalLogSenzaStoria, "SenzaDanno": DalLogSenzaDanno}[nome_D]
    p, perche = _rifatto(d, D)
    if p is None: return ("saltato", perche)
    v = verifica(p, d)
    if v: return ("diverso", v)
    try: mossa_vera(p, d["io"], d); return ("uguale", None)
    except Saltato as e: return ("mossa", str(e))


def prova():
    casi = []
    def caso(nome, ok, det=""): casi.append((nome, bool(ok), det))
    t0 = time.time()
    pts, saltati = tutti_i_punti()
    tipi = Counter(d["tipo"] for d in pts)
    caso("lettura: i punti di scelta delle 44 partite, dei tre tipi, ognuno con la risposta di Autore",
         len({d["gid"] for d in pts}) >= 40 and all(tipi[x] > 50 for x in ("agisci", "attacca", "blocca")) and all("risposta" in d for d in pts),
         f"{len(pts)} punti {dict(tipi)} da {len({d['gid'] for d in pts})} partite; saltati alla lettura {sum(saltati.values())}")
    caso("lettura: ogni punto ha i mazzi giusti (Autore: il suo mazzo vero di 40; l'avversario: tante carte quante ne ha il log)",
         all(len(d["mazzi"][d["io"]]) == 40 for d in pts) and
         all(len(d["mazzi"][1 - d["io"]]) == d["mani"][1 - d["io"]] + d["grimori"][1 - d["io"]] +
             sum(1 for x in d["oggetti"] if x["proprietario"] == 1 - d["io"] and x["pedina"] is None and not x.get("preparata")) for d in pts))
    storti = []                                                                                    # il modello dell'avversario
    for gid, path in R.partite():
        seq = list(R.messaggi(path)); io = mio_posto(seq)
        if not io: continue
        try: m, info = mazzo_modello(seq, 3 - io, gid)
        except Saltato: continue
        viste, T = viste_avversario(seq, 3 - io), F.tutte()
        col = set(info["colori"])
        for n_, k_ in Counter(m).items():
            if "Land" in T[n_].voce[1]: continue
            if k_ > max(COPIE_MASSIME, viste[n_]) or not colori_carta(n_) <= col: storti.append((gid, n_, k_))
        if len(m) != CARTE_LIMITED or sum(1 for x in m if "Land" in T[x].voce[1]) < TERRE_LIMITED - 0: storti.append((gid, "mazzo", len(m)))
    caso("modello dell'avversario: 40 carte, 17 terre, nessuna carta non vista oltre 3 copie, tutte nei suoi colori",
         not storti, f"{storti[:3]}")
    pool = G.nuovo_pool()
    try:
        out = {n: pool.map(_lavoro_verifica, [(d, n) for d in pts], chunksize=4) for n in ("DalLog", "SenzaTappati", "SenzaStoria", "SenzaDanno")}
        spazz = pool.map(_lavoro_spazzata, pts, chunksize=2)
        rif = pool.map(_lavoro_rifai, pts[::40], chunksize=1)
    finally: pool.terminate()
    c = Counter(r[0] for r in out["DalLog"])
    caso("ricostruzione: il tavolo rifatto e' quello del log (verifica) in almeno 98 punti su 100, e la mossa vera e' scritta e legale nel 98%",
         c["diverso"] + c["saltato"] <= len(pts) * 0.02 and c["uguale"] >= len(pts) * 0.98,
         f"{dict(c)}; diversi: {Counter(r[1][:50] for r in out['DalLog'] if r[0] == 'diverso').most_common(3)}")
    disc = [r[1] for r in out["DalLog"] if r[0] == "mossa" and "DISCORDE" in r[1]]
    caso("riscontro: nessuna mossa di Autore e' illegale per il motore sul tavolo rifatto (zero DISCORDE)", not disc, f"{disc[:2]}")
    tap = Counter(r[0] for r in out["SenzaTappati"])
    con_tap = sum(1 for d in pts if any(x["tappato"] for x in d["oggetti"] if x["zona"] == "campo"))
    caso("prova negativa: col tavolo rifatto senza i tappati la verifica dice «tappato» dove il log ha permanenti tappati",
         tap["diverso"] >= con_tap * 0.95 and all("tappato" in r[1] for r in out["SenzaTappati"] if r[0] == "diverso"),
         f"diversi {tap['diverso']} su {con_tap} punti con tappati")
    dan = Counter(r[0] for r in out["SenzaDanno"])
    con_dan = sum(1 for d in pts if any(x["danno"] for x in d["oggetti"] if x["zona"] == "campo"))
    caso("prova negativa: senza il danno segnato la verifica dice «danno» dove il log ha creature danneggiate",
         con_dan > 0 and dan["diverso"] >= con_dan and all("danno" in r[1] for r in out["SenzaDanno"] if r[0] == "diverso"),
         f"diversi {dan['diverso']} su {con_dan} punti con danno")
    sto = [r[1] for r in out["SenzaStoria"] if r[0] == "mossa" and "DISCORDE" in r[1]]
    caso("prova negativa: senza la storia del turno tornano gli attacchi illegali (Surveillance Phantasm attacca solo se ha guardato: 702.3b)",
         len(sto) >= 5 and all("difensore" in x for x in sto), f"{len(sto)} DISCORDE: {sto[:1]}")
    esiti = Counter("ok" if r[1] is None else ("FISCHIO" if r[1].startswith("FISCHIO") else "ECCEZIONE" if r[1].startswith("ECCEZIONE")
                    else "DISCORDE" if "DISCORDE" in r[1] else "saltato") for r in spazz)
    caso("spazzata: ogni punto rifatto e giocato fino alla fine con la mossa vera, arbitro acceso: nessun fischio, nessuna eccezione",
         esiti["FISCHIO"] == 0 and esiti["ECCEZIONE"] == 0 and esiti["DISCORDE"] == 0 and esiti["ok"] >= len(pts) * 0.97, f"{dict(esiti)}")
    caso("replay: la partita rifatta dal punto (prepara + Riparti) si rifa' uguale dal nastro, evento per evento",
         all(rif), f"{sum(rif)}/{len(rif)}")
    # il senso: un attacco di Autore che chiude la partita in quel turno
    letali = []
    for d in pts:
        if d["tipo"] != "attacca" or not d["risposta"]: continue
        avv = 1 - d["io"]
        forze = sum(x["forza"] or 0 for x in d["oggetti"] if x["iid"] in d["risposta"])
        difesa = [x for x in d["oggetti"] if x["zona"] == "campo" and x["controllore"] == avv and x["forza"] is not None and not x["tappato"]]
        if not difesa and forze >= d["vite"][avv] and forze > 0: letali.append(d)
    pool = G.nuovo_pool()
    try:
        sensi = []
        for d in letali[:4]:
            e, ctx = al_punto(d, prove=12, pool=pool)
            sensi.append((e["punti"] or [12])[e["autore"]] == 12 and (e["punti"] is None or e["punti"][e["cercatore"]] == 12))
    finally: pool.terminate()
    # (non si chiede che «nessun attacco» faccia meno: le partite di prova arrivano alla fine, e con l'avversario a 5 vite
    # senza bloccanti si vince anche al turno dopo. Il metro misura se si vince, non quanto presto: 14 ott 2026)
    caso("senso: dove Autore attacca per il letale senza bloccanti possibili, la sua mossa e quella del Cercatore vincono 12 su 12",
         letali and all(sensi), f"{len(letali)} punti letali, provati {len(sensi)}: {sensi}")
    ok = sum(1 for _, k, _ in casi if k)
    for nome, k, det in casi: print(("OK   " if k else "ROSSO"), nome, ("  -- " + det) if det else "")
    print(f"\n{ok}/{len(casi)} in {time.time() - t0:.0f} s")
    return ok == len(casi)


def _lavoro_rifai(d):
    """Registra la partita dal punto con due Semplice, poi la rifa' dal nastro: devono essere uguali."""
    a, b = _mazzi(d)
    kw = {"prepara": DalLog(d), "P": Riparti}
    try: p, nastro = G.registra(a, b, d["seme"], S.Semplice(1), S.Semplice(2), **kw)
    except Saltato: return True
    q, st = G.rifai(a, b, d["seme"], nastro, **kw)
    ch = lambda p_: [(e.tipo, e.vecchio, e.nuovo, e.da, e.a, e.causa, e.giocatore, e.quanto) for e in p_.t.eventi]
    return ch(p) == ch(q) and st["cur"] == len(nastro)


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[:1] == ["--punti"]:
        pts, s = tutti_i_punti()
        print(f"{len(pts)} punti: {dict(Counter(d['tipo'] for d in pts))}; saltati {sum(s.values())}")
        for m, k in s.most_common(): print(f"  {k} x {m}")
    elif a[:1] == ["--spazzata"]: spazzata()
    elif a[:1] == ["--confronto"]:
        r_ = int(a[1]) if len(a) > 1 and a[1].isdigit() else 12
        confronto(r_, 2 * r_, turni=int(a[a.index("--turni") + 1]) if "--turni" in a else None,
                  valuta=a[a.index("--valuta") + 1] if "--valuta" in a else "v0")
    elif a[:1] == ["--rapporto"]:
        r_ = int(a[1]) if len(a) > 1 else 12
        rapporto_da_file(r_, 2 * r_)
    elif a[:1] == ["--prova"]: sys.exit(0 if prova() else 1)
    else: print(__doc__)
