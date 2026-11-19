"""Il combattimento: il passo 6 del motore di partita (14 ott 2026). Attaccanti, bloccanti, danno, le parole chiave.

Secondo il regolamento ufficiale (Regole/MagicCompRules.txt, numeri letti con Motore_Opzioni/regolamento.py):
  - la fase di combattimento ha cinque passi: inizio, dichiarazione degli attaccanti, dei bloccanti, danno, fine (506.1).
    Attacca il giocatore attivo; in due difende l'altro, che puo' essere attaccato lui o un suo planeswalker (506.2).
    Attacca e blocca solo una creatura (506.3). Senza attaccanti dichiarati si saltano bloccanti e danno (508.8);
  - gli attaccanti (508.1, 703.4i): azione del turno, senza pila, prima della priorita'. Il giocatore attivo sceglie le
    sue creature stappate, non battaglie, con rapidita' o sotto di lui dall'inizio del turno (508.1a, 302.6, 702.10b);
    se il difensore ha planeswalker dice chi attacca ognuna (508.1b); le restrizioni (508.1c): il difensore non attacca
    (702.3b). Le creature si tappano, e non e' un costo (508.1f), tranne quelle con cautela (702.20b); poi diventano
    attaccanti (508.1k). Una dichiarazione illegale torna indietro tutta e si dichiara di nuovo (508.1, 734);
  - i bloccanti (509.1, 703.4j): il difensore sceglie le sue creature stappate, non battaglie, e per ognuna una creatura
    che lo attacca (509.1a). Le restrizioni (509.1b): il volare lo bloccano solo volare e portata (702.9b, 702.17b), la
    minaccia solo due creature o piu' (702.111b). Un attaccante con bloccanti e' bloccato, e lo resta anche se i
    bloccanti spariscono (509.1h);
  - il danno (510): prima l'attivo, poi il difensore dicono come assegnano il danno di ogni loro creatura (510.1,
    703.4k): tanto quanto la forza, niente con forza 0 o meno (510.1a); il non bloccato a chi attacca (510.1b); il
    bloccato ai suoi bloccanti, diviso come vuole chi lo controlla, niente se non ne ha piu' (510.1c); il bloccante a chi
    blocca (510.1d). Si controlla l'assegnazione tutta insieme e se e' illegale si rifa' (510.1e). Poi tutto il danno
    arriva insieme (510.2) e l'attivo riceve la priorita' (510.3), dopo le azioni di stato (117.5);
  - travolgere (702.19b): l'attaccante assegna prima il letale a tutti i bloccanti (contando il danno gia' segnato e
    quello che le altre creature assegnano nello stesso passo), poi il resto anche a chi attacca; bloccato senza piu'
    bloccanti, tutto a chi attacca (702.19d); se attacca un planeswalker il resto va al planeswalker, mai al giocatore
    (702.19f); bloccando non fa niente (702.19a). Con il tocco mortale un danno qualsiasi e' letale (702.2c);
  - primo colpo e doppio colpo (510.4, 702.7b, 702.4b): se all'inizio del passo di danno una creatura in combattimento
    li ha, in quel passo colpiscono solo loro, e segue un secondo passo di danno con chi non li aveva all'inizio del
    primo e chi ha doppio colpo adesso;
  - il danno lo fa il tavolo (120: Motore_Partita/tavolo.py, `infliggi`): vite, fedelta' (120.3c, 306.8), danno segnato,
    tocco mortale (702.2b) e legame vitale (702.15b); le azioni di stato: danno letale (704.5g), tocco mortale (704.5h),
    l'indistruttibile che le ignora (702.12b);
  - chi lascia il campo, cambia controllore o smette di essere una creatura esce dal combattimento (506.4); se il
    planeswalker attaccato esce, l'attaccante resta ma non attacca nessuno e, non bloccato, non infligge danno (506.4c);
  - finito il passo di fine combattimento nessuno attacca, blocca o e' attaccato piu' (511.3).
Nei passi di inizio, attaccanti, bloccanti, danno e fine la priorita' gira come negli altri (507.2, 508.2, 509.2, 510.3,
511.1): si risponde con gli istantanei del passo 5.

Non coperto, ed esce NonCoperto o non esiste nelle carte finte: le parole chiave fuori da tavolo.PAROLE (infetto,
avvizzire, tossico, protezione: 120.3, 615), le battaglie (310), il multigiocatore (506.2a), i requisiti e le
restrizioni scritti sulle carte (508.1c-d, 509.1b-c: «attacca se puo'», «non puo' bloccare»), i costi per attaccare o
bloccare (508.1g-j, 509.1d-f), le creature messe in campo attaccanti o bloccanti (508.4, 509.4), le creature che
bloccano piu' attaccanti, gli inneschi «quando attacca/blocca» (508.1m, 509.1i, 510.3a), le prevenzioni del danno (615):
tutte vengono dal testo delle carte, cioe' dal passo 7.

Le scelte le fa un giocatore finto: `attacca(p, i)` -> lista di creature (attaccano il giocatore) o {creatura: bersaglio}
(l'indice del giocatore o un planeswalker), `blocca(p, i)` -> {bloccante: attaccante}, `assegna(p, i, compiti)` ->
{creatura: {destinatario: danni}} per le creature che hanno una scelta. Chi non ha il metodo non attacca, non blocca e
assegna con `assegnazione_semplice` (una scelta da giocatore, non una regola).

    py -I -X utf8 Motore_Partita/combattimento.py --prova
    py -I -X utf8 Motore_Partita/combattimento.py --partita [seme]     una partita fra due giocatori che attaccano
"""
import numbers
import os
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # py -I non mette la cartella dello script nel percorso
import pila as PL
from inizio import inizia
from mana import NonCoperto
from tavolo import PAROLE, Tavolo, controlla, costituzione, forza, parole

# il mazzo finto del passo 6: 17 terre generiche e 23 carte, le creature con forza, costituzione e una parola chiave
# (Autore, 14 ott 2026: niente carte vere fino al passo 7). Costi generici, pagati dalle terre {C}.
def _cr(nome, costo, f, c, *ps):
    return (nome, "Creature", {"costo": costo, "forza": f, "costituzione": c, "parole": list(ps)})


COMPOSIZIONE_COMBATTIMENTO = (
    (("Terra", "Land", {"mana": ["{C}"]}), 17),
    (_cr("Creatura", "{1}", 1, 1), 2),
    (_cr("Orso", "{2}", 2, 2), 2),
    (_cr("Volante", "{2}", 2, 2, "flying"), 2),
    (_cr("Portata", "{2}", 1, 3, "reach"), 1),
    (_cr("Primo colpo", "{2}", 2, 1, "first strike"), 1),
    (_cr("Doppio colpo", "{3}", 2, 2, "double strike"), 1),
    (_cr("Travolgere", "{3}", 3, 3, "trample"), 2),
    (_cr("Tocco mortale", "{2}", 1, 1, "deathtouch"), 1),
    (_cr("Travolgere tocco", "{3}", 2, 2, "trample", "deathtouch"), 1),
    (_cr("Legame vitale", "{2}", 2, 2, "lifelink"), 1),
    (_cr("Minaccia", "{2}", 2, 2, "menace"), 1),
    (_cr("Cautela", "{2}", 2, 2, "vigilance"), 1),
    (_cr("Rapida", "{2}", 2, 1, "haste"), 1),
    (_cr("Difensore", "{1}", 0, 4, "defender"), 1),
    (_cr("Indistruttibile", "{3}", 1, 1, "indestructible"), 1),
    (("Planeswalker", "Planeswalker", {"costo": "{2}", "fedelta": 3}), 1),
    (("Istantaneo", "Instant", {"costo": "{1}"}), 3))


def mazzo_combattimento():
    mazzo = []
    for voce, copie in COMPOSIZIONE_COMBATTIMENTO: mazzo += [voce] * copie
    return mazzo


def _e_giocatore(b):
    return isinstance(b, numbers.Integral) and not isinstance(b, bool)


def scrivi(b):
    return "nessuno" if b is None else f"G{b + 1}" if _e_giocatore(b) else repr(b)


# ====================================================================== l'assegnazione di chi non sceglie
def assegnazione_semplice(p, i, compiti):
    """Per ogni creatura con una scelta: il letale a ogni creatura che riceve, nell'ordine dato; il resto a chi attacca,
    se travolge, o all'ultima creatura. E' la scelta di un giocatore finto, non una regola: 510.1c lascia dividere come
    si vuole."""
    fatto = {k: dict(v) for k, v in p.assegnazione_forzata.items()}
    for c in compiti:
        o, resto, d = c["creatura"], c["forza"], {}
        fatto[o] = d
        for x in c["creature"]:
            if resto <= 0: break
            n = min(resto, p.letale(x, o, fatto))
            if n > 0: d[x], resto = n, resto - n
        if resto > 0:
            dove = c["bersaglio"] if c["bersaglio"] is not None else c["creature"][-1]
            d[dove] = d.get(dove, 0) + resto
    return {c["creatura"]: fatto[c["creatura"]] for c in compiti}


# ====================================================================== i giocatori finti
class Combatte(PL.GiocaSubito):
    """Le mosse di GiocaSubito, poi attacca con tutto quello che puo' attaccare (il giocatore, mai i planeswalker) e
    blocca solo quando il bloccante sopravvive e non c'e' minaccia: un giocatore semplice, per far finire le partite."""

    def attacca(self, p, i):
        return [o for o in p.t.campo if o.controllore == i and p.puo_attaccare(o)]

    def blocca(self, p, i):
        liberi = [o for o in p.t.campo if o.controllore == i and "creature" in o.carta.tipi and not o.tappato]
        scelta = {}
        for a in sorted(p.attaccanti, key=lambda a: -forza(a)):
            if "menace" in parole(a): continue
            b = next((b for b in liberi if b not in scelta and p.puo_bloccare(b, a) and costituzione(b) > forza(a)
                      and "deathtouch" not in parole(a)), None)
            if b is not None: scelta[b] = a
        return scelta


class CasoCombatte(PL.Caso):
    """Il Caso del passo 5 che anche attacca, blocca e assegna a caso; ogni tanto tenta una dichiarazione illegale o
    un'assegnazione che non torna, e il motore deve rifiutarla. E' il banco di prova del combattimento."""

    def __init__(self, seme, attacca=0.6, blocca=0.5, **kw):
        super().__init__(seme, **kw)
        self.p_attacca, self.p_blocca = attacca, blocca

    def attacca(self, p, i):
        mie = [o for o in p.t.campo if o.controllore == i and "creature" in o.carta.tipi]
        if not mie: return None
        if self.rng.random() < self.illegali: return [self._uno(mie)]
        d = p.difensore()
        bersagli = [d] + [o for o in p.t.campo if "planeswalker" in o.carta.tipi and o.controllore == d]
        return {o: self._uno(bersagli) for o in mie if p.puo_attaccare(o) and self.rng.random() < self.p_attacca}

    def blocca(self, p, i):
        att = list(p.attaccanti)
        mie = [o for o in p.t.campo if o.controllore == i and "creature" in o.carta.tipi]
        if not att or not mie: return None
        if self.rng.random() < self.illegali: return {self._uno(mie): self._uno(att)}
        scelta = {}
        for b in mie:
            if b.tappato or self.rng.random() >= self.p_blocca: continue
            a = self._uno(att)
            if self.rng.random() < 0.8 and not p.puo_bloccare(b, a): continue
            scelta[b] = a
        return scelta

    def assegna(self, p, i, compiti):
        if self.rng.random() < 0.4: return assegnazione_semplice(p, i, compiti)
        out = {}
        for c in compiti:
            dest = list(c["creature"]) + ([c["bersaglio"]] if c["bersaglio"] is not None else [])
            d = Counter()
            for _ in range(c["forza"]): d[self._uno(dest)] += 1
            if self.rng.random() < self.illegali: d[dest[0]] += 1          # una che non torna (510.1e)
            out[c["creatura"]] = dict(d)
        return out


# ====================================================================== la partita col combattimento
class Partita(PL.Partita):
    """La partita del passo 5 con il combattimento vero."""

    def __init__(self, t):
        super().__init__(t)
        self.assegnazione_forzata = {}
        self._azzera_combattimento()

    def _azzera_combattimento(self):
        self.attaccanti = {}          # attaccante -> chi attacca: indice del giocatore, planeswalker, None (506.4c)
        self.bloccanti = {}           # bloccante -> [attaccanti che blocca] (509.1g)
        self.bloccate = set()         # gli attaccanti bloccati (509.1h)
        self._ctrl = {}               # chi controllava l'oggetto quando e' entrato in combattimento (506.4)
        self._fuori = set()
        self.dichiarati = 0           # quanti attaccanti dichiarati (508.8)
        self.passi_danno = 0
        self.doppio = False           # 510.4: c'e' un secondo passo di danno
        self.senza_primo = set()      # 510.4: in combattimento senza primo colpo ne' doppio colpo all'inizio del primo

    # ------------------------------------------------------------------ chi e' in combattimento
    def difensore(self):
        """506.2: in due, il giocatore che non e' attivo."""
        if len(self.t.giocatori) != 2: raise NonCoperto("506.2a: il combattimento con piu' di due giocatori non e' coperto")
        return 1 - self.attivo

    def _resta(self, o):
        """506.4: resta in combattimento finche' e' in campo, e' una creatura e la controlla chi la controllava."""
        tipi = o.carta.tipi
        return o.vivo and o.zona == "campo" and "creature" in tipi and "battle" not in tipi and o.controllore == self._ctrl.get(o)

    def _togli(self, o, causa="506.4"):
        if o in self._fuori: return
        self._fuori.add(o)
        self.t._evento("fuori", carta=o.carta, vecchio=o.n, causa=causa)

    def _purga(self):
        """506.4, 506.4c: chi non puo' piu' stare in combattimento ne esce."""
        for o in list(self.attaccanti):
            if not self._resta(o):
                del self.attaccanti[o]
                self.bloccate.discard(o)
                for lst in self.bloccanti.values():
                    if o in lst: lst.remove(o)
                self._togli(o)
                continue
            b = self.attaccanti[o]
            if b is not None and not _e_giocatore(b) and not (b.vivo and b.zona == "campo" and "planeswalker" in b.carta.tipi
                                                              and b.controllore == self._ctrl.get(b)):
                self.attaccanti[o] = None                                                          # 506.4c
                self._togli(b)
        for o in list(self.bloccanti):
            if not self._resta(o):
                del self.bloccanti[o]
                self._togli(o)

    def in_combattimento(self):
        self._purga()
        return list(self.attaccanti) + [b for b in self.bloccanti if b not in self.attaccanti]

    # ------------------------------------------------------------------ gli attaccanti (508)
    def _rapida(self, o):
        return "haste" in parole(o)                                                                # 702.10b

    def _si_tappa_attaccando(self, o):
        return "vigilance" not in parole(o)                                                        # 508.1f, 702.20b

    def _motivo_non_attacca(self, o, i):
        if not (hasattr(o, "carta") and o.vivo and o.zona == "campo"): return "508.1a: attacca solo una creatura in campo"
        tipi = o.carta.tipi
        if o.controllore != i: return "508.1a: attaccano solo le creature del giocatore attivo"
        if "creature" not in tipi: return "506.3: attacca solo una creatura"
        if "battle" in tipi: return "508.1a: una battaglia non attacca"
        if o.tappato: return "508.1a: una creatura tappata non attacca"
        if self.debole(o) and not self._rapida(o): return "508.1a, 302.6: debolezza da evocazione, senza rapidita'"
        if self._ha_difensore(o): return "702.3b, 508.1c: una creatura con difensore non attacca"
        return None

    def _ha_difensore(self, o):
        return "defender" in parole(o)                                                             # 702.3b

    def _danno_di(self, o):
        """510.1a: ogni creatura assegna un danno pari alla sua forza."""
        return forza(o)

    def puo_attaccare(self, o):
        return self._motivo_non_attacca(o, self.attivo) is None

    def _motivo_bersaglio(self, b, d):
        if _e_giocatore(b): return None if b == d else "506.2: si attacca il giocatore in difesa"
        if not (hasattr(b, "carta") and b.vivo and b.zona == "campo"): return "508.1b: si attacca un giocatore o un permanente in campo"
        if "battle" in b.carta.tipi: raise NonCoperto(f"506.2, 310: attaccare una battaglia ({b}) non e' coperto")
        if "planeswalker" not in b.carta.tipi: return "506.3: si attacca un giocatore, un planeswalker o una battaglia"
        if b.controllore != d: return "506.2: si attacca un planeswalker del giocatore in difesa"
        return None

    def _leggi_attacco(self, i, scelta):
        """508.1a-c. -> ({attaccante: bersaglio}, None) o (None, il motivo per cui e' illegale)."""
        if not scelta: return {}, None
        d = self.difensore()
        coppie = list(scelta.items()) if isinstance(scelta, dict) else [(o, d) for o in scelta]
        out = {}
        for o, b in coppie:
            if o in out: return None, "508.1a: la stessa creatura due volte"
            m = self._motivo_non_attacca(o, i) or self._motivo_bersaglio(b, d)
            if m: return None, m
            out[o] = b
        return out, None

    def _dichiara_attaccanti(self, giocatori):
        """703.4i, 508.1: la dichiarazione, illegale = si torna indietro e si rifa' (734); poi si tappano (508.1f) e
        diventano attaccanti (508.1k)."""
        i = self.attivo
        self.difensore()
        f = getattr(giocatori[i], "attacca", None)
        for _ in range(1000):
            dich, motivo = self._leggi_attacco(i, f(self, i) if f else None)
            if dich is not None: break
            self.t._evento("illegale", giocatore=i, a="attacca", causa=motivo)                     # 734.1
        else: raise RuntimeError(f"il giocatore {i} dichiara solo attacchi illegali")
        for o in dich:
            if self._si_tappa_attaccando(o): self.t.tappa(o)                                       # 508.1f
        self.dichiarati = len(dich)                       # 506.5: «attacks alone» se e' l'unica dichiarata
        with self.t.insieme():                            # 508.1k: diventano attaccanti tutte insieme
            for o, b in dich.items():
                self.attaccanti[o], self._ctrl[o] = b, o.controllore
                if not _e_giocatore(b): self._ctrl[b] = b.controllore
                self.t._evento("attacca", carta=o.carta, vecchio=o.n, giocatore=i, a=scrivi(b), causa="508.1k")

    # ------------------------------------------------------------------ i bloccanti (509)
    def _volare_conta(self):
        return True

    def _minaccia_conta(self):
        return True

    def _motivo_non_blocca(self, b, a, d):
        if not (hasattr(b, "carta") and b.vivo and b.zona == "campo") or b.controllore != d:
            return "509.1a: blocca solo una creatura in campo del giocatore in difesa"
        if "creature" not in b.carta.tipi: return "506.3: blocca solo una creatura"
        if "battle" in b.carta.tipi: return "509.1a: una battaglia non blocca"
        if b.tappato: return "509.1a: una creatura tappata non blocca"
        if a not in self.attaccanti: return "509.1a: si blocca una creatura che attacca"
        if "flying" in parole(a) and not self._blocca_volanti(b) and self._volare_conta():
            return "702.9b, 509.1b: una creatura con volare la bloccano solo volare e portata"
        return None

    def _blocca_volanti(self, b):
        return bool(parole(b) & {"flying", "reach"})                                               # 702.9b, 702.17b

    def puo_bloccare(self, b, a):
        """509.1a-b per un bloccante solo (la minaccia si controlla sul blocco intero)."""
        return self._motivo_non_blocca(b, a, self.difensore()) is None

    def _leggi_blocco(self, d, scelta):
        if not scelta: return {}, None
        if not isinstance(scelta, dict): return None, "509.1a: per ogni bloccante una creatura che blocca"
        quanti = Counter()
        for b, a in scelta.items():
            m = self._motivo_non_blocca(b, a, d)
            if m: return None, m
            quanti[a] += 1
        for a, k in quanti.items():
            if "menace" in parole(a) and k < 2 and self._minaccia_conta():
                return None, "702.111b, 509.1b: una creatura con minaccia la bloccano solo due creature o piu'"
        return dict(scelta), None

    def _dichiara_bloccanti(self, giocatori):
        """703.4j, 509.1: la dichiarazione (illegale = si rifa', 734); bloccanti (509.1g), bloccati (509.1h)."""
        d = self.difensore()
        self._purga()
        f = getattr(giocatori[d], "blocca", None)
        for _ in range(1000):
            dich, motivo = self._leggi_blocco(d, f(self, d) if f else None)
            if dich is not None: break
            self.t._evento("illegale", giocatore=d, a="blocca", causa=motivo)                      # 734.1
        else: raise RuntimeError(f"il giocatore {d} dichiara solo blocchi illegali")
        for b, a in dich.items():
            self.bloccanti[b], self._ctrl[b] = [a], b.controllore
            self.t._evento("blocca", carta=b.carta, vecchio=b.n, giocatore=d, a=repr(a), causa="509.1g")
        for a in self.attaccanti:
            if any(a in lst for lst in self.bloccanti.values()):
                self.bloccate.add(a)
                self.t._evento("bloccata", carta=a.carta, vecchio=a.n, giocatore=a.controllore, causa="509.1h")

    # ------------------------------------------------------------------ il danno (510)
    def _colpisce_prima(self, o):
        return bool(parole(o) & {"first strike", "double strike"})                                 # 510.4

    def _colpisce_ancora(self, o):
        return "double strike" in parole(o)                                                        # 510.4, 702.4b

    def letale(self, x, fonte, assegnato):
        """702.19b, 702.2c, 120.4a: quanto danno da «fonte» basta perche' x abbia il letale assegnato, contando il danno gia'
        segnato e quello che le altre creature gli assegnano nello stesso passo (assegnato = {fonte: {destinatario: n}}).
        Un danno qualsiasi da una fonte con tocco mortale e' letale."""
        altri = [(f, d.get(x, 0)) for f, d in assegnato.items() if f is not fonte]
        if any(n > 0 and "deathtouch" in parole(f) for f, n in altri): return 0
        resto = costituzione(x) - x.danno - sum(n for _, n in altri)
        if resto <= 0: return 0
        return 1 if "deathtouch" in parole(fonte) else resto

    def _destinatari(self, o):
        """-> (creature che possono ricevere, chi attacca se gli puo' andare il danno, travolge)."""
        if o in self.attaccanti:
            b = self.attaccanti[o]
            if o not in self.bloccate: return [], b, False                                         # 510.1b
            travolge = "trample" in parole(o)
            bloccanti = [x for x, lst in self.bloccanti.items() if o in lst]                       # 510.1c
            return bloccanti, (b if travolge else None), travolge                                  # 702.19b, d, f
        return [a for a in self.bloccanti.get(o, []) if a in self.attaccanti], None, False         # 510.1d, 702.19a

    def _controllo_travolgere(self, c, tutte):
        """702.19b: al giocatore o al planeswalker solo dopo il letale a ogni bloccante."""
        o, b = c["creatura"], c["bersaglio"]
        if b is None or tutte[o].get(b, 0) <= 0: return None
        for x in c["creature"]:
            if tutte[o].get(x, 0) < self.letale(x, o, tutte):
                return f"702.19b: {o} assegna a {scrivi(b)} senza il letale a {x}"
        return None

    def _valida_assegnazione(self, compiti, proposta, forzate):
        """510.1e: si controlla l'assegnazione tutta insieme. -> (motivo o None, l'assegnazione completa)."""
        if not isinstance(proposta, dict): return "510.1e: l'assegnazione non e' una tabella", None
        if set(proposta) != {c["creatura"] for c in compiti}: return "510.1: le creature da assegnare non tornano", None
        tutte = {k: dict(v) for k, v in forzate.items()}
        for c in compiti:
            o, d = c["creatura"], proposta[c["creatura"]]
            ammessi = list(c["creature"]) + ([c["bersaglio"]] if c["bersaglio"] is not None else [])
            pulita = {}
            for k, n in (d or {}).items():
                if not (isinstance(n, numbers.Integral) and n >= 0): return f"510.1e: {n!r} non e' un numero di danni", None
                if not any(k is x or (_e_giocatore(k) and _e_giocatore(x) and k == x) for x in ammessi):
                    return f"510.1b-d: {o} non puo' assegnare danno a {scrivi(k)}", None
                if n: pulita[k] = pulita.get(k, 0) + int(n)
            if sum(pulita.values()) != c["forza"]: return f"510.1a: {o} assegna {sum(pulita.values())} invece di {c['forza']}", None
            tutte[o] = pulita
        for c in compiti:
            if c["travolge"]:
                m = self._controllo_travolgere(c, tutte)
                if m: return m, None
        return None, tutte

    def _assegna(self, g, chi, giocatore):
        """510.1: le assegnazioni delle creature di g che colpiscono in questo passo. Le obbligate le fa il motore (un
        solo destinatario possibile); per le altre sceglie il giocatore."""
        forzate, compiti = {}, []
        for o in chi:
            f = self._danno_di(o)
            if f <= 0: continue                                                                    # 510.1a
            creature, bersaglio, travolge = self._destinatari(o)
            if not creature and bersaglio is None: continue                                        # 510.1b-d
            if len(creature) > 1 or (creature and bersaglio is not None):
                compiti.append({"creatura": o, "forza": f, "creature": creature, "bersaglio": bersaglio, "travolge": travolge})
            else: forzate[o] = {creature[0] if creature else bersaglio: f}
        if not compiti: return forzate
        self.assegnazione_forzata = forzate
        f = getattr(giocatore, "assegna", None)
        for _ in range(1000):
            proposta = f(self, g, compiti) if f else assegnazione_semplice(self, g, compiti)
            motivo, tutte = self._valida_assegnazione(compiti, proposta, forzate)
            if motivo is None: return tutte
            self.t._evento("illegale", giocatore=g, a="assegna", causa=motivo)                     # 510.1e, 734
        raise RuntimeError(f"il giocatore {g} propone solo assegnazioni illegali")

    def _infliggi_tutto(self, tutte):
        """510.2: tutto il danno assegnato arriva insieme, senza priorita' in mezzo."""
        with self.t.insieme():
            for o, d in tutte.items():
                self.t.infliggi(o, list(d.items()), causa="510.2")

    def _passo_danno(self, giocatori):
        """703.4k-m, 510.1-2, 510.4."""
        tutte_le = self.in_combattimento()
        if self.passi_danno == 0:
            primi = [o for o in tutte_le if self._colpisce_prima(o)]
            if primi:
                self.doppio = True
                self.senza_primo = {o for o in tutte_le if not self._colpisce_prima(o)}
            chi = primi or tutte_le
        else:
            chi = [o for o in tutte_le if o in self.senza_primo or self._colpisce_ancora(o)]
        self.passi_danno += 1
        tutte = {}
        for g in (self.attivo, self.difensore()):                                                  # 510.1: prima l'attivo
            tutte.update(self._assegna(g, [o for o in chi if o.controllore == g], giocatori[g]))
        self.assegnazione_forzata = {}
        self._infliggi_tutto(tutte)

    # ------------------------------------------------------------------ il turno
    def _passi(self, fase, passi, i):
        if fase != "combattimento":
            yield from super()._passi(fase, passi, i)
            return
        self._azzera_combattimento()
        yield "inizio"
        yield "attaccanti"
        if self.dichiarati:                                                                        # 508.8
            yield "bloccanti"
            yield "danno"
            if self.doppio: yield "danno"                                                          # 510.4
        yield "fine"
        if self.dichiarati and not self.t.finita:                                                  # 104.1: finita nel passo
            self.t._evento("fine combattimento", giocatore=i, causa="511.3")                       # di fine combattimento
        self._azzera_combattimento()                                                               # 511.3

    def _azioni_del_turno(self, i, passo, giocatori):
        if self.fase == "combattimento":
            if passo == "attaccanti": self._dichiara_attaccanti(giocatori)                         # 703.4i
            elif passo == "bloccanti": self._dichiara_bloccanti(giocatori)                         # 703.4j
            elif passo == "danno": self._passo_danno(giocatori)                                    # 703.4k-m
            return
        super()._azioni_del_turno(i, passo, giocatori)


def nuova(seme, mazzo=mazzo_combattimento, decidi=None, P=Partita):
    t = Tavolo([mazzo(), mazzo()], seme=seme)
    inizia(t, decidi=decidi)
    return P(t)


# ====================================================================== le prove
class FaC(PL.Fa):
    """Il giocatore di prova del passo 5 con attacca, blocca, assegna date da fuori."""

    def __init__(self, f=None, diario=None, attacca=None, blocca=None, assegna=None, scarta=None):
        super().__init__(f, diario, scarta)
        self._att, self._blo, self._ass = attacca, blocca, assegna

    def attacca(self, p, i): return self._att(p, i) if self._att else None

    def blocca(self, p, i): return self._blo(p, i) if self._blo else None

    def assegna(self, p, i, compiti):
        scelta = self._ass(p, i, compiti) if self._ass else None
        return scelta if scelta is not None else assegnazione_semplice(p, i, compiti)


def in_fila(*scelte):
    """Una funzione che a ogni chiamata da' la scelta dopo (le funzioni ricevono p, i), poi None."""
    resto = list(scelte)
    def f(p, i, *_):
        if not resto: return None
        s = resto.pop(0)
        return s(p, i) if callable(s) else s
    return f


def prove_regole(P, T=Tavolo):
    """Le regole del combattimento una per una, su una Partita di classe P e un tavolo di classe T."""
    casi = []
    def caso(nome, ok, det=""): casi.append((nome, bool(ok), det))
    def partita(seme=1):
        """Il tavolo dopo l'inizio (103), con le mani rimesse in fondo al grimorio: ogni prova vede solo le carte che da'."""
        t = T([mazzo_combattimento(), mazzo_combattimento()], seme=seme)
        inizia(t, primo=0)
        for g in t.giocatori:
            for o in list(g.mano): t.sposta(o, "grimorio", posizione="fondo", causa="prova")
        return P(t)
    def dai(p, i, nome, campo=True):
        o = next(o for o in p.t.giocatori[i].grimorio.carte if o.nome == nome)
        p.t._togli(o)
        o = p.t._arriva(o, "grimorio", "mano", None, None, "prova")
        return p.t.metti_in_campo(o, chi=i) if campo else o
    def eventi(p, tipo): return [e for e in p.t.eventi if e.tipo == tipo]
    def passi_combattimento(p):
        return [e.a for e in eventi(p, "passo") if e.da == "combattimento"]
    def illegali(p, a): return [e.causa for e in eventi(p, "illegale") if e.a == a]
    def danni(p): return [(e.carta.nome, e.a, e.quanto) for e in eventi(p, "danno")]
    def vite(p): return [g.vite for g in p.t.giocatori]
    def morti(p, regola): return sorted(e.carta.nome for e in eventi(p, "zona") if e.causa == regola)
    def gioca(p, att=None, blo=None, ass0=None, ass1=None, f0=None, f1=None, diario=None):
        p.turno({0: FaC(f0, diario, attacca=att, assegna=ass0), 1: FaC(f1, diario, blocca=blo, assegna=ass1)})
        return p

    # 506.1, 508.8: i passi del combattimento
    p = gioca(partita())
    caso("506.1, 508.8: senza attaccanti si saltano bloccanti e danno", passi_combattimento(p) == ["inizio", "attaccanti", "fine"],
         str(passi_combattimento(p)))
    p = partita(); orso = dai(p, 0, "Orso")
    gioca(p, att=in_fila([orso]))
    caso("506.1: con un attaccante i cinque passi; 508.1f: attaccando si tappa; 510.1b, 120.3a: non bloccato, il difensore perde 2 vite",
         passi_combattimento(p) == ["inizio", "attaccanti", "bloccanti", "danno", "fine"] and orso.tappato and vite(p) == [20, 18],
         f"{passi_combattimento(p)} {vite(p)}")
    caso("511.3: finito il combattimento nessuno attacca piu'", not p.attaccanti and len(eventi(p, "fine combattimento")) == 1)
    # 104.1: la partita che finisce nel passo di fine combattimento si ferma li' (seme 23 del metro del passo 8.2, 14 ott 2026):
    # il difensore va a 0 vite mentre l'attivo ha la priorita' nel passo di fine (come per una magia che lo colpisce)
    def a_zero_nella_fine(p, i):
        if p.fase == "combattimento" and p.passo == "fine" and p.t.giocatori[1].vite > 0: p.t.giocatori[1].vite = 0
        return None
    p = partita(); orso = dai(p, 0, "Orso")
    gioca(p, att=in_fila([orso]), f0=a_zero_nella_fine)
    dopo = [e.tipo for e in p.t.eventi[next((k for k, e in enumerate(p.t.eventi) if e.tipo == "perde"), len(p.t.eventi)) + 1:]]
    caso("104.1: finita nel passo di fine combattimento, la partita si ferma li' (nessun «fine combattimento» 511.3 dopo)",
         p.t.finita and "fine combattimento" not in dopo, f"finita {p.t.finita}, dopo la sconfitta {dopo}")

    # 508.1a, 302.6, 702.10b, 734
    p = partita()
    nuovi = {}
    def entrano(p, i):
        if p.fase == "principale_1" and not nuovi:
            nuovi["orso"], nuovi["rapida"] = dai(p, 0, "Orso"), dai(p, 0, "Rapida")
    stati = []
    def prima_due_poi_una(p, i):
        stati.append(p.t.stato())
        return [nuovi["orso"], nuovi["rapida"]] if len(stati) == 1 else [nuovi["rapida"]] if len(stati) == 2 else None
    gioca(p, att=prima_due_poi_una, f0=entrano)
    caso("508.1a, 302.6: la creatura entrata in questo turno non attacca; 702.10b: con rapidita' si'",
         illegali(p, "attacca") == ["508.1a, 302.6: debolezza da evocazione, senza rapidita'"]
         and [e.carta.nome for e in eventi(p, "attacca")] == ["Rapida"] and vite(p) == [20, 18], f"{illegali(p, 'attacca')} {vite(p)}")
    caso("734.1, 508.1: la dichiarazione illegale non muove niente (l'Orso non si tappa) e si dichiara di nuovo",
         len(stati) >= 2 and stati[0] == stati[1] and not nuovi["orso"].tappato)
    p = partita(); orso = dai(p, 0, "Orso"); sua = dai(p, 1, "Orso"); dif = dai(p, 0, "Difensore")
    def tappa_dopo_lo_stap(p, i):
        if p.fase == "principale_1" and not orso.tappato: p.t.tappa(orso)   # un effetto (il passo 7): lo stap l'avrebbe stappata
    gioca(p, att=in_fila([orso], [sua], [dif]), f0=tappa_dopo_lo_stap)
    caso("508.1a: una creatura tappata non attacca, quella dell'altro nemmeno; 702.3b: il difensore non attacca",
         illegali(p, "attacca") == ["508.1a: una creatura tappata non attacca", "508.1a: attaccano solo le creature del giocatore attivo",
                                    "702.3b, 508.1c: una creatura con difensore non attacca"] and not eventi(p, "attacca"),
         str(illegali(p, "attacca")))

    # 702.20b: cautela
    p = partita(); cau = dai(p, 0, "Cautela")
    gioca(p, att=in_fila([cau]))
    caso("702.20b: la creatura con cautela attacca e resta stappata", not cau.tappato and vite(p) == [20, 18], str(vite(p)))

    # 508.1b, 120.3c, 306.8, 704.5i: il planeswalker attaccato
    p = partita(); tr = dai(p, 0, "Travolgere"); pw = dai(p, 1, "Planeswalker"); mio = dai(p, 0, "Planeswalker")
    gioca(p, att=in_fila({tr: mio}, {tr: pw}))
    caso("506.2: non si attacca il proprio planeswalker", illegali(p, "attacca") == ["506.2: si attacca un planeswalker del giocatore in difesa"],
         str(illegali(p, "attacca")))
    caso("508.1b, 120.3c, 306.8, 704.5i: il planeswalker attaccato perde fedelta' quanto il danno e a 0 va nel cimitero; il giocatore no",
         not pw.vivo and morti(p, "704.5i") == ["Planeswalker"] and vite(p) == [20, 20]
         and [e.quanto for e in eventi(p, "segnalini")] == [-3], f"{vite(p)} {[e.quanto for e in eventi(p, 'segnalini')]}")

    # 509.1a: bloccanti tappati
    p = partita(); orso = dai(p, 0, "Orso"); suo = dai(p, 1, "Orso"); p.t.tappa(suo)
    gioca(p, att=in_fila([orso]), blo=in_fila(lambda p, i: {suo: orso}))
    caso("509.1a: una creatura tappata non blocca; dopo il rifiuto il difensore non blocca e prende 2",
         illegali(p, "blocca") == ["509.1a: una creatura tappata non blocca"] and vite(p) == [20, 18], str(illegali(p, "blocca")))

    # 702.9b, 702.17b: volare e portata
    p = partita(); vol = dai(p, 0, "Volante"); orso = dai(p, 1, "Orso"); por = dai(p, 1, "Portata")
    gioca(p, att=in_fila([vol]), blo=in_fila(lambda p, i: {orso: vol}, lambda p, i: {por: vol}))
    caso("702.9b: il volante non lo blocca chi non vola ne' ha portata; 702.17b: chi ha portata si'",
         illegali(p, "blocca") == ["702.9b, 509.1b: una creatura con volare la bloccano solo volare e portata"]
         and [e.carta.nome for e in eventi(p, "blocca")] == ["Portata"] and vite(p) == [20, 20], str(illegali(p, "blocca")))
    p = partita(); orso = dai(p, 0, "Orso"); vol = dai(p, 1, "Volante")
    gioca(p, att=in_fila([orso]), blo=in_fila(lambda p, i: {vol: orso}))
    caso("702.9b: una creatura con volare blocca anche chi non vola", not illegali(p, "blocca") and not orso.vivo and not vol.vivo)

    # 702.111b: minaccia
    p = partita(); mi = dai(p, 0, "Minaccia"); o1 = dai(p, 1, "Orso"); o2 = dai(p, 1, "Orso")
    gioca(p, att=in_fila([mi]), blo=in_fila(lambda p, i: {o1: mi}, lambda p, i: {o1: mi, o2: mi}))
    caso("702.111b: la minaccia non la blocca una creatura sola, due si'",
         illegali(p, "blocca") == ["702.111b, 509.1b: una creatura con minaccia la bloccano solo due creature o piu'"]
         and len(eventi(p, "blocca")) == 2 and not mi.vivo and vite(p) == [20, 20], str(illegali(p, "blocca")))

    # 510.1c-d, 510.2, 704.5g: il danno e' simultaneo
    p = partita(); orso = dai(p, 0, "Orso"); suo = dai(p, 1, "Orso")
    gioca(p, att=in_fila([orso]), blo=in_fila(lambda p, i: {suo: orso}))
    caso("510.1c, 510.1d, 510.2, 704.5g: Orso contro Orso, il danno arriva insieme e muoiono tutti e due",
         not orso.vivo and not suo.vivo and morti(p, "704.5g") == ["Orso", "Orso"] and vite(p) == [20, 20], str(morti(p, "704.5g")))

    # 510.1c, 510.1e: diviso fra due bloccanti
    p = partita(); orso = dai(p, 0, "Orso"); c1 = dai(p, 1, "Creatura"); c2 = dai(p, 1, "Creatura")
    gioca(p, att=in_fila([orso]), blo=in_fila(lambda p, i: {c1: orso, c2: orso}),
          ass0=in_fila(lambda p, i: {orso: {c1: 1}}, lambda p, i: {orso: {c1: 1, 1: 1}}, lambda p, i: {orso: {c1: 1, c2: 1}}))
    caso("510.1c: bloccato da due, l'attaccante divide il danno come vuole; 510.1e: un'assegnazione che non torna si rifa'",
         illegali(p, "assegna") == ["510.1a: Orso#{} assegna 1 invece di 2".format(orso.n), f"510.1b-d: Orso#{orso.n} non puo' assegnare danno a G2"]
         and not c1.vivo and not c2.vivo and not orso.vivo and vite(p) == [20, 20], str(illegali(p, "assegna")))

    # 702.19b, 702.19d: travolgere
    p = partita(); tr = dai(p, 0, "Travolgere"); cr = dai(p, 1, "Creatura")
    gioca(p, att=in_fila([tr]), blo=in_fila(lambda p, i: {cr: tr}),
          ass0=in_fila(lambda p, i: {tr: {1: 3}}, lambda p, i: {tr: {cr: 1, 1: 2}}))
    caso("702.19b: travolgere: niente al giocatore senza il letale al bloccante; col letale il resto passa",
         illegali(p, "assegna") == [f"702.19b: Travolgere#{tr.n} assegna a G2 senza il letale a Creatura#{cr.n}"]
         and not cr.vivo and vite(p) == [20, 18], f"{illegali(p, 'assegna')} {vite(p)}")
    p = partita(); tr = dai(p, 0, "Travolgere"); por = dai(p, 1, "Portata"); por.danno = 2
    gioca(p, att=in_fila([tr]), blo=in_fila(lambda p, i: {por: tr}),
          ass0=in_fila(lambda p, i: {tr: {por: 1, 1: 2}}))
    caso("702.19b: il letale conta il danno gia' segnato (Portata 1/3 con 2 danni: ne basta 1)",
         not illegali(p, "assegna") and not por.vivo and vite(p) == [20, 18], f"{illegali(p, 'assegna')} {vite(p)}")
    p = partita(); tr = dai(p, 0, "Travolgere"); cr = dai(p, 1, "Creatura")
    def via_il_bloccante(p, i):
        if p.passo == "bloccanti" and cr.vivo: p.t.distruggi(cr)          # un effetto in risposta (il passo 7)
    gioca(p, att=in_fila([tr]), blo=in_fila(lambda p, i: {cr: tr}), f1=via_il_bloccante)
    caso("702.19d: travolgere bloccato senza piu' bloccanti: tutto a chi attacca",
         vite(p) == [20, 17] and [e.carta.nome for e in eventi(p, "bloccata")] == ["Travolgere"], str(vite(p)))
    p = partita(); orso = dai(p, 0, "Orso"); cr = dai(p, 1, "Creatura")
    bloccata = []
    def via_e_guarda(p, i):
        if p.passo == "bloccanti" and cr.vivo: p.t.distruggi(cr)
        if p.passo == "danno": bloccata.append(orso in p.bloccate)
    gioca(p, att=in_fila([orso]), blo=in_fila(lambda p, i: {cr: orso}), f1=via_e_guarda)
    caso("510.1c, 509.1h: senza travolgere, bloccato e senza piu' bloccanti: resta bloccato e non infligge danno",
         vite(p) == [20, 20] and bloccata and all(bloccata) and not eventi(p, "danno"), f"{vite(p)} {bloccata}")

    # 702.7b, 702.4b, 510.4: primo colpo e doppio colpo
    p = partita(); pc = dai(p, 0, "Primo colpo"); orso = dai(p, 1, "Orso")
    gioca(p, att=in_fila([pc]), blo=in_fila(lambda p, i: {orso: pc}))
    caso("702.7b, 510.4: primo colpo: due passi di danno; il bloccante ucciso nel primo non colpisce nel secondo",
         passi_combattimento(p) == ["inizio", "attaccanti", "bloccanti", "danno", "danno", "fine"] and pc.vivo and not orso.vivo
         and danni(p) == [("Primo colpo", repr(orso), 2)], f"{passi_combattimento(p)} {danni(p)}")
    p = partita(); dc = dai(p, 0, "Doppio colpo"); orso = dai(p, 0, "Orso")
    per_passo = []
    def conta(p, i):
        if p.passo == "danno" and i == 0: per_passo.append(sum(e.quanto for e in eventi(p, "danno")))
    gioca(p, att=in_fila([dc, orso]), f0=conta)
    caso("702.4b, 510.4: doppio colpo: colpisce nel primo e nel secondo passo; la creatura normale solo nel secondo",
         per_passo == [2, 6] and vite(p) == [20, 14], f"{per_passo} {vite(p)}")

    # 702.2b, 704.5h, 702.2c: tocco mortale
    p = partita(); tm = dai(p, 0, "Tocco mortale"); dif = dai(p, 1, "Difensore")
    gioca(p, att=in_fila([tm]), blo=in_fila(lambda p, i: {dif: tm}))
    caso("702.2b, 704.5h: tocco mortale: un danno basta a distruggere una 0/4; 510.1a: forza 0 non infligge danno",
         not dif.vivo and morti(p, "704.5h") == ["Difensore"] and tm.vivo and tm.danno == 0
         and danni(p) == [("Tocco mortale", repr(dif), 1)], f"{morti(p, '704.5h')} {danni(p)}")
    p = partita(); tt = dai(p, 0, "Travolgere tocco"); por = dai(p, 1, "Portata")
    gioca(p, att=in_fila([tt]), blo=in_fila(lambda p, i: {por: tt}), ass0=in_fila(lambda p, i: {tt: {por: 1, 1: 1}}))
    caso("702.2c, 702.19b: travolgere e tocco mortale: un danno al bloccante e' letale, il resto al giocatore",
         not illegali(p, "assegna") and not por.vivo and vite(p) == [20, 19], f"{illegali(p, 'assegna')} {vite(p)}")

    # 702.15b: legame vitale, attaccando e bloccando
    p = partita(); lv = dai(p, 0, "Legame vitale")
    gioca(p, att=in_fila([lv]))
    caso("702.15b, 120.3f: legame vitale: chi controlla la fonte guadagna il danno inflitto", vite(p) == [22, 18], str(vite(p)))
    p = partita(); orso = dai(p, 0, "Orso"); lv = dai(p, 1, "Legame vitale")
    gioca(p, att=in_fila([orso]), blo=in_fila(lambda p, i: {lv: orso}))
    caso("702.15b: anche bloccando", vite(p) == [20, 22], str(vite(p)))

    # 702.12b: indistruttibile
    p = partita(); orso = dai(p, 0, "Orso"); ind = dai(p, 1, "Indistruttibile")
    dopo = []
    def guarda(p, i):
        if p.passo == "fine" and i == 0: dopo.append((ind.vivo, ind.danno))
    gioca(p, att=in_fila([orso]), blo=in_fila(lambda p, i: {ind: orso}), f0=guarda)
    caso("702.12b: l'indistruttibile non muore di danno letale (resta in campo con 2 danni su 1)", dopo == [(True, 2)] and ind.vivo, str(dopo))
    p = partita(); tm = dai(p, 0, "Tocco mortale"); ind = dai(p, 1, "Indistruttibile")
    gioca(p, att=in_fila([tm]), blo=in_fila(lambda p, i: {ind: tm}))
    caso("702.12b: ne' di tocco mortale", ind.vivo and not tm.vivo, f"{ind.vivo} {tm.vivo}")

    # 506.4, 510.1d, 506.4c: uscire dal combattimento
    p = partita(); orso = dai(p, 0, "Orso"); suo = dai(p, 1, "Orso")
    def via_l_attaccante(p, i):
        if p.passo == "bloccanti" and orso.vivo: p.t.distruggi(orso)
    gioca(p, att=in_fila([orso]), blo=in_fila(lambda p, i: {suo: orso}), f1=via_l_attaccante)
    caso("506.4, 510.1d: l'attaccante che lascia il campo esce dal combattimento, e chi lo bloccava non infligge danno",
         suo.vivo and suo.danno == 0 and not eventi(p, "danno") and [e.carta.nome for e in eventi(p, "fuori")] == ["Orso"],
         str([(e.carta.nome, e.causa) for e in eventi(p, "fuori")]))
    p = partita(); orso = dai(p, 0, "Orso")
    def ruba(p, i):
        if p.passo == "attaccanti" and orso.controllore == 0: p.t.prendi_controllo(orso, 1)   # un effetto (il passo 7)
    gioca(p, att=in_fila([orso]), f1=ruba)
    caso("506.4: chi cambia controllore esce dal combattimento e non infligge danno",
         vite(p) == [20, 20] and not eventi(p, "danno") and passi_combattimento(p) == ["inizio", "attaccanti", "bloccanti", "danno", "fine"],
         f"{vite(p)} {passi_combattimento(p)}")
    p = partita(); orso = dai(p, 0, "Orso"); pw = dai(p, 1, "Planeswalker")
    def via_il_planeswalker(p, i):
        if p.passo == "attaccanti" and pw.vivo: p.t.distruggi(pw)
    gioca(p, att=in_fila({orso: pw}), f1=via_il_planeswalker)
    caso("506.4c, 510.1b: se il planeswalker attaccato lascia il campo, l'attaccante resta ma non infligge danno",
         vite(p) == [20, 20] and not eventi(p, "danno") and orso.tappato, str(vite(p)))

    # 514.2: il danno si toglie nella pulizia
    p = partita(); orso = dai(p, 0, "Orso"); por = dai(p, 1, "Portata")
    segnato = []
    def guarda_danno(p, i):
        if p.passo == "fine" and i == 0: segnato.append(por.danno)
    gioca(p, att=in_fila([orso]), blo=in_fila(lambda p, i: {por: orso}), f0=guarda_danno)
    caso("120.6, 514.2: il danno segnato resta fino alla pulizia, poi si toglie", segnato == [2] and por.vivo and por.danno == 0,
         f"{segnato} {por.danno}")

    # 507.2, 508.2, 509.2, 510.3, 511.1, 117.3a: la priorita' nei passi del combattimento
    d = []
    p = partita(); orso = dai(p, 0, "Orso"); suo = dai(p, 1, "Portata")
    gioca(p, att=in_fila([orso]), blo=in_fila(lambda p, i: {suo: orso}), diario=d)
    seq = [(s, i) for _, f, s, i, _ in d if f == "combattimento"]
    caso("507.2, 508.2, 509.2, 510.3, 511.1: in ogni passo del combattimento la priorita' la riceve prima l'attivo, poi l'altro",
         seq == [(s, i) for s in ("inizio", "attaccanti", "bloccanti", "danno", "fine") for i in (0, 1)], str(seq))

    # 117.1a: l'istantaneo nel passo dei bloccanti
    p = partita(); orso = dai(p, 0, "Orso"); dai(p, 1, "Terra"); ist = dai(p, 1, "Istantaneo", campo=False)
    fatto = set()
    def trucco(p, i):
        if p.passo == "bloccanti" and "i" not in fatto: fatto.add("i"); return ("lancia", ist, 0, None)
    gioca(p, att=in_fila([orso]), f1=trucco)
    caso("117.1a: nel passo dei bloccanti si lancia un istantaneo (il posto dei trucchi da combattimento)",
         [(e.carta.nome, e.causa) for e in eventi(p, "risolve")] == [("Istantaneo", "608.1")])

    # i buchi dichiarati: una parola chiave che il passo 6 non conosce
    p = partita(); orso = dai(p, 0, "Orso"); orso.carta.car["parole"] = ["infect"]
    try: gioca(p, att=in_fila([orso])); esito = "nessun errore"
    except NonCoperto as e: esito = str(e)
    caso("702, 120.3b: una parola chiave fuori dal passo 6 (infetto) esce NonCoperto", esito.startswith("702"), esito)
    return casi


# ====================================================================== la vigilanza sulle partite a caso
def _kw(o):
    return set(o.carta.car.get("parole", ()))


def vigila(P):
    """Una Partita di classe P che rifa' a parte, dopo ogni dichiarazione e ogni passo di danno, i conti del regolamento:
    chi poteva attaccare e bloccare, chi colpisce in quale passo, quanto danno e a chi, le vite, chi doveva morire."""
    base = PL.vigila(P)

    class Vigila(base):
        def __init__(self, t):
            super().__init__(t)
            self._v_senza, self._v_morte = None, []

        def esegui(self, i, azione):
            ok = super().esegui(i, azione)
            if ok and azione[0] == "lancia" and self.fase == "combattimento":
                self.conti["magie nei passi del combattimento"] += 1
                if self.passo in ("bloccanti", "danno"): self.conti["magie dopo i bloccanti"] += 1
            return ok

        def _dichiara_attaccanti(self, giocatori):
            i = self.attivo
            inizio, prima = self.inizio_turno[i], {o: (o.tappato, o.controllo_dal) for o in self.t.campo}
            super()._dichiara_attaccanti(giocatori)
            self._v_senza = None
            for o, b in self.attaccanti.items():
                tap, dal = prima.get(o, (True, None))
                if tap: self._sbaglia(f"{o} attacca ma era tappata o fuori dal campo (508.1a)")
                if o.controllore != i or "creature" not in o.carta.tipi: self._sbaglia(f"{o} attacca senza essere una creatura di G{i + 1}")
                if not (dal is not None and dal < inizio) and "haste" not in _kw(o): self._sbaglia(f"{o} attacca con la debolezza da evocazione (302.6)")
                if "defender" in _kw(o): self._sbaglia(f"{o} attacca col difensore (702.3b)")
                if o.tappato == ("vigilance" in _kw(o)): self._sbaglia(f"{o} tappata={o.tappato} dopo l'attacco (508.1f, 702.20b)")
                if not (b == 1 - i if _e_giocatore(b) else "planeswalker" in b.carta.tipi and b.controllore == 1 - i):
                    self._sbaglia(f"{o} attacca {scrivi(b)} (506.2)")
                self.conti["attacchi"] += 1
                if not _e_giocatore(b): self.conti["planeswalker attaccati"] += 1
            if self.attaccanti: self.conti["combattimenti"] += 1

        def _dichiara_bloccanti(self, giocatori):
            prima = {o: o.tappato for o in self.t.campo}
            super()._dichiara_bloccanti(giocatori)
            d, quanti = 1 - self.attivo, Counter()
            for b, lst in self.bloccanti.items():
                a = lst[0]
                quanti[a] += 1
                if prima.get(b, True): self._sbaglia(f"{b} blocca ma era tappata o fuori dal campo (509.1a)")
                if b.controllore != d or "creature" not in b.carta.tipi or len(lst) != 1: self._sbaglia(f"{b} non poteva bloccare (509.1a)")
                if a not in self.attaccanti: self._sbaglia(f"{b} blocca {a}, che non attacca (509.1a)")
                if "flying" in _kw(a) and not _kw(b) & {"flying", "reach"}: self._sbaglia(f"{b} blocca il volante {a} (702.9b)")
                self.conti["blocchi"] += 1
                if "flying" in _kw(a): self.conti["volanti bloccati"] += 1
            for a, k in quanti.items():
                if "menace" in _kw(a):
                    if k < 2: self._sbaglia(f"{a} con minaccia bloccata da {k} (702.111b)")
                    else: self.conti["minacce bloccate da due"] += 1

        def _passo_danno(self, giocatori):
            self._purga()
            att, blo, bloccate = dict(self.attaccanti), {b: list(l) for b, l in self.bloccanti.items()}, set(self.bloccate)
            in_c = list(att) + [b for b in blo if b not in att]
            if self.passi_danno == 0:
                fs = [o for o in in_c if _kw(o) & {"first strike", "double strike"}]
                self._v_senza = {o for o in in_c if not _kw(o) & {"first strike", "double strike"}} if fs else None
                ammessi = set(fs) if fs else set(in_c)
                if fs: self.conti["combattimenti con primo colpo"] += 1
            else:
                ammessi = {o for o in in_c if (self._v_senza and o in self._v_senza) or "double strike" in _kw(o)}
            vite_prima, danno_prima = [g.vite for g in self.t.giocatori], {o: o.danno for o in self.t.campo}
            k0 = len(self.t.eventi)
            super()._passo_danno(giocatori)
            per_fonte, a_chi = defaultdict(Counter), defaultdict(list)
            for e in self.t.eventi[k0:]:
                if e.tipo != "danno": continue
                dest = ("G", e.giocatore) if e.nuovo is None else ("o", e.nuovo)
                per_fonte[e.vecchio][dest] += e.quanto
                a_chi[dest].append((e.vecchio, e.quanto))
            fonti = {o.n: o for o in in_c}
            for n in per_fonte:
                if n not in fonti: self._sbaglia(f"l'oggetto {n} infligge danno senza essere in combattimento")
            def chiave(b): return None if b is None else ("G", b) if _e_giocatore(b) else ("o", b.n)
            for o in in_c:
                f, bl = o.carta.car["forza"], []
                if o in att:
                    tk = chiave(att[o])
                    if o not in bloccate: dest = {tk} - {None}
                    else:
                        bl = [x for x, l in blo.items() if o in l]
                        dest = {("o", x.n) for x in bl} | ({tk} - {None} if "trample" in _kw(o) else set())
                else: tk, bl, dest = None, [], {("o", a.n) for a in blo[o] if a in att}
                atteso = f if (o in ammessi and f > 0 and dest) else 0
                dato = per_fonte.get(o.n, Counter())
                if sum(dato.values()) != atteso: self._sbaglia(f"{o} infligge {sum(dato.values())}, attesi {atteso} (510.1a, 510.4)")
                if set(dato) - dest: self._sbaglia(f"{o} infligge danno a chi non poteva (510.1b-d)")
                if o in bloccate and "trample" in _kw(o) and tk and dato.get(tk, 0) > 0:
                    self.conti["travolge oltre i bloccanti"] += 1
                    for x in bl:
                        ricevuto = a_chi.get(("o", x.n), [])
                        tocco = any(q > 0 and "deathtouch" in _kw(fonti[s]) for s, q in ricevuto if s in fonti)
                        if not tocco and danno_prima.get(x, 0) + sum(q for _, q in ricevuto) < x.carta.car["costituzione"]:
                            self._sbaglia(f"{o} travolge senza il letale a {x} (702.19b)")
                if dato and "deathtouch" in _kw(o):
                    self._v_morte += [x for x in self.t.campo if ("o", x.n) in dato and "creature" in x.carta.tipi]
            for j, g in enumerate(self.t.giocatori):
                atteso = vite_prima[j] - sum(q for _, q in a_chi.get(("G", j), []))
                atteso += sum(sum(per_fonte[o.n].values()) for o in in_c if "lifelink" in _kw(o) and o.controllore == j)
                if g.vite != atteso: self._sbaglia(f"G{j + 1} a {g.vite} vite, attese {atteso} (120.3a, 702.15b)")
            if any(k[0] == "G" for k in a_chi): self.conti["passi con danno ai giocatori"] += 1
            if any("lifelink" in _kw(o) and per_fonte.get(o.n) for o in in_c): self.conti["legami vitali"] += 1
            e = controlla(self.t)
            if e: self._sbaglia(e[0])

        def _priorita_del_passo(self, giocatori):
            super()._priorita_del_passo(giocatori)
            if self.passo != "danno" or self.t.finita: return
            for o in self.t.campo:                                                                 # 704.5g, 704.5h, 702.12b
                if "creature" not in o.carta.tipi or "indestructible" in _kw(o): continue
                if 0 < o.carta.car["costituzione"] <= o.danno: self._sbaglia(f"{o} con danno letale ancora in campo (704.5g)")
                if o in self._v_morte and o.vivo: self._sbaglia(f"{o} toccata dal tocco mortale ancora in campo (704.5h)")
            self._v_morte = []
    return Vigila


def a_caso(P, seme, T=Tavolo, mazzo=mazzo_combattimento, giocatori=None):
    t = T([mazzo(), mazzo()], seme=seme)
    inizia(t)
    p = vigila(P)(t)
    p.gioca(giocatori or {0: CasoCombatte(seme * 2 + 1), 1: CasoCombatte(seme * 2 + 2)})
    p.err += PL.pila_dagli_eventi(t)
    morti = Counter(e.causa for e in t.eventi if e.tipo == "zona" and e.causa in ("704.5g", "704.5h"))
    p.conti["morti di danno letale"] += morti["704.5g"]
    p.conti["morti di tocco mortale"] += morti["704.5h"]
    p.conti["dichiarazioni illegali"] += sum(1 for e in t.eventi if e.tipo == "illegale" and e.a in ("attacca", "blocca"))
    p.conti["assegnazioni illegali"] += sum(1 for e in t.eventi if e.tipo == "illegale" and e.a == "assegna")
    return p


def prova():
    casi = []
    def caso(nome, ok, det=""): casi.append((nome, bool(ok), det))
    m = mazzo_combattimento()
    caso("il mazzo finto del passo 6: 40 carte, 17 terre, 19 creature, 3 istantanei, le 12 parole chiave del passo",
         len(m) == 40 and sum(1 for v in m if v[0] == "Terra") == 17 and sum(1 for v in m if v[1] == "Creature") == 19
         and {p for v in m for p in v[2].get("parole", ())} == set(PAROLE))
    for nome, ok, det in prove_regole(Partita): caso(nome, ok, det)

    # senza attacchi il passo 6 gioca la stessa partita del passo 5, evento per evento
    diverse = []
    for s in range(20):
        a = PL.nuova(s); a.gioca({0: PL.Caso(s * 2 + 1), 1: PL.Caso(s * 2 + 2)})
        b = nuova(s, mazzo=PL.mazzo_pila); b.gioca({0: PL.Caso(s * 2 + 1), 1: PL.Caso(s * 2 + 2)})
        if [e.chiave() for e in a.t.eventi] != [e.chiave() for e in b.t.eventi] or a.t.stato() != b.t.stato(): diverse.append(s)
    caso("senza attacchi il passo 6 gioca la stessa partita del passo 5: 20 partite con risposte, stessi eventi uno per uno",
         not diverse, f"semi diversi: {diverse}")

    # le partite intere fra due giocatori che attaccano
    fini, err = Counter(), []
    for s in range(20):
        p = a_caso(Partita, s, giocatori={0: Combatte(), 1: Combatte()})
        err += [f"seme {s}: {e}" for e in p.err]
        perdente = 1 - p.t.vincitore if p.t.vincitore is not None else None
        fini[p.t.giocatori[perdente].perche if perdente is not None else "pari"] += 1
    caso("20 partite fra due giocatori che attaccano: tavolo sano, conti del combattimento rifatti a parte senza errori, "
         "e finiscono a vite zero (704.5a), non piu' a grimorio vuoto", not err and fini["704.5a"] >= 18, "; ".join(err[:2]) or str(dict(fini)))

    # le partite a caso, con risposte, dichiarazioni illegali e assegnazioni a caso
    tot, err = Counter(), []
    for s in range(40):
        p = a_caso(Partita, s)
        tot += p.conti
        err += [f"seme {s}: {e}" for e in p.err]
    minimi = {"attacchi": 500, "blocchi": 100, "planeswalker attaccati": 5, "volanti bloccati": 5, "minacce bloccate da due": 2,
              "combattimenti con primo colpo": 20, "travolge oltre i bloccanti": 5, "legami vitali": 20,
              "morti di danno letale": 100, "morti di tocco mortale": 5, "dichiarazioni illegali": 50, "assegnazioni illegali": 20,
              "magie nei passi del combattimento": 20, "magie dopo i bloccanti": 5}
    scarsi = {k: tot[k] for k, v in minimi.items() if tot[k] < v}
    caso("40 partite a caso: ogni dichiarazione, ogni passo di danno e le vite rifatti a parte, senza errori, coprendo ogni regola",
         not err and not scarsi, "; ".join(err[:2]) or (f"troppo pochi: {scarsi}" if scarsi else str({k: tot[k] for k in minimi})))
    a, b = a_caso(Partita, 3), a_caso(Partita, 3)
    caso("stesso seme, stessa partita (anche col combattimento)", [e.chiave() for e in a.t.eventi] == [e.chiave() for e in b.t.eventi])

    # le prove negative: motori rotti apposta, la regola giusta deve risultare rossa
    class NonSalta(Partita):                       # non salta bloccanti e danno senza attaccanti
        def _passi(self, fase, passi, i):
            if fase != "combattimento": yield from super()._passi(fase, passi, i); return
            self._azzera_combattimento()
            yield from ("inizio", "attaccanti", "bloccanti", "danno", "fine")
            self._azzera_combattimento()
    class SenzaRapidita(Partita):
        def _rapida(self, o): return False
    class CautelaTappa(Partita):
        def _si_tappa_attaccando(self, o): return True
    class IgnoraVolare(Partita):
        def _volare_conta(self): return False
    class IgnoraMinaccia(Partita):
        def _minaccia_conta(self): return False
    class DannoInDueTempi(Partita):                # prima gli attaccanti, le azioni di stato, poi i bloccanti rimasti
        def _infliggi_tutto(self, tutte):
            for o, d in tutte.items():
                if o in self.attaccanti: self.t.infliggi(o, list(d.items()))
            self.t.azioni_di_stato()
            for o, d in tutte.items():
                if o not in self.attaccanti and o.vivo: self.t.infliggi(o, list(d.items()))
    class TravolgereLibero(Partita):
        def _controllo_travolgere(self, c, tutte): return None
    class SenzaPrimoColpo(Partita):
        def _colpisce_prima(self, o): return False
    class NonEsce(Partita):                        # resta in combattimento anche cambiando controllore o zona
        def _resta(self, o): return True
    class SenzaPortata(Partita):
        def _blocca_volanti(self, b): return "flying" in parole(b)
    class SenzaDifensore(Partita):
        def _ha_difensore(self, o): return False
    class DoppioComePrimo(Partita):                # il doppio colpo colpisce solo nel primo passo
        def _colpisce_ancora(self, o): return False
    class LetaleSenzaTocco(Partita):               # il letale di travolgere non conta il tocco mortale (702.2c)
        def letale(self, x, fonte, assegnato):
            altri = sum(d.get(x, 0) for f, d in assegnato.items() if f is not fonte)
            return max(0, costituzione(x) - x.danno - altri)
    class SenzaToccoMortale(Tavolo):
        def azioni_di_stato(self):
            for o in self.campo: o.toccato_da_morte = False
            return super().azioni_di_stato()
    class SenzaLegame(Tavolo):
        def infliggi(self, fonte, danni, causa="120.2b"):
            vero = fonte.carta.car.get("parole")
            fonte.carta.car["parole"] = [x for x in (vero or ()) if x != "lifelink"]
            try: return super().infliggi(fonte, danni, causa)
            finally: fonte.carta.car["parole"] = vero
    class IgnoraIndistruttibile(Tavolo):
        def _parole_per_stato(self, ogg): return super()._parole_per_stato(ogg) - {"indestructible"}
    for nome, P, T, cerca in (("bloccanti e danno senza attaccanti", NonSalta, Tavolo, "508.8"),
                              ("la rapidita' non conta", SenzaRapidita, Tavolo, "702.10b"),
                              ("la cautela tappa", CautelaTappa, Tavolo, "702.20b"),
                              ("il volante bloccato da chiunque", IgnoraVolare, Tavolo, "702.9b"),
                              ("la minaccia bloccata da una", IgnoraMinaccia, Tavolo, "702.111b"),
                              ("il danno non simultaneo", DannoInDueTempi, Tavolo, "510.2"),
                              ("travolgere senza letale", TravolgereLibero, Tavolo, "702.19b"),
                              ("niente primo colpo", SenzaPrimoColpo, Tavolo, "702.7b"),
                              ("nessuno esce dal combattimento", NonEsce, Tavolo, "506.4"),
                              ("la portata non blocca i volanti", SenzaPortata, Tavolo, "702.17b"),
                              ("il difensore attacca", SenzaDifensore, Tavolo, "702.3b"),
                              ("il doppio colpo colpisce una volta", DoppioComePrimo, Tavolo, "702.4b"),
                              ("il letale di travolgere senza tocco mortale", LetaleSenzaTocco, Tavolo, "702.2c"),
                              ("niente tocco mortale", Partita, SenzaToccoMortale, "704.5h"),
                              ("niente legame vitale", Partita, SenzaLegame, "702.15b"),
                              ("l'indistruttibile muore", Partita, IgnoraIndistruttibile, "702.12b")):
        try: rosse = [n for n, ok, _ in prove_regole(P, T) if not ok]
        except Exception as e: rosse = [f"si rompe: {type(e).__name__}: {e} ({cerca})"]
        caso(f"prova negativa: {nome} risulta rosso", any(cerca in n for n in rosse), "; ".join(r[:60] for r in rosse[:3]) or "nessuna regola rossa")
    for nome, P, cerca in (("il volante bloccato da chiunque", IgnoraVolare, "702.9b"),
                           ("niente primo colpo", SenzaPrimoColpo, "510.4"),
                           ("travolgere senza letale", TravolgereLibero, "702.19b")):
        err = [e for s in range(6) for e in a_caso(P, s).err]
        caso(f"prova negativa sulle partite a caso: {nome} la trova la vigilanza", any(cerca in e for e in err), "; ".join(err[:1]))

    for nome, ok, det in casi:
        print(f"  {'ok   ' if ok else 'ROSSO'} {nome}" + (f"  [{det}]" if det else ""))
    print(f"{sum(ok for _, ok, _ in casi)}/{len(casi)}")
    return 0 if all(ok for _, ok, _ in casi) else 1


def racconta(seme=1):
    """Una partita fra due Combatte, una riga per turno: attacchi, blocchi, danni, morti, vite."""
    t = Tavolo([mazzo_combattimento(), mazzo_combattimento()], seme=seme)
    inizia(t)
    p = vigila(Partita)(t)
    print(f"seme {seme}: comincia G{t.primo + 1}")
    visti = [0]
    def riga(p):
        nuovi = p.t.eventi[visti[0]:]; visti[0] = len(p.t.eventi)
        conta = Counter(e.tipo for e in nuovi)
        morti = sum(1 for e in nuovi if e.tipo == "zona" and e.causa in ("704.5g", "704.5h"))
        al_giocatore = sum(e.quanto for e in nuovi if e.tipo == "danno" and e.nuovo is None)
        print(f"  T{p.t.turno_numero:>2} G{p.ultimo + 1}: attacca {conta['attacca']}, blocca {conta['blocca']}, "
              f"danno al giocatore {al_giocatore}, morti {morti}, vite {p.t.giocatori[0].vite}-{p.t.giocatori[1].vite}")
    p.gioca({0: Combatte(), 1: Combatte()}, dopo_ogni_turno=riga)
    print(f"fine al turno {t.turno_numero}: " + (f"vince G{t.vincitore + 1}" if t.vincitore is not None else "pari")
          + (f"; ERRORI: {p.err}" if p.err else ""))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if "--prova" in sys.argv: sys.exit(prova())
    if "--partita" in sys.argv:
        k = sys.argv.index("--partita")
        racconta(int(sys.argv[k + 1]) if len(sys.argv) > k + 1 else 1)
    else: print(__doc__)
