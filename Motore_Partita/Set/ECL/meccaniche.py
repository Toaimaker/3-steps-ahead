"""Le meccaniche di ECL (Lorwyn Eclipsed) nel motore di partita: solo cio' che e' di questo set (Motore_Partita/carte_set.py).

paragrafo(c, low, orig, car, ctx, info), frase(s, ctx), costo(parte): le letture del set; ISTRUZIONI e COSTI: nel motore.

Changeling (702.73a; 14 nov 2026): «This object is every creature type», un'abilita' che definisce le caratteristiche e
funziona ovunque, anche fuori dalla partita (604.3). Si scrive come `car["tutti_i_tipi_creatura"]`; il nucleo la legge dove
confronta i tipi (effetti.ha_sottotipo, 205.3m).

Evoke (702.74a; 14 nov 2026): «You may cast this card by paying [cost] rather than paying its mana cost» e «When this permanent
enters, if its evoke cost was paid, its controller sacrifices it.» Il costo alternativo dalla mano e l'innesco col «se»
`evocata` (il permanente ricorda il costo alternativo della sua magia, `alternativo`).

Blight (701.68a-b; 14 nov 2026): «To blight N means to put N -1/-1 counters on a creature you control»; chi non controlla
creature non puo' scegliere di farlo (701.68b). Chi non sceglie mette i segnalini sulla sua creatura con la costituzione
piu' alta (quella che regge meglio). Come costo («{T}, Blight 1: ...») si paga solo con una creatura (118.3).
"""
from meccaniche_comuni import changeling

ADERISCE = [changeling]

import re

from effetti import _scelta, costituzione


def _creature(p, j):
    return [o for o in p.t.campo if o.controllore == j and "creature" in o.carta.tipi]


def _blight(p, j, n, fonte=None):
    cand = _creature(p, j)
    if not cand or n <= 0: return False                                                        # 701.68b
    pred = max(cand, key=lambda o: (costituzione(o), o.n))
    o = _scelta(p, j, "blight", cand, n, predefinita=pred)
    if o not in cand: o = pred
    p.t.metti_segnalini(o, "-1/-1", n, causa="701.68a")
    return True


def _i_blight(p, d, chi, ctrl, fonte, ogg):
    fatto = False
    for j in chi:
        if isinstance(j, int): fatto = _blight(p, j, d["n"], fonte) or fatto
    return fatto


ISTRUZIONI = {"blight": ("701.68a", _i_blight)}
QUANDO = {}
COSTI = {"blight": (lambda p, i, ogg, v: bool(_creature(p, i)), lambda p, i, ogg, v: _blight(p, i, v))}


def frase(s, ctx):
    m = re.fullmatch(r"blight (\d+)", s)
    if m: return [{"fa": "blight", "n": int(m.group(1)), "chi": "tu"}]
    m = re.fullmatch(r"each opponent blights (\d+)", s)
    if m: return [{"fa": "blight", "n": int(m.group(1)), "chi": "avversari"}]
    m = re.fullmatch(r"target opponent blights (\d+)", s)
    if m: return [{"fa": "blight", "n": int(m.group(1)), "chi": ctx.nuovo({"chi": ["player"], "controllo": "avversario"})}]
    return None


def costo(parte):
    m = re.fullmatch(r"Blight (\d+)", parte)
    if m: return {"blight": int(m.group(1))}
    return None


def _puo_evoke(p, i, ogg, alt):
    return ogg in p.t.giocatori[i].mano                                                         # 702.74a: dalla mano (qui l'unica zona)


ALTERNATIVI = {"evoke": {"puo": _puo_evoke}}
SE = {"evocata": lambda p, v, ctrl: ((getattr(p._fonte_condizione, "alternativo", None) or {}).get("nome") == "evoke") == v}   # 702.74a


def paragrafo(c, low, orig, car, ctx, info):
    m = re.fullmatch(r"evoke ((?:\{[0-9wubrgcx/]+\})+)(?: \(.*\))?", low)
    if m:                                                                                      # 702.74a: il costo e l'innesco
        car.setdefault("alternativi", []).append({"nome": "evoke", "costo": m.group(1).upper()})
        car["abilita"].append({"tipo": "innescata", "quando": {"evento": "entra"}, "se": {"evocata": True},
                               "fa": [{"fa": "sacrifica_questo", "chi": "fonte"}]})
        return True
    return changeling.paragrafo(c, low, orig, car, ctx, info)                                    # 702.73a: la condivisa
