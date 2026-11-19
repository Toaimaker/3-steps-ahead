"""Le meccaniche di SPM nel motore di partita: solo cio' che e' di questo set (Motore_Partita/carte_set.py).

paragrafo(c, low, orig, car, ctx, info) -> True se il paragrafo e' letto qui (e scritto in `car`), None se no.
    low e' il paragrafo normalizzato (carte_fra.normalizza: il nome della carta e' «~», tutto minuscolo); orig il testo;
    info ha modi, spell, nome, corto, prog_spell. Un paragrafo letto a meta' alza carte_fra.Mancante col perche'.
ISTRUZIONI e QUANDO si aggiungono a quelle del motore (effetti.ISTRUZIONI, effetti.QUANDO): mai un nome gia' usato.
Ogni modello cita la sua regola, letta dal file: py -I -X utf8 Motore_Opzioni/regolamento.py <numero>.

Mayhem (702.187a-b; 14 nov 2026): «As long as you discarded this card this turn, you may cast it from your graveyard by
paying [cost] rather than paying its mana cost.» Un costo alternativo dal cimitero (`zona` nel nucleo): la carta nel
cimitero e' quella arrivata scartando in questo turno (l'evento dello scarto ha lei come oggetto nuovo, 400.7). Lasciata la
pila va dove va di solito. «Mayhem» senza costo (702.187c: giocare la carta dal cimitero, anche una terra) resta mancante.

Web-slinging (702.188a; 14 nov 2026): «You may cast this spell by paying [cost] and returning a tapped creature you control to
its owner's hand rather than paying its mana cost.» Dalla mano, quando si lancerebbe di solito; la creatura tappata si
sceglie (`web_slinging`; chi non sceglie: la prima) e torna in mano pagando.
"""
import re

from effetti import SCARTI, _scelta

ISTRUZIONI = {}
QUANDO = {}


def _scartata_ora(p, i, ogg):
    """702.187b: «you discarded this card this turn»: lo scarto di questo turno che ha portato la carta qui."""
    return any(e.tipo == "zona" and e.da == "mano" and e.a == "cimitero" and e.causa in SCARTI and e.nuovo == ogg.n
               for e in p.t.eventi_del_turno())


def _puo_mayhem(p, i, ogg, alt):
    return ogg.vivo and ogg.zona == "cimitero" and ogg.proprietario == i and _scartata_ora(p, i, ogg)


def _tappate(p, i, ogg):
    return [o for o in p.t.campo if o.controllore == i and "creature" in o.carta.tipi and o.tappato and o is not ogg]


def _puo_web(p, i, ogg, alt):
    return ogg in p.t.giocatori[i].mano and bool(_tappate(p, i, ogg))                            # 702.188a: dalla mano


def _paga_web(p, i, magia, alt):
    cand = _tappate(p, i, magia)
    if not cand: return
    x = _scelta(p, i, "web_slinging", cand, predefinita=cand[0])
    if x not in cand: x = cand[0]
    p.t.rimbalza(x, causa="702.188a")


ALTERNATIVI = {"mayhem": {"puo": _puo_mayhem, "zona": "cimitero"},
               "web_slinging": {"puo": _puo_web, "paga": _paga_web}}

COSTO = r"((?:\{[0-9wubrgcx/]+\})+)"


def paragrafo(c, low, orig, car, ctx, info):
    m = re.fullmatch(r"mayhem " + COSTO + r"(?: \(.*\))?", low)
    if m:                                                                                      # 702.187b
        car.setdefault("alternativi", []).append({"nome": "mayhem", "costo": m.group(1).upper()})
        return True
    m = re.fullmatch(r"web-slinging " + COSTO + r"(?: \(.*\))?", low)
    if m:                                                                                      # 702.188a
        car.setdefault("alternativi", []).append({"nome": "web_slinging", "costo": m.group(1).upper()})
        return True
    return None
