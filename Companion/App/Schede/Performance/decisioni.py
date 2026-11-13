"""L'analisi per decisione (13 nov 2026, Autore: «ok costruiamo l'analisi per decisione», «se imposto il filtro play on draw il win rate assoluto scende e
l'unica risorsa che avrei a disposizione per capire come migliorare in quella fase è analizzare il mulligan ma non so cosa dovrei inserire per leggere il mio
miglioramento al mulligan», «quando analizziamo i roi di giocata, li dobbiamo vedere anche sul grafico aggiungendo una linea sul grafico vs quella totale ...
tipo holdem manager»).

Fino a quel giorno Performance guardava la partita: «hai attaccato contro 2 terre stappate» diceva come e' finita la partita, non come e' andato quell'attacco.
Qui ogni combattimento e' una decisione col suo esito immediato, dai momenti di mana_aperto (lo stato prima del danno e quello a fine turno):

  attacco (tuo) / blocco (suo attacco, la tua difesa): quante creature attaccano e quante potevano, le terre stappate di chi difende, i blocchi; l'esito: le
  creature che attaccavano o bloccavano e non ci sono piu' a fine turno (tue e sue), le vite perse da chi difende, se chi difende ha giocato una magia nel
  turno prima del danno (un trucco, o una rimozione in combattimento) e se l'ha giocata chi attacca.

Limiti dichiarati: «a fine turno» comprende anche quel che succede dopo il combattimento (una rimozione nella seconda fase principale); le magie si sanno
nel turno, non il passo esatto (il trucco e' una magia di chi difende fra l'inizio del turno e il danno). Le vite sono quelle a fine turno: comprendono
anche un'altra perdita dopo il combattimento.

E i mulligan: le mani tenute per numero di terre sul play e sul draw, le mani rimandate indietro, le mani rischiose tenute (0-1 o 5+ terre), settimana per
settimana, cosi' si legge se le decisioni al mulligan migliorano.
"""
import os, sys
_casa = os.path.dirname(os.path.abspath(__file__))
while not os.path.isfile(os.path.join(_casa, "percorsi.py")):
    _casa = os.path.dirname(_casa)
if _casa not in sys.path:
    sys.path.insert(0, _casa)
import percorsi  # noqa: E402,F401
import collections  # noqa: E402
import datetime  # noqa: E402
import dati_analizzatore as DA  # noqa: E402

MINIMO = 10         # sotto, una riga e' un indizio (grigia)


def _ids(foto, lato):
    """Le creature (forza non vuota) di un lato della foto: {instanceId: [grp, tappata, pedina, forza, costituzione, id]}."""
    return {c[5]: c for c in ((foto or {}).get("c") or [[], []])[lato] or [] if c[3] is not None}


def _tutti_id(foto):
    return {c[5] for lato in ((foto or {}).get("c") or [[], []]) for c in lato or []}


def _istantaneo(g):
    nm = DA.nome_grp(g) if g not in DA.SENZA_FACCIA else None
    return "Instant" in ((DA._carta(nm) or {}).get("tipo") or "") if nm else False


def per_partita(x):
    """Le decisioni di combattimento di una partita (riga dell'analizzatore): [dict]. Vuota senza i momenti di mana_aperto o senza sapere il tuo posto."""
    d = DA._MANA.get(x.get("partita")) or {}
    seat = x.get("seat")
    mom = d.get("momenti") or []
    if seat not in (1, 2) or not mom:
        return []
    out = []
    for i, m in enumerate(mom):
        if m[0] != "comb" or len(m) < 5 or not m[4] or not m[4].get("att"):
            continue
        t, att, prima, info = m[1], m[2], m[3], m[4]
        dif = 2 if att == 1 else 1
        dopo = next((m2[3] for m2 in mom[i + 1:] if m2[0] == "fine" and m2[1] == t), None)
        if dopo is None and d.get("ultima"):
            dopo = d["ultima"][-1]
        resta = _tutti_id(dopo)
        att_ids = [a[0] for a in info["att"]]
        blk_ids = [b[0] for b in info.get("blocchi") or []]
        persi_att = sum(1 for a in att_ids if a not in resta)
        persi_blk = sum(1 for b in blk_ids if b not in resta)
        v0 = ((prima or {}).get("v") or [None, None])
        v1 = ((dopo or {}).get("v") or [None, None])
        danno = (v0[dif - 1] - v1[dif - 1]) if v0[dif - 1] is not None and v1[dif - 1] is not None else None
        # le magie del turno prima del danno: di chi difende tutte (nel turno dell'altro si lanciano solo istantanei e flash); di chi e' di turno solo gli
        # istantanei, se no conterebbero le magie della prima fase principale
        magie = [m2[4].get("chi") for m2 in mom[:i] if m2[0] == "spell" and m2[1] == t and m2[4] and not m2[4].get("ab")
                 and (m2[4].get("chi") != att or _istantaneo(m2[4].get("g")))]
        mio = att == seat
        pot = info.get("pot")
        out.append(dict(
            tipo="attacco" if mio else "blocco", t=t, turno=(t + 1) // 2, partita=x.get("partita"), vinta=x["vinta"], quando=x["quando"],
            attaccanti=len(att_ids), potevano=pot, tutto=bool(pot) and len(att_ids) >= pot, aperte=info.get("aperte"),
            blocchi=len(blk_ids), bloccato=bool(blk_ids),
            persi_miei=persi_att if mio else persi_blk, persi_suoi=persi_blk if mio else persi_att,
            danno=danno, trucco_suo=(dif if mio else att) in magie, trucco_mio=(att if mio else dif) in magie,
            # il guadagno della decisione (13 nov 2026, Autore: «lo esprimiamo come guadagno per spots e non per win rate perché qui analizziamo le azioni
            # non l'esito del game»): quanto cambia il tuo vantaggio (vite di differenza piu' due volte la forza in campo di differenza, DA.vantaggio) dallo
            # stato prima del danno a fine turno
            guadagno=DA.vantaggio(dopo, seat) - DA.vantaggio(prima, seat) if prima and dopo else None))
    return out


def tutte(r):
    """Le decisioni delle partite r, in ordine di tempo."""
    out = []
    for x in r:
        out += per_partita(x)
    return out


def _fascia_turno(n):
    return "Turns 1-3" if n <= 3 else "Turns 4-6" if n <= 6 else "Turns 7+"


def _aperte(a):
    return None if a is None else "0 untapped lands" if a == 0 else "1 untapped land" if a == 1 else "2+ untapped lands"


# le righe delle tabelle: (nome, condizione sulla decisione); la prima e' tutte
RIGHE_ATTACCO = [("All your attacks", lambda d: True),
                 ("Into 0 untapped lands", lambda d: d["aperte"] == 0), ("Into 1 untapped land", lambda d: d["aperte"] == 1),
                 ("Into 2+ untapped lands", lambda d: (d["aperte"] or 0) >= 2),
                 ("With everything that could", lambda d: d["tutto"]), ("Holding some back", lambda d: d["potevano"] and not d["tutto"]),
                 ("With everything, into 2+ untapped lands", lambda d: d["tutto"] and (d["aperte"] or 0) >= 2),
                 ("They blocked", lambda d: d["bloccato"]), ("Not blocked", lambda d: not d["bloccato"]),
                 ("They cast a spell before damage", lambda d: d["trucco_suo"]),
                 ("Turns 1-3", lambda d: d["turno"] <= 3), ("Turns 4-6", lambda d: 4 <= d["turno"] <= 6), ("Turns 7+", lambda d: d["turno"] >= 7)]
RIGHE_BLOCCO = [("All their attacks", lambda d: True),
                ("You blocked", lambda d: d["bloccato"]), ("You didn't block", lambda d: not d["bloccato"]),
                ("You blocked with 2+ creatures", lambda d: d["blocchi"] >= 2),
                ("They attacked into your 2+ untapped lands", lambda d: (d["aperte"] or 0) >= 2),
                ("They attacked with everything", lambda d: d["tutto"]),
                ("You cast a spell before damage", lambda d: d["trucco_mio"]), ("They cast a spell before damage", lambda d: d["trucco_suo"]),
                ("Turns 1-3", lambda d: d["turno"] <= 3), ("Turns 4-6", lambda d: 4 <= d["turno"] <= 6), ("Turns 7+", lambda d: d["turno"] >= 7)]


def guadagni(r, tipi, ff, base):
    """Il guadagno delle decisioni contro la media (13 nov 2026, Autore: «voglio vedere il gained by decisions vs la media delle partite: positivo linea
    verde negativo linea rossa»): per ogni partita di r (in ordine di tempo) la somma, sulle sue decisioni dei tipi `tipi` che passano f, di guadagno meno il
    guadagno medio delle stesse decisioni in tutte le partite `base`. ff: {tipo: filtri delle decisioni}. -> ({partita: scarto della partita}, {tipo: media}).
    Le partite senza decisioni scelte non ci sono."""
    medie = {}
    for t_ in tipi:
        g_ = [d["guadagno"] for d in scegli([d for d in tutte(base) if d["tipo"] == t_], (ff or {}).get(t_)) if d["guadagno"] is not None]
        medie[t_] = sum(g_) / len(g_) if g_ else 0.0
    per = {}
    for x in r:
        dd = [d for t_ in tipi for d in scegli([d for d in per_partita(x) if d["tipo"] == t_], (ff or {}).get(t_)) if d["guadagno"] is not None]
        if dd:
            per[x.get("partita")] = sum(d["guadagno"] - medie[d["tipo"]] for d in dd)
    return per, medie


def conti(dd):
    """I conti di un gruppo di decisioni: quante, in quante partite, % in cui hai perso almeno una creatura, % in cui lui ha perso, lo scambio medio (sue perse
    meno tue), il danno medio a chi difende, % col suo trucco, il win rate delle partite (ognuna una volta)."""
    n = len(dd)
    if not n:
        return dict(n=0, partite=0, perdi=None, uccidi=None, scambio=None, danno=None, trucco=None, wr=None, guadagno=None, ids=set())
    ids = {d["partita"] for d in dd}
    vinte = {d["partita"] for d in dd if d["vinta"]}
    danni = [d["danno"] for d in dd if d["danno"] is not None]
    gg = [d["guadagno"] for d in dd if d.get("guadagno") is not None]
    return dict(n=n, partite=len(ids), guadagno=round(sum(gg) / len(gg), 1) if gg else None, perdi=round(100 * sum(1 for d in dd if d["persi_miei"]) / n, 1),
                uccidi=round(100 * sum(1 for d in dd if d["persi_suoi"]) / n, 1),
                scambio=round(sum(d["persi_suoi"] - d["persi_miei"] for d in dd) / n, 2),
                danno=round(sum(danni) / len(danni), 1) if danni else None,
                trucco=round(100 * sum(1 for d in dd if d["trucco_suo"]) / n, 1),
                wr=round(100 * len(vinte) / len(ids), 1), ids=ids)


# i filtri delle decisioni (13 nov 2026, Autore: «Credo che decisions dovrebbe settarsi in base ai filtri che esprimo ... se io volessi sapere quanto
# perdo in difesa a T3 non ho possibilita' di settarlo», poi «i filtri per decision li imposti costruibili», «ovviamente tieni solo i filtri per noi "Player"
# perche' non possiamo valutare le decisioni di opponent»): solo le tue scelte e la situazione in cui le hai fatte. (chiave, nome, voci), per tipo.
TURNI_DEC = ("1", "2", "3", "4", "5", "6", "7", "8", "9+")
FILTRI = {"attacco": (("turno", "Turn", TURNI_DEC), ("aperte", "Their untapped lands", ("0", "1", "2+")),
                      ("tutto", "You attacked with everything", ("Yes", "No")), ("trucco_mio", "Your spell before damage", ("Yes", "No"))),
          "blocco": (("turno", "Turn", TURNI_DEC), ("aperte", "Your untapped lands", ("0", "1", "2+")), ("bloccato", "You blocked", ("Yes", "No")),
                     ("blocchi", "You blocked with", ("1 creature", "2+ creatures")), ("trucco_mio", "Your spell before damage", ("Yes", "No")))}


def valore(d, k):
    """La voce di un filtro delle decisioni per la decisione d (None: non si sa, o non vale per quel tipo di decisione)."""
    if k == "turno":
        return str(d["turno"]) if d["turno"] < 9 else "9+"
    if k == "aperte":
        return None if d["aperte"] is None else str(d["aperte"]) if d["aperte"] < 2 else "2+"
    if k == "blocchi":
        return None if not d["blocchi"] else "1 creature" if d["blocchi"] == 1 else "2+ creatures"
    return "Yes" if d[k] else "No"


def scegli(dd, f):
    """Le decisioni che passano i filtri f ({chiave: [voci]}; una voce sola vale come lista): fra le voci di un filtro basta una (turno 3 o 4), fra filtri
    diversi servono tutti."""
    f = {k: ([v] if isinstance(v, str) else list(v)) for k, v in (f or {}).items() if v}
    return [d for d in dd if all(valore(d, k) in v for k, v in f.items())]


def descrivi(f, tipo):
    """I filtri delle decisioni in parole: «turn 3 or 4 · you blocked yes»."""
    nomi = {k: n for k, n, _v in FILTRI.get(tipo, ())}
    out = []
    for k, v in (f or {}).items():
        if v:
            vv = [v] if isinstance(v, str) else v
            out.append(f"{nomi.get(k, k).lower()} {' or '.join(vv)}")
    return " · ".join(out)


def tabella(r, tipo, f=None):
    """Le righe della tabella degli attacchi («attacco») o dei blocchi («blocco») sulle partite r e coi filtri delle decisioni f: [dict(nome, **conti, poche)]."""
    dd = scegli([d for d in tutte(r) if d["tipo"] == tipo], f)
    out = []
    for nome, cond in (RIGHE_ATTACCO if tipo == "attacco" else RIGHE_BLOCCO):
        c = conti([d for d in dd if cond(d)])
        c.update(nome=nome, poche=c["n"] < MINIMO)
        out.append(c)
    return out


# ------------------------------------------------------------------ i mulligan
def _rischiosa(terre):
    return terre is not None and (terre <= 1 or terre >= 5)


def mulligan(r):
    """I mulligan delle partite r (righe dell'analizzatore, coi campi «terre», «partenza», «mulligan», «scartate»):
    tenute: {terre: {"Play": (partite, vinte), "Draw": (...)}} delle mani tenute (le terre 0-7);
    scartate: {terre: quante} delle mani rimandate indietro;
    dopo: (partite, vinte) di chi ha fatto almeno un mulligan; rischiose: (partite, vinte) delle mani tenute con 0-1 o 5+ terre senza mulligan; normali:
    (partite, vinte) delle altre tenute a 7."""
    ten = collections.defaultdict(lambda: {"Play": [0, 0], "Draw": [0, 0]})
    scart = collections.Counter()
    dopo, risc, norm = [0, 0], [0, 0], [0, 0]
    for x in r:
        if x.get("terre") is not None and x.get("partenza"):
            ten[min(x["terre"], 7)][x["partenza"]][0] += 1
            ten[min(x["terre"], 7)][x["partenza"]][1] += 1 if x["vinta"] else 0
        for s_ in x.get("scartate") or []:
            scart[min(s_, 7)] += 1
        if (x.get("mulligan") or 0) > 0:
            dopo[0] += 1; dopo[1] += 1 if x["vinta"] else 0
        elif x.get("terre") is not None:
            b = risc if _rischiosa(x["terre"]) else norm
            b[0] += 1; b[1] += 1 if x["vinta"] else 0
    return dict(tenute={k: {p: tuple(v) for p, v in d.items()} for k, d in ten.items()}, scartate=dict(scart), dopo=tuple(dopo), rischiose=tuple(risc),
                normali=tuple(norm))


def settimane(r, quante=8):
    """Il mulligan settimana per settimana (le ultime `quante` con partite): [dict(da, partite, mull %, rischiose %, wr dopo il mulligan, wr delle tenute a 7,
    wr di tutte)]. Cosi' si legge il miglioramento: meno mani rischiose tenute, e chi fa mulligan che vince di piu'."""
    per = collections.defaultdict(list)
    for x in r:
        q = x["quando"].date()
        per[q - datetime.timedelta(days=q.weekday())].append(x)
    out = []
    for da in sorted(per)[-quante:]:
        g = per[da]
        mull = [x for x in g if (x.get("mulligan") or 0) > 0]
        sette = [x for x in g if not (x.get("mulligan") or 0) and x.get("terre") is not None]
        risc = [x for x in sette if _rischiosa(x["terre"])]
        wr = lambda xs: round(100 * sum(1 for x in xs if x["vinta"]) / len(xs), 1) if xs else None
        out.append(dict(da=da, partite=len(g), mull=round(100 * len(mull) / len(g), 1), rischiose=round(100 * len(risc) / len(sette), 1) if sette else None,
                        wr_mull=wr(mull), wr_sette=wr(sette), wr=wr(g), n_mull=len(mull)))
    return out


def prova():
    casi = []
    q = datetime.datetime(2026, 11, 10)
    cr = lambda i, pw=2: [100 + i, 0, 0, pw, 2, i]
    foto = lambda mie, sue, v: dict(c=[mie, sue], v=v)
    vecchio = dict(DA._MANA)
    try:
        DA._MANA.clear()
        # tu (posto 1) attacchi al turno 3 con due creature contro 2 sue terre stappate; lui blocca con una, gioca un trucco: perdi un attaccante, lui niente;
        # poi lui attacca al turno 4 e tu non blocchi: 3 danni
        DA._MANA["g1"] = dict(momenti=[
            ["spell", 3, 1, None, dict(g=9, chi=2, ab=False)],
            ["spell", 3, 1, None, dict(g=8, chi=1, ab=False)],      # la tua magia di prima fase principale (non un istantaneo): non e' un tuo trucco
            ["comb", 3, 1, foto([cr(1), cr(2)], [cr(5)], [20, 20]), dict(att=[[1, 2], [2, 2]], blocchi=[[5, [1]]], pot=2, aperte=2)],
            ["fine", 3, 1, foto([cr(2)], [cr(5)], [20, 18])],
            ["comb", 4, 2, foto([cr(2)], [cr(5, 3)], [20, 18]), dict(att=[[5, 1]], blocchi=[], pot=1, aperte=0)],
            ["fine", 4, 2, foto([cr(2)], [cr(5, 3)], [17, 18])]])
        x = dict(partita="g1", seat=1, vinta=False, quando=q)
        dd = per_partita(x)
        a, b = dd
        casi.append(("l'attacco: 2 su 2 contro 2 terre stappate, bloccato, il suo trucco prima del danno, perdi un attaccante, lui niente, 2 danni",
                     a["tipo"] == "attacco" and a["tutto"] and a["aperte"] == 2 and a["bloccato"] and a["trucco_suo"] and a["persi_miei"] == 1
                     and a["persi_suoi"] == 0 and a["danno"] == 2 and not a["trucco_mio"]))
        casi.append(("il blocco: lui attacca, tu non blocchi, 3 danni a te, nessuno perde creature", b["tipo"] == "blocco" and not b["bloccato"] and b["danno"] == 3
                     and b["persi_miei"] == 0 and b["persi_suoi"] == 0 and b["turno"] == 2))
        casi.append(("il guadagno della decisione: il vantaggio a fine turno meno quello prima del danno (tu perdi un 2/2 e lui 2 vite: -4 + 2 = -2)",
                     a["guadagno"] == -2 and b["guadagno"] == -3))
        casi.append(("i filtri delle decisioni: turno 2 tiene tutte e due, terre stappate 2+ l'attacco, «hai bloccato: No» il blocco; turno 5 o 2 (una delle due)",
                     scegli(dd, {"turno": "2"}) == [a, b] and scegli(dd, {"aperte": ["2+"]}) == [a] and scegli(dd, {"bloccato": ["No"]}) == [b]
                     and scegli(dd, {"turno": ["5", "2"]}) == [a, b] and scegli(dd, {}) == dd))
        casi.append(("negativa: turno 5 niente; due filtri insieme li vogliono tutti e due (terre 2+ e hai bloccato No: nessuna)",
                     scegli(dd, {"turno": ["5"]}) == [] and scegli(dd, {"aperte": ["2+"], "bloccato": ["No"]}) == []
                     and descrivi({"turno": ["3", "4"]}, "blocco") == "turn 3 or 4"))
        pg, md = guadagni([x], ("attacco",), None, [x])
        casi.append(("il guadagno contro la media: una partita sola fa la media, lo scarto e' 0", md == {"attacco": -2.0} and pg == {"g1": 0.0}))
        ta = tabella([x], "attacco")
        casi.append(("la tabella degli attacchi: tutte, contro 2+ terre, con tutto; poche partite = indizio", ta[0]["n"] == 1 and ta[0]["perdi"] == 100.0
                     and next(t_ for t_ in ta if t_["nome"] == "Into 0 untapped lands")["n"] == 0 and ta[0]["poche"] and ta[0]["ids"] == {"g1"}))
        DA._MANA["g2"] = dict(momenti=[["comb", 3, 1, None, dict(att=[], blocchi=[])]])
        casi.append(("negativa: senza i momenti nessuna decisione; un combattimento senza attaccanti non conta",
                     per_partita(dict(partita="gx", seat=1, vinta=True, quando=q)) == [] and per_partita(dict(x, partita="g2")) == []))
    finally:
        DA._MANA.clear(); DA._MANA.update(vecchio)
    # i mulligan
    rr = [dict(quando=q, terre=3, partenza="Play", mulligan=0, vinta=True, scartate=[]),
          dict(quando=q, terre=1, partenza="Draw", mulligan=0, vinta=False, scartate=[]),
          dict(quando=q + datetime.timedelta(days=7), terre=2, partenza="Play", mulligan=1, vinta=True, scartate=[0]),
          dict(quando=q + datetime.timedelta(days=7), terre=6, partenza="Draw", mulligan=0, vinta=False, scartate=[])]
    m = mulligan(rr)
    casi.append(("i mulligan: tenute per terre e play/draw, una scartata a 0 terre, dopo il mulligan 1-0, rischiose (1 e 6 terre) 0-2, normali 1-0",
                 m["tenute"][3]["Play"] == (1, 1) and m["tenute"][1]["Draw"] == (1, 0) and m["scartate"] == {0: 1} and m["dopo"] == (1, 1)
                 and m["rischiose"] == (2, 0) and m["normali"] == (1, 1)))
    st = settimane(rr)
    casi.append(("settimana per settimana: due settimane, la seconda col mulligan al 50% e una rischiosa su una tenuta", len(st) == 2 and st[1]["mull"] == 50.0
                 and st[1]["rischiose"] == 100.0 and st[0]["rischiose"] == 50.0 and st[1]["wr_mull"] == 100.0))
    casi.append(("negativa: una mano a 2-4 terre non e' rischiosa", not _rischiosa(2) and not _rischiosa(4) and _rischiosa(1) and _rischiosa(5)))
    for n, ok in casi:
        print(("ok    " if ok else "ROSSO ") + n)
    print(f"{sum(1 for _n, ok in casi if ok)}/{len(casi)}")
    return all(ok for _n, ok in casi)


if __name__ == "__main__":
    if "--prova" in sys.argv:
        sys.exit(0 if prova() else 1)
    R = [x for x in DA.righe() if x["tipo"] == "Constructed"]
    for tipo in ("attacco", "blocco"):
        print(tipo.upper())
        for c in tabella(R, tipo):
            print(f"  {c['nome']:42s} {c['n']:4d} dec · {c['partite']:3d} games · lost {c['perdi']}% · killed {c['uccidi']}% · trade {c['scambio']} · "
                  f"dmg {c['danno']} · trick {c['trucco']}% · wr {c['wr']}%")
