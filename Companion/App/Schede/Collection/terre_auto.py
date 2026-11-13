"""Mana base del deck builder (Autore, 8 nov 2026, poi «non chiamarlo land fixer ma mana base»: «nel deck builder metti un calcolatore intelligentissimo che in base alla costruzione del deck inserisce
le giuste terre, possedute o meno», poi «io posso mettere le mie terre speciali se servono, fai solo un pulsante che si chiama land fix che aggiunge tutte le
terre mancanti migliori per il deck»).

Le terre che ci sono restano tutte: si aggiungono solo quelle che mancano, possedute o no (quelle da craftare si dicono).
1. QUANTE terre: dai mazzi del meta dello stesso formato (Untapped per Arena, MTGGoldfish per la carta), una retta terre = a + b x costo medio delle
   magie, misurata sulle loro liste; il mazzo prende la sua. Con meno di 8 liste: il rapporto mediano terre/carte di quelle che ci sono, o il 40% (grado C).
2. QUANTE FONTI per colore: la regola dell'articolo di Frank Karsten (2022, letta e scritta in Companion/Drafter/fonti_mana.py): una magia di costo M si
   lancia «con costanza» se almeno l'(89 + M)% delle volte, sul play, al turno M ci sono le fonti del colore sapendo di avere almeno M terre; carte d'oro +1
   fonte per colore. Qui il conto e' esatto (ipergeometrica a due livelli) per la grandezza vera del mazzo e le sue terre, non la tabella da 40.
   Karsten simula anche i mulligan: --prova confronta questo conto con la sua colonna da 40 carte.
3. QUALI terre: le terre legali nel formato che producono solo colori del mazzo, per qualita': prima quelle che entrano sempre stappate, poi quelle che
   entrano stappate a una condizione che di solito c'e' (shock, fast, slow, check), le tappate solo se tolgono un deficit; 4 copie al massimo contando
   quelle gia' nel mazzo; poi le basi, al colore che manca di piu'. Anche se non le hai: quelle da craftare si dicono, e se non le craftai le sostituisci tu.
   A parita' di qualita' prima quelle che hai.

    py -I -X utf8 Companion/App/Schede/Collection/terre_auto.py --prova      il conto contro la tabella di Karsten, i casi, le prove negative
"""
import os, sys
_casa = os.path.dirname(os.path.abspath(__file__))      # si sale fino a percorsi.py, che mette nel sys.path tutte le cartelle del Companion
while not os.path.isfile(os.path.join(_casa, "percorsi.py")):
    _casa = os.path.dirname(_casa)
if _casa not in sys.path:
    sys.path.insert(0, _casa)
import percorsi  # noqa: E402
import math
import re

COLORI = "WUBRG"
BASE_DI = {"W": "Plains", "U": "Island", "B": "Swamp", "R": "Mountain", "G": "Forest"}


# ---------------------------------------------------------------- 2. le fonti, col conto di Karsten
def _c(n, k):
    return math.comb(n, k) if 0 <= k <= n else 0


def p_lancio(N, L, S, M, c):
    """P(almeno c fonti del colore fra le carte viste al turno M sul play | almeno M terre), mazzo di N carte, L terre, S fonti del colore."""
    n = 7 + M - 1
    num = den = 0
    for s in range(0, min(S, n) + 1):
        for o in range(0, min(L - S, n - s) + 1):
            resto = n - s - o
            if resto > N - L:
                continue
            w = _c(S, s) * _c(L - S, o) * _c(N - L, resto)
            if s + o >= M:
                den += w
                if s >= c:
                    num += w
    return num / den if den else 0.0


def fonti_richieste(N, L, generico, simboli, soglia=None):
    """Le fonti minime del colore per una magia con quel mana generico e quei simboli del colore (Karsten: (89 + M)% al turno M = costo)."""
    if simboli <= 0:
        return 0
    M = max(1, generico + simboli)
    q = (89 + M) / 100 if soglia is None else soglia
    for S in range(simboli, L + 1):
        if p_lancio(N, L, S, M, simboli) >= q:
            return S
    return L


def costo_di(nome, db):
    """(mana generico, {colore: simboli}) dalla carta del database di Arena (costo come lista di simboli, «2», «U», «W/U»...)."""
    c = db.get(nome) or db.get(nome.split(" // ")[0].strip()) or {}
    gen, sim = 0, {}
    for x in c.get("costo") or []:
        x = str(x)
        if x.isdigit():
            gen += int(x)
        elif x in COLORI:
            sim[x] = sim.get(x, 0) + 1
        elif "/" in x:                       # ibrido: conta per ognuno dei suoi colori come mezzo vincolo; qui si tiene il primo colore del mazzo
            k = next((ch for ch in x if ch in COLORI), None)
            if k:
                sim[k] = sim.get(k, 0) + 1
        elif x not in ("X", "C", "S"):
            gen += 1
    return gen, sim


def richieste(magie, N, L, db):
    """{colore: fonti richieste} = il massimo sulle magie del mazzo; carte d'oro +1 per colore (Karsten)."""
    out = {}
    for n in magie:
        gen, sim = costo_di(n, db)
        oro = len(sim) > 1
        for k, s in sim.items():
            r = fonti_richieste(N, L, gen + sum(v for kk, v in sim.items() if kk != k), s) + (1 if oro else 0)
            out[k] = max(out.get(k, 0), min(L, r))
    return out


# ---------------------------------------------------------------- 1. quante terre, dai mazzi del meta
def retta_terre(liste, e_terra, cmc):
    """Su [{nome: copie}] dei mazzi del meta: (a, b, quanti) con terre = a + b * costo medio delle magie; None se le liste sono poche o tutte uguali."""
    xs, ys = [], []
    for l in liste:
        if not l:
            continue
        ter = sum(q for n, q in l.items() if e_terra(n))
        mag = [(n, q) for n, q in l.items() if not e_terra(n)]
        qm = sum(q for _n, q in mag)
        if not qm or not ter:
            continue
        xs.append(sum(q * (cmc(n) or 0) for n, q in mag) / qm); ys.append(ter * 60 / max(1, sum(l.values())))      # su 60 carte
    if len(xs) < 8:
        return None
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
    vx = sum((x - mx) ** 2 for x in xs)
    if vx < 1e-9:
        return None
    b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / vx
    return my - b * mx, b, len(xs)


def quante_terre(N, magie, e_terra, cmc, liste_meta):
    """-> (terre per un mazzo di N carte, da dove viene il numero)."""
    qm = sum(magie.values())
    mv = sum(q * (cmc(n) or 0) for n, q in magie.items()) / qm if qm else 2.5
    r = retta_terre(liste_meta, e_terra, cmc)
    if r:
        a, b, k = r
        x = (a + b * mv) * N / 60
        return int(round(x)), f"meta: {k} lists, lands = {a:.1f} + {b:.2f} x avg mana value ({mv:.2f}) on 60 cards"
    return int(round(N * 0.40)), "40% of the deck (not enough meta lists)"


# ---------------------------------------------------------------- 3. quali terre
def tappata(testo):
    """0 = entra sempre stappata, 1 = stappata a una condizione che di solito c'e', 2 = tappata. Condizioni buone: la shock («you may pay»), fast e slow
    («other lands»), le check («you control a Plains/Island/...», «a basic land»). Le altre («unless you control a planeswalker», «unless a player has 13 or
    less life») nella pratica entrano tappate: contano 2 (8 nov 2026, il primo giro metteva Innovative Commons e Peculiar Lighthouse fra le buone)."""
    t = (testo or "").lower()
    if not re.search(r"enters (the battlefield )?tapped", t):
        return 0
    if re.search(r"you may pay|other lands|unless you control an? (plains|island|swamp|mountain|forest|basic land)|unless you control (two|a) basic", t):
        return 1
    return 2


def candidate(colori_mazzo, fmt, db, legale, prodotti):
    """Le terre non base legali nel formato che producono almeno due colori del mazzo e nessun colore fuori: [(nome, colori, tappata)]."""
    out = []
    for n, c in db.items():
        tipo = c.get("tipo") or ""
        if "Land" not in tipo or "Basic" in tipo or " // " in n:
            continue
        p = set(prodotti(n))
        if len(p) < 2 or not p <= set(colori_mazzo):
            continue
        if not legale(n):
            continue
        out.append((n, "".join(k for k in COLORI if k in p), tappata(c.get("testo"))))
    return out


def fix(zone_deck, fmt, db, legale, prodotti, e_terra, cmc, coll, liste_meta, N=None, copie_max=4):
    """Le terre da aggiungere al mazzo (le sue restano tutte). -> dict(aggiungi {nome: copie}, terre, obiettivo, perche', fonti {colore: (ha, serve)}, mancano [nome])."""
    magie = {n: q for n, q in zone_deck.items() if not e_terra(n)}
    terre_ora = {n: q for n, q in zone_deck.items() if e_terra(n)}
    N = N or max(60, sum(zone_deck.values()))
    L, perche = quante_terre(N, magie, e_terra, cmc, liste_meta)
    L = max(L, sum(terre_ora.values()))
    req = richieste(magie, N, L, db)
    colori_mazzo = "".join(k for k in COLORI if k in req)
    src = {k: 0 for k in colori_mazzo}

    def conta(n, q):
        for k in prodotti(n):
            if k in src:
                src[k] += q
    for n, q in terre_ora.items():
        conta(n, q)
    posti = L - sum(terre_ora.values())
    agg = {}

    simboli = {k: 0 for k in colori_mazzo}
    for n, q in magie.items():
        for k, s in costo_di(n, db)[1].items():
            if k in simboli:
                simboli[k] += s * q

    def basi(fonti, liberi):
        """Le basi nei posti liberi, una alla volta al colore piu' lontano dalla sua richiesta (a parita' quello con piu' simboli): -> {colore: basi}."""
        f, out = dict(fonti), {}
        for _ in range(max(0, liberi)):
            if not colori_mazzo:
                break
            k = max(colori_mazzo, key=lambda x: (req[x] - f[x], simboli[x]))
            f[k] += 1; out[k] = out.get(k, 0) + 1
        return out

    def deficit():
        """Il deficit di fonti a mazzo finito: le doppie scelte fin qui e le basi nei posti che restano."""
        f = dict(src)
        for k, q in basi(src, posti).items():
            f[k] += q
        return sum(max(0, req[k] - f[k]) for k in colori_mazzo)

    if len(colori_mazzo) >= 2 and posti > 0:
        cand = candidate(colori_mazzo, fmt, db, legale, prodotti)
        # le migliori prima: piu' colori del mazzo, meno tappate, quelle che hai, il nome
        cand.sort(key=lambda x: (-len(x[1]), x[2], -min(4, coll.get(x[0], 0)), x[0]))
        # per qualita' (Autore, 8 nov 2026: «va benissimo che le guardi per qualita' / se la massima qualita' non la abbiamo il player va a sostituire»):
        # le terre migliori anche se non le hai, e quelle da craftare si dicono; a parita' di qualita' prima quelle che hai. Una doppia entra se a mazzo
        # finito non peggiora le fonti; una sempre tappata solo se toglie un deficit
        for n, cols, tap in cand:
            gia = zone_deck.get(n, 0)
            for _ in range(max(0, copie_max - gia)):          # 4 copie, 1 nel Brawl
                if posti <= 0:
                    break
                prima = deficit()
                for k in cols:
                    src[k] += 1
                posti -= 1
                dopo = deficit()
                if dopo > prima or (tap == 2 and dopo >= prima):
                    for k in cols:
                        src[k] -= 1
                    posti += 1
                    break
                agg[n] = agg.get(n, 0) + 1
    for k, q in basi(src, posti).items():
        agg[BASE_DI[k]] = agg.get(BASE_DI[k], 0) + q; src[k] += q
    posti = 0
    mancano = {n: max(0, q + zone_deck.get(n, 0) - coll.get(n, 0)) for n, q in agg.items() if n not in BASE_DI.values()}
    return dict(aggiungi=agg, terre=L, obiettivo=perche, fonti={k: (src[k], req[k]) for k in colori_mazzo},
                mancano={n: q for n, q in mancano.items() if q > 0}, carte=N)


# ---------------------------------------------------------------- prove
def prova():
    ok = tot = 0

    def caso(n, v):
        nonlocal ok, tot
        tot += 1; ok += bool(v); print(("  ok  " if v else "  NO  ") + n)
    # il conto esatto contro la colonna da 40 carte di Karsten (17 terre); Karsten simula anche i mulligan: si accetta 1 fonte di scarto
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "Drafter"))
    import fonti_mana as FM
    scarti = {(g, s): fonti_richieste(40, 17, g, s) - v for (g, s), v in FM.KARSTEN_40.items()}
    uguali = sum(1 for d in scarti.values() if d == 0)
    print(f"     Karsten 40 carte: {uguali}/{len(scarti)} uguali, scarti {sorted(set(scarti.values()))}")
    caso("il conto esatto rifa' la tabella di Karsten entro 1 fonte", all(abs(d) <= 1 for d in scarti.values()))
    neg = {(g, s): fonti_richieste(40, 17, g, s, soglia=0.80) - v for (g, s), v in FM.KARSTEN_40.items()}
    caso("prova negativa: con l'80% invece di (89+M)% la tabella non torna", sum(1 for d in neg.values() if abs(d) > 1) >= 3)
    # un mazzo finto da 60: 20 magie rosse e blu, nessuna terra
    db = {"Sacred Foundry": dict(tipo="Land — Mountain Plains", testo="As this land enters, you may pay 2 life. If you don't, it enters tapped."),
          "Shivan Reef": dict(tipo="Land", testo="{T}: Add {C}. {T}: Add {U} or {R}. This land deals 1 damage to you."),
          "Swiftwater Cliffs": dict(tipo="Land", testo="This land enters tapped. When it enters, you gain 1 life."),
          "Sulfur Falls": dict(tipo="Land", testo="This land enters tapped unless you control an Island or a Mountain."),
          "Watery Grave": dict(tipo="Land — Island Swamp", testo="As this land enters, you may pay 2 life. If you don't, it enters tapped."),
          "Bolt": dict(tipo="Instant", costo=["R"], cmc=1), "Counter": dict(tipo="Instant", costo=["U", "U"], cmc=2),
          "Drake": dict(tipo="Creature", costo=["3", "U"], cmc=4), "Dual": dict(tipo="Creature", costo=["1", "U", "R"], cmc=3)}
    for b in BASE_DI.values():
        db[b] = dict(tipo="Basic Land", testo="")
    prod = {"Sacred Foundry": "RW", "Shivan Reef": "UR", "Swiftwater Cliffs": "UR", "Sulfur Falls": "UR", "Watery Grave": "UB",
            "Plains": "W", "Island": "U", "Swamp": "B", "Mountain": "R", "Forest": "G"}
    e_t = lambda n: "Land" in (db.get(n, {}).get("tipo") or "")
    cmc = lambda n: db.get(n, {}).get("cmc", 0)
    deck = {"Bolt": 10, "Counter": 10, "Drake": 8, "Dual": 8}
    r = fix(deck, "Standard", db, lambda n: True, lambda n: prod.get(n, ""), e_t, cmc, {"Sulfur Falls": 4}, [])
    a = r["aggiungi"]
    caso("arriva alle terre del 40% senza meta (24 su 60)", sum(a.values()) == 24 and r["terre"] == 24)
    caso("prende le doppie UR che servono, 4 copie", a.get("Shivan Reef") == 4 and a.get("Sulfur Falls") == 4)
    caso("niente terre fuori colore (Sacred Foundry, Watery Grave)", "Sacred Foundry" not in a and "Watery Grave" not in a)
    senza = {k: v for k, v in db.items() if k != "Swiftwater Cliffs"}
    r0 = fix(deck, "Standard", senza, lambda n: True, lambda n: prod.get(n, ""), e_t, cmc, {"Sulfur Falls": 4}, [])
    manca0 = any(h < s for h, s in r0["fonti"].values())
    caso("la tappata entra solo se senza di lei resta un deficit", (a.get("Swiftwater Cliffs", 0) > 0) == manca0)
    db["Big"] = dict(tipo="Creature", costo=["5", "U"], cmc=6)
    leggero = {"Bolt": 16, "Big": 4}            # rosso quasi da solo e un blu caro: le fonti richieste stanno nelle 24 terre con le sole basi
    r1 = fix(leggero, "Standard", db, lambda n: True, lambda n: prod.get(n, ""), e_t, cmc, {}, [])
    caso("mazzo leggero: nessuna tappata", "Swiftwater Cliffs" not in r1["aggiungi"] and all(h >= s for h, s in r1["fonti"].values()))
    caso("per qualita': le doppie stappate entrano anche se non le hai, e si dicono da craftare", r1["aggiungi"].get("Shivan Reef") == 4 and r1["mancano"].get("Shivan Reef") == 4)
    r3 = fix(leggero, "Standard", db, lambda n: True, lambda n: prod.get(n, ""), e_t, cmc, {"Shivan Reef": 2}, [])
    caso("se ne hai 2, da craftare restano 2", r3["aggiungi"].get("Shivan Reef") == 4 and r3["mancano"].get("Shivan Reef") == 2)
    caso("la condizione del planeswalker e' una tappata, la shock no", tappata("This land enters tapped unless you control a planeswalker.") == 2
         and tappata("As this land enters, you may pay 2 life. If you don't, it enters tapped.") == 1)
    caso("dice cosa manca: le Shivan Reef che non hai, non le Sulfur Falls", r["mancano"].get("Shivan Reef") == 4 and "Sulfur Falls" not in r["mancano"])
    caso("le fonti arrivano alla richiesta", all(h >= s for h, s in r["fonti"].values()))
    tue = dict(deck, **{"Cavern of Souls": 4}); db["Cavern of Souls"] = dict(tipo="Land", testo=""); prod["Cavern of Souls"] = ""
    r2 = fix(tue, "Standard", db, lambda n: True, lambda n: prod.get(n, ""), e_t, cmc, {}, [])
    caso("le tue terre restano e contano: ne aggiunge 4 in meno", sum(r2["aggiungi"].values()) == 20 and "Cavern of Souls" not in r2["aggiungi"])
    print(f"terre_auto --prova: {ok}/{tot}")
    return ok == tot


if __name__ == "__main__":
    if "--prova" in sys.argv:
        sys.exit(0 if prova() else 1)
    print(__doc__)
