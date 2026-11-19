"""Le carte che agiscono, prima parte: le fondamenta (passo 7.1 del motore di partita, 14 ott 2026).

Autore, 14 ott 2026: «aggiungi gli effetti conosciuti delle carte di FRA (per ogni effetto istruisci il motore sulla
meccanica reale da documentazione ufficiale) [...] non approssimiamo, non inventiamo, non tappiamo buchi». Prima delle
famiglie di effetti vengono i pezzi che quasi ogni carta tocca. Secondo il regolamento ufficiale (Regole/MagicCompRules.txt,
numeri letti con Motore_Opzioni/regolamento.py):
  - le abilita' (113): statiche, attivate, innescate. Un'abilita' attivata o innescata in pila e' un oggetto che non e'
    una carta (113.1c, 405.1, 602.2a, 603.3): `Abilita`. La sua fonte e' l'oggetto che l'ha generata (113.7) e una volta
    in pila esiste da sola: se la fonte se ne va l'abilita' resta e usa le ultime informazioni note della fonte (113.7a,
    608.2h). Il controllore e' chi l'ha attivata o chi controllava la fonte quando si e' innescata (113.8, 603.3a);
  - le abilita' attivate (602): si attivano con la priorita' (117.1b); si annunciano, si scelgono i bersagli e si paga
    come per una magia (602.2b, 601.2b-h); col {T} una creatura deve essere sotto chi la controlla dall'inizio del suo
    turno, salvo rapidita' (602.5a); «solo come una stregoneria» segue i tempi della stregoneria (602.5d). Chi attiva
    tiene la priorita' (117.3c). Le abilita' di fedelta' (606): nella propria fase principale a pila vuota, una sola per
    permanente per turno (606.3), il costo sono segnalini fedelta' messi o tolti (606.4), e con un costo negativo ce ne
    devono essere abbastanza (606.6);
  - gli inneschi (603): quando l'evento succede l'abilita' si innesca (603.2) e va in pila la prossima volta che un
    giocatore riceverebbe la priorita' (603.3). Piu' inneschi insieme: ognuno, in ordine APNAP, mette i suoi nell'ordine
    che vuole, poi le azioni di stato, poi gli inneschi nati nel frattempo, finche' non succede piu' niente (603.3b, 101.4).
    Un innesco col bersaglio senza bersagli legali si toglie (603.3d). «se» subito dopo la condizione si controlla
    all'innesco e alla risoluzione (603.4). All'inizio di un passo si innesca «at the beginning of» (603.2b). Le
    abilita' che si innescano lasciando il campo guardano all'indietro: contano gli oggetti e le abilita' com'erano
    subito prima dell'evento (603.6c, 603.10a). Quelle d'entrata guardano tutti i permanenti dopo l'evento, nuovi
    compresi (603.6a). Gli eventi di un'azione simultanea (le azioni di stato, 704.3; il danno da combattimento, 510.2;
    un effetto su piu' oggetti, 608.2f) si leggono insieme (`Tavolo.insieme`);
  - i bersagli (115): si scelgono lanciando o mettendo in pila (601.2c, 602.2b, 603.3d); solo permanenti, salvo che
    dica altro (115.2); «any target» e' creatura, giocatore, planeswalker o battaglia (115.4); lo stesso bersaglio non due
    volte per la stessa parola «target» (115.3); una magia o abilita' non bersaglia se stessa (115.5); l'anti-malocchio
    (hexproof) impedisce i bersagli delle magie e abilita' degli avversari (702.11b). Alla risoluzione si ricontrollano:
    se sono tutti illegali la magia o l'abilita' non si risolve (la magia va nel cimitero), altrimenti si risolve e i
    bersagli illegali non subiscono niente (608.2b, 608.3b);
  - la risoluzione (608.2): le istruzioni in ordine (608.2c), le scelte durante la risoluzione (608.2d, 603.5 «puoi»),
    le azioni su piu' oggetti insieme (608.2f), le informazioni prese una volta (608.2h); alla fine l'istantaneo o la
    stregoneria nel cimitero del proprietario, l'abilita' smette di esistere (608.2n);
  - gli effetti continui (611, 613): quelli di una magia o abilita' risolta durano quanto dicono, «until end of turn»
    fino alla pulizia, insieme alla rimozione del danno (611.2a, 514.2), e l'insieme degli oggetti si fissa quando
    cominciano (611.2c); quelli di un'abilita' statica valgono finche' la fonte e' in campo e ha l'abilita' (604.2,
    611.3a-b) e non si fissano. Si applicano a livelli (613.1): 6 abilita' date e tolte (613.1f), 7 forza e costituzione
    con i sottolivelli 7a-7d (613.4: definite, impostate, modificate coi segnalini, scambiate); nello stesso livello per
    timestamp (613.7: l'oggetto quando entra in una zona, l'effetto quando nasce) salvo le dipendenze (613.8: un effetto
    di un'abilita' statica dipende da quello che toglie le abilita' alla sua fonte, e aspetta che sia applicato);
  - i segnalini (122): +1/+1 e -1/-1 cambiano forza e costituzione nel livello 7c (122.1a, 613.4c); se un permanente li
    ha tutti e due se ne tolgono tanti quanti il numero minore (122.3, 704.5q);
  - forza, costituzione e parole chiave passano tutte da qui (`TavoloEffetti`), quindi il combattimento del passo 6, le
    azioni di stato (704.5f-g) e la debolezza da evocazione usano i valori veri.
Le carte di questa fase sono ancora finte (mazzo_effetti): le loro abilita' sono scritte nel formato del motore,
car["abilita"] e, per istantanei e stregonerie, car["bersagli"] e car["fa"]. Le carte vere di FRA ci arrivano col passo
7.2 (Motore_Partita/carte_fra.py), dal catalogo degli effetti.

I livelli 1 e 4 (dal 14 ott 2026, Puppet Crafting e Hall of Echoes): la «vista» della carta. `Oggetto.carta` restituisce le
caratteristiche dopo la copia (613.2a, 707.2: valori fissati quando la copia comincia, 707.2b) e dopo i tipi aggiunti «in
addition to its other types» (613.1d, 205.1b) quando in campo c'e' una fonte di quei livelli (`TavoloEffetti._bassi`);
senza fonti e' la carta fisica (`Oggetto.fisica`), come prima. Il 7b di un effetto partito nel 4 continua anche senza
l'abilita' (613.6); chi lascia il campo e' ricordato com'era (603.10a, `_carta_lki`). Coperti: la copia da un'abilita'
risolta su un oggetto fissato e il tipo dato da una statica su «enchanted/equipped»; il resto esce NonCoperto (le copie
da abilita' statiche 707.2c, i cambi di tipo da magie risolte, i selettori che leggono i tipi nel livello 4).

Non coperto, ed esce NonCoperto: i livelli 2, 3 e 5 (controllo, testo, colore: 613.1b-c-e), le forze definite
dalle caratteristiche (604.3, 613.4a), le abilita' non parola chiave date da un effetto (113.1a), le modali (700.2), le
aure e le magie permanente con bersaglio (303.4, 608.3b-c), le abilita' di mana dei permanenti non terra (605.1a), le
sostituzioni e le prevenzioni (614, 615), le durate diverse da «fino a fine turno» e «per sempre» (611.2b), gli inneschi
che guardano un'altra abilita' che si innesca (603.3b, seconda parte: nessuna carta finta li ha), le battaglie (310).

    py -I -X utf8 Motore_Partita/effetti.py --prova
    py -I -X utf8 Motore_Partita/effetti.py --partita [seme]
"""
import contextlib
import itertools
import numbers
import os
import re
import types
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # py -I non mette la cartella dello script nel percorso
import numpy as np
import combattimento as C
import mana as M
import pila as PL
from inizio import inizia
from mana import NonCoperto
from tavolo import PAROLE, Tavolo, controlla, costituzione, forza, parole, parole_stampate

PAROLE_7 = dict(PAROLE, hexproof="702.11", flash="702.8", prowess="702.108", ward="702.21", crew="702.122")   # crew: 14 nov 2026
TIPI_DI_CARTA = {"artifact", "battle", "conspiracy", "creature", "dungeon", "enchantment", "instant", "kindred", "land",
                 "phenomenon", "plane", "planeswalker", "scheme", "sorcery", "vanguard"}                 # 205.2a
LIVELLI = ("6", "7b", "7c", "7d", "regola")             # 613.1f, 613.4b-d; 613.11: gli effetti sulle regole del gioco
TIPI_BASE = {"Plains", "Island", "Swamp", "Mountain", "Forest"}                                      # 205.3i, 305.6
LIVELLI_BASSI = ("1", "4")                            # 613.1a copia, 613.1d tipo: si applicano prima, nella «vista» della carta
DURATE = (None, "fine_turno", "prossimo_turno")         # 611.2a: per sempre, «until end of turn», «until your next turn»
LANCIATA = "finche_lanciata"                            # 611.2a: («finche_lanciata», n): «until this card is cast from exile»


def _e_giocatore(x):
    return isinstance(x, numbers.Integral) and not isinstance(x, bool)


def scrivi(x):
    return f"G{x + 1}" if _e_giocatore(x) else repr(x)


# ====================================================================== l'abilita' in pila
class Abilita:
    """113.1c, 405.1: un'abilita' attivata o innescata in pila, un oggetto che non e' una carta (602.2a, 603.3)."""
    carta = None
    tappato = a_faccia_in_giu = False

    def __init__(self, n, fonte, k, ab, controllore, tipo, evento=None):
        self.n, self.fonte, self.k, self.ab, self.controllore, self.tipo = n, fonte, k, ab, controllore, tipo
        self.evento = evento          # l'evento che l'ha innescata (603.2)
        self.zona, self.vivo = "pila", True
        self.bersagli, self.x = [], 0
        self.reqs, self.fa = [], []   # i bersagli richiesti e le istruzioni, dopo la scelta dei modi (700.2)
        self.esito = None

    @property
    def nome(self): return f"[{self.tipo} di {self.fonte.nome}]"

    @property
    def proprietario(self): return self.controllore

    def __repr__(self): return f"{self.nome}#{self.n}"


class Innesco:
    """Un'abilita' innescata che aspetta di andare in pila (603.2, 603.3)."""

    def __init__(self, fonte, k, ab, controllore, evento):
        self.fonte, self.k, self.ab, self.controllore, self.evento = fonte, k, ab, controllore, evento
        self.esito = None             # "pila" o la regola che l'ha tolto (603.3d)
        self.abilita = None

    def __repr__(self): return f"innesco di {self.fonte.nome} ({self.ab.get('quando', {}).get('evento', 'riflesso')})"


class Continuo:
    """Un effetto continuo (611): livello (613.1), timestamp (613.7), a chi (l'insieme fissato, 611.2c, o il selettore
    di un'abilita' statica, 611.3a), cosa fa, quanto dura (611.2a)."""

    def __init__(self, ts, livello, dati, chi=None, sel=None, fonte=None, k=None, statica=False, durata=None, ctrl=None):
        self.ts, self.livello, self.dati, self.chi, self.sel = ts, livello, dati, chi, sel
        self.fonte, self.k, self.statica, self.durata, self.ctrl = fonte, k, statica, durata, ctrl

    def __repr__(self): return f"<{self.livello} ts{self.ts} {self.dati}>"


def cambia_generico(costo, delta):
    """601.2f, 118.7a: aumenta o riduce il mana generico di un costo («{2}{U}» -1 -> «{1}{U}»; ridotto a niente: «{0}»)."""
    gen = sum(int(x) for x in re.findall(r"\{(\d+)\}", costo))
    resto = re.sub(r"\{\d+\}", "", costo)
    nuovo = max(0, gen + delta)
    out = (f"{{{nuovo}}}" if nuovo else "") + resto
    return out or "{0}"


def con_tipi(tipo, tipi, sotto):
    """205.1b: la riga del tipo con i tipi e i sottotipi aggiunti, tenendo tutti quelli di prima («Artifact — Equipment»
    + creatura Construct = «Artifact Creature — Equipment Construct»)."""
    if "//" in tipo: raise NonCoperto("613.1d: il cambio di tipo di una carta con due facce non e' coperto")
    davanti, _, dietro = tipo.partition("—")
    d, s_ = davanti.split(), dietro.split()
    d += [t.capitalize() for t in tipi if t.lower() not in {w.lower() for w in d}]
    s_ += [x for x in sotto if x not in s_]
    return " ".join(d) + (" — " + " ".join(s_) if s_ else "")


def colori_di(o):
    """202.2: i colori dal costo di mana (le pedine dal loro «colori»)."""
    if "colori" in o.carta.car: return set(o.carta.car["colori"] or "")
    return set(M.colori(o.carta.car.get("costo") or ""))


def filtri_ok(r, x):
    """I filtri di un bersaglio: non_tipi («nonland»), valore di mana (202.3), colori (202.2), con una parola chiave,
    non pedina, leggendario."""
    tipi = x.carta.tipi
    if r.get("non_tipi") and set(r["non_tipi"]) & tipi: return False
    if r.get("non_sottotipi") and any(ha_sottotipo(x, s_) for s_ in r["non_sottotipi"]): return False   # «non-Aura», 702.73a
    if "mv_min" in r or "mv_max" in r:
        mv = M.valore(x.carta.car.get("costo") or "") if not x.carta.pedina else 0                # 202.3
        if mv < r.get("mv_min", -1) or mv > r.get("mv_max", 10 ** 6): return False
    if r.get("colori") and not set(r["colori"]) & colori_di(x): return False
    if r.get("con_parole") and not set(r["con_parole"]) & parole(x): return False
    if r.get("o_sottotipo") and "creature" not in tipi and not ha_sottotipo(x, r["o_sottotipo"]): return False   # «creature or Vehicle»
    if r.get("sottotipo") and not ha_sottotipo(x, r["sottotipo"]): return False                    # «target Vehicle», 205.3
    if r.get("non_base") and "Basic" in x.carta.tipo.partition("—")[0].split(): return False       # «nonbasic», 205.4a
    sc = r.get("solo_creatura")                                                                    # «... or creature with power 4 or greater»
    if sc and not (set(sc["tranne"]) & tipi):
        if "forza_min" in sc and not ("creature" in tipi and forza(x) >= sc["forza_min"]): return False
        if "forza_max" in sc and not ("creature" in tipi and forza(x) <= sc["forza_max"]): return False
    cp = r.get("con_parole_solo")                                                                  # «... or creature with flying»
    if cp and not (set(cp["tranne"]) & tipi) and not set(cp["parole"]) & parole(x): return False
    if r.get("non_pedina") and x.carta.pedina: return False
    if r.get("tappata") and not x.tappato: return False                                            # «target tapped creature» (701.26a)
    if r.get("leggendario") and "legendary" not in tipi: return False
    if r.get("non_leggendario") and "legendary" in tipi: return False
    if r.get("entrata_nel_turno"):                                                                 # «that entered this turn»
        t_ = x.tavolo
        if t_ is None or not any(e_.tipo == "zona" and e_.a == "campo" and e_.nuovo == x.n for e_ in t_.eventi_del_turno()): return False
    if r.get("costituzione_min") is not None and costituzione(x) < r["costituzione_min"]: return False
    if r.get("forza_max") is not None and not ("creature" in tipi and forza(x) <= r["forza_max"]): return False   # «with power 2 or less»
    if r.get("forza_min") is not None and not ("creature" in tipi and forza(x) >= r["forza_min"]): return False   # «with power 4 or greater»
    if r.get("fc_max") is not None and not ("creature" in tipi and min(forza(x), costituzione(x)) <= r["fc_max"]): return False
    if r.get("costituzione_oltre_forza") and not ("creature" in tipi and costituzione(x) > forza(x)): return False
    if r.get("con_segnalino") and not x.segnalini[r["con_segnalino"]]: return False
    if r.get("ha_attaccato_turno"):                                                                # «that attacked this turn»
        t_ = x.tavolo
        if t_ is None or not any(e_.tipo == "attacca" and e_.vecchio == x.n for e_ in t_.eventi_del_turno()): return False
    if r.get("attaccante") and not r.get("_attaccanti", lambda o: True)(x): return False
    return True


# Gli agganci dei set (carte_set.modulo, 14 nov 2026): ogni posto Set/<SET> aggiunge qui solo cio' che e' suo, coi nomi
# suoi; il nucleo non sa niente delle meccaniche dei set. Vuoti, il motore e' quello di prima.
SE_SET = {}              # 603.4: le condizioni «if ...» di un innesco: k -> f(p, v, ctrl) -> bool
SE_STATICA_SET = {}      # 611.3a: le condizioni «as long as» di un'abilita' statica: k -> f(tavolo, v, o) -> bool
STATO_SET = []           # 704: le azioni di stato di un set: f(tavolo) -> [(cosa, chi, regola)]
FAI_STATO_SET = {}       # 704.3: come si fa un'azione di stato di un set: cosa -> f(tavolo, chi, regola)
def _rid_ferma(ab):
    """(giro 13) una riduzione che non dipende dai bersagli: quella di un set, o «for each / where X is / if» (601.2f)."""
    r_ = ab.get("riduzione") or {}
    return bool(r_.get("set") or "quanto" in r_ or "se" in r_)


RIDUZIONI_SET = {}       # 601.2f, 118.7: le riduzioni di costo di un set: nome -> f(partita, ab, ogg, costo) -> costo
COSTI_SET = {}           # 601.2h, 118.3: i costi di un set: chiave del costo -> (puo(partita, i, ogg, v), paga(partita, i, ogg, v))
ALTERNATIVI_SET = {}     # 118.9, 601.2b: i costi alternativi di un set: nome -> {"puo": f(p, i, ogg, alt) -> bool, "paga": f(p, i, ogg, alt),
                         #   "zona": la zona da cui si lancia se non e' la mano (702.180a: il cimitero), "riduzione": f(p, i, ogg, alt) -> delta,
                         #   "dopo": f(p, magia, alt) quando la magia e' lanciata, "entra": f(p, permanente, alt) quando diventa permanente}


def _tipi_creatura():
    """205.3m: i tipi di creatura, letti dal regolamento (14 nov 2026)."""
    f = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "Regole", "MagicCompRules.txt")
    riga = next((r for r in open(f, encoding="utf-8") if r.startswith("205.3m")), "")
    lista = riga.split("All other creature types are one word long:")[-1]
    return {w.strip().rstrip(".") for w in lista.split(",") if w.strip()} | {"Time Lord"}


TIPI_CREATURA = _tipi_creatura()


def ha_sottotipo(o, st):
    """205.3, 702.73a: o ha il sottotipo st; chi ha changeling («this object is every creature type», car
    «tutti_i_tipi_creatura») ha ogni tipo di creatura (non i tipi di terra o d'artefatto)."""
    if st in o.carta.tipo.split("//")[0].partition("—")[2].split(): return True
    return bool(o.carta.car.get("tutti_i_tipi_creatura")) and st in TIPI_CREATURA


def _evento_paga(t, n):
    for e in reversed(t.eventi):
        if e.tipo == "zona" and e.da == "pila" and e.a == "campo" and e.nuovo == n: n = e.vecchio; break
    return next((e for e in reversed(t.eventi) if e.tipo == "paga" and e.vecchio == n), None)


def mana_speso(t, n):
    """601.2h: il mana speso per lanciare la magia n, o per la magia che e' diventata il permanente n (608.3): (quanto, colori)."""
    ev = _evento_paga(t, n)
    if ev is None: return 0, 0
    return ev.quanto or 0, len(set(re.findall(r"\{([WUBRG])\}", ev.a or "")))


def speso_simboli(t, n, simboli):
    """601.2h: «if {W}{W} was spent to cast it»: fra il mana speso c'e' almeno quel mana, simbolo per simbolo."""
    ev = _evento_paga(t, n)
    if ev is None: return False
    speso = Counter(re.findall(r"\{([WUBRGC])\}", ev.a or ""))
    return all(speso[c] >= k for c, k in Counter(re.findall(r"\{([WUBRGC])\}", simboli)).items())


def segnalini_ok(o, v):
    """{"tipo": "carica", "n": 8}: l'oggetto ha almeno n segnalini di quel tipo (122.1)."""
    return o.segnalini[v["tipo"]] >= v["n"]


def scelto(sel, o, fonte, ctrl=None):
    """Il selettore di un effetto («creatures you control», «other creatures»): tipi stampati, controllo, «altre»;
    «equipped creature», «enchanted creature»: l'oggetto a cui la fonte e' attaccata (301.5, 303.4b)."""
    if sel.get("attaccata"): return fonte is not None and getattr(fonte, "attaccato_a", None) == o.n
    if ctrl is None: ctrl = fonte.controllore if fonte is not None else None
    if sel.get("altre") and o is fonte: return False
    tipi = set(sel.get("tipi") or ())
    if tipi and "permanent" not in tipi and not tipi & o.carta.tipi and not (sel.get("o_sottotipo") and ha_sottotipo(o, sel["o_sottotipo"])): return False
    if sel.get("non_tipi") and set(sel["non_tipi"]) & o.carta.tipi: return False
    if sel.get("non_pedina") and o.carta.pedina: return False
    if sel.get("pedina") and not o.carta.pedina: return False
    if sel.get("sottotipo") and not ha_sottotipo(o, sel["sottotipo"]): return False              # 702.73a
    if sel.get("sottotipi_o") and not any(ha_sottotipo(o, s_) for s_ in sel["sottotipi_o"]): return False   # «each Pest, Bat, ... you control»
    if sel.get("tipo_scelto"):                                                                     # 614.12, 205.3m: «of the chosen type»
        ts_ = getattr(fonte, "tipo_scelto", None)
        if not ts_ or not ha_sottotipo(o, ts_): return False
    if sel.get("con_segnalino") and not o.segnalini[sel["con_segnalino"]]: return False
    if sel.get("tappata") and not o.tappato: return False                                        # «tapped creatures»
    if sel.get("stappata") and o.tappato: return False                                           # «untapped creatures» (15 nov 2026)
    if sel.get("mv_max") is not None and (0 if o.carta.pedina else M.valore(o.carta.car.get("costo") or "")) > sel["mv_max"]: return False   # 202.3
    if sel.get("con_segnalini") and not any(v > 0 for v in o.segnalini.values()): return False    # «with one or more counters on it»
    if sel.get("mv_min") is not None and (0 if o.carta.pedina else M.valore(o.carta.car.get("costo") or "")) < sel["mv_min"]: return False   # 202.3
    if sel.get("attaccante"):                                                                    # 506.4: «attacking creatures»
        p_ = getattr(getattr(o, "tavolo", None), "_partita", None)
        if p_ is None or o not in (getattr(p_, "attaccanti", None) or {}): return False
    if sel.get("se_stessa") and o is not fonte: return False
    if sel.get("anche_tipo") and sel["anche_tipo"] not in o.carta.tipi: return False
    if sel.get("tranne_pedine_tue") and o.carta.pedina and o.controllore == (ctrl if ctrl is not None else getattr(fonte, "controllore", None)): return False
    if sel.get("forza_min") is not None and (forza(o) if "creature" in o.carta.tipi else -99) < sel["forza_min"]: return False
    if sel.get("forza_max") is not None and not ("creature" in o.carta.tipi and forza(o) <= sel["forza_max"]): return False   # 15 nov 2026
    if sel.get("non_sottotipi") and any(ha_sottotipo(o, s_) for s_ in sel["non_sottotipi"]): return False   # «non-Human» (205.4b)
    if sel.get("controllo") == "tuo" and o.controllore != ctrl: return False
    if sel.get("controllo") == "avversario" and o.controllore == ctrl: return False
    return True


# ====================================================================== il tavolo con gli effetti continui
class TavoloEffetti(Tavolo):
    """Il tavolo del passo 2 che calcola le caratteristiche coi livelli (613) e che segnala gli eventi agli inneschi."""

    def __init__(self, mazzi, nomi=None, seme=None, vite=20, fuori=None, basi_fuori=None):
        # 400.11, 100.4: le carte fuori dalla partita di ogni giocatore (il sideboard: nel Limited il resto del pool, 100.4b),
        # voci come quelle dei mazzi; basi_fuori: le terre base che nel Limited ci sono quante se ne vogliono (ruling di
        # Extrapolate the Impossible del 21 ago 2026). None = chi crea la partita non l'ha detto, e non si inventa.
        self.fuori = [list(f) for f in fuori] if fuori is not None else None
        self.basi_fuori = list(basi_fuori or [])
        self._ts = itertools.count(1)                     # 613.7: un contatore solo per oggetti, effetti e segnalini
        self.continui = []                                # gli effetti continui di magie e abilita' risolte (611.2)
        self.osservatore = None                           # la partita che ascolta gli eventi (gli inneschi, 603.2)
        self._coda, self._prima = [], None
        self.oggetti = {}                                 # numero -> oggetto, anche spento (per gli inneschi)
        self._versione, self._cache = 0, (None, None)
        self.da_innescate = False                         # c'e' (o c'e' stato) un effetto che da' abilita' innescate
        self.legami = {}                                  # 610.3: fonte -> gli oggetti esiliati «until ~ leaves the battlefield»
        self.scegli = None                                # le scelte dei giocatori che servono al tavolo (la partita lo collega)
        self.emblemi = []                                 # 114: nella zona di comando
        self._in_vista, self._cache_vista = False, (None, None)   # i livelli 1 e 4 (vista_carta)
        self._dall_esilio = {}                            # 400.7h: la magia in pila -> la carta in esilio da cui e' stata lanciata
        self._lanciate = {}                               # 601.2i: la magia in pila -> chi l'ha lanciata («if you cast it», 603.4)
        super().__init__(mazzi, nomi, seme, vite)
        for g in self.giocatori:
            for o in g.grimorio.carte: self.oggetti[o.n], o.ts = o, 0

    # ------------------------------------------------------------------ eventi e lotti
    def _dopo_evento(self, e):
        self._versione += 1
        if (e.tipo == "zona" and "campo" in (e.da, e.a)) or e.tipo == "fine effetti": self._conta_bassi()
        if e.tipo == "turno" and any(c.durata == "prossimo_turno" for c in self.continui):           # 611.2a: «until your next turn»
            via = [c for c in self.continui if c.durata == "prossimo_turno" and c.ctrl == e.giocatore]
            if via:
                self.continui = [c for c in self.continui if c not in via]
                self._evento("fine effetti", quanto=len(via), giocatore=e.giocatore, causa="611.2a")
        if e.tipo == "zona" and e.da == "esilio" and e.a == "pila": self._dall_esilio[e.nuovo] = e.vecchio   # 400.7h
        if e.tipo == "lanciata": self._lanciate[e.vecchio] = e.giocatore                           # 601.2i: chi l'ha lanciata (non le copie, 707.10)
        if e.tipo == "lanciata" and e.vecchio in self._dall_esilio:                                # 611.2a, 601.2i: «until this card is
            fine = (LANCIATA, self._dall_esilio[e.vecchio])                                          # cast from exile»: finisce quando la
            via = [c for c in self.continui if c.durata == fine]                                     # magia diventa lanciata (dopo il
            if via:                                                                                  # pagamento: 601.2g-h)
                self.continui = [c for c in self.continui if c not in via]
                self._evento("fine effetti", quanto=len(via), giocatore=e.giocatore, causa="611.2a")
        if self._lotto: self._coda.append(e)
        elif self.osservatore: self.osservatore([e], None)

    def _lotto_inizio(self):
        """603.10a: le caratteristiche di ogni permanente subito prima dell'azione: sono anche le ultime informazioni
        note (608.2h) di chi lascia il campo."""
        self._prima = dict(self._valori_campo())
        for o, v in self._prima.items(): o.lki = v
        vista = self._vista() if self._bassi else ({}, {}, set())
        for o in self.campo: o._carta_lki, o._copia_lki = vista[0].get(o), vista[1].get(o)       # 603.10a, 608.2h

    def _lotto_fine(self):
        coda, prima = self._coda, self._prima
        self._coda, self._prima = [], None
        if coda and self.osservatore: self.osservatore(coda, prima)

    def _sposta(self, ogg, verso, chi=None, posizione=None, causa=""):
        if ogg.vivo and ogg.zona == "campo" and verso == "cimitero" and getattr(ogg, "esilia_se_muore", None) == self.turno_numero:
            verso, causa = "esilio", "614.1a"                                                      # «exile it instead»
        if ogg.vivo and ogg.zona == "campo" and verso == "cimitero" and ogg.segnalini["finalita"] > 0:
            verso, causa = "esilio", "122.1h"                                                      # 122.1h, 614: esiliato invece
        if ogg.vivo and ogg.zona == "campo" and verso == "cimitero" and "creature" in ogg.carta.tipi and self._muore_esiliata(ogg):
            verso, causa = "esilio", "614.1a"                                                      # «would die, exile it instead»
        with self.insieme():                              # ogni cambio di zona si legge con lo sguardo all'indietro
            if ogg.vivo and ogg.zona == "campo" and getattr(ogg, "lki", None) is None: ogg.lki = self.caratteristiche(ogg)
            return super().sposta(ogg, verso, chi, posizione, causa)

    def _arriva(self, ogg, da, verso, chi, posizione, causa):
        if da == "campo" and getattr(ogg, "lki", None) is None: ogg.lki = self._valori_campo().get(ogg) or self._stampate(ogg)
        r_e = ogg._carta.retro() if verso == "campo" and (ogg.__dict__.get("_entra_retro") or (da == "pila" and ogg.__dict__.get("come_retro"))) else None
        entra = ((r_e if r_e is not None and not r_e.tipi & {"instant", "sorcery"} else ogg.carta).car.get("entra") or {})   # 712.11a
        tappata = verso == "campo" and self._entra_tappata(entra.get("tappata"), chi if chi is not None else ogg.proprietario)
        nuovo = super()._arriva(ogg, da, verso, chi, posizione, causa)
        nuovo.ts = next(self._ts)                                                                  # 613.7d
        if verso == "pila" and getattr(ogg, "come_avventura", False): nuovo.come_avventura = True   # 716.3: lanciata come avventura
        alt_ = getattr(ogg, "alternativo", None) if da == "pila" and verso == "campo" else None
        if alt_ is not None and getattr(self, "_partita", None) is not None:                       # il permanente di una magia lanciata
            nuovo.alternativo = alt_                                                               # col costo alternativo di un set
            reg = ALTERNATIVI_SET.get(alt_["nome"]) or {}
            if reg.get("entra"): reg["entra"](self._partita, nuovo, alt_)
        self.oggetti[nuovo.n] = nuovo
        if verso == "campo":
            if da == "pila": nuovo.x_magia = getattr(ogg, "x", 0)                                  # 107.3m
            if da == "pila": nuovo.facoltativo_pagato = bool(getattr(ogg, "facoltativo_pagato", False))   # 702.33d: «if it was kicked»
            if da == "pila" and ogg.n in self._lanciate: nuovo.lanciata_da = self._lanciate[ogg.n]   # 400.7d: «if you cast it»
            if da == "pila" and nuovo.fisica.car.get("copia_carta"): nuovo.fisica.pedina = True      # 608.3f, 707.10f: una pedina
            if tappata: nuovo.tappato = True                                                       # 614.1d, 614.12
            for tipo, n in (entra.get("segnalini") or {}).items():                                 # 614.1c, 122.6
                n = getattr(ogg, "x", 0) if n == "X" else n
                self.metti_segnalini(nuovo, tipo, n, causa="614.1c")
            es_ = entra.get("segnalini_se")                                                         # 614.1c (giro 8): «enters with a +1/+1
            if es_ and self.condizione_statica(es_["se"], nuovo):                                    # counter on it if you attacked this turn»
                for tipo, n in es_["segnalini"].items(): self.metti_segnalini(nuovo, tipo, n, causa="614.1c")
            for tipo, n in (ogg.__dict__.get("_entra_segnalini") or {}).items():                    # 614.1c: «return it ... with a
                self.metti_segnalini(nuovo, tipo, n, causa="614.1c")                               # +1/+1 counter on it»
            if getattr(nuovo, "facoltativo_pagato", False):                                        # 702.33d, 614.1c: «if it was kicked,
                for tipo, n in (entra.get("segnalini_se_facoltativo") or {}).items():              # it enters with ...»
                    self.metti_segnalini(nuovo, tipo, n, causa="614.1c")
            if entra.get("preparato"): self.prepara(nuovo, causa="723.3a")                          # «enters prepared»
            if entra.get("sceglie_colore"):                                                         # 614.1c, 614.12a, 105.4
                colori = ["W", "U", "B", "R", "G"]
                c = self.scegli("colore", nuovo.controllore, nuovo, colori, predefinita="W") if self.scegli else "W"
                nuovo.colore_scelto = c if c in colori else "W"
            if entra.get("sceglie_tipo"):                                                           # 614.12, 205.3m: «as this enters, choose
                opz_ = sorted(TIPI_CREATURA)                                                         # a creature type»
                pred_ = tipo_preferito(self, nuovo.controllore)
                c = self.scegli("tipo_creatura", nuovo.controllore, nuovo, opz_, predefinita=pred_) if self.scegli else pred_
                nuovo.tipo_scelto = c if c in TIPI_CREATURA else pred_
            if entra.get("sceglie_tra"):                                                            # 614.12: «as this enters, choose A or B»
                op = list(entra["sceglie_tra"])
                c = self.scegli("scelta_entrata", nuovo.controllore, nuovo, op, predefinita=op[0]) if self.scegli else op[0]
                nuovo.scelta_entrata = c if c in op else op[0]
            if getattr(ogg, "incanta_su", None) is not None:                                        # 608.3c: l'aura entra attaccata
                nuovo.attaccato_a = ogg.incanta_su
        return nuovo

    def _muore_esiliata(self, ogg):
        """614.1a: «If a creature an opponent controls would die, exile it instead» (Garruk, Veiled Butcher). 614.4: la
        sostituzione deve esistere prima dell'evento: in un'azione simultanea contano i permanenti di subito prima (anche
        quello che se ne va insieme), con le abilita' che avevano."""
        fonti = self._prima.items() if self._prima is not None else ((x, None) for x in list(self.campo))
        for x, v in fonti:
            if x is ogg or x.controllore is None or x.controllore == ogg.controllore: continue
            abil = v["abilita"] if v is not None else self.abilita_di(x)
            if any(ab.get("tipo") == "sostituzione" and ab.get("di") == "muore_esilio_avversari" for _, ab in abil): return True
        return False

    def _entra_tappata(self, cond, ctrl):
        """614.1d: «This land enters tapped [unless ...]»: la condizione si guarda mentre entra (614.12)."""
        if not cond: return False
        if cond == "sempre": return True
        if cond == "senza_planeswalker":
            return not any(o.controllore == ctrl and "planeswalker" in o.carta.tipi for o in self.campo)
        if cond == "senza_jace":
            puo = any(o.controllore == ctrl and "Jace" in o.carta.tipo.split("—")[-1].split() for o in self.campo) or \
                any("Jace" in o.carta.tipo.split("—")[-1].split() for o in self.giocatori[ctrl].mano)
            vuole = self.scegli("behold", ctrl, predefinita=True) if (puo and self.scegli) else puo
            return not (puo and vuole)
        if cond == "meno_di_due_altre_terre":
            return sum(1 for o in self.campo if o.controllore == ctrl and "land" in o.carta.tipi) < 2
        if cond == "senza_terra_base":                                                             # 205.4c: supertipo base
            return not any(o.controllore == ctrl and "land" in o.carta.tipi and "Basic" in o.carta.tipo.split("—")[0].split() for o in self.campo)
        if cond.startswith("senza_sottotipi:"):                                                    # «unless you control a Plains or an Island»
            st = cond.split(":")[1].split(",")
            return not any(o.controllore == ctrl and "land" in o.carta.tipi and any(s_ in o.carta.tipo.split("—")[-1].split() for s_ in st)
                           for o in self.campo)
        if cond.startswith("senza_permanenti:"):                                                   # «unless you control a Mount or Vehicle»
            st = cond.split(":")[1].split(",")
            return not any(o.controllore == ctrl and any(ha_sottotipo(o, s_) for s_ in st) for o in self.campo)
        if cond.startswith("senza_pagare_vite:"):                                                  # 614.12, 119.4: si paga solo con
            n = int(cond.split(":")[1])                                                            # abbastanza vite; chi non sceglie paga
            puo = self.giocatori[ctrl].vite >= n
            vuole = self.scegli("paga_vite_entrata", ctrl, n, predefinita=True) if (puo and self.scegli) else puo
            if puo and vuole:
                self.paga_vite(ctrl, n, causa="119.4")
                return False
            return True
        raise NonCoperto(f"614.1d: la condizione per entrare tappata {cond!r} non e' coperta")

    def candidati_fuori(self, i):
        """400.11, 100.4b: le carte fuori dalla partita di i (le voci del sideboard, piu' le terre base del Limited)."""
        if self.fuori is None: raise NonCoperto("400.11: le carte fuori dalla partita non le ha date chi ha creato la partita")
        return list(self.fuori[i]) + list(self.basi_fuori)

    def porta_dentro(self, i, voce, verso="mano", causa="400.11b"):
        """400.11b: una carta di i da fuori dalla partita entra in «verso» (un oggetto nuovo, proprietario i) e ci resta
        fino alla fine della partita; le terre base del Limited non finiscono (ruling del 21 ago 2026)."""
        from tavolo import Carta, Oggetto
        if voce in self.fuori[i]: self.fuori[i].remove(voce)
        elif voce not in self.basi_fuori: raise ValueError(f"{voce[0]} non e' fuori dalla partita per il giocatore {i}")
        nome, tipo, car = voce
        c = Carta(next(self._carte), nome, tipo, i, car=car)
        o = Oggetto(next(self._oggetti), c, verso, None)
        o.tavolo, o.ts = self, next(self._ts)
        self.lista(verso, i).append(o)
        self.oggetti[o.n] = o
        self._evento("zona", carta=c, da=None, a=verso, nuovo=o.n, giocatore=i, causa=causa)
        return o

    def copia_carta(self, chi, orig, causa="707.12"):
        """707.12, 112.2a: la copia di una carta nella stessa zona (l'esilio), di chi la crea e la puo' lanciare; i valori
        copiabili (707.2). Fuori dalla pila e dal campo smette di esistere (704.5e, 707.10a)."""
        import copy as _copy
        from tavolo import Carta, Oggetto
        f = orig.fisica if hasattr(orig, "fisica") else orig.carta
        c = Carta(next(self._carte), f.nome, f.tipo, chi, car=dict(_copy.deepcopy(f.car), copia_carta=True))
        o = Oggetto(next(self._oggetti), c, orig.zona, None)
        o.tavolo, o.ts = self, next(self._ts)
        from tavolo import DEL_GIOCATORE
        (self.lista(orig.zona, chi) if orig.zona in DEL_GIOCATORE else self.lista(orig.zona)).append(o)
        self.oggetti[o.n] = o
        self._evento("zona", carta=c, da=None, a=orig.zona, nuovo=o.n, giocatore=chi, causa=causa)
        return o

    def crea_pedina(self, chi, nome, tipo, causa="111.2", car=None):
        with self.insieme():
            o = super().crea_pedina(chi, nome, tipo, causa)
            if car: o.fisica.car.update(car)
            o.ts = next(self._ts)
            self.oggetti[o.n] = o
            return o

    def copiabili(self, o):
        """707.2: i valori copiabili: nome, costo di mana, tipi, testo, forza e costituzione stampati, come li cambiano
        altri effetti di copia (una pedina copia ha gia' come stampati i valori che ha copiato, 707.9a-b); non gli
        altri effetti, lo stato, i segnalini. Per un oggetto che ha lasciato il campo: com'era (608.2h)."""
        import copy as _copy
        if not o.vivo: c = getattr(o, "_copia_lki", None) or o.fisica                              # 608.2h: com'era
        elif o.zona == "campo" and self._bassi: c = self._vista()[1].get(o, o.fisica)              # 613.2c: dopo il livello 1
        else: c = o.fisica
        return c.nome, c.tipo, _copy.deepcopy(c.car)

    def crea_copia(self, chi, orig, eccezioni=None, causa="707.2"):
        """111.1, 707.2, 707.5: una pedina che e' copia di orig entra gia' copia: ha i suoi valori copiabili, le
        eccezioni dell'effetto ne fanno parte (707.9a-b), e le abilita' che sostituiscono l'entrata funzionano (entrare
        tappata, con segnalini: 614.1c-d). La fedelta' di un planeswalker con cui entra (306.5b). X vale 0 (107.3m: non
        e' stata lanciata). 111.5: la copia di un istantaneo o di una stregoneria non si crea."""
        from tavolo import Carta, Oggetto
        nome, tipo, car = self.copiabili(orig)
        if Carta(0, nome, tipo, chi).tipi & {"instant", "sorcery"}: return None
        for k, v in (eccezioni or {}).items():
            if k == "parole": car["parole"] = list(car.get("parole") or []) + [p_ for p_ in v if p_ not in (car.get("parole") or [])]
            elif k == "abilita": car["abilita"] = list(car.get("abilita") or []) + list(v)
            elif k == "leggendaria":                                                               # 707.9b (giro 13): «except it's
                via_ = re.sub(r"Legendary ", "", tipo)                                             # [not] legendary» (205.4a)
                tipo = ("Legendary " + via_) if v else via_
            else: raise NonCoperto(f"707.9: l'eccezione {k!r} di una copia non e' coperta")
        with self.insieme():
            c = Carta(next(self._carte), nome, tipo, chi, pedina=True, car=car)
            o = Oggetto(next(self._oggetti), c, "campo", chi)
            o.tavolo, o.controllo_dal, o.ts = self, self.turno_numero, next(self._ts)
            entra = car.get("entra") or {}
            if self._entra_tappata(entra.get("tappata"), chi): o.tappato = True                     # 614.1d
            if "planeswalker" in c.tipi: o.segnalini["fedelta"] = car.get("fedelta", 0)            # 306.5b
            self.campo.append(o)
            self.oggetti[o.n] = o
            self._evento("zona", carta=c, da=None, a="campo", nuovo=o.n, giocatore=chi, causa=causa)
            for tipo_s, n in (entra.get("segnalini") or {}).items():                               # 614.1c, 122.6
                self.metti_segnalini(o, tipo_s, 0 if n == "X" else n, causa="614.1c")
            if entra.get("preparato"): self.prepara(o, causa="723.3a")
            if entra.get("sceglie_colore"):                                                        # 614.12a, 707.6: sceglie di nuovo
                colori = ["W", "U", "B", "R", "G"]
                cs = self.scegli("colore", chi, o, colori, predefinita="W") if self.scegli else "W"
                o.colore_scelto = cs if cs in colori else "W"
            if entra.get("sceglie_tra"):                                                           # 614.12
                op = list(entra["sceglie_tra"])
                cs = self.scegli("scelta_entrata", chi, o, op, predefinita=op[0]) if self.scegli else op[0]
                o.scelta_entrata = cs if cs in op else op[0]
        return o

    def diventa_copia(self, x, orig, fonte=None, durata=None, ctrl=None):
        """707.2, 613.2a: il permanente x diventa una copia di orig: un effetto di livello 1 con i valori copiabili di
        adesso (707.2b), solo su x (611.2c). x non entra e non esce (707.4): nessun evento di zona."""
        return self.aggiungi_continuo("1", {"copia": self.copiabili(orig), "di": orig.n}, chi=frozenset({x.n}), fonte=fonte,
                                      durata=durata, ctrl=ctrl)

    # ------------------------------------------------------------------ gli effetti continui
    def aggiungi_continuo(self, livello, dati, chi=None, sel=None, fonte=None, durata=None, ctrl=None):
        """611.2: un effetto di una magia o abilita' risolta, col timestamp di quando nasce (613.7b)."""
        if livello not in LIVELLI + LIVELLI_BASSI: raise NonCoperto(f"613.1: il livello {livello} non e' coperto")
        if durata not in DURATE and not (isinstance(durata, tuple) and durata[0] == LANCIATA):
            raise NonCoperto(f"611.2b: la durata {durata!r} non e' coperta")
        c = Continuo(next(self._ts), livello, dati, chi=chi, sel=sel, fonte=fonte, durata=durata, ctrl=ctrl)
        self.continui.append(c)
        self._versione += 1
        if livello in LIVELLI_BASSI: self._conta_bassi()
        return c

    # ------------------------------------------------------------------ i livelli 1 e 4: la carta vista dal motore
    def _conta_bassi(self):
        """Quante fonti di effetti dei livelli 1 e 4 ci sono: effetti risolti in corso e abilita' statiche stampate dei
        permanenti in campo. A zero ogni oggetto e' la sua carta fisica e il motore non calcola niente in piu'."""
        n = sum(1 for c in self.continui if c.livello in LIVELLI_BASSI)
        for o in self.campo:
            for ab in o.fisica.car.get("abilita") or ():
                if ab.get("tipo") == "statica" and any(d.get("livello") in LIVELLI_BASSI for d in ab.get("effetti") or ()): n += 1
        self._bassi = n

    def vista_carta(self, o):
        """Le caratteristiche di o dopo i livelli 1 e 4 (613.1a, 613.1d): in campo calcolate; fuori dal campo la carta
        fisica (gli effetti dei permanenti valgono in campo, 611.3a); un oggetto che ha lasciato il campo com'era
        subito prima (603.10a, 608.2h)."""
        if self._in_vista: return o.fisica
        if not o.vivo: return getattr(o, "_carta_lki", None) or o.fisica
        if getattr(o, "come_avventura", False) and o.zona in ("mano", "pila"):                     # 716.3a-b: solo le caratteristiche
            return self._carta_avventura(o)                                                         # dell'avventura
        if o.__dict__.get("come_retro") and o.zona in ("mano", "pila") and o._carta.retro() is not None:   # 712.8b, 712.6e: la
            return o._carta.retro()                                                                 # faccia dietro di una modale
        if o.zona != "campo": return o.fisica
        return self._vista()[0].get(o, o.fisica)

    def _carta_avventura(self, o):
        """716.2, 716.3b: la stessa carta (716.2c) con le caratteristiche alternative dell'avventura."""
        from tavolo import Carta
        v = getattr(o, "_avventura_vista", None)
        if v is None:
            nome, tipo, car = o.fisica.car["avventura"]
            v = Carta(o.fisica.n, nome, tipo, o.fisica.proprietario, pedina=o.fisica.pedina)
            v.car = car
            o._avventura_vista = v
        return v

    def _vista(self):
        chiave = (self._versione, len(self.continui), len(self.campo))
        if self._cache_vista[0] != chiave:
            self._in_vista = True
            try: v = self._calcola_vista(list(self.campo))
            finally: self._in_vista = False
            self._cache_vista = (chiave, v)
        return self._cache_vista[1]

    def _calcola_vista(self, campo):
        """-> (dopo i livelli 1 e 4, dopo il solo livello 1, le parti di livello 4 applicate). Si parte dalla carta
        (613.1). Livello 1 (613.2a): gli effetti di copia in ordine di timestamp (613.7b), coi valori copiabili presi
        quando l'effetto e' nato (707.2b); dopo, quelli sono i valori copiabili (613.2c). Livello 4 (613.1d): i tipi
        dati «in addition to its other types», che lasciano tutti i tipi di prima (205.1b); tutti aggiungono e basta,
        quindi l'ordine fra loro non cambia il risultato. Un effetto che parte nel livello 4 continua nel 7b sugli
        stessi oggetti anche se l'abilita' sparisse dopo (613.6): le parti applicate tornano a _calcola."""
        from tavolo import Carta

        def nuova(c0, nome, tipo, car):
            v = Carta(c0.n, nome, tipo, c0.proprietario, pedina=c0.pedina)
            v.car = car
            return v
        per_n = {o.n: o for o in campo}
        l1 = {}
        for c in sorted((c for c in self.continui if c.livello == "1"), key=lambda c: c.ts):
            if c.chi is None: raise NonCoperto("613.2a: un effetto di copia senza l'insieme fissato (611.2c)")
            for n in sorted(c.chi):
                o = per_n.get(n)
                if o is not None: l1[o] = nuova(o.fisica, *c.dati["copia"])
        base = {o: l1.get(o, o.fisica) for o in campo}
        statiche = []
        for f in campo:
            for k, ab in enumerate(base[f].car.get("abilita") or []):
                if ab.get("tipo") != "statica": continue
                for d in ab["effetti"]:
                    if d["livello"] == "1": raise NonCoperto(f"707.2c: un effetto di copia da un'abilita' statica ({f.nome})")
                    if d["livello"] == "4": statiche.append((f, k, d))
        piu, applicati, tutti_tipi = {}, set(), set()
        for f, k, d in sorted(statiche, key=lambda x: (x[0].ts, x[0].n)):                           # 613.7a
            sel_ = set(d.get("chi") or {})
            if sel_ == {"se_stessa"} and set(d.get("se") or {}) <= {"segnalini_almeno"}:              # 611.3a, 722.2b (14 nov 2026):
                if d.get("se") and not segnalini_ok(f, d["se"]["segnalini_almeno"]): continue       # i segnalini non dipendono dai livelli
                o = f
            elif sel_ != {"attaccata"} or d.get("se"):
                raise NonCoperto(f"613.1d: il cambio di tipo di {f.nome} con il selettore {d.get('chi')} non e' coperto")
            else: o = per_n.get(getattr(f, "attaccato_a", None))                                    # 303.4b, 301.5
            if o is None: continue
            tipi, sotto = piu.setdefault(o, ([], []))
            tipi += [x for x in d.get("tipi") or () if x not in tipi]
            sotto += [x for x in d.get("sottotipi") or () if x not in sotto]
            if d.get("tutti_tipi"): tutti_tipi.add(o)                                                  # 205.3m (giro 11)
            applicati.add((f.n, k, o.n))
        for c in sorted((c for c in self.continui if c.livello == "4"), key=lambda c: c.ts):          # 613.1d, 611.2c: da un'abilita'
            if c.chi is None: raise NonCoperto("613.1d, 611.2c: un cambio di tipo risolto senza l'insieme fissato")   # risolta (crew, 702.122a)
            for n in sorted(c.chi):
                o = per_n.get(n)
                if o is None: continue
                tipi, sotto = piu.setdefault(o, ([], []))
                tipi += [x for x in c.dati.get("tipi") or () if x not in tipi]
                sotto += [x for x in c.dati.get("sottotipi") or () if x not in sotto]
        tutto = dict(l1)
        for o, (tipi, sotto) in piu.items():
            c0 = base[o]
            tutto[o] = nuova(c0, c0.nome, self._con_tipi(c0.tipo, tipi, sotto),
                             dict(c0.car, tutti_i_tipi_creatura=True) if o in tutti_tipi else c0.car)
        return tutto, l1, applicati

    def _con_tipi(self, tipo, tipi, sotto): return con_tipi(tipo, tipi, sotto)

    def stappa(self, ogg):
        """«Enchanted creature ... can't become untapped» (Frozen in Ice): nessuno stap, da nessun effetto."""
        if any(getattr(a, "attaccato_a", None) == ogg.n and a.carta.car.get("mai_stappa") for a in self.campo): return False
        return super().stappa(ogg)

    def fine_turno(self):
        """514.2, 611.2a: finiscono gli effetti «until end of turn» (anche il controllo preso fino a fine turno, 613.1b)."""
        for x, prima in reversed(getattr(self, "controlli_temp", [])):                              # dal piu' recente: torna com'era
            if x.vivo and x.zona == "campo": self.prendi_controllo(x, prima, causa="514.2")
        self.controlli_temp = []
        via = [c for c in self.continui if c.durata == "fine_turno"]
        if via:
            self.continui = [c for c in self.continui if c.durata != "fine_turno"]
            self._versione += 1
            self._evento("fine effetti", quanto=len(via), causa="514.2")

    def attacca(self, x, a, causa="701.3a"):
        """701.3a-c: x (aura o equipaggiamento in campo) va su a; se non puo', non si muove; nuovo timestamp."""
        if not (x.vivo and x.zona == "campo" and a.vivo and a.zona == "campo"): return False
        if getattr(x, "attaccato_a", None) == a.n: return False                                     # 701.3b
        if not self._puo_attaccare(x, a): return False
        x.attaccato_a, x.ts = a.n, next(self._ts)                                                  # 701.3c, 613.7e
        self._versione += 1
        self._evento("attaccata", carta=x.carta, vecchio=x.n, nuovo=a.n, giocatore=x.controllore, causa=causa)
        return True

    def _puo_attaccare(self, x, a):
        """301.5c, 303.4d: l'equipaggiamento solo su una creatura, non su se stesso; l'aura su cio' che la sua «enchant»
        permette (303.4a)."""
        if x is a: return False
        if "Equipment" in x.carta.tipo: return "creature" in a.carta.tipi and "creature" not in x.carta.tipi
        incanta = x.carta.car.get("incanta")
        if incanta: return (bool(set(incanta["chi"]) & a.carta.tipi) or "permanent" in incanta["chi"]) and filtri_ok(incanta, a)
        return False

    def prepara(self, o, causa="723.3a"):
        """723.3a, 723.3c: il permanente con una magia preparata diventa preparato (se non lo e' gia') e chi lo controlla
        crea in esilio una copia con le sole caratteristiche della magia preparata."""
        spell = o.carta.car.get("prepara")
        if not spell or not (o.vivo and o.zona == "campo") or getattr(o, "preparato", False): return None
        from tavolo import Carta, Oggetto
        o.preparato = True
        nome, tipo, car = spell
        c = Carta(next(self._carte), nome, tipo, o.controllore, car=dict(car, copia_di=o.n))
        x = Oggetto(next(self._oggetti), c, "esilio")
        x.tavolo, x.ts = self, next(self._ts)
        self.esilio.append(x)
        self.oggetti[x.n] = x
        self._evento("zona", carta=c, da=None, a="esilio", nuovo=x.n, giocatore=o.controllore, causa="723.3c")
        return x

    def _sostituzioni(self, di, ctrl):
        """614.1a: quante sostituzioni «di» generano le statiche dei permanenti di ctrl (con le abilita' che hanno adesso,
        604.2). Ognuna si applica una volta (616.1): l'ordine non cambia il risultato per quelle coperte."""
        return sum(1 for x in list(self.campo) if x.controllore == ctrl
                   for _, ab in self.abilita_di(x) if ab.get("tipo") == "sostituzione" and ab.get("di") == di)

    def infliggi(self, fonte, danni, causa="120.2b"):
        """614.1a: «If a source you control would deal noncombat damage to an opponent or a permanent an opponent
        controls, it deals that much damage plus 1 instead» (Tomik, Izzet Sparkmage)."""
        c = getattr(fonte, "controllore", None)
        if causa != "510.2" and c is not None:
            k = self._sostituzioni("danno_piu_uno_nc", c)
            if k:
                danni = [(a, n + k if n > 0 and ((a != c) if isinstance(a, numbers.Integral) else (a.controllore != c)) else n) for a, n in danni]
        return super().infliggi(fonte, danni, causa)

    def vince(self, i, causa="104.2b"):
        """104.2b: un effetto dice che un giocatore vince; la partita finisce subito (104.1), gli altri la perdono."""
        if self.finita: return
        for g in self.giocatori:
            if g.i != i and not g.perso: g.perso, g.perche = True, causa
        self.finita, self.vincitore = True, i
        self._evento("vince", giocatore=i, causa=causa)

    def sposta(self, ogg, verso, chi=None, posizione=None, causa=""):
        era_in_campo = ogg.vivo and ogg.zona == "campo"
        nuovo = self._sposta(ogg, verso, chi, posizione, causa)
        if era_in_campo and not ogg.vivo and ogg.n in self.legami:                                  # 610.3: «until ~ leaves»
            for x in self.legami.pop(ogg.n):
                if x.vivo and x.zona == "esilio": self.metti_in_campo(x, chi=x.proprietario, causa="610.3c")
        return nuovo

    def metti_segnalini(self, o, tipo, n, causa="122.1a"):
        if n <= 0 or not (o.vivo and o.zona == "campo"): return 0
        if tipo == "+1/+1" and "creature" in o.carta.tipi:                                           # 614.1a, 122.6 (anche entrando)
            n += self._sostituzioni("segnalini_piu_uno", o.controllore)
        o.segnalini[tipo] += n
        if tipo in PAROLE_7:                                                                         # 122.1b, 613.7e: il timestamp del
            if not hasattr(o, "ts_parole"): o.ts_parole = {}                                         # segnalino parola (vale nel livello 6)
            o.ts_parole[tipo] = next(self._ts)
        self._evento("segnalini", carta=o.carta, vecchio=o.n, giocatore=o.controllore, a=tipo, quanto=n, causa=causa,
                     nuovo=o.segnalini[tipo])                                                        # quanti dopo (715.2b)
        return n

    def togli_segnalini(self, o, tipo, n, causa="122.1"):
        n = min(n, o.segnalini[tipo])
        if n <= 0: return 0
        o.segnalini[tipo] -= n
        self._evento("segnalini", carta=o.carta, vecchio=o.n, giocatore=o.controllore, a=tipo, quanto=-n, causa=causa)
        return n

    # ------------------------------------------------------------------ le caratteristiche (613)
    def _tipi_nei_cimiteri(self):
        """205.2a: i tipi di carta fra le carte di tutti i cimiteri (i supertipi come «legendary» non sono tipi)."""
        return len(set().union(*[o.carta.tipi for g in self.giocatori for o in g.cimitero] or [set()]) & TIPI_DI_CARTA)

    def _tipi_base(self, i):
        """205.3i, 305.6: quanti tipi di terra base (Plains, Island, Swamp, Mountain, Forest) fra le terre che i controlla."""
        return len({w for o in self.campo if o.controllore == i and "land" in o.carta.tipi
                    for w in o.carta.tipo.split("//")[0].partition("—")[2].split()} & TIPI_BASE)

    def _stampate(self, ogg):
        car = ogg.carta.car
        f, c = car.get("forza"), car.get("costituzione")
        if car.get("cda") == "tipi_cimiteri":                                                      # 604.3, 613.4a: il livello 7a, ovunque (113.6a)
            n = self._tipi_nei_cimiteri()
            f, c = n, n + 1
        if car.get("cda") == "dominio":                                                            # «Domain»: 604.3, 613.4a, 205.3i, 305.6;
            chi = ogg.controllore if ogg.controllore is not None else ogg.proprietario              # 109.5: fuori dal campo il proprietario
            f = self._tipi_base(chi)
        if isinstance(car.get("cda"), dict) and "controlli" in car["cda"]:                         # 604.3, 613.4a: «equal to the number of
            chi = ogg.controllore if ogg.controllore is not None else ogg.proprietario              # creatures you control» (109.5)
            n = sum(1 for x in self.campo if x.controllore == chi and scelto(car["cda"]["controlli"], x, ogg, chi))
            f = n
            if car["cda"].get("anche_costituzione"): c = n
        if isinstance(f, str) or isinstance(c, str): raise NonCoperto(f"604.3, 613.4a: la forza definita di {ogg.nome}")
        return {"forza": f, "costituzione": c, "parole": frozenset(parole_stampate(ogg, PAROLE_7)),
                "abilita": list(enumerate(car.get("abilita") or []))}

    def caratteristiche(self, ogg):
        """Le caratteristiche dopo gli effetti continui: in campo coi livelli, fuori dal campo quelle stampate; un oggetto
        che ha lasciato il campo ha le sue ultime informazioni note (608.2h, 113.7a)."""
        if ogg.vivo and ogg.zona == "campo":
            v = self._valori_campo().get(ogg)
            return v if v is not None else self._stampate(ogg)
        if not ogg.vivo and getattr(ogg, "lki", None) is not None: return ogg.lki
        return self._stampate(ogg)

    def parole_di(self, ogg): return set(self.caratteristiche(ogg)["parole"])

    def _ha_costituzione(self, ogg): return self.caratteristiche(ogg)["costituzione"] is not None   # 613.4b, 208.3

    def forza_di(self, ogg): return self.caratteristiche(ogg)["forza"]

    def costituzione_di(self, ogg): return self.caratteristiche(ogg)["costituzione"]

    def abilita_di(self, ogg): return self.caratteristiche(ogg)["abilita"]

    def _valori_campo(self):
        chiave = (self._versione, len(self.continui), len(self.campo))
        if self._cache[0] != chiave: self._cache = (chiave, self._calcola(list(self.campo)))
        return self._cache[1]

    def _applica_a(self, e, o):
        """611.3a: l'effetto statico vale per quello che il suo testo indica adesso; 611.2c: quello di una magia o
        abilita' risolta per l'insieme fissato quando e' cominciato."""
        if e.chi is None: return scelto(e.sel, o, e.fonte, e.ctrl)
        return o.n in e.chi

    def _dipende(self, e, r):
        """613.8a: e dipende da r se sono nello stesso livello e applicare r cambia l'esistenza di e: r toglie tutte le
        abilita' alla fonte dell'abilita' statica che genera e (604.2: senza l'abilita' l'effetto non c'e')."""
        return (e is not r and e.statica and r.livello == e.livello and r.dati.get("toglie") == "tutte"
                and self._applica_a(r, e.fonte))

    def _effetti(self, campo, base):
        eff = list(self.continui)
        for o in campo:                                                                            # 604.2, 611.3
            for k, ab in base[o]["abilita"]:
                if ab.get("tipo") != "statica": continue
                for d in ab["effetti"]:
                    if d["livello"] in LIVELLI_BASSI: continue                                     # gia' applicati (vista_carta)
                    if d.get("se") and not self.condizione_statica(d["se"], o): continue          # «as long as»
                    if d["livello"] not in LIVELLI: raise NonCoperto(f"613.1: il livello {d['livello']} di {o.nome}")
                    eff.append(Continuo(o.ts, d["livello"], d, sel=d.get("chi") or {}, fonte=o, k=k, statica=True))   # 613.7a
        for o in self.emblemi:                                                                     # 114.4: dalla zona di comando
            for k, ab in enumerate(o.carta.car.get("abilita") or []):
                if ab.get("tipo") != "statica": continue
                for d in ab["effetti"]:
                    eff.append(Continuo(o.ts, d["livello"], d, sel=d.get("chi") or {}, fonte=o, k=k, statica=False, ctrl=o.controllore))
        return eff

    def eventi_del_turno(self):
        k = max((j for j, e in enumerate(self.eventi) if e.tipo == "turno"), default=0)
        return self.eventi[k:]

    def condizione_statica(self, cond, o):
        """Le condizioni di un'abilita' statica «as long as» (611.3a: vale quando e' vera): il cimitero di chi la
        controlla, un danno non da combattimento a un avversario in questo turno."""
        ctrl = o.controllore
        for k, v in cond.items():
            if k == "cimitero_almeno":
                if len(self.giocatori[ctrl].cimitero) < v: return False
            elif k == "avversario_danno_nc_turno":
                if not any(e.tipo == "danno" and e.nuovo is None and e.causa != "510.2" and e.giocatore != ctrl
                           for e in self.eventi_del_turno()): return False
            elif k == "senza_danno_combattimento":                                                 # «as long as they haven't dealt combat damage yet»
                if any(e.tipo == "danno" and e.causa == "510.2" and e.vecchio == o.n for e in self.eventi): return False
            elif k == "segnalini_almeno":                                                          # «as long as it has N or more
                if not segnalini_ok(o, v): return False                                            # [charge] counters» (722.2a, 711, 717)
            elif k == "controlli":                                                                 # «as long as you control a ...»
                if not any(x.controllore == ctrl and scelto(v, x, o, ctrl) for x in self.campo): return False
            elif k == "tuo_turno":                                                                 # «during your turn»
                ev = self.eventi_del_turno()
                if not (ev and ev[0].tipo == "turno" and ev[0].giocatore == ctrl): return False
            elif k == "scelta_entrata":                                                            # 614.12, 607.2: la parte scelta entrando
                if getattr(o, "scelta_entrata", None) != v: return False
            elif k == "controlli_almeno":                                                          # «as long as you control two or more artifacts»
                if sum(1 for x in self.campo if x.controllore == ctrl and scelto(v["sel"], x, o, ctrl)) < v["n"]: return False
            elif k == "lanciate_turno_almeno":                                                     # «two or more spells this turn»
                if sum(1 for e in self.eventi_del_turno() if e.tipo == "lanciata" and e.giocatore == ctrl) < v: return False
            elif k == "vite_almeno":                                                               # «25 or more life»
                if self.giocatori[ctrl].vite < v: return False
            elif k == "cimitero_tipi_almeno":                                                      # «two or more instant and/or sorcery cards»
                if sum(1 for x in self.giocatori[ctrl].cimitero if set(v["tipi"]) & x.carta.tipi
                       and (not v.get("sottotipo") or ha_sottotipo(x, v["sottotipo"]))) < v["n"]: return False   # «an Elf card»
            elif k == "morta_turno":                                                               # «a creature died this turn» (700.4)
                if not any(e.tipo == "zona" and e.da == "campo" and e.a == "cimitero" and e.carta is not None and "creature" in e.carta.tipi
                           for e in self.eventi_del_turno()): return False
            elif k == "avversario_perso_turno":                                                    # «an opponent lost life this turn»
                if not any(e.tipo == "vite" and (e.quanto or 0) < 0 and e.giocatore != ctrl for e in self.eventi_del_turno()): return False
            elif k == "guadagnato_turno":                                                          # «you gained life this turn»
                if not any(e.tipo == "vite" and (e.quanto or 0) > 0 and e.giocatore == ctrl for e in self.eventi_del_turno()): return False
            elif k == "noncreatura_turno":                                                         # «you've cast a noncreature spell this turn»
                if not any(e.tipo == "lanciata" and e.giocatore == ctrl and e.carta is not None and "creature" not in e.carta.tipi
                           for e in self.eventi_del_turno()): return False
            elif k == "mano_almeno":                                                               # «seven or more cards in your hand»
                if len(self.giocatori[ctrl].mano) < v: return False
            elif k == "terre_nomi_almeno":                                                         # 201.2: «differently named lands»
                if len({x.nome for x in self.campo if x.controllore == ctrl and "land" in x.carta.tipi}) < v: return False
            elif k == "pescate_turno_almeno":                                                      # «you've drawn two or more cards this turn» (121.1)
                if sum(1 for e in self.eventi_del_turno() if e.tipo == "zona" and e.da == "grimorio" and e.a == "mano"
                       and e.giocatore == ctrl and e.causa in ("121.1", "504.1")) < v: return False
            elif k.startswith("fonte_") and not hasattr(o, "segnalini"):                           # la fonte non c'e' piu' (608.2b)
                raise NonCoperto(f"611.3a: la condizione {k!r} su una fonte che non e' in gioco")
            elif k == "avversario_vite_max":                                                       # «an opponent has 10 or less life» (119.1)
                if not any(g.i != ctrl and not g.perso and g.vite <= v for g in self.giocatori): return False
            elif k == "mano_max":                                                                  # «one or fewer cards in hand» (402.1)
                if len(self.giocatori[ctrl].mano) > v: return False
            elif k == "fonte_attacca":                                                             # «as long as it's attacking» (506.4)
                p_ = getattr(self, "_partita", None)
                if p_ is None or o not in (getattr(p_, "attaccanti", None) or {}): return False
            elif k == "fonte_equipaggiata":                                                        # 301.5: un Equipaggiamento attaccato
                if not any(getattr(x, "attaccato_a", None) == o.n and ha_sottotipo(x, "Equipment") for x in self.campo): return False
            elif k == "fonte_modificata":                                                          # 700.9: segnalini, equipaggiata, o un'Aura
                if not (any(n_ > 0 for n_ in o.segnalini.values())                                 # di chi la controlla
                        or any(getattr(x, "attaccato_a", None) == o.n and (ha_sottotipo(x, "Equipment")
                               or (ha_sottotipo(x, "Aura") and x.controllore == o.controllore)) for x in self.campo)): return False
            elif k == "fonte_con_segnalini":                                                       # 122.1
                if not any(n_ > 0 for n_ in o.segnalini.values()): return False
            elif k == "fonte_ha_attaccato":                                                        # 508.1k: dichiarata attaccante in questo turno
                if not any(e.tipo == "attacca" and e.vecchio == o.n for e in self.eventi_del_turno()): return False
            elif k == "senza_danno":                                                               # «it hasn't dealt damage yet» (120.1)
                if any(e.tipo == "danno" and e.vecchio == o.n for e in self.eventi): return False
            elif k == "entrata_tua_turno":                                                         # «another creature entered the battlefield
                if not any(e.tipo == "zona" and e.a == "campo" and e.giocatore == ctrl and e.carta is not None   # under your control this turn»
                           and set(v["tipi"]) & e.carta.tipi and not (v.get("altra") and e.nuovo == o.n)
                           for e in self.eventi_del_turno()): return False
            elif k == "entrate_tue_turno_almeno":                                                  # «two or more creatures entered the
                if sum(1 for e in self.eventi_del_turno() if e.tipo == "zona" and e.a == "campo" and e.giocatore == ctrl   # battlefield under your
                       and e.carta is not None and set(v["tipi"]) & e.carta.tipi) < v["n"]: return False   # control this turn»
            elif k == "totale_fc_almeno":                                                          # «creatures you control have total power 8
                tot_ = sum((forza(x) if v["quale"] == "forza" else costituzione(x)) or 0 for x in self.campo   # or greater» (208.1)
                           if x.controllore == ctrl and "creature" in x.carta.tipi)
                if tot_ < v["n"]: return False
            elif k == "lanciate_tipo_turno_almeno":                                                # «another instant or sorcery spell»
                if sum(1 for e in self.eventi_del_turno() if e.tipo == "lanciata" and e.giocatore == ctrl and e.carta is not None
                       and set(v["tipi"]) & e.carta.tipi) < v["n"]: return False
            elif k == "attaccato_turno":                                                           # «you attacked this turn» (508.1)
                if not any(e.tipo == "attacca" and e.giocatore == ctrl for e in self.eventi_del_turno()): return False
            elif k == "lasciato_tuo_turno":                                                        # «a permanent left the battlefield under
                if not any(e.tipo == "zona" and e.da == "campo" and e.giocatore == ctrl for e in self.eventi_del_turno()): return False   # your control»
            elif k == "avversario_piu_terre":                                                      # «an opponent controls more lands than you»
                mie_ = sum(1 for x in self.campo if x.controllore == ctrl and "land" in x.carta.tipi)
                if not any(g.i != ctrl and not g.perso and sum(1 for x in self.campo if x.controllore == g.i and "land" in x.carta.tipi) > mie_
                           for g in self.giocatori): return False
            elif k == "guadagnato_turno_almeno":                                                   # «you've gained 3 or more life this turn»
                if sum(e.quanto or 0 for e in self.eventi_del_turno() if e.tipo == "vite" and (e.quanto or 0) > 0 and e.giocatore == ctrl) < v: return False
            elif k == "lanciata_mv_turno":                                                         # «a spell with mana value 4 or greater»
                if not any(e.tipo == "lanciata" and e.giocatore == ctrl and e.carta is not None
                           and M.valore(e.carta.car.get("costo") or "") >= v for e in self.eventi_del_turno()): return False
            elif k == "non":                                                                       # «unless COND» (giro 11)
                if self.condizione_statica(v, o): return False
            elif k in SE_STATICA_SET:                                                              # la condizione di un set
                if not SE_STATICA_SET[k](self, v, o): return False
            else: raise NonCoperto(f"611.3a: la condizione {k!r} non e' coperta")
        return True

    def _calcola(self, campo):
        base = {o: self._stampate(o) for o in campo}
        par = {o: set(base[o]["parole"]) for o in campo}
        abil = {o: {k for k, _ in base[o]["abilita"]} for o in campo}
        date = {o: {} for o in campo}
        mana_dato = {o: [] for o in campo}                                                         # 613.1f, 605.1a: «gains "{T}: Add ..."»
        senza = set()
        eff = self._effetti(campo, base)
        ordine = {id(e): j for j, e in enumerate(eff)}
        chiave = lambda e: (e.ts, ordine[id(e)])
        def esiste(e): return not e.statica or (e.fonte in abil and e.k in abil[e.fonte])           # 604.2
        # livello 6 (613.1f), in ordine di timestamp (613.3, 613.7) salvo le dipendenze (613.8b-c)
        resto = [e for e in eff if e.livello == "6"]
        tolte = defaultdict(dict)                                                                    # chi ha perso cosa, e quando
        while resto:
            liberi = [e for e in resto if not any(self._dipende(e, r) for r in resto)]
            e = min(liberi or resto, key=chiave)                                                   # 613.8b: in un anello, timestamp
            resto.remove(e)
            if not esiste(e): continue
            for o in campo:
                if not self._applica_a(e, o): continue
                if e.dati.get("dai"): par[o] |= set(e.dati["dai"])
                if any(x.get("tipo") == "innescata" for x in e.dati.get("dai_abilita") or []): self.da_innescate = True
                for j, ab in enumerate(e.dati.get("dai_abilita") or []):                            # 613.1f, 113.1a
                    kd = ("data", e.fonte.n if e.fonte is not None else 0, e.k, j)
                    date[o][kd] = ab
                    abil[o].add(kd)
                if e.dati.get("dai_mana"): mana_dato[o] += [m for m in e.dati["dai_mana"] if m not in mana_dato[o]]
                if e.dati.get("toglie") == "tutte": par[o].clear(); abil[o].clear(); senza.add(o); mana_dato[o].clear(); tolte[o]["*"] = e.ts
                elif e.dati.get("toglie"):
                    par[o] -= set(e.dati["toglie"])
                    for k_ in e.dati["toglie"]: tolte[o][k_] = e.ts
        for o in campo:                                                                            # 122.1b, 613.1f: i segnalini parola,
            for k_, ts_ in (getattr(o, "ts_parole", None) or {}).items():                           # col loro timestamp: chi toglie dopo
                if o.segnalini[k_] > 0 and ts_ > max(tolte[o].get(k_, 0), tolte[o].get("*", 0)): par[o].add(k_)   # li toglie
        # livello 7 (613.4)
        applicati = self._vista()[2] if self._bassi else set()
        def segue(e, o): return self._segue(e, o, applicati)
        valori = {}
        for o in campo:
            f, c = base[o]["forza"], base[o]["costituzione"]
            if "creature" in o.carta.tipi and (f is None or c is None):                            # 208.3: diventata creatura,
                if any(e.livello == "7b" and (esiste(e) or segue(e, o)) and self._applica_a(e, o) for e in eff):
                    f, c = 0, 0                                                                    # la forza base la da' il 7b
            if "creature" in o.carta.tipi and f is not None and c is not None:
                miei = [e for e in eff if e.livello.startswith("7") and (esiste(e) or segue(e, o)) and self._applica_a(e, o)]
                f, c = self._livello_7(o, f, c, sorted(miei, key=chiave))
            valori[o] = {"forza": f, "costituzione": c, "parole": frozenset(par[o]),
                         "abilita": [(k, ab) for k, ab in base[o]["abilita"] if k in abil[o]
                                     and (not ab.get("da_parola") or ab["da_parola"] in par[o])]     # 702.108a, 702.21a
                                    + [(k, ab) for k, ab in date[o].items() if k in abil[o]],
                         "mana_ok": o not in senza, "mana_dato": tuple(mana_dato[o])}
        return valori

    def _segue(self, e, o, applicati):
        """613.6: la parte di livello 7b di un effetto partito nel livello 4 continua sugli stessi oggetti anche se
        l'abilita' che lo genera sparisce nel frattempo (livello 6)."""
        return bool(e.statica and e.dati.get("segue") and (e.fonte.n, e.k, o.n) in applicati)

    def _livello_7(self, o, f, c, miei):
        for e in miei:                                                                             # 613.4b: impostano
            if e.livello == "7b": f, c = e.dati["p"], e.dati["t"]
        for e in miei:                                                                             # 613.4c: modificano
            if e.livello == "7c": f, c = f + self._quanto(e, "p"), c + self._quanto(e, "t")
        f += o.segnalini["+1/+1"] - o.segnalini["-1/-1"]                                           # 122.1a, 613.4c
        c += o.segnalini["+1/+1"] - o.segnalini["-1/-1"]
        for e in miei:                                                                             # 613.4d: scambiano
            if e.livello == "7d": f, c = c, f
        return f, c

    def _quanto(self, e, k):
        """«gets +1/+0 for each ...», «for every seven ...»: la quantita' di una statica si conta ogni volta che si
        applica (611.3a), di chi controlla la fonte."""
        v = e.dati.get(k, 0)
        if not isinstance(v, dict): return v
        spec, ctrl = v["conta"], e.fonte.controllore if e.fonte is not None else e.ctrl
        cim = self.giocatori[ctrl].cimitero
        if spec["tipo"] == "cimitero_tipi": n = sum(1 for x in cim if set(spec["tipi"]) & x.carta.tipi)
        elif spec["tipo"] == "cimitero_ogni": n = len(cim) // spec["ogni"]                          # 107.1a: «for every seven»
        elif spec["tipo"] == "controlli":                                                          # «for each artifact you control» (i tipi
            n = sum(1 for x in self.campo if x.controllore == ctrl and scelto(spec["sel"], x, e.fonte, ctrl))   # stampati: 613.8, niente giri)
        else: raise NonCoperto(f"611.3a: la quantita' {spec} di una statica non e' coperta")
        return v.get("molt", 1) * n

    def regola(self, nome, o):
        """613.11: un effetto sulle regole del gioco («can't be blocked») si applica dopo tutti gli altri, quindi con le
        caratteristiche finali: quelli delle magie e abilita' risolte (611.2) e le statiche delle fonti in campo con le
        abilita' che hanno adesso (604.2, 611.3a)."""
        for c in self.continui:
            if c.livello == "regola" and c.dati.get(nome) and self._applica_a(c, o) and filtri_ok(c.dati.get("filtri") or {}, o): return True
        for f in list(self.campo):
            for _, ab in self.abilita_di(f):
                if ab.get("tipo") != "statica": continue
                for d in ab["effetti"]:
                    if d["livello"] != "regola" or not d.get(nome): continue
                    if d.get("se") and not self.condizione_statica(d["se"], f): continue
                    if scelto(d.get("chi") or {}, o, f, f.controllore) and filtri_ok(d.get("filtri") or {}, o): return True
        return False

    def regola_valori(self, nome, o):
        """Come regola, ma coi valori («can't be blocked by creatures with power 2 or less»: [2]) delle statiche in campo."""
        out = [c.dati[nome] for c in self.continui if c.livello == "regola" and c.dati.get(nome) is not None and self._applica_a(c, o)]
        for f in list(self.campo):
            for _, ab in self.abilita_di(f):
                if ab.get("tipo") != "statica": continue
                for d in ab["effetti"]:
                    if d["livello"] != "regola" or d.get(nome) is None: continue
                    if d.get("se") and not self.condizione_statica(d["se"], f): continue
                    if scelto(d.get("chi") or {}, o, f, f.controllore): out.append(d[nome])
        return out

    # ------------------------------------------------------------------ le azioni di stato del passo 7
    def _muore_a_fedelta_zero(self, o):
        """704.5i, con l'eccezione scritta su una carta («Planeswalkers you control aren't put into their owners'
        graveyards for having 0 loyalty»)."""
        return not any(x.controllore == o.controllore and ab.get("tipo") == "eccezione" and ab.get("di") == "pw_fedelta_zero"
                       for x in self.campo for _, ab in self.abilita_di(x))

    def _stato_altre(self):
        out = [("annulla", o, "704.5q") for o in self.campo if o.segnalini["+1/+1"] and o.segnalini["-1/-1"]]
        per_n = {o.n: o for o in self.campo}
        for o in self.campo:                                                                       # 704.5m, 704.5n
            a = getattr(o, "attaccato_a", None)
            if "Aura" in o.carta.tipo and (a is None or a not in per_n or not self._puo_attaccare(o, per_n[a])):
                out.append(("aura", o, "704.5m"))
            elif "Equipment" in o.carta.tipo and a is not None and (a not in per_n or not self._puo_attaccare(o, per_n[a])):
                out.append(("stacca", o, "704.5n"))
        for z, _, o in self.tutti():                                                               # 704.5e, 723.3c
            if o.carta is not None and o.carta.car.get("copia_carta") and z not in ("pila", "campo"):
                if not o.carta.pedina: out.append(("cessa", o, "704.5e"))                          # 707.10a: la copia di una carta
                continue                                                                           # (diventata pedina: la toglie la 704.5d)
            if o.carta is None or "copia_di" not in o.carta.car or z == "pila": continue
            p = per_n.get(o.carta.car["copia_di"])
            if z == "esilio" and p is not None and getattr(p, "preparato", False): continue
            out.append(("cessa", o, "704.5e"))
        gruppi = defaultdict(list)                                                                 # 704.5j
        for o in self.campo:
            if "legendary" in o.carta.tipi: gruppi[(o.controllore, o.nome)].append(o)
        for (j, _), lst in gruppi.items():
            if len(lst) > 1: lst = [o for o in lst if not self.regola("senza_leggenda", o)]          # «the "legend rule" doesn't apply»
            if len(lst) > 1:
                tiene = self.scegli_leggenda(j, lst)
                out += [("leggenda", o, "704.5j") for o in lst if o is not tiene]
        p_ = getattr(self, "_partita", None)                                                       # 704.5s: la saga dopo l'ultimo capitolo
        for o in self.campo:
            if o.carta.car.get("capitoli") and o.segnalini["lore"] >= o.carta.car["capitoli"]:
                in_corso = p_ is not None and (any(getattr(x, "fonte", None) is o and (getattr(x, "ab", None) or {}).get("quando", {}).get("evento") == "capitolo"
                                                   for x in list(p_.in_attesa) + list(self.pila)))
                if not in_corso: out.append(("sacrifica_saga", o, "704.5s"))
        for f_ in STATO_SET: out += f_(self)                                                       # le azioni di stato dei set
        return out

    def scegli_leggenda(self, j, lst):
        """704.5j: sceglie il giocatore quale tenere; chi non sceglie tiene l'ultimo arrivato."""
        f = getattr(self, "scelta_leggenda", None)
        return f(j, lst) if f else max(lst, key=lambda o: o.ts)

    def _fai_stato(self, cosa, chi, regola):
        if cosa in FAI_STATO_SET: return FAI_STATO_SET[cosa](self, chi, regola)
        if cosa == "sacrifica_saga": self.sacrifica(chi, chi.controllore, causa=regola); return       # 704.5s
        if cosa in ("leggenda", "aura"):
            self.sposta(chi, "cimitero", causa=regola)
            return
        if cosa == "stacca":
            chi.attaccato_a = None
            self._versione += 1
            self._evento("staccata", carta=chi.carta, vecchio=chi.n, causa=regola)
            return
        if cosa != "annulla": return super()._fai_stato(cosa, chi, regola)
        n = min(chi.segnalini["+1/+1"], chi.segnalini["-1/-1"])                                    # 704.5q, 122.3
        self.togli_segnalini(chi, "+1/+1", n, causa=regola)
        self.togli_segnalini(chi, "-1/-1", n, causa=regola)


# ====================================================================== cosa fa scattare un innesco (603.2)
def _entra(p, e, f, q):
    if not (e.tipo == "zona" and e.a == "campo" and e.nuovo == f.n): return False
    return not q.get("stappata") or not f.tappato                                                 # «When this land enters untapped»


def _una_entra(p, e, f, q):
    o = p.t.oggetti.get(e.nuovo) if e.tipo == "zona" and e.a == "campo" else None
    return o is not None and scelto(q.get("chi") or {}, o, f)


def _muore(p, e, f, q): return e.tipo == "zona" and e.da == "campo" and e.a == "cimitero" and e.vecchio == f.n


def _muore_n(p, e, f, q):
    """700.4 (giro 13): un oggetto preciso muore (dal campo al cimitero)."""
    return e.tipo == "zona" and e.da == "campo" and e.a == "cimitero" and e.vecchio == q["n"]


def _lascia(p, e, f, q):
    """603.6c, 603.10a: «when this [permanent] leaves the battlefield»: guarda all'indietro, verso qualunque zona."""
    return e.tipo == "zona" and e.da == "campo" and e.vecchio == f.n


def _pesca_n(p, e, f, q):
    """121.1, 504.1: «whenever you draw a card» e «your second card each turn» (q["n"]: la n-esima pescata del turno, contando
    anche quella del passo di acquisizione; cercare non e' pescare)."""
    if not (e.tipo == "zona" and e.da == "grimorio" and e.a == "mano" and e.causa in ("121.1", "504.1") and e.giocatore == f.controllore):
        return False
    if q.get("n") is None: return True
    prima = [x for x in p._eventi_del_turno() if x.tipo == "zona" and x.da == "grimorio" and x.a == "mano"
             and x.causa in ("121.1", "504.1") and x.giocatore == e.giocatore and x.n <= e.n]
    return len(prima) == q["n"]


def _diventa_tappata(p, e, f, q):
    """701.26a: «whenever this creature becomes tapped» (tapparsi per attaccare, per un costo o per un effetto)."""
    return e.tipo == "tappa" and e.vecchio == f.n


def _dilemma(p, e, f, q):
    """700.17: «whenever you face a dilemma»: hai scelto uno o piu' modi di una magia o di un'abilita'."""
    return e.tipo == "dilemma" and e.giocatore == f.controllore


def _tua_danno_giocatore(p, e, f, q):
    """510.3a: «whenever a creature you control deals combat damage to a player» (una volta per creatura)."""
    if not (e.tipo == "danno" and e.nuovo is None and e.causa == "510.2"): return False
    x = p.t.oggetti.get(e.vecchio)
    if x is None or x.controllore != f.controllore or "creature" not in x.carta.tipi: return False
    if (q.get("chi") or {}).get("con_parola") and q["chi"]["con_parola"] not in parole(x): return False   # «with flying»
    if (q.get("chi") or {}).get("con_segnalini") and not any(v > 0 for v in x.segnalini.values()): return False   # «with a counter on it»
    return True


def _attaccata_danno_giocatore(p, e, f, q):
    """510.3a, 301.5: «whenever equipped creature deals combat damage to a player»."""
    return e.tipo == "danno" and e.nuovo is None and e.causa == "510.2" and e.vecchio == getattr(f, "attaccato_a", None)


def _i_dalla_mano_in_campo(p, d, chi, ctrl, fonte, ogg):
    """«put a land card from your hand onto the battlefield tapped» (305.4: non e' giocare una terra): chi controlla sceglie."""
    tipi_ = set(d["tipi"])
    if "permanent" in tipi_: tipi_ |= {"artifact", "battle", "creature", "enchantment", "land", "planeswalker"}   # 110.4
    mv_ = d.get("mv_max")
    if mv_ == "X": mv_ = getattr(ogg, "x", 0) or 0                                                  # 107.3m: la X della magia
    cand = [o for o in p.t.giocatori[ctrl].mano if tipi_ & o.carta.tipi
            and (not d.get("sottotipo") or ha_sottotipo(o, d["sottotipo"]))
            and (mv_ is None or M.valore(o.carta.car.get("costo") or "") <= mv_)]                   # 202.3 (15 nov 2026)
    if not cand: return False
    x = _scelta(p, ctrl, "dalla_mano_in_campo", cand, predefinita=cand[0])
    if x not in cand: x = cand[0]
    n = p.t.sposta(x, "campo", chi=ctrl, causa="305.4")
    if n is not None and d.get("tappata"): n.tappato = True
    return n is not None


def _i_dal_cimitero_in_mano(p, d, chi, ctrl, fonte, ogg):
    """«return a land card from your graveyard to your hand»: chi controlla sceglie (non e' un bersaglio, 115.10)."""
    cand = [o for o in p.t.giocatori[ctrl].cimitero if set(d["tipi"]) & o.carta.tipi]
    if not cand: return False
    x = _scelta(p, ctrl, "dal_cimitero_in_mano", cand, predefinita=cand[0])
    if x not in cand: x = cand[0]
    return p.t.sposta(x, "mano", causa="400.7") is not None


def _i_paga_vite(p, d, chi, ctrl, fonte, ogg):
    """119.4: «pay N life»: solo con abbastanza vite. -> True se pagate."""
    return bool(p.t.paga_vite(ctrl, d["n"], causa="119.4"))


def _capitolo(p, e, f, q):
    """715.2b: «When one or more lore counters are put onto this Saga, if the number of lore counters on it was less than
    N and became at least N»."""
    return (e.tipo == "segnalini" and e.a == "lore" and e.vecchio == f.n and e.nuovo is not None
            and e.nuovo - (e.quanto or 0) < q["n"] <= e.nuovo)


def _soglia_segnalini(p, e, f, q):
    """122.1, 603.2: «When the fourth plan counter is put on this enchantment»: i segnalini di quel tipo passano da meno di N a
    N o piu' con questo evento (come i capitoli, 715.2b)."""
    return (e.tipo == "segnalini" and e.a == q["tipo"] and e.vecchio == f.n and e.nuovo is not None
            and e.nuovo - (e.quanto or 0) < q["n"] <= e.nuovo)


def _una_muore(p, e, f, q):
    o = p.t.oggetti.get(e.vecchio) if e.tipo == "zona" and e.da == "campo" and e.a == "cimitero" else None
    return o is not None and scelto(q.get("chi") or {}, o, f)


def _inizio_fase(p, e, f, q):
    """505.1a: «at the beginning of your first main phase» (la fase principale non ha passi: l'evento ha passo vuoto)."""
    chi = f.controllore if f.controllore is not None else f.proprietario
    return e.tipo == "passo" and e.da == q["fase"] and not e.a and (q.get("di") != "tuo" or e.giocatore == chi)


def _inizio_passo(p, e, f, q):
    chi = f.controllore if f.controllore is not None else f.proprietario                              # 603.3a: dal cimitero, il proprietario
    if q.get("di") == "avversario" and e.giocatore == chi: return False                            # «each opponent's draw step»
    return e.tipo == "passo" and e.a == q["passo"] and (q.get("di") != "tuo" or e.giocatore == chi)


def _attacca(p, e, f, q):
    if not (e.tipo == "attacca" and e.vecchio == f.n): return False
    sel = q.get("se_controlli")                                                                    # «attacks while you control ...»
    return sel is None or any(o.controllore == f.controllore and scelto(sel, o, f) for o in p.t.campo)


def _attaccata_attacca(p, e, f, q):
    """«Whenever equipped creature attacks» (301.5): la creatura a cui la fonte e' attaccata."""
    return e.tipo == "attacca" and getattr(f, "attaccato_a", None) == e.vecchio


def _lasciano_cimitero(p, e, f, q):
    """«Whenever one or more cards leave your graveyard» (una volta per azione)."""
    if q.get("nel_tuo_turno") and p.attivo != f.controllore: return False                       # «during your turn»
    return e.tipo == "zona" and e.da == "cimitero" and e.carta is not None and e.carta.proprietario == f.controllore


def _ciclata_questa(p, e, f, q):
    """702.29c: «When you cycle this card»: scartata per pagare il cycling; si innesca dalla zona in cui finisce."""
    return e.tipo == "zona" and e.da == "mano" and e.a == "cimitero" and e.causa == "702.29a" and e.nuovo == f.n


def _lanci(p, e, f, q):
    """601.2i: «whenever you cast [a noncreature spell]»: la magia lanciata, coi tipi chiesti (o senza quelli esclusi)."""
    if e.tipo != "lanciata" or e.carta is None: return False
    chi = q.get("di", "tu")
    if (chi == "tu" and e.giocatore != f.controllore) or (chi == "avversario" and e.giocatore == f.controllore): return False
    tipi = e.carta.tipi
    if q.get("tipi") and not set(q["tipi"]) & tipi: return False
    if q.get("non_tipi") and set(q["non_tipi"]) & tipi: return False
    if q.get("multicolore") and len(set(M.colori(e.carta.car.get("costo") or ""))) < 2: return False   # 105.2c
    if q.get("colori") and not set(q["colori"]) & set(M.colori(e.carta.car.get("costo") or "")): return False   # 105.2 (giro 8)
    if q.get("incolore") and M.colori(e.carta.car.get("costo") or ""): return False                 # 105.2c (giro 10)
    if q.get("tipo_o_sottotipo"):                                                                  # «an artifact or Lesson spell»
        to_ = q["tipo_o_sottotipo"]
        if not (set(to_["tipi"]) & tipi or to_["sottotipo"] in (e.carta.tipo or "").split("—")[-1].split()): return False
    if q.get("sottotipo") and not (e.carta.tipo and q["sottotipo"] in e.carta.tipo.split("—")[-1].split()): return False   # 205.3
    if q.get("con_x") and "{X}" not in (e.carta.car.get("costo") or ""): return False               # 107.3
    if q.get("mv_max") is not None:                                                                # 202.3, 202.3e: in pila la X conta
        m_ = p.t.oggetti.get(e.vecchio)
        if M.valore(e.carta.car.get("costo") or "", getattr(m_, "x", 0) or 0) > q["mv_max"]: return False
    if q.get("bersaglia_avversario"):                                                              # «a spell that targets an opponent or ...»
        if not any((_e_giocatore(x) and x != f.controllore) or (not _e_giocatore(x) and x.vivo and x.zona == "campo"
                   and "creature" in x.carta.tipi and x.controllore != f.controllore) for g in getattr(p, "_bersagli_lancio", None) or [] for x in g):
            return False
    if q.get("preparata") and e.carta.car.get("copia_di") is None: return False                    # 723.3c: la copia di una magia preparata
    if q.get("bersaglia_creatura"):                                                                # «a spell that targets a creature [you control]»
        tua = q["bersaglia_creatura"] == "tua"
        if not any(not _e_giocatore(x) and x.vivo and x.zona == "campo" and "creature" in x.carta.tipi and (not tua or x.controllore == f.controllore)
                   for g in getattr(p, "_bersagli_lancio", None) or [] for x in g): return False
    if q.get("equip_o_bersaglia_tua"):                                                             # 601.2c: i bersagli scelti lanciando
        equip = "Equipment" in e.carta.tipo.split("—")[-1].split()
        bers = any(not _e_giocatore(x) and x.vivo and x.zona == "campo" and "creature" in x.carta.tipi and x.controllore == f.controllore
                   for g in getattr(p, "_bersagli_lancio", None) or [] for x in g)
        if not (equip or bers): return False
    if q.get("nel_turno_di") == "avversario" and p.attivo == f.controllore: return False            # «during an opponent's turn»
    if q.get("mv_min") is not None:                                                                # 202.3: «mana value N or greater»
        m_ = p.t.oggetti.get(e.vecchio)
        if M.valore(e.carta.car.get("costo") or "", getattr(m_, "x", 0) or 0) < q["mv_min"]: return False
    if q.get("n_del_turno"):                                                                       # «your second spell each turn»
        tutte = [x for x in p._eventi_del_turno() if x.tipo == "lanciata" and x.giocatore == e.giocatore and x.n <= e.n]
        if len(tutte) != q["n_del_turno"]: return False
    if q.get("primo_del_turno"):                                                                   # «your first ... each turn»
        simili = [x for x in p._eventi_del_turno() if x.tipo == "lanciata" and x.giocatore == e.giocatore and x.carta is not None
                  and not (q.get("non_tipi") and set(q["non_tipi"]) & x.carta.tipi) and x.n <= e.n]
        if len(simili) != 1: return False
    return True


def _lanci_questa(p, e, f, q):
    """601.2i, 113.6k: «When you cast this spell»: la magia stessa, in pila, quando diventa lanciata (la fonte e' la magia:
    la mette `_fonti` solo per l'evento del suo lancio)."""
    return e.tipo == "lanciata" and e.vecchio == f.n


def _bersagliato(p, e, f, q):
    """702.21a: «becomes the target of a spell or ability an opponent controls»."""
    return e.tipo == "bersagliato" and e.vecchio == f.n and e.giocatore != f.controllore


def _danno_a_giocatore(p, e, f, q):
    """510.3a: «deals combat damage to a player»."""
    return e.tipo == "danno" and e.vecchio == f.n and e.nuovo is None and e.causa == "510.2"


def _segnalini_fedelta(p, e, f, q):
    """«Whenever you put one or more loyalty counters on a planeswalker»: un evento di segnalini fedelta' messi da chi
    controlla la fonte (122.6: mettere segnalini)."""
    if e.tipo != "segnalini" or e.a != "fedelta" or (e.quanto or 0) <= 0: return False
    o = p.t.oggetti.get(e.vecchio)
    return o is not None and o.controllore == f.controllore and "planeswalker" in o.carta.tipi


def _scarto(p, e, f, q):
    """701.9a: «whenever a player discards one or more cards» (514.1: anche scartare nella pulizia); «you discard»: solo tu."""
    if q.get("di") == "tu" and e.giocatore != f.controllore: return False
    if q.get("di") == "avversario" and e.giocatore == f.controllore: return False                 # «an opponent discards»
    return e.tipo == "zona" and e.da == "mano" and e.a == "cimitero" and e.causa in SCARTI


def _attivi_fedelta(p, e, f, q):
    """606: «whenever you activate a loyalty ability» (con «removed two or more»: il costo pagato)."""
    if e.tipo != "attivata" or e.a != "fedelta": return False
    if (e.giocatore == f.controllore) != (q.get("di", "tu") == "tu"): return False
    return q.get("tolti_almeno") is None or -(e.nuovo or 0) >= q["tolti_almeno"]


def _danno_non_combattimento(p, e, f, q):
    """«whenever one or more opponents are dealt noncombat damage» (120.2b, non 510.2)."""
    return e.tipo == "danno" and e.nuovo is None and e.causa != "510.2" and e.giocatore != f.controllore


def _una_attacca_sola(p, e, f, q):
    """506.5, 508.1m: «whenever a creature you control attacks a player alone»: l'unica creatura dichiarata, contro un
    giocatore («attacks alone»: contro chiunque)."""
    o = p.t.oggetti.get(e.vecchio) if e.tipo == "attacca" else None
    return (o is not None and o.controllore == f.controllore and p.dichiarati == 1
            and (q.get("qualsiasi") or isinstance(p.attaccanti.get(o), numbers.Integral)))


def _attacchi_tu(p, e, f, q):
    """508.1m: «whenever you attack»: quando chi controlla la fonte dichiara una o piu' creature attaccanti, una volta
    per dichiarazione (con una_per_azione); «while creatures you control have total power N or greater»."""
    if not (e.tipo == "attacca" and e.giocatore == f.controllore): return False
    if q.get("min_attaccanti") and (getattr(p, "dichiarati", 0) or 0) < q["min_attaccanti"]: return False   # 508.1m (giro 11)
    n = q.get("forza_totale_min")
    return n is None or sum(max(0, forza(o)) for o in p.t.campo if o.controllore == f.controllore and "creature" in o.carta.tipi) >= n


def _una_attacca(p, e, f, q):
    """508.1m: «whenever a creature you control attacks»."""
    o = p.t.oggetti.get(e.vecchio) if e.tipo == "attacca" else None
    if o is not None and q.get("contro_giocatore") and not isinstance(p.attaccanti.get(o), numbers.Integral): return False   # (giro 11)
    return o is not None and o.controllore == f.controllore and (not q.get("chi") or scelto(q["chi"], o, f))   # «a Goblin you control»


def _guarda(p, e, f, q):
    """701.22d, 701.25d: «whenever you scry or surveil», dopo che e' finito."""
    return e.tipo == "guarda" and e.giocatore == f.controllore and e.a in q.get("cosa", ("scry", "surveil"))


def _guadagni(p, e, f, q):
    if not (e.tipo == "vite" and (e.quanto or 0) > 0 and e.giocatore == f.controllore): return False
    if q.get("primo_del_turno"):                                                                   # «for the first time each turn»
        primo = next((x for x in p.t.eventi_del_turno() if x.tipo == "vite" and (x.quanto or 0) > 0 and x.giocatore == f.controllore), None)
        return primo is e
    return True


def _trasforma_in(p, e, f, q):
    """701.27f: «whenever this creature transforms into ~»: l'abilita' e' della faccia che e' in su dopo."""
    return e.tipo == "trasforma" and e.vecchio == f.n


def _sacrifichi(p, e, f, q):
    """701.21a: «whenever you sacrifice another permanent»: si sacrifica solo cio' che si controlla."""
    if not (e.tipo == "zona" and e.da == "campo" and str(e.causa).startswith("701.21")): return False
    o = p.t.oggetti.get(e.vecchio)
    if o is not None and q.get("chi") and not scelto(q["chi"], o, f, f.controllore): return False   # «you sacrifice an artifact» (giro 10)
    return o is not None and o.controllore == f.controllore and not (q.get("altre") and e.vecchio == f.n)


def _avversari_danno_combattimento(p, e, f, q):
    """«When one or more of your opponents are dealt combat damage during your turn» (510.2: il danno di un passo
    arriva insieme, l'innesco una volta per passo)."""
    return (e.tipo == "danno" and e.nuovo is None and e.causa == "510.2" and e.giocatore != f.controllore
            and p.attivo == f.controllore)


def _blocca(p, e, f, q):
    """509.3a: «Whenever a creature an opponent controls with power or toughness 1 or less blocks»: si guarda quando
    blocca."""
    if e.tipo != "blocca": return False
    o = p.t.oggetti.get(e.vecchio)
    if o is None: return False
    if q.get("di") == "avversario" and o.controllore == f.controllore: return False
    if q.get("fc_max") is not None and min(forza(o), costituzione(o)) > q["fc_max"]: return False
    return True


def _attacca_avversario(p, e, f, q):
    """«whenever one or more creatures attack one of your opponents»: si attacca il giocatore (non un suo planeswalker)."""
    o = p.t.oggetti.get(e.vecchio) if e.tipo == "attacca" else None
    b = p.attaccanti.get(o) if o is not None else None
    return isinstance(b, numbers.Integral) and b != q["ctrl"]


def _attacca_te_o_pw(p, e, f, q):
    """«whenever a creature attacks you or a planeswalker you control»."""
    o = p.t.oggetti.get(e.vecchio) if e.tipo == "attacca" else None
    if o is None or o not in p.attaccanti: return False
    b = p.attaccanti[o]
    return b == q["ctrl"] if isinstance(b, numbers.Integral) else (b.controllore == q["ctrl"] and "planeswalker" in b.carta.tipi)


def _danno_ricevuto(p, e, f, q):
    """«Whenever this creature is dealt damage»."""
    return e.tipo == "danno" and e.nuovo == f.n


def _attaccata_danno(p, e, f, q):
    """«Whenever enchanted creature is dealt damage» (303.4): la creatura a cui la fonte e' attaccata."""
    return e.tipo == "danno" and e.nuovo is not None and getattr(f, "attaccato_a", None) == e.nuovo


def _attaccata_muore(p, e, f, q):
    """«When enchanted creature dies»: la creatura a cui l'aura era attaccata subito prima (603.10a, 603.6c)."""
    return e.tipo == "zona" and e.da == "campo" and e.a == "cimitero" and e.vecchio is not None and getattr(f, "attaccato_a", None) == e.vecchio


SCARTI = ("701.9a", "514.1", "702.29a")


def _scartata_questa(p, e, f, q):
    """«When you discard this card» (113.6k: si innesca dalla zona in cui la carta finisce): la carta nuova e' la fonte."""
    return e.tipo == "zona" and e.da == "mano" and e.a == "cimitero" and e.causa in SCARTI and e.nuovo == f.n


def _ha_inneschi(o):
    """Le fonti possibili di un innesco: chi ne ha di stampati, o chi puo' riceverne da un effetto (613.1f: un'abilita'
    data, come quella di un equipaggiamento). Le carte che danno abilita' innescate le segna il tavolo."""
    if any(ab.get("tipo") == "innescata" for ab in (o.carta.car.get("abilita") or ())): return True
    t = getattr(o, "tavolo", None)
    return bool(t is not None and getattr(t, "da_innescate", False))


TIPI_EVENTO = {"zona", "passo", "attacca", "lanciata", "vite", "bersagliato", "danno", "guarda", "segnalini", "attivata", "blocca",
               "tappa", "dilemma"}                                                               # 14 nov 2026: «becomes tapped», 700.17

# evento -> (regola, prova, guarda all'indietro)
QUANDO = {"entra": ("603.6a", _entra, False), "una_entra": ("603.6a", _una_entra, False),
          "muore": ("603.6c", _muore, True), "muore_n": ("603.6c", _muore_n, True), "una_muore": ("603.10a", _una_muore, True),
          "capitolo": ("715.2b", _capitolo, False), "soglia_segnalini": ("603.2", _soglia_segnalini, False), "attaccata_danno_giocatore": ("510.3a", _attaccata_danno_giocatore, False), "tua_danno_giocatore": ("510.3a", _tua_danno_giocatore, False), "dilemma": ("700.17", _dilemma, False), "lascia": ("603.6c", _lascia, True), "attaccata_attacca": ("508.1m", _attaccata_attacca, False),
          "lasciano_cimitero": ("603.2", _lasciano_cimitero, False), "ciclata_questa": ("702.29c", _ciclata_questa, False), "pesca_n": ("121.1", _pesca_n, False), "diventa_tappata": ("701.26a", _diventa_tappata, False),
          "inizio_passo": ("603.2b", _inizio_passo, False), "attacca": ("508.1m", _attacca, False),
          "lanci": ("601.2i", _lanci, False), "lanci_questa": ("601.2i", _lanci_questa, False), "guadagni_vita": ("119.3", _guadagni, False), "sacrifichi": ("701.21a", _sacrifichi, True), "trasforma_in": ("701.27f", _trasforma_in, False),
          "bersagliato": ("702.21a", _bersagliato, False), "danno_a_giocatore": ("510.3a", _danno_a_giocatore, False),
          "guarda": ("701.25d", _guarda, False), "segnalini_fedelta": ("122.6", _segnalini_fedelta, False),
          "scarto": ("701.9a", _scarto, False), "attivi_fedelta": ("606.4", _attivi_fedelta, False),
          "danno_non_combattimento": ("120.2b", _danno_non_combattimento, False), "una_attacca": ("508.1m", _una_attacca, False),
          "attaccata_muore": ("603.6c", _attaccata_muore, True), "scartata_questa": ("113.6k", _scartata_questa, False),
          "avversari_danno_combattimento": ("510.3a", _avversari_danno_combattimento, False), "blocca": ("509.3a", _blocca, False),
          "una_attacca_sola": ("506.5", _una_attacca_sola, False), "attacchi_tu": ("508.1m", _attacchi_tu, False), "inizio_fase": ("505.1a", _inizio_fase, False),
          "danno_ricevuto": ("120.3e", _danno_ricevuto, False), "attaccata_danno": ("120.3e", _attaccata_danno, False),
          "attacca_avversario": ("508.1m", _attacca_avversario, False), "attacca_te_o_pw": ("508.1m", _attacca_te_o_pw, False)}


# ====================================================================== le istruzioni (608.2c)
def _i_pesca(p, d, chi, ctrl, fonte, ogg):
    n = d.get("n", 1)
    if n == "X": n = getattr(ogg, "x", 0) or 0                                                     # 107.3a (15 nov 2026): «draw X cards»
    if d.get("se_non_dalla_mano") and not getattr(ogg, "dalla_mano", True): n = d["se_non_dalla_mano"]   # «instead»
    p._pescate_qui = sum(len(p.t.pesca(j, n, causa="121.1") or []) for j in chi)                      # «drawn this way»


def _i_guadagna(p, d, chi, ctrl, fonte, ogg):
    n = (getattr(ogg, "x", 0) or 0) if d["n"] == "X" else d["n"]                                  # 107.3a: la X della magia
    for j in chi: p.t.guadagna(j, n, causa="119.3")


def _i_perde(p, d, chi, ctrl, fonte, ogg):
    n = (getattr(ogg, "x", 0) or 0) if d["n"] == "X" else d["n"]                                  # 107.3a
    for j in chi: p.t.perdi(j, n, causa="119.3")


def _i_danno(p, d, chi, ctrl, fonte, ogg):
    """120.2b: la magia o l'abilita' dice chi infligge il danno: «this spell» la magia, «this creature» la fonte."""
    n = ogg.x if d["n"] == "X" else d["n"]                                                         # 107.3a, 107.3m
    if d.get("da") == "evento":                                                                    # «that creature deals»
        fonte = p.t.oggetti.get(getattr(getattr(ogg, "evento", None), "vecchio", None))
        if fonte is None: return
    prima_ = {}
    for x in chi:                                                                                  # 120.10: com'era prima del danno
        if _e_giocatore(x) or not x.vivo: continue
        soglie = []
        if "creature" in x.carta.tipi: soglie.append(max(0, costituzione(x) - x.danno))           # 120.6: il danno letale
        if "planeswalker" in x.carta.tipi: soglie.append(x.segnalini["fedelta"])
        if soglie: prima_[x.n] = soglie
    k = len(p.t.eventi)
    p.t.infliggi(fonte, [(x, n) for x in chi], causa="120.2b")
    inflitto = Counter()
    for e_ in p.t.eventi[k:]:
        if e_.tipo == "danno" and e_.nuovo in prima_: inflitto[e_.nuovo] += e_.quanto
    p._eccesso = (ogg, max([max(0, inflitto[n_] - s) for n_, ss in prima_.items() for s in ss] or [0]))


def _i_distruggi(p, d, chi, ctrl, fonte, ogg):
    for x in chi:
        if "indestructible" in parole(x): continue                                                  # 702.12b
        p.t.distruggi(x, causa="701.8a")


def _i_esilia(p, d, chi, ctrl, fonte, ogg):
    via = [p.t.esilia(x, causa="701.13a") for x in chi]
    p._esiliate = (ogg, [x for x in via if x is not None])                                         # «that card»
    return bool(p._esiliate[1])


def _i_ritorna_esiliata(p, d, chi, ctrl, fonte, ogg):
    """«exile ..., then return that card to the battlefield under its owner's control»: la carta in esilio (400.7: e'
    un oggetto nuovo), sotto il proprietario."""
    di, via = getattr(p, "_esiliate", (None, []))
    if di is not ogg: raise NonCoperto("608.2c: «that card» senza un esilio di questa abilita'")
    if d.get("ritardata"):                                                                         # 603.7a-c: «at the beginning of the next
        ns = [x.n for x in via if x.vivo and x.zona == "esilio"]                                   # end step»: la ritardata ricorda le carte
        if ns:
            p.ritardate.append({"ab": {"tipo": "innescata", "una_volta": True, "quando": {"evento": "inizio_passo", "passo": "finale"},
                                       "fa": [{"fa": "rimetti_esiliate", "chi": "ricordati_esilio"}], "ricordati": ns},
                                "ctrl": ctrl, "fonte": ogg, "fino": "sempre", "dopo": p.t.eventi[-1].n, "turno": p.t.turno_numero})
        return
    for x in via:
        if not (x.vivo and x.zona == "esilio"): continue
        if d.get("segnalini"): x._entra_segnalini = dict(d["segnalini"])                            # 614.1c: «with a +1/+1 counter on it»
        if d.get("trasformata"):                                                                   # 712.11a: «transformed»; una carta
            r_ = x._carta.retro()                                                                  # che non ha due facce resta dov'e'
            if r_ is None or r_.tipi & {"instant", "sorcery"}: continue                           # (712.11b)
            x._entra_retro = True
        n_ = p.t.metti_in_campo(x, chi=ctrl if d.get("tuo") else x.proprietario, causa="400.7")
        if d.get("tappata") and n_ is not None: n_.tappato = True                                 # «tapped» (15 nov 2026)


def _i_prossima_incontrastabile(p, d, chi, ctrl, fonte, ogg):
    """«The next spell you cast this turn can't be countered» (101.2)."""
    p.incontrastabile[(ctrl, p.t.turno_numero)] = True


def _i_rimbalza(p, d, chi, ctrl, fonte, ogg):
    for x in chi: p.t.rimbalza(x, causa="400.3")


def _i_tappa(p, d, chi, ctrl, fonte, ogg):
    for x in chi: p.t.tappa(x)


def _i_stappa(p, d, chi, ctrl, fonte, ogg):
    for x in chi: p.t.stappa(x)


def _i_trama(p, d, chi, ctrl, fonte, ogg):
    """701.50a-b, 701.50f: «it connives»: chi la controlla pesca una carta, poi ne scarta una; se e' una carta non terra,
    un segnalino +1/+1 sul permanente (se e' ancora in campo; 701.50b: chi la controllava)."""
    for x in chi:
        if _e_giocatore(x): continue
        j = x.controllore
        if j is None: continue
        p.t.pesca(j, 1, causa="701.50a")
        mano = list(p.t.giocatori[j].mano)
        if not mano: continue
        via = _scelta(p, j, "scarta_effetto", mano, 1, predefinita=mano[-1:])
        via = list(via) if via is not None else []
        if len(via) != 1 or via[0] not in mano: via = mano[-1:]
        terra = "land" in via[0].carta.tipi
        p.t.scarta(via[0], causa="701.9a")
        if not terra and x.vivo and x.zona == "campo": p.t.metti_segnalini(x, "+1/+1", 1)


def _i_gira_faccia(p, d, chi, ctrl, fonte, ogg):
    """701.27a: gira il permanente sull'altra faccia; 712.15, 701.27c: e' lo stesso oggetto (segnalini, danno, effetti restano).
    701.27d: solo una carta a due facce; 701.27e: non verso una faccia istantaneo o stregoneria; 701.27g: un'abilita' (non
    ritardata) del permanente lo gira solo se non si e' girato da quando e' andata in pila."""
    for x in chi:
        if _e_giocatore(x) or not (x.vivo and x.zona == "campo"): continue
        retro = x._carta.car.get("retro")
        if not retro: continue                                                                     # 701.27d
        if isinstance(ogg, Abilita) and ogg.fonte is x and not ogg.ab.get("ricordati") and getattr(x, "_girata_n", -1) > ogg.n: continue   # 701.27g
        if x.__dict__.get("_retro") is not None: x._retro = None                                  # torna davanti
        else:
            r = x._carta.retro()
            if r.tipi & {"instant", "sorcery"}: continue                                           # 701.27e
            x._retro = r
        x._girata_n = next(p.t._oggetti)
        p.t._versione += 1
        p.t._evento("trasforma", carta=x.carta, vecchio=x.n, giocatore=x.controllore, causa="701.27a")


def _i_segnalini(p, d, chi, ctrl, fonte, ogg):
    for x in chi: p.t.metti_segnalini(x, d["tipo"], d.get("n", 1))


def _continuo(livello, dati):
    def f(p, d, chi, ctrl, fonte, ogg):
        oggetti = [x for x in chi if not _e_giocatore(x) and x.vivo and x.zona == "campo"]
        insieme = p._insieme_fissato(d, oggetti)
        p.t.aggiungi_continuo(livello, dati(d), chi=insieme, sel=None if insieme is not None else d.get("chi"),
                              fonte=fonte, durata=d.get("durata"), ctrl=ctrl)
    return f


def _i_moltiplica_fc(p, d, chi, ctrl, fonte, ogg):
    """701.10b-c: raddoppiare (triplicare) forza e costituzione: +X/+Y con X e Y contati alla risoluzione, (volte-1) volte;
    un valore negativo diventa -X (701.10c). Insieme fissato (611.2c)."""
    k = d.get("volte", 2) - 1
    for x in chi:
        if _e_giocatore(x) or not (x.vivo and x.zona == "campo"): continue
        f_, c_ = forza(x), costituzione(x)
        p.t.aggiungi_continuo("7c", {"p": k * f_, "t": k * c_}, chi=frozenset({x.n}), sel=None, fonte=fonte, durata=d.get("durata"), ctrl=ctrl)


def _i_parola_scelta(p, d, chi, ctrl, fonte, ogg):
    """«gains your choice of trample, hexproof, or haste until end of turn»: chi controlla l'abilita' sceglie alla
    risoluzione (608.2d), poi l'effetto e' quello di una parola data (613.1f)."""
    opzioni = list(d["scelta"])
    x = _scelta(p, ctrl, "parola", opzioni, predefinita=opzioni[0])
    _continuo("6", _parole_date)(p, dict(d, parole=[x if x in opzioni else opzioni[0]]), chi, ctrl, fonte, ogg)


def _parole_date(d):
    altre = set(d["parole"]) - set(PAROLE_7)
    if altre: raise NonCoperto(f"702: le parole {sorted(altre)} date da un effetto non sono coperte")
    return {"dai": list(d["parole"])}


def _i_contrasta(p, d, chi, ctrl, fonte, ogg):
    for x in chi: p.contrasta(x)


def _i_contrasta_salvo(p, d, chi, ctrl, fonte, ogg):
    """702.21a e «unless its controller pays»: chi controlla la magia o abilita' puo' pagare (608.2g: con le abilita'
    di mana); se non paga, si contrasta."""
    for x in chi:
        if not (x.vivo and x.zona == "pila"): continue
        j = x.controllore
        costo = d["costo"]
        g = (p.chi or {}).get(j)
        if isinstance(costo, dict) and set(costo) == {"sacrifica"}:                                # «Ward—Sacrifice three permanents»
            n = costo["sacrifica"]                                                                 # 701.21a: solo permanenti suoi;
            cand = [o for o in p.t.campo if o.controllore == j]                                    # 118.3: senza tutti, non si paga
            vuole = len(cand) >= n and (g.paga(p, j, costo, x) if hasattr(g, "paga") else True)
            if vuole:
                sc = list(g.sacrifica_ward(p, j, cand, n)) if hasattr(g, "sacrifica_ward") else cand[:n]
                if len(sc) != n or len(set(map(id, sc))) != n or any(o not in cand for o in sc): sc = cand[:n]
                with p.t.insieme():                                                                # 601.2h: il costo, tutto insieme
                    for o in sc: p.t.sacrifica(o, j, causa="701.21a")
                p.t._evento("pagato", vecchio=x.n, giocatore=j, a="sacrifica", quanto=n, causa="702.21a")
            else: p.contrasta(x, causa="701.6a")
            continue
        if isinstance(costo, dict) and set(costo) == {"vite"}:                                     # «Ward—Pay N life» (119.4)
            n = costo["vite"]
            vuole = p.t.giocatori[j].vite >= n and (g.paga(p, j, costo, x) if hasattr(g, "paga") else True)
            if vuole:
                p.t.paga_vite(j, n, causa="119.4")
                p.t._evento("pagato", vecchio=x.n, giocatore=j, a="vite", quanto=n, causa="702.21a")
            else: p.contrasta(x, causa="701.6a")
            continue
        if isinstance(costo, dict):                                                                # «Ward—Discard a card»
            if set(costo) != {"scarta"}: raise NonCoperto(f"702.21a: il costo del ward {costo} non e' coperto")
            mano = list(p.t.giocatori[j].mano)
            vuole = bool(mano) and (g.paga(p, j, costo, x) if hasattr(g, "paga") else True)
            if vuole:
                c_ = g.scarta_costo(p, j, mano) if hasattr(g, "scarta_costo") else mano[-1]
                p.t.scarta(c_ if c_ in mano else mano[-1], causa="701.9a")
                p.t._evento("pagato", vecchio=x.n, giocatore=j, a="scarta", causa="702.21a")
            else: p.contrasta(x, causa="701.6a")
            continue
        vuole = g.paga(p, j, costo, x) if hasattr(g, "paga") else True
        with p.pagando(("abilita'",)):                                                            # 106.6: un costo, non una magia
            scelto = p._scegli_pagamento(j, costo) if vuole else None
            if scelto is not None: p._paga(j, x, costo, 0, scelto)
        if scelto is not None:
            p.pagati_abilita.append((costo, scelto[0], 0, scelto[2], scelto[3]))
            p.t._evento("pagato", vecchio=x.n, giocatore=j, a=costo, causa="702.21a")
        else: p.contrasta(x, causa="701.6a")


def _scelta(p, j, nome, *arg, predefinita):
    g = (p.chi or {}).get(j)
    f = getattr(g, nome, None)
    return f(p, j, *arg) if f else predefinita


def _i_surveil(p, d, chi, ctrl, fonte, ogg):
    """701.25a; 701.25c: surveil 0 non e' un evento. L'evento «guarda» viene dopo (701.25d)."""
    via = []
    for j in chi:
        if d["n"] <= 0: continue
        via += p.t.surveil(j, d["n"], lambda viste, j=j: _scelta(p, j, "surveil", viste, predefinita=(viste, []))) or []
        p.t._evento("guarda", giocatore=j, a="surveil", quanto=d["n"], causa="701.25a")
    p._sorvegliate = (ogg, via)                           # «into your graveyard this way»


def _i_scry(p, d, chi, ctrl, fonte, ogg):
    """701.22a; 701.22b; l'evento dopo (701.22d)."""
    for j in chi:
        if d["n"] <= 0: continue
        p.t.scry(j, d["n"], lambda viste, j=j: _scelta(p, j, "scry", viste, predefinita=(viste, [])))
        p.t._evento("guarda", giocatore=j, a="scry", quanto=d["n"], causa="701.22a")


def _i_macina(p, d, chi, ctrl, fonte, ogg):
    via = [x for j in chi for x in p.t.macina(j, d["n"], causa="701.17a")]
    p._macinate = (ogg, via)                              # «from among them»: le carte macinate da questa istruzione
    return bool(via)


PERMANENTI = ["artifact", "battle", "creature", "enchantment", "land", "planeswalker"]               # 110.4


def _i_prendi_tra_macinate(p, d, chi, ctrl, fonte, ogg):
    """«put a permanent card from among them into your hand»: una delle carte appena macinate, ancora nel cimitero
    (400.7: una carta che se n'e' andata e' un oggetto nuovo), scelta da chi controlla la magia (608.2d)."""
    di, via = getattr(p, "_macinate", (None, []))
    if di is not ogg: raise NonCoperto("608.2c: «from among them» senza carte macinate da questa magia o abilita'")
    cand = [x for x in via if x.vivo and x.zona == "cimitero" and set(d["tipi"]) & x.carta.tipi]
    if not cand: return False
    x = _scelta(p, ctrl, "prendi", cand, predefinita=cand[0])
    p.t.sposta(x if x in cand else cand[0], "mano", causa="608.2c")
    return True


def _i_togli_segnalini_scelti(p, d, chi, ctrl, fonte, ogg):
    """«remove up to three counters from ...»: chi controlla sceglie quali e quanti, fino a n in tutto (122.1, 608.2d)."""
    fatto = False
    for x in chi:
        ci = {k: v for k, v in x.segnalini.items() if v > 0}
        resto, base = d["n"], {}
        for k in sorted(ci):
            base[k] = min(ci[k], resto); resto -= base[k]
        s = _scelta(p, ctrl, "togli_segnalini", x, dict(ci), d["n"], predefinita=base)
        if not (isinstance(s, dict) and sum(s.values()) <= d["n"] and all(0 <= v <= ci.get(k, 0) for k, v in s.items())): s = base
        for k, v in s.items():
            if v: fatto = bool(p.t.togli_segnalini(x, k, v, causa="122.1")) or fatto
    return fatto


def _i_scarta_scelta_da_te(p, d, chi, ctrl, fonte, ogg):
    """«Target opponent reveals their hand. You choose a nonland permanent card from it. That player discards that
    card»: 701.9b, la sceglie chi controlla la magia; se non c'e' una carta adatta non si scarta niente."""
    fatto = False
    for j in chi:
        cand = [o for o in p.t.giocatori[j].mano if (d.get("ogni_tipo") or set(PERMANENTI) & o.carta.tipi) and not set(d.get("non_tipi") or ()) & o.carta.tipi
                and (not d.get("tipi") or set(d["tipi"]) & o.carta.tipi)]
        if not cand: continue
        x = _scelta(p, ctrl, "scegli_dalla_mano", cand, predefinita=cand[0])
        fatto = bool(p.t.scarta(x if x in cand else cand[0], causa="701.9a")) or fatto
    return fatto


def _i_esilia_scelta_da_te(p, d, chi, ctrl, fonte, ogg):
    """«Target opponent reveals their hand. You choose a nonland card from it. Exile that card» (Null Summoner): la sceglie
    chi controlla l'abilita' (701.20a: rivelare non cambia niente), va in esilio (701.13a) ed e' collegata alla fonte
    (607.2a: «the exiled card» dell'altra abilita' e' questa e solo questa; se la fonte ha lasciato il campo, il suo oggetto
    nuovo non la vede, 400.7). Senza una carta non terra non si esilia niente."""
    fatto = False
    for j in chi:
        cand = [o for o in p.t.giocatori[j].mano if not set(d.get("non_tipi") or ()) & o.carta.tipi
                and (not d.get("tipi") or set(d["tipi"]) & o.carta.tipi)]                          # «an artifact or creature card»
        if not cand: continue
        x = _scelta(p, ctrl, "scegli_dalla_mano", cand, predefinita=cand[0])
        nuovo = p.t.esilia(x if x in cand else cand[0], causa="701.13a")
        if nuovo is not None and d.get("collega"): nuovo.esiliata_da = fonte.n
        fatto = fatto or nuovo is not None
    return fatto


def mana_qualsiasi(costo):
    """609.4b: «mana of any type can be spent to cast that spell»: cambia solo come si paga. Ogni simbolo che si paga con un
    mana (colorato, {C}, ibrido, {2/B}) si paga con un mana qualsiasi: per il pagamento e' {1}; il generico e la X restano.
    Il phyrexiano (un mana o due vite) non si scrive con i simboli di 107.4: NonCoperto."""
    c = M.leggi(costo)
    if not c.pagabile: return costo
    if any(m.vite for _, modi in c.simboli for m in modi): raise NonCoperto(f"609.4b: il phyrexiano in {costo} con mana di ogni tipo")
    gen = c.generico + len(c.simboli)
    return (f"{{{gen}}}" if gen else "") + "{X}" * c.x or "{0}"


def _i_riprendi_sorvegliata(p, d, chi, ctrl, fonte, ogg):
    """«If you put a card with mana value less than or equal to the amount of life you gained this turn into your
    graveyard this way, put that card into your hand» (202.3: il valore di mana)."""
    di, via = getattr(p, "_sorvegliate", (None, []))
    if di is not ogg: raise NonCoperto("608.2c: «this way» senza un surveil di questa abilita'")
    if d.get("non_tipi"):                                                                          # «a noncreature, nonland card»
        adatta = lambda x: not set(d["non_tipi"]) & x.carta.tipi
    else:
        tetto = p.conta({"tipo": "vita_guadagnata_turno"}, ctrl, fonte, ogg)
        adatta = lambda x: M.valore(x.carta.car.get("costo") or "") <= tetto
    for x in via:
        if x.vivo and x.zona == "cimitero" and adatta(x): p.t.sposta(x, "mano", causa="608.2c")


def _i_ritardata_muore(p, d, chi, ctrl, fonte, ogg):
    """603.7, 603.7b-c, 603.6c, 700.4 (giro 13): «When that creature dies this turn, ...»: un innesco ritardato, una volta sola,
    fino alla fine del turno, sull'oggetto bersaglio (400.7: un oggetto nuovo non e' piu' lui)."""
    for o in chi:
        if _e_giocatore(o) or not (o.vivo and o.zona == "campo"): continue
        p.ritardate.append({"ab": dict(d["ab"], una_volta=True, quando={"evento": "muore_n", "n": o.n}), "ctrl": ctrl, "fonte": fonte,
                            "fino": "fine_turno", "dopo": p.t.eventi[-1].n if p.t.eventi else -1, "turno": p.t.turno_numero})


def _i_ritardata(p, d, chi, ctrl, fonte, ogg):
    """603.7: un'abilita' innescata ritardata, di chi controlla la magia o l'abilita' che la crea; 603.7a: si innesca
    solo con gli eventi dopo; 603.7b: con una durata («until your next turn», «until end of turn») si innesca ogni
    volta, fino alla fine."""
    p.ritardate.append({"ab": d["ab"], "ctrl": ctrl, "fonte": fonte, "fino": d["fino"], "dopo": p.t.eventi[-1].n if p.t.eventi else -1,
                        "turno": p.t.turno_numero})


def _i_copia_magia(p, d, chi, ctrl, fonte, ogg):
    """707.10: la copia va in pila (non e' lanciata), con modi, bersagli, X e costi di quella copiata, sotto chi
    controlla l'effetto; 707.10c: puo' scegliere bersagli nuovi, legali, o lasciarli; 707.10a, 704.5e: fuori dalla pila
    la copia smette di esistere."""
    from tavolo import Carta, Oggetto
    t = p.t
    for x in chi:
        if not (x.vivo and x.zona == "pila" and x.carta is not None): continue
        c = Carta(next(t._carte), x.carta.nome, x.carta.tipo, ctrl, car=dict(x.carta.car, copia_di=None))
        o = Oggetto(next(t._oggetti), c, "pila", ctrl)
        o.tavolo, o.ts = t, next(t._ts)
        o.bersagli, o.reqs, o.fa, o.x = [list(g) for g in getattr(x, "bersagli", [])], list(getattr(x, "reqs", [])), list(getattr(x, "fa", [])), getattr(x, "x", 0)
        o.flashback, o.dalla_mano = False, False                                                    # non e' lanciata (707.10)
        g = (p.chi or {}).get(ctrl)
        if d.get("nuovi_bersagli") and o.reqs and hasattr(g, "bersagli_copia"):
            legali = [p.candidati(r, ctrl, o, o) for r in o.reqs]
            nuova = p._scegli_bersagli(ctrl, o, o.reqs, g.bersagli_copia(p, ctrl, o, o.reqs, legali), o)
            if nuova: o.bersagli = nuova                                                           # 707.10c: legali, o restano
        t.pila.append(o)
        t.oggetti[o.n] = o
        t._evento("zona", carta=c, da=None, a="pila", nuovo=o.n, giocatore=ctrl, causa="707.10")
        p._segna_bersagli(o, ctrl)


def _i_esilia_tranne_fondo(p, d, chi, ctrl, fonte, ogg):
    """«Exile all but the bottom card of each opponent's library» (701.13a), insieme."""
    via = [o for j in chi for o in p.t.giocatori[j].grimorio.carte[:-1]]
    for o in via: p.t.esilia(o, causa="701.13a")


def _i_emblema(p, d, chi, ctrl, fonte, ogg):
    """114.1-114.5: l'emblema nella zona di comando, di chi lo prende (proprietario e controllore), con le sue abilita'."""
    from tavolo import Carta, Oggetto
    for j in chi:
        c = Carta(next(p.t._carte), "Emblema", "Emblem", j, car={"abilita": list(d["abilita"])})
        o = Oggetto(next(p.t._oggetti), c, "comando", j)
        o.tavolo, o.ts = p.t, next(p.t._ts)
        p.t.emblemi.append(o)
        p.t.oggetti[o.n] = o
        p.t._evento("emblema", carta=c, nuovo=o.n, giocatore=j, causa="114.2")


def _i_togli_segnalini(p, d, chi, ctrl, fonte, ogg):
    """«remove a +1/+1 counter from this creature» (122.1). -> se l'ha tolto (per «If you do»)."""
    return bool(sum(p.t.togli_segnalini(x, d["tipo"], d.get("n", 1), causa="122.1") for x in chi if x.vivo and x.zona == "campo"))


def _i_ritorna_tutte(p, d, chi, ctrl, fonte, ogg):
    """«Return all nonland permanent cards from your graveyard to the battlefield»: insieme (608.2f), sotto chi controlla la magia."""
    via = [o for o in list(p.t.giocatori[ctrl].cimitero) if set(PERMANENTI) & o.carta.tipi and "land" not in o.carta.tipi]
    with p.t.insieme():
        for o in via: p.t.metti_in_campo(o, chi=ctrl, causa="400.7")
    return bool(via)


def _i_distribuisci_segnalini(p, d, chi, ctrl, fonte, ogg):
    """601.2d: «Distribute three +1/+1 counters among one, two, or three target creatures»: la divisione si fissa sui bersagli
    scelti lanciando (ognuno almeno uno, 601.2d); un bersaglio diventato illegale non prende i suoi (608.2b). Chi non sceglie
    divide il piu' possibile in parti uguali, il resto ai primi."""
    k = int(d["chi"].split(":")[1]) if isinstance(d.get("chi"), str) and ":" in d["chi"] else 0
    iniziali = list((p._bersagli_iniziali or [[]])[k]) if p._bersagli_iniziali and k < len(p._bersagli_iniziali) else list(chi)
    if not iniziali: return False
    base_, resto_ = divmod(d["n"], len(iniziali))
    pred = [base_ + (1 if j < resto_ else 0) for j in range(len(iniziali))]
    div = _scelta(p, ctrl, "distribuisci", iniziali, d["n"], predefinita=pred)
    if not (isinstance(div, (list, tuple)) and len(div) == len(iniziali) and all(isinstance(v, int) and v >= 1 for v in div) and sum(div) == d["n"]):
        div = pred
    for x, v in zip(iniziali, div):
        if any(x is y for y in chi) and x.vivo and x.zona == "campo": p.t.metti_segnalini(x, d["tipo"], v, causa="601.2d")
    return True


def _i_scopri(p, d, chi, ctrl, fonte, ogg):
    """701.57a: «Discover N»: si esiliano carte dalla cima finche' se ne esilia una non terra con valore di mana N o meno; si
    puo' lanciare senza pagare il costo di mana se la magia ha valore di mana N o meno (608.2g, 118.9), se no va in mano; le
    altre esiliate vanno in fondo al grimorio in ordine casuale."""
    gr = p.t.giocatori[ctrl].grimorio
    altre, presa = [], None
    while gr.carte:
        x = p.t.esilia(gr.carte[0], causa="701.57a")
        if x is None: break
        if "land" not in x.carta.tipi and M.valore(x.carta.car.get("costo") or "") <= d["n"]: presa = x; break
        altre.append(x)
    if presa is not None:
        lanciata = None
        p._alternativo[presa.n] = "gratis"
        try: lanciata = p.lancia_in_risoluzione(ctrl, presa)
        finally: p._alternativo.pop(presa.n, None)
        if lanciata is None and presa.vivo and presa.zona == "esilio": p.t.sposta(presa, "mano", causa="701.57a")
    rng = np.random.default_rng([p.t.seme, len(p.t.eventi), 7057])
    for k in rng.permutation(len(altre)):                                                         # «in a random order»
        x = altre[int(k)]
        if x.vivo and x.zona == "esilio": p.t.sposta(x, "grimorio", posizione="fondo", causa="701.57a")
    return True


def _i_sacrifica_ritardata(p, d, chi, ctrl, fonte, ogg):
    """603.7a-c: «Sacrifice it at the beginning of the next end step»: la ritardata ricorda le pedine appena create."""
    ns = [x.n for x in chi if not _e_giocatore(x) and x.vivo and x.zona == "campo"]
    if ns:
        p.ritardate.append({"ab": {"tipo": "innescata", "una_volta": True, "quando": {"evento": "inizio_passo", "passo": d.get("passo", "finale")},
                                   "fa": [{"fa": "sacrifica_oggetti", "chi": "ricordati"}], "ricordati": ns},   # 511.2: «at end of combat»
                            "ctrl": ctrl, "fonte": ogg, "fino": "sempre", "dopo": p.t.eventi[-1].n, "turno": p.t.turno_numero})


def _i_sacrifica_oggetti(p, d, chi, ctrl, fonte, ogg):
    """701.21a: chi li controlla sacrifica questi permanenti."""
    for x in chi:
        if x.vivo and x.zona == "campo": p.t.sacrifica(x, x.controllore, causa="701.21a")


def _i_scarta_salvo(p, d, chi, ctrl, fonte, ogg):
    """701.9a: «discard two cards unless you discard a creature card»: chi scarta sceglie; chi non sceglie scarta una carta
    di quel tipo se ce l'ha, se no due."""
    mano = list(p.t.giocatori[ctrl].mano)
    if not mano: return False
    del_tipo = [o for o in mano if d["tipo"] in o.carta.tipi]
    pred = [del_tipo[-1]] if del_tipo else mano[-2:]
    via = list(_scelta(p, ctrl, "scarta_salvo", mano, d["tipo"], predefinita=pred) or [])
    ok_ = (len(via) == 1 and d["tipo"] in via[0].carta.tipi) or len(via) == min(2, len(mano))
    if not ok_ or any(o not in mano for o in via) or len({id(o) for o in via}) != len(via): via = pred
    p._scartate = (ogg, via)
    for o in via: p.t.scarta(o, causa="701.9a")
    return True


def _i_scarta_poi_pesca(p, d, chi, ctrl, fonte, ogg):
    """701.9a, 121.1: «discard up to two cards, then draw that many cards»: chi non sceglie scarta le terre in piu' (fino a
    due) se ne ha piu' di tre in mano."""
    mano = list(p.t.giocatori[ctrl].mano)
    terre_ = [o for o in mano if "land" in o.carta.tipi]
    pred = terre_[: max(0, min(d["n"], len(terre_) - 3))]
    via = list(_scelta(p, ctrl, "scarta_fino", mano, d["n"], predefinita=pred) or [])
    if len(via) > d["n"] or any(o not in mano for o in via) or len({id(o) for o in via}) != len(via): via = pred
    for o in via: p.t.scarta(o, causa="701.9a")
    if via: p.t.pesca(ctrl, len(via), causa="121.1")
    return bool(via)


def _i_raddoppia_segnalini(p, d, chi, ctrl, fonte, ogg):
    """701.10e: «double the number of +1/+1 counters on it»: tanti segnalini quanti ne ha gia'."""
    for x in chi:
        if x.vivo and x.zona == "campo" and x.segnalini[d["tipo"]] > 0: p.t.metti_segnalini(x, d["tipo"], x.segnalini[d["tipo"]], causa="701.10e")


def _i_in_fondo(p, d, chi, ctrl, fonte, ogg):
    """«Put target card from your graveyard on the bottom of your library» (401.4)."""
    for x in chi:
        if x.vivo and x.zona == "cimitero": p.t.sposta(x, "grimorio", posizione="fondo", causa="401.4")


def _i_esilia_se_muore(p, d, chi, ctrl, fonte, ogg):
    """«If that permanent would die this turn, exile it instead» (614.1a, 700.4): vale per quell'oggetto, in questo turno."""
    for x in chi:
        if x.vivo and x.zona == "campo": x.esilia_se_muore = p.t.turno_numero


def _i_ruota_scelta(p, d, chi, ctrl, fonte, ogg):
    """«Each player may discard their hand and draw seven cards»: le scelte in ordine APNAP, poi tutto insieme (101.4)."""
    si = []
    for j in p._apnap():
        g = (p.chi or {}).get(j)
        if g.sceglie(p, j, d) if hasattr(g, "sceglie") else True: si.append(j)
    with p.t.insieme():
        for j in si:
            for o in list(p.t.giocatori[j].mano): p.t.scarta(o, causa="701.9a")
    for j in si: p.t.pesca(j, d["n"], causa="121.1")


def _i_dai_flashback(p, d, chi, ctrl, fonte, ogg):
    """«target instant or sorcery card in your graveyard gains flashback until end of turn. The flashback cost is equal
    to its mana cost» (702.34a): vale per quell'oggetto (400.7), in questo turno."""
    for x in chi:
        if x.vivo and x.zona == "cimitero": x.flashback_dato = p.t.turno_numero


def _i_rimetti_esiliate(p, d, chi, ctrl, fonte, ogg):
    """603.7c: la ritardata rimette in campo le carte esiliate che ricorda, sotto il proprietario (110.2a, 400.7)."""
    for x in chi:
        if x.vivo and x.zona == "esilio": p.t.metti_in_campo(x, chi=x.proprietario, causa="603.7c")


def _i_ritorna_esiliata_tua(p, d, chi, ctrl, fonte, ogg):
    """«If that permanent's mana value was 3 or less, return it to the battlefield tapped under your control. Exile it
    at the beginning of the next end step»: il valore di mana com'era (608.2h); la ritardata ricorda l'oggetto nuovo
    (603.7c)."""
    di, via = getattr(p, "_esiliate", (None, []))
    if di is not ogg: raise NonCoperto("608.2c: «that permanent» senza un esilio di questa magia")
    for x in via:
        if not (x.vivo and x.zona == "esilio") or M.valore(x.carta.car.get("costo") or "") > d["mv_max"]: continue
        nuovo = p.t.metti_in_campo(x, chi=ctrl, causa="400.7")
        if nuovo is None or nuovo.zona != "campo": continue
        nuovo.tappato = True
        p.ritardate.append({"ab": {"tipo": "innescata", "una_volta": True, "quando": {"evento": "inizio_passo", "passo": "finale"},
                                   "fa": [{"fa": "esilia", "chi": "ricordati"}], "ricordati": [nuovo.n]},
                            "ctrl": ctrl, "fonte": ogg, "fino": "sempre", "dopo": p.t.eventi[-1].n, "turno": p.t.turno_numero})


def _i_rivela_fino(p, d, chi, ctrl, fonte, ogg):
    """«Reveal cards from the top of your library until you reveal a creature or planeswalker card. Put that card onto
    the battlefield and the rest on the bottom of your library in a random order» (701.20a)."""
    gr = p.t.giocatori[ctrl].grimorio
    ks = [j for j, o in enumerate(gr.carte) if set(d["tipi"]) & o.carta.tipi][: d.get("n", 1)]      # «until you reveal two land cards»
    fine = ks[-1] + 1 if len(ks) == d.get("n", 1) else len(gr.carte)                                # (meno se non ce ne sono: tutte)
    prese = [gr.carte[j] for j in ks]
    resto = [o for o in gr.carte[:fine] if not any(o is x for x in prese)]
    for o in prese:
        if d.get("dove") == "mano": p.t.sposta(o, "mano", causa="701.20a")
        else:
            nuovo = p.t.metti_in_campo(o, chi=ctrl, causa="701.20a")
            if d.get("tappata") and nuovo is not None and nuovo.zona == "campo": nuovo.tappato = True
    rng = np.random.default_rng([p.t.seme, len(p.t.eventi), 7020])
    for j in rng.permutation(len(resto)):                                                          # in un ordine casuale
        o = resto[int(j)]
        if o in gr.carte: gr.carte.remove(o); gr.carte.append(o)


def tipo_preferito(t, i):
    """Il tipo di creatura piu' frequente fra le carte del giocatore (campo, mano, cimitero, grimorio): la scelta di chi
    non sceglie (205.3m: si puo' scegliere qualsiasi tipo; e' una scelta del giocatore, non una regola)."""
    from collections import Counter as Cn
    g = t.giocatori[i]
    oggetti = [o for o in t.campo if o.controllore == i] + list(g.mano) + list(g.cimitero) + list(g.grimorio.carte)
    c = Cn(w for o in oggetti if o.carta.tipi & {"creature", "kindred"} for w in o.carta.tipo.split("//")[0].partition("—")[2].split()
           if w in TIPI_CREATURA)
    return c.most_common(1)[0][0] if c else "Human"


def _i_scegli_tipo(p, d, chi, ctrl, fonte, ogg):
    """205.3m, 608.2c: «Choose a creature type»: lo sceglie chi controlla l'effetto; le frasi dopo dicono «that type»."""
    opzioni = sorted(TIPI_CREATURA)
    pred = tipo_preferito(p.t, ctrl)
    tipo = _scelta(p, ctrl, "tipo_creatura", opzioni, predefinita=pred)
    if fonte is not None: fonte.tipo_scelto = tipo if tipo in TIPI_CREATURA else pred


def _i_rianima_tutte(p, d, chi, ctrl, fonte, ogg):
    """«Return all creature cards of the chosen type from your graveyard to the battlefield» (400.7: oggetti nuovi, insieme)."""
    via = [o for o in list(p.t.giocatori[ctrl].cimitero) if set(d["tipi"]) & o.carta.tipi
           and (not d.get("tipo_scelto") or (getattr(fonte, "tipo_scelto", None) and ha_sottotipo(o, fonte.tipo_scelto)))]
    with p.t.insieme():
        for o in via:
            n_ = p.t.metti_in_campo(o, chi=ctrl, causa="400.7")
            if d.get("tappata") and n_ is not None and n_.zona == "campo": n_.tappato = True        # «tapped»


def _i_distruggi_tranne_tipo(p, d, chi, ctrl, fonte, ogg):
    """«Choose a creature type. Destroy all creatures that aren't of the chosen type» (205.3m, 701.8a): sceglie chi
    controlla la magia; un tipo che nessuna creatura ha vale quanto un altro tipo assente."""
    presenti = sorted({w for o in p.t.campo if "creature" in o.carta.tipi for w in o.carta.tipo.split("—")[-1].split()} if any(
        "—" in o.carta.tipo for o in p.t.campo) else set())
    opzioni = presenti + ["(un tipo che nessuna ha)"]
    tipo = _scelta(p, ctrl, "tipo_creatura", opzioni, predefinita=opzioni[0])
    via = [o for o in p.t.campo if "creature" in o.carta.tipi and not ha_sottotipo(o, tipo)]       # 702.73a
    with p.t.insieme():
        for o in via:
            if "indestructible" not in parole(o): p.t.distruggi(o, causa="701.8a")


def _i_prolifera(p, d, chi, ctrl, fonte, ogg):
    """701.34a: proliferare: si sceglie un gruppo qualsiasi di permanenti (e giocatori) con segnalini e a ognuno si da'
    un segnalino in piu' di ogni tipo che ha; «X times»: tante volte. Chi non sceglie prende i suoi permanenti."""
    for _ in range(d.get("n", 1)):
        cand = [o for o in p.t.campo if any(v > 0 for v in o.segnalini.values())]
        if any(getattr(g, "segnalini", None) for g in p.t.giocatori): raise NonCoperto("701.34a: segnalini sui giocatori")
        sc = _scelta(p, ctrl, "prolifera", cand, predefinita=[o for o in cand if o.controllore == ctrl])
        with p.t.insieme():
            for o in [x for x in sc if x in cand]:
                for k, v in list(o.segnalini.items()):
                    if v > 0: p.t.metti_segnalini(o, k, 1, causa="701.34a")


def _i_esilia_cima(p, d, chi, ctrl, fonte, ogg):
    """701.13a, 406.3: le prime n carte del grimorio di chi controlla la magia o l'abilita' vanno in esilio, a faccia in
    su; con meno carte se ne esiliano quante ce ne sono. Sono «that card» per le istruzioni dopo (400.7j)."""
    gr = p.t.giocatori[ctrl].grimorio
    via = [p.t.esilia(x, causa="701.13a") for x in list(gr.carte[:d.get("n", 1)])]
    p._esiliate = (ogg, [x for x in via if x is not None])
    return bool(p._esiliate[1])


def _i_prendi_controllo(p, d, chi, ctrl, fonte, ogg):
    """613.1b, 110.2: chi controlla l'effetto prende il controllo; «until end of turn» torna indietro nella pulizia (514.2)."""
    fatto = False
    for x in chi:
        if not (x.vivo and x.zona == "campo"): continue
        prima = x.controllore
        if p.t.prendi_controllo(x, ctrl, causa="613.1b"):
            fatto = True
            if d.get("durata") == "fine_turno":
                if not hasattr(p.t, "controlli_temp"): p.t.controlli_temp = []
                p.t.controlli_temp.append((x, prima))
            elif d.get("durata") is not None: raise NonCoperto(f"611.2: la durata {d['durata']!r} del controllo")
    return fatto


def _i_permesso_gioca(p, d, chi, ctrl, fonte, ogg):
    """601.3, 305.1, 116.2a: «Until the end of your next turn, you may play that card»: un effetto che permette a chi
    controlla la magia di giocare la carta esiliata dall'esilio, con i tempi e i limiti di sempre (117.1a, 305.2); dura
    fino alla fine del suo prossimo turno (611.2a) e solo per quell'oggetto (400.7: se lascia l'esilio, il permesso
    non lo segue)."""
    di, via = getattr(p, "_esiliate", (None, []))
    if di is not ogg: raise NonCoperto("608.2c: «that card» senza una carta esiliata da questa magia")
    if d.get("uno") and via:                                                                       # «choose one of them»: sceglie chi la gioca
        cand = [x for x in via if x.vivo and x.zona == "esilio"]
        x_ = _scelta(p, ctrl, "scegli_esiliata", cand, predefinita=cand[0]) if cand else None
        via = [x_ if x_ in cand else cand[0]] if cand else []
    for x in via:
        if not (x.vivo and x.zona == "esilio"): continue
        p.permessi.append({"n": x.n, "giocatore": ctrl, "fino": d["fino"], "iniziato": False})
        p.t._evento("permesso", carta=x.carta, vecchio=x.n, giocatore=ctrl, a=d["fino"], causa="601.3")


def _i_fedelta_rapida(p, d, chi, ctrl, fonte, ogg):
    """606.3, 117.1a: «Until end of turn, you may activate loyalty abilities of Jace planeswalkers you control on any player's
    turn any time you could cast an instant» (Jace's Machinations): cambia solo i tempi, per i Jace che chi la controlla
    controlla quando attiva (non un insieme fissato: vale anche per il Jace creato dopo, 611.2c parla delle caratteristiche);
    una sola abilita' di fedelta' per permanente per turno resta (606.3, ruling del 21 ago 2026). Finisce nella pulizia
    (514.2, 611.2a)."""
    if d.get("durata") != "fine_turno": raise NonCoperto(f"611.2a: la durata {d.get('durata')!r} di un permesso di fedelta'")
    p.fedelta_rapide.add((ctrl, d["sottotipo"]))
    return True


def _i_mana_in_piu(p, d, chi, ctrl, fonte, ogg):
    """603.7, 605.1b, 605.4a, 106.12a: «Until end of turn, whenever you tap a Mountain for mana, add an additional {R}» (Molten
    Tide): un'abilita' innescata ritardata che e' un'abilita' di mana: si innesca quando chi la controlla tappa per mana una
    Mountain (un'abilita' di mana col {T}, 106.12, che si risolve e produce mana) e si risolve subito, senza pila, prima che il
    mana serva (605.4a, con l'esempio: si usa per pagare la stessa magia). Nel motore: ogni produzione di quella terra ha il
    mana in piu' (`produzioni`), una volta per effetto; finisce nella pulizia (603.7b, 514.2)."""
    if d.get("durata") != "fine_turno": raise NonCoperto(f"603.7b: la durata {d.get('durata')!r} di un'abilita' di mana ritardata")
    p.mana_in_piu.append((ctrl, d["sottotipo"], d["mana"]))
    p.t._versione += 1
    return True


def _i_dal_fuori(p, d, chi, ctrl, fonte, ogg):
    """«You may reveal exactly two cards you own with different names from outside the game. An opponent chooses one of them.
    You put that card into your hand» (Extrapolate the Impossible): 400.11, 100.4b (nel Limited il sideboard e' il resto del
    pool, piu' le terre base: ruling del 21 ago 2026), 701.20a. Chi la controlla sceglie se rivelarne esattamente due di nomi
    diversi (senza due nomi diversi non puo'); un avversario ne sceglie una, che entra nella mano (400.11b); l'altra resta
    fuori (ruling del 21 ago 2026)."""
    cand = p.t.candidati_fuori(ctrl)
    if len({v[0] for v in cand}) < d.get("n", 2): return False
    pred, nomi = [], set()
    for v in cand:
        if v[0] not in nomi and len(pred) < 2: pred.append(v); nomi.add(v[0])
    due = _scelta(p, ctrl, "rivela_fuori", cand, predefinita=pred)
    if due is None: return False                                                                    # «you may»: non rivela
    due = list(due)
    if len(due) != 2 or due[0][0] == due[1][0] or any(not any(v is c for c in cand) for v in due): due = pred
    p.t._evento("rivelate", giocatore=ctrl, a=" e ".join(v[0] for v in due), quanto=2, causa="701.20a")
    k = next((g.i for g in p.t.giocatori if g.i != ctrl and not g.perso), None)
    if k is None: return False
    sc = _scelta(p, k, "sceglie_fuori", due, predefinita=due[0])
    sc = sc if any(sc is v for v in due) else due[0]
    return p.t.porta_dentro(ctrl, sc, "mano", causa="400.11b") is not None


def _i_esilia_e_lancia_copie(p, d, chi, ctrl, fonte, ogg):
    """«Exile up to one target nonland card of each card type from your graveyard. Copy those cards. You may cast any number of
    spells with total mana value 6 or less from among the copies without paying their mana costs» (Uldaros Theorix): i
    bersagli legali vanno in esilio (701.13a), di ognuno si fa una copia in esilio (707.12, 112.2a: di chi la puo' lanciare);
    chi controlla l'abilita' sceglie quali lanciare, una per una (707.12a), col valore di mana totale entro il limite (202.3:
    con X=0, 107.3b e ruling del 21 ago 2026); si lanciano adesso durante la risoluzione (608.2g: i tempi non contano, i
    divieti si') senza pagare il costo di mana (118.9; i costi aggiuntivi si pagano e gli aumenti valgono, 118.9d); le magie
    permanente diventano pedine (608.3f); le copie non lanciate smettono di esistere (704.5e)."""
    esiliate = [x_ for x_ in (p.t.esilia(x, causa="701.13a") for x in chi if not _e_giocatore(x) and x.vivo and x.zona == "cimitero") if x_ is not None]
    copie = [p.t.copia_carta(ctrl, x, causa="707.12") for x in esiliate]
    limite = d["mv_totale"]
    def mv(o): return M.valore(o.carta.car.get("costo") or "")                                    # 202.3e, 107.3b: X = 0
    def puo(o):
        p._alternativo[o.n], prima = "gratis", p._lancio_risoluzione
        p._lancio_risoluzione = o.n
        try: return p.puo_lanciare(ctrl, o, 0)
        finally: p._lancio_risoluzione = prima; p._alternativo.pop(o.n, None)
    pred, tot = [], 0
    for o in copie:
        if tot + mv(o) <= limite and puo(o): pred.append(o); tot += mv(o)
    scelte = _scelta(p, ctrl, "lancia_copie", copie, limite, predefinita=pred)
    scelte = list(scelte or [])
    if len({id(o) for o in scelte}) != len(scelte) or any(not any(o is c for c in copie) for o in scelte) or sum(mv(o) for o in scelte) > limite:
        scelte = pred
    fatto = False
    for o in scelte:                                                                               # 707.12a: una per una
        if not (o.vivo and o.zona == "esilio"): continue
        p._alternativo[o.n], prima = "gratis", p._lancio_risoluzione
        p._lancio_risoluzione = o.n
        try: fatto = p.lancia(ctrl, o, 0) is not None or fatto
        finally: p._lancio_risoluzione = prima; p._alternativo.pop(o.n, None)
    return fatto or bool(esiliate)


def _carta_del_costo(ogg):
    """400.7j: «this card» dopo un costo che l'ha esiliata: l'oggetto nuovo in esilio, che l'effetto puo' trovare."""
    x = getattr(ogg, "esiliata_costo", None)
    if x is None: raise NonCoperto("400.7j: «this card» senza una carta esiliata dal costo di questa abilita'")
    return x


def _i_dai_mana(p, d, chi, ctrl, fonte, ogg):
    """613.1f, 605.1a, 611.2a: «Target land gains "{T}: Add {C}{C}" until this card is cast from exile» (Emrakul, the
    Exigent Doom): un'abilita' di mana data alla terra (sotto chi la controlla), per l'insieme fissato (611.2c). Dura
    finche' la carta esiliata dal costo diventa lanciata dall'esilio (601.2i): due ruling di Wizards (21 ago 2026) dicono
    che il mana si puo' usare lanciandola (601.2g: prima che diventi lanciata) e che se la carta lascia l'esilio senza
    essere lanciata la terra tiene l'abilita' (la durata non finisce mai, 611.2a)."""
    if d.get("durata") != "finche_lanciata_dall_esilio": raise NonCoperto(f"611.2b: la durata {d.get('durata')!r} di un'abilita' di mana data")
    carta = _carta_del_costo(ogg)
    oggetti = [x for x in chi if not _e_giocatore(x) and x.vivo and x.zona == "campo"]
    if not oggetti: return False
    p.t.aggiungi_continuo("6", {"dai_mana": [d["mana"]]}, chi=frozenset(o.n for o in oggetti), fonte=fonte,
                          durata=(LANCIATA, carta.n), ctrl=ctrl)
    return True


def _i_permesso_questa(p, d, chi, ctrl, fonte, ogg):
    """601.3, 611.2b, 400.7j: «You may cast this card for as long as it remains exiled»: chi controlla l'abilita' puo'
    lanciare la carta esiliata dal costo, coi tempi di sempre (117.1a), finche' quell'oggetto resta in esilio (400.7: se
    lascia l'esilio il permesso non lo segue). Se e' gia' uscita, il permesso non comincia (611.2b)."""
    if d.get("fino") != "finche_in_esilio": raise NonCoperto(f"611.2b: la durata {d.get('fino')!r} di un permesso")
    x = _carta_del_costo(ogg)
    if not (x.vivo and x.zona == "esilio"): return False
    p.permessi.append({"n": x.n, "giocatore": ctrl, "fino": "finche_in_esilio", "iniziato": False})
    p.t._evento("permesso", carta=x.carta, vecchio=x.n, giocatore=ctrl, a="finche_in_esilio", causa="601.3")
    return True


def _i_lancia_esiliata(p, d, chi, ctrl, fonte, ogg):
    """608.2g: «You may cast that card»: si lancia durante la risoluzione, coi passi 601.2a-i, pagando il costo; nessuno
    riceve la priorita' e la magia va in cima alla pila sopra cio' che si sta risolvendo. Una terra non si lancia
    (305.9). -> True se e' stata lanciata (per «If you don't»)."""
    di, via = getattr(p, "_esiliate", (None, []))
    if di is not ogg: raise NonCoperto("608.2c: «that card» senza una carta esiliata da questa magia")
    fatto = False
    for x in via:
        if not (x.vivo and x.zona == "esilio") or "land" in x.carta.tipi: continue
        if d.get("gratis"):                                                                        # 118.9: «without paying its mana cost
            mv_ = M.valore(x.carta.car.get("costo") or "")                                         # if the spell's mana value is N or less»
            if mv_ > d["n"] or (d.get("minore") and mv_ >= d["n"]): continue                       # (202.3, X = 0)
            p._alternativo[x.n] = "gratis"
            try: fatto = p.lancia_in_risoluzione(ctrl, x) is not None or fatto
            finally: p._alternativo.pop(x.n, None)
        elif p.lancia_in_risoluzione(ctrl, x) is not None: fatto = True
    return fatto


def _i_esilia_fino_non_terra(p, d, chi, ctrl, fonte, ogg):
    """701.13a: «exile cards from the top of your library until you exile a nonland card»: le terre restano in esilio;
    «that card» e' la carta non terra (senza una, nessuna)."""
    gr = p.t.giocatori[ctrl].grimorio
    presa = None
    while gr.carte and presa is None:
        x = p.t.esilia(gr.carte[0], causa="701.13a")
        if x is not None and "land" not in x.carta.tipi: presa = x
    p._esiliate = (ogg, [presa] if presa is not None else [])
    return presa is not None


def _i_in_mano_esiliata(p, d, chi, ctrl, fonte, ogg):
    """«If you don't, put that card into your hand» (400.7: l'oggetto in esilio, se c'e' ancora)."""
    di, via = getattr(p, "_esiliate", (None, []))
    if di is not ogg: raise NonCoperto("608.2c: «that card» senza una carta esiliata da questa magia")
    for x in via:
        if x.vivo and x.zona == "esilio": p.t.sposta(x, "mano", causa="400.7")


def _i_copia_pedina(p, d, chi, ctrl, fonte, ogg):
    """111.1, 707.2: «create a token that's a copy of ...»: una pedina sotto chi controlla la magia o l'abilita' per ogni
    oggetto, coi suoi valori copiabili (com'era, se ha lasciato il campo: 608.2h) e le eccezioni (707.9a)."""
    ecc = {k: d[k] for k in ("parole", "abilita") if d.get(k)}
    if "leggendaria" in d: ecc["leggendaria"] = d["leggendaria"]                                     # 707.9b (giro 13)
    create = [x for x in (p.t.crea_copia(ctrl, o, ecc, causa="707.2") for o in chi) if x is not None]
    p._create = (ogg, create)
    return bool(create)


def _i_diventa_copia(p, d, chi, ctrl, fonte, ogg):
    """707.2, 613.2a: «this land becomes a copy of target creature you control until end of turn» (Hall of Echoes).
    chi = [chi diventa copia, l'originale]. I valori copiabili si prendono adesso (707.2b: non seguono i cambi
    dell'originale); niente entra e niente esce, gli effetti non di copia restano (707.4); l'insieme e' fissato (611.2c);
    finisce con la pulizia (514.2, 611.2a). Se uno dei due non c'e' piu', non succede niente."""
    if len(chi) != 2: return
    x, orig = chi
    if not (x.vivo and x.zona == "campo" and orig.vivo and orig.zona == "campo"): return
    p.t.diventa_copia(x, orig, fonte=fonte, durata=d.get("durata"), ctrl=ctrl)


def _i_senza_leggenda(p, d, chi, ctrl, fonte, ogg):
    """704.5j, 611.2c, 613.11: «the "legend rule" doesn't apply to permanents you control this turn»: non cambia le
    caratteristiche, cambia una regola del gioco, quindi vale anche per i permanenti che arrivano dopo; «this turn»
    finisce con la pulizia (514.2)."""
    p.t.aggiungi_continuo("regola", {"senza_leggenda": True}, sel={"tipi": ["permanent"], "controllo": "tuo"}, fonte=fonte,
                          durata=d.get("durata"), ctrl=ctrl)


def _i_vinci(p, d, chi, ctrl, fonte, ogg):
    for j in chi: p.t.vince(j, causa="104.2b")


def _i_mescola_nel_grimorio(p, d, chi, ctrl, fonte, ogg):
    """«Its owner shuffles it into their library»: nel grimorio del proprietario, poi si mescola (401.3, 701.24a)."""
    for x in chi: p.t.sposta(x, "grimorio", posizione="mescola", causa="701.24a")


def _i_esilia_finche(p, d, chi, ctrl, fonte, ogg):
    """610.3: «exile ... until this enchantment leaves the battlefield»; 610.3b: se la fonte se n'e' gia' andata
    dopo l'innesco, non si esilia niente."""
    if not (fonte.vivo and fonte.zona == "campo"): return False
    for x in chi:
        nuovo = p.t.esilia(x, causa="610.3")
        if nuovo is not None and nuovo is not x: p.t.legami.setdefault(fonte.n, []).append(nuovo)
    return True


def _i_cima_o_fondo(p, d, chi, ctrl, fonte, ogg):
    """«Its owner may put it on top of their library. If they do, ~ deals 2 damage to them. If they didn't ..., they
    put it on the bottom»: sceglie il proprietario (608.2d), poi la magia infligge il danno (120.2b)."""
    for x in chi:
        j = x.proprietario
        g = (p.chi or {}).get(j)
        cima = g.sceglie(p, j, d) if hasattr(g, "sceglie") else True
        p.t.sposta(x, "grimorio", posizione="cima" if cima else "fondo", causa="401.4")
        if cima: p.t.infliggi(fonte, [(j, d["danno_se_cima"])], causa="120.2b")


def _i_scarta(p, d, chi, ctrl, fonte, ogg):
    """701.9a-b: sceglie chi scarta, salvo «at random»; 101.4: in ordine APNAP, poi insieme (608.2e)."""
    scelte = []
    for j in [j for j in p._apnap() if j in chi]:
        mano = list(p.t.giocatori[j].mano)
        n = len(mano) if d.get("tutta") else min(d.get("n", 1), len(mano))                         # «discard your hand»; 609.3
        if n <= 0: continue
        if d.get("a_caso"):
            rng = np.random.default_rng([p.t.seme, len(p.t.eventi), 7019])
            via = [mano[int(k)] for k in rng.permutation(len(mano))[:n]]
        else:
            via = list(_scelta(p, j, "scarta_effetto", mano, n, predefinita=mano[-n:]))
            if len(via) != n or any(o not in mano for o in via): via = mano[-n:]
        scelte += via
    p._scartate = (ogg, scelte)                           # «this way»: le carte scartate (com'erano in mano)
    for o in scelte: p.t.scarta(o, causa="701.9a")
    return bool(scelte)


def _i_pedina(p, d, chi, ctrl, fonte, ogg):
    """111.2-111.4: le pedine con le caratteristiche dette dall'effetto, sotto chi le crea."""
    n = ogg.x if d.get("quante") == "X" else d.get("quante", 1)
    if not isinstance(n, int): raise NonCoperto(f"111.2: il numero di pedine {n!r}")
    create = []
    for j in chi:
        dd = d
        if "Artifact" in d["tipo"] and p.t._sostituzioni("draghi", j):                           # 614.1a: «that many 5/5 red Dragon ... instead»
            dd = {"fa": "pedina", "nome": "Dragon", "tipo": "Token Creature — Dragon", "forza": 5, "costituzione": 5, "colori": "R", "parole": ["flying"]}
        for _ in range(n):
            car = {k: v for k, v in dd.items() if k in ("forza", "costituzione", "parole", "abilita", "mana", "colori", "fedelta", "mana_sacrifica")}
            if dd.get("parole_extra"): car["parole"] = list(car.get("parole") or []) + [x for x in dd["parole_extra"] if x not in (car.get("parole") or [])]
            if dd.get("car_extra"): car.update(dd["car_extra"])                                     # 113.1a: le altre parti dell'abilita' data
            o = p.t.crea_pedina(j, dd["nome"], dd["tipo"], causa="111.2", car=car)
            if d.get("tappata"): p.t.tappa(o)
            if d.get("attaccando"): p.entra_attaccando(o, fonte)                                   # 508.4
            create.append(o)
    p._create = (ogg, create)                             # «it»: la pedina appena creata


JACE = {"forza": None, "costituzione": None, "colori": "U", "abilita": [
    {"tipo": "attivata", "fedelta": -1, "fa": [{"fa": "surveil", "n": 1}]},
    {"tipo": "attivata", "fedelta": -3, "fa": [{"fa": "pesca", "n": 1}]}]}


def _i_empower(p, d, chi, ctrl, fonte, ogg):
    """701.71a: se non controlla una pedina planeswalker Jace la crea (blu, 0 fedelta', [-1]: Surveil 1, [-3]: Draw a
    card); poi sceglie una pedina Jace e ci mette N segnalini fedelta'."""
    n = ogg.x if d["n"] == "X" else d["n"]
    for j in chi:
        jace = [o for o in p.t.campo if o.controllore == j and o.carta.pedina and "planeswalker" in o.carta.tipi
                and "Jace" in o.carta.tipo]
        if not jace:
            jace = [p.t.crea_pedina(j, "Jace", "Token Planeswalker — Jace", causa="701.71a", car=dict(JACE))]
        scelto = _scelta(p, j, "scegli_jace", jace, predefinita=jace[0])
        p.t.metti_segnalini(scelto if scelto in jace else jace[0], "fedelta", n, causa="701.71a")


def _i_lotta(p, d, chi, ctrl, fonte, ogg):
    """701.14a-b: le due creature si infliggono danno pari alla forza; se una non c'e' o non e' piu' una creatura, o e'
    un bersaglio illegale, nessuna lotta. chi = [la prima, la seconda]."""
    if len(chi) != 2: return
    a, b = chi
    if not all(x.vivo and x.zona == "campo" and "creature" in x.carta.tipi for x in (a, b)): return
    with p.t.insieme():
        p.t.infliggi(a, [(b, forza(a))], causa="701.14a")
        p.t.infliggi(b, [(a, forza(b))], causa="701.14a")


def _i_danno_forza(p, d, chi, ctrl, fonte, ogg):
    """«[creatura] deals damage equal to its power to [x]»: chi = [la creatura che infligge, chi riceve]."""
    if len(chi) != 2: return
    a, b = chi
    if d.get("lki") and not (a.vivo and a.zona == "campo"):                                        # 113.7a, 608.2h: la fonte sacrificata
        f_ = (getattr(a, "lki", None) or {}).get("forza")                                          # come l'ultima volta in campo
        if f_ is not None: p.t.infliggi(a, [(b, f_)], causa="120.2b")
        return
    if not (a.vivo and a.zona == "campo"): return
    p.t.infliggi(a, [(b, forza(a))], causa="120.2b")


def _i_danno_fedelta(p, d, chi, ctrl, fonte, ogg):
    """«[planeswalker] deals damage equal to its loyalty to [x]» (306.5b: la fedelta' sono i segnalini)."""
    if len(chi) != 2: return
    a, b = chi
    if not (a.vivo and a.zona == "campo"): return
    p.t.infliggi(a, [(b, a.segnalini["fedelta"])], causa="120.2b")


def _i_aggiungi_mana(p, d, chi, ctrl, fonte, ogg):
    """106.4: il mana prodotto da un effetto va nella riserva; 106.6: col vincolo, se l'effetto lo dice."""
    for j in chi:
        mana = d["mana"]
        col = ["{W}", "{U}", "{B}", "{R}", "{G}"]
        if mana == "qualsiasi":                                                                    # 106.1a: «one mana of any color»
            mana = _scelta(p, j, "colore_mana", col, predefinita=col[0])
            if mana not in col: mana = col[0]
        elif mana == "tra":                                                                        # «add {W}, {B}, or {G}»: uno a scelta
            mana = _scelta(p, j, "colore_mana", d["tra"], predefinita=d["tra"][0])
            if mana not in d["tra"]: mana = d["tra"][0]
        elif mana == "uno_colore":                                                                 # «N mana of any one color»
            c_ = _scelta(p, j, "colore_mana", col, predefinita=col[0])
            mana = (c_ if c_ in col else col[0]) * max(0, d.get("n", 1))
        elif mana == "combinazione":                                                               # «N mana in any combination of colors»
            mana = ""
            for _ in range(d.get("n", 1)):
                c_ = _scelta(p, j, "colore_mana", col, predefinita=col[0])
                mana += c_ if c_ in col else col[0]
        if not mana: continue
        prod = M.produzione(mana * d.get("volte", 1)) if d.get("volte", 1) else None               # «add {G} for each ...»
        if prod is None: continue
        p.t.giocatori[j].riserva.aggiungi(prod)
        p.mana_da_effetti += sum(prod)                                                             # per il conto 106.4 di chi controlla
        if d.get("vincolo"):
            for k, n in enumerate(prod): p.vincolato[j] += [(k, d["vincolo"])] * n


def _i_sacrifica(p, d, chi, ctrl, fonte, ogg):
    """701.21a, 101.4: ogni giocatore sceglie in ordine APNAP, poi si sacrifica insieme."""
    scelte = []
    for j in [j for j in p._apnap() if j in chi]:
        cand = [o for o in p.t.campo if o.controllore == j and set(d.get("tipi", ["permanent"])) & (o.carta.tipi | {"permanent"})
                and not (d.get("altra") and o is fonte) and not (d.get("non_pedina") and o.carta.pedina)]   # «another», «nontoken»
        if not cand: continue
        if d.get("massimo_mv"):                                                                    # «with the greatest mana value»
            mv = lambda o: 0 if o.carta.pedina else M.valore(o.carta.car.get("costo") or "")
            alto = max(mv(o) for o in cand)
            cand = [o for o in cand if mv(o) == alto]
        for _k in range(d.get("quante", 1)):                                                       # «sacrifices two creatures» (giro 9)
            if not cand: break
            x = _scelta(p, j, "sacrifica", cand, predefinita=cand[0])
            x = x if x in cand else cand[0]
            scelte.append(x); cand = [o for o in cand if o is not x]
    p._sacrificati = (ogg, {o.controllore for o in scelte if p.t.sacrifica(o, o.controllore, causa="701.21a") is not None})   # «this way»
    return bool(scelte)


def _i_ritorna(p, d, chi, ctrl, fonte, ogg):
    """Dal cimitero alla mano o al campo (400.7: e' un oggetto nuovo)."""
    for x in chi:
        if not (x.vivo and x.zona == "cimitero"): continue
        if d.get("dove") == "campo":
            nuovo = p.t.metti_in_campo(x, chi=x.proprietario if d.get("sotto_proprietario") else ctrl, causa="400.7")
            if nuovo is not None and d.get("tappata"): nuovo.tappato = True                         # «to the battlefield tapped»: entra tappata
            for tipo, n in (d.get("con_segnalini") or {}).items():                                # «with a finality counter on it»
                if nuovo is not None: p.t.metti_segnalini(nuovo, tipo, n, causa="122.6")
        else: p.t.sposta(x, "mano", causa="400.7")


def _i_cerca(p, d, chi, ctrl, fonte, ogg):
    """701.23a, 701.24b: cerca nel grimorio una carta del tipo detto, la mette dove dice, poi si mescola. In una zona
    nascosta si puo' non trovarla (701.23b): chi non sceglie prende la prima che c'e'."""
    def adatta_alt(o, a):                                                                          # (giro 13) una alternativa
        if a.get("nome"): return o.carta.nome.lower() == a["nome"].lower()                         # 201.2
        riga_ = {w.lower() for w in o.carta.tipo.replace("—", " ").replace("//", " ").split()}
        if not all(w in riga_ for w in a.get("tipi") or ()): return False
        if any(w in o.carta.tipi for w in a.get("non") or ()): return False                       # «nonland» (205.4b)
        if a.get("perm") and not o.carta.tipi & {"artifact", "battle", "creature", "enchantment", "land", "planeswalker"}: return False   # 110.4
        if a.get("flash") and "flash" not in {str(x).lower() for x in (o.carta.car.get("parole") or [])}: return False   # 702.8a
        mv_ = M.valore(o.carta.car.get("costo") or "")                                             # 202.3
        mx_ = (getattr(ogg, "x", 0) or 0) if a.get("mv_max") == "X" else a.get("mv_max", 10 ** 6)
        if mv_ > mx_ or mv_ < a.get("mv_min", -1): return False
        if a.get("mv_in") and mv_ not in a["mv_in"]: return False
        return True
    def adatta(o):
        if d.get("alt") is not None: return any(adatta_alt(o, a) for a in d["alt"])
        riga = o.carta.tipo
        if d.get("parole_intere"): riga = set(riga.replace("—", " ").replace("//", " ").split())   # 205: parole intere («Ox» non e' «Fox»)
        if not all(w in riga for w in d["tipo"]): return False
        if d.get("nome") and o.carta.nome != d["nome"]: return False                               # «a card named ~» (201.2)
        if d.get("tipo_o") and not any(all(w in riga for w in alt) for alt in d["tipo_o"]): return False   # «a Mount or Vehicle card»
        if "mv_max" in d or "mv_min" in d:                                                         # 202.3: il valore di mana in grimorio
            mv_ = M.valore(o.carta.car.get("costo") or "")
            mx_ = (getattr(ogg, "x", 0) or 0) if d.get("mv_max") == "X" else d.get("mv_max", 10 ** 6)   # 107.3a (giro 10)
            if mv_ > mx_ or mv_ < d.get("mv_min", -1): return False
        return True
    for j in chi:
        if d.get("dove") == "cima":                                                                # «then shuffle and put that card on top» (701.24b)
            gr = p.t.giocatori[j].grimorio
            for o in gr.cerca(adatta, d.get("quante", 1), mescola=True): gr.metti(o, "cima")
            continue
        quante = d.get("quante", 1)
        if quante == "X": quante = getattr(ogg, "x", 0) or 0                                       # 107.3m: la X della magia
        if d.get("nomi_diversi"):                                                                  # «up to X ... with different names»:
            cand = [o for o in p.t.giocatori[j].grimorio.carte if adatta(o)]                        # chi cerca sceglie (701.23a-b)
            pred = []
            for o in cand:
                if len(pred) < quante and o.nome not in {x.nome for x in pred}: pred.append(o)
            sc = list(_scelta(p, j, "cerca_effetto", cand, quante, predefinita=pred))
            if len(sc) > quante or len({o.nome for o in sc}) != len(sc) or len({id(o) for o in sc}) != len(sc) or any(o not in cand for o in sc): sc = pred
            presi = {id(o) for o in sc}
            p.t.cerca(j, lambda o: id(o) in presi, len(sc), verso=d.get("dove", "mano"), chi=j, causa="701.23a")   # e si mescola (701.24b)
            continue
        if quante <= 0: continue
        trovate = p.t.cerca(j, adatta, quante, verso=d.get("dove", "mano"), chi=j, causa="701.23a")
        if d.get("anche_cimitero") and len(trovate) < quante:                                      # «library and/or graveyard» (giro 13)
            for o in [o for o in p.t.giocatori[j].cimitero if adatta(o)][:quante - len(trovate)]:
                if d.get("dove") == "campo" and o.carta.tipi & {"instant", "sorcery"}: continue   # 400.4a
                trovate.append(p.t.sposta(o, d.get("dove", "mano"), chi=j, causa="701.23a"))
        if d.get("tappata"):
            for o in trovate:
                if o.zona == "campo": o.tappato = True                                              # «onto the battlefield tapped»


def _i_guarda_cima_prendi(p, d, chi, ctrl, fonte, ogg):
    """701.20a, 401.4 (14 nov 2026): «look at the top N cards of your library. [you may reveal a X card from among them and]
    put [one] into your hand; the rest on the bottom (in a random order / any order) or into your graveyard». Chi non sceglie
    prende la prima carta adatta dall'alto; il resto in fondo in ordine casuale (o nel cimitero)."""
    gr = p.t.giocatori[ctrl].grimorio
    viste = list(gr.carte[:d["n"]])
    def adatta(o):
        if not d.get("tipi"): return True
        sotto = {w.lower() for w in o.carta.tipo.split("—")[-1].split()} if "—" in o.carta.tipo else set()
        return any(w in o.carta.tipi or w in sotto or (w == "permanent" and o.carta.tipi & {"artifact", "creature", "enchantment", "land",
                                                                                           "planeswalker", "battle"}) for w in d["tipi"])
    adatte = [o for o in viste if adatta(o) and not (o.carta.tipi & set(d.get("non_tipi") or ())) and (d.get("forza_max") is None or ("creature" in o.carta.tipi
                                                                               and (o.carta.car.get("forza") or 0) <= d["forza_max"]))]   # 208.1: in grimorio
    if d.get("mv_max") is not None: adatte = [o for o in adatte if M.valore(o.carta.car.get("costo") or "") <= d["mv_max"]]   # 202.3
    if d.get("dove") == "campo": adatte = [o for o in adatte if not o.carta.tipi & {"instant", "sorcery"}]   # 400.4a
    quanti = d.get("quanti", 1)
    if quanti == "tutte":                                                                          # «any number of»: chi non sceglie le
        sc = list(_scelta(p, ctrl, "guarda_cima_n", viste, adatte, len(adatte), predefinita=list(adatte)) or [])   # prende tutte
        if any(o not in adatte for o in sc) or len({id(o) for o in sc}) != len(sc): sc = list(adatte)
        prese = sc
    elif quanti == 1:
        sc = _scelta(p, ctrl, "guarda_cima", viste, adatte, predefinita=adatte[0] if adatte else None)
        if sc is not None and sc not in adatte: sc = adatte[0] if adatte else None
        if sc is None and not d.get("puoi") and adatte: sc = adatte[0]
        prese = [sc] if sc is not None else []
    else:                                                                                          # «put two of them», «up to two»
        sc = list(_scelta(p, ctrl, "guarda_cima_n", viste, adatte, quanti, predefinita=adatte[:quanti]) or [])
        if len(sc) > quanti or any(o not in adatte for o in sc) or len({id(o) for o in sc}) != len(sc): sc = adatte[:quanti]
        if not d.get("puoi") and len(sc) < min(quanti, len(adatte)): sc = adatte[:quanti]
        prese = sc
    for o in viste: gr.carte.remove(o)
    if d.get("dove") == "cima":                                                                    # «you may put one of those cards back on top»
        for o in prese: gr.metti(o, "cima")
    elif d.get("dove") == "campo":                                                                 # «onto the battlefield [tapped]»
        for o in prese:
            nuovo = p.t._arriva(o, "grimorio", "campo", ctrl, None, "701.20a")
            if d.get("tappata") and nuovo is not None: nuovo.tappato = True
    else:
        for o in prese: p.t._arriva(o, "grimorio", "mano", None, None, "701.20a")
    resto = [o for o in viste if not any(o is x for x in prese)]
    if d.get("resto") == "cimitero":
        for o in resto: p.t._arriva(o, "grimorio", "cimitero", None, None, "401.4")
    elif d.get("resto") == "mescola":                                                              # «then shuffle» (701.24a)
        for o in resto: gr.metti(o, "cima")
        gr.mescola()
    else:
        for j in gr.rng.permutation(len(resto)): gr.metti(resto[int(j)], "fondo")                  # «in a random order»
    return bool(prese)                                                                             # «this way» (608.2c)


def _i_attacca(p, d, chi, ctrl, fonte, ogg):
    """702.6a: «attach this permanent to target creature you control»."""
    for x in chi: p.t.attacca(fonte, x)


def _i_prepara(p, d, chi, ctrl, fonte, ogg):
    for x in chi: p.t.prepara(x)


def _i_terra_in_piu(p, d, chi, ctrl, fonte, ogg):
    """305.2: «you may play an additional land this turn»."""
    for j in chi: p.terre_in_piu[(j, p.t.turno_numero)] += 1


def _i_sprepara(p, d, chi, ctrl, fonte, ogg):
    """723.3b: «becomes unprepared»."""
    for x in chi:
        if getattr(x, "preparato", False):
            x.preparato = False
            p.t._evento("sprepara", carta=x.carta, vecchio=x.n, causa="723.3b")


def _i_segnalini_della_fonte(p, d, chi, ctrl, fonte, ogg):
    """«put its counters on ...»: i segnalini che la fonte aveva (608.2h: le ultime informazioni)."""
    for x in chi:
        for tipo, n in list(fonte.segnalini.items()):
            if n > 0: p.t.metti_segnalini(x, tipo, n)


def _i_in_grimorio(p, d, chi, ctrl, fonte, ogg):
    """«puts it on their choice of the top or bottom of their library»: sceglie il proprietario (400.3)."""
    for x in chi:
        if not (x.vivo and x.zona == "campo"): continue
        dove = _scelta(p, x.proprietario, "cima_o_fondo", x, predefinita="cima")
        p.t.sposta(x, "grimorio", posizione="fondo" if dove == "fondo" else "cima", causa="401.4")


def _i_esilia_e_cerca(p, d, chi, ctrl, fonte, ogg):
    """«You may exile this spell and N cards named ~ from your graveyard. If you do, search your library for a [tipo] card,
    put it onto the battlefield, then shuffle»: se non ci sono N carte con quel nome, l'opzione non si puo' scegliere
    (608.2d); se si', si esiliano insieme (608.2f), poi si cerca (701.23a) e si mescola (701.24b)."""
    g = p.t.giocatori[ctrl]
    stesse = [o for o in g.cimitero if o.nome == ogg.nome]
    if len(stesse) < d["n"] or not (ogg.vivo and ogg.zona == "pila"): return
    with p.t.insieme():
        p.t.esilia(ogg, causa="701.13a")
        for o in stesse[:d["n"]]: p.t.esilia(o, causa="701.13a")
    adatta = lambda o: all(w in o.carta.tipo for w in d["tipo"])
    p.t.cerca(ctrl, adatta, 1, verso="campo", chi=ctrl, causa="701.23a")


def _i_paga(p, d, chi, ctrl, fonte, ogg):
    """«You may pay {2}»: si paga con le abilita' di mana (608.2g), se si puo'. -> True se pagato. 106.6: e' un costo, non
    una magia: il mana vincolato «solo per lanciare ...» non lo paga e resta nella riserva col suo vincolo."""
    with p.pagando(("abilita'",)):
        scelto = p._scegli_pagamento(ctrl, d["costo"])
        if scelto is None: return False
        p._paga(ctrl, ogg, d["costo"], 0, scelto)
    p.pagati_abilita.append((d["costo"], scelto[0], 0, scelto[2], scelto[3]))
    return True


def _i_riflessa(p, d, chi, ctrl, fonte, ogg):
    """603.12: «When you do, ...»: un'abilita' innescata riflessa, che si innesca subito se l'azione e' stata fatta e va in
    pila la prossima volta che un giocatore riceverebbe la priorita' (603.3), coi suoi bersagli. «When you discard one or
    more nonland cards this way, tap up to that many target creatures» (Seasoned Cryomancer): si innesca una volta se lo
    scarto di questa risoluzione ne conta almeno una (603.12, 603.2c), e «that many» e' quel numero, gia' noto quando si
    innesca: il massimo dei bersagli (601.2c, 115.6: anche zero)."""
    ab = d["ab"]
    if "conta" in d:
        n = p.conta(d["conta"], ctrl, fonte, ogg)
        if n < 1: return False
        ab = dict(ab, bersagli=[dict(r, quanti=n) if r.get("quanti") == "N" else r for r in ab.get("bersagli") or []])
    elif not p._fatto: return False
    if ab.get("se"):                                                                               # 603.4: il «se» della riflessa, quando
        prima_ = (p._fonte_condizione, p._evento_condizione)                                       # scatta (e di nuovo alla risoluzione)
        p._fonte_condizione, p._evento_condizione = fonte, None
        try: ok_ = condizione(p, ab["se"], ctrl)
        finally: p._fonte_condizione, p._evento_condizione = prima_
        if not ok_: return False
    inn = Innesco(fonte, None, ab, ctrl, None)
    p.in_attesa.append(inn)
    p.diario_inneschi.append(inn)
    return True


def _i_sacrifica_fonte(p, d, chi, ctrl, fonte, ogg):
    for x in chi: p.t.sacrifica(x, x.controllore, causa="701.21a")


def _i_stordisci(p, d, chi, ctrl, fonte, ogg):
    n = ogg.x if d.get("n") == "X" else d.get("n", 1)                                              # 107.3k: la X del costo
    for x in chi: p.t.metti_segnalini(x, "stordimento", n, causa="122.1d")


# nome -> (regola, funzione)
ISTRUZIONI = {"pesca": ("121.1", _i_pesca), "guadagna": ("119.3", _i_guadagna), "perde": ("119.3", _i_perde),
              "danno": ("120.2b", _i_danno), "distruggi": ("701.8a", _i_distruggi), "esilia": ("701.13a", _i_esilia),
              "rimbalza": ("400.3", _i_rimbalza), "tappa": ("701.26a", _i_tappa), "stappa": ("701.26b", _i_stappa),
              "segnalini": ("122.1a", _i_segnalini),
              "pompa": ("613.4c", _continuo("7c", lambda d: {"p": d.get("p", 0), "t": d.get("t", 0)})),
              "moltiplica_fc": ("701.10b", _i_moltiplica_fc),
              "base": ("613.4b", _continuo("7b", lambda d: {"p": d["p"], "t": d["t"]})),
              "diventa_tipo": ("613.1d", _continuo("4", lambda d: {"tipi": d.get("tipi") or [], "sottotipi": d.get("sottotipi") or []})),
              "scambia": ("613.4d", _continuo("7d", lambda d: {"scambia": True})),
              "dai_parole": ("613.1f", _continuo("6", _parole_date)),
              "dai_abilita_fino": ("613.1f", _continuo("6", lambda d: {"dai_abilita": d["abilita"]})),   # 15 nov 2026: «gains "..."»
              "togli_abilita": ("613.1f", _continuo("6", lambda d: {"toglie": "tutte"})),
              "contrasta": ("701.6a", _i_contrasta), "contrasta_salvo": ("702.21a", _i_contrasta_salvo),
              "surveil": ("701.25a", _i_surveil), "scry": ("701.22a", _i_scry), "macina": ("701.17a", _i_macina),
              "scarta": ("701.9a", _i_scarta), "pedina": ("111.2", _i_pedina), "empower_jace": ("701.71a", _i_empower),
              "lotta": ("701.14a", _i_lotta), "danno_forza": ("120.2b", _i_danno_forza),
              "aggiungi_mana": ("106.4", _i_aggiungi_mana), "sacrifica": ("701.21a", _i_sacrifica),
              "ritorna": ("400.7", _i_ritorna), "stordisci": ("122.1d", _i_stordisci), "cerca": ("701.23a", _i_cerca), "ritardata_muore": ("603.7", _i_ritardata_muore),
              "sacrifica_questo": ("701.21a", _i_sacrifica_fonte), "attacca": ("701.3a", _i_attacca),
              "prepara": ("723.3a", _i_prepara), "terra_in_piu": ("305.2", _i_terra_in_piu),
              "guarda_cima_prendi": ("701.20a", _i_guarda_cima_prendi),
              "dalla_mano_in_campo": ("305.4", _i_dalla_mano_in_campo), "dal_cimitero_in_mano": ("400.7", _i_dal_cimitero_in_mano),
              "paga_vite": ("119.4", _i_paga_vite), "prendi_controllo": ("613.1b", _i_prendi_controllo),
              "non_blocca": ("509.1b", _continuo("regola", lambda d: {"non_blocca": True})),
              "attacca_con_difensore": ("702.3b", _continuo("regola", lambda d: {"attacca_con_difensore": True})),   # (giro 12)
              "sprepara": ("723.3b", _i_sprepara), "danno_fedelta": ("120.2b", _i_danno_fedelta),
              "segnalini_della_fonte": ("122.1", _i_segnalini_della_fonte), "in_grimorio": ("401.4", _i_in_grimorio),
              "esilia_e_cerca": ("608.2d", _i_esilia_e_cerca), "paga": ("608.2g", _i_paga), "riflessa": ("603.12", _i_riflessa),
              "non_bloccabile": ("509.1b", _continuo("regola", lambda d: {"non_bloccabile": True})),
              "parola_scelta": ("608.2d", _i_parola_scelta), "prendi_tra_macinate": ("608.2c", _i_prendi_tra_macinate),
              "togli_segnalini_scelti": ("122.1", _i_togli_segnalini_scelti), "cima_o_fondo": ("401.4", _i_cima_o_fondo),
              "vinci": ("104.2b", _i_vinci), "mescola_nel_grimorio": ("701.24a", _i_mescola_nel_grimorio),
              "esilia_finche": ("610.3", _i_esilia_finche), "scarta_scelta_da_te": ("701.9b", _i_scarta_scelta_da_te),
              "riprendi_sorvegliata": ("608.2c", _i_riprendi_sorvegliata), "ritorna_esiliata": ("400.7", _i_ritorna_esiliata),
              "emblema": ("114.2", _i_emblema), "ritardata": ("603.7", _i_ritardata),
              "esilia_tranne_fondo": ("701.13a", _i_esilia_tranne_fondo), "copia_magia": ("707.10", _i_copia_magia),
              "togli_segnalini": ("122.1", _i_togli_segnalini), "ritorna_tutte": ("400.7", _i_ritorna_tutte),
              "in_fondo": ("401.4", _i_in_fondo), "esilia_se_muore": ("614.1a", _i_esilia_se_muore), "scegli_tipo": ("205.3m", _i_scegli_tipo), "sacrifica_ritardata": ("603.7", _i_sacrifica_ritardata), "scopri": ("701.57a", _i_scopri), "distribuisci_segnalini": ("601.2d", _i_distribuisci_segnalini),
              "sacrifica_oggetti": ("701.21a", _i_sacrifica_oggetti), "scarta_salvo": ("701.9a", _i_scarta_salvo), "scarta_poi_pesca": ("701.9a", _i_scarta_poi_pesca), "raddoppia_segnalini": ("701.10e", _i_raddoppia_segnalini), "esilia_fino_non_terra": ("701.13a", _i_esilia_fino_non_terra), "in_mano_esiliata": ("400.7", _i_in_mano_esiliata), "rianima_tutte": ("400.7", _i_rianima_tutte), "trama": ("701.50a", _i_trama), "gira_faccia": ("701.27a", _i_gira_faccia), "ruota_scelta": ("101.4", _i_ruota_scelta),
              "dai_flashback": ("702.34a", _i_dai_flashback), "ritorna_esiliata_tua": ("603.7", _i_ritorna_esiliata_tua), "rimetti_esiliate": ("603.7c", _i_rimetti_esiliate),
              "rivela_fino": ("701.20a", _i_rivela_fino), "distruggi_tranne_tipo": ("701.8a", _i_distruggi_tranne_tipo),
              "prolifera": ("701.34a", _i_prolifera), "esilia_cima": ("701.13a", _i_esilia_cima),
              "copia_pedina": ("707.2", _i_copia_pedina),
              "diventa_copia": ("707.2", _i_diventa_copia), "senza_leggenda": ("704.5j", _i_senza_leggenda),
              "permesso_gioca": ("601.3", _i_permesso_gioca), "lancia_esiliata": ("608.2g", _i_lancia_esiliata),
              "dai_mana": ("613.1f", _i_dai_mana), "permesso_questa": ("601.3", _i_permesso_questa),
              "fedelta_rapida": ("606.3", _i_fedelta_rapida), "esilia_scelta_da_te": ("607.2a", _i_esilia_scelta_da_te),
              "mana_in_piu": ("605.4a", _i_mana_in_piu), "dal_fuori": ("400.11b", _i_dal_fuori),
              "esilia_e_lancia_copie": ("707.12", _i_esilia_e_lancia_copie),
              "prossima_incontrastabile": ("101.2", _i_prossima_incontrastabile)}


def condizione(p, cond, ctrl):
    """Le condizioni di un «se» (603.4): vite_almeno, creature_almeno (del controllore)."""
    for k, v in cond.items():
        if k == "segnalini_fonte_almeno":                                                          # 603.4: «if this enchantment has N or
            if not (p._fonte_condizione is not None and segnalini_ok(p._fonte_condizione, v)): return False   # more quest counters»
            continue
        if k == "uscito_tuo_turno":                                                                # «if a permanent left the battlefield
            fatto_ = any(e.tipo == "zona" and e.da == "campo" and getattr(p.t.oggetti.get(e.vecchio), "controllore", None) == ctrl   # under your
                         for e in p.t.eventi_del_turno())                                          # control this turn» (603.4)
            if fatto_ != v: return False
            continue
        if k == "facoltativo_pagato":                                                              # 702.33d: «if it was kicked»
            if bool(getattr(p._fonte_condizione, "facoltativo_pagato", False)) != v: return False
            continue
        if k == "mana_speso_simboli":                                                              # 601.2h: «if {W}{W} was spent to cast it»
            if speso_simboli(p.t, getattr(p._fonte_condizione, "n", None), v) is not True: return False
            continue
        if k == "mana_speso_almeno":                                                               # 601.2h: la magia che l'ha fatto scattare
            if mana_speso(p.t, getattr(getattr(p, "_evento_condizione", None), "vecchio", None))[0] < v: return False
            continue
        if k == "vite_almeno":
            if p.t.giocatori[ctrl].vite < v: return False
        elif k == "non_preparato":
            if getattr(p._fonte_condizione, "preparato", False) == v: return False
        elif k == "creature_almeno":
            if sum(1 for o in p.t.campo if o.controllore == ctrl and "creature" in o.carta.tipi) < v: return False
        elif k == "non_lanciato_turno":                                                            # «if you didn't cast a spell this turn»
            if any(e_.tipo == "lanciata" and e_.giocatore == ctrl for e_ in p._eventi_del_turno()) == v: return False
        elif k == "terre_almeno":                                                                  # «if you control six or more lands»
            if sum(1 for o in p.t.campo if o.controllore == ctrl and "land" in o.carta.tipi) < v: return False
        elif k == "morte_turno_almeno":                                                            # «if two or more creatures died this turn» (700.4)
            if sum(1 for e_ in p._eventi_del_turno() if e_.tipo == "zona" and e_.da == "campo" and e_.a == "cimitero"
                   and e_.carta is not None and "creature" in e_.carta.tipi) < v: return False
        elif k == "foreste_altre_almeno":                                                          # «if you control at least five other Forests»
            nuovo = getattr(getattr(p, "_evento_condizione", None), "nuovo", None)
            if sum(1 for o in p.t.campo if o.controllore == ctrl and o.n != nuovo and "Forest" in o.carta.tipo.split("—")[-1].split()) < v: return False
        elif k == "avversario_danno_nc_ultimo_turno":                                              # «last turn»: il turno prima
            inizi = [j for j, e_ in enumerate(p.t.eventi) if e_.tipo == "turno"]
            prima_ = p.t.eventi[inizi[-2]:inizi[-1]] if len(inizi) >= 2 else []
            if any(e_.tipo == "danno" and e_.nuovo is None and e_.causa != "510.2" and e_.giocatore != ctrl for e_ in prima_) != v: return False
        elif k == "pescate_turno_almeno":                                                          # «if you've drawn three or more cards this turn»
            if sum(1 for e_ in p._eventi_del_turno() if e_.tipo == "zona" and e_.da == "grimorio" and e_.a == "mano"
                   and e_.giocatore == ctrl and e_.causa in ("121.1", "504.1")) < v: return False   # 121.1, 504.1: pescare (non cercare)
        elif k == "vita_guadagnata_turno":                                                         # «if you gained life this turn»
            if bool(p.conta({"tipo": "vita_guadagnata_turno"}, ctrl, None, None)) != v: return False
        elif k == "fedelta_attivata_turno":                                                        # «if you've activated a loyalty ability this turn» (606)
            if any(e_.tipo == "attivata" and e_.a == "fedelta" and e_.giocatore == ctrl for e_ in p._eventi_del_turno()) != v: return False
        elif k == "fonte_non_pedina":                                                              # «if it isn't a token» (111.1)
            if bool(getattr(getattr(p._fonte_condizione, "carta", None), "pedina", False)) == v: return False
        elif k == "lanciata_tu":                                                                   # «if you cast it» (603.4): e' arrivato
            if (getattr(p._fonte_condizione, "lanciata_da", None) == ctrl) != v: return False       # in campo da una magia lanciata da te
        elif k == "senza_planeswalker":                                                            # «if you don't control a planeswalker»
            if any(o.controllore == ctrl and "planeswalker" in o.carta.tipi for o in p.t.campo) == v: return False
        elif k == "attaccato_turno":                                                               # «if you attacked this turn» (raid)
            if any(e_.tipo == "attacca" and e_.giocatore == ctrl for e_ in p._eventi_del_turno()) != v: return False
        elif k == "tuo_turno":                                                                     # «during your turn»
            if (p.attivo == ctrl) != v: return False
        elif k == "scelta_entrata":                                                                # 614.12, 607.2: la parte scelta entrando
            if getattr(p._fonte_condizione, "scelta_entrata", None) != v: return False
        elif k == "controlli_cond":                                                                # 603.4: «if you control another Elf»
            if sum(1 for o in p.t.campo if o.controllore == ctrl and scelto(v["sel"], o, p._fonte_condizione, ctrl)) < v["n"]: return False
        elif k == "cimitero_almeno":                                                               # «if there are N or more cards in your
            if len(p.t.giocatori[ctrl].cimitero) < v: return False                                 # graveyard» (603.4)
        elif k == "morta_avversario_turno":                                                        # «under an opponent's control» (700.4)
            if any(e_.tipo == "zona" and e_.da == "campo" and e_.a == "cimitero" and e_.carta is not None
                   and "creature" in e_.carta.tipi and getattr(p.t.oggetti.get(e_.vecchio), "controllore", ctrl) != ctrl
                   for e_ in p._eventi_del_turno()) != v: return False
        elif k == "morta_tua_turno":                                                               # «if a creature died under your control
            if any(e_.tipo == "zona" and e_.da == "campo" and e_.a == "cimitero" and e_.carta is not None   # this turn» (700.4: chi la
                   and "creature" in e_.carta.tipi and getattr(p.t.oggetti.get(e_.vecchio), "controllore", None) == ctrl
                   for e_ in p._eventi_del_turno()) != v: return False                              # controllava, non il proprietario)
        elif k == "attaccato_ora":                                                                 # «if a creature is attacking you» (506.4)
            if any(d == ctrl and o.vivo and o.zona == "campo" for o, d in (getattr(p, "attaccanti", {}) or {}).items()) != v: return False
        elif k == "lanciate_turno_almeno":                                                         # «if you've cast another spell this turn»
            if sum(1 for e_ in p._eventi_del_turno() if e_.tipo == "lanciata" and e_.giocatore == ctrl) < v: return False
        elif k == "creature_avversari_almeno":                                                     # «if your opponents control three or more creatures»
            if sum(1 for o in p.t.campo if o.controllore != ctrl and "creature" in o.carta.tipi) < v: return False
        elif k == "vita_guadagnata_turno_almeno":                                                  # «if you've gained N or more life this turn»
            if p.conta({"tipo": "vita_guadagnata_turno"}, ctrl, None, None) < v: return False
        elif k == "lasciato_cimitero_turno":                                                       # «if one or more cards left your graveyard this turn»
            if any(e_.tipo == "zona" and e_.da == "cimitero" and e_.carta is not None and e_.carta.proprietario == ctrl
                   for e_ in p._eventi_del_turno()) != v: return False
        elif k == "costituzione_totale_almeno":                                                    # «total toughness 10 or greater»
            if sum(costituzione(o) for o in p.t.campo if o.controllore == ctrl and "creature" in o.carta.tipi) < v: return False
        elif k == "controlli_sottotipo":                                                           # «if you control a Kithkin» (205.3, 702.73a)
            if not any(o.controllore == ctrl and ha_sottotipo(o, v) for o in p.t.campo): return False
        elif k in SE_SET:                                                                          # la condizione di un set
            if not SE_SET[k](p, v, ctrl): return False
        else: raise NonCoperto(f"603.4: la condizione {k!r} non e' coperta")
    return True


# ====================================================================== le scelte di chi non sceglie
OSTILI = {"danno", "distruggi", "esilia", "rimbalza", "tappa", "contrasta", "togli_abilita", "base"}


TIPI_NON_TERRA = TIPI_DI_CARTA & {"artifact", "battle", "creature", "enchantment", "instant", "kindred", "planeswalker", "sorcery"}


def uno_per_tipo(gruppo):
    """«up to one target nonland card of each card type» (Uldaros Theorix): carte diverse (115.3), e si puo' dare a ognuna
    un tipo di carta suo diverso da quello delle altre. Una carta con piu' tipi rappresenta uno qualsiasi dei suoi: e' la
    lettura delle ruling di Wizards sulle carte con «of each [permanent] type» (Liliana, Dreadhorde General, 12 gen 2024;
    Cataclysm, 4 ott 2004); su Uldaros una ruling apposta non c'e' (14 ott 2026): lettura confermata da Autore il
    14 ott 2026 alle 12:04. I tipi: la ruling di Grime Gorger."""
    tipi = [sorted(x.carta.tipi & TIPI_NON_TERRA) for x in gruppo]
    def assegna(k, usati):
        if k == len(tipi): return True
        return any(assegna(k + 1, usati | {t}) for t in tipi[k] if t not in usati)
    return assegna(0, frozenset())


def bersagli_semplici(p, i, oggetto, reqs, legali, fa=()):
    """Per ogni bersaglio richiesto i primi legali: dell'avversario se l'effetto fa male, propri se aiuta. E' la scelta
    di un giocatore finto, non una regola."""
    ostile = any(d.get("fa") in OSTILI or (d.get("fa") == "segnalini" and d.get("tipo") == "-1/-1") for d in fa)
    out = []
    for r, lst in zip(reqs, legali):
        mio = lambda x: (x == i) if _e_giocatore(x) else (x.controllore == i)
        ordinati = sorted(lst, key=lambda x: (mio(x) if ostile else not mio(x), not _e_giocatore(x)))
        if r.get("fino_a") and ostile: ordinati = [x for x in ordinati if not mio(x)]
        if r.get("uno_per_tipo"):                                                                  # una per tipo: si tengono quelle che ci stanno
            scelti = []
            for x in ordinati:
                if len(scelti) < r.get("quanti", 1) and uno_per_tipo(scelti + [x]): scelti.append(x)
            out.append(scelti); continue
        if r.get("stesso_cimitero") and ordinati:                                                  # tutte dal cimitero della prima
            ordinati = [x for x in ordinati if x.proprietario == ordinati[0].proprietario]
        out.append(ordinati[:r.get("quanti", 1)])
    return out


# ====================================================================== la partita
class Partita(C.Partita):
    """La partita del passo 6 con le abilita', gli inneschi, i bersagli e gli effetti continui."""

    def __init__(self, t):
        if not isinstance(t, TavoloEffetti): raise TypeError("il passo 7 vuole un TavoloEffetti")
        super().__init__(t)
        self.collega_tavolo()
        self.fedelta_usate = set()        # (oggetto, turno): 606.3
        self.diario_inneschi = []         # ogni innesco, con l'esito
        self.pagati_abilita = []          # (costo, Pagamento, x, fonti, riserva) delle abilita' attivate
        self.messe_insieme = []           # per ogni giro di 603.3b, i controllori nell'ordine in cui sono andati in pila
        self.una_volta = set()            # (fonte, abilita', turno) degli inneschi «only once each turn»
        self.incontrastabile = {}         # (giocatore, turno): la prossima magia che lancia in quel turno non si contrasta
        self.ritardate = []               # 603.7: le abilita' innescate ritardate con la loro durata
        self.esauste = set()              # 702.177a: (oggetto, abilita') exhaust gia' attivate
        self._opzione_costo, self._da_pagare_ancora = {}, None   # 601.2b: il costo aggiuntivo scelto, e cio' che resta da pagare
        self._facoltativo, self._facoltativo_resto = {}, None    # 601.2b, 702.33a: il costo facoltativo (kicker) scelto, e il resto
        self.vincolato = {g.i: [] for g in t.giocatori}   # 106.6: (indice del tipo, vincolo) per ogni mana vincolato nella riserva
        self._spesa = None                                # per cosa si sta pagando: ("magia", carta, dalla mano) o ("abilita'",)
        self._bersagli_iniziali, self._in_risoluzione = [], None
        self._fonte_condizione = None
        self._ultimo_conto = 0
        self._ultime_distrutte = []       # 701.8a (giro 12): le carte che l'ultimo «destroy» ha messo nel cimitero
        self.terre_in_piu = Counter()     # (giocatore, turno) -> terre in piu' (305.2)
        self.permessi = []                # 601.3: le carte in esilio che un giocatore puo' giocare, e fino a quando
        self._lancio_risoluzione = None   # 608.2g: l'oggetto che si sta lanciando durante una risoluzione
        self.fedelta_rapide = set()       # 606.3: (giocatore, sottotipo) che fino a fine turno attiva la fedelta' come un istantaneo
        self.costi_magie = []             # 601.2f: (costo totale fissato, Pagamento, x, fonti, riserva) di ogni magia lanciata
        self.mana_da_effetti = 0          # 106.4: il mana che le istruzioni «add ...» hanno messo nelle riserve
        self.mana_in_piu = []             # 605.4a: (giocatore, sottotipo, mana) delle abilita' di mana ritardate fino a fine turno
        self._alternativo = {}            # 118.9, 601.2b: il costo alternativo annunciato per la magia che si sta lanciando

    def collega_tavolo(self):
        """Il tavolo chiama la partita per gli eventi (gli inneschi) e per le scelte dei giocatori. Una copia della partita
        (copy.deepcopy, passo 8.6: guarda_avanti.copia) si ricollega qui: la lambda di `scegli` non si copia, resterebbe
        legata alla partita vecchia e farebbe scegliere i suoi giocatori."""
        t = self.t
        t.osservatore = self._osserva
        t._partita = self                                                                          # 704.5s: i capitoli in attesa
        t.scegli = lambda nome, j, *arg, predefinita: _scelta(self, j, nome, *arg, predefinita=predefinita)

    # ------------------------------------------------------------------ gli inneschi (603)
    def _fonti(self, e, prima):
        """603.10a: per chi lascia il campo gli oggetti e le abilita' di subito prima; 603.6a: per gli altri eventi i
        permanenti di adesso, nuovi compresi."""
        if self._guarda_indietro(e) and prima is not None:
            for o, v in prima.items():
                if _ha_inneschi(o): yield o, v["abilita"]
        else:
            for o in list(self.t.campo):
                if _ha_inneschi(o): yield o, self.t.abilita_di(o)
        for o in self.t.emblemi: yield o, list(enumerate(o.carta.car.get("abilita") or []))       # 114.4: dalla zona di comando
        if not self._guarda_indietro(e):
            for g in self.t.giocatori:                                                             # 113.6m: «return this card from your graveyard»
                for o in list(g.cimitero):
                    ab = [(k, a) for k, a in enumerate(o.carta.car.get("abilita") or []) if a.get("tipo") == "innescata" and a.get("zona") == "cimitero"]
                    if ab: yield o, ab
        if e.tipo == "lanciata":                                                                   # 113.6k, 601.2i: dalla pila
            x = self.t.oggetti.get(e.vecchio)
            if x is not None and x.vivo and x.zona == "pila" and getattr(x, "carta", None) is not None:
                ab = [(k, a) for k, a in enumerate(x.carta.car.get("abilita") or [])
                      if a.get("tipo") == "innescata" and a["quando"]["evento"] == "lanci_questa"]
                if ab: yield x, ab
        if e.tipo == "zona" and e.da == "mano" and e.a == "cimitero" and e.causa in SCARTI:          # 113.6k
            x = self.t.oggetti.get(e.nuovo)
            if x is not None and x.vivo and x.zona == "cimitero":
                ab = [(k, a) for k, a in enumerate(x.carta.car.get("abilita") or [])
                      if a.get("tipo") == "innescata" and a["quando"]["evento"] in ("scartata_questa", "ciclata_questa")]
                if ab: yield x, ab

    def _guarda_indietro(self, e):
        return e.tipo == "zona" and e.da == "campo"

    def _osserva(self, eventi, prima):
        for e in eventi:                                                                           # 800.4m: fino al suo prossimo turno
            if e.tipo == "turno":
                self.ritardate = [r for r in self.ritardate if not (r["fino"] == "prossimo_turno" and r["ctrl"] == e.giocatore)]
                self._scadono_permessi(e.giocatore)
        eventi = [e for e in eventi if e.tipo in TIPI_EVENTO]
        if not eventi: return
        self._osserva_ritardate(eventi)
        gia = {}                                                                                   # «one or more»: una volta per azione
        muti = any(ab.get("tipo") == "divieto" and ab.get("di") == "inneschi_entrata" for o in self.t.campo for _, ab in self.t.abilita_di(o))
        for e in eventi:
            if muti and e.tipo == "zona" and e.a == "campo":                                        # 101.2: niente inneschi da quell'entrata
                x_ = self.t.oggetti.get(e.nuovo)
                if x_ is not None and x_.carta.tipi & {"artifact", "creature"}: continue
            for f, abilita in self._fonti(e, prima):
                for k, ab in abilita:
                    if ab.get("tipo") != "innescata": continue
                    q = ab["quando"]
                    if q["evento"] not in QUANDO: raise NonCoperto(f"603.2: l'innesco {q['evento']!r} non e' coperto")
                    if q.get("una_per_azione") and (f.n, k) in gia:                                # lo stesso innesco: si ricorda l'evento
                        if QUANDO[q["evento"]][1](self, e, f, q): gia[(f.n, k)].eventi.append(e)
                        continue
                    if not QUANDO[q["evento"]][1](self, e, f, q): continue
                    ctrl = f.controllore if f.controllore is not None else f.proprietario         # 603.3a
                    self._fonte_condizione, self._evento_condizione = f, e
                    if "se" in ab and not condizione(self, ab["se"], ctrl): continue              # 603.4
                    if ab.get("una_volta_per_turno"):                                             # testo della carta, 603.1a
                        chiave = (f.n, k, self.t.turno_numero)
                        if chiave in self.una_volta: continue
                        self.una_volta.add(chiave)
                    inn = Innesco(f, k, ab, ctrl, e)
                    inn.eventi = [e]
                    gia[(f.n, k)] = inn
                    self.in_attesa.append(inn)
                    self.diario_inneschi.append(inn)

    def _scadono_permessi(self, chi_comincia):
        """611.2a: «until the end of your next turn»: il permesso vale fino alla fine del primo turno di chi lo ha avuto
        che comincia dopo l'effetto; quando comincia il turno dopo quello, e' finito (anche con turni in piu')."""
        resto = []
        for r in self.permessi:
            if r["fino"] == "finche_in_esilio":                                                    # 611.2b: finche' resta in esilio
                x = self.t.oggetti.get(r["n"])
                if x is not None and x.vivo and x.zona == "esilio": resto.append(r)
                continue
            if r["fino"] == "fine_turno": continue                                                  # 611.2a: «this turn», gia' finito
            if r["fino"] != "fine_prossimo_turno": raise NonCoperto(f"611.2a: la durata {r['fino']!r} di un permesso")
            if r["iniziato"]: continue
            if chi_comincia == r["giocatore"]: r["iniziato"] = True
            resto.append(r)
        self.permessi = resto

    def permesso(self, i, ogg):
        """601.3: un effetto permette a i di giocare questa carta dall'esilio adesso (400.7: lo stesso oggetto)."""
        return bool(getattr(ogg, "vivo", False) and ogg.zona == "esilio" and ogg.carta is not None
                    and (any(r["n"] == ogg.n and r["giocatore"] == i and self.t.turno_numero >= r.get("dal_turno", 0)
                             and (not r.get("solo_alternativo") or (self._alternativo.get(ogg.n) or {}).get("nome") == r["solo_alternativo"])   # 118.9: solo
                             for r in self.permessi)                                                         # «by paying X rather than»
                         or self._collegata(i, ogg) is not None))

    def _collegata(self, i, ogg):
        """607.2a, 611.3a, 601.3: «As long as there are seven or more cards in your graveyard, you may cast the exiled card»
        (Null Summoner): la statica di un permanente in campo sotto i, collegata alla carta che la sua abilita' ha esiliato,
        con la condizione vera adesso. -> l'abilita' statica, o None."""
        n = getattr(ogg, "esiliata_da", None)
        if n is None or not (getattr(ogg, "vivo", False) and ogg.zona == "esilio"): return None
        s = self.t.oggetti.get(n)
        if s is None or not (s.vivo and s.zona == "campo" and s.controllore == i): return None
        for _, ab in self.t.abilita_di(s):
            if ab.get("tipo") != "lancia_collegata": continue
            if set(ab) - {"tipo", "se", "mana_qualsiasi"}: raise NonCoperto(f"601.3: il permesso collegato {ab} non e' coperto")
            if self.t.condizione_statica(ab.get("se") or {}, s): return ab
        return None

    def puo_giocare_terra(self, i, ogg):
        """305.1, 116.2a, 305.2a-b: una terra in esilio con il permesso si gioca coi tempi e il limite di sempre."""
        if not self.permesso(i, ogg): return super().puo_giocare_terra(i, ogg)
        return (self.da_stregoneria(i) and "land" in ogg.carta.tipi
                and self.t.giocatori[i].terre_giocate < self._limite_terre(i))

    def lancia_in_risoluzione(self, i, ogg, x=0):
        """608.2g: lanciare durante la risoluzione, seguendo 601.2a-i: i tempi di 117.1a non contano (l'effetto lo
        permette adesso), i divieti si' (601.3, 702.61a), il costo si paga intero (601.2h); nessuno riceve la priorita'.
        Il giocatore sceglie X e il pagamento (`lancia_in_risoluzione` del giocatore -> (x, pagamento), None = no)."""
        g = (self.chi or {}).get(i)
        scelta = g.lancia_in_risoluzione(self, i, ogg) if hasattr(g, "lancia_in_risoluzione") else (x, None)
        if scelta is None: return None
        x, pagamento = scelta
        prima, self._lancio_risoluzione = self._lancio_risoluzione, ogg.n
        try: return self.lancia(i, ogg, x, pagamento)
        finally: self._lancio_risoluzione = prima

    def _osserva_ritardate(self, eventi):
        """603.7a-b: le ritardate guardano gli eventi venuti dopo la loro creazione; «one or more»: un innesco per azione,
        con tutti gli eventi che lo soddisfano (gli oggetti «those creatures»)."""
        for idx, r in enumerate(list(self.ritardate)):
            q = dict(r["ab"]["quando"], ctrl=r["ctrl"])
            if q["evento"] not in QUANDO: raise NonCoperto(f"603.7: l'innesco ritardato {q['evento']!r} non e' coperto")
            buoni = [e for e in eventi if e.n > r["dopo"] and QUANDO[q["evento"]][1](self, e, r["fonte"], q)]
            if not buoni: continue
            gruppi = [buoni] if q.get("una_per_azione") else [[e] for e in buoni]
            if r["ab"].get("una_volta"):                                                           # 603.7b: «when you next»: una volta sola
                gruppi = gruppi[:1]
                self.ritardate = [x for x in self.ritardate if x is not r]
            for gruppo in gruppi:
                inn = Innesco(r["fonte"], ("ritardata", idx), r["ab"], r["ctrl"], gruppo[0])
                inn.eventi = gruppo
                self.in_attesa.append(inn)
                self.diario_inneschi.append(inn)

    def _apnap(self):
        """101.4: l'attivo, poi gli altri in ordine di turno."""
        n = len(self.t.giocatori)
        return [(self.attivo + k) % n for k in range(n)]

    def _metti_inneschi(self):
        """603.3b: ognuno in ordine APNAP mette in pila i suoi, nell'ordine che sceglie (la seconda parte, gli inneschi su
        un'altra abilita' che si innesca, non c'e' nelle carte coperte)."""
        attesa, self.in_attesa = self.in_attesa, []
        giro = []
        for j in self._apnap():
            mie = [x for x in attesa if x.controllore == j]
            g = (self.chi or {}).get(j)
            if len(mie) > 1 and hasattr(g, "ordina"):
                scelta = list(g.ordina(self, j, list(mie)))
                if sorted(map(id, scelta)) == sorted(map(id, mie)): mie = scelta
            for inn in mie:
                if self._metti_innesco(inn): giro.append(j)
        self.messe_insieme.append(giro)

    def _metti_innesco(self, inn):
        """603.3, 603.3d: in pila, coi bersagli; senza bersagli legali si toglie."""
        t = self.t
        a = Abilita(next(t._oggetti), inn.fonte, inn.k, inn.ab, inn.controllore, "innescata", inn.evento)
        a.eventi = getattr(inn, "eventi", [inn.evento])
        pronto = False
        for _ in range(1000):
            pronto = self._prepara(inn.controllore, inn.ab, a, inn.fonte)
            if pronto is not False: break
        if pronto is False: raise RuntimeError(f"il giocatore {inn.controllore} propone solo scelte illegali per {inn}")
        if pronto is None:                                                                         # 603.3c-d
            inn.esito = "603.3d"
            t._evento("rimossa", carta=inn.fonte.carta, vecchio=a.n, giocatore=inn.controllore, causa="603.3d")
            return False
        a.reqs, a.fa, a.bersagli = pronto
        if inn.ab.get("quando", {}).get("evento") == "entra": a.x = getattr(inn.fonte, "x_magia", 0)    # 107.3m
        t.pila.append(a)
        if inn.ab.get("modi"): t._evento("dilemma", giocatore=inn.controllore, vecchio=a.n, causa="700.17")   # i modi scelti
        inn.esito, inn.abilita = "pila", a
        t._evento("abilita", carta=inn.fonte.carta, vecchio=a.n, a="pila", giocatore=inn.controllore, causa="603.3")
        self._segna_bersagli(a, inn.controllore)
        return True

    def priorita(self):
        """117.5, 603.3b, 704.3: le azioni di stato, poi gli inneschi in pila, e di nuovo, finche' non succede piu'
        niente. -> cosa e' successo (vuoto = niente: la pulizia non si ripete, 514.3a)."""
        fatte = list(self.t.azioni_di_stato())
        while self.in_attesa and not self.t.finita:
            self._metti_inneschi()
            fatte.append(("inneschi", None, "603.3b"))
            fatte += self.t.azioni_di_stato()
        return fatte

    # ------------------------------------------------------------------ i bersagli (115)
    def _hexproof_conta(self): return True

    def _leggi_attacco(self, i, scelta):
        out, m = super()._leggi_attacco(i, scelta)
        if out:
            quanti = Counter(b for b in out.values() if not _e_giocatore(b))
            for b, k in quanti.items():
                if k > 1 and self.t.regola("max_un_attaccante", b):
                    return None, "508.1c: non piu' di una creatura puo' attaccare questo planeswalker"
            if len(out) == 1 and self.t.regola("non_attacca_da_sola", next(iter(out))):              # 506.5, 508.1c (giro 11)
                return None, "506.5: la creatura non puo' attaccare da sola"
        return out, m

    def _leggi_blocco(self, d, scelta):
        out, m = super()._leggi_blocco(d, scelta)
        if out:                                                                                    # 509.1b: «can't be blocked by more
            for a, k in Counter(out.values()).items():                                             # than one creature»
                if k > 1 and self.t.regola("max_un_bloccante", a):
                    return None, "509.1b: la creatura non la blocca piu' di una creatura"
                if 0 < k < max(self.t.regola_valori("min_bloccanti", a), default=0):                 # 509.1b (giro 11)
                    return None, "509.1b: la bloccano solo tre o piu' creature"
        return out, m

    def _motivo_non_blocca(self, b, a, d):
        m = super()._motivo_non_blocca(b, a, d)
        if m is None and b.carta.car.get("non_blocca") and self.t.caratteristiche(b).get("mana_ok", True):   # «can't block»
            return "509.1b: la creatura non puo' bloccare"
        if m is None and self.t.regola("non_blocca", b): return "509.1b: un effetto dice che la creatura non puo' bloccare"
        if m is None and a in self.attaccanti and self.t.regola("blocca_solo_volanti", b) and "flying" not in parole(a):
            return "509.1b: blocca solo creature con volare"
        if m is None and a in self.attaccanti and any(not ha_sottotipo(a, v) for v in self.t.regola_valori("blocca_solo_tipo", b)):
            return "509.1b: non blocca le creature che non sono di quel tipo"
        if m is None and a in self.attaccanti and any(not ha_sottotipo(b, v) for v in self.t.regola_valori("non_bloccata_da_non_tipo", a)):
            return "509.1b: non la bloccano le creature che non sono di quel tipo"
        if m is None and a in self.attaccanti and any(ha_sottotipo(b, v) for v in self.t.regola_valori("non_bloccata_da_tipo", a)):
            return "509.1b: non la bloccano le creature di quel tipo"
        if m is None and a in self.attaccanti and any(forza(b) <= v for v in self.t.regola_valori("non_bloccata_da_forza_max", a)):
            return "509.1b: non la bloccano le creature con forza bassa"
        if m is None and a in self.attaccanti and getattr(b.carta, "pedina", False) and self.t.regola("non_bloccata_da_pedine", a):
            return "509.1b: non la bloccano le pedine"                                               # (giro 11)
        if m is None and a in self.attaccanti and forza(b) > forza(a) and self.t.regola("non_bloccata_da_piu_forti", a):
            return "509.1b: non la bloccano le creature con piu' forza"
        if m is None and a in self.attaccanti and self.t.regola("non_bloccabile", a):
            return "509.1b: un effetto dice che la creatura non puo' essere bloccata"
        return m

    def legale(self, r, x, i, oggetto, fonte):
        """115.2-115.5, 702.11b: x e' un bersaglio legale per la richiesta r di una magia o abilita' controllata da i?"""
        chi = set(r["chi"])
        if _e_giocatore(x):
            if not chi & {"player", "any"} or not (0 <= x < len(self.t.giocatori)) or self.t.giocatori[x].perso: return False
            if r.get("controllo") == "avversario" and x == i: return False
            if r.get("controllo") == "tuo" and x != i: return False
            return True
        if not getattr(x, "vivo", False) or x is oggetto: return False                              # 400.7, 115.5
        if r.get("zona") == "cimitero":                                                            # 115.2: «card in a graveyard»
            if x.zona != "cimitero" or x.carta is None: return False
            if r.get("tipi") and not set(r["tipi"]) & x.carta.tipi: return False
            if r.get("controllo") == "tuo" and x.proprietario != i: return False
            if r.get("leggendario") and "legendary" not in x.carta.tipi: return False
            if r.get("altra") and x is fonte: return False
            if "mv_max" in r and M.valore(x.carta.car.get("costo") or "") > r["mv_max"]: return False      # 202.3
            return True
        if "spell" in chi:                                                                         # 115.2: una magia
            if not (x.zona == "pila" and x.carta is not None and x is not oggetto): return False
            if r.get("tipi_o") and not set(r["tipi_o"]) & x.carta.tipi: return False              # «creature or legendary spell»
            if set(chi) - {"spell"} and not (set(chi) - {"spell"}) & x.carta.tipi: return False    # «creature spell»
            return filtri_ok(r, x)
        if x.zona != "campo" or x.carta is None: return False                                       # 115.2
        tipi = x.carta.tipi
        if "any" in chi:                                                                           # 115.4
            if "battle" in tipi: raise NonCoperto("115.4, 310: bersagliare una battaglia non e' coperto")
            if not tipi & {"creature", "planeswalker"}: return False
        elif "permanent" not in chi and not tipi & chi: return False
        if r.get("controllo") == "tuo" and x.controllore != i: return False
        if r.get("controllo") == "avversario" and x.controllore == i: return False
        if r.get("altra") and x is fonte: return False
        if not filtri_ok(r, x): return False
        if r.get("in_combattimento") and not (x in self.attaccanti or x in self.bloccanti): return False   # 506.4
        if r.get("attaccante_ora") and x not in self.attaccanti: return False                         # «target attacking creature» (506.4)
        if self._hexproof_conta() and "hexproof" in parole(x) and x.controllore != i: return False  # 702.11b
        return True

    def candidati(self, r, i, oggetto, fonte):
        out = []
        if set(r["chi"]) & {"player", "any"}: out += [g.i for g in self.t.giocatori if not g.perso]
        if r.get("zona") == "cimitero": zona = [o for g in self.t.giocatori for o in g.cimitero]          # 115.2: «card from a graveyard»
        else: zona = self.t.pila if "spell" in r["chi"] else self.t.campo
        return [x for x in out + list(zona) if self.legale(r, x, i, oggetto, fonte)]

    def _modo_possibile(self, i, modo, oggetto, fonte):
        """700.2a-b: un modo non si sceglie se non ci sono bersagli legali per lui."""
        return all(r.get("fino_a") or len(self.candidati(r, i, oggetto, fonte)) >= r.get("quanti", 1)
                   for r in modo.get("bersagli") or [])

    def _quanti_modi(self, prog, fonte=None):
        n = prog.get("scegli", 1)
        if isinstance(n, dict):                                                                    # 700.2, 601.2b: «choose both instead»
            n = n["facoltativo"] if self._facoltativo.get(getattr(fonte, "n", None)) else n["base"]   # col costo facoltativo pagato
        return (1, len(prog["modi"])) if n == "uno_o_piu" else (n, n)

    def programma_possibile(self, i, prog, fonte):
        if prog.get("modi"):
            minimo, _ = self._quanti_modi(prog, fonte)
            return sum(1 for m in prog["modi"] if self._modo_possibile(i, m, None, fonte)) >= minimo
        return all(r.get("fino_a") or len(self.candidati(r, i, None, fonte)) >= r.get("quanti", 1) for r in prog.get("bersagli") or [])

    def _prepara(self, i, prog, oggetto, fonte, bersagli=None, modi=None):
        """700.2a-b, 601.2b-c, 603.3c-d: i modi e poi i bersagli. -> (reqs, fa, bersagli), None se non si puo' (nessun
        modo o nessun bersaglio legale), False se la proposta e' illegale."""
        if prog.get("modi"):
            legali = [k for k, m in enumerate(prog["modi"]) if self._modo_possibile(i, m, oggetto, fonte)]
            minimo, massimo = self._quanti_modi(prog, fonte)
            if len(legali) < minimo: return None
            if modi is None:
                g = (self.chi or {}).get(i)
                f = getattr(g, "modi", None)
                modi = f(self, i, oggetto, prog["modi"], legali, minimo, massimo) if f else legali[:minimo]
            modi = list(modi)
            if not (minimo <= len(modi) <= massimo) or len(set(modi)) != len(modi) or any(k not in legali for k in modi):
                return False                                                                     # 700.2d
            reqs, fa = [], []
            for k in sorted(modi):                                                               # 700.2d: nell'ordine stampato
                m = prog["modi"][k]
                base = len(reqs)
                reqs += list(m.get("bersagli") or [])
                for d in m.get("fa") or []:
                    d = dict(d)
                    for campo in ("chi", "contro"):
                        v = d.get(campo)
                        if isinstance(v, str) and v.startswith(("bersaglio", "controllore_bersaglio")):
                            testa, _, k2 = v.partition(":")
                            d[campo] = f"{testa}:{base + int(k2 or 0)}"
                    fa.append(d)
            if oggetto is not None: oggetto.modi = sorted(modi)
            self._ultimi_modi = sorted(modi)                                                     # 601.2f: il costo dei modi scelti
        else:
            reqs, fa = list(prog.get("bersagli") or []), list(prog.get("fa") or [])
        scelta = []
        if reqs:
            scelta = self._scegli_bersagli(i, oggetto, reqs, bersagli, fonte, fa)
            if not scelta: return scelta
        return reqs, fa, scelta

    def _segna_bersagli(self, oggetto, i):
        """L'evento «diventa bersaglio» (702.21a) per ogni oggetto bersagliato."""
        for g in oggetto.bersagli:
            for x in g:
                if not _e_giocatore(x):
                    self.t._evento("bersagliato", carta=x.carta, vecchio=x.n, nuovo=oggetto.n, giocatore=i, causa="115.1")

    def _per_ogni_avversario(self, reqs):
        if any(r.get("per_ogni_avversario") for r in reqs) and len(self.t.giocatori) != 2:
            raise NonCoperto("«for each opponent»: con piu' di due giocatori non e' coperto")

    def _scegli_bersagli(self, i, oggetto, reqs, proposta, fonte, fa=()):
        """601.2c, 602.2b, 603.3d: un gruppo di bersagli per ogni parola «target», ognuno legale, senza ripetere (115.3).
        -> la scelta, None se non ci sono abbastanza bersagli legali, False se la proposta e' illegale."""
        self._per_ogni_avversario(reqs)
        legali = [self.candidati(r, i, oggetto, fonte) for r in reqs]
        if any(len(l) < r.get("quanti", 1) and not r.get("fino_a") for r, l in zip(reqs, legali)): return None
        if any(len(l) < r.get("minimo", 0) for r, l in zip(reqs, legali)): return None                # «one or two»: almeno uno
        if proposta is None:
            g = (self.chi or {}).get(i)
            f = getattr(g, "bersagli", None)
            proposta = f(self, i, oggetto, reqs, legali, fa) if f else bersagli_semplici(self, i, oggetto, reqs, legali, fa)
        if not isinstance(proposta, (list, tuple)) or len(proposta) != len(reqs): return False
        out = []
        for r, gruppo, lst in zip(reqs, proposta, legali):
            gruppo = list(gruppo) if isinstance(gruppo, (list, tuple)) else [gruppo]
            q = r.get("quanti", 1)
            if not (r.get("minimo", 0) <= len(gruppo) <= q if r.get("fino_a") else len(gruppo) == q): return False      # 115.6
            if len({id(x) if not _e_giocatore(x) else ("G", x) for x in gruppo}) != len(gruppo): return False   # 115.3
            if not all(any(x is y or (_e_giocatore(x) and _e_giocatore(y) and x == y) for y in lst) for x in gruppo): return False
            if r.get("uno_per_tipo") and not uno_per_tipo(gruppo): return False                    # «of each card type»
            if r.get("stesso_cimitero") and len({x.proprietario for x in gruppo}) > 1: return False   # «from a single graveyard»
            out.append(gruppo)
        return out

    def _ancora_legale(self, oggetto, r, x, ctrl, fonte):
        """608.2b: il bersaglio e' ancora nella zona di prima (e' lo stesso oggetto, 400.7) e ancora legale."""
        return self.legale(r, x, ctrl, oggetto, fonte)

    # ------------------------------------------------------------------ lanciare con i bersagli
    def _copia_preparata(self, i, ogg):
        """723.3c: la copia in esilio si lancia finche' il permanente resta in campo preparato, sotto chi lo controlla."""
        n = ogg.carta.car.get("copia_di")
        if n is None or not (ogg.vivo and ogg.zona == "esilio"): return False
        perm = self.t.oggetti.get(n)
        return bool(perm is not None and perm.vivo and perm.zona == "campo" and perm.controllore == i and getattr(perm, "preparato", False))

    def _da_zona_alternativo(self, i, ogg):
        """118.9, 601.2b: un costo alternativo di un set che lancia da un'altra zona (702.180a: harmonize dal cimitero)."""
        alt = self._alternativo.get(ogg.n)
        if not isinstance(alt, dict): return False
        z = (ALTERNATIVI_SET.get(alt["nome"]) or {}).get("zona")
        return z is not None and ogg.zona == z and ogg.proprietario == i

    def _dal_cimitero(self, i, ogg):
        """702.34a: con flashback si lancia dal cimitero un istantaneo o una stregoneria pagando il costo di flashback (e
        i costi in piu' scritti, 601.2f: «Discard a card»)."""
        dato = getattr(ogg, "flashback_dato", None) == self.t.turno_numero                          # «gains flashback until end of turn»
        if not (ogg.vivo and ogg in self.t.giocatori[i].cimitero and (ogg.carta.car.get("flashback") or dato) and ogg.carta.tipi & {"instant", "sorcery"}):
            return False
        return not ogg.carta.car.get("flashback_scarta") or bool(self.t.giocatori[i].mano)

    def _costo_di(self, i, ogg):
        """601.2f: il costo totale: quello stampato (o il flashback, 702.34a), piu' gli aumenti, meno le riduzioni; le
        riduzioni di mana generico toccano solo il generico (118.7a), e un costo ridotto a niente e' {0} (118.7)."""
        if self._alternativo.get(ogg.n) == "gratis": base = "{0}"                                  # 118.9: «without paying its mana cost»
        elif isinstance(self._alternativo.get(ogg.n), dict): base = self._alternativo[ogg.n]["costo"]   # 118.9: un costo alternativo scritto
        else: base = (ogg.carta.car.get("flashback") or ogg.carta.car.get("costo")) if self._dal_cimitero(i, ogg) else super()._costo_di(i, ogg)
        fac_ = ogg.carta.car.get("facoltativo")
        if base is not None and fac_ and fac_.get("mana") and self._facoltativo.get(ogg.n):         # 601.2f, 702.33a: il kicker si somma
            base = cambia_generico(base + fac_["mana"], 0)                                         # un generico solo («{1}{G}{2}{G}»: «{3}{G}{G}»)
        if base is None: return None                                                               # (118.9d: aumenti e riduzioni si
                                                                                                   # applicano anche al costo alternativo)
        delta = self._modifica_costo(i, ogg)
        alt_ = self._alternativo.get(ogg.n)
        if isinstance(alt_, dict) and (ALTERNATIVI_SET.get(alt_["nome"]) or {}).get("riduzione"):     # 118.9d, 702.180a
            delta += ALTERNATIVI_SET[alt_["nome"]]["riduzione"](self, i, ogg, alt_)
        modi_ = [m_.get("costo_modo") for m_ in ogg.carta.car.get("modi") or []]
        if any(modi_):                                                                             # 601.2f, 702.183a: il costo del modo
            ml = getattr(self, "_modi_lancio", None)                                               # scelto (prima di sceglierlo: il piu'
            if ml is not None and ml[0] == ogg.n: agg = "".join(modi_[k_] or "" for k_ in ml[1])  # economico, che c'e' sempre)
            else: agg = min((c_ or "" for c_ in modi_), key=lambda c_: M.valore(c_) if c_ else 0)
            if agg and agg != "{0}": base = base + agg
        costo = cambia_generico(base, delta) if delta else base                                    # 601.2f: il costo vero, poi
        if self._alternativo.get(ogg.n) != "gratis" and not any(r["n"] == ogg.n and r["giocatore"] == i for r in self.permessi):
            ab = self._collegata(i, ogg)                                                           # 609.4b: come si paga
            if ab is not None and ab.get("mana_qualsiasi"): costo = mana_qualsiasi(costo)
        return costo

    def _modifica_costo(self, i, ogg):
        car, tipi, delta = ogg.carta.car, ogg.carta.tipi, 0
        for m in car.get("costo_mod") or []:                                                       # «This spell costs ... less»
            if m.get("se") == "leggendaria_tua" and not any(o.controllore == i and "creature" in o.carta.tipi and "legendary" in o.carta.tipi for o in self.t.campo): continue
            if m.get("se") == "noncreatura_lanciata" and not any(e_.tipo == "lanciata" and e_.giocatore == i and e_.carta is not None
                                                                 and "creature" not in e_.carta.tipi for e_ in self._eventi_del_turno()): continue
            if m.get("meno") == "per_artefatto":                                                     # 702.41a: affinity for artifacts
                delta -= sum(1 for o in self.t.campo if o.controllore == i and "artifact" in o.carta.tipi); continue
            if m.get("meno") == "per_sel":                                                           # 702.41a (giro 8): affinity for X
                delta -= sum(1 for o in self.t.campo if o.controllore == i and scelto(m["sel"], o, None, i)); continue
            if m.get("meno") == "forza_max":
                delta -= max([forza(o) for o in self.t.campo if o.controllore == i and "creature" in o.carta.tipi] or [0]); continue
            if m.get("meno") == "costituzione_max":
                delta -= max([costituzione(o) for o in self.t.campo if o.controllore == i and "creature" in o.carta.tipi] or [0]); continue
            if m.get("bersaglio") is not None:                                                       # 601.2f: «if it targets ...» (dopo 601.2c)
                bs = getattr(self, "_bersagli_lancio", None)
                if bs is not None:
                    vale = any(self._bersaglio_costo(m["bersaglio"], x) for g_ in bs for x in (g_ if isinstance(g_, (list, tuple)) else [g_]))
                else:                                                                                # prima dei bersagli: si puo' sceglierne
                    reqs_ = car.get("bersagli") or []                                                # uno che la fa valere (per una
                    cand = [x for x in (self.candidati(reqs_[0], i, None, ogg) if reqs_ else [])]    # riduzione), o non si puo' evitarla
                    ok_ = [self._bersaglio_costo(m["bersaglio"], x) for x in cand]                   # (per un aumento)
                    vale = any(ok_) if m["delta"] < 0 else (bool(ok_) and all(ok_))
                if vale: delta += m["delta"]
                continue
            if m.get("cond") is not None:                                                            # 601.2f: una condizione sullo stato
                if condizione(self, m["cond"], i): delta += m["delta"]
                continue
            if m.get("per") == "cimitero":                                                           # «for each ... card in your graveyard»
                cim = [o for o in self.t.giocatori[i].cimitero if (not m.get("tipi") or set(m["tipi"]) & o.carta.tipi)
                       and not set(m.get("non_tipi") or []) & o.carta.tipi]
                delta -= m["n"] * len(cim); continue
            if m.get("per") == "attaccanti":                                                         # «for each attacking creature» (506.4)
                delta -= m["n"] * len([o for o in getattr(self, "attaccanti", {}) if o.vivo and o.zona == "campo"]); continue
            if m.get("meno") == "terre_nomi":                                                        # 201.2: nomi diversi
                delta -= len({o.nome for o in self.t.campo if o.controllore == i and "land" in o.carta.tipi}); continue
            if m.get("meno") == "forza_totale":                                                      # «the total power of creatures you control»
                delta -= sum(max(0, forza(o)) for o in self.t.campo if o.controllore == i and "creature" in o.carta.tipi
                             and (not m.get("volanti") or "flying" in parole(o))); continue
            delta += m["delta"]
        op = self._opzione_costo.get(ogg.n)                                                         # 601.2f: il costo aggiuntivo
        if op and "mana" in op:
            if re.sub(r"\{\d+\}", "", op["mana"]): raise NonCoperto(f"601.2f: il costo aggiuntivo colorato {op['mana']}")
            delta += sum(int(v) for v in re.findall(r"\{(\d+)\}", op["mana"]))
        for o in self.t.campo:                                                                     # gli effetti dei permanenti
            for _, ab in self.t.abilita_di(o):
                if ab.get("tipo") != "costi": continue
                if (ab["di"] == "tuo") != (o.controllore == i): continue
                if ab.get("tipi") and not set(ab["tipi"]) & tipi: continue
                if ab.get("non_tipi") and set(ab["non_tipi"]) & tipi: continue
                if ab.get("sottotipi") and not any(ha_sottotipo(ogg, s_) for s_ in ab["sottotipi"]): continue   # «Dragon spells» (giro 8)
                if ab.get("colori") and not set(ab["colori"]) & set(M.colori(ogg.carta.car.get("costo") or "")): continue   # «Red spells» (105.2)
                delta += ab["delta"]
        return delta

    def _bersaglio_costo(self, b, x):
        """Il bersaglio x soddisfa «if it targets a tapped creature / an attacking creature / a Spider ...»."""
        if not hasattr(x, "carta") or x.zona != "campo": return False
        if b.get("tipi") and not set(b["tipi"]) & x.carta.tipi: return False
        if b.get("tappato") and not x.tappato: return False
        if b.get("attaccante") and x not in (getattr(self, "attaccanti", None) or {}): return False
        if b.get("bloccante") and x not in (getattr(self, "bloccanti", None) or {}): return False
        if b.get("non_pedina") and x.carta.pedina: return False
        if b.get("parola") and b["parola"] not in parole(x): return False
        if b.get("sottotipo") and not ha_sottotipo(x, b["sottotipo"]): return False
        return True

    def _opzione_pagabile(self, i, ogg, op):
        """Un costo aggiuntivo a scelta: si puo' scegliere solo se si puo' pagare (601.2b, 601.2h)."""
        if "sacrifica" in op: return bool(self._da_sacrificare(i, ogg, {"tipi": op["sacrifica"]}, altro=False))
        if "behold" in op:                                                                         # 701.4a: un Jace tuo o in mano
            st = op["behold"]
            return any(o.controllore == i and ha_sottotipo(o, st) for o in self.t.campo) or \
                any(o is not ogg and ha_sottotipo(o, st) for o in self.t.giocatori[i].mano)                # 702.73a: anche changeling
        if "scarta" in op: return len([o for o in self.t.giocatori[i].mano if o is not ogg]) >= op["scarta"]   # 601.2h: le altre carte
        if "vite" in op: return self.t.giocatori[i].vite >= op["vite"]                             # 119.4
        if set(op) & set(COSTI_SET):                                                               # il costo di un set (il suo posto)
            return all(COSTI_SET[k][0](self, i, ogg, v) for k, v in op.items() if k in COSTI_SET)
        if set(op) - {"mana"}: raise NonCoperto(f"601.2b: il costo aggiuntivo {op} non e' coperto")
        return True                                       # il mana in piu' lo controlla il costo totale (601.2f)

    def opzioni_costo(self, i, ogg, x=0):
        """601.2b: i costi aggiuntivi a scelta di una magia che si possono scegliere adesso (con quello, la magia si lancia)."""
        out = []
        for op in ogg.carta.car.get("costo_aggiuntivo") or []:
            if not self._opzione_pagabile(i, ogg, op): continue
            self._opzione_costo[ogg.n] = op
            try: ok = self._puo_lanciare_base(i, ogg, x)
            finally: self._opzione_costo.pop(ogg.n, None)
            if ok: out.append(op)
        return out

    def _divieto_combattimento(self):
        """101.2: un permanente dice che durante il combattimento non si lancia e non si attiva (le abilita' di mana si');
        702.61a: con in pila una magia con split second nemmeno."""
        if self.fase == "combattimento" and any(ab.get("tipo") == "divieto" and ab.get("di") == "combattimento"
                                                 for o in self.t.campo for _, ab in self.t.abilita_di(o)): return True
        return any(getattr(x, "carta", None) is not None and x.carta.tipi & {"instant", "sorcery"} and x.controllore is not None
                   and self.t._sostituzioni("split_second", x.controllore) for x in self.t.pila)   # 702.61a, 613.1f

    def gratis_possibile(self, i, ogg, x=0):
        """118.9, 601.2b: «You may cast spells with mana value less than or equal to the number of creatures you control from
        your hand without paying their mana costs» (Omnipresence, in campo sotto i): la magia e' nella mano di i, il suo valore
        di mana (202.3, con X=0: 107.3b) non supera le creature che i controlla, X e' 0 (107.3b)."""
        if not (getattr(ogg, "vivo", False) and ogg in self.t.giocatori[i].mano and "land" not in ogg.carta.tipi): return False
        if x: return False                                                                         # 107.3b
        fonti = [ab for o in self.t.campo if o.controllore == i for _, ab in self.t.abilita_di(o) if ab.get("tipo") == "lancio_gratis"]
        if not fonti: return False
        if any(set(ab) - {"tipo", "da", "mv_max"} or ab.get("da") != "mano" or ab.get("mv_max") != "creature_tue" for ab in fonti):
            raise NonCoperto(f"118.9: il permesso di lanciare gratis {fonti[0]} non e' coperto")
        creature = sum(1 for o in self.t.campo if o.controllore == i and "creature" in o.carta.tipi)
        return M.valore(ogg.carta.car.get("costo") or "") <= creature

    def puo_lanciare(self, i, ogg, x=0):
        if self._divieto_combattimento(): return False
        with self.pagando(("magia", ogg.carta, ogg in self.t.giocatori[i].mano)):
            if self._puo_lanciare_scelto(i, ogg, x): return True
            if ogg.n in self._alternativo or not self.gratis_possibile(i, ogg, x): return False
            self._alternativo[ogg.n] = "gratis"                                                    # 601.2b: anche col costo alternativo
            try: return self._puo_lanciare_scelto(i, ogg, x)
            finally: self._alternativo.pop(ogg.n, None)

    def _puo_lanciare_scelto(self, i, ogg, x=0):
        if ogg.carta.car.get("costo_aggiuntivo"):
            if ogg.n in self._opzione_costo:
                return self._opzione_pagabile(i, ogg, self._opzione_costo[ogg.n]) and self._puo_lanciare_base(i, ogg, x)
            return bool(self.opzioni_costo(i, ogg, x))
        return self._puo_lanciare_base(i, ogg, x)

    def _puo_lanciare_base(self, i, ogg, x=0):
        """117.1a, 304.1, 307.1, 702.8a (lampo: quando si lancerebbe un istantaneo), 601.2b-c (modi e bersagli)."""
        c = ogg.carta
        in_risoluzione = self._lancio_risoluzione == ogg.n                                          # 608.2g
        if not (ogg.vivo and (ogg in self.t.giocatori[i].mano or self._dal_cimitero(i, ogg) or self._copia_preparata(i, ogg)
                              or self.permesso(i, ogg) or (in_risoluzione and ogg.zona == "esilio") or self._da_zona_alternativo(i, ogg))) \
                or "land" in c.tipi: return False
        self._senza_testo(c, "117.1a")
        if c.car.get("non_lanciabile"): raise NonCoperto(f"{c.car['non_lanciabile']}: {c.nome}")
        if c.car.get("lancio_solo_se") and not self._lancio_permesso(i, c.car["lancio_solo_se"]): return False   # 601.3
        if in_risoluzione: quando = not self.t.finita                                              # 608.2g: adesso, durante la risoluzione
        elif isinstance(self._alternativo.get(ogg.n), dict) and (ALTERNATIVI_SET.get(self._alternativo[ogg.n]["nome"]) or {}).get("tempo"):
            quando = ALTERNATIVI_SET[self._alternativo[ogg.n]["nome"]]["tempo"](self, i, ogg)      # i tempi del costo alternativo (702.190a)
        elif "instant" in c.tipi or "flash" in parole_stampate(ogg, PAROLE_7): quando = self.da_istantaneo(i)
        elif c.permanente or "sorcery" in c.tipi: quando = self.da_stregoneria(i)
        else: return False
        if not quando or self.piano(i, self._costo_di(i, ogg), x) is None: return False
        if c.permanente and (c.car.get("bersagli") or c.car.get("modi")):
            raise NonCoperto(f"303.4, 608.3b-c: {c.nome} e' un permanente con bersaglio")
        if c.car.get("incanta"): return bool(self.candidati(c.car["incanta"], i, None, ogg))           # 303.4a, 115.1b
        return self.programma_possibile(i, c.car, ogg)

    def lancia(self, i, ogg, x=0, pagamento=None, bersagli=None, modi=None):
        """601.2b: chi lancia annuncia il costo aggiuntivo che sceglie, fra quelli che puo' pagare; 601.2h: lo paga."""
        with self.pagando(("magia", ogg.carta, ogg in self.t.giocatori[i].mano)):
            if ogg.n not in self._alternativo and self.gratis_possibile(i, ogg, x):                 # 601.2b, 118.9a: chi lancia annuncia
                g = (self.chi or {}).get(i)                                                       # se usa il costo alternativo (uno solo)
                usa = g.costo_alternativo(self, i, ogg, ["gratis"]) if hasattr(g, "costo_alternativo") else \
                    ("gratis" if pagamento is None else None)                                       # chi da' un pagamento paga il costo
                if usa == "gratis":
                    self._alternativo[ogg.n] = "gratis"
                    try: return self._lancia_scelto(i, ogg, x, pagamento, bersagli, modi)
                    finally: self._alternativo.pop(ogg.n, None)
            return self._lancia_scelto(i, ogg, x, pagamento, bersagli, modi)

    def _facoltativo_pagabile(self, i, ogg, fac):
        op = {k: v for k, v in fac.items() if k not in ("nome", "mana")}
        return not op or self._opzione_pagabile(i, ogg, op)

    def _lancia_scelto(self, i, ogg, x=0, pagamento=None, bersagli=None, modi=None):
        if self._divieto_combattimento(): return None                                              # 101.2
        fac = ogg.carta.car.get("facoltativo")
        if fac is not None and ogg.n not in self._facoltativo:                                     # 601.2b, 702.33a: chi lancia annuncia
            g = (self.chi or {}).get(i)                                                            # se paga il kicker (chi non sceglie:
            vuole = g.facoltativo(self, i, ogg, fac) if hasattr(g, "facoltativo") else True        # si', se puo')
            for paga_ in ([True, False] if vuole else [False]):
                if paga_ and not self._facoltativo_pagabile(i, ogg, fac): continue
                self._facoltativo[ogg.n] = paga_
                resto_ = {k: v for k, v in fac.items() if k not in ("nome", "mana")}
                self._facoltativo_resto = (i, ogg.carta.nome, resto_) if paga_ and resto_ else None
                try: m = self._lancia_scelto(i, ogg, x, pagamento, bersagli, modi)
                finally: self._facoltativo.pop(ogg.n, None); self._facoltativo_resto = None
                if m is not None: m.facoltativo_pagato = paga_; return m
            return None
        if not ogg.carta.car.get("costo_aggiuntivo"): return self._lancia_base(i, ogg, x, pagamento, bersagli, modi)
        opz = self.opzioni_costo(i, ogg, x)
        if not opz: return None
        g = (self.chi or {}).get(i)
        op = g.costo_aggiuntivo(self, i, ogg, opz) if hasattr(g, "costo_aggiuntivo") else opz[0]
        if op not in opz: op = opz[0]
        self._opzione_costo[ogg.n] = op
        self._da_pagare_ancora = (i, ogg, op)
        try: return self._lancia_base(i, ogg, x, pagamento, bersagli, modi)
        finally:
            self._opzione_costo.pop(ogg.n, None)
            self._da_pagare_ancora = None

    def _metti_e_paga(self, i, ogg, x=0, pagamento=None):
        """601.2f: il costo totale fissato (con riduzioni, aumenti, costi aggiuntivi e alternativi) va nel registro accanto al
        pagamento, per chi lo controlla da fuori (costi_magie: (costo, Pagamento, x, fonti, riserva))."""
        costo, n0 = self._costo_di(i, ogg), len(self.pagati)
        magia = super()._metti_e_paga(i, ogg, x, pagamento)
        if magia is not None and len(self.pagati) > n0: self.costi_magie.append((costo,) + tuple(self.pagati[-1][1:]))
        return magia

    def _paga(self, i, oggetto, costo, x, scelto):
        """601.2h: col mana anche il resto del costo aggiuntivo (il sacrificio), prima che la magia diventi lanciata (601.2i)."""
        super()._paga(i, oggetto, costo, x, scelto)
        self._spendi_vincolato(i, scelto[0].spesa)                                                  # 106.6
        resto = getattr(self, "_da_pagare_ancora", None)
        if resto and resto[0] == i and oggetto.carta is not None and oggetto.carta.nome == resto[1].carta.nome and "scarta" in resto[2]:
            self._da_pagare_ancora = None                                                           # 601.2h: scarta un'altra carta
            mano = [o for o in self.t.giocatori[i].mano if o is not oggetto]
            g = (self.chi or {}).get(i)
            x_ = g.scarta_costo(self, i, mano) if hasattr(g, "scarta_costo") else mano[-1]
            self.t.scarta(x_ if x_ in mano else mano[-1], causa="601.2h")
        fr = self._facoltativo_resto                                                               # 601.2h, 702.33a: il resto del kicker
        if fr and fr[0] == i and oggetto.carta is not None and oggetto.carta.nome == fr[1]:
            self._facoltativo_resto = None
            if "sacrifica" in fr[2]:
                cand = self._da_sacrificare(i, None, {"tipi": fr[2]["sacrifica"]}, altro=False)
                g = (self.chi or {}).get(i)
                x_ = g.sacrifica_costo(self, i, cand) if hasattr(g, "sacrifica_costo") else cand[0]
                self.t.sacrifica(x_ if x_ in cand else cand[0], i, causa="701.21a")
            for k, v in fr[2].items():
                if k in COSTI_SET: COSTI_SET[k][1](self, i, oggetto, v)
            if set(fr[2]) - {"sacrifica"} - set(COSTI_SET): raise NonCoperto(f"702.33a: il kicker {fr[2]} non e' coperto")
        if resto and resto[0] == i and oggetto.carta is not None and oggetto.carta.nome == resto[1].carta.nome and set(resto[2]) & set(COSTI_SET):
            self._da_pagare_ancora = None                                                           # 601.2h: il costo di un set
            for k, v in resto[2].items():
                if k in COSTI_SET: COSTI_SET[k][1](self, i, oggetto, v)
        if resto and resto[0] == i and oggetto.carta is not None and oggetto.carta.nome == resto[1].carta.nome and "vite" in resto[2]:
            self._da_pagare_ancora = None
            self.t.paga_vite(i, resto[2]["vite"], causa="119.4")                                   # 601.2h
        if resto and resto[0] == i and oggetto.carta is not None and oggetto.carta.nome == resto[1].carta.nome and "sacrifica" in resto[2]:
            self._da_pagare_ancora = None
            cand = self._da_sacrificare(i, None, {"tipi": resto[2]["sacrifica"]}, altro=False)
            g = (self.chi or {}).get(i)
            x_ = g.sacrifica_costo(self, i, cand) if hasattr(g, "sacrifica_costo") else cand[0]
            self.t.sacrifica(x_ if x_ in cand else cand[0], i, causa="701.21a")

    def _lancia_base(self, i, ogg, x=0, pagamento=None, bersagli=None, modi=None):
        """601.2c: i bersagli si scelgono lanciando; se non sono legali il lancio torna indietro (734.1)."""
        car = ogg.carta.car
        if car.get("lancio_solo_se") and not self._lancio_permesso(i, car["lancio_solo_se"]): return None   # 601.3
        reqs, fa, scelta = [], list(car.get("fa") or []), []
        if car.get("bersagli") or car.get("modi"):
            if not (ogg.vivo and self.puo_lanciare(i, ogg, x)): return None
            pronto = self._prepara(i, car, None, ogg, bersagli, modi)
            if not pronto: return None
            reqs, fa, scelta = pronto
        flashback = self._dal_cimitero(i, ogg)
        dalla_mano = ogg in self.t.giocatori[i].mano
        if car.get("incanta"):                                                                     # 303.4a, 601.2c
            if not (ogg.vivo and self.puo_lanciare(i, ogg, x)): return None
            pronto = self._prepara(i, {"bersagli": [car["incanta"]], "fa": []}, None, ogg, bersagli)
            if not pronto: return None
            reqs, fa, scelta = pronto
        preparata = self._copia_preparata(i, ogg)
        self._bersagli_lancio = scelta                    # 601.2c-i: gli inneschi «a spell that targets» li vedono lanciando
        self._modi_lancio = (ogg.n, list(getattr(self, "_ultimi_modi", []))) if car.get("modi") else None
        try: magia = super().lancia(i, ogg, x, pagamento)
        finally: self._bersagli_lancio = None; self._modi_lancio = None
        if magia is not None and preparata:                                                        # 723.3c, 601.2i
            perm = self.t.oggetti.get(ogg.carta.car["copia_di"])
            if perm is not None: perm.preparato = False
        if magia is not None:
            magia.bersagli, magia.reqs, magia.fa = scelta, reqs, fa
            if self.incontrastabile.pop((i, self.t.turno_numero), None): magia.incontrastabile = True   # «the next spell you cast this turn»
            if car.get("incontrastabile"): magia.incontrastabile = True                            # 113.6g: «This spell can't be countered»
            magia.flashback = bool(flashback)
            magia.dalla_mano = dalla_mano
            if car.get("modi"): self.t._evento("dilemma", giocatore=i, vecchio=magia.n, causa="700.17")   # 700.17: i modi scelti
            if flashback and car.get("flashback_scarta"):                                          # 601.2h: il costo in piu'
                mano = list(self.t.giocatori[i].mano)
                if mano: self.t.scarta(mano[-1], causa="701.9a")
            self._segna_bersagli(magia, i)
        return magia

    def entra_attaccando(self, o, come=None, difensore=None):
        """508.4: una creatura messa in campo attaccando attacca chi sceglie chi la controlla (chi non sceglie: chi attacca
        «come», se attacca un giocatore, se no il primo avversario); 506.3a: un permanente non creatura non attacca;
        508.4d: entrata dopo la dichiarazione dei bloccanti, e' non bloccata (non e' fra le bloccate); fuori dal
        combattimento non attacca."""
        if self.fase != "combattimento" or not (o.vivo and o.zona == "campo") or "creature" not in o.carta.tipi: return False
        dif = difensore if difensore is not None else (self.attaccanti.get(come) if come is not None else None)
        if not isinstance(dif, int):
            dif = next((g.i for g in self.t.giocatori if g.i != o.controllore and not g.perso), None)
        if dif is None: return False                                                               # 508.4a
        self.attaccanti[o], self._ctrl[o] = dif, o.controllore
        self.t._evento("entra_attaccando", carta=o.carta, vecchio=o.n, giocatore=o.controllore, causa="508.4")
        return True

    def alternativi(self, i, ogg):
        """118.9, 601.2b: i costi alternativi di un set che la carta ha, pagabili adesso dalla zona in cui e'."""
        dati = list(ogg.carta.car.get("alternativi") or []) + list(getattr(ogg, "alternativi_dati", None) or [])   # anche quelli che un
        return [a for a in dati if a["nome"] in ALTERNATIVI_SET and ALTERNATIVI_SET[a["nome"]]["puo"](self, i, ogg, a)]   # effetto da' all'oggetto

    def lancia_alternativo(self, i, ogg, nome, x=0, pagamento=None, bersagli=None, modi=None):
        """601.2b: chi lancia annuncia il costo alternativo (uno solo, 118.9a); il costo e' quello scritto (118.9), poi
        aumenti e riduzioni (118.9d); quello che il costo fa in piu' lo paga il posto del set."""
        alt = next((a for a in self.alternativi(i, ogg) if a["nome"] == nome), None)
        if alt is None or ogg.n in self._alternativo: return None
        self._alternativo[ogg.n] = alt
        try:
            if not self.puo_lanciare(i, ogg, x): return None
            magia = self.lancia(i, ogg, x, pagamento, bersagli, modi)
        finally: self._alternativo.pop(ogg.n, None)
        if magia is not None:
            alt = magia.alternativo = dict(alt)                                                   # una copia per magia: la carta non cambia
            reg = ALTERNATIVI_SET[nome]
            if reg.get("paga"): reg["paga"](self, i, magia, alt)
            if reg.get("dopo"): reg["dopo"](self, magia, alt)
        return magia

    def lancia_retro(self, i, ogg, x=0, pagamento=None, bersagli=None, modi=None):
        """712.8b-c: una modale a due facce lanciata con la faccia dietro (le sole caratteristiche di quella faccia)."""
        if not (ogg.carta is not None and ogg._carta.car.get("mdfc") and ogg._carta.retro() is not None and ogg in self.t.giocatori[i].mano):
            return None
        ogg.come_retro = True
        try:
            if not self.puo_lanciare(i, ogg, x): return None
            return self.lancia(i, ogg, x, pagamento, bersagli, modi)
        finally:
            if ogg.vivo: ogg.come_retro = False

    def lancia_avventura(self, i, ogg, x=0, pagamento=None, bersagli=None, modi=None):
        """716.3, 716.3a: lancia un'avventuriera dalla mano come avventura (le sole caratteristiche dell'avventura); dall'esilio
        della 716.3d no."""
        if not (ogg.carta is not None and ogg.fisica.car.get("avventura") and ogg in self.t.giocatori[i].mano): return None
        ogg.come_avventura = True
        try:
            if not self.puo_lanciare(i, ogg, x): return None
            return self.lancia(i, ogg, x, pagamento, bersagli, modi)
        finally:
            if ogg.vivo: ogg.come_avventura = False

    def esegui(self, i, azione):
        if self.ha_priorita != i: return False
        if azione[0] == "avventura":                                                               # 716.3
            return self.lancia_avventura(i, *azione[1:]) is not None
        if azione[0] == "retro":                                                                   # 712.8b: ("retro", carta, x, ...)
            return self.lancia_retro(i, *azione[1:]) is not None
        if azione[0] == "alternativo":                                                             # 118.9: ("alternativo", carta, nome, x, ...)
            return self.lancia_alternativo(i, *azione[1:]) is not None
        if azione[0] == "lancia" and len(azione) > 4:
            return self.lancia(i, azione[1], azione[2] or 0, azione[3], azione[4], azione[5] if len(azione) > 5 else None) is not None
        if azione[0] == "attiva":
            return self.attiva(i, *azione[1:]) is not None
        return super().esegui(i, azione)

    # ------------------------------------------------------------------ le abilita' attivate (602, 606)
    def _tap_debole_conta(self): return True

    def _fedelta_una_volta(self): return True

    def motivo_non_attiva(self, i, ogg, k, x=0):
        """602.2, 602.5, 606.3, 606.6. -> None se si puo' attivare adesso, o il motivo."""
        if ogg.zona == "campo" and self._divieti_attivazione() and self.t.regola("non_attivabili", ogg):
            return "602.5: un effetto dice che le sue abilita' attivate non si possono attivare"
        if self.ha_priorita != i or self.t.finita: return "117.1b: si attiva con la priorita'"
        if getattr(ogg, "carta", None) is None or not ogg.vivo: return "602.2: l'oggetto non c'e'"
        ab = dict(self.t.abilita_di(ogg)).get(k)
        if ab is not None and ab.get("zona") == "mano":                                            # 702.29a: dalla mano
            if ogg not in self.t.giocatori[i].mano: return "702.29a: si attiva solo dalla mano di chi la possiede"
        elif ab is not None and ab.get("zona") == "cimitero":                                      # 113.6: funziona dal cimitero
            if ogg not in self.t.giocatori[i].cimitero: return "113.6: si attiva solo dal cimitero di chi la possiede"
        else:
            if ogg.zona != "campo": return "602.2: si attivano le abilita' dei permanenti in campo"
            if ogg.controllore != i: return "602.2: solo chi controlla l'oggetto ne attiva le abilita'"
        if ab is None or ab.get("tipo") != "attivata": return "113.3b: l'oggetto non ha quell'abilita' attivata"
        if self._divieto_combattimento(): return "101.2: durante il combattimento non si attivano abilita' che non sono di mana"
        if ab.get("produce"): raise NonCoperto(f"605.1a: l'abilita' di mana di {ogg.nome} non e' coperta")
        if ab.get("modi"): raise NonCoperto("700.2a: le abilita' attivate modali non sono coperte")
        if "fedelta" in ab:
            rapida = any(j == i and "planeswalker" in ogg.carta.tipi and st in ogg.carta.tipo.split("—")[-1].split()
                         for j, st in self.fedelta_rapide)                                         # Jace's Machinations
            if not self.da_stregoneria(i) and not (rapida and self.da_istantaneo(i)):
                return "606.3: la fedelta' nella propria fase principale, a pila vuota"
            if self._fedelta_una_volta() and (ogg.n, self.t.turno_numero) in self.fedelta_usate:
                return "606.3: una sola abilita' di fedelta' per permanente per turno"
            if ab["fedelta"] == "-X":                                                              # 107.3k: X scelto attivando
                if not isinstance(x, int) or x < 0: return "107.3k: X e' un intero non negativo"
                if ogg.segnalini["fedelta"] < x: return "606.6: non ci sono abbastanza segnalini fedelta'"
            elif ab["fedelta"] < 0 and ogg.segnalini["fedelta"] < -ab["fedelta"]: return "606.6: non ci sono abbastanza segnalini fedelta'"
        elif ab.get("velocita") == "stregoneria" and not self.da_stregoneria(i): return "602.5d: solo come una stregoneria"
        costo = ab.get("costo") or {}
        if costo.get("tappa"):
            if ogg.tappato: return "602.2b, 601.2h: il {T} di un permanente tappato non si paga"
            if self._tap_debole_conta() and self.debole(ogg) and "haste" not in parole(ogg):
                return "602.5a: il {T} di una creatura con la debolezza da evocazione"
        if costo.get("mana") and _rid_ferma(ab):                                                   # 601.2f: la riduzione di un set,
            if not self._pagabile(i, ogg, self._costo_set(ab, ogg), x, costo.get("tappa")):         # senza bersagli
                return "601.2f, 601.2h: il costo ridotto non si paga"
        elif costo.get("mana") and ab.get("riduzione"):                                            # 601.2c poi 601.2f: il costo
            r_ = (ab.get("bersagli") or [None])[ab["riduzione"]["bersaglio"]]                       # dipende dal bersaglio: basta
            if not any(self._pagabile(i, ogg, self._costo_attivazione(ab, [[b]]), x, costo.get("tappa"))   # un bersaglio legale
                       for b in self.candidati(r_, i, None, ogg)):                                 # che lo renda pagabile
                return "601.2c, 601.2f, 601.2h: per nessun bersaglio legale il costo si paga"
        elif costo.get("mana"):                                                                    # 602.2b, 601.2h: il suo {T} e' nel costo
            if not self._pagabile(i, ogg, costo["mana"], x, costo.get("tappa")): return "601.2h: il costo non si paga"
        if costo.get("sacrifica_se") and not (ogg.vivo and ogg.zona == "campo"): return "701.21a"
        for k_, v in (ab.get("solo_se") or {}).items():                                           # 602.5b: «Activate only if»
            ev = self._eventi_del_turno()
            if k_ == "avversario_danno_nc_turno" and not any(x.tipo == "danno" and x.nuovo is None and x.causa != "510.2" and x.giocatore != i for x in ev):
                return "602.5b: un avversario non ha subito danno non da combattimento in questo turno"
            if k_ == "guardato_turno" and not any(x.tipo == "guarda" and x.giocatore == i for x in ev):
                return "602.5b: non hai profetizzato ne' sorvegliato in questo turno"
            if k_ == "tuo_turno" and self.attivo != i: return "602.5b: si attiva solo nel proprio turno"
            if k_ == "istantaneo_o_stregoneria_turno" and not any(x.tipo == "lanciata" and x.giocatore == i and x.carta is not None
                                                                  and x.carta.tipi & {"instant", "sorcery"} for x in ev):
                return "602.5b: non hai lanciato istantanei o stregonerie in questo turno"
            if k_ == "cimitero_almeno" and len(self.t.giocatori[i].cimitero) < v: return "602.5b: meno di sette carte nel cimitero"
            if k_ == "fedelta_jace_almeno" and sum(o.segnalini["fedelta"] for o in self.t.campo if o.controllore == i
                                                   and "planeswalker" in o.carta.tipi and "Jace" in o.carta.tipo.split("—")[-1].split()) < v:
                return "602.5b: non ci sono abbastanza segnalini fedelta' sui Jace"
            if k_ == "statica":                                                                    # 602.5b, 611.3a: la condizione adesso
                if not self.t.condizione_statica(v, ogg): return f"602.5b: la condizione {v!r} non c'e'"
                continue
            if k_ in SE_SET:                                                                       # una restrizione di un set (il suo posto)
                prima_, self._fonte_condizione = self._fonte_condizione, ogg                       # la fonte, per chi la guarda
                try: ok_ = SE_SET[k_](self, v, i)
                finally: self._fonte_condizione = prima_
                if not ok_: return f"602.5b: la condizione {k_!r} non c'e'"
                continue
            if k_ not in ("avversario_danno_nc_turno", "guardato_turno", "tuo_turno", "fedelta_jace_almeno", "cimitero_almeno",
                          "istantaneo_o_stregoneria_turno"): raise NonCoperto(f"602.5b: la restrizione {k_!r}")
        if costo.get("scarta_una") and not self._da_scartare(i, ogg, costo["scarta_una"]): return "601.2h: nessuna carta da scartare"
        if costo.get("esilia_questo") and not (ogg.vivo and ogg.zona == "campo"): return "601.2h: si esilia solo dal campo"
        if costo.get("tappa_altri") and len(self._da_tappare(i, costo["tappa_altri"], ogg)) < costo["tappa_altri"]["n"]: return "601.2h: non ci sono abbastanza permanenti stappati"
        if costo.get("equipaggia") is not None and sum(self._forza_equipaggio(o) for o in self._equipaggio(i, ogg)) < costo["equipaggia"]:
            return "702.122a: le altre creature stappate non arrivano alla forza del crew"
        if ab.get("esaurisci") and (ogg.n, k) in self.esauste: return "702.177a: un'abilita' exhaust si attiva una volta sola"
        if ab.get("una_sola_volta") and (ogg.n, k) in self.esauste: return "602.5b: «activate only once»: gia' attivata"
        if ab.get("una_per_turno") and (ogg.n, k, self.t.turno_numero) in self.esauste: return "602.5b: «once each turn»: gia' attivata"
        if costo.get("togli_un_segnalino") and sum(v for v in ogg.segnalini.values() if v > 0) < int(costo["togli_un_segnalino"]):
            return "122.8, 601.2h: non ci sono abbastanza segnalini da togliere"
        if costo.get("togli_segnalini_tipo") and ogg.segnalini[costo["togli_segnalini_tipo"]["tipo"]] < costo["togli_segnalini_tipo"]["n"]:
            return "122.8, 601.2h: non ci sono abbastanza segnalini di quel tipo"                    # (giro 10)
        if costo.get("esilia_altra") and not self._da_esiliare(i, ogg, costo["esilia_altra"]): return "601.2h: nessuna altra carta da esiliare"
        if costo.get("sacrifica_altro") and not self._da_sacrificare(i, ogg, costo["sacrifica_altro"]): return "601.2h: niente da sacrificare"
        if costo.get("paga_vite") and self.t.giocatori[i].vite < costo["paga_vite"]: return "119.4: non ci sono abbastanza vite da pagare"
        for k_, v_ in costo.items():                                                               # 118.3: i costi dei set
            if k_ in COSTI_SET and not COSTI_SET[k_][0](self, i, ogg, v_): return f"118.3: il costo {k_} non si paga"
        if costo.get("sacrifica_un") and not self._da_sacrificare(i, ogg, costo["sacrifica_un"], altro=False): return "601.2h: niente da sacrificare"
        if not self.programma_possibile(i, ab, ogg): return "601.2c, 700.2a: non ci sono bersagli legali"
        return None

    def _pagabile(self, i, ogg, costo, x=0, tappa=False):
        """601.2h, 602.2b: il costo di mana di un'abilita' di ogg si paga adesso (se il suo {T} e' nel costo, ogg non e' una
        fonte per quel costo)."""
        self._senza_fonte = ogg if tappa else None
        try: return self._scegli_pagamento(i, costo, x) is not None
        finally: self._senza_fonte = None

    def _costo_set(self, ab, ogg):
        """601.2f, 118.7: una riduzione di costo di un set la calcola il suo posto (RIDUZIONI_SET). (giro 13) «This ability costs
        {N} less to activate for each Y / if Z», «{X} less, where X is Y»: contata quando si attiva, solo il generico, fino a {0}
        (118.7a)."""
        rid = ab["riduzione"]
        if "set" in rid: return RIDUZIONI_SET[rid["set"]](self, ab, ogg, ab["costo"]["mana"])
        if "quanto" in rid: n = rid["n"] * self.conta(rid["quanto"], ogg.controllore, ogg, ogg)
        else: n = rid["n"] if self.t.condizione_statica(rid["se"], ogg) else 0
        return cambia_generico(ab["costo"]["mana"], -n) if n > 0 else ab["costo"]["mana"]

    def _costo_attivazione(self, ab, scelta):
        """601.2f, 602.2b, 118.7a: il costo di mana dell'abilita' coi bersagli scelti: «costs {1} less to activate for each
        +1/+1 counter on the creature it targets» toglie solo generico, fino a {0}."""
        costo, rid = ab["costo"]["mana"], ab.get("riduzione")
        if not rid: return costo
        g = scelta[rid["bersaglio"]] if rid["bersaglio"] < len(scelta) else []
        if set(rid) - {"per_segnalino", "bersaglio", "n"}: raise NonCoperto(f"601.2f: la riduzione {rid} non e' coperta")
        n = sum(x.segnalini[rid["per_segnalino"]] for x in g if not _e_giocatore(x)) * rid["n"]
        return cambia_generico(costo, -n) if n else costo

    def _da_tappare(self, i, sel, ogg=None):
        """«Tap N untapped [tipi] you control» («another»: non la fonte, 14 nov 2026)."""
        return [o for o in self.t.campo if o.controllore == i and not o.tappato and set(sel["tipi"]) & o.carta.tipi
                and not (sel.get("altro") and o is ogg) and (not sel.get("sottotipo") or ha_sottotipo(o, sel["sottotipo"]))]   # «Elves»

    def _forza_equipaggio(self, o):
        """702.122a, 702.171a: la forza che conta per crew e saddle («as though its power were N greater»)."""
        return max(0, forza(o) + (o.carta.car.get("equipaggia_bonus") or 0))

    def _equipaggio(self, i, ogg):
        """702.122a: «other untapped creatures you control» (302.6: non e' un {T}, anche quelle appena entrate)."""
        return [o for o in self.t.campo if o.controllore == i and o is not ogg and not o.tappato and "creature" in o.carta.tipi]

    def _da_scartare(self, i, ogg, sel):
        return [o for o in self.t.giocatori[i].mano if o is not ogg and (not isinstance(sel, dict) or not sel.get("leggendaria") or "legendary" in o.carta.tipi)
                and (not isinstance(sel, dict) or not sel.get("tipi") or set(sel["tipi"]) & o.carta.tipi)]   # «Discard a land card» (giro 10)

    def _da_esiliare(self, i, ogg, sel):
        return [o for o in self.t.giocatori[i].cimitero if o is not ogg and set(sel["tipi"]) & o.carta.tipi]

    def _da_sacrificare(self, i, ogg, sel, altro=True):
        return [o for o in self.t.campo if o.controllore == i and (o is not ogg or not altro)
                and (set(sel["tipi"]) & o.carta.tipi or (sel.get("pedina_ok") and o.carta.pedina)          # «or token»
                     or any(st in o.carta.tipo.split("—")[-1].split() for st in sel.get("sottotipi") or ()))]   # «or Vehicle»

    # ------------------------------------------------------------------ 106.6: il mana che si spende solo per qualcosa
    def _vincolo_ok(self, v):
        """106.6: il mana vincolato si puo' spendere per quello che si sta pagando adesso?"""
        c = self._spesa
        magia = bool(c and c[0] == "magia")
        if v == "non_dalla_mano": return not (magia and c[2])                                     # «can't be spent to cast spells from your hand»
        if v == "solo_noncreatura": return magia and "creature" not in c[1].tipi                   # «only to cast a noncreature spell»
        if v == "solo_planeswalker": return magia and "planeswalker" in c[1].tipi                  # «only to cast a planeswalker spell»
        attiva_ = bool(c and c[0] == "abilita'" and len(c) > 2 and c[2] == "attiva")               # 602.2b: attivare un'abilita'
        if v == "artefatto": return magia and "artifact" in c[1].tipi                               # «only to cast an artifact spell»
        if v == "istantaneo_stregoneria": return magia and bool({"instant", "sorcery"} & c[1].tipi)
        if v == "solo_abilita": return attiva_                                                     # «only to activate abilities»
        if v == "abilita_artefatto": return attiva_ and c[1] is not None and "artifact" in c[1].carta.tipi
        if v == "abilita_creatura": return attiva_ and c[1] is not None and "creature" in c[1].carta.tipi
        if v == "artefatto_o_abilita": return (magia and "artifact" in c[1].tipi) or attiva_       # «... or activate an ability»
        if v == "artefatto_o_abilita_artefatto":                                                   # «... of an artifact source»
            return (magia and "artifact" in c[1].tipi) or (attiva_ and c[1] is not None and "artifact" in c[1].carta.tipi)
        if isinstance(v, str) and v.startswith("o:"): return any(self._vincolo_ok(x) for x in v[2:].split("§"))   # (giro 13) A o B
        if isinstance(v, str) and v.startswith(("tipo:", "sottotipo:")):                          # 106.6 (15 nov 2026): «Elf spells
            k_, _, x_ = v.partition(":")                                                           # [and abilities of Elf sources]»
            x_, _, ab_ = x_.partition("|")
            def ha_(o): return x_ in o.carta.tipi if k_ == "tipo" else ha_sottotipo(o, x_)
            if magia and ha_(types.SimpleNamespace(carta=c[1])): return True
            return bool(ab_) and attiva_ and c[1] is not None and ha_(c[1])
        raise NonCoperto(f"106.6: il vincolo {v!r} non e' coperto")

    @contextlib.contextmanager
    def pagando(self, cosa):
        prima, self._spesa = self._spesa, cosa
        try: yield
        finally: self._spesa = prima

    def _riserva_usabile(self, i):
        """La riserva meno il mana vincolato che non si puo' spendere per quello che si sta pagando."""
        r = M.Riserva()
        r.aggiungi(self.t.giocatori[i].riserva.tupla())
        via = [0] * len(M.TIPI)
        for k, v in self.vincolato[i]:
            if self._spesa is not None and not self._vincolo_ok(v): via[k] += 1
        if any(via) and not r.paga(tuple(via)): raise RuntimeError("106.6: il mana vincolato non e' nella riserva")
        return r

    def piano(self, i, costo, x=0):
        return M.piano(costo, self.fonti(i), self._riserva_usabile(i), x, self.t.giocatori[i].vite)

    def _scegli_pagamento(self, i, costo, x=0, pagamento=None):
        """601.2b-h con 106.6: il mana vincolato conta solo se si puo' spendere per questo."""
        g = self.t.giocatori[i]
        terre, fonti, ris = self.terre_stappate(i), self.fonti(i), self._riserva_usabile(i)
        if pagamento is None: pagamento = M.piano(costo, fonti, ris, x, g.vite)
        elif M.valida(pagamento, costo, fonti, ris.tupla(), x, g.vite): return None
        return None if pagamento is None else (pagamento, terre, fonti, ris.tupla())

    def _tappa_per_mana_vincolo(self, i, terra, prod=None):
        """605.3b, 106.6: il mana di una fonte vincolata entra nella riserva col suo vincolo."""
        prima = self.t.giocatori[i].riserva.tupla()
        ok = super().tappa_per_mana(i, terra, prod)
        v = terra.carta.car.get("mana_vincolo") if ok else None
        if v:
            dopo = self.t.giocatori[i].riserva.tupla()
            for k, (a, b) in enumerate(zip(prima, dopo)): self.vincolato[i] += [(k, v)] * (b - a)
        return ok

    def _spendi_vincolato(self, i, spesa):
        """Pagato il costo: il mana vincolato che si poteva spendere si spende per primo (una scelta legale di chi paga:
        106.6 non dice quale mana si usa), quello che non si poteva resta."""
        resto = list(spesa)
        tieni = []
        for k, v in self.vincolato[i]:
            if resto[k] > 0 and self._vincolo_ok(v): resto[k] -= 1
            else: tieni.append((k, v))
        self.vincolato[i] = tieni

    def puo_attivare(self, i, ogg, k, x=0):
        with self.pagando(("abilita'", ogg, "attiva")):                                            # 106.6: la fonte, per i vincoli
            return self.motivo_non_attiva(i, ogg, k, x) is None

    def attiva(self, i, ogg, k, x=0, pagamento=None, bersagli=None):
        with self.pagando(("abilita'", ogg, "attiva")):
            return self._attiva(i, ogg, k, x, pagamento, bersagli)

    def _attiva(self, i, ogg, k, x=0, pagamento=None, bersagli=None):
        """602.2: l'abilita' in pila (602.2a), i bersagli e il costo come una magia (602.2b, 601.2b-h). -> l'abilita' in
        pila, o None se e' illegale (734.1: niente si e' mosso)."""
        if self.motivo_non_attiva(i, ogg, k, x): return None
        ab = dict(self.t.abilita_di(ogg))[k]
        costo = ab.get("costo") or {}
        pronto = self._prepara(i, ab, None, ogg, bersagli)
        if not pronto: return None
        reqs, fa, scelta = pronto
        pag = None
        mana_ = ((self._costo_set(ab, ogg) if _rid_ferma(ab) else self._costo_attivazione(ab, scelta))
                 if costo.get("mana") else None)                 # 601.2f: dopo i bersagli (601.2c)
        if costo.get("mana"):
            self._senza_fonte = ogg if costo.get("tappa") else None                                 # non si tappa per il mana del suo costo
            try: pag = self._scegli_pagamento(i, mana_, x, pagamento)
            finally: self._senza_fonte = None
            if pag is None: return None
        t = self.t
        a = Abilita(next(t._oggetti), ogg, k, ab, i, "attivata")                                  # 602.2a, 113.8
        a.bersagli, a.x, a.reqs, a.fa = scelta, x, reqs, fa
        t.pila.append(a)
        t._evento("abilita", carta=ogg.carta, vecchio=a.n, a="pila", giocatore=i, causa="602.2a")
        self._segna_bersagli(a, i)
        if pag:
            self._paga(i, a, mana_, x, pag)                                                       # 601.2g-h
            self.pagati_abilita.append((mana_, pag[0], x, pag[2], pag[3]))
        if costo.get("tappa"): t.tappa(ogg)
        if costo.get("sacrifica_se"): t.sacrifica(ogg, i, causa="701.21a")                         # 118.3, 701.21a
        if costo.get("scarta_se"): t.scarta(ogg, causa="702.29a")                                    # 701.9a, 702.29a
        if costo.get("esilia_se"): t.esilia(ogg, causa="118.3")                                      # «exile this card from your graveyard»
        if costo.get("esilia_dalla_mano"): a.esiliata_costo = t.esilia(ogg, causa="118.3")            # 400.7j: l'effetto la ritrova
        g = (self.chi or {}).get(i)
        if costo.get("esilia_altra"):                                                              # 601.2h: esiliare come costo
            cand = self._da_esiliare(i, ogg, costo["esilia_altra"])
            x_ = g.esilia_costo(self, i, cand) if hasattr(g, "esilia_costo") else cand[-1]
            t.esilia(x_ if x_ in cand else cand[-1], causa="118.3")
        if costo.get("paga_vite"): t.paga_vite(i, costo["paga_vite"], causa="119.4")                # 118.3, 119.4
        for k_, v_ in costo.items():                                                               # 601.2h: i costi dei set
            if k_ in COSTI_SET: COSTI_SET[k_][1](self, i, ogg, v_)
        if costo.get("sacrifica_altro") or costo.get("sacrifica_un"):                               # 601.2h, 701.21a
            cand = self._da_sacrificare(i, ogg, costo.get("sacrifica_altro") or costo["sacrifica_un"], altro=bool(costo.get("sacrifica_altro")))
            x_ = g.sacrifica_costo(self, i, cand) if hasattr(g, "sacrifica_costo") else cand[0]
            t.sacrifica(x_ if x_ in cand else cand[0], i, causa="701.21a")
        if costo.get("esilia_questo"): t.esilia(ogg, causa="118.3")                                  # «Exile ~»
        if costo.get("tappa_altri"):                                                               # 302.6: non e' un {T}, anche appena entrati
            cand = self._da_tappare(i, costo["tappa_altri"], ogg)
            sc_ = g.tappa_costo(self, i, cand, costo["tappa_altri"]["n"]) if hasattr(g := (self.chi or {}).get(i), "tappa_costo") else cand[:costo["tappa_altri"]["n"]]
            if len(sc_) != costo["tappa_altri"]["n"] or any(o not in cand for o in sc_): sc_ = cand[:costo["tappa_altri"]["n"]]
            for o in sc_: t.tappa(o)
            a.tappati_costo = [(o.n, forza(o) if "creature" in o.carta.tipi else None) for o in sc_]   # 702.184a: chi si e' tappato
        if costo.get("equipaggia") is not None:                                                    # 702.122a, 702.122b: crew
            cand = self._equipaggio(i, ogg)
            n_ = costo["equipaggia"]
            pred, tot = [], 0                                                                      # chi non sceglie: le piu' forti,
            for o in sorted(cand, key=lambda o: -self._forza_equipaggio(o)):                        # finche' basta
                if tot >= n_: break
                pred.append(o); tot += self._forza_equipaggio(o)
            sc_ = g.equipaggia_costo(self, i, cand, n_) if hasattr(g := (self.chi or {}).get(i), "equipaggia_costo") else pred
            if any(o not in cand for o in sc_) or len(set(sc_)) != len(sc_) or sum(self._forza_equipaggio(o) for o in sc_) < n_: sc_ = pred
            for o in sc_: t.tappa(o)
            a.equipaggio = [o.n for o in sc_]                                                      # 702.122c: «crewed by»
        if ab.get("esaurisci") or ab.get("una_sola_volta"): self.esauste.add((ogg.n, k))           # 702.177a, 602.5b
        if ab.get("una_per_turno"): self.esauste.add((ogg.n, k, t.turno_numero))                   # 602.5b
        if costo.get("togli_segnalini_tipo"):                                                      # 122.8 (giro 10): «Remove a wish counter»
            t.togli_segnalini(ogg, costo["togli_segnalini_tipo"]["tipo"], costo["togli_segnalini_tipo"]["n"], causa="122.8")
        for _ in range(int(costo.get("togli_un_segnalino") or 0)):                                 # 122.8: chi paga sceglie quali
            tipi_ = sorted(k_ for k_, v in ogg.segnalini.items() if v > 0)
            g_ = (self.chi or {}).get(i)
            tipo_ = g_.togli_segnalino_costo(self, i, ogg, tipi_) if hasattr(g_, "togli_segnalino_costo") else tipi_[0]
            t.togli_segnalini(ogg, tipo_ if tipo_ in tipi_ else tipi_[0], 1, causa="122.8")
        if costo.get("scarta_una"):                                                                # 601.2h: scartare come costo
            mano = self._da_scartare(i, ogg, costo["scarta_una"])
            g = (self.chi or {}).get(i)
            x_ = g.scarta_costo(self, i, mano) if hasattr(g, "scarta_costo") else mano[-1]
            t.scarta(x_ if x_ in mano else mano[-1], causa="701.9a")
        costo_f = -x if ab.get("fedelta") == "-X" else ab.get("fedelta")
        if "fedelta" in ab:                                                                        # 606.4
            if costo_f >= 0: t.metti_segnalini(ogg, "fedelta", costo_f, causa="606.4")
            else: t.togli_segnalini(ogg, "fedelta", -costo_f, causa="606.4")
            self.fedelta_usate.add((ogg.n, t.turno_numero))
        t._evento("attivata", carta=ogg.carta, vecchio=a.n, giocatore=i, quanto=len(t.pila), causa="602.2b",
                  a="fedelta" if "fedelta" in ab else ("esaurisci" if ab.get("esaurisci") else ""), nuovo=costo_f)   # 702.177a
        if ab.get("di_mana"):                                                                      # 605.3b: non usa la pila, si risolve subito
            if a in t.pila: t.pila.remove(a)
            self._esegui(a, a.fa, reqs, i, ogg)
            a.vivo, a.esito = False, "605.3b"
        return a

    # ------------------------------------------------------------------ la risoluzione (608)
    def _abilita_indipendente(self): return True

    def _se_alla_risoluzione(self): return True

    def risolvi(self):
        cima = self._cima()
        if isinstance(cima, Abilita): return self._risolvi_abilita(cima)
        c = cima.carta
        if c.tipi & {"instant", "sorcery"} and (c.car.get("fa") is not None or c.car.get("modi")): return self._risolvi_magia(cima)
        if c.car.get("incanta"):                                                                   # 608.3b-c
            if self._tutti_illegali(cima, cima.reqs, cima.controllore, cima):
                self.ha_priorita = None
                t = self.t
                t._evento("risolve", carta=c, vecchio=cima.n, giocatore=cima.controllore, quanto=len(t.pila), causa="608.1")
                self.lanciate[(t.turno_numero, cima.controllore)] += 1
                return t.sposta(cima, "cimitero", causa="608.3b")
            cima.incanta_su = cima.bersagli[0][0].n
        return super().risolvi()

    def _tutti_illegali(self, oggetto, reqs, ctrl, fonte):
        """608.2b, 115.6: solo se ha almeno un bersaglio."""
        if not any(oggetto.bersagli or []): return False
        return not any(self._ancora_legale(oggetto, r, x, ctrl, fonte) for r, g in zip(reqs, oggetto.bersagli) for x in g)

    def _risolvi_abilita(self, a):
        t = self.t
        self.ha_priorita = None                                                                    # 117.2e
        t._evento("risolve", carta=a.fonte.carta, vecchio=a.n, giocatore=a.controllore, a="abilita",
                  quanto=len(t.pila), causa="608.1")
        reqs = a.reqs
        self._fonte_condizione, self._evento_condizione = a.fonte, a.evento
        if "se" in a.ab and self._se_alla_risoluzione() and not condizione(self, a.ab["se"], a.controllore): esito = "608.2a"
        elif self._tutti_illegali(a, reqs, a.controllore, a.fonte): esito = "608.2b"
        elif not self._abilita_indipendente() and not a.fonte.vivo: esito = "113.7a rotta"
        else:
            if not hasattr(self, "_volte_risolta"): self._volte_risolta = Counter()               # 15 nov 2026: le volte che ogni
            self._volte_risolta[(t.turno_numero, getattr(a.fonte, "n", None), id(a.ab))] += 1        # abilita' si risolve nel turno
            self._esegui(a, a.fa, reqs, a.controllore, a.fonte)                                     # 113.7a, 608.2c
            esito = "608.2n"
            if t.finita: return None                       # 104.1: la partita e' finita a meta' (104.2b), si ferma li'
        if a in t.pila: t.pila.remove(a)
        a.vivo, a.esito = False, esito
        t._evento("abilita", carta=a.fonte.carta, vecchio=a.n, da="pila", giocatore=a.controllore, causa=esito)
        return None

    def _risolvi_magia(self, m):
        t, c = self.t, m.carta
        self.ha_priorita = None                                                                    # 117.2e
        t._evento("risolve", carta=c, vecchio=m.n, giocatore=m.controllore, quanto=len(t.pila), causa="608.1")
        reqs = getattr(m, "reqs", [])
        via = "esilio" if getattr(m, "flashback", False) else "cimitero"                          # 702.34a
        avventura = getattr(m, "come_avventura", False)
        if self._tutti_illegali(m, reqs, m.controllore, m):
            dove = t.sposta(m, via, causa="608.2b")                                                 # 608.2b
        else:
            self._esegui(m, getattr(m, "fa", c.car.get("fa") or []), reqs, m.controllore, m)       # 608.2c
            if t.finita: return None                       # 104.1: la partita e' finita a meta' (104.2b), si ferma li'
            omen = avventura and "Omen" in c.tipo.split("—")[-1].split()                         # 721.3d: l'Omen si rimescola
            if omen and m.vivo and m.zona == "pila":
                t.sposta(m, "grimorio", posizione="mescola", causa="721.3d")
                self.lanciate[(t.turno_numero, m.controllore)] += 1
                return None
            if avventura: via = "esilio"                                                           # 716.3d: si risolve, va in esilio
            dove = t.sposta(m, via, causa="716.3d" if avventura else ("608.2n" if via == "cimitero" else "702.34a")) if m.vivo and m.zona == "pila" else None
            if avventura and dove is not None and dove.zona == "esilio":                           # 716.3d: finche' resta in esilio,
                self.permessi.append({"n": dove.n, "giocatore": m.controllore, "fino": "finche_in_esilio", "iniziato": False})   # la gioca
                t._evento("permesso", carta=dove.carta, vecchio=dove.n, giocatore=m.controllore, a="finche_in_esilio", causa="716.3d")
        self.lanciate[(t.turno_numero, m.controllore)] += 1
        return dove

    def _chi_subisce(self, d, legali, ctrl, fonte):
        chi = d.get("chi", "tu")
        if chi == "tu": return [ctrl]
        if chi == "avversari": return [g.i for g in self.t.giocatori if g.i != ctrl and not g.perso]
        if chi == "giocatori": return [g.i for g in self.t.giocatori if not g.perso]
        if isinstance(chi, str) and chi.startswith("bersaglio"):                                   # 608.2b: solo i legali
            k = int(chi.split(":")[1]) if ":" in chi else 0
            return list(legali[k]) if k < len(legali) else []
        if chi == "fonte": return [fonte] if fonte.vivo and fonte.zona == "campo" else []          # 608.2h
        if chi == "questa_carta": return [fonte] if fonte.vivo else []                             # «this card», in qualsiasi zona
        if chi == "fonte_com_era": return [fonte]                                                  # 608.2h, 603.10a: anche spenta (le ultime informazioni)
        if isinstance(chi, list):                                                                  # due soggetti (lotta, danno pari alla forza)
            parti = [self._chi_subisce(dict(d, chi=c), legali, ctrl, fonte) for c in chi]
            return [x[0] for x in parti] if all(len(x) == 1 for x in parti) else []                 # 701.14b: uno manca, niente
        if isinstance(chi, str) and chi.startswith("controllore_bersaglio"):                         # 608.2h: anche spento
            k = int(chi.split(":")[1]) if ":" in chi else 0
            return [self._bersagli_iniziali[k][0].controllore] if self._bersagli_iniziali and self._bersagli_iniziali[k] else []
        if chi == "evento":                                                                        # l'oggetto in pila che ha innescato
            n = getattr(getattr(self._in_risoluzione, "evento", None), "nuovo", None)
            return [x for x in self.t.pila if x.n == n]
        if chi == "ricordati_esilio":                                                              # 603.7c: le carte esiliate che ricorda
            ns = (getattr(self._in_risoluzione, "ab", None) or {}).get("ricordati") or []
            return [x for x in (self.t.oggetti.get(n_) for n_ in ns) if x is not None and x.vivo and x.zona == "esilio"]
        if chi == "ricordati":                                                                     # 603.7c: l'oggetto che la ritardata ricorda
            ns = (getattr(self._in_risoluzione, "ab", None) or {}).get("ricordati") or []
            return [x for x in (self.t.oggetti.get(n_) for n_ in ns) if x is not None and x.vivo and x.zona == "campo"]
        if chi == "magia_evento":                                                                  # «copy that spell»: se e' ancora in pila (603.7c)
            n_ = getattr(getattr(self._in_risoluzione, "evento", None), "vecchio", None)
            return [x for x in self.t.pila if x.n == n_ and getattr(x, "carta", None) is not None]
        if chi == "create":                                                                        # la pedina appena creata
            di, via = getattr(self, "_create", (None, []))
            if di is not self._in_risoluzione: raise NonCoperto("608.2c: «it» senza una pedina creata da questa magia")
            return [x for x in via if x.vivo and x.zona == "campo"]
        if chi == "controllore_entrato":                                                           # «that player»: chi controlla quella che e' entrata
            x = self.t.oggetti.get(getattr(getattr(self._in_risoluzione, "evento", None), "nuovo", None))
            return [x.controllore] if x is not None and x.controllore is not None else []
        if chi == "controllore_morto":                                                             # «that player»: chi la controllava
            x = self.t.oggetti.get(getattr(getattr(self._in_risoluzione, "evento", None), "vecchio", None))
            return [x.controllore] if x is not None and x.controllore is not None else []
        if chi == "giocatore_evento":                                                              # «that player»: chi ha attivato
            g_ = getattr(getattr(self._in_risoluzione, "evento", None), "giocatore", None)
            return [g_] if g_ is not None else []
        if chi == "oggetti_eventi":                                                                # «those creatures»
            ns = [getattr(e_, "vecchio", None) for e_ in getattr(self._in_risoluzione, "eventi", None) or []]
            return [x for x in (self.t.oggetti.get(n_) for n_ in ns) if x is not None and x.vivo and x.zona == "campo"]
        if chi == "entrata_evento":                                                                # «that creature» (quella che e' entrata)
            x = self.t.oggetti.get(getattr(getattr(self._in_risoluzione, "evento", None), "nuovo", None))
            return [x] if x is not None and x.vivo and x.zona == "campo" else []
        if chi == "oggetto_evento":                                                                # «that creature» (quella che attacca)
            x = self.t.oggetti.get(getattr(getattr(self._in_risoluzione, "evento", None), "vecchio", None))
            return [x] if x is not None and x.vivo and x.zona == "campo" else []
        if chi == "controllore_oggetto_evento":                                                    # «that creature's controller»
            x = self.t.oggetti.get(getattr(getattr(self._in_risoluzione, "evento", None), "vecchio", None))
            return [x.controllore] if x is not None and x.controllore is not None else []
        if chi == "carta_evento":                                                                  # «return that card»
            x = self.t.oggetti.get(getattr(getattr(self._in_risoluzione, "evento", None), "nuovo", None))
            return [x] if x is not None and x.vivo else []
        if isinstance(chi, dict) and chi.get("di_bersaglio"):                                      # «each creature target player controls»
            k = int(chi["di_bersaglio"].split(":")[1])
            gioc = [x for x in (legali[k] if k < len(legali) else []) if _e_giocatore(x)]
            sel = {a: b for a, b in chi.items() if a != "di_bersaglio"}
            return [o for o in self.t.campo if o.controllore in gioc and scelto(sel, o, fonte, o.controllore)]
        if isinstance(chi, dict):                                                                  # 608.2h
            fuori = set(getattr(self, "_create", (None, []))[1]) if chi.get("non_create") else set()
            return [o for o in self.t.campo if scelto(chi, o, fonte, ctrl) and o not in fuori]
        raise NonCoperto(f"608.2c: il destinatario {chi!r} non e' coperto")

    def _valuta_quantita(self, d, ctrl, fonte, ogg):
        """«where X is ...»: le quantita' variabili si contano quando l'istruzione si applica (608.2h, 611.2d)."""
        if d.get("n") == "X" and d.get("fa") in ("macina", "surveil", "scry", "scarta", "segnalini"):   # 107.3a (giri 7, 10): la X della magia
            d = dict(d, n=getattr(ogg, "x", 0) or 0)
        if not any(isinstance(d.get(k), dict) for k in ("n", "p", "t", "quante", "volte")): return d
        d = dict(d)
        for k in ("n", "p", "t", "quante", "volte"):                                               # (anche «up to that many»)
            v = d.get(k)
            if isinstance(v, dict): d[k] = v.get("segno", 1) * v.get("molt", 1) * self.conta(v["conta"], ctrl, fonte, ogg)   # «2 life for each»
        return d

    def conta(self, spec, ctrl, fonte, ogg):
        t = self.t
        tipo = spec["tipo"]
        if tipo == "cimitero_tuo": return len(t.giocatori[ctrl].cimitero)
        if tipo == "terre_nomi_diversi":                                                           # 201.2: nomi diversi
            return len({o.nome for o in t.campo if o.controllore == ctrl and "land" in o.carta.tipi})
        if tipo == "colori_permanenti":                                                            # 105.2: i colori, non incolore
            return len(set().union(*[colori_di(o) for o in t.campo if o.controllore == ctrl] or [set()]) & set("WUBRG"))
        if tipo == "controlli": return sum(1 for o in t.campo if o.controllore == ctrl and scelto(spec["sel"], o, fonte, ctrl))
        if tipo == "campo_sel": return sum(1 for o in t.campo if scelto(spec["sel"], o, fonte, ctrl))   # «the number of X you control»
        if tipo == "cimitero_sel":                                                                 # «the number of creature cards in your graveyard»
            return sum(1 for o in t.giocatori[ctrl].cimitero if (not spec.get("tipi") or set(spec["tipi"]) & o.carta.tipi)
                       and (not spec.get("sottotipo") or ha_sottotipo(o, spec["sottotipo"])))
        if tipo == "attaccanti":                                                                   # 506.4
            return sum(1 for o in (getattr(self, "attaccanti", None) or {}) if o.vivo and o.zona == "campo" and (not spec.get("tuoi") or o.controllore == ctrl))
        if tipo == "pescate_turno":                                                                # 121.1
            return sum(1 for e_ in t.eventi_del_turno() if e_.tipo == "zona" and e_.da == "grimorio" and e_.a == "mano"
                       and e_.giocatore == ctrl and e_.causa in ("121.1", "504.1"))
        if tipo == "lanciate_turno": return sum(1 for e_ in t.eventi_del_turno() if e_.tipo == "lanciata" and e_.giocatore == ctrl)
        if tipo == "forza_fonte":                                                                  # «this creature's power» (608.2h: alla
            x = fonte if fonte is not None and getattr(fonte, "zona", None) == "campo" else None     # risoluzione; fuori dal campo, l'ultima
            if x is None and fonte is not None: return max(0, forza(fonte)) if getattr(fonte, "carta", None) is not None else 0   # nota, 608.2h)
            return max(0, forza(x)) if x is not None else 0
        if tipo == "forza_evento":                                                                 # «that creature's power» (608.2h)
            x = t.oggetti.get(getattr(getattr(ogg, "evento", None), "nuovo", None))
            return forza(x) if x is not None else 0
        if tipo == "forza_max_tue": return max([forza(o) for o in t.campo if o.controllore == ctrl and "creature" in o.carta.tipi] or [0])
        if tipo == "costituzione_max_tue": return max([costituzione(o) for o in t.campo if o.controllore == ctrl and "creature" in o.carta.tipi] or [0])
        if tipo == "mano_fino": return max(0, spec["n"] - len(t.giocatori[ctrl].mano))             # «draw cards equal to the difference»
        if tipo == "morte_turno":                                                                  # «creatures that died this turn» (700.4)
            return sum(1 for e_ in t.eventi_del_turno() if e_.tipo == "zona" and e_.da == "campo" and e_.a == "cimitero"
                       and e_.carta is not None and "creature" in e_.carta.tipi)
        if tipo == "costituzione_fonte":                                                           # «this creature's toughness» (608.2h:
            if fonte is None or getattr(fonte, "carta", None) is None: return 0                    # fuori dal campo l'ultima nota)
            return max(0, costituzione(fonte) or 0)
        if tipo == "fc_bersaglio":                                                                 # «its toughness»: il bersaglio (608.2h:
            g_ = (getattr(self, "_bersagli_iniziali", None) or [])                                 # com'era, se ha lasciato il campo)
            x = g_[spec["k"]][0] if spec["k"] < len(g_) and g_[spec["k"]] else None
            if x is None or _e_giocatore(x): return 0
            return max(0, (forza(x) if spec["quale"] == "forza" else costituzione(x)) or 0)
        if tipo == "vite_tue": return t.giocatori[ctrl].vite                                        # 119.1: «your life total»
        if tipo == "x_magia": return getattr(ogg, "x", 0) or 0                                     # 107.3a: la X della magia
        if tipo == "quanto_evento": return getattr(getattr(ogg, "evento", None), "quanto", 0) or 0   # «that many»: quel danno
        if tipo == "vita_guadagnata_turno":
            return sum(e_.quanto for e_ in t.eventi_del_turno() if e_.tipo == "vite" and e_.giocatore == ctrl and (e_.quanto or 0) > 0)
        if tipo in ("mana_speso", "colori_spesi"):                                                 # 601.2h: della magia dell'evento o
            n_ = getattr(getattr(ogg, "evento", None), "vecchio", None) if spec.get("di") == "evento" else getattr(fonte, "n", None)   # di questa
            return mana_speso(t, n_)[0 if tipo == "mana_speso" else 1]
        if tipo == "esiliate_qui":                                                                 # «exiled this way»
            return self._ultimo_conto
        if tipo == "distrutte_qui":                                                                # 701.8a (giro 12): «destroyed this way»
            return sum(1 for c_ in self._ultime_distrutte if not spec.get("tipi") or set(spec["tipi"]) & c_.tipi)
        if tipo == "pescate_qui": return getattr(self, "_pescate_qui", 0)                          # «the number of cards drawn this way»
        if tipo == "mano_tua": return len(t.giocatori[ctrl].mano)                                  # «the number of cards in your hand»
        if tipo == "tipi_planeswalker":                                                            # 205.3j: i tipi di planeswalker
            return len({w for o in t.campo if o.controllore == ctrl and "planeswalker" in o.carta.tipi for w in o.carta.tipo.split("—")[-1].split()}
                       if any("—" in o.carta.tipo for o in t.campo) else set())
        if tipo == "dal_grimorio_al_cimitero":                                                     # «put into target player's graveyard from their library this turn»
            k = int(spec["bersaglio"].split(":")[1])
            g_ = self._bersagli_iniziali[k] if self._bersagli_iniziali and k < len(self._bersagli_iniziali) else []
            gioc = [x for x in g_ if _e_giocatore(x)]
            return sum(1 for e_ in t.eventi_del_turno() if e_.tipo == "zona" and e_.da == "grimorio" and e_.a == "cimitero"
                       and e_.carta is not None and e_.carta.proprietario in gioc)
        if tipo == "eventi_innesco":                                                               # «that many»: gli eventi dell'innesco
            return len(getattr(ogg, "eventi", None) or [])                                         # (le carte scartate insieme, 603.2c)
        if tipo == "danno_ricevuto":                                                               # «that many»: il danno di quell'evento
            return sum(e_.quanto or 0 for e_ in getattr(ogg, "eventi", None) or [] if e_.tipo == "danno" and e_.nuovo == fonte.n)
        if tipo == "cimitero_ogni": return len(t.giocatori[ctrl].cimitero) // spec["ogni"]         # 107.1a: «for every three cards»
        if tipo == "segnalini_fonte": return fonte.segnalini[spec["segnalino"]] if fonte is not None else 0   # «for each charge counter on ~»
        if tipo == "segnalini_fonte_tutti": return sum(v for v in fonte.segnalini.values() if v > 0) if fonte is not None else 0   # 122.1
        if tipo == "somma": return spec.get("piu", 0) + sum(self.conta(s_, ctrl, fonte, ogg) for s_ in spec["parti"])   # «1 plus ...»
        if tipo == "colori_altri_artefatti":                                                       # 105.2, 202.2: i colori, non i simboli
            return len(set().union(*[colori_di(o) for o in t.campo if o.controllore == ctrl and "artifact" in o.carta.tipi and o is not fonte] or [set()]))
        if tipo == "mv_max_cimitero":                                                              # «the greatest mana value among cards in your graveyard»
            return max([M.valore(x.carta.car.get("costo") or "") for x in t.giocatori[ctrl].cimitero] or [0])
        if tipo == "eccesso":                                                                      # «that excess damage» (120.10)
            di, v = getattr(self, "_eccesso", (None, 0))
            if di is not ogg: raise NonCoperto("120.10: «that excess damage» senza un danno di questa magia")
            return v
        if tipo == "avversari_senza_due_nonterra":                                                 # «for each opponent who didn't discard two nonland cards this way»
            di, via = getattr(self, "_scartate", (None, []))
            if di is not ogg: raise NonCoperto("608.2h: «this way» senza uno scarto di questa magia o abilita'")
            return sum(1 for g in t.giocatori if g.i != ctrl and not g.perso
                       and sum(1 for x in via if x.proprietario == g.i and "land" not in x.carta.tipi) < 2)
        if tipo == "scartate_qui":                                                                 # «one or more nonland cards this way»
            di, via = getattr(self, "_scartate", (None, []))
            if di is not ogg: raise NonCoperto("608.2h: «this way» senza uno scarto di questa magia o abilita'")
            return sum(1 for x in via if not set(spec.get("non_tipi") or ()) & x.carta.tipi)
        if tipo == "scartate_turno":                                                               # «each card you've discarded this turn»
            return sum(1 for e_ in t.eventi_del_turno() if e_.tipo == "zona" and e_.da == "mano" and e_.a == "cimitero"
                       and e_.causa in SCARTI and e_.giocatore == ctrl)
        raise NonCoperto(f"608.2h: la quantita' {spec} non e' coperta")

    def _insieme_fissato(self, d, oggetti):
        """611.2c: l'insieme degli oggetti di un effetto di una magia o abilita' si fissa quando comincia."""
        return frozenset(o.n for o in oggetti)

    def _esegui(self, oggetto, fa, reqs, ctrl, fonte):
        """608.2c: le istruzioni nell'ordine scritto; 608.2b: i bersagli illegali non subiscono niente; 608.2f: le
        azioni su piu' oggetti insieme."""
        legali = [[x for x in g if self._ancora_legale(oggetto, r, x, ctrl, fonte)]
                  for r, g in zip(reqs, oggetto.bersagli or [])]
        self._bersagli_iniziali = [list(g) for g in (oggetto.bersagli or [])]
        self._in_risoluzione = oggetto
        self._fatto = None
        attaccavano = {x.n for g in self._bersagli_iniziali for x in g if not _e_giocatore(x) and x in self.attaccanti}
        valutate = {}
        for d in fa:
            if self.t.finita: return
            if d["fa"] not in ISTRUZIONI: raise NonCoperto(f"608.2c: l'istruzione {d['fa']!r} non e' coperta")
            se = d.get("se") or {}
            if "bersaglio_attaccava" in se:                                                        # 608.2h: com'era
                g = self._bersagli_iniziali[se.get("k", 0)] if self._bersagli_iniziali else []
                if bool(g and g[0].n in attaccavano) != se["bersaglio_attaccava"]: continue
            if "bersaglio_era" in se:                                                              # 608.2h: com'era
                g = self._bersagli_iniziali[se.get("k", 0)] if self._bersagli_iniziali else []
                if not (g and not _e_giocatore(g[0]) and set(se["bersaglio_era"]) <= g[0].carta.tipi): continue
            if "bersaglio_sottotipo" in se:                                                        # «If it's a Spider» (608.2h: com'era)
                g = self._bersagli_iniziali[se.get("k", 0)] if self._bersagli_iniziali else []
                if not (g and not _e_giocatore(g[0]) and ha_sottotipo(g[0], se["bersaglio_sottotipo"])): continue
            if "evento_sottotipo" in se:                                                           # «If that land is a Mountain»
                n_ = getattr(getattr(oggetto, "evento", None), "nuovo", None)
                x_ = self.t.oggetti.get(n_)
                if not (x_ is not None and se["evento_sottotipo"] in x_.carta.tipo.split("—")[-1].split()): continue
            if "risolta_volte" in se:                                                              # «if this is the second time this
                v_ = (getattr(self, "_volte_risolta", None) or {}).get((self.t.turno_numero, getattr(fonte, "n", None), id(getattr(oggetto, "ab", None))), 0)
                if v_ != se["risolta_volte"]: continue                                             # ability has resolved this turn»
            if "cimitero_almeno" in se:                                                            # letta una volta, a quel punto
                kc = ("cimitero", se.get("gruppo", 0))
                if kc not in valutate: valutate[kc] = len(self.t.giocatori[ctrl].cimitero) >= se["cimitero_almeno"]
                if not valutate[kc]: continue
            if "grimorio_vuoto" in se and bool(self.t.giocatori[ctrl].grimorio.carte) == se["grimorio_vuoto"]: continue
            if "dal_cimitero" in se and bool(getattr(oggetto, "flashback", False)) != se["dal_cimitero"]: continue
            if "lanciata_dal_cimitero" in se:                                                      # «if this spell was cast from a graveyard»
                n_ = getattr(oggetto, "n", None)                                                   # (601.2a: la zona da cui e' andata in pila)
                da_ = next((e.da for e in reversed(self.t.eventi) if e.tipo == "zona" and e.a == "pila" and e.nuovo == n_), None)
                if (da_ == "cimitero") != se["lanciata_dal_cimitero"]: continue
            if "eccesso" in se and (self.conta({"tipo": "eccesso"}, ctrl, fonte, oggetto) > 0) != se["eccesso"]: continue
            if "guardato_turno" in se and any(e_.tipo == "guarda" and e_.giocatore == ctrl for e_ in self._eventi_del_turno()) != se["guardato_turno"]: continue
            if "sacrificato_tu" in se:                                                             # «If you sacrificed a creature this way»
                di, chi_ = getattr(self, "_sacrificati", (None, set()))
                if (di is oggetto and ctrl in chi_) != se["sacrificato_tu"]: continue
            if "segnalini_fonte_almeno" in se or "segnalini_fonte_meno" in se:                     # 608.2c: i segnalini della fonte adesso
                ha_ = fonte is not None and segnalini_ok(fonte, se.get("segnalini_fonte_almeno") or se.get("segnalini_fonte_meno"))
                if ("segnalini_fonte_almeno" in se) != ha_: continue
            if "facoltativo_pagato" in se:                                                         # 702.33d: «if this spell was kicked»
                v_ = getattr(oggetto, "facoltativo_pagato", None)
                if v_ is None: v_ = getattr(fonte, "facoltativo_pagato", False)
                if bool(v_) != se["facoltativo_pagato"]: continue
            if "mana_speso_almeno" in se or "mana_speso_meno" in se:                               # 601.2h: la magia dell'evento
                q_ = mana_speso(self.t, getattr(getattr(oggetto, "evento", None), "vecchio", None))[0]
                if "mana_speso_almeno" in se and q_ < se["mana_speso_almeno"]: continue
                if "mana_speso_meno" in se and q_ >= se["mana_speso_meno"]: continue
            if "controlli_cond" in se:                                                             # «if you control ...» (608.2c: adesso)
                cc = se["controlli_cond"]
                if sum(1 for o in self.t.campo if o.controllore == ctrl and scelto(cc["sel"], o, fonte, ctrl)) < cc["n"]: continue
            if "statica_non" in se:                                                                # 608.2c (giro 9): «instead»: vale se la
                chi_n = fonte if fonte is not None and getattr(fonte, "controllore", None) == ctrl else types.SimpleNamespace(controllore=ctrl, n=-1)   # condizione
                if self.t.condizione_statica(se["statica_non"], chi_n): continue                    # e' falsa
            if "statica" in se:                                                                    # 608.2c, 611.3a: la condizione adesso
                chi_c = fonte if fonte is not None and getattr(fonte, "controllore", None) == ctrl else types.SimpleNamespace(controllore=ctrl, n=-1)
                if not self.t.condizione_statica(se["statica"], chi_c): continue
            if set(se) - {"bersaglio_attaccava", "bersaglio_era", "bersaglio_sottotipo", "k", "evento_sottotipo", "fatto", "cimitero_almeno", "gruppo", "grimorio_vuoto", "eccesso", "guardato_turno", "dal_cimitero", "sacrificato_tu", "controlli_cond", "statica",
                             "mana_speso_almeno", "mana_speso_meno", "facoltativo_pagato", "segnalini_fonte_almeno", "segnalini_fonte_meno", "risolta_volte", "lanciata_dal_cimitero", "statica_non"}:
                raise NonCoperto(f"608.2c: la condizione {se} non e' coperta")
            if "fatto" in se and bool(self._fatto) != se["fatto"]: continue                        # «If you do»
            if d.get("puoi"):                                                                      # 603.5, 608.2d
                chi_sc = ctrl
                if d.get("puoi_chi"):                                                              # «its controller may»: decide lui
                    gg = self._chi_subisce(dict(d, chi=d["puoi_chi"]), legali, ctrl, fonte)
                    if gg: chi_sc = gg[0]
                g = (self.chi or {}).get(chi_sc)
                if not (g.sceglie(self, chi_sc, d) if hasattr(g, "sceglie") else True):
                    self._fatto = False
                    continue
            d = self._valuta_quantita(d, ctrl, fonte, oggetto)                                      # 608.2h, 611.2d: una volta, adesso
            chi = self._chi_subisce(d, legali, ctrl, fonte)
            k_ev = len(self.t.eventi)
            with self.t.insieme():
                esito = ISTRUZIONI[d["fa"]][1](self, d, chi, ctrl, fonte, oggetto)
            self._ultimo_conto = sum(1 for e_ in self.t.eventi[k_ev:] if e_.tipo == "zona" and e_.a == "esilio")   # «this way»
            if d["fa"] == "distruggi":                                                             # 701.8a: «destroyed this way»
                self._ultime_distrutte = [e_.carta for e_ in self.t.eventi[k_ev:] if e_.tipo == "zona" and e_.da == "campo" and e_.carta is not None]
            if d.get("puoi") or d.get("segna"):                                                    # e' successo davvero? (603.12)
                self._fatto = bool(esito) if esito is not None else len(self.t.eventi) > k_ev

    def _lancio_permesso(self, i, cond):
        """601.3: una carta che dice «You can't cast this spell unless ...»."""
        for k, v in cond.items():
            if k == "cimitero_almeno":
                if len(self.t.giocatori[i].cimitero) < v: return False
            else: raise NonCoperto(f"601.3: la condizione di lancio {k!r} non e' coperta")
        return True

    def contrasta(self, x, causa="701.6a"):
        """701.6a: la magia va nel cimitero del proprietario, l'abilita' lascia la pila e smette di esistere. 101.2:
        una magia che «can't be countered» resta in pila."""
        if getattr(x, "incontrastabile", False):
            self.t._evento("resta", carta=x.carta, vecchio=x.n, a="pila", causa="101.2")
            return None
        if isinstance(x, Abilita):
            if not (x.vivo and x in self.t.pila): return None
            self.t.pila.remove(x)
            x.vivo, x.esito = False, causa
            self.t._evento("abilita", carta=x.fonte.carta, vecchio=x.n, da="pila", giocatore=x.controllore, causa=causa)
            return x
        if getattr(x, "flashback", False) and x.vivo and x.zona == "pila":                        # 702.34a
            return self.t.sposta(x, "esilio", causa="702.34a")
        return super().contrasta(x, causa)

    def _svuota_mana(self):
        """106.4, 500.5; «until end of combat, you don't lose this mana as steps and phases end» (702.189a): il mana protetto
        resta, quanto ne resta nella riserva, fino alla fine del passo di fine combattimento."""
        prot = getattr(self, "mana_protetto", None) or {}
        for g in self.t.giocatori:
            p_ = prot.get(g.i)
            if p_ and self.fase == "combattimento" and self.passo != "fine":
                tieni = {k: min(g.riserva.m[k], p_.get(k, 0)) for k in g.riserva.m}
                g.riserva.svuota()
                for k, n in tieni.items(): g.riserva.m[k] = n
                prot[g.i] = tieni
            else:
                g.riserva.svuota()
                prot.pop(g.i, None)
        for i in self.vincolato: self.vincolato[i] = []                                            # 106.4: anche il mana vincolato

    def _azioni_del_turno(self, i, passo, giocatori):
        """703.4f: subito dopo l'inizio della prima fase principale, un segnalino lore su ogni saga coi capitoli di chi e' di
        turno (715.3b)."""
        if self.fase == "principale_1" and passo is None:
            for o in [o for o in self.t.campo if o.controllore == i and o.carta.car.get("capitoli")]:
                self.t.metti_segnalini(o, "lore", 1, causa="703.4f")
        super()._azioni_del_turno(i, passo, giocatori)

    def _limite_terre(self, i):
        statiche = sum(sum(self.t.regola_valori("terra_extra", f)) for f in self.t.campo if f.controllore == i)   # 305.2: statiche
        return 1 + self.terre_in_piu[(i, self.t.turno_numero)] + (statiche if self.attivo == i else 0)

    def _motivo_non_attacca(self, o, i):
        m = super()._motivo_non_attacca(o, i)
        if m is None and self.t.regola("non_attacca", o): return "508.1c: un effetto dice che la creatura non puo' attaccare"
        return m

    def _ha_difensore(self, o):
        """702.3b; «can attack as though it didn't have defender» se chi la controlla ha guardato in questo turno."""
        if o.carta.car.get("attacca_se_guardato") and any(e.tipo == "guarda" and e.giocatore == o.controllore
                                                            for e in self._eventi_del_turno()): return False
        if self.t.regola("attacca_con_difensore", o): return False                                  # 613.11
        return super()._ha_difensore(o)

    def _danno_di(self, o):
        """510.1a, 613.11: «assigns combat damage equal to its toughness rather than its power»."""
        if self.t.regola("danno_costituzione", o): return costituzione(o)
        if self.t.regola("danno_assoluto", o) and forza(o) < 0: return -forza(o)
        return super()._danno_di(o)

    def _eventi_del_turno(self):
        k = max((j for j, e in enumerate(self.t.eventi) if e.tipo == "turno"), default=0)
        return self.t.eventi[k:]

    # ------------------------------------------------------------------ il mana e lo stap
    def terre_stappate(self, i):
        """605.1a: le fonti di mana sono i permanenti stappati con un'abilita' {T}: Add; una creatura con la debolezza da
        evocazione non usa il {T} (302.6, 602.5a), salvo rapidita'."""
        fonti = [o for o in self.t.campo if o.controllore == i and not o.tappato and self.produzioni(o)
                 and ("creature" not in o.carta.tipi or not self.debole(o) or "haste" in parole(o))]
        if getattr(self, "_senza_fonte", None) is not None: fonti = [o for o in fonti if o is not self._senza_fonte]
        if self._divieti_attivazione(): fonti = [o for o in fonti if not self.t.regola("non_attivabili", o)]   # 602.5: anche il mana
        fonti += [o for o in self._da_convocare(i) if o not in fonti]                              # 702.51a
        if self._spesa is None: return fonti                                                       # 605.3a: per la riserva, tutte
        return [o for o in fonti if not o.carta.car.get("mana_vincolo") or self._vincolo_ok(o.carta.car["mana_vincolo"])]   # 106.6

    def _divieti_attivazione(self):
        """C'e' in campo una statica «its activated abilities can't be activated»? (per non cercarla a ogni conto)"""
        return any(d.get("non_attivabili") for o in self.t.campo for ab in (o.carta.car.get("abilita") or ()) if ab.get("tipo") == "statica"
                   for d in ab["effetti"])

    def _da_convocare(self, i):
        """702.51a: lanciando una magia con convoke, ogni creatura stappata di chi la lancia puo' pagare {1} o un mana del
        suo colore (anche con la debolezza da evocazione: non e' un {T}); 702.51b: dopo il costo totale."""
        c = self._spesa
        if not (c and c[0] == "magia" and (c[1].car.get("convoke") or c[1].car.get("improvise"))): return []
        if "{C}" in (c[1].car.get("costo") or ""): raise NonCoperto("702.51a, 702.126a: convoke o improvise con un simbolo {C} nel costo")
        out = [o for o in self.t.campo if o.controllore == i and "creature" in o.carta.tipi and not o.tappato] if c[1].car.get("convoke") else []
        if c[1].car.get("improvise"):                                                              # 702.126a: ogni artefatto stappato paga
            out += [o for o in self.t.campo if o.controllore == i and "artifact" in o.carta.tipi and not o.tappato and o not in out]   # {1}
        return out

    def produzioni(self, ogg):
        proprie = self._produzioni_proprie(ogg)
        if proprie and self.mana_in_piu and ogg.zona == "campo" and "land" in ogg.carta.tipi:      # 605.4a: Molten Tide
            sotto = set(ogg.carta.tipo.split("//")[0].partition("—")[2].split())
            extra = [M.produzione(m) for j, st, m in self.mana_in_piu if j == ogg.controllore and st in sotto]
            if extra:
                somma = tuple(map(sum, zip(*extra)))
                proprie = tuple(dict.fromkeys(tuple(a + b for a, b in zip(pr, somma)) for pr in proprie))
        if ogg.zona == "campo" and ogg in self._da_convocare(ogg.controllore):
            if "creature" in ogg.carta.tipi and self.debole(ogg) and "haste" not in parole(ogg): proprie = ()   # 302.6: il suo {T} no
            spesa_ = self._spesa[1].car
            convoke = ([M.produzione("{%s}" % c) for c in sorted(colori_di(ogg))] if spesa_.get("convoke") and "creature" in ogg.carta.tipi
                       else []) + [M.produzione("{C}")]                                            # {C} paga solo generico qui (702.126a)
            return tuple(dict.fromkeys(list(proprie) + convoke))
        return proprie

    def tappa_per_mana(self, i, terra, prod=None):
        if terra in self._da_convocare(i) and prod is not None and prod not in self._produzioni_proprie(terra):
            if not self.t.tappa(terra): return False                                               # 702.51a: si tappa la creatura
            self.t.giocatori[i].riserva.aggiungi(prod)
            self.t._evento("mana", carta=terra.carta, vecchio=terra.n, giocatore=i, a=M.scrivi(prod), quanto=sum(prod), causa="702.51a")
            return True
        ok = self._tappa_per_mana_vincolo(i, terra, prod)
        if ok and terra.carta.car.get("mana_sacrifica"): self.t.sacrifica(terra, i, causa="701.21a")    # 605.1a, 111.10a: il resto del costo
        return ok

    def _produzioni_proprie(self, ogg):
        """Le abilita' di mana {T} dell'oggetto: le sue (se un effetto non gliele ha tolte, 613.1f) piu' quelle che un
        effetto gli ha dato dopo (613.1f, 605.1a: «Target land gains "{T}: Add {C}{C}"», Emrakul, the Exigent Doom)."""
        v = self.t.caratteristiche(ogg) if ogg.zona == "campo" else {}
        date = tuple(M.produzione(m) for m in v.get("mana_dato") or ())
        proprie = self._produzioni_stampate(ogg) if v.get("mana_ok", True) else ()
        return tuple(dict.fromkeys(proprie + date)) if date else proprie

    def _produzioni_stampate(self, ogg):
        car = ogg.carta.car
        if car.get("mana_colore_scelto"):                                                           # «one mana of the chosen color»
            c = getattr(ogg, "colore_scelto", None)
            return (M.produzione("{%s}" % c),) if c else ()
        if car.get("mana_poteri_diversi"):                                                          # Loot: si sceglie il colore (105.4)
            n = len({forza(o) for o in self.t.campo if o.controllore == ogg.controllore and "creature" in o.carta.tipi})
            return tuple(M.produzione("{%s}" % c * n) for c in "WUBRG") if n else ()
        base = super().produzioni(ogg)                                                             # 305.6, 605 (le basi senza «mana»)
        for mc in car.get("mana_cond") or ():                                                      # 602.5b: il mana condizionato
            if ogg.zona == "campo" and self._mana_condizione(ogg, mc["se"]):
                base = tuple(dict.fromkeys(tuple(base) + tuple(M.produzione(x) for x in mc["mana"])))
        return base

    def _mana_condizione(self, ogg, se):
        ctrl = ogg.controllore
        if se.get("statica") and not self.t.condizione_statica(se["statica"], ogg): return False   # 602.5b, 611.3a
        if se.get("entrata_turno_o_base"):
            entrata = any(e.tipo == "zona" and e.a == "campo" and e.nuovo == ogg.n for e in self._eventi_del_turno())
            base = any(o.controllore == ctrl and "land" in o.carta.tipi and "Basic" in o.carta.tipo.split("—")[0].split() for o in self.t.campo)
            if not (entrata or base): return False
        if se.get("controlli_sottotipo") and not any(o.controllore == ctrl and "—" in o.carta.tipo
                                                     and set(se["controlli_sottotipo"]) & set(o.carta.tipo.split("—")[-1].split()) for o in self.t.campo):
            return False
        return True

    def _stap(self, i):
        """502.3; 122.1d: con un segnalino stordimento al posto di stappare se ne toglie uno; «doesn't untap during your
        untap step» resta tappato."""
        for o in list(self.t.campo):
            if o.controllore != i or not o.tappato: continue
            if o.carta.car.get("non_stappa"): continue
            if any(getattr(a, "attaccato_a", None) == o.n and a.carta.car.get("blocca_stap") for a in self.t.campo): continue
            if o.segnalini["stordimento"] > 0: self.t.togli_segnalini(o, "stordimento", 1, causa="122.1d")
            else: self.t.stappa(o)

    # ------------------------------------------------------------------ il turno
    def _fine_turno(self):
        self.t.fine_turno()                                                                        # 514.2, 611.2a
        self.ritardate = [r for r in self.ritardate if r["fino"] != "fine_turno"]                  # 603.7b: «until end of turn»
        self.fedelta_rapide.clear()                                                                # 514.2: Jace's Machinations
        self.permessi = [r for r in self.permessi if r["fino"] != "fine_turno"]                     # 611.2a: «you may play that card this turn»
        self.mana_in_piu = []                                                                      # 603.7b: Molten Tide


# ====================================================================== il mazzo finto del passo 7
def _cr(costo, f, c, *abilita, parole=()):
    return {"costo": costo, "forza": f, "costituzione": c, "parole": list(parole), "abilita": list(abilita)}


STATICA = lambda *effetti: {"tipo": "statica", "effetti": list(effetti)}
TUE_ALTRE = {"tipi": ["creature"], "controllo": "tuo", "altre": True}
TUE = {"tipi": ["creature"], "controllo": "tuo"}
QUALSIASI = {"chi": ["any"]}
CREATURA = {"chi": ["creature"]}

CARTE_EFFETTI = {
    "Signore": ("Creature", _cr("{3}", 2, 2, STATICA({"livello": "7c", "chi": TUE_ALTRE, "p": 1, "t": 1}))),
    "Capobranco": ("Creature", _cr("{2}", 1, 1, STATICA({"livello": "6", "chi": TUE_ALTRE, "dai": ["flying"]}))),
    "Araldo": ("Creature", _cr("{2}", 1, 1, {"tipo": "innescata", "quando": {"evento": "entra"}, "bersagli": [CREATURA],
                                            "fa": [{"fa": "pompa", "chi": "bersaglio", "p": 2, "t": 2, "durata": "fine_turno"}]})),
    "Lascito": ("Creature", _cr("{1}", 1, 1, {"tipo": "innescata", "quando": {"evento": "muore"}, "fa": [{"fa": "pesca", "n": 1}]})),
    "Custode": ("Creature", _cr("{2}", 0, 3, {"tipo": "innescata", "quando": {"evento": "inizio_passo", "passo": "mantenimento", "di": "tuo"},
                                             "se": {"creature_almeno": 2}, "fa": [{"fa": "guadagna", "n": 1}]})),
    "Cannone": ("Creature", _cr("{2}", 1, 1, {"tipo": "attivata", "costo": {"tappa": True}, "velocita": "istantanea",
                                             "bersagli": [QUALSIASI], "fa": [{"fa": "danno", "n": 1, "chi": "bersaglio"}]})),
    "Velo": ("Creature", _cr("{2}", 2, 1, parole=["hexproof"])),
    "Mutante": ("Creature", _cr("{1}", 1, 1, {"tipo": "attivata", "costo": {"mana": "{2}"}, "velocita": "istantanea",
                                             "fa": [{"fa": "segnalini", "tipo": "+1/+1", "n": 1, "chi": "fonte"}]})),
    "Lutto": ("Creature", _cr("{2}", 1, 3, {"tipo": "innescata", "quando": {"evento": "una_muore", "chi": TUE_ALTRE},
                                           "fa": [{"fa": "guadagna", "n": 1}]})),
    "Orso": ("Creature", _cr("{2}", 2, 2)),
    "Eroe": ("Planeswalker", {"costo": "{3}", "fedelta": 3, "abilita": [
        {"tipo": "attivata", "fedelta": 1, "fa": [{"fa": "guadagna", "n": 2}]},
        {"tipo": "attivata", "fedelta": -2, "bersagli": [CREATURA], "fa": [{"fa": "danno", "n": 2, "chi": "bersaglio"}]}]}),
    "Fulmine": ("Instant", {"costo": "{1}", "bersagli": [QUALSIASI], "fa": [{"fa": "danno", "n": 2, "chi": "bersaglio"}]}),
    "Sete": ("Instant", {"costo": "{1}", "bersagli": [CREATURA],
                         "fa": [{"fa": "danno", "n": 2, "chi": "bersaglio"}, {"fa": "guadagna", "n": 2}]}),
    "Crescita": ("Instant", {"costo": "{1}", "bersagli": [CREATURA],
                             "fa": [{"fa": "pompa", "chi": "bersaglio", "p": 3, "t": 3, "durata": "fine_turno"}]}),
    "Avvizzire": ("Instant", {"costo": "{1}", "bersagli": [CREATURA],
                              "fa": [{"fa": "segnalini", "tipo": "-1/-1", "n": 1, "chi": "bersaglio"}]}),
    "Ammutolire": ("Instant", {"costo": "{1}", "bersagli": [CREATURA],
                               "fa": [{"fa": "togli_abilita", "chi": "bersaglio", "durata": "fine_turno"}]}),
    "Rimpicciolire": ("Instant", {"costo": "{1}", "bersagli": [CREATURA],
                                  "fa": [{"fa": "base", "chi": "bersaglio", "p": 0, "t": 1, "durata": "fine_turno"}]}),
    "Inversione": ("Instant", {"costo": "{1}", "bersagli": [CREATURA],
                               "fa": [{"fa": "scambia", "chi": "bersaglio", "durata": "fine_turno"}]}),
    "Contromagia": ("Instant", {"costo": "{2}", "bersagli": [{"chi": ["spell"]}], "fa": [{"fa": "contrasta", "chi": "bersaglio"}]}),
    "Cataclisma": ("Sorcery", {"costo": "{4}", "fa": [{"fa": "distruggi", "chi": {"tipi": ["creature"]}}]}),
    "Raduno": ("Sorcery", {"costo": "{2}", "fa": [{"fa": "pompa", "chi": TUE, "p": 1, "t": 1, "durata": "fine_turno"}]}),
    # solo per le prove delle regole
    "Bastione": ("Enchantment", {"costo": "{2}", "abilita": [STATICA({"livello": "7c", "chi": TUE, "p": 0, "t": 2})]}),
    "Doppio": ("Sorcery", {"costo": "{1}", "bersagli": [{"chi": ["creature"], "quanti": 2}],
                           "fa": [{"fa": "pompa", "chi": "bersaglio", "p": 1, "t": 1, "durata": "fine_turno"}]}),
    "Tesoriere": ("Creature", _cr("{2}", 1, 1, {"tipo": "innescata", "quando": {"evento": "entra"}, "fa": [{"fa": "pesca", "n": 1, "puoi": True}]})),
    "Vedetta": ("Creature", _cr("{2}", 2, 2, {"tipo": "innescata", "quando": {"evento": "attacca"}, "fa": [{"fa": "guadagna", "n": 1}]})),
    "Corvo": ("Creature", _cr("{2}", 1, 1, {"tipo": "innescata", "quando": {"evento": "una_entra", "chi": {"tipi": ["creature"], "controllo": "tuo"}},
                                           "fa": [{"fa": "guadagna", "n": 1}]})),
}

COMPOSIZIONE_EFFETTI = {"Signore": 1, "Capobranco": 1, "Araldo": 2, "Lascito": 2, "Custode": 1, "Cannone": 2, "Velo": 1,
                        "Mutante": 1, "Lutto": 1, "Orso": 1, "Eroe": 1, "Fulmine": 1, "Crescita": 1, "Avvizzire": 1,
                        "Ammutolire": 1, "Rimpicciolire": 1, "Inversione": 1, "Contromagia": 1, "Cataclisma": 1, "Raduno": 1}
SOLO_PROVE = ("Bastione", "Doppio", "Tesoriere", "Vedetta", "Corvo", "Sete")


def _voce(nome):
    tipo, car = CARTE_EFFETTI[nome]
    return (nome, tipo, car)


def mazzo_effetti():
    """17 terre generiche e 23 carte con abilita' (il mazzo delle partite a caso del passo 7)."""
    mazzo = [("Terra", "Land", {"mana": ["{C}"]})] * 17
    for nome, k in COMPOSIZIONE_EFFETTI.items(): mazzo += [_voce(nome)] * k
    return mazzo


def mazzo_dipendenze():
    """Il mazzo delle partite a caso con piu' Capobranco e Ammutolire: il caso della dipendenza (613.8) capita spesso."""
    comp = dict(COMPOSIZIONE_EFFETTI, Capobranco=4, Ammutolire=4, Cataclisma=0, Contromagia=0, Raduno=0, Lutto=0, Velo=0, Eroe=0)
    mazzo = [("Terra", "Land", {"mana": ["{C}"]})] * 17
    for nome, k in comp.items(): mazzo += [_voce(nome)] * k
    return mazzo


def mazzo_prove():
    """Il mazzo delle prove delle regole: quello delle partite a caso, piu' le carte che servono solo alle prove."""
    return mazzo_effetti() + [_voce(n) for n in SOLO_PROVE for _ in range(2)] + [_voce("Orso")] * 3


# ====================================================================== i giocatori finti
class GiocaEffetti(C.Combatte):
    """Combatte, in piu' attiva le abilita' che puo' nella prima fase principale a pila vuota (fedelta' prima)."""

    def agisci(self, p, i):
        mossa = super().agisci(p, i)
        if mossa is not None or p.fase != "principale_1" or p.t.pila or not p.da_stregoneria(i): return mossa
        for o in list(p.t.campo):
            if o.controllore != i: continue
            for k, ab in p.t.abilita_di(o):
                if ab.get("tipo") == "attivata" and p.puo_attivare(i, o, k): return ("attiva", o, k)
        return None


class CasoEffetti(C.CasoCombatte):
    """CasoCombatte che anche attiva abilita' a caso, sceglie bersagli a caso (ogni tanto illegali), ordina gli
    inneschi a caso e risponde a caso ai «puoi»."""

    def __init__(self, seme, attiva=0.3, **kw):
        super().__init__(seme, **kw)
        self.p_attiva = attiva

    def agisci(self, p, i):
        esiliate = [o for o in p.t.esilio if p.permesso(i, o)]                                     # 601.3: le carte che puo' giocare dall'esilio
        if esiliate and self.rng.random() < 0.5:                                                   # (il generatore si usa solo se ce ne sono)
            o = self._uno(esiliate)
            if "land" in o.carta.tipi: return ("terra", o)
            x = int(self.rng.integers(0, (p.x_massimo(i, o) or 0) + 1)) if "{X}" in (o.carta.car.get("costo") or "") else 0
            return ("lancia", o, x, None)                                                          # anche illegale: il motore la rifiuta
        if self.rng.random() < self.p_attiva:
            mie = [(o, k) for o in p.t.campo if o.controllore == i for k, ab in p.t.abilita_di(o) if ab.get("tipo") == "attivata"]
            mie += [(o, k) for o in p.t.giocatori[i].mano for k, ab in p.t.abilita_di(o)                # 113.6j, 113.6m, 702.29a: dalla mano
                    if ab.get("tipo") == "attivata" and ab.get("zona") == "mano"]
            if mie:
                if self.rng.random() < self.illegali:                                              # (le carte in mano solo se ne hanno:
                    dalla_mano = list(dict.fromkeys(o for o, _ in mie if o.zona == "mano"))            # senza, le partite restano le stesse)
                    o = self._uno(list(p.t.campo) + dalla_mano); return ("attiva", o, int(self.rng.integers(0, 3)))
                legali = [(o, k) for o, k in mie if p.puo_attivare(i, o, k)]
                if legali:
                    o, k = self._uno(legali)
                    return ("attiva", o, k)
        return super().agisci(p, i)

    def bersagli(self, p, i, oggetto, reqs, legali, fa=()):
        if self.rng.random() < self.illegali:
            tutti = list(p.t.campo) + [g.i for g in p.t.giocatori]
            return [[self._uno(tutti)] for _ in reqs]
        out = []
        for r, lst in zip(reqs, legali):
            idx = self.rng.permutation(len(lst))[:r.get("quanti", 1)]
            g_ = [lst[int(j)] for j in idx]
            if r.get("uno_per_tipo"):                                                              # (la scelta a caso, tenuta legale)
                tenuti = []
                for x in g_:
                    if uno_per_tipo(tenuti + [x]): tenuti.append(x)
                g_ = tenuti
            out.append(g_)
        return out

    def ordina(self, p, i, inneschi):
        return [inneschi[int(j)] for j in self.rng.permutation(len(inneschi))]

    def sceglie(self, p, i, d):
        return bool(self.rng.random() < 0.7)

    def lancia_in_risoluzione(self, p, i, ogg):
        """608.2g: X a caso, il pagamento lo trova il motore."""
        x = int(self.rng.integers(0, (p.x_massimo(i, ogg) or 0) + 1)) if "{X}" in (ogg.carta.car.get("costo") or "") else 0
        return (x, None)


def nuova(seme, mazzo=mazzo_effetti, decidi=None, P=Partita, T=TavoloEffetti):
    t = T([mazzo(), mazzo()], seme=seme)
    inizia(t, decidi=decidi)
    return P(t)


# ====================================================================== il conto a parte (la vigilanza)
def ricalcola(t):
    """Forza, costituzione e parole di ogni permanente rifatte a parte, con un altro algoritmo: le abilita' statiche di
    una fonte colpita da un «perde tutte le abilita'» non esistono (613.8, dipendenza; nel mazzo finto non ci sono
    rimozioni statiche), poi il livello 6 per timestamp, poi 7b per timestamp, 7c come somma, 7d per parita'."""
    spente = {n for c in t.continui if c.livello == "6" and c.dati.get("toglie") == "tutte" for n in (c.chi or ())}
    # le rimozioni statiche (un'aura che toglie tutte le abilita'): le loro fonti non sono a loro volta spente nelle carte coperte
    for x in t.campo:
        for ab in car_abilita(x, t):
            if ab.get("tipo") != "statica": continue
            for d in ab["effetti"]:
                if d["livello"] == "6" and d.get("toglie") == "tutte":
                    spente |= {o.n for o in t.campo if scelto(d.get("chi") or {}, o, x)}
    out = {}
    fonti = [(x, car_abilita(x, t) if x in t.campo else car_abilita(x))                             # una volta per fonte, non per
             for x in list(t.campo) + list(getattr(t, "emblemi", [])) if x.n not in spente]       # coppia (14 ott 2026: stesso conto)
    for o in t.campo:
        car, creatura = car_a_parte(t, o)
        evs = []
        for c in t.continui:
            if c.chi is not None and o.n in c.chi: evs.append((c.ts, c.livello, c.dati))
        for x, abil in fonti:                                                                      # anche gli emblemi (114.4)
            for ab in abil:
                if ab.get("tipo") != "statica": continue
                for d in ab["effetti"]:
                    if not vera_a_parte(t, d.get("se") or {}, x): continue                         # «as long as», rifatto a parte
                    if scelto(d.get("chi") or {}, o, x):                                          # (la quantita' «you control» e' di chi
                        conta_ = isinstance(d.get("p"), dict) or isinstance(d.get("t"), dict)      # controlla la fonte, 15 nov 2026)
                        evs.append((x.ts, d["livello"], dict(d, _ctrl=x.controllore) if conta_ else d))
        evs.sort(key=lambda e: e[0])
        ps = set(car.get("parole", ()))
        for _, liv, d in evs:
            if liv != "6": continue
            if d.get("toglie") == "tutte": ps = set()
            ps |= set(d.get("dai") or ())
        f, c = car.get("forza"), car.get("costituzione")
        if car.get("cda") == "tipi_cimiteri":                                                      # rifatto a parte: i tipi nei cimiteri
            tipi_ = set()
            for g in t.giocatori:
                for x in g.cimitero: tipi_ |= {w.lower() for w in x.carta.tipo.split("—")[0].split()} & TIPI_DI_CARTA
            f, c = len(tipi_), len(tipi_) + 1
        if isinstance(car.get("cda"), dict) and "controlli" in car["cda"]:                         # rifatto a parte: il conteggio
            sel_ = car["cda"]["controlli"]
            n_ = sum(1 for x in t.campo if x.controllore == o.controllore
                     and (not sel_.get("tipi") or set(sel_["tipi"]) & x.carta.tipi)
                     and (not sel_.get("sottotipo") or sel_["sottotipo"] in x.carta.tipo.split("—")[-1].split()))
            f = n_
            if car["cda"].get("anche_costituzione"): c = n_
        if car.get("cda") == "dominio":                                                            # rifatto a parte: i nomi delle terre base
            f = sum(1 for nome in ("Plains", "Island", "Swamp", "Mountain", "Forest")                # fra i sottotipi delle terre di chi la controlla
                    if any(x.controllore == o.controllore and "land" in x.carta.tipi and nome in x.carta.tipo.split("—")[-1].split() for x in t.campo))
        if creatura and f is None and any(liv == "7b" for _, liv, _ in evs): f, c = 0, 0          # 208.3, 613.6
        if creatura and f is not None:
            for _, liv, d in evs:
                if liv == "7b": f, c = d["p"], d["t"]
            f += sum(quanto_a_parte(t, d.get("p", 0), o, d.get("_ctrl")) for _, liv, d in evs if liv == "7c") + o.segnalini["+1/+1"] - o.segnalini["-1/-1"]
            c += sum(quanto_a_parte(t, d.get("t", 0), o, d.get("_ctrl")) for _, liv, d in evs if liv == "7c") + o.segnalini["+1/+1"] - o.segnalini["-1/-1"]
            if sum(1 for _, liv, _ in evs if liv == "7d") % 2: f, c = c, f
        out[o.n] = (f, c, frozenset(ps))
    return out


def quanto_a_parte(t, v, o, ctrl=None):
    """Le quantita' delle statiche che contano il cimitero, rifatte a parte (le statiche di questo genere sono sulla
    creatura stessa: «this creature gets +1/+0 for each ...»); dal 15 nov 2026 anche «for each Forest you control», contata
    per chi controlla la fonte (ctrl), coi tipi e il sottotipo letti dalla riga del tipo."""
    if not isinstance(v, dict): return v
    spec, cim = v["conta"], t.giocatori[o.controllore].cimitero
    if spec["tipo"] == "controlli":
        sel_, chi_ = spec["sel"], ctrl if ctrl is not None else o.controllore
        tipi_ = set(sel_.get("tipi") or ())
        n = sum(1 for x in t.campo if x.controllore == chi_
                and (not tipi_ or "permanent" in tipi_ or tipi_ & {w.lower() for w in x.carta.tipo.split("—")[0].split()})
                and (not sel_.get("sottotipo") or sel_["sottotipo"] in x.carta.tipo.split("—")[-1].split()))
        return v.get("molt", 1) * n
    if spec["tipo"] == "cimitero_tipi":
        n = len([x for x in cim if any(w.lower() in spec["tipi"] for w in x.carta.tipo.split("—")[0].split())])
    elif spec["tipo"] == "cimitero_ogni":
        n = 0
        while (n + 1) * spec["ogni"] <= len(cim): n += 1
    else: raise RuntimeError(f"vigilanza: la quantita' {spec} non si rifa'")
    return v.get("molt", 1) * n


def vera_a_parte(t, cond, x):
    """Le condizioni «as long as» rifatte senza il motore: il cimitero, i danni non da combattimento del turno.
    Senza condizioni e' vera subito (14 ott 2026: l'inizio del turno si cercava fra tutti gli eventi a ogni chiamata, ed
    era l'80% del tempo di una partita con l'arbitro acceso; il risultato non cambia)."""
    if not cond: return True
    inizio = max((j for j, e in enumerate(t.eventi) if e.tipo == "turno"), default=0)
    for k, v in cond.items():
        if k == "tuo_turno" and not (t.eventi[inizio:] and t.eventi[inizio].tipo == "turno" and t.eventi[inizio].giocatore == x.controllore): return False
        if k == "cimitero_almeno" and len(t.giocatori[x.controllore].cimitero) < v: return False
        if k == "controlli" and not [y for y in t.campo if y.controllore == x.controllore and "Planeswalker" in y.carta.tipo.split("—")[0]
                                     and v["sottotipo"] in y.carta.tipo.split("—")[-1].split()]: return False
        if k == "senza_danno_combattimento" and any(e.tipo == "danno" and e.causa == "510.2" and e.vecchio == x.n for e in t.eventi): return False
        if k not in ("tuo_turno", "cimitero_almeno", "avversario_danno_nc_turno", "controlli", "senza_danno_combattimento"):
            raise RuntimeError(f"vigilanza: la condizione {k!r} non si rifa'")
        if k == "avversario_danno_nc_turno" and not any(e.tipo == "danno" and e.nuovo is None and e.causa != "510.2"
                                                        and e.giocatore != x.controllore for e in t.eventi[inizio:]): return False
    return True


def car_a_parte(t, o):
    """I livelli 1 e 4 rifatti senza la vista del motore: la copia piu' recente fra gli effetti risolti che toccano o
    (707.2b: i valori presi quando e' nata), poi «creatura» se gli e' attaccata un'aura che lo rende creatura.
    -> (car, e' una creatura)."""
    copie = [c for c in getattr(t, "continui", []) if c.livello == "1" and c.chi is not None and o.n in c.chi]
    tipo, car = (max(copie, key=lambda c: c.ts).dati["copia"][1:]) if copie and o.vivo and o.zona == "campo" else (o.fisica.tipo, o.fisica.car)
    creatura = "creature" in {w.lower() for w in tipo.split("//")[0].split("—")[0].split()}
    for x in getattr(t, "campo", []):
        if getattr(x, "attaccato_a", None) != o.n: continue
        for ab in x.fisica.car.get("abilita") or ():
            if ab.get("tipo") == "statica" and any(d["livello"] == "4" and "creature" in (d.get("tipi") or ()) for d in ab["effetti"]):
                creatura = True
    return car, creatura


def nome_e_creatura_a_parte(t, o):
    """Il nome e l'essere una creatura dopo i livelli 1 e 4, rifatti a parte (la vigilanza li confronta con la vista)."""
    copie = [c for c in getattr(t, "continui", []) if c.livello == "1" and c.chi is not None and o.n in c.chi]
    nome = max(copie, key=lambda c: c.ts).dati["copia"][0] if copie and o.vivo and o.zona == "campo" else o.fisica.nome
    return nome, car_a_parte(t, o)[1]


def car_abilita(o, t=None):
    if t is not None: return car_a_parte(t, o)[0].get("abilita") or []
    return o.carta.car.get("abilita") or []


def permesso_a_parte(t, n, i):
    """601.3 e 611.2a rifatti dagli eventi, senza il motore: c'e' un permesso per la carta n dato a i, e da allora non e'
    cominciato nessun turno dopo il primo turno di i (cioe' il suo prossimo turno non e' finito)? Oppure (607.2a, 611.3a)
    la carta e' stata esiliata da un permanente che e' ancora in campo sotto i, stampato con «you may cast the exiled card»,
    e i ha almeno sette carte nel cimitero?"""
    x = t.oggetti.get(n)
    s = t.oggetti.get(getattr(x, "esiliata_da", None)) if x is not None else None
    if s is not None and s.vivo and s.zona == "campo" and s.controllore == i and len(t.giocatori[i].cimitero) >= 7 \
            and any(ab.get("tipo") == "lancia_collegata" for ab in s.fisica.car.get("abilita") or ()): return True
    for k, e in enumerate(t.eventi):
        if e.tipo == "permesso" and e.vecchio == n and e.giocatore == i:
            if e.a == "finche_in_esilio":                                                          # 611.2b: la carta n e' ancora la
                if not any(x.tipo == "zona" and x.vecchio == n for x in t.eventi[k + 1:]): return True   # stessa, in esilio (400.7)
                continue
            dopo = [x.giocatore for x in t.eventi[k + 1:] if x.tipo == "turno"]
            if i not in dopo or dopo.index(i) == len(dopo) - 1: return True
    return False


def vigila(P):
    """La vigilanza del passo 5 (tavolo sano, illegali senza effetto, tempi di lancio, mana) piu' i conti del passo 7
    rifatti a parte dopo ogni azione e ogni risoluzione: caratteristiche (ricalcola), bersagli legali quando si
    scelgono, inneschi tutti gestiti, APNAP, effetti di fine turno finiti, azioni di stato fatte."""
    base = PL.vigila(P)

    class Vigila(base):
        def _confronta(self, dove):
            atteso = ricalcola(self.t)
            for o in self.t.campo:
                v = self.t.caratteristiche(o)
                visto = (v["forza"], v["costituzione"], frozenset(v["parole"]))
                if atteso[o.n] != visto:
                    self._sbaglia(f"{dove}: {o} e' {visto[:2]} {sorted(visto[2])}, rifatto a parte {atteso[o.n][:2]} {sorted(atteso[o.n][2])} (613)")
                    return
                nc = nome_e_creatura_a_parte(self.t, o)
                if (o.nome, "creature" in o.carta.tipi) != nc:
                    self._sbaglia(f"{dove}: {o} e' {o.nome!r} creatura={'creature' in o.carta.tipi}, rifatto a parte {nc} (613.1a, 613.1d)")
                    return
                if nc[0] != o.fisica.nome: self.conti["controlli su una copia (707.2)"] += 1
                if nc[1] and "creature" not in o.fisica.tipi and o.fisica.nome == nc[0]: self.conti["controlli su un animato (613.1d)"] += 1

        def esegui(self, i, azione):
            dall_esilio = azione[0] in ("lancia", "terra") and getattr(azione[1], "zona", None) == "esilio" \
                and "copia_di" not in azione[1].carta.car and azione[1].vivo
            if dall_esilio: n_, ok_ = azione[1].n, permesso_a_parte(self.t, azione[1].n, i)
            ok = super().esegui(i, azione)
            if dall_esilio:
                self.conti[f"giocate dall'esilio ({'ok' if ok else 'rifiutate'})"] += 1
                if ok and not ok_: self._sbaglia(f"carta #{n_} giocata dall'esilio senza un permesso valido (601.3, 611.2a)")
            if ok:
                if azione[0] == "attiva": self.conti["abilita' attivate"] += 1
                if azione[0] == "lancia" and getattr(self.t.pila[-1] if self.t.pila else None, "bersagli", None):
                    self._bersagli_ok(self.t.pila[-1], i)
                self._confronta(f"dopo {azione[0]}")
            return ok

        def attiva(self, i, ogg, k, x=0, pagamento=None, bersagli=None):
            a = super().attiva(i, ogg, k, x, pagamento, bersagli)
            if a is not None and a.bersagli: self._bersagli_ok(a, i)
            if a is not None and "fedelta" in a.ab: self.conti["abilita' di fedelta'"] += 1
            return a

        def _bersagli_ok(self, oggetto, i):
            """115.3, 115.5, 702.11b, rifatti a parte: niente ripetuti, non se stesso, niente anti-malocchio avversario."""
            rifatte = ricalcola(self.t)
            for g in oggetto.bersagli:
                if len(set(map(lambda x: x if _e_giocatore(x) else ("o", x.n), g))) != len(g): self._sbaglia(f"{oggetto}: bersaglio ripetuto (115.3)")
                for x in g:
                    if x is oggetto: self._sbaglia(f"{oggetto} bersaglia se stesso (115.5)")
                    if not _e_giocatore(x) and x.vivo and x.zona == "campo" and "hexproof" in rifatte[x.n][2] and x.controllore != i:   # sacrificato come costo: non c'e' piu' (601.2h)
                        self._sbaglia(f"{oggetto} bersaglia {x} con anti-malocchio di un avversario (702.11b)")
            self.conti["scelte di bersagli"] += 1

        def _metti_innesco(self, inn):
            ok = super()._metti_innesco(inn)
            if ok and inn.abilita.bersagli: self._bersagli_ok(inn.abilita, inn.controllore)
            return ok

        def _metti_inneschi(self):
            super()._metti_inneschi()
            giro = self.messe_insieme[-1]
            ordine = self._apnap()
            if [ordine.index(j) for j in giro] != sorted(ordine.index(j) for j in giro):
                self._sbaglia(f"inneschi in pila fuori dall'ordine APNAP: {giro} (603.3b)")
            if len(set(giro)) > 1: self.conti["giri di inneschi di due giocatori"] += 1

        def risolvi(self):
            cima = self._cima()
            dove = super().risolvi()
            if isinstance(cima, Abilita): self.conti[f"abilita' risolte ({cima.esito})"] += 1
            self._confronta("dopo la risoluzione")
            return dove

        def finestra(self, giocatori):
            super().finestra(giocatori)
            if self.t.finita: return
            for o in self.t.campo:                                                                # 704.5f-g dopo la priorita'
                if "creature" in o.carta.tipi and "costituzione" in o.carta.car:
                    c = costituzione(o)
                    if c <= 0 or (o.danno >= c and "indestructible" not in parole(o)):
                        self._sbaglia(f"{o} in campo con costituzione {c} e {o.danno} danni (704.5f-g)")

    return Vigila


def pila_dagli_eventi(t):
    """La pila ricostruita dagli eventi, con le abilita': chi esce e' sempre la cima, salvo le contromagie (405.5,
    701.6a), e ogni passo comincia a pila vuota (500.2)."""
    pila, err, entrato, risolve = [], [], {}, {}
    for e in t.eventi:
        if e.tipo == "passo" and pila: err.append(f"evento {e.n}: il passo {e.da}/{e.a} comincia con {len(pila)} in pila (500.2)")
        if e.tipo == "risolve": risolve[e.vecchio] = e.n
        dentro = (e.tipo == "zona" and e.a == "pila") or (e.tipo == "abilita" and e.a == "pila")
        fuori = (e.tipo == "zona" and e.da == "pila") or (e.tipo == "abilita" and e.da == "pila")
        if dentro:
            x = e.nuovo if e.tipo == "zona" else e.vecchio
            pila.append(x); entrato[x] = e.n
        if fuori:
            chi = e.vecchio
            sopra = pila[pila.index(chi) + 1:] if chi in pila else None
            durante = sopra is not None and chi in risolve and all(entrato.get(x, -1) > risolve[chi] for x in sopra)   # 608.2n: messe in pila risolvendo
            if (not pila or pila[-1] != chi) and e.causa != "701.6a" and not durante: err.append(f"evento {e.n}: esce {e.carta} che non e' la cima (405.5)")
            if chi in pila: pila.remove(chi)
    return err[:3]


def a_caso(P, seme, T=TavoloEffetti, mazzo=mazzo_effetti, giocatori=None):
    t = T([mazzo(), mazzo()], seme=seme)
    inizia(t)
    p = vigila(P)(t)
    fine_turno = []
    def dopo(p):
        if any(c.durata == "fine_turno" for c in p.t.continui) and not p.t.finita:
            p._sbaglia("un effetto «fino a fine turno» e' sopravvissuto alla pulizia (514.2, 611.2a)")
        fine_turno.append(1)
    p.gioca(giocatori or {0: CasoEffetti(seme * 2 + 1), 1: CasoEffetti(seme * 2 + 2)}, dopo_ogni_turno=dopo)
    p.err += pila_dagli_eventi(t)
    for costo, pag, x, fonti, riserva in [(c.car["costo"], pg, x, f, r) for c, pg, x, f, r in p.pagati] + p.pagati_abilita:
        perche = M.valida(pag, costo, fonti, riserva, x)
        if perche: p._sbaglia(f"pagamento illegale: {perche}")
    speso = sum(sum(pg.spesa) for _, pg, _, _, _ in p.pagati) + sum(sum(pg.spesa) for _, pg, _, _, _ in p.pagati_abilita)
    if p.prodotto != speso + p.perso: p._sbaglia(f"mana prodotto {p.prodotto}, speso {speso}, perso {p.perso} (106.4)")
    sospesi = [x for x in p.diario_inneschi if x.esito is None]
    if sospesi and not t.finita: p._sbaglia(f"inneschi mai messi in pila: {sospesi[:2]} (603.3)")
    p.conti["inneschi"] += len(p.diario_inneschi)
    p.conti["inneschi tolti (603.3d)"] += sum(1 for x in p.diario_inneschi if x.esito == "603.3d")
    for e in t.eventi:
        if e.tipo == "zona" and e.causa in ("608.2b", "701.6a", "704.5f", "704.5q"): p.conti[f"zona {e.causa}"] += 1
        if e.tipo == "segnalini" and e.causa == "704.5q": p.conti["704.5q"] += 1
        if e.tipo == "fine effetti": p.conti["fine effetti"] += 1
    return p


# ====================================================================== le prove delle regole
class FaE(C.FaC):
    """Il giocatore di prova del passo 6 con bersagli, ordine degli inneschi e «puoi» dati da fuori."""

    def __init__(self, f=None, diario=None, attacca=None, blocca=None, assegna=None, scarta=None, bersagli=None,
                 ordina=None, sceglie=None):
        super().__init__(f, diario, attacca, blocca, assegna, scarta)
        self._ber, self._ord, self._sce = bersagli, ordina, sceglie

    def bersagli(self, p, i, oggetto, reqs, legali, fa=()):
        b = self._ber(p, i, oggetto, reqs, legali) if self._ber else None
        return b if b is not None else bersagli_semplici(p, i, oggetto, reqs, legali, fa)

    def ordina(self, p, i, inneschi):
        return self._ord(p, i, inneschi) if self._ord else inneschi

    def sceglie(self, p, i, d):
        return self._sce(p, i, d) if self._sce else True


def prove_regole(P, T=TavoloEffetti):
    casi = []
    def caso(nome, ok, det=""): casi.append((nome, bool(ok), det))
    def partita(seme=1):
        t = T([mazzo_prove(), mazzo_prove()], seme=seme)
        inizia(t, primo=0)
        for g in t.giocatori:
            for o in list(g.mano): t.sposta(o, "grimorio", posizione="fondo", causa="prova")
        return P(t)
    def dai(p, i, nome, campo=True, zitto=True):
        """Una carta di quel nome dal grimorio, in mano o in campo, per costruire la situazione (zitto: senza inneschi)."""
        o = next(o for o in p.t.giocatori[i].grimorio.carte if o.nome == nome)
        p.t._togli(o)
        o = p.t._arriva(o, "grimorio", "mano", None, None, "prova")
        if campo: o = p.t.metti_in_campo(o, chi=i, causa="prova")
        if zitto: p.in_attesa.clear()
        return o
    def eventi(p, tipo): return [e for e in p.t.eventi if e.tipo == tipo]
    def vite(p): return [g.vite for g in p.t.giocatori]
    def fc(o): return (forza(o), costituzione(o))
    def una_volta(fatto, chiave, azione):
        if chiave in fatto: return None
        fatto.add(chiave)
        return azione
    def gioca(p, f0=None, f1=None, **kw):
        g0 = {k[:-1]: v for k, v in kw.items() if k.endswith("0")}
        g1 = {k[:-1]: v for k, v in kw.items() if k.endswith("1")}
        p.turno({0: FaE(f0, **g0), 1: FaE(f1, **g1)})
        return p
    def effetto(p, ctrl, fa, bersagli=(), fonte=None):
        """Un effetto che si risolve adesso, come se lo facesse una magia di ctrl (per provare i livelli sui numeri
        degli esempi del regolamento)."""
        class Finta: pass
        m = Finta(); m.bersagli = [list(bersagli)] if bersagli else []
        reqs = [{"chi": ["creature"], "quanti": len(bersagli)}] if bersagli else []
        p._esegui(m, fa, reqs, ctrl, fonte or p.t.campo[0])
    def terre(p, i, n):
        for _ in range(n): dai(p, i, "Terra")

    # 602.2a, 113.1c, 405.1, 113.8, 608.2n, 117.3c: l'abilita' attivata
    p = partita(); terre(p, 0, 2); mu = dai(p, 0, "Mutante"); fatto = set(); d = []
    def attiva_mutante(p, i):
        if p.fase == "principale_1": return una_volta(fatto, "a", ("attiva", mu, 0))
    viste = []
    def guarda(p, i):
        if p.fase == "principale_1" and p.t.pila: viste.append((p.t.pila[-1].carta, p.t.pila[-1].controllore, type(p.t.pila[-1]).__name__))
    gioca(p, attiva_mutante, guarda, diario0=d, diario1=d)
    caso("602.2a, 113.1c, 405.1, 113.8: l'abilita' attivata va in pila come oggetto che non e' una carta, la controlla chi l'attiva",
         viste[:1] == [(None, 0, "Abilita")], str(viste))
    caso("608.2n, 122.1a: risolta, mette il segnalino +1/+1 (2/2) e smette di esistere: niente nel cimitero",
         fc(mu) == (2, 2) and not p.t.giocatori[0].cimitero and not p.t.pila, f"{fc(mu)}")
    seq = [(i, n) for _, f, _, i, n in d if f == "principale_1"]
    caso("117.3c: chi attiva tiene la priorita' (con l'abilita' in pila la riceve di nuovo lui)", seq[:2] == [(0, 0), (0, 1)], str(seq))

    # 602.5a: il {T} con la debolezza da evocazione
    p = partita(); can = dai(p, 0, "Cannone"); p.ha_priorita = 0; p.fase = "principale_1"
    p.inizio_turno[0] = 1; p.t.turno_numero = 1; can.controllo_dal = 1
    m1 = p.motivo_non_attiva(0, can, 0)
    can.controllo_dal = 0
    m2 = p.motivo_non_attiva(0, can, 0)
    caso("602.5a: il {T} di una creatura entrata in questo turno non si attiva; dal turno dopo si'",
         m1 and m1.startswith("602.5a") and m2 is None, f"{m1} / {m2}")

    # 113.7a: la fonte se ne va, l'abilita' resta
    p = partita(); can = dai(p, 0, "Cannone"); can.controllo_dal = -1; orso = dai(p, 1, "Orso"); terre(p, 1, 1)
    ful = dai(p, 1, "Fulmine", campo=False); fatto = set()
    def spara(p, i):
        if p.passo == "mantenimento": return una_volta(fatto, "a", ("attiva", can, 0, 0, None, [[1]]))
    def via_il_cannone(p, i):
        if p.passo == "mantenimento" and p.t.pila: return una_volta(fatto, "f", ("lancia", ful, 0, None, [[can]]))
    gioca(p, spara, via_il_cannone)
    caso("113.7a: il Cannone ucciso in risposta: la sua abilita' resta in pila e infligge lo stesso 1 danno",
         not can.vivo and vite(p) == [20, 19] and [e.carta.nome for e in eventi(p, "danno")] == ["Fulmine", "Cannone"],
         f"{vite(p)} {[e.carta.nome for e in eventi(p, 'danno')]}")

    # 606.3, 606.4, 606.6: la fedelta'
    p = partita(); eroe = dai(p, 0, "Eroe"); orso = dai(p, 1, "Orso"); fatto = set(); motivi = []
    def fedelta(p, i):
        if p.fase != "principale_1" or p.t.pila: return None
        if "piu" not in fatto: fatto.add("piu"); return ("attiva", eroe, 0)
        if "meno" not in fatto: fatto.add("meno"); motivi.append(p.motivo_non_attiva(0, eroe, 1)); return ("attiva", eroe, 1)
    gioca(p, fedelta)
    caso("606.4: +1 mette un segnalino fedelta' (3 -> 4) e l'effetto si risolve (+2 vite)",
         vite(p)[0] == 22 and eroe.segnalini["fedelta"] == 4, f"{vite(p)} {eroe.segnalini['fedelta']}")
    caso("606.3: una sola abilita' di fedelta' per permanente per turno", motivi[-1:] and str(motivi[-1]).startswith("606.3"), str(motivi))
    p = partita(); eroe = dai(p, 0, "Eroe"); eroe.segnalini["fedelta"] = 1; dai(p, 1, "Orso")
    p.ha_priorita, p.fase = 0, "principale_1"
    caso("606.6: -2 con un segnalino solo non si attiva", str(p.motivo_non_attiva(0, eroe, 1)).startswith("606.6"))
    p.fase = "combattimento"
    caso("606.3: fuori dalla fase principale nessuna abilita' di fedelta'", str(p.motivo_non_attiva(0, eroe, 0)).startswith("606.3"))

    # 603.2, 603.3, 603.3a: l'innesco d'entrata e i bersagli scelti mettendolo in pila
    p = partita(); terre(p, 0, 2); ara = dai(p, 0, "Araldo", campo=False); orso = dai(p, 0, "Orso"); fatto = set(); d = []
    def lancia_araldo(p, i):
        if p.fase == "principale_1": return una_volta(fatto, "a", ("lancia", ara, 0, None))
    dimensioni = []
    def misura(p, i):
        if p.fase == "principale_1": dimensioni.append((len(p.t.pila), fc(orso)))
    gioca(p, lancia_araldo, misura, diario0=d, diario1=d, bersagli0=lambda p, i, o, r, l: [[orso]])
    ins = [x for x in p.diario_inneschi if x.fonte.nome == "Araldo"]
    caso("603.2, 603.3, 603.3a: l'Araldo risolto si innesca, va in pila alla priorita' dopo, lo controlla chi controlla l'Araldo",
         len(ins) == 1 and ins[0].controllore == 0 and ins[0].esito == "pila", str(ins))
    caso("613.4c, 608.2c: risolto l'innesco, l'Orso bersagliato e' 4/4 fino alla fine del turno",
         (0, (4, 4)) in dimensioni, str(dimensioni))
    caso("514.2, 611.2a: alla pulizia l'effetto finisce, l'Orso torna 2/2", fc(orso) == (2, 2) and not p.t.continui, f"{fc(orso)}")

    # 603.3d: l'innesco senza bersagli legali si toglie
    p = partita(); terre(p, 0, 2); ara = dai(p, 0, "Araldo", campo=False); fatto = set()
    # l'unica creatura in campo sara' l'Araldo stesso: e' legale (non e' l'abilita'); per provare 603.3d gli si da' l'anti-malocchio
    # di un avversario: un Velo dell'avversario come unica creatura, e l'Araldo che entra... l'Araldo bersaglia anche se stesso.
    # Quindi: una richiesta che solo una creatura avversaria soddisfa.
    ara.carta.car = dict(ara.carta.car, abilita=[dict(ara.carta.car["abilita"][0], bersagli=[{"chi": ["creature"], "controllo": "avversario"}])])
    dai(p, 1, "Velo")
    gioca(p, lambda p, i: una_volta(fatto, "a", ("lancia", ara, 0, None)) if p.fase == "principale_1" else None)
    ins = [x for x in p.diario_inneschi if x.fonte.nome == "Araldo"]
    caso("603.3d, 702.11b: l'unica creatura avversaria ha l'anti-malocchio: l'innesco non ha bersagli e si toglie",
         len(ins) == 1 and ins[0].esito == "603.3d" and len(eventi(p, "rimossa")) == 1, str([(x, x.esito) for x in ins]))

    # 603.3b, 101.4: APNAP e l'ordine scelto
    p = partita(); terre(p, 0, 4); cat = dai(p, 0, "Cataclisma", campo=False)
    for i in (0, 1): dai(p, i, "Lascito"); dai(p, i, "Lascito")
    fatto = set(); ordine_risolte = []
    def guarda_pila(p, i):
        if p.fase == "principale_1" and len(p.t.pila) == 4 and not ordine_risolte:
            ordine_risolte.append([x.controllore for x in p.t.pila])
    gioca(p, lambda p, i: (guarda_pila(p, i), una_volta(fatto, "c", ("lancia", cat, 0, None)) if p.fase == "principale_1" else None)[1],
          guarda_pila)
    caso("603.3b, 101.4: quattro inneschi insieme, due per giocatore: in pila prima quelli dell'attivo, sopra quelli dell'altro",
         ordine_risolte == [[0, 0, 1, 1]], str(ordine_risolte))
    caso("603.6c: «quando muore» si innesca anche se e' la carta stessa a morire: ognuno pesca due carte",
         len(p.t.giocatori[0].mano) == 2 and len(p.t.giocatori[1].mano) == 2, f"{[len(g.mano) for g in p.t.giocatori]}")
    p = partita(); terre(p, 0, 4); cat = dai(p, 0, "Cataclisma", campo=False); a = dai(p, 0, "Lascito"); b = dai(p, 0, "Lutto")
    fatto = set(); in_pila = []
    def lancia_e_guarda(p, i):
        if p.fase == "principale_1" and len(p.t.pila) == 2 and not in_pila: in_pila.append([x.fonte.nome for x in p.t.pila])
        if p.fase == "principale_1": return una_volta(fatto, "c", ("lancia", cat, 0, None))
    gioca(p, lancia_e_guarda, ordina0=lambda p, i, l: sorted(l, key=lambda x: x.fonte.nome != "Lascito"))
    caso("603.3b: chi controlla due inneschi sceglie l'ordine (Lascito sotto, Lutto sopra)", in_pila == [["Lascito", "Lutto"]], str(in_pila))
    caso("603.10a: il Lutto, distrutto insieme al Lascito, si innesca lo stesso: guarda al campo di subito prima",
         vite(p)[0] == 21, str(vite(p)))

    # 603.6a: «whenever a creature enters» comprende quella che entra
    p = partita(); terre(p, 0, 2); cor = dai(p, 0, "Corvo", campo=False); fatto = set()
    gioca(p, lambda p, i: una_volta(fatto, "c", ("lancia", cor, 0, None)) if p.fase == "principale_1" else None)
    caso("603.6a: il Corvo vede anche se stesso entrare (+1 vita)", vite(p)[0] == 21, str(vite(p)))

    # 603.2b, 603.4: il mantenimento e il «se»
    p = partita(); cus = dai(p, 0, "Custode"); dai(p, 0, "Orso")
    p.turno({0: FaE(), 1: FaE()}); p.turno({0: FaE(), 1: FaE()})
    caso("603.2b: «at the beginning of your upkeep» si innesca nel proprio mantenimento, non in quello dell'altro",
         [x.evento.giocatore for x in p.diario_inneschi] == [0] and vite(p)[0] == 21, f"{[x.evento.giocatore for x in p.diario_inneschi]} {vite(p)}")
    p = partita(); cus = dai(p, 0, "Custode")
    p.turno({0: FaE(), 1: FaE()})
    caso("603.4: con una creatura sola il «se» e' falso e non si innesca nemmeno", not p.diario_inneschi and vite(p)[0] == 20)
    p = partita(); cus = dai(p, 0, "Custode"); orso = dai(p, 0, "Orso"); terre(p, 1, 1); ful = dai(p, 1, "Fulmine", campo=False)
    fatto = set()
    def uccidi_in_risposta(p, i):
        if p.passo == "mantenimento" and p.t.pila: return una_volta(fatto, "f", ("lancia", ful, 0, None, [[orso]]))
    gioca(p, None, uccidi_in_risposta)
    ab = [x.abilita for x in p.diario_inneschi if x.abilita]
    caso("603.4, 608.2a: se il «se» e' falso alla risoluzione l'abilita' si toglie senza effetto",
         ab and ab[0].esito == "608.2a" and vite(p)[0] == 20, f"{[a.esito for a in ab]} {vite(p)}")

    # 603.5: il «puoi» si sceglie alla risoluzione
    for scelta, attese in ((True, 1), (False, 0)):
        p = partita(); terre(p, 0, 2); tes = dai(p, 0, "Tesoriere", campo=False); fatto = set()
        gioca(p, lambda p, i: una_volta(fatto, "c", ("lancia", tes, 0, None)) if p.fase == "principale_1" else None,
              sceglie0=lambda p, i, d, s=scelta: s)
        caso(f"603.5: «you may draw»: l'innesco va in pila comunque e alla risoluzione chi lo controlla sceglie ({scelta})",
             len(p.diario_inneschi) == 1 and len(p.t.giocatori[0].mano) == attese, f"mano {len(p.t.giocatori[0].mano)}")

    # 508.1m: l'innesco d'attacco
    p = partita(); ved = dai(p, 0, "Vedetta"); ved.controllo_dal = -1
    gioca(p, attacca0=C.in_fila([ved]))
    caso("508.1m: «whenever this attacks» si innesca dichiarando gli attaccanti e si risolve nel passo degli attaccanti",
         vite(p) == [21, 18], str(vite(p)))

    # 115.2, 115.4: «any target»
    p = partita(); dai(p, 1, "Bastione"); orso = dai(p, 1, "Orso"); eroe = dai(p, 1, "Eroe")
    cand = p.candidati(QUALSIASI, 0, None, None)
    caso("115.4: «any target» e' creature, giocatori e planeswalker, non un incantesimo; 115.2: niente fuori dal campo",
         set(map(scrivi, cand)) == {"G1", "G2", repr(orso), repr(eroe)}, str(cand))
    # 702.11b: anti-malocchio
    p = partita(); vel = dai(p, 1, "Velo")
    caso("702.11b: l'anti-malocchio non lo bersaglia l'avversario, chi lo controlla si'",
         vel not in p.candidati(CREATURA, 0, None, None) and vel in p.candidati(CREATURA, 1, None, None))
    # 115.3: due bersagli diversi per una parola «target»
    p = partita(); terre(p, 0, 1); o1, o2 = dai(p, 0, "Orso"), dai(p, 0, "Orso"); dop = dai(p, 0, "Doppio", campo=False)
    p.ha_priorita, p.fase = 0, "principale_1"
    no = p.lancia(0, dop, 0, None, [[o1, o1]])
    si = p.lancia(0, dop, 0, None, [[o1, o2]])
    caso("115.3, 601.2c, 734.1: «two target creatures» con la stessa due volte non si lancia (e niente si muove); con due diverse si'",
         no is None and si is not None and si.bersagli == [[o1, o2]], f"{no} {si}")
    # 601.2c: senza bersagli legali non si lancia
    p = partita(); terre(p, 0, 1); cre = dai(p, 0, "Crescita", campo=False); p.ha_priorita, p.fase = 0, "principale_1"
    caso("601.2c: senza creature in campo un istantaneo «target creature» non si lancia", not p.puo_lanciare(0, cre))
    # 115.5 e la contromagia
    p = partita(); terre(p, 0, 4); con = dai(p, 0, "Contromagia", campo=False); orsoM = dai(p, 0, "Orso", campo=False)
    p.ha_priorita, p.fase = 0, "principale_1"
    caso("115.5, 115.2: a pila vuota la Contromagia non ha bersagli", not p.puo_lanciare(0, con))
    fatto = set()
    def contro(p, i):
        if p.fase != "principale_1": return None
        if not p.t.pila: return una_volta(fatto, "o", ("lancia", orsoM, 0, None))
        return una_volta(fatto, "c", ("lancia", con, 0, None, [[p.t.pila[-1]]]))
    gioca(p, contro)
    caso("701.6a: l'Orso contrastato va nel cimitero del proprietario senza entrare in campo",
         sorted(o.nome for o in p.t.giocatori[0].cimitero) == ["Contromagia", "Orso"] and not any(o.nome == "Orso" for o in p.t.campo))

    # 608.2b: tutti i bersagli illegali -> non si risolve, nessuna parte dell'effetto
    p = partita(); terre(p, 0, 1); orso = dai(p, 1, "Orso"); sete = dai(p, 0, "Sete", campo=False); terre(p, 1, 1)
    ful = dai(p, 1, "Fulmine", campo=False); fatto = set()
    def sete_su_orso(p, i):
        if p.fase == "principale_1": return una_volta(fatto, "s", ("lancia", sete, 0, None, [[orso]]))
    def uccidi_prima(p, i):
        if p.fase == "principale_1" and p.t.pila: return una_volta(fatto, "f", ("lancia", ful, 0, None, [[orso]]))
    gioca(p, sete_su_orso, uccidi_prima)
    caso("608.2b (esempio di Sorin's Thirst): il bersaglio muore in risposta: la Sete non si risolve e non si guadagnano le 2 vite",
         vite(p) == [20, 20] and any(e.causa == "608.2b" and e.carta.nome == "Sete" for e in eventi(p, "zona")), str(vite(p)))
    # 608.2b: uno dei due bersagli illegale -> l'altro subisce
    p = partita(); terre(p, 0, 1); o1, o2 = dai(p, 0, "Orso"), dai(p, 0, "Orso"); dop = dai(p, 0, "Doppio", campo=False)
    fatto = set(); dopo = []
    def doppio(p, i):
        if p.fase == "principale_1" and not p.t.pila: return una_volta(fatto, "d", ("lancia", dop, 0, None, [[o1, o2]]))
        if p.fase == "principale_1" and p.t.pila and "x" not in fatto: fatto.add("x"); p.t.rimbalza(o1)
        if p.fase == "principale_2" and not dopo: dopo.append(fc(o2))
    gioca(p, doppio)
    caso("608.2b: un bersaglio se ne va (400.7), l'altro e' ancora legale: la magia si risolve solo su quello",
         dopo == [(3, 3)], str(dopo))

    # 613.5 (esempio di Gray Ogre): 7c, 7c, 7c, 7b
    p = partita(); orso = dai(p, 0, "Orso")
    p.t.metti_segnalini(orso, "+1/+1", 1); a = fc(orso)
    effetto(p, 0, [{"fa": "pompa", "chi": "bersaglio", "p": 4, "t": 4, "durata": "fine_turno"}], [orso]); b = fc(orso)
    dai(p, 0, "Bastione"); c = fc(orso)
    effetto(p, 0, [{"fa": "base", "chi": "bersaglio", "p": 0, "t": 1, "durata": "fine_turno"}], [orso]); d_ = fc(orso)
    caso("613.5 (esempio di Gray Ogre): segnalino 3/3, +4/+4 7/7, +0/+2 statico 7/9, «diventa 0/1» (7b) 5/8",
         [a, b, c, d_] == [(3, 3), (7, 7), (7, 9), (5, 8)], str([a, b, c, d_]))
    # 613.4d: gli esempi dello scambio
    p = partita(); orso = dai(p, 0, "Orso")
    effetto(p, 0, [{"fa": "base", "chi": "bersaglio", "p": 1, "t": 3}], [orso])
    piu = effetto(p, 0, [{"fa": "pompa", "chi": "bersaglio", "p": 0, "t": 1}], [orso]); piu = p.t.continui[-1]
    effetto(p, 0, [{"fa": "scambia", "chi": "bersaglio"}], [orso]); a = fc(orso)
    effetto(p, 0, [{"fa": "pompa", "chi": "bersaglio", "p": 5, "t": 0}], [orso]); b = fc(orso)
    cinque = p.t.continui[-1]
    p.t.continui.remove(cinque); p.t.continui.remove(piu); p.t._versione += 1; c = fc(orso)
    effetto(p, 0, [{"fa": "pompa", "chi": "bersaglio", "p": 0, "t": 1}], [orso])
    effetto(p, 0, [{"fa": "scambia", "chi": "bersaglio"}], [orso]); d_ = fc(orso)
    caso("613.4d (gli esempi): 1/3 +0/+1 scambiata 4/1; +5/+0 4/6; finito il +0/+1 3/1; due scambi si annullano 1/4",
         [a, b, c, d_] == [(4, 1), (4, 6), (3, 1), (1, 4)], str([a, b, c, d_]))
    # 613.1f, 613.7: perdere tutte le abilita' e prendere volare, nei due ordini
    p = partita(); o1, o2 = dai(p, 0, "Orso"), dai(p, 0, "Orso")
    effetto(p, 0, [{"fa": "togli_abilita", "chi": "bersaglio"}], [o1]); effetto(p, 0, [{"fa": "dai_parole", "chi": "bersaglio", "parole": ["flying"]}], [o1])
    effetto(p, 0, [{"fa": "dai_parole", "chi": "bersaglio", "parole": ["flying"]}], [o2]); effetto(p, 0, [{"fa": "togli_abilita", "chi": "bersaglio"}], [o2])
    caso("613.1f, 613.7: perde tutto e poi prende volare: vola; prende volare e poi perde tutto: non vola",
         parole(o1) == {"flying"} and parole(o2) == set(), f"{parole(o1)} {parole(o2)}")
    # 613.8: la dipendenza
    p = partita(); capo = dai(p, 0, "Capobranco"); orso = dai(p, 0, "Orso")
    prima = parole(orso)
    effetto(p, 1, [{"fa": "togli_abilita", "chi": "bersaglio", "durata": "fine_turno"}], [capo])
    caso("613.8a-b: il Capobranco perde le abilita' dopo: il suo «le altre tue creature volano» dipende da quell'effetto, "
         "che si applica prima anche se e' piu' recente: l'Orso non vola piu'", prima == {"flying"} and parole(orso) == set(),
         f"{prima} -> {parole(orso)}")
    # 604.2, 613.1f-g: lo statico di forza di una fonte senza abilita'
    p = partita(); sig = dai(p, 0, "Signore"); orso = dai(p, 0, "Orso"); a = fc(orso)
    effetto(p, 1, [{"fa": "togli_abilita", "chi": "bersaglio"}], [sig])
    caso("604.2, 613.1f-g: il Signore da' +1/+1 alle altre (Orso 3/3, non a se stesso); senza abilita' l'Orso torna 2/2",
         a == (3, 3) and fc(sig) == (2, 2) and fc(orso) == (2, 2), f"{a} {fc(orso)}")
    # 611.2c contro 611.3a
    p = partita(); terre(p, 0, 4); rad = dai(p, 0, "Raduno", campo=False); orso = dai(p, 0, "Orso"); dopo = dai(p, 0, "Orso", campo=False)
    fatto = set(); misure = []
    def raduno(p, i):
        if p.fase != "principale_1": return None
        if "r" not in fatto: fatto.add("r"); return ("lancia", rad, 0, None)
        if not p.t.pila and "o" not in fatto: fatto.add("o"); return ("lancia", dopo, 0, None)
        if not p.t.pila and not misure: misure.append([fc(o) for o in p.t.campo if o.nome == "Orso"])
    gioca(p, raduno)
    caso("611.2c: il +1/+1 del Raduno vale per le creature in campo quando si risolve, non per l'Orso lanciato dopo",
         misure == [[(3, 3), (2, 2)]], str(misure))
    p = partita(); sig = dai(p, 0, "Signore"); nuovo = dai(p, 0, "Orso")
    caso("611.3a, 611.3c: lo statico del Signore vale anche per la creatura che entra dopo", fc(nuovo) == (3, 3), str(fc(nuovo)))
    # 400.7: l'effetto non segue la carta in un'altra zona
    p = partita(); orso = dai(p, 0, "Orso")
    effetto(p, 0, [{"fa": "pompa", "chi": "bersaglio", "p": 3, "t": 3, "durata": "fine_turno"}], [orso])
    di_nuovo = p.t.metti_in_campo(p.t.rimbalza(orso), chi=0)
    caso("400.7: l'Orso pompato, rimbalzato e rigiocato e' un oggetto nuovo: 2/2", fc(di_nuovo) == (2, 2), str(fc(di_nuovo)))
    # 704.5q, 122.3, 704.5f
    p = partita(); orso = dai(p, 0, "Orso"); p.t.metti_segnalini(orso, "+1/+1", 2); p.t.metti_segnalini(orso, "-1/-1", 3)
    p.priorita()
    caso("704.5q, 122.3: due +1/+1 e tre -1/-1: se ne tolgono due di ognuno, resta un -1/-1 (1/1)",
         orso.segnalini["+1/+1"] == 0 and orso.segnalini["-1/-1"] == 1 and fc(orso) == (1, 1), f"{dict(orso.segnalini)} {fc(orso)}")
    p = partita(); terre(p, 1, 1); las = dai(p, 0, "Lascito"); avv = dai(p, 1, "Avvizzire", campo=False); fatto = set()
    gioca(p, None, lambda p, i: una_volta(fatto, "a", ("lancia", avv, 0, None, [[las]])) if p.passo == "mantenimento" else None)
    caso("122.1a, 704.5f: un -1/-1 su una 1/1: costituzione 0, va nel cimitero (e il Lascito fa pescare)",
         not las.vivo and any(e.causa == "704.5f" for e in eventi(p, "zona")) and len(p.t.giocatori[0].mano) == 1)
    # 514.2 insieme: il danno e la fine del +3/+3
    p = partita(); terre(p, 0, 1); orso = dai(p, 0, "Orso"); cre = dai(p, 0, "Crescita", campo=False); fatto = set()
    def pompa_e_ferisci(p, i):
        if p.fase == "principale_1": return una_volta(fatto, "c", ("lancia", cre, 0, None, [[orso]]))
        if p.fase == "principale_2" and "d" not in fatto: fatto.add("d"); orso.danno = 4
    gioca(p, pompa_e_ferisci)
    caso("514.2: con 4 danni e +3/+3 l'Orso sopravvive alla pulizia: il danno si toglie insieme alla fine dell'effetto",
         orso.vivo and fc(orso) == (2, 2) and orso.danno == 0, f"{orso.vivo} {fc(orso)}")
    # 514.3a: un innesco nella pulizia
    p = partita(); las = dai(p, 0, "Lascito"); p.t.metti_segnalini(las, "-1/-1", 1)
    effetto(p, 0, [{"fa": "pompa", "chi": "bersaglio", "p": 1, "t": 1, "durata": "fine_turno"}], [las])
    d = []
    p.turno({0: FaE(diario=d), 1: FaE(diario=d)})
    caso("514.3a: alla pulizia finisce il +1/+1, il Lascito muore, l'innesco va in pila e l'attivo riceve la priorita' nella pulizia",
         not las.vivo and [(s, i) for _, _, s, i, _ in d if s == "pulizia"][:1] == [("pulizia", 0)]
         and len(p.t.giocatori[0].mano) == 1, str([x for x in d if x[2] == "pulizia"]))
    # 702.12b: distruggi e l'indistruttibile
    p = partita(); orso = dai(p, 0, "Orso"); effetto(p, 0, [{"fa": "dai_parole", "chi": "bersaglio", "parole": ["indestructible"], "durata": "fine_turno"}], [orso])
    effetto(p, 1, [{"fa": "distruggi", "chi": {"tipi": ["creature"]}}])
    caso("702.12b: un'indistruttibile data da un effetto (613.1f) resiste a «distruggi»", orso.vivo)
    # le parole chiave del passo 6 coi livelli: volare dato da un effetto si blocca solo con volare o portata
    p = partita(); capo = dai(p, 0, "Capobranco"); orso = dai(p, 0, "Orso"); orso.controllo_dal = -1; suo = dai(p, 1, "Orso")
    gioca(p, attacca0=C.in_fila([orso]), blocca1=C.in_fila(lambda p, i: {suo: orso}))
    caso("702.9b coi livelli (613.1f): l'Orso che vola grazie al Capobranco non lo blocca un Orso senza volare ne' portata",
         any(e.causa.startswith("702.9b") for e in eventi(p, "illegale")) and vite(p) == [20, 18], str(vite(p)))
    # i buchi dichiarati
    p = partita(); orso = dai(p, 0, "Orso")
    try: effetto(p, 0, [{"fa": "pompa", "chi": "bersaglio", "p": 1, "t": 1, "durata": "finche_controlli"}], [orso]); esito = "nessun errore"
    except NonCoperto as e: esito = str(e)
    caso("611.2b: una durata non coperta esce NonCoperto", esito.startswith("611.2b"), esito)
    try: effetto(p, 0, [{"fa": "trasforma", "chi": "bersaglio"}], [orso]); esito = "nessun errore"
    except NonCoperto as e: esito = str(e)
    caso("608.2c: un'istruzione che il motore non conosce esce NonCoperto", esito.startswith("608.2c"), esito)
    return casi


# ====================================================================== le prove
def regole_citate():
    """I numeri di regola citati in questo file e nei moduli del motore che usa: ognuno deve esistere nel regolamento."""
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "Motore_Opzioni"))
    import regolamento as R
    testo = open(os.path.abspath(__file__), encoding="utf-8").read()
    numeri = set(re.findall(r"(?<![\d.])(\d{3}\.\d+[a-z]?)(?![\d])", testo))
    numeri = {n for n in numeri if 100 <= int(n.split(".")[0]) <= 999}
    return sorted(n for n in numeri if R.regola(n) is None), len(numeri)


def prova():
    casi = []
    def caso(nome, ok, det=""): casi.append((nome, bool(ok), det))
    mancano, quanti = regole_citate()
    caso("ogni numero di regola citato in effetti.py esiste nel regolamento", not mancano, f"{quanti} numeri; mancano {mancano}")
    m = mazzo_effetti()
    caso("il mazzo finto del passo 7: 40 carte, 17 terre, 23 con abilita' o effetti", len(m) == 40 and sum(1 for v in m if v[0] == "Terra") == 17)
    for nome, ok, det in prove_regole(Partita): caso(nome, ok, det)

    # senza effetti il passo 7 gioca la stessa partita del passo 6, evento per evento
    diverse = []
    for s in range(20):
        a = C.nuova(s); a.gioca({0: C.CasoCombatte(s * 2 + 1), 1: C.CasoCombatte(s * 2 + 2)})
        b = nuova(s, mazzo=C.mazzo_combattimento); b.gioca({0: C.CasoCombatte(s * 2 + 1), 1: C.CasoCombatte(s * 2 + 2)})
        if [e.chiave() for e in a.t.eventi] != [e.chiave() for e in b.t.eventi] or a.t.stato() != b.t.stato(): diverse.append(s)
    caso("senza effetti il passo 7 gioca la stessa partita del passo 6: 20 partite a caso col combattimento, stessi eventi",
         not diverse, f"semi diversi: {diverse}")

    # le partite fra due GiocaEffetti e le partite a caso
    fini, err = Counter(), []
    for s in range(10):
        p = a_caso(Partita, s, giocatori={0: GiocaEffetti(), 1: GiocaEffetti()})
        err += [f"seme {s}: {e}" for e in p.err]
        fini[p.t.giocatori[1 - p.t.vincitore].perche if p.t.vincitore is not None else "pari"] += 1
    caso("10 partite fra due GiocaEffetti: tavolo sano, conti rifatti a parte, finiscono", not err and sum(fini.values()) == 10,
         "; ".join(err[:2]) or str(dict(fini)))
    tot, err = Counter(), []
    for s in range(40):
        p = a_caso(Partita, s)
        tot += p.conti
        err += [f"seme {s}: {e}" for e in p.err]
    minimi = {"abilita' attivate": 100, "abilita' di fedelta'": 10, "inneschi": 100, "scelte di bersagli": 200,
              "giri di inneschi di due giocatori": 2, "abilita' risolte (608.2n)": 100, "abilita' risolte (608.2b)": 3,
              "zona 608.2b": 3, "zona 701.6a": 3, "704.5q": 1, "fine effetti": 30, "illegali": 100}
    scarsi = {k: tot[k] for k, v in minimi.items() if tot[k] < v}
    caso("40 partite a caso con abilita', inneschi, bersagli ed effetti: ogni conto rifatto a parte, senza errori, coprendo le regole",
         not err and not scarsi, "; ".join(err[:2]) or (f"troppo pochi: {scarsi}" if scarsi else str({k: tot[k] for k in minimi})))
    err = [f"seme {s}: {e}" for s in range(15) for e in a_caso(Partita, s, mazzo=mazzo_dipendenze).err]
    caso("15 partite a caso col mazzo delle dipendenze (4 Capobranco, 4 Ammutolire): nessun errore", not err, "; ".join(err[:2]))
    a, b = a_caso(Partita, 3), a_caso(Partita, 3)
    caso("stesso seme, stessa partita (anche con gli effetti)", [e.chiave() for e in a.t.eventi] == [e.chiave() for e in b.t.eventi])

    # le prove negative: motori rotti apposta, la regola giusta deve risultare rossa
    class SenzaDipendenze(TavoloEffetti):
        def _dipende(self, e, r): return False
    class SetteCPrima(TavoloEffetti):
        def _livello_7(self, o, f, c, miei):
            for e in miei:
                if e.livello == "7c": f, c = f + e.dati.get("p", 0), c + e.dati.get("t", 0)
            f += o.segnalini["+1/+1"] - o.segnalini["-1/-1"]; c += o.segnalini["+1/+1"] - o.segnalini["-1/-1"]
            for e in miei:
                if e.livello == "7b": f, c = e.dati["p"], e.dati["t"]
            return f, c
    class MaiFine(TavoloEffetti):
        def fine_turno(self): pass
    class SenzaAnnullare(TavoloEffetti):
        def _stato_altre(self): return []
    class NonFissato(Partita):
        def _insieme_fissato(self, d, oggetti): return None if isinstance(d.get("chi"), dict) else frozenset(o.n for o in oggetti)
    class SenzaAPNAP(Partita):
        def _apnap(self): return list(reversed(super()._apnap()))
    class SenzaIndietro(Partita):
        def _guarda_indietro(self, e): return False
    class SenzaRicontrollo(Partita):
        def _ancora_legale(self, oggetto, r, x, ctrl, fonte): return True
    class SenzaHexproof(Partita):
        def _hexproof_conta(self): return False
    class SeSoloAllInnesco(Partita):
        def _se_alla_risoluzione(self): return False
    class FedeltaLibera(Partita):
        def _fedelta_una_volta(self): return False
    class TapLibero(Partita):
        def _tap_debole_conta(self): return False
    class LegataAllaFonte(Partita):
        def _abilita_indipendente(self): return False
    for nome, P, T, cerca in (("dipendenze ignorate", Partita, SenzaDipendenze, "613.8"),
                              ("7c prima di 7b", Partita, SetteCPrima, "Gray Ogre"),
                              ("«fino a fine turno» che non finisce", Partita, MaiFine, "611.2a"),
                              ("+1/+1 e -1/-1 che non si annullano", Partita, SenzaAnnullare, "704.5q"),
                              ("insieme non fissato", NonFissato, TavoloEffetti, "611.2c"),
                              ("inneschi non in ordine APNAP", SenzaAPNAP, TavoloEffetti, "603.3b, 101.4"),
                              ("niente sguardo all'indietro", SenzaIndietro, TavoloEffetti, "603.10a"),
                              ("bersagli non ricontrollati", SenzaRicontrollo, TavoloEffetti, "Sorin's Thirst"),
                              ("anti-malocchio ignorato", SenzaHexproof, TavoloEffetti, "702.11b"),
                              ("il «se» solo all'innesco", SeSoloAllInnesco, TavoloEffetti, "608.2a"),
                              ("fedelta' piu' volte per turno", FedeltaLibera, TavoloEffetti, "una sola abilita'"),
                              ("{T} con la debolezza da evocazione", TapLibero, TavoloEffetti, "602.5a"),
                              ("abilita' legata alla fonte", LegataAllaFonte, TavoloEffetti, "113.7a")):
        try: rosse = [n for n, ok, _ in prove_regole(P, T) if not ok]
        except Exception as e: rosse = [f"si rompe: {type(e).__name__}: {e} ({cerca})"]
        caso(f"prova negativa: {nome} risulta rosso", any(cerca in n for n in rosse), "; ".join(r[:70] for r in rosse[:3]) or "nessuna regola rossa")
    for nome, P, T, cerca, mazzo in (("dipendenze ignorate", Partita, SenzaDipendenze, "613", mazzo_dipendenze),
                                     ("«fino a fine turno» che non finisce", Partita, MaiFine, "514.2", mazzo_effetti),
                                     ("anti-malocchio ignorato", SenzaHexproof, TavoloEffetti, "702.11b", mazzo_effetti)):
        err = [e for s in range(8) for e in a_caso(P, s, T=T, mazzo=mazzo).err]
        caso(f"prova negativa sulle partite a caso: {nome} la trova la vigilanza", any(cerca in e for e in err), "; ".join(err[:1]))

    for nome, ok, det in casi:
        print(f"  {'ok   ' if ok else 'ROSSO'} {nome}" + (f"  [{det}]" if det else ""))
    print(f"{sum(ok for _, ok, _ in casi)}/{len(casi)}")
    return 0 if all(ok for _, ok, _ in casi) else 1


def racconta(seme=1):
    t = TavoloEffetti([mazzo_effetti(), mazzo_effetti()], seme=seme)
    inizia(t)
    p = vigila(Partita)(t)
    print(f"seme {seme}: comincia G{t.primo + 1}")
    visti = [0]
    def riga(p):
        nuovi = p.t.eventi[visti[0]:]; visti[0] = len(p.t.eventi)
        conta = Counter(e.tipo for e in nuovi)
        print(f"  T{p.t.turno_numero:>2} G{p.ultimo + 1}: lanciate {conta['lanciata']}, attivate {conta['attivata']}, "
              f"abilita' in pila {sum(1 for e in nuovi if e.tipo == 'abilita' and e.a == 'pila')}, attacchi {conta['attacca']}, "
              f"vite {p.t.giocatori[0].vite}-{p.t.giocatori[1].vite}")
    p.gioca({0: GiocaEffetti(), 1: GiocaEffetti()}, dopo_ogni_turno=riga)
    print(f"fine al turno {t.turno_numero}: " + (f"vince G{t.vincitore + 1}" if t.vincitore is not None else "pari")
          + (f"; ERRORI: {p.err}" if p.err else ""))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if "--prova" in sys.argv: sys.exit(prova())
    if "--partita" in sys.argv:
        k = sys.argv.index("--partita")
        racconta(int(sys.argv[k + 1]) if len(sys.argv) > k + 1 else 1)
    else: print(__doc__)
