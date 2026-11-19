"""Le zone e i giocatori del motore di partita: il passo 2 (Autore, 14 ott 2026: «costruiamolo noi per step»).

Il tavolo tiene tutto quello che sta in una partita, secondo il regolamento ufficiale (Regole/MagicCompRules.txt, numeri
letti dal file con Motore_Opzioni/regolamento.py):
  - le zone (400.1): grimorio, mano e cimitero di ogni giocatore; campo, pila, esilio e comando in comune. Pubbliche e
    nascoste (400.2): `vista(i)` dice cosa vede il giocatore i (la mano degli altri si conta e basta, 402.3; i grimori
    si contano, 401.3);
  - la carta e l'oggetto. La carta (`Carta`) e' il pezzo fisico e non cambia mai: ha un proprietario, chi l'aveva nel
    mazzo (108.3) o chi ha creato la pedina (111.2). L'oggetto (`Oggetto`, 109.1) e' la carta in una zona: quando cambia
    zona nasce un oggetto nuovo, senza memoria del vecchio (400.7, 403.4). Il vecchio resta spento (vivo=False) e chi lo
    teneva come riferimento (un bersaglio, un'aura) non lo trova piu': `sposta` su un oggetto spento non fa niente;
  - un oggetto che dovrebbe andare nel grimorio, nella mano o nel cimitero di un altro va in quelli del proprietario
    (400.3); un istantaneo o una stregoneria non entra in campo, resta dov'era (400.4a); esiliare cio' che e' gia' in
    esilio fa un oggetto nuovo (400.8, 406.7);
  - il controllore: solo i permanenti e le magie ne hanno uno (108.4); in campo e' chi ce l'ha messo (110.2, 110.2a), in
    pila chi l'ha lanciato (405.4); a chi chiede il controllore di una carta che non ne ha si risponde col proprietario
    (108.4a). Un permanente entra stappato e a faccia in su (110.5b); tappare un permanente gia' tappato non si puo'
    (701.26a-b);
  - le pedine (111): il proprietario e' chi le crea, fuori dal campo smettono di esistere al controllo di stato (111.7,
    704.5d), e una pedina che ha lasciato il campo non si sposta piu' (111.8);
  - le vite (119): si parte da 20 (103.4, 119.1); pagare vite solo se ce ne sono abbastanza (119.4); impostarle e' un
    guadagno o una perdita (119.5); guadagnare 0 non e' un evento (119.9);
  - le azioni di stato di questo passo (704.3, tutte insieme, finche' ce n'e'): a 0 vite si perde (704.5a), chi ha
    pescato da un grimorio vuoto perde (704.5b, 121.4), le pedine fuori dal campo cessano (704.5d). Se resta un solo
    giocatore vince (104.2a); se perdono tutti insieme e' pari (104.4a). Dal passo 6 anche il danno letale (704.5g) e il
    tocco mortale (704.5h), con l'indistruttibile che li ignora (702.12b);
  - il danno (120, dal passo 6): `infliggi` fa perdere vite, toglie fedelta', segna il danno sulle creature, ricorda il
    tocco mortale e fa guadagnare il legame vitale. Le parole chiave conosciute sono in PAROLE, con la loro regola;
  - i verbi (701): pescare una alla volta (121.1-2), scartare (701.9a), distruggere (701.8a), sacrificare solo cio' che
    si controlla (701.21a), esiliare (701.13a), macinare, scry, surveil e cercare (dal grimorio del passo 1);
  - ogni cambio di zona e' un `Evento` con l'oggetto vecchio e il nuovo: e' quello che gli inneschi leggeranno dopo
    («quando muore» = dal campo al cimitero; 400.7e: l'innesco trova l'oggetto nuovo se la zona e' pubblica).
Convenzioni: nel grimorio la cima e' l'indice 0 (come nel passo 1); nel cimitero e in pila la cima e' l'ultimo
(404.1 «on top», 405.2). Le carte sono trattate per nome e tipo: cosa fanno e' il passo 7.

    py -I -X utf8 Motore_Partita/tavolo.py --prova      le prove: regole, conservazione, oggetti nuovi, prove negative
"""
import contextlib
import itertools
import numbers
import os
import secrets
import sys
from collections import Counter
from dataclasses import astuple, dataclass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # py -I non mette la cartella dello script nel percorso
import numpy as np
from grimorio import Grimorio
from mana import NonCoperto, Riserva

ZONE = ("grimorio", "mano", "campo", "cimitero", "pila", "esilio", "comando")   # 400.1 (l'ante non si gioca, 407.1)
DEL_GIOCATORE = ("grimorio", "mano", "cimitero")                               # 400.1: ognuno ha i suoi
CONDIVISE = ("campo", "pila", "esilio", "comando")
PUBBLICHE = ("campo", "cimitero", "pila", "esilio", "comando")                 # 400.2
CON_CONTROLLORE = ("campo", "pila")                                            # 108.4: permanenti e magie
TIPI_PERMANENTE = {"artifact", "battle", "creature", "enchantment", "land", "planeswalker"}   # 110.4
BASE = {n: f"Basic Land — {n}" for n in ("Plains", "Island", "Swamp", "Mountain", "Forest")}

# le parole chiave che il motore conosce dal passo 6, con la loro regola (letta dal file): una carta finta le porta nelle
# caratteristiche, car["parole"]. Una parola che non e' qui esce NonCoperto: infetto, avvizzire e tossico cambiano cosa fa
# il danno (120.3b, 120.3d, 120.3g), la protezione lo previene (615): sono il passo 7.
PAROLE = {"deathtouch": "702.2", "defender": "702.3", "double strike": "702.4", "first strike": "702.7",
          "flying": "702.9", "haste": "702.10", "indestructible": "702.12", "lifelink": "702.15", "reach": "702.17",
          "trample": "702.19", "vigilance": "702.20", "menace": "702.111"}


def parole(ogg):
    """Le parole chiave dell'oggetto (702.1). Le chiede al suo tavolo: qui sono quelle stampate, dal passo 7
    (Motore_Partita/effetti.py) quelle dopo gli effetti continui (613.1f)."""
    t = getattr(ogg, "tavolo", None)
    return t.parole_di(ogg) if t is not None else parole_stampate(ogg)


def parole_stampate(ogg, conosciute=PAROLE):
    ps = set(ogg.carta.car.get("parole", ()))
    altre = ps - set(conosciute)
    if altre: raise NonCoperto(f"702: {sorted(altre)} di {ogg.nome} non sono fra le parole chiave coperte")
    return ps


def forza(ogg):
    """208.1: la forza. Qui quella stampata, dal passo 7 dopo i segnalini e gli effetti continui (613.4)."""
    t = getattr(ogg, "tavolo", None)
    return t.forza_di(ogg) if t is not None else ogg.carta.car["forza"]


def costituzione(ogg):
    """208.1: la costituzione (vedi forza)."""
    t = getattr(ogg, "tavolo", None)
    return t.costituzione_di(ogg) if t is not None else ogg.carta.car["costituzione"]


class Carta:
    """Il pezzo fisico (o la pedina, 111.1): non cambia mai per tutta la partita. Il proprietario e' l'indice del
    giocatore (108.3, 111.2). I tipi sono quelli della faccia davanti, prima del «—» (205.1)."""

    def __init__(self, n, nome, tipo, proprietario, pedina=False, car=None):
        self.n, self.nome, self.tipo, self.proprietario, self.pedina = n, nome, tipo or "", proprietario, pedina
        davanti = self.tipo.split("//")[0].split("—")[0]
        self.tipi = set(davanti.lower().split())
        # le caratteristiche stampate che servono al turno: «costo» il costo di mana come e' stampato, «{1}{G}» (202.1;
        # assente = nessun costo, 202.1b), «forza» e «costituzione» (208), «fedelta» (306.5), «mana» le produzioni
        # dell'abilita' {T} oltre a quelle dei tipi base (605, 305.6: mana.produzioni). Il resto col passo 7.
        self.car = dict(car or {})

    @property
    def permanente(self): return bool(self.tipi & TIPI_PERMANENTE)          # 110.4

    def retro(self):
        """712.6: la faccia dietro di una carta a due facce, con le sue caratteristiche (car «retro»), o None."""
        r = self.__dict__.get("_faccia_retro")
        if r is None and self.car.get("retro"):
            nome, tipo, car = self.car["retro"]
            if not self.car.get("mdfc") and self.car.get("costo") and "costo" not in car:   # 712.6d, 202.3b: il valore di mana
                car = dict(car, costo=self.car["costo"])                                      # della faccia davanti (i colori:
            r = self._faccia_retro = Carta(self.n, nome, tipo, self.proprietario, pedina=self.pedina, car=car)   # indicatore, 204)
        return r

    def __repr__(self):
        return self.nome


class Oggetto:
    """La carta in una zona (109.1). Quando cambia zona diventa un oggetto nuovo (400.7): questo resta spento e dice in
    quale si e' trasformato (diventato = il numero del nuovo), per chi deve seguire una carta, non un oggetto."""

    def __init__(self, n, carta, zona, controllore=None):
        self.n, self.carta, self.zona, self.controllore = n, carta, zona, controllore
        self.tappato = False            # 110.5b: entra stappato
        self.a_faccia_in_giu = False    # 110.5b: e a faccia in su
        self.vivo, self.diventato = True, None
        self.segnalini = Counter()      # 122.1 (la fedelta' di un planeswalker, 306.5b)
        self.danno = 0                  # 120.6: resta fino alla pulizia (514.2)
        self.toccato_da_morte = False   # 702.2b, 704.5h: danno da una fonte con tocco mortale dall'ultimo controllo di stato
        self.controllo_dal = None       # il numero del turno da cui lo controlla chi lo controlla (302.6)
        self.tavolo = None              # il tavolo che calcola le sue caratteristiche (forza, costituzione, parole)

    @property
    def carta(self):
        """Le caratteristiche che il resto del motore legge: la carta fisica, oppure, se in campo c'e' un effetto che
        copia (613.1a, 707.2) o che cambia i tipi (613.1d, 205.1b), la carta dopo i livelli 1 e 4: un permanente
        diventato una copia, un artefatto diventato creatura. Lo calcola il tavolo (effetti.TavoloEffetti.vista_carta);
        senza effetti di quei livelli e' la carta fisica, come prima."""
        t = self.tavolo
        if t is None or not (t._bassi or self.__dict__.get("come_avventura") or self.__dict__.get("come_retro")): return self.fisica   # 716.3b, 712.8b
        return t.vista_carta(self)

    @carta.setter
    def carta(self, c): self._carta = c

    @property
    def fisica(self):
        """Il pezzo fisico, senza effetti, con la faccia che e' in su (712.6c-d: un permanente a due facce trasformato ha le
        caratteristiche della faccia dietro, `_retro`); 400.7: il nuovo oggetto di un cambio di zona e' la carta (`_carta`)."""
        return self.__dict__.get("_retro") or self._carta

    @property
    def proprietario(self): return self._carta.proprietario

    @property
    def nome(self): return self.carta.nome

    def __lt__(self, altro): return self.n < altro.n     # il grimorio confronta le carte guardate con sorted()

    def __repr__(self): return f"{self.carta.nome}#{self.n}"


@dataclass
class Evento:
    """tipo: «zona» (cambio di zona; da=None per una pedina appena creata), «resta» (un cambio di zona che le regole
    impediscono, la regola in causa), «cessa» (pedina, 704.5d), «vite», «tappa», «stappa», «controllo», «perde»."""
    n: int
    tipo: str
    carta: object = None
    da: str = None
    a: str = None
    vecchio: int = None
    nuovo: int = None
    giocatore: int = None
    quanto: int = None
    causa: str = ""

    def chiave(self):
        t = astuple(self)
        return t[:2] + ((self.carta.n, self.carta.nome) if self.carta else None,) + t[3:]


class Giocatore:
    def __init__(self, i, nome, vite):
        self.i, self.nome, self.vite = i, nome, vite        # 103.4, 119.1
        self.grimorio = None                                # il Grimorio del passo 1, cima all'indice 0
        self.mano, self.cimitero = [], []                   # cimitero: la cima e' l'ultimo (404.1)
        self.mano_massima = 7                               # 402.2, la pulizia la fa turno.py (514.1)
        self.perso, self.perche = False, None
        self.riserva = Riserva()                            # la riserva di mana per tipo (106.1b, 106.4): mana.py
        self.terre_giocate = 0                              # in questo turno (305.2)


class Tavolo:
    """mazzi: una lista per giocatore di voci «nome» o (nome, riga del tipo). Ogni mazzo diventa il grimorio (401.1) e si
    mescola (103.3) col seme del giocatore, ricavato dal seme del tavolo: stesso seme e stesse mosse, stessa partita."""

    _bassi = 0                          # quante fonti di effetti dei livelli 1 e 4 (613.1a, 613.1d): qui nessuna

    def vista_carta(self, ogg):
        """Le caratteristiche dopo i livelli 1 e 4: il passo 7 (effetti.TavoloEffetti). Qui la carta fisica."""
        return ogg.fisica

    def __init__(self, mazzi, nomi=None, seme=None, vite=20):
        self.seme = int(seme) if seme is not None else secrets.randbits(64)
        semi = np.random.default_rng(self.seme).integers(0, 2 ** 63 - 1, size=len(mazzi))
        self._oggetti, self._carte, self._eventi = itertools.count(1), itertools.count(1), itertools.count(1)
        self.campo, self.pila, self.esilio, self.comando = [], [], [], []
        self.eventi, self.giocatori, self.carte_iniziali = [], [], []
        self.finita, self.vincitore = False, None
        self.primo = None                   # chi comincia (103.1): lo decide Motore_Partita/inizio.py
        self.turno_numero = 0               # il turno in corso, contato da 1 (lo fa avanzare Motore_Partita/turno.py)
        for i, mazzo in enumerate(mazzi):
            g = Giocatore(i, nomi[i] if nomi and i < len(nomi) else f"G{i + 1}", vite)
            oggetti = []
            for voce in mazzo:
                nome, tipo, car = (voce, BASE.get(voce, ""), None) if isinstance(voce, str) else (tuple(voce) + (None,))[:3]
                c = Carta(next(self._carte), nome, tipo, i, car=car)
                self.carte_iniziali.append(c)
                o = Oggetto(next(self._oggetti), c, "grimorio")
                o.tavolo = self
                oggetti.append(o)
            g.grimorio = Grimorio(oggetti, seme=int(semi[i]))
            self.giocatori.append(g)
        self.ultimo_id_iniziale = len(self.carte_iniziali)
        self._lotto = 0                     # quanti «insieme» aperti: gli eventi di un'azione simultanea (704.3, 510.2)

    # ------------------------------------------------------------------ le zone
    def lista(self, zona, i=None):
        """La lista viva di una zona (il grimorio la ricrea a ogni macina o scry: non tenerla da parte)."""
        if zona in DEL_GIOCATORE:
            g = self.giocatori[i]
            return g.grimorio.carte if zona == "grimorio" else getattr(g, zona)
        return getattr(self, zona)

    def tutti(self):
        """(zona, giocatore della zona o None, oggetto) per ogni oggetto del tavolo."""
        for g in self.giocatori:
            for z in DEL_GIOCATORE:
                for o in self.lista(z, g.i): yield z, g.i, o
        for z in CONDIVISE:
            for o in self.lista(z): yield z, None, o

    def controllore_di(self, ogg):
        return ogg.controllore if ogg.controllore is not None else ogg.proprietario     # 108.4a

    # ------------------------------------------------------------------ le caratteristiche
    def parole_di(self, ogg):
        """Le parole chiave stampate (702.1): il passo 7 (effetti.TavoloEffetti) le calcola dopo gli effetti continui."""
        return parole_stampate(ogg)

    def forza_di(self, ogg):
        return ogg.carta.car["forza"]                                                    # 208.1

    def costituzione_di(self, ogg):
        return ogg.carta.car["costituzione"]

    @contextlib.contextmanager
    def insieme(self):
        """Le azioni dentro questo blocco succedono tutte insieme (704.3, 510.2, 608.2f): il passo 7 ci legge gli inneschi
        con lo sguardo all'indietro (603.10a). Qui non cambia niente."""
        self._lotto += 1
        if self._lotto == 1: self._lotto_inizio()
        try: yield
        finally:
            self._lotto -= 1
            if self._lotto == 0: self._lotto_fine()

    def _lotto_inizio(self): pass

    def _lotto_fine(self): pass

    # ------------------------------------------------------------------ il cambio di zona
    def _evento(self, tipo, **kw):
        e = Evento(next(self._eventi), tipo, **kw)
        self.eventi.append(e)
        self._dopo_evento(e)
        return e

    def _dopo_evento(self, e):
        """Il gancio degli inneschi (603.2, il passo 7). Qui non fa niente."""

    def _nuovo_id(self, vecchio):
        return next(self._oggetti)

    def _di_chi(self, ogg, verso, chi):
        """La zona di quale giocatore riceve l'oggetto: sempre il proprietario (400.3)."""
        return ogg.proprietario

    def _togli(self, ogg):
        lst = self.lista(ogg.zona, ogg.proprietario if ogg.zona in DEL_GIOCATORE else None)
        for k, x in enumerate(lst):
            if x is ogg:
                del lst[k]
                return
        raise RuntimeError(f"{ogg} non e' in {ogg.zona}")

    def _arriva(self, ogg, da, verso, chi, posizione, causa):
        """L'oggetto (gia' tolto da dov'era) arriva in «verso» come oggetto nuovo (400.7)."""
        if verso in CON_CONTROLLORE: ctrl = ogg.proprietario if chi is None else chi    # 110.2a, 405.4
        else: ctrl = None                                                              # 108.4
        nuovo = Oggetto(self._nuovo_id(ogg), ogg._carta, verso, ctrl)                  # 400.7, 712.6a: la carta, la faccia davanti
        nuovo.tavolo = self
        if verso == "pila" and ogg.__dict__.get("come_retro"): nuovo.come_retro = True    # 712.8b: lanciata con la faccia dietro
        if verso == "campo" and (ogg.__dict__.get("_entra_retro") or (da == "pila" and ogg.__dict__.get("come_retro"))):
            r_ = ogg._carta.retro()                                                    # 712.10, 712.11a: entra con la faccia
            if r_ is not None and not r_.tipi & {"instant", "sorcery"}: nuovo._retro = r_   # dietro in su
        if verso == "campo":
            nuovo.controllo_dal = self.turno_numero                                    # 302.6
            if "planeswalker" in ogg.fisica.tipi: nuovo.segnalini["fedelta"] = ogg.fisica.car.get("fedelta", 0)   # 306.5b
        dest = self._di_chi(ogg, verso, chi)
        if verso == "grimorio":
            gr = self.giocatori[dest].grimorio
            if posizione == "mescola": gr.mescola_dentro([nuovo])
            else: gr.metti(nuovo, posizione or "cima")
        elif verso in DEL_GIOCATORE: self.lista(verso, dest).append(nuovo)
        else: self.lista(verso).append(nuovo)
        ogg.vivo, ogg.diventato = False, nuovo.n
        self._evento("zona", carta=ogg.carta, da=da, a=verso, vecchio=ogg.n, nuovo=nuovo.n,
                     giocatore=self.controllore_di(nuovo), causa=causa)
        return nuovo

    def sposta(self, ogg, verso, chi=None, posizione=None, causa=""):
        """Sposta l'oggetto nella zona «verso» (chi: chi lo mette in campo o lo lancia; posizione nel grimorio: «cima»,
        «fondo», N-esima dall'alto, «mescola»). -> l'oggetto nuovo; lo stesso se le regole lo tengono fermo; None se
        l'oggetto non esiste piu' (400.7: e' cambiato di zona nel frattempo)."""
        if verso not in ZONE: raise ValueError(f"zona sconosciuta: {verso}")
        if not ogg.vivo: return None
        if ogg.carta.pedina and ogg.zona != "campo":                                   # 111.8
            self._evento("resta", carta=ogg.carta, da=ogg.zona, a=verso, vecchio=ogg.n, causa="111.8")
            return ogg
        if verso == "campo" and ogg.carta.tipi & {"instant", "sorcery"}:              # 400.4a
            self._evento("resta", carta=ogg.carta, da=ogg.zona, a=verso, vecchio=ogg.n, causa="400.4a")
            return ogg
        if verso == ogg.zona and verso != "esilio":                                   # 400.8: solo l'esilio
            raise ValueError(f"{ogg} e' gia' in {verso}: non e' un cambio di zona")
        da = ogg.zona
        self._togli(ogg)
        return self._arriva(ogg, da, verso, chi, posizione, causa)

    # ------------------------------------------------------------------ i verbi sugli oggetti
    def metti_in_campo(self, ogg, chi=None, causa=""):
        return self.sposta(ogg, "campo", chi=chi, causa=causa)

    def metti_in_pila(self, ogg, chi=None, causa="405.1"):
        return self.sposta(ogg, "pila", chi=chi, causa=causa)

    def scarta(self, ogg, causa="701.9a"):
        return self.sposta(ogg, "cimitero", causa=causa) if ogg.vivo and ogg.zona == "mano" else None

    def distruggi(self, ogg, causa="701.8a"):
        return self.sposta(ogg, "cimitero", causa=causa) if ogg.vivo and ogg.zona == "campo" else None

    def sacrifica(self, ogg, chi, causa="701.21a"):
        """Solo un permanente che chi sacrifica controlla (701.21a)."""
        if not (ogg.vivo and ogg.zona == "campo" and ogg.controllore == chi): return None
        return self.sposta(ogg, "cimitero", causa=causa)

    def esilia(self, ogg, a_faccia_in_giu=False, causa="701.13a"):
        nuovo = self.sposta(ogg, "esilio", causa=causa)
        if nuovo is not None and nuovo.zona == "esilio": nuovo.a_faccia_in_giu = a_faccia_in_giu
        return nuovo

    def rimbalza(self, ogg, causa=""):
        """In mano: quella del proprietario, chiunque lo controlli (400.3)."""
        return self.sposta(ogg, "mano", causa=causa)

    def crea_pedina(self, chi, nome, tipo, causa="111.2"):
        c = Carta(next(self._carte), nome, tipo, chi, pedina=True)
        o = Oggetto(next(self._oggetti), c, "campo", chi)
        o.tavolo = self
        o.controllo_dal = self.turno_numero
        self.campo.append(o)
        self._evento("zona", carta=c, da=None, a="campo", nuovo=o.n, giocatore=chi, causa=causa)
        return o

    def tappa(self, ogg):
        """701.26a: solo un permanente stappato si puo' tappare. -> True se e' successo."""
        if not (ogg.vivo and ogg.zona == "campo") or ogg.tappato: return False
        ogg.tappato = True
        self._evento("tappa", carta=ogg.carta, vecchio=ogg.n, giocatore=ogg.controllore)
        return True

    def stappa(self, ogg):
        """701.26b: solo un permanente tappato si puo' stappare."""
        if not (ogg.vivo and ogg.zona == "campo") or not ogg.tappato: return False
        ogg.tappato = False
        self._evento("stappa", carta=ogg.carta, vecchio=ogg.n, giocatore=ogg.controllore)
        return True

    def prendi_controllo(self, ogg, chi, causa=""):
        """Un effetto che cambia il controllore (110.2 «by default»): non e' un cambio di zona, l'oggetto resta lo stesso."""
        if not (ogg.vivo and ogg.zona in CON_CONTROLLORE): return False
        if ogg.controllore != chi: ogg.controllo_dal = self.turno_numero              # 302.6: il controllo riparte
        ogg.controllore = chi
        self._evento("controllo", carta=ogg.carta, vecchio=ogg.n, giocatore=chi, causa=causa)
        return True

    # ------------------------------------------------------------------ i verbi sul grimorio (il passo 1 sotto)
    def mano_iniziale(self, i, n=7, mulligan=None, fondo=None):
        """Mulligan London (103.5) dal grimorio del passo 1, poi le carte che restano arrivano in mano. -> (mano, k)."""
        gr = self.giocatori[i].grimorio
        mano, k = gr.mano_iniziale(n, mulligan)
        if k: mano = gr.fondo_mulligan(mano, k, fondo)
        return [self._arriva(o, "grimorio", "mano", None, None, "103.5") for o in mano], k

    def pesca(self, i, n=1, causa="121.1"):
        """Una carta alla volta (121.2). Da un grimorio vuoto il grimorio segna il tentativo (121.4): lo legge 704.5b."""
        gr, out = self.giocatori[i].grimorio, []
        for _ in range(n):
            presa = gr.pesca(1)
            if not presa: break
            out.append(self._arriva(presa[0], "grimorio", "mano", None, None, causa))
        return out

    def macina(self, i, n, causa="701.17a"):
        return [self._arriva(o, "grimorio", "cimitero", None, None, causa) for o in self.giocatori[i].grimorio.macina(n)]

    def scry(self, i, n, decidi):
        return self.giocatori[i].grimorio.scry(n, decidi)

    def surveil(self, i, n, decidi, causa="701.25a"):
        via = self.giocatori[i].grimorio.surveil(n, decidi)
        return [self._arriva(o, "grimorio", "cimitero", None, None, causa) for o in via]

    def cerca(self, i, predicato, quante=1, verso="mano", chi=None, causa="701.23"):
        """Cerca nel grimorio (701.23), mette le trovate in «verso», il grimorio si rimescola (701.24b)."""
        trovate = self.giocatori[i].grimorio.cerca(predicato, quante, mescola=True)
        out = []
        for o in trovate:
            if verso == "campo" and o.carta.tipi & {"instant", "sorcery"}:      # 400.4a: resta nel grimorio
                self.giocatori[i].grimorio.mescola_dentro([o])
                self._evento("resta", carta=o.carta, da="grimorio", a="campo", vecchio=o.n, causa="400.4a")
            else: out.append(self._arriva(o, "grimorio", verso, chi, None, causa))
        return out

    # ------------------------------------------------------------------ le vite
    def guadagna(self, i, n, causa=""):
        if n <= 0: return 0                                                  # 119.9: 0 non e' un guadagno
        self.giocatori[i].vite += n
        self._evento("vite", giocatore=i, quanto=n, causa=causa)
        return n

    def perdi(self, i, n, causa=""):
        if n <= 0: return 0
        self.giocatori[i].vite -= n
        self._evento("vite", giocatore=i, quanto=-n, causa=causa)
        return n

    def paga_vite(self, i, n, causa="119.4"):
        """Si paga solo se le vite bastano (119.4); pagare e' perdere."""
        if n > 0 and self.giocatori[i].vite < n: return False
        self.perdi(i, n, causa)
        return True

    def imposta_vite(self, i, n, causa="119.5"):
        d = n - self.giocatori[i].vite
        return self.guadagna(i, d, causa) if d > 0 else -self.perdi(i, -d, causa)

    # ------------------------------------------------------------------ il danno (120)
    def infliggi(self, fonte, danni, causa="120.2b"):
        """La fonte infligge i suoi danni tutti insieme: danni = [(destinatario, n)], destinatario l'indice di un giocatore
        o un oggetto in campo. Secondo 120.3: al giocatore fa perdere vite (120.3a), al planeswalker toglie segnalini
        fedelta' (120.3c, 306.8), sulla creatura resta segnato (120.3e, 120.6); da una fonte con tocco mortale la creatura
        lo ricorda fino al prossimo controllo di stato (702.2b, 704.5h); da una fonte con legame vitale chi la controlla
        (o il proprietario, se non ha controllore) guadagna altrettante vite, un guadagno per fonte (120.3f, 702.15b,
        702.15e). Il danno non distrugge niente: lo fanno le azioni di stato (120.5). 0 danni non sono danno (120.8); a
        un oggetto che non e' creatura, planeswalker o battaglia non si infliggono (120.1a). Le prevenzioni e le
        sostituzioni (120.4b-c, 614, 615) sono il passo 7. -> il totale inflitto."""
        ps, totale = parole(fonte), 0
        for a, n in danni:
            if n <= 0: continue                                                                    # 120.8
            if isinstance(a, numbers.Integral):
                if self.giocatori[a].perso: continue
                self._evento("danno", carta=fonte.carta, vecchio=fonte.n, a=f"G{a + 1}", giocatore=a, quanto=n, causa=causa)
                self.perdi(a, n, causa="120.3a")
            else:
                tipi = a.carta.tipi
                if not (a.vivo and a.zona == "campo") or not tipi & {"creature", "planeswalker", "battle"}: continue   # 120.1a
                if "battle" in tipi: raise NonCoperto(f"120.3h, 310: il danno a una battaglia ({a}) non e' coperto")
                self._evento("danno", carta=fonte.carta, vecchio=fonte.n, a=repr(a), nuovo=a.n, giocatore=a.controllore,
                             quanto=n, causa=causa)
                if "planeswalker" in tipi:                                                         # 120.3c, 306.8
                    tolti = min(n, a.segnalini["fedelta"])
                    a.segnalini["fedelta"] -= tolti
                    self._evento("segnalini", carta=a.carta, vecchio=a.n, giocatore=a.controllore, a="fedelta",
                                 quanto=-tolti, causa="120.3c")
                if "creature" in tipi:                                                             # 120.3e
                    a.danno += n
                    if "deathtouch" in ps: a.toccato_da_morte = True                               # 702.2b
            totale += n
        if totale and "lifelink" in ps:                                                            # 120.3f, 702.15b
            self.guadagna(fonte.controllore if fonte.controllore is not None else fonte.proprietario, totale, causa="702.15b")
        return totale

    # ------------------------------------------------------------------ le azioni di stato di questo passo
    def _ha_costituzione(self, ogg):
        """Una creatura senza costituzione stampata che ne ha una da un effetto (613.4b): la vede il tavolo coi livelli."""
        return False

    def _parole_per_stato(self, ogg):
        return parole(ogg)

    def azioni_di_stato(self):
        """704.3: si guardano tutte le condizioni, si fanno tutte insieme, e si ricomincia finche' non ce n'e' piu'.
        Qui 704.5a, 704.5b, 704.5d, dal passo 3 704.5f (costituzione 0) e 704.5i (fedelta' 0), dal passo 6 704.5g (danno
        letale) e 704.5h (tocco mortale), che l'indistruttibile ignora (702.12b); le altre arrivano coi passi che le rendono
        possibili. A partita finita non succede piu' niente (104.1: finisce subito). -> cosa e' successo."""
        fatte = []
        if self.finita: return fatte
        while True:
            giro = []
            for g in self.giocatori:
                if g.perso: continue
                if g.vite <= 0: giro.append(("perde", g, "704.5a"))
                elif g.grimorio.perso: giro.append(("perde", g, "704.5b"))
            for z, _, o in self.tutti():
                if o.carta is not None and o.carta.pedina and z != "campo": giro.append(("cessa", o, "704.5d"))   # 405.1: un'abilita' non ha carta
            for o in self.campo:
                tipi, car = o.carta.tipi, o.carta.car
                creatura = "creature" in tipi and ("costituzione" in car or self._ha_costituzione(o))   # 208.3: anche diventata creatura
                c = costituzione(o) if creatura else None
                if creatura and c <= 0: giro.append(("muore", o, "704.5f"))
                elif creatura and 0 < c <= o.danno \
                        and "indestructible" not in self._parole_per_stato(o): giro.append(("muore", o, "704.5g"))  # 120.6, 702.12b
                elif creatura and o.toccato_da_morte and "indestructible" not in self._parole_per_stato(o):
                    giro.append(("muore", o, "704.5h"))                                                # 702.2b, 702.12b
                elif "planeswalker" in tipi and o.segnalini["fedelta"] <= 0 and self._muore_a_fedelta_zero(o): giro.append(("muore", o, "704.5i"))
            giro += self._stato_altre()                                                               # il passo 7: 704.5q
            for o in self.campo: o.toccato_da_morte = False                                            # 704.5h: «since the last time»
            if not giro: break
            with self.insieme():                                                                       # 704.3: tutte insieme
                for cosa, chi, regola in giro:
                    if cosa == "perde":
                        chi.perso, chi.perche = True, regola
                        self._evento("perde", giocatore=chi.i, causa=regola)
                    elif cosa == "muore":
                        self.sposta(chi, "cimitero", causa=regola)
                    elif cosa == "cessa":
                        self._togli(chi); chi.vivo = False
                        self._evento("cessa", carta=chi.carta, da=chi.zona, vecchio=chi.n, causa=regola)
                    else: self._fai_stato(cosa, chi, regola)
            fatte += [(c, getattr(x, "i", x), r) for c, x, r in giro]
            if len(self.giocatori) > 1 and sum(1 for g in self.giocatori if not g.perso) <= 1:
                break                                      # 104.1, 104.2a: la partita e' finita subito, niente altro giro (704.3)
        restano = [g for g in self.giocatori if not g.perso]
        if len(self.giocatori) > 1 and len(restano) <= 1 and not self.finita:
            self.finita = True
            self.vincitore = restano[0].i if restano else None              # 104.2a; 104.4a: tutti insieme, pari
        return fatte

    def _muore_a_fedelta_zero(self, o):
        """704.5i: il planeswalker a 0 fedelta' va nel cimitero (il passo 7 legge le eccezioni scritte sulle carte)."""
        return True

    def _stato_altre(self):
        """Le azioni di stato che arrivano col passo 7 (704.5q): [(cosa, oggetto, regola)]."""
        return []

    def _fai_stato(self, cosa, chi, regola):
        raise RuntimeError(f"azione di stato sconosciuta: {cosa} ({regola})")

    # ------------------------------------------------------------------ cosa si vede
    def vista(self, i):
        """Cio' che il giocatore i puo' vedere (400.2): la propria mano per nome, quella degli altri contata (402.3), i
        grimori contati (401.3), le zone pubbliche per nome; le carte a faccia in giu' non si vedono (406.3)."""
        nomi = lambda lst: ["?" if o.a_faccia_in_giu else o.nome for o in lst]
        out = {"giocatori": [{"nome": g.nome, "vite": g.vite, "grimorio": len(g.grimorio),
                              "mano": [o.nome for o in g.mano] if g.i == i else len(g.mano),
                              "cimitero": nomi(g.cimitero)} for g in self.giocatori]}
        for z in CONDIVISE: out[z] = nomi(self.lista(z))
        return out

    def stato(self):
        """Una fotografia confrontabile del tavolo (per dire che due partite sono la stessa)."""
        def f(lst): return tuple((o.n, o.nome, o.controllore, o.tappato) for o in lst)
        return (tuple((g.vite, g.perso, f(g.grimorio.carte), f(g.mano), f(g.cimitero)) for g in self.giocatori),
                tuple(f(self.lista(z)) for z in CONDIVISE), self.finita, self.vincitore)


# ====================================================================== il controllo degli invarianti
def controlla(t):
    """-> gli errori (lista vuota = sano): ogni carta del mazzo esattamente una volta sul tavolo; nessun oggetto spento
    in una zona; la zona dell'oggetto e' quella dove sta; le zone di un giocatore contengono solo cose sue (400.3); il
    controllore c'e' solo in campo e in pila (108.4); nessun numero di oggetto ripetuto; ogni cambio di zona fa un oggetto
    con un numero mai usato (400.7)."""
    err, visti = [], {}
    for z, i, o in t.tutti():
        if not o.vivo: err.append(f"{o} e' spento ma sta ancora in {z}")
        if o.zona != z: err.append(f"{o} dice {o.zona} ma sta in {z}")
        if z in DEL_GIOCATORE and o.proprietario != i:
            err.append(f"{o} nel {z} di G{i + 1}, ma e' di G{o.proprietario + 1} (400.3)")
        if (o.controllore is not None) != (z in CON_CONTROLLORE): err.append(f"{o} in {z} col controllore {o.controllore} (108.4)")
        if o.n in visti: err.append(f"il numero {o.n} e' di due oggetti: {visti[o.n]} e {o}")
        visti[o.n] = o
    conta = Counter(o.carta.n for o in visti.values() if o.carta is not None)     # un'abilita' in pila non e' una carta (405.1)
    for c in t.carte_iniziali:
        if conta[c.n] != 1: err.append(f"{c.nome} (carta {c.n} di G{c.proprietario + 1}) e' sul tavolo {conta[c.n]} volte")
    ultimo = t.ultimo_id_iniziale
    for e in t.eventi:
        if e.tipo != "zona" or getattr(e, "storia", False): continue        # la storia letta da un log non e' un cambio di zona qui
        if e.nuovo == e.vecchio: err.append(f"{e.carta} cambia zona ({e.da} -> {e.a}) e resta lo stesso oggetto (400.7)")
        elif e.nuovo <= ultimo: err.append(f"{e.carta} cambia zona e prende un numero gia' usato ({e.nuovo})")
        ultimo = max(ultimo, e.nuovo)
    return err


# ====================================================================== le prove
COMPOSIZIONE = {"creature": 15, "artifact": 3, "enchantment": 3, "planeswalker": 2}   # le 23 carte non terra


def mazzo_draft_generico(terre=17, totale=40, composizione=None):
    """Il mazzo da draft finto di questa fase (Autore, 14 ott 2026: «non usiamo le carte reali», poi «le carte sono
    creature, incantesimi, artefatti, planeswalker, tutti permanenti, a costo 1»). «terre» terre generiche: tipo Land
    senza tipo base, quindi senza mana proprio (305.6); gli si da' «{T}: Add {C}» (car mana, come Wastes o le terre
    incolori di FRA): un mana deve avere un tipo (106.1b, 106.5) e l'incolore paga il generico (107.4b). Il resto sono
    permanenti vuoti a costo {1}: creature 1/1, artefatti, incantesimi, planeswalker con fedelta' 1 (con 0 morirebbero
    subito, 704.5i). La ripartizione e' COMPOSIZIONE, scalata se il totale cambia. 40 e' il minimo del Limited (100.2b)."""
    comp = dict(composizione or COMPOSIZIONE)
    resto = totale - terre
    if sum(comp.values()) != resto:                       # si scala, e lo scarto va alle creature
        scala = resto / sum(comp.values())
        comp = {k: int(v * scala) for k, v in comp.items()}
        comp["creature"] += resto - sum(comp.values())
    nomi = {"creature": ("Creatura", "Creature", {"costo": "{1}", "forza": 1, "costituzione": 1}),
            "artifact": ("Artefatto", "Artifact", {"costo": "{1}"}),
            "enchantment": ("Incantesimo", "Enchantment", {"costo": "{1}"}),
            "planeswalker": ("Planeswalker", "Planeswalker", {"costo": "{1}", "fedelta": 1}),
            # dal passo 5 (pila.py): istantanei e stregonerie vuoti, senza testo; risolti vanno nel cimitero (304.2, 307.2)
            "instant": ("Istantaneo", "Instant", {"costo": "{1}"}),
            "sorcery": ("Stregoneria", "Sorcery", {"costo": "{1}"})}
    mazzo = [("Terra", "Land", {"mana": ["{C}"]})] * terre
    for tipo, k in comp.items(): mazzo += [nomi[tipo]] * k
    return mazzo


# il mazzo finto a due colori del passo 4: (nome, riga del tipo, caratteristiche, copie). I costi coprono i simboli che
# FRA usa (colori, ibridi, ibridi monocolore, X) piu' un phyrexiano; le terre sono base (305.6) e doppie «{G} o {W}».
COMPOSIZIONE_COLORI = (
    ("Forest", BASE["Forest"], None, 8),
    ("Plains", BASE["Plains"], None, 7),
    ("Terra doppia", "Land", {"mana": ["{G}", "{W}"]}, 2),
    ("Creatura W", "Creature", {"costo": "{W}", "forza": 1, "costituzione": 1}, 3),
    ("Creatura G", "Creature", {"costo": "{G}", "forza": 1, "costituzione": 1}, 3),
    ("Creatura 1G", "Creature", {"costo": "{1}{G}", "forza": 2, "costituzione": 2}, 2),
    ("Creatura GW", "Creature", {"costo": "{G}{W}", "forza": 2, "costituzione": 2}, 3),
    ("Creatura G/W", "Creature", {"costo": "{G/W}", "forza": 1, "costituzione": 1}, 3),
    ("Creatura 2/W", "Creature", {"costo": "{2/W}", "forza": 1, "costituzione": 1}, 2),
    ("Creatura XG", "Creature", {"costo": "{X}{G}", "forza": 1, "costituzione": 1}, 2),
    ("Creatura W/P", "Creature", {"costo": "{W/P}", "forza": 1, "costituzione": 1}, 1),
    ("Artefatto", "Artifact", {"costo": "{1}"}, 1),
    ("Incantesimo W", "Enchantment", {"costo": "{1}{W}"}, 2),
    ("Planeswalker GW", "Planeswalker", {"costo": "{G}{W}", "fedelta": 1}, 1))


def mazzo_draft_colori(composizione=COMPOSIZIONE_COLORI):
    """Il mazzo da draft finto a due colori (verde e bianco), 17 terre su 40: per le prove del mana (passo 4)."""
    mazzo = []
    for nome, tipo, car, copie in composizione: mazzo += [(nome, tipo, car)] * copie
    return mazzo


def mazzi_di_prova():
    return [mazzo_draft_generico(), mazzo_draft_generico()]


def passeggiata(T, seme, passi, mazzi, controlla_ogni=1):
    """Una partita senza regole di turno: mosse a caso fra tutti i verbi del tavolo, il controllo degli invarianti dopo
    ogni mossa. -> (tavolo, errori al primo controllo rosso o [], conteggio delle mosse fatte)."""
    t, rng, fatte = T(mazzi, seme=seme), np.random.default_rng(seme + 1), Counter()
    def uno(lst):
        lst = list(lst)
        return lst[int(rng.integers(0, len(lst)))] if lst else None
    for i in range(2): t.mano_iniziale(i, mulligan=lambda m, k: k < int(rng.integers(0, 2)))
    for p in range(passi):
        g, op = int(rng.integers(0, 2)), int(rng.integers(0, 17))
        G, fatto = t.giocatori[g], None
        if op == 0: fatto = t.pesca(g) and "pesca"
        elif op == 1 and G.mano: fatto = t.metti_in_campo(uno(G.mano), chi=g) and "in campo"
        elif op == 2 and G.mano: fatto = t.metti_in_pila(uno(G.mano), chi=g) and "in pila"
        elif op == 3 and t.pila:
            o = t.pila[-1]
            fatto = t.sposta(o, "cimitero" if o.carta.tipi & {"instant", "sorcery"} else "campo", chi=o.controllore) and "risolve"
        elif op == 4 and t.campo: fatto = t.distruggi(uno(t.campo)) and "distruggi"
        elif op == 5 and t.campo: fatto = t.sacrifica(uno(t.campo), g) and "sacrifica"
        elif op == 6: fatto = (o := uno(o for _, _, o in t.tutti())) and t.esilia(o) and "esilia"
        elif op == 7 and t.esilio: fatto = t.esilia(uno(t.esilio)) and "esilia dall'esilio"
        elif op == 8 and t.campo: fatto = t.rimbalza(uno(t.campo)) and "rimbalza"
        elif op == 9 and G.mano: fatto = t.scarta(uno(G.mano)) and "scarta"
        elif op == 10: fatto = t.macina(g, int(rng.integers(1, 4))) and "macina"
        elif op == 11: fatto = t.surveil(g, 2, lambda v: (v[:1], v[1:])) and "surveil"
        elif op == 12: fatto = t.cerca(g, lambda o: "land" in o.carta.tipi, 1, verso=uno(["mano", "campo"]), chi=g) and "cerca"
        elif op == 13: fatto = t.crea_pedina(g, "Spirit", "Token Creature — Spirit") and "pedina"
        elif op == 14:
            o = uno([o for o in G.mano + G.cimitero + t.campo])
            pos = uno(["cima", "fondo", "mescola", int(rng.integers(1, 60))])
            fatto = o is not None and t.sposta(o, "grimorio", posizione=pos) and "nel grimorio"
        elif op == 15 and t.campo:
            o = uno(t.campo)
            fatto = (t.prendi_controllo(o, 1 - o.controllore) if rng.random() < 0.3 else (t.tappa(o) or t.stappa(o))) and "controllo o tappa"
        elif op == 16:
            t.azioni_di_stato(); fatto = "azioni di stato"
        if fatto: fatte[fatto] += 1
        if p % controlla_ogni == 0 or p == passi - 1:
            e = controlla(t)
            if e: return t, e, fatte
    t.azioni_di_stato()
    return t, controlla(t), fatte


def prove_regole(T):
    """Le regole una per una, su un tavolo di classe T. -> [(nome, ok, dettaglio)]."""
    casi = []
    def caso(nome, ok, det=""): casi.append((nome, bool(ok), det))
    orso = ("Orso", "Creature — Bear")
    def nuovo(seme=1, **kw):
        return T([[orso, ("Incanto", "Enchantment"), ("Fulmine", "Instant"), ("Rito", "Sorcery")] + ["Forest"] * 6,
                  [orso, ("Orso2", "Creature — Bear")] + ["Island"] * 8], seme=seme, **kw)
    def prendi(t, i, nome):
        o = next(o for o in t.giocatori[i].grimorio.carte if o.nome == nome)
        t._togli(o)
        return t._arriva(o, "grimorio", "mano", None, None, "prova")

    # 400.7 e 403.4: rimbalzare e rigiocare fa un oggetto nuovo; il riferimento vecchio non trova piu' niente
    t = nuovo(); o = t.metti_in_campo(prendi(t, 0, "Orso"), chi=0)
    m = t.rimbalza(o); o2 = t.metti_in_campo(m, chi=0)
    caso("cambiare zona fa un oggetto nuovo (400.7)", len({o.n, m.n, o2.n}) == 3 and not o.vivo and not m.vivo and o2.vivo,
         f"{o} -> {m} -> {o2}")
    caso("il riferimento all'oggetto vecchio non trova niente (400.7)", t.distruggi(o) is None and o2 in t.campo)
    # 400.8 / 406.7
    t = nuovo(); e1 = t.esilia(prendi(t, 0, "Orso")); e2 = t.esilia(e1)
    caso("esiliare dall'esilio fa un oggetto nuovo, sempre in esilio (400.8, 406.7)",
         e2 is not None and e2.n != e1.n and t.esilio == [e2] and not e1.vivo)
    # 400.3: il permanente rubato torna al proprietario
    t = nuovo(); o = t.metti_in_campo(prendi(t, 0, "Orso"), chi=0); t.prendi_controllo(o, 1)
    c = t.distruggi(o)
    caso("distrutto mentre lo controlla l'altro: va nel cimitero del proprietario (400.3)",
         c in t.giocatori[0].cimitero and not t.giocatori[1].cimitero)
    t = nuovo(); o = t.metti_in_campo(prendi(t, 0, "Orso"), chi=1)
    m = t.rimbalza(o)
    caso("rimbalzato mentre lo controlla l'altro: va nella mano del proprietario (400.3)",
         m in t.giocatori[0].mano and m not in t.giocatori[1].mano)
    t = nuovo(); o = t.metti_in_campo(prendi(t, 0, "Orso"), chi=1); g = t.sposta(o, "grimorio", chi=1, posizione="cima")
    caso("messo in cima al grimorio da chi lo controlla: e' il grimorio del proprietario (400.3)",
         t.giocatori[0].grimorio.carte[0] is g and len(t.giocatori[1].grimorio) == 10)
    # 400.4a
    t = nuovo(); r = prendi(t, 0, "Rito"); r2 = t.metti_in_campo(r, chi=0)
    f = prendi(t, 0, "Fulmine"); f2 = t.metti_in_campo(f, chi=0)
    caso("istantanei e stregonerie non entrano in campo: restano dove sono (400.4a)",
         r2 is r and f2 is f and r.vivo and f.vivo and r in t.giocatori[0].mano and not t.campo)
    # 110.2, 110.2a, 108.4, 108.4a, 405.4
    t = nuovo(); o = prendi(t, 0, "Orso")
    caso("in mano non ha controllore; chiesto, si risponde col proprietario (108.4, 108.4a)",
         o.controllore is None and t.controllore_di(o) == 0)
    p = t.metti_in_campo(o, chi=1)
    caso("in campo lo controlla chi ce l'ha messo, il proprietario non cambia (110.2, 110.2a)",
         p.controllore == 1 and p.proprietario == 0)
    s = t.metti_in_pila(prendi(t, 0, "Fulmine"), chi=0)
    caso("in pila lo controlla chi l'ha lanciato (405.4)", s.controllore == 0 and t.pila == [s])
    # 110.5b, 701.26a-b
    t = nuovo(); o = t.metti_in_campo(prendi(t, 0, "Orso"), chi=0)
    seq = [o.tappato, t.tappa(o), t.tappa(o), t.stappa(o), t.stappa(o)]
    caso("entra stappato; tappare due volte o stappare due volte non si puo' (110.5b, 701.26a-b)",
         seq == [False, True, False, True, False], str(seq))
    t.tappa(o); o2 = t.metti_in_campo(t.rimbalza(o), chi=0)
    caso("tappato, rimbalzato e rigiocato: rientra stappato (110.5b, 400.7)", o.tappato and not o2.tappato)
    # 701.21a, 701.8a
    t = nuovo(); o = t.metti_in_campo(prendi(t, 0, "Orso"), chi=0)
    caso("non si sacrifica cio' che controlla un altro (701.21a)", t.sacrifica(o, 1) is None and o.vivo)
    caso("si sacrifica cio' che si controlla", t.sacrifica(o, 0) in t.giocatori[0].cimitero)
    t = nuovo(); m = prendi(t, 0, "Orso")
    caso("distruggere vale solo in campo (701.8a)", t.distruggi(m) is None and m.vivo)
    # 404.1: la cima del cimitero
    t = nuovo(); a = t.scarta(prendi(t, 0, "Orso")); b = t.scarta(prendi(t, 0, "Rito"))
    caso("l'ultimo arrivato e' in cima al cimitero (404.1)", t.giocatori[0].cimitero == [a, b])
    # 111.2, 111.7, 704.5d, 111.8
    t = nuovo(); p = t.crea_pedina(1, "Spirit", "Token Creature — Spirit")
    caso("la pedina e' di chi la crea e la controlla lui (111.2)", p.proprietario == 1 and p.controllore == 1)
    m = t.rimbalza(p)
    passaggio = any(e.tipo == "zona" and e.vecchio == p.n and e.a == "mano" for e in t.eventi)
    t.azioni_di_stato()
    caso("la pedina rimbalzata passa dalla mano (l'evento c'e', 111.7) e poi cessa (704.5d)",
         passaggio and not any(o.carta.pedina for _, _, o in t.tutti()) and t.eventi[-1].tipo == "cessa")
    t = nuovo(); p = t.distruggi(t.crea_pedina(0, "Spirit", "Token Creature — Spirit"))
    q = t.metti_in_campo(p, chi=0)
    caso("una pedina che ha lasciato il campo non ci torna (111.8)", q is p and p in t.giocatori[0].cimitero and not t.campo)
    # le vite: 119.4, 119.5, 119.9, 704.5a, 104.2a, 104.4a
    t = nuovo(vite=3)
    caso("pagare 5 vite con 3 non si puo' (119.4)", not t.paga_vite(0, 5) and t.giocatori[0].vite == 3)
    caso("pagarne 3 con 3 si'", t.paga_vite(0, 3) and t.giocatori[0].vite == 0)
    t.azioni_di_stato()
    caso("a 0 vite si perde, e l'altro vince (704.5a, 104.2a)", t.giocatori[0].perso and t.finita and t.vincitore == 1)
    t = nuovo(); n0 = len(t.eventi)
    t.imposta_vite(0, 25); t.imposta_vite(0, 18)
    caso("impostare le vite e' guadagnarle o perderle (119.5)",
         [e.quanto for e in t.eventi[n0:]] == [5, -7] and t.giocatori[0].vite == 18)
    n0 = len(t.eventi); t.guadagna(0, 0)
    caso("guadagnare 0 vite non e' un evento (119.9)", len(t.eventi) == n0)
    t = nuovo(); t.perdi(0, 20); t.perdi(1, 20); t.azioni_di_stato()
    caso("se perdono tutti insieme e' pari (104.4a)", t.finita and t.vincitore is None)
    t = nuovo(); t.perdi(1, 20); t.azioni_di_stato(); t.perdi(0, 20); t.azioni_di_stato()
    caso("a partita finita non perde piu' nessuno (104.1)", t.vincitore == 0 and not t.giocatori[0].perso)
    # 121.4, 704.5b
    t = nuovo(); t.pesca(1, 11); t.azioni_di_stato()
    caso("chi pesca da un grimorio vuoto perde al controllo di stato (121.4, 704.5b)",
         t.giocatori[1].perso and t.giocatori[1].perche == "704.5b" and len(t.giocatori[1].mano) == 10)
    # 400.2, 401.3, 402.3, 406.3
    t = nuovo(); t.mano_iniziale(0); t.mano_iniziale(1); t.macina(0, 2)
    t.esilia(t.giocatori[1].mano[0], a_faccia_in_giu=True)
    v = t.vista(1)
    caso("si vede la propria mano, quella dell'altro solo contata, i grimori contati (402.3, 401.3)",
         v["giocatori"][0]["mano"] == 7 and isinstance(v["giocatori"][1]["mano"], list) and v["giocatori"][0]["grimorio"] == 1)
    caso("il cimitero si vede per nome, l'esilio a faccia in giu' no (400.2, 406.3)",
         len(v["giocatori"][0]["cimitero"]) == 2 and "?" not in v["giocatori"][0]["cimitero"] and v["esilio"] == ["?"])
    # 103.5 dal tavolo
    t = nuovo(); mano, k = t.mano_iniziale(0, mulligan=lambda m, k: k < 1)
    caso("mulligan London dal tavolo: 1 mulligan, 6 in mano, 4 nel grimorio (103.5)",
         k == 1 and len(mano) == 6 and len(t.giocatori[0].grimorio) == 4 and all(o.zona == "mano" for o in mano))
    # gli eventi: «muore» e 400.7e
    t = nuovo(); o = t.metti_in_campo(prendi(t, 0, "Orso"), chi=0); c = t.distruggi(o)
    e = next(e for e in reversed(t.eventi) if e.tipo == "zona")
    trovato = next((x for _, _, x in t.tutti() if x.n == e.nuovo), None)
    caso("«muore» e' un evento dal campo al cimitero, e l'evento trova l'oggetto nuovo (400.7e)",
         (e.da, e.a, e.vecchio) == ("campo", "cimitero", o.n) and trovato is c)
    return casi


def prova():
    casi = []
    def caso(nome, ok, det=""): casi.append((nome, bool(ok), det))
    mazzi = mazzi_di_prova()
    conta = Counter(v[0] for v in mazzi[0])
    caso("il mazzo di prova e' quello da draft finto: 17 terre generiche e 23 permanenti vuoti",
         len(mazzi[0]) == 40 and conta["Terra"] == 17 and all(Carta(0, v[0], v[1], 0).permanente for v in mazzi[0]), str(dict(conta)))
    # 1. le regole una per una
    for nome, ok, det in prove_regole(Tavolo): caso(nome, ok, det)
    # 2. la conservazione: 3 partite a caso da 3000 mosse, gli invarianti dopo ogni mossa
    tot, rossi = Counter(), []
    for s in (1, 2, 3):
        t, err, fatte = passeggiata(Tavolo, s, 3000, mazzi)
        tot += fatte
        if err: rossi.append((s, err[:3]))
    cambi = sum(1 for e in t.eventi if e.tipo == "zona")
    caso("9000 mosse a caso: ogni carta sempre in un posto solo, ogni cambio di zona un oggetto nuovo",
         not rossi and len(tot) >= 16, str(rossi) if rossi else f"{len(tot)} tipi di mossa, {cambi} cambi di zona nell'ultima")
    # 3. il seme: la stessa partita si rifa' uguale, anche negli eventi
    a, _, _ = passeggiata(Tavolo, 7, 1500, mazzi, controlla_ogni=500)
    b, _, _ = passeggiata(Tavolo, 7, 1500, mazzi, controlla_ogni=500)
    c, _, _ = passeggiata(Tavolo, 8, 1500, mazzi, controlla_ogni=500)
    caso("stesso seme, stessa partita (tavolo ed eventi)", a.stato() == b.stato() and [e.chiave() for e in a.eventi] == [e.chiave() for e in b.eventi])
    caso("semi diversi, partite diverse", a.stato() != c.stato())

    # 4. le prove negative: tre tavoli rotti apposta, ognuno deve risultare rosso
    class StessoOggetto(Tavolo):          # dimentica 400.7: la carta cambia zona e resta lo stesso oggetto
        def _nuovo_id(self, vecchio): return vecchio.n
    class Doppione(Tavolo):               # dimentica di togliere la carta da dov'era
        def _togli(self, ogg): pass
    class AlControllore(Tavolo):          # dimentica 400.3: la carta va nella zona di chi la controlla
        def _di_chi(self, ogg, verso, chi): return chi if chi is not None else self.controllore_di(ogg)
    for nome, T, regola in (("stesso oggetto dopo il cambio di zona", StessoOggetto, "(400.7)"),
                            ("carta lasciata anche dov'era", Doppione, "una volta sola"),
                            ("carta nella zona di chi la controlla", AlControllore, "(400.3)")):
        _, err, _ = passeggiata(T, 1, 3000, mazzi)
        rosse = [n for n, ok, _ in prove_regole(T) if not ok and regola.strip("()") in n] if regola.startswith("(") else []
        caso(f"prova negativa: {nome} risulta rosso", err and (rosse or not regola.startswith("(")),
             (err[0] if err else "nessun errore trovato") + (f" | regole rosse: {len(rosse)}" if rosse else ""))

    for nome, ok, det in casi:
        print(f"  {'ok   ' if ok else 'ROSSO'} {nome}" + (f"  [{det}]" if det else ""))
    print(f"{sum(ok for _, ok, _ in casi)}/{len(casi)}")
    return 0 if all(ok for _, ok, _ in casi) else 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if "--prova" in sys.argv: sys.exit(prova())
    print(__doc__)
