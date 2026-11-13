"""I matchup dai log: il primo pezzo della banca dati nostra (12 nov 2026, Autore: «fai la bancadati più completa e tutt'ora inesistente per soddisfare il
massimo delle informazioni», «pensa a cosa vorrebbe sapere un pro da uno scenario competitivo», poi la scelta «Matchup dai log»).

Ogni partita finita del costruito diventa un record: formato, giorno, il tuo mazzo, l'archetipo dell'avversario, esito, chi comincia, mulligan, turni, rango.
- **L'archetipo dell'avversario** si riconosce dalle sue carte viste fuori da grimorio e mano (partite_log «sue»): le magie viste si confrontano con le liste
  degli archetipi del meta del formato (i file della pagina Meta: lo scout nell'app di Autore, la copia ferma dell'11 nov 2026 nell'app pubblica).
  Vince l'archetipo che ne contiene di piu' (ogni carta pesa le copie della lista su 4) se arriva almeno a SOGLIA con almeno 2 carte e se i colori visti
  stanno nei suoi; se no l'avversario resta coi soli colori («Azorius», «Mono-White»: mai «Other», regola di Autore del 12 nov 2026), e senza magie viste
  «Unknown». Grado C: chi concede al turno 3 mostra poco.
- **Il tuo mazzo** e' il nome che ha su Arena (partite_log «nome_mazzo»); una riga condivisa (condividi.riga, senza nomi) si riconosce come l'avversario,
  dalla lista intera.
- Fuori: le partite contro Sparky (AIBotMatch) e quelle non finite. I Dual Color Precons hanno formato «precon» e gli avversari coi soli colori: le liste del
  meta non sono quelle. Il limited ha i suoi colori, non gli archetipi del costruito (coppia di colori delle magie viste).
- La banca dati: Log_Arena/banca_dati.sqlite (dell'account, account.lega), tabella `partite` con un record per partita (si rifa' ogni volta: e' un derivato
  dei log). Si interroga anche da fuori: `SELECT suo, count(*), avg(vinta) FROM partite WHERE formato='standard' GROUP BY suo`.
- I conti: `tabella` (tuo mazzo x suo archetipo: partite, vinte, win rate con l'intervallo di Wilson al 95%, on the play e on the draw, mulligan, turni medi
  delle vinte e delle perse), `campo` (cosa incontri: quota e win rate per archetipo, anche per giorno). Sotto MIN_PARTITE un matchup e' un indizio (n=1).

    py -I -X utf8 Companion/App/Schede/Meta/matchup_log.py              il campo e i matchup dei tuoi mazzi, a testo
    py -I -X utf8 Companion/App/Schede/Meta/matchup_log.py --prova      partite finte, con le negative
"""
import os, sys
_casa = os.path.dirname(os.path.abspath(__file__))      # si sale fino a percorsi.py, che mette nel sys.path tutte le cartelle del Companion
while not os.path.isfile(os.path.join(_casa, "percorsi.py")):
    _casa = os.path.dirname(_casa)
if _casa not in sys.path:
    sys.path.insert(0, _casa)
import percorsi  # noqa: E402,F401
import datetime  # noqa: E402
import json  # noqa: E402
import math  # noqa: E402
import re  # noqa: E402
import sqlite3  # noqa: E402
import threading  # noqa: E402
import account as _ACC  # noqa: E402

BANCA = ""
_ACC.lega(globals(), "BANCA", "banca_dati.sqlite")
SOGLIA = 1.5            # punti di carte (copie della lista / 4) per dire un archetipo
MIN_PARTITE = 5         # sotto, un matchup e' un indizio
COLORI = "WUBRG"
DUE = dict(WU="Azorius", UB="Dimir", BR="Rakdos", RG="Gruul", WG="Selesnya", WB="Orzhov", UR="Izzet", BG="Golgari", WR="Boros", UG="Simic")
TRE = dict(WUB="Esper", UBR="Grixis", BRG="Jund", WRG="Naya", WUG="Bant", WBG="Abzan", WUR="Jeskai", UBG="Sultai", WBR="Mardu", URG="Temur")
MONO = dict(W="Mono-White", U="Mono-Blue", B="Mono-Black", R="Mono-Red", G="Mono-Green")
SOLI_COLORI = set(MONO.values()) | set(DUE.values()) | set(TRE.values()) | {"4-Color", "5-Color", "Colorless"}


def solo_colori(suo):
    """Un avversario fuori dal meta, chiamato coi soli colori (12 nov 2026: mai «Other»; «Other · ...» e' il nome di prima, se ne resta uno in una copia)."""
    return bool(suo) and (suo in SOLI_COLORI or suo.startswith("Other"))
META_FMT = dict(standard="Standard", historic="Historic", explorer="Explorer", alchemy="Alchemy", timeless="Timeless", brawl="Brawl")
_LOCK = threading.Lock()
_INFO = {}
_ARCH = {}


def formato(evento):
    """Il formato di un evento di Arena, o None se la partita non conta (Sparky)."""
    e = evento or ""
    if e.startswith("AIBotMatch"):
        return None
    if re.search(r"Draft|Sealed|Cube", e):
        return "limited"
    if e.startswith("DualColorPrecons") or "Precon" in e:
        return "precon"
    for k in ("historic", "explorer", "alchemy", "timeless", "brawl"):
        if k in e.lower():
            return k
    return "standard"       # Ladder, Play, Traditional_Ladder, Constructed_Event_...


def nome_colori(c):
    c = "".join(x for x in COLORI if x in (c or ""))
    if not c:
        return "Colorless"
    return MONO.get(c) or DUE.get(c) or TRE.get(c) or f"{len(c)}-Color"


def _chiave(n):
    return (n or "").split(" // ")[0].strip().lower()


def info_carte():
    """{nome minuscolo: (colori, terra)} dal database delle carte di Arena (una volta per processo)."""
    with _LOCK:
        if not _INFO:
            import db_carte
            t = db_carte.testi()
            for c in db_carte.carte():
                n = t.get(c.get("titleId"))
                if not n:
                    continue
                k = _chiave(n)
                tipo = t.get(c.get("cardTypeTextId")) or ""
                col = "".join(COLORI[i - 1] for i in (c.get("colors") or []) if 1 <= i <= 5)
                vec = _INFO.get(k)
                _INFO[k] = (col if vec is None else "".join(x for x in COLORI if x in vec[0] + col), "Land" in tipo if vec is None else vec[1] and "Land" in tipo)
    return _INFO


def colori_di(nomi, info=None):
    """I colori di un mazzo dalle sue carte: quelli di almeno 2 carte diverse (una carta sola fuori colore, uno splash o una pedina, non cambia il mazzo);
    se nessun colore ha 2 carte, tutti quelli visti."""
    info = info or info_carte()
    conta = {}
    for k in {_chiave(n) for n in nomi}:
        for x in (info.get(k) or ("", False))[0]:
            conta[x] = conta.get(x, 0) + 1
    s = {x for x, q in conta.items() if q >= 2} or set(conta)
    return "".join(x for x in COLORI if x in s)


def magie(nomi, info=None):
    info = info or info_carte()
    return {_chiave(n) for n in nomi if not (info.get(_chiave(n)) or ("", False))[1]}


def archetipi(fmt, meta=None):
    """[(nome, colori, {carta: peso}, quota)] degli archetipi del meta di un formato che hanno la lista (le magie, peso = copie / 4)."""
    if meta is None:
        if fmt in _ARCH:
            return _ARCH[fmt]
        meta = []
        if fmt in META_FMT:
            try:
                import dati_meta
                with open(dati_meta.file_meta(META_FMT[fmt]), encoding="utf-8") as f:
                    meta = json.load(f)
            except (OSError, ValueError, ImportError):
                meta = []
    info = info_carte()
    out = []
    for a in meta if isinstance(meta, list) else []:
        lista = a.get("lista") or {}
        pesi = {_chiave(n): min(q, 4) / 4 for n, q in lista.items() if not (info.get(_chiave(n)) or ("", False))[1]}
        if pesi:
            out.append((a.get("nome") or "?", "".join(x for x in COLORI if x in (a.get("colori") or "")), pesi, a.get("quota") or 0))
    if fmt is not None:
        _ARCH[fmt] = out
    return out


def riconosci(nomi, fmt, arch=None):
    """(archetipo, punti) dalle carte viste: l'archetipo del meta o i soli colori («Azorius»), «Unknown» senza magie."""
    info = info_carte()
    m = magie(nomi, info)
    if not m:
        return "Unknown", 0.0
    col = colori_di(nomi, info)
    arch = archetipi(fmt) if arch is None else arch
    meglio = None
    for nome, ca, pesi, quota in arch:
        if not set(col) <= set(ca or COLORI):
            continue
        dentro = [pesi[k] for k in m if k in pesi]
        if len(dentro) < 2:
            continue
        p = sum(dentro)
        if p >= SOGLIA and (meglio is None or (p, quota) > meglio[:2]):
            meglio = (p, quota, nome)
    if meglio:
        return meglio[2], round(meglio[0], 2)
    return nome_colori(col), 0.0


def nome_mazzo(n):
    """Il nome di un mazzo come lo mostra Arena: i mazzi dati da Arena hanno il nome in codice («?=?Loc/Decks/Precon/...»)."""
    if n and n.startswith("?=?"):
        try:
            import mazzi_arena
            return mazzi_arena.nome_precon(n) or n
        except Exception:       # noqa: BLE001 - senza traduzione resta il codice
            return n
    return n


def record(p, arch_fmt=None):
    """Il record di una partita di partite_log, o None se non conta (Sparky, non finita, senza esito)."""
    fmt = formato(p.get("evento"))
    if fmt is None or p.get("vinta") is None:
        return None
    import condividi
    sue = list((condividi.nomi(p.get("sue") or []) or {}).keys())
    mazzo = list((condividi.nomi(p.get("carte") or []) or {}).keys())
    if fmt in ("limited", "precon"):
        suo = nome_colori(colori_di(sue)) if magie(sue) else "Unknown"
        mio = (nome_mazzo(p.get("nome_mazzo")) if fmt == "precon" else None) or nome_colori(colori_di(mazzo))
        punti = 0.0
    else:
        suo, punti = riconosci(sue, fmt, arch_fmt)
        mio = nome_mazzo(p.get("nome_mazzo")) or riconosci(mazzo, fmt, arch_fmt)[0]
    mani = p.get("mani") or []
    rg = p.get("rango_prima") or []
    return dict(partita=p.get("matchId"), giorno=datetime.date.fromtimestamp((p.get("inizio") or 0) / 1000).isoformat(), formato=fmt, evento=p.get("evento"),
                mio=mio, suo=suo, punti=punti, colori_suoi=colori_di(sue), carte_viste=len(magie(sue)), vinta=bool(p["vinta"]),
                inizia=(p.get("inizia") == p.get("seat")) if p.get("inizia") is not None else None, mulligan=max(0, len(mani) - 1), turni=p.get("turni"),
                rango=rg[0] if rg else None)


def records(partite=None):
    """I record delle tue partite (partite_log, l'account mostrato)."""
    if partite is None:
        import partite_log
        partite, _n = partite_log.partite()
    return [r for r in (record(p) for p in partite) if r]


def salva(recs, file=None):
    """La banca dati su disco: la tabella `partite` rifatta coi record."""
    file = file or BANCA
    os.makedirs(os.path.dirname(file), exist_ok=True)
    tmp = file + ".tmp"
    if os.path.exists(tmp):
        os.remove(tmp)
    db = sqlite3.connect(tmp)
    try:
        db.execute("CREATE TABLE partite (partita TEXT PRIMARY KEY, giorno TEXT, formato TEXT, evento TEXT, mio TEXT, suo TEXT, punti REAL, colori_suoi TEXT, "
                   "carte_viste INTEGER, vinta INTEGER, inizia INTEGER, mulligan INTEGER, turni INTEGER, rango TEXT)")
        db.execute("CREATE INDEX partite_fmt ON partite (formato, suo)")
        db.executemany("INSERT OR REPLACE INTO partite VALUES (:partita, :giorno, :formato, :evento, :mio, :suo, :punti, :colori_suoi, :carte_viste, :vinta, "
                       ":inizia, :mulligan, :turni, :rango)", [dict(r, inizia=None if r["inizia"] is None else int(r["inizia"])) for r in recs])
        db.commit()
    finally:
        db.close()
    os.replace(tmp, file)
    return file


def wilson(v, n, z=1.96):
    """(basso, alto) del win rate in %, intervallo di Wilson."""
    if not n:
        return None, None
    p = v / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    m = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return round(100 * (c - m), 1), round(100 * (c + m), 1)


def _conta(rr):
    n = len(rr)
    v = sum(1 for r in rr if r["vinta"])
    lo, hi = wilson(v, n)
    pl = [r for r in rr if r["inizia"] is True]
    dr = [r for r in rr if r["inizia"] is False]
    tv = [r["turni"] for r in rr if r["vinta"] and r["turni"]]
    tp = [r["turni"] for r in rr if not r["vinta"] and r["turni"]]
    return dict(partite=n, vinte=v, perse=n - v, wr=round(100 * v / n, 1) if n else None, basso=lo, alto=hi,
                play=(len(pl), sum(1 for r in pl if r["vinta"])), draw=(len(dr), sum(1 for r in dr if r["vinta"])),
                mulligan=round(100 * sum(1 for r in rr if r["mulligan"]) / n, 1) if n else None,
                turni_vinte=round(sum(tv) / len(tv), 1) if tv else None, turni_perse=round(sum(tp) / len(tp), 1) if tp else None,
                poche=n < MIN_PARTITE)


def tabella(recs, fmt=None, mio=None):
    """[{mio, suo, ...conti}] per ogni coppia tuo mazzo x suo archetipo, dalla piu' giocata."""
    g = {}
    for r in recs:
        if (fmt is None or r["formato"] == fmt) and (mio is None or r["mio"] == mio):
            g.setdefault((r["mio"], r["suo"]), []).append(r)
    out = [dict(mio=a, suo=b, **_conta(rr)) for (a, b), rr in g.items()]
    return sorted(out, key=lambda x: (-x["partite"], x["mio"], x["suo"]))


def campo(recs, fmt=None, dal=None):
    """[{suo, quota, ...conti}]: cosa incontri (dal giorno ISO dal), dalla piu' vista."""
    rr = [r for r in recs if (fmt is None or r["formato"] == fmt) and (dal is None or r["giorno"] >= dal)]
    g = {}
    for r in rr:
        g.setdefault(r["suo"], []).append(r)
    out = [dict(suo=s, quota=round(100 * len(x) / len(rr), 1), **_conta(x)) for s, x in g.items()]
    return sorted(out, key=lambda x: (-x["partite"], x["suo"]))


def per_giorno(recs, fmt=None):
    """{giorno: {suo: partite}}: la storia del campo, per i grafici."""
    out = {}
    for r in recs:
        if fmt is None or r["formato"] == fmt:
            d = out.setdefault(r["giorno"], {})
            d[r["suo"]] = d.get(r["suo"], 0) + 1
    return dict(sorted(out.items()))


def aggiorna():
    """Rilegge i log e rifa' la banca dati -> i record."""
    recs = records()
    try:
        salva(recs)
    except (OSError, sqlite3.Error):
        pass
    return recs


def prova():
    import tempfile
    casi = []
    meta = [dict(nome="Mono-White Auras", colori="W", quota=10, lista={"Ethereal Armor": 4, "Sheltered by Ghosts": 4, "Seam Rip": 2, "Plains": 20}),
            dict(nome="Izzet Prowess", colori="UR", quota=8, lista={"Opt": 4, "Lightning Strike": 4, "Stormchaser's Talent": 3, "Island": 8})]
    arch = archetipi(None, meta)
    casi.append(("le terre non entrano nelle liste degli archetipi", all("plains" not in p and "island" not in p for _n, _c, p, _q in arch)))
    casi.append(("due carte della lista bastano: Mono-White Auras", riconosci(["Ethereal Armor", "Sheltered by Ghosts", "Plains"], "x", arch)[0] == "Mono-White Auras"))
    casi.append(("negativa: una carta sola non basta, resta coi colori", riconosci(["Ethereal Armor", "Plains"], "x", arch)[0] == "Mono-White"))
    casi.append(("negativa: un colore fuori dall'archetipo lo esclude", riconosci(["Opt", "Lightning Strike", "Ethereal Armor"], "x", arch)[0] != "Mono-White Auras"
                 and solo_colori(riconosci(["Opt", "Lightning Strike", "Ethereal Armor"], "x", arch)[0])))
    casi.append(("una carta sola fuori colore non cambia il mazzo: resta Mono-White Auras",
                 riconosci(["Ethereal Armor", "Sheltered by Ghosts", "Opt"], "x", arch)[0] == "Mono-White Auras"))
    casi.append(("senza magie viste: Unknown", riconosci(["Plains", "Island"], "x", arch)[0] == "Unknown"))
    casi.append(("i formati: Ladder e Play Standard, Sparky fuori, draft limited, precon a parte",
                 formato("Ladder") == formato("Play") == formato("Constructed_Event_2026") == "standard" and formato("AIBotMatch_Rebalanced") is None
                 and formato("QuickDraft_FRA_20261008") == "limited" and formato("DualColorPrecons") == "precon" and formato("Historic_Ladder") == "historic"))
    recs = [dict(partita=str(i), giorno="2026-11-1%d" % (i % 3), formato="standard", evento="Ladder", mio="UW Bouncer", suo="Mono-White Auras" if i < 6 else "Izzet Prowess",
                 punti=2.0, colori_suoi="W", carte_viste=3, vinta=i in (0, 1, 2, 6), inizia=(i % 2 == 0), mulligan=1 if i == 3 else 0, turni=8 + i, rango="Gold")
            for i in range(8)]
    t = {(x["mio"], x["suo"]): x for x in tabella(recs, "standard")}
    a = t[("UW Bouncer", "Mono-White Auras")]
    casi.append(("i conti del matchup: 3-3, play 2-1 e draw 1-2, un mulligan su 6", (a["vinte"], a["perse"]) == (3, 3) and a["play"] == (3, 2) and a["draw"] == (3, 1)
                 and abs(a["mulligan"] - 16.7) < 0.1 and not a["poche"]))
    lo, hi = wilson(3, 6)
    casi.append(("l'intervallo di Wilson contiene il 50% e si stringe con le partite", lo < 50 < hi and (wilson(30, 60)[1] - wilson(30, 60)[0]) < (hi - lo)))
    casi.append(("negativa: 2 partite sono poche", t[("UW Bouncer", "Izzet Prowess")]["poche"]))
    c = campo(recs, "standard")
    casi.append(("il campo: quote che fanno 100", abs(sum(x["quota"] for x in c) - 100) < 0.2 and c[0]["suo"] == "Mono-White Auras"))
    d = tempfile.mkdtemp()
    f = salva(recs, os.path.join(d, "b.sqlite"))
    db = sqlite3.connect(f)
    q = db.execute("SELECT suo, count(*), sum(vinta) FROM partite WHERE formato='standard' GROUP BY suo ORDER BY suo").fetchall()
    db.close()
    casi.append(("la banca dati su disco risponde come i conti", q == [("Izzet Prowess", 2, 1), ("Mono-White Auras", 6, 3)]))
    for n, v in casi:
        print(("ok    " if v else "ROSSO ") + n)
    ok = sum(1 for _n, v in casi if v)
    print(f"{ok}/{len(casi)}")
    return ok == len(casi)


def stampa():
    recs = aggiorna()
    print(f"{len(recs)} partite nella banca dati ({BANCA})")
    for fmt in ("standard", "precon", "limited"):
        rr = [r for r in recs if r["formato"] == fmt]
        if not rr:
            continue
        print(f"\n== {fmt}: {len(rr)} partite · il campo")
        for x in campo(recs, fmt)[:12]:
            print(f"  {x['suo'][:34]:34} {x['quota']:5.1f}%  {x['vinte']:3}-{x['perse']:<3} {x['wr'] or 0:5.1f}%  [{x['basso']}-{x['alto']}]")
        print(f"-- matchup dei tuoi mazzi (da {MIN_PARTITE} partite)")
        for x in tabella(recs, fmt):
            if not x["poche"]:
                print(f"  {x['mio'][:24]:24} vs {x['suo'][:30]:30} {x['vinte']:3}-{x['perse']:<3} {x['wr']:5.1f}%  play {x['play'][1]}-{x['play'][0] - x['play'][1]}"
                      f"  draw {x['draw'][1]}-{x['draw'][0] - x['draw'][1]}")
    riconosciute = [r for r in recs if r["formato"] == "standard"]
    if riconosciute:
        n = sum(1 for r in riconosciute if not solo_colori(r["suo"]) and r["suo"] != "Unknown")
        print(f"\narchetipo riconosciuto in {n} partite su {len(riconosciute)} dello Standard")


if __name__ == "__main__":
    if "--prova" in sys.argv:
        sys.exit(0 if prova() else 1)
    stampa()
