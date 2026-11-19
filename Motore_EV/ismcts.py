"""Il motore dell'EV di nuova generazione, pezzo 3: IS-MCTS sul motore di partita (sessione Magic 22, 19 nov 2026).

Autore, 19 nov 2026: «le alternative sono le azioni che Arena offriva piu' attacchi e blocchi; le determinizzazioni pescano la sua mano dal pezzo 2 e il
tuo grimorio con quasi-Monte Carlo; stessi mondi per tutte le alternative; orizzonte fino alla fine del suo turno dopo; foglie valutate dal pezzo 1. Lo
scarto di una giocata e' il valore della scelta fatta meno quello della migliore alternativa. Carta che il motore non copre: non stimabile, mai inventata».

Come e' costruito (nessun file del motore cambiato: Motore_Partita/ e' di un'altra sessione)
  - Il punto di scelta e lo stato vengono da Motore_Partita/confronto_log.py (passo 8.3: DalLog, Riparti, verifica): il tavolo del motore deve essere
    quello del log, se no il punto e' «non stimabile» col perche'. Le candidate sono quelle del Cercatore (guarda_avanti: le mosse legali che il motore
    sa fare in quel punto, cioe' terre, magie e abilita' che Arena offriva e che il motore copre, attacchi, blocchi) piu' la mossa vera.
  - Information Set: ogni mondo e' una determinizzazione di quello che Hero non vede. La mano dell'avversario si pesca dalle carte nascoste del suo
    mazzo modello con i pesi del pezzo 2 (mano_avversaria.credenza: le copie rimaste e le sue non-azioni); il tuo grimorio con la prossima pescata
    stratificata fra i mondi (quasi-Monte Carlo: in W mondi ogni carta del grimorio e' la prossima pescata W/n volte, il resto a caso).
  - Numeri casuali comuni: tutte le candidate si giocano negli stessi mondi. Il budget si spende per dimezzamenti successivi (sequential halving, la
    selezione di MCTS a un livello): giro 1 tutte le candidate su W0 mondi, poi la meta' migliore su altri W0, e cosi' via; la mossa vera non esce mai,
    cosi' il confronto con la migliore e' sempre sugli stessi mondi.
  - L'orizzonte: la partita di prova si ferma alla fine del suo turno dopo (turni K = 1 se la scelta e' nel tuo turno, 2 se e' nel suo) e la foglia la
    giudica il pezzo 1 (valuta_carte: le carte del tavolo come vettori). Dopo la scelta giocano due Semplice (il limite del passo 8.2: i giocatori finti
    non sono avversari veri).
  - Lo scarto: valore della mossa vera meno valore della migliore, in punti di probabilita' di vincere, coi mondi in comune; e il test dei segni sulle
    coppie mondo per mondo. «C'era di meglio» solo con scarto oltre SOGLIA e p sotto P_MAX.

Uso (mai con MTGA.exe aperto: si ferma da solo; a priorita' bassa)
  py -I -X utf8 Motore_EV/ismcts.py --pilota [N] [--processi 8]   N punti dei limited di FRA -> Motore_EV/ismcts_pilota.json, Note/Motore_EV_ISMCTS.md
  py -I -X utf8 Motore_EV/ismcts.py --prova
"""
import os, sys, json, math, time, argparse
from pathlib import Path
QUI = Path(__file__).resolve().parent
ROOT = QUI.parent
sys.path.insert(0, str(ROOT / "Companion")); import percorsi  # noqa: E402,F401
sys.path.insert(0, str(ROOT / "Motore_Partita"))
sys.path.insert(0, str(QUI))
import numpy as np  # noqa: E402

USCITA = ROOT / "Log_Arena" / "ismcts.json"       # i risultati sulle partite di chi usa l'app (fuori da git); dal 19 nov 2026
VECCHIO = QUI / "ismcts_pilota.json"              # il primo pilota, sulle partite di FRA di Autore (letto una volta, poi USCITA)
NOTA = ROOT / "Note" / "Motore_EV_ISMCTS.md"
W0 = 6              # mondi per giro
GIRI = 3            # giri di dimezzamento
SOGLIA = 5.0        # punti di P: sotto, la differenza non si chiama «c'era di meglio»
P_MAX = 0.1

_STATO = {"pesi": None, "w": 0, "W": 1}


# ---------------------------------------------------------------------------- la foglia: il pezzo 1 sul tavolo del motore
class FogliaCarte:
    """Il valutatore delle partite troncate (stessa interfaccia di Motore_Partita/valuta.Modello.valuta): la P del pezzo 1 per il giocatore i."""

    def valuta(self, p, i):
        import valuta_carte as VC
        import prob_vittoria as PV
        import testi_carte as TC
        t = p.t
        g, k = t.giocatori[i], t.giocatori[1 - i]

        def lato(j):
            cre, non, terre = [], [], 0
            for o in t.campo:
                if o.controllore != j or o.carta is None:
                    continue
                tipi = set(o.carta.tipi)
                if "land" in tipi and "creature" not in tipi:
                    terre += 1; continue
                gid = TC.per_nome(o.carta.nome)
                if "creature" in tipi:
                    cre.append((dict(p=max(0, t.forza_di(o)), t=max(0, t.costituzione_di(o) - o.danno), kw=sorted(t.parole_di(o)), girato=o.tappato), gid))
                elif gid:
                    non.append(gid)
            return cre, non, terre
        cu, nu, tu = lato(i); co, no, to = lato(1 - i)
        tocca_me = p.attivo != i         # a fine turno: chi ha appena finito e' p.attivo
        giro = (t.turno_numero + 2) // 2
        st = dict(tocca_me=1 if tocca_me else 0, N=giro, on_play=0, LU=max(0, g.vite), LO=max(0, k.vite),
                  miei=[c for c, _ in cu], suoi=[c for c, _ in co], TERU=tu, TERO=to, MANU=len(g.mano), MANO=len(k.mano))
        if k.vite <= 0 < g.vite:
            return 1.0
        if g.vite <= 0:
            return 0.0
        zone = {"cre_u": [x for _, x in cu if x], "cre_o": [x for _, x in co if x], "non_u": nu, "non_o": no,
                "mano": [x for x in (TC.per_nome(o.carta.nome) for o in g.mano if o.carta is not None) if x]}
        q = VC.p_tavolo(PV.vettore(st), zone, None, giro, tocca_me)
        return 0.5 if q is None else q


# ---------------------------------------------------------------------------- le determinizzazioni
def nascondi_ev(t, i, rng):
    """Come guarda_avanti.nascondi, ma: la mano dell'avversario pescata coi pesi del pezzo 2; la tua prossima pescata stratificata fra i mondi."""
    pesi = _STATO["pesi"] or {}
    w, W = _STATO["w"], _STATO["W"]
    for j, gi in enumerate(t.giocatori):
        if j == i:
            posti = list(gi.grimorio.carte)
            carte = sorted((o.fisica for o in posti), key=lambda c: c.n)
            n = len(carte)
            if n:
                base = np.random.default_rng(len(carte) * 7919 + 17).permutation(n)
                top = int(base[(w * n // max(W, 1)) % n])
                resto = [x for x in rng.permutation(n) if x != top]
                ordine = [top] + resto
                for o, kk in zip(posti, ordine):
                    o.carta = carte[int(kk)]
        else:
            mano, grim = list(gi.mano), list(gi.grimorio.carte)
            carte = sorted((o.fisica for o in mano + grim), key=lambda c: c.n)
            if not carte:
                continue
            pw = np.array([max(1e-6, pesi.get(getattr(c, "nome", None), 1.0)) for c in carte], float)
            h = len(mano)
            scelte = []
            disp = np.ones(len(carte), bool)
            for _ in range(h):          # senza rimessa, proporzionale ai pesi
                q = pw * disp
                if q.sum() <= 0:
                    break
                x = int(rng.choice(len(carte), p=q / q.sum()))
                scelte.append(x); disp[x] = False
            resto = [x for x in rng.permutation(len(carte)) if disp[x]]
            for o, kk in zip(mano + grim, scelte + resto):
                o.carta = carte[int(kk)]
    for gi in t.giocatori:
        gi.grimorio.rng = np.random.Generator(np.random.PCG64(int(rng.integers(0, 2 ** 63 - 1))))
    t.seme = int(rng.integers(0, 2 ** 63 - 1))
    if hasattr(t, "_versione"):
        t._versione += 1


def installa():
    """Nel processo: la foglia del pezzo 1 come valutazione «carte» e le determinizzazioni del pezzo 2."""
    import guarda_avanti as G
    import valuta as V
    V._MODELLI["carte"] = FogliaCarte()
    G.nascondi = nascondi_ev


def lavoro(arg):
    """Una partita di prova: (lavoro di guarda_avanti, mondo w, W, pesi della mano)."""
    base, w, W, pesi = arg
    _STATO.update(w=w, W=W, pesi=pesi)
    import guarda_avanti as G
    return G._lavoro(base)


# ---------------------------------------------------------------------------- la ricerca
def cerca(d, pool=None, pesi=None, w0=W0, giri=GIRI, log=lambda *a: None):
    """IS-MCTS al punto d (un punto di confronto_log). -> dict(candidate, valori, n_mondi, vera, migliore, scarto, p) o raise Saltato."""
    import confronto_log as CL
    import guarda_avanti as G
    import simula as S
    installa()
    turni = 1 if d["tipo"] in ("agisci", "attacca") else 2
    # 1. le candidate e il prefisso del nastro: il CercatoreLog con una prova per candidata (serve solo per arrivare al punto e codificarle)
    esito, ctx = CL.al_punto(d, prove=1, pool=None, turni=turni, valuta="carte")
    if not esito.get("prefisso") and esito.get("punti") is None:
        raise CL.Saltato("una sola candidata")
    a, b, kw = ctx
    codici = esito["codici"]; nomi = esito["candidate"]; vera = esito["autore"]
    kw = {**kw, "turni": turni, "valuta": "carte"}
    vive = list(range(len(codici)))
    valori = {j: [] for j in vive}
    mondi_usati = []
    for giro in range(giri):
        nuovi = [int(x) for x in np.random.default_rng([d["seme"], 8907, giro]).integers(0, 2 ** 63 - 1, size=w0)]
        Wtot = w0 * giri
        lavori = []
        for j in vive:
            for wi, m in enumerate(nuovi):
                lavori.append(((a, b, d["seme"], esito["prefisso"], d["io"], d["tipo"], codici[j], m, False, kw), giro * w0 + wi, Wtot, pesi))
        es = pool.map(lavoro, lavori, chunksize=1) if pool else [lavoro(x) for x in lavori]
        for idx, (j) in enumerate(vive):
            valori[j] += es[idx * w0:(idx + 1) * w0]
        mondi_usati += nuovi
        if giro < giri - 1 and len(vive) > 2:
            media = {j: float(np.mean(valori[j])) for j in vive}
            ordine = sorted(vive, key=lambda j: -media[j])
            tieni = ordine[:max(2, (len(vive) + 1) // 2)]
            if vera not in tieni:
                tieni.append(vera)
            vive = tieni
        log(f"    giro {giro + 1}: {len(vive)} candidate vive")
    # la migliore fra quelle con tutti i mondi; il confronto con la vera sui mondi in comune (tutti, la vera c'e' sempre)
    n = len(valori[vera])
    piene = [j for j in valori if len(valori[j]) == n]
    media = {j: 100 * float(np.mean(valori[j])) for j in valori}
    migliore = max(piene, key=lambda j: (media[j], j == vera))
    dv = np.array(valori[vera]); dm = np.array(valori[migliore])
    scarto = float(100 * (dv - dm).mean())
    piu, meno = int((dm > dv + 1e-9).sum()), int((dv > dm + 1e-9).sum())
    pval = CL.segni(piu, meno)
    return dict(gid=d["gid"], k=d["k"], tipo=d["tipo"], turno=d.get("turno"), candidate=nomi, valori={str(j): round(media[j], 2) for j in media},
                mondi={str(j): len(valori[j]) for j in valori}, vera=vera, migliore=migliore, scarto=round(scarto, 2), p=round(pval, 4),
                meglio=bool(migliore != vera and -scarto >= SOGLIA and pval <= P_MAX))


def pesi_mano(d):
    """I pesi per nome delle carte nella sua mano al punto d, dal pezzo 2 (None se la partita non e' nei log dell'analizzatore)."""
    try:
        import mano_avversaria as MA
        tutte = _TUTTE.get("t") or _TUTTE.setdefault("t", MA.partite())
        mid = _match_di(d["gid"])
        p = next((x for x in tutte if x["id"] == mid), None)
        if p is None:
            return None
        T = d.get("turno") or 1
        pool = MA.pool_empirico(tutte)
        import collections
        nf = collections.Counter((x["formato"], x["set"] if x["formato"] == "limited" else "") for x in tutte)
        peso, rest, _ = MA.credenza(p, T + 1, pool, nf, json.loads((QUI / "mano_avversaria.misure.json").read_text(encoding="utf8"))
                                    .get("Limited", {}).get("pi", [None])[0] if (QUI / "mano_avversaria.misure.json").exists() else None)
        import testi_carte as TC
        out = {}
        s = sum(peso.values()) or 1
        n = len(peso) or 1
        for g, w in peso.items():
            nm = TC.nome(g)
            if nm:
                out[nm] = max(0.05, w / s * n)       # 1 = la media; mai zero (una carta che il pezzo 2 non ha resta possibile)
        return out
    except Exception:       # noqa: BLE001 - senza pesi la mano si pesca a caso come prima
        return None


_TUTTE = {}


def _match_di(gid):
    """Il matchId di un punto: gid e' il matchId (i punti dai log, dal 19 nov 2026) o la cartella di Espansioni/FRA/Partite (il primo pilota)."""
    f = ROOT / "Espansioni" / "FRA" / "Partite" / gid / "partita.json"
    try:
        return json.loads(f.read_text(encoding="utf8")).get("matchId") or gid
    except (OSError, ValueError):
        return gid


def arena_aperta():
    import piattaforma
    return piattaforma.arena_aperta()


def bassa_priorita():
    try:
        import piattaforma
        piattaforma.priorita_bassa()
    except Exception:       # noqa: BLE001
        pass


def _init_worker():
    bassa_priorita()
    installa()


def punti_partita(x):
    """I punti di scelta di una partita dell'analizzatore (x di DA.righe) dal suo log, per qualunque utente (19 nov 2026: prima solo dalle cartelle di
    Espansioni/FRA/Partite, che esistono solo nell'app di Autore). -> (punti, saltati) come confronto_log.punti_seq; Saltato senza log o senza mazzo."""
    import confronto_log as CL
    import riscontro as R
    import simula as S
    import dati_analizzatore as DA
    import replay_log as RL
    righe = RL.righe_partita(x["partita"], (DA._MANA.get(x["partita"]) or {}).get("dove"))
    if not righe:
        raise CL.Saltato("il log della partita non si trova")
    try:
        mazzo, side = S.mazzo_da_testo(chr(10).join(righe), x["partita"])
    except RuntimeError as e:
        raise CL.Saltato(f"mazzo non letto: {str(e)[:50]}")
    st = R.Stato()
    seq = []
    for riga in righe:
        seq.extend(R.messaggi_di(st, riga))
    return CL.punti_seq(seq, x["partita"], {"mazzo": mazzo, "sideboard": side})


def leggi_uscita():
    """Il registro dell'IS-MCTS (Log_Arena/ismcts.json); la prima volta prende il pilota del 19 nov 2026 se c'e'."""
    for f in (USCITA, VECCHIO):
        try:
            d = json.loads(f.read_text(encoding="utf8"))
            d.setdefault("punti", []); d.setdefault("non_stimabili", {}); d.setdefault("partite", [])
            return d
        except (OSError, ValueError):
            continue
    return {"punti": [], "non_stimabili": {}, "partite": []}


def giro(processi=4, max_partite=None, log=print, solo=None):
    """L'IS-MCTS sulle partite limited dei log, dalla piu' recente, una partita alla volta e mai con Arena aperta (si ferma e riprende al giro dopo).
    Lo lancia la finestra grande in sottofondo a priorita' bassa, come la cottura delle carte; una copia sola (Log_Arena/ismcts.lock)."""
    import piattaforma
    import dati_analizzatore as DA
    import confronto_log as CL
    from multiprocessing import Pool
    USCITA.parent.mkdir(parents=True, exist_ok=True)
    blocco = open(USCITA.with_suffix(".lock"), "w")
    if not piattaforma.blocca(blocco):
        return None         # ce n'e' gia' uno
    bassa_priorita()
    if arena_aperta():
        log("Arena e' aperta: l'IS-MCTS non parte"); return None
    fatto = leggi_uscita()
    fatte = set(fatto["partite"]) | {_match_di(r["gid"]) for r in fatto["punti"]}
    partite = [x for x in reversed(DA.righe()) if x.get("tipo") == "Limited" and x["partita"] not in fatte and (solo is None or x["partita"] in solo)]
    if max_partite:
        partite = partite[:max_partite]
    if not partite:
        log("nessuna partita nuova"); return fatto
    t0 = time.time()
    with Pool(processi, initializer=_init_worker) as pool:
        for x in partite:
            if arena_aperta():
                log("Arena aperta: mi fermo (riprendo al prossimo giro)"); break
            try:
                punti, _s = punti_partita(x)
            except Exception as e:      # noqa: BLE001 - una partita che il motore non sa rifare: non stimabile, mai inventata
                motivo = f"partita: {str(e)[:70] or type(e).__name__}"
                fatto["non_stimabili"][motivo] = fatto["non_stimabili"].get(motivo, 0) + 1
                punti = []
            for d in punti:
                if arena_aperta():
                    break
                try:
                    r = cerca(d, pool=pool, pesi=pesi_mano(d))
                    fatto["punti"].append(r)
                except Exception as e:      # noqa: BLE001
                    motivo = str(e)[:80] or type(e).__name__
                    if not isinstance(e, (CL.Saltato, CL.Fermo)):
                        motivo = f"{type(e).__name__}: {str(e)[:60]}"
                    fatto["non_stimabili"][motivo] = fatto["non_stimabili"].get(motivo, 0) + 1
            else:
                fatto["partite"].append(x["partita"])
            USCITA.write_text(json.dumps(fatto, indent=1, ensure_ascii=False), encoding="utf8")
            log(f"  {x['partita'][:8]}: {len(punti)} punti ({time.time() - t0:.0f} s)")
    return fatto


_LANCI = {}


def stesso_turno(r):
    """True se la «migliore» di un punto «agisci» e' una magia che hai lanciato anche tu in quel turno (la stessa linea in un altro ordine: il pilota
    confronta solo la prima azione, poi gioca il Semplice). Dai lanci di mana_aperto della partita."""
    if r["tipo"] != "agisci" or not str(r["candidate"][r["migliore"]]).startswith("lancia "):
        return False
    nome = r["candidate"][r["migliore"]][len("lancia "):]
    mid = _match_di(r["gid"])
    if mid not in _LANCI:
        try:
            sys.path.insert(0, str(ROOT / "Companion")); import percorsi  # noqa: F401
            sys.path.insert(0, str(ROOT / "Companion" / "App" / "Schede" / "Performance"))
            import dati_analizzatore as DA
            import testi_carte as TC
            if not DA._MANA:
                DA.righe()
            x = next((y for y in DA.righe() if y["partita"] == mid), None)
            d = DA._MANA.get(mid) or {}
            seat = (x or {}).get("seat")
            _LANCI[mid] = {(a[0], (TC.nome(a[3]) or "").split(" // ")[0]) for a in d.get("azioni") or [] if a[1] == seat and a[2] == "magia"}
        except Exception:       # noqa: BLE001
            _LANCI[mid] = set()
    return (r.get("turno"), nome.split(" // ")[0]) in _LANCI[mid]


def affidabilita(fatto):
    """Il controllo del pezzo 3: il valore della tua mossa vera (P alla fine del suo turno dopo) contro il risultato vero della partita.
    -> dict(n, auc, log_loss, log_loss_50, per fascia [(fascia, n, valore medio, vinte)]) o None."""
    sys.path.insert(0, str(ROOT / "Companion" / "App" / "Schede" / "Performance"))
    import dati_analizzatore as DA
    sys.path.insert(0, str(QUI)); import misura_p as MP
    vinta = {x["partita"]: x["vinta"] for x in DA.righe() if x.get("vinta") is not None}
    v, y = [], []
    for r in fatto.get("punti") or []:
        mid = _match_di(r["gid"])
        if mid in vinta:
            v.append(min(0.99, max(0.01, r["valori"][str(r["vera"])] / 100))); y.append(1.0 if vinta[mid] else 0.0)
    if len(v) < 20:
        return None
    m = MP.misure(v, y)
    return dict(n=len(v), auc=m["auc"], log_loss=m["log_loss"], log_loss_50=0.6931, calibrazione=MP.calibrazione(v, y))


def scrivi_nota(fatto):
    P = fatto["punti"]
    for x in P:
        x["altro_ordine"] = bool(x["meglio"] and stesso_turno(x))
    meglio = [x for x in P if x["meglio"] and not x["altro_ordine"]]
    L = ["# Il pezzo 3: IS-MCTS sul motore di partita (pilota sui limited di FRA)", "",
         "Generato da `py -I -X utf8 Motore_EV/ismcts.py --pilota` (sessione Magic 22). Ogni punto: le candidate del motore piu' la tua mossa, "
         f"giocate negli stessi mondi (dimezzamenti: {W0} mondi a giro, {GIRI} giri), fino alla fine del suo turno dopo, foglia del pezzo 1. "
         f"«C'era di meglio» se la migliore supera la tua di {SOGLIA:.0f} punti di P con il test dei segni sotto {P_MAX}.", "",
         f"Punti stimati: {len(P)}; non stimabili: {sum(fatto.get('non_stimabili', {}).values())}; «c'era di meglio»: {len(meglio)} "
         f"({100 * len(meglio) / max(len(P), 1):.0f}%), piu' {sum(1 for x in P if x.get('altro_ordine'))} che erano la tua stessa linea in un altro ordine "
         f"(la magia «migliore» l'hai lanciata anche tu in quel turno: non contano); la tua mossa era la migliore in {sum(1 for x in P if x['vera'] == x['migliore'])}.", "",
         "Limiti: nei punti «agisci» si confronta la prima azione della prima fase principale e il resto del turno lo gioca il Semplice; dopo la "
         "scelta giocano due Semplice; un valore 0 o 100 vuol dire che la partita di prova e' finita prima dell'orizzonte in tutti i mondi (da "
         "guardare: puo' essere un difetto del motore). Sono scelte da guardare nel replayer, non sentenze.", "",
         "## Perche' un punto non e' stimabile", ""]
    af = affidabilita(fatto)
    if af:
        L[-2:-2] = ["## Il controllo: il valore della tua mossa vera contro come e' finita la partita", "",
                    f"{af['n']} punti: AUC {af['auc']}, log-loss {af['log_loss']} (il 50% fisso {af['log_loss_50']}). Per fascia (fascia, punti, valore medio, "
                    "vinte): " + "; ".join(f"{a} {b} {c}/{d}" for a, b, c, d in af["calibrazione"]) + ".", ""]
    L += [f"- {k}: {v}" for k, v in sorted(fatto.get("non_stimabili", {}).items(), key=lambda z: -z[1])[:20]]
    L += ["", "## Le scelte «c'era di meglio» da guardare nel replayer (dalla piu' grande)", "", "| partita | turno | tipo | la tua | P | la migliore | P | scarto | p |", "|---|---|---|---|---|---|---|---|---|"]
    for x in sorted(meglio, key=lambda z: z["scarto"])[:10]:
        L.append(f"| {x['gid']} | {x.get('turno')} | {x['tipo']} | {x['candidate'][x['vera']]} | {x['valori'][str(x['vera'])]} | "
                 f"{x['candidate'][x['migliore']]} | {x['valori'][str(x['migliore'])]} | {x['scarto']} | {x['p']} |")
    NOTA.write_text("\n".join(L) + "\n", encoding="utf8")


def prova():
    ok = tot = 0

    def chk(c, m):
        nonlocal ok, tot
        tot += 1; ok += bool(c); print(("OK   " if c else "ROSSO") + " " + m, flush=True)
    # 1. la stratificazione: in W mondi la prossima pescata copre il grimorio in modo uniforme
    class Ogg:
        def __init__(self, c): self.carta = c; self.fisica = c

    class Carta:
        def __init__(self, n, nome): self.n = n; self.nome = nome

    class Zona:
        def __init__(self, cc): self.carte = [Ogg(c) for c in cc]; self.rng = None

    class Gioc:
        def __init__(self, gr, mano): self.grimorio = Zona(gr); self.mano = [Ogg(c) for c in mano]

    class Tav:
        pass
    W = 8; prime = []
    for w in range(W):
        t = Tav(); t.giocatori = [Gioc([Carta(k, f"c{k}") for k in range(8)], []), Gioc([Carta(100 + k, "X" if k < 2 else "Y") for k in range(10)], [])]
        _STATO.update(w=w, W=W, pesi={})
        nascondi_ev(t, 0, np.random.default_rng(w))
        prime.append(t.giocatori[0].grimorio.carte[0].carta.n)
    chk(sorted(prime) == list(range(8)), f"quasi-Monte Carlo: in 8 mondi le 8 carte del grimorio sono ognuna una volta la prossima pescata ({sorted(prime)})")
    # negativa: senza stratificazione (W enorme: sempre la stessa fascia) le prime non coprono
    prime2 = []
    for w in range(W):
        t = Tav(); t.giocatori = [Gioc([Carta(k, f"c{k}") for k in range(8)], []), Gioc([], [])]
        _STATO.update(w=0, W=1, pesi={})
        nascondi_ev(t, 0, np.random.default_rng(w))
        prime2.append(t.giocatori[0].grimorio.carte[0].carta.n)
    chk(len(set(prime2)) == 1, "negativa: con un mondo solo per strato la prossima pescata e' sempre la stessa")
    # 2. la mano coi pesi: X pesata 50 volte Y finisce in mano molto piu' spesso
    nX = 0
    for s in range(300):
        t = Tav(); t.giocatori = [Gioc([], []), Gioc([Carta(100 + k, "X" if k < 2 else "Y") for k in range(8)], [Carta(200, "Y"), Carta(201, "Y")])]
        _STATO.update(w=0, W=1, pesi={"X": 50.0, "Y": 1.0})
        nascondi_ev(t, 0, np.random.default_rng(s))
        nX += sum(1 for o in t.giocatori[1].mano if o.carta.nome == "X")
    chk(nX / 300 > 1.5, f"la mano dal pezzo 2: la carta pesata 50 volte e' in mano {nX / 300:.2f} copie su 2 (a caso: 0,4)")
    nX0 = 0
    for s in range(300):
        t = Tav(); t.giocatori = [Gioc([], []), Gioc([Carta(100 + k, "X" if k < 2 else "Y") for k in range(8)], [Carta(200, "Y"), Carta(201, "Y")])]
        _STATO.update(w=0, W=1, pesi={})
        nascondi_ev(t, 0, np.random.default_rng(s))
        nX0 += sum(1 for o in t.giocatori[1].mano if o.carta.nome == "X")
    chk(0.2 < nX0 / 300 < 0.7, f"negativa: senza pesi la mano e' a caso ({nX0 / 300:.2f} copie, atteso 0,4)")
    # 3. un punto vero, coi punti di scelta letti dal log della partita (come nell'app di chiunque, 19 nov 2026)
    import dati_analizzatore as DA
    lim = [x for x in DA.righe() if x.get("tipo") == "Limited"]
    chk(len(lim) > 0, f"partite limited nei log: {len(lim)}")
    fatto, punti = None, []
    for x in reversed(lim[-12:]):
        try:
            punti, _s = punti_partita(x)
        except Exception:       # noqa: BLE001
            continue
        if punti:
            break
    chk(len(punti) > 3, f"punti di scelta dal log di una partita: {len(punti)}")
    rng = np.random.default_rng(3)
    for j in rng.permutation(len(punti))[:15]:
        try:
            fatto = cerca(punti[int(j)], pool=None, pesi=None, w0=2, giri=2); break
        except Exception:       # noqa: BLE001
            continue
    chk(fatto is not None and fatto["vera"] in range(len(fatto["candidate"])) and all(0 <= v <= 100 for v in fatto["valori"].values()),
        f"IS-MCTS su un punto vero: {fatto and len(fatto['candidate'])} candidate, scarto {fatto and fatto['scarto']}")
    chk(fatto is not None and fatto["mondi"][str(fatto["vera"])] == max(fatto["mondi"].values()), "la mossa vera non esce mai dai dimezzamenti")
    try:
        punti_partita(dict(partita="00000000-nessuna", seat=1))
        chk(False, "negativa: una partita senza log")
    except Exception as e:      # noqa: BLE001
        chk("log" in str(e), f"negativa: una partita senza log non ha punti ({e})")
    print(f"{ok}/{tot}")
    return ok == tot


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--pilota", nargs="?", const=60, type=int); ap.add_argument("--processi", type=int, default=4)
    ap.add_argument("--giro", action="store_true")
    ap.add_argument("--prova", action="store_true")
    a = ap.parse_args()
    if a.pilota:
        f = giro(a.processi, a.pilota)
        if f:
            scrivi_nota(f)
    if a.giro:
        giro(a.processi)
    if a.prova:
        sys.exit(0 if prova() else 1)
