"""La scheda Help, l'ultima (Autore, 10 nov 2026: «creiamo un'ultima scheda che si chiama help / spiega il funzionamento di ogni scheda e i suoi comandi e se arriva
un pulsante in quella pagina comunica di scaricare l'update»).

In testa il riquadro UPDATES: la versione dell'app, l'esito dell'ultimo controllo (aggiornamenti.py), «Check now» e, quando c'e' una versione nuova, il pulsante
arancio «Download update X», che apre il link nel browser. Sotto, una sezione per ogni scheda con cosa fa e i suoi comandi; i comandi del Board si leggono dalla
lista del Board stesso (tavolo_carte.COMANDI), cosi' restano uguali. Quando c'e' un aggiornamento la linguetta Help ha un pallino (su_aggiornamento).
"""
import os
import threading
import webbrowser

import aggiornamenti as AG
from account import ASPETTO_PUBBLICO
from ambiente import PRODOTTO, PUBBLICA, VERSIONE
from tema import CI as C
from widget import ARANCIO, pulsante_solido

def url_donazioni():
    """La pagina delle donazioni: nell'app pubblica da canale.json («sostegno»), in quella di Autore da Distribuzione/config.json («url_sostegno»). "" se
    non c'e' ancora."""
    import json
    from percorsi import ROOT
    for f, k in ((os.path.join(ROOT, "canale.json"), "sostegno"), (os.path.join(ROOT, "Distribuzione", "config.json"), "url_sostegno")):
        try:
            v = str(json.load(open(f, encoding="utf-8")).get(k) or "").strip()
        except (OSError, ValueError):
            continue
        return v if v.startswith(("https://", "http://")) else ""
    return ""


# (chiave, titolo, cosa fa, [(comando, effetto)]): una sezione per scheda, nell'ordine delle linguette
SEZIONI = (
    ("meta", "Meta", ("The most played decks of every format. The starting data comes from Untapped.gg (Arena formats) and MTGGoldfish (paper and MTGO "
                      "formats), 11 Nov 2026; from now on it grows from the games players choose to share.") if PUBBLICA
     else "The most played decks of every format: Arena formats from Untapped, paper and MTGO formats from MTGGoldfish.",
     [("Format", "the format to show"), ("Sort by", "meta share, win rate, price, cards you own, name"),
      ("Click a deck", "opens its deck window, with the sideboard and the link to the original page"),
      ("Star on a deck", "adds it to your Wishlist (gold when it is there); click again to take it out"),
      ("Rank", "the meta at one league, or Diamond + Mythic"), ("View", "switches between the deck cards (Grid) and the Charts"),
      ("Charts", "the top 10 on the left: tick a deck to draw its line, double-click opens it; meta share or win rate, daily or by season (a month)"),
      ("Premier Draft charts", "the whole history of the format and the matchups of the color pairs. Data: 17Lands public datasets "
       "(17lands.com/public_datasets), CC BY 4.0, aggregated by 3 Steps Ahead; not endorsed by 17Lands")]),
    ("mazzi", "Your decks", "Your Arena decks, the decks Arena gave you, your wishlist and your deck building, grouped by format.",
     [("Group title", "opens or closes the group"), ("Show", "only the decks you own, or all"), ("Import", "a list copied from Arena, MTGO or a site goes to the Wishlist"),
      ("Trash", "on a Wishlist or Deck builder card: asks, then removes the deck"), ("Clone", "on a Deck builder card or in its window: a copy of the deck"),
      ("Board view · Edit this deck", "under the list: look at the deck as cards, or open it in the builder"),
      ("Save", "in the builder and on its board nothing is saved by itself; closing with changes asks Save, Don't save or Cancel"), ("Click a deck", "the deck window: list, data, starting hands, export"),
      ("Analysis › Matchups", "the decks you met with this deck, recognized from the cards they showed: record, play and draw; under 5 games it is a hint"),
      ("All games · On the play · On the draw", "the flags on top of Analysis and of the Win rate chart: each one filters its own section"),
      ("Open full analysis", "every card of the deck sortable (seen, cast, win when cast, vs deck, stuck in hand), matchups with the 95% range, mulligans, game length, "
       "the trend week by week and the full lists"),
      ("Hover a card", "under its data, how it played in this deck: cast, win rate when cast, vs deck, stuck in hand"),
      ("Public · Private", "the rule of a group (on its title) and of each deck (on its cover): private decks are never shared"),
      ("Edit · Add to wishlist", "the orange buttons at the top of the deck window"), ("Board", "under the list: the deck as whole cards, to look at and move around"),
      ("Edit", "a Meta or Arena deck gets a copy in Deck builder; the builder opens over the Collection, where the Board can be customized")]),
    ("corso", "Drafter", "Your companion for limited: the event calendar, the pick advice, the three decks, the gate and the chat during the games.",
     [("Launch", "starts the companion and checks the draft data before the first pick"), ("Rare pick", "on: takes every rare and mythic you own fewer than 4 of"),
      ("Chat", "a title per pack, a line per pick: the crown is the pick, the shields the next best"), ("Possible decks", "the three color pairs the drafter sees"),
      ("Select deck", "lights the overlay on Arena's deck builder: green keep or add, red remove"), ("Fix", "with a red gate: the swaps that fix the deck"),
      ("Closed session", "closes the draft by hand: two clicks")]),
    ("performance", "Performance", "An analyzer of your games and situations, from your Arena logs: pick any variables, and the numbers, the chart, the spots "
     "and the matchups follow.",
     [("Constructed · Limited", "which games"), ("+ more", "on each phase of the game, its extra filters: the 1-2 mana spells and creatures in your opening hand and "
                                             "the first turns (missed land drops, curve, first creature); the fight (who attacked first, spells on the other turn, targeted, "
                                             "attacks into untapped lands, passing with lands up); how it ended (who conceded) and creatures lost; the day of the week and "
                                             "the break before the game"),
      ("Smart filters", "by phase of the game: format, event and your deck (By deck); play or draw, mulligans, lands in hand, result; the opponent's archetype and colors; "
                        "length and rank; date, time of day and game in the session"),
      ("Win rate", "type a number: after the other filters, your most recent games going back as long as together they make that win rate (rounded); "
                   "≥ before it: at least that, ≤ after it: at most that; 10 games at least. So the number on top is the one you typed"),
      ("By deck", "pick one of your decks (one box each, with its colors; sorted by most played, win rate or name), against everyone or against one exact color variant of the opponent's deck (vs colors: flag the colors, mono-color to "
                  "five colors or colorless); the table is your deck against every variant you met, click a row to pick it"),
      ("Advanced filters", "the button under the smart filters opens your question: every filter you turn on is a piece with its x, the answer (win rate, "
                           "games, record, interval, against all your games) right below, and the whole page follows it. Two tabs, You and Opponent, each with "
                           "its phases: opening hand (your deck's colors, creatures, instants, sorceries, artifacts, enchantments, planeswalkers, battles; the "
                           "opponent's mulligans), what was cast on each player's turns 1-5 and on the other one's turns (by type and by type and mana value, "
                           "\"Instant · 1\"; pick several in the same turn and the games must have them all), the draws on each turn (the draw step too) and "
                           "the extra draws in one turn, attacks turn by turn (how many "
                           "creatures, the defender's untapped lands), defense (blocked or not), and the game: land drops on curve, lowest life, life and "
                           "creatures at the end of your turns, permanents removed, board wipes, counterspells, graveyard targets, spells cast, when the game "
                           "ended, no creature by a turn"),
      ("Chart", "win rate, games, average turns or mulligan rate; by game or by date; cumulative or the last N games; split by a variable; under it, "
                "Ranks (the league logos where your rank changes) and Trophies (the cup on the game that closes a draft with 7 wins)"),
      ("Games in this situation", "under the chart, one game per row: deck, opponent, result, start, your opening hand and the board at the end; click the "
                                  "hand or the board to open the table of that game, turn by turn, with a replayer: first, back, play and pause, forward, last, "
                                  "the timeline and the speed (keys: space, arrows, Home, End, T); each player's graveyard and exile (click to see them all), the cards that just arrived marked "
                                  "NEW, power and toughness, what happened in that moment, the chart of the game (life and power) and the turning point (★); the bar on the "
                                  "right scrolls the games, the mark on top opens them in their own window; click a column title to sort by it (again to "
                                  "reverse); the opponent's colors are mana symbols"),
      ("Spots", "Preset searches: the basic questions already built (opening hand, attack, defense, instant speed; life, board and removal), each with "
                "its win rate and games; one click turns on all its filters and opens the view that answers it, again to go back. Auto spots: where you "
                "win and lose the most, one or two variables at a time, never the result itself (who conceded, life at 0); strong when it holds even counting how many spots were tried (5% false positives at most); click one to filter it"),
      ("Report", "group by a variable; click a row to filter it, a column to sort"),
      ("Matchups", "your decks against the archetypes you met, or only the meta decks; click a cell to filter it"),
      ("Compare", "A, the situation of your filters, against B: everything else, all your games or a saved situation; the difference, and whether it holds "
                  "(p under 5%) or how many games would tell"),
      ("Cards", "the cards of the games you picked, as cards, in rows: most found in your hand, your turn 1 (opening hand and first draw), drawn on "
                "your turns 2, 3 and 4, your most cast spells, the opponent's most played cards, harder to cast (in your hand and never cast); no lands; under "
                "each card the win rate and record of its games, and in how many; click a card to keep only its games, again to go back; hover to see it big; "
                "Pairs › on each row opens a window with the pairs of cards that come together in the same game (from your turn 1: the pairs of your "
                "opening hand), by win rate, 5 games together at least; Pairs or Trios; click one to keep only the games with them. Rows opens the "
                "little window to pick which rows you see. Also: cast by your turn 4 (its Pairs: what you played together early) and Finishers (the decisive play of your "
                "wins: in the turn with the biggest swing after which you stayed ahead, the spells you cast and the creatures you attacked with, 2+ cards; "
                "the pairs that decided the most wins, with the average swing)"),
      ("Decisions", "every combat as a decision with its outcome, by situation: your attacks (into untapped lands, with everything or holding back, "
                    "blocked or not, by turn) and your defense; for each, how often you lost a creature, how often they did, the trade, the damage, "
                    "their spell before damage and the game win rate; click a row to see its games as a line on the Chart against All. Mulligans: the "
                    "hands you kept by lands on the play and on the draw (click a cell to filter), the hands you sent back, risky keeps, week by week"),
      ("The folders", "the mark on the right of each folder opens it in its own window, even on another screen; close it, or Bring it back, to dock it again"),
      ("Save as my filter", "keep a set of filters: it goes to the My filters folder, one under the other with its numbers; click to apply it, ✕ to "
                            "remove it; your filters are also a B of Compare"),
      ("Clear all filters", "the button under it: back to all your games, the chart and the folder stay as they are"),
      ("The board", "each battlefield as at the table: the creatures in front, toward the middle; behind them the lands on the left and the other "
                    "permanents on the right; hover a card to see it big; the heart is the life, the two cards the cards in hand; the combat moments have arrows from each "
                    "blocker to its attacker (yellow) and from each unblocked attacker to the player (red); the spells and abilities with targets show the card "
                    "on the stack with an arrow to each target (purple); every instant and sorcery has its moment on the stack, before it resolves, with red "
                    "arrows to the permanents it removed (a sweeper shows everything it wiped, marked REMOVED); on top of each graveyard and exile the last "
                    "card in; Moments or Every action on top: every action is the game action by action (each draw, land, spell, damage, life change, token, "
                    "counter, planeswalker ability, scry, attack and block), with the damage on the card it hits, and the last action says how the game ended "
                    "(conceded, 0 life, empty library, poison, time); a target in a graveyard or exile gets its arrow to that pile, a spell on the stack "
                    "is named under the card; a spell you started and cancelled is not counted; where Arena's own log left part of a step out (a message "
                    "too large to write), the action says so and those cards show as Unknown card; the replay opens on the opening hand; PgUp and PgDn jump a turn; "
                    "Combat ›, Spell › and Opp. tapped out › jump to the next one (C, S, O; with Shift the one before); Bookmark (B) marks the spot: it goes to "
                    "My filters, under your filters, one click to watch it again; stepping forward the cards slide from where they were (hand, stack, battlefield, "
                    "graveyard, exile); in the limited games the companion followed, THE COMPANION SAID shows its advice for that turn")]),
    ("risorse", "Resources", "Gold, gems, packs, cards and wildcards: what you earn and spend, the Farmer that plans how to spend them, the roadmap and the ROI.",
     [("Period · Range · Resource", "what the chart and the income show"), ("Farmer", "goal sliders; Create makes the roadmap, Dismiss ends it"),
      ("Gold value", "My win rate or Pack price"), ("Spend gold on packs", "off: gold never buys packs"), ("Roadmap check", "above or below the plan, day by day")]),
    ("collezione", "Collection", "Every card of Arena, the ones you own and the ones you don't, at full size.",
     [("Search", "name, type and rules text; quotes for a phrase"), ("Settings", "format, copies, colors, rarity, type, mana value, sets"),
      ("Owned · Not owned", "the two filters on top"), ("Deck builder", "opens the builder on the right: drag cards into it, or double click them"),
      ("Hover", "the card large")]),
    ("board", "Board", "The deck as whole cards on a sheet, with the network of synergies: parent → child arrows, dots, labels. From the deck window it is "
              "view only; open it from the builder (Edit, then Board) to change it.", None),
    ("hud", "Deck HUD", "The opponent's deck while you play, like a poker HUD but for decks, never for players: the archetype it most likely is, with how sure "
            "(from the spells it has shown and the meta lists), the cards likely still in its 60, what it plays on its turns 2-4, the instants its open mana "
            "can pay, and your record against it on the play and on the draw. In limited: its color pair with the public 17Lands numbers. Nothing about "
            "the opponent is saved, and it stays off in sanctioned competitive events.",
     [("Deck HUD", "the pill in the tab bar: blue ON when the HUD is on, grey OFF when it is off, a green dot and LIVE during a game"),
      ("On Arena only", "the HUD shows only on top of Arena during your games, never in an app window; clicks pass through"),
      ("Click the pill", "two switches: your deck on the left edge (every card: copies left / in the deck, chance to draw it next) and the "
                         "opponent's deck on the right edge (both on by default)"), ("Esc", "closes the switches")]),
    ("social", "Social column", "On the right of every tab: your profile and the friends you follow, read from their public Untapped profile.",
     [("Avatar", "click: a card art or a file"), ("+", "adds a friend by the link of the Untapped profile"), ("✕", "on a friend: removes it")]),
)
BOARD_EXTRA = (("Arrange ▾", "four ways, groups always whole: By mana cost, By groups, By connections (parents above children), Mixed (the network with the groups as nodes, everything else stacked below)"), ("Grid snap", "what you drop lines up on the grid"),
               ("Full page", "the Board on the whole screen"), ("Outliner", "on the left: every card with its copies; click, then F"),
               ("Label (≡ next to a selection)", "a named frame: locked it moves with its cards"), ("HUD", "top right: cards and mana curve; its head closes it"))


def comandi_board():
    """I comandi del Board, dalla lista del Board stesso: un comando nuovo li' compare anche qui."""
    try:
        import tavolo_carte as TC
        return list(TC.COMANDI) + list(TC.COMANDI_MOD) + list(BOARD_EXTRA)
    except Exception:
        return list(BOARD_EXTRA)


class PaginaHelp:
    def __init__(self, tk, padre, F, mana=None, controlla=True):
        self.tk, self.F = tk, F
        self.fr = tk.Frame(padre, bg=C["fondo"])
        self.stato = AG.carica()
        self.su_aggiornamento = None        # la finestra grande: il pallino sulla linguetta
        self._esito = None
        self.ancore = {}
        self.costruisci()
        self.mostra_stato()
        if controlla and AG.da_ricontrollare(self.stato):
            self.fr.after(5000, self.controlla_ora)
        if controlla:
            self.fr.after(AG.OGNI * 1000, self.ogni_tanto)

    def se_sporca(self):
        pass

    # ------------------------------------------------ il disegno
    def costruisci(self):
        tk, F = self.tk, self.F
        testa = tk.Frame(self.fr, bg=C["fondo"]); testa.pack(fill="x", padx=16, pady=(14, 6))
        tk.Label(testa, text="HELP", bg=C["fondo"], fg=C["titolo"], font=F(16, True)).pack(side="left")
        tk.Label(testa, text=f"{PRODOTTO}  v{VERSIONE}", bg=C["fondo"], fg=C["grigio"], font=F(9)).pack(side="left", padx=14, pady=(6, 0))
        # gli aggiornamenti
        box = tk.Frame(self.fr, bg=C["filo"], padx=1, pady=1); box.pack(fill="x", padx=16, pady=(0, 10))
        upd = tk.Frame(box, bg=C["scheda"]); upd.pack(fill="x")
        tk.Label(upd, text="UPDATES", bg=C["scheda"], fg=C["muto"], font=F(7, True)).pack(anchor="w", padx=12, pady=(8, 2))
        riga = tk.Frame(upd, bg=C["scheda"]); riga.pack(fill="x", padx=12, pady=(0, 10))
        self.l_stato = tk.Label(riga, text="", bg=C["scheda"], fg=C["testo"], font=F(10, True), anchor="w", justify="left")
        self.l_stato.pack(side="left")
        self.b_scarica = pulsante_solido(tk, F, riga, "Download update", False, self.scarica, alto=30, bg=C["scheda"], colori=ARANCIO)
        self.b_scarica.configure(width=220)
        self.b_controlla = pulsante_solido(tk, F, riga, "Check now", False, self.controlla_ora, alto=30, bg=C["scheda"])
        self.b_controlla.configure(width=120); self.b_controlla.pack(side="right")
        self.l_note = tk.Label(upd, text="", bg=C["scheda"], fg=C["grigio"], font=F(9), anchor="w", justify="left", wraplength=900)
        if ASPETTO_PUBBLICO:        # l'app pubblica (e quella di Autore, che la vede uguale: 11 nov 2026): la condivisione dei dati si cambia da qui (condividi.py; l'informativa lo promette), col codice da citare per i diritti
            self.riquadro_donazioni()
            self.riquadro_untapped()
            self.riquadro_condivisione()
        # i collegamenti alle sezioni
        link = tk.Frame(self.fr, bg=C["fondo"]); link.pack(fill="x", padx=16, pady=(0, 6))
        for k, titolo, _d, _c in SEZIONI:
            l = tk.Label(link, text=titolo, bg=C["fondo"], fg=C["accento"], font=F(9, True), cursor="hand2", padx=8)
            l.pack(side="left")
            l.bind("<Button-1>", lambda e, k=k: self.vai(k))
        # le sezioni, in un testo solo che scorre (11 nov 2026, sessione Magic 13, Note/Motore_Grafico_App.md): erano ~155 widget dentro una tela, e su Windows
        # ogni widget e' una finestra che lo scorrimento sposta una per una. Il testo ha i suoi stili (titolo, descrizione, comando, effetto), scorre da solo
        # con la rotella e si puo' selezionare e copiare
        from tkinter import font as tkfont
        t = self.cv = tk.Text(self.fr, bg=C["fondo"], fg=C["testo"], relief="flat", bd=0, highlightthickness=0, wrap="word", cursor="arrow", padx=0, pady=0,
                              selectbackground=C["sel"], inactiveselectbackground=C["sel"], exportselection=True)
        t.pack(fill="both", expand=True, padx=(16, 4), pady=(0, 10))
        tutti = [(k, titolo, descr, comandi if comandi is not None else comandi_board()) for k, titolo, descr, comandi in SEZIONI]
        f_cmd = tkfont.Font(font=F(9, True))
        tab = 12 + max((f_cmd.measure(c) for _k, _t, _d, cc in tutti for c, _e in cc), default=180) + 18      # la colonna dei comandi, come la griglia di prima
        blocco = dict(background=C["scheda"], lmargincolor=C["scheda"], rmargincolor=C["scheda"], rmargin=12)
        t.tag_configure("titolo", font=F(12, True), foreground=C["titolo"], lmargin1=12, lmargin2=12, spacing1=10, spacing3=2, **blocco)
        t.tag_configure("descr", font=F(9), foreground=C["grigio"], lmargin1=12, lmargin2=12, spacing3=6, **blocco)
        t.tag_configure("cmd", font=F(9, True), foreground=C["accento"])
        t.tag_configure("eff", font=F(9), foreground=C["testo"])
        t.tag_configure("riga", lmargin1=12, lmargin2=tab, tabs=(tab,), spacing1=1, spacing3=1, **blocco)
        t.tag_configure("fine", font=F(5), lmargin1=12, **blocco)
        t.tag_configure("spazio", font=F(5), background=C["fondo"])
        for k, titolo, descr, comandi in tutti:
            self.sezione(t, k, titolo, descr, comandi)
        t.configure(state="disabled")

    def riquadro_donazioni(self):
        """SUPPORT: l'app e' gratis al 100%, solo donazioni (Autore, 11 nov 2026: «lanciamo l'app come 100% free e solo donazioni»); in beta la donazione
        e' di €2,99 al mese (13 nov 2026: «fase di beta test perciò tutto gratuito con donazione per sostenere il progetto a 2,99»). Il pulsante apre la pagina
        delle donazioni (url_donazioni); finche' non c'e', dice che apre presto."""
        tk, F = self.tk, self.F
        box = tk.Frame(self.fr, bg=C["filo"], padx=1, pady=1); box.pack(fill="x", padx=16, pady=(0, 10))
        d = tk.Frame(box, bg=C["scheda"]); d.pack(fill="x")
        tk.Label(d, text="SUPPORT", bg=C["scheda"], fg=C["muto"], font=F(7, True)).pack(anchor="w", padx=12, pady=(8, 2))
        riga = tk.Frame(d, bg=C["scheda"]); riga.pack(fill="x", padx=12, pady=(0, 10))
        url = url_donazioni()
        self.b_dona = None
        self.l_dona = tk.Label(riga, text=f"{PRODOTTO} is in beta and 100% free, for everyone: nothing is locked. If it helps you, support the project with €2.99 a month."
                               + ("" if url else " Donations open soon."), bg=C["scheda"], fg=C["testo"], font=F(9), anchor="w", justify="left", wraplength=700)
        self.l_dona.pack(side="left", fill="x", expand=True)
        if url:
            import webbrowser
            b = self.b_dona = pulsante_solido(tk, F, riga, "Donate", False, lambda: webbrowser.open(url), alto=30, bg=C["scheda"], colori=ARANCIO)
            b.configure(width=140); b.pack(side="right")

    def riquadro_untapped(self):
        """YOUR COLLECTION: il link del profilo pubblico di Untapped (account.collega_untapped). Il log di Arena non scrive la collezione intera: senza, Your decks e
        Collection non sanno quali carte hai. Collegato, si scarica subito la collezione (collezione_viva.aggiorna_scarico); limited e social dopo un riavvio."""
        tk, F = self.tk, self.F
        import account
        box = tk.Frame(self.fr, bg=C["filo"], padx=1, pady=1); box.pack(fill="x", padx=16, pady=(0, 10))
        d = tk.Frame(box, bg=C["scheda"]); d.pack(fill="x")
        tk.Label(d, text="YOUR COLLECTION", bg=C["scheda"], fg=C["muto"], font=F(7, True)).pack(anchor="w", padx=12, pady=(8, 2))
        riga = tk.Frame(d, bg=C["scheda"]); riga.pack(fill="x", padx=12, pady=(0, 4))
        self.v_link = tk.StringVar()
        e = tk.Entry(riga, textvariable=self.v_link, bg=C["fondo"], fg=C["titolo"], insertbackground=C["titolo"], relief="flat", font=F(9))
        e.pack(side="left", fill="x", expand=True, ipady=5, padx=(0, 8))
        b = pulsante_solido(tk, F, riga, "Link", False, self.collega, alto=30, bg=C["scheda"]); b.configure(width=110); b.pack(side="right")
        a = account.account()
        self.l_link = tk.Label(d, text="", bg=C["scheda"], fg=C["grigio"], font=F(8), anchor="w", justify="left", wraplength=900)
        self.l_link.pack(fill="x", padx=12, pady=(0, 10))
        self.l_link.configure(text=("Linked to your Untapped profile. " if a.get("untapped_player") else "Not linked. ")
                              + "Arena's log does not list your whole collection: paste the link of your public Untapped.gg profile "
                              "(mtga.untapped.gg/profile/...) to see the cards you own and the wildcards your decks need.")

    def collega(self):
        import account
        if not account.collega_untapped(self.v_link.get()):
            self.l_link.configure(text="That is not an Untapped profile link. It looks like https://mtga.untapped.gg/profile/<id>/<id>", fg=C["rosso_t"])
            return
        self.l_link.configure(text="Linked. Downloading your collection…", fg=C["testo"])

        def lavoro():
            try:
                import collezione_viva as CV
                esito = CV.aggiorna_scarico()
            except Exception:       # noqa: BLE001
                esito = None
            msg = {True: "Collection downloaded. Restart the app to see limited games and your profile.", False: "Linked; the collection did not change.",
                   None: "Linked, but Untapped did not answer. The app tries again in a few minutes."}[esito]
            self.fr.after(0, lambda: self.l_link.configure(text=msg, fg=C["verde_t"] if esito else C["testo"]))
        threading.Thread(target=lavoro, daemon=True).start()

    def riquadro_condivisione(self):
        """DATA SHARING: acceso o spento, il pulsante che lo cambia, il codice pseudonimo di chi usa l'app (condividi.codice dell'account) e quante partite aspettano."""
        tk, F = self.tk, self.F
        import account
        import condividi
        box = tk.Frame(self.fr, bg=C["filo"], padx=1, pady=1); box.pack(fill="x", padx=16, pady=(0, 10))
        d = tk.Frame(box, bg=C["scheda"]); d.pack(fill="x")
        tk.Label(d, text="DATA SHARING", bg=C["scheda"], fg=C["muto"], font=F(7, True)).pack(anchor="w", padx=12, pady=(8, 2))
        riga = tk.Frame(d, bg=C["scheda"]); riga.pack(fill="x", padx=12, pady=(0, 10))
        self.l_cond = tk.Label(riga, text="", bg=C["scheda"], fg=C["testo"], font=F(10, True), anchor="w", justify="left"); self.l_cond.pack(side="left")
        self.b_cond = pulsante_solido(tk, F, riga, "Turn on", False, self.cambia_condivisione, alto=30, bg=C["scheda"]); self.b_cond.configure(width=150); self.b_cond.pack(side="right")
        tk.Label(d, text="Only cards, results, mulligans and turns of your games. Never your name, your account or your opponents' names. "
                 f"Your code for any privacy request: {condividi.codice(account.account().get('id') or '?')}", bg=C["scheda"], fg=C["grigio"], font=F(8),
                 anchor="w", justify="left", wraplength=900).pack(fill="x", padx=12, pady=(0, 10))
        self.mostra_condivisione()

    def mostra_condivisione(self):
        import condividi
        si = condividi.consenso() is True
        coda = os.path.join(condividi.CARTELLA[0], "coda.jsonl")
        n = sum(1 for r in open(coda, encoding="utf-8") if r.strip()) if os.path.exists(coda) else 0
        self.l_cond.configure(text=("On" if si else "Off") + (f" · {n} game{'s' if n != 1 else ''} waiting to be sent" if si and n else ""),
                              fg=C["verde_t"] if si else C["testo"])
        self.b_cond.metti("Turn off" if si else "Turn on", False)

    def cambia_condivisione(self):
        import condividi
        condividi.imposta_consenso(condividi.consenso() is not True)
        self.mostra_condivisione()

    def sezione(self, t, k, titolo, descr, comandi):
        """Una sezione nel testo: il titolo, cosa fa, i comandi in due colonne (il comando in azzurro, l'effetto accanto), su un blocco col fondo della scheda."""
        segno = f"sez_{k}"
        t.mark_set(segno, "end-1c"); t.mark_gravity(segno, "left")
        self.ancore[k] = segno
        t.insert("end", titolo + "\n", ("titolo",))
        t.insert("end", descr + "\n", ("descr",))
        for com, eff in comandi:
            t.insert("end", com, ("cmd", "riga"))
            t.insert("end", "\t" + eff + "\n", ("eff", "riga"))
        t.insert("end", "\n", ("fine",))
        t.insert("end", "\n", ("spazio",))

    def testi(self):
        """I testi della pagina, per le prove: le etichette e, del testo delle sezioni, ogni titolo, descrizione, comando ed effetto."""
        out = []

        def giu(w):
            for x in w.winfo_children():
                if isinstance(x, self.tk.Label):
                    out.append(x.cget("text"))
                giu(x)
        giu(self.fr)
        for riga in self.cv.get("1.0", "end").split("\n"):
            out.extend(p_ for p_ in riga.split("\t") if p_)
        return out

    def vai(self, k):
        """Un collegamento in alto: la sezione in cima alla colonna."""
        segno = self.ancore.get(k)
        if segno is None:
            return
        self.cv.yview(segno)

    # ------------------------------------------------ gli aggiornamenti
    def mostra_stato(self):
        st = self.stato or {}
        s = st.get("stato")
        nuova = s == "nuova"
        if nuova:
            testo = f"Update {st.get('ultima')} available · you have {VERSIONE}"
        elif s == "aggiornata":
            testo = f"You have the latest version ({VERSIONE})"
        elif s == "errore":
            testo = f"Could not check for updates: {st.get('errore', '')}"
        elif s == "senza_canale":
            testo = "No update channel yet: updates are not published anywhere for now"
        else:
            testo = "Not checked yet"
        self.l_stato.configure(text=testo, fg=ARANCIO[1] if nuova else C["rosso"] if s == "errore" else C["testo"])
        if nuova:
            self.b_scarica.metti(f"Download update {st.get('ultima')}", False)
            self.b_scarica.pack(side="right", padx=(8, 0), before=self.b_controlla)
        else:
            self.b_scarica.pack_forget()
        note = (st.get("note") or "").strip() if nuova else ""
        if note:
            self.l_note.configure(text=note); self.l_note.pack(fill="x", padx=12, pady=(0, 10))
        else:
            self.l_note.pack_forget()
        if self.su_aggiornamento:
            self.su_aggiornamento(nuova)

    def controlla_ora(self, url=None):
        """Il controllo in un filo (la rete non ferma la finestra); l'esito arriva col giro di Tk."""
        self.b_controlla.metti("Checking…", True)
        self._esito = None
        threading.Thread(target=lambda: setattr(self, "_esito", AG.controlla(url)), daemon=True).start()
        self.fr.after(200, self.aspetta)

    def aspetta(self):
        if self._esito is None:
            self.fr.after(200, self.aspetta)
            return
        self.stato, self._esito = self._esito, None
        AG.salva(self.stato)
        self.b_controlla.metti("Check now", False)
        self.mostra_stato()

    def ogni_tanto(self):
        self.controlla_ora()
        self.fr.after(AG.OGNI * 1000, self.ogni_tanto)

    def scarica(self):
        """Apre il link dell'aggiornamento nel browser: l'app non scarica e non installa niente da sola."""
        link = (self.stato or {}).get("download") or ""
        if (self.stato or {}).get("stato") == "nuova" and link.lower().startswith(("https://", "http://")):
            webbrowser.open(link)
            return True
        return False
