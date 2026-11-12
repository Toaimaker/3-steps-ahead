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


# ------------------------------------------------------------------ le situazioni dentro la partita (12 nov 2026, Autore: «una finestra di filtri da flaggare
# che aggiungono agli smart situazioni piu' specifiche»). Dalle schede delle partite (Partite/, archivio_partite: turno, fase, chi, terre, magie coi bersagli,
# attacchi, morti): per ogni partita si' o no, o None se non si puo' dire (la partita e' finita prima, o non si sa chi ha cominciato).
SIT = [("io_terra", "You missed a land drop (by your 4th turn)"), ("lui_terra", "Opponent missed a land drop (by the opponent's 4th turn)"),
       ("io_curva", "You cast a spell on each of your turns 2, 3 and 4"), ("io_crea2", "Your first creature by your turn 2"),
       ("lui_crea2", "Opponent's first creature by the opponent's turn 2"), ("io_nel_suo", "You cast a spell on the opponent's turn"),
       ("lui_nel_mio", "Opponent cast a spell on your turn"),
       ("io_primo", "You attacked first"), ("lui_bersagli", "Opponent targeted your permanents with a spell"), ("io_morti", "You lost 3+ creatures"),
       ("lui_morti", "Opponent lost 3+ creatures"),
       # il mana aperto (stesso giorno, «vs mana untapped / with mana untapped»): dai pezzi di log di ogni partita (mana_aperto.py)
       ("io_att_aperto", "You attacked into 2+ untapped lands"), ("io_att_chiuso", "You attacked when the opponent was tapped out"),
       ("lui_att_aperto", "Opponent attacked into your 2+ untapped lands"), ("io_passa_aperto", "You passed your turn with 2+ lands untapped"),
       ("lui_passa_aperto", "Opponent passed the turn with 2+ lands untapped")]
_MANA = {}      # {matchId: dato di mana_aperto}, riempito da righe()
NOME_SIT = dict(SIT)
_SCHEDE = {}


def indice_schede():
    """{prime 8 lettere del matchId: file} delle schede in Partite/ (il nome finisce con _<8 lettere>.json)."""
    if "indice" not in _SCHEDE:
        import glob
        d = {}
        for f in glob.glob(os.path.join(percorsi.ROOT, "Partite", "*.json")):
            k = os.path.basename(f)[:-5].rsplit("_", 1)[-1]
            d[k] = f
        _SCHEDE["indice"] = d
    return _SCHEDE["indice"]


def scheda(match_id):
    f = indice_schede().get((match_id or "")[:8])
    if not f:
        return None
    if f not in _SCHEDE:
        try:
            with open(f, encoding="utf-8") as h:
                s = json.load(h)
            _SCHEDE[f] = s if s.get("matchId") == match_id else None
        except (OSError, ValueError):
            _SCHEDE[f] = None
    return _SCHEDE[f]


def situazioni_partita(s, io_inizia):
    """Le situazioni di una partita dalla sua scheda: {chiave: True, False o None}."""
    out = {k: None for k, _n in SIT}
    if not s or io_inizia is None:
        return out
    ev = s.get("eventi") or []
    turni = int(s.get("turni") or max([e.get("t", 0) for e in ev] or [0]))
    mio = lambda t: (t % 2 == 1) == bool(io_inizia)         # il turno t e' tuo?
    turno_k = lambda chi, k: (2 * k - 1) if (chi == "io") == bool(io_inizia) else 2 * k      # il k-esimo turno di chi
    for chi, chiave in (("io", "io_terra"), ("lui", "lui_terra")):
        t4 = turno_k(chi, 4)
        if turni >= t4:
            terre = sum(1 for e in ev if e.get("tipo") == "terra" and e.get("chi") == chi and e.get("t", 0) <= t4)
            out[chiave] = terre < 4
    if turni >= turno_k("io", 4):
        out["io_curva"] = all(any(e.get("tipo") == "lancia" and e.get("chi") == "io" and e.get("t") == turno_k("io", k) for e in ev) for k in (2, 3, 4))
    for chi, chiave in (("io", "io_crea2"), ("lui", "lui_crea2")):
        t2 = turno_k(chi, 2)
        if turni >= t2:
            out[chiave] = any(e.get("tipo") == "lancia" and e.get("chi") == chi and "Creature" in (e.get("tipi") or []) and e.get("t", 99) <= t2 for e in ev)
    out["io_nel_suo"] = any(e.get("tipo") == "lancia" and e.get("chi") == "io" and not mio(e.get("t", 0)) for e in ev)
    out["lui_nel_mio"] = any(e.get("tipo") == "lancia" and e.get("chi") == "lui" and mio(e.get("t", 0)) for e in ev)
    primo = next((e for e in ev if e.get("tipo") == "attacca"), None)
    out["io_primo"] = None if primo is None else primo.get("chi") == "io"
    out["lui_bersagli"] = any(e.get("tipo") == "lancia" and e.get("chi") == "lui" and "io" in (e.get("bersagli_di") or []) for e in ev)
    out["io_morti"] = sum(1 for e in ev if e.get("tipo") == "muore" and e.get("chi") == "io") >= 3
    out["lui_morti"] = sum(1 for e in ev if e.get("tipo") == "muore" and e.get("chi") == "lui") >= 3
    return out


# ------------------------------------------------------------------ le righe
def _fascia(h):
    return next(n for n, a, b in FASCE if a <= h < b)


def _lunga(t):
    return next((n for n, a, b in LUNGHE if a <= t <= b), None) if t else None


_TAB = {}


def _tabella():
    """Le carte di Arena per nome (costo, tipo, colori), una volta."""
    if "t" not in _TAB:
        try:
            import dati_mazzo as DM
            _TAB["t"] = DM.tabella_carte()
        except Exception:      # noqa: BLE001 - senza il database i filtri della mano restano vuoti
            _TAB["t"] = {}
    return _TAB["t"]


def _carta(nome):
    t = _tabella()
    return t.get(nome) or t.get(nome.split(" // ")[0].strip())


def dalla_mano(tenuta):
    """La mano tenuta {nome: copie} -> (magie da 1-2 mana «0»/«1»/«2+», una creatura da 1-2 mana True/False); None se la mano non si conosce."""
    if not tenuta:
        return None, None
    econ, crea = 0, False
    for n, q in tenuta.items():
        c = _carta(n)
        if not c or "Land" in (c.get("tipo") or "").split(" // ")[0]:
            continue
        if 0 < (c.get("cmc") or 0) <= 2:
            econ += q
            crea = crea or "Creature" in (c.get("tipo") or "")
    return ("0" if econ == 0 else "1" if econ == 1 else "2+"), crea


def colori_mazzo(nomi_):
    """La variante di colore del tuo mazzo (WUBRG, «C» senza colori) dalle magie della lista; None senza lista."""
    if not nomi_:
        return None
    trovati = set()
    for n in nomi_:
        c = _carta(n)
        if c and "Land" not in (c.get("tipo") or "").split(" // ")[0]:
            trovati |= set(c.get("colori") or "")
    return "".join(k for k in "WUBRG" if k in trovati) or "C"


def come_finita(motivo, vinta):
    """Come e' finita: la concessione di chi, giocata fino in fondo, il tempo."""
    m = (motivo or "").replace("ResultReason_", "")
    if m == "Concede":
        return "Opponent conceded" if vinta else "You conceded"
    return {"Game": "Played to the end", "Timeout": "Timeout"}.get(m)


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
    econ, crea = dalla_mano(tenuta)
    lista = condividi.nomi(p.get("carte") or []) or {}
    return dict(r, seat=p.get("seat"), economiche=econ, crea_mano=crea, miei_colori=colori_mazzo(lista), fine=come_finita(p.get("motivo"), r["vinta"]),
                giorno=GIORNI[quando.weekday()], tipo="Limited" if r["formato"] == "limited" else "Constructed", quando=quando, ora=quando.hour, fascia=_fascia(quando.hour),
                terre=terre, mano=sorted(tenuta or {}), sue_viste=sorted(n for n in sue if not MS.e_terra(n)),
                turno=math.ceil(turni / 2) if turni else None, lunga=_lunga(math.ceil(turni / 2) if turni else None),
                partenza=None if r.get("inizia") is None else ("Play" if r["inizia"] else "Draw"),
                mull="0" if r["mulligan"] == 0 else "1" if r["mulligan"] == 1 else "2+",
                sit=dict(situazioni_partita(scheda(r.get("partita")), r.get("inizia")), **_mana_sit(r.get("partita"), p.get("seat"))))


_NOMI_GRP = {}


def nome_grp(g):
    """Il nome di una carta di Arena dal suo grpId (una volta per grpId); None se il database non la conosce."""
    if g not in _NOMI_GRP:
        try:
            import condividi
            _NOMI_GRP[g] = next(iter(condividi.nomi([g]) or {}), None)
        except Exception:      # noqa: BLE001 - senza database niente nomi
            _NOMI_GRP[g] = None
    return _NOMI_GRP[g]


def foto_partita(x):
    """Le foto di una partita dal tuo posto (mano_aperto): dict(mano0, turni=[(turno, tuo turno?, foto)], ultima) con le foto girate cosi' che [0] sia il tuo
    lato; None se la partita non ha il log. Una foto: dict(mio=[(nome, tappata, pedina)], suo=[...], mano=[nomi], n_suo=carte nella sua mano, vite=(tu, lui))."""
    d = _MANA.get(x.get("partita"))
    seat = x.get("seat")
    if not d or seat not in (1, 2) or "foto" not in d:
        return None
    a, b = seat - 1, 2 - seat

    def gira(f):
        if not f:
            return None
        carte = lambda lst: [(nome_grp(g) or ("Token" if p_ else f"#{g}"), bool(t_), bool(p_)) for g, t_, p_ in lst]
        return dict(mio=carte(f["c"][a]), suo=carte(f["c"][b]), mano=[nome_grp(g) or f"#{g}" for g in f["m"][a]], n_suo=f["n"][b], vite=(f["v"][a], f["v"][b]))
    turni = [(t, att == seat, gira(f)) for t, att, f in d.get("foto") or []]
    ult = d.get("ultima")
    return dict(mano0=gira(d.get("mano0")), turni=turni, ultima=(ult[0], ult[1] == seat, gira(ult[2])) if ult else None)


def _mana_sit(match_id, seat):
    import mana_aperto
    return mana_aperto.situazioni(_MANA.get(match_id), seat)


def sessioni(righe):
    """Il numero della partita nella sua sessione (1, 2, ...): righe in ordine di tempo; una sessione finisce dopo SESSIONE_ORE senza partite."""
    prima = None
    for x in sorted(righe, key=lambda x: x["quando"]):
        x["n_sessione"] = 1 if prima is None or (x["quando"] - prima["quando"]).total_seconds() > SESSIONE_ORE * 3600 else prima["n_sessione"] + 1
        x["sessione"] = "1st game" if x["n_sessione"] == 1 else "2nd-3rd game" if x["n_sessione"] <= 3 else "4th game or later"
        minuti = None if prima is None else (x["quando"] - prima["quando"]).total_seconds() / 60
        x["pausa"] = "Over 1 hour (new session)" if minuti is None or minuti > 60 else "Under 15 minutes" if minuti < 15 else "15-60 minutes"
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
    try:        # il mana aperto: dalla copia su disco, e le partite nuove lette adesso (la prima volta ~10 s per 450 partite)
        import mana_aperto
        _MANA.clear(); _MANA.update(mana_aperto.tutti(ids={p.get("matchId") for p in partite}))
    except Exception:       # noqa: BLE001 - senza i pezzi di log le situazioni del mana restano None
        _MANA.clear()
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
    ("colori", "Opponent colors (contains)", None),
    ("partenza", "Start", lambda x: x.get("partenza")),
    ("mull", "Mulligans", lambda x: x.get("mull")),
    ("terre", "Lands in opening hand", lambda x: None if x.get("terre") is None else str(x["terre"])),
    ("lunga", "Game length (your turns)", lambda x: x.get("lunga")),
    ("rango", "Rank", lambda x: x.get("rango")),
    ("data", "Date", None),
    ("fascia", "Time of day", lambda x: x.get("fascia")),
    ("sessione", "Game in session", lambda x: x.get("sessione")),
    ("mano", "Card in opening hand", None),
    ("sue", "Opponent card seen", None),
]
NOME = {k: n for k, n, _f in VARIABILI}
LEGGI = {k: f for k, _n, f in VARIABILI}
ORDINE_VALORI = {"partenza": ("Play", "Draw"), "mull": ("0", "1", "2+"), "lunga": tuple(n for n, _a, _b in LUNGHE), "rango": RANGHI,
                 "fascia": tuple(n for n, _a, _b in FASCE), "sessione": ("1st game", "2nd-3rd game", "4th game or later"), "colori": tuple("WUBRG"),
                 "terre": tuple(str(i) for i in range(8)), "data": tuple(n for n, _d in DATE)}
NOMI_COLORI = {"W": "White", "U": "Blue", "B": "Black", "R": "Red", "G": "Green"}

# la variante di colore esatta dell'avversario (12 nov 2026, Autore: «By deck ... un deck contro un'unica variante colore mazzo»): dal monocolore al
# pentacolore, o incolore («C»); non e' fra le tendine (si sceglie nella finestra By deck), ma vale per filtri, Split by, Group by e Spots
import itertools  # noqa: E402
VARIANTI = tuple("".join(c) for n in range(1, 6) for c in itertools.combinations("WUBRG", n)) + ("C",)
GRUPPI_VS = ((1, "Mono-color"), (2, "Two colors"), (3, "Three colors"), (4, "Four colors"), (5, "Five colors"), (0, "Colorless"))
NOMI_VS = dict(WU="Azorius", UB="Dimir", BR="Rakdos", RG="Gruul", WG="Selesnya", WB="Orzhov", UR="Izzet", BG="Golgari", WR="Boros", UG="Simic",
               WUB="Esper", UBR="Grixis", BRG="Jund", WRG="Naya", WUG="Bant", WBG="Abzan", WUR="Jeskai", UBG="Sultai", WBR="Mardu", URG="Temur")
NOME["vs"] = "Against"
ORDINE_VALORI["vs"] = VARIANTI


def vs_di(x):
    """La variante di colore del mazzo avversario, esatta, in ordine WUBRG («BR»); «C» se ha mostrato solo magie incolori; None se non si sa (nessuna sua
    magia vista)."""
    c = x.get("colori_suoi") or ""
    if c:
        return "".join(k for k in "WUBRG" if k in c)
    return None if (x.get("suo") or "Unknown") == "Unknown" else "C"


def nome_vs(v):
    if v == "C":
        return "Colorless"
    if len(v) == 1:
        return "Mono-" + NOMI_COLORI[v]
    if len(v) == 4:
        return "Four-color, no " + NOMI_COLORI[next(k for k in "WUBRG" if k not in v)].lower()
    if len(v) == 5:
        return "Five-color"
    return NOMI_VS.get(v, v)


# i filtri in piu' di ogni fase (12 nov 2026, Autore: «aggiungere a ogni tendina un set di filtri aggiuntivi per ogni step», «Sì, costruiscili»): non sono
# tendine, si scelgono dal + della fase; valgono come le altre variabili (filtri, Split by, Group by, Spots)
GIORNI = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
EXTRA = [("miei_colori", "Your deck's colors", lambda x: x.get("miei_colori")),
         ("economiche", "1-2 mana spells in your opening hand", lambda x: x.get("economiche")),
         ("crea_mano", "A 1-2 mana creature in your opening hand", lambda x: None if x.get("crea_mano") is None else ("Yes" if x["crea_mano"] else "No")),
         ("fine", "How it ended", lambda x: x.get("fine")),
         ("giorno", "Day of the week", lambda x: x.get("giorno")),
         ("pausa", "Break before this game", lambda x: x.get("pausa"))]
for _k, _n, _f in EXTRA:
    NOME[_k], LEGGI[_k] = _n, _f
# vinta o persa come tendina della fase Opening and first turns (12 nov 2026, Autore: «aggiungiamo la tendina di partita vinta o persa nella sezione opening
# hands and first turns»): non entra negli Spots (spiegherebbe tutto il win rate da sola)
NOME["esito"], LEGGI["esito"] = "Result", (lambda x: "Won" if x["vinta"] else "Lost")
ORDINE_VALORI.update(esito=("Won", "Lost"), miei_colori=VARIANTI, economiche=("0", "1", "2+"), crea_mano=("Yes", "No"),
                     fine=("You conceded", "Opponent conceded", "Played to the end", "Timeout"), giorno=GIORNI,
                     pausa=("Under 15 minutes", "15-60 minutes", "Over 1 hour (new session)"))


def per_varianti(r):
    """La tabella di By deck: per gruppo (mono, due ... cinque colori, incolore) i conti del gruppo e di ogni variante esatta che ha partite.
    -> [dict(gruppo, conti, varianti=[(variante, conti)])]."""
    out = []
    for n, nome in GRUPPI_VS:
        vv = [v for v in VARIANTI if (0 if v == "C" else len(v)) == n]
        per = collections.defaultdict(list)
        for x in r:
            v = vs_di(x)
            if v in vv:
                per[v].append(x)
        if per:
            out.append(dict(gruppo=nome, conti=conti([x for v in vv for x in per[v]]), varianti=[(v, conti(per[v])) for v in vv if per[v]]))
    return out


def valori_di(k, x):
    """I valori della variabile k per la riga x (una lista: una carta in mano o un colore possono essere piu' d'uno). «sit:chiave»: una situazione, «Yes» o «No»."""
    if k.startswith("sit:"):
        v = (x.get("sit") or {}).get(k[4:])
        return [] if v is None else ["Yes" if v else "No"]
    if k == "colori":
        return list(x.get("colori_suoi") or "")
    if k == "vs":
        v = vs_di(x)
        return [v] if v else []
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
    if k.startswith("sit:"):
        return [(v, c[v]) for v in ("Yes", "No") if c[v]]
    return c.most_common(massimo)


def nome_var(k):
    """Il nome di una variabile o di una situazione («sit:chiave»)."""
    return NOME_SIT.get(k[4:], k[4:]) if k.startswith("sit:") else NOME.get(k, k)


def etichetta(k, v):
    if k.startswith("sit:"):
        return NOME_SIT.get(k[4:], k[4:]) if v == "Yes" else "Not: " + NOME_SIT.get(k[4:], k[4:])
    if k in ("vs", "miei_colori"):
        return nome_vs(v) if v == "C" else f"{v} · {nome_vs(v)}"
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


def p_proporzioni(va, na, vb, nb):
    """Il test z di due proporzioni (va su na contro vb su nb): la p a due code. None con meno di 5 partite da una parte."""
    if na < 5 or nb < 5:
        return None
    p = (va + vb) / (na + nb)
    se = math.sqrt(p * (1 - p) * (1 / na + 1 / nb))
    if se == 0:
        return 1.0
    return math.erfc(abs(va / na - vb / nb) / se / math.sqrt(2))


def p_medie(xs, ys):
    """Due medie (i turni): il test z di Welch, la p a due code. None con meno di 5 valori da una parte."""
    xs, ys = [x for x in xs if x is not None], [y for y in ys if y is not None]
    if len(xs) < 5 or len(ys) < 5:
        return None
    ma, mb = sum(xs) / len(xs), sum(ys) / len(ys)
    va = sum((x - ma) ** 2 for x in xs) / (len(xs) - 1)
    vb = sum((y - mb) ** 2 for y in ys) / (len(ys) - 1)
    se = math.sqrt(va / len(xs) + vb / len(ys))
    if se == 0:
        return 1.0 if ma == mb else 0.0
    return math.erfc(abs(ma - mb) / se / math.sqrt(2))


def servono(pa, pb):
    """Quante partite per lato servirebbero a vedere una differenza come questa fra due proporzioni (0..1), al 5% con potenza 80%: (1,96 + 0,84)^2 = 7,84."""
    d = abs(pa - pb)
    if d < 1e-9:
        return None
    return math.ceil(7.84 * (pa * (1 - pa) + pb * (1 - pb)) / d ** 2)


def confronta(a, b):
    """Il confronto situazionale: A (le partite della situazione) contro B (il resto, tutte, o un'altra situazione). -> dict(a=conti, b=conti, righe=[...]):
    per ogni misura i due valori, la differenza (A meno B), la p (test z delle proporzioni, Welch per i turni) e, dove la differenza non regge ancora, quante
    partite per lato servirebbero a vederla."""
    ca, cb = conti(a), conti(b)
    righe_ = []

    def prop(k, nome, sa, sb, bene):
        va, vb = sum(1 for x in sa if bene(x)), sum(1 for x in sb if bene(x))
        na, nb = len(sa), len(sb)
        pa, pb = (va / na if na else None), (vb / nb if nb else None)
        d = round(100 * (pa - pb), 1) if pa is not None and pb is not None else None
        righe_.append(dict(k=k, nome=nome, a=None if pa is None else round(100 * pa, 1), b=None if pb is None else round(100 * pb, 1), na=na, nb=nb,
                           ic_a=wilson(va, na), ic_b=wilson(vb, nb), delta=d, p=p_proporzioni(va, na, vb, nb),
                           servono=servono(pa, pb) if d is not None else None, unita="%"))

    def media(k, nome, sa, sb):
        xa, xb = [x.get("turno") for x in sa], [x.get("turno") for x in sb]
        ma, mb = _media(xa), _media(xb)
        righe_.append(dict(k=k, nome=nome, a=ma, b=mb, na=sum(1 for x in xa if x is not None), nb=sum(1 for x in xb if x is not None), ic_a=None, ic_b=None,
                           delta=round(ma - mb, 1) if ma is not None and mb is not None else None, p=p_medie(xa, xb), servono=None, unita="T"))
    vinta = lambda x: x["vinta"]
    prop("wr", "Win rate", a, b, vinta)
    prop("play", "Win rate on the play", [x for x in a if x.get("partenza") == "Play"], [x for x in b if x.get("partenza") == "Play"], vinta)
    prop("draw", "Win rate on the draw", [x for x in a if x.get("partenza") == "Draw"], [x for x in b if x.get("partenza") == "Draw"], vinta)
    prop("mull", "Mulligan rate", a, b, lambda x: x["mulligan"])
    media("turni", "Game length", a, b)
    media("turni_v", "Length of the wins", [x for x in a if x["vinta"]], [x for x in b if x["vinta"]])
    media("turni_p", "Length of the losses", [x for x in a if not x["vinta"]], [x for x in b if not x["vinta"]])
    return dict(a=ca, b=cb, righe=righe_)


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
COPPIE = ("mio", "suo", "colori", "vs", "partenza", "mull", "terre", "lunga", "rango", "fascia", "sessione") + tuple("sit:" + s for s, _n in SIT)


def spot(r, minimo=15, quanti=8, coppie=True, gia=None):
    """-> (meglio, peggio): [dict(condizioni=[(chiave, valore)], nome, n, vinte, perse, wr, ic, delta, forte)]. gia: i filtri gia' messi (non si ripropongono)."""
    gia = {k for k, v in (gia or {}).items() if v is not None}
    base = conti(r)
    if not base["n"] or base["wr"] is None:
        return [], []
    insiemi = {}
    for k in [k for k, _n, _f in VARIABILI] + ["vs"] + [k for k, _n, _f in EXTRA] + ["sit:" + s for s, _n in SIT]:
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
        out.append(dict(condizioni=list(cond), nome=" · ".join(etichetta(k, v_) if k.startswith("sit:") else f"{NOME[k]}: {etichetta(k, v_)}" for k, v_ in cond),
                        n=n, vinte=v, perse=n - v, wr=wr, ic=(lo, hi),
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
    # le situazioni da una scheda finta: tu cominci (i tuoi turni sono i dispari)
    sch = dict(matchId="x", turni=9, eventi=[dict(t=1, chi="io", tipo="terra"), dict(t=2, chi="lui", tipo="terra"), dict(t=3, chi="io", tipo="terra"),
                                              dict(t=3, chi="io", tipo="lancia", tipi=["Creature"]), dict(t=4, chi="lui", tipo="terra"), dict(t=5, chi="io", tipo="terra"),
                                              dict(t=5, chi="io", tipo="lancia", tipi=["Instant"]), dict(t=6, chi="io", tipo="lancia", tipi=["Instant"]),
                                              dict(t=6, chi="lui", tipo="lancia", tipi=["Sorcery"], bersagli_di=["io"]), dict(t=7, chi="io", tipo="lancia", tipi=["Creature"]),
                                              dict(t=7, chi="io", tipo="attacca"), dict(t=8, chi="lui", tipo="muore"), dict(t=8, chi="io", tipo="muore")])
    s_ = situazioni_partita(sch, True)
    casi.append(("situazioni: tu 3 terre entro il tuo 4o turno (saltata), lui 2 entro il suo (saltata), curva piena, prima creatura al tuo T2",
                 s_["io_terra"] is True and s_["lui_terra"] is True and s_["io_curva"] is True and s_["io_crea2"] is True and s_["lui_crea2"] is False))
    casi.append(("situazioni: la tua magia nel suo turno, attacchi per primo, lui bersaglia il tuo, meno di 3 morti", s_["io_nel_suo"] and not s_["lui_nel_mio"]
                 and s_["io_primo"] and s_["lui_bersagli"] and s_["io_morti"] is False and s_["lui_morti"] is False))
    casi.append(("negativa: chi comincia non si sa, nessuna situazione", all(v is None for v in situazioni_partita(sch, None).values())))
    s_corta = situazioni_partita(dict(sch, turni=4), True)
    casi.append(("negativa: una partita finita prima del 4o turno non dice se hai saltato una terra", s_corta["io_terra"] is None))
    x_ = dict(righe_[0], sit=dict(io_terra=True))
    casi.append(("il filtro di una situazione: Yes, No, e None non passa", passa(x_, {"sit:io_terra": "Yes"}) and not passa(x_, {"sit:io_terra": "No"})
                 and not passa(x_, {"sit:io_curva": "Yes"}) and not passa(x_, {"sit:io_curva": "No"})))
    # il confronto situazionale: 70 su 100 contro 40 su 100 regge; lo stesso insieme no; con 3 partite non si dice
    fa = lambda v, n: [dict(vinta=i < v, mulligan=False, partenza="Play" if i % 2 else "Draw", turno=8) for i in range(n)]
    cf = confronta(fa(70, 100), fa(40, 100))
    w_ = cf["righe"][0]
    casi.append(("confronto: 70% contro 40% su 100 partite, +30 punti, p sotto 0,001", w_["k"] == "wr" and w_["delta"] == 30.0 and w_["p"] < 0.001))
    casi.append(("negativa: lo stesso insieme, differenza 0 e p 1", confronta(fa(50, 60), fa(50, 60))["righe"][0]["p"] == 1.0))
    casi.append(("negativa: 3 partite per lato, nessuna p", confronta(fa(2, 3), fa(1, 3))["righe"][0]["p"] is None))
    casi.append(("confronto: 50% contro 60% servono 385 partite per lato", servono(0.5, 0.6) == 385))
    casi.append(("confronto: turni uguali, p dei turni 1", next(r_ for r_ in cf["righe"] if r_["k"] == "turni")["p"] == 1.0))
    # la variante di colore esatta: «RB» e' Rakdos «BR», senza magie viste non si sa, solo incolori e' «C»; WBR non e' BR
    vx = [dict(colori_suoi="RB", suo="X"), dict(colori_suoi="", suo="Unknown"), dict(colori_suoi="", suo="No-Color Ramp"), dict(colori_suoi="WBR", suo="Y")]
    casi.append(("vs: la variante esatta in ordine WUBRG, incolore C, senza magie None", [vs_di(x) for x in vx] == ["BR", None, "C", "WBR"]))
    rv = [dict(righe_[i], colori_suoi=["BR", "WBR", "W", ""][i % 4], suo="Z") for i in range(40)]
    casi.append(("negativa: il filtro vs BR non prende WBR ne' W", all(vs_di(x) == "BR" for x in filtra(rv, {"vs": "BR"})) and len(filtra(rv, {"vs": "BR"})) == 10))
    pv = per_varianti(rv)
    casi.append(("per_varianti: mono, due, tre colori e incolore, ognuno coi suoi", [g["gruppo"] for g in pv] == ["Mono-color", "Two colors", "Three colors", "Colorless"]
                 and all(g["conti"]["n"] == 10 for g in pv) and nome_vs("WUBG") == "Four-color, no red" and etichetta("vs", "BR") == "BR · Rakdos"))
    # i filtri in piu' delle fasi: la mano, i colori del tuo mazzo, come e' finita
    _TAB["t"] = {"Shock": dict(tipo="Instant", cmc=1, colori="R"), "Goblin": dict(tipo="Creature — Goblin", cmc=2, colori="R"),
                 "Dragon": dict(tipo="Creature — Dragon", cmc=5, colori="R"), "Mountain": dict(tipo="Basic Land — Mountain", cmc=0, colori="R"),
                 "Owl": dict(tipo="Creature — Bird", cmc=2, colori="U")}
    casi.append(("la mano: 2 magie da 1-2 mana con una creatura; senza creatura economica No; mano sconosciuta None",
                 dalla_mano({"Shock": 1, "Goblin": 1, "Mountain": 3}) == ("2+", True) and dalla_mano({"Shock": 1, "Dragon": 1}) == ("1", False)
                 and dalla_mano(None) == (None, None)))
    casi.append(("negativa: le terre non contano fra le magie da 1-2 mana", dalla_mano({"Mountain": 5}) == ("0", False)))
    casi.append(("i colori del tuo mazzo dalle magie (le terre no), come e' finita", colori_mazzo(["Goblin", "Owl", "Mountain"]) == "UR"
                 and colori_mazzo(["Mountain"]) == "C" and come_finita("ResultReason_Concede", True) == "Opponent conceded"
                 and come_finita("ResultReason_Concede", False) == "You conceded" and come_finita("ResultReason_Game", True) == "Played to the end"))
    _TAB.clear()
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
