"""L'inizio della partita: chi comincia, la mano iniziale e il mulligan (passo 2.bis, Autore, 14 ott 2026: «sappiamo
costruire la pesca iniziale delle carte e il primo mulligan con le regole reali?» e «non usiamo le carte reali: simuliamo un
mazzo da draft a 17 terre generiche, il resto carte vuote»).

Secondo il regolamento ufficiale (Regole/MagicCompRules.txt, regola 103):
  - chi comincia (103.1): nella prima partita del match a caso; nelle partite dopo sceglie chi ha perso la precedente
    (con un pari, chi aveva scelto l'ultima volta): chi sceglie lo passa il chiamante, `chi_sceglie`;
  - i mazzi si mescolano (103.3: lo fa gia' il Tavolo, col grimorio del passo 1), le vite partono da 20 (103.4);
  - la mano (103.5): ognuno pesca 7 carte. Poi a giri: dichiara prima chi comincia, poi gli altri in ordine di turno,
    e chi dichiara dopo sa cosa hanno detto quelli prima. I mulligan dichiarati si fanno tutti insieme: la mano torna nel
    grimorio, si mescola, se ne pescano 7. Chi tiene mette in fondo tante carte quanti mulligan ha fatto, nell'ordine che
    sceglie, e non dichiara piu'. Si puo' andare avanti finche' la mano sarebbe di zero carte.
    Il regolamento mette le carte in fondo subito dopo ogni mulligan; Arena fa vedere 7 carte, chiede se tenere e poi
    quali mettere in fondo. Il risultato e' lo stesso (le carte messe in fondo a un mulligan rifatto si rimescolano
    comunque) e qui si segue Arena, come il grimorio del passo 1.

Arena nel Bo1 non pesca la mano a caso (modo="arena_bo1"): pesca piu' mani e tiene quella col rapporto terre/carte piu'
vicino a quello del mazzo. Lo confermano le note di patch per il Premier Draft (era di Ikoria, fonte MTGAZone); quante mani
pesca, cosa fa a parita' e se vale anche nei mulligan non e' pubblico, e per il Quick non e' confermato (canone G9,
Note/Canone_Esperti_Gioco_FRA.md). Qui e' un'IPOTESI con i suoi parametri (campioni, anche_ai_mulligan; a parita' vince la
mano pescata prima). Misurata il 14 ott 2026 sulle mani vere dei log (Motore_Partita/misura_smoothing.py,
Misura_Smoothing_Bo1.md): nel Quick Draft il regolamento puro e' respinto e regge campioni=2 (44 partite, dato moderato);
il Premier non e' nei log. `distribuzione_terre` da' la
distribuzione esatta delle terre nella mano per ogni ipotesi: e' il metro per quella misura.

    py -I -X utf8 Motore_Partita/inizio.py --prova
"""
import os
import sys
from math import comb

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from grimorio import _chi2_p
from tavolo import Tavolo, controlla, mazzo_draft_generico

MODI = ("regolamento", "arena_bo1")


def e_terra(o):
    return "land" in o.carta.tipi


def _distanza(terre_mano, n, terre_mazzo, totale):
    """|terre_mano/n - terre_mazzo/totale|, moltiplicata per n*totale: un intero, cosi' le parita' sono esatte."""
    return abs(terre_mano * totale - n * terre_mazzo)


def _pesca_mano(t, i, n, liscia, campioni):
    """Le n carte della mano (tolte dal grimorio, ancora oggetti del grimorio: arrivano in mano solo a mano tenuta).
    liscia: l'ipotesi del Bo1, «campioni» mescolate e si tiene quella con le terre piu' vicine al mazzo."""
    gr = t.giocatori[i].grimorio
    if liscia and campioni > 1 and len(gr) >= n:
        terre, totale = sum(map(e_terra, gr.carte)), len(gr)
        migliore, dist = None, None
        for s in range(campioni):
            if s: gr.mescola()
            d = _distanza(sum(map(e_terra, gr.carte[:n])), n, terre, totale)
            if dist is None or d < dist: migliore, dist = list(gr.carte), d
        gr.carte = migliore
    return gr.pesca(n)


def inizia(t, decidi=None, fondo=None, modo="regolamento", campioni=2, anche_ai_mulligan=False,
           primo=None, chi_sceglie=None, sceglie=None, n=7):
    """La regola 103 sul tavolo t.
    decidi(i, mano, k, dette) -> True per il mulligan: i il giocatore, mano le 7 carte che vede, k i mulligan gia' fatti,
      dette le dichiarazioni gia' fatte in questo giro ({giocatore: True/False}, 103.5). Senza: si tiene sempre.
    fondo(i, mano, k) -> le k carte da mettere in fondo, nell'ordine (senza: le ultime k).
    primo: chi comincia, se e' gia' deciso. Altrimenti chi_sceglie=None e' la prima partita (a caso), oppure il giocatore
      che sceglie (103.1) e sceglie(chi_sceglie) -> chi comincia (senza: comincia lui).
    -> {"primo", "mulligan": {i: k}, "mani": {i: [oggetti in mano]}, "dichiarazioni": [(giro, i, mulligan?)]}."""
    if modo not in MODI: raise ValueError(f"modo sconosciuto: {modo}")
    bo1 = modo == "arena_bo1"
    N = len(t.giocatori)
    rng = np.random.default_rng([t.seme, 103])
    if primo is None:
        if chi_sceglie is None: primo = int(rng.integers(0, N))                  # 103.1: prima partita, a caso
        else: primo = sceglie(chi_sceglie) if sceglie else chi_sceglie            # 103.1: sceglie chi ha perso
    t.primo = primo
    ordine = [(primo + j) % N for j in range(N)]
    mani = {i: _pesca_mano(t, i, n, bo1, campioni) for i in ordine}               # 103.5
    k = {i: 0 for i in ordine}
    aperti, dichiarazioni, giro, finali = list(ordine), [], 0, {}
    while aperti:
        giro += 1
        dette = {}
        for i in aperti:                                 # chi comincia per primo, poi in ordine di turno (103.5)
            vuole = k[i] < n and bool(decidi and decidi(i, list(mani[i]), k[i], dict(dette)))
            dette[i] = vuole
            dichiarazioni.append((giro, i, vuole))
        for i in aperti:
            if dette[i]: continue                        # chi tiene: in fondo k carte, la mano e' quella (103.5)
            gr, mano = t.giocatori[i].grimorio, mani[i]
            if k[i]: mano = gr.fondo_mulligan(mano, k[i], (lambda m, kk, i=i: fondo(i, m, kk)) if fondo else None)
            finali[i] = [t._arriva(o, "grimorio", "mano", None, None, "103.5") for o in mano]
        aperti = [i for i in aperti if dette[i]]
        for i in aperti:                                 # i mulligan, tutti insieme (103.5)
            gr = t.giocatori[i].grimorio
            gr.carte.extend(mani[i]); gr.mescola()
            k[i] += 1
            mani[i] = _pesca_mano(t, i, n, bo1 and anche_ai_mulligan, campioni)
    t.mulligan = dict(k)
    return {"primo": primo, "mulligan": dict(k), "mani": finali, "dichiarazioni": dichiarazioni}


def distribuzione_terre(terre, totale, n=7, campioni=1):
    """La probabilita' esatta di avere 0..n terre nella mano. campioni=1: l'ipergeometrica (una mano a caso). campioni=m:
    la migliore di m mani (la piu' vicina al rapporto del mazzo, a parita' la prima): si ordinano i numeri di terre per
    distanza; P(la migliore cade nella classe c) = S_c^m - S_(c+1)^m, con S_c la probabilita' di una classe c o peggiore;
    dentro la classe, la prima mano che ci cade ha le terre in proporzione all'ipergeometrica."""
    p = [comb(terre, j) * comb(totale - terre, n - j) / comb(totale, n) for j in range(n + 1)]
    if campioni == 1: return p
    classi = {}
    for j in range(n + 1): classi.setdefault(_distanza(j, n, terre, totale), []).append(j)
    ordinate = [classi[d] for d in sorted(classi)]
    pc = [sum(p[j] for j in c) for c in ordinate]
    S = [sum(pc[r:]) for r in range(len(pc))] + [0.0]
    out = [0.0] * (n + 1)
    for r, c in enumerate(ordinate):
        if pc[r] == 0: continue
        pr = S[r] ** campioni - S[r + 1] ** campioni
        for j in c: out[j] = pr * p[j] / pc[r]
    return out


def confronta(conte, attese, minimo=20):
    """Chi quadro fra le mani contate (per numero di terre) e una distribuzione attesa; le code con meno di «minimo» mani
    attese si uniscono alla vicina. -> (p, le classi usate)."""
    N = sum(conte)
    oss, att = list(map(float, conte)), [a * N for a in attese]
    gruppi = [[j] for j in range(len(oss))]
    def unisci(a, b):
        oss[b] += oss[a]; att[b] += att[a]; gruppi[b] = sorted(gruppi[a] + gruppi[b])
        del oss[a], att[a], gruppi[a]
    while len(att) > 2 and att[0] < minimo: unisci(0, 1)
    while len(att) > 2 and att[-1] < minimo: unisci(len(att) - 1, len(att) - 2)
    _, p = _chi2_p(np.array(oss), np.array(att), len(att) - 1)
    return p, gruppi


# ====================================================================== le prove
def prova():
    casi = []
    def caso(nome, ok, det=""): casi.append((nome, bool(ok), det))
    TERRE, TOT, N = 17, 40, 20_000

    def tavolo(seme): return Tavolo([mazzo_draft_generico(TERRE, TOT), mazzo_draft_generico(TERRE, TOT)], seme=seme)
    def mani_tenute(modo, campioni=2, quante=N, seme0=0):
        conte = np.zeros(8, int)
        for s in range(quante):
            t = tavolo(seme0 + s)
            r = inizia(t, modo=modo, campioni=campioni)
            for i in (0, 1): conte[sum(map(e_terra, r["mani"][i]))] += 1
        return conte

    # 1. le distribuzioni: una mano a caso e' l'ipergeometrica; il Bo1 a 2 e 3 mani segue la formula esatta
    ip = distribuzione_terre(TERRE, TOT)
    caso("le probabilita' esatte sommano a 1", all(abs(sum(distribuzione_terre(TERRE, TOT, campioni=m)) - 1) < 1e-12 for m in (1, 2, 3)))
    q = N // 2
    reg = mani_tenute("regolamento", quante=q)
    p, _ = confronta(reg, ip)
    caso("regolamento: le terre nella mano come l'ipergeometrica", p > 0.001, f"{reg.sum()} mani, p = {p:.3f}")
    bo2 = mani_tenute("arena_bo1", 2, quante=q, seme0=10 ** 6)
    p2, _ = confronta(bo2, distribuzione_terre(TERRE, TOT, campioni=2))
    caso("Bo1 a 2 mani: come la formula esatta della migliore di 2", p2 > 0.001, f"p = {p2:.3f}")
    bo3 = mani_tenute("arena_bo1", 3, quante=q, seme0=2 * 10 ** 6)
    p3, _ = confronta(bo3, distribuzione_terre(TERRE, TOT, campioni=3))
    caso("Bo1 a 3 mani: come la formula esatta della migliore di 3", p3 > 0.001, f"p = {p3:.3f}")
    # 2. le prove negative: il metro distingue le ipotesi (e' quello che servira' sulle mani vere dei log)
    pn1, _ = confronta(reg, distribuzione_terre(TERRE, TOT, campioni=2))
    pn2, _ = confronta(bo2, ip)
    pn3, _ = confronta(bo2, distribuzione_terre(TERRE, TOT, campioni=3))
    caso("prova negativa: le mani del regolamento lette come Bo1 a 2 risultano rosse", pn1 < 0.001, f"p = {pn1:.2g}")
    caso("prova negativa: le mani del Bo1 a 2 lette come regolamento risultano rosse", pn2 < 0.001, f"p = {pn2:.2g}")
    caso("prova negativa: le mani del Bo1 a 2 lette come Bo1 a 3 risultano rosse", pn3 < 0.001, f"p = {pn3:.2g}")
    estreme = lambda d: sum(d[j] for j in (0, 1, 6, 7))
    caso("quanto cambia: mani con 0, 1, 6 o 7 terre", True,
         f"regolamento {100 * estreme(ip):.1f}%, Bo1 a 2 {100 * estreme(distribuzione_terre(TERRE, TOT, campioni=2)):.2f}%, "
         f"Bo1 a 3 {100 * estreme(distribuzione_terre(TERRE, TOT, campioni=3)):.3f}%")

    # 3. chi comincia (103.1)
    primi = sum(inizia(tavolo(s))["primo"] for s in range(4000))
    caso("prima partita: comincia uno dei due a caso (103.1)", abs(primi - 2000) < 4 * 1000 ** 0.5, f"G2 comincia {primi}/4000")
    caso("partita dopo: sceglie chi ha perso, e puo' scegliere di andare per primo (103.1)",
         inizia(tavolo(1), chi_sceglie=1)["primo"] == 1 and inizia(tavolo(1), chi_sceglie=1, sceglie=lambda c: 1 - c)["primo"] == 0)

    # 4. l'ordine delle dichiarazioni e i mulligan insieme (103.5)
    viste = []
    def decidi(i, mano, k, dette):
        viste.append((i, k, dict(dette)))
        return k < (2 if i == 1 else 1)
    t = tavolo(5); r = inizia(t, decidi=decidi, primo=1)
    caso("dichiara prima chi comincia, poi l'altro, che sa cosa ha detto il primo (103.5)",
         [v[0] for v in viste[:2]] == [1, 0] and viste[0][2] == {} and viste[1][2] == {1: True})
    caso("i mulligan dichiarati nello stesso giro si fanno insieme (103.5)",
         r["dichiarazioni"][:4] == [(1, 1, True), (1, 0, True), (2, 1, True), (2, 0, False)], str(r["dichiarazioni"]))
    caso("chi ha tenuto non dichiara piu' (103.5)", [d for d in r["dichiarazioni"] if d[1] == 0] == [(1, 0, True), (2, 0, False)])
    caso("G2 con 2 mulligan tiene 5 carte, G1 con 1 ne tiene 6, il grimorio ha il resto",
         len(r["mani"][1]) == 5 and len(r["mani"][0]) == 6 and len(t.giocatori[1].grimorio) == 35 and len(t.giocatori[0].grimorio) == 34)
    caso("dopo l'inizio il tavolo e' sano (ogni carta in un posto solo)", controlla(t) == [], "; ".join(controlla(t)[:2]))
    # 5. fino a zero carte, non oltre
    t = tavolo(6); r = inizia(t, decidi=lambda *a: True)
    caso("chi rifa' sempre arriva a 7 mulligan e a una mano vuota, poi non puo' piu' (103.5)",
         r["mulligan"] == {0: 7, 1: 7} and r["mani"] == {0: [], 1: []} and len(t.giocatori[0].grimorio) == 40)
    # 6. le carte in fondo, nell'ordine scelto
    t = tavolo(7); scelte = {}
    def fondo(i, mano, k):
        scelte[i] = [mano[3], mano[0]][:k]
        return scelte[i]
    r = inizia(t, decidi=lambda i, m, k, d: k < 2, fondo=fondo)
    caso("le carte del mulligan vanno in fondo nell'ordine scelto (103.5)",
         all(t.giocatori[i].grimorio.carte[-2:] == scelte[i] for i in (0, 1)))
    # 7. il seme: lo stesso inizio si rifa' uguale
    a, b = tavolo(9), tavolo(9)
    ra, rb = inizia(a, decidi=lambda i, m, k, d: k < 1, modo="arena_bo1"), inizia(b, decidi=lambda i, m, k, d: k < 1, modo="arena_bo1")
    caso("stesso seme, stesso inizio (chi comincia, mani, grimori)", ra["primo"] == rb["primo"] and a.stato() == b.stato())
    # 8. l'ipotesi nei mulligan: senza anche_ai_mulligan la mano rifatta e' a caso
    q8 = 4000
    conte_mull = {False: np.zeros(8, int), True: np.zeros(8, int)}
    for anche in (False, True):
        def decidi8(i, mano, k, dette, anche=anche):
            if k == 1: conte_mull[anche][sum(map(e_terra, mano))] += 1     # le 7 carte della mano rifatta
            return k < 1
        for s in range(q8): inizia(tavolo(3 * 10 ** 6 + s), decidi=decidi8, modo="arena_bo1", anche_ai_mulligan=anche)
    pa, _ = confronta(conte_mull[False], ip)
    pb, _ = confronta(conte_mull[True], distribuzione_terre(TERRE, TOT, campioni=2))
    pc, _ = confronta(conte_mull[False], distribuzione_terre(TERRE, TOT, campioni=2))
    caso("Bo1: la mano dopo il mulligan e' a caso, se non si dice altro", pa > 0.001, f"p = {pa:.4f}")
    caso("Bo1 con anche_ai_mulligan: anche la mano rifatta e' scelta", pb > 0.001, f"p = {pb:.4f}")
    caso("prova negativa: la mano rifatta a caso letta come scelta risulta rossa", pc < 0.001, f"p = {pc:.2g}")

    for nome, ok, det in casi:
        print(f"  {'ok   ' if ok else 'ROSSO'} {nome}" + (f"  [{det}]" if det else ""))
    print(f"{sum(ok for _, ok, _ in casi)}/{len(casi)} (mazzo da draft finto: {TERRE} terre su {TOT})")
    return 0 if all(ok for _, ok, _ in casi) else 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if "--prova" in sys.argv: sys.exit(prova())
    print(__doc__)
