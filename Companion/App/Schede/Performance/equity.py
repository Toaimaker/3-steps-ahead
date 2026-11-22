"""L'equity di una giocata contro il range dell'avversario, anche nel Constructed (21 nov 2026; Autore: «il risolutore a regole, per portare l'equity
anche fuori da FRA: l'equity dobbiamo poterla calcolare sempre anche nel constructed, oramai ci serve perche' l'EV senza equity e' quasi inutile»).

Per ogni tua magia lanciata nel tuo turno, due esiti costruiti sul tavolo del lancio (la foto di mana_aperto «lanci», la magia in pila):
  va a segno    una creatura entra nel tuo campo (forza e costituzione stampate); una magia non creatura: il tavolo dopo, se lui non ha risposto nel
                frattempo (se ha risposto, l'effetto non si sa simulare: l'esito resta quello del tavolo del lancio, grado C)
  risposta      la magia non c'e' (contrastata, o la creatura tolta subito): il tavolo del lancio, e lui ha una carta in meno in mano
q = la probabilita' che nel tuo turno lanci una risposta che ferma, dal suo range (liste_avversarie.risposta: la lista esatta del meta quando la sua lista e'
riconosciuta, se no il ritratto del suo mazzo). Ogni tavolo ha la sua P (il modello di oggi, «se il turno finisse qui»), e
    equity = (1 - q) P(va a segno) + q P(risposta)
Nel Limited q viene dalle terre aperte (q_limited): il range della sua mano non aggiunge niente sulle partite che abbiamo.

La misura (--misura): l'equity deve prevedere il risultato della partita meglio della P del tavolo prima della giocata, senza sapere cosa ha fatto lui; la P
del tavolo dopo (che lo sa) e' il tetto. Negativa: q di un'altra giocata a caso.

    py -I -X utf8 Companion/App/Schede/Performance/equity.py --misura
    py -I -X utf8 Companion/App/Schede/Performance/equity.py --prova
"""
import os
import sys
import math
import random
import collections

_casa = os.path.dirname(os.path.abspath(__file__))
while not os.path.isfile(os.path.join(_casa, "percorsi.py")):
    _casa = os.path.dirname(_casa)
if _casa not in sys.path:
    sys.path.insert(0, _casa)
import percorsi  # noqa: E402,F401
import dati_analizzatore as DA  # noqa: E402


def _pt(nome):
    pt = ((DA._carta(nome or "") or {}).get("pt") or "").split("//")[0].strip()
    try:
        a, b = pt.split("/")
        return int(a), int(b)
    except (ValueError, AttributeError):
        return None


def tavoli(f, seat, g, nome, dopo, ha_risposto):
    """(tavolo se va a segno, tavolo se risponde) dalla foto del lancio f."""
    a, b = seat - 1, 2 - seat
    c = [list(map(list, z)) for z in (f.get("c") or [[], []])]
    n = list(f.get("n") or [0, 0])
    if "Creature" in ((DA._carta(nome or "") or {}).get("tipo") or "").split(" // ")[0]:
        pt = _pt(nome)
        if pt is None:
            return None
        c_res = [list(z) for z in c]
        c_res[a] = c_res[a] + [[g, 0, 0, pt[0], pt[1], -1, None]]
        res = dict(f, c=c_res)
    else:
        res = dopo if (dopo is not None and not ha_risposto) else f
    n_ans = list(n)
    n_ans[b] = max(0, n_ans[b] - 1)
    ans = dict(f, n=n_ans)
    return res, ans


def eventi_partita(x, righe):
    """Le tue magie lanciate nel tuo turno con la loro equity: [dict(t, nome, q, p_prima, p_res, p_ans, equity, p_dopo, ha_risposto)]."""
    import ev_partita as EV
    import liste_avversarie as LA
    d = DA._MANA.get(x.get("partita")) or {}
    seat = x.get("seat")
    lanci = d.get("lanci")
    if seat not in (1, 2) or not lanci:
        return []
    lui = 3 - seat
    fine = {t: (att, f) for t, att, f in d.get("foto") or []}
    per_t = collections.defaultdict(list)
    for l_ in lanci:
        per_t[l_[0]].append((l_[5], l_[4], l_[1]))
    for c_ in d.get("confini") or []:
        if len(c_) > 4:
            per_t[c_[0]].append((c_[4], c_[3], None))
    for v in per_t.values():
        v.sort(key=lambda e: e[0])
    out = []
    q_turno = {}
    r_turno = {}
    for t, chi, cosa, g, f, sid in lanci:
        if chi != seat or cosa == "terra" or g in DA.SENZA_FACCIA or t not in fine:
            continue
        att = fine[t][0]
        if att != seat:         # solo le magie nel tuo turno (nel suo, la risposta e' un'altra cosa)
            continue
        nome = DA.nome_intero(DA.nome_grp(g) or "")
        if not nome:
            continue
        if t not in q_turno and x.get("tipo") == "Limited":
            q_turno[t] = q_limited(x, t, righe)
        if t not in q_turno:
            r = LA.risposta(x, t, righe) if x.get("tipo") == "Constructed" else None
            r_turno[t] = r
            if r is None:
                q_turno[t] = None
            elif r.get("esatta") is not None:
                q_turno[t] = r["esatta"]["lancia"]
            else:
                q_turno[t] = min(r["p"], sum(qq for rr_, qq in r.get("cosa") or [] if rr_ in LA.INTERFERISCE)) if r["p"] else 0.0
        q = q_turno[t]
        if q is None:
            continue
        seg = [e for e in per_t[t] if e[0] > sid]
        dopo = seg[0][1] if seg else fine[t][1]
        ha_risposto = any(e[2] == lui for e in seg[:1]) or any(l_[1] == lui and l_[0] == t and sid < l_[5] < (seg[0][0] if seg else 10 ** 12)
                                                                for l_ in lanci)
        tv = tavoli(f, seat, g, nome, dopo, ha_risposto)
        if tv is None:
            continue
        p_prima = EV._p_nel_turno(f, seat, t, att, x)
        p_res = EV._p_nel_turno(tv[0], seat, t, att, x)
        p_ans = EV._p_nel_turno(tv[1], seat, t, att, x)
        p_dopo = EV._p_nel_turno(dopo, seat, t, att, x) if dopo is not None else None
        if None in (p_prima, p_res, p_ans):
            continue
        creatura = "Creature" in ((DA._carta(nome) or {}).get("tipo") or "").split(" // ")[0]
        risp, fonte = risposte_di(r_turno.get(t)) if CON_MANO else ([], None)
        mv = (DA._carta(nome) or {}).get("cmc")
        pm = p_mano(f, tv[0], seat, t, att, x, risp, creatura, p_res, mv) if risp else None
        calc = (lambda rr, f=f, res=tv[0], t=t, att=att, cr=creatura, pr=p_res, mv=mv: p_mano(f, res, seat, t, att, x, rr, cr, pr, mv))
        out.append(dict(t=t, nome=nome, q=q, p_prima=p_prima, p_res=p_res, p_ans=p_ans, equity=(1 - q) * p_res + q * p_ans, p_dopo=p_dopo,
                        ha_risposto=ha_risposto, p_mano=pm[0] if pm else None, mano=pm[1] if pm else [], fonte=fonte, risposte=risp, _calc=calc,
                        eq_mano=((1 - q) * p_res + q * pm[0]) if pm else None))
    return out


_CACHE = {}
_TASSI = {}


def _fascia(ap):
    return 0 if ap <= 0 else 1 if ap == 1 else 2


def q_limited(x, t, righe):
    """Nel Limited q viene dalle terre che ha lasciato aperte a fine del suo turno prima del tuo turno t: quanto spesso, nelle altre tue partite Limited
    con le stesse terre aperte (0, 1, 2+), ha lanciato nel tuo turno una risposta che ferma (liste_avversarie.INTERFERISCE, a velocita' istantanea).
    Il range della sua mano (Motore_EV/range_nucleo) qui non aggiunge niente: misurato il 21 nov 2026 sulle 59 partite di FRA (474 suoi turni, 25
    risposte), log-loss +0,006 ±0,005 sulle sole terre aperte, la negativa -0,002. -> q o None senza dati."""
    import liste_avversarie as LA
    e = LA.eventi(x)
    if not e or x.get("inizia") is None:
        return None
    n = (t - 1) // 2 if x.get("inizia") else t // 2
    ap = e["aperte"].get(n)
    if ap is None:
        return None
    k = (len(righe), x.get("partita"))
    if k not in _TASSI:
        if len(_TASSI) > 40:
            _TASSI.clear()
        c = collections.defaultdict(lambda: [0, 0])
        for y in righe:
            if y.get("tipo") != "Limited" or y.get("partita") == x.get("partita"):
                continue
            ey = LA.eventi(y)
            for nn, a in (ey.get("aperte") or {}).items() if ey else ():
                v = c[_fascia(a)]
                v[0] += 1
                v[1] += any(z[1] and z[2] in LA.INTERFERISCE for z in ey["nel_tuo"].get(nn) or [])
        _TASSI[k] = {f: (r + 0.5) / (n_ + 1) for f, (n_, r) in c.items() if n_ >= 10}
    return _TASSI[k].get(_fascia(ap))


def equity_partita(x, righe):
    k = (x.get("partita"), len(righe))
    if k not in _CACHE:
        if len(_CACHE) > 60:
            _CACHE.clear()
        try:
            _CACHE[k] = eventi_partita(x, righe)
        except Exception:       # noqa: BLE001
            _CACHE[k] = []
    return _CACHE[k]


def della_riga(x, t, testo, righe):
    """L'equity della riga «You cast X» del voto per fase al turno t, o None."""
    if not testo.startswith("You cast "):
        return None
    nome = DA.nome_intero(testo[len("You cast "):].strip())
    return next((e for e in equity_partita(x, righe) if e["t"] == t and e["nome"] == nome), None)


# ---------------------------------------------------------------------------------------------- la giocata contro ogni mano
# (22 nov 2026, Autore: «vai con la giocata vs mano»). L'equity di sopra ha due esiti: va a segno, o «risposta» (il tavolo del lancio, lui con una carta in
# meno), lo stesso per ogni risposta. Qui ogni risposta della sua lista fa il suo effetto, letto dal testo della carta (grado C): la contromagia ferma solo la
# magia che puo' contrastare (Negate non tocca una creatura), la rimozione toglie la tua creatura che a lui conviene di piu' fra quelle che puo' prendere
# (Cut Down solo forza + costituzione 5 o meno, Fatal Push solo valore di mana 2 o meno, il danno solo chi ha costituzione fino al danno), il rimbalzo la
# rimanda in mano, la creatura flash entra nel suo campo; una risposta che qui non ha un bersaglio o non c'entra (un trucco, Settle the Wreckage fuori dal
# combattimento) lascia andare la giocata. Lui sceglie il bersaglio peggiore per te (la P piu' bassa).
#     equity = (1 - q) P(va a segno) + q * somma_c w_c P(risposta c)
# q e' la stessa di sopra (lista esatta tarata, o il ritratto); w_c = le copie rimaste di c fra le risposte pagabili (lista esatta), o la quota del ruolo
# (ritratto: allora l'effetto e' quello tipico del ruolo).

import re

_RX_DANNO = re.compile(r"deals (\d+) damage to (?:any target|target creature|target creature or planeswalker|target creature or player)")
_RX_MENO = re.compile(r"gets -(\d+)/-(\d+)")
_RX_TOGLIE = re.compile(r"(?:destroy|exile) target (?:[a-z\-]+ )?(?:creature|nonland permanent|permanent)")
_RX_RIMBALZA = re.compile(r"return target (?:[a-z\-]+ )?(?:creature|nonland permanent|permanent)[^.]*to its owner's hand")
_RX_MV = re.compile(r"(?:mana value|converted mana cost) (\d+) or less")
_RX_PT = re.compile(r"total power and toughness (\d+) or less")
_RX_FORZA = re.compile(r"(?:with )?power (\d+) or (less|greater)")
_RX_COST = re.compile(r"with toughness (\d+) or greater")
_RX_MV_ESATTO = re.compile(r"counter target spell with mana value (\d+)")
_EFF = {}


def effetto(nome):
    """Cosa fa una risposta alla tua giocata nel tuo turno, dal testo: dict(tipo=«contra»|«toglie»|«danno»|«meno»|«rimbalza»|«flash», ...) o None."""
    if nome in _EFF:
        return _EFF[nome]
    c = DA._carta(nome or "") or {}
    tipo = (c.get("tipo") or "").split(" // ")[0]
    t = (c.get("testo") or "").lower()
    out = None
    if "Creature" in tipo:
        pt = _pt(nome)
        if pt and t.startswith("flash"):
            out = dict(tipo="flash", pt=pt)
    elif "counter target" in t:
        solo = "noncreature" if "counter target noncreature" in t else "creature" if "counter target creature spell" in t else None
        out = dict(tipo="contra", solo=solo)
        m = _RX_MV_ESATTO.search(t)
        if m:
            out["mv_esatto"] = int(m.group(1))
    else:
        vincoli = {}
        if "nonartifact" in t:
            vincoli["nonartifact"] = True
        m = _RX_MV.search(t)
        if m:
            vincoli["mv"] = int(m.group(1))
        m = _RX_PT.search(t)
        if m:
            vincoli["pt"] = int(m.group(1))
        m = _RX_FORZA.search(t)
        if m and "target creature with power" in t:
            vincoli["forza"] = (int(m.group(1)), m.group(2))
        m = _RX_COST.search(t)
        if m:
            vincoli["cost_min"] = int(m.group(1))
        if "target attacking" in t or "exile all attacking" in t:
            out = None          # solo nel combattimento: nella tua fase principale non c'entra
        elif _RX_TOGLIE.search(t):
            out = dict(tipo="toglie", **vincoli)
        elif _RX_RIMBALZA.search(t):
            out = dict(tipo="rimbalza", **vincoli)
        elif _RX_DANNO.search(t):
            out = dict(tipo="danno", n=int(_RX_DANNO.search(t).group(1)), **vincoli)
        elif _RX_MENO.search(t):
            out = dict(tipo="meno", n=int(_RX_MENO.search(t).group(2)), **vincoli)
    _EFF[nome] = out
    return out


CON_MANO = False        # la giocata contro ogni mano: misurata il 22 nov 2026 e non passata (Note/Liste_Avversarie.md), accesa solo da --misura --mano
SCELTA = "min"          # il bersaglio della sua rimozione: «min» il peggiore per te (la P piu' bassa), «forte» la tua creatura piu' grossa
EFFETTO_RUOLO = {"Counterspell": dict(tipo="contra", solo=None), "Removal": dict(tipo="toglie"), "Creature": dict(tipo="flash", pt=(2, 2))}


def _prendibile(z, eff):
    """Se la creatura z della foto [grp, tappata, pedina, forza, costituzione, id, ...] e' un bersaglio valido della risposta eff."""
    if z[3] is None or z[4] is None:
        return False
    nome = DA.nome_grp(z[0]) or ""
    c = DA._carta(nome) or {}
    if eff.get("nonartifact") and "Artifact" in (c.get("tipo") or ""):
        return False
    if "mv" in eff and (0 if z[2] else (c.get("cmc") if c.get("cmc") is not None else 99)) > eff["mv"]:
        return False
    if "pt" in eff and (z[3] or 0) + (z[4] or 0) > eff["pt"]:
        return False
    if "forza" in eff:
        n, verso = eff["forza"]
        if (verso == "less" and (z[3] or 0) > n) or (verso == "greater" and (z[3] or 0) < n):
            return False
    if "cost_min" in eff and (z[4] or 0) < eff["cost_min"]:
        return False
    if eff["tipo"] in ("danno", "meno") and (z[4] or 0) > eff["n"]:
        return False
    if "indestructible" in (c.get("testo") or "").lower() and eff["tipo"] in ("toglie", "danno"):
        return False
    return True


def esiti_mano(f, res, seat, eff, creatura, mv=None):
    """I tavoli possibili quando lui risponde con eff (lui sceglie fra questi quello peggiore per te); [] = la risposta non c'entra, la giocata va."""
    a, b = seat - 1, 2 - seat

    def meno_una(tav):
        n = list(tav.get("n") or [0, 0])
        n[b] = max(0, n[b] - 1)
        return dict(tav, n=n)
    if eff is None:
        return []
    if eff["tipo"] == "contra":
        if (eff.get("solo") == "noncreature" and creatura) or (eff.get("solo") == "creature" and not creatura) or                 ("mv_esatto" in eff and mv != eff["mv_esatto"]):
            return []
        return [meno_una(f)]
    if eff["tipo"] == "flash":
        c = [list(map(list, z)) for z in (res.get("c") or [[], []])]
        c[b] = c[b] + [[0, 0, 0, eff["pt"][0], eff["pt"][1], -2, None]]
        return [meno_una(dict(res, c=c))]
    out = []
    lato = (res.get("c") or [[], []])[a] or []
    ordine = sorted(range(len(lato)), key=lambda i: -((lato[i][3] or 0) + (lato[i][4] or 0)))      # la piu' grossa prima
    for i in ordine:
        z = lato[i]
        if not _prendibile(z, eff):
            continue
        c = [list(map(list, zz)) for zz in (res.get("c") or [[], []])]
        del c[a][i]
        tav = dict(res, c=c)
        if eff["tipo"] == "rimbalza" and not z[2]:
            n = list(tav.get("n") or [0, 0])
            n[a] += 1
            tav = dict(tav, n=n)
        out.append(meno_una(tav))
    return out


def p_mano(f, res, seat, t, att, x, risposte, creatura, p_res, mv=None):
    """La P quando lui risponde, pesata sulle sue risposte: risposte = [(eff, peso)]. -> (P, dettaglio [(nome, peso, P)]) o None."""
    import ev_partita as EV
    tot = sum(w for _e, w, _n in risposte)
    if tot <= 0:
        return None
    acc, det = 0.0, []
    for eff, w, nome in risposte:
        ps = [EV._p_nel_turno(tv, seat, t, att, x) for tv in esiti_mano(f, res, seat, eff, creatura, mv)]
        ps = [p for p in ps if p is not None]
        p = (min(ps) if SCELTA == "min" else ps[0]) if ps else p_res
        acc += w / tot * p
        det.append((nome, w / tot, p))
    return acc, det


def risposte_di(r):
    """Le risposte pesate dalla risposta di liste_avversarie: la lista esatta carta per carta, se no i ruoli del ritratto. -> ([(eff, peso, nome)], fonte)."""
    if not r:
        return [], None
    es = r.get("esatta")
    if es and es.get("nomi"):
        return [(effetto(n), k, n) for n, k in es["nomi"]], "list"
    cosa = [(ru, qq) for ru, qq in r.get("cosa") or [] if ru in EFFETTO_RUOLO]
    return [(EFFETTO_RUOLO[ru], qq, ru) for ru, qq in cosa], "roles"


# ---------------------------------------------------------------------------------------------- il combattimento
# (21 nov 2026, Autore: «fai quel che manca»: l'equity anche per attacchi e blocchi). Dalla foto prima del danno (attaccanti e blocchi dichiarati,
# mana_aperto «comb») due esiti: va come dichiarato (il risolutore qui sotto, a regole: 510, 702.2, 702.4, 702.7, 702.15, 702.19) e risposta (lui toglie
# prima del danno la tua creatura piu' forte del combattimento: rimozione, trucco, bloccante flash; grado C). q = quanto spesso, nelle altre partite dello
# stesso tipo (a gradini dal mazzo avversario verso tutte), lui ha lanciato un istantaneo prima del danno in un combattimento come questo.

def _parole(nome):
    c = DA._carta(nome or "") or {}
    t = (c.get("testo") or "").lower()
    kw = set()
    for k, s_ in (("deathtouch", "deathtouch"), ("first", "first strike"), ("double", "double strike"), ("trample", "trample"), ("lifelink", "lifelink"),
                  ("indestructible", "indestructible")):
        if s_ in t:
            kw.add(k)
    return kw


def _bloccati(info):
    out = collections.defaultdict(list)
    for b, aa in info.get("blocchi") or []:
        for x_ in (aa if isinstance(aa, list) else [aa]):
            out[x_].append(b)
    return out


def risolvi(f, att_seat, info, togli=()):
    """La foto dopo il danno di combattimento, a regole, dalla foto f prima del danno: ogni attaccante non bloccato colpisce il giocatore (un planeswalker
    attaccato no: grado C), un attaccante bloccato divide il danno fra i bloccanti nell'ordine (letale a ognuno, travolgere il resto al giocatore), ogni
    bloccante colpisce il suo attaccante; primo colpo e doppio colpo in due passi, tocco mortale, legame vitale, indistruttibile; muore chi ha danno pari
    alla costituzione. togli: gli id tolti prima del danno (la risposta). -> foto o None."""
    if not f or not info or not info.get("att"):
        return None
    a, d = att_seat - 1, 2 - att_seat
    campo = [[list(z) for z in lato or []] for lato in (f.get("c") or [[], []])]
    for i in togli:
        for lato in campo:
            lato[:] = [z for z in lato if not (len(z) > 5 and z[5] == i)]
    per_id = {z[5]: z for lato in campo for z in lato if len(z) > 5 and z[5] is not None}
    att = [i for i, _b in info["att"] if i in per_id]
    bersagli = {i: b for i, b in info["att"]}
    tutti_blk = _bloccati(info)
    blk = {i: [b for b in bb if b in per_id] for i, bb in tutti_blk.items()}
    kw = {i: _parole(DA.nome_grp(z[0]) or "") for i, z in per_id.items()}
    if any(per_id[i][3] is None for i in att):
        return None
    fo = lambda i: max(0, per_id[i][3] or 0)       # noqa: E731
    co = lambda i: per_id[i][4] or 0       # noqa: E731
    danno = collections.Counter()
    tocco = set()
    vita = list(f.get("v") or [20, 20])
    morti = set()

    def colpisce(fonte, quanto, verso, lato_vita=None):
        if quanto <= 0:
            return
        if verso is None:
            vita[lato_vita] -= quanto
        else:
            danno[verso] += quanto
            if "deathtouch" in kw[fonte]:
                tocco.add(verso)
        if "lifelink" in kw[fonte]:
            vita[a if fonte in att else d] += quanto

    for passo in (1, 2):
        def colpisce_ora(i):
            return ("first" in kw[i] or "double" in kw[i]) if passo == 1 else ("first" not in kw[i] or "double" in kw[i])
        for i in att:
            if i in morti or not colpisce_ora(i):
                continue
            p_ = fo(i)
            if i not in tutti_blk:          # non bloccato: al giocatore (un planeswalker o una battaglia, grado C: niente)
                if bersagli.get(i) in per_id:
                    continue
                colpisce(i, p_, None, d)
                continue
            for b in [b for b in blk.get(i, []) if b not in morti]:
                serve = 1 if "deathtouch" in kw[i] else max(0, co(b) - danno[b])
                x_ = min(p_, serve)
                colpisce(i, x_, b)
                p_ -= x_
            if p_ > 0 and "trample" in kw[i]:
                colpisce(i, p_, None, d)
        for i in att:
            for b in blk.get(i, []):
                if b not in morti and i not in morti and colpisce_ora(b):
                    colpisce(b, fo(b), i)
        for i in list(per_id):
            if i in morti or "indestructible" in kw[i]:
                continue
            if (co(i) > 0 and danno[i] >= co(i)) or (i in tocco and danno[i] > 0):
                morti.add(i)
    for lato in campo:
        lato[:] = [z for z in lato if not (len(z) > 5 and z[5] in morti)]
    return dict(f, c=campo, v=vita)


def _forte(f, seat_, ids):
    """L'id della creatura piu' forte (forza + costituzione) fra ids del lato di seat_, o None."""
    lato = ((f.get("c") or [[], []])[seat_ - 1]) or []
    cand = [z for z in lato if len(z) > 5 and z[5] in ids and z[3] is not None]
    return max(cand, key=lambda z: (z[3] or 0) + (z[4] or 0))[5] if cand else None


_TASSI_C = {}


def q_combattimento(x, mio_attacco, righe):
    """Quanto spesso lui lancia un istantaneo prima del danno in un combattimento come questo (tu attacchi: lui difende; tu blocchi: lui attacca), nelle
    altre partite dello stesso tipo, a gradini dal mazzo avversario verso tutte (8 combattimenti finti di tutte). -> q o None."""
    import decisioni as DEC
    k = (len(righe), x.get("tipo"))
    if k not in _TASSI_C:
        per = collections.defaultdict(collections.Counter)
        for y in righe:
            if y.get("tipo") != x.get("tipo"):
                continue
            for dz in DEC.per_partita(y, con_p=False):
                if dz["tipo"] == "blocco" and not dz["bloccato"]:
                    continue
                ma = dz["tipo"] == "attacco"
                for a_ in (y.get("suo") or "?", "*"):
                    c = per[(ma, a_)]
                    c["n"] += 1
                    c["y"] += bool(dz["trucco_suo"])
                    c[("g", y.get("partita"))] += 1
                    c[("gy", y.get("partita"))] += bool(dz["trucco_suo"])
        _TASSI_C[k] = per
    per = _TASSI_C[k]
    g = x.get("partita")
    tutti = per.get((mio_attacco, "*"))
    if not tutti:
        return None
    n_t, y_t = tutti["n"] - tutti[("g", g)], tutti["y"] - tutti[("gy", g)]
    if n_t < 20:
        return None
    base = y_t / n_t
    ar = per.get((mio_attacco, x.get("suo") or "?")) or collections.Counter()
    n_a, y_a = ar["n"] - ar[("g", g)], ar["y"] - ar[("gy", g)]
    return (y_a + 8 * base) / (n_a + 8)


def eventi_combattimento(x, righe):
    """I tuoi attacchi e i tuoi blocchi con la loro equity: [dict(t, tipo, q, p_prima, p_res, p_ans, equity, p_dopo, ha_risposto)]."""
    import decisioni as DEC
    import ev_partita as EV
    d = DA._MANA.get(x.get("partita")) or {}
    seat = x.get("seat")
    mom = d.get("momenti") or []
    if seat not in (1, 2) or not mom:
        return []
    m2 = {c_[0]: c_[3] for c_ in d.get("confini") or [] if len(c_) > 3 and c_[2] == "m2"}
    dz = {(z["t"], z["tipo"]): z for z in DEC.per_partita(x, con_p=False)}
    lui = 3 - seat
    out = []
    for m in mom:
        if m[0] != "comb" or len(m) < 5 or not m[4] or not m[4].get("att"):
            continue
        t, att, f, info = m[1], m[2], m[3], m[4]
        mio = att == seat
        if not mio and not info.get("blocchi"):
            continue        # nessun tuo blocco: non c'e' una tua decisione da pesare contro il suo trucco
        q = q_combattimento(x, mio, righe)
        if q is None:
            continue
        res = risolvi(f, att, info)
        if res is None:
            continue
        ids = {i for i, _b in info["att"]} if mio else {b for b, _aa in info["blocchi"]}
        via = _forte(f, seat, ids)
        ans = risolvi(f, att, info, togli=(via,) if via else ())
        if ans is None:
            continue
        n_ans = list(ans.get("n") or [0, 0])
        n_ans[lui - 1] = max(0, n_ans[lui - 1] - 1)
        ans = dict(ans, n=n_ans)
        p_prima = EV._p_nel_turno(f, seat, t, att, x)
        p_res = EV._p_nel_turno(res, seat, t, att, x)
        p_ans = EV._p_nel_turno(ans, seat, t, att, x)
        dopo = m2.get(t)
        p_dopo = EV._p_nel_turno(dopo, seat, t, att, x) if dopo is not None else None
        if None in (p_prima, p_res, p_ans):
            continue
        z = dz.get((t, "attacco" if mio else "blocco")) or {}
        out.append(dict(t=t, tipo="attack" if mio else "block", q=q, p_prima=p_prima, p_res=p_res, p_ans=p_ans,
                        equity=(1 - q) * p_res + q * p_ans, p_dopo=p_dopo, ha_risposto=bool(z.get("trucco_suo"))))
    return out


_CACHE_C = {}


def combattimento_partita(x, righe):
    k = (x.get("partita"), len(righe))
    if k not in _CACHE_C:
        if len(_CACHE_C) > 60:
            _CACHE_C.clear()
        try:
            _CACHE_C[k] = eventi_combattimento(x, righe)
        except Exception:       # noqa: BLE001
            _CACHE_C[k] = []
    return _CACHE_C[k]



def della_riga_combattimento(x, t, testo, righe):
    """L'equity della riga «You attacked with ...» o «You blocked ...» del voto per fase al turno t, o None."""
    if testo.startswith("You attacked with "):
        tipo = "attack"
    elif testo.startswith("You blocked "):
        tipo = "block"
    else:
        return None
    return next((e for e in combattimento_partita(x, righe) if e["t"] == t and e["tipo"] == tipo), None)

def misura(log=print, seme=7, tipo="Constructed", quali="magie"):
    import numpy as np
    R = DA.righe()
    ev = []
    for x in R:
        if x.get("tipo") != tipo:
            continue
        evs = eventi_partita(x, R) if quali == "magie" else [e for e in eventi_combattimento(x, R) if e["tipo"] == quali]
        for e in evs:
            ev.append(dict(e, g=x["partita"], y=1.0 if x["vinta"] else 0.0))
    if len(ev) < 50:
        log(f"troppo pochi eventi: {len(ev)}")
        return None
    rng = random.Random(seme)
    for e in ev:
        q2 = ev[rng.randrange(len(ev))]["q"]
        e["eq_neg"] = (1 - q2) * e["p_res"] + q2 * e["p_ans"]
    colonne = ["P before the play", "equity", "equity, negative", "P after (knows his answer)"]
    mappa = {"P before the play": "p_prima", "equity": "equity", "equity, negative": "eq_neg", "P after (knows his answer)": "p_dopo"}
    if quali == "magie" and "--mano" in sys.argv:       # la giocata contro ogni mano: solo dove c'e', e la negativa con le risposte di un'altra giocata
        ev = [e for e in ev if e.get("eq_mano") is not None]
        con = [e for e in ev if e["risposte"]]
        for e in ev:
            altra = con[rng.randrange(len(con))]["risposte"]
            pm = e["_calc"](altra)
            e["eq_mano_neg"] = (1 - e["q"]) * e["p_res"] + e["q"] * pm[0] if pm else e["eq_mano"]
        colonne[2:2] = ["vs every hand", "vs every hand, negative"]
        mappa.update({"vs every hand": "eq_mano", "vs every hand, negative": "eq_mano_neg"})
        fonti = collections.Counter(e["fonte"] for e in ev)
        cambia = sum(1 for e in ev if abs(e["eq_mano"] - e["equity"]) >= 1)
        log(f"vs every hand: {len(ev)} plays ({dict(fonti)}), {cambia} with the equity moved by 1+ point")
    lg = lambda p: math.log(min(0.99, max(0.01, p / 100)) / (1 - min(0.99, max(0.01, p / 100))))
    giochi = sorted({e["g"] for e in ev})
    ris = collections.defaultdict(list)
    for s_ in range(6):
        r_ = random.Random(s_)
        gg = giochi[:]
        r_.shuffle(gg)
        A = set(gg[: len(gg) // 2])
        for nome in colonne:
            col = mappa[nome]
            evv = [e for e in ev if e[col] is not None]
            Xa = np.array([[1.0, lg(e[col])] for e in evv if e["g"] in A]); ya = np.array([e["y"] for e in evv if e["g"] in A])
            Xb = np.array([[1.0, lg(e[col])] for e in evv if e["g"] not in A]); yb = np.array([e["y"] for e in evv if e["g"] not in A])
            w = np.zeros(2)
            for _ in range(40):
                pp = 1 / (1 + np.exp(-(Xa @ w)))
                w -= np.linalg.solve((Xa.T * (pp * (1 - pp))) @ Xa + 1e-3 * np.eye(2), Xa.T @ (pp - ya) + 1e-3 * w)
            pb = np.clip(1 / (1 + np.exp(-(Xb @ w))), 1e-6, 1 - 1e-6)
            ris[nome].append(float(np.mean(-(yb * np.log(pb) + (1 - yb) * np.log(1 - pb)))))
    base = np.array(ris["P before the play"])
    log(f"L'equity contro il range ({tipo}, {quali}, {len(ev)} eventi, {len(giochi)} partite; risposto davvero {sum(e['ha_risposto'] for e in ev)}): "
        "log-loss del risultato sulla meta' non vista, sei divisioni")
    for nome in colonne:
        v = np.array(ris[nome])
        log(f"  {nome:28} {v.mean():.4f}  (meno la P di prima {np.mean(v - base):+.4f}, da {np.min(v - base):+.4f} a {np.max(v - base):+.4f})")
    return ris


def prova():
    casi = []
    f = dict(c=[[[1, 0, 0, 2, 2, 10, None]], [[2, 0, 0, 3, 3, 11, None]]], n=[4, 5], v=[20, 20], m=[[], []], g=[[], []], e=[[], []])
    vero = DA._carta
    DA._carta = lambda n: {"Orso": {"tipo": "Creature — Bear", "pt": "2/2"}, "Fulmine": {"tipo": "Instant"}}.get(n)
    try:
        res, ans = tavoli(f, 1, 99, "Orso", None, False)
        casi.append(("va a segno: la creatura entra nel tuo campo", len(res["c"][0]) == 2 and res["c"][0][-1][3:5] == [2, 2]))
        casi.append(("risposta: lui ha una carta in meno, il tuo campo resta", ans["n"] == [4, 4] and len(ans["c"][0]) == 1))
        dopo = dict(f, v=[20, 17])
        res2, _a = tavoli(f, 1, 98, "Fulmine", dopo, False)
        casi.append(("una magia non creatura senza risposta: il tavolo dopo", res2 is dopo))
        res3, _a = tavoli(f, 1, 98, "Fulmine", dopo, True)
        casi.append(("negativa: se ha risposto, l'effetto non si simula (il tavolo del lancio)", res3 is f))
        DA._carta = lambda n: {"Senza": {"tipo": "Creature — X", "pt": "*/*"}}.get(n)
        casi.append(("negativa: una creatura senza forza stampata non si stima", tavoli(f, 1, 97, "Senza", None, False) is None))
    finally:
        DA._carta = vero
    # la giocata contro ogni mano
    vero_c, vero_n = DA._carta, DA.nome_grp
    carte = {"Negate": dict(tipo="Instant", testo="Counter target noncreature spell."),
             "Cut Down": dict(tipo="Instant", testo="Destroy target creature with total power and toughness 5 or less."),
             "Shock": dict(tipo="Instant", testo="Shock deals 2 damage to any target."),
             "Unsummon": dict(tipo="Instant", testo="Return target creature to its owner's hand."),
             "Kirin": dict(tipo="Creature — Kirin", pt="2/1", testo="Flash Flying"),
             "Giant Growth": dict(tipo="Instant", testo="Target creature gets +3/+3 until end of turn."),
             "Orso": dict(tipo="Creature — Bear", pt="2/2", cmc=2, testo=""), "Drago": dict(tipo="Creature — Dragon", pt="5/5", cmc=5, testo="")}
    _EFF.clear()
    DA._carta = lambda n: carte.get(n)
    DA.nome_grp = lambda g: {1: "Orso", 2: "Drago"}.get(g)
    try:
        f = dict(c=[[[1, 0, 0, 2, 2, 10, None]], []], n=[4, 5], v=[20, 20])
        res = dict(f, c=[[[1, 0, 0, 2, 2, 10, None], [2, 0, 0, 5, 5, -1, None]], []])
        casi.append(("mano: Negate non ferma una creatura", esiti_mano(f, res, 1, effetto("Negate"), True) == []))
        casi.append(("mano: Negate ferma una magia non creatura (il tavolo del lancio, lui una carta in meno)",
                     esiti_mano(f, f, 1, effetto("Negate"), False) == [dict(f, n=[4, 4])]))
        e = esiti_mano(f, res, 1, effetto("Cut Down"), True)
        casi.append(("mano: Cut Down prende l'Orso 2/2 e non il Drago 5/5", len(e) == 1 and [z[5] for z in e[0]["c"][0]] == [-1]))
        e = esiti_mano(f, res, 1, effetto("Shock"), True)
        casi.append(("mano: Shock uccide solo chi ha costituzione 2 o meno", len(e) == 1 and [z[5] for z in e[0]["c"][0]] == [-1]))
        e = esiti_mano(f, res, 1, effetto("Unsummon"), True)
        casi.append(("mano: Unsummon rimanda in mano (la tua mano +1), due bersagli possibili", len(e) == 2 and all(t_["n"] == [5, 4] for t_ in e)))
        e = esiti_mano(f, res, 1, effetto("Kirin"), True)
        casi.append(("mano: la creatura flash entra nel suo campo", len(e) == 1 and e[0]["c"][1][0][3:5] == [2, 1]))
        casi.append(("negativa: un trucco non c'entra con la tua giocata", effetto("Giant Growth") is None
                     and esiti_mano(f, res, 1, effetto("Giant Growth"), True) == []))
    finally:
        DA._carta, DA.nome_grp = vero_c, vero_n
        _EFF.clear()
    # il risolutore del combattimento
    vero_c, vero_n = DA._carta, DA.nome_grp
    testi = {1: "", 2: "", 3: "Deathtouch", 4: "Trample", 5: "First strike", 6: "Lifelink"}
    DA.nome_grp = lambda g: f"c{g}"
    DA._carta = lambda n: {"testo": testi.get(int(n[1:]), "")} if n and n[0] == "c" else None
    try:
        f = dict(c=[[[1, 1, 0, 3, 3, 101, None], [4, 1, 0, 5, 2, 102, None]], [[2, 0, 0, 2, 2, 201, None], [3, 0, 0, 1, 1, 202, None]]], v=[20, 20], n=[3, 3])
        r = risolvi(f, 1, dict(att=[[101, 2], [102, 2]], blocchi=[[201, [101]]]))
        casi.append(("combattimento: il 3/3 uccide il 2/2 che lo blocca e resta vivo, il 5/2 non bloccato fa 5", r["v"][1] == 15
                     and {z[5] for z in r["c"][0]} == {101, 102} and {z[5] for z in r["c"][1]} == {202}))
        r = risolvi(f, 1, dict(att=[[101, 2]], blocchi=[[202, [101]]]))
        casi.append(("tocco mortale: il 1/1 che blocca uccide il 3/3", {z[5] for z in r["c"][0]} == {102} and 202 not in {z[5] for z in r["c"][1]}))
        r = risolvi(f, 1, dict(att=[[102, 2]], blocchi=[[201, [102]]]))
        casi.append(("travolgere: 5 contro un 2/2, 3 passano; il 5/2 muore", r["v"][1] == 17 and 102 not in {z[5] for z in r["c"][0]}))
        f2 = dict(f, c=[[[5, 1, 0, 2, 2, 103, None]], [[2, 0, 0, 2, 2, 201, None]]])
        r = risolvi(f2, 1, dict(att=[[103, 2]], blocchi=[[201, [103]]]))
        casi.append(("primo colpo: il 2/2 colpisce prima e non muore", 103 in {z[5] for z in r["c"][0]} and not r["c"][1]))
        f3 = dict(f, c=[[[6, 1, 0, 3, 3, 104, None]], []])
        r = risolvi(f3, 1, dict(att=[[104, 2]], blocchi=[]))
        casi.append(("legame vitale: 3 a lui e 3 a te", r["v"] == [23, 17]))
        r = risolvi(f, 1, dict(att=[[101, 2], [102, 2]], blocchi=[[201, [101]]]), togli=(102,))
        casi.append(("risposta: tolto il 5/2 prima del danno, niente danno a lui", r["v"][1] == 20 and 102 not in {z[5] for z in r["c"][0]}))
        casi.append(("negativa: senza attaccanti nessun esito", risolvi(f, 1, dict(att=[], blocchi=[])) is None))
    finally:
        DA._carta, DA.nome_grp = vero_c, vero_n
    for n, ok in casi:
        print(("ok    " if ok else "ROSSO ") + n)
    print(f"{sum(1 for _n, ok in casi if ok)}/{len(casi)}")
    return all(ok for _n, ok in casi)


if __name__ == "__main__":
    if "--prova" in sys.argv:
        sys.exit(0 if prova() else 1)
    if "--misura" in sys.argv:
        CON_MANO = "--mano" in sys.argv
        misura(tipo="Limited" if "--limited" in sys.argv else "Constructed",
               quali="attack" if "--attacchi" in sys.argv else "block" if "--blocchi" in sys.argv else "magie")
