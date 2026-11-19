"""Le meccaniche di FDN nel motore di partita: solo cio' che e' di questo set (Motore_Partita/carte_set.py).

paragrafo(c, low, orig, car, ctx, info) -> True se il paragrafo e' letto qui (e scritto in `car`), None se no.
    low e' il paragrafo normalizzato (carte_fra.normalizza: il nome della carta e' «~», tutto minuscolo); orig il testo;
    info ha modi, spell, nome, corto, prog_spell. Un paragrafo letto a meta' alza carte_fra.Mancante col perche'.
ISTRUZIONI e QUANDO si aggiungono a quelle del motore (effetti.ISTRUZIONI, effetti.QUANDO): mai un nome gia' usato.
Ogni modello cita la sua regola, letta dal file: py -I -X utf8 Motore_Opzioni/regolamento.py <numero>.
"""
from meccaniche_comuni import changeling

ADERISCE = [changeling]                                                                       # 702.73a (15 nov 2026)
ISTRUZIONI = {}
QUANDO = {}


def paragrafo(c, low, orig, car, ctx, info):
    for m in ADERISCE:
        r = m.paragrafo(c, low, orig, car, ctx, info)
        if r: return r
    return None
