"""I dati della scheda Meta: i formati e i mazzi piu' giocati di ognuno."""
import json
import os

import capsule as CAP
import prezzi_carte as PZ

from ambiente import ROOT
from dati_app import BASI, _meta_formato, collezione, collezione_nota, craft, jolly, rarita_nome, url_untapped


FORMATI_META = (("Standard", "arena"), ("Alchemy", "arena"), ("Explorer", "arena"), ("Historic", "arena"), ("Timeless", "arena"), ("Brawl", "arena"),
                ("Pioneer", "carta"), ("Modern", "carta"), ("Legacy", "carta"), ("Vintage", "carta"), ("Pauper", "carta"))
QUANTI_META = 30


def meta_mazzi(fmt):
    """I mazzi del meta di un formato, per la pagina Meta: (mazzi per quota, sottotitolo). I formati di Arena da Untapped (meta_formato), quelli di carta e
    di MTGO da MTGGoldfish (Note/meta_goldfish_<formato>.json, Motore/meta_goldfish_formati.py). Ogni mazzo ha lista, sideboard se c'e', prezzo e tix."""
    coll, _ = collezione()
    if dict(FORMATI_META).get(fmt) == "arena":
        mm, sotto = _meta_formato(fmt, QUANTI_META)
        for x in mm:
            x["url"] = url_untapped(fmt, x)
    else:
        p = os.path.join(ROOT, "Note", f"meta_goldfish_{fmt.lower()}.json")
        try:
            with open(p, encoding="utf-8") as f:
                d = json.load(f)
        except (OSError, ValueError):
            return [], ""
        info = d.get("carte") or {}
        CAP.aggiungi({n: (v.get("costo") or "", v.get("colori") or "", v.get("cmc"), "") for n, v in info.items()})
        mm = [x for x in (d.get("archetipi") or []) if x.get("lista")][:QUANTI_META]
        for x in mm:
            x["carte_info"] = {n: info[n] for z in (x["lista"], x.get("side") or {}) for n in z if n in info}
            x["su_arena"] = sum(q for n, q in x["lista"].items() if n in BASI or rarita_nome(n))       # le copie di carte che esistono anche su Arena
            x["possedute"] = sum(min(q, coll.get(n, 0)) for n, q in x["lista"].items() if n not in BASI) + sum(q for n, q in x["lista"].items() if n in BASI)
        sotto = f"tournaments · {d.get('scaricato', '')[8:10]}/{d.get('scaricato', '')[5:7]}"
    out = []
    jl, _q = jolly()
    for i, x in enumerate(sorted(mm, key=lambda z: -(z.get("quota") or 0))):
        x = dict(x)
        x["quota"] = float(x.get("quota") or 0)
        x["carte"] = x.get("carte") or sum((x.get("lista") or {}).values())
        tutte = dict(x.get("lista") or {})
        for z in ("comandante", "compagno"):
            for n, q in (x.get(z) or {}).items():
                tutte[n] = tutte.get(n, 0) + q
        x["eur"], _usd, x["senza_prezzo"] = PZ.totale(tutte)
        x["manca"], x["si"] = craft(tutte, coll, jl) if collezione_nota() else (None, None)      # i jolly che servono (nei formati di carta: per le carte che
        # ci sono su Arena); senza la collezione (l'app pubblica senza Untapped) non si sanno
        x["jl"] = jl
        voci = [(q, n) for n, q in {**(x.get("comandante") or {}), **(x.get("lista") or {})}.items()]
        x["arte"] = (x.get("chiave") or [None])[0] if x.get("chiave") else CAP.copertina(voci)
        x["posto"] = i + 1
        x["formato"] = fmt
        out.append(x)
    return out, sotto
