"""Decodifica dei deckstring di Untapped (formato 'AAQAAQ...'): base64url -> varint; header [0,4,0,1];
poi gruppi per quantita' (1 copia, 2 copie, ...): [n, id1, delta2, delta3...]. Gli id sono i titleId di Arena
(mtgajson cards.json), non i grpId: scoperto il 22 set 2026 dopo tre ipotesi sbagliate.
Cache dei titleId in Collezione/arena_titleid_cache.json (7 giorni).
"""
import os, sys; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); import percorsi  # la casa del Companion: i percorsi stanno in Companion/percorsi.py (13 ott 2026)
import os, json, base64, time, urllib.request
ROOT = percorsi.ROOT
CACHE = os.path.join(ROOT, "Collezione", "arena_titleid_cache.json")
UA = {"User-Agent": "companion-magic-arena/1.0", "Accept": "application/json"}

def _titoli(forza=False):
    if not forza and os.path.exists(CACHE) and time.time() - os.path.getmtime(CACHE) < 7 * 86400:
        return json.load(open(CACHE, encoding="utf-8"))
    try:
        import ssl, certifi; ctx = ssl.create_default_context(cafile=certifi.where())
    except Exception:
        ctx = None
    def get(u): return json.load(urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=60, context=ctx))
    cards = get("https://mtgajson.untapped.gg/v1/latest/cards.json"); loc = get("https://mtgajson.untapped.gg/v1/latest/loc_en.json")
    L = {e["id"]: e["text"] for e in loc}
    t = {str(c["titleId"]): L.get(c["titleId"], "?") for c in cards}
    json.dump(t, open(CACHE, "w", encoding="utf-8"), ensure_ascii=False)
    return t
TITOLI = _titoli()


def aggiorna_titoli():
    """Riscarica i titleId subito (le carte ribilanciate di Alchemy prendono id nuovi, 13 ott 2026): per chi scarica
    liste di oggi, come Motore/meta_formati.py. Aggiorna TITOLI sul posto."""
    TITOLI.update(_titoli(forza=True))

def varints(b):
    out = []; i = 0
    while i < len(b):
        v = 0; s = 0
        while True:
            c = b[i]; i += 1; v |= (c & 0x7f) << s; s += 7
            if not c & 0x80: break
        out.append(v)
    return out

def decodifica(ds, nomi=True):
    """-> {nome carta: copie} (o {titleId: copie} con nomi=False). Le carte fuori dal mazzo in decodifica.comandanti
    (il comandante del Brawl) e decodifica.compagni (il compagno, es. Yorion).
    L'intestazione e' [0, 4, n carte di zona, (id, zona) per carta, 1]: Standard [0,4,0,1], Brawl [0,4,1,id,1,1]. La sideboard in decodifica.side.
    Zona 1 = comandante, 2 = compagno: dedotto il 18 ott 2026 dalle liste di Untapped (Brawl: 99 carte piu' il comandante
    in tutte le 111 liste; Explorer: Yorion, Sky Nomad con zona 2 in liste da 80 carte)."""
    v = varints(base64.urlsafe_b64decode(ds + "=" * (-len(ds) % 4)))
    nc = v[2] if len(v) > 2 else 0
    zona = {v[3 + 2 * k]: v[4 + 2 * k] for k in range(nc) if 4 + 2 * k < len(v)}
    i = 4 + 2 * nc
    def gruppi():
        nonlocal i
        out = {}
        for qty in range(1, 5):              # quattro fasce: 1, 2, 3, 4 copie (id assoluto, poi delta)
            if i >= len(v):
                break
            n = v[i]; i += 1; last = 0
            for k in range(n):
                if i >= len(v):
                    break
                last = v[i] if k == 0 else last + v[i]; i += 1
                out[last] = qty
        if i < len(v):                       # fuori fascia: coppie (copie, id), es. 20 Plains; l'id come nelle fasce:
            n = v[i]; i += 1; last = 0       # assoluto il primo, poi delta (18 ott 2026: «6 Plains, 6 Swamp» = (6,648),(6,5))
            for k in range(n):
                if i + 1 >= len(v):
                    break
                last = v[i + 1] if k == 0 else last + v[i + 1]
                out[last] = v[i]; i += 2
        return out
    main = gruppi()
    # dopo il mazzo ogni sezione comincia col suo numero: l'1 in fondo all'intestazione e' quello del mazzo, 2 e' la sideboard, 0 la fine (6 nov 2026: senza saltarlo la sideboard
    # si leggeva spostata di uno, e «2, 1, 1113257» diventava due carte inesistenti, «title1» e «title1113258»)
    side = {}
    if i < len(v) and v[i] == 2:
        i += 1
        side = gruppi()
    conv = (lambda d: d) if not nomi else (lambda d: {TITOLI.get(str(t), f"title{t}"): q for t, q in d.items()})
    decodifica.side = conv(side)
    decodifica.comandanti = conv({k: 1 for k, z in zona.items() if z == 1})
    decodifica.compagni = conv({k: 1 for k, z in zona.items() if z != 1})
    return conv(main)

def prova():
    """Le stringhe costruite a mano: col mazzo solo, con la sideboard, e la lettura di prima (senza saltare il numero della sezione) che deve dare carte diverse."""
    def scrivi(nums):
        b = bytearray()
        for x in nums:
            while True:
                c = x & 0x7f; x >>= 7
                b.append(c | (0x80 if x else 0))
                if not x:
                    break
        return base64.urlsafe_b64encode(bytes(b)).decode().rstrip("=")
    solo = decodifica(scrivi([0, 4, 0, 1, 1, 100, 0, 0, 0, 0]), nomi=False), dict(decodifica.side)
    con = scrivi([0, 4, 0, 1, 1, 100, 0, 0, 0, 0, 2, 1, 1113257, 1, 500, 0, 0, 0, 0])
    m_, s_ = decodifica(con, nomi=False), dict(decodifica.side)
    finale_2 = decodifica(scrivi([0, 4, 0, 1, 0, 0, 0, 0, 1, 21, 1250, 2, 2, 2221, 229, 0, 0, 0, 0, 0]), nomi=False), dict(decodifica.side)
    casi = [("senza sideboard", solo == ({100: 1}, {})), ("il mazzo non cambia con la sideboard", m_ == {100: 1}), ("la sideboard: una copia e due copie", s_ == {1113257: 1, 500: 2}),
            ("id assoluto, poi delta", finale_2 == ({1250: 21}, {2221: 1, 2450: 1})), ("prova negativa: senza saltare il 2 e' un'altra lista", s_ != {1: 1, 1113258: 1})]
    for nome, ok in casi:
        print("  ok   " if ok else "  ROSSO", nome)
    print(f"{sum(ok for _, ok in casi)}/{len(casi)}")
    return 0 if all(ok for _, ok in casi) else 1


if __name__ == "__main__":
    import sys
    if "--prova" in sys.argv:
        sys.exit(prova())
    for ds in sys.argv[1:]:
        print(decodifica(ds))
