"""UpgradePlan01, il profilo del giocatore per mazzo (Autore, 20 nov 2026: «risolvendo il giocatore si risolvono i profili, a quel punto sappiamo le
regole e applichiamo le meccaniche dei mazzi, basta capire chi è capace di spremere più ev», poi «Il profilo per mazzo»; il piano: Note/UpgradePlan01.md;
la misura: Note/UpgradePlan01_Profilo.md).

Dagli spot di psicologia.py (ogni turno dell'Hero col turno dell'Opponent dopo, lo stato sotto pressione o tranquillo, i comportamenti) per ogni mazzo:
  spremuto   la finestra (il tuo turno piu' il suo dopo) contro il solito del mazzo, media per stato, MENO la stessa media di tutti i tuoi mazzi:
             quanto quel mazzo, nelle tue mani, spreme piu' o meno EV dei tuoi altri mazzi in quello stato
  le linee   quanto spesso fai ogni comportamento in quello stato, contro i tuoi altri mazzi (z delle proporzioni)
  il prezzo  quanto rende il comportamento con quel mazzo (finestra con meno senza, dentro il mazzo e lo stato), grigio con poche volte
  gli indici panico (una delle tre linee del panico), freddezza (corsa / corsa + no_corsa), inganno (trappola), speranza (aspetta),
             strategia (aspetta_catena / aspetta)

La negativa: i mazzi rimescolati fra le partite (non fra i turni: i turni di una partita si somigliano); quante differenze «forti» (|z| > 2) restano.
La replica: le partite pari contro le dispari, mazzo per mazzo.

    py -I -X utf8 Companion/App/Schede/Performance/profilo_giocatore.py [--limited] [--mazzo NOME]
    py -I -X utf8 Companion/App/Schede/Performance/profilo_giocatore.py --prova
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
import psicologia as PS  # noqa: E402

MINIMO_PARTITE = 15
MINIMO_COMPO = 5
Z_FORTE = 2.0
STATI = ((True, "under pressure"), (False, "calm"))


def _m_es(v):
    n = len(v)
    if n < 2:
        return None, None
    m = sum(v) / n
    return m, math.sqrt(sum((q - m) ** 2 for q in v) / (n - 1) / n)


def z_prop(k1, n1, k2, n2):
    if n1 < 1 or n2 < 1:
        return None
    p = (k1 + k2) / (n1 + n2)
    es = math.sqrt(p * (1 - p) * (1 / n1 + 1 / n2)) if 0 < p < 1 else 0
    return None if es == 0 else (k1 / n1 - k2 / n2) / es


def indici(G):
    """Gli indici delle linee su un gruppo di spot (None dove non si possono contare)."""
    n = len(G)
    c = collections.Counter(k for s in G for k in s["compo"])
    pan = sum(1 for s in G if s["compo"] & {"tappato", "no_corsa", "chump"})
    corse = c["corsa"] + c["no_corsa"]
    return dict(panico=pan / n if n else None, freddezza=c["corsa"] / corse if corse else None, inganno=c["trappola"] / n if n else None,
                speranza=c["aspetta"] / n if n else None, strategia=c["aspetta_catena"] / c["aspetta"] if c["aspetta"] else None)


def profilo(S, mazzo):
    """Il profilo di un mazzo dagli spot S di tutti i mazzi (con la finestra): {stato: dict(n, spremuto, es, indici, linee={compo: dict(...)})}."""
    out = {}
    for stato, _nome in STATI:
        M = [s for s in S if s["pressione"] == stato and s["mazzo"] == mazzo]
        A = [s for s in S if s["pressione"] == stato and s["mazzo"] != mazzo]
        mm, em = _m_es([s["finestra"] for s in M])
        ma, ea = _m_es([s["finestra"] for s in A])
        spr = None if mm is None or ma is None else mm - ma
        es = None if spr is None else math.sqrt(em ** 2 + ea ** 2)
        linee = {}
        for k in PS.NOMI:
            km = sum(1 for s in M if k in s["compo"])
            ka = sum(1 for s in A if k in s["compo"])
            con = [s["finestra"] for s in M if k in s["compo"]]
            senza = [s["finestra"] for s in M if k not in s["compo"]]
            prezzo = (sum(con) / len(con) - sum(senza) / len(senza)) if len(con) >= MINIMO_COMPO and len(senza) >= MINIMO_COMPO else None
            linee[k] = dict(quota=km / len(M) if M else None, quota_altri=ka / len(A) if A else None, z=z_prop(km, len(M), ka, len(A)),
                            volte=km, prezzo=prezzo)
        out[stato] = dict(n=len(M), spremuto=spr, es=es, indici=indici(M) if M else {}, linee=linee)
    return out


def mazzi(S, R):
    """I mazzi con almeno MINIMO_PARTITE partite, dal piu' giocato."""
    c = collections.Counter(PS.DA.chiave_mazzo(x) for x in R)
    con_spot = {s["mazzo"] for s in S}
    return [m for m, n in c.most_common() if n >= MINIMO_PARTITE and m in con_spot]


def forti(S, lista):
    """Quante differenze forti (|z| > Z_FORTE) fra un mazzo e gli altri, su tutti i mazzi, stati e comportamenti, e su quante prove."""
    k = tot = 0
    for m in lista:
        P = profilo(S, m)
        for stato, _n in STATI:
            for v in P[stato]["linee"].values():
                if v["z"] is not None:
                    tot += 1
                    k += abs(v["z"]) > Z_FORTE
            if P[stato]["spremuto"] is not None and P[stato]["es"]:
                tot += 1
                k += abs(P[stato]["spremuto"] / P[stato]["es"]) > Z_FORTE
    return k, tot


def rimescola(S, seme):
    """La negativa: i mazzi rimescolati fra le partite (ogni partita tiene i suoi turni, prende il mazzo di un'altra)."""
    rnd = random.Random(seme)
    per = {}
    for s in S:
        per.setdefault(s["partita"], s["mazzo"])
    chiavi = list(per)
    v = [per[k] for k in chiavi]
    rnd.shuffle(v)
    nuovo = dict(zip(chiavi, v))
    return [dict(s, mazzo=nuovo[s["partita"]]) for s in S]


def replica(S, lista):
    """Le partite pari contro le dispari: per ogni mazzo, stato e indice, il valore sulle due meta'. -> [(a, b)]"""
    ordine = {p: i for i, p in enumerate(sorted({s["partita"] for s in S}))}
    A = [s for s in S if ordine[s["partita"]] % 2 == 0]
    B = [s for s in S if ordine[s["partita"]] % 2 == 1]
    out = []
    for m in lista:
        for stato, _n in STATI:
            ia = indici([s for s in A if s["mazzo"] == m and s["pressione"] == stato] or [])
            ib = indici([s for s in B if s["mazzo"] == m and s["pressione"] == stato] or [])
            for k in ("panico", "freddezza", "inganno", "speranza"):
                if ia.get(k) is not None and ib.get(k) is not None:
                    out.append((k, ia[k], ib[k]))
    return out


def pearson(xy):
    n = len(xy)
    if n < 3:
        return None
    mx = sum(a for a, _b in xy) / n
    my = sum(b for _a, b in xy) / n
    sx = math.sqrt(sum((a - mx) ** 2 for a, _b in xy))
    sy = math.sqrt(sum((b - my) ** 2 for _a, b in xy))
    return None if sx == 0 or sy == 0 else sum((a - mx) * (b - my) for a, b in xy) / sx / sy


def stampa(P, nome):
    print(f"\n=== {nome} ===")
    for stato, sn in STATI:
        q = P[stato]
        if not q["n"]:
            continue
        spr = "" if q["spremuto"] is None else f"  squeezes {q['spremuto']:+.1f} ±{q['es']:.1f} vs your other decks"
        print(f"  {sn}: {q['n']} Hero turns{spr}")
        ix = q["indici"]
        print("    " + "  ".join(f"{k} {100 * v:.0f}%" for k, v in ix.items() if v is not None))
        for k, v in q["linee"].items():
            if not v["volte"]:
                continue
            z = "" if v["z"] is None else f" z {v['z']:+.1f}"
            pr = "" if v["prezzo"] is None else f"  worth {v['prezzo']:+.1f}"
            segno = " *" if v["z"] is not None and abs(v["z"]) > Z_FORTE else ""
            print(f"    {PS.LINEE[k]:9s} {PS.NOMI[k]:52s} {100 * v['quota']:5.1f}% (others {100 * v['quota_altri']:5.1f}%){z}{segno}{pr}")


def prova():
    casi = []
    rnd = random.Random(5)
    S = []
    for p in range(400):
        mazzo = "A" if p % 2 else "B"
        for t in range(6):
            pres = t % 3 == 0
            compo = set()
            if mazzo == "A" and pres and rnd.random() < 0.5:
                compo.add("chump")
            if rnd.random() < 0.1:
                compo.add("corsa")
            fin = rnd.gauss(-4 if "chump" in compo else 0, 3) + (2 if mazzo == "B" else 0)
            S.append(dict(partita=p, mazzo=mazzo, t=t, pressione=pres, compo=compo, finestra=fin))
    P = profilo(S, "A")
    casi.append(("il mazzo A fa piu' chump sotto pressione dei suoi altri mazzi (z forte)", P[True]["linee"]["chump"]["z"] > Z_FORTE))
    casi.append(("il chump col mazzo A costa (prezzo sotto -2)", P[True]["linee"]["chump"]["prezzo"] < -2))
    casi.append(("il mazzo B spreme di piu' da tranquillo (+2 contro A)", profilo(S, "B")[False]["spremuto"] > 1))
    casi.append(("negativa: la corsa e' uguale nei due mazzi, z debole", abs(P[True]["linee"]["corsa"]["z"] or 0) < Z_FORTE))
    k_vero, tot = forti(S, ["A", "B"])
    k_finto = sum(forti(rimescola(S, s_), ["A", "B"])[0] for s_ in range(5)) / 5
    casi.append(("negativa: coi mazzi rimescolati fra le partite le differenze forti spariscono", k_vero >= 4 and k_finto < 2))
    ix = indici([dict(compo={"corsa"}), dict(compo={"no_corsa"}), dict(compo={"aspetta", "aspetta_catena"}), dict(compo={"aspetta"})])
    casi.append(("gli indici: freddezza 1 su 2, strategia 1 su 2, panico 1 su 4", ix["freddezza"] == 0.5 and ix["strategia"] == 0.5 and ix["panico"] == 0.25))
    for n_, ok in casi:
        print(("ok    " if ok else "ROSSO ") + n_)
    print(f"{sum(1 for _n, ok in casi if ok)}/{len(casi)}")
    return all(ok for _n, ok in casi)


if __name__ == "__main__":
    if "--prova" in sys.argv:
        sys.exit(0 if prova() else 1)
    tipo = "Limited" if "--limited" in sys.argv else "Constructed"
    R = [x for x in PS.DA.righe() if x["tipo"] == tipo]
    S = PS.con_finestra(R, R)
    lista = mazzi(S, R)
    if "--mazzo" in sys.argv:
        nome = sys.argv[sys.argv.index("--mazzo") + 1]
        lista = [m for m in lista if m[1] == nome]
    print(f"{tipo}: {len(S)} Hero turns, {len(lista)} decks with {MINIMO_PARTITE}+ games")
    for m in lista:
        stampa(profilo(S, m), m[1] or "(no name)")
    k_vero, tot = forti(S, lista)
    finti = [forti(rimescola(S, s_), lista)[0] for s_ in range(20)]
    print(f"\nstrong differences (|z| > {Z_FORTE}): {k_vero} of {tot}; decks shuffled between games: {sum(finti) / len(finti):.1f} "
          f"(max {max(finti)})")
    rp = replica(S, lista)
    for k in ("panico", "freddezza", "inganno", "speranza"):
        xy = [(a, b) for kk, a, b in rp if kk == k]
        r_ = pearson(xy)
        print(f"replica even vs odd games · {k}: r {r_:+.2f} on {len(xy)} deck-states" if r_ is not None else f"replica · {k}: too few")
