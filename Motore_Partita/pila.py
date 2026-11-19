"""La pila e la priorita': il passo 5 del motore di partita (14 ott 2026). Lanciare e risolvere, con le risposte.

Secondo il regolamento ufficiale (Regole/MagicCompRules.txt, numeri letti con Motore_Opzioni/regolamento.py):
  - chi ha la priorita' puo' agire (117.1). L'istantaneo si lancia ogni volta che si ha la priorita' (117.1a, 304.1);
    stregonerie e permanenti solo nella propria fase principale, con la priorita' e la pila vuota (117.1a, 301.1, 302.1,
    303.1, 306.1, 307.1, 307.5). La terra pure, ed e' un'azione speciale che non usa la pila (116.2a, 305.1);
  - chi riceve la priorita' (117.3): il giocatore attivo all'inizio di ogni passo e fase, dopo le azioni del turno
    (117.3a), nessuno nello stap (502.4) e di norma nessuno nella pulizia (514.3); l'attivo dopo ogni risoluzione
    (117.3b); chi lancia, attiva o fa un'azione speciale la tiene (117.3c, 116.3, 601.2i); l'abilita' di mana si
    risolve subito e chi aveva la priorita' la riavvia (405.6c, 605.3b, 117.1d); chi passa la cede al prossimo in ordine
    di turno e annuncia il mana che ha nella riserva (117.3d, 106.4b);
  - se tutti passano in fila, cioe' senza nessuna azione in mezzo, si risolve la cima della pila, l'ultima arrivata;
    a pila vuota il passo o la fase finisce (117.4, 405.2, 405.5, 500.2). Un'azione qualsiasi, anche un'abilita' di
    mana, rimette a zero il conto dei passaggi: e' la lettura letterale di 117.4 («without taking any actions»);
  - prima di ogni priorita' le azioni di stato, finche' ce n'e', poi gli inneschi in pila (117.5, 704.3). Gli inneschi
    nascono dalle abilita' delle carte, cioe' dal passo 7: un innesco in attesa oggi esce NonCoperto (603.3);
  - lanciare (601.2): la carta in pila e' la magia, sotto chi la lancia (601.2a, 405.4); annunci, abilita' di mana e
    pagamento intero dal passo 4 (601.2b-h); poi la magia e' lanciata e chi aveva la priorita' la riceve (601.2i). Un
    lancio illegale torna indietro tutto e la priorita' resta a chi l'aveva (734.1, 734.2);
  - risolvere (608): mentre si risolve nessuno ha la priorita' (117.2e). Il permanente entra in campo sotto chi
    controlla la magia (608.3a); l'istantaneo e la stregoneria seguono il testo (608.2c) e vanno nel cimitero del
    proprietario (608.2n, 304.2, 307.2). Le carte finte non hanno testo; una carta con testo esce NonCoperto (passo 7),
    e cosi' i bersagli (601.2c, 608.2b, 608.3b), che vengono solo dal testo;
  - contrastare (701.6a): la magia lascia la pila senza risolversi e va nel cimitero del proprietario; i costi pagati
    non tornano (701.6b). E' il verbo che le carte useranno al passo 7;
  - la pulizia (514.3a): se le azioni di stato fanno qualcosa, l'attivo riceve la priorita' e poi comincia un'altra
    pulizia.
Qui il combattimento resta senza attaccanti (il combattimento vero e' il passo 6, Motore_Partita/combattimento.py, che
parte da questa classe): dichiarazione dei bloccanti e danno si saltano (508.8), ma nei passi
di inizio, attaccanti e fine combattimento la priorita' gira come negli altri (508.2).

Le scelte le fa un giocatore finto con `agisci(p, i)`: None = passa, oppure un'azione («terra», terra), («lancia», carta,
x, pagamento), («mana», terra, produzione). `GiocaSubito` fa le mosse di turno.GiocaTutto e non risponde mai: con lui
il passo 5 gioca la stessa partita del passo 3, mossa per mossa (e' una prova). `Caso` sceglie a caso fra le azioni
legali e ogni tanto ne tenta una illegale: e' il banco di prova delle risposte.

    py -I -X utf8 Motore_Partita/pila.py --prova
    py -I -X utf8 Motore_Partita/pila.py --partita [seme]     una partita fra due Caso, con risposte, turno per turno
"""
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # py -I non mette la cartella dello script nel percorso
import numpy as np
import mana as M
import turno as T
from inizio import inizia
from mana import NonCoperto
from tavolo import COMPOSIZIONE_COLORI, Tavolo, controlla, mazzo_draft_colori, mazzo_draft_generico

# il mazzo finto del passo 5: come quello del passo 3, con 6 istantanei e una stregoneria vuoti al posto di 7 permanenti
COMPOSIZIONE_PILA = {"creature": 10, "artifact": 2, "enchantment": 2, "planeswalker": 2, "instant": 6, "sorcery": 1}


def _colori_pila():
    """Il mazzo a due colori del passo 4 con 6 creature in meno e 5 istantanei e una stregoneria colorati al loro posto."""
    meno = {"Creatura G": 2, "Creatura G/W": 1, "Creatura 2/W": 1, "Creatura W": 1, "Creatura 1G": 1}
    comp = tuple((n, tp, car, k - meno.get(n, 0)) for n, tp, car, k in COMPOSIZIONE_COLORI)
    return comp + (("Istantaneo G", "Instant", {"costo": "{G}"}, 3),
                   ("Istantaneo 1W", "Instant", {"costo": "{1}{W}"}, 2),
                   ("Stregoneria XG", "Sorcery", {"costo": "{X}{G}"}, 1))


COMPOSIZIONE_PILA_COLORI = _colori_pila()


def mazzo_pila():
    return mazzo_draft_generico(composizione=COMPOSIZIONE_PILA)


def mazzo_pila_colori():
    return mazzo_draft_colori(COMPOSIZIONE_PILA_COLORI)


# ====================================================================== i giocatori finti
class GiocaSubito:
    """Le mosse di turno.GiocaTutto con la priorita' vera: nella prima fase principale, a pila vuota, gioca una terra se
    ce l'ha e lancia la prima carta che riesce a pagare (con la X piu' grande); per il resto passa. Non risponde mai."""

    def agisci(self, p, i):
        if p.fase != "principale_1" or not p.da_stregoneria(i): return None
        mano = p.t.giocatori[i].mano
        terra = next((o for o in mano if "land" in o.carta.tipi), None)
        if terra is not None and p.puo_giocare_terra(i, terra): return ("terra", terra)
        carta = next((o for o in mano if p.puo_lanciare(i, o)), None)
        return None if carta is None else ("lancia", carta, p.x_massimo(i, carta) or 0, None)

    def scarta(self, p, i, mano, quante):
        return mano[-quante:]


class Caso:
    """Sceglie a caso fra le azioni legali di adesso (terra, lanciare, tappare per mana) o passa; con probabilita'
    «illegali» tenta di lanciare una carta qualsiasi della mano, legale o no: il motore deve rifiutare quelle illegali.
    Tiene gli istantanei per rispondere: li lancia con la pila piena o nel turno dell'altro (con probabilita' «risponde»),
    quasi mai a pila vuota nel proprio turno. E' il banco di prova delle risposte, non un modo di giocare bene."""

    def __init__(self, seme, passa=0.4, illegali=0.1, mana=0.01, risponde=0.6):
        self.rng, self.passa, self.illegali, self.mana = np.random.default_rng(seme), passa, illegali, mana
        self.risponde = risponde

    def _uno(self, lst):
        return lst[int(self.rng.integers(0, len(lst)))]

    def agisci(self, p, i):
        mano = p.t.giocatori[i].mano
        if mano and self.rng.random() < self.illegali: return ("lancia", self._uno(mano), 0, None)
        azioni = []
        for o in mano:
            if "land" in o.carta.tipi:
                if p.puo_giocare_terra(i, o): azioni.append(("terra", o))
            elif p.puo_lanciare(i, o):
                x = 0
                if "{X}" in (o.carta.car.get("costo") or ""): x = int(self.rng.integers(0, (p.x_massimo(i, o) or 0) + 1))
                azioni.append(("lancia", o, x, None))
        for terra in p.terre_stappate(i):
            if self.rng.random() < self.mana: azioni.append(("mana", terra, self._uno(p.produzioni(terra))))
        istantanei = [a for a in azioni if a[0] == "lancia" and "instant" in a[1].carta.tipi]
        if istantanei and (p.t.pila or i != p.attivo) and self.rng.random() < self.risponde: return self._uno(istantanei)
        if not (p.t.pila or i != p.attivo) and self.rng.random() < 0.9:
            azioni = [a for a in azioni if a not in istantanei]
        if not azioni or self.rng.random() < self.passa: return None
        return self._uno(azioni)

    def scarta(self, p, i, mano, quante):
        return mano[:quante]


# ====================================================================== la partita con la pila
class Partita(T.Partita):
    """Il turno del passo 3 con la priorita' vera in ogni passo e fase."""

    def __init__(self, t):
        super().__init__(t)
        self.ha_priorita = None            # chi ha la priorita' adesso (None: nessuno, 117.2e, 502.4)
        self.in_attesa = []                # gli inneschi in attesa di andare in pila (603.3): il passo 7

    # ------------------------------------------------------------------ quando si puo'
    def da_stregoneria(self, i):
        """307.5: la priorita', la propria fase principale, la pila vuota."""
        return self.ha_priorita == i and super().da_stregoneria(i)

    def da_istantaneo(self, i):
        """304.5, 117.1a: basta la priorita'."""
        return self.ha_priorita == i and not self.t.finita

    @staticmethod
    def _senza_testo(carta, regola):
        """Le carte finte non hanno testo. Una carta con testo vuole il passo 7: lampo (702.8), bersagli (601.2c), effetti."""
        if carta.car.get("testo"):
            raise NonCoperto(f"{regola}: {carta.nome} ha un testo, e gli effetti delle carte sono il passo 7")

    def puo_lanciare(self, i, ogg, x=0):
        c = ogg.carta
        if not (ogg.vivo and ogg in self.t.giocatori[i].mano) or "land" in c.tipi: return False   # 305.9
        self._senza_testo(c, "117.1a")
        if "instant" in c.tipi: quando = self.da_istantaneo(i)                                     # 117.1a, 304.1
        elif c.permanente or "sorcery" in c.tipi: quando = self.da_stregoneria(i)                 # 117.1a, 307.1, 302.1
        else: return False
        return quando and self.piano(i, c.car.get("costo"), x) is not None                         # 601.2h

    # ------------------------------------------------------------------ le azioni
    def lancia(self, i, ogg, x=0, pagamento=None):
        """601.2: la magia in pila e il costo pagato (601.2a-h); poi e' lanciata e chi aveva la priorita' la tiene
        (601.2i, 117.3c). -> la magia in pila, o None se il lancio e' illegale (niente si e' mosso, 734.1)."""
        magia = self._metti_e_paga(i, ogg, x, pagamento)
        if magia is not None:
            self.t._evento("lanciata", carta=magia.carta, vecchio=magia.n, giocatore=i, quanto=len(self.t.pila),
                           causa="601.2i")
        return magia

    def esegui(self, i, azione):
        """L'azione del giocatore che ha la priorita'. -> True se e' successa, False se era illegale (734.1)."""
        if self.ha_priorita != i: return False
        tipo = azione[0]
        if tipo == "terra": return self.gioca_terra(i, azione[1]) is not None                    # 116.2a
        if tipo == "lancia":
            x = azione[2] if len(azione) > 2 else 0
            return self.lancia(i, azione[1], x or 0, azione[3] if len(azione) > 3 else None) is not None
        if tipo == "mana":                                                                         # 117.1d, 605.3a
            return self.tappa_per_mana(i, azione[1], azione[2] if len(azione) > 2 else None)
        raise ValueError(f"azione sconosciuta: {azione!r}")

    def contrasta(self, magia, causa="701.6a"):
        """701.6a: la magia lascia la pila e va nel cimitero del proprietario (400.3), senza risolversi; 701.6b: niente
        di quello che e' stato pagato torna. -> la carta nel cimitero, None se non e' (piu') in pila."""
        if not (magia.vivo and magia.zona == "pila"): return None
        return self.t.sposta(magia, "cimitero", causa=causa)

    # ------------------------------------------------------------------ la risoluzione
    def _cima(self):
        return self.t.pila[-1]                                                                     # 405.2, 405.5

    def risolvi(self):
        """608.1: si risolve la cima della pila. Nessuno ha la priorita' mentre si risolve (117.2e). -> dove e' finita."""
        t, magia = self.t, self._cima()
        c = magia.carta
        self._senza_testo(c, "608.2c")
        self.ha_priorita = None                                                                    # 117.2e
        t._evento("risolve", carta=c, vecchio=magia.n, giocatore=magia.controllore, quanto=len(t.pila), causa="608.1")
        if c.permanente: dove = t.sposta(magia, "campo", chi=magia.controllore, causa="608.3a")    # 608.3a
        else: dove = t.sposta(magia, "cimitero", causa="608.2n")                                   # 608.2n, 304.2, 307.2
        self.lanciate[(t.turno_numero, magia.controllore)] += 1
        return dove

    # ------------------------------------------------------------------ la priorita'
    def priorita(self):
        """117.5, 704.3: prima di ogni priorita' le azioni di stato finche' ce n'e', poi gli inneschi in pila, e si
        ripete. -> le azioni di stato fatte."""
        fatte = self.t.azioni_di_stato()
        if self.in_attesa:
            raise NonCoperto(f"603.3: {len(self.in_attesa)} inneschi in attesa; mettere in pila un'abilita' e' il passo 7")
        return fatte

    def _in_gioco(self):
        return [g.i for g in self.t.giocatori if not g.perso]

    def _dopo(self, i):
        """117.3d: il prossimo in ordine di turno, saltando chi ha perso."""
        n = len(self.t.giocatori)
        for k in range(1, n + 1):
            j = (i + k) % n
            if not self.t.giocatori[j].perso: return j
        return i

    def _tutti_passato(self, passati):
        return passati >= len(self._in_gioco())                                                    # 117.4

    def _dopo_azione(self, passati):
        return 0                                                                                   # 117.4: «in succession»

    def _dopo_risoluzione(self, magia):
        return self.attivo                                                                         # 117.3b

    def finestra(self, giocatori):
        """La priorita' in un passo o in una fase: comincia l'attivo (117.3a). Chi ha la priorita' agisce o passa; se tutti
        passano in fila si risolve la cima (117.4, 405.5) e la priorita' torna all'attivo (117.3b); a pila vuota il passo
        finisce (500.2). -> quando il passo finisce o la partita e' finita."""
        t, chi, passati, illegali = self.t, self.attivo, 0, 0
        while True:
            self.priorita()                                                                        # 117.5
            if t.finita:
                self.ha_priorita = None                                                            # 104.1
                return
            self.ha_priorita = chi
            azione = giocatori[chi].agisci(self, chi)
            if azione is not None:
                if self.esegui(chi, azione):
                    passati, illegali = self._dopo_azione(passati), 0                              # 117.3c, 116.3, 405.6c
                    continue
                illegali += 1                                                                      # 734.2: la tiene chi l'aveva
                t._evento("illegale", giocatore=chi, a=azione[0], causa="734.1")
                if illegali > 1000: raise RuntimeError(f"il giocatore {chi} propone solo azioni illegali")
                continue
            riserva = t.giocatori[chi].riserva                                                     # 117.3d, 106.4b
            t._evento("passa", giocatore=chi, a=repr(riserva) if riserva.totale() else "", causa="117.3d")
            passati += 1
            if self._tutti_passato(passati):
                if not t.pila:
                    self.ha_priorita = None                                                        # 500.2
                    return
                magia = self._cima()
                self.risolvi()                                                                     # 405.5, 608.1
                chi, passati = self._dopo_risoluzione(magia), 0                                    # 117.3b
                continue
            chi = self._dopo(chi)                                                                  # 117.3d

    # ------------------------------------------------------------------ il turno
    def _priorita_del_passo(self, giocatori):
        self.finestra(giocatori)
        if self.t.pila and not self.t.finita:
            raise RuntimeError(f"500.2: il passo {self.fase}/{self.passo} finisce con {self.t.pila} in pila")

    def _pulizia(self, i, giocatore):
        """514.1-2, poi 514.3a: se le azioni di stato fanno qualcosa l'attivo riceve la priorita' e comincia un'altra
        pulizia, finche' una pulizia passa senza azioni di stato (704.3)."""
        while True:
            super()._pulizia(i, giocatore)                                                         # 514.1, 514.2
            if not self.priorita() or self.t.finita: return                                        # 514.3a, 704.3
            self.finestra(self.chi)
            if self.t.finita: return
            self._svuota_mana()                                                                    # 500.5: il passo finisce
            self.t._evento("passo", giocatore=i, da=self.fase, a=self.passo, causa="514.3a")


def nuova(seme, mazzo=mazzo_pila, decidi=None):
    t = Tavolo([mazzo(), mazzo()], seme=seme)
    inizia(t, decidi=decidi)
    return Partita(t)


# ====================================================================== le prove
class Fa:
    """Un giocatore di prova: agisci = f(p, i) -> azione o None; il diario segna chi riceve la priorita', dove, e con
    quante cose in pila."""

    def __init__(self, f=None, diario=None, scarta=None):
        self.f, self.diario, self._scarta = f, (diario if diario is not None else []), scarta

    def agisci(self, p, i):
        self.diario.append((p.t.turno_numero, p.fase, p.passo, i, len(p.t.pila)))
        return self.f(p, i) if self.f else None

    def scarta(self, p, i, mano, quante):
        return self._scarta(p, i, mano, quante) if self._scarta else mano[-quante:]


def prove_regole(P):
    """Le regole della pila e della priorita' una per una, su una Partita di classe P. -> [(nome, ok, dettaglio)]."""
    casi = []
    def caso(nome, ok, det=""): casi.append((nome, bool(ok), det))
    def partita(seme=1):
        """Il tavolo dopo l'inizio (103), con le mani rimesse in fondo al grimorio: ogni prova vede solo le carte che da'."""
        t = Tavolo([mazzo_pila(), mazzo_pila()], seme=seme)
        inizia(t, primo=0)
        for g in t.giocatori:
            for o in list(g.mano): t.sposta(o, "grimorio", posizione="fondo", causa="prova")
        return P(t)
    def dai(p, i, nome, campo=False):
        o = next(o for o in p.t.giocatori[i].grimorio.carte if o.nome == nome)
        p.t._togli(o)
        o = p.t._arriva(o, "grimorio", "mano", None, None, "prova")
        return p.t.metti_in_campo(o, chi=i) if campo else o
    def in_mano(p, i, nome):
        return next((o for o in p.t.giocatori[i].mano if o.nome == nome), None)
    def eventi(p, tipo): return [e for e in p.t.eventi if e.tipo == tipo]
    def una_volta(fatto, chiave, azione):
        """L'azione la prima volta che la si chiede, poi None."""
        if chiave in fatto: return None
        fatto.add(chiave)
        return azione

    # 117.3a, 117.3d, 117.4, 500.2, 502.4, 514.3: chi riceve la priorita' nel primo turno
    d = []; p = partita(); p.turno({0: Fa(diario=d), 1: Fa(diario=d)})
    visto = [(f, s, i) for _, f, s, i, _ in d]
    passi = [("iniziale", "mantenimento"), ("principale_1", None), ("combattimento", "inizio"),
             ("combattimento", "attaccanti"), ("combattimento", "fine"), ("principale_2", None), ("finale", "finale")]
    atteso = [(f, s, i) for f, s in passi for i in (0, 1)]
    caso("117.3a, 117.3d: in ogni passo la priorita' la riceve prima l'attivo, poi l'altro; nello stap e nella pulizia nessuno (502.4, 514.3)",
         visto == atteso, str(visto[:6]))
    caso("117.4, 500.2: tutti passano in fila a pila vuota e il passo finisce: due priorita' per passo, non una",
         len(d) == 14 and len(eventi(p, "passa")) == 14, f"{len(d)} priorita'")

    # 117.1a, 304.1, 608.2n, 304.2: l'istantaneo nel mantenimento dell'altro
    d, fatto = [], set()
    p = partita(); dai(p, 1, "Terra", True); ist = dai(p, 1, "Istantaneo")
    def risponde(p, i):
        if p.passo == "mantenimento": return una_volta(fatto, "i", ("lancia", ist, 0, None))
    p.turno({0: Fa(diario=d), 1: Fa(risponde, d)})
    zone = [(e.da, e.a, e.causa) for e in eventi(p, "zona") if e.carta is ist.carta][1:]
    caso("117.1a, 304.1: l'istantaneo si lancia nel mantenimento dell'altro, con la sola priorita'",
         zone[:1] == [("mano", "pila", "601.2a")] and any(s == "mantenimento" and i == 1 and n == 1 for _, _, s, i, n in d), str(zone))
    caso("608.2n, 304.2: risolto, l'istantaneo va nel cimitero del proprietario",
         zone[1:] == [("pila", "cimitero", "608.2n")] and [o.nome for o in p.t.giocatori[1].cimitero] == ["Istantaneo"], str(zone))

    # 117.1a, 307.1, 302.1, 734: stregonerie e permanenti solo nella propria fase principale, a pila vuota
    p = partita(); dai(p, 1, "Terra", True); dai(p, 1, "Stregoneria"); dai(p, 1, "Creatura")
    prima = {}
    def fuori_tempo(p, i):
        if p.passo != "mantenimento": return None
        if "s" not in prima: prima["s"] = p.t.stato(); return ("lancia", in_mano(p, 1, "Stregoneria"), 0, None)
        if "c" not in prima: prima["c"] = p.t.stato(); return ("lancia", in_mano(p, 1, "Creatura"), 0, None)
        prima.setdefault("dopo", p.t.stato())
    p.turno({0: Fa(), 1: Fa(fuori_tempo)})
    caso("117.1a, 307.1, 302.1: nel turno dell'altro stregoneria e creatura non si lanciano, e non si muove niente (734.1)",
         in_mano(p, 1, "Stregoneria") and in_mano(p, 1, "Creatura") and prima.get("s") == prima.get("c") == prima.get("dopo")
         and len(eventi(p, "illegale")) == 2, f"illegali: {len(eventi(p, 'illegale'))}")
    p = partita(); dai(p, 0, "Terra", True); dai(p, 0, "Terra", True); dai(p, 0, "Istantaneo"); dai(p, 0, "Creatura")
    esiti, fatto = [], set()
    def a_pila_piena(p, i):
        if p.fase != "principale_1": return None
        if not p.t.pila: return una_volta(fatto, "i", ("lancia", in_mano(p, 0, "Istantaneo"), 0, None))
        if "c" not in fatto:
            fatto.add("c"); esiti.append(p.puo_lanciare(0, in_mano(p, 0, "Creatura")))
            return ("lancia", in_mano(p, 0, "Creatura"), 0, None)
    p.turno({0: Fa(a_pila_piena), 1: Fa()})
    caso("117.1a, 307.5: con la propria magia in pila, nella propria fase principale, la creatura non si lancia",
         esiti == [False] and in_mano(p, 0, "Creatura") is not None, str(esiti))

    # 117.7, 405.2, 405.5, 117.3b, 117.3c, 117.4: le risposte, l'ordine, chi riceve la priorita'
    d, f0, f1 = [], set(), set()
    p = partita()
    for _ in range(2): dai(p, 0, "Terra", True)
    dai(p, 1, "Terra", True); dai(p, 0, "Creatura"); dai(p, 0, "Istantaneo"); dai(p, 1, "Istantaneo")
    def g0(p, i):
        if p.fase != "principale_1": return None
        if not p.t.pila: return una_volta(f0, "c", ("lancia", in_mano(p, 0, "Creatura"), 0, None))
        return una_volta(f0, "i", ("lancia", in_mano(p, 0, "Istantaneo"), 0, None))
    def g1(p, i):
        if p.fase == "principale_1" and p.t.pila: return una_volta(f1, "i", ("lancia", in_mano(p, 1, "Istantaneo"), 0, None))
    sotto = []
    p.t._evento_vero = p.t._evento
    def spia(tipo, **kw):
        if tipo == "zona" and kw.get("da") == "pila": sotto.append(p.ha_priorita)
        return p.t._evento_vero(tipo, **kw)
    p.t._evento = spia
    p.turno({0: Fa(g0, d), 1: Fa(g1, d)})
    risolte = [(e.carta.nome, e.giocatore) for e in eventi(p, "risolve")]
    caso("117.7, 405.2, 405.5: in risposta, l'ultima arrivata si risolve per prima",
         risolte == [("Istantaneo", 1), ("Istantaneo", 0), ("Creatura", 0)], str(risolte))
    seq = [(i, n) for _, f, _, i, n in d if f == "principale_1"]
    caso("117.3c, 601.2i: chi lancia tiene la priorita' (anche per rispondere a se stesso)",
         seq[:3] == [(0, 0), (0, 1), (0, 2)] and (1, 3) in seq, str(seq))
    caso("117.3b: dopo ogni risoluzione la priorita' torna all'attivo, anche se la magia risolta era dell'altro",
         seq[5:7] == [(0, 3), (0, 2)] and seq[8:9] == [(0, 1)] and seq[10:11] == [(0, 0)], str(seq))
    caso("117.4 «in fila»: dopo una risposta i passaggi si ricontano, e l'attivo puo' rispondere prima che la cima si risolva",
         seq[3:6] == [(1, 2), (1, 3), (0, 3)], str(seq))
    caso("117.3d, 117.4, 500.2: la sequenza intera della fase principale", seq == [(0, 0), (0, 1), (0, 2), (1, 2), (1, 3), (0, 3),
         (0, 2), (1, 2), (0, 1), (1, 1), (0, 0), (1, 0)], str(seq))
    caso("117.2e: mentre una magia si risolve nessuno ha la priorita'", len(sotto) == 3 and set(sotto) == {None}, str(sotto))
    caso("608.3a: la creatura risolta entra in campo sotto chi l'ha lanciata",
         any(o.nome == "Creatura" and o.controllore == 0 for o in p.t.campo))

    # 500.2, 608.3a, 608.2n, 307.2: dopo una risoluzione il passo continua e l'attivo lancia ancora
    p = partita()
    for _ in range(3): dai(p, 0, "Terra", True)
    for n in ("Creatura", "Artefatto", "Stregoneria"): dai(p, 0, n)
    def tre(p, i):
        if p.fase == "principale_1" and not p.t.pila:
            return next((("lancia", o, 0, None) for o in p.t.giocatori[0].mano if p.puo_lanciare(0, o)), None)
    p.turno({0: Fa(tre), 1: Fa()})
    passo_di = {e.n: None for e in p.t.eventi}
    corrente = None
    for e in p.t.eventi:
        if e.tipo == "passo": corrente = (e.da, e.a)
        passo_di[e.n] = corrente
    caso("500.2: dopo una risoluzione il passo non finisce, l'attivo lancia ancora: tre magie nella stessa fase principale",
         [passo_di[e.n] for e in eventi(p, "risolve")] == [("principale_1", "")] * 3)
    caso("307.2, 608.2n: la stregoneria risolta va nel cimitero; artefatto e creatura in campo (608.3a)",
         [o.nome for o in p.t.giocatori[0].cimitero] == ["Stregoneria"]
         and sorted(o.nome for o in p.t.campo if o.controllore == 0 and "land" not in o.carta.tipi) == ["Artefatto", "Creatura"])

    # 405.6c, 605.3b, 117.1d, 106.4b, 106.4: l'abilita' di mana
    d, fatto = [], set()
    p = partita(); terra = dai(p, 0, "Terra", True); dai(p, 0, "Creatura")
    def mana_poi(p, i):
        if p.fase != "principale_1": return None
        if "m" not in fatto: fatto.add("m"); return ("mana", terra, None)
        if p.t.giocatori[0].riserva.totale(): return una_volta(fatto, "c", ("lancia", in_mano(p, 0, "Creatura"), 0, None))
    p.turno({0: Fa(mana_poi, d), 1: Fa(diario=d)})
    seq = [(i, n) for _, f, _, i, n in d if f == "principale_1"]
    caso("405.6c, 605.3b, 117.1d: l'abilita' di mana non usa la pila e chi l'attiva tiene la priorita'; il mana paga la creatura",
         seq[:3] == [(0, 0), (0, 0), (0, 1)] and any(o.nome == "Creatura" for o in p.t.campo), str(seq))
    d, fatto = [], set()
    p = partita(); terra = dai(p, 0, "Terra", True)
    riserve = []
    def tappa_e_passa(p, i):
        if i == 0: riserve.append((p.fase, p.t.giocatori[0].riserva.totale()))
        if p.fase == "principale_1" and i == 0: return una_volta(fatto, "m", ("mana", terra, None))
    p.turno({0: Fa(tappa_e_passa), 1: Fa()})
    annunci = [e.a for e in eventi(p, "passa") if e.giocatore == 0 and e.a]
    caso("106.4b, 117.3d: chi passa con mana nella riserva lo annuncia; 106.4: a fine fase il mana si perde",
         annunci == ["{C}"] and ("combattimento", 0) in riserve and ("principale_1", 1) in riserve, f"{annunci} {riserve[:4]}")

    # 116.2a, 305.1: la terra solo a pila vuota, con la priorita'
    p = partita(); dai(p, 0, "Terra", True); dai(p, 0, "Terra"); dai(p, 0, "Istantaneo")
    esiti, fatto = [], set()
    def terra_in_pila(p, i):
        if p.fase != "principale_1": return None
        if not p.t.pila and "i" not in fatto: fatto.add("i"); return ("lancia", in_mano(p, 0, "Istantaneo"), 0, None)
        if p.t.pila and "t" not in fatto:
            fatto.add("t"); esiti.append(p.puo_giocare_terra(0, in_mano(p, 0, "Terra"))); return ("terra", in_mano(p, 0, "Terra"))
        if not p.t.pila and in_mano(p, 0, "Terra"): esiti.append("dopo"); return ("terra", in_mano(p, 0, "Terra"))
    p.turno({0: Fa(terra_in_pila), 1: Fa()})
    caso("116.2a, 305.1: con l'istantaneo in pila la terra non si gioca; risolto, si'",
         esiti == [False, "dopo"] and in_mano(p, 0, "Terra") is None and len(eventi(p, "illegale")) == 1, str(esiti))

    # 117.5, 704.3: le azioni di stato prima di ogni priorita'
    p = partita(); pw = dai(p, 0, "Planeswalker", True)
    visto = []
    def azzera(p, i):
        if p.passo == "mantenimento" and i == 0: pw.segnalini["fedelta"] = 0
    def guarda(p, i):
        if p.passo == "mantenimento": visto.append(pw.vivo)
    p.turno({0: Fa(azzera), 1: Fa(guarda)})
    caso("117.5, 704.3: prima che l'altro riceva la priorita' le azioni di stato: il planeswalker a 0 e' gia' nel cimitero (704.5i)",
         visto == [False], str(visto))

    # 514.3a: un'azione di stato nella pulizia
    d = []
    p = partita(); cr = dai(p, 0, "Creatura", True)
    for _ in range(8): dai(p, 0, "Terra")
    def scarta_e_rompe(p, i, mano, quante):
        cr.carta.car["costituzione"] = 0                       # un effetto che arriva con le carte vere: qui lo si forza
        return mano[-quante:]
    p.turno({0: Fa(diario=d, scarta=scarta_e_rompe), 1: Fa(diario=d)})
    pulizie = [e.causa for e in eventi(p, "passo") if e.a == "pulizia"]
    caso("514.3a: un'azione di stato nella pulizia da' la priorita' all'attivo, poi comincia un'altra pulizia",
         not cr.vivo and [(s, i) for _, _, s, i, _ in d if s == "pulizia"] == [("pulizia", 0), ("pulizia", 1)]
         and pulizie == ["500.1", "514.3a"], f"{pulizie} {[x for x in d if x[2] == 'pulizia']}")

    # 701.6a, 701.6b: contrastare
    p = partita(); terra = dai(p, 0, "Terra", True); cr = dai(p, 0, "Creatura")
    fatto = set()
    def lancia_c(p, i):
        if p.fase == "principale_1": return una_volta(fatto, "c", ("lancia", in_mano(p, 0, "Creatura"), 0, None))
    def contrasta(p, i):
        if p.t.pila and "x" not in fatto: fatto.add("x"); p.contrasta(p.t.pila[-1])   # l'effetto di un contromagia (passo 7)
    p.turno({0: Fa(lancia_c), 1: Fa(contrasta)})
    ultimo = [(e.da, e.a, e.causa) for e in eventi(p, "zona") if e.carta is cr.carta][-1]
    caso("701.6a, 701.6b: contrastata, la magia va nel cimitero del proprietario senza risolversi, e la terra resta tappata",
         ultimo == ("pila", "cimitero", "701.6a") and not eventi(p, "risolve") and terra.tappato
         and [o.nome for o in p.t.giocatori[0].cimitero] == ["Creatura"], str(ultimo))

    # 734.1, 734.2: il lancio illegale
    d, prima = [], []
    p = partita(); dai(p, 0, "Creatura")
    def senza_mana(p, i):
        if p.fase == "principale_1" and not prima:
            prima.append(p.t.stato()); return ("lancia", in_mano(p, 0, "Creatura"), 0, None)
        if p.fase == "principale_1" and len(prima) == 1: prima.append(p.t.stato())
    p.turno({0: Fa(senza_mana, d), 1: Fa(diario=d)})
    seq = [(i, n) for _, f, _, i, n in d if f == "principale_1"]
    caso("734.1, 734.2: il lancio illegale non muove niente e la priorita' resta a chi l'aveva",
         len(prima) == 2 and prima[0] == prima[1] and seq[:2] == [(0, 0), (0, 0)], str(seq))

    # 104.1: a partita finita nessuno ha piu' la priorita'
    d = []
    p = partita()
    def arrende(p, i):
        if p.passo == "mantenimento": p.t.perdi(0, 20)
    p.turno({0: Fa(arrende, d), 1: Fa(diario=d)})
    caso("104.1, 704.5a: a 0 vite la partita finisce prima della priorita' dopo, e nessuno la riceve piu'",
         p.t.finita and p.t.vincitore == 1 and len(d) == 1 and p.ha_priorita is None, str(d))

    # i buchi dichiarati: carte con testo e inneschi sono il passo 7
    p = partita(); dai(p, 0, "Terra", True); ist = dai(p, 0, "Istantaneo"); ist.carta.car["testo"] = "Draw a card."
    p.ha_priorita = 0
    try: p.puo_lanciare(0, ist); esito = "nessun errore"
    except NonCoperto as e: esito = str(e)
    caso("608.2c, passo 7: una carta con testo non si lancia a caso, esce NonCoperto", esito.startswith("117.1a"), esito)
    p = partita(); p.in_attesa.append("un innesco")
    try: p.priorita(); esito = "nessun errore"
    except NonCoperto as e: esito = str(e)
    caso("603.3, passo 7: un innesco in attesa esce NonCoperto", esito.startswith("603.3"), esito)
    return casi


# ====================================================================== la vigilanza sulle partite a caso
def tempo_legale(tipi, i, attivo, fase, in_pila):
    """117.1a scritta un'altra volta, indipendente dal motore: quando un giocatore puo' lanciare una carta di quei tipi."""
    if "instant" in tipi: return True
    return i == attivo and fase in ("principale_1", "principale_2") and in_pila == 0


def vigila(P):
    """Una Partita di classe P che controlla tutto dopo ogni azione: invarianti del tavolo, azioni illegali senza effetto
    (734.1), tempi di lancio (117.1a), mana prodotto = speso + perso (106.4)."""
    class Vigila(P):
        def __init__(self, t):
            super().__init__(t)
            self.err, self.conti, self.prodotto, self.perso = [], Counter(), 0, 0

        def _sbaglia(self, msg):
            if len(self.err) < 3: self.err.append(f"turno {self.t.turno_numero}: {msg}")

        def esegui(self, i, azione):
            prima = (self.t.stato(), tuple(g.riserva.tupla() for g in self.t.giocatori))
            contesto = (i, self.attivo, self.fase, len(self.t.pila))
            ok = super().esegui(i, azione)
            if not ok:
                self.conti["illegali"] += 1
                if (self.t.stato(), tuple(g.riserva.tupla() for g in self.t.giocatori)) != prima:
                    self._sbaglia(f"l'azione illegale {azione[0]} ha cambiato il tavolo (734.1)")
                return ok
            self.conti[azione[0]] += 1
            if azione[0] == "lancia":
                tipi = azione[1].carta.tipi | ({"instant"} if "flash" in azione[1].carta.car.get("parole", ()) else set())   # 702.8a
                if not tempo_legale(tipi, *contesto): self._sbaglia(f"{azione[1]} lanciata fuori tempo {contesto} (117.1a)")
                if contesto[3]: self.conti["in risposta"] += 1
                if i != self.attivo: self.conti["nel turno dell'altro"] += 1
            e = controlla(self.t)
            if e: self._sbaglia(e[0])
            return ok

        def tappa_per_mana(self, i, terra, prod=None):
            prima = self.t.giocatori[i].riserva.totale()
            ok = super().tappa_per_mana(i, terra, prod)
            self.prodotto += self.t.giocatori[i].riserva.totale() - prima
            return ok

        def _svuota_mana(self):
            self.perso += sum(g.riserva.totale() for g in self.t.giocatori)
            super()._svuota_mana()
    return Vigila


def pila_dagli_eventi(t):
    """La pila ricostruita dagli eventi, indipendente dal motore: chi esce dalla pila deve essere la cima (405.5: in
    queste partite nessuno contrasta), e ogni passo comincia a pila vuota (500.2). -> gli errori."""
    pila, err = [], []
    for e in t.eventi:
        if e.tipo == "passo" and pila: err.append(f"evento {e.n}: il passo {e.da}/{e.a} comincia con {len(pila)} in pila (500.2)")
        if e.tipo != "zona": continue
        if e.a == "pila": pila.append(e.nuovo)
        if e.da == "pila":
            if not pila or pila[-1] != e.vecchio: err.append(f"evento {e.n}: esce {e.carta} che non e' la cima (405.5)")
            if e.vecchio in pila: pila.remove(e.vecchio)
    return err[:3]


def a_caso(P, seme, mazzo=mazzo_pila):
    t = Tavolo([mazzo(), mazzo()], seme=seme)
    inizia(t)
    p = vigila(P)(t)
    p.gioca({0: Caso(seme * 2 + 1), 1: Caso(seme * 2 + 2)})
    p.err += pila_dagli_eventi(t)
    for carta, pag, x, fonti, riserva in p.pagati:
        perche = M.valida(pag, carta.car["costo"], fonti, riserva, x)
        if perche: p._sbaglia(f"{carta}: pagamento illegale, {perche}")
    speso = sum(sum(pag.spesa) for _, pag, _, _, _ in p.pagati)
    if p.prodotto != speso + p.perso: p._sbaglia(f"mana prodotto {p.prodotto}, speso {speso}, perso {p.perso} (106.4)")
    return p


STESSI_TIPI = {"zona", "mana", "paga", "vite", "tappa", "stappa", "perde", "turno", "passo", "resta", "cessa", "controllo"}


def chiavi(t):
    """Gli eventi che il passo 3 e il passo 5 hanno in comune, senza il numero d'ordine."""
    return [e.chiave()[1:] for e in t.eventi if e.tipo in STESSI_TIPI]


def prova():
    casi = []
    def caso(nome, ok, det=""): casi.append((nome, bool(ok), det))
    conta = Counter(v[0] for v in mazzo_pila())
    caso("il mazzo finto del passo 5: 17 terre, 6 istantanei, 1 stregoneria, 16 permanenti a costo {1}",
         len(mazzo_pila()) == 40 and conta["Terra"] == 17 and conta["Istantaneo"] == 6 and conta["Stregoneria"] == 1,
         str(dict(conta)))
    caso("il mazzo a due colori del passo 5 ha 40 carte, 17 terre, 5 istantanei e una stregoneria",
         len(mazzo_pila_colori()) == 40 and sum(1 for v in mazzo_pila_colori() if v[1] in ("Instant", "Sorcery")) == 6
         and sum(1 for v in mazzo_pila_colori() if "Land" in v[1]) == 17)
    for nome, ok, det in prove_regole(Partita): caso(nome, ok, det)

    # senza risposte il passo 5 gioca la stessa partita del passo 3, mossa per mossa
    diverse = []
    for s in range(20):
        t = Tavolo([mazzo_draft_generico(), mazzo_draft_generico()], seme=s); inizia(t)
        a = T.Partita(t); a.gioca({0: T.GiocaTutto(), 1: T.GiocaTutto()})
        b = nuova(s, mazzo=mazzo_draft_generico); b.gioca({0: GiocaSubito(), 1: GiocaSubito()})
        if chiavi(a.t) != chiavi(b.t) or a.t.stato() != b.t.stato() or b.t.turno_numero != 68: diverse.append(s)
    caso("senza risposte il passo 5 gioca la stessa partita del passo 3: 20 partite, stessi eventi, stessa fine al turno 68",
         not diverse, f"semi diversi: {diverse}")

    # le partite a caso, con risposte e tentativi illegali
    alte = {}
    for nome, mazzo in (("finto", mazzo_pila), ("a due colori", mazzo_pila_colori)):
        tot, err, alta = Counter(), [], 0
        for s in range(20):
            p = a_caso(Partita, s, mazzo)
            tot += p.conti
            alta = max([alta] + [e.quanto for e in p.t.eventi if e.tipo == "lanciata"])
            err += [f"seme {s}: {e}" for e in p.err]
        caso(f"20 partite a caso col mazzo {nome}: tavolo sano, pila LIFO, passi a pila vuota, lanci a tempo, mana che torna, "
             f"illegali senza effetto", not err and tot["in risposta"] >= 10 and tot["nel turno dell'altro"] >= 20
             and tot["illegali"] >= 100 and tot["mana"] >= 20,
             "; ".join(err[:2]) or f"{dict(tot)}, pila piu' alta {alta}")
        alte[nome] = alta
    caso("nelle 40 partite a caso la pila arriva almeno a tre magie (catene di risposte)", max(alte.values()) >= 3, str(alte))
    a, b = a_caso(Partita, 5), a_caso(Partita, 5)
    caso("stesso seme, stessa partita (anche con le risposte)", a.t.stato() == b.t.stato()
         and [e.chiave() for e in a.t.eventi] == [e.chiave() for e in b.t.eventi])

    # le prove negative: motori rotti apposta, la regola giusta deve risultare rossa
    class PilaFIFO(Partita):                    # risolve la magia in fondo alla pila
        def _cima(self): return self.t.pila[0]
    class AlLanciatore(Partita):                # dopo la risoluzione la priorita' va a chi aveva lanciato
        def _dopo_risoluzione(self, magia): return magia.controllore
    class UnoBasta(Partita):                    # basta che passi uno e il passo finisce
        def _tutti_passato(self, passati): return passati >= 1
    class NonInFila(Partita):                   # dopo un'azione i passaggi non si ricontano
        def _dopo_azione(self, passati): return passati
    class TuttoIstantaneo(Partita):             # ogni carta si lancia come un istantaneo
        def da_stregoneria(self, i): return self.ha_priorita == i and not self.t.finita
    class SenzaStato(Partita):                  # niente azioni di stato prima della priorita'
        def priorita(self): return []
    for nome, P, cerca in (("la pila risolve la carta in fondo", PilaFIFO, "117.7"),
                           ("la priorita' va a chi aveva lanciato", AlLanciatore, "117.3b"),
                           ("il passo finisce quando passa uno", UnoBasta, "500.2"),
                           ("i passaggi non si ricontano dopo un'azione", NonInFila, "«in fila»"),
                           ("stregonerie e creature come istantanei", TuttoIstantaneo, "307.1"),
                           ("niente azioni di stato prima della priorita'", SenzaStato, "117.5")):
        rosse = [n for n, ok, _ in prove_regole(P) if not ok]
        caso(f"prova negativa: {nome} risulta rosso", any(cerca in n for n in rosse), "; ".join(r[:60] for r in rosse[:3]) or "nessuna regola rossa")
    for nome, P, cerca in (("pila FIFO", PilaFIFO, "405.5"), ("stregonerie come istantanei", TuttoIstantaneo, "117.1a")):
        err = [e for s in range(3) for e in a_caso(P, s).err]
        caso(f"prova negativa sulle partite a caso: {nome} la trova la vigilanza", any(cerca in e for e in err), "; ".join(err[:1]))

    for nome, ok, det in casi:
        print(f"  {'ok   ' if ok else 'ROSSO'} {nome}" + (f"  [{det}]" if det else ""))
    print(f"{sum(ok for _, ok, _ in casi)}/{len(casi)}")
    return 0 if all(ok for _, ok, _ in casi) else 1


def racconta(seme=1):
    """Una partita fra due Caso, una riga per turno: magie risolte, risposte, magie nel turno dell'altro."""
    t = Tavolo([mazzo_pila(), mazzo_pila()], seme=seme)
    inizia(t)
    p = vigila(Partita)(t)
    print(f"seme {seme}: comincia G{t.primo + 1}")
    visti = [0]
    def riga(p):
        nuovi = p.t.eventi[visti[0]:]; visti[0] = len(p.t.eventi)
        lanciate = [e for e in nuovi if e.tipo == "lanciata"]
        risposte = sum(1 for e in lanciate if e.quanto > 1)
        altro = sum(1 for e in lanciate if e.giocatore != p.ultimo)
        risolte = sum(1 for e in nuovi if e.tipo == "risolve")
        print(f"  T{p.t.turno_numero:>2} G{p.ultimo + 1}: lanciate {len(lanciate)} (in risposta {risposte}, dall'altro {altro}), "
              f"risolte {risolte}, vite {p.t.giocatori[0].vite}-{p.t.giocatori[1].vite}")
    p.gioca({0: Caso(seme * 2 + 1), 1: Caso(seme * 2 + 2)}, dopo_ogni_turno=riga)
    print(f"fine al turno {t.turno_numero}: " + (f"vince G{t.vincitore + 1}" if t.vincitore is not None else "pari")
          + (f"; ERRORI: {p.err}" if p.err else ""))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if "--prova" in sys.argv: sys.exit(prova())
    if "--partita" in sys.argv:
        k = sys.argv.index("--partita")
        racconta(int(sys.argv[k + 1]) if len(sys.argv) > k + 1 else 1)
    else: print(__doc__)
