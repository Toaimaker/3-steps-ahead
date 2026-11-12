"""I dati dell'analizzatore della scheda Performance (Autore, 12 nov 2026: «riusciamo a modificarla per farla diventare come un analizzatore di partite ma
anche di situazioni come in holdem manager? la possibilita' di aggiungere variabili che ci mostrano come i grafici cambiano»).

Una riga per partita dai nostri log (partite_log, l'account mostrato), dal 22 set 2026 (il primo log archiviato), senza Sparky. Ogni riga ha le variabili che si
filtrano: formato, evento, il tuo mazzo, l'archetipo e i colori dell'avversario (matchup_log), chi comincia, i mulligan, le terre nella mano tenuta, la
lunghezza (i tuoi turni: i turni della partita contati per giocatore), il rango, la data, l'ora, la partita nella sessione (una sessione finisce dopo un'ora
ferma), una carta nella mano tenuta, una carta sua vista. Una situazione e' un insieme di filtri: i conti (win rate con l'intervallo di Wilson, record, turni,
mulligan, play e draw), le serie del grafico (una metrica per partite o per data, divise per una variabile) e il report (raggruppato per una variabile).

    py -I -X utf8 Companion/App/Schede/Performance/dati_analizzatore.py --prova
"""
import os, sys
_casa = os.path.dirname(os.path.abspath(__file__))
while not os.path.isfile(os.path.join(_casa, "percorsi.py")):
    _casa = os.path.dirname(_casa)
if _casa not in sys.path:
    sys.path.insert(0, _casa)
import percorsi  # noqa: E402,F401
import collections  # noqa: E402
import datetime  # noqa: E402
import json  # noqa: E402
import math  # noqa: E402

import account  # noqa: E402

SITUAZIONI = account.lega(globals(), "SITUAZIONI", "performance_situazioni.json")     # Log_Arena/performance_situazioni.json: le situazioni salvate
SESSIONE_ORE = 1.0          # un'ora senza partite chiude la sessione
RANGHI = ("Bronze", "Silver", "Gold", "Platinum", "Diamond", "Mythic")
FASCE = (("Night (0-6)", 0, 6), ("Morning (6-12)", 6, 12), ("Afternoon (12-18)", 12, 18), ("Evening (18-24)", 18, 24))
LUNGHE = (("Turns 1-5", 1, 5), ("Turns 6-8", 6, 8), ("Turns 9-11", 9, 11), ("Turns 12+", 12, 999))
DATE = (("Last 7 days", 7), ("Last 30 days", 30), ("Last 90 days", 90))
NOMI_FMT = {"standard": "Standard", "alchemy": "Alchemy", "explorer": "Explorer", "historic": "Historic", "timeless": "Timeless", "brawl": "Brawl",
            "standard_brawl": "Standard Brawl", "precon": "Dual Color Precons", "limited": "Limited"}


# ------------------------------------------------------------------ le righe
def _fascia(h):
    return next(n for n, a, b in FASCE if a <= h < b)


def _lunga(t):
    return next((n for n, a, b in LUNGHE if a <= t <= b), None) if t else None


def riga(p, r):
    """Una partita: il record di matchup_log piu' le variabili dell'analizzatore. p e' la partita di partite_log."""
    import condividi
    import mazzi_salvati as MS
    quando = datetime.datetime.fromtimestamp((p.get("inizio") or 0) / 1000)
    mani = p.get("mani") or []
    tenuta = condividi.nomi(mani[-1]) if mani else None
    terre = sum(q for n, q in tenuta.items() if MS.e_terra(n)) if tenuta else None
    sue = condividi.nomi(p.get("sue") or []) or {}
    turni = r.get("turni")
    return dict(r, tipo="Limited" if r["formato"] == "limited" else "Constructed", quando=quando, ora=quando.hour, fascia=_fascia(quando.hour),
                terre=terre, mano=sorted(tenuta or {}), sue_viste=sorted(n for n in sue if not MS.e_terra(n)),
                turno=math.ceil(turni / 2) if turni else None, lunga=_lunga(math.ceil(turni / 2) if turni else None),
                partenza=None if r.get("inizia") is None else ("Play" if r["inizia"] else "Draw"),
                mull="0" if r["mulligan"] == 0 else "1" if r["mulligan"] == 1 else "2+")


def sessioni(righe):
    """Il numero della partita nella sua sessione (1, 2, ...): righe in ordine di tempo; una sessione finisce dopo SESSIONE_ORE senza partite."""
    prima = None
    for x in sorted(righe, key=lambda x: x["quando"]):
        x["n_sessione"] = 1 if prima is None or (x["quando"] - prima["quando"]).total_seconds() > SESSIONE_ORE * 3600 else prima["n_sessione"] + 1
        x["sessione"] = "1st game" if x["n_sessione"] == 1 else "2nd-3rd game" if x["n_sessione"] <= 3 else "4th game or later"
        prima = x
    return righe


_CACHE = {}


def righe(partite=None):
    """Tutte le partite dei log come righe dell'analizzatore, in ordine di tempo. Ricordate finche' i log non cambiano."""
    import matchup_log as MU
    if partite is None:
        import partite_log
        partite, _n = partite_log.partite()
    partite = [p for p in partite if not p.get("bot") and p.get("vinta") is not None]
    firma = (len(partite), partite[-1].get("matchId") if partite else None)       # partite_log da' gia' le partite dell'account mostrato
    if _CACHE.get("firma") == firma:
        return _CACHE["righe"]
    out = []
    for p in partite:
        r = MU.record(p)
        if r:
            out.append(riga(p, r))
    sessioni(out)
    out.sort(key=lambda x: x["quando"])
    _CACHE.update(firma=firma, righe=out)
    return out


# ------------------------------------------------------------------ le variabili
def _tutte(chiave):
    return lambda x, v: x.get(chiave) == v


VARIABILI = [       # (chiave, nome, come si legge il valore dalla riga, test personalizzato o None)
    ("formato", "Format", lambda x: NOMI_FMT.get(x["formato"], x["formato"].title())),
    ("evento", "Event", lambda x: x.get("evento")),
    ("mio", "My deck", lambda x: x.get("mio")),
    ("suo", "Opponent", lambda x: x.get("suo")),
    ("colori", "Opp. colors (contains)", None),
    ("partenza", "Start", lambda x: x.get("partenza")),
    ("mull", "Mulligans", lambda x: x.get("mull")),
    ("terre", "Lands in opening hand", lambda x: None if x.get("terre") is None else str(x["terre"])),
    ("lunga", "Game length (your turns)", lambda x: x.get("lunga")),
    ("rango", "Rank", lambda x: x.get("rango")),
    ("data", "Date", None),
    ("fascia", "Time of day", lambda x: x.get("fascia")),
    ("sessione", "Game in session", lambda x: x.get("sessione")),
    ("mano", "Card in opening hand", None),
    ("sue", "Their card seen", None),
]
NOME = {k: n for k, n, _f in VARIABILI}
LEGGI = {k: f for k, _n, f in VARIABILI}
ORDINE_VALORI = {"partenza": ("Play", "Draw"), "mull": ("0", "1", "2+"), "lunga": tuple(n for n, _a, _b in LUNGHE), "rango": RANGHI,
                 "fascia": tuple(n for n, _a, _b in FASCE), "sessione": ("1st game", "2nd-3rd game", "4th game or later"), "colori": tuple("WUBRG"),
                 "terre": tuple(str(i) for i in range(8)), "data": tuple(n for n, _d in DATE)}
NOMI_COLORI = {"W": "White", "U": "Blue", "B": "Black", "R": "Red", "G": "Green"}


def valori_di(k, x):
    """I valori della variabile k per la riga x (una lista: una carta in mano o un colore possono essere piu' d'uno)."""
    if k == "colori":
        return list(x.get("colori_suoi") or "")
    if k == "mano":
        return x.get("mano") or []
    if k == "sue":
        return x.get("sue_viste") or []
    if k == "data":
        giorni = (datetime.datetime.now() - x["quando"]).days
        return [n for n, d in DATE if giorni < d]
    v = LEGGI[k](x)
    return [] if v is None else [v]


def passa(x, filtri):
    return all(v in valori_di(k, x) for k, v in filtri.items() if v is not None)


def filtra(righe_, filtri, tipo=None):
    return [x for x in righe_ if (tipo is None or x["tipo"] == tipo) and passa(x, filtri)]


def valori(righe_, k, massimo=80):
    """I valori della variabile k nelle righe, coi conti: [(valore, partite)], nell'ordine della variabile o dai piu' frequenti."""
    c = collections.Counter(v for x in righe_ for v in set(valori_di(k, x)))
    if k in ORDINE_VALORI:
        return [(v, c[v]) for v in ORDINE_VALORI[k] if c[v]]
    return c.most_common(massimo)


def etichetta(k, v):
    return f"{v} · {NOMI_COLORI[v]}" if k == "colori" and v in NOMI_COLORI else str(v)


# ------------------------------------------------------------------ i conti
def wilson(v, n, z=1.96):
    if not n:
        return None
    p = v / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    m = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return round(100 * (c - m)), round(100 * (c + m))


def _media(xs):
    xs = [x for x in xs if x is not None]
    return round(sum(xs) / len(xs), 1) if xs else None


def conti(r):
    """I numeri di un insieme di partite."""
    n = len(r)
    v = sum(1 for x in r if x["vinta"])
    pl = [x for x in r if x.get("partenza") == "Play"]
    dr = [x for x in r if x.get("partenza") == "Draw"]
    wr = lambda s: round(100 * sum(1 for x in s if x["vinta"]) / len(s), 1) if s else None
    return dict(n=n, vinte=v, perse=n - v, wr=wr(r), ic=wilson(v, n), play=wr(pl), n_play=len(pl), draw=wr(dr), n_draw=len(dr),
                mull=round(100 * sum(1 for x in r if x["mulligan"]) / n, 1) if n else None,
                turni=_media(x.get("turno") for x in r), turni_v=_media(x.get("turno") for x in r if x["vinta"]),
                turni_p=_media(x.get("turno") for x in r if not x["vinta"]))


METRICHE = (("wr", "Win rate"), ("n", "Games"), ("turni", "Avg turns"), ("mull", "Mulligan rate"))
FINESTRE = (("cum", "Cumulative"), ("10", "Last 10 games"), ("20", "Last 20 games"), ("50", "Last 50 games"))


def serie(r, metrica="wr", asse="games", finestra="20", posto=None):
    """Una linea: [(x, y)]. asse «games»: x = 1..n (o la posizione della partita fra tutte, posto: {id della partita: posizione}, cosi' le linee divise stanno
    sull'asse di tutte); «date»: x = il giorno (ordinale). finestra: «cum» cumulativa, o le ultime N partite (le partite: per giorno)."""
    r = sorted(r, key=lambda x: x["quando"])
    if not r:
        return []
    px = (lambda i, x: posto.get(x.get("partita") or id(x), i + 1)) if posto else (lambda i, x: i + 1)
    if metrica == "n":      # le partite: quante per giorno (o il conto che sale, per partite)
        if asse == "games":
            return [(px(i, x), i + 1) for i, x in enumerate(r)]
        per = collections.Counter(x["quando"].date().toordinal() for x in r)
        return sorted(per.items())
    val = {"wr": lambda x: 100.0 if x["vinta"] else 0.0, "turni": lambda x: x.get("turno"), "mull": lambda x: 100.0 if x["mulligan"] else 0.0}[metrica]
    N = None if finestra == "cum" else int(finestra)
    out, coda, tot, cnt = [], collections.deque(), 0.0, 0
    for i, x in enumerate(r):
        y = val(x)
        if y is None:
            continue
        coda.append(y); tot += y; cnt += 1
        if N is not None and len(coda) > N:
            tot -= coda.popleft(); cnt -= 1
        if N is not None and cnt < min(N, 5):       # le prime partite di una finestra mobile sono rumore: si comincia da 5
            continue
        xx = px(i, x) if asse == "games" else x["quando"].date().toordinal()
        yy = round(tot / cnt, 2)
        if asse == "date" and out and out[-1][0] == xx:
            out[-1] = (xx, yy)
        else:
            out.append((xx, yy))
    return out


def linee(r, metrica, asse, finestra, dividi=None, quante=5):
    """Le linee del grafico: [(nome, punti)]. Con dividi una per valore (i piu' giocati, al massimo quante), piu' All."""
    posto = {x.get("partita") or id(x): i + 1 for i, x in enumerate(sorted(r, key=lambda x: x["quando"]))}
    out = [("All", serie(r, metrica, asse, finestra))]
    if dividi:
        for v, _n in sorted(valori(r, dividi), key=lambda t: -t[1])[:quante]:
            out.append((etichetta(dividi, v), serie([x for x in r if v in valori_di(dividi, x)], metrica, asse, finestra, posto=posto)))
    return out


def cambi_rango(r):
    """Dove cambia il rango, sull'asse delle partite: [(indice 1.., rango)] (i loghi delle leghe sul grafico di prima)."""
    out, prima = [], None
    for i, x in enumerate(sorted(r, key=lambda x: x["quando"])):
        if x.get("rango") and x["rango"] != prima:
            if prima is not None:
                out.append((i + 1, x["rango"]))
            prima = x["rango"]
    return out


def report(r, per, ordina="n", minimo=15):
    """Il report raggruppato per la variabile per: una riga per valore coi conti e lo scarto dal win rate di tutte (delta). ordina: una chiave dei conti
    («n», «wr», «delta», «turni», ...) o «nome». minimo: sotto, la riga e' un indizio (poche)."""
    tutti = conti(r)
    out = []
    for v, _n in valori(r, per, massimo=200):
        c = conti([x for x in r if v in valori_di(per, x)])
        c.update(valore=v, nome=etichetta(per, v), delta=None if c["wr"] is None or tutti["wr"] is None else round(c["wr"] - tutti["wr"], 1),
                 poche=c["n"] < minimo)
        out.append(c)
    if ordina == "nome":
        out.sort(key=lambda c: str(c["nome"]).lower())
    elif ordina == "ordine" and per in ORDINE_VALORI:
        pass
    else:
        out.sort(key=lambda c: (c["poche"], -(c.get(ordina) if c.get(ordina) is not None else -1e9)))
    return out


# ------------------------------------------------------------------ gli spot: dove vinci e dove perdi di piu'
# (Autore, 12 nov 2026: «questa sezione dovra' aiutare i giocatori a leggere gli spot dove vincono di piu' dove perdono di piu'»). Si provano tutte le
# condizioni di una variabile e le coppie di due variabili (fra quelle di COPPIE), sulle partite della situazione; resta chi ha almeno `minimo` partite. L'ordine
# non e' lo scarto grezzo, che premia il rumore: e' quanto l'intervallo di Wilson sta sopra (o sotto) il win rate di tutte, cosi' in testa ci sono gli spot che
# reggono. «forte»: l'intervallo intero sta dalla sua parte.
COPPIE = ("mio", "suo", "colori", "partenza", "mull", "terre", "lunga", "rango", "fascia", "sessione")


def spot(r, minimo=15, quanti=8, coppie=True, gia=None):
    """-> (meglio, peggio): [dict(condizioni=[(chiave, valore)], nome, n, vinte, perse, wr, ic, delta, forte)]. gia: i filtri gia' messi (non si ripropongono)."""
    gia = {k for k, v in (gia or {}).items() if v is not None}
    base = conti(r)
    if not base["n"] or base["wr"] is None:
        return [], []
    insiemi = {}
    for k, _n, _f in VARIABILI:
        if k in gia or k == "data":
            continue
        per = collections.defaultdict(set)
        for i, x in enumerate(r):
            for v in set(valori_di(k, x)):
                per[v].add(i)
        for v, s in per.items():
            if len(s) >= minimo and len(s) < len(r):
                insiemi[((k, v),)] = frozenset(s)
    if coppie:
        uno = [(c[0], s) for c, s in insiemi.items() if c[0][0] in COPPIE]
        for a in range(len(uno)):
            for b in range(a + 1, len(uno)):
                (ka, va), sa = uno[a]
                (kb, vb), sb = uno[b]
                if ka == kb:
                    continue
                s = sa & sb
                if len(s) >= minimo and s != sa and s != sb:
                    insiemi[((ka, va), (kb, vb))] = s
    out = []
    for cond, s in insiemi.items():
        sub = [r[i] for i in s]
        v = sum(1 for x in sub if x["vinta"])
        n = len(sub)
        lo, hi = wilson(v, n)
        wr = round(100 * v / n, 1)
        out.append(dict(condizioni=list(cond), nome=" · ".join(f"{NOME[k]}: {etichetta(k, v_)}" for k, v_ in cond), n=n, vinte=v, perse=n - v, wr=wr, ic=(lo, hi),
                        delta=round(wr - base["wr"], 1), su=lo - base["wr"], giu=base["wr"] - hi))
    meglio = sorted((x for x in out if x["delta"] > 0), key=lambda x: -x["su"])[:quanti]
    peggio = sorted((x for x in out if x["delta"] < 0), key=lambda x: -x["giu"])[:quanti]
    for x in meglio:
        x["forte"] = x["su"] > 0
    for x in peggio:
        x["forte"] = x["giu"] > 0
    return meglio, peggio


# ------------------------------------------------------------------ la matrice dei matchup
# (stesso giorno: «potranno incastrare anche i mazzi che utilizzano vs i mazzi del meta o trovati in partite»): i tuoi mazzi in riga, gli archetipi incontrati in
# colonna (quelli riconosciuti fra le liste del meta, o anche «Other · colori» e «Unknown», i mazzi trovati in partita), in ogni cella partite e win rate.
def del_meta(suo):
    return bool(suo) and not suo.startswith("Other") and suo != "Unknown"


def matrice(r, solo_meta=False, righe_max=8, colonne_max=10):
    """-> (mazzi, archetipi, celle {(mazzo, archetipo): (n, vinte, wr)}, totali per mazzo {mazzo: (n, wr)}, per archetipo {arch: (n, wr)})."""
    r = [x for x in r if x.get("mio") and x.get("suo") and (not solo_meta or del_meta(x["suo"]))]
    mazzi = [m for m, _n in collections.Counter(x["mio"] for x in r).most_common(righe_max)]
    archi = [a for a, _n in collections.Counter(x["suo"] for x in r if x["mio"] in mazzi).most_common(colonne_max)]
    celle, per_m, per_a = {}, {}, {}
    for m in mazzi:
        rm = [x for x in r if x["mio"] == m]
        per_m[m] = (len(rm), round(100 * sum(x["vinta"] for x in rm) / len(rm), 1))
        for a in archi:
            s = [x for x in rm if x["suo"] == a]
            if s:
                v = sum(1 for x in s if x["vinta"])
                celle[(m, a)] = (len(s), v, round(100 * v / len(s), 1))
    for a in archi:
        ra = [x for x in r if x["suo"] == a and x["mio"] in mazzi]
        per_a[a] = (len(ra), round(100 * sum(x["vinta"] for x in ra) / len(ra), 1))
    return mazzi, archi, celle, per_m, per_a


# ------------------------------------------------------------------ le situazioni salvate
def situazioni():
    try:
        with open(SITUAZIONI, encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, list) else []
    except (OSError, ValueError):
        return []


def nome_situazione(tipo, filtri):
    parti = [etichetta(k, v) for k, v in filtri.items() if v is not None]
    return (tipo + " · " if tipo else "") + (" · ".join(parti) if parti else "all games")


def salva_situazione(tipo, filtri, nome=None):
    """Una situazione nuova in testa (una uguale non si ripete). -> la lista."""
    d = [s for s in situazioni() if not (s.get("tipo") == tipo and s.get("filtri") == filtri)]
    d.insert(0, dict(nome=nome or nome_situazione(tipo, filtri), tipo=tipo, filtri={k: v for k, v in filtri.items() if v is not None}))
    _scrivi(d[:30])
    return d[:30]


def togli_situazione(i):
    d = situazioni()
    if 0 <= i < len(d):
        d.pop(i)
        _scrivi(d)
    return d


def _scrivi(d):
    if account.sola_lettura():
        return
    os.makedirs(os.path.dirname(SITUAZIONI), exist_ok=True)
    with open(SITUAZIONI + ".tmp", "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
    os.replace(SITUAZIONI + ".tmp", SITUAZIONI)


# ------------------------------------------------------------------ prova
def prova():
    """Righe finte: i filtri, i conti, le serie, il report, le sessioni, le situazioni salvate (file temporaneo). Con le negative."""
    import tempfile
    global SITUAZIONI
    base = datetime.datetime(2026, 11, 1, 20, 0)
    righe_ = []
    for i in range(40):
        q = base + datetime.timedelta(minutes=20 * i + (300 if i >= 20 else 0))
        x = dict(tipo="Constructed", formato="standard", evento="Ladder", mio="UW" if i % 2 else "Red", suo="Mono-White Auras" if i % 3 == 0 else "Other",
                 colori_suoi="W" if i % 3 == 0 else "BR", vinta=i % 4 != 0, mulligan=1 if i % 5 == 0 else 0, turni=16 + i % 6, rango="Gold" if i < 25 else "Platinum",
                 quando=q, inizia=bool(i % 2))
        x.update(ora=q.hour, fascia=_fascia(q.hour), terre=2 + i % 3, mano=["Erode"] if i % 2 else ["Shock"], sue_viste=["Unholy Annex"] if i % 3 == 0 else [],
                 turno=math.ceil(x["turni"] / 2), lunga=_lunga(math.ceil(x["turni"] / 2)), partenza="Play" if x["inizia"] else "Draw",
                 mull="0" if x["mulligan"] == 0 else "1")
        righe_.append(x)
    sessioni(righe_)
    casi = []
    c = conti(righe_)
    casi.append(("conti: 40 partite, 30 vinte, win rate 75, l'intervallo intorno", c["n"] == 40 and c["vinte"] == 30 and c["wr"] == 75.0 and c["ic"][0] < 75 < c["ic"][1]))
    f = filtra(righe_, {"partenza": "Draw", "terre": "2"})
    casi.append(("filtri insieme: on the draw e 2 terre", f and all(x["partenza"] == "Draw" and x["terre"] == 2 for x in f)))
    casi.append(("negativa: un valore che non c'e' non passa niente", not filtra(righe_, {"suo": "Nessuno"})))
    casi.append(("colori: contiene", all("W" in x["colori_suoi"] for x in filtra(righe_, {"colori": "W"})) and len(filtra(righe_, {"colori": "W"})) == 14))
    casi.append(("carta in mano e carta sua", len(filtra(righe_, {"mano": "Erode"})) == 20 and len(filtra(righe_, {"sue": "Unholy Annex"})) == 14))
    casi.append(("le sessioni: dopo un'ora ferma si riparte da 1", righe_[0]["n_sessione"] == 1 and righe_[19]["n_sessione"] == 20 and righe_[20]["n_sessione"] == 1))
    s = serie(righe_, "wr", "games", "cum")
    casi.append(("serie cumulativa: l'ultimo punto e' il win rate", s[-1] == (40, 75.0)))
    s10 = serie(righe_, "wr", "games", "10")
    casi.append(("serie mobile: comincia dalla quinta partita e l'ultimo punto e' sulle ultime 10", s10[0][0] == 5 and s10[-1][1] == 80.0))
    ln = linee(righe_, "wr", "games", "cum", dividi="partenza")
    casi.append(("split by: All e una linea per valore", [n for n, _p in ln] == ["All", "Play", "Draw"]))
    rp = report(righe_, "suo")
    casi.append(("report: una riga per archetipo, col delta da tutte", {x["valore"] for x in rp} == {"Mono-White Auras", "Other"}
                 and next(x for x in rp if x["valore"] == "Mono-White Auras")["delta"] == round(next(x for x in rp if x["valore"] == "Mono-White Auras")["wr"] - 75.0, 1)))
    casi.append(("report: sotto 15 partite e' poche", all(x["poche"] == (x["n"] < 15) for x in rp)))
    casi.append(("i cambi di rango", cambi_rango(righe_) == [(26, "Platinum")]))
    vecchio = SITUAZIONI
    SITUAZIONI = os.path.join(tempfile.mkdtemp(), "s.json")
    try:
        salva_situazione("Constructed", {"partenza": "Draw", "terre": "2", "suo": None})
        d = salva_situazione("Constructed", {"partenza": "Draw", "terre": "2"})
        casi.append(("situazioni: si salvano col nome dai filtri, una uguale non si ripete", len(d) == 1 and d[0]["nome"] == "Constructed · Draw · 2"))
        casi.append(("situazioni: si tolgono", togli_situazione(0) == [] and situazioni() == []))
    finally:
        SITUAZIONI = vecchio
    righe_[3].update(partita="p3")
    for i, x in enumerate(righe_):
        x.setdefault("partita", f"p{i}")
    lnp = dict(linee(righe_, "wr", "games", "cum", dividi="partenza"))
    casi.append(("le linee divise stanno sull'asse di tutte: la linea Draw arriva fino all'ultima partita della situazione",
                 lnp["Draw"][-1][0] in (39, 40) and lnp["Play"][-1][0] in (39, 40)))
    # uno spot vero piantato: con 2 terre in mano si perde sempre
    for x in righe_:
        if x["terre"] == 2:
            x["vinta"] = False
    meglio, peggio = spot(righe_, minimo=10)
    casi.append(("spot: in testa a dove perdi c'e' la condizione piantata (2 terre in mano, a pari merito con chi ha le stesse partite), forte",
                 peggio and any(x["condizioni"] == [("terre", "2")] and x["giu"] == peggio[0]["giu"] and x["forte"] for x in peggio)))
    casi.append(("spot: dove vinci di piu' sono sopra la media, dove perdi sotto", all(x["delta"] > 0 for x in meglio) and all(x["delta"] < 0 for x in peggio)))
    casi.append(("negativa: un filtro gia' messo non torna fra gli spot", not any(k == "terre" for x in spot(righe_, minimo=10, gia={"terre": "2"})[1] for k, _v in x["condizioni"])))
    casi.append(("negativa: sotto il minimo di partite niente spot", spot(righe_, minimo=100) == ([], [])))
    mz, ar, ce, pm, pa = matrice(righe_)
    casi.append(("matrice: i tuoi mazzi in riga, gli archetipi in colonna, ogni cella con partite e win rate", set(mz) == {"UW", "Red"} and set(ar) == {"Mono-White Auras", "Other"}
                 and sum(ce[(m, a)][0] for m in mz for a in ar if (m, a) in ce) == 40))
    casi.append(("matrice: solo i mazzi del meta toglie Other e Unknown", matrice(righe_, solo_meta=True)[1] == ["Mono-White Auras"]))
    vere = righe()
    casi.append(("i log veri: righe con le variabili (se ci sono partite)", not vere or all(k in vere[0] for k in ("tipo", "partenza", "terre", "sessione", "fascia"))))
    for n, ok in casi:
        print(("ok    " if ok else "ROSSO ") + n)
    print(f"{sum(1 for _n, ok in casi if ok)}/{len(casi)}")
    return all(ok for _n, ok in casi)


if __name__ == "__main__":
    if "--prova" in sys.argv:
        sys.exit(0 if prova() else 1)
    r = righe()
    print(len(r), "partite;", collections.Counter(x["tipo"] for x in r))
    print(conti(r))
