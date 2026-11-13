"""I premi veri degli eventi, letti dai log di Arena (Autore, 17 ott 2026 ~23:20: nei tuoi numeri «dati su gemme ottenute,
dati su buste ottenute, dati su rare mitiche ottenute»).

Nel Player.log ogni cambio dell'inventario e' un oggetto {"Source": ..., "SourceId": ...}. Si leggono tre fonti:
- EventPayEntry: il costo d'ingresso (InventoryGems / InventoryGold negativi; SourceId = CourseId del corso);
- EventReward: il premio a fine evento (InventoryGems, Boosters con il set e il numero, GrantedCards; SourceId = CourseId);
- EventGrantCardPool: le carte del draft o del sealed che restano nella collezione (GrantedCards; SourceId = nome dell'evento).
Il CourseId si traduce nel nome dell'evento con le righe «"CourseId":"...","InternalEventName":"..."» degli stessi log.
La rarita' delle carte viene da Collezione/arena_cards_cache.json (r: C, U, R, M).

I log sono quelli archiviati in Log_Arena/ (dal 22 set 2026) piu' Player.log e Player-prev.log vivi: prima non c'e' niente.
Le copie si sovrappongono (Player-prev e' il Player della volta prima), quindi ogni voce si conta una volta: il premio e il
costo per CourseId, il pool per evento e insieme di carte. I log archiviati non cambiano: quello che se ne estrae si tiene in
Log_Arena/premi_eventi_cache.json (per nome e dimensione del file), cosi' solo i file nuovi si rileggono.
Ogni voce porta «conto», l'account di Arena dell'ultimo accesso prima di lei (10 nov 2026, Magic 12: un profilo per ogni account); nell'app pubblica raccogli()
da' le voci dell'account mostrato (account.attivo), con All accounts tutte. Nell'app di Autore tutte, come prima.

    py -I -X utf8 Companion/App/Schede/Resources/premi_eventi.py           il riepilogo per tipo di evento e per set
    py -I -X utf8 Companion/App/Schede/Resources/premi_eventi.py --prova   in piu' esce 1 se non trova niente
"""
import os, sys
_casa = os.path.dirname(os.path.abspath(__file__))      # si sale fino a percorsi.py, che mette nel sys.path tutte le cartelle del Companion
while not os.path.isfile(os.path.join(_casa, "percorsi.py")):
    _casa = os.path.dirname(_casa)
if _casa not in sys.path:
    sys.path.insert(0, _casa)
import percorsi  # noqa: E402
import piattaforma  # noqa: E402  (i percorsi di Arena su Windows e su Mac)
import re, json, collections
import account as _ACC

ROOT = percorsi.ROOT
LOGDIR = os.path.join(ROOT, "Log_Arena")
CACHE = os.path.join(LOGDIR, "premi_eventi_cache.json")
CARTE = os.path.join(ROOT, "Collezione", "arena_cards_cache.json")
VIVI = [os.path.join(piattaforma.cartella_arena(), n)
        for n in ("Player-prev.log", "Player.log")]
FONTI = ("EventPayEntry", "EventReward", "EventGrantCardPool")
RX_ACCESSO = re.compile(r'"authenticateResponse": \{ "clientId": "([A-Z0-9]+)"')
RX_CORSO = re.compile(r'"CourseId":"([0-9a-f-]{36})","InternalEventName":"([^"]+)"')
# il mazzo di ogni corso (18 ott 2026: «quanto ha farmato» un mazzo): il nome nella CourseDeckSummary dello stesso corso
RX_MAZZO = re.compile(r'"CourseId":"([0-9a-f-]{36})","InternalEventName":"[^"]+","CurrentModule":"[^"]*","ModulePayload":"(?:[^"\\]|\\.)*",'
                      r'"CourseDeckSummary":\{"DeckId":"[^"]*","Name":"([^"]*)"')


def leggi_file(path):
    """-> (voci, corsi, mazzi): le voci delle tre fonti trovate nel file, la mappa CourseId -> evento e CourseId -> mazzo. Ogni voce ha l'account dell'ultimo
    accesso prima di lei (prima del primo accesso del file, quello del primo)."""
    dec = json.JSONDecoder()
    voci, corsi, mazzi, conto = [], {}, {}, None
    with open(path, encoding="utf-8", errors="ignore") as f:
        for riga in f:
            if '"authenticateResponse"' in riga:
                a = RX_ACCESSO.search(riga)
                if a:
                    conto = a.group(1)
                    for v in voci:
                        v["conto"] = v["conto"] or conto
            if '"InternalEventName"' in riga and '"CourseId"' in riga:
                for cid, ev in RX_CORSO.findall(riga):
                    corsi[cid] = ev
                for cid, nome in RX_MAZZO.findall(riga):
                    mazzi[cid] = nome
            if '{"Source":"Event' not in riga:
                continue
            i = riga.find('{"Source":"Event')
            while i >= 0:
                try:
                    o, fine = dec.raw_decode(riga, i)
                except ValueError:
                    fine = i + 1; o = None
                if isinstance(o, dict) and o.get("Source") in FONTI:
                    voci.append(dict(fonte=o["Source"], id=o.get("SourceId") or "",
                                     gemme=o.get("InventoryGems") or 0, oro=o.get("InventoryGold") or 0,
                                     buste=[[b.get("SetCode"), b.get("Count") or 0] for b in o.get("Boosters") or []],
                                     carte=[c.get("GrpId") for c in o.get("GrantedCards") or [] if c.get("GrpId")], conto=conto))
                i = riga.find('{"Source":"Event', fine)
    return voci, corsi, mazzi


def raccogli(aggiorna_cache=True, conto=False):
    """Tutte le voci, contate una volta, con il nome dell'evento. -> lista di dict (fonte, evento, gemme, oro, buste, carte, conto). conto: l'account (False:
    quello mostrato; None o account.TUTTI: tutti); nell'app di Autore tutte."""
    if conto is False:
        conto = _ACC.attivo() if _ACC.PUBBLICA else None
    if conto == _ACC.TUTTI:
        conto = None
    try:
        with open(CACHE, encoding="utf-8") as f:
            cache = json.load(f)
    except (OSError, ValueError):
        cache = {}
    files = sorted(os.path.join(LOGDIR, n) for n in os.listdir(LOGDIR) if "Player" in n and n.endswith(".log")) if os.path.isdir(LOGDIR) else []
    tutte, corsi, mazzi, cambiata = [], {}, {}, False
    for p in files + [v for v in VIVI if os.path.exists(v)]:
        chiave = f"{os.path.basename(p)}|{os.path.getsize(p)}"
        vivo = p in VIVI
        if not vivo and chiave in cache and "mazzi" in cache[chiave] and (not _ACC.PUBBLICA or cache[chiave].get("conti")):
            voci, cc, mm = cache[chiave]["voci"], cache[chiave]["corsi"], cache[chiave]["mazzi"]
        else:
            voci, cc, mm = leggi_file(p)
            if not vivo:
                cache[chiave] = dict(voci=voci, corsi=cc, mazzi=mm, conti=True); cambiata = True
        tutte += voci; corsi.update(cc); mazzi.update(mm)
    if cambiata and aggiorna_cache:
        tmp = CACHE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(cache, f)
        os.replace(tmp, CACHE)
    out, visti = [], set()
    for v in tutte:
        ev = v["id"] if v["fonte"] == "EventGrantCardPool" else corsi.get(v["id"], "")
        k = (v["fonte"], v["id"], tuple(sorted(v["carte"])) if v["fonte"] == "EventGrantCardPool" else ())
        if k in visti or not ev or (conto is not None and v.get("conto") not in (conto, None)):
            continue
        visti.add(k)
        out.append(dict(v, evento=ev, mazzo=mazzi.get(v["id"], "") if v["fonte"] != "EventGrantCardPool" else ""))
    return out


def premi_mazzo(voci, nome):
    """I premi degli eventi giocati con il mazzo «nome» (il nome del mazzo su Arena): gemme, oro e buste vinte, eventi."""
    r = dict(gemme=0, oro=0, buste=0, eventi=0)
    for v in voci or []:
        if v["fonte"] == "EventReward" and v.get("mazzo") == nome:
            r["eventi"] += 1; r["gemme"] += max(v["gemme"], 0); r["oro"] += max(v["oro"], 0)
            r["buste"] += sum(n for _, n in v["buste"])
    return r


_RAR = None


def rarita(grp):
    global _RAR
    if _RAR is None:
        try:
            _RAR = {int(k): v.get("r") for k, v in json.load(open(CARTE, encoding="utf-8")).items()}
        except (OSError, ValueError):
            return None           # file illeggibile adesso: si riprova alla prossima carta, non si resta a zero fino al riavvio
    return _RAR.get(int(grp))


def dal():
    """La data del log archiviato piu' vecchio («22/09»): da li' ci sono i premi."""
    try:
        n = min(x for x in os.listdir(LOGDIR) if "Player" in x and x.endswith(".log") and x[:4].isdigit())
        return f"{n[8:10]}/{n[5:7]}"
    except (OSError, ValueError):
        return "?"


def tipo_e_set(evento):
    """«QuickDraft_FRA_20261008» -> ('QuickDraft', 'FRA')."""
    p = evento.split("_")
    return p[0], (p[1] if len(p) > 1 and p[1].isupper() and len(p[1]) <= 4 else "")


def riepilogo(voci=None, tipo=None, set_=None):
    """Somme per un tipo di evento (QuickDraft, PremierDraft, ...) e un set (None = tutti): gemme vinte e spese, oro speso,
    buste vinte, rare e mitiche nelle carte ricevute (pool e premi), eventi riscossi."""
    voci = raccogli() if voci is None else voci
    r = dict(gemme_vinte=0, gemme_spese=0, oro_speso=0, buste=0, rare=0, mitiche=0, premi=0, ingressi=0)
    for v in voci:
        t, s = tipo_e_set(v["evento"])
        if (tipo and t not in (tipo if isinstance(tipo, (tuple, list)) else (tipo,))) or (set_ and s != set_):
            continue
        if v["fonte"] == "EventReward":
            r["premi"] += 1; r["gemme_vinte"] += max(v["gemme"], 0); r["buste"] += sum(n for _, n in v["buste"])
        elif v["fonte"] == "EventPayEntry":
            r["ingressi"] += 1; r["gemme_spese"] += -min(v["gemme"], 0); r["oro_speso"] += -min(v["oro"], 0)
        if v["fonte"] in ("EventReward", "EventGrantCardPool"):
            for g in v["carte"]:
                x = rarita(g)
                r["rare"] += x == "R"; r["mitiche"] += x == "M"
    return r


def main():
    voci = raccogli()
    tipi = collections.Counter(tipo_e_set(v["evento"]) for v in voci)
    print(f"{len(voci)} voci da {len(set(v['evento'] for v in voci))} eventi")
    for (t, s), _ in sorted(tipi.items()):
        r = riepilogo(voci, t, s)
        if any(r.values()):
            print(f"  {t:<22} {s or '-':<4} premi {r['premi']:>3} ingressi {r['ingressi']:>3} | gemme +{r['gemme_vinte']} -{r['gemme_spese']}"
                  f" | oro -{r['oro_speso']} | buste {r['buste']} | rare {r['rare']} mitiche {r['mitiche']}")
    if "--prova" in sys.argv:
        q = riepilogo(voci, "QuickDraft")
        print("Quick Draft, tutti i set:", q)
        return 0 if voci and q["ingressi"] else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
