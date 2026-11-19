"""Il passo 8.5 del motore di partita: la valutazione del tavolo (14 ott 2026).

Autore, 14 ott 2026 (handoff, §5, «il piano dopo»): «da vite, creature, carte in mano, mana, una stima della
probabilita' di vincere, allenata su milioni di posizioni di partite simulate col risultato vero (prima un modello semplice
e leggibile, per esempio una regressione logistica su caratteristiche scritte, poi solo se serve qualcosa di piu')».
A cosa serve: le partite di prova del Cercatore (guarda_avanti.py) si fermano K turni dopo la scelta e il loro punteggio
e' la probabilita' detta qui, non il risultato di una partita giocata fino in fondo da due Semplice.

Come e' fatta:
  - `caratteristiche(p, i)`: dal tavolo a fine turno, per ognuno dei due giocatori, le cose che contano (vite, carte in
    mano, terre, creature, forza, forza in volo, fedelta', grimorio corto, la pressione: quanta parte delle vite
    dell'altro si toglie in un attacco). Ogni caratteristica e' «mia meno sua», piu' «tocca a me il prossimo turno»
    (+1/-1). Il modello e' una regressione logistica SENZA intercetta su queste differenze: quindi P(io vinco) +
    P(lui vince) = 1 sempre, per costruzione (la partita a due e' a somma zero: 104.2a; le patte, 104.4a, si tolgono).
  - I dati: partite intere fra due `simula.Semplice` sui 10 mazzi veri, arbitro acceso (CLAUDE.md, regola 3). Una
    posizione a ogni fine turno (dopo la pulizia, 514), vista da G1; il risultato vero e' chi ha vinto. Allenamento e
    misura su semi DIVERSI (le posizioni di una partita sono legate fra loro: si separa per partita, non per posizione).
  - Quello che la valutazione NON e': il valore di una posizione per un giocatore bravo. E' la probabilita' che vinca chi
    e' in quella posizione se da li' giocano due Semplice, cioe' esattamente quello che una partita di prova del Cercatore
    misurerebbe giocando fino in fondo. Il Semplice resta dentro il numero: lo toglie il passo 8.6, non questo.

    py -I -X utf8 Motore_Partita/valuta.py --dati A B [--processi N]     posizioni dai semi A-B (valuta_posizioni.npz)
    py -I -X utf8 Motore_Partita/valuta.py --allena                       allena su 20000-27999, misura su 30000-31999
    py -I -X utf8 Motore_Partita/valuta.py --prova                        le prove (modello, calibratura, prove negative)
    py -I -X utf8 Motore_Partita/valuta.py --curva                        quante partite servono (la curva di apprendimento)
    py -I -X utf8 Motore_Partita/valuta.py --cercatori A B [--prove 4] [--turni 3] [--processi N]
                                                                          passo 8.6: partite fra due Cercatori leggeri, semi A-B,
                                                                          scritte riga per riga in valuta_partite_cercatori.jsonl
    py -I -X utf8 Motore_Partita/valuta.py --riassunto-cercatori          cosa c'e' nel file, e come lo legge la valutazione V0
    py -I -X utf8 Motore_Partita/valuta.py --giocate                      il quaderno delle giocate: le note del Cercatore
    py -I -X utf8 Motore_Partita/valuta.py --allena-versione v1           passo 8.6, punto 3: la V1 sulle partite fra Cercatori
    py -I -X utf8 Motore_Partita/valuta.py --giro A B [--a v1] [--b v0] [--processi N]
                                                                          punto 4: Cercatore con va contro Cercatore con vb, semi A-B
                                                                          a posti scambiati (giro_<va>_<vb>.jsonl)
    py -I -X utf8 Motore_Partita/valuta.py --riassunto-giro [va vb]       vittorie, Wilson, coppie e test dei segni
"""
import json
import math
import os
import sys
import time
from datetime import datetime

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # py -I non mette la cartella dello script nel percorso
import effetti as E
import simula as S
from tavolo import costituzione, forza, parole

QUI = os.path.dirname(os.path.abspath(__file__))
DATI = os.path.join(QUI, "valuta_posizioni.npz")
PESI = os.path.join(QUI, "valuta_pesi.json")
RAPPORTO = os.path.join(QUI, "Valuta_Tavolo.md")
ALLENA = (20000, 27999)          # i semi dell'allenamento
MISURA = (30000, 31999)          # i semi della misura (mai visti dall'allenamento)


# ====================================================================== le caratteristiche
def _lato(t, j):
    """Le quantita' di un giocatore j, dal tavolo. Forza e costituzione sono quelle dopo gli effetti (613, il tavolo)."""
    g, k = t.giocatori[j], t.giocatori[1 - j]
    mie = [o for o in t.campo if o.controllore == j and o.carta is not None]
    cre = [o for o in mie if "creature" in o.carta.tipi]
    f = [max(0, forza(o)) for o in cre]
    vola = sum(x for o, x in zip(cre, f) if "flying" in parole(o))
    vite_k = max(1, k.vite)
    return {
        "vite": min(max(g.vite, 0), 30),
        "mano": len(g.mano),
        "terre": sum(1 for o in mie if "land" in o.carta.tipi),
        "creature": len(cre),
        "forza": sum(f),
        "costituzione": sum(max(0, costituzione(o) - o.danno) for o in cre),
        "forza_in_volo": vola,
        "fedelta": sum(o.segnalini["fedelta"] for o in mie if "planeswalker" in o.carta.tipi),
        "altri": sum(1 for o in mie if not ({"land", "creature", "planeswalker"} & set(o.carta.tipi))),
        "grimorio_corto": max(0, 5 - len(g.grimorio.carte)),
        "pressione": min(1.0, sum(f) / vite_k),
        "pressione_in_volo": min(1.0, vola / vite_k),
        "letale": 1.0 if sum(f) >= k.vite else 0.0,
    }


NOMI = ["vite", "mano", "terre", "creature", "forza", "costituzione", "forza_in_volo", "fedelta", "altri",
        "grimorio_corto", "pressione", "pressione_in_volo", "letale"]
BASE = [n + " (mia - sua)" for n in NOMI] + ["tocca a me (+1/-1)"]
PRESTO = 8                       # la fase: «presto» pesa 1 al turno 0 e scende a 0 al turno 8
CON_FASE = [NOMI.index(n) for n in ("vite", "mano", "terre", "creature", "forza", "costituzione")] + [len(NOMI)]
COLONNE = BASE + [BASE[k] + " x presto" for k in CON_FASE]


def espandi(X, turno):
    """Le caratteristiche base piu' sette di loro moltiplicate per «presto» = max(0, 1 - turno/8): nei primi turni lo
    stesso vantaggio pesa diversamente (la prima misura, senza, era scalibrata sui turni 1-4: ECE 0,044). «presto» e'
    uguale per i due giocatori, quindi l'antisimmetria resta. Solo sette: con tutte e quattordici (14 ott 2026, 21:00)
    «letale x presto» e la coppia in volo (quasi uguali nei primi turni, pesi grandi e opposti) davano da sole fino a 11
    punti di z in posizioni rare, 13 posizioni dei turni 1-4 sopra il 90% o sotto il 10% e giuste 9 volte su 13; con
    sette la precisione e' la stessa (skill 25,4% contro 25,5%), il contributo massimo 3,7, le posizioni estreme 4."""
    X = np.atleast_2d(np.asarray(X, float))
    presto = np.clip(1 - np.asarray(turno, float).reshape(-1, 1) / PRESTO, 0, None)
    return np.hstack([X, X[:, CON_FASE] * presto])


def caratteristiche(p, i):
    """Il vettore della posizione per il giocatore i, a fine turno: mia meno sua per ogni quantita', e +1 se il prossimo
    turno e' di i (chi ha appena finito e' p.attivo), -1 se no. Antisimmetrico: per l'altro giocatore e' il negativo."""
    a, b = _lato(p.t, i), _lato(p.t, 1 - i)
    return np.array([a[n] - b[n] for n in NOMI] + [1.0 if p.attivo != i else -1.0], dtype=float)


# ====================================================================== il modello
class Modello:
    """La regressione logistica senza intercetta: P(i vince) = 1 / (1 + exp(-w . x)), x standardizzata per scala (non per
    media: togliere la media romperebbe l'antisimmetria)."""

    def __init__(self, w, scala, info=None):
        self.w, self.scala, self.info = np.asarray(w, float), np.asarray(scala, float), info or {}

    def z(self, X, turno):
        return (espandi(X, turno) / self.scala) @ self.w

    def p(self, X, turno):
        """X: le caratteristiche base (caratteristiche()), turno: il turno appena finito, uno per riga."""
        q = 1.0 / (1.0 + np.exp(-np.clip(self.z(X, turno), -40, 40)))
        return q if np.ndim(X) > 1 else float(q[0])

    def valuta(self, p, i):
        return self.p(caratteristiche(p, i), p.t.turno_numero)

    def salva(self, f=PESI):
        d = {"colonne": COLONNE, "w": [float(x) for x in self.w], "scala": [float(x) for x in self.scala], **self.info}
        json.dump(d, open(f, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    @staticmethod
    def carica(f=PESI):
        d = json.load(open(f, encoding="utf-8"))
        if d["colonne"] != COLONNE: raise RuntimeError(f"{f}: le colonne del modello non sono quelle di oggi: si riallena")
        return Modello(d["w"], d["scala"], {k: v for k, v in d.items() if k not in ("colonne", "w", "scala")})


def allena(X, turno, y, l2=1e-3, giri=50):
    """IRLS (Newton) per la logistica senza intercetta, con una piccola L2 per la stabilita'. -> Modello."""
    X, y = espandi(X, turno), np.asarray(y, float)
    scala = np.maximum(np.abs(X).mean(axis=0), 1e-9)
    Z = X / scala
    w = np.zeros(Z.shape[1])
    for _ in range(giri):
        q = 1.0 / (1.0 + np.exp(-np.clip(Z @ w, -40, 40)))
        g = Z.T @ (q - y) + l2 * len(y) * w
        H = (Z * (q * (1 - q))[:, None]).T @ Z + l2 * len(y) * np.eye(len(w))
        passo = np.linalg.solve(H, g)
        w -= passo
        if np.abs(passo).max() < 1e-10: break
    return Modello(w, scala)


_MODELLI = {}


def pesi_di(versione):
    """Il file dei pesi di una versione: v0 e' valuta_pesi.json (il passo 8.5), le altre valuta_pesi_<v>.json (passo 8.6,
    handoff §5: «V0 resta, valuta.modello() deve poter scegliere la versione»). Un percorso che finisce in .json e' preso
    com'e' (le prove)."""
    if versione.endswith(".json"): return versione
    return PESI if versione == "v0" else os.path.join(QUI, f"valuta_pesi_{versione}.json")


def modello(versione="v0"):
    """Il modello salvato di una versione (di norma v0), caricato una volta per processo."""
    if versione not in _MODELLI: _MODELLI[versione] = Modello.carica(pesi_di(versione))
    return _MODELLI[versione]


# ====================================================================== le posizioni dalle partite simulate
class Segna(E.Partita):
    """La partita che fotografa il tavolo a ogni fine turno (dopo la pulizia), vista da G1."""
    def turno(self, giocatori):
        super().turno(giocatori)
        if not self.t.finita:
            if not hasattr(self, "foto"): self.foto = []
            self.foto.append((self.t.turno_numero, caratteristiche(self, 0)))


def coppia(s, n=10):
    """I mazzi del seme s (come simula.sfida): a = s % 10, b = (7s + 3) % 10, mai lo stesso."""
    a, b = s % n, (s * 7 + 3) % n
    if a == b: b = (b + 1) % n
    return a, b


def _partita(s):
    """Una partita del seme s fra due Semplice, arbitro acceso. -> (seme, [(turno, x)], vincitore o None, causa)."""
    M = S.mazzi_veri()
    a, b = coppia(s, len(M))
    try:
        p = S.partita(M[a], M[b], s, S.Semplice(s * 2 + 1), S.Semplice(s * 2 + 2), P=Segna)
    except S.ArbitroFischia as e:
        return s, [], None, "FISCHIO: " + str(e)
    v = p.t.vincitore if p.t.finita else None
    return s, getattr(p, "foto", []), v, S.come_finisce(p) if p.t.finita else "a tempo"


def raccogli(semi, processi=None):
    """Le posizioni dei semi, in parallelo. -> (X, y, seme, turno, fischi, patte)."""
    pool = _pool(processi)
    try: out = pool.map(_partita, semi, chunksize=8)
    finally: pool.terminate()
    X, y, sm, tu, fischi, patte = [], [], [], [], [], 0
    for s, foto, v, causa in out:
        if causa and causa.startswith("FISCHIO"): fischi.append(causa); continue
        if v is None: patte += 1; continue                                                   # 104.4a o a tempo: fuori
        for n, x in foto:
            X.append(x); y.append(1.0 if v == 0 else 0.0); sm.append(s); tu.append(n)
    return (np.array(X).reshape(-1, len(BASE)), np.array(y), np.array(sm), np.array(tu), fischi, patte)


def _pool(n):
    import multiprocessing as mp
    return mp.get_context("spawn").Pool(n or max(1, (os.cpu_count() or 2) - 2))


def dati(a, b, processi=None, f=DATI):
    """Le posizioni dei semi a-b, aggiunte al file (un seme gia' presente non si rifa')."""
    t0 = time.time()
    vecchi = dict(np.load(f)) if os.path.exists(f) else None
    gia = set(vecchi["seme"].tolist()) if vecchi else set()
    semi = [s for s in range(a, b + 1) if s not in gia]
    X, y, sm, tu, fischi, patte = raccogli(semi, processi)
    if fischi:
        for x in fischi[:5]: print(x)
        raise S.ArbitroFischia(f"{len(fischi)} partite con un fischio: nessun dato scritto")
    if vecchi:
        X = np.vstack([vecchi["X"], X]); y = np.concatenate([vecchi["y"], y])
        sm = np.concatenate([vecchi["seme"], sm]); tu = np.concatenate([vecchi["turno"], tu])
    np.savez_compressed(f, X=X, y=y, seme=sm, turno=tu)
    print(f"semi {a}-{b}: {len(semi)} partite, {patte} patte o a tempo, {len(y)} posizioni in tutto, {time.time() - t0:.0f} s")


# ====================================================================== le partite fra Cercatori (passo 8.6, punto 2)
CERCATORI = os.path.join(QUI, "valuta_partite_cercatori.jsonl")   # una riga per partita: si riprende da dove si e' fermata
PROVE_C, TURNI_C = 4, 3          # il Cercatore leggero (handoff, §5, piano dell'8.6, punto 2)
# I semi delle partite fra Cercatori, decisi dalla curva (`curva`, 15 ott 2026 12:53, sui dati dei Semplice): la skill e'
# al plateau gia' a 2000 partite (25,2% contro 25,4% con 8000), la calibratura per fase regge le soglie dell'8.5 (ECE
# sotto 0,03 in ogni fase, nessuna fascia fuori) solo da 4000. Una partita fra Cercatori costa ~150 s in un processo
# (contro ~0,1 s fra Semplice): 4000 sarebbero ~170 ore di calcolo. Si parte da 2000 (allenamento) e 500 (misura); se la
# V1 non regge la calibratura, si allarga a 42000-43999 (la raccolta riprende da dove si e' fermata).
ALLENA_C = (40000, 41999)
MISURA_C = (50000, 50499)


def _nome(x, i):
    if x is None: return "niente"
    if E._e_giocatore(x): return "se stesso" if x == i else "l'avversario"
    return getattr(x, "nome", None) or str(x)


def descrivi(gancio, m, i):
    """Una mossa in parole, coi nomi delle carte: per il quaderno delle giocate (le note del Cercatore)."""
    if gancio == "agisci":
        if m is None: return "passa"
        if m[0] == "terra": return f"terra {m[1].nome}"
        if m[0] == "lancia":
            s = f"lancia {m[1].nome}" + (f" con X={m[2]}" if m[2] else "")
            if len(m) > 4 and m[4]: s += " su " + ", ".join(_nome(b, i) for gr in m[4] for b in gr)
            return s
        if m[0] == "attiva": return f"attiva {m[1].nome} (abilita' {m[2]})"
        return str(m[0])
    if gancio == "attacca":
        if not m: return "non attacca"
        return "attacca con " + ", ".join(sorted(a.nome + ("" if E._e_giocatore(d) else f" su {_nome(d, i)}") for a, d in m.items()))
    if gancio == "blocca":
        if not m: return "non blocca"
        return "blocca " + ", ".join(sorted(f"{b.nome} su {a.nome}" for b, a in m.items()))
    if gancio == "bersagli":
        return "bersaglio " + ", ".join(_nome(b, i) for gr in (m or []) for b in gr)
    return str(m)


_ANNOTA = None


def cercatore_che_annota():
    """Il Cercatore che scrive le note (15 ott 2026, Autore: «non sarebbe meglio che anche lui le annotasse in modo da
    poter capire sulle partite future da quali mosse gia' importanti partire?»): a ogni scelta cercata in cui sceglie
    diverso dal Semplice, una nota con il gancio, il turno, la fase, la mossa del Semplice e la sua in parole, le candidate
    e i loro punti, e le caratteristiche del tavolo in quel momento (`caratteristiche`, viste da chi sceglie). Le note NON
    si usano per scegliere: la partita e' quella del Cercatore normale (la prova lo controlla). Usarle e' un passo a parte,
    misurato (handoff, §4, «Passo 8.6, punto 2»)."""
    global _ANNOTA
    if _ANNOTA is None:
        import guarda_avanti as G
        class CercatoreAnnota(G.Cercatore):
            def __init__(self, *a, **k):
                super().__init__(*a, **k)
                self.note, self._ora = [], None
            def agisci(self, p, i): self._ora = (p, i); return super().agisci(p, i)
            def attacca(self, p, i): self._ora = (p, i); return super().attacca(p, i)
            def blocca(self, p, i): self._ora = (p, i); return super().blocca(p, i)
            def bersagli(self, p, i, oggetto, reqs, legali, fa=()):
                self._ora = (p, i); return super().bersagli(p, i, oggetto, reqs, legali, fa)
            def _scegli(self, nome, cand):
                n = len(self.diario)
                m = super()._scegli(nome, cand)
                if len(self.diario) > n and self.diario[-1][4] != 0 and self._ora is not None:
                    p, i = self._ora
                    self.note.append({"gancio": nome, "turno": p.t.turno_numero, "fase": p.fase, "passo": p.passo, "giocatore": i,
                                      "semplice": descrivi(nome, cand[0][0], i), "scelta": descrivi(nome, m, i),
                                      "candidate": [descrivi(nome, c, i) for c, _ in cand], "punti": [round(float(x), 4) for x in self.diario[-1][3]],
                                      "prove": self.prove, "x": [float(z) for z in caratteristiche(p, i)]})
                return m
        _ANNOTA = CercatoreAnnota
    return _ANNOTA


def partita_cercatori(s, prove=PROVE_C, turni=TURNI_C, cerca=None, kw_prove=None, annota=True, valute=("v0", "v0")):
    """La partita del seme s fra due Cercatori leggeri (guarda_avanti.Cercatore con `prove` partite di prova a candidata,
    troncate `turni` turni dopo la scelta e giudicate dalla valutazione di oggi), sui mazzi di `coppia(s)`, arbitro acceso
    nella partita e in ogni partita di prova (CLAUDE.md di Magic_Arena, regola 3). Le posizioni a fine turno le scrive
    `Segna` (P della partita vera, non delle partite di prova: quelle ripartono da `effetti.Partita`). I Cercatori hanno
    dentro i Semplice dei semi 2s+1 e 2s+2, gli stessi di `_partita`: con cerca=() la partita e' quella fra due Semplice
    (la prova). kw_prove: gli argomenti delle partite di prova (solo le prove: un motore rotto apposta). valute: la versione
    della valutazione di ogni Cercatore (il giro del passo 8.6, punto 4). -> (partita, nastro, i due Cercatori)."""
    import guarda_avanti as G
    G._FOTO.clear()                                         # le foto della partita prima non servono piu' (memoria)
    M = S.mazzi_veri()
    a, b = coppia(s, len(M))
    nastro = []
    C = cercatore_che_annota() if annota else G.Cercatore
    def opzioni(v):                       # «v0», «v1», o «v0@0.05»: la versione e il margine (16 ott 2026)
        ver, _, m = v.partition("@")
        return ({} if ver == "v0" else {"valuta": ver}) | ({"margine": float(m)} if m else {})
    c = [C(s * 2 + 1 + i, prove=prove, turni=turni, **opzioni(valute[i]),
           **({} if cerca is None else {"cerca": cerca})) for i in (0, 1)]      # con v0 la chiamata di prima del passo 8.6
    for i, x in enumerate(c): x.collega(M[a], M[b], s, i, nastro, dict(kw_prove or {}))
    r = [G.Registro(x, i, nastro) for i, x in enumerate(c)]
    return S.partita(M[a], M[b], s, r[0], r[1], P=Segna), nastro, c


def _partita_c(arg):
    """Il lavoro di un processo: una partita fra Cercatori, giocata qui da cima a fondo (le partite di prova in fila, senza
    un pool dentro il pool: cosi' la cache delle foto e' tutta della stessa partita). -> la riga del file."""
    s, prove, turni, kw_prove = arg
    return _gioca_riga(s, prove, turni, kw_prove=kw_prove)


def _gioca_riga(s, prove, turni, **k):
    """Una partita fra Cercatori giocata e messa in riga (anche per il giro: k passa a partita_cercatori)."""
    import guarda_avanti as G
    t0 = time.time()
    try: p, nastro, c = partita_cercatori(s, prove, turni, **k)
    except S.ArbitroFischia as e: return {"seme": s, "errore": "FISCHIO: " + str(e)[:400]}
    except G.Divergenza as e: return {"seme": s, "errore": "DIVERGENZA: " + str(e)[:400]}
    v = p.t.vincitore if p.t.finita else None
    return {"seme": s, "mazzi": list(coppia(s, len(S.mazzi_veri()))), "prove": prove, "turni_prova": turni,
            "vincitore": v, "causa": S.come_finisce(p) if p.t.finita else "a tempo", "turni": p.t.turno_numero,
            "voci": len(nastro), "scelte": [len(x.diario) for x in c], "diverse": [sum(1 for d in x.diario if d[4] != 0) for x in c],
            "partite_di_prova": sum(len(d[2]) * prove for x in c for d in x.diario), "secondi": round(time.time() - t0, 1),
            "posizioni": [[int(n), [float(z) for z in x]] for n, x in getattr(p, "foto", [])],
            "impronta": impronta_eventi(p), "note": [n for x in c for n in getattr(x, "note", [])]}


def impronta_eventi(p):
    """L'impronta degli eventi della partita (per rifarla e controllare che sia la stessa). Dal 15 ott 2026 17:31 in ogni
    riga nuova del file, insieme alle note del Cercatore."""
    import hashlib
    ev = [(e.tipo, e.vecchio, e.nuovo, e.da, e.a, e.causa, e.giocatore, e.quanto) for e in p.t.eventi]
    return hashlib.sha1(repr(ev).encode()).hexdigest()


def leggi_cercatori(f=CERCATORI):
    """Le righe del file delle partite fra Cercatori (le partite gia' giocate). -> {seme: riga}."""
    if not os.path.exists(f): return {}
    out = {}
    for riga in open(f, encoding="utf-8"):
        if riga.strip():
            r = json.loads(riga); out[r["seme"]] = r
    return out


def dati_cercatori(a, b, prove=PROVE_C, turni=TURNI_C, processi=None, f=CERCATORI, kw_prove=None):
    """Le partite fra Cercatori dei semi a-b, una per processo, scritte riga per riga appena finiscono (un lavoro di ore:
    si ferma e si riprende, i semi gia' nel file non si rifanno). Al primo fischio o divergenza ci si ferma: la partita
    che fischia non si scrive (regola 3) e si cerca chi ha sbagliato prima di continuare. -> quante partite scritte."""
    gia = leggi_cercatori(f)
    semi = [s for s in range(a, b + 1) if s not in gia]
    t0, fatte, vinte0, decise = time.time(), 0, 0, 0
    print(f"semi {a}-{b}: {len(semi)} partite da giocare ({len(gia)} gia' nel file), Cercatori a {prove} prove, troncate a {turni} turni", flush=True)
    import multiprocessing as mp
    pool = mp.get_context("spawn").Pool(processi or max(1, (os.cpu_count() or 2) - 2), maxtasksperchild=25)
    try:
        with open(f, "a", encoding="utf-8") as h:
            for r in pool.imap_unordered(_partita_c, [(s, prove, turni, kw_prove) for s in semi], chunksize=1):
                if "errore" in r:
                    print(f"seme {r['seme']}: {r['errore']}", flush=True)
                    raise S.ArbitroFischia(f"seme {r['seme']}: {r['errore']}")
                h.write(json.dumps(r, ensure_ascii=False) + "\n"); h.flush()
                fatte += 1
                if r["vincitore"] is not None: decise += 1; vinte0 += r["vincitore"] == 0
                dt = time.time() - t0
                print(f"seme {r['seme']}: {'G1' if r['vincitore'] == 0 else 'G2' if r['vincitore'] == 1 else 'nessuno'} al turno {r['turni']}, "
                      f"{sum(r['scelte'])} scelte cercate ({sum(r['diverse'])} diverse dal Semplice), {r['partite_di_prova']} partite di prova, "
                      f"{r['secondi']:.0f} s | {fatte}/{len(semi)} in {dt / 60:.0f} min, fine fra ~{dt / fatte * (len(semi) - fatte) / 60:.0f} min", flush=True)
    finally:
        pool.terminate()
    return fatte


def posizioni_cercatori(f=CERCATORI, semi=None):
    """Le posizioni delle partite fra Cercatori, nella forma di valuta_posizioni.npz (le patte e le partite a tempo fuori,
    come in `raccogli`). semi: (da, a) per prenderne solo una parte. -> {X, y, seme, turno}."""
    X, y, sm, tu = [], [], [], []
    for s, r in sorted(leggi_cercatori(f).items()):
        if r["vincitore"] is None or (semi and not semi[0] <= s <= semi[1]): continue
        for n, x in r["posizioni"]:
            X.append(x); y.append(1.0 if r["vincitore"] == 0 else 0.0); sm.append(s); tu.append(n)
    return {"X": np.array(X, float).reshape(-1, len(BASE)), "y": np.array(y), "seme": np.array(sm), "turno": np.array(tu)}


def giocate(f=CERCATORI, quante=30):
    """Il quaderno delle giocate: le note del Cercatore (le scelte diverse dal Semplice) raggruppate per gancio, mossa del
    Semplice e mossa del Cercatore, le piu' frequenti per prime. Il guadagno e' quello detto dalle stesse partite di prova
    che hanno scelto, quindi ottimista (trappola (b) dell'8.5): una giocata «buona» qui e' un'ipotesi da confermare su
    mondi nuovi, non un fatto."""
    from collections import defaultdict
    R = leggi_cercatori(f)
    note = [n for r in R.values() for n in r.get("note", [])]
    print(f"{len(note)} note da {sum(1 for r in R.values() if 'note' in r)} partite (le righe prima del 15 ott 17:31 non hanno note)")
    g = defaultdict(list)
    for n in note: g[(n["gancio"], n["semplice"], n["scelta"])].append((max(n["punti"]) - n["punti"][0]) / n["prove"])
    for (gan, s, c), v in sorted(g.items(), key=lambda kv: (-len(kv[1]), -np.mean(kv[1])))[:quante]:
        print(f"{len(v):4d} x {gan}: il Semplice «{s}», il Cercatore «{c}» (+{np.mean(v):.2f} di probabilita' nelle prove che hanno scelto)")
    return g


def riassunto_cercatori(f=CERCATORI):
    """Cosa c'e' nel file: partite, come finiscono, quanto costano, quanto il Cercatore leggero si stacca dal Semplice, e
    come la valutazione di oggi (V0, allenata sui Semplice) legge le loro posizioni. Non allena niente (e' il punto 3)."""
    R = leggi_cercatori(f)
    if not R: print("nessuna partita fra Cercatori"); return None
    rr = list(R.values())
    dec = [r for r in rr if r["vincitore"] is not None]
    sc, dv = sum(sum(r["scelte"]) for r in rr), sum(sum(r["diverse"]) for r in rr)
    out = {"partite": len(rr), "decise": len(dec), "vinte_G1": sum(r["vincitore"] == 0 for r in dec),
           "turni_medi": float(np.mean([r["turni"] for r in rr])), "scelte": sc, "diverse": dv,
           "partite_di_prova": sum(r["partite_di_prova"] for r in rr), "secondi_medi": float(np.mean([r["secondi"] for r in rr])),
           "cause": {c: sum(1 for r in rr if r["causa"] == c) for c in sorted({str(r["causa"]) for r in rr})}}
    D = posizioni_cercatori(f)
    out["posizioni"] = int(len(D["y"]))
    print(f"{out['partite']} partite fra Cercatori ({out['decise']} decise, G1 ne vince {out['vinte_G1']}), turni in media "
          f"{out['turni_medi']:.1f}, cause {out['cause']}")
    print(f"scelte cercate {sc}, diverse dal Semplice {dv} ({dv / max(sc, 1):.1%}); {out['partite_di_prova']} partite di prova; "
          f"{out['secondi_medi']:.0f} s a partita in un processo")
    if len(D["y"]) > 100:
        m = misura(modello(), D["X"], D["y"], D["seme"], D["turno"])
        out["V0"] = {k: v for k, v in m.items() if k not in ("calibratura", "per_turno")}
        print(f"V0 sulle loro posizioni: {m['posizioni']} posizioni, Brier {m['brier']:.4f} (base {m['brier_base']:.4f}, skill "
              f"{m['skill']:.1%}), AUC {m['auc']:.3f}, ECE {m['ece']:.4f}")
        for da, a, n, np_, d, v, scx in m["calibratura"]:
            print(f"  {da:.0%}-{a:.0%}: {n:6d} posizioni, {np_:5d} partite, detto {d:.1%}, vinto {v:.1%}, scarto {scx:+.1f} e.s.")
        for da, a, n, d, v, b, e in m["per_turno"]:
            print(f"  turni {da}-{a if a < 999 else '...'}: {n} posizioni, detto {d:.1%}, vinto {v:.1%}, Brier {b:.4f}, ECE {e:.4f}")
    return out


# ====================================================================== la V1 e il giro (passo 8.6, punti 3 e 4)
def misura_versione(mod, D):
    return misura(mod, D["X"], D["y"], D["seme"], D["turno"])


def allena_versione(v="v1", allena_semi=ALLENA_C, misura_semi=MISURA_C, scrivi=True, f=CERCATORI):
    """Il punto 3: la valutazione allenata sulle posizioni delle partite fra Cercatori (semi `allena_semi`), misurata sui
    semi `misura_semi` con lo stesso metro dell'8.5, accanto a V0 sugli stessi semi e a tutte e due sulle partite fra
    Semplice (semi MISURA). Pesi in valuta_pesi_<v>.json (V0 resta), rapporto in Valuta_Tavolo_<V>.md."""
    tr, te = posizioni_cercatori(f, allena_semi), posizioni_cercatori(f, misura_semi)
    if len(tr["y"]) < 1000 or len(te["y"]) < 1000: raise RuntimeError(f"posizioni troppo poche: {len(tr['y'])} e {len(te['y'])}")
    mod = allena(tr["X"], tr["turno"], tr["y"])
    mod.info = {"allenato": datetime.now().strftime("%Y-%m-%dT%H:%M"), "semi_allenamento": list(allena_semi),
                "posizioni_allenamento": int(len(tr["y"])), "partite_allenamento": int(len(np.unique(tr["seme"]))),
                "giocatori": f"due guarda_avanti.Cercatore(prove={PROVE_C}, turni={TURNI_C}) con V0, arbitro acceso, i 10 mazzi veri"}
    m = {"tr": misura_versione(mod, tr), "te": misura_versione(mod, te), "v0_te": misura_versione(modello("v0"), te)}
    D = dict(np.load(DATI)); _, ts = separa(D)
    Ds = {k: D[k][ts] for k in ("X", "y", "seme", "turno")}
    m["semplici"], m["v0_semplici"] = misura_versione(mod, Ds), misura_versione(modello("v0"), Ds)
    mod.info["misura"] = {k: v_ for k, v_ in m["te"].items() if k not in ("calibratura", "per_turno")}
    for nome, k in (("V1 allenamento", "tr"), ("V1 misura (Cercatori)", "te"), ("V0 misura (Cercatori)", "v0_te"),
                    ("V1 sui Semplice", "semplici"), ("V0 sui Semplice", "v0_semplici")):
        x = m[k]
        print(f"{nome}: {x['posizioni']} posizioni da {x['partite']} partite; Brier {x['brier']:.4f} (base {x['brier_base']:.4f}, "
              f"skill {x['skill']:.1%}), AUC {x['auc']:.3f}, ECE {x['ece']:.4f}; per fase " +
              " · ".join(f"{da}-{a}: {e:.3f}" for da, a, n, d, vv, b, e in x["per_turno"]))
    for da, a, n, np_, d, vv, sc in m["te"]["calibratura"]:
        print(f"  V1 {da:.0%}-{a:.0%}: {n:6d} posizioni, {np_:5d} partite, detto {d:.1%}, vinto {vv:.1%}, scarto {sc:+.1f} e.s.")
    if scrivi:
        mod.salva(pesi_di(v))
        _MODELLI.pop(v, None)
        rapporto_versione(v, mod, m)
    return mod, m


def rapporto_versione(v, mod, m):
    V0 = modello("v0")
    w0 = dict(zip(COLONNE, V0.w))
    righe = ["---", "tipo: misura", f"creato: {datetime.now().strftime('%Y-%m-%dT%H:%M')}", f"aggiornato: {datetime.now().strftime('%Y-%m-%dT%H:%M')}", "---", "",
             f"# La valutazione del tavolo {v.upper()} (passo 8.6, punto 3)", "",
             f"La stessa regressione logistica di V0 (`Valuta_Tavolo.md`), allenata sulle posizioni delle partite fra due Cercatori "
             f"leggeri ({PROVE_C} partite di prova a candidata, troncate a {TURNI_C} turni e giudicate da V0), arbitro acceso, i 10 mazzi "
             f"veri. Allenamento: semi {mod.info['semi_allenamento'][0]}-{mod.info['semi_allenamento'][1]} "
             f"({mod.info['partite_allenamento']} partite, {mod.info['posizioni_allenamento']} posizioni). Misura: le partite fra Cercatori "
             f"dei semi {MISURA_C[0]}-{MISURA_C[1]}, mai viste dall'allenamento, e le 2.000 partite fra Semplice della misura di V0. "
             f"Vuol dire: la probabilita' di vincere se da li' giocano due Cercatori leggeri. Non e' il valore per un giocatore bravo.", "",
             f"Scritto da `py -I -X utf8 Motore_Partita/valuta.py --allena-versione {v}` il {datetime.now().strftime('%Y-%m-%d %H:%M')}.", "",
             "## La misura", "", "| Modello | Partite | Posizioni | Brier | Brier base | Skill | AUC | ECE | ECE peggiore per fase |",
             "| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for nome, k in ((f"{v.upper()}, allenamento", "tr"), (f"**{v.upper()}, misura fra Cercatori**", "te"), ("V0, misura fra Cercatori", "v0_te"),
                    (f"{v.upper()}, misura fra Semplice", "semplici"), ("V0, misura fra Semplice", "v0_semplici")):
        x = m[k]
        righe.append(f"| {nome} | {x['partite']} | {x['posizioni']} | {x['brier']:.4f} | {x['brier_base']:.4f} | {x['skill']:.1%} | "
                     f"{x['auc']:.3f} | {x['ece']:.4f} | {max(e for *_, e in x['per_turno']):.4f} |")
    righe += ["", f"## La calibratura di {v.upper()} sulle partite fra Cercatori della misura", "",
              "L'errore standard e' a grappoli per partita (come nell'8.5).", "",
              "| Fascia | Posizioni | Partite | Detto | Vinto | Scarto (e.s.) |", "| :--- | ---: | ---: | ---: | ---: | ---: |"]
    for da, a, n, np_, d, vv, sc in m["te"]["calibratura"]:
        righe.append(f"| {da:.0%}-{a:.0%} | {n} | {np_} | {d:.1%} | {vv:.1%} | {sc:+.1f} |")
    righe += ["", "## Per fase (partite fra Cercatori della misura)", "", f"| Turni | Posizioni | Detto | Vinto | Brier {v.upper()} | ECE {v.upper()} | ECE V0 |",
              "| :--- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for (da, a, n, d, vv, b, e), (*_, e0) in zip(m["te"]["per_turno"], m["v0_te"]["per_turno"]):
        righe.append(f"| {da}-{a if a < 999 else '...'} | {n} | {d:.1%} | {vv:.1%} | {b:.4f} | {e:.4f} | {e0:.4f} |")
    righe += ["", f"## I pesi, {v.upper()} accanto a V0 (standardizzati)", "", f"| Caratteristica | {v.upper()} | V0 |", "| :--- | ---: | ---: |"]
    for n, w in sorted(zip(COLONNE, mod.w), key=lambda x: -abs(x[1])):
        righe.append(f"| {n} | {w:+.3f} | {w0[n]:+.3f} |")
    open(os.path.join(QUI, f"Valuta_Tavolo_{v.upper()}.md"), "w", encoding="utf-8").write("\n".join(righe) + "\n")


GIRO = os.path.join(QUI, "giro_{a}_{b}.jsonl")


def _partita_giro(arg):
    """Una partita del giro: la versione a al posto `posto` (0 o 1), la versione b all'altro. Stessi mazzi e stessi
    Semplice dentro i Cercatori della partita col posto scambiato: cambia solo chi ha quale valutazione."""
    s, va, vb, posto = arg
    r = _gioca_riga(s, PROVE_C, TURNI_C, valute=(va, vb) if posto == 0 else (vb, va))
    r.update({"versioni": [va, vb], "posto": posto})
    if "errore" not in r: r["vince_a"] = None if r["vincitore"] is None else int(r["vincitore"] == posto)
    return r


def leggi_giro(va, vb):
    f = GIRO.format(a=va, b=vb)
    if not os.path.exists(f): return {}
    return {(r["seme"], r["posto"]): r for r in (json.loads(x) for x in open(f, encoding="utf-8") if x.strip())}


def giro(a, b, va="v1", vb="v0", processi=None):
    """Il punto 4: la versione va contro la vb sui semi a-b, ogni seme due volte a posti scambiati (coppie: stessi mazzi,
    stessi mondi del caso, cambia solo la valutazione). Una partita per processo, una riga a partita appena finisce
    (giro_<va>_<vb>.jsonl: si riprende da dove si e' fermato), fermo al primo fischio. Le posizioni a fine turno restano nelle
    righe: sono i dati della versione dopo."""
    f = GIRO.format(a=va, b=vb)
    gia = leggi_giro(va, vb)
    lavori = [(s, va, vb, posto) for s in range(a, b + 1) for posto in (0, 1) if (s, posto) not in gia]
    t0, fatte = time.time(), 0
    print(f"giro {va} contro {vb}, semi {a}-{b}: {len(lavori)} partite da giocare ({len(gia)} gia' nel file)", flush=True)
    import multiprocessing as mp
    pool = mp.get_context("spawn").Pool(processi or max(1, (os.cpu_count() or 2) - 2), maxtasksperchild=25)
    try:
        with open(f, "a", encoding="utf-8") as h:
            for r in pool.imap_unordered(_partita_giro, lavori, chunksize=1):
                if "errore" in r:
                    print(f"seme {r['seme']}: {r['errore']}", flush=True)
                    raise S.ArbitroFischia(f"seme {r['seme']}: {r['errore']}")
                h.write(json.dumps(r, ensure_ascii=False) + "\n"); h.flush()
                fatte += 1
                dt = time.time() - t0
                print(f"seme {r['seme']} posto {r['posto']}: {'vince ' + va if r['vince_a'] == 1 else 'vince ' + vb if r['vince_a'] == 0 else 'nessuno'} "
                      f"al turno {r['turni']}, {r['secondi']:.0f} s | {fatte}/{len(lavori)} in {dt / 60:.0f} min, fine fra ~{dt / fatte * (len(lavori) - fatte) / 60:.0f} min", flush=True)
    finally:
        pool.terminate()
    return riassunto_giro(va, vb)


def riassunto_giro(va="v1", vb="v0"):
    """Vittorie di va, intervallo di Wilson al 95%, e le coppie (lo stesso seme ai due posti): quelle vinte due volte da va
    contro quelle vinte due volte da vb, col test dei segni (le coppie divise non contano)."""
    R = leggi_giro(va, vb)
    dec = [r for r in R.values() if r.get("vince_a") is not None]
    v = sum(r["vince_a"] for r in dec)
    lo, hi = S.wilson(v, len(dec))
    semi = sorted({s for s, _ in R})
    doppie_a = sum(1 for s in semi if all((s, p) in R and R[(s, p)].get("vince_a") == 1 for p in (0, 1)))
    doppie_b = sum(1 for s in semi if all((s, p) in R and R[(s, p)].get("vince_a") == 0 for p in (0, 1)))
    n, k = doppie_a + doppie_b, max(doppie_a, doppie_b)
    p_segni = 1.0 if n == 0 else min(1.0, 2 * sum(math.comb(n, j) for j in range(k, n + 1)) / 2 ** n)
    out = {"partite": len(R), "decise": len(dec), "vinte": v, "wilson": (lo, hi), "coppie_doppie": (doppie_a, doppie_b), "p_segni": p_segni}
    print(f"{va} contro {vb}: {v}/{len(dec)} ({v / max(len(dec), 1):.1%}, 95% {lo:.1%}-{hi:.1%}); coppie vinte due volte: "
          f"{va} {doppie_a}, {vb} {doppie_b} (test dei segni p {p_segni:.4f})")
    return out


# ====================================================================== la misura
def brier(q, y): return float(np.mean((q - y) ** 2))


def logloss(q, y):
    q = np.clip(q, 1e-9, 1 - 1e-9)
    return float(-np.mean(y * np.log(q) + (1 - y) * np.log(1 - q)))


def auc(q, y):
    """L'area sotto la curva ROC (Mann-Whitney): la probabilita' che una posizione vinta abbia un detto piu' alto di una persa."""
    o = np.argsort(q, kind="mergesort")
    r = np.empty(len(q)); r[o] = np.arange(1, len(q) + 1)
    _, gruppo = np.unique(q, return_inverse=True)                         # i pari: rango medio del gruppo
    r = (np.bincount(gruppo, weights=r) / np.bincount(gruppo))[gruppo]
    n1, n0 = y.sum(), len(y) - y.sum()
    return float((r[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def calibratura(q, y, seme, fasce=10):
    """Detto contro vinto per fasce di probabilita'. Le posizioni di una partita hanno lo stesso risultato: l'errore
    standard e' quello a grappoli per partita, sqrt(somma sulle partite di (somma di y - q nella fascia)^2) / posizioni.
    Contare le partite come se pesassero uguale (la prima versione, 14 ott 2026) lo sottostima: una partita con sei
    posizioni nella fascia pesa sei volte. -> righe (da, a, posizioni, partite, detto, vinto, scarto in errori standard)."""
    out = []
    lati = np.linspace(0, 1, fasce + 1)
    for k in range(fasce):
        m = (q >= lati[k]) & ((q < lati[k + 1]) if k < fasce - 1 else (q <= 1))
        if not m.any(): continue
        _, g = np.unique(seme[m], return_inverse=True)
        d, v = float(q[m].mean()), float(y[m].mean())
        es = math.sqrt(float((np.bincount(g, weights=y[m] - q[m]) ** 2).sum())) / m.sum()
        out.append((lati[k], lati[k + 1], int(m.sum()), int(g.max() + 1), d, v, (v - d) / max(es, 1e-9)))
    return out


def ece(q, y, fasce=10):
    lati = np.linspace(0, 1, fasce + 1)
    tot = 0.0
    for k in range(fasce):
        m = (q >= lati[k]) & ((q < lati[k + 1]) if k < fasce - 1 else (q <= 1))
        if m.any(): tot += m.sum() * abs(q[m].mean() - y[m].mean())
    return tot / len(q)


def misura(mod, X, y, seme, turno):
    q = mod.p(X, turno)
    base = float(y.mean())
    out = {"posizioni": int(len(y)), "partite": int(len(np.unique(seme))), "vinte_G1": base,
           "brier": brier(q, y), "brier_base": brier(np.full_like(y, base), y), "logloss": logloss(q, y),
           "auc": auc(q, y), "ece": ece(q, y), "calibratura": calibratura(q, y, seme)}
    out["skill"] = 1 - out["brier"] / out["brier_base"]
    out["per_turno"] = []
    for da, a in ((1, 4), (5, 8), (9, 12), (13, 999)):
        m = (turno >= da) & (turno <= a)
        if m.sum() > 100:
            out["per_turno"].append((da, a, int(m.sum()), float(q[m].mean()), float(y[m].mean()), brier(q[m], y[m]), ece(q[m], y[m])))
    return out


def separa(D):
    tr = (D["seme"] >= ALLENA[0]) & (D["seme"] <= ALLENA[1])
    te = (D["seme"] >= MISURA[0]) & (D["seme"] <= MISURA[1])
    return tr, te


def allena_e_misura(scrivi=True):
    D = dict(np.load(DATI))
    tr, te = separa(D)
    if not tr.any() or not te.any(): raise RuntimeError(f"servono i semi {ALLENA} e {MISURA} in {DATI} (--dati)")
    t0 = time.time()
    mod = allena(D["X"][tr], D["turno"][tr], D["y"][tr])
    mod.info = {"allenato": datetime.now().strftime("%Y-%m-%dT%H:%M"), "semi_allenamento": list(ALLENA),
                "posizioni_allenamento": int(tr.sum()), "partite_allenamento": int(len(np.unique(D["seme"][tr]))),
                "giocatori": "due simula.Semplice, arbitro acceso, i 10 mazzi veri (mazzi_veri.json)"}
    m_tr = misura(mod, D["X"][tr], D["y"][tr], D["seme"][tr], D["turno"][tr])
    m_te = misura(mod, D["X"][te], D["y"][te], D["seme"][te], D["turno"][te])
    mod.info["misura"] = {k: v for k, v in m_te.items() if k not in ("calibratura", "per_turno")}
    print(f"allenato in {time.time() - t0:.1f} s su {tr.sum()} posizioni")
    stampa(mod, m_tr, m_te)
    if scrivi:
        mod.salva()
        rapporto(mod, m_tr, m_te)
    return mod, m_tr, m_te


def stampa(mod, m_tr, m_te):
    for n, w in sorted(zip(COLONNE, mod.w / mod.scala), key=lambda x: -abs(x[1] * 1)):
        print(f"  {n:34s} {w:+.4f}")
    for nome, m in (("allenamento", m_tr), ("misura", m_te)):
        print(f"{nome}: {m['posizioni']} posizioni da {m['partite']} partite; Brier {m['brier']:.4f} (base {m['brier_base']:.4f}, "
              f"skill {m['skill']:.1%}), log-loss {m['logloss']:.4f}, AUC {m['auc']:.3f}, ECE {m['ece']:.4f}")
    for da, a, n, np_, d, v, sc in m_te["calibratura"]:
        print(f"  {da:.0%}-{a:.0%}: {n:6d} posizioni, {np_:5d} partite, detto {d:.1%}, vinto {v:.1%}, scarto {sc:+.1f} e.s.")
    for da, a, n, d, v, b, e in m_te["per_turno"]:
        print(f"  turni {da}-{a if a < 999 else '...'}: {n} posizioni, detto {d:.1%}, vinto {v:.1%}, Brier {b:.4f}, ECE {e:.4f}")


def rapporto(mod, m_tr, m_te):
    righe = ["---", "tipo: misura", f"creato: 2026-10-14T20:30", f"aggiornato: {datetime.now().strftime('%Y-%m-%dT%H:%M')}", "---", "",
             "# La valutazione del tavolo (passo 8.5)", "",
             "Una probabilita' di vincere detta dal tavolo a fine turno: la regressione logistica di `valuta.py` su caratteristiche "
             "scritte, «mia meno sua», senza intercetta (P mia + P sua = 1 per costruzione). Allenata su partite fra due "
             "`simula.Semplice` coi 10 mazzi veri, arbitro acceso; misurata su partite con semi mai visti dall'allenamento. "
             "Vuol dire: la probabilita' di vincere se da li' giocano due Semplice. Non e' il valore per un giocatore bravo.", "",
             f"Scritto da `py -I -X utf8 Motore_Partita/valuta.py --allena` il {datetime.now().strftime('%Y-%m-%d %H:%M')}.", "",
             "## I pesi (per unita' della caratteristica)", "", "| Caratteristica | Peso | Peso standardizzato |", "| :--- | ---: | ---: |"]
    for n, w, ws in sorted(zip(COLONNE, mod.w / mod.scala, mod.w), key=lambda x: -abs(x[2])):
        righe.append(f"| {n} | {w:+.4f} | {ws:+.3f} |")
    righe += ["", "## La misura", "", "| | Posizioni | Partite | Brier | Brier base | Skill | Log-loss | AUC | ECE |",
              "| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for nome, m in (("allenamento", m_tr), ("**misura** (semi nuovi)", m_te)):
        righe.append(f"| {nome} | {m['posizioni']} | {m['partite']} | {m['brier']:.4f} | {m['brier_base']:.4f} | {m['skill']:.1%} | "
                     f"{m['logloss']:.4f} | {m['auc']:.3f} | {m['ece']:.4f} |")
    righe += ["", "## La calibratura sui semi della misura (detto contro vinto)", "",
              "L'errore standard di ogni fascia conta le partite distinte, non le posizioni (le posizioni di una partita hanno "
              "lo stesso risultato).", "", "| Fascia | Posizioni | Partite | Detto | Vinto | Scarto (e.s.) |", "| :--- | ---: | ---: | ---: | ---: | ---: |"]
    for da, a, n, np_, d, v, sc in m_te["calibratura"]:
        righe.append(f"| {da:.0%}-{a:.0%} | {n} | {np_} | {d:.1%} | {v:.1%} | {sc:+.1f} |")
    righe += ["", "## Per fase della partita (semi della misura)", "", "| Turni | Posizioni | Detto | Vinto | Brier | ECE |", "| :--- | ---: | ---: | ---: | ---: | ---: |"]
    for da, a, n, d, v, b, e in m_te["per_turno"]:
        righe.append(f"| {da}-{a if a < 999 else '...'} | {n} | {d:.1%} | {v:.1%} | {b:.4f} | {e:.4f} |")
    open(RAPPORTO, "w", encoding="utf-8").write("\n".join(righe) + "\n")


# ====================================================================== quante partite servono (passo 8.6, punto 2)
def curva(passi=(125, 250, 500, 1000, 2000, 4000, 8000), ripetizioni=5, f=DATI):
    """La curva di apprendimento: lo stesso modello allenato su n partite prese a caso fra quelle dell'allenamento (n per
    `passi`, `ripetizioni` sorteggi diversi per ogni n sotto il totale), misurato sempre sulle stesse partite della misura.
    Dice quante partite servono prima che la misura smetta di migliorare: e' la misura che decide quante partite fra
    Cercatori giocare (handoff, §5, piano dell'8.6, punto 2). -> righe (n, sorteggi, skill media, min, max, AUC, ECE, ECE
    peggiore per fase, fasce fuori di 3 e.s.)."""
    D = dict(np.load(f))
    tr, te = separa(D)
    giochi = np.unique(D["seme"][tr])
    Xte, yte, ste, tte = D["X"][te], D["y"][te], D["seme"][te], D["turno"][te]
    out = []
    for n in passi:
        n = min(n, len(giochi))
        rip = 1 if n == len(giochi) else ripetizioni
        ms = []
        for r in range(rip):
            scelti = np.random.default_rng([n, r, 8602]).choice(giochi, size=n, replace=False)
            m_ = np.isin(D["seme"], scelti) & tr
            mod = allena(D["X"][m_], D["turno"][m_], D["y"][m_])
            ms.append(misura(mod, Xte, yte, ste, tte))
        sk = [m["skill"] for m in ms]
        fuori = max(sum(1 for *_, np_, d, v, sc in m["calibratura"] if np_ >= 30 and abs(sc) > 3) for m in ms)
        out.append((n, rip, float(np.mean(sk)), float(min(sk)), float(max(sk)), float(np.mean([m["auc"] for m in ms])),
                    float(np.mean([m["ece"] for m in ms])), float(max(max(e for *_, e in m["per_turno"]) for m in ms)), fuori))
        print(f"{n:5d} partite ({rip} sorteggi): skill {out[-1][2]:.1%} ({out[-1][3]:.1%}-{out[-1][4]:.1%}), AUC {out[-1][5]:.3f}, "
              f"ECE {out[-1][6]:.4f}, ECE peggiore per fase {out[-1][7]:.4f}, fasce fuori {fuori}", flush=True)
    return out


# ====================================================================== le prove
def prova():
    casi = []
    def caso(nome, ok, det=""): casi.append((nome, bool(ok), det))
    t0 = time.time()
    D = dict(np.load(DATI))
    tr, te = separa(D)
    mod = Modello.carica()
    Xte, yte, ste, tte = D["X"][te], D["y"][te], D["seme"][te], D["turno"][te]
    m = misura(mod, Xte, yte, ste, tte)

    # 1. il modello salvato e' quello che si ottiene riallenando sugli stessi dati
    rif = allena(D["X"][tr], D["turno"][tr], D["y"][tr])
    caso("il modello salvato e' quello dei dati (riallenato sugli stessi semi: stessi pesi)",
         np.allclose(rif.w, mod.w, atol=1e-6) and np.allclose(rif.scala, mod.scala), f"scarto massimo {np.abs(rif.w - mod.w).max():.2e}")
    caso("allenamento e misura su semi diversi (nessuna partita in comune)",
         not (set(D["seme"][tr].tolist()) & set(ste.tolist())) and te.sum() > 10000, f"{tr.sum()} e {te.sum()} posizioni")

    # 2. l'antisimmetria: P(io) + P(lui) = 1 sulle posizioni vere
    s = mod.p(Xte, tte) + mod.p(-Xte, tte)
    caso("P(io vinco) + P(lui vince) = 1 su ogni posizione della misura (niente intercetta, caratteristiche antisimmetriche)",
         np.abs(s - 1).max() < 1e-9, f"scarto massimo {np.abs(s - 1).max():.1e}")

    # 3. discrimina. La prima soglia (skill 30% e AUC 0,80 su tutte le posizioni, fissata prima di vedere i dati) e'
    # rossa: 25,5% e 0,788 il 14 ott 2026, perche' nei turni 1-4 il tavolo dice quasi niente (skill 3%). Si misura invece
    # contro i modelli piu' poveri sugli stessi semi, e la soglia di prima da meta' partita in poi.
    def povero(nomi):
        k = [NOMI.index(n) for n in nomi] + [len(NOMI)]
        def sub(X): Z = np.zeros_like(X); Z[:, k] = X[:, k]; return Z
        return misura(allena(sub(D["X"][tr]), D["turno"][tr], D["y"][tr]), sub(Xte), yte, ste, tte)
    p1, p3 = povero(["vite"]), povero(["vite", "creature", "forza"])
    caso("discrimina meglio dei modelli poveri sugli stessi semi nuovi: skill oltre le sole vite di 5 punti e oltre vite, creature e forza",
         m["skill"] > p1["skill"] + 0.05 and m["skill"] > p3["skill"] and m["auc"] > p3["auc"],
         f"skill {m['skill']:.1%} (vite {p1['skill']:.1%}, vite+creature+forza {p3['skill']:.1%}), AUC {m['auc']:.3f} ({p1['auc']:.3f}, {p3['auc']:.3f})")
    tardi = tte >= 9
    m9 = misura(mod, Xte[tardi], yte[tardi], ste[tardi], tte[tardi])
    caso("discrimina dal turno 9: Brier skill oltre 30% e AUC oltre 0,80", m9["skill"] > 0.30 and m9["auc"] > 0.80,
         f"skill {m9['skill']:.1%}, AUC {m9['auc']:.3f} su {m9['posizioni']} posizioni")

    # 4. calibrato: ogni fascia dentro 3 errori standard (contati per partita), ECE sotto 0,02
    fuori = [(round(da, 1), round(sc, 1)) for da, a, n, np_, d, v, sc in m["calibratura"] if np_ >= 30 and abs(sc) > 3]
    caso("calibrato sui semi nuovi: ogni fascia con 30 partite o piu' dentro 3 errori standard, ECE sotto 0,02",
         not fuori and m["ece"] < 0.02, f"ECE {m['ece']:.4f}, fasce fuori {fuori}")
    caso("calibrato anche per fase della partita: ECE sotto 0,03 in ogni fascia di turni",
         all(e < 0.03 for *_, e in m["per_turno"]), " · ".join(f"{da}-{a}: {e:.3f}" for da, a, n, d, v, b, e in m["per_turno"]))

    # 5. il senso: chi ha piu' vite, piu' forza, la pressione, il prossimo turno, conta in positivo
    w = dict(zip(COLONNE, mod.w))
    segni = {c: w[c] for c in ("vite (mia - sua)", "forza (mia - sua)", "pressione (mia - sua)", "mano (mia - sua)")}
    caso("senso: vite, forza, pressione e carte in mano in piu' alzano la probabilita' (pesi positivi)",
         all(v > 0 for v in segni.values()), str({k.split(" ")[0]: round(v, 3) for k, v in segni.items()}))
    x = np.zeros(len(BASE)); x[NOMI.index("vite")] = 10
    caso("senso: 10 vite in piu' a parita' di tutto, al turno 10: sopra il 60%", mod.p(x, 10) > 0.6, f"{mod.p(x, 10):.1%}")

    # 5.bis nessuna caratteristica da sola decide: contributo a z sotto 5 su ogni posizione della misura (14 ott 2026: con
    # le interazioni su tutte e quattordici, «letale x presto» arrivava a 11 da sola)
    def massimo(m_):
        return float(np.abs(espandi(Xte, tte) / m_.scala * m_.w).max())
    caso("nessuna caratteristica da sola sposta il giudizio di oltre 5 punti di z (sulle posizioni della misura)", massimo(mod) < 5,
         f"massimo {massimo(mod):.2f}")
    global espandi
    giusta = espandi
    def tutte(X, turno):
        X = np.atleast_2d(np.asarray(X, float))
        return np.hstack([X, X * np.clip(1 - np.asarray(turno, float).reshape(-1, 1) / PRESTO, 0, None)])
    try:
        espandi = tutte
        m14 = allena(D["X"][tr], D["turno"][tr], D["y"][tr]); mx14 = massimo(m14)
    finally: espandi = giusta
    caso("prova negativa: con le interazioni su tutte e quattordici la prova di sopra e' rossa", mx14 > 5, f"massimo {mx14:.2f}")

    # 6. le prove negative
    rng = np.random.default_rng(5)
    giochi = np.unique(D["seme"][tr]); vinto = {g: D["y"][tr][D["seme"][tr] == g][0] for g in giochi}
    perm = dict(zip(giochi, rng.permutation([vinto[g] for g in giochi])))
    y_mesc = np.array([perm[g] for g in D["seme"][tr]])
    m_mesc = misura(allena(D["X"][tr], D["turno"][tr], y_mesc), Xte, yte, ste, tte)
    caso("prova negativa: allenato coi risultati mescolati fra le partite non discrimina (skill sotto 2%: la prova 3 sarebbe rossa)",
         m_mesc["skill"] < 0.02, f"skill {m_mesc['skill']:.1%}, AUC {m_mesc['auc']:.3f}")
    rotto = Modello(-mod.w, mod.scala)
    m_r = misura(rotto, Xte, yte, ste, tte)
    caso("prova negativa: i pesi ribaltati sono scalibrati (ECE oltre 0,2: la prova 4 sarebbe rossa)", m_r["ece"] > 0.2, f"ECE {m_r['ece']:.3f}")
    Xs = Xte.copy(); Xs[:, NOMI.index("vite")] *= -1                     # le vite lette dal lato sbagliato
    m_s = misura(mod, Xs, yte, ste, tte)
    fuori_s = [1 for *_, np_, d, v, sc in m_s["calibratura"] if np_ >= 30 and abs(sc) > 3]
    caso("prova negativa: le vite lette dal lato sbagliato fanno uscire la calibratura (fasce fuori o ECE oltre 0,02)",
         fuori_s or m_s["ece"] > 0.02, f"ECE {m_s['ece']:.4f}, fasce fuori {len(fuori_s)}")

    # 7. sul tavolo vero: la valutazione di una partita in corso, dai due lati, somma a 1, e la partita finita la dice giusta
    M = S.mazzi_veri()
    p = S.partita(M[0], M[3], 77, S.Semplice(1), S.Semplice(2), P=Segna)
    foto = getattr(p, "foto", [])
    q0 = mod.p(foto[-1][1], foto[-1][0]) if foto else None
    caso("sul tavolo vero: l'ultima posizione prima della fine favorisce chi ha vinto", q0 is not None and (q0 > 0.5) == (p.t.vincitore == 0),
         f"vincitore G{(p.t.vincitore or 0) + 1}, detto per G1 {q0 if q0 is not None else float('nan'):.1%}")
    # 8. le partite fra Cercatori (passo 8.6, punto 2)
    def ch(p): return [(e.tipo, e.vecchio, e.nuovo, e.da, e.a, e.causa, e.giocatore, e.quanto) for e in p.t.eventi]
    uguali, segna_ok = [], []
    for s in (40000, 40001, 40002):
        a, b = coppia(s, len(M))
        ps = S.partita(M[a], M[b], s, S.Semplice(s * 2 + 1), S.Semplice(s * 2 + 2), P=Segna)
        pe = S.partita(M[a], M[b], s, S.Semplice(s * 2 + 1), S.Semplice(s * 2 + 2), P=E.Partita)
        q, _, c = partita_cercatori(s, cerca=())
        segna_ok.append(ch(ps) == ch(pe))
        uguali.append(ch(q) == ch(ps) and [(n, x.tolist()) for n, x in q.foto] == [(n, x.tolist()) for n, x in ps.foto]
                      and not any(x.diario for x in c))
    caso("Segna non cambia la partita (3 semi, evento per evento uguale a effetti.Partita)", all(segna_ok), f"{sum(segna_ok)}/3")
    caso("Cercatori con la ricerca spenta (cerca=()): la partita e le posizioni sono quelle fra i due Semplice degli stessi semi",
         all(uguali), f"{sum(uguali)}/3")
    import multiprocessing as mp
    import tempfile
    import guarda_avanti as G
    pool = mp.get_context("spawn").Pool(4)
    try:
        r1, r2, rotta, rif, senza, storte = pool.map(_prova_c, [(40003, None), (40003, None), (40003, {"P": G.SenzaStato}), (40004, "replay"),
                                                                (40003, "senza_note"), (40003, "note_storte")], chunksize=1)
    finally: pool.terminate()
    note = r1.get("note", [])
    caso("le note del Cercatore non cambiano la partita: stessa impronta del Cercatore che non annota", r1.get("impronta") == senza,
         f"{r1.get('impronta', '')[:10]} e {str(senza)[:10]}")
    caso("una nota per ogni scelta diversa dal Semplice, in parole (carte per nome) e con le caratteristiche del tavolo",
         len(note) == sum(r1.get("diverse", [])) > 0 and all(n["scelta"] != n["semplice"] and len(n["x"]) == len(BASE) for n in note),
         f"{len(note)} note; per esempio: {note[0]['gancio']} turno {note[0]['turno']}, il Semplice «{note[0]['semplice']}», il Cercatore «{note[0]['scelta']}»" if note else "nessuna nota")
    caso("prova negativa: un Cercatore le cui note cambiano la scelta gioca un'altra partita (l'impronta lo vede)",
         storte is not None and storte != senza, f"{str(storte)[:10]}")
    def senza_tempo(r): return {k: v for k, v in r.items() if k != "secondi"}
    caso("una partita fra Cercatori leggeri (2 prove, troncate a 1 turno) finisce, arbitro zitto, e stesso seme in due processi "
         "e' la stessa partita (posizioni comprese)", "errore" not in r1 and r1["vincitore"] is not None and senza_tempo(r1) == senza_tempo(r2),
         f"G{(r1.get('vincitore') or 0) + 1} al turno {r1.get('turni')}, {r1.get('errore', '')[:80]}")
    caso("le scelte dei Cercatori non sono tutte quelle del Semplice (se lo fossero, i dati sarebbero quelli di V0)",
         "errore" not in r1 and sum(r1["diverse"]) > 0, f"{sum(r1.get('diverse', [0]))} diverse su {sum(r1.get('scelte', [0]))} cercate")
    caso("una posizione a ogni fine turno tranne l'ultimo (la partita finisce durante il turno)",
         "errore" not in r1 and len(r1["posizioni"]) == r1["turni"] - 1 and [n for n, _ in r1["posizioni"]] == list(range(1, r1["turni"])),
         f"{len(r1.get('posizioni', []))} posizioni, {r1.get('turni')} turni")
    caso("la partita fra Cercatori si rifa' uguale dal nastro (le scelte dei Cercatori sono tutte sul nastro)", rif is True, str(rif)[:120])
    caso("prova negativa: col motore rotto apposta nelle partite di prova (niente azioni di stato) la partita fra Cercatori si "
         "ferma col fischio", "FISCHIO" in rotta.get("errore", ""), rotta.get("errore", "nessun errore")[:120])
    # 8.bis il giro (passo 8.6, punto 4): la versione della valutazione arriva davvero alle partite di prova
    cart = tempfile.mkdtemp()
    stessi, ribaltati = os.path.join(cart, "uguale.json"), os.path.join(cart, "ribaltata.json")
    mod.salva(stessi); Modello(-mod.w, mod.scala).salva(ribaltati)
    pool = mp.get_context("spawn").Pool(2)
    try: con_v0, con_copia, con_rotta, con_m0, con_mgrande, semplici = pool.map(_prova_c, [
            (40003, "senza_note"), (40003, ("versioni", stessi)), (40003, ("versioni", ribaltati)),
            (40003, ("versioni", "v0@0")), (40003, ("versioni", "v0@99")), (40003, "semplici")], chunksize=1)
    finally: pool.terminate()
    caso("margine 0: la partita di sempre; margine enorme: il Cercatore gioca sempre la mossa del Semplice (la partita fra Semplice)",
         con_m0 == con_v0 and con_mgrande == semplici, f"{str(con_m0)[:10]}/{str(con_v0)[:10]}, {str(con_mgrande)[:10]}/{str(semplici)[:10]}")
    caso("prova negativa: col margine enorme la partita non e' quella del Cercatore senza margine", con_mgrande != con_v0, "")
    caso("giro: due Cercatori con una versione che ha i pesi di V0 (un altro file) giocano la partita di V0", con_copia == con_v0,
         f"{str(con_copia)[:10]} e {str(con_v0)[:10]}")
    caso("prova negativa: con una versione dai pesi ribaltati la partita cambia (la versione arriva alle partite di prova)",
         con_rotta != con_v0, f"{str(con_rotta)[:10]}")
    tmp = os.path.join(tempfile.mkdtemp(), "c.jsonl")
    try: dati_cercatori(40003, 40003, 2, 1, processi=1, f=tmp, kw_prove={"P": G.SenzaStato}); fermo = False
    except S.ArbitroFischia: fermo = True
    caso("prova negativa: la raccolta si ferma al fischio e non scrive la partita che ha fischiato",
         fermo and not leggi_cercatori(tmp), f"fermata {fermo}, righe {len(leggi_cercatori(tmp))}")
    ok = sum(1 for _, k, _ in casi if k)
    for nome, k, det in casi: print(("OK   " if k else "ROSSO"), nome, ("  -- " + det) if det else "")
    print(f"\n{ok}/{len(casi)} in {time.time() - t0:.0f} s")
    return ok == len(casi)


def _prova_c(arg):
    """Per le prove: una partita fra Cercatori leggeri (2 prove, troncate a 1 turno); con «replay» la rifa' dal nastro e
    dice se e' la stessa evento per evento."""
    s, x = arg
    if x == "senza_note": return impronta_eventi(partita_cercatori(s, 2, 1, annota=False)[0])
    if isinstance(x, tuple) and x[0] == "versioni": return impronta_eventi(partita_cercatori(s, 2, 1, annota=False, valute=(x[1], x[1]))[0])
    if x == "semplici": return impronta_eventi(partita_cercatori(s, 2, 1, annota=False, cerca=())[0])
    if x == "note_storte":                          # il motore rotto apposta: dopo la nota, la mossa del Semplice
        global _ANNOTA
        base = cercatore_che_annota()
        class Storto(base):
            def _scegli(self, nome, cand):
                super()._scegli(nome, cand)
                return cand[0][0]
        _ANNOTA = Storto
        try: return impronta_eventi(partita_cercatori(s, 2, 1)[0])
        finally: _ANNOTA = base
    if x != "replay": return _partita_c((s, 2, 1, x))
    import guarda_avanti as G
    p, nastro, _ = partita_cercatori(s, 2, 1)
    M = S.mazzi_veri()
    a, b = coppia(s, len(M))
    q, st = G.rifai(M[a], M[b], s, nastro, P=Segna)
    def ch(z): return [(e.tipo, e.vecchio, e.nuovo, e.da, e.a, e.causa, e.giocatore, e.quanto) for e in z.t.eventi]
    return ch(p) == ch(q) and st["cur"] == len(nastro) or f"diversa: {len(ch(p))} e {len(ch(q))} eventi, voci {st['cur']}/{len(nastro)}"


if __name__ == "__main__":
    a = sys.argv[1:]
    proc = int(a[a.index("--processi") + 1]) if "--processi" in a else None
    if a[:1] == ["--dati"]: dati(int(a[1]), int(a[2]), proc)
    elif a[:1] == ["--allena"]: allena_e_misura()
    elif a[:1] == ["--prova"]: sys.exit(0 if prova() else 1)
    elif a[:1] == ["--curva"]: curva()
    elif a[:1] == ["--cercatori"]:
        dati_cercatori(int(a[1]), int(a[2]), prove=int(a[a.index("--prove") + 1]) if "--prove" in a else PROVE_C,
                       turni=int(a[a.index("--turni") + 1]) if "--turni" in a else TURNI_C, processi=proc)
    elif a[:1] == ["--riassunto-cercatori"]: riassunto_cercatori()
    elif a[:1] == ["--giocate"]: giocate()
    elif a[:1] == ["--allena-versione"]: allena_versione(a[1] if len(a) > 1 and not a[1].startswith("--") else "v1")
    elif a[:1] == ["--giro"]:
        giro(int(a[1]), int(a[2]), a[a.index("--a") + 1] if "--a" in a else "v1", a[a.index("--b") + 1] if "--b" in a else "v0", processi=proc)
    elif a[:1] == ["--riassunto-giro"]: riassunto_giro(*(a[1:3] if len(a) >= 3 else ("v1", "v0")))
    else: print(__doc__)
