"""Le risorse del conto Arena, per la scheda «Risorse» della finestra grande (Autore, 4 nov 2026: «aggiungiamo una nuova
sezione: risorse: ci dice quanto gold viene farmato ogni mese in media / quanto gold e gemme vengono reinvestite e in cosa /
quanti pack e carte ottenute ogni mese / quante wc ottenute ogni mese / i dati possono essere filtrati per settimana / mese e
anno»).

La fonte e' una sola: i Player.log archiviati in Log_Arena/ (dal 22 set 2026) piu' i due vivi. Ogni risposta del server porta
l'«InventoryInfo», la foto del conto: oro, gemme, jolly, vault, posizione sulla pista dei jolly, buste non aperte. A volte
porta anche «Changes», i movimenti col nome (EventPayEntry, EventReward, CampaignGraph...). Fra due foto vicine si legge:
- oro e gemme: la differenza, meno i movimenti col nome, e' il resto. Un resto positivo e' farmato (vittorie, missioni e
  ricompense non hanno un movimento col nome); un resto negativo e' una spesa che Arena non scrive (il negozio non lascia righe).
- buste aperte: WcTrackPosition, che avanza di uno a ogni busta aperta e gira a 30 (quando vale 0 il campo manca).
- buste ottenute: aperte + differenza delle non aperte (nelle foto Count manca quando e' 0). Tornano col saldo: --prova.
- jolly: le differenze per rarita', positive ottenuti, negative usati.
- carte: i pool dei draft (EventGrantCardPool) e le GrantedCards dei premi e del pass sono esatti. **Le carte delle buste nel
  log non ci sono: sono una stima**, 8 a busta meno i jolly usciti in quel passo (grado C). Prova del 4 nov 2026: dal 6 ott al 3
  nov la collezione e' cresciuta di 824 copie; pool 525 + pass 20 + buste ~500 + jolly usati ~60 fanno ~1.100, e i ~250 doppioni
  oltre la quarta copia che vanno nel vault (vault +47,8%) chiudono il conto.

Il ROI (Autore, 4 nov 2026: «il roi e' il calcolo delle risorse ottenute per il periodo selezionato dalle tendine, se il roi e'
piu' alto dell'incasso allora la spesa e' stata positiva, si calcola dalla media di carte e wild card ottenute divise per i loro valore
in gemme») e' il valore in gemme delle carte e dei jolly ottenuti. **I valori sono una stima**, da «The true values of a rare» di Four
Daily Wins (feb 2025 o dopo, grado B; sites.google.com/mtgfutures.com/four-daily-wins/the-true-values-of-a-rare): una rara da busta 136
gemme, una mitica 204; un jolly raro 500 e uno mitico 1.000 (il suo prezzo nel negozio, 2,50 e 5 dollari, a 0,005 dollari la gemma). Comuni e
non comuni valgono 0, per la stessa fonte praticamente gratis. La rarita' di pool e premi e' nota; una busta conta come 7/8 di rara e
1/8 di mitica (grado C). L'incasso si confronta in gemme, con 1.000 oro = 200 gemme (il prezzo di una busta).

Il farmer calculator (Autore, 4 nov 2026: «a destra costruiamo un motore di simulazione spese mensili, una sorta di farmer calculator con
spese contro roi atteso») e' Risorse.simula: dato quanti Quick Draft, Premier Draft e buste al mese, con che valuta paghi, il win rate e l'oro
farmato, dice il costo in gemme, le gemme vinte, le buste vinte, il ROI atteso e cosa resta in cassa a fine mese. Le gemme e le buste per
vittorie sono le tabelle di Motore/economia_draft.py (grado B). Il ROI di un draft e' il valore medio dei tuoi pool (i tuoi draft veri) piu' le
buste vinte; una busta vale la sua rara o mitica piu' i jolly medi per busta aperta, misurati dalle tue foto. Il Premier usa i pool del Quick, finche'
non ne giochi uno (grado C). Ingresso Premier 10.000 oro o 1.500 gemme. E' una stima, non una previsione.

Il piano per obiettivi (Autore, 4 nov 2026: «ogni obiettivo deve calcolare dove investire il 100% del guadagno mensile per massimizzare il roi sull'obiettivo e roi
collaterali: se gioco quickdraft e' vero che ottengo carte ma ottengo anche gemme e buste e wildcard, tutto deve essere calcolato») e' Risorse.piano. Prova tutte le
combinazioni di draft ed eventi che l'oro medio paga, con i draft token per primi; il resto dell'oro va in buste e le gemme, quelle del trend piu' quelle vinte, in buste, tranne
con l'obiettivo gemme. Di ogni combinazione conta tutto (Risorse.rese): gemme, buste, carte, jolly. Le gemme si possono anche reinvestire in ingressi, che a win rate alto si ripagano. Vince l'obiettivo; fra i piani entro il 5% del migliore vince il valore totale, cioe' i
ritorni collaterali (il 5% e' una scelta nostra, grado C). Risorse.soglie («un massimizzatore di roi per elemento che sappia quale e' il migliore modo di reinvestire le risorse in base alle soglie di
winrate del giocatore») rifa' il piano per ogni win rate e dice dove cambia la rotta. Con «carte di un set» il draft conta solo se e' di quel set, e le buste premio degli eventi solo per il set nuovo. Una busta da' i
jolly e le carte medi delle tue buste aperte, vault compreso: tuoi, misurati, non una regola di Arena.

Gli eventi constructed (Bo1, 7 vittorie o 3 sconfitte): ingresso 2.500 oro o 375 gemme, premi da mtg.wiki, confermati dai tuoi due eventi dell'ott 2026 (4 vittorie = 300 gemme e 1 busta,
2 vittorie = 75 gemme e 1 busta); le altre vittorie restano grado B. Il premio si calcola col win rate constructed.

Le spese che Arena non scrive si leggono cosi':
- buste nel negozio: nello stesso passo un resto negativo e buste ottenute che nessun movimento spiega, a 1.000 oro l'una.
  Il prezzo e' dedotto, non letto: tornano 8 buste con -7.300 (700 farmati nello stesso passo) e 1 busta con -1.000; il 18 ott
  3 buste con -3.600 lasciano 600 oro in «Altro».
- Mastery Pass: resto negativo di gemme nel passo col movimento CampaignGraphPurchaseNode (3.400 gemme il 18 ott 2026).
- l'ingresso perso: un evento con il premio ma senza EventPayEntry (l'8 ott 2026 Arena si e' riavviato e il log s'e' perso) prende
  il resto negativo piu' vicino nelle 24 ore prima, al prezzo degli altri ingressi dello stesso evento.
- il resto e' «Altro».
Una foto dopo un buco nei log si confronta con l'ultima che c'e': il movimento finisce nel giorno della foto dopo.

La roadmap del Farmer (Autore, 6 nov 2026: «con il farmer una volta impostato il piano si clicca create e a destra nasce una road map che indica al player dove e quando durante la settimana
investire le risorse per rispettare il piano del farmer») e' Risorse.roadmap: prende le voci del mese di simula e le mette giorno per giorno, dal giorno del piano, per 30 giorni. Ogni voce e' sparsa in
parti uguali sui giorni in cui si puo' fare: un draft solo nelle finestre del calendario di Arena (Regole/calendario_set.json), buste ed eventi constructed sempre. La cassa parte dal saldo vero, ogni giorno
entra la media del trend (oro e gemme), e un evento rende le sue gemme medie il giorno dopo. Quel che i soldi non pagano ancora slitta: l'oro si tiene per la voce piu' vecchia. Sono medie: la cassa di un
giorno e' una stima. Il piano si salva in Log_Arena/piano_farmer.json; quel che hai gia' fatto si legge dai log (Risorse.fatti, le buste si riconoscono solo come buste comprate).

Quello che si estrae dai log archiviati si tiene in Log_Arena/risorse_cache.json (per nome e dimensione), come premi_eventi.
Un profilo per ogni account di Arena (10 nov 2026, Magic 12): ogni foto del conto e ogni pool porta l'account dell'ultimo accesso prima di lei («a»); nell'app
pubblica raccogli() da' quelle dell'account mostrato, e con All accounts una serie sola che somma i conti (somma_conti: a ogni passo cambia un account solo, quindi
oro farmato, spese e buste restano giusti). Nell'app di Autore tutto come prima.

    py -I -X utf8 Companion/App/Schede/Resources/risorse.py           il riepilogo mese per mese
    py -I -X utf8 Companion/App/Schede/Resources/risorse.py --prova   i casi di calcolo, con la prova negativa, e il bilancio contro il saldo vero
"""
import os, sys
_casa = os.path.dirname(os.path.abspath(__file__))      # si sale fino a percorsi.py, che mette nel sys.path tutte le cartelle del Companion
while not os.path.isfile(os.path.join(_casa, "percorsi.py")):
    _casa = os.path.dirname(_casa)
if _casa not in sys.path:
    sys.path.insert(0, _casa)
import percorsi  # noqa: E402
import re, copy, json, datetime, collections

import premi_eventi as PE
import economia_draft as ED
import account as _ACC

CACHE = os.path.join(PE.LOGDIR, "risorse_cache.json")
VERSIONE_CACHE = 3      # 2: i movimenti tengono i GrpId, per la rarita'; 3: i draft token
RX_ORA = re.compile(r"\[UnityCrossThreadLogger\](\d\d)/(\d\d)/(\d{4}) (\d\d:\d\d:\d\d)")
PISTA = 30               # la pista dei jolly gira a 30 buste
PREZZO_BUSTA = 1000      # dedotto dai saldi, vedi sopra
CARTE_A_BUSTA = 8        # grado C: nei log non c'e', vedi sopra
VALORE_CARTA = {"R": 136, "M": 204}       # gemme, vedi sopra
VALORE_JOLLY = {"R": 500, "M": 1000}      # gemme, vedi sopra
VALORE_BUSTA = 7 / 8 * VALORE_CARTA["R"] + 1 / 8 * VALORE_CARTA["M"]     # la rara o mitica di una busta
GEMME_PER_ORO = 200 / 1000     # il prezzo di una busta: dall'8 nov 2026 solo il punto di partenza, il cambio vero e' Risorse.gpo (sotto)
# Le gemme sono la moneta vera (Autore, 8 nov 2026: «l'importante alla base di tutto e' che l'algoritmo voglia che la vera moneta siano le gemme / tutto quanto deve sempre essere
# riproporzionato alle gemme quindi cambiare oro in gemme e' fondamentale»). L'oro non si cambia in negozio: diventa gemme solo pagando eventi e incassando i premi, quindi vale le gemme vere
# che ti tornano al tuo win rate sulla via migliore (Risorse.cambio_oro). Il win rate e' il tuo, spostato verso la media quando le partite sono poche (win_stimato; Autore: «usare il cambio
# individuale di ogni giocatore e' meglio o e' meglio usare il cambio vero per aiutare quanti piu' giocatori»: individuale, e chi ha poche partite parte dalla media).
PRIOR_WIN, PARTITE_PRIOR = 0.5, 50     # la media di tutti e quante partite pesa: con 50 partite il tuo numero conta meta'. Grado C
PREZZI_BUSTE = {"buste": {"oro": 1000, "gemme": 200}, "mitiche": {"oro": 1300, "gemme": 260}}     # la busta mitica: fonti 2025, grado B, da ricontrollare nel negozio
INGRESSI = {"quick": {"oro": 5000, "gemme": ED.INGRESSO}, "premier": {"oro": 10000, "gemme": ED.P_INGRESSO}, "costruiti": {"oro": 2500, "gemme": 375}}
MAX_EVENTI = 30       # ingressi in gemme ripetuti in un mese: un tetto nostro, un mese ha tante ore
PASSO_SOGLIE = 2      # il passo in punti di win rate per cercare le soglie
PIANO = os.path.join(PE.LOGDIR, "piano_farmer.json")
GIORNI_ROADMAP = 30
MAX_PROVE = 250       # quanti piani si provano giorno per giorno prima di arrendersi: la prova costa un paio di millisecondi
PASS_ANNO = 7         # i set con un Mastery all'anno, grado C: 2026 con ECL, TMT, SOS, MSH, HOB, FRA, TRK; FRA a TRK sono 42 giorni (29 set - 10 nov, calendario Wizards)
EXTRA_ORO, EXTRA_GEMME = 1000, 200       # l'income in piu' che rifa' la roadmap: il prezzo di una busta, in oro o in gemme (9 nov 2026)
EVENTI_AL_GIORNO = 2  # un draft e' un'ora e piu': un tetto nostro
NOMI_VOCE = dict(quick="Quick Draft", premier="Premier Draft", costruiti="Constructed event", buste="Packs", mitiche="Mythic packs", passo="Mastery Pass")
DOVE = dict(quick="Events", premier="Events", costruiti="Events", buste="Store", mitiche="Store", passo="Store")
COSTRUITO_GEMME = {0: 25, 1: 50, 2: 75, 3: 200, 4: 300, 5: 400, 6: 450, 7: 500}
COSTRUITO_BUSTE = {0: 0, 1: 0, 2: 1, 3: 1, 4: 1, 5: 2, 6: 2, 7: 3}
RARITA = ("C", "U", "R", "M")   # l'ordine di WildCardCommons, UnCommons, Rares, Mythics
NOMI_EVENTO = {"QuickDraft": "Quick Draft", "PremierDraft": "Premier Draft", "TradDraft": "Traditional Draft", "Sealed": "Sealed",
               "TradSealed": "Traditional Sealed", "Constructed": "Constructed event"}
BUSTE, PASS, ALTRO = "Packs", "Mastery Pass", "Other"
MESI = ("january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december")
GRANA = ("Settimana", "Mese", "Anno")


def _foto(o, ora):
    """La foto del conto da un InventoryInfo: chiavi corte, per la copia su disco."""
    bu = {}
    for b in o.get("Boosters") or []:
        if b.get("Count"):
            k = b.get("SetCode") or str(b.get("CollationId"))
            bu[k] = bu.get(k, 0) + b["Count"]
    mov = []
    for c in o.get("Changes") or []:
        mov.append(dict(f=c.get("Source") or "", id=c.get("SourceId") or "", oro=c.get("InventoryGold") or 0, gem=c.get("InventoryGems") or 0,
                        bu=sum(b.get("Count") or 0 for b in c.get("Boosters") or []), c=len(c.get("GrantedCards") or []),
                        g=[x.get("GrpId") for x in c.get("GrantedCards") or [] if x.get("GrpId")]))
    return dict(t=ora, s=o.get("SeqId") or 0, oro=o.get("Gold") or 0, gem=o.get("Gems") or 0, tr=o.get("WcTrackPosition", o.get("wcTrackPosition")) or 0,
                wc=[o.get(k) or 0 for k in ("WildCardCommons", "WildCardUnCommons", "WildCardRares", "WildCardMythics")],
                va=o.get("TotalVaultProgress") or 0, bu=bu, mov=mov, tok=(o.get("CustomTokens") or {}).get("DraftToken", 0))


def _stessa(a, b):
    return all(a[k] == b[k] for k in ("oro", "gem", "tr", "wc", "bu", "va", "tok"))


def leggi_file(path):
    """-> (foto, pool): le foto del conto che cambiano qualcosa o portano movimenti, e i pool dei draft [ora, evento, carte]."""
    dec = json.JSONDecoder()
    foto, pool, ora, conto = [], [], None, None
    with open(path, encoding="utf-8", errors="ignore") as f:
        for riga in f:
            if '"authenticateResponse"' in riga:      # l'account delle righe che seguono (10 nov 2026); quelle prima del primo accesso sono sue
                a = PE.RX_ACCESSO.search(riga)
                if a:
                    conto = a.group(1)
                    for x in foto:
                        x["a"] = x.get("a") or conto
                    for x in pool:
                        x[3] = x[3] or conto
            m = RX_ORA.search(riga)
            if m:
                ora = f"{m.group(3)}-{m.group(2)}-{m.group(1)} {m.group(4)}"
            if ora is None:
                continue
            i = riga.find('"InventoryInfo"')
            if i >= 0:
                try:
                    o, _ = dec.raw_decode(riga, riga.find("{", i))
                except ValueError:
                    o = None
                if isinstance(o, dict) and any(k in o for k in ("Gold", "Gems", "WildCardCommons", "SeqId")):
                    x = _foto(o, ora)
                    x["a"] = conto
                    if x["mov"] or not foto or not _stessa(x, foto[-1]) or foto[-1].get("a") != conto:
                        foto.append(x)
            i = riga.find('{"Source":"EventGrantCardPool"')
            while i >= 0:
                try:
                    o, fine = dec.raw_decode(riga, i)
                except ValueError:
                    o, fine = None, i + 1
                if isinstance(o, dict):
                    pool.append([ora, o.get("SourceId") or "", [c.get("GrpId") for c in o.get("GrantedCards") or [] if c.get("GrpId")], conto])
                i = riga.find('{"Source":"EventGrantCardPool"', fine)
    return foto, pool


def somma_conti(foto):
    """All accounts: le foto di piu' account in una serie sola. A ogni foto di un account, la somma dell'ultima foto di ogni account (di quella che verra', per un
    account non ancora visto): il passo cambia solo l'account della foto, quindi i movimenti e le differenze fra due foto restano i suoi."""
    per = collections.OrderedDict()
    for x in foto:
        per.setdefault(x.get("a"), x)
    stato = dict(per)
    out = []
    for x in foto:
        stato[x.get("a")] = x
        tot = dict(x, oro=0, gem=0, tr=0, wc=[0] * 4, va=0, bu={}, tok=0)
        for y in stato.values():
            for k in ("oro", "gem", "tr", "va", "tok"):
                tot[k] += y.get(k) or 0
            tot["wc"] = [a + b for a, b in zip(tot["wc"], y["wc"])]
            for s_, n in y["bu"].items():
                tot["bu"][s_] = tot["bu"].get(s_, 0) + n
        tot["tr"] = tot["tr"] % PISTA
        out.append(tot)
    return out


def raccogli(aggiorna_cache=True, conto=False):
    """-> (foto, pool) di tutti i log, in ordine di tempo, ognuna contata una volta (le copie dei log si sovrappongono). conto: l'account (False: quello mostrato;
    None o account.TUTTI: tutti, sommati); nell'app di Autore tutto, come prima."""
    if conto is False:
        conto = _ACC.attivo() if _ACC.PUBBLICA else None
    if conto == _ACC.TUTTI:
        conto = None
    try:
        with open(CACHE, encoding="utf-8") as f:
            cache = json.load(f)
        if cache.get("versione") != VERSIONE_CACHE:
            cache = {}
    except (OSError, ValueError):
        cache = {}
    file_ = cache.setdefault("file", {})
    cache["versione"] = VERSIONE_CACHE
    nomi = sorted(os.path.join(PE.LOGDIR, n) for n in os.listdir(PE.LOGDIR) if "Player" in n and n.endswith(".log")) if os.path.isdir(PE.LOGDIR) else []
    foto, pool, cambiata = {}, {}, False
    for p in nomi + [v for v in PE.VIVI if os.path.exists(v)]:
        chiave = f"{os.path.basename(p)}|{os.path.getsize(p)}"
        vivo = p in PE.VIVI
        if not vivo and chiave in file_ and (not _ACC.PUBBLICA or file_[chiave].get("conti")):
            ff, pp = file_[chiave]["foto"], file_[chiave]["pool"]
        else:
            ff, pp = leggi_file(p)
            if not vivo:
                file_[chiave] = dict(foto=ff, pool=pp, conti=True); cambiata = True
        for x in ff:
            if _ACC.PUBBLICA and conto is not None and x.get("a") not in (conto, None):
                continue
            k = (x["t"], x["s"], x["oro"], x["gem"], x["tr"], tuple(x["wc"])) + ((x.get("a"),) if _ACC.PUBBLICA else ())
            if k not in foto or len(x["mov"]) > len(foto[k]["mov"]):
                foto[k] = x
        for t, ev, carte, *chi in pp:
            if _ACC.PUBBLICA and conto is not None and (chi or [None])[0] not in (conto, None):
                continue
            k = (ev, tuple(sorted(carte)))
            if k not in pool or t < pool[k][0]:
                pool[k] = [t, ev, carte]
    if cambiata and aggiorna_cache:
        tmp = CACHE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(cache, f)
        os.replace(tmp, CACHE)
    foto = sorted(foto.values(), key=lambda x: (x["t"], x["s"]))
    if _ACC.PUBBLICA and conto is None and len({x.get("a") for x in foto}) > 1:
        foto = somma_conti(foto)
    return foto, sorted(pool.values(), key=lambda x: x[0])


def nome_evento(evento):
    return NOMI_EVENTO.get(PE.tipo_e_set(evento)[0].split("_")[0], evento.split("_")[0] if evento else ALTRO)


def _vuoto(giorno):
    return dict(giorno=giorno, oro_piu=0, gem_piu=0, spese=collections.Counter(), spese_gem=collections.Counter(), volte=collections.Counter(),
                bu_ott=0, bu_ap=0, bu_comp=0, jolly_piu=[0] * 4, jolly_meno=[0] * 4, c_draft=0, c_premi=0, c_buste=0, val_carte=0.0, r_draft=0, bu_premi=0, gem_premi=0)


def valore_carte(grp_id):
    """Il valore in gemme di carte di rarita' nota."""
    return sum(VALORE_CARTA.get(PE.rarita(g), 0) for g in grp_id)


def movimenti(foto, pool, eventi):
    """-> una voce per passo fra due foto, piu' una per ogni pool. eventi: CourseId -> nome dell'evento (da premi_eventi)."""
    pagati = {m["id"] for x in foto for m in x["mov"] if m["f"] == "EventPayEntry"}
    prezzi = collections.Counter((eventi.get(m["id"]), -m["oro"]) for x in foto for m in x["mov"] if m["f"] == "EventPayEntry" and m["oro"] < 0)
    # l'ingresso perso: l'indice della foto che porta il resto negativo, per ogni evento col premio ma senza ingresso nei log
    resti = []
    for i in range(1, len(foto)):
        a, b = foto[i - 1], foto[i]
        resti.append(b["oro"] - a["oro"] - sum(m["oro"] for m in b["mov"]))
    persi = {}
    for i, x in enumerate(foto):
        for m in x["mov"]:
            ev = eventi.get(m["id"])
            if m["f"] != "EventReward" or m["id"] in pagati or not ev:
                continue
            noti = [p for (e, p), _ in prezzi.most_common() if e == ev]
            if not noti:
                continue
            quando = datetime.datetime.fromisoformat(x["t"])
            for j in range(i, 0, -1):
                if quando - datetime.datetime.fromisoformat(foto[j]["t"]) > datetime.timedelta(hours=24):
                    break
                if foto[j].get("tok", 0) < foto[j - 1].get("tok", 0):      # il token e' calato: l'ingresso e' quello
                    break
                if j not in persi and -resti[j - 1] >= noti[0] * 0.5:
                    persi[j] = (ev, noti[0]); break
    out = []
    for i in range(1, len(foto)):
        a, b = foto[i - 1], foto[i]
        v = _vuoto(b["t"][:10])
        aperte = (b["tr"] - a["tr"]) % PISTA
        non_aperte = sum(b["bu"].values()) - sum(a["bu"].values())
        ottenute = max(0, non_aperte + aperte)
        dai_mov = 0
        for m in b["mov"]:
            dai_mov += m["bu"]
            v["c_premi"] += m["c"]
            v["val_carte"] += valore_carte(m.get("g") or [])
            if m["f"] == "EventReward":          # i premi degli eventi: nelle risorse attese li mette il calcolatore, non il trend
                v["bu_premi"] += m["bu"]; v["gem_premi"] += max(m["gem"], 0)
            nome = nome_evento(eventi.get(m["id"], "")) if m["f"] == "EventPayEntry" else ALTRO
            if m["oro"] > 0:
                v["oro_piu"] += m["oro"]
            elif m["oro"] < 0:
                v["spese"][nome] -= m["oro"]
            if m["gem"] > 0:
                v["gem_piu"] += m["gem"]
            elif m["gem"] < 0:
                v["spese_gem"][nome] -= m["gem"]
            if m["f"] == "EventPayEntry":
                v["volte"][nome] += 1
        # il resto dell'oro: farmato se positivo, una spesa da riconoscere se negativo
        resto = b["oro"] - a["oro"] - sum(m["oro"] for m in b["mov"])
        if resto >= 0:
            v["oro_piu"] += resto
        else:
            spesa = -resto
            comprate = max(0, ottenute - dai_mov)
            if i in persi:
                nome = nome_evento(persi[i][0])
                v["spese"][nome] += persi[i][1]; v["volte"][nome] += 1
                spesa -= persi[i][1]
            elif comprate and spesa >= comprate * PREZZO_BUSTA * 0.5:
                prezzo = PREZZI_BUSTE["mitiche"]["oro"] if spesa >= comprate * PREZZI_BUSTE["mitiche"]["oro"] else PREZZO_BUSTA    # la busta mitica costa di piu'
                v["spese"][BUSTE] += comprate * prezzo; v["bu_comp"] += comprate
                spesa -= comprate * prezzo
                comprate = 0
            if spesa > 0:
                v["spese"][ALTRO] += spesa
            else:
                v["oro_piu"] -= spesa              # l'oro farmato nello stesso passo della spesa
        resto = b["gem"] - a["gem"] - sum(m["gem"] for m in b["mov"])
        if resto >= 0:
            v["gem_piu"] += resto
        else:
            spesa = -resto
            if any(m["f"] == "CampaignGraphPurchaseNode" for m in b["mov"]):
                v["spese_gem"][PASS] += spesa
            else:
                sole = max(0, ottenute - dai_mov - v["bu_comp"])          # buste che nessun movimento e nessun oro spiega: comprate in gemme
                prezzo = PREZZI_BUSTE["buste"]["gemme"]
                if sole and spesa >= sole * prezzo * 0.5:
                    v["spese_gem"][BUSTE] += min(spesa, sole * prezzo); v["bu_comp"] += sole
                    spesa -= min(spesa, sole * prezzo)
                if spesa > 0:
                    v["spese_gem"][ALTRO] += spesa
        v["bu_ott"], v["bu_ap"] = ottenute, aperte
        wc_step = 0
        for r in range(4):
            d = b["wc"][r] - a["wc"][r]
            if d > 0:
                v["jolly_piu"][r] += d; wc_step += d
            else:
                v["jolly_meno"][r] -= d
        if aperte:
            v["c_buste"] = max(0, CARTE_A_BUSTA * aperte - wc_step)
            v["val_carte"] += aperte * VALORE_BUSTA
        out.append(v)
    for t, _, carte in pool:
        v = _vuoto(t[:10]); v["c_draft"] = len(carte); v["val_carte"] = valore_carte(carte)
        v["r_draft"] = sum(PE.rarita(g) in VALORE_CARTA for g in carte); out.append(v)
    return out


def somma(vv):
    """La somma di piu' voci di movimenti."""
    s = _vuoto("")
    for v in vv:
        for k in ("oro_piu", "gem_piu", "bu_ott", "bu_ap", "bu_comp", "c_draft", "c_premi", "c_buste", "val_carte", "bu_premi", "gem_premi"):
            s[k] += v[k]
        for k in ("spese", "spese_gem", "volte"):
            s[k].update(v[k])
        for r in range(4):
            s["jolly_piu"][r] += v["jolly_piu"][r]; s["jolly_meno"][r] += v["jolly_meno"][r]
    s["carte"] = s["c_draft"] + s["c_premi"] + s["c_buste"]
    s["oro_meno"], s["gem_meno"] = sum(s["spese"].values()), sum(s["spese_gem"].values())
    s["jolly"] = sum(s["jolly_piu"])
    # il ROI: quanto valgono in gemme le carte e i jolly ottenuti, contro l'incasso di oro e gemme portato in gemme
    s["roi"] = s["val_carte"] + sum(VALORE_JOLLY.get(RARITA[r], 0) * s["jolly_piu"][r] for r in range(4))
    s["incasso"] = s["oro_piu"] * GEMME_PER_ORO + s["gem_piu"]
    return s


def inizio(d, grana):
    """Il primo giorno del periodo che contiene d. grana: Giorno, Settimana (da lunedi'), Mese, Anno."""
    if grana == "Settimana":
        return d - datetime.timedelta(days=d.weekday())
    if grana == "Mese":
        return d.replace(day=1)
    if grana == "Anno":
        return d.replace(month=1, day=1)
    return d


def fine(k, grana):
    """L'ultimo giorno del periodo che comincia da k."""
    if grana == "Settimana":
        return k + datetime.timedelta(days=6)
    if grana == "Mese":
        return (k.replace(day=28) + datetime.timedelta(days=4)).replace(day=1) - datetime.timedelta(days=1)
    if grana == "Anno":
        return k.replace(month=12, day=31)
    return k


def tagli(a, b, g):
    """I periodi di gradino g fra a e b: [(x, y, nome, nome corto)]. Un periodo con meno giorni si legge dai suoi giorni, non sembra intero."""
    out, p = [], inizio(a, g)
    while p <= b:
        x, y = max(p, a), min(fine(p, g), b)
        nome, corto = nome_periodo(p, g), nome_periodo(p, g, True)
        if (x, y) != (p, fine(p, g)):
            nome = corto = f"{x.day}-{y.day} {MESI[y.month - 1][:3]} {y.year}" if g == "Mese" else f"{x:%d/%m}-{y:%d/%m}"
        out.append((x, y, nome, corto))
        p = fine(p, g) + datetime.timedelta(days=1)
    return out


def nome_periodo(k, grana, corto=False):
    if grana == "Settimana":
        return f"{k:%d/%m}-{fine(k, grana):%d/%m}"
    if grana == "Mese":
        return f"{MESI[k.month - 1][:3]} {k.year}" if corto else f"{MESI[k.month - 1].capitalize()} {k.year}"
    if grana == "Anno":
        return str(k.year)
    return f"{k:%d/%m}"


class Risorse:
    """I dati della scheda: le voci di movimenti, le prime e le ultime foto, e i tagli per periodo."""

    def __init__(self, foto, pool, eventi):
        self.foto, self.voci = foto, movimenti(foto, pool, eventi)
        self.gpo, self.via_cambio = GEMME_PER_ORO, None      # quante gemme vere vale un oro: lo rifa' imposta_cambio col win rate
        self.dal = datetime.date.fromisoformat(foto[0]["t"][:10]) if foto else None
        self.al = datetime.date.fromisoformat(foto[-1]["t"][:10]) if foto else None
        for v in self.voci:
            v["data"] = datetime.date.fromisoformat(v["giorno"])

    def periodi(self, grana):
        """I periodi che hanno dati, dal piu' vecchio. Si contano tutti, anche una settimana senza movimenti."""
        if not self.dal:
            return []
        out, k = [], inizio(self.dal, grana)
        while k <= self.al:
            out.append(k)
            k = fine(k, grana) + datetime.timedelta(days=1)
        return out

    def tra(self, a, b):
        """La somma dei giorni da a a b, piu' i giorni coperti dai dati, per la media. Le voci non cambiano dopo la lettura: ogni somma si fa una volta
        e si da' una copia (7 nov 2026: Resources rifaceva le stesse 150 somme a ogni tendina)."""
        memo = self.__dict__.setdefault("_tra", {})
        if (a, b) not in memo:
            memo[(a, b)] = self._tra_calcola(a, b)
        return copy.deepcopy(memo[(a, b)])

    def _tra_calcola(self, a, b):
        s = somma([v for v in self.voci if a <= v["data"] <= b])
        s["giorni"] = max(1, (min(b, self.al) - max(a, self.dal)).days + 1)
        s["jolly_r"], s["jolly_m"], s["jolly_ru"], s["jolly_mu"] = s["jolly_piu"][2], s["jolly_piu"][3], s["jolly_meno"][2], s["jolly_meno"][3]
        s["fine"] = min(b, self.al)       # il giorno del saldo a fine periodo
        return s

    def taglio(self, grana=None, k=None):
        """La somma di un periodo (o di tutto)."""
        return self.tra(k, fine(k, grana)) if k else self.tra(self.dal, self.al)

    def gradino(self, grana, k=None):
        """Il gradino delle righe del grafico: «grana» se k e' None (con un anno solo, i suoi mesi); dentro un periodo scelto il gradino sotto."""
        if k is None:
            return "Mese" if grana == "Anno" and len(self.periodi(grana)) == 1 else grana
        return {"Settimana": "Giorno", "Mese": "Settimana", "Anno": "Mese"}[grana]

    def righe(self, grana, k=None):
        """Le righe del grafico e della tabella: [(nome, nome corto, somma)]. Tutti i periodi di «grana» se k e' None (con un
        anno solo, i suoi mesi); dentro un periodo scelto il gradino sotto: la settimana per giorni, il mese per settimane
        tagliate ai suoi giorni, l'anno per mesi."""
        a, b = (self.dal, self.al) if k is None else (k, fine(k, grana))
        a, b = max(a, self.dal), min(b, self.al)
        return [(nome, corto, self.tra(x, y)) for x, y, nome, corto in tagli(a, b, self.gradino(grana, k))]

    def confronto(self, e):
        """Il trend contro il piano e (una simula), per il grafico (Autore, 6 nov 2026: «avere dei confronti tra la tendenza senza il farmer e quella con il piano di farmer per vedere quanto i
        trend migliorerebbero»; poi, sempre il 6 nov: «la spunta farmer non si sovrappone piu' ma sostituisce la vista»). senza e con danno ogni voce del grafico al giorno: senza e' la
        media di tutta la storia, con e' la base del trend piu' il piano (attese), che e' anche quel che il Farmer stima. L'oro farmato non cambia: il piano lo spende, non lo guadagna; le buste si
        aprono tutte, come conta attese. finisce: fra quanti giorni il piano svuota la cassa di oro e gemme, None se regge."""
        s, m = self.tra(self.dal, self.al), 365.25 / 12
        a = self.attese(e)
        senza = {c: s[c] / s["giorni"] for c in ("oro_piu", "oro_meno", "gem_piu", "gem_meno", "bu_ott", "bu_ap", "carte", "jolly_r", "jolly_m", "jolly_ru", "jolly_mu")}
        con = {c: v / m for c, v in dict(oro_piu=a["oro"], oro_meno=e["oro_speso"], gem_piu=a["gemme"], gem_meno=e["gemme_spese"], bu_ott=a["buste"], bu_ap=a["buste"], carte=a["carte"],
                                         jolly_r=a["jolly_r"], jolly_m=a["jolly_m"]).items()}
        con["jolly_ru"], con["jolly_mu"] = senza["jolly_ru"], senza["jolly_mu"]      # il piano non dice quanti jolly userai
        if e.get("con_pass", True):         # il prezzo del pass e' una spesa, non un'entrata che manca
            q_ = self.scatto_pass()["costo"] * PASS_ANNO / 12 / m
            con["gem_piu"] += q_; con["gem_meno"] += q_
        c = self.saldo()
        vuota = lambda cassa, piu, meno: int(cassa / (meno - piu)) if meno > piu else None
        return dict(senza=senza, con=con, finisce=dict(oro=vuota(c["oro"], con["oro_piu"], con["oro_meno"]), gem=vuota(c["gem"], con["gem_piu"], con["gem_meno"])))

    def media(self, s, chiave, grana):
        """Quanto fa «chiave» a settimana, al mese o all'anno, sui giorni coperti. -> (valore, «a settimana» | «al mese» | «all'anno»)."""
        if grana == "Settimana":
            return s[chiave] / s["giorni"] * 7, "per week"
        if grana == "Anno":
            return s[chiave] / s["giorni"] * 365.25, "per year"
        return s[chiave] / s["giorni"] * 365.25 / 12, "per month"

    def valori(self):
        """I valori misurati che il calcolatore usa: gemme medie di un pool di draft, di una busta aperta, draft e buste al mese."""
        s = self.tra(self.dal, self.al)
        pool = [v["val_carte"] for v in self.voci if v["c_draft"]]
        al_mese = 365.25 / 12 / s["giorni"]
        return dict(draft=sum(pool) / len(pool) if pool else 0.0,
                    busta=float(PREZZI_BUSTE["buste"]["gemme"]),      # il suo prezzo, jolly compresi: fino al 6 nov 2026 era 144 piu' tutti i jolly del periodo, 330 gemme per una cosa che in negozio ne costa 200
                    quick_mese=s["volte"]["Quick Draft"] * al_mese, buste_mese=s["bu_comp"] * al_mese, oro_mese=s["oro_piu"] * al_mese,
                    jolly_r=s["jolly_piu"][2] / s["bu_ap"] if s["bu_ap"] else 0.0, jolly_m=s["jolly_piu"][3] / s["bu_ap"] if s["bu_ap"] else 0.0,
                    carte_busta=s["c_buste"] / s["bu_ap"] if s["bu_ap"] else 0.0,
                    carte_draft=s["c_draft"] / len(pool) if pool else 0.0, rare_draft=sum(v["r_draft"] for v in self.voci if v["c_draft"]) / len(pool) if pool else 0.0)

    def spese_eventi(self, s):
        """Dove sono andati oro e gemme negli eventi di un taglio: [dict(nome, volte, oro, gemme)], prima chi e' costato di piu' (1.000 oro = 200 gemme). Buste, pass e altro non sono eventi."""
        nomi = (set(s["spese"]) | set(s["spese_gem"]) | set(s["volte"])) - {BUSTE, PASS, ALTRO}
        out = [dict(nome=n, volte=s["volte"][n], oro=s["spese"][n], gemme=s["spese_gem"][n]) for n in nomi]
        return sorted(out, key=lambda x: (-(x["oro"] * self.gpo + x["gemme"]), x["nome"]))

    def pass_comprati(self, a=None, b=None):
        """I Mastery Pass comprati fra due date: [dict(data, gemme)], letti dal passo col movimento del pass."""
        a, b = a or self.dal, b or self.al
        return [dict(data=v["data"], gemme=v["spese_gem"][PASS]) for v in sorted(self.voci, key=lambda x: x["data"]) if a <= v["data"] <= b and v["spese_gem"][PASS]]

    def rese(self, win=0.5, win_c=0.5):
        """Cosa porta una volta ogni opzione, tutto: gemme, buste, carte, jolly. -> {voce: dict(oro, gemme_in, gemme, buste, carte, jolly_r, jolly_m, valore)}.
        Le buste vinte portano carte e jolly come quelle aperte; il valore e' tutto in gemme."""
        v = self.valori()
        out = {}
        def voce(nome, oro, gem_in, gem, bu, c_pool, val_pool, var=0.0):
            out[nome] = dict(oro=oro, gemme_in=gem_in, gemme=gem, buste=bu, carte=c_pool + bu * v["carte_busta"], jolly_r=bu * v["jolly_r"], jolly_m=bu * v["jolly_m"],
                             valore=gem + val_pool + bu * v["busta"], var=var)
        voce("buste", PREZZI_BUSTE["buste"]["oro"], PREZZI_BUSTE["buste"]["gemme"], 0.0, 1.0, 0.0, 0.0)
        for nome, w, tab, c_pool, val_pool in (("quick", win, (ED.GEMME, ED.BUSTE), v["carte_draft"], v["draft"]), ("premier", win, (ED.P_GEMME, ED.P_BUSTE), v["carte_draft"], v["draft"]),
                                               ("costruiti", win_c, (COSTRUITO_GEMME, COSTRUITO_BUSTE), 0.0, 0.0)):
            gem, bu = ED.resa(w, *tab)[:2]
            # la varianza di una corsa: quanto oscilla il premio in gemme e buste fra 0 e 7 vittorie, al tuo win rate (il pool c'e' sempre, non oscilla)
            d_, media = ED.distribuzione(w), gem + bu * v["busta"]
            var = sum(q * (tab[0][k] + tab[1][k] * v["busta"] - media) ** 2 for k, q in d_.items())
            voce(nome, INGRESSI[nome]["oro"], INGRESSI[nome]["gemme"], gem, bu, c_pool, val_pool, var)
        return out

    def convenienza(self, win=0.5, win_c=0.5):
        """Cosa rende di piu', a parita' di cambio, al tuo win rate: [dict(k, nome, oro, gemme, sd)], valore per 1.000 oro e per 100 gemme, e quanto oscilla una corsa, dal piu' conveniente in oro."""
        r_ = self.rese(win, win_c)
        out = [dict(k=k, nome=NOMI_VOCE[k], oro=x["valore"] / x["oro"] * 1000, gemme=x["valore"] / x["gemme_in"] * 100, sd=x["var"] ** 0.5) for k, x in r_.items()]
        return sorted(out, key=lambda x: -x["oro"])

    def rischio(self, e, win=0.5, win_c=0.5):
        """Quanto oscilla il ritorno del piano e (una simula): la deviazione standard in gemme, somma delle varianze delle sue corse, una indipendente dall'altra. Le buste comprate non oscillano."""
        r_ = self.rese(win, win_c)
        return sum(r["volte"] * r_.get(r["nome"].split("_")[0], {}).get("var", 0.0) for r in e["righe"]) ** 0.5

    def cambio(self, e, win=0.5, win_c=0.5):
        """Quanto vale in gemme l'oro speso dal piano e (una simula), e quanto se ne spreca (Autore, 6 nov 2026: «dobbiamo sempre mantenere un corrispettivo tra oro e gemme e valutare quando
        spendo direttamente in oro, quanto sto sprecando in gemme, per valutare ad esempio il piano dove copro solo buste, se e' veramente valido o uno spreco in gemme»).
        Guarda solo le voci pagate in oro. in_gemme: l'oro al cambio di una busta, 1.000 = 200. valore: quel che quell'oro porta, tutto in gemme, coi valori di rese. spreco: quanto meno della voce
        che con lo stesso oro rende di piu' (meglio) al tuo win rate. gemme: le gemme vere che tornano, che pagano gli ingressi dopo; gemme_meglio: quante ne tornerebbero con la voce che ne da' di piu'."""
        r_ = self.rese(win, win_c)
        r_["mitiche"] = dict(oro=PREZZI_BUSTE["mitiche"]["oro"], gemme=0.0, valore=self.valori()["busta"] + VALORE_CARTA["M"] - VALORE_BUSTA)
        oro = valore = gemme = 0.0
        for r in e["righe"]:
            if r["oro"] and r["nome"] in r_:
                x = r_[r["nome"]]
                n = r["oro"] / x["oro"]
                oro += r["oro"]; valore += n * x["valore"]; gemme += n * x["gemme"]
        per = {k: x["valore"] / x["oro"] for k, x in r_.items()}
        liq = {k: x["gemme"] / x["oro"] for k, x in r_.items()}
        meglio, m_g = max(per, key=per.get), max(liq, key=liq.get)
        return dict(oro=oro, in_gemme=oro * self.gpo, valore=valore, gemme=gemme, meglio=meglio, valore_meglio=oro * per[meglio], spreco=max(0.0, oro * per[meglio] - valore), meglio_gemme=m_g, gemme_meglio=oro * liq[m_g])

    def cambio_oro(self, win=0.5, win_c=0.5, aperti_ora=None):
        """Quante gemme vere torna un oro, sulla via migliore che oggi c'e': i draft solo se sono aperti, gli eventi constructed sempre. Le gemme vere sono i premi in gemme, non il valore di carte e buste.
        -> dict(gpo, via, vie={via: gemme per oro})."""
        r_ = self.rese(win, win_c)
        ap = aperti() if aperti_ora is None else aperti_ora
        vie = {k: r_[k]["gemme"] / r_[k]["oro"] for k in ("quick", "premier", "costruiti") if k == "costruiti" or ap.get(k)}
        via = max(vie, key=vie.get)
        return dict(gpo=vie[via], via=via, vie=vie)

    def imposta_cambio(self, win=0.5, win_c=0.5, aperti_ora=None, busta=False):
        """Mette il cambio al win rate dato; se cambia, i piani gia' fatti non valgono piu'. busta=True: il prezzo di una busta, 1.000 oro = 200 (Autore, 8 nov 2026: «diamo dei flag in testa:
        gold gems rate o personal wr to gems»): l'oro letto come valore in carte, non come gemme che tornano. -> dict(gpo, via)."""
        c = dict(gpo=GEMME_PER_ORO, via="busta") if busta else self.cambio_oro(win, win_c, aperti_ora)
        if abs(c["gpo"] - self.gpo) > 1e-12 or c["via"] != self.via_cambio:
            self.gpo, self.via_cambio = c["gpo"], c["via"]
            self.__dict__.pop("_memo_piani", None)
            self.__dict__.pop("_soglie", None)
        return c

    def pareggi(self, win=0.5, win_c=0.5):
        """Il pareggio in gemme vere di ogni evento: il win rate da cui un ingresso pagato in gemme ti torna tutto in gemme, cioe' il punto da cui quell'evento si gioca gratis per sempre.
        I draft al variare del win rate limited, gli eventi constructed del constructed. -> {voce: win rate, o None se non arriva entro il 95%}."""
        out = {}
        for k in ("quick", "premier", "costruiti"):
            out[k] = None
            for pc in range(20, 96):
                x = self.rese(pc / 100 if k != "costruiti" else win, pc / 100 if k == "costruiti" else win_c)[k]
                if x["gemme"] >= x["gemme_in"]:
                    out[k] = pc / 100
                    break
        return out

    def piano(self, obiettivo="jolly", win=0.5, set_=None, aperti_ora=None, win_c=0.5, oro_buste=True, mazzo=None):
        """Il piano del goal, col Mastery Pass e senza: vince il migliore per l'obiettivo, contando anche quel che il pass mette nella base. A parita', entro il 3%, si tiene il pass: da' anche quel
        che qui non si conta. oro_buste=False: l'oro non compra buste (Autore, 8 nov 2026: «una spunta che mi permette di decidere se nell'algoritmo voglio inserire la richiesta di spendere
        meno oro possibile in buste, se non e' flaggato l'algoritmo ovviamente gioca anche sulle buste»): l'oro va negli eventi o resta oro, le buste vengono solo da gemme e premi.
        -> dict come _piano, con pass=True o False."""
        memo = self.__dict__.setdefault("_memo_piani", {})
        chiave = (tuple(sorted(pesi_obiettivo(obiettivo).items())), round(win, 4), round(win_c, 4), set_, datetime.date.today(), None if aperti_ora is None else tuple(sorted((k, str(x)) for k, x in aperti_ora.items())), oro_buste,
                  tuple(sorted((mazzo or {}).items())), round(self.gpo, 6))
        if chiave not in memo:
            memo[chiave] = self._scegli_pass(obiettivo, win, set_, aperti_ora, win_c, oro_buste, mazzo)
        return dict(memo[chiave])

    def _scegli_pass(self, obiettivo, win, set_, aperti_ora, win_c, oro_buste=True, mazzo=None):
        pesi = pesi_obiettivo(obiettivo)
        top = None
        if len(pesi) > 1:
            # nel mix i due piani si misurano sugli stessi massimi, col pass e senza, anche quando uno solo sta nella roadmap (verifica_piani, 9 nov 2026: col pass fuori dalla roadmap il
            # piano senza pass si misurava sui massimi suoi, e il jolly valeva 8.132 invece di 9.936: «gemme 34 + jolly 33 + carte 33» al 30% sceglieva un piano peggiore del 12%)
            tops = [t for t in (self._piano(obiettivo, win, set_, aperti_ora, win_c, c_p, solo_top=True, oro_buste=oro_buste, mazzo=mazzo) for c_p in (True, False)) if t]
            top = {g: max(t[g] for t in tops) for g in pesi} if tops else None
        con = self._piano(obiettivo, win, set_, aperti_ora, win_c, True, top=top, oro_buste=oro_buste, mazzo=mazzo)
        senza = self._piano(obiettivo, win, set_, aperti_ora, win_c, False, top=top, oro_buste=oro_buste, mazzo=mazzo)
        if con is None or senza is None:
            return dict(senza or con, **{"pass": senza is None})
        if con["eseguibile"] != senza["eseguibile"]:     # uno solo sta nel calendario e nella cassa: vince lui
            return dict(con, **{"pass": True}) if con["eseguibile"] else dict(senza, **{"pass": False})
        if len(pesi) > 1:            # il pass solo se alza la quota piu' bassa
            return dict(con, **{"pass": True}) if con["esito"]["meta"] > senza["esito"]["meta"] + 1e-9 else dict(senza, **{"pass": False})
        g, v = next(iter(pesi)), self.valori()
        def punti(p, c_p):
            b = self.base(c_p)
            return p["esito"]["meta"] + {"jolly": b["buste"] * (VALORE_JOLLY["R"] * v["jolly_r"] + VALORE_JOLLY["M"] * v["jolly_m"]), "buste": b["buste"]}.get(g, 0.0)
        return dict(con, **{"pass": True}) if punti(con, True) > punti(senza, False) + 1e-9 else dict(senza, **{"pass": False})     # il pass solo se serve al goal: 3.400 gemme non si spendono per pareggiare

    def _piano(self, obiettivo, win, set_, aperti_ora, win_c, con_pass, top=None, solo_top=False, oro_buste=True, mazzo=None):
        """Il massimizzatore: dove investire il 100% del guadagno del mese per un obiettivo, «jolly», «gemme», «buste» o «carte» (del set set_), al win rate del giocatore.
        Gli obiettivi si possono mischiare (Autore, 4 nov 2026: «costruiamo il menu dei goal in modo da poterli costruire misti»): obiettivo e' anche una lista, o {obiettivo: peso}.
        Di ogni obiettivo si misura la quota del suo massimo e vince il piano con la quota piu' bassa piu' alta: una somma finirebbe tutta su un obiettivo solo, i soldi sono gli stessi.
        Nel mix ogni obiettivo si misura sul guadagno rispetto a non fare niente, senza pass (Autore, 6 nov 2026: «i goal misti dovrebbero creare nuove formule per gli obiettivi»): le gemme che hai gia' non
        sono gemme convertite, e un piano che ne chiude meno di quante ne avevi ha quota negativa; quel che il Mastery Pass mette nella base conta per l'obiettivo, e il pass paga il suo prezzo. top: i massimi comuni.
        Tiene solo i piani col ROI non negativo e, a parita' di risultato entro il 3%, sceglie il guadagno piu' alto, tolta una deviazione standard, e a parita' chi investe di piu'. Prova ogni combinazione di Quick, Premier ed eventi constructed che l'oro paga, con quel che avanza in buste. Le gemme, quelle del trend piu' quelle vinte, si reinvestono
        nel modo migliore: buste, o ingressi in gemme, che col win rate alto si ripagano e si possono ripetere (al massimo MAX_EVENTI al mese), o si tengono. Di ogni piano conta
        tutto. Vince l'obiettivo.
        -> dict(voci, gemme_voci, esito, rese, oro_mese, oro_sett, settimane, gemme_mese, aperti); esito["quote"]: {obiettivo: frazione del suo massimo}."""
        pesi = pesi_obiettivo(obiettivo)
        solo_gemme = list(pesi) == ["gemme"]
        solo_carte = list(pesi) == ["carte"]
        # si investe solo in quel che serve al goal (Autore, 6 nov 2026: «la roadmap porti il giocatore a investire risorse esclusivamente nel goal senza sprechi, esempio: se voglio convertire oro in gemme non
        # comprero' mai buste nemmeno se vado in avanzo di gold»): col goal gemme niente buste, l'oro che avanza resta oro; col goal carte niente eventi constructed, che carte non ne danno
        misto_gemme = "gemme" in pesi and len(pesi) > 1      # col mix le gemme vinte si possono anche dividere fra buste e cassa
        v, rese, b = self.valori(), self.rese(win, win_c), self.base(con_pass)
        # il goal del mazzo (Autore, 8 nov 2026, «ok» a: «il traguardo concreto e' il tuo prossimo mazzo competitivo»): mazzo = i jolly rari e mitici che mancano oltre quelli che hai.
        # Il progresso del mese e' la rarita' piu' indietro, al massimo 1 (il mazzo e' fatto): contano i jolly del piano e quelli delle buste che arrivano comunque (pass compreso).
        n_r, n_m = (mazzo or {}).get("R", 0), (mazzo or {}).get("M", 0)

        def progresso(jr, jm, bu_base):
            jr, jm = jr + bu_base * v["jolly_r"], jm + bu_base * v["jolly_m"]
            parti = ([min(1.0, jr / n_r)] if n_r else []) + ([min(1.0, jm / n_m)] if n_m else [])
            return min(parti) if parti else 1.0
        ap = aperti() if aperti_ora is None else aperti_ora
        # i draft si contano solo se nei prossimi 30 giorni si possono fare: un Quick che chiude oggi non regge un mese (Autore, 6 nov 2026: «non considera il fatto che le quick draft di quel set chiudono oggi»)
        posti = dict(quick=99, premier=99)
        if aperti_ora is None:
            ap = dict(ap)
            cal, oggi_ = _calendario(), datetime.date.today()
            for k in posti:
                set_goal = set_ if "carte" in pesi else None
                posti[k] = capienza(k, oggi_, cal, set_goal)
                if posti[k]:
                    ap[k] = set_goal or ap.get(k) or primo_set(k, oggi_, cal) or "altro"
                elif set_goal and len(pesi) > 1:       # nel mix gli altri draft servono agli altri obiettivi
                    posti[k] = capienza(k, oggi_, cal)
                    # col set suo, non quello del goal (8 nov 2026: col Quick di Bloomburrow aperto, il mix «carte FRA + gemme» contava le sue carte come carte FRA, e FRA e TRK davano lo stesso piano)
                    ap[k] = (ap.get(k) or primo_set(k, oggi_, cal) or "altro") if posti[k] else None
                else:
                    ap[k] = None
        oro_m, gem_in, tok = b["oro"], b["gemme"], self.saldo().get("token", 0)       # i token che hai adesso: il piano e' di un mese, spesi non ci sono piu'
        if aperti_ora is None:
            # il piano vero investe quel che hai davvero nei suoi 30 giorni: la cassa di oggi piu' quel che entra, e il pass solo se esce in questi giorni
            sa, b0, sp0, mese = self.saldo(), self.base(False), self.scatto_pass(), (GIORNI_ROADMAP - 1) * 12 / 365.25      # i giorni che la roadmap incassa: il primo e' oggi
            esce = sp0["costo"] and any(s_.get("premier") and s_.get("inizio") and 0 <= (datetime.date.fromisoformat(s_["inizio"]) - oggi_).days < GIORNI_ROADMAP for s_ in cal.values())
            if con_pass and not esce:
                return None
            oro_m = sa["oro"] + b0["oro"] * mese + (sp0["oro"] if con_pass else 0)
            gem_in = sa["gem"] + b0["gemme"] * mese + (sp0["gem"] - sp0["costo"] if con_pass else 0)
        settimane = 365.25 / 12 / 7
        nuovo = set_costruiti()
        set_di = {"buste": set_, "quick": ap.get("quick"), "premier": ap.get("premier"), "costruiti": nuovo}
        costr_set = nuovo == set_          # i constructed danno buste del set del goal: col goal carte servono anche loro (9 nov 2026)
        chiavi = ("buste", "carte", "jolly_r", "jolly_m", "valore")
        cq, cp, cc, cb = rese["quick"]["oro"], rese["premier"]["oro"], rese["costruiti"]["oro"], rese["buste"]["oro"]
        prezzo_g = rese["buste"]["gemme_in"]
        # le gemme non comprano mai buste (Autore, 9 nov 2026: «non voglio spendere gemme in buste», poi «le gemme non devono essere contate per l'acquisto buste mai»): restano gemme o
        # pagano ingressi; la spunta delle buste riguarda solo l'oro. Fino a quel giorno le gemme che avanzavano andavano in buste da 200
        vie_gemme = ["tiene"] + [k for k in ("quick", "premier", "costruiti") if (k == "costruiti" and (not solo_carte or costr_set)) or (k != "costruiti" and ap.get(k))]
        q_max = min(int(oro_m // cq), posti["quick"]) if ap.get("quick") else 0
        p_max = min(int(oro_m // cp) + tok, posti["premier"]) if ap.get("premier") else 0
        piani = []
        misto = len(pesi) > 1

        def quanti_in_gemme(via, disp, n_):
            """Gli ingressi pagati in gemme da provare per una via. Ogni ingresso si paga prima del suo premio. Un draft non va oltre i posti del calendario che restano dopo quelli in
            oro (verifica_piani, 9 nov 2026: col win rate al 55% il piano carte TRK contava piu' Quick in gemme dei posti, la roadmap li scartava e ripiegava su un piano peggiore del 5%).
            Tutti, da 1 al massimo: nel mix le gemme servono a un obiettivo e gli ingressi a un altro, e il meglio sta in mezzo (stessa verifica: con gemme 50 + carte 50 il meglio era
            spesso 1-6 Quick in gemme, il piano provava tutto o niente; con una griglia 1-6, 8, 10... mancava il 9 e il piano chiudeva il 6% sotto); con un goal solo il massimo puo' non
            stare nella cassa dei giorni della roadmap, e quello appena sotto si' (carte FRA al 55%: 5 Premier e 13 in gemme fuori, 11 dentro; il piano provava solo il massimo)."""
            if via not in rese or via == "buste":
                return (0,)
            ent, gain = rese[via]["gemme_in"], rese[via]["gemme"]
            if disp < ent:
                return ()
            g = MAX_EVENTI if gain >= ent else int((disp - ent) // (ent - gain)) + 1
            g = min(g, MAX_EVENTI, max(0, posti[via] - n_[via]) if via in posti else MAX_EVENTI)
            if not g:
                return ()
            if aperti_ora is not None:
                # le soglie e le prove col calendario finto: niente roadmap, conta il mese. Col goal solo basta il massimo; nel mix una griglia, che per dire dove cambia la rotta basta
                # (tutti gli ingressi portavano le soglie del Farmer da 2 a 18 s, in un filo accanto alla finestra)
                return (g,) if not misto else sorted({x for x in (1, 2, 3, 4, 6, 8, 12, 18, 24) if x < g} | {g})
            return range(1, g + 1)
        # le combinazioni si contano una volta per chiamata uguale: il mix chiama _piano due volte per gli stessi piani, prima per i massimi e poi per scegliere. Poche voci: ognuna e'
        # decine di migliaia di piani
        cache_en = self.__dict__.setdefault("_enum_piani", {})
        k_en = (tuple(sorted(pesi.items())), round(win, 4), round(win_c, 4), set_, con_pass, oro_buste, None if aperti_ora is None else tuple(sorted((k, str(x)) for k, x in aperti_ora.items())),
                tuple(sorted((mazzo or {}).items())), round(self.gpo, 6), self.via_cambio, datetime.date.today(), round(oro_m, 3), round(gem_in, 3))
        for q in (range(q_max + 1) if k_en not in cache_en else ()):
            for p in range(p_max + 1):
                tq = 0; tp = min(p, tok)        # il draft token paga un Premier o un Traditional, non un Quick (pagina di Wizards dello schedule del set)
                oro = (q - tq) * cq + (p - tp) * cp
                if oro > oro_m:
                    break
                for c in range(1 if solo_carte and not costr_set else int((oro_m - oro) // cc) + 1):
                    resto = oro_m - oro - c * cc
                    n = dict(quick=q, premier=p, costruiti=c, buste=0 if solo_gemme or not oro_buste else int(resto // cb))
                    premi = q * rese["quick"]["gemme"] + p * rese["premier"]["gemme"] + c * rese["costruiti"]["gemme"]
                    t0 = {k: sum(n[x] * rese[x][k] for x in n) for k in chiavi}
                    c_set0 = sum(n[k] * rese[k]["carte"] for k in n if set_di[k] == set_)
                    for via, gem_ev in ((v_, g_) for v_ in vie_gemme for g_ in quanti_in_gemme(v_, gem_in + premi, n)):
                        disp = gem_in + premi
                        if disp < 0:           # il mese non paga il Mastery Pass: a lungo andare la cassa finirebbe
                            continue
                        if gem_ev:
                            disp += gem_ev * (rese[via]["gemme"] - rese[via]["gemme_in"])
                        pieno = int(disp // prezzo_g)
                        if True:      # nessuna gemma in buste, mai (9 nov 2026)
                            quote_b = (0,)
                        elif misto_gemme:
                            quote_b = sorted({0, pieno // 4, pieno // 2, 3 * pieno // 4, pieno})
                        else:
                            quote_b = (pieno,)
                        for gem_b in quote_b:
                            gemme = disp - gem_b * prezzo_g
                            t = dict(t0); c_set = c_set0 + gem_b * rese["buste"]["carte"]
                            for k in chiavi:
                                t[k] += gem_b * rese["buste"][k] + (gem_ev * rese[via][k] if gem_ev else 0)
                            t["valore"] += gem_in - gem_b * prezzo_g - (gem_ev * rese[via]["gemme_in"] if gem_ev else 0)
                            if gem_ev and set_di[via] == set_:
                                c_set += gem_ev * rese[via]["carte"]
                            # «valore»: tutto in gemme col cambio di 1.000 oro = 200, l'oro che avanza compreso: sceglie da solo fra eventi e buste (Autore, 6 nov 2026: «tieni sempre in considerazione il cambio gemme oro / se conviene di piu' investire su eventi che sulle buste»)
                            mete = {"jolly": VALORE_JOLLY["R"] * t["jolly_r"] + VALORE_JOLLY["M"] * t["jolly_m"], "gemme": gemme, "carte": c_set, "buste": t["buste"], "valore": t["valore"] + (resto - n["buste"] * cb) * self.gpo,
                                    "mazzo": progresso(t["jolly_r"], t["jolly_m"], b["buste"])}
                            piani.append((mete, t["valore"], n, gem_b, via if gem_ev else None, gem_ev, tq, tp, gemme, resto - n["buste"] * cb, t))
        if k_en in cache_en:
            piani = cache_en[k_en][0]
        if not piani:         # nessun piano regge il pass
            return None
        # un goal non chiude mai in perdita (Autore, 6 nov 2026: «la funzione dei goal deve essere quella di trovare sempre il migliore risultato possibile senza mandare il roi in negativo e investendo
        # la maggiore quantita' di risorse a disposizione / i goal non possono avere roi negativo»): lo stesso bilancio di simula, fatto qui per ogni piano. Comprare buste in oro e' alla pari, quindi c'e' sempre
        sp_, q_ = self.scatto_pass(), PASS_ANNO / 12 if con_pass else 0.0
        # il ROI conta l'oro alle gemme vere che ti torna, anche con la spunta Pack price (Autore, 8 nov 2026: «convert gold to gems ancora mi manda ai quick draft invece che ai
        # constructed»): a 1.000 oro = 200 ogni evento constructed sembrava in perdita e la regola del ROI non negativo lo scartava, restavano i Quick col loro pool. Pack price e' un modo di
        # vedere l'oro, non un vincolo sulla conversione
        g_v = self.cambio_oro(win, win_c, aperti_ora)["gpo"] if self.via_cambio == "busta" else self.gpo
        c_pass, v_pass = sp_["costo"] * q_, (sp_["gem"] + sp_["oro"] * g_v + sp_["bu"] * v["busta"]) * q_

        bil_ = cache_en[k_en][1] if k_en in cache_en else {}       # ogni bilancio una volta per piano (8 nov 2026: le soglie lo rifacevano 268.000 volte e il Farmer fermava la finestra fino a 1,7 s)

        def bilancio(x):
            """-> (quanto spendi, quanto ottieni), in gemme."""
            k_ = id(x)
            if k_ not in bil_:
                bil_[k_] = _bilancio(x)
            return bil_[k_]

        def _bilancio(x):
            _m, _v, n_, gb, via_, gev, tq_, tp_ = x[:8]
            sp = c_pass + tp_ * min(rese["premier"]["gemme_in"], rese["premier"]["valore"]) + (n_["premier"] - tp_) * cp * g_v + n_["quick"] * cq * g_v + n_["costruiti"] * cc * g_v + n_["buste"] * cb * g_v + gb * prezzo_g
            ott = v_pass + sum(n_[k] * rese[k]["valore"] for k in n_) + gb * rese["buste"]["valore"]
            if via_:
                sp += gev * rese[via_]["gemme_in"]; ott += gev * rese[via_]["valore"]
            return sp, ott
        def sd(x):
            """La deviazione standard del ritorno del piano x, in gemme."""
            _m, _v, n_, gb, via_, gev = x[:6]
            return (sum(n_[k] * rese[k]["var"] for k in n_) + (gev * rese[via_]["var"] if via_ else 0.0)) ** 0.5
        sani = [x for x in piani if (lambda b_: b_[1] - b_[0])(bilancio(x)) >= -1e-6]
        piani = sani or piani
        if k_en not in cache_en:
            if len(cache_en) >= 4:
                cache_en.clear()
            cache_en[k_en] = (piani, bil_)
        if len(pesi) > 1:
            # il punto zero del mix: non fare niente, senza pass. In piu' quel che il pass mette nella base, se c'e'
            b0_ = self.base(False)
            if aperti_ora is None:
                sa0, m0 = self.saldo(), (GIORNI_ROADMAP - 1) * 12 / 365.25
                g0, o0 = sa0["gem"] + b0_["gemme"] * m0, sa0["oro"] + b0_["oro"] * m0
            else:
                g0, o0 = b0_["gemme"], b0_["oro"]
            bu_p = b["buste"] - b0_["buste"]
            extra = dict(jolly=bu_p * (VALORE_JOLLY["R"] * v["jolly_r"] + VALORE_JOLLY["M"] * v["jolly_m"]), buste=bu_p, valore=bu_p * v["busta"], gemme=0.0, carte=0.0, mazzo=0.0)
            zero = dict(jolly=0.0, buste=0.0, carte=0.0, gemme=g0, valore=g0 + o0 * self.gpo, mazzo=progresso(0.0, 0.0, b0_["buste"]))
            guadagno = lambda m, g: m[g] + extra[g] - zero[g]
        else:
            guadagno = lambda m, g: m[g]
        tetto = {g: max(guadagno(x[0], g) for x in piani) for g in pesi}
        if solo_top:
            return tetto
        top = top or tetto
        quota = lambda m, g: guadagno(m, g) / top[g] if top[g] > 0 else 1.0
        pun_ = {}

        def punti(m):
            k_ = id(m)
            if k_ not in pun_:
                pun_[k_] = min(quota(m, g) / pesi[g] for g in pesi)
            return pun_[k_]
        # la roadmap mette ogni voce nelle finestre del set con cui il piano l'ha contata (Autore, 9 nov 2026: «se faccio convert gold in gems al 50% e al 50% cards from a set TRK mi
        # manda a fare i quick draft di BLB»: il piano contava i Quick come Quick di TRK, che aprono il 19, e la roadmap filtrava il set solo col goal carte da solo, quindi li metteva
        # nel Quick di Bloomburrow aperto adesso, che chiude prima)
        solo_ = dict(quick=ap.get("quick"), premier=ap.get("premier"), buste=set_, mitiche=set_, costruiti=set_ if costr_set else None) if "carte" in pesi else None
        visti = {}

        def eseguibile(x):
            """Il piano sta nel calendario e nella cassa di ogni giorno? Se no resterebbe a meta': si prova la roadmap vera."""
            if aperti_ora is not None:      # le prove e le soglie: un calendario finto, conta il mese
                return True
            if id(x) not in visti:
                _m, _v, n_, gb, via_, gev, tq_, tp_ = x[:8]
                pg = dict(quick="token" if tq_ else "oro", premier="token" if tp_ else "oro", costruiti="oro", buste="oro", mitiche="oro")
                e_ = self.simula(n_["quick"], n_["premier"], n_["buste"], 0, pg, win, oro_m, buste_gemme=gb, costruiti=n_["costruiti"], win_c=win_c, gemme_mese=gem_in, gemme_voci={via_: gev} if via_ else None, con_pass=con_pass)
                visti[id(x)] = not self.roadmap(e_, win=win, win_c=win_c, solo_set=solo_)["fuori"]
            return visti[id(x)]
        ordine = sorted(piani, key=lambda x: (-punti(x[0]), -x[1]))
        primo = next((x for x in ordine[:MAX_PROVE] if eseguibile(x)), None)
        ok_ = primo is not None
        p_primo = punti((primo or ordine[0])[0])
        soglia = p_primo - abs(p_primo) * 0.03
        # a parita' di risultato il guadagno piu' alto, tolta la varianza, e a parita' di guadagno chi investe di piu' (Autore, 6 nov 2026: «il calcolo corretto dovrebbe essere sempre: spesa vs varianza vs
        # % win rate», poi «spendere meno per investire il massimo e guadagnare il massimo»): la cassa si investe tutta, ogni voce al prezzo migliore, oro sulle buste e gemme sugli ingressi
        def guadagno_prudente(x):
            sp, ott = bilancio(x)
            return ott - sp - sd(x)
        fascia = sorted((x for x in piani if punti(x[0]) >= soglia), key=lambda x: (-round(guadagno_prudente(x)), -bilancio(x)[0], -x[1], -punti(x[0])))
        scelto = next((x for x in fascia[:MAX_PROVE] if eseguibile(x)), primo or ordine[0])
        mete, valore, n, gem_b, via, gem_ev, tq, tp, gemme, oro_resto, t = scelto
        meta = mete[next(iter(pesi))] if len(pesi) == 1 else punti(mete)
        # in quante settimane il mazzo e' fatto a questo ritmo: la rarita' piu' lenta (None: niente da fare, il mazzo si crafta gia')
        sett_m = None
        if n_r or n_m:
            jr_, jm_ = t["jolly_r"] + b["buste"] * v["jolly_r"], t["jolly_m"] + b["buste"] * v["jolly_m"]
            mesi = max((n_r / jr_ if jr_ else float("inf")) if n_r else 0.0, (n_m / jm_ if jm_ else float("inf")) if n_m else 0.0)
            sett_m = mesi * 365.25 / 12 / 7
        return dict(voci=dict(n, mitiche=0, buste_gemme=gem_b, tq=tq, tp=tp), gemme_voci={via: gem_ev} if via else {}, esito=dict(t, meta=meta, gemme=gemme, oro_resto=oro_resto, settimane_mazzo=sett_m, carte_set=mete["carte"], quote={g: quota(mete, g) for g in pesi}, spende=bilancio(scelto)[0], ottiene=bilancio(scelto)[1]),
                    rese=rese, oro_mese=oro_m, oro_sett=oro_m / settimane, settimane=settimane, gemme_mese=gem_in, aperti=ap, eseguibile=ok_, solo=solo_)

    def soglie(self, obiettivo="jolly", win=0.5, win_c=0.5, set_=None, aperti_ora=None, oro_buste=True, mazzo=None):
        """Dove cambia la rotta col win rate: si rifa' il piano per ogni win rate, prima il limited e poi il constructed, tenendo fermo l'altro al valore del giocatore.
        -> dict(limited=[(da, a, rotta)], constructed=[...]); rotta e' la voce che prende piu' oro, piu' il modo di reinvestire le gemme. Grado C: dipende dalle tabelle dei premi."""
        ap = aperti() if aperti_ora is None else aperti_ora
        chiave = (tuple(sorted(pesi_obiettivo(obiettivo).items())), round(win, 3), round(win_c, 3), set_, tuple(sorted((k, str(x)) for k, x in ap.items())), oro_buste, tuple(sorted((mazzo or {}).items())), round(self.gpo, 6))
        memo = self.__dict__.setdefault("_soglie", {})
        if chiave in memo:
            return memo[chiave]
        def rotta(p):
            vo, r = p["voci"], p["rese"]
            oro = {k: vo[k] * r[k]["oro"] for k in ("quick", "premier", "costruiti", "buste")}
            testa = max(oro, key=oro.get)
            g = next(iter(p["gemme_voci"]), None)
            return testa, g or ("buste" if vo["buste_gemme"] else None)
        out = {}
        for nome in ("limited", "constructed"):
            pezzi = []
            for pc in range(PASSO_SOGLIE * 15, 81, PASSO_SOGLIE):
                p = self.piano(obiettivo, pc / 100 if nome == "limited" else win, set_, ap, pc / 100 if nome == "constructed" else win_c, oro_buste, mazzo)
                r = rotta(p)
                if pezzi and pezzi[-1][2] == r:
                    pezzi[-1][1] = pc
                else:
                    pezzi.append([pc, pc, r])
            out[nome] = [tuple(x) for x in pezzi]
        memo[chiave] = out
        return out

    def scatto_pass(self):
        """Quel che il Mastery Pass da' tutto insieme il giorno che lo compri, dai log: -> dict(oro, gem, bu, c, costo). Zero senza acquisti."""
        out = dict(oro=0, gem=0, bu=0, c=0, costo=self.tra(self.dal, self.al)["spese_gem"][PASS])
        giorni = {f["t"][:10] for f in self.foto for m in f["mov"] if m["f"] == "CampaignGraphPurchaseNode"}
        for f in self.foto:
            if f["t"][:10] in giorni:
                for m in f["mov"]:
                    if m["f"] == "CampaignGraphTieredRewardNode":
                        out["oro"] += m["oro"]; out["gem"] += m["gem"]; out["bu"] += m["bu"]; out["c"] += m["c"]
        return out

    def base(self, con_pass=True):
        """Quel che entra al mese senza comprare niente e senza eventi, dal trend. Il Mastery Pass non e' un'entrata qualunque: lo scatto del giorno dell'acquisto si ripete a ogni set, non ogni 46 giorni
        di log, e costa. Quindi si toglie dal trend e si rimette spalmato su PASS_ANNO, col suo prezzo: al mese in gemme puo' venire negativo, e il piano deve pagarlo con quel che vince.
        con_pass=False: senza comprarlo."""
        s = self.tra(self.dal, self.al)
        m = 365.25 / 12 / s["giorni"]
        sp, q = self.scatto_pass(), PASS_ANNO / 12 if con_pass else 0.0
        return dict(oro=(s["oro_piu"] - sp["oro"]) * m + sp["oro"] * q, gemme=(s["gem_piu"] - s["gem_premi"] - sp["gem"]) * m + (sp["gem"] - sp["costo"]) * q,
                    buste=max(0, s["bu_ott"] - s["bu_comp"] - s["bu_premi"] - sp["bu"]) * m + sp["bu"] * q, carte=(s["c_premi"] - sp["c"]) * m + sp["c"] * q)

    def attese(self, e):
        """Le risorse attese al mese: la base del trend piu' quel che porta il piano e (una simula)."""
        v, b, r = self.valori(), self.base(e.get("con_pass", True)), e["ritorno"]
        buste = b["buste"] + r["buste"]
        return dict(oro=b["oro"], gemme=b["gemme"] + r["gemme"], buste=buste, jolly_r=buste * v["jolly_r"], jolly_m=buste * v["jolly_m"],
                    carte=b["carte"] + r["carte"] + b["buste"] * v["carte_busta"])

    def simula(self, quick=0, premier=0, buste=0, mitiche=0, paga="oro", win=0.5, oro_mese=0, buste_gemme=0, costruiti=0, win_c=0.5, gemme_mese=0, gemme_voci=None, con_pass=True):
        """Un mese di spese contro il ROI atteso. paga: una valuta per tutti, o {voce: "oro" | "gemme" | "token"} per voce (quick, premier, buste, mitiche);
        il token vale solo per i draft e quelli che mancano si pagano in oro. win: da 0 a 1. buste_gemme: buste comprate con le gemme vinte, a parte dalle altre. gemme_voci: {voce: n} ingressi in gemme in piu', dal piano.
        -> dict con le righe, i totali e il ritorno per risorsa."""
        val = self.valori()
        cassa = self.saldo()
        pag = {k: paga for k in ("quick", "premier", "costruiti", "buste", "mitiche")} if isinstance(paga, str) else dict(paga)
        token_liberi = cassa.get("token", 0)
        token_usati = token_mancati = 0
        oro_sp = gem_sp = 0.0
        righe = []
        for nome, n, w_, tabelle in (("quick", quick, win, (ED.GEMME, ED.BUSTE)), ("premier", premier, win, (ED.P_GEMME, ED.P_BUSTE)),
                                     ("costruiti", costruiti, win_c, (COSTRUITO_GEMME, COSTRUITO_BUSTE))):
            gem, bu = ED.resa(w_, *tabelle)[:2]
            v_ = pag.get(nome, "oro")
            if nome in ("costruiti", "quick") and v_ == "token":      # il draft token paga solo Premier e Traditional
                v_ = "oro"
            con_token = min(n, token_liberi) if v_ == "token" else 0
            token_liberi -= con_token; token_usati += con_token
            resto = n - con_token
            if v_ == "token":
                token_mancati += resto
            valuta = "gemme" if v_ == "gemme" else "oro"
            spesa = resto * INGRESSI[nome][valuta]
            oro_sp += spesa if valuta == "oro" else 0; gem_sp += spesa if valuta == "gemme" else 0
            righe.append(dict(nome=nome, volte=n, valuta=v_, costo=spesa * (self.gpo if valuta == "oro" else 1) + con_token * min(INGRESSI[nome]["gemme"], gem + (0.0 if nome == "costruiti" else val["draft"]) + bu * val["busta"]), oro=spesa if valuta == "oro" else 0, gemme=spesa if valuta == "gemme" else 0, token=con_token,
                              premi=n * gem, buste=n * bu,
                              roi=n * ((0.0 if nome == "costruiti" else val["draft"]) + bu * val["busta"])))
        extra_ev = 0
        for nome, n in (gemme_voci or {}).items():
            w_, tabelle = (win_c, (COSTRUITO_GEMME, COSTRUITO_BUSTE)) if nome == "costruiti" else (win, (ED.GEMME, ED.BUSTE) if nome == "quick" else (ED.P_GEMME, ED.P_BUSTE))
            gem, bu = ED.resa(w_, *tabelle)[:2]
            spesa = n * INGRESSI[nome]["gemme"]
            gem_sp += spesa; extra_ev += 0 if nome == "costruiti" else n
            righe.append(dict(nome=nome + "_gemme", volte=n, valuta="gemme", costo=spesa, oro=0, gemme=spesa, token=0, premi=n * gem, buste=n * bu, roi=n * ((0.0 if nome == "costruiti" else val["draft"]) + bu * val["busta"])))
        for nome, n, extra in (("buste", buste, 0.0), ("mitiche", mitiche, VALORE_CARTA["M"] - VALORE_BUSTA), ("buste_gemme", buste_gemme, 0.0)):
            valuta = "gemme" if nome == "buste_gemme" or pag.get(nome) == "gemme" else "oro"
            spesa = n * PREZZI_BUSTE["buste" if nome == "buste_gemme" else nome][valuta]
            oro_sp += spesa if valuta == "oro" else 0; gem_sp += spesa if valuta == "gemme" else 0
            righe.append(dict(nome=nome, volte=n, valuta=valuta, costo=spesa * (self.gpo if valuta == "oro" else 1), oro=spesa if valuta == "oro" else 0, gemme=spesa if valuta == "gemme" else 0, token=0,
                              premi=0, buste=0, roi=n * (val["busta"] + extra)))
        t = {k: sum(r[k] for r in righe) for k in ("costo", "premi", "buste", "roi")}
        n_draft, tutte = quick + premier + extra_ev, t["buste"] + buste + mitiche + buste_gemme
        ritorno = dict(buste=tutte, jolly_r=tutte * val["jolly_r"], jolly_m=tutte * val["jolly_m"], gemme=t["premi"], carte=n_draft * val["carte_draft"] + tutte * val["carte_busta"])
        # il bilancio del piano in gemme (Autore, 6 nov 2026: «in gemme + oro convertito in gemme quanto spendo vs quanto guadagno ... calcolato tra tutti gli asset ottenuti»): l'oro a 1.000 = 200, un draft
        # token al prezzo in gemme dell'ingresso che paga, il Mastery Pass per la quota del mese, col suo scatto. Il reddito di base non e' un guadagno del piano: entra comunque
        sp, q = self.scatto_pass(), PASS_ANNO / 12 if con_pass else 0.0
        c_pass, v_pass = sp["costo"] * q, (sp["gem"] + sp["oro"] * self.gpo + sp["bu"] * val["busta"]) * q
        spende, ottiene = t["costo"] + c_pass, t["roi"] + t["premi"] + v_pass
        return dict(righe=righe, costo=t["costo"], premi=t["premi"], buste=t["buste"], roi=t["roi"], saldo=ottiene - spende, spende=spende, ottiene=ottiene, c_pass=c_pass, v_pass=v_pass, oro_speso=oro_sp, gemme_spese=gem_sp,
                    oro_fine=cassa["oro"] + oro_mese - oro_sp, gem_fine=cassa["gem"] + gemme_mese + t["premi"] - gem_sp, ritorno=ritorno, token_usati=token_usati, token_mancati=token_mancati, con_pass=con_pass)

    def roadmap(self, e, dal=None, win=0.5, win_c=0.5, giorni=GIORNI_ROADMAP, cal=None, solo_set=None):
        """Il piano e (una simula) giorno per giorno, da «dal», con la cassa vera di ogni giorno (Autore, 6 nov 2026: «serve una profonda analisi di queste operazioni che considerino sempre il migliore
        guadagno e che considerino anche i calendari»). Si parte dal saldo di oggi, entra la media del trend senza il pass, e ogni voce si mette nel primo giorno in cui la sua finestra e' aperta e i soldi
        ci sono senza mandare sotto zero nessun giorno dopo: quel che e' gia' a calendario resta pagato. L'ordine conta: prima i draft in oro o token, da quello che chiude prima, poi gli eventi constructed,
        poi il Mastery Pass alla sua data, poi quel che si paga in gemme, in fondo le buste, che non hanno finestre. I premi in gemme arrivano il giorno dopo.
        -> dict(dal, al, giorni=[dict(data, oro, gemme, azioni=[dict(k, nome, set, dove, quanti, oro, gemme, token, chiude)])], fuori=[dict(k, nome, quanti, perche)], totale). Il primo giorno c'e' sempre, gli
        altri solo se c'e' qualcosa da fare. Tutto e' JSON: si salva cosi' com'e'."""
        dal = dal or datetime.date.today()
        cal = _calendario() if cal is None else cal
        giorno = lambda t: dal + datetime.timedelta(days=t)
        # solo_set: un set per tutte le voci, o {voce: set} (il piano lo da' in «solo»: ogni draft nelle finestre del set con cui e' contato, 9 nov 2026)
        solo = solo_set if isinstance(solo_set, dict) else {k: solo_set for k in ("quick", "premier", "buste", "mitiche", "costruiti")} if solo_set else {}
        rese, sa, b_ = self.rese(win, win_c), self.saldo(), self.base(False)
        al_giorno = 12 / 365.25
        oro = [float(sa["oro"]) + b_["oro"] * al_giorno * t for t in range(giorni)]
        gem = [float(sa["gem"]) + b_["gemme"] * al_giorno * t for t in range(giorni)]
        eventi, azioni, fuori, fatte = [0] * giorni, {}, collections.Counter(), 0

        def apre(k, t):
            a = _aperto(k, giorno(t), cal, solo.get(k))
            return None if a is None or (t == 0 and a["chiude"] == dal.isoformat()) else a       # un draft cominciato il giorno che chiude non si finisce

        def segna(u, t, ap):
            nonlocal fatte
            for x in range(t, giorni):
                oro[x] -= u["oro"]; gem[x] -= u["gemme"]
            premio = rese.get(u["k"], {}).get("gemme", 0)
            for x in range(t + 1, giorni):
                gem[x] += premio
            if u["k"] in ("quick", "premier", "costruiti"):
                eventi[t] += 1
            fatte += 1
            a = azioni.setdefault(t, {}).setdefault(u["k"], dict(k=u["k"], nome=NOMI_VOCE[u["k"]], set=ap["set"] or (solo.get(u["k"]) if k_busta(u["k"]) or u["k"] == "costruiti" else "") or "", chiude=ap["chiude"], dove=DOVE[u["k"]], quanti=0, oro=0, gemme=0, token=0))
            a["quanti"] += 1; a["oro"] += u["oro"]; a["gemme"] += u["gemme"]; a["token"] += u["token"]

        def metti(u):
            giorni_ok = [t for t in range(giorni) if apre(u["k"], t)]
            if not giorni_ok:
                fuori[(u["k"], "closed")] += 1
                return
            for t in giorni_ok:
                if u["k"] in ("quick", "premier", "costruiti") and eventi[t] >= EVENTI_AL_GIORNO:
                    continue
                if u["oro"] <= min(oro[t:]) + 1e-6 and u["gemme"] <= min(gem[t:]) + 1e-6:
                    segna(u, t, apre(u["k"], t))
                    return
            fuori[(u["k"], "money")] += 1

        unita = []
        for r in e["righe"]:
            k = r["nome"].split("_")[0]
            tok, resto = r["token"], r["volte"] - r["token"]
            unita += [dict(k=k, token=1 if i < tok else 0, oro=0 if i < tok else r["oro"] / resto, gemme=0 if i < tok else r["gemme"] / resto) for i in range(r["volte"])]
        def scadenza(u):
            ok = [t for t in range(giorni) if apre(u["k"], t)]
            return ok[-1] if ok else giorni
        draft = lambda u: u["k"] in ("quick", "premier")
        evento = lambda u: u["k"] in ("quick", "premier", "costruiti")
        for u in sorted((u for u in unita if draft(u) and not u["gemme"]), key=scadenza):
            metti(u)
        for u in (u for u in unita if u["k"] == "costruiti" and not u["gemme"]):
            metti(u)
        # il Mastery Pass il giorno che esce: 3.400 gemme, e lo scatto di oro e gemme entra subito
        sp = self.scatto_pass()
        if e.get("con_pass", True) and sp["costo"]:
            for s_ in cal.values():
                if not s_.get("premier") or not s_.get("inizio"):
                    continue
                t = (datetime.date.fromisoformat(s_["inizio"]) - dal).days
                if 0 <= t < giorni:
                    if sp["costo"] <= min(gem[t:]) + 1e-6:
                        segna(dict(k="passo", token=0, oro=0, gemme=sp["costo"]), t, dict(set="", chiude=""))
                        for x in range(t, giorni):
                            oro[x] += sp["oro"]; gem[x] += sp["gem"]
                    else:
                        fuori[("passo", "money")] += 1
        for u in sorted((u for u in unita if evento(u) and u["gemme"]), key=scadenza):
            metti(u)
        for u in sorted((u for u in unita if not evento(u)), key=lambda u: bool(u["gemme"])):
            metti(u)
        out = []
        for t in range(giorni):
            if t in azioni or not t:
                out.append(dict(data=giorno(t).isoformat(), oro=round(oro[t]), gemme=round(gem[t]), azioni=[dict(a, oro=round(a["oro"]), gemme=round(a["gemme"])) for a in azioni.get(t, {}).values()]))
        return dict(dal=dal.isoformat(), al=giorno(giorni - 1).isoformat(), giorni=out, totale=fatte, fuori=[dict(k=k, nome=NOMI_VOCE[k], quanti=n, perche=p) for (k, p), n in fuori.items()],
                    cassa_dal=dal.isoformat(), cassa=[[round(oro[t]), round(gem[t])] for t in range(giorni)], win=win, win_c=win_c)       # la cassa attesa giorno per giorno: serve a vedere l'income in piu' (surplus)

    def surplus(self, piano, oggi=None):
        """Quanto hai in piu' di quel che il piano si aspettava oggi (Autore, 9 nov 2026: «fa che la roadmap sappia adattarsi nel caso ci fosse income extra rispetto all'atteso»).
        L'atteso e' la cassa del piano di oggi piu' quel che costano le azioni fino a oggi non ancora fatte (sono soldi gia' promessi, non un extra). Un piano di prima, senza la cassa giorno
        per giorno, prende l'ultimo giorno scritto piu' l'entrata media dei giorni dopo. -> dict(oro, gemme, scatta) o None senza piano o senza saldo."""
        if not piano or not self.foto:
            return None
        oggi = oggi or datetime.date.today()
        sa, b_ = self.saldo(), self.base(False)
        al_giorno = 12 / 365.25
        t = (oggi - datetime.date.fromisoformat(piano.get("cassa_dal") or piano["dal"])).days
        if piano.get("cassa") and 0 <= t < len(piano["cassa"]):
            att_o, att_g = piano["cassa"][t]
        else:
            prima = [g for g in piano["giorni"] if g["data"] <= oggi.isoformat()]
            if not prima:
                return None
            g = prima[-1]
            dd = (oggi - datetime.date.fromisoformat(g["data"])).days
            att_o, att_g = g["oro"] + b_["oro"] * al_giorno * dd, g["gemme"] + b_["gemme"] * al_giorno * dd
        self.segna(piano, oggi)
        rese = self.rese(piano.get("win", 0.5), piano.get("win_c", 0.5))
        for g in piano["giorni"]:
            if g["data"] <= oggi.isoformat():
                for a in g["azioni"]:
                    n = a["quanti"] - a.get("fatte", 0)
                    resta = n / max(a["quanti"], 1)
                    att_o += a["oro"] * resta; att_g += a["gemme"] * resta
                    if g["data"] < oggi.isoformat():        # e il premio di un evento non giocato non e' arrivato: la cassa del piano lo contava dal giorno dopo
                        att_g -= rese.get(a["k"], {}).get("gemme", 0) * n
        so, sg = sa["oro"] - att_o, sa["gem"] - att_g
        scatta = (so >= EXTRA_ORO or sg >= EXTRA_GEMME) and so * self.gpo + sg > 0
        return dict(oro=round(so), gemme=round(sg), scatta=bool(scatta))

    def andamento(self, piano, oggi=None, ultima=None, attese=None):
        """La roadmap contro la cassa vera, giorno per giorno (Autore, 9 nov 2026: «un pulsante nella sezione ROI che apre in dettaglio i dati con un grafo e ci aiuta a capire se siamo sopra o sotto
        la road map nel periodo di gioco e in che %»). Per ogni giorno dal primo della cassa del piano all'ultima lettura del conto (non oltre oggi e la fine del piano):
        atteso = la cassa del piano di quel giorno, corretta come in surplus: le azioni fino a quel giorno non ancora fatte sono soldi promessi (si rimettono), il premio di un evento non giocato
        non e' arrivato (si toglie), e un'azione fatta prima della sua data ha gia' speso e gia' reso. vero = il conto a fine giorno. Il cambio dell'oro lo mette chi legge (scarto).
        ultima: l'ultimo giorno letto, per le prove (None: l'ultima foto del conto).
        attese: le risorse attese al mese dal piano (attese(e), o quelle salvate col piano): buste, carte e jolly rari e mitici ottenuti dal primo giorno, contro
        l'attesa al giorno per i giorni passati (Autore, 9 nov 2026: «coi flag che poi sono le stesse voci del menu a tendina della tabella trend controlliamo ogni voce quanto
        sta sopra o sotto all'andamento atteso»). Senza attese quei campi non ci sono.
        -> dict(dal, al, ultima, giorni=[dict(data, att_o, att_g, vero_o, vero_g, [att_b, vero_b, att_c, vero_c, att_j, vero_j])], piano=[[oro, gemme]] (la cassa del piano tutta, come creata), azioni=dict(fatta, ritardo, da fare)) o None."""
        if not piano or not self.foto or not piano.get("cassa"):
            return None
        oggi = oggi or datetime.date.today()
        dal = datetime.date.fromisoformat(piano.get("cassa_dal") or piano["dal"])
        ultima = ultima or self.al
        fine = min(ultima, oggi, dal + datetime.timedelta(days=len(piano["cassa"]) - 1))
        rese = self.rese(piano.get("win", 0.5), piano.get("win_c", 0.5))
        sp = self.scatto_pass()
        partenza = piano.get("partenza") or {}
        p0 = datetime.date.fromisoformat(piano["dal"])
        giorni = []
        for t in range(max(0, (fine - dal).days) + 1):
            d = dal + datetime.timedelta(days=t)
            att_o, att_g = piano["cassa"][t]
            ora = self.fatti(p0, d)
            resta = {k: ora[k] - partenza.get(k, 0) for k in ora}
            resta["mitiche"] = 0
            di = d.isoformat()
            for g in piano["giorni"]:
                for a in g["azioni"]:
                    k = "buste" if a["k"] == "mitiche" else a["k"]
                    n = max(0, min(a["quanti"], resta.get(k, 0)))
                    resta[k] = resta.get(k, 0) - n
                    q = max(a["quanti"], 1)
                    premio = rese.get(a["k"], {}).get("gemme", 0)
                    if g["data"] <= di:         # in calendario fino a oggi: quel che non hai fatto e' ancora in cassa, e il suo premio non e' arrivato
                        m = a["quanti"] - n
                        att_o += a["oro"] * m / q; att_g += a["gemme"] * m / q
                        if g["data"] < di:
                            att_g -= premio * m
                            if a["k"] == "passo" and m:
                                att_o -= sp["oro"]; att_g -= sp["gem"]
                    elif n:                     # fatta prima della sua data: ha speso e ha reso
                        att_o -= a["oro"] * n / q; att_g -= a["gemme"] * n / q - premio * n
            v = self.saldo(d) if d >= self.dal else self.saldo()
            g_ = dict(data=di, att_o=round(att_o), att_g=round(att_g), vero_o=v["oro"], vero_g=v["gem"])
            if attese:
                al_g = 12 / 365.25 * t        # i giorni passati dal primo: il primo giorno l'attesa e' zero
                s_ = self.tra(dal, d) if d >= self.dal else None
                g_.update(att_b=attese["buste"] * al_g, vero_b=s_["bu_ott"] if s_ else 0, att_c=attese["carte"] * al_g, vero_c=s_["carte"] if s_ else 0,
                          att_j=(attese["jolly_r"] + attese["jolly_m"]) * al_g, vero_j=(s_["jolly_r"] + s_["jolly_m"]) if s_ else 0)
            giorni.append(g_)
        self.segna(piano, oggi)
        stati, oi = collections.Counter(), oggi.isoformat()        # le azioni contate una per una, non per riga della roadmap
        for g in piano["giorni"]:
            for a in g["azioni"]:
                stati["fatta"] += a["fatte"]
                stati["ritardo" if g["data"] < oi else "da_fare"] += a["quanti"] - a["fatte"]
        return dict(dal=dal.isoformat(), al=(dal + datetime.timedelta(days=len(piano["cassa"]) - 1)).isoformat(), ultima=ultima.isoformat(), giorni=giorni, piano=piano["cassa"],
                    azioni=dict(stati))

    def adatta(self, piano, nuova, oggi=None, extra=None):
        """Il piano rifatto da oggi col surplus: i giorni fino a oggi restano con quel che hai fatto (le azioni non fatte cadono, i loro soldi sono nella cassa di oggi e il piano nuovo li
        rimette), da oggi i giorni della roadmap nuova. La cassa attesa diventa quella nuova; la storia degli adattamenti resta in «adattato». Cambia il piano e lo restituisce."""
        oggi = (oggi or datetime.date.today()).isoformat()
        self.segna(piano, datetime.date.fromisoformat(oggi))
        tenuti = []
        for g in piano["giorni"]:
            if g["data"] > oggi:
                continue
            az = [dict(a, quanti=a["fatte"], oro=round(a["oro"] * a["fatte"] / max(a["quanti"], 1)), gemme=round(a["gemme"] * a["fatte"] / max(a["quanti"], 1)),
                       token=round(a["token"] * a["fatte"] / max(a["quanti"], 1))) for a in g["azioni"] if a.get("fatte")]
            if az or g["data"] == piano["dal"]:
                tenuti.append(dict(g, azioni=az))
        nuovi = list(nuova["giorni"])
        if tenuti and nuovi and tenuti[-1]["data"] == nuovi[0]["data"]:        # oggi: prima quel che hai gia' fatto, poi il resto del giorno
            ultimo = tenuti.pop()
            nuovi[0] = dict(nuovi[0], azioni=ultimo["azioni"] + nuovi[0]["azioni"])
        piano["giorni"] = tenuti + nuovi
        piano["al"] = max(piano["al"], nuova["al"])
        piano["fuori"] = nuova["fuori"]
        piano["totale"] = sum(a["quanti"] for g in piano["giorni"] for a in g["azioni"])
        piano["cassa"], piano["cassa_dal"] = nuova["cassa"], nuova["cassa_dal"]
        piano.setdefault("adattato", []).append(dict(data=oggi, **{k: v for k, v in (extra or {}).items() if k in ("oro", "gemme")}))
        for g in piano["giorni"]:
            for a in g["azioni"]:
                a.pop("fatte", None); a.pop("stato", None)
        return piano

    def fatti(self, dal, al=None):
        """Quello che hai fatto davvero da «dal», dai log: {voce: volte}. Buste normali e mitiche non si distinguono: stanno tutte in «buste»."""
        s = self.tra(dal, al or self.al)
        return dict(quick=s["volte"]["Quick Draft"], premier=s["volte"]["Premier Draft"], costruiti=s["volte"]["Constructed event"], buste=s["bu_comp"], passo=len(self.pass_comprati(dal, al or self.al)))

    def segna(self, piano, oggi=None):
        """Mette su ogni azione della roadmap quante ne hai gia' fatte e lo stato: fatta, in ritardo, da fare. Le prime della lista si contano per prime. -> (fatte, totale)."""
        oggi = (oggi or datetime.date.today()).isoformat()
        ora = self.fatti(datetime.date.fromisoformat(piano["dal"]))
        resta = {k: ora[k] - (piano.get("partenza") or {}).get(k, 0) for k in ora}
        resta["mitiche"] = 0
        fatte = 0
        for g in piano["giorni"]:
            for a in g["azioni"]:
                k = "buste" if a["k"] == "mitiche" else a["k"]
                n = max(0, min(a["quanti"], resta[k]))
                resta[k] -= n; fatte += n
                a["fatte"] = n
                a["stato"] = "fatta" if n == a["quanti"] else "ritardo" if g["data"] < oggi else "da fare"
        return fatte, sum(a["quanti"] for g in piano["giorni"] for a in g["azioni"])

    def saldo(self, al=None):
        """Il conto alla fine del giorno «al» (None: adesso): oro, gemme, jolly per rarita', buste non aperte, vault in %."""
        x = self.foto[0]
        for f in self.foto:
            if al is not None and f["t"][:10] > al.isoformat():
                break
            x = f
        return dict(oro=x["oro"], gem=x["gem"], jolly=x["wc"], buste=sum(x["bu"].values()), vault=x["va"] / 10, token=x.get("tok", 0))


def scarto_voce(g, voce, gpo=GEMME_PER_ORO):
    """Un giorno di andamento per una voce del Trend: (vero, atteso, % sopra o sotto), None se l'atteso e' zero (il primo giorno delle risorse che si accumulano).
    voce: Oro, Gemme, Buste, Carte, Jolly, o ROI: il valore in gemme di cassa e buste ottenute (oro al cambio gpo, una busta al suo prezzo; grado C)."""
    if voce == "ROI":
        vero = g["vero_o"] * gpo + g["vero_g"] + g.get("vero_b", 0) * PREZZI_BUSTE["buste"]["gemme"]
        att = g["att_o"] * gpo + g["att_g"] + g.get("att_b", 0) * PREZZI_BUSTE["buste"]["gemme"]
        return vero, att, 100.0 * (vero - att) / max(abs(att), 1.0)
    k = {"Oro": "o", "Gemme": "g", "Buste": "b", "Carte": "c", "Jolly": "j"}[voce]
    if f"att_{k}" not in g:
        return None
    vero, att = g[f"vero_{k}"], g[f"att_{k}"]
    if abs(att) < 0.5:
        return vero, att, None
    return vero, att, 100.0 * (vero - att) / abs(att)


def scarto(g, gpo):
    """Un giorno di andamento in gemme, col cambio gpo (gemme per un oro): (vero, atteso, % sopra o sotto la roadmap). Il valore e' oro per il cambio piu' gemme; la % e' sull'atteso."""
    vero, att = g["vero_o"] * gpo + g["vero_g"], g["att_o"] * gpo + g["att_g"]
    return vero, att, 100.0 * (vero - att) / max(abs(att), 1.0)


def win_stimato(win, partite, prior=PRIOR_WIN, k=PARTITE_PRIOR):
    """Il win rate da usare nei conti: il tuo, spostato verso la media quando le partite sono poche. Senza partite e' la media."""
    if win is None or not partite:
        return prior
    return (win * partite + prior * k) / (partite + k)


def pesi_obiettivo(obiettivo):
    """Un obiettivo, una lista di obiettivi o {obiettivo: peso} -> {obiettivo: peso}, col peso piu' alto a 1."""
    p = {obiettivo: 1.0} if isinstance(obiettivo, str) else dict(obiettivo) if isinstance(obiettivo, dict) else {g: 1.0 for g in obiettivo}
    alto = max(p.values())
    return {g: x / alto for g, x in p.items()}


def copie_collezione():
    """Le copie in collezione nell'ultimo scarico, o None."""
    try:
        with open(_ACC.percorso("collezione.json", autore=os.path.join(percorsi.ROOT, "Collezione", "collezione.json")), encoding="utf-8") as f:
            return sum(c["quantity"] for c in json.load(f)["cards"])
    except (OSError, ValueError, KeyError):
        return None


def k_busta(k):
    return k in ("buste", "mitiche")


def _calendario():
    try:
        with open(os.path.join(percorsi.ROOT, "Regole", "calendario_set.json"), encoding="utf-8") as f:
            return json.load(f)["set"]
    except (OSError, ValueError, KeyError):
        return {}


def _aperto(k, d, cal, solo_set=None):
    """Si puo' fare la voce k il giorno d? -> dict(set, chiude), con set e chiusura solo per i draft; None se no. solo_set: il goal vuole le carte di quel set, un draft di un altro non serve."""
    giorno = d.isoformat()
    if k not in ("quick", "premier"):
        # le buste di un set si comprano da quando esce
        # le buste di un set si comprano da quando esce su Arena, e da quel giorno gli eventi constructed danno buste sue (9 nov 2026)
        return None if solo_set and k in ("buste", "mitiche", "costruiti") and (cal.get(solo_set) or {}).get("inizio", "") > giorno else dict(set="", chiude="")
    for s_, v in cal.items():
        if solo_set and s_ != solo_set:
            continue
        for a, b in v.get(k) or []:
            if a <= giorno <= b:
                return dict(set=s_, chiude=b)
    return None


def primo_set(k, oggi, cal, giorni=GIORNI_ROADMAP):
    """Il set del primo draft k aperto nei prossimi giorni, o None."""
    for t in range(giorni):
        x = _aperto(k, oggi + datetime.timedelta(days=t), cal)
        if x:
            return x["set"]
    return None


def capienza(k, oggi, cal, solo_set=None, giorni=GIORNI_ROADMAP):
    """Quanti draft k ci stanno nei prossimi giorni: i giorni di finestra aperta, per EVENTI_AL_GIORNO. Il giorno in cui chiude non conta se e' oggi: un draft cominciato oggi non si finisce."""
    n = 0
    for t in range(giorni):
        d = oggi + datetime.timedelta(days=t)
        x = _aperto(k, d, cal, solo_set)
        if x and not (t == 0 and x["chiude"] == oggi.isoformat()):
            n += 1
    return n * EVENTI_AL_GIORNO


def leggi_piano(file=None):
    """Il piano del Farmer lanciato con Create, o None."""
    try:
        with open(file or PIANO, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def salva_piano(p, file=None):
    f = file or PIANO
    tmp = f"{f}.{os.getpid()}.tmp"
    with open(tmp, "w", encoding="utf-8") as x:
        json.dump(p, x, ensure_ascii=False)
    os.replace(tmp, f)


def togli_piano(file=None):
    try:
        os.remove(file or PIANO)
    except OSError:
        pass


def aperti(oggi=None):
    """I draft aperti oggi su Arena, dal calendario: {"quick": set o None, "premier": set o None}."""
    oggi = (oggi or datetime.date.today()).isoformat()
    out = dict(quick=None, premier=None)
    try:
        with open(os.path.join(percorsi.ROOT, "Regole", "calendario_set.json"), encoding="utf-8") as f:
            cal = json.load(f)["set"]
    except (OSError, ValueError, KeyError):
        return out
    for s_, v in cal.items():
        for k in out:
            if any(a <= oggi <= b for a, b in v.get(k) or []):
                out[k] = s_
    return out


def date_uscita():
    """{codice: data di uscita}, da Regole/Set_Legali.md. {} se il file non si legge."""
    try:
        with open(os.path.join(percorsi.ROOT, "Regole", "Set_Legali.md"), encoding="utf-8") as f:
            return {c: d for c, d in re.findall(r"^\| [^|]+? \| ([A-Z0-9]+) \| (\d{4}-\d{2}-\d{2}) \|", f.read(), re.M)}
    except OSError:
        return {}


def nomi_set():
    """{codice: nome}, da Regole/Set_Legali.md."""
    try:
        with open(os.path.join(percorsi.ROOT, "Regole", "Set_Legali.md"), encoding="utf-8") as f:
            return {c: n for n, c in re.findall(r"^\| ([^|]+?) \| ([A-Z0-9]+) \| \d{4}-\d{2}-\d{2} \|", f.read(), re.M)}
    except OSError:
        return {}


def ordina_set(sets):
    """I codici per data di uscita, dal piu' nuovo (Autore, 5 nov 2026: «ordina i set nelle tendine in ordine di uscita»); quelli senza data in fondo."""
    date = date_uscita()
    return sorted(sets, key=lambda c: date.get(c, ""), reverse=True)


def set_principali(oggi=None):
    """I set principali gia' usciti, dal piu' nuovo: [(codice, nome)], da Regole/Set_Legali.md (almeno 100 carte nel pool)."""
    oggi = (oggi or datetime.date.today()).isoformat()
    try:
        with open(os.path.join(percorsi.ROOT, "Regole", "Set_Legali.md"), encoding="utf-8") as f:
            righe = re.findall(r"^\| ([^|]+?) \| ([A-Z0-9]+) \| (\d{4}-\d{2}-\d{2}) \| (\d+) \|", f.read(), re.M)
    except OSError:
        return []
    return [(c, n) for n, c, d, k in sorted(righe, key=lambda r: r[2], reverse=True) if int(k) >= 100 and d <= oggi]


def set_costruiti(oggi=None, cal=None):
    """Il set delle buste premio degli eventi constructed nel piano dei prossimi 30 giorni: il set piu' nuovo su Arena, letto dal calendario (Autore, 9 nov 2026: «lui calcolera' i
    constructed da quando Trek sara' uscito, ovvio che oggi c'e' FRA ma deve avere a disposizione nel calcolo del piano la lettura del calendario»). Conta il set che esce su Arena
    («inizio» di Regole/calendario_set.json) entro meta' piano: per la maggior parte dei giorni i premi saranno suoi; la roadmap mette i constructed di quel set solo da quel giorno.
    Senza calendario, il set uscito piu' nuovo (set_principali)."""
    oggi = oggi or datetime.date.today()
    cal = _calendario() if cal is None else cal
    limite = (oggi + datetime.timedelta(days=GIORNI_ROADMAP // 2)).isoformat()
    ora = (set_principali(oggi) or [("", "")])[0][0]
    uscite = date_uscita()
    # solo i set nuovi: nel calendario c'e' anche chi torna (DFT il 19 ott 2026), e il suo «inizio» e' l'evento, non l'uscita
    nuovi = [(v["inizio"], c) for c, v in cal.items() if v.get("inizio") and v["inizio"] <= limite and uscite.get(c, "") > uscite.get(ora, "")]
    return max(nuovi)[1] if nuovi else ora


def set_farmer(oggi=None):
    """I set del goal «carte di un set»: quelli usciti (set_principali) piu' quelli col draft su Arena aperto o in arrivo nel calendario, anche prima dell'uscita e prima che il pool
    dello Standard li abbia (Autore, 9 nov 2026: «al farmer devi aggiungere star trek»: TRK esce il 13 nov, il Premier apre il 10, nel pool ne aveva 10 carte). Dal piu' nuovo."""
    oggi_ = (oggi or datetime.date.today()).isoformat()
    out = set_principali(oggi)
    try:
        with open(os.path.join(percorsi.ROOT, "Regole", "calendario_set.json"), encoding="utf-8") as f:
            cal = json.load(f)["set"]
        with open(os.path.join(percorsi.ROOT, "Regole", "Set_Legali.md"), encoding="utf-8") as f:
            uscite = {c: d for _n, c, d in re.findall(r"^\| ([^|]+?) \| ([A-Z0-9]+) \| (\d{4}-\d{2}-\d{2}) \|", f.read(), re.M)}
    except (OSError, ValueError, KeyError):
        return out
    gia = {c for c, _n in out}
    for c, v in cal.items():
        finestre = [f for k in ("quick", "premier", "trad", "sealed") for f in v.get(k) or []]
        if c not in gia and any(b_ >= oggi_ for _a, b_ in finestre):
            out.append((c, v.get("nome") or c))
    return sorted(out, key=lambda x: uscite.get(x[0], "0000"), reverse=True)


def set_mancanti(set_):
    """Quanto hai di un set a 4 copie: dict(fatte, tutte, rare_mancanti). Le carte di quel set nel pool dello Standard; un set che il pool non ha ancora (sotto 100 carte: TRK prima
    dell'uscita, 9 nov 2026) dal database delle carte di Arena, terre base escluse."""
    try:
        with open(os.path.join(percorsi.ROOT, "Regole", "standard_carte.json"), encoding="utf-8") as f:
            carte = {c["name"]: c["rarity"] for c in json.load(f) if c.get("set") == set_}
        import collezione_viva as CV       # con le carte dei log dopo lo scarico di Untapped (8 nov 2026)
        mie = CV.copie_nomi()
    except (OSError, ValueError):
        return None
    if len(carte) < 100:
        try:
            import collezione_carte as CC
            nomi = dict(M="mythic", R="rare", U="uncommon", C="common")
            arena = {c["nome"]: nomi[c["r"]] for c in (CC.carica() or {}).get("carte") or [] if set_ in c["sets"] and c["r"] in nomi}
            if len(arena) > len(carte):
                carte = arena
        except Exception:
            pass
    if not carte:
        return None
    copie = lambda n: mie.get(n) or mie.get(n.split(" // ")[0], 0)          # la collezione ha spesso la sola faccia davanti
    fatte = sum(min(4, copie(n)) for n in carte)
    return dict(fatte=fatte, tutte=4 * len(carte), rare_mancanti=sum(max(0, 4 - copie(n)) for n, r in carte.items() if r in ("rare", "mythic")))


def carica():
    """La Risorse dai log. La mappa degli eventi viene da premi_eventi (CourseId -> nome)."""
    foto, pool = raccogli()
    eventi = {v["id"]: v["evento"] for v in PE.raccogli() if v["fonte"] != "EventGrantCardPool"}
    return Risorse(foto, pool, eventi)


def bilancio(R):
    """Il bilancio contro il saldo vero: quel che entra meno quel che esce deve dare la differenza fra la prima e l'ultima foto."""
    s = somma(R.voci); a, b = R.foto[0], R.foto[-1]
    return dict(oro=(a["oro"] + s["oro_piu"] - s["oro_meno"], b["oro"]), gem=(a["gem"] + s["gem_piu"] - s["gem_meno"], b["gem"]),
                buste=(sum(a["bu"].values()) + s["bu_ott"] - s["bu_ap"], sum(b["bu"].values())),
                **{f"jolly_{RARITA[r]}": (a["wc"][r] + s["jolly_piu"][r] - s["jolly_meno"][r], b["wc"][r]) for r in range(4)})


def _f(t, oro, gem, tr=0, wc=(0, 0, 0, 0), bu=None, mov=()):
    return dict(t=t, s=0, oro=oro, gem=gem, tr=tr, wc=list(wc), bu=bu or {}, va=0, mov=list(mov), tok=0)


def _m(f, id_="", oro=0, gem=0, bu=0, c=0):
    return dict(f=f, id=id_, oro=oro, gem=gem, bu=bu, c=c)


def prova_conti():
    """Due account di Arena sullo stesso PC (10 nov 2026, Magic 12): l'oro farmato di ognuno resta suo, All accounts somma, e mischiare le foto (il codice di prima)
    inventa spese e oro farmato. -> lista di (nome, ok)."""
    import tempfile
    d = tempfile.mkdtemp()
    acc = lambda i: '{ "authenticateResponse": { "clientId": "%s", "sessionId": "s", "screenName":"X" } }\n' % i
    inv = lambda h, oro: '[UnityCrossThreadLogger]10/11/2026 %02d:00:00 {"InventoryInfo":{"SeqId":%d,"Gold":%d,"Gems":0,"WildCardCommons":0,"WildCardUnCommons":0,"WildCardRares":0,"WildCardMythics":0}}\n' % (h, h, oro)
    A, B = "AAAA1111BBBB2222CCCC3333DD", "ZZZZ1111BBBB2222CCCC3333DD"
    open(os.path.join(d, "2026-11-10_0000_Player.log"), "w", encoding="utf-8").write(
        acc(A) + inv(1, 1000) + inv(2, 1500) + acc(B) + inv(3, 200) + inv(4, 300) + acc(A) + inv(5, 1500) + inv(6, 1700))
    vero = (PE.LOGDIR, list(PE.VIVI), CACHE, _ACC.PUBBLICA)
    globals()["CACHE"] = os.path.join(d, "c.json")
    PE.LOGDIR, PE.VIVI[:], _ACC.PUBBLICA = d, [], True
    try:
        farm = lambda conto: somma(movimenti(raccogli(False, conto)[0], [], {}))
        fa, fb, ft = farm(A), farm(B), farm(_ACC.TUTTI)
        tutte = sorted(leggi_file(os.path.join(d, "2026-11-10_0000_Player.log"))[0], key=lambda x: (x["t"], x["s"]))
        mischiate = somma(movimenti(tutte, [], {}))
        saldo_t = raccogli(False, _ACC.TUTTI)[0][-1]["oro"]
    finally:
        PE.LOGDIR, PE.VIVI[:], _, _ACC.PUBBLICA = vero[0], vero[1], None, vero[3]
        globals()["CACHE"] = vero[2]
    return [("due account: l'oro farmato di A resta suo", fa["oro_piu"] == 700 and not fa["spese"]),
            ("e quello di B suo", fb["oro_piu"] == 100 and not fb["spese"]),
            ("All accounts somma, senza spese inventate, col saldo dei due", ft["oro_piu"] == 800 and not ft["spese"] and saldo_t == 2000),
            ("negativa: le foto mischiate (il codice di prima) inventano spese", mischiate["oro_piu"] != 800 or bool(mischiate["spese"]))]


def casi():
    """I casi di calcolo, presi dai passi veri di ott 2026. -> lista di (nome, ok)."""
    ev = {"q1": "QuickDraft_FRA_20261008", "c1": "Constructed_Event_2026", "q2": "QuickDraft_FRA_20261008"}
    T = "2026-10-%02d 12:00:00"
    out = []
    # farmato: oro che sale senza movimenti
    s = somma(movimenti([_f(T % 1, 100, 0), _f(T % 1, 850, 0)], [], ev))
    out.append(("oro farmato", s["oro_piu"] == 750 and not s["spese"]))
    # l'ingresso col nome
    s = somma(movimenti([_f(T % 1, 5000, 0), _f(T % 1, 0, 0, mov=[_m("EventPayEntry", "q1", oro=-5000)])], [], ev))
    out.append(("ingresso Quick Draft", s["spese"] == {"Quick Draft": 5000} and s["volte"]["Quick Draft"] == 1 and s["oro_piu"] == 0))
    # 31 ott: 8 buste aperte, -7.300 oro: 8.000 in buste, 700 farmati
    s = somma(movimenti([_f(T % 1, 10650, 0, tr=27), _f(T % 1, 3350, 0, tr=5, wc=(2, 2, 2, 0))], [], ev))
    out.append(("8 buste nel negozio", s["spese"] == {BUSTE: 8000} and s["oro_piu"] == 700 and s["bu_comp"] == 8 and s["bu_ap"] == 8 and s["bu_ott"] == 8))
    out.append(("carte delle buste", s["c_buste"] == 8 * 8 - 6))
    # il ROI di quel passo: 8 buste a 144,5 e 2 jolly rari a 500; comuni e non comuni a zero. L'incasso sono i 700 oro, 140 gemme
    out.append(("ROI", s["roi"] == 8 * 144.5 + 2 * 500 and s["incasso"] == 140))
    # 18 ott: il Mastery Pass, 3.400 gemme, col premio del pass di +4.000 oro e +1.200 gemme nello stesso passo, 3 buste comprate e 600 oro senza nome
    s = somma(movimenti([_f(T % 18, 3650, 4405, tr=21, bu={"FRA": 1}), _f(T % 18, 4050, 2205, tr=25, bu={"FRA": 5, "ECL": 5, "SOS": 5}, mov=[
        _m("CampaignGraphPurchaseNode", "BattlePass_FRA.RewardTierUpgrade"), _m("CampaignGraphTieredRewardNode", "", 4000, 1200, 15, 6)])], [], ev))
    out.append(("Mastery Pass", s["spese_gem"] == {PASS: 3400} and s["gem_piu"] == 1200 and s["spese"] == {BUSTE: 3000, ALTRO: 600} and s["oro_piu"] == 4000 and s["c_premi"] == 6))
    # 8 ott: il premio senza ingresso: il resto di -4.700 e' l'ingresso da 5.000, non 1 busta e 3.700 di altro
    ff = [_f(T % 7, 10000, 0, tr=26), _f(T % 8, 5300, 0, tr=27),
          _f("2026-10-08 13:00:00", 5300, 50, tr=27, mov=[_m("EventReward", "q1", gem=50)]),
          _f("2026-10-09 12:00:00", 300, 50, tr=27, mov=[_m("EventPayEntry", "q2", oro=-5000)])]
    s = somma(movimenti(ff, [], ev))
    out.append(("ingresso perso", s["spese"] == {"Quick Draft": 10000} and s["oro_piu"] == 300 and s["volte"]["Quick Draft"] == 2 and not s["bu_comp"]))
    # un campo a zero manca dal JSON: gemme a zero non rompono niente
    x = _foto({"SeqId": 3, "Gold": 500, "WildCardCommons": 1}, "2026-11-04 12:00:00")
    out.append(("gemme a zero", x["gem"] == 0 and x["oro"] == 500))
    # le buste in gemme e la mitica a 1.300 oro
    s = somma(movimenti([_f(T % 1, 0, 1000), _f(T % 2, 0, 600, tr=2)], [], ev))
    out.append(("buste comprate in gemme", s["spese_gem"] == {BUSTE: 400} and s["bu_comp"] == 2 and not s["spese"]))
    s = somma(movimenti([_f(T % 1, 2000, 0), _f(T % 2, 700, 0, tr=1)], [], ev))
    out.append(("busta mitica in oro", s["spese"] == {BUSTE: 1300} and s["bu_comp"] == 1 and s["oro_piu"] == 0))
    # un draft pagato col token: niente ingresso finto cercato nell'oro
    ff = [_f(T % 7, 5000, 0, tr=26), _f(T % 8, 1000, 0, tr=29), dict(_f("2026-10-08 13:00:00", 1000, 0, tr=29), tok=0, s=1), _f("2026-10-08 13:30:00", 1000, 50, tr=29, mov=[_m("EventReward", "q9", gem=50)])]
    ff[0]["tok"] = ff[1]["tok"] = 2; ff[2]["tok"] = 1; ff[3]["tok"] = 1
    s = somma(movimenti(ff, [], dict(ev, q9="QuickDraft_FRA_20261008")))
    out.append(("il token non fa nascere un ingresso", s["volte"]["Quick Draft"] == 0 and s["spese"].get("Quick Draft", 0) == 0))
    # una spesa piccola con una busta in piu' non e' un acquisto da 1.000 oro
    s = somma(movimenti([_f(T % 1, 1000, 0, bu={"FRA": 0}), _f(T % 2, 900, 0, bu={"FRA": 1})], [], ev))
    out.append(("spesa piccola, niente buste comprate", s["spese"] == {ALTRO: 100} and not s["bu_comp"] and s["oro_piu"] == 0))
    # il resto che non si riconosce
    s = somma(movimenti([_f(T % 1, 5000, 100), _f(T % 2, 4000, 50)], [], ev))
    out.append(("spesa senza nome", s["spese"] == {ALTRO: 1000} and s["spese_gem"] == {ALTRO: 50}))
    # la pista gira a 30, e quando vale 0 il campo manca
    s = somma(movimenti([_f(T % 1, 0, 0, tr=29), _f(T % 2, 0, 0, tr=0), _f(T % 3, 0, 0, tr=1)], [], ev))
    out.append(("pista a 30", s["bu_ap"] == 2 and s["bu_ott"] == 2))
    # jolly ottenuti e usati
    s = somma(movimenti([_f(T % 1, 0, 0, wc=(41, 48, 36, 18)), _f(T % 2, 0, 0, wc=(19, 20, 36, 19))], [], ev))
    out.append(("jolly", s["jolly_piu"] == [0, 0, 0, 1] and s["jolly_meno"] == [22, 28, 0, 0]))
    ff = [_f("2026-09-22 12:00:00", 0, 0), _f("2026-10-02 12:00:00", 3000, 0), _f("2026-11-02 12:00:00", 3200, 0)]
    R = Risorse(ff, [], ev)
    out.append(("in cassa a fine periodo", R.saldo(datetime.date(2026, 9, 30))["oro"] == 0 and R.saldo(datetime.date(2026, 10, 31))["oro"] == 3000 and R.saldo()["oro"] == 3200))
    # il calcolatore: un Quick Draft a oro costa 1.000 gemme di valore, a gemme 750; premi e buste vengono dalle tabelle, a win rate fisso
    ff = [_f(T % 1, 10000, 2000, tr=0), _f(T % 2, 10000, 2000, tr=1, wc=(0, 0, 1, 0))]
    R = Risorse(ff, [[T % 1, "e", []]], ev)
    a, b = R.simula(quick=2, win=0.5, oro_mese=3000), R.simula(quick=2, paga="gemme", win=0.5)
    gem, bu = ED.resa(0.5)[:2]
    val = R.valori()
    out.append(("calcolatore: valori", val["draft"] == 0 and val["busta"] == PREZZI_BUSTE["buste"]["gemme"]))
    out.append(("calcolatore: oro", a["costo"] == 2000 and abs(a["premi"] - 2 * gem) < 1e-9 and a["oro_fine"] == 3000 and a["gem_fine"] == 2000 + a["premi"]))
    out.append(("calcolatore: gemme", b["costo"] == 1500 and b["oro_fine"] == 10000 and abs(b["gem_fine"] - (2000 + b["premi"] - 1500)) < 1e-9))
    c = R.simula(buste=3, win=0.5)
    out.append(("calcolatore: buste", c["costo"] == 600 and abs(c["roi"] - 3 * val["busta"]) < 1e-9 and abs(c["saldo"] - (c["roi"] - 600)) < 1e-9 and c["oro_fine"] == 7000))
    out.append(("calcolatore: ROI dei draft", abs(a["roi"] - 2 * bu * val["busta"]) < 1e-9))
    # ogni voce si paga a modo suo; la busta mitica costa 1.300 oro o 260 gemme e vale una mitica invece della rara; i token non bastano: il resto in oro
    d_ = R.simula(quick=1, buste=1, mitiche=1, paga=dict(quick="gemme", buste="oro", mitiche="gemme"), win=0.5)
    out.append(("calcolatore: valute diverse", d_["costo"] == 750 + 200 + 260 and d_["oro_fine"] == 10000 - 1000 and abs(d_["gem_fine"] - (2000 + d_["premi"] - 750 - 260)) < 1e-9))
    out.append(("calcolatore: busta mitica", abs(d_["righe"][4]["roi"] - (d_["righe"][3]["roi"] + VALORE_CARTA["M"] - VALORE_BUSTA)) < 1e-9))
    R.foto[-1]["tok"] = 2
    e_ = R.simula(premier=3, paga="token", win=0.5)
    misto = R.simula(3, 1, 4, 1, dict(quick="oro", premier="token", buste="oro", mitiche="gemme"), buste_gemme=2, gemme_voci=dict(quick=1))
    out.append(("il token non paga un Quick", R.simula(quick=1, paga="token", win=0.5)["token_usati"] == 0))
    out.append(("le voci sommano la spesa vera", sum(x["oro"] for x in misto["righe"]) == misto["oro_speso"] and sum(x["gemme"] for x in misto["righe"]) == misto["gemme_spese"]
                and sum(x["token"] for x in misto["righe"]) == misto["token_usati"]))
    out.append(("calcolatore: token", e_["token_usati"] == 2 and e_["token_mancati"] == 1 and e_["costo"] <= 2000 + 2 * INGRESSI["premier"]["gemme"] and e_["costo"] > 2000 and e_["oro_speso"] == 10000))
    f_ = R.simula(quick=1, buste=2, win=0.5)
    out.append(("calcolatore: ritorno per risorsa", abs(f_["ritorno"]["buste"] - (bu + 2)) < 1e-9 and abs(f_["ritorno"]["jolly_r"] - (bu + 2) * val["jolly_r"]) < 1e-9 and abs(f_["ritorno"]["gemme"] - gem) < 1e-9))
    # le risorse attese: la base del trend non conta le buste comprate ne' i premi; col piano che riproduce il trend tornano i conti veri
    ff = [_f(T % 1, 0, 0), _f(T % 2, 5000, 0, tr=2, bu={"FRA": 0}), _f(T % 3, 5000, 300, tr=2, bu={"FRA": 1}, mov=[_m("EventReward", "q1", gem=300, bu=1)]),
          _f(T % 31, 0, 300, tr=4, bu={"FRA": 0})]
    R = Risorse(ff, [], ev)
    b_ = R.base()
    gi = R.tra(R.dal, R.al)["giorni"]; me = 365.25 / 12 / gi
    out.append(("base del trend", abs(b_["gemme"]) < 1e-9 and abs(b_["oro"] - R.tra(R.dal, R.al)["oro_piu"] * me) < 1e-9 and b_["buste"] >= 0))
    e_ = R.simula(buste=0, win=0.5); att = R.attese(e_)
    out.append(("attese senza piano = base", abs(att["buste"] - b_["buste"]) < 1e-9 and abs(att["gemme"] - b_["gemme"]) < 1e-9 and abs(att["oro"] - b_["oro"]) < 1e-9))
    f_ = R.simula(buste=2, buste_gemme=3, win=0.5); att = R.attese(f_)
    out.append(("attese col piano", abs(att["buste"] - (b_["buste"] + 5)) < 1e-9 and f_["righe"][-1]["nome"] == "buste_gemme" and f_["righe"][-1]["costo"] == 600 and f_["gem_fine"] == 300 - 600))
    # il piano: 30.000 oro in 30 giorni e 10 buste aperte, con 2 jolly rari e 1 mitico; niente pool
    ff = [_f("2026-10-01 12:00:00", 0, 0), _f("2026-10-30 12:00:00", 30000, 0, tr=10, wc=(0, 0, 2, 1))]
    R = Risorse(ff, [], ev)
    m = 365.25 / 12 / 30
    tutti, niente = dict(quick="FRA", premier="FRA"), dict(quick=None, premier=None)
    a = R.piano("jolly", 0.4, aperti_ora=tutti)
    oro_a = 30000 * m
    out.append(("piano jolly: l'oro in buste", a["voci"]["buste"] == int(oro_a // 1000) and a["voci"]["quick"] == 0 and a["esito"]["oro_resto"] < 1000
                and abs(a["esito"]["jolly_r"] - a["esito"]["buste"] * 0.2) < 1e-9))
    b = R.piano("gemme", 0.75, aperti_ora=tutti, win_c=0.75)       # qui i pool non valgono niente: gli eventi rendono solo se vinci tanto
    out.append(("a win rate basso nessun evento in perdita", sum(R.piano("gemme", 0.3, aperti_ora=tutti, win_c=0.3)["voci"][k] for k in ("quick", "premier", "costruiti")) == 0))
    out.append(("piano gemme: l'oro diventa eventi", b["esito"]["gemme"] > 0 and b["voci"]["buste_gemme"] == 0 and b["esito"]["oro_resto"] < 1000 and b["voci"]["costruiti"] + b["voci"]["quick"] + b["voci"]["premier"] > 0))
    g_ = R.piano("gemme", 0.75, aperti_ora=niente, win_c=0.75)
    out.append(("gemme senza draft aperti: restano gli eventi constructed", g_["voci"]["costruiti"] > 0 and g_["voci"]["quick"] == 0))
    c = R.piano("carte", 0.4, set_="HOB", aperti_ora=tutti)
    out.append(("piano carte: un set vecchio si fa a buste", c["voci"]["buste"] > 0 and abs(c["esito"]["meta"] - (c["voci"]["buste"] + c["voci"]["buste_gemme"]) * R.valori()["carte_busta"]) < 1e-9))
    bp = R.piano("buste", 0.4, aperti_ora=tutti)
    out.append(("piano buste", bp["esito"]["meta"] == bp["esito"]["buste"] and bp["esito"]["buste"] >= int(oro_a // 1000)))
    # il win rate cambia la rotta: al 90% un ingresso si ripaga e le gemme diventano ingressi in gemme
    alto = R.piano("gemme", 0.9, aperti_ora=tutti, win_c=0.9); basso = R.piano("gemme", 0.3, aperti_ora=tutti, win_c=0.3)
    out.append(("il win rate cambia la rotta", basso["esito"]["gemme"] < alto["esito"]["gemme"] and bool(alto["gemme_voci"])))
    mx, a75 = R.piano(["jolly", "gemme"], 0.75, aperti_ora=tutti, win_c=0.75), R.piano("jolly", 0.75, aperti_ora=tutti, win_c=0.75)
    out.append(("goal misti: piu' gemme del solo jolly, piu' jolly del solo gemme", mx["esito"]["gemme"] >= a75["esito"]["gemme"] and mx["esito"]["jolly_r"] >= b["esito"]["jolly_r"]))      # dal 9 nov 2026 le gemme non comprano buste: al 75% il solo jolly e il mix possono coincidere
    out.append(("goal misti: nessun obiettivo resta indietro", min(mx["esito"]["quote"].values()) > 0.3))
    # il mix conta il guadagno: chiudere sotto il punto zero non e' una quota positiva, e il piano del mix guadagna gemme davvero
    gz = mx["esito"]["gemme"] - R.base(False)["gemme"]
    top_gz = max(R._piano(["jolly", "gemme"], 0.75, None, tutti, 0.75, c_, solo_top=True)["gemme"] for c_ in (True, False))
    out.append(("mix: le gemme contano dal punto zero", gz > 0 and abs(mx["esito"]["quote"]["gemme"] - gz / top_gz) < 1e-9))
    out.append(("mix: il pass si decide sui massimi comuni", mx["pass"] in (True, False) and mx["esito"]["meta"] == min(mx["esito"]["quote"].values())))
    out.append(("un goal solo in lista e' lo stesso goal", R.piano(["jolly"], 0.4, aperti_ora=tutti)["voci"] == a["voci"]))
    # i pesi degli slider (8 nov 2026): l'obiettivo col peso alto prende di piu', e un peso a uno solo e' il goal da solo
    p82, p28 = R.piano({"gemme": 80, "jolly": 20}, 0.75, aperti_ora=tutti, win_c=0.75), R.piano({"gemme": 20, "jolly": 80}, 0.75, aperti_ora=tutti, win_c=0.75)
    out.append(("pesi: 80% gemme chiude piu' gemme di 80% jolly, e meno jolly", p82["esito"]["gemme"] >= p28["esito"]["gemme"] and p82["esito"]["jolly_r"] <= p28["esito"]["jolly_r"] and p82["voci"] != p28["voci"]))
    out.append(("pesi: {jolly: 100} e' il goal jolly", R.piano({"jolly": 100}, 0.4, aperti_ora=tutti)["voci"] == a["voci"]))
    # la spunta: l'oro non compra buste; le buste del goal vengono dalle gemme, l'oro che avanza resta oro
    nb = R.piano("buste", 0.4, aperti_ora=tutti, oro_buste=False); nj = R.piano("jolly", 0.4, aperti_ora=tutti, oro_buste=False)
    out.append(("spunta: niente buste in oro, l'oro resta", nb["voci"]["buste"] == 0 and nj["voci"]["buste"] == 0 and nj["esito"]["oro_resto"] >= 1000 and bp["voci"]["buste"] > 0))
    sj = R.piano("jolly", 0.4, aperti_ora=tutti)
    out.append(("le gemme non comprano mai buste, nemmeno con la spunta accesa (9 nov 2026)", all(x["voci"]["buste_gemme"] == 0 for x in (nb, nj, sj, bp)) and sj["voci"]["buste"] > 0))
    # il win rate verso la media (8 nov 2026): senza partite la media, con 50 partite a meta' strada, con tante quasi il tuo
    out.append(("win stimato", win_stimato(None, 0) == PRIOR_WIN and abs(win_stimato(0.3, 50) - 0.4) < 1e-9 and abs(win_stimato(0.3, 5000) - 0.3) < 0.003))
    # il cambio vero: le gemme vere per oro della via migliore, i draft solo se aperti; cambiandolo i piani si rifanno
    c_tutti, c_niente = R.cambio_oro(0.5, 0.5, tutti), R.cambio_oro(0.5, 0.5, niente)
    rr_ = R.rese(0.5, 0.5)
    out.append(("cambio: la via migliore", c_tutti["gpo"] == max(rr_[k]["gemme"] / rr_[k]["oro"] for k in ("quick", "premier", "costruiti")) and c_niente["via"] == "costruiti"
                and c_tutti["gpo"] < GEMME_PER_ORO))
    vecchio = R.piano("valore", 0.5, aperti_ora=tutti)
    R.imposta_cambio(0.5, 0.5, tutti)
    nuovo = R.piano("valore", 0.5, aperti_ora=tutti)
    out.append(("cambio: l'oro vale le gemme vere, il piano si rifa'", R.gpo == c_tutti["gpo"] and nuovo["esito"]["spende"] < vecchio["esito"]["spende"]))
    gz_wr = R.piano("gemme", 0.5, aperti_ora=tutti, win_c=0.5)
    R.imposta_cambio(0.5, 0.5, tutti, busta=True)
    gz_b = R.piano("gemme", 0.5, aperti_ora=tutti, win_c=0.5)
    out.append(("cambio a prezzo busta: 1.000 = 200, e convertire oro in gemme resta lo stesso piano (il ROI conta le gemme vere)",
                R.gpo == GEMME_PER_ORO and R.via_cambio == "busta" and gz_b["voci"] == gz_wr["voci"] and gz_b["esito"]["gemme"] == gz_wr["esito"]["gemme"]))
    # il pareggio in gemme vere: piu' alto il win rate, piu' gemme tornano; sotto la soglia meno dell'ingresso, alla soglia almeno l'ingresso
    pg_ = R.pareggi(0.5, 0.5)
    ok_pg = True
    for k, w in pg_.items():
        if w is None:
            continue
        sopra = R.rese(w if k != "costruiti" else 0.5, w if k == "costruiti" else 0.5)[k]
        sotto = R.rese(w - 0.01 if k != "costruiti" else 0.5, w - 0.01 if k == "costruiti" else 0.5)[k]
        ok_pg = ok_pg and sopra["gemme"] >= sopra["gemme_in"] > sotto["gemme"]
    out.append(("pareggi in gemme vere", ok_pg and any(w for w in pg_.values())))
    # il goal del mazzo: piu' jolly del goal gemme, il progresso e' la rarita' piu' indietro, le settimane tornano coi jolly del mese
    mz = R.piano("mazzo", 0.4, aperti_ora=tutti, mazzo={"R": 30, "M": 10})
    gz_ = R.piano("gemme", 0.4, aperti_ora=tutti)
    bb_ = R.base(mz["pass"])["buste"]       # le buste che arrivano comunque portano i loro jolly
    jr_m, jm_m = mz["esito"]["jolly_r"] + bb_ * R.valori()["jolly_r"], mz["esito"]["jolly_m"] + bb_ * R.valori()["jolly_m"]
    sett = max(30 / jr_m, 10 / jm_m) * 365.25 / 12 / 7 if jr_m and jm_m else None
    out.append(("mazzo: i jolly prima delle gemme", mz["esito"]["jolly_r"] + mz["esito"]["jolly_m"] > gz_["esito"]["jolly_r"] + gz_["esito"]["jolly_m"] and abs(mz["esito"]["meta"] - min(1, jr_m / 30, jm_m / 10)) < 1e-9))
    out.append(("mazzo: le settimane", sett is not None and abs(mz["esito"]["settimane_mazzo"] - sett) < 1e-9))
    fatto = R.piano("mazzo", 0.4, aperti_ora=tutti, mazzo={"R": 0, "M": 0})
    out.append(("mazzo gia' craftabile: nessuna settimana, decide il guadagno", fatto["esito"]["settimane_mazzo"] is None and fatto["esito"]["meta"] == 1.0))
    mix_ = R.piano({"mazzo": 50, "gemme": 50}, 0.4, aperti_ora=tutti, mazzo={"R": 30, "M": 10})
    out.append(("mazzo nel mix", set(mix_["esito"]["quote"]) == {"mazzo", "gemme"}))
    R.gpo, R.via_cambio = GEMME_PER_ORO, None
    R.__dict__.pop("_memo_piani", None); R.__dict__.pop("_soglie", None)
    # il mix carte + gemme col draft di un altro set (8 nov 2026): il draft resta per le gemme, ma le sue carte non sono del set del goal
    oggi_t = datetime.date.today()
    finto = {"AAA": dict(quick=[[(oggi_t - datetime.timedelta(days=5)).isoformat(), (oggi_t + datetime.timedelta(days=40)).isoformat()]], premier=[], inizio="2020-01-01"),
             "BBB": dict(quick=[], premier=[], inizio="2020-01-01")}
    g_ = globals(); vecchi = (g_["_calendario"], g_["aperti"])
    val0 = R.valori; R.valori = lambda: dict(val0(), carte_draft=40.0, draft=600.0)      # qui i draft danno un pool: 40 carte, 600 gemme
    R.__dict__.pop("_memo_piani", None)
    g_["_calendario"], g_["aperti"] = (lambda: finto), (lambda oggi=None: dict(quick="AAA", premier=None))
    try:
        altro = R.piano({"carte": 70, "gemme": 30}, 0.5, set_="BBB", win_c=0.5)
        suo = R.piano({"carte": 70, "gemme": 30}, 0.5, set_="AAA", win_c=0.5)
    finally:
        g_["_calendario"], g_["aperti"] = vecchi
        R.valori = val0; R.__dict__.pop("valori", None); R.__dict__.pop("_memo_piani", None)
    rb = R.rese(0.5, 0.5)["buste"]["carte"]
    print("   mix carte+gemme: set del goal non aperto", altro["voci"], round(altro["esito"]["carte_set"], 1), "| aperto", suo["voci"], round(suo["esito"]["carte_set"], 1))
    solo_buste = abs(altro["esito"]["carte_set"] - (altro["voci"]["buste"] + altro["voci"]["buste_gemme"]) * rb) < 1e-6
    out.append(("mix con il draft di un altro set: le sue carte non contano per il set del goal", solo_buste and altro["voci"] != suo["voci"]
                and (not suo["voci"]["quick"] or suo["esito"]["carte_set"] > (suo["voci"]["buste"] + suo["voci"]["buste_gemme"]) * rb)))
    so = R.soglie("gemme", 0.4, 0.5, aperti_ora=tutti)
    out.append(("le soglie coprono tutti i win rate", all(x[0][0] == PASSO_SOGLIE * 15 and x[-1][1] == 80 and all(x[i][1] + PASSO_SOGLIE == x[i + 1][0] for i in range(len(x) - 1)) for x in so.values())))
    # gli ingressi in gemme del piano passano in simula
    h = R.simula(gemme_voci={"costruiti": 2}, win_c=0.5, gemme_mese=1000)
    gc0 = ED.resa(0.5, COSTRUITO_GEMME, COSTRUITO_BUSTE)[0]
    out.append(("ingressi in gemme in simula", h["costo"] == 750 and abs(h["gem_fine"] - (1000 + 2 * gc0 - 750)) < 1e-9))
    # tutto il guadagno investito, in ogni piano
    out.append(("il piano usa il 100% dell'oro", all(p_["esito"]["oro_resto"] < 1000 for p_ in (a, b, c))))
    # i collaterali: due piani a pari obiettivo, vince quello che porta di piu' nel resto. Qui ogni evento rende 0 buste a win 0: conta il valore
    n_ = R.rese(0.4, 0.5)
    out.append(("le rese contano tutto", all({"gemme", "buste", "carte", "jolly_r", "jolly_m", "valore"} <= set(x) for x in n_.values()) and n_["costruiti"]["buste"] > 0 and n_["quick"]["carte"] >= n_["quick"]["buste"] * 0))
    # gli eventi constructed: i tuoi due eventi veri tornano con la tabella
    out.append(("premi constructed veri", COSTRUITO_GEMME[4] == 300 and COSTRUITO_BUSTE[4] == 1 and COSTRUITO_GEMME[2] == 75 and COSTRUITO_BUSTE[2] == 1))
    e_c = R.simula(costruiti=2, win_c=0.5, win=0.1)
    gc, bc = ED.resa(0.5, COSTRUITO_GEMME, COSTRUITO_BUSTE)[:2]
    out.append(("simula constructed usa il suo win rate", abs(e_c["premi"] - 2 * gc) < 1e-9 and e_c["costo"] == 1000 and abs(e_c["ritorno"]["buste"] - 2 * bc) < 1e-9))
    h_ = R.simula(buste=0, gemme_mese=500)
    out.append(("le gemme del trend entrano in cassa", h_["gem_fine"] == 500))
    # dove e' andata la spesa
    Sp = Risorse([_f(T % 1, 20000, 5000), _f(T % 2, 15000, 5000, mov=[_m("EventPayEntry", "q1", oro=-5000)]), _f(T % 3, 15000, 4625, mov=[_m("EventPayEntry", "c1", gem=-375)]),
                  _f(T % 4, 15000, 1225, mov=[_m("CampaignGraphPurchaseNode")])], [], ev)
    sp = Sp.spese_eventi(Sp.taglio())
    out.append(("le spese per evento, prima la piu' cara", [x["nome"] for x in sp] == ["Quick Draft", "Constructed event"] and sp[0]["volte"] == 1 and sp[0]["oro"] == 5000 and sp[1]["gemme"] == 375))
    pc = Sp.pass_comprati()
    out.append(("il pass comprato, con la data", len(pc) == 1 and pc[0]["gemme"] == 3400 and pc[0]["data"] == datetime.date(2026, 10, 4) and not Sp.pass_comprati(datetime.date(2026, 10, 1), datetime.date(2026, 10, 3))))
    # la roadmap: tutto quel che il mese paga sta nei 30 giorni
    d0 = datetime.date(2026, 11, 2)
    Rd = Risorse([_f("2026-10-01 12:00:00", 0, 0), _f("2026-10-31 12:00:00", 60000, 1000)], [], ev)
    Rd.foto[-1]["tok"] = 1
    Rd.valori = lambda: dict(Risorse.valori(Rd), oro_mese=30000)
    aperto = {"AAA": dict(quick=[["2026-11-01", "2026-11-05"]], premier=[["2026-11-01", "2026-11-05"]])}
    ee = Rd.simula(premier=3, buste=6, costruiti=2, paga=dict(premier="token", buste="oro", costruiti="gemme"), win=0.5, oro_mese=30000)
    rm = Rd.roadmap(ee, d0, cal=aperto)
    conta = collections.Counter()
    for g in rm["giorni"]:
        for a in g["azioni"]:
            conta[a["k"]] += a["quanti"]
    out.append(("roadmap: ogni voce ci sta", conta == dict(premier=3, buste=6, costruiti=2) and not rm["fuori"] and rm["totale"] == 11))
    out.append(("roadmap: parte dal giorno del piano, ordinata", rm["giorni"][0]["data"] == "2026-11-02" and [g["data"] for g in rm["giorni"]] == sorted(g["data"] for g in rm["giorni"]) and rm["al"] == "2026-12-01"))
    out.append(("roadmap: il draft solo a finestra aperta", all(g["data"] <= "2026-11-05" for g in rm["giorni"] for a in g["azioni"] if a["k"] == "premier")))
    q_ = [a for g in rm["giorni"] for a in g["azioni"] if a["k"] == "premier"]
    out.append(("roadmap: il token non costa oro, gli altri si'", sum(a["token"] for a in q_) == 1 and sum(a["oro"] for a in q_) == 20000 and q_[0]["set"] == "AAA" and q_[0]["chiude"] == "2026-11-05" and q_[0]["dove"] == "Events"))
    out.append(("roadmap: la cassa non va mai sotto zero", all(g["oro"] >= 0 and g["gemme"] >= 0 for g in rm["giorni"])))
    # l'income in piu' rifa' la roadmap (9 nov 2026): le azioni in ritardo non sono un extra, l'extra si', e dopo l'adattamento non scatta di nuovo
    pm = json.loads(json.dumps(dict(rm, partenza=Rd.fatti(d0))))
    o5 = d0 + datetime.timedelta(days=5)
    s0 = Rd.surplus(pm, o5)
    out.append(("surplus: azioni in ritardo e nessun income in piu': niente", s0 is not None and not s0["scatta"] and s0["oro"] < 0))
    vero = Rd.saldo
    Rd.saldo = lambda al=None: dict(vero(al), oro=vero(al)["oro"] + 20000)
    s1 = Rd.surplus(pm, o5)
    r1 = Rd.roadmap(ee, o5, cal=aperto)
    Rd.adatta(pm, r1, o5, s1)
    s2 = Rd.surplus(pm, o5)
    date_ = [g["data"] for g in pm["giorni"]]
    out.append(("surplus: 20.000 oro in piu' rifanno la roadmap da oggi", s1["scatta"] and 10000 < s1["oro"] < 20000 and date_[0] == "2026-11-02" and all(d_ >= "2026-11-07" for d_ in date_[1:])
                and date_ == sorted(date_) and pm["adattato"][-1]["oro"] == s1["oro"] and pm["cassa_dal"] == "2026-11-07"))
    out.append(("surplus: dopo l'adattamento non scatta di nuovo", s2 is not None and not s2["scatta"] and abs(s2["oro"]) <= 1))
    Rd.saldo = vero
    # la roadmap contro la cassa vera (9 nov 2026): il primo giorno a zero; le azioni in ritardo non sono un ritardo di soldi (il loro prezzo e' ancora in cassa), manca solo l'income che non e' entrato
    pa = json.loads(json.dumps(dict(rm, partenza=Rd.fatti(d0))))
    an = Rd.andamento(pa, o5, ultima=o5)
    b_o = Rd.base(False)["oro"] * 12 / 365.25
    gap5 = an["giorni"][5]["vero_o"] - an["giorni"][5]["att_o"]
    crudo5 = an["giorni"][5]["vero_o"] - pa["cassa"][5][0]
    out.append(("andamento: il giorno del piano e' a zero", len(an["giorni"]) == 6 and abs(scarto(an["giorni"][0], 0.2)[2]) < 0.01))
    out.append(("andamento: manca solo l'income, non le azioni in ritardo", abs(gap5 + 5 * b_o) <= 2 and abs(crudo5 - gap5) > 1000 and an["azioni"].get("ritardo", 0) > 0))
    Rd.saldo = lambda al=None: dict(vero(al), oro=vero(al)["oro"] + (20000 if al and al >= d0 + datetime.timedelta(days=3) else 0))
    an2 = Rd.andamento(json.loads(json.dumps(pa)), o5, ultima=o5)
    s5 = scarto(an2["giorni"][5], 0.2)
    out.append(("andamento: 20.000 oro in piu' dal terzo giorno, sopra la roadmap", abs(an2["giorni"][2]["vero_o"] - an["giorni"][2]["vero_o"]) == 0 and abs(an2["giorni"][5]["vero_o"] - an2["giorni"][5]["att_o"] - (20000 - 5 * b_o)) <= 2
                and s5[2] > 0 and scarto(an2["giorni"][5], 0.072)[2] < s5[2]))
    Rd.saldo = vero
    # le voci del Trend contro le attese del piano (9 nov 2026): l'atteso cresce coi giorni, il primo giorno non ha una %, il ROI conta le buste a 200 gemme
    att_ = dict(oro=0, gemme=0, buste=30, carte=300, jolly_r=3, jolly_m=1)
    an3 = Rd.andamento(json.loads(json.dumps(pa)), o5, ultima=o5, attese=att_)
    g5 = an3["giorni"][5]
    out.append(("andamento per voce: l'atteso delle buste e' la quota al giorno per i giorni passati", abs(g5["att_b"] - 30 * 12 / 365.25 * 5) < 1e-6 and abs(g5["att_j"] - 4 * 12 / 365.25 * 5) < 1e-6
                and scarto_voce(an3["giorni"][0], "Buste")[2] is None and scarto_voce(g5, "Buste")[2] is not None))
    roi5 = scarto_voce(dict(g5, vero_b=g5["att_b"] + 1), "ROI", 0.2)
    out.append(("il ROI conta una busta in piu' come 200 gemme", abs((roi5[0] - roi5[1]) - (g5["vero_o"] - g5["att_o"]) * 0.2 - (g5["vero_g"] - g5["att_g"]) - 200) < 1e-6))
    out.append(("senza le attese del piano le voci non ci sono (prova negativa)", scarto_voce(an["giorni"][5], "Buste") is None and scarto_voce(an["giorni"][5], "Oro") is not None))
    # i soldi: se il mese non paga, quel che resta si dice
    Rp = Risorse([_f("2026-10-01 12:00:00", 0, 0), _f("2026-10-31 12:00:00", 0, 0)], [], ev)
    Rp.valori = lambda: dict(Risorse.valori(Rp), oro_mese=3000); Rp.base = lambda con_pass=True: dict(Risorse.base(Rp, con_pass), oro=3000)
    rp = Rp.roadmap(Rp.simula(buste=9, costruiti=1), d0, cal=aperto)
    out.append(("roadmap: quel che i soldi non pagano resta fuori e si dice", any(x["perche"] == "money" for x in rp["fuori"]) and all(g["oro"] >= 0 for g in rp["giorni"]) and rp["totale"] < 10))
    rv = Rp.roadmap(Rp.simula(buste=3, costruiti=1), d0, cal=aperto)        # 100 oro al giorno: l'evento arriva al giorno 26, e le buste non gli mangiano l'oro prima
    out.append(("roadmap: l'evento prima delle buste", [a["k"] for g in rv["giorni"] for a in g["azioni"]] == ["costruiti"] and any(x["k"] == "buste" and x["perche"] == "money" for x in rv["fuori"])))
    fin2 = {"AAA": dict(quick=[["2026-11-20", "2026-11-24"]], premier=[])}
    Rs = Risorse([_f("2026-10-01 12:00:00", 0, 0), _f("2026-10-31 12:00:00", 3000, 0)], [], ev)     # 100 oro al giorno, 3.000 in cassa: le buste non devono mangiare i 5.000 del draft del 20
    Rs.base = lambda con_pass=True: dict(Risorse.base(Rs, con_pass), oro=3000)
    r2 = Rs.roadmap(Rs.simula(quick=1, buste=3, paga="oro"), d0, cal=fin2)
    k2 = {a["k"]: g["data"] for g in r2["giorni"] for a in g["azioni"]}
    out.append(("roadmap: il draft futuro tiene l'oro che gli serve", k2.get("quick", "").startswith("2026-11-2") and min(g["oro"] for g in r2["giorni"]) >= 0))
    fin3 = {"AAA": dict(quick=[["2026-11-02", "2026-11-05"]], premier=[])}
    r3 = Rd.roadmap(Rd.simula(quick=1, paga="oro"), datetime.date(2026, 11, 5), cal=fin3)
    out.append(("roadmap: il giorno che chiude non si comincia un draft", r3["totale"] == 0 and r3["fuori"][0]["perche"] == "closed"))
    fin4 = {"BBB": dict(inizio="2026-11-10", premier=[["2026-11-10", "2026-12-30"]], quick=[])}
    Rw = Risorse([_f("2026-10-01 12:00:00", 0, 0), _f("2026-10-11 12:00:00", 0, 9000, mov=[_m("CampaignGraphPurchaseNode"), _m("CampaignGraphTieredRewardNode", oro=4000, gem=1200)]), _f("2026-10-31 12:00:00", 0, 0)], [], ev)
    Rw.scatto_pass = lambda: dict(oro=4000, gem=1200, bu=17, c=0, costo=3400)
    rw = Rw.roadmap(Rw.simula(), d0, cal=fin4)
    out.append(("roadmap: senza gemme il pass non si puo' comprare, e lo dice", rw["fuori"] == [dict(k="passo", nome="Mastery Pass", quanti=1, perche="money")]))
    Rw.saldo = lambda al=None: dict(oro=0, gem=3400, jolly=[0] * 4, buste=0, vault=0, token=0)
    rw = Rw.roadmap(Rw.simula(), d0, cal=fin4)
    pz_ = [(g["data"], a["gemme"]) for g in rw["giorni"] for a in g["azioni"] if a["k"] == "passo"]
    out.append(("roadmap: il pass il giorno che esce", pz_ == [("2026-11-10", 3400)] and rw["giorni"][-1]["oro"] >= 4000))
    out.append(("buste di un set solo da quando esce", _aperto("buste", datetime.date(2026, 11, 9), fin4, "BBB") is None and _aperto("buste", datetime.date(2026, 11, 10), fin4, "BBB") is not None))
    # nessuna finestra nel mese: resta fuori, non si inventa una data
    rc = Rd.roadmap(Rd.simula(quick=2, paga="oro"), d0, cal={})
    out.append(("roadmap: senza una finestra il draft non si inventa", rc["totale"] == 0 and rc["fuori"] == [dict(k="quick", nome="Quick Draft", quanti=2, perche="closed")] and len(rc["giorni"]) == 1))
    Rk = Risorse([_f("2026-10-01 12:00:00", 0, 0), dict(_f("2026-10-31 12:00:00", 0, 0), tok=1)], [], ev)
    ek = Rk.simula(premier=1, paga="token")
    out.append(("il token vale al massimo l'ingresso, e un Premier che rende meno lo pareggia", ek["spende"] == min(INGRESSI["premier"]["gemme"], ek["ottiene"]) and ek["oro_speso"] == 0 and ek["gemme_spese"] == 0 and ek["saldo"] >= 0))
    # il Mastery Pass: lo scatto si ripete a ogni set e costa; i token in tasca non sono un'entrata
    fp = [_f("2026-10-01 12:00:00", 0, 3400, tr=0), _f("2026-10-11 12:00:00", 4000, 1200, tr=0, mov=[_m("CampaignGraphPurchaseNode"), _m("CampaignGraphTieredRewardNode", oro=4000, gem=1200, bu=17)]),
          _f("2026-10-31 12:00:00", 34000, 1200)]
    Rv = Risorse(fp, [], ev)
    sp, m_ = Rv.scatto_pass(), 365.25 / 12 / 31
    out.append(("pass: lo scatto si legge dai log", (sp["oro"], sp["gem"], sp["bu"], sp["costo"]) == (4000, 1200, 17, 3400)))
    bc, bs = Rv.base(True), Rv.base(False)
    out.append(("pass: in base c'e' a ogni set, col suo prezzo", abs(bc["gemme"] - (1200 - 3400) * PASS_ANNO / 12) < 1e-6 and abs(bc["buste"] - 17 * PASS_ANNO / 12) < 1e-6 and bs["gemme"] == 0 and bs["buste"] == 0))
    gg_ = {"AAA": {"quick": [["2026-11-01", "2026-11-06"], ["2027-01-05", "2027-01-18"]], "premier": [["2026-11-01", "2026-12-02"]]}, "BBB": {"quick": [["2026-11-07", "2026-12-30"]]}}
    o_ = datetime.date(2026, 11, 6)
    out.append(("capienza: il Quick che chiude oggi non conta", capienza("quick", o_, gg_, "AAA") == 0 and capienza("quick", o_, gg_) == 29 * EVENTI_AL_GIORNO))
    out.append(("capienza: il Premier fino al 2 dicembre", capienza("premier", o_, gg_, "AAA") == 27 * EVENTI_AL_GIORNO))
    out.append(("capienza: oggi conta se non chiude oggi", capienza("premier", datetime.date(2026, 11, 1), gg_, "AAA") == 30 * EVENTI_AL_GIORNO))
    ep = Rv.simula(con_pass=True); e0 = Rv.simula(con_pass=False)
    out.append(("il pass entra nel bilancio per la sua quota", abs(ep["spende"] - 3400 * PASS_ANNO / 12) < 1e-6 and abs(ep["ottiene"] - (1200 + 800 + 17 * 200) * PASS_ANNO / 12) < 1e-6 and e0["spende"] == 0 and e0["ottiene"] == 0))
    out.append(("una busta vale il suo prezzo", Rv.valori()["busta"] == 200 and Rv.rese()["buste"]["valore"] == 200))
    pv = Rv.piano("gemme", 0.4, aperti_ora=dict(quick="AAA", premier=None), win_c=0.5)
    out.append(("il piano non resta mai sotto zero in gemme", pv["esito"]["gemme"] >= 0))
    # un goal non chiude mai in perdita
    Rq = Risorse([_f("2026-10-01 12:00:00", 0, 0), _f("2026-10-31 12:00:00", 30000, 0)], [], ev)
    for ob_ in ("jolly", "buste", "gemme"):
        pq = Rq.piano(ob_, 0.3, aperti_ora=dict(quick="AAA", premier="AAA"), win_c=0.3)
        vq = pq["voci"]
        eq = Rq.simula(vq["quick"], vq["premier"], vq["buste"], 0, dict(premier="token" if vq["tp"] else "oro", quick="oro", costruiti="oro", buste="oro", mitiche="oro"), 0.3, pq["oro_mese"], buste_gemme=vq["buste_gemme"], costruiti=vq["costruiti"], win_c=0.3, gemme_voci=pq["gemme_voci"], con_pass=pq["pass"])
        out.append((f"goal {ob_}: il ROI non e' negativo", eq["saldo"] >= -1e-6))
        out.append((f"goal {ob_}: il piano e simula fanno lo stesso conto", abs(eq["spende"] - pq["esito"]["spende"]) < 1e-6 and abs(eq["ottiene"] - pq["esito"]["ottiene"]) < 1e-6))
    # la varianza: le buste non oscillano, un draft si', e a mano
    Rv2 = Risorse([_f("2026-10-01 12:00:00", 0, 0), _f("2026-10-31 12:00:00", 0, 0)], [], ev)
    r5 = Rv2.rese(0.5, 0.5)
    d5 = ED.distribuzione(0.5); m5 = sum(d5[k] * (ED.GEMME[k] + ED.BUSTE[k] * 200) for k in d5); v5 = sum(d5[k] * (ED.GEMME[k] + ED.BUSTE[k] * 200 - m5) ** 2 for k in d5)
    out.append(("varianza: un Quick a mano, e la busta zero", abs(r5["quick"]["var"] - v5) < 1e-6 and r5["buste"]["var"] == 0))
    out.append(("varianza: due corse sommano, le buste no", abs(Rv2.rischio(Rv2.simula(quick=2, buste=5), 0.5, 0.5) - (2 * v5) ** 0.5) < 1e-6))
    # chi conviene: il valore segue win rate e cambio, eventi o buste
    cv7, cv3 = Rv2.convenienza(0.75, 0.75), Rv2.convenienza(0.3, 0.3)
    out.append(("convenienza: a win rate basso le buste, ad alto gli eventi", cv3[0]["k"] == "buste" and cv7[0]["k"] != "buste"))
    Rb = Risorse([_f("2026-10-01 12:00:00", 0, 0), _f("2026-10-31 12:00:00", 30000, 0)], [], ev)
    bb = Rb.piano("valore", 0.3, aperti_ora=dict(quick="AAA", premier="AAA"), win_c=0.3)["voci"]
    be = Rb.piano("valore", 0.75, aperti_ora=dict(quick="AAA", premier="AAA"), win_c=0.75)["voci"]
    out.append(("goal valore: sceglie da solo", bb["quick"] + bb["premier"] + bb["costruiti"] == 0 and bb["buste"] > 0 and be["quick"] + be["premier"] + be["costruiti"] > 0))
    # il ROI rifatto a mano: 2 Quick in oro e 3 buste in gemme, al 50%
    Rh = Risorse([_f("2026-10-01 12:00:00", 0, 1000), _f("2026-10-31 12:00:00", 0, 1000)], [], ev)
    g5, b5 = ED.resa(0.5)[:2]
    eh = Rh.simula(quick=2, buste_gemme=3, win=0.5)
    out.append(("ROI a mano: spendi", eh["spende"] == 2 * 5000 * 0.2 + 3 * 200 and eh["oro_speso"] == 10000 and eh["gemme_spese"] == 600))
    out.append(("ROI a mano: ottieni e saldo", abs(eh["ottiene"] - (2 * g5 + 2 * b5 * 200 + 3 * 200)) < 1e-6 and abs(eh["saldo"] - (eh["ottiene"] - eh["spende"])) < 1e-9))
    # solo quel che serve al goal
    Rz = Risorse([_f("2026-10-01 12:00:00", 0, 0), _f("2026-10-31 12:00:00", 30000, 0)], [], ev)
    pg = Rz.piano("gemme", 0.75, aperti_ora=dict(quick="AAA", premier="AAA"), win_c=0.75)
    out.append(("goal gemme: mai una busta, l'oro avanza", pg["voci"]["buste"] == 0 and pg["voci"]["buste_gemme"] == 0))
    pl = Rz.piano("gemme", 0.3, aperti_ora=dict(quick="AAA", premier="AAA"), win_c=0.3)
    out.append(("goal gemme a win rate basso: non compra niente", pl["voci"]["buste"] == 0 and pl["voci"]["quick"] == 0 and pl["voci"]["costruiti"] == 0))
    pc = Rz.piano("carte", 0.75, set_="AAA", aperti_ora=dict(quick="AAA", premier="AAA"), win_c=0.75)
    out.append(("goal carte: niente eventi constructed", pc["voci"]["costruiti"] == 0 and "costruiti" not in pc["gemme_voci"]))
    # il goal delle carte di un set: un draft di un altro set non si mette in calendario
    due = {"AAA": {"nome": "A", "quick": [["2026-11-01", "2026-11-03"]]}, "BBB": {"nome": "B", "quick": [["2026-11-04", "2026-11-30"]]}}
    rs_ = Rd.roadmap(Rd.simula(quick=2, paga="oro"), d0, cal=due, solo_set="AAA")
    out.append(("roadmap: col set del goal, solo i suoi draft", all(a["set"] == "AAA" for g in rs_["giorni"] for a in g["azioni"]) and Rd.roadmap(Rd.simula(quick=2, paga="oro"), d0, cal=due)["totale"] >= rs_["totale"]))
    out.append(("roadmap: prova negativa, senza il filtro l'altro set entra", _aperto("quick", datetime.date(2026, 11, 10), due)["set"] == "BBB" and _aperto("quick", datetime.date(2026, 11, 10), due, "AAA") is None))
    # il mix gemme + carte di un set (9 nov 2026): il Quick del set del goal apre dopo, uno di un altro set e' aperto adesso; la roadmap li mette in quello con cui il piano li conta
    mix_c = {"AAA": {"nome": "A", "quick": [["2026-11-20", "2026-11-30"]], "inizio": "2026-11-01"}, "BBB": {"nome": "B", "quick": [["2026-11-01", "2026-11-12"]]}}
    e_mix = Rd.simula(quick=3, paga="oro")
    r_mix = Rd.roadmap(e_mix, d0, cal=mix_c, solo_set=dict(quick="AAA", premier=None, buste="AAA", mitiche="AAA"))
    r_tutti = Rd.roadmap(e_mix, d0, cal=mix_c)
    q_mix = [(g["data"], a["set"]) for g in r_mix["giorni"] for a in g["azioni"] if a["k"] == "quick"]
    out.append(("mix gemme + carte: i Quick del set del goal nelle sue finestre, non nel primo aperto", q_mix and all(st == "AAA" and d_ >= "2026-11-20" for d_, st in q_mix)
                and any(a["set"] == "BBB" for g in r_tutti["giorni"] for a in g["azioni"])))
    pz_mix = Rz.piano(dict(gemme=1.0, carte=1.0), 0.75, set_="AAA", aperti_ora=dict(quick="AAA", premier=None), win_c=0.75)
    # i constructed premiano col set piu' nuovo su Arena, letto dal calendario (9 nov 2026): TRK dal 10 nov; DFT che torna il 19 ott non e' un set nuovo
    out.append(("constructed: il set dal calendario, i set che tornano no", set_costruiti(datetime.date(2026, 11, 9)) == "TRK" and set_costruiti(datetime.date(2026, 10, 20)) == "FRA"))
    c_trk = {"TRK": {"nome": "Star Trek", "inizio": "2026-11-10"}}
    e_c2 = Rd.simula(costruiti=2, paga="oro")
    d_c = [g["data"] for g in Rd.roadmap(e_c2, d0, cal=c_trk, solo_set=dict(costruiti="TRK"))["giorni"] for a in g["azioni"] if a["k"] == "costruiti"]
    d_c0 = [g["data"] for g in Rd.roadmap(e_c2, d0, cal=c_trk)["giorni"] for a in g["azioni"] if a["k"] == "costruiti"]
    out.append(("constructed per le carte del set: solo da quando esce su Arena", d_c and all(d_ >= "2026-11-10" for d_ in d_c) and any(d_ < "2026-11-10" for d_ in d_c0)))
    out.append(("il piano col goal carte da' alla roadmap il set di ogni voce", pz_mix["solo"] == dict(quick="AAA", premier=None, buste="AAA", mitiche="AAA", costruiti=None) and Rz.piano("gemme", 0.75, aperti_ora=dict(quick="AAA", premier=None), win_c=0.75)["solo"] is None))
    # quel che hai fatto si segna, in ritardo quel che e' passato
    Rd.fatti = lambda dal, al=None: dict(quick=0, premier=2, costruiti=0, buste=2)
    pz = json.loads(json.dumps(rm)); pz["partenza"] = dict(quick=0, premier=0, costruiti=0, buste=0)
    n_f, n_t = Rd.segna(pz, datetime.date(2026, 11, 20))
    st = [(a["k"], a["stato"]) for g in pz["giorni"] for a in g["azioni"]]
    out.append(("roadmap: fatte e in ritardo", n_f == 4 and n_t == 11 and ("premier", "ritardo") in st and any(x[1] == "fatta" for x in st)))
    pz2 = json.loads(json.dumps(pz)); Rd.segna(pz2, datetime.date(2026, 11, 1))
    out.append(("roadmap: prima del giorno sono da fare", all(a["stato"] in ("fatta", "da fare") for g in pz2["giorni"] for a in g["azioni"])))
    pz["partenza"] = dict(quick=0, premier=2, costruiti=0, buste=2)
    out.append(("roadmap: quel che c'era prima del piano non conta", Rd.segna(pz, datetime.date(2026, 11, 20))[0] == 0))
    import tempfile
    f_ = os.path.join(tempfile.mkdtemp(), "p.json")
    salva_piano(rm, f_); ok_ = leggi_piano(f_) == rm; togli_piano(f_)
    out.append(("il piano si salva, si rilegge e si toglie", ok_ and leggi_piano(f_) is None))
    # il confronto col Farmer: il trend contro il piano, sul grafico
    Rc = Risorse([_f("2026-10-01 12:00:00", 31000, 100), _f("2026-10-31 12:00:00", 61000, 100)], [], ev)
    m_, ec = 365.25 / 12, Rc.simula(buste=9)
    cc = Rc.confronto(ec)
    out.append(("confronto: il trend e' la media della storia, il piano la base piu' le voci", abs(cc["senza"]["oro_piu"] * 31 - 30000) < 1e-6 and abs(cc["con"]["oro_meno"] * m_ - 9000) < 1e-6 and abs(cc["con"]["bu_ott"] * m_ - 9) < 1e-6))
    out.append(("confronto: il piano non cambia l'oro farmato", abs(cc["con"]["oro_piu"] - cc["senza"]["oro_piu"]) < 1e-9))
    fermo = Rc.confronto(Rc.simula())
    out.append(("confronto: un piano vuoto e' il trend", all(abs(fermo["con"][c] - fermo["senza"][c]) < 1e-9 for c in fermo["con"])))
    cv_ = Rc.confronto(Rc.simula(buste=60))
    out.append(("confronto: dice quando il piano svuota la cassa", cv_["finisce"]["gem"] is None and 58 <= cv_["finisce"]["oro"] <= 62 and cc["finisce"]["oro"] is None))
    # oro e gemme: quanto vale l'oro speso e quanto se ne spreca
    cb = Rc.cambio(ec, 0.5, 0.5)
    out.append(("cambio: 9 buste in oro sono 1.800 gemme, nessuna gemma torna", cb["oro"] == 9000 and cb["in_gemme"] == 1800 and cb["gemme"] == 0 and abs(cb["valore"] - 9 * Rc.valori()["busta"]) < 1e-6))
    top, tutte_ = cb["meglio"], {k: Rc.cambio(Rc.simula(**{k: 1}), 0.5, 0.5) for k in ("quick", "premier", "costruiti", "buste", "mitiche")}
    out.append(("cambio: la voce migliore non spreca niente", tutte_[top]["spreco"] < 1e-6))
    out.append(("cambio: tutte le altre si'", all(x["spreco"] > 0 for k, x in tutte_.items() if k != top)))
    out.append(("cambio: quel che paghi in gemme non e' oro speso", Rc.cambio(Rc.simula(buste=9, paga="gemme"), 0.5, 0.5)["oro"] == 0))
    # i periodi
    d = datetime.date(2026, 11, 4)
    out.append(("settimana da lunedi'", inizio(d, "Settimana") == datetime.date(2026, 11, 2) and fine(inizio(d, "Settimana"), "Settimana") == datetime.date(2026, 11, 8)))
    out.append(("mese", fine(datetime.date(2026, 2, 1), "Mese") == datetime.date(2026, 2, 28) and fine(datetime.date(2026, 12, 1), "Mese") == datetime.date(2026, 12, 31)))
    return out


def main():
    R = carica()
    if not R.foto:
        print("nessuna foto del conto nei log")
        return 0
    for k in R.periodi("Mese"):
        s = R.taglio("Mese", k)
        print(f"{nome_periodo(k, 'Mese'):<16} oro +{s['oro_piu']} -{s['oro_meno']} | gemme +{s['gem_piu']} -{s['gem_meno']} | buste +{s['bu_ott']} aperte {s['bu_ap']}"
              f" | carte {s['carte']} (draft {s['c_draft']}, premi {s['c_premi']}, buste ~{s['c_buste']}) | jolly {s['jolly_piu']} usati {s['jolly_meno']} | giorni {s['giorni']}")
    s = R.taglio()
    print(f"dal {R.dal} al {R.al}, {s['giorni']} giorni, oro al giorno {s['oro_piu'] / s['giorni']:.0f}")
    print("spese oro:", dict(s["spese"]), "| gemme:", dict(s["spese_gem"]), "| volte:", dict(s["volte"]), "| buste nel negozio:", s["bu_comp"])
    print("adesso:", R.saldo())
    if "--prova" in sys.argv:
        rossi = 0
        for nome, ok in casi() + prova_conti():
            print(f"  {'ok' if ok else 'ROSSO'} {nome}"); rossi += not ok
        for nome, (calcolato, vero) in bilancio(R).items():
            ok = calcolato == vero
            print(f"  {'ok' if ok else 'ROSSO'} bilancio {nome}: {calcolato} contro {vero}"); rossi += not ok
        for g in GRANA:          # ogni taglio somma al totale, e dentro un periodo le righe sommano al periodo
            ok = sum(x[2]["oro_piu"] for x in R.righe(g)) == s["oro_piu"] and sum(x[2]["carte"] for x in R.righe(g)) == s["carte"]
            ok = ok and all(sum(x[2]["oro_piu"] for x in R.righe(g, k)) == R.taglio(g, k)["oro_piu"] for k in R.periodi(g))
            print(f"  {'ok' if ok else 'ROSSO'} le righe di {g} sommano al totale"); rossi += not ok
        # la prova negativa: una foto rotta apposta deve far cambiare il calcolo, e un prezzo sbagliato rompere il caso delle buste
        global PREZZO_BUSTA
        vero = PREZZO_BUSTA; PREZZO_BUSTA = 900
        rotto = dict(casi())["8 buste nel negozio"]; PREZZO_BUSTA = vero
        print(f"  {'ok' if not rotto else 'ROSSO'} prova negativa: il prezzo sbagliato delle buste e' rosso"); rossi += rotto
        global _aperto
        vero_ap = _aperto; _aperto = lambda k, d, cal, s_=None: dict(set="", chiude="")       # un calendario che non conta: il draft esce dalla finestra
        rotto = dict(casi())["roadmap: senza una finestra il draft non si inventa"]; _aperto = vero_ap
        print(f"  {'ok' if not rotto else 'ROSSO'} prova negativa: un calendario ignorato e' rosso"); rossi += rotto
        ver = aperti(datetime.date(2026, 11, 4)), aperti(datetime.date(2026, 11, 8)), set_mancanti("FRA")
        ok = ver[0] == dict(quick="FRA", premier="FRA") and ver[1] == dict(quick="BLB", premier="FRA") and ver[2] and 0 < ver[2]["fatte"] <= ver[2]["tutte"] and set_principali(datetime.date(2026, 11, 4))[0][0] == "FRA"
        trk = set_farmer(datetime.date(2026, 11, 9)), set_mancanti("TRK")      # Star Trek prima dell'uscita, dal calendario e dal database di Arena (9 nov 2026)
        ok = ok and trk[0][0] == ("TRK", "Star Trek") and "FRA" in [c for c, _n in trk[0]] and bool(trk[1]) and trk[1]["tutte"] > 400
        ok = ok and "TRK" not in [c for c, _n in set_principali(datetime.date(2026, 11, 9))]      # uscito il 13: dal calendario, non dai set usciti
        print(f"  {'ok' if ok else 'ROSSO'} calendario e set: {ver}"); rossi += not ok
        print("verde" if not rossi else f"{rossi} ROSSI")
        return 1 if rossi else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
