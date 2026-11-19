"""Le meccaniche di FIN (Final Fantasy) nel motore di partita: solo cio' che e' di questo set (Motore_Partita/carte_set.py).

Job select (702.182a, 14 nov 2026): «Job select is a triggered ability. "Job select" means "When this Equipment enters,
create a 1/1 colorless Hero creature token, then attach this Equipment to it."»

Tiered (702.183a, 14 nov 2026): «Tiered is a static ability found on some modal spells ... Tiered means "Choose one. As an
additional cost to cast this spell, pay the cost associated with that mode."» I modi stanno nei paragrafi dopo, «• Nome —
{costo} — testo»; il costo del modo scelto lo somma il nucleo al costo totale (601.2f, `costo_modo`).
"""
import re

import carte_fra as CF


def magia(par, k, car, nome):
    if par[k] != "tiered (choose one additional cost.)" and par[k] != "tiered": return None
    mm, j = [], k + 1
    while j < len(par) and par[j].startswith("•"):
        m = re.fullmatch(r"•\s*[^—]+ — ((?:\{[0-9wubrgc]\})+) — (.+)", par[j])
        if not m: raise CF.Mancante("702.183a: un modo di tiered non si legge")
        cm = CF.Contesto(nome)
        mm.append({"fa": CF.frasi(m.group(2), cm), "bersagli": cm.reqs, "costo_modo": m.group(1).upper()})
        j += 1
    if len(mm) < 2: raise CF.Mancante("702.183a: tiered senza modi")
    car["modi"], car["scegli"] = mm, 1
    return j


ISTRUZIONI = {}
QUANDO = {}


HERO = {"fa": "pedina", "quante": 1, "nome": "Hero", "tipo": "Token Creature — Hero", "forza": 1, "costituzione": 1, "colori": "", "parole": []}


def paragrafo(c, low, orig, car, ctx, info):
    if re.fullmatch(r"job select(?: \(.*\))?", low):                                              # 702.182a
        if "Equipment" not in (c.get("faces") or [{}])[0].get("type", ""): raise CF.Mancante("702.182a: job select fuori da un equipaggiamento")
        car["abilita"].append({"tipo": "innescata", "quando": {"evento": "entra"},                # come mobilize: l'innesco, senza la
                               "fa": [dict(HERO), {"fa": "attacca", "chi": "create"}]})          # parola nelle caratteristiche
        return True
    if not (info.get("spell") and re.fullmatch(r"tiered(?: \(choose one additional cost\.\))?", low)): return None
    mm = []
    for t_ in info["modi"]:                                                                      # 702.183a: «• Nome — {costo} — testo»
        m = re.fullmatch(r"(?:[^—{]+ — )?((?:\{[0-9wubrgc]\})+) — (.+)", CF.normalizza(t_, info["nome"], info["corto"]))
        if not m: raise CF.Mancante("702.183a: un modo di tiered non si legge")
        cm = CF.Contesto(info["nome"])
        mm.append({"fa": CF.frasi(m.group(2), cm), "bersagli": cm.reqs, "costo_modo": m.group(1).upper()})
    if len(mm) < 2: raise CF.Mancante("702.183a: tiered senza modi")
    if info["prog_spell"]["fa"]: raise CF.Mancante("testo prima dei modi")
    car["modi"], car["scegli"] = mm, 1
    return True
