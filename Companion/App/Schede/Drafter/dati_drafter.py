"""I dati della scheda Drafter: il limited aperto dal Player.log, i draft da Untapped, campo, rimozioni, calendario dei set."""
import collections
import datetime
import json
import os
import piattaforma  # noqa: E402  (i percorsi di Arena su Windows e su Mac)
import re
import time

import chiudi_draft as CD
import progetto as PR

from ambiente import LOGDIR, ROOT


# ---------------------------------------------------------------- dati: Untapped, formato, calendario

RX_CORSO = re.compile(r'"CourseId":"([^"]+)","InternalEventName":"([^"]*(?:Draft|Sealed|Cube)[^"]*)","CurrentModule":"([^"]*)"')
RX_VINTE, RX_PERSE = re.compile(r'"CurrentWins":(\d+)'), re.compile(r'"CurrentLosses":(\d+)')
MODULI_APERTI = ("BotDraft", "Draft", "DeckSelect", "CreateMatch", "WaitingForMatch", "Match", "MatchResults")
LOG_ARENA = (piattaforma.player_log(), piattaforma.player_prev_log())


def limited_dal_log(files=LOG_ARENA):
    """Lo stato dei limited su Arena, dal Player.log (Autore, 6 nov 2026: «se chiudo l'app senza avere concluso un limited, l'app si riavvia con l'ultimo limited in corso ancora aperto. a limited finito, la
    scheda limited si resetta al launch event»). Arena scrive a ogni accesso i corsi con modulo e record: basta l'ultimo stato di ogni corso, anche se il companion era spento.
    -> dict(aperto, evento, modulo, w, l), None se i log non dicono niente o se Arena ha gia' detto che non c'e' un limited aperto: allora resta Untapped.
    Il record vale solo dal primo log. Appena Arena riparte il Player.log non ha ancora i corsi, e Player-prev.log puo' avere giorni: il 7 nov 2026 ha dato 2-0 al draft nuovo, che era 0-0, col record del
    draft del 5 nov. Dal log vecchio si legge solo che un limited c'era: w e l restano None."""
    for i, f in enumerate(files):
        try:
            with open(f, "rb") as fh:
                testo = fh.read().decode("utf-8", "ignore")
        except OSError:
            continue
        corsi = {}
        for m in RX_CORSO.finditer(testo):
            coda_ = testo[m.end():m.end() + 4000]
            prossimo = coda_.find('"InternalEventName"')
            coda_ = coda_[:prossimo] if prossimo > 0 else coda_
            v, p = RX_VINTE.search(coda_), RX_PERSE.search(coda_)
            corsi[m.group(1)] = dict(pos=m.start(), evento=m.group(2), modulo=m.group(3), w=int(v.group(1)) if v else 0, l=int(p.group(1)) if p else 0)     # Arena non scrive gli zeri
        if corsi:
            chiusi = CD.corsi_chiusi()      # chiusi a mano col pulsante Closed session: non si riaprono dal log
            aperti = [c for k, c in corsi.items() if c["modulo"] in MODULI_APERTI and k not in chiusi]
            c = max(aperti or corsi.values(), key=lambda x: x["pos"])
            return dict(aperto=bool(aperti), evento=c["evento"], modulo=c["modulo"], w=c["w"] if i == 0 else None, l=c["l"] if i == 0 else None)
        if '"InternalEventName"' in testo:      # Arena ha elencato i corsi e nessuno e' un limited: il log di prima non conta piu'
            return None
    return None


def draft_da_untapped(forza=False, forza_set=None):
    """Un draft = un friendly_deck_id. Torna la lista dei draft dal piu' vecchio al piu' nuovo."""
    # Ogni set si chiede a parte e se uno non risponde si alza un errore: partite_untapped.partite() salta in silenzio
    # il set che non risponde, e il 12 ott la finestra ha mostrato solo HOB come se fosse tutto (FRA non era arrivato).
    # Copia sul PC (Log_Arena/untapped_partite_cache.json, fuori da git): un set gia' chiuso non si richiede piu', il set in
    # corso al massimo ogni 10 minuti (o prima, con forza=True a fine partita). Il 12 ott le riaperture di prova, sei set a
    # ogni apertura, hanno fatto rispondere Untapped con 403 per un po'.
    from partite_untapped import ultimi_set, USER as U, PLAYER as PL, CTX
    import urllib.request, urllib.error
    import account as _ACC
    pc = _ACC.percorso("untapped_partite_cache.json", autore=os.path.join(LOGDIR, "untapped_partite_cache.json"))       # nell'app pubblica quella dell'account (10 nov 2026)
    try:
        with open(pc, encoding="utf-8") as f:
            cache = json.load(f)
    except (OSError, ValueError):  # manca o e' rovinata: si richiede tutto (dal 17 ott la usano due finestre, Companion e Set)
        cache = {}
    sets = ultimi_set(6)
    errore = None
    for st in sets:
        voce = cache.get(st)
        vivo = st == sets[-1] or st in (forza_set or ())
        if voce and (not vivo or (time.time() - voce["quando"] < 600 and not forza)):
            continue
        if _ACC.tutti():        # All accounts: la copia unita di tutti, senza chiedere a Untapped
            continue
        try:
            u = f"https://api.mtga.untapped.gg/api/v1/games/users/{U}/players/{PL}/?card_set={st}"
            j = json.load(urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "companion-magic-arena/1.0", "Accept": "application/json"}), timeout=60, context=CTX))
            cache[st] = {"quando": time.time(), "partite": j if isinstance(j, list) else []}
        except urllib.error.HTTPError as e:
            if e.code in (403, 404):     # per i set vecchi Untapped risponde sempre 403: nessuna partita da dare, non un guasto
                cache[st] = {"quando": time.time(), "partite": [], "codice": e.code}
            else:
                errore = e
        except Exception as e:
            errore = e
    # mai un file a meta' per l'altra finestra: si scrive accanto e si sostituisce. Su Windows la sostituzione fallisce
    # finche' l'altra finestra lo sta leggendo (17 ott 2026, era diventato «Untapped non risponde»): qualche tentativo,
    # poi si lascia la copia di prima. E' solo una copia: i dati appena arrivati restano in memoria.
    tmp = f"{pc}.{os.getpid()}.tmp"
    try:
        os.makedirs(os.path.dirname(pc), exist_ok=True)
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(cache, f)
        for _ in range(10):
            try:
                os.replace(tmp, pc); break
            except PermissionError:
                time.sleep(0.2)
        else:
            os.remove(tmp)
    except OSError:
        pass
    if errore and not all(st in cache for st in sets):
        raise errore
    tutte, visti = [], set()
    for st in sets:
        for g in (cache.get(st) or {}).get("partite", []):
            k = g.get("short_id") or (g.get("match_start"), g.get("friendly_deck_id"))
            if k not in visti:
                visti.add(k); tutte.append(g)
    out = collections.OrderedDict()
    for g in sorted(tutte, key=lambda g: g.get("match_start") or 0):
        ev = g.get("event_name") or ""
        if not any(x in ev for x in ("Draft", "Sealed", "Cube")):    # tutti i limited di Arena (18 ott 2026: anche sealed e cube)
            continue
        k = g.get("friendly_deck_id")
        parti = ev.split("_")
        d = out.setdefault(k, dict(id=k, evento=ev, tipo=parti[0], set=parti[1] if len(parti) > 1 else "?",
                                   colori=colori_da_bit(g.get("friendly_deck_colors")), w=0, l=0, seq=[],
                                   quando=datetime.datetime.fromtimestamp(g["match_start"] / 1000), mazzo={}, leghe=[], rango=None))
        if g.get("friendly_deckstring") and not d["mazzo"]:
            try:
                from deckstring import decodifica
                d["mazzo"] = decodifica(g["friendly_deckstring"])
            except Exception:
                pass
        d.setdefault("partite", []).append(dict(quando=datetime.datetime.fromtimestamp(g["match_start"] / 1000), vinta=g.get("winning_team_id") == g.get("friendly_team_id"),
                                                giochi=g.get("games") or [], seat=g.get("friendly_system_seat_id")))
        if g.get("winning_team_id") == g.get("friendly_team_id"):
            d["w"] += 1; d["seq"].append("v")
            d["leghe"].append((g.get("friendly_ranking_class_before"), g.get("friendly_ranking_class_after")))
        else:
            d["l"] += 1; d["seq"].append("p")
            d["leghe"].append((g.get("friendly_ranking_class_before"), g.get("friendly_ranking_class_after")))
        classe = g.get("friendly_ranking_class_after")
        if classe and classe != "None":          # il rango dopo l'ultima partita del draft
            d["rango"] = classe if classe == "Mythic" or not g.get("friendly_ranking_tier_after") else f"{classe} {g['friendly_ranking_tier_after']}"
    return list(out.values())


def campo(set_="FRA", tipo="QuickDraft"):
    """Gli avversari come gruppo, dalle partite di draft del set (copia di Untapped scritta da draft_da_untapped):
    per colori rivelati, per record al momento della partita, e le carte viste piu' spesso. Il nome dell'avversario
    resta nella copia ma qui non si usa: nei draft nessun avversario si e' ripetuto (126 su 126 al 12 ott 2026).
    Nota: in Untapped «friendly_course_wins_before/losses_before» e' il record DOPO la partita (verificato il 12 ott:
    la prima partita di un draft vinta porta 1-0), quindi il record prima si ricava togliendo il risultato."""
    import account as _ACC
    pc = _ACC.percorso("untapped_partite_cache.json", autore=os.path.join(LOGDIR, "untapped_partite_cache.json"))
    if not os.path.exists(pc):
        return None
    cache = json.load(open(pc, encoding="utf-8"))
    from deckstring import decodifica
    voti = voti_carte(set_)
    principali = _PRINCIPALI.get(set_, set())
    rim = rimozioni(set_)
    per_col = collections.defaultdict(lambda: [0, 0]); per_rec = collections.defaultdict(lambda: [0, 0])
    carte = collections.Counter(); forze = collections.defaultdict(list); n = 0
    for g in (cache.get(set_) or {}).get("partite", []):
        if not (g.get("event_name") or "").startswith(tipo):
            continue
        vinta = g.get("winning_team_id") == g.get("friendly_team_id")
        n += 1
        bits = 0; viste = collections.Counter()
        for gg in g.get("games") or []:
            for b_ in gg.get("opponent_revealed_colors") or []:
                bits |= b_ or 0
            for ds in gg.get("opponent_revealed_deckstrings") or []:
                try:
                    for nome, q in decodifica(ds).items():
                        if nome in principali:
                            viste[nome] = max(viste[nome], 1)
                except Exception:
                    pass
        col = colori_da_bit(bits) or "?"
        per_col[col][0] += 1; per_col[col][1] += vinta
        w_dopo = g.get("friendly_course_wins_before"); l_dopo = g.get("friendly_course_losses_before")
        if w_dopo is not None:
            w_prima = w_dopo - (1 if vinta else 0)
            fascia = "0" if w_prima == 0 else ("1-2" if w_prima <= 2 else "3+")
            per_rec[fascia][0] += 1; per_rec[fascia][1] += vinta
            f, k = forza(viste, voti)
            if f and k >= 5:
                forze[fascia].append(f)
        carte.update(viste.keys())
    return dict(partite=n, per_col=dict(per_col), per_rec=dict(per_rec), carte=carte.most_common(6),
                forze={k: sum(v) / len(v) for k, v in forze.items() if v}, rimozioni=rim)


def rimozioni(set_="FRA"):
    pq = PR.file("anagrafe", set_)
    out = set()
    if os.path.exists(pq):
        for c in json.load(open(pq, encoding="utf-8"))["carte"].values():
            r = c.get("rimozione") or {}
            if r.get("scheda") or r.get("classificatore"):
                out.add(c["nome"].split(" // ")[0])
    return out


def formato_quick(set_="FRA"):
    p = PR.file("nota_quick", set_, "quick")
    if not os.path.exists(p):
        return [], ""
    t = open(p, encoding="utf-8").read()
    fonte = (re.search(r"scaricato il ([^;]+);", t) or [None, ""])[1]
    trofei = dict((c, int(n)) for c, n in re.findall(r"\b([WUBRG]{2,3}) (\d+)", (re.search(r"Colori \(3\+ carte per colore\): (.+)", t) or [None, ""])[1]))
    righe = [(c, float(w)) for c, w in re.findall(r"^\| ([WUBRG]{2}) \| \*\*([\d.]+)%\*\*", t, re.M)]
    return [(c, w, trofei.get(c)) for c, w in righe], fonte


def calendario():
    p = os.path.join(ROOT, "Regole", "calendario_set.json")
    return json.load(open(p, encoding="utf-8"))["set"] if os.path.exists(p) else {}


def data(s):
    return datetime.date.fromisoformat(s)
BIT = {"W": 1, "U": 2, "B": 4, "R": 8, "G": 16}


_VOTI = {}
_PRINCIPALI = {}
_COLORI = {}
_TIPI = {}


def voti_carte(set_="FRA"):
    """{nome: GIH del Quick (o del Premier se il Quick manca)} dal quaderno del set (Regole/anagrafe_<SET>.json,
    17Lands), solo le carte che non sono terre. Le carte a due facce rispondono a ogni nome di faccia."""
    if set_ in _VOTI:
        return _VOTI[set_]
    out = {}
    pq = PR.file("anagrafe", set_)
    if os.path.exists(pq):
        for c in json.load(open(pq, encoding="utf-8"))["carte"].values():
            if c.get("terra"):
                continue
            g = (c.get("gih") or {})
            v = (g.get("quick") or {}).get("gih") or (g.get("premier") or {}).get("gih")
            if v is None:
                continue
            _PRINCIPALI.setdefault(set_, set()).add(c["nome"].split(" // ")[0])
            _COLORI.setdefault(set_, {})[c["nome"].split(" // ")[0]] = c.get("colori") or ""
            for f in c.get("testo") or []:
                if f.get("nome"): _TIPI[f["nome"]] = (f.get("tipo") or "") + (" flash" if "Flash" in (f.get("oracle") or "") else "")  # la faccia «preparata» non e' una carta a se
            nomi = {c["nome"]} | {f.get("nome") for f in c.get("testo") or [] if f.get("nome")}
            for n in nomi:
                out[n] = v
                for parte in n.split(" // "):
                    out.setdefault(parte, v)
    _VOTI[set_] = out
    return out


def forza(carte, voti):
    """Media del GIH sulle carte con un voto, pesata per le copie. -> (media, quante carte contate)."""
    tot = n = 0
    for nome, q in carte.items():
        v = voti.get(nome)
        if v is not None:
            tot += v * q; n += q
    return (tot / n, n) if n else (None, 0)


def colori_da_bit(n):
    return "".join(k for k in "WUBRG" if (n or 0) & BIT[k])
