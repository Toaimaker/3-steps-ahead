"""I numeri di un mazzo per la sua finestra (Autore, 7 nov 2026: «ogni mazzo deve avere tutti i dati compreso le win per partenza / turni medi di chiusura e le best starting hand che hanno
decretato lo snowball della partita», «deve avere anche un piccolo grafo che ne descrive in base ai dati e le carte l'archetipo»).

Da dove vengono:
- chi comincia: active_player_id della partita di Untapped uguale al proprio posto; confrontato con le schede di Partite/: torna su 376 partite su 381;
- la mano: player_opening_hands di Untapped (l'ultima e' quella tenuta), su quasi tutte le partite;
- i turni: le schede di Partite/, quindi solo dal 22 set 2026, agganciate per minuto d'inizio ed esito. La scheda conta i turni di Arena dei due giocatori, qui si contano i tuoi.
«Snowball» non e' una misura di Arena: sono le vittorie piu' veloci, con la mano che le ha aperte. Le mani migliori sono le coppie di magie viste da 3 partite in su, ordinate col
win rate stimato (v + 1) / (n + 2), che non premia un 2-0: col mazzo da 60 la stessa mano intera non si ripete mai. Ogni coppia porta le mani intere delle sue partite (esempi: prima le
vinte, dalla piu' veloce), e ogni vittoria veloce la sua: la finestra del mazzo le mostra carta per carta (Autore, 8 nov 2026: «la best starting hand: possiamo farla che si apre in una sotto
finestra e mostra effettivamente le carte che si hanno in mano?»).
L'archetipo e' una stima di grado C dalle carte e dai turni di chiusura: quattro assi, pesi miei, non una classificazione di Untapped.

    py -I -X utf8 Companion/App/Schede/Your_decks/dati_mazzo.py --prova
"""
import os, sys
_casa = os.path.dirname(os.path.abspath(__file__))      # si sale fino a percorsi.py, che mette nel sys.path tutte le cartelle del Companion
while not os.path.isfile(os.path.join(_casa, "percorsi.py")):
    _casa = os.path.dirname(_casa)
if _casa not in sys.path:
    sys.path.insert(0, _casa)
import percorsi  # noqa: E402
import datetime
import glob
import itertools
import json
import re

QUI = os.path.dirname(os.path.abspath(__file__))
RADICE = percorsi.ROOT
import collezione_carte as CC  # noqa: E402

ASSI = ("Aggro", "Midrange", "Control", "Ramp")
_S = {"chiave": None, "d": {}}
_M = {}


def schede():
    """{minuto d'inizio: dict(turni, esito, primo)} dalle schede di Partite/."""
    file = glob.glob(os.path.join(RADICE, "Partite", "*.json"))
    chiave = (len(file), max((os.path.getmtime(f) for f in file[-5:]), default=0))
    if chiave != _S["chiave"]:
        d = {}
        for f in file:
            try:
                s = json.load(open(f, encoding="utf-8"))
                d[s["inizio"][:16]] = dict(turni=s.get("turni"), esito=s.get("esito"), motivo=s.get("motivo"))
            except (OSError, ValueError, KeyError):
                continue
        _S.update(chiave=chiave, d=d)
    return _S["d"]


def scheda_di(p, sc):
    """La scheda della partita: stesso minuto (uno di scarto) e stesso esito, se no niente: due partite vicine non si scambiano."""
    for dm in (0, -1, 1):
        s = sc.get((p["quando"] + datetime.timedelta(minutes=dm)).strftime("%Y-%m-%dT%H:%M"))
        if s and s.get("turni") and (s["esito"] == "vinta") == bool(p["vinta"]):
            return s
    return None


def mano(codice):
    if codice not in _M:
        from deckstring import decodifica
        try:
            _M[codice] = dict(decodifica(codice))
        except Exception:
            _M[codice] = {}
    return _M[codice]


def tabella_carte():
    d = CC.carica()
    return {c["nome"]: c for c in (d or {}).get("carte") or []}


def e_terra(nome, carte):
    c = carte.get(nome) or carte.get(nome.split(" // ")[0].strip())
    return bool(c) and "Land" in c["tipo"].split(" // ")[0]


def righe(partite, carte, sc=None):
    """Una riga per partita: vinta, primo, turno tuo di fine, mano tenuta."""
    sc = schede() if sc is None else sc
    out = []
    for p in partite:
        g = (p.get("giochi") or [{}])[0]
        s = scheda_di(p, sc) or ({"turni": p["turni"], "motivo": None} if p.get("turni") else None)      # una partita letta dal Player.log porta i suoi turni (9 nov 2026)
        primo = g.get("active_player_id") == p.get("seat") if g.get("active_player_id") is not None and p.get("seat") is not None else None
        turno = None
        if s and primo is not None:
            turno = (s["turni"] + 1) // 2 if primo else s["turni"] // 2
        mani = g.get("player_opening_hands") or []
        tenuta = mano(mani[-1]) if mani else {}
        terre = sum(q for n, q in tenuta.items() if e_terra(n, carte))
        magie = [n for n, q in tenuta.items() if not e_terra(n, carte) for _ in range(q)]
        if turno is not None and turno <= 3 and s.get("motivo") == "Concede":      # uno che lascia al terzo turno non dice quanto chiude il mazzo: niente turno, la partita resta nel record
            turno = None
        out.append(dict(vinta=bool(p["vinta"]), primo=primo, turno=turno, mull=max(0, len(mani) - 1), terre=terre if tenuta else None, magie=magie, mano=dict(tenuta)))
    return out


def analizza(partite, carte, sc=None):
    """-> dict(play, draw, chiude, perde, terre, mani, veloci). play e draw: (vinte, partite). chiude e perde: (turno medio, partite) o None."""
    rr = righe(partite, carte, sc)

    def conta(xs):
        return sum(x["vinta"] for x in xs), len(xs)

    def media(xs):
        return (sum(x["turno"] for x in xs) / len(xs), len(xs)) if xs else None
    r_t = [x for x in rr if x["turno"]]
    per_terre = {}
    for x in rr:
        if x["terre"] is not None and not x["mull"]:
            a = per_terre.setdefault(x["terre"], [0, 0]); a[0] += x["vinta"]; a[1] += 1
    coppie = {}
    for x in rr:
        if x["mull"]:
            continue
        for c in itertools.combinations(sorted(set(x["magie"])), 2):
            a = coppie.setdefault(c, dict(v=0, n=0, turni=[], righe=[]))
            a["v"] += x["vinta"]; a["n"] += 1; a["righe"].append(x)
            if x["vinta"] and x["turno"]:
                a["turni"].append(x["turno"])
    buone = [(c, a) for c, a in coppie.items() if a["n"] >= 3 and a["v"] >= 2]
    buone.sort(key=lambda z: (-(z[1]["v"] + 1) / (z[1]["n"] + 2), -z[1]["n"], z[0]))
    mani = []
    usate = set()
    for c, a in buone:          # una carta forte non deve riempire la tabella con tutte le sue coppie
        if c[0] in usate and c[1] in usate:
            continue
        usate |= set(c)
        mani.append(dict(carte=c, v=a["v"], n=a["n"], turno=sum(a["turni"]) / len(a["turni"]) if a["turni"] else None,
                         esempi=sorted((x for x in a["righe"] if x["mano"]), key=lambda x: (not x["vinta"], x["turno"] or 99))))
        if len(mani) == 3:
            break
    veloci = sorted((x for x in r_t if x["vinta"] and x["magie"] and not x["mull"]), key=lambda x: x["turno"])[:3]
    return dict(play=conta([x for x in rr if x["primo"] is True]), draw=conta([x for x in rr if x["primo"] is False]),
                chiude=media([x for x in r_t if x["vinta"]]), perde=media([x for x in r_t if not x["vinta"]]), terre=per_terre, mani=mani, veloci=veloci)


RX_TOGLIE = re.compile(r"destroy target|exile target|destroy all|exile all|counter target|deals? \d+ damage to target creature|target creature gets -|return target [a-z ]*to its owner")
RX_BRUCIA = re.compile(r"damage to any target|damage to each opponent|damage to target (player|opponent)")     # il fuoco che arriva in faccia spinge, non controlla: il Mono Red usciva Control
RX_PESCA = re.compile(r"draw (a|two|three) card")
RX_MANA = re.compile(r"add \{|add one mana|add two mana|search your library for [a-z ,]*land")


def archetipo(main, carte, chiude=None):
    """-> (nome, {asse: percentuale}), None se la lista non si legge."""
    magie = []
    for n, q in main.items():
        c = carte.get(n) or carte.get(n.split(" // ")[0].strip())
        if c and "Land" not in c["tipo"].split(" // ")[0]:
            magie += [c] * q
    if not magie:
        return None
    tot = len(magie)
    quota = lambda f: sum(1 for c in magie if f(c)) / tot
    creatura = lambda c: "Creature" in c["tipo"]
    testo = lambda c: c.get("testo", "").lower()
    costo = sum(c["cmc"] for c in magie) / tot
    punti = dict(Aggro=1.6 * quota(lambda c: creatura(c) and c["cmc"] <= 2) + 1.2 * quota(lambda c: c["cmc"] <= 3 and RX_BRUCIA.search(testo(c))) + 0.4 * max(0, 3 - costo),
                 Midrange=1.6 * quota(lambda c: creatura(c) and 3 <= c["cmc"] <= 4) + (0.2 if 2.5 < costo < 3.6 else 0),
                 Control=1.5 * quota(lambda c: RX_TOGLIE.search(testo(c)) or RX_PESCA.search(testo(c))) + 0.3 * quota(lambda c: not creatura(c)),
                 Ramp=2 * quota(lambda c: RX_MANA.search(testo(c))) + 1.2 * quota(lambda c: c["cmc"] >= 5))
    if chiude and chiude[1] >= 5:       # come chiude davvero conta piu' delle carte
        if chiude[0] <= 7:
            punti["Aggro"] *= 1.3
        elif chiude[0] >= 8:
            punti["Control"] *= 1.3
    somma = sum(punti.values()) or 1
    q = {k: round(100 * punti[k] / somma) for k in ASSI}
    o = sorted(ASSI, key=lambda k: -q[k])
    return (f"{o[0]}-{o[1]}" if q[o[0]] - q[o[1]] <= 5 else o[0]), q


def prova():
    carte = {"Plains": dict(nome="Plains", tipo="Basic Land — Plains", cmc=0, testo=""), "Orso": dict(nome="Orso", tipo="Creature — Bear", cmc=2, testo=""), "Gatto": dict(nome="Gatto", tipo="Creature — Cat", cmc=1, testo=""),
             "Fuoco": dict(nome="Fuoco", tipo="Instant", cmc=2, testo="Destroy target creature."), "Libro": dict(nome="Libro", tipo="Sorcery", cmc=3, testo="Draw two cards."), "Drago": dict(nome="Drago", tipo="Creature — Dragon", cmc=7, testo="")}
    import deckstring
    vero = deckstring.decodifica
    mani_finte = {"m1": {"Plains": 3, "Orso": 2, "Gatto": 2}, "m2": {"Plains": 2, "Orso": 2, "Gatto": 3}, "m3": {"Plains": 1, "Fuoco": 3, "Libro": 3}}
    _M.clear(); _M.update(mani_finte)
    def p(ora, vinta, mano_, primo=True, **k):
        return dict(quando=datetime.datetime(2026, 11, 1, ora), vinta=vinta, seat=1, giochi=[dict(active_player_id=1 if primo else 2, player_opening_hands=[mano_] if isinstance(mano_, str) else mano_)], **k)
    pp = [p(10, True, "m1"), p(11, True, "m2", primo=False), p(12, True, "m1"), p(13, False, "m3", primo=False), p(14, False, "m1"), p(15, True, ["m3", "m1"])]
    sc = {"2026-11-01T10:00": dict(turni=9, esito="vinta", motivo="Game"), "2026-11-01T11:00": dict(turni=10, esito="vinta", motivo="Concede"), "2026-11-01T12:00": dict(turni=7, esito="vinta", motivo="Game"),
          "2026-11-01T13:00": dict(turni=12, esito="vinta", motivo="Game"), "2026-11-01T15:00": dict(turni=3, esito="vinta", motivo="Concede")}
    a = analizza(pp, carte, sc)
    aggro = archetipo({"Orso": 20, "Gatto": 16, "Plains": 24}, carte, (5.0, 6))
    contr = archetipo({"Fuoco": 20, "Libro": 12, "Drago": 4, "Plains": 24}, carte)
    casi = [("sul play e sul draw", a["play"] == (3, 4) and a["draw"] == (1, 2)),
            ("i turni sono i tuoi: 9 di Arena sul play sono 5, 10 sul draw sono 5", abs(a["chiude"][0] - (5 + 5 + 4) / 3) < 1e-9 and a["chiude"][1] == 3),
            ("una scheda con l'esito diverso non si aggancia", a["perde"] is None),
            ("le mani per terre, senza i mulligan", a["terre"] == {3: [2, 3], 2: [1, 1], 1: [0, 1]}),
            ("la coppia che torna", a["mani"] and a["mani"][0]["carte"] == ("Gatto", "Orso") and (a["mani"][0]["v"], a["mani"][0]["n"]) == (3, 4)),
            ("la vittoria piu' veloce in testa", a["veloci"][0]["turno"] == 4),
            ("la coppia porta le sue mani intere, prima le vinte e la piu' veloce", [sum(x["mano"].values()) for x in a["mani"][0]["esempi"]] == [7, 7, 7, 7]
             and [x["vinta"] for x in a["mani"][0]["esempi"]] == [True, True, True, False] and a["mani"][0]["esempi"][0]["turno"] == 4),
            ("la vittoria veloce ha la sua mano", a["veloci"][0]["mano"] == mani_finte["m1"]),
            ("chi lascia al terzo turno non conta nei turni", analizza(pp[5:], carte, sc)["chiude"] is None),
            ("sotto le 3 partite nessuna mano", analizza(pp[:2], carte, sc)["mani"] == []),
            ("senza partite non cade", analizza([], carte, sc)["chiude"] is None),
            ("un mazzo di creature piccole e' aggro", aggro[0] == "Aggro"), ("rimozioni e pescate: control", contr[0] == "Control"),
            ("le percentuali fanno circa 100", 98 <= sum(aggro[1].values()) <= 102), ("senza carte lette: None", archetipo({"Plains": 60}, carte) is None)]
    _M.clear()
    for n, v in casi:
        print(("  ok   " if v else "  ROSSO ") + n)
    print(f"{sum(1 for _, v in casi if v)}/{len(casi)}")
    return 0 if all(v for _, v in casi) else 1


if __name__ == "__main__":
    sys.exit(prova())
