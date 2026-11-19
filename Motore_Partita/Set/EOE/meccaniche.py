"""Le meccaniche di EOE (Edge of Eternities) nel motore di partita: solo cio' che e' di questo set (Motore_Partita/carte_set.py),
piu' le meccaniche condivise a cui il set aderisce (Motore_Partita/meccaniche_comuni).

paragrafo(c, low, orig, car, ctx, info): le letture del set; ISTRUZIONI e ALTERNATIVI: nel motore.

Warp (702.185a-c; 14 nov 2026). «Warp [cost]» e' «You may cast this card from your hand by paying [cost] rather than its mana
cost» e «If this spell's warp cost was paid, exile the permanent this spell becomes at the beginning of the next end step.
Its owner may cast this card after the current turn has ended for as long as it remains exiled.» Il costo alternativo lo
annuncia chi lancia (la mossa del motore `("alternativo", carta, "warp", ...)`); il permanente porta un'abilita' innescata
ritardata (603.7) che lo esilia alla prossima fase finale; dall'esilio si lancia col suo costo di mana, dal turno dopo.

Void (14 nov 2026): una parola d'abilita' (207.2c), senza regole sue; la condizione «if a nonland permanent left the
battlefield this turn or a spell was warped this turn» e' il «se» dell'innesco (603.4: vera quando scatta e quando si
risolve): un permanente non terra uscito dal campo in questo turno, o una magia lanciata col warp (702.185c, l'evento «warp»).
"""
import re

from meccaniche_comuni import station

ADERISCE = [station]


def _puo_warp(p, i, ogg, alt):
    return ogg in p.t.giocatori[i].mano                                                         # «from your hand»


def _dopo_warp(p, magia, alt):
    p.t._evento("warp", carta=magia.carta, vecchio=magia.n, giocatore=magia.controllore, causa="702.185c")   # «a spell was warped»


def _entra_warp(p, perm, alt):
    """702.185a: alla prossima fase finale il permanente va in esilio (un'abilita' ritardata, 603.7)."""
    ab = {"tipo": "innescata", "quando": {"evento": "inizio_passo", "passo": "finale"}, "una_volta": True, "ricordati": [perm.n],
          "fa": [{"fa": "warp_esilia", "chi": "ricordati"}]}
    p.ritardate.append({"ab": ab, "ctrl": perm.controllore, "fonte": perm, "fino": "sempre",
                        "dopo": p.t.eventi[-1].n if p.t.eventi else -1, "turno": p.t.turno_numero})


def _i_warp_esilia(p, d, chi, ctrl, fonte, ogg):
    """702.185a-b: esilia il permanente; il proprietario puo' lanciare la carta finche' resta in esilio, dal turno dopo."""
    for x in chi:
        nuovo = p.t.esilia(x, causa="702.185a")
        if nuovo is None: continue
        nuovo.warpata = True                                                                   # 702.185b: «warped card in exile»
        p.permessi.append({"n": nuovo.n, "giocatore": nuovo.proprietario, "fino": "finche_in_esilio", "iniziato": False,
                           "dal_turno": p.t.turno_numero + 1})
        p.t._evento("permesso", carta=nuovo.carta, vecchio=nuovo.n, giocatore=nuovo.proprietario, a="finche_in_esilio", causa="702.185a")


ISTRUZIONI = dict({"warp_esilia": ("702.185a", _i_warp_esilia)}, **{k: v for m in ADERISCE for k, v in getattr(m, "ISTRUZIONI", {}).items()})
QUANDO = {k: v for m in ADERISCE for k, v in getattr(m, "QUANDO", {}).items()}
ALTERNATIVI = {"warp": {"puo": _puo_warp, "dopo": _dopo_warp, "entra": _entra_warp}}


def _void(p, v, ctrl):
    """603.4, 702.185c: un permanente non terra ha lasciato il campo in questo turno, o una magia e' stata warpata."""
    fatto = any((e.tipo == "zona" and e.da == "campo" and e.carta is not None and "land" not in e.carta.tipi) or e.tipo == "warp"
                for e in p.t.eventi_del_turno())
    return fatto == v


SE = {"void": _void}
VOID = "if a nonland permanent left the battlefield this turn or a spell was warped this turn, "


def se_innesco(resto):
    if resto.startswith(VOID): return resto[len(VOID):], {"void": True}
    return None


def paragrafo(c, low, orig, car, ctx, info):
    m = re.fullmatch(r"warp ((?:\{[0-9wubrgcx]\})+)", low)
    if m:                                                                                      # 702.185a
        car.setdefault("alternativi", []).append({"nome": "warp", "costo": m.group(1).upper()})
        return True
    for x in ADERISCE:
        if x.paragrafo(c, low, orig, car, ctx, info): return True
    return None
