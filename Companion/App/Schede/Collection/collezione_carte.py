"""La collezione di Autore, carta per carta, per la scheda Collection (Autore, 5 nov 2026: «riusciamo a creare una nuova scheda che raccoglie la collezione delle carte
possedute, con menu articolato per fare ricerca di carte dalla collezione?»). Ci sono anche le carte di Arena che non ha, con 0 copie (6 nov 2026: «aggiungiamo anche quelle non
possedute e mettiamo un filtro»): tutte tranne pedine, seconde facce e le carte che esistono solo nei Cube e nel Momir (DigitalReleaseSet CUBE-.., MOMIR). Il database non ha un campo
che dica se una carta si puo' ottenere: quella lista viene da come sono divise le stampe, e qualche carta da evento potrebbe esserci lo stesso.

Le copie vengono da Collezione/collezione.json (Untapped, per grpid). Tutto il resto dal database delle carte di Arena, Dati/untapped/arena_cards/cards.json e loc_en.json: nome,
set, rarita', costo, colori, tipo, testo. Una carta sta una volta sola, con le copie di tutte le stampe sommate: «sets» dice le copie per set. Le terre hanno come colore l'identita'.
Standard: nel pool di Regole/standard_carte.json e fuori da Regole/Ban_Standard.md.

Le carte di Alchemy non ci sono (Autore, 5 nov 2026: «le alchemy non le vogliamo»): i set Y.., Alchemy Horizons e le versioni ribilanciate A-. La carta di partenza di una A- resta.
La ricerca guarda sempre nome, tipo e testo, facce dietro comprese (stesso giorno: «la finestra di ricerca ci aiuta a trovare anche inserendo parole chiave del testo delle carte?»).

Legge soltanto. Si rifa' quando cambia uno dei file (mtime).

    py -I -X utf8 Companion/App/Schede/Collection/collezione_carte.py --prova
"""
import os, sys
_casa = os.path.dirname(os.path.abspath(__file__))      # si sale fino a percorsi.py, che mette nel sys.path tutte le cartelle del Companion
while not os.path.isfile(os.path.join(_casa, "percorsi.py")):
    _casa = os.path.dirname(_casa)
if _casa not in sys.path:
    sys.path.insert(0, _casa)
import percorsi  # noqa: E402
import json, re
import risorse as RS

ROOT = percorsi.ROOT
import account as _ACC  # noqa: E402
F_COLL = _ACC.lega(globals(), "F_COLL", "collezione.json", autore=os.path.join(ROOT, "Collezione", "collezione.json"))     # per account nell'app pubblica
F_CARTE = os.path.join(ROOT, "Dati", "untapped", "arena_cards", "cards.json")
F_LOC = os.path.join(ROOT, "Dati", "untapped", "arena_cards", "loc_en.json")
F_STD = os.path.join(ROOT, "Regole", "standard_carte.json")
F_BAN = os.path.join(ROOT, "Regole", "Ban_Standard.md")
RARITA = {5: "M", 4: "R", 3: "U", 2: "C", 1: "C", 0: "C"}      # 1: su Arena sono le terre, anche le doppie comuni
PESO_RARITA = dict(M=4, R=3, U=2, C=1, L=0)
COLORI = {1: "W", 2: "U", 3: "B", 4: "R", 5: "G"}
TIPI = ("Creature", "Instant", "Sorcery", "Enchantment", "Artifact", "Planeswalker", "Land")
ORDINI = ("Color", "Name", "Mana value", "Rarity", "Copies", "Newest set")      # Color e' il default (8 nov 2026)
COPIE = ("Any", "1", "2", "3", "4+", "Under 4")
MODI = ("Any of these", "Exactly these", "Only these")
MOSTRA = ("All cards", "Owned", "Not owned")
_CACHE = {"chiave": None, "d": None}
import threading  # noqa: E402
_LUCCHETTO = threading.Lock()      # carica() da due fili: il secondo aspetta il caricamento del primo, non lo rifa'


def precarica():
    """Legge il database delle carte in un filo (11 nov 2026, sessione Magic 13): all'avvio la Meta lo chiedeva prima di comparire, 0,9 s di finestra ferma."""
    threading.Thread(target=carica, daemon=True).start()


def simboli(costo):
    """«o2oUo(U/R)» -> ["2", "U", "U/R"]."""
    return [t.strip("()") for t in re.findall(r"o(\([^)]*\)|[^o()]+)", costo or "")]


def pulisci(testo):
    """Il testo di Arena senza i tag e con i simboli come in Oracle: serve solo a cercarci dentro."""
    return re.sub(r"\s+", " ", re.sub(r"</?[^>]+>", "", (testo or "").replace("{o", "{").replace("\u2019", "'"))).strip()


def alchemy(c):
    """Una carta del database di Arena che esiste solo in Alchemy. Non basta IsDigitalOnly: lo hanno anche le carte del set dei principianti (ANB)."""
    return bool(c.get("IsRebalanced")) or bool(re.fullmatch(r"Y\d\d", c.get("set") or "")) or (bool(c.get("IsDigitalOnly")) and c.get("set") == "HBG")


def collezionabile(c):
    """Una stampa che puo' stare in collezione. Vedi la testa del file."""
    return not (c.get("isToken") or c.get("isSecondaryCard") or alchemy(c) or re.match(r"CUBE|MOMIR", c.get("DigitalReleaseSet") or ""))


def _leggi():
    try:
        col = json.load(open(F_COLL, encoding="utf-8"))
    except (OSError, ValueError):       # un account nuovo dell'app pubblica: senza scarico, la collezione e' quella dei log
        col = {"cards": []}
    carte = {c["grpid"]: c for c in json.load(open(F_CARTE, encoding="utf-8"))}
    loc = {e["id"]: e["text"] for e in json.load(open(F_LOC, encoding="utf-8"))}
    try:
        std = {c["name"] for c in json.load(open(F_STD, encoding="utf-8"))}
        std |= {n.split(" // ")[0].strip() for n in std}
    except (OSError, ValueError):
        std = set()
    try:
        ban = {m.strip() for m in re.findall(r"^- \*\*([^*]+)\*\*", open(F_BAN, encoding="utf-8").read(), re.M)}
    except OSError:
        ban = set()
    testi = lambda c: " ".join(loc.get(a.get("TextId")) or "" for a in c.get("abilities") or [])
    per_nome, ignote, tolte = {}, 0, 0

    def voce(c, nome):
        v = per_nome.get(nome)
        if v is None:
            tipo = loc.get(c.get("cardTypeTextId")) or ""
            sotto = loc.get(c.get("subtypeTextId")) or ""
            terra = "Land" in tipo
            colori = c.get("colors") or (c.get("colorIdentity") if terra else None) or []
            v = per_nome[nome] = dict(nome=nome, copie=0, sets={}, r="L" if "Basic" in tipo else RARITA.get(c.get("rarity"), "C"), costo=simboli(c.get("castingcost")), cmc=c.get("cmc") or 0,
                                      colori="".join(k for i, k in COLORI.items() if i in colori), tipo=f"{tipo} — {sotto}" if sotto else tipo,
                                      testo=pulisci(testi(c)), pt=f"{c['power']}/{c['toughness']}" if c.get("power") else "",
                                      standard=(nome in std or nome.split(" // ")[0].strip() in std) and nome not in ban,
                                      ban_std=nome in ban or nome.split(" // ")[0].strip() in ban)      # bandita nello Standard: in rosso nella Collection (10 nov 2026)
            facce = [carte[g] for g in c.get("linkedFaces") or [] if g in carte]      # la faccia dietro si cerca con la sua carta
            v["cerca"] = " ".join([f"{nome} {v['tipo']}"] + [f"{loc.get(f.get('titleId')) or ''} {loc.get(f.get('cardTypeTextId')) or ''} {loc.get(f.get('subtypeTextId')) or ''}" for f in facce]).lower()
            v["cerca_testo"] = " ".join([v["testo"]] + [pulisci(testi(f)) for f in facce]).lower()
        return v

    import collezione_viva as CV       # lo scarico di Untapped piu' le carte dei log dopo lo scarico (8 nov 2026)
    for x in CV.righe() or col.get("cards") or []:
        c = carte.get(x["grpid"])
        nome = loc.get(c.get("titleId")) if c else None
        if not nome:
            ignote += x.get("quantity", 0)
            continue
        if alchemy(c):
            tolte += x.get("quantity", 0)
            continue
        q, s = x.get("quantity", 0), c.get("set") or "?"
        v = voce(c, nome)
        v["copie"] += q
        v["sets"][s] = v["sets"].get(s, 0) + q
    for c in carte.values():      # poi tutto il resto, a 0 copie
        nome = loc.get(c.get("titleId"))
        if nome and collezionabile(c):
            voce(c, nome)["sets"].setdefault(c.get("set") or "?", 0)
    return dict(carte=list(per_nome.values()), ignote=ignote, alchemy=tolte, quando=col.get("last_updated") or "")


def carica():
    """-> dict(carte, ignote, alchemy, quando); lo stesso oggetto finche' i file non cambiano."""
    try:
        import collezione_viva as CV
        st_ = CV.stato()
        chiave = tuple(os.path.getmtime(f) for f in (F_COLL, F_CARTE, F_LOC)) + ((st_["soglia"], len(st_["piu"])) if st_ else ())
    except OSError:
        return None
    with _LUCCHETTO:
        if chiave != _CACHE["chiave"]:
            _CACHE.update(chiave=chiave, d=_leggi())
        return _CACHE["d"]


def per_capsule(d):
    """{nome: (costo, colori, mana, rarita')} per capsule.aggiungi: le capsule conoscono cosi' anche le carte fuori dallo Standard."""
    nomi = dict(M="mythic", R="rare", U="uncommon", C="common", L="common")
    return {c["nome"]: ("".join("{" + t + "}" for t in c["costo"]), c["colori"], c["cmc"], nomi[c["r"]]) for c in d["carte"]}


def elenco_set(d):
    """I set della collezione per data di uscita, dal piu' nuovo; quelli senza data in fondo, per codice."""
    return RS.ordina_set(sorted({s for c in d["carte"] for s in c["sets"]}))


def parole_di(testo):
    """Le parole cercate, in minuscolo; fra virgolette una frase intera."""
    return [x for x in (a or b.strip('"') for a, b in re.findall(r'"([^"]+)"|(\S+)', testo.lower().replace("\u2019", "'"))) if x]


def nel_testo(p):
    """Compilata: p all'inizio di una parola del testo, cosi' «ward» non trova «toward»; «tokens» trova anche «token». Il segno davanti resta buono: «-5/-0», «+1/+1»."""
    if len(p) > 3 and p.endswith("s") and not p.endswith("ss"):
        p = p[:-1]
    return re.compile(r"(?<![a-z0-9])" + re.escape(p))


def copie_in(c, sets=()):
    """Le copie della carta nei set scelti; senza set, tutte."""
    return sum(c["sets"].get(x, 0) for x in sets) if sets else c["copie"]


def filtra(carte, testo="", sets=(), standard=False, colori=(), modo=MODI[0], rarita=(), tipi=(), costi=(), copie="Any", mostra=MOSTRA[0]):
    """Le carte che passano. testo: ogni parola deve stare nel nome, nel tipo o nel testo della carta. costi: 7 vuol dire 7 o piu'. colori: W U B R G e C per le incolori.
    sets: la carta sta in almeno uno; copie e mostra contano le copie di quei set sommate."""
    sets = set(sets)
    parole = [(p, nel_testo(p)) for p in parole_di(testo)]
    colori, rarita, tipi, costi = set(colori), set(rarita), set(tipi), set(costi)
    tinte = colori - {"C"}
    out = []
    for c in carte:
        if sets and not sets & c["sets"].keys():
            continue
        if standard and not c["standard"]:
            continue
        if parole and not all(p in c["cerca"] or r.search(c["cerca_testo"]) for p, r in parole):
            continue
        if rarita and c["r"] not in rarita:
            continue
        if tipi and not any(t in c["tipo"] for t in tipi):
            continue
        if costi and min(int(c["cmc"]), 7) not in costi:
            continue
        q = copie_in(c, sets)
        if (mostra == MOSTRA[1] and not q) or (mostra == MOSTRA[2] and q):
            continue
        if (copie == "4+" and q < 4) or (copie == "Under 4" and q >= 4) or (copie in ("1", "2", "3") and q != int(copie)):
            continue
        if colori:
            mie = set(c["colori"])
            if modo == MODI[1]:       # esattamente questi
                ok = mie == tinte and ("C" in colori or mie)
            elif modo == MODI[2]:     # solo questi: giocabile con questi colori
                ok = mie <= tinte and (mie or "C" in colori)
            else:                     # almeno uno di questi
                ok = bool(mie & tinte) or ("C" in colori and not mie)
            if not ok:
                continue
        out.append(c)
    return out


def ordina(carte, ordine="Name", testo=""):
    """Per nome, con la ricerca testo: prima chi ha le parole come parole del nome o del tipo: «ward» non mette in cima Angelic Reward.
    «Color» (Autore, 8 nov 2026: «che le collezioni vengano mostrate prima in ordine di colore e per ogni colore in ordine di mana cost, terre sempre alla fine di
    ogni colore»): bianco, blu, nero, rosso, verde, poi le multicolori e le incolori, come in Arena; dentro ogni colore per costo di mana, poi il nome, e le terre in
    fondo al loro colore (il colore di una terra e' quello che produce: le basi col loro, le doppie fra le multicolori, le incolori fra le incolori)."""
    if ordine == "Color":
        parole = [nel_testo(p) for p in parole_di(testo)]

        def gruppo(c):
            col = [k for k in "WUBRG" if k in (c.get("colori") or "")]
            return "WUBRG".index(col[0]) if len(col) == 1 else 5 if col else 6
        return sorted(carte, key=lambda c: (not all(r.search(c["cerca"]) for r in parole), gruppo(c), "Land" in (c.get("tipo") or ""), c["cmc"], c["nome"]))
    if ordine == "Mana value":
        return sorted(carte, key=lambda c: (c["cmc"], c["nome"]))
    if ordine == "Rarity":
        return sorted(carte, key=lambda c: (-PESO_RARITA[c["r"]], c["nome"]))
    if ordine == "Copies":
        return sorted(carte, key=lambda c: (-c["copie"], c["nome"]))
    if ordine == "Newest set":
        date = RS.date_uscita()
        return sorted(sorted(carte, key=lambda c: c["nome"]), key=lambda c: max((date.get(s, "") for s in c["sets"]), default=""), reverse=True)
    parole = [nel_testo(p) for p in parole_di(testo)]
    return sorted(carte, key=lambda c: (not all(r.search(c["cerca"]) for r in parole), c["nome"]))


def riassunto(carte, sets=()):
    """Quante carte diverse, quante copie, e quante diverse per rarita'."""
    r = dict(uniche=len(carte), copie=sum(copie_in(c, sets) for c in carte), M=0, R=0, U=0, C=0)
    for c in carte:
        if c["r"] in r:
            r[c["r"]] += 1
    return r


def prova():
    d = carica()
    import collezione_viva as CV       # lo scarico piu' le carte dei log dopo lo scarico (8 nov 2026)
    try:
        tot = sum(x.get("quantity", 0) for x in json.load(open(F_COLL, encoding="utf-8")).get("cards") or [])
    except (OSError, ValueError):
        tot = 0
    tot += len((CV.stato() or {}).get("piu") or [])
    C = d["carte"]
    per = {c["nome"]: c for c in C}
    sah = per.get("Saheeli, Jewel of Avishkar")
    prova_c = [dict(nome="A", copie=4, sets={"FRA": 3, "DFT": 1}, r="R", costo=[], cmc=2, colori="UR", tipo="Creature — Elf", testo="", cerca="a creature — elf", cerca_testo="draw a card", standard=True),
               dict(nome="B", copie=1, sets={"DFT": 1}, r="C", costo=[], cmc=9, colori="", tipo="Artifact", testo="", cerca="b artifact", cerca_testo="", standard=False),
               dict(nome="C", copie=2, sets={"FRA": 2}, r="M", costo=[], cmc=1, colori="U", tipo="Instant", testo="", cerca="c instant", cerca_testo="", standard=True)]
    nomi = lambda l: "".join(c["nome"] for c in l)
    vere = lambda t: {c["nome"] for c in filtra(C, t)}
    prova_z = dict(prova_c[1], nome="Z", cerca="z draw", cerca_testo="")
    prova_0 = prova_c + [dict(prova_c[1], nome="N", copie=0, sets={"FRA": 0, "DFT": 0})]
    casi = [("le copie tornano col file", sum(c["copie"] for c in C) + d["ignote"] + d["alchemy"] == tot),
            ("ci sono le carte che non hai, a 0 copie", any(c["copie"] == 0 for c in C) and sum(c["copie"] > 0 for c in C) < len(C) / 2),
            ("una carta che non hai ha il suo set", all(c["sets"] for c in C)),
            ("niente pedine", not any("Token" in c["tipo"] for c in C)),
            ("niente carte solo da Cube", not {"True-Name Nemesis", "Mana Crypt"} & set(per)),
            ("le seconde facce non sono carte", "Stomp" not in per and "Seed Suture" not in per),
            ("Owned", nomi(filtra(prova_0, mostra="Owned")) == "ABC"),
            ("Not owned", nomi(filtra(prova_0, mostra="Not owned")) == "N"),
            ("Not owned dentro un set", nomi(filtra(prova_0, sets=["FRA"], mostra="Not owned")) == "N"),
            ("nessuna versione A-", not any(c["nome"].startswith("A-") for c in C)),
            ("nessun set di Alchemy", not any(re.fullmatch(r"Y\d\d", s) for c in C for s in c["sets"]) and d["alchemy"] > 0),
            ("le carte dei principianti non sono Alchemy", any("ANB" in c["sets"] for c in C)),
            ("ogni copia ha il suo set", all(sum(c["sets"].values()) == c["copie"] for c in C)),
            ("una carta vera ha costo, colori e tipo", sah is not None and sah["costo"] == ["2", "U", "R"] and sah["colori"] == "UR" and "Creature" in sah["tipo"]),
            ("il costo ibrido si legge", simboli("o2o(U/R)oG") == ["2", "U/R", "G"]),
            ("una terra base ha il suo colore", all(c["colori"] for c in C if c["nome"] in ("Island", "Plains"))),
            ("una terra doppia comune e' comune", all(c["r"] == "C" for c in C if c["nome"] == "Abraded Bluffs")),
            ("una base non conta fra le comuni", all(c["r"] == "L" for c in C if c["nome"] == "Island")),
            ("una bandita non e' Standard", not any(c["standard"] and c["nome"] in ("Screaming Nemesis", "Up the Beanstalk") for c in C)),
            ("il nome cerca anche il tipo", nomi(filtra(prova_c, "elf")) == "A"),
            ("il testo della carta si cerca sempre", nomi(filtra(prova_c, "draw")) == "A"),
            ("nome e testo insieme", nomi(filtra(prova_c, "elf draw")) == "A"),
            ("nel testo conta l'inizio della parola", nomi(filtra(prova_c, "ard")) == "" and nomi(filtra(prova_c, "car")) == "A"),
            ("il plurale trova il singolare", nomi(filtra(prova_c, "cards")) == "A"),
            ("fra virgolette una frase", nomi(filtra(prova_c, '"a card"')) == "A" and nomi(filtra(prova_c, '"card a"')) == ""),
            ("una virgoletta sola non rompe", nomi(filtra(prova_c, '"dra')) == "A"),
            ("prima chi ce l'ha nel nome", nomi(ordina([prova_c[0], prova_z], "Name", "draw")) == "ZA"),
            ("senza ricerca per nome", nomi(ordina([prova_z, prova_c[0]], "Name")) == "AZ"),
            ("una parola chiave vera", "Serra Angel" in vere("flying") and "Serra Angel" in vere("vigilance")),
            ("il segno davanti al numero", "Icy Reception" in vere("-5/-0")),
            ("la faccia dietro si cerca", "Aetherblade Agent" in vere("mindstinger")),
            ("almeno uno dei colori", nomi(filtra(prova_c, colori="U")) == "AC"),
            ("esattamente questi", nomi(filtra(prova_c, colori="U", modo=MODI[1])) == "C"),
            ("solo questi", nomi(filtra(prova_c, colori="UR", modo=MODI[2])) == "AC"),
            ("incolori", nomi(filtra(prova_c, colori="C")) == "B"),
            ("il set conta le sue copie", nomi(filtra(prova_c, sets=["DFT"], copie="1")) == "AB"),
            ("due set insieme: basta uno", nomi(filtra(prova_c, sets=["FRA", "DFT"])) == "ABC" and nomi(filtra(prova_c, sets=["FRA"])) == "AC"),
            ("due set insieme: le copie si sommano", nomi(filtra(prova_c, sets=["FRA", "DFT"], copie="4+")) == "A"),
            ("sotto le 4 copie", nomi(filtra(prova_c, copie="Under 4")) == "BC"),
            ("costo 7 o piu'", nomi(filtra(prova_c, costi=[7])) == "B"),
            ("rarita' e tipo", nomi(filtra(prova_c, rarita="MR", tipi=["Instant"])) == "C"),
            ("Standard", nomi(filtra(prova_c, standard=True)) == "AC"),
            ("per rarita'", nomi(ordina(prova_c, "Rarity")) == "CAB"),
            ("per copie", nomi(ordina(prova_c, "Copies")) == "ACB"),
            ("il riassunto", riassunto(prova_c, ["DFT"]) == dict(uniche=3, copie=2, M=1, R=1, U=0, C=1)),
            ("il riassunto di due set", riassunto(prova_c, ["FRA", "DFT"])["copie"] == 7),
            ("i set dal piu' nuovo", elenco_set(d)[0] in ("TRC", "TRK", "FRA", "HOB"))]
    for nome, ok in casi:
        print(("  ok    " if ok else "  ROSSO ") + nome)
    print(f"  {len(C)} carte diverse, {sum(c['copie'] for c in C)} copie, {len(elenco_set(d))} set, ignote {d['ignote']}")
    n = sum(1 for _, ok in casi if ok)
    print(f"{n}/{len(casi)}")
    return 0 if n == len(casi) else 1


if __name__ == "__main__":
    if "--prova" in sys.argv:
        sys.exit(prova())
    r = riassunto(carica()["carte"])
    print(r, "possedute", sum(c["copie"] > 0 for c in carica()["carte"]))
