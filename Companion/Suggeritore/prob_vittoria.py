"""La probabilita' di vincere da un tavolo, misurata sui replay 17Lands (HANDOFF_Spalla_Pensa_In_Partite §5.1-5.2).

Autore, 12 ott 2026 17:45: «bisogna che lui pensi in termine di partita, vorrebbe arrivare a chiudere il piu' veloce
possibile e calcola ogni variabile per raggiungere l'obiettivo in EV». Il metro del turno intero diventa la P(vittoria) del
tavolo che il turno lascia; questo modulo la misura.

Il dato
  Le tabelle per turno di Motore/stile_vincente.py (Dati/17lands/stile/<SET>_attacco.pkl e _difesa.pkl, fuori da git):
  una riga per ogni turno fino al 12° giro, con lo stato del tavolo PRIMA del turno (fine del turno precedente) visto da
  te. Righe «tocca a te» (prima del tuo turno) e «tocca a lui» (prima del suo). Sei set del Premier Draft: HOB, MSH, SOS,
  TMT, TLA, ECL. Le partite si dividono per draft (lo stesso mazzo non sta nelle due meta'): una meta' tara, l'altra prova.

Le variabili (sempre dal tuo lato)
  tocca a te, giro (1-12, oltre si legge come 12), chi ha iniziato, vite tue e sue, creature tue e sue: numero, forza e
  costituzione sommate (stampate nel dato, vere dal vivo), evasive (volare, minacciare, imbloccabile), con volare o
  raggiungere, quelle che possono attaccare (forza 1+ e senza difensore); terre in campo, carte in mano, mulligan,
  creature tappate dal turno prima (le sue quando tocca a te: non bloccano; le tue quando tocca a lui), la bravura del
  giocatore (bucket di win rate di 17Lands) e la qualita' del mazzo (GP WR medio delle carte, scarto dalla media del set).
  Dal vivo bravura = 0,50 e qualita' = 0: la P e' quella di un giocatore medio con un mazzo medio, contro il suo pari.
  Dal 13 ott 2026 (HANDOFF_Spalla_Senso_Di_Partita passo 1) anche il valore delle carte: il GIH WR (17Lands) delle tue
  creature in campo, delle sue e delle carte nella tua mano, come media, massimo e somma dello scarto dalla media del set
  (Motore/carte_in_p.py: contato sulla sola meta' di taratura, per non vedere l'esito attraverso la carta). Dal vivo il
  GIH viene dall'anagrafe di FRA (Premier, lo stesso metro della spalla); pedine e carte senza dato restano fuori dalla
  media, come nel dato.

Il modello
  Gradient boosting a istogrammi scritto qui (numpy: sklearn non c'e' sul PC), perdita logistica, alberi di profondita'
  5, vincoli monotoni dove il verso e' ovvio (piu' vite tue, piu' forza tua, piu' carte in mano tua non valgono mai meno;
  il contrario per lui): il piano confronta tavoli vicini e un modello che oscilla sceglierebbe a caso. Si confronta, sulla
  meta' non usata, con la logistica sulle stesse variabili e col modello delle sole vite. Si tiene il migliore (regola
  del giudice dei motori).
  I turni per chiudere: un secondo boosting (perdita quadratica) sulle sole partite vinte, che stima quanti tuoi turni
  mancano alla fine contando quello che sta per cominciare (o il prossimo, se tocca a lui).

Limiti dichiarati
  Grado B: misurato sul Premier di altri set, contro giocatori di 17Lands (piu' bravi della media). FRA e il Quick possono
  essere diversi: si controlla sulle nostre partite (--fra), poche, solo un controllo. Forza e costituzione del dato sono
  quelle stampate: segnalini, aure e pedine sconosciute mancano. Oltre il 12° giro il modello legge 12. Nessuna carta
  conta per quello che fa: un 2/2 con un'abilita' che vince la partita pesa come un 2/2.

Uso
  py -I -X utf8 Companion/Suggeritore/prob_vittoria.py --tara [--partite 20000]    tara e prova, scrive Regole/prob_vittoria.json
  py -I -X utf8 Companion/Suggeritore/prob_vittoria.py --prova                       esempi a mano
  dal codice:  import prob_vittoria as PV; PV.p_vittoria(stato); PV.turni_per_chiudere(stato)
"""
import os, sys; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); import percorsi  # la casa del Companion: i percorsi stanno in Companion/percorsi.py (13 ott 2026)
import os, sys, json, math, time, argparse
from pathlib import Path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

ROOT = Path(percorsi.ROOT)
STILE = ROOT / "Dati" / "17lands" / "stile"
OUT = ROOT / "Regole" / "prob_vittoria.json"
SET = ["HOB", "MSH", "SOS", "TMT", "TLA", "ECL"]
NMAX = 12

# nome, verso monotono per la P (+1 sale con la variabile, -1 scende, 0 libero), verso per i turni per chiudere
VAR = [("tocca_me", 0, 0), ("N", 0, 0), ("on_play", 0, 0),
       ("LU", +1, 0), ("LO", -1, +1),
       ("U", +1, 0), ("PU", +1, -1), ("TU", +1, 0), ("EVU", +1, -1), ("AAU", +1, 0), ("UA", +1, 0),
       ("O", -1, 0), ("PO", -1, 0), ("TO", -1, 0), ("EVO", -1, 0), ("AAO", -1, 0), ("OA", -1, 0),
       ("TERU", 0, 0), ("TERO", 0, 0), ("MANU", +1, 0), ("MANO", -1, 0),
       ("mull", -1, 0), ("opp_mull", +1, 0),
       ("tappati_suoi", +1, 0), ("tappati_miei", -1, 0),
       ("bravura", +1, 0), ("qualita", +1, 0),
       # il valore delle carte (13 ott 2026, Motore/carte_in_p.py): GIH centrato sul set, media / massimo / somma delle
       # tue creature in campo (U), delle sue (O) e delle carte non terra nella tua mano (M). In coda: il modello vecchio
       # (Regole/prob_vittoria.senza_carte.json) legge le prime 27 e resta valido
       ("GIHU_m", +1, 0), ("GIHU_max", +1, 0), ("GIHU_s", +1, 0),
       ("GIHO_m", -1, 0), ("GIHO_max", -1, 0), ("GIHO_s", -1, 0),
       ("GIHM_m", +1, 0), ("GIHM_max", +1, 0), ("GIHM_s", +1, 0)]
NOMI = [v[0] for v in VAR]
MONO_P = [v[1] for v in VAR]
MONO_K = [v[2] for v in VAR]
CARTE = [n for n in NOMI if n.startswith("GIH")]
COL_STATO = ["N", "U", "PU", "TU", "EVU", "AAU", "UA", "O", "PO", "TO", "EVO", "AAO", "OA",
             "LU", "LO", "TERU", "TERO", "MANU", "MANO"]
DIFETTO = {"bravura": 0.50, "qualita": 0.0, "mull": 0, "opp_mull": 0, "tappati_suoi": 0, "tappati_miei": 0,
           "on_play": 0, **{n: 0.0 for n in CARTE}}


# ======================================================================== il boosting
class Boosting:
    """Alberi binari a istogramma, livello per livello. Una foglia e' un valore; un nodo e' (variabile, soglia sul valore
    grezzo: a sinistra se x <= soglia). Si salva in JSON, si legge senza numpy."""

    def __init__(self, perdita="logistica", profondita=5, lr=0.1, alberi=400, lam=1.0, min_h=50.0, campione=0.5,
                 mono=None, seme=7):
        self.perdita, self.prof, self.lr, self.max_alberi = perdita, profondita, lr, alberi
        self.lam, self.min_h, self.campione, self.mono, self.seme = lam, min_h, campione, mono, seme
        self.alberi, self.base = [], 0.0

    # ---- i cassetti
    @staticmethod
    def cassetti(X, max_b=63):
        import numpy as np
        tagli = []
        for j in range(X.shape[1]):
            x = X[:, j]
            u = np.unique(x)
            if len(u) <= max_b:
                t = (u[:-1] + u[1:]) / 2.0
            else:
                t = np.unique(np.quantile(x, np.linspace(0, 1, max_b + 1)[1:-1]))
            tagli.append(t.astype(np.float64))
        return tagli

    @staticmethod
    def in_cassetti(X, tagli):
        import numpy as np
        return np.stack([np.searchsorted(t, X[:, j], side="left").astype(np.uint8) for j, t in enumerate(tagli)])

    def _gh(self, F, y):
        import numpy as np
        if self.perdita == "logistica":
            p = 1.0 / (1.0 + np.exp(-F))
            return p - y, np.maximum(p * (1 - p), 1e-6)
        return F - y, np.ones_like(F)

    def perdita_di(self, F, y):
        import numpy as np
        if self.perdita == "logistica":
            return float(np.mean(np.logaddexp(0, F) - y * F))
        return float(np.mean((F - y) ** 2))

    def fit(self, X, y, Xv=None, yv=None, ogni=10, pazienza=3, voce=""):
        import numpy as np
        rng = np.random.default_rng(self.seme)
        self.tagli = self.cassetti(X)
        B = self.in_cassetti(X, self.tagli)
        nb = [len(t) + 1 for t in self.tagli]
        if self.perdita == "logistica":
            m = float(np.clip(y.mean(), 1e-4, 1 - 1e-4)); self.base = math.log(m / (1 - m))
        else:
            self.base = float(y.mean())
        F = np.full(len(y), self.base)
        Fv = None if Xv is None else np.full(len(yv), self.base)
        Bv = None if Xv is None else self.in_cassetti(Xv, self.tagli)
        mono = self.mono or [0] * X.shape[1]
        meglio, n_meglio, peggio, t0 = 1e9, 0, 0, time.time()
        for it in range(self.max_alberi):
            g, h = self._gh(F, y)
            idx = np.flatnonzero(rng.random(len(y)) < self.campione)
            albero = self._albero(B, g, h, idx, nb, mono)
            self.alberi.append(albero)
            F += self._pred_b(albero, B)
            if Fv is not None:
                Fv += self._pred_b(albero, Bv)
                if (it + 1) % ogni == 0:
                    l = self.perdita_di(Fv, yv)
                    print(f"   {voce} albero {it + 1}: perdita di convalida {l:.5f} ({time.time() - t0:.0f} s)", flush=True)
                    if l < meglio - 1e-6: meglio, n_meglio, peggio = l, it + 1, 0
                    else:
                        peggio += 1
                        if peggio >= pazienza: break
        if Fv is not None and n_meglio: self.alberi = self.alberi[:n_meglio]
        return self

    def _albero(self, B, g, h, idx, nb, mono):
        import numpy as np
        lam, nodi = self.lam, []
        # un nodo: dict con idx (righe), lo, hi (limiti monotoni), id
        coda = [{"idx": idx, "lo": -1e9, "hi": 1e9, "d": 0, "id": 0}]
        nodi.append(None)
        while coda:
            nuovo = []
            for nd in coda:
                ii = nd["idx"]; G = g[ii].sum(); H = h[ii].sum()
                w = float(np.clip(-G / (H + lam), nd["lo"], nd["hi"]))
                best = None
                if nd["d"] < self.prof and H >= 2 * self.min_h:
                    base = G * G / (H + lam)
                    gi, hi = g[ii], h[ii]
                    for j in range(B.shape[0]):
                        bj = B[j, ii]
                        Gb = np.bincount(bj, weights=gi, minlength=nb[j]); Hb = np.bincount(bj, weights=hi, minlength=nb[j])
                        GL = np.cumsum(Gb)[:-1]; HL = np.cumsum(Hb)[:-1]; GR = G - GL; HR = H - HL
                        ok = (HL >= self.min_h) & (HR >= self.min_h)
                        if not ok.any(): continue
                        wl = np.clip(-GL / (HL + lam), nd["lo"], nd["hi"]); wr = np.clip(-GR / (HR + lam), nd["lo"], nd["hi"])
                        if mono[j] > 0: ok &= wl <= wr
                        elif mono[j] < 0: ok &= wl >= wr
                        # guadagno coi pesi vincolati: -(2 G w + (H+lam) w^2)
                        gain = -(2 * GL * wl + (HL + lam) * wl ** 2) - (2 * GR * wr + (HR + lam) * wr ** 2) - base
                        gain = np.where(ok, gain, -np.inf)
                        k = int(np.argmax(gain))
                        if gain[k] > 1e-9 and (best is None or gain[k] > best[0]):
                            best = (float(gain[k]), j, k, float(wl[k]), float(wr[k]))
                if best is None:
                    nodi[nd["id"]] = {"f": w * self.lr}
                    continue
                _, j, k, wl, wr = best
                sx = B[j, ii] <= k
                lo_l, hi_l, lo_r, hi_r = nd["lo"], nd["hi"], nd["lo"], nd["hi"]
                if mono[j] != 0:
                    mid = (wl + wr) / 2.0
                    if mono[j] > 0: hi_l, lo_r = min(hi_l, mid), max(lo_r, mid)
                    else: lo_l, hi_r = max(lo_l, mid), min(hi_r, mid)
                il, ir = len(nodi), len(nodi) + 1
                nodi.extend([None, None])
                nodi[nd["id"]] = {"v": j, "b": k, "s": float(self.tagli[j][k]), "l": il, "r": ir}
                nuovo.append({"idx": ii[sx], "lo": lo_l, "hi": hi_l, "d": nd["d"] + 1, "id": il})
                nuovo.append({"idx": ii[~sx], "lo": lo_r, "hi": hi_r, "d": nd["d"] + 1, "id": ir})
            coda = nuovo
        return nodi

    @staticmethod
    def _pred_b(nodi, B):
        import numpy as np
        foglia = np.array(["f" in n for n in nodi]); val = np.array([n.get("f", 0.0) for n in nodi])
        v = np.array([n.get("v", 0) for n in nodi]); b = np.array([n.get("b", 0) for n in nodi])
        l = np.array([n.get("l", 0) for n in nodi]); r = np.array([n.get("r", 0) for n in nodi])
        n = B.shape[1]; pos = np.zeros(n, np.int32); attivi = np.arange(n)
        while len(attivi):
            p = pos[attivi]
            attivi = attivi[~foglia[p]]
            if not len(attivi): break
            p = pos[attivi]
            pos[attivi] = np.where(B[v[p], attivi] <= b[p], l[p], r[p])
        return val[pos]

    def predici_grezzo(self, X):
        import numpy as np
        B = self.in_cassetti(X, self.tagli)
        F = np.full(X.shape[0], self.base)
        for a in self.alberi: F += self._pred_b(a, B)
        return F

    def a_json(self):
        return {"perdita": self.perdita, "base": self.base,
                "alberi": [[[n["v"], n["s"], n["l"], n["r"]] if "v" in n else n["f"] for n in a] for a in self.alberi]}


def valuta_json(m, x):
    """Una riga, senza numpy: la somma delle foglie (logit per la logistica)."""
    F = m["base"]
    for a in m["alberi"]:
        i = 0
        while True:
            n = a[i]
            if not isinstance(n, list): F += n; break
            i = n[2] if x[n[0]] <= n[1] else n[3]
    return F


def valuta_json_np(m, X):
    """Tante righe, con numpy: il logit (o il valore) di un modello salvato, sulle colonne che quel modello conosce.
    Serve al confronto fra un modello vecchio e uno nuovo sulle stesse righe di prova."""
    import numpy as np
    F = np.full(X.shape[0], float(m["base"]))
    for a in m["alberi"]:
        foglia = np.array([not isinstance(n, list) for n in a])
        val = np.array([n if not isinstance(n, list) else 0.0 for n in a], np.float64)
        v = np.array([n[0] if isinstance(n, list) else 0 for n in a]); s = np.array([n[1] if isinstance(n, list) else 0.0 for n in a])
        l = np.array([n[2] if isinstance(n, list) else 0 for n in a]); r = np.array([n[3] if isinstance(n, list) else 0 for n in a])
        pos = np.zeros(X.shape[0], np.int32); attivi = np.arange(X.shape[0])
        while len(attivi):
            p = pos[attivi]; attivi = attivi[~foglia[p]]
            if not len(attivi): break
            p = pos[attivi]
            pos[attivi] = np.where(X[attivi, v[p]] <= s[p], l[p], r[p])
        F += val[pos]
    return F


def conteggio_split(m):
    """Quante volte ogni variabile (per indice) e' usata in un nodo: un'importanza grezza, senza il guadagno."""
    c = {}
    for a in m["alberi"]:
        for n in a:
            if isinstance(n, list): c[n[0]] = c.get(n[0], 0) + 1
    return c


# ======================================================================== la logistica (confronto)
def logistica(X, y, Xv, lam=1.0):
    """Regressione logistica con variabili standardizzate, quadrati delle vite e interazioni col giro. -> (predici, coef)."""
    import numpy as np
    def espandi(X):
        i = {n: k for k, n in enumerate(NOMI)}
        ex = [X, X[:, [i["LU"]]] ** 2, X[:, [i["LO"]]] ** 2, np.minimum(X[:, [i["LU"]]], 5), np.minimum(X[:, [i["LO"]]], 5)]
        for n in ("LU", "LO", "PU", "PO", "MANU", "MANO", "U", "O"):
            ex.append(X[:, [i[n]]] * X[:, [i["N"]]])
        return np.hstack(ex)
    E = espandi(X); mu = E.mean(0); sd = E.std(0) + 1e-9
    Z = np.hstack([np.ones((len(E), 1)), (E - mu) / sd])
    w = np.zeros(Z.shape[1])
    for _ in range(25):  # Newton
        # il pavimento ai pesi: senza, sui dati veri alcune p arrivano a 0 o 1, i pesi diventano subnormali e il prodotto
        # di matrici rallenta di cento volte (12 ott 2026: 15 minuti fermi dove servivano secondi)
        p = 1 / (1 + np.exp(-np.clip(Z @ w, -30, 30))); W = np.maximum(p * (1 - p), 1e-6)
        Hm = (Z * W[:, None]).T @ Z + lam * np.eye(len(w)); gr = Z.T @ (p - y) + lam * w
        w -= np.linalg.solve(Hm, gr)
    Zv = np.hstack([np.ones((len(Xv), 1)), (espandi(Xv) - mu) / sd])
    return Zv @ w


# ======================================================================== i dati
def divisione(n_partite, seme=11):
    """La divisione delle partite, la stessa per ogni strumento (carica, attacco_in_p.meta_prova, carte_in_p):
    -> {set: {tara_draft, prova_draft (codici dei draft), tara_tutti (tutti i gid della meta' di taratura, array),
    gid_tara, gid_prova (le partite estratte per il modello, insiemi)}}. Le estrazioni seguono lo stesso generatore
    nello stesso ordine: cambiarne una cambia tutte le altre."""
    import numpy as np, pandas as pd
    rng = np.random.default_rng(seme); out = {}
    for s in SET:
        P = pd.read_pickle(STILE / f"{s}_partite.pkl", )[["gid", "draft"]]
        drafts = P["draft"].unique()
        lato = pd.Series(rng.random(len(drafts)) < 0.5, index=drafts)
        tara = lato.reindex(P["draft"]).to_numpy()
        d = {"tara_draft": set(lato.index[lato.to_numpy()].tolist()), "prova_draft": set(lato.index[~lato.to_numpy()].tolist()),
             "tara_tutti": P.loc[tara, "gid"].to_numpy()}
        for nome, msk in (("gid_tara", tara), ("gid_prova", ~tara)):
            g = P.loc[msk, "gid"].to_numpy()
            d[nome] = set(rng.choice(g, size=min(n_partite, len(g)), replace=False).tolist())
        out[s] = d
    return out


def carica(n_partite, seme=11, log=print, carte=True):
    """-> dict per meta' ('tara', 'prova'): X, y (vinta), k (tuoi turni per chiudere, solo vinte), set, gid.
    carte: unisce le variabili del valore delle carte (Dati/17lands/stile/<SET>_carte.pkl, Motore/carte_in_p.py);
    senza, quelle colonne restano a 0 (la media del set)."""
    import numpy as np, pandas as pd
    div = divisione(n_partite, seme)
    parti = {"tara": [], "prova": []}
    for s in SET:
        t0 = time.time()
        P = pd.read_pickle(STILE / f"{s}_partite.pkl")
        P["qualita"] = (P["qualita"] - P["qualita"].mean()).fillna(0.0)
        P["bravura"] = P["wr_bucket"].fillna(P["wr_bucket"].median())
        scelte = {"tara": div[s]["gid_tara"], "prova": div[s]["gid_prova"]}
        tutte = scelte["tara"] | scelte["prova"]
        P = P[P["gid"].isin(tutte)].set_index("gid")
        A = pd.read_pickle(STILE / f"{s}_attacco.pkl")
        A = A[A["gid"].isin(tutte)][["gid"] + COL_STATO + ["O_libere"]].copy()
        D = pd.read_pickle(STILE / f"{s}_difesa.pkl")
        D = D[D["gid"].isin(tutte)][["gid"] + COL_STATO + ["U_libere"]].copy()
        # l'ultimo tuo turno giocato: dal dato se la partita sta nei 12 giri, altrimenti il giro finale
        ult = A.groupby("gid")["N"].max()
        P["ultimo_mio"] = np.where(P["turni"] <= NMAX, ult.reindex(P.index).fillna(P["turni"]).to_numpy(), P["turni"])
        A["tocca_me"] = 1; A["tappati_suoi"] = (A["O"] - A["O_libere"]).clip(lower=0); A["tappati_miei"] = 0
        D["tocca_me"] = 0; D["tappati_miei"] = (D["U"] - D["U_libere"]).clip(lower=0); D["tappati_suoi"] = 0
        R = pd.concat([A.drop(columns="O_libere"), D.drop(columns="U_libere")], ignore_index=True)
        if carte:
            fc = STILE / f"{s}_carte.pkl"
            if not fc.exists():
                raise SystemExit(f"manca {fc}: py -I -X utf8 Motore/carte_in_p.py --estrai {s}")
            C = pd.read_pickle(fc)
            C = C[C["gid"].isin(tutte)]
            C["N"] = C["N"].astype(R["N"].dtype); C["tocca_me"] = C["tocca_me"].astype(R["tocca_me"].dtype)
            R = R.merge(C, on=["gid", "tocca_me", "N"], how="left")
            senza = int(R[CARTE[0]].isna().sum())
            if senza: log(f"  {s}: {senza} righe senza le carte (restano a 0)")
            for c in CARTE: R[c] = R[c].fillna(0.0).astype(np.float32)
        else:
            for c in CARTE: R[c] = np.float32(0.0)
        Pj = P.loc[R["gid"]]
        for c in ("on_play", "mull", "opp_mull", "bravura", "qualita"):
            R[c] = Pj[c].to_numpy()
        R["on_play"] = R["on_play"].astype(int)
        y = Pj["won"].to_numpy().astype(float)
        # il tuo prossimo turno: N se tocca a te; se tocca a lui, N+1 quando hai iniziato tu, N quando ha iniziato lui
        prossimo = np.where(R["tocca_me"] == 1, R["N"], R["N"] + R["on_play"])
        k = (Pj["ultimo_mio"].to_numpy() - prossimo + 1).clip(1, 10).astype(float)
        X = R[NOMI].to_numpy(np.float64)
        X[:, NOMI.index("LU")] = X[:, NOMI.index("LU")].clip(0, 30); X[:, NOMI.index("LO")] = X[:, NOMI.index("LO")].clip(0, 30)
        tara = R["gid"].isin(scelte["tara"]).to_numpy()
        for nome, msk in (("tara", tara), ("prova", ~tara)):
            parti[nome].append({"X": X[msk], "y": y[msk], "k": k[msk], "set": np.array([s] * int(msk.sum())),
                                "gid": R["gid"].to_numpy()[msk] + SET.index(s) * 10_000_000})
        log(f"  {s}: {len(tutte)} partite, {len(R)} righe ({time.time() - t0:.0f} s)")
        del A, D, R, P, Pj
    import numpy as np
    return {n: {c: np.concatenate([d[c] for d in v]) for c in v[0]} for n, v in parti.items()}


# ======================================================================== le misure
def misure(p, y):
    import numpy as np
    p = np.clip(p, 1e-6, 1 - 1e-6)
    ll = float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))
    br = float(np.mean((p - y) ** 2))
    from scipy.stats import rankdata
    r = rankdata(p)  # i pari col rango medio: la costante deve dare 0,5
    n1 = y.sum(); n0 = len(y) - n1
    auc = float((r[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))
    return {"log_loss": round(ll, 5), "brier": round(br, 5), "auc": round(auc, 4)}


def calibrazione(p, y, fasce=10):
    import numpy as np
    out = []
    for a in range(fasce):
        m = (p >= a / fasce) & (p < (a + 1) / fasce + (a == fasce - 1))
        if m.sum() >= 100: out.append([round(a / fasce, 1), int(m.sum()), round(float(p[m].mean()), 3), round(float(y[m].mean()), 3)])
    return out


def errore_standard_ll(p, y, gid):
    """-> funzione q -> (log-loss di q meno quella di p, errore standard per cluster di partita: le righe della stessa
    partita non sono indipendenti)."""
    import numpy as np, pandas as pd
    def ll(q):
        q = np.clip(q, 1e-6, 1 - 1e-6)
        return -(y * np.log(q) + (1 - y) * np.log(1 - q))
    lp = ll(p)
    def es(q):
        d = ll(q) - lp; N = len(d); m = d.mean()
        S = pd.DataFrame({"g": gid, "d": d}).groupby("g")["d"].agg(["sum", "count"])
        return round(float(m), 5), round(float(np.sqrt(((S["sum"] - S["count"] * m) ** 2).sum()) / N), 5)
    return es


def tara(n_partite, carte=True):
    import numpy as np, shutil
    t0 = time.time()
    print(f"Carico {n_partite} partite per set e per meta'{' (con le carte)' if carte else ''}...", flush=True)
    D = carica(n_partite, carte=carte)
    T, V = D["tara"], D["prova"]
    # il modello di prima, salvato accanto: il confronto sulle stesse righe di prova si fa con lui, non rifacendolo
    vecchio = None
    if carte and OUT.exists():
        M0 = json.load(open(OUT, encoding="utf-8"))
        if not M0["meta"].get("carte"):
            prima = OUT.with_name("prob_vittoria.senza_carte.json")
            if not prima.exists(): shutil.copy(OUT, prima); shutil.copy(OUT.with_suffix(".misure.json"), prima.with_suffix(".misure.json"))
            vecchio = M0
    print(f"Righe: tara {len(T['y'])}, prova {len(V['y'])}. Vinte: {T['y'].mean():.3f}", flush=True)
    # convalida per l'arresto: il 15% delle partite di taratura
    rng = np.random.default_rng(3)
    gu = np.unique(T["gid"]); cv = set(rng.choice(gu, size=len(gu) // 7, replace=False).tolist())
    mcv = np.isin(T["gid"], list(cv))
    tr = {c: v[~mcv] for c, v in T.items()}; cvd = {c: v[mcv] for c, v in T.items()}
    sig = lambda F: 1 / (1 + np.exp(-F))
    ris = {}
    def salva():
        vince = "boosting" if ris["boosting"]["log_loss"] <= ris.get("logistica", {"log_loss": 9})["log_loss"] else "logistica"
        meta = {"creato": time.strftime("%Y-%m-%d %H:%M"), "fonte": "replay pubblici 17Lands, Premier Draft " + ", ".join(SET),
                "partite_per_set_e_meta": n_partite, "righe_tara": int(len(T["y"])), "righe_prova": int(len(V["y"])),
                "variabili": NOMI, "carte": bool(carte), "difetti_dal_vivo": DIFETTO, "giro_massimo": NMAX, "vince": vince,
                "misure": ris, "secondi": round(time.time() - t0), "grado": "B (Premier di altri set; FRA e Quick da controllare)"}
        json.dump({"meta": meta, "p": bp.a_json(), "turni": bk.a_json()}, open(OUT, "w", encoding="utf-8"), ensure_ascii=False)
        json.dump(meta, open(OUT.with_suffix(".misure.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"Scritto {OUT} ({OUT.stat().st_size // 1024} KB) in {time.time() - t0:.0f} s. Vince: {vince}", flush=True)
    # prima il modello che serve, salvato subito: i confronti vengono dopo (12 ott: una logistica lenta ha fatto perdere 20 minuti)
    # 4. il boosting su tutto
    bp = Boosting(alberi=500, lr=0.15, mono=MONO_P).fit(tr["X"], tr["y"], cvd["X"], cvd["y"], voce="P")
    p_gb = sig(bp.predici_grezzo(V["X"]))
    ris["boosting"] = misure(p_gb, V["y"]); print("  boosting:", ris["boosting"], flush=True)
    # 5. i turni per chiudere, sulle sole vinte
    vt, vc, vv = tr["y"] == 1, cvd["y"] == 1, V["y"] == 1
    bk = Boosting(perdita="quadratica", alberi=400, lr=0.1, mono=MONO_K).fit(tr["X"][vt], tr["k"][vt], cvd["X"][vc], cvd["k"][vc], voce="turni")
    kp = bk.predici_grezzo(V["X"][vv]); kv = V["k"][vv]
    media = float(tr["k"][vt].mean())
    ris["turni_per_chiudere"] = {"errore_medio_assoluto": round(float(np.mean(np.abs(kp - kv))), 3),
                                 "errore_con_la_media": round(float(np.mean(np.abs(media - kv))), 3),
                                 "esatti_arrotondando": round(float(np.mean(np.round(kp) == kv)), 3),
                                 "entro_uno": round(float(np.mean(np.abs(np.round(kp) - kv) <= 1)), 3)}
    print("  turni per chiudere:", ris["turni_per_chiudere"], flush=True)
    salva()
    es = errore_standard_ll(p_gb, V["y"], V["gid"])
    GIRI = ((1, 3), (4, 6), (7, 9), (10, 12))
    giro = lambda a, b: (V["X"][:, 1] >= a) & (V["X"][:, 1] <= b)
    per_giro = lambda p: {f"{a}-{b}": misure(p[giro(a, b)], V["y"][giro(a, b)]) for a, b in GIRI}
    ris["calibrazione_boosting"] = calibrazione(p_gb, V["y"])
    ris["per_set"] = {s: misure(p_gb[V["set"] == s], V["y"][V["set"] == s]) for s in SET}
    ris["per_giro"] = per_giro(p_gb)
    ris["split_per_variabile"] = {NOMI[i]: c for i, c in sorted(conteggio_split(bp.a_json()).items(), key=lambda x: -x[1])}
    if vecchio is not None:
        # il modello senza le carte, sulle stesse righe di prova: la differenza di log-loss con l'errore standard per
        # partita, per giro e per set, e i turni per chiudere (HANDOFF_Spalla_Senso_Di_Partita passo 1, verifica 6)
        k0 = len(vecchio["meta"]["variabili"])
        assert vecchio["meta"]["variabili"] == NOMI[:k0], "il modello vecchio non legge le prime colonne di NOMI"
        p0 = sig(valuta_json_np(vecchio["p"], V["X"][:, :k0]))
        ris["senza_carte"] = misure(p0, V["y"]); print("  senza carte (modello vecchio):", ris["senza_carte"], flush=True)
        ris["differenze_log_loss"] = {"senza_carte_meno_con_carte [diff, es]": es(p0)}
        ris["per_giro_senza_carte"] = per_giro(p0)
        ris["differenza_per_giro [diff, es]"] = {f"{a}-{b}": errore_standard_ll(p_gb[giro(a, b)], V["y"][giro(a, b)], V["gid"][giro(a, b)])(p0[giro(a, b)])
                                               for a, b in GIRI}
        ris["per_set_senza_carte"] = {s: misure(p0[V["set"] == s], V["y"][V["set"] == s]) for s in SET}
        ris["calibrazione_senza_carte"] = calibrazione(p0, V["y"])
        k0p = valuta_json_np(vecchio["turni"], V["X"][vv][:, :k0])
        ris["turni_per_chiudere_senza_carte"] = {"errore_medio_assoluto": round(float(np.mean(np.abs(k0p - kv))), 3),
                                                 "esatti_arrotondando": round(float(np.mean(np.round(k0p) == kv)), 3),
                                                 "entro_uno": round(float(np.mean(np.abs(np.round(k0p) - kv) <= 1)), 3)}
        print("  differenza log-loss senza meno con [diff, es]:", ris["differenze_log_loss"], flush=True)
        print("  per giro:", ris["differenza_per_giro [diff, es]"], flush=True)
    else:
        # 1. le sole vite
        iv = [NOMI.index("LU"), NOMI.index("LO")]
        bv = Boosting(alberi=200, mono=[MONO_P[i] for i in iv]).fit(tr["X"][:, iv], tr["y"], cvd["X"][:, iv], cvd["y"], voce="vite")
        p_vite = sig(bv.predici_grezzo(V["X"][:, iv]))
        ris["solo_vite"] = misure(p_vite, V["y"]); print("  solo vite:", ris["solo_vite"], flush=True)
        # 2. vite, giro, chi tocca, chi ha iniziato
        iv2 = [NOMI.index(n) for n in ("tocca_me", "N", "on_play", "LU", "LO")]
        bv2 = Boosting(alberi=200, mono=[MONO_P[i] for i in iv2]).fit(tr["X"][:, iv2], tr["y"], cvd["X"][:, iv2], cvd["y"], voce="vite+giro")
        p_vite2 = sig(bv2.predici_grezzo(V["X"][:, iv2]))
        ris["vite_giro"] = misure(p_vite2, V["y"]); print("  vite e giro:", ris["vite_giro"], flush=True)
        # 3. la logistica su tutto
        sub = np.random.default_rng(5).random(len(tr["y"])) < min(1.0, 800_000 / len(tr["y"]))
        p_log = sig(logistica(tr["X"][sub], tr["y"][sub], V["X"]))
        ris["logistica"] = misure(p_log, V["y"]); print("  logistica:", ris["logistica"], flush=True)
        ris["differenze_log_loss"] = {"vite_meno_boosting [diff, es]": es(p_vite), "vite_giro_meno_boosting [diff, es]": es(p_vite2),
                                      "logistica_meno_boosting [diff, es]": es(p_log)}
    salva()


# ======================================================================== dal vivo
_M = None


def _modello():
    global _M
    if _M is None:
        _M = json.load(open(OUT, encoding="utf-8"))
    return _M


def riassumi(creature):
    """Creature (dict con p, t, kw come in ev_combattimento) -> numero, forza, costituzione, evasive, volare o raggiungere,
    attaccanti possibili. Le pedine e i segnalini contano con la forza vera."""
    n = p = t = ev = aa = at = 0
    for c in creature:
        kw = {k.lower() for k in (c.get("kw") or ())}
        fp, ft = max(int(c.get("p") or 0), 0), max(int(c.get("t") or 0), 0)
        n += 1; p += fp; t += ft
        ev += bool(kw & {"flying", "menace"} or c.get("imbloccabile"))
        aa += bool(kw & {"flying", "reach"})
        at += fp >= 1 and "defender" not in kw and not c.get("no_attacco")
    return n, p, t, ev, aa, at


def statistiche_gih(valori):
    """GIH centrati (frazione) delle carte che ne hanno uno -> (media, massimo, somma); niente -> 0 (la media del set).
    Lo stesso conto di carte_in_p.statistiche: una cosa, un posto solo per il dato e per il vivo."""
    v = [float(x) for x in valori if x is not None]
    if not v: return (0.0, 0.0, 0.0)
    return (sum(v) / len(v), max(v), sum(v))


_GIH = {}


def gih_nome(nome, set_code=None):
    """Il GIH centrato (frazione, scarto dalla media del set pesata per partite) di una carta dal vivo, dall'anagrafe del
    set (Regole/anagrafe_<SET>.json) coi valori del drafter: anagrafe_carte.valori_17lands, 17Lands del formato che si
    gioca (MAGIC_FORMATO, Quick se manca) portato sulla scala del Premier, con i suoi ripieghi dichiarati (su FRA il solo
    Premier di 17Lands copre 188 carte su 290, i valori del drafter 249). None se il dato non c'e' (pedine, carte senza
    valore): la carta resta fuori dalla media, come nel dato di taratura."""
    if not nome: return None
    try:
        import anagrafe_carte as AN
        s = (set_code or AN.SET).upper()
        if s not in _GIH:
            tab, _ = AN.valori_17lands(s, os.environ.get("MAGIC_FORMATO", "quick").lower())
            con = [(v["wr"], v["n"]) for v in tab.values() if v.get("wr") and v.get("n")]
            tot = sum(n for _, n in con)
            media = sum(w * n for w, n in con) / tot if tot else 55.0
            _GIH[s] = ({k: (v["wr"] - media) / 100.0 for k, v in tab.items() if v.get("wr")}, media)
        tab = _GIH[s][0]
    except Exception:
        return None
    n = nome.lower()
    return tab.get(n, tab.get(n.split(" // ")[0]))


def vettore(stato):
    """stato: dict con tocca_me, N (il giro: turnNumber di Arena diviso 2 arrotondato in su), on_play, LU, LO, miei/suoi
    (liste di creature, ognuna con «gih» centrato o None) oppure i riassunti U, PU, ... , TERU, TERO, MANU, MANO, mull,
    opp_mull, tappati_suoi, tappati_miei; mano_gih (i GIH centrati delle carte non terra in mano, None dove manca).
    Quello che manca prende il difetto."""
    s = dict(DIFETTO); s.update(stato)
    if "miei" in stato:
        s["U"], s["PU"], s["TU"], s["EVU"], s["AAU"], s["UA"] = riassumi(stato["miei"])
        s["GIHU_m"], s["GIHU_max"], s["GIHU_s"] = statistiche_gih(c.get("gih") for c in stato["miei"])
    if "suoi" in stato:
        s["O"], s["PO"], s["TO"], s["EVO"], s["AAO"], s["OA"] = riassumi(stato["suoi"])
        s["GIHO_m"], s["GIHO_max"], s["GIHO_s"] = statistiche_gih(c.get("gih") for c in stato["suoi"])
    if "mano_gih" in stato:
        s["GIHM_m"], s["GIHM_max"], s["GIHM_s"] = statistiche_gih(stato["mano_gih"])
    s["N"] = max(1, min(NMAX, int(s.get("N", 1))))
    s["LU"] = max(0, min(30, s["LU"])); s["LO"] = max(0, min(30, s["LO"]))
    return [float(s.get(n, 0)) for n in NOMI]


def p_vittoria(stato):
    """La probabilita' di vincere la partita da questo tavolo (0-1). Vite a 0: 0 o 1 senza chiedere al modello."""
    if stato.get("LO", 20) <= 0 and stato.get("LU", 20) > 0: return 1.0
    if stato.get("LU", 20) <= 0: return 0.0
    F = valuta_json(_modello()["p"], vettore(stato))
    return 1.0 / (1.0 + math.exp(-F))


def turni_per_chiudere(stato):
    """Quanti tuoi turni mancano alla fine, se la vinci, contando il prossimo tuo (stima, media sulle partite vinte)."""
    if stato.get("LO", 20) <= 0: return 0.0
    return max(1.0, valuta_json(_modello()["turni"], vettore(stato)))


def riga(stato):
    p = p_vittoria(stato); k = turni_per_chiudere(stato)
    return f"vinci {round(100 * p)}% (chiudi in {max(1, round(k))})"


def prova():
    mk = lambda p, t, *kw: {"p": p, "t": t, "kw": set(kw)}
    casi = [("partenza, tocca a te, inizi tu", {"tocca_me": 1, "N": 1, "on_play": 1, "LU": 20, "LO": 20, "MANU": 7, "MANO": 7}),
            ("partenza, tocca a lui, inizia lui", {"tocca_me": 0, "N": 1, "on_play": 0, "LU": 20, "LO": 20, "MANU": 7, "MANO": 7}),
            ("giro 6, pari", {"tocca_me": 1, "N": 6, "on_play": 1, "LU": 15, "LO": 15, "TERU": 6, "TERO": 6, "MANU": 3, "MANO": 3,
                              "miei": [mk(3, 3), mk(2, 2)], "suoi": [mk(3, 3), mk(2, 2)]}),
            ("giro 6, un volante 3/3 in piu'", {"tocca_me": 1, "N": 6, "on_play": 1, "LU": 15, "LO": 15, "TERU": 6, "TERO": 6, "MANU": 3, "MANO": 3,
                              "miei": [mk(3, 3), mk(2, 2), mk(3, 3, "flying")], "suoi": [mk(3, 3), mk(2, 2)]}),
            ("giro 8, lui a 4, tu a 12", {"tocca_me": 1, "N": 8, "on_play": 0, "LU": 12, "LO": 4, "TERU": 7, "TERO": 7, "MANU": 2, "MANO": 2,
                              "miei": [mk(4, 4), mk(2, 1, "flying")], "suoi": [mk(3, 3), mk(1, 4)]}),
            ("giro 8, tu a 4, lui a 12", {"tocca_me": 1, "N": 8, "on_play": 0, "LU": 4, "LO": 12, "TERU": 7, "TERO": 7, "MANU": 2, "MANO": 2,
                              "miei": [mk(3, 3), mk(1, 4)], "suoi": [mk(4, 4), mk(2, 1, "flying")]})]
    for nome, s in casi:
        print(f"  {nome:38s} {riga(s)}")


# ======================================================================== dal log di Arena
def stato_da_arena(st, V, on_play=None):
    """Lo stato per p_vittoria da uno stato del Tracker (tavolo.py). V = vigila_partita. on_play: chi ha iniziato, se
    lo sai (dal turno 1); altrimenti si ricava da chi e' di turno e dal numero del turno."""
    me = st["me"]; avv = 3 - me
    t = st.get("turno") or {}
    tn = int(t.get("turnNumber") or 1); attivo = t.get("activePlayer")
    tocca = 1 if attivo == me else 0
    if on_play is None:
        on_play = 1 if (tn % 2 == 1) == bool(tocca) else 0
    def cre(seat):
        out = []
        for o in V.campo_di(st, seat):
            kw = set(V.parole_oggetto(o))
            # il valore della carta (13 ott 2026): le pedine non ne hanno
            g = None if o.get("type") == "GameObjectType_Token" else gih_nome(V.tavolo.nome(o.get("grpId")))
            out.append({"p": int(o.get("power", {}).get("value") or 0), "t": int(o.get("toughness", {}).get("value") or 0),
                        "kw": kw, "girato": bool(o.get("isTapped")), "gih": g})
        return out
    miei, suoi = cre(me), cre(avv)
    def mano(seat):
        return sum(len(z.get("objectInstanceIds", [])) for z in st["zone"].values()
                   if z.get("type") == "ZoneType_Hand" and z.get("ownerSeatId") == seat)
    mano_gih = [gih_nome(V.tavolo.nome(o.get("grpId"))) for o in V.oggetti(st, "ZoneType_Hand", me)
                if o.get("ownerSeatId") == me and "CardType_Land" not in o.get("cardTypes", [])]
    return {"tocca_me": tocca, "N": math.ceil(tn / 2), "on_play": int(on_play),
            "LU": (st["pl"].get(me) or {}).get("lifeTotal", 20), "LO": (st["pl"].get(avv) or {}).get("lifeTotal", 20),
            "miei": miei, "suoi": suoi, "TERU": V.terre(st, me)[0], "TERO": V.terre(st, avv)[0],
            "MANU": mano(me), "MANO": mano(avv), "mano_gih": mano_gih,
            "tappati_suoi": sum(c["girato"] for c in suoi) if tocca else 0,
            "tappati_miei": 0 if tocca else sum(c["girato"] for c in miei)}


def controllo_fra(evento="QuickDraft_FRA"):
    """Le nostre partite archiviate (Partite/*.json) rilette dai Player.log salvati in Log_Arena/: all'inizio di ogni
    turno la P del modello, alla fine l'esito. Poche partite e righe della stessa partita legate: e' un controllo, non una
    taratura."""
    import glob, re
    import vigila_partita as V
    tracker = V.tavolo.Tracker
    partite = {}
    for f in sorted(glob.glob(str(ROOT / "Partite" / "*.json"))):
        d = json.load(open(f, encoding="utf-8"))
        if evento in (d.get("evento") or "") and d.get("esito") in ("vinta", "persa"):
            partite[d["matchId"]] = (d["esito"] == "vinta", os.path.basename(f))
    logs = sorted(glob.glob(str(ROOT / "Log_Arena" / "*.log")), key=os.path.getmtime)
    dove = {}
    for lp in logs:
        data = open(lp, "rb").read()
        for mid in partite:
            k = data.count(mid.encode())
            if k and k > dove.get(mid, (0, None))[0]: dove[mid] = (k, lp)
        del data
    righe = []
    for mid, (vinta, nome) in partite.items():
        if mid not in dove: print(f"  {nome}: log non archiviato"); continue
        lp = dove[mid][1]
        data = open(lp, "rb").read(); j = data.find(mid.encode()); off = data.rfind(b"\n", 0, j) + 1; del data
        tr = tracker(); visti = set(); primo = None
        with open(lp, "rb") as fh:
            fh.seek(off)
            for b in fh:
                if not tr.feed(b.decode("utf-8", "ignore")) or not tr.stato: continue
                st = tr.stato
                if st["mid"] != mid: break
                t = st.get("turno") or {}; tn = t.get("turnNumber")
                if tn and st.get("me") and tn not in visti and t.get("activePlayer"):
                    visti.add(tn)
                    if primo is None: primo = 1 if t.get("activePlayer") == st["me"] else 0
                    s = stato_da_arena(st, V, on_play=primo if tn >= 1 else None)
                    righe.append((mid, tn, p_vittoria(s), float(vinta)))
                if st.get("fine"): break
        print(f"  {nome}: {len(visti)} turni, {'vinta' if vinta else 'persa'}", flush=True)
    import numpy as np
    if not righe: print("Nessuna riga."); return
    p = np.array([r[2] for r in righe]); y = np.array([r[3] for r in righe])
    base = np.full(len(y), y.mean())
    print(f"\nFRA: {len(set(r[0] for r in righe))} partite, {len(righe)} inizi di turno, vinte {y.mean():.2f} (per turno)")
    print("  modello :", misure(p, y)); print("  costante:", misure(np.clip(base, 1e-6, 1 - 1e-6), y))
    print("  calibrazione [fascia, righe, P media, vinte]:", calibrazione(p, y, 5))
    return {"partite": len(set(r[0] for r in righe)), "righe": len(righe), "modello": misure(p, y),
            "costante": misure(np.clip(base, 1e-6, 1 - 1e-6), y), "calibrazione": calibrazione(p, y, 5)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tara", action="store_true"); ap.add_argument("--partite", type=int, default=20000)
    ap.add_argument("--prova", action="store_true"); ap.add_argument("--fra", action="store_true")
    ap.add_argument("--senza-carte", action="store_true", help="tara il modello di prima, senza il valore delle carte")
    a = ap.parse_args()
    if a.fra:
        r = controllo_fra()
        if r:
            M = json.load(open(OUT, encoding="utf-8")); M["meta"]["controllo_fra"] = r
            json.dump(M, open(OUT, "w", encoding="utf-8"), ensure_ascii=False)
            mm = json.load(open(OUT.with_suffix(".misure.json"), encoding="utf-8")); mm["controllo_fra"] = r
            json.dump(mm, open(OUT.with_suffix(".misure.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        return
    if a.tara: tara(a.partite, carte=not a.senza_carte)
    if a.prova or not a.tara: prova()


if __name__ == "__main__":
    main()
