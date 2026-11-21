"""UpgradePlan01, il voto per scopo, primo pezzo: il lettore dello scopo delle carte tenute (Autore, 20 nov 2026: «il motore di discesa dovrebbe
servire a capire se una carta tenuta in mano per troppi turni scende al momento giusto per sbloccare una sinergia o un vantaggio sul board o per
sistemare una situazione di svantaggio», «sapendo che il giocatore cerca di essere intelligente, sarà più facile capire ogni azione fatta o non fatta a
cosa è servita a produrre, ed è lì che si dovrebbe esprimere un vero voto», «il player pensa sempre più a quel che potrebbe ucciderlo a sorpresa»; poi
«vai». Il piano: Note/UpgradePlan01.md; la misura: Note/UpgradePlan01_Scopo.md).

Lo spot: una magia che Arena ti offriva pagabile all'ultima tua priorita' del turno (leak.arena_offriva: dopo l'ultima giocata) e che non hai lanciato in
quel turno. Si guarda avanti: quando l'hai lanciata (la prima volta dopo), in che turno di chi, e cosa era cambiato.

Lo scopo, in quest'ordine (prima la difesa):
  difesa     lanciata nel turno dell'Opponent (velocita' istantanea), o una risposta (rimozione, contromagia, trucco) lanciata quando l'Opponent aveva
             piu' creature di quando l'hai tenuta (la minaccia e' arrivata)
  sinergia   lanciata quando in campo c'era un partner (ev_partita.in_sinergia) che quando l'hai tenuta non c'era
  tempo      lanciata piu' tardi senza una ragione che si legga
  mai        mai lanciata in quella partita

Il valore: l'EV del lancio vero (ev_partita._ev_lanci: la P dalla foto del lancio a quella dopo) contro il solito della stessa carta lanciata subito,
cioe' nel primo turno in cui era pagabile, nelle partite dello stesso mazzo (DA.chiave_mazzo; con meno di MIN_SUBITO lanci subito, il solito delle carte
dello stesso ruolo nel mazzo). Voto = EV del lancio - solito subito. Il verdetto: preparazione (scopo di difesa o di sinergia e voto >= SOGLIA), miope
(voto <= -SOGLIA), neutra; «mai» resta a parte.

Limiti (grado C, detto nella nota): la probabilita' che lo scopo si realizzasse con quello che sapevi (la mano avversaria, il partner da pescare) non
c'e' ancora, quindi «scommessa andata bene» non si distingue da «preparazione»; il costo dei turni in cui la carta e' rimasta in mano sta nell'EV di quei
turni, non nel voto; una copia tenuta e un'altra copia lanciata dopo sono la stessa carta.

    py -I -X utf8 Companion/App/Schede/Performance/scopo.py [--limited]      la misura sulle tue partite
    py -I -X utf8 Companion/App/Schede/Performance/scopo.py --prova
"""
import os
import sys
import math
import random
import collections

_casa = os.path.dirname(os.path.abspath(__file__))
while not os.path.isfile(os.path.join(_casa, "percorsi.py")):
    _casa = os.path.dirname(_casa)
if _casa not in sys.path:
    sys.path.insert(0, _casa)
import percorsi  # noqa: E402,F401
import dati_analizzatore as DA  # noqa: E402
import ev_partita as EV  # noqa: E402
import leak  # noqa: E402

SOGLIA = 2.0            # punti di P: sotto, il voto e' neutro
MIN_SUBITO = 3          # lanci «subito» della stessa carta per farne il solito
RISPOSTE = ("Removal", "Counterspell", "Combat trick")
SCOPI = ("difesa", "sinergia", "tempo", "mai")
NOMI_SCOPI = {"difesa": "defense (an answer, or instant speed in the Opponent's turn)", "sinergia": "synergy (a partner arrived)",
              "tempo": "later, no reason that shows", "mai": "never cast"}


def _creature(f, lato):
    return sum(1 for z in ((f.get("c") or [[], []])[lato] or []) if len(z) > 4 and z[3] is not None)


def _nomi(f, lato):
    return [DA.nome_intero(DA.nome_grp(z[0]) or "") for z in ((f.get("c") or [[], []])[lato] or []) if not z[2]]


def _ruolo(nome):
    try:
        return DA.ruolo_magia(nome)
    except Exception:       # noqa: BLE001
        return "Other spell"


def scopo_di(tenuta, lancio):
    """Lo scopo di una carta tenuta. tenuta = dict(nome, ruolo, sue_cre, partner (famiglie col campo di allora)); lancio = None (mai) o dict(suo_turno,
    sue_cre, partner). Prima la difesa, poi la sinergia, poi il tempo."""
    if lancio is None:
        return "mai"
    if lancio["suo_turno"] or (tenuta["ruolo"] in RISPOSTE and lancio["sue_cre"] > tenuta["sue_cre"]):
        return "difesa"
    if lancio["partner"] and not tenuta["partner"]:
        return "sinergia"
    return "tempo"


def spot_partita(x):
    """Le carte tenute di una partita: [dict(partita, mazzo, t, nome, ruolo, scopo, t_lancio, ev (del lancio vero) o None)]. [] senza i dati."""
    d = DA._MANA.get(x.get("partita")) or {}
    seat = x.get("seat")
    if seat not in (1, 2) or d.get("disponibili") is None or d.get("lanci") is None:
        return []
    a, b = seat - 1, 2 - seat
    fine = {t: (att, f) for t, att, f in d.get("foto") or []}
    lanci = [(t, g, n, ev) for t, g, n, ev in EV._ev_lanci(x, con_turno=True) if not DA.e_terra(n)]
    lanciati_t = collections.defaultdict(set)
    for t, g, _n, _ev in lanci:
        lanciati_t[t].add(g)
    gia = set()
    out = []
    for t in sorted(fine):
        if fine[t][0] != seat:
            continue
        off = leak.arena_offriva(d, seat, t)
        if not off:
            continue
        for g in sorted(off["lanci"] - lanciati_t[t]):
            if g in gia or g in DA.SENZA_FACCIA:
                continue
            nome = DA.nome_intero(DA.nome_grp(g) or "")
            if not nome or DA.e_terra(nome):
                continue
            gia.add(g)
            f = fine[t][1]
            ten = dict(nome=nome, ruolo=_ruolo(nome), sue_cre=_creature(f, b), partner=EV.in_sinergia(nome, _nomi(f, a)))
            dopo = next(((t2, ev) for t2, g2, _n, ev in lanci if g2 == g and t2 > t), None)
            lan = None
            if dopo is not None:
                t2 = dopo[0]
                f2 = (fine.get(t2 - 1) or (None, None))[1] or f
                lan = dict(suo_turno=(fine.get(t2) or (seat,))[0] != seat, sue_cre=_creature(f2, b), partner=EV.in_sinergia(nome, _nomi(f2, a)))
            out.append(dict(partita=x.get("partita"), mazzo=DA.chiave_mazzo(x), t=t, nome=nome, ruolo=ten["ruolo"], scopo=scopo_di(ten, lan),
                            t_lancio=dopo[0] if dopo else None, ev=dopo[1] if dopo else None))
    return out


def soliti_subito(base):
    """{(mazzo, nome): [ev dei lanci subito]} e {(mazzo, ruolo): [...]}: i lanci di una carta mai tenuta prima in quella partita."""
    per_carta, per_ruolo = collections.defaultdict(list), collections.defaultdict(list)
    for x in base:
        d = DA._MANA.get(x.get("partita")) or {}
        seat = x.get("seat")
        if seat not in (1, 2) or d.get("disponibili") is None or d.get("lanci") is None:
            continue
        tenute = {(s["nome"]) : s["t"] for s in spot_partita(x)}
        km = DA.chiave_mazzo(x)
        for t, _g, n, ev in EV._ev_lanci(x, con_turno=True):
            if DA.e_terra(n) or (n in tenute and tenute[n] < t):
                continue
            per_carta[(km, n)].append(ev)
            per_ruolo[(km, _ruolo(n))].append(ev)
    return per_carta, per_ruolo


def voti(r, base):
    """Le carte tenute delle partite r col voto contro il solito subito dalle partite base: ogni spot con «solito», «voto», «verdetto»."""
    pc, pr = soliti_subito(base)
    out = []
    for x in r:
        for s in spot_partita(x):
            v = pc.get((s["mazzo"], s["nome"])) or []
            if len(v) < MIN_SUBITO:
                v = pr.get((s["mazzo"], s["ruolo"])) or []
            s["solito"] = sum(v) / len(v) if len(v) >= MIN_SUBITO else None
            s["voto"] = s["ev"] - s["solito"] if s["ev"] is not None and s["solito"] is not None else None
            if s["voto"] is None:
                s["verdetto"] = "mai" if s["scopo"] == "mai" else None
            elif s["scopo"] in ("difesa", "sinergia") and s["voto"] >= SOGLIA:
                s["verdetto"] = "preparazione"
            elif s["voto"] <= -SOGLIA:
                s["verdetto"] = "miope"
            else:
                s["verdetto"] = "neutra"
            out.append(s)
    return out


def _media(v):
    n = len(v)
    if n < 2:
        return (v[0] if v else None), None, n
    m = sum(v) / n
    return m, math.sqrt(sum((q - m) ** 2 for q in v) / (n - 1) / n), n


def misura(S, giri=2000, seme=7):
    """Lo scopo serve? Il voto medio per scopo, e la differenza (difesa e sinergia) - tempo contro la stessa differenza con gli scopi rimescolati fra gli
    spot dello stesso ruolo (la negativa: se lo scopo non dice niente, la differenza vera sta dentro quelle rimescolate)."""
    V = [s for s in S if s["voto"] is not None]
    per = {k: _media([s["voto"] for s in V if s["scopo"] == k]) for k in ("difesa", "sinergia", "tempo")}
    diff = lambda W: ((lambda a, b: (a - b) if a is not None and b is not None else None)(
        _media([s["voto"] for s in W if s["scopo"] in ("difesa", "sinergia")])[0], _media([s["voto"] for s in W if s["scopo"] == "tempo"])[0]))
    vera = diff(V)
    rnd = random.Random(seme)
    per_ruolo = collections.defaultdict(list)
    for i, s in enumerate(V):
        per_ruolo[s["ruolo"]].append(i)
    finte = []
    for _ in range(giri):
        sc = [s["scopo"] for s in V]
        for idx in per_ruolo.values():
            v = [sc[i] for i in idx]
            rnd.shuffle(v)
            for i, q in zip(idx, v):
                sc[i] = q
        d_ = diff([dict(s, scopo=q) for s, q in zip(V, sc)])
        if d_ is not None:
            finte.append(d_)
    p = (sum(1 for q in finte if q >= vera) + 1) / (len(finte) + 1) if vera is not None and finte else None
    return dict(per=per, vera=vera, p=p, finte_media=sum(finte) / len(finte) if finte else None)


def prova():
    casi = []
    T = dict(nome="X", ruolo="Removal", sue_cre=1, partner=[])
    casi.append(("mai lanciata: mai", scopo_di(T, None) == "mai"))
    casi.append(("lanciata nel suo turno: difesa", scopo_di(T, dict(suo_turno=True, sue_cre=1, partner=[])) == "difesa"))
    casi.append(("rimozione lanciata quando lui ha piu' creature: difesa", scopo_di(T, dict(suo_turno=False, sue_cre=2, partner=[])) == "difesa"))
    casi.append(("negativa: rimozione nel tuo turno, lui con le stesse creature: non e' difesa",
                 scopo_di(T, dict(suo_turno=False, sue_cre=1, partner=[])) == "tempo"))
    C = dict(nome="Y", ruolo="Creature", sue_cre=0, partner=[])
    casi.append(("prima la difesa: una creatura flash nel suo turno con un partner e' difesa",
                 scopo_di(C, dict(suo_turno=True, sue_cre=0, partner=["token"])) == "difesa"))
    casi.append(("partner arrivato: sinergia", scopo_di(C, dict(suo_turno=False, sue_cre=3, partner=["token"])) == "sinergia"))
    casi.append(("negativa: il partner c'era gia' quando l'hai tenuta: non e' sinergia",
                 scopo_di(dict(C, partner=["token"]), dict(suo_turno=False, sue_cre=0, partner=["token"])) == "tempo"))
    # la misura: con uno scopo che vale (+5) la differenza esce e la negativa no; con voti a caso nessuna differenza
    rnd = random.Random(3)
    S = [dict(voto=rnd.gauss(5 if k != "tempo" else 0, 3), scopo=k, ruolo="R") for k in ("difesa", "sinergia", "tempo") for _ in range(60)]
    m = misura(S, giri=300)
    casi.append(("la misura trova uno scopo che vale (+5, p sotto 0,01)", m["vera"] > 3 and m["p"] < 0.01))
    S0 = [dict(s, voto=rnd.gauss(0, 3)) for s in S]
    m0 = misura(S0, giri=300)
    casi.append(("negativa: voti a caso, nessuna differenza (p sopra 0,05)", m0["p"] > 0.05))
    for n_, ok in casi:
        print(("ok    " if ok else "ROSSO ") + n_)
    print(f"{sum(1 for _n, ok in casi if ok)}/{len(casi)}")
    return all(ok for _n, ok in casi)


if __name__ == "__main__":
    if "--prova" in sys.argv:
        sys.exit(0 if prova() else 1)
    tipo = "Limited" if "--limited" in sys.argv else "Constructed"
    R = [x for x in DA.righe() if x["tipo"] == tipo]
    S = voti(R, R)
    print(f"{tipo}: {len(R)} games, {len(S)} held spells")
    for k in SCOPI:
        g = [s for s in S if s["scopo"] == k]
        m, es, n = _media([s["voto"] for s in g if s["voto"] is not None])
        print(f"  {NOMI_SCOPI[k]:62s} {len(g):5d} spots" + (f"  vote {m:+5.1f} ±{es:.1f} ({n} with a usual)" if es is not None else ""))
    print("  verdicts:", dict(collections.Counter(s["verdetto"] for s in S)))
    per_r = collections.defaultdict(list)
    for s in S:
        if s["voto"] is not None:
            per_r[(s["ruolo"], s["scopo"])].append(s["voto"])
    for (ru, sc), v in sorted(per_r.items()):
        m, es, n = _media(v)
        if n >= 10:
            print(f"    {ru:14s} {sc:9s} {m:+5.1f} ±{es:.1f}  ({n})")
    mm = misura(S)
    print(f"  does the purpose matter? (defense+synergy) - later = {mm['vera']:+.1f}, shuffled {mm['finte_media']:+.1f}, p {mm['p']:.4f}")
