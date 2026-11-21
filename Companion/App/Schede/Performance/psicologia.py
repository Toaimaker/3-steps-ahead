"""UpgradePlan01, il voto dalle linee psicologiche del giocatore, primo pezzo (Autore, 20 nov 2026: «è un essere umano e prova ansia di perdere e
desiderio di vincere con facilità. Vuole ingannare e ottenere valore dall'inganno, ma vuole anche salvarsi la vita e sopravvivere / su questo si misura
la giocata», «eh si riscriviamolo partendo dalle linee psicologiche del giocatore»; il piano: Note/UpgradePlan01.md; la misura:
Note/UpgradePlan01_Psicologia.md).

Lo spot e' ogni turno dell'Hero con il turno dell'Opponent che segue (la finestra). Lo stato si legge dal tavolo all'inizio del turno, mai dal risultato:
  sotto pressione   la P a inizio turno sotto PRESSIONE_P, o l'Opponent ti chiude in OROLOGIO turni o meno con la forza che ha in campo
  tranquillo        il resto

I comportamenti, dal log (grado C, le regole sono scritte qui):
  panico     tappato     a fine turno nessuna terra stappata, almeno una magia lanciata, almeno 3 terre (svuota la mano e resta senza risposte)
             no_corsa    nessun attacco con creature in campo quando la corsa era tua (il tuo orologio su di lui non piu' lungo del suo su di te)
             chump       nel suo turno blocchi, il tuo bloccante muore, il suo attaccante resta, e senza quel blocco non morivi
  freddezza  corsa       attacchi quando la corsa e' tua
  inganno    trappola    lanci una magia nel suo combattimento
             bluff       a fine turno 2+ terre stappate, in mano niente di istantaneo o flash, lui ha creature e nel suo turno non attacca con tutte

Il valore: lo scarto della finestra (il tuo turno piu' il suo dopo) contro il solito del mazzo (ev_partita.turni_con_scarto). Per ogni comportamento,
la finestra con e senza fra gli spot nello stesso stato; la negativa: i comportamenti rimescolati fra gli spot dello stesso mazzo e stato.

    py -I -X utf8 Companion/App/Schede/Performance/psicologia.py [--limited]
    py -I -X utf8 Companion/App/Schede/Performance/psicologia.py --prova
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

PRESSIONE_P = 30.0
OROLOGIO = 2
LINEE = {"tappato": "panico", "no_corsa": "panico", "chump": "panico", "corsa": "freddezza", "trappola": "inganno", "bluff": "inganno",
         "aspetta": "speranza", "aspetta_catena": "strategia", "catena": "strategia"}
NOMI = {"tappato": "tapped out after casting", "no_corsa": "no attack when the race was yours", "chump": "chump block you did not need",
        "corsa": "attacked when the race was yours", "trappola": "cast a spell in the Opponent's combat (a trap)",
        "bluff": "mana open with nothing to cast, he did not attack with everything",
        "aspetta": "waited: a creature (no flash) was castable, cast nothing", "aspetta_catena": "waited, then 2+ spells in synergy next turn",
        "catena": "2+ spells in synergy in the turn"}


def orologio(forza, vite):
    """In quanti turni la forza in campo toglie le vite (99 senza forza)."""
    return 99 if forza <= 0 else max(1, math.ceil(max(vite, 1) / forza))


def _lato(f, i):
    c = (f.get("c") or [[], []])[i] or []
    cre = [z for z in c if len(z) > 5 and z[3] is not None and not DA.e_terra(DA.nome_grp(z[0]) or "")]
    v = (f.get("v") or [20, 20])[i]
    return dict(cre={z[5]: max(0, z[3] or 0) for z in cre}, forza=sum(max(0, z[3] or 0) for z in cre), vite=20 if v is None else v,
                mano=list((f.get("m") or [[], []])[i] or []))


_ISTANTANEA = {}


def istantanea(g):
    """La carta si lancia nel turno dell'altro: istantaneo o flash (dal testo, grado C)."""
    if g not in _ISTANTANEA:
        c = DA._carta(DA.nome_grp(g) or "") or {}
        tipo, testo = (c.get("tipo") or "").split(" // ")[0], c.get("testo") or ""
        _ISTANTANEA[g] = "Instant" in tipo or "Flash" in testo.split("\n")[0] or testo.startswith("Flash")
    return _ISTANTANEA[g]


_CREATURA = {}


def creatura(g):
    if g not in _CREATURA:
        c = DA._carta(DA.nome_grp(g) or "") or {}
        _CREATURA[g] = "Creature" in (c.get("tipo") or "").split(" // ")[0]
    return _CREATURA[g]


_SIN = {}


def in_catena(nomi):
    """Fra le magie lanciate nel turno c'e' almeno una coppia in sinergia (ev_partita.in_sinergia, dal testo: grado C)."""
    k = tuple(sorted(set(n for n in nomi if n)))
    if k not in _SIN:
        _SIN[k] = len(k) >= 2 and any(EV.in_sinergia(a, [b]) for i, a in enumerate(k) for b in k[i + 1:])
    return _SIN[k]


def chump(m_comb, f_dopo, seat_mio, vite):
    """Un blocco che non serviva: nel combattimento dell'Opponent (m_comb = momento «comb» con att e blocchi) un tuo bloccante muore (non c'e' piu' a
    fine turno), il suo attaccante resta, e senza quel blocco la forza che passava non toglieva tutte le tue vite."""
    info = m_comb[4] or {}
    f0 = m_comb[3]
    a = seat_mio - 1
    lui = _lato(f0, 1 - a)
    miei_dopo = set(_lato(f_dopo, a)["cre"]) if f_dopo else set()
    suoi_dopo = set(_lato(f_dopo, 1 - a)["cre"]) if f_dopo else set()
    attaccanti = [x[0] for x in info.get("att") or []]
    totale = sum(lui["cre"].get(i, 0) for i in attaccanti)
    for blocc, chi in info.get("blocchi") or []:
        if blocc in miei_dopo:
            continue
        if any(x in suoi_dopo for x in chi) and totale < vite:
            return True
    return False


def spot_partita(x):
    """I turni dell'Hero di una partita: [dict(partita, mazzo, t, pressione, compo (set dei comportamenti), giro)]. [] senza i dati."""
    d = DA._MANA.get(x.get("partita")) or {}
    seat = x.get("seat")
    if seat not in (1, 2) or not d.get("foto"):
        return []
    c = EV.partita(x)
    if c is None:
        return []
    a, b = seat - 1, 2 - seat
    fine = {t: (att, f) for t, att, f in d.get("foto") or []}
    stappate = {(t, chi): (s, n) for t, chi, s, n in d.get("fine") or []}
    magie = collections.Counter((t, s_) for t, s_, _g, _f in d.get("fasi") or [])
    in_comb = {(t, s_) for t, s_, _g, f in d.get("fasi") or [] if f == "Phase_Combat"}
    comb = {(m[1], m[2]): m for m in d.get("momenti") or [] if m[0] == "comb" and len(m) > 4 and m[4] and isinstance(m[3], dict)}
    p0 = {z["t"]: z["p0"] for z in c["turni"] if z["mio"]}
    out = []
    for t in sorted(p0):
        f0 = (fine.get(t - 1) or (None, d.get("mano0")))[1] if t > 1 else d.get("mano0")
        if not f0 or t not in fine:
            continue
        io, lui = _lato(f0, a), _lato(f0, b)
        mio_or, suo_or = orologio(io["forza"], lui["vite"]), orologio(lui["forza"], io["vite"])
        pressione = p0[t] < PRESSIONE_P or suo_or <= OROLOGIO
        compo = set()
        s_n = stappate.get((t, seat))
        if s_n and s_n[0] == 0 and s_n[1] >= 3 and magie.get((t, seat)):
            compo.add("tappato")
        corsa_mia = io["cre"] and mio_or <= suo_or
        attaccato = (t, seat) in comb
        if corsa_mia and attaccato:
            compo.add("corsa")
        elif corsa_mia and not attaccato:
            compo.add("no_corsa")
        t2 = t + 1
        if (t2, seat) in in_comb:
            compo.add("trappola")
        f_fine = fine[t][1]
        mano = _lato(f_fine, a)["mano"]
        if s_n and s_n[0] >= 2 and mano is not None and not any(istantanea(g) for g in mano) and _lato(f_fine, b)["cre"]:
            m2 = comb.get((t2, 3 - seat))
            n_att = len((m2[4] or {}).get("att") or []) if m2 else 0
            if n_att < len(_lato(f_fine, b)["cre"]):
                compo.add("bluff")
        m2 = comb.get((t2, 3 - seat))
        if m2 and (m2[4] or {}).get("blocchi") and chump(m2, (fine.get(t2) or (None, None))[1], seat, _lato(m2[3], a)["vite"]):
            compo.add("chump")
        out.append(dict(partita=x.get("partita"), mazzo=DA.chiave_mazzo(x), t=t, giro=(t + 1) // 2, pressione=pressione, compo=compo))
    # lo stratega e chi spera (20 nov 2026): aspetta = Arena ti offriva una creatura pagabile all'ultima priorita' e non hai lanciato niente;
    # la catena = 2+ magie nel turno in sinergia fra loro; aspetta_catena = aspetti e al tuo turno dopo fai la catena
    nomi_t = collections.defaultdict(list)
    for t_, s_, g_, _f in d.get("fasi") or []:
        if s_ == seat:
            nomi_t[t_].append(DA.nome_grp(g_))
    for s in out:
        t = s["t"]
        if in_catena(nomi_t.get(t, [])):
            s["compo"].add("catena")
        off = leak.arena_offriva(d, seat, t)
        if off and not magie.get((t, seat)) and any(creatura(g) and not istantanea(g) for g in off["lanci"]):
            s["compo"].add("aspetta")
            if in_catena(nomi_t.get(t + 2, [])):
                s["compo"].add("aspetta_catena")
    return out


def con_finestra(r, base):
    """Gli spot delle partite r con lo scarto della finestra (il tuo turno e il suo dopo) contro il solito del mazzo dalle partite base."""
    sc = collections.defaultdict(dict)
    for z in EV.turni_con_scarto(r, base):
        sc[z["partita"]][z["t"]] = z["scarto"]
    out = []
    for x in r:
        for s in spot_partita(x):
            a_, b_ = sc[s["partita"]].get(s["t"]), sc[s["partita"]].get(s["t"] + 1)
            if a_ is None or b_ is None:
                continue
            s["finestra"] = a_ + b_
            out.append(s)
    return out


def _media(v):
    n = len(v)
    if n < 2:
        return None, None, n
    m = sum(v) / n
    return m, math.sqrt(sum((q - m) ** 2 for q in v) / (n - 1) / n), n


def misura(S, compo, giri=2000, seme=7):
    """Per uno stato gia' scelto: la finestra con il comportamento meno senza, e la p contro lo stesso conto coi comportamenti rimescolati fra gli spot
    dello stesso mazzo (la negativa)."""
    def diff(L):
        a_ = [w for k, w in L if k]
        b_ = [w for k, w in L if not k]
        return (sum(a_) / len(a_) - sum(b_) / len(b_)) if len(a_) >= 5 and len(b_) >= 5 else None
    L = [(compo in s["compo"], s["finestra"]) for s in S]
    vera = diff(L)
    if vera is None:
        return dict(vera=None, p=None, n=sum(1 for k, _w in L if k))
    rnd = random.Random(seme)
    per = collections.defaultdict(list)
    for i, s in enumerate(S):
        per[s["mazzo"]].append(i)
    finte = []
    for _ in range(giri):
        k = [kk for kk, _w in L]
        for idx in per.values():
            v = [k[i] for i in idx]
            rnd.shuffle(v)
            for i, q in zip(idx, v):
                k[i] = q
        finte.append(diff([(kk, w) for kk, (_k, w) in zip(k, L)]))
    p = (sum(1 for q in finte if abs(q) >= abs(vera)) + 1) / (len(finte) + 1)
    return dict(vera=vera, p=p, n=sum(1 for k, _w in L if k))


def prova():
    casi = []
    casi.append(("l'orologio: 6 di forza contro 13 vite fa 3 turni, senza forza 99", orologio(6, 13) == 3 and orologio(0, 5) == 99))
    F = lambda mie, sue, v=(10, 20): dict(c=[[[1, 0, 0, p, p, i, None] for i, p in mie], [[2, 0, 0, p, p, i, None] for i, p in sue]], v=list(v))
    DA_ = DA.e_terra
    DA.e_terra = lambda n: False
    try:
        m = ["comb", 4, 2, F([(11, 2)], [(21, 3), (22, 2)]), dict(att=[[21, 1], [22, 1]], blocchi=[[11, [21]]])]
        casi.append(("chump: il tuo 2/2 muore, il suo 3/3 resta, 5 di forza contro 10 vite", chump(m, F([], [(21, 3), (22, 2)]), 1, 10)))
        casi.append(("negativa: con 4 vite quel blocco ti salvava, non e' un chump", not chump(m, F([], [(21, 3), (22, 2)]), 1, 4)))
        casi.append(("negativa: se il suo attaccante muore e' uno scambio", not chump(m, F([], [(22, 2)]), 1, 10)))
    finally:
        DA.e_terra = DA_
    rnd = random.Random(3)
    S = [dict(mazzo="M", compo={"chump"} if i % 3 == 0 else set(), finestra=rnd.gauss(-6 if i % 3 == 0 else 0, 3)) for i in range(150)]
    casi.append(("la misura trova un comportamento che costa 6 punti (p sotto 0,01)", (lambda m_: m_["vera"] < -4 and m_["p"] < 0.01)(misura(S, "chump", 300))))
    S0 = [dict(s, finestra=rnd.gauss(0, 3)) for s in S]
    casi.append(("negativa: finestre a caso, nessuna differenza (p sopra 0,05)", misura(S0, "chump", 300)["p"] > 0.05))
    for n_, ok in casi:
        print(("ok    " if ok else "ROSSO ") + n_)
    print(f"{sum(1 for _n, ok in casi if ok)}/{len(casi)}")
    return all(ok for _n, ok in casi)


if __name__ == "__main__":
    if "--prova" in sys.argv:
        sys.exit(0 if prova() else 1)
    tipo = "Limited" if "--limited" in sys.argv else "Constructed"
    R = [x for x in DA.righe() if x["tipo"] == tipo]
    S = con_finestra(R, R)
    for stato, nome in ((True, "UNDER PRESSURE"), (False, "CALM")):
        G = [s for s in S if s["pressione"] == stato]
        m, es, n = _media([s["finestra"] for s in G])
        print(f"\n{tipo} · {nome}: {len(G)} Hero turns, window vs the deck's usual {m:+.1f} ±{es:.1f}")
        for k in NOMI:
            r_ = misura(G, k)
            quota = 100 * r_["n"] / len(G) if G else 0
            riga = f"  {LINEE[k]:9s} {NOMI[k]:58s} {r_['n']:5d} ({quota:4.1f}%)"
            if r_["vera"] is not None:
                riga += f"  with - without {r_['vera']:+5.1f}  p {r_['p']:.3f}"
            print(riga)
