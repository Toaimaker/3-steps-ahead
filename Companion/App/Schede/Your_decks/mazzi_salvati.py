"""I mazzi che non sono (ancora) su Arena: la wishlist e le build (Autore, 7 nov 2026: «add deck dove possiamo mettere in wishlist altri mazzi quindi
sezione wish list / build your deck dove possiamo testare delle build e guadagnare dati in anticipo»).

- La wishlist: mazzi che vuoi, da una lista incollata (Arena, MTGO, i siti) o dalla scheda Meta. Servono a sapere cosa manca: jolly, carte, prezzo.
- Le build: liste che stai provando. Prima di giocarle danno i dati che si possono avere senza partite: legalita' nel formato, terre in curva e nella
  mano iniziale (conto esatto, ipergeometrica), fonti per colore, il mazzo del meta piu' simile col suo win rate, l'archetipo, jolly e prezzo.
  Sono stime prima della partita, non risultati: il win rate del mazzo simile e' quello del mazzo del meta, non della tua build.
Tutto sta in Log_Arena/mazzi_salvati.json (fuori da git, come i tuoi dati di Arena). La legalita' dello Standard viene da Regole/standard_carte.json e
Regole/Ban_Standard.md, come in Regole/controlla_legalita.py; gli altri formati dai «legalities» di Scryfall (Dati/scryfall/carte.json, prezzi_carte.py).
Explorer non e' fra i formati di Scryfall: e' Pioneer e su Arena.

    py -I -X utf8 Companion/App/Schede/Your_decks/mazzi_salvati.py --prova
"""
import os, sys
_casa = os.path.dirname(os.path.abspath(__file__))      # si sale fino a percorsi.py, che mette nel sys.path tutte le cartelle del Companion
while not os.path.isfile(os.path.join(_casa, "percorsi.py")):
    _casa = os.path.dirname(_casa)
if _casa not in sys.path:
    sys.path.insert(0, _casa)
import percorsi  # noqa: E402
import datetime
import json
import math
import re
import threading
import uuid

QUI = os.path.dirname(os.path.abspath(__file__))
RADICE = percorsi.ROOT
import prezzi_carte as PZ  # noqa: E402

import account as _ACC  # noqa: E402
FILE = _ACC.lega(globals(), "FILE", "mazzi_salvati.json")     # Log_Arena/mazzi_salvati.json; nell'app pubblica uno per account (10 nov 2026, Magic 12)
SEZIONI = ("wish", "build")
BASI = {"Plains", "Island", "Swamp", "Mountain", "Forest", "Wastes", "Snow-Covered Plains", "Snow-Covered Island", "Snow-Covered Swamp",
        "Snow-Covered Mountain", "Snow-Covered Forest", "Snow-Covered Wastes"}
FORMATI = ("Standard", "Alchemy", "Explorer", "Historic", "Timeless", "Brawl", "Standard Brawl", "Commander", "Pioneer", "Modern", "Legacy", "Vintage", "Pauper")
SCRYFALL = {"Standard": "standard", "Alchemy": "alchemy", "Historic": "historic", "Timeless": "timeless", "Brawl": "brawl", "Standard Brawl": "standardbrawl",
            "Pioneer": "pioneer", "Modern": "modern", "Legacy": "legacy", "Vintage": "vintage", "Pauper": "pauper", "Explorer": "pioneer", "Commander": "commander"}
# i formati col comandante (15 nov 2026, Autore: «costruzione di mazzi brawl e commander nell'editor mazzi»): singleton, la zona Commander, l'identita' di colore.
# Brawl e Standard Brawl come su Arena (100 e 60 carte); Commander quello di carta (903.5a: 100). Le regole si leggono da Regole/MagicCompRules.txt, 903 e 702.124
SINGLETON = {"Brawl", "Standard Brawl", "Commander"}
COMANDANTE = SINGLETON
DIMENSIONE = {"Brawl": 100, "Standard Brawl": 60, "Commander": 100}       # le carte esatte, comandante compreso
BRAWL = {"Brawl", "Standard Brawl"}


def dimensione(formato):
    """Le carte del mazzo: esatte nei formati col comandante (comandante compreso), il minimo negli altri (60)."""
    return DIMENSIONE.get(formato, 60)
QUALSIASI = re.compile(r"a deck can have any number of cards named", re.I)
VERSIONE = [0]          # cresce a ogni salvataggio: chi mostra i mazzi sa quando ridisegnare
_CHIAVE = threading.Lock()


# ------------------------------------------------------------------ il file
def carica(f=None):
    f = f or FILE
    try:
        with open(f, encoding="utf-8") as g:
            d = json.load(g)
    except (OSError, ValueError):
        d = {}
    for k in SEZIONI:
        d.setdefault(k, [])
    return d


def salva(d, f=None):
    if f is None and _ACC.sola_lettura():       # All accounts: wishlist e Deck building si guardano e basta
        return
    f = f or FILE
    with _CHIAVE:
        os.makedirs(os.path.dirname(f), exist_ok=True)
        with open(f + ".tmp", "w", encoding="utf-8") as g:
            json.dump(d, g, ensure_ascii=False, indent=1)
        os.replace(f + ".tmp", f)
        VERSIONE[0] += 1


def in_wishlist(mazzo, f=None):
    """Il mazzo della wishlist uguale a questo, o None (Autore, 10 nov 2026: «un mazzo gia' in wishlist non deve avere il pulsante add to wishlist»). Uguale: la stessa
    pagina d'origine (un mazzo del meta), o le stesse carte in mazzo, sideboard e comandante. Il nome non basta: una copia cambiata nel Deck building e' un altro mazzo."""
    def carte(m):
        return tuple(tuple(sorted((n, int(q)) for n, q in (m.get(k) or {}).items() if int(q) > 0)) for k in ("lista", "side", "comandante"))
    fonte, mie = (mazzo.get("fonte") or "").strip(), carte(mazzo)
    for w in carica(f)["wish"]:
        if (fonte and fonte == (w.get("fonte") or "").strip()) or carte(w) == mie:
            return w
    return None


def aggiungi(sez, mazzo, f=None):
    """Un mazzo nuovo in «wish» o «build»: dict(nome, formato, lista, side, comandante, compagno, fonte). -> il mazzo salvato, con id e data; None con All
    accounts (sola lettura)."""
    if f is None and _ACC.sola_lettura():
        return None
    d = carica(f)
    adesso = f"{datetime.datetime.now():%Y-%m-%dT%H:%M:%S}"
    m = dict(id=uuid.uuid4().hex[:12], nome=mazzo.get("nome") or "New deck", formato=mazzo.get("formato") or "Standard",
             lista=dict(mazzo.get("lista") or {}), side=dict(mazzo.get("side") or {}), comandante=dict(mazzo.get("comandante") or {}),
             compagno=dict(mazzo.get("compagno") or {}), colori=mazzo.get("colori") or colori(mazzo.get("lista") or {}),
             fonte=mazzo.get("fonte") or "", aggiunto=adesso, modificato=adesso,
             **{k: mazzo[k] for k in ("lucchetti", "base_fatta") if k in mazzo})      # le terre col lucchetto del builder (8 nov 2026)
    d[sez].insert(0, m)
    salva(d, f)
    return m


def cambia(sez, mid, f=None, **campi):
    if f is None and _ACC.sola_lettura():
        return None
    d = carica(f)
    for m in d[sez]:
        if m["id"] == mid:
            m.update(campi)
            if "lista" in campi:
                m["colori"] = colori(m["lista"])
            m["modificato"] = f"{datetime.datetime.now():%Y-%m-%dT%H:%M:%S}"
            salva(d, f)
            return m
    return None


def togli(sez, mid, f=None):
    if f is None and _ACC.sola_lettura():
        return False
    d = carica(f)
    prima = len(d[sez])
    d[sez] = [m for m in d[sez] if m["id"] != mid]
    if len(d[sez]) != prima:
        salva(d, f)
        return True
    return False


# ------------------------------------------------------------------ la lista incollata
def leggi_lista(testo):
    """Una lista incollata -> dict(lista, side, comandante, compagno, nome). Legge il formato di Arena («Deck», «Sideboard», «Commander», «Companion»,
    «About / Name X», «4 Nome (SET) 123»), quello di MTGO e dei siti (riga vuota prima della sideboard, «SB: 2 Nome», «4x Nome»)."""
    zone = dict(lista={}, side={}, comandante={}, compagno={})
    nome, zona, visto = "", "lista", False
    titoli = {"deck": "lista", "main": "lista", "maindeck": "lista", "mainboard": "lista", "sideboard": "side", "side": "side",
              "commander": "comandante", "companion": "compagno"}
    for r in (testo or "").replace("\r", "").split("\n"):
        r = r.strip()
        if not r:
            if visto and zona == "lista":
                zona = "side"
            continue
        k = r.lower().rstrip(":")
        if k in titoli:
            zona, visto = titoli[k], False if titoli[k] == "lista" else visto
            continue
        if k == "about":
            continue
        m = re.match(r"name\s+(.+)", r, re.I)
        if m and not re.match(r"\d", r):
            nome = m.group(1).strip()
            continue
        sb = r.upper().startswith("SB:")
        m = re.match(r"(?:SB:\s*)?(\d+)\s*x?\s+(.+?)(?:\s+\([A-Za-z0-9]{2,6}\)(?:\s+\S+)?)?(?:\s+\*F\*)?$", r)
        if not m:
            continue
        n = re.sub(r"\s*/\s*(?!/)", " // ", m.group(2).strip()) if re.search(r"[^/]/[^/]", m.group(2)) else m.group(2).strip()
        z = "side" if sb else zona
        zone[z][n] = zone[z].get(n, 0) + int(m.group(1))
        if z == "lista":
            visto = True
    zone["nome"] = nome
    return zone


# ------------------------------------------------------------------ i dati di una build
def _carte_arena():
    try:
        import dati_mazzo as DM
        return DM.tabella_carte()
    except Exception:
        return {}


def tipo(nome, arena=None):
    arena = _carte_arena() if arena is None else arena
    c = arena.get(nome) or arena.get(nome.split(" // ")[0].strip())
    if c:
        return c.get("tipo") or ""
    s = PZ.carta(nome)
    return (s or {}).get("t") or ""


def e_terra(nome, arena=None):
    return nome in BASI or "Land" in tipo(nome, arena).split(" // ")[0]


def colori(lista, arena=None):
    arena = _carte_arena() if arena is None else arena
    trovati = set()
    for n in lista:
        if e_terra(n, arena):
            continue
        c = arena.get(n) or arena.get(n.split(" // ")[0].strip())
        col = (c or {}).get("colori") if c else (PZ.carta(n) or {}).get("c")
        trovati |= set(col or "")
    return "".join(k for k in "WUBRG" if k in trovati)


def iper(N, K, n, k):
    """P(almeno k successi in n pescate da N carte con K successi)."""
    if n > N:
        n = N
    tot = math.comb(N, n)
    return sum(math.comb(K, i) * math.comb(N - K, n - i) for i in range(k, min(K, n) + 1)) / tot if tot else 0.0


_POOL = {"chiave": None, "d": None}


def pool_standard():
    """(nomi legali in Standard, nomi banditi) dalle stesse fonti di Regole/controlla_legalita.py. Riletti solo quando i file cambiano (7 nov 2026: il builder li
    rileggeva a ogni carta)."""
    fp, fb = os.path.join(RADICE, "Regole", "standard_carte.json"), os.path.join(RADICE, "Regole", "Ban_Standard.md")
    try:
        chiave = (os.path.getmtime(fp), os.path.getmtime(fb))
    except OSError:
        return None, set()
    if chiave != _POOL["chiave"]:
        _POOL.update(chiave=chiave, d=_pool_standard())
    pool, ban = _POOL["d"]
    return (set(pool) if pool is not None else None), set(ban)


def _pool_standard():
    try:
        pool ={c["name"].lower() for c in json.load(open(os.path.join(RADICE, "Regole", "standard_carte.json"), encoding="utf-8"))}
        pool |= {n.split(" // ")[0] for n in pool}
        ban = {re.sub(r"\*\*", "", m).lower() for m in re.findall(r"- \*\*([^*]+)\*\*", open(os.path.join(RADICE, "Regole", "Ban_Standard.md"), encoding="utf-8").read())}
        return pool, ban
    except (OSError, ValueError):
        return None, set()


def legalita(lista, side, formato, comandante=None, compagno=None, arena=None):
    """-> [problema] (vuoto = legale). Carte che non esistono nel formato, bandite, troppe copie, troppo poche carte."""
    arena = _carte_arena() if arena is None else arena
    tutte = {}
    for z in (lista, side, comandante or {}, compagno or {}):
        for n, q in z.items():
            tutte[n] = tutte.get(n, 0) + q
    problemi = []
    pool, ban = pool_standard() if formato == "Standard" else (None, set())
    chiave = SCRYFALL.get(formato)
    for n, q in sorted(tutte.items()):
        if n in BASI:
            continue
        s = PZ.carta(n)
        if formato == "Standard" and pool is not None:
            low = n.lower()
            if low not in pool and low.split(" // ")[0] not in pool:
                problemi.append(f"not in Standard: {n}")
                continue
            if low in ban or low.split(" // ")[0] in ban:
                problemi.append(f"banned: {n}")
                continue
        elif formato == "Alchemy" and n.startswith("A-"):
            pass        # le carte ribilanciate esistono solo su Arena, in Alchemy e Historic
        elif s is None:
            if not (arena.get(n) or arena.get(n.split(" // ")[0].strip())):
                problemi.append(f"unknown card: {n}")
            continue
        elif chiave and chiave not in s["l"].split() and chiave not in s["r"].split():
            problemi.append(f"not legal in {formato}: {n}")
            continue
        if formato == "Explorer" and not (arena.get(n) or arena.get(n.split(" // ")[0].strip())):
            problemi.append(f"not on Arena: {n}")
        limite = 1 if formato in SINGLETON or (s and chiave and chiave in s["r"].split()) else 4
        c = arena.get(n) or {}
        if QUALSIASI.search(c.get("testo") or ""):
            limite = 10 ** 6
        if q > limite:
            problemi.append(f"{q} copies of {n} (max {limite})")
    minimo = dimensione(formato)
    carte = sum(lista.values()) + sum((comandante or {}).values())
    if formato in SINGLETON:
        if carte != minimo:
            problemi.append(f"{carte} cards ({minimo} with the commander)")
        problemi += problemi_comandante(lista, comandante or {}, formato, arena, compagno=compagno)
    elif carte < minimo:
        problemi.append(f"only {carte} cards (min {minimo})")
    if formato not in SINGLETON and sum(side.values()) > 15:
        problemi.append(f"sideboard of {sum(side.values())} (max 15)")
    return problemi


def _info(nome, arena):
    """(tipo, identita') della carta: da Scryfall (carte.json, VERSIONE_CARTE 2), se no da Arena (il tipo; per l'identita' i colori della carta, che per le terre
    sono gia' l'identita': un'approssimazione per le sole carte di Arena, dichiarata)."""
    s = PZ.carta(nome)
    c = arena.get(nome) or arena.get(nome.split(" // ")[0].strip()) or {}
    t = (s or {}).get("t") or c.get("tipo") or ""
    i = (s or {}).get("i") if s and "i" in s else c.get("colori") or ""
    return t, i


def puo_comandare(nome, formato, arena=None):
    """Puo' essere il comandante da solo? -> (si/no, perche'). Commander (903.3): leggendaria e creatura, Vehicle o Spacecraft, o il testo «can be your commander»
    (903.3a). Brawl (903.12c): anche un planeswalker. Un Background solo accanto a chi ha «choose a Background» (702.124k)."""
    arena = _carte_arena() if arena is None else arena
    t, _i = _info(nome, arena)
    s = PZ.carta(nome) or {}
    davanti = t.split(" // ")[0]
    if "a" in (s.get("k") or ""):
        return True, "its text says it can be your commander"
    if "Legendary" not in davanti:
        return False, f"{nome} is not legendary"
    if "g" in (s.get("k") or ""):
        return False, f"{nome} is a Background: it needs a commander with «Choose a Background»"
    tipi = ["Creature", "Vehicle", "Spacecraft"] + (["Planeswalker"] if formato in BRAWL else [])
    if any(x in davanti for x in tipi):
        return True, ""
    return False, f"{nome} is not a creature" + (" or a planeswalker" if formato in BRAWL else "")


def coppia_ok(a, b):
    """Due comandanti insieme (702.124): tutti e due partner; lo stesso partner—[testo]; partner with l'uno dell'altro; choose a Background e un Background;
    Doctor's companion e un Time Lord Doctor. Le varianti non si mescolano (702.124f). -> (si/no, perche')."""
    sa, sb = PZ.carta(a) or {}, PZ.carta(b) or {}
    ka, kb, pa, pb = sa.get("k") or "", sb.get("k") or "", sa.get("pa") or "", sb.get("pa") or ""
    if "p" in ka and "p" in kb:
        return True, "partner"
    if pa.startswith("text:") and pa == pb:
        return True, "partner—" + pa[5:]
    if pa == "with:" + b.lower() and pb == "with:" + a.lower():
        return True, "partner with"
    for x, y in ((ka, kb), (kb, ka)):
        if "c" in x and "g" in y:
            return True, "choose a Background"
        if "d" in x and "t" in y:
            return True, "Doctor's companion"
    return False, f"{a} and {b} can't be commanders together: they need matching partner abilities"


def identita_comandante(comandante, arena=None):
    """L'identita' di colore del mazzo: quella dei comandanti insieme (903.4, 702.124c), in WUBRG."""
    arena = _carte_arena() if arena is None else arena
    tutti = "".join(_info(n, arena)[1] for n in comandante)
    return "".join(k for k in "WUBRG" if k in tutti)


def problemi_comandante(lista, comandante, formato, arena=None, compagno=None):
    """I problemi dei formati col comandante: nessun comandante, troppi, chi non puo' esserlo, due che non vanno insieme, le carte fuori dalla sua identita'
    di colore (903.5c; le terre base comprese: Plains e' bianca). Con un comandante incolore nel Brawl le basi di un tipo sono libere (903.12e)."""
    arena = _carte_arena() if arena is None else arena
    com = [n for n, q in comandante.items() if q > 0]
    out = []
    if not com:
        return ["no commander: put a legendary creature" + (" or planeswalker" if formato in BRAWL else "") + " in Commander"]
    if sum(comandante.values()) > 2 or len(com) > 2:
        out.append(f"{sum(comandante.values())} commanders (max 2, with partner)")
    elif len(com) == 2:
        ok, perche = coppia_ok(com[0], com[1])
        if not ok:
            out.append(perche)
        for n in com:       # in coppia un Background va bene (choose a Background); gli altri devono poter comandare
            if not ok or "g" not in ((PZ.carta(n) or {}).get("k") or ""):
                si, perche_ = puo_comandare(n, formato, arena)
                if not si:
                    out.append(f"not a commander: {perche_}")
    else:
        si, perche_ = puo_comandare(com[0], formato, arena)
        if not si:
            out.append(f"not a commander: {perche_}")
    ident = set(identita_comandante(com, arena))
    fuori = []
    for n, q in sorted({**lista, **(compagno or {})}.items()):
        if q <= 0 or (not ident and formato in BRAWL and n in BASI):
            continue
        extra = set(_info(n, arena)[1]) - ident
        if extra:
            fuori.append(f"{n} ({''.join(k for k in 'WUBRG' if k in extra)})")
    if fuori:
        nomi_c = " + ".join(com)
        out.append(f"outside {nomi_c}'s colors ({''.join(sorted(ident, key='WUBRG'.index)) or 'colorless'}): " + ", ".join(fuori[:8])
                   + (f" +{len(fuori) - 8} more" if len(fuori) > 8 else ""))
    return out


def mana(lista, arena=None):
    """Le terre: quante, in curva (sul play: T2 = 8 carte viste) e nella mano iniziale; le fonti di ogni colore e i simboli che le magie chiedono."""
    arena = _carte_arena() if arena is None else arena
    N = sum(lista.values())
    K = sum(q for n, q in lista.items() if e_terra(n, arena))
    curva = {t: iper(N, K, 6 + t, t) for t in (1, 2, 3, 4, 5)} if N else {}
    mano = {k: (iper(N, K, 7, k) - iper(N, K, 7, k + 1)) for k in range(8)} if N else {}
    fonti, simboli = {}, {}
    for n, q in lista.items():
        if e_terra(n, arena):
            s = PZ.carta(n)
            prod = (s or {}).get("p") or {"Plains": "W", "Island": "U", "Swamp": "B", "Mountain": "R", "Forest": "G"}.get(n.replace("Snow-Covered ", ""), "")
            for k in prod:
                if k in "WUBRG":
                    fonti[k] = fonti.get(k, 0) + q
        else:
            c = arena.get(n) or arena.get(n.split(" // ")[0].strip())
            costo = " ".join(c.get("costo") or []) if c else (PZ.carta(n) or {}).get("m") or ""
            for k in "WUBRG":
                if k in costo:
                    simboli[k] = simboli.get(k, 0) + q
    return dict(carte=N, terre=K, curva=curva, mano=mano, fonti=fonti, simboli=simboli)


def simile(lista, mazzi):
    """Il mazzo del meta piu' vicino: -> (mazzo, quota di carte uguali) o (None, 0). Si contano le copie in comune fuori dalle basi."""
    mia = {n: q for n, q in lista.items() if n not in BASI}
    tot = sum(mia.values())
    meglio, qm = None, 0.0
    for m in mazzi or []:
        loro = {n: q for n, q in (m.get("lista") or {}).items() if n not in BASI}
        if not loro or not tot:
            continue
        comune = sum(min(q, loro.get(n, 0)) for n, q in mia.items())
        x = comune / max(tot, sum(loro.values()))
        if x > qm:
            meglio, qm = m, x
    return meglio, qm


def prova():
    import tempfile
    casi = []
    arena = {"Lightning Strike": dict(tipo="Instant", colori="R", costo=["1", "R"], testo=""), "Rat Colony": dict(tipo="Creature — Rat", colori="B", costo=["1", "B"],
             testo="A deck can have any number of cards named Rat Colony."), "Sacred Foundry": dict(tipo="Land — Mountain Plains", colori="", costo=[], testo="")}
    a = leggi_lista("About\nName Prova Rossa\n\nDeck\n4 Lightning Strike (FDN) 152\n20 Mountain\n\nSideboard\n2 Duress\n")
    casi.append(("Arena: nome, mazzo e sideboard, senza il set", a["nome"] == "Prova Rossa" and a["lista"] == {"Lightning Strike": 4, "Mountain": 20} and a["side"] == {"Duress": 2}))
    b = leggi_lista("4 Lightning Strike\n4x Shock\n\n2 Duress\nSB: 1 Negate\n")
    casi.append(("MTGO e siti: riga vuota, 4x e SB:", b["lista"] == {"Lightning Strike": 4, "Shock": 4} and b["side"] == {"Duress": 2, "Negate": 1}))
    c = leggi_lista("Commander\n1 Kaalia of the Vast\n\nDeck\n1 Fire/Ice\n")
    casi.append(("il comandante e le split col doppio slash", c["comandante"] == {"Kaalia of the Vast": 1} and c["lista"] == {"Fire // Ice": 1}))
    casi.append(("una riga che non e' una carta non entra (prova negativa)", leggi_lista("Deck\nciao\n4 Shock")["lista"] == {"Shock": 4}))
    m = mana({"Lightning Strike": 36, "Mountain": 24}, arena)
    casi.append(("terre e curva esatte", m["terre"] == 24 and abs(m["curva"][1] - (1 - math.comb(36, 7) / math.comb(60, 7))) < 1e-12 and abs(sum(m["mano"].values()) - 1) < 1e-12))
    casi.append(("fonti e simboli", m["fonti"].get("R") == 24 and m["simboli"].get("R") == 36))
    casi.append(("la terra doppia conta per due colori", mana({"Sacred Foundry": 4}, arena)["fonti"] == {"W": 4, "R": 4} or PZ.carta("Sacred Foundry") is None))
    fw = os.path.join(tempfile.mkdtemp(), "wish.json")
    aggiungi("wish", dict(nome="Rossa", lista={"Shock": 4, "Mountain": 20}, side={"Duress": 2}, fonte="https://esempio/rossa"), f=fw)
    casi.append(("gia' in wishlist: stesse carte con un altro nome, o la stessa pagina d'origine",
                 in_wishlist(dict(nome="Rossa (lab)", lista={"Mountain": 20, "Shock": 4}, side={"Duress": 2}), f=fw) is not None
                 and in_wishlist(dict(nome="Altro", lista={"Shock": 1}, fonte="https://esempio/rossa"), f=fw) is not None))
    casi.append(("negativa: una copia cambiata non e' in wishlist, ne' una con un'altra sideboard",
                 in_wishlist(dict(nome="Rossa", lista={"Shock": 3, "Mountain": 21}, side={"Duress": 2}), f=fw) is None
                 and in_wishlist(dict(nome="Rossa", lista={"Shock": 4, "Mountain": 20}), f=fw) is None))
    l1 = legalita({"Lightning Strike": 5, "Mountain": 20}, {}, "Modern", arena=arena)
    casi.append(("la quinta copia e le poche carte", any("5 copies" in x for x in l1) and any("only 25" in x for x in l1)))
    casi.append(("le carte senza limite", not any("Rat Colony" in x for x in legalita({"Rat Colony": 40, "Swamp": 20}, {}, "Modern", arena=arena))))
    casi.append(("singleton nel Brawl", any("max 1" in x for x in legalita({"Lightning Strike": 2}, {}, "Brawl", arena=arena))))
    # i formati col comandante (15 nov 2026): le carte di Scryfall vere (carte.json); senza il file le prove saltano dette
    if (PZ.carta("Atraxa, Praetors' Voice") or {}).get("i"):
        casi.append(("Commander: 100 carte, singleton, nella lista dei formati", "Commander" in FORMATI and dimensione("Commander") == 100 and "Commander" in SINGLETON))
        casi.append(("Atraxa comanda; Teferi, Temporal Archmage («can be your commander») anche; Jace, Wielder of Mysteries solo nel Brawl",
                     puo_comandare("Atraxa, Praetors' Voice", "Commander", arena)[0] and puo_comandare("Teferi, Temporal Archmage", "Commander", arena)[0]
                     and not puo_comandare("Jace, Wielder of Mysteries", "Commander", arena)[0] and puo_comandare("Jace, Wielder of Mysteries", "Brawl", arena)[0]))
        casi.append(("negativa: Sol Ring non e' leggendaria, Raised by Giants (Background) non comanda da sola", not puo_comandare("Sol Ring", "Commander", arena)[0]
                     and not puo_comandare("Raised by Giants", "Commander", arena)[0]))
        casi.append(("le coppie: partner, partner with fra loro, Background, Doctor's companion",
                     coppia_ok("Thrasios, Triton Hero", "Tymna the Weaver")[0] and coppia_ok("Pir, Imaginative Rascal", "Toothy, Imaginary Friend")[0]
                     and coppia_ok("Wilson, Refined Grizzly", "Raised by Giants")[0] and coppia_ok("Clara Oswald", "The Thirteenth Doctor")[0]))
        casi.append(("negativa: partner con partner with non va (702.124f), due leggendarie qualsiasi nemmeno",
                     not coppia_ok("Thrasios, Triton Hero", "Toothy, Imaginary Friend")[0] and not coppia_ok("Atraxa, Praetors' Voice", "Kenrith, the Returned King")[0]))
        pa_ = problemi_comandante({"Lightning Bolt": 1, "Counterspell": 1, "Forest": 10, "Mountain": 3}, {"Thrasios, Triton Hero": 1}, "Commander", arena)
        casi.append(("fuori dai colori di Thrasios (UG): Lightning Bolt e Mountain, non Counterspell ne' Forest", any("outside" in x and "Lightning Bolt" in x
                     and "Mountain" in x and "Counterspell" not in x and "Forest (" not in x for x in pa_)))
        casi.append(("negativa: senza comandante lo dice; con due che non vanno insieme pure", problemi_comandante({}, {}, "Commander", arena)[0].startswith("no commander")
                     and any("together" in x for x in problemi_comandante({}, {"Atraxa, Praetors' Voice": 1, "Kenrith, the Returned King": 1}, "Commander", arena))))
        casi.append(("Brawl con un comandante incolore: le basi di un tipo sono libere (903.12e)", not problemi_comandante({"Island": 30}, {"Karn, Living Legacy": 1}, "Brawl", arena)
                     or not any("outside" in x for x in problemi_comandante({"Island": 30}, {"Karn, Living Legacy": 1}, "Brawl", arena))))
        lg = legalita({"Counterspell": 1, "Island": 98}, {}, "Commander", comandante={"Thrasios, Triton Hero": 1}, arena=arena)
        casi.append(("un mazzo Commander legale di 100 carte non ha problemi", lg == []))
    else:
        print("(le prove del comandante saltate: manca Dati/scryfall/carte.json nuovo)")
    mm = [dict(nome="A", lista={"Lightning Strike": 4, "Shock": 4, "Mountain": 20}), dict(nome="B", lista={"Duress": 4, "Swamp": 20})]
    v, q = simile({"Lightning Strike": 4, "Shock": 2, "Mountain": 22}, mm)
    casi.append(("il mazzo simile", v["nome"] == "A" and abs(q - 6 / 8) < 1e-9))
    casi.append(("senza meta niente simile", simile({"Shock": 4}, []) == (None, 0.0)))
    t = os.path.join(tempfile.mkdtemp(), "salvati.json")
    x = aggiungi("wish", dict(nome="W", lista={"Shock": 4}), t)
    y = aggiungi("build", dict(nome="B", lista={"Shock": 4}), t)
    cambia("build", y["id"], t, lista={"Duress": 4}, nome="B2")
    d = carica(t)
    casi.append(("salva, cambia, toglie", d["wish"][0]["id"] == x["id"] and d["build"][0]["nome"] == "B2" and d["build"][0]["lista"] == {"Duress": 4}
                 and togli("wish", x["id"], t) and not carica(t)["wish"] and not togli("wish", "nessuno", t)))
    ok = True
    for nome, esito in casi:
        print(("OK   " if esito else "ROSSO") + " " + nome)
        ok &= bool(esito)
    print(f"{sum(bool(e) for _n, e in casi)}/{len(casi)}")
    return ok


if __name__ == "__main__":
    if "--prova" in sys.argv:
        sys.exit(0 if prova() else 1)
    d = carica()
    print(f"wishlist {len(d['wish'])}, build {len(d['build'])}")
