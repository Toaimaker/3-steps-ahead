"""Il primo livello della spremuta: le occasioni della partita, separate dal gioco (sessione Magic 24, 21 nov 2026).

Autore, 21 nov 2026: «la partita che determina come il mazzo sarà mescolato, le mani di partenza e le pescate crea le situazioni da cui spremere i
punti … la partita guida le occasioni», poi «noi dobbiamo risolvere 3 cose: la partita, i mazzi e il giocatore», poi «si costruiscilo». La mappa:
Note/Gerarchie_Valore.md 1.ter, Note/UpgradePlan01.md «I tre livelli della spremuta».

La partita si divide, coi punti che si conservano (le spine di spine.py, dove le pescate sono foglie «partita»):
    fine (100 o 0) = mano + pescate dell'Hero + pescate dell'Opponent + gioco dell'Hero + gioco dell'Opponent + ritmo + fine_partita
  mano       la P della mano tenuta (la P di partenza della spina del tempo);
  pescate    i punti di P che ogni pescata ha mosso (le righe «You drew X»; quelle dell'Opponent sono carte coperte e muovono solo il numero di carte);
  gioco      le scelte (lanciare, giocare la terra, attaccare, bloccare, i poteri) con le loro conseguenze, piu' la posta del turno (la P che chi
             e' di turno perde se passa senza fare niente: la riprende col gioco; dal 21 nov 2026 e' del giocatore di turno, prima stava nel ritmo);
  ritmo      le fasi senza scelte e gli arrotondamenti; fine_partita: dall'ultima foto al risultato (il colpo finale o la concessione).

Le occasioni sono la parte che nessuno sceglie, contro il solito del mazzo (ogni mazzo contro se stesso, DA.chiave_mazzo; sotto MINIMO_MAZZO partite il
solito del tipo):
    occasioni = (mano - mano media del mazzo) + (pescate dell'Hero - pescate attese: quante pescate x la pescata media del mazzo)
La mano tenuta e' anche una scelta (il mulligan): qui conta come occasione (grado C, dichiarato).

La misura (--misura): (1) le occasioni predicono il risultato (AUC); (2) la prova negativa: le pescate rimescolate fra le partite dello stesso mazzo non
predicono niente (AUC vicina a 0,5); (3) l'indipendenza: quanto le occasioni si muovono col gioco dell'Hero (Spearman). Se il gioco sale con le
occasioni, una parte della fortuna sta ancora dentro i punti delle scelte: e' quello che il secondo livello (il potenziale del mazzo per spot) deve
togliere.

    py -I -X utf8 Companion/App/Schede/Performance/occasioni.py --misura [--limited]
    py -I -X utf8 Companion/App/Schede/Performance/occasioni.py --prova
"""
import os
import sys
import json
import random
import collections

_casa = os.path.dirname(os.path.abspath(__file__))
while not os.path.isfile(os.path.join(_casa, "percorsi.py")):
    _casa = os.path.dirname(_casa)
if _casa not in sys.path:
    sys.path.insert(0, _casa)
import percorsi  # noqa: E402,F401
import dati_analizzatore as DA  # noqa: E402
import spine as SP  # noqa: E402

QUI = os.path.dirname(os.path.abspath(__file__))


def componenti(x, passi=None):
    """-> dict(mazzo, vinta, mano, pescate_io, n_pescate_io, pescate_suo, gioco_io, gioco_suo, ritmo, fine) o None."""
    passi = passi if passi is not None else DA.azioni_partita(x)
    if not passi:
        return None
    s = SP.spine_partita(x, passi)
    if s is None:
        return None
    acc = collections.Counter()
    for k, v in s["giocatore"].items():
        chi, _st, _lin, ultima = k
        if chi == "partita":
            acc["pescate_io" if ultima == "pescata Hero" else "pescate_suo"] += v
        elif chi == "Hero":
            acc["gioco_io"] += v
        elif chi == "Opponent":
            acc["gioco_suo"] += v
        elif ultima == "la fine":
            acc["fine_partita"] += v
        else:
            acc["ritmo"] += v
    n_p = sum(1 for p_ in passi for _m, tx in (p_[4] or []) if tx.startswith("You drew "))
    return dict(mazzo=DA.chiave_mazzo(x), vinta=bool(x.get("vinta")), mano=s["inizio"], n_pescate_io=n_p, fine=s["fine"],
                **{k: acc.get(k, 0.0) for k in ("pescate_io", "pescate_suo", "gioco_io", "gioco_suo", "ritmo", "fine_partita")})


def con_occasioni(C, minimo=None):
    """Aggiunge a ogni partita «occasioni» contro il solito del suo mazzo (lascia-una-fuori: la partita non entra nel suo solito)."""
    minimo = minimo or getattr(DA, "MINIMO_MAZZO", 10)
    per = collections.defaultdict(list)
    for c in C:
        per[c["mazzo"]].append(c)
    tot_m = sum(c["mano"] for c in C); tot_p = sum(c["pescate_io"] for c in C); tot_n = sum(c["n_pescate_io"] for c in C)
    for c in C:
        g = per[c["mazzo"]]
        if len(g) - 1 >= minimo:
            sm = sum(z["mano"] for z in g) - c["mano"]; sp = sum(z["pescate_io"] for z in g) - c["pescate_io"]
            sn = sum(z["n_pescate_io"] for z in g) - c["n_pescate_io"]; n = len(g) - 1
        else:
            sm, sp, sn, n = tot_m - c["mano"], tot_p - c["pescate_io"], tot_n - c["n_pescate_io"], len(C) - 1
        mano_media = sm / max(n, 1)
        per_pescata = sp / max(sn, 1)
        c["mano_rel"] = c["mano"] - mano_media
        c["pescate_rel"] = c["pescate_io"] - c["n_pescate_io"] * per_pescata
        c["occasioni"] = c["mano_rel"] + c["pescate_rel"]
    return C


def auc(punti, y):
    """Area sotto la curva ROC (Mann-Whitney), con i pari a meta'."""
    pos = [p for p, v in zip(punti, y) if v]; neg = [p for p, v in zip(punti, y) if not v]
    if not pos or not neg:
        return None
    tutti = sorted([(p, 1) for p in pos] + [(p, 0) for p in neg])
    rango, i = {}, 0
    somma = 0.0
    while i < len(tutti):
        j = i
        while j < len(tutti) and tutti[j][0] == tutti[i][0]:
            j += 1
        r = (i + j - 1) / 2 + 1
        somma += r * sum(1 for k in range(i, j) if tutti[k][1])
        i = j
    return (somma - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg))


def misura(limited=False, log=print, giri=200):
    tipo = "Limited" if limited else "Constructed"
    r = [x for x in DA.righe() if x.get("seat") in (1, 2) and x.get("tipo") == tipo]
    C = []
    for i, x in enumerate(r):
        c = componenti(x)
        if c:
            C.append(c)
        if i % 100 == 0:
            log(f"  {i}/{len(r)}")
    con_occasioni(C)
    y = [c["vinta"] for c in C]
    out = dict(tipo=tipo, partite=len(C))
    for k in ("occasioni", "mano_rel", "pescate_rel", "gioco_io", "gioco_suo", "ritmo", "fine_partita"):
        out["auc_" + k] = round(auc([c[k] for c in C], y), 3)
    # la prova negativa: le pescate (il loro valore per pescata) rimescolate fra le partite dello stesso mazzo, la mano fra le stesse partite
    rng = random.Random(7)
    neg = []
    per = collections.defaultdict(list)
    for i, c in enumerate(C):
        per[c["mazzo"]].append(i)
    for _ in range(giri):
        occ = [0.0] * len(C)
        for idx in per.values():
            perm = idx[:]
            rng.shuffle(perm)
            for a, b in zip(idx, perm):
                occ[a] = C[b]["occasioni"]
        neg.append(auc(occ, y))
    neg.sort()
    out["auc_negativa"] = [round(neg[len(neg) // 2], 3), round(neg[int(0.95 * len(neg))], 3)]
    out["spearman_occasioni_gioco"] = round(SP._spearman([c["occasioni"] for c in C], [c["gioco_io"] for c in C]), 3)
    out["spearman_occasioni_gioco_suo"] = round(SP._spearman([c["occasioni"] for c in C], [c["gioco_suo"] for c in C]), 3)
    out["medie"] = {k: round(sum(c[k] for c in C) / max(len(C), 1), 2) for k in ("mano", "pescate_io", "pescate_suo", "gioco_io", "gioco_suo", "ritmo",
                                                                          "fine_partita")}
    for nome, f in (("vinte", True), ("perse", False)):
        g = [c for c in C if c["vinta"] == f]
        out["medie_" + nome] = {k: round(sum(c[k] for c in g) / max(len(g), 1), 2) for k in ("occasioni", "mano_rel", "pescate_rel", "gioco_io",
                                                                                                 "gioco_suo", "ritmo")}
    # quanto spiegano: la quota delle vinte fra le partite con le occasioni migliori e peggiori (terzili)
    o = sorted(C, key=lambda c: c["occasioni"])
    t = len(o) // 3
    out["terzili_win_rate"] = [round(100 * sum(c["vinta"] for c in g) / max(len(g), 1), 1) for g in (o[:t], o[t:2 * t], o[2 * t:])]
    with open(os.path.join(QUI, f"occasioni_{'limited' if limited else 'costruito'}.json"), "w", encoding="utf8") as fh:
        json.dump(out, fh, indent=1, ensure_ascii=False)
    log(json.dumps(out, ensure_ascii=False))
    return out


def prova():
    ok, tot = 0, 0

    def chk(nome, c_):
        nonlocal ok, tot
        tot += 1
        ok += bool(c_)
        print(("  ok  " if c_ else "  ROSSO ") + nome)
    chk("AUC: separazione perfetta 1, al contrario 0", auc([3, 4], [False, True]) == 1.0 and auc([4, 3], [False, True]) == 0.0)
    chk("negativa: AUC con un punteggio costante 0,5", auc([1, 1, 1, 1], [True, False, True, False]) == 0.5)
    C = [dict(mazzo="A", mano=50.0 + i, pescate_io=2.0 * i, n_pescate_io=i, vinta=i % 2 == 0) for i in range(12)]
    con_occasioni(C, minimo=5)
    chk("lascia-una-fuori: le mani relative di un mazzo sommano zero", abs(sum(c["mano_rel"] for c in C)) < 1e-6)
    chk("pescate tutte da 2 punti l'una: le pescate relative sono zero", all(abs(c["pescate_rel"]) < 1e-9 for c in C))
    C2 = [dict(mazzo="B", mano=50.0, pescate_io=0.0, n_pescate_io=3, vinta=True) for _ in range(11)] + \
         [dict(mazzo="B", mano=50.0, pescate_io=33.0, n_pescate_io=3, vinta=True)]
    con_occasioni(C2, minimo=5)
    chk("una partita con pescate fortunate ha occasioni positive, le altre negative", C2[-1]["occasioni"] > 30 and C2[0]["occasioni"] < 0)
    print(f"  {ok}/{tot}")
    return ok == tot


if __name__ == "__main__":
    if "--prova" in sys.argv:
        sys.exit(0 if prova() else 1)
    if "--misura" in sys.argv:
        misura(limited="--limited" in sys.argv)
