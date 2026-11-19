"""Le meccaniche di SOS nel motore di partita: solo cio' che e' di questo set (Motore_Partita/carte_set.py).

paragrafo(c, low, orig, car, ctx, info) -> True se il paragrafo e' letto qui (e scritto in `car`), None se no.
    low e' il paragrafo normalizzato (carte_fra.normalizza: il nome della carta e' «~», tutto minuscolo); orig il testo;
    info ha modi, spell, nome, corto, prog_spell. Un paragrafo letto a meta' alza carte_fra.Mancante col perche'.
ISTRUZIONI e QUANDO si aggiungono a quelle del motore (effetti.ISTRUZIONI, effetti.QUANDO): mai un nome gia' usato.
Ogni modello cita la sua regola, letta dal file: py -I -X utf8 Motore_Opzioni/regolamento.py <numero>.

Increment (702.191a-b; 14 nov 2026): «Whenever you cast a spell, if this permanent is a creature and the amount of mana spent to
cast that spell is greater than this creature's power or this creature's toughness, put a +1/+1 counter on this creature.»
Il «se» (603.4) e' `incremento`: guarda il mana speso per la magia dell'evento (601.2h, `effetti.mana_speso`) contro forza e
costituzione di adesso. Ogni istanza scatta da se' (702.191b): una per paragrafo.
"""
import re

from effetti import mana_speso
from tavolo import costituzione, forza

ISTRUZIONI = {}
QUANDO = {}


def _incremento(p, v, ctrl):
    """702.191a: la fonte e' una creatura e il mana speso supera la sua forza o la sua costituzione."""
    f = p._fonte_condizione
    if f is None or not (f.vivo and f.zona == "campo" and "creature" in f.carta.tipi): return not v
    q = mana_speso(p.t, getattr(getattr(p, "_evento_condizione", None), "vecchio", None))[0]
    return (q > forza(f) or q > costituzione(f)) == v


SE = {"incremento": _incremento}


def paragrafo(c, low, orig, car, ctx, info):
    if re.fullmatch(r"increment(?: \(.*\))?", low):                                             # 702.191a
        car["abilita"].append({"tipo": "innescata", "quando": {"evento": "lanci"}, "se": {"incremento": True},
                               "fa": [{"fa": "segnalini", "tipo": "+1/+1", "n": 1, "chi": "fonte"}]})
        return True
    return None
