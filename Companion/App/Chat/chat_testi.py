"""I testi della chat: le fasi del turno, la traduzione in inglese, azioni e minidati di una riga, l'ordine dei messaggi."""
import datetime
import re
import time


# ---------------------------------------------------------------- gerarchia dei testi della chat
# Autore, 13 ott 2026: «tutto e' mischiato e ogni testo ha la stessa importanza». Quattro livelli: la fase del turno
# col suo nome vero di Magic (stampatello bianco, il titolo piu' grande; 13 ott 2026), l'azione da fare (stampatello grassetto bianco), le carte coinvolte (bianco, normale),
# i minidati (azzurro, piccolo).

def fase_di(m, lato_turno):
    """La fase del turno a cui appartiene un messaggio. Vuota fuori dai turni (mano iniziale, draft)."""
    ico = m.get("ico"); t = m["testo"]; nota = m.get("nota") or ""
    if ico in ("vinta", "persa"):
        return ""
    if lato_turno == "lui":
        if ico in ("attacca", "difendi", "scoperto") or t.startswith(("Blocca", "Non bloccare")):
            return "FASE DI COMBATTIMENTO"
        return NOME_FASE.get(m.get("fase_io"), "FASE PRINCIPALE")      # la fase che Arena dice (dal 13 ott sera)
    if lato_turno != "tu":
        return ""
    if m["lato"] == "lui":          # una sua magia nel tuo turno: nella fase in cui l'ha lanciata
        return NOME_FASE.get(m.get("fase_io"), "PRIMA FASE PRINCIPALE")
    if ico in ("attacca", "difendi", "letale") or t.startswith(("Lui non ha creature", "Contrattacco", "Adesso o mai", "Attacca lui", "Trucco noto")):
        return "FASE DI COMBATTIMENTO"
    if m["lato"] == "info" or ico == "controllo":
        # un avviso sta nella fase in cui e' arrivato (13 ott 2026): «lui e' a corto di mana» arriva col turno, nella prima
        return {"Main2": "SECONDA FASE PRINCIPALE", "Combat": "FASE DI COMBATTIMENTO"}.get(m.get("fase_io"), "PRIMA FASE PRINCIPALE")
    if "dopo l'attacco" in nota:
        return "SECONDA FASE PRINCIPALE"
    # cio' che non viene dal piano (un surveil, un ripensamento) sta nella fase in cui e' arrivato: il surveil del -1 di
    # Jace usato dopo l'attacco finiva nella prima fase, gia' grigia (replay contro SrLeitao, 13 ott 2026)
    if not m.get("dal_piano") and m.get("fase_io") in ("Combat", "Main2"):
        return {"Main2": "SECONDA FASE PRINCIPALE", "Combat": "FASE DI COMBATTIMENTO"}[m["fase_io"]]
    return "PRIMA FASE PRINCIPALE"


ORDINE_FASI = {"Beginning": 0, "Main1": 1, "Combat": 2, "Main2": 3, "Ending": 4}      # le fasi di Arena, nello stato
INDICE_FASE = {"FASE INIZIALE": 0, "PRIMA FASE PRINCIPALE": 1, "FASE PRINCIPALE": 1, "FASE DI COMBATTIMENTO": 2,
               "SECONDA FASE PRINCIPALE": 3, "FASE FINALE": 4}
NOME_FASE = {"Beginning": "FASE INIZIALE", "Main1": "PRIMA FASE PRINCIPALE", "Combat": "FASE DI COMBATTIMENTO",
             "Main2": "SECONDA FASE PRINCIPALE", "Ending": "FASE FINALE"}


def _nomi(s):
    return [x.strip() for x in s.split(", ") if x.strip()]


_REGOLE_TESTO = [
    (r"Gioca la terra: (.+)$", lambda g: ("Gioca la terra", [g[1]], [])),
    (r"(Gioca|Lancia) (.+?)(?: (\d+/\d+))?(?: su (.+))?$", lambda g: (g[1], [g[2] + (f"  →  {g[4]}" if g[4] else "")], [g[3]] if g[3] else [])),
    (r"Attiva (.+?) \((\d+) mana\)$", lambda g: ("Attiva", [g[1]], [f"{g[2]} mana"])),
    (r"(.+?): usa ([+−-]\d+), (.+)$", lambda g: ("Attiva", [f"{g[1].replace(' (pedina)', '')}  {g[2]}"], [g[3]])),
    (r"(.+?) ([+−]\d+): (.+)$", lambda g: ("Attiva", [f"{g[1].replace(' (pedina)', '')}  {g[2]}"], [g[3]])),
    (r"Togli il suo (.+?) \(fedeltà (\d+)\): (.+)$", lambda g: ("Togli il suo planeswalker", [g[1]], [f"fedeltà {g[2]}", g[3]])),
    (r"Attacca lui, non il suo (.+?) \(fedeltà (\d+)\)$", lambda g: ("Attacca lui, non il suo planeswalker", [g[1]], [f"fedeltà {g[2]}"])),
    (r"Blocca: (.+?) su (.+)$", lambda g: ("Blocca", [f"{g[1]}  →  {g[2]}"], [])),
    (r"(Lui ha giocato|Ha giocato) (.+?)(?: su (.+))?$", lambda g: (g[1], [g[2] + (f"  →  {g[3]}" if g[3] else "")], [])),
    (r"Aura sua: (.+?) su (.+)$", lambda g: ("Aura sua", [f"{g[1]}  →  {g[2]}"], [])),
    (r"Ti attacca con (.+?): (.+)$", lambda g: ("Ti attacca con", _nomi(g[1]), [g[2]])),
    (r"Attacca il tuo planeswalker con (.+?): (.+)$", lambda g: ("Attacca il tuo planeswalker con", _nomi(g[1]), [g[2]])),
    (r"Tieni in mano: (.+)$", lambda g: ("Tieni in mano", _nomi(g[1]), [])),
    (r"In mano ha: (.+)$", lambda g: ("In mano ha", [g[1]], [])),
    (r"Trucco noto in combattimento: (.+)$", lambda g: ("Trucco noto in combattimento", _nomi(g[1]), [])),
    (r"Al suo turno toglie: (.+?) con (.+)$", lambda g: ("Al suo turno può togliere", [g[1]], [f"con {g[2]}"])),
    (r"(Tieni|Mulligan|Fai mulligan|Cambia) la mano: (.+)$", lambda g: (f"{g[1]} la mano", [], [g[2]])),
    (r"(Surveil|Scry|Esplora): (.+?) (in cima|sopra|sotto|nel cimitero|al cimitero)$", lambda g: (g[1], [g[2]], [g[3]])),
]


# La chat a video e' in inglese (Autore, 4 nov 2026: «scriviamo tutta l'app in inglese»). Partita, ordina_chat e il collaudo restano sulle
# parole del diario (italiane, come lo scrive la spalla): si traduce solo quello che si disegna, qui sotto. Le righe «CLAUDE:» restano come sono.
FASI_EN = {"PRIMA FASE PRINCIPALE": "FIRST MAIN PHASE", "SECONDA FASE PRINCIPALE": "SECOND MAIN PHASE", "FASE PRINCIPALE": "MAIN PHASE",
           "FASE DI COMBATTIMENTO": "COMBAT PHASE", "FASE INIZIALE": "BEGINNING PHASE", "FASE FINALE": "ENDING PHASE"}
SEP_EN = {"Mano iniziale": "Opening hand", "Costruzione del mazzo": "Deck building"}
AZIONI_EN = {"GIOCA LA TERRA": "PLAY LAND", "GIOCA": "PLAY", "LANCIA": "CAST", "ATTIVA": "ACTIVATE", "ATTACCA CON": "ATTACK WITH", "NON ATTACCARE": "DON'T ATTACK",
             "BLOCCA": "BLOCK", "NON BLOCCARE": "DON'T BLOCK", "NON HAI BLOCCANTI LIBERI": "NO FREE BLOCKERS", "LUI HA GIOCATO": "OPPONENT PLAYED", "HA GIOCATO": "PLAYED",
             "TI ATTACCA CON": "ATTACKS YOU WITH", "ATTACCA IL TUO PLANESWALKER CON": "ATTACKS YOUR PLANESWALKER WITH", "AURA SUA": "OPPONENT'S AURA",
             "TIENI IN MANO": "HOLD IN HAND", "IN MANO HA": "IN THEIR HAND", "TRUCCO NOTO IN COMBATTIMENTO": "KNOWN COMBAT TRICK", "AL SUO TURNO PUÒ TOGLIERE": "CAN REMOVE ON THEIR TURN",
             "TOGLI IL SUO PLANESWALKER": "REMOVE THEIR PLANESWALKER", "ATTACCA LUI, NON IL SUO PLANESWALKER": "ATTACK THEM, NOT THEIR PLANESWALKER", "TIENI LA MANO": "KEEP HAND",
             "MULLIGAN LA MANO": "MULLIGAN", "FAI MULLIGAN LA MANO": "MULLIGAN", "CAMBIA LA MANO": "CHANGE HAND", "ESPLORA": "EXPLORE", "LETALE": "LETHAL", "PARTITA VINTA": "GAME WON",
             "PARTITA PERSA": "GAME LOST", "SEQUENZA, IN QUEST'ORDINE": "SEQUENCE, IN THIS ORDER", "IL TURNO INTERO, IN QUEST'ORDINE": "FULL TURN, IN THIS ORDER",
             "LUI NON HA CREATURE": "OPPONENT HAS NO CREATURES", "OPZIONI (MOTORE NUOVO)": "OPTIONS", "OPZIONI DI LUI (MOTORE NUOVO)": "OPPONENT'S OPTIONS", "METRO": "WIN METER",
             "CONTROLLO DEL MAZZO": "DECK CHECK", "COL MANA APERTO PUÒ GIOCARE": "CAN PLAY WITH OPEN MANA", "LUI È A CORTO DI MANA": "OPPONENT IS SHORT ON MANA", "PERICOLO": "DANGER",
             "ADESSO O MAI PIÙ": "NOW OR NEVER", "CONTRATTACCO A RISCHIO": "COUNTERATTACK RISK", "CONFRONTO CON LA SPALLA": "COMPARED WITH THE ASSISTANT", "DECIDI LA MANO": "DECIDE HAND"}
_EN = [(r"\((\d+) carte, ", r"(\1 cards, "), (r"prezzo ([\d.]+) punti", r"cost \1 points"), (r"carte al (\d+)° percentile dei trofei Quick", r"cards at the \1th percentile of Quick trophies"), (r"\bfonti\b", "sources"), (r"rimozioni vere dei tuoi colori in sideboard", "removal in your colors left in the sideboard"),
       (r"entrano al posto delle carte piu' deboli", "they go in for the weakest cards"), (r"^tieni a casa (\d+) bloccant[ei]", r"keep \1 home to block"), (r"\bmorto \(era a (\d+)\)", r"dead (was at \1)"), (r"· tu adesso:", "· you now:"), (r"\bdalla mano\b", "from hand"), (r"\(preparata\)", "(prepared)"),
       (r"\(minaccia\)", "(menace)"), (r"Sei tu sotto pressione", "You are under pressure"), (r"ogni attacco va a segno: i danni sono liberi", "every attack connects: free damage"),
       (r"attacca subito, prima che trovi le terre per difendersi", "attack now, before they find lands to defend"), (r"\bdal cimitero\b", "from the graveyard"),
       (r"(\d+) di forza sua contro le tue (\d+) vite", r"\1 of their power against your \2 life"), (r"niente da fare", "nothing to do"), (r"niente attacco: adesso", "no attack: now"),
       (r"con il mana che avanza, a fine turno", "with leftover mana, at end of turn"), (r"aspetta: prima il board \(canone \d+\)", "waits: board first"),
       (r"nessuna uscita in mano: cerca bloccanti volanti o rimozioni", "no way out in hand: look for flying blockers or removal"), (r"effetto non letto dalla scheda", "effect not read"),
       (r"\(non hai bloccanti per lui\)", "(you have no blockers for them)"), (r"\(giocala prima\)", "(play it first)"), (r"torna in mano a lui", "returns to opponent's hand"),
       (r"lui è a corto di mana", "opponent is short on mana"), (r"ha un potere che chiude", "has a game-ending ability"), (r"non si stappa", "doesn't untap"), (r"perde le abilità", "loses abilities"),
       (r"poi attacca anche con", "then also attack with"), (r"Poi lui, al suo turno:", "Then opponent, on their turn:"), (r"Poi tu, al tuo turno:", "Then you, on your turn:"),
       (r"\(tuo turno (\d+)\)", r"(your turn \1)"), (r"\(era (\d+), cala\)", r"(was \1, falling)"), (r"\(era (\d+), cresce\)", r"(was \1, growing)"),
       (r"vinci (\d+)% contro (\d+)% della proposta", r"win \1% vs \2% for the suggestion"), (r"\bvinci (\d+)%", r"win \1%"), (r"\bfedeltà\b", "loyalty"),
       (r"(\d+) terre aperte", r"\1 open lands"), (r"1 terra aperta", "1 open land"), (r"ti chiude in (\d+) turn[oi]", r"kills you in \1 turns"),
       (r"danni a turno che non fermi", "damage a turn you can't stop"), (r"carte in mano", "cards in hand"), (r"(\d+) terre dopo (\d+) turni", r"\1 lands after \2 turns"), (r"\bterre\b", "lands"),
       (r"\bdanni\b", "damage"), (r"al planeswalker", "to the planeswalker"), (r"in cima", "on top"), (r"\bnel cimitero\b|\bal cimitero\b", "to the graveyard"), (r"in fondo", "to the bottom"),
       (r"^sopra$", "on top"), (r"^sotto$", "on the bottom"), (r"vittorie attese", "expected wins"), (r"meglio del (\d+)% dei pool", r"better than \1% of pools"), (r"^prendi ", "take "),
       (r"lo paga col mana libero adesso", "they can pay it with open mana now"), (r"ogni attacco va a segno: i danni sono liberi", "every attack connects: free damage"),
       (r"anche col trucco", "even through a trick"), (r"^verde$", "green"), (r"^giallo$", "yellow"), (r"^rosso$", "red"), (r"errore della spalla o scelta tua\?", "assistant error or your choice?"),
       (r"attacca subito, prima che trovi le terre per difendersi", "attack now, before they find lands to defend"), (r"attacca subito, prima che trovi le lands per difendersi", "attack now, before they find lands to defend"),
       (r"Tieni le rimozioni per le sue minacce", "Keep removal for their threats"), (r"Prima difenditi, attacchi dopo", "Defend first, attack later"), (r"Sei tu sotto pressione", "You are under pressure"),
       (r"oggi passano (\d+) damage \(lui da (\d+) a (\d+)\), domani (\d+)", r"\1 damage today (they go from \2 to \3), \4 tomorrow"), (r"tappate oggi", "tapped today"),
       (r"visibili e circa (\d+) nascosti contro (\d+) vite", r"visible and about \1 hidden against \2 life"), (r"\+(\d+) vite", r"+\1 life"), (r"\bvite\b", "life"),
       (r"\(peschi (\d+)\)", r"(draw \1)"), (r"\bpeschi (\d+)", r"draw \1"), (r"(\S+) nasce a (\d+)", r"\1 enters at \2"), (r"\ba rischio\b", "at risk"), (r"\bal sicuro\b", "safe"),
       (r"\bforza sua\b", "their power"), (r"\bforza tua\b", "your power"), (r"\bconviene\b", "best"), (r"\(campo\)", "(battlefield)"), (r"\(cimitero\)", "(graveyard)"), (r"\(pedina\)", "(token)"),
       (r"-> tuo planeswalker", "-> your planeswalker"), (r"\battiva\b", "activate"), (r"\btrucchi (\d+)%", r"tricks \1%"), (r"prima: GIH", "first: GIH"), (r"\bmuore\b", "dies"),
       (r"colpisce per (\d+)", r"hits for \1"), (r"\brimozione:", "removal:"), (r"\blui\b", "opponent"), (r"^tu\b", "you"), (r"\bturni\b", "turns"), (r"\bturno\b", "turn"), (r"^tieni\b", "keep"),
       (r"\bpoi\b", "then"), (r" per ", " for "), (r"\bsu\b", "on"), (r"\bcon\b", "with"), (r"\bprima\b", "before"), (r"\bdopo\b", "after")]
_EN = [(re.compile(a), b) for a, b in _EN]


def en(t):
    """Una riga di carte o di minidati in inglese: si cambiano le parole della spalla, i nomi delle carte restano."""
    for rx, b in _EN:
        t = rx.sub(b, t)
    return t


def azione_en(a):
    """Il titolo di un'azione in inglese: la tabella, poi le parti col numero («MAZZO 1», «LISTA 2»)."""
    if a in AZIONI_EN:
        return AZIONI_EN[a]
    a = re.sub(r"^MAZZO (\d)", r"DECK \1", a)
    a = re.sub(r"^LISTA (\d)", r"LIST \1", a)
    return en(a)


def scomponi(m):
    """Un messaggio -> (azione, carte, minidati)."""
    t = m["testo"]; lista = list(m.get("lista") or [])
    nota = re.sub(r"(^|,\s*|\s*·\s*)(dopo l|prima dell)'attacco", "", m.get("nota") or "").strip(" ,·")
    if nota.startswith("cambio"):
        nota = ""
    azione, carte, dati = t, [], []
    for rx, f in _REGOLE_TESTO:
        g = re.match(rx, t)
        if g:
            azione, carte, dati = f(g)
            break
    else:
        if ": " in t:
            azione, resto = t.split(": ", 1)
            dati = [resto]
    if m.get("ico") == "pw" and t.startswith("Togli"):
        dati += lista
    else:
        carte += lista
    if nota:
        dati.append(nota)
    return azione.upper(), carte, dati


def ordina_chat(P):
    """Cosa mostra la chat e in che ordine: i turni dal piu' recente, dentro il turno le fasi col loro titolo, un passo da
    fare alla volta, i grigi, e il messaggio da evidenziare. -> (ordine, id evidenziato). Senza tkinter: la usa anche il
    collaudo delle partite (collaudo_finestra.py, 13 ott 2026)."""
    P.fin_qui = None          # fin dove si vede il tuo turno in corso (indice di fase): lo legge il collaudo
    # la chat scorre al contrario (Autore, 12 ott 2026): il turno piu' recente in cima, e dentro il turno l'ultimo
    # messaggio per primo, sotto il titolo del turno
    gruppi = [[None, []]]
    for m in P.msg[-80:]:
        if m["tipo"] == "sep": gruppi.append([m, []])
        else: gruppi[-1][1].append(m)
    # un passo alla volta: del turno in corso si vede solo il primo passo da fare; i fatti e i turni passati in grigio
    t_max = max([x.get("t") or 0 for x in P.msg] or [0])
    visto_pendente = False; nascosti = set()
    for x in P.msg[-80:]:
        if x["tipo"] != "msg": continue
        if x.get("nascosto"): nascosti.add(x["id"]); continue      # sostituita dal piano del turno (13 ott 2026)
        # grigio solo i turni passati: le azioni del turno in corso restano leggibili, anche quelle fatte (Autore, 13 ott 2026)
        x["grigio"] = (x.get("t") or 0) < t_max
        if x.get("passo") and not x.get("fatto"):
            if x["barrato"]: nascosti.add(x["id"]); continue
            if (x.get("t") or 0) == t_max:
                if visto_pendente: nascosti.add(x["id"])
                visto_pendente = True
    ordine = []
    for sep, ms in reversed(gruppi):
        if sep is not None: ordine.append(sep)
        vis = [x for x in ms if x["id"] not in nascosti]
        if sep is None or not sep.get("t") or sep["lato"] not in ("tu", "lui"):
            ordine += list(reversed(vis)); continue
        # le fasi del turno (13 ott 2026): la situazione in testa, poi dall'ultima fase alla prima, come la chat
        # la fase in cui e' Arena adesso: quelle prima diventano grigie, titolo e contenuto (Autore, 13 ott 2026)
        # solo nel turno piu' recente: lo stato di Arena c'e' solo nel tuo turno, e nel turno suo restava «in corso» la fase
        # del tuo turno prima (derbabyadmiral T5, collaudo del 13 ott: il riquadro chiaro finiva nel turno passato)
        ora = ORDINE_FASI.get(P.io.get("fase"), -1) if sep.get("t") == P.io.get("turno") and sep.get("t") == t_max else -1
        # le fasi che devono ancora venire non si mostrano (Autore, 13 ott 2026: «manda la fase principale e quella di
        # combattimento assieme, cosi' non va bene», «fa casino, troppe fasi assieme»): nel tuo turno in corso si vede la
        # fase in cui e' Arena e quelle passate; prima del primo stato del turno, la prima fase principale
        fin_qui = None
        if sep["lato"] == "tu" and sep.get("t") == t_max:
            fin_qui = ora if ora >= 0 else 1
            # finite le azioni della fase in corso si vede la fase dopo, una sola: Arena scrive lo stato del combattimento
            # solo dopo la dichiarazione degli attaccanti, e l'attacco va visto prima (Shovelspoon T16, 13 ott 2026: «non mi
            # da la fase di attacco»)
            def da_fare(f):
                return any(x.get("passo") and not x.get("fatto") and not x["barrato"] and INDICE_FASE.get(fase_di(x, "tu"), 0) <= f for x in vis)
            dopo = sorted({INDICE_FASE.get(fase_di(x, "tu"), 0) for x in vis} - set(range(fin_qui + 1)))
            if dopo and not da_fare(fin_qui) and dopo[0] <= fin_qui + 2: fin_qui = dopo[0]
            # il Cercatore parla quando Arena ha aperto la scelta: la sua fase si vede anche se lo stato non l'ha ancora scritta
            fin_qui = max([fin_qui] + [INDICE_FASE.get(fase_di(x, "tu"), 0) for x in vis if x.get("cercatore")])
            vis = [x for x in vis if INDICE_FASE.get(fase_di(x, "tu"), 0) <= fin_qui]
        if fin_qui is not None: P.fin_qui = fin_qui
        fasi = []
        for x in vis:
            x["_fase"] = fase_di(x, sep["lato"])
            i = INDICE_FASE.get(x["_fase"], -1)
            if ora >= 0 and i < ora:
                if x.get("passo") and not x.get("fatto") and ora == 3 and x.get("ico") not in ("attacca", "difendi", "letale"):
                    x["_fase"] = "SECONDA FASE PRINCIPALE"     # cio' che non hai fatto prima si puo' fare ancora adesso
                else:
                    x["grigio"] = True
            if x["_fase"] not in fasi: fasi.append(x["_fase"])
        # una fase del tuo turno gia' raggiunta senza niente da fare ha il suo titolo e «niente da fare» (Autore, 13 ott
        # 2026: «se nella fase iniziale non c'e' davvero nulla da fare sarebbe meglio che dicesse: fase inizio nulla, poi apre
        # la fase di attacco»)
        if fin_qui is not None:
            for i_, nome_f in ((1, "PRIMA FASE PRINCIPALE"), (2, "FASE DI COMBATTIMENTO"), (3, "SECONDA FASE PRINCIPALE")):
                if i_ <= fin_qui and nome_f not in fasi: fasi.append(nome_f)
        for f in [f for f in fasi if f in ("", "FASE INIZIALE")] + sorted([f for f in fasi if f not in ("", "FASE INIZIALE")], key=lambda f: -INDICE_FASE.get(f, 0)):
            grigia = (sep.get("t") or 0) < t_max or (ora >= 0 and INDICE_FASE.get(f, -1) < ora)
            if f: ordine.append(dict(tipo="fase", testo=f, grigio=grigia, attuale=ora >= 0 and INDICE_FASE.get(f, -1) == ora))
            della = sorted([x for x in reversed(vis) if x["_fase"] == f], key=lambda x: not x.get("cercatore"))   # il Cercatore per primo
            if f and not della: ordine.append(dict(tipo="vuota", testo="Niente da fare", id=f"vuota:{sep.get('t')}:{f}",
                                                   grigio=grigia or (fin_qui is not None and INDICE_FASE.get(f, 0) < fin_qui)))
            ordine += della
    # l'ultimo messaggio della fase in cui e' Arena, in un riquadro appena piu' chiaro (Autore, 13 ott 2026). La fase
    # e' quella dello stato; nel turno suo, che non ha stati, la prima fase non grigia. Si prende il primo messaggio sotto
    # quel titolo, mai uno di un'altra fase o di un altro turno
    def primo_sotto(i):
        return ordine[i + 1]["id"] if i + 1 < len(ordine) and ordine[i + 1]["tipo"] in ("msg", "vuota") else None
    evid = None
    for i, x in enumerate(ordine):
        if x["tipo"] == "fase" and x.get("attuale"): evid = primo_sotto(i); break
    if evid is None:
        for i, x in enumerate(ordine):
            if x["tipo"] == "fase" and not x["grigio"] and primo_sotto(i) is not None: evid = primo_sotto(i); break
    # la riga del Cercatore del turno in corso e' sempre quella in evidenza: cambia la scelta da fare
    for x in ordine:
        if x["tipo"] == "msg" and x.get("cercatore") and (x.get("t") or 0) == t_max and not x.get("grigio"):
            evid = x["id"]; break
    return ordine, evid


def ora_riga(r):
    """L'istante di una riga del diario («HH:MM:SS ...», il diario e' del giorno): per sapere se il mazzo inviato e' di
    questo draft. Senza ora, adesso."""
    m = re.match(r"(\d\d):(\d\d):(\d\d) ", r)
    if not m:
        return time.time()
    oggi = datetime.date.today()
    return datetime.datetime(oggi.year, oggi.month, oggi.day, *map(int, m.groups())).timestamp()
