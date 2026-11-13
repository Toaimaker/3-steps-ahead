"""Scrive un deckstring nel formato di Untapped (quello che Companion/Comune/deckstring.py legge), per le partite lette dal nostro log (10 nov 2026, Autore: «Si,
passa al log»: le schede leggono le partite nel formato di Untapped, e le partite del log ci arrivano scritte cosi'). Il lettore e' blindato: qui si scrive soltanto.

Il formato (dal lettore): base64url di varint; intestazione [0, 4, n carte di zona, (titleId, zona)..., 1]; quattro fasce per 1, 2, 3, 4 copie [n, id assoluto, delta...];
la fascia fuori misura [n, (copie, id assoluto poi delta)...]; la sideboard comincia con 2 e ha le stesse fasce; 0 alla fine. Gli id sono i titleId di Arena, non i grpId:
`titoli()` porta i grpId del log ai titleId col database delle carte sul disco (Dati/untapped/arena_cards/cards.json).

    py -I -X utf8 Companion/App/Comune/deckstring_scrivi.py --prova     ogni deckstring di Untapped sul disco, letto, riscritto e riletto: uguale
"""
import os, sys
_casa = os.path.dirname(os.path.abspath(__file__))      # si sale fino a percorsi.py, che mette nel sys.path tutte le cartelle del Companion
while not os.path.isfile(os.path.join(_casa, "percorsi.py")):
    _casa = os.path.dirname(_casa)
if _casa not in sys.path:
    sys.path.insert(0, _casa)
import percorsi  # noqa: E402
import base64
import json

F_CARTE = os.path.join(percorsi.ROOT, "Dati", "untapped", "arena_cards", "cards.json")
_T, _COL = {}, {}
COLORI = {1: "W", 2: "U", 3: "B", 4: "R", 5: "G"}
BIT = {"W": 1, "U": 2, "B": 4, "R": 8, "G": 16}


def _varint(n):
    out = bytearray()
    while True:
        b = n & 0x7f
        n >>= 7
        if n:
            out.append(b | 0x80)
        else:
            out.append(b)
            return bytes(out)


def _fasce(d):
    """{titleId: copie} -> i varint delle quattro fasce e della fascia fuori misura."""
    out = []
    for q in range(1, 5):
        ids = sorted(t for t, c in d.items() if c == q)
        out.append(len(ids))
        prima = 0
        for k, t in enumerate(ids):
            out.append(t if k == 0 else t - prima)
            prima = t
    fuori = sorted((t, c) for t, c in d.items() if c > 4)
    out.append(len(fuori))
    prima = 0
    for k, (t, c) in enumerate(fuori):
        out += [c, t if k == 0 else t - prima]
        prima = t
    return out


def codifica(main, side=None, comandanti=None, compagni=None):
    """{titleId: copie} (e la sideboard, i comandanti, i compagni) -> il deckstring."""
    zona = [(t, 1) for t in sorted(comandanti or {})] + [(t, 2) for t in sorted(compagni or {})]
    v = [0, 4, len(zona)]
    for t, z in zona:
        v += [t, z]
    v.append(1)
    v += _fasce({t: q for t, q in main.items() if q > 0})
    if side:
        v.append(2)
        v += _fasce({t: q for t, q in side.items() if q > 0})
    v.append(0)
    return base64.urlsafe_b64encode(b"".join(_varint(x) for x in v)).decode().rstrip("=")


def titoli():
    """{grpId: titleId} dal database delle carte di Arena sul disco (letto una volta)."""
    if not _T:
        try:
            import db_carte         # il database di Arena letto una volta per processo, ridotto e cotto (11 nov 2026)
            for c in db_carte.carte():
                if c.get("titleId") is not None:
                    _T[c["grpid"]] = c["titleId"]
                _COL[c["grpid"]] = "".join(COLORI[k] for k in c.get("colors") or () if k in COLORI)
        except (OSError, ValueError):
            pass
    return _T


def colori(grp):
    """I colori (WUBRG, in ordine) delle carte coi grpId dati: le terre non hanno colore."""
    titoli()
    tutti = {k for g in grp for k in _COL.get(g, "")}
    return "".join(k for k in "WUBRG" if k in tutti)


def bit(col):
    """«WU» -> il numero a bit dei colori di Untapped (W 1, U 2, B 4, R 8, G 16)."""
    return sum(BIT[k] for k in col)


def da_grp(grp):
    """[grpId, ...] (anche ripetuti) -> {titleId: copie}; i grpId che il database non conosce restano fuori."""
    t = titoli()
    out = {}
    for g in grp:
        if g in t:
            out[t[g]] = out.get(t[g], 0) + 1
    return out


def prova():
    from deckstring import decodifica
    import account as _ACC
    p = _ACC.percorso("untapped_partite_cache.json")
    stringhe = set()
    try:
        cache = json.load(open(p, encoding="utf-8"))
    except (OSError, ValueError):
        cache = {}
    for v in cache.values():
        for g in v.get("partite") or []:
            stringhe.add(g.get("friendly_deckstring") or "")
            for gg in g.get("games") or []:
                stringhe.update(gg.get("player_opening_hands") or [])
                stringhe.update(gg.get("opponent_revealed_deckstrings") or [])
    stringhe.discard("")
    uguali = 0
    for s in stringhe:
        m = decodifica(s, nomi=False)
        sd, cm, cp = dict(decodifica.side), dict(decodifica.comandanti), dict(decodifica.compagni)
        r = codifica(m, sd, cm, cp)
        m2 = decodifica(r, nomi=False)
        if (m2, decodifica.side, decodifica.comandanti, decodifica.compagni) == (m, sd, cm, cp):
            uguali += 1
    casi = [(f"ogni deckstring di Untapped riletto dopo la riscrittura: {uguali}/{len(stringhe)}", stringhe and uguali == len(stringhe))]
    d = {100: 4, 7: 1, 9: 1, 50: 20, 51: 3}
    casi.append(("un mazzo con fascia fuori misura, sideboard e comandante", decodifica(codifica(d, {3: 2}, {999: 1}), nomi=False) == d and decodifica.side == {3: 2}
                 and decodifica.comandanti == {999: 1}))
    casi.append(("negativa: un mazzo diverso da' una stringa diversa", codifica(d) != codifica({**d, 100: 3})))
    t = titoli()
    casi.append(("i grpId del log ai titleId", len(t) > 10000 and da_grp([next(iter(t))] * 2) == {t[next(iter(t))]: 2}))
    ok = sum(1 for _n, v in casi if v)
    for n, v in casi:
        print(("ok    " if v else "ROSSO ") + n)
    print(f"{ok}/{len(casi)}")
    return ok == len(casi)


if __name__ == "__main__":
    if "--prova" in sys.argv:
        sys.exit(0 if prova() else 1)
    print(__doc__)
