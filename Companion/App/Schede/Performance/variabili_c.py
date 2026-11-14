"""Le variabili C del censimento (13 nov 2026, Note/HANDOFF_Censimento_Performance.md; Autore: «a tutto quel che è rimasto»):

    C2  la mano senza un colore del mazzo (le terre delle 7 carte non lo danno) e il colore che manca in campo a fine tuo turno 3
    C3  le rimozioni: nella mano iniziale (0, 1, 2+), nel mazzo ogni 60 carte (0-4, 5-8, 9+), la prima lanciata (entro il tuo turno 3, 5, dopo, mai)
    C4  pescata contro non pescata, carta per carta (l'IWD personale): il win rate delle partite in cui la carta ti e' passata per la mano meno quello delle
        partite in cui era nel mazzo e non l'hai vista (una riga di Cards)
    C6  il tilt misurato: dopo una vittoria o una sconfitta, e quante sconfitte di fila prima della partita
    C7  le carte in mano a fine tuo turno 3, 5, 7 (tue e sue)
    C9  le terre nel mazzo
    C13 il valore dei bersagli delle tue rimozioni: cosa ha tolto ogni tua rimozione (il valore di mana del permanente; una pedina 0), e quante volte
        su una pedina o su una carta piu' economica della rimozione (grado C: una carta da 1 mana puo' essere la minaccia vera)
    C15 «quale carta mi avrebbe salvato?»: le sue carte che vedi piu' nelle tue sconfitte che nelle vittorie (le minacce), e per ognuna le rimozioni della
        tua collezione, nei colori dei tuoi mazzi (e legali in Standard se giochi Standard), che dal testo la tolgono (grado C: il bersaglio, il danno contro la
        costituzione, -X/-X, «power 3 or less», «nonblack», «with flying»; non le protezioni)
    C8  le versioni della lista dello stesso mazzo (la lista di ogni partita da partite_log): «nome · v2 · since 12 Nov», col win rate per versione nel Report
        (Group by), e cosa e' cambiato dalla versione prima

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
            dopo="The game before", versione="Deck version", serie_prima="Losses in a row before this game", terre_mazzo="Lands in your deck",
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


def versioni(righe):
    """C8: le versioni della lista di ogni tuo mazzo costruito (lo stesso mazzo di Arena, se no lo stesso nome), dalla prima partita: una lista mai vista prima
    e' una versione nuova, una lista tornata uguale a una di prima riprende il suo numero. Il mazzo principale senza la sideboard (la lista di partite_log).
    Scrive in ogni riga «versione» («nome · v2 · since 12 Nov») e «versione_cambi» (le carte cambiate dalla versione prima: «+2 Shock, -1 Opt»); il limited
    no (ogni draft e' un mazzo suo). -> {chiave del mazzo: [(versione, prima partita, cambi)]}."""
    gruppi = collections.defaultdict(list)
    for x in righe:
        if x.get("tipo") != "Constructed" or not x.get("deck"):
            continue
        gruppi[x.get("mazzo_id") or (x.get("mio") or "").strip()].append(x)
    out = {}
    for k, xs in gruppi.items():
        viste = []      # [(lista come chiave, numero, prima partita, cambi)]
        prima_l = None
        for x in sorted(xs, key=lambda x: x["quando"]):
            chiave = tuple(sorted((n, q) for n, q in x["deck"].items() if q))
            v_ = next((v for v in viste if v[0] == chiave), None)
            if v_ is None:
                cambi = ""
                if prima_l is not None:
                    a_, b_ = dict(prima_l), dict(chiave)
                    d_ = {n: b_.get(n, 0) - a_.get(n, 0) for n in set(a_) | set(b_)}
                    piu = [f"+{q} {n}" for n, q in sorted(d_.items()) if q > 0]
                    meno = [f"-{-q} {n}" for n, q in sorted(d_.items()) if q < 0]
                    cambi = ", ".join(piu + meno)
                v_ = (chiave, len(viste) + 1, x["quando"], cambi)
                viste.append(v_)
            prima_l = chiave
            nome = (x.get("mio") or "").strip() or "Deck"
            x["versione"] = f"{nome} · v{v_[1]} · since {v_[2]:%d %b}"
            x["versione_cambi"] = v_[3]
        out[k] = [(f"v{v[1]}", v[2], v[3]) for v in viste]
    return out


def bersagli_rimozioni(x):
    """C13: le tue rimozioni lanciate (magie, non abilita') coi permanenti dell'avversario che hanno tolto (colpiti_di, dalla foto con la magia in pila).
    -> [dict(rim, rim_mv, bers, bers_mv, pedina)]; [] senza i momenti."""
    d = DA._MANA.get(x.get("partita")) or {}
    seat = x.get("seat")
    if seat not in (1, 2):
        return []
    out = []
    for m in d.get("momenti") or []:
        if m[0] != "spell" or len(m) < 5 or not isinstance(m[4], dict):
            continue
        info = m[4]
        if info.get("chi") != seat or info.get("ab"):
            continue
        nome = DA.nome_intero(DA.nome_grp(info.get("g")) or "")
        if not nome or not rimozione(nome):
            continue
        suoi = {c_[5]: c_ for c_ in ((m[3] or {}).get("c") or [[], []])[2 - seat] or [] if len(c_) > 5}
        for id_ in DA.colpiti_di(info):
            c_ = suoi.get(id_)
            if c_ is None:
                continue
            nb = DA.nome_intero(DA.nome_grp(c_[0]) or "") or "a token"
            pedina = bool(c_[2])
            out.append(dict(rim=nome, rim_mv=(DA._carta(nome) or {}).get("cmc", 0), bers=nb, bers_mv=0 if pedina else (DA._carta(nb) or {}).get("cmc", 0),
                            pedina=pedina))
    return out


def valore_rimozioni(r, quante=40):
    """C13 in Cards: per ogni tua rimozione, nelle partite r in cui l'hai lanciata (n, il win rate: le partite del suo filtro), quante volte ha tolto qualcosa, il valore di mana medio di cio' che ha tolto e la quota su
    pedine o carte piu' economiche di lei. -> righe di Cards (filtro: le partite in cui l'hai lanciata)."""
    per = collections.defaultdict(list)
    partite, vinte = collections.Counter(), collections.Counter()
    for x in r:
        bb = x.get("rim_bersagli") or []
        for b in bb:
            per[b["rim"]].append(b)
        for n in set(x.get("mie_lanciate") or []) | {b["rim"] for b in bb}:     # le partite in cui l'hai lanciata: quelle del suo filtro
            partite[n] += 1
            vinte[n] += x["vinta"]
    out = []
    for n, bb in per.items():
        npar = partite[n]
        econ = sum(1 for b in bb if b["pedina"] or b["bers_mv"] < b["rim_mv"])
        out.append(dict(nome=n, n=npar, vinte=vinte[n], perse=npar - vinte[n], wr=round(100 * vinte[n] / npar, 1), quota=0.0,
                        tolti=len(bb), bers_mv=round(sum(b["bers_mv"] for b in bb) / len(bb), 1), economici=round(100 * econ / len(bb)),
                        rim_mv=bb[0]["rim_mv"], filtro=("lanciate", n)))
    out.sort(key=lambda c: (-c["tolti"], c["nome"]))
    return out[:quante]


COLORI_PAROLA = {"white": "W", "blue": "U", "black": "B", "red": "R", "green": "G"}
TOGLIE_PERMANENTE = r"(?:destroy|exile|return) (?:up to one )?target (?:nonland permanent|permanent|{t}(?: or [a-z]+)?|[a-z]+ or {t}|[a-z]+, {t})"


def _prima(c):
    return ((c or {}).get("tipo") or "").split(" // ")[0]


def colpisce(rim, minaccia):
    """C15: la carta rim, dal suo testo, puo' togliere la carta minaccia? (grado C) Il bersaglio giusto (creatura, artefatto, incantesimo, planeswalker,
    permanente), il danno contro la costituzione, il -X/-X, le restrizioni piu' comuni (power o mana value N or less, non<colore>, with flying)."""
    cr, cm = DA._carta(rim or "") or {}, DA._carta(minaccia or "") or {}
    t, tipo = (cr.get("testo") or "").lower(), _prima(cm)
    if not t or not tipo:
        return False
    if "Creature" in tipo:
        if not (rimozione(rim) or re.search(TOGLIE_PERMANENTE.format(t="creature"), t)):
            return False
        try:
            forza, cost = (int(v) for v in (cm.get("pt") or "").split("/")[:2])
        except ValueError:
            forza, cost = None, None
        m = re.search(r"deals? (\d+) damage to (?:any target|(?:up to one )?target (?:[\w-]+ )*?creature)", t)
        if m and cost is not None and int(m.group(1)) < cost and not re.search(r"(?:destroy|exile) target (?:[\w-]+ )*?creature", t):
            return False
        m = re.search(r"gets? -\d+/-(\d+)", t)
        if m and not re.search(r"deals? .*damage|(?:destroy|exile) target", t) and cost is not None and int(m.group(1)) < cost:
            return False
        m = re.search(r"creature with (power|mana value) (\d+) or less", t)
        if m and ((m.group(1) == "power" and (forza is None or forza > int(m.group(2)))) or (m.group(1) == "mana value" and (cm.get("cmc") or 0) > int(m.group(2)))):
            return False
        m = re.search(r"target non(white|blue|black|red|green) creature", t)
        if m and COLORI_PAROLA[m.group(1)] in (cm.get("colori") or ""):
            return False
        if re.search(r"target creature with flying", t) and "flying" not in (cm.get("testo") or "").lower():
            return False
        return True
    for k in ("Planeswalker", "Artifact", "Enchantment", "Battle"):
        if k in tipo:
            kk = k.lower()
            if re.search(TOGLIE_PERMANENTE.format(t=kk), t):
                return True
            if k == "Planeswalker" and (re.search(r"target (?:creature or )?planeswalker", t) or "any target" in t) and re.search(r"destroy|exile|damage", t):
                return True
    return False


def minacce(r, quante=12, minimo=3):
    """C15: le sue magie lanciate che stanno piu' nelle tue sconfitte che nelle vittorie (la quota delle sconfitte con la carta meno quella delle vittorie),
    da `minimo` sconfitte; per ognuna le risposte della tua collezione (risposte). -> righe di Cards: dict(nome, n, vinte, perse, wr, quota, eccesso,
    risposte, filtro)."""
    perse = [x for x in r if not x["vinta"]]
    vinte = [x for x in r if x["vinta"]]
    if not perse:
        return []
    cp, cv = collections.Counter(), collections.Counter()
    for x in perse:
        cp.update(set(x.get("sue_lanciate") or []))
    for x in vinte:
        cv.update(set(x.get("sue_lanciate") or []))
    colori = set()
    for x in r:
        colori |= _colori_mazzo(x.get("deck") or {})
    standard = bool(r) and all((x.get("formato") or "").lower() == "standard" for x in r)
    out = []
    for n, l in cp.items():
        tipo_ = _prima(DA._carta(n))
        if l < minimo or DA.e_terra(n) or not tipo_ or "Instant" in tipo_ or "Sorcery" in tipo_:      # una minaccia resta in campo: si toglie
            continue
        ecc = 100 * l / len(perse) - (100 * cv[n] / len(vinte) if vinte else 0)
        if ecc <= 0:
            continue
        tot = l + cv[n]
        out.append(dict(nome=n, n=tot, vinte=cv[n], perse=l, wr=round(100 * cv[n] / tot, 1), quota=round(100 * tot / len(r), 1), eccesso=round(ecc),
                        risposte=None, filtro=("sue_lanciate", n)))
    out.sort(key=lambda c: (-c["eccesso"] * c["perse"], c["nome"]))
    out = out[:quante]
    for c in out:
        c["risposte"] = risposte(c["nome"], colori, standard)
    return out


def risposte(minaccia, colori, standard, quante=8):
    """C15: le carte che hai (almeno una copia), nei colori dati (tutti i loro colori dentro; incolori sempre), legali in Standard se standard, che dal testo
    tolgono la minaccia (colpisce), dalla piu' economica."""
    out = []
    for c in DA._tabella().values():
        if not c.get("copie") or "Land" in _prima(c) or (standard and (not c.get("standard") or c.get("ban_std"))):
            continue
        if not set(c.get("colori") or "") - {"C"} <= colori:
            continue
        if "Creature" in _prima(c) and " enters" not in (c.get("testo") or ""):      # una creatura risponde solo all'entrata (o muore: no)
            continue
        if colpisce(c["nome"], minaccia):
            out.append(c["nome"])
    out.sort(key=lambda n: ((DA._carta(n) or {}).get("cmc", 99), n))
    return out[:quante]


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
    q2 = lambda d: dt.datetime(2026, 11, d, 20)
    rv = [dict(tipo="Constructed", quando=q2(10), mio="UW", mazzo_id="a", deck={"Opt": 4, "Island": 20}),
          dict(tipo="Constructed", quando=q2(11), mio="UW", mazzo_id="a", deck={"Opt": 2, "Shock": 2, "Island": 20}),
          dict(tipo="Constructed", quando=q2(12), mio="UW", mazzo_id="a", deck={"Opt": 4, "Island": 20}),
          dict(tipo="Constructed", quando=q2(12), mio="Red", mazzo_id="b", deck={"Shock": 4, "Mountain": 20}),
          dict(tipo="Limited", quando=q2(12), mio="WB", mazzo_id="c", deck={"Bolt": 1})]
    vv = versioni(rv)
    casi.append(("C8: due versioni di UW (la terza partita torna alla v1), coi cambi della v2; Red una sola", rv[0]["versione"] == "UW · v1 · since 10 Nov"
                 and rv[1]["versione"] == "UW · v2 · since 11 Nov" and rv[1]["versione_cambi"] == "+2 Shock, -2 Opt" and rv[2]["versione"] == rv[0]["versione"]
                 and len(vv["a"]) == 2 and len(vv["b"]) == 1))
    casi.append(("negativa C8: il limited non ha versioni", "versione" not in rv[4]))
    rb = [dict(vinta=True, rim_bersagli=[dict(rim="Shock", rim_mv=1, bers="Dragon", bers_mv=5, pedina=False),
                                         dict(rim="Shock", rim_mv=1, bers="a token", bers_mv=0, pedina=True)]),
          dict(vinta=False, rim_bersagli=[dict(rim="Murder", rim_mv=3, bers="Goblin", bers_mv=2, pedina=False)]), dict(vinta=False)]
    vr = {c_["nome"]: c_ for c_ in valore_rimozioni(rb)}
    casi.append(("C13: Shock ha tolto un Dragon (5) e una pedina: media 2,5, meta' su bersagli economici; Murder su un Goblin da 2: 100% economico",
                 vr["Shock"]["tolti"] == 2 and vr["Shock"]["bers_mv"] == 2.5 and vr["Shock"]["economici"] == 50 and vr["Murder"]["economici"] == 100
                 and vr["Shock"]["wr"] == 100.0))
    casi.append(("negativa C13: una partita senza rimozioni lanciate non entra", sum(c_["n"] for c_ in vr.values()) == 2))
    vecchia = DA._TAB.get("t")
    DA._TAB["t"] = {"Shock": dict(nome="Shock", tipo="Instant", cmc=1, colori="R", testo="Shock deals 2 damage to any target.", copie=4, standard=True),
                    "Murder": dict(nome="Murder", tipo="Instant", cmc=3, colori="B", testo="Destroy target creature.", copie=1, standard=True),
                    "Doom Blade": dict(nome="Doom Blade", tipo="Instant", cmc=2, colori="B", testo="Destroy target nonblack creature.", copie=2, standard=True),
                    "Shatter": dict(nome="Shatter", tipo="Instant", cmc=2, colori="R", testo="Destroy target artifact.", copie=1, standard=True),
                    "Goblin": dict(nome="Goblin", tipo="Creature — Goblin", cmc=1, colori="R", testo="", pt="1/1", copie=0),
                    "Vampire": dict(nome="Vampire", tipo="Creature — Vampire", cmc=4, colori="B", testo="", pt="4/5", copie=0),
                    "Relic": dict(nome="Relic", tipo="Artifact", cmc=2, colori="", testo="", copie=0)}
    _RIM.clear()
    try:
        casi.append(("C15: Shock toglie il Goblin 1/1 ma non il Vampire 4/5; Murder il Vampire; Doom Blade non un nero; Shatter il Relic",
                     colpisce("Shock", "Goblin") and not colpisce("Shock", "Vampire") and colpisce("Murder", "Vampire") and not colpisce("Doom Blade", "Vampire")
                     and colpisce("Shatter", "Relic") and not colpisce("Shatter", "Goblin")))
        rm = [dict(vinta=False, sue_lanciate=["Vampire"], deck={"Shock": 4, "Murder": 2}, formato="standard") for _ in range(4)] + \
             [dict(vinta=True, sue_lanciate=[], deck={"Shock": 4, "Murder": 2}, formato="standard") for _ in range(4)]
        mn = minacce(rm)
        casi.append(("C15: il Vampire in 4 sconfitte su 4 e in nessuna vittoria; la risposta che hai nei tuoi colori e' Murder",
                     bool(mn) and mn[0]["nome"] == "Vampire" and mn[0]["perse"] == 4 and mn[0]["risposte"] == ["Murder"]))
        casi.append(("negativa C15: Doom Blade (nero ma non lo toglie) e Shock (troppo poco danno) non sono risposte; una carta vista solo nelle vittorie no",
                     bool(mn) and "Doom Blade" not in mn[0]["risposte"] and "Shock" not in mn[0]["risposte"] and len(mn) == 1))
    finally:
        DA._TAB["t"] = vecchia
        _RIM.clear()
    for n, ok in casi:
        print(("ok    " if ok else "ROSSO ") + n)
    print(f"{sum(1 for _n, ok in casi if ok)}/{len(casi)}")
    return all(ok for _n, ok in casi)


import dati_analizzatore as DA  # noqa: E402  (in fondo: dati_analizzatore importa questo modulo, e avviato da solo lo reimporterebbe a meta')

if __name__ == "__main__":
    sys.exit(0 if prova() else 1)
