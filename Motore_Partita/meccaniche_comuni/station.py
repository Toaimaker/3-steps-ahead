"""Station, meccanica condivisa (EOE e TRK aderiscono dai loro posti; nata in Set/EOE il 14 nov 2026).

Station (702.184a, 722; 14 nov 2026). «Station» e' «Tap another untapped creature you control: Put a number of charge
counters on this permanent equal to the tapped creature's power. Activate only as a sorcery.» (702.184a). Un simbolo
«N+ | [abilita']» e' un'abilita' statica: finche' il permanente ha N o piu' segnalini carica ha quelle abilita' (722.2a);
con il riquadro forza/costituzione e' anche una creatura con quella forza e costituzione base (722.2b). Il riquadro non
compare nel testo Oracle: la soglia della creatura si legge dal testo di richiamo della carta («It's an artifact creature
at 8+»), che dice dove sta il riquadro; la forza e la costituzione sono quelle stampate (301.7b come i veicoli).
"""
import re
import sys

import carte_fra as CF
from effetti import forza

CARICA = "carica"                                                                              # 122.1: i segnalini carica


def _station_carica(p, d, chi, ctrl, fonte, ogg):
    """702.184a: tanti segnalini carica quanto la forza della creatura tappata per il costo (702.184c: quella di adesso
    se e' ancora in campo, se no l'ultima nota quando e' stata tappata)."""
    n = 0
    for num, f_ in getattr(ogg, "tappati_costo", None) or []:
        o = p.t.oggetti.get(num)
        n += forza(o) if o is not None and o.vivo and o.zona == "campo" and "creature" in o.carta.tipi else (f_ or 0)
    for x in chi:
        if n > 0: p.t.metti_segnalini(x, CARICA, n, causa="702.184a")


ISTRUZIONI = {"station_carica": ("702.184a", _station_carica)}
QUANDO = {}


def _soglia(n):
    return {"segnalini_almeno": {"tipo": CARICA, "n": n}}


def paragrafo(c, low, orig, car, ctx, info):
    if low == "station":                                                                       # 702.184a
        car["abilita"].append({"tipo": "attivata", "costo": {"tappa_altri": {"tipi": ["creature"], "n": 1, "altro": True}},
                               "velocita": "stregoneria", "fa": [{"fa": "station_carica", "chi": "fonte"}]})
        m = re.search(r"It's an artifact creature at (\d+)\+", c["faces"][0]["oracle"])
        if m:                                                                                  # 722.2b: la soglia del riquadro
            if car.get("forza") is None: raise CF.Mancante("722.2b: una soglia di creatura senza forza e costituzione stampate")
            car["abilita"].append({"tipo": "statica", "effetti": [
                {"livello": "4", "chi": {"se_stessa": True}, "tipi": ["artifact", "creature"], "se": _soglia(int(m.group(1)))}]})
        elif car.get("forza") is not None:
            raise CF.Mancante("722.2b: forza e costituzione stampate ma nessuna soglia di creatura nel testo di richiamo")
        return True
    m = re.fullmatch(r"(\d+)\+ \| (.+)", low)
    if not m: return None
    n, corpo = int(m.group(1)), m.group(2).strip()                                             # 722.2a
    corpo_orig = orig.split("|", 1)[1].strip()
    parole = [x.strip() for x in re.split(r",\s*", corpo.rstrip("."))]
    if all(x in CF.PAROLE_SEMPLICI for x in parole):
        eff = {"livello": "6", "chi": {"se_stessa": True}, "dai": parole, "se": _soglia(n)}
    else:
        ab = CF.innesco(corpo, ctx)
        if ab is None:
            ab = CF.attivata(corpo_orig, corpo, ctx)
            if ab == "mana": raise CF.Mancante("722.2a: un'abilita' di mana dietro una soglia")
        if not ab: raise CF.Mancante(f"722.2a: l'abilita' della soglia {n}+ non si legge")
        if any(a.pop("modi_da_leggere", None) for a in ab): raise CF.Mancante("722.2a: una soglia con i modi")
        eff = {"livello": "6", "chi": {"se_stessa": True}, "dai_abilita": ab, "se": _soglia(n)}
    car["abilita"].append({"tipo": "statica", "effetti": [eff]})
    return True
