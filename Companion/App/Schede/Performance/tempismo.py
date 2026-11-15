"""Il tempismo degli istantanei e dei flash (14 nov 2026, il censimento delle domande di Autore, D2 e D3: «quante volte non ho lanciato una spell nel turno
avversario ma nel mio perdendo valore»; M2, M3, M4 di Note/Censimento_Domande_Autore_Strumenti.md).

Per ogni tuo istantaneo o creatura con flash lanciato nel tuo turno, dai dati di mana_aperto (le fasi delle magie, i momenti, le foto di fine turno):
  - in combattimento (fase Combat): un trucco o una risposta, non poteva aspettare;
  - una risposta: la magia prima, nello stesso turno e nella stessa fase, e' dell'avversario, o la tua prende di mira qualcosa in pila (una contromagia);
  - libera l'attacco: in Main 1 (o all'inizio del turno) toglie un suo permanente e poi attacchi;
  - poteva aspettare: tutto il resto (M3). Fra questi il valore perso (M4):
      mana bloccato: a fine turno avevi in mano una magia non istantanea che col mana speso avresti lanciato (stap < costo <= stap + costo
                     dell'istantaneo; i colori non contano, grado C);
      flash esposto: la creatura con flash non c'era piu' a fine del tuo turno dopo (non ha mai attaccato).
Non vede le ragioni buone del tuo turno (una creatura con un innesco d'entrata o con rapidita' tolta prima che attacchi, il burn alla faccia per chiudere, il
flashback come mana di fine partita): «poteva aspettare» e' un massimo. Misura del 14 nov 2026 (544 partite): Constructed 372 lanci che potevano aspettare,
153 col valore perso; Limited 62 e 36.

per_partita(x) -> dict(nel_mio=[turni], aspetta=[turni], perso=[turni]) o None senza i momenti; valore(x, k) -> «0», «1», «2+» o None.
"""
import os, sys
_casa = os.path.dirname(os.path.abspath(__file__))
while not os.path.isfile(os.path.join(_casa, "percorsi.py")):
    _casa = os.path.dirname(_casa)
if _casa not in sys.path:
    sys.path.insert(0, _casa)
import percorsi  # noqa: E402,F401
import re  # noqa: E402


class _DA:
    """L'analizzatore preso quando serve (come cimitero.py): dati_analizzatore importa questo modulo mentre si carica."""
    def __getattr__(self, k):
        import dati_analizzatore
        return getattr(dati_analizzatore, k)

    def __setattr__(self, k, v):
        import dati_analizzatore
        setattr(dati_analizzatore, k, v)


DA = _DA()

NOMI = {"tm_nel_mio": "Instants and flash you cast on your turn", "tm_aspetta": "Of them, ones that could have waited for their turn",
        "tm_perso": "Of them, ones that lost value (mana you needed, or a flash creature exposed)"}
ORDINE = {k: ("0", "1", "2+") for k in NOMI}
_MEMO = {}


def _info(g):
    import leak as LK
    n = LK._nome(g)
    c = LK._carta(n) if n else {}
    return n, (c.get("tipo") or ""), (c.get("testo") or ""), c.get("cmc")


# Le sinergie (15 nov 2026, Autore: «alcuni leak non tengono conto di sinergie»): un istantaneo o un flash lanciato in Main 1 del turno in cui attacchi
# non «poteva aspettare» se serve all'attacco. Il suo effetto tappa un bloccante o gli toglie il blocco (una pompa no: quella si lancia dopo i blocchi),
# o una tua carta in campo ha un payoff che scatta quando lanci la magia e potenzia le creature (prowess, «whenever you cast a noncreature / an instant
# spell ... gets +1/+1», un segnalino +1/+1, magecraft) o, se fa danno non da combattimento, Master of Barbs.
_RX_BLOCCO = re.compile(r"\btap (?:target|up to|all)|can't block", re.I)
_RX_PAYOFF = re.compile(r"\bprowess\b|(?:whenever you cast|magecraft)[^.]{0,80}(?:\+\d+/\+\d+|gets? \+|\+1/\+1 counter)|"
                        r"dealt noncombat damage, creatures you control get", re.I)


def _serve_attacco(n, testo, t, a, mom):
    if _RX_BLOCCO.search(testo or ""):
        return True
    comb = next((m for m in mom if m[0] == "comb" and m[1] == t and isinstance(m[3], dict)), None)
    for c in ((comb[3].get("c") or [[], []])[a] if comb else []):
        tx = _info(c[0])[2] or ""
        if _RX_PAYOFF.search(tx):
            return True
    return False


def per_partita(x):
    d = DA._MANA.get(x.get("partita")) or {}
    seat = x.get("seat")
    mom = d.get("momenti")
    if not mom or seat not in (1, 2):
        return None
    firma = (x.get("partita"), len(mom), len(d.get("fasi") or []))
    if firma in _MEMO:
        return _MEMO[firma]
    a = seat - 1
    attivo = {}
    for m in mom:
        if m[0] in ("fine", "comb", "spell"):
            attivo.setdefault(m[1], m[2])
    attaccato = {m[1] for m in mom if m[0] == "comb" and m[2] == seat}
    fine = {m[1]: m[3] for m in mom if m[0] == "fine" and isinstance(m[3], dict)}
    magie = [m for m in mom if m[0] == "spell" and m[4] and not m[4].get("ab")]
    fasi = d.get("fasi") or []
    out = dict(nel_mio=[], aspetta=[], perso=[])
    for i, (t, s_, g, fase) in enumerate(fasi):
        if s_ != seat or attivo.get(t) != seat:
            continue
        n, tipo, testo, cmc = _info(g)
        if not n:
            continue
        flash = "Creature" in tipo and "Flash" in testo
        if "Instant" not in tipo and not flash:
            continue
        out["nel_mio"].append(t)
        if fase == "Phase_Combat":
            continue
        prec = fasi[i - 1] if i else None
        sm = next((m for m in magie if m[1] == t and m[4].get("g") == g and m[4].get("chi") == seat), None)
        if (prec is not None and prec[0] == t and prec[1] != seat and prec[3] == fase) or "counter target" in testo.lower() \
                or (sm and any(z == "pila" for _i, z, _p, _g in (sm[4].get("fuori") or []))):
            continue        # una risposta
        if fase in ("Phase_Main1", "Phase_Beginning") and t in attaccato and sm and (sm[4].get("colpiti") or sm[4].get("fatti")):
            continue        # ha liberato l'attacco
        if fase in ("Phase_Main1", "Phase_Beginning") and t in attaccato and _serve_attacco(n, testo, t, a, mom):
            continue        # ha servito l'attacco: tappa o ferma un bloccante, o accende un payoff da combattimento in campo (15 nov 2026, le sinergie)
        out["aspetta"].append(t)
        perso = False
        f = fine.get(t)
        if f and cmc is not None:
            terre = [c for c in (f.get("c") or [[], []])[a] if DA.e_terra(_info(c[0])[0] or "")]
            stap = sum(1 for c in terre if not c[1])
            for gm in (f.get("m") or [[], []])[a]:
                nm, tp, tx, cm = _info(gm)
                if nm and cm and "Land" not in tp and "Instant" not in tp and "Flash" not in tx and stap < cm <= stap + cmc:
                    perso = True
                    break
        if not perso and flash and fine.get(t + 2) is not None:
            perso = g not in [c[0] for c in (fine[t + 2].get("c") or [[], []])[a]]
        if perso:
            out["perso"].append(t)
    _MEMO[firma] = out
    return out


def valore(x, k):
    p = per_partita(x)
    if p is None:
        return None
    n = len(p[k[3:]])
    return str(n) if n < 2 else "2+"


def prova():
    casi = []
    # lanci finti: Opt (istantaneo) nel tuo turno 1 in Main 2 = poteva aspettare; in combattimento no; la sua magia prima nella stessa fase = risposta
    import leak as LK
    nomi = {801: ("Opt", "Instant", "Scry 1. Draw a card.", 1), 802: ("Grizzly Bears", "Creature — Bear", "", 2), 803: ("Ambush Viper", "Creature — Snake", "Flash\nDeathtouch", 2),
            804: ("Shock", "Instant", "Shock deals 2 damage to any target.", 1)}
    vecchie = (LK._nome, LK._carta)
    LK._nome = lambda g: nomi.get(g, (None,))[0]
    LK._carta = lambda n: next(({"tipo": v[1], "testo": v[2], "cmc": v[3]} for v in nomi.values() if v[0] == n), {})
    try:
        def partita(fasi, mom, chiave):
            DA._MANA[chiave] = dict(momenti=mom, fasi=fasi)
            return per_partita(dict(partita=chiave, seat=1))
        fine1 = ["fine", 1, 1, dict(c=[[], []], m=[[], []]), None]
        p = partita([[1, 1, 801, "Phase_Main2"]], [fine1], "tm1")
        casi.append(("Opt nel tuo turno in Main 2: lanciato nel tuo turno e poteva aspettare", p == dict(nel_mio=[1], aspetta=[1], perso=[])))
        p = partita([[1, 1, 801, "Phase_Combat"]], [fine1], "tm2")
        casi.append(("negativa: in combattimento non poteva aspettare", p == dict(nel_mio=[1], aspetta=[], perso=[])))
        p = partita([[1, 2, 804, "Phase_Main1"], [1, 1, 801, "Phase_Main1"]], [fine1], "tm3")
        casi.append(("negativa: la sua magia prima nella stessa fase, la tua e' una risposta", p["aspetta"] == []))
        p = partita([[2, 2, 804, "Phase_Main1"]], [["fine", 2, 2, None, None]], "tm4")
        casi.append(("negativa: nel suo turno non conta", p == dict(nel_mio=[], aspetta=[], perso=[])))
        # mana bloccato: a fine turno 1 hai in mano Grizzly Bears (2), una terra stappata, Opt costava 1 → con Opt in mano avresti avuto 2 mana
        terra = [[999, 0, 0, None, None, 1]]
        DA_e = DA.e_terra
        DA.e_terra = lambda n: n == "Forest"
        nomi[999] = ("Forest", "Basic Land — Forest", "", 0)
        f1 = dict(c=[terra, []], m=[[802], []])
        p = partita([[1, 1, 801, "Phase_Main2"]], [["fine", 1, 1, f1, None]], "tm5")
        casi.append(("mana bloccato: Grizzly Bears in mano, 1 terra stappata + Opt da 1 = l'avresti lanciata", p["perso"] == [1]))
        f2 = dict(c=[terra + [[999, 0, 0, None, None, 2]], []], m=[[802], []])
        p = partita([[1, 1, 801, "Phase_Main2"]], [["fine", 1, 1, f2, None]], "tm6")
        casi.append(("negativa: con 2 terre stappate i Bears li potevi lanciare lo stesso", p["perso"] == []))
        # flash esposto: Ambush Viper lanciata nel tuo turno, sparita a fine del tuo turno dopo
        mom = [["fine", 1, 1, dict(c=[[[803, 0, 0, 2, 1, 5]], []], m=[[], []]), None], ["fine", 3, 1, dict(c=[[], []], m=[[], []]), None]]
        p = partita([[1, 1, 803, "Phase_Main1"]], mom, "tm7")
        casi.append(("flash esposto: la Viper lanciata nel tuo turno non c'e' piu' due turni dopo", p["perso"] == [1]))
        DA.e_terra = DA_e
        # le sinergie (15 nov 2026): Opt in Main 1 del turno in cui attacchi con un prowess in campo serve all'attacco; negativa: senza il payoff aspetta
        nomi[805] = ("Monastery Swiftspear", "Creature — Human Monk", "Haste\nProwess", 1)
        nomi[806] = ("Frost Breath", "Instant", "Tap up to two target creatures. They don't untap during their controller's next untap step.", 3)
        comb_ = lambda campo: ["comb", 1, 1, dict(c=[campo, []], m=[[], []]), dict(att=[[5, 2]], blocchi=[])]
        p = partita([[1, 1, 801, "Phase_Main1"]], [comb_([[805, 0, 0, 1, 2, 5]]), fine1], "tm8")
        p2 = partita([[1, 1, 801, "Phase_Main1"]], [comb_([[802, 0, 0, 2, 2, 5]]), fine1], "tm9")
        casi.append(("sinergia: Opt prima dell'attacco con Monastery Swiftspear (prowess) non poteva aspettare; negativa: coi Grizzly Bears si'",
                     p["aspetta"] == [] and p2["aspetta"] == [1]))
        p = partita([[1, 1, 806, "Phase_Main1"]], [comb_([[802, 0, 0, 2, 2, 5]]), fine1], "tm10")
        casi.append(("sinergia: Frost Breath prima dell'attacco tappa i bloccanti, non poteva aspettare", p["aspetta"] == []))
        casi.append(("valore: 2+ e 0", valore(dict(partita="tm7", seat=1), "tm_perso") == "1" and valore(dict(partita="tm4", seat=1), "tm_nel_mio") == "0"))
    finally:
        LK._nome, LK._carta = vecchie
        for k in [k for k in DA._MANA if str(k).startswith("tm")]:
            DA._MANA.pop(k, None)
        _MEMO.clear()
    for n, ok in casi:
        print(("ok    " if ok else "ROSSO ") + n)
    print(f"{sum(1 for _n, ok in casi if ok)}/{len(casi)}")
    return all(ok for _n, ok in casi)


if __name__ == "__main__":
    sys.exit(0 if prova() else 1)
