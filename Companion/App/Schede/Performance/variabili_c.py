"""Le variabili C del censimento (13 nov 2026, Note/HANDOFF_Censimento_Performance.md; Autore: «a tutto quel che è rimasto»):

    C2  la mano senza un colore del mazzo (le terre delle 7 carte non lo danno) e il colore che manca in campo a fine tuo turno 3
    C3  le rimozioni: nella mano iniziale (0, 1, 2+), nel mazzo ogni 60 carte (0-4, 5-8, 9+), la prima lanciata (entro il tuo turno 3, 5, dopo, mai)
    C4  pescata contro non pescata, carta per carta (l'IWD personale): il win rate delle partite in cui la carta ti e' passata per la mano meno quello delle
        partite in cui era nel mazzo e non l'hai vista (una riga di Cards)
    C6  il tilt misurato: dopo una vittoria o una sconfitta, e quante sconfitte di fila prima della partita
    C7  le carte in mano a fine tuo turno 3, 5, 7 (tue e sue)
    C9  le terre nel mazzo

Le rimozioni con le regole delle rimozioni vere di Companion/Comune/rimozioni.py (VERA), copiate qui: quel modulo legge un file di Scryfall che l'app
pubblica non ha, e le due app devono dire le stesse cose. Il testo delle carte e' quello del database dell'app (dati_analizzatore._carta).
"""
import os, sys
_casa = os.path.dirname(os.path.abspath(__file__))
while not os.path.isfile(os.path.join(_casa, "percorsi.py")):
    _casa = os.path.dirname(_casa)
if _casa not in sys.path:
    sys.path.insert(0, _casa)
import percorsi  # noqa: E402,F401
import collections  # noqa: E402
import re  # noqa: E402

VERA = [
    r"destroy (?:up to one )?target (?:[\w-]+ )*?(?:creature|permanent)(?!(?: or planeswalker)? you control)",
    r"exile (?:up to one )?target (?:[\w-]+ )*?(?:creature|permanent)(?!(?: or planeswalker)? you control)",
    r"deals? (?:\d+|x|that much|twice that much) damage to (?:any target|(?:up to one )?target (?:[\w-]+ )*?creature)",
    r"deals? damage equal to (?:its|that creature's|their) power to (?:up to one |another )?target (?:[\w-]+ )*?creature",
    r"fights? (?:up to one |another )?target",
    r"target creature (?:an opponent controls )?gets? -\d+/-[1-9]\d*",
    r"(?:enchanted creature|it) (?:loses all abilities and )?(?:doesn't untap|can't attack or block|can't block)",
    r"target (?:[\w-]+ )*?(?:creature|permanent)[^.]*?puts? it on (?:their choice of )?the top or bottom of (?:their|its owner's) library",
    r"base power and toughness 0/0",
    r"target (?:[\w-]+ )*?(?:creature|permanent)\. its owner may put it on (?:the )?top of their library",
    r"(?:target|each) opponent sacrifices? a creature",
    r"(?:destroy|exile) all (?:other )?creatures",
    r"all (?:other )?creatures get -\d+/-\d+",
]
_RIM = {}
BASI = {"Plains": "W", "Island": "U", "Swamp": "B", "Mountain": "R", "Forest": "G"}
ORDINE = dict(c2_mano=("Yes", "No"), c2_t3=("Yes", "No"), rim_mano=("0", "1", "2+"), rim_mazzo=("0-4", "5-8", "9+"),
              rim_prima=("By your turn 3", "By your turn 5", "Later", "Never"), dopo=("After a win", "After a loss", "First of the session"),
              serie_prima=("0", "1", "2", "3+"), **{f"mano_io{n}": ("0", "1-2", "3+") for n in (3, 5, 7)}, **{f"mano_lui{n}": ("0", "1-2", "3+") for n in (3, 5, 7)})
NOMI = dict(c2_mano="Your opening hand · a deck color missing from its lands", c2_t3="A deck color missing on your battlefield at the end of your turn 3",
            rim_mano="Removal in your opening hand", rim_mazzo="Removal in your deck · per 60 cards", rim_prima="Your first removal cast",
            dopo="The game before", serie_prima="Losses in a row before this game", terre_mazzo="Lands in your deck",
            **{f"mano_io{n}": f"Cards in your hand at the end of your turn {n}" for n in (3, 5, 7)},
            **{f"mano_lui{n}": f"Cards in the opponent's hand at the end of your turn {n}" for n in (3, 5, 7)})


def rimozione(nome):
    """La carta e' una rimozione vera (le regole VERA sul testo)? Ricordata per nome."""
    if nome not in _RIM:
        t = (DA._carta(nome or "") or {}).get("testo") or ""
        _RIM[nome] = bool(t) and any(re.search(rx, t.lower()) for rx in VERA)
    return _RIM[nome]


def _colori_terra(nome):
    c = DA._carta(nome or "") or {}
    return set(BASI.get(nome) or (c.get("colori") or "")) - {"C"}


def _colori_mazzo(lista):
    out = set()
    for n in lista or {}:
        if not DA.e_terra(n):
            out |= set((DA._carta(n) or {}).get("colori") or "") & set("WUBRG")
    return out


def campi(p, r, lista, tenuta):
    """I campi C2, C3, C7, C9 di una partita (la riga dell'analizzatore li aggiunge)."""
    out = {}
    col = _colori_mazzo(lista)
    if tenuta and col:
        terre_c = set().union(*[_colori_terra(n) for n in tenuta if DA.e_terra(n)] or [set()])
        out["c2_mano"] = "Yes" if col - terre_c else "No"
    if tenuta is not None:
        k = sum(q for n, q in tenuta.items() if not DA.e_terra(n) and rimozione(n))
        out["rim_mano"] = "0" if k == 0 else "1" if k == 1 else "2+"
    if lista:
        k = sum(q for n, q in lista.items() if not DA.e_terra(n) and rimozione(n))
        k60 = k * 60 / max(1, sum(lista.values()))       # ogni 60 carte: con le fasce di un mazzo da 40 ogni mazzo costruito era «6+» (13 nov 2026)
        out["rim_mazzo"] = "0-4" if k60 < 4.5 else "5-8" if k60 < 8.5 else "9+"
        out["terre_mazzo"] = str(sum(q for n, q in lista.items() if DA.e_terra(n)))
    d = DA._MANA.get(r.get("partita")) or {}
    seat, inizia = p.get("seat"), r.get("inizia")
    if seat in (1, 2) and inizia is not None and d:
        a, b = seat - 1, 2 - seat
        mio_t = lambda n: 2 * n - 1 if inizia else 2 * n
        fine = {m[1]: m[3] for m in d.get("momenti") or [] if m[0] == "fine" and isinstance(m[3], dict)}
        f3 = fine.get(mio_t(3))
        if f3 and col:
            terre_c = set().union(*[_colori_terra(DA.nome_grp(c[0]) or "") for c in (f3.get("c") or [[], []])[a]
                                    if DA.e_terra(DA.nome_grp(c[0]) or "")] or [set()])
            out["c2_t3"] = "Yes" if col - terre_c else "No"
        for n in (3, 5, 7):
            fn = fine.get(mio_t(n))
            if fn:
                fasce = lambda k: "0" if k == 0 else "1-2" if k <= 2 else "3+"
                out[f"mano_io{n}"] = fasce(len((fn.get("m") or [[], []])[a]))
                out[f"mano_lui{n}"] = fasce((fn.get("n") or [0, 0])[b])
        prima_t = None
        for t, s_, cosa, g, _tp in d.get("azioni") or []:
            if cosa == "magia" and s_ == seat and g not in DA.SENZA_FACCIA and rimozione(DA.nome_grp(g) or ""):
                prima_t = t
                break
        if d.get("azioni"):
            out["rim_prima"] = ("Never" if prima_t is None else "By your turn 3" if prima_t <= mio_t(3) else "By your turn 5" if prima_t <= mio_t(5)
                                else "Later")
    return out


def serie(righe):
    """C6: per ogni partita, la partita prima del suo tipo (Constructed o Limited) nella stessa sessione e le sconfitte di fila prima di questa."""
    for tipo in ("Constructed", "Limited"):
        prima, di_fila = None, 0
        for x in sorted((x for x in righe if x["tipo"] == tipo), key=lambda x: x["quando"]):
            nuova = x.get("n_sessione") == 1 or prima is None
            x["dopo"] = "First of the session" if nuova else ("After a win" if prima["vinta"] else "After a loss")
            if nuova:
                di_fila = 0
            x["serie_prima"] = "3+" if di_fila >= 3 else str(di_fila)
            di_fila = 0 if x["vinta"] else di_fila + 1
            prima = x
    return righe


def serie_piu_lunghe(r):
    """La serie di sconfitte e di vittorie piu' lunghe nelle partite r (in ordine di tempo)."""
    piu = {True: 0, False: 0}
    ora, ultima = 0, None
    for x in sorted(r, key=lambda x: x["quando"]):
        ora = ora + 1 if x["vinta"] == ultima else 1
        ultima = x["vinta"]
        piu[ultima] = max(piu[ultima], ora)
    return piu[True], piu[False]


def iwd(r, quante=40, minimo=15):
    """C4, l'IWD personale: per ogni carta non terra del mazzo, il win rate delle partite in cui ti e' passata per la mano (tenuta o pescata) meno quello
    delle partite in cui era nel mazzo e non l'hai vista; da `minimo` partite fra tutte e due (sotto, grigio: si tengono ma in fondo). -> righe di Cards."""
    dentro, vista = collections.Counter(), collections.Counter()
    v_dentro, v_vista = collections.Counter(), collections.Counter()
    for x in r:
        if not x.get("deck") or not x.get("in_mano") and not x.get("mano"):
            continue
        mano_ = set(x.get("in_mano") or [])
        for n in x["deck"]:
            if DA.e_terra(n):
                continue
            ni = DA.nome_intero(n)
            dentro[ni] += 1
            v_dentro[ni] += x["vinta"]
            if ni in mano_:
                vista[ni] += 1
                v_vista[ni] += x["vinta"]
    out = []
    for n, tot in dentro.items():
        nv, nn = vista[n], tot - vista[n]
        if not nv or not nn:
            continue
        wr_v, wr_n = 100 * v_vista[n] / nv, 100 * (v_dentro[n] - v_vista[n]) / nn
        out.append(dict(nome=n, n=nv, vinte=v_vista[n], perse=nv - v_vista[n], wr=round(wr_v, 1), quota=round(100 * nv / tot, 1), iwd=round(wr_v - wr_n, 1),
                        n_non=nn, wr_non=round(wr_n, 1), poche=tot < minimo, filtro=("iwd", n)))
    out.sort(key=lambda c: (c["poche"], -c["iwd"]))
    return out[:quante]


def prova():
    casi = []
    casi.append(("le rimozioni dal testo: Mortify e Shock si', Opt no", rimozione("Mortify") and rimozione("Shock") and not rimozione("Opt")))
    lista = {"Plains": 10, "Swamp": 7, "Mortify": 2, "Healer's Hawk": 4, "Shock": 1}
    c = campi(dict(seat=1), dict(partita="nessuna", inizia=True), lista, {"Plains": 3, "Mortify": 1, "Healer's Hawk": 3})
    casi.append(("C2: mazzo WBR, mano con sole Plains: mancano dei colori; C3: una rimozione in mano, 3 nel mazzo; C9: 17 terre",
                 c["c2_mano"] == "Yes" and c["rim_mano"] == "1" and c["rim_mazzo"] == "5-8" and c["terre_mazzo"] == "17"))
    c2 = campi(dict(seat=1), dict(partita="nessuna", inizia=True), {"Plains": 17, "Healer's Hawk": 23}, {"Plains": 3, "Healer's Hawk": 4})
    casi.append(("negativa C2/C3: mazzo bianco con la Plains in mano non manca nulla; nessuna rimozione", c2["c2_mano"] == "No" and c2["rim_mano"] == "0"
                 and c2["rim_mazzo"] == "0-4"))
    import datetime as dt
    q = lambda h: dt.datetime(2026, 11, 13, h)
    rr = [dict(tipo="Constructed", quando=q(10), vinta=False, n_sessione=1), dict(tipo="Constructed", quando=q(11), vinta=False, n_sessione=2),
          dict(tipo="Constructed", quando=q(12), vinta=True, n_sessione=3), dict(tipo="Constructed", quando=q(13), vinta=False, n_sessione=4)]
    serie(rr)
    casi.append(("C6: dopo una sconfitta, due di fila prima della terza; la prima della sessione", rr[1]["dopo"] == "After a loss" and rr[2]["serie_prima"] == "2"
                 and rr[3]["dopo"] == "After a win" and rr[0]["dopo"] == "First of the session" and rr[3]["serie_prima"] == "0"))
    casi.append(("C6: la serie piu' lunga di sconfitte 2, di vittorie 1", serie_piu_lunghe(rr) == (1, 2)))
    ri = [dict(deck={"Mortify": 1, "Plains": 1}, in_mano=["Mortify"], mano=["Mortify"], vinta=True) for _ in range(8)] + \
         [dict(deck={"Mortify": 1, "Plains": 1}, in_mano=[], mano=["Plains"], vinta=False) for _ in range(8)]
    iw = iwd(ri)
    casi.append(("C4: Mortify vista vince il 100%, non vista lo 0%: IWD +100; negativa: le terre non ci sono", iw and iw[0]["nome"] == "Mortify" and iw[0]["iwd"] == 100
                 and all(c_["nome"] != "Plains" for c_ in iw)))
    for n, ok in casi:
        print(("ok    " if ok else "ROSSO ") + n)
    print(f"{sum(1 for _n, ok in casi if ok)}/{len(casi)}")
    return all(ok for _n, ok in casi)


import dati_analizzatore as DA  # noqa: E402  (in fondo: dati_analizzatore importa questo modulo, e avviato da solo lo reimporterebbe a meta')

if __name__ == "__main__":
    sys.exit(0 if prova() else 1)
