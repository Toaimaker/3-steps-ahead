"""UpgradePlan01, passo 3: la discesa automatica dal macro al micro (Autore, 20 nov 2026: «le analisi incastrano le gerarchie una alla voce dell'altra
in base a cosa si deve analizzare», «Sì, passo 3»; il piano: Note/UpgradePlan01.md).

Il motore scende da solo, scala dentro scala, dove l'EV cala rispetto al solito del mazzo, fino allo spot. Le unita' sono le fasi dei turni delle partite
scelte (ev_partita.turni_con_scarto: lo scarto di ogni fase contro il solito dello stesso mazzo; le fasi sommano il turno, nessun punto contato due volte).
Ogni fase porta le sue voci, una per scala, dal macro al micro:

  TEMPO      chi gioca (Hero, Opponent) > tratto della partita (turni 1-3, 4-6, 7+) > fase (inizio, main 1, combattimento, main 2)
  BOARD      a inizio turno: le creature (Hero dietro, pari, avanti) > le vite (dietro, pari, avanti di 5) > le carte in mano (meno, pari, piu')
  MAZZO      nel turno, le carte lanciate dall'Hero: la meccanica (le famiglie che producono, ev_partita.tag_carta) > il tipo > la carta
  AVVERSARIO l'archetipo dell'Opponent (matchup_log)

A ogni passo si guardano tutte le voci non ancora scelte, da sole e a due a due (il tempo e' la chiave del solito: ogni suo valore da solo e' pari per
costruzione, e la discesa deve poterlo attraversare), e per ogni valore la cella: le partite che la hanno, per ogni partita la somma degli scarti delle sue fasi nella cella, la media per partita e l'errore per partita.
Si sceglie la cella piu' forte nel verso cercato, con almeno MINIMO partite e EFFETTO punti a partita, se batte il 99% delle celle migliori trovate
coi punti rimescolati fra le fasi della stessa partita (test a permutazione, PERMUTAZIONI giri: Benjamini-Hochberg da solo, con tutte le coppie,
faceva passare il rumore fino al 47% delle volte; tarato sul rumore: 2 percorsi falsi su 60, una perdita di 3 punti a partita trovata 20 volte su 20); si scende dentro e si ripete. Si ferma quando nessuna cella passa. Il percorso si legge sempre dal macro al micro: tempo, mazzo, board, avversario. La stessa discesa al rovescio trova dove guadagni.

Uso: discesa.scendi_auto(r, base, verso) -> (percorso, catalogo), l'autoswitch fra i due cataloghi; discesa.scendi(r, base, cat=) -> [nodo]; nodo = dict(scala, voce, valore, testo, partite, fasi, media, es, p, totale).
    py -I -X utf8 Companion/App/Schede/Performance/discesa.py [--mazzo "UW Bouncer"] [--limited]
    py -I -X utf8 Companion/App/Schede/Performance/discesa.py --prova
"""
import os
import sys
import math
import collections

_casa = os.path.dirname(os.path.abspath(__file__))
while not os.path.isfile(os.path.join(_casa, "percorsi.py")):
    _casa = os.path.dirname(_casa)
if _casa not in sys.path:
    sys.path.insert(0, _casa)
import percorsi  # noqa: E402,F401
import dati_analizzatore as DA  # noqa: E402
import ev_partita as EV  # noqa: E402

MINIMO = 10         # partite in una cella
EFFETTO = 1.0       # punti a partita: sotto, una cella non e' un luogo dove si perde (le fasi a zero, dove non succede niente, non passano)
FDR = 0.05          # per _bh (resta per chi lo usa); la discesa usa il test a permutazione
PERMUTAZIONI = 100
QUANTILE = 0.99      # tarato sul rumore (60 prove di solo rumore): 95° percentile 4 su 40, 97,5° 6 su 60
PROFONDITA = 6
SCALE = {"tempo": ("chi", "tratto", "fase"), "board": ("creature", "vite", "mano"), "mazzo": ("meccanica", "tipo", "carta"),
         "avversario": ("archetipo",)}
NOMI = {"chi": "whose turn", "tratto": "part of the game", "fase": "phase", "creature": "creatures at the start of the turn",
        "vite": "life at the start of the turn", "mano": "cards in hand at the start of the turn", "meccanica": "mechanic you cast",
        "tipo": "type you cast", "carta": "card you cast", "archetipo": "opponent's deck"}
TIPI = {"C": "Creature", "I": "Instant", "S": "Sorcery", "E": "Enchantment", "A": "Artifact", "P": "Planeswalker", "B": "Battle"}
FASI = {"inizio": "start of the turn", "main1": "main phase 1", "comb": "combat", "main2": "main phase 2", "turn": "the whole turn"}


def _trio(d, soglia=0):
    return "behind" if d < -soglia else ("ahead" if d > soglia else "even")


def _foto_inizio(d):
    """{turno di Arena: foto a fine del turno prima} dalla partita di mana_aperto."""
    out = {}
    fine = {t: f for t, _a, f in d.get("foto") or []}
    for t in range(1, 60):
        f = fine.get(t - 1) if t > 1 else d.get("mano0")
        if f:
            out[t] = f
    return out


def unita(r, base):
    """Le fasi dei turni delle partite r con lo scarto contro il solito del loro mazzo (dalle partite base), e le voci di ogni scala."""
    out = []
    per_partita = collections.defaultdict(list)
    for z in EV.turni_con_scarto(r, base):
        per_partita[z["partita"]].append(z)
    righe = {x["partita"]: x for x in r}
    for pid, turni in per_partita.items():
        x = righe.get(pid)
        if x is None:
            continue
        d = DA._MANA.get(pid) or {}
        seat = x.get("seat")
        a, b = (seat - 1, 2 - seat) if seat in (1, 2) else (0, 1)
        inizio = _foto_inizio(d)
        lanci = collections.defaultdict(list)
        for az in d.get("azioni") or []:
            if len(az) >= 5 and az[1] == seat and az[2] == "magia":
                lanci[az[0]].append(az)
        for z in turni:
            t = z["t"]
            f = inizio.get(t) or {}
            lati = f.get("c") or [[], []]
            cre = lambda lato: sum(1 for c in lato or [] if len(c) >= 5 and c[3] is not None)
            v = f.get("v") or [20, 20]
            n = f.get("n") or [0, 0]
            nomi = [DA.nome_grp(az[3]) for az in lanci.get(t, []) if az[3]]
            nomi = [DA.nome_intero(nn) if hasattr(DA, "nome_intero") else nn for nn in nomi if nn]
            mecc, tipi = set(), set()
            for nn in nomi:
                try:
                    mecc |= set(EV.tag_carta(nn)[0])
                except Exception:       # noqa: BLE001 - una carta senza testo non ha meccanica
                    pass
            for az in lanci.get(t, []):
                tipi |= {TIPI[c] for c in (az[4] or "") if c in TIPI}
            voci = dict(chi="Hero" if z["mio"] else "Opponent",
                        tratto="turns 1-3" if z["giro"] <= 3 else ("turns 4-6" if z["giro"] <= 6 else "turns 7+"),
                        creature=_trio(cre(lati[a]) - cre(lati[b])) if f else None,
                        vite=_trio((v[a] if v[a] is not None else 20) - (v[b] if v[b] is not None else 20), 4) if f else None,
                        mano=_trio((n[a] or 0) - (n[b] or 0)) if f else None,
                        meccanica=(mecc or {"nothing cast"}) if z["mio"] else None,
                        tipo=(tipi or {"nothing cast"}) if z["mio"] else None,
                        carta=(set(nomi) or {"nothing cast"}) if z["mio"] else None,
                        archetipo=x.get("suo") or None)
            for ph in z.get("fasi") or []:
                vv = dict(voci, fase=FASI.get(ph["f"], ph["f"]))
                out.append(dict(partita=pid, scarto=ph["scarto"], voci=vv))
    return out


def _valori(u, voce):
    v = u["voci"].get(voce)
    if v is None:
        return ()
    return v if isinstance(v, set) else (v,)


def _p(z):
    return math.erfc(abs(z) / math.sqrt(2))


def _stat(per, conta, etich):
    s = list(per.values())
    n = len(s)
    if n < MINIMO:
        return None
    m = sum(s) / n
    if abs(m) < EFFETTO:
        return None
    sd = math.sqrt(sum((q - m) ** 2 for q in s) / (n - 1)) if n > 1 else 0.0
    es = sd / math.sqrt(n)
    z = m / es if es > 0 else 0.0
    return dict(cond=etich, partite=n, fasi=conta, media=m, es=es, z=z, p=_p(z), totale=sum(s))


def celle(U, voci):
    """Le celle di una o due voci insieme: per ogni combinazione di valori, dict(cond=((voce, valore), ...), partite, fasi, media (punti a partita),
    es, z, p, totale). Ogni partita conta una volta: la somma degli scarti delle sue fasi nella cella."""
    per = collections.defaultdict(lambda: collections.defaultdict(float))
    conta = collections.Counter()
    for u in U:
        combo = [()]
        for v in voci:
            combo = [c + ((v, val),) for c in combo for val in _valori(u, v)]
        for c in combo:
            per[c][u["partita"]] += u["scarto"]
            conta[c] += 1
    return [st for c, g in per.items() for st in [_stat(g, conta[c], c)] if st]


def _bh(cc):
    """Benjamini-Hochberg al FDR: le celle che passano."""
    cc = sorted(cc, key=lambda c: c["p"])
    m = len(cc)
    k = 0
    for i, c in enumerate(cc, 1):
        if c["p"] <= FDR * i / m:
            k = i
    return cc[:k]


def _indice(U, gruppi):
    """Le celle dei gruppi una volta sola (chi ci sta non cambia quando si rimescolano i punti): (codice della partita di ogni fase, quante partite,
    [(cond, indici delle fasi)]), nell'ordine dei gruppi e dei valori come celle(). Solo le celle con almeno MINIMO partite che restringono il gruppo."""
    import numpy as np
    pid = {}
    gi = np.array([pid.setdefault(u["partita"], len(pid)) for u in U], dtype=np.int64)
    out = []
    n = len(U)
    for g in gruppi:
        per = {}
        for i, u in enumerate(U):
            combo = [()]
            for v in g:
                combo = [c + ((v, val),) for c in combo for val in _valori(u, v)]
            for c in combo:
                per.setdefault(c, []).append(i)
        for c, idx in per.items():
            if len(idx) >= n:
                continue
            a = np.array(idx, dtype=np.int64)
            if len(np.unique(gi[a])) >= MINIMO:
                out.append((c, a))
    return gi, len(pid), out


def _migliore_ix(sc, ix, verso):
    """Come _migliore, sugli indici di _indice e coi punti sc (array): la cella piu' forte nel verso cercato."""
    import numpy as np
    gi, G, cc = ix
    best = None
    for c, idx in cc:
        g_ = gi[idx]
        som = np.bincount(g_, weights=sc[idx], minlength=G)
        v = som[np.bincount(g_, minlength=G) > 0]
        k = len(v)
        m = float(v.mean())
        if abs(m) < EFFETTO or (m < 0) != (verso < 0):
            continue
        es = float(v.std(ddof=1)) / math.sqrt(k) if k > 1 else 0.0
        z = m / es if es > 0 else 0.0
        if best is None or abs(z) > abs(best["z"]):
            best = dict(cond=c, partite=k, fasi=len(idx), media=m, es=es, z=z, p=_p(z), totale=float(v.sum()))
    return best


def _migliore(U, gruppi, verso, ix=None):
    """La cella piu' forte nel verso cercato che restringe il gruppo (tutto il gruppo non e' un passo)."""
    import numpy as np
    ix = ix or _indice(U, gruppi)
    return _migliore_ix(np.array([u["scarto"] for u in U], dtype=float), ix, verso)


def _soglia(U, gruppi, verso, giri=PERMUTAZIONI, seme=11, ix=None):
    """Il test a permutazione: i punti rimescolati fra le fasi della stessa partita (cosi' le voci non dicono piu' niente e il totale di ogni partita
    resta), la cella migliore di ogni giro; la soglia e' il QUANTILE. Tante celle provate insieme non fanno piu' passare il rumore."""
    import random
    import numpy as np
    ix = ix or _indice(U, gruppi)
    rnd = random.Random(seme)
    per = collections.defaultdict(list)
    for i, u in enumerate(U):
        per[u["partita"]].append(i)
    mx = []
    for _ in range(giri):
        sc = [u["scarto"] for u in U]
        for idx in per.values():
            v = [sc[i] for i in idx]
            rnd.shuffle(v)
            for i, q in zip(idx, v):
                sc[i] = q
        c = _migliore_ix(np.array(sc, dtype=float), ix, verso)
        mx.append(abs(c["z"]) if c else 0.0)
    mx.sort()
    return mx[int(QUANTILE * (len(mx) - 1))] if mx else float("inf")


def _migliore_lento(U, gruppi, verso):
    """La versione di prima (senza numpy), per la prova d'identita'."""
    n = len(U)
    best = None
    for g in gruppi:
        for c in celle(U, g):
            if (c["media"] < 0) != (verso < 0) or c["fasi"] >= n:
                continue
            if best is None or abs(c["z"]) > abs(best["z"]):
                best = c
    return best


ORDINE = ("tempo", "mazzo", "board", "avversario")     # come si legge il percorso: dal macro al micro (Autore: partite > turni > fasi; mazzi; board)


VECCHIO = dict(scale=SCALE, ordine=ORDINE, nomi=NOMI, coppie=None)     # il catalogo del passo 3; quello del passo 3b: catalogo_scale.CATALOGO


def _scala(voce, cat=None):
    sc = (cat or VECCHIO)["scale"]
    return next(s for s, vv in sc.items() if voce in vv)


def _dentro(u, cond):
    return all(val in _valori(u, voce) for voce, val in cond)


def scendi(r, base, verso=-1, U=None, cat=None):
    """La discesa: dove l'EV cala (verso -1) o sale (verso +1) di piu' rispetto al solito del mazzo, scala dentro scala. A ogni passo le celle di una
    voce nuova e di due insieme (cosi' si attraversa un livello che da solo vale zero: il tempo e' la chiave del solito, ogni suo valore da solo e'
    pari per costruzione). -> [nodo] in ordine dal macro al micro, ognuno coi numeri della cella fino a lui."""
    cat = cat or VECCHIO
    SC, ORD, NM = cat["scale"], cat["ordine"], cat["nomi"]
    if U is None:
        if cat is VECCHIO:
            U = unita(r, base)
        else:
            import catalogo_scale as CS
            U = CS.unita(r, base)
    U0 = U
    scelte = []
    for _ in range(PROFONDITA):
        # tutte le voci non ancora scelte, da sole e a due a due (un livello che vale zero da solo, come il turno dell'Hero ai turni 4-6 quando il main 1
        # guadagna quanto il combattimento perde, non ferma la discesa); il percorso si legge poi dal macro al micro
        usate_v = {v for v, _x in scelte}
        teste = [v for s in SC for v in SC[s] if v not in usate_v]
        due = cat["coppie"](teste) if cat.get("coppie") else [(v1, v2) for k, v1 in enumerate(teste) for v2 in teste[k + 1:]]
        gruppi = [(v,) for v in teste] + due
        ix = _indice(U, gruppi)
        c = _migliore(U, gruppi, verso, ix)
        if c is None or abs(c["z"]) < _soglia(U, gruppi, verso, ix=ix):
            break
        scelte += list(c["cond"])
        U = [u for u in U if _dentro(u, c["cond"])]
    if not scelte:
        return []
    # il percorso in ordine dal macro al micro; il mazzo (le carte che l'Hero lancia) vuol dire che il turno e' dell'Hero
    voci_sc = {v for v, _x in scelte}
    if any(_scala(v, cat) in ("mazzo", "occasioni") or v in ("attacco",) for v in voci_sc) and "chi" not in voci_sc:
        scelte.append(("chi", "Hero"))
    scelte.sort(key=lambda cv: (ORD.index(_scala(cv[0], cat)), SC[_scala(cv[0], cat)].index(cv[0])))
    out, cond = [], ()
    for voce, val in scelte:
        cond = cond + ((voce, val),)
        g = collections.defaultdict(float); n_f = 0
        for u in U0:
            if _dentro(u, cond):
                g[u["partita"]] += u["scarto"]; n_f += 1
        sv = list(g.values()); n = len(sv)
        m = sum(sv) / n if n else 0.0
        es = math.sqrt(sum((q - m) ** 2 for q in sv) / (n - 1)) / math.sqrt(n) if n > 1 else 0.0
        z = m / es if es > 0 else 0.0
        out.append(dict(scala=_scala(voce, cat), voce=voce, valore=val, testo=f"{NM[voce]}: {val}", partite=n, fasi=n_f, media=m, es=es, z=z, p=_p(z),
                        totale=sum(sv)))
    return out


def punti(percorso):
    """I punti che l'ultimo passo di un percorso spiega: effetto a partita x partite (0 senza percorso)."""
    return abs(percorso[-1]["media"]) * percorso[-1]["partite"] if percorso else 0.0


def scendi_auto(r, base, verso=-1, U_vecchio=None, U_nuovo=None):
    """L'autoswitch (Autore, 20 nov 2026: «non possiamo usarli entrambi con autoswitch intelligente?»): la discesa col catalogo del passo 3 (celle
    larghe, spiega piu' punti) e col catalogo delle scale del passo 3b (piu' voci, spot piu' precisi), e tiene il percorso che spiega piu' punti
    (effetto x partite). Misurato su meta' partite mai viste (Note/UpgradePlan01_Passo3b.md): 58 percorsi replicati su 59 contro 40 e 51 dei due da
    soli, 9.459 punti spiegati contro 6.343 e 4.748, rumore 0 su 40. -> (percorso, "vecchio"|"nuovo"|None)."""
    import catalogo_scale as CS
    a = scendi(r, base, verso, U=U_vecchio)
    b = scendi(r, base, verso, U=U_nuovo, cat=CS.CATALOGO)
    if not a and not b:
        return [], None
    return (a, "vecchio") if punti(a) >= punti(b) else (b, "nuovo")


def scrivi(percorso, titolo):
    righe = [titolo]
    for i, c in enumerate(percorso, 1):
        righe.append(f"  {i}. {c['testo']:55s} {c['media']:+6.1f} a game ±{c['es']:.1f}  ({c['partite']} games, {c['fasi']} phases, p {c['p']:.3f})")
    if not percorso:
        righe.append("  nothing passes the test: no place where this deck clearly loses (or gains) against its own usual")
    return "\n".join(righe)


def prova():
    casi = []
    import random
    rnd = random.Random(5)
    # unita' finte: 40 partite; le fasi del combattimento dell'Hero ai turni 4-6 perdono 6 punti, il resto e' rumore attorno a zero
    U = []
    for g in range(40):
        for chi in ("Hero", "Opponent"):
            for tr in ("turns 1-3", "turns 4-6", "turns 7+"):
                for fa in ("main phase 1", "combat", "main phase 2"):
                    s = rnd.gauss(0, 2)
                    if chi == "Hero" and tr == "turns 4-6" and fa == "combat":
                        s -= 6
                    U.append(dict(partita=f"g{g}", scarto=s, voci=dict(chi=chi, tratto=tr, fase=fa, creature="even", vite="even", mano="even",
                                                                       meccanica=None, tipo=None, carta=None, archetipo="X")))
    per = scendi(None, None, U=U)
    casi.append(("la discesa trova Hero > turni 4-6 > combattimento", [c["valore"] for c in per[:3]] == ["Hero", "turns 4-6", "combat"]))
    casi.append(("e scende in ordine nella scala del tempo", [c["voce"] for c in per[:3]] == ["chi", "tratto", "fase"]))
    # la chiave del solito: ogni valore del tempo da solo e' pari (qui il turno dell'Hero perde 6 nel combattimento e ne guadagna 6 nel main 1);
    # la discesa deve attraversarlo e arrivare al combattimento
    Uz = [dict(u, scarto=u["scarto"] + (6 if u["voci"]["chi"] == "Hero" and u["voci"]["tratto"] == "turns 4-6" and u["voci"]["fase"] == "main phase 1"
                                        else 0)) for u in U]
    pz = scendi(None, None, U=Uz)
    casi.append(("attraversa un livello che da solo vale zero (Hero turni 4-6 pari) e arriva al combattimento",
                 any(c["valore"] == "combat" for c in pz) and pz[-1]["media"] < -3))
    rnd2 = random.Random(9)
    U0 = [dict(u, scarto=rnd2.gauss(0, 2)) for u in U]
    casi.append(("negativa: sul solo rumore nessuna cella passa", scendi(None, None, U=U0) == []))
    pos = scendi(None, None, verso=1, U=U)
    casi.append(("negativa: al rovescio (dove guadagni) la cella che perde non esce", all(c["valore"] != "combat" or c["media"] > 0 for c in pos)))
    poche = [u for u in U if int(u["partita"][1:]) < MINIMO - 1]
    casi.append(("negativa: sotto il minimo di partite nessuna cella", scendi(None, None, U=poche) == []))
    U2 = [dict(u, voci=dict(u["voci"], tipo={"Creature"} if u["voci"]["chi"] == "Hero" else None)) for u in U]
    p2 = scendi(None, None, U=U2)
    casi.append(("il mazzo si guarda solo dopo «Hero»", all(c["scala"] != "mazzo" for c in p2[:1])))
    U3 = [dict(u, scarto=0.0) for u in U]
    casi.append(("negativa: fasi tutte a zero non sono un luogo dove si perde (minimo di 1 punto a partita)", scendi(None, None, U=U3) == []))
    casi.append(("il test di Benjamini-Hochberg: 0,001 e 0,02 su 2 passano, 0,2 no",
                 len(_bh([dict(p=0.001), dict(p=0.02)])) == 2 and _bh([dict(p=0.2)]) == []))
    casi.append(("l'autoswitch tiene il percorso che spiega piu' punti", punti([dict(media=-2.0, partite=50)]) > punti([dict(media=-6.0, partite=10)])))
    casi.append(("negativa: senza percorso i punti sono zero", punti([]) == 0.0))
    teste = [v for vv in SCALE.values() for v in vv]
    gr = [(v,) for v in teste] + [(a, b) for k, a in enumerate(teste) for b in teste[k + 1:]]
    for v_ in (-1, 1):
        a_, b_ = _migliore(U, gr, v_), _migliore_lento(U, gr, v_)
        casi.append((f"la cella migliore in numpy e' quella di prima (verso {v_:+d})",
                     (a_ is None and b_ is None) or (a_ and b_ and a_["cond"] == b_["cond"] and abs(a_["z"] - b_["z"]) < 1e-9)))
    for n_, ok in casi:
        print(("ok    " if ok else "ROSSO ") + n_)
    print(f"{sum(1 for _n, ok in casi if ok)}/{len(casi)}")
    return all(ok for _n, ok in casi)


if __name__ == "__main__":
    if "--prova" in sys.argv:
        sys.exit(0 if prova() else 1)
    tipo = "Limited" if "--limited" in sys.argv else "Constructed"
    R = [x for x in DA.righe() if x["tipo"] == tipo]
    mazzi = [sys.argv[sys.argv.index("--mazzo") + 1]] if "--mazzo" in sys.argv else \
        [m for m, n in collections.Counter(x.get("mio") for x in R).most_common() if m and n >= 60]
    for m in mazzi:
        G = [x for x in R if (x.get("mio") or "").strip() == m.strip()]
        import catalogo_scale as CS
        U, U2 = unita(G, R), CS.unita(G, R)
        for v_, dove in ((-1, "lose"), (1, "gain")):
            per, quale = scendi_auto(G, R, v_, U, U2)
            print(scrivi(per, f"\n{m.strip()} ({len(G)} games): where you {dove} against your usual  [catalog: {quale or '-'}]"))
