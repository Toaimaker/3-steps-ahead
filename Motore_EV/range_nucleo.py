"""Il nucleo del range della mano avversaria: quello che serve per CALCOLARLO, senza tarare niente e senza pickle (21 nov 2026).

Autore, 21 nov 2026: «montiamo ogni miglioria apportata sul motore», per il range «Sì, solo Limited». La taratura e le misure restano in
range_mano.py (legge i replay di 17Lands, salva i pickle delle estrazioni); qui le classi delle carte, gli spot di una partita, la base del mazzo, le
regole, gli indizi e i due modelli (le carte coperte, il range), coi pesi da e verso un JSON: e' il pezzo che l'app (anche la pubblica) carica.
Il regolamento di sicurezza (Distribuzione/SICUREZZA.md, R2) vieta pickle.load nel pacchetto: per questo il nucleo e' a parte.
"""
import os, sys, re, json, math, time, zlib, collections
from pathlib import Path
QUI = Path(__file__).resolve().parent
ROOT = QUI.parent
if str(ROOT / "Companion") not in sys.path:
    sys.path.insert(0, str(ROOT / "Companion"))
import percorsi  # noqa: E402,F401
if str(QUI) not in sys.path:
    sys.path.insert(0, str(QUI))
import numpy as np  # noqa: E402

D17 = ROOT / "Dati" / "17lands"
STILE = D17 / "stile"
NOTA = ROOT / "Note" / "Motore_EV_Range.md"
NMAX = 12
CLASSI = ["terra", "cre12", "cre3", "cre4", "cre5", "rim_ist", "rim_sor", "trucco", "contro", "pescata", "altro"]
NOMI_CLASSI = {"terra": "terra", "cre12": "creatura 1-2", "cre3": "creatura 3", "cre4": "creatura 4", "cre5": "creatura 5+",
               "rim_ist": "rimozione istantanea", "rim_sor": "rimozione stregoneria", "trucco": "trucco", "contro": "contromagia",
               "pescata": "pescata", "altro": "altro", "rapida": "rapida (istantaneo o lampo)", "terra2": "due terre o piu'"}
BERSAGLI = CLASSI + ["rapida", "terra2"]
K = len(CLASSI)
PI = {"sorc": 0.55, "inst": 0.25}         # PI_DIFETTO di mano_avversaria.py
COLORI = "WUBRG"
BASI = {"plains": "W", "island": "U", "swamp": "B", "mountain": "R", "forest": "G"}
CAMPI_U = ["cards_drawn", "lands_played", "creatures_cast", "non_creatures_cast", "user_instants_sorceries_cast", "user_mana_spent",
           "creatures_attacked", "creatures_blocking", "cards_discarded", "eot_user_cards_in_hand", "eot_user_lands_in_play",
           "eot_user_creatures_in_play", "eot_user_non_creatures_in_play", "eot_oppo_creatures_in_play", "eot_user_life", "eot_oppo_life"]



# ---------------------------------------------------------------------------- le carte
_C = {}


def classe(g):
    """-> (indice della classe, rapida, cmc, colori) di un grpId; None se sconosciuto."""
    if g in _C:
        return _C[g]
    try:
        import testi_carte as TC
        c = TC.carta(g)
    except Exception:       # noqa: BLE001 - senza il database delle carte: la tabella salvata con la base (base_json) o niente
        c = None
    if not c:
        _C[g] = None
        return None
    nm, tipo, ab = TC.testo(g)
    tp = (tipo or "").split(" ")
    abl = re.sub(r"<[^>]+>", " ", (ab or "").lower())
    cmc = int(c.get("cmc") or 0)
    col = "".join(COLORI[x - 1] for x in (c.get("colors") or []) if 1 <= x <= 5)
    if "Land" in tp and "Creature" not in tp:
        col = BASI.get((nm or "").lower(), "")
        _C[g] = (0, False, 0, col)
        return _C[g]
    ist = "Instant" in tp
    rapida = ist or bool(re.search(r"(^|\W)flash(\W|$)", abl))
    if "Creature" in tp:
        k = "cre12" if cmc <= 2 else "cre3" if cmc == 3 else "cre4" if cmc == 4 else "cre5"
    else:
        try:
            import rimozioni as R
            liv = R.classifica(nm or "")[0] if nm else None
        except Exception:       # noqa: BLE001 - il classificatore delle rimozioni legge Scryfall: senza, la tabella salvata
            liv = None
        if liv != "vera" and re.search(r"put (two|three|four|five|six|x) -1/-1 counters on target creature", abl):
            liv = "vera"
        if liv == "vera":
            k = "rim_ist" if rapida else "rim_sor"
        elif rapida and "counter target" in abl:
            k = "contro"
        elif re.search(r"draw (a|two|three|four|x|that many) cards?", abl):
            k = "pescata"
        elif rapida:
            k = "trucco"
        else:
            k = "altro"
    _C[g] = (CLASSI.index(k), rapida, cmc, col)
    return _C[g]


def _ids(v):
    if not v:
        return []
    out = []
    for x in v.split("|"):
        try:
            out.append(int(float(x)))
        except ValueError:
            pass
    return out


def _n(v):
    try:
        return float(v) if v else 0.0
    except ValueError:
        return 0.0



def _test(draft_id):
    return zlib.crc32(str(draft_id).encode()) % 4 == 0           # un quarto dei draft: partite mai viste


# ---------------------------------------------------------------------------- una partita -> gli spot
def spot_partita(r, cols):
    """r: la riga (lista), cols: {nome: indice}. -> dict(draft, colori del mazzo, mazzo {nome: copie}, spot [...]) o None."""
    g = lambda c: r[cols[c]] if c in cols else ""       # noqa: E731
    on_play = g("on_play") == "True"
    mull = int(_n(g("num_mulligans")))
    nt = int(_n(g("num_turns")))
    mazzo = {}
    for c, i in cols.items():
        if c.startswith("deck_") and r[i] not in ("", "0", "0.0"):
            mazzo[c[5:]] = int(_n(r[i]))
    seq = []
    for N in range(1, min(NMAX, nt) + 1):
        seq += [("user", N), ("oppo", N)] if on_play else [("oppo", N), ("user", N)]
    seen_perm = collections.Counter()
    spells = collections.Counter()
    storia = []          # i suoi turni: (N, terre a fine turno, mana aperto, carte lanciate, indice del mezzo turno, terra giocata)
    altro = []           # i turni dell'altro: (indice, mana speso da R)
    mano_t = []          # la mano per oggetto: [id, indice di arrivo] (-1 = mano iniziale)
    draws = 0
    n_cre = n_ist = n_non = 0
    ult_magia = 0        # indice del mezzo turno dell'ultima magia
    ist_altro = 0        # magie lanciate nel turno dell'altro
    spesi_altro = 0.0    # mana speso nell'ultimo turno dell'altro
    att_altro = blocchi = 0
    terre_mancate = 0
    terra_ult = 1
    aperto = 0.0
    out = []
    for i, (lato, N) in enumerate(seq):
        p = f"{lato}_turn_{N}_"
        if not g(p + "eot_user_life"):
            break
        terre = _ids(g(p + "eot_user_lands_in_play"))
        cre = _ids(g(p + "eot_user_creatures_in_play"))
        non = _ids(g(p + "eot_user_non_creatures_in_play"))
        ist = _ids(g(p + "user_instants_sorceries_cast"))
        spells.update(ist)
        if lato == "user":
            draws += len(_ids(g(p + "cards_drawn")))
            lc = _ids(g(p + "creatures_cast")); ln = _ids(g(p + "non_creatures_cast"))
            spells.update(_ids(g(p + "cards_discarded")))
            n_cre += len(lc); n_non += len(ln); n_ist += len(ist)
            lanciate = set(lc) | set(ln) | set(ist)
            if lanciate:
                ult_magia = i
            giocata = bool(_ids(g(p + "lands_played")))
            terra_ult = int(giocata)
            terre_mancate += 0 if giocata else 1
            spesa = _n(g(p + "user_mana_spent"))
            aperto = max(0.0, len(terre) - spesa)
            storia.append((N, len(terre), aperto, lanciate, i, giocata))
            pescate = _ids(g(p + "cards_drawn"))
        else:
            spesi_altro = _n(g(p + "user_mana_spent"))
            altro.append((i, spesi_altro))
            pescate = []
            ist_altro += len(ist)
            if ist:
                ult_magia = i
            att_altro = len(_ids(g(p + "creatures_attacked")))
            blocchi = len(_ids(g(p + "creatures_blocking")))
        vis = collections.Counter(terre) + collections.Counter(cre) + collections.Counter(non)
        for k_, v in vis.items():
            if v > seen_perm[k_]:
                seen_perm[k_] = v
        mano = _ids(g(p + "eot_user_cards_in_hand"))
        H = len(mano)
        # gli oggetti della mano: chi c'era resta col suo arrivo, chi e' nuovo arriva ora (-1 al primo mezzo turno, tranne le pescate)
        cm, ct = collections.Counter(mano), collections.Counter(x for x, _a in mano_t)
        nuovo = []
        for gg, q in ct.items():
            togli = q - cm.get(gg, 0)
            if togli > 0:          # esce la copia piu' vecchia (con le copie uguali non si sa quale: grado C)
                cop = sorted([o for o in mano_t if o[0] == gg], key=lambda o: o[1])
                for o in cop[:togli]:
                    mano_t.remove(o)
        pesc = collections.Counter(pescate)
        for gg, q in cm.items():
            for _ in range(q - ct.get(gg, 0)):
                if i == 0 and not pesc.get(gg):
                    nuovo.append([gg, -1])
                else:
                    if pesc.get(gg):
                        pesc[gg] -= 1
                    nuovo.append([gg, i])
        mano_t.extend(nuovo)
        if H == 0:
            continue
        ogg = []
        for gg, arr in mano_t:
            c = classe(gg)
            if c is None:
                continue
            dopo = [x for x in storia if x[4] > arr]
            ogg.append((c[0], int(arr < 0), len(dopo), i - arr, sum(1 for x in dopo if not x[5]),
                        *[sum(1 for x in dopo if x[1] >= cc) for cc in range(1, 8)], sum(1 for x in dopo if x[2] >= 2),
                        sum(1 for a_, sp_ in altro if a_ > arr and sp_ > 0)))
        visti = dict(seen_perm)
        for k_, v in spells.items():
            visti[k_] = visti.get(k_, 0) + v
        col = set()
        for k_ in visti:
            c = classe(k_)
            if c:
                col.update(c[3])
        y = [0] * K
        ignote = 0
        for h in mano:
            c = classe(h)
            if c is None:
                ignote += 1
                continue
            y[c[0]] += 1
        rap = sum(1 for h in mano if (classe(h) or (0, False))[1])
        out.append(dict(
            N=N, mom=1 if lato == "user" else 0, on_play=int(on_play), mull=mull, H=H, terre=len(terre), mancate=terre_mancate, terra_ult=terra_ult,
            aperto=aperto, spesi_altro=spesi_altro, ist_altro=ist_altro, att_altro=att_altro, blocchi=blocchi, n_cre=n_cre, n_ist=n_ist, n_non=n_non,
            da_magia=i - ult_magia, vecchie=max(0, H - draws), draws=draws, mie_cre=len(cre), sue_cre=len(_ids(g(p + "eot_oppo_creatures_in_play"))),
            vita=_n(g(p + "eot_user_life")), sua_vita=_n(g(p + "eot_oppo_life")), col="".join(c for c in COLORI if c in col),
            visti=visti, storia=list(storia), y=y, ogg=ogg, mano_g=tuple(sorted(set(mano))), rap=rap, ignote=ignote,
            imp3=(tuple(sorted(terre)), tuple(sorted(cre)), tuple(sorted(non)), tuple(sorted(spells.elements())),
                  tuple(sorted(_ids(g(p + "eot_oppo_creatures_in_play")))))))
    if not out:
        return None
    colm = (g("main_colors") or "") + (g("splash_colors") or "")
    return dict(draft=g("draft_id"), test=_test(g("draft_id")), colori="".join(c for c in COLORI if c in colm), mazzo=mazzo, spot=out)


# ---------------------------------------------------------------------------- la base del mazzo
def _sotto(cs):
    return frozenset(cs)


class Base:
    """La composizione media dei mazzi di taratura nei colori mostrati (per classe, su 40 carte), e il pool per le regole."""

    def __init__(self, tara):
        import testi_carte as TC
        self.mazzi = []
        pres = collections.Counter()
        for p in tara:
            v = np.zeros(K); tot = 0
            for nm, q in p["mazzo"].items():
                gg = TC.per_nome(nm)
                c = classe(gg) if gg else None
                if c is None:
                    continue
                v[c[0]] += q; tot += q
                if c[0] != 0:
                    pres[gg] += 1
            if tot >= 30:
                self.mazzi.append((set(p["colori"]), v * 40.0 / tot))
        self.cache = {}
        n = len(self.mazzi)
        # il pool di mano_avversaria: 1 + 3 c/n copie per ogni magia vista in un mazzo
        self.pool_g = np.array(sorted(pres), np.int64)
        self.pool_w = np.array([1.0 + 3.0 * pres[g] / n for g in self.pool_g])
        info = [classe(int(g)) for g in self.pool_g]
        self.pool_k = np.array([c[0] for c in info])
        self.pool_cmc = np.array([c[2] for c in info], float)
        self.pool_rap = np.array([c[1] for c in info], bool)
        self.pool_col = [set(c[3]) for c in info]
        self.pool_idx = {int(g): i for i, g in enumerate(self.pool_g)}
        self.cache_m = {}

    def media(self, col):
        S = frozenset(col)
        if S not in self.cache:
            vv = [v for c, v in self.mazzi if S <= c]
            if len(vv) < 30:
                vv = [v for _c, v in self.mazzi]
            self.cache[S] = np.mean(vv, 0)
        return self.cache[S]

    def maschera(self, col):
        S = frozenset(col)
        if S not in self.cache_m:
            self.cache_m[S] = np.array([not (len(S) >= 2 and cc and not cc <= S) for cc in self.pool_col], bool)
        return self.cache_m[S]


def p_base(b, sp):
    """-> (P(almeno una) per le BERSAGLI, frazioni f per classe)."""
    m = b.media(sp["col"]).copy()
    for g, q in sp["visti"].items():
        c = classe(g)
        if c:
            m[c[0]] -= q
    m = np.maximum(m, 0.05)
    tot = max(m.sum(), 1.0)
    f = m / tot
    H = sp["H"]
    p = 1 - (1 - f) ** H
    # rapida: la frazione delle classi rapide (le creature lampo: la quota media dei mazzi, grado C) -> uso le classi istantanee + 8% delle creature
    f_rap = f[CLASSI.index("rim_ist")] + f[CLASSI.index("trucco")] + f[CLASSI.index("contro")] + 0.5 * f[CLASSI.index("pescata")] \
        + 0.08 * f[1:5].sum()
    fl = f[0]
    p2 = 1 - (1 - fl) ** H - H * fl * (1 - fl) ** max(H - 1, 0)
    return np.concatenate([p, [1 - (1 - f_rap) ** H, p2]]), f


def p_regole(b, sp, f_base, pesi=False):
    """mano_avversaria.py portato sui replay: le non-azioni sul pool; le terre con la quota della base. pesi=True: anche i pesi per carta."""
    w = b.pool_w * b.maschera(sp["col"])
    w = w.copy()
    for g, q in sp["visti"].items():
        j = b.pool_idx.get(g)
        if j is not None:
            w[j] = max(0.0, w[j] - q)
    st = sp["storia"]
    Tn = len(st)
    logm = np.zeros_like(w)
    for ii, (t, ter, aperto, lanciate, _i, _gio) in enumerate(st):
        giri = Tn - 1 - ii
        if sp["mom"] == 0:          # alla fine del turno dell'altro i suoi turni passati sono tutti; quello appena chiuso conta 1
            pass
        e = 0.8 ** giri
        pag = b.pool_cmc <= ter
        pp = np.where(b.pool_rap, PI["inst"], PI["sorc"])
        pp = np.where(aperto >= b.pool_cmc, np.minimum(0.95, pp * 1.4), pp)
        lan = np.array([int(g) in lanciate for g in b.pool_g]) if lanciate else np.zeros(len(w), bool)
        logm += np.where(pag & ~lan, np.log(1 - pp) * e, 0.0)
    w = w * np.exp(logm)
    s = w.sum()
    if s <= 0:
        return None
    quota = np.bincount(b.pool_k, weights=w, minlength=K) / s
    f = quota * (1 - f_base[0]); f[0] = f_base[0]
    H = sp["H"]
    p = 1 - (1 - f) ** H
    f_rap = (w * b.pool_rap).sum() / s * (1 - f_base[0])
    fl = f[0]
    p2 = 1 - (1 - fl) ** H - H * fl * (1 - fl) ** max(H - 1, 0)
    out = np.concatenate([p, [1 - (1 - f_rap) ** H, p2]])
    return (out, w) if pesi else out


def etichette(sp):
    y = np.array(sp["y"], float)
    return np.concatenate([(y >= 1).astype(float), [1.0 if sp["rap"] >= 1 else 0.0, 1.0 if y[0] >= 2 else 0.0]])


# ---------------------------------------------------------------------------- gli indizi
GRUPPI = {
    "pubblici": lambda s: [s["N"], s["mom"], s["on_play"], s["terre"], s["terra_ult"], s["mie_cre"], s["sue_cre"], s["vita"] / 20, s["sua_vita"] / 20,
                           len(s["col"]), s["n_cre"], s["n_ist"], s["n_non"]]
    + [1.0 * (s["H"] == h) for h in range(1, 9)] + [1.0 * (s["N"] == n) for n in range(1, 13)],
    "eta": lambda s: [s["vecchie"], min(s["vecchie"], 3) / max(s["H"], 1), s["da_magia"], min(s["da_magia"], 6), s["draws"]],
    "mulligan": lambda s: [s["mull"], 1.0 * (s["mull"] >= 1)],
    "nonazioni": lambda s: [s["aperto"], min(s["aperto"], 4), 1.0 * (s["aperto"] >= 2), s["spesi_altro"], s["ist_altro"], s["att_altro"],
                            s["blocchi"], 1.0 * (s["att_altro"] > 0 and s["blocchi"] == 0 and s["spesi_altro"] == 0), s["mancate"]],
}
ORDINE = ["pubblici", "regole", "eta", "oggetti", "mulligan", "nonazioni"]
PROB = {"regole": "PR", "oggetti": "PO"}


def logit(p):
    p = np.clip(p, 1e-4, 1 - 1e-4)
    return np.log(p / (1 - p))


def costruisci(partite, b, con_regole=True, log=print):
    """-> dict di matrici: Y (S x B), PB, PR, X {gruppo: matrice}, gid (indice di partita), test (bool), H, N, mom, imp (impronte per la scala)."""
    Y, PB, PR, gid, test, FB = [], [], [], [], [], []
    OS, OC, OX = [], [], []
    X = {k: [] for k in GRUPPI}
    imp = {"L0": [], "L1": [], "L2": [], "L3": []}
    t0 = time.time()
    for ip, p in enumerate(partite):
        for sp in p["spot"]:
            pb, fb = p_base(b, sp)
            pr = p_regole(b, sp, fb) if con_regole else pb
            if pr is None:
                pr = pb
            si = len(Y)
            Y.append(etichette(sp)); PB.append(pb); PR.append(pr); gid.append(ip); test.append(p["test"]); FB.append(fb)
            for o in sp["ogg"]:
                OS.append(si); OC.append(o[0]); OX.append(ogg_x(o, sp))
            for k, fn in GRUPPI.items():
                X[k].append(fn(sp))
            l0 = (sp["N"], sp["mom"])
            l1 = l0 + (sp["on_play"], sp["H"], sp["terre"], min(sp["n_cre"], 6), min(sp["n_ist"], 4))
            l2 = l1 + (sp["col"], sp["mie_cre"], sp["sue_cre"], int(sp["vita"] // 5), int(sp["aperto"]), int(sp["spesi_altro"] > 0), sp["mull"])
            l3 = l2 + sp["imp3"]
            for nm, v in (("L0", l0), ("L1", l1), ("L2", l2), ("L3", l3)):
                imp[nm].append(hash(v))
        if ip % 10000 == 0 and ip:
            log(f"    {ip} partite, {time.time() - t0:.0f} s")
    D = dict(Y=np.array(Y), PB=np.array(PB), PR=np.array(PR), gid=np.array(gid), test=np.array(test, bool), FB=np.array(FB),
             OS=np.array(OS, np.int64), OC=np.array(OC, np.int64), OX=np.array(OX, np.float32),
             X={k: np.array(v, float) for k, v in X.items()}, imp={k: np.array(v, np.int64) for k, v in imp.items()})
    return D


# ---------------------------------------------------------------------------- le carte coperte, una per una
def ogg_x(o, sp):
    """Gli indizi di una carta coperta: da dove viene (mano iniziale), quanti suoi turni ha attraversato, in quanti non ha giocato la terra (allora non
    e' una terra), in quanti aveva almeno 1..7 terre (non l'ha lanciata pur potendo), in quanti ha lasciato 2+ mana aperto, in quanti turni dell'altro
    ha speso mana; piu' il momento."""
    _k, ini, giri, eta, mancate, *resto = o
    esp, aperti, spesi = resto[:7], resto[7], resto[8]
    return [ini, giri, min(giri, 4), 1.0 * (giri == 0), eta, mancate, 1.0 * (mancate > 0), *esp, aperti, spesi, sp["N"], sp["mom"], sp["H"],
            sp["terre"], sp["mull"], len(sp["col"]), ini * giri]


def tara_softmax(X, c, off, l2=1e-4, maxiter=300):
    """Regressione multinomiale: logit = X W + b + beta * off (off = log della frazione della base per classe). -> (W, b, beta)."""
    from scipy.optimize import minimize
    n, d = X.shape
    Kc = off.shape[1]
    Yh = np.zeros((n, Kc)); Yh[np.arange(n), c] = 1

    def f(w):
        W = w[:d * Kc].reshape(d, Kc); b = w[d * Kc:d * Kc + Kc]; be = w[-1]
        Z = X @ W + b + be * off
        Z -= Z.max(1, keepdims=True)
        E = np.exp(Z); S = E.sum(1, keepdims=True); P = E / S
        L = -np.sum(Z[np.arange(n), c] - np.log(S[:, 0])) / n + l2 * np.sum(W ** 2)
        G = (P - Yh) / n
        gW = X.T @ G + 2 * l2 * W
        return L, np.concatenate([gW.ravel(), G.sum(0), [np.sum(G * off)]])
    w0 = np.zeros(d * Kc + Kc + 1); w0[-1] = 1.0
    r = minimize(f, w0, jac=True, method="L-BFGS-B", options=dict(maxiter=maxiter))
    w = r.x
    return w[:d * Kc].reshape(d, Kc), w[d * Kc:d * Kc + Kc], w[-1]


class Oggetti:
    """Il modello per carta coperta: la classe di ogni carta in mano dalla sua eta' e dai turni che ha attraversato; la mano = le carte insieme."""

    def fit(self, D, spot_ok, max_righe=1500000, seme=3):
        m = spot_ok[D["OS"]]
        ii = np.where(m)[0]
        if len(ii) > max_righe:
            ii = np.random.default_rng(seme).choice(ii, max_righe, replace=False)
        X = D["OX"][ii].astype(float)
        self.mu, self.sd = X.mean(0), X.std(0) + 1e-6
        off = np.log(np.maximum(D["FB"][D["OS"][ii]], 1e-4))
        self.W, self.b, self.beta = tara_softmax((X - self.mu) / self.sd, D["OC"][ii], off)
        return self

    def prob_oggetti(self, D, sel=None):
        sel = np.arange(len(D["OS"])) if sel is None else sel
        X = (D["OX"][sel].astype(float) - self.mu) / self.sd
        Z = X @ self.W + self.b + self.beta * np.log(np.maximum(D["FB"][D["OS"][sel]], 1e-4))
        Z -= Z.max(1, keepdims=True); E = np.exp(Z)
        return E / E.sum(1, keepdims=True)

    def prob(self, D):
        """-> (S x BERSAGLI) P(almeno una) per ogni spot: le carte coperte indipendenti, ognuna con la sua distribuzione."""
        P = self.prob_oggetti(D)
        S = len(D["Y"])
        lnon = np.zeros((S, K))
        np.add.at(lnon, D["OS"], np.log(np.clip(1 - P, 1e-9, 1)))
        out = np.zeros((S, len(BERSAGLI)))
        out[:, :K] = 1 - np.exp(lnon)
        ir = [CLASSI.index(x) for x in ("rim_ist", "trucco", "contro")]
        prap = P[:, ir].sum(1) + 0.5 * P[:, CLASSI.index("pescata")] + 0.08 * P[:, 1:5].sum(1)
        lr = np.zeros(S); np.add.at(lr, D["OS"], np.log(np.clip(1 - prap, 1e-9, 1)))
        out[:, K] = 1 - np.exp(lr)
        q = P[:, 0]
        l0 = np.zeros(S); np.add.at(l0, D["OS"], np.log(np.clip(1 - q, 1e-9, 1)))
        r1 = np.zeros(S); np.add.at(r1, D["OS"], q / np.clip(1 - q, 1e-9, 1))
        p0 = np.exp(l0)
        out[:, K + 1] = np.clip(1 - p0 - p0 * r1, 0, 1)
        self.P = P
        return out


# ---------------------------------------------------------------------------- la logistica
def ll(y, p):
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return -(y * np.log(p) + (1 - y) * np.log(1 - p))


def tara_logistica(X, y, l2=1e-3, base=None):
    """Regressione logistica (con intercetta) con L2 piccola; X gia' standardizzata. -> pesi."""
    from scipy.optimize import minimize
    n, d = X.shape
    off = base if base is not None else np.zeros(n)

    def f(w):
        z = X @ w[1:] + w[0] + off
        p = 1 / (1 + np.exp(-np.clip(z, -30, 30)))
        L = np.sum(np.logaddexp(0, z) - y * z) / n + l2 * np.sum(w[1:] ** 2)
        gr = np.concatenate([[np.sum(p - y)], X.T @ (p - y)]) / n
        gr[1:] += 2 * l2 * w[1:]
        return L, gr
    r = minimize(f, np.zeros(d + 1), jac=True, method="L-BFGS-B", options=dict(maxiter=400))
    return r.x


def matrice(D, gruppi, idx):
    cols = []
    for gname in gruppi:
        if gname in PROB:
            continue
        cols.append(D["X"][gname][idx])
    return np.concatenate(cols, 1) if cols else np.zeros((len(idx), 0))


class Range:
    def __init__(self, gruppi):
        self.gruppi = list(gruppi)

    def fit(self, D, idx, Y=None):
        Y = D["Y"] if Y is None else Y
        Xr = matrice(D, self.gruppi, idx)
        self.mu = Xr.mean(0) if Xr.shape[1] else None
        self.sd = Xr.std(0) + 1e-6 if Xr.shape[1] else None
        self.w = []
        for j in range(Y.shape[1]):
            Xj = self._X(D, idx, j, Xr)
            self.w.append(tara_logistica(Xj, Y[idx, j]))
        return self

    def _X(self, D, idx, j, Xr=None):
        if Xr is None:
            Xr = matrice(D, self.gruppi, idx)
        parti = [logit(D["PB"][idx, j])[:, None]]
        for gname, chiave in PROB.items():
            if gname in self.gruppi:
                parti.append(logit(D[chiave][idx, j])[:, None])
        if Xr.shape[1]:
            parti.append((Xr - self.mu) / self.sd)
        return np.concatenate(parti, 1)

    def predict(self, D, idx):
        Xr = matrice(D, self.gruppi, idx)
        out = np.zeros((len(idx), len(self.w)))
        for j, w in enumerate(self.w):
            z = self._X(D, idx, j, Xr) @ w[1:] + w[0]
            out[:, j] = 1 / (1 + np.exp(-np.clip(z, -30, 30)))
        return out


def riga_arena(x, d=None, posto=None, turni=None):
    """Una partita dei nostri log (mana_aperto) come una riga del replay di 17Lands, dal posto dell'Hero (lui e' «user»). -> (riga, cols) o None.
    Per mezzo turno: la mano a fine mezzo turno, le terre, creature e altri permanenti in campo, le pescate, la terra giocata, le magie lanciate (le
    creature, gli altri permanenti, istantanei e stregonerie anche nel turno dell'altro), il mana speso (le sue terre tappate a fine mezzo turno), chi ha
    attaccato e chi ha bloccato, le creature dell'altro, le vite. Grado C: gli scarti non ci sono; il mana speso conta solo le terre.
    posto: il posto di chi ha la mano da stimare (di partenza l'Hero). Se e' l'Opponent la sua mano e' coperta: ogni carta e' il segnaposto 0, con la sua
    eta' (il modello per carta guarda solo da quanto e' in mano e cosa e' successo intanto, non il nome). turni: un dict che riceve (lato, N) -> turno."""
    sys.path.insert(0, str(ROOT / "Companion" / "App" / "Schede" / "Performance"))
    import dati_analizzatore as DA
    d = d or DA._MANA.get(x.get("partita"))
    hero = x.get("seat")
    if not d or hero not in (1, 2) or x.get("inizia") is None or not d.get("foto"):
        return None
    seat = posto or hero
    coperta = seat != hero
    hs, os_ = seat - 1, 2 - seat
    terra = lambda g: DA.e_terra(DA.nome_grp(g) or "")       # noqa: E731
    primo = bool(x.get("inizia")) != coperta
    mull = {"1": 1, "2+": 2}.get(DA.suo_mulligan(x.get("partita"), hero), 0) if coperta else x.get("mulligan")
    R = {"on_play": "True" if primo else "False", "num_mulligans": str(mull or 0), "draft_id": str(x.get("partita"))}
    att = collections.defaultdict(int); blk = collections.defaultdict(int)
    for mm in d.get("momenti") or []:
        if mm[0] == "comb" and len(mm) > 4 and isinstance(mm[4], dict):
            t, posto = mm[1], mm[2]
            if posto == seat:
                att[t] = max(att[t], len(mm[4].get("att") or []))
            else:
                blk[t] = max(blk[t], len(mm[4].get("blocchi") or []))
    az = collections.defaultdict(list)
    for a in d.get("azioni") or []:
        az[a[0]].append(a)
    n = {"user": 0, "oppo": 0}
    nt = 0
    for t, posto, f in d["foto"]:
        lato = "user" if posto == seat else "oppo"
        n[lato] += 1
        N = n[lato]
        if N > NMAX:
            break
        nt = max(nt, N)
        if turni is not None:
            turni[(lato, N)] = t
        pre = f"{lato}_turn_{N}_"
        campo = (f.get("c") or [[], []])
        mio = campo[hs] or []
        suo = campo[os_] or []
        terre = [z[0] for z in mio if terra(z[0])]
        cre = [z[0] for z in mio if not terra(z[0]) and z[3] is not None]
        non = [z[0] for z in mio if not terra(z[0]) and z[3] is None]
        J = lambda v: "|".join(str(int(g)) for g in v)       # noqa: E731
        R[pre + "eot_user_cards_in_hand"] = J([0] * int((f.get("n") or [0, 0])[hs] or 0) if coperta else (((f.get("m") or [[], []])[hs]) or []))
        R[pre + "eot_user_lands_in_play"] = J(terre)
        R[pre + "eot_user_creatures_in_play"] = J(cre)
        R[pre + "eot_user_non_creatures_in_play"] = J(non)
        R[pre + "eot_oppo_creatures_in_play"] = J([z[0] for z in suo if not terra(z[0]) and z[3] is not None])
        v = f.get("v") or [20, 20]
        R[pre + "eot_user_life"] = str(v[hs]); R[pre + "eot_oppo_life"] = str(v[os_])
        R[pre + "user_mana_spent"] = str(sum(1 for z in mio if terra(z[0]) and z[1]))
        mie = [a for a in az.get(t, []) if a[1] == seat]
        R[pre + "user_instants_sorceries_cast"] = J([a[3] for a in mie if a[2] == "magia" and ("I" in a[4] or "S" in a[4]) and "C" not in a[4]])
        if lato == "user":
            R[pre + "cards_drawn"] = J([0 if coperta else a[3] for a in mie if a[2] == "pesca" and (a[3] or coperta)])
            R[pre + "lands_played"] = J([a[3] for a in mie if a[2] == "terra"])
            R[pre + "creatures_cast"] = J([a[3] for a in mie if a[2] == "magia" and "C" in a[4]])
            R[pre + "non_creatures_cast"] = J([a[3] for a in mie if a[2] == "magia" and "C" not in a[4] and "I" not in a[4] and "S" not in a[4]])
            R[pre + "creatures_attacked"] = J([0] * att.get(t, 0))
        else:
            R[pre + "creatures_blocking"] = J([0] * blk.get(t, 0))
    R["num_turns"] = str(nt)
    cols = {c: i for i, c in enumerate(R)}
    return list(R.values()), cols



# ---------------------------------------------------------------------------- i pesi in JSON (per l'app)
def _a(v):
    return None if v is None else np.asarray(v).tolist()


def modello_a_dict(m):
    rg = lambda r: dict(gruppi=r.gruppi, mu=_a(r.mu), sd=_a(r.sd), w=[_a(w) for w in r.w])        # noqa: E731
    og = m["oggetti"]
    return dict(set=m["set"], tenuti=m["tenuti"], range=rg(m["range"]), base_ric=rg(m["base_ric"]),
                oggetti=dict(mu=_a(og.mu), sd=_a(og.sd), W=_a(og.W), b=_a(og.b), beta=float(og.beta)))


def modello_da_dict(d):
    def rg(x):
        r = Range(x["gruppi"])
        r.mu = None if x["mu"] is None else np.array(x["mu"])
        r.sd = None if x["sd"] is None else np.array(x["sd"])
        r.w = [np.array(w) for w in x["w"]]
        return r
    og = Oggetti()
    o = d["oggetti"]
    og.mu, og.sd, og.W, og.b, og.beta = np.array(o["mu"]), np.array(o["sd"]), np.array(o["W"]), np.array(o["b"]), o["beta"]
    return dict(set=d["set"], tenuti=d["tenuti"], range=rg(d["range"]), base_ric=rg(d["base_ric"]), oggetti=og)


def base_a_dict(b, classi):
    import itertools
    medie = {}
    for n in range(0, 6):         # la composizione media per ogni insieme di colori (Base.media): l'unica cosa che il calcolo legge dei mazzi
        for cs in itertools.combinations(COLORI, n):
            medie["".join(cs)] = _a(b.media(set(cs)))
    return dict(medie=medie, pool_g=_a(b.pool_g), pool_w=_a(b.pool_w),
                classi={str(g): list(c) for g, c in classi.items() if c is not None})


def base_da_dict(d):
    for g, c in d["classi"].items():
        _C.setdefault(int(g), (int(c[0]), bool(c[1]), int(c[2]), c[3]))
    b = Base.__new__(Base)
    b.mazzi = []
    b.cache = {frozenset(c): np.array(v) for c, v in d["medie"].items()}
    b.cache_m = {}
    b.pool_g = np.array(d["pool_g"], np.int64)
    b.pool_w = np.array(d["pool_w"])
    info = [classe(int(g)) for g in b.pool_g]
    b.pool_k = np.array([c[0] for c in info])
    b.pool_cmc = np.array([c[2] for c in info], float)
    b.pool_rap = np.array([c[1] for c in info], bool)
    b.pool_col = [set(c[3]) for c in info]
    b.pool_idx = {int(g): i for i, g in enumerate(b.pool_g)}
    return b


MODELLO_JSON = QUI / "range_mano_modello_{s}.json"
BASE_JSON = QUI / "range_mano_base_{s}.json"
_CARICATI = {}


def carica_json(s_modello, s_base):
    """-> (modello, base) dai JSON, una volta per processo; None se mancano."""
    k = (s_modello, s_base)
    if k not in _CARICATI:
        fm, fb = Path(str(MODELLO_JSON).format(s=s_modello)), Path(str(BASE_JSON).format(s=s_base))
        if not (fm.exists() and fb.exists()):
            return None
        _CARICATI[k] = (modello_da_dict(json.loads(fm.read_text(encoding="utf8"))), base_da_dict(json.loads(fb.read_text(encoding="utf8"))))
    return _CARICATI[k]



ETICHETTE = (("terra", "a land"), ("terra2", "2+ lands"), ("rim_ist", "instant removal"), ("rim_sor", "sorcery removal"), ("trucco", "a combat trick"),
             ("contro", "a counterspell"), ("rapida", "something at instant speed"))


def set_evento(evento):
    """Il set di un evento limited di Arena (QuickDraft_FRA_20261008 -> FRA), o None."""
    m = re.search(r"(?:Draft|Sealed|Cube)_([A-Z0-9]{3})_", str(evento or ""))
    return m.group(1) if m else None


def range_partita(x, d=None, s_modello="ECL"):
    """Il range della mano dell'Opponent a fine di ogni mezzo turno di una nostra partita limited, dai JSON del modello e della base del set
    dell'evento. -> [dict(t=turno, mio=l'Hero era di turno, N, H, p={classe: probabilita'})] in ordine, o None (nessun set, modello o base)."""
    s_base = set_evento(x.get("evento"))
    mb = carica_json(s_modello, s_base) if s_base else None
    seat = x.get("seat")
    if mb is None or seat not in (1, 2):
        return None
    m, b = mb
    turni = {}
    rr = riga_arena(x, d, posto=3 - seat, turni=turni)
    if rr is None:
        return None
    _C.setdefault(0, (0, False, 0, ""))        # il segnaposto delle carte coperte: la classe non conta per le previsioni
    pp = spot_partita(*rr)
    if not pp:
        return None
    pp["test"] = True
    D = costruisci([pp], b, log=lambda *_a: None)
    D["PO"] = m["oggetti"].prob(D)
    P = m["range"].predict(D, np.arange(len(D["Y"])))
    out = []
    for sp, pv in zip(pp["spot"], P):
        lato = "user" if sp["mom"] == 1 else "oppo"
        t = turni.get((lato, sp["N"]))
        if t is None:
            continue
        out.append(dict(t=t, mio=lato == "oppo", N=sp["N"], H=sp["H"], p={k: float(pv[BERSAGLI.index(k)]) for k, _e in ETICHETTE}))
    return out
