"""L'HUD del mazzo avversario: cosa dicono le sue carte viste (sessione Magic 15, 12 nov 2026).

Autore, 12 nov 2026: «e se schedassimo i mazzi e non i giocatori? come la celebre app per il poker che ha un hud per i giocatori, se noi facessimo la
stessa cosa per i mazzi?». Gli HUD del poker (PokerTracker, Hold'em Manager) mettono accanto a ogni giocatore le sue statistiche; qui l'oggetto e' il
**mazzo**: da quello che l'avversario mostra si riconosce l'archetipo e si dice cosa fa di solito. Nessun nome, nessun id di giocatore entra nei conti, si
salva o si condivide (Termini d'uso di Wizards §2.2, Codice di condotta §2, GDPR). Negli eventi competitivi sanzionati l'HUD tace. La nota: Note/HUD_Mazzo.md.

Il costruito (Standard, Historic...):
- **L'archetipo con la confidenza.** Bayes ingenuo sulle sue magie viste contro le liste del meta del formato (i file della pagina Meta). A priori la quota di
  ogni archetipo nel meta e una parte «Other» per i mazzi fuori dal meta, misurata sulla banca dati delle tue partite (matchup_log). Verosimiglianza di una
  carta: nella lista dell'archetipo la presenza per copie (PRESENZA), fuori dalla lista FUORI, fuori dai suoi colori FUORI_COLORE; in «Other» la frequenza
  della carta nel meta, almeno POP_MIN. Le terre non contano. Grado C: Untapped da' una lista sola per archetipo, quindi la presenza per copie e' una stima
  (misura in Note/HUD_Mazzo.md: `--misura` rifa' la prova sulle tue partite archiviate).
- **Le carte probabili:** P(nelle sue 60) = somma sugli archetipi di P(archetipo) x presenza; quelle gia' viste no.
- **T2-T4 e chiusura:** le sue magie al suo 2°, 3° e 4° turno nelle tue partite archiviate contro quell'archetipo (Partite/, da 3 partite); senza, la curva
  della lista (le magie da 2, 3, 4 mana con piu' copie). La chiusura: il suo turno medio nelle partite che hai perso contro di lui.
- **Le istantanee da temere:** istantanei e carte con lampo che la sua lista probabile ha, che il suo mana aperto paga, con la P.
- **Il tuo win rate contro l'archetipo**, sul play e sul draw, con tutti i mazzi e con quello che stai giocando (banca dati delle tue partite).
Il limited: l'archetipo e' la coppia di colori delle sue magie; a priori la quota di ogni coppia nei dati pubblici di 17Lands del Premier del set
(Motore/limited_17lands.py, CC BY 4.0), che danno anche win rate, play e draw, il turno medio delle vittorie e la coppia contro la tua. Le istantanee: le
carte del set nei suoi colori che il suo mana paga, dalle piu' giocate su 17Lands.

    py -I -X utf8 Companion/App/Schede/Meta/hud_mazzo.py "Carta 1" "Carta 2" [--formato standard] [--aperte 2]   l'HUD a testo
    py -I -X utf8 Companion/App/Schede/Meta/hud_mazzo.py --vivo                                                 l'HUD della partita nel Player.log
    py -I -X utf8 Companion/App/Schede/Meta/hud_mazzo.py --misura                                               la prova sulle partite archiviate
    py -I -X utf8 Companion/App/Schede/Meta/hud_mazzo.py --prova                                                un meta finto, con le negative
"""
import os, sys
_casa = os.path.dirname(os.path.abspath(__file__))      # si sale fino a percorsi.py, che mette nel sys.path tutte le cartelle del Companion
while not os.path.isfile(os.path.join(_casa, "percorsi.py")):
    _casa = os.path.dirname(_casa)
if _casa not in sys.path:
    sys.path.insert(0, _casa)
import percorsi  # noqa: E402
import glob  # noqa: E402
import json  # noqa: E402
import math  # noqa: E402
import re  # noqa: E402
import threading  # noqa: E402
import matchup_log as ML  # noqa: E402

PRESENZA = {1: 0.55, 2: 0.75, 3: 0.9, 4: 0.95}     # P che la carta sia nelle sue 60 se la lista dell'archetipo ne ha N copie (grado C)
FUORI = 0.06            # una carta che la lista dell'archetipo non ha: flessibili, sideboard. Tarata il 12 nov 2026 sulla meta' delle tue partite archiviate perche' la confidenza sia onesta (0,03: 10 punti troppo sicura), verificata sull'altra meta'
FUORI_COLORE = 0.002    # una carta fuori dai colori dell'archetipo
POP_MIN = 0.05          # in un mazzo fuori dal meta: almeno questa P per una carta qualsiasi (piu' di FUORI: una carta di nessuna lista spinge verso Other)
POP_ALTRO = 0.5         # un mazzo fuori dal meta ha le carte del meta la meta' delle volte del meta stesso (grado C)
ALTRO = 0.35            # la parte dei mazzi fuori dal meta quando la banca dati non basta a misurarla (grado C)
MIN_ARCHIVIO = 3        # partite archiviate per dire cosa fa al T2-T4
ARCHIVIO = os.path.join(percorsi.ROOT, "Partite")
_LOCK = threading.Lock()
_CARTE = {}
_MEMO = {}


def _k(n):
    return (n or "").split(" // ")[0].strip().lower()


def carte():
    """{nome minuscolo: dict(nome, cmc, colori, tipo, lampo, terra, istantaneo, set)} dal database delle carte di Arena (una volta per processo)."""
    with _LOCK:
        if not _CARTE:
            import db_carte
            t = db_carte.testi()
            for c in db_carte.carte():
                n = t.get(c.get("titleId"))
                if not n or c.get("isToken"):
                    continue
                k = _k(n)
                tipo = t.get(c.get("cardTypeTextId")) or ""
                lampo = any(t.get(a.get("TextId")) == "Flash" for a in c.get("abilities") or [])
                col = "".join(ML.COLORI[i - 1] for i in (c.get("colors") or []) if 1 <= i <= 5)
                v = _CARTE.get(k)
                seconda = bool(c.get("isSecondaryCard"))     # la faccia «preparata» di FRA (Molten Tide): non si lancia dalla mano
                if v is None:
                    _CARTE[k] = dict(nome=n.split(" // ")[0], cmc=c.get("cmc") or 0, colori=col, tipo=tipo, lampo=lampo, terra="Land" in tipo,
                                     istantaneo="Instant" in tipo, set={c.get("set")}, seconda=seconda)
                else:
                    v["lampo"] = v["lampo"] or lampo
                    v["seconda"] = v["seconda"] and seconda
                    v["set"].add(c.get("set"))
    return _CARTE


def info(n):
    return carte().get(_k(n)) or dict(nome=n, cmc=0, colori="", tipo="", lampo=False, terra=False, istantaneo=False, set=set(), seconda=False)


def presenza(q):
    return PRESENZA.get(max(1, min(4, int(q or 0))), 0.95) if q else 0.0


# --------------------------------------------------------------------------------------------------------------- il costruito: il modello del meta
def modello(fmt, meta=None, altro=None):
    """Il modello di un formato: archetipi [(nome, colori, {carta: copie}, quota)] dalle liste del meta (solo le magie), la frequenza di ogni carta nel meta e
    la parte «Other». meta: la lista degli archetipi (per le prove); se no il file della pagina Meta."""
    chiave = ("modello", fmt, altro)
    if meta is None and chiave in _MEMO:
        return _MEMO[chiave]
    if meta is None:
        meta = []
        if fmt in ML.META_FMT:
            try:
                import dati_meta
                with open(dati_meta.file_meta(ML.META_FMT[fmt]), encoding="utf-8") as f:
                    meta = json.load(f)
            except (OSError, ValueError, ImportError):
                meta = []
    arch = []
    for a in meta if isinstance(meta, list) else []:
        lista = {_k(n): q for n, q in (a.get("lista") or {}).items() if not info(n)["terra"]}
        if lista and (a.get("quota") or 0) > 0:
            arch.append(dict(nome=a.get("nome") or "?", colori="".join(x for x in ML.COLORI if x in (a.get("colori") or "")), lista=lista,
                             quota=float(a["quota"]), nomi={_k(n): n for n in a.get("lista") or {}}))
    tot = sum(a["quota"] for a in arch) or 1
    pop = {}
    for a in arch:
        for c, q in a["lista"].items():
            pop[c] = pop.get(c, 0) + a["quota"] / tot * presenza(q)
    out = dict(formato=fmt, archetipi=arch, pop=pop, altro=ALTRO if altro is None else altro)
    if meta is None:        # dal file: ricordato per formato (il file del meta cambia ogni 6 ore, l'HUD si rifa' a ogni carta)
        _MEMO[chiave] = out
    return out


def altro_misurato(recs, fmt):
    """La parte dei mazzi fuori dal meta fra le tue partite del formato con almeno 3 sue magie viste (None se sono meno di 30)."""
    rr = [r for r in recs if r["formato"] == fmt and r["carte_viste"] >= 3]
    if len(rr) < 30:
        return None
    return round(sum(1 for r in rr if ML.solo_colori(r["suo"])) / len(rr), 3)


def posteriori(visti, mod):
    """[(archetipo, P)] dalle sue carte viste, dalla piu' probabile; «Other» e' un mazzo fuori dal meta. Senza magie viste: la quota del meta."""
    viste = []
    for n in visti:
        i = info(n)
        if not i["terra"] and _k(n) not in viste:
            viste.append(_k(n))
    arch = mod["archetipi"]
    tot = sum(a["quota"] for a in arch) or 1
    log = []
    for a in arch:
        lp = math.log((1 - mod["altro"]) * a["quota"] / tot)
        for c in viste:
            if c in a["lista"]:
                p = presenza(a["lista"][c])
            elif not set(info(c)["colori"]) <= set(a["colori"] or ML.COLORI):
                p = FUORI_COLORE
            else:
                p = FUORI
            lp += math.log(p)
        log.append((a["nome"], lp))
    lp = math.log(mod["altro"]) + sum(math.log(max(POP_MIN, POP_ALTRO * mod["pop"].get(c, 0))) for c in viste)
    log.append(("Other", lp))
    m = max(x for _n, x in log)
    s = sum(math.exp(x - m) for _n, x in log)
    return sorted(((n, math.exp(x - m) / s) for n, x in log), key=lambda z: -z[1])


def probabili(post, mod, visti, quante=8, soglia=0.15):
    """[(nome, P nelle sue 60, copie nella lista piu' probabile che l'ha)] delle carte non ancora viste."""
    pv = dict(post)
    viste = {_k(n) for n in visti}
    p, copie, nomi = {}, {}, {}
    for a in mod["archetipi"]:
        w = pv.get(a["nome"], 0)
        if w < 0.01:
            continue
        for c, q in a["lista"].items():
            p[c] = p.get(c, 0) + w * presenza(q)
            if w > copie.get(c, (0, 0))[0]:
                copie[c] = (w, q)
            nomi.setdefault(c, a["nomi"].get(c, c))
    w_o = pv.get("Other", 0)
    for c in p:
        p[c] += w_o * POP_ALTRO * mod["pop"].get(c, 0)
    out = [(nomi[c], round(v, 3), copie[c][1]) for c, v in p.items() if c not in viste and v >= soglia]
    return sorted(out, key=lambda z: (-z[1], z[0]))[:quante]


def istantanee(post, mod, visti, aperte, quante=5, soglia=0.10):
    """[(nome, costo, P, gia' vista)] degli istantanei e delle carte con lampo che il suo mana aperto paga."""
    pv = dict(post)
    viste = {_k(n) for n in visti}
    p, nomi = {}, {}
    for a in mod["archetipi"]:
        w = pv.get(a["nome"], 0)
        if w < 0.01:
            continue
        for c, q in a["lista"].items():
            i = info(c)
            if (i["istantaneo"] or i["lampo"]) and not i["seconda"] and i["cmc"] <= aperte:
                p[c] = p.get(c, 0) + w * presenza(q)
                nomi.setdefault(c, a["nomi"].get(c, i["nome"]))
    out = [(nomi[c], info(c)["cmc"], 1.0 if c in viste else round(v, 3), c in viste) for c, v in p.items() if v >= soglia or c in viste]
    return sorted(out, key=lambda z: (-z[2], z[1], z[0]))[:quante]


# --------------------------------------------------------------------------------------------------------------- le tue partite: archivio e banca dati
def _archivio():
    """{matchId: scheda} delle partite archiviate (Partite/, archivio_partite.py), ricordato finche' la cartella non cambia."""
    try:
        firma = (os.path.getmtime(ARCHIVIO), len(os.listdir(ARCHIVIO)))
    except OSError:
        return {}
    v = _MEMO.get("archivio")
    if v and v[0] == firma:
        return v[1]
    out = {}
    for f in glob.glob(os.path.join(ARCHIVIO, "*.json")):
        try:
            with open(f, encoding="utf-8") as fh:
                d = json.load(fh)
        except (OSError, ValueError):
            continue
        if d.get("matchId"):
            out[d["matchId"]] = dict(eventi=[e for e in d.get("eventi") or [] if e.get("chi") == "lui" and e.get("tipo") == "lancia"])
    _MEMO["archivio"] = (firma, out)
    return out


def suo_turno(t, lui_comincia):
    """Il numero del suo turno dal numero del turno della partita, o None se il turno della partita e' tuo."""
    if lui_comincia:
        return (t + 1) // 2 if t % 2 == 1 else None
    return t // 2 if t % 2 == 0 else None


def curva(arch, recs, mod=None, archivio=None):
    """{"fonte": "partite"|"lista", "partite": N, 2: [(nome, quota)], 3: [...], 4: [...]}: cosa gioca al suo 2°, 3° e 4° turno."""
    archivio = _archivio() if archivio is None else archivio
    rr = [r for r in recs if r["suo"] == arch and r["partita"] in archivio and r["inizia"] is not None]
    if len(rr) >= MIN_ARCHIVIO:
        conta = {2: {}, 3: {}, 4: {}}
        for r in rr:
            visti = {2: set(), 3: set(), 4: set()}
            for e in archivio[r["partita"]]["eventi"]:
                k = suo_turno(e.get("t") or 0, not r["inizia"])
                if k in visti and not info(e.get("carta"))["terra"]:
                    visti[k].add(e["carta"])
            for k, s in visti.items():
                for n in s:
                    conta[k][n] = conta[k].get(n, 0) + 1
        out = dict(fonte="partite", partite=len(rr))
        for k, d in conta.items():
            out[k] = sorted(((n, round(q / len(rr), 2)) for n, q in d.items()), key=lambda z: (-z[1], z[0]))[:2]
        return out
    a = next((x for x in (mod or {}).get("archetipi") or [] if x["nome"] == arch), None)
    if not a:
        return None
    out = dict(fonte="lista", partite=len(rr))
    for k in (2, 3, 4):
        cc = [(a["nomi"].get(c, c), q) for c, q in a["lista"].items() if info(c)["cmc"] == k]
        out[k] = [(n, None) for n, _q in sorted(cc, key=lambda z: (-z[1], z[0]))[:2]]
    return out


def contro(arch, recs, fmt, mio=None):
    """I tuoi conti contro un archetipo: dict(tutti=conti, mazzo=conti col tuo mazzo, chiude=suo turno medio nelle tue sconfitte)."""
    rr = [r for r in recs if r["formato"] == fmt and r["suo"] == arch]
    perse = [r["turni"] for r in rr if not r["vinta"] and r["turni"]]
    mm = [r for r in rr if mio and r["mio"] == mio]
    return dict(tutti=ML._conta(rr) if rr else None, mazzo=ML._conta(mm) if mm else None,
                chiude=round(sum(math.ceil(t / 2) for t in perse) / len(perse), 1) if perse else None, perse=len(perse))


# --------------------------------------------------------------------------------------------------------------- il limited: 17Lands
def set_evento(evento):
    m = re.search(r"(?:Draft|Sealed|Cube)_([A-Z0-9]{2,4})_", evento or "")
    return m.group(1) if m else None


def colori_mazzo(nomi):
    """La coppia di colori di un tuo mazzo di limited: i due colori con piu' magie, piu' un terzo da 5 magie in su (uno splash di 2 carte non conta)."""
    conta = {}
    for n in nomi:
        i = info(n)
        if not i["terra"]:
            for x in i["colori"]:
                conta[x] = conta.get(x, 0) + 1
    cc = sorted(conta, key=lambda x: -conta[x])
    tieni = cc[:2] + [x for x in cc[2:3] if conta[x] >= 5]
    return "".join(x for x in ML.COLORI if x in tieni)


def coppie_limited(colori, storia):
    """[(chiave colori, nome, P)] delle coppie di 17Lands che contengono i colori visti, pesate per partite (la quota nel formato)."""
    cc = (storia or {}).get("coppie") or {}
    nomi = (storia or {}).get("nomi") or {}
    vv = [(k, v.get("n") or 0) for k, v in cc.items() if set(colori) <= set(k) and 1 < len(k) <= 3]
    tot = sum(n for _k_, n in vv) or 1
    return sorted(((k, nomi.get(k) or ML.nome_colori(k), n / tot) for k, n in vv), key=lambda z: -z[2])


def istantanee_limited(set_, colori, aperte, quante=5):
    """[(nome, costo, GIH o None)] delle carte del set con istantaneo o lampo, nei suoi colori, che il suo mana paga, dalle piu' giocate su 17Lands."""
    gih = {}
    try:
        import progetto as PR
        with open(PR.file("anagrafe", set_), encoding="utf-8") as f:
            for v in (json.load(f).get("carte") or {}).values():
                g = (v.get("gih") or {}).get("premier") or {}
                gih[_k(v.get("nome"))] = (g.get("partite") or 0, g.get("gih"))
    except Exception:       # noqa: BLE001 - senza il quaderno del set: le carte del set senza ordine di 17Lands
        gih = {}
    out = []
    for k, i in carte().items():
        if set_ in i["set"] and (i["istantaneo"] or i["lampo"]) and not i["terra"] and not i["seconda"] and i["cmc"] <= aperte and i["colori"] and set(i["colori"]) <= set(colori):
            n, g = gih.get(k, (0, None))
            out.append((i["nome"], i["cmc"], round(g, 1) if g else None, n))
    out.sort(key=lambda z: (-z[3], z[0]))
    return [x[:3] for x in out[:quante]]


# --------------------------------------------------------------------------------------------------------------- il tuo mazzo
def nostro(s, recs, quante=6):
    """Il pannello del tuo mazzo (Autore, 12 nov 2026: «sulla sinistra mettiamo il suo mazzo sulla destra il nostro»): il nome, quante carte restano nel
    grimorio, le magie che peschi piu' probabilmente alla prossima pescata (copie rimaste / grimorio: le carte fuori dal grimorio si leggono dalle zone), le
    terre rimaste, e il record del mazzo (banca dati). None senza la lista del mazzo nel log."""
    mazzo = {}
    for g in s.get("mio_mazzo") or []:
        mazzo[g] = mazzo.get(g, 0) + 1
    if not mazzo:
        return None
    import hud_partita
    fuori = s.get("mie_fuori") or {}
    resto, totali = {}, {}
    for g, q in mazzo.items():
        n = hud_partita.nome_grp(g)
        if n:
            resto[n] = resto.get(n, 0) + max(0, q - fuori.get(g, 0))
            totali[n] = totali.get(n, 0) + q
    tot = sum(resto.values())
    N = s.get("grimorio") or tot
    if not N:
        return None
    terre = sum(q for n, q in resto.items() if info(n)["terra"])
    carte = sorted(((n, q, round(min(1.0, q / N), 3)) for n, q in resto.items() if q and not info(n)["terra"]), key=lambda z: (-z[2], z[0]))[:quante]
    fmt = ML.formato(s.get("evento"))
    tutte = s.get("mio_mazzo_nomi") or []
    nome = s.get("mazzo") if fmt not in ("limited", None) else None
    if fmt == "limited":
        nome = ML.nome_colori(colori_mazzo(tutte))
    rr = [r for r in recs or [] if r["formato"] == fmt and nome and r["mio"] == nome]
    # la lista intera (Autore, 12 nov 2026: «il mio deck deve dirmi quante carte mie ho in quante copie, man mano che scendono mi aggiorna il numero e mi da la %
    # di trovarle alla prossima pescata»): (nome, costo, rimaste, nel mazzo, P alla prossima pescata, terra), le magie per costo e le terre in fondo
    lista = sorted(((n, info(n)["cmc"], resto[n], totali[n], round(min(1.0, resto[n] / N), 3), info(n)["terra"]) for n in totali),
                   key=lambda z: (z[5], z[1], z[0]))
    return dict(nome=nome or "Your deck", grimorio=N, carte=carte, terre=terre, p_terra=round(terre / N, 3), record=ML._conta(rr) if rr else None, lista=lista)


# --------------------------------------------------------------------------------------------------------------- l'HUD
def scheda(stato, recs=None, meta=None, storia=None, archivio=None):
    """Tutto quello che l'HUD mostra, da uno stato di hud_partita (o un dict con evento, sue_nomi, aperte, sul_play, mazzo, mio_mazzo_nomi)."""
    s = stato or {}
    ev = s.get("evento") or ""
    out = dict(magie_viste=len(ML.magie(list(s.get("sue_nomi") or []))) if s.get("sue_nomi") else 0, evento=ev, turno=s.get("turno"), aperte=s.get("aperte") or 0, sul_play=s.get("sul_play"), finita=s.get("finita"), visti=list(s.get("sue_nomi") or []))
    if s.get("competitivo"):
        return dict(out, tipo="spento", motivo="Competitive event: the HUD stays off (sanctioned events forbid outside assistance).")
    fmt = ML.formato(ev)
    if fmt is None:
        return dict(out, tipo="spento", motivo="Sparky: no deck to read.")
    out["formato"] = fmt
    if recs is None:
        try:
            recs = ML.records()
        except Exception:       # noqa: BLE001 - senza le tue partite l'HUD dice solo il mazzo
            recs = []
    out["mio"] = nostro(s, recs)
    visti = out["visti"]
    if fmt == "limited":
        set_ = set_evento(ev)
        if storia is None and set_:
            import dati_grafici
            storia = dati_grafici.storia_17lands(set_)
        col = ML.colori_di(visti) if ML.magie(visti) else ""
        cc = coppie_limited(col, storia) if storia and col else []
        out.update(tipo="limited", set=set_, colori=col, coppie=cc[:3], fonte="17Lands Premier " + (set_ or "") + " (CC BY 4.0)" if storia else None)
        mio_col = colori_mazzo(s.get("mio_mazzo_nomi") or [])
        if cc:
            k = cc[0][0]
            v = storia["coppie"][k]
            out["l17"] = dict(coppia=cc[0][1], wr=round(100 * v["w"] / v["n"], 1) if v.get("n") else None,
                              play=round(100 * v["play"][1] / v["play"][0], 1) if (v.get("play") or [0])[0] else None,
                              draw=round(100 * v["draw"][1] / v["draw"][0], 1) if (v.get("draw") or [0])[0] else None,
                              chiude=v.get("turni_vinte"), partite=v.get("n"))
            x = ((v.get("contro") or {}).get(mio_col)) if mio_col else None
            if x and x[0] >= 200:       # sotto 200 partite la matrice di 17Lands e' rumore (come nella vista Charts)
                out["l17"]["tu_contro"] = dict(coppia=ML.nome_colori(mio_col), wr=round(100 * (1 - x[1] / x[0]), 1), partite=x[0])
            nome = cc[0][1]
            out["contro"] = contro(nome, recs, "limited")
        out["istantanee"] = istantanee_limited(set_, col or "WUBRG", out["aperte"]) if set_ and col else []
        return out
    if fmt == "precon":
        col = ML.colori_di(visti) if ML.magie(visti) else ""
        nome = ML.nome_colori(col) if col else "Unknown"
        return dict(out, tipo="precon", archetipi=[(nome, None)], contro=contro(nome, recs, fmt, s.get("mazzo")))
    altro = altro_misurato(recs, fmt)
    mod = modello(fmt, meta, altro)
    if not mod["archetipi"]:
        return dict(out, tipo="spento", motivo=f"No meta lists for {fmt}.")
    post = posteriori(visti, mod)
    top = post[0][0]
    # un mazzo fuori dal meta si chiama coi colori delle sue magie, come nella banca dati (matchup_log: «Boros»): i tuoi conti contro di lui sono quelli
    # mai «Other» (12 nov 2026): fuori dal meta i soli colori, senza magie viste «Unknown colors»
    altro = ML.nome_colori(ML.colori_di(visti)) if ML.magie(visti) else "Unknown colors"
    out.update(tipo="costruito", archetipi=[(altro if n == "Other" else n, p) for n, p in post[:3]], altro=mod["altro"], probabili=probabili(post, mod, visti),
               istantanee=istantanee(post, mod, visti, out["aperte"]),
               curva=curva(top, recs, mod, archivio) if top != "Other" else None, contro=contro(altro if top == "Other" else top, recs, fmt, s.get("mazzo")))
    return out


def testo(h):
    """L'HUD a righe di testo (per la riga di comando e le prove)."""
    r = []
    if h.get("tipo") == "spento":
        return [h.get("motivo") or ""]
    pp = "on the play" if h.get("sul_play") else "on the draw" if h.get("sul_play") is False else ""
    r.append(f"OPPONENT DECK · {h.get('formato')} · turn {h.get('turno') or '-'} {pp} · {h.get('aperte')} open")
    if h["tipo"] == "limited":
        r += [f"  {n} {round(100 * p)}%" for _k_, n, p in h.get("coppie") or []] or ["  no spell seen yet"]
        x = h.get("l17")
        if x:
            r.append(f"  17Lands: {x['coppia']} wins {x['wr']}% · play {x['play']}% · draw {x['draw']}% · wins close on T{x['chiude']}")
            if x.get("tu_contro"):
                r.append(f"  {x['tu_contro']['coppia']} vs it: {x['tu_contro']['wr']}% on {x['tu_contro']['partite']} games")
    else:
        r += [f"  {n} {round(100 * p)}%" if p is not None else f"  {n}" for n, p in h.get("archetipi") or []]
        if h.get("probabili"):
            r.append("  LIKELY: " + ", ".join(f"{n} {round(100 * p)}%" for n, p, _q in h["probabili"]))
        c = h.get("curva")
        if c:
            r.append(f"  T2-T4 ({'your ' + str(c['partite']) + ' games' if c['fonte'] == 'partite' else 'from the list'}): "
                     + " | ".join(f"T{k} " + ", ".join(n for n, _q in c.get(k) or []) for k in (2, 3, 4)))
    if h.get("istantanee"):
        r.append(f"  WITH {h['aperte']} OPEN: " + ", ".join(x[0] for x in h["istantanee"]))
    c = h.get("contro") or {}
    if c.get("tutti"):
        t = c["tutti"]
        r.append(f"  YOU VS IT: {t['vinte']}-{t['perse']} ({t['wr']}%) · play {t['play'][1]}-{t['play'][0] - t['play'][1]} · draw {t['draw'][1]}-{t['draw'][0] - t['draw'][1]}"
                 + (f" · it closes on its T{c['chiude']}" if c.get("chiude") else ""))
    return r


# --------------------------------------------------------------------------------------------------------------- la misura e le prove
def misura(recs=None, archivio=None, fmt="standard"):
    """La prova sulle tue partite archiviate: con le sue prime k magie viste (in ordine), l'archetipo in testa e' quello della partita intera
    (matchup_log, che legge tutte le sue carte)? E la confidenza e' onesta (media della P contro la quota di giuste)?"""
    recs = ML.records() if recs is None else recs
    archivio = _archivio() if archivio is None else archivio
    mod = modello(fmt, None, altro_misurato(recs, fmt))
    rr = [r for r in recs if r["formato"] == fmt and r["partita"] in archivio and not r["suo"].startswith("Unknown")]
    out = {}
    for k in (1, 2, 3, 4):
        giuste, conf, n = 0, 0.0, 0
        for r in rr:
            ordine = []
            for e in archivio[r["partita"]]["eventi"]:
                c = e.get("carta")
                if c and not info(c)["terra"] and c not in ordine:
                    ordine.append(c)
            if len(ordine) < k:
                continue
            post = posteriori(ordine[:k], mod)
            atteso = "Other" if ML.solo_colori(r["suo"]) else r["suo"]
            giuste += post[0][0] == atteso
            conf += post[0][1]
            n += 1
        out[k] = dict(partite=n, giuste=round(100 * giuste / n, 1) if n else None, confidenza=round(100 * conf / n, 1) if n else None)
    return out


def prova():
    casi = []
    meta = [dict(nome="Mono-White Auras", colori="W", quota=10, lista={"Ethereal Armor": 4, "Sheltered by Ghosts": 4, "Seam Rip": 2, "Plains": 20}),
            dict(nome="Izzet Prowess", colori="UR", quota=8, lista={"Opt": 4, "Lightning Strike": 4, "Spell Pierce": 2, "Island": 8, "Mountain": 8}),
            dict(nome="Boros Burn", colori="WR", quota=6, lista={"Lightning Strike": 4, "Shock": 4, "Seam Rip": 1, "Mountain": 10})]
    mod = modello("x", meta, 0.3)
    p0 = [n for n, _p in posteriori([], mod)]
    casi.append(("senza carte viste: Other (30%) poi gli archetipi per quota", p0 == ["Other", "Mono-White Auras", "Izzet Prowess", "Boros Burn"]))
    p = posteriori(["Ethereal Armor", "Sheltered by Ghosts"], mod)
    casi.append(("due carte della lista: Mono-White Auras oltre il 90%", p[0][0] == "Mono-White Auras" and p[0][1] > 0.9))
    p1 = posteriori(["Lightning Strike"], mod)
    casi.append(("una carta di due liste: Izzet e Boros si dividono la P", {p1[0][0], p1[1][0]} == {"Izzet Prowess", "Boros Burn"} and p1[0][1] < 0.8))
    p2 = posteriori(["Lightning Strike", "Opt"], mod)
    casi.append(("la seconda carta decide: Izzet Prowess", p2[0][0] == "Izzet Prowess" and p2[0][1] > p1[0][1]))
    p3 = posteriori(["Llanowar Elves", "Giant Growth", "Ethereal Armor"], mod)
    casi.append(("negativa: carte di nessuna lista e fuori colore portano a Other", p3[0][0] == "Other"))
    casi.append(("negativa: le terre non contano", posteriori(["Plains", "Island", "Mountain"], mod) == posteriori([], mod)))
    pr = probabili(p2, mod, ["Lightning Strike", "Opt"])
    casi.append(("le probabili: Spell Pierce di Izzet, non le carte gia' viste", pr and pr[0][0] == "Spell Pierce"
                 and all(n not in ("Lightning Strike", "Opt") for n, _p, _q in pr)))
    ist = istantanee(p2, mod, ["Lightning Strike", "Opt"], aperte=1)
    casi.append(("con 1 mana aperto: Opt e Spell Pierce, non Lightning Strike (costa 2)", {x[0] for x in ist} >= {"Opt", "Spell Pierce"}
                 and "Lightning Strike" not in {x[0] for x in ist}))
    casi.append(("negativa: con 0 mana aperto nessuna istantanea", istantanee(p2, mod, ["Opt"], aperte=0) == []))
    casi.append(("i colori del tuo mazzo: due colori, lo splash di 2 carte no", colori_mazzo(["Opt", "Opt", "Lightning Strike", "Shock", "Spell Pierce",
                                                                                         "Ethereal Armor", "Seam Rip", "Island"]) == "UR"))
    recs = [dict(partita=f"m{i}", giorno="2026-11-12", formato="x", evento="Ladder", mio="UW Bouncer" if i < 3 else "Mono Red", suo="Izzet Prowess", punti=2.0,
                 colori_suoi="UR", carte_viste=3, vinta=i in (0, 3), inizia=i % 2 == 0, mulligan=0, turni=10 + i, rango=None) for i in range(4)]
    arch = {f"m{i}": dict(eventi=[dict(t=4 if i % 2 == 0 else 3, chi="lui", tipo="lancia", carta="Opt"), dict(t=6 if i % 2 == 0 else 5, chi="lui", tipo="lancia", carta="Lightning Strike")])
            for i in range(4)}
    c = curva("Izzet Prowess", recs, mod, arch)
    casi.append(("T2-T4 dalle tue partite: Opt al suo T2 e Lightning Strike al T3 in 4 su 4", c["fonte"] == "partite" and c[2] == [("Opt", 1.0)]
                 and c[3] == [("Lightning Strike", 1.0)]))
    casi.append(("il suo turno: sul draw il turno 4 della partita e' il suo 2°, il 3 e' tuo", suo_turno(4, False) == 2 and suo_turno(3, False) is None
                 and suo_turno(3, True) == 2))
    c2 = curva("Izzet Prowess", recs[:2], mod, arch)
    casi.append(("negativa: con 2 partite la curva viene dalla lista", c2["fonte"] == "lista" and c2[2][0][0] == "Lightning Strike"))
    k = contro("Izzet Prowess", recs, "x", "UW Bouncer")
    casi.append(("il tuo win rate contro l'archetipo, play e draw, e col tuo mazzo", k["tutti"]["vinte"] == 2 and k["tutti"]["play"] == (2, 1)
                 and k["mazzo"]["partite"] == 3 and k["chiude"] == 6.0))
    st = dict(evento="Ladder", sue_nomi=["Lightning Strike", "Opt"], aperte=1, sul_play=True, turno=5, mazzo="UW Bouncer")
    h = scheda(st, recs=[dict(r, formato="standard") for r in recs], meta=meta, archivio=arch)
    casi.append(("la scheda intera del costruito", h["tipo"] == "costruito" and h["archetipi"][0][0] == "Izzet Prowess" and h["contro"]["tutti"]["partite"] == 4))
    ho = scheda(dict(st, sue_nomi=["Llanowar Elves", "Giant Growth"]), recs=[dict(r, formato="standard", suo="Mono-Green") for r in recs], meta=meta, archivio=arch)
    casi.append(("fuori dal meta: «Mono-Green» (mai Other) e i tuoi conti contro quei mazzi", ho["archetipi"][0][0] == "Mono-Green"
                 and ho["contro"]["tutti"]["partite"] == 4 and ho["curva"] is None))
    casi.append(("negativa: evento competitivo, l'HUD tace", scheda(dict(st, competitivo=True))["tipo"] == "spento"))
    casi.append(("negativa: contro Sparky niente", scheda(dict(st, evento="AIBotMatch"))["tipo"] == "spento"))
    storia = dict(nomi=dict(WG="Selesnya", WU="Azorius", UG="Simic", WUG="Bant"),
                  coppie=dict(WG=dict(n=1000, w=560, play=[500, 290], draw=[500, 270], turni_vinte=9.5, contro=dict(UB=[400, 180])),
                              WU=dict(n=500, w=240, play=[250, 125], draw=[250, 115]), UG=dict(n=500, w=250, play=[1, 1], draw=[1, 0]),
                              WUG=dict(n=100, w=50, play=[1, 1], draw=[1, 0])))
    cc = coppie_limited("G", storia)
    casi.append(("limited: un verde visto, Selesnya in testa e Azorius fuori", cc[0][1] == "Selesnya" and all(k_ != "WU" for k_, _n, _p in cc)))
    hl = scheda(dict(evento="QuickDraft_XXX_20261112", sue_nomi=[], aperte=2), recs=[], storia=storia)
    casi.append(("negativa: limited senza magie viste, nessuna coppia", hl["tipo"] == "limited" and hl["coppie"] == []))
    import hud_partita
    hud_partita.nome_grp(0)
    gid = {n.lower(): g for g, n in hud_partita._NOMI.items()}
    mm = [gid["lightning strike"]] * 4 + [gid["opt"]] * 2 + [gid["island"]] * 4
    nn = nostro(dict(evento="Ladder", mazzo="Izzet Test", mio_mazzo=mm, mie_fuori={gid["lightning strike"]: 1, gid["island"]: 1}, grimorio=7),
                [dict(r, formato="standard", mio="Izzet Test") for r in recs])
    casi.append(("il tuo mazzo: 3 Lightning Strike su 7 nel grimorio (43%), 3 terre, il record del mazzo", nn["carte"][0] == ("Lightning Strike", 3, 0.429)
                 and nn["terre"] == 3 and nn["record"]["partite"] == 4 and nn["nome"] == "Izzet Test"))
    ls = {x[0]: x for x in nn["lista"]}
    casi.append(("la lista intera: copie rimaste su quelle del mazzo e la P, le terre in fondo", ls["Lightning Strike"][2:5] == (3, 4, 0.429)
                 and ls["Opt"][2:4] == (2, 2) and nn["lista"][-1][0] == "Island" and ls["Island"][2:4] == (3, 4)))
    casi.append(("negativa: senza la lista del mazzo nel log, niente pannello", nostro(dict(evento="Ladder"), []) is None))
    tutti = json.dumps(h, default=str) + json.dumps(hl, default=str)
    casi.append(("negativa: nell'HUD nessun campo del giocatore (nome, id)", not re.search(r'"(avversario|playerName|userId|opponent)"', tutti)))
    for n_, ok in casi:
        print(("ok    " if ok else "ROSSO ") + n_)
    print(f"{sum(ok for _n, ok in casi)}/{len(casi)}")
    return all(ok for _n, ok in casi)


def main():
    a = sys.argv[1:]
    if "--prova" in a:
        sys.exit(0 if prova() else 1)
    if "--misura" in a:
        for k, v in misura().items():
            print(f"prime {k} magie: {v['partite']} partite, archetipo giusto {v['giuste']}%, confidenza media {v['confidenza']}%")
        return
    if "--vivo" in a:
        import hud_partita
        st = hud_partita.Seguito().aggiorna()
        if not st:
            print("nessuna partita nel Player.log")
            return
    else:
        fmt = a[a.index("--formato") + 1] if "--formato" in a else "standard"
        aperte = int(a[a.index("--aperte") + 1]) if "--aperte" in a else 0
        nomi = [x for i, x in enumerate(a) if not x.startswith("--") and (i == 0 or a[i - 1] not in ("--formato", "--aperte"))]
        st = dict(evento={"standard": "Ladder"}.get(fmt, fmt.capitalize() + "_Ladder"), sue_nomi=nomi, aperte=aperte)
    for r in testo(scheda(st)):
        print(r)


if __name__ == "__main__":
    main()
