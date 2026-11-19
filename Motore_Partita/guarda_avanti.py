"""Il passo 8.2 del motore di partita: guardare avanti (14 ott 2026).

Il piano e' nell'handoff (HANDOFF_Motore_Partita.md, §5, passo 8.2). Il motore e' a callback: i giocatori sono chiamati da
DENTRO il turno, quindi una partita a meta' di una scelta non si copia. La strada e' il replay deterministico:
  1. `Registro`: un involucro di giocatore che segna sul `Nastro` ogni risposta a ogni gancio (agisci, attacca, blocca,
     assegna, bersagli, modi, sceglie, ordina, scarta, mulligan, fondo e le scelte che il tavolo chiede con
     effetti._scelta), con gli oggetti codificati per posizione negli argomenti o per numero (o.n);
  2. `Replay`: rifa' la stessa partita dallo stesso seme rispondendo dal nastro; a ogni chiamata controlla l'impronta
     (chi, quale gancio, quanti eventi sul tavolo): se la partita rifatta va per un'altra strada, `Divergenza`;
  3. il punto di scelta: rifatta la partita fino alla scelta k, le carte che chi sceglie NON vede si rimescolano
     (`nascondi`: mano e grimorio dell'avversario insieme, il proprio grimorio; 400.2, 401.3, 402.3) e si cambiano i semi
     del caso (le mescolate future e lo scarto a caso), poi si gioca la mossa candidata e il resto lo giocano due
     `simula.Semplice`. Ogni partita di prova ha l'arbitro acceso (CLAUDE.md di Magic_Arena, regola 3): se fischia, la
     scelta si ferma (`simula.ArbitroFischia`);
  4. `Cercatore`: a ogni scelta con piu' di una mossa sensata (agisci, anche col bersaglio della magia gia' scelto; attacca;
     blocca; il bersaglio singolo di un innesco) prova ogni
     candidata con N partite e sceglie quella che vince di piu' (a parita' quella del Semplice). Le N partite usano gli
     stessi mondi per ogni candidata (numeri casuali comuni: la differenza fra le candidate non e' rumore dei mondi).
Quello che il Cercatore sa e non sa: conosce la lista del mazzo e del sideboard dell'avversario (non l'ordine, non la
mano); dimentica anche quello che saprebbe davvero (le carte guardate con scry e rimesse sopra, una carta rivelata in mano
all'avversario): perde informazione, non ne ruba. Le carte a faccia in giu' in esilio non ci sono fra le 285 di FRA.

    py -I -X utf8 Motore_Partita/guarda_avanti.py --prova            le prove
    py -I -X utf8 Motore_Partita/guarda_avanti.py --metro A B R [--turni K] [--processi N]
                                                                     Cercatore contro Semplice, semi A-B, R prove a candidata
                                                                     (con --turni le prove si fermano K turni dopo: passo 8.5)
    py -I -X utf8 Motore_Partita/guarda_avanti.py --spazzata A B     tutte le candidate di ~1 scelta su 8 dei semi A-B, arbitro acceso
    py -I -X utf8 Motore_Partita/guarda_avanti.py --copia A B M      passo 8.6: le partite di prova di --troncate dalla copia e dal
                                                                     seme, evento per evento uguali, e i tempi a coppie
Il passo 8.6 (15 ott 2026): le partite di prova non rifanno piu' la partita dal seme. La partita all'inizio del turno
dell'ultima voce del nastro si fotografa una volta per processo (`foto`, `Foto`: copy.deepcopy fatto con pickle, con
`t.scegli` ricollegata alla copia) e ogni partita di prova parte da una sua copia, rifacendo dal nastro solo quel turno.
"""
import io
import json
import math
import numbers
import os
import pickle
import sys
import time
import types
from datetime import datetime

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # py -I non mette la cartella dello script nel percorso
import effetti as E
import simula as S

QUI = os.path.dirname(os.path.abspath(__file__))


class Divergenza(RuntimeError):
    """La partita rifatta dal nastro non e' la stessa: un'altra chiamata, un altro gancio, o un oggetto che non c'e'."""


# ====================================================================== codificare le risposte
def _e_partita(x):
    return hasattr(x, "t") and hasattr(x, "fase")


def _indice(args):
    """id(oggetto) -> il suo percorso negli argomenti della chiamata (le liste, le tuple, le chiavi e i valori dei dizionari),
    per ritrovare l'oggetto corrispondente nella partita rifatta. Gli insiemi non hanno un ordine: non si guardano."""
    out = {}
    def giro(x, via, prof):
        if prof > 5 or x is None or isinstance(x, (str, bytes, bool, numbers.Number)): return
        if isinstance(x, (list, tuple)):
            for k, v in enumerate(x): giro(v, via + (k,), prof + 1)
            return
        if isinstance(x, dict):
            for k, (kk, v) in enumerate(x.items()):
                giro(kk, via + (("k", k),), prof + 1)
                giro(v, via + (("v", k),), prof + 1)
            return
        if isinstance(x, (set, frozenset)) or _e_partita(x): return
        out.setdefault(id(x), via)
    for k, a in enumerate(args):
        if not _e_partita(a): giro(a, (k,), 0)
    return out


def codifica(x, idx):
    """La risposta di un gancio, senza oggetti vivi: ogni oggetto per posizione negli argomenti («@a») o per numero («@n»)."""
    if x is None or isinstance(x, (bool, str, float)): return x
    if isinstance(x, numbers.Integral): return int(x)
    if id(x) in idx: return ("@a", idx[id(x)])
    if isinstance(x, tuple): return ("@t", [codifica(v, idx) for v in x])
    if isinstance(x, list): return ("@l", [codifica(v, idx) for v in x])
    if isinstance(x, dict): return ("@d", [(codifica(k, idx), codifica(v, idx)) for k, v in x.items()])
    n = getattr(x, "n", None)
    if isinstance(n, numbers.Integral) and not isinstance(n, bool): return ("@n", int(n))
    raise TypeError(f"risposta non codificabile: {x!r} ({type(x).__name__})")


def _per_numero(t, n):
    o = getattr(t, "oggetti", {}).get(n)
    if o is not None: return o
    for x in list(t.pila) + list(t.campo) + list(t.esilio) + list(t.comando):
        if getattr(x, "n", None) == n: return x
    for g in t.giocatori:
        for x in list(g.mano) + list(g.cimitero) + list(g.grimorio.carte):
            if x.n == n: return x
    raise Divergenza(f"l'oggetto numero {n} non c'e' nella partita rifatta")


def decodifica(c, args, t):
    if not isinstance(c, tuple): return c
    tag, v = c
    if tag == "@a":
        x = args
        for passo in v:
            if isinstance(passo, tuple):
                quale, k = passo
                coppia = list(x.items())[k]
                x = coppia[0] if quale == "k" else coppia[1]
            else: x = x[passo]
        return x
    if tag == "@t": return tuple(decodifica(y, args, t) for y in v)
    if tag == "@l": return [decodifica(y, args, t) for y in v]
    if tag == "@d": return {decodifica(k, args, t): decodifica(y, args, t) for k, y in v}
    if tag == "@n": return _per_numero(t, v)
    raise Divergenza(f"codice sconosciuto {tag}")


def _tavolo(args):
    return next((a.t for a in args if _e_partita(a)), None)


def impronta(nome, args):
    """Dove avviene la chiamata: il gancio e, se c'e' la partita, quanti eventi ha il tavolo; per il mulligan (che non ha la
    partita) le carte della mano e quanti mulligan."""
    t = _tavolo(args)
    if t is not None: return (nome, len(t.eventi), t.turno_numero)
    return (nome,) + tuple(tuple(getattr(o, "n", None) for o in a) if isinstance(a, list) else a for a in args
                           if isinstance(a, (list, numbers.Integral)))


# ====================================================================== il registro e il replay
class Registro:
    """Il giocatore `dentro` (indice i), con ogni risposta segnata sul nastro comune ai due giocatori: (i, gancio,
    impronta, risposta codificata). Il posto si prende quando la chiamata comincia (una chiamata dentro un'altra viene
    dopo, come nella partita rifatta). Un gancio che il giocatore non ha resta assente (hasattr del motore)."""

    def __init__(self, dentro, i, nastro):
        self.dentro, self.i, self.nastro = dentro, i, nastro

    def __getattr__(self, nome):
        if nome.startswith("_"): raise AttributeError(nome)
        f = getattr(self.dentro, nome)
        if not callable(f): return f
        def chiama(*args):
            k = len(self.nastro)
            self.nastro.append(None)
            imp, idx = impronta(nome, args), _indice(args)
            r = f(*args)
            self.nastro[k] = (self.i, nome, imp, codifica(r, idx))
            return r
        return chiama


class Replay:
    """Risponde dal nastro (comune: `stato["cur"]` e' la prossima voce), controllando chi chiama, quale gancio e
    l'impronta. Arrivato alla voce `ferma` (se e' sua) chiama `punto(nome, args)` una volta; dopo, o finito il nastro, la
    risposta la da' `poi`. Quali ganci esistono lo dice `poi` (lo stesso tipo di giocatore della partita vera)."""

    def __init__(self, i, nastro, poi, stato, ferma=None, punto=None):
        self.i, self.nastro, self.poi, self.stato, self.ferma, self.punto = i, nastro, poi, stato, ferma, punto

    def __getattr__(self, nome):
        if nome.startswith("_"): raise AttributeError(nome)
        f = getattr(self.poi, nome)
        if not callable(f): return f
        def chiama(*args):
            st = self.stato
            k = st["cur"]
            if st.get("libero"): return f(*args)
            if k == self.ferma:                                               # il punto di scelta
                if self.punto is None: raise Divergenza(f"voce {k}: il punto di scelta e' dell'altro giocatore")
                st["cur"] += 1
                st["libero"] = True
                return self.punto(nome, args)
            if k >= len(self.nastro):                                         # nastro finito: risponde `poi`
                st["libero"] = True
                return f(*args)
            voce = self.nastro[k]
            if voce is None: raise Divergenza(f"voce {k}: il nastro e' vuoto qui (una chiamata non finita)")
            if (voce[0], voce[1], voce[2]) != (self.i, nome, impronta(nome, args)):
                raise Divergenza(f"voce {k}: il nastro dice {voce[:3]}, arriva {(self.i, nome, impronta(nome, args))}")
            st["cur"] += 1
            return decodifica(voce[3], args, _tavolo(args))
        return chiama


def registra(a, b, seme, g0, g1, **kw):
    """Una partita di simula.partita (arbitro acceso) col registro. kw: P, T, prepara di simula.partita (passano anche
    alle partite di prova del Cercatore). -> (partita, nastro)."""
    nastro = []
    r = [Registro(g0, 0, nastro), Registro(g1, 1, nastro)]
    for i, g in enumerate((g0, g1)):
        if isinstance(g, Cercatore): g.collega(a, b, seme, i, nastro, kw)
    return S.partita(a, b, seme, r[0], r[1], **kw), nastro


def rifai(a, b, seme, nastro, poi=None, **kw):
    """La stessa partita rifatta dal nastro. poi: i giocatori che rispondono a nastro finito (di norma due Semplice)."""
    poi = poi or [S.Semplice(), S.Semplice()]
    stato = {"cur": 0}
    g = [Replay(i, nastro, poi[i], stato) for i in (0, 1)]
    p = S.partita(a, b, seme, g[0], g[1], **kw)
    return p, stato


# ====================================================================== le carte che chi sceglie non vede
def nascondi(t, i, rng):
    """Il mondo come lo vede il giocatore i (400.2, 401.3, 402.3): il suo grimorio in un ordine nuovo; la mano e il
    grimorio dell'avversario rimescolati insieme (stesse posizioni, carte ridistribuite). Le carte si mettono in fila per
    numero prima di mescolarle, quindi il risultato dipende solo da QUALI carte sono nascoste e dal seme, mai da dove
    stavano davvero. Poi i semi del caso cambiano (le mescolate future, 701.24; lo scarto a caso, effetti._i_scarta):
    altrimenti chi sceglie conoscerebbe il futuro del seme vero. -> i numeri del caso usati (per le prove)."""
    for j, g in enumerate(t.giocatori):
        posti = list(g.grimorio.carte) + ([] if j == i else list(g.mano))
        carte = sorted((o.fisica for o in posti), key=lambda c: c.n)
        for o, k in zip(posti, rng.permutation(len(carte))): o.carta = carte[int(k)]
    for g in t.giocatori: g.grimorio.rng = np.random.Generator(np.random.PCG64(int(rng.integers(0, 2 ** 63 - 1))))
    t.seme = int(rng.integers(0, 2 ** 63 - 1))
    if hasattr(t, "_versione"): t._versione += 1                     # la cache dei livelli si rifa' (handoff, trappola)


def visibile(t, i):
    """Quello che il giocatore i vede: le zone pubbliche, la sua mano, quante carte ha l'avversario in mano e nel grimorio,
    vite e segnalini. Due tavoli con lo stesso `visibile` sono indistinguibili per i."""
    def zona(lst): return tuple((o.n, o.fisica.n, o.controllore, o.tappato, o.danno, tuple(sorted(o.segnalini.items()))) for o in lst)
    out = [zona(t.campo), zona(t.pila), zona(t.esilio), zona(t.comando), t.turno_numero]
    for j, g in enumerate(t.giocatori):
        out += [g.vite, zona(g.cimitero), len(g.grimorio.carte), len(g.mano)]
        if j == i: out.append(zona(g.mano))
    return tuple(out)


def nascoste(t, i):
    """Le carte che i non vede, posto per posto: (oggetto, carta)."""
    out = []
    for j, g in enumerate(t.giocatori):
        out += [(o.n, o.fisica.n) for o in g.grimorio.carte] + ([] if j == i else [(o.n, o.fisica.n) for o in g.mano])
    return out


# ====================================================================== una partita di prova
def esito(p, i):
    """1 vince i, 0 perde, 1/2 pari o finita per tempo."""
    if p.t.finita and p.t.vincitore is not None: return 1.0 if p.t.vincitore == i else 0.0
    return 0.5


def prova_mossa(a, b, seme, nastro, i, nome, mossa, mondo, baro=False, kw=None, guarda=None, via="copia"):
    """Rifa' la partita dal nastro fino alla scelta k = len(nastro) di i (il gancio «nome»); li', se non bara, il mondo
    come lo vede i (`nascondi` col seme `mondo`); la mossa candidata (codificata); poi due Semplice fino alla fine, con
    l'arbitro acceso. kw: P, T, prepara di simula.partita; guarda(t, prima, dopo): per le prove, il tavolo al punto di
    scelta con quello che i vede prima e dopo `nascondi`. -> l'esito per i.
    Il passo 8.5 (valuta.py): kw["turni"] = K ferma la partita di prova alla fine del K-esimo turno dopo quello della
    scelta (K = 0: alla fine di questo) e, se non e' finita, l'esito e' la probabilita' detta dalla valutazione del tavolo;
    kw["segna"] = True la gioca fino in fondo e da' (esito, {K: valutazione alla fine del turno della scelta + K}).
    Il passo 8.6: via="copia" (di norma) riparte da una copia della partita all'inizio del turno dell'ultima voce del
    nastro (`foto`, `copia`) e rifa' dal nastro solo quel pezzo; via="replay" rifa' tutto dal seme, come nell'8.2. Le due
    vie danno la stessa partita evento per evento (guarda_avanti.py --prova e --copia)."""
    p, turni, segna = partita_di_prova(a, b, seme, nastro, i, nome, mossa, mondo, baro, kw, guarda, via)
    if segna: return esito(p, i), dict(getattr(p, "_valori", {}))
    if turni is not None and not p.t.finita:
        if p.t.turno_numero < p._fino: raise Divergenza(f"la partita di prova si e' fermata al turno {p.t.turno_numero}, prima del {p._fino}")
        import valuta as V
        return V.modello(p._valuta_v).valuta(p, i)
    return esito(p, i)


def partita_di_prova(a, b, seme, nastro, i, nome, mossa, mondo, baro=False, kw=None, guarda=None, via="copia"):
    """La partita di prova di `prova_mossa`, giocata. -> (partita, turni, segna)."""
    poi = [S.Semplice(), S.Semplice()]
    stato = {"cur": 0}
    kw = dict(kw or {})
    turni, segna = kw.pop("turni", None), kw.pop("segna", False)
    versione = kw.pop("valuta", "v0")                 # passo 8.6: quale valutazione giudica le troncate (valuta.modello)
    def punto(nome_, args):
        if nome_ != nome: raise Divergenza(f"al punto di scelta arriva «{nome_}», non «{nome}»")
        if any(getattr(a, "_in_azione", 0) for a in args):
            raise Divergenza(f"il punto di scelta «{nome}» e' dentro un'azione: le carte nascoste non si rimescolano li' (734.1)")
        t = _tavolo(args)
        prima = (visibile(t, i), nascoste(t, i)) if guarda else None
        if not baro: nascondi(t, i, np.random.default_rng(mondo))
        if guarda: guarda(t, prima, (visibile(t, i), nascoste(t, i)))
        pp = next(x for x in args if _e_partita(x))
        pp._dal_turno = t.turno_numero
        pp._segna = i if segna else None
        pp._valuta_v = versione
        if turni is not None: pp._fino = t.turno_numero + turni
        return decodifica(mossa, args, t)
    k = len(nastro)
    f = foto(a, b, seme, nastro, k, kw) if via == "copia" else None
    if f is not None:                                                         # dalla copia a inizio turno, non dal seme
        kw["da"], stato["cur"] = f[0].copia(), f[1]
    g = [Replay(j, nastro, poi[j], stato, ferma=k, punto=punto if j == i else None) for j in (0, 1)]
    kw["P"] = _con_guardia(kw.get("P") or E.Partita)
    p = S.partita(a, b, seme, g[0], g[1], **kw)
    if stato["cur"] <= k: raise Divergenza(f"la partita rifatta non e' arrivata alla scelta {k}")
    return p, turni, segna


def _con_guardia(P, scatta=None):
    """La partita P che sa se sta eseguendo un'azione (lancio, attivazione, terra): il punto di scelta li' dentro e' un
    errore della ricerca, non del motore (vedi Cercatore._bersagli_lancio). Dal passo 8.5 si ferma alla fine del turno
    `_fino` (fissato al punto di scelta), e con `_segna` = i scrive la valutazione per i a ogni fine turno dopo la scelta.
    Dal passo 8.6, con `_scatta` = T, all'inizio del turno T (prima che cominci, nessun giocatore chiamato) lancia `Scatto`
    con se' stessa: e' la foto da cui ripartono le copie (`foto`)."""
    class Guardia(P):
        _in_azione = 0
        _fino = None
        _dal_turno = None
        _segna = None
        _valuta_v = "v0"
        _scatta = scatta
        def esegui(self, i, azione):
            self._in_azione += 1
            try: return super().esegui(i, azione)
            finally: self._in_azione -= 1
        def turno(self, giocatori):
            super().turno(giocatori)
            if self._segna is not None and self._dal_turno is not None and not self.t.finita:
                import valuta as V
                if not hasattr(self, "_valori"): self._valori = {}
                self._valori[self.t.turno_numero - self._dal_turno] = V.modello(self._valuta_v).valuta(self, self._segna)
        def gioca(self, giocatori, max_turni=500, dopo_ogni_turno=None):     # il ciclo di turno.Partita.gioca, piu' _fino
            while not self.t.finita and self.t.turno_numero < max_turni:
                if self._scatta is not None and self.t.turno_numero == self._scatta - 1: raise Scatto(self)
                self.turno(giocatori)
                if dopo_ogni_turno: dopo_ogni_turno(self)
                if self._fino is not None and self.t.turno_numero >= self._fino: break
            return self.t.vincitore
    return Guardia


# ====================================================================== la copia a inizio turno (passo 8.6)
class Scatto(Exception):
    """La partita rifatta e' arrivata all'inizio del turno da fotografare (Guardia._scatta)."""
    def __init__(self, p):
        super().__init__("scatto")
        self.p = p


RICOLLEGA = True          # solo per la prova negativa: False lascia `t.scegli` legata alla partita vecchia


class _Scrivi(pickle.Pickler):
    """Classi e funzioni per riferimento (come fa copy.deepcopy, che non le copia): anche quelle create dentro una funzione
    (l'Arbitro di simula.partita, la Guardia), che pickle da solo non sa scrivere."""
    def __init__(self, fh, tab):
        super().__init__(fh, protocol=5)
        self.tab = tab
    def persistent_id(self, o):
        if isinstance(o, (type, types.FunctionType, types.BuiltinFunctionType)):
            self.tab.append(o)
            return len(self.tab) - 1
        return None


class _Leggi(pickle.Unpickler):
    def __init__(self, fh, tab):
        super().__init__(fh)
        self.tab = tab
    def persistent_load(self, pid): return self.tab[pid]


class Foto:
    """Una partita presa fra un turno e l'altro (nessun gancio aperto: lo stack di Python non si copia), scritta una volta in
    memoria; ogni `copia()` e' una partita indipendente e uguale, il generatore del caso compreso. E' copy.deepcopy fatto
    con pickle: 1,8 ms a copia contro 9,0 ms (15 ott 2026, una partita al turno 9). `chi` (i giocatori del turno passato)
    non si scrive, il turno dopo lo rimette; la lambda di `t.scegli` si ricollega alla copia (effetti.Partita.collega_tavolo),
    altrimenti le scelte del tavolo (colore, behold) andrebbero ai giocatori della partita vecchia."""
    def __init__(self, p):
        chi = getattr(p, "chi", None)
        p.chi = None
        try:
            self.tab, fh = [], io.BytesIO()
            _Scrivi(fh, self.tab).dump(p)
            self.dati = fh.getvalue()
        finally: p.chi = chi

    def copia(self):
        q = _Leggi(io.BytesIO(self.dati), self.tab).load()
        q._scatta = None
        if RICOLLEGA: q.collega_tavolo()
        return q


def copia(p):
    """Una copia indipendente della partita p, presa fra un turno e l'altro (vedi Foto)."""
    return Foto(p).copia()


def _raggiungibili(x):
    """Gli oggetti raggiungibili da x per riferimento (gc), senza moduli e classi; delle funzioni si seguono solo le
    variabili chiuse (il codice e i globali sono del modulo)."""
    import gc
    visti, pila = {}, [x]
    while pila:
        o = pila.pop()
        if id(o) in visti or isinstance(o, (types.ModuleType, type)): continue
        visti[id(o)] = o
        if isinstance(o, types.FunctionType):
            pila.extend(c.cell_contents for c in (o.__closure__ or ()) if c.cell_contents is not None)
            continue
        pila.extend(gc.get_referents(o))
    return visti


def _mutabili_in_comune(x, y):
    """Per le prove: gli oggetti mutabili raggiungibili sia da x sia da y (le funzioni del modulo, condivise apposta come
    in copy.deepcopy, non contano: le loro variabili chiuse si'). Due partite indipendenti: nessuno."""
    rx, ry = _raggiungibili(x), _raggiungibili(y)
    atomi = (str, bytes, int, float, complex, bool, type(None), tuple, frozenset, range, types.FunctionType,
             types.BuiltinFunctionType, types.CodeType)
    return sorted(type(rx[n]).__name__ for n in rx.keys() & ry.keys() if not isinstance(rx[n], atomi))


_FOTO = {}                # in ogni processo: la chiave della partita -> [(turno, j, nastro[:j], partita a inizio turno)]
FOTO_MAX = 8


def _chiave_partita(a, b, seme, kw):
    """Quello che fa la partita: i mazzi, il seme e gli argomenti di simula.partita (le classi e le funzioni del modulo
    per riferimento, gli oggetti per contenuto; quello che non si serializza per identita', tenuto vivo dalla chiave)."""
    import pickle
    def k(v):
        try: return pickle.dumps(v, protocol=4)
        except Exception: return v
    return (k(a), k(b), seme, tuple(sorted((n, k(v)) for n, v in kw.items())))


def turno_della_voce(nastro, k):
    """Il turno dell'ultima voce del nastro prima di k che ha la partita (l'impronta (gancio, eventi, turno)); None se non
    ce n'e' (il mulligan). La scelta k viene in quel turno o dopo: la copia del suo inizio sta prima della scelta."""
    for v in reversed(nastro[:k]):
        imp = v[2] if v is not None else None
        if imp and len(imp) == 3 and isinstance(imp[1], int) and isinstance(imp[2], int) and imp[2] >= 1: return imp[2]
    return None


FOTO_CONTI = {"dalla cache": 0, "da una foto prima": 0, "dal seme": 0}


def foto(a, b, seme, nastro, k, kw, tipi=None):
    """La partita all'inizio del turno dell'ultima voce prima di k, rifatta dal nastro, e j = le voci usate fin li'. Dalla
    cache del processo se il nastro fino a j e' lo stesso; se no, dalla foto piu' vicina di un turno prima (o dal seme),
    rifacendo dal nastro i turni che mancano. None se la scelta viene prima del primo turno. -> (Foto, j); la foto
    non si gioca mai: si gioca una sua copia. tipi: le classi dei giocatori della partita vera (di norma due Semplice: il
    Cercatore risponde agli stessi ganci), perche' i ganci che esistono li dice il giocatore (Replay)."""
    T = turno_della_voce(nastro, k)
    if T is None: return None
    tipi = tipi or (S.Semplice, S.Semplice)
    lst = _FOTO.setdefault(_chiave_partita(a, b, seme, {**kw, "_tipi": tipi}), [])
    base = None
    for x in lst:
        tt, j, pref, f = x
        if tt > T or j > k or nastro[:j] != pref: continue
        if tt == T:
            lst.remove(x); lst.insert(0, x)
            FOTO_CONTI["dalla cache"] += 1
            return f, j
        if base is None or tt > base[0]: base = x
    FOTO_CONTI["da una foto prima" if base else "dal seme"] += 1
    stato = {"cur": base[1] if base else 0}
    poi = [tipi[0](), tipi[1]()]
    g = [Replay(j, nastro, poi[j], stato) for j in (0, 1)]
    kw2 = dict(kw)
    kw2["P"] = _con_guardia(kw.get("P") or E.Partita, scatta=T)
    if base is not None:
        kw2["da"] = q = base[3].copia()
        q._scatta = T
    try:
        S.partita(a, b, seme, g[0], g[1], **kw2)
        raise Divergenza(f"la partita rifatta non e' arrivata all'inizio del turno {T}")
    except Scatto as s: p = s.p
    j = stato["cur"]
    if stato.get("libero"): raise Divergenza(f"il nastro e' finito prima dell'inizio del turno {T}")
    p._scatta = None
    f = Foto(p)
    lst.insert(0, (T, j, list(nastro[:j]), f))
    del lst[FOTO_MAX:]
    return f, j


def rifai_dalla_copia(a, b, seme, nastro, k, poi=None, **kw):
    """La partita rifatta fino in fondo dal nastro intero, ripartendo dalla copia dell'inizio del turno della voce k-1 (la
    stessa foto delle partite di prova). poi: i giocatori a nastro finito (di norma due Semplice), del tipo della partita
    vera. -> (partita, j, stato)."""
    poi = poi or [S.Semplice(), S.Semplice()]
    f, j = foto(a, b, seme, nastro, k, kw, tipi=tuple(type(x) for x in poi))
    stato = {"cur": j}
    g = [Replay(i, nastro, poi[i], stato) for i in (0, 1)]
    kw = dict(kw)
    kw["P"] = _con_guardia(kw.get("P") or E.Partita)
    return S.partita(a, b, seme, g[0], g[1], da=f.copia(), **kw), j, stato


def _lavoro(arg):
    return prova_mossa(*arg)


# ====================================================================== il cercatore
class Cercatore:
    """Il giocatore che guarda avanti. Per i ganci cercati (agisci, attacca, blocca, il bersaglio singolo) raccoglie le
    mosse candidate (la prima e' quella del Semplice), e se sono piu' d'una le prova con `prove` partite ciascuna; per
    tutto il resto risponde il Semplice. pool: un multiprocessing.Pool per le partite di prova (None = qui).
    baro=True salta `nascondi`: la prova negativa (conosce la mano dell'avversario e l'ordine dei grimori)."""

    CERCATI = ("agisci", "attacca", "blocca", "bersagli")

    def __init__(self, seme=0, prove=12, max_candidate=6, pool=None, baro=False, cerca=CERCATI, turni=None, valuta="v0", margine=0.0):
        self.base = S.Semplice(seme)
        self.prove, self.max_candidate, self.pool, self.baro, self.cerca = prove, max_candidate, pool, baro, set(cerca)
        self.turni = turni                # passo 8.5: le partite di prova si fermano K turni dopo la scelta (valuta.py)
        self.valuta = valuta              # passo 8.6: la versione della valutazione che giudica le troncate (v0, v1...)
        self.margine = margine            # passo 8.6: la mossa del Semplice si lascia solo per un guadagno di almeno tanto a prova
        self.seme = seme
        self.contesto = None
        self.diario = []                  # (gancio, turno, candidate, punteggi, scelta)
        self._no = set()                  # mosse proposte e rifiutate dal motore (734): non si ripropongono li'
        self._ultima = None
        self._dichiarate = set()          # (turno, gancio): la dichiarazione di combattimento si cerca una volta
        self._attivate = {}               # (turno, oggetto, abilita') -> volte

    def collega(self, a, b, seme, i, nastro, kw=None):
        self.contesto = (a, b, seme, i, nastro, kw or {})

    def __getattr__(self, nome):
        if nome.startswith("_"): raise AttributeError(nome)
        return getattr(self.base, nome)

    # ------------------------------------------------------------------ la ricerca
    def _scegli(self, nome, cand):
        """cand: [(mossa viva, codificata)] -> la mossa viva migliore. Stessi mondi per ogni candidata."""
        a, b, seme, i, nastro, kw = self.contesto
        k = len(nastro) - 1                                                   # la voce di questa chiamata (gia' presa)
        prefisso = nastro[:k]
        if any(v is None for v in prefisso): return cand[0][0]               # dentro un'altra chiamata: niente ricerca
        mondi = [int(x) for x in np.random.default_rng([self.seme, k, 8202]).integers(0, 2 ** 63 - 1, size=self.prove)]
        lavori = [(a, b, seme, prefisso, i, nome, c, m, self.baro, self.kw_prova(kw)) for _, c in cand for m in mondi]
        esiti = self.pool.map(_lavoro, lavori, chunksize=1) if self.pool else [_lavoro(x) for x in lavori]
        punti = [sum(esiti[j * len(mondi):(j + 1) * len(mondi)]) for j in range(len(cand))]
        migliore = max(range(len(cand)), key=lambda j: (punti[j], -j))       # a parita' la prima (il Semplice)
        if self.margine and punti[migliore] - punti[0] < self.margine * len(mondi): migliore = 0    # dentro il rumore: il Semplice
        self.diario.append((nome, k, [c for _, c in cand], punti, migliore))
        return cand[migliore][0]

    def kw_prova(self, kw):
        """Gli argomenti delle partite di prova: quelli della partita, piu' i turni se si tronca (passo 8.5)."""
        kw = kw if self.turni is None else {**kw, "turni": self.turni}
        return kw if self.valuta == "v0" else {**kw, "valuta": self.valuta}       # con v0 gli argomenti di sempre

    def _codificate(self, mosse, args):
        idx = _indice(args)
        out, viste = [], set()
        for m in mosse:
            c = codifica(m, idx)
            chiave = json.dumps(c, sort_keys=True, default=str)
            if chiave in viste: continue
            viste.add(chiave); out.append((m, c))
        return out[:self.max_candidate]

    # ------------------------------------------------------------------ la priorita'
    def _chiave(self, p, o):
        return (p.t.turno_numero, p.fase, p.passo, o.n, len(p.t.pila))

    def agisci(self, p, i):
        if self._ultima is not None and any(e.tipo == "illegale" for e in p.t.eventi[self._ultima[1]:]):
            self._no.add(self._ultima[0])
        self._ultima = None
        base = self.base.agisci(p, i)
        if base is not None and self._chiave(p, base[1]) in self._no: base = None
        if "agisci" not in self.cerca or self.contesto is None: m = base
        else:
            cand = self._codificate([base] + self._mosse(p, i), (p, i))
            m = cand[0][0] if len(cand) == 1 else self._scegli("agisci", cand)
        if m is not None:
            self._ultima = (self._chiave(p, m[1]), len(p.t.eventi))
            if m[0] == "attiva": self._attivate[(p.t.turno_numero, m[1].n, m[2])] = self._attivate.get((p.t.turno_numero, m[1].n, m[2]), 0) + 1
        return m

    def _mosse(self, p, i):
        """Le mosse legali adesso (la regola la dice il motore): passare, una terra, una magia (con la X piu' grande),
        un'abilita' attivata che non sia di mana (al massimo tre volte per turno la stessa: un'opinione, contro i giri a
        vuoto). Una per nome di carta."""
        t = p.t
        out, nomi, bersagliate = [None], set(), []
        mie = list(t.giocatori[i].mano) + [o for o in t.esilio if p.permesso(i, o)] + list(t.giocatori[i].cimitero)
        for o in mie:
            if self._chiave(p, o) in self._no or o.carta is None: continue
            if "land" in o.carta.tipi:
                if ("terra", o.nome) not in nomi and p.puo_giocare_terra(i, o): nomi.add(("terra", o.nome)); out.append(("terra", o))
                continue
            x = (p.x_massimo(i, o) or 0) if "{X}" in (o.carta.car.get("costo") or "") else 0
            if ("lancia", o.nome, o.zona) not in nomi and p.puo_lanciare(i, o, x):
                nomi.add(("lancia", o.nome, o.zona)); out.append(("lancia", o, x, None))
                bersagliate += [("lancia", o, x, None, [[b]]) for b in self._bersagli_lancio(p, i, o)]
        for o in list(t.campo) + list(t.giocatori[i].mano) + list(t.giocatori[i].cimitero):
            if (o.controllore if o.zona == "campo" else o.proprietario) != i: continue
            for k, ab in t.abilita_di(o):
                if ab.get("tipo") != "attivata" or isinstance(ab.get("fedelta"), str): continue
                fa = ab.get("fa") or []
                if fa and all(d.get("fa") == "aggiungi_mana" for d in fa): continue
                if self._attivate.get((t.turno_numero, o.n, k), 0) >= 3: continue
                if ("attiva", o.nome, k) not in nomi and p.puo_attivare(i, o, k):
                    nomi.add(("attiva", o.nome, k)); out.append(("attiva", o, k))
        return out + bersagliate

    def _bersagli_lancio(self, p, i, o):
        """Il bersaglio di una magia si sceglie lanciandola (601.2c), quindi dentro l'azione: la ricerca lo sceglie PRIMA,
        come mossa intera («lancia» con i bersagli, che il motore accetta e controlla, 734). Cosi' le carte nascoste si
        rimescolano fuori da ogni azione: rimescolate a meta' di un lancio poi rifiutato, l'arbitro vedrebbe un'azione
        illegale che ha cambiato il tavolo (seme 26 del metro, 14 ott 2026). Solo le magie con un bersaglio singolo e
        senza modi; i bersagli possibili li dice il motore (115, 601.2c)."""
        car = o.carta.car
        reqs = car.get("bersagli") or []
        if len(reqs) != 1 or car.get("modi") or car.get("incanta") or reqs[0].get("quanti", 1) != 1                 or reqs[0].get("fino_a") or reqs[0].get("uno_per_tipo"): return []
        return list(p.candidati(reqs[0], i, None, o))[:5]

    # ------------------------------------------------------------------ il combattimento
    def attacca(self, p, i):
        base = self.base.attacca(p, i) or {}
        chiave = (p.t.turno_numero, "attacca")
        if "attacca" not in self.cerca or self.contesto is None or chiave in self._dichiarate: return base
        self._dichiarate.add(chiave)
        mie = [o for o in p.t.campo if o.controllore == i and p.puo_attaccare(o)]
        if not mie: return base
        d = p.difensore()
        mosse = [base, {}, {o: d for o in mie}]
        for o in sorted(mie, key=lambda o: -S.forza(o)):
            m = dict(base)
            if o in m: del m[o]
            else: m[o] = d
            mosse.append(m)
        cand = self._codificate(mosse, (p, i))
        return cand[0][0] if len(cand) == 1 else self._scegli("attacca", cand)

    def blocca(self, p, i):
        base = self.base.blocca(p, i) or {}
        chiave = (p.t.turno_numero, "blocca")
        if "blocca" not in self.cerca or self.contesto is None or chiave in self._dichiarate: return base
        self._dichiarate.add(chiave)
        mie = [o for o in p.t.campo if o.controllore == i and "creature" in o.carta.tipi and not o.tappato]
        if not mie or not p.attaccanti: return base
        mosse = [base, {}]
        for b in list(base):                                                  # il blocco del Semplice con uno in meno
            m = dict(base); del m[b]; mosse.append(m)
        liberi = [b for b in mie if b not in base]
        for a in sorted(p.attaccanti, key=lambda a: -S.forza(a)):             # un blocco in piu': chi lo uccide, o il meno prezioso
            if a in base.values() or "menace" in S.parole(a): continue
            chi = [b for b in liberi if p.puo_bloccare(b, a)]
            if not chi: continue
            uccide = [b for b in chi if S.uccide(b, a)]
            b = min(uccide or chi, key=S.valore)
            m = dict(base); m[b] = a; mosse.append(m)
        cand = self._codificate(mosse, (p, i))
        return cand[0][0] if len(cand) == 1 else self._scegli("blocca", cand)

    # ------------------------------------------------------------------ i bersagli
    def bersagli(self, p, i, oggetto, reqs, legali, fa=()):
        base = self.base.bersagli(p, i, oggetto, reqs, legali, fa)
        if "bersagli" not in self.cerca or self.contesto is None: return base
        if not (isinstance(oggetto, E.Abilita) and oggetto.tipo == "innescata"): return base   # solo fuori da un'azione: l'innesco
        if len(reqs) != 1 or reqs[0].get("quanti", 1) != 1 or reqs[0].get("uno_per_tipo") or reqs[0].get("fino_a"): return base
        mosse = [base] + [[[x]] for x in legali[0]]
        cand = self._codificate(mosse, (p, i, oggetto, reqs, legali, fa))
        return cand[0][0] if len(cand) == 1 else self._scegli("bersagli", cand)


def nuovo_pool(n=None):
    import multiprocessing as mp
    return mp.get_context("spawn").Pool(n or max(1, (os.cpu_count() or 2) - 2))


# ====================================================================== il metro
def gioca_contro(s, mazzi, prove, baro=False, pool=None, cerca=Cercatore.CERCATI, turni=None):
    """Una partita del metro: il Cercatore col mazzo s % 10, il Semplice con (7s + 3) % 10 (come in simula.sfida: su 40
    semi ogni mazzo sta 4 volte da una parte e 4 dall'altra), il Cercatore al posto s % 2. -> (esito per il Cercatore,
    partita, Cercatore)."""
    a, b = s % len(mazzi), (s * 7 + 3) % len(mazzi)
    if a == b: b = (b + 1) % len(mazzi)
    io = s % 2
    m = [mazzi[a], mazzi[b]] if io == 0 else [mazzi[b], mazzi[a]]
    c = Cercatore(s * 2 + 1, prove=prove, pool=pool, baro=baro, cerca=cerca, turni=turni)
    g = [c, S.Semplice(s * 2 + 2)] if io == 0 else [S.Semplice(s * 2 + 2), c]
    p, nastro = registra(m[0], m[1], s, g[0], g[1])
    return esito(p, io), p, c


def metro(semi, prove, baro=False, scrivi=True, turni=None, processi=None):
    """turni = K: le partite di prova si fermano K turni dopo la scelta e le giudica la valutazione del tavolo (passo 8.5);
    la partita del metro si gioca comunque fino in fondo."""
    mazzi = S.mazzi_veri()
    pool = nuovo_pool(processi)
    t0, v, n, pari, cambi, scelte = time.time(), 0.0, 0, 0, 0, 0
    righe = []
    try:
        for s in semi:
            t1 = time.time()
            e, p, c = gioca_contro(s, mazzi, prove, baro, pool, turni=turni)
            if e == 0.5: pari += 1
            else: n += 1; v += e
            diverse = sum(1 for d in c.diario if d[4] != 0)
            cambi += diverse; scelte += len(c.diario)
            righe.append(f"seme {s}: {'vince' if e == 1 else 'perde' if e == 0 else 'pari'} al turno {p.t.turno_numero}, "
                         f"{len(c.diario)} scelte cercate, {diverse} diverse dal Semplice, {time.time() - t1:.0f} s")
            print(righe[-1], f"| finora {v:.0f}/{n}", flush=True)
    finally:
        pool.terminate()
    lo, hi = S.wilson(v, n)
    tr = f" troncate a {turni} turni dopo la scelta (valuta.py)" if turni is not None else ""
    sintesi = (f"{'Baro' if baro else 'Cercatore'} contro Semplice, {prove} partite di prova a candidata{tr}: {v:.0f}/{n} "
               f"({v / max(n, 1):.0%}, 95% {lo:.0%}-{hi:.0%}), pari o a tempo {pari}; scelte cercate {scelte}, diverse dal Semplice "
               f"{cambi}; {time.time() - t0:.0f} s")
    print(sintesi)
    if scrivi:
        f = os.path.join(QUI, "Metro_Guarda_Avanti.md")
        nuovo = not os.path.exists(f)
        with open(f, "a", encoding="utf-8") as h:
            if nuovo: h.write("# Il metro del guardare avanti (passo 8.2)\n\nOgni riga di sintesi e' una misura: "
                              "`py -I -X utf8 Motore_Partita/guarda_avanti.py --metro <primo seme> <ultimo seme> <prove> [--baro]`.\n"
                              "Una simulazione resta una simulazione: l'avversario e' il Semplice, non un giocatore vero.\n")
            h.write(f"\n## {datetime.now().strftime('%Y-%m-%d %H:%M')}, semi {semi[0]}-{semi[-1]}\n\n**{sintesi}**\n\n")
            for r in righe: h.write(f"- {r}\n")
    return v, n, pari


# ====================================================================== le prove
NOME_PROVA = "No Admittance"


def prepara_no_admittance(p):
    """La situazione della prova di senso: G1 comincia, con No Admittance in mano e due Mountain in campo; G2 a 3 vite
    con Keeper of the Quiet Hour (3/2) in campo. Il Semplice tira i 3 danni sulla creatura che muore; chi guarda avanti,
    al giocatore (e vince)."""
    t = p.t
    def dai(i, nome, campo):
        o = next(o for o in t.giocatori[i].grimorio.carte if o.nome == nome)
        t._togli(o)
        o = t._arriva(o, "grimorio", "mano", None, None, "prova")
        if campo: o = t.metti_in_campo(o, chi=i, causa="prova")
        p.in_attesa.clear()
        return o
    for g in t.giocatori:
        for o in list(g.mano): t.sposta(o, "grimorio", posizione="fondo", causa="prova")
    dai(0, NOME_PROVA, False); dai(0, "Mountain", True); dai(0, "Mountain", True)
    dai(1, "Keeper of the Quiet Hour", True)
    t.perdi(1, 17, causa="prova")
    t.primo = p.attivo = 0


class SenzaStato(E.Partita):
    """Motore rotto apposta: niente azioni di stato prima della priorita' (117.5, 704.3)."""
    def priorita(self): return []


def _rimescola_a_caso(t, i, seme):
    """Per le prove: una verita' diversa, le carte nascoste a i scambiate a caso fra i loro posti."""
    rng = np.random.default_rng(seme)
    for g in t.giocatori:
        pos = list(g.grimorio.carte) + ([] if g.i == i else list(g.mano))
        carte = [o.fisica for o in pos]
        for o, k in zip(pos, rng.permutation(len(carte))): o.carta = carte[int(k)]


def prova():
    from tavolo import controlla
    casi = []
    def caso(nome, ok, det=""): casi.append((nome, bool(ok), det))
    t0 = time.time()
    mazzi = S.mazzi_veri()
    def ch(p): return [(e.tipo, e.vecchio, e.nuovo, e.da, e.a, e.causa, e.giocatore, e.quanto) for e in p.t.eventi]
    def coppia(s): return mazzi[s % 10], mazzi[(s * 3 + 1) % 10]

    # 1. il registro non cambia la partita
    diverse = []
    for s in range(1, 11):
        a, b = coppia(s)
        if ch(S.partita(a, b, s, S.Semplice(s), S.Semplice(s + 100))) != ch(registra(a, b, s, S.Semplice(s), S.Semplice(s + 100))[0]):
            diverse.append(s)
    caso("il Registro non cambia la partita: 10 semi, evento per evento uguali a simula.partita", not diverse, f"diverse {diverse}")

    # 2. il replay: la stessa partita dal nastro, su 50 semi
    nastri, diverse, voci, ganci = {}, [], 0, set()
    for s in range(1, 51):
        a, b = coppia(s)
        p, nastro = registra(a, b, s, S.Semplice(s), S.Semplice(s + 100))
        q, st = rifai(a, b, s, nastro)
        nastri[s] = (p, nastro)
        voci += len(nastro); ganci |= {v[1] for v in nastro}
        if ch(p) != ch(q) or st["cur"] != len(nastro): diverse.append(s)
    caso("replay: 50 semi rifatti dal nastro, evento per evento uguali, ogni voce usata", not diverse,
         f"{voci} voci, ganci {sorted(ganci)}, diverse {diverse}")

    # 3. la prova negativa: una risposta spostata di uno = un'altra partita (o il nastro che non torna)
    rossi, come = [], []
    for s in range(1, 11):
        a, b = coppia(s)
        p, nastro = nastri[s]
        k = len(nastro) // 3
        while k + 1 < len(nastro) and (nastro[k][1] != "agisci" or nastro[k][3] == nastro[k + 1][3]): k += 1
        ag = [j for j in range(k, len(nastro)) if nastro[j][1] == "agisci"]           # le risposte ad agisci, spostate di uno
        storto = list(nastro)
        for j, j2 in zip(ag, ag[1:]): storto[j] = nastro[j][:3] + (nastro[j2][3],)
        try:
            q, _ = rifai(a, b, s, storto)
            rossi.append(ch(q) != ch(p)); come.append("altra partita")
        except Divergenza:
            rossi.append(True); come.append("divergenza")
    caso("prova negativa: le risposte ad agisci spostate di uno da un terzo del nastro danno un'altra partita (10 semi su 10)",
         all(rossi) and len(rossi) == 10, f"{sum(rossi)}/10: {dict((x, come.count(x)) for x in set(come))}")

    # 4. il replay in un altro processo (gli insiemi e gli id cambiano da un processo all'altro)
    pool = nuovo_pool(4)
    try:
        fuori = pool.map(_rifai_chiavi, [(coppia(s)[0], coppia(s)[1], s, nastri[s][1]) for s in range(1, 9)])
    finally: pool.terminate()
    diverse = [s for s, f in zip(range(1, 9), fuori) if f != ch(nastri[s][0])]
    caso("replay in un altro processo: 8 semi, evento per evento uguali", not diverse, f"diverse {diverse}")

    # 5. il punto di scelta: la partita rifatta arriva al tavolo vero (carte nascoste comprese); dopo `nascondi` chi
    # sceglie vede lo stesso tavolo, le carte nascoste sono altre e non dipendono da dove stavano davvero
    class Fotografa(Cercatore):
        def _scegli(self, nome, cand):
            if len(self.diario) < 3 and len(self.contesto[4]) > 40:
                t, i = self.ultimo_p.t, self.contesto[3]
                self.diario.append((nome, list(self.contesto[4][:-1]), cand, visibile(t, i), nascoste(t, i)))
            return cand[0][0]
        def agisci(self, p, i):
            self.ultimo_p = p
            return super().agisci(p, i)
    viste, stessi, nascosto, visto_uguale, sani, dipende = 0, [], [], [], [], []
    for s in (3, 4, 5):
        a, b = coppia(s)
        c = Fotografa(s, cerca=("agisci",))
        registra(a, b, s, c, S.Semplice(s + 100))
        for nome, pref, cand, vis, nas in c.diario:
            viste += 1
            def guarda(t, prima, dopo, vis=vis, nas=nas):
                stessi.append(prima == (vis, nas))
                visto_uguale.append(dopo[0] == vis)
                nascosto.append(dopo[1] != nas)
                sani.append(not controlla(t))
                _rimescola_a_caso(t, 0, 99); nascondi(t, 0, np.random.default_rng(7)); r_a = nascoste(t, 0)
                _rimescola_a_caso(t, 0, 5); nascondi(t, 0, np.random.default_rng(7))
                dipende.append(r_a == nascoste(t, 0))
            prova_mossa(a, b, s, pref, 0, nome, cand[0][1], 1234, guarda=guarda)
    caso("punto di scelta: la partita rifatta arriva al tavolo vero, carte nascoste comprese (9 punti in 3 partite)",
         viste == 9 and all(stessi) and len(stessi) == 9, f"{sum(stessi)}/{viste}")
    caso("nascondi: chi sceglie vede lo stesso tavolo (zone pubbliche, la sua mano, quante carte ha l'altro), il tavolo resta sano",
         all(visto_uguale) and all(sani) and len(sani) == 9, f"visto uguale {sum(visto_uguale)}, sani {sum(sani)}")
    caso("nascondi: le carte nascoste sono altre, e dipendono solo da quali sono, non da dove stavano davvero",
         all(nascosto) and all(dipende) and len(dipende) == 9, f"altre {sum(nascosto)}, indipendenti {sum(dipende)}")
    a, b = coppia(3)
    c = Fotografa(3, cerca=("agisci",)); registra(a, b, 3, c, S.Semplice(103))
    nome, pref, cand, vis, nas = c.diario[0]
    bari = []
    prova_mossa(a, b, 3, pref, 0, nome, cand[0][1], 1234, baro=True, guarda=lambda t, prima, dopo: bari.append(dopo[1] == nas))
    caso("prova negativa: il baro (senza nascondi) al punto di scelta ha le carte nascoste vere", bari == [True], f"{bari}")

    # 6. il senso della ricerca: No Admittance con l'avversario a 3 vite e un Keeper 3/2
    a = {"nome": "R", "mazzo": [NOME_PROVA] + ["Mountain"] * 39, "sideboard": []}
    b = {"nome": "B", "mazzo": ["Keeper of the Quiet Hour"] + ["Swamp"] * 39, "sideboard": []}
    kw = {"prepara": prepara_no_admittance}
    p_s, _ = registra(a, b, 1, S.Semplice(1), S.Semplice(2), **kw)
    fine1 = next((k for k, e in enumerate(p_s.t.eventi) if e.tipo == "turno" and e.quanto == 2), len(p_s.t.eventi))
    primo = p_s.t.eventi[:fine1]
    morto = any(e.tipo == "zona" and e.a == "cimitero" and e.carta is not None and e.carta.nome == "Keeper of the Quiet Hour" for e in primo)
    ferite = sum(-e.quanto for e in primo if e.tipo == "vite" and e.giocatore == 1 and e.causa != "prova")
    caso("senso: il Semplice tira No Admittance sul Keeper 3/2, che muore al primo turno; l'avversario resta a 3 vite",
         morto and ferite == 0, f"Keeper morto {morto}, vite perse da G2 nel primo turno {ferite}")
    c = Cercatore(1, prove=6, cerca=("agisci", "bersagli"))
    p_c, _ = registra(a, b, 1, c, S.Semplice(2), **kw)
    scelte = [d for d in c.diario if d[0] == "agisci"]
    presa = scelte[0][2][scelte[0][4]] if scelte else None
    caso("senso: il Cercatore lancia No Admittance gia' col bersaglio G2 (scelto in agisci) e vince al primo turno (6 su 6)",
         p_c.t.vincitore == 0 and p_c.t.turno_numero == 1 and scelte and max(scelte[0][3]) == 6 and presa and presa[1][4:] == [("@l", [("@l", [1])])],
         f"vincitore G{(p_c.t.vincitore or 0) + 1}, turno {p_c.t.turno_numero}, punti {scelte[0][3] if scelte else None}, mossa {presa}")
    class Vecchio(Cercatore):                       # la ricerca di prima: il bersaglio della magia cercato a meta' del lancio
        def bersagli(self, p, i, oggetto, reqs, legali, fa=()):
            base = self.base.bersagli(p, i, oggetto, reqs, legali, fa)
            cand = self._codificate([base] + [[[x]] for x in legali[0]], (p, i, oggetto, reqs, legali, fa))
            return cand[0][0] if len(cand) == 1 else self._scegli("bersagli", cand)
    try: registra(a, b, 1, Vecchio(1, prove=2, cerca=("bersagli",)), S.Semplice(2), **kw); dentro = None
    except Divergenza as e: dentro = str(e)
    caso("prova negativa: la ricerca del bersaglio a meta' del lancio (seme 26 del metro) si ferma sulla guardia, non arriva all'arbitro",
         dentro is not None and "dentro un'azione" in dentro, (dentro or "nessuna fermata")[:120])

    # 7. l'arbitro nelle partite di prova: un motore rotto apposta ferma la scelta
    a, b = coppia(4)
    c = Fotografa(4, cerca=("agisci",)); registra(a, b, 4, c, S.Semplice(104))
    nome, pref, cand, _, _ = c.diario[0]
    fischio = None
    for m in range(1, 6):
        try: prova_mossa(a, b, 4, pref, 0, nome, cand[0][1], m, kw={"P": SenzaStato})
        except S.ArbitroFischia as e: fischio = str(e); break
        except Divergenza as e: fischio = "divergenza: " + str(e); break
    caso("arbitro acceso nelle partite di prova: col motore rotto apposta (niente azioni di stato) la scelta si ferma",
         fischio is not None and not fischio.startswith("divergenza"), (fischio or "nessun fischio")[:140])
    cc = Cercatore(4, prove=2)
    cc.collega(a, b, 4, 0, pref + [None], {"P": SenzaStato})
    try: cc._scegli(nome, cand); fermo = False
    except (S.ArbitroFischia, Divergenza): fermo = True
    caso("il Cercatore non sceglie se una partita di prova fischia (l'errore esce, nessuna mossa)", fermo)

    # 8. partite intere Cercatore contro Semplice, con le partite di prova in altri processi, e il loro replay
    pool = nuovo_pool()
    try:
        fischi, finite, cercate, rifatte = [], 0, 0, 0
        for s in (1, 2):
            try:
                e, p, c = gioca_contro(s, mazzi, 4, pool=pool)
                finite += p.t.finita; cercate += len(c.diario)
                io = s % 2
                aa, bb = s % 10, (s * 7 + 3) % 10
                m = [mazzi[aa], mazzi[bb]] if io == 0 else [mazzi[bb], mazzi[aa]]
                q, st = rifai(m[0], m[1], s, c.contesto[4])
                rifatte += ch(q) == ch(p)
            except S.ArbitroFischia as x: fischi.append(str(x))
    finally: pool.terminate()
    caso("2 partite intere Cercatore contro Semplice (4 prove a candidata): finite, arbitro zitto, rifatte uguali dal nastro",
         finite == 2 and rifatte == 2 and not fischi, f"finite {finite}, rifatte {rifatte}, scelte cercate {cercate}, fischi {fischi[:1]}")
    # 9. le partite di prova troncate (passo 8.5, valuta.py)
    a, b = coppia(5)
    c = Fotografa(5, cerca=("agisci",)); registra(a, b, 5, c, S.Semplice(105))
    uguali_intere, uguali_k, fermate, valori, rossi = [], [], [], [], []
    for nome, pref, cand, vis, _ in c.diario:
        for m in (1, 2, 3):
            intera = prova_mossa(a, b, 5, pref, 0, nome, cand[0][1], m)
            e, val = prova_mossa(a, b, 5, pref, 0, nome, cand[0][1], m, kw={"segna": True})
            uguali_intere.append(e == intera)
            for k in (0, 1, 2):
                stop = {}
                class Ferma(E.Partita):                     # l'ultimo turno giocato dalla partita troncata
                    def turno(self, g):
                        super().turno(g); stop["turno"] = self.t.turno_numero
                v = prova_mossa(a, b, 5, pref, 0, nome, cand[0][1], m, kw={"turni": k, "P": Ferma})
                atteso = val[k] if k in val else e
                uguali_k.append(abs(v - atteso) < 1e-12)
                fermate.append(k not in val or stop["turno"] == vis[4] + k)
                valori.append(0 <= v <= 1)
                rossi.append(k + 1 in val and abs(v - val[k + 1]) > 1e-12)    # un turno in piu': un altro numero
    caso("troncate: segnare la valutazione non cambia la partita (stesso esito della partita di prova intera, 9 casi)",
         all(uguali_intere) and len(uguali_intere) == 9, f"{sum(uguali_intere)}/{len(uguali_intere)}")
    caso("troncate: la partita troncata a K (0, 1, 2) si ferma alla fine del turno della scelta + K e vale quanto la valutazione "
         "segnata li' nella partita intera (o il risultato, se e' finita prima)",
         all(uguali_k) and all(fermate) and all(valori) and len(uguali_k) == 27, f"uguali {sum(uguali_k)}/27, fermate giuste {sum(fermate)}/27")
    caso("prova negativa: la valutazione un turno dopo e' un altro numero (il confronto vede l'errore di un turno)",
         sum(rossi) >= 15, f"{sum(rossi)} su {len(rossi)} diversi")
    a = {"nome": "R", "mazzo": [NOME_PROVA] + ["Mountain"] * 39, "sideboard": []}
    b = {"nome": "B", "mazzo": ["Keeper of the Quiet Hour"] + ["Swamp"] * 39, "sideboard": []}
    c = Cercatore(1, prove=6, cerca=("agisci", "bersagli"), turni=1)
    p_c, _ = registra(a, b, 1, c, S.Semplice(2), prepara=prepara_no_admittance)
    scelte = [d for d in c.diario if d[0] == "agisci"]
    caso("senso, troncate a 1 turno: il Cercatore tira ancora No Admittance a G2 e vince al primo turno",
         p_c.t.vincitore == 0 and p_c.t.turno_numero == 1 and scelte and max(scelte[0][3]) == 6,
         f"vincitore G{(p_c.t.vincitore or 0) + 1}, turno {p_c.t.turno_numero}, punti {scelte[0][3] if scelte else None}")

    # 10. la copia a inizio turno (passo 8.6): la stessa partita del replay, la cache, una copia indipendente, la negativa
    _FOTO.clear()
    for x in FOTO_CONTI: FOTO_CONTI[x] = 0
    diverse, cache_div, fine_div, punti_c, tipi_kw = [], [], [], 0, ({}, {"turni": 3}, {"segna": True})
    for s in range(1, 51):
        a, b = coppia(s)
        p, nastro = nastri[s]
        cand = [k for k, v in enumerate(nastro) if v[1] in ("agisci", "attacca", "blocca") and turno_della_voce(nastro, k)]
        rng = np.random.default_rng([s, 8601])
        for k in sorted(int(x) for x in rng.choice(cand, size=3, replace=False)):
            i, nome, mossa = nastro[k][0], nastro[k][1], nastro[k][3]
            kw = tipi_kw[punti_c % 3]
            pr, _, _ = partita_di_prova(a, b, s, nastro[:k], i, nome, mossa, s * 7 + k, kw=kw, via="replay")
            pc, _, _ = partita_di_prova(a, b, s, nastro[:k], i, nome, mossa, s * 7 + k, kw=kw, via="copia")
            pc2, _, _ = partita_di_prova(a, b, s, nastro[:k], i, nome, mossa, s * 7 + k, kw=kw, via="copia")
            punti_c += 1
            if ch(pr) != ch(pc) or getattr(pr, "_valori", None) != getattr(pc, "_valori", None): diverse.append((s, k))
            if ch(pc2) != ch(pc): cache_div.append((s, k))
        q, j, st = rifai_dalla_copia(a, b, s, nastro, cand[len(cand) // 2])
        if ch(q) != ch(p) or st["cur"] != len(nastro) or j == 0: fine_div.append(s)
    caso("copia: 50 semi, 150 partite di prova (intere, troncate a 3 turni, segnate) dalla copia a inizio turno, evento per "
         "evento uguali a quelle rifatte dal seme, valutazioni comprese",
         not diverse and punti_c == 150, f"{punti_c} partite, diverse {diverse[:5]}")
    caso("copia: la foto presa dalla cache da' la stessa partita della foto appena fatta; usate tutte e tre le vie (cache, "
         "una foto di un turno prima, il seme)", not cache_div and all(FOTO_CONTI.values()), f"{FOTO_CONTI}, diverse {cache_div[:5]}")
    caso("copia: la partita rifatta fino in fondo dalla copia di un turno a meta' e' quella vera (50 semi), ogni voce del nastro usata",
         not fine_div, f"diverse {fine_div}")
    a, b = coppia(7)
    p, nastro = nastri[7]
    f, j = foto(a, b, 7, nastro, len(nastro) // 2, {})
    q1 = f.copia()
    def tutto(x): return (ch(x), nascoste(x.t, 0), nascoste(x.t, 1), [g.grimorio.rng.bit_generator.state for g in x.t.giocatori])
    prima = tutto(q1)
    q2 = copia(q1)
    comuni = _mutabili_in_comune(q1, q2)
    stato = {"cur": j}
    gg = [Replay(i, nastro, S.Semplice(), stato) for i in (0, 1)]
    S.partita(a, b, 7, gg[0], gg[1], da=q2)
    caso("copia indipendente: nessun oggetto mutabile in comune con l'originale, e giocare la copia fino in fondo non cambia "
         "l'originale (eventi, carte nascoste, generatori del caso)",
         not comuni and tutto(q1) == prima and q2.t.finita and not q1.t.finita, f"in comune {comuni[:5]}")
    class Colori(S.Semplice):                          # risponde a «colore» (Room of Refuge): il Semplice non lo fa
        def colore(self, p, j, o, colori): return "U"
    def rifugio(m): return {**m, "mazzo": ["Room of Refuge" if x == "Island" else x for x in m["mazzo"]]}
    a, b = rifugio(mazzi[0]), rifugio(mazzi[1])
    giusti, rossi, come = [], [], []
    for s in range(1, 9):
        p, nastro = registra(a, b, s, Colori(s), Colori(s + 100))
        ks = [k + 1 for k, v in enumerate(nastro) if v[1] == "colore" and v[3] == "U"]
        if not ks: continue
        q, j, st = rifai_dalla_copia(a, b, s, nastro, ks[0], poi=[Colori(), Colori()])
        giusti.append(ch(q) == ch(p) and st["cur"] == len(nastro) and j < ks[0])
        global RICOLLEGA
        RICOLLEGA = False
        try:
            q, _, _ = rifai_dalla_copia(a, b, s, nastro, ks[0], poi=[Colori(), Colori()])
            rossi.append(ch(q) != ch(p)); come.append("altra partita")
        except Divergenza as e:
            rossi.append(True); come.append("divergenza")
        finally: RICOLLEGA = True
    caso("copia con un giocatore che sceglie il colore (Room of Refuge): rifatta fino in fondo dalla copia del turno della "
         "scelta, e' la partita vera", len(giusti) >= 4 and all(giusti), f"{sum(giusti)}/{len(giusti)} partite con «colore»")
    caso("prova negativa: `t.scegli` non ricollegato alla copia, la scelta del colore la fa la partita vecchia e la partita "
         "cambia o il nastro non torna", len(rossi) == len(giusti) and all(rossi),
         f"{sum(rossi)}/{len(rossi)}: {dict((x, come.count(x)) for x in set(come))}")
    ok = sum(1 for _, k, _ in casi if k)
    for nome, k, det in casi: print(("OK   " if k else "ROSSO"), nome, ("  -- " + det) if det else "")
    print(f"\n{ok}/{len(casi)} in {time.time() - t0:.0f} s")
    return ok == len(casi)


# ====================================================================== la spazzata delle partite di prova
class Raccogli(Cercatore):
    """Non cerca: raccoglie una scelta vera su otto circa (il prefisso del nastro, il gancio, le candidate) e gioca la mossa
    del Semplice. Serve alla spazzata."""
    def _scegli(self, nome, cand):
        a, b, seme, i, nastro, kw = self.contesto
        if np.random.default_rng([self.seme, len(nastro), 8203]).random() < 0.12:
            self.diario.append((a, b, seme, list(nastro[:-1]), i, nome, [c for _, c in cand]))
        return cand[0][0]


def _lavoro_spazzata(arg):
    try: return (arg[5], prova_mossa(*arg), None)
    except S.ArbitroFischia as e: return (arg[5], None, "fischio: " + str(e))
    except Divergenza as e: return (arg[5], None, "divergenza: " + str(e))


def spazzata(semi, mondi=2):
    """Dopo ogni modifica al motore o alla ricerca: da ogni partita (Raccogli contro Semplice, a posti alterni) si prendono
    alcune scelte vere e si giocano TUTTE le loro candidate in `mondi` mondi, con l'arbitro acceso. Trova in pochi minuti i
    fischi che il metro trova uno all'ora (14 ott 2026: 13190 partite di prova, semi 500-699, due fischi, 122.1h)."""
    from collections import Counter
    M = S.mazzi_veri()
    punti, t0 = [], time.time()
    for s in semi:
        a, b = M[s % 10], M[(s * 7 + 3) % 10]
        c = Raccogli(s)
        if s % 2 == 0: registra(a, b, s, c, S.Semplice(s + 1))
        else: registra(b, a, s, S.Semplice(s + 1), c)
        punti += c.diario
    lavori = [(a, b, seme, pref, i, nome, cnd, m, False, {}) for a, b, seme, pref, i, nome, cands in punti for cnd in cands
              for m in range(1, mondi + 1)]
    print(f"{len(punti)} scelte ({dict(Counter(x[5] for x in punti))}), {len(lavori)} partite di prova, raccolte in {time.time() - t0:.0f} s", flush=True)
    pool = nuovo_pool()
    try: out = pool.map(_lavoro_spazzata, lavori, chunksize=2)
    finally: pool.terminate()
    err = [x for x in out if x[2]]
    print(f"giocate in {time.time() - t0:.0f} s; fischi o divergenze: {len(err)}")
    for (nome, msg), k in Counter((x[0], x[2][:160]) for x in err).most_common(10): print(f"  {k} x {nome}: {msg}")
    return not err


# ====================================================================== troncare le partite di prova (passo 8.5)
def _lavoro_segna(arg):
    a, b, seme, pref, i, nome, c, m, kw, pid, j = arg
    try:
        t0 = time.time()
        e, val = prova_mossa(a, b, seme, pref, i, nome, c, m, False, {**kw, "segna": True})
        return pid, j, m, e, val, time.time() - t0, None
    except S.ArbitroFischia as x: return pid, j, m, None, None, 0, "fischio: " + str(x)
    except Divergenza as x: return pid, j, m, None, None, 0, "divergenza: " + str(x)


def _lavoro_tempo(arg):
    """I tempi a coppie: la stessa partita di prova intera e troncata a ogni K, di fila nello stesso processo (con
    un'altra sessione che occupa i processori, tempi presi in momenti diversi non si confrontano)."""
    lav, K = arg
    out = {}
    for k in (None,) + tuple(K):
        t0 = time.time()
        prova_mossa(*lav[:9], {} if k is None else {"turni": k})
        out[k] = time.time() - t0
    return out


def troncate(semi, mondi=8, K=(0, 1, 2, 3, 4), processi=None, scrivi=True):
    """La prova che conta per il passo 8.5: troncare le partite di prova cambia la scelta del Cercatore? Dalle partite dei
    semi (Raccogli contro Semplice, come la spazzata) si prendono le scelte vere; ogni candidata si gioca FINO IN FONDO in
    `mondi` mondi, segnando la valutazione a ogni fine turno dopo la scelta: la partita troncata a K turni avrebbe detto
    esattamente quel numero (stesso nastro, stesso mondo, stesse mosse fino a li'), e se la partita e' finita prima lo dice
    il risultato vero. Poi, coi mondi divisi in due meta' indipendenti A e B, per ogni regola di scelta (la mossa del
    Semplice, le partite intere, le troncate a K) si sceglie coi mondi A e si guarda quanto vale la scelta sui mondi B a
    partite intere: e' il punteggio che conta, misurato su mondi che non hanno scelto."""
    from collections import Counter, defaultdict
    M = S.mazzi_veri()
    t0 = time.time()
    punti = []
    for s in semi:
        a, b = M[s % 10], M[(s * 7 + 3) % 10]
        c = Raccogli(s)
        if s % 2 == 0: registra(a, b, s, c, S.Semplice(s + 1))
        else: registra(b, a, s, S.Semplice(s + 1), c)
        punti += c.diario
    lavori = [(a, b, seme, pref, i, nome, cnd, m, {}, pid, j) for pid, (a, b, seme, pref, i, nome, cands) in enumerate(punti)
              for j, cnd in enumerate(cands) for m in range(1, mondi + 1)]
    print(f"{len(punti)} scelte ({dict(Counter(x[5] for x in punti))}), {len(lavori)} partite di prova", flush=True)
    pool = nuovo_pool(processi)
    try:
        out = pool.map(_lavoro_segna, lavori, chunksize=4)
        campione = [((a, b, seme, pref, i, nome, cnd, m, False), K) for a, b, seme, pref, i, nome, cnd, m, _, _, _ in lavori[::max(1, len(lavori) // 150)]]
        coppie = pool.map(_lavoro_tempo, campione, chunksize=1)
        tempi = {k: float(np.mean([c[k] for c in coppie])) for k in (None,) + tuple(K)}
    finally: pool.terminate()
    json.dump({"semi": list(semi), "mondi": mondi, "tempi": {str(k): v for k, v in tempi.items()},
               "candidate": [len(x[6]) for x in punti], "out": [[pid, j, m, e, {str(k): v for k, v in (val or {}).items()}, dt, er]
                                                               for pid, j, m, e, val, dt, er in out]},
              open(os.path.join(QUI, "troncate_grezzi.json"), "w", encoding="utf-8"))
    err = [x for x in out if x[6]]
    if err:
        for (msg,), n in Counter((x[6][:160],) for x in err).most_common(5): print(f"  {n} x {msg}")
        raise S.ArbitroFischia(f"{len(err)} partite di prova con un fischio o una divergenza: nessun risultato")
    # il valore della partita troncata a K: la valutazione segnata, o il risultato se la partita e' finita prima
    tab = defaultdict(dict)                                    # (pid, j) -> mondo -> (esito, {K: v})
    for pid, j, m, e, val, dt, _ in out: tab[(pid, j)][m] = (e, val)
    def v_k(e, val, k): return val[k] if k in val else e
    righe = {}
    for k in K:                                                # calibratura delle troncate contro il risultato vero
        q = np.array([v_k(e, val, k) for _, _, _, e, val, _, _ in out if k in val])
        y = np.array([e for _, _, _, e, val, _, _ in out if k in val])
        g = np.array([punti[pid][2] for pid, _, _, _, val, _, _ in out if k in val])       # la partita da cui viene la scelta
        _, g = np.unique(g, return_inverse=True)
        es = math.sqrt(float((np.bincount(g, weights=y - q) ** 2).sum())) / max(len(q), 1)   # a grappoli per partita
        righe[k] = {"aperte": len(q) / len(out), "detto": float(q.mean()), "vinto": float(y.mean()),
                    "brier": float(np.mean((q - y) ** 2)), "es": es, "partite": int(g.max() + 1) if len(g) else 0}
    # le regole di scelta, A per scegliere e B per giudicare
    A, B = range(1, mondi // 2 + 1), range(mondi // 2 + 1, mondi + 1)
    regole = {"Semplice": None, "intere": "e"} | {f"troncate a {k}": k for k in K}
    valore = {r: [] for r in regole}
    uguali = {r: 0 for r in regole}
    for pid, (_, _, _, _, _, _, cands) in enumerate(punti):
        nc = len(cands)
        pieno_B = [np.mean([tab[(pid, j)][m][0] for m in B]) for j in range(nc)]
        def punteggio(j, r):
            if r == "e": return sum(tab[(pid, j)][m][0] for m in A)
            return sum(v_k(*tab[(pid, j)][m], r) for m in A)
        scelte = {}
        for nome, r in regole.items():
            scelte[nome] = 0 if r is None else max(range(nc), key=lambda j: (punteggio(j, r), -j))
            valore[nome].append(pieno_B[scelte[nome]])
        for nome in regole: uguali[nome] += scelte[nome] == scelte["intere"]
    sintesi = {"scelte": len(punti), "candidate": len(tab), "partite_di_prova": len(out), "mondi": mondi,
               "tempo_intera": tempi[None], "tempi": {k: tempi[k] for k in K}, "calibratura": righe,
               "valore_B": {r: float(np.mean(v)) for r, v in valore.items()},
               "come_le_intere": {r: uguali[r] / len(punti) for r in regole}, "secondi": time.time() - t0}
    # la differenza a coppie col valore delle intere: errore standard sulle scelte
    for r in regole:
        d = np.array(valore[r]) - np.array(valore["intere"])
        sintesi.setdefault("diff_intere", {})[r] = (float(d.mean()), float(d.std(ddof=1) / math.sqrt(len(d))))
    stampa_troncate(sintesi)
    if scrivi: scrivi_troncate(sintesi, semi)
    return sintesi


def stampa_troncate(s):
    print(f"{s['scelte']} scelte, {s['candidate']} candidate, {s['partite_di_prova']} partite di prova intere, {s['secondi']:.0f} s")
    print(f"tempo di una partita di prova: intera {s['tempo_intera']:.3f} s; " + ", ".join(f"K={k} {t:.3f} s" for k, t in s["tempi"].items()))
    for k, r in s["calibratura"].items():
        print(f"  K={k}: aperte {r['aperte']:.0%}, detto {r['detto']:.3f}, vinto {r['vinto']:.3f} (e.s. a grappoli {r['es']:.3f}, {r['partite']} partite), Brier {r['brier']:.4f}")
    for r, v in s["valore_B"].items():
        dm, de = s["diff_intere"][r]
        print(f"  {r:16s}: valore sui mondi B {v:.3f}, meno le intere {dm:+.4f} (e.s. {de:.4f}), stessa scelta delle intere {s['come_le_intere'][r]:.0%}")


def scrivi_troncate(s, semi):
    f = os.path.join(QUI, "Metro_Guarda_Avanti.md")
    with open(f, "a", encoding="utf-8") as h:
        h.write(f"\n## {datetime.now().strftime('%Y-%m-%d %H:%M')}, partite di prova troncate (passo 8.5), semi {semi[0]}-{semi[-1]}\n\n"
                f"`py -I -X utf8 Motore_Partita/guarda_avanti.py --troncate {semi[0]} {semi[-1]} {s['mondi']}`: {s['scelte']} scelte vere, "
                f"{s['candidate']} candidate, {s['partite_di_prova']} partite di prova giocate fino in fondo con la valutazione segnata a "
                f"ogni fine turno; mondi divisi in due meta': si sceglie con A, si giudica la scelta con le partite intere di B. "
                f"Tempo di una partita di prova intera {s['tempo_intera']:.3f} s.\n\n"
                "| Regola di scelta | Tempo a partita | Valore sui mondi B | Meno le intere (e.s.) | Stessa scelta delle intere |\n"
                "| :--- | ---: | ---: | ---: | ---: |\n")
        for r, v in s["valore_B"].items():
            dm, de = s["diff_intere"][r]
            k = r.split()[-1]
            tempo = s["tempo_intera"] if r == "intere" else s["tempi"].get(int(k)) if k.isdigit() else None
            h.write(f"| {r} | {f'{tempo:.3f} s' if tempo is not None else '-'} | {v:.3f} | {dm:+.4f} ({de:.4f}) | {s['come_le_intere'][r]:.0%} |\n")
        h.write("\n| K | Partite ancora aperte | Detto | Vinto (e.s.) | Brier |\n| ---: | ---: | ---: | ---: | ---: |\n")
        for k, r in s["calibratura"].items():
            h.write(f"| {k} | {r['aperte']:.0%} | {r['detto']:.3f} | {r['vinto']:.3f} ({r['es']:.3f}) | {r['brier']:.4f} |\n")


# ====================================================================== la copia contro il replay (passo 8.6)
def _impronta_partita(p, i):
    import hashlib
    eventi = [(e.tipo, e.vecchio, e.nuovo, e.da, e.a, e.causa, e.giocatore, e.quanto) for e in p.t.eventi]
    return hashlib.sha1(repr((eventi, esito(p, i), sorted(getattr(p, "_valori", {}).items()))).encode()).hexdigest()


def _lavoro_copia(arg):
    """Una partita di prova di --troncate (segnata, fino in fondo) giocata con le due vie, nell'ordine che cambia a ogni
    lavoro (chi va per secondo trova i processori gia' caldi): le impronte (eventi, esito, valutazioni) e i tempi."""
    a, b, seme, pref, i, nome, c, m, kw, pid, j, n = arg
    out = {}
    try:
        for via in (("replay", "copia") if n % 2 == 0 else ("copia", "replay")):
            t0 = time.time()
            p, _, _ = partita_di_prova(a, b, seme, pref, i, nome, c, m, False, {**kw, "segna": True}, via=via)
            out[via] = (_impronta_partita(p, i), time.time() - t0)
        return pid, j, m, out, None
    except S.ArbitroFischia as x: return pid, j, m, out, "fischio: " + str(x)
    except Divergenza as x: return pid, j, m, out, "divergenza: " + str(x)


def _lavoro_tempo_copia(arg):
    """I tempi a coppie della partita di prova intera e troncata a 3 turni, con le due vie, di fila nello stesso processo."""
    lav, n = arg
    out = {}
    for k in (None, 3):
        for via in (("replay", "copia") if n % 2 == 0 else ("copia", "replay")):
            t0 = time.time()
            prova_mossa(*lav, {} if k is None else {"turni": k}, via=via)
            out[(k, via)] = time.time() - t0
    return out


def uguale_copia(semi, mondi=8, processi=None, scrivi=True):
    """Il passo 8.6, punto 1: le partite di prova di --troncate (stessi semi, stesse scelte, stessi mondi) giocate dalla
    copia a inizio turno e rifatte dal seme devono essere la stessa partita evento per evento; poi i tempi a coppie su un
    campione (la partita intera e la troncata a 3 turni, le due vie di fila nello stesso processo)."""
    from collections import Counter
    M = S.mazzi_veri()
    t0 = time.time()
    punti = []
    for s in semi:
        a, b = M[s % 10], M[(s * 7 + 3) % 10]
        c = Raccogli(s)
        if s % 2 == 0: registra(a, b, s, c, S.Semplice(s + 1))
        else: registra(b, a, s, S.Semplice(s + 1), c)
        punti += c.diario
    lavori = [(a, b, seme, pref, i, nome, cnd, m, {}, pid, j) for pid, (a, b, seme, pref, i, nome, cands) in enumerate(punti)
              for j, cnd in enumerate(cands) for m in range(1, mondi + 1)]
    lavori = [x + (n,) for n, x in enumerate(lavori)]
    print(f"{len(punti)} scelte, {len(lavori)} partite di prova, due vie ciascuna", flush=True)
    pool = nuovo_pool(processi)
    try:
        out = pool.map(_lavoro_copia, lavori, chunksize=4)
        campione = [(x[:8] + (False,), n) for n, x in enumerate(lavori[::max(1, len(lavori) // 200)])]
        coppie = pool.map(_lavoro_tempo_copia, campione, chunksize=1)
    finally: pool.terminate()
    err = [x for x in out if x[4]]
    diverse = [x for x in out if not x[4] and x[3]["replay"][0] != x[3]["copia"][0]]
    tr = float(np.mean([x[3]["replay"][1] for x in out if not x[4]])) if len(err) < len(out) else 0.0
    tc = float(np.mean([x[3]["copia"][1] for x in out if not x[4]])) if len(err) < len(out) else 0.0
    tempi = {f"{'intera' if k is None else f'troncata a {k}'}, {via}": float(np.mean([c[(k, via)] for c in coppie]))
             for k in (None, 3) for via in ("replay", "copia")}
    sintesi = {"scelte": len(punti), "partite_di_prova": len(out), "diverse": len(diverse), "errori": len(err),
               "segnate_replay": tr, "segnate_copia": tc, "tempi_campione": tempi, "campione": len(coppie), "secondi": time.time() - t0}
    print(f"diverse {len(diverse)}, fischi o divergenze {len(err)} su {len(out)}; segnate fino in fondo: replay {tr:.3f} s, copia {tc:.3f} s")
    for k, v in tempi.items(): print(f"  {k}: {v:.3f} s")
    for (msg,), n in Counter((x[4][:160],) for x in err).most_common(5): print(f"  {n} x {msg}")
    if scrivi:
        with open(os.path.join(QUI, "Metro_Guarda_Avanti.md"), "a", encoding="utf-8") as h:
            h.write(f"\n## {datetime.now().strftime('%Y-%m-%d %H:%M')}, la copia a inizio turno contro il replay (passo 8.6), semi {semi[0]}-{semi[-1]}\n\n"
                    f"`py -I -X utf8 Motore_Partita/guarda_avanti.py --copia {semi[0]} {semi[-1]} {mondi}`: {len(punti)} scelte vere, "
                    f"{len(out)} partite di prova di --troncate giocate fino in fondo con la valutazione segnata, ognuna con le due vie: "
                    f"**diverse {len(diverse)}**, fischi o divergenze {len(err)}. Tempo medio (le due vie di fila nello stesso processo, "
                    f"l'ordine alterno): replay {tr:.3f} s, copia {tc:.3f} s.\n\n| Partita di prova (campione di {len(coppie)}) | Tempo |\n| :--- | ---: |\n")
            for k, v in tempi.items(): h.write(f"| {k} | {v:.3f} s |\n")
    return sintesi


def _rifai_chiavi(arg):
    a, b, s, nastro = arg
    q, _ = rifai(a, b, s, nastro)
    return [(e.tipo, e.vecchio, e.nuovo, e.da, e.a, e.causa, e.giocatore, e.quanto) for e in q.t.eventi]


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[:1] == ["--prova"]: sys.exit(0 if prova() else 1)
    elif a[:1] == ["--troncate"]:
        troncate(list(range(int(a[1]), int(a[2]) + 1)), mondi=int(a[3]) if len(a) > 3 and a[3].isdigit() else 8,
                 processi=int(a[a.index("--processi") + 1]) if "--processi" in a else None)
    elif a[:1] == ["--copia"]:
        r = uguale_copia(list(range(int(a[1]), int(a[2]) + 1)), mondi=int(a[3]) if len(a) > 3 and a[3].isdigit() else 8,
                         processi=int(a[a.index("--processi") + 1]) if "--processi" in a else None)
        sys.exit(0 if r["diverse"] == 0 and r["errori"] == 0 else 1)
    elif a[:1] == ["--spazzata"]: sys.exit(0 if spazzata(list(range(int(a[1]), int(a[2]) + 1))) else 1)
    elif a[:1] == ["--metro"]: metro(list(range(int(a[1]), int(a[2]) + 1)), int(a[3]), baro="--baro" in a,
                                     turni=int(a[a.index("--turni") + 1]) if "--turni" in a else None,
                                     processi=int(a[a.index("--processi") + 1]) if "--processi" in a else None)
    else: print(__doc__)
