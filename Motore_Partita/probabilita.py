"""Il passo 8.4 del motore di partita: le probabilita' delle pescate (14 ott 2026).

Autore, 14 ott 2026: «il cercatore si e' abituato a conoscere anche le uscite in % della probabile carta che gli arrivera'
nel turno successivo?» e poi «si cominciamo a calcolare %». Il Cercatore (passo 8.2) le probabilita' le sente solo dentro le
partite di prova (rimescola le carte che non vede); qui si calcolano esatte, senza simulare:
  - il grimorio si divide in tre pezzi: le carte in cima che chi gioca conosce (uno scry lasciato sopra: 701.22a, 401.2),
    quelle in fondo che conosce (scry in fondo, mulligan: 103.5), e il mezzo, mescolato (701.24a: nessuno conosce l'ordine);
  - le pescate escono dall'alto, una alla volta (121.1, 121.2): prima la cima nota, poi il mezzo, poi il fondo noto;
  - dal mezzo, «almeno j carte del gruppo in r pescate» e' l'ipergeometrica (estrazioni senza reinserimento): esatta, coi
    coefficienti binomiali, mai con il reinserimento (la prova negativa: la binomiale da' numeri diversi e la prova li vede);
  - i gruppi: ogni nome, terra, terra che produce un colore (305.6, 605: il motore dice cosa produce), creatura, istantaneo
    o con lampo (702.8a), non terra.
Il grimorio di Autore si conosce: il mazzo vero meno le carte che si vedono nelle altre zone, con le carte in cima e in
fondo che il log gli fa vedere. Quello dell'avversario no: lo stesso conto sul mazzo modello del passo 8.3 e' una stima,
e si scrive cosi'.

    py -I -X utf8 Motore_Partita/probabilita.py --prova               le prove (conti esatti, mescolatore, log)
    py -I -X utf8 Motore_Partita/probabilita.py --calibratura         le pescate vere dei log contro le probabilita' (scrive Calibratura_Pescate.md)
    py -I -X utf8 Motore_Partita/probabilita.py --punto <partita> <turno>   la tabella al punto di scelta di quel turno
"""
import math
import os
import sys
import time
from collections import Counter
from datetime import datetime

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import carte_fra as F
import mana as M

QUI = os.path.dirname(os.path.abspath(__file__))
REPORT = os.path.join(QUI, "Calibratura_Pescate.md")


# ====================================================================== i conti
def pmf(N, g, r, j):
    """Ipergeometrica: P(esattamente j carte del gruppo in r pescate da N carte mescolate, g del gruppo)."""
    if j < 0 or j > r or j > g or r - j > N - g or r > N: return 0.0
    return math.comb(g, j) * math.comb(N - g, r - j) / math.comb(N, r)


def almeno(N, g, r, j=1):
    """P(almeno j del gruppo in r pescate dal mezzo mescolato)."""
    if j <= 0: return 1.0
    return sum(pmf(N, g, r, x) for x in range(j, min(g, r) + 1))


class Grimorio:
    """Il grimorio come lo vede chi pesca: cima nota (dall'alto), mezzo mescolato (nome -> quante), fondo noto (dall'alto
    verso il basso: il primo e' quello che si pesca per primo quando il mezzo finisce)."""

    def __init__(self, mezzo, cima=(), fondo=()):
        self.mezzo, self.cima, self.fondo = Counter(mezzo), list(cima), list(fondo)

    def __len__(self): return len(self.cima) + sum(self.mezzo.values()) + len(self.fondo)

    def prob(self, gruppo, k, j=1):
        """P(almeno j carte del gruppo, un insieme di nomi, fra le prossime k pescate). Oltre il grimorio non si pesca
        (121.4: si perde): le pescate in piu' non contano."""
        k = min(k, len(self))
        m = len(self.cima)
        presi = sum(1 for n in self.cima[:k] if n in gruppo)
        if k <= m: return 1.0 if presi >= j else 0.0
        N = sum(self.mezzo.values())
        r = min(k - m, N)
        presi += sum(1 for n in self.fondo[:k - m - r] if n in gruppo)
        g = sum(v for n, v in self.mezzo.items() if n in gruppo)
        return almeno(N, g, r, j - presi)

    def nomi(self):
        return set(self.cima) | set(self.mezzo) | set(self.fondo)


def binomiale_sbagliata(N, g, r, j=1):
    """Il conto SBAGLIATO, con il reinserimento (ogni pescata indipendente): serve solo alla prova negativa."""
    p = g / N if N else 0
    return 1 - sum(math.comb(r, x) * p ** x * (1 - p) ** (r - x) for x in range(j))


# ====================================================================== i gruppi
def _carta(nome):
    from tavolo import Carta
    t = F.tutte().get(nome)
    return Carta(0, nome, t.voce[1], 0, car=t.voce[2]) if t else None


def colori_terra(nome):
    """I colori che la terra produce secondo il motore (305.6, 605: mana.produzioni; 106.1b)."""
    c = _carta(nome)
    if c is None or "land" not in c.tipi: return set()
    out = set()
    for prod in M.produzioni(c):
        for i, tipo in enumerate(M.TIPI):
            if prod[i] and tipo in "WUBRG": out.add(tipo)
    return out


def gruppi(nomi):
    """Nome del gruppo -> insieme di nomi. I gruppi vuoti non ci sono."""
    out = {}
    for n in sorted(nomi): out[n] = {n}
    def metti(g, n): out.setdefault(g, set()).add(n)
    for n in nomi:
        c = _carta(n)
        if c is None: continue
        if "land" in c.tipi:
            metti("terra", n)
            for col in colori_terra(n): metti(f"terra che da' {col}", n)
        else:
            metti("non terra", n)
            if "creature" in c.tipi: metti("creatura", n)
            if "instant" in c.tipi or "flash" in (c.car.get("parole") or []): metti("istantaneo o lampo", n)
    return out


def tavola(gr, ks=(1, 2, 3)):
    """[(gruppo, quante nel grimorio, [P entro k pescate per k in ks])], prima i gruppi, poi i nomi."""
    tutti = list(gr.cima) + list(gr.mezzo.elements()) + list(gr.fondo)
    righe = []
    for g, ins in gruppi(gr.nomi()).items():
        righe.append((g, sum(1 for n in tutti if n in ins), [gr.prob(ins, k) for k in ks]))
    grp = [r for r in righe if r[0] not in gr.nomi()]
    nom = sorted((r for r in righe if r[0] in gr.nomi()), key=lambda r: -r[2][0])
    return grp + nom


def scrivi_tavola(gr, ks=(1, 2, 3), titolo=""):
    righe = [titolo] if titolo else []
    if gr.cima: righe.append(f"  in cima, note: {gr.cima}")
    if gr.fondo: righe.append(f"  in fondo, note: {gr.fondo}")
    righe.append(f"  {'':34} {'quante':>6} " + " ".join(f"{'entro ' + str(k):>9}" for k in ks))
    for g, n, ps in tavola(gr, ks): righe.append(f"  {g:34} {n:>6} " + " ".join(f"{p:9.1%}" for p in ps))
    return "\n".join(righe)


# ====================================================================== dal log
def grimorio_dal_log(st, seat, mazzo):
    """Il grimorio di chi siede a seat come lo vede lui nello stato st del log: il mazzo vero meno le sue carte nelle
    altre zone (la mano, il campo, il cimitero, l'esilio, la pila: le vede), con le carte del grimorio che il log gli fa
    vedere al loro posto (posto 0 = la cima, 401.2). -> Grimorio, o None se il mazzo non torna col log."""
    import confronto_log as CL
    viste = Counter()
    for tipo in ("ZoneType_Hand", "ZoneType_Battlefield", "ZoneType_Graveyard", "ZoneType_Exile", "ZoneType_Stack"):
        for o in CL.in_zone(st, tipo):
            if o.get("ownerSeatId") != seat or o.get("type") != "GameObjectType_Card" or o.get("isCopy"): continue
            n = CL._nome(o)
            if n: viste[n] += 1
    resto = Counter(mazzo) - viste
    z = st.zona("ZoneType_Library", seat) or {}
    ids = z.get("objectInstanceIds", [])
    if sum(resto.values()) != len(ids) or viste - Counter(mazzo): return None
    noti = [(j, CL._nome(st.obj[i])) for j, i in enumerate(ids) if i in st.obj and st.obj[i].get("grpId")]
    cima, fondo = [], []
    for j, n in noti:
        if j == len(cima): cima.append(n)
    for j, n in reversed(noti):
        if j == len(ids) - 1 - len(fondo) and j >= len(cima): fondo.insert(0, n)
    mezzo = resto - Counter(cima) - Counter(fondo)
    if sum(mezzo.values()) + len(cima) + len(fondo) != len(ids): return None
    return Grimorio(mezzo, cima, fondo)


def pescate_vere():
    """Ogni pescata di Autore nelle partite di Quick Draft FRA (ZoneTransfer «Draw»): (grimorio prima, carta pescata)."""
    import confronto_log as CL
    import riscontro as R
    import simula as S
    mazzi = {g: m for m in S.mazzi_veri() for g in (m["partite"] if isinstance(m["partite"], list) else [])}
    out, saltate = [], 0
    for gid, path in R.partite():
        if gid not in mazzi: continue
        seq = list(R.messaggi(path))
        io = CL.mio_posto(seq)
        for prima, dopo, ann in seq:
            for a in ann:
                if a["type"][0] != "AnnotationType_ZoneTransfer" or R.dettagli(a).get("category") != "Draw": continue
                o = dopo.obj.get((a.get("affectedIds") or [None])[0]) or {}
                if o.get("ownerSeatId") != io: continue
                if any(x["type"][0] == "AnnotationType_ZoneTransfer" and R.dettagli(x).get("category") == "Draw" and x is not a
                       and ((dopo.obj.get((x.get("affectedIds") or [None])[0]) or {}).get("ownerSeatId") == io) for x in ann):
                    saltate += 1; continue                                                         # piu' pescate nello stesso messaggio:
                gr = grimorio_dal_log(prima, io, mazzi[gid]["mazzo"])                               # lo stato fra l'una e l'altra non c'e'
                if gr is None: saltate += 1; continue
                out.append((gid, gr, CL._nome(o)))
    return out, saltate


def calibratura(scrivi=True):
    """Le probabilita' di pescare una terra contro le terre pescate davvero (fasce), e la carta pescata: il conto esatto
    contro il mazzo intero senza togliere le carte viste (quello che si direbbe a memoria). Log-verosimiglianza media: piu'
    alta e' meglio."""
    t0 = time.time()
    pesc, saltate = pescate_vere()
    fasce = [[0, 0, 0.0] for _ in range(10)]                                                       # [pescate, terre, somma p]
    brier, ll_vero, ll_ingenuo, certe, certe_ok = 0.0, 0.0, 0.0, 0, 0
    import simula as S
    mazzi = {g: m["mazzo"] for m in S.mazzi_veri() for g in (m["partite"] if isinstance(m["partite"], list) else [])}
    for gid, gr, nome in pesc:
        terre = gruppi(gr.nomi()).get("terra", set())
        p = gr.prob(terre, 1)
        uscita = nome in terre
        f = fasce[min(int(p * 10), 9)]
        f[0] += 1; f[1] += uscita; f[2] += p
        brier += (p - uscita) ** 2
        pn = gr.prob({nome}, 1)
        ll_vero += math.log(max(pn, 1e-12))
        intero = Counter(mazzi[gid])
        ll_ingenuo += math.log(max(intero[nome] / sum(intero.values()), 1e-12))
        if gr.cima:
            certe += 1; certe_ok += gr.cima[0] == nome
    n = len(pesc)
    righe = ["# La calibratura delle pescate (passo 8.4)\n",
             f"Scritto il {datetime.now().strftime('%Y-%m-%d %H:%M')} da `py -I -X utf8 Motore_Partita/probabilita.py --calibratura`. Ogni pescata "
             f"di Autore nelle partite di Quick Draft FRA: il grimorio come lo vedeva lui un attimo prima (il mazzo vero meno le "
             f"carte viste, la cima nota dopo uno scry), la probabilita' calcolata, la carta uscita davvero.\n",
             f"- pescate: **{n}** (saltate {saltate}: piu' pescate nello stesso messaggio del log, o il mazzo che non torna)",
             f"- con la carta in cima nota (scry o surveil lasciati sopra): {certe}, e la carta pescata e' quella in {certe_ok}",
             f"- terra alla prossima pescata, punteggio di Brier: {brier / max(n, 1):.4f} (0 perfetto; dire sempre 50% darebbe 0,25)",
             f"- la carta esatta: log-verosimiglianza media {ll_vero / max(n, 1):.3f} col grimorio vero, {ll_ingenuo / max(n, 1):.3f} col mazzo "
             f"intero (senza togliere le carte viste); piu' alta e' meglio\n",
             "## Terra alla prossima pescata: detto contro uscito\n",
             "| fascia | pescate | detto (media) | uscite terre |", "| :--- | ---: | ---: | ---: |"]
    for k, (m_, t_, s_) in enumerate(fasce):
        if m_: righe.append(f"| {k * 10}-{k * 10 + 10}% | {m_} | {s_ / m_:.1%} | {t_ / m_:.1%} |")
    if scrivi:
        with open(REPORT, "w", encoding="utf-8") as h:
            h.write("---\ntipo: misura\ncreato: " + datetime.now().strftime("%Y-%m-%dT%H:%M") + "\n---\n\n" + "\n".join(righe) + "\n")
    print("\n".join(righe))
    return {"n": n, "fasce": fasce, "brier": brier / max(n, 1), "ll_vero": ll_vero / max(n, 1), "ll_ingenuo": ll_ingenuo / max(n, 1),
            "certe": certe, "certe_ok": certe_ok, "secondi": time.time() - t0}


# ====================================================================== le prove
def _mescolate(nomi, gruppo, k, j, N_mescolate, seme, cima=(), fondo=()):
    """Il conto fatto mescolando davvero col mescolatore del passo 1 (Fisher-Yates su PCG64)."""
    from grimorio import Grimorio as G
    ok = 0
    for s in range(N_mescolate):
        g = G(list(nomi), seme=seme * 1_000_003 + s)
        pesc = list(cima) + list(g.carte) + list(fondo)
        ok += sum(1 for n in pesc[:k] if n in gruppo) >= j
    return ok / N_mescolate


def prova():
    casi = []
    def caso(nome, ok, det=""): casi.append((nome, bool(ok), det))
    t0 = time.time()
    # 1. l'ipergeometrica contro il conteggio di tutti i casi (piccoli mazzi, tutte le combinazioni)
    from itertools import combinations
    err = 0.0
    for N, g, r in [(5, 2, 2), (6, 3, 3), (7, 2, 4), (8, 4, 3), (9, 1, 5)]:
        carte = ["x"] * g + ["o"] * (N - g)
        tutte = list(combinations(range(N), r))
        for j in range(0, r + 1):
            esatto = sum(1 for c in tutte if sum(carte[i] == "x" for i in c) >= j) / len(tutte)
            err = max(err, abs(esatto - almeno(N, g, r, j)))
    caso("ipergeometrica uguale al conteggio di tutte le combinazioni (5 mazzi piccoli, ogni j)", err < 1e-12, f"scarto massimo {err:.1e}")
    # 2. contro il mescolatore vero (passo 1), su un grimorio da Limited
    nomi = ["Island"] * 9 + ["Mountain"] * 8 + ["Last Gasp"] * 1 + ["Keeper of the Quiet Hour"] * 2 + ["X"] * 10
    terre = {"Island", "Mountain"}
    peggio = 0.0
    for k, j, grp in [(1, 1, terre), (3, 2, terre), (2, 1, {"Last Gasp"}), (5, 1, {"Keeper of the Quiet Hour"})]:
        atteso = Grimorio(Counter(nomi)).prob(grp, k, j)
        visto = _mescolate(nomi, grp, k, j, 40000, 7 + k)
        sigma = math.sqrt(atteso * (1 - atteso) / 40000)
        peggio = max(peggio, abs(visto - atteso) / max(sigma, 1e-9))
    caso("il conto esatto torna col mescolatore vero (40.000 mescolate per caso, scarto entro 4 deviazioni)", peggio < 4, f"scarto massimo {peggio:.2f} deviazioni")
    # 3. la prova negativa: la binomiale (con reinserimento) e' un altro numero, e il confronto col mescolatore lo vede
    att_b = binomiale_sbagliata(30, 1, 10, 1)                                                   # una copia sola, 10 pescate: 28,7% contro 33,3%
    visto = _mescolate(nomi, {"Last Gasp"}, 10, 1, 40000, 99)
    z = abs(visto - att_b) / math.sqrt(att_b * (1 - att_b) / 40000)
    z_giusto = abs(visto - almeno(30, 1, 10, 1)) / math.sqrt(1 / 3 * 2 / 3 / 40000)
    caso("prova negativa: il conto con il reinserimento (binomiale) e' rosso contro il mescolatore, quello giusto no",
         z > 6 and z_giusto < 4, f"binomiale a {z:.1f} deviazioni, ipergeometrica a {z_giusto:.1f}")
    # 4. la cima e il fondo noti
    gr = Grimorio(Counter(["Island"] * 5 + ["Mountain"] * 5), cima=["Last Gasp"], fondo=["Mountain"])
    a1 = gr.prob({"Last Gasp"}, 1) == 1.0 and gr.prob({"Island"}, 1) == 0.0
    a2 = abs(gr.prob({"Island"}, 2) - 0.5) < 1e-12 and gr.prob({"Mountain"}, 12, 6) == 1.0
    visto = _mescolate(["Island"] * 5 + ["Mountain"] * 5, {"Island"}, 3, 1, 40000, 5, cima=["Last Gasp"], fondo=["Mountain"])
    a3 = abs(visto - gr.prob({"Island"}, 3)) < 4 * math.sqrt(0.25 / 40000)
    caso("cima nota (si pesca per prima), fondo noto (per ultimo), il mezzo mescolato: tornano col mescolatore", a1 and a2 and a3,
         f"P(Island entro 3) {gr.prob({'Island'}, 3):.4f}, mescolate {visto:.4f}")
    # 5. i gruppi: le terre per colore dal motore
    g_ = gruppi({"Island", "Mountain", "Last Gasp", "Keeper of the Quiet Hour"})
    caso("gruppi: terre e colori letti dal motore (Island da' U, Mountain da' R), creatura, non terra",
         g_.get("terra che da' U") == {"Island"} and g_.get("terra che da' R") == {"Mountain"} and "Last Gasp" in g_["non terra"]
         and g_.get("creatura") == {"Keeper of the Quiet Hour"}, str({k: sorted(v) for k, v in g_.items() if len(v) > 1}))
    # 6. il log: ogni pescata vera di Autore, col grimorio come lo vedeva lui
    cal = calibratura(scrivi=False)
    caso("log: le pescate di Autore nelle partite FRA lette col grimorio vero (il mazzo torna col log)", cal["n"] > 300, f"{cal['n']} pescate")
    caso("log: quando la carta in cima e' nota, la pescata e' sempre quella", cal["certe"] > 0 and cal["certe"] == cal["certe_ok"],
         f"{cal['certe_ok']}/{cal['certe']}")
    fasce_ok = all(abs(t_ / m_ - s_ / m_) < 3 * math.sqrt(max(s_ / m_ * (1 - s_ / m_), 0.02) / m_) for m_, t_, s_ in cal["fasce"] if m_ >= 20)
    caso("log: terra alla prossima pescata, detto contro uscito, entro 3 deviazioni in ogni fascia con almeno 20 pescate", fasce_ok,
         " ".join(f"{s_ / m_:.0%}->{t_ / m_:.0%}({m_})" for m_, t_, s_ in cal["fasce"] if m_))
    caso("log: il grimorio vero spiega le carte pescate meglio del mazzo intero (log-verosimiglianza piu' alta)",
         cal["ll_vero"] > cal["ll_ingenuo"], f"{cal['ll_vero']:.3f} contro {cal['ll_ingenuo']:.3f}")
    ok = sum(1 for _, k, _ in casi if k)
    for nome, k, det in casi: print(("OK   " if k else "ROSSO"), nome, ("  -- " + det) if det else "")
    print(f"\n{ok}/{len(casi)} in {time.time() - t0:.0f} s")
    return ok == len(casi)


def al_punto(gid, turno):
    """La tabella di Autore (e la stima per l'avversario) al primo punto di scelta di quel turno."""
    import confronto_log as CL
    import riscontro as R
    import simula as S
    mazzi = {g: m for m in S.mazzi_veri() for g in (m["partite"] if isinstance(m["partite"], list) else [])}
    path = dict(R.partite())[gid]
    seq = list(R.messaggi(path))
    io = CL.mio_posto(seq)
    for prima, dopo, ann in seq:
        if dopo.turno.get("turnNumber") == turno and dopo.turno.get("phase") == "Phase_Main1":
            gr = grimorio_dal_log(dopo, io, mazzi[gid]["mazzo"])
            print(scrivi_tavola(gr, titolo=f"{gid}, turno {turno}, prima fase principale: il grimorio di Autore ({len(gr)} carte)"))
            modello, _ = CL.mazzo_modello(seq, 3 - io, gid)
            avv = Counter(modello) - CL._pubbliche(dopo, 3 - io)
            print(scrivi_tavola(Grimorio(avv), titolo="l'avversario, STIMA sul mazzo modello (mano e grimorio insieme: non si sa cosa ha in mano)"))
            return
    print("turno non trovato")


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[:1] == ["--prova"]: sys.exit(0 if prova() else 1)
    elif a[:1] == ["--calibratura"]: calibratura()
    elif a[:1] == ["--punto"]: al_punto(a[1], int(a[2]))
    else: print(__doc__)
