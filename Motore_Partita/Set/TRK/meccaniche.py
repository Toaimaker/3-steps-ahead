"""Le meccaniche di TRK (Star Trek) nel motore di partita: solo cio' che e' di questo set (Motore_Partita/carte_set.py), piu' le
meccaniche condivise a cui il set aderisce (Motore_Partita/meccaniche_comuni).

paragrafo(c, low, orig, car, ctx, info) e frase(s, ctx): le letture del set.

New Planet (14 nov 2026): «Create a tapped Planet land token named New Planet with "{T}: Add one mana of any color."»: una
pedina terra (111.4, 111.10 non la definisce: le sue caratteristiche le dice il testo), tappata, col mana di ogni colore.

Beam me up (702.196a; 14 nov 2026): «You may cast this card from your graveyard if the resulting spell is an instant or sorcery
spell by paying [cost] and returning a creature you control to its owner's hand rather than paying its mana cost» e «If the
beam me up cost was paid, exile this card instead of putting it anywhere else any time it would leave the stack.» Un costo
alternativo dal cimitero (`zona` nel nucleo); la creatura si sceglie (`beam_me_up`; chi non sceglie: la prima) e torna in
mano pagando; lasciata la pila la carta va in esilio. 702.196b (una creatura che non si puo' «beam up»): nessuna carta del
perimetro lo dice.
"""
import re

from effetti import _scelta
from meccaniche_comuni import station

ADERISCE = [station]                                                                          # le condivise, in ordine
ISTRUZIONI = {k: v for m in ADERISCE for k, v in getattr(m, "ISTRUZIONI", {}).items()}
QUANDO = {k: v for m in ADERISCE for k, v in getattr(m, "QUANDO", {}).items()}


def _creature(p, i):
    return [o for o in p.t.campo if o.controllore == i and "creature" in o.carta.tipi]


def _puo_beam(p, i, ogg, alt):
    return (ogg.vivo and ogg.zona == "cimitero" and ogg.proprietario == i and bool(ogg.carta.tipi & {"instant", "sorcery"})
            and bool(_creature(p, i)))                                                         # 702.196a


def _paga_beam(p, i, magia, alt):
    cand = _creature(p, i)
    if not cand: return
    x = _scelta(p, i, "beam_me_up", cand, predefinita=cand[0])
    if x not in cand: x = cand[0]
    p.t.rimbalza(x, causa="702.196a")


def _dopo_beam(p, magia, alt):
    magia.flashback = True                                                                     # 702.196a: lasciata la pila, in esilio


ALTERNATIVI = {"beam_me_up": {"puo": _puo_beam, "zona": "cimitero", "paga": _paga_beam, "dopo": _dopo_beam}}

NEW_PLANET = 'create a tapped planet land token named new planet with "{t}: add one mana of any color."'


def frase(s, ctx):
    if s.rstrip(".") == NEW_PLANET.rstrip("."):                                                # 111.4
        return [{"fa": "pedina", "quante": 1, "nome": "New Planet", "tipo": "Token Land — Planet", "colori": "",
                 "mana": ["{W}", "{U}", "{B}", "{R}", "{G}"], "tappata": True}]
    return None


def paragrafo(c, low, orig, car, ctx, info):
    m_ = re.fullmatch(r"beam me up ((?:\{[0-9wubrgcx/]+\})+)(?: \(.*\))?", low)
    if m_:                                                                                     # 702.196a
        car.setdefault("alternativi", []).append({"nome": "beam_me_up", "costo": m_.group(1).upper()})
        return True
    for m in ADERISCE:
        if m.paragrafo(c, low, orig, car, ctx, info): return True
    return None
