"""Le meccaniche di MSH (Marvel Super Heroes) nel motore di partita: solo cio' che e' di questo set (Motore_Partita/carte_set.py).

paragrafo(c, low, orig, car, ctx, info) -> True se il paragrafo e' letto qui (e scritto in `car`), None se no.

Power-up (702.193; 14 nov 2026). «Power-up — [Cost]: [Effect]» e' «[Cost]: [Effect]. If this permanent entered this turn,
this ability's cost is reduced by this permanent's mana cost. Activate this ability only once.» (702.193a). Il generico del
costo di mana del permanente riduce il generico; colorato e incolore riducono mana dello stesso tipo e l'eccesso riduce il
generico (702.193b, 118.7). Un simbolo ibrido del costo di mana riduce lo stesso simbolo ibrido dell'abilita' (stesso tipo
di simbolo), se no il generico: lettura nostra della 702.193b, scritta qui.

Teamwork (702.194a-c; 14 nov 2026): «As an additional cost to cast this spell, you may tap any number of creatures you control
with total power N or more.» E' il costo facoltativo del nucleo (601.2b, `facoltativo`, come il kicker): chi lancia annuncia
se lo paga; le creature da tappare si scelgono (`teamwork`; chi non sceglie: dalla piu' forte, finche' basta). «If this spell
was cast using teamwork» (702.194b) e' il costo facoltativo pagato: la frase la legge il nucleo come «was kicked». «Choose
one. If this spell was cast using teamwork, choose both instead.»: due modi col costo pagato, uno senza. 702.194c (i
bersagli solo col teamwork) resta mancante: il nucleo non cambia i bersagli col costo facoltativo.
"""
import re

import carte_fra as CF
from effetti import _scelta, cambia_generico
from tavolo import forza


def _entrato_nel_turno(p, ogg):
    return any(e.tipo == "zona" and e.a == "campo" and e.nuovo == ogg.n for e in p._eventi_del_turno())


def riduzione_power_up(p, ab, ogg, costo):
    """702.193a-b: il costo ridotto del costo di mana del permanente, se e' entrato in questo turno."""
    if ogg is None or not _entrato_nel_turno(p, ogg): return costo
    simboli = re.findall(r"\{([^}]+)\}", costo)
    meno_generico = 0
    for s in re.findall(r"\{([^}]+)\}", ogg.carta.car.get("costo") or ""):
        if s.isdigit(): meno_generico += int(s)
        elif s in simboli: simboli.remove(s)
        else: meno_generico += 1                                                               # l'eccesso riduce il generico
    return cambia_generico("".join("{%s}" % s for s in simboli) or "{0}", -meno_generico)


ISTRUZIONI = {}
QUANDO = {}
RIDUZIONI = {"power_up": riduzione_power_up}


def _stappate(p, i):
    return [o for o in p.t.campo if o.controllore == i and "creature" in o.carta.tipi and not o.tappato]


def _puo_teamwork(p, i, ogg, n):
    return sum(max(0, forza(o)) for o in _stappate(p, i)) >= n                                   # 702.194a


def _paga_teamwork(p, i, ogg, n):
    cand = sorted(_stappate(p, i), key=lambda o: -forza(o))
    pred, tot = [], 0
    for o in cand:
        if tot >= n: break
        pred.append(o); tot += max(0, forza(o))
    scelte = _scelta(p, i, "teamwork", cand, n, predefinita=pred)
    if not (isinstance(scelte, (list, tuple)) and set(scelte) <= set(cand) and sum(max(0, forza(o)) for o in scelte) >= n): scelte = pred
    for o in scelte: p.t.tappa(o)


COSTI = {"squadra": (_puo_teamwork, _paga_teamwork)}
SQUADRA = "if this spell was cast using teamwork"


def paragrafo(c, low, orig, car, ctx, info):
    m = re.fullmatch(r"teamwork (\d+)(?: \(.*\))?", low)
    if m:                                                                                      # 702.194a
        car["facoltativo"] = {"nome": "teamwork", "squadra": int(m.group(1))}
        return True
    if info.get("spell") and low == "choose one. " + SQUADRA + ", choose both instead.":         # 700.2, 702.194b
        mm = []
        for t_ in info["modi"]:
            cm = CF.Contesto(info["nome"])
            mm.append({"fa": CF.frasi(CF.senza_nome_modo(CF.normalizza(t_, info["nome"], info["corto"])), cm), "bersagli": cm.reqs})
        if info["prog_spell"]["fa"] or len(mm) != 2: raise CF.Mancante("702.194b: i modi del teamwork")
        car["modi"], car["scegli"] = mm, {"base": 1, "facoltativo": 2}
        return True
    if info.get("spell") and SQUADRA in low and not re.match(r"(when|whenever|at) ", low):        # 702.194b: come «was kicked»
        cs = info["ctx_spell"]
        info["prog_spell"]["fa"] += CF.frasi(low.replace(SQUADRA, "if this spell was kicked"), cs)
        info["prog_spell"]["bersagli"] = cs.reqs
        return True
    m = re.fullmatch(r"power-up — (.+)", low)
    if not m: return None
    corpo_orig = orig.split("—", 1)[1].strip()
    ab = CF.attivata(corpo_orig, m.group(1).strip(), ctx)
    if not ab or ab == "mana": raise CF.Mancante("702.193a: l'abilita' di power-up non si legge")
    for a in ab:
        if not (a.get("costo") or {}).get("mana"): raise CF.Mancante("702.193a: power-up senza costo di mana")
        a["una_sola_volta"] = True                                                              # «Activate this ability only once»
        a["riduzione"] = {"set": "power_up"}
    car["abilita"] += ab
    return True
