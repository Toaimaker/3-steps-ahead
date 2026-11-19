"""Le meccaniche di TMT (Teenage Mutant Ninja Turtles) nel motore di partita: solo cio' che e' di questo set (Motore_Partita/carte_set.py).

Sneak (702.190a-b; 14 nov 2026). «Sneak [cost]» e' «Any time you could cast an instant during your declare blockers step, you
may cast this spell by paying [cost] and returning an unblocked creature you control to its owner's hand rather than paying
this spell's mana cost.» Un permanente lanciato cosi' entra tappato e attaccando lo stesso giocatore (o planeswalker) della
creatura rimandata in mano (702.190b). Chi non sceglie rimanda la prima creatura non bloccata.
"""
import re

import carte_fra as CF

from effetti import _scelta


def _non_bloccate(p, i):
    if p.fase != "combattimento" or p.passo != "bloccanti": return []
    return [o for o in p.attaccanti if o.controllore == i and o not in p.bloccate and o.vivo and o.zona == "campo"]


def _tempo(p, i, ogg):
    """702.190a: quando si potrebbe lanciare un istantaneo, nel proprio passo di dichiarazione dei bloccanti."""
    return p.attivo == i and p.fase == "combattimento" and p.passo == "bloccanti" and p.da_istantaneo(i)


def _puo(p, i, ogg, alt):
    return ogg in p.t.giocatori[i].mano and bool(_non_bloccate(p, i))


def _paga(p, i, magia, alt):
    cand = _non_bloccate(p, i)
    if not cand: return
    x = _scelta(p, i, "sneak", cand, predefinita=cand[0])
    if x not in cand: x = cand[0]
    magia.sneak_difensore = p.attaccanti.get(x)
    p.t.sposta(x, "mano", causa="702.190a")


def _entra(p, perm, alt):
    """702.190b: tappato e attaccando chi attaccava la creatura rimandata in mano."""
    dif = alt.get("_difensore")
    p.t.tappa(perm)
    p.entra_attaccando(perm, difensore=dif)


def _dopo(p, magia, alt):
    alt["_difensore"] = getattr(magia, "sneak_difensore", None)                                 # lo ricorda il permanente (702.190b)


ISTRUZIONI = {}
QUANDO = {}
ALTERNATIVI = {"sneak": {"puo": _puo, "paga": _paga, "dopo": _dopo, "entra": _entra, "tempo": _tempo}}

# Le Classi (717; 14 nov 2026). «[Cost]: Level N — [Abilities]» e' «[Cost]: This Class's level becomes N. Activate only if this
# Class is level N-1 and only as a sorcery» e «As long as this Class is level N or greater, it has [abilities]» (717.2a); senza
# livello e' 1 (717.2d). Le abilita' dopo una barra di livello le legge il nucleo; alla fine della carta (`fine`) qui prendono
# la condizione del loro livello: le statiche nei loro effetti, gli inneschi nel «se», le attivate nel «solo se». «When this
# Class becomes level N» scatta col cambio di livello (l'evento «livello»).


def livello(o): return getattr(o, "livello_classe", None) or 1                                  # 717.2d


def _i_livello(p, d, chi, ctrl, fonte, ogg):
    for x in chi:
        if not (x.vivo and x.zona == "campo"): continue
        x.livello_classe = d["n"]                                                              # 717.2a, 717.2b
        p.t._evento("livello", carta=x.carta, vecchio=x.n, quanto=d["n"], causa="717.2a")


def _diventa_livello(p, e, f, q):
    return e.tipo == "livello" and e.vecchio == f.n and e.quanto == q["n"]


ISTRUZIONI = {"livello_classe": ("717.2a", _i_livello)}
QUANDO = {"diventa_livello": ("717.2a", _diventa_livello, False)}
SE = {"classe_livello": lambda p, v, ctrl: livello(p._fonte_condizione) == v,
      "classe_livello_almeno": lambda p, v, ctrl: livello(p._fonte_condizione) >= v}
SE_STATICA = {"classe_livello_almeno": lambda t, v, o: livello(o) >= v}


def fine(car):
    """717.2a: ogni abilita' dopo la barra del livello N vale col livello N o piu'."""
    barre = car.pop("_classe", None)
    if not barre: return None
    if car.get("_classe_parole") is not None and len(car["parole"]) != car.pop("_classe_parole"):
        return "717.2a: una parola chiave dopo una barra di livello"
    ab = car["abilita"]
    for k, (n, da) in enumerate(barre):
        a_ = barre[k + 1][1] - 1 if k + 1 < len(barre) else len(ab)
        for x in ab[da:a_]:
            if x.get("tipo") == "statica":
                for e in x.get("effetti") or []: e["se"] = dict(e.get("se") or {}, classe_livello_almeno=n)
            elif x.get("tipo") == "innescata": x["se"] = dict(x.get("se") or {}, classe_livello_almeno=n)
            elif x.get("tipo") == "attivata": x["solo_se"] = dict(x.get("solo_se") or {}, classe_livello_almeno=n)
            else: return f"717.2a: l'abilita' {x.get('tipo')} dopo una barra di livello"
    for k_ in [k_ for k_ in car if k_ not in ("costo", "parole", "abilita", "forza", "costituzione", "alternativi", "facoltativo")]:
        return f"717.2a: {k_} in una Classe"
    return None


def paragrafo(c, low, orig, car, ctx, info):
    m = re.fullmatch(r"((?:\{[0-9wubrgcx/]+\})+): level (\d)", low)
    if m and "Class" in (c.get("faces") or [{}])[0].get("type", ""):                            # 717.2a: la barra di livello
        n = int(m.group(2))
        car.setdefault("_classe_parole", len(car["parole"]))
        car["abilita"].append({"tipo": "attivata", "costo": {"mana": m.group(1).upper()}, "velocita": "stregoneria",
                               "solo_se": {"classe_livello": n - 1}, "fa": [{"fa": "livello_classe", "n": n, "chi": "fonte"}]})
        car.setdefault("_classe", []).append((n, len(car["abilita"])))
        return True
    m = re.fullmatch(r"when this class becomes level (\d), (.+)", low)
    if m:                                                                                      # 717.2a
        cx = CF.Contesto(info["nome"]); cx.ultimo_chi = "fonte"
        ab = {"tipo": "innescata", "quando": {"evento": "diventa_livello", "n": int(m.group(1))}, "fa": CF.frasi(m.group(2), cx)}
        if cx.reqs: ab["bersagli"] = cx.reqs
        car["abilita"].append(ab)
        return True
    m = re.fullmatch(r"sneak ((?:\{[0-9wubrgcx]\})+)", low)
    if m:                                                                                      # 702.190a
        car.setdefault("alternativi", []).append({"nome": "sneak", "costo": m.group(1).upper()})
        return True
    return None
