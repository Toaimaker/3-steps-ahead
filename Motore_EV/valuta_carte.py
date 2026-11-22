"""Il motore dell'EV di nuova generazione, pezzo 1: la probabilita' di vincere con le carte come vettori (sessione Magic 22, 19 nov 2026).

Autore, 19 nov 2026 (il risultato migliore sul mercato): «una rete che rappresenta ogni carta come un vettore, imparato dal testo e dalle
partite; ogni carta in campo e in mano entra col suo vettore, planeswalker e permanenti non creatura compresi; una carta di un set nuovo ha un valore
dal suo testo». Si tiene solo se batte prob_vittoria sulle stesse righe di prova.

Il modello (numpy e scipy, nessuna dipendenza nuova)
  La posizione di ogni carta: e(c) = A·phi(c) + delta(c). phi e' il vettore del testo (testi_carte.py: parole hashate, costo, forza, costituzione,
  colori, tipi, rarita'), A una proiezione imparata (DIM x K), delta una correzione della carta, imparata dalle partite e tirata a zero (L2): una carta
  che la rete non ha visto giocare vale solo per il suo testo. Ogni zona del tavolo e' la somma delle posizioni delle sue carte: le tue creature, le
  sue, i tuoi permanenti non creatura non terra, i suoi, la tua mano (le terre comprese, come nel replay). Sopra, una rete a uno strato nascosto (H
  unita' relu) che legge le zone e le variabili del tavolo che il modello di oggi vede dal vivo (prob_vittoria.NOMI senza bravura, qualita',
  mulligan suoi e GIH: dal vivo non si sanno).
  Tarata sulla meta' di taratura di prob_vittoria.divisione(20000) dei sei set del Premier (HOB, MSH, SOS, TMT, TLA, ECL), arresto sul 15% delle sue
  partite, provata sulla meta' di prova: le stesse righe del modello di oggi.

Le misure (--misura): log-loss, Brier, AUC, calibrazione per fascia e per giro, contro
  - prob_vittoria come lo usa l'app (DIFETTO dal vivo: bravura 0,5, niente GIH);
  - prob_vittoria con tutto quello che il dato sa (bravura, qualita', GIH): un metro piu' forte di quello dal vivo;
  e a parte su FRA (le nostre partite limited) e sul Constructed (le partite dei log, Motore_EV/misura_p.py). Il set nuovo: un set lasciato fuori
  dalla taratura (--senza SET) misura quanto vale il solo testo.

Limiti dichiarati: la mano avversaria e i cimiteri non sono nei replay (non entrano); il Constructed e' un'estrapolazione dal limited come prima;
il valore di una carta e' quello medio fra le partite in cui e' sul tavolo (grado B).

Uso
  py -I -X utf8 Motore_EV/valuta_carte.py --dati            prepara Dati/17lands/stile/ev_carte_dati.npz (una volta, ~10 min)
  py -I -X utf8 Motore_EV/valuta_carte.py --tara [--senza SET]   tara e scrive Motore_EV/modello_carte.npz
  py -I -X utf8 Motore_EV/valuta_carte.py --misura          prova e log: Note/Motore_EV_Carte.md
  py -I -X utf8 Motore_EV/valuta_carte.py --prova           prove con le negative
"""
import os, sys, json, math, time, argparse
from pathlib import Path
QUI = Path(__file__).resolve().parent
ROOT = QUI.parent
sys.path.insert(0, str(ROOT / "Companion")); import percorsi  # noqa: E402,F401
sys.path.insert(0, str(ROOT / "Companion" / "Suggeritore"))
sys.path.insert(0, str(QUI))
import numpy as np  # noqa: E402

STILE = ROOT / "Dati" / "17lands" / "stile"
DATI = STILE / "ev_carte_dati.npz"
MODELLO = QUI / "modello_carte.npz"
MISURE = QUI / "modello_carte.misure.json"
NOTA = ROOT / "Note" / "Motore_EV_Carte.md"
ZONE = ["cre_u", "cre_o", "non_u", "non_o", "mano"]
K = 16          # la dimensione della posizione di una carta
H = 128         # le unita' nascoste (19 nov: 64 -> 128 e L2 delle carte 3e-4 -> 1e-3, prova 0,5687 -> 0,5670)
FUORI = ("bravura", "qualita", "opp_mull")     # dal vivo non si sanno; i GIH nemmeno (le carte entrano coi vettori)


def colonne():
    import prob_vittoria as PV
    return [i for i, n in enumerate(PV.NOMI) if n not in FUORI and not n.startswith("GIH")]


# ======================================================================== i dati
def prepara():
    import prob_vittoria as PV
    import dati_replay as DR
    import testi_carte as TC
    t0 = time.time()
    D = PV.carica(DR.N_PARTITE, carte=True)
    print(f"carica: {time.time() - t0:.0f} s", flush=True)
    parti = {}
    vocab = {}
    for meta, d in D.items():
        X = d["X"]; gid = d["gid"]; sets = d["set"]
        zrow = {z: ([], []) for z in ZONE}        # per riga: liste di indici di carta (CSR)
        idx_riga = np.full(len(X), -1, np.int64)
        per_set = {}
        for si, s in enumerate(DR.SET):
            m = np.flatnonzero(sets == s)
            if not len(m):
                continue
            Kz, Z = DR.carica_zone(s)
            chiave = Kz[:, 0] * 100 + Kz[:, 1] * 50 + Kz[:, 2]
            ordine = np.argsort(chiave); ch_ord = chiave[ordine]
            g = gid[m] - DR.SET.index(s) * 10_000_000
            q = g * 100 + X[m, 0].astype(np.int64) * 50 + X[m, 1].astype(np.int64)
            pos = np.searchsorted(ch_ord, q)
            pos = np.clip(pos, 0, len(ch_ord) - 1)
            trov = ch_ord[pos] == q
            righe_z = np.where(trov, ordine[pos], -1)
            per_set[s] = (m, righe_z, Z)
            print(f"  {meta} {s}: {trov.mean():.4f} righe con le zone", flush=True)
        dove = np.full(len(X), -1, np.int64); dset = np.full(len(X), -1, np.int64)
        for si, s in enumerate(DR.SET):
            if s in per_set:
                m, rz, _Z = per_set[s]; dove[m] = rz; dset[m] = si
        ptr, ids = {}, {}
        for z in ZONE:
            lens = np.zeros(len(X), np.int64); pezzi_ord = []
            starts = np.zeros(len(X), np.int64)
            for si, s in enumerate(DR.SET):
                if s not in per_set:
                    continue
                zp, zi = per_set[s][2][z]
                msk = (dset == si) & (dove >= 0)
                r = dove[msk]
                lens[msk] = zp[r + 1] - zp[r]
                starts[msk] = zp[r]
            p = np.zeros(len(X) + 1, np.int64); p[1:] = np.cumsum(lens)
            tot = int(p[-1])
            out = np.zeros(tot, np.int64)
            riga = np.repeat(np.arange(len(X)), lens)
            off = np.arange(tot) - p[riga] + starts[riga]
            for si, s in enumerate(DR.SET):
                if s not in per_set:
                    continue
                zi = per_set[s][2][z][1]
                msk = dset[riga] == si
                out[msk] = zi[off[msk]]
            ptr[z] = p; ids[z] = out
        # il vocabolario: gli id di Arena -> indici
        for z in ZONE:
            for g in np.unique(ids[z]).tolist():
                if g not in vocab:
                    vocab[g] = len(vocab)
        lut_k = np.array(sorted(vocab)); lut_v = np.array([vocab[k] for k in lut_k])
        for z in ZONE:
            ids[z] = lut_v[np.searchsorted(lut_k, ids[z])].astype(np.int32)
        parti[meta] = dict(X=X.astype(np.float32), y=d["y"].astype(np.float32), gid=gid, set=np.array([DR.SET.index(s) for s in sets], np.int8),
                           **{f"{z}_ptr": ptr[z] for z in ZONE}, **{f"{z}_id": ids[z] for z in ZONE})
        print(f"  {meta}: {len(X)} righe, carte nel vocabolario {len(vocab)} ({time.time() - t0:.0f} s)", flush=True)
    grp = np.array(sorted(vocab, key=vocab.get), np.int64)
    np.savez(DATI, grp=grp, **{f"{m}_{k}": v for m, d in parti.items() for k, v in d.items()})
    print(f"scritto {DATI} ({time.time() - t0:.0f} s)")


def leggi_dati():
    d = np.load(DATI)
    out = {"grp": d["grp"]}
    for m in ("tara", "prova"):
        out[m] = {k[len(m) + 1:]: d[k] for k in d.files if k.startswith(m + "_")}
    return out


def incidenza(part, n_carte):
    """{zona: csr (righe x carte)} delle zone di una parte."""
    from scipy import sparse
    out = {}
    n = len(part["y"])
    for z in ZONE:
        p = part[f"{z}_ptr"]; ids = part[f"{z}_id"]
        out[z] = sparse.csr_matrix((np.ones(len(ids), np.float32), ids, p), shape=(n, n_carte))
    return out


# ======================================================================== la rete
class Rete:
    def __init__(self, n_in, dim_testo, n_carte, seme=0):
        r = np.random.default_rng(seme)
        self.A = (r.standard_normal((dim_testo, K)) * 0.05).astype(np.float32)
        self.dl = np.zeros((n_carte, K), np.float32)
        self.zone = list(ZONE)      # le zone con cui e' stata allenata (22 nov 2026: le reti con lib_u e vis_o)
        n_tot = n_in + K * len(self.zone)
        self.W1 = (r.standard_normal((n_tot, H)) * math.sqrt(2 / n_tot)).astype(np.float32)
        self.b1 = np.zeros(H, np.float32)
        self.w2 = (r.standard_normal(H) * math.sqrt(1 / H)).astype(np.float32)
        self.b2 = np.float32(0.0)
        self.mu = None; self.sd = None

    def parametri(self):
        return ["A", "dl", "W1", "b1", "w2", "b2"]

    def posizioni(self, Phi):
        return np.asarray(Phi @ self.A) + self.dl

    def avanti(self, Xs, Mz, E):
        S = [np.asarray(Mz[z] @ E) for z in self.zone]
        inp = np.concatenate([Xs] + S, axis=1).astype(np.float32)
        a = inp @ self.W1 + self.b1
        h = np.maximum(a, 0)
        f = h @ self.w2 + self.b2
        return f, (inp, a, h)

    def logit(self, X, Mz, Phi):
        Xs = (X - self.mu) / self.sd
        E = self.posizioni(Phi)
        out = np.empty(len(X), np.float32)
        for i in range(0, len(X), 50000):
            sl = slice(i, i + 50000)
            out[sl] = self.avanti(Xs[sl], {z: Mz[z][sl] for z in self.zone}, E)[0]
        return out

    def salva(self, path, grp, cols, extra):
        np.savez(path, A=self.A, dl=self.dl, W1=self.W1, b1=self.b1, w2=self.w2, b2=np.array(self.b2), mu=self.mu, sd=self.sd,
                 grp=grp, cols=np.array(cols), meta=np.array(json.dumps(dict(extra, zone=self.zone))))

    @classmethod
    def apri(cls, path):
        d = np.load(path, allow_pickle=False)
        r = cls.__new__(cls)
        for k in ("A", "dl", "W1", "b1", "w2", "mu", "sd"):
            setattr(r, k, d[k])
        r.b2 = np.float32(d["b2"])
        r.grp = d["grp"]; r.cols = d["cols"].tolist(); r.meta = json.loads(str(d["meta"]))
        r.indice = {int(g): i for i, g in enumerate(r.grp)}
        r.zone = list(r.meta.get("zone") or ZONE[:5])
        return r


def allena(T, Mz_T, Phi, n_carte, cols, val_frac=0.15, epoche=8, batch=4096, lr=2e-3, l2_dl=1e-3, l2_w=1e-6, seme=0, log=print, falsifica=None):
    """Adam sui minibatch; arresto sulla log-loss della convalida (15% delle partite di taratura). falsifica: funzione che cambia y (le prove)."""
    rng = np.random.default_rng(seme)
    X = T["X"][:, cols]; y = T["y"].copy()
    if falsifica is not None:
        y = falsifica(y, T)
    gu = np.unique(T["gid"]); cv = set(rng.choice(gu, size=int(len(gu) * val_frac), replace=False).tolist())
    mcv = np.isin(T["gid"], list(cv))
    itr = np.flatnonzero(~mcv); icv = np.flatnonzero(mcv)
    net = Rete(X.shape[1], Phi.shape[1], n_carte, seme)
    net.mu = X[itr].mean(0); net.sd = X[itr].std(0) + 1e-6
    Xs = ((X - net.mu) / net.sd).astype(np.float32)
    PhiT = Phi.T.tocsr()
    m = {k: np.zeros_like(getattr(net, k), dtype=np.float32) for k in net.parametri()}
    v = {k: np.zeros_like(getattr(net, k), dtype=np.float32) for k in net.parametri()}
    t = 0
    migliore = (9.0, None)
    pazienza = 0

    def ll_cv():
        E = net.posizioni(Phi)
        f = np.concatenate([net.avanti(Xs[icv[i:i + 50000]], {z: Mz_T[z][icv[i:i + 50000]] for z in ZONE}, E)[0] for i in range(0, len(icv), 50000)])
        p = 1 / (1 + np.exp(-f)); p = np.clip(p, 1e-6, 1 - 1e-6)
        return float(-np.mean(y[icv] * np.log(p) + (1 - y[icv]) * np.log(1 - p)))
    for ep in range(epoche):
        t0 = time.time()
        perm = rng.permutation(itr)
        for i in range(0, len(perm), batch):
            b = perm[i:i + batch]
            E = net.posizioni(Phi)
            Mb = {z: Mz_T[z][b] for z in ZONE}
            f, (inp, a, h) = net.avanti(Xs[b], Mb, E)
            p = 1 / (1 + np.exp(-f))
            g = ((p - y[b]) / len(b)).astype(np.float32)
            gw2 = h.T @ g + l2_w * net.w2; gb2 = g.sum()
            dh = np.outer(g, net.w2) * (a > 0)
            gW1 = inp.T @ dh + l2_w * net.W1; gb1 = dh.sum(0)
            dinp = dh @ net.W1.T
            n_in = Xs.shape[1]
            dE = np.zeros_like(E)
            for j, z in enumerate(ZONE):
                dS = dinp[:, n_in + j * K: n_in + (j + 1) * K]
                dE += np.asarray(Mb[z].T @ dS)
            gdl = dE + l2_dl * net.dl
            gA = np.asarray(PhiT @ dE) + l2_w * net.A
            t += 1
            for k, gk in (("A", gA), ("dl", gdl), ("W1", gW1), ("b1", gb1), ("w2", gw2), ("b2", gb2)):
                m[k] = 0.9 * m[k] + 0.1 * gk; v[k] = 0.999 * v[k] + 0.001 * gk * gk
                mh = m[k] / (1 - 0.9 ** t); vh = v[k] / (1 - 0.999 ** t)
                setattr(net, k, (getattr(net, k) - lr * mh / (np.sqrt(vh) + 1e-8)).astype(np.float32))
        l = ll_cv()
        log(f"  epoca {ep + 1}: convalida log-loss {l:.5f} ({time.time() - t0:.0f} s)")
        if l < migliore[0] - 1e-5:
            migliore = (l, {k: getattr(net, k).copy() if hasattr(getattr(net, k), "copy") else getattr(net, k) for k in net.parametri()}); pazienza = 0
        else:
            pazienza += 1
            lr *= 0.5
            if pazienza >= 2:
                break
    for k, val in migliore[1].items():
        setattr(net, k, val)
    return net, migliore[0]


# ======================================================================== le misure
def misure(p, y):
    sys.path.insert(0, str(QUI)); import misura_p as MP
    return MP.misure(p, y)


def calibrazione(p, y):
    import misura_p as MP
    return MP.calibrazione(p, y)


def logit_pv(X, dal_vivo):
    """Il logit di prob_vittoria sulle righe X (36 colonne); dal_vivo: le colonne che l'app non sa rimesse al DIFETTO."""
    import prob_vittoria as PV
    X = X.astype(np.float64).copy()
    if dal_vivo:
        for i, n in enumerate(PV.NOMI):
            if n in FUORI or n.startswith("GIH"):
                X[:, i] = PV.DIFETTO.get(n, 0.0)
    M = json.load(open(PV.OUT, encoding="utf-8"))
    return PV.valuta_json_np(M["p"], X)


def tara(senza=None, epoche=8, seme=0, falsifica=None, scrivi=True, log=print):
    import testi_carte as TC
    import dati_replay as DR
    t0 = time.time()
    D = leggi_dati()
    grp = D["grp"]
    Phi = TC.matrice(grp.tolist())
    cols = colonne()
    T, V = D["tara"], D["prova"]
    if senza:
        si = DR.SET.index(senza)
        T = {k: v for k, v in T.items()}
        keep = T["set"] != si
        T = sottoinsieme(T, keep)
    Mz_T = incidenza(T, len(grp))
    log(f"taratura: {len(T['y'])} righe, {len(grp)} carte ({time.time() - t0:.0f} s)")
    net, llcv = allena(T, Mz_T, Phi, len(grp), cols, epoche=epoche, seme=seme, falsifica=falsifica, log=log)
    meta = dict(creato=time.strftime("%Y-%m-%d %H:%M"), righe_tara=int(len(T["y"])), carte=int(len(grp)), K=K, H=H, convalida=round(llcv, 5),
                senza=senza, secondi=round(time.time() - t0), fonte="replay pubblici 17Lands, Premier " + ", ".join(DR.SET) + " (CC BY 4.0)")
    if scrivi:
        net.salva(MODELLO if not senza else QUI / f"modello_carte_senza_{senza}.npz", grp, cols, meta)
        log(f"scritto ({time.time() - t0:.0f} s)")
    return net, Phi, cols


def sottoinsieme(P, mask):
    """Le righe mask di una parte, con le CSR delle zone ricostruite."""
    out = {}
    idx = np.flatnonzero(mask)
    for k, v in P.items():
        if k.endswith("_ptr") or k.endswith("_id"):
            continue
        out[k] = v[idx]
    for z in ZONE:
        p = P[f"{z}_ptr"]; ids = P[f"{z}_id"]
        lens = (p[1:] - p[:-1])[idx]
        np_ = np.zeros(len(idx) + 1, np.int64); np_[1:] = np.cumsum(lens)
        sel = np.concatenate([ids[p[i]:p[i + 1]] for i in idx]) if len(idx) else np.zeros(0, np.int32)
        out[f"{z}_ptr"] = np_; out[f"{z}_id"] = sel.astype(np.int32)
    return out


def misura_set_nuovo(s="ECL", log=print):
    """Quanto vale il solo testo: tarato senza il set s, provato sulle righe di prova di s, contro la P dal vivo e il modello che ha visto s."""
    import dati_replay as DR
    import testi_carte as TC
    import misura_p as MP
    net_senza, Phi, cols = tara(senza=s, scrivi=False, log=lambda *a: None)
    D = leggi_dati(); V = D["prova"]; si = DR.SET.index(s)
    Vs = sottoinsieme(V, V["set"] == si)
    Mz = incidenza(Vs, len(D["grp"]))
    sig = lambda f: 1 / (1 + np.exp(-f))
    con = Rete.apri(MODELLO)
    r = dict(set=s, righe=int(len(Vs["y"])),
             nuovo=MP.misure(sig(net_senza.logit(Vs["X"][:, cols], Mz, Phi)), Vs["y"])["log_loss"],
             con=MP.misure(sig(con.logit(Vs["X"][:, con.cols], Mz, Phi)), Vs["y"])["log_loss"],
             P_dal_vivo=MP.misure(sig(logit_pv(Vs["X"], True)), Vs["y"])["log_loss"])
    log(f"set nuovo {s}: {r}")
    return r


# ======================================================================== dal vivo: una foto dei log
_NET = {}


def rete():
    if "n" not in _NET:
        _NET["n"] = Rete.apri(MODELLO) if MODELLO.exists() else None
        if _NET["n"] is not None:
            import testi_carte as TC
            _NET["phi"] = TC.matrice(_NET["n"].grp.tolist())
            _NET["E"] = _NET["n"].posizioni(_NET["phi"])
            _NET["nuove"] = {}
    return _NET["n"]


def posizione(g):
    """La posizione di una carta: dal vocabolario se vista in taratura, se no dal solo testo."""
    net = rete()
    i = net.indice.get(int(g))
    if i is not None:
        return _NET["E"][i]
    e = _NET["nuove"].get(g)
    if e is None:
        import testi_carte as TC
        e = _NET["nuove"][g] = np.asarray(TC.matrice([int(g)]) @ net.A)[0]
    return e


INSIEME = QUI / "insieme"        # le reti in uso dal 22 nov 2026 (Motore_EV/insieme.py): cinque «base» e cinque «zone»
_INS = {}


def insieme(tipo):
    """Le cinque reti di un insieme («base» o «zone»), lette una volta; [] se mancano. SPENTE di default (22 nov 2026): sui log di Autore non
    battono la rete di prima (Motore_EV/insieme.json, «log»); EV_INSIEME=1 le accende per le misure."""
    if os.environ.get("EV_INSIEME") != "1":
        return []
    if tipo not in _INS:
        fs = sorted(INSIEME.glob(f"{tipo}_*.npz")) if INSIEME.exists() else []
        reti = []
        try:
            for f in fs:
                reti.append(Rete.apri(f))
        except (OSError, ValueError, KeyError):
            reti = []
        if reti:
            import testi_carte as TC
            phi = TC.matrice(reti[0].grp.tolist())
            for r in reti:
                r.E = r.posizioni(phi)
                r.nuove = {}
        _INS[tipo] = reti
    return _INS[tipo]


def _pos_rete(r, g):
    i = r.indice.get(int(g))
    if i is not None:
        return r.E[i]
    e = r.nuove.get(g)
    if e is None:
        import testi_carte as TC
        if g not in _NET.setdefault("phi_nuove", {}):
            _NET["phi_nuove"][g] = TC.matrice([int(g)])
        e = r.nuove[g] = np.asarray(_NET["phi_nuove"][g] @ r.A)[0]
    return e


def _logit_rete(r, xv, zone):
    x = np.array([xv[i] for i in r.cols], np.float32)
    S = []
    for z in r.zone:
        v = sum((_pos_rete(r, g) for g in zone.get(z) or []), np.zeros(K, np.float32))
        if z == "lib_u":
            v = v * float(zone.get("_lib_scala", 1.0))      # un mazzo da 60 portato alla misura di uno da 40, su cui le reti sono allenate
        S.append(v)
    inp = np.concatenate([(x - r.mu) / r.sd] + S).astype(np.float32)
    h = np.maximum(inp @ r.W1 + r.b1, 0)
    return float(h @ r.w2 + r.b2)


def logit_tavolo(xv, zone, quale=None):
    """xv: il vettore di prob_vittoria.vettore (36 numeri); zone: {zona: [grpId, ...]} (con lib_u e vis_o quando si sanno). -> logit, o None.
    quale: None = l'insieme che si puo' usare (le cinque reti «zone» se ci sono lib_u e vis_o, se no le cinque «base», se no la rete di prima);
    «zone», «base», «singola» per le misure."""
    if quale in (None, "zone", "base"):
        tipo = quale or ("zone" if "lib_u" in zone else "base")
        reti = insieme(tipo)
        if reti:
            return float(np.mean([_logit_rete(r, xv, zone) for r in reti]))
        if quale in ("zone", "base"):
            return None
    net = rete()
    if net is None:
        return None
    x = np.array([xv[i] for i in net.cols], np.float32)
    Xs = (x - net.mu) / net.sd
    S = [sum((posizione(g) for g in zone.get(z) or []), np.zeros(K, np.float32)) for z in ZONE]
    inp = np.concatenate([Xs] + S).astype(np.float32)
    h = np.maximum(inp @ net.W1 + net.b1, 0)
    return float(h @ net.w2 + net.b2)


CALIB = QUI / "calibrazione_constructed.json"


def _cal_x(fn, giro, tocca_me):
    g = min(giro, 10) / 10
    return np.array([1.0, fn, fn * g, g, float(tocca_me)])


def calibra(rr=None, log=print):
    """La ricalibrazione del Constructed (19 nov 2026): una logistica sul logit del modello, il giro e chi tocca, tarata sulle partite costruite dei log.
    Misurata in validazione incrociata a due meta' per partita (--misura la riporta); poi tarata su tutte e scritta in CALIB."""
    import zlib
    import misura_p as MP
    rr = rr if rr is not None else righe_log()
    R = [r for r in rr if r["tipo"] == "Constructed"]
    X = np.stack([_cal_x(r["fn"], r["giro"], r["tocca_me"]) for r in R]); y = np.array([r["y"] for r in R])
    lato = np.array([zlib.crc32(r["partita"].encode()) & 1 for r in R])
    w0 = np.array([0, 1, 0, 0, 0.0])

    def fit(m):
        w = w0.copy()
        for _ in range(50):
            q = 1 / (1 + np.exp(-X[m] @ w)); g = X[m].T @ (q - y[m]) + (w - w0)
            Hm = (X[m] * (q * (1 - q))[:, None]).T @ X[m] + np.eye(len(w)); w -= np.linalg.solve(Hm, g)
        return w
    p = np.zeros(len(y))
    for s_ in (0, 1):
        w = fit(lato != s_); p[lato == s_] = 1 / (1 + np.exp(-X[lato == s_] @ w))
    pn = np.array([r["p_new"] for r in R])
    cv = dict(partite=len({r["partita"] for r in R}), righe=len(R), senza=MP.misure(pn, y), con_cv=MP.misure(p, y),
              con_meno_senza=MP.es_cluster(MP.ll_righe(p, y), MP.ll_righe(pn, y), [r["partita"] for r in R]), calibrazione_cv=MP.calibrazione(p, y))
    w = fit(np.ones(len(y), bool))
    CALIB.write_text(json.dumps(dict(w=w.tolist(), cv=cv, creato=time.strftime("%Y-%m-%d %H:%M")), indent=1), encoding="utf8")
    _NET.pop("cal", None)
    log(f"calibrazione del Constructed: {cv['con_meno_senza']} (CV), scritta")
    return cv


def p_tavolo(xv, zone, tipo=None, giro=1, tocca_me=True):
    """La P (0-1) del modello nuovo, ricalibrata sul Constructed se tipo == 'Constructed'. None senza il modello."""
    fn = logit_tavolo(xv, zone)
    if fn is None:
        return None
    if tipo == "Constructed":
        if "cal" not in _NET:
            try:
                _NET["cal"] = np.array(json.loads(CALIB.read_text(encoding="utf8"))["w"])
            except (OSError, ValueError, KeyError):
                _NET["cal"] = None
        w = _NET["cal"]
        if w is not None:
            fn = float(_cal_x(fn, giro, tocca_me) @ w)
    return 1 / (1 + math.exp(-fn))


def zone_foto(f, seat):
    """{zona: [grpId]} dalla foto di mana_aperto vista dal posto seat: creature (forza non None), permanenti non terra non creatura, la mano."""
    import testi_carte as TC
    a, b = seat - 1, 2 - seat
    lati = f.get("c") or [[], []]
    out = {z: [] for z in ZONE}
    for lato, cre, non in ((lati[a], "cre_u", "non_u"), (lati[b], "cre_o", "non_o")):
        for c in lato or []:
            g = c[0]
            if len(c) >= 5 and c[3] is not None:
                out[cre].append(g)
            elif not TC.e_terra(g):
                out[non].append(g)
    m = (f.get("m") or [[], []])
    out["mano"] = list(m[a] or []) if len(m) > a else []
    return out


# ======================================================================== le misure complete
def misura(log=print):
    import dati_replay as DR
    import testi_carte as TC
    import misura_p as MP
    t0 = time.time()
    net = Rete.apri(MODELLO)
    D = leggi_dati(); V = D["prova"]
    Phi = TC.matrice(D["grp"].tolist())
    assert (D["grp"] == net.grp).all()
    Mz = incidenza(V, len(D["grp"]))
    f_new = net.logit(V["X"][:, net.cols], Mz, Phi)
    f_live = logit_pv(V["X"], True)
    f_full = logit_pv(V["X"], False)
    sig = lambda f: 1 / (1 + np.exp(-f))
    y = V["y"]; gid = V["gid"]
    res = {"replay_prova": {}}
    for nome, f in (("nuovo", f_new), ("P_dal_vivo", f_live), ("P_con_tutto", f_full)):
        res["replay_prova"][nome] = misure(sig(f), y)
    res["replay_prova"]["nuovo_meno_P_dal_vivo"] = MP.es_cluster(MP.ll_righe(sig(f_new), y), MP.ll_righe(sig(f_live), y), gid)
    res["replay_prova"]["nuovo_meno_P_con_tutto"] = MP.es_cluster(MP.ll_righe(sig(f_new), y), MP.ll_righe(sig(f_full), y), gid)
    res["replay_prova"]["calibrazione_nuovo"] = calibrazione(sig(f_new), y)
    res["replay_prova"]["calibrazione_P_dal_vivo"] = calibrazione(sig(f_live), y)
    giro = V["X"][:, 1]
    res["replay_prova"]["per_giro"] = {}
    for a, b in ((1, 3), (4, 6), (7, 9), (10, 12)):
        m = (giro >= a) & (giro <= b)
        res["replay_prova"]["per_giro"][f"{a}-{b}"] = {"nuovo": misure(sig(f_new[m]), y[m]), "P_dal_vivo": misure(sig(f_live[m]), y[m])}
    res["replay_prova"]["per_set"] = {s: {"nuovo": misure(sig(f_new[V["set"] == i]), y[V["set"] == i])["log_loss"],
                                          "P_dal_vivo": misure(sig(f_live[V["set"] == i]), y[V["set"] == i])["log_loss"]} for i, s in enumerate(DR.SET)}
    log(f"replay: {json.dumps({k: v for k, v in res['replay_prova'].items() if k in ('nuovo', 'P_dal_vivo', 'P_con_tutto', 'nuovo_meno_P_dal_vivo')})}")
    # i log di Autore
    rr = righe_log(net)
    res["log"] = misura_log(net, rr)
    res["calibrazione_constructed"] = calibra(rr, log)
    MISURE.write_text(json.dumps(res, indent=1, ensure_ascii=False), encoding="utf8")
    log(f"misure in {time.time() - t0:.0f} s")
    return res


def righe_log(net=None):
    """Le previsioni sui log: per ogni foto dei turni (come misura_p) il logit di prob_vittoria dal vivo e del modello nuovo."""
    sys.path.insert(0, str(ROOT / "Companion" / "App" / "Schede" / "Performance"))
    import dati_analizzatore as DA
    import ev_partita as EV
    import prob_vittoria as PV
    out = []
    for x in DA.righe():
        c = EV.partita(x)
        if not c:
            continue
        d = DA._MANA.get(x["partita"]) or {}
        seat = x["seat"]
        y = 1.0 if x["vinta"] else 0.0
        voci = [(1, bool(x["inizia"]), d.get("mano0"))] + [((t + 2) // 2, att != seat, f) for t, att, f in d.get("foto") or []]
        for giro, tocca_me, f in voci:
            if not f:
                continue
            st = _stato_foto(DA, f, seat, tocca_me, giro, x)
            if st is None:
                continue
            p_old = DA.p_foto(f, seat, tocca_me, giro, x.get("inizia"), x.get("mulligan"), vecchia=True)
            if p_old is None:
                continue
            xv = PV.vettore(st)
            fn = logit_tavolo(xv, zone_foto(f, seat))
            if fn is None:
                continue
            p_new = 1 / (1 + math.exp(-fn))
            if DA.letale(f, seat, tocca_me):       # lo stesso override del letale che l'app mette sopra
                p_new = 0.99 if tocca_me else 0.01
            out.append(dict(partita=x["partita"], tipo=x["tipo"], evento=x.get("evento") or "", giro=giro, tocca_me=int(tocca_me),
                            p_old=p_old / 100, p_new=p_new, y=y, fn=fn))
    return out


def _stato_foto(DA, f, seat, tocca_me, giro, x):
    """Lo stesso stato che DA.p_foto passa a prob_vittoria (senza il letale)."""
    a, b = seat - 1, 2 - seat
    lati = f.get("c") or [[], []]

    def cre(lato):
        return [dict(p=c_[3] or 0, t=c_[4] or 0, kw=DA._parole(c_[0]), girato=bool(c_[1])) for c_ in lato or [] if len(c_) >= 5 and c_[3] is not None]

    def terre(lato):
        return sum(1 for c_ in lato or [] if not c_[2] and DA.e_terra(DA.nome_grp(c_[0]) or ""))
    miei, suoi = cre(lati[a]), cre(lati[b])
    v = f.get("v") or [20, 20]; n = f.get("n") or [0, 0]
    return dict(tocca_me=1 if tocca_me else 0, N=giro, on_play=1 if x.get("inizia") else 0, LU=v[a] if v[a] is not None else 20,
                LO=v[b] if v[b] is not None else 20, miei=miei, suoi=suoi, TERU=terre(lati[a]), TERO=terre(lati[b]), MANU=n[a] or 0,
                MANO=n[b] or 0, mull=x.get("mulligan") or 0, tappati_suoi=sum(c["girato"] for c in suoi) if tocca_me else 0,
                tappati_miei=0 if tocca_me else sum(c["girato"] for c in miei))


def misura_log(net=None, rr=None):
    import misura_p as MP
    rr = rr if rr is not None else righe_log(net)
    res = {}
    for nome, sel in (("Constructed", lambda r: r["tipo"] == "Constructed"), ("Limited FRA", lambda r: r["tipo"] == "Limited" and "FRA" in r["evento"])):
        R = [r for r in rr if sel(r)]
        if not R:
            continue
        y = np.array([r["y"] for r in R]); po = np.array([r["p_old"] for r in R]); pn = np.array([r["p_new"] for r in R]); gid = [r["partita"] for r in R]
        e = dict(partite=len(set(gid)), righe=len(R), P_dal_vivo=MP.misure(po, y), nuovo=MP.misure(pn, y),
                 nuovo_meno_P=MP.es_cluster(MP.ll_righe(pn, y), MP.ll_righe(po, y), gid),
                 calibrazione_nuovo=MP.calibrazione(pn, y), calibrazione_P=MP.calibrazione(po, y))
        giri = np.array([r["giro"] for r in R])
        e["per_fase"] = {}
        for a, b in ((1, 3), (4, 6), (7, 99)):
            m = (giri >= a) & (giri <= b)
            if m.sum():
                e["per_fase"][f"{a}-{b if b < 99 else '+'}"] = dict(righe=int(m.sum()), P=MP.misure(po[m], y[m]), nuovo=MP.misure(pn[m], y[m]),
                                                                     p_media_P=round(float(po[m].mean()) * 100, 1),
                                                                     p_media_nuovo=round(float(pn[m].mean()) * 100, 1),
                                                                     vinte=round(float(y[m].mean()) * 100, 1))
        res[nome] = e
    return res


def scrivi_nota(res):
    r = res["replay_prova"]
    L = ["# Il pezzo 1: la probabilita' di vincere con le carte come vettori", "",
         "Generato da `py -I -X utf8 Motore_EV/valuta_carte.py --misura` (sessione Magic 22). Il modello: `Motore_EV/valuta_carte.py`, "
         "il testo delle carte `Motore_EV/testi_carte.py`, i tavoli dei replay `Motore_EV/dati_replay.py`. Fonte: replay pubblici di 17Lands "
         "(CC BY 4.0), Premier di sei set, le stesse righe di prova di `prob_vittoria`.", "",
         "## Sui replay (meta' di prova, le stesse righe)", "",
         "| modello | log-loss | Brier | AUC |", "|---|---|---|---|"]
    for k, nome in (("nuovo", "carte come vettori"), ("P_dal_vivo", "P di oggi come la usa l'app"), ("P_con_tutto", "P di oggi con bravura e GIH (non disponibili dal vivo)")):
        m = r[k]; L.append(f"| {nome} | {m['log_loss']} | {m['brier']} | {m['auc']} |")
    d, e = r["nuovo_meno_P_dal_vivo"]; d2, e2 = r["nuovo_meno_P_con_tutto"]
    L += ["", f"Nuovo meno P dal vivo: {d:+.4f} ± {e:.4f}; nuovo meno P con tutto: {d2:+.4f} ± {e2:.4f} (negativo = il nuovo e' meglio).", "",
          "Per giro (log-loss): ", "", "| giri | nuovo | P dal vivo |", "|---|---|---|"]
    L += [f"| {g} | {v['nuovo']['log_loss']} | {v['P_dal_vivo']['log_loss']} |" for g, v in r["per_giro"].items()]
    L += ["", "Per set (log-loss): " + ", ".join(f"{s} {v['nuovo']} contro {v['P_dal_vivo']}" for s, v in r["per_set"].items()), "",
          "Calibrazione del nuovo (fascia, righe, P, vinte): " + "; ".join(f"{a} {b} {c}/{d_}" for a, b, c, d_ in r["calibrazione_nuovo"]), ""]
    for nome, e in res.get("log", {}).items():
        dd, ee = e["nuovo_meno_P"]
        L += [f"## {nome} (log di Autore)", "", f"{e['partite']} partite, {e['righe']} previsioni.", "",
              "| modello | log-loss | Brier | AUC |", "|---|---|---|---|",
              f"| carte come vettori | {e['nuovo']['log_loss']} | {e['nuovo']['brier']} | {e['nuovo']['auc']} |",
              f"| P di oggi | {e['P_dal_vivo']['log_loss']} | {e['P_dal_vivo']['brier']} | {e['P_dal_vivo']['auc']} |", "",
              f"Nuovo meno P: {dd:+.4f} ± {ee:.4f}.", "", "| giri | righe | P media oggi | P media nuovo | vinte | log-loss oggi | log-loss nuovo |", "|---|---|---|---|---|---|---|"]
        for g, v in e["per_fase"].items():
            L.append(f"| {g} | {v['righe']} | {v['p_media_P']} | {v['p_media_nuovo']} | {v['vinte']} | {v['P']['log_loss']} | {v['nuovo']['log_loss']} |")
        L += ["", "Calibrazione del nuovo: " + "; ".join(f"{a} {b} {c}/{d_}" for a, b, c, d_ in e["calibrazione_nuovo"]), ""]
    if res.get("calibrazione_constructed"):
        c = res["calibrazione_constructed"]; d, e = c["con_meno_senza"]
        L += ["## La ricalibrazione del Constructed (dai log, in validazione incrociata)", "",
              f"{c['partite']} partite, {c['righe']} previsioni: log-loss {c['senza']['log_loss']} -> {c['con_cv']['log_loss']} ({d:+.4f} ± {e:.4f}). "
              "Una logistica sul logit, il giro e chi tocca; dal vivo vale solo per le partite costruite.", "",
              "Calibrazione: " + "; ".join(f"{a} {b} {c_}/{d_}" for a, b, c_, d_ in c["calibrazione_cv"]), ""]
    if res.get("set_nuovo"):
        s = res["set_nuovo"]
        L += ["## Un set mai visto (il solo testo)", "", f"Tarato senza {s['set']}, provato sulle sue righe di prova: nuovo {s['nuovo']}, "
              f"P dal vivo {s['P_dal_vivo']}, il modello con {s['set']} {s['con']}.", ""]
    NOTA.write_text("\n".join(L), encoding="utf8")


# ======================================================================== le prove
def prova():
    ok = tot = 0

    def chk(c, m):
        nonlocal ok, tot
        tot += 1; ok += bool(c); print(("OK   " if c else "ROSSO") + " " + m, flush=True)
    import testi_carte as TC
    # 1. il gradiente: differenze finite su una rete piccola
    rng = np.random.default_rng(1)
    from scipy import sparse
    n, nc = 64, 10
    T = {"X": rng.standard_normal((n, 3)).astype(np.float32), "y": (rng.random(n) < 0.5).astype(np.float32), "gid": np.arange(n)}
    Mz = {z: sparse.random(n, nc, density=0.2, format="csr", random_state=i, dtype=np.float32) for i, z in enumerate(ZONE)}
    Phi = sparse.random(nc, 20, density=0.3, format="csr", random_state=9, dtype=np.float32)
    net = Rete(3, 20, nc, 2); net.mu = np.zeros(3, np.float32); net.sd = np.ones(3, np.float32)

    def L(net):
        f = net.logit(T["X"], Mz, Phi).astype(np.float64); p = 1 / (1 + np.exp(-f))
        return float(-np.mean(T["y"] * np.log(p) + (1 - T["y"]) * np.log(1 - p)))
    # gradiente analitico come in allena (una passata)
    E = net.posizioni(Phi); f, (inp, a, h) = net.avanti(T["X"], Mz, E); p = 1 / (1 + np.exp(-f)); g = (p - T["y"]) / n
    dh = np.outer(g, net.w2) * (a > 0); dinp = dh @ net.W1.T
    dE = sum(np.asarray(Mz[z].T @ dinp[:, 3 + j * K:3 + (j + 1) * K]) for j, z in enumerate(ZONE))
    gA = np.asarray(Phi.T @ dE)
    i, j = np.unravel_index(np.argmax(np.abs(gA)), gA.shape)
    eps = 1e-2; net.A = net.A.astype(np.float64); net.A[i, j] += eps; l1 = L(net); net.A[i, j] -= 2 * eps; l2 = L(net); net.A[i, j] += eps
    num = (l1 - l2) / (2 * eps)
    chk(abs(num - gA[i, j]) < 0.05 * abs(gA[i, j]) + 1e-5, f"gradiente della proiezione del testo: analitico {gA[i, j]:.5f} numerico {num:.5f}")
    # 2. il modello vero, se c'e'
    if MODELLO.exists():
        net = Rete.apri(MODELLO)
        g = TC.per_nome("Ajani's Pridemate")
        xv = [0.0] * 36
        import prob_vittoria as PV
        st = dict(tocca_me=1, N=5, on_play=1, LU=15, LO=15, miei=[], suoi=[], TERU=5, TERO=5, MANU=3, MANO=3)
        xv = PV.vettore(st)
        f0 = logit_tavolo(xv, {})
        chk(f0 is not None, f"il modello risponde dal vivo (P {100 / (1 + math.exp(-f0)):.1f}% a tavolo vuoto)")
        st2 = dict(st, LO=3)
        chk(logit_tavolo(PV.vettore(st2), {}) > f0, "piu' vite tolte all'avversario: la P sale")
        st3 = dict(st, LU=3)
        chk(logit_tavolo(PV.vettore(st3), {}) < f0, "negativa: meno vite tue, la P scende")
        # una creatura grande in piu' tua deve valere piu' di zero, la stessa sua meno di zero
        drago = TC.per_nome("Shivan Dragon") or TC.per_nome("Serra Angel")
        mia = logit_tavolo(PV.vettore(dict(st, miei=[dict(p=4, t=4, kw=["flying"])])), {"cre_u": [drago]})
        sua = logit_tavolo(PV.vettore(dict(st, suoi=[dict(p=4, t=4, kw=["flying"])])), {"cre_o": [drago]})
        chk(mia > f0 > sua, f"un volante 4/4 tuo alza la P, suo l'abbassa ({mia:.2f} > {f0:.2f} > {sua:.2f})")
        # una carta mai vista ha un valore dal testo
        chk(posizione(-987654).shape == (K,) and float(np.abs(posizione(-987654)).sum()) < 1e-6, "negativa: una carta che non esiste (senza testo, mai vista) ha la posizione zero")
        nuova = next((int(gg) for gg in TC._db()["carte"] if int(gg) not in net.indice and TC.e_creatura(gg)), None)
        chk(nuova is not None and float(np.abs(posizione(nuova)).sum()) > 0, f"una creatura mai vista in taratura ha una posizione dal testo ({TC.nome(nuova)})")
        # i planeswalker entrano
        pw = next((int(gg) for gg in TC._db()["carte"] if "Planeswalker" in (TC.testo(gg)[1] or "") and int(gg) in net.indice), None)
        if pw:
            f_pw = logit_tavolo(xv, {"non_u": [pw]})
            chk(f_pw > f0, f"un tuo planeswalker ({TC.nome(pw)}) alza la P ({f_pw:.2f} > {f0:.2f})")
        if MISURE.exists():
            m = json.load(open(MISURE, encoding="utf8"))
            chk(m["replay_prova"]["nuovo"]["log_loss"] < m["replay_prova"]["P_dal_vivo"]["log_loss"],
                "sui replay di prova il nuovo batte la P di oggi (misura scritta)")
    # 3. la negativa dell'allenamento: con i risultati rimescolati fra le partite la rete non impara niente (log-loss vicina a ln 2)
    if DATI.exists():
        D = leggi_dati(); T = D["tara"]
        rng = np.random.default_rng(5)
        sel = np.isin(T["gid"], rng.choice(np.unique(T["gid"]), 3000, replace=False))
        Ts = sottoinsieme(T, sel)
        Phi = TC.matrice(D["grp"].tolist())

        def mescola(y, P):
            gu = np.unique(P["gid"]); vinte = {g: float(rng.random() < 0.5) for g in gu}
            return np.array([vinte[g] for g in P["gid"]], np.float32)
        net, ll = allena(Ts, incidenza(Ts, len(D["grp"])), Phi, len(D["grp"]), colonne(), epoche=2, falsifica=mescola, log=lambda *a: None)
        chk(ll > 0.68, f"negativa: risultati a caso, la convalida resta vicina a ln 2 ({ll:.4f})")
    print(f"{ok}/{tot}")
    return ok == tot


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dati", action="store_true"); ap.add_argument("--tara", action="store_true"); ap.add_argument("--misura", action="store_true")
    ap.add_argument("--prova", action="store_true"); ap.add_argument("--senza"); ap.add_argument("--set-nuovo"); ap.add_argument("--epoche", type=int, default=8)
    a = ap.parse_args()
    if a.dati:
        prepara()
    if a.tara:
        tara(senza=a.senza, epoche=a.epoche)
    if a.misura:
        res = misura()
        old = json.loads(MISURE.read_text(encoding="utf8")) if MISURE.exists() else {}
        if old.get("set_nuovo"):
            res["set_nuovo"] = old["set_nuovo"]
        scrivi_nota(res)
        print("scritto", NOTA)
    if a.set_nuovo:
        r = misura_set_nuovo(a.set_nuovo)
        old = json.loads(MISURE.read_text(encoding="utf8")) if MISURE.exists() else {}
        old["set_nuovo"] = r; MISURE.write_text(json.dumps(old, indent=1, ensure_ascii=False), encoding="utf8"); scrivi_nota(old)
    if a.prova:
        sys.exit(0 if prova() else 1)


if __name__ == "__main__":
    main()
