"""Il turno: il passo 3 del motore di partita (Autore, 14 ott 2026: «ogni turno un giocatore puo' pescare una carta e
giocare una terra; se il mana della terra lo permette puo' giocare una carta a costo 1 da mettere sul campo; le carte sono
creature, incantesimi, artefatti, planeswalker, tutti permanenti»).

Secondo il regolamento ufficiale (Regole/MagicCompRules.txt):
  - il turno ha cinque fasi, sempre tutte (500.1): iniziale (stap, mantenimento, acquisizione: 501.1), principale
    precombattimento, combattimento (506.1), principale postcombattimento, finale (finale e pulizia: 512.1). Senza
    attaccanti si saltano dichiarazione dei bloccanti e danno (508.8): in questo passo nessuno attacca (e' il passo 6);
  - stap: il giocatore attivo stappa i suoi permanenti (502.3), e nessuno ha priorita' (502.4). Senza questo la terra
    tappata al primo turno resta tappata per sempre;
  - acquisizione: il giocatore attivo pesca (504.1); chi comincia salta l'acquisizione del suo primo turno (103.8a);
  - la terra: una per turno (305.2, 116.2a), solo nel proprio turno, in una fase principale, a pila vuota (305.1). Non
    passa dalla pila e non si lancia (305.9): si mette in campo;
  - il mana (passo 4, Motore_Partita/mana.py): la terra con un tipo base da' il suo colore (305.6), le altre le
    produzioni scritte (la terra generica del mazzo finto «{T}: Add {C}»). E' un'abilita' di mana: non usa la pila, si
    risolve subito (605.3b). Il mana va nella riserva per tipo e la riserva si svuota alla fine di ogni passo e di ogni
    fase (106.4);
  - lanciare un permanente: dalla mano, nel proprio turno, in una fase principale, a pila vuota (301.1, 302.1, 303.1,
    306.1, 117.1a). La carta va in pila (601.2a), si annunciano la X e il modo di pagare ibridi e phyrexiani (601.2b,
    107.3a), si attivano le abilita' di mana (601.2g), si paga tutto il costo o niente (601.2h): i colori col loro colore,
    il generico con qualsiasi mana, le vite solo se bastano (107.4, 118.3a, 119.4). Poi i giocatori passano e si risolve
    (405.5): entra in campo sotto chi l'ha lanciata (608.3a), oggetto nuovo (400.7). Un oggetto senza costo di mana non
    si lancia pagandolo (202.1b, 118.6). In questo passo nessuno risponde: la priorita' vera e le risposte sono il passo 5
    (pila.py, che usa questo turno come base);
  - la debolezza da evocazione (302.6): una creatura non puo' attaccare ne' tapparsi per un costo finche' chi la controlla
    non la controlla dall'inizio del suo ultimo turno. Qui si calcola (`debole`), serve dal combattimento;
  - il planeswalker entra con i segnalini fedelta' (306.5b); a 0 va nel cimitero (704.5i); una creatura con costituzione
    0 pure (704.5f). Le azioni di stato si controllano ogni volta che qualcuno avrebbe la priorita' (117.5, 704.3);
  - pulizia: chi ha piu' di 7 carte scarta fino a 7, sceglie lui quali (514.1); il danno si toglie (514.2).
Le scelte (che terra giocare, cosa lanciare, cosa scartare) le fa un `Giocatore` finto passato da fuori: `GiocaTutto`
gioca una terra e lancia tutto quello che puo' pagare.

    py -I -X utf8 Motore_Partita/turno.py --prova
    py -I -X utf8 Motore_Partita/turno.py --partita [seme]     una partita fra due GiocaTutto, turno per turno
"""
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mana as M
from inizio import inizia
from tavolo import Tavolo, controlla, mazzo_draft_generico

FASI = (("iniziale", ("stap", "mantenimento", "acquisizione")),                                   # 501.1
        ("principale_1", (None,)),                                                                 # 505.1
        ("combattimento", ("inizio", "attaccanti", "bloccanti", "danno", "fine")),                 # 506.1
        ("principale_2", (None,)),
        ("finale", ("finale", "pulizia")))                                                         # 512.1
SENZA_PRIORITA = {"stap", "pulizia"}                                                               # 502.4, 514.3


class GiocaTutto:
    """Il giocatore finto piu' semplice: nella prima fase principale gioca una terra, se ce l'ha, e lancia tutto quello
    che riesce a pagare (con la X piu' grande che paga); alla pulizia scarta le ultime carte della mano."""

    def principale(self, p, i, fase):
        if fase != "principale_1": return
        terra = next((o for o in p.t.giocatori[i].mano if "land" in o.carta.tipi), None)
        if terra is not None: p.gioca_terra(i, terra)
        while True:
            carta = next((o for o in p.t.giocatori[i].mano if p.puo_lanciare(i, o)), None)
            if carta is None or p.lancia(i, carta, x=p.x_massimo(i, carta) or 0) is None: break

    def scarta(self, p, i, mano, quante):
        return mano[-quante:]


class Partita:
    """Il turno sul tavolo t, gia' cominciato con inizio.inizia (chi comincia e le mani)."""

    def __init__(self, t):
        if t.primo is None: raise ValueError("prima inizio.inizia(t): chi comincia e le mani (103)")
        self.t = t
        self.attivo = t.primo
        self.ultimo = None                                         # di chi era il turno appena giocato (anche se la partita e' finita a meta')
        self.fase = self.passo = None
        self.inizio_turno = {g.i: None for g in t.giocatori}      # il turno in cui e' cominciato l'ultimo turno di ognuno
        self.lanciate = Counter()                                  # (turno, giocatore) -> magie risolte
        self.pagati = []                                           # (carta, Pagamento, X, fonti, riserva prima): per le prove
        self.chi = None                                            # i giocatori finti del turno in corso (indice -> Giocatore)

    # ------------------------------------------------------------------ quando si puo'
    def da_stregoneria(self, i):
        """307.5, 117.1a: il proprio turno, una fase principale, la pila vuota (e la priorita', che qui ha l'attivo)."""
        return i == self.attivo and self.fase in ("principale_1", "principale_2") and not self.t.pila and not self.t.finita

    def _limite_terre(self, i):
        return 1                                                                                   # 305.2

    def puo_giocare_terra(self, i, ogg):
        g = self.t.giocatori[i]
        return (self.da_stregoneria(i) and ogg.vivo and ogg in g.mano and "land" in ogg.carta.tipi
                and g.terre_giocate < self._limite_terre(i))

    def terre_stappate(self, i):
        """Le fonti di mana di i adesso: i suoi permanenti stappati con un'abilita' di mana {T}. In questo passo sono le
        terre (le creature con {T}: aggiungi vogliono 302.6 e arrivano col passo 7)."""
        return [o for o in self.t.campo if o.controllore == i and "land" in o.carta.tipi and not o.tappato
                and self.produzioni(o)]

    def produzioni(self, ogg):
        return M.produzioni(ogg.carta)                                                             # 305.6, 605

    def fonti(self, i):
        return [self.produzioni(o) for o in self.terre_stappate(i)]

    def piano(self, i, costo, x=0):
        """601.2b-h: il pagamento del costo con la riserva e le fonti di adesso. -> mana.Pagamento o None."""
        return M.piano(costo, self.fonti(i), self.t.giocatori[i].riserva, x, self.t.giocatori[i].vite)

    def mana_disponibile(self, i):
        """Quanti mana in tutto: la riserva piu' la produzione piu' grande di ogni fonte (solo per contare)."""
        return self.t.giocatori[i].riserva.totale() + sum(max(map(sum, f)) for f in self.fonti(i))

    def x_massimo(self, i, ogg):
        return M.x_massimo(ogg.carta.car.get("costo"), self.fonti(i), self.t.giocatori[i].riserva, self.t.giocatori[i].vite)

    def puo_lanciare(self, i, ogg, x=0):
        c = ogg.carta
        return (self.da_stregoneria(i) and ogg.vivo and ogg in self.t.giocatori[i].mano and c.permanente
                and "land" not in c.tipi                                                           # 305.9
                and self.piano(i, c.car.get("costo"), x) is not None)                              # 202.1b, 601.2h

    # ------------------------------------------------------------------ le azioni
    def gioca_terra(self, i, ogg):
        """305.1, 116.2a: azione speciale, niente pila. -> la terra in campo, o None se non si puo'."""
        if not self.puo_giocare_terra(i, ogg): return None
        self.t.giocatori[i].terre_giocate += 1
        return self.t.metti_in_campo(ogg, chi=i, causa="305.1")

    def tappa_per_mana(self, i, terra, prod=None):
        """L'abilita' di mana della terra (605): si risolve subito (605.3b), il mana va nella riserva (106.4). prod: quale
        produzione, se la terra ne ha piu' d'una (la doppia «{G} o {W}»); None = la prima."""
        prods = self.produzioni(terra) if terra.vivo else ()
        if not (prods and terra.zona == "campo" and terra.controllore == i): return False
        prod = prods[0] if prod is None else prod
        if prod not in prods or not self.t.tappa(terra): return False                             # 118.3: gia' tappata no
        self.t.giocatori[i].riserva.aggiungi(prod)
        self.t._evento("mana", carta=terra.carta, vecchio=terra.n, giocatore=i, a=M.scrivi(prod), quanto=sum(prod),
                       causa="605.3b")
        return True

    def lancia(self, i, ogg, x=0, pagamento=None):
        """601.2: in pila, gli annunci (X, ibridi, phyrexiani), le abilita' di mana, il pagamento intero; poi tutti passano
        e si risolve (405.5, 608.3a). pagamento: un mana.Pagamento scelto dal giocatore (None = mana.piano). -> il
        permanente in campo, o None se non si puo' lanciare o il pagamento non e' legale (e allora non si e' mosso niente).
        Nel passo 5 (pila.py) la risoluzione si stacca: lanciare finisce con la magia in pila."""
        magia = self._metti_e_paga(i, ogg, x, pagamento)
        if magia is None: return None
        self.priorita()                                                                            # 117.5
        permanente = self.t.sposta(magia, "campo", chi=magia.controllore, causa="608.3a")          # 405.5: tutti passano
        self.lanciate[(self.t.turno_numero, i)] += 1
        self.priorita()
        return permanente

    def _metti_e_paga(self, i, ogg, x=0, pagamento=None):
        """601.2a-h: la magia in pila e il costo pagato tutto. -> la magia in pila, o None (e niente si e' mosso, 734.1)."""
        if not self.puo_lanciare(i, ogg, x): return None
        costo = self._costo_di(i, ogg)
        scelto = self._scegli_pagamento(i, costo, x, pagamento)
        if scelto is None: return None
        magia = self.t.metti_in_pila(ogg, chi=i, causa="601.2a")
        magia.x = x                                                                                # 107.3a
        self._paga(i, magia, costo, x, scelto)
        self.pagati.append((ogg.carta, scelto[0], x, scelto[2], scelto[3]))
        return magia

    def _costo_di(self, i, ogg):
        """Il costo da pagare lanciando (601.2f): il costo di mana stampato. Il passo 7 ci mette i costi alternativi."""
        return ogg.carta.car.get("costo")

    def _scegli_pagamento(self, i, costo, x=0, pagamento=None):
        """601.2b-h: il pagamento scelto (o quello di mana.piano) se e' legale adesso. -> (Pagamento, terre, fonti,
        riserva) com'erano prima di pagare, o None. Le abilita' attivate pagano allo stesso modo (602.2b)."""
        g = self.t.giocatori[i]
        terre, fonti, riserva = self.terre_stappate(i), self.fonti(i), g.riserva.tupla()
        if pagamento is None: pagamento = self.piano(i, costo, x)
        elif M.valida(pagamento, costo, fonti, riserva, x, g.vite): return None
        return None if pagamento is None else (pagamento, terre, fonti, riserva)

    def _paga(self, i, oggetto, costo, x, scelto):
        """601.2g-h: le abilita' di mana, poi il costo tutto insieme."""
        pagamento, terre = scelto[0], scelto[1]
        g = self.t.giocatori[i]
        for k, prod in pagamento.usa: self.tappa_per_mana(i, terre[k], prod)                       # 601.2g
        if pagamento.vite: self.t.paga_vite(i, pagamento.vite, causa="107.4f")                     # 119.4
        if not g.riserva.paga(pagamento.spesa):                                                    # 601.2h
            raise RuntimeError(f"601.2h: il pagamento di {oggetto} non torna con la riserva {g.riserva}")
        self.t._evento("paga", carta=oggetto.carta, vecchio=oggetto.n, giocatore=i, a=M.scrivi(pagamento.spesa),
                       quanto=sum(pagamento.spesa), causa="601.2h")

    def debole(self, ogg):
        """302.6: vero se la creatura non e' sotto chi la controlla da quando e' cominciato il suo ultimo turno."""
        if "creature" not in ogg.carta.tipi or ogg.zona != "campo": return False
        inizio = self.inizio_turno.get(ogg.controllore)
        return inizio is None or ogg.controllo_dal is None or ogg.controllo_dal >= inizio

    def priorita(self):
        """117.5: prima che qualcuno abbia la priorita', le azioni di stato."""
        return self.t.azioni_di_stato()

    # ------------------------------------------------------------------ il turno
    def _svuota_mana(self):
        for g in self.t.giocatori: g.riserva.svuota()                                              # 106.4

    def _stap(self, i):
        for o in self.t.campo:                                                                     # 502.3
            if o.controllore == i and o.tappato: self.t.stappa(o)

    def _salta_acquisizione(self, i):
        return i == self.t.primo and self.t.turno_numero == 1                                     # 103.8a

    def turno(self, giocatori):
        """Un turno intero del giocatore attivo. giocatori: un Giocatore finto per indice (principale, scarta)."""
        t, i = self.t, self.attivo
        self.ultimo, self.chi = i, giocatori
        t.turno_numero += 1
        self.inizio_turno[i] = t.turno_numero
        t.giocatori[i].terre_giocate = 0
        t._evento("turno", giocatore=i, quanto=t.turno_numero, causa="500.1")
        for fase, passi in FASI:
            for passo in self._passi(fase, passi, i):
                if t.finita: return
                self.fase, self.passo = fase, passo
                t._evento("passo", giocatore=i, da=fase, a=passo or "", causa="500.1")
                self._azioni_del_turno(i, passo, giocatori)                                        # 703.4
                if passo not in SENZA_PRIORITA: self._priorita_del_passo(giocatori)                # 117.3a
                if passo is not None: self._svuota_mana()                                          # 106.4: fine passo
            self._svuota_mana()                                                                    # 106.4: fine fase
        self.fase = self.passo = None
        self.attivo = (i + 1) % len(t.giocatori)

    def _passi(self, fase, passi, i):
        """I passi della fase che si giocano davvero, uno alla volta (il passo 6 decide i passi del combattimento mentre
        il combattimento avanza: 508.8, 510.4)."""
        for passo in passi:
            if passo == "acquisizione" and self._salta_acquisizione(i): continue                   # 103.8a
            if passo in ("bloccanti", "danno"): continue                                           # 508.8: nessun attaccante
            yield passo

    def _azioni_del_turno(self, i, passo, giocatori):
        """703.4: le azioni del turno all'inizio del passo, prima della priorita'."""
        if passo == "stap": self._stap(i)                                                          # 703.4c, 502.3
        elif passo == "acquisizione": self.t.pesca(i, causa="504.1")                               # 703.4d
        elif passo == "pulizia": self._pulizia(i, giocatori[i])                                    # 703.4n-p

    def _priorita_del_passo(self, giocatori):
        """Il passo con la priorita'. Qui nessuno risponde: le azioni di stato (117.5) e, nella fase principale, il
        giocatore attivo che fa le sue mosse. Il passo 5 (pila.py) mette al suo posto la priorita' vera (117)."""
        self.priorita()                                                                            # 117.5
        if self.passo is None and not self.t.finita: giocatori[self.attivo].principale(self, self.attivo, self.fase)

    def _pulizia(self, i, giocatore):
        g = self.t.giocatori[i]
        troppe = len(g.mano) - g.mano_massima
        if troppe > 0:                                                                             # 514.1
            via = list(giocatore.scarta(self, i, list(g.mano), troppe))
            if len(via) != troppe or any(o not in g.mano for o in via): via = g.mano[-troppe:]
            with self.t.insieme():                                                                 # 514.1: tutte insieme
                for o in via: self.t.scarta(o, causa="514.1")
        for o in self.t.campo: o.danno = 0                                                         # 514.2
        self._fine_turno()                                                                         # 514.2: insieme al danno

    def _fine_turno(self):
        """514.2: gli effetti «until end of turn» finiscono insieme alla rimozione del danno (il passo 7). Qui niente."""

    def gioca(self, giocatori, max_turni=500, dopo_ogni_turno=None):
        while not self.t.finita and self.t.turno_numero < max_turni:
            self.turno(giocatori)
            if dopo_ogni_turno: dopo_ogni_turno(self)
        return self.t.vincitore


def nuova(seme, giocatori=None, decidi=None, **kw):
    """Un tavolo col mazzo da draft finto, l'inizio (103) e la partita pronta. -> Partita."""
    t = Tavolo([mazzo_draft_generico(**kw), mazzo_draft_generico(**kw)], seme=seme)
    inizia(t, decidi=decidi)
    return Partita(t)


# ====================================================================== le prove
def prove_regole(P):
    """Le regole del turno una per una, su una Partita di classe P. -> [(nome, ok, dettaglio)]."""
    casi = []
    def caso(nome, ok, det=""): casi.append((nome, bool(ok), det))
    class Fermo:                                          # non fa niente
        def principale(self, p, i, fase): pass
        def scarta(self, p, i, mano, quante): return mano[:quante]
    def partita(seme=1, **kw):
        t = Tavolo([mazzo_draft_generico(**kw), mazzo_draft_generico(**kw)], seme=seme)
        inizia(t, primo=0)
        return P(t)
    def in_mano(p, i, nome):
        return next(o for o in p.t.giocatori[i].mano if o.nome == nome)
    def dai(p, i, nome):
        """Una carta di quel nome dal grimorio alla mano, per costruire la situazione."""
        o = next(o for o in p.t.giocatori[i].grimorio.carte if o.nome == nome)
        p.t._togli(o)
        return p.t._arriva(o, "grimorio", "mano", None, None, "prova")
    class Script:                                         # fa nella prima fase principale le azioni scritte
        def __init__(self, azioni): self.azioni, self.esiti = azioni, []
        def principale(self, p, i, fase):
            if fase == "principale_1": self.esiti.append(self.azioni(p, i, fase))
        def scarta(self, p, i, mano, quante): return mano[:quante]

    # 500.1, 501.1, 506.1, 508.8, 512.1, 103.8a: i passi del primo turno
    p = partita(); p.turno({0: Fermo(), 1: Fermo()})
    passi = [(e.da, e.a) for e in p.t.eventi if e.tipo == "passo"]
    attesi = [("iniziale", "stap"), ("iniziale", "mantenimento"), ("principale_1", ""), ("combattimento", "inizio"),
              ("combattimento", "attaccanti"), ("combattimento", "fine"), ("principale_2", ""), ("finale", "finale"),
              ("finale", "pulizia")]
    caso("il primo turno: cinque fasi, senza acquisizione per chi comincia (500.1, 103.8a), senza bloccanti e danno (508.8)",
         passi == attesi, str(passi))
    caso("chi comincia non pesca al primo turno (103.8a)", len(p.t.giocatori[0].grimorio) == 33)
    p.turno({0: Fermo(), 1: Fermo()})        # chi non gioca niente scarta a 7 alla pulizia: si conta il grimorio
    caso("l'altro pesca al suo primo turno (504.1)", len(p.t.giocatori[1].grimorio) == 32)
    p.turno({0: Fermo(), 1: Fermo()})
    caso("chi comincia pesca dal suo secondo turno", len(p.t.giocatori[0].grimorio) == 32)

    # 305.1, 305.2, 116.2a, 305.9: la terra
    def due_terre(p, i, fase):
        dai(p, i, "Terra"); dai(p, i, "Terra")
        terre = [o for o in p.t.giocatori[i].mano if o.nome == "Terra"]
        return [p.gioca_terra(i, terre[0]) is not None, p.gioca_terra(i, terre[1]) is not None]
    s = Script(due_terre); p = partita(); p.turno({0: s, 1: Fermo()})
    caso("una terra per turno: la seconda no (305.2)", s.esiti[0] == [True, False], str(s.esiti))
    p = partita(); dai(p, 1, "Terra")
    p.fase = "principale_1"
    caso("la terra solo nel proprio turno (305.1)", p.gioca_terra(1, in_mano(p, 1, "Terra")) is None)
    p = partita(); dai(p, 0, "Terra"); p.fase, p.passo = "iniziale", "mantenimento"
    caso("la terra solo in una fase principale (305.1)", p.gioca_terra(0, in_mano(p, 0, "Terra")) is None)
    p = partita(); dai(p, 0, "Terra"); dai(p, 0, "Creatura"); p.fase = "principale_1"
    p.t.metti_in_pila(in_mano(p, 0, "Creatura"), chi=0)
    caso("la terra solo a pila vuota (305.1, 116.2a)", p.gioca_terra(0, in_mano(p, 0, "Terra")) is None)
    p = partita(); dai(p, 0, "Terra"); p.fase = "principale_1"
    caso("la terra non si lancia (305.9)", p.lancia(0, in_mano(p, 0, "Terra")) is None and not p.t.pila)
    caso("giocata, la terra va in campo senza passare dalla pila (305.1)",
         p.gioca_terra(0, in_mano(p, 0, "Terra")) in p.t.campo and not any(e.a == "pila" for e in p.t.eventi if e.tipo == "zona"))

    # 601.2, 608.3a, 107.4b: lanciare a costo 1
    p = partita(); dai(p, 0, "Creatura"); p.fase = "principale_1"
    c = in_mano(p, 0, "Creatura")
    caso("senza terre una carta a costo 1 non si lancia, e resta in mano (601.2h)", p.lancia(0, c) is None and c in p.t.giocatori[0].mano)
    dai(p, 0, "Terra"); terra = p.gioca_terra(0, in_mano(p, 0, "Terra"))
    perm = p.lancia(0, c)
    zone = [(e.da, e.a) for e in p.t.eventi if e.tipo == "zona" and e.carta is c.carta][1:]   # il primo e' il «dai»
    caso("con una terra si lancia: dalla mano in pila, poi in campo (601.2a, 608.3a)", zone == [("mano", "pila"), ("pila", "campo")], str(zone))
    caso("in campo la controlla chi l'ha lanciata, ed e' un oggetto nuovo (608.3a, 400.7)",
         perm.controllore == 0 and perm.n != c.n and not c.vivo)
    caso("la terra si e' tappata per pagare (601.2g, 605.3b) e la riserva e' a zero", terra.tappato and p.t.giocatori[0].riserva.totale() == 0)
    dai(p, 0, "Artefatto")
    caso("con la terra gia' tappata non se ne lancia una seconda", p.lancia(0, in_mano(p, 0, "Artefatto")) is None)
    # tre terre, tre carte
    p = partita(); p.fase = "principale_1"
    for _ in range(3): p.t.metti_in_campo(dai(p, 0, "Terra"), chi=0)
    for nome in ("Creatura", "Incantesimo", "Artefatto", "Creatura"): dai(p, 0, nome)
    fatte = [p.lancia(0, in_mano(p, 0, n)) is not None for n in ("Creatura", "Incantesimo", "Artefatto", "Creatura")]
    caso("con tre terre si lanciano tre carte a costo 1, la quarta no", fatte == [True, True, True, False], str(fatte))
    # 301.1, 302.1, 117.1a: solo nella propria fase principale
    p = partita(); p.t.metti_in_campo(dai(p, 1, "Terra"), chi=1); dai(p, 1, "Creatura"); p.fase = "principale_1"
    caso("nel turno dell'altro non si lancia un permanente (302.1, 117.1a)", p.lancia(1, in_mano(p, 1, "Creatura")) is None)
    p = partita(); p.t.metti_in_campo(dai(p, 0, "Terra"), chi=0); dai(p, 0, "Creatura"); p.fase, p.passo = "finale", "finale"
    caso("nel passo finale non si lancia un permanente (302.1)", p.lancia(0, in_mano(p, 0, "Creatura")) is None)

    # 106.4: la riserva si svuota fra le fasi
    def tappa_e_aspetta(p, i, fase):
        if fase == "principale_1":
            dai(p, i, "Creatura")
            p.tappa_per_mana(i, p.gioca_terra(i, dai(p, i, "Terra")))
            return ("p1", p.t.giocatori[i].riserva.totale())
        return ("p2", p.t.giocatori[i].riserva.totale(), p.lancia(i, in_mano(p, i, "Creatura")) is None)
    class Due(Script):
        def principale(self, p, i, fase): self.esiti.append(self.azioni(p, i, fase))
    s = Due(tappa_e_aspetta); p = partita(); p.turno({0: s, 1: Fermo()})
    caso("il mana non speso si perde alla fine della fase (106.4)", s.esiti == [("p1", 1), ("p2", 0, True)], str(s.esiti))

    # 502.3: lo stap
    p = partita(); mia = p.t.metti_in_campo(dai(p, 0, "Terra"), chi=0); sua = p.t.metti_in_campo(dai(p, 1, "Terra"), chi=1)
    p.t.tappa(mia); p.t.tappa(sua)
    p.turno({0: Fermo(), 1: Fermo()})
    caso("nel suo stap il giocatore attivo stappa i suoi permanenti, non quelli dell'altro (502.3)", not mia.tappato and sua.tappato)
    p.turno({0: Fermo(), 1: Fermo()})
    caso("e l'altro li stappa nel suo turno", not sua.tappato)

    # 302.6: la debolezza da evocazione
    vista = {}
    def lancia_creatura(p, i, fase):
        dai(p, i, "Creatura"); p.gioca_terra(i, dai(p, i, "Terra"))
        vista["c"] = p.lancia(i, in_mano(p, i, "Creatura"))
        vista["subito"] = p.debole(vista["c"])
    class Guarda:
        def principale(self, p, i, fase):
            if fase == "principale_1": vista.setdefault("turni", []).append((i, p.debole(vista["c"])))
        def scarta(self, p, i, mano, quante): return mano[:quante]
    p = partita(); p.turno({0: Script(lancia_creatura), 1: Fermo()})
    p.turno({0: Guarda(), 1: Guarda()}); p.turno({0: Guarda(), 1: Guarda()})
    caso("la creatura appena lanciata e' debole, anche nel turno dell'altro, non piu' nel turno dopo del suo controllore (302.6)",
         vista["subito"] and vista["turni"] == [(1, True), (0, False)], str(vista.get("turni")))

    # 306.5b, 704.5i, 704.5f
    p = partita(); p.fase = "principale_1"; p.t.metti_in_campo(dai(p, 0, "Terra"), chi=0); dai(p, 0, "Planeswalker")
    pw = p.lancia(0, in_mano(p, 0, "Planeswalker"))
    caso("il planeswalker entra coi segnalini fedelta' (306.5b)", pw.segnalini["fedelta"] == 1)
    pw.segnalini["fedelta"] = 0; p.priorita()
    caso("a fedelta' 0 va nel cimitero (704.5i)", not pw.vivo and any(o.nome == "Planeswalker" for o in p.t.giocatori[0].cimitero))
    p = partita(); p.t.metti_in_campo(dai(p, 0, "Creatura"), chi=0); cr = p.t.campo[-1]
    cr.carta.car["costituzione"] = 0; p.priorita()
    caso("una creatura con costituzione 0 va nel cimitero (704.5f)", not cr.vivo)

    # 514.1: la pulizia
    p = partita()
    for _ in range(3): dai(p, 0, "Terra")                    # 10 carte in mano
    scelte = {}
    class Sceglie(Fermo):
        def scarta(self, p, i, mano, quante):
            scelte["via"] = [o for o in mano if o.nome == "Terra"][:quante]
            return scelte["via"]
    p.turno({0: Sceglie(), 1: Fermo()})
    caso("alla pulizia si scarta fino a 7, le carte che sceglie il giocatore (514.1)",
         len(p.t.giocatori[0].mano) == 7 and all(not o.vivo for o in scelte["via"]) and len(p.t.giocatori[0].cimitero) == 3)
    return casi


def prova():
    casi = []
    def caso(nome, ok, det=""): casi.append((nome, bool(ok), det))
    for nome, ok, det in prove_regole(Partita): caso(nome, ok, det)

    # la partita intera fra due GiocaTutto: invarianti dopo ogni turno, mana mai inventato, la fine esatta
    def gioca_e_controlla(seme, P=Partita):
        t = Tavolo([mazzo_draft_generico(), mazzo_draft_generico()], seme=seme)
        inizia(t)
        p, err = P(t), []
        def dopo(p):
            e = controlla(p.t)
            if e and not err: err.append(f"turno {p.t.turno_numero}: {e[0]}")
            i = p.ultimo
            terre = sum(1 for o in p.t.campo if o.controllore == i and "land" in o.carta.tipi)
            if p.lanciate[(p.t.turno_numero, i)] > terre and not err:
                err.append(f"turno {p.t.turno_numero}: {p.lanciate[(p.t.turno_numero, i)]} magie con {terre} terre")
        p.gioca({0: GiocaTutto(), 1: GiocaTutto()}, dopo_ogni_turno=dopo)
        return p, err
    fini, errori = Counter(), []
    for s in range(20):
        p, err = gioca_e_controlla(s)
        errori += err
        perdente = 1 - p.t.vincitore if p.t.vincitore is not None else None
        fini[(p.t.turno_numero, perdente == 1 - p.t.primo, p.t.giocatori[perdente].perche if perdente is not None else None)] += 1
    caso("20 partite intere: ogni carta sempre in un posto solo, mai piu' magie che terre in un turno", not errori, "; ".join(errori[:2]))
    caso("finiscono tutte al turno 68: chi non ha cominciato resta senza carte per primo (103.8a, 121.4, 704.5b)",
         fini == Counter({(68, True, "704.5b"): 20}), str(dict(fini)))
    a, _ = gioca_e_controlla(7); b, _ = gioca_e_controlla(7)
    caso("stesso seme, stessa partita", a.t.stato() == b.t.stato() and len(a.t.eventi) == len(b.t.eventi))

    # le prove negative: quattro turni rotti apposta, la regola giusta deve risultare rossa
    class SenzaStap(Partita):
        def _stap(self, i): pass
    class DueTerre(Partita):
        def _limite_terre(self, i): return 2
    class RiservaPiena(Partita):
        def _svuota_mana(self): pass
    class PescaSubito(Partita):
        def _salta_acquisizione(self, i): return False
    for nome, P, cerca in (("senza stap", SenzaStap, "502.3"), ("due terre per turno", DueTerre, "305.2"),
                           ("la riserva non si svuota", RiservaPiena, "106.4"), ("chi comincia pesca subito", PescaSubito, "103.8a")):
        rosse = [n for n, ok, _ in prove_regole(P) if not ok]
        caso(f"prova negativa: {nome} risulta rosso", any(cerca in n for n in rosse), "; ".join(rosse[:2]) or "nessuna regola rossa")

    for nome, ok, det in casi:
        print(f"  {'ok   ' if ok else 'ROSSO'} {nome}" + (f"  [{det}]" if det else ""))
    print(f"{sum(ok for _, ok, _ in casi)}/{len(casi)}")
    return 0 if all(ok for _, ok, _ in casi) else 1


def racconta(seme=1):
    """Una partita fra due GiocaTutto, una riga per turno."""
    p = nuova(seme)
    print(f"seme {seme}: comincia G{p.t.primo + 1}")
    def riga(p):
        i = p.ultimo
        g = p.t.giocatori[i]
        terre = sum(1 for o in p.t.campo if o.controllore == i and "land" in o.carta.tipi)
        altri = sum(1 for o in p.t.campo if o.controllore == i and "land" not in o.carta.tipi)
        print(f"  T{p.t.turno_numero:>2} G{i + 1}: mano {len(g.mano)}, grimorio {len(g.grimorio)}, terre {terre}, "
              f"permanenti {altri}, lanciate {p.lanciate[(p.t.turno_numero, i)]}")
    p.gioca({0: GiocaTutto(), 1: GiocaTutto()}, dopo_ogni_turno=riga)
    print(f"fine al turno {p.t.turno_numero}: vince G{p.t.vincitore + 1}" if p.t.vincitore is not None else "pari")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if "--prova" in sys.argv: sys.exit(prova())
    if "--partita" in sys.argv:
        k = sys.argv.index("--partita")
        racconta(int(sys.argv[k + 1]) if len(sys.argv) > k + 1 else 1)
    else: print(__doc__)
