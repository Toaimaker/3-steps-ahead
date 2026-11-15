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
import re  # noqa: E402
import dati_analizzatore as DA  # noqa: E402

VITA_ALTA = 10          # da qui in su un chump block costa una carta per vite che non servono ancora (grado C)
VITA_CONCEDI = 8        # L7: sotto, una concessione e' di solito una partita persa davvero (grado C)
# i testi dei leak (15 nov 2026, Autore: «la scheda leak deve avere definizioni dei leak e descrizioni moooolto più intendibili»): per ognuno il nome
# in parole di tutti i giorni (NOMI), cosa si cerca nella partita (SPIEGA), perche' costa (PERCHE), un esempio (ESEMPIO) e come si corregge (COME)
NOMI = {"l1": "You skipped a land drop", "l2": "You left mana unused with a creature in hand", "l3": "You cast a creature before attacking",
        "l4": "You chump blocked while your life was high", "l5": "You traded a bigger creature for a smaller one",
        "l6": "You waited to cast an instant when they couldn't answer it", "l7": "You conceded a game you could still win",
        "l8": "You tapped the wrong lands", "l9": "You didn't attack when nothing could block",
        # il Leak Finder (15 nov 2026, Autore: «cambia anche il nome della scheda, da ora non si chiama più performance ma leak finder, deve essere un leak
        # finder a tutti gli effetti»): i leak della pagella dell'enciclopedia e quelli di un leak finder per Magic (mulligan, sequenza delle pescate, mana tenuto)
        "l10": "You cast an instant on your own turn for no reason", "l11": "You missed lethal", "l12": "You kept a hand you should have mulliganed",
        "l13": "You mulliganed a hand you should have kept", "l14": "You played your land before your card draw",
        "l15": "You held mana open and never used it"}
ORDINE = ("l1", "l2", "l3", "l4", "l5", "l6", "l7", "l8", "l9", "l10", "l11", "l12", "l13", "l14", "l15")
PARTITA = {"l7", "l12", "l13"}       # i leak della partita intera (gli altri hanno i turni)
SPIEGA = {"l1": "At the end of one of your turns you still had a land in your hand, but you hadn't played a land that turn.",
          "l2": "At the end of your turn you had enough untapped lands, of the right colors, to cast a creature in your hand, and you didn't cast it. "
                "Mana kept for the opponent's turn is not counted: if on their turn you cast something, that mana is taken away first and it is a leak "
                "only if the creature still fit; if you held an instant or a flash card those lands could pay, it was held on purpose (if you then never "
                "used it, that is the leak «held mana open and never used it»); an ability activated on their turn clears it.",
          "l3": "On a turn you attacked, you first cast a creature (without haste) in your first main phase, and only then attacked. A creature that "
                "helps that attack is not counted: directly (its entry pumps, puts counters, taps or removes a blocker, makes them discard, shows you "
                "their hand or draws you a card; its ability pumps your team or triggers at the beginning of combat) or through your other cards (a "
                "lifegain payoff and you gained life in the attack, a card that triggers when a creature enters and pumps, deals damage or gains life "
                "for a payoff, a payoff for their life loss or for your creatures dying that the combat turned on).",
          "l4": f"You blocked, your blocker died and their attacker survived. You had {VITA_ALTA} or more life and the attack would not have killed you. "
                "Not counted: a block that saves your planeswalker or battle, a token blocking, a creature that leaves something when it dies.",
          "l5": "In one of your combats (attacking or blocking) creatures died on both sides, and what you lost was worth at least 2 more than what "
                "they lost, without killing more of their cards than you lost. A creature is worth its body ((power + toughness) / 2, counters "
                "included), at least its mana cost if it's a card with no enter-the-battlefield effect (the effect you already got doesn't die "
                "with it); tokens and animated lands are worth their body; a creature that leaves something when it dies is worth half (a quarter "
                "if it comes back), and each death payoff on the battlefield takes 1 off. It doesn't count if the opponent cast an instant that "
                "turn or targeted one of the creatures in the fight: a trick or a removal chose that trade, not you.",
          "l6": "At the end of your turn the opponent had every land tapped, so they couldn't respond. You waited and cast your instant on their turn, "
                "when their mana was back (combat tricks and counterspells don't count).",
          "l7": f"You conceded with {VITA_CONCEDI} or more life, more than twice the power they had on the battlefield, and at least one card in your hand.",
          "l8": "At the end of your turn your untapped lands were enough to cast a card in your hand, but they made the wrong colors. If you had tapped "
                "different lands for the spells you cast, the right colors would have stayed open.",
          "l9": "One of your creatures could attack, the opponent had every land tapped and no untapped creature to block, and you didn't attack.",
          "l10": "You cast an instant or a flash creature during your own main phase when it could have waited for their turn, and at the end of your turn "
                 "you still had a spell in hand that the same mana would have cast (or the flash creature died before it ever attacked).",
          "l11": "Your creatures had enough power to kill the opponent that turn, even after their untapped creatures blocked your biggest ones, and they "
                 "were still alive at the end of your turn.",
          "l12": "You kept your 7 cards, but the numbers say that hand should go back: in Limited no lands or 6-7 lands (17Lands data), in Constructed "
                 "0-1 or 6-7 lands (the usual rule for 60-card decks).",
          "l13": "You sent back your 7 cards, but the numbers say that hand was a keep: 2-5 lands in Limited, 3-4 lands in Constructed.",
          "l14": "On your turn you played your land first and then cast a spell that draws, scries or surveils, even though you could already pay for "
                 "that spell before playing the land.",
          "l15": "At the end of the opponent's turn you still had untapped lands and an instant or a flash creature you could pay for, and you cast nothing "
                 "during their turn."}
PERCHE = {"l1": "Every land you don't play is mana you lose for the rest of the game: from the next turn you are one land behind on everything you want to cast.",
          "l2": "A creature not cast this turn is a turn of attacking and blocking you never get back, and the mana you didn't use is simply gone.",
          "l3": "That creature can't attack this turn anyway. Casting it first shows your opponent what you had and that your mana is spent, so they block "
                "knowing you have no tricks.",
          "l4": "You gave away a card to save a few life points you didn't need yet. In a long game cards win; life matters only when it gets low.",
          "l5": "You spent more mana and a better card to get rid of a cheaper one: after the trade you are behind on the battlefield.",
          "l6": "While they are tapped out they can't counter, protect or answer. By waiting you gave them back the chance to respond.",
          "l7": "With that much life you had several more turns to draw an answer. Conceding throws away every one of those chances.",
          "l8": "The same lands could have cast one more spell that turn: a wrong tap costs you a whole card's worth of tempo.",
          "l9": "That damage was free: nothing could block it and they had no mana for a trick. (We can't see your hand: sometimes staying home is right, "
                "for example to block a lethal counter-attack.)",
          "l10": "Instants are strongest on the opponent's turn: they surprise, they dodge sorcery-speed answers, and on your turn the mana is better "
                 "spent on your other spells.",
          "l11": "You could have ended the game that turn. Every extra turn you give the opponent is a chance for them to come back.",
          "l12": "Hands with too few or too many lands lose more often than a fresh hand of 6 cards.",
          "l13": "Each mulligan costs you a card: a normal 7 wins more often than a random 6.",
          "l14": "Casting the draw spell first shows you one more card before you choose which land to play: maybe a land you'd rather play, or a spell "
                 "that needs a color you'd keep open.",
          "l15": "Keeping mana open only pays off if you use it. If nothing happened worth answering, you should spend it at the end of their turn: "
                 "otherwise that mana is lost."}
ESEMPIO = {"l1": "Turn 4: you have a Forest in hand, you cast a 3-drop with your three lands and forget the Forest. On turn 5 you have 4 lands instead of 5.",
           "l2": "You end your turn with 3 untapped lands and a 3-mana creature in your hand.",
           "l3": "You cast a 2/2, then attack with your 3/3. The opponent sees your lands are tapped and blocks without fear of a trick.",
           "l4": "At 16 life you block their 4/4 with your 1/1 just to avoid 4 damage, and lose the 1/1.",
           "l5": "Your 5-mana 4/4 blocks their 2-mana 2/2 with deathtouch: both die.",
           "l6": "They tap out for a big creature. On your turn you could kill it safely, but you wait for their turn and they save it with a trick.",
           "l7": "At 12 life, facing a single 4/4 and holding 2 cards, you concede.",
           "l8": "You have Island, Island, Mountain, Mountain. You pay a {1}{U} spell with both Islands: now the {1}{U} instant in your hand can't be cast. "
                 "Paying with Island + Mountain would have left Island + Mountain open for it.",
           "l9": "They tapped out and their only creature is tapped: your 3/3 stays home.",
           "l10": "On your turn you flash in a 2/2, and now you can't cast the 2-mana creature still in your hand.",
           "l11": "They are at 5 with one untapped blocker. You have a 4/4, a 3/3 and a 2/2: attacking with all three deals at least 5, but you attack "
                  "with one.",
           "l12": "You keep 7 cards with one land and six spells, hoping to draw lands.",
           "l13": "You send back a 7 with 3 lands because the spells look weak.",
           "l14": "You play a Plains, then cast a draw spell with your Island: it finds a dual land you would rather have played this turn.",
           "l15": "You keep 3 lands open for a removal spell, they play nothing worth killing, and you pass the turn back without casting the card-draw "
                  "instant in your hand."}


# R10, il leak tracker (13 nov 2026, come il Leak Tracker di PokerTracker): come si corregge ogni leak, una riga (dai coach citati sopra; grado C)
COME = {"l1": "Play a land every turn, unless you are holding it on purpose (a landfall card, a bluff).",
        "l2": "At the end of your turn count your untapped lands against your hand: if a creature fits, cast it, unless you are holding up an instant for "
              "their turn (and then use it).",
        "l3": "Attack first, then cast your creatures in the second main phase. Cast it before combat only when it changes the attack: it pumps, "
              "taps a blocker, feeds a payoff that the attack will trigger, or shows you something you need to decide the attack.",
        "l4": "While your life is high, take the damage: block to trade creatures, not to throw one away. Start chump blocking only when the life total "
              "matters.",
        "l5": "Before blocking or attacking into a block, compare what you lose with what they lose: avoid trading an expensive card for a cheap one "
              "or a token. Trading a creature that already gave you its value when it entered, or one that leaves something when it dies, is fine.",
        "l6": "Cast your instants when they can't answer: on your turn while they are tapped out, or at a moment they can't respond.",
        "l7": "With life and cards in hand, play it out: many games turn on one draw.",
        "l8": "Before tapping, look at the cards left in your hand: tap the lands whose colors you won't need, and leave open the colors you will.",
        "l9": "When they are tapped out with no untapped blockers, attack with what is ready, unless you need it home against a lethal swing back.",
        "l10": "Hold instants and flash creatures for their turn, unless they win a combat or answer a threat right now.",
        "l11": "Before passing the turn, add up your power and subtract what their untapped blockers can stop: if it is enough to kill, attack with "
               "everything.",
        "l12": "Mulligan the hands the numbers say to mulligan, even when the spells look good.",
        "l13": "Keep the hands the numbers say to keep, even when the spells look weak.",
        "l14": "Cast the draw or scry spell first, then choose which land to play.",
        "l15": "If you held mana up and they gave you no reason to use it, use it at the end of their turn: draw, flash in a creature, remove a threat."}
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
        out.append(dict(k=k, nome=NOMI[k], spiega=SPIEGA[k], perche=PERCHE[k], esempio=ESEMPIO[k], come=COME[k], n=len(rr), con=len(con), tasso=tasso(rr), wr_con=w_c, wr_senza=w_s,
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
        # il mana tenuto per il suo turno (15 nov 2026, Autore: «quel mana poteva essere utile per giocare una spell nel turno avversario, come
        # sistemiamo questo dilemma?»): se nel suo turno dopo hai lanciato qualcosa, quel mana si toglie e il leak c'e' solo se la creatura ci stava lo
        # stesso; un'abilita' attivata nel suo turno (costo che non si legge) chiude il dubbio a tuo favore; se non hai lanciato niente ma in mano avevi un
        # istantaneo o un flash che quelle terre pagavano, il mana era tenuto apposta: non e' L2 (se poi non l'hai usato e' L15)
        spese_suo = [c_ for c_ in (_costo(_nome(g)) for t_, s_, g, _f in d.get("fasi") or [] if t_ == t + 1 and s_ == seat) if c_]
        abil_suo = any(a_[0] == t + 1 and a_[1] == seat for a_ in d.get("attivate") or [])
        tenuti = [n for n in mano if _costo(n) and ("Instant" in (_carta(n).get("tipo") or "") or "Flash" in (_carta(n).get("testo") or ""))
                  and _paga([_costo(n)], stap)]
        if abil_suo or (not spese_suo and tenuti):
            pass
        elif any(_paga([_costo(n)] + spese_suo, stap) for n in creature if 0 < len(_costo(n))):
            l2.append(t)
        if t not in l2 and not any(_paga([_costo(n)], stap) for n in creature if 0 < len(_costo(n))):       # L8: non la pagano le stappate, ma le terre di adesso, ripartite su quello che hai lanciato nel turno, si'
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
        if (s_ == seat and t in attaccato and fase == "Phase_Main1" and "Creature" in tipo and "Haste" not in testo and "haste" not in testo
                and not aiuta_attacco(n, t, seat, d, mom)):
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
            if scambio_cattivo(_scambio(d, dec, seat)):
                l5.append(dec["t"])
    l7 = False
    ult = d.get("ultima")
    if x.get("fine") == "You conceded" and ult and isinstance(ult[-1], dict):
        f = ult[-1]
        vita = (f.get("v") or [None, None])[a]
        in_mano = len((f.get("m") or [[], []])[a])
        l7 = vita is not None and vita >= VITA_CONCEDI and vita > 2 * _forza((f.get("c") or [[], []])[b]) and in_mano >= 1
    import mana_aperto as MA
    l9 = [w["t"] for w in MA.finestre_non_att(d, seat) or [] if w["scoperto"]]
    # i leak del Leak Finder (15 nov 2026)
    import tempismo as TM
    l10 = list((TM.per_partita(x) or {}).get("perso") or [])
    l11 = [w["t"] for w in MA.letali_mancati(d, seat) or []]
    l12, l13 = mulligan(x)       # qui la riga non ha ancora la mano: valore() li rifa' sulla riga intera
    l14, l15 = _sequenza(d, seat, mom), _mana_tenuto(d, seat, mom)
    return dict(l1=sorted(set(l1)), l2=sorted(set(l2)), l3=sorted(set(l3)), l4=sorted(set(l4)), l5=sorted(set(l5)), l6=sorted(set(l6)), l7=l7,
                l8=sorted(set(l8)), l9=sorted(set(l9)), l10=sorted(set(l10)), l11=sorted(set(l11)), l12=bool(l12), l13=bool(l13), l14=l14, l15=l15)


# L3 e le sinergie (15 nov 2026, Autore: «alcuni leak non tengono conto di sinergie, per esempio creature che entrano prima della fase di combattimento
# per potenziare altre in maniera diretta o indiretta»): una creatura lanciata prima dell'attacco non e' un leak se serve all'attacco di quel turno. Dal
# testo delle carte (grado C) e da quello che e' successo nel combattimento (le vite, le creature morte), mai da un'ipotesi:
# - diretta, la sua entrata: potenzia o mette segnalini, tappa, toglie o fa combattere una creatura, fa scartare o guarda la sua mano, fa pescare o
#   scry/surveil (sai cosa hai prima di attaccare), empower Jace, una Role, da' una parola chiave, rende giocabile una carta;
# - diretta, la sua statica: «creatures you control get/have», «attacking creatures», exalted, un innesco a inizio combattimento o all'attacco, raddoppia
#   la vita che lui perde nel tuo turno, pesca quando lo colpisci in combattimento;
# - un payoff che il combattimento ha acceso: «whenever you gain life» e nel turno hai guadagnato vita dopo l'inizio del combattimento; «whenever an
#   opponent loses life» e lui ha perso vita; «whenever a creature you control dies» e ne e' morta una nel combattimento;
# - indiretta, le tue carte: un tuo permanente in campo con un innesco quando entra una creatura (o un artefatto, un incantesimo, del tipo giusto) o
#   quando lanci una creatura, che fa qualcosa da combattimento, o fa guadagnare vita con un payoff della vita in campo.
_RX_EFFETTO = re.compile(r"\+\d+/\+\d+|\+1/\+1 counter|\bgets? \+|\btap (?:target|up to)|\bdestroy target|\bexile (?:target|up to one target) (?:creature|nonland|permanent)|"
                         r"deals? (?:\d+|x|that much) damage|\bfights?\b|\bdiscards?\b|look at target opponent's hand|\bdraws?\b|\bscry\b|\bsurveil\b|"
                         r"\bempower\b|\brole token|gains? (?:flying|trample|menace|haste|first strike|double strike|lifelink|deathtouch|indestructible|"
                         r"hexproof)|an opponent controls[^.]*owner's hand|\bloses? \d+ life|can't block|you may (?:play|cast) (?:that|it|the exiled)", re.I)
_RX_STATICA = re.compile(r"creatures you control (?:get|have)|other [^.]{0,40}you control (?:get|have)|attacking creatures|\bexalted\b|"
                         r"beginning of combat on your turn|whenever (?:a|another|one or more) creatures? you control attacks?|"
                         r"would lose life during your turn|(?:are|is) dealt combat damage during your turn", re.I)
_RX_VITA = re.compile(r"whenever you gain life|gain life for the first time", re.I)
_RX_PERDE = re.compile(r"whenever (?:an|each) opponent loses life|whenever an opponent is dealt", re.I)
_RX_MUORE = re.compile(r"whenever (?:this creature or )?(?:another|a) (?:nontoken )?creature you control dies|whenever (?:a|another) creature dies", re.I)
_RX_ENTRA = re.compile(r"whenever (?:another |a |an |one or more )?(?:nontoken )?(?:(\w+) )?(creature|artifact|enchantment)s?(?: card)?s? "
                       r"(?:you control )?enters?|whenever you cast a (?:(\w+) )?creature spell", re.I)


def _righe(n):
    """Le frasi del testo della carta (il testo qui non va a capo fra le abilita'); una frase che segue un'entrata e comincia con If, Then, Until,
    When you do o un punto elenco resta attaccata (Nurturing Pixie: «If a permanent was returned this way, put a +1/+1 counter»)."""
    testo = (_carta(n).get("testo") or "").replace("\n", " ")
    out = []
    for f in re.split(r"(?<=[.)])\s+|\s+(?=•)", testo):
        f = f.strip()
        if not f:
            continue
        if out and re.match(r"(?:if |then |until |when you do|•|it |that )", f, re.I) and _entrata(out[-1]):
            out[-1] += " " + f
        else:
            out.append(f)
    return out


def _entrata(r_):
    return bool(re.search(r"\bwhen [^,.]{0,60}\benters?\b", r_, re.I))


def aiuta_attacco(n, t, seat, d, mom):
    """Perche' la creatura n, lanciata prima dell'attacco del turno t, serve a quell'attacco (una frase), o None (allora e' L3)."""
    righe = _righe(n)
    for r_ in righe:
        if _entrata(r_) and _RX_EFFETTO.search(r_):
            return "its entry helps the attack"
        if not _entrata(r_) and _RX_STATICA.search(r_):
            return "its ability helps the attack"
    a, b = seat - 1, 2 - seat
    comb = next((m for m in mom if m[0] == "comb" and m[1] == t and isinstance(m[3], dict)), None)
    fine = next((m[3] for m in mom if m[0] == "fine" and m[1] == t and isinstance(m[3], dict)), None)
    v0 = (comb[3].get("v") if comb else None) or [None, None]
    v1 = (fine.get("v") if fine else None) or [None, None]
    guadagno = v0[a] is not None and v1[a] is not None and v1[a] > v0[a]
    perde = v0[b] is not None and v1[b] is not None and v1[b] < v0[b]
    morte = False
    if comb and fine:
        resta = {c[5] for c in (fine.get("c") or [[], []])[a] if len(c) > 5}
        ids = {x_[0] for x_ in (comb[4] or {}).get("att") or []} | {x_[0] for x_ in (comb[4] or {}).get("blocchi") or []}
        morte = any(len(c) > 5 and c[5] in ids and c[5] not in resta for c in (comb[3].get("c") or [[], []])[a])
    testo = " ".join(righe)
    if (_RX_VITA.search(testo) and guadagno) or (_RX_PERDE.search(testo) and perde) or (_RX_MUORE.search(testo) and morte):
        return "the attack fed its payoff"
    # le tue carte in campo (il tavolo del combattimento, senza una copia della creatura appena lanciata)
    campo = [_nome(c[0]) for c in ((comb[3].get("c") or [[], []])[a] if comb else [])]
    if n in campo:
        campo.remove(n)
    tipo_n = (_carta(n).get("tipo") or "")
    payoff_vita = bool(_RX_VITA.search(testo)) or any(_RX_VITA.search(" ".join(_righe(m_))) for m_ in campo if m_)
    for m_ in set(campo):
        if not m_ or DA.e_terra(m_):
            continue
        for r_ in _righe(m_):
            k = _RX_ENTRA.search(r_)
            if not k:
                continue
            quale = (k.group(2) or "creature").lower()
            sotto = (k.group(1) or k.group(3) or "").lower()
            if quale != "creature" and quale.capitalize() not in tipo_n:
                continue
            if sotto and sotto not in ("nontoken", "another", "other") and sotto not in tipo_n.lower():
                continue
            effetto = r_[k.end():]
            if _RX_EFFETTO.search(effetto) or (re.search(r"gains? \d+ life", effetto, re.I) and payoff_vita):
                return f"it triggered {m_}"
    return None


def mulligan(x):
    """L12 e L13 per formato: (tenuta una 7 che il formato manda in mulligan, rimandata una 7 che il formato tiene). Nel Limited la tabella misurata,
    nel Constructed la regola a 60 carte (dati_analizzatore.mull_tabella, mull_60)."""
    if x.get("tipo") == "Constructed":
        m_ = DA.mull_60(x)
        return m_ == DA.ORDINE_MULL_60[2], m_ == DA.ORDINE_MULL_60[3]
    m_ = DA.mull_tabella(x)
    return m_ == DA.ORDINE_MULL_TAB[2], m_ == DA.ORDINE_MULL_TAB[3]


RX_GUARDA = re.compile(r"draws? (?:a|one|two|three|\d+) cards?|\bscry \d|\bsurveil \d", re.I)


def _guarda(n):
    """Una magia che fa pescare, scry o surveil (dal testo, grado C)."""
    c = _carta(n) or {}
    return bool(n) and "Land" not in (c.get("tipo") or "") and bool(RX_GUARDA.search(c.get("testo") or ""))


def _sequenza(d, seat, mom):
    """L14: nei tuoi turni, la terra giocata prima di una magia che fa pescare, scry o surveil, che costava al massimo le terre che avevi gia' a fine del
    tuo turno prima (la potevi lanciare prima della terra). L'ordine e' quello delle azioni del log. -> [turni]."""
    attivo = {}
    for m in mom:
        if m[0] in ("fine", "comb", "spell"):
            attivo.setdefault(m[1], m[2])
    terre_fine = {f[0]: f[3] for f in d.get("fine") or [] if f[1] == seat}
    out = []
    per_t = {}
    for t, s_, cosa, g_, _tp in d.get("azioni") or []:
        if s_ == seat and attivo.get(t) == seat and cosa in ("terra", "magia"):
            per_t.setdefault(t, []).append((cosa, g_))
    for t, az in per_t.items():
        prima = terre_fine.get(t - 2)
        if not prima:
            continue
        visto_terra = False
        for cosa, g_ in az:
            if cosa == "terra":
                visto_terra = True
            elif visto_terra:
                n = _nome(g_)
                c_ = (_carta(n) or {}).get("cmc") if n else None
                if c_ is not None and c_ <= prima and _guarda(n):
                    out.append(t)
                    break
    return sorted(out)


def _mana_tenuto(d, seat, mom):
    """L15: a fine del suo turno avevi ancora le terre stappate e in mano un istantaneo da fine turno (rimozione, pescata, scry o surveil) o una creatura
    con flash che pagavano (i colori non contano, grado C), e nel suo turno non hai lanciato niente. -> [turni di Arena del suo turno]."""
    import variabili_c as VC
    a = seat - 1
    lanci = {t for t, s_, _g, _f in d.get("fasi") or [] if s_ == seat}
    out = []
    for m in mom:
        if m[0] != "fine" or m[2] == seat or not isinstance(m[3], dict) or m[1] in lanci:
            continue
        f = m[3]
        stap = sum(1 for c in (f.get("c") or [[], []])[a] if _terra(c[0]) and not c[1])
        if stap < 1:
            continue
        for g in (f.get("m") or [[], []])[a]:
            n = _nome(g)
            cc = _carta(n) if n else {}
            tipo, testo, cmc = cc.get("tipo") or "", cc.get("testo") or "", cc.get("cmc")
            if not cmc or cmc > stap:
                continue
            flash = "Creature" in tipo and "Flash" in testo
            fine_turno = "Instant" in tipo and "counter target" not in testo.lower() and (_guarda(n) or VC.rimozione(n))
            if flash or fine_turno:
                out.append(m[1])
                break
    return out


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


# L5 e le sinergie (15 nov 2026, Autore: «alcuni leak non tengono conto di sinergie»; voce del Memo_In_Sospeso «L'analisi degli scambi»). Fino a quel
# giorno una creatura valeva il suo costo e una pedina zero: una pedina 5/5, una terra animata 6/3 o un Goblin 3/3 equipaggiato non contavano, il suo
# trucco in combattimento diventava uno scambio tuo, e una creatura che aveva gia' dato il suo valore entrando (Mindseeker Oculus, Stockpiling Celebrant)
# pesava quanto il costo pieno. Ora il valore di una creatura che muore:
# - il corpo: (forza + costituzione) / 2 di quel momento, segnalini compresi; una carta senza effetto d'entrata vale almeno il suo costo (perderla e'
#   una carta in meno), una con l'effetto d'entrata il solo corpo (l'entrata l'hai gia' incassata), una pedina o una terra animata il solo corpo;
# - meno quello che lascia morendo: «when this creature dies» meta' del valore, se torna in campo (Unstoppable Slasher) un quarto;
# - meno 1 per ogni payoff in campo del suo controllore che scatta quando muore una sua creatura (Vengeful Bloodwitch);
# e lo scambio non conta se l'avversario ha lanciato un istantaneo o una creatura con flash in quel turno, o ha preso di mira una delle creature del
# combattimento (un trucco, una rimozione: lo scambio non l'hai scelto tu).
_RX_LASCIA = re.compile(r"when (?:this creature|[^,.]{0,30}) dies", re.I)
_RX_TORNA = re.compile(r"dies[^.]*return (?:it|this card|[^.]{0,20}) to the battlefield", re.I)


def valore_morta(c, payoff=0):
    """Il valore di una creatura del tavolo ([grpId, tappata, pedina, forza, costituzione, id...]) che muore in uno scambio (L5)."""
    n = _nome(c[0])
    cc = _carta(n) if n else {}
    corpo = (max(0, c[3] or 0) + max(0, c[4] or 0)) / 2 if len(c) > 4 else 0
    v = corpo
    if not c[2] and not DA.e_terra(n or "") and not any(_entrata(r_) and _RX_EFFETTO.search(r_) for r_ in _righe(n)):
        v = max(corpo, cc.get("cmc") or 0)
    testo = cc.get("testo") or ""
    if _RX_TORNA.search(testo):
        v *= 0.25
    elif _RX_LASCIA.search(testo):
        v *= 0.5
    return max(0.0, v - payoff)


def _trucco(mom, t, seat, ids):
    """Nel turno t l'avversario ha lanciato un istantaneo o un flash, o ha preso di mira una delle creature del combattimento?"""
    for m_ in mom:
        if m_[0] != "spell" or m_[1] != t or not m_[4] or m_[4].get("chi") == seat:
            continue
        if set(m_[4].get("bers") or []) & ids:
            return True
        n = _nome(m_[4].get("g"))
        cc = _carta(n) if n and not m_[4].get("ab") else {}
        if "Instant" in (cc.get("tipo") or "") or ("Creature" in (cc.get("tipo") or "") and "Flash" in (cc.get("testo") or "")):
            return True
    return False


def _scambio(d, dec, seat):
    """L5: (valore delle tue creature perse, delle sue) nel combattimento della decisione, dai momenti di mana_aperto; None se non si sa o se il suo
    trucco ha deciso lo scambio."""
    mom = d.get("momenti") or []
    m = next((m_ for m_ in mom if m_[0] == "comb" and m_[1] == dec["t"]), None)
    dopo = next((m_[3] for m_ in mom if m_[0] == "fine" and m_[1] == dec["t"]), None)
    if not m or not isinstance(m[3], dict) or not isinstance(dopo, dict):
        return None
    resta = {c[5] for lato in dopo.get("c") or [[], []] for c in lato if len(c) > 5}
    info = m[4] or {}
    ids = {a_[0] for a_ in info.get("att") or []} | {b_[0] for b_ in info.get("blocchi") or []}
    if _trucco(mom, dec["t"], seat, ids):
        return None
    val, carte = [0.0, 0.0], [0, 0]
    for lato_i, lato in enumerate(m[3].get("c") or [[], []]):
        payoff = sum(1 for c in lato if not _terra(c[0]) and _RX_MUORE.search(_carta(_nome(c[0])).get("testo") or ""))
        for c in lato:
            if len(c) > 5 and c[5] in ids and c[5] not in resta:
                i_ = 0 if lato_i == seat - 1 else 1
                val[i_] += valore_morta(c, payoff)
                carte[i_] += 0 if c[2] else 1
    return val[0], val[1], carte[0], carte[1]


def scambio_cattivo(v):
    """Lo scambio di _scambio e' un leak? Le tue perdite valgono almeno 2 piu' delle sue, e non hai tolto piu' carte di quante ne hai perse (due pedine
    1/1 che fermano due sue carte non sono uno scambio cattivo, anche se le sue valevano poco)."""
    return v is not None and v[0] >= v[1] + 2 and v[2] >= v[3]


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
        # le sinergie (15 nov 2026): bloccare per salvare un tuo planeswalker o una battaglia non e' un chump per le vite; e una pedina, o una creatura
        # che morendo lascia qualcosa (o con un tuo payoff della morte in campo), non e' una carta buttata
        bloccati = set()
        for b_ in m[4].get("blocchi") or []:
            bloccati.update(b_[1] if isinstance(b_[1], list) else [b_[1]])
        if any(len(a_) > 1 and a_[0] in bloccati and a_[1] not in (1, 2) for a_ in m[4]["att"]):
            continue
        dopo = next((m_[3] for m_ in mom if m_[0] == "fine" and m_[1] == dec["t"] and isinstance(m_[3], dict)), None)
        if dopo is not None:
            resta = {c[5] for lato in dopo.get("c") or [[], []] for c in lato if len(c) > 5}
            bl_ids = {b_[0] for b_ in m[4].get("blocchi") or []}
            miei = (prima.get("c") or [[], []])[seat - 1]
            payoff = sum(1 for c in miei if not _terra(c[0]) and _RX_MUORE.search(_carta(_nome(c[0])).get("testo") or ""))
            morti = [c for c in miei if len(c) > 5 and c[5] in bl_ids and c[5] not in resta]
            if morti and all(c[2] or valore_morta(c, payoff) < 1 for c in morti):
                continue
        forza_att = _forza((prima.get("c") or [[], []])[2 - seat], att_ids)
        if vita is not None and vita >= VITA_ALTA and forza_att < vita:
            out.append(dec["t"])
    return out


def valore(x, k):
    """Il valore del filtro: «Yes» o «No» (None senza i momenti)."""
    lk = x.get("leak")
    if lk is None:
        return None
    if k in ("l12", "l13"):     # il mulligan, sulla riga intera (la mano e il tipo ci sono solo li')
        return "Yes" if mulligan(x)[0 if k == "l12" else 1] else "No"
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
        # L4 e le sinergie (15 nov 2026): il blocco che salva un tuo planeswalker, e la pedina che blocca, non sono carte buttate per le vite
        DA._MANA["lk32"] = dict(DA._MANA["lk3"], momenti=[["comb", 4, 2, foto([], v=(15, 20), c1=[tua], c2=[sua]), dict(att=[[50, 77]], blocchi=[[60, 50]])],
                                                          DA._MANA["lk3"]["momenti"][1]])
        casi.append(("negativa L4: bloccare l'attacco al tuo planeswalker non e' un chump per le vite", per_partita(dict(x3, partita="lk32"))["l4"] == []))
        ped_ = [700, False, True, 1, 1, 60]
        DA._MANA["lk33"] = dict(DA._MANA["lk3"], momenti=[["comb", 4, 2, foto([], v=(15, 20), c1=[ped_], c2=[sua]), dict(att=[[50, 1]], blocchi=[[60, 50]])],
                                                          DA._MANA["lk3"]["momenti"][1]])
        casi.append(("negativa L4: una pedina che blocca non e' una carta buttata", per_partita(dict(x3, partita="lk33"))["l4"] == []))
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
        # il mana tenuto per il suo turno (15 nov 2026): due Plains stappate, in mano Healer's Hawk e Raise the Alarm
        DA._NOMI_GRP[818] = "Raise the Alarm"
        DA._MANA["lk20"] = dict(DA._MANA["lk7"], momenti=[["fine", 1, 1, foto([814, 818], c1=[P1, P2, tap(SW)])]])
        casi.append(("negativa L2: con Raise the Alarm in mano e le terre per pagarlo, il mana era tenuto apposta",
                     per_partita(dict(partita="lk20", seat=1, inizia=True))["l2"] == []))
        DA._MANA["lk21"] = dict(DA._MANA["lk20"], fasi=[[1, 1, 813, "Phase_Main2"], [2, 1, 818, "Phase_Ending"]])
        casi.append(("negativa L2: Raise the Alarm lanciato nel suo turno usa le due Plains, Healer's Hawk non ci stava piu'",
                     per_partita(dict(partita="lk21", seat=1, inizia=True))["l2"] == []))
        P3 = [811, False, False, None, None, 5]
        DA._MANA["lk22"] = dict(DA._MANA["lk21"], momenti=[["fine", 1, 1, foto([814, 818], c1=[P1, P2, P3, tap(SW)])]])
        casi.append(("L2: tre Plains, Raise the Alarm nel suo turno ne usa due, la terza pagava Healer's Hawk",
                     per_partita(dict(partita="lk22", seat=1, inizia=True))["l2"] == [1]))
        DA._MANA["lk23"] = dict(DA._MANA["lk8"], attivate=[[2, 1, 811, "Phase_Ending", "Step_End", 2]])
        casi.append(("negativa L2: un'abilita' attivata nel suo turno, col costo che non si legge, chiude il dubbio a tuo favore",
                     per_partita(dict(partita="lk23", seat=1, inizia=True))["l2"] == []))
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
        # L3 e le sinergie (15 nov 2026): la creatura che serve all'attacco non e' un leak, direttamente o con le tue carte
        DA._NOMI_GRP.update({819: "Spellbook Vendor", 820: "Hinterland Sanctifier"})
        DA._MANA["lk24"] = dict(DA._MANA["lk9"], fasi=[[1, 1, 819, "Phase_Main1"]])
        casi.append(("L3 e sinergie: Spellbook Vendor (innesco a inizio combattimento) prima dell'attacco non e' un leak",
                     per_partita(dict(partita="lk24", seat=1, inizia=True))["l3"] == []))
        com_ = lambda vita: [["comb", 1, 1, foto([], v=(20, 20), c1=[[813, False, False, 2, 2, 9]]), dict(att=[[9, 2]], blocchi=[])],
                             ["fine", 1, 1, foto([], v=(vita, 18), c1=[[813, False, False, 3, 3, 9]])]]
        DA._MANA["lk25"] = dict(azioni=[], fasi=[[1, 1, 813, "Phase_Main1"]], momenti=com_(22), ultima=None)
        DA._MANA["lk26"] = dict(DA._MANA["lk25"], momenti=com_(20))
        casi.append(("L3 e sinergie: Ajani's Pridemate prima di un attacco che ti fa guadagnare vita (il payoff si accende); negativa: senza vita "
                     "guadagnata resta un leak", per_partita(dict(partita="lk25", seat=1, inizia=True))["l3"] == []
                     and per_partita(dict(partita="lk26", seat=1, inizia=True))["l3"] == [1]))
        ind_ = lambda campo: [["comb", 1, 1, foto([], c1=campo + [[814, False, False, 1, 1, 12]]), dict(att=[[9, 2]], blocchi=[])]]
        PM, HS = [813, False, False, 2, 2, 9], [820, False, False, 2, 1, 10]
        DA._MANA["lk27"] = dict(azioni=[], fasi=[[1, 1, 814, "Phase_Main1"]], momenti=ind_([PM, HS]), ultima=None)
        DA._MANA["lk28"] = dict(DA._MANA["lk27"], momenti=ind_([[816, False, False, 4, 4, 9], HS]))
        casi.append(("L3 e sinergie indirette: Healer's Hawk entra, Hinterland Sanctifier ti fa guadagnare 1 vita e Pridemate cresce prima "
                     "dell'attacco; negativa: senza un payoff della vita in campo resta un leak",
                     per_partita(dict(partita="lk27", seat=1, inizia=True))["l3"] == []
                     and per_partita(dict(partita="lk28", seat=1, inizia=True))["l3"] == [1]))
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
        # L5 e le sinergie (15 nov 2026): una pedina 4/4 vale il suo corpo, il suo trucco in combattimento non e' uno scambio tuo, una creatura che
        # ha gia' dato il suo valore entrando vale il solo corpo
        pedina = [900, False, True, 4, 4, 21]
        DA._MANA["lk29"] = dict(DA._MANA["lk13"], momenti=[["comb", 3, 1, foto([], c1=[ang], c2=[pedina]), dict(att=[[20, 2]], blocchi=[[21, 20]])],
                                                         ["fine", 3, 1, foto([], c1=[], c2=[])]])
        casi.append(("negativa L5: Serra Angel per una pedina 4/4 non e' uno scambio cattivo (prima la pedina valeva 0)",
                     per_partita(dict(x13, partita="lk29"))["l5"] == []))
        DA._NOMI_GRP[831] = "Giant Growth"
        DA._MANA["lk30"] = dict(DA._MANA["lk13"], momenti=[DA._MANA["lk13"]["momenti"][0], ["spell", 3, 1, foto([]), dict(g=831, chi=2, bers=[21])],
                                                         DA._MANA["lk13"]["momenti"][1]])
        casi.append(("negativa L5: il suo Giant Growth sull'Hawk ha deciso lo scambio, non e' tuo", per_partita(dict(x13, partita="lk30"))["l5"] == []))
        DA._NOMI_GRP[832] = "Mindseeker Oculus"
        oc = [832, False, False, 2, 1, 20]
        DA._MANA["lk31"] = dict(DA._MANA["lk13"], momenti=[["comb", 3, 1, foto([], c1=[oc], c2=[hawk]), dict(att=[[20, 2]], blocchi=[[21, 20]])],
                                                         ["fine", 3, 1, foto([], c1=[], c2=[])]])
        casi.append(("negativa L5: Mindseeker Oculus (l'entrata gia' incassata, resta un 2/1) per un Hawk non e' uno scambio cattivo",
                     per_partita(dict(x13, partita="lk31"))["l5"] == []))
        casi.append(("il filtro dice Yes e No", valore(dict(leak=lk), "l7") == "Yes" and valore(dict(leak=dict(l7=False)), "l7") == "No"))
        # il Leak Finder (15 nov 2026): L14 la terra prima di Opt (pagabile gia' prima), L15 il mana tenuto con Opt in mano e niente lanciato, L12-L13 il mulligan
        mio = lambda t, tot: [t, 1, 0, tot]
        DA._MANA["lk17"] = dict(azioni=[[3, 1, "terra", 811, "L"], [3, 1, "magia", 815, "I"]], fasi=[], fine=[mio(1, 1), mio(3, 2)], ultima=None,
                                momenti=[["fine", 1, 1, foto([])], ["fine", 3, 1, foto([])]])
        casi.append(("L14: al tuo turno 3 di Arena la terra e poi Opt, che con la terra di prima pagavi gia'",
                     per_partita(dict(partita="lk17", seat=1, inizia=True))["l14"] == [3]))
        DA._MANA["lk18"] = dict(DA._MANA["lk17"], azioni=[[3, 1, "magia", 815, "I"], [3, 1, "terra", 811, "L"]])
        casi.append(("negativa L14: prima Opt e poi la terra e' la sequenza giusta", per_partita(dict(partita="lk18", seat=1, inizia=True))["l14"] == []))
        DA._MANA["lk19"] = dict(azioni=[], fasi=[], ultima=None, momenti=[["fine", 2, 2, foto([815], c1=[P1])]])
        casi.append(("L15: a fine del suo turno una Plains stappata e Opt in mano, e nel suo turno niente lanciato",
                     per_partita(dict(partita="lk19", seat=1, inizia=False))["l15"] == [2]))
        DA._MANA["lk20"] = dict(DA._MANA["lk19"], fasi=[[2, 1, 815, "Phase_Ending"]])
        casi.append(("negativa L15: Opt lanciato alla fine del suo turno", per_partita(dict(partita="lk20", seat=1, inizia=False))["l15"] == []))
        casi.append(("L12-L13 per formato: nel Constructed una 7 tenuta a 1 terra e' un leak, nel Limited no (1 terra e' pari); rimandare una 7 a 3 terre e' "
                     "un leak in tutti e due",
                     valore(dict(leak={}, tipo="Constructed", mulligan=0, terre=1), "l12") == "Yes"
                     and valore(dict(leak={}, tipo="Limited", mulligan=0, terre=1), "l12") == "No"
                     and valore(dict(leak={}, tipo="Constructed", mulligan=1, scartate=[3]), "l13") == "Yes"
                     and valore(dict(leak={}, tipo="Limited", mulligan=1, scartate=[3]), "l13") == "Yes"
                     and valore(dict(leak={}, tipo="Limited", mulligan=1, scartate=[0]), "l13") == "No"))
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
