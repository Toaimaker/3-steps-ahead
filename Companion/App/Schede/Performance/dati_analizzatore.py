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
import re  # noqa: E402

import account  # noqa: E402

SITUAZIONI = account.lega(globals(), "SITUAZIONI", "performance_situazioni.json")     # Log_Arena/performance_situazioni.json: le situazioni salvate
SEGNALIBRI = account.lega(globals(), "SEGNALIBRI", "performance_segnalibri.json")     # gli spot segnati nel replayer (12 nov 2026)
CARTE_SCELTE = account.lega(globals(), "CARTE_SCELTE", "performance_cards.json")      # le righe di Cards che vuoi vedere (13 nov 2026)
NUMERI_SCELTI = account.lega(globals(), "NUMERI_SCELTI", "performance_numeri.json")    # i sei numeri in cima a Performance (13 nov 2026)
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
       ("lui_passa_aperto", "Opponent passed the turn with 2+ lands untapped"),
       # i combattimenti (13 nov 2026, per le ricerche preimpostate di Spots): dai momenti di mana_aperto, VERSIONE 12
       ("io_blocca", "Opponent attacked and you blocked"), ("io_difende", "You defended more than you attacked"),
       ("io_tutto", "You attacked with everything (2+ creatures could attack)"),
       ("io_tutto_aperto", "You attacked with everything into 2+ untapped lands")]
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


_INTERI = {}


def nome_intero(n):
    """Il nome intero di una carta a due facce («Unholy Annex» -> «Unholy Annex // Ritual Chamber»), come lo scrivono le carte viste e le immagini cotte; le
    altre restano come sono. Le azioni di mana_aperto danno il nome della faccia davanti (13 nov 2026: nella cartella Cards Unholy Annex senza immagine)."""
    if not _INTERI:
        for k in _tabella():
            if " // " in k:
                for faccia in k.split(" // "):       # anche la faccia dietro («Ritual Chamber»): il replay scrive la faccia che si vede
                    _INTERI.setdefault(faccia.strip(), k)
        _INTERI.setdefault("", "")
    return _INTERI.get(n, n)


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


def creature_in_mano(tenuta):
    """Le creature nella mano tenuta: «0», «1», «2», «3+»; None se la mano non si conosce (13 nov 2026, Autore: «senza creature ... tutte e tre»)."""
    if not tenuta:
        return None
    n = sum(q for nm, q in tenuta.items() if (c := _carta(nm)) and "Creature" in (c.get("tipo") or "").split(" // ")[0])
    return str(n) if n < 3 else "3+"


def suo_mulligan(match_id, seat):
    """I mulligan dell'avversario: le carte che ha in mano all'inizio del primo turno (mana_aperto, la foto mano0) contro 7: al primo turno chi comincia non
    ha ancora pescato e chi non comincia non ha ancora giocato. «0», «1», «2+»; None senza la foto. Sui log del 13 nov: 51 partite su 477 con un suo mulligan."""
    m = (_MANA.get(match_id) or {}).get("mano0")
    if not m or seat not in (1, 2):
        return None
    n = (m.get("n") or [None, None])[2 - seat]
    if n is None or n > 7:
        return None
    return "0" if n == 7 else "1" if n == 6 else "2+"


def prima_creatura(match_id, seat, inizia):
    """Il tuo turno (1, 2, ...) della prima creatura che hai lanciato; 0 se non ne hai lanciate; None se la partita non ha le azioni (mana_aperto VERSIONE 12)
    o non si sa chi ha cominciato. Il turno di Arena conta i due giocatori: se hai cominciato tu i tuoi sono i dispari."""
    d = _MANA.get(match_id) or {}
    if "azioni" not in d or seat not in (1, 2) or inizia is None:
        return None
    for t, chi, cosa, _g, tipi in d["azioni"]:
        if chi == seat and cosa == "magia" and "C" in (tipi or ""):
            return (t + 1) // 2 if inizia else t // 2
    return 0


def magie_in_mano(tenuta, tipo):
    """Le magie di un tipo («Instant», «Sorcery») nella mano tenuta: «0», «1», «2+»; None se la mano non si conosce."""
    if not tenuta:
        return None
    n = sum(q for nm, q in tenuta.items() if (c := _carta(nm)) and tipo in (t_ := (c.get("tipo") or "").split(" // ")[0]) and "Land" not in t_)
    return str(n) if n < 2 else "2+"


TURNI_FILTRO = 5        # i filtri turno per turno: i primi 5 turni di ognuno
NOMI_TIPO = {"C": "Creature", "I": "Instant", "S": "Sorcery", "E": "Enchantment", "A": "Artifact", "P": "Planeswalker", "B": "Battle"}
ORDINE_TIPI = ("Creature", "Instant", "Sorcery", "Enchantment", "Artifact", "Planeswalker", "Battle", "Nothing")


ORDINE_ATT = ("No attack", "1 creature", "2 creatures", "3+ creatures")
ORDINE_DIF = ("Not attacked", "Blocked", "No block")
ORDINE_APERTE = ("No attack", "0 untapped lands", "1 untapped land", "2+ untapped lands")
ORDINE_PESCATE = ("0 draws", "1 draw", "2 draws", "3+ draws")
ORDINE_PESCATE_X = ("0 draws", "1 draw", "2+ draws")
ORDINE_EXTRA = ("No extra draw", "1+ extra in one turn", "2+ extra in one turn", "3+ extra in one turn")


def per_turno(match_id, seat, inizia, turni):
    """Turno per turno, per te («io») e per l'avversario («lui»), nei primi TURNI_FILTRO turni di ognuno (13 nov 2026, Autore: «bisogna estrarre dai
    replay delle azioni che possono essere trasformate in filtri», poi «ci mancano le giocate nel turno avversario, le sue nei nostri turni, le fasi di attacco
    di entrambi e di difesa di entrambi»):
      «{chi}{n}»   cosa ha lanciato nel suo turno n (i tipi, o «Nothing»);
      «{chi}x{n}»  cosa ha lanciato nel turno n dell'altro;
      «a{chi}{n}»  il suo attacco nel suo turno n: «No attack», «1 creature», «2 creatures», «3+ creatures»;
      «d{chi}{n}»  la sua difesa nel turno n dell'altro: «Not attacked», «Blocked», «No block»;
      «m{chi}{n}»  le terre stappate di chi difende quando lui attacca nel suo turno n (stesso giorno: «aggiungiamo anche in attacco se ci sono situazioni di
                   mana stappato vs chi attacca»): «No attack», «0 untapped lands», «1 untapped land», «2+ untapped lands»;
      «p{chi}{n}»  le carte che ha pescato nel suo turno n, la pescata del turno compresa: «0 draws» ... «3+ draws» (13 nov 2026, Autore: «nei filtri di
                   you e opponent aggiungiamo anche le pescate nel proprio e nel turno avversario più alcuni filtri generali che indicano che sono avvenute 1, 2
                   o più pescate in almeno uno dei turni»);
      «p{chi}x{n}» le carte che ha pescato nel turno n dell'altro: «0 draws», «1 draw», «2+ draws»;
      «pe{chi}»    le pescate extra (oltre quella del suo turno; nel turno dell'altro tutte) nel turno che ne ha di piu' fra quelli dei filtri: una lista, come le
                   soglie («2+ extra in one turn» e' anche «1+ extra in one turn»), o «No extra draw». Le pescate ci sono da mana_aperto VERSIONE 13.
    Un turno che la partita non ha raggiunto non c'e'. Il turno n di chi comincia e' il turno 2n-1 di Arena, quello dell'altro il 2n: in tutti e due i casi
    n = (t + 1) // 2. Dalle azioni e dai combattimenti di mana_aperto (VERSIONE 12); {} se mancano o non si sa chi ha cominciato."""
    d = _MANA.get(match_id) or {}
    if "azioni" not in d or seat not in (1, 2) or inizia is None:
        return {}
    primo = "io" if inizia else "lui"
    altro = {"io": "lui", "lui": "io"}
    di_turno = lambda t: primo if t % 2 == 1 else altro[primo]
    out = {}
    for t in range(1, 2 * TURNI_FILTRO + 1):
        if not turni or t > turni:
            break
        chi, n = di_turno(t), (t + 1) // 2
        out[f"{chi}{n}"] = []
        out[f"{altro[chi]}x{n}"] = []
        out[f"a{chi}{n}"] = "No attack"
        out[f"d{altro[chi]}{n}"] = "Not attacked"
        out[f"m{chi}{n}"] = "No attack"
    pescate = collections.Counter()
    ci_sono = False
    for t, s_, cosa, _g, _tipi in d["azioni"]:
        if cosa == "pesca":
            ci_sono = True
            pescate[("io" if s_ == seat else "lui", t)] += 1
    if ci_sono:
        extra = {"io": 0, "lui": 0}
        for t in range(1, 2 * TURNI_FILTRO + 1):
            if not turni or t > turni:
                break
            chi, n = di_turno(t), (t + 1) // 2
            mie, sue = pescate[(chi, t)], pescate[(altro[chi], t)]
            out[f"p{chi}{n}"] = ORDINE_PESCATE[min(mie, 3)]
            out[f"p{altro[chi]}x{n}"] = ORDINE_PESCATE_X[min(sue, 2)]
            normale = 0 if (chi == primo and t == 1) else 1        # chi comincia non pesca al suo primo turno (103.8a)
            extra[chi] = max(extra[chi], mie - normale)
            extra[altro[chi]] = max(extra[altro[chi]], sue)
        for chi, e in extra.items():
            out[f"pe{chi}"] = tuple(ORDINE_EXTRA[i] for i in range(1, min(e, 3) + 1)) or (ORDINE_EXTRA[0],)
    for t, s_, cosa, g_, tipi in d["azioni"]:
        if cosa != "magia":
            continue
        chi = "io" if s_ == seat else "lui"
        k = f"{chi}{(t + 1) // 2}" if di_turno(t) == chi else f"{chi}x{(t + 1) // 2}"
        if k in out:
            # i tipi di ogni magia lanciata, ripetuti: due istantanei nel turno sono «Instant», «Instant» (13 nov 2026, Autore: «da advanced filters togli
            # per tipo carta 1-2-3, se faccio t1 creature e t2 creature è ovvio che sono state castate 2 creature - se faccio t3 istant - istant ovviamente ho
            # lanciato 2 istant / complichiamo le cose ma rendiamole semplici»; prima c'erano anche le voci col costo, «Instant · 1»)
            out[k].extend(NOMI_TIPO[c] for c in dict.fromkeys(tipi or "") if c in NOMI_TIPO)
    for kind, t, att, _f, info in d.get("momenti") or []:
        if kind != "comb" or not info or not info.get("att"):
            continue
        chi, n = ("io" if att == seat else "lui"), (t + 1) // 2
        if f"a{chi}{n}" in out:
            na = len(info["att"])
            out[f"a{chi}{n}"] = "1 creature" if na == 1 else "2 creatures" if na == 2 else "3+ creatures"
            out[f"d{altro[chi]}{n}"] = "Blocked" if info.get("blocchi") else "No block"
            ap = info.get("aperte")
            if ap is None:          # un combattimento letto prima della VERSIONE 12: le terre di chi difende non si sanno
                out.pop(f"m{chi}{n}", None)
            else:
                out[f"m{chi}{n}"] = "0 untapped lands" if ap == 0 else "1 untapped land" if ap == 1 else "2+ untapped lands"
    return {k: [v] if isinstance(v, str) else list(v) if isinstance(v, tuple) else (sorted(v, key=ordine_lancio) if v else ["Nothing"])
            for k, v in out.items()}       # le magie del turno: una lista coi tipi ripetuti, in ordine; «Nothing» se niente


def ordine_lancio(v):
    """L'ordine delle voci di un turno: i tipi come ORDINE_TIPI (ripetuti una volta per magia: «Instant», «Instant»). Una voce di prima col costo
    («Creature · 2», fino al 13 nov 2026) va dopo il suo tipo."""
    tipo, _s, costo = v.partition(" · ")
    return (ORDINE_TIPI.index(tipo) if tipo in ORDINE_TIPI else 99, int(costo) if costo.isdigit() else -1)


def multipla(k):
    """Le chiavi a scelta multipla: le giocate turno per turno («t_io2», «t_luix3»). Il filtro e' una lista di voci, e una partita passa se in quel turno ha
    tutte le voci scelte, ripetizioni comprese (una creatura e due istantanei)."""
    return bool(re.fullmatch(r"t_(io|lui)x?\d+", k))


ENTRO = tuple(range(3, 13))         # «la partita finita entro il tuo turno N»
SENZA = tuple(range(1, 7))          # «nessuna creatura lanciata entro il tuo turno N»


SITUA_TURNI = (3, 5, 7)         # i turni delle foto di fine turno per vite e creature
TERRE_TURNI = (3, 4, 5)         # le terre in curva entro il tuo turno N
ORDINE_SITUA = {"terre": ("On curve", "1 short", "2+ short"), "vita": ("16+", "11-15", "6-10", "1-5", "0 or less"),
                "vita_t": ("Ahead", "Even", "Behind"), "crea_t": ("More creatures", "Same", "Fewer creatures"),
                "rim": ("0", "1", "2", "3+"), "si": ("Yes", "No"), "magie": ("0-4", "5-9", "10-14", "15+")}


def situazioni_replay(match_id, seat, inizia, turni):
    """I filtri situazionali letti dai replay (13 nov 2026, Autore: «Aggiungi tutti i filtri situazionali per le spot che potrebbero ancora mancare sii
    minuzioso e dettagliato parti dai replay per aggiungere le migliori features di filtri»), per te («io») e per l'avversario («lui»), dalle azioni, dai
    momenti e dalle foto di fine turno di mana_aperto (VERSIONE 12). {chiave: valore}; una chiave manca quando non si sa (la partita e' finita prima, mancano
    i dati). Le chiavi:
      terre_{chi}{N}   le terre giocate entro il suo turno N: «On curve» (N), «1 short», «2+ short»;
      vita_{chi}       la sua vita piu' bassa nelle foto di fine turno e all'ultimo stato: «16+» ... «0 or less»;
      vita_t{N}        a fine del tuo turno N: tu «Ahead», «Even» (2 vite o meno di scarto), «Behind»;
      crea_t{N}        a fine del tuo turno N: le tue creature in campo contro le sue, «More creatures», «Same», «Fewer creatures»;
      rim_{chi}        i permanenti dell'altro che le sue magie e abilita' hanno tolto dal campo (come colpiti_di): «0», «1», «2», «3+»;
      wipe_{chi}       una sua magia o abilita' ha tolto 3+ permanenti (un board wipe): «Yes», «No»;
      counter_{chi}    ha bersagliato una magia dell'altro in pila (una contromagia): «Yes», «No»;
      cim_{chi}        ha bersagliato una carta in un cimitero (rianimare, riprendere): «Yes», «No»;
      magie_{chi}      le magie lanciate nella partita: «0-4», «5-9», «10-14», «15+»."""
    d = _MANA.get(match_id) or {}
    if "azioni" not in d or seat not in (1, 2) or inizia is None:
        return {}
    out = {}
    altro_s = 2 if seat == 1 else 1
    posto = {"io": seat, "lui": altro_s}
    comincia = {"io": inizia, "lui": not inizia}
    t_di = lambda chi, n: 2 * n - 1 if comincia[chi] else 2 * n       # il turno di Arena del suo turno n
    for chi in ("io", "lui"):
        # le terre in curva
        for n in TERRE_TURNI:
            if turni and t_di(chi, n) <= turni:
                k = sum(1 for t, s_, cosa, _g, _tp in d["azioni"] if cosa == "terra" and s_ == posto[chi] and t <= t_di(chi, n))
                out[f"terre_{chi}{n}"] = "On curve" if k >= n else "1 short" if k == n - 1 else "2+ short"
        # le magie lanciate
        k = sum(1 for _t, s_, cosa, _g, _tp in d["azioni"] if cosa == "magia" and s_ == posto[chi])
        out[f"magie_{chi}"] = "0-4" if k < 5 else "5-9" if k < 10 else "10-14" if k < 15 else "15+"
    # la vita piu' bassa
    foto = [f for _t, _a, f in d.get("foto") or []] + ([d["ultima"][2]] if d.get("ultima") and d["ultima"][2] else [])
    for chi in ("io", "lui"):
        vv = [f["v"][posto[chi] - 1] for f in foto if f.get("v") and f["v"][posto[chi] - 1] is not None]
        if vv:
            m = min(vv)
            out[f"vita_{chi}"] = "16+" if m >= 16 else "11-15" if m >= 11 else "6-10" if m >= 6 else "1-5" if m >= 1 else "0 or less"
    # a fine dei tuoi turni: vite e creature
    per_t = {t: f for t, _a, f in d.get("foto") or []}
    for n in SITUA_TURNI:
        f = per_t.get(t_di("io", n))
        if not f:
            continue
        v = f.get("v") or [None, None]
        if v[seat - 1] is not None and v[altro_s - 1] is not None:
            dv = v[seat - 1] - v[altro_s - 1]
            out[f"vita_t{n}"] = "Ahead" if dv > 2 else "Behind" if dv < -2 else "Even"
        c = f.get("c") or [[], []]
        mie = sum(1 for x in c[seat - 1] if len(x) > 3 and x[3] is not None)
        sue = sum(1 for x in c[altro_s - 1] if len(x) > 3 and x[3] is not None)
        out[f"crea_t{n}"] = "More creatures" if mie > sue else "Fewer creatures" if mie < sue else "Same"
    # le magie e le abilita' coi permanenti tolti, le contromagie, i bersagli nei cimiteri
    rim = {"io": 0, "lui": 0}
    for chi in ("io", "lui"):
        for k in ("wipe", "counter", "cim"):
            out[f"{k}_{chi}"] = "No"
    for kind, _t, _att, f, info in d.get("momenti") or []:
        if kind != "spell" or not info or info.get("chi") not in (1, 2):
            continue
        chi = "io" if info["chi"] == seat else "lui"
        tolti = colpiti_di(info)
        c = (f or {}).get("c") or [[], []]
        suoi = {x[5] for x in c[(altro_s if chi == "io" else seat) - 1] if len(x) > 5}
        rim[chi] += sum(1 for x in tolti if x in suoi)
        if len(tolti) >= 3:
            out[f"wipe_{chi}"] = "Yes"
        for _i, zona, proprietario, _g in info.get("fuori") or []:
            if zona == "pila" and proprietario not in (None, info["chi"]):
                out[f"counter_{chi}"] = "Yes"
            elif zona == "cim":
                out[f"cim_{chi}"] = "Yes"
    for chi in ("io", "lui"):
        out[f"rim_{chi}"] = str(rim[chi]) if rim[chi] < 3 else "3+"
    return out


SITUA_NOMI = {}
for _chi, _tu, _suo in (("io", "You", "the opponent's"), ("lui", "Opponent", "your")):
    for _n in TERRE_TURNI:
        SITUA_NOMI[f"terre_{_chi}{_n}"] = (f"{_tu} · land drops by {'your' if _chi == 'io' else 'their'} turn {_n}", "terre")
    SITUA_NOMI[f"vita_{_chi}"] = (f"{_tu} · lowest life in the game", "vita")
    SITUA_NOMI[f"rim_{_chi}"] = (f"{_tu} · {_suo} permanents removed", "rim")
    SITUA_NOMI[f"wipe_{_chi}"] = (f"{_tu} · wiped the board (3+ permanents at once)", "si")
    SITUA_NOMI[f"counter_{_chi}"] = (f"{_tu} · countered a spell", "si")
    SITUA_NOMI[f"cim_{_chi}"] = (f"{_tu} · targeted a card in a graveyard", "si")
    SITUA_NOMI[f"magie_{_chi}"] = (f"{_tu} · spells cast in the game", "magie")
for _n in SITUA_TURNI:
    SITUA_NOMI[f"vita_t{_n}"] = (f"Life at the end of your turn {_n}", "vita_t")
    SITUA_NOMI[f"crea_t{_n}"] = (f"Creatures at the end of your turn {_n}", "crea_t")


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


_TERRE = {}         # e_terra ricordata per nome: quella di mazzi_salvati ricontrolla 5 file a ogni chiamata (13 nov 2026: 0,7 s su 1,9 per rileggere)


def e_terra(n):
    if n not in _TERRE:
        import mazzi_salvati as MS
        _TERRE[n] = MS.e_terra(n)
    return _TERRE[n]


# ------------------------------------------------------------------ C1 · le terre contro il caso
# (13 nov 2026, Note/HANDOFF_Censimento_Performance.md, voce C1: «la domanda di tutti, in ogni lingua»: lo shuffler e' truccato? perdo per le terre?)
# Il test onesto e' sulle PESCATE, non sulla mano: la mano la scegli tu (mulligan) e nel Bo1 Arena la «liscia», le pescate no. Dopo le 7 carte della mano
# (le ultime viste, anche quelle messe in fondo dal mulligan) il grimorio ha D - 7 carte a caso con L - terre_delle_7 terre (le carte in fondo non si pescano
# nei primi turni): le terre pescate entro il tuo turno N seguono l'ipergeometrica. Ogni pescata conta (anche quelle delle magie: vengono dalla cima a caso).
# Limite dichiarato: scry e surveil rimettono in cima o in fondo carte gia' viste, e da li' le pescate non sono piu' del tutto a caso.
TURNI_FORTUNA = (3, 5, 7)
FORTUNA = ("Screw · bottom 5%", "Fewer than expected", "As expected", "More than expected", "Flood · top 5%")
CODA, FASCIA = 0.05, 0.25       # le code del 5% (screw, flood: fuori dalla fascia centrale del 90%) e quelle del 25% (meno, piu' del previsto)


def ipergeom(N, K, n):
    """Le probabilita' di 0..n successi in n estrazioni senza reimmissione da N con K successi."""
    if not (0 <= K <= N and 0 <= n <= N):
        return None
    tot = math.comb(N, n)
    return [math.comb(K, j) * math.comb(N - K, n - j) / tot for j in range(n + 1)]


def classe_fortuna(pmf, x):
    """La voce di FORTUNA di x terre pescate: le code del 5% prima, poi quelle del 25%; una x che sta nelle due code del 25% (poche pescate) e' «As expected»."""
    pl, ph = sum(pmf[:x + 1]), sum(pmf[x:])
    if pl <= CODA + 1e-12:
        return FORTUNA[0]
    if ph <= CODA + 1e-12:
        return FORTUNA[4]
    meno, piu = pl <= FASCIA + 1e-12, ph <= FASCIA + 1e-12
    return FORTUNA[1] if meno and not piu else FORTUNA[3] if piu and not meno else FORTUNA[2]


def mano_liscia(terre, totale, n=7, campioni=1):
    """Le terre della prima mano: campioni=1 l'ipergeometrica (il regolamento, una mano a caso), campioni=m la migliore di m mani, la piu' vicina al rapporto
    del mazzo (lo smoothing del Bo1 di Arena: nel Quick regge la migliore di 2, Motore_Partita/Misura_Smoothing_Bo1.md). Lo stesso conto di
    Motore_Partita/inizio.distribuzione_terre, rifatto qui senza numpy."""
    p = ipergeom(totale, terre, n)
    if p is None or campioni == 1:
        return p
    classi = {}
    for j in range(n + 1):
        classi.setdefault(abs(j * totale - n * terre), []).append(j)
    ordinate = [classi[d] for d in sorted(classi)]
    pc = [sum(p[j] for j in c) for c in ordinate]
    S = [sum(pc[r:]) for r in range(len(pc))] + [0.0]
    out = [0.0] * (n + 1)
    for r, c in enumerate(ordinate):
        if pc[r]:
            pr = S[r] ** campioni - S[r + 1] ** campioni
            for j in c:
                out[j] = pr * p[j] / pc[r]
    return out


def bo3_di(evento):
    e = evento or ""
    return "Traditional" in e or e.startswith(("TradDraft", "TradSealed"))


def fortuna(p, r, lista):
    """Le terre di una partita contro il caso: dict(D, L, mano0 = terre della prima mano da 7, bo3, turni={N: dict(k pescate, x terre, e attese, var, classe,
    attese_classi={voce: probabilita'})}) o None (mazzo o mano che non si sanno, partita letta prima delle pescate, una tua pescata senza nome)."""
    import condividi
    mani = p.get("mani") or []
    D = sum(lista.values()) if lista else 0
    if not mani or D < 40:
        return None
    L = sum(q for n, q in lista.items() if e_terra(n))
    sette = condividi.nomi(mani[-1]) or {}
    prima = condividi.nomi(mani[0]) or {}
    n7 = sum(sette.values())
    l7 = sum(q for n, q in sette.items() if e_terra(n))
    out = dict(D=D, L=L, mano0=sum(q for n, q in prima.items() if e_terra(n)) if sum(prima.values()) == 7 else None, bo3=bo3_di(p.get("evento")), turni={})
    az = (_MANA.get(r.get("partita")) or {}).get("azioni")
    seat, inizia, turni = p.get("seat"), r.get("inizia"), r.get("turni") or 0
    if not az or not any(a[2] == "pesca" for a in az) or seat not in (1, 2) or inizia is None or n7 != 7:
        return out
    Npop, K = D - n7, L - l7
    for N in TURNI_FORTUNA:
        fine = 2 * N - 1 if inizia else 2 * N        # il tuo turno N nel conto dei turni di Arena
        if turni < fine:
            continue
        pesc = [g for t, s_, cosa, g, _tp in az if cosa == "pesca" and s_ == seat and t <= fine]
        nomi_ = [nome_grp(g) if g not in SENZA_FACCIA else None for g in pesc]
        if any(not n for n in nomi_):
            continue
        k, x = len(nomi_), sum(1 for n in nomi_ if e_terra(n))
        pmf = ipergeom(Npop, K, k)
        if pmf is None:
            continue
        att = {v: 0.0 for v in FORTUNA}
        for j, pj in enumerate(pmf):
            att[classe_fortuna(pmf, j)] += pj
        q = K / Npop if Npop else 0
        out["turni"][N] = dict(k=k, x=x, e=k * q, var=k * q * (1 - q) * ((Npop - k) / (Npop - 1) if Npop > 1 else 0), classe=classe_fortuna(pmf, x), attese_classi=att)
    return out


def chi2_p(oss, att, minimo=5.0):
    """Il p del chi quadro fra conte osservate e attese, le code con meno di «minimo» attese unite alla vicina; la coda della chi quadro con
    l'approssimazione di Wilson-Hilferty (senza scipy: basta a dire «regge» o «no»)."""
    o, a = [float(x) for x in oss], [float(x) for x in att]
    while len(a) > 2 and a[0] < minimo:       # (o[1] += o.pop(0) sommerebbe alla casella sbagliata: il pop sposta gli indici dopo la lettura)
        vo, va = o.pop(0), a.pop(0)
        o[0] += vo; a[0] += va
    while len(a) > 2 and a[-1] < minimo:
        vo, va = o.pop(), a.pop()
        o[-1] += vo; a[-1] += va
    x2 = sum((oi - ai) ** 2 / ai for oi, ai in zip(o, a) if ai > 0)
    k = len(a) - 1
    if k < 1:
        return 1.0
    z = ((x2 / k) ** (1 / 3) - (1 - 2 / (9 * k))) / math.sqrt(2 / (9 * k))
    return 0.5 * math.erfc(z / math.sqrt(2))


def contro_il_caso(r):
    """La cartella Luck: le partite r contro il caso. -> dict(turni={N: dict(partite, x, e, z, p, classi={voce: (tue, attese)})},
    mani=dict(n, oss[0..7], reg[0..7], liscia[0..7], bo1 = partite Bo1)). z e p: le terre pescate in tutto contro le attese (normale, p a due code)."""
    out = dict(turni={}, mani=None)
    for N in TURNI_FORTUNA:
        gg = [x["fortuna"]["turni"][N] for x in r if (x.get("fortuna") or {}).get("turni", {}).get(N)]
        if not gg:
            continue
        X, E, V = sum(g["x"] for g in gg), sum(g["e"] for g in gg), sum(g["var"] for g in gg)
        z = (X - E) / math.sqrt(V) if V > 0 else 0.0
        cl = {v: [0, 0.0] for v in FORTUNA}
        for g in gg:
            cl[g["classe"]][0] += 1
            for v, pv in g["attese_classi"].items():
                cl[v][1] += pv
        out["turni"][N] = dict(partite=len(gg), x=X, e=E, z=z, p=math.erfc(abs(z) / math.sqrt(2)), classi={v: tuple(t) for v, t in cl.items()})
    mm = [x["fortuna"] for x in r if (x.get("fortuna") or {}).get("mano0") is not None]
    if mm:
        oss, reg, lis = [0] * 8, [0.0] * 8, [0.0] * 8
        for f in mm:
            oss[f["mano0"]] += 1
            pr = ipergeom(f["D"], f["L"], 7) or [0.0] * 8
            pl = pr if f["bo3"] else (mano_liscia(f["L"], f["D"], 7, 2) or pr)
            for j in range(8):
                reg[j] += pr[j]
                lis[j] += pl[j]
        out["mani"] = dict(n=len(mm), oss=oss, reg=reg, liscia=lis, bo1=sum(1 for f in mm if not f["bo3"]))
    return out


def riga(p, r):
    """Una partita: il record di matchup_log piu' le variabili dell'analizzatore. p e' la partita di partite_log."""
    import condividi
    quando = datetime.datetime.fromtimestamp((p.get("inizio") or 0) / 1000)
    mani = p.get("mani") or []
    tenuta = condividi.nomi(mani[-1]) if mani else None
    terre = sum(q for n, q in tenuta.items() if e_terra(n)) if tenuta else None
    sue = condividi.nomi(p.get("sue") or []) or {}
    turni = r.get("turni")
    econ, crea = dalla_mano(tenuta)
    lista = condividi.nomi(p.get("carte") or []) or {}
    mie_l = sorted({nm for t_, s_, cosa, g_, _tp in (_MANA.get(r.get("partita")) or {}).get("azioni") or []
                    if cosa == "magia" and s_ == p.get("seat") and (nm := nome_intero(nome_grp(g_) or "")) and g_ not in SENZA_FACCIA})
    # le mani rimandate indietro al mulligan: le terre di ognuna (13 nov 2026, l'analisi dei mulligan di decisioni.py)
    scartate = [sum(q for n, q in (condividi.nomi(m) or {}).items() if e_terra(n)) for m in mani[:-1]]
    return dict(r, seat=p.get("seat"), mazzo_id=p.get("mazzo"), mie_lanciate=mie_l, scartate=scartate, fortuna=fortuna(p, r, lista), **carte_partita(r, p.get("seat"), tenuta), economiche=econ, crea_mano=crea, crea_in_mano=creature_in_mano(tenuta),
                suo_mull=suo_mulligan(r.get("partita"), p.get("seat")), crea_prima=prima_creatura(r.get("partita"), p.get("seat"), r.get("inizia")),
                ist_mano=magie_in_mano(tenuta, "Instant"), str_mano=magie_in_mano(tenuta, "Sorcery"),
                art_mano=magie_in_mano(tenuta, "Artifact"), inc_mano=magie_in_mano(tenuta, "Enchantment"), pw_mano=magie_in_mano(tenuta, "Planeswalker"),
                bat_mano=magie_in_mano(tenuta, "Battle"),
                per_turno=per_turno(r.get("partita"), p.get("seat"), r.get("inizia"), turni),
                situa=situazioni_replay(r.get("partita"), p.get("seat"), r.get("inizia"), turni),
                crea_prima_lui=prima_creatura(r.get("partita"), 2 if p.get("seat") == 1 else 1 if p.get("seat") == 2 else None,
                                              None if r.get("inizia") is None else not r.get("inizia")), miei_colori=colori_mazzo(lista), fine=come_finita(p.get("motivo"), r["vinta"]),
                giorno=GIORNI[quando.weekday()], tipo="Limited" if r["formato"] == "limited" else "Constructed", quando=quando, ora=quando.hour, fascia=_fascia(quando.hour),
                terre=terre, mano=sorted(tenuta or {}), sue_viste=sorted(n for n in sue if not e_terra(n)),
                turno=math.ceil(turni / 2) if turni else None, lunga=_lunga(math.ceil(turni / 2) if turni else None),
                partenza=None if r.get("inizia") is None else ("Play" if r["inizia"] else "Draw"),
                mull="0" if r["mulligan"] == 0 else "1" if r["mulligan"] == 1 else "2+",
                sit=dict(situazioni_partita(scheda(r.get("partita")), r.get("inizia")), **_mana_sit(r.get("partita"), p.get("seat"))))


_NOMI_GRP = {}


# i grpId che Arena usa per le carte senza faccia: 3 a faccia in giu' (camuffata, manifestata), 0 una carta che il log non ha scritto (messaggio riassunto)
SENZA_FACCIA = {0: "Unknown card", 3: "Face-down card"}


def nome_grp(g):
    """Il nome di una carta di Arena dal suo grpId (una volta per grpId); None se il database non la conosce."""
    if g in SENZA_FACCIA:
        return SENZA_FACCIA[g]
    if g not in _NOMI_GRP:
        try:
            import condividi
            _NOMI_GRP[g] = next(iter(condividi.nomi([g]) or {}), None)
        except Exception:      # noqa: BLE001 - senza database niente nomi
            _NOMI_GRP[g] = None
    return _NOMI_GRP[g]


def _fuori(lst, seat):
    """I bersagli fuori dal campo dal tuo posto: {id: (zona, «mio»|«suo», nome)}: «cim_mio», «esi_suo», «pila»..."""
    out = {}
    for i, z, chi, g in lst or []:
        lato_ = "mio" if chi == seat else "suo"
        out[i] = (f"{z}_{lato_}" if z in ("cim", "esi") else z, lato_, nome_grp(g) if g is not None else None)
    return out


def colpiti_di(info):
    """I permanenti che una magia o un'abilita' ha tolto dal campo, per le frecce rosse del replayer. Senza bersagli (un board wipe) tutto quello che e'
    sparito mentre era in pila; coi bersagli i bersagli tolti e quello che ha spostato lei (13 nov 2026: Settle the Wreckage ha per bersaglio il giocatore ed
    esilia le sue creature attaccanti, Tribute to Hunger fa sacrificare; Burst Lightning alla faccia non toglie quello che muore per altro). «fatti» c'e' dalla
    VERSIONE 11 di mana_aperto e nel replay azione per azione; senza, coi bersagli valgono solo i bersagli."""
    colpiti, bers = list(info.get("colpiti") or []), info.get("bers") or []
    if not bers:
        return colpiti
    fatti = set(info.get("fatti") or ())
    return [x for x in colpiti if x in bers or x in fatti]


def foto_partita(x):
    """Le foto di una partita dal tuo posto (mano_aperto): dict(mano0, turni=[(turno, tuo turno?, foto)], ultima) con le foto girate cosi' che [0] sia il tuo
    lato; None se la partita non ha il log. turni=[(turno, tuo turno?, foto, «fine»|«comb»|«spell», relazioni)]. Una foto: dict(mio=[(nome, tappata, pedina,
    forza, costituzione, id)], suo=[...], mano=[nomi], n_suo=carte nella sua
    mano, vite=(tu, lui), cim=(tuo cimitero, suo), esi=(tuo esilio, suo))."""
    d = _MANA.get(x.get("partita"))
    seat = x.get("seat")
    if not d or seat not in (1, 2) or "foto" not in d:
        return None
    a, b = seat - 1, 2 - seat

    def gira(f):
        if not f:
            return None
        carte = lambda lst: [(nome_grp(c[0]) or ("Token" if c[2] else f"#{c[0]}"), bool(c[1]), bool(c[2]), *(list(c[3:6]) + [None, None, None])[:3]) for c in lst]
        nomi = lambda lst: [nome_grp(g) or f"#{g}" for g in lst]
        vuoto = [[], []]
        return dict(mio=carte(f["c"][a]), suo=carte(f["c"][b]), mano=nomi(f["m"][a]), n_suo=f["n"][b], vite=(f["v"][a], f["v"][b]),
                    cim=(nomi((f.get("g") or vuoto)[a]), nomi((f.get("g") or vuoto)[b])), esi=(nomi((f.get("e") or vuoto)[a]), nomi((f.get("e") or vuoto)[b])))
    lato = lambda b_: ("vita_mio" if b_ == seat else "vita_suo") if b_ in (1, 2) else b_      # un bersaglio giocatore e' il suo posto (1 o 2)
    if d.get("momenti") is not None:        # i momenti in ordine: la fine dei turni, i combattimenti, le magie coi bersagli (VERSIONE 4)
        turni = []
        for kind, t, att, f, info in d["momenti"]:
            rel = None
            if kind == "spell":
                nome = nome_grp(info["g"])
                if not nome:
                    continue
                bers = info.get("bers") or []
                colpiti = colpiti_di(info)
                rel = dict(tipo="spell", nome=nome, mio=info.get("chi") == seat, ab=bool(info.get("ab")), bers=[lato(b_) for b_ in bers], colpiti=colpiti,
                           fuori=_fuori(info.get("fuori"), seat))
            elif kind == "comb":
                rel = dict(tipo="comb", att=[(i, lato(tg)) for i, tg in info.get("att") or []], blocchi=[(i, list(a_)) for i, a_ in info.get("blocchi") or []])
            turni.append((t, att == seat, gira(f), kind, rel))
    else:
        turni = [(t, att == seat, gira(f), "fine", None) for t, att, f in d.get("foto") or []]
    ult = d.get("ultima")
    return dict(mano0=gira(d.get("mano0")), turni=turni, ultima=(ult[0], ult[1] == seat, gira(ult[2])) if ult else None)


def gira_foto(f, seat):
    """Una foto di mana_aperto o di replay_log girata dal tuo posto, coi nomi (come in foto_partita)."""
    if not f:
        return None
    a, b = seat - 1, 2 - seat
    carte = lambda lst: [(nome_grp(c[0]) or ("Token" if c[2] else f"#{c[0]}"), bool(c[1]), bool(c[2]), *(list(c[3:6]) + [None, None, None])[:3]) for c in lst]
    nomi = lambda lst: [nome_grp(g) or f"#{g}" for g in lst]
    vuoto = [[], []]
    return dict(mio=carte(f["c"][a]), suo=carte(f["c"][b]), mano=nomi(f["m"][a]), n_suo=f["n"][b], vite=(f["v"][a], f["v"][b]),
                cim=(nomi((f.get("g") or vuoto)[a]), nomi((f.get("g") or vuoto)[b])), esi=(nomi((f.get("e") or vuoto)[a]), nomi((f.get("e") or vuoto)[b])))


VERBI = ("played", "cast", "drew", "gained", "lost", "created", "attacked", "discarded", "sacrificed", "turn", "conceded", "scried")


def azioni_partita(x):
    """Il replay azione per azione di una partita dal tuo posto (replay_log, 12 nov 2026): [(nome, foto, turno, relazioni, eventi, danni)], o None senza log.
    Gli eventi: [(tuo?, testo)] col soggetto («You», «Opponent») e i giocatori nei testi («you», «the opponent»)."""
    import replay_log as RL
    seat = x.get("seat")
    mid = x.get("partita")
    if seat not in (1, 2) or not mid:
        return None
    righe = RL.righe_partita(mid, (_MANA.get(mid) or {}).get("dove"))
    if not righe:
        return None
    lato = lambda b_: ("vita_mio" if b_ == seat else "vita_suo") if b_ in (1, 2) else b_
    altro = 2 if seat == 1 else 1
    out = []
    for fr in RL.azioni(righe, nome_grp):
        ev = []
        for chi, testo in fr["ev"]:
            testo = testo.replace(f"{{P{seat}}}", "you").replace(f"{{P{altro}}}", "the opponent")
            if testo.split(" ")[0] in VERBI:
                testo = ("You " if chi == seat else "Opponent " if chi else "") + testo
                if testo.startswith("You turn") or testo.startswith("Opponent turn"):
                    testo = testo.replace("You turn", "Your turn").replace("Opponent turn", "Opponent's turn")
            ev.append((chi == seat, testo[:1].upper() + testo[1:]))
        r_ = fr["rel"]
        rel = None
        if r_ and r_["k"] == "comb":
            rel = dict(tipo="comb", att=[(i, lato(tg)) for i, tg in r_["att"]], blocchi=[(i, list(a_)) for i, a_ in r_["blocchi"]])
        elif r_ and r_["k"] == "spell" and nome_grp(r_["g"]):
            rel = dict(tipo="spell", nome=nome_grp(r_["g"]), mio=r_["chi"] == seat, ab=r_["ab"], bers=[lato(b_) for b_ in r_["bers"]], colpiti=colpiti_di(r_),
                       fuori=_fuori(r_.get("fuori"), seat))
        nome = f"{'You' if fr['att'] == seat else 'Opponent'} T{(fr['t'] + 1) // 2} · {fr['step'] or '-'}"
        out.append((nome, gira_foto(fr["foto"], seat), fr["t"], rel, ev, [(lato(b_), q) for b_, q in fr["danni"]]))
    return out


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
    _TERRE.clear()      # una rilettura dei log rifa' anche le terre (una carta nuova del database)
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
         ("pausa", "Break before this game", lambda x: x.get("pausa")),
         # 13 nov 2026, Autore: «mio wr quando ho 3 terre in mano on the draw e chiudo entro T5 senza creature e oppo mulliga»; «senza creature»: tutte e tre
         ("crea_in_mano", "Creatures in your opening hand", lambda x: x.get("crea_in_mano")),
         ("senza_crea", "No creature cast by", lambda x: (valori_di("senza_crea", x) or [None])[0]),
         ("suo_mull", "Opponent's mulligans", lambda x: x.get("suo_mull")),
         ("fine_entro", "Game ended by", lambda x: (valori_di("fine_entro", x) or [None])[0]),
         ("ist_mano", "Instants in your opening hand", lambda x: x.get("ist_mano")),
         ("str_mano", "Sorceries in your opening hand", lambda x: x.get("str_mano")),
         # i permanenti che mancavano (13 nov 2026, Autore: «in your opening hand mettiamo anche i permanenti che mancano ... mancano anche i planeswalker»)
         ("art_mano", "Artifacts in your opening hand", lambda x: x.get("art_mano")),
         ("inc_mano", "Enchantments in your opening hand", lambda x: x.get("inc_mano")),
         ("pw_mano", "Planeswalkers in your opening hand", lambda x: x.get("pw_mano")),
         ("bat_mano", "Battles in your opening hand", lambda x: x.get("bat_mano"))]
# turno per turno (13 nov 2026): «t_io3» = cosa hai lanciato nel tuo turno 3, «t_lui1» = cosa ha lanciato l'avversario nel suo turno 1
EXTRA += [(f"t_{pre}{chi}{suf}{n}", nome.format(n=n), (lambda x, k=f"{pre}{chi}{suf}{n}": ((x.get("per_turno") or {}).get(k) or [None])[0]))
          for chi, tu, lui_ in (("io", "You", "the opponent's"), ("lui", "Opponent", "your"))
          for pre, suf, nome in (("", "", tu + " · turn {n} cast"), ("", "x", tu + " · " + lui_ + " turn {n} cast"),
                                 ("a", "", tu + " · turn {n} attack"), ("d", "", tu + " · " + lui_ + " turn {n} defense"),
                                 ("m", "", tu + " · turn {n} attack · " + ("the opponent's" if chi == "io" else "your") + " untapped lands"),
                                 ("p", "", tu + " · turn {n} draws"), ("p", "x", tu + " · " + lui_ + " turn {n} draws"))
          for n in range(1, TURNI_FILTRO + 1)]
EXTRA += [(f"t_pe{chi}", f"{tu} · extra draws in one turn (turns 1-{TURNI_FILTRO})", (lambda x, k=f"pe{chi}": ((x.get("per_turno") or {}).get(k) or [None])[-1]))
          for chi, tu in (("io", "You"), ("lui", "Opponent"))]
# i filtri situazionali dai replay (13 nov 2026, situazioni_replay) e la prima creatura dell'avversario
EXTRA += [("s_" + k_, nome_, (lambda x, k=k_: (x.get("situa") or {}).get(k))) for k_, (nome_, _o) in SITUA_NOMI.items()]
EXTRA += [("senza_lui", "Opponent · no creature cast by", lambda x: (valori_di("senza_lui", x) or [None])[0])]
# C1 (13 nov 2026): le terre pescate contro il caso, entro il tuo turno 3, 5, 7
EXTRA += [(f"luck{N}", f"Lands drawn by your turn {N} · vs chance", (lambda x, N=N: (((x.get("fortuna") or {}).get("turni") or {}).get(N) or {}).get("classe")))
          for N in TURNI_FORTUNA]
for _k, _n, _f in EXTRA:
    NOME[_k], LEGGI[_k] = _n, _f
# vinta o persa come tendina della fase Opening and first turns (12 nov 2026, Autore: «aggiungiamo la tendina di partita vinta o persa nella sezione opening
# hands and first turns»): non entra negli Spots (spiegherebbe tutto il win rate da sola)
NOME["esito"], LEGGI["esito"] = "Result", (lambda x: "Won" if x["vinta"] else "Lost")
NOME["wr_rif"] = "Win rate"
NOME["lanciate"] = "Card you cast"
NOME.update(lanc_t4="Card you cast by your turn 4", finisher="Card in your finish", in_mano="Card in your hand", sue_lanciate="Card the opponent cast", bloccate="Card stuck in your hand",
            **{f"pesc{n}": f"Card found on your turn {n}" for n in range(1, 5)})       # 4 = TURNI_CARTE; i clic della cartella Cards, fuori dagli Spots
ORDINE_VALORI.update(esito=("Won", "Lost"), miei_colori=VARIANTI, economiche=("0", "1", "2+"), crea_mano=("Yes", "No"),
                     fine=("You conceded", "Opponent conceded", "Played to the end", "Timeout"), giorno=GIORNI,
                     pausa=("Under 15 minutes", "15-60 minutes", "Over 1 hour (new session)"), crea_in_mano=("0", "1", "2", "3+"),
                     senza_crea=tuple(f"Your turn {n}" for n in SENZA) + ("The whole game",), suo_mull=("0", "1", "2+"),
                     fine_entro=tuple(f"Your turn {n}" for n in ENTRO), ist_mano=("0", "1", "2+"), str_mano=("0", "1", "2+"),
                     art_mano=("0", "1", "2+"), inc_mano=("0", "1", "2+"), pw_mano=("0", "1", "2+"), bat_mano=("0", "1", "2+"),
                     **{f"t_{pre}{chi}{suf}{n}": o_ for chi in ("io", "lui") for n in range(1, TURNI_FILTRO + 1)
                        for pre, suf, o_ in (("", "", ORDINE_TIPI), ("", "x", ORDINE_TIPI), ("a", "", ORDINE_ATT), ("d", "", ORDINE_DIF),
                                             ("m", "", ORDINE_APERTE), ("p", "", ORDINE_PESCATE), ("p", "x", ORDINE_PESCATE_X))},
                     t_peio=ORDINE_EXTRA, t_pelui=ORDINE_EXTRA,
                     **{"s_" + k_: ORDINE_SITUA[o_] for k_, (_n, o_) in SITUA_NOMI.items()},
                     senza_lui=tuple(f"Their turn {n}" for n in SENZA) + ("The whole game",), **{f"luck{N}": FORTUNA for N in TURNI_FORTUNA})


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
    if k == "lanciate":         # le tue magie lanciate (la cartella Cards, 13 nov 2026)
        return x.get("mie_lanciate") or []
    if k in ("in_mano", "sue_lanciate", "bloccate", "lanc_t4", "finisher") or re.fullmatch(r"pesc\d", k):      # le altre righe della cartella Cards
        return x.get(k) or []
    if k == "data":
        giorni = (datetime.datetime.now() - x["quando"]).days
        return [n for n, d in DATE if giorni < d]
    if k.startswith("t_"):       # turno per turno: tutti i tipi lanciati in quel turno (una creatura artefatto e' Creature e Artifact)
        return list((x.get("per_turno") or {}).get(k[2:]) or [])
    # le soglie (13 nov 2026): una partita sta in ogni «entro il turno N» che la comprende, come le date
    if k == "fine_entro":
        t = x.get("turno")
        return [] if not t else [f"Your turn {n}" for n in ENTRO if t <= n]
    if k.startswith("s_"):       # i filtri situazionali dai replay (situazioni_replay)
        v = (x.get("situa") or {}).get(k[2:])
        return [] if v is None else [v]
    if k in ("senza_crea", "senza_lui"):
        prima = x.get("crea_prima" if k == "senza_crea" else "crea_prima_lui")
        if prima is None:
            return []
        chi_ = "Your" if k == "senza_crea" else "Their"
        return [f"{chi_} turn {n}" for n in SENZA if prima == 0 or n < prima] + (["The whole game"] if prima == 0 else [])
    v = LEGGI[k](x)
    return [] if v is None else [v]


WR_MINIMO = 10      # il gruppo del win rate ha almeno 10 partite: con meno un 100% si fa con una vittoria sola


def finestra_wr(r, f):
    """Il filtro del win rate (13 nov 2026, Autore: «win rate deve poter settare una % di win rate sulla quale si posiziona la ricerca», poi, dopo la prima
    versione che guardava il win rate che avevi a ogni partita: «in base al wr lui filtra le partite che partecipano a costruire quel dato di wr, se poi aggiungo
    mulligan 1 lui filtra le partite vinte almeno al 51% con mulligan 1»): le partite r (gia' passate dagli altri filtri, in ordine di tempo) dalla piu' recente
    all'indietro, finche' il loro win rate resta al valore; si tiene il gruppo piu' lungo, di almeno WR_MINIMO partite. f = (valore, ≥, ≤): col ≥ almeno il
    valore, col ≤ al massimo, senza segni (o con tutti e due) il valore esatto, arrotondato all'unita'. Cosi' il win rate delle partite che restano e' quello
    scritto. Nessun gruppo che regge: nessuna partita."""
    try:
        val, ge, le = float(f[0]), bool(f[1]), bool(f[2])
    except (TypeError, ValueError, IndexError):
        return list(r)
    if ge and not le:
        regge = lambda w: w >= val - 1e-9
    elif le and not ge:
        regge = lambda w: w <= val + 1e-9
    else:
        regge = lambda w: round(w) == round(val)
    vinte, migliore = 0, 0
    for n, x in enumerate(reversed(r), 1):
        vinte += 1 if x["vinta"] else 0
        if n >= WR_MINIMO and regge(100 * vinte / n):
            migliore = n
    return list(r[len(r) - migliore:]) if migliore else []


def etichetta_wr(f):
    try:
        val, ge, le = float(f[0]), bool(f[1]), bool(f[2])
    except (TypeError, ValueError, IndexError):
        return "-"
    segno = "≥ " if ge and not le else "≤ " if le and not ge else ""
    return f"{segno}{val:g}%"


def passa(x, filtri):
    for k, v in filtri.items():
        if v is None:
            continue
        if k == "wr_rif":       # non e' un filtro della singola partita: lo applica filtra, dopo gli altri (finestra_wr)
            continue
        elif isinstance(v, (list, tuple)):
            if not v:
                continue
            ci_sono = collections.Counter(valori_di(k, x))
            if any(ci_sono[i] < n for i, n in collections.Counter(v).items()):      # «Instant», «Instant»: almeno due istantanei
                return False
        elif v not in valori_di(k, x):
            return False
    return True


TURNI_CARTE = 4         # le righe della cartella Cards turno per turno
SALTO_MINIMO = 8        # il salto di vantaggio di un finisher (sui log del 13 nov: il salto piu' grande e' almeno 8 nell'85% delle vittorie, nel 64% delle perse)


def vantaggio(f, seat):
    """Il vantaggio dal tuo posto in una foto di fine turno: vite di differenza piu' due volte la forza in campo di differenza (grado C, come il punto di
    svolta del replayer). 0 senza foto."""
    if not f:
        return 0
    v = f.get("v") or [20, 20]
    forza = [sum(int(c_[3] or 0) for c_ in lato or [] if c_[3] is not None) for lato in (f.get("c") or [[], []])]
    o = 2 - seat
    return ((v[seat - 1] or 0) - (v[o] or 0)) + 2 * (forza[seat - 1] - forza[o])


def carte_partita(r, seat, tenuta):
    """Le carte di una partita per le righe della cartella Cards (13 nov 2026, Autore: «in cards creiamo delle vere e proprie righe di dato: most in hand
    find card / most t1 /t2 /t3 / t4 found cards / match up most played cards / harder to cast cards»), le terre escluse, coi nomi interi:
      «in_mano»      le carte che hai avuto in mano: la mano tenuta e tutte le pescate;
      «pesc{n}»      al tuo turno 1 la mano tenuta e la prima pescata, ai turni 2-4 le carte pescate in quel tuo turno (anche le extra);
      «sue_lanciate» le magie che ha lanciato l'avversario;
      «bloccate»     le carte che hai avuto in mano e non hai mai lanciato in quella partita.
    Dalle azioni di mana_aperto (VERSIONE 13, le pescate); senza azioni, o senza sapere chi ha cominciato, le righe di quella partita restano vuote."""
    az = (_MANA.get(r.get("partita")) or {}).get("azioni")
    out = dict(in_mano=[], sue_lanciate=[], bloccate=[], lanc_t4=[], finisher=[], **{f"pesc{n}": [] for n in range(1, TURNI_CARTE + 1)})
    if not az or seat not in (1, 2) or r.get("inizia") is None:
        return out
    magia = lambda nm: bool(nm) and not e_terra(nm)
    nome_g = lambda g: nome_intero(nome_grp(g) or "") if g not in SENZA_FACCIA else ""
    mano = {nome_intero(n) for n in (tenuta or {})}
    pescate = collections.defaultdict(set)
    tutte_p, mie, sue = set(), set(), set()
    mio_turno = (lambda t: t % 2 == 1) if r["inizia"] else (lambda t: t % 2 == 0)
    for t, s_, cosa, g_, _tp in az:
        nm = nome_g(g_)
        if cosa == "pesca" and s_ == seat and nm:
            tutte_p.add(nm)
            if mio_turno(t):
                pescate[(t + 1) // 2].add(nm)
        elif cosa == "magia" and nm:
            (mie if s_ == seat else sue).add(nm)
    if not any(a[2] == "pesca" for a in az):        # una partita letta prima delle pescate: le righe della mano non si sanno
        mano_p = None
    else:
        mano_p = mano | tutte_p
    pesc = {f"pesc{n}": sorted(n_ for n_ in ((mano | pescate[1]) if n == 1 else pescate[n]) if magia(n_)) for n in range(1, TURNI_CARTE + 1)}
    out.update(pesc if mano_p is not None else {})
    out["sue_lanciate"] = sorted(n_ for n_ in sue if magia(n_))
    # entro il tuo turno 4 (13 nov 2026, Autore: «le carte che hanno interagito generando più valore o sinergia entro il t4»): le tue magie lanciate fino
    # alla fine del tuo turno 4, anche nei suoi turni; il turno 4 tuo e' il 7 di Arena se cominci, l'8 se no
    fine_t4 = 2 * TURNI_CARTE - (1 if r["inizia"] else 0)
    out["lanc_t4"] = sorted({nome_g(g_) for t, s_, cosa, g_, _tp in az if cosa == "magia" and s_ == seat and t <= fine_t4 and magia(nome_g(g_))})
    # il finisher (13 nov 2026, Autore: «finishers dovrebbe essere la raccolta di quella giocata sinergica tra almeno due carte che ha generato un roi
    # pazzesco sulla partita e che ha decretato in modo insindacabile la sconfitta dell'avversario, del suo board o del suo piano, non semplicemente le ultime
    # due carte arrivate alla fine»): nelle vittorie, il tuo turno col salto di vantaggio piu' grande (vantaggio = vite di differenza piu' due volte la forza
    # in campo di differenza, come il punto di svolta del replayer; salto = vantaggio a fine turno meno quello a fine turno prima), almeno SALTO_MINIMO, dopo il
    # quale il vantaggio resta tuo fino alla fine; la giocata sono le magie che hai lanciato in quel turno e le creature con cui hai attaccato, almeno due carte.
    # Sui log del 13 nov: 122 vittorie su 234 hanno una giocata cosi'.
    out["finisher"], out["salto"], out["turno_svolta"] = [], None, None
    foto = {f[0]: f[2] for f in (_MANA.get(r.get("partita")) or {}).get("foto") or [] if isinstance(f[2], dict)}
    if r.get("vinta") and foto:
        ts = sorted(foto)
        vant = {t: vantaggio(foto[t], seat) for t in ts}
        best = None
        for t in ts:
            if not mio_turno(t):
                continue
            salto = vant[t] - vant.get(t - 1, 0)
            if salto >= SALTO_MINIMO and all(vant[t2] > 0 for t2 in ts if t2 >= t) and (best is None or salto > best[1]):
                best = (t, salto)
        if best:
            t = best[0]
            gioc = {nome_g(g_) for t_, s_, cosa, g_, _tp in az if cosa == "magia" and s_ == seat and t_ == t}
            for m in (_MANA.get(r.get("partita")) or {}).get("momenti") or []:
                if m[0] == "comb" and m[1] == t and m[2] == seat and len(m) > 4 and m[4]:
                    ids_a = {a_[0] for a_ in m[4].get("att") or []}
                    for c_ in ((m[3] or {}).get("c") or [[], []])[seat - 1] or []:
                        if c_[5] in ids_a and not c_[2]:
                            gioc.add(nome_g(c_[0]))
            gioc = sorted(n_ for n_ in gioc if magia(n_))
            if len(gioc) >= 2:
                out["finisher"], out["salto"], out["turno_svolta"] = gioc, best[1], (t + 1) // 2
    if mano_p is not None:
        out["in_mano"] = sorted(n_ for n_ in mano_p if magia(n_))
        out["bloccate"] = sorted(n_ for n_ in mano_p if magia(n_) and n_ not in mie)
    return out


RIGHE_CARTE = [("in_mano", "MOST FOUND IN YOUR HAND · opening hand and draws"),
               ("pesc1", "YOUR TURN 1 · the opening hand and the first draw"), ("pesc2", "YOUR TURN 2 · drawn on it"),
               ("pesc3", "YOUR TURN 3 · drawn on it"), ("pesc4", "YOUR TURN 4 · drawn on it"),
               ("lanciate", "YOUR MOST CAST SPELLS"), ("lanc_t4", "CAST BY YOUR TURN 4 · Pairs: what you played together early"),
               ("finisher", "FINISHERS · the decisive play of your wins: the biggest swing after which you stayed ahead, 2+ cards"), ("sue_lanciate", "THE MATCHUPS · the opponent's most played cards"),
               ("bloccate", "HARDER TO CAST · in your hand and never cast")]
CAMPO_CARTE = {"lanciate": "mie_lanciate"}       # la chiave del filtro -> il campo della riga (le altre si chiamano uguali)


def riga_carte(r, chiave, quante=40, minimo=5):
    """Una riga della cartella Cards: le carte della chiave nelle partite r, ognuna una volta per partita, dalla piu' comune; per «bloccate» dalla piu'
    bloccata (le partite in cui e' rimasta in mano sulle partite in cui l'avevi in mano, da `minimo` partite in mano), col win rate di quelle partite.
    -> [dict(nome, n, vinte, perse, wr, quota[, mano, bloccata])]."""
    if chiave == "finisher":
        return finisher_coppie(r, quante)
    campo = CAMPO_CARTE.get(chiave, chiave)
    conta, vinte = collections.Counter(), collections.Counter()
    for x in r:
        for nm in set(x.get(campo) or []):
            conta[nm] += 1
            vinte[nm] += 1 if x["vinta"] else 0
    tot = len(r) or 1
    out = [dict(nome=nm, n=n, vinte=vinte[nm], perse=n - vinte[nm], wr=round(100 * vinte[nm] / n, 1), quota=round(100 * n / tot, 1)) for nm, n in conta.items()]
    if chiave == "bloccate":
        in_mano = collections.Counter(nm for x in r for nm in set(x.get("in_mano") or []))
        for c in out:
            c["mano"] = in_mano[c["nome"]]
            c["bloccata"] = round(100 * c["n"] / c["mano"]) if c["mano"] else 0
        out = [c for c in out if c["mano"] >= minimo]
        out.sort(key=lambda c: (-c["bloccata"], -c["n"], c["nome"]))
    else:
        out.sort(key=lambda c: (-c["n"], c["nome"]))
    return out[:quante]


def coppie_carte(r, chiave, quante=60, minimo=5, k=2):
    """Le coppie di carte di una riga di Cards, dalla piu' vincente (13 nov 2026, Autore: «come imposteresti i filtri per determinare al di sopra del 51% di
    win rate quale combinazione di carte vince almeno il 60% delle volte in starting hand?», poi «non aggiungere le coppie come righe ma come finestre extra che
    si aprono dalla riga e mostrano le coppie»): due carte della riga nella stessa partita, una volta per partita, da `minimo` partite; a parita' di win rate
    prima quella con piu' partite. Dalla riga del turno 1 le coppie sono della mano tenuta (la «starting hand»: Card in opening hand), dalle altre del campo
    della riga (in mano, lanciate insieme, rimaste in mano insieme...). -> [dict(nome «A + B», nomi=(A, B), n, vinte, perse, wr, quota, filtro=(chiave, [A, B]))]."""
    campo, fk = ("mano", "mano") if chiave == "pesc1" else (CAMPO_CARTE.get(chiave, chiave), chiave)
    conta, vinte = collections.Counter(), collections.Counter()
    for x in r:
        m = sorted({n for n in x.get(campo) or [] if not e_terra(n)})
        for cp in itertools.combinations(m, k):
            conta[cp] += 1
            vinte[cp] += 1 if x["vinta"] else 0
    tot = len(r) or 1
    out = [dict(nome=" + ".join(cp), nomi=cp, n=n, vinte=vinte[cp], perse=n - vinte[cp], wr=round(100 * vinte[cp] / n, 1),
                quota=round(100 * n / tot, 1), filtro=(fk, list(cp))) for cp, n in conta.items() if n >= minimo]
    out.sort(key=lambda c: (-c["wr"], -c["n"], c["nome"]))
    return out[:quante]


def finisher_coppie(r, quante=40, minimo=2):
    """La riga Finishers: le coppie di carte delle giocate decisive (carte_partita, «finisher») delle partite r, da quella che ha deciso piu' vittorie, col
    salto medio. -> [dict(nome, nomi, n (vittorie decise), vinte, perse, wr, quota (% delle vittorie), salto, filtro)]."""
    conta, salti = collections.Counter(), collections.defaultdict(list)
    for x in r:
        for cp in itertools.combinations(sorted(set(x.get("finisher") or [])), 2):
            conta[cp] += 1
            salti[cp].append(x.get("salto") or 0)
    vinte_tot = sum(1 for x in r if x["vinta"]) or 1
    out = [dict(nome=" + ".join(cp), nomi=cp, n=n, vinte=n, perse=0, wr=100.0, quota=round(100 * n / vinte_tot, 1),
                salto=round(sum(salti[cp]) / len(salti[cp]), 1), filtro=("finisher", list(cp))) for cp, n in conta.items() if n >= minimo]
    out.sort(key=lambda c: (-c["n"], -c["salto"], c["nome"]))
    return out[:quante]


def filtro_carta(chiave, c):
    """Il filtro di una carta o di una coppia di Cards: -> (chiave, valore). Una coppia tiene le partite con tutte e due (una lista: passa le vuole tutte)."""
    return tuple(c["filtro"]) if "filtro" in c else (chiave, c["nome"])


def filtra(righe_, filtri, tipo=None):
    """Le righe del tipo che passano i filtri. Il win rate (finestra_wr) si calcola dopo gli altri filtri ma prima di Result: con Result acceso il gruppo
    sarebbe tutto vinto (100%) o tutto perso; cosi' «52% e le vittorie» sono le vittorie del gruppo di partite che fa il 52% (13 nov 2026)."""
    if not filtri.get("wr_rif"):
        return [x for x in righe_ if (tipo is None or x["tipo"] == tipo) and passa(x, filtri)]
    senza = {k: v for k, v in filtri.items() if k != "esito"}
    out = finestra_wr([x for x in righe_ if (tipo is None or x["tipo"] == tipo) and passa(x, senza)], filtri["wr_rif"])
    return [x for x in out if passa(x, {"esito": filtri["esito"]})] if filtri.get("esito") else out


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
    if k == "wr_rif":
        return etichetta_wr(v)
    if isinstance(v, (list, tuple)):        # una scelta multipla: le voci insieme
        return " + ".join(str(i) for i in v)
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


def linee(r, metrica, asse, finestra, dividi=None, quante=5, extra=None):
    """Le linee del grafico: [(nome, punti)]. Con dividi una per valore (i piu' giocati, al massimo quante), piu' All. extra = (nome, partite): una linea in
    piu' sulle partite di una decisione di Decisions, sull'asse di tutte (13 nov 2026, Autore: «li dobbiamo vedere anche sul grafico aggiungendo una linea
    sul grafico vs quella totale ... tipo holdem manager»)."""
    posto = {x.get("partita") or id(x): i + 1 for i, x in enumerate(sorted(r, key=lambda x: x["quando"]))}
    out = [("All", serie(r, metrica, asse, finestra))]
    for nome_, ids_ in ([extra] if extra and isinstance(extra[0], str) else extra or []):
        out.append((nome_, serie([x for x in r if x.get("partita") in ids_], metrica, asse, finestra, posto=posto)))
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


def trofei(r):
    """Le partite che chiudono un draft col trofeo, sull'asse delle partite: [indice 1..] (13 nov 2026, Autore: «nei grafici non si vedono piu' i loghi dei
    trofei per il limited»). Ogni draft ha il suo mazzo (un id per corso): le sue partite in fila, e la vittoria numero 7 (3 nel Traditional, al meglio
    delle tre) e' il trofeo. Solo gli eventi limited (Draft, Sealed, Cube)."""
    out, vinte = [], {}
    for i, x in enumerate(sorted(r, key=lambda x: x["quando"])):
        ev = x.get("evento") or ""
        if not x.get("mazzo_id") or not re.search(r"Draft|Sealed|Cube", ev) or not x.get("vinta"):
            continue
        k = (ev, x["mazzo_id"])
        vinte[k] = vinte.get(k, 0) + 1
        if vinte[k] == (3 if ev.startswith("Trad") else 7):
            out.append(i + 1)
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


FDR = 0.05          # gli spot «strong»: i falsi positivi attesi fra loro (Benjamini-Hochberg)
# le variabili che sono il risultato, non una situazione: negli Spots spiegherebbero da sole il win rate (13 nov 2026, le simulazioni: in testa «Opponent
# conceded» al 100% e «la tua vita piu' bassa: 0 o meno» allo 0%). Restano filtri; Result non c'era gia'
FUORI_SPOT = {"fine", "s_vita_io", "s_vita_lui"}


def spot(r, minimo=15, quanti=8, coppie=True, gia=None):
    """-> (meglio, peggio): [dict(condizioni=[(chiave, valore)], nome, n, vinte, perse, wr, ic, delta, forte)]. gia: i filtri gia' messi (non si ripropongono)."""
    gia = {k for k, v in (gia or {}).items() if v is not None}
    base = conti(r)
    if not base["n"] or base["wr"] is None:
        return [], []
    insiemi = {}
    for k in [k for k, _n, _f in VARIABILI] + ["vs"] + [k for k, _n, _f in EXTRA] + ["sit:" + s for s, _n in SIT]:
        if k in gia or k == "data" or k in FUORI_SPOT:
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
    # «strong» corretto per le prove multiple (13 nov 2026, le simulazioni: con vittorie e sconfitte mescolate a caso, cioe' senza nessun segnale, l'intervallo
    # al 95% preso da solo marcava «strong» da 79 a 156 spot, perche' le condizioni e le coppie provate sono migliaia). Ogni condizione si confronta con le
    # partite fuori da lei (p_proporzioni) e passa la procedura di Benjamini-Hochberg sul numero di condizioni provate, con i falsi positivi al 5% (FDR).
    tot_v, tot_n = sum(1 for x in r if x["vinta"]), len(r)
    for x in out:
        x["p"] = p_proporzioni(x["vinte"], x["n"], tot_v - x["vinte"], tot_n - x["n"])
    ps = sorted(x["p"] for x in out if x["p"] is not None)
    soglia = 0.0
    for i, pv in enumerate(ps, 1):
        if pv <= FDR * i / len(ps):
            soglia = pv
    for x in out:
        x["forte"] = x["p"] is not None and x["p"] <= soglia and soglia > 0
    meglio = sorted((x for x in out if x["delta"] > 0), key=lambda x: (not x["forte"], -x["su"]))[:quanti]
    peggio = sorted((x for x in out if x["delta"] < 0), key=lambda x: (not x["forte"], -x["giu"]))[:quanti]
    return meglio, peggio


# ------------------------------------------------------------------ la matrice dei matchup
# (stesso giorno: «potranno incastrare anche i mazzi che utilizzano vs i mazzi del meta o trovati in partite»): i tuoi mazzi in riga, gli archetipi incontrati in
# colonna (quelli riconosciuti fra le liste del meta, o anche i soli colori, «Azorius», e «Unknown», i mazzi trovati in partita), in ogni cella partite e win rate.
def del_meta(suo):
    import matchup_log as MU
    return bool(suo) and not MU.solo_colori(suo) and suo != "Unknown"


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


def righe_carte_scelte():
    """Le righe di Cards da mostrare (13 nov 2026, Autore: «creiamo un menu filtri in cards per non avere mille righe ma solo quelle che cerchiamo
    combinando da una sotto finestrella di filtri dedicato alla sezione cards»): le chiavi spuntate, nell'ordine di RIGHE_CARTE; tutte se non hai mai scelto."""
    try:
        with open(CARTE_SCELTE, encoding="utf-8") as f:
            d = json.load(f)
        if isinstance(d, list):
            return [k for k, _t in RIGHE_CARTE if k in d]
    except (OSError, ValueError):
        pass
    return [k for k, _t in RIGHE_CARTE]


def numeri_scelti():
    """I numeri in cima a Performance (numeri_partite.CATALOGO), al massimo sei, nell'ordine del catalogo; quelli di partenza se non hai mai scelto."""
    import numeri_partite as NP
    try:
        with open(NUMERI_SCELTI, encoding="utf-8") as f:
            d = json.load(f)
        if isinstance(d, list):
            return [k for k, _n, _d in NP.CATALOGO if k in d][:NP.MASSIMO]
    except (OSError, ValueError):
        pass
    return list(NP.PARTENZA)


def salva_numeri(chiavi):
    import numeri_partite as NP
    _scrivi_in(NUMERI_SCELTI, [k for k, _n, _d in NP.CATALOGO if k in chiavi][:NP.MASSIMO])


def salva_righe_carte(chiavi):
    _scrivi_in(CARTE_SCELTE, [k for k, _t in RIGHE_CARTE if k in chiavi])


def segnalibri():
    """Gli spot segnati nel replayer, dal piu' recente: [dict(partita, quando, tipo, mio, suo, vinta, modo, i, passo, t)]."""
    try:
        with open(SEGNALIBRI, encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, list) else []
    except (OSError, ValueError):
        return []


def segnato(partita, modo, i):
    return any(s.get("partita") == partita and s.get("modo") == modo and s.get("i") == i for s in segnalibri())


def segna(x, modo, i, passo, t_):
    """Segna uno spot (una partita, il modo del replayer, il passo): in testa, al massimo 200; segnato di nuovo, si toglie. -> True se ora e' segnato."""
    d = segnalibri()
    gia = [s for s in d if s.get("partita") == x.get("partita") and s.get("modo") == modo and s.get("i") == i]
    if gia:
        d = [s for s in d if s not in gia]
    else:
        d.insert(0, dict(partita=x.get("partita"), quando=x["quando"].isoformat(timespec="minutes"), tipo=x.get("tipo"), mio=(x.get("mio") or "").strip(),
                         suo=x.get("suo"), vinta=bool(x.get("vinta")), modo=modo, i=i, passo=passo, t=t_))
    _scrivi_in(SEGNALIBRI, d[:200])
    return not gia


def togli_segnalibro(k):
    d = segnalibri()
    if 0 <= k < len(d):
        d.pop(k)
        _scrivi_in(SEGNALIBRI, d)
    return d


def _scrivi_in(path, d):
    if account.sola_lettura():
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path + ".tmp", "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
    os.replace(path + ".tmp", path)


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
    # i filtri del 13 nov 2026: finita entro il tuo turno N, nessuna creatura entro il turno N, il suo mulligan
    casi.append(("finita entro: la partita finita al tuo turno 5 sta in «entro il 5» e dopo, non in «entro il 4»",
                 "Your turn 5" in valori_di("fine_entro", dict(turno=5)) and "Your turn 4" not in valori_di("fine_entro", dict(turno=5))))
    casi.append(("nessuna creatura entro: la prima al tuo turno 3 sta in «entro il 2», non in «entro il 3»; mai una creatura: tutta la partita",
                 valori_di("senza_crea", dict(crea_prima=3)) == ["Your turn 1", "Your turn 2"]
                 and valori_di("senza_crea", dict(crea_prima=0))[-1] == "The whole game"))
    casi.append(("negativa: senza le azioni della partita nessuna soglia (non si sa)", valori_di("senza_crea", dict(crea_prima=None)) == []))
    vecchio_m = dict(_MANA)
    try:
        _MANA.clear(); _MANA.update(m1=dict(mano0=dict(n=[7, 6])), m2=dict(mano0=dict(n=[7, 7])), m3=dict(azioni=[[2, 2, "magia", 5, "I"], [4, 2, "magia", 6, "C"]]))
        casi.append(("il suo mulligan dalla sua mano al primo turno; la prima creatura al tuo turno (chi non comincia gioca i turni pari)",
                     suo_mulligan("m1", 1) == "1" and suo_mulligan("m2", 1) == "0" and suo_mulligan("m1", 2) == "0" and prima_creatura("m3", 2, False) == 2))
        casi.append(("negativa: senza la foto o le azioni non si sa", suo_mulligan("mx", 1) is None and prima_creatura("m1", 1, True) is None))
        pt = per_turno("m3", 2, False, 8)
        casi.append(("turno per turno: tu (non cominci) T1 istantaneo, T2 creatura, T3 e T4 niente; lui niente; i turni oltre la fine non ci sono",
                     pt.get("io1") == ["Instant"] and pt.get("io2") == ["Creature"] and pt.get("io4") == ["Nothing"] and "io5" not in pt
                     and pt.get("lui4") == ["Nothing"] and "lui5" not in pt))
        _MANA["m4"] = dict(azioni=[[1, 1, "magia", 7, "I"], [2, 1, "magia", 8, "I"]],
                          momenti=[["comb", 3, 1, None, dict(att=[[1, 2], [2, 2]], blocchi=[[9, [1]]])], ["comb", 4, 2, None, dict(att=[[5, 1]], blocchi=[])]])
        p4 = per_turno("m4", 2, False, 6)
        casi.append(("nel turno dell'altro: il suo istantaneo nel tuo turno 1; gli attacchi e le difese di tutti e due, turno per turno",
                     p4.get("lui1") == ["Instant"] and p4.get("luix1") == ["Instant"] and p4.get("io1") == ["Nothing"]
                     and p4.get("alui2") == ["2 creatures"] and p4.get("dio2") == ["Blocked"] and p4.get("aio2") == ["1 creature"]
                     and p4.get("dlui2") == ["No block"] and p4.get("aio1") == ["No attack"] and p4.get("dlui1") == ["Not attacked"]))
        casi.append(("negativa: il turno oltre la fine della partita non c'e' (ne' attacco ne' difesa)", "aio4" not in p4 and "dlui4" not in p4))
        _MANA["m5"] = dict(azioni=[], momenti=[["comb", 3, 1, None, dict(att=[[1, 2]], blocchi=[], aperte=2)], ["comb", 4, 2, None, dict(att=[[5, 1]], blocchi=[], aperte=0)]])
        p5 = per_turno("m5", 2, False, 6)
        casi.append(("le terre stappate di chi difende: lui attacca al suo turno 2 contro 2 tue stappate, tu al tuo 2 contro lui tappato",
                     p5.get("mlui2") == ["2+ untapped lands"] and p5.get("mio2") == ["0 untapped lands"] and p5.get("mio1") == ["No attack"]))
        casi.append(("negativa: un combattimento senza le terre (prima della VERSIONE 12) non da' il valore", "alui2" in p4 and "mlui2" not in p4))
        # i filtri situazionali dai replay (13 nov 2026): terre, vita e campo a fine turno, rimozioni, board wipe, contromagie
        fo_ = dict(v=[12, 4], c=[[[1, 0, 0, 2, 2, 10], [2, 0, 0, 1, 1, 11]], [[3, 0, 0, 3, 3, 20]]])
        _MANA["m6"] = dict(azioni=[[1, 1, "terra", 1, "L"], [3, 1, "terra", 1, "L"], [2, 2, "terra", 1, "L"], [4, 2, "terra", 1, "L"], [6, 2, "terra", 1, "L"]],
                          foto=[[5, 1, fo_]],
                          momenti=[["spell", 5, 1, fo_, dict(g=1, chi=1, ab=False, bers=[20], colpiti=[20], fatti=[], fuori=[[30, "pila", 2, 99]])],
                                   ["spell", 6, 2, fo_, dict(g=2, chi=2, ab=False, bers=[], colpiti=[10, 11, 12], fatti=[10, 11, 12], fuori=[])]])
        sr = situazioni_replay("m6", 1, True, 6)
        casi.append(("situazioni dai replay: le terre (tu corto di una al turno 3, lui in curva), vita e creature a fine del tuo turno 3, le vite piu' basse",
                     sr.get("terre_io3") == "1 short" and sr.get("terre_lui3") == "On curve" and sr.get("vita_t3") == "Ahead"
                     and sr.get("crea_t3") == "More creatures" and sr.get("vita_io") == "11-15" and sr.get("vita_lui") == "1-5"))
        casi.append(("le rimozioni: la tua toglie una sua creatura e contromaga; la sua spazza 3 permanenti, 2 tuoi (12 non e' in campo)",
                     sr.get("rim_io") == "1" and sr.get("counter_io") == "Yes" and sr.get("wipe_lui") == "Yes" and sr.get("rim_lui") == "2"
                     and sr.get("wipe_io") == "No" and sr.get("counter_lui") == "No"))
        casi.append(("negativa: senza le azioni della partita nessuna situazione", situazioni_replay("mx", 1, True, 6) == {}))
        q_ = datetime.datetime(2026, 11, 1)
        tr = [dict(quando=q_ + datetime.timedelta(hours=i), evento="QuickDraft_FRA_1", mazzo_id="d1", vinta=i != 3) for i in range(9)]
        casi.append(("i trofei: la settima vittoria dello stesso draft (con una sconfitta in mezzo) e' la nona partita", trofei(tr) == [8]))
        casi.append(("negativa: le partite costruite non danno trofei, e un Traditional basta a 3",
                     trofei([dict(x, evento="Ladder") for x in tr]) == [] and trofei([dict(x, evento="TradDraft_FRA_1") for x in tr]) == [3]))
        # le pescate e le giocate del turno (13 nov 2026): tu non cominci (seat 2); al tuo turno 1 peschi 1, al 2 tre (due extra), nel suo turno 2 una
        _NOMI_GRP.update({905: "Shock", 906: "Goblin"})
        _MANA["m7"] = dict(azioni=[[2, 2, "pesca", 0, ""], [3, 1, "pesca", 0, ""], [3, 2, "pesca", 0, ""], [4, 2, "pesca", 0, ""],
                                   [4, 2, "pesca", 0, ""], [4, 2, "pesca", 0, ""], [4, 2, "magia", 905, "I"], [4, 2, "magia", 906, "C"]])
        p7 = per_turno("m7", 2, False, 6)
        casi.append(("le pescate: lui (comincia) 0 al turno 1 e 1 al 2; tu 1 al turno 1 e 3 al 2; nel suo turno 2 una tua", p7.get("plui1") == ["0 draws"]
                     and p7.get("plui2") == ["1 draw"] and p7.get("pio1") == ["1 draw"] and p7.get("pio2") == ["3+ draws"] and p7.get("piox2") == ["1 draw"]))
        casi.append(("le extra in un turno: tu 2 (al turno 2) piu' quella nel suo turno; lui nessuna (il suo turno 1 senza pescata non e' una mancata)",
                     p7.get("peio") == ["1+ extra in one turn", "2+ extra in one turn"] and p7.get("pelui") == ["No extra draw"]))
        casi.append(("negativa: le extra «2+» non sono «3+», e senza le pescate nel log (VERSIONE 12) le chiavi delle pescate non ci sono",
                     not passa(dict(per_turno=p7), {"t_peio": "3+ extra in one turn"}) and passa(dict(per_turno=p7), {"t_peio": "1+ extra in one turn"})
                     and "pio1" not in per_turno("m4", 2, False, 6)))
        casi.append(("le giocate del turno: i tipi, uno per magia, nell'ordine dei tipi (niente piu' voci col costo)", p7.get("io2") == ["Creature", "Instant"]))
        _MANA["m12"] = dict(azioni=[[4, 2, "magia", 905, "I"], [4, 2, "magia", 905, "I"], [4, 2, "magia", 906, "C"]])
        p12 = per_turno("m12", 2, False, 6)
        casi.append(("due istantanei nello stesso turno sono «Instant», «Instant»: il filtro con due Instant passa, con tre no",
                     p12.get("io2") == ["Creature", "Instant", "Instant"] and passa(dict(per_turno=p12), {"t_io2": ["Instant", "Instant"]})
                     and not passa(dict(per_turno=p12), {"t_io2": ["Instant", "Instant", "Instant"]})))
        _NOMI_GRP.update({907: "Dragon", 908: "Owl"})
        _MANA["m8"] = dict(azioni=[[2, 2, "pesca", 907, ""], [3, 1, "pesca", 0, ""], [3, 1, "magia", 906, "C"], [4, 2, "pesca", 908, ""], [4, 2, "magia", 905, "I"]])
        cp_ = carte_partita(dict(partita="m8", inizia=False), 2, {"Shock": 1, "Goblin": 1, "Mountain": 1})
        casi.append(("le carte della partita: al tuo turno 1 la mano e la prima pescata, al 2 la pescata; in mano tutte; bloccate quelle mai lanciate; le sue",
                     cp_["pesc1"] == ["Dragon", "Goblin", "Shock"] and cp_["pesc2"] == ["Owl"] and cp_["in_mano"] == ["Dragon", "Goblin", "Owl", "Shock"]
                     and cp_["bloccate"] == ["Dragon", "Goblin", "Owl"] and cp_["sue_lanciate"] == ["Goblin"]))
        _MANA["m9"] = dict(azioni=[[4, 2, "magia", 905, "I"]])
        cp9 = carte_partita(dict(partita="m9", inizia=False), 2, {"Shock": 1, "Goblin": 1})
        casi.append(("negativa: le terre non entrano, e senza le pescate nel log la mano e le bloccate non si sanno (vuote)", "Mountain" not in cp_["in_mano"]
                     and cp9["in_mano"] == [] and cp9["bloccate"] == [] and cp9["pesc1"] == []))
        # il finisher: tu cominci (posto 1); al tuo turno 2 (Arena 3) lanci Shock e Goblin, il vantaggio salta da 0 a 10 e resta tuo
        fv_ = lambda v, mie: dict(v=v, c=[mie, []])
        gob = [906, 0, 0, 3, 3, 50]
        _MANA["m10"] = dict(azioni=[[3, 1, "magia", 905, "I"], [3, 1, "magia", 906, "C"]],
                            foto=[[1, 1, fv_([20, 20], [])], [2, 2, fv_([20, 20], [])], [3, 1, fv_([20, 16], [gob])], [4, 2, fv_([20, 16], [gob])],
                                  [5, 1, fv_([20, 10], [gob])]])
        f10 = carte_partita(dict(partita="m10", inizia=True, vinta=True), 1, {})
        casi.append(("il finisher: la giocata del turno col salto piu' grande dopo il quale resti avanti (Goblin + Shock, +10, il tuo turno 2)",
                     f10["finisher"] == ["Goblin", "Shock"] and f10["salto"] == 10 and f10["turno_svolta"] == 2))
        _MANA["m11"] = dict(_MANA["m10"], foto=_MANA["m10"]["foto"][:3] + [[4, 2, fv_([5, 16], [gob])], [5, 1, fv_([20, 10], [gob])]])
        f11 = carte_partita(dict(partita="m11", inizia=True, vinta=True), 1, {})
        casi.append(("negativa: in una sconfitta niente finisher; se dopo il salto torni sotto non e' decisivo, e il turno decisivo senza 2 carte giocate non da' niente",
                     carte_partita(dict(partita="m10", inizia=True, vinta=False), 1, {})["finisher"] == [] and f11["finisher"] == []))
        rf = [dict(vinta=True, finisher=["Goblin", "Shock"], salto=10), dict(vinta=True, finisher=["Goblin", "Shock", "Owl"], salto=20), dict(vinta=False, finisher=[])]
        fc = riga_carte(rf, "finisher")
        casi.append(("la riga Finishers: Goblin + Shock ha deciso 2 vittorie con un salto medio di 15, e il suo filtro e' Card in your finish con tutte e due",
                     (fc[0]["nomi"], fc[0]["n"], fc[0]["salto"], fc[0]["quota"]) == (("Goblin", "Shock"), 2, 15.0, 100.0)
                     and filtro_carta("finisher", fc[0]) == ("finisher", ["Goblin", "Shock"]) and all(c_["n"] >= 2 for c_ in fc)))
        casi.append(("la scelta multipla: tutte e due le voci nello stesso turno passano; una che manca no", multipla("t_io2") and multipla("t_luix3")
                     and not multipla("t_aio2") and passa(dict(per_turno=p7), {"t_io2": ["Instant", "Creature"]})
                     and not passa(dict(per_turno=p7), {"t_io2": ["Instant", "Instant"]}) and etichetta("t_io2", ["Instant", "Creature"])
                     == "Instant + Creature"))
        casi.append(("negativa: il filtro del turno sbagliato non passa (la creatura e' del tuo turno 2, non dell'1)",
                     passa(dict(per_turno=pt), {"t_io2": "Creature"}) and not passa(dict(per_turno=pt), {"t_io1": "Creature"})))
    finally:
        _MANA.clear(); _MANA.update(vecchio_m)
    casi.append(("i colori del tuo mazzo dalle magie (le terre no), come e' finita", colori_mazzo(["Goblin", "Owl", "Mountain"]) == "UR"
                 and colori_mazzo(["Mountain"]) == "C" and come_finita("ResultReason_Concede", True) == "Opponent conceded"
                 and come_finita("ResultReason_Concede", False) == "You conceded" and come_finita("ResultReason_Game", True) == "Played to the end"))
    # il win rate: le partite piu' recenti che insieme fanno quel win rate, dopo gli altri filtri
    w_r = [dict(vinta=v_, tipo="Constructed", mull=m_) for v_, m_ in zip([True, False] * 20 + [True] * 10, ["0", "1"] * 25)]      # 50%, poi 10 vinte
    g_ = finestra_wr(w_r, [70, True, False])
    casi.append(("≥ 70: dalle piu' recenti all'indietro finche' il win rate regge, il gruppo piu' lungo (le 10 vinte e 14 prima: 17 su 24)",
                 len(g_) == 24 and g_ == w_r[-24:] and 100 * sum(x["vinta"] for x in g_) / 24 >= 70))
    e_ = finestra_wr(w_r, [60, False, False])
    l_ = finestra_wr(w_r, [65, False, True])
    casi.append(("esatto 60: il win rate del gruppo arrotondato e' 60; ≤ 65: al massimo 65", len(e_) == 50 and round(100 * sum(x["vinta"] for x in e_) / 50) == 60
                 and l_ and 100 * sum(x["vinta"] for x in l_) / len(l_) <= 65))
    casi.append(("dopo gli altri filtri: con Mulligan 1 il gruppo e' fatto solo di partite con un mulligan", all(x["mull"] == "1" for x in filtra(w_r, {"mull": "1",
                 "wr_rif": [40, True, False]}, "Constructed")) and filtra(w_r, {"mull": "1", "wr_rif": [40, True, False]}, "Constructed")
                 and etichetta("wr_rif", [55, True, False]) == "≥ 55%"))
    g60 = filtra(w_r, {"wr_rif": [60, False, False]}, "Constructed")
    casi.append(("il win rate prima di Result: «60% e le vittorie» sono le vittorie del gruppo che fa il 60% (con Result prima sarebbero il 100%: nessuna)",
                 filtra(w_r, {"wr_rif": [60, False, False], "esito": "Won"}, "Constructed") == [x for x in g60 if x["vinta"]] and len(g60) == 50
                 and len([x for x in g60 if x["vinta"]]) == 30))
    casi.append(("negativa: un win rate che nessun gruppo di 10 partite raggiunge da' zero partite, e meno di 10 partite non bastano",
                 finestra_wr(w_r[:40], [99, True, False]) == [] and finestra_wr(w_r[-9:], [50, True, False]) == []))
    cr = [dict(vinta=True, mie_lanciate=["Shock", "Goblin"], in_mano=["Shock", "Goblin", "Owl"], bloccate=["Owl"]),
          dict(vinta=False, mie_lanciate=["Shock", "Shock"], in_mano=["Shock", "Owl", "Dragon"], bloccate=["Owl", "Dragon"]),
          dict(vinta=False, mie_lanciate=["Dragon"], in_mano=["Dragon"], bloccate=[])]
    cc_ = riga_carte(cr, "lanciate")
    casi.append(("le righe di Cards: Shock lanciata in 2 partite (una volta per partita) 50%, poi Dragon e Goblin in una",
                 [(c["nome"], c["n"], c["wr"]) for c in cc_] == [("Shock", 2, 50.0), ("Dragon", 1, 0.0), ("Goblin", 1, 100.0)]))
    bl_ = riga_carte(cr, "bloccate", minimo=2)
    casi.append(("Harder to cast: Owl rimasta in mano 2 volte su 2 (100%), Dragon 1 su 2 (50%), dalla piu' bloccata",
                 [(c["nome"], c["bloccata"], c["mano"]) for c in bl_] == [("Owl", 100, 2), ("Dragon", 50, 2)]))
    casi.append(("negativa: sotto il minimo di partite in mano una carta non entra fra le difficili", riga_carte(cr, "bloccate", minimo=3) == []))
    cm = [dict(vinta=v_, mano=m_, mie_lanciate=m_) for v_, m_ in [(True, ["Shock", "Goblin", "Mountain"])] * 3 + [(False, ["Shock", "Goblin"])]
          + [(True, ["Shock", "Owl"])] * 2 + [(False, ["Shock", "Owl"])] * 2]
    cp = coppie_carte(cm, "pesc1", minimo=4)
    casi.append(("le coppie della mano tenuta (dalla riga del turno 1): Goblin + Shock 3-1 prima di Owl + Shock 2-2, le terre fuori; il filtro e' Card in opening hand",
                 [(c["nomi"], c["n"], c["wr"]) for c in cp] == [(("Goblin", "Shock"), 4, 75.0), (("Owl", "Shock"), 4, 50.0)]
                 and filtro_carta("pesc1", cp[0]) == ("mano", ["Goblin", "Shock"]) and filtro_carta("lanciate", coppie_carte(cm, "lanciate", minimo=4)[0])
                 == ("lanciate", ["Goblin", "Shock"])))
    casi.append(("negativa: sotto il minimo di partite una coppia non c'e', e il filtro di una carta sola resta la sua chiave",
                 coppie_carte(cm, "pesc1", minimo=5) == [] and filtro_carta("in_mano", dict(nome="Shock")) == ("in_mano", "Shock")))
    _TAB.clear()
    vere = righe()
    # C1 · le terre contro il caso (13 nov 2026)
    pm = ipergeom(53, 22, 4)
    casi.append(("l'ipergeometrica: somma 1, la media e' n*K/N; negativa: K oltre N non c'e'", abs(sum(pm) - 1) < 1e-12
                 and abs(sum(j * q for j, q in enumerate(pm)) - 4 * 22 / 53) < 1e-12 and ipergeom(10, 11, 3) is None))
    pm6 = ipergeom(53, 22, 6)
    casi.append(("le voci: 0 terre su 6 pescate e' screw, 6 su 6 flood, 2-3 come previsto; negativa: con 1 pescata nessuna coda del 5%",
                 classe_fortuna(pm6, 0) == FORTUNA[0] and classe_fortuna(pm6, 6) == FORTUNA[4] and classe_fortuna(pm6, 2) == FORTUNA[2]
                 and classe_fortuna(pm6, 3) == FORTUNA[2] and classe_fortuna(ipergeom(53, 22, 1), 0) not in (FORTUNA[0], FORTUNA[4])))
    casi.append(("le prime mani: la migliore di 2 piu' stretta del regolamento e con la stessa somma",
                 abs(sum(mano_liscia(24, 60, 7, 2)) - 1) < 1e-9 and mano_liscia(24, 60, 7, 2)[3] > ipergeom(60, 24, 7)[3]
                 and mano_liscia(24, 60, 7, 2)[0] < ipergeom(60, 24, 7)[0]))
    casi.append(("il chi quadro: uguali p alto; negativa: 259 contro 233 su 489 mani non regge", chi2_p([10, 20, 30], [10, 20, 30]) > 0.9
                 and chi2_p([0, 12, 184, 259, 34, 0, 0, 0], [1.0, 28.1, 171.8, 233.5, 51.1, 3.5, 0.1, 0.0]) < 0.01))
    # una partita finta: mazzo di 60 con 24 terre (nomi veri dal database), le 7 con 2 terre, poi le pescate
    vero_nomi = None
    try:
        import condividi
        vero_nomi = condividi.nomi
        T, M = "Island", "Opt"
        condividi.nomi = lambda gg: (dict(collections.Counter(gg)) if gg and isinstance(gg[0], str) else {}) if gg is not None else None
        _NOMI_GRP.update({901: T, 902: M})
        mazzo = [T] * 24 + [M] * 36
        p_ = dict(mani=[[T, T, M, M, M, M, M]], carte=mazzo, seat=1, evento="Ladder")
        # cominci tu: il tuo turno 5 e' il 9 di Arena; pescate al 3, 5, 7, 9 (una per turno, niente al primo): tutte magie = 4 pescate, 0 terre
        _MANA["fx1"] = dict(azioni=[[t, 1, "pesca", 902, ""] for t in (3, 5, 7, 9, 11, 13)])
        f1 = fortuna(p_, dict(partita="fx1", inizia=True, turni=14), dict(collections.Counter(mazzo)))
        t5 = f1["turni"][5]
        casi.append(("una partita: al tuo turno 5 (il 9 di Arena) 4 pescate, 0 terre, attese 4*22/53; turno 7 sei pescate, 0 terre = screw",
                     t5["k"] == 4 and t5["x"] == 0 and abs(t5["e"] - 4 * 22 / 53) < 1e-9 and f1["turni"][7]["classe"] == FORTUNA[0]
                     and f1["mano0"] == 2 and f1["D"] == 60 and f1["L"] == 24 and f1["bo3"] is False))
        casi.append(("negativa: la partita finita al tuo turno 6 non ha il turno 7; il Bo3 si riconosce",
                     7 not in fortuna(p_, dict(partita="fx1", inizia=True, turni=12), dict(collections.Counter(mazzo)))["turni"]
                     and fortuna(dict(p_, evento="Traditional_Ladder"), dict(partita="fx1", inizia=True, turni=14), dict(collections.Counter(mazzo)))["bo3"]))
        _MANA["fx2"] = dict(azioni=[[t, 1, "pesca", 0 if t == 5 else 901, ""] for t in (3, 5, 7, 9)])
        casi.append(("negativa: una tua pescata senza nome (il log riassunto) toglie il turno, non lo conta sbagliato",
                     5 not in fortuna(p_, dict(partita="fx2", inizia=True, turni=14), dict(collections.Counter(mazzo)))["turni"]))
        _MANA["fx3"] = dict(azioni=[[3, 1, "magia", 902, "I"]])
        casi.append(("negativa: una partita letta prima delle pescate non ha turni", fortuna(p_, dict(partita="fx3", inizia=True, turni=14),
                                                                                     dict(collections.Counter(mazzo)))["turni"] == {}))
        rr = [dict(fortuna=f1), dict(fortuna=None)]
        k_ = contro_il_caso(rr)
        casi.append(("contro il caso: una partita, le terre e le attese di quel turno, le voci che sommano a 1 partita attesa, le mani",
                     k_["turni"][5]["partite"] == 1 and k_["turni"][5]["x"] == 0 and abs(sum(a for _o, a in k_["turni"][5]["classi"].values()) - 1) < 1e-9
                     and k_["mani"]["oss"][2] == 1 and k_["mani"]["bo1"] == 1))
        casi.append(("il filtro: «Lands drawn by your turn 7 · vs chance» = screw prende la partita; negativa: «flood» no",
                     passa(dict(fortuna=f1), {"luck7": FORTUNA[0]}) and not passa(dict(fortuna=f1), {"luck7": FORTUNA[4]})))
    finally:
        if vero_nomi:
            condividi.nomi = vero_nomi
        for k in ("fx1", "fx2", "fx3"):
            _MANA.pop(k, None)
        _NOMI_GRP.pop(901, None); _NOMI_GRP.pop(902, None)
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
