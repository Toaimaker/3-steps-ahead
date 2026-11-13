"""L'analisi di un mazzo dalle sue partite vere (Autore, 10 nov 2026: «aggiungiamo una sezione di analisi: aiutiamo a migliorare i mazzi elencando le carte piu' giocate
in win rate e quelle che fanno fatica a entrare in partita e le carte piu' viste in loss games e le combinazioni di carte che hanno reso la partita ingiocabile, serve un
tool che permetta di fare analisi vera del mazzo»).

Da dove vengono i dati: solo dai nostri log, mai da Untapped (Autore, stesso giorno: «questi dati devono venire dal nostro log non da untapped»). Le partite del mazzo
sono quelle del Player.log e dei log archiviati (partite_log.py: il mazzo scelto per quell'evento, per id; le copie dei Dual Color Precons tornano al mazzo di Arena con
dati_app.mazzo_di_arena), con l'esito del log, fuori dai limited; le carte di ogni partita vengono dalla sua scheda di Partite/ (archivio_partite.py, dal Player.log, dal
22 set 2026), agganciata per matchId. Una partita senza scheda, o con un esito che non torna, non entra nell'analisi. Le due facce di una carta sono la stessa carta
(«Unholy Annex» e «Unholy Annex // Ritual Chamber»). Di ogni partita si usano:
- «vista»: una tua carta uscita dal grimorio (mano, campo, cimitero, esilio: `mio_mazzo_visto`). Comprende le carte macinate o messe al cimitero con surveil: non sono
  tutte pescate. Si contano solo le carte della lista del mazzo (niente pedine);
- «lanciata»: lanciata da te (evento «lancia»), o giocata se e' una terra;
- «bloccata»: vista e mai lanciata in quella partita;
- le carte viste dell'avversario (`sue_carte_viste`, fuori da grimorio e mano), senza le terre.

Cosa esce (ogni lista al massimo 5 righe, una carta per nome, non per copia; le terre non entrano mai):
- migliori: le tue carte col win rate piu' alto nelle partite in cui le hai lanciate (almeno 3 partite), contro il win rate del mazzo nelle stesse partite;
- fatica: le carte rimaste in mano piu' spesso (bloccate su viste, almeno 3 partite viste), col win rate delle partite in cui sono rimaste bloccate;
- nelle perse: le tue carte col win rate piu' basso quando escono (almeno 3 partite viste, almeno 2 perse, sotto il mazzo);
- le sue: le carte dell'avversario che ti costano piu' sconfitte di quelle che il mazzo perde comunque (perse meno partite viste per la quota di sconfitte del mazzo;
  almeno 2 perse), con quante volte le hai viste e la quota di sconfitte;
- combo: due sue carte viste insieme in almeno 3 partite, che perdi almeno nel 75% delle volte (e 15 punti piu' del mazzo) e almeno 10 punti piu' di ognuna delle due
  da sola (se no e' una carta forte con una compagna qualsiasi); e due tue carte rimaste bloccate insieme, ordinate per sconfitte in piu' dell'atteso, in almeno 2
  sconfitte (la mano che non si gioca).
Il win rate e' contato, non stimato; la classifica usa (v + 1) / (n + 2), che non premia un 2-0. Con poche partite sono indizi: la finestra lo dice.

    py -I -X utf8 Companion/App/Schede/Your_decks/analisi_mazzo.py --prova
    py -I -X utf8 Companion/App/Schede/Your_decks/analisi_mazzo.py "Nome del mazzo"     (l'analisi di un tuo mazzo di Arena, a testo)
"""
import os, sys
_casa = os.path.dirname(os.path.abspath(__file__))      # si sale fino a percorsi.py, che mette nel sys.path tutte le cartelle del Companion
while not os.path.isfile(os.path.join(_casa, "percorsi.py")):
    _casa = os.path.dirname(_casa)
if _casa not in sys.path:
    sys.path.insert(0, _casa)
import percorsi  # noqa: E402
import collections
import datetime
import glob
import itertools
import json
import re

RADICE = percorsi.ROOT
BASI = {"Plains", "Island", "Swamp", "Mountain", "Forest", "Wastes", "Snow-Covered Plains", "Snow-Covered Island", "Snow-Covered Swamp", "Snow-Covered Mountain",
        "Snow-Covered Forest"}
MIN_VISTE, MIN_LANCIATE, MIN_COMBO, QUOTA_COMBO, RIGHE = 3, 3, 3, 0.75, 5
POCHE = 15          # sotto: «indizi, non dati» nella finestra
_C = {"chiave": None, "d": {}}


def faccia(n):
    """Il nome di una carta senza la seconda faccia: Arena scrive a volte l'una, a volte l'intera."""
    return n.split(" // ")[0].strip()


def carte_partite(cartella=None):
    """{matchId: dict(esito, viste, lanciate, sue)} dalle schede di Partite/, rilette solo quando cambiano. I nomi senza la seconda faccia."""
    file = glob.glob(os.path.join(cartella or os.path.join(RADICE, "Partite"), "*.json"))
    chiave = (cartella, len(file), max((os.path.getmtime(f) for f in file[-5:]), default=0))
    if chiave != _C["chiave"]:
        d = {}
        for f in file:
            try:
                s = json.load(open(f, encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if not s.get("matchId") or s.get("esito") not in ("vinta", "persa"):
                continue
            mie = {faccia(e["carta"]) for e in s.get("eventi") or () if e.get("chi") == "io" and e.get("tipo") in ("lancia", "terra") and e.get("carta")}
            d[s["matchId"]] = dict(esito=s["esito"], viste={faccia(n) for n in s.get("mio_mazzo_visto") or ()}, lanciate=mie,
                                   sue={faccia(n) for n in s.get("sue_carte_viste") or () if n not in BASI})
        _C.update(chiave=chiave, d=d)
    return _C["d"]


def partite_mazzo(id_mazzo):
    """Le partite del mazzo dal Player.log e dai log archiviati: [dict(matchId, vinta, quando, primo)], finite, fuori dai limited. primo: True se l'hai
    cominciata tu (on the play), False se l'avversario, None se il log non lo dice (10 nov 2026: il filtro play/draw della finestra del mazzo)."""
    from dati_app import mazzi_arena_o_niente, mazzo_di_arena, partite_dal_log
    pl, nomi = partite_dal_log()
    rimappa = mazzo_di_arena(mazzi_arena_o_niente(), nomi)
    return [dict(matchId=p["matchId"], vinta=bool(p["vinta"]), quando=datetime.datetime.fromtimestamp(p["inizio"] / 1000),
                 primo=(p["inizia"] == p["seat"]) if p.get("inizia") is not None and p.get("seat") is not None else None) for p in pl
            if p.get("vinta") is not None and p.get("mazzo") and rimappa(p["mazzo"]) == id_mazzo and not re.search(r"Draft|Sealed|Cube", p.get("evento") or "")]


def aggancia(p, idx):
    """La scheda della partita p, per matchId; None se non c'e' o se l'esito non torna."""
    s = idx.get(p.get("matchId"))
    return s if s and (s["esito"] == "vinta") == bool(p["vinta"]) else None


def _wr(v, n):
    return v / n if n else 0.0


def _stima(v, n):
    return (v + 1) / (n + 2)


def analizza(partite, lista, e_terra=lambda n: False, idx=None, righe=None):
    """partite: quelle del mazzo (dict con matchId e vinta: partite_mazzo); lista: {nome: copie} del mazzo (main, comandante, sideboard).
    -> dict(n, con_dati, wr, migliori, fatica, perse, sue, combo_sue, combo_mie); ogni lista di dict con nome (o coppia), numeri e wr."""
    idx = carte_partite() if idx is None else idx
    RIGHE = righe or globals()["RIGHE"]         # la finestra dettagliata (12 nov 2026) chiede le liste intere
    intero = {faccia(n): n for n in lista}        # nella finestra le carte del mazzo hanno il nome della lista
    terra_ = e_terra

    def e_terra(n):
        return terra_(intero.get(n, n)) or terra_(n)
    giochi = []
    for p in partite:
        s = aggancia(p, idx)
        if s is None:
            continue
        viste = {n for n in s["viste"] if n in intero}
        lanc = {n for n in s["lanciate"] if n in intero}
        giochi.append(dict(vinta=bool(p["vinta"]), viste=viste | lanc, lanciate=lanc, bloccate=viste - lanc, sue={n for n in s["sue"] if not e_terra(n)}))     # le sue terre no
    out = dict(n=len(partite), con_dati=len(giochi), wr=None, migliori=[], fatica=[], perse=[], sue=[], combo_sue=[], combo_mie=[])
    if not giochi:
        return out
    wr = _wr(sum(g["vinta"] for g in giochi), len(giochi))
    out["wr"] = wr
    st = collections.defaultdict(lambda: dict(nv=0, vv=0, nl=0, vl=0, nb=0, vb=0))
    for g in giochi:
        for n in g["viste"]:
            a = st[n]; a["nv"] += 1; a["vv"] += g["vinta"]
        for n in g["lanciate"]:
            a = st[n]; a["nl"] += 1; a["vl"] += g["vinta"]
        for n in g["bloccate"]:
            a = st[n]; a["nb"] += 1; a["vb"] += g["vinta"]
    magie = {n: a for n, a in st.items() if not e_terra(n) and n not in BASI}
    out["migliori"] = [dict(nome=n, v=a["vl"], n=a["nl"], wr=_wr(a["vl"], a["nl"]), delta=_wr(a["vl"], a["nl"]) - wr)
                       for n, a in sorted(magie.items(), key=lambda z: (-_stima(z[1]["vl"], z[1]["nl"]), -z[1]["nl"], z[0])) if a["nl"] >= MIN_LANCIATE][:RIGHE]
    out["fatica"] = [dict(nome=n, bloccata=a["nb"], viste=a["nv"], quota=a["nb"] / a["nv"], v=a["vb"], wr=_wr(a["vb"], a["nb"]))
                     for n, a in sorted(magie.items(), key=lambda z: (-z[1]["nb"] / max(z[1]["nv"], 1), -z[1]["nb"], z[0])) if a["nv"] >= MIN_VISTE and a["nb"]][:RIGHE]
    out["perse"] = [dict(nome=n, perse=a["nv"] - a["vv"], v=a["vv"], n=a["nv"], wr=_wr(a["vv"], a["nv"]), delta=_wr(a["vv"], a["nv"]) - wr)
                    for n, a in sorted(magie.items(), key=lambda z: (_stima(z[1]["vv"], z[1]["nv"]), -(z[1]["nv"] - z[1]["vv"]), z[0]))
                    if a["nv"] >= MIN_VISTE and a["nv"] - a["vv"] >= 2 and _wr(a["vv"], a["nv"]) < wr][:RIGHE]
    for k in ("migliori", "fatica", "perse"):
        for x in out[k]:
            x["nome"] = intero.get(x["nome"], x["nome"])
    # ogni carta, per la scheda in hover della finestra del mazzo (12 nov 2026, Autore: «l'hover sulle carte dovrebbe dare i meta dati accanto o sotto la carta
    # in merito al suo comportamento in partita in quel mazzo»): viste, lanciate, rimaste in mano, con le vinte di ognuna
    out["carte"] = {intero.get(n, n): dict(a) for n, a in st.items()}
    loro = collections.defaultdict(lambda: [0, 0])     # nome -> [partite viste, perse]
    for g in giochi:
        for n in g["sue"]:
            loro[n][0] += 1; loro[n][1] += not g["vinta"]

    def attese(n_, p_):
        """Le sconfitte in piu' di quelle che il mazzo perde comunque: una carta che c'e' sempre non conta."""
        return p_ - n_ * (1 - wr)
    out["sue"] = [dict(nome=n, perse=p_, n=n_, quota=p_ / n_, extra=attese(n_, p_)) for n, (n_, p_) in sorted(loro.items(), key=lambda z: (-attese(*z[1]), -z[1][1], z[0]))
                  if p_ >= 2 and p_ / n_ > 1 - wr][:RIGHE]
    coppie = collections.defaultdict(lambda: [0, 0])
    for g in giochi:
        for c in itertools.combinations(sorted(g["sue"]), 2):
            coppie[c][0] += 1; coppie[c][1] += not g["vinta"]
    soglia = max(QUOTA_COMBO, (1 - wr) + 0.15)
    q1 = {n: p_ / n_ for n, (n_, p_) in loro.items()}
    cand = [(c, n_, p_) for c, (n_, p_) in coppie.items() if n_ >= MIN_COMBO and p_ / n_ >= soglia and p_ / n_ >= max(q1[c[0]], q1[c[1]]) + 0.1]      # insieme perdono piu'
    # di ognuna da sola: se no e' una carta forte con una compagna qualsiasi
    cand.sort(key=lambda z: (-z[2], -z[2] / z[1], z[0]))
    usate = set()
    for c, n_, p_ in cand:        # una carta che vince da sola non riempie la lista con tutte le sue coppie
        if c[0] in usate and c[1] in usate:
            continue
        usate |= set(c)
        out["combo_sue"].append(dict(carte=c, perse=p_, n=n_, quota=p_ / n_))
        if len(out["combo_sue"]) == RIGHE:
            break
    mie = collections.defaultdict(lambda: [0, 0])        # coppia rimasta in mano insieme -> [partite, perse]
    for g in giochi:
        for c in itertools.combinations(sorted(n for n in g["bloccate"] if not e_terra(n) and n not in BASI), 2):
            mie[c][0] += 1; mie[c][1] += not g["vinta"]
    usate = set()
    for c, (n_, p_) in sorted(mie.items(), key=lambda z: (-attese(*z[1]), -z[1][1], z[0])):     # le sconfitte in piu' dell'atteso, come per le sue carte
        if p_ < 2 or p_ / n_ <= 1 - wr:
            continue
        if c[0] in usate and c[1] in usate:
            continue
        usate |= set(c)
        out["combo_mie"].append(dict(carte=tuple(intero.get(x, x) for x in c), perse=p_, n=n_, quota=p_ / n_))
        if len(out["combo_mie"]) == RIGHE:
            break
    return out


def prova():
    """Partite finte con un esito noto: le liste trovano quello che c'e' e non quello che non c'e'."""
    import random
    rnd = random.Random(1)
    t0 = datetime.datetime(2026, 10, 1, 12, 0)
    idx, pp = {}, []
    lista = {"Asso // Retro": 4, "Mattone": 4, "Neutra": 4, "Neutra2": 4, "Plains": 20, "Terra Doppia": 4}     # l'Asso ha due facce: il log scrive la prima
    for i in range(40):
        asso = i % 2 == 0                       # l'Asso lanciato: si vince sempre
        mattone = i % 3 == 0 and not asso       # il Mattone: visto e mai lanciato, e si perde
        insieme = i % 4 == 1                    # le carte sue che fanno perdere, insieme; da sole (con l'Asso) si vince
        drago, fiamma = insieme or i % 8 == 2, insieme or i % 8 == 6
        vinta = asso or (not insieme and not mattone and i % 5 == 0)
        viste = {"Neutra", "Plains", "Terra Doppia", "Pedina Gatto"} | ({"Asso"} if asso else set()) | ({"Mattone", "Neutra2"} if mattone else set())
        lanciate = {"Neutra", "Plains", "Terra Doppia"} | ({"Asso"} if asso else set())
        sue = {"Mountain", "Comune Sua"} | ({"Drago"} if drago else set()) | ({"Fiamma"} if fiamma else set()) | ({"Rara"} if rnd.random() < 0.3 else set())
        idx[f"m{i}"] = dict(esito="vinta" if vinta else "persa", viste=viste, lanciate=lanciate, sue={n for n in sue if n not in BASI})
        pp.append(dict(matchId=f"m{i}", quando=t0 + datetime.timedelta(hours=i), vinta=vinta))
    pp.append(dict(matchId="senza", quando=t0 - datetime.timedelta(days=3), vinta=True))       # una partita senza scheda: conta in n, non nell'analisi
    terra = lambda n: n in ("Plains", "Terra Doppia")
    a = analizza(pp, lista, terra, idx)
    casi = [("le partite senza scheda restano fuori", a["n"] == 41 and a["con_dati"] == 40),
            ("migliori: l'Asso in testa, sopra il mazzo, col nome intero della lista", a["migliori"] and a["migliori"][0]["nome"] == "Asso // Retro" and a["migliori"][0]["delta"] > 0.2),
            ("fatica: il Mattone, bloccato ogni volta", a["fatica"] and a["fatica"][0]["nome"] == "Mattone" and a["fatica"][0]["quota"] == 1.0),
            ("nessuna terra e nessuna pedina nelle liste", not any(x["nome"] in ("Plains", "Terra Doppia", "Pedina Gatto") for k in ("migliori", "fatica", "perse") for x in a[k])),
            ("nelle perse: il Mattone sotto il mazzo", any(x["nome"] == "Mattone" and x["delta"] < 0 for x in a["perse"])),
            ("le sue: il Drago in testa, le terre base no", a["sue"] and a["sue"][0]["nome"] in ("Drago", "Fiamma") and not any(x["nome"] == "Mountain" for x in a["sue"])),
            ("combo sue: Drago + Fiamma", any(set(x["carte"]) == {"Drago", "Fiamma"} for x in a["combo_sue"])),
            ("negativa: una carta sua che c'e' sempre non e' una combo e non e' fra le sue", not any("Comune Sua" in x["carte"] for x in a["combo_sue"])
             and not any(x["nome"] == "Comune Sua" for x in a["sue"])),
            ("combo tue: Mattone + Neutra2 bloccate insieme nelle perse", any(set(x["carte"]) == {"Mattone", "Neutra2"} and x["perse"] == x["n"] for x in a["combo_mie"]))]
    b = analizza(pp, lista, lambda n: terra(n) or n == "Drago", idx)
    casi.append(("negativa: una sua terra non e' fra le sue carte ne' nelle combo", not any(x["nome"] == "Drago" for x in b["sue"]) and not any("Drago" in x["carte"] for x in b["combo_sue"])))
    ribaltata = analizza([dict(matchId="m0", vinta=False)], lista, terra, idx)
    casi.append(("negativa: una partita il cui esito non torna con la scheda non entra", ribaltata["con_dati"] == 0))
    vuota = analizza([dict(matchId="m0", vinta=True)], lista, terra, {})
    casi.append(("negativa: senza schede niente liste", vuota["con_dati"] == 0 and not any(vuota[k] for k in ("migliori", "fatica", "perse", "sue", "combo_sue", "combo_mie"))))
    ok = sum(1 for _n, v in casi if v)
    for n, v in casi:
        print(("ok    " if v else "ROSSO ") + n)
    print(f"{ok}/{len(casi)}")
    return ok == len(casi)


def stampa(nome):
    """L'analisi di un tuo mazzo di Arena, a testo."""
    from dati_app import mazzi_arena_o_niente
    import dati_mazzo as DM
    db = DM.tabella_carte()
    for m in mazzi_arena_o_niente():
        if m["nome"] == nome:
            lista = {**m["main"], **m["side"], **m["comandante"], **m["compagno"]}
            a = analizza(partite_mazzo(m["id"]), lista, lambda n: DM.e_terra(n, db))
            print(f"{nome}: {a['n']} partite nel log, {a['con_dati']} con le carte, win rate {round(100 * (a['wr'] or 0))}%")
            for k in ("migliori", "fatica", "perse", "sue", "combo_sue", "combo_mie"):
                print(f"  {k}:")
                for x in a[k]:
                    print("    ", x)
            return
    print("mazzo non trovato:", nome)


if __name__ == "__main__":
    if "--prova" in sys.argv:
        sys.exit(0 if prova() else 1)
    if len(sys.argv) > 1:
        stampa(sys.argv[1])
    else:
        print(__doc__)
