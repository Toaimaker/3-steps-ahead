"""I dati della vista Charts della scheda Meta: il meta giocato mazzo per mazzo, costruito e limited, con lo storico.

Autore, 10 nov 2026: «su meta abbiamo la sezione mazzi che viene da mtggoldfish / possiamo creare una seconda sezione che non e' visualizzata a
scacchiera ma a elenchi e ci fa vedere il meta giocato per mazzo in termini di grafici?», poi «includendo anche il meta del limited ovviamente».

- Costruito: le righe sono i mazzi della vista a schede (dati_meta.meta_mazzi: Untapped per Arena, MTGGoldfish per carta e MTGO), con quota, win rate
  (solo Standard: Untapped gratis non lo da' negli altri formati, la' c'e' la «forza»), win rate per rango (Standard), partite.
- Limited: le combinazioni di colori di un set nel Quick o nel Premier, da Untapped (Espansioni/<SET>/Quick/untapped/set_info_<formato>.json, che il
  giro del drafter riscarica; quick_draft_untapped.py): quota sulle partite del formato, win rate, win rate per rango, draft, il turno medio delle vittorie.
  La chiave «-1» del file e' il totale del formato. I colori sono una maschera di bit (W 1, U 2, B 4, R 8, G 16).
- Lo storico: Note/meta_storico/<chiave>.json, {giorno: {nome: [quota, win rate]}}, scritto da Motore/meta_storico.py nel giro dello scout.

    py -I -X utf8 Companion/App/Schede/Meta/dati_grafici.py --prova     i conti su un set_info finto e sui file veri, con le negative
"""
import os, sys
_casa = os.path.dirname(os.path.abspath(__file__))
while not os.path.isfile(os.path.join(_casa, "percorsi.py")):
    _casa = os.path.dirname(_casa)
if _casa not in sys.path:
    sys.path.insert(0, _casa)
import percorsi  # noqa: E402,F401
import glob  # noqa: E402
import json  # noqa: E402

ROOT = percorsi.ROOT
RANGHI = ("bronze", "silver", "gold", "platinum", "diamond", "mythic")
LIMITED = (("Quick Draft", "quick"), ("Premier Draft", "premier"))
BIT = {1: "W", 2: "U", 4: "B", 8: "R", 16: "G"}
QUOTA_MIN = 0.5         # nel limited le combinazioni sotto lo 0,5% delle partite non si mostrano (tre colori rari, mono colore)
STORICO = os.path.join(ROOT, "Note", "meta_storico")
TRE = dict(WUB="Esper", UBR="Grixis", BRG="Jund", WRG="Naya", WUG="Bant", WBG="Abzan", WUR="Jeskai", UBG="Sultai", WBR="Mardu", URG="Temur")   # i tre colori


def _json(p):
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def colori_da_bit(k):
    k = int(k)
    return "".join(c for b, c in BIT.items() if k > 0 and k & b)


def file_limited(set_, fmt):
    return os.path.join(ROOT, "Espansioni", set_, "Quick", "untapped", f"set_info_{fmt}.json")


def set_limited(fmt):
    """I set col meta del limited di quel formato, per data di uscita dal piu' nuovo."""
    sets = sorted({os.path.basename(os.path.dirname(os.path.dirname(os.path.dirname(p))))
                   for p in glob.glob(os.path.join(ROOT, "Espansioni", "*", "Quick", "untapped", f"set_info_{fmt}.json"))})
    try:
        import risorse as RS
        return RS.ordina_set(sets)
    except Exception:
        return sorted(sets, reverse=True)


def righe_limited(set_, fmt, d=None):
    """Le combinazioni di colori del meta limited di un set: [dict(nome, colori, quota, wr, wr_ranghi, partite, draft, turni)], per quota.
    d: il json gia' letto (le prove). [] se il file manca o non si legge."""
    import capsule as CAP
    d = _json(file_limited(set_, fmt)) if d is None else d
    cc = (d or {}).get("color_combinations_data") if isinstance(d, dict) else None
    if not isinstance(cc, dict):
        return []
    somma = lambda v, k: sum((v.get(k) or {}).values())
    tot = somma(cc.get("-1") or {}, "matches_all_by_rank") or sum(somma(v, "matches_all_by_rank") for k, v in cc.items() if k != "-1")
    if not tot:
        return []
    out = []
    for k, v in cc.items():
        if k == "-1":
            continue
        col = colori_da_bit(k)
        m, w = somma(v, "matches_all_by_rank"), somma(v, "matches_won_by_rank")
        if not col or not m:
            continue
        quota = m / tot * 100
        if quota < QUOTA_MIN:
            continue
        per = {}
        for r in RANGHI:
            mr, wr_ = (v.get("matches_all_by_rank") or {}).get(r, 0), (v.get("matches_won_by_rank") or {}).get(r, 0)
            if mr >= 100:          # sotto le 100 partite il win rate di un rango e' rumore
                per[r] = wr_ / mr * 100
        tw = v.get("avg_turns_won_by_rank") or {}
        mw = v.get("matches_won_by_rank") or {}
        turni = sum(tw[r] * mw.get(r, 0) for r in tw) / max(sum(mw.get(r, 0) for r in tw), 1) if tw else None
        out.append(dict(nome=TRE.get(col) or CAP.nome_mazzo(col), colori=col, quota=quota, wr=w / m * 100, wr_ranghi=per, partite=m,
                        draft=somma(v, "events_all_by_rank"), turni=turni))
    return sorted(out, key=lambda x: -x["quota"])


def righe_costruito(fmt):
    """I mazzi del meta costruito, quelli della vista a schede (stessi dati, si aprono nella stessa finestra): (righe, sottotitolo)."""
    from dati_meta import meta_mazzi
    mm, sotto = meta_mazzi(fmt)
    for m in mm:
        wt = m.get("wr_tutti") or {}
        m["wr_ranghi"] = {r: wt[r] for r in RANGHI if wt.get(r) is not None}
    return mm, sotto


def chiave_storico(fmt, set_=None):
    """«standard», «modern», «quick_FRA»..."""
    lim = dict(LIMITED).get(fmt)
    return f"{lim}_{set_}" if lim else fmt.lower().replace(" ", "_")


def storico(chiave):
    """{giorno: {nome: [quota, wr]}} dello storico, {} se non c'e'."""
    d = _json(os.path.join(STORICO, f"{chiave}.json"))
    return d if isinstance(d, dict) else {}


def serie(st, nome):
    """La quota di un mazzo giorno per giorno: [(giorno, quota)], dal piu' vecchio; i giorni in cui non c'era non contano."""
    return [(g, st[g][nome][0]) for g in sorted(st) if isinstance(st[g], dict) and nome in st[g]]


def storia_17lands(set_):
    """La storia del Premier di un set dai dati pubblici di 17Lands (Motore/limited_17lands.py): {coppie, nomi, dal, al, partite...}, None se non c'e'."""
    d = _json(os.path.join(ROOT, "Espansioni", set_, "Premier", "storia_17lands.json"))
    return d if isinstance(d, dict) and isinstance(d.get("coppie"), dict) else None


def matrice(storia, nomi):
    """{(riga, colonna): (partite, vinte)} fra le coppie coi nomi dati: la coppia della riga contro i colori principali dell'avversario uguali alla colonna."""
    if not storia:
        return {}
    chiave = {v: k for k, v in (storia.get("nomi") or {}).items()}
    out = {}
    for a in nomi:
        c = storia["coppie"].get(chiave.get(a)) or {}
        for b in nomi:
            n, w = (c.get("contro") or {}).get(chiave.get(b), (0, 0))
            if n:
                out[(a, b)] = (n, w)
    return out


MESI = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def nome_stagione(k):
    """«2026-10» -> «Oct 2026»: la stagione classificata di Arena e' un mese."""
    return f"{MESI[int(k[5:7]) - 1]} {k[:4]}"


def per_stagione(st):
    """Lo storico giorno per giorno raccolto per stagione (12 nov 2026, Autore: «gli stessi dati per season»; la stagione classificata di Arena, un mese):
    {«AAAA-MM»: {nome: [quota, wr]}}, la media dei giorni in cui il mazzo c'era (il win rate solo dei giorni che lo hanno)."""
    acc = {}
    for g, d in st.items():
        if not isinstance(d, dict) or len(g) < 7:
            continue
        for nome, v in d.items():
            if not isinstance(v, (list, tuple)) or not v:
                continue
            a = acc.setdefault(g[:7], {}).setdefault(nome, [[], []])
            if v[0] is not None:
                a[0].append(v[0])
            if len(v) > 1 and v[1] is not None:
                a[1].append(v[1])
    media = lambda x: round(sum(x) / len(x), 3) if x else None
    return {k: {n: [media(q), media(w)] for n, (q, w) in d.items()} for k, d in sorted(acc.items())}


def serie_di(st, nome, metrica=0):
    """[(chiave, valore)] di un mazzo per la metrica (0 quota, 1 win rate), dal piu' vecchio; i punti senza il valore non contano."""
    out = []
    for g in sorted(st):
        v = st[g].get(nome) if isinstance(st[g], dict) else None
        if isinstance(v, (list, tuple)) and len(v) > metrica and v[metrica] is not None:
            out.append((g, v[metrica]))
    return out


def prova():
    """I conti del limited su un file finto (quota, win rate, ranghi sotto 100 partite fuori, combinazioni sotto lo 0,5% fuori, file rotto vuoto) e
    sui file veri di FRA; lo storico e la serie."""
    casi = []
    finto = {"color_combinations_data": {
        "-1": {"matches_all_by_rank": {"gold": 1000}, "matches_won_by_rank": {"gold": 500}},
        "6": {"matches_all_by_rank": {"gold": 400, "mythic": 50}, "matches_won_by_rank": {"gold": 220, "mythic": 40}, "events_all_by_rank": {"gold": 90},
              "avg_turns_won_by_rank": {"gold": 9.0, "mythic": 8.0}},
        "9": {"matches_all_by_rank": {"gold": 4}, "matches_won_by_rank": {"gold": 4}}}}
    r = righe_limited("X", "quick", finto)
    ub = r[0] if r else {}
    casi.append(("UB: quota sulle partite del formato", abs(ub.get("quota", 0) - 45.0) < 1e-9))
    casi.append(("UB: win rate di tutte le partite", abs(ub.get("wr", 0) - 260 / 450 * 100) < 1e-9))
    casi.append(("UB: il rango sotto 100 partite non entra (negativa)", list(ub.get("wr_ranghi", {})) == ["gold"]))
    casi.append(("UB: turno medio delle vittorie pesato", abs(ub.get("turni", 0) - (9 * 220 + 8 * 40) / 260) < 1e-9))
    casi.append(("UB: nome e colori", ub.get("nome") == "Dimir" and ub.get("colori") == "UB"))
    casi.append(("sotto lo 0,5% non entra (negativa)", len(r) == 1))
    casi.append(("file rotto: vuoto, nessun errore (negativa)", righe_limited("X", "quick", {"color_combinations_data": None}) == [] and righe_limited("X", "quick", []) == []))
    vere = righe_limited("FRA", "quick")
    casi.append(("FRA Quick dai file veri: le coppie con quote che sommano sotto il 100%", len(vere) >= 8 and 50 < sum(x["quota"] for x in vere) <= 100.01))
    casi.append(("i set del limited per data di uscita", "FRA" in set_limited("quick")))
    st = {"2026-11-09": {"Mono-White": [10.0, 55.0]}, "2026-11-10": {"Mono-White": [11.0, 54.0], "Dimir": [5.0, 50.0]}}
    casi.append(("la serie dello storico", serie(st, "Mono-White") == [("2026-11-09", 10.0), ("2026-11-10", 11.0)] and serie(st, "Dimir") == [("2026-11-10", 5.0)]))
    stg = per_stagione({"2026-10-01": {"A": [10.0, 50.0]}, "2026-10-02": {"A": [14.0, None]}, "2026-11-01": {"A": [8.0, 52.0], "B": [3.0, 48.0]}})
    casi.append(("per stagione: la media dei giorni, il win rate solo dove c'e'", stg == {"2026-10": {"A": [12.0, 50.0]}, "2026-11": {"A": [8.0, 52.0], "B": [3.0, 48.0]}}))
    casi.append(("negativa: la serie del win rate salta i giorni senza", serie_di({"d1": {"A": [1.0, None]}, "d2": {"A": [2.0, 51.0]}}, "A", 1) == [("d2", 51.0)]
                 and nome_stagione("2026-10") == "Oct 2026"))
    sto = {"nomi": {"UB": "Dimir", "WU": "Azorius"}, "coppie": {"UB": {"contro": {"WU": [10, 6], "BR": [5, 1]}}, "WU": {"contro": {"UB": [10, 4]}}}}
    casi.append(("la matrice coppia contro coppia, solo fra le coppie chieste", matrice(sto, ["Dimir", "Azorius"]) == {("Dimir", "Azorius"): (10, 6), ("Azorius", "Dimir"): (10, 4)}
                 and matrice(None, ["Dimir"]) == {}))
    casi.append(("le chiavi dello storico", chiave_storico("Quick Draft", "FRA") == "quick_FRA" and chiave_storico("Standard") == "standard"))
    for n, e in casi:
        print(("  ok    " if e else "  ROSSO ") + n)
    print(f"{sum(bool(e) for _n, e in casi)}/{len(casi)}")
    return 0 if all(e for _n, e in casi) else 1


if __name__ == "__main__":
    sys.exit(prova() if "--prova" in sys.argv else 0)
