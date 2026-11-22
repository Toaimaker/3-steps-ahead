"""I due voti di una tua scelta nel replayer (sessione Magic 22, 19 nov 2026): contro la migliore alternativa (pezzo 3, IS-MCTS) e contro i giocatori
forti (pezzo 4). Autore, 19 nov 2026: «ogni scelta riceve due voti»; il mockup approvato con «vai in ordine tutto».

  - La migliore alternativa: dal pilota dell'IS-MCTS (Motore_EV/ismcts_pilota.json), per partita (le prime 8 cifre del matchId), turno di Arena e
    tipo (agisci: la prima azione della prima fase principale; attacca; blocca). Solo dove il pilota e' passato; altrimenti niente.
  - I giocatori forti: la cella dello Specchio di ogni tuo attacco e blocco, letta dai momenti di combattimento di mana_aperto (le stesse definizioni di
    Motore/specchio.py: giro, chi comincia, attaccanti possibili, suoi bloccanti stappati, forza in campo, vite, sue terre aperte; per la difesa i tuoi
    bloccanti, le sue creature, gli attaccanti, la forza dell'attacco contro la tua costituzione, il letale), e il voto dalle celle dei forti
    (forti_celle.json). Le celle sono del Premier di 17Lands (limited): nel Constructed e' un'estrapolazione, e la riga lo dice.

Uso dal codice: voti.della_scelta(x, t, testo) -> dict(linea=..., forti=...) (ognuno None se manca).
  py -I -X utf8 Motore_EV/voti.py --prova
"""
import os, sys, json
from pathlib import Path
QUI = Path(__file__).resolve().parent
sys.path.insert(0, str(QUI))

PILOTA = QUI.parent / "Log_Arena" / "ismcts.json"     # il registro dell'IS-MCTS (ismcts.giro), fuori da git
VECCHIO = QUI / "ismcts_pilota.json"
_P = {}


def _pilota():
    f = PILOTA if PILOTA.exists() else VECCHIO
    try:
        m = f.stat().st_mtime
    except OSError:
        return {}
    if _P.get("m") != m:
        try:
            d = json.loads(f.read_text(encoding="utf8"))
        except (OSError, ValueError):
            d = {"punti": []}
        idx = {}
        for r in d.get("punti") or []:
            idx[(r["gid"].rsplit("_", 1)[-1][:8], r.get("turno"), r["tipo"])] = r
        _P.update(m=m, idx=idx)
    return _P["idx"]


def linea(match_id, t, tipo):
    """-> dict(scarto, vera, migliore, p, meglio, stessa) o None. tipo: agisci, attacca, blocca."""
    r = _pilota().get(((match_id or "")[:8], t, tipo))
    if not r:
        return None
    return dict(scarto=r["scarto"], vera=r["candidate"][r["vera"]], migliore=r["candidate"][r["migliore"]], p=r["p"],
                meglio=r["meglio"] and not r.get("altro_ordine"), altro_ordine=bool(r.get("altro_ordine")),
                stessa=r["vera"] == r["migliore"], mondi=max(int(v) for v in r["mondi"].values()), contro=r.get("contro") or {})


def _r(x, q):
    return int(max(-2, min(2, round(x / q))))


def _lato(f, s):
    lati = (f or {}).get("c") or [[], []]
    return lati[s - 1] if len(lati) >= s else []


def decisioni(x):
    """{(turno di Arena, 'attacco'|'difesa'): dict(tipo, cella, scelta)} dai momenti di combattimento della partita x (posto dell'Hero)."""
    sys.path.insert(0, str(QUI.parent / "Companion")); import percorsi  # noqa: F401
    import dati_analizzatore as DA
    d = DA._MANA.get(x.get("partita")) or {}
    seat = x.get("seat")
    if seat not in (1, 2) or x.get("inizia") is None:
        return {}
    lui = 3 - seat
    fine = {t: f for t, _a, f in d.get("foto") or []}
    out = {}
    conta = {}
    for m in d.get("momenti") or []:
        if m[0] != "comb" or len(m) < 5 or not m[4]:
            continue
        t, f, info = m[1], m[3], m[4]
        att = m[2] if isinstance(m[2], int) else (seat if (t % 2 == 1) == bool(x["inizia"]) else lui)
        prima = fine.get(t - 1) or d.get("mano0") or {}
        v = prima.get("v") or [20, 20]
        LU, LO = (v[seat - 1] or 20), (v[lui - 1] or 20)
        mie = [c for c in _lato(prima, seat) if len(c) >= 5 and c[3] is not None]
        sue = [c for c in _lato(prima, lui) if len(c) >= 5 and c[3] is not None]
        PU, PO = sum(max(0, c[3] or 0) for c in mie), sum(max(0, c[3] or 0) for c in sue)
        TU = sum(max(0, c[4] or 0) for c in mie)
        giro = (t + 1) // 2
        n_att = len(info.get("att") or [])
        if att == seat:
            pot = int(info.get("pot") or 0)
            if pot < 1:
                continue
            ol = sum(1 for c in _lato(f, lui) if len(c) >= 5 and c[3] is not None and not c[1])
            scelta = "nessuno" if n_att == 0 else ("tutti" if n_att >= pot else "parte")
            cella = dict(N=giro, on_play=bool(x["inizia"]), Ub=min(max(pot, 1), 4), Ol=min(ol, 4), dP=_r(PU - PO, 3), dv=_r(LU - LO, 5),
                         ap=0 if (info.get("aperte") or 0) < 2 else (1 if (info.get("aperte") or 0) < 4 else 2))
            out[(t, "attacco")] = dict(tipo="attacco", cella=cella, scelta=scelta)
        else:
            ul = sum(1 for c in _lato(f, seat) if len(c) >= 5 and c[3] is not None and not c[1])
            if ul < 1 or n_att < 1:
                continue
            ids_att = {a[0] for a in info.get("att") or []}
            forza_att = sum(max(0, c[3] or 0) for c in _lato(f, lui) if len(c) > 5 and c[5] in ids_att and c[3] is not None)
            cella = dict(N=giro, on_play=bool(x["inizia"]), Ul=min(max(ul, 1), 4), Ob=min(max(len(sue), 1), 4), ab=min(n_att, 4),
                         dP=_r(forza_att - TU, 3), dv=_r(LU - LO, 5), letale=int(forza_att >= LU))
            out[(t, "difesa")] = dict(tipo="difesa", cella=cella, scelta="blocca" if info.get("blocchi") else "non blocca")
        conta[t] = 1
    return out


CELLE = QUI / "forti_celle.json"
_J = {}


def voto_forti(decisione):
    """Il voto dei forti dalle celle (forti_celle.json, scritto da forti.py --json): dict(come_te, piu_comune, quote, n, livello) o None."""
    if "j" not in _J:
        try:
            _J["j"] = json.loads(CELLE.read_text(encoding="utf8"))
        except (OSError, ValueError):
            _J["j"] = None
    J = _J["j"]
    if not J:
        return None
    T = J["attacco" if decisione["tipo"] == "attacco" else "difesa"]
    for lv, L in enumerate(T["livelli"]):
        k = "|".join(str(int(decisione["cella"][c])) for c in L["chiavi"])
        r = L["celle"].get(k)
        if r is None:
            continue
        n = r[-1]
        if decisione["tipo"] == "attacco":
            q = {c: r[i] / n for i, c in enumerate(T["colonne"])}
        else:
            q = {"blocca": r[0] / n, "non blocca": 1 - r[0] / n}
        return dict(come_te=round(100 * q.get(decisione["scelta"], 0.0), 1), piu_comune=max(q, key=q.get),
                    quote={kk: round(100 * v, 1) for kk, v in q.items()}, n=n, livello=lv)
    return None


_D = {}


def della_scelta(x, t, testo):
    """I due voti della riga di una tua scelta (testo del voto per fase) nel turno t di Arena della partita x."""
    tl = (testo or "").lower()
    tipo_p = "attacca" if "attack" in tl else ("blocca" if "block" in tl else "agisci")
    out = {"linea": linea(x.get("partita"), t, tipo_p), "forti": None, "constructed": x.get("tipo") == "Constructed"}
    if tipo_p in ("attacca", "blocca"):
        k = x.get("partita")
        if k not in _D:
            try:
                _D[k] = decisioni(x)
            except Exception:       # noqa: BLE001 - senza i momenti niente voto dei forti
                _D[k] = {}
        dec = _D[k].get((t, "attacco" if tipo_p == "attacca" else "difesa"))
        if dec:
            out["forti"] = voto_forti(dec)
            if out["forti"]:
                out["forti"]["scelta"] = dec["scelta"]
    return out


def inglese(mossa):
    """Una mossa del motore (in italiano, come la scrive confronto_log.scrivi_mossa) nella lingua dell'app."""
    m = mossa or ""
    for it, en in (("attacca con nessuno", "no attack"), ("blocca nessuno", "no block"), ("passa", "pass"), ("attacca con ", "attack with "),
                   ("lancia ", "cast "), ("attiva ", "activate "), ("terra ", "play land ")):
        if m == it or m.startswith(it):
            return en + m[len(it):] if m != it else en
    if m.startswith("blocca "):
        return "block " + m[len("blocca "):].replace(" con ", " with ")
    return m


TESTO_FORTI = {"nessuno": "most hold back", "parte": "most attack with some", "tutti": "most attack with all", "blocca": "most block",
               "non blocca": "most don't block"}


def prova():
    ok = tot = 0

    def chk(c, m):
        nonlocal ok, tot
        tot += 1; ok += bool(c); print(("OK   " if c else "ROSSO") + " " + m, flush=True)
    idx = _pilota()
    chk(len(idx) > 30, f"il pilota indicizzato: {len(idx)} punti")
    l = linea("d6b4a7f6-c0b0-4d2f", 20, "agisci")
    chk(l is not None and not l["stessa"] and "Theorist" in l["migliore"], f"Delumi T20: la migliore e' il potere di The Theorist ({l and l['migliore']})")
    chk(linea("zzzzzzzz", 20, "agisci") is None, "negativa: una partita che il pilota non ha non ha voto")
    # una partita finta: Hero attacca con 1 su 1 possibili contro nessun bloccante
    sys.path.insert(0, str(QUI.parent / "Companion")); import percorsi  # noqa: F401
    sys.path.insert(0, str(QUI.parent / "Companion" / "App" / "Schede" / "Performance"))
    import dati_analizzatore as DA
    cr = lambda i, p, tap=0: [100 + i, tap, 0, p, p, i]
    DA._MANA["finta_voti"] = dict(foto=[[4, 2, dict(c=[[cr(1, 3)], []], v=[20, 20])]],
                                  momenti=[["comb", 5, 1, dict(c=[[cr(1, 3)], []], v=[20, 20]), dict(att=[[1, 2]], blocchi=[], pot=1, aperte=0)]])
    x = dict(partita="finta_voti", seat=1, inizia=True, tipo="Limited")
    dec = decisioni(x)
    chk((5, "attacco") in dec and dec[(5, "attacco")]["scelta"] == "tutti" and dec[(5, "attacco")]["cella"]["Ub"] == 1,
        f"la cella dell'attacco dai momenti: {dec.get((5, 'attacco'))}")
    v = della_scelta(x, 5, "You attacked with Bear")
    chk(v["forti"] is not None and v["forti"]["come_te"] > 50, f"i forti attaccano anche loro: {v['forti'] and v['forti']['come_te']}%")
    DA._MANA["finta_voti"]["momenti"][0][4]["att"] = []
    _D.clear()
    v2 = della_scelta(x, 5, "You attacked with nothing")
    chk(v2["forti"] is not None and v2["forti"]["come_te"] < 50, "negativa: restare fermi nella stessa cella e' una scelta di minoranza fra i forti")
    DA._MANA.pop("finta_voti", None)
    print(f"{ok}/{tot}")
    return ok == tot


if __name__ == "__main__":
    if "--prova" in sys.argv:
        sys.exit(0 if prova() else 1)
