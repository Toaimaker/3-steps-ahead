"""Il motore dell'EV di nuova generazione, pezzo 1: il testo di ogni carta come vettore di partenza (sessione Magic 22, 19 nov 2026).

Ogni carta di Arena (id grpId: lo stesso dei replay di 17Lands e del Player.log) diventa un vettore sparso di caratteristiche lette dal database
delle carte di Arena (Companion/App/Comune/db_carte.py, sola lettura): le parole e le coppie di parole del testo delle abilita' e della riga del tipo
(il nome della carta diventa «~»), hashate in BUCKET caselle; costo di mana, forza, costituzione, colori, tipi, rarita', pedina. Le facce collegate
(avventure, presagi, carte a due facce) entrano con mezzo peso. La rete del pezzo 1 (valuta_carte.py) impara una proiezione da questo vettore a un
vettore piccolo (la «posizione» della carta), piu' una correzione sua per le carte che ha visto giocare: cosi' una carta di un set nuovo ha un valore
dal suo testo dal primo giorno.

Uso
  py -I -X utf8 Motore_EV/testi_carte.py "Nome o grpId"     le parole e i numeri di una carta
  py -I -X utf8 Motore_EV/testi_carte.py --prova
"""
import os, sys, re, zlib, math
from pathlib import Path
QUI = Path(__file__).resolve().parent
ROOT = QUI.parent
sys.path.insert(0, str(ROOT / "Companion")); import percorsi  # noqa: E402,F401
sys.path.insert(0, str(ROOT / "Companion" / "App" / "Comune"))

BUCKET = 2048
TIPI = ["Creature", "Land", "Artifact", "Enchantment", "Planeswalker", "Instant", "Sorcery", "Battle"]
NUM = 3 + 5 + len(TIPI) + 5 + 2       # cmc, forza, costituzione; colori; tipi; rarita' 0-4 (bucket); pedina, numero di abilita'
DIM = BUCKET + NUM
_TOK = re.compile(r"\{[^}]+\}|[+-]?\d+/[+-]?\d+|[+-]?\d+|[a-z]+(?:'[a-z]+)?")
_D = {}


def _db():
    if not _D:
        import db_carte
        _D["carte"] = {c["grpid"]: c for c in db_carte.carte()}
        _D["testi"] = db_carte.testi()
        _D["per_nome"] = {}
        for g, c in _D["carte"].items():
            n = _D["testi"].get(c.get("titleId"))
            if n and not c.get("isToken"):
                _D["per_nome"].setdefault(n.lower(), g)
    return _D


def carta(g):
    return _db()["carte"].get(int(g))


def nome(g):
    c = carta(g)
    return _db()["testi"].get(c.get("titleId")) if c else None


def per_nome(n):
    return _db()["per_nome"].get((n or "").lower())


def testo(g):
    """(nome, riga del tipo, testo delle abilita') di una carta."""
    D = _db(); c = carta(g)
    if not c:
        return None, "", ""
    T = D["testi"]
    nm = T.get(c.get("titleId")) or ""
    tipo = " ".join(x for x in (T.get(c.get("cardTypeTextId")), T.get(c.get("subtypeTextId"))) if x)
    ab = " ".join(T.get(a.get("TextId")) or "" for a in c.get("abilities") or [])
    return nm, tipo, ab


def parole(g):
    nm, tipo, ab = testo(g)
    t = (ab or "")
    if nm:
        t = t.replace(nm, "~")
        t = t.replace(nm.split(",")[0], "~")
    t = re.sub(r"<[^>]+>", " ", t.lower())
    tok = _TOK.findall(t) + ["T:" + w for w in _TOK.findall((tipo or "").lower())]
    return tok


def _h(s):
    return zlib.crc32(s.encode("utf8")) % BUCKET


def caratteristiche(g, peso=1.0, con_facce=True):
    """-> dict {indice: valore} del vettore sparso della carta (DIM caselle)."""
    c = carta(g)
    out = {}
    if not c:
        return out
    tok = parole(g)
    if tok:
        w = peso / math.sqrt(len(tok) + len(tok) - 1)
        for a in tok:
            out[_h(a)] = out.get(_h(a), 0.0) + w
        for a, b in zip(tok, tok[1:]):
            k = _h(a + " " + b); out[k] = out.get(k, 0.0) + w
    nm, tipo, _ab = testo(g)
    base = BUCKET

    def num(v):
        try:
            return float(v)
        except (TypeError, ValueError):
            return 0.0
    out[base + 0] = out.get(base + 0, 0) + peso * num(c.get("cmc")) / 6
    out[base + 1] = out.get(base + 1, 0) + peso * num(c.get("power")) / 5
    out[base + 2] = out.get(base + 2, 0) + peso * num(c.get("toughness")) / 5
    for col in c.get("colors") or []:
        if 1 <= col <= 5:
            out[base + 2 + col] = out.get(base + 2 + col, 0) + peso
    for i, tp in enumerate(TIPI):
        if tp in (tipo or "").split(" "):
            out[base + 8 + i] = out.get(base + 8 + i, 0) + peso
    r = int(c.get("rarity") or 0)
    out[base + 8 + len(TIPI) + min(max(r - 1, 0), 4)] = out.get(base + 8 + len(TIPI) + min(max(r - 1, 0), 4), 0) + peso
    out[base + 13 + len(TIPI)] = peso * (1.0 if c.get("isToken") else 0.0)
    out[base + 14 + len(TIPI)] = peso * len(c.get("abilities") or []) / 5
    if con_facce:
        for f in c.get("linkedFaces") or []:
            for k, v in caratteristiche(f, 0.5 * peso, con_facce=False).items():
                out[k] = out.get(k, 0.0) + v
    return out


def matrice(grpids):
    """-> scipy.sparse.csr_matrix (len(grpids) x DIM) delle caratteristiche, una riga per carta (una carta sconosciuta: riga vuota)."""
    import numpy as np
    from scipy import sparse
    r, cidx, v = [], [], []
    for i, g in enumerate(grpids):
        for k, x in caratteristiche(g).items():
            if x:
                r.append(i); cidx.append(k); v.append(x)
    return sparse.csr_matrix((np.array(v, np.float32), (np.array(r), np.array(cidx))), shape=(len(grpids), DIM))


def e_terra(g):
    _nm, tipo, _ab = testo(g)
    return "Land" in (tipo or "").split(" ") and "Creature" not in (tipo or "").split(" ")


def e_creatura(g):
    _nm, tipo, _ab = testo(g)
    return "Creature" in (tipo or "").split(" ")


def prova():
    ok = tot = 0

    def chk(c, m):
        nonlocal ok, tot
        tot += 1; ok += bool(c); print(("OK   " if c else "ROSSO") + " " + m)
    g = 103373  # Bofur, Reliable Guardian (HOB): lifelink, avventura collegata
    nm, tipo, ab = testo(g)
    chk(nm.startswith("Bofur") and "Creature" in tipo, f"testo dal database di Arena: {nm} / {tipo}")
    f = caratteristiche(g)
    chk(f.get(BUCKET + 8 + TIPI.index("Creature"), 0) > 0, "la creatura ha la casella del tipo")
    chk(_h("lifelink") in f, "la parola chiave lifelink e' nel vettore")
    chk(_h("hexproof") in f, "la faccia collegata (avventura: hexproof) entra")
    senza = caratteristiche(g, con_facce=False)
    chk(_h("hexproof") not in senza, "negativa: senza le facce collegate l'avventura non c'e'")
    chk(caratteristiche(-5) == {}, "negativa: una carta che non esiste da' un vettore vuoto")
    gp = per_nome("Ajani's Pridemate")
    chk(gp is not None and "counter" in parole(gp) and "T:creature" in parole(gp), "le parole del testo e della riga del tipo (Ajani's Pridemate)")
    M = matrice([g, -5])
    chk(M.shape == (2, DIM) and M[1].nnz == 0 and M[0].nnz > 5, "la matrice: una riga per carta")
    print(f"{ok}/{tot}")
    return ok == tot


if __name__ == "__main__":
    a = sys.argv[1:]
    if a and a[0] == "--prova":
        sys.exit(0 if prova() else 1)
    if a:
        g = int(a[0]) if a[0].isdigit() else per_nome(a[0])
        print(g, testo(g)); print(parole(g)); print(len(caratteristiche(g)), "caselle")
