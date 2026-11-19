"""Leak Finder · la carta sotto la lente, le win condition, le carte dell'Opponent nel tempo (18 nov 2026, Autore: «Analisi by the card: Nella scheda card una
sezione dedicata all'analisi individuale di una carta quanto sinergizza con altre carte e una rosa di carte attorno a essa migliori per sinergia (ovviamente
dati estratti dai replay e sommati per casistica). Analisi meta della carta dai log. Replay in cui e' presente la carta», «In cards dobbiamo aggiungere win
condition ovvero cosa il giocatore mette nel mazzo per determinare la vittoria della partita», «migliorare la conoscenza delle carte che ci troviamo contro sia
per partita e specificamente in che turno o contro quale delle nostre carte»).

Tutto dalle righe dell'analizzatore (dati_analizzatore.righe) e dai momenti di mana_aperto: niente dati di terzi.

    sinergie(r, nome)         la rosa: le tue carte lanciate nelle stesse partite, col win rate insieme contro quello della carta senza di loro
    meta(r, nome)             i tuoi mazzi che la giocano, gli avversari contro cui la lanci, chi la gioca contro di te
    partite_con(r, nome)      le partite in cui c'e' (lanciata da te o da lui), dalla piu' recente, col turno del primo lancio
    win_condition(r)          la riga WIN CONDITIONS: le carte che chiudono le tue vittorie (il colpo letale, se no chi ha fatto piu' danni)
    sue_quando(r)             la riga THEIR CARDS · WHEN AND ON WHAT: il turno medio del suo primo lancio e le tue carte che ha preso di mira

    py -I -X utf8 Companion/App/Schede/Performance/analisi_carta.py      le prove, con le negative
"""
import collections
import os
import sys

_casa = os.path.dirname(os.path.abspath(__file__))
while not os.path.isfile(os.path.join(_casa, "percorsi.py")):
    _casa = os.path.dirname(_casa)
if _casa not in sys.path:
    sys.path.insert(0, _casa)
import percorsi  # noqa: E402,F401
import dati_analizzatore as DA  # noqa: E402

MINIMO = 5          # partite insieme per entrare nella rosa (sotto: grigio)


def _wr(v, n):
    return round(100 * v / n, 1) if n else None


def sinergie(r, nome, quante=12, minimo=MINIMO):
    """La rosa della carta: per ogni tua altra carta lanciata nelle stesse partite (non terre), le partite insieme, il win rate insieme e la differenza col
    win rate della carta nelle partite senza quel compagno (lift). Dalla differenza piu' alta, da `minimo` partite insieme. -> dict(n, wr, rosa=[...])."""
    con = [x for x in r if nome in set(x.get("mie_lanciate") or [])]
    n, v = len(con), sum(1 for x in con if x["vinta"])
    insieme, vinte = collections.Counter(), collections.Counter()
    for x in con:
        for p in set(x.get("mie_lanciate") or []) - {nome}:
            if DA.e_terra(p):
                continue
            insieme[p] += 1
            vinte[p] += 1 if x["vinta"] else 0
    rosa = []
    for p, k in insieme.items():
        senza_n, senza_v = n - k, v - vinte[p]
        wr_i = _wr(vinte[p], k)
        wr_s = _wr(senza_v, senza_n)
        rosa.append(dict(nome=p, n=k, vinte=vinte[p], perse=k - vinte[p], wr=wr_i, wr_senza=wr_s,
                         lift=None if wr_s is None else round(wr_i - wr_s, 1), poche=k < minimo, quota=round(100 * k / n, 1) if n else 0.0,
                         filtro=("lanciate", [nome, p])))
    rosa.sort(key=lambda c: (c["poche"], -(c["lift"] if c["lift"] is not None else -999), -c["n"], c["nome"]))
    return dict(n=n, vinte=v, wr=_wr(v, n), rosa=rosa[:quante])


def meta(r, nome):
    """La carta nel meta dei tuoi log: i tuoi mazzi che la lanciano (partite, win rate), gli archetipi dell'Opponent contro cui l'hai lanciata, gli archetipi
    che la lanciano contro di te (e il tuo win rate contro). -> dict(miei=[(mazzo, n, wr)], contro=[(archetipo, n, wr)], suoi=[(archetipo, n, wr)])."""
    def tab(pp, chiave):
        c, w = collections.Counter(), collections.Counter()
        for x in pp:
            k = (x.get(chiave) or "").strip() or "Unknown"
            c[k] += 1
            w[k] += 1 if x["vinta"] else 0
        return sorted(((k, n, _wr(w[k], n)) for k, n in c.items()), key=lambda t: (-t[1], t[0]))
    mie = [x for x in r if nome in set(x.get("mie_lanciate") or [])]
    sue = [x for x in r if nome in set(x.get("sue_lanciate") or [])]
    return dict(miei=tab(mie, "mio"), contro=tab(mie, "suo"), suoi=tab(sue, "suo"), n_mie=len(mie), n_sue=len(sue))


def _primo_lancio(x, nome, mio):
    """Il giro (il turno di quel giocatore) del primo lancio della carta nella partita, dalle azioni di mana_aperto; None se non si sa."""
    d = DA._MANA.get(x.get("partita")) or {}
    seat = x.get("seat")
    if seat not in (1, 2):
        return None
    for t, s_, cosa, g, _tp in d.get("azioni") or []:
        if cosa == "magia" and (s_ == seat) == mio and DA.nome_intero(DA.nome_grp(g) or "") == nome:
            return (t + 1) // 2
    return None


def partite_con(r, nome, quante=200):
    """Le partite in cui c'e' la carta: lanciata da te o dall'Opponent. -> [dict(x, chi «you»|«opponent»|«both», giro)], dalla piu' recente."""
    out = []
    for x in r:
        mia, sua = nome in set(x.get("mie_lanciate") or []), nome in set(x.get("sue_lanciate") or [])
        if not (mia or sua):
            continue
        chi = "both" if mia and sua else "you" if mia else "opponent"
        out.append(dict(x=x, chi=chi, giro=_primo_lancio(x, nome, mia)))
    out.sort(key=lambda z: z["x"]["quando"], reverse=True)
    return out[:quante]


def _chiude(x):
    """Le carte che hanno chiuso una tua vittoria: chi ha il merito «letale»; senza (l'Opponent ha concesso) chi ha fatto piu' volte danno. Niente pedine."""
    if not x.get("vinta"):
        return set()
    try:
        import ev_partita as EV_
        ev = EV_._eventi(x)
    except Exception:       # noqa: BLE001 - senza i momenti niente win condition
        return set()
    let, danni = set(), collections.Counter()
    for k in ev:
        if k.get("pedina"):
            continue
        for mer, *_r in k.get("eventi") or []:
            if mer == "letale":
                let.add(k["nome"])
            elif mer == "danno":
                danni[k["nome"]] += 1
    if let:
        return let
    if danni:
        top = max(danni.values())
        return {n for n, v in danni.items() if v == top}
    return set()


def win_condition(r, quante=40, minimo=2):
    """La riga WIN CONDITIONS: per ogni tua carta, in quante vittorie ha chiuso la partita (_chiude), la quota delle tue vittorie e il win rate delle partite
    in cui l'hai lanciata (il suo filtro). Da `minimo` vittorie chiuse. -> righe di Cards."""
    chiuse, partite, vinte = collections.Counter(), collections.Counter(), collections.Counter()
    nv = 0
    for x in r:
        if x["vinta"]:       # solo le carte che hai lanciato in quella partita: il numero sotto la carta e' quello del suo filtro (il clic)
            nv += 1
            chiuse.update(_chiude(x) & set(x.get("mie_lanciate") or []))
        for n in set(x.get("mie_lanciate") or []):
            partite[n] += 1
            vinte[n] += 1 if x["vinta"] else 0
    out = []
    for n, k in chiuse.items():
        if k < minimo:
            continue
        np_ = partite[n]
        out.append(dict(nome=n, n=np_, vinte=vinte[n], perse=np_ - vinte[n], wr=_wr(vinte[n], np_) or 0.0, quota=round(100 * k / nv, 1) if nv else 0.0,
                        chiuse=k, filtro=("lanciate", n)))
    out.sort(key=lambda c: (-c["chiuse"], c["nome"]))
    return out[:quante]


def _bersagli_suoi(x):
    """Le tue carte prese di mira dalle magie e abilita' dell'Opponent: [(sua carta, tua carta, giro)] dai momenti di mana_aperto."""
    d = DA._MANA.get(x.get("partita")) or {}
    seat = x.get("seat")
    if seat not in (1, 2):
        return []
    out = []
    for m in d.get("momenti") or []:
        if m[0] != "spell" or len(m) < 5 or not isinstance(m[4], dict) or m[4].get("chi") in (seat, None):
            continue
        info = m[4]
        sua = DA.nome_intero(DA.nome_grp(info.get("g")) or "")
        if not sua:
            continue
        miei = {c_[5]: c_ for c_ in ((m[3] or {}).get("c") or [[], []])[seat - 1] or [] if len(c_) > 5}
        for id_ in set(info.get("bers") or []) | set(DA.colpiti_di(info) or []):
            c_ = miei.get(id_)
            if c_ is not None:
                mia = DA.nome_intero(DA.nome_grp(c_[0]) or "") or "a token"
                out.append((sua, "a token" if c_[2] else mia, (m[1] + 1) // 2))
    return out


def sue_quando(r, quante=40, minimo=3):
    """La riga THEIR CARDS · WHEN AND ON WHAT: per ogni sua carta lanciata, in quante partite, il turno medio del suo primo lancio (il giro dell'Opponent), le
    tue carte che ha preso di mira (le tre piu' colpite) e il tuo win rate in quelle partite. Da `minimo` partite. -> righe di Cards."""
    partite, vinte, giri = collections.Counter(), collections.Counter(), collections.defaultdict(list)
    colpite = collections.defaultdict(collections.Counter)
    for x in r:
        sue = set(x.get("sue_lanciate") or [])
        for n in sue:
            if DA.e_terra(n):
                continue
            partite[n] += 1
            vinte[n] += 1 if x["vinta"] else 0
            g = _primo_lancio(x, n, False)
            if g is not None:
                giri[n].append(g)
        for sua, mia, _g in _bersagli_suoi(x):
            colpite[sua][mia] += 1
    out = []
    for n, k in partite.items():
        if k < minimo:
            continue
        out.append(dict(nome=n, n=k, vinte=vinte[n], perse=k - vinte[n], wr=_wr(vinte[n], k), quota=round(100 * k / len(r), 1) if r else 0.0,
                        giro=round(sum(giri[n]) / len(giri[n]), 1) if giri[n] else None, colpite=colpite[n].most_common(3),
                        filtro=("sue_lanciate", n), quando_sua=True))
    out.sort(key=lambda c: (-c["n"], c["nome"]))
    return out[:quante]


# ---------------------------------------------------------------- la scheda della carta (la sotto-scheda Card di Cards)
# Autore, 18 nov 2026: «la scheda cards deve avere delle sotto schede: Una per l'analisi specifica di una carta: Questa analisi deve darci dati diversi se
# siamo settati in limited o constructed. Per constructed ci deve dare statistiche su quante sinergie conosciute ci sono tra lei e altre carte. Sinergie
# verificate e realizzatesi in campo dalle piu' deboli alle piu' forti. Ci deve dire in quanto e' giocata in quanti mazzi appare quanto valore ci genera ecc»

def uso(r, nome):
    """Quanto e' giocata nelle partite r: nelle liste (partite, mazzi diversi, copie medie), lanciata (partite, win rate), contro di te.
    -> dict(n, in_lista, mazzi, copie, lanciata, vinte, wr, contro, wr_contro, quota)."""
    lis = [x for x in r if (x.get("deck") or {}).get(nome)]
    lan = [x for x in r if nome in set(x.get("mie_lanciate") or [])]
    sue = [x for x in r if nome in set(x.get("sue_lanciate") or [])]
    v = sum(1 for x in lan if x["vinta"])
    return dict(n=len(r), in_lista=len(lis), mazzi=len({x.get("mio") or "?" for x in lis}),
                copie=round(sum(x["deck"][nome] for x in lis) / len(lis), 1) if lis else None,
                lanciata=len(lan), vinte=v, wr=_wr(v, len(lan)), contro=len(sue), wr_contro=_wr(sum(1 for x in sue if x["vinta"]), len(sue)),
                quota=_wr(len(lan), len(r)))


def sinergie_note(r, nome):
    """Le sinergie conosciute dal testo (grado C, le tabelle PRODUCE/VUOLE della rete del Board, ev_partita.in_sinergia) fra la carta e le altre carte dei tuoi
    mazzi nelle partite r (non terre): [dict(nome, famiglie, mazzi)], prima le carte che stanno con lei in piu' liste. Se la carta non e' mai nelle tue liste
    (una carta dell'Opponent) i compagni sono tutte le carte delle tue liste, con mazzi 0."""
    import ev_partita as EV_
    insieme = collections.Counter()
    for x in r:
        d = x.get("deck") or {}
        if not d.get(nome):
            continue
        for q_ in d:
            if q_ != nome and d[q_] and not DA.e_terra(q_):
                insieme[q_] += 1
    if not insieme:
        for x in r:
            for q_, k in (x.get("deck") or {}).items():
                if k and q_ != nome and not DA.e_terra(q_):
                    insieme[q_] += 0
    out = []
    for q_, k in insieme.items():
        fam = EV_.in_sinergia(nome, [q_])
        if fam:
            out.append(dict(nome=q_, famiglie=fam, mazzi=k))
    out.sort(key=lambda c: (-c["mazzi"], c["nome"]))
    return out


def sinergie_in_campo(r, base, nome, note=None):
    """Le sinergie conosciute che si sono avverate: la carta e il compagno in campo insieme (tuoi, a fine dello stesso turno) nelle partite r. Per ogni
    compagno: le partite in cui sono stati insieme, il win rate, i turni insieme e l'EV di quei turni (lo scarto dei turni contro il solito, ev_partita), media
    per partita. Dalla piu' debole alla piu' forte (EV per partita), quelle sotto 3 partite in fondo. -> [dict(nome, famiglie, n, vinte, wr, turni, ev, poche)]."""
    import ev_partita as EV_
    note = sinergie_note(r, nome) if note is None else note
    fam = {c["nome"]: c["famiglie"] for c in note}
    if not fam:
        return []
    mappa = EV_._mappa_turni(base)
    acc = {}
    for x in r:
        ev = EV_._eventi(x)
        if not ev:
            continue
        tt_ = EV_._turni_di(base, x.get("partita"))
        fine_p = tt_[-1]["t"] if tt_ else None

        def turni(k):
            fino = k["esce"] - 1 if k["esce"] is not None else (fine_p if fine_p is not None else k.get("ultimo", k["entra"]))
            return set(range(k["entra"], max(k["entra"], fino) + 1))
        miei = set().union(*[turni(k) for k in ev if k["nome"] == nome and not k["pedina"]] or [set()])
        if not miei:
            continue
        for k in ev:
            if k["pedina"] or k["nome"] not in fam:
                continue
            comuni = miei & turni(k)
            if not comuni:
                continue
            a = acc.setdefault(k["nome"], dict(partite={}, turni=0, ev=0.0))
            a["partite"][x.get("partita")] = bool(x["vinta"])
            a["turni"] += len(comuni)
            a["ev"] += sum((mappa.get((x.get("partita"), t)) or {}).get("scarto", 0.0) for t in comuni)
    out = []
    for q_, a in acc.items():
        n = len(a["partite"])
        v = sum(a["partite"].values())
        out.append(dict(nome=q_, famiglie=fam[q_], n=n, vinte=v, perse=n - v, wr=_wr(v, n), turni=a["turni"], ev=round(a["ev"] / n, 2) if n else 0.0,
                        poche=n < 3, filtro=("lanciate", [nome, q_])))
    out.sort(key=lambda c: (c["poche"], c["ev"], c["nome"]))
    return out


def valore(r, base, nome):
    """Il valore che la carta ti genera: la sua riga di ev_partita.carte (in_campo, ev_meriti, conta dei meriti, sopravvive), None se non c'e'."""
    import ev_partita as EV_
    return next((c for c in EV_.carte(r, base, quante=10 ** 6, minimo=0) if c["nome"] == nome), None)


def limited(nome):
    """Nel Limited, i dati del draft: il GIH di 17Lands (Premier e Quick) e l'ALSA dal quaderno del set della carta, e i tuoi pick dai log (quante volte
    l'hai presa, il pick medio nel pack, quante volte l'hai vista e lasciata). -> dict(gih={fmt: (gih, partite, alsa, data)}, prese, pick_medio, vista,
    lasciata)."""
    out = dict(gih={}, prese=0, pick_medio=None, vista=0, lasciata=0)
    try:
        import anagrafe_carte as AN
        for s_ in ((DA._carta(nome) or {}).get("sets") or {}):
            try:
                rr = AN.per_nome(nome, s_)
            except Exception:      # noqa: BLE001 - un set senza quaderno
                continue
            for fmt in ("premier", "quick"):
                g = ((rr or {}).get("gih") or {}).get(fmt)
                if g and fmt not in out["gih"]:
                    out["gih"][fmt] = (g.get("gih"), g.get("partite"), g.get("alsa"), g.get("data"))
    except Exception:       # noqa: BLE001 - senza quaderni niente GIH
        pass
    try:
        import draft_log as DL
        nome_g = lambda g: DA.nome_intero(DA.nome_grp(g) or "") if g not in DA.SENZA_FACCIA else ""
        posti = []
        for d in DL.tutti():
            for kk, pack in d["pack"].items():
                if nome not in {nome_g(g) for g in pack}:
                    continue
                out["vista"] += 1
                if nome_g(d["pick"].get(kk)) == nome:
                    out["prese"] += 1
                    posti.append(int(kk.split("-")[1]) + 1)
                else:
                    out["lasciata"] += 1
        out["pick_medio"] = round(sum(posti) / len(posti), 1) if posti else None
    except Exception:       # noqa: BLE001 - senza log di draft niente pick
        pass
    return out


# ---------------------------------------------------------------- prove

def prova():
    import datetime
    casi = []
    vecchio_m, vecchio_n = dict(DA._MANA), dict(DA._NOMI_GRP)
    vero_t = DA.e_terra
    try:
        DA.e_terra = lambda n: n == "Plains"
        DA._NOMI_GRP.update({901: "Ajani's Pridemate", 902: "Healer's Hawk", 903: "Cut Down", 904: "Plains"})
        q = lambda d: datetime.datetime(2026, 11, d)
        r = []
        # 10 partite: Pridemate sempre; con Hawk 6 (5 vinte), senza Hawk 4 (1 vinta); lui lancia Cut Down in 4 partite sul Pridemate al suo turno 2
        for i in range(10):
            hawk = i < 6
            vinta = (i < 5) or i == 6
            r.append(dict(partita=f"ac{i}", seat=1, vinta=vinta, quando=q(i + 1), mio="Lifegain", suo="Rakdos" if i % 2 else "Azorius",
                          mie_lanciate=["Ajani's Pridemate"] + (["Healer's Hawk"] if hawk else []) + ["Plains"],
                          sue_lanciate=["Cut Down"] if i >= 6 else []))
            DA._MANA[f"ac{i}"] = dict(azioni=[[3, 1, "magia", 901, "C"]] + ([[4, 2, "magia", 903, "I"]] if i >= 6 else []),
                                      momenti=([["spell", 4, 2, dict(c=[[[901, False, False, 2, 2, 77]], []]), dict(g=903, chi=2, bers=[77], colpiti=[77])]]
                                               if i >= 6 else []))
        s = sinergie(r, "Ajani's Pridemate")
        hw = next(c for c in s["rosa"] if c["nome"] == "Healer's Hawk")
        casi.append(("la rosa: Healer's Hawk con Pridemate 6 partite all'83%, senza 25%: lift +58; negativa: le terre non entrano",
                     s["n"] == 10 and hw["n"] == 6 and hw["wr"] == 83.3 and hw["wr_senza"] == 25.0 and hw["lift"] == 58.3
                     and all(c["nome"] != "Plains" for c in s["rosa"])))
        casi.append(("negativa: una carta mai lanciata non ha rosa", sinergie(r, "Shock")["n"] == 0 and sinergie(r, "Shock")["rosa"] == []))
        m = meta(r, "Ajani's Pridemate")
        casi.append(("il meta: un tuo mazzo (Lifegain, 10 partite), due archetipi contro; Cut Down lanciata contro di te da Azorius e Rakdos",
                     m["miei"][0][:2] == ("Lifegain", 10) and {a for a, _n, _w in m["contro"]} == {"Rakdos", "Azorius"}
                     and meta(r, "Cut Down")["n_sue"] == 4))
        pc = partite_con(r, "Cut Down")
        casi.append(("le partite con la carta: 4, dalla piu' recente, sua, lanciata al suo turno 2; negativa: una carta assente non ha partite",
                     len(pc) == 4 and pc[0]["x"]["partita"] == "ac9" and all(z["chi"] == "opponent" and z["giro"] == 2 for z in pc)
                     and partite_con(r, "Shock") == []))
        sq = sue_quando(r)
        casi.append(("le sue carte: Cut Down in 4 partite, al suo turno 2, sempre sul tuo Pridemate; negativa: sotto 3 partite non c'e'",
                     len(sq) == 1 and sq[0]["nome"] == "Cut Down" and sq[0]["giro"] == 2.0 and sq[0]["colpite"] == [("Ajani's Pridemate", 4)]
                     and sue_quando(r, minimo=5) == []))
        import ev_partita as EV_
        vero_e = EV_._eventi
        try:
            EV_._eventi = lambda x: ([dict(nome="Ajani's Pridemate", pedina=False, eventi=[("letale", 5, "comb", 3.0)]),
                                      dict(nome="Spirit", pedina=True, eventi=[("letale", 5, "comb", 1.0)])] if x["partita"] != "ac6"
                                     else [dict(nome="Healer's Hawk", pedina=False, eventi=[("danno", 3, "comb", 1.0), ("danno", 4, "comb", 1.0)]),
                                           dict(nome="Ajani's Pridemate", pedina=False, eventi=[("danno", 4, "comb", 1.0)])])
            wc = win_condition(r)
            ap = next(c for c in wc if c["nome"] == "Ajani's Pridemate")
            senza_lancio = all(c["nome"] != "Healer's Hawk" for c in win_condition(r, minimo=1))     # in ac6 Hawk chiude ma non e' lanciato
            r[6]["mie_lanciate"] = r[6]["mie_lanciate"] + ["Healer's Hawk"]
            casi.append(("win condition: Pridemate chiude 5 vittorie col letale; nella vittoria per concessione chi ha fatto piu' danni (Hawk, 1 sola: sotto il "
                         "minimo); negative: le pedine e le sconfitte non contano, chi chiude senza essere lanciato nemmeno (il numero e' quello del filtro)",
                         ap["chiuse"] == 5 and ap["quota"] == 83.3 and senza_lancio
                         and all(c["nome"] not in ("Spirit", "Healer's Hawk") for c in wc) and win_condition(r, minimo=1)[-1]["nome"] == "Healer's Hawk"))
            r[6]["mie_lanciate"] = r[6]["mie_lanciate"][:-1]
        finally:
            EV_._eventi = vero_e
        # la scheda della carta: uso, sinergie dal testo, sinergie in campo
        for i, x in enumerate(r):
            x["deck"] = {"Ajani's Pridemate": 4, "Healer's Hawk": 4 if i < 6 else 0, "Plains": 16}
        u = uso(r, "Ajani's Pridemate")
        casi.append(("l'uso: in 10 liste di un mazzo, 4 copie, lanciata 10 volte; negativa: Cut Down non e' nelle tue liste ma contro di te 4 volte",
                     u["in_lista"] == 10 and u["mazzi"] == 1 and u["copie"] == 4 and u["lanciata"] == 10 and uso(r, "Cut Down")["in_lista"] == 0
                     and uso(r, "Cut Down")["contro"] == 4))
        vero_s, vero_m, vero_td = EV_.in_sinergia, EV_._mappa_turni, EV_._turni_di
        try:
            EV_.in_sinergia = lambda n, altri: ["lifegain"] if {n, *altri} == {"Ajani's Pridemate", "Healer's Hawk"} else []
            sn_ = sinergie_note(r, "Ajani's Pridemate")
            casi.append(("le sinergie dal testo: Healer's Hawk in 6 liste; negativa: le terre no", [c_["nome"] for c_ in sn_] == ["Healer's Hawk"]
                         and sn_[0]["mazzi"] == 6))
            EV_._eventi = lambda x: ([dict(nome="Ajani's Pridemate", pedina=False, entra=2, esce=None, eventi=[]),
                                      dict(nome="Healer's Hawk", pedina=False, entra=3, esce=5, eventi=[])] if x["partita"] in ("ac0", "ac1", "ac2")
                                     else [dict(nome="Ajani's Pridemate", pedina=False, entra=2, esce=3, eventi=[]),
                                           dict(nome="Healer's Hawk", pedina=False, entra=4, esce=None, eventi=[])])
            EV_._mappa_turni = lambda base: {(f"ac{i}", t): dict(scarto=1.0) for i in range(10) for t in range(1, 9)}
            EV_._turni_di = lambda base, p_: [dict(t=8)]
            ic = sinergie_in_campo(r, r, "Ajani's Pridemate")
            casi.append(("in campo insieme: Hawk con Pridemate nelle 3 partite in cui si sono incrociati, turni 3 e 4, EV +2 a partita; negativa: dove "
                         "Pridemate esce prima che entri Hawk non conta", len(ic) == 1 and ic[0]["n"] == 3 and ic[0]["turni"] == 6 and ic[0]["ev"] == 2.0))
        finally:
            EV_.in_sinergia, EV_._eventi, EV_._mappa_turni, EV_._turni_di = vero_s, vero_e, vero_m, vero_td
    finally:
        DA.e_terra = vero_t
        DA._MANA.clear(); DA._MANA.update(vecchio_m)
        DA._NOMI_GRP.clear(); DA._NOMI_GRP.update(vecchio_n)
    for nome, ok in casi:
        print(("ok    " if ok else "ROSSO ") + nome)
    print(f"{sum(1 for _n, ok in casi if ok)}/{len(casi)}")
    return all(ok for _n, ok in casi)


if __name__ == "__main__":
    sys.exit(0 if prova() else 1)
