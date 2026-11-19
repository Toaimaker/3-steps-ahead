"""Il motore dell'EV di nuova generazione, pezzo 2: la mano dell'avversario come distribuzione bayesiana (sessione Magic 22, 19 nov 2026).

Autore, 19 nov 2026: «una distribuzione delle carte possibili nella sua mano: nel Limited dal pool del formato, nel Constructed dalle liste del meta
dell'archetipo riconosciuto; si aggiorna a ogni sua azione e non-azione». Si tiene solo se predice le carte che poi ha rivelato meglio della
distribuzione senza aggiornamento.

Il modello, a ogni suo turno T
  1. il suo mazzo: quante copie di ogni magia (grado C):
     - Standard e gli altri costruiti: la miscela delle liste del meta pesata con la posteriore dell'archetipo dalle sue magie viste fin li'
       (Companion/App/Schede/Meta/hud_mazzo.py: modello, posteriori; «Other» con la frequenza del meta);
     - Limited e mazzi precostruiti: le magie che gli avversari hanno lanciato nelle altre partite dello stesso formato (e dello stesso set nel
       Limited) nei colori che ha mostrato, pesate per quante partite le hanno (una partita non vede mai se stessa: lascia-una-fuori);
     piu' una coda uniforme (EPS) per le carte che il modello non ha.
  2. il resto: le copie meno quelle che ha gia' mostrato (lanciate o in campo).
  3. il prior di ogni carta in mano: proporzionale alle copie rimaste (pescate a caso dal grimorio).
  4. l'aggiornamento dalle non-azioni: per ogni suo turno passato in cui una carta era lanciabile (costo di mana non oltre le sue terre) e non l'ha
     lanciata, la sua probabilita' di stare in mano si moltiplica per (1 - pi), pi la propensione a lanciarla quando puo' (stregonerie e creature nel
     suo turno; istantanei e lampo anche nel tuo turno, col mana che ha lasciato aperto). Il peso conta quanta della mano di allora e' ancora in mano
     (le carte pescate dopo non c'erano). pi si stima sulla meta' delle partite e si prova sull'altra.

La misura (--misura, Note/Motore_EV_Mano.md): a ogni suo turno in cui lancia una magia dalla mano, la probabilita' che il modello dava a quella carta
fra le magie che poteva pagare (log-loss sull'identita'), senza e con l'aggiornamento; e la calibrazione di «la lancia in questo turno» per fascia.
Limite dichiarato: «non l'ha lanciata» puo' essere una scelta (tenerla per dopo): e' proprio cio' che pi misura, in media.

Uso
  py -I -X utf8 Motore_EV/mano_avversaria.py --misura
  py -I -X utf8 Motore_EV/mano_avversaria.py --prova
"""
import os, sys, json, math, argparse, zlib
from pathlib import Path
QUI = Path(__file__).resolve().parent
ROOT = QUI.parent
sys.path.insert(0, str(ROOT / "Companion")); import percorsi  # noqa: E402,F401
for _c in ("Companion/App/Schede/Performance", "Companion/App/Schede/Meta"):
    sys.path.insert(0, str(ROOT / _c))
sys.path.insert(0, str(QUI))

NOTA = ROOT / "Note" / "Motore_EV_Mano.md"
MISURE = QUI / "mano_avversaria.misure.json"
EPS = 0.02          # la coda uniforme: una carta che il modello non ha
PI_DIFETTO = {"sorc": 0.55, "inst": 0.25}


# ---------------------------------------------------------------------------- le carte
def info(g):
    import testi_carte as TC
    c = TC.carta(g)
    if not c:
        return None
    _nm, tipo, ab = TC.testo(g)
    tp = (tipo or "").split(" ")
    return dict(nome=TC.nome(g), cmc=int(c.get("cmc") or 0), terra="Land" in tp and "Creature" not in tp,
                rapida="Instant" in tp or "flash" in (ab or "").lower(), colori=tuple(c.get("colors") or ()))


_INFO = {}


def inf(g):
    v = _INFO.get(g)
    if v is None and g not in _INFO:
        v = _INFO[g] = info(g)
    return v


# ---------------------------------------------------------------------------- le partite
def partite():
    """-> [dict(id, formato, set, seat, lui, colori (lettere mostrate), eventi per turno)] dalle partite dei log con le azioni."""
    import dati_analizzatore as DA
    import matchup_log as ML
    out = []
    for x in DA.righe():
        d = DA._MANA.get(x["partita"]) or {}
        if not d.get("azioni") or x.get("seat") not in (1, 2):
            continue
        fmt = ML.formato(x.get("evento"))
        if not fmt:
            continue
        lui = 3 - x["seat"]
        m = __import__("re").search(r"_([A-Z0-9]{3})_", x.get("evento") or "")
        out.append(dict(id=x["partita"], formato=fmt, set=m.group(1) if m else "", seat=x["seat"], lui=lui, evento=x.get("evento") or "",
                        azioni=d["azioni"], fine=d.get("fine") or [], foto=d.get("foto") or []))
    return out


def lanci_suoi(p):
    """{turno: [grpId delle sue magie lanciate]} (le terre no)."""
    out = {}
    for a in p["azioni"]:
        if a[1] == p["lui"] and a[2] == "magia" and a[3]:
            g = a[3]; i = inf(g)
            if i and not i["terra"]:
                out.setdefault(a[0], []).append(g)
    return out


# ---------------------------------------------------------------------------- il mazzo
def pool_empirico(tutte):
    """{(formato, set): {grpId: [partite]}} delle magie lanciate dagli avversari, per il lascia-una-fuori."""
    out = {}
    for p in tutte:
        k = (p["formato"], p["set"] if p["formato"] == "limited" else "")
        for g in {g for v in lanci_suoi(p).values() for g in v}:
            out.setdefault(k, {}).setdefault(g, set()).add(p["id"])
    return out


def mazzo(p, visti, pool, n_partite_fmt):
    """{grpId: copie attese nel suo mazzo} (solo magie). visti: le sue magie gia' mostrate."""
    k = (p["formato"], p["set"] if p["formato"] == "limited" else "")
    colori = {c for g in visti for c in (inf(g) or {}).get("colori", ())}
    out = {}
    if p["formato"] == "standard":
        try:
            out = _da_meta(visti)
        except Exception:       # noqa: BLE001 - senza il meta, il solo pool empirico
            out = {}
    # il pool empirico (anche nello Standard, insieme al meta: 19 nov 2026, la meta' dei suoi lanci nella coda Play non stava in nessuna lista del meta)
    P = pool.get(k, {})
    n = max(1, n_partite_fmt.get(k, 1) - 1)
    for g, ids in P.items():
        c = len(ids - {p["id"]})
        if not c:
            continue
        cg = set((inf(g) or {}).get("colori", ()))
        if colori and cg and not cg <= colori and len(colori) >= 2:
            continue
        out[g] = out.get(g, 0.0) + 1.0 + 3.0 * c / n         # da una a quattro copie, secondo quanto spesso compare (grado C)
    return out


_META = {}


def _da_meta(visti):
    import hud_mazzo as HM
    import testi_carte as TC
    mod = _META.get("m") or _META.setdefault("m", HM.modello("standard"))
    nomi = [TC.nome(g) for g in visti if TC.nome(g)]
    post = HM.posteriori(nomi, mod)
    pv = dict(post)
    out = {}
    for a in mod["archetipi"]:
        w = pv.get(a["nome"], 0)
        if w < 0.005:
            continue
        for c, q in a["lista"].items():
            g = TC.per_nome(a["nomi"].get(c, c))
            if g:
                out[g] = out.get(g, 0) + w * q
    w_o = pv.get("Other", 0)
    if w_o:
        for c, f in mod["pop"].items():
            g = TC.per_nome(c)
            if g:
                out[g] = out.get(g, 0) + w_o * 2.0 * f
    return out


# ---------------------------------------------------------------------------- il conto turno per turno
def turni_suoi(p):
    return sorted({a[0] for a in p["azioni"] if a[1] == p["lui"]} | {f[0] for f in p["fine"] if f[1] == p["lui"]})


def credenza(p, T, pool, nfmt, pi=None, aggiorna=True):
    """Prima del suo turno T: (pesi {grpId: peso}, copie rimaste, terre a T). pesi proporzionali a P(in mano) per copia."""
    pi = pi or PI_DIFETTO
    L = lanci_suoi(p)
    visti = [g for t in sorted(L) if t < T for g in L[t]]
    D = mazzo(p, visti, pool, nfmt)
    import collections
    usati = collections.Counter(visti)
    rest = {g: max(0.0, c - usati.get(g, 0)) for g, c in D.items()}
    rest = {g: c for g, c in rest.items() if c > 0}
    terre_turno = {f[0]: (f[2], f[3]) for f in p["fine"] if f[1] == p["lui"]}     # suo turno: (stappate a fine turno, terre)
    terre_mio = {f[0]: (f[2], f[3]) for f in p["fine"] if f[1] != p["lui"]}       # mio turno: (sue stappate? no: mie) -> serve la sua foto
    peso = {}
    for g, c in rest.items():
        w = 1.0
        if aggiorna:
            i = inf(g) or {}
            for t in sorted(terre_turno):
                if t >= T:
                    break
                stap, ter = terre_turno[t]
                if g in L.get(t, []):
                    continue
                # lanciabile nel suo turno t: costo non oltre le terre (le stappate a fine turno ci dicono che aveva mana in piu')
                if i.get("cmc", 99) <= ter:
                    lasciate = stap >= i.get("cmc", 99)
                    pp = pi["sorc"] if not i.get("rapida") else pi["inst"]
                    if lasciate:            # aveva il mana e l'ha lasciato aperto: la non-azione pesa di piu'
                        pp = min(0.95, pp * 1.4)
                    w *= (1 - pp) ** _esposizione(p, t, T)
        peso[g] = c * w
    return peso, rest, terre_turno


def _esposizione(p, t, T):
    """Quanto del suo turno t pesa ancora prima di T: le carte pescate dopo t non c'erano. Grado C: un turno vale 1, piu' indietro meno (0,8 a turno)."""
    giri = sum(1 for f in p["fine"] if f[1] == p["lui"] and t < f[0] < T)
    return 0.8 ** giri


def q_lancio(peso, rest, terre, eps=EPS):
    """La distribuzione dell'identita' della magia che lancia fra quelle che paga con le sue terre: {grpId: q}, piu' la coda."""
    cand = {g: w for g, w in peso.items() if (inf(g) or {}).get("cmc", 99) <= terre}
    s = sum(cand.values())
    return {g: (1 - eps) * w / s for g, w in cand.items()} if s > 0 else {}


_POOL = {}


def valuta(tutte, pi=None, aggiorna=True, solo=None):
    """-> dict(ll (media -log q sui lanci veri), n, coperti, calibrazione [(P, y)]) sulle partite tutte (o solo quelle con id in solo)."""
    import collections
    k_ = id(tutte)
    if _POOL.get("k") != k_:
        _POOL.update(k=k_, pool=pool_empirico(tutte),
                     nfmt=collections.Counter((p["formato"], p["set"] if p["formato"] == "limited" else "") for p in tutte))
    pool, nfmt = _POOL["pool"], _POOL["nfmt"]
    ll, n, coperti = 0.0, 0, 0
    cal = []
    for p in tutte:
        if solo is not None and p["id"] not in solo:
            continue
        L = lanci_suoi(p)
        fine_suo = {f[0]: f for f in p["fine"] if f[1] == p["lui"]}
        for T in turni_suoi(p):
            if T not in fine_suo:
                continue
            ter = fine_suo[T][3]
            peso, rest, _ = credenza(p, T, pool, nfmt, pi, aggiorna)
            q = q_lancio(peso, rest, ter)
            if not q:
                continue
            univ = max(50, len(q))
            for g in L.get(T, []):
                pr = q.get(g)
                if pr is None:
                    pr = EPS / univ
                else:
                    coperti += 1
                ll += -math.log(pr); n += 1
            # calibrazione: P(la lancia in T) ~ q * (magie lanciate in T)
            k = len(L.get(T, []))
            if k:
                for g, pr in q.items():
                    cal.append((min(1.0, pr * k), 1.0 if g in L.get(T, []) else 0.0))
    return dict(ll=round(ll / max(n, 1), 4), n=n, coperti=round(coperti / max(n, 1), 3), cal=cal)


def tara_pi(tutte, solo):
    """La propensione pi (stregonerie, istantanei) che minimizza la log-loss sulle partite solo: griglia."""
    best = None
    for ps in (0.2, 0.45, 0.7):
        for pi_ in (0.05, 0.2, 0.4):
            r = valuta(tutte, {"sorc": ps, "inst": pi_}, True, solo)
            if best is None or r["ll"] < best[0]:
                best = (r["ll"], {"sorc": ps, "inst": pi_})
    return best[1]


def calibrazione(cal, fasce=(0, 0.05, 0.1, 0.2, 0.35, 0.5, 0.75, 1.01)):
    out = []
    for a, b in zip(fasce, fasce[1:]):
        v = [(p, y) for p, y in cal if a <= p < b]
        if v:
            out.append([f"{int(a * 100)}-{int(min(b, 1) * 100)}%", len(v), round(100 * sum(p for p, _ in v) / len(v), 1), round(100 * sum(y for _, y in v) / len(v), 1)])
    return out


def misura():
    tutte = partite()
    lato = {p["id"]: zlib.crc32(p["id"].encode()) & 1 for p in tutte}
    res = {}
    for nome, sel in (("tutte", lambda p: True), ("Constructed (standard)", lambda p: p["formato"] == "standard"),
                      ("precostruiti", lambda p: p["formato"] == "precon"), ("Limited", lambda p: p["formato"] == "limited")):
        sub = [p for p in tutte if sel(p)]
        if not sub:
            continue
        # pi tarata su una meta', provata sull'altra (e viceversa)
        r_senza = {"ll": 0, "n": 0}; r_con = {"ll": 0, "n": 0}; cal_s, cal_c = [], []; pis = []
        for s in (0, 1):
            tr = {p["id"] for p in sub if lato[p["id"]] != s}; te = {p["id"] for p in sub if lato[p["id"]] == s}
            pi = tara_pi(tutte, tr); pis.append(pi)
            a = valuta(tutte, None, False, te); b = valuta(tutte, pi, True, te)
            for r, x in ((r_senza, a), (r_con, b)):
                r["ll"] += x["ll"] * x["n"]; r["n"] += x["n"]
            cal_s += a["cal"]; cal_c += b["cal"]
        res[nome] = dict(partite=len(sub), lanci=r_con["n"], ll_senza=round(r_senza["ll"] / max(r_senza["n"], 1), 4),
                         ll_con=round(r_con["ll"] / max(r_con["n"], 1), 4), pi=pis, cal_senza=calibrazione(cal_s), cal_con=calibrazione(cal_c))
        print(nome, {k: v for k, v in res[nome].items() if not k.startswith("cal")}, flush=True)
    MISURE.write_text(json.dumps(res, indent=1, ensure_ascii=False), encoding="utf8")
    L = ["# Il pezzo 2: la mano dell'avversario, bayesiana", "", "Generato da `py -I -X utf8 Motore_EV/mano_avversaria.py --misura` (sessione Magic 22). "
         "A ogni suo turno in cui lancia una magia, la probabilita' che il modello dava a quella carta fra le magie che poteva pagare (log-loss "
         "sull'identita', piu' bassa e' meglio): senza aggiornamento (le copie rimaste) e con le non-azioni dei suoi turni passati. La propensione pi "
         "e' tarata su una meta' delle partite e provata sull'altra.", "",
         "| partite | n | lanci | log-loss senza | log-loss con | pi (meta' A, meta' B) |", "|---|---|---|---|---|---|"]
    for k, v in res.items():
        L.append(f"| {k} | {v['partite']} | {v['lanci']} | {v['ll_senza']} | {v['ll_con']} | {v['pi']} |")
    for k, v in res.items():
        L += ["", f"## {k}: calibrazione di «la lancia in questo turno»", "", "| fascia | coppie | P senza | vero | | P con | vero |", "|---|---|---|---|---|---|---|"]
        cs = {a: (b, c, d) for a, b, c, d in v["cal_senza"]}
        for a, b, c, d in v["cal_con"]:
            s = cs.get(a, ("", "", ""))
            L.append(f"| {a} | {b} | {s[1]} | {s[2]} | | {c} | {d} |")
    NOTA.write_text("\n".join(L) + "\n", encoding="utf8")
    return res


def prova():
    ok = tot = 0

    def chk(c, m):
        nonlocal ok, tot
        tot += 1; ok += bool(c); print(("OK   " if c else "ROSSO") + " " + m, flush=True)
    import testi_carte as TC
    a = TC.per_nome("Ajani's Pridemate"); b = TC.per_nome("Shock") or TC.per_nome("Opt")
    # partita finta: lui ha Pridemate e Shock nel pool; al suo turno 2 aveva 2 terre e non ha lanciato Pridemate (costo 2)
    p = dict(id="finta", formato="precon", set="", seat=1, lui=2, evento="x", foto=[],
             azioni=[[2, 2, "terra", 1, "L"], [4, 2, "terra", 1, "L"], [6, 2, "terra", 1, "L"]],
             fine=[[2, 2, 0, 2], [4, 2, 2, 2], [6, 2, 0, 3]])
    pool = {("precon", ""): {a: {"x1", "x2"}, b: {"x1", "x2"}}}
    nf = {("precon", ""): 3}
    w0, _r, _t = credenza(p, 6, pool, nf, aggiorna=False)
    w1, _r, _t = credenza(p, 6, pool, nf, aggiorna=True)
    chk(abs(w0[a] - w0[b]) < 1e-9, "senza aggiornamento le due carte valgono uguale (stesse copie)")
    chk(w1[a] < w0[a], "la non-azione: 2 terre al suo turno 4 e niente Pridemate, la sua P scende")
    chk(w1[a] / w1[b] < 1, "dopo la non-azione Pridemate pesa meno di Shock (che in parte e' istantaneo e meno propenso)")
    # negativa: se l'ha lanciata, non conta come non-azione
    p2 = dict(p, azioni=p["azioni"] + [[4, 2, "magia", a, "C"]])
    w2, r2, _t = credenza(p2, 6, pool, nf, aggiorna=True)
    chk(r2.get(a, 0) < _r.get(a, 99), "negativa: la carta lanciata esce dalle copie rimaste")
    q = q_lancio(w1, _r, 1)
    chk(a not in q, "una magia da 2 con una sola terra non entra fra quelle che puo' lanciare")
    # sui log: l'aggiornamento non deve peggiorare, e il modello rimescolato deve fare peggio
    tutte = partite()
    chk(len(tutte) > 300, f"partite dei log con le azioni: {len(tutte)}")
    sub = {p["id"] for p in tutte if p["formato"] != "limited"}
    r = valuta(tutte, None, False, sub)
    chk(r["n"] > 500 and r["coperti"] > 0.3, f"lanci misurati {r['n']}, coperti dal modello {r['coperti']}")
    import random
    random.seed(1)
    finte = [dict(t, azioni=[[a_[0], a_[1], a_[2], (random.choice(list(_INFO)) if a_[2] == "magia" and a_[1] == t["lui"] and _INFO else a_[3]), a_[4]]
                             for a_ in t["azioni"]]) for t in tutte]
    rf = valuta(finte, None, False, sub)
    chk(rf["ll"] > r["ll"] + 0.3, f"negativa: magie a caso al posto delle sue, la log-loss sale ({rf['ll']} > {r['ll']})")
    print(f"{ok}/{tot}")
    return ok == tot


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--misura", action="store_true"); ap.add_argument("--prova", action="store_true")
    a = ap.parse_args()
    if a.misura:
        misura()
    if a.prova:
        sys.exit(0 if prova() else 1)
