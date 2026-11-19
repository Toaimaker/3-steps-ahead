"""Le meccaniche di DFT (Aetherdrift) nel motore di partita: solo cio' che e' di questo set (Motore_Partita/carte_set.py).

paragrafo(c, low, orig, car, ctx, info) -> True se il paragrafo e' letto qui (e scritto in `car`), None se no.
ISTRUZIONI, QUANDO, SE, SE_STATICA, STATO e FAI_STATO si aggiungono al motore (effetti.py): mai un nome gia' usato.
Ogni modello cita la sua regola, letta dal file: py -I -X utf8 Motore_Opzioni/regolamento.py <numero>.

La velocita' (702.179, 702.178; 14 nov 2026).
- «Start your engines!» e' statica: chi controlla un permanente con start your engines! e non ha velocita' prende velocita'
  1; e' un'azione di stato (702.179a). Senza velocita' un giocatore ha 0 per gli effetti che la contano (702.179f).
- Con velocita' 1 o piu' il giocatore ha un'abilita' innescata intrinseca, senza fonte, che controlla lui: «Whenever one or
  more opponents lose life during your turn, if your speed is less than 4, your speed increases by 1. This ability
  triggers only once each turn.» (702.179d). Il motore fa scattare gli inneschi dagli oggetti: qui la porta un oggetto
  nella zona di comando, di quel giocatore, che non e' un emblema per le regole e che nessuna carta del perimetro nomina.
- «Max speed — [abilita']» e' statica: finche' la tua velocita' e' 4, l'oggetto ha quell'abilita' (702.178a). Se l'abilita'
  data funziona da un'altra zona (dal cimitero) anche max speed funziona da li' (702.178b): un'abilita' attivata dal
  cimitero («{3}, Exile this card from your graveyard: Draw a card») e' l'abilita' della carta nel cimitero che si puo'
  attivare solo con la velocita' a 4 (`velocita_max_tua`): stessa cosa, perche' la statica la da' solo a velocita' 4.
"""
import re

import carte_fra as CF

# Saddle (702.171a-c; 14 nov 2026): «Tap any number of other untapped creatures you control with total power N or greater:
# This permanent becomes saddled until end of turn. Activate only as a sorcery.» Il costo e' quello di crew nel nucleo
# (`equipaggia`); «saddled» e' una designazione che dura fino a fine turno o finche' resta in campo (702.171b).

VEL_MAX = 4                                                                                     # 702.179e


def velocita(t, j):
    """702.179f: senza velocita' e' 0."""
    return getattr(t.giocatori[j], "velocita", None) or 0


def _stato_velocita(t):
    """702.179a: un giocatore senza velocita' che controlla un permanente con start your engines!."""
    out = []
    for g in t.giocatori:
        if getattr(g, "velocita", None) is None and any(o.controllore == g.i and o.carta.car.get("start_your_engines") for o in t.campo):
            out.append(("velocita_1", g, "702.179a"))
    return out


def _fai_velocita_1(t, g, regola):
    """702.179a, 702.179d: la velocita' diventa 1 e nasce l'innesco intrinseco del giocatore."""
    from tavolo import Carta, Oggetto
    g.velocita = 1
    t._evento("velocita", giocatore=g.i, quanto=1, causa=regola)
    if any(getattr(o, "velocita_di", None) == g.i for o in t.emblemi): return
    ab = {"tipo": "innescata", "quando": {"evento": "avversari_perdono_vite_tuo_turno"}, "se": {"velocita_sotto_max": True},
          "una_volta_per_turno": True, "fa": [{"fa": "aumenta_velocita", "chi": "tu"}]}
    c = Carta(next(t._carte), "Speed", "Speed", g.i, car={"abilita": [ab]})
    o = Oggetto(next(t._oggetti), c, "comando", g.i)
    o.tavolo, o.ts, o.velocita_di = t, next(t._ts), g.i
    t.emblemi.append(o)
    t.oggetti[o.n] = o


def _avversari_perdono_vite(p, e, f, q):
    """702.179d: «whenever one or more opponents lose life during your turn» (vite perse da un avversario nel turno di chi
    controlla l'abilita')."""
    return e.tipo == "vite" and (e.quanto or 0) < 0 and e.giocatore != f.controllore and p.attivo == f.controllore


def _attivi_esaurisci(p, e, f, q):
    """702.177a: «whenever you activate an exhaust ability» (anche da una carta nel cimitero: 113.6m)."""
    chi = f.controllore if f.controllore is not None else f.proprietario
    return e.tipo == "attivata" and e.a == "esaurisci" and e.giocatore == chi


def _i_aumenta_velocita(p, d, chi, ctrl, fonte, ogg):
    """702.179c-d: la velocita' sale di 1, fino a 4."""
    g = p.t.giocatori[ctrl]
    g.velocita = min(VEL_MAX, velocita(p.t, ctrl) + 1)
    p.t._evento("velocita", giocatore=ctrl, quanto=g.velocita, causa="702.179d")


def _i_sella(p, d, chi, ctrl, fonte, ogg):
    for x in chi: x.sellata = p.t.turno_numero                                                   # 702.171b


ISTRUZIONI = {"aumenta_velocita": ("702.179d", _i_aumenta_velocita), "sella": ("702.171a", _i_sella)}
QUANDO = {"avversari_perdono_vite_tuo_turno": ("702.179d", _avversari_perdono_vite, False),
          "attivi_esaurisci": ("702.177a", _attivi_esaurisci, False)}
SE = {"velocita_max_tua": lambda p, v, ctrl: (velocita(p.t, ctrl) == VEL_MAX) == v,                # 702.178b: dal cimitero
      "velocita_sotto_max": lambda p, v, ctrl: (velocita(p.t, ctrl) < VEL_MAX) == v,             # 603.4, 702.179d
      "sellata": lambda p, v, ctrl: (getattr(p._fonte_condizione, "sellata", None) == p.t.turno_numero) == v}   # 702.171b
SE_STATICA = {"velocita_max": lambda t, v, o: (velocita(t, o.controllore) == VEL_MAX) == v}        # 702.178a
STATO = [_stato_velocita]
FAI_STATO = {"velocita_1": _fai_velocita_1}

MAX = {"velocita_max": True}
PT = r"\+(\d+)/\+(\d+)"


def _max_speed(corpo, corpo_orig, ctx):
    """Il corpo di «Max speed — ...» -> gli effetti statici condizionati (702.178a)."""
    if "from your graveyard" in corpo:                                                         # 702.178b: funziona dal cimitero
        ab = CF.attivata(corpo_orig, corpo, ctx)
        if not ab or ab == "mana" or len(ab) != 1 or ab[0].get("zona") != "cimitero": raise CF.Mancante("702.178b: max speed da un'altra zona")
        a = dict(ab[0]); a["solo_se"] = dict(a.get("solo_se") or {}, velocita_max_tua=True)
        return {"dal_cimitero": a}
    m = re.fullmatch(r"this creature (?:gets " + PT + r")?(?: and )?(?:has ([a-z ,]+?))?\.", corpo)
    if m and (m.group(1) or m.group(3)):
        eff = []
        if m.group(1): eff.append({"livello": "7c", "chi": {"se_stessa": True}, "p": int(m.group(1)), "t": int(m.group(2)), "se": MAX})
        if m.group(3):
            parole = CF.parole_lista(m.group(3))
            if not all(x in CF.PAROLE_SEMPLICI for x in parole): raise CF.Mancante("702.178a: parole chiave non coperte")
            eff.append({"livello": "6", "chi": {"se_stessa": True}, "dai": parole, "se": MAX})
        return eff
    ab = CF.innesco(corpo, ctx)
    if ab is None:
        ab = CF.attivata(corpo_orig, corpo, ctx)
        if ab == "mana":
            mt = re.fullmatch(r"\{t\}: add ((?:\{[wubrgc]\})+)\.", corpo)
            if not mt: raise CF.Mancante("702.178a: un'abilita' di mana con altri costi")
            return [{"livello": "6", "chi": {"se_stessa": True}, "dai_mana": [mt.group(1).upper()], "se": MAX}]   # 605.1a, 613.1f
    if not ab: raise CF.Mancante("702.178a: l'abilita' di max speed non si legge")
    if any(a.pop("modi_da_leggere", None) for a in ab): raise CF.Mancante("702.178a: max speed con i modi")
    return [{"livello": "6", "chi": {"se_stessa": True}, "dai_abilita": ab, "se": MAX}]


def paragrafo(c, low, orig, car, ctx, info):
    m = re.fullmatch(r"saddle (\d+)", low.strip())
    if m:                                                                                      # 702.171a
        car["abilita"].append({"tipo": "attivata", "costo": {"equipaggia": int(m.group(1))}, "velocita": "stregoneria",
                               "fa": [{"fa": "sella", "chi": "fonte"}]})
        return True
    m = re.fullmatch(r"this creature saddles mounts and crews vehicles as though its power were (\d+) greater\.", low)
    if m: car["equipaggia_bonus"] = int(m.group(1)); return True                                 # 702.122a, 702.171a
    m = re.fullmatch(r"whenever this creature attacks while saddled, (.+)", low)
    if m:                                                                                      # 702.171b, 603.4
        cx = CF.Contesto(info["nome"]); cx.ultimo_chi = "fonte"
        ab = {"tipo": "innescata", "quando": {"evento": "attacca"}, "se": {"sellata": True}, "fa": CF.frasi(m.group(1), cx)}
        if cx.reqs: ab["bersagli"] = cx.reqs
        car["abilita"].append(ab)
        return True
    m = re.fullmatch(r"whenever you activate an exhaust ability, (.+)", low)
    if m:                                                                                      # 702.177a
        cx = CF.Contesto(info["nome"])
        ab = {"tipo": "innescata", "quando": {"evento": "attivi_esaurisci"}, "fa": CF.frasi(m.group(1), cx)}
        if cx.reqs: ab["bersagli"] = cx.reqs
        if "return this card from your graveyard" in m.group(1): ab["zona"] = "cimitero"         # 113.6m
        car["abilita"].append(ab)
        return True
    if low == "start your engines!":                                                           # 702.179a
        car["start_your_engines"] = True
        return True
    m = re.fullmatch(r"max speed — (.+)", low)
    if m:
        corpo_orig = orig.split("—", 1)[1].strip()
        eff = _max_speed(m.group(1).strip(), corpo_orig, ctx)
        if isinstance(eff, dict): car["abilita"].append(eff["dal_cimitero"]); return True
        car["abilita"].append({"tipo": "statica", "effetti": eff})
        return True
    return None
