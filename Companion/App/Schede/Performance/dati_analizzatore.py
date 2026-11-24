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
NOTE = account.lega(globals(), "NOTE", "performance_note.json")      # R3: le note sulle partite (13 nov 2026)
SESSIONE_ORE = 1.0          # un'ora senza partite chiude la sessione
RANGHI = ("Bronze", "Silver", "Gold", "Platinum", "Diamond", "Mythic")
FASCE = (("Night (0-6)", 0, 6), ("Morning (6-12)", 6, 12), ("Afternoon (12-18)", 12, 18), ("Evening (18-24)", 18, 24))
LUNGHE = (("Turns 1-5", 1, 5), ("Turns 6-8", 6, 8), ("Turns 9-11", 9, 11), ("Turns 12+", 12, 999))
DATE = (("Last 7 days", 7), ("Last 30 days", 30), ("Last 90 days", 90))
NOMI_FMT = {"standard": "Standard", "alchemy": "Alchemy", "explorer": "Explorer", "historic": "Historic", "timeless": "Timeless", "brawl": "Brawl",
            "standard_brawl": "Standard Brawl", "precon": "Dual Color Precons", "jumpin": "Jump In", "limited": "Limited"}


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
       ("io_tutto_aperto", "You attacked with everything into 2+ untapped lands"),
       # gli attacchi mancati (14 nov 2026): mana_aperto.finestre_non_att, dalle foto di fine turno
       ("io_non_att_chiuso", "You had an attacker ready, the opponent was tapped out with no untapped blockers, and you did not attack"),
       ("io_letale_mancato", "Your board had lethal through their untapped blockers and the opponent survived the turn")]
_MANA = {}      # {matchId: dato di mana_aperto}, riempito da righe()
NOME_SIT = dict(SIT)

# Il «solito» di ogni mazzo viene solo dalle partite di quel mazzo (UpgradePlan01 passo 1, Autore, 20 nov 2026: «ogni mazzo deve confrontarsi con se
# stesso», «Sì, montalo»; la prova: Note/UpgradePlan01_Passo1.md). Il mazzo e' il nome del tuo mazzo (nel Limited la coppia di colori), dentro il tipo
# (Constructed o Limited). Sotto MINIMO_MAZZO partite il mazzo non ha ancora un solito: l'EV vero resta, il confronto no.
MINIMO_MAZZO = 10


def chiave_mazzo(x):
    return (x.get("tipo"), (x.get("mio") or "").strip())


def per_mazzo(base):
    """{chiave del mazzo: [partite]} dalle partite base."""
    out = collections.defaultdict(list)
    for x in base:
        out[chiave_mazzo(x)].append(x)
    return out
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
        # la seconda meta' di una carta che la collezione conosce col solo nome davanti (18 nov 2026, Autore: «perche' di alcune carte come flameshape non
        # abbiamo immagini?»): l'avventura di Gandalf, Goblins' Bane (Flameshape), il presagio di Scavenger Regent (Exude Toxin). Arena scrive la meta'
        # lanciata; dal database di Arena (isSecondaryCard, linkedFaces) si risale alla carta, cosi' Cards la conta con lei e ne mostra l'immagine
        try:
            import db_carte
            tab = _tabella()
            for r_ in db_carte.carte():
                if not r_.get("isSecondaryCard") or not r_.get("linkedFaces"):
                    continue
                seconda = nome_grp(r_["grpid"])
                if not seconda or seconda in tab or seconda in _INTERI:
                    continue
                prima = nome_grp(r_["linkedFaces"][0])
                if prima and prima in tab:
                    _INTERI[seconda] = _INTERI.get(prima, prima)
        except Exception:       # noqa: BLE001 - senza il database le meta' restano col loro nome
            pass
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


# la mano iniziale descritta riga per riga (18 nov 2026, Autore: «se voglio sapere da advanced filters quali carte ho nella mano di partenza quel tab va
# rivisto perche' da troppe opzioni, studia la migliore soluzione di quel tab affinche' possa descrivere una mano generica o specifica nel dettaglio di ogni
# carta»): ogni riga e' quante (almeno, esattamente, nessuna) · di cosa (un tipo, un ruolo, qualunque carta) · quale carta (facoltativa) · che valore di mana
# (facoltativo). Il filtro «mano_req» e' una lista di «quante|cosa|carta|mv»; servono tutte le righe (una mano che le ha tutte).
MANO_QUANTI = (("1+", "At least 1"), ("2+", "At least 2"), ("3+", "At least 3"), ("4+", "At least 4"), ("0", "None (0)"), ("=1", "Exactly 1"),
               ("=2", "Exactly 2"), ("=3", "Exactly 3"), ("=4", "Exactly 4"), ("=5", "Exactly 5"))
MANO_COSA = ("Any card", "Land", "Spell (not a land)", "Creature", "Instant", "Sorcery", "Artifact", "Enchantment", "Planeswalker", "Battle", "Removal",
             "Card draw", "Counterspell", "Combat trick")
MANO_MV = (("0", "mana value 0"), ("1", "mana value 1"), ("2", "mana value 2"), ("3", "mana value 3"), ("4", "mana value 4"), ("5", "mana value 5"),
           ("6", "mana value 6+"), ("-2", "mana value 2 or less"), ("-3", "mana value 3 or less"))
MANO_MV_QUALSIASI = "any mana value"


def _mano_e(nome, cosa, carta, mv):
    """Se una carta della mano conta per una riga del costruttore."""
    if carta and nome_intero(carta) != nome_intero(nome):
        return False
    c = _carta(nome) or {}
    tipo = (c.get("tipo") or "").split(" // ")[0]
    terra = e_terra(nome)
    if mv:
        if terra:
            return False
        v = c.get("cmc") or 0
        if mv.startswith("-"):
            if v > int(mv[1:]):
                return False
        elif mv == "6":
            if v < 6:
                return False
        elif v != int(mv):
            return False
    if cosa in (None, "Any card"):
        return True
    if cosa == "Land":
        return terra
    if terra:
        return False
    if cosa == "Spell (not a land)":
        return True
    if cosa in ("Creature", "Instant", "Sorcery", "Artifact", "Enchantment", "Planeswalker", "Battle"):
        return cosa in tipo
    return ruolo_magia(nome) == {"Removal": "Removal", "Card draw": "Card draw", "Counterspell": "Counterspell", "Combat trick": "Combat trick"}.get(cosa)


def mano_soddisfa(conta, reqs):
    """conta: la mano tenuta {nome: copie}; reqs: le righe «quante|cosa|carta|mv». None se la mano non si conosce."""
    if not conta:
        return None
    for q in reqs or []:
        quante, cosa, carta, mv = (str(q).split("|") + ["", "", "", ""])[:4]
        n = sum(k for nm, k in conta.items() if _mano_e(nm, cosa or None, carta or None, mv or None))
        if quante.endswith("+"):
            if n < int(quante[:-1]):
                return False
        elif quante.startswith("="):
            if n != int(quante[1:]):
                return False
        elif n != int(quante or 0):
            return False
    return True


def testo_mano(q):
    """Una riga del costruttore detta: «At least 2 Creature · Shock · mana value 2 or less»."""
    quante, cosa, carta, mv = (str(q).split("|") + ["", "", "", ""])[:4]
    pezzi = [dict(MANO_QUANTI).get(quante, quante) + " " + (cosa or "Any card")]
    if carta:
        pezzi.append(carta)
    if mv:
        pezzi.append(dict(MANO_MV).get(mv, mv))
    return " · ".join(pezzi)


def magie_in_mano(tenuta, tipo):
    """Le magie di un tipo («Instant», «Sorcery») nella mano tenuta: «0», «1», «2+»; None se la mano non si conosce."""
    if not tenuta:
        return None
    n = sum(q for nm, q in tenuta.items() if (c := _carta(nm)) and tipo in (t_ := (c.get("tipo") or "").split(" // ")[0]) and "Land" not in t_)
    return str(n) if n < 2 else "2+"


TURNI_FILTRO = 10       # i filtri turno per turno: i primi 10 turni di ognuno (erano 5 fino al 14 nov 2026), poi «dal turno 11» e «qualunque turno»
NOMI_TIPO = {"C": "Creature", "I": "Instant", "S": "Sorcery", "E": "Enchantment", "A": "Artifact", "P": "Planeswalker", "B": "Battle"}
ORDINE_TIPI = ("Creature", "Instant", "Sorcery", "Enchantment", "Artifact", "Planeswalker", "Battle", "Nothing")


ORDINE_ATT = ("No attack", "1 creature", "2 creatures", "3+ creatures")
ORDINE_DIF = ("Not attacked", "Blocked", "No block")
ORDINE_APERTE = ("No attack", "0 untapped lands", "1 untapped land", "2+ untapped lands")
ORDINE_PESCATE = ("0 draws", "1 draw", "2 draws", "3+ draws")
ORDINE_PESCATE_X = ("0 draws", "1 draw", "2+ draws")
ORDINE_EXTRA = ("No extra draw", "1+ extra in one turn", "2+ extra in one turn", "3+ extra in one turn")
ORDINE_SCELTA = ("Couldn't attack", "Didn't attack", "Attacked with some", "Attacked with everything", "Held back, nothing to block")      # = mana_aperto.SCELTE_ATTACCO
ORDINE_MANA = ("All mana used", "1 mana left", "2+ mana left")      # il mana lasciato nel proprio turno («u»)
ORDINE_EFF = ("90%+ of your mana", "70-90%", "50-70%", "Under 50%")       # l'efficienza del mana nei primi 5 turni («eff»)


def per_turno(match_id, seat, inizia, turni, grezzo=False):
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
    # tutti i turni della partita (14 nov 2026, la pagella dell'enciclopedia: «in qualunque turno», «dal turno 6 in poi»): i filtri del turno N arrivano a
    # TURNI_FILTRO, e ogni famiglia ha anche «qualunque turno» (A) e «dal turno TURNI_FILTRO+1» (L), fatti dopo da turni_estesi
    for t in range(1, (turni or 0) + 1):
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
        for t in range(1, (turni or 0) + 1):
            chi, n = di_turno(t), (t + 1) // 2
            mie, sue = pescate[(chi, t)], pescate[(altro[chi], t)]
            out[f"p{chi}{n}"] = ORDINE_PESCATE[min(mie, 3)]
            out[f"p{altro[chi]}x{n}"] = ORDINE_PESCATE_X[min(sue, 2)]
            normale = 0 if (chi == primo and t == 1) else 1        # chi comincia non pesca al suo primo turno (103.8a)
            if n <= TURNI_FILTRO:       # le pescate extra: nei turni dei filtri, come prima
                extra[chi] = max(extra[chi], mie - normale)
                extra[altro[chi]] = max(extra[altro[chi]], sue)
        for chi, e in extra.items():
            out[f"pe{chi}"] = tuple(ORDINE_EXTRA[i] for i in range(1, min(e, 3) + 1)) or (ORDINE_EXTRA[0],)
        # le carte pescate per nome (16 nov 2026, Autore: «per ogni filtro che parla di carte in advanced filter dobbiamo sempre poter scrivere alla fine una
        # carta specifica se la conosciamo»): «np{chi}{x}{n}»; dell'avversario Arena non scrive la carta (grpId 0), quindi niente
        for t, s_, cosa, g_, _tp in d["azioni"]:
            if cosa == "pesca" and g_ and (not turni or t <= turni):
                chi = "io" if s_ == seat else "lui"
                nome = nome_intero(nome_grp(g_) or "")
                if nome:
                    out.setdefault(f"np{chi}{'' if di_turno(t) == chi else 'x'}{(t + 1) // 2}", []).append(nome)
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
    # la fase di ogni magia (VERSIONE 14 di mana_aperto): le «fasi» sono nello stesso ordine delle magie lanciate, una per magia; si appaiano per turno,
    # posto e carta, cosi' una riga che manca non sposta le altre
    coda, coda_p = collections.defaultdict(list), collections.defaultdict(list)
    for t, s_, g_, f_ in d.get("fasi") or []:
        coda[(t, s_, g_)].append(f_)
    for t, s_, g_, p_ in d.get("passi_lanci") or []:      # il passo (mana_aperto VERSIONE 22)
        coda_p[(t, s_, g_)].append(p_)
    for t, s_, cosa, g_, tipi in d["azioni"]:
        if cosa != "magia":
            continue
        fq, pq = coda.get((t, s_, g_)), coda_p.get((t, s_, g_))
        fase = FASE_ARENA.get(fq.pop(0)) if fq else None
        passo = PASSO_ARENA.get(pq.pop(0)) if pq else None
        codici = [c_ for c_ in (fase, passo) if c_]          # una magia nel combattimento e' in «c» e nel suo passo
        chi = "io" if s_ == seat else "lui"
        k = f"{chi}{(t + 1) // 2}" if di_turno(t) == chi else f"{chi}x{(t + 1) // 2}"
        if k not in out or not codici:
            continue
        nome = nome_intero(nome_grp(g_) or "") if g_ not in SENZA_FACCIA else ""
        for fc in dict.fromkeys(codici):
            out.setdefault(f"k{fc}{k}", []).extend(NOMI_TIPO[c] for c in dict.fromkeys(tipi or "") if c in NOMI_TIPO)
            if nome:
                out.setdefault(f"k{fc}n{k}", []).append(nome)
    for kind, t, att, _f, info in d.get("momenti") or []:
        if kind != "comb" or not info or not info.get("att"):
            continue
        chi, n = ("io" if att == seat else "lui"), (t + 1) // 2
        if f"a{chi}{n}" in out:
            na = len(info["att"])
            out[f"a{chi}{n}"] = "1 creature" if na == 1 else "2 creatures" if na == 2 else "3+ creatures"
            out[f"d{altro[chi]}{n}"] = "Blocked" if info.get("blocchi") else "No block"
            # chi ha attaccato e chi ha bloccato, per nome (16 nov 2026): «na{chi}{n}», «nd{chi}{n}» (la difesa sta nel turno dell'altro, come «d»)
            per_id = {z[5]: z[0] for lato in ((_f.get("c") if isinstance(_f, dict) else None) or []) for z in lato if len(z) > 5}
            for a_ in info["att"]:
                nm_ = nome_intero(nome_grp(per_id.get(a_[0])) or "") if per_id.get(a_[0]) else ""
                if nm_:
                    out.setdefault(f"na{chi}{n}", []).append(nm_)
            for b_ in info.get("blocchi") or []:
                nm_ = nome_intero(nome_grp(per_id.get(b_[0])) or "") if per_id.get(b_[0]) else ""
                if nm_:
                    out.setdefault(f"nd{altro[chi]}{n}", []).append(nm_)
            ap = info.get("aperte")
            if ap is None:          # un combattimento letto prima della VERSIONE 12: le terre di chi difende non si sanno
                out.pop(f"m{chi}{n}", None)
            else:
                out[f"m{chi}{n}"] = "0 untapped lands" if ap == 0 else "1 untapped land" if ap == 1 else "2+ untapped lands"
    # il mana lasciato nel proprio turno (14 nov 2026, la pagella dell'enciclopedia, V27 della 1-6): le terre a fine turno meno il valore di mana delle magie
    # lanciate nel turno; «u{chi}{n}». Grado C: non vede le abilita' pagate, le riduzioni di costo, le fonti che non sono terre
    spese = collections.Counter()
    for t, s_, cosa, g_, _tp in d["azioni"]:
        if cosa == "magia" and di_turno(t) == ("io" if s_ == seat else "lui"):
            c_ = (_carta(nome_grp(g_) or "") or {}).get("cmc") if g_ not in SENZA_FACCIA else None
            spese[t] += c_ or 0
    for t, _att, _stap, tot in d.get("fine") or []:
        if turni and t > turni:
            continue
        resto = max(0, (tot or 0) - spese[t])
        out[f"u{di_turno(t)}{(t + 1) // 2}"] = ORDINE_MANA[min(resto, 2)]
    # l'efficienza del mana nei primi 5 turni di ognuno: il mana speso (al massimo le terre) sulle terre, turno per turno («eff{chi}»)
    for chi_ in ("io", "lui"):
        tt = [(min(spese[t], tot or 0), tot or 0) for t, _a, _s, tot in d.get("fine") or [] if di_turno(t) == chi_ and (t + 1) // 2 <= 5 and (tot or 0) > 0]
        if tt:
            e_ = 100 * sum(a_ for a_, _b in tt) / sum(b_ for _a, b_ in tt)
            out[f"eff{chi_}"] = ORDINE_EFF[0] if e_ >= 90 else ORDINE_EFF[1] if e_ >= 70 else ORDINE_EFF[2] if e_ >= 50 else ORDINE_EFF[3]
    import mana_aperto as MA
    for t, scelta in MA.scelte_attacco(d).items():      # la scelta d'attacco (V3): «q{chi}{n}»
        if not turni or t <= turni:
            out[f"q{di_turno(t)}{(t + 1) // 2}"] = scelta
    out.update(campo_inizio_turno(d, seat, di_turno, turni))
    out.update(ruoli_turno(d, seat, di_turno, turni))
    out = {k: [v] if isinstance(v, str) else list(v) if isinstance(v, tuple) else (sorted(v, key=ordine_lancio) if v else ["Nothing"])
           for k, v in out.items()}       # le magie del turno: una lista coi tipi ripetuti, in ordine; «Nothing» se niente
    return out if grezzo else turni_estesi(out)      # grezzo: un turno per chiave, anche oltre TURNI_FILTRO (spot_filtri)


# ------------------------------------------------------------------ Board: il campo all'inizio di ogni turno (16 nov 2026, Autore: «credo che nel leak finder
# ci manchi un presupposto importante: la condizione in cui si trova il board per noi e per oppo ... se io volessi sapere se a t3 con una mia creatura in campo
# e nessuna di oppo io faccio bene a giocare una creatura o piuttosto a lanciare per un extra pescata pre combat?», poi «tenere you e opponent e aggiungere
# board / da board derivano tutte le aree del board che abbiamo in gioco», «si vai»). Il campo all'inizio del turno t e' la foto di fine del turno t-1
# (mana_aperto, momenti «fine»): permanenti con forza e se sono tappati, vite, mano, cimitero, esilio. Il grimorio nelle foto non c'e'.
# Le chiavi, nello schema di per_turno: «b{area}{chi}{x}{n}» = l'area di chi all'inizio del turno n di chi (x: del turno dell'altro), e
# «b{area}vio{x}{n}» = chi e' avanti in quell'area, dal tuo posto, all'inizio del tuo turno n (x: del suo). Le lettere delle aree non sono i, o, l, u
# (la regola delle chiavi le leggerebbe come «io», «lui»).
# 16 nov 2026, seconda versione (Autore: «other permanents dovrebbe avere l'elenco di tutti i tipi di permanente», e prima «non abbiamo contesto di
# cimitero, incantesimi o creature incantate»): i tipi di permanente della regola 110.4 uno per uno (creature, terre, artefatti, incantesimi, planeswalker,
# battaglie) piu' aure ed equipaggiamenti (303.4, 301.5); il cimitero per tipo e coi tipi di carta (il delirium). Il tipo e' quello stampato (il database
# delle carte): una terra animata resta una terra, una creatura che non lo e' piu' resta una creatura (grado C).
_N4 = lambda cosa, una=None: (f"0 {cosa}", f"1 {una or cosa}", f"2 {cosa}", f"3+ {cosa}")
BOARD_AREE = (("c", "Creatures", ("0 creatures", "1 creature", "2 creatures", "3+ creatures")),
              ("f", "Power on the battlefield", ("0 power", "1-2 power", "3-5 power", "6+ power")),
              ("t", "Lands", ("0-1 lands", "2 lands", "3 lands", "4 lands", "5+ lands")),
              ("s", "Untapped lands", ("0 untapped", "1 untapped", "2 untapped", "3+ untapped")),
              ("k", "Artifacts", _N4("artifacts", "artifact")),
              ("q", "Equipment", _N4("equipment")),
              ("y", "Enchantments", _N4("enchantments", "enchantment")),
              ("r", "Auras", _N4("auras", "aura")),
              ("w", "Planeswalkers", _N4("planeswalkers", "planeswalker")),
              ("z", "Battles", _N4("battles", "battle")),
              ("m", "Cards in hand", ("0-1 cards", "2-3 cards", "4-5 cards", "6+ cards")),
              ("g", "Graveyard", ("0 cards", "1-2 cards", "3-5 cards", "6+ cards")),
              ("j", "Creatures in the graveyard", _N4("creatures", "creature")),
              ("h", "Instants and sorceries in the graveyard", _N4("instants and sorceries", "instant or sorcery")),
              ("d", "Card types in the graveyard", ("0-1 types", "2-3 types", "4+ types (delirium)")),
              ("e", "Exile", ("0 cards", "1-2 cards", "3+ cards")),
              ("v", "Life", ("1-5 life", "6-10 life", "11-15 life", "16-20 life", "21+ life")))
# le sottovoci della fase Board (le aree vicine insieme, perche' i pulsanti stiano in una riga)
BOARD_GRUPPI = (("Creatures", ("c", "f")), ("Lands", ("t", "s")), ("Other permanents", ("k", "q", "y", "r", "w", "z")), ("Hand", ("m",)),
                ("Graveyard, exile", ("g", "j", "h", "d", "e")), ("Life", ("v",)))
BOARD_AVANTI = ("c", "f", "t", "k", "y", "w", "m", "g", "v")           # le aree dove «chi e' avanti» ha senso
ORDINE_AVANTI = ("You're ahead", "Even", "Opponent's ahead")
SOGLIE_BOARD = dict(c=(1, 2, 3), f=(1, 3, 6), t=(2, 3, 4, 5), s=(1, 2, 3), k=(1, 2, 3), q=(1, 2, 3), y=(1, 2, 3), r=(1, 2, 3), w=(1, 2, 3), z=(1, 2, 3),
                    m=(2, 4, 6), g=(1, 3, 6), j=(1, 2, 3), h=(1, 2, 3), d=(2, 4), e=(1, 3), v=(6, 11, 16, 21))
TIPI_CARTA = ("Artifact", "Battle", "Creature", "Enchantment", "Instant", "Kindred", "Land", "Planeswalker", "Sorcery")      # 205.2a, per il delirium


def _fascia_board(n, soglie):
    """L'indice della fascia: soglie = i limiti bassi delle fasce dalla seconda in poi."""
    return sum(1 for s_ in soglie if n >= s_)


def _misure_campo(f, lato):
    """Le misure di un lato di una foto di fine turno: {area: numero} (None dove la foto non lo dice)."""
    c = (f.get("c") or [[], []])[lato]
    tipo = lambda g: (_carta(nome_grp(g) or "") or {}).get("tipo") or ""
    terre = [z for z in c if e_terra(nome_grp(z[0]) or "")]
    crea = [z for z in c if len(z) > 4 and z[3] is not None and not e_terra(nome_grp(z[0]) or "")]
    altri = [(z, tipo(z[0]).split(" // ")[0]) for z in c if z not in terre and z not in crea]
    conta = lambda parola: sum(1 for _z, tp in altri if parola in tp)
    cim = [tipo(g).split(" // ")[0] for g in (f.get("g") or [[], []])[lato] if g]
    return dict(c=len(crea), f=sum(max(0, z[3] or 0) for z in crea), t=len(terre), s=sum(1 for z in terre if not z[1]),
                k=conta("Artifact"), q=conta("Equipment"), y=conta("Enchantment"), r=conta("Aura"), w=conta("Planeswalker"), z=conta("Battle"),
                m=(f.get("n") or [None, None])[lato], g=len((f.get("g") or [[], []])[lato]),
                j=sum(1 for tp in cim if "Creature" in tp), h=sum(1 for tp in cim if "Instant" in tp or "Sorcery" in tp),
                d=len({w_ for tp in cim for w_ in TIPI_CARTA if w_ in tp}), e=len((f.get("e") or [[], []])[lato]),
                v=(f.get("v") or [None, None])[lato])


def _nomi_campo(f, lato):
    """Le carte di un lato di una foto di fine turno, per area del Board: {area: [nomi]} (16 nov 2026: la carta specifica nelle righe del Board). Le aree
    senza carte (forza, stappate, tipi nel cimitero, vita) non ci sono; la mano solo se la foto la dice (la sua no)."""
    nome = lambda g: nome_intero(nome_grp(g) or "") if g else ""
    c = (f.get("c") or [[], []])[lato]
    tipo = lambda g: ((_carta(nome_grp(g) or "") or {}).get("tipo") or "").split(" // ")[0]
    out = {k: [] for k in ("c", "t", "k", "q", "y", "r", "w", "z", "m", "g", "j", "h", "e")}
    for z in c:
        n_ = nome(z[0])
        if not n_ or z[2]:          # le pedine non hanno un nome di carta da cercare
            continue
        if e_terra(nome_grp(z[0]) or ""):
            out["t"].append(n_)
        elif len(z) > 4 and z[3] is not None:
            out["c"].append(n_)
        else:
            tp = tipo(z[0])
            for a_, parola in (("k", "Artifact"), ("q", "Equipment"), ("y", "Enchantment"), ("r", "Aura"), ("w", "Planeswalker"), ("z", "Battle")):
                if parola in tp:
                    out[a_].append(n_)
    out["m"] = [nome(g) for g in (f.get("m") or [[], []])[lato] if nome(g)]
    for g in (f.get("g") or [[], []])[lato]:
        n_ = nome(g)
        if n_:
            out["g"].append(n_)
            tp = tipo(g)
            if "Creature" in tp:
                out["j"].append(n_)
            if "Instant" in tp or "Sorcery" in tp:
                out["h"].append(n_)
    out["e"] = [nome(g) for g in (f.get("e") or [[], []])[lato] if nome(g)]
    return out


AREE_CON_CARTE = ("c", "t", "k", "q", "y", "r", "w", "z", "m", "g", "j", "h", "e")


def campo_inizio_turno(d, seat, di_turno, turni):
    """Le famiglie «b...» di per_turno: il campo di tutti e due all'inizio di ogni turno, dalla foto di fine del turno prima (il turno 1 parte dal campo
    vuoto: creature, forza, terre, altri permanenti a zero; mano, vite, cimitero ed esilio non si sanno). Chi e' di turno ha appena stappato: tutte le sue
    terre sono stappate."""
    fine = {m[1]: m[3] for m in d.get("momenti") or [] if m[0] == "fine" and isinstance(m[3], dict)}
    out = {}
    a, b = seat - 1, 2 - seat
    for t in range(1, (turni or 0) + 1):
        chi_t, n = di_turno(t), (t + 1) // 2
        if t == 1:
            vuoto = dict(c=0, f=0, t=0, s=0, k=0, q=0, y=0, r=0, w=0, z=0, g=0, j=0, h=0, d=0, e=0)
            mis = {"io": dict(vuoto), "lui": dict(vuoto)}
        else:
            f = fine.get(t - 1)
            if f is None:
                continue
            mis = {"io": _misure_campo(f, a), "lui": _misure_campo(f, b)}
            mis[chi_t]["s"] = mis[chi_t]["t"]
            for chi, lato in (("io", a), ("lui", b)):        # le carte per nome: «nb{area}{chi}{x}{n}»
                x_ = "" if chi == chi_t else "x"
                for k, nomi_ in _nomi_campo(f, lato).items():
                    if nomi_:
                        out[f"nb{k}{chi}{x_}{n}"] = sorted(nomi_)
        for chi in ("io", "lui"):
            x_ = "" if chi == chi_t else "x"
            for k, _nome, voci in BOARD_AREE:
                v = mis[chi].get(k)
                if v is not None:
                    out[f"b{k}{chi}{x_}{n}"] = voci[_fascia_board(v, SOGLIE_BOARD[k])]
        x_ = "" if chi_t == "io" else "x"
        for k in BOARD_AVANTI:
            vi, vl = mis["io"].get(k), mis["lui"].get(k)
            if vi is not None and vl is not None:
                out[f"b{k}vio{x_}{n}"] = ORDINE_AVANTI[0 if vi > vl else 1 if vi == vl else 2]
    return out


# il ruolo di ogni magia lanciata e quando, rispetto al combattimento del turno (stesso giorno): «r{chi}{x}{n}», una lista con due voci per magia, il ruolo
# («Card draw») e il ruolo col momento («Card draw · before combat»), cosi' una tendina col solo ruolo vale in qualunque momento. Dal testo (grado C).
RUOLI = ("Creature", "Removal", "Counterspell", "Card draw", "Combat trick", "Other spell")
MOMENTI_RUOLO = ("before combat", "in combat", "after combat")
ORDINE_RUOLI = RUOLI + tuple(f"{r_} · {m_}" for r_ in RUOLI for m_ in MOMENTI_RUOLO) + ("Nothing",)
_RX_PESCA = re.compile(r"draws? (?:a|one|two|three|\d+) cards?|\bscry \d|\bsurveil \d", re.I)
_RX_TRUCCO = re.compile(r"target creature (?:you control )?gets \+|\bgains? (?:hexproof|indestructible|protection|first strike|double strike|trample|lifelink|"
                        r"deathtouch)", re.I)


def ruolo_magia(n):
    """Il ruolo di una magia dal tipo e dal testo, in quest'ordine: creatura, rimozione (le regole VERA di variabili_c), contromagia, pescata (draw, scry,
    surveil), trucco da combattimento, altro."""
    c = _carta(n or "") or {}
    tipo, testo = c.get("tipo") or "", c.get("testo") or ""
    if "Creature" in tipo.split(" // ")[0]:
        return "Creature"
    import variabili_c as VC
    if VC.rimozione(n):
        return "Removal"
    if "counter target" in testo.lower():
        return "Counterspell"
    if _RX_PESCA.search(testo):
        return "Card draw"
    if "Instant" in tipo and _RX_TRUCCO.search(testo):
        return "Combat trick"
    return "Other spell"


def ruoli_turno(d, seat, di_turno, turni):
    """Le famiglie «r...» di per_turno, dalle «fasi» di mana_aperto (ogni magia col suo turno e la fase di Arena); «Nothing» senza magie."""
    out = {}
    for t in range(1, (turni or 0) + 1):
        chi_t, n = di_turno(t), (t + 1) // 2
        out[f"r{chi_t}{n}"] = []
        out[f"r{'lui' if chi_t == 'io' else 'io'}x{n}"] = []
    for t, s_, g_, fase in d.get("fasi") or []:
        if (turni and t > turni) or g_ in SENZA_FACCIA:
            continue
        chi = "io" if s_ == seat else "lui"
        k = f"r{chi}{'' if di_turno(t) == chi else 'x'}{(t + 1) // 2}"
        if k not in out:
            continue
        r_ = ruolo_magia(nome_grp(g_))
        m_ = "in combat" if fase == "Phase_Combat" else "after combat" if fase in ("Phase_Main2", "Phase_Ending") else "before combat"
        out[k] += [r_, f"{r_} · {m_}"]
        # il nome della carta (16 nov 2026, Autore: «in ogni tendina in cui possiamo dire di aver castato qualcosa dobbiamo avere una tendina in piu' per
        # inserire il nome specifico della carta se vogliamo»): la famiglia «n» per le righe dei tipi, «nr» (la stessa) per quelle dei ruoli
        nome = nome_intero(nome_grp(g_) or "")
        if nome:
            out.setdefault("n" + k[1:], []).append(nome)
            out.setdefault("nr" + k[1:], []).append(nome)
    return out


# la fase del lancio (18 nov 2026, Autore: «quando indichiamo i turni sulle tendine negli advanced filters credo che dovremo mettere una tendina successiva
# che chiede la fase in cui vogliamo esplorare il turno», «fai solo la tendina per ora»): le famiglie «k{fase}{chi}{x}{n}» (i tipi) e «k{fase}n{chi}{x}{n}»
# (la carta) di per_turno, dalle «fasi» di mana_aperto; a = prima fase principale (con l'inizio del turno), c = combattimento, z = seconda fase principale
# (con la fine del turno)
# poi, stesso giorno («in fasi metti le fasi nel dettaglio almeno le main: upkeep ecc»): ogni passo di Arena col suo codice; «combat» resta, ed e' qualunque
# passo del combattimento. Il codice e' una lettera sola (le famiglie si leggono con [a-z])
FASI_LANCIO = (("u", "upkeep"), ("w", "draw step"), ("a", "main phase 1"), ("c", "combat (any step)"), ("b", "beginning of combat"),
               ("t", "declare attackers"), ("l", "declare blockers"), ("g", "combat damage"), ("e", "end of combat"), ("z", "main phase 2"),
               ("f", "end step"))
FASE_ARENA = {"Phase_Beginning": None, "Phase_Main1": "a", "Phase_Combat": "c", "Phase_Main2": "z", "Phase_Ending": "f"}
PASSO_ARENA = {"Step_Upkeep": "u", "Step_Draw": "w", "Step_BeginCombat": "b", "Step_DeclareAttack": "t", "Step_DeclareBlock": "l",
               "Step_CombatDamage": "g", "Step_FirstStrikeDamage": "g", "Step_EndCombat": "e", "Step_End": "f", "Step_Cleanup": "f"}
CAMPI_TURNO = tuple(str(n) for n in range(1, TURNI_FILTRO + 1)) + ("L", "A")           # i turni dei filtri, «dal turno 11» (L) e «qualunque turno» (A)


_RX_FAM = re.compile(r"([a-z]*?(?:io|lui)x?)(\d+)")
_FAM_TURNO = {}


def turni_estesi(out):
    """Da {famiglia+turno: [voci]} di tutti i turni: i turni oltre TURNI_FILTRO diventano «famigliaL» e tutti i turni «famigliaA», ognuno una lista di turni
    (una lista di voci per turno); i singoli turni oltre TURNI_FILTRO non restano. passa_turni legge A e L: basta un turno che abbia tutte le voci scelte."""
    finale = {}
    for k, v in out.items():
        fn_ = _FAM_TURNO.get(k, 0)
        if fn_ == 0:        # la chiave letta una volta (18 nov 2026, la lentezza al caricamento: la regex su ogni chiave di ogni partita)
            m_ = _RX_FAM.fullmatch(k)
            fn_ = _FAM_TURNO[k] = (m_.group(1), int(m_.group(2))) if m_ else None
        if fn_ is None:
            finale[k] = v
            continue
        fam, n = fn_
        if n <= TURNI_FILTRO:
            finale[k] = v
        else:
            finale.setdefault(fam + "L", []).append(v)
            finale.setdefault(fam + "L#", []).append(n)
        finale.setdefault(fam + "A", []).append(v)
        finale.setdefault(fam + "A#", []).append(n)      # il numero di ogni turno (16 nov 2026): le condizioni nello stesso turno (turni_comuni)
    return finale


# le condizioni nello stesso turno (16 nov 2026, Autore: «le condizioni devono sommarsi non essere individuali ... come spieghiamo che voglio che quella
# situazione sia letta su tutti i replay in qualunque turno io e oppo vi troviamo ad avere io una creatura e lui no nello stesso turno?»): i filtri «in
# qualunque turno» (A) e «dal turno 11» (L) che parlano dei turni dello stesso giocatore valgono insieme solo in un turno in cui sono veri tutti. Il turno di
# chi: quello di chi agisce, o dell'altro se la famiglia ha la «x» (o e' la difesa, nel turno dell'altro); «chi e' avanti» col «x» e' il suo turno.
# i filtri da un momento del replay (16 nov 2026, Autore: «possiamo lavorare dai replay al contrario? ovvero estrarre da un momento di un replay un
# insieme di filtri che descrivono quel momento? con l'opzione di poter completare dal leak finder le azioni fino a un range di momenti o turni precedenti e/o
# successivi ma sicuramente nel filtro completerà la parte iniziale del game: chi era on the draw, Mulligan ecc», «Sì, costruiscilo»). La foto del momento,
# a fasce, perche' trovi altre partite simili e non solo quella da cui viene: l'inizio della partita (play o draw, mulligan, terre in mano), il campo dei due
# all'inizio di quel turno (creature, terre, mano, vita; gli altri tipi di permanente e le creature nel cimitero solo se ci sono) e, se chiesto, cosa hanno
# lanciato per ruolo in quel turno e in quelli intorno. Ogni pezzo e' un filtro normale, che si toglie con la sua x.
# Misurato sui log del 16 nov (50 momenti a caso, Constructed): con tutto il campo la meta' dei momenti trova solo la sua partita; con inizio, creature e
# terre la mediana e' 9 partite simili, con le sole creature 23. Quindi di partenza inizio, creature e terre; il campo intero (mano, vita, altri tipi,
# cimitero) e le terre in mano si aggiungono a richiesta.
AREE_MOMENTO = ("c", "t")                       # sempre
AREE_TUTTO = ("m", "v")                         # col campo intero
AREE_SE_CI_SONO = ("k", "y", "w", "z", "j")     # col campo intero, solo se il valore non e' zero (la loro assenza e' quasi sempre la regola)


def filtri_momento(x, T, intorno=None, tutto=False):
    """{filtro: valore} che descrivono il turno di Arena T della partita x. intorno: None = niente giocate; 0 = anche cosa e' stato lanciato in quel turno;
    N = anche nei N turni (di Arena) prima e dopo. tutto: il campo intero (mano, vita, gli altri tipi di permanente e le creature nel cimitero se ci sono)
    e le terre nella mano iniziale. I turni oltre TURNI_FILTRO diventano «dal turno 11» (L), che resta nello stesso turno degli altri filtri dello stesso
    giocatore (turni_comuni)."""
    out = {}
    for k in ("partenza", "mull") + (("terre",) if tutto else ()):
        v = LEGGI[k](x) if k in LEGGI else None
        if v is not None:
            out[k] = v
    pt = x.get("per_turno") or {}
    inizia = x.get("inizia")
    if inizia is None or not T:
        return out
    padrone = lambda t: "io" if (t % 2 == 1) == bool(inizia) else "lui"
    altro = {"io": "lui", "lui": "io"}

    def chiave(fam, chi, t):
        """La chiave del filtro e il valore di per_turno per la famiglia di chi nel turno t (con la «x» se il turno e' dell'altro)."""
        n = (t + 1) // 2
        base = f"{fam}{chi}{'' if padrone(t) == chi else 'x'}"
        if n <= TURNI_FILTRO:
            return f"t_{base}{n}", pt.get(f"{base}{n}")
        vv = dict(zip(pt.get(base + "L#") or [], pt.get(base + "L") or []))
        return f"t_{base}L", vv.get(n)

    for chi in ("io", "lui"):
        for a in AREE_MOMENTO + ((AREE_TUTTO + AREE_SE_CI_SONO) if tutto else ()):
            k, v = chiave("b" + a, chi, T)
            if not v:
                continue
            if a in AREE_SE_CI_SONO and v[0].startswith("0 "):
                continue
            out[k] = list(v)
    if intorno is not None:
        for t in range(max(1, T - intorno), T + intorno + 1):
            for chi in ("io", "lui"):
                k, v = chiave("r", chi, t)
                if v is None:
                    continue
                ruoli = [r_ for r_ in v if " · " not in r_]       # i ruoli, senza il momento: piu' largo; il momento si aggiunge a mano
                out[k] = ruoli or ["Nothing"]
    return out


def padrone_turno(k):
    """(di chi e' il turno, A o L) di un filtro esteso «t_...A/L»; None se non lo e'."""
    m_ = re.fullmatch(r"t_([a-z]*?)(io|lui)(x?)([AL])", k)
    if not m_:
        return None
    fam, chi, ics, q = m_.groups()
    altro = {"io": "lui", "lui": "io"}
    return (altro[chi] if (ics or fam in ("d", "nd")) else chi), q


def gruppi_turno(filtri):
    """{(padrone, A/L): [chiavi]} dei filtri estesi accesi: ogni gruppo vale in un turno solo."""
    out = {}
    for k, v in (filtri or {}).items():
        if v is None or v == [] or k == "wr_rif":
            continue
        pt = padrone_turno(k)
        if pt:
            out.setdefault(pt, []).append(k)
    return out


def _turni_veri(x, k, scelte):
    """I numeri dei turni in cui il filtro esteso k ha tutte le voci scelte."""
    pt = x.get("per_turno") or {}
    voglio = collections.Counter(scelte if isinstance(scelte, (list, tuple)) else [scelte])
    return {n for v, n in zip(pt.get(k[2:]) or [], pt.get(k[2:] + "#") or [])
            if all(collections.Counter(v)[i] >= q for i, q in voglio.items())}


def turni_comuni(x, filtri, chiavi):
    """I turni in cui sono veri insieme tutti i filtri estesi di un gruppo."""
    comuni = None
    for k in chiavi:
        t_ = _turni_veri(x, k, filtri[k])
        comuni = t_ if comuni is None else comuni & t_
        if not comuni:
            return set()
    return comuni or set()


def esteso(k):
    """La chiave di un filtro turno per turno «in qualunque turno» o «dal turno 11» (t_aioA, t_ioL)?"""
    return bool(re.fullmatch(r"t_[a-z]*?(io|lui)x?[AL]", k))


def turni_di(k, x):
    """Per una chiave A o L: la lista dei turni, ognuno la sua lista di voci; per un turno solo: [voci]; [] se la partita non ce l'ha."""
    v = (x.get("per_turno") or {}).get(k[2:])
    if not v:
        return []
    return v if esteso(k) else [v]


def episodi(r, filtri):
    """Quante volte (14 nov 2026, Autore: «quanto performiamo o perdiamo in una determinata azione o situazione e quante volte ci è capitato di essere in
    quella situazione»): per ogni filtro acceso che si conta a episodi, nelle partite r (gia' filtrate) -> [dict(chiave, nome, volte, partite, occasioni)].
    volte: i turni (o le finestre) in cui e' successo; partite: in quante; occasioni: i turni in cui poteva succedere (None se non si sa).
      - turno per turno «in qualunque turno» / «dal turno 11»: i turni con tutte le voci scelte, su tutti i turni di quella famiglia;
      - un turno solo: la partita conta una volta;
      - «sit:io_non_att_chiuso»: le finestre con lui scoperto, su tutti i turni con un attaccante pronto e senza attacco;
      - «sit:io_letale_mancato»: i turni col letale sul tavolo e lui vivo;
      - i leak: i turni del leak."""
    import mana_aperto as MA
    out = []
    for k, v in filtri.items():
        if v is None or v == [] or k == "wr_rif":
            continue
        volte, part, occ = 0, 0, 0
        if re.fullmatch(r"t_[a-z]*?(io|lui)x?(\d+|[AL])", k):
            for x in r:
                tt = turni_di(k, x)
                occ += len(tt)
                voglio = collections.Counter(v if isinstance(v, (list, tuple)) else [v])
                n_ = sum(1 for t_ in tt if all(collections.Counter(t_)[i] >= q for i, q in voglio.items()))
                if esteso(k):       # nello stesso turno degli altri filtri estesi dei turni dello stesso giocatore (16 nov 2026)
                    n_ = len(turni_comuni(x, filtri, gruppi_turno(filtri).get(padrone_turno(k), [k])))
                volte += n_
                part += 1 if n_ else 0
        elif k in ("sit:io_non_att_chiuso", "sit:io_letale_mancato") and v == "Yes":
            for x in r:
                d = _MANA.get(x.get("partita"))
                if k == "sit:io_non_att_chiuso":
                    w = MA.finestre_non_att(d, x.get("seat")) or []
                    n_, occ = sum(1 for z in w if z["scoperto"]), occ + len(w)
                else:
                    n_, occ = len(MA.letali_mancati(d, x.get("seat")) or []), None
                volte += n_
                part += 1 if n_ else 0
        elif k in _VP.NOMI and v not in ("0", "No", "Never", "None", None) and k not in ("primo_att_io", "primo_att_lui", "rim_prima_lui", "rim_quando_io"):
            occ = None
            for x in r:
                n_ = _VP.conta(x, k)
                if n_ is None:      # le voci Yes/No: una volta a partita
                    n_ = 1 if _VP.valore(x, k) == "Yes" else 0
                volte += n_
                part += 1 if n_ else 0
        elif k in _TM.NOMI and v not in ("0", None):        # il tempismo: i lanci contati
            occ = 0
            for x in r:
                tm = _TM.per_partita(x) or {}
                n_ = len(tm.get(k[3:]) or [])
                occ += len(tm.get("nel_mio") or [])
                volte += n_
                part += 1 if n_ else 0
        elif re.fullmatch(r"leak_l\d+", k) and v == "Yes":
            occ = None
            for x in r:
                lk = (x.get("leak") or {}).get(k[5:]) if k not in ("leak_l12", "leak_l13") else (__import__("leak").valore(x, k[5:]) == "Yes")
                n_ = (len(lk) if isinstance(lk, list) else 1 if lk else 0)
                volte += n_
                part += 1 if n_ else 0
        else:
            continue
        out.append(dict(chiave=k, nome=nome_var(k), volte=volte, partite=part, occasioni=occ))
    return out


# gli spot dei filtri nel replayer (15 nov 2026, Autore: «quando setto i filtri, i replay in this situation si aprano sulla posizione indicata dal filtro di
# ricerca? magari creando un logo sul replay dedicato che indica la situazione da filtro attivo», poi «Sì, costruiscilo»): dove, in una partita, e' vero ogni
# filtro acceso che ha un momento. I filtri di tutta la partita (formato, rango, data, risultato, mulligan, colori...) non ne hanno e restano fuori.
# Il dove: «magia» la prima magia (non abilita') di chi l'ha lanciata in quel turno, «comb» il combattimento, «inizio» il primo passo del turno, «fine» l'ultimo,
# «mano» la mano tenuta, «ultimo» l'ultimo passo della partita.
DOVE_FAMIGLIA = {"": "magia", "a": "comb", "d": "comb", "m": "comb", "q": "comb", "p": "inizio", "u": "fine"}


def _voce_filtro(v):
    return " + ".join(str(z) for z in v) if isinstance(v, (list, tuple)) else str(v)


def _fase_lancio(x, t, posto, voglio):
    """(fase di Arena, grpId) della prima magia di un tipo voluto lanciata nel turno t da chi sta al posto (le azioni e le «fasi» di mana_aperto): serve al
    replayer per uno spot di magia senza bersagli, che non ha un passo «spell» suo (15 nov 2026): la carta nella pila, se no la fase. None se non si sa."""
    d = _MANA.get(x.get("partita")) or {}
    nomi = {v: k for k, v in NOMI_TIPO.items()}
    lettere = {nomi[v] for v in voglio if v in nomi}
    ruoli = {v for v in voglio if v.partition(" · ")[0] in RUOLI}
    carte = {v for v in voglio if v not in nomi and v.partition(" · ")[0] not in RUOLI and v != "Nothing"}
    if carte:       # i nomi delle carte (16 nov 2026): la prima di quelle carte lanciata in quel turno
        for t_, s_, g_, f_ in d.get("fasi") or []:
            if t_ == t and s_ == posto and g_ not in SENZA_FACCIA and nome_intero(nome_grp(g_) or "") in carte:
                return f_, g_
        return None
    if ruoli:       # i ruoli (16 nov 2026): la prima magia di quel ruolo, e se la voce lo dice, in quel momento del combattimento
        for t_, s_, g_, f_ in d.get("fasi") or []:
            if t_ != t or s_ != posto or g_ in SENZA_FACCIA:
                continue
            r_ = ruolo_magia(nome_grp(g_))
            m_ = "in combat" if f_ == "Phase_Combat" else "after combat" if f_ in ("Phase_Main2", "Phase_Ending") else "before combat"
            if r_ in ruoli or f"{r_} · {m_}" in ruoli:
                return f_, g_
        return None
    fasi = {(t_, s_, g_): f_ for t_, s_, g_, f_ in d.get("fasi") or []}
    for t_, s_, cosa, g_, tipi in d.get("azioni") or []:
        if cosa == "magia" and t_ == t and s_ == posto and (not lettere or lettere & set(tipi or "")) and (t_, s_, g_) in fasi:
            return fasi[(t_, s_, g_)], g_
    return None


def spot_filtri(x, filtri):
    """Gli spot dei filtri accesi nella partita x -> [dict(chiave, nome, voce, t, dove, mio)] in ordine di turno; [] se nessun filtro acceso ha un momento.
    t e' il turno di Arena (i due giocatori contati insieme), mio dice di chi e' la magia per «magia»."""
    import mana_aperto as MA
    out = []
    seat, inizia = x.get("seat"), x.get("inizia")
    grezzo = None
    # i filtri estesi dello stesso giocatore insieme (16 nov 2026): uno spot «any turn» c'e' solo nei turni in cui sono veri tutti quelli del suo gruppo
    comuni_k = {k: turni_comuni(x, filtri, ch) for ch in gruppi_turno(filtri).values() for k in ch}
    for k, v in (filtri or {}).items():
        if v is None or v == [] or k == "wr_rif":
            continue
        nome, voce = nome_var(k), _voce_filtro(v)

        def aggiungi(t, dove, mio=None, k=k, nome=nome, voce=voce, fase=None):
            fg = fase or (None, None)
            out.append(dict(chiave=k, nome=nome, voce=voce, t=t, dove=dove, mio=mio, fase=fg[0], g=fg[1]))
        m_ = re.fullmatch(r"t_([a-z]*?)(io|lui)(x?)(\d+|[AL])", k)
        if m_:
            fam, chi, ics, quale = m_.groups()
            if inizia is None or seat not in (1, 2):
                continue
            if grezzo is None:
                fn_ = (_MANA.get(x.get("partita")) or {}).get("fine") or []
                tt_ = x.get("turni") or max([0] + [z[0] for z in fn_])
                grezzo = per_turno(x.get("partita"), seat, inizia, tt_, grezzo=True) or {}
            voglio = collections.Counter(v if isinstance(v, (list, tuple)) else [v])
            primo = "io" if inizia else "lui"
            altro = {"io": "lui", "lui": "io"}
            for kg, voci in grezzo.items():
                mg = re.fullmatch(r"([a-z]*?)(io|lui)(x?)(\d+)", kg)
                if not mg or mg.group(1) != fam or mg.group(2) != chi or mg.group(3) != ics:
                    continue
                n = int(mg.group(4))
                if (quale.isdigit() and n != int(quale)) or (quale == "L" and n <= TURNI_FILTRO):
                    continue
                if quale in "AL" and n not in comuni_k.get(k, set()):
                    continue
                if not all(collections.Counter(voci)[i] >= q for i, q in voglio.items()):
                    continue
                padrone = altro[chi] if (ics or fam in ("d", "nd")) else chi        # di chi e' il turno: il suo, o quello dell'altro («x»; la difesa e' nel suo attacco)
                t = 2 * n - 1 if padrone == primo else 2 * n
                aggiungi(t, DOVE_FAMIGLIA.get(fam, "inizio"), chi == "io", fase=_fase_lancio(x, t, seat if chi == "io" else 3 - seat, voglio) if fam in ("", "r", "n", "nr") or re.fullmatch(r"k[a-z]n?", fam) else None)
        elif re.fullmatch(r"leak_l\d+", k) and v == "Yes":
            l_ = k[5:]
            if l_ in ("l12", "l13"):
                if __import__("leak").valore(x, l_) == "Yes":
                    aggiungi(0, "mano")
            elif l_ == "l7":
                if (x.get("leak") or {}).get("l7"):
                    aggiungi(10 ** 6, "ultimo")
            else:
                for t in (x.get("leak") or {}).get(l_) or []:
                    aggiungi(t, "comb" if l_ in ("l4", "l5") else "fine")
        elif k in ("sit:io_non_att_chiuso", "sit:io_letale_mancato") and v == "Yes":
            d = _MANA.get(x.get("partita"))
            if k == "sit:io_non_att_chiuso":
                for z in MA.finestre_non_att(d, seat) or []:
                    if z.get("scoperto"):
                        aggiungi(z["t"], "fine")
            else:
                for z in MA.letali_mancati(d, seat) or []:
                    aggiungi(z["t"], "comb")
        elif k in _TM.NOMI and v not in ("0", None):
            for t in (_TM.per_partita(x) or {}).get(k[3:]) or []:
                aggiungi(t, "magia", True)
        elif k.startswith("s_") and seat in (1, 2) and inizia is not None:
            for t, dove, mio, g in spot_situa(x, k[2:], v):
                aggiungi(t, dove, mio, fase=(None, g) if g else None)
    out.sort(key=lambda z: z["t"])
    return out


def spot_situa(x, key, v):
    """I momenti di una situazione dei replay (situazioni_replay) nella partita x, se la partita ha il valore filtrato: [(turno di Arena, dove, mio, grpId)].
    24 nov 2026 (Note/Replayer_Lacune.md voce 5): il replayer parte dal momento della situazione, come coi filtri turno per turno. Il board wipe, la
    contromagia, il bersaglio nel cimitero e le rimozioni sulla magia che li fa; la vita piu' bassa sul primo turno che la tocca; vite, creature e terre a fine
    del turno della situazione. [] senza un momento (le magie lanciate nella partita) o se la partita non ha quel valore."""
    vals = v if isinstance(v, (list, tuple)) else [v]
    if (x.get("situa") or {}).get(key) not in vals:
        return []
    d = _MANA.get(x.get("partita")) or {}
    seat, inizia = x.get("seat"), x.get("inizia")
    altro_s = 2 if seat == 1 else 1
    comincia = {"io": inizia, "lui": not inizia}
    t_di = lambda chi, n: 2 * n - 1 if comincia[chi] else 2 * n
    out = []
    m_ = re.fullmatch(r"(wipe|counter|cim|rim)_(io|lui)", key)
    if m_:
        tipo, chi = m_.groups()
        posto = seat if chi == "io" else altro_s
        for kind, t, _att, f, info in d.get("momenti") or []:
            if kind != "spell" or not info or info.get("chi") != posto:
                continue
            tolti = colpiti_di(info)
            fuori = info.get("fuori") or []
            if tipo == "wipe":
                ok = len(tolti) >= 3
            elif tipo == "counter":
                ok = any(z_ == "pila" and pr_ not in (None, posto) for _i, z_, pr_, _g in fuori)
            elif tipo == "cim":
                ok = any(z_ == "cim" for _i, z_, _p, _g in fuori)
            else:
                c = (f or {}).get("c") or [[], []]
                suoi = {x_[5] for x_ in c[(altro_s if chi == "io" else seat) - 1] if len(x_) > 5}
                ok = any(t_ in suoi for t_ in tolti)
            if ok:
                out.append((t, "magia", chi == "io", info.get("g")))
        return out
    m_ = re.fullmatch(r"(vita|crea)_t(\d+)", key)
    if m_:
        return [(t_di("io", int(m_.group(2))), "fine", None, None)]
    m_ = re.fullmatch(r"terre_(io|lui)(\d+)", key)
    if m_:
        return [(t_di(m_.group(1), int(m_.group(2))), "fine", None, None)]
    m_ = re.fullmatch(r"vita_(io|lui)", key)
    if m_:
        i = (seat if m_.group(1) == "io" else altro_s) - 1
        fascia = lambda m: "16+" if m >= 16 else "11-15" if m >= 11 else "6-10" if m >= 6 else "1-5" if m >= 1 else "0 or less"
        for t, _a, f in d.get("foto") or []:
            vv = (f.get("v") or [None, None])[i]
            if vv is not None and fascia(vv) == x["situa"][key]:
                return [(t, "fine", None, None)]
        return [(10 ** 6, "ultimo", None, None)]       # la vita piu' bassa all'ultimo stato (non fra le foto di fine turno)
    return out


def passa_turni(k, x, scelte):
    """Una partita passa un filtro turno per turno se almeno uno dei suoi turni ha tutte le voci scelte (ripetizioni comprese)."""
    voglio = collections.Counter(scelte if isinstance(scelte, (list, tuple)) else [scelte])
    return any(all(collections.Counter(t_)[i] >= n for i, n in voglio.items()) for t_ in turni_di(k, x))


# le abilita' attivate, carta per carta e quando (13 nov 2026, Autore: «saccare reliquia dopo draw step di Oppo migliora le mie possibilita' di vittoria
# perche' gli impedisco di usare al meglio brainstorm in upkeep, pero' non credo proprio sia una cosa che un programma riesce a stimare», poi «Sì, aggiungilo»):
# da mana_aperto VERSIONE 15 («attivate»). Il quando e' sempre dal tuo posto: «their turn» e' il turno dell'avversario, anche per le sue abilita'.
PASSI_ARENA = {"Step_Upkeep": "Upkeep", "Step_Draw": "Draw step", "Phase_Main1": "Main 1", "Step_BeginCombat": "Beginning of combat",
               "Step_DeclareAttack": "Declare attackers", "Step_DeclareBlock": "Declare blockers", "Step_FirstStrikeDamage": "Combat damage",
               "Step_CombatDamage": "Combat damage", "Step_EndCombat": "End of combat", "Phase_Main2": "Main 2", "Step_End": "End step", "Step_Cleanup": "Cleanup"}
PASSI = tuple(dict.fromkeys(PASSI_ARENA.values()))
QUANDO_ATTIVATE = ("Any time", "Your turn", "Their turn") + tuple(f"{q} · {w}" for w in ("your turn", "their turn") for q in PASSI)


def passo_di(fase, step):
    """Il nome del passo di Arena: lo step se c'e' (nelle fasi principali Arena non lo scrive), se no la fase; None se non e' fra i PASSI."""
    return PASSI_ARENA.get(step or "") or PASSI_ARENA.get(fase or "")


def attivate_partita(match_id, seat):
    """Le abilita' attivate (non di mana) di una partita: {«io»: [voci], «lui»: [voci]}, ogni voce «Carta · quando» con quando in QUANDO_ATTIVATE: «Any time»,
    il turno («Your turn», «Their turn») e il passo col turno («Draw step · their turn»). Una voce per partita anche se l'abilita' e' stata attivata piu' volte.
    {} senza i dati (mana_aperto prima della VERSIONE 15) o senza il posto."""
    d = _MANA.get(match_id) or {}
    if "attivate" not in d or seat not in (1, 2):
        return {}
    out = {"io": set(), "lui": set()}
    for _t, s_, g_, fase, step, *att in d["attivate"]:
        n = nome_intero(nome_grp(g_) or "") if g_ not in SENZA_FACCIA else ""
        if not n:
            continue
        chi = "io" if s_ == seat else "lui"
        out[chi].add(f"{n} · Any time")
        if att:     # il posto di chi era di turno
            w = "your turn" if att[0] == seat else "their turn"
            out[chi].add(f"{n} · {w.capitalize()}")
            p_ = passo_di(fase, step)
            if p_:
                out[chi].add(f"{n} · {p_} · {w}")
    return {k: sorted(v) for k, v in out.items()}


def ordine_lancio(v):
    """L'ordine delle voci di un turno: i tipi come ORDINE_TIPI (ripetuti una volta per magia: «Instant», «Instant»). Una voce di prima col costo
    («Creature · 2», fino al 13 nov 2026) va dopo il suo tipo."""
    tipo, _s, costo = v.partition(" · ")
    return (ORDINE_TIPI.index(tipo) if tipo in ORDINE_TIPI else 99, int(costo) if costo.isdigit() else -1)


def multipla(k):
    """Le chiavi a scelta multipla: le giocate turno per turno («t_io2», «t_luix3»). Il filtro e' una lista di voci, e una partita passa se in quel turno ha
    tutte le voci scelte, ripetizioni comprese (una creatura e due istantanei)."""
    return bool(re.fullmatch(r"t_(?:k[a-z])?(io|lui)x?(\d+|[AL])", k))


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
    # 16 nov 2026: i simboli ibridi chiedono uno dei loro colori, non tutti e due (un mono bianco con Peer Review {W/U} non e' Azorius): le carte che il database
    # di Arena conosce passano da matchup_log.colori_di (minimo 1: la lista e' tutta del mazzo); le altre col colore della tabella, come prima
    trovati, note = set(), []
    try:
        import matchup_log as MU
        R = MU.requisiti()
    except Exception:       # noqa: BLE001 - senza database delle carte, i colori della tabella
        MU, R = None, {}
    for n in nomi_:
        r_ = R.get(MU._chiave(n)) if MU is not None else None
        if r_ and (r_[0] or r_[1] or r_[2]):       # una magia coi suoi simboli, o una terra
            note.append(n)
            continue
        c = _carta(n)
        if c and "Land" not in (c.get("tipo") or "").split(" // ")[0]:
            trovati |= set(c.get("colori") or "")
    if note:
        trovati |= set(MU.colori_di(note, minimo=1))
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
        _TERRE[n] = MS.e_terra(n, _tabella())     # la tabella una volta (18 nov 2026: senza, 1.500 chiamate rileggevano il database, 2,4 s)
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


# ------------------------------------------------------------------ R1 + R6 · le due liste a lato del replayer
# (13 nov 2026, Note/HANDOFF_Censimento_Performance.md voci R1 e R6: quello che il replay di Untapped ha e il nostro no; Autore: «Sì, R1+R6»)
def _conta(nomi):
    out = collections.Counter()
    for n in nomi or []:
        if n and n not in SENZA_FACCIA.values() and not n.startswith("#"):
            out[nome_intero(n)] += 1
    return out


def lista_mia(deck, foto, rel=None):
    """R6: il tuo mazzo a un momento del replay. deck {nome: copie} (la lista della partita), foto del momento (DA.foto_partita, gia' dal tuo lato), rel la
    magia in pila (una tua magia sta fuori dal grimorio). -> dict(righe=[(nome, rimaste, nel mazzo, terra?)], grimorio). Rimaste = copie meno quelle viste
    fuori dal grimorio (mano, campo senza pedine, cimitero, esilio, pila); mai sotto zero. Il grimorio e' il mazzo meno tutte le viste."""
    if not deck:
        return None
    fuori = _conta(foto.get("mano")) + _conta(n for n, _t, ped, *_r in foto.get("mio") or [] if not ped)
    fuori += _conta((foto.get("cim") or [[], []])[0]) + _conta((foto.get("esi") or [[], []])[0])
    if isinstance(rel, dict) and rel.get("tipo") == "spell" and rel.get("mio") and not rel.get("ab") and rel.get("nome"):
        fuori[nome_intero(rel["nome"])] += 1
    righe, visti = [], 0
    for n, q in deck.items():
        ni = nome_intero(n)
        v = min(q, fuori.get(ni, 0))
        visti += v
        righe.append((ni, q - v, q, e_terra(ni)))
    cmc = lambda n: (_carta(n) or {}).get("cmc", 99)
    righe.sort(key=lambda r_: (r_[3], cmc(r_[0]), r_[0]))
    return dict(righe=righe, grimorio=sum(deck.values()) - visti)


def lista_sua(passi, i):
    """R1: le carte dell'avversario viste fino al momento i del replay: per nome il numero massimo di copie visto insieme in un momento (campo senza pedine,
    cimitero, esilio, le sue magie in pila): un minimo, non il suo mazzo. passi = [(nome, foto, turno, rel)]. -> [(nome, copie, terra?)] per costo."""
    massimo = collections.Counter()
    for p_ in passi[:i + 1]:            # (nome, foto, turno, rel, ...): in Every action i passi hanno piu' campi
        f, rel = p_[1], (p_[3] if len(p_) > 3 and isinstance(p_[3], dict) else None)
        ora = _conta(n for n, _tp, ped, *_r in f.get("suo") or [] if not ped)
        ora += _conta((f.get("cim") or [[], []])[1]) + _conta((f.get("esi") or [[], []])[1])
        if rel and rel.get("tipo") == "spell" and not rel.get("mio") and not rel.get("ab") and rel.get("nome"):
            ora[nome_intero(rel["nome"])] += 1
        for n, q in ora.items():
            massimo[n] = max(massimo[n], q)
    cmc = lambda n: (_carta(n) or {}).get("cmc", 99)
    return sorted(((n, q, e_terra(n)) for n, q in massimo.items()), key=lambda r_: (r_[2], cmc(r_[0]), r_[0]))


def testo_lista(righe):
    """«Copy as list»: una carta per riga, «N Nome», come la importa Arena; le terre in fondo."""
    return "\n".join(f"{q} {n}" for n, q, _t in righe)


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
    import variabili_c as VC
    c_ = VC.campi(p, r, lista, tenuta)
    c_["rim_bersagli"] = VC.bersagli_rimozioni(dict(r, seat=p.get("seat")))       # C13
    import cimitero as CM
    c_["cimitero"] = CM.per_partita(dict(r, seat=p.get("seat")))      # cimitero ed esilio (14 nov 2026: «ok fai i filtri per la decisione»)
    import leak as LK
    leak_ = LK.per_partita(dict(r, seat=p.get("seat"), fine=come_finita(p.get("motivo"), r["vinta"]), quando=quando))
    # la durata in minuti, la stagione e lo step del rango (14 nov 2026, partite_log VERSIONE 5)
    minuti = round((p["fine"] - p["inizio"]) / 60000, 1) if p.get("fine") and p.get("inizio") and p["fine"] > p["inizio"] else None
    c_ = dict(c_, minuti=minuti, stagione=p.get("stagione"), rango_step=p.get("rango_step"))
    return dict(r, **c_, seat=p.get("seat"), mazzo_id=p.get("mazzo"), mie_lanciate=mie_l, scartate=scartate, fortuna=fortuna(p, r, lista), deck=lista, leak=leak_, **carte_partita(r, p.get("seat"), tenuta), economiche=econ, crea_mano=crea, crea_in_mano=creature_in_mano(tenuta),
                suo_mull=suo_mulligan(r.get("partita"), p.get("seat")), crea_prima=prima_creatura(r.get("partita"), p.get("seat"), r.get("inizia")),
                ist_mano=magie_in_mano(tenuta, "Instant"), str_mano=magie_in_mano(tenuta, "Sorcery"),
                art_mano=magie_in_mano(tenuta, "Artifact"), inc_mano=magie_in_mano(tenuta, "Enchantment"), pw_mano=magie_in_mano(tenuta, "Planeswalker"),
                bat_mano=magie_in_mano(tenuta, "Battle"),
                per_turno=per_turno(r.get("partita"), p.get("seat"), r.get("inizia"), turni), abil=attivate_partita(r.get("partita"), p.get("seat")),
                situa=situazioni_replay(r.get("partita"), p.get("seat"), r.get("inizia"), turni),
                crea_prima_lui=prima_creatura(r.get("partita"), 2 if p.get("seat") == 1 else 1 if p.get("seat") == 2 else None,
                                              None if r.get("inizia") is None else not r.get("inizia")), miei_colori=colori_mazzo(lista), fine=come_finita(p.get("motivo"), r["vinta"]),
                giorno=GIORNI[quando.weekday()], tipo="Limited" if r["formato"] == "limited" else "Constructed", quando=quando, ora=quando.hour, fascia=_fascia(quando.hour),
                terre=terre, mano=sorted(tenuta or {}), mano_conta=dict(tenuta or {}), sue_viste=sorted(n for n in sue if not e_terra(n)),
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


def _segnalini(v):
    """I segnalini di una carta in campo come {tipo (int): quanti}: dalla copia su disco le chiavi tornano stringhe."""
    if not v:
        return None
    try:
        return {int(k): int(q) for k, q in v.items() if q}
    except (AttributeError, TypeError, ValueError):
        return None


def _carta_foto(c):
    """Una carta in campo di una foto -> (nome, tappata, pedina, forza, costituzione, id, grpId, segnalini). grpId e segnalini dal 14 nov 2026 (le immagini
    delle pedine, i segnalini ben visibili nel replayer)."""
    resto = (list(c[3:6]) + [None, None, None])[:3]
    return (nome_grp(c[0]) or ("Token" if c[2] else f"#{c[0]}"), bool(c[1]), bool(c[2]), *resto, c[0], _segnalini(c[6] if len(c) > 6 else None))


def foto_partita(x):
    """Le foto di una partita dal tuo posto (mano_aperto): dict(mano0, turni=[(turno, tuo turno?, foto)], ultima) con le foto girate cosi' che [0] sia il tuo
    lato; None se la partita non ha il log. turni=[(turno, tuo turno?, foto, «fine»|«comb»|«spell», relazioni)]. Una foto: dict(mio=[(nome, tappata, pedina,
    forza, costituzione, id)], suo=[...], mano=[nomi], n_suo=carte nella sua
    mano, vite=(tu, lui), cim=(tuo cimitero, suo), esi=(tuo esilio, suo))."""
    if x.get("simulata"):       # una partita del motore di partita (partite_motore.py)
        import partite_motore
        return partite_motore.foto_partita(x)
    d = _MANA.get(x.get("partita"))
    seat = x.get("seat")
    if not d or seat not in (1, 2) or "foto" not in d:
        return None
    a, b = seat - 1, 2 - seat

    def gira(f):
        if not f:
            return None
        carte = lambda lst: [_carta_foto(c) for c in lst]
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
                rel = dict(tipo="spell", nome=nome, g=info.get("g"), mio=info.get("chi") == seat, ab=bool(info.get("ab")), bers=[lato(b_) for b_ in bers], colpiti=colpiti,
                           fuori=_fuori(info.get("fuori"), seat))
            elif kind == "comb":
                rel = dict(tipo="comb", att=[(i, lato(tg)) for i, tg in info.get("att") or []], blocchi=[(i, list(a_)) for i, a_ in info.get("blocchi") or []])
            turni.append((t, att == seat, gira(f), kind, rel))
    else:
        turni = [(t, att == seat, gira(f), "fine", None) for t, att, f in d.get("foto") or []]
    ult = d.get("ultima")
    return dict(mano0=gira(d.get("mano0")), turni=turni, ultima=(ult[0], ult[1] == seat, gira(ult[2])) if ult else None)


FRASI_EMOTE = {"Phrase_Basic_Hello": "Hello!", "Phrase_Basic_GoodGame": "Good game", "Phrase_Basic_Nice": "Nice!", "Phrase_Basic_Thinking": "Thinking...",
               "Phrase_Basic_Oops": "Oops", "Phrase_Basic_YourGo": "Your go", "Phrase_Basic_GoodLuck": "Good luck!"}


def _frase_emote(p_):
    import re
    if p_ in FRASI_EMOTE:
        return FRASI_EMOTE[p_]
    return re.sub(r"(?<=[a-z])(?=[A-Z])", " ", (p_ or "").split("_")[-1]) or p_


def _info_foto(f, seat):
    """I dati del passo che vengono dalle richieste e dai messaggi di Arena (16 nov 2026), dal tuo posto, coi nomi delle carte."""
    try:
        import testi_arena as TA
    except Exception:      # noqa: BLE001 - senza database niente testi
        TA = None
    mio = lambda d_: (d_ or {}).get("chi") in (None, seat)
    out = {}
    if f.get("pa") and mio(f["pa"]):
        out["pa"] = list(f["pa"].get("ids") or [])
    if f.get("pb") and mio(f["pb"]):
        out["pb"] = [b_[0] for b_ in f["pb"].get("b") or []]
    if f.get("lt") and mio(f["lt"]):
        out["lt"] = list(f["lt"].get("ids") or [])
    if f.get("op") and mio(f["op"]):
        out["op"] = list(f["op"].get("o") or [])
    if f.get("sn") and mio(f["sn"]):
        out["sn"] = (f["sn"].get("mn"), f["sn"].get("mx"), [nome_grp(g_) or "a card" for g_ in f["sn"].get("g") or []])
    if f.get("pdd"):
        out["pdd"] = [(nome_grp(g_) or "a card", v_) for g_, v_ in f["pdd"].values()]
    if f.get("sp"):
        out["sp"] = [(nome_grp(e_[2]) or "a card", e_[1]) for e_ in f["sp"]]
    if f.get("ch"):
        out["ch"] = [(s_ == seat, _frase_emote(p_)) for s_, p_ in f["ch"]]
    if f.get("dado"):
        out["dado"] = (f["dado"].get(str(seat)), f["dado"].get(str(2 if seat == 1 else 1)))
    if f.get("mul"):
        out["mul"] = (f["mul"].get(str(seat), 0), f["mul"].get(str(2 if seat == 1 else 1), 0))
    if f.get("pp"):
        out["pp"] = True
    for k_ in ("canc", "auto", "conc"):
        if f.get(k_):
            out[k_] = True
    if f.get("mdec"):
        out["mdec"] = list(f["mdec"])
    if f.get("parte") is not None:
        out["parte"] = "first" if f["parte"] == seat else "second"
    if f.get("opz") and mio(f["opz"]):
        out["opz"] = (nome_grp(f["opz"].get("g")) or "a card", f.get("opr") or "")
    elif f.get("opr"):
        out["opz"] = ("a card", f["opr"])
    if f.get("cerca") is not None:
        out["cerca"] = [nome_grp(g_) or "a card" for g_ in f["cerca"]]
    if f.get("div"):
        out["div"] = [(nome_grp(a_) or "a creature", [(nome_grp(b_) or "a creature", q_) for b_, q_ in bb_]) for a_, bb_ in f["div"]]
    if f.get("trz"):
        out["trz"] = [(nome_grp(g_) or "a card", z_) for g_, z_ in f["trz"]]
    if f.get("hvm"):
        out["hvm"] = list(f["hvm"])
    if f.get("abt") and TA is not None:
        out["abt"] = {int(i_): TA.abilita(g_) or "" for i_, g_ in f["abt"].items()}
    gi_ = f.get("gi") or {}
    if gi_.get("a") and gi_.get("chi") in (None, seat):
        voci = []
        for e_ in gi_["a"]:
            n_ = nome_grp(e_[3]) or "a card"
            if e_[1] == "A" and len(e_) > 4 and e_[4] and TA is not None:
                tx_ = (TA.abilita(e_[4]) or "").strip()
                voci.append(f"{n_}: {tx_[:48]}{'…' if len(tx_) > 48 else ''}" if tx_ else n_)
            else:
                voci.append(n_)
        out["gioc"] = list(dict.fromkeys(voci))
    return out


def gira_foto(f, seat):
    """Una foto di mana_aperto o di replay_log girata dal tuo posto, coi nomi (come in foto_partita)."""
    if not f:
        return None
    a, b = seat - 1, 2 - seat
    carte = lambda lst: [_carta_foto(c) for c in lst]
    nomi = lambda lst: [nome_grp(g) or f"#{g}" for g in lst]
    vuoto = [[], []]
    return dict(mio=carte(f["c"][a]), suo=carte(f["c"][b]), mano=nomi(f["m"][a]), n_suo=f["n"][b], vite=(f["v"][a], f["v"][b]),
                # le tue carte della mano mostrate all'avversario (15 nov 2026; le sue che Arena manda stanno fuori dalla lista della sua mano: residui)
                mostrate=nomi((f.get("mv") or [[], []])[a]),
                emblemi=(nomi((f.get("em") or [[], []])[a]), nomi((f.get("em") or [[], []])[b])),
                opzioni=dict(f.get("op") or {}),        # come e' stata lanciata la magia in pila: {id: [KICKED, X = 3...]}      # gli emblemi (tuoi, suoi), col nome della carta
                # la carta in cima al grimorio che si conosce (tua, sua): (nome, pubblica) o None (15 nov 2026)
                cima=tuple((nome_grp(c_[0]) or f"#{c_[0]}", bool(c_[1])) if c_ else None for c_ in ((f.get("cm") or [None, None])[a], (f.get("cm") or [None, None])[b])),
                cim=(nomi((f.get("g") or vuoto)[a]), nomi((f.get("g") or vuoto)[b])), esi=(nomi((f.get("e") or vuoto)[a]), nomi((f.get("e") or vuoto)[b])),
                grimori=tuple((f.get("lb") or [None, None])[k_] for k_ in (a, b)),      # quante carte nei grimori (tuo, suo), dal log (24 nov 2026)
                pila=[(nome_grp(g) or f"#{g}", chi == seat, bool(ab), g, i) for g, chi, ab, i in f.get("p") or []],
                riv=[(nome_grp(g) or f"#{g}", chi == seat) for g, chi in f.get("r") or []],        # le carte rivelate (il censimento, 14 nov 2026)
                mes=[s_ == seat for s_ in f.get("s") or []],                                          # chi rimescola il grimorio: True tu
                # i segni che restano sul tavolo (14 nov 2026): per id, con i nomi delle carte sotto; la velocita' (tua, sua)
                segni={i_: dict(v_, sotto=[nome_grp(g_) or f"#{g_}" for g_ in v_.get("sotto") or []],
                                porta=[(a_, nome_grp(g_) or f"#{g_}") for a_, g_ in v_.get("porta") or []],
                                **({"copia_di": nome_grp(v_["copia_di"]) or f"#{v_['copia_di']}"} if v_.get("copia_di") else {}),
                                **({"gioca": ((nome_grp(v_["gioca"][0]) or f"#{v_['gioca'][0]}") if v_["gioca"][0] else "Face-down card",
                                               v_["gioca"][1] == seat, v_["gioca"][2])} if v_.get("gioca") else {}))
                       for i_, v_ in (f.get("x") or {}).items()},
                # lo scry (14 nov 2026): le carte guardate, (nome o None se non si vede, tue?, sopra?)
                scry=[(nome_grp(e_[0]) if e_[0] else None, e_[1] == seat, bool(e_[2]), len(e_) > 3 and bool(e_[3])) for e_ in f.get("sc") or []],
                mn=[(i_, c_) for i_, c_ in f.get("mn") or []],       # il mana che vola dalle fonti alla magia (id della fonte, colore)
                mnd=f.get("mnd"),        # dove va il mana speso, se non e' una magia dalla mano: il permanente che attiva l'abilita' o che si paga
                pc=list(f.get("pc") or []), pd=dict(f.get("pd") or {}),       # le copie in pila; da quale creatura parte la copia preparata
                pz={k_: [z_, z_o == seat] for k_, (z_, z_o) in (f.get("pz") or {}).items()},      # da quale pila e' lanciata (tua?)
                mp=(((f.get("mp") or [[], []])[seat - 1]), ((f.get("mp") or [[], []])[2 - seat])),      # il mana in riserva (tuo, suo)
                vel=((f.get("vel") or {}).get(seat), (f.get("vel") or {}).get(2 if seat == 1 else 1)),
                # le tue giocate legali in questo passo (16 nov 2026): (nome, id, lancio|terra|abilita' C/P/A, zona mano/campo/esi/cim)
                pt=[tuple(x_) for x_ in f.get("pt") or []],
                pf=list(f.get("pf") or []),        # le carte il cui potenziamento e' appena finito (16 nov 2026)
                hv=list(f.get("hv") or []),       # le carte che l'avversario ha avuto sotto il mouse in questo passo (16 nov 2026)
                # cosa Arena ti ha chiesto e detto in questo passo (16 nov 2026, «vai monta»): chi poteva attaccare o bloccare, i bersagli legali, le
                # opzioni del lancio, «scegli N», il danno previsto, gli avvisi, le emote, il dado, il testo delle abilita' in pila
                info=_info_foto(f, seat),        # i potenziamenti del passo: (id, forza, costituzione), «got +3/+3» (16 nov 2026)
                gioc=[(nome_grp(e_[3]) or f"#{e_[3]}", e_[0], e_[1], e_[2]) for e_ in ((f.get("gi") or {}).get("a") or [])]
                if (f.get("gi") or {}).get("chi") in (None, seat) else [])


VERBI = ("paid", "played", "cast", "drew", "gained", "lost", "created", "attacked", "discarded", "sacrificed", "turn", "conceded", "scried", "revealed", "shuffled", "surveilled", "chose")


def azioni_partita(x):
    """Il replay azione per azione di una partita dal tuo posto (replay_log, 12 nov 2026): [(nome, foto, turno, relazioni, eventi, danni)], o None senza log.
    Gli eventi: [(tuo?, testo)] col soggetto («You», «Opponent») e i giocatori nei testi («you», «the opponent»)."""
    if x.get("simulata"):       # una partita del motore di partita (partite_motore.py, 24 nov 2026): i passi li ha gia' fatti lui
        import partite_motore
        return partite_motore.azioni(x)
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
            rel = dict(tipo="spell", nome=nome_grp(r_["g"]), g=r_["g"], mio=r_["chi"] == seat, ab=r_["ab"], bers=[lato(b_) for b_ in r_["bers"]], colpiti=colpiti_di(r_),
                       fuori=_fuori(r_.get("fuori"), seat), da=list(r_.get("da") or []))       # chi ha fatto scattare l'abilita' (15 nov 2026)
        nome = f"{'You' if fr['att'] == seat else 'Opponent'} T{(fr['t'] + 1) // 2} · {fr['step'] or '-'}"
        foto_ = gira_foto(fr["foto"], seat)
        if foto_ is not None:       # la foto com'e' nel log e chi e' di turno: servono al voto EV di ogni fase (19 nov 2026, ev_partita.righe_fasi)
            foto_["_grezza"], foto_["_att"] = fr["foto"], fr["att"]
        inf_ = (foto_ or {}).get("info") or {}
        if inf_.get("pp"):
            # hai passato potendo giocare: conta solo quando chiudi il tuo turno (seconda fase principale, fine) con una terra o una magia ancora
            # giocabili; passare con un'istantanea in mano o dalla prima fase al combattimento e' normale (16 nov 2026: senza questo, 256 passi su 256)
            ist_ = {(e_[0], e_[1]) for e_ in (fr["foto"].get("gi") or {}).get("a") or [] if len(e_) > 5 and e_[5]}
            mie_ = [e_[0] for e_ in (foto_ or {}).get("gioc") or [] if e_[2] in ("C", "P") and (e_[1], e_[2]) not in ist_]
            if fr["att"] == seat and fr["step"] in ("Main2", "End") and mie_ and not (foto_ or {}).get("pila"):
                inf_["pp"] = list(dict.fromkeys(mie_))
            else:
                inf_.pop("pp", None)
        out.append((nome, foto_, fr["t"], rel, ev, [(lato(d_[0]), d_[1]) for d_ in fr["danni"]],
                    [(lato(d_[0]), d_[1], d_[2] if len(d_) > 2 else None) for d_ in fr["danni"]]))       # il settimo: chi infligge ogni danno
    if out and (out[0][1].get("mio") or out[0][1].get("suo")):
        # il passo zero, il campo vuoto con la mano tenuta (16 nov 2026, Autore: «perche' a volte il replay parte con gia' terre in campo?»): il
        # primo passo del log e' gia' la prima terra giocata, e senza un passo prima quella terra non entrava mai in campo con la sua animazione
        f0 = dict(out[0][1])
        mie = [c[0] for c in f0.get("mio") or [] if not c[2]] if all(len(c) > 2 for c in f0.get("mio") or []) else []
        f0.update(mio=[], suo=[], pila=[], mn=[], mnd=None, pz={}, pd={}, pc=[], scry=[], riv=[], mes=[],
                  mano=list(f0.get("mano") or []) + mie, n_suo=(f0.get("n_suo") or 0) + len([c for c in f0.get("suo") or [] if len(c) > 2 and not c[2]]))
        f0["info"] = dict(f0.get("info") or {})
        f0["_grezza"] = None
        for k_ in ("dado", "mul", "mdec", "parte"):      # le righe dell'inizio stanno solo sul passo zero
            (out[0][1].get("info") or {}).pop(k_, None)
        out.insert(0, (out[0][0].split(" · ")[0] + " · Game start", f0, out[0][2], None, [(True, "The game begins")], [], []))
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

# La copia su disco delle righe (21 nov 2026, Autore: «La lentezza del Leak Finder all'apertura»): riga() costava 8,4 s su 10,7 a freddo per 595 partite.
# Ogni riga si ricorda per (partita, record di matchup_log, partita di partite_log, dato di mana_aperto) e per l'ambiente (il codice dell'app, le regole,
# il database delle carte): se cambia una cosa sola dell'ambiente si rifanno tutte, come prima; una partita nuova si fa da sola. Solo quello che esce da
# riga(): sessioni, serie, versioni e draft si rifanno sempre, perche' dipendono dalle altre partite. RIGHE_COPIA=0 la spegne (le prove d'identita').
import hashlib as _hashlib  # noqa: E402
import pickle as _pickle  # noqa: E402 - solo per l'impronta di una riga (dumps), mai per leggere un file
import marshal as _marshal  # noqa: E402
import datetime as _dt  # noqa: E402
_F_RIGHE = None
_RIGHE_MEM = {}


def _f_righe():
    global _F_RIGHE
    if _F_RIGHE is None:
        from ambiente import LOGDIR
        _F_RIGHE = os.path.join(LOGDIR, "cache", "righe_analizzatore.marshal")
    return _F_RIGHE


_AMB = {}


def _ambiente_righe():
    """L'impronta di tutto quello da cui riga() dipende oltre la partita: i .py dell'app e del Companion, le regole, il database delle carte.
    Ricordata 60 s (23 nov 2026, Autore: «l'app sembra lenta a caricarsi»: il riscaldamento del voto per fase la chiedeva a ogni partita, e ogni volta
    percorreva tutti i file del Companion; a regime era la maggior parte del tempo della finestra)."""
    import time as _t
    if _AMB.get("v") is not None and _t.time() - _AMB.get("t", 0) < 60:
        return _AMB["v"]
    _AMB["v"] = _ambiente_calcola()
    _AMB["t"] = _t.time()
    return _AMB["v"]


def _ambiente_calcola():
    h = _hashlib.sha1()
    radice = percorsi.ROOT
    for f_ in (os.path.join(radice, "Dati", "scryfall", "carte.json"),):      # i formati e l'identita' di colore delle carte
        try:
            st_ = os.stat(f_)
            h.update(f"{f_}:{st_.st_mtime_ns}:{st_.st_size};".encode())
        except OSError:
            pass
    for cart, est in ((os.path.join(radice, "Companion"), ".py"), (os.path.join(radice, "Regole"), ".json"),
                      (os.path.join(radice, "Dati", "untapped", "arena_cards"), ".json")):
        for d_, _sub, files in os.walk(cart):
            if "__pycache__" in d_:
                continue
            for f in files:
                if f.endswith(est):
                    try:
                        st_ = os.stat(os.path.join(d_, f))
                        h.update(f"{d_}/{f}:{st_.st_mtime_ns}:{st_.st_size};".encode())
                    except OSError:
                        pass
    try:
        import mana_aperto
        h.update(str(mana_aperto.VERSIONE).encode())
    except Exception:       # noqa: BLE001
        pass
    return h.hexdigest()


def _chiave_riga(p, r):
    h = _hashlib.sha1()
    h.update(_pickle.dumps((p, r), protocol=5))
    d = _MANA.get(r.get("partita"))
    h.update(b"m" if d else b"-")
    f_ = indice_schede().get((r.get("partita") or "")[:8])        # la scheda in Partite/ (puo' arrivare dopo la partita, o essere riscritta)
    try:
        h.update(str(os.stat(f_).st_mtime_ns).encode() if f_ else b"senza scheda")
    except OSError:
        h.update(b"senza scheda")
    if d:
        h.update(str(len(d.get("azioni") or [])).encode()); h.update(str(len(d.get("momenti") or [])).encode())
    return h.hexdigest()


def _riga_dumps(x):
    """Una riga in marshal (solo dati, mai codice: SICUREZZA.md R2; fino al 23 nov 2026 era pickle): la data come testo."""
    q = x.get("quando")
    return _marshal.dumps(dict(x, quando=q.isoformat()) if isinstance(q, _dt.datetime) else x)


def _riga_loads(b):
    x = _marshal.loads(b)
    q = x.get("quando")
    if isinstance(q, str):
        x["quando"] = _dt.datetime.fromisoformat(q)
    return x


def _copia_righe():
    """{chiave: riga in pickle} della copia su disco, se l'ambiente e' lo stesso; {} se no."""
    if os.environ.get("RIGHE_COPIA") == "0":
        return {}
    amb = _ambiente_righe()
    _RIGHE_MEM["amb"] = amb
    if _RIGHE_MEM.get("letta") == amb:
        return _RIGHE_MEM.get("righe") or {}
    try:
        with open(_f_righe(), "rb") as h:
            c = _marshal.loads(h.read())
        righe_ = c["righe"] if c.get("amb") == amb else {}
    except Exception:       # noqa: BLE001 - copia assente o rotta: si rifa' tutto
        righe_ = {}
    _RIGHE_MEM.update(letta=amb, righe=righe_)
    return righe_


def _salva_righe(nuove):
    if os.environ.get("RIGHE_COPIA") == "0" or "amb" not in _RIGHE_MEM:
        return
    if _RIGHE_MEM.get("letta") == _RIGHE_MEM["amb"] and _RIGHE_MEM.get("righe") == nuove:
        return
    try:
        f = _f_righe()
        os.makedirs(os.path.dirname(f), exist_ok=True)
        with open(f + ".tmp", "wb") as h:
            _marshal.dump(dict(amb=_RIGHE_MEM["amb"], righe=nuove), h)
        os.replace(f + ".tmp", f)
        _RIGHE_MEM.update(letta=_RIGHE_MEM["amb"], righe=nuove)
    except OSError:
        pass


def righe(partite=None):
    """Tutte le partite dei log come righe dell'analizzatore, in ordine di tempo. Ricordate finche' i log non cambiano."""
    import matchup_log as MU
    partite_vere = partite is None
    if partite is None:
        import partite_log
        partite, _n = partite_log.partite()
    partite = [p for p in partite if not p.get("bot") and p.get("vinta") is not None]
    firma = (len(partite), partite[-1].get("matchId") if partite else None)       # partite_log da' gia' le partite dell'account mostrato
    if _CACHE.get("firma") == firma:
        return _CACHE["righe"]
    _SCHEDE.clear()     # le schede di Partite/ si rileggono: una partita appena finita ha la sua scheda dopo la prima lettura (21 nov 2026, il debug)
    _TERRE.clear()      # una rilettura dei log rifa' anche le terre (una carta nuova del database)
    try:        # il mana aperto: dalla copia su disco, e le partite nuove lette adesso (la prima volta ~10 s per 450 partite)
        import mana_aperto
        _MANA.clear(); _MANA.update(mana_aperto.tutti(ids={p.get("matchId") for p in partite}))
    except Exception:       # noqa: BLE001 - senza i pezzi di log le situazioni del mana restano None
        _MANA.clear()
    out = []
    vere = partite_vere
    copia = _copia_righe() if vere else {}
    nuove = {}
    for p in partite:
        r = MU.record(p)
        if r:
            k = _chiave_riga(p, r)
            b = copia.get(k)
            if b is not None:
                try:
                    out.append(_riga_loads(b)); nuove[k] = b
                    continue
                except Exception:       # noqa: BLE001 - una voce rotta si rifa'
                    pass
            x = riga(p, r)
            out.append(x)
            nuove[k] = _riga_dumps(x)
    if vere:        # solo le partite dei log: le prove con partite finte non toccano la copia
        _salva_righe(nuove)
    sessioni(out)
    import variabili_c as VC
    VC.serie(out)       # C6: la partita prima e le sconfitte di fila
    VC.versioni(out)    # C8: le versioni della lista
    try:                # i pick del draft (15 nov 2026, draft_log.py): ogni partita Limited prende il suo draft
        import draft_log as DL
        DL.assegna(out, sys.modules[__name__])
    except Exception:      # noqa: BLE001 - senza i draft le voci del draft restano vuote
        pass
    out.sort(key=lambda x: x["quando"])
    _CACHE.update(firma=firma, righe=out)
    return out


# ------------------------------------------------------------------ le variabili
def _tutte(chiave):
    return lambda x, v: x.get(chiave) == v


def evento_breve(ev):
    """Un evento limited senza la data dell'apertura: «QuickDraft_FRA_20261008» e «QuickDraft_FRA_20261027» sono lo stesso evento, «QuickDraft_FRA» (19 nov
    2026: la tendina Event del Limited elenca gli eventi del gioco, non le loro riaperture). Le code del Constructed restano come sono."""
    m = re.fullmatch(r"([A-Za-z]+)_([A-Z0-9]{2,5})_\d{8}", ev or "")
    return f"{m.group(1)}_{m.group(2)}" if m else ev


# gli eventi limited del gioco (19 nov 2026, Autore: «nella tendina event dobbiamo avere tutti gli eventi di limited», «non solo i miei»; la regola n.1):
# dal calendario di Wizards (Regole/calendario_eventi.json, aperti e in arrivo, e Regole/calendario_set.json, anche i passati), il set dal suo nome
# (Companion/Grafica/set/nomi.json). Un tipo col nome interno di Arena verificato sui log diventa il suo codice (QuickDraft_FRA): le tue partite ci cadono
# dentro; gli altri (Pick-Two, Cube, Arena Direct, Contender...) restano col nome del calendario, «cal:...», finche' non se ne vede uno nei log.
PREFISSI_LIMITED = {"Quick Draft": "QuickDraft", "Premier Draft": "PremierDraft", "Flashback Premier Draft": "PremierDraft", "Traditional Draft": "TradDraft",
                    "Sealed": "Sealed"}
_CAL_SET = {"quick": "Quick Draft", "premier": "Premier Draft", "trad": "Traditional Draft", "sealed": "Sealed", "trad_sealed": "Traditional Sealed"}
_ORDINE_TIPI = ("QuickDraft", "PremierDraft", "TradDraft", "Sealed")


def eventi_limited_gioco():
    """Gli eventi limited del gioco, dal calendario: [(valore del filtro, data d'inizio)], i codici di Arena prima per tipo, poi gli altri; i piu' nuovi
    prima."""
    nomi = {}
    try:
        with open(os.path.join(percorsi.ROOT, "Companion", "Grafica", "set", "nomi.json"), encoding="utf-8") as f:
            nomi = {v.lower(): k for k, v in json.load(f).items()}
    except (OSError, ValueError):
        pass
    voci = []           # (tipo, titolo, codice del set o None, inizio)
    try:
        with open(os.path.join(percorsi.ROOT, "Regole", "calendario_set.json"), encoding="utf-8") as f:
            for cod, d in (json.load(f).get("set") or {}).items():
                for k_, tipo in _CAL_SET.items():
                    for a, _b in d.get(k_) or []:
                        voci.append((tipo, d.get("nome") or cod, cod, a))
    except (OSError, ValueError):
        pass
    try:
        with open(os.path.join(percorsi.ROOT, "Regole", "calendario_eventi.json"), encoding="utf-8") as f:
            for e in json.load(f).get("eventi") or []:
                tit = (e.get("titolo") or "").strip()
                cod = nomi.get(re.sub(r"\s*\(.*\)$", "", tit).lower()) if tit else None
                voci.append((e.get("tipo") or "", tit, cod, e.get("inizio") or ""))
    except (OSError, ValueError):
        pass
    out = {}
    for tipo, tit, cod, inizio in voci:
        if tipo in PREFISSI_LIMITED and cod:
            v = f"{PREFISSI_LIMITED[tipo]}_{cod}"
        else:
            v = "cal:" + (f"{tipo} · {tit}" if tit else tipo)
        if v not in out or inizio < out[v]:
            out[v] = inizio
    chiave = lambda kv: (_ORDINE_TIPI.index(kv[0].split("_")[0]) if not kv[0].startswith("cal:") and kv[0].split("_")[0] in _ORDINE_TIPI else 9,
                         "".join(chr(0x10FFFF - ord(c)) for c in kv[1]))
    return sorted(out.items(), key=chiave)


VARIABILI = [       # (chiave, nome, come si legge il valore dalla riga, test personalizzato o None)
    ("formato", "Format", lambda x: NOMI_FMT.get(x["formato"], x["formato"].title())),
    ("evento", "Event", lambda x: evento_breve(x.get("evento"))),
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
def turno_nome(n):
    """Come si legge un campo dei turni: «turn 3», «turn 11+» (L), «any turn» (A)."""
    return {"A": "any turn", "L": f"turn {TURNI_FILTRO + 1}+"}.get(str(n), f"turn {n}")


EXTRA += [(f"t_{pre}{chi}{suf}{n}", nome.format(n=turno_nome(n)), (lambda x, k=f"{pre}{chi}{suf}{n}": ((x.get("per_turno") or {}).get(k) or [None])[0]))
          for chi, tu, lui_ in (("io", "You", "the opponent's"), ("lui", "Opponent", "your"))
          for pre, suf, nome in (("", "", tu + " · {n} cast"), ("", "x", tu + " · " + lui_ + " {n} cast"),
                                 ("a", "", tu + " · {n} attack"), ("d", "", tu + " · " + lui_ + " {n} defense"),
                                 ("m", "", tu + " · {n} attack · " + ("the opponent's" if chi == "io" else "your") + " untapped lands"),
                                 ("p", "", tu + " · {n} draws"), ("p", "x", tu + " · " + lui_ + " {n} draws"),
                                 ("q", "", tu + " · {n} · when " + ("you" if chi == "io" else "they") + " could attack"),
                                 ("u", "", tu + " · {n} · mana left unused"))
          for n in CAMPI_TURNO]
EXTRA += [(f"t_eff{chi}", f"{tu} · mana used in the first 5 turns (spent on lands; grade C)", (lambda x, k=f"eff{chi}": ((x.get("per_turno") or {}).get(k) or [None])[0]))
          for chi, tu in (("io", "You"), ("lui", "Opponent"))]
EXTRA += [(f"t_pe{chi}", f"{tu} · extra draws in one turn (turns 1-{TURNI_FILTRO})", (lambda x, k=f"pe{chi}": ((x.get("per_turno") or {}).get(k) or [None])[-1]))
          for chi, tu in (("io", "You"), ("lui", "Opponent"))]
# i filtri situazionali dai replay (13 nov 2026, situazioni_replay) e la prima creatura dell'avversario
EXTRA += [("s_" + k_, nome_, (lambda x, k=k_: (x.get("situa") or {}).get(k))) for k_, (nome_, _o) in SITUA_NOMI.items()]
EXTRA += [("senza_lui", "Opponent · no creature cast by", lambda x: (valori_di("senza_lui", x) or [None])[0])]
# i leak (13 nov 2026, leak.py, voci L1, L4, L7 del censimento): Yes o No per partita; indizi di grado C
EXTRA += [(f"leak_{k_}", f"Leak · {n_}", (lambda x, k_=k_: __import__("leak").valore(x, k_)))
          for k_, n_ in (("l1", "missed a land drop with a land in hand"), ("l2", "unused mana with a castable creature in hand"),
                         ("l3", "creature cast before your attack"), ("l4", "chump block at high life"), ("l5", "unfavourable trade"),
                         ("l6", "instant on their turn while they were tapped out on yours"), ("l7", "conceded with outs"),
                         ("l8", "lands tapped the wrong way"), ("l9", "missed attack into an open board"),
                         # il Leak Finder (15 nov 2026)
                         ("l10", "instant cast on your turn that lost value"), ("l11", "missed lethal on board"),
                         ("l12", "kept a 7 the format says to mulligan"), ("l13", "sent back a 7 the format says to keep"),
                         ("l14", "land played before a draw or scry spell"), ("l15", "held mana up and never used it"))]
# cimitero ed esilio (14 nov 2026, cimitero.py): grado C, nessun peso nel costo (misurati: non predicono le vittorie oltre al vantaggio)
import cimitero as _CM  # noqa: E402
EXTRA += [(k_, n_, (lambda x, k_=k_: (x.get("cimitero") or {}).get(k_))) for k_, n_ in _CM.NOMI.items()]
# C2, C3, C6, C7, C9 (13 nov 2026, variabili_c.py)
import variabili_c as _VC  # noqa: E402
EXTRA += [(k_, n_, (lambda x, k_=k_: x.get(k_))) for k_, n_ in _VC.NOMI.items()]
# la probabilita' di vincere nella partita (14 nov 2026, la pagella dell'enciclopedia, capitoli 15 e 22: «partite gia' vinte perse», «rimonte», la forma della
# partita come le Game Shapes di chess.com): la P di p_foto a ogni fine turno, dal tuo posto (grado C: il modello e' del limited, nel costruito estrapola)
_PROB = {}
ORDINE_PROB = {"p_max": ("80%+", "60-80%", "40-60%", "Under 40%"), "p_min": ("Under 20%", "20-40%", "40-60%", "60%+"),
               "forma": ("Dominated", "Comeback", "Collapse", "Seesaw", "Outclassed", "Close all game"),
               "svolta": ("For you, on your turn", "For you, on their turn", "For them, on your turn", "For them, on their turn"),
               "svolta_fase": ("Turns 1-3", "Turns 4-6", "Turns 7+")}
NOMI_PROB = {"p_max": "Your highest win chance in the game", "p_min": "Your lowest win chance in the game", "forma": "Game shape (win chance over the game)",
             "svolta": "The biggest swing in win chance", "svolta_fase": "The biggest swing came in your"}


def prob_partita(x):
    """{p_max, p_min, forma, svolta, svolta_fase} di una partita, o {} senza le foto. La P dopo ogni turno (p_foto, letta come all'inizio del turno dopo).
    La forma: Comeback (vinta da sotto il 20%), Collapse (persa da sopra l'80%), Seesaw (la P passa il 50% tre volte o piu'), Dominated (vinta senza mai
    scendere sotto il 40%), Outclassed (persa senza mai salire sopra il 40%), Close all game (il resto). La svolta: il salto di P piu' grande fra due fine turno,
    per chi e nel turno di chi."""
    k = x.get("partita")
    d = _MANA.get(k) or {}
    firma = (k, len(d.get("foto") or []))
    if firma in _PROB:
        return _PROB[firma]
    seat, ps = x.get("seat"), []
    for t, att, f in d.get("foto") or []:
        if isinstance(f, dict):
            p = p_foto(f, seat, att != seat, (t + 2) // 2, x.get("inizia"), x.get("mulligan"), x.get("tipo"))
            if p is not None:
                ps.append((t, att, p))
    out = {}
    if ps:
        pp = [p for _t, _a, p in ps]
        hi, lo = max(pp), min(pp)
        out["p_max"] = "80%+" if hi >= 80 else "60-80%" if hi >= 60 else "40-60%" if hi >= 40 else "Under 40%"
        out["p_min"] = "Under 20%" if lo < 20 else "20-40%" if lo < 40 else "40-60%" if lo < 60 else "60%+"
        passa50 = sum(1 for a_, b_ in zip(pp, pp[1:]) if (a_ - 50) * (b_ - 50) < 0)
        vinta = x.get("vinta")
        out["forma"] = ("Comeback" if vinta and lo < 20 else "Collapse" if not vinta and hi >= 80 else "Seesaw" if passa50 >= 3 else
                        "Dominated" if vinta and lo >= 40 else "Outclassed" if not vinta and hi < 40 else "Close all game")
        salti = [(b_[2] - a_[2], b_[0], b_[1]) for a_, b_ in zip([(0, None, 50)] + ps, ps)]
        dp, t, att = max(salti, key=lambda z: abs(z[0]))
        out["svolta"] = ("For you" if dp > 0 else "For them") + (", on your turn" if att == seat else ", on their turn")
        n = (t + 1) // 2
        out["svolta_fase"] = "Turns 1-3" if n <= 3 else "Turns 4-6" if n <= 6 else "Turns 7+"
    _PROB[firma] = out
    return out


EXTRA += [(k_, n_, (lambda x, k_=k_: prob_partita(x).get(k_))) for k_, n_ in NOMI_PROB.items()]
# la mano da 7 contro la tabella del mulligan (14 nov 2026, la pagella dell'enciclopedia, D7 e V19: Regole/mulligan.json, misurata sul Premier di 17Lands:
# con 2-5 terre si tiene, con 1 e' pari, 0 e 6-7 sono mulligan; nel costruito da 60 carte e' un ripiego, grado C)
ORDINE_MULL_TAB = ("Kept a 7 the table keeps (2-5 lands)", "Kept a 7 with 1 land (even)", "Kept a 7 the table mulligans (0, 6-7 lands)",
                   "Sent back a 7 the table keeps (2-5 lands)", "Sent back a 7 the table mulligans")


def mull_tabella(x):
    if (x.get("mulligan") or 0) > 0:
        prima = (x.get("scartate") or [None])[0]
        if prima is None:
            return None
        return ORDINE_MULL_TAB[3] if 2 <= prima <= 5 else ORDINE_MULL_TAB[4]
    t = x.get("terre")
    if t is None:
        return None
    return ORDINE_MULL_TAB[0] if 2 <= t <= 5 else ORDINE_MULL_TAB[1] if t == 1 else ORDINE_MULL_TAB[2]


# il Constructed a 60 carte ha la sua regola (14 nov 2026, Autore: «anche se analizzo constructed i filtri di mulligan lavorano per limited, no, i filtri
# devono adattarsi se sono in constructed o in limited in maniera differente»). Una tabella misurata come quella di 17Lands per il 60 carte non c'e' (cercata il
# 14 nov 2026); la regola e' quella di gamertagmythras.com/blog/magic-the-gathering/mtg-mulligan-guide-london-mulligan (letta lo stesso giorno, grado B):
# 0-1 terre mulligan, 2 si tiene solo con giocate presto, 3-4 il range ideale, 5 si tiene se le magie sono buone, 6-7 mulligan
ORDINE_MULL_60 = ("Kept a 7 with 3-4 lands (ideal)", "Kept a 7 with 2 or 5 lands (it depends)", "Kept a 7 the rule mulligans (0-1, 6-7 lands)",
                  "Sent back a 7 with 3-4 lands (the rule keeps)", "Sent back a 7 with 2 or 5 lands (it depends)", "Sent back a 7 the rule mulligans")


def mull_60(x):
    """La mano da 7 contro la regola del Constructed a 60 carte (sopra); None nel Limited o senza i dati."""
    if x.get("tipo") != "Constructed":
        return None
    if (x.get("mulligan") or 0) > 0:
        prima = (x.get("scartate") or [None])[0]
        if prima is None:
            return None
        return ORDINE_MULL_60[3] if 3 <= prima <= 4 else ORDINE_MULL_60[4] if prima in (2, 5) else ORDINE_MULL_60[5]
    t = x.get("terre")
    if t is None:
        return None
    return ORDINE_MULL_60[0] if 3 <= t <= 4 else ORDINE_MULL_60[1] if t in (2, 5) else ORDINE_MULL_60[2]


EXTRA += [("mull_tabella", "Your 7-card decision against the measured mulligan table (Limited)", lambda x: mull_tabella(x) if x.get("tipo") != "Constructed" else None),
          ("mull_60", "Your 7-card decision against the 60-card rule (Constructed)", mull_60)]
# le voci di un formato solo: Advanced filters mostra solo quelle del formato che analizzi
SOLO_TIPO = {"mull_tabella": "Limited", "mull_60": "Constructed"}
ORDINE_DURATA = ("Under 5 minutes", "5-10 minutes", "10-20 minutes", "20+ minutes")      # sui log del 14 nov: costruito 5,3 minuti in media, limited 11,5
EXTRA += [("durata", "Game length in minutes", lambda x: None if not x.get("minuti") else ORDINE_DURATA[0] if x["minuti"] < 5 else ORDINE_DURATA[1]
           if x["minuti"] < 10 else ORDINE_DURATA[2] if x["minuti"] < 20 else ORDINE_DURATA[3]),
          ("stagione", "Ranked season", lambda x: None if x.get("stagione") is None else f"Season {x['stagione']}")]
# i pick del draft (15 nov 2026, «prosegui con i pick del draft»): draft_log.py; solo nel Limited
import draft_log as _DL  # noqa: E402
EXTRA += [(k_, n_, (lambda x, k_=k_: x.get(k_))) for k_, n_ in _DL.NOMI.items()]
SOLO_TIPO.update({k_: "Limited" for k_ in _DL.NOMI})
# il tempismo degli istantanei e dei flash (14 nov 2026, D2-D3 del censimento, M2-M4): tempismo.py
import tempismo as _TM  # noqa: E402
EXTRA += [(k_, n_, (lambda x, k_=k_: _TM.valore(x, k_))) for k_, n_ in _TM.NOMI.items()]
# le voci di combattimento e di interazione della pagella (14 nov 2026): voci_partita.py
import voci_partita as _VP  # noqa: E402
EXTRA += [(k_, n_, (lambda x, k_=k_: _VP.valore(x, k_))) for k_, n_ in _VP.NOMI.items()]
# C1 (13 nov 2026): le terre pescate contro il caso, entro il tuo turno 3, 5, 7
EXTRA += [(f"luck{N}", f"Lands drawn by your turn {N} · vs chance", (lambda x, N=N: (((x.get("fortuna") or {}).get("turni") or {}).get(N) or {}).get("classe")))
          for N in TURNI_FORTUNA]
for _k, _n, _f in EXTRA:
    NOME[_k], LEGGI[_k] = _n, _f
# il Board e i ruoli (16 nov 2026): i nomi e le voci delle famiglie nuove; non entrano in EXTRA (Split by, Group by e Spots ne avrebbero centinaia in piu')
for _n_ in CAMPI_TURNO:
    _tn = turno_nome(_n_)
    _quando = lambda di, n=_n_, tn=_tn: f"any of {di} turns" if n == "A" else f"{di} {tn}"       # «start of any of your turns», non «your any turn»
    for _ch, _Tu in (("io", "You"), ("lui", "Opponent")):
        for _x, _di in (("", "your" if _ch == "io" else "their"), ("x", "the opponent's" if _ch == "io" else "your")):
            for _a, _nm, _voci in BOARD_AREE:
                NOME[f"t_b{_a}{_ch}{_x}{_n_}"] = f"{_Tu} · {_nm.lower()} at the start of {_quando(_di)}"
                ORDINE_VALORI[f"t_b{_a}{_ch}{_x}{_n_}"] = _voci
            NOME[f"t_r{_ch}{_x}{_n_}"] = f"{_Tu} · {_di} {_tn} · cast, by role"
            ORDINE_VALORI[f"t_r{_ch}{_x}{_n_}"] = ORDINE_RUOLI
            NOME[f"t_n{_ch}{_x}{_n_}"] = NOME[f"t_nr{_ch}{_x}{_n_}"] = f"{_Tu} · {_di} {_tn} · the card cast"
            NOME[f"t_np{_ch}{_x}{_n_}"] = f"{_Tu} · {_di} {_tn} · the card drawn"
            for _c, _fn in FASI_LANCIO:         # la fase del lancio (18 nov 2026)
                NOME[f"t_k{_c}{_ch}{_x}{_n_}"] = f"{_Tu} · {_di} {_tn} · cast in {_fn}"
                ORDINE_VALORI[f"t_k{_c}{_ch}{_x}{_n_}"] = tuple(v_ for v_ in ORDINE_TIPI if v_ != "Nothing")
                NOME[f"t_k{_c}n{_ch}{_x}{_n_}"] = f"{_Tu} · {_di} {_tn} · the card cast in {_fn}"
            for _a, _nm, _voci in BOARD_AREE:
                if _a in AREE_CON_CARTE:
                    NOME[f"t_nb{_a}{_ch}{_x}{_n_}"] = f"{_Tu} · {_nm.lower()} at the start of {_quando(_di)} · the card"
        NOME[f"t_na{_ch}{_n_}"] = f"{_Tu} · {'your' if _ch == 'io' else 'their'} {_tn} · the attacking card"
        NOME[f"t_nd{_ch}{_n_}"] = f"{_Tu} · {'the opponent' if _ch == 'io' else 'your'} {_tn} · the blocking card"
    for _x, _di in (("", "your"), ("x", "the opponent's")):
        for _a, _nm, _voci in BOARD_AREE:
            if _a in BOARD_AVANTI:
                NOME[f"t_b{_a}vio{_x}{_n_}"] = f"Who's ahead · {_nm.lower()} at the start of {_quando(_di)}"
                ORDINE_VALORI[f"t_b{_a}vio{_x}{_n_}"] = ORDINE_AVANTI
DOVE_FAMIGLIA.update({f"b{_a}": "inizio" for _a, _n, _v in BOARD_AREE})
DOVE_FAMIGLIA.update({f"b{_a}v": "inizio" for _a in BOARD_AVANTI})
DOVE_FAMIGLIA.update(r="magia", n="magia", nr="magia", **{f"k{_c}": "magia" for _c, _f in FASI_LANCIO}, **{f"k{_c}n": "magia" for _c, _f in FASI_LANCIO})
DOVE_FAMIGLIA.update(np="inizio", na="comb", nd="comb", **{f"nb{_a}": "inizio" for _a in AREE_CON_CARTE})
# Hero e Opponent nei nomi dei filtri turno per turno (16 nov 2026, Autore: «you che poi deve essere Hero Player al posto di you ovunque», «non usare
# theyr mai più si usa opponent»)


def _hero(t):
    for a_, b_ in (("the opponent's", "Opponent's"), ("their", "Opponent's"), ("they", "Opponent"), ("your", "Hero's"), ("You", "Hero"), ("you", "Hero")):
        t = re.sub(r"(?<![A-Za-z'])" + re.escape(a_) + r"(?![A-Za-z])", b_, t)
    return t


for _k in [k for k in NOME if k.startswith("t_")]:
    NOME[_k] = _hero(NOME[_k])


# vinta o persa come tendina della fase Opening and first turns (12 nov 2026, Autore: «aggiungiamo la tendina di partita vinta o persa nella sezione opening
# hands and first turns»): non entra negli Spots (spiegherebbe tutto il win rate da sola)
NOME["esito"], LEGGI["esito"] = "Result", (lambda x: "Won" if x["vinta"] else "Lost")
NOME["wr_rif"] = "Win rate"
NOME["lanciate"] = "Card you cast"
NOME["mano_req"] = "Hero's opening hand"
NOME.update(ab_io="Your activated abilities", ab_lui="Opponent's activated abilities")
NOME.update(lanc_t4="Card you cast by your turn 4", finisher="Card in your finish", in_mano="Card in your hand", sue_lanciate="Card the opponent cast", bloccate="Card stuck in your hand",
            **{f"pesc{n}": f"Card found on your turn {n}" for n in range(1, 5)})       # 4 = TURNI_CARTE; i clic della cartella Cards, fuori dagli Spots
ORDINE_VALORI.update(esito=("Won", "Lost"), miei_colori=VARIANTI, economiche=("0", "1", "2+"), crea_mano=("Yes", "No"),
                     fine=("You conceded", "Opponent conceded", "Played to the end", "Timeout"), giorno=GIORNI,
                     pausa=("Under 15 minutes", "15-60 minutes", "Over 1 hour (new session)"), crea_in_mano=("0", "1", "2", "3+"),
                     senza_crea=tuple(f"Your turn {n}" for n in SENZA) + ("The whole game",), suo_mull=("0", "1", "2+"),
                     fine_entro=tuple(f"Your turn {n}" for n in ENTRO), ist_mano=("0", "1", "2+"), str_mano=("0", "1", "2+"),
                     art_mano=("0", "1", "2+"), inc_mano=("0", "1", "2+"), pw_mano=("0", "1", "2+"), bat_mano=("0", "1", "2+"),
                     **{f"t_{pre}{chi}{suf}{n}": o_ for chi in ("io", "lui") for n in CAMPI_TURNO
                        for pre, suf, o_ in (("", "", ORDINE_TIPI), ("", "x", ORDINE_TIPI), ("a", "", ORDINE_ATT), ("d", "", ORDINE_DIF),
                                             ("m", "", ORDINE_APERTE), ("p", "", ORDINE_PESCATE), ("p", "x", ORDINE_PESCATE_X),
                                             ("q", "", ORDINE_SCELTA), ("u", "", ORDINE_MANA))},
                     t_peio=ORDINE_EXTRA, t_pelui=ORDINE_EXTRA, t_effio=ORDINE_EFF, t_efflui=ORDINE_EFF,
                     **{"s_" + k_: ORDINE_SITUA[o_] for k_, (_n, o_) in SITUA_NOMI.items()},
                     senza_lui=tuple(f"Their turn {n}" for n in SENZA) + ("The whole game",), **{f"luck{N}": FORTUNA for N in TURNI_FORTUNA},
                     **{f"leak_l{i}": ("Yes", "No") for i in range(1, 16)}, **_VC.ORDINE, **_CM.ORDINE, **ORDINE_PROB, **_TM.ORDINE, **_VP.ORDINE, mull_tabella=ORDINE_MULL_TAB, mull_60=ORDINE_MULL_60, durata=ORDINE_DURATA, **_DL.ORDINE)


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
    if k in ("ab_io", "ab_lui"):        # le abilita' attivate, «Carta · quando» (attivate_partita)
        return list((x.get("abil") or {}).get(k[3:]) or [])
    if k in ("lanciate", "ev_carte", "ev_giocate", "win_cond"):     # le tue magie lanciate (Cards, 13 nov 2026; le righe EV del 18 nov filtrano allo stesso modo)
        return x.get("mie_lanciate") or []
    if k == "iwd":              # la riga IWD di Cards (C4): una carta pescata o tenuta, come «in_mano»
        return x.get("in_mano") or []
    if k == "rim_valore":       # C13: le Pairs della riga delle rimozioni, sulle magie lanciate
        return x.get("mie_lanciate") or []
    if k in ("minacce", "ev_sue", "sue_quando"):      # C15 e l'EV delle sue carte: sulle sue magie lanciate
        return x.get("sue_lanciate") or []
    if k in ("in_mano", "sue_lanciate", "bloccate", "lanc_t4", "finisher") or re.fullmatch(r"pesc\d", k):      # le altre righe della cartella Cards
        return x.get(k) or []
    if k == "data":
        giorni = (datetime.datetime.now() - x["quando"]).days
        return [n for n, d in DATE if giorni < d]
    if k.startswith("t_"):       # turno per turno: tutti i tipi lanciati in quel turno (una creatura artefatto e' Creature e Artifact)
        if esteso(k):            # in qualunque turno / dal turno 11: le voci di tutti quei turni, una volta (passa li' guarda turno per turno)
            return list(dict.fromkeys(v for t_ in turni_di(k, x) for v in t_))
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
        elif esteso(k):         # qualunque turno / dal turno 11: per gruppo, dopo (turni_comuni)
            continue
        elif k == "mano_req":   # la mano iniziale descritta riga per riga (18 nov 2026): servono tutte le righe
            if v and not mano_soddisfa(x.get("mano_conta"), v):
                return False
        elif isinstance(v, (list, tuple)):
            if not v:
                continue
            ci_sono = collections.Counter(valori_di(k, x))
            if any(ci_sono[i] < n for i, n in collections.Counter(v).items()):      # «Instant», «Instant»: almeno due istantanei
                return False
        elif v not in valori_di(k, x):
            return False
    for chiavi in gruppi_turno(filtri).values():        # i filtri estesi dei turni dello stesso giocatore: tutti veri nello stesso turno
        if not turni_comuni(x, filtri, chiavi):
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


_KW = {}


def _parole(g):
    """Le parole chiave che contano per il modello della P (volare, minaccia, raggiungere, difensore) dal testo della carta; ricordate per grpId."""
    if g not in _KW:
        nome = nome_grp(g) if g not in SENZA_FACCIA else None
        t = ((_carta(nome or "") or {}).get("testo") or "").lower()
        # «flying» da solo o in testa a una frase, non «creatures with flying» (grado C)
        _KW[g] = {k for k in ("flying", "menace", "reach", "defender") if re.search(rf"(?:^|[.,;] ?|\b(?:and|has|gains) ){k}\b", t) and
                  not re.search(rf"with {k}", t.split(".")[0])}
    return _KW[g]


_DRENA = {}


def _drena(g):
    """Le vite che una creatura toglie quando attacca (19 nov 2026, Sanguine Syphoner: «Whenever ~ attacks, each opponent loses 1 life»), dal testo della carta;
    grado C. Ricordate per grpId."""
    if g not in _DRENA:
        nome = nome_grp(g) if g not in SENZA_FACCIA else None
        t = ((_carta(nome or "") or {}).get("testo") or "").lower()
        n = 0
        for m in re.finditer(r"whenever [^.]*?attacks[^.]*?(?:each opponent|target opponent|defending player|the player it'?s attacking) loses (\d+|one|two|three|four)"
                             r" life", t):
            n += {"one": 1, "two": 2, "three": 3, "four": 4}.get(m.group(1)) or int(m.group(1))
        _DRENA[g] = n
    return _DRENA[g]


def letale(f, seat, tocca_me):
    """Il letale sul tavolo (19 nov 2026, Autore: «aveva pti vita per farmi andare letale al turno successivo»): chi tocca attacca con tutte le sue creature
    (a inizio turno si stappano), chi difende blocca con le sue stappate (restano tappate fino al suo turno), ognuna sull'attaccante piu' forte che puo'
    bloccare (volare: solo chi vola o ha portata; minaccia: due bloccanti); i danni che passano piu' le vite che gli attaccanti tolgono attaccando (_drena)
    contro le vite di chi difende. Vale solo se chi difende non ha carte in mano (niente trucchi, niente lampo): True se chi tocca chiude, se no False.
    Grado C: niente doppio colpo, travolgere, abilita' attivate dal campo."""
    if not f or seat not in (1, 2):
        return False
    me, lui = seat - 1, 2 - seat
    a, d = (me, lui) if tocca_me else (lui, me)
    lati = f.get("c") or [[], []]
    v = f.get("v") or [20, 20]
    n = f.get("n") or [0, 0]
    if (n[d] or 0) > 0 or v[d] is None:
        return False
    att = [(c_[3] or 0, _parole(c_[0]), _drena(c_[0])) for c_ in lati[a] or [] if len(c_) > 4 and c_[3] is not None and "defender" not in _parole(c_[0])]
    if not att:
        return False
    blocc = [_parole(c_[0]) for c_ in lati[d] or [] if len(c_) > 4 and c_[3] is not None and not c_[1]]
    drenaggio = sum(z[2] for z in att)
    liberi = sorted(att, key=lambda z: -z[0])
    for kw in blocc:        # ogni bloccante ferma l'attaccante piu' forte che puo' fermare
        for j, (pw, kwa, _dr) in enumerate(liberi):
            if "flying" in kwa and not ({"flying", "reach"} & kw):
                continue
            if "menace" in kwa and len(blocc) < 2:
                continue
            liberi.pop(j)
            break
    return sum(z[0] for z in liberi) + drenaggio >= v[d]


_VC = {}


def _p_carte(f, seat, stato, tipo, giro, tocca_me):
    """La P del modello con le carte come vettori (Motore_EV/valuta_carte.py), o None se manca."""
    if "m" not in _VC:
        try:
            cart = os.path.join(percorsi.ROOT, "Motore_EV")
            if cart not in sys.path:
                sys.path.insert(0, cart)
            import valuta_carte
            _VC["m"] = valuta_carte if valuta_carte.rete() is not None else None
        except Exception:       # noqa: BLE001 - senza il modello nuovo resta quello di prima
            _VC["m"] = None
    VC = _VC["m"]
    if VC is None:
        return None
    try:
        import prob_vittoria as PV
        return VC.p_tavolo(PV.vettore(stato), dict(VC.zone_foto(f, seat), **zone_extra(f, seat)), tipo, giro, tocca_me)
    except Exception:       # noqa: BLE001
        return None


_ZX = {}            # id(foto) -> (seat, grimorio [grp], sue magie lanciate fin li' [grp], scala del grimorio)
_ZX_DI = {}
_GRP_NOME = {}


def _grp_di_nome(n):
    """Un grpId di Arena per nome (non pedina, non ribilanciata), dal database delle carte; None se non c'e'."""
    if not _GRP_NOME:
        try:
            import db_carte
            tt = db_carte.testi()
            for c in db_carte.carte():
                if c.get("isToken") or c.get("IsRebalanced") or "titleId" not in c:
                    continue
                nm = tt.get(c["titleId"])
                if nm:
                    _GRP_NOME.setdefault(nm, c["grpid"])
                    _GRP_NOME.setdefault(nm.split(" // ")[0], c["grpid"])
        except Exception:       # noqa: BLE001
            _GRP_NOME[""] = None
    return _GRP_NOME.get(n) or _GRP_NOME.get(nome_intero(n))


def _zx_partita(x):
    """Le zone in piu' del modello (22 nov 2026: le cinque reti «zone» di Motore_EV/insieme.py) per ogni foto della partita, dal posto dell'Hero:
    lib_u = la lista della partita meno le carte viste fuori dal grimorio (mano, campo senza pedine, cimitero, esilio); vis_o = le magie che l'Opponent
    ha lanciato fino a quel turno (le azioni di mana_aperto). Il posto dell'Opponent non ha la sua lista: li' restano le cinque reti «base»."""
    from collections import Counter
    d = _MANA.get(x.get("partita")) or {}
    deck, seat = x.get("deck") or {}, x.get("seat")
    if not d or not deck or seat not in (1, 2):
        return
    a = seat - 1
    voci = [(0, d.get("mano0"))] + [(t, f) for t, _att, f in d.get("foto") or []]
    nel_gioco = {}
    for _t, f in voci:
        for g in [c_[0] for c_ in ((f or {}).get("c") or [[], []])[a] or []] + list(((f or {}).get("m") or [[], []])[a] or []):
            n = nome_grp(g)
            if n:
                nel_gioco.setdefault(nome_intero(n), g)
    lib0 = Counter()
    for n, q in deck.items():
        g = nel_gioco.get(nome_intero(n)) or _grp_di_nome(n)
        if g:
            lib0[g] += q
    tot = sum(deck.values())
    scala = 40 / tot if tot > 40 else 1.0
    sue = [(t, g) for t, posto, tipo, g, *_r in d.get("azioni") or [] if posto != seat and tipo == "magia" and g]
    for t, f in voci:
        if not f:
            continue
        lib = Counter(lib0)
        fuori = [c_[0] for c_ in (f.get("c") or [[], []])[a] or [] if len(c_) > 2 and not c_[2]]
        for k in ("m", "g", "e"):
            fuori += list(((f.get(k) or [[], []])[a]) or [])
        for g in fuori:
            if lib.get(g, 0) > 0:
                lib[g] -= 1
        _ZX[id(f)] = (seat, [g for g, q in lib.items() for _ in range(q)], [g for tt, g in sue if tt <= t], scala)


def zone_extra(f, seat):
    """{lib_u, vis_o, _lib_scala} per una foto di mana_aperto dal posto seat, o {} se non si sanno (le reti «base» le fanno a meno)."""
    if not f:
        return {}
    R = _CACHE.get("righe")
    if R is not None and _ZX_DI.get("r") is not R:
        _ZX.clear()
        _ZX_DI["r"] = R
        for x in R:
            try:
                _zx_partita(x)
            except Exception:       # noqa: BLE001 - una partita strana resta senza zone in piu'
                pass
    v = _ZX.get(id(f))
    if not v or v[0] != seat:
        return {}
    return {"lib_u": v[1], "vis_o": v[2], "_lib_scala": v[3]}


def con_pila(f):
    """La foto con le magie in pila contate come carte di chi le ha lanciate (24 nov 2026, Note/Replayer_Lacune.md voce 4: la WIN CHANCE scendeva in media
    di 6 punti a ogni lancio e risaliva di 10 alla risoluzione, perche' la carta in pila non stava ne' in mano ne' in campo). Il conto della mano (n) e, per la
    tua mano coi nomi (m), la carta; le abilita' non sono carte e non contano. La foto senza pila torna com'e'."""
    pila = [e for e in f.get("p") or [] if len(e) > 2 and not e[2] and e[1] in (1, 2)]
    if not pila:
        return f
    n = list(f.get("n") or [0, 0])
    m = [list(x or []) for x in (f.get("m") or [[], []])]
    while len(m) < 2:
        m.append([])
    for e in pila:
        i = e[1] - 1
        n[i] = (n[i] or 0) + 1
        if m[i] or (f.get("m") and i < len(f["m"]) and f["m"][i] is not None):
            m[i].append(e[0])
    return dict(f, n=n, m=m)


def p_foto(f, seat, tocca_me, giro, inizia=None, mull=0, tipo=None, vecchia=False, mano_extra=(0, 0)):
    """R8 (13 nov 2026, Autore: «Sì, con la citazione»): la probabilita' di vincere, in punti percentuali, dal tavolo di una foto, col modello del suggeritore
    (Companion/Suggeritore/prob_vittoria.py, Regole/prob_vittoria.json: gradient boosting tarato sui replay pubblici di 17Lands, CC BY 4.0, sei set del
    limited). Vite, creature (forza, costituzione, volare/minaccia/raggiungere, tappate), terre, carte in mano, chi tocca, il giro, chi ha cominciato, i
    mulligan. Il valore delle carte (GIH) no: e' la media del set per tutte, cosi' le due app dicono la stessa cosa. Nel costruito e' un'estrapolazione
    (il modello e' del limited): confronta due tavoli, non e' una promessa. None senza foto o senza il modello.
    mano_extra (UpgradePlan01 passo 2, 20 nov 2026): carte da aggiungere (o togliere) al conto della mano (tua, sua) per la pescata del turno, che il dato
    del modello conta in un momento preciso (ev_partita.pescata_extra); solo il numero, le carte restano quelle della foto."""
    if not f or seat not in (1, 2):
        return None
    try:
        import prob_vittoria as PV
    except Exception:       # noqa: BLE001 - senza il modello niente P
        return None
    f = con_pila(f)
    a, b = seat - 1, 2 - seat
    lati = f.get("c") or [[], []]

    def cre(lato):
        out = []
        for c_ in lato or []:
            if len(c_) < 5 or c_[3] is None:        # non e' una creatura (forza assente)
                continue
            out.append(dict(p=c_[3] or 0, t=c_[4] or 0, kw=_parole(c_[0]), girato=bool(c_[1])))
        return out

    def terre(lato):
        return sum(1 for c_ in lato or [] if not c_[2] and e_terra(nome_grp(c_[0]) or "") )
    miei, suoi = cre(lati[a]), cre(lati[b])
    v = f.get("v") or [20, 20]
    n = f.get("n") or [0, 0]
    stato = dict(tocca_me=1 if tocca_me else 0, N=giro, on_play=1 if inizia else 0, LU=v[a] if v[a] is not None else 20, LO=v[b] if v[b] is not None else 20,
                 miei=miei, suoi=suoi, TERU=terre(lati[a]), TERO=terre(lati[b]), MANU=max(0, (n[a] or 0) + mano_extra[0]), MANO=max(0, (n[b] or 0) + mano_extra[1]), mull=mull or 0,
                 tappati_suoi=sum(c["girato"] for c in suoi) if tocca_me else 0, tappati_miei=0 if tocca_me else sum(c["girato"] for c in miei))
    # il letale sul tavolo, che il modello non vede (19 nov 2026): chi tocca chiude e chi difende non ha carte in mano -> la partita e' decisa (99 e 1, non
    # 100 e 0: qualcosa che non si vede resta possibile)
    # le vite a zero (704.5a, 119.6): la partita e' decisa, per tutti e due i modelli. Fino al 20 nov 2026 lo diceva solo il modello di prima
    # (prob_vittoria.p_vittoria); quello con le carte dava 4-5% a un giocatore a 0 vite (trovato dalla verifica sui gemelli, UpgradePlan01)
    if stato["LU"] <= 0:
        return 0.0
    if stato["LO"] <= 0:
        return 100.0
    if letale(f, seat, tocca_me):
        return 99.0 if tocca_me else 1.0
    # il modello nuovo (19 nov 2026, sessione Magic 22, Motore_EV/valuta_carte.py): ogni carta del tavolo e della tua mano col suo vettore, imparato dal
    # testo e dai replay di 17Lands; nel Constructed ricalibrato sui log. Batte quello di prima sulle stesse righe (Note/Motore_EV_Carte.md).
    # EV_CARTE=0 nell'ambiente torna al modello di prima; vecchia=True lo chiede per i confronti.
    if not vecchia and os.environ.get("EV_CARTE", "1") != "0":
        p = _p_carte(f, seat, stato, tipo, giro, tocca_me)
        if p is not None:
            return 100.0 * p
    try:
        return 100.0 * PV.p_vittoria(stato)
    except Exception:       # noqa: BLE001
        return None


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
    out["tempi"] = tempi_lancio(az, seat, mano, magia, nome_g)
    return out


def tempi_lancio(az, seat, mano, magia, nome_g):
    """R12 (13 nov 2026): per ogni tua magia lanciata, il primo lancio della partita: il giro in cui l'hai lanciata ((turno di Arena + 1) // 2, come i filtri
    turno per turno) e quanti giri l'hai tenuta in mano prima (dalla mano tenuta: giro 1; da una pescata: il suo giro). Una carta lanciata senza che si sappia
    quando ti e' arrivata (da sotto al grimorio, dall'esilio, senza le pescate nel log) ha solo il giro del lancio. -> {nome: [giro_lancio, giri_in_mano|None]}."""
    arrivo = {n_: 1 for n_ in mano}
    out = {}
    for t, s_, cosa, g_, _tp in az:
        if s_ != seat:
            continue
        nm = nome_g(g_)
        if not magia(nm):
            continue
        giro = (t + 1) // 2
        if cosa == "pesca":
            arrivo.setdefault(nm, giro)
        elif cosa == "magia" and nm not in out:
            out[nm] = [giro, (giro - arrivo[nm]) if nm in arrivo else None]
    return out


RIGHE_CARTE = [("in_mano", "MOST FOUND IN YOUR HAND · opening hand and draws"),
               ("pesc1", "YOUR TURN 1 · the opening hand and the first draw"), ("pesc2", "YOUR TURN 2 · drawn on it"),
               ("pesc3", "YOUR TURN 3 · drawn on it"), ("pesc4", "YOUR TURN 4 · drawn on it"),
               ("lanciate", "YOUR MOST CAST SPELLS · cast T: the average turn of the first cast; held: the turns it waited in your hand"), ("lanc_t4", "CAST BY YOUR TURN 4 · Pairs: what you played together early"),
               ("win_cond", "WIN CONDITIONS · the cards that closed your wins: the lethal blow, or the most damage when they conceded; right-click a "
                            "card: its analysis"),
               ("finisher", "FINISHERS · the decisive play of your wins: the biggest swing after which you stayed ahead, 2+ cards"), ("sue_lanciate", "THE MATCHUPS · the opponent's most played cards"),
               ("bloccate", "HARDER TO CAST · in your hand and never cast"),
               ("sue_quando", "THEIR CARDS · WHEN AND ON WHAT: the opponent's turn of their first cast and which of your cards they hit"),
               ("minacce", "THE THREATS THAT BEAT YOU · their cards in more of your losses than your wins; Answers ›: what in your collection removes them"),
               ("rim_valore", "YOUR REMOVAL · ON WHAT: the average mana value of what it removed (a token 0), and how often a token or a card cheaper than it"),
               ("iwd", "DRAWN VS NOT DRAWN · IWD: your win rate when the card came to your hand minus when it stayed in the deck (grey under 15 games)"),
               # il lettore di EV (18 nov 2026, ev_partita): le carte e le giocate, i due livelli piu' micro della spina
               ("ev_carte", "EV IN PLAY · win-probability points the turns gave above or below the usual while the card was on your battlefield; "
                            "Merits ›: what each kind of deed is worth"),
               ("ev_sue", "THEIR CARDS · EV IN PLAY FOR THE OPPONENT: the points their turns gave them while the card was on their battlefield (red: it hurt "
                          "you); Lists ›: their decks rebuilt from the cards you saw"),
               ("ev_giocate", "EV AT CAST · every spell you cast and land you played: how much the win chance moved from that moment to the next "
                              "(a land: with it against without it), against the same card in all your games")]
# le righe per categoria, dalle piu' importanti per chi vuole migliorare il proprio mazzo fino a quelle sull'Opponent (19 nov 2026, Autore: «la rotella del
# row: organizza meglio al suo interno e per categorie i flag delle row: partiamo dalle categorie piu' importanti per noi in alto e scendiamo per quelle vs
# oppo»). Questo e' anche l'ordine in cui la cartella Cards disegna le righe.
GRUPPI_CARTE = (("WHAT YOUR CARDS ARE WORTH", ("ev_carte", "iwd", "ev_giocate")),
                ("WHAT WINS YOUR GAMES", ("win_cond", "finisher")),
                ("WHAT HOLDS YOU BACK", ("bloccate",)),
                ("YOUR HAND AND YOUR DRAWS", ("in_mano", "pesc1", "pesc2", "pesc3", "pesc4")),
                ("WHAT YOU CAST", ("lanciate", "lanc_t4", "rim_valore")),
                ("THE OPPONENT", ("minacce", "ev_sue", "sue_quando", "sue_lanciate")))
BREVI_CARTE = {"ev_carte": ("EV in play", "points the turns gave while the card was on your battlefield"),
               "iwd": ("Drawn vs not drawn", "your win rate when you drew it minus when it stayed in the deck"),
               "ev_giocate": ("EV at cast", "how much the win chance moved when you cast it"),
               "win_cond": ("Win conditions", "the cards that dealt the lethal blow"),
               "finisher": ("Finishers", "the decisive two-card plays of your wins"),
               "bloccate": ("Harder to cast", "in your hand and never cast"),
               "in_mano": ("Most found in your hand", "opening hand and draws"),
               "pesc1": ("Your turn 1", "the opening hand and the first draw"), "pesc2": ("Your turn 2", "drawn on it"),
               "pesc3": ("Your turn 3", "drawn on it"), "pesc4": ("Your turn 4", "drawn on it"),
               "lanciate": ("Your most cast spells", "when you first cast them and how long they waited"),
               "lanc_t4": ("Cast by your turn 4", "what you played together early"),
               "rim_valore": ("Your removal, on what", "the mana value of what it removed"),
               "minacce": ("The threats that beat you", "and the answers you own or can craft"),
               "ev_sue": ("Their cards, EV for them", "and their decks rebuilt from what you saw"),
               "sue_quando": ("Their cards, when and on what", "their turn and which of your cards they hit"),
               "sue_lanciate": ("Their most played cards", "in these games")}
_ORDINE_CARTE = [k for _g, kk in GRUPPI_CARTE for k in kk]
assert sorted(_ORDINE_CARTE) == sorted(k for k, _t in RIGHE_CARTE) and set(BREVI_CARTE) == set(_ORDINE_CARTE)
RIGHE_CARTE = sorted(RIGHE_CARTE, key=lambda kt: _ORDINE_CARTE.index(kt[0]))
CAMPO_CARTE = {"win_cond": "mie_lanciate", "sue_quando": "sue_lanciate", "ev_sue": "sue_lanciate", "ev_carte": "mie_lanciate", "ev_giocate": "mie_lanciate", "lanciate": "mie_lanciate", "iwd": "in_mano", "rim_valore": "mie_lanciate", "minacce": "sue_lanciate"}
NOME["iwd"] = "Card drawn (IWD)"
NOME["ev_carte"] = NOME["ev_giocate"] = "Your card cast"
NOME["ev_sue"] = "Their card cast"
NOME["rim_valore"] = "Your removal cast"
NOME["minacce"] = "Their threat cast"
NOME["win_cond"] = "Your card cast"
NOME["sue_quando"] = "Their card cast"       # la chiave del filtro -> il campo della riga (le altre si chiamano uguali)


# le righe di Cards che hanno un verso (19 nov 2026, Autore: «Sì, aggiungilo», dall'articolo «Tune a Constructed deck»): le righe mettono le carte
# migliori per prime e ne mostrano quante stanno nella larghezza, quindi le peggiori restavano fuori (UW Bouncer: Cathar Commando -7,7 quando pescata).
# «Weakest first» le mette in testa; quelle sotto il minimo di partite restano in fondo in tutti e due i versi.
VALORE_RIGA = {"iwd": "iwd", "ev_carte": "in_campo", "ev_giocate": "ev"}


def deboli_prima(carte, chiave, quante):
    """Le carte della riga dalla piu' debole: prima quelle con abbastanza partite, dal valore piu' basso. -> le prime `quante`."""
    k = VALORE_RIGA[chiave]
    minimo = MINIMO_DEBOLI.get(chiave, 0)
    poche = lambda c: bool(c.get("poche")) or (c.get("n") or 0) < minimo
    return sorted(carte, key=lambda c: (poche(c), c.get(k) if c.get(k) is not None else 0.0))[:quante]


# le partite che servono perche' una carta stia in testa fra le piu' deboli: col minimo delle righe (il totale delle partite in IWD, le copie nelle righe
# EV) una carta pescata in 5 partite su 130 (Day of Judgment, -36) o lanciata una volta (Elrond, -18,6) saliva prima di quelle con 60 partite
MINIMO_DEBOLI = {"iwd": 15, "ev_carte": 5, "ev_giocate": 5}

def riga_carte(r, chiave, quante=40, minimo=5, base=None):
    """Una riga della cartella Cards: le carte della chiave nelle partite r, ognuna una volta per partita, dalla piu' comune; per «bloccate» dalla piu'
    bloccata (le partite in cui e' rimasta in mano sulle partite in cui l'avevi in mano, da `minimo` partite in mano), col win rate di quelle partite.
    -> [dict(nome, n, vinte, perse, wr, quota[, mano, bloccata])]."""
    if chiave in ("ev_carte", "ev_giocate", "ev_sue"):       # il lettore di EV: l'atteso dalle partite base (di solito tutte quelle del tipo)
        import ev_partita as EV_
        return {"ev_carte": EV_.carte, "ev_giocate": EV_.giocate, "ev_sue": EV_.carte_sue}[chiave](r, base if base is not None else r, quante=quante)
    if chiave == "finisher":
        return finisher_coppie(r, quante)
    if chiave in ("win_cond", "sue_quando"):     # 18 nov 2026 (analisi_carta): le win condition, le sue carte nel tempo e sulle tue
        import analisi_carta as AC
        return (AC.win_condition if chiave == "win_cond" else AC.sue_quando)(r, quante)
    if chiave == "iwd":     # C4 (variabili_c.iwd)
        import variabili_c as VC
        return VC.iwd(r, quante)
    if chiave == "minacce":         # C15 (variabili_c.minacce)
        import variabili_c as VC
        return VC.minacce(r, quante)
    if chiave == "rim_valore":      # C13 (variabili_c.valore_rimozioni)
        import variabili_c as VC
        return VC.valore_rimozioni(r, quante)
    campo = CAMPO_CARTE.get(chiave, chiave)
    conta, vinte = collections.Counter(), collections.Counter()
    for x in r:
        for nm in set(x.get(campo) or []):
            conta[nm] += 1
            vinte[nm] += 1 if x["vinta"] else 0
    tot = len(r) or 1
    out = [dict(nome=nm, n=n, vinte=vinte[nm], perse=n - vinte[nm], wr=round(100 * vinte[nm] / n, 1), quota=round(100 * n / tot, 1)) for nm, n in conta.items()]
    if chiave == "lanciate":      # R12: il giro medio del primo lancio e i giri in mano prima
        lanc, tenuti = collections.defaultdict(list), collections.defaultdict(list)
        for x in r:
            for nm, (g_l, g_m) in (x.get("tempi") or {}).items():
                lanc[nm].append(g_l)
                if g_m is not None:
                    tenuti[nm].append(g_m)
        for c in out:
            c["turno_lancio"] = round(sum(lanc[c["nome"]]) / len(lanc[c["nome"]]), 1) if lanc[c["nome"]] else None
            c["in_mano_giri"] = round(sum(tenuti[c["nome"]]) / len(tenuti[c["nome"]]), 1) if tenuti[c["nome"]] else None
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


def frase(filtri, tipo=None):
    """La domanda dei filtri accesi detta di fila (18 nov 2026, Autore: «gli advanced filters costruiscano man mano che aggiungo filtri una frase che
    screma per bene fino a spot specifici»): «Constructed games where Hero, Hero's turn 2, cast in main phase 1: Creature, and Opponent, untapped lands at
    the start of Opponent's turn 3: 2 untapped.» Ogni filtro e' una clausola: il nome (le parti separate da virgole) e il valore; le situazioni Yes/No dette
    come frase. Senza filtri: tutte le partite."""
    pezzi = []
    for k, v in (filtri or {}).items():
        if v is None or v == [] or v == "":
            continue
        if k.startswith("sit:"):
            pezzi.append(etichetta(k, v)[:1].lower() + etichetta(k, v)[1:])
            continue
        nome_ = nome_var(k).replace(" · ", ", ")
        pezzi.append(f"{nome_}: {etichetta(k, v)}")
    testa = f"{tipo} games" if tipo else "Games"
    if not pezzi:
        return f"All your {tipo.lower() + ' ' if tipo else ''}games."
    return f"{testa} where " + (pezzi[0] if len(pezzi) == 1 else "; ".join(pezzi[:-1]) + "; and " + pezzi[-1]) + "."


def etichetta(k, v):
    if k == "wr_rif":
        return etichetta_wr(v)
    if k == "mano_req":
        return " and ".join(testo_mano(q) for q in (v or []))
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


_STORIE = {}


def storia_17lands(set_):
    """La storia del Premier di un set dai dati pubblici di 17Lands (Motore/limited_17lands.py, Espansioni/<SET>/Premier/storia_17lands.json), o None."""
    if set_ not in _STORIE:
        try:
            with open(os.path.join(percorsi.ROOT, "Espansioni", set_, "Premier", "storia_17lands.json"), encoding="utf-8") as f:
                _STORIE[set_] = json.load(f)
        except (OSError, ValueError):
            _STORIE[set_] = None
    return _STORIE[set_]


def set_di(x):
    m = re.search(r"_([A-Z0-9]{3})_", x.get("evento") or "")
    return m.group(1) if m else None


def coppia_wubrg(colori):
    return "".join(c for c in "WUBRG" if c in (colori or ""))


def p_contro(va, na, p0):
    """Il test z di una proporzione contro un valore noto (la popolazione di 17Lands, centinaia di migliaia di partite): la p a due code. None sotto 5."""
    if na < 5 or p0 is None or p0 <= 0 or p0 >= 1:
        return None
    return math.erfc(abs(va / na - p0) / math.sqrt(p0 * (1 - p0) / na) / math.sqrt(2))


def confronta_17lands(a):
    """C12 (13 nov 2026, Autore: «Tutti e due»: 17Lands per il limited adesso, il costruito coi log condivisi): le tue partite di limited A contro chi usa
    17Lands, nel Premier Draft degli stessi set e degli stessi colori (dati pubblici, CC BY 4.0). Ogni misura di 17Lands e' la media delle loro coppie di
    colori pesata con le tue partite in ognuna (stesso set, stessi colori): cosi' la differenza non viene dai colori che giochi. Le partite senza i dati di
    17Lands del loro set o dei loro colori restano fuori. -> dict(a=conti, b=dict(n, vinte, perse), righe come confronta, fuori, set)."""
    celle, dentro = collections.Counter(), []
    for x in a:
        s_, cp = set_di(x), coppia_wubrg(x.get("miei_colori"))
        st = storia_17lands(s_) if s_ else None
        if st and cp in (st.get("coppie") or {}):
            celle[(s_, cp)] += 1
            dentro.append(x)
    righe_ = []

    def media_pesata(f):
        num = den = 0.0
        for (s_, cp), w in celle.items():
            v = f(storia_17lands(s_)["coppie"][cp])
            if v is not None:
                num += w * v
                den += w
        return num / den if den else None

    def frac(nw):
        return nw[1] / nw[0] if nw and nw[0] else None
    pop_n = sum(storia_17lands(s_)["coppie"][cp]["n"] for s_, cp in celle)

    def prop(k, nome, sa, bene, p0):
        va, na = sum(1 for x in sa if bene(x)), len(sa)
        pa = va / na if na else None
        d = round(100 * (pa - p0), 1) if pa is not None and p0 is not None else None
        righe_.append(dict(k=k, nome=nome, a=None if pa is None else round(100 * pa, 1), b=None if p0 is None else round(100 * p0, 1), na=na, nb=pop_n,
                           ic_a=wilson(va, na), ic_b=None, delta=d, p=p_contro(va, na, p0), servono=servono(pa, p0) if d is not None else None, unita="%"))

    def media(k, nome, sa, m0):
        xa = [x.get("turno") for x in sa]
        ma = _media(xa)
        righe_.append(dict(k=k, nome=nome, a=ma, b=None if m0 is None else round(m0, 1), na=sum(1 for v in xa if v is not None), nb=pop_n, ic_a=None, ic_b=None,
                           delta=round(ma - m0, 1) if ma is not None and m0 is not None else None, p=None, servono=None, unita="T"))
    vinta = lambda x: x["vinta"]
    prop("wr", "Win rate", dentro, vinta, media_pesata(lambda c: c["w"] / c["n"] if c["n"] else None))
    prop("play", "Win rate on the play", [x for x in dentro if x.get("partenza") == "Play"], vinta, media_pesata(lambda c: frac(c.get("play"))))
    prop("draw", "Win rate on the draw", [x for x in dentro if x.get("partenza") == "Draw"], vinta, media_pesata(lambda c: frac(c.get("draw"))))
    prop("mull", "Mulligan rate", dentro, lambda x: x["mulligan"],
         media_pesata(lambda c: 1 - c["mull"]["0"][0] / c["n"] if c.get("mull") and c["n"] else None))
    prop("bravi", "Win rate · 17Lands top players (60%+)", dentro, vinta, media_pesata(lambda c: frac(c.get("bravi"))))
    media("turni_v", "Length of the wins", [x for x in dentro if x["vinta"]], media_pesata(lambda c: c.get("turni_vinte")))
    media("turni_p", "Length of the losses", [x for x in dentro if not x["vinta"]], media_pesata(lambda c: c.get("turni_perse")))
    wr0 = righe_[0]["b"]
    b_n = pop_n
    return dict(a=conti(dentro), b=dict(n=b_n, vinte=round(b_n * (wr0 or 0) / 100), perse=b_n - round(b_n * (wr0 or 0) / 100)), righe=righe_,
                fuori=len(a) - len(dentro), set=sorted({s_ for s_, _c in celle}))


# «EV vs expected» (18 nov 2026, Autore: «deve esprimersi sul grafico come games o win rate ... dobbiamo avere un grafico che ci parla delle giocate EV»):
# per ogni partita i punti di probabilita' di vincere che i suoi turni hanno generato sopra o sotto l'atteso (ev_partita.scarti); cumulativa e' la somma
METRICHE = (("wr", "Win rate"), ("ev", "EV vs expected"), ("n", "Games"), ("turni", "Avg turns"), ("mull", "Mulligan rate"))
FINESTRE = (("cum", "Cumulative"), ("10", "Last 10 games"), ("20", "Last 20 games"), ("50", "Last 50 games"))


def serie(r, metrica="wr", asse="games", finestra="20", posto=None, base=None, ev_di="all"):
    """Una linea: [(x, y)]. asse «games»: x = 1..n (o la posizione della partita fra tutte, posto: {id della partita: posizione}, cosi' le linee divise stanno
    sull'asse di tutte); «date»: x = il giorno (ordinale). finestra: «cum» cumulativa, o le ultime N partite (le partite: per giorno).
    metrica «ev»: lo scarto della partita dall'EV atteso, con l'atteso dalle partite base (di solito tutte quelle del tipo); cumulativa e' la somma che sale,
    con una finestra la media delle ultime N."""
    r = sorted(r, key=lambda x: x["quando"])
    if not r:
        return []
    px = (lambda i, x: posto.get(x.get("partita") or id(x), i + 1)) if posto else (lambda i, x: i + 1)
    if metrica == "n":      # le partite: quante per giorno (o il conto che sale, per partite)
        if asse == "games":
            return [(px(i, x), i + 1) for i, x in enumerate(r)]
        per = collections.Counter(x["quando"].date().toordinal() for x in r)
        return sorted(per.items())
    if metrica == "ev":
        import ev_partita as EV_
        sc_ = EV_.scarti(base if base is not None else r)
        # ev_di: di quali turni e fasi (ev_partita.EV_DI); una partita che non ha quella fase conta zero, una senza il conto non conta
        val = lambda x: (None if x.get("partita") not in sc_ else sc_[x["partita"]]["scarto"] if ev_di == "all"
                         else sc_[x["partita"]]["per"].get(ev_di, 0.0))
    else:
        val = {"wr": lambda x: 100.0 if x["vinta"] else 0.0, "turni": lambda x: x.get("turno"), "mull": lambda x: 100.0 if x["mulligan"] else 0.0}[metrica]
    N = None if finestra == "cum" else int(finestra)
    somma = metrica == "ev" and N is None
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
        yy = round(tot if somma else tot / cnt, 2)
        if asse == "date" and out and out[-1][0] == xx:
            out[-1] = (xx, yy)
        else:
            out.append((xx, yy))
    return out


def linee(r, metrica, asse, finestra, dividi=None, quante=5, extra=None, base=None, ev_di="all"):
    """Le linee del grafico: [(nome, punti)]. Con dividi una per valore (i piu' giocati, al massimo quante), piu' All. extra = (nome, partite): una linea in
    piu' sulle partite di una decisione di Decisions, sull'asse di tutte (13 nov 2026, Autore: «li dobbiamo vedere anche sul grafico aggiungendo una linea
    sul grafico vs quella totale ... tipo holdem manager»)."""
    posto = {x.get("partita") or id(x): i + 1 for i, x in enumerate(sorted(r, key=lambda x: x["quando"]))}
    out = [("All", serie(r, metrica, asse, finestra, base=base, ev_di=ev_di))]
    for nome_, ids_ in ([extra] if extra and isinstance(extra[0], str) else extra or []):
        out.append((nome_, serie([x for x in r if x.get("partita") in ids_], metrica, asse, finestra, posto=posto, base=base, ev_di=ev_di)))
    if dividi:
        for v, _n in sorted(valori(r, dividi), key=lambda t: -t[1])[:quante]:
            out.append((etichetta(dividi, v), serie([x for x in r if v in valori_di(dividi, x)], metrica, asse, finestra, posto=posto, base=base, ev_di=ev_di)))
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


def report(r, per, ordina="n", minimo=15, ev=None):
    """Il report raggruppato per la variabile per: una riga per valore coi conti e lo scarto dal win rate di tutte (delta). ordina: una chiave dei conti
    («n», «wr», «delta», «turni», ...) o «nome». minimo: sotto, la riga e' un indizio (poche)."""
    tutti = conti(r)
    out = []
    for v, _n in valori(r, per, massimo=200):
        c = conti([x for x in r if v in valori_di(per, x)])
        c.update(valore=v, nome=etichetta(per, v), delta=None if c["wr"] is None or tutti["wr"] is None else round(c["wr"] - tutti["wr"], 1),
                 poche=c["n"] < minimo)
        if ev is not None:      # l'EV medio a partita contro il solito (18 nov 2026, la scheda Breakdown)
            vv = [ev[x["partita"]] for x in r if v in valori_di(per, x) and x.get("partita") in ev]
            c["ev"] = round(sum(vv) / len(vv), 1) if vv else None
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
FUORI_SPOT = {"fine", "s_vita_io", "s_vita_lui", "leak_l7", "leak_l9", "versione", "p_max", "p_min", "forma", "svolta"}      # la P della partita: spiega il risultato      # versione: una per mazzo, gli Spots sarebbero rumore; leak_l7 e' sempre una sconfitta (una concessione): spiegherebbe il risultato


# gli spot in EV guardano solo quello che si sa prima o all'inizio della partita (18 nov 2026: con l'EV della partita in testa uscivano situazioni che
# raccontano come e' andata, «hai difeso piu' che attaccato», «hai perso 3+ creature», «durata 6-8 turni»: spiegano l'EV, non dicono dove intervenire)
SPOT_EV = ("mio", "suo", "colori", "vs", "partenza", "mull", "terre", "rango", "fascia", "sessione", "miei_colori", "economiche", "crea_mano",
           "giorno", "pausa", "crea_in_mano", "suo_mull", "ist_mano", "str_mano", "art_mano", "inc_mano", "pw_mano", "dopo", "serie_prima",
           "t_io1", "t_io2", "t_io3", "t_lui1", "t_lui2", "t_lui3", "sit:io_terra", "sit:lui_terra", "sit:io_curva", "sit:io_crea2", "sit:lui_crea2")


def spot(r, minimo=15, quanti=8, coppie=True, gia=None, ev=None):
    """-> (meglio, peggio): [dict(condizioni=[(chiave, valore)], nome, n, vinte, perse, wr, ic, delta, forte)]. gia: i filtri gia' messi (non si ripropongono).
    ev (18 nov 2026, Autore: «e spot? dovremmo ripensarle?», poi «Si', tutte e tre»): {partita: EV della partita contro il solito}; con ev la misura e'
    l'EV medio a partita della condizione contro le partite fuori da lei (delta in punti di probabilita' di vincere, test di Welch, la stessa correzione per
    le prove multiple), non piu' il win rate; ogni spot porta anche «ev» (la sua media) e «ev_tutte». Le partite senza EV non entrano."""
    gia = {k for k, v in (gia or {}).items() if v is not None}
    if ev is not None:
        r = [x for x in r if x.get("partita") in ev]
    base = conti(r)
    if not base["n"] or base["wr"] is None:
        return [], []
    insiemi = {}
    for k in [k for k, _n, _f in VARIABILI] + ["vs"] + [k for k, _n, _f in EXTRA] + ["sit:" + s for s, _n in SIT]:
        if k in gia or k == "data" or k in FUORI_SPOT or (ev is not None and k not in SPOT_EV):
            continue
        per = collections.defaultdict(set)
        for i, x in enumerate(r):
            for v in set(valori_di(k, x)):
                per[v].add(i)
        for v, s in per.items():
            if len(s) >= minimo and len(s) < len(r):
                insiemi[((k, v),)] = frozenset(s)
    if coppie:
        uno = [(c[0], s) for c, s in insiemi.items() if c[0][0] in COPPIE or (ev is not None and c[0][0].startswith("t_"))]
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
    if ev is not None:          # l'EV: ogni condizione contro le partite fuori da lei
        tutti_ev = [ev[x["partita"]] for x in r]
        m_tutte = sum(tutti_ev) / len(tutti_ev) if tutti_ev else 0.0
        for (cond, s_), x in zip(insiemi.items(), out):
            dentro = [ev[r[i]["partita"]] for i in s_]
            fuori = [ev[r[i]["partita"]] for i in range(len(r)) if i not in s_]
            m_ = sum(dentro) / len(dentro)
            v_ = sum((a_ - m_) ** 2 for a_ in dentro) / (len(dentro) - 1) if len(dentro) > 1 else 0.0
            se_ = math.sqrt(v_ / len(dentro)) or 1e-9
            x.update(ev=round(m_, 2), ev_tutte=round(m_tutte, 2), delta=round(m_ - m_tutte, 2), p=p_medie(dentro, fuori),
                     su=(m_ - m_tutte) / se_, giu=(m_tutte - m_) / se_)
    for x in out:
        if ev is not None:
            continue
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


def matrice2(r, kr, kc, solo_meta=False, righe_max=10, colonne_max=10, ev=None):
    """La matrice di due variabili qualsiasi (18 nov 2026, Autore: «possiamo ridisegnare in maniera piu' intuitiva report e match up in un unica
    scheda?»): kr in riga, kc in colonna, i valori piu' frequenti. solo_meta: con l'avversario («suo») in riga o in colonna, solo gli archetipi del meta.
    -> (righe, colonne, celle {(vr, vc): (n, vinte, wr, ev)}, per riga {vr: (n, wr, ev)}, per colonna {vc: (n, wr, ev)}); ev = EV medio a partita o None."""
    if solo_meta and "suo" in (kr, kc):
        r = [x for x in r if x.get("suo") and del_meta(x["suo"])]
    righe_ = [v for v, _n in valori(r, kr, massimo=righe_max)]
    colonne = [v for v, _n in valori([x for x in r if any(v in valori_di(kr, x) for v in righe_)], kc, massimo=colonne_max)]

    def conto(xs):
        if not xs:
            return None
        vt = sum(1 for x in xs if x["vinta"])
        vv = [ev[x["partita"]] for x in xs if ev is not None and x.get("partita") in ev]
        return len(xs), vt, round(100 * vt / len(xs), 1), (round(sum(vv) / len(vv), 1) if vv else None)
    celle, per_r, per_c = {}, {}, {}
    for vr in righe_:
        rr = [x for x in r if vr in valori_di(kr, x)]
        t_ = conto(rr)
        per_r[vr] = (t_[0], t_[2], t_[3])
        for vc in colonne:
            z = conto([x for x in rr if vc in valori_di(kc, x)])
            if z:
                celle[(vr, vc)] = z
    for vc in colonne:
        t_ = conto([x for x in r if vc in valori_di(kc, x) and any(v in valori_di(kr, x) for v in righe_)])
        per_c[vc] = (t_[0], t_[2], t_[3])
    return righe_, colonne, celle, per_r, per_c


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
        if isinstance(d, list):     # una riga nata dopo l'ultima scelta (RIGHE_NUOVE) si vede finche' non la togli («-chiave» nel file)
            return [k for k, _t in RIGHE_CARTE if k in d or (k in RIGHE_NUOVE and f"-{k}" not in d)]
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


RIGHE_NUOVE = ("ev_carte", "ev_giocate", "ev_sue", "win_cond", "sue_quando")        # le righe del lettore di EV (18 nov 2026): accese anche per chi aveva gia' scelto le sue


def salva_righe_carte(chiavi):
    _scrivi_in(CARTE_SCELTE, [k for k, _t in RIGHE_CARTE if k in chiavi] + [f"-{k}" for k in RIGHE_NUOVE if k not in chiavi])


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


def segna_vivo(partita, turno, quando=None):
    """R13 (13 nov 2026, come PokerTracker): segna lo spot mentre giochi, dal pulsante «★ MARK» accanto a DECK HUD: la partita (matchId) e il turno di Arena
    di adesso. Il passo del replayer si trova quando lo apri (il primo momento di quel turno); la partita prende nome ed esito quando e' nei log.
    Lo stesso turno della stessa partita si segna una volta. -> True se segnato ora."""
    import datetime as _dt
    d = segnalibri()
    if any(s.get("partita") == partita and s.get("vivo") and s.get("t") == turno for s in d):
        return False
    d.insert(0, dict(partita=partita, quando=(quando or _dt.datetime.now()).isoformat(timespec="minutes"), tipo=None, mio="", suo=None, vinta=None,
                     modo="momenti", i=None, passo=f"turn {(turno + 1) // 2} · marked live", t=turno, vivo=True))
    _scrivi_in(SEGNALIBRI, d[:200])
    return True


def note():
    try:
        with open(NOTE, encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def nota_partita(partita):
    """R3: la nota scritta su una partita ("" se non c'e')."""
    return note().get(partita or "", "")


def salva_nota_partita(partita, testo):
    d = note()
    testo = (testo or "").strip()
    if testo:
        d[partita] = testo
    else:
        d.pop(partita, None)
    _scrivi_in(NOTE, d)
    return testo


def nota_segnalibro(partita, modo, i, testo=None):
    """R3: la nota di uno spot segnato (testo None la legge, "" la toglie). None se lo spot non e' segnato."""
    d = segnalibri()
    s_ = next((s for s in d if s.get("partita") == partita and s.get("modo") == modo and s.get("i") == i), None)
    if s_ is None:
        return None
    if testo is None:
        return s_.get("nota", "")
    if testo.strip():
        s_["nota"] = testo.strip()
    else:
        s_.pop("nota", None)
    _scrivi_in(SEGNALIBRI, d)
    return s_.get("nota", "")


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
    # gli spot in EV e la matrice di Breakdown (18 nov 2026): UW guadagna 10 punti a partita, Red ne perde 10
    for i_, x_ in enumerate(righe_):
        x_.setdefault("partita", f"p{i_}")
    ev_ = {x_["partita"]: (10.0 if x_["mio"] == "UW" else -10.0) for x_ in righe_}
    mg_, pg_ = spot(righe_, minimo=10, quanti=40, ev=ev_)
    casi.append(("gli spot in EV: «My deck: UW» dove guadagni (+10 a partita), «Red» dove perdi; negativa: niente variabili che raccontano la partita (la durata)",
                 any(z["condizioni"] == [("mio", "UW")] and z["ev"] == 10.0 for z in mg_) and any(z["condizioni"] == [("mio", "Red")] for z in pg_)
                 and not any(k_ not in SPOT_EV for z in mg_ + pg_ for k_, _v in z["condizioni"])))
    rg_, cl_, ce_, pr_, _pc = matrice2(righe_, "mio", "partenza", ev=ev_)
    casi.append(("Breakdown, mazzo per partenza: UW sempre on the play (20 partite, EV +10), Red on the draw; negativa: nessuna cella UW on the draw",
                 ce_.get(("UW", "Play"), (0,))[0] == 20 and ce_[("UW", "Play")][3] == 10.0 and ("Red", "Draw") in ce_ and ("UW", "Draw") not in ce_
                 and pr_["UW"][2] == 10.0))
    # la mano riga per riga (18 nov 2026): quante · cosa · carta · valore di mana, tutte le righe nella stessa mano
    mano_ = {"Plains": 3, "Llanowar Elves": 1, "Shock": 2, "Opt": 1}
    casi.append(("la mano: 3 terre esatte, almeno una creatura da 2 o meno, 2 rimozioni, una pescata, Shock preciso", mano_soddisfa(mano_, ["=3|Land||", "1+|Creature||-2", "=2|Removal||", "1+|Card draw||", "2+|Any card|Shock|"]) is True))
    casi.append(("negative: 4 terre no, una carta da 6 no, un valore di mana non conta le terre, nessuna pescata no, la mano ignota None", mano_soddisfa(mano_, ["4+|Land||"]) is False and mano_soddisfa(mano_, ["1+|Any card||6"]) is False and mano_soddisfa(mano_, ["=0|Any card||0"]) is True and mano_soddisfa(mano_, ["0|Card draw||"]) is False and mano_soddisfa({}, ["1+|Land||"]) is None))
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
        # le abilita' attivate (mana_aperto VERSIONE 15): tu (posto 1) rompi la Reliquia nel draw step del suo turno 4 e due volte la Fetch nel tuo turno;
        # lui attiva la Fetch nel suo Main 1
        _NOMI_GRP.update({909: "Relic", 910: "Fetch"})
        _MANA["m13"] = dict(azioni=[], attivate=[[4, 1, 909, "Phase_Beginning", "Step_Draw", 2], [3, 1, 910, "Phase_Main1", "", 1],
                                                 [5, 1, 910, "Phase_Main1", "", 1], [4, 2, 910, "Phase_Main1", "", 2]])
        a13 = attivate_partita("m13", 1)
        x13 = dict(abil=a13)
        casi.append(("le abilita' attivate: la Reliquia nel draw step del suo turno, la Fetch nel tuo Main 1 una voce sola; le sue a parte, dal tuo posto",
                     "Relic · Draw step · their turn" in a13["io"] and "Relic · Their turn" in a13["io"] and a13["io"].count("Fetch · Main 1 · your turn") == 1
                     and a13["lui"] == ["Fetch · Any time", "Fetch · Main 1 · their turn", "Fetch · Their turn"]
                     and passa(x13, {"ab_io": ["Relic · Draw step · their turn", "Fetch · Any time"]})))
        casi.append(("negativa: la Reliquia nel suo upkeep o nel tuo turno non passa, la sua Fetch non e' tua, una partita senza i dati non passa",
                     not passa(x13, {"ab_io": ["Relic · Upkeep · their turn"]}) and not passa(x13, {"ab_io": ["Relic · Your turn"]})
                     and not passa(x13, {"ab_lui": ["Relic · Any time"]}) and not passa({}, {"ab_io": ["Relic · Any time"]})
                     and attivate_partita("m4", 1) == {} and set(q.partition(" · ")[2] for q in a13["io"] + a13["lui"]) <= set(QUANDO_ATTIVATE)))
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
    # R12: il giro del primo lancio e i giri in mano prima
    az_t = [[1, 1, "pesca", 11, ""], [3, 1, "pesca", 12, ""], [3, 1, "magia", 10, "C"], [5, 1, "magia", 12, "C"], [5, 1, "magia", 10, "C"],
            [6, 2, "magia", 13, "C"], [7, 1, "magia", 14, "C"]]
    nomi_t = {10: "Shock", 11: "Owl", 12: "Goblin", 13: "Bolt", 14: "Dragon"}
    tl = tempi_lancio(az_t, 1, {"Shock"}, bool, nomi_t.get)
    casi.append(("R12: Shock dalla mano tenuta lanciato al giro 2 (1 giro in mano), Goblin pescato al giro 2 e lanciato al 3 (1); il secondo Shock non conta",
                 tl.get("Shock") == [2, 1] and tl.get("Goblin") == [3, 1]))
    casi.append(("negativa: le magie dell'avversario non entrano, e una carta arrivata senza che si sappia come ha solo il giro (Dragon)",
                 "Bolt" not in tl and tl.get("Dragon") == [4, None]))
    rl_ = riga_carte([dict(vinta=True, mie_lanciate=["Shock"], tempi={"Shock": [2, 1]}), dict(vinta=False, mie_lanciate=["Shock"], tempi={"Shock": [4, None]})],
                     "lanciate")
    casi.append(("R12 nella riga: Shock al giro 3,0 di media, 1,0 in mano (la partita senza arrivo non conta nei giri in mano)",
                 rl_[0]["turno_lancio"] == 3.0 and rl_[0]["in_mano_giri"] == 1.0))
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
    # R1 + R6 · le due liste del replayer (13 nov 2026)
    deck_ = {"Opt": 4, "Island": 20, "Shock": 2}
    foto_ = dict(mano=["Opt", "Island"], mio=[("Island", True, False), ("Island", False, False), ("Shark", False, True)], cim=(["Opt"], ["Bolt"]),
                 esi=([], []), suo=[("Mountain", True, False), ("Goblin", False, False), ("Goblin Token", False, True)])
    lm = lista_mia(deck_, foto_, dict(tipo="spell", mio=True, ab=False, nome="Shock"))
    rig = {n: (rim, q) for n, rim, q, _t in lm["righe"]}
    casi.append(("R6: rimaste = copie meno mano, campo (senza pedine), cimitero e la tua magia in pila; il grimorio e' il resto",
                 rig["Opt"] == (2, 4) and rig["Island"] == (17, 20) and rig["Shock"] == (1, 2) and lm["grimorio"] == 26 - 6
                 and [n for n, _r, _q, t in lm["righe"] if t] == ["Island"] and lm["righe"][-1][0] == "Island"))
    casi.append(("negativa R6: una carta vista piu' volte di quante ne hai non va sotto zero; senza lista niente", lista_mia({"Opt": 1}, dict(mano=["Opt", "Opt"]))
                 ["righe"][0][1] == 0 and lista_mia(None, foto_) is None))
    passi_ = [("a", dict(suo=[("Goblin", False, False)], cim=([], []), esi=([], [])), 1, None),
              ("b", dict(suo=[("Goblin", False, False), ("Goblin", False, False)], cim=([], ["Bolt"]), esi=([], [])), 2, None),
              ("c", dict(suo=[], cim=([], ["Goblin", "Bolt"]), esi=([], [])), 3, dict(tipo="spell", mio=False, ab=False, nome="Lava Spike"))]
    ls = {n: q for n, q, _t in lista_sua(passi_, 2)}
    casi.append(("R1: le sue carte viste fino al momento: il massimo di copie insieme (2 Goblin, 1 Bolt), la magia in pila; le pedine no",
                 ls == {"Goblin": 2, "Bolt": 1, "Lava Spike": 1}))
    casi.append(("negativa R1: al primo momento vede solo quello che c'era allora; Copy as list una per riga",
                 {n: q for n, q, _t in lista_sua(passi_, 0)} == {"Goblin": 1} and testo_lista([("Goblin", 2, False), ("Mountain", 1, True)]) == "2 Goblin\n1 Mountain"))
    casi.append(("i log veri: righe con le variabili (se ci sono partite)", not vere or all(k in vere[0] for k in ("tipo", "partenza", "terre", "sessione", "fascia"))))
    # C12: contro 17Lands, pesato sui tuoi colori
    vecchie = dict(_STORIE)
    _STORIE.clear()
    _STORIE["XXX"] = dict(coppie=dict(WU=dict(n=1000, w=600, play=[500, 320], draw=[500, 280], mull={"0": [900, 0]}, bravi=[100, 70], turni_vinte=9.0,
                                              turni_perse=10.0),
                                      BR=dict(n=1000, w=400, play=[500, 220], draw=[500, 180], mull={"0": [800, 0]}, bravi=[100, 50], turni_vinte=8.0,
                                              turni_perse=9.0)))
    try:
        ra = [dict(evento="QuickDraft_XXX_1", miei_colori="UW", vinta=i < 6, partenza="Play", mulligan=0, turno=9, quando=datetime.datetime(2026, 11, 1))
              for i in range(10)] + [dict(evento="QuickDraft_YYY_1", miei_colori="UW", vinta=True, partenza="Play", mulligan=0, turno=9,
                                          quando=datetime.datetime(2026, 11, 1))]
        c12 = confronta_17lands(ra)
        w12 = c12["righe"][0]
        casi.append(("C12: 10 partite WU contro 17Lands WU (60%): A 60%, B 60%, differenza 0; i colori si leggono in ordine WUBRG (UW = WU)",
                     w12["a"] == 60.0 and w12["b"] == 60.0 and w12["delta"] == 0.0 and c12["a"]["n"] == 10))
        casi.append(("negativa C12: la partita di un set senza i dati di 17Lands resta fuori; BR non entra nella media", c12["fuori"] == 1
                     and next(x for x in c12["righe"] if x["k"] == "mull")["b"] == 10.0))
    finally:
        _STORIE.clear()
        _STORIE.update(vecchie)
    # la mano da 7 contro la tabella del mulligan (14 nov 2026)
    casi.append(("mull_tabella: tenuta a 3 terre = la tabella tiene; rimandata a 4 terre = la tabella teneva; tenuta a 6 = la tabella fa mulligan",
                 mull_tabella(dict(mulligan=0, terre=3)) == ORDINE_MULL_TAB[0] and mull_tabella(dict(mulligan=1, scartate=[4], terre=3)) == ORDINE_MULL_TAB[3]
                 and mull_tabella(dict(mulligan=0, terre=6)) == ORDINE_MULL_TAB[2]))
    casi.append(("Constructed: la regola a 60 carte; 1 terra tenuta e' un mulligan, 3 terre ideale, 5 terre dipende; negativa: nel Limited None",
                 mull_60(dict(tipo="Constructed", mulligan=0, terre=1)) == ORDINE_MULL_60[2] and mull_60(dict(tipo="Constructed", mulligan=0, terre=3)) == ORDINE_MULL_60[0]
                 and mull_60(dict(tipo="Constructed", mulligan=0, terre=5)) == ORDINE_MULL_60[1] and mull_60(dict(tipo="Limited", mulligan=0, terre=3)) is None
                 and LEGGI["mull_tabella"](dict(tipo="Constructed", mulligan=0, terre=3)) is None))
    casi.append(("negativa: rimandata a 0 terre non e' un errore (la tabella fa mulligan); 1 terra e' pari; senza dati None",
                 mull_tabella(dict(mulligan=1, scartate=[0])) == ORDINE_MULL_TAB[4] and mull_tabella(dict(mulligan=0, terre=1)) == ORDINE_MULL_TAB[1]
                 and mull_tabella(dict(mulligan=0)) is None))
    # i turni estesi (14 nov 2026): dal turno 11 e «qualunque turno»; un turno che abbia tutte le voci
    pt = turni_estesi({"io1": ["Creature"], "io11": ["Instant", "Instant"], "aio2": ["No attack"]})
    xt = dict(per_turno=pt)
    casi.append(("turni estesi: il turno 11 va in «11+» e in «any», i turni 1-10 restano anche da soli", pt.get("io1") == ["Creature"] and "io11" not in pt
                 and pt["ioL"] == [["Instant", "Instant"]] and pt["ioA"] == [["Creature"], ["Instant", "Instant"]]))
    casi.append(("any turn: due istantanei nello stesso turno passano; negativa: una creatura e un istantaneo non stanno nello stesso turno",
                 passa(xt, {"t_ioA": ["Instant", "Instant"]}) and not passa(xt, {"t_ioA": ["Creature", "Instant"]})))
    # il Board (16 nov 2026): il campo all'inizio di ogni turno dalla foto di fine del turno prima. Tu (posto 1) cominci; alla fine del tuo turno 3 di Arena
    # (il tuo 2) hai un 2/2 e tre terre, lui niente in campo, due terre stappate; all'inizio del suo turno 4 di Arena (il suo 2) le sue terre sono stappate
    salva_nomi = dict(_NOMI_GRP)
    try:
        _NOMI_GRP.update({880: "Plains", 881: "Grizzly Bears", 882: "Opt", 883: "Shock"})
        foto3 = dict(c=[[[880, True, 0, None, None, 1], [880, True, 0, None, None, 2], [880, False, 0, None, None, 3], [881, False, 0, 2, 2, 4]],
                        [[880, False, 0, None, None, 5], [880, False, 0, None, None, 6]]], n=[4, 6], v=[20, 17], g=[[882], []], e=[[], []])
        dt = dict(momenti=[["fine", 3, 1, foto3]], fasi=[[1, 1, 881, "Phase_Main1"], [5, 1, 882, "Phase_Main1"], [5, 1, 881, "Phase_Main2"],
                                                         [4, 2, 883, "Phase_Combat"]])
        dit = lambda t: "io" if t % 2 == 1 else "lui"
        cb = campo_inizio_turno(dt, 1, dit, 5)
        casi.append(("Board: all'inizio del suo turno 2 (il 4 di Arena) tu hai 1 creatura, 2 di forza, 3 terre (1 stappata), lui 0 creature e 2 terre "
                     "stappate; sei avanti in creature e terre", cb.get("bciox2") == ["1 creature"][0] and cb.get("bfiox2") == "1-2 power"
                     and cb.get("btiox2") == "3 lands" and cb.get("bsiox2") == "1 untapped" and cb.get("bclui2") == "0 creatures"
                     and cb.get("bslui2") == "2 untapped" and cb.get("bcviox2") == "You're ahead" and cb.get("btviox2") == "You're ahead"
                     and cb.get("bgiox2") == "1-2 cards" and cb.get("bvlui2") == "16-20 life"))
        casi.append(("Board: il turno 1 parte dal campo vuoto (0 creature, pari); negativa: senza la foto del turno prima (il 3 di Arena da quella del 2) "
                     "il campo non si inventa", cb.get("bcio1") == "0 creatures" and cb.get("bcvio1") == "Even" and "bcio2" not in cb and "bmio1" not in cb))
        ru = ruoli_turno(dt, 1, dit, 5)
        casi.append(("ruoli: al tuo turno 3 una pescata prima del combattimento e una creatura dopo; il suo Shock nel combattimento e' una rimozione; "
                     "negativa: il tuo turno 2 (il 4 di Arena) senza magie tue resta vuoto",
                     ru["rio3"] == ["Card draw", "Card draw · before combat", "Creature", "Creature · after combat"]
                     and ru["rlui2"] == ["Removal", "Removal · in combat"] and ru["riox2"] == []))
        xb = dict(per_turno=turni_estesi({**{k: [v] for k, v in cb.items()}, **{k: (v or ["Nothing"]) for k, v in ru.items()}}))
        casi.append(("Board nei filtri: all'inizio del suo turno 2 tu 1 creatura e lui 0, e al tuo turno 3 «Card draw · before combat» passa anche come "
                     "«Card draw»; negative: «Card draw · after combat», lui con 1 creatura",
                     passa(xb, {"t_bciox2": ["1 creature"], "t_bclui2": ["0 creatures"], "t_rio3": ["Card draw · before combat"]})
                     and passa(xb, {"t_rio3": ["Card draw"]}) and not passa(xb, {"t_rio3": ["Card draw · after combat"]})
                     and not passa(xb, {"t_bclui2": ["1 creature"]})))
        # le condizioni nello stesso turno (16 nov 2026, Autore: «come spieghiamo che voglio che quella situazione sia letta ... in qualunque turno io e
        # oppo vi troviamo ad avere io una creatura e lui no nello stesso turno?»): al tuo turno 2 tu 1 creatura e lui 2, al 3 tu 0 e lui 0, al 4 tu 1 e lui 0
        xs = dict(per_turno=turni_estesi({"bcio2": ["1 creature"], "bcluix2": ["2 creatures"], "bcio3": ["0 creatures"], "bcluix3": ["0 creatures"],
                                          "bcio4": ["1 creature"], "bcluix4": ["0 creatures"]}))
        fs = {"t_bcioA": ["1 creature"], "t_bcluixA": ["0 creatures"]}
        casi.append(("stesso turno: «any turn» tu 1 creatura e lui 0 vale solo al tuo turno 4; negativa: senza il turno 4 ognuna e' vera in un turno diverso "
                     "(2 e 3) e la partita non passa", passa(xs, fs) and turni_comuni(xs, fs, list(fs)) == {4}
                     and not passa(dict(per_turno=turni_estesi({k: v for k, v in {"bcio2": ["1 creature"], "bcluix2": ["2 creatures"], "bcio3": ["0 creatures"],
                                                                                   "bcluix3": ["0 creatures"]}.items()})), fs)))
        # i filtri da un momento del replay (16 nov 2026): il tuo turno 3 di Arena 5 (cominci tu)
        xm = dict(partenza="Play", mull="0", terre=3, inizia=True, per_turno=turni_estesi({
            "bcio3": ["1 creature"], "bcluix3": ["0 creatures"], "btio3": ["2 lands"], "btluix3": ["3 lands"], "bkio3": ["0 artifacts"],
            "byluix3": ["1 enchantment"], "rio3": ["Creature", "Creature · before combat"], "rluix3": ["Nothing"], "rlui2": ["Removal", "Removal · in combat"],
            "riox2": ["Nothing"], "rio2": ["Nothing"], "rluix2": ["Nothing"]}))
        fm = filtri_momento(xm, 5, tutto=True)
        fm0 = filtri_momento(xm, 5, 0)
        fm1 = filtri_momento(xm, 5, 1)
        casi.append(("filtri dal momento: l'inizio (Play, 0 mulligan, 3 terre) e il campo dei due all'inizio del tuo turno 3; un tipo a zero non entra, un "
                     "incantesimo suo si'; negativa: senza la richiesta niente giocate", fm.get("partenza") == "Play" and fm.get("mull") == "0"
                     and fm.get("terre") == "3" and fm.get("t_bcio3") == ["1 creature"] and fm.get("t_bcluix3") == ["0 creatures"]
                     and "t_bkio3" not in fm and fm.get("t_byluix3") == ["1 enchantment"] and not any(k_.startswith("t_r") for k_ in fm)))
        casi.append(("filtri dal momento: «questo turno» aggiunge le tue giocate per ruolo (senza il momento), ±1 turno anche il suo turno prima; di "
                     "partenza solo inizio, creature e terre (negativa: niente terre in mano ne' incantesimi)",
                     fm0.get("t_rio3") == ["Creature"] and "t_rlui2" not in fm0 and fm1.get("t_rlui2") == ["Removal"]
                     and "terre" not in fm0 and "t_byluix3" not in fm0 and fm0.get("t_btio3") == ["2 lands"]))
        casi.append(("filtri dal momento: la partita da cui vengono li passa tutti", passa(xm, fm1)))
        casi.append(("stesso turno: un filtro dei suoi turni non si lega a uno dei tuoi (gruppi diversi)", sorted(gruppi_turno({"t_bcioA": ["1 creature"],
                     "t_bcluiA": ["0 creatures"]})) == [("io", "A"), ("lui", "A")]))
        # il letale sul tavolo (19 nov 2026): chi tocca chiude se i danni che passano arrivano alle vite e chi difende non ha carte in mano
        salva_kw, salva_dr = dict(_KW), dict(_DRENA)
        try:
            _KW.update({9001: set(), 9002: {"flying"}, 9003: set()}); _DRENA.update({9001: 0, 9002: 0, 9003: 1})
            cre_ = lambda g, p_, tapp=0: [g, tapp, 0, p_, p_, 1]
            fl = dict(c=[[cre_(9001, 6), cre_(9002, 2), cre_(9003, 1)], [cre_(9001, 5, 1), cre_(9001, 5, 1)]], v=[4, 10], n=[1, 0])
            casi.append(("letale: 6 + 2 + 1 e il drenaggio di 1 contro 10 vite, le sue creature tappate, niente carte in mano", letale(fl, 1, True)))
            casi.append(("letale: la P diventa 99 per chi tocca", p_foto(fl, 1, True, 8) == 99.0))
            casi.append(("negativa: con una carta in mano niente letale (un trucco e' possibile)", not letale(dict(fl, n=[1, 1]), 1, True)))
            casi.append(("negativa: una sua creatura stappata blocca il 6 e non basta piu'",
                         not letale(dict(fl, c=[fl["c"][0], [cre_(9001, 5, 0), cre_(9001, 5, 1)]]), 1, True)))
            casi.append(("il volante passa: un bloccante senza volare ne' portata ferma il 6, il 2 volante e il resto no (3 contro 3 vite)",
                         letale(dict(fl, c=[fl["c"][0], [cre_(9001, 5, 0)]], v=[4, 3]), 1, True)))
            casi.append(("negativa: se tocca a lui, il letale e' suo da cercare (le mie creature non contano)", not letale(fl, 1, False)))
        finally:
            _KW.clear(); _KW.update(salva_kw); _DRENA.clear(); _DRENA.update(salva_dr)
    finally:
        _NOMI_GRP.clear()
        _NOMI_GRP.update(salva_nomi)
    # gli eventi limited del gioco (19 nov 2026): le riaperture sono lo stesso evento, il calendario da' anche quelli mai giocati; negativa: le code non cambiano
    casi.append(("evento_breve: QuickDraft_FRA_20261008 e _20261027 sono QuickDraft_FRA", evento_breve("QuickDraft_FRA_20261008") == "QuickDraft_FRA"
                 == evento_breve("QuickDraft_FRA_20261027")))
    casi.append(("negativa: le code del Constructed restano come sono", evento_breve("Traditional_Ladder") == "Traditional_Ladder" and evento_breve(None) is None))
    eg_ = [v_ for v_, _d in eventi_limited_gioco()]
    casi.append(("il catalogo dal calendario: Quick Draft FRA, Premier Draft TRK, un flashback e un evento senza nome interno", {"QuickDraft_FRA", "PremierDraft_TRK",
                 "PremierDraft_KHM"} <= set(eg_) and any(v_.startswith("cal:") for v_ in eg_) and len(eg_) == len(set(eg_))))
    # le piu' deboli per prime (19 nov 2026): dal valore piu' basso, quelle con poche partite in fondo
    rr_ = [dict(nome="A", n=60, iwd=-8.0), dict(nome="B", n=5, iwd=-36.0), dict(nome="C", n=70, iwd=12.0), dict(nome="D", n=40, iwd=-2.0, poche=True)]
    casi.append(("Weakest first: A (-8 in 60) prima di C, B (5 partite) e D (poche) in fondo",
                 [c_["nome"] for c_ in deboli_prima(rr_, "iwd", 4)] == ["A", "C", "B", "D"]))
    casi.append(("negativa: una carta pescata in 5 partite non sale in testa anche a -36", deboli_prima(rr_, "iwd", 1)[0]["nome"] != "B"))
    # la copia delle righe (21 nov 2026): la chiave cambia col record e col dato di mana_aperto; le partite finte non scrivono la copia
    p_, r_ = {"matchId": "x", "seat": 1}, {"partita": "x", "vinta": True}
    k0 = _chiave_riga(p_, r_)
    casi.append(("copia delle righe: stessa partita, stessa chiave", k0 == _chiave_riga(dict(p_), dict(r_))))
    casi.append(("negativa: un record diverso cambia la chiave", k0 != _chiave_riga(p_, dict(r_, vinta=False))))
    _MANA["x"] = {"azioni": [1]}
    casi.append(("negativa: il dato di mana_aperto cambia la chiave", k0 != _chiave_riga(p_, r_)))
    _MANA.pop("x", None)
    import tempfile
    ind_ = _SCHEDE.get("indice")
    with tempfile.TemporaryDirectory() as td_:
        fs_ = os.path.join(td_, "scheda_x.json")
        open(fs_, "w").write("{}")
        _SCHEDE["indice"] = {"x": fs_}
        k1 = _chiave_riga(p_, r_)
        os.utime(fs_, ns=(1, 10 ** 18))
        casi.append(("negativa: la scheda di Partite/ arrivata o riscritta cambia la chiave", k0 != k1 != _chiave_riga(p_, r_)))
    if ind_ is None:
        _SCHEDE.pop("indice", None)
    else:
        _SCHEDE["indice"] = ind_
    try:
        prima_ = os.stat(_f_righe()).st_mtime_ns
    except OSError:
        prima_ = None
    _CACHE.clear()
    righe([{"matchId": "finta", "seat": 1, "vinta": True, "inizio": 0}])
    try:
        dopo_ = os.stat(_f_righe()).st_mtime_ns
    except OSError:
        dopo_ = None
    _CACHE.clear()
    casi.append(("le partite finte non toccano la copia su disco", prima_ == dopo_))
    # la magia in pila conta come carta di chi l'ha lanciata (24 nov 2026, la WIN CHANCE che saltava al lancio); negativa: un'abilita' in pila no
    fp_ = dict(n=[3, 4], m=[[1, 2, 3], []], p=[[500, 1, False, 9], [600, 2, True, 10]])
    cp_ = con_pila(fp_)
    # lo spot delle situazioni dei replay (24 nov 2026): il wipe sulla sua magia, vite e terre a fine turno; negativa: un'altra fascia di valore non ha spot
    xs_ = dict(partita="sim-nessuna", seat=1, inizia=True, situa=dict(vita_t3="Behind", terre_lui2="1 short"))
    casi.append(("le situazioni dei replay hanno il loro turno (vita_t3 al tuo T3 = 5, terre_lui2 al suo T2 = 4); negativa: Ahead non e' Behind",
                 spot_situa(xs_, "vita_t3", "Behind") == [(5, "fine", None, None)] and spot_situa(xs_, "terre_lui2", "1 short") == [(4, "fine", None, None)]
                 and spot_situa(xs_, "vita_t3", "Ahead") == []))
    casi.append(("la magia in pila conta nella mano di chi la lancia (3 -> 4, la carta coi nomi); negativa: l'abilita' dell'altro no (4 resta 4)",
                 cp_["n"] == [4, 4] and cp_["m"][0] == [1, 2, 3, 500] and fp_["n"] == [3, 4] and con_pila(dict(n=[1, 1])) == dict(n=[1, 1])))
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
