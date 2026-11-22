"""Il solito riga per riga del voto per fase (21 nov 2026, dal memo: «il "sotto il solito" riga per riga ... oggi la riga di una tua scelta e' verde o
rossa per il segno, non contro come rendono di solito le tue scelte uguali»; Autore: «Facciamo Il voto per fase»).

Ogni tua scelta del voto per fase (ev_partita.righe_fasi: lanciare, giocare una terra, attaccare, bloccare, non bloccare, il potere di un planeswalker)
si mette contro le tue scelte uguali nelle altre partite DELLO STESSO MAZZO (la regola del 20 nov 2026: ogni mazzo si confronta con se stesso,
DA.chiave_mazzo), nella stessa fase del turno (prima principale, combattimento, seconda) e nello stesso tratto di partita (turni 1-3, 4-6, 7+). La scelta
uguale si cerca a gradini, dalla piu' stretta alla piu' larga, e vale il primo gradino con almeno MINIMO esempi:
    la stessa carta (lanci e poteri)  ->  lo stesso tipo di carta (creatura, istantaneo...)  ->  lo stesso tipo di scelta  ->  lo stesso tipo in ogni tratto.
Il numero e' in punti di probabilita' di vincere, come le righe: lo scarto = la riga meno la media dei suoi esempi. La partita stessa non conta nel suo
solito (lascia-una-fuori).

Le righe di tutte le partite costano ~0,17 s a partita (il replay azione per azione e il modello della P): si calcolano in sottofondo (la pagina, a pezzi,
mai mentre il replayer anima) e si tengono in Log_Arena/cache/righe_fasi.marshal, valide finche' l'ambiente (il codice, le regole, il database) e il dato
della partita sono gli stessi. Senza abbastanza esempi la riga resta col colore del segno e lo dice («few games»).

    py -I -X utf8 Companion/App/Schede/Performance/solito_righe.py --prova
    py -I -X utf8 Companion/App/Schede/Performance/solito_righe.py --tutte     (le righe di tutte le partite, da riga di comando)
"""
import os
import re
import sys
import marshal      # solo dati, mai codice (SICUREZZA.md R2; fino al 22 nov 2026 era un altro formato)

_casa = os.path.dirname(os.path.abspath(__file__))
while not os.path.isfile(os.path.join(_casa, "percorsi.py")):
    _casa = os.path.dirname(_casa)
if _casa not in sys.path:
    sys.path.insert(0, _casa)
import percorsi  # noqa: E402,F401

MINIMO = 8          # esempi per un gradino (grado C: sotto, la media di poche scelte e' rumore)
_MEM = {}           # {"amb": impronta, "righe": {chiave partita: [voci]}}
_F = None


def _file():
    global _F
    if _F is None:
        from ambiente import LOGDIR
        _F = os.path.join(LOGDIR, "cache", "righe_fasi.marshal")
    return _F


def tratto(giro):
    return "1-3" if giro <= 3 else "4-6" if giro <= 6 else "7+"


def _tipo_carta(nome):
    try:
        import dati_analizzatore as DA
        c = DA._carta(nome or "") or {}
    except Exception:       # noqa: BLE001
        c = {}
    tipo = (c.get("tipo") or "").split(" // ")[0]
    for k in ("Creature", "Planeswalker", "Instant", "Sorcery", "Enchantment", "Artifact", "Battle", "Land"):
        if k in tipo:
            return k
    return "Other"


def specie(testo):
    """(tipo di scelta, carta) di una riga di scelta dell'Hero; None se non e' una scelta che si confronta."""
    m = re.match(r"You cast (.+)$", testo)
    if m:
        return "lancio", m.group(1).strip()
    if re.match(r"You played ", testo):
        return "terra", None
    if re.match(r"You attacked with ", testo):
        return "attacco", None
    if testo == NON_BLOCCO:
        return "non_blocco", None
    if " blocked " in testo:
        return "blocco", None
    m = re.match(r"(.+?) (got|lost) \d+ loyalty", testo)
    if m:
        return "potere", m.group(1).strip()
    return None


NON_BLOCCO = "You did not block"      # la riga che ev_partita.righe_fasi aggiunge quando non blocchi potendo


def voci_partita(v):
    """Le scelte dell'Hero di un voto per fase (ev_partita.righe_fasi) -> [(tipo, carta, tipo carta, fase, tratto, ev)]."""
    out = []
    for fz in (v or {}).get("fasi") or []:
        for r_ in fz["righe"]:
            if not r_.get("mio") or r_.get("incluso") or r_.get("tipo") == "risultato":
                continue
            sp = specie(r_["testo"])
            if sp is None:
                continue
            tipo, carta = sp
            out.append((tipo, carta, _tipo_carta(carta) if carta else None, fz["f"], tratto(fz["giro"]), round(r_["ev"], 3)))
    return out


def _chiave_partita(x):
    import dati_analizzatore as DA
    d = DA._MANA.get(x.get("partita")) or {}
    return (x.get("partita"), x.get("seat"), len(d.get("azioni") or []), len(d.get("momenti") or []))


def _carica():
    import dati_analizzatore as DA
    amb = DA._ambiente_righe()
    if _MEM.get("amb") == amb:
        return _MEM["righe"]
    try:
        with open(_file(), "rb") as h:
            c = marshal.loads(h.read())
        righe = c["righe"] if c.get("amb") == amb else {}
    except Exception:       # noqa: BLE001 - copia assente o rotta: si rifa'
        righe = {}
    _MEM.update(amb=amb, righe=righe, sporco=False)
    return righe


def salva():
    if not _MEM.get("sporco"):
        return
    try:
        f = _file()
        os.makedirs(os.path.dirname(f), exist_ok=True)
        with open(f + ".tmp", "wb") as h:
            marshal.dump(dict(amb=_MEM["amb"], righe=_MEM["righe"]), h)
        os.replace(f + ".tmp", f)
        _MEM["sporco"] = False
    except OSError:
        pass


def gia_fatta(x):
    return _chiave_partita(x) in _carica()


def calcola(x, passi=None):
    """Le voci di una partita (dalla copia, se no dal replay); [] senza log."""
    righe = _carica()
    k = _chiave_partita(x)
    if k in righe:
        return righe[k]
    import dati_analizzatore as DA
    import ev_partita as EV
    try:
        ps = passi if passi is not None else DA.azioni_partita(x)
        v = EV.righe_fasi(x, ps) if ps else None
        voci = voci_partita(v)
    except Exception:       # noqa: BLE001 - una partita senza dati non ha voci
        voci = []
    righe[k] = voci
    _MEM["sporco"] = True
    return voci


def solito(x, r_, fz, base):
    """Il solito della scelta r_ (una riga del voto della fase fz, della partita x) fra le partite dello stesso mazzo in base (la mappa delle partite del
    tipo): dict(media, n, gradino, scarto, fatte, totali) o None se la riga non si confronta. Solo partite gia' calcolate (calcola non parte qui)."""
    sp = specie(r_.get("testo") or "")
    if sp is None or not r_.get("mio") or r_.get("incluso"):
        return None
    tipo, carta = sp
    tc = _tipo_carta(carta) if carta else None
    import dati_analizzatore as DA
    km = DA.chiave_mazzo(x)
    stesse = [y for y in (base or []) if DA.chiave_mazzo(y) == km and y.get("partita") != x.get("partita")]
    righe = _carica()
    esempi, fatte = [], 0
    for y in stesse:
        v = righe.get(_chiave_partita(y))
        if v is None:
            continue
        fatte += 1
        esempi.extend(v)
    f, tr = fz["f"], tratto(fz["giro"])
    gradini = []
    if carta:
        gradini.append(("the same card", lambda e: e[0] == tipo and e[1] == carta and e[3] == f and e[4] == tr))
        gradini.append(("the same card, any turn", lambda e: e[0] == tipo and e[1] == carta and e[3] == f))
    if tc:
        gradini.append((f"{'an' if tc[0] in 'AEIOU' else 'a'} {tc.lower()}", lambda e: e[0] == tipo and e[2] == tc and e[3] == f and e[4] == tr))
    gradini.append(("the same kind of play", lambda e: e[0] == tipo and e[3] == f and e[4] == tr))
    gradini.append(("the same kind of play, any turn", lambda e: e[0] == tipo and e[3] == f))
    for nome, ok in gradini:
        vs = [e[5] for e in esempi if ok(e)]
        if len(vs) >= MINIMO:
            m = sum(vs) / len(vs)
            return dict(media=m, n=len(vs), gradino=nome, scarto=r_["ev"] - m, fatte=fatte, totali=len(stesse))
    return dict(media=None, n=0, gradino=None, scarto=None, fatte=fatte, totali=len(stesse))


def prova():
    import dati_analizzatore as DA
    casi = []
    casi.append(("lancio", specie("You cast Shock") == ("lancio", "Shock")))
    casi.append(("non blocco", specie(NON_BLOCCO) == ("non_blocco", None)))
    casi.append(("blocco", specie("Vampire Nighthawk blocked Goblin") == ("blocco", None)))
    casi.append(("potere", specie("Jace got 1 loyalty") == ("potere", "Jace")))
    casi.append(("negativa: un risultato non e' una scelta", specie("You drew a card") is None))
    v = dict(fasi=[dict(f="main1", giro=2, righe=[dict(testo="You cast Shock", mio=True, incluso=False, tipo="mio_su", ev=3.0),
                                                   dict(testo="Goblin died", mio=None, incluso=True, tipo="risultato", ev=1.0),
                                                   dict(testo="Opponent cast Shock", mio=False, incluso=False, tipo="suo_buono", ev=-2.0)])])
    vp = voci_partita(v)
    casi.append(("le voci: solo le scelte dell'Hero", len(vp) == 1 and vp[0][0] == "lancio" and vp[0][3] == "main1" and vp[0][4] == "1-3"))
    # il solito a gradini, su partite finte dello stesso mazzo
    chiave_vera = DA.chiave_mazzo
    DA.chiave_mazzo = lambda y: y.get("m")
    salvate = dict(_MEM)
    try:
        _MEM.update(amb=DA._ambiente_righe(), righe={}, sporco=False)
        base = [dict(partita=f"p{i}", seat=1, m="A") for i in range(12)] + [dict(partita="q", seat=1, m="B")]
        for i, y in enumerate(base[:12]):
            _MEM["righe"][_chiave_partita(y)] = [("lancio", "Shock", "Instant", "main1", "1-3", 2.0 if i < 6 else 4.0)]
        _MEM["righe"][_chiave_partita(base[12])] = [("lancio", "Shock", "Instant", "main1", "1-3", -50.0)]
        x = dict(partita="nuova", seat=1, m="A")
        fz = dict(f="main1", giro=2)
        s = solito(x, dict(testo="You cast Shock", mio=True, incluso=False, ev=5.0), fz, base)
        casi.append(("il solito della stessa carta, stesso mazzo", s and s["gradino"] == "the same card" and abs(s["media"] - 3.0) < 1e-9 and s["n"] == 12))
        casi.append(("negativa: l'altro mazzo non entra nel solito", s and s["media"] > 0))
        s2 = solito(x, dict(testo="You cast Lightning Strike", mio=True, incluso=False, ev=1.0), fz, base)
        casi.append(("negativa: un'altra carta senza esempi non usa quelli di Shock come stessa carta", s2 is None or s2["gradino"] != "the same card"))
        s3 = solito(base[0], dict(testo="You cast Shock", mio=True, incluso=False, ev=2.0), fz, base)
        casi.append(("lascia-una-fuori: la partita non conta nel suo solito", s3 and s3["n"] == 11))
        s4 = solito(x, dict(testo="You cast Shock", mio=True, incluso=False, ev=5.0), dict(f="main2", giro=2), base)
        casi.append(("negativa: un'altra fase non ha esempi", s4 and s4["media"] is None))
    finally:
        DA.chiave_mazzo = chiave_vera
        _MEM.clear(); _MEM.update(salvate)
    for n, ok in casi:
        print(("ok    " if ok else "ROSSO ") + n)
    print(f"{sum(1 for _n, ok in casi if ok)}/{len(casi)}")
    return all(ok for _n, ok in casi)


if __name__ == "__main__":
    if "--prova" in sys.argv:
        sys.exit(0 if prova() else 1)
    if "--tutte" in sys.argv:
        import time
        import dati_analizzatore as DA
        t0 = time.time()
        R = DA.righe()
        for j, x in enumerate(R):
            calcola(x)
            if j % 50 == 0:
                salva()
        salva()
        print(f"{len(R)} partite in {time.time() - t0:.0f} s")
