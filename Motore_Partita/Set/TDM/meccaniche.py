"""Le meccaniche di TDM (Tarkir: Dragonstorm) nel motore di partita: solo cio' che e' di questo set (Motore_Partita/carte_set.py).

Mobilize (702.181a; 14 nov 2026): «Whenever this creature attacks, create N 1/1 red Warrior creature tokens. Those tokens
enter tapped and attacking. Sacrifice them at the beginning of the next end step.» Le pedine attaccano chi attacca la
creatura, se e' un giocatore (508.4: lo sceglie chi le controlla; il motore: effetti.Partita.entra_attaccando); il sacrificio
e' un'abilita' ritardata (603.7) che ricorda le pedine create.

Endure (701.63a-b; 14 nov 2026): «that permanent's controller creates an N/N white Spirit creature token unless they put N
+1/+1 counters on that permanent»; endure 0 non fa niente. Chi non sceglie mette i segnalini se il permanente e' ancora in
campo, se no crea lo Spirito (i segnalini non si possono mettere).

Harmonize (702.180a-b; 14 nov 2026): «You may cast this card from your graveyard by paying [cost] and tapping up to one
untapped creature you control rather than paying this spell's mana cost»; il costo totale scende di tanto mana generico
quanta e' la forza della creatura tappata; lasciata la pila, la carta va in esilio. La creatura si sceglie quando si sceglie
il costo (702.180b, `harmonize`; chi non sceglie tappa quella con la forza piu' alta, prima quelle senza abilita' di mana) e
si tappa pagando. Il nucleo: il costo alternativo che lancia dal cimitero (`zona`) e la sua riduzione (`riduzione`).
"""
import re

import carte_fra as CF

from effetti import _scelta
from tavolo import forza


def _i_endure(p, d, chi, ctrl, fonte, ogg):
    n = d["n"]
    if n <= 0: return False                                                                    # 701.63b
    vivi = [x for x in chi if not isinstance(x, int) and x.vivo and x.zona == "campo"]
    perm = vivi[0] if vivi else None
    scelta = "segnalini" if perm is not None else "pedina"
    if perm is not None:
        scelta = _scelta(p, perm.controllore, "endure", perm, n, predefinita="segnalini")
        if scelta not in ("segnalini", "pedina"): scelta = "segnalini"
    if scelta == "segnalini": p.t.metti_segnalini(perm, "+1/+1", n, causa="701.63a")
    else:
        j = perm.controllore if perm is not None else ctrl
        p.t.crea_pedina(j, "Spirit", "Token Creature — Spirit", causa="701.63a",
                        car={"forza": n, "costituzione": n, "colori": "W", "parole": []})
    return True


def _i_mobilize(p, d, chi, ctrl, fonte, ogg):
    create = []
    for _ in range(d["n"]):
        o = p.t.crea_pedina(ctrl, "Warrior", "Token Creature — Warrior", causa="702.181a",
                            car={"forza": 1, "costituzione": 1, "colori": "R", "parole": []})
        p.t.tappa(o)
        p.entra_attaccando(o, fonte)
        create.append(o)
    if create:
        ab = {"tipo": "innescata", "quando": {"evento": "inizio_passo", "passo": "finale"}, "una_volta": True,
              "ricordati": [o.n for o in create], "fa": [{"fa": "sacrifica_ricordate", "chi": "ricordati"}]}
        p.ritardate.append({"ab": ab, "ctrl": ctrl, "fonte": fonte, "fino": "sempre",
                            "dopo": p.t.eventi[-1].n if p.t.eventi else -1, "turno": p.t.turno_numero})
    return bool(create)


def _i_sacrifica_ricordate(p, d, chi, ctrl, fonte, ogg):
    for x in chi: p.t.sacrifica(x, x.controllore, causa="702.181a")


ISTRUZIONI = {"endure": ("701.63a", _i_endure), "mobilize": ("702.181a", _i_mobilize),
              "sacrifica_ricordate": ("701.21a", _i_sacrifica_ricordate)}
QUANDO = {}


def _puo_harmonize(p, i, ogg, alt):
    return ogg.vivo and ogg.zona == "cimitero" and ogg.proprietario == i                       # 702.180a


def _da_tappare(p, i, ogg):
    return [o for o in p.t.campo if o.controllore == i and "creature" in o.carta.tipi and not o.tappato and o is not ogg]


def _riduzione_harmonize(p, i, ogg, alt):
    """702.180a-b: la creatura da tappare si sceglie con il costo; il costo scende della sua forza (solo il generico)."""
    cand = _da_tappare(p, i, ogg)
    if not cand: alt.pop("_tappa", None); return 0
    pred = max(cand, key=lambda o: (not o.carta.car.get("mana"), forza(o)))
    x = _scelta(p, i, "harmonize", cand, predefinita=pred)
    if x is None: alt.pop("_tappa", None); return 0                                             # «up to one»: nessuna
    if x not in cand: x = pred
    alt["_tappa"] = x.n
    return -max(0, forza(x))


def _paga_harmonize(p, i, magia, alt):
    x = p.t.oggetti.get(alt.get("_tappa"))
    if x is not None and x.vivo and x.zona == "campo" and not x.tappato: p.t.tappa(x)            # 702.180b: si tappa pagando


def _dopo_harmonize(p, magia, alt):
    magia.flashback = True                                                                     # 702.180a: lasciata la pila, in esilio


ALTERNATIVI = {"harmonize": {"puo": _puo_harmonize, "zona": "cimitero", "riduzione": _riduzione_harmonize,
                             "paga": _paga_harmonize, "dopo": _dopo_harmonize}}


def frase(s, ctx):
    m = re.fullmatch(r"(it|this creature|~) endures (\d+)", s)
    if m:
        chi = "fonte" if m.group(1) != "it" else (ctx.ultimo_chi if ctx.ultimo_chi == "fonte" else ctx.ultimo())
        return [{"fa": "endure", "chi": chi, "n": int(m.group(2))}]
    return None


CLAN = {"abzan", "jeskai", "sultai", "mardu", "temur"}


def _siege(low, car, info):
    """614.12, 607.2 (14 nov 2026): «As this enchantment enters, choose Abzan or Mardu.» e i due rami «• Abzan — ...»: ogni
    abilita' vale solo col clan scelto entrando (la condizione «scelta_entrata» del nucleo)."""
    m = re.fullmatch(r"as this enchantment enters, choose ([a-z]+) or ([a-z]+)\.", low)
    if not m or not {m.group(1), m.group(2)} <= CLAN: return None
    scelte = [m.group(1).title(), m.group(2).title()]
    if len(info["modi"]) != 2: raise CF.Mancante("614.12: i rami dell'assedio")
    abil = []
    for t_ in info["modi"]:
        nome_, _, corpo = t_.partition(" — ")
        if nome_ not in scelte: raise CF.Mancante("614.12: un ramo che non e' fra le scelte")
        low_ = CF.normalizza(corpo, info["nome"], info["corto"])
        se = {"scelta_entrata": nome_}
        cx = CF.Contesto(info["nome"])
        ab = CF.innesco(low_, cx)
        if ab:
            if any(a.pop("modi_da_leggere", None) for a in ab): raise CF.Mancante("614.12: un ramo coi modi")
            abil += [dict(a, se=dict(a.get("se") or {}, **se)) for a in ab]
            continue
        st = CF.statica(low_, cx)
        if isinstance(st, list) and st and all(isinstance(a, dict) and a.get("tipo") == "statica" for a in st):
            abil += [dict(a, effetti=[dict(e, se=dict(e.get("se") or {}, **se)) for e in a["effetti"]]) for a in st]
            continue
        raise CF.Mancante(f"614.12: il ramo {nome_} non si legge")
    car.setdefault("entra", {})["sceglie_tra"] = scelte
    car["abilita"] += abil
    return True


def paragrafo(c, low, orig, car, ctx, info):
    m = re.fullmatch(r"harmonize ((?:\{[0-9wubrgcx]\})+)(?: \(.*\))?", low)
    if m:                                                                                      # 702.180a
        car.setdefault("alternativi", []).append({"nome": "harmonize", "costo": m.group(1).upper()})
        return True
    if _siege(low, car, info): return True
    m = re.fullmatch(r"mobilize (\d+)", low)
    if m:                                                                                      # 702.181a
        car["abilita"].append({"tipo": "innescata", "quando": {"evento": "attacca"}, "fa": [{"fa": "mobilize", "n": int(m.group(1))}]})
        return True
    return None
