"""Cimitero ed esilio come filtri e come voce di Decisions (13-14 nov 2026; Autore: «mettere il valore cimitero nel costo delle decisioni», poi «ma valuta le
carte giocabili dall'esilio e le carte che evocano altre carte dal cimitero?», e sulla proposta «ok fai i filtri per la decisione»).

La misura prima (sui log del 13 nov, 6.963 foto di fine turno in 542 partite, meta' e meta', log-loss sulla meta' di prova, bootstrap per partita, il termine
rimescolato fra le partite come prova negativa): nessuno di questi termini predice le vittorie oltre al vantaggio (vite + 2 x forza), quindi non hanno un peso
nel costo delle decisioni. Diventano situazioni da guardare col loro win rate, come i leak: indizi di grado C, letti dal testo delle carte.

    rian_io / rian_lui  una rianimazione pronta: a fine di un turno una carta in mano (solo la tua: la sua non si vede) o in campo che riporta una creatura dal
                        cimitero al campo, con una creatura nel cimitero giusto
    esil_io / esil_lui  carte che si possono ancora giocare dall'esilio a fine di un turno: foretell, plot, warp, suspend, avventura (l'impulse draw no: la carta
                        esiliata non lo dice, lo dice l'effetto di un'altra)
    odio_io / odio_lui  il cimitero dell'avversario esiliato: nel tuo turno (o nel suo per odio_lui) carte uscite dal suo cimitero e finite nel suo esilio,
                        il massimo in un turno (0, 1-2, 3+). Grado C: nel suo turno puo' essere lui che esilia le sue (escape, delve)

per_partita(x) -> dict con le sei chiavi ("Yes"/"No", "0"/"1-2"/"3+") o None senza le foto. Prova: --prova (con le negative).
"""
import os, sys
_casa = os.path.dirname(os.path.abspath(__file__))
while not os.path.isfile(os.path.join(_casa, "percorsi.py")):
    _casa = os.path.dirname(_casa)
if _casa not in sys.path:
    sys.path.insert(0, _casa)
import percorsi  # noqa: E402,F401
import collections  # noqa: E402
import re  # noqa: E402

DALL_ESILIO = re.compile(r"\b(foretell|plot|warp|suspend)\b", re.I)
RIANIMA = re.compile(r"(?:return|put) (?:up to (?:one|two) )?(?:target )?(?:[\w-]+ )*?creature cards? (?:with [^.]{0,40})?from (your|a|an opponent's) graveyard "
                     r"(?:to|onto) the battlefield", re.I)
NOMI = {"rian_io": "You · a reanimation ready (with a creature in the graveyard)", "rian_lui": "Opponent · a reanimation ready (on their battlefield)",
        "esil_io": "You · cards playable from exile", "esil_lui": "Opponent · cards playable from exile",
        "odio_io": "You exiled cards from their graveyard (most in a turn)", "odio_lui": "They exiled cards from your graveyard (most in a turn)"}
ORDINE = {**{k: ("Yes", "No") for k in ("rian_io", "rian_lui", "esil_io", "esil_lui")}, "odio_io": ("0", "1-2", "3+"), "odio_lui": ("0", "1-2", "3+")}
_C = {}


def _da():
    import dati_analizzatore as DA
    return DA


def carta(g):
    if g not in _C:
        DA = _da()
        n = DA.nome_grp(g) if g not in DA.SENZA_FACCIA else None
        _C[g] = DA._carta(n or "") or {}
    return _C[g]


def giocabile_esilio(g):
    c = carta(g)
    return bool(DALL_ESILIO.search(c.get("testo") or "")) or "Adventure" in (c.get("tipo") or "")


def creatura(g):
    return "Creature" in ((carta(g).get("tipo") or "").split(" // ")[0])


def rianimazioni(fonti, mio_gy, suo_gy):
    """Quante carte fra le fonti riportano una creatura dal cimitero al campo, con un bersaglio nel cimitero giusto («your»: il mio; «an opponent's»: il suo;
    «a»: tutti e due)."""
    n = 0
    for g in fonti:
        m = RIANIMA.search(carta(g).get("testo") or "")
        if not m:
            continue
        dove = m.group(1).lower()
        bersagli = mio_gy if dove == "your" else suo_gy if dove == "an opponent's" else list(mio_gy) + list(suo_gy)
        n += any(creatura(x) for x in bersagli)
    return n


def _fascia(n):
    return "0" if n <= 0 else "1-2" if n <= 2 else "3+"


def per_partita(x):
    DA = _da()
    d = DA._MANA.get(x.get("partita")) or {}
    seat = x.get("seat")
    foto = [f for f in d.get("foto") or [] if isinstance(f[2], dict) and "g" in f[2]]
    if seat not in (1, 2) or not foto:
        return None
    a, b = seat - 1, 2 - seat
    out = dict(rian_io=False, rian_lui=False, esil_io=False, esil_lui=False, odio_io=0, odio_lui=0)
    prima = None
    for t, att, f in foto:
        g, e, c = f.get("g") or [[], []], f.get("e") or [[], []], f.get("c") or [[], []]
        mano = (f.get("m") or [[], []])[a] or []
        out["rian_io"] |= rianimazioni([c_[0] for c_ in c[a] or []] + list(mano), list(g[a] or []), list(g[b] or [])) > 0
        out["rian_lui"] |= rianimazioni([c_[0] for c_ in c[b] or []], list(g[b] or []), list(g[a] or [])) > 0
        out["esil_io"] |= any(giocabile_esilio(gg) for gg in e[a] or [])
        out["esil_lui"] |= any(giocabile_esilio(gg) for gg in e[b] or [])
        if prima is not None:
            pg, pe = prima.get("g") or [[], []], prima.get("e") or [[], []]
            for lato, chiave in ((b, "odio_io"), (a, "odio_lui")):      # il cimitero di lui esiliato nel tuo turno; il tuo nel suo
                if (chiave == "odio_io") != (att == seat):
                    continue
                usciti = collections.Counter(pg[lato] or []) - collections.Counter(g[lato] or [])
                esiliati = collections.Counter(e[lato] or []) - collections.Counter(pe[lato] or [])
                out[chiave] = max(out[chiave], sum((usciti & esiliati).values()))
        prima = f
    return {k: (("Yes" if v else "No") if isinstance(v, bool) else _fascia(v)) for k, v in out.items()}


def tracker(r):
    """La voce Graveyard di Decisions: per ogni situazione, nelle partite r con le foto, in quante c'e', il win rate con e senza, la differenza."""
    rr = [x for x in r if x.get("cimitero")]
    wr = lambda xs: round(100 * sum(1 for x in xs if x["vinta"]) / len(xs), 1) if xs else None
    out = []
    for k in NOMI:
        si = ("Yes",) if ORDINE[k][0] == "Yes" else ("1-2", "3+")
        con = [x for x in rr if x["cimitero"][k] in si]
        senza = [x for x in rr if x["cimitero"][k] not in si]
        w_c, w_s = wr(con), wr(senza)
        out.append(dict(k=k, nome=NOMI[k], n=len(rr), con=len(con), tasso=round(100 * len(con) / len(rr), 1) if rr else None, wr_con=w_c, wr_senza=w_s,
                        delta=None if w_c is None or w_s is None else round(w_c - w_s, 1), si=si))
    return out


def prova():
    DA = _da()
    casi = []
    tab = {"Rev": dict(testo="Return target creature card from your graveyard to the battlefield.", tipo="Sorcery"),
           "Raise": dict(testo="Return target creature card from your graveyard to your hand.", tipo="Sorcery"),
           "Bear": dict(testo="", tipo="Creature — Bear"), "Lands": dict(testo="", tipo="Land"),
           "Fore": dict(testo="Foretell {1}{U}", tipo="Instant"), "Adv": dict(testo="", tipo="Creature — Elf // Sorcery — Adventure"),
           "Rip": dict(testo="Exile target card from a graveyard.", tipo="Instant")}
    nomi = {901: "Rev", 902: "Raise", 903: "Bear", 904: "Lands", 905: "Fore", 906: "Adv", 907: "Rip"}
    vg, vc, vm = DA.nome_grp, DA._carta, dict(DA._MANA)
    _C.clear()
    DA.nome_grp = lambda g: nomi.get(g)
    DA._carta = lambda n: tab.get(n)
    try:
        casi.append(("rianimare: con una creatura nel cimitero si'; negativa: senza creatura no, «to your hand» non e' rianimare",
                     rianimazioni([901], [903], []) == 1 and rianimazioni([901], [904], []) == 0 and rianimazioni([902], [903], []) == 0))
        casi.append(("giocabili dall'esilio: foretell e avventura si'; negativa: una creatura esiliata no",
                     giocabile_esilio(905) and giocabile_esilio(906) and not giocabile_esilio(903)))
        foto = lambda mio_c, mano, gy, ex: dict(c=[mio_c, []], m=[mano, []], n=[len(mano), 0], v=[20, 20], g=gy, e=ex)
        DA._MANA.clear()
        DA._MANA["cm1"] = dict(foto=[[1, 1, foto([], [901], [[903], [903, 903]], [[], []])],
                                     [2, 2, foto([], [901], [[903], [903, 903]], [[905], []])],
                                     [3, 1, foto([], [], [[903], []], [[905], [903, 903]])]])
        cm = per_partita(dict(partita="cm1", seat=1))
        casi.append(("in partita: la rianimazione pronta, l'esilio giocabile, 2 carte del suo cimitero esiliate nel tuo turno 3",
                     cm["rian_io"] == "Yes" and cm["esil_io"] == "Yes" and cm["odio_io"] == "1-2"))
        casi.append(("negativa: lui niente rianimazione ne' esilio giocabile; nel suo turno il tuo cimitero non e' stato toccato", cm["rian_lui"] == "No"
                     and cm["esil_lui"] == "No" and cm["odio_lui"] == "0"))
        DA._MANA["cm2"] = dict(foto=[[1, 2, foto([], [], [[], [903, 903]], [[], []])], [2, 2, foto([], [], [[], []], [[], [903, 903]])]])
        casi.append(("negativa: le sue carte esiliate nel suo turno (escape, delve) non sono il tuo odio sul cimitero",
                     per_partita(dict(partita="cm2", seat=1))["odio_io"] == "0"))
        casi.append(("senza foto: None", per_partita(dict(partita="nessuna", seat=1)) is None))
        tr = {t["k"]: t for t in tracker([dict(vinta=True, cimitero=cm), dict(vinta=False, cimitero=dict(cm, rian_io="No")), dict(vinta=False)])}
        casi.append(("la voce di Decisions: rianimazione pronta in 1 partita su 2, win rate 100% contro 0%; la partita senza foto non conta",
                     tr["rian_io"]["con"] == 1 and tr["rian_io"]["n"] == 2 and tr["rian_io"]["delta"] == 100.0))
    finally:
        DA.nome_grp, DA._carta = vg, vc
        DA._MANA.clear(); DA._MANA.update(vm)
        _C.clear()
    for n, ok in casi:
        print(("ok    " if ok else "ROSSO ") + n)
    print(f"{sum(1 for _n, ok in casi if ok)}/{len(casi)}")
    return all(ok for _n, ok in casi)


if __name__ == "__main__":
    sys.exit(0 if prova() else 1)
