"""Le meccaniche di TLA (Avatar: The Last Airbender) nel motore di partita: solo cio' che e' di questo set (Motore_Partita/carte_set.py).

paragrafo(c, low, orig, car, ctx, info) e frase(s, ctx): le letture del set; ISTRUZIONI e QUANDO: nel motore.

Firebending (702.189a; 14 nov 2026): «Whenever this creature attacks, add N {R}. Until end of combat, you don't lose this mana
as steps and phases end.» Il mana protetto lo tiene il nucleo (effetti.Partita._svuota_mana, `mana_protetto`).
Earthbend (701.66a): «Target land you control becomes a 0/0 land creature with haste in addition to its other types. Put N
+1/+1 counters on it. When that land dies or is put into exile, return it to the battlefield tapped under your control.»
Gli effetti non hanno durata (611.2c: l'insieme fissato); il ritorno e' un'abilita' ritardata (603.7) che ricorda la terra.
Waterbend (701.67a): «Pay [cost]. For each generic mana in that cost, you may tap an untapped artifact or creature you control
rather than pay that mana.» Qui solo come costo di un'abilita' attivata con un numero ({X} e il costo aggiuntivo di una magia,
701.67b, restano mancanti). Chi paga sceglie quali tappare (`waterbend` del giocatore); chi non sceglie paga col mana quanto
puo' e tappa il resto. 701.67c: un evento «waterbend» a ogni pagamento.
Airbend (701.65a): «that player exiles those objects. For each card exiled this way, for as long as it remains exiled, its
owner may cast it by paying {2} rather than paying its mana cost.» Il nucleo da' i costi alternativi dati all'oggetto
(`alternativi_dati`) e il permesso che vale solo con quel costo (`solo_alternativo`). 701.65b: un evento «airbend».
"""
import re

import carte_fra as CF
import mana as M


def _i_firebending(p, d, chi, ctrl, fonte, ogg):
    n = d["n"]
    if n <= 0: return False
    p.t.giocatori[ctrl].riserva.aggiungi(M.produzione("{R}" * n))
    if not hasattr(p, "mana_protetto"): p.mana_protetto = {}
    prot = p.mana_protetto.setdefault(ctrl, {})
    r = next(k for k, v in zip(M.TIPI, M.produzione("{R}")) if v)
    prot[r] = prot.get(r, 0) + n
    p.t._evento("mana", carta=fonte.carta, vecchio=fonte.n, giocatore=ctrl, a="{R}" * n, quanto=n, causa="702.189a")
    return True


def _i_earthbend(p, d, chi, ctrl, fonte, ogg):
    fatto = False
    for x in chi:
        if not (x.vivo and x.zona == "campo"): continue
        ins = frozenset({x.n})
        p.t.aggiungi_continuo("4", {"tipi": ["creature"], "sottotipi": []}, chi=ins, fonte=fonte, durata=None, ctrl=ctrl)
        p.t.aggiungi_continuo("7b", {"p": 0, "t": 0}, chi=ins, fonte=fonte, durata=None, ctrl=ctrl)
        p.t.aggiungi_continuo("6", {"dai": ["haste"]}, chi=ins, fonte=fonte, durata=None, ctrl=ctrl)
        p.t.metti_segnalini(x, "+1/+1", d["n"], causa="701.66a")
        ab = {"tipo": "innescata", "quando": {"evento": "terra_piegata_lascia", "ricordati": [x.n]}, "una_volta": True,
              "fa": [{"fa": "earthbend_ritorna"}]}
        p.ritardate.append({"ab": ab, "ctrl": ctrl, "fonte": fonte, "fino": "sempre",
                            "dopo": p.t.eventi[-1].n if p.t.eventi else -1, "turno": p.t.turno_numero})
        fatto = True
    return fatto


def _lascia(p, e, f, q):
    """701.66a: «When that land dies or is put into exile»."""
    return e.tipo == "zona" and e.da == "campo" and e.a in ("cimitero", "esilio") and e.vecchio in q.get("ricordati", ())


def _i_earthbend_ritorna(p, d, chi, ctrl, fonte, ogg):
    """701.66a: torna in campo tappata sotto il controllo di chi l'ha piegata (la carta nella zona dove e' andata, 400.7)."""
    ev = getattr(ogg, "evento", None)
    x = p.t.oggetti.get(getattr(ev, "nuovo", None))
    if x is None or not x.vivo or x.zona not in ("cimitero", "esilio"): return False
    nuovo = p.t.sposta(x, "campo", chi=ctrl, causa="701.66a")
    if nuovo is not None: p.t.tappa(nuovo)
    return nuovo is not None


def _tappabili(p, i):
    return [o for o in p.t.campo if o.controllore == i and not o.tappato and o.carta.tipi & {"artifact", "creature"}]


def _con_tap(ogg):
    """Il {T} dello stesso costo si paga prima (la fonte non si tappa due volte)."""
    return any((a.get("costo") or {}).get("waterbend") is not None and (a.get("costo") or {}).get("tappa")
               for a in ogg.carta.car.get("abilita") or [])


def _piano(p, i, ogg, n, tappa=None):
    """701.67a -> (m mana da pagare, pagamento o None, permanenti da tappare) o None. Con `tappa` (la scelta di chi paga)
    il resto si paga col mana; senza, prima il mana (quanto si puo'), poi si tappa il resto."""
    fonte_esclusa = ogg if (_con_tap(ogg) and not ogg.tappato) else None
    p._senza_fonte = fonte_esclusa
    try:
        tapp = [o for o in _tappabili(p, i) if o is not fonte_esclusa]
        prove = [n - len(tappa)] if tappa is not None else range(n, -1, -1)
        for m in prove:
            if m < 0: return None
            if m == 0: pag, usate = None, set()
            else:
                pag = p._scegli_pagamento(i, "{%d}" % m)
                if pag is None: continue
                usate = {id(pag[1][k]) for k, _ in pag[0].usa}
            liberi = [o for o in tapp if id(o) not in usate]
            if tappa is not None:
                if all(o in liberi for o in tappa) and len(set(map(id, tappa))) == len(tappa): return m, pag, list(tappa)
                return None
            if len(liberi) >= n - m: return m, pag, liberi[:n - m]
        return None
    finally: p._senza_fonte = None


def _puo_waterbend(p, i, ogg, n):
    return _piano(p, i, ogg, n) is not None


def _paga_waterbend(p, i, ogg, n):
    g = (p.chi or {}).get(i)
    piano = None
    if hasattr(g, "waterbend"):                                                                # chi paga sceglie (701.67a)
        sc = g.waterbend(p, i, ogg, n, _tappabili(p, i))
        if sc is not None and len(sc) <= n: piano = _piano(p, i, ogg, n, tappa=list(sc))
    if piano is None: piano = _piano(p, i, ogg, n)
    m, pag, tap = piano
    if pag: p._paga(i, ogg, "{%d}" % m, 0, pag)
    for o in tap: p.t.tappa(o)
    p.t._evento("waterbend", carta=ogg.carta, vecchio=ogg.n, giocatore=i, quanto=n, causa="701.67c")


def _i_airbend(p, d, chi, ctrl, fonte, ogg):
    """701.65a: esilia; il proprietario puo' lanciare la carta per {2} finche' resta in esilio (una pedina smette di esistere)."""
    fatto = False
    for x in chi:
        if not (x.vivo and x.zona in ("campo", "pila")): continue
        nuovo = p.t.esilia(x, causa="701.65a")
        if nuovo is None: continue
        fatto = True
        if nuovo.zona != "esilio" or nuovo.carta.pedina: continue
        nuovo.alternativi_dati = [{"nome": "airbend", "costo": "{2}"}]
        p.permessi.append({"n": nuovo.n, "giocatore": nuovo.proprietario, "fino": "finche_in_esilio", "iniziato": False,
                           "solo_alternativo": "airbend"})
        p.t._evento("permesso", carta=nuovo.carta, vecchio=nuovo.n, giocatore=nuovo.proprietario, a="finche_in_esilio", causa="701.65a")
    if fatto: p.t._evento("airbend", giocatore=ctrl, causa="701.65b")
    return fatto


def _puo_airbend(p, i, ogg, a):
    return ogg.zona == "esilio" and any(r["n"] == ogg.n and r["giocatore"] == i and r.get("solo_alternativo") == "airbend" for r in p.permessi)


ISTRUZIONI = {"firebending": ("702.189a", _i_firebending), "earthbend": ("701.66a", _i_earthbend),
              "earthbend_ritorna": ("701.66a", _i_earthbend_ritorna), "airbend": ("701.65a", _i_airbend)}
QUANDO = {"terra_piegata_lascia": ("701.66a", _lascia, True)}
COSTI = {"waterbend": (_puo_waterbend, _paga_waterbend)}
ALTERNATIVI = {"airbend": {"puo": _puo_airbend}}


def fine(car):
    """601.2f, 701.67a: il waterbend come costo aggiuntivo di una magia si paga insieme al costo totale (il mana del costo base
    e quello del waterbend, con le tappate che aiutano): il motore non lo fa ancora, e la carta resta mancante."""
    if any("waterbend" in op for op in car.get("costo_aggiuntivo") or []) or "waterbend" in (car.get("facoltativo") or {}):
        return "701.67a: il waterbend come costo aggiuntivo non e' coperto (si paga col costo totale)"
    return None


def costo(parte):
    m = re.fullmatch(r"Waterbend \{(\d+)\}", parte)
    if m: return {"waterbend": int(m.group(1))}                                                 # 701.67a
    return None


def frase(s, ctx):
    m = re.fullmatch(r"earthbend (\d+|x)", s)
    if m: return [{"fa": "earthbend", "chi": ctx.nuovo({"chi": ["land"], "controllo": "tuo"}),
                   "n": "X" if m.group(1) == "x" else int(m.group(1))}]                         # la X la conta «where X is» (608.2h)
    m = re.fullmatch(r"airbend (target nonland permanent|up to one target creature|target creature)", s)
    if m: return [{"fa": "airbend", "chi": CF.chi_frase(m.group(1), ctx)}]                      # 701.65a
    m = re.fullmatch(r"airbend ((?:up to one )?(?:another |other )?target .+)", s)               # 701.65a (15 nov 2026): ogni bersaglio
    if m and CF.bersaglio(m.group(1)) is not None: return [{"fa": "airbend", "chi": ctx.nuovo(CF.bersaglio(m.group(1)))}]
    m = re.fullmatch(r"(create .+? creature tokens?) with firebending (\d+)", s)                # 702.189a (giro 11): la pedina
    if m:                                                                                      # col firebending, come una carta
        n0_ = len(ctx.reqs)
        try: a_ = CF.frase(m.group(1), ctx)
        except CF.Mancante: del ctx.reqs[n0_:]; return None
        if len(a_) != 1 or a_[0].get("fa") != "pedina": del ctx.reqs[n0_:]; return None
        d_ = dict(a_[0])
        d_["abilita"] = list(d_.get("abilita") or []) + [{"tipo": "innescata", "quando": {"evento": "attacca"},
                                                         "fa": [{"fa": "firebending", "n": int(m.group(2))}]}]
        return [d_]
    m = re.fullmatch(r"(.+?) gains firebending (\d+) until end of turn", s)                       # 702.189a, 613.1f (giro 11)
    if m:
        try: c_ = CF.chi_frase(m.group(1), ctx)
        except CF.Mancante: return None
        return [{"fa": "dai_abilita_fino", "chi": c_, "durata": "fine_turno",
                 "abilita": [{"tipo": "innescata", "quando": {"evento": "attacca"}, "fa": [{"fa": "firebending", "n": int(m.group(2))}]}]}]
    return None


def paragrafo(c, low, orig, car, ctx, info):
    m = re.fullmatch(r"firebending (\d+)", low)
    if m:                                                                                      # 702.189a
        car["abilita"].append({"tipo": "innescata", "quando": {"evento": "attacca"}, "fa": [{"fa": "firebending", "n": int(m.group(1))}]})
        return True
    return None
