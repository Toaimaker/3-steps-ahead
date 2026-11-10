"""I dati che servono a piu' schede: collezione e jolly, partite costruite e di draft, meta, rarita', voti e colori delle carte."""
import collections
import datetime
import json
import os
import re

import progetto as PR

from ambiente import LOGDIR, ROOT
from dati_drafter import calendario as calendario_draft, colori_da_bit, data as data_draft, formato_quick
from tema import CI as C, LEGHE


def passaggi(ranghi):
    """I passaggi di lega in una fila di partite: ranghi = [(lega prima, lega dopo)] partita per partita. -> [(indice della
    partita, testo, lega)]: una promozione o una retrocessione dove la lega cambia dopo la partita, una stagione nuova dove la
    lega prima della partita non e' quella dopo la partita precedente."""
    out, ieri = [], None
    for i, (prima, dopo) in enumerate(ranghi, 1):
        if ieri and prima and prima != ieri:
            out.append((i - 1, f"↺ {prima}", prima))
        if prima and dopo and dopo != prima:
            su = LEGHE.index(dopo) > LEGHE.index(prima) if dopo in LEGHE and prima in LEGHE else True
            out.append((i, f"{'↑' if su else '↓'} {dopo}", dopo))
        ieri = dopo or ieri
    return out
SCHEDE = (("meta", "Meta"), ("mazzi", "Your decks"), ("corso", "Drafter"), ("performance", "Performance"), ("risorse", "Resources"), ("collezione", "Collection"), ("help", "Help"))   # Your decks dopo Meta (Autore, 7 nov 2026); Help l'ultima (10 nov 2026)
TIPO = {"quick": "QuickDraft", "premier": "PremierDraft"}
# i formati limited di Arena: il nome nel menu e i prefissi del nome dell'evento (QuickDraft_FRA_20261008 -> QuickDraft)
FORMATI_LIMITED = (("Quick Draft", ("QuickDraft",)), ("Premier Draft", ("PremierDraft",)), ("Traditional Draft", ("TradDraft",)),
                   ("Sealed", ("Sealed",)), ("Traditional Sealed", ("TradSealed",)), ("Arena Cube", ("ArenaCube", "CubeDraft", "Cube")),
                   ("Pick Two Draft", ("PickTwoDraft",)))
TUTTI_FORMATI = "All formats"
# i formati costruiti con dati veri: le tue partite (Ladder e Play di Untapped sono Standard, super_format 2) e il meta al rango
# platinum di Untapped (Note/meta_untapped.json). Un formato nuovo entra qui quando ha i suoi dati, mai prima.
FORMATI_COSTRUITI = ("Standard", "Alchemy", "Explorer", "Historic", "Timeless", "Brawl", "Standard Brawl")
SUPER_FORMATO = {"Standard": 2}   # il codice super_format di Untapped per formato: solo Standard e' verificato (tutte le tue partite)
BASI = {"Plains", "Island", "Swamp", "Mountain", "Forest", "Wastes"}
COL_RARITA = {"C": "#9a9aa0", "U": "#b8bcc4", "R": "#e8c15a", "M": "#ff7a3d"}
NOME_RARITA = {"C": "comune", "U": "non comune", "R": "rara", "M": "mitica"}


_RARITA_NOME = None


def rarita_nome(nome):
    """La rarita' di una carta per nome (C, U, R, M) come la conta il jolly: la piu' bassa fra le sue stampe su Arena, in
    Collezione/arena_cards_cache.json. Da maggio 2022 una carta stampata con piu' rarita' si crea col jolly della rarita'
    piu' bassa (mtgrocks.com/mtg-arena-reprints-update; segnalazione sul forum feedback.wizards.com, «the lowest rarity
    printing on Arena determines the rarity of the wildcard»): fonte di terzi, non una pagina di Wizards. Fino al 18 ott
    2026 qui c'era la stampa piu' recente: Llanowar Elves risultava mitica (FDN), i jolly che mancano erano gonfiati."""
    global _RARITA_NOME
    if _RARITA_NOME is None:
        _RARITA_NOME = {}
        ordine = "CURM"
        try:
            d = json.load(open(os.path.join(ROOT, "Collezione", "arena_cards_cache.json"), encoding="utf-8"))
            for v in d.values():
                if v.get("n") and v.get("r") in COL_RARITA:
                    for n in [v["n"]] + v["n"].split(" // "):
                        if n not in _RARITA_NOME or ordine.index(v["r"]) < ordine.index(_RARITA_NOME[n]):
                            _RARITA_NOME[n] = v["r"]
        except (OSError, ValueError):
            pass
    return _RARITA_NOME.get(nome)


_COLL = {"chiave": None, "d": ({}, None)}
_JOLLY = {}
import account as _ACCOUNT  # noqa: E402
_ACCOUNT.lega(globals(), "UNTAPPED_CACHE", "untapped_partite_cache.json")      # le partite di Untapped sono dell'account: nell'app pubblica si copiano nella sua cartella
# e si uniscono con All accounts (10 nov 2026, Magic 12); qui sotto il percorso si chiede ad account.percorso a ogni lettura


def collezione():
    """{nome: copie che hai} e la data della copia della collezione. Riletta solo quando il file cambia (7 nov 2026: ogni scheda e ogni carta del builder la rileggevano)."""
    import account as _ACC
    p = _ACC.percorso("collezione_nomi.json", autore=os.path.join(ROOT, "Collezione", "collezione_nomi.json"))      # per account nell'app pubblica
    try:
        import collezione_viva as CV      # lo scarico di Untapped piu' le carte che i log scrivono dopo (8 nov 2026: «fallo leggere dal mio log»)
        st_ = CV.stato()
        chiave = ((os.path.getmtime(p), os.path.getsize(p)) if os.path.exists(p) else (0, 0, p)) + ((st_["soglia"], len(st_["piu"])) if st_ else ())      # un account
        # nuovo dell'app pubblica non ha lo scarico: la collezione e' quella dei log
        if chiave != _COLL["chiave"]:
            _COLL.update(chiave=chiave, d=(CV.copie_nomi(), datetime.datetime.fromtimestamp(chiave[0])))
        return _COLL["d"]
    except (OSError, ValueError):
        return {}, None


def collezione_nota():
    """Si sa quali carte hai? Nell'app di Autore si', sempre. Nell'app pubblica (account.py) solo se c'e' uno scarico di Untapped con delle carte: il log di
    Arena non scrive la collezione intera, e una collezione vuota farebbe dire a ogni mazzo che mancano tutte le carte (10 nov 2026)."""
    import account
    if not account.PUBBLICA:
        return True
    try:
        return bool(json.load(open(account.percorso("collezione.json"), encoding="utf-8")).get("cards"))
    except (OSError, ValueError):
        return False


def jolly():
    """I jolly che hai (C, U, R, M) dall'ultimo inventario scritto nei log di Arena: il Player.log vivo, se no il log
    archiviato piu' recente che lo contiene. -> (dict o None, data del log). Nell'app pubblica dall'ultima foto del conto dell'account mostrato (risorse.raccogli:
    il Player.log puo' essere di un altro account; con All accounts la somma), riletta quando cambiano i log o l'account (10 nov 2026, Magic 12)."""
    import account as _ACC
    if _ACC.PUBBLICA:
        firma = ("pub", _ACC.scelta(), _ACC.attivo()) + tuple(os.path.getmtime(f) if os.path.exists(f) else 0 for f in _ACC.VIVI)
        if _JOLLY.get("pub", (None,))[0] != firma:
            try:
                import risorse as RS
                foto, _p = RS.raccogli(aggiorna_cache=False)
            except Exception:       # noqa: BLE001 - senza foto i jolly non si sanno
                foto = []
            _JOLLY["pub"] = (firma, (dict(zip("CURM", foto[-1]["wc"])), datetime.datetime.fromisoformat(foto[-1]["t"])) if foto else (None, None))
        return _JOLLY["pub"][1]
    vivo = os.path.join(os.path.expandvars(r"%USERPROFILE%\AppData\LocalLow\Wizards Of The Coast\MTGA"), "Player.log")
    arch = sorted((os.path.join(LOGDIR, n) for n in os.listdir(LOGDIR) if "Player" in n and n.endswith(".log")),
                  key=os.path.getmtime, reverse=True) if os.path.isdir(LOGDIR) else []
    for f in [vivo] + arch[:6]:
        try:
            chiave = (os.path.getmtime(f), os.path.getsize(f))
        except OSError:
            continue
        if _JOLLY.get(f, (None,))[0] != chiave:     # 20 MB di log letti una volta per versione del file, non a ogni scheda (7 nov 2026)
            try:
                with open(f, "rb") as fh:
                    fh.seek(0, 2); n = fh.tell(); fh.seek(max(0, n - 20_000_000))
                    t = fh.read().decode("utf-8", "ignore")
            except OSError:
                continue
            out = {}
            for k, ch in (("C", "WildCardCommons"), ("U", "WildCardUnCommons"), ("R", "WildCardRares"), ("M", "WildCardMythics")):
                m = re.findall(r'"%s":\s*(\d+)' % ch, t)
                if m:
                    out[k] = int(m[-1])
            _JOLLY[f] = (chiave, out)
        out = _JOLLY[f][1]
        if len(out) == 4:
            return dict(out), datetime.datetime.fromtimestamp(chiave[0])
    return None, None


def craft(carte, coll, jl):
    """carte: {nome: copie}. -> (mancanti per rarita', craftabile o None se i jolly non si sanno). Le basi non contano."""
    manca = {"C": 0, "U": 0, "R": 0, "M": 0}
    for nome, q in carte.items():
        if nome in BASI:
            continue
        r = rarita_nome(nome)
        if r:
            manca[r] += max(0, min(q, 4) - coll.get(nome, 0))
    if jl is None:
        return manca, None
    return manca, all(manca[r] <= jl.get(r, 0) for r in manca)


NOMI_RARITA = dict(C="Common", U="Uncommon", R="Rare", M="Mythic")
MOSTRA_MAZZI = ("Your decks", "Meta", "Field")
FARMING = "Farming"   # in «Mostra» solo quando farming() trova almeno un premio vero
META_STD = os.path.join(ROOT, "Note", "meta_untapped.json")


# ---------------------------------------------------------------- i dati

def numeri(ds):
    """(vinte, partite, draft, trofei) di una lista di draft di draft_da_untapped."""
    w = sum(d["w"] for d in ds); l = sum(d["l"] for d in ds)
    return w, w + l, len(ds), sum(1 for d in ds if d["w"] >= 7)


def coppie(set_, formato):
    """[(coppia, % vinte, trofei o None)] dal meta del set: il Quick dalla sua colonna, il Premier dalla sua (Untapped)."""
    if formato == "quick":
        return formato_quick(set_)
    p = PR.file("nota_quick", set_, "quick")
    if not os.path.exists(p):
        return [], ""
    t = open(p, encoding="utf-8").read()
    fonte = (re.search(r"scaricato il ([^;]+);", t) or [None, ""])[1]
    righe = re.findall(r"^\| ([WUBRG]{2}) \| \*\*[\d.]+%\*\* \| [\d,]+ \| (\d+) \| ([\d.]+)%", t, re.M)
    return sorted(((c, float(w), None) for c, _, w in righe), key=lambda x: -x[1]), fonte


NOMI_EVENTI = dict(Ladder="Ranked", Play="Play", Constructed="Constructed Event", DualColorPrecons="Dual Color Precons", AIBotMatch="Bot Match", WelcomeDeckDuels="Welcome Deck Duels", Timeless="Timeless Play")
EVENTI_BASE, EVENTI_TUTTI = "Ranked and Play", "All events"
_PREZZI_AGGIORNATI = []    # il bulk dei prezzi si rinnova una volta per processo, in sottofondo


def partite_costruite(tutti=False):
    """Le tue partite costruite, una per una: evento (Ladder o Play), nome del mazzo, colori, quando, vinta, rango dopo la partita. tutti: anche gli altri eventi
    costruiti (evento constructed, precostruiti, bot), per la tendina Event.

    Da dove vengono (10 nov 2026, Autore: «Si, passa al log», poi «teniamo per adesso da untapped tutto cio' che riguarda il limited»): dal nostro Player.log
    (partite_log.py) per ogni partita da quando ci sono i log (la prima, il 22 set 2026), con il mazzo giocato, la mano tenuta e i mulligan, chi comincia, le carte
    dell'avversario e i suoi colori, i turni; il rango in classificata e' quello che Arena scrive dopo la partita, quando lo scrive (partite_log.py: non sempre,
    allora resta vuoto), nelle altre code il rango che avevi. Da
    Untapped (la copia sul disco, Log_Arena/untapped_partite_cache.json) solo le partite prima del primo log: lo storico dal 12 ago al 21 set 2026, quando i log non
    c'erano. Il limited resta su Untapped (dati_drafter.draft_da_untapped). Fino al 10 nov era il contrario: Untapped per tutto, il log solo per le partite che Untapped
    non aveva (dal 9 nov)."""
    import account as _ACC
    pc = _ACC.percorso("untapped_partite_cache.json", autore=os.path.join(LOGDIR, "untapped_partite_cache.json"))       # nell'app pubblica quella dell'account (10 nov 2026)
    try:
        with open(pc, encoding="utf-8") as f:
            cache = json.load(f)
    except (OSError, ValueError):
        cache = None
    arena = mazzi_arena_o_niente()
    pl, nomi_log = partite_dal_log()
    rimappa = mazzo_di_arena(arena, nomi_log)
    limited = lambda e: bool(re.search(r"Draft|Sealed|Cube", e or ""))
    dal_log = [p for p in pl if p["vinta"] is not None and not limited(p["evento"])]
    inizio_log = min((p["inizio"] for p in pl), default=None)        # da qui in poi parla il log
    out, visti = [], set()
    for set_k, v in (cache or {}).items():
        for g in v.get("partite") or []:
            ev = (g.get("event_name") or "").split("_")[0]
            k = g.get("short_id") or (g.get("match_start"), ev)
            if (ev not in ("Ladder", "Play") and not (tutti and g.get("super_format") == 2)) or k in visti or not g.get("match_start"):
                continue
            if inizio_log is not None and g["match_start"] >= inizio_log:      # c'e' il log: Untapped non serve
                continue
            visti.add(k)
            g = dict(g, friendly_deck_id=rimappa(g.get("friendly_deck_id")))
            rango = None
            if g.get("friendly_ranking_class_after"):
                rango = f"{g['friendly_ranking_class_after']} {g.get('friendly_ranking_tier_after') or ''}".strip()
            gg = g.get("games") or [{}]
            col_a = (gg[0].get("opponent_revealed_colors") or [0])[0]
            out.append(dict(ev=ev, evento=NOMI_EVENTI.get(ev, ev), raw=g.get("event_name") or "", avv=colori_da_bit(col_a), nome=(g.get("friendly_deck_name") or "").strip(), colori=colori_da_bit(g.get("friendly_deck_colors")),
                            quando=datetime.datetime.fromtimestamp(g["match_start"] / 1000), rango=rango,
                            lega_prima=g.get("friendly_ranking_class_before"), lega=g.get("friendly_ranking_class_after"), set=set_k,
                            ds=g.get("friendly_deckstring") or "", formato=g.get("super_format"), id=g.get("friendly_deck_id"), giochi=g.get("games") or [], seat=g.get("friendly_system_seat_id"),
                            vinta=g.get("winning_team_id") == g.get("friendly_team_id"), fonte="untapped"))
    import deckstring_scrivi as DS
    per_mazzo = {m["id"]: m for m in arena or []}
    for p in dal_log:
        ev = p["evento"].split("_")[0]
        if ev not in ("Ladder", "Play") and not tutti:
            continue
        q = datetime.datetime.fromtimestamp(p["inizio"] / 1000)
        idm = rimappa(p["mazzo"])
        m = per_mazzo.get(idm) or {}
        nome = m.get("nome") or mazzo_leggibile(nomi_log.get(p["mazzo"]) or "")
        carte = p.get("carte") or []
        ds = DS.codifica(DS.da_grp(carte), DS.da_grp(p.get("side") or []), DS.da_grp(p.get("cmd") or [])) if carte else ""
        avv = DS.colori(p.get("sue") or [])
        # il rango: in classificata quello che Arena scrive dopo la partita, se l'ha scritto; nelle altre code il rango che avevi (partite_log)
        prima = p.get("rango_prima")
        dopo = p.get("rango_dopo") if "Ladder" in p["evento"] else prima
        classe = lambda r: r[0] if r and r[0] not in (None, "None") else None
        rango = (dopo[0] if dopo[0] == "Mythic" else f"{dopo[0]} {dopo[1]}") if classe(dopo) else None
        gioco = dict(game_number=1, active_player_id=p["inizia"], winning_team_id=p["team"] if p["vinta"] else 3 - (p["team"] or 1),
                     player_opening_hands=[DS.codifica(DS.da_grp(h)) for h in p.get("mani") or []],
                     opponent_revealed_colors=[DS.bit(avv)], opponent_revealed_deckstrings=[DS.codifica({t: 1 for t in DS.da_grp(p.get("sue") or [])})] if p.get("sue") else [])
        out.append(dict(ev=ev, evento=NOMI_EVENTI.get(ev, ev), raw=p["evento"], avv=avv, nome=nome,
                        colori=m.get("colori") or colori_chiave(nomi_log.get(p["mazzo"]) or "") or DS.colori(carte),
                        quando=q, rango=rango, lega_prima=classe(prima), lega=classe(dopo), set=set_del_giorno(q.date()), ds=ds, formato=2, id=idm,
                        giochi=[gioco], seat=p["seat"], vinta=p["vinta"], turni=p["turni"], fonte="log", avversario=p["avversario"]))
    if cache is None and not out:
        return None
    return sorted(out, key=lambda x: x["quando"])


def mazzi_arena_o_niente():
    try:
        import mazzi_arena
        return mazzi_arena.mazzi() or []
    except (OSError, ValueError, KeyError):
        return []


def partite_dal_log():
    """Le partite del Player.log e dei log archiviati (partite_log.py), o niente se non si leggono."""
    try:
        import partite_log
        return partite_log.partite()
    except (OSError, ValueError) as e:
        print("partite dal log:", e)
        return [], {}


def mazzo_di_arena(arena, nomi_log):
    """L'id di un mazzo -> l'id del mazzo di Arena che e' davvero. I Dual Color Precons fanno giocare una copia del mazzo, col suo id e il nome
    «?=?Loc/Decks/Precon/Precon_EPPFDN_BW»: va sul mazzo di Arena con la stessa chiave (Vampiric Hunger), se no le sue partite non si vedono mai (9 nov 2026)."""
    ids = {m["id"] for m in arena}
    per_chiave = {}
    for m in arena:
        if m.get("chiave"):
            per_chiave.setdefault(m["chiave"], m["id"])

    def f(i):
        if not i or i in ids:
            return i
        k = re.search(r"Decks/Precon/(.+?)(?:_desc)?$", nomi_log.get(i) or "")
        return per_chiave.get(k.group(1), i) if k else i
    return f


def mazzo_leggibile(nome):
    """«?=?Loc/Decks/Precon/Precon_EPPFDN_BW» -> il nome di Arena se c'e', se no «Precon EPPFDN BW»."""
    if not nome.startswith("?=?Loc"):
        return nome
    try:
        import mazzi_arena
        return mazzi_arena.nome_precon(nome)
    except (OSError, ValueError, KeyError):
        return nome.rsplit("/", 1)[-1].replace("_", " ")


def colori_chiave(nome):
    """I colori dalla chiave di un mazzo di Arena («..._BW» -> «WB»), nell'ordine WUBRG."""
    m = re.search(r"_([WUBRG]{2,5})$", nome)
    return "".join(c for c in "WUBRG" if m and c in m.group(1))


_SET_USCITI = []


def set_del_giorno(giorno):
    """Il periodo di set di un giorno (come la copia di Untapped): l'ultimo set principale uscito entro quel giorno, con 7 giorni di margine (Set_Legali.md)."""
    if not _SET_USCITI:
        righe = re.findall(r"^\| [^|]+ \| ([A-Z0-9]+) \| (\d{4}-\d{2}-\d{2}) \| (\d+) \|", open(os.path.join(ROOT, "Regole", "Set_Legali.md"), encoding="utf-8").read(), re.M)
        _SET_USCITI.extend((d, c) for c, d, k in sorted(righe, key=lambda r: r[1]) if int(k) >= 100)
    entro = (giorno + datetime.timedelta(days=7)).isoformat()
    ok = [c for d, c in _SET_USCITI if d <= entro]
    return ok[-1] if ok else None


def costruite():
    """Il riassunto di Standard: Ladder (classificata, col rango dopo l'ultima) e Play (libera), e le partite una per una."""
    pp = partite_costruite()
    if pp is None:
        return None
    out = {"Ladder": [0, 0], "Play": [0, 0]}
    for g in pp:
        out[g["ev"]][1] += 1; out[g["ev"]][0] += g["vinta"]
    rango = next((g["rango"] for g in reversed(pp) if g["ev"] == "Ladder" and g["rango"]), None)
    try:
        import mazzi_arena
        arena = mazzi_arena.mazzi()     # Your decks: i mazzi veri, dal Player.log; quelli che Arena ti ha dato vanno in Arena decks
    except (OSError, ValueError, KeyError) as e:
        print("mazzi di Arena:", e)
        arena = None
    return dict(ladder=out["Ladder"], play=out["Play"], rango=rango, partite=pp, tutte=partite_costruite(tutti=True), arena=arena)


def mazzi_draft(ds):
    """I tuoi draft raggruppati per coppia di colori, i piu' giocati prima: [(colori, draft, vinte, perse, trofei)]."""
    g = collections.OrderedDict()
    for d in ds:
        x = g.setdefault(d["colori"] or "?", [0, 0, 0, 0])
        x[0] += 1; x[1] += d["w"]; x[2] += d["l"]; x[3] += d["w"] >= 7
    return sorted(((k, *v) for k, v in g.items()), key=lambda r: (-r[1], -(r[2] / max(r[2] + r[3], 1))))


def mazzi_costruiti(pp, n=8):
    """Le tue partite di Standard per mazzo (il nome che gli hai dato su Arena), i piu' giocati prima:
    [(nome, colori, partite, vinte, ultima volta)]. I mazzi senza nome si raggruppano per colori."""
    g = {}
    for x in pp:
        k = x["nome"] or ("Unnamed" + (f" {x['colori']}" if x["colori"] else ""))
        r = g.setdefault(k, dict(colori=collections.Counter(), n=0, w=0, ultima=x["quando"]))
        r["colori"][x["colori"]] += 1; r["n"] += 1; r["w"] += x["vinta"]; r["ultima"] = max(r["ultima"], x["quando"])
    righe = [(k, r["colori"].most_common(1)[0][0], r["n"], r["w"], r["ultima"]) for k, r in g.items()]
    # gli n piu' giocati, in ordine di win rate dal piu' alto (Autore, 17 ott 2026: «in standard, i tuoi mazzi: metti i mazzi
    # in ordine di win rate»); prima i piu' giocati, cosi' un mazzo provato due volte non sale in cima per caso
    return sorted(sorted(righe, key=lambda r: -r[2])[:n], key=lambda r: (-r[3] / r[2], -r[2]))


def saldo_draft(ds):
    """Il win rate dall'inizio partita per partita, su tutti i draft (dal piu' vecchio): punti [(etichetta, % vinte)],
    l'inizio di ogni draft [(indice del primo punto, data)], i passaggi di lega [(indice, testo, lega)] e i trofei
    [indice dell'ultima partita di un draft da 7 vinte]."""
    punti, inizi, ranghi, trofei, vinte, giocate = [], [], [], [], 0, 0
    for d in ds:
        seq = d["seq"] if len(d["seq"]) == d["w"] + d["l"] else ["v"] * d["w"] + ["p"] * d["l"]
        if seq:
            inizi.append((len(punti), f"{d['quando']:%d/%m}"))
        lg = d.get("leghe") or []
        for k, esito in enumerate(seq, 1):
            vinte += esito == "v"; giocate += 1
            punti.append((f"draft of {d['quando']:%d/%m} {d['colori'] or ''}, game {k} {'won' if esito == 'v' else 'lost'}", 100.0 * vinte / giocate))
            ranghi.append(lg[k - 1] if len(lg) == len(seq) else (None, None))
        if d["w"] >= 7:
            trofei.append(len(punti))
    return punti, inizi, passaggi(ranghi), trofei


def saldo_partite(pp, ev="Ladder"):
    """Lo stesso per Standard, sulla classificata (la lega esiste solo li'): il win rate dall'inizio, un segno a ogni giorno
    nuovo, i passaggi di lega."""
    punti, inizi, ranghi, vinte, ieri = [], [], [], 0, None
    for x in pp:
        if ev and x["ev"] != ev:
            continue
        g = x["quando"].date()
        if g != ieri:
            inizi.append((len(punti), f"{g:%d/%m}")); ieri = g
        vinte += x["vinta"]
        punti.append((f"{x['quando']:%d/%m} {x['nome'] or 'unnamed'}, {'won' if x['vinta'] else 'lost'}"
                      + (f" · {x['rango']}" if x.get("rango") else ""), 100.0 * vinte / (len(punti) + 1)))
        ranghi.append((x.get("lega_prima"), x.get("lega")))
    return punti, inizi, passaggi(ranghi), []


def _json(p):
    """Un json del meta, o None se manca o non si legge (il giro lo riscrive ogni 6 ore: mai un errore nella finestra)."""
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def sotto_meta(d, quando):
    """Il sottotitolo del meta di Untapped: rango, periodo, partite, giorno dello scarico, e se il periodo nuovo ha ancora
    troppe poche partite (10 nov 2026: Star Trek aperto da poche ore, si legge Reality Fracture, e lo si dice)."""
    per = (d.get("periodo") or "").replace("Set Release - ", "")
    pezzi = [f"{d.get('rango') or 'platinum'} rank"] + ([per] if per else [])
    if d.get("partite_rango"):
        pezzi.append(f"{d['partite_rango']:,} games")
    pezzi.append(f"{quando:%d/%m}")
    nuovo = (d.get("periodo_nuovo") or "").replace("Set Release - ", "")
    if nuovo:
        pezzi.append(f"{nuovo}: too few games yet")
    return " · ".join(pezzi)


def meta_standard(n=14):
    d = _json(META_STD)
    if not isinstance(d, list):
        return [], ""
    quando = datetime.datetime.fromtimestamp(os.path.getmtime(META_STD))
    info = _json(os.path.join(ROOT, "Note", "meta_untapped_periodo.json"))
    return sorted(d, key=lambda x: -x.get("quota", 0))[:n], sotto_meta(info if isinstance(info, dict) else {}, quando)


def url_untapped(fmt, m):
    """La pagina originale dell'archetipo su Untapped (verificata il 18 ott 2026 su Standard 304 e Alchemy 514):
    mtga.untapped.gg/constructed/<formato>/archetypes/<gruppo>/<nome in minuscolo coi trattini>."""
    if not m.get("gruppo"):
        return None
    slug = re.sub(r"[^a-z0-9]+", "-", (m.get("nome") or "").lower()).strip("-")
    return f"https://mtga.untapped.gg/constructed/{fmt.lower().replace(' ', '-')}/archetypes/{m['gruppo']}/{slug}"


def meta_formato(fmt, n=14):
    """Il meta di un formato: (archetipi, sottotitolo). I piu' giocati (per quota), messi in ordine di win rate dal piu'
    alto; dove Untapped non da' il win rate, in ordine di forza (Autore, 18 ott 2026: «i mazzi meta vanno ordinati per
    win rate, devono essere sempre linkati ai dati originali»). Ogni archetipo porta «url», la sua pagina su Untapped."""
    m, sotto = _meta_formato(fmt, n)
    for x in m:
        x["url"] = url_untapped(fmt, x)
    if m and all(x.get("wr") is not None for x in m):
        m = sorted(m, key=lambda x: -x["wr"])
    elif m:
        m = sorted(m, key=lambda x: x.get("forza") or 999)
    return m, sotto


def _meta_formato(fmt, n=14):
    """Il meta di un formato: (archetipi per quota, sottotitolo). Standard dal suo file (col win rate), gli altri da
    Note/meta_untapped_<formato>.json (con la «forza» al posto del win rate). ([], "") se il formato non ha meta."""
    if fmt == "Standard":
        return meta_standard(n)
    p = os.path.join(ROOT, "Note", f"meta_untapped_{fmt.lower().replace(' ', '_')}.json")
    d = _json(p)
    if not isinstance(d, dict):
        return [], ""
    quando = datetime.datetime.fromtimestamp(os.path.getmtime(p))
    return sorted(d.get("archetipi") or [], key=lambda x: -x.get("quota", 0))[:n], sotto_meta(d, quando)


def farming(voci):
    """I tuoi mazzi negli eventi costruiti a premi, dai premi veri dei log (voci di premi_eventi.raccogli): per mazzo
    [dict(nome, colori, ds, eventi, gemme_vinte, gemme_spese, oro_vinto, oro_speso, buste, nomi_eventi)], prima chi ha reso
    di piu' in gemme (vinte meno spese). Un evento e' costruito se fra le partite costruite (partite_costruite) ce n'e' una."""
    if not voci:
        return []
    costruiti, ultima = set(), {}       # dal 10 nov 2026 dalle stesse partite delle altre schede (il log, Untapped solo prima dei log)
    for x in partite_costruite(tutti=True) or []:
        if x["raw"]:
            costruiti.add(x["raw"])
            k = (x["raw"], x["nome"])
            ms = x["quando"].timestamp() * 1000
            if x["ds"] and ms >= ultima.get(k, (0,))[0]:
                ultima[k] = (ms, x["ds"], x["colori"])
    righe = {}
    for v in voci:
        if v["fonte"] not in ("EventReward", "EventPayEntry") or v["evento"] not in costruiti or not v.get("mazzo"):
            continue
        r = righe.setdefault(v["mazzo"], dict(nome=v["mazzo"], colori="", ds="", quando=0, eventi=0, gemme_vinte=0, gemme_spese=0,
                                              oro_vinto=0, oro_speso=0, buste=0, nomi_eventi=set()))
        if v["fonte"] == "EventReward":
            r["eventi"] += 1; r["gemme_vinte"] += max(v["gemme"], 0); r["oro_vinto"] += max(v["oro"], 0)
            r["buste"] += sum(n for _, n in v["buste"]); r["nomi_eventi"].add(v["evento"])
        else:
            r["gemme_spese"] += -min(v["gemme"], 0); r["oro_speso"] += -min(v["oro"], 0)
        u = ultima.get((v["evento"], v["mazzo"]))
        if u and u[0] >= r["quando"]:
            r["quando"], r["ds"], r["colori"] = u
    out = [dict(r, nomi_eventi=sorted(r["nomi_eventi"])) for r in righe.values() if r["eventi"]]
    return sorted(out, key=lambda r: -(r["gemme_vinte"] - r["gemme_spese"]))


def calendario(set_, formato):
    """(date del formato, riga di stato, colore) dal calendario del set; None se il set non ha date."""
    cal = calendario_draft().get(set_, {})
    q = cal.get(formato, [])
    if not q:
        return None
    oggi = datetime.date.today(); data = data_draft
    aperta = [b for a, b in q if data(a) <= oggi <= data(b)]
    prossima = [a for a, b in q if data(a) > oggi]
    if aperta:
        gg = (data(aperta[0]) - oggi).days
        stato = ("closes today" if gg == 0 else f"closes in {gg} d", C["arancio"])
    elif prossima:
        stato = (f"reopens on {data(prossima[0]):%d/%m}", C["acciaio"])
    else:
        stato = ("chiuso", C["grigio"])
    return dict(date=q, testo=stato[0], col=stato[1], inizio=data(cal["inizio"]), fine=data(cal["fine"]),
                conqueror=cal.get("conqueror_fino"))


def data_corta(d):
    """«9 Nov» da una data o da «2026-11-09»: i mesi in inglese a mano, il %b segue la lingua del sistema."""
    d = datetime.date.fromisoformat(d[:10]) if isinstance(d, str) else d
    return f"{d.day} {('Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec')[d.month - 1]}"
