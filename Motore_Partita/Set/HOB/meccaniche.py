"""Le meccaniche di HOB (The Hobbit) nel motore di partita: solo cio' che e' di questo set (Motore_Partita/carte_set.py).

paragrafo(c, low, orig, car, ctx, info) e frase(s, ctx): le letture del set; ISTRUZIONI: le azioni del set nel motore.

Amass (701.47a; 14 nov 2026): «If you don't control an Army creature, create a 0/0 black [subtype] Army creature token.
Choose an Army creature you control. Put N +1/+1 counters on that creature. If it isn't a [subtype], it becomes a [subtype]
in addition to its other types.» Chi non sceglie prende la prima Army. Il passo «becomes a [subtype]» e' un effetto di
livello 4 senza durata (613.1d, 611.2c: l'insieme fissato).
Recruit (701.70a): «Draw a card, then discard a card. If you discarded a nonland card this way, create a 1/1 white Human
Soldier creature token.» Chi non sceglie scarta l'ultima carta della mano (come gli altri scarti del motore).
Storied (702.195a-c; 14 nov 2026): «Any time you control three or more permanents that are artifacts, Sagas, and/or legendary
and you don't have an enduring story, you have an enduring story for the rest of the game.» La designazione (702.195b) sta
sul giocatore; il motore la da' come le azioni di stato (prima degli inneschi e della priorita', come chiede la 702.195c).
«As long as you have an enduring story» e' la condizione `storia_duratura` (611.3a).
"""
import re

import carte_fra as CF
from effetti import _scelta, ha_sottotipo


def _i_amass(p, d, chi, ctrl, fonte, ogg):
    st = d["sottotipo"]
    armate = [o for o in p.t.campo if o.controllore == ctrl and "creature" in o.carta.tipi and ha_sottotipo(o, "Army")]
    if not armate:
        o = p.t.crea_pedina(ctrl, f"{st} Army", f"Token Creature — {st} Army", causa="701.47a",
                            car={"forza": 0, "costituzione": 0, "colori": "B", "parole": []})
        armate = [o]
    a = _scelta(p, ctrl, "amass", armate, predefinita=armate[0])
    if a not in armate: a = armate[0]
    p.t.metti_segnalini(a, "+1/+1", d["n"], causa="701.47a")
    if not ha_sottotipo(a, st):
        p.t.aggiungi_continuo("4", {"tipi": [], "sottotipi": [st]}, chi=frozenset({a.n}), fonte=fonte, durata=None, ctrl=ctrl)
    return True


def _i_recruit(p, d, chi, ctrl, fonte, ogg):
    p.t.pesca(ctrl, 1, causa="121.1")
    mano = list(p.t.giocatori[ctrl].mano)
    if not mano: return False
    via = _scelta(p, ctrl, "scarta_effetto", mano, 1, predefinita=mano[-1:])
    via = list(via) if via else mano[-1:]
    if len(via) != 1 or via[0] not in mano: via = mano[-1:]
    p.t.scarta(via[0], causa="701.9a")
    if "land" not in via[0].carta.tipi:
        p.t.crea_pedina(ctrl, "Human Soldier", "Token Creature — Human Soldier", causa="701.70a",
                        car={"forza": 1, "costituzione": 1, "colori": "W", "parole": []})
    return True


ISTRUZIONI = {"amass": ("701.47a", _i_amass), "recruit": ("701.70a", _i_recruit)}
QUANDO = {}


def _conta_storia(t, j):
    """702.195a: i permanenti che sono artefatti, Saghe e/o leggendari."""
    return sum(1 for o in t.campo if o.controllore == j and ("artifact" in o.carta.tipi or "legendary" in o.carta.tipi
                                                                    or ha_sottotipo(o, "Saga")))


def _stato_storia(t):
    out = []
    for g in t.giocatori:
        if getattr(g, "storia_duratura", False): continue
        if any(o.controllore == g.i and o.carta.car.get("storied") for o in t.campo) and _conta_storia(t, g.i) >= 3:
            out.append(("storia_duratura", g, "702.195a"))
    return out


def _fai_storia(t, g, regola):
    g.storia_duratura = True                                                                   # 702.195b: per il resto della partita
    t._evento("storia_duratura", giocatore=g.i, causa=regola)


STATO = [_stato_storia]
FAI_STATO = {"storia_duratura": _fai_storia}
SE_STATICA = {"storia_duratura": lambda t, v, o: bool(getattr(t.giocatori[o.controllore], "storia_duratura", False)) == v}


def se_statica(cond):
    if cond == "you have an enduring story": return {"storia_duratura": True}                  # 702.195b, 611.3a
    return None


def frase(s, ctx):
    m = re.fullmatch(r"amass ([a-z]+) (\d+)", s)
    if m:
        st = CF.singolare(m.group(1)) or m.group(1)
        return [{"fa": "amass", "sottotipo": st.title(), "n": int(m.group(2))}]
    if s == "recruit": return [{"fa": "recruit"}]
    return None


def paragrafo(c, low, orig, car, ctx, info):
    if re.fullmatch(r"storied(?: \(.*\))?", low): car["storied"] = True; return True               # 702.195a
    return None
