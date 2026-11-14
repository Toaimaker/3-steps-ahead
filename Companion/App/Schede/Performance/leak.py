"""I leak: gli errori che i coach cercano nei replay, trovati dal log (13 nov 2026, Note/HANDOFF_Censimento_Performance.md, voci L1-L8 dentro R5; Autore:
«poi passa a L1 ecc», «a tutto quel che è rimasto»). Sono indizi di grado C finche' non sono misurati sulle vittorie: si mostrano come segni, col numero
vero, mai come sentenze.

    L1  terra non giocata con una terra in mano: un tuo turno senza terra giocata e una terra nella tua mano a fine turno (Sam Black)
    L4  chump block a vita alta: hai bloccato, i tuoi bloccanti sono morti e i suoi attaccanti no, con la vita a VITA_ALTA o piu' e un attacco che non era
        letale (Wizards)
    L2  mana inutilizzato con una creatura lanciabile in mano: a fine tuo turno le terre stappate pagano (colori compresi) una creatura senza flash che
        hai in mano (Draftsim). Solo le creature: con tutte le magie non istantanee erano 250 partite su 483 (aure senza bersaglio, rimozioni tenute per
        la minaccia giusta), con le creature 132, vinte al 43%
    L3  creatura lanciata prima dell'attacco: nel turno in cui attacchi, una creatura senza rapidita' lanciata nella prima fase principale (prima terra,
        attacco, poi magie: PVDDR). Serve la fase delle magie (mana_aperto VERSIONE 14)
    L5  scambio sfavorevole: in un tuo attacco o in un tuo blocco perdi creature che costano almeno 2 mana piu' delle sue (Cardsphere)
    L6  istantaneo nel suo turno quando nel tuo era tappato: lanci un istantaneo nel suo turno fuori dal combattimento, non una contromagia, e alla fine del
        tuo turno prima lui aveva tutte le terre tappate: potevi lanciarlo senza che rispondesse (Merriam)
    L8  terre tappate male: a fine tuo turno una magia in mano (non istantanea) costa quanto le terre stappate ma i loro colori non la pagano, mentre le
        stesse terre, tappate diversamente per le magie lanciate nel turno, l'avrebbero pagata (Verhey, Chapin). Senza le abilita' attivate: grado C
    L7  concessione con vie d'uscita: hai concesso con almeno VITA_CONCEDI vite, piu' del doppio della forza che lui ha in campo (non ti chiudeva nemmeno
        in due attacchi) e almeno una carta in mano (Ferguson). Tarata sui log del 13 nov: con «vita sopra la sua forza» erano 116 concessioni su 206

per_partita(x) -> dict(l1 ... l8 = [turni di Arena in cui succede] (dicono anche di chi era il turno), l7=bool) dai momenti di mana_aperto (foto di fine turno, combattimenti) e dalle azioni (terre
giocate); None se la partita non ha i momenti. I turni sono quelli di ognuno (il tuo turno 3), come nel replayer.
"""
import os, sys
_casa = os.path.dirname(os.path.abspath(__file__))
while not os.path.isfile(os.path.join(_casa, "percorsi.py")):
    _casa = os.path.dirname(_casa)
if _casa not in sys.path:
    sys.path.insert(0, _casa)
import percorsi  # noqa: E402,F401
import dati_analizzatore as DA  # noqa: E402

VITA_ALTA = 10          # da qui in su un chump block costa una carta per vite che non servono ancora (grado C)
VITA_CONCEDI = 8        # L7: sotto, una concessione e' di solito una partita persa davvero (grado C)
NOMI = {"l1": "Missed a land drop with a land in hand", "l2": "Unused mana with a castable creature in hand", "l3": "Creature cast before your attack",
        "l4": "Chump block at high life", "l5": "Unfavourable trade", "l6": "Instant on their turn while they were tapped out on yours",
        "l7": "Conceded with outs", "l8": "Lands tapped the wrong way"}
ORDINE = ("l1", "l2", "l3", "l4", "l5", "l6", "l7", "l8")
SPIEGA = {"l1": "a turn of yours with no land played and a land in your hand at its end",
          "l4": f"you blocked, your blockers died and their attackers did not, at {VITA_ALTA}+ life against an attack that was not lethal",
          "l2": "at the end of your turn your untapped lands could pay a creature (without flash) in your hand, colors included",
          "l3": "on a turn you attacked, a creature without haste cast in your first main phase (land, attack, then spells)",
          "l5": "in an attack or a block of yours you lost creatures costing 2+ mana more than theirs",
          "l6": "an instant cast on their turn (not in combat, not a counterspell) while they had every land tapped at the end of your turn",
          "l8": "at the end of your turn a card in hand cost what your untapped lands could make, but not their colors; tapping other lands would have paid it",
          "l7": f"you conceded with {VITA_CONCEDI}+ life, more than twice their power on the battlefield, and at least one card in hand"}


# R10, il leak tracker (13 nov 2026, come il Leak Tracker di PokerTracker): come si corregge ogni leak, una riga (dai coach citati sopra; grado C)
COME = {"l1": "Play a land every turn unless you hold it on purpose (a landfall, a bluff): a missed drop is a turn of mana you never get back",
        "l2": "At the end of your turn count your untapped lands against your hand: if a creature fits, cast it unless you are holding up something better",
        "l3": "Attack first, then cast creatures in your second main phase: they hide what you hold and keep their bluff (unless they help the attack)",
        "l4": "At high life take the damage: block to trade, not to chump, until the life total starts to matter",
        "l5": "Before blocking or attacking into a block, compare what you lose with what they lose: avoid trading a big card for a small one",
        "l6": "Cast your instants when they cannot answer: on their turn while they are tapped out, or on yours before they untap",
        "l7": "With life and cards in hand, play it out: many games turn on one draw, and a concession gives away every out",
        "l8": "Tap the lands that make the colors you will not need: leave open the colors of the cards still in your hand"}
RECENTI = 50        # il trend: le ultime RECENTI partite contro quelle prima


def tracker(r):
    """R10: per ogni leak, nelle partite r che hanno i momenti: in quante c'e' (il tasso), il win rate con e senza, e il trend (il tasso nelle ultime RECENTI
    partite contro quelle prima). La popolazione (gli altri giocatori) non c'e': servirebbero i dati condivisi (C12, scelta di Autore).
    -> [dict(k, nome, spiega, come, n, con, tasso, wr_con, wr_senza, delta, tasso_rec, tasso_prima)] nell'ordine di ORDINE."""
    rr = sorted((x for x in r if x.get("leak")), key=lambda x: x["quando"])
    out = []
    wr = lambda xs: round(100 * sum(1 for x in xs if x["vinta"]) / len(xs), 1) if xs else None
    for k in ORDINE:
        con = [x for x in rr if valore(x, k) == "Yes"]
        senza = [x for x in rr if valore(x, k) == "No"]
        rec, prima = rr[-RECENTI:], rr[:-RECENTI]
        tasso = lambda xs: round(100 * sum(1 for x in xs if valore(x, k) == "Yes") / len(xs), 1) if xs else None
        w_c, w_s = wr(con), wr(senza)
        out.append(dict(k=k, nome=NOMI[k], spiega=SPIEGA[k], come=COME[k], n=len(rr), con=len(con), tasso=tasso(rr), wr_con=w_c, wr_senza=w_s,
                        delta=None if w_c is None or w_s is None else round(w_c - w_s, 1),
                        tasso_rec=tasso(rec) if len(rr) > RECENTI else None, tasso_prima=tasso(prima) if len(prima) >= 10 else None))
    return out


def _terra(g):
    n = DA.nome_grp(g) if g not in DA.SENZA_FACCIA else None
    return bool(n) and DA.e_terra(n)


def _forza(lato, ids=None):
    return sum(max(0, c[3] or 0) for c in lato or [] if len(c) > 3 and c[3] is not None and (ids is None or (len(c) > 5 and c[5] in ids)))


def per_partita(x):
    d = DA._MANA.get(x.get("partita")) or {}
    seat, mom = x.get("seat"), d.get("momenti")
    if seat not in (1, 2) or not mom:
        return None
    a, b = seat - 1, 2 - seat
    terre = {t for t, s_, cosa, _g, _tp in d.get("azioni") or [] if cosa == "terra" and s_ == seat}
    l1, l4 = [], []
    for m in mom:
        if m[0] == "fine" and m[2] == seat and isinstance(m[3], dict):
            mano = (m[3].get("m") or [[], []])[a]
            if m[1] not in terre and any(_terra(g) for g in mano):
                l1.append(m[1])
    for dec in _blocchi(x, d, seat):
        l4.append(dec)
    l2, l3, l5, l6, l8 = [], [], [], [], []
    magie_t, terre_t = {}, {}
    for t, s_, cosa, g_, _tp in d.get("azioni") or []:
        if cosa == "magia" and s_ == seat:
            magie_t.setdefault(t, []).append(g_)
        elif cosa == "terra" and s_ == seat:
            terre_t.setdefault(t, []).append(g_)
    fine_mie = {m[1]: m[3] for m in mom if m[0] == "fine" and m[2] == seat and isinstance(m[3], dict)}
    for t, f in fine_mie.items():
        mano = [n for n in (_nome(g) for g in (f.get("m") or [[], []])[a]) if n]
        miei = (f.get("c") or [[], []])[a]
        terre_tutte = [c for c in miei if _terra(c[0])]
        stap = [_colori_terra(c[0]) for c in terre_tutte if not c[1]]
        # per L8 contano le terre che potevano dare mana nel turno: non quella giocata ora che entra tappata (guildgate, Scoured Barrens: era un falso
        # positivo, 106 partite su 483 prima di toglierle)
        nuove_tappate = [g for g in terre_t.get(t, []) if "enters tapped" in (_carta(_nome(g)).get("testo") or "")]
        tutte_col = []
        for c in terre_tutte:
            if c[1] and c[0] in nuove_tappate:
                nuove_tappate.remove(c[0])
                continue
            tutte_col.append(_colori_terra(c[0]))
        lanciabili = [n for n in mano if not DA.e_terra(n) and "Instant" not in (_carta(n).get("tipo") or "") and _costo(n) is not None]
        creature = [n for n in lanciabili if "Creature" in (_carta(n).get("tipo") or "") and "Flash" not in (_carta(n).get("testo") or "")]
        if any(_paga([_costo(n)], stap) for n in creature if 0 < len(_costo(n))):
            l2.append(t)
        else:       # L8: non la pagano le stappate, ma le terre di adesso, ripartite su quello che hai lanciato nel turno, si'
            spese = [c_ for c_ in (_costo(_nome(g)) for g in magie_t.get(t, [])) if c_]
            if spese and any(len(_costo(n)) <= len(stap) and not _paga([_costo(n)], stap) and _paga(spese + [_costo(n)], tutte_col)
                             for n in lanciabili if _costo(n)):       # le stappate NON la pagano (prima mancava: Sunpearl Kirin, flash, tenuta apposta)
                l8.append(t)
    attaccato = {m[1] for m in mom if m[0] == "comb" and m[2] == seat}
    for t, s_, g_, fase in d.get("fasi") or []:
        n = _nome(g_)
        if not n:
            continue
        cc = _carta(n)
        tipo, testo = cc.get("tipo") or "", (cc.get("testo") or "")
        if s_ == seat and t in attaccato and fase == "Phase_Main1" and "Creature" in tipo and "Haste" not in testo and "haste" not in testo:
            l3.append(t)
        mio_turno = (t % 2 == 1) == bool(x.get("inizia")) if x.get("inizia") is not None else None
        if s_ == seat and mio_turno is False and "Instant" in tipo and fase != "Phase_Combat" and "counter target" not in testo.lower():
            f_prima = fine_mie.get(t - 1)
            if f_prima is not None:
                sue_terre = [c for c in (f_prima.get("c") or [[], []])[b] if _terra(c[0])]
                if sue_terre and all(c[1] for c in sue_terre):
                    l6.append(t)
    import decisioni as DEC
    for dec in DEC.per_partita(dict(x, vinta=x.get("vinta"), quando=x.get("quando"))):
        if dec["persi_miei"] and dec["persi_suoi"]:         # uno scambio: muoiono creature da tutte e due le parti
            v = _scambio(d, dec, seat)
            if v is not None and v[0] >= v[1] + 2:
                l5.append(dec["t"])
    l7 = False
    ult = d.get("ultima")
    if x.get("fine") == "You conceded" and ult and isinstance(ult[-1], dict):
        f = ult[-1]
        vita = (f.get("v") or [None, None])[a]
        in_mano = len((f.get("m") or [[], []])[a])
        l7 = vita is not None and vita >= VITA_CONCEDI and vita > 2 * _forza((f.get("c") or [[], []])[b]) and in_mano >= 1
    return dict(l1=sorted(set(l1)), l2=sorted(set(l2)), l3=sorted(set(l3)), l4=sorted(set(l4)), l5=sorted(set(l5)), l6=sorted(set(l6)), l7=l7,
                l8=sorted(set(l8)))


def _nome(g):
    return DA.nome_grp(g) if g not in DA.SENZA_FACCIA else None


def _carta(n):
    return DA._carta(n or "") or {}


def _costo(n):
    """Il costo in simboli («1», «W», «W/U»...) senza X; None se la carta non si conosce."""
    c = _carta(n)
    if not c:
        return None
    out = []
    for sym in c.get("costo") or []:
        if sym.isdigit():
            out += ["1"] * int(sym)
        elif sym not in ("X", "Y", "Z"):
            out.append(sym)
    return out


def _colori_terra(g):
    """I colori che una terra produce (dal database: «colori» della carta; una base dal suo nome); incolore «C»."""
    n = _nome(g) or ""
    base = {"Plains": "W", "Island": "U", "Swamp": "B", "Mountain": "R", "Forest": "G"}.get(n)
    return set(base or (_carta(n).get("colori") or "C"))


def _paga(costi, terre):
    """Le terre (insiemi di colori, una terra = un mana) pagano tutti i costi insieme? Simboli colorati abbinati (abbinamento bipartito), il resto generico.
    Un simbolo ibrido «W/U» vale per tutti e due; «2/W» come colorato; «P» phyrexiano come generico."""
    simboli = [x for c in costi for x in c]
    if len(simboli) > len(terre):
        return False
    colorati = [set(x.replace("2/", "").replace("/P", "").split("/")) for x in simboli if x != "1" and x != "C" and not x.endswith("/P")]
    incolori = sum(1 for x in simboli if x == "C")
    if incolori > sum(1 for t in terre if "C" in t):
        colorati += [{"C"}] * incolori
    match = {}

    def prova(i, visti):
        for j, t in enumerate(terre):
            if j in visti or not (t & colorati[i]):
                continue
            visti.add(j)
            if j not in match or prova(match[j], visti):
                match[j] = i
                return True
        return False
    return all(prova(i, set()) for i in range(len(colorati)))


def _scambio(d, dec, seat):
    """L5: (costo delle tue creature perse, costo delle sue) nel combattimento della decisione, dai momenti di mana_aperto; None se non si sa."""
    mom = d.get("momenti") or []
    m = next((m_ for m_ in mom if m_[0] == "comb" and m_[1] == dec["t"]), None)
    dopo = next((m_[3] for m_ in mom if m_[0] == "fine" and m_[1] == dec["t"]), None)
    if not m or not isinstance(m[3], dict) or not isinstance(dopo, dict):
        return None
    resta = {c[5] for lato in dopo.get("c") or [[], []] for c in lato if len(c) > 5}
    info = m[4] or {}
    ids = {a_[0] for a_ in info.get("att") or []} | {b_[0] for b_ in info.get("blocchi") or []}
    val = [0, 0]
    for lato_i, lato in enumerate(m[3].get("c") or [[], []]):
        for c in lato:
            if len(c) > 5 and c[5] in ids and c[5] not in resta:
                val[0 if lato_i == seat - 1 else 1] += 0 if c[2] else (_carta(_nome(c[0])).get("cmc") or 0)
    return tuple(val)


def _blocchi(x, d, seat):
    """I turni dei tuoi chump block a vita alta (il turno di chi attaccava, il suo: «Opponent T4»)."""
    import decisioni as DEC
    out = []
    mom = d.get("momenti") or []
    per_t = {}
    for m in mom:
        if m[0] == "comb" and len(m) > 4 and m[4] and m[4].get("att") and m[2] != seat:
            per_t.setdefault(m[1], m)
    for dec in DEC.per_partita(dict(x, vinta=x.get("vinta"), quando=x.get("quando"))):
        if dec["tipo"] != "blocco" or not dec["bloccato"] or dec["persi_miei"] < 1 or dec["persi_suoi"] > 0:
            continue
        m = per_t.get(dec["t"])
        if not m or not isinstance(m[3], dict):
            continue
        prima = m[3]
        vita = (prima.get("v") or [None, None])[seat - 1]
        att_ids = {a_[0] for a_ in m[4]["att"]}
        forza_att = _forza((prima.get("c") or [[], []])[2 - seat], att_ids)
        if vita is not None and vita >= VITA_ALTA and forza_att < vita:
            out.append(dec["t"])
    return out


def valore(x, k):
    """Il valore del filtro: «Yes» o «No» (None senza i momenti)."""
    lk = x.get("leak")
    if lk is None:
        return None
    v = lk.get(k)
    return "Yes" if v else "No"


def prova():
    """Partite finte nei dati di mana_aperto: L1 col turno, L4 col blocco perso a vita alta, L7 con la concessione; le negative."""
    casi = []
    salva = dict(DA._MANA)
    nomi = dict(DA._NOMI_GRP)
    try:
        DA._NOMI_GRP.update({801: "Island", 802: "Opt"})
        foto = lambda mano1, mano2=(), v=(20, 20), c1=(), c2=(): dict(m=[list(mano1), list(mano2)], v=list(v), c=[list(c1), list(c2)], n=[len(mano1), len(mano2)])
        # cominci tu (posto 1): al turno 1 giochi la terra, al turno 3 no con un'Isola in mano, al turno 5 no ma senza terre in mano
        DA._MANA["lk1"] = dict(azioni=[[1, 1, "terra", 801, "L"]],
                               momenti=[["fine", 1, 1, foto([801])], ["fine", 3, 1, foto([801, 802])], ["fine", 5, 1, foto([802])]],
                               ultima=[6, 2, foto([802], v=(12, 20), c2=[[900, False, False, 3, 3, 50]])])
        x = dict(partita="lk1", seat=1, fine="You conceded")
        lk = per_partita(x)
        casi.append(("L1: il turno 3 di Arena (il tuo 2) senza terra con un'Isola in mano; negativa: il turno 1 l'ha giocata, il 3 non aveva terre",
                     lk["l1"] == [3]))
        casi.append(("L7: concesso a 12 vite contro 3 di forza con una carta in mano", lk["l7"] is True))
        DA._MANA["lk2"] = dict(DA._MANA["lk1"], ultima=[6, 2, foto([802], v=(3, 20), c2=[[900, False, False, 5, 5, 50]])])
        casi.append(("negativa L7: a 3 vite contro 5 di forza la concessione non ha vie d'uscita", per_partita(dict(x, partita="lk2"))["l7"] is False))
        DA._MANA["lk6"] = dict(DA._MANA["lk1"], ultima=[6, 2, foto([802], v=(12, 20), c2=[[900, False, False, 7, 7, 50]])])
        casi.append(("negativa L7: 12 vite contro 7 di forza (due attacchi la chiudono) non e' una concessione con vie d'uscita",
                     per_partita(dict(x, partita="lk6"))["l7"] is False))
        casi.append(("negativa L7: senza concessione niente", per_partita(dict(x, fine="Played to the end"))["l7"] is False))
        casi.append(("negativa: senza i momenti niente leak", per_partita(dict(partita="nessuna", seat=1)) is None))
        # L4: lui attacca al suo turno 2 (il 4 di Arena) con un 3/3, tu blocchi con un 1/1 a 15 vite: muore il tuo, il suo no
        import datetime
        tua, sua = [700, False, False, 1, 1, 60], [900, False, False, 3, 3, 50]
        DA._MANA["lk3"] = dict(azioni=[], momenti=[["comb", 4, 2, foto([], v=(15, 20), c1=[tua], c2=[sua]), dict(att=[[50, 1]], blocchi=[[60, 50]])],
                                                   ["fine", 4, 2, foto([], v=(15, 20), c1=[], c2=[sua])]], ultima=None)
        x3 = dict(partita="lk3", seat=1, vinta=False, quando=datetime.datetime(2026, 11, 13), fine=None)
        casi.append(("L4: il chump block a 15 vite contro un attacco da 3, al turno 4 di Arena (il suo 2)", per_partita(x3)["l4"] == [4]))
        DA._MANA["lk4"] = dict(DA._MANA["lk3"], momenti=[["comb", 4, 2, foto([], v=(5, 20), c1=[tua], c2=[sua]), dict(att=[[50, 1]], blocchi=[[60, 50]])],
                                                         ["fine", 4, 2, foto([], v=(5, 20), c1=[], c2=[sua])]])
        casi.append(("negativa L4: a 5 vite il chump block non e' un leak", per_partita(dict(x3, partita="lk4"))["l4"] == []))
        DA._MANA["lk5"] = dict(DA._MANA["lk3"], momenti=[["comb", 4, 2, foto([], v=(15, 20), c1=[tua], c2=[sua]), dict(att=[[50, 1]], blocchi=[[60, 50]])],
                                                         ["fine", 4, 2, foto([], v=(15, 20), c1=[], c2=[])]])
        casi.append(("negativa L4: se muore anche il suo e' uno scambio, non un chump block", per_partita(dict(x3, partita="lk5"))["l4"] == []))
        # L2, L3, L5, L6, L8 con carte vere del database (nomi dal grpId finto)
        DA._NOMI_GRP.update({811: "Plains", 812: "Swamp", 813: "Ajani's Pridemate", 814: "Healer's Hawk", 815: "Opt", 816: "Serra Angel"})
        P1, P2, SW = [811, False, False, None, None, 1], [811, False, False, None, None, 2], [812, False, False, None, None, 3]
        tap = lambda c: [c[0], True] + c[2:]
        # L8: tre terre, Pridemate lanciata (1W) tappando le due Plains; resta la Swamp, in mano Healer's Hawk (W): ripartendo (Plains + Swamp) si pagava
        DA._MANA["lk7"] = dict(azioni=[[1, 1, "magia", 813, "C"]], fasi=[[1, 1, 813, "Phase_Main2"]],
                               momenti=[["fine", 1, 1, foto([814], c1=[tap(P1), tap(P2), SW])]], ultima=None)
        l7_ = per_partita(dict(partita="lk7", seat=1, inizia=True))
        casi.append(("L8: la Swamp stappata non paga Healer's Hawk, le terre ripartite si'; negativa L2: la Swamp non la paga", l7_["l8"] == [1] and l7_["l2"] == []))
        DA._MANA["lk8"] = dict(DA._MANA["lk7"], momenti=[["fine", 1, 1, foto([814], c1=[tap(P1), P2, tap(SW)])]])
        l8_ = per_partita(dict(partita="lk8", seat=1, inizia=True))
        casi.append(("L2: la Plains stappata paga Healer's Hawk in mano; negativa L8: tappate giuste", l8_["l2"] == [1] and l8_["l8"] == []))
        DA._NOMI_GRP[817] = "Scoured Barrens"
        BAR = [817, True, False, None, None, 4]
        DA._MANA["lk15"] = dict(azioni=[[1, 1, "magia", 813, "C"], [1, 1, "terra", 817, "L"]], fasi=[], ultima=None,
                                momenti=[["fine", 1, 1, foto([814], c1=[tap(P1), tap(SW), BAR])]])
        DA._MANA["lk16"] = dict(DA._MANA["lk7"], momenti=[["fine", 1, 1, foto([814], c1=[tap(P1), tap(SW), P2])]])
        casi.append(("negativa L8: se le terre stappate pagano gia' la carta non e' un leak di tappatura",
                     per_partita(dict(partita="lk16", seat=1, inizia=True))["l8"] == []))
        casi.append(("negativa L8: la terra giocata nel turno che entra tappata non dava mana (niente leak)",
                     per_partita(dict(partita="lk15", seat=1, inizia=True))["l8"] == []))
        # L3: Pridemate lanciata nella prima fase principale del turno in cui attacchi
        att_ = [["comb", 1, 1, foto([], c1=[[813, False, False, 2, 2, 9]]), dict(att=[[9, 2]], blocchi=[])]]
        DA._MANA["lk9"] = dict(azioni=[], fasi=[[1, 1, 813, "Phase_Main1"]], momenti=att_, ultima=None)
        casi.append(("L3: una creatura lanciata prima dell'attacco", per_partita(dict(partita="lk9", seat=1, inizia=True))["l3"] == [1]))
        DA._MANA["lk10"] = dict(DA._MANA["lk9"], fasi=[[1, 1, 813, "Phase_Main2"]])
        casi.append(("negativa L3: lanciata dopo l'attacco (seconda fase principale)", per_partita(dict(partita="lk10", seat=1, inizia=True))["l3"] == []))
        # L6: alla fine del tuo turno 1 le sue terre sono tutte tappate, nel suo turno 2 lanci Opt fuori dal combattimento
        DA._MANA["lk11"] = dict(azioni=[], fasi=[[2, 1, 815, "Phase_Main1"]], ultima=None,
                                momenti=[["fine", 1, 1, foto([], c2=[tap([812, False, False, None, None, 7])])]])
        casi.append(("L6: Opt nel suo turno mentre nel tuo lui era tappato", per_partita(dict(partita="lk11", seat=1, inizia=True))["l6"] == [2]))
        DA._MANA["lk12"] = dict(DA._MANA["lk11"], momenti=[["fine", 1, 1, foto([], c2=[[812, False, False, None, None, 7]])]])
        casi.append(("negativa L6: lui aveva una terra stappata", per_partita(dict(partita="lk12", seat=1, inizia=True))["l6"] == []))
        # L5: tu attacchi con Serra Angel (5), lui blocca con Healer's Hawk (1): muoiono tutti e due
        ang, hawk = [816, False, False, 4, 4, 20], [814, False, False, 1, 1, 21]
        DA._MANA["lk13"] = dict(azioni=[], ultima=None, momenti=[["comb", 3, 1, foto([], c1=[ang], c2=[hawk]), dict(att=[[20, 2]], blocchi=[[21, 20]])],
                                                               ["fine", 3, 1, foto([], c1=[], c2=[])]])
        x13 = dict(partita="lk13", seat=1, inizia=True, vinta=False, quando=datetime.datetime(2026, 11, 13))
        casi.append(("L5: perdi un 5 mana per il suo 1 mana", per_partita(x13)["l5"] == [3]))
        DA._MANA["lk14"] = dict(DA._MANA["lk13"], momenti=[DA._MANA["lk13"]["momenti"][0], ["fine", 3, 1, foto([], c1=[], c2=[hawk])]])
        casi.append(("negativa L5: se muore solo il tuo non e' uno scambio", per_partita(dict(x13, partita="lk14"))["l5"] == []))
        casi.append(("il filtro dice Yes e No", valore(dict(leak=lk), "l7") == "Yes" and valore(dict(leak=dict(l7=False)), "l7") == "No"))
        # R10: il tracker
        q_ = lambda i: datetime.datetime(2026, 11, 1) + datetime.timedelta(hours=i)
        rt = [dict(quando=q_(i), vinta=i % 2 == 0, leak=dict(l1=[3] if i < 10 else [], l7=False)) for i in range(60)] + [dict(quando=q_(99), vinta=True, leak=None)]
        tr = {t["k"]: t for t in tracker(rt)}
        casi.append(("R10: L1 in 10 partite su 60 (16,7%), win rate con 50% e senza 50%; tutte nelle prime 10: nelle ultime 50 lo 0%",
                     tr["l1"]["con"] == 10 and tr["l1"]["tasso"] == 16.7 and tr["l1"]["tasso_rec"] == 0.0 and tr["l1"]["tasso_prima"] == 100.0
                     and tr["l1"]["n"] == 60))
        casi.append(("negativa R10: una partita senza i momenti non conta; un leak mai visto ha tasso 0 e nessun win rate con", tr["l2"]["con"] == 0
                     and tr["l2"]["wr_con"] is None and tr["l2"]["tasso"] == 0.0))
    finally:
        DA._MANA.clear(); DA._MANA.update(salva)
        DA._NOMI_GRP.clear(); DA._NOMI_GRP.update(nomi)
    for n, ok in casi:
        print(("ok    " if ok else "ROSSO ") + n)
    print(f"{sum(1 for _n, ok in casi if ok)}/{len(casi)}")
    return all(ok for _n, ok in casi)


if __name__ == "__main__":
    sys.exit(0 if prova() else 1)
