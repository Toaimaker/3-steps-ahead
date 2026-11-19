"""Il riscontro del motore con le partite di Quick Draft giocate davvero (14 ott 2026).

Autore, 14 ott 2026: «la regola e' di cominciare a testare partite di quick match sul motore e confrontarle con quelle
giocate per validare il funzionamento». Le partite sono quelle di Reality Fracture nei log di Arena
(Espansioni/FRA/Partite/<ID>/partita.json -> Log_Arena/partite/<ID>/arena.log). Il log e' la verita': dice gli oggetti
con forza e costituzione, chi attacca e chi blocca, i danni, il mana pagato e da quale fonte, gli inneschi creati, le
vite. Il riscontro, nei momenti in cui una regola decide l'esito, fa rifare il conto al motore partendo dallo stato vero
del log e confronta:
  1. il danno da combattimento (510, 702.2-702.19, il passo 6): con forza, costituzione, danno gia' segnato e parole
     chiave di ogni creatura come le dice il log (le parole dagli id delle abilita' di Arena: Regole/abilita_combattimento.json),
     gli attaccanti e i bloccanti del log e l'assegnazione del log (che il motore controlla, 510.1e), il motore infligge
     il danno e fa le azioni di stato: si confrontano i danni fonte per fonte, le vite e le creature morte;
  2. il mana (106, 107, 601.2g-h, il passo 4): il mana pagato per ogni magia, fonte per fonte, deve pagare il costo
     stampato secondo `mana`, e ogni fonte deve poter produrre quel colore secondo il motore (305.6, 605);
  3. i tempi di lancio (117.1a, 307.5, 702.8a, il passo 5): una magia che non e' istantaneo ne' ha lampo si lancia solo
     nella propria fase principale, a pila vuota;
  4. le terre che entrano tappate (614.1d, il passo 7.2): per ogni terra intera giocata il motore dice tappata o no
     guardando il campo di quel momento;
  5. forza e costituzione (613, il passo 7): per ogni creatura di una carta intera in campo, senza effetti temporanei
     ne' segnalini sconosciuti, il motore calcola i livelli con le statiche delle carte intere in campo;
  6. gli inneschi d'entrata (603.6a, il passo 7.2): una carta intera che entra in campo fa nascere in Arena tante
     abilita' quante il motore ne legge «When this enters».
Ogni controllo dice anche quanti casi ha saltato e perche' (una carta non intera, un effetto che il log non spiega):
un caso saltato non e' un caso verde.

    py -I -X utf8 Motore_Partita/riscontro.py               il riscontro su tutte le partite FRA di Quick Draft
    py -I -X utf8 Motore_Partita/riscontro.py --prova       le prove: motori rotti apposta devono dare discordanze
"""
import glob
import json
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import carte_fra as F
import combattimento as C
import effetti as E
import mana as M
from mana import NonCoperto
from tavolo import PAROLE, Carta, Oggetto, costituzione, forza, parole

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = json.load(open(os.path.join(ROOT, "Collezione", "arena_cards_cache.json"), encoding="utf-8"))
ABILITA = json.load(open(os.path.join(ROOT, "Regole", "abilita_combattimento.json"), encoding="utf-8"))["abilita"]
COLORE = {1: "W", 2: "U", 3: "B", 4: "R", 5: "G"}        # dal log: Plains 1, Island 2, Mountain 4, Forest 5 (Swamp 3)
SEGNALINI_NOTI = {7, 172}                                 # fedelta', stordimento (non toccano forza e costituzione)
SEGNALINI_LOG = {1: "+1/+1", 7: "fedelta", 172: "stordimento", 185: "finalita"}   # i codici del log che il motore conosce (122.1a, 306.5b, 122.1d, 122.1h: 185 letto il 4 nov 2026 su Grim Repriser tornata dal cimitero)
# il +1/+1 (1) e' nel log un'annotazione «ModifiedToughness, ModifiedPower, Counter»: Titanbones con due segnalini e' 6/5
REPORT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Riscontro_Quick_FRA.md")


def nome(grp):
    return DB.get(str(grp), {}).get("n")


def pulito(testo):
    return F.pulisci(testo)


def partite():
    out = []
    for f in sorted(glob.glob(os.path.join(ROOT, "Espansioni", "FRA", "Partite", "*", "partita.json"))):
        d = json.load(open(f, encoding="utf-8"))
        if "QuickDraft" not in d.get("evento", ""): continue
        log = os.path.join(ROOT, d["log"]) if d.get("log") else os.path.join(ROOT, "Log_Arena", "partite", d["id"], "arena.log")
        if os.path.exists(log): out.append((d["id"], log))
    return out


def dettagli(a):
    return {x["key"]: (x.get("valueInt32") or x.get("valueString") or [None])[0] for x in a.get("details", [])}


# ====================================================================== la lettura del log
class Stato:
    def __init__(self):
        self.obj, self.zone, self.pl, self.turno, self.pann = {}, {}, {}, {}, {}

    def copia(self):
        s = Stato()
        s.obj, s.zone, s.pl, s.turno, s.pann = dict(self.obj), dict(self.zone), {k: dict(v) for k, v in self.pl.items()}, dict(self.turno), dict(self.pann)
        return s

    def zona(self, tipo, seat=None):
        for z in self.zone.values():
            if z["type"] == tipo and (seat is None or z.get("ownerSeatId") == seat): return z
        return None

    def in_zona(self, tipo, seat=None):
        z = self.zona(tipo, seat)
        return [self.obj[i] for i in (z or {}).get("objectInstanceIds", []) if i in self.obj]

    def tipo_zona(self, zid):
        return (self.zone.get(zid) or {}).get("type")


def messaggi_di(st, riga):
    """I gameStateMessage di una riga del log, sullo stato st che tiene la partita: -> (stato prima, stato dopo, annotazioni)
    per ognuno. Una riga alla volta, perche' dal vivo (cercatore_vivo.py, 4 nov 2026) le righe arrivano mentre si gioca."""
    if "greToClientEvent" not in riga: return
    try: ev = json.loads(riga[riga.find("{"):])
    except ValueError: return
    for m in ev.get("greToClientEvent", {}).get("greToClientMessages", []):
        gs = m.get("gameStateMessage")
        if not gs: continue
        prima = st.copia()
        if gs.get("type") == "GameStateType_Full": st.obj, st.zone = {}, {}
        for z in gs.get("zones", []): st.zone[z["zoneId"]] = z
        for o in gs.get("gameObjects", []): st.obj[o["instanceId"]] = o
        for i in gs.get("diffDeletedInstanceIds", []): st.obj.pop(i, None)
        for p in gs.get("players", []):
            g = st.pl.setdefault(p.get("systemSeatNumber") or p.get("systemSeatId"), {})
            g.update(p)
            if "lifeTotal" not in p: g["lifeTotal"] = 0      # Arena non scrive i valori a zero (13 nov 2026, come mana_aperto.vite_da)
        if gs.get("turnInfo"): st.turno.update(gs["turnInfo"])
        for a in gs.get("persistentAnnotations", []): st.pann[a["id"]] = a
        for i in gs.get("diffDeletedPersistentAnnotationIds", []): st.pann.pop(i, None)
        yield prima, st.copia(), list(gs.get("annotations", [])) + list(gs.get("persistentAnnotations", []))


def messaggi(path):
    """-> (stato prima, stato dopo, annotazioni) per ogni gameStateMessage della partita."""
    st = Stato()
    for riga in open(path, encoding="utf-8", errors="ignore"):
        yield from messaggi_di(st, riga)


def parole_log(o):
    """Le parole chiave dell'oggetto secondo Arena (id delle abilita'), solo quelle del passo 6 piu' anti-malocchio."""
    out = set()
    for a in o.get("uniqueAbilities", []):
        kw = ABILITA.get(str(a.get("grpId")), {}).get("kw")
        if kw in PAROLE or kw == "hexproof": out.add(kw)
    return out


def segnalini_log(st, iid):
    """I segnalini di un oggetto secondo il log: codice -> quanti (le annotazioni persistenti col tipo «Counter», in
    qualsiasi posizione della lista dei tipi)."""
    out = {}
    for a in st.pann.values():
        if "AnnotationType_Counter" in a["type"] and iid in a.get("affectedIds", []):
            out[dettagli(a).get("counter_type")] = dettagli(a).get("count", 0)
    return out


def fedelta_log(st, o):
    """306.5b, 122.1e: la fedelta' sono i segnalini fedelta' (nel log: segnalini di tipo 7)."""
    s = segnalini_log(st, o["instanceId"])
    return s[7] if 7 in s else valore(o.get("loyalty", 0))


def valore(x):
    return x.get("value", 0) if isinstance(x, dict) else x                  # il log non scrive i valori zero


# ====================================================================== 1. il danno da combattimento
class Assegna:
    """Il giocatore del riscontro: assegna il danno come l'ha assegnato in Arena."""

    def __init__(self, danni, mappa):
        self.danni, self.mappa = danni, mappa

    def assegna(self, p, i, compiti):
        out = {}
        for c in compiti:
            o = c["creatura"]
            d = {}
            for (src, dst), n in self.danni.items():
                if src != self.mappa["n2iid"][o.n]: continue
                if dst in (1, 2): d[dst - 1] = d.get(dst - 1, 0) + n
                elif dst in self.mappa["iid2o"]: d[self.mappa["iid2o"][dst]] = n
            out[o] = d
        return out


def tavolo_vuoto(T=E.TavoloEffetti):
    t = T([[], []], seme=1)
    t.primo = 0
    return t


def metti(t, nome_, tipo, seat, car):
    c = Carta(next(t._carte), nome_, tipo, seat - 1, car=car)
    o = Oggetto(next(t._oggetti), c, "campo", seat - 1)
    o.tavolo, o.ts, o.controllo_dal = t, next(t._ts), -5
    t.oggetti[o.n] = o
    t.campo.append(o)
    return o


def solo_regole(car):
    """Le abilita' di una carta intera che non toccano forza e costituzione (quelle il log le dice gia'): gli effetti
    sulle regole del gioco (613.11), le sostituzioni (614.1a), le eccezioni alle azioni di stato (704.5i)."""
    return [ab for ab in car.get("abilita") or [] if ab.get("tipo") in ("eccezione", "sostituzione")
            or (ab.get("tipo") == "statica" and all(d["livello"] == "regola" for d in ab["effetti"]))]


def combattimento(prima, dopo, ann, P=E.Partita, T=E.TavoloEffetti, primo_passo=True, senza_primo=None):
    """Il danno di un passo di combattimento rifatto dal motore. -> (discordanze, dettaglio) o None se non si puo'."""
    danni = Counter()
    for a in ann:
        if a["type"][0] != "AnnotationType_DamageDealt": continue
        d = dettagli(a)
        if d.get("type") != 1: continue
        for x in a.get("affectedIds", []): danni[(a["affectorId"], x)] += d.get("damage", 0)
    if not danni: return None
    campo = prima.in_zona("ZoneType_Battlefield")
    att = [o for o in campo if o.get("attackState") == "AttackState_Attacking"]
    blo = [o for o in campo if o.get("blockState") == "BlockState_Blocking"]
    if not att: return ("senza attaccanti nel log", None)
    for o in campo:                                                                                # un effetto sul danno che il motore non legge
        tr = carta(o)
        if tr is not None and tr.intera: continue
        testo = " ".join(f.get("oracle") or "" for f in (tr.scheda["faces"] if tr else []))
        statiche = [x for x in pulito(testo).split("\n") if not re.match(r"([A-Z][a-z]+ — )?(When|Whenever|At|\{|[+−-]\d|\d+:)", x.strip())]
        if any(re.search(r"(?<!non)combat damage|assigns|prevent|would deal|loyalty\.$|for having 0 loyalty", x) and "noncombat" not in x and not x.startswith("Planeswalkers you control have")
               for x in statiche):
            return (f"in campo {nome(o['grpId'])}, un effetto sul danno che il motore non legge", None)
    t = tavolo_vuoto(T)
    mappa = {"iid2o": {}, "n2iid": {}}
    attivo = prima.turno.get("activePlayer")
    for o in att + blo + [x for x in campo if "CardType_Planeswalker" in x.get("cardTypes", [])]:
        if o["instanceId"] in mappa["iid2o"]: continue
        car = {"parole": sorted(parole_log(o))}
        tipo = "Creature" if "CardType_Creature" in o.get("cardTypes", []) else "Planeswalker"
        if tipo == "Creature": car.update(forza=valore(o["power"]), costituzione=valore(o["toughness"]))
        else: car["fedelta"] = valore(o.get("loyalty", 0))
        if tipo == "Planeswalker": car["fedelta"] = fedelta_log(prima, o)
        tr = carta(o)
        if tr is not None and tr.intera and solo_regole(tr.voce[2]): car["abilita"] = solo_regole(tr.voce[2])   # 613.11, 614.1a
        x = metti(t, nome(o["grpId"]) or str(o["grpId"]), tipo, o["controllerSeatId"], car)
        x.danno = o.get("damage", 0) or 0
        if tipo == "Planeswalker": x.segnalini["fedelta"] = fedelta_log(prima, o)
        mappa["iid2o"][o["instanceId"]], mappa["n2iid"][x.n] = x, o["instanceId"]
    for o in campo:                                                                                # le regole, le sostituzioni, le eccezioni (704.5i)
        tr = carta(o)
        if o["instanceId"] in mappa["iid2o"] or tr is None or not tr.intera: continue
        if solo_regole(tr.voce[2]):
            metti(t, tr.nome, tr.voce[1], o["controllerSeatId"], {"abilita": solo_regole(tr.voce[2])})
    for s in (1, 2): t.giocatori[s - 1].vite = prima.pl.get(s, {}).get("lifeTotal", 20)
    t.primo = attivo - 1
    p = P(t)
    p.attivo, p.fase, p.passo = attivo - 1, "combattimento", "danno"
    for o in att:
        x = mappa["iid2o"][o["instanceId"]]
        tid = (o.get("attackInfo") or {}).get("targetId")
        b = (tid - 1) if tid in (1, 2) else mappa["iid2o"].get(tid)
        if b is None: return ("attacca un bersaglio sconosciuto", None)
        p.attaccanti[x], p._ctrl[x] = b, x.controllore
        if not isinstance(b, int): p._ctrl[b] = b.controllore
    for o in blo:
        x = mappa["iid2o"][o["instanceId"]]
        ids = (o.get("blockInfo") or {}).get("attackerIds", [])
        lst = [mappa["iid2o"][i] for i in ids if i in mappa["iid2o"]]
        if len(lst) != 1: return ("un bloccante su piu' attaccanti o su nessuno", None)
        p.bloccanti[x], p._ctrl[x] = lst, x.controllore
    for a in p.attaccanti:
        if any(a in l for l in p.bloccanti.values()): p.bloccate.add(a)
    if any(o.get("blockState") == "BlockState_Blocked" for o in att):
        for o in att:
            if o.get("blockState") == "BlockState_Blocked": p.bloccate.add(mappa["iid2o"][o["instanceId"]])
    p.dichiarati = len(att)
    if not primo_passo:
        p.passi_danno = 1
        p.senza_primo = {mappa["iid2o"][i] for i in (senza_primo or set()) if i in mappa["iid2o"]}
    g = Assegna(danni, mappa)
    k0 = len(t.eventi)
    vite0 = [gg.vite for gg in t.giocatori]
    try:
        p._passo_danno({0: g, 1: g})
        t.azioni_di_stato()
    except (NonCoperto, RuntimeError) as e:
        return (f"motore: {e}", None)
    fatti = Counter()
    for e in t.eventi[k0:]:
        if e.tipo != "danno": continue
        dst = (e.giocatore + 1) if e.nuovo is None else mappa["n2iid"].get(e.nuovo)
        fatti[(mappa["n2iid"][e.vecchio], dst)] += e.quanto
    disc = []
    if fatti != danni:
        disc.append(f"danni: motore {sorted(fatti.items())}, Arena {sorted(danni.items())}")
    illegali = [e.causa for e in t.eventi[k0:] if e.tipo == "illegale"]
    if illegali: disc.append(f"il motore rifiuta l'assegnazione di Arena: {illegali[0]}")
    vite_log = [dopo.pl.get(s, {}).get("lifeTotal") for s in (1, 2)]
    if any(a["type"][0] == "AnnotationType_LossOfGame" for a in ann):                              # l'ultimo messaggio non aggiorna le vite:
        vite_log = [(prima.pl.get(s, {}).get("lifeTotal") or 0) + sum(dettagli(a).get("life", 0) for a in ann     # si leggono le variazioni
                    if a["type"][0] == "AnnotationType_ModifiedLife" and s in a.get("affectedIds", [])) for s in (1, 2)]
    vite_motore = [gg.vite for gg in t.giocatori]
    altre_vite = [a for a in ann if a["type"][0] == "AnnotationType_ModifiedLife" and a.get("affectorId") not in {i for i, _ in danni}]
    if vite_log != vite_motore and not altre_vite: disc.append(f"vite: motore {vite_motore}, Arena {vite_log}")
    morti_m = sorted(mappa["n2iid"][e.vecchio] for e in t.eventi[k0:] if e.tipo == "zona" and e.da == "campo")
    morti_l = sorted(i for i in mappa["iid2o"] if i not in [o["instanceId"] for o in dopo.in_zona("ZoneType_Battlefield")])
    return (disc, {"morti_motore": morti_m, "morti_log": morti_l, "primi": [mappa["n2iid"][o.n] for o in p.senza_primo] if p.doppio else None,
                   "doppio": p.doppio})


# ====================================================================== 2-6. mana, tempi, terre, livelli, inneschi
_PREPARATE = None


def carta(o):
    """La traduzione della carta dell'oggetto: per nome, o la magia preparata (723.3c) col nome della seconda faccia."""
    global _PREPARATE
    n = nome(o.get("grpId"))
    if not n: return None
    tr = F.tutte().get(n)
    if tr is not None: return tr
    if _PREPARATE is None:
        _PREPARATE = {}
        for t in set(F.tutte().values()):                                                         # la magia e' intera se il suo testo e' letto
            prep = t.voce[2].get("prepara")
            if prep: _PREPARATE[prep[0]] = F.Traduzione(prep[0], (prep[0], prep[1], prep[2]), [], t.scheda)
    return _PREPARATE.get(n)


def produce(t, colore):
    """La fonte (Traduzione) puo' produrre quel colore secondo il motore? 305.6, 605."""
    from tavolo import Carta as K
    k = K(0, t.nome, t.voce[1], 0, car=t.voce[2])
    if any(sum(prod) and prod[M.TIPI.index(colore)] for prod in M.produzioni(k)): return True
    return any(d.get("fa") == "aggiungi_mana" and M.produzione(d["mana"])[M.TIPI.index(colore)]           # 106.4: un'abilita' che
               for ab in t.voce[2].get("abilita") or [] for d in ab.get("fa") or [])                       # non e' di mana (Chandra +1)


def riscontra(path, P=E.Partita, T=E.TavoloEffetti, conti=None, esempi=None):
    conti = conti if conti is not None else Counter()
    esempi = esempi if esempi is not None else defaultdict(list)
    def nota(chiave, msg):
        conti[chiave] += 1
        if msg and len(esempi[chiave]) < 6: esempi[chiave].append(f"{os.path.basename(os.path.dirname(path))}: {msg}")
    ultimo_combattimento = None
    attese_etb = {}
    bersagli = defaultdict(lambda: defaultdict(list))
    jace_attesi = {}
    jace_fatti, attivate = set(), set()
    seq = list(messaggi(path))
    for k, (prima, dopo, ann) in enumerate(seq):
        for a in ann:                                                                              # 601.2c: i bersagli dichiarati
            if a["type"][0] == "AnnotationType_TargetSpec" and a.get("affectorId") is not None:
                idx = dettagli(a).get("index", 1)
                for x in a.get("affectedIds", []):
                    if x not in bersagli[a["affectorId"]][idx]: bersagli[a["affectorId"]][idx].append(x)
        for a in ann:                                                                              # 8. la pedina Jace
            d8 = dettagli(a)
            if a["type"][0] == "AnnotationType_UserActionTaken" and d8.get("actionType") == 2:
                for aid in a.get("affectedIds", []):
                    ab = dopo.obj.get(aid) or {}
                    src = dopo.obj.get(ab.get("parentId")) or prima.obj.get(ab.get("parentId")) or {}
                    if not (src.get("type") == "GameObjectType_Token" and "SubType_Jace" in src.get("subtypes", [])): continue
                    ids = [u.get("grpId") for u in src.get("uniqueAbilities", [])]
                    if d8.get("abilityGrpId") not in ids[:2]: nota("Jace saltati", "abilita' non fra le due del Jace"); continue
                    j_ = ids.index(d8.get("abilityGrpId"))
                    tolti = sum(dettagli(x).get("transaction_amount", 0) for x in ann if x["type"][0] == "AnnotationType_CounterRemoved"
                                and x.get("affectorId") == aid and dettagli(x).get("counter_type") == 7)
                    if tolti == -E.JACE["abilita"][j_]["fedelta"]: nota("costo di fedelta' del Jace uguale (606.4)", None)
                    else: nota("costo di fedelta' del Jace DISCORDE", f"abilita' {j_}: motore {-E.JACE['abilita'][j_]['fedelta']}, Arena {tolti}")
                    jace_attesi[aid] = j_
            if a["type"][0] == "AnnotationType_ResolutionStart" and a.get("affectorId") in jace_attesi:
                aid = a["affectorId"]
                j_ = jace_attesi.pop(aid)
                jace_fatti.add(aid)
                fine = next((jj for jj in range(k, min(k + 8, len(seq))) if any(x["type"][0] == "AnnotationType_ResolutionComplete" and x.get("affectorId") == aid for x in seq[jj][2])), k)
                cat = Counter(dettagli(x).get("category") for _, _, a2 in seq[k:fine + 1] for x in a2
                              if x["type"][0] == "AnnotationType_ZoneTransfer" and x.get("affectorId") == aid)
                fa = E.JACE["abilita"][j_]["fa"][0]
                if fa["fa"] == "pesca": ok = cat["Draw"] == fa["n"]                                        # 121.1
                else: ok = cat["Draw"] == 0 and cat["Surveil"] <= fa["n"]                                 # 701.25a
                if ok: nota("abilita' del Jace uguali (701.71a)", None)
                else: nota("abilita' del Jace DISCORDI", f"{fa['fa']} {fa['n']}: Arena {dict(cat)}")
        for a in ann:                                                                              # le attivazioni (602)
            if a["type"][0] == "AnnotationType_UserActionTaken" and dettagli(a).get("actionType") == 2:
                attivate.update(a.get("affectedIds", []))
        for a in ann:                                                                              # 7. le magie e le abilita' intere
            if a["type"][0] == "AnnotationType_ResolutionStart":
                if a.get("affectorId") in jace_fatti: continue
                r = magia(seq, k, a, bersagli.get(a["affectorId"], {}), P, T)
                tipo_ = "magie"
                if r is None:
                    r = abilita_intera(seq, k, a, bersagli.get(a["affectorId"], {}), attivate, P, T)
                    tipo_ = "abilita'"
                if r is None: continue
                if isinstance(r[0], str): nota(f"{tipo_} saltate", r[0])
                elif r[0]: nota(f"{tipo_} DISCORDI", f"{r[1]['magia']}: " + "; ".join(r[0]))
                else: nota(f"{tipo_} uguali (608.2)", f"{r[1]['magia']}")
        tipi = [a["type"][0] for a in ann]
        step = dopo.turno.get("step")
        # 1. il danno da combattimento
        if any(t_ == "AnnotationType_DamageDealt" and dettagli(a).get("type") == 1 for t_, a in zip(tipi, ann)):
            primo, senza = True, None                                                                 # 510.4: il secondo passo
            if step == "Step_CombatDamage" and ultimo_combattimento and ultimo_combattimento[0] == dopo.turno.get("turnNumber"):
                primo, senza = False, ultimo_combattimento[2]
            r = combattimento(prima, dopo, ann, P, T, primo_passo=primo, senza_primo=senza)
            if step == "Step_FirstStrikeDamage" and r and r[1]:
                campo = prima.in_zona("ZoneType_Battlefield")
                senza_fs = {o["instanceId"] for o in campo if o.get("attackState") == "AttackState_Attacking" or o.get("blockState") == "BlockState_Blocking"
                            if not parole_log(o) & {"first strike", "double strike"}}
                ultimo_combattimento = (dopo.turno.get("turnNumber"), "fs", senza_fs)
            if r is None: pass
            elif isinstance(r[0], str): nota("combattimento saltato", r[0])
            elif r[0]: nota("combattimento DISCORDE", "; ".join(r[0]))
            else: nota("combattimento uguale", None)
            if r and not isinstance(r[0], str) and r[1]:
                m_m, m_l = r[1]["morti_motore"], r[1]["morti_log"]
                if m_m == m_l: nota("morti dopo il combattimento uguali (704.5g-h)", None)
                else:
                    # chi muore dopo, in Arena, lo dice il messaggio seguente (le azioni di stato)
                    dopo2 = seq[k + 1][1] if k + 1 < len(seq) else dopo
                    sul = {o["instanceId"] for o in dopo2.in_zona("ZoneType_Battlefield")}
                    m_l2 = sorted(i for i in r[1]["morti_log"] + [i for i in m_m if i not in sul] if i not in sul)
                    if sorted(set(m_l2)) == m_m: nota("morti dopo il combattimento uguali (704.5g-h)", None)
                    else: nota("morti dopo il combattimento DISCORDI", f"motore {m_m}, Arena {sorted(set(m_l2))}")
        # 2-3. il mana e i tempi di lancio
        for a in ann:
            if a["type"][0] != "AnnotationType_ZoneTransfer": continue
            d = dettagli(a)
            if d.get("category") == "CastSpell":
                for iid in a.get("affectedIds", []):
                    o = dopo.obj.get(iid)
                    if not o: continue
                    n = nome(o.get("grpId"))
                    tr = F.tutte().get(n) if n else None
                    # il lancio e' completato quando il log conferma l'azione «lancia» (actionType 1) su quell'oggetto: un lancio
                    # cominciato e annullato torna indietro tutto (734) e l'id puo' essere riusato da un'altra azione
                    fine = None
                    for j in range(k, min(k + 12, len(seq))):
                        az = [dettagli(x).get("actionType") for x in seq[j][2]
                              if x["type"][0] == "AnnotationType_UserActionTaken" and iid in x.get("affectedIds", [])]
                        if az:
                            fine = j if az[-1] == 1 else -1
                            break
                    if fine is None or fine < 0:
                        nota("mana saltato", f"{n}: lancio non confermato nel log (annullato, o l'id riusato da un'altra azione)")
                        nota("tempi saltati", None)
                        continue
                    # il mana pagato sta fra il lancio e la conferma (601.2g-h viene dopo 601.2a)
                    pag = [x for _, _, a2 in seq[k:fine + 1] for x in a2 if x["type"][0] == "AnnotationType_ManaPaid" and iid in x.get("affectedIds", [])]
                    pagati = [dettagli(x).get("color") for x in pag]
                    fonti = [x.get("affectorId") for x in pag]
                    if tr is None: nota("mana saltato", f"{n}: non e' una carta di FRA"); continue
                    costo = tr.voce[2].get("costo") or ""
                    testo = " ".join((f.get("oracle") or "") for f in tr.scheda["faces"])
                    if o.get("zoneId") and dopo.tipo_zona(dettagli(a).get("zone_src")) != "ZoneType_Hand":
                        nota("mana saltato", f"{n}: lanciata da fuori dalla mano (flashback, copia: costo diverso)")
                    elif re.search(r"additional cost|convoke|can't cast this spell|cast a noncreature spell this turn", testo, re.I) or \
                            any(re.search(r"spells (you|your opponents) cast cost", " ".join(f.get("oracle") or "" for f in (carta(x) or F.Traduzione("", None, [], {"faces": []})).scheda.get("faces", [])))
                                and not (carta(x) and carta(x).intera) for x in prima.in_zona("ZoneType_Battlefield")) or \
                            (re.search(r"this spell costs", testo, re.I) and not tr.intera):
                        nota("mana saltato", f"{n}: costo che un effetto non letto puo' cambiare (601.2f)")
                    elif (tr.voce[2].get("costo_mod") or any(carta(x_) is not None and carta(x_).intera and any(ab.get("tipo") == "costi"
                          for ab in carta(x_).voce[2].get("abilita") or []) for x_ in prima.in_zona("ZoneType_Battlefield"))) and ignoto_in_campo(prima):
                        nota("mana saltato", f"{n}: un costo che dipende dal campo, e nel campo {ignoto_in_campo(prima)}")
                    elif any(c not in COLORE for c in pagati):
                        nota("mana saltato", f"{n}: mana incolore o di colore che il log codifica in modo non letto ({pagati})")
                    else:
                        # 601.2f: il costo totale lo calcola il motore, col campo di quel momento (riduzioni e aumenti)
                        tv, _ = tavolo_da_log(prima, T)
                        tv.primo = (prima.turno.get("activePlayer") or 1) - 1
                        pv = P(tv)
                        cv = Carta(next(tv._carte), tr.nome, tr.voce[1], o["ownerSeatId"] - 1, car=dict(tr.voce[2]))
                        ov = Oggetto(next(tv._oggetti), cv, "mano"); ov.tavolo, ov.ts = tv, 0
                        tv.giocatori[o["controllerSeatId"] - 1].mano.append(ov)
                        stampato = costo
                        costo = pv._costo_di(o["controllerSeatId"] - 1, ov) or ""
                        if costo != stampato: nota("costi modificati dal motore (601.2f)", f"{n}: {stampato} -> {costo}")
                        mana = [tuple(1 if M.TIPI[j] == COLORE[c] else 0 for j in range(len(M.TIPI))) for c in pagati]
                        c_ = M.leggi(costo) if costo else None
                        x = len(pagati) - M.valore(costo) if c_ is not None and c_.x else 0
                        ok = M.pagabile(costo, [[m] for m in mana], x=x) if costo else not pagati
                        if not ok or (costo and len(pagati) != M.valore(costo, x)):
                            nota("mana DISCORDE", f"{n} {costo}: pagato {''.join(COLORE[c] for c in pagati)} (601.2h)")
                        else: nota("mana uguale", None)
                        for f_, c in zip(fonti, pagati):
                            src = prima.obj.get(f_) or dopo.obj.get(f_)
                            ts = carta(src) if src else None
                            if ts is None or not ts.intera: continue
                            if ts.voce[2].get("mana_colore_scelto") or ts.voce[2].get("mana_poteri_diversi"):
                                nota("fonti saltate", f"{ts.nome}: il colore scelto il log non lo dice"); continue
                            if produce(ts, COLORE[c]): nota("fonti di mana uguali (305.6, 605)", None)
                            else: nota("fonti di mana DISCORDI", f"{ts.nome} ha prodotto {COLORE[c]}")
                    # i tempi
                    if tr is not None:
                        car = tr.voce[2]
                        istantanea = "Instant" in tr.voce[1] or "flash" in car.get("parole", [])
                        zona_src = prima.tipo_zona(d.get("zone_src"))
                        if istantanea: nota("tempi di lancio uguali (117.1a, 702.8a)", None)
                        elif zona_src != "ZoneType_Hand": nota("tempi saltati", f"{n}: lanciata da {zona_src}")
                        else:
                            chi = o.get("controllerSeatId")
                            fase = prima.turno.get("phase")
                            # la pila quando il lancio e' confermato, senza la magia stessa: un'attivazione annullata e' gia' cancellata
                            pila = [x for x in seq[fine][1].in_zona("ZoneType_Stack") if x.get("grpId") != o.get("grpId")
                                    and x.get("instanceId") in prima.obj]
                            if chi == prima.turno.get("activePlayer") and fase in ("Phase_Main1", "Phase_Main2") and not pila:
                                nota("tempi di lancio uguali (117.1a, 702.8a)", None)
                            else: nota("tempi di lancio DISCORDI", f"{n} lanciata da G{chi} in {fase} con {len(pila)} in pila, attivo G{prima.turno.get('activePlayer')}")
            # 4. le terre che entrano tappate
            if d.get("category") == "PlayLand":
                for iid in a.get("affectedIds", []):
                    o = dopo.obj.get(iid)
                    tr = carta(o) if o else None
                    if tr is None or not tr.intera: continue
                    cond = (tr.voce[2].get("entra") or {}).get("tappata")
                    seat = o.get("controllerSeatId")
                    altre = [x for x in prima.in_zona("ZoneType_Battlefield") if x.get("controllerSeatId") == seat and "CardType_Land" in x.get("cardTypes", [])]
                    pw = [x for x in prima.in_zona("ZoneType_Battlefield") if x.get("controllerSeatId") == seat and "CardType_Planeswalker" in x.get("cardTypes", [])]
                    # la decide il motore (614.1d, TavoloEffetti._entra_tappata) col campo di quel momento
                    tv = tavolo_vuoto(T)
                    for x in altre + pw:
                        metti(tv, nome(x["grpId"]) or "?", "Land" if "CardType_Land" in x.get("cardTypes", []) else "Planeswalker", seat, {})
                    attesa = tv._entra_tappata(cond, seat - 1)
                    if bool(o.get("isTapped")) == attesa: nota("terre tappate uguali (614.1d)", None)
                    else: nota("terre tappate DISCORDI", f"{tr.nome}: motore {'tappata' if attesa else 'stappata'}, Arena {'tappata' if o.get('isTapped') else 'stappata'}")
            # 6. gli inneschi d'entrata
            if dopo.tipo_zona(d.get("zone_dest")) == "ZoneType_Battlefield":
                for iid in a.get("affectedIds", []):
                    o = dopo.obj.get(iid)
                    tr = carta(o) if o else None
                    if tr is None or not tr.intera or "Land" in tr.voce[1]: continue
                    tipi_c = {x.lower() for x in tr.voce[1].split("—")[0].split()}
                    def si_vede(q):                                                              # 603.6a: «this or another ... enters»
                        sel = q.get("chi") or {}
                        return q["evento"] == "una_entra" and not sel.get("altre") and sel.get("controllo") in (None, "tuo") \
                            and (not sel.get("tipi") or set(sel["tipi"]) & tipi_c) and not set(sel) - {"tipi", "controllo"}
                    attesi = sum(1 for ab in tr.voce[2].get("abilita") or [] if ab.get("tipo") == "innescata"
                                 and (ab["quando"]["evento"] == "entra" or si_vede(ab["quando"])) and "se" not in ab)
                    attese_etb[iid] = (tr.nome, attesi, k)
        di_mana = {a.get("affectorId") for a in ann if a["type"][0] == "AnnotationType_ManaPaid"}   # 605: le abilita' di mana
        for a in ann:
            # 603.6a: l'innesco d'entrata nasce mentre la carta entra (lo stesso messaggio o il seguente); gli inneschi
            # che vengono dopo (una terra giocata, uno scarto) non sono d'entrata
            if a["type"][0] == "AnnotationType_AbilityInstanceCreated" and a.get("affectorId") in attese_etb \
                    and a.get("affectorId") not in di_mana and k - attese_etb[a["affectorId"]][2] <= 1:
                scatena = {x.get("affectorId"): x.get("affectedIds", []) for x in ann if x["type"][0] == "AnnotationType_TriggeringObject"}
                attese_etb[a["affectorId"]] += tuple(i for i in a.get("affectedIds", [])
                                                     if i not in scatena or a["affectorId"] in scatena[i])   # l'oggetto che l'ha scatenato
        for iid, v in list(attese_etb.items()):
            if k - v[2] < 3: continue
            # conta le abilita' che sono davvero andate in pila (603.3): la scelta di un modo e' un oggetto di passaggio
            in_pila = {x["instanceId"] for j in range(v[2], k + 1) for x in seq[j][1].in_zona("ZoneType_Stack")}
            attivate = {i for j in range(v[2], min(v[2] + 15, len(seq))) for x in seq[j][2] if x["type"][0] == "AnnotationType_UserActionTaken"
                        for i in x.get("affectedIds", [])}                                       # 602: le attivazioni (confermate anche dopo) non sono inneschi
            visti = sum(1 for x in v[3:] if x in in_pila and x not in attivate)
            if visti == v[1]: nota("inneschi d'entrata uguali (603.6a)", None)
            elif visti > v[1]: nota("inneschi d'entrata DISCORDI", f"{v[0]}: il motore ne legge {v[1]}, Arena ne crea {visti}")
            else: nota("inneschi d'entrata DISCORDI", f"{v[0]}: il motore ne legge {v[1]}, Arena ne crea {visti}")
            del attese_etb[iid]
        # 5. forza e costituzione delle carte intere
        if tipi and k % 3 == 0:
            livelli(dopo, nota, T)
    return conti, esempi


STATICA_RIGA = re.compile(r"^([A-Z][a-z]+ — )?(When|Whenever|At|\{|[+−-][\dX]|\d+:|[^.:\"]+: |This creature enters prepared|Flying|Trample|Vigilance|Reach|Menace|Haste|"
                          r"Deathtouch|Lifelink|First strike|Double strike|Defender|Flash|Prowess|Ward|Enchant|Equip|Basic landcycling|Flashback)")


# le statiche che non cambiano l'esito di una risoluzione (danni, vite, chi lascia il campo, pescate, pedine, forza e
# costituzione): costi (601.2f, contano solo lanciando), poteri dati ai planeswalker (contano solo se si usano), parole che
# non toccano quelle misure, come entra una terra, i modi di un'abilita' («•», non sono statiche)
INNOCUE = re.compile(r"^•|cost[s]? \{[\dX]+\} (less|more)|costs \{X\} less|^Planeswalkers you control have \"\[|enters tapped|"
                     r"As it enters, choose|(have|has) (vigilance|trample|haste|flying|reach|menace)\.?$|can't be blocked|"
                     r"can attack as though|enters with an? (\+1/\+1 )?counters?|This spell can't be countered|A deck can have")


EFFETTI = {"AnnotationType_LayeredEffect", "AnnotationType_ModifiedPower", "AnnotationType_ModifiedToughness", "AnnotationType_AddAbility"}


def effetto_letto(st, a):
    """Un effetto del log che il motore calcola da se': Arena lo attacca alla creatura stessa (autore = l'oggetto
    modificato) e la carta, intera, ha un'abilita' statica che parla di se' (Winter, Dark Matter Manipulator, le
    soglie: 611.3a). Gli effetti di magie e abilita' risolte hanno un altro autore."""
    if not (set(a["type"]) & EFFETTI) or "AnnotationType_Counter" in a["type"]: return False
    ids = a.get("affectedIds", [])
    if ids and attaccata_statica(st, a.get("affectorId"), ids): return True
    if not ids or any(a.get("affectorId") != i for i in ids): return False
    o = st.obj.get(ids[0])
    tr = carta(o) if o else None
    return bool(tr is not None and tr.intera and any(ab.get("tipo") == "statica" and any((d.get("chi") or {}).get("se_stessa") for d in ab["effetti"])
                                                     for ab in tr.voce[2].get("abilita") or []))


def attaccamenti(st):
    """Le aure e gli equipaggiamenti attaccati, dal log (AnnotationType_Attachment: autore l'aura, colpito il permanente;
    301.5, 303.4b). -> {id dell'aura: id del permanente}."""
    out = {}
    for a in st.pann.values():
        if "AnnotationType_Attachment" in a.get("type", []) and a.get("affectedIds"): out[a.get("affectorId")] = a["affectedIds"][0]
    return out


def attaccata_statica(st, autore, ids):
    """Un effetto che Arena attribuisce a un'aura o a un equipaggiamento intero attaccato a quei permanenti, e che la sua
    abilita' statica su «enchanted»/«equipped» (selettore attaccata) spiega: il motore lo calcola da se'."""
    o = st.obj.get(autore)
    tr = carta(o) if o else None
    if tr is None or not tr.intera or autore not in {x.get("instanceId") for x in st.in_zona("ZoneType_Battlefield")}: return False
    if any(attaccamenti(st).get(autore) != i for i in ids): return False
    return any(ab.get("tipo") == "statica" and any((d.get("chi") or {}).get("attaccata") for d in ab["effetti"])
               for ab in tr.voce[2].get("abilita") or [])


def attacca_dal_log(t, st, mappa):
    """Le aure e gli equipaggiamenti del tavolo attaccati come nel log; poi il motore riconta le fonti dei livelli 1 e 4."""
    for au, cr in attaccamenti(st).items():
        if au in mappa and cr in mappa: mappa[au].attaccato_a = mappa[cr].n
    t._conta_bassi()
    t._versione += 1


def ignoto_in_campo(st):
    """Un permanente di una carta non intera con un'abilita' statica (che il motore non legge e che potrebbe cambiare
    l'esito), o un effetto temporaneo, o un segnalino che il log non nomina: il caso non si puo' rifare."""
    for o in st.in_zona("ZoneType_Battlefield"):
        tr = carta(o)
        if tr is not None and tr.intera: continue
        testo = " ".join(f.get("oracle") or "" for f in (tr.scheda["faces"] if tr else [])) if tr else ""
        if o.get("type") == "GameObjectType_Token" and "SubType_Jace" in o.get("subtypes", []): continue    # 701.71a: il motore lo sa
        if tr is None and "CardType_Land" not in o.get("cardTypes", []) and not o.get("isCopy") and o.get("type") == "GameObjectType_Card":
            return f"in campo una carta che il motore non conosce ({nome(o.get('grpId'))})"
        if any(not STATICA_RIGA.match(x.strip()) and not INNOCUE.search(x.strip()) for x in F.pulisci(testo).split("\n") if x.strip()):
            return f"in campo {nome(o['grpId'])}, con un'abilita' statica che il motore non legge"
    for a in st.pann.values():
        if "AnnotationType_Counter" in a["type"]:                                                  # un segnalino, non un effetto
            if dettagli(a).get("counter_type") not in SEGNALINI_LOG: return "un segnalino che il motore non conosce"
            continue
        if set(a["type"]) & EFFETTI and not effetto_letto(st, a):
            return "un effetto temporaneo in corso"
    return None


def cimiteri(t, st):
    """I cimiteri come li dice il log (404.1): ogni carta col suo nome e i tipi del log (le statiche che contano il
    cimitero, 611.3a, e le soglie li leggono)."""
    for s_ in (1, 2):
        g = t.giocatori[s_ - 1]
        g.cimitero = []
        for o in st.in_zona("ZoneType_Graveyard", s_):
            sopra = [x.replace("SuperType_", "") for x in o.get("superTypes", [])]
            tipi = [x.replace("CardType_", "") for x in o.get("cardTypes", [])]
            sotto = [x.replace("SubType_", "") for x in o.get("subtypes", [])]
            tipo = " ".join(sopra + tipi) + (" — " + " ".join(sotto) if sotto else "")
            tr = carta(o)
            c = Carta(next(t._carte), nome(o.get("grpId")) or "?", tipo or "Card", s_ - 1, car=dict(tr.voce[2]) if tr is not None else {})
            x = Oggetto(next(t._oggetti), c, "cimitero"); x.tavolo, x.ts = t, 0
            t.oggetti[x.n] = x
            g.cimitero.append(x)


def tavolo_da_log(st, T=E.TavoloEffetti):
    """Il tavolo del motore com'e' il log in quel momento: grimori e mani di carte finte (contate), il campo con le carte
    intere (il loro testo) e le altre col loro aspetto nel log, vite, danno segnato, tappati, fedelta'."""
    from tavolo import Grimorio
    t = tavolo_vuoto(T)
    mappa = {}
    for s_ in (1, 2):
        g = t.giocatori[s_ - 1]
        g.vite = st.pl.get(s_, {}).get("lifeTotal", 20)
        n_lib = len((st.zona("ZoneType_Library", s_) or {}).get("objectInstanceIds", []))
        carte = []
        for _ in range(n_lib):
            c = Carta(next(t._carte), "Finta", "Card", s_ - 1, car={})
            o = Oggetto(next(t._oggetti), c, "grimorio"); o.tavolo, o.ts = t, 0
            carte.append(o)
        g.grimorio = Grimorio(carte, seme=1)
        for _ in range(len((st.zona("ZoneType_Hand", s_) or {}).get("objectInstanceIds", []))):
            c = Carta(next(t._carte), "Finta", "Card", s_ - 1, car={})
            o = Oggetto(next(t._oggetti), c, "mano"); o.tavolo, o.ts = t, 0
            g.mano.append(o)
    cimiteri(t, st)
    for o in st.in_zona("ZoneType_Battlefield"):
        tr = carta(o)
        if tr is not None and tr.intera: nome_, tipo, car = tr.voce
        elif o.get("type") == "GameObjectType_Token" and "SubType_Jace" in o.get("subtypes", []) and "CardType_Planeswalker" in o.get("cardTypes", []):
            nome_, tipo, car = "Jace", "Token Planeswalker — Jace", dict(E.JACE)                     # 701.71a
        else:
            tipi = [x.replace("CardType_", "") for x in o.get("cardTypes", [])]
            sopra = [x.replace("SuperType_", "") for x in o.get("superTypes", [])]                 # 205.4: Legendary, Basic
            tipo = " ".join(sopra + tipi) or "Artifact"
            car = {"parole": sorted(parole_log(o))}
            if "Creature" in tipi: car.update(forza=valore(o.get("power", {})), costituzione=valore(o.get("toughness", {})))
            nome_ = nome(o.get("grpId")) or "?"
        x = metti(t, nome_, tipo, o["controllerSeatId"], dict(car))
        if o.get("type") == "GameObjectType_Token": x.carta.pedina = True
        x.danno, x.tappato = o.get("damage", 0) or 0, bool(o.get("isTapped"))
        for cod, n_ in segnalini_log(st, o["instanceId"]).items():                                 # 122.1
            if SEGNALINI_LOG.get(cod) == "+1/+1" and not (tr is not None and tr.intera): continue  # l'aspetto del log li conta gia'
            if cod in SEGNALINI_LOG and SEGNALINI_LOG[cod] != "fedelta": x.segnalini[SEGNALINI_LOG[cod]] = n_
        if "planeswalker" in x.carta.tipi: x.segnalini["fedelta"] = fedelta_log(st, o)
        mappa[o["instanceId"]] = x
    t._versione += 1                                      # i segnalini messi a mano: il motore ricalcola (613)
    attacca_dal_log(t, st, mappa)
    return t, mappa


SCELTE = ("surveil", "scry", "scarta", "cerca", "sacrifica", "prendi_tra_macinate", "togli_segnalini_scelti", "cima_o_fondo", "parola_scelta",
          "scarta_scelta_da_te")
_DB_ARENA, _TESTI_ABILITA = None, {}


def testo_abilita(aid):
    """Il testo di un'abilita' nel database delle carte di Arena (SQLite, sola lettura: Motore_Opzioni/incrocio_arena.py)."""
    global _DB_ARENA
    if aid in _TESTI_ABILITA: return _TESTI_ABILITA[aid]
    if _DB_ARENA is None:
        sys.path.insert(0, os.path.join(ROOT, "Motore_Opzioni"))
        import incrocio_arena as IA
        _DB_ARENA = (IA.apri(), IA.norm) if IA.DB else False
    if not _DB_ARENA: return None
    r = _DB_ARENA[0].execute("select l.Loc from Abilities a left join Localizations_enUS l on l.LocId=a.TextId where a.Id=?", (aid,)).fetchone()
    _TESTI_ABILITA[aid] = r[0] if r else None
    return _TESTI_ABILITA[aid]


def abilita_proprie(grp):
    """Le abilita' stampate di una carta nel database di Arena (Cards.AbilityIds, «id:testo,...»); None senza database.
    Un'abilita' che si risolve e non e' fra queste e' data da un'altra carta (Medic's Kitesail, Hunter's Axe: 613.1f)."""
    testo_abilita(0)                                                                               # apre il database
    if not _DB_ARENA or grp is None: return None
    r = _DB_ARENA[0].execute("select AbilityIds from Cards where GrpId=?", (grp,)).fetchone()
    if r is None: return None
    return {int(x.split(":")[0]) for x in (r[0] or "").split(",") if x.strip()}


def modi_scelti(o, tr, faccia=0):
    """700.2a: i modi scelti di una magia modale in pila: Arena lascia sull'oggetto solo le abilita' dei modi scelti; il
    loro testo (database di Arena) si confronta con le righe «•» del testo Oracle. -> gli indici dei modi, o None."""
    import difflib
    righe = [x.strip()[1:].strip() for x in F.pulisci(tr.scheda["faces"][faccia]["oracle"]).split("\n") if x.strip().startswith("•")]
    if not righe: return None
    norm = _DB_ARENA[1] if _DB_ARENA else None
    scelti = []
    for u in o.get("uniqueAbilities", []):
        t = testo_abilita(u.get("grpId"))
        if t is None: return None
        norm = _DB_ARENA[1]
        punti = [difflib.SequenceMatcher(None, norm(t, tr.nome), norm(r, tr.nome)).ratio() for r in righe]
        best = max(range(len(righe)), key=lambda j: punti[j])
        if punti[best] < 0.88: return None
        scelti.append(best)
    return sorted(set(scelti)) if scelti and len(set(scelti)) == len(scelti) else None


def programma_dei_modi(prog, modi):
    """Come effetti.Partita._prepara: i bersagli e le istruzioni dei modi scelti, nell'ordine stampato (700.2d)."""
    reqs, fa = [], []
    for k in sorted(modi):
        m = prog["modi"][k]
        base = len(reqs)
        reqs += list(m.get("bersagli") or [])
        for d in m.get("fa") or []:
            d = dict(d)
            for campo in ("chi", "contro"):
                v = d.get(campo)
                if isinstance(v, str) and v.startswith(("bersaglio", "controllore_bersaglio")):
                    testa, _, k2 = v.partition(":")
                    d[campo] = f"{testa}:{base + int(k2 or 0)}"
                elif isinstance(v, list):
                    d[campo] = [f"{x.partition(':')[0]}:{base + int(x.partition(':')[2] or 0)}" if isinstance(x, str) and x.startswith("bersaglio") else x for x in v]
            fa.append(d)
    return {"bersagli": reqs, "fa": fa}


def _programma_controllabile(prog):
    """-> il motivo per cui il riscontro non puo' rifarlo, o None."""
    if prog.get("modi"): return "modale (il modo scelto il log non lo dice in chiaro)"
    fa = prog.get("fa") or []
    if any(d.get("puoi") for d in fa): return "con una scelta («you may»)"
    if any(d["fa"] in SCELTE for d in fa): return "con una scelta del giocatore che il riscontro non legge"
    if any(d.get("chi") in ("evento", "carta_evento", "controllore_oggetto_evento", "oggetto_evento", "oggetti_eventi", "controllore_entrato",
                            "giocatore_evento", "magia_evento") or d.get("da") == "evento" for d in fa):
        return "legata all'evento che l'ha innescata"
    return None


def _rifai(seq, k, sid, fonti_log, prog, nome_, crea, P=E.Partita, T=E.TavoloEffetti):
    """608.2: rifa' col motore la risoluzione dell'oggetto sid (magia o abilita'), sullo stesso campo del log e con gli
    stessi bersagli, e confronta: danni, chi lascia il campo, vite, pescate, pedine, Jace, forza e costituzione dei
    bersagli. crea(t, mappa) -> l'oggetto in pila del motore. -> (discordanze, info) o (motivo del salto, None)."""
    prima = seq[k][0]
    perche = ignoto_in_campo(prima)
    if perche: return (perche, None)
    fine = next((jj for jj in range(k, min(k + 12, len(seq))) if any(x["type"][0] == "AnnotationType_ResolutionComplete" and x.get("affectorId") == sid for x in seq[jj][2])), None)
    if fine is None: return ("la risoluzione non finisce nel log", None)
    t, mappa = tavolo_da_log(prima, T)
    m = crea(t, mappa)
    if isinstance(m, str): return (m, None)
    reqs = prog.get("bersagli") or []
    gruppi = []
    for idx in sorted(BERSAGLI_ORA):
        g = []
        for x in BERSAGLI_ORA[idx]:
            if x in (1, 2): g.append(x - 1)
            elif x in mappa: g.append(mappa[x])
            else: return ("un bersaglio che non e' piu' in campo o in pila (il motore non lo ritrova)", None)
        gruppi.append(g)
    if len(gruppi) != len(reqs): return (f"bersagli: il log ne dice {len(gruppi)}, la carta {len(reqs)}", None)
    m.bersagli, m.reqs, m.fa = gruppi, reqs, list(prog.get("fa") or [])
    if not hasattr(m, "x") or m.x is None: m.x = 0
    t.pila.append(m)
    if getattr(m, "carta", None) is not None: t.oggetti[m.n] = m
    attivo = prima.turno.get("activePlayer") or 1
    t.primo = attivo - 1
    pp = P(t)
    pp.attivo = attivo - 1
    for ol in prima.in_zona("ZoneType_Battlefield"):                                              # chi sta attaccando (506)
        if ol.get("attackState") == "AttackState_Attacking" and ol["instanceId"] in mappa:
            x = mappa[ol["instanceId"]]
            tid = (ol.get("attackInfo") or {}).get("targetId")
            pp.attaccanti[x], pp._ctrl[x] = (tid - 1) if tid in (1, 2) else mappa.get(tid), x.controllore
            if ol.get("blockState") == "BlockState_Blocked": pp.bloccate.add(x)                     # 509.1h
            pp.fase = "combattimento"
    for ol in prima.in_zona("ZoneType_Battlefield"):                                              # chi sta bloccando (509.1g)
        if ol.get("blockState") == "BlockState_Blocking" and ol["instanceId"] in mappa:
            x = mappa[ol["instanceId"]]
            pp.bloccanti[x] = [mappa[i_] for i_ in (ol.get("blockInfo") or {}).get("attackerIds", []) if i_ in mappa]
            pp._ctrl[x] = x.controllore
    n0 = {x.n for x in t.campo}
    k0 = len(t.eventi)
    fonte_m = getattr(m, "fonte", m)
    try:
        pp.risolvi()
        t.azioni_di_stato()
    except (NonCoperto, RuntimeError, KeyError) as e:
        return (f"motore: {type(e).__name__} {e}", None)
    inv = {v.n: k_ for k_, v in mappa.items()}
    finestra = seq[k:fine + 1]
    for jj in range(fine + 1, min(fine + 3, len(seq))):
        tipi_j = [x["type"][0] for x in seq[jj][2]]
        if set(tipi_j) & {"AnnotationType_PhaseOrStepModified", "AnnotationType_ResolutionStart", "AnnotationType_UserActionTaken",
                          "AnnotationType_AbilityInstanceCreated", "AnnotationType_CounterRemoved", "AnnotationType_CounterAdded"} or \
                any(x["type"][0] == "AnnotationType_DamageDealt" and x.get("affectorId") not in fonti_log for x in seq[jj][2]):
            break
        finestra.append(seq[jj])
    ultimo = finestra[-1][1]
    disc = []
    danni_log = Counter()
    for _, _, ann in finestra:
        for x in ann:
            if x["type"][0] == "AnnotationType_DamageDealt" and x.get("affectorId") in fonti_log and dettagli(x).get("type") != 1:
                for y in x.get("affectedIds", []): danni_log[y] += dettagli(x).get("damage", 0)
    danni_m = Counter()
    for e in t.eventi[k0:]:
        if e.tipo == "danno" and e.vecchio in (m.n, fonte_m.n):
            danni_m[(e.giocatore + 1) if e.nuovo is None else inv.get(e.nuovo)] += e.quanto
    if danni_log != danni_m: disc.append(f"danni: motore {dict(danni_m)}, Arena {dict(danni_log)}")
    sul_log = {x["instanceId"] for x in ultimo.in_zona("ZoneType_Battlefield")}
    via_log = sorted(i_ for i_ in mappa if i_ not in sul_log)
    via_m = sorted(inv[x] for x in n0 if x not in {y.n for y in t.campo} and x in inv)
    if via_log != via_m: disc.append(f"lasciano il campo: motore {[nome(prima.obj[i_]['grpId']) for i_ in via_m]}, Arena {[nome(prima.obj[i_]['grpId']) for i_ in via_log]}")
    vite_log = [ultimo.pl.get(s_, {}).get("lifeTotal") for s_ in (1, 2)]
    vite_m = [g.vite for g in t.giocatori]
    altre_vite = any(x["type"][0] == "AnnotationType_ModifiedLife" and x.get("affectorId") not in set(fonti_log) | {1, 2} for _, _, ann in finestra for x in ann)
    if vite_log != vite_m and not altre_vite: disc.append(f"vite: motore {vite_m}, Arena {vite_log}")
    pescate_log = [0, 0]
    for _, st_, ann in finestra:
        for x in ann:
            d_ = dettagli(x)
            if x["type"][0] == "AnnotationType_ZoneTransfer" and d_.get("category") == "Draw" and x.get("affectorId") in fonti_log:
                z = st_.zone.get(d_.get("zone_dest")) or {}
                if z.get("ownerSeatId") in (1, 2): pescate_log[z["ownerSeatId"] - 1] += 1
    pescate_m = [sum(1 for e in t.eventi[k0:] if e.tipo == "zona" and e.a == "mano" and e.da == "grimorio" and e.giocatore == jj) for jj in (0, 1)]
    if pescate_log != pescate_m: disc.append(f"pescate: motore {pescate_m}, Arena {pescate_log}")
    pedine_log = sum(1 for _, _, ann in finestra for x in ann if x["type"][0] == "AnnotationType_TokenCreated" and x.get("affectorId") in fonti_log)
    pedine_m = sum(1 for e in t.eventi[k0:] if e.tipo == "zona" and e.da is None and e.a == "campo")
    if pedine_log != pedine_m: disc.append(f"pedine: motore {pedine_m}, Arena {pedine_log}")
    def jace_log(st_):
        return sorted((x["controllerSeatId"], fedelta_log(st_, x)) for x in st_.in_zona("ZoneType_Battlefield")
                      if x.get("type") == "GameObjectType_Token" and "SubType_Jace" in x.get("subtypes", []))
    jace_m = sorted((x.controllore + 1, x.segnalini["fedelta"]) for x in t.campo if x.carta.pedina and "Jace" in x.carta.tipo)
    if jace_log(ultimo) != jace_m: disc.append(f"Jace (giocatore, fedelta'): motore {jace_m}, Arena {jace_log(ultimo)}")
    for g in gruppi:
        for x in g:
            if isinstance(x, int) or not x.vivo or x.zona != "campo" or "creature" not in x.carta.tipi: continue
            ol = ultimo.obj.get(inv[x.n])
            if ol is None or "power" not in ol: continue
            if (forza(x), costituzione(x)) != (valore(ol["power"]), valore(ol["toughness"])):
                disc.append(f"{x.nome} dopo: motore {(forza(x), costituzione(x))}, Arena {(valore(ol['power']), valore(ol['toughness']))}")
    return (disc, {"magia": nome_})


BERSAGLI_ORA = {}


def magia(seq, k, a, bersagli_log, P=E.Partita, T=E.TavoloEffetti):
    """608.2: la magia intera che Arena risolve nel messaggio k, risolta dal motore."""
    global BERSAGLI_ORA
    prima = seq[k][0]
    sid = a["affectorId"]
    o = prima.obj.get(sid) or seq[k][1].obj.get(sid)
    tr = carta(o) if o else None
    if tr is None or not ({"Instant", "Sorcery"} & set(tr.voce[1].split())): return None
    if not tr.intera: return ("magia non intera", None)
    car = tr.voce[2]
    if "X" in (car.get("costo") or ""): return ("magia con X", None)
    if car.get("modi"):                                                                            # 700.2a: il modo scelto dal log
        modi = modi_scelti(o, tr, faccia=len(tr.scheda["faces"]) - 1 if tr.nome != tr.scheda["faces"][0]["name"] else 0)
        if modi is None: return ("magia modale: il modo scelto non si legge", None)
        car = dict(car, **programma_dei_modi(car, modi)); car.pop("modi")
    perche = _programma_controllabile(car)
    if perche: return ("magia " + perche, None)
    BERSAGLI_ORA = bersagli_log
    zona_lancio = None
    for jj in range(k, max(-1, k - 60), -1):                                                       # 601.2a: la zona da cui e' partita
        for x in seq[jj][2]:
            if x["type"][0] == "AnnotationType_ZoneTransfer" and dettagli(x).get("category") == "CastSpell" and sid in x.get("affectedIds", []):
                zona_lancio = seq[jj][1].tipo_zona(dettagli(x).get("zone_src")) or seq[jj][0].tipo_zona(dettagli(x).get("zone_src"))
        if zona_lancio: break
    if any(d.get("se_non_dalla_mano") for d in car.get("fa") or []) and zona_lancio is None: return ("la zona da cui e' stata lanciata non si legge", None)
    def crea(t, mappa):
        c = Carta(next(t._carte), tr.nome, tr.voce[1], o["ownerSeatId"] - 1, car=dict(car))
        m = Oggetto(next(t._oggetti), c, "pila", o["controllerSeatId"] - 1)
        m.tavolo, m.ts, m.x = t, next(t._ts), 0
        m.dalla_mano = zona_lancio in (None, "ZoneType_Hand")
        return m
    return _rifai(seq, k, sid, {sid}, car, tr.nome, crea, P, T)


def abilita_intera(seq, k, a, bersagli_log, attivate, P=E.Partita, T=E.TavoloEffetti):
    """608.2: un'abilita' (innescata o attivata) di una carta intera che Arena risolve, risolta dal motore. Si sa quale
    abilita' e' quando la carta ne ha una sola di quel genere."""
    global BERSAGLI_ORA
    prima = seq[k][0]
    sid = a["affectorId"]
    o = prima.obj.get(sid) or seq[k][1].obj.get(sid)
    if not o or o.get("type") != "GameObjectType_Ability": return None
    src_grp = o.get("objectSourceGrpId")
    tr = carta({"grpId": src_grp})
    if tr is None: return None
    if not tr.intera: return ("abilita' di una carta non intera", None)
    abil = tr.voce[2].get("abilita") or []
    if sid in attivate:
        cand = [ab for ab in abil if ab.get("tipo") == "attivata" and "fedelta" not in ab]
        if any("fedelta" in ab for ab in abil): return ("abilita' di fedelta' di una carta (si riscontra solo il Jace)", None)
    else:
        cand = [ab for ab in abil if ab.get("tipo") == "innescata"]
        if any(d.get("fa") == "ritardata" for ab in abil for d in ab.get("fa") or []):           # 603.7: anche la ritardata viene da li'
            return ("la carta crea abilita' ritardate: non si sa quale innescata si risolve", None)
    if len(cand) != 1: return (f"la carta ha {len(cand)} abilita' di quel genere: non si sa quale", None)
    proprie = abilita_proprie(src_grp)
    if proprie is not None and o.get("grpId") not in proprie:                                      # 613.1f: data da un'aura o un equipaggiamento
        return ("un'abilita' data da un'altra carta (Arena: non e' fra le abilita' della carta)", None)
    ab = cand[0]
    perche = _programma_controllabile(ab)
    if perche: return ("abilita' " + perche, None)
    if ab.get("da_parola") == "ward": return ("ward (contrasta salvo che si paghi: la scelta di pagare)", None)
    BERSAGLI_ORA = bersagli_log
    pid = o.get("parentId")
    def crea(t, mappa):
        fonte = mappa.get(pid)
        if fonte is None:                                                                          # 113.7a: la fonte se n'e' andata
            fonte = metti(t, tr.nome, tr.voce[1], o["controllerSeatId"], dict(tr.voce[2]))
            for jj in range(k, max(-1, k - 40), -1):                                               # 608.2h: com'era in campo l'ultima volta
                if any(x["instanceId"] == pid for x in seq[jj][0].in_zona("ZoneType_Battlefield")):
                    for cod, n_ in segnalini_log(seq[jj][0], pid).items():
                        if cod in SEGNALINI_LOG: fonte.segnalini[SEGNALINI_LOG[cod]] = n_
                    break
            t._versione += 1
            fonte.lki = t._valori_campo().get(fonte) or t._stampate(fonte)
            t.campo.remove(fonte); fonte.vivo = False
        k_ = (abil.index(ab))
        m = E.Abilita(next(t._oggetti), fonte, k_, ab, o["controllerSeatId"] - 1, "attivata" if sid in attivate else "innescata")
        m.x = getattr(fonte, "x_magia", 0)
        return m
    return _rifai(seq, k, sid, {sid, pid}, ab, f"{tr.nome} (abilita')", crea, P, T)


def livelli(st, nota, T=E.TavoloEffetti):
    campo = st.in_zona("ZoneType_Battlefield")
    effetti_vivi = {i for a in st.pann.values() if "AnnotationType_Counter" not in a["type"] and set(a["type"]) & EFFETTI
                    and not effetto_letto(st, a) for i in a.get("affectedIds", [])}
    segnati = defaultdict(set)
    for a in st.pann.values():
        if "AnnotationType_Counter" in a["type"]:
            for i in a.get("affectedIds", []): segnati[i].add(dettagli(a).get("counter_type"))
    sconosciute = [o for o in campo if (carta(o) is None or not carta(o).intera)
                   and re.search(r"\b(gets?|have|has) [+-]?\d|\bhave\b|\bhas\b|\bget\b", " ".join(f.get("oracle") or "" for f in (carta(o).scheda["faces"] if carta(o) else [])) or "x")]
    if sconosciute: return
    t = tavolo_vuoto(T)
    cimiteri(t, st)
    coppie, mappa = [], {}
    for o in campo:
        tr = carta(o)
        if tr is None or not tr.intera: continue
        x = metti(t, tr.nome, tr.voce[1], o["controllerSeatId"], tr.voce[2])
        mappa[o["instanceId"]] = x
        if "CardType_Creature" in o.get("cardTypes", []) and "power" in o:
            coppie.append((o, x))
    attacca_dal_log(t, st, mappa)
    for o, x in coppie:                                                                            # 122.1a, 613.4c: i segnalini, prima di ogni conto
        for cod, n_ in segnalini_log(st, o["instanceId"]).items():
            if SEGNALINI_LOG.get(cod) == "+1/+1": x.segnalini["+1/+1"] = n_
    t._versione += 1
    for o, x in coppie:
        if o["instanceId"] in effetti_vivi: nota("livelli saltati", None); continue
        if segnati.get(o["instanceId"], set()) - set(SEGNALINI_LOG): nota("livelli saltati", None); continue
        try: fc = (forza(x), costituzione(x))
        except NonCoperto as e: nota("livelli saltati", str(e)); continue
        if fc == (valore(o["power"]), valore(o["toughness"])): nota("forza e costituzione uguali (613)", None)
        else: nota("forza e costituzione DISCORDI", f"{x.nome}: motore {fc}, Arena {(valore(o['power']), valore(o['toughness']))}")


def tutto(P=E.Partita, T=E.TavoloEffetti, solo=None):
    conti, esempi = Counter(), defaultdict(list)
    lista = partite()
    if solo: lista = lista[:solo]
    for _, path in lista: riscontra(path, P, T, conti, esempi)
    return lista, conti, esempi


def scrivi(lista, conti, esempi):
    righe = ["---", "tipo: riscontro", "creato: 2026-10-14T03:30", "aggiornato: " + datetime.now().strftime("%Y-%m-%dT%H:%M"), "---", "",
             "# Il riscontro del motore con le partite di Quick Draft FRA", "",
             f"Generato da `Motore_Partita/riscontro.py` su {len(lista)} partite di Quick Draft di Reality Fracture "
             "(Espansioni/FRA/Partite, log in Log_Arena/partite). Il log di Arena e' la verita'; il motore rifa' il conto "
             "con le sue regole partendo dallo stato vero. Un caso saltato non e' un caso verde: e' scritto quanti e perche'.", "",
             "| Controllo | Uguali | Discordi | Saltati |", "| :--- | ---: | ---: | ---: |"]
    gruppi = [("Danno da combattimento (510, 702)", "combattimento uguale", "combattimento DISCORDE", "combattimento saltato"),
              ("Morti dopo il combattimento (704.5g-h)", "morti dopo il combattimento uguali (704.5g-h)", "morti dopo il combattimento DISCORDI", None),
              ("Mana pagato (601.2h)", "mana uguale", "mana DISCORDE", "mana saltato"),
              ("Costi modificati, dentro il mana pagato (601.2f)", "costi modificati dal motore (601.2f)", None, None),
              ("Fonti di mana (305.6, 605)", "fonti di mana uguali (305.6, 605)", "fonti di mana DISCORDI", None),
              ("Tempi di lancio (117.1a, 702.8a)", "tempi di lancio uguali (117.1a, 702.8a)", "tempi di lancio DISCORDI", "tempi saltati"),
              ("Terre che entrano tappate (614.1d)", "terre tappate uguali (614.1d)", "terre tappate DISCORDI", None),
              ("Forza e costituzione (613)", "forza e costituzione uguali (613)", "forza e costituzione DISCORDI", "livelli saltati"),
              ("Inneschi d'entrata (603.6a)", "inneschi d'entrata uguali (603.6a)", "inneschi d'entrata DISCORDI", None),
              ("Magie intere risolte (608.2)", "magie uguali (608.2)", "magie DISCORDI", "magie saltate"),
              ("Abilita' di carte intere risolte (608.2)", "abilita' uguali (608.2)", "abilita' DISCORDI", "abilita' saltate"),
              ("Costo di fedelta' del Jace (606.4)", "costo di fedelta' del Jace uguale (606.4)", "costo di fedelta' del Jace DISCORDE", "Jace saltati"),
              ("Abilita' della pedina Jace (701.71a)", "abilita' del Jace uguali (701.71a)", "abilita' del Jace DISCORDI", None)]
    for titolo, u, d, s_ in gruppi:
        righe.append(f"| {titolo} | {conti[u]} | {conti[d] if d else '-'} | {conti[s_] if s_ else '-'} |")
    righe += ["", "## Le discordanze e i salti, con esempi", ""]
    for chiave in sorted(esempi):
        righe.append(f"**{chiave}** ({conti[chiave]})")
        for e in esempi[chiave]: righe.append(f"- {e}")
        righe.append("")
    open(REPORT, "w", encoding="utf-8").write("\n".join(righe) + "\n")
    return REPORT


def prova():
    """Il motore giusto su tutte le partite: nessuna discordanza e abbastanza casi per ogni controllo. Poi le prove
    negative: un motore rotto apposta deve dare discordanze nel controllo giusto (se un controllo non sa trovare un
    errore messo apposta, il suo verde non vale niente)."""
    global COLORE
    casi = []
    def caso(nome_, ok, det=""): casi.append((nome_, bool(ok), det))
    lista, conti, esempi = tutto()
    discordi = {k: v for k, v in conti.items() if "DISCORD" in k}
    minimi = {"combattimento uguale": 250, "morti dopo il combattimento uguali (704.5g-h)": 250, "mana uguale": 700,
              "fonti di mana uguali (305.6, 605)": 1500, "tempi di lancio uguali (117.1a, 702.8a)": 800,
              "terre tappate uguali (614.1d)": 500, "forza e costituzione uguali (613)": 1500, "inneschi d'entrata uguali (603.6a)": 200,
              "magie uguali (608.2)": 20, "abilita' uguali (608.2)": 30, "abilita' del Jace uguali (701.71a)": 150,
              "costo di fedelta' del Jace uguale (606.4)": 150}
    scarsi = {k: conti[k] for k, v in minimi.items() if conti[k] < v}
    caso(f"il motore sulle {len(lista)} partite di Quick Draft FRA: nessuna discordanza, e ogni controllo con abbastanza casi",
         not discordi and not scarsi and len(lista) >= 40, str(discordi or scarsi or {k: conti[k] for k in minimi}))
    poche = partite()[:15]
    def rifai(P=E.Partita, T=E.TavoloEffetti, tutte=False):
        c, e = Counter(), defaultdict(list)
        for _, path in (partite() if tutte else poche): riscontra(path, P, T, c, e)
        return c
    class DannoDoppio(E.Partita):                     # il passo 6 rotto: il danno da combattimento raddoppia
        def _infliggi_tutto(self, tutte):
            super()._infliggi_tutto({o: {k: 2 * v for k, v in d.items()} for o, d in tutte.items()})
    class SenzaLegame(E.TavoloEffetti):               # 702.15b rotto
        def infliggi(self, fonte, danni, causa="120.2b"):
            vero = fonte.carta.car.get("parole")
            fonte.carta.car["parole"] = [x for x in (vero or ()) if x != "lifelink"]
            try: return super().infliggi(fonte, danni, causa)
            finally: fonte.carta.car["parole"] = vero
    class MaiTappata(E.TavoloEffetti):                # 614.1d rotto
        def _entra_tappata(self, cond, ctrl): return False
    class CostituzionePiuUno(E.TavoloEffetti):        # 613 rotto
        def costituzione_di(self, ogg): return super().costituzione_di(ogg) + 1
    class SenzaToccoMortale(E.TavoloEffetti):         # 704.5h rotto
        def azioni_di_stato(self):
            for o in self.campo: o.toccato_da_morte = False
            return super().azioni_di_stato()
    class SenzaSegnalini(E.TavoloEffetti):            # 122.1a, 613.4c rotto: i segnalini +1/+1 non contano
        def _livello_7(self, o, f, c, miei):
            vero = o.segnalini["+1/+1"]
            o.segnalini["+1/+1"] = 0
            try: return super()._livello_7(o, f, c, miei)
            finally: o.segnalini["+1/+1"] = vero
    class CimiteroVuoto(E.TavoloEffetti):             # 611.3a rotto: le statiche che contano il cimitero contano zero
        def _quanto(self, e, k):
            v = e.dati.get(k, 0)
            return 0 if isinstance(v, dict) else v
    for nome_, P, T, cerca in (("danno da combattimento raddoppiato", DannoDoppio, E.TavoloEffetti, "combattimento DISCORDE"),
                               ("i segnalini +1/+1 ignorati", E.Partita, SenzaSegnalini, "forza e costituzione DISCORDI"),
                               ("le terre doppie sempre stappate", E.Partita, MaiTappata, "terre tappate DISCORDI"),
                               ("costituzione +1 (i livelli)", E.Partita, CostituzionePiuUno, "forza e costituzione DISCORDI"),
                               ("niente legame vitale", E.Partita, SenzaLegame, "combattimento DISCORDE")):
        c2 = rifai(P, T)
        caso(f"prova negativa: {nome_}: il riscontro lo trova ({cerca})", c2[cerca] > 0, f"{c2[cerca]} discordanze")
    class DannoDallaForza(E.Partita):                 # 613.11 rotto: Ghalta the Immovable non cambia il danno assegnato
        def _danno_di(self, o): return forza(o)
    c2 = rifai(DannoDallaForza, E.TavoloEffetti, tutte=True)
    caso("prova negativa: il danno da combattimento sempre dalla forza (Ghalta the Immovable ignorato): il riscontro lo trova",
         c2["combattimento DISCORDE"] > 0, f"{c2['combattimento DISCORDE']} discordanze")
    class AttaccateSenzaEffetto(E.TavoloEffetti):    # 301.5, 303.4b rotto: le aure e gli equipaggiamenti attaccati non danno niente
        def _applica_a(self, e, o):
            if e.chi is None and (e.sel or {}).get("attaccata"): return False
            return super()._applica_a(e, o)
    c2 = rifai(E.Partita, AttaccateSenzaEffetto, tutte=True)
    caso("prova negativa: le aure e gli equipaggiamenti attaccati non danno niente (Hunter's Axe, Medic's Kitesail): il riscontro lo "
         "trova (forza e costituzione DISCORDI)", c2["forza e costituzione DISCORDI"] > 0, f"{c2['forza e costituzione DISCORDI']} discordanze")
    c2 = rifai(E.Partita, CimiteroVuoto, tutte=True)
    n2 = c2["forza e costituzione DISCORDI"] + c2["mana DISCORDE"]
    caso("prova negativa: le statiche che contano il cimitero contano zero (Winter, Dark Matter Manipulator): il riscontro lo trova",
         n2 > 0, f"{n2} discordanze")
    vere = dict(E.ISTRUZIONI)
    def danno_piu_uno(p_, d, chi, ctrl, fonte, ogg): vere["danno"][1](p_, dict(d, n=(d["n"] + 1) if isinstance(d["n"], int) else d["n"]), chi, ctrl, fonte, ogg)
    def pesca_niente(p_, d, chi, ctrl, fonte, ogg): pass
    for nome_, nuova, cerca in (("le istruzioni di danno fanno 1 in piu'", ("120.2b", danno_piu_uno), "DISCORD"),
                                ("le istruzioni di pescare non pescano", ("121.1", pesca_niente), "DISCORD")):
        chiave = "danno" if "danno" in nome_ else "pesca"
        E.ISTRUZIONI[chiave] = nuova
        try: c2 = rifai(tutte=True)
        finally: E.ISTRUZIONI[chiave] = vere[chiave]
        n2 = c2["magie DISCORDI"] + c2["abilita' DISCORDI"]
        caso(f"prova negativa: {nome_}: il riscontro delle magie e delle abilita' lo trova", n2 > 0, f"{n2} discordanze")
    vero = COLORE
    COLORE = {1: "U", 2: "W", 3: "B", 4: "R", 5: "G"}  # i colori del mana letti male: W e U scambiati
    try: c2 = rifai()
    finally: COLORE = vero
    caso("prova negativa: il bianco e il blu scambiati: il riscontro trova mana e fonti discordi",
         c2["mana DISCORDE"] > 0 and c2["fonti di mana DISCORDI"] > 0, f"{c2['mana DISCORDE']} mana, {c2['fonti di mana DISCORDI']} fonti")
    # le vite a zero (13 nov 2026): Arena non scrive lifeTotal quando e' 0; un giocatore nominato senza lifeTotal ha 0 vite
    def vite_dopo(*giocatori):
        st_ = Stato()
        r0 = json.dumps({"greToClientEvent": {"greToClientMessages": [{"gameStateMessage": {"type": "GameStateType_Full",
              "players": [dict(systemSeatNumber=1, lifeTotal=20), dict(systemSeatNumber=2, lifeTotal=3)]}}]}})
        r1 = json.dumps({"greToClientEvent": {"greToClientMessages": [{"gameStateMessage": {"type": "GameStateType_Diff", "players": list(giocatori)}}]}})
        for r_ in (r0, r1):
            ultimo_ = list(messaggi_di(st_, r_))
        return [ultimo_[-1][1].pl.get(x, {}).get("lifeTotal") for x in (1, 2)]
    v0 = vite_dopo(dict(systemSeatNumber=2))
    caso("le vite a zero: il giocatore nominato senza lifeTotal ha 0 vite", v0 == [20, 0], str(v0))
    v1 = vite_dopo(dict(systemSeatNumber=1, lifeTotal=18))
    caso("prova negativa: il giocatore non nominato tiene le sue vite (3), non 0", v1 == [18, 3], str(v1))
    scrivi(lista, conti, esempi)
    for nome_, ok, det in casi:
        print(f"  {'ok   ' if ok else 'ROSSO'} {nome_}" + (f"  [{det}]" if det else ""))
    print(f"{sum(ok for _, ok, _ in casi)}/{len(casi)}")
    return 0 if all(ok for _, ok, _ in casi) else 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if "--prova" in sys.argv: sys.exit(prova())
    lista, conti, esempi = tutto()
    print(f"{len(lista)} partite")
    for k, v in sorted(conti.items()): print(f"  {v:6} {k}")
    print(scrivi(lista, conti, esempi))
