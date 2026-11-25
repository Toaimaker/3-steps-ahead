"""La scheda Performance: l'analizzatore di partite e di situazioni (Autore, 12 nov 2026: «riusciamo a modificarla per farla diventare come un analizzatore di
partite ma anche di situazioni come in holdem manager? la possibilita' di aggiungere variabili che ci mostrano come i grafici cambiano», poi «Sì, costruiscila» sulla
proposta). Fino a quel giorno la scheda erano le pagine Limited e Standard con la tendina Mode (pagina_limited, pagina_standard: le classi restano, Your decks
eredita da PaginaStandard).

In testa Constructed o Limited. A sinistra le variabili: ogni tendina filtra (Any = tutte), coi conti delle partite di ogni valore sotto gli altri filtri; sotto, le
situazioni salvate. A destra i numeri della situazione (win rate con l'intervallo di Wilson, record, turni, mulligan, play e draw, quante partite), il grafico
(win rate, partite, turni medi, mulligan; per partite o per data; cumulativo o sulle ultime N; diviso per una variabile, una linea per valore), e il report
raggruppato per una variabile: il clic su una riga la mette fra i filtri, il clic su una colonna ordina. Sotto 15 partite una riga e' grigia: un indizio.
Le viste stanno in cartelle (Chart, Spots, Report, Matchups, Compare), e ognuna si stacca in una finestra sua (12 nov 2026, Autore: «questi falli a modo di
cartelle e poi tira via il sotto testo / poi procedi con i confronti situazionali / ogni sezione di ogni cartella si puo' staccare dal quadro e renderla una
finestra a se stante»). Compare mette la situazione (A) contro il resto, tutte le partite o una situazione salvata (B), con la significativita'.
I dati: dati_analizzatore (i nostri log, dal 22 set 2026)."""
import collections
import datetime
import math
import os
import re
import threading
import time

import blocco_partita
import dati_analizzatore as DA
import decisioni as DEC
import numeri_partite as NP
import righe_filtri as R_F
import disegni as DG
from tema import CI as C, FN, RD
from widget import ARANCIO, VERDE_P, Tendina, disegna_s3, pulsante_solido

LINEE = ("#d8d8dc", "#2f9bff", "#f0ad4e", "#a58cff", "#5cb85c", "#ee8a87")      # All, poi i valori: lontani fra loro anche per i daltonici (come il resto dell'app)
TIPI = ("Constructed", "Limited")
# lo switch unico (15 nov 2026, Autore: «in alto alla scheda c'è il pulsante constructed e limited, quelli devono essere un unico switch universale»):
# una pillola sola, il clic la gira; vale per tutta la pagina, Advanced filters compresi
SW_L, SW_H = 280, 28
SOLO_FASE = {"Draft": "Limited"}       # le fasi di Advanced filters che hanno senso in un formato solo: negli altri il pulsante non c'e'
# le ricerche preimpostate di Spots (13 nov 2026, Autore: «spots ... deve dare una combo di filtri preimpostati per risolvere le ricerche fondamentali tra le
# partite / ne schiaccio uno e tutti i filtri si combinano per quella ricerca»): (gruppo, nome, cosa cerca, filtri, vista che risponde, Group by del Report)
PRESET = (
    ("OPENING HAND", "Kept 7 · which cards win", "No mulligan · Cards: the cards in your hand and their win rate", {"mull": "0"}, "cards", None),
    ("OPENING HAND", "After a mulligan · which cards win", "One mulligan · Cards: the cards in your hand", {"mull": "1"}, "cards", None),
    ("OPENING HAND", "Kept 7 on the draw", "No mulligan, on the draw · Cards: the cards in your hand", {"mull": "0", "partenza": "Draw"}, "cards", None),
    ("OPENING HAND", "You missed a land drop", "By your 4th turn", {"sit:io_terra": "Yes"}, "chart", None),
    ("OPENING HAND", "You curved out", "A spell on each of your turns 2, 3 and 4", {"sit:io_curva": "Yes"}, "chart", None),
    ("ATTACK", "All-in into open mana", "Everything attacked, the opponent had 2+ untapped lands", {"sit:io_tutto_aperto": "Yes"}, "chart", None),
    ("ATTACK", "Held back against open mana", "2+ untapped lands: you never attacked with everything", {"sit:io_tutto_aperto": "No"}, "chart", None),
    ("ATTACK", "Attacked into a tapped-out opponent", "The opponent had no untapped land", {"sit:io_att_chiuso": "Yes"}, "chart", None),
    # gli attacchi mancati (14 nov 2026): una finestra in cui attaccare era sicuro, non un errore (non vede la mano di lui); il Watch › di L9 in Decisions › Leaks
    ("ATTACK", "Missed attack into an open board", "You had an attacker ready, the opponent was tapped out with no untapped blockers, and you did not attack · "
     "a maximum, grade C · Watch it in Decisions › Habits (L9)", {"sit:io_non_att_chiuso": "Yes"}, "chart", None),
    ("ATTACK", "Missed lethal on board", "Your power through their untapped blockers reached their life, and they survived the turn · a maximum, grade C", {"sit:io_letale_mancato": "Yes"}, "chart", None),
    ("ATTACK", "You attacked first", "The first attack of the game was yours", {"sit:io_primo": "Yes"}, "chart", None),
    ("DEFENSE", "On defense", "You defended more than you attacked", {"sit:io_difende": "Yes"}, "chart", None),
    ("DEFENSE", "Opponent attacked · you blocked", "At least one block when attacked", {"sit:io_blocca": "Yes"}, "chart", None),
    ("DEFENSE", "Opponent attacked · you never blocked", "Attacked, and no block in the whole game", {"sit:io_blocca": "No"}, "chart", None),
    ("DEFENSE", "Opponent attacked into your open mana", "You had 2+ untapped lands", {"sit:lui_att_aperto": "Yes"}, "chart", None),
    ("INSTANT SPEED", "You cast on the opponent's turn", "Instants and flash", {"sit:io_nel_suo": "Yes"}, "chart", None),
    ("INSTANT SPEED", "Opponent cast on your turn", "Their instants and flash", {"sit:lui_nel_mio": "Yes"}, "chart", None),
    ("INSTANT SPEED", "You passed with mana up", "2+ untapped lands at the end of your turn", {"sit:io_passa_aperto": "Yes"}, "chart", None),
    # dai filtri situazionali dei replay (13 nov 2026)
    ("LIFE, BOARD AND REMOVAL", "You survived at 5 life or less", "Your lowest life was 1-5", {"s_vita_io": "1-5"}, "chart", None),
    ("LIFE, BOARD AND REMOVAL", "More creatures at your turn 5", "At the end of your 5th turn", {"s_crea_t5": "More creatures"}, "chart", None),
    ("LIFE, BOARD AND REMOVAL", "Fewer creatures at your turn 5", "At the end of your 5th turn", {"s_crea_t5": "Fewer creatures"}, "chart", None),
    ("LIFE, BOARD AND REMOVAL", "You removed none of their permanents", "No removal landed in the whole game", {"s_rim_io": "0"}, "chart", None),
    ("LIFE, BOARD AND REMOVAL", "Opponent wiped the board", "3+ permanents at once", {"s_wipe_lui": "Yes"}, "chart", None),
    ("LIFE, BOARD AND REMOVAL", "Opponent countered your spell", "A spell of theirs targeted yours on the stack", {"s_counter_lui": "Yes"}, "chart", None),
    ("LIFE, BOARD AND REMOVAL", "Opponent stumbled on lands", "2+ land drops short by their turn 4", {"s_terre_lui4": "2+ short"}, "chart", None),
)
# come si ordina la tabella delle partite per colonna (13 nov 2026); None va in fondo. La mano: per terre in mano
ORDINI_PARTITE = {"data": lambda x: x["quando"], "mio": lambda x: (x.get("mio") or "").strip().lower() or None,
                  "suo": lambda x: (len(v), "WUBRG".index(v[0]) if v[0] in "WUBRG" else 5, v) if (v := DA.vs_di(x)) else None,
                  "via": lambda x: x.get("partenza"), "mull": lambda x: x.get("mulligan"), "esito": lambda x: 1 if x["vinta"] else 0,
                  "turni": lambda x: x.get("turno"), "spotev": lambda x: _SPOT_EV.get(x.get("partita")),
                  # le carte di EV piu' alto e piu' basso di ogni partita, per il loro EV (18 nov 2026, Autore: «anche most ev card e lowest ev card devono
                  # essere ordinabili cliccando sul titoletto, ordinabili per ev ovviamente»)
                  "best": lambda x: (_CARTE_EV.get(x.get("partita")) or (None, None))[0],
                  "worst": lambda x: (_CARTE_EV.get(x.get("partita")) or (None, None))[1]}
# l'EV della carta migliore e peggiore di ogni partita (disegna_partite lo riempie quando la tabella si ordina per quelle colonne)
_CARTE_EV = {}
# l'EV dello spot di ogni partita della tabella (18 nov 2026): lo riempie disegna_partite coi filtri di adesso, prima di ordinare
_SPOT_EV = {}
# 18 nov 2026 (Autore: «e spot? dovremmo ripensarle?», poi «Si', tutte e tre»): in testa dove guadagni e dove perdi EV, trovati da soli fra le situazioni di
# prima e d'inizio partita; le ricerche preimpostate restano come domande di partenza
SPOT_MODI = (("auto", "EV spots"), ("preset", "Starting questions"))
# il Leak Finder (15 nov 2026, Autore: «da ora non si chiama più performance ma leak finder, deve essere un leak finder a tutti gli effetti»): i leak sono
# la vista d'apertura
# Leaks dopo Chart (15 nov 2026, Autore: «metti la scheda leaks dopo la scheda charts», poi «metti le schede in ordine: charts / leaks / spots»):
# le cartelle in quest'ordine e si apre sulla prima, Chart
def nome_famiglia(f):
    """Il nome in inglese di una famiglia delle sinergie (quello della rete del Board, rete_sinergie.NOMI)."""
    try:
        import rete_sinergie as RS
        return RS.NOMI.get(f, f.replace("_", " "))
    except Exception:      # noqa: BLE001
        return f.replace("_", " ")


VELOCITA = (0.5, 1.0, 2.0, 3.0)      # le velocita' del replayer (19 nov 2026, Autore: «aggiungi velocita' per 3 anche»)
TESTA_TAB = "#1a2230"     # la fascia dietro i titoli delle colonne delle tabelle (19 nov 2026, i tre livelli)
MU_MODI = (("matchups", "Matchups"), ("gemme", "Gem events"))      # le sotto-schede di Matchups (18 nov 2026)
ALTO_SUB, LARGA_SUB = 30, 150       # le sotto-cartelle
VITTORIE_CORSA = 7          # una corsa di un evento Bo1 finisce a 7 vittorie (il trofeo) o a 3 sconfitte
SCONFITTE_CORSA = 3
CARTE_MODI = (("games", "By games"), ("card", "Card spot"))     # le sotto-schede di Cards (18 nov 2026)
# Report e Matchups in una scheda sola, Breakdown (18 nov 2026, Autore: «possiamo ridisegnare in maniera piu' intuitiva report e match up in un unica
# scheda?», poi «Si', tutte e tre»): la chiave interna resta «report» (le ricerche preimpostate, la playlist, le finestre staccate)
# Breakdown, il secondo giro (18 nov 2026, Autore: «break down da troppe opzioni: dovrebbe incrociare i mazzi di player vs quali mazzi incontra e in
# quale categoria: es io voglio sapere quante volte incontro e vinco vs orzov life gain in evento standard best of one overall o quante volte lo stesso spot
# con un mio mazzo specifico ma in lega ... però voglio un sistema di filtro intelligente»): quattro scelte, ognuna mostra solo cio' che c'e' date le altre
BD_EVENTI = {"Ladder": "Ranked · Bo1", "Traditional_Ladder": "Ranked · Bo3", "Play": "Play · Bo1", "Traditional_Play": "Play · Bo3",
             "DualColorPrecons": "Dual Color Precons"}
# la colonna dei colori prima del nome (19 nov 2026, Autore: «in match ups prima del nome dei mazzi la colonna di colore/i di quel mazzo»)
BD_COLONNE = (("col", "COLORS", 96), ("nome", "", 280), ("n", "MET", 150), ("wl", "W-L", 80), ("wr", "WIN RATE", 180), ("ev", "EV A GAME", 90), ("play", "ON THE PLAY", 100),
              ("draw", "ON THE DRAW", 100), ("ultima", "LAST", 90))


# tutti i formati e le loro code negli Smart filters (18 nov 2026, Autore: «modifichiamo smart filters in testa aggiungendo tutti i formati e tutti gli
# eventi di quei formati cosi' matchup si auto filtra»): i formati di Arena (i nomi di DA.NOMI_FMT) e per ognuno le sue code, Ranked e Play, Bo1 e Bo3; le
# code dei formati diversi dallo Standard sono quelle di /meta-periods/active di Untapped (Alchemy_Ladder, Explorer_Ladder, Historic_Ladder, Timeless_Ladder,
# Brawl_Ladder e le Traditional_ in Bo3); in piu' gli eventi che hai giocato in quel formato
FORMATI_ARENA = {"Constructed": ("Standard", "Alchemy", "Explorer", "Historic", "Timeless", "Brawl", "Standard Brawl", "Dual Color Precons", "Jump In"),
                 "Limited": ("Limited",)}
EVENTI_ARENA = {"Standard": ("Ladder", "Traditional_Ladder", "Play", "Traditional_Play"),
                "Alchemy": ("Alchemy_Ladder", "Traditional_Alchemy_Ladder"), "Explorer": ("Explorer_Ladder", "Traditional_Explorer_Ladder"),
                "Historic": ("Historic_Ladder", "Traditional_Historic_Ladder"), "Timeless": ("Timeless_Ladder", "Traditional_Timeless_Ladder"),
                "Brawl": ("Brawl_Ladder",), "Dual Color Precons": ("DualColorPrecons",)}


def nome_evento(ev, formato=None):
    """L'evento detto come si legge: «Standard · Ranked · Bo1», «Historic · Ranked · Bo3», «Quick Draft · FRA», «Dual Color Precons»."""
    import re as _re
    if not ev:
        return "Unknown event"
    if ev.startswith("cal:"):       # un evento del calendario di Wizards senza il nome interno di Arena
        return ev[4:]
    m = _re.fullmatch(r"(Traditional_)?([A-Za-z]+)_(Ladder|Play)", ev)
    if m and m.group(2) not in ("Traditional",):
        return f"{m.group(2).title()} · {'Ranked' if m.group(3) == 'Ladder' else 'Play'} · {'Bo3' if m.group(1) else 'Bo1'}"
    m = _re.match(r"(QuickDraft|PremierDraft|TradDraft|Sealed|TradSealed)_([A-Z0-9]+)", ev)
    if m:
        try:            # col nome del set (19 nov 2026, la tendina con tutti gli eventi del gioco: «Quick Draft · Reality Fracture (FRA)»)
            from icone import nome_set as _ns
            n_set = _ns(m.group(2))
        except Exception:      # noqa: BLE001
            n_set = None
        return {"QuickDraft": "Quick Draft", "PremierDraft": "Premier Draft", "TradDraft": "Traditional Draft", "Sealed": "Sealed",
                "TradSealed": "Traditional Sealed"}[m.group(1)] + " · " + (f"{n_set} ({m.group(2)})" if n_set and n_set != m.group(2) else m.group(2))
    base = BD_EVENTI.get(ev) or ev.replace("_", " ")
    if formato and formato not in ("limited", "precon") and ev in BD_EVENTI:
        return f"{formato.capitalize()} · {base}"
    return base


# l'ordine delle cartelle (19 nov 2026, Autore: «riordina le schede: chart / match up / cards / e poi il resto»)
VISTE = (("chart", "Chart"), ("report", "Matchups"), ("cards", "Cards"), ("leaks", "Habits"), ("spots", "Spots"), ("compare", "Compare"), ("decisions", "Decisions"),
         ("luck", "Luck"), ("mine", "My filters"))
DISEGNI = {"leaks": "disegna_leaks", "chart": "disegna_grafico", "spots": "disegna_spot", "report": "disegna_report", "matchups": "disegna_matchup", "compare": "disegna_confronto",
           "mine": "disegna_miei", "cards": "disegna_carte", "decisions": "disegna_decisioni", "luck": "disegna_fortuna"}
DEC_MODI = (("attacco", "Attacks"), ("blocco", "Blocks"), ("mull", "Mulligans"), ("costo", "Costliest"), ("leak", "Habits"), ("cimitero", "Graveyard"))
RARITA_NOME = {"M": "mythic", "R": "rare", "U": "uncommon", "C": "common"}
COLORI_COSTO = {"rosso": "#ff5d5d", "giallo": "#f0ad4e", "verde": "#5cb85c", "nd": "#7a7a80"}
LARGA_CARTA = 112                               # le carte della cartella Cards
ALTO_MIO = 58                                   # una riga dei filtri personali
GRIGI = ("#2a2a30", "#3a3a42", "#0f86cc")       # i pulsanti a pillola grigi, azzurri se scelti


def chip(c, x0, y0, x1, y1, testo, on, font, scritta=None):
    """Una voce da scegliere disegnata su una tela (i valori dei filtri, vs all, Pairs e Trios, i momenti del replayer): un pulsante S3 grigio, azzurro se
    scelto (14 nov 2026, Autore: «ogni pulsante esistente deve avere il redesign in linea con lo stile»; fino a quel giorno rettangoli col bordo)."""
    disegna_s3(c, x0, y0, x1, y1, testo, font, GRIGI, premuto=on, icona=False, scritta=scritta or ("#ffffff" if on else C["testo"]))
ALTO_TAB, LARGA_TAB = 34, 132                   # le cartelle
ALTO_AREE = 26                                  # le cartelle delle sottovoci del Board in Advanced filters (16 nov 2026)
LARGA_DECK = 1000                               # la finestra By deck
ALTO_PARTITA = 30                               # una riga della tabella delle partite (30 dal redesign del 14 nov 2026; era 24)
ALTO_CTRL = 158                                 # la barra del replayer della board: il grafico della partita sopra, i comandi sotto
SEGNO_FILTRO = C["accento"]                       # il segno degli spot dei filtri nel replayer (15 nov 2026; «C»: imbuto bianco sul quadratino blu)
ALTO_GRAF = 92                                  # il grafico della partita nella barra
PASSI_SPINTA, PASSI_COLPO = 18, 26
OMBRA_ALFA = 60             # l'ombra sulla meta' di chi non agisce (0-255; 14 nov 2026; «meno ombra»: era 92)
OMBRA_SFUMA = 70            # la sfumatura dell'ombra, in pixel del progetto, per parte della linea di mezzo
# i tempi del replayer (14 nov 2026, Autore: «tutto piu' lento. regola: l'essere umano comprende un'azione alla volta in ordine e non rapida»): circa
# una volta e mezza quelli della prima versione dello stesso giorno (voli 300/500/450 ms di pausa, 0,35 s a volo, il passo a 3,2 s)
def con_teschio(im):
    """La carta grigia (morta) col badge della morte (15 nov 2026, Autore: «morte a esagono», fra tre stili esport): la carta un po' piu' scura e al
    centro l'esagono scuro col contorno grigio, il teschio chiaro dentro e sotto il tab grigio con KO. Fino a quel giorno un teschio grande a tratto
    bianco (14 nov 2026, «teschio C»). im: PIL RGBA. Disegnato a 4x e ridotto."""
    from PIL import Image, ImageDraw
    import disegno_tappeto as DT
    w, h = im.size
    S = 4
    st = Image.new("RGBA", (w * S, h * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(st)
    R = min(w * 0.40, h * 0.27) * S                # il raggio dell'esagono (punta in alto)
    cx, cy = w * S / 2, h * S * 0.45
    esa = lambda r: [(cx + r * x, cy + r * y) for x, y in ((0, -1), (0.866, -0.5), (0.866, 0.5), (0, 1), (-0.866, 0.5), (-0.866, -0.5))]
    grigio, chiaro, fondo = (138, 147, 163, 255), (232, 236, 242, 255), (28, 36, 50, 240)
    d.polygon(esa(R * 1.12), fill=(6, 8, 12, 150))
    d.polygon(esa(R), fill=grigio)
    d.polygon(esa(R * 0.89), fill=fondo)
    r = R * 0.42                                    # il teschio: la calotta, la mascella, gli occhi, il naso
    ct = cy - R * 0.06
    d.ellipse((cx - r, ct - r, cx + r, ct + r), fill=chiaro)
    d.rounded_rectangle((cx - r * 0.6, ct + r * 0.55, cx + r * 0.6, ct + r * 1.25), radius=r * 0.18, fill=chiaro)
    for sx in (-1, 1):
        d.ellipse((cx + sx * r * 0.42 - r * 0.27, ct - r * 0.02 - r * 0.27, cx + sx * r * 0.42 + r * 0.27, ct - r * 0.02 + r * 0.27), fill=fondo)
    d.polygon([(cx, ct + r * 0.38), (cx - r * 0.13, ct + r * 0.62), (cx + r * 0.13, ct + r * 0.62)], fill=fondo)
    for sx in (-0.2, 0.2):
        d.line((cx + sx * r, ct + r * 0.85, cx + sx * r, ct + r * 1.25), fill=fondo, width=max(1, int(r * 0.09)))
    tw, th = R * 0.95, R * 0.42                     # il tab KO sotto l'esagono, sopra la sua punta
    ty = cy + R * 0.86
    d.rounded_rectangle((cx - tw / 2 - S, ty - th / 2 - S, cx + tw / 2 + S, ty + th / 2 + S), radius=th * 0.2, fill=(6, 8, 12, 150))
    d.rounded_rectangle((cx - tw / 2, ty - th / 2, cx + tw / 2, ty + th / 2), radius=th * 0.18, fill=grigio)
    f = DT.font(max(8, th * 0.78))
    bb = d.textbbox((0, 0), "KO", font=f)
    d.text((cx - (bb[2] - bb[0]) / 2 - bb[0], ty - (bb[3] - bb[1]) / 2 - bb[1]), "KO", font=f, fill=(28, 36, 50, 255))
    out = im.copy()
    velo = Image.new("RGBA", im.size, (0, 0, 0, 90))
    velo.putalpha(Image.eval(im.getchannel("A"), lambda a: min(a, 90)))
    out.alpha_composite(velo)
    out.alpha_composite(st.resize((w, h), Image.LANCZOS))
    return out


PIASTRA_W, PIASTRA_H = 66, 28    # la piastra broadcast del danno e della vita (icona_danno), in pixel
# dove sta la piastra: la goccia sull'angolo in alto a destra di chi e' colpito, la spada in basso a sinistra di chi colpisce, accanto al cerchio della vita
GOCCIA_DX, GOCCIA_DY = -PIASTRA_W / 2 + 4, PIASTRA_H / 2 - 2
SPADA_DX, SPADA_DY = PIASTRA_W / 2 - 4, -PIASTRA_H / 2 - 6
VITA_DX = -PIASTRA_W / 2 - 6
def alza_icone(c):
    """Le piastre del danno e della vita sopra a tutte le carte (15 nov 2026, Autore: «controlla la posizione delle nuove icone perche' appaiono dietro
    le carte»): le copie delle carte che le animazioni creano dopo (la carta che si tappa, quella che scivola, quella che vola) le coprivano, e le piastre,
    piu' larghe delle icone di prima, sporgono sulle carte vicine. Si rimettono in cima fra un'azione e l'altra e a fine passo; la schermata finale resta
    sopra a tutto."""
    try:
        c.tag_raise("danni")
        c.tag_raise("cuori")
        c.tag_raise("finale")
    except Exception:      # noqa: BLE001 - una tela gia' chiusa
        pass


RIVELA_MS = 1300            # la carta rivelata resta al centro (il censimento, 14 nov 2026)
MANA_MS = 700               # un simbolo di mana dalla terra alla vaschetta (M1)
SPENDI_MS, SPENDI_PAUSA = 520, 160      # un simbolo dalla vaschetta alla carta che si paga, e la pausa prima del prossimo
SCRY_MS = 1500              # le carte guardate restano a ventaglio col loro TOP o BOTTOM (S1)
POTENZIA_MS = 1100          # l'impulso di un potenziamento: la carta accesa e il «+3/+3» che sale (16 nov 2026)
MESCOLA_MS = 1100           # il grimorio che si rimescola
FOTOGRAMMA = 8               # ms fra due fotogrammi delle animazioni (guidate dal tempo vero: un fotogramma in ritardo non le rallenta)
VELO_ALFA = 150             # il velo del duello: quanto si scurisce il resto della tavola
DUELLO_MS = 4 * 70 + 480 * 4 + 5 * 45 + 150 + 780 + 3 * 70      # un duello senza i movimenti (luce, pause, scossa, danni, spegni)
PAUSA_VOLI = 480           # ms fra due azioni della stessa fase («azione, pausa, risposta, pausa»)
PAUSA_FASI = 780           # ms fra le fasi di un passo: l'effetto, poi la magia risolta al suo posto, poi il resto
PAUSA_FRECCIA = 700        # ms fra la carta arrivata in pila e la sua freccia, e fra una freccia e l'altra
ANIM_TOTALE = 3300          # ms: tutti i voli di un passo stanno qui dentro (con tanti voli ognuno si accorcia)
OMBRA_FADE = 720            # ms: l'ombra passa da una meta' all'altra sfumando, quando cambia chi agisce
LARGA_RACCONTO = 300                            # la colonna del racconto a destra della tavola
LARGA_LISTA = 236                               # le due liste ai lati della tavola: il tuo mazzo (R6) e le sue carte viste (R1)
LARGA_PILA_SOLA = 160                           # col racconto staccato, sulla tavola resta la colonna della magia in pila (da li' partono le frecce)
ALTO_RIGA_LISTA = 18
# per fasi della partita (12 nov 2026, Autore: «il menu a tendine creiamolo per macro fasi partita: formato evento e deck - poi start e mulligan - lands in
# hand / cards in hand possiamo toglierlo, their card anche»): prima della partita (con By deck), l'apertura, l'avversario, com'e' finita, quando.
# «deck» e' il pulsante By deck; Card in hand e Their card non sono tendine (restano in Split by, Group by e negli Spots)
FASI = (("BEFORE THE GAME", ()),      # senza + more (13 nov 2026, Autore: «sezione before the game non serve il pulsante more»): i colori del tuo mazzo stanno in Advanced filters
        ("OPENING AND FIRST TURNS", ("economiche", "crea_mano", "sit:io_terra", "sit:lui_terra", "sit:io_curva", "sit:io_crea2", "sit:lui_crea2",
                                     "luck3", "luck5", "luck7")),
        ("THE OPPONENT AND THE FIGHT", ("sit:io_primo", "sit:io_nel_suo", "sit:lui_nel_mio", "sit:lui_bersagli", "sit:io_att_aperto", "sit:io_att_chiuso",
                                        "sit:lui_att_aperto", "sit:io_passa_aperto", "sit:lui_passa_aperto", "sit:io_blocca", "sit:io_difende",
                                        "sit:io_tutto", "sit:io_tutto_aperto", "sit:io_non_att_chiuso", "sit:io_letale_mancato")),
        ("THE END OF THE GAME", ("fine", "sit:io_morti", "sit:lui_morti", "leak_l7")),
        ("WHEN", ("giorno", "pausa", "dopo", "serie_prima", "stagione")))      # i filtri in piu' di ogni fase, nel suo +
LARGA_FASE = 780
LARGA_RIGHE_AV = 960            # la tela delle righe di Advanced filters (le righe «cast» con la carta e la fase)
# i filtri della finestra Advanced filters (13 nov 2026): due schede, You e Opponent, e dentro ognuna le fasi (stesso giorno, Autore: «nei filtri avanzati
# ci mancano le giocate nel turno avversario, le sue nei nostri turni, le fasi di attacco di entrambi e di difesa di entrambi quindi ci devono essere in you e
# opponent delle sotto schede di fasi e you e opponent diventano le macro schede»). {scheda: ((fase, ((titolo, chiavi), ...)), ...)}
AVANZATI = {
    # niente sezione del mazzo (14 nov 2026, Autore: «advanced filters > opening hand la parte di filtri dedicata al mazzo la trovo superflua poiché in
    # smart filters abbiamo i filtri by deck»): colori, classe, terre, creature, costo medio, magie da 2, rimozioni e rare del mazzo restano variabili
    # dell'analizzatore (Report › Group by, Split by, Spots), per confrontare i mazzi fra loro; un mazzo si sceglie con By deck
    # la mano iniziale descritta riga per riga (18 nov 2026, Autore: «quel tab va rivisto perche' da troppe opzioni, studia la migliore soluzione di quel tab
    # affinche' possa descrivere una mano generica o specifica nel dettaglio di ogni carta»): «?mano_req» e' il costruttore (righe_mano); le tendine di prima
    # per tipo (crea_in_mano, ist_mano...) e la carta specifica restano variabili dell'analizzatore (Split by, Group by, Spots), non piu' qui
    "io": (("Opening hand", (("YOUR OPENING HAND · ONE LINE PER CARD OR GROUP OF CARDS: HOW MANY · WHAT · WHICH CARD · WHICH MANA VALUE", ("?mano_req",)),
                              # per formato (14 nov 2026): nel Limited la tabella misurata, nel Constructed la regola a 60 carte; si vede solo quella del formato
                              ("YOUR MULLIGAN DECISION", ("mull_tabella", "mull_60")))),
           # le pescate (13 nov 2026, Autore: «nei filtri di you e opponent aggiungiamo anche le pescate nel proprio e nel turno avversario più alcuni filtri
           # generali che indicano che sono avvenute 1, 2 o più pescate in almeno uno dei turni»)
           ("Your turns", (("WHAT YOU CAST ON YOUR TURNS", ("@t_io",)),
                           ("MANA LEFT UNUSED AT THE END OF YOUR TURNS (LANDS MINUS WHAT YOU CAST; GRADE C)", ("@t_uio",)),
                           ("MANA USED IN YOUR FIRST 5 TURNS", ("t_effio",)),
                           ("YOUR DRAWS ON YOUR TURNS (THE DRAW STEP TOO)", ("@t_pio",)),
                           ("EXTRA DRAWS", ("t_peio",)),
                           ("YOUR LANDS DRAWN AGAINST CHANCE (C1)", tuple(f"luck{N}" for N in DA.TURNI_FORTUNA)),
                           # il tempismo degli istantanei (14 nov 2026, D2-D3 del censimento): una famiglia sola, coi lanci nel suo turno e il leak L6
                           ("INSTANT TIMING · YOUR INSTANTS AND FLASH", ("tm_nel_mio", "tm_aspetta", "tm_perso", "sit:io_nel_suo", "sit:io_passa_aperto", "leak_l6")))),
           ("Opponent's turns", (("WHAT YOU CAST ON THE OPPONENT'S TURNS", ("@t_iox",)),
                                 ("YOUR DRAWS ON THE OPPONENT'S TURNS", ("@t_piox",)),
                                 ("EXTRA DRAWS", ("t_peio",)))),
           ("Attack", (("WHEN YOU COULD ATTACK, TURN BY TURN", ("@t_qio",)),
                       ("YOUR ATTACKS, TURN BY TURN", ("@t_aio",)),
                       ("THE OPPONENT'S UNTAPPED LANDS WHEN YOU ATTACK", ("@t_mio",)),
                       ("IN THE WHOLE GAME", ("sit:io_primo", "sit:io_tutto", "sit:io_tutto_aperto", "sit:io_att_aperto", "sit:io_att_chiuso", "sit:io_non_att_chiuso", "sit:io_letale_mancato")),
                       # quante volte (14 nov 2026, la pagella dell'enciclopedia, capitolo 7): voci_partita.py
                       ("HOW MANY TIMES IN THE GAME", ("primo_att_io", "n_att_io", "non_att_io", "tutto_n_io", "parte_n_io", "att_pw_io", "esposto_lui",
                                                       "trucco_comb_lui")))),
           ("Defense", (("YOUR DEFENSE ON THE OPPONENT'S TURNS", ("@t_dio",)),
                        ("IN THE WHOLE GAME", ("sit:io_blocca", "sit:io_difende", "trucco_comb_io", "pericolo_io", "esposto_io")))),
           # le abilita' attivate, la carta e quando (13 nov 2026, Autore: «saccare reliquia dopo draw step di Oppo», poi «Sì, aggiungilo»): «&» = il
           # costruttore a righe per carta (righe_abilita), il filtro e' una lista di «Carta · quando»
           ("Abilities", (("YOUR ACTIVATED ABILITIES · THE CARD AND WHEN YOU ACTIVATED IT", ("&ab_io",)),)),
           # i filtri situazionali dai replay (13 nov 2026, «sii minuzioso e dettagliato parti dai replay»): terre, vita e campo, rimozioni e interazione
           ("Game", (("LAND DROPS", ("s_terre_io3", "s_terre_io4", "s_terre_io5")),
                     ("LIFE AND BOARD AT THE END OF YOUR TURNS", ("s_vita_io", "s_vita_t3", "s_vita_t5", "s_vita_t7", "s_crea_t3", "s_crea_t5", "s_crea_t7")),
                     ("REMOVAL AND INTERACTION", ("s_rim_io", "s_wipe_io", "s_counter_io", "s_cim_io", "s_magie_io", "rim_lanciate_io", "rim_quando_io", "rim_fine_io",
                                                  "contrastate_io")),
                     ("CARDS · DISCARDS, SCRY AND SURVEIL", ("scarti_io", "scry_io", "scry_giu_io", "surveil_io")),
                     ("THE END", ("senza_crea", "fine_entro", "durata")),
                     ("MANA, REMOVAL AND CARDS LEFT", ("c2_t3", "rim_prima", "mano_io3", "mano_io5", "mano_io7")),
                     ("HABITS · CLUES FROM THE REPLAY, NOT VERDICTS", tuple(f"leak_l{i}" for i in range(1, 16))),
                     ("GRAVEYARD AND EXILE · FROM THE CARD TEXT", ("rian_io", "esil_io", "odio_io")),
                     # la probabilita' di vincere nella partita (14 nov 2026, la pagella dell'enciclopedia: capitoli 15 e 22)
                     ("WIN CHANCE OVER THE GAME · FROM THE MODEL, GRADE C", ("p_max", "p_min", "forma", "svolta", "svolta_fase")))),
           # i pick del draft (15 nov 2026, «prosegui con i pick del draft»): draft_log.py, solo nel Limited
           ("Draft", (("YOUR DRAFT · LIMITED ONLY, FROM THE PICKS IN YOUR LOGS", ("d_impegno", "d_p1", "d_ruote", "d_p1p1", "d_rare_prese", "d_rare_passate",
                                                                                  "d_drafter")),)),),
    "lui": (("Opening hand", (("THE OPPONENT", ("suo_mull",)),)),
            ("Their turns", (("WHAT THEY CAST ON THEIR TURNS", ("@t_lui",)),
                             ("MANA THEY LEFT UNUSED ON THEIR TURNS (GRADE C)", ("@t_ului",)),
                             ("MANA THEY USED IN THEIR FIRST 5 TURNS", ("t_efflui",)),
                             ("THEIR DRAWS ON THEIR TURNS (THE DRAW STEP TOO)", ("@t_plui",)),
                             ("EXTRA DRAWS", ("t_pelui",)))),
            ("Your turns", (("WHAT THEY CAST ON YOUR TURNS", ("@t_luix",)),
                            ("THEIR DRAWS ON YOUR TURNS", ("@t_pluix",)),
                            ("EXTRA DRAWS", ("t_pelui",)))),
            ("Attack", (("WHEN THEY COULD ATTACK, TURN BY TURN", ("@t_qlui",)),
                        ("THEIR ATTACKS, TURN BY TURN", ("@t_alui",)),
                        ("YOUR UNTAPPED LANDS WHEN THEY ATTACK", ("@t_mlui",)),
                        ("IN THE WHOLE GAME", ("sit:lui_att_aperto", "primo_att_lui", "n_att_lui", "non_att_lui", "tutto_n_lui", "parte_n_lui", "att_pw_lui")))),
            ("Defense", (("THEIR DEFENSE ON YOUR TURNS", ("@t_dlui",)),)),
            ("Abilities", (("THEIR ACTIVATED ABILITIES · THE CARD AND WHEN THEY ACTIVATED IT", ("&ab_lui",)),)),
            ("Game", (("LAND DROPS", ("s_terre_lui3", "s_terre_lui4", "s_terre_lui5")),
                      ("LIFE AND CREATURES", ("s_vita_lui", "senza_lui")),
                      ("CARDS IN THEIR HAND", ("mano_lui3", "mano_lui5", "mano_lui7")),
                      ("A SPECIFIC CARD THEY SHOWED IN THE GAME", ("%sue",)),
                      ("REMOVAL AND INTERACTION", ("s_rim_lui", "s_wipe_lui", "s_counter_lui", "s_cim_lui", "s_magie_lui", "rim_lanciate_lui", "rim_prima_lui",
                                                   "lui_prima_crea", "trucco_comb_lui", "contrastate_lui")),
                      ("CARDS · DISCARDS, SCRY AND SURVEIL", ("scarti_lui", "scry_lui", "scry_giu_lui", "surveil_lui")),
                      ("GRAVEYARD AND EXILE · FROM THE CARD TEXT", ("rian_lui", "esil_lui", "odio_lui")))))}
# il Board (16 nov 2026, Autore: «da board derivano tutte le aree del board che abbiamo in gioco», poi «porta board in you (Hero Player) e Opponent prima di
# attack, così separiamo le sezioni, tienila così com'è con i suoi sotto menù»): una fase Board in Hero Player e in Opponent, prima di Attack, con le sue
# sottovoci per area (DA.BOARD_GRUPPI); in ogni area il campo di quel giocatore all'inizio dei suoi turni e di quelli dell'altro, e in Hero Player chi e'
# avanti. Le chiavi sono le famiglie «b...» di per_turno (DA.campo_inizio_turno)
def _board_sezioni(sch, aree):
    sezioni = []
    for a in aree:
        nm = next(n_ for k_, n_, _v in DA.BOARD_AREE if k_ == a).upper()
        if sch == "io":
            sezioni.append((f"YOUR {nm} · AT THE START OF YOUR TURNS", (f"@t_b{a}io",)))
            sezioni.append((f"YOUR {nm} · AT THE START OF THE OPPONENT'S TURNS", (f"@t_b{a}iox",)))
        else:
            sezioni.append((f"THEIR {nm} · AT THE START OF THEIR TURNS", (f"@t_b{a}lui",)))
            sezioni.append((f"THEIR {nm} · AT THE START OF YOUR TURNS", (f"@t_b{a}luix",)))
    return tuple(sezioni)


BOARD_AV = {sch: tuple((nome, _board_sezioni(sch, aree)) for nome, aree in DA.BOARD_GRUPPI) for sch in ("io", "lui")}
for _sch in ("io", "lui"):
    _fasi = list(AVANZATI[_sch])
    _fasi.insert(next(j for j, (n_, _s) in enumerate(_fasi) if n_ == "Attack"), ("Board", ()))      # le sezioni le da' la sottovoce aperta
    AVANZATI[_sch] = tuple(_fasi)
# il ruolo delle magie e quando (stesso giorno): nelle fasi dei turni di You e Opponent, sotto le giocate per tipo
for _sch, _fase, _k, _tit in (("io", "Your turns", "@t_rio", "WHAT YOU CAST ON YOUR TURNS · BY ROLE, BEFORE OR AFTER COMBAT (FROM THE TEXT, GRADE C)"),
                              ("io", "Opponent's turns", "@t_riox", "WHAT YOU CAST ON THE OPPONENT'S TURNS · BY ROLE (FROM THE TEXT, GRADE C)"),
                              ("lui", "Their turns", "@t_rlui", "WHAT THEY CAST ON THEIR TURNS · BY ROLE, BEFORE OR AFTER COMBAT (FROM THE TEXT, GRADE C)"),
                              ("lui", "Your turns", "@t_rluix", "WHAT THEY CAST ON YOUR TURNS · BY ROLE (FROM THE TEXT, GRADE C)")):
    _fasi = list(AVANZATI[_sch])
    _j = next(j for j, (n_, _s) in enumerate(_fasi) if n_ == _fase)
    _sez = list(_fasi[_j][1])
    _sez.insert(1, (_tit, (_k,)))
    _fasi[_j] = (_fase, tuple(_sez))
    AVANZATI[_sch] = tuple(_fasi)
SCHEDE_AV = (("io", "Hero Player"), ("lui", "Opponent"))       # 16 nov 2026, Autore: «you (Hero Player)»


# Hero e Opponent (16 nov 2026, Autore: «you che poi deve essere Hero Player al posto di you ovunque», «non usare theyr mai più si usa opponent»): i testi
# di Advanced filters si scrivono come prima (You, their...) e passano tutti da qui. Un testo nuovo non va scritto con their/they: passa comunque da hero_txt.
def hero_txt(t):
    """You/your -> Hero/Hero's, their/they -> Opponent's/Opponent, «the opponent's» -> «Opponent's» (maiuscolo resta maiuscolo)."""
    sub = (("THE OPPONENT'S", "OPPONENT'S"), ("the opponent's", "Opponent's"), ("The opponent's", "Opponent's"),
           ("THEIR", "OPPONENT'S"), ("Their", "Opponent's"), ("their", "Opponent's"), ("THEY", "OPPONENT"), ("They", "Opponent"), ("they", "Opponent"),
           ("THEM", "OPPONENT"), ("them", "Opponent"), ("YOUR", "HERO'S"), ("Your", "Hero's"), ("your", "Hero's"), ("YOU", "HERO"), ("You", "Hero"),
           ("you", "Hero"))
    for a_, b_ in sub:
        t = re.sub(r"(?<![A-Za-z'])" + re.escape(a_) + r"(?![A-Za-z])", b_, t)
    return t


AVANZATI = {sch: tuple((hero_txt(nome).replace("Hero's turns", "Hero's turns"), tuple((hero_txt(ti), kk) for ti, kk in sez)) for nome, sez in fasi)
            for sch, fasi in AVANZATI.items()}
BOARD_AV = {sch: tuple((nome, tuple((hero_txt(ti), kk) for ti, kk in sez)) for nome, sez in gruppi) for sch, gruppi in BOARD_AV.items()}
VALORI_FISSI = {"mull": ("0", "1", "2+"), "partenza": ("Play", "Draw"), "esito": ("Won", "Lost")}      # le tendine con le voci fisse
# le tendine dell'avversario (Opponent, Opp. colors) non ci sono piu' (15 nov 2026, Autore: «rivedi in smart filters i filtri per oppo perche' sono
# ridondanti col pulsante by deck»): l'avversario si sceglie in By deck (vs colors, la variante esatta del suo mazzo); la fase resta, col suo + dei filtri in
# piu' (chi attacca per primo, il mana aperto...), e il suo mazzo resta in Split by, Group by, Spots e Matchups
SEZIONI_FILTRI = (("formato", "evento", "wr_rif", "deck"), ("partenza", "mull", "terre", "esito"), (), ("lunga", "rango"), ("data", "fascia", "sessione"))


def _cartella(x0, x1, top, H, sl=6, r=5):
    """Il contorno di una linguetta da cartella: i fianchi un po' inclinati e gli angoli in alto arrotondati, da (x0, H) a (x1, H)."""
    pts = [(x0, H)]
    cx, cy = x0 + sl + r, top + r
    for i in range(7):
        a = math.pi - (math.pi / 2) * i / 6
        pts.append((cx + r * math.cos(a), cy - r * math.sin(a)))
    cx = x1 - sl - r
    for i in range(7):
        a = math.pi / 2 - (math.pi / 2) * i / 6
        pts.append((cx + r * math.cos(a), cy - r * math.sin(a)))
    pts.append((x1, H))
    return pts


def _segno_stacca(d, cx, cy, colore, fuori):
    """Il segno per staccare una cartella: un riquadro con la freccia che esce in alto a destra; staccata, la freccia rientra."""
    d.rett(cx - 6, cy - 3, cx + 4, cy + 7, bordo=colore, larghezza=1.2, raggio=1.5)
    if fuori:
        d.linea([(cx + 6, cy - 6), (cx, cy)], colore, 1.3)
        d.linea([(cx - 0.5, cy - 4), (cx, cy), (cx + 4, cy + 0.5)], colore, 1.3)
    else:
        d.linea([(cx - 1, cy + 1), (cx + 6, cy - 6)], colore, 1.3)
        d.linea([(cx + 1.5, cy - 6), (cx + 6, cy - 6), (cx + 6, cy - 1.5)], colore, 1.3)


class _Nulla:
    """Un disegno che non disegna: la barra del replayer gia' pronta (le stesse chiamate, nessun lavoro)."""

    def __getattr__(self, k):
        return lambda *a, **kw: None



def modo_iniziale(draft, partite, aperto):
    """Da dove parte Performance: Limited con un draft aperto, se no il formato dell'ultima partita giocata (a pari merito o senza partite, Limited)."""
    if aperto:
        return "Limited"
    ultimo = lambda xs: max((x["quando"].timestamp() for x in xs), default=0)
    return "Standard" if ultimo(partite or []) > ultimo(draft or []) else "Limited"


class _Ricevitore:
    """Al posto delle pagine Limited e Standard di prima: la finestra grande le chiama coi dati nuovi; qui vuol dire «ci sono partite nuove, rileggi i log»."""

    def __init__(self, pagina):
        self.pagina, self.premi, self.aperto, self.sporca = pagina, None, None, False

    def aggiorna(self, *a, **k):
        self.pagina.ricarica()

    def apri(self, chi):
        return None


def p_is_comb(p_):
    return len(p_) > 3 and isinstance(p_[3], dict) and p_[3].get("tipo") == "comb"


def nome_momento(az, k):
    """Il nome di un momento come nei Moments di sempre: «Opening hand», «You T3» (la fine del turno), «You T6 · combat», «You T6 · Moment of Craving»."""
    if k == 0:
        return "Opening hand"
    nome_, _f, t_, rel_ = az[k][:4]
    chi_ = nome_.split(" · ")[0]
    if len(az[k]) > 5 and az[k][5] and "CombatDamage" in nome_:
        return f"{chi_} · combat"
    if rel_ and rel_.get("tipo") == "spell" and (rel_.get("bers") or rel_.get("colpiti")):
        cima_ = ((az[k][1] or {}).get("pila") or [None])[0]
        cima0_ = ((az[k - 1][1] or {}).get("pila") or [None])[0]
        if not (cima_ and cima0_ and cima_[4] == cima0_[4]):
            return f"{chi_} · {rel_.get('nome')}"
    return chi_


def momenti_da_azioni(az):
    """Quali passi di Every action sono i Moments (16 nov 2026): il passo zero; una magia o un'abilita' coi bersagli o che toglie permanenti quando entra in
    pila (non ancora nei passi dopo); il passo del danno in combattimento; l'ultimo passo di ogni turno. -> indici in az, in ordine."""
    out = [0]
    for k_ in range(1, len(az)):
        nome_, f_, t_, rel_ = az[k_][:4]
        danni_ = az[k_][5] if len(az[k_]) > 5 else None
        fine_ = k_ + 1 == len(az) or az[k_ + 1][2] != t_
        cima_ = ((f_ or {}).get("pila") or [None])[0]
        cima0_ = ((az[k_ - 1][1] or {}).get("pila") or [None])[0]
        magia_ = bool(rel_ and rel_.get("tipo") == "spell" and (rel_.get("bers") or rel_.get("colpiti"))) and not (cima_ and cima0_ and cima_[4] == cima0_[4])
        comb_ = bool(danni_) and "CombatDamage" in nome_
        if fine_ or magia_ or comb_:
            out.append(k_)
    return out


class PaginaPerformance:
    MODI = ("Limited", "Standard")

    def __init__(self, tk, padre, F, mana):
        self.tk, self.F = tk, F
        self.fr = tk.Frame(padre, bg=C["fondo"])
        self.blocco = blocco_partita.attacca(self)     # app pubblica: chiusa con Arena o MTGO aperti (15 nov 2026)
        self.limited, self.standard = _Ricevitore(self), _Ricevitore(self)
        self.tipo = "Constructed"
        self.filtri = {}
        self.metrica, self.asse, self.finestra, self.dividi, self.per, self.ordina = "wr", "games", "20", None, "suo", "n"
        self.basso, self.solo_meta, self.vista = "report", False, "chart"       # la vista del pannello: chart, spots, report, matchups o compare
        self.con, self.staccate, self.vs_modo, self.ord_deck = "rest", {}, "all", "n"
        self.partite_fuori = None       # la tabella delle partite nella sua finestra: dict(win, lista, l)        # B del confronto (rest, all, s<i>); le viste staccate: {vista: dict(win, o, l)}
        self.righe, self.sporca, self.deciso, self.modo = None, True, False, "Standard"
        self.dec_modo = "attacco"       # Decisions: gli attacchi, i blocchi o i mulligan
        self.dec_f = {"attacco": {}, "blocco": {}}      # i filtri delle decisioni, per tipo: {chiave: [voci]} (solo le tue scelte)
        self.righe_dec = {"attacco": [], "blocco": []}  # le righe del costruttore dei filtri delle decisioni
        self.mostra_vs_filtro = False
        self.mu_modo = "matchups"       # Matchups: i matchup del mazzo o i suoi eventi a gemme
        self.gem_aperti = set()         # Gem events: gli eventi aperti (le loro partite sotto)
        self.carte_modo = "games"       # Cards: «By games» (le righe) o «Card spot» (l'analisi di una carta)
        self.analisi_di = None   # sotto il grafico: la linea di tutte le partite contro quella filtrata
        self.mostra_guadagno = False    # sotto il grafico: il guadagno delle decisioni contro la media
        self.linea_dec = None           # una riga di Decisions sul grafico: (tipo, nome della riga)
        self.spot_modo = "auto"         # Spots: gli spot in EV (di partenza) o le domande di partenza (le ricerche preimpostate)
        self._lavoro, self.l_carica = None, None
        self.scheda_av = "io"        # la scheda aperta della finestra Advanced filters
        self.playlist = None        # R15: le partite da guardare una dopo l'altra nel replayer (dict(partite, nome)), o None
        self.ord_partite = ("data", False)        # la tabella delle partite: la colonna e il verso (di partenza dalla piu' recente)
        self.fase_av = {"io": 0, "lui": 0}
        self.area_av = {"io": 0, "lui": 0}      # la sottovoce aperta della fase Board (16 nov 2026)      # e la fase aperta di ognuna
        self.costruisci()
        self.fr.bind("<<Davanti>>", lambda e: self.se_sporca(), add="+")
        self.fr.bind("<Destroy>", lambda e: setattr(self, "_chiusa", True) if e.widget is self.fr else None, add="+")      # i fili di sottofondo si fermano
        self.fr.bind("<Map>", lambda e: self.se_sporca(), add="+")
        self.ricarica()

    # ------------------------------------------------------------ la finestra grande
    def segna(self):
        self.sporca = True

    def se_sporca(self):
        if (self.sporca or getattr(self, "_da_disegnare", False)) and self.righe is not None:
            self.disegna()

    def _a_vista(self):
        """Vero se la pagina si vede (come Pagina.davanti: montata e non coperta da un'altra scheda)."""
        from pagina_base import Pagina
        if Pagina.SUBITO:       # le prove disegnano anche le pagine nascoste
            return True
        try:
            if Pagina.AVVIO or not self.fr.winfo_viewable():
                return False
        except Exception:       # noqa: BLE001
            return False
        p_ = str(self.fr)
        return not any(p_ == d or p_.startswith(d + ".") for d in Pagina.DIETRO)

    def parti(self, draft, partite, aperto):
        if not self.deciso:
            self.deciso = True
            self.scegli(modo_iniziale(draft, partite, aperto))

    def scegli(self, modo):
        """Limited o Standard (le chiavi di prima, --scheda limited|standard) o direttamente Constructed / Limited."""
        self.deciso = True
        self.modo = modo
        self.cambia_tipo("Limited" if modo == "Limited" else "Constructed")

    def mostra(self, modo):
        self.scegli(modo)

    def ricarica(self):
        """Le partite dai log, su un filo: la pagina resta viva."""
        if self._lavoro is not None and self._lavoro.is_alive():
            self._di_nuovo = True
            return
        self._di_nuovo = False
        esito = {}

        def lavora():
            try:
                esito["r"] = DA.righe()
            except Exception as e:      # noqa: BLE001 - senza log la pagina lo dice
                esito["r"], esito["e"] = [], e
        self._lavoro = threading.Thread(target=lavora, daemon=True)
        self._lavoro.start()
        if self.righe is None:      # la prima lettura: la scritta al centro della pagina, coi secondi
            self.mostra_carica(0)
        inizio = datetime.datetime.now()

        def aspetta():
            if self._lavoro.is_alive():
                if self.l_carica is not None:
                    self.mostra_carica((datetime.datetime.now() - inizio).total_seconds())
                self.fr.after(150, aspetta)
                return
            self.righe = esito.get("r") or []
            self.togli_carica()
            if self._a_vista():
                self.disegna()
            else:       # dietro un'altra scheda (23 nov 2026: all'avvio il disegno, coi conti dell'EV di tutte le partite, fermava la finestra 7 s)
                self._da_disegnare = True
            if self._di_nuovo:
                self.ricarica()
            self.fr.after(2500, lambda: self.scalda_decisioni(list(self.righe or [])))
        self.fr.after(150, aspetta)

    def scalda_decisioni(self, righe, da=0, a_volta=4):
        """Le decisioni e l'EV di ogni partita (decisioni._ricorda, ev_partita) calcolati prima che servano (15 nov 2026, il debug del replayer: il primo
        replay aperto nella sessione aspettava 1,5 s). Dal 23 nov 2026 su un filo suo (Autore: «l'app sembra lenta a caricarsi»: sul filo della finestra
        la fermava a pezzi), mai mentre il replayer anima; finito, la pagina nascosta si lascia preparare in anticipo (prepara_dietro della finestra), e poi
        parte il solito riga per riga del voto per fase."""
        import threading
        import time as _t
        import ev_partita as EV_
        if getattr(self, "_dec_filo", None) is not None and self._dec_filo.is_alive():
            return

        def lavoro():
            for x in righe[da:]:
                if getattr(self, "_chiusa", False):      # mai Tk da questo filo: la pagina alza il segno quando si chiude
                    return
                while (getattr(self, "_anim_in_corso", False) or getattr(self, "_replayer_a_vista", False)) and not getattr(self, "_chiusa", False):
                    _t.sleep(0.4)
                try:
                    EV_.partita(x)                  # i turni e l'EV della partita (EV VALUE, SPOT EV, i numeri in cima)
                    DEC.per_partita(x)
                    DEC.per_partita_magie(x)
                    EV_._eventi(x)                  # i meriti delle carte dei due lati (il lettore di EV, 18 nov 2026): la prima apertura di Cards non aspetta
                    EV_._eventi(EV_.specchio(x))
                    EV_._giocate_partita(x)         # e le giocate (EV AT CAST, 18 nov 2026): il modello della P su ogni lancio, una volta per partita
                except Exception:      # noqa: BLE001 - una partita senza dati si salta
                    pass
                _t.sleep(0.02)
            if getattr(self, "_da_disegnare", False):
                self.sporca = True          # adesso il disegno costa poco: la finestra lo fa quando e' ferma
            _t.sleep(0.5)
            if not getattr(self, "_chiusa", False):
                self.scalda_solito(list(reversed(righe)))       # parte il suo filo, senza toccare Tk
        self._dec_filo = threading.Thread(target=lavoro, daemon=True, name="scalda_decisioni")
        self._dec_filo.start()

    def scalda_solito(self, righe, da=0):
        """Le righe del voto per fase di ogni partita (solito_righe.calcola, ~0,17 s a partita), su un filo suo a priorita' di cortesia (23 nov 2026,
        Autore: «l'app sembra lenta a caricarsi»: fino a quel giorno girava sul filo della finestra, una partita ogni 60 ms, e dopo ogni aggiornamento
        del codice le rifaceva tutte: la finestra restava ferma 200-400 ms a ogni cambio di scheda per un paio di minuti). Mai mentre il replayer anima;
        la copia su disco ogni 20 partite. Le partite gia' nella copia non costano niente."""
        import threading
        import time as _t
        import solito_righe as SR
        if getattr(self, "_solito_filo", None) is not None and self._solito_filo.is_alive():
            return

        def lavoro():
            fatte = 0
            for x in righe[da:]:
                if getattr(self, "_chiusa", False):      # mai Tk da questo filo
                    break
                while (getattr(self, "_anim_in_corso", False) or getattr(self, "_replayer_a_vista", False)) and not getattr(self, "_chiusa", False):
                    _t.sleep(0.4)
                try:
                    if SR.gia_fatta(x):
                        continue
                    SR.calcola(x)
                    fatte += 1
                except Exception:      # noqa: BLE001 - una partita senza dati si salta
                    continue
                if fatte % 20 == 0:
                    SR.salva()
                _t.sleep(0.15)          # lascia il filo della finestra libero fra una partita e l'altra (con 0,03 la finestra si disegnava a pezzi)
            SR.salva()
        self._solito_filo = threading.Thread(target=lavoro, daemon=True, name="scalda_solito")
        self._solito_filo.start()

    def mostra_carica(self, secondi):
        """«Loading your games…» al centro della pagina mentre la prima lettura dei log e' in corso (13 nov 2026, Autore: «la scheda performance non carica i
        dati»: dopo un aggiornamento la prima lettura rifa' tutte le partite, fino a un minuto e mezzo, e la pagina restava vuota con una scritta piccola in alto)."""
        testo = "Loading your games…\nreading your Arena logs" + (f"  ·  {int(secondi)} s" if secondi >= 1 else "") \
                + ("\nthe first time after an update it reads every game again (up to a minute or two)" if secondi >= 5 else "")
        if self.l_carica is None or not self.l_carica.winfo_exists():
            self.l_carica = self.tk.Label(self.fr, text=testo, bg=C["cap"], fg=C["titolo"], font=self.F(11, True), padx=36, pady=24, justify="center",
                                          highlightthickness=1, highlightbackground=C["filo"])
            self.l_carica.place(relx=0.5, rely=0.45, anchor="center")
        else:
            self.l_carica.configure(text=testo)
        self.l_carica.lift()

    def togli_carica(self):
        if self.l_carica is not None:
            if self.l_carica.winfo_exists():
                self.l_carica.destroy()
            self.l_carica = None

    # ------------------------------------------------------------ la costruzione
    def costruisci(self):
        tk, F = self.tk, self.F
        testa = tk.Frame(self.fr, bg=C["fondo"]); testa.pack(fill="x")       # sul fondo della pagina, il titolo in Bahnschrift (redesign del 14 nov 2026)
        tk.Label(testa, text="LEAK FINDER", bg=C["fondo"], fg=C["titolo"], font=FN(17), padx=0).pack(side="left", padx=(12, 12), pady=8)
        tk.Label(testa, text="your mistakes and your games, from your Arena logs", bg=C["fondo"], fg=C["muto"], font=F(9)).pack(side="left", padx=(0, 18))
        self.sw_tipo = tk.Canvas(testa, width=SW_L, height=SW_H, bg=C["fondo"], highlightthickness=0, bd=0, cursor="hand2")
        self.sw_tipo.pack(side="left", pady=8)
        self.sw_tipo.bind("<Button-1>", lambda e: self.cambia_tipo(TIPI[1 - TIPI.index(self.tipo)]))
        self.disegna_switch()
        # il reset globale (12 nov 2026, Autore: «aggiungiamo anche un reset global che ci porta a tutte le partite di default»): filtri, situazioni, grafico e
        # vista in basso come all'apertura; Constructed o Limited resta
        self.b_reset = pulsante_solido(tk, F, testa, "Reset all", False, self.reset, alto=26, bg=C["fondo"], colori=ARANCIO)      # arancio come gli altri Reset (13 nov 2026)
        self.b_reset.configure(width=100); self.b_reset.pack(side="right", padx=(8, 16), pady=8)
        self.l_info = tk.Label(testa, text="Reading your logs…", bg=C["fondo"], fg=C["grigio"], font=F(8))
        self.l_info.pack(side="right", padx=(16, 4))
        corpo = tk.Frame(self.fr, bg=C["fondo"]); corpo.pack(fill="both", expand=True, padx=10, pady=10)
        corpo.columnconfigure(0, weight=0, minsize=300); corpo.columnconfigure(1, weight=1); corpo.rowconfigure(0, weight=1)
        # a sinistra: le variabili e le situazioni salvate, in una colonna che scorre
        sx = tk.Frame(corpo, bg=C["scheda"], highlightthickness=1, highlightbackground=RD["filo2"]); sx.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        tk.Frame(sx, bg=RD["luce"], height=1).pack(fill="x")        # il filo di luce in cima al pannello (redesign del 14 nov 2026)
        rs = tk.Frame(sx, bg=C["scheda"]); rs.pack(fill="x", padx=12, pady=(10, 4))
        # «Smart filters» (12 nov 2026, Autore: «i filtri a sinistra potremmo chiamarli smart filters»); il pulsante Add filters (le situazioni) non c'e' piu':
        # le situazioni stanno nel + della loro fase
        tk.Frame(rs, bg=C["accento"], width=3, height=14).pack(side="left", padx=(0, 6))
        tk.Label(rs, text="SMART FILTERS", bg=C["scheda"], fg=C["titolo"], font=F(9, True)).pack(side="left")
        # la colonna scorre: con la rotella sopra qualunque sua parte, e con la barra sottile a destra (fino al 12 nov la rotella andava solo sul fondo vuoto e
        # le ultime tendine e le situazioni salvate restavano tagliate in fondo: Autore, «la finestra degli smart filters e' tagliata sul fondo»)
        # la barra a destra non c'e' piu' (15 nov 2026, Autore: «togli la barra di scorrimento dalla destra di smart filters»): resta la rotella
        riga_sx = tk.Frame(sx, bg=C["scheda"]); riga_sx.pack(fill="both", expand=True)
        self.cv_sx = tk.Canvas(riga_sx, bg=C["scheda"], highlightthickness=0, bd=0, width=280); self.cv_sx.pack(side="left", fill="both", expand=True)
        self.col_sx = tk.Frame(self.cv_sx, bg=C["scheda"])
        self.cv_sx.create_window(0, 0, window=self.col_sx, anchor="nw")
        self.col_sx.bind("<Configure>", lambda e: self.cv_sx.configure(scrollregion=(0, 0, 0, self.col_sx.winfo_reqheight() + 16)))

        def rotella(e):
            w = str(e.widget)
            if w.startswith(str(self.cv_sx)) and self.col_sx.winfo_reqheight() > self.cv_sx.winfo_height():
                self.cv_sx.yview_scroll(-2 if e.delta > 0 else 2, "units")
        self.cv_sx.bind_all("<MouseWheel>", rotella, add="+")
        # una riga per filtro, il nome a sinistra e il campo a destra (12 nov 2026, Autore: «impaginiamo meglio, holdem manager tiene tutto non tagliato e
        # sulla stessa pagina»): 15 filtri in ~440 pixel invece di ~870, tutti a vista senza scorrere
        self.tendine = {}
        griglia = tk.Frame(self.col_sx, bg=C["scheda"]); griglia.pack(fill="x", padx=(12, 4))
        griglia.columnconfigure(0, minsize=104)
        # My deck non e' fra le tendine: il mazzo si sceglie con By deck, in fondo (12 nov 2026, Autore: «togli dalle tendine my deck e crea un pulsante in
        # fondo: by deck»)
        # in sezioni separate da una lineetta (stesso giorno, Autore: «opponent, opponent colors e their card spostale insieme dopo lands in hand in una
        # sezione loro separata da una lineetta / poi tutto cio' che ha a che fare con date e orario uguale in fondo / card in hand prima di lands in hand /
        # format e event in una loro sezione»)
        nomi_var = dict(DA.NOME)
        riga_g = 0
        self.testate = []
        for j_, sezione in enumerate(SEZIONI_FILTRI):
            # la testa della fase: la lineetta, il nome e il + dei suoi filtri in piu' (12 nov 2026, Autore: «aggiungere a ogni tendina un set di filtri
            # aggiuntivi per ogni step», «Sì, costruiscili»)
            t_ = tk.Canvas(griglia, bg=C["scheda"], highlightthickness=0, bd=0, width=262, height=24 if j_ == 0 else 34, cursor="hand2" if FASI[j_][1] else "")
            t_.grid(row=riga_g, column=0, columnspan=2, sticky="ew", pady=(0, 2))
            if FASI[j_][1]:     # la fase senza filtri in piu' non apre niente
                t_.bind("<Button-1>", lambda e, j=j_: self.apri_fase(j))
            t_.bind("<Configure>", lambda e, j=j_: self.disegna_testata(j))
            self.testate.append(t_)
            riga_g += 1
            for k in sezione:
                if k == "wr_rif":
                    self.riga_wr(griglia, riga_g)
                elif k == "deck":
                    self.b_deck = pulsante_solido(tk, F, griglia, "Choose your deck  ·  all decks vs all", False, self.apri_deck, alto=28, bg=C["scheda"])
                    self.b_deck.configure(width=262); self.b_deck.grid(row=riga_g, column=0, columnspan=2, sticky="ew", pady=(4, 2))
                else:
                    self.riga_filtro(griglia, riga_g, k, nomi_var[k])
                riga_g += 1
        # il pulsante della finestra Advanced filters (13 nov 2026), in fondo agli smart filters
        self.b_avanzati = pulsante_solido(tk, F, griglia, "Advanced filters", False, self.apri_avanzati, alto=28, bg=C["scheda"])
        self.b_avanzati.configure(width=262); self.b_avanzati.grid(row=riga_g, column=0, columnspan=2, sticky="ew", pady=(12, 2))
        riga_g += 1
        tk.Frame(self.col_sx, bg=C["filo"], height=1).pack(fill="x", padx=12, pady=(10, 8))
        # le situazioni salvate sono i tuoi filtri personali, nella cartella My filters (12 nov 2026, Autore: «le situazioni salvate diventano filtri
        # personali che vanno in una nuova chart dopo compare e li si incolonnano»); sotto, Clear all ben visibile («clear all lo mettiamo sotto save this
        # situation bello visibile come pulsante»)
        self.b_salva_sit = pulsante_solido(tk, F, self.col_sx, "Save as my filter", False, self.salva_situazione, alto=28, bg=C["scheda"],
                                             colori=VERDE_P)      # Save sempre verde (13 nov 2026)
        self.b_salva_sit.configure(width=262); self.b_salva_sit.pack(anchor="w", padx=12, pady=(4, 6))
        self.b_pulisci = pulsante_solido(tk, F, self.col_sx, "Clear all filters", False, self.pulisci, alto=28, bg=C["scheda"],
                                         colori=ARANCIO)      # arancio (13 nov 2026, Autore: «e clear all filter lo fai arancio»)
        self.b_pulisci.configure(width=262); self.b_pulisci.pack(anchor="w", padx=12, pady=(0, 12))
        # a destra: i numeri in alto, sotto le cartelle (12 nov 2026, Autore: «questi falli a modo di cartelle e poi tira via il sotto testo»): Chart, Spots,
        # Report, Matchups e Compare, una alla volta; il segno a destra di ogni linguetta la stacca in una finestra sua («ogni sezione di ogni cartella si puo'
        # staccare dal quadro e renderla una finestra a se stante»), chiusa torna qui
        dx = tk.Frame(corpo, bg=C["fondo"]); dx.grid(row=0, column=1, sticky="nsew")
        dx.columnconfigure(0, weight=1); dx.rowconfigure(2, weight=1)
        self.cv_num = tk.Canvas(dx, bg=C["fondo"], highlightthickness=0, height=108, bd=0)       # le tessere centrate fra la riga in alto e il fondo, con aria sotto (12 nov 2026, Autore: «le barre toccano la base della tabella, voglio le cose centrate»)
        self.cv_num.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        self.cv_num.bind("<Configure>", lambda e: self.disegna_numeri())
        self.cv_num.bind("<Button-1>", self.clic_numeri_rotella)
        self.cv_tab = tk.Canvas(dx, bg=C["fondo"], highlightthickness=0, bd=0, height=ALTO_TAB)
        self.cv_tab.grid(row=1, column=0, sticky="ew")
        self.cv_tab.bind("<Configure>", lambda e: self.disegna_cartelle())
        self.cv_tab.bind("<Button-1>", self.clic_cartella)
        self.cv_tab.bind("<Motion>", self.sopra_cartella)
        self.cv_tab.bind("<Leave>", lambda e: self.sopra_cartella(None))
        bordo = tk.Frame(dx, bg=C["filo"]); bordo.grid(row=2, column=0, sticky="nsew")      # il bordo del pannello sui fianchi e sotto: sopra lo fanno le cartelle
        self.pan = pan = tk.Frame(bordo, bg=C["scheda"]); pan.pack(fill="both", expand=True, padx=1, pady=(0, 1))
        self.ospiti = {k: self.fai_vista(k, pan) for k, _n in VISTE}
        o = self.ospiti
        self.cv_gr, self.cv_sp, self.cv_rp, self.cv_cf = (o[k]["tela"] for k in ("chart", "spots", "report", "compare"))
        self.cv_mt = self.cv_rp     # i Matchups sono la matrice di Breakdown
        self.b_metr = o["chart"]["ctl"]["metr"]
        self.t_asse, self.t_fin, self.t_dividi = (o["chart"]["ctl"][k] for k in ("asse", "fin", "dividi"))

        # la cartella che sta nella sua finestra: qui lo si dice, coi due pulsanti
        self.f_fuori = tk.Frame(pan, bg=C["scheda"])
        self.l_fuori = tk.Label(self.f_fuori, text="", bg=C["scheda"], fg=C["grigio"], font=F(10, True)); self.l_fuori.pack(pady=(70, 14))
        rb = tk.Frame(self.f_fuori, bg=C["scheda"]); rb.pack()
        b = pulsante_solido(tk, F, rb, "Show its window", False, lambda: self.stacca(self.vista), alto=28, bg=C["scheda"], colori=GRIGI)
        b.configure(width=150); b.pack(side="left", padx=4)
        b = pulsante_solido(tk, F, rb, "Bring it back here", False, lambda: self.riattacca(self.vista), alto=28, bg=C["scheda"])
        b.configure(width=170); b.pack(side="left", padx=4)
        self.mostra_vista()
        self.disegna_situazioni()

    def riga_wr(self, griglia, i):
        """Il win rate (13 nov 2026, Autore: «win rate deve poter settare una % di win rate sulla quale si posiziona la ricerca, puoi metterla dopo event»,
        «non mettere tendina sarà una casella dove si scrive il wr coi numeri», «accanto prima e dopo ci metti due flag per due simboli maggiore e minore, se sono
        deflaggati si cerca il wr esatto, se sono flaggati si cerca il wr uguale e maggiore o uguale e minore del valore inserito»): ≥ | casella | % | ≤. Tiene
        le partite che insieme fanno quel win rate: dopo gli altri filtri, dalle piu' recenti all'indietro finche' regge (DA.finestra_wr; «filtra le partite
        che partecipano a costruire quel dato di wr»). Invio, l'uscita dalla casella o un attimo di pausa lo mettono; la casella vuota lo toglie."""
        tk, F = self.tk, self.F
        lab = tk.Label(griglia, text="Win rate", bg=C["scheda"], fg=C["testo"], font=F(9), anchor="w"); lab.grid(row=i, column=0, sticky="w", pady=2)
        self.lab_filtri = getattr(self, "lab_filtri", {}); self.lab_filtri["wr_rif"] = lab
        fr = tk.Frame(griglia, bg=C["scheda"]); fr.grid(row=i, column=1, sticky="w", pady=2)
        self.wr_segni = {}
        for chiave, segno in (("ge", "≥"), ("le", "≤")):
            b = tk.Label(fr, text=segno, width=2, bg="#0b0e14", fg=C["grigio"], font=F(10, True), cursor="hand2", highlightthickness=1,
                         highlightbackground="#2a303b")
            b.bind("<Button-1>", lambda e, c_=chiave: self.cambia_segno_wr(c_))
            self.wr_segni[chiave] = b
        self.wr_ge, self.wr_le = False, False
        self.wr_var = tk.StringVar(value="")
        self.e_wr = tk.Entry(fr, textvariable=self.wr_var, width=6, justify="center", bg="#0b0e14", fg=C["titolo"], insertbackground=C["titolo"],
                             relief="flat", font=F(10, True), highlightthickness=1, highlightbackground="#2a303b", highlightcolor=C["accento"])
        # ≤ prima della casella e ≥ dopo (13 nov 2026, Autore: «affianco alla win rate inverti l'ordine dei bracket»): il significato resta, ≤ al massimo,
        # ≥ almeno
        self.wr_segni["le"].pack(side="left", ipady=1)
        self.e_wr.pack(side="left", padx=(6, 2), ipady=3)
        tk.Label(fr, text="%", bg=C["scheda"], fg=C["grigio"], font=F(9, True)).pack(side="left", padx=(0, 6))
        self.wr_segni["ge"].pack(side="left", ipady=1)
        self.e_wr.bind("<Return>", lambda e: self.metti_wr())
        self.e_wr.bind("<FocusOut>", lambda e: self.metti_wr())
        self.e_wr.bind("<KeyRelease>", lambda e: self.wr_poi())
        self._wr_dopo = None

    def wr_poi(self):
        """Mentre scrivi: il filtro si mette dopo 600 ms di pausa, non a ogni cifra."""
        if self._wr_dopo is not None:
            try:
                self.fr.after_cancel(self._wr_dopo)
            except Exception:      # noqa: BLE001
                pass
        self._wr_dopo = self.fr.after(600, self.metti_wr)

    def cambia_segno_wr(self, chiave):
        setattr(self, "wr_" + chiave, not getattr(self, "wr_" + chiave))
        self.metti_wr()

    def metti_wr(self):
        """Dalla casella e dai segni al filtro «wr_rif» = [valore, ≥, ≤] (una lista: si salva come i tuoi filtri); un testo che non e' un numero fra 0 e 100 lo
        toglie."""
        self._wr_dopo = None
        testo = (self.wr_var.get() or "").replace("%", "").replace(",", ".").strip()
        try:
            v = float(testo)
        except ValueError:
            v = None
        nuovo = None if v is None or not 0 <= v <= 100 else [round(v, 1), self.wr_ge, self.wr_le]
        if nuovo != self.filtri.get("wr_rif"):
            self.filtri["wr_rif"] = nuovo
            self.disegna()
        else:
            self.disegna_wr()

    def disegna_wr(self):
        """La casella e i segni come dice il filtro (anche dopo Clear all, Reset, una ricerca preimpostata o un tuo filtro): acceso, azzurri."""
        if not hasattr(self, "e_wr"):
            return
        f = self.filtri.get("wr_rif")
        if f:
            self.wr_ge, self.wr_le = bool(f[1]), bool(f[2])
            if self.focus_wr() is False:
                self.wr_var.set(f"{float(f[0]):g}")
        elif getattr(self, "_wr_ultimo", None) and self.focus_wr() is False:      # tolto da fuori (Clear all, Reset): casella e segni da capo
            self.wr_var.set("")
            self.wr_ge = self.wr_le = False
        self._wr_ultimo = f
        on = bool(f)
        self.e_wr.configure(bg="#0e2238" if on else "#0b0e14", highlightbackground=C["accento"] if on else "#2a303b")
        for chiave, b in self.wr_segni.items():
            acceso = getattr(self, "wr_" + chiave)
            b.configure(bg=C["accento"] if acceso else "#0b0e14", fg="#0b0e14" if acceso else C["grigio"],
                        highlightbackground=C["accento"] if acceso or on else "#2a303b")
        self.lab_filtri["wr_rif"].configure(fg=C["accento"] if on else C["testo"])

    def focus_wr(self):
        """La casella ha il fuoco (stai scrivendo: il testo non si tocca)?"""
        try:
            return self.e_wr.focus_get() is self.e_wr
        except Exception:      # noqa: BLE001
            return False

    def riga_filtro(self, griglia, i, k, nome):
        """Una riga degli smart filters: il nome a sinistra e la tendina a destra."""
        tk, F = self.tk, self.F
        corto = {"Opponent colors (contains)": "Opp. colors", "Lands in opening hand": "Lands in hand", "Game length (your turns)": "Game length",
                 "Card in opening hand": "Card in hand", "Opponent card seen": "Opponent card"}.get(nome, nome)
        lab = tk.Label(griglia, text=corto, bg=C["scheda"], fg=C["testo"], font=F(9), anchor="w"); lab.grid(row=i, column=0, sticky="w", pady=2)      # come nel mockup del 14 nov 2026
        self.lab_filtri = getattr(self, "lab_filtri", {}); self.lab_filtri[k] = lab
        t = Tendina(tk, griglia, "", F, larga=156, bg=C["scheda"])
        t.fr.winfo_children()[0].pack_forget()        # il nome sta a sinistra, sulla stessa riga
        t.campo.configure(height=24)
        t.fr.grid(row=i, column=1, sticky="w", pady=2)
        t.opzioni(["Any"], lambda v, k=k: self.metti_filtro(k, v)); t.set("Any")
        self.tendine[k] = t

    def fai_vista(self, k, padre):
        """Una vista dentro padre (il pannello o la sua finestra): la riga dei comandi e la tela. -> dict(fr, tela, ctl). Le scelte sono della pagina: due copie
        della stessa vista dicono le stesse cose (sincronizza)."""
        tk, F = self.tk, self.F
        fr = tk.Frame(padre, bg=C["scheda"])
        riga = tk.Frame(fr, bg=C["scheda"]); riga.pack(fill="x", padx=12, pady=(8, 0))
        ctl = {}
        sit_k = ["sit:" + s_ for s_, _n in DA.SIT]
        et_var = {**DA.NOME, **{k_: DA.nome_var(k_) for k_ in sit_k}}

        def asse_e_finestra():
            ctl["fin"] = Tendina(tk, riga, "Window", F, larga=140, bg=C["scheda"]); ctl["fin"].fr.pack(side="right", padx=(10, 0))
            ctl["fin"].opzioni([k_ for k_, _n in DA.FINESTRE], lambda v: self.cambia("finestra", v), etichette=dict(DA.FINESTRE)); ctl["fin"].set(self.finestra)
            ctl["asse"] = Tendina(tk, riga, "X axis", F, larga=100, bg=C["scheda"]); ctl["asse"].fr.pack(side="right", padx=(10, 0))
            ctl["asse"].opzioni(["games", "date"], lambda v: self.cambia("asse", v), etichette={"games": "Games", "date": "Date"}); ctl["asse"].set(self.asse)
        if k == "chart":
            ctl["metr"] = {}
            for m, n in DA.METRICHE:
                b = pulsante_solido(tk, F, riga, n, m == self.metrica, lambda m=m: self.cambia("metrica", m), alto=26, bg=C["scheda"], colori=GRIGI)
                b.configure(width=128 if m == "ev" else 104); b.pack(side="left", padx=(0, 6), anchor="s", pady=(0, 2))
                ctl["metr"][m] = b
            # di quali turni e fasi e' l'EV (18 nov 2026, le fasi del turno): si vede solo con la metrica «EV vs expected»
            import ev_partita as EV_
            ctl["evdi"] = Tendina(tk, riga, "EV of", F, larga=210, bg=C["scheda"])
            ctl["evdi"].opzioni([k_ for k_, _n in EV_.EV_DI], lambda v: self.cambia("ev_di", v), etichette=dict(EV_.EV_DI))
            ctl["evdi"].set(getattr(self, "ev_di", "all"))
            ctl["dividi"] = Tendina(tk, riga, "Split by", F, larga=180, bg=C["scheda"]); ctl["dividi"].fr.pack(side="right", padx=(10, 0))
            ctl["dividi"].opzioni(["None"] + [k_ for k_, _n, _f in DA.VARIABILI if k_ not in ("data",)] + ["vs"] + [k_ for k_, _n, _f in DA.EXTRA] + sit_k,
                                  lambda v: self.cambia("dividi", None if v == "None" else v), etichette={"None": "None", **et_var})
            ctl["dividi"].set(self.dividi or "None")
            asse_e_finestra()
        elif k == "spots":       # le ricerche preimpostate o gli spot automatici di prima (13 nov 2026)
            ctl["smodo"] = {}
            for m, n in SPOT_MODI:
                b = pulsante_solido(tk, F, riga, n, m == self.spot_modo, lambda m=m: self.cambia_spot(m), alto=26, bg=C["scheda"], colori=GRIGI)
                b.configure(width=130); b.pack(side="left", padx=(0, 6), anchor="s", pady=(0, 2))
                ctl["smodo"][m] = b
        elif k == "report":     # Matchups: nessuna scelta sua (le scelte stanno negli Smart filters), due sotto-schede (18 nov 2026, Autore: «una volta scelto il
            # deck mi mostra i dati che gia' mostra adesso ma come prima sottoscheda / come seconda sotto scheda fa una analisi limitata agli eventi che si fanno
            # per convertire gemme»)
            # come sotto-cartelle, col disegno delle cartelle (Autore, stesso giorno: «le sotto schede non per pulsanti ma proprio come sotto cartelle
            # anche come design»)
            cs_ = tk.Canvas(riga, height=ALTO_SUB, bg=C["scheda"], highlightthickness=0, bd=0, cursor="hand2")
            cs_.pack(side="left", fill="x", expand=True)
            cs_.bind("<Configure>", lambda e, cs_=cs_: self.disegna_sottocartelle(cs_, MU_MODI, self.mu_modo))
            cs_.bind("<Button-1>", lambda e, cs_=cs_: self.clic_sottocartella(cs_, e))
            ctl["musub"] = cs_
        elif k == "decisions":       # attacchi, blocchi, mulligan (13 nov 2026), e i filtri delle decisioni
            ctl["dmodo"] = {}
            for m, n in DEC_MODI:
                b = pulsante_solido(tk, F, riga, n, m == self.dec_modo, lambda m=m: self.cambia_dec(m), alto=26, bg=C["scheda"], colori=GRIGI)
                b.configure(width=110); b.pack(side="left", padx=(0, 6), anchor="s", pady=(0, 2))
                ctl["dmodo"][m] = b
            ctl["dfin"] = pulsante_solido(tk, F, riga, "Decision filters", False, self.apri_filtri_dec, alto=26, bg=C["scheda"], colori=GRIGI)
            ctl["dfin"].configure(width=200); ctl["dfin"].pack(side="right", anchor="s", pady=(0, 2))
        elif k == "cards":
            # 18 nov 2026 (Autore: «invece del pulsante rows anche qui sulla sinistra mettiamo la rotella con le spunte per le righe che vogliamo leggere»):
            # a sinistra la rotella disegnata, come quella dei numeri; poi le sotto-schede (Autore: «la scheda cards deve avere delle sotto schede: Una per
            # l'analisi specifica di una carta ... Altra scheda come adesso ma dedicata alle analisi delle carte dei mazzi selezionati o dai filtri»)
            ro_ = tk.Canvas(riga, width=30, height=28, bg=C["scheda"], highlightthickness=0, bd=0, cursor="hand2")
            ro_._img = DG.rotella(20, C["accento"], C["scheda"])
            ro_.create_image(15, 14, image=ro_._img)
            ro_.bind("<Button-1>", lambda e: self.apri_righe_carte())
            ro_.pack(side="left", anchor="s", padx=(0, 10), pady=(0, 2))
            ctl["rotella"] = ro_
            ctl["cmodo"] = {}
            for m, n in CARTE_MODI:
                b = pulsante_solido(tk, F, riga, n, m == self.carte_modo, lambda m=m: self.cambia_carte_modo(m), alto=26, bg=C["scheda"], colori=GRIGI)
                b.configure(width=120); b.pack(side="left", padx=(0, 6), anchor="s", pady=(0, 2))
                ctl["cmodo"][m] = b
            ctl["cerca_fr"] = tk.Frame(riga, bg=C["scheda"])
            tk.Label(ctl["cerca_fr"], text="CARD", bg=C["scheda"], fg=C["grigio"], font=F(7, True)).pack(side="left", padx=(8, 6))
            ctl["cerca"] = R_F.CartaCompleta(tk, F, ctl["cerca_fr"], self.carte_cercabili(), getattr(self, "analisi_di", None),
                                             lambda v: self.apri_analisi_carta(None if v in (None, R_F.QUALSIASI) else v), larga=280)
            ctl["cerca"].fr.pack(side="left")
        elif k == "compare":
            ctl["con"] = Tendina(tk, riga, "Compare A with (B)", F, larga=260, bg=C["scheda"]); ctl["con"].fr.pack(side="left")
            ctl["con"].opzioni(["rest"], lambda v: self.cambia("con", v), etichette={"rest": "Everything else"}); ctl["con"].set(self.con)
            asse_e_finestra()
        lista = None
        if k == "chart":       # sotto il grafico le partite della situazione, una per riga, con la mano e la board (12 nov 2026, «proprio come holdem manager»)
            # grafico e partite divisi da una linea da trascinare: allarga uno e stringe l'altro (12 nov 2026, Autore: «tra chart e elenco crea una linea di
            # separazione che possa aumentare la dimensione della lista sotto restringendo lo spazio sopra e viceversa»)
            corpo_ = tk.PanedWindow(fr, orient="vertical", bg="#252b36", bd=0, sashwidth=7, sashrelief="flat", sashpad=0, opaqueresize=True,
                                    sashcursor="sb_v_double_arrow")
            corpo_.pack(fill="both", expand=True, padx=8, pady=(4, 6))
            c = tk.Canvas(corpo_, bg=C["scheda"], highlightthickness=0, bd=0, height=120)
            corpo_.add(c, minsize=120, stretch="always")
            sotto = tk.Frame(corpo_, bg=C["scheda"])
            corpo_.add(sotto, minsize=110, stretch="always")
            lista = self.fai_tabella(sotto)
            lista.sotto, lista.diviso = sotto, corpo_

            def primo_posto(e, p_=corpo_):      # la prima volta il grafico prende il 60%
                if not getattr(p_, "_messo", False) and e.height > 300 and len(p_.panes()) > 1:
                    p_._messo = True
                    p_.after_idle(lambda: p_.sash_place(0, 0, int(e.height * 0.6)))
            corpo_.bind("<Configure>", primo_posto, add="+")
            if self.partite_fuori:      # la tabella sta nella sua finestra: qui il grafico prende tutto
                corpo_.forget(sotto)
        else:
            c = tk.Canvas(fr, bg=C["scheda"], highlightthickness=0, bd=0, height=120)
            if k == "report":       # Breakdown scorre: la barra a destra (18 nov 2026, Autore: «vedo dati tagliati e no scroll»)
                sb_ = tk.Scrollbar(fr, orient="vertical", command=c.yview)
                sb_.pack(side="right", fill="y", pady=(4, 6))
                c.configure(yscrollcommand=sb_.set)
            c.pack(fill="both", expand=True, padx=8, pady=(4, 6))
        c.bind("<Configure>", lambda e, k=k: self.tela(k) is e.widget and self.disegna_vista(k))
        if k == "chart":
            c.bind("<Button-1>", self.clic_grafico)
        if k in ("chart", "compare"):
            c.bind("<Motion>", self.punta)
            c.bind("<Leave>", lambda e: e.widget.delete("punta"))
        elif k == "spots":
            c.bind("<Button-1>", self.clic_spot)
            c.bind("<MouseWheel>", lambda e: self.spot_modo == "preset" and e.widget.yview_scroll(-2 if e.delta > 0 else 2, "units"))
        elif k == "report":
            c.bind("<Button-1>", self.clic_report)
            c.bind("<Double-Button-1>", lambda e: self.partite_numero("report"))     # R14: dal numero alle sue partite
            c.configure(yscrollincrement=24)       # la rotella scorre di una riga intera
            c.bind("<MouseWheel>", lambda e: (e.widget.yview_scroll(-1 if e.delta > 0 else 1, "units"), self.maschera_rp(e.widget)))
        elif k in ("decisions", "leaks"):
            c.bind("<Button-1>", self.clic_decisioni)
            c.bind("<MouseWheel>", lambda e: e.widget.yview_scroll(-2 if e.delta > 0 else 2, "units"))
        elif k == "cards":
            c.bind("<Button-1>", self.clic_carte)
            c.bind("<Button-3>", self.destro_carte)
            c.bind("<MouseWheel>", lambda e: (self.via_hover_carte(), e.widget.yview_scroll(-2 if e.delta > 0 else 2, "units")))
            c.bind("<Motion>", self.sopra_carte)
            c.bind("<Leave>", lambda e: self.via_hover_carte())
        elif k == "luck":
            c.bind("<Button-1>", self.clic_fortuna)
            c.bind("<MouseWheel>", lambda e: e.widget.yview_scroll(-2 if e.delta > 0 else 2, "units"))
        elif k == "mine":
            c.bind("<Button-1>", self.clic_miei)
            c.bind("<MouseWheel>", lambda e: e.widget.yview_scroll(-2 if e.delta > 0 else 2, "units"))
        return dict(fr=fr, tela=c, ctl=ctl, lista=lista)

    def ospite(self, k):
        """La copia della vista che si vede: quella della sua finestra se e' staccata, se no quella del pannello."""
        s_ = self.staccate.get(k)
        return s_["o"] if s_ else self.ospiti[k]

    def tela(self, k):
        return self.ospite(k)["tela"]

    def copie(self, k=None):
        """Tutte le copie vive delle viste (o della vista k): nel pannello e nelle finestre."""
        out = [o for k_, o in self.ospiti.items() if k in (None, k_)]
        return out + [s_["o"] for k_, s_ in self.staccate.items() if k in (None, k_)]

    def visibili(self):
        return {self.vista} | set(self.staccate)

    # le cartelle del giocatore e del mazzo (19 nov 2026, Autore: «sul all decks non ha senso aprire altro che le cartelle che parlano solo del giocatore, in
    # choose your deck invece vedro' solo le cartelle che parlano del mazzo»): nel Constructed, con All decks niente Matchups, Cards e Decisions (mischierebbero
    # mazzi diversi), con un mazzo niente Luck (lo shuffler e' tuo, non del mazzo); Chart, Habits, Spots, Compare e My filters seguono la scelta. Nel Limited
    # ogni draft e' un mazzo nuovo e il confronto e' gia' fra le partite dello stesso set: tutte le cartelle.
    SOLO_MAZZO = ("report", "cards", "decisions")
    SOLO_GIOCATORE = ("luck",)

    def cartelle_attive(self):
        if self.tipo != "Constructed":
            return list(VISTE)
        fuori = self.SOLO_GIOCATORE if self.filtri.get("mio") else self.SOLO_MAZZO
        return [(k, n) for k, n in VISTE if k not in fuori]

    def adegua_cartelle(self):
        """Dopo un cambio di mazzo o di tipo: scelto un mazzo si apre Matchups; tolto, se la cartella aperta non c'e' piu' si torna a Chart. Una cartella
        staccata che non c'e' piu' torna nel pannello."""
        chiave = (self.tipo, self.filtri.get("mio"))
        prima = getattr(self, "_mazzo_cartelle", None)
        self._mazzo_cartelle = chiave
        if prima is None or prima == chiave:
            return
        attive = {k for k, _n in self.cartelle_attive()}
        for k in [k for k in self.staccate if k not in attive]:
            self.riattacca(k)
        if self.tipo == "Constructed" and chiave[1] and not prima[1]:
            self.cambia_vista("report")
        elif self.vista not in attive:
            self.cambia_vista("chart")
        else:
            self.disegna_cartelle()

    def nome_mazzo_habits(self):
        return f" · {self.filtri['mio'].upper()}" if self.tipo == "Constructed" and self.filtri.get("mio") else (" · ALL DECKS" if self.tipo == "Constructed" else "")

    def disegna_vista(self, k):
        getattr(self, DISEGNI[k])()

    def sincronizza(self):
        """I comandi di ogni copia di ogni vista dicono le scelte di adesso."""
        for o in self.copie():
            ctl = o["ctl"]
            for m, b in ctl.get("metr", {}).items():
                b.metti(dict(DA.METRICHE)[m], m == self.metrica)
            for m, b in ctl.get("smodo", {}).items():
                b.metti(dict(SPOT_MODI)[m], m == self.spot_modo)
            for m, b in ctl.get("dmodo", {}).items():
                b.metti(dict(DEC_MODI)[m], m == self.dec_modo)
            if "dfin" in ctl:
                n_ = sum(1 for t_ in ("attacco", "blocco") for v in self.dec_f.get(t_, {}).values() if v)
                ctl["dfin"].metti(f"Decision filters · {n_} on" if n_ else "Decision filters", bool(n_))
            for k, v in (("asse", self.asse), ("fin", self.finestra), ("dividi", self.dividi or "None"),
                         ("con", self.con),
                         ("evdi", self.ev_di)):
                if k in ctl:
                    ctl[k].set(v)
            if "evdi" in ctl:       # la tendina «EV of» solo con la metrica EV, accanto ai pulsanti delle metriche
                if self.metrica == "ev" and not ctl["evdi"].fr.winfo_ismapped():
                    ctl["evdi"].fr.pack(side="left", padx=(6, 0))
                elif self.metrica != "ev" and ctl["evdi"].fr.winfo_manager():
                    ctl["evdi"].fr.pack_forget()
            if "musub" in ctl:
                self.disegna_sottocartelle(ctl["musub"], MU_MODI, self.mu_modo)
            for m, b in ctl.get("cmodo", {}).items():
                b.metti(dict(CARTE_MODI)[m], m == self.carte_modo)
            if "cerca_fr" in ctl:
                if self.carte_modo == "card" and not ctl["cerca_fr"].winfo_ismapped():
                    ctl["cerca_fr"].pack(side="left", anchor="s", pady=(0, 2))
                elif self.carte_modo != "card" and ctl["cerca_fr"].winfo_manager():
                    ctl["cerca_fr"].pack_forget()
                # le carte della casella: nate quando le partite non erano ancora lette (lista vuota: «single card non mi mostra la carta inserita
                # nel testo», 19 nov 2026); si rifanno quando cambiano le partite o il tipo
                k_c = (id(self.righe), self.tipo)
                if getattr(ctl["cerca"], "_chiave", None) != k_c and self.righe is not None:
                    ctl["cerca"].carte, ctl["cerca"]._chiave = self.carte_cercabili(), k_c
                if ctl["cerca"].scelta != getattr(self, "analisi_di", None):
                    ctl["cerca"].scelta = getattr(self, "analisi_di", None)
                    ctl["cerca"].metti_testo(ctl["cerca"].scelta)

    # ------------------------------------------------------------ le cartelle
    def disegna_cartelle(self):
        """Le linguette da cartella sopra il pannello: quella scelta si fonde col pannello, le altre piu' scure; a destra di ognuna il segno per staccarla."""
        c = self.cv_tab
        c.delete("all")
        F = self.F
        W, H = max(c.winfo_width(), 600), ALTO_TAB
        d = DG.Disegno(W, H)
        sopra = getattr(self, "_tab_sopra", None)
        self._box_tab, att, testi, segni = [], None, [], []
        x = 0
        for k, n in self.cartelle_attive():
            x0, x1 = x, x + LARGA_TAB
            fuori = k in self.staccate
            top = 3 if k == self.vista else 8
            if k == self.vista:
                att = (x0, x1)
            elif sopra and sopra[0] == k:       # redesign del 14 nov 2026: le cartelle chiuse sono solo testo, sotto il puntatore un velo appena chiaro
                d.poligono(_cartella(x0, x1, top, H + 1, sl=0, r=4), riempi="#121722")
            su_segno = sopra == (k, "segno")
            segni.append((x1 - 22, (top + H) / 2 - 2, C["titolo"] if su_segno else C["accento"] if fuori else C["muto"], fuori))
            testi.append(((x0 + x1 - 26) / 2, (top + H) / 2 - 1, n + ("  ↗" if fuori else ""), k == self.vista))
            self._box_tab.append((x0, top, x1, H, k, (x1 - 34, top, x1 - 6, H)))
            x = x1 + 3
        if att:
            x0, x1 = att
            d.linea([(0, H - 0.5), (x0 + 0.5, H - 0.5)], C["filo"], 1.0)       # il bordo alto del pannello, aperto sotto la cartella scelta
            d.linea([(x1 - 0.5, H - 0.5), (W, H - 0.5)], C["filo"], 1.0)
            pts = _cartella(x0, x1, 3, H + 1, sl=0, r=4)      # la cartella aperta unita al pannello, con la riga azzurra in cima (redesign del 14 nov 2026)
            d.poligono(pts, riempi=C["scheda"])
            d.linea(pts, C["filo"], 1.0)
            d.linea([(x0 + 3, 3.8), (x1 - 3, 3.8)], C["accento"], 2.0)
        else:
            d.linea([(0, H - 0.5), (W, H - 0.5)], C["filo"], 1.0)
        for sx_, sy_, col, fuori in segni:        # sopra le cartelle, anche su quella aperta
            _segno_stacca(d, sx_, sy_, col, fuori)
        self._img_tab = d.foto()
        c.create_image(0, 0, image=self._img_tab, anchor="nw")
        for tx, ty, t, on in testi:
            c.create_text(tx, ty, text=t, fill=C["titolo"] if on else C["grigio"], font=F(9, on))

    def _cartella_a(self, x, y):
        """(vista, «segno» o «tab») sotto il punto, o None."""
        for x0, y0, x1, y1, k, (a, b, c_, d_) in getattr(self, "_box_tab", []):
            if a <= x <= c_ and b <= y <= d_:
                return k, "segno"
            if x0 <= x <= x1 and y0 <= y <= y1:
                return k, "tab"
        return None

    def sopra_cartella(self, e):
        q = None if e is None else self._cartella_a(e.x, e.y)
        self.cv_tab.configure(cursor="hand2" if q else "")
        if q != getattr(self, "_tab_sopra", None):
            self._tab_sopra = q
            self.disegna_cartelle()

    def clic_cartella(self, e):
        q = self._cartella_a(e.x, e.y)
        if q is None:
            return
        k, dove = q
        if dove == "segno":
            if k in self.staccate:
                self.riattacca(k)
            else:
                self.stacca(k)
        elif k in self.staccate:      # una cartella staccata: qui il segnaposto, e la sua finestra davanti
            self.vista = k
            self.mostra_vista()
            self.staccate[k]["win"].lift()
        else:
            self.cambia_vista(k)

    # ------------------------------------------------------------ staccare una cartella in una finestra sua
    def stacca(self, k):
        """La vista k in una finestra sua (non sopra la grande: si porta anche su un altro schermo), coi suoi comandi e la situazione di adesso; chiusa, torna
        nel pannello. Nel pannello passa alla prima cartella rimasta."""
        if k in self.staccate:
            w = self.staccate[k]["win"]
            w.deiconify(); w.lift()
            return w
        tk, F = self.tk, self.F
        nome = dict(VISTE)[k]
        w = tk.Toplevel(self.fr)
        w.title(f"Leak Finder · {nome}")
        w.configure(bg=C["scheda"])
        pw, ph = max(self.pan.winfo_width(), 900), max(self.pan.winfo_height(), 520) + 60
        w.geometry(f"{pw}x{ph}+{self.pan.winfo_rootx() + 40}+{max(0, self.pan.winfo_rooty() - 40)}")
        testa = tk.Frame(w, bg=C["cap"]); testa.pack(fill="x")
        tk.Label(testa, text=f"LEAK FINDER · {nome.upper()}", bg=C["cap"], fg=C["titolo"], font=F(10, True)).pack(side="left", padx=(16, 10), pady=10)
        l_ = tk.Label(testa, text="", bg=C["cap"], fg=C["grigio"], font=F(8), anchor="w"); l_.pack(side="left", fill="x", expand=True)
        b = pulsante_solido(tk, F, testa, "Bring it back", False, lambda: self.riattacca(k), alto=26, bg=C["cap"], colori=GRIGI)
        b.configure(width=120); b.pack(side="right", padx=(8, 16), pady=8)
        o = self.fai_vista(k, w)
        o["fr"].pack(fill="both", expand=True)
        self.staccate[k] = dict(win=w, o=o, l=l_)
        w.protocol("WM_DELETE_WINDOW", lambda: self.riattacca(k, scegli=self.vista == k))
        if self.vista == k:
            libere = [k_ for k_, _n in VISTE if k_ not in self.staccate]
            if libere:
                self.vista = libere[0]
                if self.vista in ("report", "matchups"):
                    self.basso = self.vista
        self.sincronizza()
        self.mostra_vista()
        self.aggiorna_fuori()
        if self.righe is not None:
            self.disegna_vista(self.vista)
            w.after(60, lambda: w.winfo_exists() and self.disegna_vista(k))
        return w

    def riattacca(self, k, scegli=True):
        """La finestra si chiude e la vista torna nel pannello (scegli: e diventa la cartella aperta)."""
        s_ = self.staccate.pop(k, None)
        if s_ is not None:
            try:
                s_["win"].destroy()
            except Exception:      # noqa: BLE001 - gia' chiusa
                pass
        if scegli:
            self.vista = k
            if k in ("report", "matchups"):
                self.basso = k
        self.mostra_vista()
        if self.righe is not None and self.vista == k:
            self.disegna_vista(k)

    def aggiorna_fuori(self):
        """Nella testa di ogni finestra staccata: la situazione e quante partite."""
        if not self.staccate and not self.partite_fuori:
            return
        n = len(self.scelte()) if self.righe is not None else 0
        for s_ in list(self.staccate.values()) + ([self.partite_fuori] if self.partite_fuori else []):
            s_["l"].configure(text=f"{n} games · " + self.descrivi(self.filtri))

    def descrivi(self, filtri, tipo=None):
        on = [(k, v) for k, v in filtri.items() if v is not None]
        if not on:
            return f"all your {(tipo or self.tipo).lower()} games"
        return " · ".join(DA.etichetta(k, v) if k.startswith("sit:") else f"{DA.nome_var(k)}: {DA.etichetta(k, v)}" for k, v in on)

    # ------------------------------------------------------------ i comandi
    def disegna_switch(self):
        """Lo switch Constructed / Limited: la pillola scura, la meta' del formato scelto piena d'azzurro col testo bianco."""
        c = getattr(self, "sw_tipo", None)
        if c is None or not c.winfo_exists():
            return
        c.delete("all")
        d = DG.Disegno(SW_L, SW_H)
        d.rett(0.5, 0.5, SW_L - 0.5, SW_H - 0.5, riempi="#14181f", bordo=RD["filo2"], larghezza=1.2, raggio=(SW_H - 1) / 2)
        sel = TIPI.index(self.tipo)
        meta = SW_L / 2
        x0, x1 = (3, meta) if sel == 0 else (meta, SW_L - 3)
        d.rett(x0, 3, x1, SW_H - 3, riempi="#0f86cc", raggio=(SW_H - 7) / 2)
        c._img = d.foto()
        c.create_image(0, 0, image=c._img, anchor="nw")
        for i, t in enumerate(TIPI):
            c.create_text(meta * i + meta / 2 + (1 if i == 0 else -1), SW_H / 2, text=t.upper(), fill="#ffffff" if i == sel else C["muto"],
                          font=self.F(9, True))

    def cambia_tipo(self, t):
        self.tipo = t
        self.disegna_switch()
        self.filtri = {}
        for tnd in self.tendine.values():
            tnd.set("Any")
        self.disegna()
        f = getattr(self, "fin_av", None)      # Advanced filters aperti: le fasi del formato nuovo (la fase Draft solo nel Limited)
        if f is not None and f.winfo_exists():
            self.apri_avanzati()

    def metti_filtro(self, k, v):
        self.filtri[k] = None if v == "Any" else v
        if k == "formato" and self.filtri.get("evento") and self.filtri["formato"]:     # un evento di un altro formato non resta acceso
            if self.filtri["evento"] not in EVENTI_ARENA.get(self.filtri["formato"], ()) and not any(
                    DA.evento_breve(x.get("evento")) == self.filtri["evento"] and self.filtri["formato"] in DA.valori_di("formato", x) for x in self.righe or []):
                self.filtri["evento"] = None
        self.disegna()

    def pulisci(self):
        self.filtri = {}
        self._righe_ui = {}
        self.disegna()

    ev_di = "all"           # di quali turni e fasi e' l'EV del grafico (18 nov 2026); la scelta di partenza anche prima di reset
    bd_ord = "n"            # e come sono ordinate
    PARTENZA = dict(ev_di="all", metrica="wr", asse="games", finestra="20", dividi=None, per="suo", per_col=None, ordina="n", basso="report", solo_meta=False, vista="chart", con="rest", vs_modo="all", dec_modo="attacco",
                    linea_dec=None)

    deboli = frozenset()    # le righe di Cards lette dalla carta piu' debole (19 nov 2026)

    def reset(self):
        """Tutte le partite, come all'apertura: niente filtri ne' situazioni, il grafico e la cartella di partenza (le finestre staccate restano)."""
        self.filtri = {}
        self.deboli = frozenset()
        for k, v in self.PARTENZA.items():
            setattr(self, k, v)
        self.dec_f, self.righe_dec, self._righe_ui = {"attacco": {}, "blocco": {}}, {"attacco": [], "blocco": []}, {}
        self.sincronizza()
        self.mostra_vista()
        self.cv_sx.yview_moveto(0)
        self.disegna()

    def cambia(self, cosa, v):
        setattr(self, cosa, v)
        self.sincronizza()
        if cosa in ("metrica", "asse", "finestra", "dividi", "ev_di"):
            self.disegna_grafico()
            if cosa in ("asse", "finestra") and "compare" in self.visibili():
                self.disegna_confronto()
        elif cosa == "con":
            self.disegna_confronto()
        else:
            self.disegna_report()

    def cambia_vista(self, k):
        if k == "matchups":       # i Matchups di prima sono Breakdown (18 nov 2026)
            k = "report"
        self.vista = k
        if k in ("report", "matchups"):
            self.basso = k
        self.mostra_vista()
        if self.righe is not None:
            self.disegna_vista(k)

    def cambia_basso(self, k):      # il nome di prima (le prove, il reset): Report o Matchups
        self.cambia_vista(k)

    def mostra_vista(self):
        """Nel pannello la cartella scelta; se sta nella sua finestra, il segnaposto coi due pulsanti."""
        for o in self.ospiti.values():
            o["fr"].pack_forget()
        self.f_fuori.pack_forget()
        if self.vista in self.staccate:
            self.l_fuori.configure(text=f"{dict(VISTE)[self.vista]} is in its own window")
            self.f_fuori.pack(fill="both", expand=True)
        else:
            self.ospiti[self.vista]["fr"].pack(fill="both", expand=True)
        self.disegna_cartelle()



    def scelte(self):
        """Le partite del tipo e della situazione."""
        return DA.filtra(self.righe or [], self.filtri, self.tipo)

    # ------------------------------------------------------------ il disegno
    def disegna(self):
        if self.righe is None:
            return
        self.sporca = False
        self._da_disegnare = False
        self.adegua_cartelle()
        tutte = [x for x in self.righe if x["tipo"] == self.tipo]
        if tutte:
            self.l_info.configure(text=f"{len(tutte):,} {self.tipo.lower()} games · {tutte[0]['quando']:%d %b} – {tutte[-1]['quando']:%d %b}")
        else:
            self.l_info.configure(text=f"No {self.tipo.lower()} games in your logs yet")
        tutte_t = [x for x in self.righe if x["tipo"] == self.tipo]
        for k, t in self.tendine.items():
            # sempre le stesse voci, qualunque filtro ci sia (12 nov 2026, Autore: «la tendina mulligans vedo che e' variabile, no deve sempre in ogni caso
            # avere any, 0, 1, 2+»; 13 nov 2026: «perche' oltre certe impostazioni non posso filtrare per lands? Le tendine devono avere valori fissi sempre»):
            # le voci fisse, se no tutte quelle della variabile nell'ordine suo, se no quelle di tutte le partite del tipo. Fino a quel giorno le altre tendine
            # avevano solo i valori rimasti sotto gli altri filtri, e con qualche filtro acceso Lands in hand perdeva le voci
            if k in VALORI_FISSI:
                vv = [(v, 0) for v in VALORI_FISSI[k]]
            elif k == "formato":        # tutti i formati di Arena, poi quelli che hai e non sono nella lista
                vv = [(v, 0) for v in dict.fromkeys(list(FORMATI_ARENA.get(self.tipo, ())) + [v for v, _n in DA.valori(tutte_t, k)])]
            elif k == "evento":         # le code del formato scelto (di tutti, senza formato) e gli eventi che hai giocato li'
                fmt_ = self.filtri.get("formato")
                note = [e_ for f_, ee in EVENTI_ARENA.items() if (fmt_ is None and f_ in FORMATI_ARENA.get(self.tipo, ())) or f_ == fmt_ for e_ in ee]
                if self.tipo == "Limited":      # tutti gli eventi limited del gioco, dal calendario (DA.eventi_limited_gioco), anche quelli mai giocati
                    note = [v_ for v_, _d in DA.eventi_limited_gioco()]
                giocati = [v for v, _n in DA.valori([x for x in tutte_t if fmt_ is None or DA.valori_di("formato", x) == [fmt_]
                                                     or fmt_ in DA.valori_di("formato", x)], k)]
                vv = [(v, 0) for v in dict.fromkeys(note + giocati)]
            elif k in DA.ORDINE_VALORI:
                vv = [(v, 0) for v in DA.ORDINE_VALORI[k]]
            else:
                vv = DA.valori(tutte_t, k)
            sc = self.filtri.get(k)
            voci = ["Any"] + [v for v, _n in vv]
            if sc is not None and sc not in voci:
                voci.append(sc)
            # solo le voci, senza i conti (12 nov 2026, Autore: «nei menu a tendina non mettere anche i numeri solo le voci, i numeri li vogliamo come risultato
            # sui dati»): i valori restano quelli che hanno partite sotto gli altri filtri
            t.opzioni(voci, lambda v, k=k: self.metti_filtro(k, v), etichette={"Any": "Any", **{v: (nome_evento(v, "standard" if v in EVENTI_ARENA["Standard"] else None) if k == "evento" else DA.etichetta(k, v))
                                                                                       for v, _n in vv}})
            t.set(sc if sc is not None else "Any")
            self.evidenzia(k, sc is not None)
        self.disegna_wr()
        for j_ in range(len(FASI)):
            self.disegna_testata(j_)
        self.disegna_finestra_fase()
        self.disegna_avanzati()
        self.disegna_coppie()           # la finestra delle coppie di Cards, se e' aperta, segue i filtri
        self.aggiorna_bottone_avanzati()
        self.aggiorna_bottone_deck()
        self.disegna_finestra_deck()
        self.disegna_numeri()
        for k, _n in VISTE:         # solo le cartelle che si vedono: le altre si disegnano quando si aprono
            if k in self.visibili():
                self.disegna_vista(k)
        if self.partite_fuori:
            self.disegna_partite(self.partite_fuori["lista"])
        self.aggiorna_fuori()

    def evidenzia(self, k, on):
        """Una tendina con un valore scelto: il campo azzurro scuro col bordo azzurro e il nome in azzurro (12 nov 2026, Autore: «le tendine dove ho dati
        inseriti le evidenzi in azzurro»); il bordo resta azzurro anche quando il puntatore se ne va."""
        t = self.tendine[k]
        bordo = C["accento"] if on else "#2a303b"
        t.campo.configure(bg="#0e2238" if on else "#0b0e14", highlightbackground=bordo)
        t.campo.bind("<Leave>", lambda e, b=bordo: t.campo.configure(highlightbackground=b))
        lab = getattr(self, "lab_filtri", {}).get(k)
        if lab is not None:
            lab.configure(fg=C["accento"] if on else C["testo"])

    def disegna_numeri(self):
        c = self.cv_num
        c.delete("all")
        if self.righe is None:
            return
        F = self.F
        r = self.scelte()
        base_ = self.base_confronto()
        tot = DA.conti(base_)
        k = DA.conti(r)
        W = max(c.winfo_width(), 600)
        n_f = sum(1 for k_, v in self.filtri.items() if v is not None and k_ != "mio")
        n_t = sum(1 for v in self.filtri.values() if v is not None)
        dy = 0
        c.create_text(16, 14, text=(f"THIS SITUATION · {k['n']} GAMES" if n_f else f"ALL GAMES WITH {str(self.filtri['mio']).upper()} · {k['n']}" if n_t
                                    else f"ALL {self.tipo.upper()} GAMES · {k['n']}"), anchor="w", fill=C["azzurro"], font=F(8, True))
        xd = W - 46        # a destra la rotellina dei numeri
        if n_f:
            i_ = c.create_text(xd, 14, text=f"vs {self.nome_base()} ({tot['n']}): {tot['wr'] if tot['wr'] is not None else '-'}%", anchor="e", fill=C["grigio"], font=F(7))
            xd = (c.bbox(i_) or (xd, 0, xd, 0))[0] - 14
        if k["n"] and k["n"] < 30:      # in alto, accanto: in fondo usciva dalla tela
            c.create_text(xd, 14, text="under 30 games: a hint, not a fact", anchor="e", fill=C["arancio"], font=F(7, True))
        # i numeri scelti con la rotellina (13 nov 2026, Autore: «in alto a dx creiamo una rotellina di impostazioni con i 6 dati che vogliamo avere su
        # questa tabella»): numeri_partite.CATALOGO, la scelta in dati_analizzatore.numeri_scelti
        val = NP.valori(r, base_, self.filtri, atteso=[x for x in self.righe if x["tipo"] == self.tipo])
        toni = {"su": C["verde"], "giu": C["rosso"], "neutro": C["testo"], "vuoto": C["muto"]}      # il positivo verde (19 nov 2026)
        tess = [(NP.NOMI[k_].upper(), val[k_][0], toni[val[k_][1]], val[k_][2]) for k_ in DA.numeri_scelti() if k_ in val]
        # la rotellina, in alto a destra
        i_r = c.create_image(W - 12, 14, image=DG.rotella(18, C["accento"], C["scheda"]), anchor="e")      # disegnata, nitida (disegni.rotella)
        bb_r = c.bbox(i_r)
        c._box_rotella = (bb_r[0] - 6, bb_r[1] - 4, bb_r[2] + 6, bb_r[3] + 4)
        if not tess:
            c.create_text(16, 60, text="No numbers picked: click ⚙ and tick the ones you want here.", anchor="w", fill=C["grigio"], font=F(9))
            return
        # tutti i numeri del catalogo si possono tenere (13 nov 2026, Autore: «permetti fino a tutti i valori sulla barra ma ben organizzati»): fino a 8 per
        # riga; oltre, due righe pari (9 = 5 e 4 ... 16 = 8 e 8), e la barra si alza
        per_riga = len(tess) if len(tess) <= 8 else -(-len(tess) // 2)
        righe_n = -(-len(tess) // per_riga)
        alto = 32 + righe_n * 76 + 2
        if int(c.cget("height")) != alto:
            c.configure(height=alto)
        cw = (W - 32) / per_riga
        # il pannello del redesign (14 nov 2026): la sfumatura appena percettibile, il filo di luce in cima; le tessere in una fascia sola divisa da fili
        c._img_pannello = DG.foto_pannello(W, alto, RD["p1"], RD["p0"], RD["filo2"], luce=RD["luce"], raggio=6, fondo=C["fondo"])
        c.tag_lower(c.create_image(0, 0, image=c._img_pannello, anchor="nw"))
        for i, (a, v, col, s_) in enumerate(tess):
            x = 16 + (i % per_riga) * cw
            dy = (i // per_riga) * 76
            # piu' aria fra nome, numero e riga sotto (12 nov 2026, Autore: «i testi qui sono tutti incollati, gestisci meglio le spaziature»)
            if i % per_riga:
                c.create_line(x - 2, 34 + dy, x - 2, 96 + dy, fill=RD["filo2"], width=1)
            # il nome dice cosa misura (win rate, % delle partite, media: 13 nov 2026), quindi e' lungo: se non sta nella sua tessera si stringe
            # i tre livelli (19 nov 2026, Autore: «strutturiamo i livelli di importanza visiva: i titoletti delle varie voci devono essere piu' visibili
            # e attirare l'attenzione sul dato»): il titolo bianco con la barretta azzurra, la parte che dice l'unita' («· % of games») piu' chiara accanto
            nome_a, _sep, unita_a = a.partition(" · ")
            c.create_rectangle(x + 4, 37 + dy, x + 6, 49 + dy, fill=C["accento"], outline="")
            i_n = c.create_text(x + 12, 36 + dy, text=nome_a, anchor="nw", fill=C["titolo"], font=F(8, True), tags="nome_num")
            i_u = c.create_text((c.bbox(i_n) or (0, 0, x + 12, 0))[2] + 4, 37 + dy, text=("· " + unita_a.lower()) if unita_a else "", anchor="nw",
                                fill=C["muto"], font=F(7), tags="nome_num")
            for fn, fu in ((F(7, True), F(7)), (F(7, True), F(6)), (F(6, True), F(6))):
                bb_u = c.bbox(i_u) if unita_a else c.bbox(i_n)
                if bb_u and bb_u[2] - x <= cw - 8:
                    break
                c.itemconfigure(i_n, font=fn)
                c.itemconfigure(i_u, font=fu)
                c.coords(i_u, (c.bbox(i_n) or (0, 0, x + 12, 0))[2] + 4, 37 + dy)
            if unita_a and (c.bbox(i_u) or (0, 0, 0, 0))[2] - x > cw - 8:     # non ci sta neanche cosi': l'unita' va sotto il titolo
                c.coords(i_u, x + 12, 50 + dy)
            # il numero in Bahnschrift, l'unita' (%) piu' piccola accanto (redesign del 14 nov 2026)
            unita = "%" if isinstance(v, str) and v.endswith("%") and len(v) > 1 else ""
            i_v = c.create_text(x + 12, 66 + dy, text=v[:-1] if unita else v, anchor="w", fill=col, font=FN(22))
            if unita:
                c.create_text((c.bbox(i_v) or (0, 0, x + 40, 0))[2] - 2, 70 + dy, text=unita, anchor="w", fill=col, font=FN(12, False))
            c.create_text(x + 12, 89 + dy, text=s_, anchor="w", fill=C["grigio"], font=F(7), width=cw - 20)

    def clic_numeri_rotella(self, e):
        b = getattr(self.cv_num, "_box_rotella", None)
        if b and b[0] <= e.x <= b[2] and b[1] <= e.y <= b[3]:
            return self.apri_numeri()
        return None

    def apri_numeri(self):
        """La finestrella della rotellina: una spunta per numero del catalogo, sei al massimo; si applica subito e resta."""
        tk = self.tk
        f = getattr(self, "fin_numeri", None)
        if f is None or not f.winfo_exists():
            f = self.fin_numeri = tk.Toplevel(self.fr)
            f.title("Leak Finder · Numbers")
            f.configure(bg=C["scheda"])
            f.resizable(False, False)
            f.bind("<Escape>", lambda e: f.destroy())
            c = self.cv_numeri = tk.Canvas(f, bg=C["scheda"], highlightthickness=0, bd=0, width=620, height=60 + 28 * len(NP.CATALOGO) + 30)
            c.pack(padx=8, pady=8)
            c.bind("<Button-1>", self.clic_numeri)
            try:
                f.geometry(f"+{self.fr.winfo_pointerx() - 600}+{self.fr.winfo_pointery() + 16}")
            except Exception:      # noqa: BLE001
                pass
        self.disegna_scelta_numeri()
        f.lift()
        return f

    def disegna_scelta_numeri(self, avviso=""):
        c = getattr(self, "cv_numeri", None)
        if c is None or not c.winfo_exists():
            return
        F = self.F
        c.delete("all")
        c._box = []
        scelti = DA.numeri_scelti()
        c.create_text(12, 16, text=f"THE NUMBERS ON TOP · {len(scelti)} of {len(NP.CATALOGO)} · tick the ones you want to see (8 a row, then two rows)",
                      anchor="w", fill=C["azzurro"], font=F(8, True))
        y = 40
        for k, nome, cosa in NP.CATALOGO:
            on = k in scelti
            c.create_image(14, y + 10, image=DG.spunta(14, on, C["azzurro"], C["fondo"], C["grigio"], C["fondo"]), anchor="w")
            i_ = c.create_text(38, y + 10, text=nome, anchor="w", fill=C["titolo"] if on else C["grigio"], font=F(9, True))
            bb = c.bbox(i_)
            c.create_text(max(bb[2] + 10, 190), y + 10, text=cosa, anchor="w", fill=C["muto"], font=F(7))
            c._box.append((6, y, 612, y + 22, k))
            y += 28
        if avviso:
            c.create_text(12, y + 12, text=avviso, anchor="w", fill=C["arancio"], font=F(8, True))

    def clic_numeri(self, e):
        b = next((b for b in getattr(self.cv_numeri, "_box", []) if b[0] <= e.x <= b[2] and b[1] <= e.y <= b[3]), None)
        if b is None:
            return None
        scelti = DA.numeri_scelti()
        k = b[4]
        if k in scelti:
            scelti.remove(k)
        elif len(scelti) >= NP.MASSIMO:
            self.disegna_scelta_numeri(f"{NP.MASSIMO} at most: untick one first")
            return None
        else:
            scelti.append(k)
        DA.salva_numeri(scelti)
        self.disegna_scelta_numeri()
        self.disegna_numeri()
        return k

    def traccia(self, c, lin, box, metrica, asse, colori, titolo, vuoto="No games in this situation"):
        """Il grafico a linee su una tela qualsiasi (la cartella Chart, il confronto): assi, griglia, le linee in un'immagine nitida, il nome in fondo a ogni
        linea. Tiene sulla tela quel che serve al puntatore (_linee, _scala, _metrica, _asse, _colori)."""
        F = self.F
        W, H = max(c.winfo_width(), 400), max(c.winfo_height(), 160)
        x0, y0, x1, y1 = box
        c._linee, c._metrica, c._asse, c._colori, c._scala = lin, metrica, asse, colori, None
        if not lin:
            c.create_text((x0 + x1) / 2, (y0 + y1) / 2, text=vuoto, fill=C["grigio"], font=F(9))
            return None
        xs = [x for _n, p in lin for x, _y in p]
        ys = [y for _n, p in lin for _x, y in p]
        if metrica in ("wr", "mull"):
            ya, yb = 0.0, 100.0
            if metrica == "wr":
                ya, yb = max(0.0, min(ys) // 10 * 10 - 10), min(100.0, (max(ys) // 10 + 1) * 10 + 10)
        elif metrica == "ev":       # sopra e sotto lo zero, lo zero e' l'atteso
            m_ = max(abs(min(ys)), abs(max(ys)), 1.0) * 1.15
            ya, yb = -m_, m_
        else:
            ya, yb = 0.0, max(ys) * 1.15 or 1.0
        xa, xb = min(xs), max(xs) if max(xs) > min(xs) else min(xs) + 1
        c._scala = (x0, y0, x1, y1, xa, xb, ya, yb)
        sx = lambda x: x0 + (x - xa) / (xb - xa) * (x1 - x0)
        sy = lambda y: y1 - (y - ya) / (yb - ya) * (y1 - y0)
        passo = 10 if metrica in ("wr", "mull") else max(1, round((yb - ya) / 5))
        if metrica == "ev":         # le righe partono dallo zero, in su e in giu'
            passo = max(1, round(yb / 3))
            v = -passo * int(yb // passo)
        else:
            v = ya
        while v <= yb + 1e-9:
            yy = sy(v)
            forte = (metrica == "wr" and abs(v - 50) < 1e-9) or (metrica == "ev" and abs(v) < 1e-9)
            c.create_line(x0, yy, x1, yy, fill="#3a4456" if metrica == "ev" and forte else "#2c3340" if forte else "#171c25")
            c.create_text(x0 - 8, yy, text=(f"{v:+.0f}" if metrica == "ev" and v else f"{v:.0f}") + ('%' if metrica in ('wr', 'mull') else ''), anchor="e",
                          fill=C["muto"], font=F(7))
            v += passo
        etx = (lambda x: f"game {int(x)}") if asse == "games" else (lambda x: datetime.date.fromordinal(int(x)).strftime("%d %b"))
        c.create_text(x0, y1 + 12, text=etx(xa), anchor="w", fill=C["muto"], font=F(7))
        c.create_text(x1, y1 + 12, text=etx(xb), anchor="e", fill=C["muto"], font=F(7))
        tratti, etichette, aree = [], [], []
        for i, (n, p) in enumerate(lin):
            col = colori[i % len(colori)]
            if len(lin) == 1:       # la linea sola e' azzurra, con l'area sotto appena velata (redesign del 14 nov 2026)
                col = C["accento"]
            pts = [(sx(x), sy(y)) for x, y in p]
            if len(pts) == 1:
                pts = [pts[0], (pts[0][0] + 1, pts[0][1])]
            if len(lin) == 1 and len(pts) > 1:
                fondo_ = sy(0) if metrica == "ev" else y1       # l'EV si vela fino allo zero, non fino al fondo
                aree.append((pts + [(pts[-1][0], fondo_), (pts[0][0], fondo_)], (47, 155, 255, 22), None, 1.0))
            # sottili (12 nov 2026, Autore: «le linee dei grafici le voglio piu' sottili»; erano 2,4 / 2,0 / 1,6)
            spess = 1.4 if n == "All" and len(lin) == 1 else 1.2 if n != "All" else 1.0
            # una linea divisa si spezza dove quel valore non c'e' per un tratto lungo (un mazzo che per 30 partite non giochi): niente ponti piatti che
            # attraversano il grafico (12 nov 2026, «split by my decks ... non si capisce mai nulla»)
            salto = max(12, (xb - xa) * 0.04) if n != "All" and asse == "games" else float("inf")
            pezzo = [pts[0]]
            for (xp, _yp), q in zip(p, p[1:]):
                if q[0] - xp > salto:
                    tratti.append((pezzo if len(pezzo) > 1 else [pezzo[0], (pezzo[0][0] + 1, pezzo[0][1])], col, spess, None))
                    pezzo = []
                pezzo.append((sx(q[0]), sy(q[1])))
            tratti.append((pezzo if len(pezzo) > 1 else [pezzo[0], (pezzo[0][0] + 1, pezzo[0][1])], col, spess, None))
            etichette.append([pts[-1][1], pts[-1][1], n, p[-1][1], col])
        # i nomi in fondo alle linee non si sovrappongono (12 nov 2026, Autore: «split by my decks: i nomi dei decks si sormontano e non si capisce mai
        # nulla»): ordinati per altezza e distanziati di 14 pixel, dentro il grafico; un filo collega il nome spostato alla fine della sua linea
        etichette.sort(key=lambda e_: e_[0])
        for j in range(1, len(etichette)):
            etichette[j][1] = max(etichette[j][1], etichette[j - 1][1] + 14)
        troppo = etichette[-1][1] - (y1 + 4) if etichette else 0
        if troppo > 0:
            for e_ in etichette:
                e_[1] -= troppo
            for j in range(len(etichette) - 2, -1, -1):
                etichette[j][1] = min(etichette[j][1], etichette[j + 1][1] - 14)
        corto = lambda t_, n_: t_ if len(t_) <= n_ else t_[:n_ - 1] + "…"
        for y_vero, y_et, n, v_, col in etichette:
            if abs(y_et - y_vero) > 2:
                tratti.append(([(x1 + 1, y_vero), (x1 + 5, y_et)], col, 0.8, None))
            c.create_text(x1 + 8, y_et, text=f"{corto(str(n).strip(), 24)}  " + (f"{v_:+.0f}" if metrica == "ev" else f"{v_:.0f}")
                          + ('%' if metrica in ('wr', 'mull') else ''), anchor="w", fill=col,
                          font=F(7, True))
        c._img = DG.tratti(W, H, linee=tratti, poligoni=aree)
        c.create_image(0, 0, image=c._img, anchor="nw")
        c.create_text((x0 + x1) / 2, y0 - 12, text=titolo, anchor="n", fill=C["grigio"], font=F(7))
        return sx, sy

    def base_confronto(self):
        """Le partite contro cui si confronta la situazione (18 nov 2026, Autore: «quando seleziono un mazzo, il nuovo totale dei game deve partire dalla conta
        delle partite totali con il mazzo selezionato ... vs filter flag deve darmi le partite con quel filtro vs le partite totali del mazzo selezionato»):
        tutte le partite del tipo, o con un mazzo scelto in By deck solo quelle del mazzo. L'atteso dell'EV resta su tutte le partite del tipo."""
        tutte = [x for x in (self.righe or []) if x["tipo"] == self.tipo]
        mio = self.filtri.get("mio")
        return [x for x in tutte if DA.passa(x, {"mio": mio})] if mio is not None else tutte

    def nome_base(self):
        mio = self.filtri.get("mio")
        return f"all games with {mio}" if mio is not None else f"all your {self.tipo.lower()} games"

    def disegna_grafico(self):
        c = self.tela("chart")
        c.delete("all")
        c._img, c._linee, c._scala = None, [], None
        if self.righe is None:
            return
        W, H = max(c.winfo_width(), 400), max(c.winfo_height(), 160)
        r = self.scelte()
        extra = []
        # vs filter (13 nov 2026, Autore: «sotto mettici il flag per "vs filter" che confronta il filtrato vs la main line con una nuova linea colorata di
        # azzurro»): la linea principale diventa tutte le partite del tipo, e le partite filtrate sono la linea azzurra, sullo stesso asse
        n_f = sum(1 for k_, v in self.filtri.items() if v is not None and k_ != "mio")
        vs = self.mostra_vs_filtro and n_f
        base_g = self.base_confronto() if vs else r
        if vs:
            extra.append(("This filter", {x.get("partita") for x in r}))
        if self.linea_dec:          # la riga di Decisions scelta: le sue partite come linea in piu' (ricalcolata coi filtri di adesso)
            riga_ = next((c_ for c_ in DEC.tabella(r, self.linea_dec[0], self.dec_f.get(self.linea_dec[0])) if c_["nome"] == self.linea_dec[1]), None)
            if riga_ and riga_["ids"]:
                extra.append((("Attack: " if self.linea_dec[0] == "attacco" else "Block: ") + self.linea_dec[1], riga_["ids"]))
        tutte_t = [x for x in self.righe if x["tipo"] == self.tipo]     # l'EV atteso viene sempre da tutte le partite del tipo
        lin = [(n, p) for n, p in DA.linee(base_g, self.metrica, self.asse, self.finestra, None if vs else self.dividi, extra=extra, base=tutte_t,
                                           ev_di=self.ev_di) if p]
        if vs and lin:
            lin[0] = (("All games" if self.filtri.get("mio") is None else f"All {self.filtri['mio']}"), lin[0][1])
        tit = {"wr": "win rate", "n": "games", "turni": "average length in your turns", "mull": "mulligan rate",
               "ev": "EV vs expected: win-probability points your turns made above or below what the same turns usually give"
               + ("" if self.ev_di == "all" else f" · {dict(__import__('ev_partita').EV_DI)[self.ev_di].lower()}")}[self.metrica]
        fin = "" if self.metrica == "n" else (", cumulative sum" if self.finestra == "cum" and self.metrica == "ev" else ", cumulative" if self.finestra == "cum"
                                              else f", average of the last {self.finestra} games" if self.metrica == "ev" else f", last {self.finestra} games")
        tit = f"{tit}{fin}" + (f" · split by {DA.nome_var(self.dividi).lower()}" if self.dividi else "")
        vuoto = "No games in this situation" if not r else f"{len(r)} games: too few for this chart (a moving window starts at 5)"
        # Gained by decisions: un pannello sotto il grafico, col suo asse (13 nov 2026)
        banda = max(90, int((H - 60) * 0.32)) if self.mostra_guadagno else 0
        destra = W - (210 if self.dividi or extra else 120)
        sc = self.traccia(c, lin, (52, 16, destra, H - 44 - banda), self.metrica, self.asse, LINEE, tit, vuoto)
        if banda:
            self.disegna_guadagno(c, r, base_g, (52, H - 44 - banda + 44, destra, H - 44))
        # i loghi delle leghe e le coppe dei trofei, con le loro spunte sotto il grafico (13 nov 2026, Autore: «nei grafici non si vedono piu' i loghi dei
        # trofei per il limited e dei rank superati, metti una spunta per i rank e una per i trofei da accendere o spegnere sotto il grafico»)
        c._spunte_g = []
        F = self.F
        # le spunte sotto il grafico (13 nov 2026, Autore: «rank e trophy li metti a dx della chart / sotto mettici il flag per vs filter»): a sinistra
        # vs filter e Gained by decisions, a destra Ranks e Trophies
        x_ = 52
        for k_, nome in (("vs_filtro", "vs filter"), ("guadagno", "Gained by decisions")):
            on = getattr(self, "mostra_" + k_, False)
            c.create_image(x_, H - 14, image=DG.spunta(13, on, C["azzurro"], C["fondo"], C["grigio"], C["fondo"]), anchor="w")
            t_ = c.create_text(x_ + 18, H - 14, text=nome, anchor="w", fill=C["titolo"] if on else C["grigio"], font=F(7, True))
            x1_ = (c.bbox(t_) or (0, 0, x_ + 80, 0))[2]
            c._spunte_g.append((x_ - 2, H - 24, x1_ + 4, H - 4, k_))
            x_ = x1_ + 22
        x_ = W - 12
        for k_, nome in (("trofei", "Trophies"), ("ranghi", "Ranks")):
            on = getattr(self, "mostra_" + k_, True)
            t_ = c.create_text(x_, H - 14, text=nome, anchor="e", fill=C["titolo"] if on else C["grigio"], font=F(7, True))
            x0_ = (c.bbox(t_) or (x_ - 80, 0, 0, 0))[0]
            c.create_image(x0_ - 18, H - 14, image=DG.spunta(13, on, C["azzurro"], C["fondo"], C["grigio"], C["fondo"]), anchor="w")
            c._spunte_g.append((x0_ - 20, H - 24, x_ + 4, H - 4, k_))
            x_ = x0_ - 40
        if sc and self.asse == "games" and (len(lin) == 1 or vs):
            sx, sy = sc
            punti = dict(lin[0][1])
            if getattr(self, "mostra_ranghi", True):        # dove cambia la lega: la linea e il suo logo
                tipo_l = "limited" if self.tipo == "Limited" else "constructed"
                for i_, rango in DA.cambi_rango(r):
                    xx = sx(i_)
                    c.create_line(xx, 16, xx, H - 44 - banda, fill="#2c3340", dash=(3, 3))
                    img = self.logo_grafico(tipo_l, rango)
                    if img is not None:
                        c.create_image(xx, 18, image=img, anchor="n")
                    else:
                        c.create_text(xx + 4, 18, text=rango, anchor="nw", fill=C["grigio"], font=F(7, True))
            if getattr(self, "mostra_trofei", True):        # la coppa sulla partita che chiude un draft col trofeo
                img = self.logo_grafico(None, "coppa")
                for i_ in DA.trofei(r):
                    y_ = punti.get(i_)
                    if img is not None and y_ is not None:
                        c.create_image(sx(i_), sy(y_) - 12, image=img)
        if not self.partite_fuori:
            self.disegna_partite(self.ospite("chart").get("lista"))

    def disegna_guadagno(self, c, r, base_g, box):
        """Il pannello Gained by decisions (13 nov 2026, Autore: «voglio vedere il gained by decisions vs la media delle partite: positivo linea verde
        negativo linea rossa ( lo esprimiamo come guadagno per spots e non per win rate perché qui analizziamo le azioni non l'esito del game, ma se tanti spot
        positivi spostano il wr più in alto allora è un bel tell )»): le decisioni scelte in Decisions (il tipo e i suoi filtri), nelle partite di questa
        situazione, contro la media delle stesse decisioni in tutte le partite del tipo (DEC.guadagni); cumulato partita per partita, sullo stesso asse del
        grafico sopra; verde sopra lo zero, rosso sotto."""
        F = self.F
        x0, y0, x1, y1 = box
        tipi = (self.dec_modo,) if self.dec_modo in ("attacco", "blocco") else ("attacco", "blocco")
        tutte_t = [x for x in self.righe if x["tipo"] == self.tipo]
        per, medie = DEC.guadagni(r, tipi, self.dec_f, tutte_t)
        cosa = "your attacks" if tipi == ("attacco",) else "your defense" if tipi == ("blocco",) else "your attacks and blocks"
        f_ = " · ".join(DEC.descrivi(self.dec_f.get(t_), t_) for t_ in tipi if self.dec_f.get(t_))
        f_ = " · " + f_ if f_ else ""
        c.create_text(x0, y0 - 14, text=f"GAINED BY DECISIONS · {cosa}{f_} vs the average one (life + 2 × power), cumulative", anchor="w",
                      fill=C["muto"], font=F(7, True))
        sc_ = getattr(c, "_scala", None)
        if not per or not sc_:
            c.create_text((x0 + x1) / 2, (y0 + y1) / 2, text="No decisions of this kind in these games", fill=C["grigio"], font=F(8))
            return None
        _a, _b, _c, _d, xa, xb, _ya, _yb = sc_
        posto = {x.get("partita"): i + 1 for i, x in enumerate(sorted(base_g, key=lambda x: x["quando"]))}
        pts, cum = [], 0.0
        for x in sorted(r, key=lambda x: x["quando"]):
            if x.get("partita") not in per:
                continue
            cum += per[x["partita"]]
            xx = posto.get(x.get("partita")) if self.asse == "games" else x["quando"].date().toordinal()
            if xx is not None:
                pts.append((xx, cum))
        if not pts:
            return None
        m = max(1.0, max(abs(v) for _x, v in pts))
        sx = lambda v: x0 + (v - xa) / ((xb - xa) or 1) * (x1 - x0)
        sy = lambda v: (y0 + y1) / 2 - v / m * (y1 - y0) / 2
        c.create_rectangle(x0, y0, x1, y1, fill="#10141b", outline="#1d222b")
        c.create_line(x0, sy(0), x1, sy(0), fill="#2c3340")
        c.create_text(x0 - 8, sy(m), text=f"+{m:.0f}", anchor="e", fill=C["muto"], font=F(7))
        c.create_text(x0 - 8, sy(-m), text=f"-{m:.0f}", anchor="e", fill=C["muto"], font=F(7))
        c.create_text(x0 - 8, sy(0), text="0", anchor="e", fill=C["muto"], font=F(7))
        prima = (sx(pts[0][0]), sy(0))
        for xx, v in pts:
            p_ = (sx(xx), sy(v))
            c.create_line(*prima, *p_, fill="#5cb85c" if v >= 0 else "#d9534f", width=1.6)
            prima = p_
        fine = pts[-1][1]
        c.create_text(x1 + 8, sy(fine), text=f"{fine:+.0f} vs avg · {len(per)} games", anchor="w", fill="#5cb85c" if fine >= 0 else "#d9534f",
                      font=F(7, True))
        return fine

    def logo_grafico(self, tipo, nome):
        """Il logo di una lega (tipo «constructed» o «limited») o la coppa (nome «coppa»), fatto una volta."""
        cache = self.__dict__.setdefault("_loghi_g", {})
        if (tipo, nome) not in cache:
            import icone
            try:
                f = icone.emoji_png("🏆", "coppa", 20) if nome == "coppa" else icone.logo_lega(tipo, (nome or "").split(" ")[0], 26)
                cache[(tipo, nome)] = self.tk.PhotoImage(file=f) if f else None
            except Exception:      # noqa: BLE001 - senza il file resta il nome
                cache[(tipo, nome)] = None
        return cache[(tipo, nome)]

    def clic_grafico(self, e):
        """Le spunte sotto il grafico: vs filter, Gained by decisions, Ranks e Trophies."""
        for x0, y0, x1, y1, k in getattr(e.widget, "_spunte_g", []):
            if x0 <= e.x <= x1 and y0 <= e.y <= y1:
                setattr(self, "mostra_" + k, not getattr(self, "mostra_" + k, k in ("ranghi", "trofei")))
                self.disegna_vista("chart")
                return k
        return None

    # ------------------------------------------------------------ le partite sotto il grafico e la board di ognuna (12 nov 2026, Autore: «proprio come
    # holdem manager, sotto al grafico si dovrebbe generare una tabella che ci permette di vedere la nostra mano in una colonna e il board in un'altra colonna:
    # premendo su quello specifico dato si apre una board dedicata che ci mostra le carte in quello spot in mano o sul tavolo»)
    def colonne_partite(self, W):
        """Le colonne della tabella delle partite: (chiave, titolo, x, larghezza). Dal 18 nov 2026 (Autore: «spot EV lo mettiamo al posto di your
        opening hand con verde se in guadagno e rosso se in perdita per lo specifico spot / al posto di board at the end ... most ev card e dopo lowest ev
        card», «result alla fine»): l'EV dello spot, la carta che ha generato piu' EV e quella che ne ha generato meno si dividono quel che resta; il
        risultato in fondo."""
        spot = any(v not in (None, [], "") for k_, v in self.filtri.items() if k_.startswith(("t_", "sit:", "s_", "leak_")))      # un filtro con un momento
        fisse = (("data", "DATE", 96), ("mio", "YOUR DECK", 150), ("suo", "OPPONENT", 150), ("via", "START", 60), ("mull", "MULLIGAN", 76), ("turni", "TURNS", 56),
                 ("spotev", "SPOT EV" if spot else "GAME EV", 84))
        out, x = [], 8
        for k, t, w in fisse:
            out.append((k, t, x, w)); x += w
        resto = max(300, W - x - 8 - 72)
        out.append(("best", "MOST EV CARD", x, resto * 0.5)); x += resto * 0.5
        out.append(("worst", "LOWEST EV CARD", x, resto * 0.5)); x += resto * 0.5
        out.append(("esito", "RESULT", x, 64))
        return out

    def fai_tabella(self, padre):
        """La tabella delle partite dentro padre (sotto il grafico o nella sua finestra): la testa, le righe e a destra la barra per scorrere (12 nov 2026,
        Autore: «alla tabella dei dati dai lo slider a destra per scorrerla e rendi anche lei staccabile»). -> la tela delle righe."""
        tk = self.tk
        testa = tk.Canvas(padre, bg=C["scheda"], highlightthickness=0, bd=0, height=44); testa.pack(fill="x")
        riga_ = tk.Frame(padre, bg=C["scheda"]); riga_.pack(fill="both", expand=True)
        barra = tk.Canvas(riga_, width=10, bg=C["traccia"], highlightthickness=0, bd=0, cursor="hand2"); barra.pack(side="right", fill="y", padx=(4, 0))
        lista = tk.Canvas(riga_, bg=C["scheda"], highlightthickness=0, bd=0, height=100); lista.pack(side="left", fill="both", expand=True)

        def segna(a, b_):
            barra.delete("all")
            a, b_ = float(a), float(b_)
            if b_ - a < 0.999:
                H_ = barra.winfo_height()
                barra.create_rectangle(1, H_ * a, 9, max(H_ * a + 18, H_ * b_), fill=C["grigio"], width=0)

        def vai(e):
            lista.yview_moveto(max(0.0, e.y / max(barra.winfo_height(), 1) - (lista.yview()[1] - lista.yview()[0]) / 2))
            self.righe_partite(lista)
        lista.configure(yscrollincrement=ALTO_PARTITA, yscrollcommand=segna)
        barra.bind("<Button-1>", vai)
        barra.bind("<B1-Motion>", vai)
        barra.bind("<MouseWheel>", lambda e: (lista.yview_scroll(-2 if e.delta > 0 else 2, "units"), self.righe_partite(lista)))
        lista.testa, lista.barra = testa, barra
        testa.bind("<Button-1>", self.clic_testa_partite)
        testa.bind("<Motion>", lambda e: e.widget.configure(cursor="hand2" if e.x >= e.widget.winfo_width() - 34 and e.y < 22 else ""))
        lista.bind("<Configure>", lambda e: self.disegna_partite(e.widget))
        lista.bind("<MouseWheel>", lambda e: (e.widget.yview_scroll(-2 if e.delta > 0 else 2, "units"), self.righe_partite(e.widget)))
        lista.bind("<Motion>", self.sopra_partita)
        lista.bind("<Leave>", lambda e: (e.widget.delete("sopra"), self.via_hover_carte()))
        lista.bind("<Button-1>", self.clic_partita)
        return lista

    def tabella_partite(self):
        """La tabella delle partite che si vede: nella sua finestra se staccata, se no sotto il grafico."""
        if self.partite_fuori:
            return self.partite_fuori["lista"]
        return self.ospite("chart").get("lista")

    def clic_testa_partite(self, e):
        """Il segno in alto a destra della tabella: la stacca in una finestra sua, o la rimette sotto il grafico."""
        if e.x >= e.widget.winfo_width() - 34 and e.y < 22:
            if self.partite_fuori:
                self.riattacca_partite()
            else:
                self.stacca_partite()
            return None
        # i titoli delle colonne riordinano (13 nov 2026, Autore: «i titoli dell'elenco rendiamoli premibili in modo che riordinino l'elenco in base alla loro
        # voce, per i valori numerici ordine crescente dall'alto»): la prima volta crescente (la data dalla piu' recente), di nuovo al contrario
        if e.y >= 22:
            lista = next((l_ for l_ in self.tabelle_partite() if l_.testa is e.widget), None)
            k = next((k for k, _t, x, w in getattr(lista, "_col", []) if x <= e.x < x + w), None) if lista is not None else None
            if k in ORDINI_PARTITE:
                vecchio, cresce = self.ord_partite
                self.ord_partite = (k, not cresce if k == vecchio else k != "data")
                for l_ in self.tabelle_partite():
                    l_.yview_moveto(0)
                    self.disegna_partite(l_)
                return k
        return None

    def tabelle_partite(self):
        """Le tele della tabella delle partite che esistono: sotto il grafico e nella sua finestra."""
        out = []
        l_ = (self.ospite("chart") or {}).get("lista")
        if l_ is not None and l_.winfo_exists():
            out.append(l_)
        if self.partite_fuori and self.partite_fuori.get("lista") is not None and self.partite_fuori["lista"].winfo_exists():
            out.append(self.partite_fuori["lista"])
        return out

    def stacca_partite(self):
        """La tabella delle partite in una finestra sua (non sopra la grande: anche sull'altro schermo); sotto il grafico il posto va al grafico. Chiusa, torna."""
        if self.partite_fuori:
            w = self.partite_fuori["win"]
            w.deiconify(); w.lift()
            return w
        tk, F = self.tk, self.F
        w = tk.Toplevel(self.fr)
        w.title("Leak Finder · Games")
        w.configure(bg=C["scheda"])
        w.geometry(f"{max(self.pan.winfo_width(), 1000)}x560+{self.pan.winfo_rootx() + 40}+{self.pan.winfo_rooty() + 60}")
        testa = tk.Frame(w, bg=C["cap"]); testa.pack(fill="x")
        tk.Label(testa, text="LEAK FINDER · GAMES", bg=C["cap"], fg=C["titolo"], font=F(10, True)).pack(side="left", padx=(16, 10), pady=10)
        l_ = tk.Label(testa, text="", bg=C["cap"], fg=C["grigio"], font=F(8), anchor="w"); l_.pack(side="left", fill="x", expand=True)
        b = pulsante_solido(tk, F, testa, "Bring it back", False, self.riattacca_partite, alto=26, bg=C["cap"], colori=GRIGI)
        b.configure(width=120); b.pack(side="right", padx=(8, 16), pady=8)
        corpo_ = tk.Frame(w, bg=C["scheda"]); corpo_.pack(fill="both", expand=True, padx=12, pady=(8, 12))
        lista = self.fai_tabella(corpo_)
        self.partite_fuori = dict(win=w, lista=lista, l=l_)
        w.protocol("WM_DELETE_WINDOW", self.riattacca_partite)
        for o in self.copie("chart"):       # sotto il grafico il posto va al grafico
            if o.get("lista") is not None:
                o["lista"].diviso.forget(o["lista"].sotto)
        self.aggiorna_fuori()
        if self.righe is not None:
            w.after(60, lambda: w.winfo_exists() and self.disegna_partite(lista))
        return w

    def riattacca_partite(self):
        s_ = self.partite_fuori
        self.partite_fuori = None
        if s_:
            try:
                s_["win"].destroy()
            except Exception:      # noqa: BLE001 - gia' chiusa
                pass
        for o in self.copie("chart"):
            if o.get("lista") is not None:
                if str(o["lista"].sotto) not in [str(x_) for x_ in o["lista"].diviso.panes()]:
                    o["lista"].diviso.add(o["lista"].sotto, minsize=110, stretch="always")
        if self.righe is not None:
            self.disegna_partite(self.tabella_partite())

    def disegna_partite(self, c):
        if c is None or not c.winfo_exists() or self.righe is None:
            return
        F = self.F
        k_o, cresce = self.ord_partite
        if k_o not in ORDINI_PARTITE:       # una colonna che non c'e' piu' (la mano, prima del 18 nov 2026): si torna alla data
            self.ord_partite = k_o, cresce = ("data", False)
        chiave = ORDINI_PARTITE[k_o]
        # l'EV dello spot di ogni partita, coi filtri di adesso (l'atteso da tutte le partite del tipo)
        import ev_partita as EV_
        base_ = [x for x in self.righe if x["tipo"] == self.tipo]
        _SPOT_EV.clear()
        for x in self.scelte():
            v_, _s = EV_.ev_spot_partita(x, self.filtri, base_)
            if v_ is not None:
                _SPOT_EV[x.get("partita")] = v_
        if k_o in ("best", "worst"):
            _CARTE_EV.clear()
            for x in self.scelte():
                cc_ = EV_.carte_ev_partita(x, base_)
                if cc_:
                    _CARTE_EV[x.get("partita")] = (cc_[0][1], cc_[-1][1])
        nulli = [x for x in self.scelte() if chiave(x) is None]
        c._partite = sorted([x for x in self.scelte() if chiave(x) is not None], key=chiave, reverse=not cresce) + nulli       # chi non ha il dato in fondo
        c._col = self.colonne_partite(max(c.winfo_width(), 700))
        t = c.testa
        t.delete("all")
        Wt = max(t.winfo_width(), 700)
        t.create_rectangle(0, 4, 2, 16, fill=C["accento"], outline="")
        t.create_text(8, 10, text=f"GAMES IN THIS SITUATION · {len(c._partite)}", anchor="w", fill=C["titolo"], font=F(8, True))
        t.create_text(Wt - 40, 10, text="click a game: it opens its replay · Spot EV: green gained, red lost against the usual", anchor="e",
                      fill=C["muto"], font=F(7))
        d = DG.Disegno(28, 22)       # il segno per staccarla (o rimetterla sotto il grafico), come le cartelle
        _segno_stacca(d, 14, 11, C["accento"] if self.partite_fuori else C["grigio"], bool(self.partite_fuori))
        c._img_segno = d.foto()
        t.create_image(Wt - 30, 0, image=c._img_segno, anchor="nw")
        t.create_rectangle(0, 23, max(t.winfo_width(), 700), 43, fill=TESTA_TAB, outline="")
        for k_, tit, x, _w in c._col:
            on = k_ == k_o
            t.create_text(x, 33, text=tit + (("  ↑" if cresce else "  ↓") if on else ""), anchor="w",
                          fill=C["accento"] if on else C["titolo"] if k_ in ORDINI_PARTITE else C["testo"], font=F(8, True))
        t.create_line(0, 43, max(t.winfo_width(), 700), 43, fill=C["accento"], width=2)
        c.configure(scrollregion=(0, 0, max(c.winfo_width(), 700), max(1, len(c._partite)) * ALTO_PARTITA))
        self.righe_partite(c)

    def righe_partite(self, c):
        """Solo le righe in vista (le partite possono essere centinaia)."""
        c.delete("riga")
        F = self.F
        partite = getattr(c, "_partite", [])
        if not partite:
            c.create_text(8, 16, text="No games in this situation", anchor="w", fill=C["grigio"], font=F(8), tags="riga")
            return
        corto = lambda t_, n: t_ if len(t_) <= n else t_[:n - 1] + "…"
        top = c.canvasy(0)
        a = max(0, int(top // ALTO_PARTITA) - 1)
        b = min(len(partite), int((top + max(c.winfo_height(), 100)) // ALTO_PARTITA) + 2)
        W = max(c.winfo_width(), 700)
        for i in range(a, b):
            x_ = partite[i]
            y = i * ALTO_PARTITA
            if i % 2 == 0:
                c.create_rectangle(0, y, W, y + ALTO_PARTITA, fill="#161b25", outline="", tags=("riga", "fondo"))
            fo = DA.foto_partita(x_)
            for k, _t, x, w in c._col:
                col, testo, font = C["testo"], "", F(8)
                if k == "data":
                    testo = x_["quando"].strftime("%d %b %H:%M")
                elif k == "mio":
                    testo, col = (x_.get("mio") or "-").strip(), C["titolo"]
                elif k == "suo":       # contro chi: la combinazione di colori, coi simboli (12 nov 2026, Autore: «opponent usiamo la combinazione colori»)
                    v = DA.vs_di(x_)
                    if v:
                        for j, ch in enumerate(v):
                            img = self.lista().simbolo(ch, 14)
                            if img is not None:
                                c.create_image(x + 7 + j * 15, y + ALTO_PARTITA / 2, image=img, tags="riga")
                        x, w = x + 8 + len(v) * 15 + 4, w - 8 - len(v) * 15 - 4
                        testo = ""        # i soli simboli, niente nome dei colori (13 nov 2026, Autore: «invece di descrivere i colori per testo usiamo i simboli di mana»)
                    else:
                        testo, col = "Unknown", C["muto"]
                elif k == "esito":      # dopo il mulligan, e accanto i turni della partita (12 nov 2026, Autore: «result dopo mulligan e dopo result il numero
                    testo = "Won" if x_["vinta"] else "Lost"        # di turni partita»)
                    col, font = (C["verde"] if x_["vinta"] else C["rosso"]), F(8, True)
                    c.create_image(x + 3, y + ALTO_PARTITA / 2, image=DG.punto(6, col), tags="riga")       # il pallino del risultato (redesign del 14 nov 2026)
                    x, w = x + 12, w - 12
                elif k == "turni":
                    testo = str(x_["turno"]) if x_.get("turno") else "-"
                elif k == "via":
                    testo = x_.get("partenza") or "-"
                elif k == "mull":       # la sua colonna (12 nov 2026, Autore: «aggiungi anche la colonna mulligan cosi' esce dallo start»)
                    n_ = x_.get("mulligan")
                    testo = "-" if n_ is None else str(n_)
                    col = C["muto"] if not n_ else C["arancio"]
                elif k == "spotev":     # l'EV dello spot: verde se guadagnato, rosso se perso, contro il solito
                    v_ = _SPOT_EV.get(x_.get("partita"))
                    testo = "-" if v_ is None else f"{v_:+.1f}"
                    col = C["muto"] if v_ is None or abs(v_) < 0.05 else (C["verde"] if v_ > 0 else C["rosso"])
                    font = F(8, True)
                elif k in ("best", "worst"):        # la carta che ha generato piu' EV, e quella che ne ha generato meno
                    import ev_partita as EV_
                    cc_ = EV_.carte_ev_partita(x_, [z for z in self.righe if z["tipo"] == x_.get("tipo")])
                    if not cc_:
                        testo, col = "not in the logs" if not fo else "-", C["muto"]
                    else:
                        nome_, v_ = cc_[0] if k == "best" else cc_[-1]
                        testo = f"{nome_}  {v_:+.1f}"
                        col = C["verde"] if v_ > 0 else C["rosso"] if v_ < 0 else C["testo"]
                c.create_text(x, y + ALTO_PARTITA / 2, text=corto(testo, int((w - 10) / 6.2)), anchor="w", fill=col, font=font, tags="riga")

    def testo_mano(self, fo):
        """La mano tenuta in una riga: le magie, poi quante terre."""
        if not fo or not fo["mano0"]:
            return "not in the logs"
        import mazzi_salvati as MS
        mano = fo["mano0"]["mano"]
        magie = [n for n in mano if not MS.e_terra(n)]
        terre = len(mano) - len(magie)
        return ", ".join(magie) + (f"  ·  {terre} land{'s' if terre != 1 else ''}" if terre or not magie else "")


    def partita_a(self, c, e):
        """(partita, colonna) sotto il puntatore, o (None, None)."""
        y = c.canvasy(e.y)
        i = int(y // ALTO_PARTITA)
        partite = getattr(c, "_partite", [])
        if not 0 <= i < len(partite):
            return None, None
        k = next((k for k, _t, x, w in getattr(c, "_col", []) if x <= e.x < x + w), None)
        return partite[i], k

    def carta_ev_riga(self, x_, k):
        """La carta della colonna MOST EV CARD o LOWEST EV CARD di una partita della tabella, o None."""
        if k not in ("best", "worst") or x_ is None:
            return None
        import ev_partita as EV_
        cc_ = EV_.carte_ev_partita(x_, [z for z in self.righe or [] if z["tipo"] == x_.get("tipo")])
        return (cc_[0] if k == "best" else cc_[-1])[0] if cc_ else None

    def sopra_partita(self, e):
        c = e.widget
        c.delete("sopra")
        x_, k = self.partita_a(c, e)
        c.configure(cursor="hand2" if x_ is not None else "")
        # la carta grande al passaggio sopra MOST EV CARD e LOWEST EV CARD (18 nov 2026, Autore: «dammi la possibilita' di vedere la carta in hover»):
        # la stessa finestrella della cartella Cards
        n_ = self.carta_ev_riga(x_, k)
        if n_ != getattr(self, "_hc_nome", None):
            self.via_hover_carte()
            img = self.immagine_grande(DA.nome_intero(n_)) if n_ else None
            if img is not None:
                h = self._hc = self.tk.Toplevel(c.winfo_toplevel())
                h.overrideredirect(True)
                h.configure(bg="#0b0e14")
                self.tk.Label(h, image=img, bg="#0b0e14", bd=0).pack(padx=2, pady=2)
                self._hc_nome = n_
        if n_ and getattr(self, "_hc", None) is not None:
            self.metti_hover_carte(e)
        if x_ is None:
            return
        # la riga si schiarisce appena, senza cornice e trasparente (12 nov 2026, Autore: «togli la cornice di selezione blu ... evidenziala
        # delicatamente», poi «la selezione sulla riga deve essere trasparente»): un velo bianco al 7% sopra la riga, la mano o la board al 12%
        i = int(c.canvasy(e.y) // ALTO_PARTITA)
        W = max(c.winfo_width(), 700)
        d = DG.Disegno(W, ALTO_PARTITA)
        d.rett(0, 0, W, ALTO_PARTITA, riempi=(255, 255, 255, 18))
        if k in ("best", "worst", "spotev"):
            x, w = next((x, w) for k_, _t, x, w in c._col if k_ == k)
            d.rett(x - 6, 0, x + w - 4, ALTO_PARTITA, riempi=(255, 255, 255, 14), raggio=3)
        c._img_sopra = d.foto(veloce=True)
        c.create_image(0, i * ALTO_PARTITA, image=c._img_sopra, anchor="nw", tags="sopra")

    def clic_partita(self, e):
        c = getattr(e, "widget", None) or self.tabella_partite()
        x_, k = self.partita_a(c, e)
        if x_ is not None:
            # il replay parte sempre dall'inizio, la mano tenuta (12 nov 2026, Autore: «i replay partono tutti dalla fine e mai dall'inizio»); R15: le
            # partite della tabella, nel suo ordine, sono la playlist
            self.playlist = dict(partite=list(getattr(c, "_partite", []) or [x_]), nome="games in this situation")
            self.apri_board(x_, "filtro")       # sullo spot dei filtri, se ne hanno uno (15 nov 2026)

    def passi_board(self, fo):
        """I momenti di una partita da guardare: la mano tenuta, la fine di ogni turno, l'ultimo stato (se e' dopo l'ultima fine di turno).
        -> [(nome, foto, turno di Arena)]."""
        passi = []
        if fo["mano0"]:
            passi.append(("Opening hand", fo["mano0"], 0, None))
        corto = lambda t_, n: t_ if len(t_) <= n else t_[:n - 1] + "…"
        for t, mio_, f, kind, rel in fo["turni"]:      # Arena conta i turni dei due giocatori insieme: qui il turno di ognuno, come in partita
            base = f"{'You' if mio_ else 'Opponent'} T{(t + 1) // 2}"
            if kind == "comb":
                base += " · combat"
            elif kind == "spell":
                base += " · " + corto(rel["nome"], 16)
            passi.append((base, f, t, rel))
        if fo["ultima"] and fo["ultima"][2] and (not fo["turni"] or fo["ultima"][2] != fo["turni"][-1][2]):
            passi.append(("End", fo["ultima"][2], fo["ultima"][0], None))
        return passi

    @staticmethod
    def forza(lato):
        """La forza delle creature in campo di un lato. Una forza negativa (segnalini -1/-1) conta 0: non fa danni, e nel grafico della barra una
        barra negativa faceva cadere il disegno (debug del 12 nov 2026: in 7 partite su 25 la barra del replayer non si disegnava)."""
        return sum(max(0, c_[3] or 0) for c_ in lato if len(c_) > 3 and c_[3] is not None)

    def momenti(self, passi):
        """Il grafico della partita: per ogni momento le vite, la forza in campo dei due e il vantaggio (vite di differenza piu' due volte la forza di
        differenza: grado C, un modo semplice di dire chi sta davanti). -> [dict(vite, forza, vantaggio)]."""
        out = []
        for p_ in passi:
            f = p_[1]
            v = f.get("vite") or (None, None)
            fm, fs = self.forza(f["mio"]), self.forza(f["suo"])
            vm, vs = (v[0] if v[0] is not None else 20), (v[1] if v[1] is not None else 20)
            out.append(dict(vite=(vm, vs), forza=(fm, fs), vantaggio=(vm - vs) + 2 * (fm - fs)))
        return out

    def curva_p(self, b):
        """La curva della partita (18 nov 2026, Autore: «procedi con 1 2 3 4», la 4: la probabilita' di vincere sulla timeline): [(indice del passo,
        P in percentuale, scarto del turno che finisce li')], dal conto della partita di ev_partita (la P a inizio partita, poi a fine di ogni turno sull'ultimo
        passo di quel turno). None senza il conto. Una volta per partita e modo."""
        k_ = (id(b["passi"]),)
        if b.get("_curva_k") == k_:
            return b["_curva"]
        out = None
        try:
            import ev_partita as EV_
            x = b["x"]
            base = [y for y in self.righe or [] if y["tipo"] == x.get("tipo")]
            tt = EV_._turni_di(base, x.get("partita")) if base else []
            ultimo = {}
            for i, p_ in enumerate(b["passi"]):
                ultimo[p_[2]] = i
            pts = []
            for z in tt:
                i = ultimo.get(z["t"])
                if i is None or z.get("p1") is None:
                    continue
                if not pts and z.get("p0") is not None:
                    pts.append((0, z["p0"], None))
                if pts and i <= pts[-1][0]:
                    continue
                pts.append((i, z["p1"], z.get("scarto")))
            out = pts if len(pts) >= 2 else None
        except Exception:       # noqa: BLE001 - senza il conto della partita il grafico resta quello delle vite
            out = None
        b["_curva_k"], b["_curva"] = k_, out
        return out

    def svolta(self, passi, vinta):
        """Il punto di svolta: il momento in cui il vantaggio cambia di piu' verso chi ha vinto (None con meno di 3 momenti)."""
        m = self.momenti(passi)
        if len(m) < 3:
            return None
        if len(m) >= 4:     # l'ultimo momento no: il colpo che chiude e' sempre il piu' grande, la svolta viene prima
            m = m[:-1]
        salti = [(m[i]["vantaggio"] - m[i - 1]["vantaggio"]) * (1 if vinta else -1) for i in range(1, len(m))]
        i = max(range(len(salti)), key=lambda j: salti[j])
        return i + 1 if salti[i] > 0 else None

    def posto_board(self, largo=1500, alto=960):
        """Il replayer al centro della finestra dell'app (13 nov 2026, Autore: «quando apriamo il replayer facciamolo partire bello centrato alla
        pagina»), mai piu' grande di lei meno un margine; prima si apriva a 60 pixel dal bordo della tabella, spostato a destra."""
        top = self.fr.winfo_toplevel()
        top.update_idletasks()
        x0, y0, W, H = top.winfo_rootx(), top.winfo_rooty(), top.winfo_width(), top.winfo_height()
        if W < 200 or H < 200:          # la finestra non ancora disegnata: lo schermo
            x0, y0, W, H = 0, 0, top.winfo_screenwidth(), top.winfo_screenheight()
        w, h = min(largo, W - 40), min(alto, H - 40)
        return f"{w}x{h}+{x0 + (W - w) // 2}+{max(0, y0 + (H - h) // 2)}"

    CHIUSE_AVVIO = True
    MODO_AVVIO = "azioni"
    MOMENTI_VISIBILI = False        # Moments nel replayer: tolto per adesso (19 nov 2026)
    PASSO_PLAY = 800            # ms a 1x (18 nov 2026, Autore: «rendi x1 l'attuale x2 e x2 il doppio»: il 2x di prima durava 800 ms a passo, perche' la
    # pausa dopo i voli (800 ms) non seguiva la velocita' e copriva i 525 ms del passo; ora 1x = 800 e la pausa si divide per la velocita', cosi' il 2x
    # dimezza davvero; le due attese a meta')
    # prima: ms a 1x (14 nov 2026, Autore: «la nuova velocita' 1x deve essere 0,5x attuale»: era 1600; poi «tutto piu' lento»: 3200, 4200;
    # la sera «la nuova velocita' x1 deve essere l'attuale x2»: 2100, e le attese dopo l'attacco e la magia in pila dimezzate; a notte, di nuovo «la nuova
    # velocita' 1 deve essere l'attuale velocita' 2»: 1050, e le due attese ancora a meta')
    ATTESA_ATTACCO = 188        # in piu' dopo la dichiarazione degli attaccanti, prima dei bloccanti (era 750)
    ATTESA_MAGIA = 325          # la magia in pila: il tempo di vederla prima che si risolva (era 1300)

    def apri_board(self, x_, dove="inizio"):
        """La board di una partita: in alto i momenti (la mano tenuta, la fine di ogni turno, la fine), sotto la tavola: le sue carte in campo, le tue, la tua
        mano, con le vite; le carte tappate girate. Frecce o clic per muoversi. Una finestra sola: un'altra partita la riempie."""
        tk, F = self.tk, self.F
        fo = DA.foto_partita(x_)
        if not fo:
            return None
        passi = self.passi_board(fo)
        if not passi:
            return None
        # i Moments dalle foto di Every action (16 nov 2026, Autore: «in modalita' moments ora e' un po' buggato nel mettere in sequenza le azioni la pila
        # ecc mentre in every action e' piu' affidabile»): un momento e' un passo scelto della sequenza azione per azione, con gli stessi dati (la pila, gli
        # id, da dove parte una magia); senza il log della partita restano i momenti di mana_aperto
        az_ = DA.azioni_partita(x_) or []
        idx_m = momenti_da_azioni(az_) if az_ else None
        if idx_m:
            passi = [(nome_momento(az_, k_),) + tuple(az_[k_][1:]) for k_ in idx_m]
        f = getattr(self, "fin_board", None)
        if f is None or not f.winfo_exists():
            # il replayer parte con tutte le sezioni espandibili chiuse (14 nov 2026, Autore: «il replayer deve partire con tutte le sezioni espandibili
            # chiuse»): la striscia dei turni, le due liste dei mazzi ai lati, il grafico sopra la timeline; si aprono con le loro linguette
            if not self.MOMENTI_VISIBILI:
                self._modo_board = "azioni"
            if self.MODO_AVVIO:         # parte da Every action (14 nov 2026, Autore: «fai partire il replayer da every action»)
                self._modo_board = self.MODO_AVVIO
            if self.CHIUSE_AVVIO:       # le prove di prima del 14 nov 2026 lo spengono: guardano le sezioni aperte
                self._passi_chiusi, self._graf_chiuso = True, True
                self.liste_chiuse().update(mio=True, suo=True)
            f = self.fin_board = tk.Toplevel(self.fr); f.configure(bg=C["scheda"])
            # il replayer a vista: i lavori di sottofondo (scalda_decisioni, scalda_solito) aspettano, cosi' le animazioni non perdono quadri (23 nov 2026)
            f.bind("<Map>", lambda e, f=f: setattr(self, "_replayer_a_vista", True) if e.widget is f else None, add="+")
            f.bind("<Unmap>", lambda e, f=f: setattr(self, "_replayer_a_vista", False) if e.widget is f else None, add="+")
            f.bind("<Destroy>", lambda e, f=f: setattr(self, "_replayer_a_vista", False) if e.widget is f else None, add="+")
            f.title("The board")
            f.geometry(self.posto_board())
            f.bind("<Escape>", lambda e: self.chiudi_pila() if getattr(self, "_pila_aperta", None) else f.destroy())
            f.bind("<Left>", lambda e: self.passo_board(-1))
            f.bind("<Right>", lambda e: self.passo_board(1))
            testa_b = tk.Frame(f, bg=C["cap"]); testa_b.pack(fill="x")
            # il titolo bianco (data, mazzi, il record del giorno) non si mostra piu' (14 nov 2026, Autore: «togli in alto a sx il testo bianco di
            # titolo»): la testata tiene solo i pulsanti, che cosi' ci stanno tutti; l'etichetta resta, senza posto, per chi le scrive il testo
            self.l_board = tk.Label(testa_b, text="", bg=C["cap"], fg=C["titolo"], font=F(10, True), anchor="w", padx=16, pady=10)
            tk.Frame(testa_b, bg=C["cap"], width=12).pack(side="left")
            # Moments (quello di sempre) o Every action, azione per azione (12 nov 2026, Autore: «il replayer migliore in circolazione ... basta che non
            # perdiamo assolutamente cio' che abbiamo adesso»)
            self.b_modi = {}
            # i salti e il segnalibro (12 nov 2026, «Sì, prosegui» sui salti e i segnalibri): il clic va avanti, col Maiuscolo indietro; tasti C, S, O, B
            self.b_salti = {}
            for k_, n_ in (("chiave", "Key ›"), ("comb", "Combat ›"), ("spell", "Spell ›"), ("tappato", "Opp. tapped out ›"), ("leak", "Leak ›"),
                         ("filtro", "Filter ›")):
                b_ = pulsante_solido(tk, F, testa_b, n_, False, lambda k_=k_: self.salta(k_), alto=26, bg=C["cap"], colori=GRIGI)
                b_.configure(width=150 if k_ == "tappato" else 96); b_.pack(side="left", padx=(0, 6), pady=8)
                b_.bind("<Shift-Button-1>", lambda e, k_=k_: (self.salta(k_, -1), "break")[1])
                self.b_salti[k_] = b_
            # di chi sono i momenti chiave (R16, come su chess.com): tutti e due, i tuoi (il vantaggio sale per te), i suoi
            self.b_chi = pulsante_solido(tk, F, testa_b, "Keys: both", False, self.cambia_chi_chiave, alto=26, bg=C["cap"], colori=GRIGI)
            self.b_chi.configure(width=104); self.b_chi.pack(side="left", padx=(0, 6), pady=8)
            self.b_segna = pulsante_solido(tk, F, testa_b, "Bookmark", False, self.segna_board, alto=26, bg=C["cap"], colori=("#3a3220", "#4a4028", "#8a6d1c"))
            self.b_segna.configure(width=120); self.b_segna.pack(side="left", padx=(6, 6), pady=8)
            # R3: una nota sulla partita (e sullo spot, se e' segnato)
            self.b_nota = pulsante_solido(tk, F, testa_b, "Note", False, self.apri_nota_board, alto=26, bg=C["cap"], colori=("#3a3220", "#4a4028", "#8a6d1c"))
            self.b_nota.configure(width=84); self.b_nota.pack(side="left", padx=(0, 6), pady=8)
            # i filtri da questo momento (16 nov 2026, Autore: «possiamo lavorare dai replay al contrario? ovvero estrarre da un momento di un replay un
            # insieme di filtri che descrivono quel momento?», «Sì, costruiscilo»)
            self.b_momento = pulsante_solido(tk, F, testa_b, "Filters from here", False, self.menu_momento, alto=26, bg=C["cap"], colori=GRIGI, icona=False)
            self.b_momento.configure(width=150); self.b_momento.pack(side="left", padx=(0, 6), pady=8)
            # In hand: la mano a ventaglio (acceso) o il tavolo ingrandito con la mano in riga piccola (spento); 14 nov 2026
            self.b_mano = pulsante_solido(tk, F, testa_b, "In hand" if self.mano_in_vista() else "In hand: off", self.mano_in_vista(), self.cambia_mano, alto=26,
                                          bg=C["cap"], colori=GRIGI)
            self.b_mano.configure(width=110); self.b_mano.pack(side="left", padx=(0, 6), pady=8)
            f.bind("<h>", lambda e: self.cambia_mano())
            # R2 e R17: la partita come testo o pagina web, lo spot come immagine; senza nomi ne' id dell'account
            self.b_esporta = pulsante_solido(tk, F, testa_b, "Export ▾", False, self.menu_esporta, alto=26, bg=C["cap"], colori=GRIGI)
            self.b_esporta.configure(width=96); self.b_esporta.pack(side="left", padx=(0, 6), pady=8)
            # R15: la playlist, partita dopo partita (tasti P e N; i salti, a fine partita, continuano nella partita dopo)
            self.b_gioco = {}
            for d_, n_ in ((-1, "◀ Game"), (1, "Game ▶")):
                b_ = pulsante_solido(tk, F, testa_b, n_, False, lambda d_=d_: self.gioco_playlist(d_), alto=26, bg=C["cap"], colori=GRIGI)
                b_.configure(width=80); b_.pack(side="left", padx=(0, 6 if d_ < 0 else 12), pady=8)
                self.b_gioco[d_] = b_
            f.bind("<n>", lambda e: self.gioco_playlist(1))
            f.bind("<p>", lambda e: self.gioco_playlist(-1))
            for tasto, k_ in (("c", "comb"), ("s", "spell"), ("o", "tappato"), ("l", "leak"), ("k", "chiave"), ("f", "filtro")):
                f.bind(f"<{tasto}>", lambda e, k_=k_: self.salta(k_))
                f.bind(f"<{tasto.upper()}>", lambda e, k_=k_: self.salta(k_, -1))
            f.bind("<b>", lambda e: self.segna_board())
            # Moments tolto per adesso (19 nov 2026, Autore: «togli moments per adesso dal replayer»): il replayer va solo azione per azione; il codice resta
            # poi anche Every action (stesso giorno: «a questo punto togli anche every action, il replayer sara' solo every action»): con un modo solo niente pulsanti
            for k_, n_ in ((("azioni", "Every action"), ("momenti", "Moments")) if self.MOMENTI_VISIBILI else ()):
                b_ = pulsante_solido(tk, F, testa_b, n_, False, lambda k_=k_: self.cambia_modo_board(k_), alto=26, bg=C["cap"], colori=GRIGI)
                b_.configure(width=120); b_.pack(side="right", padx=(0, 8), pady=8)
                self.b_modi[k_] = b_
            f.bind("<Prior>", lambda e: self.turno_board(-1))
            f.bind("<Next>", lambda e: self.turno_board(1))
            self.cv_passi = tk.Canvas(f, bg=C["scheda"], highlightthickness=0, bd=0, height=40)
            self.cv_passi.bind("<Button-1>", self.clic_passo)
            # la striscia dei turni si chiude verso l'alto con la sua linguetta, come il grafico in basso (14 nov 2026, Autore: «il menu turni in alto
            # sia anche quello espandibile con freccetta»); la scelta resta per le partite dopo
            self.cv_ling_passi = tk.Canvas(f, height=14, bg=C["scheda"], highlightthickness=0, bd=0, cursor="hand2")
            self.cv_ling_passi.bind("<Configure>", lambda e: self.disegna_linguetta_passi())
            self.cv_ling_passi.bind("<Enter>", lambda e: self.disegna_linguetta_passi(True))
            self.cv_ling_passi.bind("<Leave>", lambda e: self.disegna_linguetta_passi(False))
            self.cv_ling_passi.bind("<Button-1>", lambda e: self.chiudi_passi())
            if not self.__dict__.get("_passi_chiusi"):
                self.cv_passi.pack(fill="x", padx=12, pady=(10, 0))
            self.cv_ling_passi.pack(fill="x", pady=(2 if self.__dict__.get("_passi_chiusi") else 0, 2))
            # in fondo i comandi di un replayer (12 nov 2026, Autore: «visto che abbiamo costruito una board che e' un player, metti in fondo le classiche
            # funzioni di un replayer»): inizio, indietro, play e pausa, avanti, fine, la timeline da cliccare o trascinare, la velocita'
            self.cv_ctrl = tk.Canvas(f, bg=C["cap"], highlightthickness=0, bd=0, height=ALTO_CTRL, cursor="hand2")
            self.cv_ctrl.pack(side="bottom", fill="x")
            # la linguetta sopra la barra: chiude il grafico della partita verso il basso, resta la riga dei comandi (14 nov 2026, Autore: «rendi
            # chiudibile verso il basso la timeline espansa»)
            self.cv_linguetta = tk.Canvas(f, height=14, bg=C["scheda"], highlightthickness=0, bd=0, cursor="hand2")
            self.cv_linguetta.pack(side="bottom", fill="x")
            self.cv_linguetta.bind("<Configure>", lambda e: self.disegna_linguetta())
            self.cv_linguetta.bind("<Enter>", lambda e: self.disegna_linguetta(True))
            self.cv_linguetta.bind("<Leave>", lambda e: self.disegna_linguetta(False))
            self.cv_linguetta.bind("<Button-1>", lambda e: self.chiudi_grafico())
            self.cv_ctrl.bind("<Configure>", lambda e: self.disegna_controlli())
            self.cv_ctrl.bind("<Button-1>", self.clic_controlli)
            self.cv_ctrl.bind("<B1-Motion>", self.trascina_timeline)
            f.bind("<space>", lambda e: self.play_board())
            f.bind("<Home>", lambda e: self.vai_board(0))
            f.bind("<End>", lambda e: self.vai_board(10 ** 6))
            f.bind("<t>", lambda e: self.vai_svolta())
            f.bind("<Destroy>", lambda e: e.widget is f and self.via_hover(), add="+")
            f.bind("<Destroy>", lambda e: e.widget is f and self.ferma_board(), add="+")
            # ai lati della tavola le due liste, come nel replay di Untapped (13 nov 2026, voci R1 e R6 del censimento; Autore: «Sì, R1+R6»): a sinistra
            # il tuo mazzo con le copie rimaste nel grimorio a quel momento, a destra le sue carte viste fino a quel momento, con «Copy as list»
            mezzo = tk.Frame(f, bg=C["scheda"]); mezzo.pack(fill="both", expand=True, padx=12, pady=(4, 8))
            # chiudibili con la linguetta dell'outliner del Board (13 nov 2026, Autore: «le freccette per comprimere le liste le voglio come nell'outliner
            # della board editor, stesso colore stesso stile stessa posizione»): una striscia a tutta altezza sul bordo verso la tavola, ◀ ▶
            self.f_lista_mio = tk.Frame(mezzo, bg=C["scheda"]); self.f_lista_mio.pack(side="left", fill="y", padx=(0, 8))
            self.f_lista_suo = tk.Frame(mezzo, bg=C["scheda"]); self.f_lista_suo.pack(side="right", fill="y", padx=(8, 0))
            self.b_lista = {}
            for lato, fr_, verso in (("mio", self.f_lista_mio, "right"), ("suo", self.f_lista_suo, "left")):
                lab_ = tk.Label(fr_, text="", bg=C["cap"], fg=C["titolo"], font=F(8, True), cursor="hand2", width=2)
                lab_.pack(side=verso, fill="y")
                lab_.bind("<Button-1>", lambda e, lato=lato: self.chiudi_lista(lato))
                self.b_lista[lato] = lab_
            self.cv_lista_mio = tk.Canvas(self.f_lista_mio, bg="#0d1016", highlightthickness=1, highlightbackground=C["filo"], bd=0, width=LARGA_LISTA)
            self.cv_lista_suo = tk.Canvas(self.f_lista_suo, bg="#0d1016", highlightthickness=1, highlightbackground=C["filo"], bd=0, width=LARGA_LISTA)
            self.metti_liste()
            for cv_ in (self.cv_lista_mio, self.cv_lista_suo):
                cv_.bind("<Configure>", lambda e: self.disegna_liste())
                cv_.bind("<Motion>", self.sopra_lista)
                cv_.bind("<Leave>", self.via_hover)
                cv_.bind("<Button-1>", self.clic_lista)
                cv_.bind("<MouseWheel>", lambda e: (self.via_hover(), e.widget.yview_scroll(-2 if e.delta > 0 else 2, "units")))
            self.cv_board = tk.Canvas(mezzo, bg="#0d1016", highlightthickness=1, highlightbackground=C["filo"], bd=0)
            self.cv_board.pack(side="left", fill="both", expand=True)
            self.cv_board.bind("<Configure>", lambda e: self.disegna_board())
            self.cv_board.bind("<Button-1>", self.clic_pila)
            self.cv_board.bind("<Motion>", self.sopra_carta_board)
            self.cv_board.bind("<Leave>", self.via_hover)
        self.ferma_board()
        self._pila_aperta = None
        self._board = dict(x=x_, passi=passi, i=len(passi) - 1 if dove == "fine" else 0, play=False, vel=getattr(self, "_vel_board", 1.0), modo="momenti",
                           momenti_passi=passi)
        if idx_m:
            self._board["azioni_passi"], self._board["mom_idx"] = az_, idx_m
        self._board["svolta"] = self.svolta(passi, x_["vinta"])
        if getattr(self, "_modo_board", "momenti") == "azioni" or not self.MOMENTI_VISIBILI:      # resta la scelta dell'ultima volta (senza Moments: sempre)
            self.cambia_modo_board("azioni", ridisegna=False)
            if dove != "fine":      # in Every action dalla prima azione
                self._board["i"] = 0
        if dove == "filtro":        # sullo spot dei filtri accesi, se ne hanno uno (15 nov 2026); se no dall'inizio
            i_f = self.primo_spot(self._board)
            if i_f is not None:
                self._board["i"] = i_f
        for k_, b_ in self.b_modi.items():
            b_.metti({"azioni": "Every action", "momenti": "Moments"}[k_], k_ == self._board["modo"])
        esito = "won" if x_["vinta"] else "lost"
        # R11 (13 nov 2026, come PokerTracker): il record com'era quel giorno, prima di questa partita (tutte le partite del tipo, e con questo mazzo)
        prima_ = [y for y in self.righe or [] if y["tipo"] == x_.get("tipo") and y["quando"].date() == x_["quando"].date() and y["quando"] < x_["quando"]]
        stesso_ = [y for y in prima_ if y.get("mio") == x_.get("mio")]
        rec_ = lambda yy: f"{sum(1 for y in yy if y['vinta'])}-{sum(1 for y in yy if not y['vinta'])}"
        giorno_ = (f"  ·  that day before it: {rec_(prima_)}" + (f" ({rec_(stesso_)} with this deck)" if stesso_ and len(stesso_) != len(prima_) else "")
                   if prima_ else "  ·  first game of that day")
        self.l_board.configure(text=f"{x_['quando']:%d %b %Y %H:%M}  ·  {(x_.get('mio') or '-').strip()} vs {x_.get('suo') or '-'}  ·  {esito}"
                               + (f" on turn {x_['turno']}" if x_.get("turno") else "") + (f"  ·  {x_['partenza'].lower()}" if x_.get("partenza") else "") + giorno_)
        pl_ = self.posto_playlist(x_)
        f.title(f"The board · {(x_.get('mio') or '').strip()} vs {x_.get('suo') or ''}"
                + (f" · game {pl_[0] + 1} of {pl_[1]} · {self.playlist['nome']}" if pl_ else ""))
        self.disegna_board()
        f.lift(); f.focus_force()
        return f

    def passo_board(self, d):
        b = getattr(self, "_board", None)
        if b:
            self._anima = d == 1        # un passo avanti: le carte scorrono da dove erano (anima_board)
            self.vai_board(b["i"] + d)

    def vai_board(self, i):
        b = getattr(self, "_board", None)
        if b:
            b["i"] = max(0, min(len(b["passi"]) - 1, i))
            self.disegna_board()

    def play_board(self):
        """Play: un momento ogni PASSO_PLAY (3,2 s dal 14 nov 2026, era 1,6) diviso la velocita' (attesa_play); arrivato in fondo si ferma. Play in fondo
        riparte dall'inizio."""
        b = getattr(self, "_board", None)
        if not b:
            return
        if b["play"]:
            self.ferma_board()
            self.disegna_controlli()
            return
        if b["i"] >= len(b["passi"]) - 1:
            b["i"] = 0
        b["play"] = True
        self.disegna_board()
        self._play_id = self.fin_board.after(self.attesa_play(), self.giro_board)

    def giro_board(self):
        b = getattr(self, "_board", None)
        f = getattr(self, "fin_board", None)
        if not b or not b["play"] or f is None or not f.winfo_exists():
            return
        if b["i"] >= len(b["passi"]) - 1:
            self.ferma_board()
            self.disegna_controlli()
            return
        b["i"] += 1
        self._anima = True
        self.disegna_board()
        self._play_id = f.after(self.attesa_play(), self.giro_board)

    def attesa_play(self):
        """Quanto resta il passo prima del prossimo, in play (14 nov 2026, Autore: «ancora troppe azioni in sormonto, fai passare tempo tra le
        dichiarazioni attacchi e le dichiarazioni difensori»): almeno 1,6 s diviso la velocita', mai prima che i voli del passo siano finiti (piu' mezzo
        secondo per guardare dove sono arrivati), e dopo la dichiarazione degli attaccanti (il combattimento senza blocchi ancora) un secondo in piu' prima
        dei bloccanti."""
        b = self._board
        ms = int(self.PASSO_PLAY / b["vel"])
        ms = max(ms, getattr(self, "_durata_anim", 0) + int(800 / b["vel"]))      # «tutto piu' lento» (14 nov 2026): era mezzo secondo; dal 18 nov segue la velocita'
        rel = b["passi"][b["i"]][3] if b["passi"] else None
        if rel and rel.get("tipo") == "comb" and not rel.get("blocchi"):
            ms += int(self.ATTESA_ATTACCO / b["vel"])
        if rel and rel.get("tipo") == "spell":      # la magia in pila: il tempo di vederla arrivare, poi la freccia, prima che si risolva
            ms = max(ms, getattr(self, "_durata_anim", 0) + PAUSA_FRECCIA + int(self.ATTESA_MAGIA / b["vel"]))
        return ms

    def ferma_board(self):
        b = getattr(self, "_board", None)
        if b:
            b["play"] = False
        pid, f = getattr(self, "_play_id", None), getattr(self, "fin_board", None)
        if pid and f is not None:
            try:
                f.after_cancel(pid)
            except Exception:      # noqa: BLE001 - gia' scattato
                pass
        self._play_id = None

    def disegna_controlli(self):
        """La barra del replayer. Sopra, il grafico della partita sulla stessa x della timeline: le vite (tu azzurro, l'avversario arancio), sotto la forza in
        campo dei due a barre, la stella sul punto di svolta, la riga del momento; sotto i pulsanti disegnati (nitidi), la timeline coi momenti, il momento, il
        punto di svolta e la velocita'."""
        c = getattr(self, "cv_ctrl", None)
        b = getattr(self, "_board", None)
        if c is None or not c.winfo_exists() or not b:
            return
        F = self.F
        c.delete("all")
        W, H = max(c.winfo_width(), 800), ALTO_CTRL
        cy = ALTO_GRAF + (H - ALTO_GRAF) / 2
        sopra = getattr(self, "_ctrl_sopra", None)
        # la parte ferma (pulsanti, grafico, timeline coi pallini, velocita') si disegna nitida una volta sola; a ogni passo si muovono solo la riga del
        # momento, il riempimento della timeline, i pallini passati e il cursore (12 nov 2026: un passo da 119 ms, quasi tutti qui, a pochi ms)
        chiave = (W, id(b["passi"]), b.get("svolta"), b["play"], sopra, b["vel"], getattr(self, "_chi_chiave", "both"))
        rifai = chiave != getattr(self, "_chiave_ctrl", None)
        d = DG.Disegno(W, H) if rifai else _Nulla()
        bianco, grigio = "#e6e6ea", "#9a9aa2"
        self._box_ctrl = []
        x = 22
        for k in ("primo", "indietro", "play", "avanti", "ultimo"):
            r = 20 if k == "play" else 15
            cx = x + r
            on = sopra == k
            if k == "play":
                d.cerchio(cx, cy, r, riempi="#2ba3ea" if on else "#0f86cc")
            else:
                d.cerchio(cx, cy, r, riempi="#262c37" if on else "#1a202b", bordo="#2c3340", larghezza=1)
            col = "#ffffff" if k == "play" else (bianco if on else grigio)
            if k == "play" and b["play"]:
                d.rett(cx - 6, cy - 7, cx - 2, cy + 7, riempi=col, raggio=1)
                d.rett(cx + 2, cy - 7, cx + 6, cy + 7, riempi=col, raggio=1)
            elif k == "play":
                d.poligono([(cx - 5, cy - 8), (cx + 8, cy), (cx - 5, cy + 8)], riempi=col)
            elif k == "indietro":
                d.poligono([(cx + 4, cy - 6), (cx - 5, cy), (cx + 4, cy + 6)], riempi=col)
            elif k == "avanti":
                d.poligono([(cx - 4, cy - 6), (cx + 5, cy), (cx - 4, cy + 6)], riempi=col)
            elif k == "primo":
                d.rett(cx - 6, cy - 6, cx - 4, cy + 6, riempi=col)
                d.poligono([(cx + 5, cy - 6), (cx - 3, cy), (cx + 5, cy + 6)], riempi=col)
            else:
                d.rett(cx + 4, cy - 6, cx + 6, cy + 6, riempi=col)
                d.poligono([(cx - 5, cy - 6), (cx + 3, cy), (cx - 5, cy + 6)], riempi=col)
            self._box_ctrl.append((cx - r, cx + r, k))
            x += 2 * r + 10
        # la timeline, e sopra il grafico della partita sulla stessa x
        t0, t1 = x + 20, W - 330
        n = len(b["passi"])
        self._timeline = (t0, t1, n)
        pos = lambda i: t0 + (t1 - t0) * (i / max(1, n - 1))
        m = self.momenti(b["passi"])
        sv = b.get("svolta")
        g0, g1 = 14, ALTO_GRAF - 30          # la fascia delle vite
        f0, f1 = ALTO_GRAF - 26, ALTO_GRAF - 4   # la fascia della forza
        vmax = max([20] + [max(z["vite"]) for z in m])
        vmin = min([0] + [min(z["vite"]) for z in m])
        sy = lambda v: g1 - (v - vmin) / max(1, vmax - vmin) * (g1 - g0)
        d.linea([(t0, sy(20)), (t1, sy(20))], "#2a2a32", 1)
        if vmin < 0:
            d.linea([(t0, sy(0)), (t1, sy(0))], "#2c3340", 1)
        fmax = max([1] + [max(z["forza"]) for z in m])
        larga_b = max(2, min(10, (t1 - t0) / max(1, n) / 3))
        for i, z in enumerate(m):
            # mai sotto zero (23 nov 2026: una forza negativa, i segnalini -1/-1, rovesciava la barretta e il disegno cadeva, timeline compresa)
            hm, hs = max(0, z["forza"][0]) / fmax * (f1 - f0), max(0, z["forza"][1]) / fmax * (f1 - f0)
            if hm:
                d.rett(pos(i) - larga_b - 0.5, f1 - hm, pos(i) - 0.5, f1, riempi=(36, 186, 255, 150))
            if hs:
                d.rett(pos(i) + 0.5, f1 - hs, pos(i) + larga_b + 0.5, f1, riempi=(240, 173, 78, 150))
        curva = self.curva_p(b)
        if curva:
            # la probabilita' di vincere (18 nov 2026): 0-100, la riga del 50%, ogni tratto verde dove il turno e' andato meglio del solito, rosso dove e'
            # andato peggio, grigio dentro SOGLIA_PARLA; al posto delle vite (che stanno gia' sul tappeto)
            py_ = lambda v: g1 - max(0.0, min(100.0, v)) / 100.0 * (g1 - g0)
            for xx_ in range(int(t0), int(t1), 8):
                d.linea([(xx_, py_(50)), (min(xx_ + 4, t1), py_(50))], "#3a4150", 1)
            for (i_a, p_a, _s), (i_b, p_b, s_b) in zip(curva, curva[1:]):
                col_ = "#5cb85c" if (s_b or 0) >= self.SOGLIA_PARLA else "#ff5d5d" if (s_b or 0) <= -self.SOGLIA_PARLA else "#9aa3b2"
                d.linea([(pos(i_a), py_(p_a)), (pos(i_b), py_(p_b))], col_, 2.2)
            for i_c, p_c, s_c in curva:
                d.cerchio(pos(i_c), py_(p_c), 2.2, riempi="#e6e6ea")
        elif n > 1:
            d.linea([(pos(i), sy(z["vite"][1])) for i, z in enumerate(m)], "#f0ad4e", 1.6)
            d.linea([(pos(i), sy(z["vite"][0])) for i, z in enumerate(m)], "#2f9bff", 1.8)
        if sv is not None:      # la stella del punto di svolta
            import math as _m
            sx_, sy_ = pos(sv), 10
            pts = [(sx_ + (7 if j % 2 == 0 else 3) * _m.cos(-_m.pi / 2 + j * _m.pi / 5), sy_ + (7 if j % 2 == 0 else 3) * _m.sin(-_m.pi / 2 + j * _m.pi / 5))
                   for j in range(10)]
            d.poligono(pts, riempi="#ffd23f")
        d.linea([(0, ALTO_GRAF), (W, ALTO_GRAF)], "#1d222b", 1)
        d.linea([(t0, cy), (t1, cy)], "#2c3340", 4)
        chiave_i = self.chiave_passi(b)
        for i, p_ in enumerate(b["passi"]):
            nome = p_[0]
            mio_ = nome.startswith("You") or nome == "Opening hand"
            d.cerchio(pos(i), cy, 3.2 if n <= 60 else 1.6, riempi="#2f9bff" if mio_ else "#7a8394")
            if i in chiave_i:   # un momento chiave (R7): il rombo sopra, azzurro se il vantaggio sale per te, arancio se per lui
                col_k = "#2f9bff" if chiave_i[i] > 0 else "#f0ad4e"
                d.poligono([(pos(i), cy - 15), (pos(i) + 5, cy - 10), (pos(i), cy - 5), (pos(i) - 5, cy - 10)], riempi=col_k)
            # i leak non sono piu' segni sulla timeline (18 nov 2026, il lettore di EV): restano come spiegazione nel racconto e col salto «Leak ›»
            if i == sv:
                d.cerchio(pos(i), cy, 5.5, bordo="#ffd23f", larghezza=1.6)
        # il punto di svolta e la velocita'
        self._box_vel, self._box_svolta = [], None
        vx = W - 196
        for v in VELOCITA:
            on = abs(b["vel"] - v) < 1e-9
            d.rett(vx, cy - 12, vx + 42, cy + 12, riempi="#0f86cc" if on else "#1a202b", bordo="#0f86cc" if on else "#2c3340", larghezza=1, raggio=4)
            self._box_vel.append((vx, vx + 42, v))
            vx += 46
        if sv is not None:
            d.rett(W - 150, 8, W - 12, 32, riempi="#2a2416", bordo="#ffd23f", larghezza=1, raggio=4)
            self._box_svolta = (W - 150, 8, W - 12, 32)
        if rifai:
            self._img_ctrl, self._chiave_ctrl = d.foto(), chiave
        c.create_image(0, 0, image=self._img_ctrl, anchor="nw")
        # la parte che si muove
        xi = pos(b["i"])
        c.create_line(xi, 6, xi, ALTO_GRAF - 2, fill="#ffffff")
        c.create_line(t0, cy, xi, cy, fill="#0f86cc", width=4, capstyle="round")
        punto_ = DG.punto(round(2 * (3.2 if n <= 60 else 1.6)) + 1, "#ffffff")
        for j in range(b["i"]):
            c.create_image(pos(j), cy, image=punto_)
        c.create_image(xi, cy, image=DG.punto(17, "#ffffff", "#0f86cc", 2))
        for s_ in DA.segnalibri():      # gli spot segnati di questa partita in questo modo: un segno d'oro sopra la timeline
            if s_.get("partita") == b["x"].get("partita") and s_.get("modo") == b.get("modo", "momenti") and 0 <= (s_.get("i") if s_.get("i") is not None else -1) < n:       # il segno fatto dal vivo (★ MARK) ha solo il turno
                xs_ = pos(s_["i"])
                c.create_polygon(xs_ - 5, cy - 20, xs_ + 5, cy - 20, xs_ + 5, cy - 9, xs_, cy - 13, xs_ - 5, cy - 9, fill="#ffd23f", outline="")
        im_f = DG.spot_filtro(12, SEGNO_FILTRO, "#ffffff")
        for i_f in self.filtro_passi(b):        # gli spot dei filtri accesi (15 nov 2026): il quadratino blu con l'imbuto bianco, col beccuccio verso il passo,
            c.create_image(pos(i_f), cy + 15, image=im_f, anchor="n", tags=("spot_filtro",))       # sotto i triangolini dei leak
        c.create_text(t0 - 10, sy(m[0]["vite"][0]) if m else 20, text="LIFE", anchor="e", fill=grigio, font=F(6, True))
        c.create_text(t0 - 10, (f0 + f1) / 2, text="POWER", anchor="e", fill=grigio, font=F(6, True))
        if m:
            z = m[b["i"]]
            c.create_text(t1 + 14, 20, text=f"you {z['vite'][0]}", anchor="w", fill="#2f9bff", font=F(8, True))
            c.create_text(t1 + 14, 36, text=f"opponent {z['vite'][1]}", anchor="w", fill="#f0ad4e", font=F(8, True))
            c.create_text(t1 + 14, (f0 + f1) / 2 + 2, text=f"power {z['forza'][0]} vs {z['forza'][1]}", anchor="w", fill=grigio, font=F(7))
        if sv is not None:
            c.create_text(W - 81, 20, text="★ Turning point", fill="#ffd23f", font=F(7, True))
        for x0_, x1_, v in self._box_vel:
            on = abs(b["vel"] - v) < 1e-9
            c.create_text((x0_ + x1_) / 2, cy, text=("0.5×" if v == 0.5 else f"{v:.0f}×"), fill="#ffffff" if on else grigio, font=F(7, True))
        # il nome del passo nel suo spazio fra la timeline e la velocita', sotto «N / M» (14 nov 2026, Autore: «in basso a dx testi si sovrappongono»: il
        # nome lungo e la riga dei tasti andavano sopra la fine della timeline)
        nome = b["passi"][b["i"]][0] + ("   ★" if b["i"] == sv else "")
        import tkinter.font as _tkf
        f9_ = _tkf.Font(font=F(9, True))
        spazio_ = (W - 212) - (t1 + 12)
        while f9_.measure(nome) > spazio_ and len(nome) > 4:
            nome = nome[:-2].rstrip() + "…"
        c.create_text(W - 212, cy - 7, text=nome, anchor="e", fill=bianco, font=F(9, True))
        c.create_text(W - 212, cy + 10, text=f"{b['i'] + 1} / {n}", anchor="e", fill=grigio, font=F(7))
        if self.curva_p(b) and not getattr(self, "_graf_chiuso", False):     # la curva e' la probabilita' di vincere: lo dice una scritta
            c.create_text(t0 + 4, 4, text="YOUR CHANCE TO WIN · 50% dotted · green better than usual, red worse", anchor="nw", fill=grigio, font=F(7, True))
        # col grafico chiuso la tela si abbassa all'altezza dei comandi e mostra solo la loro riga (la linguetta HIDE CHART, 14 nov 2026)
        chiuso_ = getattr(self, "_graf_chiuso", False)
        c.configure(scrollregion=(0, 0, W, ALTO_CTRL))
        if int(float(c.cget("height"))) != (ALTO_CTRL - ALTO_GRAF if chiuso_ else ALTO_CTRL):
            c.configure(height=ALTO_CTRL - ALTO_GRAF if chiuso_ else ALTO_CTRL)
        c.yview_moveto(ALTO_GRAF / ALTO_CTRL if chiuso_ else 0)

    def clic_controlli(self, e):
        b = getattr(self, "_board", None)
        if not b:
            return
        e.y = int(self.cv_ctrl.canvasy(e.y))        # col grafico chiuso la tela e' scorsa in basso
        if self._box_svolta and self._box_svolta[0] <= e.x <= self._box_svolta[2] and self._box_svolta[1] <= e.y <= self._box_svolta[3]:
            self.ferma_board()
            self.vai_board(b["svolta"])
            return
        if e.y >= ALTO_GRAF:
            for x0, x1, k in getattr(self, "_box_ctrl", []):
                if x0 <= e.x <= x1:
                    if k == "play":
                        self.play_board()
                    else:
                        self.ferma_board()
                        {"primo": lambda: self.vai_board(0), "indietro": lambda: self.passo_board(-1), "avanti": lambda: self.passo_board(1),
                         "ultimo": lambda: self.vai_board(10 ** 6)}[k]()
                    return
            for x0, x1, v in getattr(self, "_box_vel", []):
                if x0 <= e.x <= x1:
                    b["vel"] = self._vel_board = v
                    self.disegna_controlli()
                    return
        self.trascina_timeline(e)       # la timeline, o il grafico sopra di lei: il momento piu' vicino

    def trascina_timeline(self, e):
        """Clic o trascinamento sulla timeline (o sul grafico sopra): il momento piu' vicino."""
        t0, t1, n = getattr(self, "_timeline", (0, 0, 0))
        if n and t0 - 12 <= e.x <= t1 + 12:
            i = round((min(max(e.x, t0), t1) - t0) / max(1, t1 - t0) * (n - 1))
            if i != self._board["i"]:
                self.ferma_board()
                self.vai_board(i)

    def cambia_modo_board(self, modo, ridisegna=True):
        """Moments (i momenti di sempre) o Every action (replay_log: ogni azione). Si resta sullo stesso turno."""
        b = getattr(self, "_board", None)
        if not b:
            return
        if modo == "azioni":
            if b.get("azioni_passi") is None:
                b["azioni_passi"] = DA.azioni_partita(b["x"]) or []
            nuovi = b["azioni_passi"]
            if not nuovi:       # senza log non c'e' il replay azione per azione: si resta sui momenti
                modo, nuovi = "momenti", b["momenti_passi"]
        else:
            nuovi = b["momenti_passi"]
        t_ora = b["passi"][b["i"]][2] if b["passi"] else 0
        self.ferma_board()
        b["modo"], b["passi"] = modo, nuovi
        self._modo_board = modo
        dentro = [i for i, p_ in enumerate(nuovi) if p_[2] <= t_ora]
        b["i"] = dentro[-1] if dentro else 0
        b["svolta"] = self.svolta(nuovi, b["x"]["vinta"])
        for k_, b_ in getattr(self, "b_modi", {}).items():
            b_.metti({"azioni": "Every action", "momenti": "Moments"}[k_], k_ == modo)
        if ridisegna:
            self.disegna_board()

    def tappato(self, f):
        """L'avversario e' tappato: tutte le sue terre (almeno 2) tappate."""
        import mazzi_salvati as MS
        terre = [c_ for c_ in f["suo"] if MS.e_terra(c_[0])]
        return len(terre) >= 2 and all(c_[1] for c_ in terre)

    def salta(self, k, d=1):
        """Il prossimo (d=1) o il precedente (d=-1) combattimento, magia, o momento in cui l'avversario resta tappato (il primo di ogni tratto)."""
        b = getattr(self, "_board", None)
        if not b:
            return None
        ps = b["passi"]
        if k == "comb":
            ok = lambda i: bool(ps[i][3]) and ps[i][3]["tipo"] == "comb"
        elif k == "spell":
            ok = lambda i: bool(ps[i][3]) and ps[i][3]["tipo"] == "spell"
        elif k == "leak":
            ok = lambda i: i in self.leak_passi(b)
        elif k == "filtro":
            ok = lambda i: i in self.filtro_passi(b)
        elif k == "chiave":
            ok = lambda i: i in self.chiave_passi(b)
        else:
            ok = lambda i: self.tappato(ps[i][1]) and not (i > 0 and self.tappato(ps[i - 1][1]))
        i = b["i"] + d
        while 0 <= i < len(ps):
            if ok(i):
                self.ferma_board()
                self.vai_board(i)
                return i
            i += d
        # R15: in fondo alla partita, la playlist continua nella partita dopo (o prima), fino a trovarne uno; al massimo GIRO_PLAYLIST partite
        if self.playlist and not getattr(self, "_in_giro", False):
            x0_, i0_ = b["x"], b["i"]
            self._in_giro = True
            try:
                for _n in range(self.GIRO_PLAYLIST):
                    x_ = self.gioco_playlist(d, vai=False)
                    if x_ is None:
                        break
                    b2 = self._board
                    b2["i"] = -1 if d > 0 else len(b2["passi"])
                    trovato = self.salta(k, d)
                    if trovato is not None:
                        return trovato
            finally:
                self._in_giro = False
            if self._board.get("x") is not x0_:      # nessuno nelle partite dopo: si torna dove si era
                self.apri_board(x0_)
                self.vai_board(i0_)
        return None

    GIRO_PLAYLIST = 40

    def posto_playlist(self, x_):
        """(indice, quante) della partita x_ nella playlist, o None."""
        pl = self.playlist
        if not pl:
            return None
        i = next((i for i, y in enumerate(pl["partite"]) if y is x_ or y.get("partita") == x_.get("partita")), None)
        return None if i is None else (i, len(pl["partite"]))

    def apri_playlist(self, partite, nome, k=None):
        """R14 e R15: dai numeri alle loro partite. Le partite si guardano una dopo l'altra nel replayer (◀ Game, Game ▶, tasti P e N); con k (comb, spell,
        leak, chiave, tappato) si apre sul primo di quel tipo, e i salti continuano partita dopo partita. Le partite senza la tavola si saltano.
        -> l'indice del passo, o None se nessuna partita si apre."""
        self.playlist = dict(partite=list(partite), nome=nome)
        for x_ in self.playlist["partite"]:
            self.apri_board(x_, "inizio")
            b = getattr(self, "_board", None)
            if b and b.get("x") is x_:
                if k:
                    b["i"] = -1
                    trovato = self.salta(k, 1)
                    if trovato is None:
                        self.vai_board(0)
                    return trovato if trovato is not None else 0
                return b["i"]
        return None

    def gioco_playlist(self, d=1, vai=True):
        """La partita dopo (d=1) o prima (-1) nella playlist, saltando quelle senza la tavola; vai: dall'inizio (la mano tenuta). -> la partita o None."""
        b = getattr(self, "_board", None)
        if not b or not self.playlist:
            return None
        pos = self.posto_playlist(b["x"])
        ps = self.playlist["partite"]
        j = (pos[0] if pos else -1) + d
        while 0 <= j < len(ps):
            self.apri_board(ps[j], "inizio")
            b2 = getattr(self, "_board", None)
            if b2 and b2.get("x") is ps[j]:
                if vai:
                    i_f = self.primo_spot(b2)
                    self.vai_board(0 if i_f is None else i_f)
                return ps[j]
            j += d
        return None

    CHI_CHIAVE = (("both", "Keys: both"), ("mine", "Keys: yours"), ("theirs", "Keys: theirs"))
    PIU_CHIAVE, SOGLIA_CHIAVE = 5, 6

    def ev_turno_passo(self, b):
        """Il turno del passo aperto nel replayer col suo EV contro il solito (ev_partita: il solito dello stesso mazzo, DA.chiave_mazzo), o None."""
        try:
            import ev_partita as EV_
            t = b["passi"][b["i"]][2]
            x = b["x"]
            base = [y for y in self.righe or [] if y["tipo"] == x.get("tipo")]
            return EV_._mappa_turni(base).get((x.get("partita"), t))
        except Exception:       # noqa: BLE001 - un passo senza turno o una partita senza conto: niente riga
            return None

    def chiave_passi(self, b):
        """R7, i momenti chiave (13 nov 2026, come i momenti chiave di chess.com): i passi dove il vantaggio (vite di differenza piu' due volte la forza in
        campo di differenza, come il punto di svolta) cambia di piu' rispetto al passo prima, al massimo PIU_CHIAVE e di almeno SOGLIA_CHIAVE; R16: solo i
        tuoi (il vantaggio sale per te), solo i suoi, o tutti e due. -> {indice: salto}. Il punto di svolta ★ resta il primo."""
        chi = getattr(self, "_chi_chiave", "both")
        k_ = (id(b["passi"]), chi)
        if b.get("_chiave_k") == k_:
            return b["_chiave_i"]
        ev_ = self.chiave_ev(b, chi)
        if ev_ is not None:         # il lettore di EV (18 nov 2026): i momenti chiave sono le fasi con lo scarto di EV piu' grande
            b["_chiave_k"], b["_chiave_i"] = k_, ev_
            return ev_
        m = self.momenti(b["passi"])
        salti = [(i, m[i]["vantaggio"] - m[i - 1]["vantaggio"]) for i in range(1, len(m))]
        salti = [(i, d) for i, d in salti if abs(d) >= self.SOGLIA_CHIAVE and (chi == "both" or (d > 0) == (chi == "mine"))]
        out = dict(sorted(sorted(salti, key=lambda z: -abs(z[1]))[:self.PIU_CHIAVE]))
        b["_chiave_k"], b["_chiave_i"] = k_, out
        return out

    SOGLIA_EV = 5.0         # una fase e' un momento chiave da 5 punti di P sopra o sotto il solito

    def chiave_ev(self, b, chi="both"):
        """I momenti chiave dall'EV (18 nov 2026, Autore: «nei replayer quindi non vogliamo piu' i punti di leak ma i punti salienti di ev value»): le fasi
        della partita (prima principale, combattimento, seconda, dell'Hero e dell'Opponent) con lo scarto dal solito piu' grande, al massimo PIU_CHIAVE e
        di almeno SOGLIA_EV punti di P; ognuna sul primo passo di quella fase nel replayer. -> {indice: scarto} (positivo: per l'Hero), o None senza il conto
        della partita (si torna al vantaggio)."""
        import ev_partita as EV_
        x_ = b["x"]
        base = [y for y in self.righe or [] if y["tipo"] == x_.get("tipo")]
        mappa = EV_._mappa_turni(base)
        turni = [z for (pp, _t), z in sorted(mappa.items(), key=lambda kv: kv[0][1]) if pp == x_.get("partita")]
        if not turni:
            return None
        fasi = [(z["t"], ph["f"], ph["scarto"]) for z in turni for ph in z.get("fasi") or [] if ph["f"] != "inizio"]       # il cambio di chi tocca: di nessuno
        fasi = [f_ for f_ in fasi if abs(f_[2]) >= self.SOGLIA_EV and (chi == "both" or (f_[2] > 0) == (chi == "mine"))]
        ps = b["passi"]

        def passo(t, f):
            del_t = [i for i, p_ in enumerate(ps) if p_[2] == t]
            if not del_t:
                return None
            nomi = [(i, (ps[i][0] or "").lower()) for i in del_t]
            comb_ = lambda n_: any(w in n_ for w in ("combat", "attack", "block", "damage"))
            # ogni fase sul suo passo: due fasi diverse non finiscono mai sullo stesso passo (una fase senza un passo suo non ha il rombo)
            if f == "comb":
                return next((i for i, n_ in nomi if comb_(n_)), None)
            if f == "main2":
                return next((i for i, n_ in nomi if "main2" in n_ or n_.split("·")[-1].strip() in ("end", "end of turn")), None) or                     next((i for i, n_ in reversed(nomi) if not comb_(n_)), None)
            return next((i for i, n_ in nomi if not comb_(n_)), None)
        out = {}
        for t, f, sc in sorted(fasi, key=lambda f_: -abs(f_[2]))[:self.PIU_CHIAVE]:
            i = passo(t, f)
            if i is not None and i not in out:
                out[i] = sc
        return dict(sorted(out.items()))

    SOGLIA_PARLA = 3.0      # il racconto parla dell'EV solo da 3 punti di P sopra o sotto il solito (18 nov 2026, «parlare solo quando conta»)

    # il voto EV di ogni fase (19 nov 2026, Autore: «i voti EV li diamo alla fine di ogni fase: un voto per ogni cosa accaduta piu' i pti guadagnati dagli
    # errori di oppo ... ogni voto cliccabile per andare al punto esatto della fase»): le etichette col loro colore, di chi e' il merito o il regalo
    COLORI_VOTO = {"mio_su": "verde", "mio_giu": "rosso", "mio_pari": "muto", "suo_errore": "verde", "suo_buono": "rosso", "suo_pari": "muto",
                   "risultato": "muto"}

    def voto_fase(self, b):
        """La fase del passo aperto col suo voto (ev_partita.righe_fasi), in Every action: dict(fase, righe fino al passo aperto, finita) o None."""
        import ev_partita as EV_
        x_ = b["x"]
        base = [y for y in self.righe or [] if y["tipo"] == x_.get("tipo")]
        v = EV_.righe_fasi(x_, b["passi"], base)
        if not v:
            return None
        ch = v["del_passo"].get(b["i"])
        if ch is None:      # un passo senza foto (l'inizio della partita): la fase dopo, se c'e'
            return None
        fz = next((f_ for f_ in v["fasi"] if f_["chiave"] == ch), None)
        if fz is None:
            return None
        return dict(fase=fz, righe=[r_ for r_ in fz["righe"] if r_["i"] <= b["i"]], finita=b["i"] >= fz["ultimo"])

    def disegna_win_chance(self, cc, b, x0, larga, y):
        """In testa al racconto la probabilita' di vincere adesso, tua contro la sua (19 nov 2026, Autore: «dovremmo avere un totale di wr mio vs oppo per
        capire meglio l'andamento ... mettiamo in testa win chance»): la barra (tu a sinistra in verde, l'Opponent in arancio), e la partenza della partita.
        La stessa lettura del voto: «se il turno finisse qui». Il passo zero (prima del primo turno) e un passo senza foto: la partenza."""
        import ev_partita as EV_
        x_ = b["x"]
        base = [z for z in self.righe or [] if z["tipo"] == x_.get("tipo")]
        v = EV_.righe_fasi(x_, b["passi"], base) if b.get("modo") == "azioni" else None
        cp = EV_.partita(x_)
        p0 = cp["inizio"] if cp else None
        pp = (v or {}).get("p_passo") or {}
        p = next((pp[i] for i in range(b["i"], -1, -1) if i in pp), p0)
        if p is None:
            return y
        F = self.F
        cc.create_rectangle(x0 + 12, y + 1, x0 + 14, y + 13, fill=C["accento"], outline="")
        cc.create_text(x0 + 19, y, text="WIN CHANCE · NOW", anchor="nw", fill=C["titolo"], font=F(8, True))
        y += 18
        W_ = larga - 28
        xm = x0 + 14 + W_ * max(0.0, min(100.0, p)) / 100
        cc.create_rectangle(x0 + 14, y, xm, y + 20, fill="#1c4d38", outline="")
        cc.create_rectangle(xm, y, x0 + 14 + W_, y + 20, fill="#4a2f12", outline="")
        cc.create_text(x0 + 20, y + 10, text=f"YOU {p:.0f}%", anchor="w", fill=C["verde"], font=F(9, True))
        cc.create_text(x0 + 8 + W_, y + 10, text=f"{100 - p:.0f}% OPPONENT", anchor="e", fill=C["arancio"], font=F(9, True))
        y += 24
        if p0 is not None:
            d_ = p - p0
            sol_ = self.mano_solita(x_)
            if sol_ is not None:        # la mano tenuta e' la prima occasione della partita (occasioni.py): contro la mano media dello stesso mazzo
                d_m = p0 - sol_
                cc.create_text(x0 + 14, y, text=f"hand you kept {p0:.0f}% · your deck's usual {sol_:.0f}%", anchor="nw", fill=C["muto"], font=F(7))
                cc.create_text(x0 + larga - 14, y - 1, text=f"{d_m:+.1f}".replace("-", "−"), anchor="ne",
                               fill=C["verde"] if d_m >= 1 else C["rosso"] if d_m <= -1 else C["muto"], font=F(8, True))
                y += 16
            cc.create_text(x0 + 14, y, text=f"start of the game {p0:.0f}% · since then", anchor="nw", fill=C["muto"], font=F(7))
            cc.create_text(x0 + larga - 14, y - 1, text=f"{d_:+.1f}".replace("-", "−"), anchor="ne", fill=C["verde"] if d_ >= 1 else C["rosso"] if d_ <= -1 else C["muto"],
                           font=F(8, True))
            y += 16
        y = self.disegna_orologio(cc, b, x0, larga, y)
        return y + 8

    def disegna_orologio(self, cc, b, x0, larga, y):
        """Sotto la WIN CHANCE l'orologio (22 nov 2026, Autore: «Sì, mettilo»): perche' il tavolo vale quello che vale, in turni. La tua forza in campo
        contro le sue vite, la sua contro le tue, le carte in mano. Non cambia il numero: lo spiega (Note/Gerarchie_Valore.md, l'equity come corsa)."""
        import ev_partita as EV_
        passi = b.get("passi") or []
        i = min(b.get("i") or 0, len(passi) - 1) if passi else -1
        f_ = (passi[i][1] or {}).get("_grezza") if i >= 0 else None
        o = EV_.orologio(f_, b["x"].get("seat"))
        if not o:
            return y
        F = self.F

        def frase(t, forza, vite):
            if t == 0:
                return "already at 0 life"
            if t is None:
                return f"no clock yet ({forza} power vs {vite} life)" if forza <= 0 else f"over {EV_.TETTO_OROLOGIO} turns ({forza} power vs {vite} life)"
            return f"{t} turn{'s' if t != 1 else ''} ({forza} power vs {vite} life)"
        cc.create_text(x0 + 14, y + 2, text="CLOCK", anchor="nw", fill=C["titolo"], font=F(7, True))
        y += 15
        tm, ts = o["turni_mie"], o["turni_suoi"]
        col_m = C["verde"] if tm is not None and (ts is None or tm < ts) else C["testo"]
        col_s = C["arancio"] if ts is not None and (tm is None or ts < tm) else C["testo"]
        cc.create_text(x0 + 14, y, text=f"Hero kills the Opponent in {frase(tm, o['forza_mia'], o['vite_sue'])}", anchor="nw", fill=col_m, font=F(7),
                       width=larga - 28)
        y += 15
        cc.create_text(x0 + 14, y, text=f"The Opponent kills Hero in {frase(ts, o['forza_sua'], o['vite_mie'])}", anchor="nw", fill=col_s, font=F(7),
                       width=larga - 28)
        y += 15
        cc.create_text(x0 + 14, y, text=f"creatures: Opponent {o['bloccanti_suoi']}, Hero {o['bloccanti_miei']} · cards in hand: Opponent {o['mano_sua']}, Hero {o['mano_mia']}",
                       anchor="nw", fill=C["muto"], font=F(7), width=larga - 28)
        return y + 16

    def range_avversario(self, b):
        """Il range della mano dell'Opponent a fine di ogni suo mezzo turno e del tuo (Motore_EV/range_nucleo.range_partita), solo nel Limited, una volta per
        partita; None fuori dal Limited o senza il modello e la base del set (21 nov 2026, Autore: «montiamo ogni miglioria», per il range «Sì, solo
        Limited»: nel Constructed non e' misurato)."""
        x_ = b["x"]
        if x_.get("tipo") != "Limited":
            return None
        k_ = (x_.get("partita"),)
        if b.get("_range_k") != k_:
            try:
                import sys as _s
                cart = os.path.join(DA.percorsi.ROOT, "Motore_EV")
                if cart not in _s.path:
                    _s.path.insert(0, cart)
                import range_nucleo as RN_
                b["_range"] = RN_.range_partita(x_)
            except Exception:       # noqa: BLE001 - senza il modello o la base del set: niente range
                b["_range"] = None
            b["_range_k"] = k_
        return b["_range"]

    def disegna_range(self, cc, b, x0, larga, y):
        """Sotto la WIN CHANCE, nel Limited: la probabilita' che l'Opponent abbia in mano almeno una carta di ogni tipo, alla fine dell'ultimo mezzo turno
        chiuso prima del passo aperto (Note/Motore_EV_Range.md). Una stima dai replay di 17Lands, non la sua mano."""
        rr = self.range_avversario(b)
        if not rr:
            return y
        try:
            t_cur = b["passi"][b["i"]][2]
        except (IndexError, KeyError, TypeError):
            return y
        z = None
        for q in rr:
            if q["t"] is not None and t_cur is not None and q["t"] < t_cur:
                z = q
        if z is None:
            return y
        import range_nucleo as RN_
        F = self.F
        chi = "your" if z["mio"] else "Opponent's"
        cc.create_rectangle(x0 + 12, y + 1, x0 + 14, y + 13, fill=C["accento"], outline="")
        cc.create_text(x0 + 19, y, text="OPPONENT'S HAND · RANGE", anchor="nw", fill=C["titolo"], font=F(8, True))
        cc.create_text(x0 + larga - 14, y + 1, text=f"{z['H']} cards · end of {chi} T{z['N']}", anchor="ne", fill=C["muto"], font=F(7))
        y += 18
        W_ = larga - 28
        xb = x0 + 14 + int(W_ * 0.55)
        for k, et in RN_.ETICHETTE:
            v = z["p"].get(k)
            if v is None:
                continue
            cc.create_text(x0 + 14, y + 6, text=f"has {et}", anchor="w", fill=C["testo"], font=F(7))
            cc.create_rectangle(xb, y + 2, x0 + 14 + W_ - 40, y + 10, fill="#1b2130", outline="")
            cc.create_rectangle(xb, y + 2, xb + (x0 + 14 + W_ - 40 - xb) * max(0.0, min(1.0, v)), y + 10, fill=C["accento"], outline="")
            cc.create_text(x0 + larga - 14, y + 6, text=f"{100 * v:.0f}%", anchor="e", fill=C["titolo"], font=F(7, True))
            y += 14
        i_n = cc.create_text(x0 + 14, y + 2, text="A guess learned from 17Lands replays (CC BY 4.0), Limited only: never his real hand.", anchor="nw",
                             fill=C["grigio"], font=F(6), width=larga - 28)
        return (cc.bbox(i_n) or (0, 0, 0, y + 14))[3] + 10      # la nota puo' andare a capo: quello che viene dopo parte sotto di lei

    def mano_solita(self, x_):
        """La P media della mano tenuta nelle partite dello stesso mazzo (DA.chiave_mazzo, lascia-una-fuori come occasioni.con_occasioni), o None sotto
        DA.MINIMO_MAZZO partite col conto."""
        import ev_partita as EV_
        k_ = DA.chiave_mazzo(x_)
        cache = getattr(self, "_mani_solite", None)
        if cache is None or cache[0] is not self.righe:
            cache = self._mani_solite = (self.righe, {})
        if k_ not in cache[1]:
            vv = []
            for y_ in self.righe or []:
                if DA.chiave_mazzo(y_) == k_:
                    c_ = EV_.partita(y_)
                    if c_ is not None:
                        vv.append((y_.get("partita"), c_["inizio"]))
            cache[1][k_] = vv
        vv = [p_ for pid, p_ in cache[1][k_] if pid != x_.get("partita")]
        if len(vv) < getattr(DA, "MINIMO_MAZZO", 10):
            return None
        return sum(vv) / len(vv)

    def segnapunti(self, b):
        """La somma dei voti delle fasi chiuse fino al passo aperto (19 nov 2026, Autore: «una somma dei victory points che si aggiorna a ogni ricalcolo
        delle fasi mia e di oppo», posizione A): le tue scelte, le sue scelte buone (i punti che ti tolgono), i suoi errori (i punti che ti regala); dal 21
        nov 2026 divisi come le spine (sotto): le pescate, la posta del turno, le tue non-azioni, il resto; net e' la somma, quanto e' cambiata la tua
        probabilita' di vincere dall'inizio. -> dict o None senza il voto."""
        import ev_partita as EV_
        x_ = b["x"]
        base = [y for y in self.righe or [] if y["tipo"] == x_.get("tipo")]
        v = EV_.righe_fasi(x_, b["passi"], base)
        if not v:
            return None
        # divisi come le spine del motore (21 nov 2026, Autore: «montiamo ogni miglioria apportata sul motore ... che il replayer sia allineato ai dati
        # ev del motore», spine.py, Note/Spine_Mazzo_Giocatore.md): le pescate sono occasioni della partita, di nessuno (occasioni.py); la posta del turno
        # (la P che chi e' di turno perde se passa senza fare niente, la fase «inizio» di ev_partita) e' di chi ha la mossa; il resto delle fasi senza
        # scelte a parte. Cosi' il totale e' quanto e' cambiata la tua probabilita' di vincere dall'inizio della partita, come la WIN CHANCE.
        out = dict(mie=0.0, n_mie=0, buone=0.0, n_buone=0, errori=0.0, n_errori=0, altro=0.0, fino=None, pesc_io=0.0, n_pesc_io=0, pesc_suo=0.0,
                   n_pesc_suo=0, posta_io=0.0, posta_suo=0.0, attese=0.0)
        k_ = (id(b["passi"]),)
        if b.get("_spine_k") != k_:
            import spine as SP_
            try:
                b["_spine"] = SP_.spine_partita(x_, b["passi"])
            except Exception:       # noqa: BLE001 - una partita senza il conto: il segnapunti non c'e'
                b["_spine"] = None
            b["_spine_k"] = k_
        sp_ = b["_spine"]
        if not sp_:
            return None
        # quando si chiude ogni fase della spina: la fase (t, f) e' chiusa se una fase delle righe dello stesso turno e non prima, o di un turno dopo, e'
        # chiusa al passo aperto; all'ultimo passo tutto (meno la fine, che e' il risultato)
        ORD = {"inizio": 0, "main1": 1, "turn": 1, "comb": 2, "main2": 3}
        chiuse = [(fz["t"], ORD.get(fz["f"], 3)) for fz in v["fasi"] if fz["ultimo"] <= b["i"]]
        ultimo = b["i"] >= len(b["passi"]) - 1
        for fz in v["fasi"]:
            if fz["ultimo"] <= b["i"]:
                out["fino"] = fz

        def chiusa(t, f):
            return ultimo or any(t2 > t or (t2 == t and o2 >= ORD.get(f, 3)) for t2, o2 in chiuse)
        for t, f, k, ev, testo in sp_["pezzi"]:
            if t is None or not chiusa(t, f):
                continue
            chi, _st, lin, ult = k
            if lin == "la mossa":
                out["posta_io" if chi == "Hero" else "posta_suo"] += ev
            elif chi == "partita":
                if ult == "pescata Hero":
                    out["pesc_io"] += ev; out["n_pesc_io"] += 1
                else:
                    out["pesc_suo"] += ev; out["n_pesc_suo"] += 1
            elif chi == "Hero" and ult == "non-azione":
                out["attese"] += ev
            elif chi == "Hero":
                out["mie"] += ev; out["n_mie"] += 1
            elif chi == "Opponent":
                if ev < 0:
                    out["buone"] += ev; out["n_buone"] += 1
                else:
                    out["errori"] += ev; out["n_errori"] += 1
            else:
                out["altro"] += ev
        out["occasioni"] = out["pesc_io"] + out["pesc_suo"]
        out["net"] = (out["mie"] + out["buone"] + out["errori"] + out["altro"] + out["occasioni"] + out["posta_io"] + out["posta_suo"]
                      + out["attese"])
        return out

    def disegna_segnapunti(self, cc, sp, x0, larga, y):
        """Il segnapunti in testa al racconto: tre caselle (le tue scelte, le sue buone, i suoi errori), sotto pescate e conseguenze e il net."""
        import ev_partita as EV_
        F = self.F
        fz = sp["fino"]
        quando = (f"up to Hero T{fz['giro']} · {EV_.NOMI_FASI.get(fz['f'], fz['f'])}" if fz and fz["mio"] else
                  f"up to Opponent T{fz['giro']} · {EV_.NOMI_FASI.get(fz['f'], fz['f'])}" if fz else "no phase closed yet")
        cc.create_rectangle(x0 + 12, y + 1, x0 + 14, y + 13, fill=C["accento"], outline="")
        cc.create_text(x0 + 19, y, text="TOTAL VICTORY POINTS", anchor="nw", fill=C["titolo"], font=F(8, True))
        cc.create_text(x0 + 19, y + 15, text=quando, anchor="nw", fill=C["muto"], font=F(7), width=larga - 34)
        y += 32
        w = (larga - 28 - 8) / 3
        segno = lambda v: f"{v:+.1f}".replace("-", "−")
        col = lambda v: C["verde"] if v >= EV_.SOGLIA_RIGA else C["rosso"] if v <= -EV_.SOGLIA_RIGA else C["muto"]
        for j, (tit, v, n, nome_n) in enumerate((("YOUR PLAYS", sp["mie"], sp["n_mie"], "plays"), ("OPP. GOOD PLAYS", sp["buone"], sp["n_buone"], "plays"),
                                                 ("OPP. MISTAKES", sp["errori"], sp["n_errori"], "gifts"))):
            xa = x0 + 14 + j * (w + 4)
            cc.create_rectangle(xa, y, xa + w, y + 50, fill="#131720", outline="#232a37")
            cc.create_rectangle(xa + 4, y + 6, xa + 6, y + 16, fill=C["accento"], outline="")
            cc.create_text(xa + 10, y + 11, text=tit, anchor="w", fill=C["titolo"], font=F(6, True))
            cc.create_text(xa + 6, y + 30, text=segno(v), anchor="w", fill=C["arancio"] if j == 2 and v >= EV_.SOGLIA_RIGA else col(v), font=F(12, True))
            cc.create_text(xa + 6, y + 43, text=f"{n} {nome_n}", anchor="w", fill=C["muto"], font=F(6))
        y += 56
        # sotto, le voci che non sono scelte (le spine): le occasioni della partita, la posta del turno, il resto
        for tit, v, nota in (("THE GAME · YOUR DRAWS", sp["pesc_io"], f"{sp['n_pesc_io']} draws"),
                             ("THE GAME · OPPONENT'S DRAWS", sp["pesc_suo"], f"{sp['n_pesc_suo']} draws"),
                             ("TURN STAKES · YOU / OPPONENT", sp["posta_io"] + sp["posta_suo"], f"{segno(sp['posta_io'])} / {segno(sp['posta_suo'])}"),
                             ("YOUR NON-ACTIONS · held back, waited", sp["attese"], ""),
                             ("NO CHOICE · rest of the phases", sp["altro"], "")):
            cc.create_text(x0 + 14, y + 7, text=tit, anchor="w", fill=C["muto"], font=F(7, True))
            if nota:
                cc.create_text(x0 + larga - 70, y + 7, text=nota, anchor="e", fill=C["muto"], font=F(6))
            cc.create_text(x0 + larga - 14, y + 7, text=segno(v), anchor="e", fill=col(v), font=F(8, True))
            y += 15
        cc.create_line(x0 + 14, y + 2, x0 + larga - 14, y + 2, fill="#232a37")
        cc.create_text(x0 + 14, y + 13, text="TOTAL · your win chance since the start", anchor="w", fill=C["muto"], font=F(7, True))
        cc.create_text(x0 + larga - 14, y + 13, text=segno(sp["net"]), anchor="e", fill=col(sp["net"]), font=F(12, True))
        return y + 32

    def due_voti(self, x_, fz, r_):
        """I due voti di una tua scelta (19 nov 2026, sessione Magic 22, il mockup: Autore «vai in ordine tutto»): [(testo, tono)].
        BEST LINE: la migliore alternativa dell'IS-MCTS (Motore_EV/ismcts.py: le candidate negli stessi mondi fino alla fine del suo turno dopo), solo dove il
        pilota e' passato; la prima azione della prima fase principale si confronta solo se e' la prima tua riga. STRONG PLAYERS: quanti giocatori forti di
        17Lands (60%+ con 50+ partite) fanno come te nella stessa situazione (Motore_EV/forti.py), per attacchi e blocchi."""
        try:
            cart = os.path.join(DA.percorsi.ROOT, "Motore_EV")
            import sys as _s
            if cart not in _s.path:
                _s.path.insert(0, cart)
            import voti
        except Exception:       # noqa: BLE001 - senza il motore dell'EV nessun voto in piu'
            return []
        testo = r_.get("testo") or ""
        tl = testo.lower()
        primo = next((z for z in fz["righe"] if z["mio"] and z["tipo"] != "risultato"), None)
        if "attack" not in tl and "block" not in tl and not (fz["f"] == "main1" and primo is r_):
            return []
        try:
            v = voti.della_scelta(x_, fz["t"], testo)
        except Exception:       # noqa: BLE001
            return []
        out = []
        ln = v.get("linea")
        if ln:
            if ln["stessa"]:
                out.append(("BEST LINE · this was it", "verde"))
            elif ln["meglio"]:
                out.append((f"BEST LINE {ln['scarto']:+.1f} · {voti.inglese(ln['migliore'])}".replace("-", "−"), "rosso"))
            else:
                out.append((f"BEST LINE · about the same ({ln['scarto']:+.1f}) · {voti.inglese(ln['migliore'])}".replace("-", "−"), "muto"))
            # perde contro (21 nov 2026): nei mondi della ricerca, la tua mossa con la sua mano che aveva un trucco, una rimozione istantanea, una
            # contromagia o una creatura flash, contro i mondi senza; solo le classi che costano almeno SOGLIA punti
            peggio = sorted(((c, q, d) for c, (q, d) in (ln.get("contro") or {}).items() if d <= -5), key=lambda z: z[2])
            if peggio:
                testo_c = "LOSES TO · " + ", ".join(f"{c} ({100 * q:.0f}% of his hands, {d:+.0f})" for c, q, d in peggio[:3])
                out.append((testo_c.replace("-", "−"), "arancio"))
        fo = v.get("forti")
        if fo:
            dove = " · Limited players" if v.get("constructed") else ""
            out.append((f"STRONG PLAYERS {fo['come_te']:.0f}% do this · {voti.TESTO_FORTI.get(fo['piu_comune'], '')}{dove}", "azzurro"))
        return out

    def pillola_voto(self, cc, x, y, larga, testo, tono):
        """Una pillola del voto: il testo nel colore del tono dentro un riquadro col filo dello stesso colore; va a capo, mai tagliata. -> la y sotto."""
        F = self.F
        col = C.get(tono, C["muto"])
        it = cc.create_text(x + 8, y + 3, text=testo, anchor="nw", fill=col, font=F(7, True), width=max(60, larga - 16))
        bb = cc.bbox(it) or (x, y, x + larga, y + 14)
        r = cc.create_rectangle(x, y, min(x + larga, bb[2] + 8), bb[3] + 3, fill=C["scheda"], outline=col)
        cc.tag_lower(r, it)
        return bb[3] + 3

    def disegna_voto_fase(self, cc, b, voto, x0, larga, y):
        """Il voto della fase nel racconto: in testa chi e quale fase, poi una riga per ogni cosa accaduta (il numero, l'etichetta di chi e' il merito o il
        regalo; le conseguenze, coi punti gia' nella riga sopra, senza numero); a fine fase il totale e il solito. Il clic su una riga porta al suo passo."""
        import ev_partita as EV_
        F = self.F
        fz = voto["fase"]
        chi = "HERO" if fz["mio"] else "OPPONENT"
        cc.create_text(x0 + 14, y, text=f"{chi} T{fz['giro']} · {EV_.NOMI_FASI.get(fz['f'], fz['f']).upper()} · EV", anchor="nw", fill=C["azzurro"],
                       font=F(8, True), width=larga - 28)
        y += 20
        if fz["mio"] and fz["f"] in ("main1", "comb"):
            # l'equity contro il suo range (21 nov 2026, liste_avversarie): nel Constructed, se lui ha passato con 2+ terre aperte, quanto spesso il suo mazzo
            # in quel caso risponde nel tuo turno e con cosa; una volta in testa alle tue fasi
            try:
                import liste_avversarie as LA_
                tx_r = LA_.testo_risposta(LA_.risposta(b["x"], fz["t"], self.righe or []))
            except Exception:       # noqa: BLE001 - senza il ritratto nessuna riga
                tx_r = None
            if tx_r:
                y = self.pillola_voto(cc, x0 + 14, y, larga - 28, tx_r, "arancio" if "go through" in tx_r else "muto") + 6
        self._box_voto = []
        for r_ in voto["righe"]:
            on = r_["i"] == b["i"]
            col = C[self.COLORI_VOTO.get(r_["tipo"], "muto")]
            y0 = y
            i_t = cc.create_text(x0 + 24, y + 2, text=r_["testo"], anchor="nw", fill=C["titolo"] if r_["tipo"] != "risultato" else C["testo"],
                                 font=F(8, r_["tipo"] != "risultato"), width=larga - 96)
            yb = (cc.bbox(i_t) or (0, 0, 0, y + 14))[3]
            sol = None
            if r_["incluso"]:
                eti = "result · in the row above"
            else:
                eti = EV_.ETICHETTE.get(r_["tipo"], "")
                if r_["mio"] and r_["tipo"] != "risultato":
                    # contro le tue scelte uguali con questo mazzo (21 nov 2026, solito_righe): il colore del numero dallo scarto, non dal segno
                    try:
                        import solito_righe as SR
                        base_ = [z for z in self.righe or [] if z["tipo"] == b["x"].get("tipo")]
                        sol = SR.solito(b["x"], r_, fz, base_)
                    except Exception:       # noqa: BLE001 - senza il solito resta il colore del segno
                        sol = None
                    if sol and sol["media"] is not None:
                        sc_ = sol["scarto"]
                        col = C["verde"] if sc_ >= EV_.SOGLIA_RIGA else C["rosso"] if sc_ <= -EV_.SOGLIA_RIGA else C["muto"]
                        eti += (f" · usually {sol['media']:+.1f} ({sol['n']} times, {sol['gradino']}) · vs usual {sc_:+.1f}").replace("-", "−")
                    elif sol is not None:
                        eti += (f" · few games to compare ({sol['fatte']} of {sol['totali']} read)" if sol["fatte"] < sol["totali"]
                                else " · few games to compare")
                cc.create_text(x0 + larga - 14, y + 2, text=f"{r_['ev']:+.1f}".replace("-", "−"), anchor="ne", fill=col, font=F(10, True))
            col_e = C["arancio"] if r_["tipo"] in ("suo_errore", "suo_buono") else C["muto"]
            i_e = cc.create_text(x0 + 24, yb + 1, text=eti, anchor="nw", fill=col_e, font=F(7, True), width=larga - 40)
            y = (cc.bbox(i_e) or (0, 0, 0, yb + 13))[3] + 3
            if r_["mio"] and not r_["incluso"] and r_["tipo"] != "risultato":
                for testo_, tono_ in self.due_voti(b["x"], fz, r_):
                    y = self.pillola_voto(cc, x0 + 22, y, larga - 44, testo_, tono_) + 3
                # l'equity contro il suo range (21 nov 2026, equity.py): la tua magia se va a segno e se lui risponde, pesate dalla probabilita' che risponda
                if b["x"].get("tipo") == "Constructed" and r_["testo"].startswith("You cast "):
                    try:
                        import equity as EQ_
                        eq_ = EQ_.della_riga(b["x"], fz["t"], r_["testo"], self.righe or [])
                    except Exception:       # noqa: BLE001 - senza l'equity la riga resta com'era
                        eq_ = None
                    if eq_:
                        y = self.pillola_voto(cc, x0 + 22, y, larga - 44, f"EQUITY VS HIS RANGE · {eq_['equity']:.0f}% · it resolves {eq_['p_res']:.0f}% · "
                                              f"if he answers {eq_['p_ans']:.0f}% · he answers {100 * eq_['q']:.0f}%", "azzurro") + 3
                # il combattimento (21 nov 2026, equity.risolvi, Constructed e Limited): come dichiarato, a regole, contro la sua risposta prima del danno
                if r_["testo"].startswith(("You attacked with ", "You blocked ")):
                    try:
                        import equity as EQ_
                        eq_ = EQ_.della_riga_combattimento(b["x"], fz["t"], r_["testo"], self.righe or [])
                    except Exception:       # noqa: BLE001
                        eq_ = None
                    if eq_:
                        y = self.pillola_voto(cc, x0 + 22, y, larga - 44, f"EQUITY VS HIS RANGE · {eq_['equity']:.0f}% · as declared {eq_['p_res']:.0f}% · "
                                              f"if he answers before damage {eq_['p_ans']:.0f}% · he answers {100 * eq_['q']:.0f}%", "azzurro") + 3
            # la barretta di chi e' il voto e la riga accesa sul passo aperto
            cc.create_rectangle(x0 + 12, y0 + 2, x0 + 15, y - 4, fill=col if not r_["incluso"] else "#2a3140", outline="")
            if on:
                it_ = cc.create_rectangle(x0 + 6, y0 - 2, x0 + larga - 6, y - 1, fill="#1f3446", outline=C["azzurro"])
                cc.tag_lower(it_, i_t)      # sotto le scritte della riga, sopra il fondo della colonna
            tag_ = f"voto_{r_['i']}"
            cc.addtag_overlapping(tag_, x0 + 8, y0, x0 + larga - 8, y - 2)
            cc.tag_bind(tag_, "<Button-1>", lambda _e, i_=r_["i"]: self.vai_board(i_))
            cc.tag_bind(tag_, "<Enter>", lambda _e: cc.configure(cursor="hand2"))
            cc.tag_bind(tag_, "<Leave>", lambda _e: cc.configure(cursor=""))
            self._box_voto.append((x0 + 6, y0 - 2, x0 + larga - 6, y - 1, r_["i"]))
            y += 4
        if voto["finita"]:
            cc.create_line(x0 + 12, y, x0 + larga - 12, y, fill="#2a3140")
            y += 6
            tot = fz["totale"]
            col_t = C["verde"] if tot >= EV_.SOGLIA_RIGA else C["rosso"] if tot <= -EV_.SOGLIA_RIGA else C["muto"]
            cc.create_text(x0 + 14, y, text="PHASE TOTAL", anchor="nw", fill=C["muto"], font=F(7, True))
            cc.create_text(x0 + larga - 14, y - 2, text=f"{tot:+.1f}".replace("-", "−"), anchor="ne", fill=col_t, font=F(12, True))
            y += 20
            if fz.get("atteso") is not None:
                sc_ = fz["scarto"]
                poche = (fz.get("n") or 0) < EV_.MINIMO
                col_s = C["muto"] if poche else C["verde"] if sc_ > 0 else C["rosso"]
                cc.create_text(x0 + 14, y, text=f"usually {fz['atteso']:+.1f} ({fz.get('n') or 0} games) · vs usual", anchor="nw", fill=C["muto"], font=F(7))
                cc.create_text(x0 + larga - 14, y - 1, text=f"{sc_:+.1f}".replace("-", "−"), anchor="ne", fill=col_s, font=F(9, True))
                y += 18
        else:
            cc.create_text(x0 + 14, y, text="the vote comes at the end of the phase", anchor="nw", fill=C["muto"], font=F(7))
            y += 16
        return y + 8

    def blocchi_ev(self, b, tutti=False):
        """L'EV del passo aperto, dell'Hero soltanto (18 nov 2026 sera, Autore: «questi messaggi sono troppo difficili da capire ... facciamo cosi': solo ev
        + e ev - e solo di hero / su ev- se vuoi puoi spiegare la perdita in un messaggio espandibile»): [dict(titolo, diff, n, perche=[righe])], la tua
        giocata di questo momento (attacco, blocco, magia) e il tuo turno. diff e' lo scarto dal solito in punti di P, il numero che si vede; perche' sono le
        righe della spiegazione (solo per l'EV negativo). Solo quando lo scarto arriva a SOGLIA_PARLA (tutti=True: sempre)."""
        import ev_partita as EV_
        out = []
        dz_ = self.costi_passi(b).get(b["i"])
        if dz_ is not None and dz_.get("costo") is not None:
            out.append(dict(titolo="your play", diff=dz_["costo"], n=dz_.get("n_confronto") or 0, perche=self.perche_giocata(dz_)))
        ze_ = self.ev_turno_passo(b)
        if ze_ is not None and ze_.get("mio") and ze_.get("scarto") is not None:
            fasi_ = [ph for ph in ze_.get("fasi") or [] if ph["f"] != "turn"]
            perche_ = []
            if ze_.get("p0") is not None and ze_.get("p1") is not None:
                perche_.append(f"Your chance to win went from {ze_['p0']:.0f}% to {ze_['p1']:.0f}% in this turn.")
            if ze_.get("atteso") is not None:
                perche_.append(f"A turn like this usually moves it {ze_['atteso']:+.1f} points ({ze_.get('n') or 0} games); this one {ze_['ev']:+.1f}.")
            if fasi_:
                peggio = min(fasi_, key=lambda ph: ph["scarto"])
                if peggio["scarto"] < 0:
                    perche_.append(f"Most of it was lost in {EV_.NOMI_FASI.get(peggio['f'], 'the turn')} ({peggio['scarto']:+.1f}).")
                perche_.append("By phase: " + " · ".join(f"{EV_.NOMI_FASI.get(ph['f'], ph['f'])} {ph['scarto']:+.1f}" for ph in fasi_) + ".")
            out.append(dict(titolo=f"your turn {ze_['giro']}", diff=ze_["scarto"], n=ze_.get("n") or 0, perche=perche_))
        return [z for z in out if tutti or abs(z["diff"]) >= self.SOGLIA_PARLA]

    @staticmethod
    def perche_giocata(dz_):
        """Le righe che spiegano una tua giocata (per l'EV negativo): cosa e' successo, la probabilita' prima e dopo, il solito."""
        r = []
        tipo = dz_.get("tipo")
        if tipo in ("attacco", "blocco"):
            pm, ps, dn = dz_.get("persi_miei") or 0, dz_.get("persi_suoi") or 0, dz_.get("danno") or 0
            if tipo == "attacco":
                r.append(f"You attacked with {dz_.get('attaccanti') or 0}: you lost {pm} creature{'s' * (pm != 1)}, the opponent lost {ps}, "
                         f"{dn} damage to the opponent." + (" The opponent had a trick." if dz_.get("trucco_suo") else ""))
            else:
                r.append(("You blocked" if dz_.get("bloccato") else "You didn't block") + f": you lost {pm} creature{'s' * (pm != 1)}, the opponent lost {ps}, "
                         f"you took {dn} damage." + (" The opponent had a trick." if dz_.get("trucco_suo") else ""))
        elif tipo == "magia":
            r.append(f"You cast {dz_.get('nome') or 'a spell'}.")
        if dz_.get("p_prima") is not None and dz_.get("p_dopo") is not None:
            r.append(f"Your chance to win went from {dz_['p_prima']:.0f}% to {dz_['p_dopo']:.0f}%.")
        if dz_.get("media") is not None and dz_.get("guadagno_r8") is not None:
            r.append(f"A play like this usually moves it {dz_['media']:+.1f} points ({dz_.get('n_confronto') or 0} plays); this one {dz_['guadagno_r8']:+.1f}.")
        return r

    def tenuto_passo(self, b):
        """(attaccanti, potevano) se il passo aperto e' il primo del combattimento di un turno in cui l'Opponent ha lasciato danni sul tavolo
        (mana_aperto.tenuti_a_casa), se no None. Una volta per partita e modo."""
        k_ = (id(b["passi"]),)
        if b.get("_tenuti_k") != k_:
            import mana_aperto as MA_
            x_ = b["x"]
            tt_ = MA_.tenuti_a_casa(DA._MANA.get(x_.get("partita")), x_.get("seat"))
            primi = {}
            for i, p_ in enumerate(b["passi"]):
                if p_[2] in tt_ and p_[2] not in primi and p_is_comb(p_):
                    primi[p_[2]] = i
            b["_tenuti_k"], b["_tenuti_i"] = k_, {i: tt_[t] for t, i in primi.items()}
        return b["_tenuti_i"].get(b["i"])

    def costi_passi(self, b):
        """R8 nel replayer: {indice del passo: decisione col costo} per i tuoi attacchi, blocchi e magie di questa partita (contro tutte le partite del
        tipo). Una volta per partita e modo."""
        k_ = (id(b["passi"]),)
        if b.get("_costi_k") == k_:
            return b["_costi_i"]
        x_ = b["x"]
        base = [x for x in self.righe or [] if x["tipo"] == x_.get("tipo")]
        out = {}
        for z in DEC.costi([x_], base or [x_]):
            ps = b["passi"]
            if z["tipo"] == "magia":
                i = next((i for i, p_ in enumerate(ps) if p_[2] == z["t"] and isinstance(p_[3], dict) and p_[3].get("tipo") == "spell"
                          and p_[3].get("nome") == z["nome"] and i not in out), None)
            else:
                i = next((i for i, p_ in enumerate(ps) if p_[2] == z["t"] and p_is_comb(p_) and i not in out), None)
            if i is not None:
                out[i] = z
        b["_costi_k"], b["_costi_i"] = k_, out
        return out

    def cambia_chi_chiave(self):
        voci = [k for k, _n in self.CHI_CHIAVE]
        self._chi_chiave = voci[(voci.index(getattr(self, "_chi_chiave", "both")) + 1) % len(voci)]
        self.b_chi.metti(dict(self.CHI_CHIAVE)[self._chi_chiave], self._chi_chiave != "both")
        self._chiave_ctrl = None
        self.disegna_board()
        return self._chi_chiave

    def leak_passi(self, b):
        """I leak della partita sui passi del replayer (leak.py): {indice: [nomi]}. L1 sul tuo turno (l'ultimo passo di quel turno), L4 sul combattimento del
        suo turno, L7 sull'ultimo passo. Una volta per partita e modo."""
        k_ = (id(b["passi"]),)
        if b.get("_leak_k") == k_:
            return b["_leak_i"]
        import leak as LK
        x_, ps = b["x"], b["passi"]
        lk = x_.get("leak") or {}
        out = {}
        if lk:
            carte_ = lk.get("carte") or {}

            def metti(i, k, T=None):
                if i is not None:       # con la carta, dove il leak la sa (17 nov 2026): «... · Cathar Commando»
                    cc_ = (carte_.get(k) or {}).get(T) or []
                    out.setdefault(i, []).append(LK.NOMI[k] + (" · " + ", ".join(dict.fromkeys(cc_)) if cc_ else ""))
            for k in LK.ORDINE:     # ogni leak sul suo turno di Arena: sul combattimento (L4, L5), sull'ultimo passo del turno (gli altri), L7 sull'ultimo
                if k == "l7":
                    if lk.get("l7") and ps:
                        metti(len(ps) - 1, "l7")
                    continue
                if k in ("l12", "l13"):     # il mulligan: sul primo passo, la mano (15 nov 2026)
                    if LK.valore(x_, k) == "Yes" and ps:
                        metti(0, k)
                    continue
                for T in lk.get(k) or []:
                    cand = [i for i, p_ in enumerate(ps) if p_[2] == T]
                    if k in ("l4", "l5"):
                        metti(next((i for i in cand if p_is_comb(ps[i])), cand[-1] if cand else None), k, T)
                    else:
                        metti(cand[-1] if cand else None, k, T)
        b["_leak_k"], b["_leak_i"] = k_, out
        return out

    def filtro_passi(self, b):
        """Gli spot dei filtri accesi sui passi del replayer (15 nov 2026, Autore: «quando setto i filtri, i replay in this situation si aprano sulla
        posizione indicata dal filtro di ricerca? magari creando un logo sul replay dedicato che indica la situazione da filtro attivo»): {indice: [(chiave,
        testo)]}. DA.spot_filtri dice il turno di Arena e il dove; qui il passo: la magia di quel giocatore, il combattimento, il primo o l'ultimo passo del
        turno, la mano, l'ultimo passo. I filtri di tutta la partita non hanno un momento e non segnano niente."""
        k_ = (id(b["passi"]), tuple(sorted((k, repr(v)) for k, v in self.filtri.items() if v is not None)))
        if b.get("_filtro_k") == k_:
            return b["_filtro_i"]
        ps, out = b["passi"], {}
        for z in DA.spot_filtri(b["x"], self.filtri):
            i = self.indice_spot(ps, z)
            if i is not None:
                v_ = out.setdefault(i, [])
                if z["chiave"] not in [c_ for c_, _t in v_]:
                    v_.append((z["chiave"], f"{z['nome']}: {z['voce']}"))
        b["_filtro_k"], b["_filtro_i"] = k_, out
        return out

    FASI_PASSO = {"Phase_Main1": ("Main1",), "Phase_Main2": ("Main2",), "Phase_Ending": ("End",), "Phase_Beginning": ("Upkeep", "Draw"),
                  "Phase_Combat": ("BeginCombat", "DeclareAttack", "DeclareBlock", "Damage", "EndCombat")}

    @staticmethod
    def indice_spot(ps, z):
        """Il passo di uno spot (DA.spot_filtri) nei passi del replayer, o None se quel turno non c'e'."""
        if not ps:
            return None
        if z["dove"] == "mano":
            return 0
        if z["dove"] == "ultimo":
            return len(ps) - 1
        cand = [i for i, p_ in enumerate(ps) if p_[2] == z["t"]]
        if not cand:
            return None
        if z["dove"] == "comb":
            return next((i for i in cand if p_is_comb(ps[i])), cand[-1])
        if z["dove"] == "magia":
            spell_ = lambda i: len(ps[i]) > 3 and isinstance(ps[i][3], dict) and ps[i][3].get("tipo") == "spell" and not ps[i][3].get("ab")                 and (z["mio"] is None or bool(ps[i][3].get("mio")) == z["mio"])
            # la magia della situazione (24 nov 2026: il board wipe, la contromagia): il passo di quella carta, se no la prima magia di chi la lancia
            i_m = next((i for i in cand if spell_(i) and z.get("g") and ps[i][3].get("g") == z["g"]), None)
            if i_m is None:
                i_m = next((i for i in cand if spell_(i)), None)
            if i_m is not None:
                return i_m
            # una magia senza bersagli non ha un passo «spell»: il primo passo con la carta nella pila (Every action; voci (nome, mio, abilita', grpId,
            # id)), se no il primo passo della fase in cui e' stata lanciata (le «fasi» di mana_aperto)
            if z.get("g"):
                i_p = next((i for i in cand if isinstance(ps[i][1], dict) and any(len(v_) > 3 and v_[3] == z["g"] and not v_[2]
                                                                                   for v_ in ps[i][1].get("pila") or [])), None)
                if i_p is not None:
                    return i_p
            parole = PaginaPerformance.FASI_PASSO.get(z.get("fase") or "", ())
            return next((i for i in cand if any(w_ in ps[i][0] for w_ in parole)), cand[0])
        return cand[-1] if z["dove"] == "fine" else cand[0]

    def primo_spot(self, b):
        """Dove aprire il replayer coi filtri accesi: il primo passo in cui sono veri tutti i filtri che hanno un momento, se no il primo spot; None senza."""
        fi = self.filtro_passi(b)
        if not fi:
            return None
        tutte = {c_ for v_ in fi.values() for c_, _t in v_}
        return next((i for i in sorted(fi) if {c_ for c_, _t in fi[i]} == tutte), min(fi))

    def segna_board(self):
        """Segna lo spot di adesso (o lo toglie): finisce nella cartella My filters, sotto i tuoi filtri, e si riapre da li'."""
        b = getattr(self, "_board", None)
        if not b:
            return None
        p_ = b["passi"][b["i"]]
        ora = DA.segna(b["x"], b.get("modo", "momenti"), b["i"], p_[0], p_[2])
        self.disegna_board()
        if "mine" in self.visibili():
            self.disegna_miei()
        return ora

    def apri_segnalibro(self, s_):
        """Uno spot segnato: la sua partita nel replayer, nel suo modo, sul suo passo (o su quello con lo stesso nome piu' vicino)."""
        x_ = next((x for x in self.righe or [] if x.get("partita") == s_.get("partita")), None)
        if x_ is None:
            return None
        f = self.apri_board(x_, "fine")
        if f is None:
            return None
        if s_.get("modo") == "azioni":
            self.cambia_modo_board("azioni", ridisegna=False)
        ps = self._board["passi"]
        if s_.get("i") is None:     # R13: segnato dal vivo, col turno di Arena: il primo momento di quel turno (o l'ultimo prima)
            dentro = [i for i, p_ in enumerate(ps) if p_[2] <= (s_.get("t") or 0)]
            stesso = [i for i, p_ in enumerate(ps) if p_[2] == s_.get("t")]
            i = stesso[0] if stesso else (dentro[-1] if dentro else 0)
            self.vai_board(i)
            return f
        stessi = [i for i, p_ in enumerate(ps) if p_[0] == s_.get("passo")]
        i = min(stessi, key=lambda j: abs(j - s_.get("i", 0))) if stessi else min(s_.get("i", 0), len(ps) - 1)
        self.vai_board(i)
        return f

    def turno_board(self, d):
        """Pagina su e giu': il turno prima o dopo (il primo momento o la prima azione di quel turno)."""
        b = getattr(self, "_board", None)
        if not b:
            return
        t_ora = b["passi"][b["i"]][2]
        turni = sorted({p_[2] for p_ in b["passi"]})
        k = turni.index(t_ora) + d if t_ora in turni else 0
        if 0 <= k < len(turni):
            self.ferma_board()
            self.vai_board(next(i for i, p_ in enumerate(b["passi"]) if p_[2] == turni[k]))

    def clic_passo(self, e):
        x = self.cv_passi.canvasx(e.x)
        for x0, x1, i in getattr(self, "_box_passi", []):
            if x0 <= x <= x1:
                self.ferma_board()
                self.vai_board(i)
                return

    def vai_svolta(self):
        b = getattr(self, "_board", None)
        if b and b.get("svolta") is not None:
            self.ferma_board()
            self.vai_board(b["svolta"])

    def racconto(self, i):
        """Cosa e' successo nel turno del momento i. Dal debug del 12 nov 2026 dal replay azione per azione (replay_log: l'annullamento di Arena, le terre
        messe in campo da un effetto, i messaggi riassunti); senza il log della partita, dalla scheda (Partite/), come prima: le terre, le magie, le abilita'
        (non quelle di mana delle terre), gli attacchi, i blocchi, le pedine, chi muore. -> [(tu?, testo)]; None senza niente."""
        b = self._board
        nome, _f, t = b["passi"][i][:3]
        if nome == "Opening hand":
            x_ = b["x"]
            out = [(True, f"You are on the {x_['partenza'].lower()}" if x_.get("partenza") else "Who starts is not in the logs")]
            if x_.get("mulligan"):
                out.append((True, f"You took {x_['mulligan']} mulligan{'s' if x_['mulligan'] > 1 else ''}"))
            return out
        if b.get("azioni_passi") is None:
            b["azioni_passi"] = DA.azioni_partita(b["x"]) or []
        if b["azioni_passi"]:
            out = []
            for p_ in b["azioni_passi"]:
                if p_[2] != t:
                    continue
                for mio, testo in p_[4]:
                    if testo.endswith(" begins") or " drew " in f" {testo}" or testo.endswith(" resolved"):    # il riassunto del turno: le mosse, non il contorno
                        continue
                    if out and out[-1][1] == testo:      # le righe uguali di fila una volta sola, con quante
                        out[-1][2] += 1
                    else:
                        out.append([mio, testo, 1])
            return [(a, t_ + (f"  ×{n_}" if n_ > 1 else "")) for a, t_, n_ in out]
        sch = DA.scheda(b["x"].get("partita"))
        if not sch:
            return None
        import mazzi_salvati as MS
        verbi = {"terra": "played", "lancia": "cast", "abilita": "activated", "attacca": "attacked with", "blocca": "blocked with", "pedina": "made a token:",
                 "muore": "lost"}
        out = []
        for e in sch.get("eventi") or []:
            if e.get("t") != t or e.get("tipo") not in verbi:
                continue
            carta = e.get("carta") or "a card"
            if e["tipo"] == "abilita" and MS.e_terra(carta):
                continue
            chi = "You" if e.get("chi") == "io" else "Opponent"
            testo = f"{chi} {verbi[e['tipo']]} {carta}"
            if e["tipo"] == "attacca" and e.get("pt"):
                testo += f" ({e['pt']})"
            if e["tipo"] == "blocca" and e.get("blocca"):
                testo += " → " + ", ".join(e["blocca"])
            if out and out[-1][1] == testo:      # le righe uguali di fila una volta sola, con quante
                out[-1][2] += 1
            else:
                out.append([e.get("chi") == "io", testo, 1])
        return [(a, t_ + (f"  ×{n_}" if n_ > 1 else "")) for a, t_, n_ in out]

    def immagine_carta(self, nome, w, tappata, grigia=False):
        """La carta in piccolo dalla miniatura cotta (capsule.cuoci), girata se tappata; grigia (desaturata e scurita: una creatura morta, 14 nov 2026);
        None se la miniatura non c'e'."""
        cache = self.__dict__.setdefault("_img_carte", {})
        k = (nome, w, tappata, grigia)
        if k not in cache:
            try:
                import capsule
                from PIL import Image, ImageEnhance, ImageTk
                f_ = capsule.file_mini(nome)
                if not os.path.exists(f_):      # la meta' di una carta (un'avventura, un presagio): l'immagine e' quella della carta intera
                    f_ = capsule.file_mini(DA.nome_intero(nome))
                im = Image.open(f_).convert("RGBA")
                im = im.resize((w, round(w * im.height / im.width)), Image.LANCZOS)
                if grigia:
                    a_ = im.getchannel("A")
                    im = ImageEnhance.Brightness(ImageEnhance.Color(im.convert("RGB")).enhance(0.0)).enhance(0.62).convert("RGBA")
                    im.putalpha(a_)
                    im = con_teschio(im)
                if tappata:
                    im = im.rotate(90, expand=True)
                cache[k] = ImageTk.PhotoImage(im)
            except Exception:      # noqa: BLE001 - senza miniatura il riquadro col nome
                cache[k] = None
        return cache[k]

    def immagine_pezzo(self, nome, w, tappata, grigia=False):
        """Come immagine_carta, e per una pedina (o una carta senza miniatura) l'immagine del tappeto (disegno_tappeto.faccia, con la pedina vera)."""
        im_ = self.immagine_carta(nome, w, tappata, grigia)
        if im_ is not None:
            return im_
        cache = self.__dict__.setdefault("_img_pezzo_cache", {})
        k = (nome, w, tappata, grigia)
        if k not in cache:
            try:
                import disegno_tappeto as DT
                from PIL import ImageEnhance, ImageTk
                im = DT.faccia(nome, w, tappata, pedina=(getattr(self, "_pedine_nomi", {}) or {}).get(nome)).copy()
                if grigia:
                    a_ = im.getchannel("A")
                    im = ImageEnhance.Brightness(ImageEnhance.Color(im.convert("RGB")).enhance(0.0)).enhance(0.62).convert("RGBA")
                    im.putalpha(a_)
                    im = con_teschio(im)
                cache[k] = ImageTk.PhotoImage(im)
            except Exception:      # noqa: BLE001 - niente immagine: niente animazione per lei
                cache[k] = None
        return cache[k]

    def icona_danno(self, tipo, q):
        """Le icone del combattimento e della vita (15 nov 2026, Autore: «vorrei tutto piu' esport», fra tre stili «danno vite perse e vite guadagnate
        a broadcast»): la piastra inclinata come le barre dell'HUD sopra Arena, il blocco piu' scuro a sinistra col simbolo bianco e il numero grande in
        Bahnschrift a destra. «spada» arancio col numero (chi infligge il danno), «goccia» rossa col «-N» (chi perde vite o costituzione), «cuore» verde col
        «+N» (la vita che sale). Disegnate a 4x e ridotte, con un filo scuro intorno perche' si leggano anche sopra le carte. Fino a quel giorno: la goccia
        di sangue, il tondo arancio con la spada, il cuore verde (14 nov 2026, «spada B, vite A»)."""
        cache = self.__dict__.setdefault("_icone_danno", {})
        k = (tipo, q)
        if k not in cache:
            from PIL import Image, ImageDraw, ImageTk
            import disegno_tappeto as DT
            S = 4
            W_, H_ = PIASTRA_W, PIASTRA_H
            colori = {"spada": ((255, 122, 26), (201, 79, 0)), "goccia": ((224, 38, 47), (156, 18, 25)), "cuore": ((31, 191, 106), (17, 138, 74))}
            chiaro, scuro = colori.get(tipo, colori["spada"])
            testo = f"+{q}" if tipo == "cuore" else str(q)      # il meno si disegna (il Bahnschrift non ha il segno U+2212, usciva un quadratino)
            im = Image.new("RGBA", (W_ * S, H_ * S), (0, 0, 0, 0))
            d = ImageDraw.Draw(im)
            m, inc = 2 * S, 7 * S                       # il margine del filo scuro e quanto pende la piastra
            x0, y0, x1, y1 = m, m, W_ * S - m, H_ * S - m
            piastra = lambda e: [(x0 + inc - e, y0 - e), (x1 + e, y0 - e), (x1 - inc + e, y1 + e), (x0 - e, y1 + e)]
            d.polygon(piastra(m * 0.9), fill=(6, 8, 12, 170))
            d.polygon(piastra(0), fill=chiaro + (255,))
            xb = x0 + 22 * S                             # il blocco del simbolo
            d.polygon([(x0 + inc, y0), (xb + inc, y0), (xb, y1), (x0, y1)], fill=scuro + (255,))
            cx, cy = x0 + inc / 2 + 11 * S, (y0 + y1) / 2
            bianco = (255, 255, 255, 255)
            if tipo == "goccia":
                r = 5.6 * S
                cyg = cy + 2.2 * S
                d.polygon([(cx, cyg - 11.5 * S), (cx - r * 0.93, cyg - r * 0.36), (cx + r * 0.93, cyg - r * 0.36)], fill=bianco)
                d.ellipse((cx - r, cyg - r, cx + r, cyg + r), fill=bianco)
            elif tipo == "cuore":
                r = 3.9 * S
                top = cy - 6.2 * S
                d.ellipse((cx - 2 * r + 0.4 * S, top, cx + 0.4 * S, top + 2 * r), fill=bianco)
                d.ellipse((cx - 0.4 * S, top, cx + 2 * r - 0.4 * S, top + 2 * r), fill=bianco)
                d.polygon([(cx - 2 * r + 0.7 * S, top + r * 1.25), (cx + 2 * r - 0.7 * S, top + r * 1.25), (cx, cy + 7.6 * S)], fill=bianco)
            else:
                spada = Image.new("RGBA", (12 * S, 24 * S), (0, 0, 0, 0))
                ds = ImageDraw.Draw(spada)
                mm = 6 * S
                ds.polygon([(mm, 0), (mm + 2.2 * S, 3 * S), (mm + 2.2 * S, 14 * S), (mm - 2.2 * S, 14 * S), (mm - 2.2 * S, 3 * S)], fill=bianco)
                ds.rectangle((mm - 5.5 * S, 14 * S, mm + 5.5 * S, 16.4 * S), fill=bianco)
                ds.rectangle((mm - 1.3 * S, 16.4 * S, mm + 1.3 * S, 21 * S), fill=bianco)
                ds.ellipse((mm - 2 * S, 20.5 * S, mm + 2 * S, 24 * S), fill=bianco)
                spada = spada.rotate(45, expand=True, resample=Image.BICUBIC)
                im.alpha_composite(spada, (int(cx - spada.width / 2), int(cy - spada.height / 2)))
                d = ImageDraw.Draw(im)
            f = DT.font(19 * S)
            bb = d.textbbox((0, 0), testo, font=f)
            meno = 7 * S if tipo == "goccia" else 0          # la barra del meno e lo spazio dopo
            largo = (bb[2] - bb[0]) + (meno + 2 * S if meno else 0)
            xt = (xb + inc / 2 + x1 - inc / 2) / 2 - largo / 2
            if meno:
                d.rectangle((xt, cy - 1.2 * S, xt + meno, cy + 1.2 * S), fill=bianco)
                xt += meno + 2 * S
            d.text((xt - bb[0], cy - (bb[3] - bb[1]) / 2 - bb[1]), testo, font=f, fill=bianco)
            cache[k] = ImageTk.PhotoImage(im.resize((W_, H_), Image.LANCZOS))
        return cache[k]

    def immagine_dorso(self, w):
        """Il dorso delle carte 3 Steps Ahead (disegno_tappeto.dorso) largo w, per la pescata dell'avversario che vola."""
        cache = self.__dict__.setdefault("_img_dorsi", {})
        if w not in cache:
            try:
                import disegno_tappeto as DT
                from PIL import ImageTk
                cache[w] = ImageTk.PhotoImage(DT.dorso(w))
            except Exception:      # noqa: BLE001 - senza il dorso niente volo
                cache[w] = None
        return cache[w]


    def disegna_liste(self):
        """Le due liste del momento: a sinistra il tuo mazzo (DA.lista_mia: copie rimaste nel grimorio su copie nel mazzo, la probabilita' di pescarla alla
        prossima, finite in grigio, le terre in fondo), a destra le sue carte viste fino a qui (DA.lista_sua: un minimo, non il suo mazzo) col pulsante
        «Copy as list». Il passaggio del mouse su una riga mostra la carta grande."""
        b = getattr(self, "_board", None)
        F = self.F
        for c in (getattr(self, "cv_lista_mio", None), getattr(self, "cv_lista_suo", None)):
            if c is None or not c.winfo_exists() or not b:
                continue
            c.delete("all")
            c._righe, c._copia = [], None
            mio = c is self.cv_lista_mio
            _n, f, _t, rel = b["passi"][b["i"]][:4]
            # chiudibili, ognuna verso il suo lato (13 nov 2026, Autore: «nel replayer rendi le liste dei mazzi chiudibili ognuna verso il suo lato»): chiusa
            # resta una striscia col nome in verticale, il clic la riapre; la scelta resta per le partite dopo
            if self.liste_chiuse()["mio" if mio else "suo"]:      # chiusa: resta la linguetta (metti_liste)
                continue
            W = LARGA_LISTA
            y = 14
            if mio:
                m = DA.lista_mia(b["x"].get("deck"), f, rel)
                c.create_text(10, y, text="YOUR DECK", anchor="w", fill=C["azzurro"], font=F(8, True))
                if not m:
                    c.create_text(10, y + 26, text="The deck list of this game\nis not in the log.", anchor="nw", fill=C["grigio"], font=F(8))
                    continue
                c.create_text(W - 10, y, text=f"{m['grimorio']} in library", anchor="e", fill=C["grigio"], font=F(7))
                y += 16
                c.create_text(10, y, text="LEFT/DECK · NEXT DRAW", anchor="w", fill=C["muto"], font=F(6, True))
                y += 14
                terre_ = False
                for n, rim, q, terra in m["righe"]:
                    if terra and not terre_:
                        terre_ = True
                        y += 6
                        c.create_text(10, y + 6, text="LANDS", anchor="w", fill=C["muto"], font=F(6, True))
                        y += 14
                    col = C["testo"] if rim else "#55555c"
                    if len(c._righe) % 2 == 0:
                        c.create_rectangle(4, y, W - 4, y + ALTO_RIGA_LISTA, fill="#141922", outline="")
                    c.create_text(10, y + ALTO_RIGA_LISTA / 2, text=f"{rim}/{q}", anchor="w", fill=C["titolo"] if rim else "#55555c", font=F(8, True))
                    corto = n if len(n) <= 21 else n[:20] + "…"
                    c.create_text(44, y + ALTO_RIGA_LISTA / 2, text=corto, anchor="w", fill=col, font=F(8))
                    pc_ = 100 * rim / m["grimorio"] if m["grimorio"] and rim else 0
                    c.create_text(W - 10, y + ALTO_RIGA_LISTA / 2, text=f"{pc_:.0f}%" if rim else "-", anchor="e",
                                  fill=C["azzurro"] if rim else "#55555c", font=F(7, True))
                    c._righe.append((0, y, W, y + ALTO_RIGA_LISTA, n))
                    y += ALTO_RIGA_LISTA
            else:
                righe = DA.lista_sua(b["passi"], b["i"])
                c.create_text(10, y, text="OPPONENT · CARDS SEEN", anchor="w", fill=C["arancio"], font=F(8, True))
                c.create_text(W - 10, y, text=f"{sum(q for _n, q, _t in righe)} cards", anchor="e", fill=C["grigio"], font=F(7))
                y += 16
                c.create_text(10, y, text="up to this moment · not their whole deck", anchor="w", fill=C["muto"], font=F(6, True))
                y += 14
                if not righe:
                    c.create_text(10, y + 6, text="Nothing seen yet.", anchor="nw", fill=C["grigio"], font=F(8))
                    y += 24
                terre_ = False
                for n, q, terra in righe:
                    if terra and not terre_:
                        terre_ = True
                        y += 6
                        c.create_text(10, y + 6, text="LANDS", anchor="w", fill=C["muto"], font=F(6, True))
                        y += 14
                    if len(c._righe) % 2 == 0:
                        c.create_rectangle(4, y, W - 4, y + ALTO_RIGA_LISTA, fill="#141922", outline="")
                    c.create_text(10, y + ALTO_RIGA_LISTA / 2, text=f"{q}x", anchor="w", fill=C["titolo"], font=F(8, True))
                    c.create_text(36, y + ALTO_RIGA_LISTA / 2, text=n if len(n) <= 24 else n[:23] + "…", anchor="w", fill=C["testo"], font=F(8))
                    c._righe.append((0, y, W, y + ALTO_RIGA_LISTA, n))
                    y += ALTO_RIGA_LISTA
                if righe:
                    y += 10
                    c.create_rectangle(10, y, W - 10, y + 26, fill="#1e2431", outline="", tags="copia")
                    c.create_text(W / 2, y + 13, text=getattr(self, "_copiato", None) == b["x"].get("partita") and "Copied ✓" or "Copy as list",
                                  fill="#ffffff", font=F(8, True), tags="copia")
                    c._copia = (10, y, W - 10, y + 26, DA.testo_lista(righe))
                    y += 34
            c.configure(scrollregion=(0, 0, W, y + 10))

    def sopra_lista(self, e):
        """Il puntatore su una riga di una delle due liste: la carta grande accanto, come sulla tavola."""
        c = e.widget
        x, y = c.canvasx(e.x), c.canvasy(e.y)
        n = next((r_[4] for r_ in getattr(c, "_righe", []) if r_[1] <= y <= r_[3]), None)
        cp = getattr(c, "_copia", None)
        sopra_ = bool(cp and cp[0] <= x <= cp[2] and cp[1] <= y <= cp[3])
        c.configure(cursor="hand2" if sopra_ else "")
        if n == getattr(self, "_hover_nome", None):
            if n is not None and getattr(self, "_hover", None) is not None:
                self.metti_hover(e)
            return
        self.via_hover()
        self._hover_nome = n
        img = self.immagine_grande(n) if n else None
        if img is None:
            return
        tk = self.tk
        h = self._hover = tk.Toplevel(self.fin_board)
        h.overrideredirect(True)
        h.configure(bg="#0b0e14")
        try:
            h.attributes("-topmost", True)
        except Exception:      # noqa: BLE001
            pass
        tk.Label(h, image=img, bg="#0b0e14", bd=0).pack(padx=2, pady=2)
        self.metti_hover(e)

    def liste_chiuse(self):
        return self.__dict__.setdefault("_liste_chiuse", {"mio": False, "suo": False})

    def chiudi_lista(self, lato, chiusa=None):
        """Chiude (o riapre) una delle due liste del replayer verso il suo lato; la tavola prende il posto."""
        st = self.liste_chiuse()
        st[lato] = (not st[lato]) if chiusa is None else bool(chiusa)
        self.metti_liste()
        self.disegna_liste()
        return st[lato]

    def metti_liste(self):
        """Le liste aperte o chiuse, con la linguetta dell'outliner del Board: aperta ◀ per il tuo mazzo (si chiude verso sinistra) e ▶ per le sue carte, chiusa il
        contrario; chiusa resta la sola linguetta."""
        st = self.liste_chiuse()
        for lato, cv_, lab_ in (("mio", self.cv_lista_mio, self.b_lista["mio"]), ("suo", self.cv_lista_suo, self.b_lista["suo"])):
            if st[lato]:
                cv_.pack_forget()
            elif not cv_.winfo_manager():
                cv_.pack(side="left" if lato == "mio" else "right", fill="y", before=lab_)
            aperta = not st[lato]
            lab_.configure(text=("◀" if aperta else "▶") if lato == "mio" else ("▶" if aperta else "◀"))

    def clic_lista(self, e):
        """«Copy as list» negli appunti: le sue carte viste, una per riga. (Chiudere e riaprire: la linguetta, metti_liste.)"""
        c = e.widget
        x, y = c.canvasx(e.x), c.canvasy(e.y)
        cp = getattr(c, "_copia", None)
        if not cp or not (cp[0] <= x <= cp[2] and cp[1] <= y <= cp[3]):
            return None
        try:
            c.clipboard_clear(); c.clipboard_append(cp[4])
        except Exception:      # noqa: BLE001 - senza appunti niente copia
            return None
        self._copiato = self._board["x"].get("partita")
        self.disegna_liste()
        return cp[4]

    def disegna_board(self):
        """La tavola del momento: il campo dell'avversario, il tuo, la tua mano; accanto a ogni campo il cimitero e l'esilio di quel giocatore; le carte arrivate
        dal momento prima col filo azzurro e «NEW»; forza e costituzione sulle creature; a destra il racconto di cosa e' successo (12 nov 2026, Autore:
        «aggiungiamo cimitero e esilio, facciamo un replayer piu' avanzato e migliore degli attuali, di nuova generazione»)."""
        c = getattr(self, "cv_board", None)
        b = getattr(self, "_board", None)
        if c is None or not c.winfo_exists() or not b:
            return
        F = self.F
        mi_ = b.get("mom_idx") if b.get("modo") == "momenti" and not b.get("_pre") else None
        if mi_ and getattr(self, "_anima", False) and 0 < b["i"] < len(mi_) and mi_[b["i"]] - 1 > mi_[b["i"] - 1]:
            # un momento avanti: prima, senza animazioni, la tavola all'azione subito prima del momento; poi il momento anima solo la sua azione, come in
            # Every action (16 nov 2026: animare in un colpo tutto quello che era successo dal momento prima mescolava l'ordine di pila, voli e combattimento)
            passi_m, i_m = b["passi"], b["i"]
            b["_pre"], b["passi"], b["i"], self._anima = True, b["azioni_passi"], mi_[i_m] - 1, False
            try:
                self.disegna_board()
            finally:
                b["passi"], b["i"], self._anima = passi_m, i_m, True
                b.pop("_pre", None)
        import mazzi_salvati as MS
        self.disegna_liste()
        # i momenti
        cp = self.cv_passi
        cp.delete("all")
        self._box_passi = []
        x = 0
        azioni_ = b.get("modo") == "azioni"
        if azioni_:     # in Every action la striscia sono i turni: il clic porta alla prima azione del turno
            visti_, voci = set(), []
            for i, p_ in enumerate(b["passi"]):
                if p_[2] not in visti_:
                    visti_.add(p_[2])
                    voci.append((i, p_[0].split(" · ")[0]))
        else:
            voci = [(i, p_[0]) for i, p_ in enumerate(b["passi"])]
        t_ora = b["passi"][b["i"]][2]
        for i, nome in voci:
            w = max(64, len(nome) * 7 + 20)
            on = (b["passi"][i][2] == t_ora) if azioni_ else i == b["i"]
            mio_ = nome.startswith("You") or nome == "Opening hand"
            chip(cp, x, 4, x + w, 32, nome, on, F(7, True), scritta=None if on else (C["testo"] if mio_ else C["grigio"]))
            if i == b.get("svolta"):        # il punto di svolta: il filo d'oro intorno
                cp.create_rectangle(x, 4, x + w - 1, 31, outline="#ffd23f")
            self._box_passi.append((x, x + w, i))
            x += w + 4
        cp.configure(scrollregion=(0, 0, x, 36))
        scelto = next((bp for bp in self._box_passi if (b["passi"][bp[2]][2] == t_ora if azioni_ else bp[2] == b["i"])), None)
        if scelto:     # il passo scelto resta in vista
            x0, x1, _i = scelto
            W_ = max(cp.winfo_width(), 400)
            if x > W_:
                cp.xview_moveto(max(0, (x0 - W_ / 2) / x))
        # la tavola
        c.delete("all")
        prima_zone = list(getattr(self, "_box_zona", []))        # dove stavano le carte nel passo disegnato prima (per farle scorrere)
        self._firme_prima = list(getattr(self, "_frecce_firme", []) or [])
        self._prima_pezzi = dict(getattr(self, "_pezzo_id", {}) or {})
        prima_pile = None
        anima = getattr(self, "_anima", False)
        self._anima = False
        self._anima_ora = anima         # l'ombra sfuma solo andando avanti di un passo (ombra_board)
        self._durata_anim = 0
        self._ritardo_frecce = 0
        self.ferma_animazione()
        self._img_coperte = []          # le coperture del passo prima (pile, vite): finite con lui
        self._pila_prima, self._pila_ora = getattr(self, "_pila_ora", None), None
        self._box_zona, self._nuove = [], []
        self._box_pile, self._box_carte = [], []
        self.via_hover()
        W, H = max(c.winfo_width(), 900), max(c.winfo_height(), 560)
        cr = self.tela_racconto()           # il racconto staccato nella sua finestra (13 nov 2026), o None
        larga_col = LARGA_RACCONTO if cr is None else LARGA_PILA_SOLA
        Wt = W - LARGA_RACCONTO - 12 if cr is None else W     # col racconto staccato la tavola prende tutto: la pila sta sul tappeto
        nome, f, _t, rel = b["passi"][b["i"]][:4]
        prima = b["passi"][b["i"] - 1][1] if b["i"] > 0 else None
        if mi_ and 0 < mi_[b["i"]] <= len(b["azioni_passi"]):       # nei Moments da Every action: la foto dell'azione subito prima
            prima = b["azioni_passi"][mi_[b["i"]] - 1][1]
        if getattr(self, "b_segna", None) is not None:
            segnato_ = DA.segnato(b["x"].get("partita"), b.get("modo", "momenti"), b["i"])
            self.b_segna.metti("Bookmarked ★" if segnato_ else "Bookmark", segnato_)
        if getattr(self, "b_nota", None) is not None:
            ha_ = bool(DA.nota_partita(b["x"].get("partita")) or DA.nota_segnalibro(b["x"].get("partita"), b.get("modo", "momenti"), b["i"]))
            self.b_nota.metti("Note ✎" if ha_ else "Note", ha_)
        self._pos_id, self._pos_vita = {}, {}       # dove stanno le carte (per id di Arena) e i cuori delle vite: le frecce partono e arrivano li'
        self._tappeto_disegno(c, b, f, nome, rel, prima, Wt, H)      # la tavola: il tappetino (disegno_tappeto, 14 nov 2026)
        # il racconto del momento: nella colonna a destra o, staccato, nella sua finestra (13 nov 2026, Autore: «la chat staccabile se vogliamo aumentare le
        # dimensioni del campo»); staccato, sulla tavola resta la colonna stretta della magia in pila, da cui partono le frecce verso i bersagli
        xr = Wt + 12
        c.create_rectangle(xr, 0, W, H, fill="#11151c", outline="")
        if cr is None:
            c.create_text(xr + 14, 16, text="WHAT HAPPENED", anchor="w", fill=C["muto"], font=F(7, True))
            i_s = c.create_text(W - 12, 16, text="⧉ Detach", anchor="e", fill=C["accento"], font=F(7, True), tags="stacca")
            bb_s = c.bbox(i_s)
            self._box_stacca = (bb_s[0] - 4, bb_s[1] - 4, bb_s[2] + 4, bb_s[3] + 4) if bb_s else None
            cc, x0_r, larga_r, Hc = c, xr, LARGA_RACCONTO, H
        else:
            self._box_stacca = None
            c.create_text(xr + 14, 16, text="ON THE STACK", anchor="w", fill=C["muto"], font=F(7, True))
            cc = cr
            cc.delete("all")
            larga_r, Hc = max(cc.winfo_width(), 260), max(cc.winfo_height(), 300)
            x0_r = 0
            cc.create_rectangle(0, 0, larga_r, Hc, fill="#11151c", outline="")
            cc.create_text(14, 16, text="WHAT HAPPENED", anchor="w", fill=C["muto"], font=F(7, True))
        tit_ = cc.create_text(x0_r + 14, 25, text=nome + ("   ★ turning point" if b["i"] == b.get("svolta") else ""), anchor="nw",
                              fill="#ffd23f" if b["i"] == b.get("svolta") else C["titolo"], font=F(10, True), width=larga_r - 28)
        y = max(58, (cc.bbox(tit_) or (0, 0, 0, 46))[3] + 14)     # un nome lungo va a capo verso il basso, non sopra «WHAT HAPPENED» (debug del 12 nov 2026)
        for tit_n, txt_n in (("YOUR NOTE ON THIS SPOT", DA.nota_segnalibro(b["x"].get("partita"), b.get("modo", "momenti"), b["i"])),
                             ("YOUR NOTE ON THIS GAME", DA.nota_partita(b["x"].get("partita")))):
            if txt_n:       # R3: le tue note, in testa al racconto
                i_n = cc.create_text(x0_r + 14, y, text=f"✎ {tit_n} · {txt_n}", anchor="nw", fill="#e8d28a", font=F(8), width=larga_r - 28)
                y = (cc.bbox(i_n) or (0, 0, 0, y + 14))[3] + 6
        # l'EV della giocata e del turno, a elenco (18 nov 2026, Autore: «Mettiamo gli argomenti in elenco: EV Giocata e punteggio, poi sotto EV
        # registrato nella media e infine sotto la differenza totale. EV giocata positiva sempre in verde e negativa sempre in rosso ... se la giocata ha una
        # media di game di confronto bassa allora di colore grigio», «togli dai replayer you made an error non ragioniamo piu' cosi'»): niente giudizi
        # poi semplificato (18 nov 2026, Autore: «stare dietro ai dati di ev e' davvero un inferno ... idee per semplificare», «procedi con 1 2 3 4»): una
        # frase con la probabilita' di vincere prima e dopo, un bollino meglio / peggio del solito, i numeri solo col mouse sopra il bollino, e niente sotto
        # SOGLIA_PARLA punti di scarto
        # poi solo EV + e EV - dell'Hero (18 nov 2026 sera, «a your chance to win non funziona»): una riga col numero, verde o rosso (grigio con poche
        # partite di confronto); sull'EV negativo «Why?» apre la spiegazione e sposta in giu' quello che c'e' sotto
        import ev_partita as EV_
        voto_ = self.voto_fase(b) if b.get("modo") == "azioni" else None
        y = self.disegna_win_chance(cc, b, x0_r, larga_r, y)
        y = self.disegna_range(cc, b, x0_r, larga_r, y)
        if voto_ is not None:
            # i punti della partita in un posto fisso, subito sotto la win chance (stesso giorno, Autore: «la tabellina di accumulo pti devi tenerla sotto il
            # grafo di win chance o la vediamo andare su e giu' e diventiamo matti»: dopo PHASE TOTAL saltava con l'altezza del voto della fase)
            sp_ = self.segnapunti(b)
            if sp_ is not None:
                y = self.disegna_segnapunti(cc, sp_, x0_r, larga_r, y)
            y = self.disegna_voto_fase(cc, b, voto_, x0_r, larga_r, y)
        for k_v, z in enumerate(self.blocchi_ev(b) if voto_ is None else []):
            col_v = C["muto"] if z["n"] < EV_.MINIMO else C["verde"] if z["diff"] > 0 else C["rosso"]
            i_v = cc.create_text(x0_r + 14, y, text=f"EV {z['diff']:+.1f}".replace("-", "−"), anchor="nw", fill=col_v, font=F(12, True))
            bv_ = cc.bbox(i_v) or (x0_r + 14, y, x0_r + 90, y + 18)
            cc.create_text(bv_[2] + 10, (bv_[1] + bv_[3]) / 2, text=z["titolo"], anchor="w", fill=C["muto"], font=F(8, True))
            y = bv_[3] + 4
            if z["diff"] < 0 and z["perche"]:
                tag_w = f"ev_why_{k_v}"
                i_w = cc.create_text(x0_r + 14, y, text="▸ Why?", anchor="nw", fill=C["accento"], font=F(8, True), tags=(tag_w,))
                bw_ = cc.bbox(i_w) or (x0_r + 14, y, x0_r + 60, y + 14)
                y = bw_[3] + 6
                testo_w = "\n".join("• " + r_ for r_ in z["perche"])

                def _apri(_e, cc=cc, i_w=i_w, tag_w=tag_w, testo_w=testo_w, x_=x0_r + 22, larga_=larga_r - 40, xc_=x0_r):
                    aperti = cc.find_withtag(tag_w + "_testo")
                    yb_ = (cc.bbox(i_w) or (0, 0, 0, 0))[3] + 4
                    if aperti:      # chiudi: via il testo, su quello che c'e' sotto
                        h_ = (cc.bbox(aperti[0]) or (0, 0, 0, 0))[3] - yb_ + 6
                        cc.delete(tag_w + "_testo")
                        for it_ in cc.find_all():
                            bb_ = cc.bbox(it_)
                            if bb_ and bb_[1] >= yb_ and bb_[0] >= xc_ - 2:
                                cc.move(it_, 0, -h_)
                        cc.itemconfigure(i_w, text="▸ Why?")
                        return
                    # solo la colonna del racconto (non staccato, la tela e' la stessa della tavola)
                    sotto = [it_ for it_ in cc.find_all() if (cc.bbox(it_) or (0, -1, 0, 0))[1] >= yb_ and (cc.bbox(it_) or (-9, 0, 0, 0))[0] >= xc_ - 2]
                    i_t = cc.create_text(x_, yb_, text=testo_w, anchor="nw", fill=C["testo"], font=F(8), width=larga_, tags=(tag_w + "_testo",))
                    h_ = (cc.bbox(i_t) or (0, 0, 0, yb_))[3] - yb_ + 6
                    for it_ in sotto:
                        cc.move(it_, 0, h_)
                    cc.itemconfigure(i_w, text="▾ Why?")
                cc.tag_bind(tag_w, "<Button-1>", _apri)
            y += 6
        # l'Opponent che lascia danni sul tavolo (18 nov 2026, Autore: «quando oppo attacca con 2 creature su 3 e io ho board vuoto, oppo ha lasciato
        # punti sul tavolo?»): sul primo passo del suo combattimento, se ha attaccato con una parte di chi poteva e tu non avevi creature stappate
        tc_ = self.tenuto_passo(b)
        if tc_ is not None:
            i_h = cc.create_text(x0_r + 14, y, text=(f"▲ OPPONENT HELD BACK · attacked with {tc_[0]} of {tc_[1]} ready creatures while you had no untapped "
                                                    "blocker: damage left on the table (a clue: the creature kept home may be guarding against your next turn)"),
                                 anchor="nw", fill=C["verde"], font=F(8, True), width=larga_r - 28)
            y = (cc.bbox(i_h) or (0, 0, 0, y + 14))[3] + 6
        sk_ = self.chiave_passi(b).get(b["i"])
        if sk_ is not None:     # R7: un momento chiave, col salto del vantaggio
            i_k = cc.create_text(x0_r + 14, y, text=(f"◆ KEY MOMENT · {abs(sk_):.1f} win-probability points {'gained' if sk_ > 0 else 'lost'} against the usual"
                                                    if self.chiave_ev(b) is not None else
                                                    f"◆ KEY MOMENT · {abs(sk_):.0f} points of advantage to {'you' if sk_ > 0 else 'the opponent'}"), anchor="nw",
                                 fill="#2f9bff" if sk_ > 0 else "#f0ad4e", font=F(8, True), width=larga_r - 28)
            y = (cc.bbox(i_k) or (0, 0, 0, y + 14))[3] + 6
        for _c, nf_ in self.filtro_passi(b).get(b["i"], []):     # i filtri accesi veri in questo momento (15 nov 2026)
            cc.create_image(x0_r + 14, y + 1, image=DG.spot_filtro(12, SEGNO_FILTRO, "#ffffff", becco=False), anchor="nw")
            i_fl = cc.create_text(x0_r + 32, y, text=f"YOUR FILTER · {nf_}", anchor="nw", fill=SEGNO_FILTRO, font=F(8, True), width=larga_r - 46)
            y = (cc.bbox(i_fl) or (0, 0, 0, y + 14))[3] + 6
        for col_i, tx_i in self.righe_info(f):      # cosa Arena ti ha chiesto e detto in questo passo (16 nov 2026, «vai monta»)
            i_i = cc.create_text(x0_r + 14, y, text=tx_i, anchor="nw", fill=col_i, font=F(8, True), width=larga_r - 28)
            y = (cc.bbox(i_i) or (0, 0, 0, y + 14))[3] + 6
        if cr is None:
            yp = y
        if cr is not None:      # dove va la carta in pila sulla tavola: in cima alla colonna stretta (nel racconto, sotto il titolo)
            yp = 36
        pila_box = None
        if rel and rel["tipo"] == "spell":      # la magia (o l'abilita') in pila, da cui partono le frecce verso i bersagli
            chi = "You" if rel["mio"] else "Opponent"
            pila_box = getattr(self, "_pila_mat", None)        # la carta sta sul tappeto, nella zona STACK: le frecce viola partono da li'
            self._pila_ora = (pila_box, rel["nome"], bool(rel.get("mio")), bool(rel.get("ab"))) if pila_box else None
            hp = 0
            cc.create_text(x0_r + 14, y, text=f"ON THE STACK · {chi.upper()}" + (" · ABILITY OF" if rel["ab"] else "") + f" · {rel['nome']}", anchor="w",
                           fill="#b58cff", font=F(7, True), width=larga_r - 28)
            y += 26
            cima_ = ((f or {}).get("pila") or [None])[0]
            tx_ab = ((f or {}).get("info") or {}).get("abt", {}).get(cima_[4]) if cima_ and rel["ab"] else None
            if tx_ab:       # quale abilita' (il potere del planeswalker col suo costo in fedelta'): il testo dal database di Arena (16 nov 2026)
                import re as _re
                costo_ = next((("+" if m_.group(1) == "got" else "−") + m_.group(2) for _m, t_ in b["passi"][b["i"]][4]
                               for m_ in [_re.match(_re.escape(rel["nome"]) + r" (got|lost) (\d+) loyalty", t_)] if m_), "")
                i_ab = cc.create_text(x0_r + 14, y - 8, text=(f"{rel['nome']} {costo_}: " if costo_ else "") + f"“{tx_ab}”", anchor="nw", fill="#d6c2ff",
                                      font=F(8), width=larga_r - 28)
                y = (cc.bbox(i_ab) or (0, 0, 0, y + 14))[3] + 10
            dove_n = {"cim_mio": "in your graveyard", "cim_suo": "in the opponent's graveyard", "esi_mio": "in your exile", "esi_suo": "in the opponent's exile",
                      "pila": "on the stack", "mano": "in hand", "grimorio": "in the library"}
            for _i, (z_, _l, n_) in (rel.get("fuori") or {}).items():      # i bersagli che non sono in campo: una contromagia, una rianimazione
                cc.create_text(x0_r + 14, y - 6, text=f"→ {n_ or 'a card'} {dove_n.get(z_, '')}", anchor="w", fill="#b58cff", font=F(7, True),
                               width=larga_r - 28)
                y += 16
            nc = len(rel.get("colpiti") or [])
            if nc:      # l'effetto: quanti permanenti ha tolto
                cc.create_text(x0_r + 14, y - 6, text=f"REMOVED {nc} PERMANENT{'S' if nc > 1 else ''}" + ("  ·  a sweeper" if nc >= 3 else ""), anchor="w",
                               fill="#ff5d5d", font=F(7, True))
                y += 16
        elif rel and rel["tipo"] == "comb":
            nb = len(rel["blocchi"])
            cc.create_text(x0_r + 14, y, text=f"COMBAT · {len(rel['att'])} attacking · {nb} block{'s' if nb != 1 else ''}", anchor="w", fill="#ff6b6b",
                           font=F(7, True))
            y += 22
        elif cr is not None:
            c.create_text(xr + 14, 36, text="nothing on the stack", anchor="w", fill=C["grigio"], font=F(7))
        self.frecce_board(c, rel, pila_box, W, H)
        self.metti_giocabili(c, f)
        self.metti_possibili(c, f)
        self.metti_sguardo(c, f)
        if "spalla" not in b:       # cosa diceva la spalla (solo nei limited seguiti dal companion)
            try:
                import replay_log as RL
                b["spalla"] = RL.spalla(b["x"].get("partita"))
            except Exception:      # noqa: BLE001 - senza diario niente spalla
                b["spalla"] = {}
        t_passo = b["passi"][b["i"]][2]
        consigli = [(None, "THE COMPANION SAID")] + [("spalla", s_) for s_ in b["spalla"].get(t_passo, [])] if b["spalla"].get(t_passo) else []
        if b.get("modo") == "azioni" or mi_:
            pas_, i_p = (b["azioni_passi"], mi_[b["i"]]) if mi_ else (b["passi"], b["i"])
            self.danni_board(c, pas_[i_p][5], pas_[i_p][6] if len(pas_[i_p]) > 6 and "Damage" not in pas_[i_p][0] else None)
            self.guadagno_board(c, prima, f, pas_[i_p][5])
            alza_icone(c)
            righe_r = [(m_, "▸ " + t_) for m_, t_ in pas_[i_p][4]]       # quest'azione, in testa, poi la spalla, poi il resto del turno
            prima_ = [ev_ for p_ in pas_[:i_p] if p_[2] == pas_[i_p][2] for ev_ in p_[4]]
            righe_r += consigli
            if prima_:
                righe_r += [(None, "EARLIER THIS TURN")] + list(reversed(prima_))
        else:
            righe_r = self.racconto(b["i"])
            if righe_r is not None or consigli:
                righe_r = consigli + (righe_r or [])
        if righe_r is None:
            cc.create_text(x0_r + 14, y, text="No turn record for this game.", anchor="w", fill=C["grigio"], font=F(8))
        elif not righe_r:
            cc.create_text(x0_r + 14, y, text="Nothing cast or attacked.", anchor="w", fill=C["grigio"], font=F(8))
        for mio_, testo in righe_r or []:
            if y > Hc - 24:
                cc.create_text(x0_r + 14, y, text="…", anchor="w", fill=C["grigio"], font=F(9, True))
                break
            if mio_ is None:        # un titoletto
                cc.create_text(x0_r + 14, y + 6, text=testo, anchor="w", fill=C["muto"], font=F(7, True))
                y += 20
                continue
            sp_ = mio_ == "spalla"
            cc.create_oval(x0_r + 14, y + 4, x0_r + 22, y + 12, fill="#b58cff" if sp_ else "#2f9bff" if mio_ else "#f0ad4e", outline="")
            forte = testo.startswith("▸ ")
            i_ = cc.create_text(x0_r + 30, y, text=testo[2:] if forte else testo, anchor="nw", fill="#d6c8ff" if sp_ else C["titolo"] if forte else C["testo"],
                               font=F(7 if sp_ else 8, forte), width=larga_r - 46)      # dall'alto: a capo non copre la riga dopo
            bb = cc.bbox(i_)
            y = (bb[3] if bb else y + 16) + 6
        # il combattimento (14 nov 2026, Autore: «le carte prima si tappano - dichiarano bersaglio - dichiarazione difesa - poi dichiarano freccia difesa -
        # le carte compiono una alla volta il tragitto completo - poi cambio colore e morte»): nessuna avanzata alla dichiarazione (la prima versione dello
        # stesso giorno spostava attaccanti e bloccanti di qualche pixel); il tragitto completo si fa nel passo del danno (anima_board, i «colpo»)
        self._spinte_anim, self._prima_spinte, self._spinte = [], {}, {}
        if anima and prima is not None:
            # le frecce, una alla volta, ognuna la sua azione; le frecce gia' dichiarate al passo prima (lo stesso attacco nel passo dei blocchi e del danno)
            # restano a vista: compaiono solo le nuove
            gia_ = set(getattr(self, "_firme_prima", []) or [])
            ids_ = [it__ for it__, fi__ in zip(getattr(self, "_frecce_ids", []), getattr(self, "_frecce_firme", [])) if fi__ not in gia_]
            for it__ in ids_:
                c.itemconfigure(it__, state="hidden")
            po_, pp_ = getattr(self, "_pila_ora", None), getattr(self, "_pila_prima", None)
            arriva_ = bool(po_) and not (pp_ and pp_[1] == po_[1])
            # una magia gia' in pila che si risolve: prima le frecce, poi l'effetto (14 nov 2026, Autore: «alcune abilita' come Settle the Wreckage attivano
            # le frecce solo dopo aver esiliato le creature»); una magia che arriva adesso in pila: prima la carta, poi la freccia («la spell deve andare
            # nella pila, fare la freccia ...»)
            prima_frecce = bool(ids_) and rel and rel.get("tipo") == "spell" and not arriva_
            self._ritardo_frecce = 0
            if prima_frecce:
                inizio_ = PAUSA_VOLI + getattr(self, "_ritardo_ombra", 0)
                for k__, it__ in enumerate(ids_):
                    self._anim_after.append(self.fin_board.after(inizio_ + k__ * PAUSA_FRECCIA,
                                                                 lambda it__=it__: c.winfo_exists() and c.itemconfigure(it__, state="normal")))
                self._ritardo_frecce = inizio_ + len(ids_) * PAUSA_FRECCIA + PAUSA_VOLI - getattr(self, "_ritardo_ombra", 0)
            rit_f = self._ritardo_frecce
            self.anima_board(c, prima_zone, prima_pile, prima, f)
            if ids_ and not prima_frecce:        # dopo i voli
                inizio_ = (self._durata_anim + PAUSA_FRECCIA) if getattr(self, "_durata_anim", 0) else PAUSA_VOLI + getattr(self, "_ritardo_ombra", 0)
                for k__, it__ in enumerate(ids_):
                    self._anim_after.append(self.fin_board.after(inizio_ + k__ * PAUSA_FRECCIA,
                                                                 lambda it__=it__: c.winfo_exists() and c.itemconfigure(it__, state="normal")))
                self._durata_anim = inizio_ + (len(ids_) - 1) * PAUSA_FRECCIA
            elif prima_frecce:
                self._durata_anim = max(getattr(self, "_durata_anim", 0), rit_f)
            self._durata_anim = max(self._durata_anim, getattr(self, "_ritardo_ombra", 0))      # anche solo l'ombra che passa dall'altra parte
        self._anim_fino = time.monotonic() + getattr(self, "_durata_anim", 0) / 1000       # fino a quando il passo si muove (le pedine aspettano)
        if b["i"] == len(b["passi"]) - 1:       # l'ultimo passo: la schermata finale, quando il passo ha finito di muoversi
            ritardo_f = (getattr(self, "_durata_anim", 0) + PAUSA_FASI) if anima else 0
            self._anim_after.append(self.fin_board.after(int(ritardo_f), lambda: c.winfo_exists() and self.schermata_finale(c, b, Wt, H)))
        self.disegna_pila_aperta(c, f, W, H)
        self.disegna_controlli()

    def _tappeto_disegno(self, c, b, f, nome, rel, prima, Wt, H):
        """La tavola del momento sul tappetino (disegno_tappeto; 13-14 nov 2026, Autore: «un vero tappetino da gioco con la vista delle mie carte in mano e
        quelle in mano all'avversario di dorso con copertina carte dell'app»): il fondo come un'immagine, ogni carta come un oggetto suo della tela, cosi'
        animazioni, frecce, danni, hover, cimitero ed esilio aperti funzionano come con le tre fasce di prima (_box_zona, _pos_id, _pos_vita, _box_carte,
        _box_pile, _nuove). Le scritte GRAVEYARD ed EXILE sono testi della tela."""
        import disegno_tappeto as DT
        from PIL import ImageTk
        Wt, H = int(Wt), int(H)
        tp = getattr(self, "_tappeto", None)
        mano_on = self.mano_in_vista()
        if tp is None or (tp.W, tp.H, tp.mano) != (Wt, H, mano_on):
            tp = self._tappeto = DT.Tappeto(Wt, H, mano_on)
        try:
            grim = (DA.lista_mia(b["x"].get("deck"), f, rel) or {}).get("grimorio")
        except Exception:      # noqa: BLE001 - senza la lista il grimorio non si conta
            grim = None
        mio = nome.startswith("You") or nome == "Opening hand"
        titolo = "Opening hand · the hand you kept" if nome == "Opening hand" else nome
        # la carta messa nel grimorio in questo passo: in cima o in fondo, la pillola sul mazzo (15 nov 2026, il gruppo del grimorio)
        messa = {}
        try:
            for mio_e, tx_e in (b["passi"][b["i"]][4] if b.get("modo") == "azioni" else []):
                for chiave_e, parola in (("top", "put on top of the library"), ("bottom", "put on the bottom of the library"), ("mid", "from the top")):
                    if parola in tx_e:
                        messa["mio" if mio_e else "suo"] = chiave_e
        except Exception:      # noqa: BLE001 - senza il passo niente pillola
            messa = {}
        if messa:
            f = dict(f, messa=messa)
        base, pezzi, info = tp.disegna(f, prima, rel, None, grim, titolo, mio, pezzi=True)
        self._base_prima, self._base_ora = getattr(self, "_base_ora", None), base       # il fondo del passo prima: le vite com'erano (anima_board)
        self._img_tappeto = ImageTk.PhotoImage(base)
        c.create_image(0, 0, image=self._img_tappeto, anchor="nw")
        # i gruppi del passo prima (terre e pedine uguali col xN): la loro immagine resta viva per questo passo (anima_board)
        self._gruppi_prima, self._img_pezzi_prima = getattr(self, "_gruppi_ora", {}) or {}, getattr(self, "_img_pezzi", [])
        self._gruppi_ora, self._gruppo_item = {}, {}
        self._pila_img_prima, self._pila_img_ora = getattr(self, "_pila_img_ora", None), None       # la pila del passo prima (anima_board)
        self._img_pezzi, mani = [], []
        giocabili = {}
        self._mano_suo_items = []
        self._pila_item = None
        self._pezzo_id = {}
        self._pezzo_gruppo = {}
        self._pedine_nomi = getattr(self, "_pedine_nomi", {})
        for q in pezzi:
            im = ImageTk.PhotoImage(q["img"])
            self._img_pezzi.append(im)
            it = c.create_image(round(q["xy"][0]), round(q["xy"][1]), image=im, anchor="nw")
            bx = q["box"]
            if q["zkey"] == "mano_suo":     # il suo ventaglio, da sinistra: la carta pescata (l'ultima) entra al suo posto (anima_board)
                self._mano_suo_items.append((it, tuple(q["box"])))
            if q["zkey"] == "pila":         # la carta in pila: nascosta finche' non ci arriva quella che vola dalla mano (anima_board)
                self._pila_item = it
                self._pila_img_ora = (im, (round(q["xy"][0]), round(q["xy"][1])))
            if q["zkey"] in ("mio", "suo") and q["ids"]:       # per gruppo (nome, tappata): la sua immagine e quante carte; due gruppi uguali: ambiguo
                k_g = (q["zkey"], q["nome"], bool(q["tap"]))
                self._gruppi_ora[k_g] = None if k_g in self._gruppi_ora else (im, len(q["ids"]))
                self._gruppo_item[it] = k_g
            if q["zkey"] in ("mio", "suo") and len(q["ids"]) == 1:      # una carta sola (non un gruppo di pedine): si tappa e si stappa da sola
                self._pezzo_id[q["ids"][0]] = (it, q["box"], q["tap"], q["nome"])
            elif q["zkey"] in ("mio", "suo") and q["ids"]:      # dentro un gruppo (le terre uguali col xN): anche lei si gira (21 nov 2026, sotto)
                for id_q in q["ids"]:
                    self._pezzo_gruppo[id_q] = (it, q["box"], q["tap"], q["nome"])
            if q["zkey"] in ("mio", "suo", "mano"):
                self._box_zona.append((q["zkey"], q["nome"], bx, q["tap"], it, q["ped"]))
            elif q["zkey"].startswith("esi_mano_"):      # la fila PLAYABLE accanto alla mano: la carta che diventa giocabile ci vola (anima_board)
                giocabili.setdefault(q["zkey"][9:], []).append((q["nome"], bx, it))
            for id_ in q["ids"]:
                self._pos_id[id_] = bx
            if q["nuova"]:      # anche le pedine: scorrono dalla carta in pila che le crea (14 nov 2026)
                self._nuove.append((q["zkey"], q["nome"], bx, q["tap"], it, q["ped"], tuple(q["ids"])))
            if q["ped"] and q.get("grp"):
                self._pedine_nomi[q["nome"]] = q["grp"]
            if q["nome"]:
                (mani if q["zkey"] == "mano" else self._box_carte).append(tuple(q.get("vis") or bx) + (q["nome"],))
        self._mano_vis = list(mani)          # la parte che si vede di ogni carta della tua mano (le giocabili si accendono li')
        self._box_carte += list(reversed(mani))     # nella mano a ventaglio la carta di destra sta sopra: il passaggio del mouse la trova prima
        for i_a, h_a in (info.get("attaccati") or {}).items():      # l'aura attaccata sta sul riquadro della carta che la porta (frecce, voli)
            if h_a in self._pos_id:
                self._pos_id[i_a] = self._pos_id[h_a]
        # le aure attaccate in questo passo: volano sulla carta che le porta e restano dietro di lei (anima_board), col nome e la carta che le porta
        nomi_att = {i_: n_ for v_ in (f.get("segni") or {}).values() for i_, n_ in v_.get("porta") or []}
        self._attaccate_nuove = [(nomi_att.get(i_a), h_a) for i_a, h_a in (info.get("attaccati_nuovi") or {}).items() if nomi_att.get(i_a)]
        # le carte esiliate sotto una fonte in questo passo (15 nov 2026, «esilia finche'»): volano sotto la fonte invece che sulla pila dell'esilio
        self._sotto_nuove = [(n_s, h_s) for h_s, ns_ in (info.get("sotto_nuovi") or {}).items() for n_s in ns_]
        self._tappeto_k = tp.k
        self._giocabili = giocabili
        if prima is not None:       # le carte arrivate in mano dal passo prima: la pescata le fa volare dal grimorio (anima_board)
            in_piu = {}
            for n_ in f.get("mano") or []:
                in_piu[n_] = in_piu.get(n_, 0) + 1
            for n_ in prima.get("mano") or []:
                in_piu[n_] = in_piu.get(n_, 0) - 1
            for z in reversed([z for z in self._box_zona if z[0] == "mano"]):      # le ultime del ventaglio per prime
                if in_piu.get(z[1], 0) > 0:
                    in_piu[z[1]] -= 1
                    self._nuove.append(z)
        self._box_grimorio = (info.get("grimori") or {}).get("lib_mio")
        # dove stanno grimori, cimiteri, esili e la pila: le carte scorrono da li' e verso li' (anima_board)
        self._zone_carte = dict(info.get("grimori") or {}, **(info.get("carte_pile") or {}))
        self._stack_box = tp.box(tp.L["STACK"])
        # la riserva di mana di ognuno nella sua vaschetta (15 nov 2026, Autore: «costruiamolo invece in basso a sx poco sotto l'area your lands»): il mana
        # che resta a galla (players.manaPool di Arena); quello del pagamento ci arriva volando dalle terre (anima_board)
        self._pool_n, self._pool_col, self._pool_badge = {}, {}, {}
        for chi_p, k_p in (("mio", 0), ("suo", 1)):
            mp_p = list((f.get("mp") or ([], []))[k_p] or [])
            self._pool_n[chi_p] = len(mp_p)
            self._pool_col[chi_p] = list(mp_p)
            if mp_p and f"pool_{chi_p}" in tp.L["ZONE"]:
                # oltre 6 simboli i colori uguali stanno nello stesso posto col numero (15 nov 2026)
                posti_p, lato_p, idx_p = tp.posti_pool_gruppi(chi_p, mp_p)
                conta_p = {}
                for (x_p, y_p), col_p, i_p in zip(posti_p, mp_p, idx_p):
                    img_p = self.immagine_mana(col_p, lato_p)
                    if img_p is not None:
                        c.create_image(round(x_p), round(y_p), image=img_p, tags="pool")
                    conta_p[i_p] = (conta_p.get(i_p, (0,))[0] + 1, x_p, y_p, lato_p)
                for i_p, (n_p, x_p, y_p, lato_p) in conta_p.items():
                    if n_p > 1:
                        self._pool_badge[(chi_p, i_p)] = self.badge_mana(c, x_p, y_p, lato_p, n_p, "pool")
        self._mano_mio_box = (info.get("mani") or {}).get("mio")
        self._mano_suo_box = ((info.get("mani") or {}).get("suo")      # col tavolo ingrandito la sua mano sta in mezzo alla sua fila dietro
                              or (tp.X(tp.L["MANO"][0]) - tp.K(46), -tp.K(120), tp.X(tp.L["MANO"][0]) + tp.K(46), tp.K(20)))
        if DT.PEDINE_ATTESA:        # un'immagine di pedina in arrivo: quando c'e', la tavola si ridisegna (senza animazione)
            self._attesa_pedine(15)
        self._box_carte += info["scatole"]          # la cima di cimiteri ed esili, la carta in pila
        self._pos_vita.update(info["vite"])
        titoli = {"cim": "GRAVEYARD", "esi": "EXILE"}
        for k, (bx, carte) in info["pile"].items():
            if carte:
                self._box_pile.append(tuple(bx) + (titoli[k[:3]], k, carte))
        self._etichette_pile = {}
        for k, (x, y, testo, col) in info.get("etichette", {}).items():
            self._etichette_pile[k] = c.create_text(x, y, text=testo, fill="#%02x%02x%02x" % col, font=self.F(7, True))
        self._pila_mat = info["pila"]
        self._pila_sotto = dict(info.get("pila_sotto") or {})      # le carte sotto la cima, la loro barra del nome (le frecce verso una carta in pila)
        pila_f = f.get("pila") or []
        if info["pila"] and pila_f and not (rel and rel.get("tipo") == "spell"):        # la pila senza la magia come relazione: c'e' lo stesso
            self._pila_ora = (info["pila"], pila_f[0][0], bool(pila_f[0][1]), bool(pila_f[0][2]))
        self.ombra_board(c, tp, b, rel, nome, Wt, H)       # dopo la pila: la pila resta fuori dall'ombra

    def chi_agisce(self, b, rel, nome):
        """Chi fa l'azione del passo: True tu, False l'avversario. La magia o l'abilita' in pila, se no il primo evento del passo che ha un giocatore (Every
        action: chi gioca, chi paga, chi blocca...), se no chi e' di turno."""
        if rel and rel.get("tipo") == "spell":
            return bool(rel.get("mio"))
        passo = b["passi"][b["i"]] if b.get("passi") else None
        if b.get("modo") == "azioni" and passo and len(passo) > 4:
            for m_, _t in passo[4]:
                if m_ is not None:
                    return bool(m_)
        return nome.startswith("You") or nome == "Opening hand"

    def ombra_board(self, c, tp, b, rel, nome, Wt, H):
        """Un'ombra leggera sulla meta' del tavolo di chi non agisce in questo passo (14 nov 2026, Autore: «mettiamo in leggera ombra il giocatore che non
        gioca rispetto a quello che gioca, cosi' capiamo chi sta interagendo»): sopra le carte, sotto frecce e voli. Sfumata verso la linea di mezzo, e la
        pila resta fuori, con un bordo morbido (stesso giorno: «la pila esclusa dal taglio ombra e l'ombra non con taglio netto ma sfumato»). Quando cambia chi
        agisce e si va avanti di un passo, l'ombra lascia una meta' e arriva sull'altra sfumando (stesso giorno: «transizione morbida tra il turno di player e
        oppo, non di scatto ombra accesa o spenta ma morbida»), e le azioni del passo partono dopo (_ritardo_ombra)."""
        from PIL import ImageTk
        mio = self.chi_agisce(b, rel, nome)
        prima_att = getattr(self, "_attore_board", None)
        self._attore_board = mio
        self._ritardo_ombra = 0
        cache = self.__dict__.setdefault("_img_ombra", {})
        if len(cache) > 40:
            cache.clear()

        def immagine(lato, livello):
            k = (int(Wt), int(H), lato, livello, tuple(int(v) for v in tp.box(tp.L["STACK"])) if getattr(self, "_pila_mat", None) else None)
            if k not in cache:
                # la maschera (col buco sfumato della pila) una volta per misura e lato; i livelli della dissolvenza la scalano soltanto (15 nov 2026,
                # il debug del replayer: ogni livello rifaceva la sfocatura, 40 ms a fotogramma durante il cambio d'ombra)
                maschere = self.__dict__.setdefault("_maschere_ombra", {})
                km = (int(Wt), int(H), lato, k[4])
                if km not in maschere:
                    if len(maschere) > 8:
                        maschere.clear()
                    maschere[km] = self.maschera_ombra(tp, lato, Wt, H)
                m_, y0_ = maschere[km]
                if m_ is None:
                    cache[k] = (None, 0)
                else:
                    from PIL import Image
                    im_ = Image.new("RGBA", m_.size, (4, 6, 10, 0))
                    im_.putalpha(m_.point(lambda v: int(v * livello / 8)))
                    cache[k] = (ImageTk.PhotoImage(im_), y0_)
            return cache[k]
        img, y0 = immagine(mio, 8)
        if img is None:
            return
        if prima_att is None or prima_att == mio or not getattr(self, "_anima_ora", False):
            c.create_image(0, y0, image=img, anchor="nw", tags="ombra")
            return
        passi = 8
        for q in range(passi + 1):          # tutti i livelli prima di partire: durante la dissolvenza si cambia solo l'immagine
            immagine(prima_att, q), immagine(mio, q)
        vecchia, yv = immagine(prima_att, 8)
        it_v = c.create_image(0, yv, image=vecchia, anchor="nw", tags="ombra") if vecchia is not None else None
        it_n = c.create_image(0, y0, image=immagine(mio, 0)[0], anchor="nw", tags="ombra")
        for q in range(1, passi + 1):
            def cambia(q=q):
                if not c.winfo_exists():
                    return
                if it_v is not None:
                    c.itemconfigure(it_v, image=immagine(prima_att, passi - q)[0])
                c.itemconfigure(it_n, image=immagine(mio, q)[0])
            self._anim_after.append(self.fin_board.after(int(OMBRA_FADE * q / passi), cambia))
        self._ritardo_ombra = OMBRA_FADE

    def maschera_ombra(self, tp, mio, Wt, H):
        """La maschera (PIL, «L») dell'ombra sulla meta' di chi non agisce, e la y dove va: piena lontano dalla linea di mezzo, sfumata verso di lei, la pila
        fuori coi bordi morbidi."""
        from PIL import Image, ImageDraw, ImageFilter
        import disegno_tappeto as DT
        ym = int(tp.Y(DT.MEZZO))
        sf = int(tp.K(OMBRA_SFUMA))
        y0 = 0 if mio else max(0, ym - sf)          # sopra (lui) o sotto (tu), la sfumatura passa un po' oltre la linea di mezzo
        y1 = min(H, ym + sf) if mio else H
        alto = y1 - y0
        if alto <= 0:
            return None, 0
        pb = tp.box(tp.L["STACK"]) if getattr(self, "_pila_mat", None) else None
        a_ = Image.new("L", (int(Wt), int(alto)), OMBRA_ALFA)
        d_ = ImageDraw.Draw(a_)
        for i_ in range(2 * sf):
            v_ = int(OMBRA_ALFA * (1 - i_ / (2 * sf)))
            yy = (alto - 2 * sf + i_) if mio else (2 * sf - 1 - i_)
            d_.line((0, yy, Wt, yy), fill=v_)
        if pb:          # la pila fuori dall'ombra, coi bordi morbidi
            buco = Image.new("L", a_.size, 255)
            m_ = int(tp.K(14))
            ImageDraw.Draw(buco).rounded_rectangle((pb[0] - m_, pb[1] - y0 - m_, pb[2] + m_, pb[3] - y0 + m_), radius=m_ * 2, fill=0)
            buco = buco.filter(ImageFilter.GaussianBlur(m_ / 1.5))
            a_ = Image.composite(a_, Image.new("L", a_.size, 0), buco)
        return a_, y0

    def _attesa_pedine(self, giri):
        """Le immagini delle pedine si scaricano su un altro filo (pedine.py): ogni secondo si guarda se sono arrivate e la tavola si ridisegna."""
        import disegno_tappeto as DT
        import pedine as PD
        fb = getattr(self, "fin_board", None)
        if fb is None or not fb.winfo_exists() or getattr(self, "_attesa_ped", None):
            return

        def guarda(n):
            self._attesa_ped = None
            arrivate = {g for g in DT.PEDINE_ATTESA if os.path.isfile(PD.file(g))}
            DT.PEDINE_ATTESA.difference_update({g for g in DT.PEDINE_ATTESA if PD._indice().get(g) == ""})      # non trovate su Scryfall: resta il riquadro
            if arrivate and time.monotonic() < getattr(self, "_anim_fino", 0) and fb.winfo_exists():     # mai a meta' di un'animazione: dopo
                self._attesa_ped = fb.after(500, lambda: guarda(n))
                return
            if arrivate:
                DT.PEDINE_ATTESA.difference_update(arrivate)
                if getattr(self, "cv_board", None) is not None and self.cv_board.winfo_exists():
                    self.disegna_board()
            elif n > 0 and DT.PEDINE_ATTESA and fb.winfo_exists():
                self._attesa_ped = fb.after(1000, lambda: guarda(n - 1))
        self._attesa_ped = fb.after(1000, lambda: guarda(giri))

    def chiudi_grafico(self):
        """La linguetta: chiude il grafico della partita sopra la timeline verso il basso, o lo riapre."""
        self._graf_chiuso = not getattr(self, "_graf_chiuso", False)
        self.disegna_controlli()
        self.disegna_linguetta(True)

    def mano_in_vista(self):
        """In hand acceso (la mano a ventaglio, di partenza) o spento (il tavolo ingrandito, la mano in riga piccola); la scelta resta per le partite dopo."""
        return self.__dict__.setdefault("_mano_vista", True)

    def cambia_mano(self, accesa=None):
        """Il pulsante In hand (14 nov 2026, Autore: «permetti lo zoom dinamico > in hand e' la versione attuale e se va off la mano a ventaglio
        scompare e si sposta lo zoom sul tavolo ingrandendo tutto e la mano viene messa in riga piu' piccola»)."""
        self._mano_vista = (not self.mano_in_vista()) if accesa is None else bool(accesa)
        if getattr(self, "b_mano", None) is not None:
            self.b_mano.metti("In hand" if self._mano_vista else "In hand: off", self._mano_vista)
        if getattr(self, "cv_board", None) is not None and self.cv_board.winfo_exists():
            self.disegna_board()
        return self._mano_vista

    def chiudi_passi(self, chiusa=None):
        """La linguetta sotto la striscia dei turni: la chiude verso l'alto (la tavola prende il posto) o la riapre."""
        self._passi_chiusi = (not self.__dict__.get("_passi_chiusi")) if chiusa is None else bool(chiusa)
        if self._passi_chiusi:
            self.cv_passi.pack_forget()
        elif not self.cv_passi.winfo_manager():
            self.cv_passi.pack(fill="x", padx=12, pady=(10, 0), before=self.cv_ling_passi)
        self.disegna_linguetta_passi(True)
        return self._passi_chiusi

    def disegna_linguetta_passi(self, sopra=False):
        """▴ HIDE TURNS con la striscia aperta, ▾ SHOW TURNS chiusa: la stessa linguetta del grafico, girata verso l'alto."""
        li = getattr(self, "cv_ling_passi", None)
        if li is None or not li.winfo_exists():
            return
        li.delete("all")
        W = max(li.winfo_width(), 200)
        chiuso = bool(self.__dict__.get("_passi_chiusi"))
        cx, L = W / 2, 120
        li.create_polygon(cx - L / 2, 0, cx - L / 2 + 8, 14, cx + L / 2 - 8, 14, cx + L / 2, 0, fill="#262c37" if sopra else C["cap"], outline="")
        col = "#ffffff" if sopra else "#9a9aa2"
        if chiuso:
            li.create_polygon(cx - 30, 4, cx - 24, 10, cx - 18, 4, fill=col, outline="")
        else:
            li.create_polygon(cx - 30, 10, cx - 24, 4, cx - 18, 10, fill=col, outline="")
        li.create_text(cx + 16, 7, text="SHOW TURNS" if chiuso else "HIDE TURNS", fill=col, font=self.F(6, True))

    def disegna_linguetta(self, sopra=False):
        """La linguetta al centro del bordo alto della barra, nel colore della testata come quelle delle liste: ▾ HIDE CHART, ▴ SHOW CHART."""
        li = getattr(self, "cv_linguetta", None)
        if li is None or not li.winfo_exists():
            return
        li.delete("all")
        W = max(li.winfo_width(), 200)
        chiuso = getattr(self, "_graf_chiuso", False)
        cx, L = W / 2, 120
        li.create_polygon(cx - L / 2, 14, cx - L / 2 + 8, 0, cx + L / 2 - 8, 0, cx + L / 2, 14, fill="#262c37" if sopra else C["cap"], outline="")
        col = "#ffffff" if sopra else "#9a9aa2"
        if chiuso:
            li.create_polygon(cx - 30, 10, cx - 24, 4, cx - 18, 10, fill=col, outline="")
        else:
            li.create_polygon(cx - 30, 4, cx - 24, 10, cx - 18, 4, fill=col, outline="")
        li.create_text(cx + 16, 7, text="SHOW CHART" if chiuso else "HIDE CHART", fill=col, font=self.F(6, True))

    def ferma_animazione(self):
        self._anim_in_corso = False
        for a_ in getattr(self, "_anim_after", []):
            try:
                self.fin_board.after_cancel(a_)
            except Exception:      # noqa: BLE001 - gia' scattato
                pass
        self._anim_after = []
        c = getattr(self, "cv_board", None)
        if c is not None and c.winfo_exists():
            self._scivola = []
            self._frecce_duello = []
            c.delete("anim")
            c.itemconfigure("frecce", state="normal")
            c.itemconfigure("danni", state="normal")
            alza_icone(c)
            for it_ in getattr(self, "_nascoste", []):
                c.itemconfigure(it_, state="normal")
        self._nascoste = []

    def anima_board(self, c, prima_zone, prima_pile, prima, f):
        """Le carte che scorrono fra le zone invece di comparire (12 nov 2026, «le carte che scorrono da una zona all'altra invece di comparire»; 14 nov 2026,
        Autore: «facciamo che le carte non appaiono ma scorrono tra le zone (es: se una carta genera pedine esse scorrono dalla carta in pila sul board, se una
        carta torna dal cimitero essa viene trascinata dal cimitero sul board)»). Ogni carta arrivata in campo parte da dove era: dalla pila (la magia risolta;
        le pedine dalla carta in pila che le crea, o dalla zona della pila), dal cimitero o dall'esilio se li' ne manca una, dalla mano (la tua; la sua dal suo
        lato del tavolo), se no dal grimorio (messa in campo dal mazzo). Una carta che lascia il campo scivola sul cimitero, sull'esilio, in mano o nel grimorio
        (una pedina sparisce). Anche fuori dal campo: la pescata dal grimorio (o dal cimitero, dall'esilio) alla mano, lo scarto dalla mano al cimitero, la magia
        risolta dalla pila al cimitero, le carte macinate dal grimorio al cimitero, la magia lanciata dalla mano alla pila. 14 quadri da 16 ms che rallentano
        all'arrivo; un altro passo le chiude subito."""
        from collections import Counter

        def centro(r_):
            return ((r_[0] + r_[2]) / 2, (r_[1] + r_[3]) / 2)
        zc = getattr(self, "_zone_carte", {}) or {}
        lati = ("mio", "suo")
        vuoto = ([], [])

        def conta(f_, k, i):
            return Counter(((f_ or {}).get(k) or vuoto)[i])
        cim_piu = [conta(f, "cim", i) - conta(prima, "cim", i) for i in (0, 1)]
        cim_meno = [conta(prima, "cim", i) - conta(f, "cim", i) for i in (0, 1)]
        esi_piu = [conta(f, "esi", i) - conta(prima, "esi", i) for i in (0, 1)]
        esi_meno = [conta(prima, "esi", i) - conta(f, "esi", i) for i in (0, 1)]
        mano_piu = Counter(f.get("mano") or []) - Counter(prima.get("mano") or [])
        mano_meno = Counter(prima.get("mano") or []) - Counter(f.get("mano") or [])
        suo_mano = (prima.get("n_suo") or 0, f.get("n_suo") or 0)
        # (14 nov 2026, il censimento del replayer) la carta che cambia lato: stesso id di Arena, dall'altro campo (non vola dal grimorio: scivola da un
        # lato all'altro); la carta che si gira: stesso id, stesso campo, nome nuovo (la faccia dietro)
        ids_l = {lato: {c_[5]: c_[0] for c_ in (prima.get(lato) or []) if len(c_) > 5 and c_[5] is not None} for lato in lati}
        ids_o = {lato: {c_[5]: c_[0] for c_ in (f.get(lato) or []) if len(c_) > 5 and c_[5] is not None} for lato in lati}
        cambi = {id_: lb for la, lb in (("mio", "suo"), ("suo", "mio")) for id_ in ids_l[la] if id_ in ids_o[lb]}
        cambi_n = Counter((lb, ids_o[lb][id_]) for id_, lb in cambi.items())
        girate_faccia = {id_: (lato, ids_l[lato][id_], n_) for lato in lati for id_, n_ in ids_o[lato].items() if id_ in ids_l[lato] and ids_l[lato][id_] != n_}
        girate_n = Counter((v_[0], v_[2]) for v_ in girate_faccia.values())
        guadagni = {}
        for k_v, i_v in (("vita_mio", 0), ("vita_suo", 1)):
            pv, fv = (prima.get("vite") or (None, None))[i_v], (f.get("vite") or (None, None))[i_v]
            if pv is not None and fv is not None and fv > pv:
                guadagni[k_v] = (pv, fv)
        rivelate = list(f.get("riv") or [])
        guardate = list(f.get("scry") or [])
        mescole = list(f.get("mes") or [])
        mosse = []          # (nome, tappata, da, a, item della carta arrivata o None)
        suo_torna = [0]     # le sue carte tornate in mano dal campo: non sono pescate
        mano_prima = [z for z in prima_zone if z[0] == "mano"]
        usate = set()
        pila_prima = getattr(self, "_pila_prima", None)
        pila_ora = getattr(self, "_pila_ora", None)
        # la pila si confronta per id di Arena, non per nome (15 nov 2026, il controllo delle animazioni della pila): la Room in pila si chiama come la meta'
        # lanciata («Unholy Annex») e in mano col nome intero, Mockingbird si risolve ed entra col nome di quello che copia; l'id resta lo stesso
        ids_p0 = [q[4] for q in (prima.get("pila") or []) if len(q) > 4]
        ids_p1 = [q[4] for q in (f.get("pila") or []) if len(q) > 4]
        id_prima, id_ora = (ids_p0 or [None])[0], (ids_p1 or [None])[0]
        # le due meta' della Room: «Ritual Chamber» lanciata e' la carta «Unholy Annex // Ritual Chamber» (la faccia dietro, 15 nov 2026)
        stessa = lambda a, b: bool(a) and bool(b) and (a == b or a in b.split(" // ") or b in a.split(" // "))
        if pila_prima and id_prima is not None:
            dalla_pila = id_prima not in ids_p1         # la magia di prima non e' piu' in pila: si e' risolta (o e' stata contrastata, rimandata)
        else:
            dalla_pila = bool(pila_prima) and not (pila_ora and pila_ora[1] == pila_prima[1])

        # le magie andate in pila in questo turno e non ancora risolte al passo prima: una che arriva nel cimitero viene dalla pila, anche se non era in
        # cima (la magia contrastata sta sotto la contromagia)
        in_pila_turno = Counter()       # lanciate in questo turno e non ancora risolte (dai racconti dei passi: «cast X», «X resolved»)
        lanciate_turno = Counter()      # lanciate in questo turno, risolte o no: una che arriva nel cimitero o in esilio senza altra origine viene dalla pila
        b_p = self.vista_azioni(getattr(self, "_board", None)) or {}
        if b_p.get("passi") and b_p.get("modo") == "azioni":
            i_p = b_p.get("i", 0)
            t_p = b_p["passi"][i_p][2]
            q0 = i_p
            while q0 > 0 and b_p["passi"][q0 - 1][2] == t_p:
                q0 -= 1
            for q_ in range(q0, i_p):
                for _m, tx_ in (b_p["passi"][q_][4] if len(b_p["passi"][q_]) > 4 else []):
                    if " cast " in f" {tx_} ":
                        n_c = tx_.split(" cast ", 1)[1].replace(" from the top of the library", "").strip()
                        in_pila_turno[n_c] += 1
                        lanciate_turno[n_c] += 1
                    elif tx_.endswith(" resolved") and in_pila_turno[tx_[:-len(" resolved")]] > 0:
                        in_pila_turno[tx_[:-len(" resolved")]] -= 1
            if pila_prima and in_pila_turno[pila_prima[1]] > 0:         # quella in cima ha la sua regola (dalla_pila)
                in_pila_turno[pila_prima[1]] -= 1

        eventi_passo = (b_p["passi"][b_p.get("i", 0)][4] if b_p.get("passi") and len(b_p["passi"][b_p.get("i", 0)]) > 4 else []) or []

        def da_mano(n):
            z = next((z for z in mano_prima if z[1] == n and id(z) not in usate), None)
            if z:
                usate.add(id(z))
                return z[2]
            return None
        # «esilia finche'» (15 nov 2026, il censimento): la carta esiliata sotto la sua fonte ci arriva volando e ci resta (sotto_di); quando la fonte se ne
        # va, o la lascia, la carta torna da sotto di lei, dove stava disegnata, non dalla pila dell'esilio (da_sotto)
        k_ts = getattr(self, "_tappeto_k", 1) or 1
        sposta_ = lambda b_: (b_[0] + 9 * k_ts, b_[1] + 9 * k_ts, b_[2] + 9 * k_ts, b_[3] + 9 * k_ts)
        sotto_att = list(getattr(self, "_sotto_nuove", []) or [])

        def sotto_di(n_):
            for j_, (n2, h2) in enumerate(sotto_att):
                pz_ = (getattr(self, "_pezzo_id", {}) or {}).get(h2)
                if not pz_:     # la fonte e' un'aura: sta dietro la carta che la porta, e la carta esiliata con lei
                    pz_ = (getattr(self, "_pezzo_id", {}) or {}).get(((f.get("segni") or {}).get(h2) or {}).get("su"))
                if n2 == n_ and pz_:
                    sotto_att.pop(j_)
                    return sposta_(pz_[1]), pz_[0]
            return None
        prima_pz0 = getattr(self, "_prima_pezzi", {}) or {}
        seg_o0 = f.get("segni") or {}
        liberate = []
        for i_, v_ in ((prima or {}).get("segni") or {}).items():
            d_ = Counter(v_.get("sotto") or []) - Counter((seg_o0.get(i_) or {}).get("sotto") or [])
            bx_ = (prima_pz0.get(i_) or prima_pz0.get(v_.get("su")) or (None, None))[1]     # un'aura: dalla carta che la portava
            if d_ and bx_ is not None:
                liberate += [(n_, sposta_(bx_)) for n_ in d_.elements()]

        def da_sotto(n_):
            for j_, (n2, b2) in enumerate(liberate):
                if n2 == n_:
                    liberate.pop(j_)
                    return b2
            return None
        for z in self._nuove:        # arrivi
            zkey, n, box, tap, it_ = z[:5]
            ped = z[5] if len(z) > 5 else False
            da = None
            if zkey in lati and cambi_n[(zkey, n)] > 0:        # ha cambiato lato: scivola dal campo di prima (non vola dal grimorio)
                cambi_n[(zkey, n)] -= 1
                continue
            if zkey in lati and girate_n[(zkey, n)] > 0:       # si e' girata: il giro al suo posto (non vola dal grimorio)
                girate_n[(zkey, n)] -= 1
                continue
            if zkey in lati:
                i = lati.index(zkey)
                if ped:
                    da = pila_prima[0] if pila_prima else getattr(self, "_stack_box", None)
                elif pila_prima and (stessa(pila_prima[1], n) or (id_prima is not None and id_prima in (z[6] if len(z) > 6 else ()))):       # dalla pila al campo: la magia risolta
                    da = pila_prima[0]
                elif cim_meno[i][n] > 0:        # dal cimitero (una rianimazione)
                    cim_meno[i][n] -= 1
                    da = zc.get(f"cim_{zkey}")
                elif esi_meno[i][n] > 0:        # dall'esilio (un ritorno, una carta giocata dall'esilio)
                    esi_meno[i][n] -= 1
                    da = da_sotto(n) or zc.get(f"esi_{zkey}")
                elif zkey == "mio":
                    da = da_mano(n)
                    if da:
                        mano_meno[n] -= 1
                elif suo_mano[1] < suo_mano[0] or any(tx_ == f"Opponent played {n}" for _m, tx_ in eventi_passo):
                    # (16 nov 2026: la terra giocata dalla sua mano quando il conto della sua mano nel log resta indietro, «Opponent played Island»)
                    da = getattr(self, "_mano_suo_box", None)
                if da is None and not ped:      # messa in campo dal grimorio
                    da = zc.get(f"lib_{zkey}")
            elif zkey == "mano":        # in mano: dal cimitero, dall'esilio, se no la pescata dal grimorio (14 nov 2026: «l'animazione di pescata»)
                if any(z_[0] == "mio" and z_[1] == n for z_ in prima_zone) and not any(c_[0] == n for c_ in f["mio"]):
                    da = None           # tornata in mano dal campo: scivola con le partenze
                elif dalla_pila and stessa(pila_prima[1], n):        # la magia rimandata in mano dalla pila
                    da, dalla_pila = pila_prima[0], False
                elif in_pila_turno[n] > 0:          # stava in pila sotto un'altra: rimandata in mano (14 nov 2026: «torna in mano dal mazzo e non dalla pila»)
                    in_pila_turno[n] -= 1
                    da = (pila_prima or (None,))[0] or getattr(self, "_stack_box", None)
                elif cim_meno[0][n] > 0:
                    cim_meno[0][n] -= 1
                    da = zc.get("cim_mio")
                elif esi_meno[0][n] > 0:
                    esi_meno[0][n] -= 1
                    da = da_sotto(n) or zc.get("esi_mio")
                elif any(tx_ == f"{n} returned to hand" for _m, tx_ in eventi_passo):      # tornata in mano da un cimitero che la foto non aveva
                    da = zc.get("cim_mio")
                else:
                    da = getattr(self, "_box_grimorio", None)
            if da:
                fase_ = (1 if ped else 2 if pila_prima and da is pila_prima[0] else 3) if zkey in lati else 4
                mosse.append((n, tap, da, box, it_, zkey in lati, fase_))
        # l'aura o l'equipaggiamento attaccato in questo passo (15 nov 2026, Autore: «quando una carta riceve un incantesimo aura o indossa un artefatto,
        # non dovremmo vedere quelle carte al di sotto di chi l'ha ricevuta?»): dalla pila (o dalla mano) vola sulla carta che lo porta, si posa dietro di lei
        # sfalsato in alto col nome a vista e ci resta; la carta che lo porta e' disegnata senza finche' non arriva
        k_t = getattr(self, "_tappeto_k", 1) or 1
        for n_a, h_a in getattr(self, "_attaccate_nuove", []) or []:
            pz_h = (getattr(self, "_pezzo_id", {}) or {}).get(h_a)
            hb = self._pos_id.get(h_a)
            if not hb or not pz_h:
                continue
            dest = (hb[0] + 5 * k_t, hb[1] - 22 * k_t, hb[2] + 5 * k_t, hb[3] - 22 * k_t)
            if pila_prima and pila_prima[1] == n_a:
                da_a, fase_a = pila_prima[0], 2
            else:
                da_a, fase_a = (da_mano(n_a) or getattr(self, "_stack_box", None)), 3
            if da_a:
                mosse.append((n_a, False, da_a, dest, None, True, fase_a, "attacca", pz_h[0]))
        # la carta che diventa giocabile da fuori della mano (15 nov 2026, Autore: «le famose carte esiliate dorate in mano non le vedo mai»): dalla pila
        # dell'esilio o del cimitero vola nella fila PLAYABLE accanto alla mano di chi puo' giocarla, dopo che e' arrivata in esilio; prima compariva li' e basta
        def gioc(f_):
            c_ = Counter()
            for v_ in ((f_ or {}).get("segni") or {}).values():
                if v_.get("gioca"):
                    c_[tuple(v_["gioca"])] += 1
            return c_
        if "segni" in f and prima is not None:
            import disegno_tappeto as DT_
            nuove_g = gioc(f) - gioc(prima)
            usati_g = set()
            esi_f = f.get("esi") or ([], [])
            cim_f = f.get("cim") or ([], [])
            for (n_g, mio_g, z_g), q_g in nuove_g.items():
                lato_g = "mio" if mio_g else "suo"
                for _ in range(q_g):
                    dove_g = next(((j_, b_, it_) for j_, (n2, b_, it_) in enumerate((getattr(self, "_giocabili", {}) or {}).get(lato_g, []))
                                   if (n2 or DT_.FACCIA_GIU) == n_g and (lato_g, j_) not in usati_g), None)
                    if dove_g is None:
                        continue
                    usati_g.add((lato_g, dove_g[0]))
                    pile_ = esi_f if z_g == "esi" else cim_f
                    # dalla pila dove sta la carta: la sua, se no quella di chi puo' giocarla (le sue a faccia in giu' sono nel suo esilio)
                    lato_z = "mio" if n_g in pile_[0] else "suo" if n_g in pile_[1] else lato_g
                    da_g = zc.get(f"{z_g}_{lato_z}")
                    if da_g:
                        mosse.append(("dorso" if n_g == DT_.FACCIA_GIU else n_g, False, da_g, dove_g[1], dove_g[2], False, 4.5))
        # partenze dal campo: per nome, dalle carte delle due foto, non dai riquadri (14 nov 2026, Autore: «a volte delle terre tornano nel mazzo dopo
        # essere state stappate e non si sa perche'»): le terre uguali stanno in gruppi col xN, una terra che si stappa cambia gruppo, e contarle per
        # riquadro la faceva uscire dal campo e volare nel grimorio
        # chi esce si riconosce per il suo id di Arena, non per il nome (14 nov 2026, la caccia ai glitch: con due Semester Foreseer in campo e uno morto,
        # diventava grigio e volava quello sbagliato); il nome resta il ripiego per le carte senza id
        campo_prima, partenze = [z for z in prima_zone if z[0] in lati], []
        prima_pz_ = getattr(self, "_prima_pezzi", {}) or {}
        usati_box = set()
        quota = Counter()
        for lato in lati:
            ids_ora = {c_[5] for c_ in f.get(lato) or [] if len(c_) > 5 and c_[5] is not None}
            for c_ in prima.get(lato) or []:
                id_c = c_[5] if len(c_) > 5 else None
                if id_c is None or id_c in ids_ora or id_c in cambi:
                    continue
                bx_ = (prima_pz_.get(id_c) or (None, None))[1]
                su_ = ((prima.get("segni") or {}).get(id_c) or {}).get("su")
                if bx_ is None and su_ is not None and (prima_pz_.get(su_) or (None, None))[1] is not None:
                    # l'aura o l'equipaggiamento che cade (15 nov 2026, la caccia ai glitch: Unflinching Courage volava dal grimorio): parte da sotto la carta
                    # che la portava, dove stava disegnata
                    hb_ = prima_pz_[su_][1]; k_t = getattr(self, "_tappeto_k", 1) or 1
                    partenze.append((lato, c_[0], (hb_[0] + 5 * k_t, hb_[1] - 22 * k_t, hb_[2] + 5 * k_t, hb_[3] - 22 * k_t), False, None, False))
                    continue
                z_ = next((z for z in campo_prima if z[0] == lato and bx_ is not None and tuple(round(v) for v in z[2]) == tuple(round(v) for v in bx_)
                           and id(z) not in usati_box), None)
                if z_ is not None:
                    usati_box.add(id(z_))
                    partenze.append(z_)
                else:       # un gruppo (xN) o una carta senza pezzo suo: per nome
                    quota[(lato, c_[0])] += 1
        while True:
            presi = 0
            for z in campo_prima:
                if quota[(z[0], z[1])] > 0 and id(z) not in usati_box:        # un gruppo puo' perdere piu' carte: lo stesso riquadro piu' volte
                    quota[(z[0], z[1])] -= 1
                    partenze.append(z)
                    presi += 1
            if not presi:
                break
        for z in partenze:
            i = lati.index(z[0])
            ped = z[5] if len(z) > 5 else False
            dove = None
            muore = False
            if cim_piu[i][z[1]] > 0:
                cim_piu[i][z[1]] -= 1
                dove = zc.get(f"cim_{z[0]}")
                muore = True
            elif esi_piu[i][z[1]] > 0:
                esi_piu[i][z[1]] -= 1
                s_ = sotto_di(z[1])
                if s_:      # esiliata «finche'»: va sotto la sua fonte e ci resta
                    mosse.append((z[1], z[3], z[2], s_[0], None, False, 0.5, "attacca", s_[1]))
                    continue
                dove = zc.get(f"esi_{z[0]}")
            elif not ped and cim_piu[1 - i][z[1]] > 0:
                # la carta controllata dall'altro va nel cimitero del proprietario (400.3; 16 nov 2026: Sunpearl Kirin presa con Come Back Wrong e
                # sacrificata a fine turno volava nel suo grimorio)
                cim_piu[1 - i][z[1]] -= 1
                dove = zc.get(f"cim_{lati[1 - i]}")
                muore = True
            elif not ped and esi_piu[1 - i][z[1]] > 0:      # e nell'esilio del proprietario
                esi_piu[1 - i][z[1]] -= 1
                dove = zc.get(f"esi_{lati[1 - i]}")
            elif not ped and any(tx_ == f"{z[1]} exiled" for _m, tx_ in eventi_passo) \
                   and any(tx_.startswith(f"{z[1]} returned to the battlefield") for _m, tx_ in eventi_passo):
                # esce e rientra nello stesso passo (16 nov 2026: Daydream su Starfield Shepherd): vola in esilio e torna al suo posto, con l'id nuovo
                nuova_z = next((zz for zz in self._box_zona if zz[0] == z[0] and zz[1] == z[1]), None)
                esi_b = zc.get(f"esi_{z[0]}")
                if esi_b:
                    mosse.append((z[1], z[3], z[2], esi_b, None, False, 0.5))
                    if nuova_z:
                        mosse.append((z[1], nuova_z[3], esi_b, nuova_z[2], nuova_z[4], False, 1))       # nell'effetto, prima che la magia lasci la pila
                continue
            elif i == 0 and mano_piu[z[1]] > 0:
                dove = next((zz[2] for zz in self._box_zona if zz[0] == "mano" and zz[1] == z[1]), None)
            elif i == 1 and not ped and suo_mano[1] - suo_mano[0] - suo_torna[0] > 0:
                # una pedina non torna mai in mano, e non tornano piu' carte di quante la sua mano ne guadagna (15 nov 2026: due Insetti morti volavano
                # nella sua mano perche' nello stesso passo riprendeva Dredger's Insight)
                dove = getattr(self, "_mano_suo_box", None)
                suo_torna[0] += 1
            elif not ped:
                # la carta a due facce lascia il campo con la faccia dietro e arriva nel cimitero o in esilio con quella davanti (14 nov 2026, la caccia
                # ai glitch: Neo Exdeath muore, nel cimitero e' Exdeath, Void Warlock, e volava nel grimorio): il nome nuovo lo dice il racconto del passo
                for k_z2, piu_ in ((f"cim_{z[0]}", cim_piu[i]), (f"esi_{z[0]}", esi_piu[i])):
                    # non la magia che lascia la pila nello stesso passo (16 nov 2026: Daydream risolta finiva sulla creatura che fa uscire e rientrare)
                    n2 = next((n2 for n2, q2 in piu_.items() if q2 > 0 and n2 != z[1] and any(n2 in tx_ for _m, tx_ in eventi_passo)
                               and not (pila_prima and stessa(pila_prima[1], n2))), None)
                    if n2:
                        piu_[n2] -= 1
                        dove, muore = zc.get(k_z2), k_z2.startswith("cim")
                        break
                if dove is None:
                    dove = zc.get(f"lib_{z[0]}")
            else:       # la pedina che lascia il campo non va da nessuna parte: diventa grigia al suo posto e si spegne (mai di colpo)
                mosse.append((z[1], z[3], z[2], z[2], None, False, 0.5, "svanisce"))
            if dove:        # fase 0.5: chi lascia il campo va via per primo, poi le altre scivolano a chiudere il buco, poi arriva il nuovo
                mosse.append((z[1], z[3], z[2], dove, None, False, 0.5, "muore" if muore else None))
        for i, lato in enumerate(lati):     # le altre carte arrivate in un cimitero o in un esilio: dalla pila, dalla mano, se no dal grimorio (macinate)
            for k_z, piu in ((f"cim_{lato}", cim_piu[i]), (f"esi_{lato}", esi_piu[i])):
                for n, q in piu.items():
                    for _ in range(q):
                        da = None
                        if dalla_pila and stessa(pila_prima[1], n):
                            da, dalla_pila = pila_prima[0], False
                        elif in_pila_turno[n] > 0:      # stava in pila sotto un'altra (contrastata: 14 nov 2026, «dalla pila se vengono counterate e' come
                            in_pila_turno[n] -= 1       # se andassero dal mazzo al cimitero»): parte dalla pila
                            da = (pila_prima or (None,))[0] or getattr(self, "_stack_box", None)
                        elif k_z.startswith("esi") and cim_meno[i][n] > 0:     # dal cimitero all'esilio (Afterthought Sentry, escape, delve)
                            cim_meno[i][n] -= 1
                            da = zc.get(f"cim_{lato}")
                        elif k_z.startswith("cim") and esi_meno[i][n] > 0:     # dall'esilio al cimitero
                            esi_meno[i][n] -= 1
                            da = zc.get(f"esi_{lato}")
                        elif lanciate_turno[n] > 0:         # lanciata in questo turno (risolta mentre in pila c'era la sua abilita')
                            lanciate_turno[n] -= 1
                            da = (pila_prima or (None,))[0] or getattr(self, "_stack_box", None)
                        elif k_z.startswith("esi") and any(tx_ == f"{n} exiled" for _m, tx_ in eventi_passo) and ((prima.get("cim") or vuoto)[i]) and not (dalla_pila and any(tx_ == f"{n} resolved" for _m, tx_ in eventi_passo)):
                            # (16 nov 2026: Gandalf risolto come Flameshape va in esilio dalla pila, non dal cimitero)
                            da = zc.get(f"cim_{lato}")      # esiliata da un cimitero che la foto non aveva per intero
                        elif i == 0 and mano_meno[n] > 0:
                            mano_meno[n] -= 1
                            da = da_mano(n)
                        elif i == 1 and suo_mano[1] < suo_mano[0]:
                            da = getattr(self, "_mano_suo_box", None)
                        if da is None and dalla_pila and pila_prima and not (len(pila_prima) > 3 and pila_prima[3]) \
                                and any(tx_ == f"{n} resolved" for _m, tx_ in eventi_passo):
                            # (solo la carta che il passo dice risolta: con Flameshape anche la Mountain esiliata dalla cima arrivava senza spiegazione)
                            # la magia uscita dalla pila col nome dell'altra meta' (15 nov 2026: Flameshape, la magia di Gandalf, va in esilio come
                            # Gandalf): una carta arrivata senza altra spiegazione mentre una magia lascia la pila e' lei
                            da, dalla_pila = pila_prima[0], False
                        if da is None and not any(w_ in tx_ for _m, tx_ in eventi_passo for w_ in ("milled", "surveil", "library", "exiled", "discard",
                                                                                                        "graveyard", "left out part")):
                            # nessuna azione del passo dice da dove arriva (16 nov 2026: Solstice Revelations gia' nel cimitero, senza nome prima): compare
                            # al suo posto, senza un volo dal grimorio inventato
                            continue
                        if da is None:
                            da = zc.get(f"lib_{lato}")
                        s_ = sotto_di(n) if k_z.startswith("esi") else None
                        if da and s_:      # esiliata «finche'» dalla mano o dalla pila (Deep-Cavern Bat): sotto la sua fonte
                            mosse.append((n, False, da, s_[0], None, False, 2 if da is (pila_prima or (None,))[0] else 3, "attacca", s_[1]))
                            continue
                        if da and zc.get(k_z):
                            mosse.append((n, False, da, zc[k_z], None, False, 2 if da is (pila_prima or (None,))[0] else 3))
        # la sua carta che torna in mano da sotto la fonte che se ne va (15 nov 2026, «esilia finche'»: muore il Deep-Cavern Bat e la carta torna nella sua
        # mano): vola da sotto la fonte nella sua mano; non e' una pescata, quindi non parte un dorso dal suo grimorio
        for n_l, b_l in list(liberate):
            if suo_mano[1] - suo_mano[0] - suo_torna[0] > 0 and esi_meno[1][n_l] > 0 and getattr(self, "_mano_suo_box", None):
                esi_meno[1][n_l] -= 1
                liberate.remove((n_l, b_l))
                suo_torna[0] += 1
                mosse.append((n_l, False, b_l, self._mano_suo_box, None, False, 3))
        # la sua pescata (14 nov 2026, Autore: «non si vede l'animazione di pescata di oppo»): un dorso dal suo grimorio alla sua mano per ogni carta in
        # piu' che non e' tornata dal campo
        # (14 nov 2026, Autore: «quando l'avversario pesca la carta gli diventa trasparente invece di inserirsi fisicamente nel suo mazzo»): la carta nuova
        # del suo ventaglio resta nascosta finche' il dorso non arriva al suo posto, nel ventaglio
        nuove_sue = list(getattr(self, "_mano_suo_items", []) or [])[:suo_mano[1]]      # solo i dorsi della sua mano (dopo, col tavolo ingrandito, l'esilio)
        for k_p in range(max(0, suo_mano[1] - suo_mano[0] - suo_torna[0])):
            if zc.get("lib_suo") and getattr(self, "_mano_suo_box", None):
                if k_p < len(nuove_sue):
                    it_n, bx_n = nuove_sue[-(k_p + 1)]
                    mosse.append(("dorso", False, zc["lib_suo"], bx_n, it_n, False, 4))
                else:
                    mosse.append(("dorso", False, zc["lib_suo"], self._mano_suo_box, None, False, 4))
        if dalla_pila and pila_prima and not (len(pila_prima) > 3 and pila_prima[3]) and id_prima not in (prima.get("pc") or []) \
               and not any(m_[2] is pila_prima[0] for m_ in mosse) and any("library" in tx_ for _m, tx_ in eventi_passo):
            # la magia che dalla pila va nel grimorio (15 nov 2026: Exude Toxin, l'Omen di Scavenger Regent, «put on top of the library»)
            dest_l = zc.get("lib_mio" if pila_prima[2] else "lib_suo")
            if dest_l:
                mosse.append((pila_prima[1], False, pila_prima[0], dest_l, None, False, 2))
        if pila_ora and not (pila_prima and (id_ora == id_prima if id_ora is not None and id_prima is not None else pila_prima[1] == pila_ora[1])):       # una magia appena lanciata: dalla mano alla pila
            it_p = getattr(self, "_pila_item", None)        # la carta in pila resta nascosta finche' quella che vola non arriva
            # solo una magia vera, uscita davvero dalla mano (14 nov 2026, Autore: «a volte vanno nella pila carte che poi non vengono giocate, confonde»):
            # l'abilita' di un permanente (Meticulous Archive) con una carta dallo stesso nome in mano faceva volare quella carta, che restava in mano
            abil_ = len(pila_ora) > 3 and pila_ora[3]
            src_prep = (f.get("pd") or {}).get(id_ora)
            z_l = (f.get("pz") or {}).get(id_ora)
            if src_prep is not None and self._pos_id.get(src_prep):       # la copia preparata: dalla creatura che la prepara (15 nov 2026)
                # con l'immagine della carta in pila (la faccia preparata non ha un'immagine col suo nome: il volo si perdeva)
                mosse.append((pila_ora[1], False, self._pos_id[src_prep], pila_ora[0], it_p, it_p is not None, 2.5))
            elif z_l and zc.get(f"{z_l[0]}_{'mio' if z_l[1] else 'suo'}"):
                # lanciata dal cimitero, dall'esilio o dal grimorio (flashback, l'esilio che si gioca, Gandalf): vola da quella pila (15 nov 2026)
                mosse.append((pila_ora[1], False, zc[f"{z_l[0]}_{'mio' if z_l[1] else 'suo'}"], pila_ora[0], it_p, False, 2.5))
            elif abil_:
                pass
            elif len(pila_ora) < 3 or pila_ora[2]:
                k_m = next((k_ for k_, q_ in mano_meno.items() if q_ > 0 and stessa(k_, pila_ora[1])), None)      # la Room in mano col nome intero
                if k_m is None and sum(mano_meno.values()) == 1:
                    # la meta' magia di una carta con un altro nome in mano (Exude Toxin di Scavenger Regent, 15 nov 2026): e' l'unica uscita dalla mano
                    k_m = next(k_ for k_, q_ in mano_meno.items() if q_ > 0)
                da = next((z[2] for z in mano_prima if z[1] == k_m and id(z) not in usate), None) if k_m else None
                if da:      # vola col nome che ha in mano: l'immagine della Room c'e' col nome intero, non con quello della meta'
                    mosse.append((k_m, False, da, pila_ora[0], it_p, False, 2.5))
                elif any(tx_ in (f"You cast {pila_ora[1]}", f"You cast {pila_ora[1]} from the top of the library") for _m, tx_ in eventi_passo):
                    # rilanciata dopo un annullamento che Arena ha scritto riassunto (16 nov 2026, Seam Rip): la foto della mano non l'aveva piu', ma il log
                    # dice che arriva dalla mano: vola dal centro della mano
                    box_m = getattr(self, "_mano_mio_box", None) or (mano_prima[len(mano_prima) // 2][2] if mano_prima else None)
                    if box_m:
                        mosse.append((pila_ora[1], False, box_m, pila_ora[0], it_p, it_p is not None, 2.5))
            elif suo_mano[1] < suo_mano[0] and getattr(self, "_mano_suo_box", None):
                # la sua: un dorso dalla sua mano alla pila, e li' si rivela (14 nov 2026, Autore: «anche all'oppo devono scorrere le carte per esempio dalla
                # mano alla pila e li' rivelarsi»)
                mosse.append(("dorso", False, self._mano_suo_box, pila_ora[0], it_p, False, 2.5))
        self._durata_anim = 0
        # una mano sola (14 nov 2026, Autore: «deve sembrare una partita giocata usando le mani vere, i giocatori hanno solo due mani e con una tengono le
        # carte, quindi possono fare uso solo di una mano, e quindi fanno le cose in sequenza»): le carte che si tappano o si stappano (le terre per pagare,
        # gli attaccanti, lo stap a inizio turno) girano una alla volta, da sinistra a destra, prima dei voli; fino a quel giorno giravano tutte insieme
        tap_prima = {c_[5]: bool(c_[1]) for lato in ("mio", "suo") for c_ in (prima.get(lato) or []) if len(c_) > 5}
        girate = sorted(((id_, it_g, box_g, tap_g, n_g) for id_, (it_g, box_g, tap_g, n_g) in (getattr(self, "_pezzo_id", {}) or {}).items()
                         if id_ in tap_prima and tap_prima[id_] != bool(tap_g) and id_ not in cambi), key=lambda g_: (g_[2][1], g_[2][0]))
        # la terra che si tappa ed entra in un gruppo uguale gia' tappato (o si stappa ed entra in quello stappato) non ha un pezzo suo: si gira il gruppo
        # che la riceve, una volta (21 nov 2026, il debug: l'avversario paga con un'Island e un secondo Dismal Backwater, e il Dismal saliva a x2 senza
        # girarsi; la regola «una mano sola»: ogni terra del pagamento si gira, una alla volta)
        visti_g = {g_[1] for g_ in girate}
        for id_, (it_g, box_g, tap_g, n_g) in (getattr(self, "_pezzo_gruppo", {}) or {}).items():
            if id_ in tap_prima and tap_prima[id_] != bool(tap_g) and id_ not in cambi and it_g not in visti_g:
                visti_g.add(it_g)
                girate.append((id_, it_g, box_g, tap_g, n_g))
        girate.sort(key=lambda g_: (g_[2][1], g_[2][0]))
        # il combattimento (14 nov 2026, Autore: «dopo la dichiarazione di attacchi e difesa le carte si muovono per dirigersi verso la direzione, le carte
        # che muoiono vanno in overlay desaturato prima di andare al cimitero», «insomma animiamo il combattimento»): gli attaccanti avanzano verso chi
        # attaccano e i bloccanti verso l'attaccante (spinte nuove, una alla volta), nel passo del danno ogni attaccante colpisce (avanti e indietro), poi
        # i danni, poi chi muore diventa grigio al suo posto, poi va al cimitero
        spinte_nuove = list(getattr(self, "_spinte_anim", []) or [])
        b_ = self.vista_azioni(getattr(self, "_board", None)) or {}
        passo_ = (b_.get("passi") or [None])[b_.get("i", 0)] if b_.get("passi") else None
        danni_ = bool(b_.get("modo") == "azioni" and passo_ and len(passo_) > 5 and passo_[5])
        rel_ = passo_[3] if passo_ else None
        if danni_ and passo_ and "Damage" in passo_[0]:
            rel_ = self.combattimento_dichiarato(b_) or rel_
        elif danni_ and passo_ and len(passo_) > 6:
            # la lotta (15 nov 2026, il censimento: «le gocce su tutte e due; il duello animato solo nel combattimento»): fuori dal combattimento due creature
            # che si fanno danno a vicenda si affrontano come in un duello, una verso l'altra
            fonti_l = {(t_, s_) for t_, _q, s_ in passo_[6] or [] if isinstance(t_, int) and isinstance(s_, int) and t_ != s_}
            lotta_ = next(((s_, t_) for t_, s_ in sorted(fonti_l) if (s_, t_) in fonti_l), None)
            if lotta_:
                rel_ = dict(tipo="comb", att=[(lotta_[0], lotta_[1])], blocchi=[(lotta_[1], [lotta_[0]])])
        if passo_ and "Damage" not in passo_[0] and rel_ is passo_[3] and (rel_ or {}).get("tipo") == "comb":
            # niente duelli fuori dal passo del danno (15 nov 2026, Autore: «errori gravissimi nei combattimenti, che vengono svolti in maniera doppia»):
            # l'innesco che fa perdere vita mentre si dichiarano gli attaccanti (Sanguine Syphoner) faceva duellare tutti gli attaccanti col giocatore,
            # e poi di nuovo al danno vero
            rel_ = None
        if not mosse and not girate and not spinte_nuove and not (danni_ and rel_ and rel_.get("tipo") == "comb") \
                and not (cambi or girate_faccia or guadagni or rivelate or mescole or guardate or f.get("mn")):
            return
        # uno alla volta (14 nov 2026, Autore: «vorrei che non ci fossero animazioni contemporaneamente, ogni azione ha un suo spazio privato e poi la
        # successiva»): nell'ordine della partita; ogni carta che deve ancora arrivare resta nascosta finche' non tocca a lei
        mosse.sort(key=lambda m_: m_[6])
        self._voli_persi = []
        # la magia in pila di questo passo (un'abilita' d'entrata, quella dopo) compare quando quella risolta ha lasciato la pila: prima Seam Rip va in
        # campo, poi la sua abilita' sta in pila con la freccia (14 nov 2026)
        # (non si nasconde piu' la pila: la magia risolta, grande come la carta in pila, ci sta sopra finche' non va al suo posto; nasconderla toglieva
        # tutta la pila, anche le magie sotto: «la pila ancora appare e scompare», 14 nov 2026)
        it_p = getattr(self, "_pila_item", None)
        prima_pz = getattr(self, "_prima_pezzi", {}) or {}
        prima_sp = getattr(self, "_prima_spinte", {}) or {}
        pila_ora_ = getattr(self, "_pila_ora", None)
        id_di_box = {tuple(round(v) for v in v_[1]): k_ for k_, v_ in prima_pz.items()}
        az = []             # le azioni del passo, in ordine: dict(tipo, fase, ...)
        fantasmi = {}       # id -> l'immagine della creatura morta al suo posto (com'era nel passo prima, anche spostata in combattimento)
        grigi_id = {}       # id -> la sua immagine grigia
        voli = []
        for m__ in mosse:
            n, tap, da, a_, it_, pezzo, fase_ = m__[:7]
            svanisce = len(m__) > 7 and m__[7] == "svanisce"
            muore = len(m__) > 7 and m__[7] in ("muore", "svanisce")
            img, dx, dy = None, 0, 0
            if pezzo and it_ is not None:       # la carta arrivata vola com'e' sulla tavola (pedina, tappata, segnalini): la sua immagine, centrata come lei
                nome_img = c.itemcget(it_, "image")
                xy = c.coords(it_)
                if nome_img and xy:
                    w_i, h_i = int(c.tk.call("image", "width", nome_img)), int(c.tk.call("image", "height", nome_img))
                    img = nome_img
                    dx, dy = xy[0] + w_i / 2 - centro(a_)[0], xy[1] + h_i / 2 - centro(a_)[1]
            gruppo_v = None
            dalla_pila_ = pila_prima is not None and fase_ == 2 and da is pila_prima[0]
            if dalla_pila_:     # chi esce dalla pila e' grande come la carta in pila (poi arriva grande quanto il suo posto)
                img, dx, dy = self.immagine_pezzo(n, int(max(30, da[2] - da[0])), False), 0, 0
            if pezzo and it_ is not None and not dalla_pila_:       # una carta che si aggiunge a un gruppo che c'era gia' (una terra, una pedina uguale; 14 nov 2026, Autore: «non
                # facciamole sparire dal board per poi farle riapparire tutte piu' una, l'animazione ne porta una o piu' nuova in pila e si alza il numero»):
                # il gruppo resta a vista col numero di prima, vola una carta sola, all'arrivo il numero sale
                k_g = (getattr(self, "_gruppo_item", {}) or {}).get(it_)
                vecchio_g = (getattr(self, "_gruppi_prima", {}) or {}).get(k_g) if k_g else None
                ora_g = (getattr(self, "_gruppi_ora", {}) or {}).get(k_g) if k_g else None
                if vecchio_g and ora_g and ora_g[1] > vecchio_g[1]:
                    gruppo_v = vecchio_g[0]
                    w1 = int(max(30, round(min(a_[2] - a_[0], a_[3] - a_[1]) if tap else a_[2] - a_[0])))
                    img, dx, dy = self.immagine_pezzo(n, w1, tap), 0, 0
            if img is None and n == "dorso":       # il dorso delle carte dell'app (la sua pescata); verso la pila grande come la carta in pila
                verso_pila = pila_ora_ is not None and a_ is pila_ora_[0]
                img = self.immagine_dorso(int(max(30, (a_[2] - a_[0]) if verso_pila else (da[2] - da[0]))))
            grigia = None
            if img is None and muore:       # la creatura morta: com'era al suo posto, poi grigia, poi al cimitero
                w0 = int(max(30, round(min(da[2] - da[0], da[3] - da[1]))))
                img = self.immagine_pezzo(n, w0, tap)
                grigia = self.immagine_pezzo(n, w0, tap, grigia=True)
            if img is None:
                w0 = max(30, round(min(a_[2] - a_[0], a_[3] - a_[1]) if tap else a_[2] - a_[0]))
                # una pedina (il Ruolo Sorcerer che si attacca) ha l'immagine fra le pedine, non fra le carte: senza, il volo si perdeva (16 nov 2026)
                img = self.immagine_carta(n, int(w0), tap) or self.immagine_pezzo(n, int(w0), tap)
            if img is None:
                self._voli_persi.append(n)      # un volo senza immagine si perde: la caccia ai glitch lo segnala (G-VOLO-PERSO)
                continue
            vecchio_it = None
            if it_ is not None:
                c.itemconfigure(it_, state="hidden")
                self._nascoste.append(it_)
                if gruppo_v is not None and c.coords(it_):         # il gruppo col numero di prima, al suo posto, finche' la carta nuova non arriva
                    xy_g = c.coords(it_)
                    vecchio_it = c.create_image(xy_g[0], xy_g[1], image=gruppo_v, anchor="nw", tags="anim")
                    c.tag_lower(vecchio_it, it_)
                elif it_ is getattr(self, "_pila_item", None) and getattr(self, "_pila_img_prima", None):
                    # una carta che vola nella pila: intanto resta a vista la pila di prima (con le magie che c'erano), non una pila sparita
                    im_pp, xy_pp = self._pila_img_prima
                    vecchio_it = c.create_image(xy_pp[0], xy_pp[1], image=im_pp, anchor="nw", tags="anim")
                    c.tag_lower(vecchio_it, it_)
            (x0, y0), (x1, y1) = centro(da), centro(a_)
            id_m = id_di_box.get(tuple(round(v) for v in da)) if muore else None
            if id_m is not None and id_m in prima_sp:        # era avanzata in combattimento: resta dov'era
                x0, y0 = x0 + prima_sp[id_m][0], y0 + prima_sp[id_m][1]
            # ogni carta resta dov'era finche' non tocca a lei (14 nov 2026, Autore: «le carte scompaiono dal tavolo e appaiono in esilio e cimitero e dopo
            # arriva l'azione di trascinamento ... deve essere: spostamento dal tavolo a cimitero o esilio e solo alla fine appare la carta nell'area»): la
            # magia risolta ferma in pila, la creatura morta al suo posto, la carta esiliata, rimandata in mano o scartata dove stava, la carta che torna dal
            # cimitero sulla sua pila; non la carta che esce dal grimorio (resta il mazzo coperto) ne' la pedina appena creata (prima non c'era)
            dal_grimorio = any(da is z_ or (z_ is not None and tuple(da) == tuple(z_))
                               for z_ in (zc.get("lib_mio"), zc.get("lib_suo"), getattr(self, "_box_grimorio", None)))
            nasce = len(m__) <= 7 and fase_ == 1 and pezzo        # la pedina: nasce dalla pila
            resta_ = fase_ == 2 or muore or not (dal_grimorio and n != "dorso" or nasce)
            fermo_ = c.create_image(x0 + dx, y0 + dy, image=img, tags="anim") if resta_ else None
            if not muore and fermo_ is not None and fase_ == 0.5 and "Damage" in ((passo_ or [""])[0] or ""):
                # chi lascia il campo nel passo del danno senza morire (15 nov 2026: Overlord of the Mistmoors ucciso dal Demone va in esilio): il suo duello
                # combatte con la carta ferma al suo posto, come chi muore; senza, il duello spariva
                id_x = id_di_box.get(tuple(round(v) for v in da))
                if id_x is not None and id_x not in fantasmi:
                    fantasmi[id_x] = fermo_
            if muore and fermo_ is not None:
                if id_m is not None:
                    fantasmi[id_m] = fermo_
                    if grigia is not None:
                        grigi_id[id_m] = grigia
                if grigia is not None:
                    az.append(dict(tipo="grigio", fase=4, fermo=fermo_, img=grigia))
            if svanisce:
                w0 = int(max(30, round(min(da[2] - da[0], da[3] - da[1]))))
                voli.append(dict(tipo="via", fase=5 + fase_, fermo=fermo_, uscito=id_di_box.get(tuple(round(v) for v in da)), imgs=[self.immagine_pezzo(n, max(8, int(w0 * (1 - q_ / 7))), tap, grigia=True)
                                                                                 for q_ in range(1, 7)]))
                continue
            uscito = id_di_box.get(tuple(round(v) for v in da)) if fase_ == 0.5 else None      # chi lascia il campo: le sue frecce e i suoi danni vanno via con lui
            voli.append(dict(tipo="vola", fase=5 + fase_, img=img, x0=x0 + dx, y0=y0 + dy, x1=x1 + dx, y1=y1 + dy, it=it_, fermo=fermo_, n=n, nasce=nasce,
                             vecchio=vecchio_it, uscito=uscito, tiene=m__[8] if len(m__) > 8 and m__[7] == "attacca" else None,
                             tiene_img=self.immagine_pezzo(n, int(max(30, a_[2] - a_[0])), False) if len(m__) > 8 and m__[7] == "attacca" else None))
        # le carte rimaste in campo che nel passo nuovo stanno altrove (chi e' morto o uscito lascia un buco, uno nuovo fa spazio): restano dov'erano e
        # scivolano al posto nuovo solo dopo che chi va via e' arrivato (14 nov 2026, Autore: «quando una creatura muore e diventa grigia sul campo, la
        # creatura accanto le passa subito sotto per occuparne il posto senza aspettare che l'animazione di viaggio a cimitero o esilio si concluda»)
        # anche quando la carta cambia misura (le creature passano a due file): scivola e intanto cresce o si rimpicciolisce, mai di colpo (14 nov 2026)
        girati_id = {g_[0] for g_ in girate}
        ora_pz = getattr(self, "_pezzo_id", {}) or {}
        scivola = []
        for id_r, (it_r, box_r, tap_r, n_r) in ora_pz.items():
            if id_r in girati_id or id_r not in prima_pz:
                continue
            bp_ = prima_pz[id_r][1]
            (xa, ya), (xb, yb) = centro(bp_), centro(box_r)
            larg = lambda b_: (b_[3] - b_[1]) if tap_r else (b_[2] - b_[0])       # la larghezza della carta (girata: l'altezza del riquadro)
            wa, wb = larg(bp_), larg(box_r)
            if abs(xa - xb) > 3 or abs(ya - yb) > 3 or abs(wa - wb) > 3:
                misure = sorted({int(round(wa + (wb - wa) * q_ / 4)) for q_ in range(5)}, key=lambda w_: abs(w_ - wa))
                imgs = {w_: self.immagine_pezzo(n_r, max(12, w_), tap_r) for w_ in misure}
                if any(v_ is None for v_ in imgs.values()):
                    continue
                c.itemconfigure(it_r, state="hidden")
                self._nascoste.append(it_r)
                g_s = c.create_image(xa, ya, image=imgs[int(round(wa))], tags="anim")
                scivola.append(dict(id=id_r, it=it_r, g=g_s, xa=xa, ya=ya, xb=xb, yb=yb, wa=wa, wb=wb, imgs=imgs))
        self._scivola = scivola
        giri_ = []
        for _id, it_g, box_g, tap_g, n_g in girate:        # la carta com'era (stappata o tappata) finche' non tocca a lei
            img_g = self.immagine_carta(n_g, int(min(box_g[2] - box_g[0], box_g[3] - box_g[1])), not tap_g)
            if img_g is None:
                continue
            cx_g, cy_g = centro(box_g)
            fermo_g = c.create_image(cx_g, cy_g, image=img_g, tags="anim")
            c.itemconfigure(it_g, state="hidden")
            self._nascoste.append(it_g)
            giri_.append(dict(tipo="gira", fase=0, it=it_g, fermo=fermo_g))
        spinte_ = [dict(tipo="sposta", fase=1, it=it_s, dx=dx_s, dy=dy_s) for it_s, dx_s, dy_s, _i in spinte_nuove]
        # il passo del danno raccontato a duelli, uno alla volta (14 nov 2026, Autore: «i combattimenti con animazione non li sai risolvere, prova una strada
        # diversa per descriverli perche' il bambino non sta capendo nulla, i segnalini di danno non si leggono perche' passano dietro la carta»): il tavolo
        # si scurisce e restano in luce l'attaccante e chi lo ferma (o il giocatore, o il planeswalker); l'attaccante avanza fino a mettersi di fronte; una
        # scossa; i «-N» sopra a tutto (e la vita che cambia); chi muore diventa grigio; l'attaccante torna; la luce torna. Poi il duello dopo
        colpi_ = []
        if danni_ and rel_ and rel_.get("tipo") == "comb":
            pz = getattr(self, "_pezzo_id", {}) or {}
            pos_ = lambda k: self._pos_id.get(k) or self._pos_vita.get(k) or (prima_pz.get(k) or (None, None))[1]
            in_attesa = {v_["id"]: v_["g"] for v_ in scivola}      # chi deve ancora spostarsi: nel duello combatte la carta che aspetta al posto di prima
            item_ = lambda k: in_attesa.get(k) or (pz[k][0] if k in pz else fantasmi.get(k))
            colpiti_ = {str(b_) for b_, q_ in (passo_[5] or []) if q_}
            colpi_vita = {k_v: [q_ for b_, q_ in (passo_[5] or []) if b_ == k_v and q_] for k_v in ("vita_mio", "vita_suo")}
            n_vita = {"vita_mio": 0, "vita_suo": 0}
            self._vita_corsa = {"vita_mio": (prima.get("vite") or (None, None))[0], "vita_suo": (prima.get("vite") or (None, None))[1]}
            # duella solo chi in questo passo fa o riceve danno (15 nov 2026: col primo colpo di Lyra Dawnbringer duellavano tutti gli attaccanti, e poi
            # di nuovo nel passo del danno normale); senza chi infligge il danno (i Moments) come prima
            fonti_c = passo_[6] if len(passo_) > 6 else []
            # anche i danni da 0 (Market Gnome che attacca con forza 0, 16 nov 2026): l'attacco c'e', e si vede
            coinvolti_ = ({t_ for t_, q_, s_ in fonti_c or []} | {s_ for t_, q_, s_ in fonti_c or []}) \
                if fonti_c and any(len(d_) > 2 and d_[2] is not None for d_ in fonti_c) else None
            for a_id, tg in rel_.get("att") or []:
                bls = [b_id for b_id, aa in rel_.get("blocchi") or [] if a_id in aa]
                if coinvolti_ is not None and a_id not in coinvolti_ and not any(b_ in coinvolti_ for b_ in bls):
                    continue
                it_a = item_(a_id)
                if it_a is None or not c.coords(it_a):        # coords, non bbox: un oggetto nascosto (che si gira dopo) non ha riquadro
                    continue
                difese = []
                carta_ = lambda k: (prima_pz.get(k) or (None, None))[1] or pos_(k)     # il riquadro della carta (senza l'ombra), dove sta adesso
                for k_d in (bls or [tg]):
                    it_d = item_(k_d) if k_d not in ("vita_mio", "vita_suo") else None
                    bx_d = carta_(k_d)
                    if bx_d:
                        difese.append((k_d, it_d, bx_d))
                if not difese and bls and tg is not None and carta_(tg):
                    # i bloccanti non ci sono piu' (morti col primo colpo) e l'attaccante travolge: il duello va verso cio' che attacca (16 nov 2026,
                    # Timeline Culler dopo Stockpiling Celebrant)
                    difese.append((tg, item_(tg) if tg not in ("vita_mio", "vita_suo") else None, carta_(tg)))
                ba = carta_(a_id)
                if not difese or not ba:
                    continue
                ca = centro(ba)
                cb = (sum(centro(d_[2])[0] for d_ in difese) / len(difese), sum(centro(d_[2])[1] for d_ in difese) / len(difese))
                vx, vy = cb[0] - ca[0], cb[1] - ca[1]
                ln = max(1.0, math.hypot(vx, vy))
                ux, uy = vx / ln, vy / ln
                est = lambda b_: abs(ux) * (b_[2] - b_[0]) / 2 + abs(uy) * (b_[3] - b_[1]) / 2
                corsa = max(0.0, ln - est(ba) - max(est(d_[2]) for d_ in difese) + 6)      # fino a toccarlo
                morti_ = [k_ for k_ in [a_id] + [d_[0] for d_ in difese] if k_ in grigi_id and k_ in fantasmi]
                vita_ = []          # i colpi di questo attaccante al giocatore: (chi, quale colpo, quanto)
                for k_d, _i, _b in difese:
                    if k_d in colpi_vita and n_vita[k_d] < len(colpi_vita[k_d]):
                        vita_.append((k_d, n_vita[k_d], colpi_vita[k_d][n_vita[k_d]]))
                        n_vita[k_d] += 1
                # chi blocca viene incontro: tutti e due fanno meta' strada, si toccano
                # chi colpisce chi e quanto, dai danni veri del log (id di chi infligge e di chi riceve; 14 nov 2026, Autore: «le gocce di sangue segnano i
                # danni a caso senza guardare quale creatura in realta' li ha inflitti»): le gocce su chi riceve, le spade su chi infligge
                in_duello = {a_id} | {d_[0] for d_ in difese}
                fonti_ = passo_[6] if len(passo_) > 6 else []
                ricevuti_, inflitti_v = {}, {}
                for tgt_, q_, src_ in fonti_ or []:
                    if src_ in in_duello and (tgt_ in in_duello or (src_ == a_id and tgt_ in ("vita_mio", "vita_suo"))):
                        ricevuti_[tgt_] = ricevuti_.get(tgt_, 0) + q_
                        inflitti_v[src_] = inflitti_v.get(src_, 0) + q_
                nome_ = lambda k: ((pz.get(k) or prima_pz.get(k) or (None, None, None, None))[3]) if k not in ("vita_mio", "vita_suo") else None
                # chi infligge quanto, dal racconto del passo («X dealt N to Y»): la spada col numero su chi colpisce
                nomi_d = {k_: nome_(k_) for k_ in [a_id] + [d_[0] for d_ in difese]}
                bersagli_ = {"vita_mio": ("you",), "vita_suo": ("the opponent",)}
                inflitti = {}
                for _m, tx_ in (passo_[4] if len(passo_) > 4 else []):
                    if " dealt " not in tx_ or " to " not in tx_:
                        continue
                    chi_, resto_ = tx_.split(" dealt ", 1)
                    try:
                        q_, a_chi = resto_.split(" to ", 1)
                        q_ = int(q_)
                    except ValueError:
                        continue
                    for k_s, n_s in nomi_d.items():
                        if n_s and chi_ == n_s:
                            altri = [nomi_d.get(k_o) for k_o in nomi_d if k_o != k_s] + [w_ for k_o in nomi_d for w_ in bersagli_.get(k_o, ())]
                            if a_chi in altri or (k_s == a_id and a_chi in bersagli_.get(difese[0][0], ())):
                                inflitti[k_s] = inflitti.get(k_s, 0) + q_
                if fonti_ and any(len(d_) > 2 and d_[2] is not None for d_ in fonti_):     # i danni veri ci sono: valgono loro
                    inflitti = inflitti_v
                colpi_.append(dict(tipo="duello", fase=2, a=a_id, it=it_a, dif=difese, dx=ux * corsa, dy=uy * corsa, incontro=bool(bls), inflitti=inflitti,
                                   ricevuti=ricevuti_ if fonti_ and any(len(d_) > 2 and d_[2] is not None for d_ in fonti_) else None,
                                   ferite=[k_ for k_ in [a_id] + [d_[0] for d_ in difese] if str(k_) in colpiti_ and k_ not in ("vita_mio", "vita_suo")],
                                   morti=morti_, vita=vita_))
            gestiti = {fantasmi[k_] for d_ in colpi_ for k_ in d_["morti"]}
            self._fantasmi_ora, self._grigi_ora = dict(fantasmi), dict(grigi_id)
            az = [x_ for x_ in az if not (x_["tipo"] == "grigio" and x_["fermo"] in gestiti)]
        # le pile che ricevono una carta: finche' non arriva la prima, si vede com'erano (la carta di prima o il fondo vuoto, e il numero di prima)
        coperte = {}
        for v_ in [v__ for v__ in voli if v__["tipo"] == "vola"]:
            for k_z in ("cim_mio", "cim_suo", "esi_mio", "esi_suo"):
                r_z = zc.get(k_z)
                if r_z and k_z not in coperte and abs(v_["x1"] - centro(r_z)[0]) < 3 and abs(v_["y1"] - centro(r_z)[1]) < 3:
                    i_l = 0 if k_z.endswith("mio") else 1
                    lista_p = ((prima.get("cim" if k_z.startswith("cim") else "esi") or ([], []))[i_l]) or []
                    tp_ = getattr(self, "_tappeto", None)
                    w_z = int(r_z[2] - r_z[0])
                    base_p = getattr(self, "_base_prima", None)
                    m_z = 7
                    box_z = tuple(int(round(q)) for q in (r_z[0] - m_z, r_z[1] - m_z, r_z[2] + m_z, r_z[3] + m_z))
                    if base_p is not None and base_p.size == getattr(self, "_base_ora", base_p).size:
                        # la pila com'era, ritagliata dal tavolo del passo prima: la stessa carta, la stessa carta storta dietro, lo stesso fondo (14 nov
                        # 2026, Autore: «su esilio o cimitero appare una carta grigia»: l'immagine rifatta a parte non combaciava col tavolo)
                        from PIL import ImageTk as _ITk
                        img_z = _ITk.PhotoImage(base_p.crop(box_z))
                        self.__dict__.setdefault("_img_coperte", []).append(img_z)
                        coperte[k_z] = c.create_image(box_z[0], box_z[1], image=img_z, anchor="nw", tags="anim")
                        if c.find_withtag("ombra"):         # sotto l'ombra di chi non agisce, come la pila vera
                            c.tag_lower(coperte[k_z], "ombra")
                        img_z = None
                    elif lista_p:
                        img_z = self.immagine_carta(lista_p[0], w_z, False)
                    elif tp_ is not None:
                        from PIL import ImageTk as _ITk
                        img_z = _ITk.PhotoImage(tp_.fondo().crop(tuple(int(round(q)) for q in r_z)))
                        self.__dict__.setdefault("_img_coperte", []).append(img_z)
                    else:
                        img_z = None
                    if img_z is not None:
                        coperte[k_z] = c.create_image(centro(r_z)[0], centro(r_z)[1], image=img_z, tags="anim")
                    if k_z in coperte:
                        et_ = (getattr(self, "_etichette_pile", {}) or {}).get(k_z)
                        if et_:
                            v_et = c.itemcget(et_, "text")
                            import re as _re
                            c.itemconfigure(et_, text=_re.sub(r"\d+(?=\s*$)", str(len(lista_p)), v_et))
                            coperte[k_z] = (coperte[k_z], et_, v_et)
                        else:
                            coperte[k_z] = (coperte[k_z], None, None)
                    v_["scopre"] = k_z
        mostra_danni = bool(colpi_) and bool(c.find_withtag("danni"))
        if mostra_danni:
            c.itemconfigure("danni", state="hidden")
        # le vite cambiano quando compare il danno, non all'inizio del passo (14 nov 2026, Autore: «la life dell'avversario se colpita indica il danno ma
        # non cambia all'istante»): il fondo e' gia' quello nuovo, quindi sopra il cerchio delle vite si mette quello di prima finche' non tocca ai danni
        vite_coperte, vite_cop_k = [], {}
        base_p = getattr(self, "_base_prima", None)
        if mostra_danni and base_p is not None and base_p.size == getattr(self, "_base_ora", base_p).size:
            from PIL import ImageTk as _ITk
            for k_v, i_v in (("vita_mio", 0), ("vita_suo", 1)):
                r_v = self._pos_vita.get(k_v)
                if r_v and (prima.get("vite") or (None, None))[i_v] != (f.get("vite") or (None, None))[i_v] and k_v not in guadagni:
                    m_ = 6
                    box_v = tuple(int(round(q)) for q in (r_v[0] - m_, r_v[1] - m_, r_v[2] + m_, r_v[3] + m_))
                    img_v = _ITk.PhotoImage(base_p.crop(box_v))
                    self.__dict__.setdefault("_img_coperte", []).append(img_v)
                    vite_coperte.append(c.create_image(box_v[0], box_v[1], image=img_v, anchor="nw", tags="anim"))
                    vite_cop_k[k_v] = (vite_coperte[-1], img_v, box_v)
                    if c.find_withtag("ombra"):
                        c.tag_lower(vite_coperte[-1], "ombra")
        # (14 nov 2026, il censimento del replayer, Autore: «ok ora voglio che tu faccia un censimento tra il motore del gioco e quello che oggi il
        # replayer non valuta», poi «Sì, parti» sulle cinque animazioni): le carte rivelate (grandi al centro, poi tornano), la carta a due facce che si
        # gira, il grimorio che si rimescola, la vita che sale col cuore verde
        W_c, H_c = c.winfo_width(), c.winfo_height()
        # M1 (14 nov 2026, scelto da Autore fra tre disegni): il mana che paga una magia, dopo che le terre si sono girate. Dal 15 nov 2026 (Autore:
        # «l'accumulo di mana dalle terre adesso e' il logo del mana che dalle terre va verso il player / costruiamolo invece in basso a sx poco sotto l'area
        # your lands cosi' vediamo il mana accumulato e poi speso»): da ogni terra il suo simbolo vola nella vaschetta di chi paga e ci resta, uno alla volta;
        # poi, uno alla volta, i simboli lasciano la vaschetta e vanno sulla carta che si paga
        tp_m = getattr(self, "_tappeto", None)
        if f.get("mn") and tp_m is not None:
            n_paga = next((tx_.split("paid mana for ", 1)[1] for _m, tx_ in eventi_passo if "paid mana for " in tx_), None)
            mio_p = any(m_ and "paid mana for " in tx_ for m_, tx_ in eventi_passo)
            # dove va il mana (16 nov 2026, Autore: «a volte il mana dal mana pool va verso il mazzo e altre volte verso la pila senza capirsi»): sulla
            # carta che si paga, cercata anche per meta' nome (Room, Omen, avventure) e in ogni zona a vista (la fila PLAYABLE, le pile); per l'avversario
            # sui dorsi della sua mano che si vedono, non sul riquadro della sua mano che senza zoom sta per meta' fuori dal bordo alto
            dest_p = None
            if mio_p:
                dest_p = next((z_[2] for z_ in self._box_zona if z_[0] == "mano" and stessa(z_[1], n_paga)), None)                     or next((z_[2] for z_ in self._box_zona if stessa(z_[1], n_paga)), None)
            else:
                its_s = [it_ for it_ in (getattr(self, "_mano_suo_items", None) or []) if c.bbox(it_)]
                bb_s = c.bbox(*its_s) if its_s else None
                if bb_s:
                    dest_p = (bb_s[0], max(bb_s[1], 4), bb_s[2], max(bb_s[3], 40))
                else:
                    dest_p = getattr(self, "_mano_suo_box", None)
            if f.get("mnd") is not None and self._pos_id.get(f["mnd"]):     # l'abilita' o il permanente pagato: il mana va su di lui (15 nov 2026)
                dest_p = self._pos_id[f["mnd"]]
            if dest_p is None:
                dest_p = getattr(self, "_stack_box", None)
            chi_m = "mio" if mio_p else "suo"
            da_terre = [(self._pos_id.get(id_m), col_m) for id_m, col_m in f["mn"] if self._pos_id.get(id_m)]
            if da_terre and dest_p and f"pool_{chi_m}" in tp_m.L["ZONE"]:
                gia_ = getattr(self, "_pool_n", {}).get(chi_m, 0)
                tutti_c = list((getattr(self, "_pool_col", None) or {}).get(chi_m) or [])[:gia_]
                tutti_c += ["?"] * (gia_ - len(tutti_c)) + [col_m for _b, col_m in da_terre]
                posti_m, lato_m, idx_m = tp_m.posti_pool_gruppi(chi_m, tutti_c)
                nella_ = []        # i simboli arrivati nella vaschetta: li spende l'azione dopo
                badge_ = []        # i numeri dei simboli impilati: se ne vanno con loro
                conta_m = {}       # quanti simboli ha gia' ogni posto (la riserva di prima); ogni arrivo fa salire il numero del suo
                for i_m in idx_m[:gia_]:
                    conta_m[i_m] = conta_m.get(i_m, 0) + 1
                for (b_m, col_m), (xp_, yp_), i_m in zip(da_terre, posti_m[gia_:], idx_m[gia_:]):
                    img_m = self.immagine_mana(col_m, lato_m)
                    if img_m is not None:
                        voli.append(dict(tipo="mana", fase=5.1, img=img_m, x0=centro(b_m)[0], y0=b_m[1] - 6, x1=xp_, y1=yp_, resta=nella_,
                                         posto=(chi_m, i_m), conta=conta_m, lato=lato_m, badge=badge_))
                if nella_ is not None and any(v_.get("resta") is nella_ for v_ in voli):
                    voli.append(dict(tipo="spendi", fase=5.15, its=nella_, x1=centro(dest_p)[0], y1=centro(dest_p)[1], badge=badge_))
        if guardate:        # S1 (14 nov 2026, scelto da Autore fra tre disegni: «Scry 1»): le carte guardate a ventaglio sopra il mazzo, TOP o BOTTOM
            mio_s = guardate[0][1]
            r_l = zc.get("lib_mio" if mio_s else "lib_suo")
            if r_l:
                w_s = int(max(60, (r_l[2] - r_l[0]) * 1.6))
                imgs_s = [(self.immagine_pezzo(e_s[0], w_s, False) if e_s[0] else None) or self.immagine_dorso(w_s) for e_s in guardate]
                if all(im_ is not None for im_ in imgs_s):
                    h_s = int(c.tk.call("image", "height", imgs_s[0]))
                    passo_s = w_s + 14
                    cx_l, cy_l = centro(r_l)
                    # accanto al mazzo, verso il tavolo, alla stessa altezza: fuori da cimitero ed esilio (14 nov 2026, la prima foto: sopra il mazzo le
                    # carte coprivano le due pile ed erano piccole)
                    # nello spazio aperto della meta' del tavolo di chi guarda, fra il centro e il mazzo: lontano da vite, mano, cimitero ed esilio
                    # (14 nov 2026, le prime due foto: sopra il mazzo coprivano le pile, accanto coprivano la vita e la mano)
                    bordo_v = min([r_l[0]] + [zc[k_z][0] for k_z in (("cim_mio", "esi_mio") if mio_s else ("cim_suo", "esi_suo")) if zc.get(k_z)])
                    cx_v = min((W_c * 0.5 + r_l[0]) / 2, bordo_v - 30 - (len(imgs_s) - 1) * passo_s / 2 - w_s / 2)
                    xs_ = [cx_v + (k_ - (len(imgs_s) - 1) / 2) * passo_s for k_ in range(len(imgs_s))]
                    y_v = H_c * (0.62 if mio_s else 0.36)
                    voli.append(dict(tipo="scry", fase=5.2, imgs=imgs_s, sopra=[e_s[2] for e_s in guardate], sorv=[len(e_s) > 3 and e_s[3] for e_s in guardate], x0=cx_l, y0=cy_l, xs=xs_, y=y_v,
                                     h=h_s, mio=mio_s))
        for n_r, mio_r in rivelate:
            r_l = zc.get("lib_mio" if mio_r else "lib_suo")
            img_r = self.immagine_pezzo(n_r, 210, False)
            if r_l and img_r is not None:
                voli.append(dict(tipo="rivela", fase=5.3, img=img_r, x0=centro(r_l)[0], y0=centro(r_l)[1], x1=W_c / 2, y1=H_c / 2, n=n_r))
        for id_g, (lato_g, vecchio_g, nuovo_g) in girate_faccia.items():
            v_s = next((v_ for v_ in scivola if v_["id"] == id_g), None)
            pz_g = ora_pz.get(id_g)
            if not pz_g:
                continue
            it_g, box_g, tap_g, _n = pz_g
            box0 = prima_pz[id_g][1] if v_s is not None and id_g in prima_pz else box_g
            w_g = int(max(30, round(min(box0[2] - box0[0], box0[3] - box0[1]) if tap_g else box0[2] - box0[0])))
            vecchie, nuove_ = self.immagini_giro(vecchio_g, w_g, tap_g, False), self.immagini_giro(nuovo_g, w_g, tap_g, True)
            if not vecchie or not nuove_:
                continue
            fermo_g = c.create_image(centro(box0)[0], centro(box0)[1], image=vecchie[0], tags="anim")
            if v_s is not None:     # si sposta anche: prima si gira dov'era, poi scivola
                c.itemconfigure(v_s["g"], state="hidden")
            else:
                c.itemconfigure(it_g, state="hidden")
                self._nascoste.append(it_g)
            voli.append(dict(tipo="faccia", fase=5.4, fermo=fermo_g, imgs=vecchie + nuove_, mostra=v_s["g"] if v_s is not None else it_g))
        for mio_m in mescole:
            r_l = zc.get("lib_mio" if mio_m else "lib_suo")
            img_d = self.immagine_dorso(int(max(30, (r_l[2] - r_l[0]) * 0.9))) if r_l else None
            if img_d is not None:
                voli.append(dict(tipo="mescola", fase=9.5, img=img_d, x=centro(r_l)[0], y=centro(r_l)[1], w=r_l[2] - r_l[0]))
        for k_v, (pv, fv) in guadagni.items():
            c.itemconfigure(f"gu_{k_v}", state="hidden")
            cop_v = None
            r_v = self._pos_vita.get(k_v)
            if r_v and base_p is not None and base_p.size == getattr(self, "_base_ora", base_p).size:      # il numero di prima finche' non tocca al cuore
                from PIL import ImageTk as _ITk
                box_v = tuple(int(round(q)) for q in (r_v[0] - 6, r_v[1] - 6, r_v[2] + 6, r_v[3] + 6))
                img_v = _ITk.PhotoImage(base_p.crop(box_v))
                self.__dict__.setdefault("_img_coperte", []).append(img_v)
                cop_v = c.create_image(box_v[0], box_v[1], image=img_v, anchor="nw", tags="anim")
                if c.find_withtag("ombra"):
                    c.tag_lower(cop_v, "ombra")
            voli.append(dict(tipo="vita", fase=9, k=k_v, da=pv, a=fv, cop=cop_v))
        # i potenziamenti e gli indebolimenti (16 nov 2026, Autore: «nel log esistono ulteriori note che fino ad adesso non sono state considerate?»):
        # la creatura si accende e sopra le sale il «+3/+3», verde se cresce, rosso se cala, dopo che la magia che lo fa e' arrivata
        restano_ = {c_[5] for lato_ in ("mio", "suo") for c_ in f.get(lato_) or [] if len(c_) > 5}
        for i_f in f.get("pf") or []:       # il potenziamento finito: la carta si accende di grigio e le sale sopra «ENDS» (16 nov 2026)
            if i_f in restano_ and self._pos_id.get(i_f):
                voli.append(dict(tipo="potenzia", fase=8.6, box=self._pos_id[i_f], txt="ENDS", su=None))
        for i_p, dp_, dt_ in f.get("pt") or []:
            box_p = self._pos_id.get(i_p) if i_p in restano_ else (prima_pz.get(i_p) or (None, None))[1]
            if box_p:     # chi muore per il -2/-2 (Stab) lo riceve al suo posto di prima, prima di andare via (fase 0.4); gli altri dopo gli arrivi
                voli.append(dict(tipo="potenzia", fase=8.5 if i_p in restano_ else 0.4, box=box_p, txt=f"{dp_:+d}/{dt_:+d}", su=dp_ + dt_ >= 0))
        voli.sort(key=lambda v_: v_["fase"])
        if scivola:     # dopo chi va via (fase 5.5), prima di chi arriva; una carta alla volta, da sinistra (14 nov 2026, Autore: «immagina l'osservatore
            # come un bambino che vuole vedere ogni cosa arrivare per piccoli step che puo' capire uno alla volta»)
            k_s = next((k_ for k_, v_ in enumerate(voli) if v_["fase"] > 5.5), len(voli))
            ordine_s = sorted(range(len(scivola)), key=lambda q_: scivola[q_]["xa"])
            for q_ in reversed(ordine_s):
                voli.insert(k_s, dict(tipo="scivola", fase=5.75, k=q_))
        # il riquadro della pila, vuoto, quando una magia arriva in una pila vuota (c'e' prima che la carta ci voli dentro) o quando l'ultima esce (resta
        # finche' la magia risolta non e' andata al suo posto): mai il riquadro che compare o sparisce insieme alla carta
        tp_p = getattr(self, "_tappeto", None)
        pila_ora_ = getattr(self, "_pila_ora", None)
        it_pan = None
        if tp_p is not None and bool(pila_ora_) != bool(pila_prima):
            try:
                from PIL import ImageTk as _ITk
                pan_, px0, py0 = tp_p.pannello_pila()
                img_p = _ITk.PhotoImage(pan_)
                self.__dict__.setdefault("_img_coperte", []).append(img_p)
                it_pan = c.create_image(round(px0), round(py0), image=img_p, anchor="nw", tags="anim")
                if getattr(self, "_pila_item", None) is not None:
                    c.tag_lower(it_pan, self._pila_item)
                elif pila_prima:            # sotto la magia risolta, che sta ferma in pila finche' non va al suo posto
                    fermi_p = [v_["fermo"] for v_ in voli if v_.get("tipo") == "vola" and v_.get("fase") == 7 and v_.get("fermo")]
                    if fermi_p:
                        c.tag_lower(it_pan, fermi_p[0])
            except Exception:      # noqa: BLE001 - senza il riquadro si va avanti
                pass
        az = giri_ + spinte_ + colpi_ + ([dict(tipo="danni", fase=3)] if mostra_danni and not colpi_ else []) + az + voli
        self._ultime_az = az        # le azioni del passo, in ordine (per le prove)
        if not az and it_pan is not None and pila_ora_:       # la carta in pila e' gia' a vista: il riquadro sotto non serve
            c.delete(it_pan)
        if not az:        # niente da far vedere: cio' che era stato nascosto torna a vista, e via ogni pezzo provvisorio (il riquadro vuoto della pila: la caccia
            c.delete("anim")      # ai glitch del 15 nov 2026, b97a4757 al passo 76)
            for it__ in self._nascoste:
                c.itemconfigure(it__, state="normal")
            self._nascoste = []
            return
        n_voli = max(1, sum(1 for a__ in az if a__["tipo"] == "vola"))
        quadri = max(12, min(32, int(ANIM_TOTALE / 16 / n_voli)))      # ~0,5 s a volo (14 nov 2026: «tutto piu' lento»; erano 22 quadri)
        # niente insieme (14 nov 2026, Autore: «non devono esserci animazioni contemporaneamente, tutto deve svolgersi ad azione, pausa, risposta, pausa,
        # azione»): fra due azioni sempre una pausa (PAUSA_VOLI), piu' lunga fra due fasi (PAUSA_FASI); se il passo ha dei danni senza combattimento (una
        # magia), prima si vedono loro, poi, dopo una pausa, il resto
        attesa0 = (PAUSA_FASI if danni_ and not mostra_danni else 0) + getattr(self, "_ritardo_ombra", 0) + getattr(self, "_ritardo_frecce", 0)
        self._ritardo_frecce = 0        # vale per questo passo solo
        pause_ = [0] + [PAUSA_FASI if a__["fase"] != b__["fase"] else PAUSA_VOLI for a__, b__ in zip(az, az[1:])]
        dura = {"vola": (quadri + 1) * 16, "sposta": (PASSI_SPINTA + 1) * 16, "colpo": (2 * PASSI_COLPO + 1) * 16, "via": 7 * 45 + 16,
                "duello": DUELLO_MS + 2 * (PASSI_COLPO + 1) * 16, "rivela": 2 * (quadri + 1) * 16 + RIVELA_MS, "faccia": 12 * 45 + 16,
                "mescola": MESCOLA_MS, "scry": SCRY_MS + 3 * (quadri + 1) * 16, "mana": MANA_MS, "spendi": SPENDI_MS * max(1, len(f.get("mn") or [])), "vita": 120 + 110 * min(12, max([a__["a"] - a__["da"] for a__ in az if a__["tipo"] == "vita"] or [0])),
                "scivola": (PASSI_SPINTA + 1) * 16, "potenzia": POTENZIA_MS}
        self._durata_anim = attesa0 + sum(dura.get(a__["tipo"], 0) for a__ in az) + sum(pause_)     # il play aspetta (attesa_play)
        pausate = set()

        def avanti(j):
            alza_icone(c)
            self._anim_after.append(self.fin_board.after(16, lambda: esegui(j)))

        self._anim_in_corso = True      # la caccia ai glitch aspetta questo, non l'assenza di pezzi provvisori (fra due duelli non ce ne sono)

        def esegui(j):
            if j >= len(az):      # finite: niente in volo, tutte le carte al loro posto (le frecce arrivano dopo, col loro tempo)
                self._anim_in_corso = False
                self._scivola = []
                c.delete("anim")
                for it_f in getattr(self, "_frecce_duello", []) or []:      # le frecce spente dai duelli
                    if c.type(it_f):
                        c.itemconfigure(it_f, state="normal")
                self._frecce_duello = []
                for cop_ in coperte.values():
                    if cop_[1]:
                        c.itemconfigure(cop_[1], text=cop_[2])
                c.itemconfigure("danni", state="normal")
                c.itemconfigure("cuori", state="normal")
                alza_icone(c)
                for it__ in self._nascoste:
                    c.itemconfigure(it__, state="normal")
                self._nascoste = []
                return
            attesa_ = attesa0 if j == 0 else pause_[j]
            if attesa_ and j not in pausate:      # prima di ogni azione la sua pausa
                pausate.add(j)
                self._anim_after.append(self.fin_board.after(attesa_, lambda: esegui(j)))
                return
            a__ = az[j]
            t_ = a__["tipo"]
            if t_ == "gira":         # la carta si tappa o si stappa: com'era, poi com'e'
                c.delete(a__["fermo"])
                c.itemconfigure(a__["it"], state="normal")
                if a__["it"] in self._nascoste:
                    self._nascoste.remove(a__["it"])
                return esegui(j + 1)
            if t_ == "duello":
                return self.duello(c, a__, vite_cop_k, lambda: avanti(j + 1))
            if t_ == "potenzia":     # la creatura si accende e il «+3/+3» le sale sopra
                x0_, y0_, x1_, y1_ = a__["box"]
                col_ = "#9aa3b2" if a__["su"] is None else ("#39d98a" if a__["su"] else "#ff5d5d")
                c.create_rectangle(x0_ - 3, y0_ - 3, x1_ + 3, y1_ + 3, outline=col_, width=3, tags=("anim", "pot_box"))
                cx_, cy_ = (x0_ + x1_) / 2, (y0_ + y1_) / 2
                w_ = 30 + 8 * len(a__["txt"])
                pill_ = c.create_rectangle(cx_ - w_ / 2, cy_ - 15, cx_ + w_ / 2, cy_ + 15, fill="#1a1d24" if a__["su"] is None else ("#0b1a12" if a__["su"] else "#2a0c0c"), outline=col_, width=2,
                                           tags=("anim", "pot_pill"))
                txt_ = c.create_text(cx_, cy_, text=a__["txt"], fill=col_, font=self.F(16, True), tags=("anim", "pot_pill"))
                t_p = [None]

                def sale(k):
                    if t_p[0] is None:
                        t_p[0] = time.monotonic()
                    u_ = (time.monotonic() - t_p[0]) * 1000 / POTENZIA_MS
                    if u_ < 1.0:
                        dy_ = -(y1_ - y0_) * 0.35 * min(1.0, u_ * 1.6)
                        c.coords(pill_, cx_ - w_ / 2, cy_ - 15 + dy_, cx_ + w_ / 2, cy_ + 15 + dy_)
                        c.coords(txt_, cx_, cy_ + dy_)
                        c.tag_raise("pot_pill")
                        self._anim_after.append(self.fin_board.after(FOTOGRAMMA, lambda: sale(k + 1)))
                    else:
                        c.delete("pot_box")
                        c.delete("pot_pill")
                        avanti(j + 1)
                sale(0)
                return
            if t_ == "vita":         # la vita che sale: il cuore verde, poi il numero che sale
                k_v = a__["k"]
                c.itemconfigure(f"gu_{k_v}", state="normal")
                c.tag_raise(f"gu_{k_v}")
                tot_v = a__["a"] - a__["da"]
                valori = [a__["da"] + round(tot_v * (q_ + 1) / min(12, tot_v)) for q_ in range(min(12, tot_v))]

                def conta(k):
                    if k < len(valori):
                        self.numero_vita(c, k_v, valori[k])
                        if k == 0 and a__.get("cop") is not None:       # il numero di prima resta finche' non c'e' il primo numero nuovo
                            c.delete(a__["cop"])
                        c.tag_raise(f"gu_{k_v}")
                        self._anim_after.append(self.fin_board.after(110, lambda: conta(k + 1)))
                    else:
                        c.delete(f"vita_corsa_{k_v}")
                        avanti(j + 1)
                self._anim_after.append(self.fin_board.after(120, lambda: conta(0)))
                return
            if t_ == "faccia":       # la carta a due facce si gira: si stringe, cambia faccia, si riapre
                def giro(k):
                    if k < len(a__["imgs"]):
                        c.itemconfigure(a__["fermo"], image=a__["imgs"][k])
                        self._anim_after.append(self.fin_board.after(45, lambda: giro(k + 1)))
                    else:
                        c.delete(a__["fermo"])
                        c.itemconfigure(a__["mostra"], state="normal")
                        if a__["mostra"] in self._nascoste:
                            self._nascoste.remove(a__["mostra"])
                        avanti(j + 1)
                giro(1)
                return
            if t_ == "mescola":      # il grimorio che si rimescola: tre dorsi che si mischiano a destra e a sinistra
                its_ = [c.create_image(a__["x"], a__["y"], image=a__["img"], tags="anim") for _q in range(3)]
                t_m = [None]

                def mischia(k):
                    if t_m[0] is None:
                        t_m[0] = time.monotonic()
                    u_ = (time.monotonic() - t_m[0]) * 1000 / MESCOLA_MS
                    if u_ < 1.0:
                        amp = a__["w"] * 0.7 * math.sin(math.pi * u_)
                        for q_, it_q in enumerate(its_):
                            off = amp * math.sin(2 * math.pi * 3 * u_ + q_ * 2.1) * (1 if q_ % 2 else -1)
                            c.coords(it_q, a__["x"] + off, a__["y"] - q_ * 2)
                        self._anim_after.append(self.fin_board.after(FOTOGRAMMA, lambda: mischia(k + 1)))
                    else:
                        for it_q in its_:
                            c.delete(it_q)
                        avanti(j + 1)
                mischia(0)
                return
            if t_ == "spendi":       # la vaschetta si svuota: un simbolo alla volta va sulla carta che si paga e si spegne
                for it_b in a__.get("badge") or []:     # i numeri dei simboli impilati se ne vanno con loro
                    c.delete(it_b)

                def spendi(k):
                    if k >= len(a__["its"]):
                        return avanti(j + 1)
                    it_s = a__["its"][k]
                    xy_s = c.coords(it_s) or [a__["x1"], a__["y1"]]
                    t_s = [None]

                    def volo_s():
                        if t_s[0] is None:
                            t_s[0] = time.monotonic()
                        u_t = min(1.0, (time.monotonic() - t_s[0]) * 1000 / SPENDI_MS)
                        u = 1 - (1 - u_t) ** 3
                        c.coords(it_s, xy_s[0] + (a__["x1"] - xy_s[0]) * u, xy_s[1] + (a__["y1"] - xy_s[1]) * u)
                        if u_t < 1.0:
                            self._anim_after.append(self.fin_board.after(FOTOGRAMMA, volo_s))
                        else:
                            c.delete(it_s)
                            self._anim_after.append(self.fin_board.after(SPENDI_PAUSA, lambda: spendi(k + 1)))
                    volo_s()
                self._anim_after.append(self.fin_board.after(PAUSA_VOLI, lambda: spendi(0)))
                return
            if t_ == "mana":         # il simbolo esce dalla terra (sale un poco), poi vola nella vaschetta di chi paga e ci resta
                g_m = c.create_image(a__["x0"], a__["y0"], image=a__["img"], tags="anim")
                c.tag_raise(g_m)
                t_m = [None]

                def volo_m(k):
                    if t_m[0] is None:
                        t_m[0] = time.monotonic()
                    u_t = min(1.0, (time.monotonic() - t_m[0]) * 1000 / MANA_MS)
                    if u_t < 0.3:           # esce e sale
                        u = u_t / 0.3
                        c.coords(g_m, a__["x0"], a__["y0"] - 26 * (1 - (1 - u) ** 2))
                    else:                   # vola alla carta
                        u = 1 - (1 - (u_t - 0.3) / 0.7) ** 3
                        xa, ya = a__["x0"], a__["y0"] - 26
                        c.coords(g_m, xa + (a__["x1"] - xa) * u, ya + (a__["y1"] - ya) * u)
                    if u_t < 1.0:
                        self._anim_after.append(self.fin_board.after(FOTOGRAMMA, lambda: volo_m(k + 1)))
                    else:
                        if a__.get("resta") is not None:
                            a__["resta"].append(g_m)
                        else:
                            c.delete(g_m)
                        if a__.get("posto") is not None:      # oltre 6 simboli: nel posto c'era gia' lo stesso colore e il numero sale
                            cnt_, i_b = a__["conta"], a__["posto"][1]
                            cnt_[i_b] = cnt_.get(i_b, 0) + 1
                            if cnt_[i_b] > 1:
                                pb_ = getattr(self, "_pool_badge", None)
                                if pb_ is None:
                                    pb_ = self._pool_badge = {}
                                for it_b in pb_.pop(a__["posto"], None) or []:
                                    c.delete(it_b)
                                nuovo_b = self.badge_mana(c, a__["x1"], a__["y1"], a__["lato"], cnt_[i_b], "anim")
                                pb_[a__["posto"]] = nuovo_b
                                a__["badge"].extend(nuovo_b)
                        avanti(j + 1)
                volo_m(0)
                return
            if t_ == "scry":         # lo scry: le carte escono dal mazzo a ventaglio, ognuna col suo TOP o BOTTOM, poi una alla volta tornano sopra o vanno sotto
                its_s = [c.create_image(a__["x0"], a__["y0"], image=im_, tags="anim") for im_ in a__["imgs"]]
                for it_q in its_s:
                    c.tag_raise(it_q)
                t_s = [None]
                durata_s = max(1, quadri * 16)

                def tween(its, da_, a_, poi_, t0=[None]):
                    t0 = [None]

                    def q_(k):
                        if t0[0] is None:
                            t0[0] = time.monotonic()
                        u_t = min(1.0, (time.monotonic() - t0[0]) * 1000 / durata_s)
                        u = 1 - (1 - u_t) ** 3
                        for it_q, (xa, ya), (xb, yb) in zip(its, da_, a_):
                            c.coords(it_q, xa + (xb - xa) * u, ya + (yb - ya) * u)
                        if u_t < 1.0:
                            self._anim_after.append(self.fin_board.after(FOTOGRAMMA, lambda: q_(k + 1)))
                        else:
                            poi_()
                    q_(0)

                def etichette():        # TOP verde, BOTTOM rosso, sotto ogni carta
                    for k_e, (x_e, su_) in enumerate(zip(a__["xs"], a__["sopra"])):
                        y_e = a__["y"] + a__["h"] / 2 + 14
                        et_ = c.create_text(x_e, y_e, text="TOP" if su_ else ("GRAVEYARD" if a__["sorv"][k_e] else "BOTTOM"), fill="#ffffff", font=self.F(11, True),
                                            tags=("anim", "scry_et", f"scry_et{k_e}"))
                        bb_ = c.bbox(et_)
                        fo_ = c.create_rectangle(bb_[0] - 10, bb_[1] - 3, bb_[2] + 10, bb_[3] + 3, fill="#1e8a4f" if su_ else "#b03a3a", outline="",
                                                 tags=("anim", "scry_et", f"scry_et{k_e}"))
                        c.tag_lower(fo_, et_)
                    self._anim_after.append(self.fin_board.after(SCRY_MS, lambda: una(0)))

                def una(k):             # una alla volta: TOP torna sul mazzo, BOTTOM scende sotto il mazzo e sparisce
                    if k >= len(its_s):
                        c.delete("scry_et")
                        for it_q in its_s:
                            c.delete(it_q)
                        return avanti(j + 1)
                    su_ = a__["sopra"][k]
                    dy_ = a__["h"] * 0.35 if su_ else (a__["h"] * 0.9 if a__["mio"] else -a__["h"] * 0.9)
                    c.delete(f"scry_et{k}")        # l'etichetta va via con la sua carta
                    tween([its_s[k]], [(a__["xs"][k], a__["y"])], [(a__["x0"], a__["y0"] + (0 if su_ else dy_))],
                          lambda: (c.delete(its_s[k]), self._anim_after.append(self.fin_board.after(PAUSA_VOLI // 2, lambda: una(k + 1)))))
                tween(its_s, [(a__["x0"], a__["y0"])] * len(its_s), [(x_, a__["y"]) for x_ in a__["xs"]], etichette)
                return
            if t_ == "rivela":       # la carta rivelata: esce dal grimorio del suo proprietario, si mostra grande al centro, torna
                g_r = c.create_image(a__["x0"], a__["y0"], image=a__["img"], tags="anim")
                h_r = int(c.tk.call("image", "height", c.itemcget(g_r, "image")))
                c.tag_raise(g_r)
                t_r = [None, 0]

                def viaggio(k):
                    if t_r[0] is None:
                        t_r[0] = time.monotonic()
                    u_t = min(1.0, (time.monotonic() - t_r[0]) * 1000 / max(1, quadri * 16))
                    u = 1 - (1 - u_t) ** 3
                    andata = t_r[1] == 0
                    xa, ya, xb, yb = (a__["x0"], a__["y0"], a__["x1"], a__["y1"]) if andata else (a__["x1"], a__["y1"], a__["x0"], a__["y0"])
                    c.coords(g_r, xa + (xb - xa) * u, ya + (yb - ya) * u)
                    if u_t < 1.0:
                        self._anim_after.append(self.fin_board.after(FOTOGRAMMA, lambda: viaggio(k + 1)))
                    elif andata:        # al centro: «REVEALED», poi torna
                        t_r[0], t_r[1] = None, 1
                        et_ = c.create_text(a__["x1"], a__["y1"] + h_r / 2 + 16, text="REVEALED", fill="#ffffff", font=self.F(13, True), tags=("anim", "riv_et"))
                        bb_ = c.bbox(et_)
                        fondo_ = c.create_rectangle(bb_[0] - 12, bb_[1] - 4, bb_[2] + 12, bb_[3] + 4, fill="#2f9bff", outline="", tags=("anim", "riv_et"))
                        c.tag_lower(fondo_, et_)

                        def ritorno():
                            c.delete("riv_et")
                            viaggio(0)
                        self._anim_after.append(self.fin_board.after(RIVELA_MS, ritorno))
                    else:
                        c.delete(g_r)
                        avanti(j + 1)
                self._anim_after.append(self.fin_board.after(16, lambda: viaggio(1)))
                return
            if t_ == "danni":
                c.itemconfigure("danni", state="normal")
                alza_icone(c)
                for it_v in vite_coperte:       # e le vite, insieme ai danni
                    c.delete(it_v)
                return esegui(j + 1)
            if t_ == "grigio":       # la creatura morta diventa grigia al suo posto
                c.itemconfigure(a__["fermo"], image=a__["img"])
                return esegui(j + 1)
            if t_ == "scivola":      # una carta rimasta va al suo posto nuovo, e intanto prende la misura nuova
                tot_s = PASSI_SPINTA
                v_s = self._scivola[a__["k"]]
                c.tag_raise(v_s["g"])

                t_s = [None]

                def passo_s(k):
                    if t_s[0] is None:
                        t_s[0] = time.monotonic()
                    u_t = min(1.0, (time.monotonic() - t_s[0]) * 1000 / max(1, tot_s * 16))
                    u = u_t * u_t * (3 - 2 * u_t)       # parte e arriva piano
                    c.coords(v_s["g"], v_s["xa"] + (v_s["xb"] - v_s["xa"]) * u, v_s["ya"] + (v_s["yb"] - v_s["ya"]) * u)
                    w_u = v_s["wa"] + (v_s["wb"] - v_s["wa"]) * u
                    w_k = min(v_s["imgs"], key=lambda w_: abs(w_ - w_u))
                    c.itemconfigure(v_s["g"], image=v_s["imgs"][w_k])
                    if u_t < 1.0:
                        self._anim_after.append(self.fin_board.after(FOTOGRAMMA, lambda: passo_s(k + 1)))
                    else:       # arrivata: la carta vera al suo posto
                        c.delete(v_s["g"])
                        c.itemconfigure(v_s["it"], state="normal")
                        if v_s["it"] in self._nascoste:
                            self._nascoste.remove(v_s["it"])
                        avanti(j + 1)
                self._anim_after.append(self.fin_board.after(16, lambda: passo_s(1)))
                return
            if t_ == "via":          # la pedina grigia si rimpicciolisce e si spegne al suo posto
                imgs_ = [im_ for im_ in a__["imgs"] if im_ is not None]

                def stringi(k):
                    if k < len(imgs_):
                        c.itemconfigure(a__["fermo"], image=imgs_[k])
                        self._anim_after.append(self.fin_board.after(45, lambda: stringi(k + 1)))
                    else:
                        c.delete(a__["fermo"])
                        if a__.get("uscito") is not None:      # la pedina spenta: via anche i suoi «-N» e le sue frecce
                            self.via_con_lui(c, a__["uscito"])
                        avanti(j + 1)
                stringi(0)
                return
            if t_ in ("sposta", "colpo"):
                tot = PASSI_SPINTA if t_ == "sposta" else 2 * PASSI_COLPO

                def passo_m(k):
                    if t_ == "sposta":
                        u0, u1 = 1 - (1 - (k - 1) / tot) ** 3, 1 - (1 - k / tot) ** 3
                    else:       # avanti fino a meta', poi indietro
                        su_ = lambda q: (q / PASSI_COLPO) if q <= PASSI_COLPO else (2 - q / PASSI_COLPO)
                        u0, u1 = su_(k - 1), su_(k)
                    c.move(a__["it"], a__["dx"] * (u1 - u0), a__["dy"] * (u1 - u0))
                    if k < tot:
                        self._anim_after.append(self.fin_board.after(16, lambda: passo_m(k + 1)))
                    else:
                        avanti(j + 1)
                self._anim_after.append(self.fin_board.after(16, lambda: passo_m(1)))
                return
            x0, y0, x1, y1, it_, fermo_ = a__["x0"], a__["y0"], a__["x1"], a__["y1"], a__["it"], a__["fermo"]
            g_ = fermo_ if fermo_ is not None else c.create_image(x0, y0, image=a__["img"], tags="anim")
            c.tag_raise(g_)         # la carta in volo sta sopra a tutto: sopra le altre carte e sopra la pila coperta dove arriva
            sotto_ = None
            if a__.get("nasce"):    # la pedina esce da sotto la carta in pila che la crea (14 nov 2026, Autore: «dovrebbero fare scorrere da sotto di esse dalla
                # pila la pedina sul campo e poi risolvere la loro animazione»): parte dietro la magia, passa sopra quando ne e' uscita
                sotto_ = next((v_["fermo"] for v_ in az if v_.get("tipo") == "vola" and v_.get("fase") == 7 and v_.get("fermo")), None)                     or getattr(self, "_pila_item", None)
                if sotto_ is not None:
                    c.tag_lower(g_, sotto_)

            t_v, alzata = [None], [sotto_ is None]

            def quadro(k):          # guidato dal tempo vero (14 nov 2026, «potenziamo la fluidita'»): un fotogramma lento non rallenta il volo
                if t_v[0] is None:
                    t_v[0] = time.monotonic()
                u_t = min(1.0, (time.monotonic() - t_v[0]) * 1000 / max(1, quadri * 16))
                u = 1 - (1 - u_t) ** 3        # rallenta all'arrivo
                if not alzata[0] and u_t >= 0.33:
                    c.tag_raise(g_)
                    alzata[0] = True
                c.coords(g_, x0 + (x1 - x0) * u, y0 + (y1 - y0) * u)
                if u_t < 1.0:
                    self._anim_after.append(self.fin_board.after(FOTOGRAMMA, lambda: quadro(k + 1)))
                else:       # arrivata: la carta vera al suo posto, poi la prossima
                    if a__.get("tiene") is not None and c.coords(a__["tiene"]):     # l'aura resta dietro la carta che la porta, fino al passo dopo
                        if a__.get("tiene_img") is not None:       # grande come la carta che la porta (dalla pila arriva grande)
                            c.itemconfigure(g_, image=a__["tiene_img"])
                        c.dtag(g_, "anim")
                        c.addtag_withtag("aura_posata", g_)
                        c.tag_lower(g_, a__["tiene"])
                    else:
                        c.delete(g_)
                    if a__.get("uscito") is not None:      # uscita dal campo: i suoi «-N» e le frecce verso di lei non indicano piu' un posto vuoto (14 nov 2026,
                        self.via_con_lui(c, a__["uscito"])     # Autore: «segnalini e frecce restano visibili anche dopo che la creatura e' morta»)
                    if a__.get("vecchio") is not None:     # il gruppo col numero nuovo
                        c.delete(a__["vecchio"])
                    if it_ is not None:
                        c.itemconfigure(it_, state="normal")
                        if it_ in self._nascoste:
                            self._nascoste.remove(it_)
                    cop_ = coperte.pop(a__.get("scopre"), None)
                    if cop_:        # la prima carta arrivata nella pila: si vede la pila di adesso, col numero di adesso
                        c.delete(cop_[0])
                        if cop_[1]:
                            c.itemconfigure(cop_[1], text=cop_[2])
                    esegui(j + 1)
            self._anim_after.append(self.fin_board.after(16, lambda: quadro(1)))
        esegui(0)

    def via_con_lui(self, c, u_):
        """Chi ha lasciato il campo: via i suoi «-N», le sue spade e le frecce che lo toccano."""
        c.delete(f"dn_{u_}")
        c.delete(f"sp_{u_}")
        for it_f, fi_ in zip(getattr(self, "_frecce_ids", []), getattr(self, "_frecce_firme", [])):
            if fi_ and u_ in fi_[1:]:
                c.itemconfigure(it_f, state="hidden")
                if it_f in (getattr(self, "_frecce_duello", []) or []):
                    self._frecce_duello.remove(it_f)

    def schermata_finale(self, c, b, Wt, H):
        """La fine della partita sopra la tavola (14 nov 2026, Autore: «aggiungiamo in schermata finale se opponent concede / player win / player lost /
        player concede»): il tavolo in ombra, al centro YOU WIN in verde o YOU LOSE in rosso, sotto come e' finita (chi ha concesso, a 0 vite, il grimorio
        vuoto, il tempo). Si capisce anche senza leggere: il colore, la corona o la X. Dal 15 nov 2026 il banner broadcast (banner_finale)."""
        x = b.get("x") or {}
        vinta = x.get("vinta")
        if vinta is None:
            return
        fine = x.get("fine") or ""
        testi = " ".join(tx_ for q in b["passi"][-3:] for _m, tx_ in (q[4] if len(q) > 4 else [])).lower()
        if fine == "Opponent conceded":
            come = "OPPONENT CONCEDED"
        elif fine == "You conceded":
            come = "YOU CONCEDED"
        elif fine == "Timeout":
            come = "TIME RAN OUT"
        elif "library" in testi and "lost the game" in testi:
            come = ("OPPONENT" if vinta else "YOU") + " · EMPTY LIBRARY"
        elif "poison" in testi:
            come = ("OPPONENT" if vinta else "YOU") + " · POISONED"
        else:
            come = ("OPPONENT" if vinta else "YOU") + " · 0 LIFE"
        import re as _re
        m_t = _re.search(r"T(\d+)", b["passi"][-1][0] if b.get("passi") else "")
        if m_t:
            come += f" · T{m_t.group(1)}"
        concessa = fine == "You conceded"
        c.delete("finale")
        c.create_image(0, 0, image=self.velo(c, 3), anchor="nw", tags="finale")
        img_f = self.banner_finale("concessa" if concessa else ("vinta" if vinta else "persa"), come, int(min(Wt * 0.62, 860)))
        c.create_image(Wt / 2, H / 2, image=img_f, tags="finale")
        c.tag_raise("finale")

    def banner_finale(self, esito, come, largo):
        """La schermata finale in stile broadcast (15 nov 2026, Autore: «il redesign di victory loss e concede in stile esport allineato al design
        dell'app», fra tre proposte «A»): la barra inclinata a tutta larghezza come le barre dell'HUD sopra Arena, il blocco piu' scuro a sinistra col segno
        che si capisce senza leggere (la corona per la vittoria, la X per la sconfitta, la bandiera per la concessione), il risultato grande in Bahnschrift
        (VICTORY, DEFEAT, CONCEDED) e sotto il tab con come e' finita e il turno, col filo del colore (arancio per la concessione). Verde, rosso, grigio:
        la concessione non si confonde con la sconfitta a 0 vite. Disegnata a 4x e ridotta."""
        cache = self.__dict__.setdefault("_banner_finale", {})
        k = (esito, come, largo)
        if k in cache:
            return cache[k]
        from PIL import Image, ImageDraw, ImageTk
        import disegno_tappeto as DT
        S = 4
        stili = {"vinta": ((31, 191, 106), (17, 138, 74), (31, 191, 106), "VICTORY"), "persa": ((224, 38, 47), (156, 18, 25), (224, 38, 47), "DEFEAT"),
                 "concessa": ((58, 69, 86), (38, 47, 61), (255, 122, 26), "CONCEDED")}
        chiaro, scuro, filo, titolo = stili[esito]
        W_, hb, ht = largo, 116, 40
        H_ = hb + 18 + ht + 8
        im = Image.new("RGBA", (W_ * S, H_ * S), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        inc, m = 26 * S, 4 * S
        x0, y0, x1, y1 = m, m, W_ * S - m, hb * S
        barra = lambda e: [(x0 + inc - e, y0 - e), (x1 + e, y0 - e), (x1 - inc + e, y1 + e), (x0 - e, y1 + e)]
        d.polygon(barra(m * 0.9), fill=(4, 6, 10, 200))
        d.polygon(barra(0), fill=chiaro + (255,))
        xb = x0 + 150 * S
        d.polygon([(x0 + inc, y0), (xb + inc, y0), (xb, y1), (x0, y1)], fill=scuro + (255,))
        d.line([(x0 + inc, y0 + 2 * S), (x1 - 2 * S, y0 + 2 * S)], fill=(255, 255, 255, 70), width=2 * S)       # il filo chiaro in cima
        cx, cy = x0 + inc / 2 + 75 * S, (y0 + y1) / 2
        bianco = (255, 255, 255, 255)
        if esito == "vinta":            # la corona
            r = 30 * S
            d.polygon([(cx - r, cy + r * 0.6), (cx - r, cy - r * 0.45), (cx - r * 0.5, cy + r * 0.05), (cx, cy - r * 0.75), (cx + r * 0.5, cy + r * 0.05),
                       (cx + r, cy - r * 0.45), (cx + r, cy + r * 0.6)], fill=bianco)
            for dx_, dy_ in ((-1, -0.45), (0, -0.75), (1, -0.45)):
                d.ellipse((cx + dx_ * r - 5 * S, cy + dy_ * r - 5 * S, cx + dx_ * r + 5 * S, cy + dy_ * r + 5 * S), fill=bianco)
        elif esito == "persa":          # la X
            r, sp = 24 * S, 9 * S
            d.line([(cx - r, cy - r), (cx + r, cy + r)], fill=bianco, width=sp)
            d.line([(cx - r, cy + r), (cx + r, cy - r)], fill=bianco, width=sp)
        else:                           # la bandiera
            d.rectangle((cx - 20 * S, cy - 30 * S, cx - 15 * S, cy + 30 * S), fill=bianco)
            d.polygon([(cx - 15 * S, cy - 30 * S), (cx + 26 * S, cy - 19 * S), (cx - 15 * S, cy - 6 * S)], fill=bianco)
        f = DT.font(70 * S)
        bb = d.textbbox((0, 0), titolo, font=f)
        xt = (xb + inc / 2 + x1 - inc / 2) / 2
        d.text((xt - (bb[2] - bb[0]) / 2 - bb[0], cy - (bb[3] - bb[1]) / 2 - bb[1]), titolo, font=f, fill=bianco)
        ft = DT.font(17 * S)                                   # il tab sotto: come e' finita e il turno
        bt = d.textbbox((0, 0), come, font=ft)
        tw = (bt[2] - bt[0]) + 44 * S
        tx0, ty0 = W_ * S / 2 - tw / 2, (hb + 18) * S
        d.rectangle((tx0 - m, ty0 - m, tx0 + tw + m, ty0 + ht * S + m), fill=(4, 6, 10, 200))
        d.rectangle((tx0, ty0, tx0 + tw, ty0 + ht * S), fill=(20, 29, 42, 255), outline=filo + (255,), width=2 * S)
        col_t = (255, 176, 122, 255) if esito == "concessa" else (200, 212, 228, 255)
        d.text((W_ * S / 2 - (bt[2] - bt[0]) / 2 - bt[0], ty0 + ht * S / 2 - (bt[3] - bt[1]) / 2 - bt[1]), come, font=ft, fill=col_t)
        cache[k] = ImageTk.PhotoImage(im.resize((W_, H_), Image.LANCZOS))
        return cache[k]

    def velo(self, c, livello):
        """Il velo scuro su tutta la tavola (il duello: tutto in ombra tranne chi combatte), livello 1-4."""
        W_, H_ = max(1, c.winfo_width()), max(1, c.winfo_height())
        cache = self.__dict__.setdefault("_velo_duello", {})
        k = (W_, H_, livello)
        if k not in cache:
            from PIL import Image, ImageTk
            if len(cache) > 12:
                cache.clear()
            cache[k] = ImageTk.PhotoImage(Image.new("RGBA", (W_, H_), (4, 6, 10, int(VELO_ALFA * livello / 4))))
        return cache[k]

    def cerchio_vita(self, c, k_v, base):
        """Il cerchio della vita k_v ritagliato da un fondo (il numero di prima o quello nuovo), come oggetto della tela sopra il velo del duello."""
        r_v = self._pos_vita.get(k_v)
        if base is None or not r_v:
            return None
        from PIL import ImageTk as _ITk
        bv = tuple(int(round(q)) for q in (r_v[0] - 6, r_v[1] - 6, r_v[2] + 6, r_v[3] + 6))
        im_v = _ITk.PhotoImage(base.crop(bv))
        self.__dict__.setdefault("_img_coperte", []).append(im_v)
        return c.create_image(bv[0], bv[1], image=im_v, anchor="nw", tags=("anim", f"luce_{k_v}"))

    def duello(self, c, d, vite_cop_k, poi):
        """Un duello del passo del danno, a piccoli passi uno dopo l'altro (14 nov 2026, Autore: «prova una strada diversa per descriverli perche' il bambino
        non sta capendo nulla»): la luce su chi combatte (il resto sotto un velo scuro, solo le frecce di questo duello), l'attaccante e chi lo blocca si
        vengono incontro fino a toccarsi (contro il giocatore o il planeswalker avanza solo l'attaccante), la scossa, i «-N» sopra a tutto, la vita che scende
        colpo per colpo, chi muore grigio, si torna al posto, la luce torna. poi() quando ha finito."""
        it_a = d["it"]
        velo_it = []
        base_o = getattr(self, "_base_ora", None)
        blocchi_it = [d_[1] for d_ in d["dif"] if d_[1] is not None] if d.get("incontro") else []
        firme_mie = {("att", d["a"], k_d) for k_d, _i, _b in d["dif"]} | {("blk", k_d, d["a"]) for k_d, _i, _b in d["dif"]}

        def dopo(ms, f_):
            self._anim_after.append(self.fin_board.after(int(ms), f_))

        def esiste(it_):
            return it_ is not None and bool(c.coords(it_))

        def vita_sopra(k_v):        # il cerchio della vita sopra il velo: la copertura col numero di prima, o il numero che scende
            cop_ = vite_cop_k.get(k_v)
            if cop_ and c.type(cop_[0]):
                c.tag_raise(cop_[0])
            elif not c.find_withtag(f"vita_corsa_{k_v}"):
                self.cerchio_vita(c, k_v, base_o)
            c.tag_raise(f"vita_corsa_{k_v}")

        def luce(k=1):          # 1. il velo, e sopra chi combatte e le sue frecce
            if not velo_it:
                velo_it.append(c.create_image(0, 0, image=self.velo(c, 1), anchor="nw", tags="anim"))
                # le frecce degli altri attacchi spente per tutta la serie dei duelli (rimesse a fine passo: niente sfarfallio fra un duello e l'altro)
                spente_ = self.__dict__.setdefault("_frecce_duello", [])
                for it_f, fi_ in zip(getattr(self, "_frecce_ids", []), getattr(self, "_frecce_firme", [])):
                    if fi_ in firme_mie:
                        if it_f in spente_:
                            c.itemconfigure(it_f, state="normal")
                        c.tag_raise(it_f)
                    elif c.itemcget(it_f, "state") != "hidden":
                        c.itemconfigure(it_f, state="hidden")
                        spente_.append(it_f)
                for k_d, it_d, _b in d["dif"]:
                    if esiste(it_d):
                        c.tag_raise(it_d)
                    elif k_d in ("vita_mio", "vita_suo"):
                        vita_sopra(k_d)
                if esiste(it_a):
                    c.tag_raise(it_a)
                c.tag_raise(f"dn_{d['a']}")
            else:
                c.itemconfigure(velo_it[0], image=self.velo(c, k))
            if k < 4:
                dopo(70, lambda: luce(k + 1))
            else:
                dopo(PAUSA_VOLI, avanza)

        t_m = {}

        def muovi(fx, fy, k, tot, fine):        # si vengono incontro (o avanza l'attaccante), coi loro danni; guidato dal tempo vero
            chiave_m = (fx, fy)
            if k == 1 or chiave_m not in t_m:
                t_m[chiave_m] = [time.monotonic(), 0.0]
            t0_m, u_prima = t_m[chiave_m]
            u_t = min(1.0, (time.monotonic() - t0_m) * 1000 / max(1, tot * 16))
            u0, u1 = u_prima, u_t * u_t * (3 - 2 * u_t)
            t_m[chiave_m][1] = u1
            q_a = 0.5 if blocchi_it else 1.0
            mx, my = fx * (u1 - u0), fy * (u1 - u0)
            if esiste(it_a):
                c.move(it_a, mx * q_a, my * q_a)
            c.move(f"dn_{d['a']}", mx * q_a, my * q_a)
            c.move(f"sp_{d['a']}", mx * q_a, my * q_a)
            if blocchi_it:      # Tk ridipinge un rettangolo solo che copre tutto cio' che si e' mosso: con l'attaccante e chi lo blocca lontani era il
                c.update_idletasks()        # tavolo intero col velo da rimescolare (50-100 ms a fotogramma, 15 nov 2026): due ridipinture piccole
            for (k_d, it_d, _b) in d["dif"]:
                if it_d in blocchi_it and esiste(it_d):
                    c.move(it_d, -mx * 0.5, -my * 0.5)
                    c.move(f"dn_{k_d}", -mx * 0.5, -my * 0.5)
                    c.move(f"sp_{k_d}", -mx * 0.5, -my * 0.5)
            if u_t < 1.0:
                dopo(FOTOGRAMMA, lambda: muovi(fx, fy, k + 1, tot, fine))
            else:
                fine()

        def avanza():           # 2. fino a toccarsi
            muovi(d["dx"], d["dy"], 1, PASSI_COLPO, lambda: dopo(PAUSA_VOLI, lambda: scossa(0)))

        scosse = [6, -12, 12, -12, 6]

        def scossa(k):          # 3. l'urto
            if k < len(scosse):
                for it_ in [it_a] + [d_[1] for d_ in d["dif"]]:
                    if esiste(it_):
                        c.move(it_, scosse[k], 0)
                dopo(45, lambda: scossa(k + 1))
            else:
                dopo(150, danni)

        def danni():            # 4. i danni sull'angolo di ogni carta colpita, sopra a tutto; la vita scende di questo colpo
            if d.get("ricevuti") is not None:       # dai danni veri: una goccia per chi riceve, col danno di questo duello
                for k_f, q_f in d["ricevuti"].items():
                    if k_f in ("vita_mio", "vita_suo"):
                        r_v = self._pos_vita.get(k_f)
                        if not r_v:
                            continue
                        c.delete(f"dn_{k_f}")
                        c.create_image(r_v[0] + VITA_DX, (r_v[1] + r_v[3]) / 2 - 4, image=self.icona_danno("goccia", q_f), tags=("danni", f"dn_{k_f}"))
                        cop_ = vite_cop_k.get(k_f)
                        if cop_:
                            c.delete(cop_[0])
                        corsa_ = getattr(self, "_vita_corsa", {}) or {}
                        if corsa_.get(k_f) is not None:
                            corsa_[k_f] -= q_f
                            self.numero_vita(c, k_f, corsa_[k_f])
                    else:
                        it_f = it_a if k_f == d["a"] else next((d_[1] for d_ in d["dif"] if d_[0] == k_f), None)
                        if not esiste(it_f):
                            continue
                        bf = c.bbox(it_f)
                        c.delete(f"dn_{k_f}")
                        c.create_image(bf[2] + GOCCIA_DX, bf[1] + GOCCIA_DY, image=self.icona_danno("goccia", q_f), tags=("danni", f"dn_{k_f}"))
                    c.tag_raise(f"dn_{k_f}")
            for k_f in ([] if d.get("ricevuti") is not None else d["ferite"]):
                tag_ = f"dn_{k_f}"
                it_f = it_a if k_f == d["a"] else next((d_[1] for d_ in d["dif"] if d_[0] == k_f), None)
                bb_t = c.bbox(tag_)
                if bb_t and esiste(it_f):
                    bf = c.bbox(it_f)
                    c.move(tag_, (bf[2] + GOCCIA_DX) - (bb_t[0] + bb_t[2]) / 2, (bf[1] + GOCCIA_DY) - (bb_t[1] + bb_t[3]) / 2)
                c.itemconfigure(tag_, state="normal")
                c.tag_raise(tag_)
            for k_s, q_s in (d.get("inflitti") or {}).items():       # la spada col numero sull'angolo di chi colpisce, sopra a tutto
                it_s = it_a if k_s == d["a"] else next((d_[1] for d_ in d["dif"] if d_[0] == k_s), None)
                if q_s and esiste(it_s):
                    bs = c.bbox(it_s)
                    c.delete(f"sp_{k_s}")
                    c.create_image(bs[0] + SPADA_DX, bs[3] + SPADA_DY, image=self.icona_danno("spada", q_s), tags=("danni", f"sp_{k_s}"))
                    c.tag_raise(f"sp_{k_s}")
            for k_v, n_v, q_v in ([] if d.get("ricevuti") is not None else (d.get("vita") or [])):
                c.itemconfigure(f"dn_{k_v}_{n_v}", state="normal")
                corsa_ = getattr(self, "_vita_corsa", {}) or {}
                if corsa_.get(k_v) is not None:
                    corsa_[k_v] -= q_v
                    self.numero_vita(c, k_v, corsa_[k_v])
                c.tag_raise(f"dn_{k_v}_{n_v}")
            dopo(PAUSA_FASI, grigi)

        def grigi(k=0):         # 5. chi muore diventa grigio, uno alla volta
            if k < len(d["morti"]):
                fermo_ = (getattr(self, "_fantasmi_ora", {}) or {}).get(d["morti"][k])
                img_g = (getattr(self, "_grigi_ora", {}) or {}).get(d["morti"][k])
                if fermo_ is not None and img_g is not None:
                    c.itemconfigure(fermo_, image=img_g)
                dopo(PAUSA_VOLI, lambda: grigi(k + 1))
            else:
                torna()

        def torna():            # 6. ognuno torna al suo posto, la luce torna
            muovi(-d["dx"], -d["dy"], 1, PASSI_COLPO, lambda: dopo(PAUSA_VOLI, lambda: spegni(3)))

        def spegni(k):
            if k > 0 and velo_it:
                c.itemconfigure(velo_it[0], image=self.velo(c, k))
                dopo(70, lambda: spegni(k - 1))
            else:
                for it_ in velo_it:
                    c.delete(it_)
                poi()
        luce()

    def numero_vita(self, c, k_v, valore):
        """Il numero della vita che scende colpo per colpo nel passo del danno (un disco scuro sopra il numero del fondo e il numero nuovo), finche' il passo
        non finisce: poi resta il fondo, col numero finale."""
        r_v = self._pos_vita.get(k_v)
        if not r_v:
            return
        c.delete(f"vita_corsa_{k_v}")
        cx, cy = (r_v[0] + r_v[2]) / 2, (r_v[1] + r_v[3]) / 2
        R = (r_v[2] - r_v[0]) / 2
        c.create_oval(cx - R * 0.78, cy - R * 0.78, cx + R * 0.78, cy + R * 0.62, fill="#0c0e12", outline="", tags=("anim", f"vita_corsa_{k_v}"))
        c.create_text(cx, cy - R * 0.08, text=str(valore), fill="#ffffff", font=self.F(max(12, int(R * 0.55)), True), tags=("anim", f"vita_corsa_{k_v}"))

    def vista_azioni(self, b):
        """Nei Moments ricavati da Every action, la board vista come in Every action (la sequenza intera e l'indice dell'azione del momento): la usano le
        animazioni che guardano i passi prima nello stesso turno (la dichiarazione dell'attacco, le magie lanciate). 16 nov 2026."""
        if b and b.get("modo") == "momenti" and b.get("mom_idx") and not b.get("_pre") and b.get("azioni_passi") and 0 <= b.get("i", 0) < len(b["mom_idx"]):
            return dict(b, passi=b["azioni_passi"], i=b["mom_idx"][b["i"]], modo="azioni")
        return b

    def combattimento_dichiarato(self, b):
        """Nel passo del danno, attaccanti e blocchi come dichiarati nello stesso turno (14 nov 2026, Autore: «le carte non si spostano sui bloccanti ma
        entrambi attacco e difesa spariscono all'improvviso», «attaccante viene bloccato ... planeswalker riceve danno pur non essendo stato attaccato»):
        nel log il passo del danno puo' non avere piu' il bloccante (morto nello stesso messaggio) o avere un innesco al posto del combattimento. None se il
        passo non e' un danno o il turno non ha attacchi."""
        b = self.vista_azioni(b)
        if not b or not b.get("passi"):
            return None
        i_ = b.get("i", 0)
        passo_ = b["passi"][i_]
        if "Damage" not in passo_[0]:
            return None
        dich_ = None            # nel turno, la dichiarazione con piu' bloccanti (i blocchi si dichiarano uno alla volta; il passo del danno puo' averne meno)
        # e gli attaccanti di tutto il combattimento (15 nov 2026, il verificatore del combattimento: chi muore nello stesso messaggio del danno, Sun-Blessed
        # Healer bloccato o Felidar Savior col primo colpo del Nighthawk, non e' piu' fra gli attaccanti del passo, e il suo duello spariva); ci si ferma
        # fuori dalla fase di combattimento, cosi' un secondo combattimento nello stesso turno (Fear of Missing Out) resta a parte
        att_tutti = {}
        for q_ in range(i_, -1, -1):
            pq_ = b["passi"][q_]
            if pq_[2] != passo_[2] or not any(k_ in pq_[0] for k_ in ("Attack", "Block", "Damage", "BeginCombat")):
                break
            r_ = pq_[3]
            if r_ and r_.get("tipo") == "comb" and r_.get("att"):
                for a_ in r_["att"]:
                    k_a = a_[0] if isinstance(a_, (list, tuple)) else a_
                    att_tutti.setdefault(k_a, a_)
                if dich_ is None or len(r_.get("blocchi") or []) > len(dich_.get("blocchi") or []):
                    dich_ = r_
        if not dich_:
            return None
        if len(att_tutti) > len(dich_["att"]):
            dich_ = dict(dich_, att=list(att_tutti.values()))
        # un blocco vale solo se il danno lo conferma (14 nov 2026, la partita del 7 ottobre: «Mindseeker Oculus blocked Human Soldier» era una scelta che
        # l'avversario ha poi tolto; il danno e' andato a Jace): il bloccante o l'attaccante bloccato prendono danno in un passo del danno del turno
        return self.blocchi_veri(b, dich_, passo_[2])

    def blocchi_veri(self, b, rel, turno):
        """Tiene solo i blocchi che il danno del turno conferma: il bloccante o l'attaccante bloccato prendono danno (un blocco scelto e poi tolto
        dall'avversario resta nel log del passo dei bloccanti). Senza passi del danno nel turno, tutti."""
        b = self.vista_azioni(b)
        colpiti_t, c_danno = set(), False
        for pq_ in b["passi"]:
            if pq_[2] == turno and "Damage" in pq_[0] and len(pq_) > 5:
                c_danno = True
                colpiti_t |= {b_ for b_, q_ in (pq_[5] or []) if q_}
        if not c_danno or not rel.get("blocchi"):
            return rel
        veri = [(b_, aa) for b_, aa in rel.get("blocchi") or [] if b_ in colpiti_t or any(a_ in colpiti_t for a_ in aa)]
        return rel if len(veri) == len(rel.get("blocchi") or []) else dict(rel, blocchi=veri)

    def guadagno_board(self, c, prima, f, danni):
        """La vita che sale (14 nov 2026, il censimento): il cuore verde col «+N» accanto al cerchio della vita (sotto la goccia, se nello stesso passo ha
        anche perso vite). Si accende nell'animazione (anima_board, «vita»)."""
        if not prima or not f:
            return
        for k_v, i_v in (("vita_mio", 0), ("vita_suo", 1)):
            pv, fv = (prima.get("vite") or (None, None))[i_v], (f.get("vite") or (None, None))[i_v]
            r_ = self._pos_vita.get(k_v)
            if pv is None or fv is None or fv <= pv or not r_:
                continue
            gocce = any(b_ == k_v and q_ for b_, q_ in danni or [])
            cy = (r_[1] + r_[3]) / 2 + (PIASTRA_H + 4 if gocce else -4)
            c.create_image(r_[0] + VITA_DX, cy, image=self.icona_danno("cuore", fv - pv), tags=("cuori", f"gu_{k_v}"))

    def immagine_mana(self, col, lato):
        """Il simbolo di mana di Scryfall (W U B R G C) largo lato, col bordino bianco e l'ombra; se manca il file, un tondo col colore e la lettera."""
        cache = self.__dict__.setdefault("_img_mana", {})
        k = (col, lato)
        if k not in cache:
            try:
                from PIL import Image, ImageDraw, ImageTk
                import capsule
                try:
                    try:
                        import pymupdf as fitz
                    except ImportError:
                        import fitz
                    doc = fitz.open(capsule.file_simbolo(col)); pg = doc[0]; z = (lato * 4) / pg.rect.width
                    pm = pg.get_pixmap(matrix=fitz.Matrix(z, z), alpha=True)
                    sim = Image.frombytes("RGBA", (pm.width, pm.height), pm.samples)
                except Exception:      # noqa: BLE001 - il tondo disegnato
                    sim = Image.new("RGBA", (lato * 4, lato * 4), (0, 0, 0, 0))
                    ImageDraw.Draw(sim).ellipse((0, 0, lato * 4 - 1, lato * 4 - 1), fill={"W": (248, 231, 185), "U": (55, 138, 221), "B": (60, 50, 60),
                                                                                     "R": (226, 75, 74), "G": (99, 153, 34)}.get(col, (180, 178, 169)))
                S = lato * 4 + 16
                im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
                ImageDraw.Draw(im).ellipse((2, 2, S - 3, S - 3), fill=(255, 255, 255, 255))
                im.alpha_composite(sim.resize((lato * 4, lato * 4), Image.LANCZOS), (8, 8))
                cache[k] = ImageTk.PhotoImage(im.resize((lato + 4, lato + 4), Image.LANCZOS))
            except Exception:      # noqa: BLE001 - niente simbolo: niente volo
                cache[k] = None
        return cache[k]

    def immagini_giro(self, nome, w, tappata, nuova):
        """La carta che si gira (la faccia dietro di una carta a due facce): la carta stretta in orizzontale, da intera a una riga (nuova=False) o da una
        riga a intera (nuova=True)."""
        try:
            from PIL import Image, ImageTk
            try:
                import capsule
                im = Image.open(capsule.file_mini(nome)).convert("RGBA")
                im = im.resize((w, round(w * im.height / im.width)), Image.LANCZOS)
            except Exception:      # noqa: BLE001 - senza miniatura la faccia del tappeto
                import disegno_tappeto as DT
                im = DT.faccia(nome, w, False).copy()
            if tappata:
                im = im.rotate(90, expand=True)
            scale = [1.0, 0.8, 0.6, 0.4, 0.22, 0.06]
            out = [ImageTk.PhotoImage(im.resize((max(1, int(im.width * q_)), im.height), Image.LANCZOS)) for q_ in scale]
            return list(reversed(out)) if nuova else out
        except Exception:      # noqa: BLE001 - niente immagini: niente giro
            return None

    def badge_mana(self, c, x, y, lato, n, tag):
        """Il numero dei simboli di mana uguali impilati nella vaschetta: un tondo scuro col bordo bianco e «N», in basso a destra del simbolo (15 nov
        2026). -> gli id degli elementi."""
        r_ = max(7, lato * 0.30)
        bx, by = x + lato * 0.40, y + lato * 0.32
        o_ = c.create_oval(bx - r_, by - r_, bx + r_, by + r_, fill="#0b0e14", outline="#ffffff", width=1, tags=tag)
        t_ = c.create_text(bx, by, text=str(n), fill="#ffffff", font=self.F(7 if n < 10 else 6, True), tags=tag)
        return [o_, t_]

    def danni_board(self, c, danni, fonti=None):
        """I danni dell'azione: un tondo rosso col «-N» sulla carta o sul cuore colpito (la carta morta non c'e' piu': lo dice il racconto). fonti, fuori dal
        combattimento: [(bersaglio, quanto, chi infligge)]; la spada col numero su chi infligge se e' sul tavolo (15 nov 2026, il censimento: «la spada di chi
        infligge solo nei duelli»), non nella lotta (la disegna il duello)."""
        if fonti:
            coppie_ = {(t_, s_) for t_, _q, s_ in fonti}
            inflitti_ = {}
            for t_, q_, s_ in fonti:
                if s_ is not None and q_ and (s_, t_) not in coppie_ and self._pos_id.get(s_):
                    inflitti_[s_] = inflitti_.get(s_, 0) + q_
            for s_, q_ in inflitti_.items():
                bs = self._pos_id[s_]
                c.create_image(bs[0] + SPADA_DX, bs[3] + SPADA_DY, image=self.icona_danno("spada", q_), tags=("danni", f"sp_{s_}"))
        F = self.F
        prima_pz = getattr(self, "_prima_pezzi", {}) or {}
        n_colpo = {}
        somme, ordine_ = {}, []         # una goccia sola per carta colpita, col totale del passo (14 nov 2026: le gocce uguali una sopra l'altra mostravano l'ultima)
        for bers, q in danni or []:
            if bers not in somme:
                ordine_.append(bers)
            somme[bers] = somme.get(bers, 0) + (q or 0)
        danni = [(b_, somme[b_]) for b_ in ordine_]
        for bers, q in danni or []:         # la creatura morta in questo passo: dove stava (li' resta grigia finche' non va al cimitero)
            r_ = self._pos_id.get(bers) or self._pos_vita.get(bers) or (prima_pz.get(bers) or (None, None))[1]
            if not r_ or not q:
                continue
            cx, cy = (r_[0] + VITA_DX, (r_[1] + r_[3]) / 2) if bers in ("vita_mio", "vita_suo") else (r_[2] + GOCCIA_DX, r_[1] + GOCCIA_DY + 4)      # sul cuore: accanto, non sopra
            k_n = n_colpo.get(bers, 0)
            n_colpo[bers] = k_n + 1
            tg_ = ("danni", f"dn_{bers}", f"dn_{bers}_{k_n}")
            # la goccia di sangue col «-N» dentro (14 nov 2026, Autore, fra tre disegni: «vite A»): chi perde vite o costituzione
            c.create_image(cx, cy - 4, image=self.icona_danno("goccia", q), tags=tg_)

    def metti_giocabili(self, c, f):
        """Le tue giocate legali in questo passo (16 nov 2026, Autore: «nel log esistono ulteriori note che fino ad adesso non sono state considerate?»):
        Arena, a ogni tua priorita', manda le azioni che puoi fare; le carte che potevi lanciare, la terra che potevi giocare e i permanenti con un'abilita'
        attivabile si accendono col bordo azzurro, come in Arena. Senza priorita' tua nel passo, niente."""
        c.delete("giocabile")
        gioc = (f or {}).get("gioc") or []
        if not gioc:
            return
        vis = getattr(self, "_mano_vis", None) or []
        box_ = []
        usati = set()
        for n_g, i_g, k_g, z_g in gioc:
            if z_g == "campo" and self._pos_id.get(i_g):
                box_.append(self._pos_id[i_g])
            elif z_g == "mano":         # la mano: il bordo sta dentro il disegno della carta (disegno_tappeto.giocabile)
                pass
            else:       # dalla fila PLAYABLE (esilio, cimitero)
                for n2, b2, _it in (getattr(self, "_giocabili", {}) or {}).get("mio", []):
                    if n2 == n_g:
                        box_.append(b2)
                        break
        for b_ in box_:
            x0, y0, x1, y1 = b_
            c.create_rectangle(x0 - 2, y0 - 2, x1 + 2, y1 + 2, outline="#5acdff", width=2, tags="giocabile")
        if c.find_withtag("frecce"):
            c.tag_lower("giocabile", "frecce")

    def giocabili_col_solito(self, nomi):
        """Le carte che potevi giocare, ognuna con quanto rende di solito lanciarla in questa fase e tratto di partita col tuo mazzo (21 nov 2026, la
        revisione del range, punto 4: «il replayer valuta le carte giocabili»; solito_righe, gli stessi gradini del voto per fase). Dalla migliore; le
        abilita' («carta: testo») e le carte senza abbastanza esempi restano col solo nome."""
        b = getattr(self, "_board", None) or {}
        try:
            import ev_partita as EV_
            import solito_righe as SR
            passo = (b.get("passi") or [])[b.get("i", 0)]
            t = passo[2]
            fz = dict(f=EV_.FASE_PASSO.get(passo[0].split(" · ")[-1], "main1"), giro=(t + 1) // 2)
            base = [z for z in self.righe or [] if z["tipo"] == b["x"].get("tipo")]
        except Exception:       # noqa: BLE001
            return list(nomi)
        con, senza = [], []
        for n_ in nomi:
            if ": " in n_:
                senza.append(n_)
                continue
            try:
                so = SR.solito(b["x"], dict(testo=f"You cast {n_}", mio=True, incluso=False, ev=0.0), fz, base)
            except Exception:       # noqa: BLE001
                so = None
            # solo i gradini della carta o del suo tipo: «qualunque magia lanciata» non dice niente di questa carta (e una carta sconosciuta e' «Other»)
            if so and so.get("media") is not None and not so["gradino"].startswith("the same kind of play") and not so["gradino"].startswith("an other"):
                con.append((so["media"], f"{n_} (usually {so['media']:+.1f})".replace("-", "−")))
            else:
                senza.append(n_)
        return [t_ for _m, t_ in sorted(con, key=lambda z: -z[0])] + senza

    def righe_stato_avversario(self):
        """Quello che si sa di lui a fine del turno prima (stato_avversario, 21 nov 2026): le carte che puo' giocare dall'esilio o dal cimitero e la
        rianimazione pronta. Fatti del tavolo, non stime (la rianimazione e' letta dal testo, grado C)."""
        b = getattr(self, "_board", None) or {}
        try:
            import stato_avversario as SA
            passo = (b.get("passi") or [])[b.get("i", 0)]
            st = SA.al_turno(b["x"], passo[2] - 1)
        except Exception:       # noqa: BLE001
            return []
        out = []
        if st.get("gioca"):
            out.append(("#ff9a3c", "HE CAN PLAY FROM " + " · ".join(f"{'EXILE' if z_ == 'esi' else 'GRAVEYARD'}: {n_}" for n_, z_ in st["gioca"][:4])))
        if st.get("rianima"):
            out.append(("#ff9a3c", f"HIS GRAVEYARD · {', '.join(st['bersagli'][:3])} can come back"
                        + (f" ({', '.join(st['modo_rianima'][:2])})" if st.get("modo_rianima") else "")))
        if st.get("noti"):
            out.append(("#ff9a3c", "IN HIS HAND, KNOWN · " + ", ".join(st["noti"][:5])))
        return out

    def righe_info(self, f):
        """Le righe del racconto che vengono da cosa Arena ti ha chiesto e detto in questo passo (16 nov 2026, Autore: «vai monta»)."""
        inf = (f or {}).get("info") or {}
        out = []
        if inf.get("dado") and inf["dado"][0] is not None:
            out.append(("#c8ccd6", f"DIE ROLL · you {inf['dado'][0]} · opponent {inf['dado'][1]}"))
        if inf.get("mul"):
            out.append(("#c8ccd6", f"MULLIGANS · you {inf['mul'][0]} · opponent {inf['mul'][1]}"))
        if inf.get("parte"):
            out.append(("#c8ccd6", f"YOU CHOSE TO GO {inf['parte'].upper()}"))
        if inf.get("mdec"):
            out.append(("#c8ccd6", "YOUR HAND · " + " → ".join("kept" if d_ == "AcceptHand" else "mulligan" for d_ in inf["mdec"])))
        for n_, z_ in inf.get("trz") or []:
            out.append(("#b58cff", f"TRIGGERED FROM THE {z_.upper()} · {n_}"))
        if inf.get("opz"):
            n_, r_ = inf["opz"]
            out.append(("#ffd23f", f"YOU MAY · {n_}" + (f" · you said {'YES' if 'Yes' in r_ else 'NO'}" if r_ else "")))
        if inf.get("cerca") is not None:
            out.append(("#ffd23f", "YOU SEARCHED · " + (", ".join(inf["cerca"]) if inf["cerca"] else "found nothing")))
        for a_, bb_ in inf.get("div") or []:
            out.append(("#ff8a5c", f"YOU DIVIDED THE DAMAGE OF {a_} · " + ", ".join(f"{b_} {q_}" for b_, q_ in bb_)))
        if inf.get("canc"):
            out.append(("#9aa3b2", "YOU CANCELED AN ACTION"))
        if inf.get("auto"):
            out.append(("#9aa3b2", "MANA PAID AUTOMATICALLY"))
        if inf.get("conc"):
            out.append(("#ff5d5d", "YOU CONCEDED HERE"))
        if inf.get("pp"):      # hai chiuso il turno potendo ancora giocare (dal tuo client): un indizio, non per forza un errore
            out.append(("#ff9a3c", "YOU PASSED THE TURN · could still play " + ", ".join(inf["pp"][:6]) + (f" +{len(inf['pp']) - 6}" if len(inf["pp"]) > 6 else "")))
        for mio_, fr_ in inf.get("ch") or []:
            out.append(("#ffe08a", f"{'YOU SAY' if mio_ else 'OPPONENT SAYS'} · {fr_}"))
        if inf.get("gioc"):
            out.append(("#5acdff", "YOU COULD PLAY · " + ", ".join(self.giocabili_col_solito(inf["gioc"][:8]))
                        + (f" +{len(inf['gioc']) - 8}" if len(inf["gioc"]) > 8 else "")))
        out += self.righe_stato_avversario()
        if inf.get("pa"):
            out.append(("#39d98a", f"COULD ATTACK · {len(inf['pa'])} creature{'s' if len(inf['pa']) != 1 else ''}"))
        if inf.get("pb"):
            out.append(("#5acdff", f"COULD BLOCK · {len(inf['pb'])} creature{'s' if len(inf['pb']) != 1 else ''}"))
        if inf.get("lt"):
            out.append(("#c39bff", f"LEGAL TARGETS · {len(inf['lt'])}"))
        if inf.get("op"):
            out.append(("#ffd23f", "OPTIONS OFFERED · " + ", ".join(o_.replace("_", " ") for o_ in inf["op"])))
        if inf.get("sn"):
            mn_, mx_, nomi_ = inf["sn"]
            quanti = f"{mn_}" if mn_ == mx_ else f"{mn_}-{mx_}"
            out.append(("#ffd23f", f"CHOOSE {quanti} OF · " + ", ".join(nomi_[:6])))
        for n_, v_ in inf.get("pdd") or []:
            out.append(("#ff8a5c", f"PREDICTED DAMAGE · {n_}: {v_}"))
        for n_, r_ in inf.get("sp") or []:
            out.append(("#ff9a3c", f"ARENA WARNING · {n_}" + (f": {r_}" if r_ else "")))
        return out

    def metti_possibili(self, c, f):
        """Chi poteva attaccare (verde), chi poteva bloccare (azzurro) e i bersagli legali (viola), tratteggiati sulle carte, nel passo in cui Arena te
        li ha chiesti (16 nov 2026, «vai monta»)."""
        c.delete("possibili")
        inf = (f or {}).get("info") or {}
        for k_, col_ in (("pa", "#39d98a"), ("pb", "#5acdff"), ("lt", "#c39bff")):
            for i_ in inf.get(k_) or []:
                b_ = self._pos_id.get(i_)
                if b_:
                    c.create_rectangle(b_[0] - 4, b_[1] - 4, b_[2] + 4, b_[3] + 4, outline=col_, width=2, dash=(4, 3), tags="possibili")
        if c.find_withtag("frecce"):
            c.tag_lower("possibili", "frecce")

    def metti_sguardo(self, c, f):
        """Dove guarda l'avversario (16 nov 2026): le carte in campo o in pila che ha avuto sotto il mouse in questo passo hanno il bordo arancio
        tratteggiato e l'occhio in alto a destra, come nell'HUD sopra Arena."""
        c.delete("sguardo")
        for i_m in ((f or {}).get("info") or {}).get("hvm") or []:      # le carte che guardavi tu: un filo azzurro sottile
            b_m = self._pos_id.get(i_m)
            if b_m:
                c.create_rectangle(b_m[0] - 2, b_m[1] - 2, b_m[2] + 2, b_m[3] + 2, outline="#5acdff", width=1, dash=(2, 3), tags="sguardo")
        hv = (f or {}).get("hv") or []
        if not hv:
            return
        try:
            import disegno_tappeto as DT_
            from PIL import Image, ImageDraw, ImageTk as _ITk
            if not getattr(self, "_img_occhio_suo", None):
                im_o = DT_.icona_occhio(18, True)
                fondo_ = Image.new("RGBA", (28, 28), (0, 0, 0, 0))
                ImageDraw.Draw(fondo_).ellipse((0, 0, 27, 27), fill=(214, 120, 30, 245))
                fondo_.alpha_composite(im_o, ((28 - im_o.width) // 2, (28 - im_o.height) // 2))
                self._img_occhio_suo = _ITk.PhotoImage(fondo_)
        except Exception:      # noqa: BLE001 - senza l'icona resta il bordo
            self._img_occhio_suo = None
        pila_ids = {q[4]: q for q in (f.get("pila") or [])}
        for i_h in hv:
            b_ = self._pos_id.get(i_h) or (getattr(self, "_stack_box", None) if i_h in pila_ids else None)
            if not b_:
                continue
            x0, y0, x1, y1 = b_
            c.create_rectangle(x0 - 2, y0 - 2, x1 + 2, y1 + 2, outline="#ff9a3c", width=2, dash=(6, 4), tags="sguardo")
            if self._img_occhio_suo is not None:
                c.create_image(x1 - 4, y0 + 4, image=self._img_occhio_suo, tags="sguardo")

    def frecce_board(self, c, rel, pila_box, W, H):
        """Le frecce di chi interagisce con chi (12 nov 2026, Autore: «una freccia che definisce quali carte interagiscono con quali altre, per vedere
        come si e' bloccato in combattimento o contro cosa e' stato lanciato uno spot removal»): nel combattimento dal bloccante all'attaccante (gialle) e
        dall'attaccante non bloccato al giocatore o al planeswalker che attacca (rosse); per una magia o un'abilita' dalla carta in pila ai bersagli (viola).
        Curve nitide in un'immagine sola sopra la tavola; la punta sul bordo della carta."""
        rimossi_ = []       # i permanenti che la magia toglie: REMOVED compare con le frecce, non prima che la magia arrivi in pila (16 nov 2026)
        dich_ = self.combattimento_dichiarato(getattr(self, "_board", None))
        if dich_ and (not rel or rel["tipo"] == "comb"):        # nel passo del danno le frecce del combattimento dichiarato (un innesco in pila resta suo)
            rel = dich_
        elif rel and rel["tipo"] == "comb" and getattr(self, "_board", None):      # nei passi della dichiarazione: niente frecce dei blocchi poi tolti
            b_f = self._board
            rel = self.blocchi_veri(b_f, rel, b_f["passi"][b_f["i"]][2])
        if not rel:
            return
        frecce = []
        prima_pz = getattr(self, "_prima_pezzi", {}) or {}
        dove = lambda k: self._pos_id.get(k) or self._pos_vita.get(k) or (prima_pz.get(k) or (None, None))[1]
        # un trucco in combattimento (24 nov 2026, verifica_frecce): sotto la freccia della magia restano quelle dell'attacco e dei blocchi
        rel_c = rel if rel["tipo"] == "comb" else rel.get("comb")
        if rel_c is not None and rel_c is not rel and getattr(self, "_board", None):
            b_f = self._board
            rel_c = dich_ or self.blocchi_veri(b_f, rel_c, b_f["passi"][b_f["i"]][2])
        if rel_c:       # prima gli attacchi, poi i blocchi: l'ordine in cui si dichiarano (14 nov 2026)
            bloccati = {a_ for _b, aa in rel_c["blocchi"] for a_ in aa}
            for a_, tg in rel_c["att"]:
                if a_ not in bloccati and dove(a_) and dove(tg):
                    frecce.append((dove(a_), dove(tg), "#ff5d5d", ("att", a_, tg)))
            for b_, aa in rel_c["blocchi"]:
                for a_ in aa:
                    if dove(b_) and dove(a_):
                        frecce.append((dove(b_), dove(a_), "#ffd23f", ("blk", b_, a_)))
        if rel["tipo"] == "spell" and pila_box:
            pile = {k_: (x0, y0, x1, y1) for x0, y0, x1, y1, _t, k_, _c in getattr(self, "_box_pile", [])}
            # una magia che ha per bersaglio un giocatore e toglie i suoi permanenti (Settle the Wreckage, un sacrificio: 13 nov 2026, Autore: «dovrebbe
            # esiliare le creature attaccanti ma nel replayer la freccia punta ai punti vita del giocatore»): le frecce vanno ai permanenti, non alle vite
            sui_permanenti = bool(rel.get("colpiti")) and all(isinstance(tg, str) and tg.startswith("vita") for tg in rel["bers"])
            for tg in rel["bers"]:
                if sui_permanenti:
                    continue
                if dove(tg):
                    frecce.append((pila_box, dove(tg), "#b58cff", ("spell", rel.get("nome"), tg)))
                elif (rel.get("fuori") or {}).get(tg, (None,))[0] == "pila" and tg in (getattr(self, "_pila_sotto", {}) or {}):
                    # una carta gia' in pila (una contromagia): la freccia resta nella pila, dalla cima alla barra della carta sotto (14 nov 2026)
                    frecce.append((pila_box, self._pila_sotto[tg], "#b58cff", ("spell", rel.get("nome"), tg)))
                elif (rel.get("fuori") or {}).get(tg, (None,))[0] in pile:       # un bersaglio nel cimitero o in esilio: la freccia va alla sua pila
                    frecce.append((pila_box, pile[rel["fuori"][tg][0]], "#b58cff", ("spell", rel.get("nome"), tg)))
            for k_ in rel.get("da") or []:      # chi l'ha fatta scattare: la freccia azzurra dalla causa all'abilita' in pila (15 nov 2026, TriggeringObject)
                if self._pos_id.get(k_):        # solo da una carta che c'e' (chi e' morto e ha fatto scattare «when it dies» non e' piu' li')
                    frecce.insert(0, (self._pos_id[k_], pila_box, "#5fd4ff", ("trig", rel.get("nome"), k_)))
            for k_ in rel.get("colpiti") or []:      # cio' che la magia ha tolto dal campo (un board wipe: tutto quello che spazza)
                if k_ not in rel["bers"] and dove(k_):
                    frecce.append((pila_box, dove(k_), "#ff5d5d", ("tolto", rel.get("nome"), k_)))
            for k_ in rel.get("colpiti") or []:
                if self._pos_id.get(k_):
                    rimossi_.append((k_, self._pos_id[k_]))
        self._frecce_ids, self._frecce_firme = [], []
        if not frecce:
            self.metti_rimossi(c, rimossi_)
            return
        self._img_frecce = []

        def bordo(r, verso):
            """Il punto sul bordo del riquadro r nella direzione del punto verso."""
            cx, cy = (r[0] + r[2]) / 2, (r[1] + r[3]) / 2
            dx, dy = verso[0] - cx, verso[1] - cy
            if dx == 0 and dy == 0:
                return cx, cy
            sx = (r[2] - r[0]) / 2 / abs(dx) if dx else float("inf")
            sy = (r[3] - r[1]) / 2 / abs(dy) if dy else float("inf")
            k = min(sx, sy)
            return cx + dx * k, cy + dy * k
        self._frecce_firme = [fr_[3] for fr_ in frecce]
        for a, b, col, _firma in frecce:
            ca, cb = ((a[0] + a[2]) / 2, (a[1] + a[3]) / 2), ((b[0] + b[2]) / 2, (b[1] + b[3]) / 2)
            p0, p2 = bordo(a, cb), bordo(b, ca)
            dx, dy = p2[0] - p0[0], p2[1] - p0[1]
            lung = max(1.0, math.hypot(dx, dy))
            ctrl = ((p0[0] + p2[0]) / 2 - dy / lung * lung * 0.18, (p0[1] + p2[1]) / 2 + dx / lung * lung * 0.18)     # un po' curva, si leggono anche sovrapposte
            if _firma and _firma[0] == "spell" and _firma[2] in (getattr(self, "_pila_sotto", {}) or {}):
                # verso una carta gia' in pila (una contromagia): esce dal fianco destro della carta in cima, gira fuori dalla pila e torna sulla barra della
                # carta presa di mira, cosi' si vede chi colpisce chi anche se stanno una sopra l'altra
                p0 = (a[2], (a[1] + a[3]) / 2)
                p2 = (b[2] - 4, (b[1] + b[3]) / 2)
                ctrl = (max(a[2], b[2]) + 90, (p0[1] + p2[1]) / 2)
            pts = [((1 - u) ** 2 * p0[0] + 2 * (1 - u) * u * ctrl[0] + u * u * p2[0], (1 - u) ** 2 * p0[1] + 2 * (1 - u) * u * ctrl[1] + u * u * p2[1])
                   for u in (i / 30 for i in range(31))]
            # ogni freccia un'immagine sua, grande quanto lei: compaiono una alla volta (14 nov 2026, Autore: «anche le frecce che appaiono sono azioni»)
            ux, uy = pts[-1][0] - pts[-3][0], pts[-1][1] - pts[-3][1]
            ul = max(1e-6, math.hypot(ux, uy))
            ux, uy = ux / ul, uy / ul
            tip = pts[-1]
            punta = [tip, (tip[0] - 16 * ux + 8 * uy, tip[1] - 16 * uy - 8 * ux), (tip[0] - 16 * ux - 8 * uy, tip[1] - 16 * uy + 8 * ux)]
            ox, oy = math.floor(min(x for x, _y in pts + punta)) - 12, math.floor(min(y for _x, y in pts + punta)) - 12
            ex, ey = math.ceil(max(x for x, _y in pts + punta)) + 12, math.ceil(max(y for _x, y in pts + punta)) + 12
            d = DG.Disegno(ex - ox, ey - oy)
            sp = lambda q: [(x - ox, y - oy) for x, y in q]
            d.linea(sp(pts), (0, 0, 0, 150), 6)       # l'ombra, per staccarla dalle carte
            d.linea(sp(pts), col, 3)
            d.poligono(sp(punta), riempi=col)
            d.cerchio(p0[0] - ox, p0[1] - oy, 5, riempi=col)
            im_ = d.foto(veloce=True)
            self._img_frecce.append(im_)
            self._frecce_ids.append(c.create_image(ox, oy, image=im_, anchor="nw", tags="frecce"))
        self.metti_rimossi(c, rimossi_)

    def metti_rimossi(self, c, rimossi):
        """REMOVED sui permanenti che la magia toglie, nella sequenza delle frecce (16 nov 2026, Autore: «a volte risultano removed dei permanenti quando
        ancora la carta che li doveva rimuovere non e' arrivata in pila»): ogni segno e' un gruppo della tela col suo tag, messo fra le frecce; con
        l'animazione resta nascosto e compare dopo le frecce, una volta arrivata la magia."""
        for k_, r_ in rimossi:
            tag_ = f"rem_{k_}"
            c.create_rectangle(r_[0] - 3, r_[1] - 3, r_[2] + 3, r_[3] + 3, outline="#ff5d5d", width=3, tags=("frecce", tag_))
            c.create_rectangle(r_[0] + 4, r_[3] - 40, r_[0] + 62, r_[3] - 24, fill="#ff5d5d", outline="", tags=("frecce", tag_))
            c.create_text(r_[0] + 33, r_[3] - 32, text="REMOVED", fill="#ffffff", font=self.F(6, True), tags=("frecce", tag_))
            self._frecce_ids.append(tag_)
            self._frecce_firme.append(("rem", k_))


    def sopra_carta_board(self, e):
        """Il puntatore su una carta della tavola (o in cima a una pila): la carta grande accanto, come nelle liste dell'app (12 nov 2026, Autore: «lascia
        l'hover delle carte per poter vedere la versione grande sul replayer»)."""
        c = self.cv_board
        n = next((b_[4] for b_ in getattr(self, "_box_carte", []) if b_[0] <= e.x <= b_[2] and b_[1] <= e.y <= b_[3]), None)
        if n == getattr(self, "_hover_nome", None):
            if n is not None and getattr(self, "_hover", None) is not None:
                self.metti_hover(e)
            return
        self.via_hover()
        self._hover_nome = n
        c.configure(cursor="hand2" if n or any(b_[0] <= e.x <= b_[2] and b_[1] <= e.y <= b_[3] for b_ in getattr(self, "_box_pile", [])) else "")
        if n is None:
            return
        img = self.immagine_grande(n)
        if img is None:
            return
        tk = self.tk
        h = self._hover = tk.Toplevel(self.fin_board)
        h.overrideredirect(True)
        h.configure(bg="#0b0e14")
        try:
            h.attributes("-topmost", True)
        except Exception:      # noqa: BLE001 - non serve fuori da Windows
            pass
        tk.Label(h, image=img, bg="#0b0e14", bd=0).pack(padx=2, pady=2)
        self.metti_hover(e)

    def metti_hover(self, e):
        h = self._hover
        w, hh = h.winfo_reqwidth(), h.winfo_reqheight()
        x, y = e.x_root + 24, e.y_root - hh // 2
        sw, sh = h.winfo_screenwidth(), h.winfo_screenheight()
        if x + w > self.fin_board.winfo_rootx() + self.fin_board.winfo_width():
            x = e.x_root - w - 24
        h.geometry(f"+{max(0, x)}+{max(0, min(y, sh - hh - 40))}")

    def via_hover(self, e=None):
        h = getattr(self, "_hover", None)
        if h is not None:
            try:
                h.destroy()
            except Exception:      # noqa: BLE001 - gia' chiusa
                pass
        self._hover, self._hover_nome = None, None

    def immagine_grande(self, nome):
        """La carta grande (360 pixel) dall'immagine intera scaricata, se no dalla miniatura."""
        cache = self.__dict__.setdefault("_img_grandi", {})
        if nome not in cache:
            try:
                import capsule
                from PIL import Image, ImageTk
                f = capsule.file_immagine(nome)
                if not os.path.exists(f):
                    f = capsule.file_mini(nome)
                g_ = getattr(self, "_pedine_nomi", {}).get(nome)
                if not os.path.exists(f) and g_:        # una pedina: la sua immagine da Scryfall (pedine.py)
                    import pedine as PD
                    f = PD.file(g_)
                im = Image.open(f).convert("RGBA")
                im = im.resize((360, round(360 * im.height / im.width)), Image.LANCZOS)
                cache[nome] = ImageTk.PhotoImage(im)
            except Exception:      # noqa: BLE001 - senza immagine niente hover
                cache[nome] = None
            if len(cache) > 60:
                cache.pop(next(iter(cache)))
        return cache.get(nome)

    def tela_racconto(self):
        """La tela del racconto staccato, o None se sta nella colonna a destra della tavola."""
        f = getattr(self, "fin_racconto", None)
        try:
            return f.cv if f is not None and f.winfo_exists() else None
        except Exception:      # noqa: BLE001 - gia' chiusa
            return None

    def stacca_racconto(self):
        """Il racconto (WHAT HAPPENED) in una finestra sua, accanto al replayer: la tavola prende il posto della colonna (resta la colonna stretta della magia
        in pila). Chiusa, il racconto torna nella colonna."""
        tk = self.tk
        if self.tela_racconto() is not None:
            self.fin_racconto.lift()
            return self.fin_racconto
        fb = self.fin_board
        f = self.fin_racconto = tk.Toplevel(fb)
        f.title("The board · what happened")
        f.configure(bg=C["scheda"])
        try:
            from tema import barra_scura
            f.after(60, lambda f=f: f.winfo_exists() and barra_scura(f, C["testa"], C["titolo"], C["filo"]))      # a finestra comparsa, se no resta bianca
        except Exception:      # noqa: BLE001 - fuori da Windows la barra resta quella del sistema
            pass
        try:
            fb.update_idletasks()
            f.geometry(f"{LARGA_RACCONTO + 60}x{max(500, fb.winfo_height() - 120)}+{fb.winfo_rootx() + fb.winfo_width() - LARGA_RACCONTO - 80}+{fb.winfo_rooty() + 80}")
        except Exception:      # noqa: BLE001
            pass
        f.cv = tk.Canvas(f, bg="#11151c", highlightthickness=0, bd=0)
        f.cv.pack(fill="both", expand=True)
        f.cv.bind("<Configure>", lambda e: self.disegna_board())
        f.protocol("WM_DELETE_WINDOW", self.riattacca_racconto)
        f.bind("<Escape>", lambda e: self.riattacca_racconto())
        for tasto, fn in (("<Left>", lambda e: self.passo_board(-1)), ("<Right>", lambda e: self.passo_board(1))):
            f.bind(tasto, fn)
        self.disegna_board()
        return f

    def riattacca_racconto(self):
        f = getattr(self, "fin_racconto", None)
        self.fin_racconto = None
        if f is not None:
            try:
                f.destroy()
            except Exception:      # noqa: BLE001
                pass
        if getattr(self, "cv_board", None) is not None and self.cv_board.winfo_exists():
            self.disegna_board()

    def clic_pila(self, e):
        """Il clic sulla tavola: con un cimitero o un esilio aperto, la ✕ o il clic fuori dal riquadro lo chiudono; se no il clic su una pila la apre."""
        if getattr(self, "_pila_aperta", None):
            x0, y0, x1, y1 = getattr(self, "_box_riquadro", (0, 0, 0, 0))
            cx0, cy0, cx1, cy1 = getattr(self, "_box_chiudi", (0, 0, 0, 0))
            if not (x0 <= e.x <= x1 and y0 <= e.y <= y1) or (cx0 <= e.x <= cx1 and cy0 <= e.y <= cy1):
                self.chiudi_pila()
            return None
        bs_ = getattr(self, "_box_stacca", None)
        if bs_ and bs_[0] <= e.x <= bs_[2] and bs_[1] <= e.y <= bs_[3]:      # «⧉ Detach»: il racconto nella sua finestra
            return self.stacca_racconto()
        for x0, y0, x1, y1, tit, k, carte in getattr(self, "_box_pile", []):
            if x0 <= e.x <= x1 and y0 <= e.y <= y1:
                return self.apri_pila(tit, carte, k)
        return None

    def apri_pila(self, tit, carte, chiave=None):
        """Il cimitero o l'esilio aperto sopra la tavola, nella stessa finestra (12 nov 2026, Autore: «cimitero ed esilio ora si aprono ma non in
        sovrimpressione ma da un'altra parte e sta cosa non va bene»): un riquadro sopra la tavola velata, le carte dall'ultima arrivata, la carta grande in
        hover; segue il momento (cambiando momento mostra quella pila in quel momento); ✕, clic fuori o Esc lo chiudono."""
        self._pila_aperta = (tit, chiave, carte)
        self.disegna_board()
        return self._pila_aperta

    def chiudi_pila(self):
        if getattr(self, "_pila_aperta", None):
            self._pila_aperta = None
            self.disegna_board()

    def disegna_pila_aperta(self, c, f, W, H):
        ap = getattr(self, "_pila_aperta", None)
        if not ap:
            return
        F = self.F
        tit, chiave, carte = ap
        dove = {"cim_mio": ("cim", 0), "cim_suo": ("cim", 1), "esi_mio": ("esi", 0), "esi_suo": ("esi", 1)}.get(chiave)
        if dove:        # la pila di questo momento
            carte = (f.get(dove[0]) or ([], []))[dove[1]]
            self._pila_aperta = (tit, chiave, carte)
        chi = "YOUR" if (chiave or "").endswith("mio") else "OPPONENT'S"
        d = DG.Disegno(W, H)
        d.rett(0, 0, W, H, riempi=(8, 8, 12, 190))
        mx = 60
        rx0, ry0, rx1, ry1 = mx, 40, W - mx, H - 40
        d.rett(rx0, ry0, rx1, ry1, riempi="#11151c", bordo="#2c3340", larghezza=1.2, raggio=8)
        self._img_velo = d.foto(veloce=True)
        c.create_image(0, 0, image=self._img_velo, anchor="nw", tags="pila_aperta")
        self._box_riquadro = (rx0, ry0, rx1, ry1)
        self._box_carte = []        # sotto il velo le carte della tavola non si guardano: solo quelle della pila
        c.create_text(rx0 + 20, ry0 + 22, text=f"{chi} {tit} · {len(carte)} card{'s' if len(carte) != 1 else ''}", anchor="w", fill=C["titolo"], font=F(11, True))
        c.create_text(rx0 + 20, ry0 + 42, text=self._board["passi"][self._board["i"]][0] + "  ·  the last one in first  ·  click outside or Esc to close",
                      anchor="w", fill=C["grigio"], font=F(7))
        self._box_chiudi = (rx1 - 40, ry0 + 8, rx1 - 10, ry0 + 36)
        c.create_text(rx1 - 25, ry0 + 22, text="✕", fill=C["titolo"], font=F(12, True))
        if not carte:
            c.create_text((rx0 + rx1) / 2, (ry0 + ry1) / 2, text="empty", fill=C["muto"], font=F(10))
            return
        larga, alta = rx1 - rx0 - 40, ry1 - ry0 - 80
        w = 150
        while w > 60:       # la carta piu' grande con cui ci stanno tutte
            h = round(w * 279 / 200)
            per = max(1, int((larga + 10) // (w + 10)))
            if ((len(carte) + per - 1) // per) * (h + 10) <= alta:
                break
            w -= 6
        h = round(w * 279 / 200)
        per = max(1, int((larga + 10) // (w + 10)))
        for j, n in enumerate(carte):     # l'ultima arrivata per prima (Arena le scrive gia' cosi')
            x, y = rx0 + 20 + (j % per) * (w + 10), ry0 + 60 + (j // per) * (h + 10)
            if y + h > ry1:
                c.create_text(rx1 - 20, ry1 - 14, text=f"+{len(carte) - j} more", anchor="e", fill=C["grigio"], font=F(8, True))
                break
            img = self.immagine_carta(n, w, False)
            if img is not None:
                c.create_image(x, y, image=img, anchor="nw")
            else:
                c.create_rectangle(x, y, x + w, y + h, fill="#1d222b", outline="#4a4a52")
                c.create_text(x + w / 2, y + h / 2, text=n, width=w - 10, fill=C["titolo"], font=F(7, True), justify="center")
            self._box_carte.append((x, y, x + w, y + h, n))

    def punta(self, e):
        """Il puntatore su un grafico (Chart o Compare): la linea verticale e il valore di ogni linea in quel punto."""
        c = e.widget
        c.delete("punta")
        if not getattr(c, "_linee", None) or not getattr(c, "_scala", None):
            return
        x0, y0, x1, y1, xa, xb, _ya, _yb = c._scala
        if not x0 <= e.x <= x1:
            return
        xv = xa + (e.x - x0) / (x1 - x0) * (xb - xa)
        c.create_line(e.x, y0, e.x, y1, fill="#4a4a52", tags="punta")
        righe = []
        pc = "%" if c._metrica in ("wr", "mull") else " pts" if c._metrica == "ev" else ""
        for i, (n, p) in enumerate(c._linee):
            q = min(p, key=lambda t: abs(t[0] - xv))
            righe.append((f"{n}: " + (f"{q[1]:+.1f}" if c._metrica == "ev" else f"{q[1]:.1f}") + pc, c._colori[i % len(c._colori)]))
        etx = f"game {round(xv)}" if c._asse == "games" else datetime.date.fromordinal(int(round(xv))).strftime("%d %b %Y")
        bx = e.x + 12 if e.x < (x0 + x1) / 2 else e.x - 170
        c.create_rectangle(bx, y0 + 4, bx + 160, y0 + 22 + 15 * len(righe), fill="#0b0e14", outline="#2c3340", tags="punta")
        c.create_text(bx + 8, y0 + 12, text=etx, anchor="w", fill=C["titolo"], font=self.F(7, True), tags="punta")
        for j, (t, col) in enumerate(righe):
            c.create_text(bx + 8, y0 + 27 + 15 * j, text=t, anchor="w", fill=col, font=self.F(7), tags="punta")


    def cambia_spot(self, m):
        """Le ricerche preimpostate o gli spot automatici di prima (13 nov 2026)."""
        self.spot_modo = m
        self.sincronizza()
        self.disegna_vista("spots")

    def preset_attivo(self):
        """La ricerca preimpostata accesa: quella i cui filtri sono esattamente i filtri di adesso, o None."""
        on = {k: v for k, v in self.filtri.items() if v is not None}
        for p_ in PRESET:
            if p_[3] == on:
                return p_
        return None

    def usa_preset(self, p_):
        """Una ricerca preimpostata (13 nov 2026, Autore: «spots ... deve dare una combo di filtri preimpostati per risolvere le ricerche fondamentali tra le
        partite / ne schiaccio uno e tutti i filtri si combinano per quella ricerca»): i suoi filtri al posto di quelli di adesso, il raggruppamento del Report
        se lo vuole, e la vista che risponde. Premuta di nuovo, se e' ancora quella accesa, si toglie (tutte le partite)."""
        _g, _n, _s, filtri, vista, per = p_
        if self.preset_attivo() is p_:
            self.filtri = {}
            self.disegna()
            return None
        self.filtri = dict(filtri)
        if per:
            self.per = per
            self.basso = "report"
        self.sincronizza()
        self.disegna()
        if vista and vista != self.vista:
            self.cambia_vista(vista)
        return p_

    def disegna_preset(self, c):
        """Le ricerche preimpostate a gruppi, ognuna con le partite e il win rate che darebbe adesso (sui filtri di nessun'altra ricerca: ogni ricerca parte da
        tutte le partite del tipo). Quella accesa ha il bordo azzurro. Il clic la usa (usa_preset)."""
        F = self.F
        W = max(c.winfo_width(), 400)
        tutte = [x for x in self.righe or [] if x["tipo"] == self.tipo]
        accesa = self.preset_attivo()
        corto = lambda t, n: t if len(t) <= n else t[:max(1, n - 1)] + "…"
        gruppi = []
        for p_ in PRESET:
            if not gruppi or gruppi[-1][0] != p_[0]:
                gruppi.append((p_[0], []))
            gruppi[-1][1].append(p_)
        per_riga = 2 if W >= 1000 else 1
        larga = (W - 8 - 14 * (per_riga - 1)) / per_riga
        alto = 46
        y_col = [4] * per_riga
        for gi, (nome_g, lista) in enumerate(gruppi):
            col = y_col.index(min(y_col))
            x0, y = col * (larga + 14), y_col[col]
            c.create_text(x0 + 4, y + 9, text=nome_g, anchor="w", fill=C["titolo"], font=F(9, True))
            y += 24
            for p_ in lista:
                _g, nome, sotto, filtri, vista, per = p_
                r = DA.filtra(tutte, filtri)
                k = DA.conti(r)
                on = p_ is accesa
                c.create_rectangle(x0, y, x0 + larga, y + alto, fill="#22262c" if on else "#131820", outline=C["azzurro"] if on else "#252b36", width=2 if on else 1)
                c.create_text(x0 + 12, y + 15, text=corto(nome, int((larga - 150) / 6.6)), anchor="w", fill=C["azzurro"] if on else C["titolo"], font=F(8, True))
                c.create_text(x0 + 12, y + 32, text=corto(sotto, int((larga - 150) / 5.6)), anchor="w", fill=C["grigio"], font=F(7))
                wr = k.get("wr")
                pochi = len(r) < 15
                c.create_text(x0 + larga - 12, y + 15, text=f"{wr:.0f}%" if wr is not None else "-", anchor="e",
                              fill=C["muto"] if wr is None or pochi else (C["verde"] if wr >= 50 else C["rosso"]), font=F(11, True))
                c.create_text(x0 + larga - 12, y + 33, text=f"{len(r):,} games" + (" · a hint" if pochi and r else ""), anchor="e", fill=C["muto"], font=F(7))
                c._dom_box.append((x0, y, x0 + larga, y + alto, p_))
                y += alto + 6
            y_col[col] = y + 12
        c.create_text(4, max(y_col) + 6, text="One click turns on every filter of the search and opens the view that answers it; click it again to go back to all "
                                             "games  ·  the filters stay on the left: change them to narrow the search", anchor="w", fill=C["muto"], font=F(7))
        c.configure(scrollregion=(0, 0, W, max(y_col) + 24))

    def disegna_spot(self):
        """Dove vinci e dove perdi di piu': due elenchi (affiancati a tutta larghezza), quanti ne stanno nell'altezza (niente si taglia), gli spot che reggono in
        testa («strong»: regge anche contando quante condizioni si sono provate, DA.spot). Il clic mette le condizioni fra i filtri."""
        c = self.tela("spots")
        c.delete("all")
        c._spot_box, c._dom_box = [], []
        if self.righe is None:
            return
        if self.spot_modo == "preset":
            return self.disegna_preset(c)
        c.configure(scrollregion=(0, 0, max(c.winfo_width(), 300), max(c.winfo_height(), 200)))
        c.yview_moveto(0)
        F = self.F
        r = self.scelte()
        W, H = max(c.winfo_width(), 300), max(c.winfo_height(), 200)
        alto = 40
        affiancati = W >= 800        # a tutta larghezza: dove guadagni a sinistra, dove perdi a destra
        per_lista = max(1, int((H - 40 - 8) // (alto + 4))) if affiancati else max(1, int((H - 2 * 40 - 8) // 2 // (alto + 4)))
        minimo = 15 if len(r) >= 90 else max(6, len(r) // 6)
        # l'EV di ogni partita contro il solito (ev_partita.scarti, l'atteso da tutte le partite del tipo): la misura degli spot; solo le situazioni che si
        # sanno prima o all'inizio della partita (DA.SPOT_EV)
        import ev_partita as EV_
        sc = {p_: v_["scarto"] for p_, v_ in EV_.scarti([x for x in self.righe if x["tipo"] == self.tipo]).items()}
        meglio, peggio = DA.spot(r, minimo=minimo, quanti=per_lista, gia=self.filtri, ev=sc)
        ev_qui = [sc[x["partita"]] for x in r if x.get("partita") in sc]
        m_qui = sum(ev_qui) / len(ev_qui) if ev_qui else None
        corto = lambda t, n: t if len(t) <= n else t[:n - 1] + "…"
        c.create_text(4, 10, text=("Where your games gain and lose EV: the situations you know before or early in the game (your deck, the opponent, start, "
                                   "mulligan, hand, the first turns, the session), each with the win-probability points its games made a game above or below "
                                   "the usual. Click one: its filters."), anchor="nw", fill=C["grigio"], font=F(7), width=W - 8)
        y = 40
        larga = (W - 12) / 2 if affiancati else W
        for j_, (tit, lista, col) in enumerate((("WHERE YOU GAIN EV", meglio, C["verde"]), ("WHERE YOU LOSE EV", peggio, C["rosso"]))):
            x0 = j_ * (larga + 12) if affiancati else 0
            if affiancati:
                y = 40
            c.create_text(x0 + 4, y + 8, text=tit, anchor="w", fill=col, font=F(7, True))
            c.create_text(x0 + larga - 4, y + 8, text=f"these games {m_qui:+.1f} a game" if m_qui is not None else "", anchor="e", fill=C["muto"], font=F(7))
            y += 20
            if not lista:
                c.create_text(x0 + 4, y + 12, text=f"nothing yet: no situation with {minimo}+ games that stands out", anchor="w", fill=C["grigio"], font=F(7))
                y += 28
            for s_ in lista:
                c.create_rectangle(x0, y, x0 + larga - 1, y + alto, fill="#161b25", outline=col if s_["forte"] else "#252b36")
                c.create_text(x0 + 10, y + 12, text=corto(s_["nome"], int((larga - 110) / 6.4)), anchor="w", fill=C["titolo"], font=F(8, True))
                c.create_text(x0 + 10, y + 28, text=f"{s_['n']} games · {s_['vinte']}-{s_['perse']} · {s_['wr']:.0f}% WR"
                              + ("  ·  strong" if s_["forte"] else "  ·  a hint"), anchor="w", fill=C["grigio"] if s_["forte"] else C["muto"], font=F(7))
                c.create_text(x0 + larga - 12, y + 13, text=f"{s_['ev']:+.1f}", anchor="e", fill=col if s_["forte"] else C["muto"], font=F(11, True))
                c.create_text(x0 + larga - 12, y + 29, text="EV a game", anchor="e", fill=C["muto"], font=F(7))
                c._spot_box.append((x0, y, x0 + larga, y + alto, s_))
                y += alto + 4
            y += 6

    def clic_spot(self, e):
        """Uno spot: le sue condizioni fra i filtri. Fra le ricerche preimpostate, la ricerca (usa_preset)."""
        c = getattr(e, "widget", None) or self.tela("spots")
        if self.spot_modo == "preset":
            yy = c.canvasy(e.y)
            for x0, y0, x1, y1, p_ in getattr(c, "_dom_box", []):
                if x0 <= e.x <= x1 and y0 <= yy <= y1:
                    return self.usa_preset(p_) or "tolta"
            return None
        for x0, y0, x1, y1, s in getattr(c, "_spot_box", []):
            if x0 <= e.x <= x1 and y0 <= e.y <= y1:
                for k, v in s["condizioni"]:
                    self.filtri[k] = v
                self.disegna()
                return

    # ------------------------------------------------------------ Breakdown
    def bd_partite(self):
        """Le partite di Breakdown: quelle degli Smart filters."""
        return self.scelte()

    def disegna_matchup(self):
        """I Matchups di prima: sono Breakdown."""
        return self.disegna_report()

    def disegna_sottocartelle(self, c, voci, scelta):
        """Le sotto-cartelle di una cartella (18 nov 2026: Matchups e Gem events), col disegno delle cartelle in alto: quella scelta con la riga azzurra in cima,
        aperta sul contenuto sotto; le altre solo testo."""
        c.delete("all")
        F = self.F
        W, H = max(c.winfo_width(), 400), ALTO_SUB
        d = DG.Disegno(W, H)
        c._box, att, testi = [], None, []
        x = 0
        for k, n in voci:
            x0, x1 = x, x + LARGA_SUB
            top = 3 if k == scelta else 8
            if k == scelta:
                att = (x0, x1)
            testi.append(((x0 + x1) / 2, (top + H) / 2 - 1, n, k == scelta))
            c._box.append((x0, 0, x1, H, k))
            x = x1 + 3
        if att:
            x0, x1 = att
            d.linea([(0, H - 0.5), (x0 + 0.5, H - 0.5)], C["filo"], 1.0)
            d.linea([(x1 - 0.5, H - 0.5), (W, H - 0.5)], C["filo"], 1.0)
            pts = _cartella(x0, x1, 3, H + 1, sl=0, r=4)
            d.poligono(pts, riempi="#131720")
            d.linea(pts, C["filo"], 1.0)
            d.linea([(x0 + 3, 3.8), (x1 - 3, 3.8)], C["accento"], 2.0)
        c._img = d.foto()
        c.create_image(0, 0, image=c._img, anchor="nw")
        for tx, ty, t, on in testi:
            c.create_text(tx, ty, text=t, fill=C["titolo"] if on else C["grigio"], font=F(9, on))

    def clic_sottocartella(self, c, e):
        k = next((b[4] for b in getattr(c, "_box", []) if b[0] <= e.x <= b[2] and b[1] <= e.y <= b[3]), None)
        if k is not None:
            self.cambia_mu_modo(k)
        return k

    def cambia_mu_modo(self, m):
        self.mu_modo = m
        self.sincronizza()
        if "report" in self.visibili():
            self.disegna_report()

    def disegna_vuoto_mazzo(self, c, W):
        """Matchups senza un mazzo (18 nov 2026, Autore: «la prima cosa che deve apparire e' quel messaggio al centro della scheda che quindi sara' vuota»):
        al centro il messaggio e il pulsante che apre Choose your deck."""
        F = self.F
        H = max(c.winfo_height(), 360)
        cy = H / 2 - 40
        c.create_text(W / 2, cy, text="Choose a deck to see its matchups", fill=C["titolo"], font=F(14, True))
        c.create_text(W / 2, cy + 30, text=("Pick one of your decks in Choose your deck, on the left. Format, event and rank narrow it down;\nyou can also pick "
                                            "the opponent's deck there."), fill=C["grigio"], font=F(9), justify="center")
        disegna_s3(c, W / 2 - 90, cy + 58, W / 2 + 90, cy + 86, "Choose your deck", F(9, True))
        c._bd_box.append((W / 2 - 90, cy + 58, W / 2 + 90, cy + 86, ("scegli",)))
        c.configure(scrollregion=(0, 0, W, H))

    def corse_eventi(self, r):
        """Le iscrizioni agli eventi pagati del mazzo (18 nov 2026, Autore: «in events ogni evento pagato e' una riga con il suo risultato e data e nome
        evento e se lo espando dentro ho i game»): dai log (premi_eventi) ogni iscrizione (EventPayEntry, il CourseId) col suo ingresso e il suo premio
        (EventReward dello stesso CourseId); le partite del mazzo in quell'evento divise in corse in ordine di tempo (una corsa Bo1 finisce a 7 vittorie, il
        trofeo, o a 3 sconfitte) e abbinate alle iscrizioni nello stesso ordine (le partite nel log non dicono il CourseId: grado C).
        -> [dict(evento, data, partite, vinte, perse, trofeo, ingresso_gemme, ingresso_oro, gemme, oro, buste)], dalla piu' recente."""
        mio = self.filtri.get("mio")
        try:
            import premi_eventi as PE
            voci = PE.raccogli()
        except Exception:      # noqa: BLE001 - senza i premi niente eventi pagati
            voci = []
        iscr, premi = collections.defaultdict(list), {}
        for v in voci:
            if v["fonte"] not in ("EventPayEntry", "EventReward") or (mio and v.get("mazzo") and v.get("mazzo").strip() != mio.strip()):
                continue
            if v["fonte"] == "EventPayEntry":
                if v["id"] not in [z["id"] for z in iscr[v["evento"]]]:
                    iscr[v["evento"]].append(dict(id=v["id"], ingresso_gemme=-min(v["gemme"], 0), ingresso_oro=-min(v["oro"], 0)))
            else:
                premi[v["id"]] = dict(gemme=max(v["gemme"], 0), oro=max(v["oro"], 0), buste=sum(n for _s, n in v["buste"]))
        out = []
        for ev, cc in iscr.items():
            pp = sorted((x for x in r if x.get("evento") == ev), key=lambda x: x["quando"])
            corse, cur, v_, p_ = [], [], 0, 0
            for x in pp:
                cur.append(x)
                v_ += 1 if x["vinta"] else 0
                p_ += 0 if x["vinta"] else 1
                if v_ >= VITTORIE_CORSA or p_ >= SCONFITTE_CORSA:
                    corse.append(cur)
                    cur, v_, p_ = [], 0, 0
            if cur:
                corse.append(cur)
            for j, z in enumerate(cc):
                gg = corse[j] if j < len(corse) else []
                vv = sum(1 for x in gg if x["vinta"])
                pr = premi.get(z["id"], dict(gemme=0, oro=0, buste=0))
                out.append(dict(evento=ev, id=z["id"], data=gg[0]["quando"] if gg else None, partite=gg, vinte=vv, perse=len(gg) - vv,
                                trofeo=vv >= VITTORIE_CORSA, ingresso_gemme=z["ingresso_gemme"], ingresso_oro=z["ingresso_oro"], **pr))
        out.sort(key=lambda z: (z["data"] is None, -(z["data"].timestamp() if z["data"] else 0)))
        return out

    def disegna_gemme(self, c, r, W, y):
        """Gem events (18 nov 2026, Autore: «sopra i dati di che quel mazzo ha ottenuto dagli eventi: wr / conversione oro in gemme / ecc»; «ogni evento
        pagato e' una riga con il suo risultato e data e nome evento e se lo espando dentro ho i game»): in testa i numeri del mazzo negli eventi pagati, sotto
        una riga per iscrizione, aperta mostra le sue partite (il clic: il replay)."""
        F = self.F
        ev = self.corse_eventi(r)
        if not ev:
            c.create_text(14, y + 14, text="This deck hasn't played a paid event in your logs yet (the logs start on 22 Sep 2026).", anchor="w",
                          fill=C["grigio"], font=F(9))
            c.configure(scrollregion=(0, 0, W, y + 40))
            return
        n = sum(len(z["partite"]) for z in ev)
        vinte = sum(z["vinte"] for z in ev)
        oro_s, gem_s = sum(z["ingresso_oro"] for z in ev), sum(z["ingresso_gemme"] for z in ev)
        gem_v = sum(z["gemme"] for z in ev)
        conv = f"{round(1000 * gem_v / oro_s)} gems" if oro_s else "-"
        netto = gem_v - gem_s
        tessere = [("PAID EVENTS", str(len(ev)), f"{sum(1 for z in ev if z['trofeo'])} trophies (7 wins)", C["titolo"]),
                   ("WON · LOST", f"{vinte}-{n - vinte}", f"{n} games", C["titolo"]),
                   ("WIN RATE", f"{round(100 * vinte / n)}%" if n else "-", "in paid events", C["muto"] if not n else C["verde"] if vinte / n >= 0.5 else C["rosso"]),
                   ("SPENT", " + ".join(t_ for t_ in ((f"{oro_s:,} gold" if oro_s else ""), (f"{gem_s:,} gems" if gem_s else "")) if t_) or "-", "entries",
                    C["titolo"]),
                   ("GEMS WON", f"{gem_v:,}", f"net {netto:+,} gems", C["verde"] if gem_v else C["muto"]),
                   ("GOLD → GEMS", conv, "won for every 1,000 gold spent", C["arancio"] if oro_s else C["muto"]),
                   ("PACKS", str(sum(z["buste"] for z in ev)), "from the prizes", C["titolo"])]
        tw = (W - 28) / len(tessere)
        for i, (t_, v_, sotto, col) in enumerate(tessere):
            x0 = 14 + i * tw
            c.create_rectangle(x0, y, x0 + tw - 8, y + 66, fill="#161b25", outline="#252b36")
            c.create_rectangle(x0 + 4, y + 6, x0 + 6, y + 18, fill=C["accento"], outline="")
            c.create_text(x0 + 10, y + 12, text=t_, anchor="w", fill=C["titolo"], font=F(8, True))
            c.create_text(x0 + 10, y + 36, text=v_, anchor="w", fill=col, font=F(15, True))
            c.create_text(x0 + 10, y + 56, text=sotto, anchor="w", fill=C["muto"], font=F(7), width=tw - 20)
        y += 82
        c.create_text(14, y + 8, text="EVERY PAID EVENT · click one: its games · click a game: its replay", anchor="w", fill=C["azzurro"], font=F(8, True))
        y += 24
        cols = (("DATE", 14), ("EVENT", 150), ("RESULT", 430), ("ENTRY", 540), ("GEMS WON", 680), ("PACKS", 790))
        for t_, xc in cols:
            c.create_text(xc, y + 6, text=t_, anchor="w", fill=C["titolo"], font=F(7, True))
        y += 20
        for i, z in enumerate(ev):
            aperto = z["id"] in self.gem_aperti
            c.create_rectangle(8, y - 2, W - 8, y + 26, fill="#1f3446" if aperto else ("#161b25" if i % 2 == 0 else "#131820"),
                               outline=C["azzurro"] if aperto else "")
            ingresso = " + ".join(t_ for t_ in ((f"{z['ingresso_gemme']:,} gems" if z["ingresso_gemme"] else ""),
                                                (f"{z['ingresso_oro']:,} gold" if z["ingresso_oro"] else "")) if t_) or "-"
            ris = f"{z['vinte']}-{z['perse']}" + ("  · trophy" if z["trofeo"] else "")
            for t_, xc, col in (((("▾ " if aperto else "▸ ") + (f"{z['data']:%d %b %H:%M}" if z["data"] else "no games")), 14, C["titolo"]),
                                (nome_evento(z["evento"])[:38], 150, C["titolo"]),
                                (ris, 430, C["arancio"] if z["trofeo"] else (C["verde"] if z["vinte"] >= z["perse"] else C["rosso"])),
                                (ingresso, 540, C["testo"]), (f"{z['gemme']:,}", 680, C["verde"] if z["gemme"] else C["muto"]),
                                (str(z["buste"]), 790, C["testo"])):
                c.create_text(xc, y + 12, text=t_, anchor="w", fill=col, font=F(9, True))
            c._bd_box.append((8, y - 2, W - 8, y + 26, ("evento_gemme", z["id"])))
            y += 30
            if aperto:
                for x in z["partite"]:
                    c.create_rectangle(32, y - 2, W - 8, y + 20, fill="#131820", outline="")
                    for t_, xc, col in ((f"{x['quando']:%d %b %H:%M}", 44, C["testo"]), ((x.get("suo") or "Unknown")[:30], 170, C["titolo"]),
                                        ("on the play" if x.get("inizia") else "on the draw", 420, C["testo"]),
                                        (f"T{x.get('turno')}" if x.get("turno") else "-", 540, C["testo"]),
                                        ("Won" if x["vinta"] else "Lost", 620, C["verde"] if x["vinta"] else C["rosso"]),
                                        ("▶ replay", 720, C["accento"])):
                        c.create_text(xc, y + 9, text=t_, anchor="w", fill=col, font=F(8, True))
                    c._bd_box.append((32, y - 2, W - 8, y + 20, ("partita", x)))
                    y += 22
                if not z["partite"]:
                    c.create_text(44, y + 8, text="no games of this entry in your logs", anchor="w", fill=C["muto"], font=F(8))
                    y += 22
                y += 6
        c.create_text(14, y + 10, text=("Entry and prizes are read from your Arena logs; the games are matched to each entry in time order (Bo1: an entry ends at 7 "
                                        "wins or 3 losses). Gold → gems: the gems the prizes gave back for every 1,000 gold of entries."), anchor="nw",
                      fill=C["muto"], font=F(7), width=W - 28)
        c.configure(scrollregion=(0, 0, W, y + 40))

    def disegna_report(self):
        """Breakdown (18 nov 2026, il terzo giro, Autore: «questa pagina si completa dalla selezione del deck in smart filters e parte gia' dai dati del deck
        selezionato altrimenti da tutti i deck / il confronto va verso all a meno che in smart filters deck non abbiamo stabilito un colore avversario / e poi
        la selezione di formato ed eventi», «immagina sempre che un player parta sapendo tutto e voglia andare in spot ... le informazioni non devono essere
        ridondanti»): nessuna scelta sua. La domanda in testa la dicono gli Smart filters (il mazzo e il colore avversario di By deck, formato, evento, rango);
        sotto la risposta (quante volte, vinte e perse, win rate, EV a partita, on the play e on the draw, l'ultima volta) e una riga per ogni mazzo
        avversario incontrato (con un colore avversario in By deck, solo quelli di quel colore). Il clic su un avversario lo mette fra i filtri e mostra le
        partite contro di lui, una per riga (il clic apre il replay); il doppio clic le apre tutte nel replayer."""
        c = self.tela("report")
        c.delete("all")
        c._bd_box, c._n = [], 0
        if self.righe is None:
            return
        F = self.F
        import ev_partita as EV_
        tutte_t = [x for x in self.righe if x["tipo"] == self.tipo]
        sc = {p_: v_["scarto"] for p_, v_ in EV_.scarti(tutte_t).items()}
        formati = {}
        for x in tutte_t:
            formati.setdefault(x.get("evento"), x.get("formato"))
        r = self.bd_partite()
        W = max(c.winfo_width(), 800)
        if not self.filtri.get("mio"):      # senza un mazzo: solo il messaggio al centro (anche dopo Reset)
            return self.disegna_vuoto_mazzo(c, W)

        def numeri(xs):
            n = len(xs)
            v = sum(1 for x in xs if x["vinta"])
            ev = [sc[x["partita"]] for x in xs if x.get("partita") in sc]
            pl = [x for x in xs if x.get("inizia") is True]
            dr = [x for x in xs if x.get("inizia") is False]
            wr_ = lambda ys: round(100 * sum(1 for y in ys if y["vinta"]) / len(ys)) if ys else None
            return dict(n=n, v=v, p=n - v, wr=wr_(xs), ev=round(sum(ev) / len(ev), 1) if ev else None, play=wr_(pl), n_play=len(pl), draw=wr_(dr),
                        n_draw=len(dr), ultima=max((x["quando"] for x in xs), default=None), ic=DA.conti(xs).get("ic") if xs else None,
                        turni=round(sum(x.get("turno") or 0 for x in xs) / n, 1) if n else None)
        # la domanda, dagli Smart filters
        f_ = self.filtri
        contro = (f_.get("suo") or (f"{DA.nome_vs(f_['vs'])} decks" if f_.get("vs") else None) or "every deck you met")
        dove = " · ".join(t_ for t_ in ((f_.get("formato") or "").capitalize(), nome_evento(f_["evento"], formati.get(f_["evento"])) if f_.get("evento") else "",
                                        f_.get("rango") or "") if t_) or "everywhere"
        dom = f"{f_.get('mio') or 'All your decks'}  vs  {contro}  ·  {dove}"
        c.create_text(14, 16, text=dom, anchor="w", fill=C["titolo"], font=F(12, True), width=W - 28)
        if self.mu_modo == "gemme":
            return self.disegna_gemme(c, r, W, 36)
        k_ = numeri(r)
        tessere = [("GAMES", f"{k_['n']}", "", C["titolo"]),
                   ("WON · LOST", f"{k_['v']}-{k_['p']}", "", C["titolo"]),
                   ("WIN RATE", f"{k_['wr']}%" if k_["wr"] is not None else "-", f"95% CI {k_['ic'][0]}–{k_['ic'][1]}%" if k_.get("ic") else "",
                    C["muto"] if k_["wr"] is None or k_["n"] < 5 else C["verde"] if k_["wr"] >= 50 else C["rosso"]),
                   ("EV A GAME", f"{k_['ev']:+.1f}" if k_["ev"] is not None else "-", "win-probability points vs the usual",
                    C["muto"] if k_["ev"] is None or k_["n"] < 5 else C["verde"] if k_["ev"] > 0 else C["rosso"]),
                   ("ON THE PLAY", f"{k_['play']}%" if k_["play"] is not None else "-", f"win rate in {k_['n_play']} games", C["testo"]),
                   ("ON THE DRAW", f"{k_['draw']}%" if k_["draw"] is not None else "-", f"win rate in {k_['n_draw']} games", C["testo"]),
                   ("LAST", f"{k_['ultima']:%d %b}" if k_["ultima"] else "-", f"avg {k_['turni']} turns" if k_["turni"] else "", C["testo"])]
        tw = (W - 28) / len(tessere)
        for i, (t_, v_, sotto, col) in enumerate(tessere):
            x0 = 14 + i * tw
            c.create_rectangle(x0, 36, x0 + tw - 8, 102, fill="#161b25", outline="#252b36")
            c.create_rectangle(x0 + 4, 42, x0 + 6, 54, fill=C["accento"], outline="")
            c.create_text(x0 + 10, 48, text=t_, anchor="w", fill=C["titolo"], font=F(8, True))
            c.create_text(x0 + 10, 72, text=v_, anchor="w", fill=col, font=F(16, True))
            c.create_text(x0 + 10, 92, text=sotto, anchor="w", fill=C["muto"], font=F(7), width=tw - 20)
        y = 116
        if k_["n"] and k_["n"] < 5:
            c.create_text(14, y, text="under 5 games: a hint, not a fact", anchor="w", fill=C["arancio"], font=F(7, True))
            y += 16
        # (la striscia degli scenari per evento c'e' stata un'ora, il 18 nov 2026: Autore, «questo riquadro non serve»; gli scenari sono il filtro Event)
        if not r:
            c.create_text(14, y + 14, text="No games: change the Smart filters on the left.", anchor="w", fill=C["grigio"], font=F(9))
            c.configure(scrollregion=(0, 0, W, y + 40))
            return
        if True:       # una riga per ogni mazzo avversario incontrato (con un avversario scelto restano tutti, il suo acceso)
            c.create_rectangle(14, y + 3, 16, y + 17, fill=C["accento"], outline="")
            c.create_text(22, y + 10, text="AGAINST EACH DECK YOU MET", anchor="w", fill=C["titolo"], font=F(9, True))
            c.create_text(W - 14, y + 10, text="click a deck: the totals against it (again: all) · double-click: its games in the replayer · grey under 5 games",
                          anchor="e", fill=C["muto"], font=F(7))
            y += 26
            gruppi = collections.defaultdict(list)
            for x in (DA.filtra(self.righe or [], {k2: v2 for k2, v2 in f_.items() if k2 != "suo"}, self.tipo) if f_.get("suo") else r):
                gruppi[x.get("suo") or "Unknown"].append(x)
            righe_ = []
            for v, xs in gruppi.items():
                var_ = collections.Counter(DA.vs_di(x_) for x_ in xs if DA.vs_di(x_))
                righe_.append(dict(valore=v, nome=v, colori=var_.most_common(1)[0][0] if var_ else "", **numeri(xs)))
            ordk = self.bd_ord
            righe_.sort(key=lambda z: str(z["nome"]).lower() if ordk == "nome" else (len(z["colori"]) or 9, z["colori"], str(z["nome"]).lower()) if ordk == "col" else (z["n"] < 5, -(z.get(ordk if ordk != "wl" else "v") or -1e9)
                                                                                       if ordk != "ultima" else -(z["ultima"].timestamp() if z["ultima"] else 0)))
            x = 14
            c.create_rectangle(8, y - 3, W - 8, y + 19, fill=TESTA_TAB, outline="")
            c.create_line(8, y + 19, W - 8, y + 19, fill=C["accento"], width=2)
            for kc, tc, wc in BD_COLONNE:
                c.create_text(x, y + 8, text=tc or "OPPONENT'S DECK", anchor="w", fill=C["accento"] if kc == ordk else C["titolo"], font=F(8, True))
                c._bd_box.append((x, y, x + wc, y + 16, ("ord", kc)))
                x += wc
            y += 26
            nmax = max(z["n"] for z in righe_)
            for i, z in enumerate(righe_):
                poche = z["n"] < 5
                scelto_ = f_.get("suo") == z["valore"]
                if i % 2 == 0 or scelto_:
                    c.create_rectangle(8, y - 2, W - 8, y + 22, fill="#1f3446" if scelto_ else "#161b25", outline=C["azzurro"] if scelto_ else "")
                x = 14
                for kc, _tc, wc in BD_COLONNE:
                    if kc == "col":
                        for j, ch in enumerate(z["colori"]):
                            img = self.lista().simbolo(ch, 14)
                            if img is not None:
                                c.create_image(x + 7 + j * 16, y + 10, image=img)
                        if not z["colori"]:
                            c.create_text(x, y + 10, text="?", anchor="w", fill=C["muto"], font=F(8, True))
                    elif kc == "nome":
                        c.create_text(x, y + 10, text=z["nome"][:40], anchor="w", fill=C["muto"] if poche else C["titolo"], font=F(8, True))
                    elif kc == "n":
                        c.create_rectangle(x, y + 6, x + 90, y + 14, fill="#252b36", outline="")
                        c.create_rectangle(x, y + 6, x + 90 * z["n"] / nmax, y + 14, fill=C["muto"] if poche else C["accento"], outline="")
                        c.create_text(x + 98, y + 10, text=str(z["n"]), anchor="w", fill=C["testo"], font=F(8, True))
                    elif kc == "wr":
                        col = C["muto"] if poche or z["wr"] is None else (C["verde"] if z["wr"] >= 50 else C["rosso"])
                        c.create_rectangle(x, y + 5, x + 120, y + 15, fill="#252b36", outline="")
                        c.create_rectangle(x, y + 5, x + 1.2 * (z["wr"] or 0), y + 15, fill=col, outline="")
                        c.create_line(x + 60, y + 2, x + 60, y + 18, fill="#d8d8dc")
                        c.create_text(x + 128, y + 10, text=f"{z['wr']}%", anchor="w", fill=col, font=F(8, True))
                    else:
                        v_ = {"wl": f"{z['v']}-{z['p']}", "ev": f"{z['ev']:+.1f}" if z["ev"] is not None else "-",
                              "play": f"{z['play']}% · {z['n_play']}" if z["play"] is not None else "-",
                              "draw": f"{z['draw']}% · {z['n_draw']}" if z["draw"] is not None else "-",
                              "ultima": f"{z['ultima']:%d %b}" if z["ultima"] else "-"}[kc]
                        col = C["muto"] if poche else ((C["verde"] if z["ev"] > 0 else C["rosso"]) if kc == "ev" and z["ev"] else C["testo"])
                        c.create_text(x, y + 10, text=v_, anchor="w", fill=col, font=F(8, kc == "ev"))
                    x += wc
                c._bd_box.append((8, y - 2, W - 8, y + 22, ("riga", "suo", z["valore"])))
                y += 24
            c._n = len(righe_)
        c.configure(scrollregion=(0, 0, W, y + 24))

    def maschera_rp(self, c=None):
        """(Breakdown non copre piu' l'ultima riga: la tabella scorre intera, con la barra.)"""
        return None

    def partite_numero(self, da):
        """R14: il doppio clic su un avversario di Breakdown (il primo clic l'ha messo fra i filtri) apre le sue partite nel replayer, una dopo l'altra (la
        playlist), dalla piu' recente."""
        r = sorted(self.scelte(), key=lambda x: x["quando"], reverse=True)
        if not r:
            return None
        return self.apri_playlist(r, "Matchup")

    def clic_report(self, e):
        """Breakdown: un avversario va fra i filtri (si scende alle sue partite), un titolo ordina, una partita apre il replay."""
        c = getattr(e, "widget", None) or self.tela("report")
        x, y = c.canvasx(e.x), c.canvasy(e.y)
        b = next((b_ for b_ in getattr(c, "_bd_box", []) if b_[0] <= x <= b_[2] and b_[1] <= y <= b_[3]), None)
        if b is None:
            return None
        cosa = b[4]
        if cosa[0] == "riga":       # l'avversario fra i filtri; di nuovo, tolto
            self.filtri[cosa[1]] = None if self.filtri.get(cosa[1]) == cosa[2] else cosa[2]
            self.disegna()
        elif cosa[0] == "ord":
            self.bd_ord = cosa[1]
            self.disegna_report()
        elif cosa[0] == "partita":
            self.apri_board(cosa[1])
        elif cosa[0] == "scegli":       # Matchups vuoto: apre Choose your deck
            self.apri_deck()
        elif cosa[0] == "evento_gemme":     # Gem events: l'evento si apre o si chiude
            self.gem_aperti ^= {cosa[1]}
            self.disegna_report()
        return cosa

    def b_confronto(self):
        """B: il resto delle partite (rest), tutte (all) o una situazione salvata (s<i>). -> (partite, nome, descrizione)."""
        tutte = [x for x in self.righe if x["tipo"] == self.tipo]
        if self.con.startswith("s") and self.con[1:].isdigit():
            sal = DA.situazioni()
            i = int(self.con[1:])
            if i < len(sal):
                s_ = sal[i]
                t = s_.get("tipo") or self.tipo
                return DA.filtra(self.righe, s_.get("filtri") or {}, t), s_.get("nome") or f"Situation {i + 1}", self.descrivi(s_.get("filtri") or {}, t)
            self.con = "rest"
        if self.con == "all":
            return tutte, f"All {self.tipo.lower()} games", f"all your {self.tipo.lower()} games, A included"
        dentro = {id(x) for x in self.scelte()}
        return [x for x in tutte if id(x) not in dentro], "Everything else", f"your {self.tipo.lower()} games outside A"

    def disegna_confronto(self):
        """A (la situazione dei filtri) contro B: le due schede, la tabella delle misure con la differenza e se regge (test z, p sotto 5%), la frase, e sotto il
        win rate dei due nel tempo."""
        c = self.tela("compare")
        c.delete("all")
        c._img, c._linee, c._scala = None, [], None
        if self.righe is None:
            return
        F = self.F
        sal = DA.situazioni()
        voci = ["rest", "all"] + (["17l"] if self.tipo == "Limited" else []) + [f"s{i}" for i in range(len(sal))]
        if self.con not in voci:
            self.con = "rest"
        et = {"rest": "Everything else", "all": f"All {self.tipo.lower()} games", "17l": "17Lands players (same sets and colors)",
              **{f"s{i}": (s_.get("nome") or f"Situation {i + 1}") for i, s_ in enumerate(sal)}}
        for o in self.copie("compare"):
            o["ctl"]["con"].opzioni(voci, lambda v: self.cambia("con", v), etichette=et)
            o["ctl"]["con"].set(self.con)
        W, H = max(c.winfo_width(), 600), max(c.winfo_height(), 240)
        n_f = sum(1 for v in self.filtri.values() if v is not None)
        if not n_f and self.con in ("rest", "all"):     # (contro 17Lands si confronta anche senza filtri: A sono tutte le tue partite di limited)
            c.create_text(16, 30, text="A is the situation you build with the smart filters (and the + of each phase).", anchor="w", fill=C["titolo"], font=F(9, True))
            c.create_text(16, 52, text="Set some, then compare it here with everything else, with all your games or with a saved situation.", anchor="w",
                          fill=C["grigio"], font=F(8))
            return
        a = self.scelte()
        if self.con == "17l":       # C12: contro chi usa 17Lands (dati pubblici, CC BY 4.0), stessi set e stessi colori
            res = DA.confronta_17lands(a)
            b, nome_b = [], "17Lands players"
            descr_b = (f"Premier Draft of {', '.join(res['set']) or '-'}, weighted on your colors · 17Lands public game data (CC BY 4.0), 17lands.com"
                       + (f" · {res['fuori']} of your games have no 17Lands data" if res["fuori"] else ""))
        else:
            b, nome_b, descr_b = self.b_confronto()
            res = DA.confronta(a, b)
        corto = lambda t, n: t if len(t) <= n else t[:n - 1] + "…"
        meta = (W - 16 - 12) / 2
        for i, (lett, tit, descr, k_, col) in enumerate((("A", "THIS SITUATION", self.descrivi(self.filtri), res["a"], C["azzurro"]),
                                                         ("B", nome_b.upper(), descr_b, res["b"], C["arancio"]))):
            x0 = 8 + i * (meta + 12)
            c.create_rectangle(x0, 4, x0 + meta, 52, fill="#161b25", outline="#252b36")
            c.create_rectangle(x0, 4, x0 + 3, 52, fill=col, outline="")
            c.create_text(x0 + 14, 17, text=corto(f"{lett} · {tit}", int((meta - 150) / 6.6)), anchor="w", fill=col, font=F(8, True))
            c.create_text(x0 + meta - 10, 17, text=f"{k_['n']:,} games · {k_['vinte']:,}-{k_['perse']:,}", anchor="e", fill=C["titolo"], font=F(8, True))
            c.create_text(x0 + 14, 37, text=corto(descr, int((meta - 24) / 5.6)), anchor="w", fill=C["grigio"], font=F(7))
        # la tabella: misura, A, B, A meno B, se regge
        cx = (16, 250, 420, 580, 700)
        y = 64
        for x_, t in zip(cx, ("MEASURE", "A", "B", "A − B", "DOES IT HOLD?")):
            c.create_text(x_, y + 8, text=t, anchor="w", fill=C["azzurro"] if t == "A" else C["arancio"] if t == "B" else C["titolo"], font=F(7, True))
        y += 20
        pf = lambda p: "p < 0.001" if p < 0.001 else f"p {p:.3f}" if p < 0.1 else f"p {p:.2f}"
        for i, r in enumerate(res["righe"]):
            if i % 2 == 0:
                c.create_rectangle(0, y, W, y + 24, fill="#161b25", outline="")
            c.create_text(cx[0], y + 12, text=r["nome"], anchor="w", fill=C["titolo"], font=F(8, True))
            for x_, v, n, ic, col in ((cx[1], r["a"], r["na"], r["ic_a"], C["azzurro"]), (cx[2], r["b"], r["nb"], r["ic_b"], C["arancio"])):
                if v is None:
                    t = "-"
                elif r["unita"] == "%":
                    t = f"{v:.0f}%" + (f"  ({ic[0]}–{ic[1]})" if r["k"] == "wr" and ic else "") + f"  · {n:,} g"
                else:
                    t = f"T{v}  · {n:,} g"
                c.create_text(x_, y + 12, text=t, anchor="w", fill=col if v is not None else C["muto"], font=F(8))
            d = r["delta"]
            buono = r["k"] in ("wr", "play", "draw")
            if d is None:
                td, cd = "-", C["muto"]
            else:
                td = f"{d:+.1f} pts" if r["unita"] == "%" else f"{d:+.1f} turns"
                cd = (C["verde"] if d > 0 else C["rosso"] if d < 0 else C["testo"]) if buono else C["testo"]
            c.create_text(cx[3], y + 12, text=td, anchor="w", fill=cd, font=F(8, True))
            if r["p"] is None:
                tv, cv, fv = "too few games (5 a side)", C["muto"], F(7)
            elif r["p"] < 0.05:
                tv, cv, fv = f"holds · {pf(r['p'])}", C["accento"], F(8, True)
            else:
                tv, cv, fv = f"could be chance · {pf(r['p'])}" + (f" · ~{r['servono']:,} games a side to tell" if r["servono"] and r["servono"] <= 3000
                                                                   else " · no real difference" if r["unita"] == "%" else ""), C["grigio"], F(7)
            c.create_text(cx[4], y + 12, text=tv, anchor="w", fill=cv, font=fv)
            y += 24
        # la frase sul win rate
        w = res["righe"][0]
        if w["p"] is None:
            fr, cf = "Too few games on one side to compare the win rate: 5 at least on each.", C["grigio"]
        else:
            piu = f"{abs(w['delta']):.1f} points {'more' if w['delta'] > 0 else 'less'}" if w["delta"] else "the same"
            if w["p"] < 0.05:
                fr, cf = f"In A you win {piu} than in B, and it holds: {pf(w['p'])}, under 5% it is not chance.", C["accento"]
            else:
                fr, cf = (f"In A you win {piu} than in B, but it could still be chance ({pf(w['p'])})"
                          + (f": about {w['servono']:,} games on each side would tell." if w["servono"] and w["servono"] <= 3000
                             else ": so small that it is no real difference." if w["servono"] else "."), C["titolo"])
        c.create_text(16, y + 16, text=fr, anchor="w", fill=cf, font=F(9, True), width=W - 32)
        y += 40
        if self.con == "17l":       # la citazione (CC BY 4.0) sempre intera e a vista, non dentro la scheda di B che si accorcia
            c.create_text(16, y, text=("B: 17Lands public game data (CC BY 4.0), 17lands.com/public_datasets · Premier Draft players, who win about 55% on "
                                       "average; your games may be Quick Draft. 17Lands does not endorse this app."), anchor="w", fill=C["grigio"], font=F(7),
                          width=W - 32)
            y += 24
        if H - y >= 130 and b:        # sotto, il win rate di A e di B nel tempo (contro 17Lands B non ha partite: niente)
            lin = [(n, p) for n, p in (("A", DA.serie(a, "wr", self.asse, self.finestra)), ("B", DA.serie(b, "wr", self.asse, self.finestra))) if p]
            fin = "cumulative" if self.finestra == "cum" else f"last {self.finestra} games"
            self.traccia(c, lin, (52, y + 18, W - 120, H - 24), "wr", self.asse, (C["azzurro"], C["arancio"]), f"win rate of A and B, {fin}")

    # ------------------------------------------------------------ i filtri in piu' di ogni fase (12 nov 2026: le situazioni di Add filters stanno qui)
    def disegna_testata(self, j):
        """La testa di una fase: la lineetta (non sulla prima), il nome e a destra il «+ more», azzurro con quanti ne sono accesi."""
        c = self.testate[j]
        c.delete("all")
        F = self.F
        W = max(c.winfo_width(), 262)
        H = int(c.cget("height"))
        if j:
            c.create_line(0, 5, W, 5, fill=C["filo"])
        nome, chiavi = FASI[j]
        on = sum(1 for k in chiavi if self.filtri.get(k) is not None)
        c.create_rectangle(0, H - 16, 2, H - 4, fill=C["accento"], outline="")
        c.create_text(7, H - 10, text=nome, anchor="w", fill=C["accento"] if on else C["titolo"], font=F(8, True))
        if not chiavi:      # una fase senza filtri in piu': niente + more
            return
        t = f"+ {on} on" if on else "+ more"
        chip(c, W - 62, H - 19, W - 2, H - 1, t, bool(on), F(7, True))

    # ------------------------------------------------------------ Advanced filters (13 nov 2026, Autore: «io voglio una sezione dove posso ottenere una
    # risposta in base a dei filtri ... mio wr quando ho 3 terre in mano on the draw e chiudo entro T5 senza creature e oppo mulliga», poi «tutta sta roba sta in
    # una nuova sotto finestra / il pulsante per aprirla e' advanced filters», «filtri e domanda ma i filtri per me e per oppo stanno in due schede differenti»)
    @staticmethod
    def sezioni_av(scheda):
        """Tutte le sezioni di una scheda di Advanced filters, quelle del Board (ogni sottovoce) comprese."""
        out = [z for _f, sezioni in AVANZATI[scheda] for z in sezioni]
        out += [z for _g, sezioni in BOARD_AV.get(scheda, ()) for z in sezioni]
        return out

    def sezioni_aperte(self):
        """Le sezioni a video: quelle della fase aperta, o della sottovoce aperta del Board."""
        nome, sezioni = AVANZATI[self.scheda_av][self.fase_av[self.scheda_av]]
        if nome == "Board":
            return BOARD_AV[self.scheda_av][self.area_av[self.scheda_av]][1]
        return sezioni

    def chiavi_scheda_av(self, scheda):
        """I filtri di una scheda di Advanced filters (Hero Player o Opponent), le righe delle giocate per turno e il Board compresi."""
        return {k2 for _t, kk in self.sezioni_av(scheda) for k in kk for k2 in self.chiavi_av(k)}

    @staticmethod
    def chiavi_av(k):
        """Le chiavi dei filtri di una voce di AVANZATI: «@t_io» le righe turno per turno (t_io1 ... t_io5), «&ab_io» le abilita' (ab_io), le altre se stesse."""
        if k.startswith("@"):
            carta = [f"{PaginaPerformance.chiave_carta(k[1:])}{n}" for n in DA.CAMPI_TURNO] if PaginaPerformance.chiave_carta(k[1:]) else []
            return [f"{k[1:]}{n}" for n in DA.CAMPI_TURNO] + carta
        return [k[1:]] if k[:1] in ("&", "%", "?") else [k]

    def reset_scheda_av(self):
        """Il Reset della scheda aperta di Advanced filters: i suoi filtri via, gli altri (le altre schede, gli smart filters) restano."""
        for k in self.chiavi_scheda_av(self.scheda_av):
            self.filtri.pop(k, None)
        for _t, kk in self.sezioni_av(self.scheda_av):
            for k in kk:
                if k[:1] in ("@", "&", "?"):
                    self.__dict__.setdefault("_righe_ui", {}).pop(k[1:], None)
        self.disegna()

    def avanzati_on(self):
        """Quanti filtri della finestra Advanced filters sono accesi."""
        chiavi = {k2 for sch in AVANZATI for _t, kk in self.sezioni_av(sch) for k in kk for k2 in self.chiavi_av(k)}
        return sum(1 for k, v in self.filtri.items() if v is not None and k in chiavi)

    def aggiorna_bottone_avanzati(self):
        b = getattr(self, "b_avanzati", None)
        if b is not None and b.winfo_exists():
            n = self.avanzati_on()
            b.metti("Advanced filters" + (f"  ·  {n} on" if n else ""), bool(n))

    def apri_avanzati(self, scheda=None, fase=None, area=None):
        """La finestra: in cima la domanda (ogni filtro acceso, anche quelli della pagina, con la sua x) e la risposta; sotto due schede, You e Opponent, coi
        filtri avanzati di ognuno. Tutto si applica subito: la pagina (grafico, report, partite) segue la stessa domanda. Una finestra sola."""
        tk, F = self.tk, self.F
        if scheda:
            self.scheda_av = scheda
        if fase is not None:
            self.fase_av[self.scheda_av] = fase
        if area is not None:
            self.area_av[self.scheda_av] = area
        f = getattr(self, "fin_av", None)
        if f is None or not f.winfo_exists():
            f = self.fin_av = tk.Toplevel(self.fr); f.configure(bg=C["scheda"])
            self._fasi_di = None
            f.transient(self.fr.winfo_toplevel())
            f.title("Advanced filters")
            f.geometry(f"+{self.cv_sx.winfo_rootx() + self.cv_sx.winfo_width() + 16}+{max(0, self.cv_sx.winfo_rooty() - 40)}")
            f.bind("<Escape>", lambda e: f.destroy())
            tk.Label(f, text="ADVANCED FILTERS", bg=C["scheda"], fg=C["titolo"], font=F(10, True)).pack(anchor="w", padx=14, pady=(12, 2))
            tk.Label(f, text="Build your question: every filter adds a piece, the answer is right below and the whole Leak Finder page follows it "
                     "(chart, report, matchups, the games and their replays).", bg=C["scheda"], fg=C["grigio"], font=F(7), wraplength=LARGA_FASE - 20,
                     justify="left").pack(anchor="w", padx=14, pady=(0, 6))
            self.cv_dom = tk.Canvas(f, bg="#17171b", highlightthickness=1, highlightbackground=C["filo"], bd=0, width=LARGA_FASE, height=90)
            self.cv_dom.pack(padx=8, pady=(0, 8))
            self.cv_dom.bind("<Button-1>", self.clic_domanda)
            schede = tk.Frame(f, bg=C["scheda"]); schede.pack(fill="x", padx=8, pady=(2, 4))
            self.b_schede_av = {}
            for k, n in SCHEDE_AV:
                b = pulsante_solido(tk, F, schede, n, k == self.scheda_av, lambda k=k: self.apri_avanzati(k), alto=28, bg=C["scheda"], colori=GRIGI, icona=False)
                b.configure(width=150); b.pack(side="left", padx=(0, 6))
                self.b_schede_av[k] = b
            # il Reset della scheda aperta (13 nov 2026, Autore: «per ogni scheda in cui inseriamo valori crea un pulsante reset localizzato, mentre il main
            # reset le resetta tutte contemporaneamente»)
            self.b_reset_av = pulsante_solido(tk, F, schede, "Reset", False, self.reset_scheda_av, alto=28, bg=C["scheda"], colori=ARANCIO)
            self.b_reset_av.configure(width=150); self.b_reset_av.pack(side="right")
            self.fr_fasi_av = tk.Frame(f, bg=C["scheda"]); self.fr_fasi_av.pack(fill="x", padx=8, pady=(2, 4))
            # le sottovoci della fase Board (16 nov 2026): cartelle disegnate sotto le fasi, solo con Board aperta (Autore, stesso giorno: «i suoi sotto menù
            # non farli come pulsanti ma come cartelle o si generano troppi pulsanti su troppe file»)
            self.fr_aree_av = tk.Frame(f, bg=C["scheda"]); self.fr_aree_av.pack(fill="x", padx=8, pady=(0, 0))
            self.cv_aree_av = tk.Canvas(self.fr_aree_av, bg=C["scheda"], highlightthickness=0, bd=0, width=LARGA_FASE, height=ALTO_AREE, cursor="hand2")
            self.cv_aree_av.bind("<Button-1>", self.clic_aree_av)
            self.cv_aree_av.bind("<Motion>", self.sopra_aree_av)
            self.cv_aree_av.bind("<Leave>", lambda e: self.sopra_aree_av(None))
            self.b_aree_av = []
            # i filtri scorrono (13 nov 2026, Autore: «caso mai mettiamo uno scroller per scendere alle voci in fondo»): la rotella su tutta la finestra e una
            # barra sottile a destra, da cliccare o trascinare
            corpo = tk.Frame(f, bg=C["scheda"]); corpo.pack(padx=8, pady=(4, 12))
            # piu' larga della testa (18 nov 2026, Autore: «sposta la barra di scroll di advanced filters piu' a destra»): le righe con la carta e la
            # fase arrivano a ~900 pixel e la ✕ finiva sotto la barra
            self.cv_av = tk.Canvas(corpo, bg=C["scheda"], highlightthickness=0, bd=0, width=LARGA_RIGHE_AV, height=200)
            self.cv_av.pack(side="left")
            self.cv_av.bind("<Button-1>", self.clic_avanzati)
            self.cv_barra_av = tk.Canvas(corpo, bg=C["scheda"], highlightthickness=0, bd=0, width=10, height=200, cursor="hand2")
            self.cv_barra_av.pack(side="left", fill="y", padx=(4, 0))
            self.cv_av.configure(yscrollcommand=self.barra_av)
            self.cv_barra_av.bind("<Button-1>", self.trascina_av)
            self.cv_barra_av.bind("<B1-Motion>", self.trascina_av)
            f.bind("<MouseWheel>", lambda e: (self.cv_av.yview_scroll(-2 if e.delta > 0 else 2, "units"), "break")[1])
        for k, b in self.b_schede_av.items():
            b.metti(dict(SCHEDE_AV)[k], k == self.scheda_av)
        self.b_reset_av.metti("Reset · " + dict(SCHEDE_AV)[self.scheda_av], False)
        # le fasi della scheda: rifatte quando cambia la scheda (You e Opponent ne hanno di diverse) o il formato (la fase Draft solo nel Limited, SOLO_FASE)
        vive = [j for j, (nome, _sez) in enumerate(AVANZATI[self.scheda_av]) if SOLO_FASE.get(nome, self.tipo) == self.tipo]
        if self.fase_av[self.scheda_av] not in vive:        # la fase aperta non c'e' in questo formato: la prima
            self.fase_av[self.scheda_av] = vive[0]
        if getattr(self, "_fasi_di", None) != (self.scheda_av, self.tipo):
            for w in self.fr_fasi_av.winfo_children():
                w.destroy()
            self.b_fasi_av, self._j_fasi_av = [], []
            for j in vive:
                b = pulsante_solido(tk, F, self.fr_fasi_av, AVANZATI[self.scheda_av][j][0], False, lambda j=j: self.apri_avanzati(fase=j), alto=24,
                                    bg=C["scheda"], colori=("#202024", "#2c2c32", "#1f3446"), icona=False)
                b.configure(width=124); b.pack(side="left", padx=(0, 4))
                self.b_fasi_av.append(b)
                self._j_fasi_av.append(j)
            self._fasi_di = (self.scheda_av, self.tipo)
        for j, b in zip(self._j_fasi_av, self.b_fasi_av):
            b.metti(AVANZATI[self.scheda_av][j][0], j == self.fase_av[self.scheda_av])
        # le sottovoci del Board: le cartelle, solo con la fase Board aperta
        if AVANZATI[self.scheda_av][self.fase_av[self.scheda_av]][0] == "Board":
            self.cv_aree_av.pack(anchor="w")
            self.disegna_aree_av()
        else:
            self.cv_aree_av.pack_forget()
            self.b_aree_av = []
        self.disegna_avanzati()
        if scheda or fase is not None or area is not None:          # un'altra scheda, fase o sottovoce riparte dall'alto
            self.cv_av.yview_moveto(0)
        f.lift()
        return f

    def disegna_aree_av(self):
        """Le sottovoci del Board come cartelle (come le viste della pagina): larghe quanto il nome, quella aperta si fonde con l'area dei filtri sotto, le
        altre solo testo, sotto il puntatore un velo appena chiaro. self.b_aree_av = [(x0, x1, j)]."""
        c, F = self.cv_aree_av, self.F
        c.delete("all")
        W, H = LARGA_FASE, ALTO_AREE
        d = DG.Disegno(W, H)
        from tkinter import font as tkfont
        fnt = tkfont.Font(font=F(9, True))
        sopra = getattr(self, "_aree_sopra", None)
        aperta = self.area_av[self.scheda_av]
        self.b_aree_av, testi, att, x = [], [], None, 0
        for j, (nome_g, _sez) in enumerate(BOARD_AV[self.scheda_av]):
            x0, x1 = x, x + fnt.measure(nome_g) + 28
            top = 2 if j == aperta else 6
            if j == aperta:
                att = (x0, x1)
            elif sopra == j:
                d.poligono(_cartella(x0, x1, top, H + 1, sl=0, r=4), riempi="#121722")
            testi.append(((x0 + x1) / 2, (top + H) / 2 - 1, nome_g, j == aperta))
            self.b_aree_av.append((x0, x1, j))
            x = x1 + 2
        if att:
            x0, x1 = att
            d.linea([(0, H - 0.5), (x0 + 0.5, H - 0.5)], C["filo"], 1.0)
            d.linea([(x1 - 0.5, H - 0.5), (W, H - 0.5)], C["filo"], 1.0)
            pts = _cartella(x0, x1, 2, H + 1, sl=0, r=4)
            d.poligono(pts, riempi=C["scheda"])
            d.linea(pts, C["filo"], 1.0)
            d.linea([(x0 + 3, 2.8), (x1 - 3, 2.8)], C["accento"], 2.0)
        self._img_aree_av = d.foto()
        c.create_image(0, 0, image=self._img_aree_av, anchor="nw")
        for tx, ty, t, on in testi:
            c.create_text(tx, ty, text=t, fill=C["titolo"] if on else C["grigio"], font=F(9, on))

    def _area_a(self, x):
        return next((j for x0, x1, j in getattr(self, "b_aree_av", []) if x0 <= x <= x1), None)

    def clic_aree_av(self, e):
        j = self._area_a(e.x)
        if j is not None and j != self.area_av[self.scheda_av]:
            self.apri_avanzati(area=j)
        return j

    def sopra_aree_av(self, e):
        j = None if e is None else self._area_a(e.x)
        if j != getattr(self, "_aree_sopra", None):
            self._aree_sopra = j
            self.disegna_aree_av()

    def disegna_avanzati(self):
        """La domanda con la risposta e i filtri della scheda aperta. Mai dentro se stessa (16 nov 2026): le righe misurano la loro altezza con
        update_idletasks, che fa partire un disegno in attesa (una carta scelta nella casella) e distruggeva le righe a meta'; quel disegno si rifa' dopo."""
        if getattr(self, "_in_avanzati", False):
            self.fr.after(15, self.disegna_avanzati)      # un timer: update_idletasks non lo fa partire (after_idle girerebbe all'infinito)
            return
        self._in_avanzati = True
        try:
            self._disegna_avanzati()
        finally:
            self._in_avanzati = False

    def _disegna_avanzati(self):
        c = getattr(self, "cv_dom", None)
        if c is None or not c.winfo_exists() or self.righe is None:
            return
        F = self.F
        from tkinter import font as tkfont
        misura = tkfont.Font(font=F(7, True))
        # la domanda: ogni filtro acceso e' un pezzo con la sua x
        c.delete("all")
        c._pezzi = []
        r = self.scelte()
        k_ = DA.conti(r)
        tot = DA.conti(self.base_confronto())        # con un mazzo scelto, le partite di quel mazzo (18 nov 2026)
        c.create_text(12, 16, text=f"YOUR QUESTION · {self.tipo.lower()} games when", anchor="w", fill=C["azzurro"], font=F(7, True))
        # la domanda detta di fila (18 nov 2026): sopra i pezzi, una frase sola
        i_fr = c.create_text(12, 30, text=DA.frase({k_: v_ for k_, v_ in self.filtri.items() if v_ is not None}, self.tipo), anchor="nw",
                             fill=C["titolo"], font=F(9, True), width=LARGA_FASE - 24, tags="frase")
        x, y = 12, (c.bbox(i_fr) or (0, 0, 0, 40))[3] + 18
        accesi = [(kf, v) for kf, v in self.filtri.items() if v is not None]
        if not accesi:
            c.create_text(x, y, text="no filter yet: all your games", anchor="w", fill=C["muto"], font=F(7))
        for kf, v in accesi:
            testo = DA.etichetta(kf, v) if kf.startswith("sit:") else f"{DA.nome_var(kf)}: {DA.etichetta(kf, v)}"
            largo = misura.measure(testo) + 34
            if x + largo > LARGA_FASE - 12 and x > 12:
                x, y = 12, y + 24
            c.create_rectangle(x, y - 10, x + largo, y + 10, fill="#1f3446", outline=C["azzurro"])
            c.create_text(x + 8, y, text=testo, anchor="w", fill=C["titolo"], font=F(7, True))
            c.create_text(x + largo - 10, y, text="x", fill=C["azzurro"], font=F(8, True))
            c._pezzi.append((x + largo - 20, y - 10, x + largo, y + 10, kf))
            x += largo + 6
        # la risposta
        y += 30
        wr = k_["wr"]
        col = C["muto"] if wr is None else (C["verde"] if wr >= 50 else C["rosso"])
        c.create_text(12, y + 4, text=f"{wr:.0f}%" if wr is not None else "-", anchor="w", fill=col, font=F(18, True))
        info = (f"{k_['n']} games · {k_['vinte']}-{k_['perse']}" + (f" · 95% CI {k_['ic'][0]}–{k_['ic'][1]}%" if k_.get("ic") else "")
                + (f" · vs {self.nome_base()} ({tot['n']}) {tot['wr']:.0f}%" if tot["wr"] is not None and any(kf != "mio" for kf, _v in accesi) else ""))
        c.create_text(100, y - 2, text=info, anchor="w", fill=C["grigio"], font=F(8))
        if 0 < k_["n"] < 30:
            c.create_text(100, y + 14, text="under 30 games: a hint, not a fact", anchor="w", fill=C["arancio"], font=F(7, True))
        elif not k_["n"]:
            c.create_text(100, y + 14, text="no games answer this question: remove a piece", anchor="w", fill=C["arancio"], font=F(7, True))
        # quante volte (14 nov 2026, «quante volte ci è capitato di essere in quella situazione»): per i filtri che si contano a episodi, i turni o le finestre
        # in cui e' successo, in quante partite, su quante occasioni
        for e_ in DA.episodi(r, self.filtri):
            y += 18
            occ = f" out of {e_['occasioni']:,} turns" if e_["occasioni"] else ""
            c.create_text(12, y + 14, text=f"HOW MANY TIMES · {e_['volte']:,} times in {e_['partite']:,} games{occ}  ·  {e_['nome']}", anchor="w",
                          fill=C["azzurro"], font=F(7, True))
        # dallo spot alla conseguenza (18 nov 2026, «quante volte la creatura sopravvive al T3 di oppo ... quale removal»): le tue creature dello spot fino
        # alla fine del turno dopo dell'Opponent, le rimozioni carta per carta, l'EV di quei turni contro il solito (ev_partita.esito_spot)
        try:
            import ev_partita as EV_
            es_ = EV_.esito_spot(r, self.filtri, [x_ for x_ in self.righe if x_["tipo"] == self.tipo]) if accesi else None
        except Exception:      # noqa: BLE001 - senza i dati dei replay la riga non c'e'
            es_ = None
        if es_:
            n_c = es_["creature"] or 1
            pc_ = lambda k: f"{100 * es_['esiti'].get(k, 0) / n_c:.0f}%"
            y += 18
            c.create_text(12, y + 14, text=(f"WHAT HAPPENED NEXT · your {es_['creature']} creature{'s' * (es_['creature'] != 1)} from the spot, through the Opponent's "
                                            f"next turn ({es_['partite']} games): survived {pc_('survived')} · removed {pc_('removed')} · died in combat "
                                            f"{pc_('died in combat')} · left otherwise {pc_('left otherwise')}"),
                          anchor="w", fill=C["titolo"], font=F(7, True))
            if es_["rimozioni"]:
                y += 18
                c.create_text(12, y + 14, text="REMOVED BY · " + " · ".join(f"{n_} {q_}" for n_, q_ in es_["rimozioni"].most_common(6)),
                              anchor="w", fill=C["rosso"], font=F(7, True))
            if es_["ev"] is not None:
                y += 18
                col_e = C["verde"] if es_["ev"] >= 1 else C["rosso"] if es_["ev"] <= -1 else C["testo"]
                c.create_text(12, y + 14, text=(f"EV OF THE SPOT · those turns gave {es_['ev']:+.1f} win-probability points against the usual"
                                                + (" · under 30 games, a hint" if es_["ev_n"] < 30 else "")), anchor="w", fill=col_e, font=F(7, True))
        c.configure(height=y + 26)
        # i filtri della scheda: per ognuno Any o un valore, a sezioni; le giocate turno per turno a righe (R_F.Righe)
        ca = self.cv_av
        for w in getattr(self, "_costruttori_av", {}).values():
            try:
                w.fr.destroy()
            except Exception:      # noqa: BLE001
                pass
        self._costruttori_av = {}
        ca.delete("all")
        self._box_av = []
        tutte = [x_ for x_ in self.righe if x_["tipo"] == self.tipo]
        y = 4
        for titolo, chiavi in self.sezioni_aperte():
            ca.create_text(8, y + 10, text=titolo, anchor="w", fill=C["azzurro"], font=F(7, True))
            y += 24
            if len(chiavi) == 1 and chiavi[0].startswith("@"):
                y = self.righe_avanzate(ca, chiavi[0][1:], y, tutte)
                continue
            if len(chiavi) == 1 and chiavi[0].startswith("&"):
                y = self.righe_abilita(ca, chiavi[0][1:], y, tutte)
                continue
            if len(chiavi) == 1 and chiavi[0].startswith("?"):
                y = self.righe_mano(ca, chiavi[0][1:], y, tutte)
                continue
            altri = {DA.SOLO_TIPO[k] for k in chiavi if DA.SOLO_TIPO.get(k, self.tipo) != self.tipo}
            if altri and all(DA.SOLO_TIPO.get(k, self.tipo) != self.tipo for k in chiavi):      # la sezione e' tutta dell'altro formato (il draft)
                ca.create_text(8, y + 12, text=f"{' and '.join(sorted(altri))} only: switch to {' / '.join(sorted(altri))} at the top of the page",
                               anchor="w", fill=C["arancio"], font=F(8, True))
                y += 34
                continue
            for k in chiavi:
                if k.startswith("%"):       # una carta di tutta la partita (16 nov 2026): la casella che completa
                    y = self.casella_carta_av(ca, k[1:], y, tutte)
                    continue
                if DA.SOLO_TIPO.get(k, self.tipo) != self.tipo:      # la voce di un altro formato (il mulligan)
                    continue
                sc = self.filtri.get(k)
                # sempre tutte le voci, anche quelle che nelle tue partite non ci sono (13 nov 2026: «mancano anche i planeswalker»)
                vv = ([v for v, _n in DA.valori(tutte, k)] if k == "miei_colori" else      # i colori: solo le varianti dei tuoi mazzi
                      list(DA.ORDINE_VALORI.get(k) or [v for v, _n in DA.valori(tutte, k)]))
                if DA.multipla(k):      # le giocate del turno: i tipi sempre, poi tipo e costo come ci sono nelle tue partite
                    combo = {v for x_ in tutte for v in DA.valori_di(k, x_) if " · " in v}
                    vv = sorted(set(vv) | combo, key=DA.ordine_lancio)
                ca.create_text(8, y + 13, text=DA.nome_var(k), anchor="w", fill=C["titolo"] if sc else C["testo"], font=F(8, bool(sc)), width=290)
                x = 310
                for v in [None] + vv:
                    t = "Any" if v is None else DA.etichetta(k, v) if k == "miei_colori" else v
                    w = max(50, misura.measure(t) + 22)
                    if x + w > LARGA_FASE - 6:
                        x, y = 310, y + 30
                    on = (v in sc if v is not None else not sc) if isinstance(sc, list) else sc == v
                    chip(ca, x, y + 2, x + w, y + 24, t, on, F(7, True))
                    self._box_av.append((x, y + 2, x + w, y + 24, k, v))
                    x += w + 6
                y += 34
            y += 6
        alto = max(240, min(y + 4, self.fr.winfo_screenheight() - 420))      # la finestra resta dentro lo schermo: il resto scorre
        ca.configure(height=alto, scrollregion=(0, 0, LARGA_FASE, y + 4), yscrollincrement=12)
        self.cv_barra_av.configure(height=alto)

    # le giocate turno per turno a righe (13 nov 2026, Autore: «in advanced filters sulle azioni per turno c'è troppa roba a vista, ricostruiamo la UX:
    # Your T1 Cast appare di default: tendina di default per scegliere cosa castiamo e accanto un + per aggiungere un'altra tendina / sotto mettiamo un add
    # line: tendina Turno e tendina di cast con + ... possiamo aggiungere infinite righe ... così anche in opponent turns»). Una riga: il turno, e una tendina
    # per ogni cosa lanciata (il tipo; lo stesso tipo due volte = due magie di quel tipo); piu' tendine nella stessa riga = tutte in quel turno (la scelta multipla di prima). I filtri sono gli
    # stessi («t_io3» = [voci]); le righe ancora senza voci restano solo a video.
    NOMI_RIGHE = {"t_io": ("Your T{}", "cast"), "t_iox": ("Opponent's T{}", "you cast"), "t_lui": ("Their T{}", "cast"), "t_luix": ("Your T{}", "they cast"),
                  # le sezioni turno per turno di attacco, difesa e pescate (14 nov 2026, la pagella dell'enciclopedia: dal turno 6 in poi e «in qualunque
                  # turno»): lo stesso costruttore, una voce per riga
                  "t_pio": ("Your T{}", "drew"), "t_piox": ("Opponent's T{}", "you drew"), "t_plui": ("Their T{}", "drew"), "t_pluix": ("Your T{}", "they drew"),
                  "t_aio": ("Your T{}", "attack"), "t_alui": ("Their T{}", "attack"), "t_mio": ("Your T{}", "their lands"), "t_mlui": ("Their T{}", "your lands"),
                  "t_dio": ("Opponent's T{}", "you"), "t_dlui": ("Your T{}", "they"), "t_qio": ("Your T{}", "you"), "t_qlui": ("Their T{}", "they"),
                  "t_uio": ("Your T{}", "you"), "t_ului": ("Their T{}", "they"),
                  # i ruoli (16 nov 2026)
                  "t_rio": ("Your T{}", "cast"), "t_riox": ("Opponent's T{}", "you cast"), "t_rlui": ("Their T{}", "cast"), "t_rluix": ("Your T{}", "they cast"),
                  # il Board (16 nov 2026): all'inizio di quel turno
                  **{f"t_b{a_}{s_}": (t_, d_) for a_, _n, _v in DA.BOARD_AREE
                     for s_, t_, d_ in (("io", "Your T{}", "you have"), ("luix", "Your T{}", "they have"), ("lui", "Their T{}", "they have"),
                                        ("iox", "Their T{}", "you have"))},
                  **{f"t_b{a_}{s_}": (t_, "ahead") for a_ in DA.BOARD_AVANTI for s_, t_ in (("vio", "Your T{}"), ("viox", "Their T{}"))}}
    VOCI_RIGHE = {"pio": DA.ORDINE_PESCATE, "plui": DA.ORDINE_PESCATE, "piox": DA.ORDINE_PESCATE_X, "pluix": DA.ORDINE_PESCATE_X, "aio": DA.ORDINE_ATT,
                  "alui": DA.ORDINE_ATT, "mio": DA.ORDINE_APERTE, "mlui": DA.ORDINE_APERTE, "dio": DA.ORDINE_DIF, "dlui": DA.ORDINE_DIF,
                  "qio": DA.ORDINE_SCELTA, "qlui": DA.ORDINE_SCELTA, "uio": DA.ORDINE_MANA, "ului": DA.ORDINE_MANA,
                  **{f"b{a_}{s_}": v_ for a_, _n, v_ in DA.BOARD_AREE for s_ in ("io", "luix", "lui", "iox")},
                  **{f"b{a_}{s_}": DA.ORDINE_AVANTI for a_ in DA.BOARD_AVANTI for s_ in ("vio", "viox")}}
    VOCI_MULTI = {k_: DA.ORDINE_RUOLI for k_ in ("rio", "riox", "rlui", "rluix")}      # le famiglie a piu' voci che non sono i tipi
    CAST = ("t_io", "t_iox", "t_lui", "t_luix", "t_rio", "t_riox", "t_rlui", "t_rluix")      # le righe «cast»: la tendina della carta

    @staticmethod
    def chiave_carta(pre):
        """La famiglia del nome della carta di una riga (16 nov 2026, Autore: «per ogni filtro che parla di carte in advanced filter dobbiamo sempre poter
        scrivere alla fine una carta specifica se la conosciamo»): le giocate per tipo e per ruolo («t_io» -> «t_nio», «t_rio» -> «t_nrio»), le pescate dell'Hero
        («t_pio» -> «t_npio»; quelle dell'Opponent Arena non le dice), chi attacca e chi blocca («t_naio», «t_ndio»), le aree del Board con le carte
        («t_bcio» -> «t_nbcio»; la mano dell'Opponent no). None per le righe senza carte (mana, terre stappate, forza, vita, chi e' avanti)."""
        if pre in PaginaPerformance.CAST:
            return "t_n" + pre[2:]
        m_ = re.fullmatch(r"t_([a-z]*?)(io|lui)(x?)", pre)
        if not m_:
            return None
        base, chi, _x = m_.groups()
        if base in ("a", "d") or (base == "p" and chi == "io"):
            return "t_n" + pre[2:]
        if base[:1] == "b" and base[1:] in DA.AREE_CON_CARTE and not (base == "bm" and chi == "lui"):
            return "t_n" + pre[2:]
        return None

    @staticmethod
    def campo_riga(nome, n):
        """Il campo del turno di una riga: «Hero T3», «Hero T11+», «Hero turns · any» (A: in qualunque turno, basta uno; 16 nov 2026: Hero e Opponent)."""
        nome = PaginaPerformance.nome_riga(nome)
        if n == "A":
            return nome.split(" T{}")[0] + " turns · any"
        return nome.format(f"{DA.TURNI_FILTRO + 1}+" if n == "L" else n)

    @staticmethod
    def nome_riga(t):
        """«Your T{}» -> «Hero T{}», «Their T{}» e «Opponent's T{}» -> «Opponent T{}»; «you cast» -> «Hero cast», «they have» -> «Opponent has»."""
        t = t.replace("Your T{}", "Hero T{}").replace("Their T{}", "Opponent T{}").replace("Opponent's T{}", "Opponent T{}")
        t = re.sub(r"\b(you|they) (have)\b", lambda m: ("Hero" if m.group(1) == "you" else "Opponent") + " has", t)
        return hero_txt(t).replace("Opponent's lands", "Opponent's lands")

    FASE_RIGHE = ("t_io", "t_iox", "t_lui", "t_luix")       # le righe dei tipi lanciati: la tendina della fase (18 nov 2026)

    @staticmethod
    def chiavi_fase(pre, fase):
        """Le chiavi di una riga con la fase: (tipi, carta). Senza fase quelle di sempre («t_io3», «t_nio3»), con la fase «t_kcio3», «t_kcnio3»."""
        if not fase:
            return pre, PaginaPerformance.chiave_carta(pre)
        return f"t_k{fase}{pre[2:]}", f"t_k{fase}n{pre[2:]}"

    def _da_righe(self, pre, righe):
        """I filtri di un gruppo dalle sue righe: {«t_io3»: [voci]} (le righe dello stesso turno e della stessa fase si uniscono)."""
        nuovi = {}
        for r_ in righe:
            campo, voci = r_[0], r_[1]
            fase = r_[3] if len(r_) > 3 and pre in self.FASE_RIGHE else None
            kt, kc = self.chiavi_fase(pre, fase)
            vv = [v for v in voci or [] if v]
            if campo and vv:        # le voci ripetute contano (due Instant = due istantanei); le righe dello stesso turno si sommano
                k = f"{kt}{campo}"
                nuovi[k] = sorted(nuovi.get(k, []) + vv, key=DA.ordine_lancio)
            if campo and kc and len(r_) > 2 and r_[2]:      # la carta scelta (16 nov 2026): una lista, come i tipi
                nuovi[f"{kc}{campo}"] = nuovi.get(f"{kc}{campo}", []) + [r_[2]]
        return nuovi

    def righe_av(self, pre):
        """Le righe del costruttore di un gruppo: quelle a video (con le tendine ancora vuote) se dicono ancora i filtri accesi, se no rifatte dai filtri (Clear
        all, la x di un pezzo della domanda, un tuo filtro salvato); di partenza il turno 1 vuoto."""
        con_fase = pre in self.FASE_RIGHE
        kc = self.chiave_carta(pre)
        ora, righe = {}, []
        for fase in ([None] + [c_ for c_, _n in DA.FASI_LANCIO] if con_fase else [None]):
            kt, kcf = self.chiavi_fase(pre, fase)
            tipi, carte = {}, {}
            for n in DA.CAMPI_TURNO:
                v = self.filtri.get(f"{kt}{n}")
                if v:
                    tipi[n] = ora[f"{kt}{n}"] = sorted(v if isinstance(v, list) else [v], key=DA.ordine_lancio)
                if kcf:
                    v = self.filtri.get(f"{kcf}{n}")
                    if v:
                        carte[n] = ora[f"{kcf}{n}"] = list(v) if isinstance(v, list) else [v]
            for n in sorted(set(tipi) | set(carte), key=DA.CAMPI_TURNO.index):
                for j, c_ in enumerate(carte.get(n) or [None]):
                    righe.append([n, list(tipi.get(n, [None])) if j == 0 else [None]] + ([c_] if kc else []) + ([fase] if con_fase else []))
        ui = self.__dict__.setdefault("_righe_ui", {}).get(pre)
        if ui and self._da_righe(pre, ui) == ora:
            return [[r_[0], list(r_[1])] + list(r_[2:4]) for r_ in ui]
        return righe or [["1", [None]] + ([None] if kc else []) + ([None] if con_fase else [])]

    def righe_avanzate(self, ca, pre, y, tutte):
        """Il costruttore delle righe di un gruppo dentro la tela di Advanced filters, a y. -> la y sotto."""
        tk, F = self.tk, self.F
        nome, dopo = self.NOMI_RIGHE[pre]
        dopo = self.nome_riga(dopo)
        una = self.VOCI_RIGHE.get(pre[2:])      # le famiglie con una voce sola per turno: le loro voci, e niente +
        voci = lambda n, o_=self.VOCI_MULTI.get(pre[2:], DA.ORDINE_TIPI): list(o_)      # i tipi soli: le ripetizioni dicono quante (13 nov 2026); i ruoli
        if una:
            voci = lambda n, una=una: list(una)
        kc = self.chiave_carta(pre)
        carte = None
        if kc:      # le carte lanciate in questa famiglia nelle partite del tipo, dalla piu' frequente
            conta = collections.Counter(c_ for x_ in tutte for k_, v_ in (x_.get("per_turno") or {}).items()
                                        if re.fullmatch(kc[2:] + r"(\d+)", k_) for c_ in v_)
            carte = [c_ for c_, _n in conta.most_common()]
        b = R_F.Righe(tk, F, ca, self.righe_av(pre), list(DA.CAMPI_TURNO), lambda n: self.campo_riga(nome, n), voci,
                      lambda rr, pre=pre: self.metti_righe_av(pre, rr), dopo=dopo, larga_campo=170, larga_voce=200, una_voce=bool(una), carte=carte,
                      fasi=list(DA.FASI_LANCIO) if pre in self.FASE_RIGHE else None)
        self._costruttori_av[pre] = b
        ca.create_window(8, y, window=b.fr, anchor="nw")
        b.fr.update_idletasks()
        return y + b.fr.winfo_reqheight() + 12

    # le abilita' attivate a righe (13 nov 2026): una riga = una carta, e una tendina per ogni momento (Any time, il turno, il passo col turno); piu' momenti
    # nella stessa riga o piu' righe = tutti nella stessa partita. Il filtro: «ab_io» = [«Carta · quando»]
    def righe_ab(self, k):
        """Le righe del costruttore delle abilita': quelle a video se dicono ancora il filtro, se no rifatte dal filtro; di partenza una riga vuota."""
        ora = sorted(self.filtri.get(k) or [])
        ui = self.__dict__.setdefault("_righe_ui", {}).get(k)
        if ui and self._da_righe_ab(ui) == ora:
            return [[c_, list(v_)] for c_, v_ in ui]
        per = {}
        for v in ora:
            carta, _s, quando = v.partition(" · ")
            per.setdefault(carta, []).append(quando)
        return [[c_, q_] for c_, q_ in per.items()] or [[None, [None]]]

    @staticmethod
    def _da_righe_ab(righe):
        return sorted({f"{c_} · {q_}" for c_, vv in righe if c_ for q_ in vv or [] if q_})

    def righe_abilita(self, ca, k, y, tutte):
        """Il costruttore delle abilita' attivate dentro la tela di Advanced filters, a y: le carte sono quelle attivate nelle partite di questo tipo, dalla
        piu' frequente; i momenti sempre tutti (DA.QUANDO_ATTIVATE). -> la y sotto."""
        tk, F = self.tk, self.F
        conta = collections.Counter(v.partition(" · ")[0] for x_ in tutte for v in DA.valori_di(k, x_) if v.endswith(" · Any time"))
        righe = self.righe_ab(k)
        carte = [c_ for c_, _n in conta.most_common()] + [c_ for c_, _v in righe if c_ and c_ not in conta]
        if not carte:
            ca.create_text(8, y + 10, text="No activated abilities in these games (or games read before this filter existed).", anchor="w",
                           fill=C["grigio"], font=F(8))
            return y + 30
        b = R_F.Righe(tk, F, ca, righe, carte, lambda c_: f"{c_}  ({conta.get(c_, 0)})", lambda c_: list(DA.QUANDO_ATTIVATE),
                      lambda rr, k=k: self.metti_righe_ab(k, rr), dopo="activated", larga_campo=230, larga_voce=200)
        self._costruttori_av[k] = b
        ca.create_window(8, y, window=b.fr, anchor="nw")
        b.fr.update_idletasks()
        return y + b.fr.winfo_reqheight() + 12

    def righe_mano(self, ca, k, y, tutte):
        """Il costruttore della mano iniziale dentro la tela di Advanced filters, a y: ogni riga e' quante · di cosa · quale carta (facoltativa, le carte delle
        mani tenute dalla piu' frequente) · che valore di mana (facoltativo). Di partenza una riga vuota. -> la y sotto."""
        tk, F = self.tk, self.F
        conta = collections.Counter(n for x_ in tutte for n in (x_.get("mano_conta") or {}))
        righe = self.__dict__.setdefault("_righe_ui", {}).get(k)
        if righe is not None and (self.filtri.get(k) or None) != (self.reqs_mano(righe) or None):      # il filtro tolto dalla domanda: le righe lo seguono
            righe = None
        if righe is None:
            righe = []
            for q in self.filtri.get(k) or []:
                quante, cosa, carta, mv = (str(q).split("|") + ["", "", "", ""])[:4]
                righe.append([quante or None, [cosa or None], carta or None, mv or None])
            righe = righe or [[None, [None], None, None]]
            self._righe_ui[k] = righe
        b = R_F.Righe(tk, F, ca, righe, [k_ for k_, _n in DA.MANO_QUANTI], lambda q_: dict(DA.MANO_QUANTI).get(q_, q_), lambda q_: list(DA.MANO_COSA),
                      lambda rr, k=k: self.metti_righe_mano(k, rr), larga_campo=140, larga_voce=170, una_voce=True,
                      carte=[c_ for c_, _n in conta.most_common()], fasi=list(DA.MANO_MV), etichetta_fase="with", fase_qualsiasi=DA.MANO_MV_QUALSIASI)
        self._costruttori_av["?" + k] = b
        ca.create_window(8, y, window=b.fr, anchor="nw")
        b.fr.update_idletasks()
        y += b.fr.winfo_reqheight() + 4
        ca.create_text(8, y + 8, text=("Every line must be true in the same hand. «Any card» with a card name: that card; a mana value leaves the lands out. "
                                       "Examples: Exactly 3 Land · At least 1 Creature with mana value 2 or less · None (0) Removal."),
                       anchor="nw", fill=C["muto"], font=F(7), width=LARGA_RIGHE_AV - 30)
        return y + 40

    @staticmethod
    def reqs_mano(righe):
        """Le righe del costruttore della mano -> il filtro: una riga entra quando ha quante e almeno cosa o la carta."""
        reqs = []
        for r_ in righe:
            quante, cosa = r_[0], (r_[1] or [None])[0]
            carta = r_[2] if len(r_) > 2 else None
            mv = r_[3] if len(r_) > 3 else None
            if quante and (cosa or carta):
                reqs.append(f"{quante}|{cosa or 'Any card'}|{carta or ''}|{mv or ''}")
        return reqs

    def metti_righe_mano(self, k, righe):
        """Dalle righe della mano al filtro «mano_req»."""
        reqs = self.reqs_mano(righe)
        if reqs:
            self.filtri[k] = reqs
        else:
            self.filtri.pop(k, None)
        self.__dict__.setdefault("_righe_ui", {})[k] = [[r_[0], list(r_[1] or [None])] + list(r_[2:4]) for r_ in righe]
        self.fr.after_idle(self.disegna)

    def metti_righe_ab(self, k, righe):
        self.filtri[k] = self._da_righe_ab(righe) or None
        if self.filtri[k] is None:
            self.filtri.pop(k)
        self.__dict__.setdefault("_righe_ui", {})[k] = [[c_, list(v_ or [None])] for c_, v_ in righe]
        self.fr.after_idle(self.disegna)

    def casella_carta_av(self, ca, k, y, tutte):
        """Una voce di Advanced filters che e' una carta di tutta la partita (la carta nella mano iniziale, la carta vista dell'Opponent): il nome e la casella
        che completa, coi nomi delle partite del tipo dal piu' frequente. -> la y sotto."""
        sc = self.filtri.get(k)
        sc = sc[0] if isinstance(sc, list) and sc else sc
        ca.create_text(8, y + 13, text=hero_txt(DA.nome_var(k)), anchor="w", fill=C["titolo"] if sc else C["testo"], font=self.F(8, bool(sc)), width=290)
        conta = collections.Counter(c_ for x_ in tutte for c_ in set(DA.valori_di(k, x_) or []))
        cc = R_F.CartaCompleta(self.tk, self.F, ca, [c_ for c_, _n in conta.most_common()], sc or None,
                               lambda v_, k=k: self.metti_carta_av(k, v_), larga=300)
        ca.create_window(310, y + 2, window=cc.fr, anchor="nw")
        self._costruttori_av["%" + k] = cc
        return y + 36

    def metti_carta_av(self, k, v):
        """La carta scelta in una casella di tutta la partita; «Any card» la toglie."""
        if not v or v == R_F.QUALSIASI:
            self.filtri.pop(k, None)
        else:
            self.filtri[k] = v
        self.fr.after_idle(self.disegna)

    def metti_righe_av(self, pre, righe):
        """Dalle righe ai filtri del gruppo; le righe restano come sono a video (anche le tendine ancora vuote)."""
        for fase in [None] + ([c_ for c_, _n in DA.FASI_LANCIO] if pre in self.FASE_RIGHE else []):
            kt, kc = self.chiavi_fase(pre, fase)
            for n in DA.CAMPI_TURNO:
                self.filtri.pop(f"{kt}{n}", None)
                if kc:
                    self.filtri.pop(f"{kc}{n}", None)
        self.filtri.update(self._da_righe(pre, righe))
        self.__dict__.setdefault("_righe_ui", {})[pre] = [[r_[0], list(r_[1] or [None])] + list(r_[2:4]) for r_ in righe]
        self.fr.after_idle(self.disegna)

    def barra_av(self, a, b):
        """La barra sottile accanto ai filtri: dove sei e quanto si vede; niente se tutto ci sta."""
        c = self.cv_barra_av
        c.delete("all")
        a, b = float(a), float(b)
        if b - a >= 0.999:
            return
        H = max(c.winfo_height(), int(c.cget("height")))
        c.create_rectangle(3, 0, 7, H, fill="#161b25", outline="")
        c.create_rectangle(2, a * H, 8, max(a * H + 24, b * H), fill="#4a4a52", outline="")

    def trascina_av(self, e):
        H = max(self.cv_barra_av.winfo_height(), 1)
        a, b = self.cv_av.yview()
        self.cv_av.yview_moveto(max(0.0, min(1.0 - (b - a), e.y / H - (b - a) / 2)))

    def clic_avanzati(self, e):
        yy = self.cv_av.canvasy(e.y)
        for x0, y0, x1, y1, k, v in getattr(self, "_box_av", []):
            if x0 <= e.x <= x1 and y0 <= yy <= y1:
                if v is None:
                    self.filtri.pop(k, None)
                elif DA.multipla(k):        # scelta multipla: la voce si aggiunge o si toglie; Nothing sta da sola
                    sc = self.filtri.get(k)
                    sc = list(sc) if isinstance(sc, list) else ([sc] if sc else [])
                    if v in sc:
                        sc.remove(v)
                    elif v == "Nothing":
                        sc = ["Nothing"]
                    else:
                        sc = [i for i in sc if i != "Nothing"] + [v]
                    sc.sort(key=DA.ordine_lancio)
                    self.filtri[k] = sc or None
                else:
                    self.filtri[k] = v
                self.disegna()
                return (k, v)
        return None

    def clic_domanda(self, e):
        """La x di un pezzo della domanda: quel filtro si toglie."""
        for x0, y0, x1, y1, kf in getattr(self.cv_dom, "_pezzi", []):
            if x0 <= e.x <= x1 and y0 <= e.y <= y1:
                self.filtri.pop(kf, None)
                self.disegna()
                return kf
        return None

    def apri_fase(self, j):
        """La finestra dei filtri in piu' di una fase: per ognuno Any o un valore (per le situazioni Yes o No), si applica subito. Una finestra sola: un'altra fase
        la riempie."""
        tk, F = self.tk, self.F
        self.fase = j
        f = getattr(self, "fin_fase", None)
        if f is None or not f.winfo_exists():
            f = self.fin_fase = tk.Toplevel(self.fr); f.configure(bg=C["scheda"])
            f.transient(self.fr.winfo_toplevel())
            f.geometry(f"+{self.cv_sx.winfo_rootx() + self.cv_sx.winfo_width() + 16}+{self.cv_sx.winfo_rooty()}")
            f.bind("<Escape>", lambda e: f.destroy())
            self.l_fase = tk.Label(f, text="", bg=C["scheda"], fg=C["titolo"], font=F(9, True)); self.l_fase.pack(anchor="w", padx=14, pady=(12, 2))
            tk.Label(f, text="More filters for this phase of the game. Yes: only the games where it happened; No: only those where it did not. "
                     "They apply at once, like the smart filters.", bg=C["scheda"], fg=C["grigio"], font=F(7), wraplength=LARGA_FASE - 20,
                     justify="left").pack(anchor="w", padx=14, pady=(0, 8))
            self.cv_fase = tk.Canvas(f, bg=C["scheda"], highlightthickness=0, bd=0, width=LARGA_FASE, height=200)
            self.cv_fase.pack(padx=8, pady=(0, 12))
            self.cv_fase.bind("<Button-1>", self.clic_fase)
        f.title("More filters · " + FASI[j][0].capitalize())
        self.l_fase.configure(text="MORE FILTERS · " + FASI[j][0])
        self.disegna_finestra_fase()
        f.lift()
        return f

    def disegna_finestra_fase(self):
        c = getattr(self, "cv_fase", None)
        if c is None or not c.winfo_exists():
            return
        F = self.F
        c.delete("all")
        self._box_fase = []
        tutte = [x for x in (self.righe or []) if x["tipo"] == self.tipo]
        from tkinter import font as tkfont
        misura = tkfont.Font(font=F(7, True))
        y = 4
        for k in FASI[getattr(self, "fase", 0)][1]:
            sc = self.filtri.get(k)
            vv = ["Yes", "No"] if k.startswith("sit:") else [v for v, _n in DA.valori(tutte, k)]
            c.create_text(8, y + 13, text=DA.nome_var(k), anchor="w", fill=C["titolo"] if sc else C["testo"], font=F(8, bool(sc)), width=290)
            x = 310
            for v in [None] + vv:
                t = "Any" if v is None else DA.etichetta(k, v) if k in ("miei_colori",) else v
                w = max(50, misura.measure(t) + 22)
                if x + w > LARGA_FASE - 6:      # va a capo: i valori restano tutti leggibili
                    x, y = 310, y + 30
                on = sc == v
                chip(c, x, y + 2, x + w, y + 24, t, on, F(7, True))
                self._box_fase.append((x, y + 2, x + w, y + 24, k, v))
                x += w + 6
            y += 34
        c.configure(height=y + 4)

    def clic_fase(self, e):
        for x0, y0, x1, y1, k, v in getattr(self, "_box_fase", []):
            if x0 <= e.x <= x1 and y0 <= e.y <= y1:
                self.filtri[k] = v
                self.disegna()
                return

    # ------------------------------------------------------------ By deck (12 nov 2026, Autore: «crea un pulsante in fondo: by deck: si apre una finestra e
    # scegli il tuo deck, sempre nella finestra di default e' vs all - si puo' spuntare vs colors e flaggare i colori di vs - da qui troviamo un modo intelligente
    # per fare l'analisi in base al monocolore fino al pentacolore o incolore - in ogni caso sempre un deck contro un'unica variante colore mazzo»)
    def lista(self):
        """I simboli di mana (capsule), fatti una volta."""
        if getattr(self, "_lista", None) is None:
            from capsule import Liste
            self._lista = Liste(self.tk, self.F)
        return self._lista

    def aggiorna_bottone_deck(self):
        mio, vs, suo = self.filtri.get("mio"), self.filtri.get("vs"), self.filtri.get("suo")
        t = f"Choose your deck  ·  {(mio or 'all decks').strip()} vs {suo or (DA.nome_vs(vs) if vs else 'all')}"
        self.b_deck.metti(t if len(t) <= 36 else t[:35].rstrip() + "…", bool(mio or vs or suo))

    def apri_deck(self):
        """La finestra By deck: a sinistra il tuo mazzo (o tutti), a destra contro chi: vs all, o vs colors coi colori da spuntare (una variante esatta, dal
        monocolore al pentacolore, o incolore), e sotto il mazzo contro ogni variante di colore incontrata, per gruppi; il clic su una riga la sceglie."""
        tk, F = self.tk, self.F
        f = getattr(self, "fin_deck", None)
        if f is not None and f.winfo_exists():
            f.lift(); return f
        f = self.fin_deck = tk.Toplevel(self.fr); f.title("Choose your deck"); f.configure(bg=C["scheda"])
        f.transient(self.fr.winfo_toplevel())
        f.geometry(f"+{self.cv_sx.winfo_rootx() + self.cv_sx.winfo_width() + 16}+{max(0, self.cv_sx.winfo_rooty() - 80)}")
        f.bind("<Escape>", lambda e: f.destroy())
        tk.Label(f, text="CHOOSE YOUR DECK", bg=C["scheda"], fg=C["titolo"], font=F(9, True)).pack(anchor="w", padx=14, pady=(12, 2))
        tk.Label(f, text="One of your decks against everyone, or against one exact color variant of the opponent's deck: mono-color to five colors, or colorless. "
                 "The table below is your deck against every variant you met: click a row to pick it.", bg=C["scheda"], fg=C["grigio"], font=F(7),
                 wraplength=960, justify="left").pack(anchor="w", padx=14, pady=(0, 8))
        self.cv_deck = tk.Canvas(f, bg=C["scheda"], highlightthickness=0, bd=0, width=LARGA_DECK, height=560)
        self.cv_deck.pack(padx=8, pady=(0, 12), fill="both", expand=True)
        self.cv_deck.bind("<Button-1>", self.clic_deck)
        self.cv_deck.bind("<MouseWheel>", lambda e: e.widget.yview_scroll(-2 if e.delta > 0 else 2, "units"))
        # i tuoi mazzi in ordine di utilizzo, di win rate o di nome, dalla tendina (12 nov 2026, Autore: «in by deck la mia lista deck in ordine alfabetico o
        # di win rate o di utilizzo da tendina / in box per ogni deck, a elenco con simboli di colore mana»)
        self.t_ord_deck = Tendina(tk, self.cv_deck, "Sort your decks by", F, larga=270, bg=C["scheda"])
        self.t_ord_deck.opzioni(["n", "wr", "nome"], self.ordina_deck, etichette={"n": "Most played", "wr": "Win rate", "nome": "Name (A-Z)"})
        self.t_ord_deck.set(self.ord_deck)
        self.disegna_finestra_deck()
        return f

    def ordina_deck(self, v):
        self.ord_deck = v
        self.disegna_finestra_deck()

    def colori_deck(self, nome):
        """I colori di un tuo mazzo: la variante piu' frequente fra le sue partite (dalle magie della lista)."""
        import collections
        cc = collections.Counter(x.get("miei_colori") for x in self.righe or [] if x.get("mio") == nome and x.get("miei_colori"))
        return cc.most_common(1)[0][0] if cc else ""

    def disegna_finestra_deck(self):
        c = getattr(self, "cv_deck", None)
        if c is None or not c.winfo_exists() or self.righe is None:
            return
        F = self.F
        c.delete("all")
        self._box_deck = []
        corto = lambda t, n: t if len(t) <= n else t[:n - 1] + "…"
        mio, vs, suo = self.filtri.get("mio"), self.filtri.get("vs"), self.filtri.get("suo")
        modo = "deck" if suo or self.vs_modo == "deck" else ("colors" if vs else self.vs_modo)
        pc = lambda v: f"{v:.0f}%" if v is not None else "-"
        # a sinistra il tuo mazzo: contati sotto gli altri filtri (contro chi compreso)
        base_m = DA.filtra(self.righe, {k: v for k, v in self.filtri.items() if k != "mio"}, self.tipo)
        mazzi = [v for v, _n in DA.valori(base_m, "mio", massimo=80)]
        if mio and mio not in mazzi:
            mazzi.append(mio)
        conti_m = {v: DA.conti([x for x in base_m if x.get("mio") == v]) for v in mazzi}
        ordine = getattr(self, "ord_deck", "n")
        if ordine == "nome":
            mazzi.sort(key=lambda v: v.strip().casefold())
        elif ordine == "wr":
            mazzi.sort(key=lambda v: (conti_m[v]["wr"] is None, -(conti_m[v]["wr"] or 0), -conti_m[v]["n"]))
        else:
            mazzi.sort(key=lambda v: -conti_m[v]["n"])
        t_ = getattr(self, "t_ord_deck", None)
        y = 2
        if t_ is not None and t_.fr.winfo_exists():
            c.create_window(0, y, window=t_.fr, anchor="nw")
            y += 62
        for v in [None] + mazzi:       # un riquadro per mazzo: il nome, sotto i simboli dei suoi colori, a destra partite e win rate
            k_ = DA.conti(base_m) if v is None else conti_m[v]
            on = mio == v
            c.create_rectangle(0, y, 270, y + 42, fill="#0e2238" if on else "#161b25", outline=C["accento"] if on else "#252b36")
            c.create_text(10, y + 13, text=corto((v or "All decks").strip(), 26), anchor="w", fill=C["titolo"] if on else C["testo"], font=F(8, True))
            if v is not None:
                for j, ch in enumerate(self.colori_deck(v)):
                    img = self.lista().simbolo(ch, 14)
                    if img is not None:
                        c.create_image(18 + j * 17, y + 30, image=img)
            else:
                c.create_text(10, y + 30, text="every deck", anchor="w", fill=C["muto"], font=F(7))
            wr = k_["wr"]
            c.create_text(262, y + 13, text=pc(wr), anchor="e", fill=C["muto"] if wr is None else (C["verde"] if wr >= 50 else C["rosso"]), font=F(9, True))
            c.create_text(262, y + 30, text=f"{k_['n']} games", anchor="e", fill=C["accento"] if on else C["grigio"], font=F(7))
            self._box_deck.append((0, y, 270, y + 42, "mio", v))
            y += 46
        fine_sx = y
        # a destra: contro chi
        X = 296
        y = 4
        c.create_text(X, y + 8, text="AGAINST", anchor="w", fill=C["muto"], font=F(7, True))
        y += 22
        for i, (m, t) in enumerate((("all", "vs all"), ("colors", "vs colors"), ("deck", "vs a deck"))):
            x = X + i * 118
            on = modo == m
            chip(c, x, y, x + 110, y + 28, t, on, F(8, True))
            self._box_deck.append((x, y, x + 110, y + 28, "modo", m))
        y += 40
        flag = set() if not vs else ({"C"} if vs == "C" else set(vs))
        for i, k in enumerate("WUBRGC"):
            x = X + i * 48
            on = k in flag
            c.create_rectangle(x, y, x + 40, y + 36, fill="#0e2238" if on else "#161b25", outline=C["accento"] if on else "#252b36", width=2 if on else 1)
            img = self.lista().simbolo(k, 22)
            if img is not None:
                c.create_image(x + 20, y + 18, image=img)
            else:
                c.create_text(x + 20, y + 18, text=k, fill=C["titolo"], font=F(9, True))
            self._box_deck.append((x, y, x + 40, y + 36, "colore", k))
        base_vs = DA.filtra(self.righe, {k: v for k, v in self.filtri.items() if k != "vs"}, self.tipo)
        x = X + 6 * 48 + 8
        if suo:
            kk = DA.conti(DA.filtra(self.righe, self.filtri, self.tipo))
            c.create_text(x, y + 10, text=f"{(mio or 'All decks').strip()} vs {suo}", anchor="w", fill=C["titolo"], font=F(9, True))
            c.create_text(x, y + 28, text=f"{kk['n']} games · {kk['vinte']}-{kk['perse']} · {pc(kk['wr'])}"
                          + (f"  (95% CI {kk['ic'][0]}–{kk['ic'][1]}%)" if kk["ic"] else ""), anchor="w", fill=C["accento"], font=F(8, True))
        elif vs:
            kk = DA.conti(DA.filtra(base_vs, {"vs": vs}))
            c.create_text(x, y + 10, text=f"{(mio or 'All decks').strip()} vs {DA.etichetta('vs', vs)}", anchor="w", fill=C["titolo"], font=F(9, True))
            c.create_text(x, y + 28, text=f"{kk['n']} games · {kk['vinte']}-{kk['perse']} · {pc(kk['wr'])}"
                          + (f"  (95% CI {kk['ic'][0]}–{kk['ic'][1]}%)" if kk["ic"] else ""), anchor="w", fill=C["accento"], font=F(8, True))
        elif modo == "colors":
            c.create_text(x, y + 18, text="Flag the colors of the opponent's deck: exactly those, one variant.", anchor="w", fill=C["grigio"], font=F(8))
        else:
            kk = DA.conti(base_vs)
            c.create_text(x, y + 10, text=f"{(mio or 'All decks').strip()} vs everyone", anchor="w", fill=C["titolo"], font=F(9, True))
            c.create_text(x, y + 28, text=f"{kk['n']} games · {kk['vinte']}-{kk['perse']} · {pc(kk['wr'])}", anchor="w", fill=C["grigio"], font=F(8))
        y += 52
        if modo == "deck":
            # vs a deck (18 nov 2026, Autore: «si aggiungila»): i mazzi avversari incontrati per nome, col tuo mazzo e coi colori scelti; i simboli dei loro
            # colori (la variante piu' frequente nelle tue partite contro di loro); il clic sceglie il mazzo, di nuovo lo toglie
            base_s = DA.filtra(self.righe, {k: v for k, v in self.filtri.items() if k != "suo"}, self.tipo)
            per_s = collections.defaultdict(list)
            for x_ in base_s:
                per_s[x_.get("suo") or "Unknown"].append(x_)
            c.create_text(X, y + 8, text="AGAINST EVERY DECK YOU MET" + (f" · {DA.nome_vs(vs)} only" if vs else ""), anchor="w", fill=C["muto"], font=F(7, True))
            col = dict(var=X, n=X + 280, wl=X + 336, wr=X + 400, play=X + 560, draw=X + 620)
            y += 22
            for k, t in (("var", "OPPONENT'S DECK"), ("n", "GAMES"), ("wl", "W-L"), ("wr", "WIN RATE"), ("play", "PLAY"), ("draw", "DRAW")):
                c.create_text(col[k], y + 6, text=t, anchor="w", fill=C["titolo"], font=F(7, True))
            y += 18
            if not per_s:
                c.create_text(X, y + 16, text="No opponent's decks in this situation", anchor="w", fill=C["grigio"], font=F(8))
                y += 34
            for i, (v, xs) in enumerate(sorted(per_s.items(), key=lambda kv: (-len(kv[1]), kv[0]))):
                k_ = DA.conti(xs)
                on, poche = v == suo, k_["n"] < 5
                c.create_rectangle(X - 4, y, LARGA_DECK, y + 24, fill="#0e2238" if on else ("#161b25" if i % 2 == 0 else C["scheda"]),
                                   outline=C["accento"] if on else "")
                varianti = collections.Counter(DA.vs_di(x_) for x_ in xs if DA.vs_di(x_))
                vv_ = varianti.most_common(1)[0][0] if varianti else ""
                for j, ch in enumerate(vv_):
                    img = self.lista().simbolo(ch, 14)
                    if img is not None:
                        c.create_image(col["var"] + 8 + j * 16, y + 12, image=img)
                testo = C["muto"] if poche else C["titolo"]
                c.create_text(col["var"] + 8 + 5 * 16 + 4, y + 12, text=corto(v, 24), anchor="w", fill=testo, font=F(8, on))
                c.create_text(col["n"], y + 12, text=str(k_["n"]), anchor="w", fill=testo, font=F(8))
                c.create_text(col["wl"], y + 12, text=f"{k_['vinte']}-{k_['perse']}", anchor="w", fill=C["muto"] if poche else C["testo"], font=F(8))
                wr_ = k_["wr"]
                colw = C["muto"] if poche else (C["verde"] if (wr_ or 0) >= 50 else C["rosso"])
                c.create_rectangle(col["wr"], y + 8, col["wr"] + 100, y + 16, fill="#252b36", outline="")
                if wr_ is not None:
                    c.create_rectangle(col["wr"], y + 8, col["wr"] + wr_, y + 16, fill=colw, outline="")
                c.create_line(col["wr"] + 50, y + 5, col["wr"] + 50, y + 19, fill="#d8d8dc")
                c.create_text(col["wr"] + 108, y + 12, text=pc(wr_), anchor="w", fill=colw, font=F(8, True))
                c.create_text(col["play"], y + 12, text=pc(k_["play"]), anchor="w", fill=C["muto"] if poche else C["testo"], font=F(8))
                c.create_text(col["draw"], y + 12, text=pc(k_["draw"]), anchor="w", fill=C["muto"] if poche else C["testo"], font=F(8))
                self._box_deck.append((X - 4, y, LARGA_DECK, y + 24, "suo", v))
                y += 26
            c.create_text(X, y + 8, text="grey: under 5 games, a hint", anchor="w", fill=C["muto"], font=F(7))
            y += 22
            alto = max(y, fine_sx) + 8
            c.configure(scrollregion=(0, 0, LARGA_DECK, alto), height=min(alto, 720))
            return
        # la tabella: il mazzo contro ogni variante, per gruppi dal monocolore al pentacolore e incolore
        c.create_text(X, y + 8, text="AGAINST EVERY COLOR VARIANT YOU MET", anchor="w", fill=C["muto"], font=F(7, True))
        col = dict(var=X, n=X + 280, wl=X + 336, wr=X + 400, play=X + 560, draw=X + 620)
        y += 22
        for k, t in (("var", "VARIANT"), ("n", "GAMES"), ("wl", "W-L"), ("wr", "WIN RATE"), ("play", "PLAY"), ("draw", "DRAW")):
            c.create_text(col[k], y + 6, text=t, anchor="w", fill=C["titolo"], font=F(7, True))
        y += 18
        gruppi = DA.per_varianti(base_vs)
        if not gruppi:
            c.create_text(X, y + 16, text="No games with the opponent's colors in this situation", anchor="w", fill=C["grigio"], font=F(8))
            y += 34

        def barra(x, yy, wr, colore):
            c.create_rectangle(x, yy + 8, x + 100, yy + 16, fill="#252b36", outline="")
            if wr is not None:
                c.create_rectangle(x, yy + 8, x + wr, yy + 16, fill=colore, outline="")
            c.create_line(x + 50, yy + 5, x + 50, yy + 19, fill="#d8d8dc")
            c.create_text(x + 108, yy + 12, text=pc(wr), anchor="w", fill=colore, font=F(8, True))
        for g in gruppi:
            k_ = g["conti"]
            c.create_rectangle(X - 4, y, LARGA_DECK, y + 24, fill="#1d222b", outline="")
            c.create_text(col["var"], y + 12, text=g["gruppo"].upper(), anchor="w", fill=C["titolo"], font=F(8, True))
            c.create_text(col["n"], y + 12, text=str(k_["n"]), anchor="w", fill=C["titolo"], font=F(8, True))
            c.create_text(col["wl"], y + 12, text=f"{k_['vinte']}-{k_['perse']}", anchor="w", fill=C["testo"], font=F(8))
            barra(col["wr"], y, k_["wr"], C["verde"] if (k_["wr"] or 0) >= 50 else C["rosso"])
            c.create_text(col["play"], y + 12, text=pc(k_["play"]), anchor="w", fill=C["testo"], font=F(8))
            c.create_text(col["draw"], y + 12, text=pc(k_["draw"]), anchor="w", fill=C["testo"], font=F(8))
            y += 26
            for i, (v, k_) in enumerate(g["varianti"]):
                on, poche = v == vs, k_["n"] < 5
                fondo = "#0e2238" if on else ("#161b25" if i % 2 == 0 else C["scheda"])
                c.create_rectangle(X - 4, y, LARGA_DECK, y + 24, fill=fondo, outline=C["accento"] if on else "")
                for j, ch in enumerate(v):
                    img = self.lista().simbolo(ch, 14)
                    if img is not None:
                        c.create_image(col["var"] + 8 + j * 16, y + 12, image=img)
                testo = C["muto"] if poche else C["titolo"]
                c.create_text(col["var"] + 8 + 5 * 16 + 4, y + 12, text=DA.nome_vs(v), anchor="w", fill=testo, font=F(8, on))
                c.create_text(col["n"], y + 12, text=str(k_["n"]), anchor="w", fill=testo, font=F(8))
                c.create_text(col["wl"], y + 12, text=f"{k_['vinte']}-{k_['perse']}", anchor="w", fill=C["muto"] if poche else C["testo"], font=F(8))
                barra(col["wr"], y, k_["wr"], C["muto"] if poche else (C["verde"] if (k_["wr"] or 0) >= 50 else C["rosso"]))
                c.create_text(col["play"], y + 12, text=pc(k_["play"]), anchor="w", fill=C["muto"] if poche else C["testo"], font=F(8))
                c.create_text(col["draw"], y + 12, text=pc(k_["draw"]), anchor="w", fill=C["muto"] if poche else C["testo"], font=F(8))
                self._box_deck.append((X - 4, y, LARGA_DECK, y + 24, "vs", v))
                y += 26
            y += 6
        if gruppi:
            c.create_text(X, y + 8, text="grey: under 5 games, a hint", anchor="w", fill=C["muto"], font=F(7))
            y += 22
        alto = max(y, fine_sx) + 8
        c.configure(scrollregion=(0, 0, LARGA_DECK, alto), height=min(alto, 720))

    def clic_deck(self, e):
        c = getattr(e, "widget", None) or self.cv_deck
        y = c.canvasy(e.y)
        for x0, y0, x1, y1, cosa, v in getattr(self, "_box_deck", []):
            if not (x0 <= e.x <= x1 and y0 <= y <= y1):
                continue
            vs = self.filtri.get("vs")
            if cosa == "mio":
                self.filtri["mio"] = v
            elif cosa == "modo":
                self.vs_modo = v
                if v == "all":
                    self.filtri["vs"] = None
                    self.filtri["suo"] = None
                elif v == "colors":
                    self.filtri["suo"] = None
            elif cosa == "suo":         # vs a deck: il mazzo avversario per nome (di nuovo: tolto)
                self.vs_modo = "deck"
                self.filtri["suo"] = None if self.filtri.get("suo") == v else v
            elif cosa == "colore":     # vs colors: i colori spuntati sono una variante esatta; incolore sta da solo
                self.vs_modo = "colors"
                flag = set() if not vs else ({"C"} if vs == "C" else set(vs))
                if v == "C":
                    flag = set() if "C" in flag else {"C"}
                else:
                    flag.discard("C")
                    flag ^= {v}
                self.filtri["vs"] = ("C" if "C" in flag else "".join(k for k in "WUBRG" if k in flag)) or None
            elif cosa == "vs":
                self.vs_modo = "colors"
                self.filtri["vs"] = None if vs == v else v
            self.disegna()
            return

    # ------------------------------------------------------------ le situazioni salvate
    def salva_situazione(self):
        DA.salva_situazione(self.tipo, dict(self.filtri))
        self.disegna_situazioni()
        if "compare" in self.visibili():       # i filtri personali sono anche i B del confronto
            self.disegna_confronto()
        self.b_salva_sit.metti("Saved in My filters", False)
        self.b_salva_sit.after(1800, lambda: self.b_salva_sit.winfo_exists() and self.b_salva_sit.metti("Save as my filter", False))

    def disegna_situazioni(self):
        """I filtri personali si vedono nella cartella My filters: si ridisegna se si vede."""
        if "mine" in self.visibili() and self.righe is not None:
            self.disegna_miei()

    # ------------------------------------------------------------ la cartella Cards
    # Autore, 13 nov 2026: «dopo compare ci serve una chart "cards" che parlerà delle carte più comuni delle partite selezionate e le mostrerà come immagini
    # carta», poi «in cards creiamo delle vere e proprie righe di dato: riga 1 most in hand find card / most t1 /t2 /t3 / t4 found cards / match up most played
    # cards / harder to cast cards - questi risultati arriveranno dall'impostazione dei filtri». Una riga per categoria (DA.RIGHE_CARTE), le carte come immagini
    # una accanto all'altra (quante ne stanno nella larghezza), sulle partite dei filtri; sotto ogni carta il win rate e il record delle partite in cui c'e',
    # azzurro sopra il win rate di tutte le partite scelte e rosso sotto, grigio sotto 5 partite, e in quante; nella riga Harder to cast quante volte e' rimasta
    # in mano. Il clic su una carta tiene solo le sue partite, nel senso della sua riga (un filtro, che si toglie col secondo clic); al passaggio la carta grande.
    def disegna_carte(self):
        c = self.tela("cards")
        c.delete("all")
        self.via_hover_carte()
        c._box_carte, c._box_coppie, c._box_partite = [], [], []
        if self.righe is None:
            return
        if self.carte_modo == "card":
            return self.disegna_scheda_carta(c)
        F = self.F
        W = max(c.winfo_width(), 600)
        r = self.scelte()
        tutte_t = [x for x in self.righe if x["tipo"] == self.tipo]     # l'EV atteso delle righe EV viene da tutte le partite del tipo
        k_ = DA.conti(r)
        base = k_["wr"]
        c.create_text(14, 14, text=f"THE CARDS OF THESE {k_['n']} GAMES · NO LANDS", anchor="w", fill=C["muto"], font=F(7, True))
        if base is not None:
            c.create_text(W - 14, 14, text=f"win rate of these games {base:.0f}% · click a card: only its games · right-click: its analysis · Pairs: the cards that come together",
                          anchor="e", fill=C["grigio"], font=F(7))
        wc = LARGA_CARTA
        hc = round(wc * 279 / 200)
        per_riga = max(1, int((W - 28) // (wc + 14)))
        per_coppie = max(1, int((W - 28) // (wc + round(wc * 0.5) + 14)))
        y = 34
        scelte_r = set(DA.righe_carte_scelte())
        if not scelte_r:
            c.create_text(14, 46, text="No rows picked: open the wheel on the left and tick the ones you want to see.", anchor="w", fill=C["grigio"], font=F(9))
        for chiave, titolo in DA.RIGHE_CARTE:
            if chiave not in scelte_r:      # solo le righe spuntate nella rotella
                continue
            deboli = chiave in self.deboli
            if deboli:      # le piu' deboli per prime: tutta la riga, poi le ultime (DA.deboli_prima)
                carte = DA.deboli_prima(DA.riga_carte(r, chiave, quante=999, base=tutte_t), chiave, per_riga)
            else:
                carte = DA.riga_carte(r, chiave, quante=per_coppie if chiave == "finisher" else per_riga, base=tutte_t)
            c.create_line(14, y, W - 14, y, fill="#252b36")
            t_titolo = c.create_text(14, y + 14, text=titolo, anchor="w", fill=C["azzurro"], font=F(8, True))
            # le coppie della riga si aprono in una finestra a parte (13 nov 2026, Autore: «non aggiungere le coppie come righe ma come finestre extra che
            # si aprono dalla riga e mostrano le coppie»)
            i_ = c.create_text(W - 14, y + 14, text="Answers ›" if chiave == "minacce" else "Merits ›" if chiave == "ev_carte" else "Lists ›" if chiave == "ev_sue"
                               else "Pairs ›", anchor="e",
                               fill=C["accento"], font=F(8, True))
            bb = c.bbox(i_)
            c._box_coppie.append((bb[0] - 6, bb[1] - 4, bb[2] + 6, bb[3] + 4, chiave, titolo))
            if chiave in DA.VALORE_RIGA:        # il verso della riga: le migliori o le piu' deboli per prime
                ip = c.create_text(bb[0] - 26, y + 14, text="⇅ Weakest first" if deboli else "⇅ Strongest first", anchor="e",
                                   fill=C["accento"] if deboli else C["grigio"], font=F(8, True))
                bp = c.bbox(ip)
                c.create_rectangle(bp[0] - 7, bp[1] - 3, bp[2] + 7, bp[3] + 3, outline=C["accento"] if deboli else "#3a4250")
                c.tag_raise(ip)
                c._box_coppie.append((bp[0] - 7, bp[1] - 3, bp[2] + 7, bp[3] + 3, ("verso", chiave), None))
                c.itemconfigure(t_titolo, width=max(200, bp[0] - 30))
            y += 28
            if not carte:
                c.create_text(14, y + 10, text=("no cards here: these games have no replay data" if r else "no games in this situation"), anchor="w",
                              fill=C["muto"], font=F(8))
                y += 36
                continue
            x_ = 14
            for cc in carte:
                x_ += self.metti_carta(c, x_, y, cc, chiave, base) + 14
            y += hc + 50
        if getattr(self, "fin_meriti", None) is not None and self.fin_meriti.winfo_exists():      # la finestra dei meriti segue i filtri
            self.apri_meriti(alza=False)
        if getattr(self, "fin_liste", None) is not None and self.fin_liste.winfo_exists():        # e quella dei mazzi ricomposti
            self.apri_liste(alza=False)
        c.configure(scrollregion=(0, 0, W, y + 6))

    def metti_carta(self, c, x, y, cc, chiave, base):
        """metti_carta_dentro, poi ogni testo sotto la carta sta nella sua larghezza (18 nov 2026, la foto della cartella Cards: le righe lunghe, «their turn
        4.3 · 39 games», «survived 11/13 · won 82% · else ...», si accavallavano con la carta accanto): prima il carattere piu' piccolo, fino a 6 punti, poi il
        testo tagliato coi puntini; un testo che va a capo prende la larghezza della carta."""
        import re as _re
        prima = (c.find_all() or (0,))[-1]
        larga = self.metti_carta_dentro(c, x, y, cc, chiave, base)
        hc = round(LARGA_CARTA * 279 / 200)
        lim = larga + 10
        for i in c.find_all():
            if i <= prima or c.type(i) != "text" or (c.coords(i) or [0, 0])[1] < y + hc:
                continue
            if int(float(c.itemcget(i, "width") or 0)) > 0:
                c.itemconfigure(i, width=lim)
                continue
            f_ = c.itemcget(i, "font")
            m_ = _re.search(r"(\d+)", f_)
            dim, gr = (int(m_.group(1)) if m_ else 8), "bold" in f_
            bb = c.bbox(i)
            while bb and bb[2] - bb[0] > lim and dim > 6:
                dim -= 1
                c.itemconfigure(i, font=self.F(dim, gr))
                bb = c.bbox(i)
            t_ = c.itemcget(i, "text")
            while bb and bb[2] - bb[0] > lim and len(t_) > 4:
                t_ = t_[:-2]
                c.itemconfigure(i, text=t_.rstrip(" ·") + "…")
                bb = c.bbox(i)
        return larga

    def metti_carta_dentro(self, c, x, y, cc, chiave, base):
        """Una carta (o una coppia: due carte sovrapposte a meta') di Cards o della finestra delle coppie: l'immagine, il bordo se e' il filtro acceso, sotto il
        win rate col record e in quante partite (nella riga Harder to cast quante volte e' rimasta in mano). -> la larghezza."""
        F = self.F
        wc = LARGA_CARTA
        hc = round(wc * 279 / 200)
        nomi = cc.get("nomi") or (cc["nome"],)
        sopra = round(wc * 0.5)
        larga_c = wc + sopra * (len(nomi) - 1)
        fk, fv = DA.filtro_carta(chiave, cc)
        for j, nm in enumerate(nomi):
            xx = x + j * sopra
            img = self.immagine_carta(DA.nome_intero(nm), wc, False)
            if img is not None:
                c.create_image(xx, y, image=img, anchor="nw")
            else:
                c.create_rectangle(xx, y, xx + wc, y + hc, fill="#141a24", outline="#2c3340")
                c.create_text(xx + wc / 2, y + hc / 2, text=nm, fill=C["titolo"], font=F(8, True), width=wc - 12, justify="center")
            # il riquadro di ogni carta: la carta grande al passaggio; il filtro della carta o della coppia al clic
            c._box_carte.append((xx, y, (xx + sopra) if j < len(nomi) - 1 else xx + wc, y + hc + 38, nm, chiave, fk, fv))
        if self.filtri.get(fk) == fv:
            c.create_rectangle(x - 3, y - 3, x + larga_c + 3, y + hc + 3, outline=C["accento"], width=2)
        poche = cc["n"] < 5
        col = C["muto"] if poche or base is None else (C["verde"] if cc["wr"] > base else C["rosso"] if cc["wr"] < base else C["testo"])
        xc = x + larga_c / 2
        if cc.get("sua"):           # una carta dell'Opponent: il suo EV in campo per lui (rosso se ti ha fatto male), il tuo win rate in quelle partite
            col_v = C["muto"] if cc["poche"] else (C["rosso"] if cc["in_campo"] >= 1 else C["verde"] if cc["in_campo"] <= -1 else C["testo"])
            c.create_text(xc, y + hc + 12, text=f"{cc['in_campo']:+.1f} EV for them", fill=col_v, font=F(9, True))
            c.create_text(xc, y + hc + 29, text=f"stayed {cc['sopr']}/{cc['n']} · you won {cc['wr']:.0f}%", fill=C["grigio"], font=F(7))
        elif "in_campo" in cc:        # l'EV di una carta in campo (18 nov 2026): il plus-minus dei turni in cui c'era, e chi sopravvive
            col_v = C["muto"] if cc["poche"] else (C["verde"] if cc["in_campo"] >= 1 else C["rosso"] if cc["in_campo"] <= -1 else C["testo"])
            c.create_text(xc, y + hc + 12, text=f"{cc['in_campo']:+.1f} EV in play", fill=col_v, font=F(9, True))
            sopr_ = (f"lived {cc['sopr']}/{cc['n']}" + (f" · {cc['wr_sopr']}%" if cc["wr_sopr"] is not None else "")
                     + (f" · else {cc['wr_non']}%" if cc["wr_non"] is not None else ""))
            c.create_text(xc, y + hc + 29, text=sopr_, fill=C["grigio"], font=F(7))
            # il contesto: con un partner in campo o da sola; altrimenti lanciata subito o dopo aver aspettato in mano (Autore: «se tengo ajani pridemate
            # finche' non ho sul tavolo qualcosa che sinergizzi ... sto cercando il mio EV»)
            if cc.get("con_ev") is not None and cc.get("sola_ev") is not None:
                ctx_ = f"partner {cc['con_ev']:+.1f} · alone {cc['sola_ev']:+.1f}"
            elif cc.get("subito_ev") is not None and cc.get("attesa_ev") is not None:
                ctx_ = f"at once {cc['subito_ev']:+.1f} · waited {cc['attesa_ev']:+.1f}"
            else:
                ctx_ = ""
            if ctx_:
                c.create_text(xc, y + hc + 43, text=ctx_, fill=C["muto"], font=F(7))
        elif "atteso" in cc:        # l'EV al lancio di una magia contro la stessa magia nelle altre partite
            col_v = C["muto"] if cc["poche"] else (C["verde"] if cc["scarto"] >= 1 else C["rosso"] if cc["scarto"] <= -1 else C["testo"])
            c.create_text(xc, y + hc + 12, text=f"{cc['ev']:+.1f} at cast", fill=col_v, font=F(9, True))
            c.create_text(xc, y + hc + 29, text=f"usual {cc['atteso']:+.1f} · {cc['lanci']} cast{'s' * (cc['lanci'] != 1)}", fill=C["grigio"], font=F(7))
            if cc.get("assist"):        # l'assist: meta' del merito della creatura che ha preparato (il trucco prima del combattimento)
                c.create_text(xc, y + hc + 43, text=f"assist {cc['assist']:+.1f} to your creatures", fill=C["muto"], font=F(7))
        elif "salto" in cc:           # un finisher: quante vittorie ha deciso, il salto di vantaggio medio
            c.create_text(xc, y + hc + 12, text=f"decided {cc['n']} win{'s' * (cc['n'] != 1)}", fill=C["azzurro"], font=F(9, True))
            c.create_text(xc, y + hc + 29, text=f"swing +{cc['salto']:.0f} · {cc['quota']:.0f}% of your wins", fill=C["grigio"], font=F(7))
        elif cc.get("risposta"):    # C15: una tua risposta, quante copie hai (o il jolly per craftarla: 18 nov 2026)
            cr_ = DA._carta(cc["nome"]) or {}
            if cr_.get("copie"):
                c.create_text(xc, y + hc + 12, text=f"you own {cr_.get('copie', 0)}", fill=C["azzurro"], font=F(9, True))
            else:
                c.create_text(xc, y + hc + 12, text=f"craft · {RARITA_NOME.get(cr_.get('r'), 'wildcard')}", fill="#f0ad4e", font=F(9, True))
            c.create_text(xc, y + hc + 29, text=f"MV {cr_.get('cmc', 0)}", fill=C["grigio"], font=F(7))
        elif "chiuse" in cc:        # una win condition (18 nov 2026): quante vittorie ha chiuso
            c.create_text(xc, y + hc + 12, text=f"closed {cc['chiuse']} win{'s' * (cc['chiuse'] != 1)}", fill=C["azzurro"], font=F(9, True))
            c.create_text(xc, y + hc + 29, text=f"{cc['quota']:.0f}% of wins · {cc['n']} cast · {cc['wr']:.0f}% WR", fill=C["grigio"], font=F(7))
        elif cc.get("quando_sua"):  # una sua carta nel tempo e sulle tue (18 nov 2026)
            c.create_text(xc, y + hc + 12, text=(f"their turn {cc['giro']:.1f}" if cc.get("giro") is not None else "turn unknown") + f" · {cc['n']} games",
                          fill=C["rosso"] if (cc["wr"] or 0) < (base or 0) else C["testo"], font=F(9, True))
            # i bersagli: la prima sotto, la seconda sulla riga dopo (una riga a capo saliva sopra il turno); il resto nella sotto-scheda Card
            col_ = list(cc.get("colpite") or [])
            c.create_text(xc, y + hc + 29, text=(f"hit {col_[0][0]} ×{col_[0][1]}" if col_ else f"you won {cc['wr']:.0f}%"), fill=C["grigio"], font=F(7))
            if len(col_) > 1:
                c.create_text(xc, y + hc + 43, text=f"{col_[1][0]} ×{col_[1][1]}" + (f" +{len(col_) - 2}" if len(col_) > 2 else ""), fill=C["muto"],
                              font=F(7))
        elif "lift" in cc:          # un compagno nella rosa della carta (18 nov 2026)
            col_l = C["muto"] if cc["poche"] or cc["lift"] is None else (C["verde"] if cc["lift"] > 0 else C["rosso"] if cc["lift"] < 0 else C["testo"])
            c.create_text(xc, y + hc + 12, text=("-" if cc["lift"] is None else f"{cc['lift']:+.0f} pts together"), fill=col_l, font=F(9, True))
            c.create_text(xc, y + hc + 29, text=f"{cc['wr']:.0f}% in {cc['n']} · without {cc['wr_senza'] if cc['wr_senza'] is not None else '-'}%",
                          fill=C["grigio"], font=F(7))
        elif "eccesso" in cc:       # C15: una minaccia, quante sconfitte, quante risposte hai
            c.create_text(xc, y + hc + 12, text=f"in {cc['perse']} of your losses", fill=C["rosso"], font=F(9, True))
            c.create_text(xc, y + hc + 29, text=f"+{cc['eccesso']} pts vs wins · {len(cc.get('risposte') or [])} answers", fill=C["grigio"], font=F(7))
        elif "economici" in cc:     # C13: cosa tolgono le tue rimozioni
            col_e = C["muto"] if cc["n"] < 5 else (C["rosso"] if cc["economici"] >= 50 else C["verde"])
            c.create_text(xc, y + hc + 12, text=f"removed MV {cc['bers_mv']:.1f} · its {cc['rim_mv']:.0f}", fill=col_e, font=F(9, True))
            c.create_text(xc, y + hc + 29, text=f"{cc['economici']}% cheap · {cc['tolti']} removed", fill=C["grigio"], font=F(7))
        elif "iwd" in cc:       # C4: l'IWD personale
            col_i = C["muto"] if cc["poche"] else (C["verde"] if cc["iwd"] > 0 else C["rosso"] if cc["iwd"] < 0 else C["testo"])
            c.create_text(xc, y + hc + 12, text=f"{cc['iwd']:+.0f} pts when drawn", fill=col_i, font=F(9, True))
            c.create_text(xc, y + hc + 29, text=f"{cc['wr']:.0f}% in {cc['n']} · not drawn {cc['wr_non']:.0f}% in {cc['n_non']}", fill=C["grigio"], font=F(7))
        elif chiave == "bloccate" and "bloccata" in cc:
            c.create_text(xc, y + hc + 12, text=f"{cc['bloccata']}% stuck", fill=C["rosso"], font=F(9, True))
            c.create_text(xc, y + hc + 29, text=f"{cc['n']} of {cc['mano']} games · {cc['wr']:.0f}% WR", fill=C["grigio"], font=F(7))
        else:
            c.create_text(xc, y + hc + 12, text=f"{cc['wr']:.0f}% WR  ·  {cc['vinte']}-{cc['perse']}", fill=col, font=F(9, True))
            if cc.get("turno_lancio") is not None:      # R12: il giro medio del primo lancio e i giri in mano prima
                held_ = f" · held {cc['in_mano_giri']:.1f}" if cc.get("in_mano_giri") is not None else ""
                c.create_text(xc, y + hc + 29, text=f"cast T{cc['turno_lancio']:.1f}{held_}", fill=C["grigio"], font=F(7))
            else:
                c.create_text(xc, y + hc + 29, text=f"in {cc['n']} games · {cc['quota']:.0f}% of games", fill=C["grigio"], font=F(7))
        return larga_c

    # ------------------------------------------------------------ la cartella Decisions
    def cambia_dec(self, m):
        self.dec_modo = m
        self.sincronizza()
        self.disegna_decisioni()
        self.disegna_filtri_dec()
        if self.mostra_guadagno and "chart" in self.visibili():
            self.disegna_grafico()

    def apri_filtri_dec(self):
        """La finestra dei filtri delle decisioni, impaginata come Advanced filters (13 nov 2026, Autore: «i filtri per decision li imposti costruibili e
        l'impaginazione la fai come in advanced filters», «tieni solo i filtri per noi Player»): in cima Your attacks e Your blocks, sotto la risposta (le
        decisioni scelte coi loro conti) e le righe del costruttore (filtro e voci; fra le voci di un filtro basta una, fra filtri servono tutti)."""
        tk, F = self.tk, self.F
        f = getattr(self, "fin_dec", None)
        if f is None or not f.winfo_exists():
            f = self.fin_dec = tk.Toplevel(self.fr)
            f.title("Leak Finder · Decision filters")
            f.configure(bg=C["scheda"])
            f.bind("<Escape>", lambda e: f.destroy())
            tk.Label(f, text="DECISION FILTERS", bg=C["scheda"], fg=C["titolo"], font=F(12, True)).pack(anchor="w", padx=16, pady=(14, 2))
            tk.Label(f, text="Only your decisions: what you did and the situation you did it in. Between the values of a filter one is enough, between filters "
                             "all are needed. The Decisions folder and «Gained by decisions» under the Chart follow them.", bg=C["scheda"], fg=C["grigio"],
                     font=F(8), wraplength=780, justify="left").pack(anchor="w", padx=16)
            self.f_dec_tipi = tk.Frame(f, bg=C["scheda"]); self.f_dec_tipi.pack(anchor="w", padx=16, pady=(10, 4))
            self.cv_dec_dom = tk.Canvas(f, bg=C["scheda"], highlightthickness=1, highlightbackground="#252b36", bd=0, width=820, height=66)
            self.cv_dec_dom.pack(anchor="w", padx=16, pady=(4, 8))
            self.f_dec_righe = tk.Frame(f, bg=C["scheda"]); self.f_dec_righe.pack(anchor="w", padx=16, pady=(4, 16), fill="x")
            try:
                f.geometry(f"+{self.fr.winfo_rootx() + 120}+{self.fr.winfo_rooty() + 80}")
            except Exception:      # noqa: BLE001
                pass
        self.disegna_filtri_dec()
        f.lift()
        return f

    def disegna_filtri_dec(self):
        f = getattr(self, "fin_dec", None)
        if f is None or not f.winfo_exists():
            return
        tk, F = self.tk, self.F
        tipo = self.dec_modo if self.dec_modo in ("attacco", "blocco") else "attacco"
        for w in self.f_dec_tipi.winfo_children():
            w.destroy()
        for t_, nome in (("attacco", "Your attacks"), ("blocco", "Your blocks")):
            b = pulsante_solido(tk, F, self.f_dec_tipi, nome, t_ == tipo, lambda t_=t_: self.cambia_dec(t_), alto=28, bg=C["scheda"], colori=GRIGI)
            b.configure(width=150); b.pack(side="left", padx=(0, 6))
        # il Reset della scheda aperta (Your attacks o Your blocks); Reset all in alto azzera tutto
        b = pulsante_solido(tk, F, self.f_dec_tipi, "Reset · " + ("Your attacks" if tipo == "attacco" else "Your blocks"), False,
                            lambda tipo=tipo: self.reset_filtri_dec(tipo), alto=28, bg=C["scheda"], colori=ARANCIO)
        b.configure(width=190); b.pack(side="left", padx=(30, 0))
        self.b_reset_dec = b
        self.disegna_risposta_dec()
        for w in self.f_dec_righe.winfo_children():
            w.destroy()
        filtri_t = DEC.FILTRI[tipo]
        nomi = {k2: n2 for k2, n2, _v in filtri_t}
        voci = {k2: list(v2) for k2, _n, v2 in filtri_t}
        righe = self.righe_dec.setdefault(tipo, [])
        if not righe:
            righe.append([None, [None]])
        self.costruttore_dec = R_F.Righe(tk, F, self.f_dec_righe, righe, [k2 for k2, _n, _v in filtri_t], lambda k2: nomi.get(k2, k2),
                                        lambda k2: voci.get(k2, []), lambda rr, tipo=tipo: self.metti_righe_dec(tipo, rr), larga_campo=230, larga_voce=150)
        self.costruttore_dec.fr.pack(anchor="w", fill="x")

    def reset_filtri_dec(self, tipo):
        """Il Reset di una scheda dei filtri delle decisioni: i suoi filtri e le sue righe via, quelli dell'altro tipo restano."""
        self.dec_f = dict(self.dec_f, **{tipo: {}})
        self.righe_dec[tipo] = []
        self.sincronizza()
        self.disegna_decisioni()
        self.disegna_filtri_dec()
        if "chart" in self.visibili():
            self.disegna_grafico()

    def metti_righe_dec(self, tipo, righe):
        """Dalle righe del costruttore ai filtri delle decisioni di quel tipo: {chiave: [voci scelte]} (le righe con la stessa chiave si uniscono)."""
        f = {}
        for campo, voci in righe:
            vv = [v for v in voci or [] if v]
            if campo and vv:
                f[campo] = list(dict.fromkeys(f.get(campo, []) + vv))
        self.dec_f = dict(self.dec_f, **{tipo: f})
        self.sincronizza()
        self.disegna_decisioni()
        if "chart" in self.visibili():
            self.disegna_grafico()
        self.disegna_risposta_dec()

    def disegna_risposta_dec(self):
        """In cima alla finestra dei filtri delle decisioni: le decisioni scelte coi loro conti, nelle partite dei filtri della pagina."""
        f = getattr(self, "fin_dec", None)
        if f is None or not f.winfo_exists() or self.righe is None:
            return
        tipo = self.dec_modo if self.dec_modo in ("attacco", "blocco") else "attacco"
        c, F = self.cv_dec_dom, self.F
        c.delete("all")
        r = self.scelte()
        k_ = DEC.tabella(r, tipo, self.dec_f.get(tipo))[0] if r else None
        desc = DEC.descrivi(self.dec_f.get(tipo), tipo) or "no filter yet: all of them"
        c.create_text(10, 16, text=("YOUR ATTACKS" if tipo == "attacco" else "YOUR BLOCKS") + " · " + desc, anchor="w", fill=C["azzurro"], font=F(8, True))
        if k_ and k_["n"]:
            c.create_text(10, 44, text=f"{k_['n']} combats in {k_['partite']} games", anchor="w", fill=C["titolo"], font=F(12, True))
            c.create_text(250, 44, text=f"you lost a creature {k_['perdi']:.0f}% · they lost one {k_['uccidi']:.0f}% · trade {k_['scambio']:+.2f} · "
                                        f"avg gain {(k_['guadagno'] or 0):+.1f} · game win rate {k_['wr']:.0f}%", anchor="w", fill=C["grigio"], font=F(8))
        else:
            c.create_text(10, 44, text="No decisions answer these filters: remove a line.", anchor="w", fill=C["arancio"], font=F(9, True))
        self.cv_dec_dom.k_ = k_



    def disegna_fortuna(self):
        """La cartella Luck (C1, 13 nov 2026: «lo shuffler e' truccato? perdo per le terre?», la domanda di tutti): le partite della situazione contro il caso.
        In alto le terre PESCATE entro il tuo turno 3, 5, 7 contro l'ipergeometrica del grimorio vero (DA.contro_il_caso): in tutto (con z e p) e per voce,
        screw e flood compresi, le tue partite contro quelle che il caso darebbe; il clic su una voce la mette fra i filtri. Sotto le prime mani da 7 contro il
        regolamento e contro lo smoothing del Bo1 (la migliore di 2, la nostra misura)."""
        c = self.tela("luck")
        c.delete("all")
        c._box = []
        if self.righe is None:
            return
        F = self.F
        W = max(c.winfo_width(), 700)
        r = self.scelte()
        k = DA.contro_il_caso(r)
        y = 22
        c.create_text(14, y, text="YOUR GAMES AGAINST CHANCE", anchor="w", fill=C["azzurro"], font=F(9, True))
        c.create_text(W - 14, y, text="the shuffle tested on your draws: your opening hand is your choice, your draws are not", anchor="e",
                      fill=C["grigio"], font=F(7))
        y += 26
        t5 = k["turni"].get(5) or k["turni"].get(3)
        if not k["turni"]:
            c.create_text(14, y + 10, text="No games with the draws in the log here: draws are read from the games played with the app since 22 Sep 2026.",
                          anchor="w", fill=C["grigio"], font=F(9))
            y += 40
        else:
            N0 = 5 if k["turni"].get(5) else 3
            d_ = t5["x"] - t5["e"]
            giudizio = ("normal luck: chance explains it" if t5["p"] >= 0.05 else
                        ("fewer lands than chance would give" if d_ < 0 else "more lands than chance would give") + " (p under 5%)")
            c.create_text(14, y, text=f"By your turn {N0} you drew {t5['x']} lands; chance expected {t5['e']:.1f} ({d_:+.1f}). {giudizio[0].upper() + giudizio[1:]}.",
                          anchor="w", fill=C["titolo"], font=F(10, True))
            y += 30
            col = [("turno", "BY YOUR TURN", 14), ("partite", "GAMES", 130), ("x", "LANDS DRAWN", 200), ("e", "CHANCE EXPECTED", 300), ("d", "DIFFERENCE", 420),
                   ("p", "P (Z TEST)", 510)] + [(v, t_, 600 + i * 118) for i, (v, t_) in enumerate(zip(DA.FORTUNA, (
                       "SCREW\nBOTTOM 5%", "FEWER\nTHAN EXPECTED", "AS\nEXPECTED", "MORE\nTHAN EXPECTED", "FLOOD\nTOP 5%")))]
            for _k, t, x in col:
                c.create_text(x, y, text=t, anchor="nw", fill=C["titolo"], font=F(7, True))
            y += 32
            for i, N in enumerate(DA.TURNI_FORTUNA):
                v = k["turni"].get(N)
                if not v:
                    continue
                c.create_rectangle(8, y, W - 8, y + 26, fill="#161b25" if i % 2 == 0 else "#131820", outline="")
                d_ = v["x"] - v["e"]
                for x, t, colr in ((14, f"Turn {N}", C["titolo"]), (130, str(v["partite"]), C["testo"]), (200, str(v["x"]), C["testo"]),
                                   (300, f"{v['e']:.1f}", C["testo"]), (420, f"{d_:+.1f}", C["rosso"] if v["p"] < 0.05 and d_ < 0 else C["verde"] if v["p"] < 0.05 else C["testo"]),
                                   (510, f"{v['p']:.2f}", C["testo"] if v["p"] >= 0.05 else C["arancio"])):
                    c.create_text(x, y + 13, text=t, anchor="w", fill=colr, font=F(8, x == 14))
                for j, voce in enumerate(DA.FORTUNA):
                    oss, att = v["classi"][voce]
                    x0 = 600 + j * 118
                    lontano = abs(oss - att) > 2 * math.sqrt(max(att, 1))
                    c.create_text(x0, y + 13, text=f"{oss} · {att:.1f}", anchor="w", fill=C["arancio"] if lontano else C["testo"], font=F(8, True))
                    c._box.append((x0 - 4, y, x0 + 110, y + 26, ("voce", N, voce)))
                y += 28
            y += 8
            c.create_text(14, y, text=("Each cell: your games · what chance would give (orange: far from it); click a cell to keep only those games. "
                                       "Screw and flood: the 5% tails of chance for that many draws (outside the central 90%); fewer and more: the 25% tails. "
                                       "Draws after a scry or a surveil are not fully random, and that blurs the test a little."),
                          anchor="nw", fill=C["grigio"], font=F(7), width=W - 30)
            y += 46
        m = k["mani"]
        y += 10
        c.create_text(14, y, text="YOUR FIRST 7 CARDS", anchor="w", fill=C["azzurro"], font=F(9, True))
        if not m:
            c.create_text(14, y + 26, text="No opening hands in these games.", anchor="w", fill=C["grigio"], font=F(9))
            c.configure(scrollregion=(0, 0, W, y + 60))
            return
        c.create_text(W - 14, y, text=f"{m['n']} hands · {m['bo1']} in Bo1, where Arena smooths the opening hand", anchor="e", fill=C["grigio"], font=F(7))
        y += 24
        cols = ((14, "LANDS"), (110, "YOUR HANDS"), (230, "ONE RANDOM HAND (THE RULES)"), (450, "ARENA BO1 SMOOTHING (BEST OF 2)"))
        for x, t in cols:
            c.create_text(x, y, text=t, anchor="w", fill=C["titolo"], font=F(7, True))
        y += 16
        tot = m["n"]
        for j in range(8):
            c.create_rectangle(8, y, 700, y + 22, fill="#161b25" if j % 2 == 0 else "#131820", outline="")
            for x, v, colr in ((14, str(j), C["titolo"]), (110, f"{m['oss'][j]}  ({100 * m['oss'][j] / tot:.0f}%)", C["testo"]),
                               (230, f"{m['reg'][j]:.1f}  ({100 * m['reg'][j] / tot:.0f}%)", C["grigio"]),
                               (450, f"{m['liscia'][j]:.1f}  ({100 * m['liscia'][j] / tot:.0f}%)", C["grigio"])):
                c.create_text(x, y + 11, text=v, anchor="w", fill=colr, font=F(8, x == 14))
            y += 24
        pr, pl = DA.chi2_p(m["oss"], m["reg"]), DA.chi2_p(m["oss"], m["liscia"])
        pp_ = lambda v: "p < 0.001" if v < 0.001 else f"p {v:.3f}"
        y += 6
        c.create_text(14, y, text=(f"Against one random hand: {pp_(pr)}" + (" (your hands are not plain random: smoothing)" if pr < 0.05 else "")
                                   + f" · against best of 2: {pp_(pl)}" + (" (closer, still not exact: Arena smooths more than best of 2)" if pl < 0.05 else " (it fits)")
                                   # per formato (14 nov 2026): la «migliore di 2» e' misurata sul Quick Draft; nel Constructed Bo1 non regge (Note/Misura_Smoothing_Bo1)
                                   + (" · the best-of-2 model was measured on Quick Draft: in Constructed Bo1 it is a stand-in" if self.tipo == "Constructed" else "")),
                      anchor="nw", fill=C["testo"], font=F(8), width=W - 30)
        y += 22
        c.create_text(14, y, text="The opening hand is the first 7 Arena dealt, before any mulligan. p is a chi-square test (tails merged), approximate.",
                      anchor="nw", fill=C["grigio"], font=F(7), width=W - 30)
        c.configure(scrollregion=(0, 0, W, y + 40))

    def clic_fortuna(self, e):
        c = e.widget
        x, y = c.canvasx(e.x), c.canvasy(e.y)
        b = next((b for b in getattr(c, "_box", []) if b[0] <= x <= b[2] and b[1] <= y <= b[3]), None)
        if b is None:
            return None
        _cosa, N, voce = b[4]
        self.metti_filtro(f"luck{N}", None if self.filtri.get(f"luck{N}") == voce else voce)
        return (N, voce)

    def disegna_decisioni(self):
        """Gli attacchi e i blocchi per situazione col loro esito immediato (decisioni.tabella), o i mulligan. Il clic su una riga di attacchi o blocchi la mette
        sul grafico (una linea in piu' sulle partite di quella decisione, contro All), di nuovo la toglie; nei mulligan il clic su una casella delle mani
        tenute mette Lands in hand e Start fra i filtri."""
        c = self.tela("decisions")
        c.delete("all")
        c._box = []
        if self.righe is None:
            return
        F = self.F
        W = max(c.winfo_width(), 700)
        r = self.scelte()
        if self.dec_modo == "mull":
            return self.disegna_mulligan(c, r, W)
        if self.dec_modo == "costo":
            return self.disegna_costi(c, r, W)
        if self.dec_modo == "leak":
            return self.disegna_leak(c, r, W)
        if self.dec_modo == "cimitero":
            return self.disegna_cimitero(c, r, W)
        tab = DEC.tabella(r, self.dec_modo, self.dec_f.get(self.dec_modo))
        tutte_ = tab[0]
        att = self.dec_modo == "attacco"
        f_ = DEC.descrivi(self.dec_f.get(self.dec_modo), self.dec_modo)
        c.create_text(14, 14, text=("YOUR ATTACKS" if att else "THEIR ATTACKS · YOUR DEFENSE") + (f" · {f_}" if f_ else "")
                      + f" · {tutte_['n']} combats in {tutte_['partite']} games · the outcome of the combat, at the end of that turn", anchor="w",
                      fill=C["muto"], font=F(7, True))
        c.create_text(W - 14, 14, text="click a row: its games as a line on the Chart, against All", anchor="e", fill=C["grigio"], font=F(7))
        col = [("nome", "SITUATION", 14), ("n", "COMBATS", 300), ("partite", "GAMES", 372), ("perdi", "YOU LOST ONE · % combats", 432),
               ("uccidi", "THEY LOST ONE · % combats", 590), ("scambio", "TRADE · per combat", 752), ("danno", "DAMAGE TO " + ("THEM" if att else "YOU") + " · avg", 832),
               ("trucco", "THEIR SPELL · % combats", 975), ("guadagno", "GAIN · avg", 1128), ("wr", "WIN RATE · their games", 1205)]
        y = 34
        # i titoli ordinano le righe (13 nov 2026, Autore: «anche all'elenco decisions diamo i titoli cliccabili per riordinare le colonne»): il primo clic
        # crescente, il secondo al contrario; la riga di tutte resta in cima, come riferimento; un valore che manca va in fondo
        ok_, giu_ = getattr(self, "ord_dec", (None, False))
        for k, t, x in col:
            freccia = (" ↓" if giu_ else " ↑") if k == ok_ else ""
            i_ = c.create_text(x, y, text=t + freccia, anchor="w", fill=C["accento"] if k == ok_ else C["titolo"], font=F(7, True))
            bb = c.bbox(i_)
            c._box.append((bb[0] - 2, bb[1] - 3, bb[2] + 4, bb[3] + 3, ("testa", k)))
        if ok_:
            resto = tab[1:]
            con = [rg for rg in resto if rg.get(ok_) is not None]
            senza = [rg for rg in resto if rg.get(ok_) is None]
            con.sort(key=lambda rg: (str(rg[ok_]).lower() if ok_ == "nome" else rg[ok_]), reverse=giu_)
            tab = tab[:1] + con + senza
        y += 16
        for i, rg in enumerate(tab):
            on = self.linea_dec == (self.dec_modo, rg["nome"])
            fondo = "#0e2238" if on else ("#161b25" if i % 2 == 0 else "#131820")
            c.create_rectangle(8, y, W - 8, y + 24, fill=fondo, outline=C["accento"] if on else "")
            for k, _t, x in col:
                v = rg[k]
                if k == "nome":
                    testo, colr = v + ("   ● on the chart" if on else ""), C["titolo"] if not rg["poche"] else C["muto"]
                elif v is None:
                    testo, colr = "-", C["muto"]
                elif k in ("perdi", "uccidi", "trucco", "wr"):
                    testo = f"{v:.0f}%"
                    base_ = tutte_[k]
                    meglio = (v < base_) if k in ("perdi", "trucco") else (v > base_)
                    colr = C["muto"] if rg["poche"] or i == 0 or base_ is None or abs(v - base_) < 3 else (C["verde"] if meglio else C["rosso"])
                elif k == "scambio":
                    testo, colr = f"{v:+.2f}", (C["muto"] if rg["poche"] else C["verde"] if v > 0 else C["rosso"] if v < 0 else C["testo"])
                elif k == "danno":
                    testo, colr = f"{v:.1f}", C["testo"] if not rg["poche"] else C["muto"]
                elif k == "guadagno":       # il guadagno medio della decisione (vite + 2 x forza), contro quello di tutte
                    base_ = tutte_[k]
                    testo = f"{v:+.1f}"
                    colr = C["muto"] if rg["poche"] or i == 0 or base_ is None or abs(v - base_) < 0.5 else (C["verde"] if v > base_ else C["rosso"])
                else:
                    testo, colr = f"{v}", C["testo"] if not rg["poche"] else C["muto"]
                c.create_text(x, y + 12, text=testo, anchor="w", fill=colr, font=F(8, k == "nome"))
            c._box.append((8, y, W - 8, y + 24, ("riga", rg["nome"])))
            y += 26
        y += 10
        c.create_text(14, y, text=("Blue: better than all your attacks, red: worse (3 points at least); grey: under 10 combats, a hint. Trade: their creatures lost "
                                   "minus yours, per combat." if att else "Blue: better than all their attacks, red: worse; grey: under 10 combats. Trade: their "
                                   "creatures lost minus yours, per combat.") + " Avg gain: how your advantage (life + 2 × power) changed from before damage to "
                                   "the end of the turn; on the Chart, «Gained by decisions» shows these decisions against the average one.", anchor="w",
                      fill=C["muto"], font=F(7))
        c.configure(scrollregion=(0, 0, W, y + 20))

    def disegna_costi(self, c, r, W):
        """R8, le decisioni che ti sono costate di piu' (13 nov 2026, come GTO Wizard): i tuoi attacchi, blocchi e magie coi bersagli nelle partite della
        situazione, col guadagno di vantaggio (vite + 2 × forza) e lo scarto dalla media delle tue decisioni dello stesso tipo nella stessa fase
        (DEC.costi, contro tutte le partite del tipo), dalla piu' costosa; rosso, giallo, verde col numero accanto. Il clic apre il replayer su quel momento."""
        F = self.F
        base = [x for x in self.righe if x["tipo"] == self.tipo]
        cc = DEC.costi(r, base)
        per_p = {x["partita"]: x for x in r}
        n_col = {k: sum(1 for z in cc if z["colore"] == k) for k in COLORI_COSTO}
        c.create_text(14, 14, text=f"THE DECISIONS THAT COST YOU MOST · {len(cc)} decisions in {len({z['partita'] for z in cc})} games · "
                                   f"{n_col['rosso']} red, {n_col['giallo']} yellow, {n_col['verde']} green, {n_col['nd']} not estimable", anchor="w",
                      fill=C["muto"], font=F(7, True))
        c.create_text(W - 14, 14, text="click a row: the replayer on that moment", anchor="e", fill=C["grigio"], font=F(7))
        # R9: il quiz sulle decisioni rosse di queste partite
        n_q = len([z for z in cc if z["colore"] == "rosso" and z["tipo"] in ("attacco", "blocco")])
        if n_q:
            disegna_s3(c, W - 250, 24, W - 14, 48, f"What would you do? · {n_q} spots", F(8, True), tags="quiz", icona=False)
            c._box.append((W - 250, 26, W - 14, 46, ("quiz",)))
        y = 50
        col = ((14, "VS YOUR AVERAGE · pts"), (150, "WIN CHANCE"), (220, "DECISION"), (560, "TURN"), (650, "GAME"))
        for x_, t in col:
            c.create_text(x_, y, text=t, anchor="w", fill=C["titolo"], font=F(7, True))
        y += 16
        for i, z in enumerate(cc[:80]):
            x = per_p.get(z["partita"])
            if x is None:
                continue
            c.create_rectangle(8, y, W - 8, y + 24, fill="#161b25" if i % 2 == 0 else "#131820", outline="")
            colr = COLORI_COSTO[z["colore"]]
            c.create_rectangle(14, y + 5, 26, y + 19, fill=colr, outline="")
            c.create_text(34, y + 12, text="not estimable" if z["costo"] is None else f"{z['costo']:+.1f}", anchor="w", fill=colr, font=F(8, True))
            c.create_text(150, y + 12, text="-" if z.get("guadagno_r8") is None else f"{z['guadagno_r8']:+.1f}%", anchor="w", fill=C["testo"], font=F(8))
            if z["tipo"] == "attacco":
                cosa = f"Attack · {z['attaccanti']} of {z['potevano'] or '?'} creatures · {z['aperte'] if z['aperte'] is not None else '?'} untapped lands against you"
            elif z["tipo"] == "blocco":
                cosa = f"Defense · they attacked with {z['attaccanti']} · you blocked with {z['blocchi']}"
            else:
                cosa = f"Spell · {z['nome']}"
            c.create_text(220, y + 12, text=cosa, anchor="w", fill=C["testo"], font=F(8), width=330)
            mio_t = z["tipo"] != "blocco"
            c.create_text(560, y + 12, text=f"{'Your' if mio_t else 'Their'} T{z['turno']}", anchor="w", fill=C["grigio"], font=F(8))
            c.create_text(650, y + 12, text=f"{x['quando']:%d %b} · {(x.get('mio') or '-').strip()[:22]} vs {(x.get('suo') or '-')[:18]} · {'W' if x['vinta'] else 'L'}",
                          anchor="w", fill=C["grigio"], font=F(8))
            c._box.append((8, y, W - 8, y + 24, ("costo", z["partita"], z["t"], z["tipo"], z.get("nome"))))
            y += 26
        y += 10
        c.create_text(14, y, text=("Win chance: how much your chance to win changed from the decision to the next moment (for a spell, its answer too), read "
                                   "from the table (life, creatures, lands, cards in hand) by our win-probability model, trained on 17Lands public replay data "
                                   "(CC BY 4.0, 17lands.com/public_datasets) from six limited sets: in constructed it is a stretch, it compares two tables. "
                                   "Against the average of your decisions of the same kind in the same part of the game: red 7+ points worse, yellow 3.5+, "
                                   "green the rest. A clue, not a verdict."), anchor="nw", fill=C["grigio"], font=F(7), width=W - 30)
        c.configure(scrollregion=(0, 0, W, y + 40))

    def disegna_leaks(self):
        """La cartella Leaks del Leak Finder (15 nov 2026): il leak tracker sulle partite della situazione, i leak dal piu' costoso."""
        c = self.tela("leaks")
        c.delete("all")
        c._box = []
        if self.righe is None:
            return
        self.disegna_leak(c, self.scelte(), max(c.winfo_width(), 700))

    def disegna_leak(self, c, r, W):
        """R10, il leak tracker (13 nov 2026, come PokerTracker): ogni leak nelle partite della situazione: in quante partite, il win rate con e senza e la
        differenza, il trend (ultime 50 partite contro quelle prima: verde se scende), e come si corregge. Il clic su una riga la mette fra i filtri (di nuovo
        la toglie), «Watch ›» apre le sue partite nel replayer sul leak, una dopo l'altra. La popolazione non c'e' (servono i dati condivisi)."""
        import leak as LK
        F = self.F
        tr = LK.tracker(r)
        n = tr[0]["n"] if tr else 0
        # il costo (15 nov 2026, il Leak Finder): quanto win rate ti toglie in tutto, nel formato che guardi = quanto spesso capita x quanto costa quando capita;
        # dal piu' costoso, sotto 10 partite in fondo (un indizio). Cosi' il peso di ogni leak viene dai dati di Limited o di Constructed, non da una regola fissa
        # il costo in EV (18 nov 2026, Autore: «la scheda leaks e' effettivamente ancora utile visto il nuovo modo di ragionare in ev?», «Si', tutte e
        # tre»): quanti punti di probabilita' di vincere il leak ti toglie in media a partita (ev_partita.costo_leak), non piu' il win rate. Tre gruppi: i
        # leak che le tue partite confermano, dal piu' costoso; quelli non ancora decisi; le scelte che funzionano (i turni col «leak» rendono di piu': nelle
        # tue partite non e' un errore); in fondo quelli mai successi
        import ev_partita as EV_
        cl = EV_.costo_leak(r, [x for x in self.righe if x["tipo"] == self.tipo])

        def gruppo(t):
            e_ = cl.get(t["k"])
            if not t["con"] or not e_:
                return 3
            return {"confermato": 0, "contrario": 2}.get(e_["verdetto"], 1)
        tr.sort(key=lambda t: (gruppo(t), -((cl.get(t["k"]) or {}).get("costo") or -99)))
        c.create_text(14, 14, text=f"YOUR HABITS · {self.tipo.upper()}{self.nome_mazzo_habits()} · what we can spot in the replays of your {n} games, weighed in EV",
                      anchor="w", fill=C["muto"], font=F(8, True))
        c.create_text(14, 32, text=("A habit is something you do again and again, read from the replay: a land you kept in hand, mana left open, a concession. EV judges "
                                    "it: the turns with it against your other turns, in win-probability points per game. When those turns go worse, it is costing "
                                    "you EV: a leak, most likely, though the situation may have forced it. When they go better, it works for you. Click a habit to "
                                    "keep only the games where it happened (again to see all); Watch › opens them in the replayer, right on the moment."),
                      anchor="nw", fill=C["grigio"], font=F(7), width=W - 30)
        y = 66
        LX = 120        # le etichette a sinistra, il testo da LX in poi
        TITOLI = {0: ("COSTING YOU EV · the turns with them go worse than your others, beyond chance: the likely leaks", C["rosso"]),
                  1: ("NOT DECIDED YET · too close to call, or too few turns", C["grigio"]),
                  2: ("WORKING FOR YOU · the turns with them go better than your others: in your games they are not mistakes", C["verde"]),
                  3: ("NEVER HAPPENED IN THESE GAMES", C["muto"])}
        gr_prima = None
        for i, t in enumerate(tr):
            on = self.filtri.get(f"leak_{t['k']}") == "Yes"
            e_ = cl.get(t["k"])
            gr_ = gruppo(t)
            if gr_ != gr_prima:
                y += 4
                c.create_text(14, y + 8, text=TITOLI[gr_][0], anchor="w", fill=TITOLI[gr_][1], font=F(8, True))
                c.create_line(14, y + 20, W - 14, y + 20, fill="#252b36")
                y += 28
                gr_prima = gr_
            co_ = (e_ or {}).get("costo")
            sfondo = c.create_rectangle(8, y, W - 8, y + 10, fill="#161b25" if i % 2 == 0 else "#131820", outline=C["accento"] if on else "")
            c.create_text(18, y + 16, text=t["nome"], anchor="w", fill=C["titolo"], font=F(11, True), width=W - 330)
            # il costo in EV, in parole, in alto a destra
            if not t["con"]:
                badge, col_b = "never happened", C["verde"]
            elif not e_ or co_ is None:
                badge, col_b = "too few turns to say", C["muto"]
            elif gr_ == 0:
                badge, col_b = f"costs you {co_:.1f} EV pts a game", C["rosso"]
            elif gr_ == 2:
                badge, col_b = f"works for you: {-co_:+.1f} EV pts a game", C["azzurro"]
            else:
                badge, col_b = f"not decided · {-co_:+.1f} EV pts a game?", C["muto"]
            c.create_text(W - 136, y + 16, text=badge, anchor="e", fill=col_b, font=F(9, True))
            # cosa e' successo nelle tue partite, in una frase
            if not t["con"]:
                fatto = f"It never happened in your {n} games. Nice."
            else:
                fatto = f"It happened in {t['con']} of your {n} games ({t['tasso']:.0f}%)"
                if e_ and e_["livello"] == "turno":
                    fatto += f", in {e_['n']} turn{'s' * (e_['n'] != 1)}"
                fatto += "."
                if e_ and e_.get("diff") is not None:
                    quando = "time" if e_["livello"] == "turno" else "game"
                    fatto += (f" Each {quando} it {'costs' if e_['diff'] < 0 else 'gives'} about {abs(e_['diff']):.1f} win-probability points against your "
                              f"other {quando}s; across your games about {abs(co_):.1f} points a game.")
                if t["tasso_rec"] is not None and t["tasso_prima"] is not None:
                    if t["tasso_rec"] < t["tasso_prima"]:
                        fatto += f" Getting better: {t['tasso_rec']:.0f}% of your last 50 games, {t['tasso_prima']:.0f}% before."
                    elif t["tasso_rec"] > t["tasso_prima"]:
                        fatto += f" Getting worse: {t['tasso_rec']:.0f}% of your last 50 games, {t['tasso_prima']:.0f}% before."
            yy = y + 34
            i_f = c.create_text(18, yy, text=fatto, anchor="nw", fill=C["testo"], font=F(8, True), width=W - 160)
            yy = c.bbox(i_f)[3] + 8
            altri, col_altri = self.confronto_leak(t["k"], t["tasso"] if t["con"] else 0.0)
            if e_:
                cosa_ = "turns" if e_["livello"] == "turno" else "games"
                ev_t = (f"The {e_['n']} {cosa_[:-1] if e_['n'] == 1 else cosa_} with this habit gave {e_['scarto']:+.1f} win-probability points against what the "
                        f"same {cosa_} usually give" + (f"; your other {cosa_} {e_['altri']:+.1f}." if e_["altri"] is not None else ".")
                        + (f" A hint: under {EV_.MINIMO} {cosa_}." if e_["n"] < EV_.MINIMO else ""))
                ver_ = e_.get("verdetto")
                if ver_ == "confermato":
                    ev_t += f" CONFIRMED by your games: {e_['diff']:+.1f} points (±{2 * e_['err']:.1f})."
                elif ver_ == "contrario":
                    ev_t += (f" NOT CONFIRMED: {e_['diff']:+.1f} points better than your others (±{2 * e_['err']:.1f}); in your games it is a choice, not a "
                             "mistake.")
                elif e_["n"] >= EV_.MINIMO and e_.get("diff") is not None:
                    ev_t += f" Not decided yet: {e_['diff']:+.1f} points, within the noise (±{2 * e_['err']:.1f})."
                if e_["livello"] == "partita" and t["k"] == "l7":
                    ev_t += " A concession comes when the game is already going badly: its games are low by nature, read this one as a clue."
                col_ev = (C["muto"] if e_["n"] < EV_.MINIMO else C["rosso"] if ver_ == "confermato" else C["verde"] if ver_ == "contrario"
                          else C["rosso"] if e_["scarto"] <= -1 else C["verde"] if e_["scarto"] >= 1 else C["testo"])
            elif t["con"]:
                ev_t, col_ev = "No turn-by-turn data for these games yet.", C["grigio"]
            else:
                ev_t, col_ev = "-", C["grigio"]
            motore_ = None
            if self.tipo == "Limited" and t["con"]:     # il giudice del motore di partita (21 nov 2026, il leaker intelligente, passo 3)
                try:
                    import leak as LK_
                    g_ = LK_.giudice_motore(r, t["k"])
                    motore_ = LK_.testo_motore(g_)
                    col_m = (C["rosso"] if g_["meglio"] > g_["stessa"] + g_["pari"] else C["verde"] if g_["stessa"] > g_["meglio"] + g_["pari"]
                             else C["testo"]) if motore_ else None
                except Exception:       # noqa: BLE001 - senza il motore la riga non c'e'
                    motore_ = None
            righe_l = [("EV IN THOSE TURNS", ev_t, col_ev), ("OTHER PLAYERS", altri, col_altri)]
            if motore_:
                righe_l.append(("THE GAME ENGINE", motore_, col_m))
            for etichetta, testo, colore in (*righe_l, ("WHAT IT IS", t["spiega"], C["testo"]),
                                              ("WHY IT COSTS", t["perche"], C["testo"]), ("EXAMPLE", t["esempio"], C["grigio"]),
                                              ("HOW TO FIX", t["come"], "#e8d28a")):
                c.create_text(18, yy, text=etichetta, anchor="nw", fill=C["azzurro"] if etichetta != "HOW TO FIX" else "#e8d28a", font=F(7, True))
                i_t = c.create_text(LX, yy, text=testo, anchor="nw", fill=colore, font=F(8), width=W - LX - 150)
                yy = c.bbox(i_t)[3] + 5
            alto = yy + 6 - y
            c.coords(sfondo, 8, y, W - 8, y + alto)
            c._box.append((8, y, W - 130, y + alto, ("leak", t["k"])))
            if t["con"]:
                disegna_s3(c, W - 120, y + 30, W - 16, y + 54, "Watch ›", F(8, True), icona="play")
                c._box.append((W - 120, y + 30, W - 16, y + 54, ("guarda_leak", t["k"])))
            y += alto + 6
        y += 8
        y = self.disegna_linee(c, W, y)
        c.create_text(14, y, text=("How the cost is counted: each turn has its EV, the win-probability points it made above or below what the same turn usually "
                                   "gives (the model of the chance to win, from the replays). A leak's turns are compared with your other turns (the whole game "
                                   "for the mulligan and the concession): the difference each time, times how often it happens, over your games. Confirmed = "
                                   f"beyond twice its error; under {EV_.MINIMO} turns only a hint."), anchor="nw", fill=C["grigio"], font=F(7), width=W - 30)
        import leak_17lands as L17
        d17 = L17.carica()
        if self.tipo == "Limited" and d17:
            y += 40
            c.create_text(14, y, text=(f"Other players: {d17['fonte']}, {d17['gruppi']['tutti']['partite']:,} games read on {d17['data']} (Mythic: the players "
                                       "ranked Mythic). Their data has the same turns as yours but not which lands were tapped or the phase of each spell, so 7 "
                                       "habits of 15 can be measured there; a «close rule» says what changes. Not endorsed by 17Lands."),
                          anchor="nw", fill=C["grigio"], font=F(7), width=W - 30)
        c.configure(scrollregion=(0, 0, W, y + 60))

    LINEE_EN = {"panico": "PANIC", "freddezza": "COLD HEAD", "inganno": "DECEPTION", "speranza": "HOPE", "strategia": "STRATEGY"}

    def linee_spot(self):
        """Gli spot delle linee psicologiche (psicologia.con_finestra) delle partite del tipo, una volta per lettura delle partite (~2,5 s)."""
        k_ = (self.tipo, id(self.righe))
        if getattr(self, "_linee_k", None) != k_:
            import psicologia as PS
            r = [x for x in self.righe or [] if x.get("seat") in (1, 2) and x["tipo"] == self.tipo]
            try:
                self._linee = (r, PS.con_finestra(r, r))
            except Exception:       # noqa: BLE001 - senza le foto delle partite il profilo non c'e'
                self._linee = (r, [])
            self._linee_k = k_
        return self._linee

    def disegna_linee(self, c, W, y):
        """Il profilo psicologico del mazzo scelto (21 nov 2026, Autore: «montiamo ogni miglioria apportata sul motore», Replayer + Leak Finder;
        profilo_giocatore.py, Note/UpgradePlan01_Profilo.md): sotto pressione e da tranquillo, quanto spesso fai ogni linea con questo mazzo contro i tuoi
        altri mazzi e quanto ti rende con lui (la finestra del tuo turno e del suo dopo, contro il solito del mazzo). Solo con un mazzo in Choose your deck."""
        import psicologia as PS
        import profilo_giocatore as PG
        F = self.F
        mio = self.filtri.get("mio")
        c.create_rectangle(12, y + 1, 14, y + 15, fill=C["accento"], outline="")
        c.create_text(19, y, text="YOUR LINES WITH THIS DECK · under pressure and calm", anchor="nw", fill=C["titolo"], font=F(9, True))
        y += 20
        if not mio:
            c.create_text(19, y, text="Choose a deck in Choose your deck: the profile compares how you play it with how you play your other decks.",
                          anchor="nw", fill=C["grigio"], font=F(7), width=W - 40)
            return y + 34
        r, S = self.linee_spot()
        chiavi = {DA.chiave_mazzo(x) for x in r if x.get("mio") == mio}
        m = next(iter(chiavi), None)
        n_p = sum(1 for x in r if DA.chiave_mazzo(x) == m)
        if m is None or n_p < PG.MINIMO_PARTITE or not any(s_["mazzo"] == m for s_ in S):
            c.create_text(19, y, text=f"Under {PG.MINIMO_PARTITE} games with this deck: no profile yet.", anchor="nw", fill=C["grigio"], font=F(7))
            return y + 30
        P = PG.profilo(S, m)
        segno = lambda v: f"{v:+.1f}".replace("-", "−")
        for stato, nome in PG.STATI:
            q = P[stato]
            if not q["n"]:
                continue
            spr = "" if q["spremuto"] is None else f" · squeezes {segno(q['spremuto'])} ±{q['es']:.1f} vs your other decks"
            c.create_text(19, y, text=f"{nome.upper()} · {q['n']} Hero turns{spr}", anchor="nw", fill=C["testo"], font=F(8, True))
            y += 18
            for col_x, tit in ((19, "LINE"), (W - 330, "WITH THIS DECK"), (W - 210, "OTHER DECKS"), (W - 90, "WORTH")):
                c.create_text(col_x, y, text=tit, anchor="nw", fill=C["muto"], font=F(6, True))
            y += 14
            for k, v in q["linee"].items():
                if not v["volte"]:
                    continue
                forte = v["z"] is not None and abs(v["z"]) > PG.Z_FORTE
                c.create_text(19, y, text=f"{self.LINEE_EN.get(PS.LINEE[k], PS.LINEE[k])} · {PS.NOMI[k]}", anchor="nw",
                              fill=C["testo"] if forte else C["muto"], font=F(7, forte), width=W - 360)
                c.create_text(W - 330, y, text=f"{100 * v['quota']:.1f}%", anchor="nw", fill=C["arancio"] if forte else C["testo"], font=F(7, True))
                c.create_text(W - 210, y, text=f"{100 * v['quota_altri']:.1f}%", anchor="nw", fill=C["muto"], font=F(7))
                if v["prezzo"] is not None:
                    c.create_text(W - 90, y, text=segno(v["prezzo"]), anchor="nw",
                                  fill=C["verde"] if v["prezzo"] > 0 else C["rosso"], font=F(7, True))
                else:
                    c.create_text(W - 90, y, text="few", anchor="nw", fill=C["grigio"], font=F(7))
                y += 16
            y += 8
        c.create_text(19, y, text=("Orange: you do it with this deck much more or much less than with your other decks (beyond twice its error). Worth: "
                                   "win-probability points of your turn and the Opponent's next one with the line against without it, with this deck and in "
                                   "this state. Under pressure = your chance to win under 30% or the Opponent kills you within 2 turns. Some lines are "
                                   "partly read from what came after (chump, trap, bluff)."), anchor="nw", fill=C["grigio"], font=F(7), width=W - 40)
        return y + 52

    def confronto_leak(self, k, tuo):
        """La riga OTHER PLAYERS di un leak (15 nov 2026, Autore: «aggiungi il confronto»): nel Limited quanto spesso succede ai giocatori di 17Lands
        (tutti e Mythic) contro te; nel Constructed non ci sono replay pubblici. -> (testo, colore)."""
        import leak_17lands as L17
        if self.tipo != "Limited":
            return ("No public replays exist for Constructed: the comparison comes with the games shared by the app's users.", C["grigio"])
        d17 = L17.carica()
        if not d17:
            return ("The 17Lands comparison file is missing.", C["grigio"])
        if k not in d17.get("regole", {}):
            return ("Not measurable on 17Lands: their data doesn't say which lands were tapped or in which phase each spell was cast.", C["grigio"])
        tutti = d17["gruppi"]["tutti"]["leak"].get(k) or {}
        myth = (d17["gruppi"].get("mythic") or {}).get("leak", {}).get(k) or {}
        loro = tutti.get("tasso")
        if loro is None:
            return ("No number from 17Lands for this habit.", C["grigio"])
        testo = f"17Lands players: in {loro:.0f}% of their games" + (f" (Mythic players {myth['tasso']:.0f}%)" if myth.get("tasso") is not None else "")
        testo += f"; you: {tuo:.0f}%."
        if loro > 0 and tuo > 0:
            volte = tuo / loro
            testo += (f" You do it {volte:.1f} times as often." if volte >= 1.25 else f" You do it less often ({volte:.1f}×)." if volte <= 0.8
                      else " About the same.")
        elif tuo == 0 and loro > 0:
            testo += " You never do it."
        if tutti.get("wr_con") is not None and tutti.get("wr_senza") is not None:
            testo += f" They win {tutti['wr_con']:.0f}% of the games with it and {tutti['wr_senza']:.0f}% without."
        regola = (d17.get("regole") or {}).get(k) or ["same", ""]
        if regola[0] == "close":
            testo += f" Close rule: {regola[1]}."
        colore = C["rosso"] if loro > 0 and tuo >= 1.25 * loro else C["verde"] if tuo <= 0.8 * loro else C["testo"]
        return testo, colore

    def disegna_cimitero(self, c, r, W):
        """Cimitero ed esilio in Decisions (14 nov 2026, Autore: «ok fai i filtri per la decisione»): ogni situazione nelle partite scelte, in quante,
        il win rate con e senza, la differenza; il clic la mette fra i filtri (di nuovo la toglie). Grado C, dal testo delle carte: misurate sui log del 13 nov,
        nessuna predice le vittorie oltre al vantaggio, quindi non pesano nel costo delle decisioni."""
        import cimitero as CM
        F = self.F
        tr = CM.tracker(r)
        n = tr[0]["n"] if tr else 0
        c.create_text(14, 14, text=f"GRAVEYARD AND EXILE · {n} games with the moments · from the card text, clues not verdicts", anchor="w", fill=C["muto"],
                      font=F(7, True))
        c.create_text(W - 14, 14, text="click a row: only its games (again: all)", anchor="e", fill=C["grigio"], font=F(7))
        y = 34
        for x_, t in ((14, "SITUATION"), (420, "GAMES"), (510, "WIN RATE WITH"), (620, "WITHOUT"), (710, "DIFFERENCE")):
            c.create_text(x_, y, text=t, anchor="w", fill=C["titolo"], font=F(7, True))
        y += 16
        wr_ = lambda v: "-" if v is None else f"{v:.0f}%"
        for i, t in enumerate(tr):
            on = self.filtri.get(t["k"]) in t["si"]
            c.create_rectangle(8, y, W - 8, y + 26, fill="#161b25" if i % 2 == 0 else "#131820", outline=C["accento"] if on else "")
            c.create_text(14, y + 13, text=t["nome"], anchor="w", fill=C["titolo"], font=F(8, True), width=400)
            c.create_text(420, y + 13, text=f"{t['con']} · {t['tasso']:.0f}%" if t["tasso"] is not None else "-", anchor="w", fill=C["testo"], font=F(8, True))
            c.create_text(510, y + 13, text=wr_(t["wr_con"]), anchor="w", fill=C["testo"], font=F(8))
            c.create_text(620, y + 13, text=wr_(t["wr_senza"]), anchor="w", fill=C["testo"], font=F(8))
            poche = t["con"] < 10
            col_d = C["muto"] if poche or t["delta"] is None else (C["rosso"] if t["delta"] < 0 else C["verde"])
            c.create_text(710, y + 13, text="-" if t["delta"] is None else f"{t['delta']:+.0f} pts" + (" · few" if poche else ""), anchor="w", fill=col_d,
                          font=F(8, True))
            c._box.append((8, y, W - 8, y + 26, ("cimitero", t["k"], t["si"][0])))
            y += 28
        y += 8
        c.create_text(14, y, text=("A reanimation ready: a card in your hand or on the battlefield (theirs: battlefield only) that returns a creature from a "
                                   "graveyard to the battlefield, with a creature in that graveyard. Playable from exile: foretell, plot, warp, suspend, an "
                                   "adventure (impulse draw is not seen). Exiled from a graveyard: cards that left it for exile during that player's turn "
                                   "(on their own turn it can be their escape or delve). Measured on your games: none of these predicts wins beyond life and "
                                   "power on the battlefield, so they carry no weight in the decision cost; here you see what they meant for you."),
                      anchor="nw", fill=C["grigio"], font=F(7), width=W - 30)
        c.configure(scrollregion=(0, 0, W, y + 60))

    def testo_partita(self, html=False):
        """R2: la partita aperta nel replayer, momento per momento coi suoi fatti, come testo o pagina web. Niente nomi ne' id dell'account: «You», «Opponent»,
        i mazzi e un codice di partita pseudonimo (condividi.codice, lo stesso dei dati condivisi)."""
        import condividi
        import html as H
        b = self._board
        x_ = b["x"]
        passi_ora = b["passi"]
        passi = b["passi"] = b.get("momenti_passi") or passi_ora     # sempre i momenti, senza cambiare il modo a video
        testa = [f"{x_['quando']:%d %b %Y %H:%M} · {(x_.get('mio') or '-').strip()} vs {x_.get('suo') or '-'} · {'won' if x_['vinta'] else 'lost'}"
                 + (f" on turn {x_['turno']}" if x_.get("turno") else "") + (f" · {x_['partenza'].lower()}" if x_.get("partenza") else ""),
                 f"Game code {condividi.codice(x_.get('partita') or '?')} · exported from 3 Steps Ahead"]
        blocchi = []
        for i, p_ in enumerate(passi):
            try:
                righe = [t for _m, t in (self.racconto(i) or []) if t]
            except Exception:       # noqa: BLE001 - un momento che non si racconta non ferma l'esportazione
                righe = []
            f = p_[1] or {}
            v = f.get("vite") or (None, None)
            blocchi.append((p_[0], f"life you {v[0]} · opponent {v[1]}", righe))
        b["passi"] = passi_ora
        nota = DA.nota_partita(x_.get("partita"))
        if not html:
            out = testa + ([f"Note: {nota}"] if nota else []) + [""]
            for nome, vite, righe in blocchi:
                out += [f"{nome}  ({vite})"] + [f"  - {r_}" for r_ in righe] + [""]
            return "\n".join(out)
        e = H.escape
        corpo = "".join(f"<h3>{e(nome)} <small>{e(vite)}</small></h3><ul>" + "".join(f"<li>{e(r_)}</li>" for r_ in righe) + "</ul>" for nome, vite, righe in blocchi)
        return ("<!doctype html><html><head><meta charset='utf-8'><title>3 Steps Ahead · game</title><style>body{background:#0b0e14;color:#d7dce5;"
                "font-family:Segoe UI,sans-serif;max-width:860px;margin:24px auto;padding:0 16px}h1{color:#fff;font-size:20px}h3{color:#fff;margin:18px 0 4px;"
                "font-size:14px}small{color:#7a7a80;font-weight:normal}li{margin:2px 0}.c{color:#7a7a80}</style></head><body>"
                f"<h1>{e(testa[0])}</h1><p class='c'>{e(testa[1])}</p>" + (f"<p>Note: {e(nota)}</p>" if nota else "") + corpo + "</body></html>")

    def menu_esporta(self):
        """Il menu di Export: la partita come testo, come pagina web, lo spot come immagine."""
        tk = self.tk
        m = tk.Menu(self.fin_board, tearoff=0, bg=C["scheda"], fg=C["titolo"], activebackground="#0f86cc", activeforeground="#ffffff")
        m.add_command(label="Game as text (.txt)", command=lambda: self.esporta("txt"))
        m.add_command(label="Game as web page (.html)", command=lambda: self.esporta("html"))
        m.add_command(label="This spot as image (.png)", command=lambda: self.esporta("png"))
        try:
            m.tk_popup(self.b_esporta.winfo_rootx(), self.b_esporta.winfo_rooty() + self.b_esporta.winfo_height())
        finally:
            m.grab_release()
        return m

    def esporta(self, cosa, file=None):
        """Scrive l'esportazione: file None chiede dove (la finestra di Windows). L'immagine e' la tavola com'e' sullo schermo (R17). -> il file o None."""
        b = getattr(self, "_board", None)
        if not b:
            return None
        if file is None:
            from tkinter import filedialog
            file = filedialog.asksaveasfilename(parent=self.fin_board, defaultextension="." + cosa, initialfile=f"3StepsAhead_{b['x']['quando']:%Y%m%d_%H%M}.{cosa}",
                                                filetypes=[(cosa.upper(), "*." + cosa)])
            if not file:
                return None
        if cosa == "png":
            import piattaforma
            im = piattaforma.foto_finestra(self.cv_board)      # la tavola com'e' disegnata, mai lo schermo (Arena o altro sopra)
            if im is None:
                return None
            im.save(file)
        else:
            with open(file, "w", encoding="utf-8") as g:
                g.write(self.testo_partita(html=cosa == "html"))
        return file

    # (titolo, riga, giocate intorno, campo intero): la prima e' la foto larga (misurata: con tutto il campo quasi sempre solo la partita da cui vieni)
    INTORNO = (("Start, creatures and lands", "Play or draw and mulligans; Hero's and Opponent's creatures and lands at the start of this turn", None, False),
               ("+ what was cast this turn", "The Hero's and the Opponent's spells this turn, by role", 0, False),
               ("+ one turn before and after", "The spells of the turn before and the turn after too", 1, False),
               ("+ the whole board", "Also hands, life, other permanents, the graveyard and the lands in the opening hand", None, True))

    def menu_momento(self):
        """Il menu del pulsante «Filters from here»: quanto della partita intorno a questo momento entra nei filtri."""
        import menu_board as MB
        b = getattr(self, "_board", None)
        if not b:
            return None
        m = MB.Menu(self.tk, self.F, self.fin_board, "Filters from this moment", larga=340)
        m.sezione("Fill Advanced filters with this moment")
        T = b["passi"][b["i"]][2]
        tutte = [x_ for x_ in self.righe or [] if x_["tipo"] == self.tipo]
        for titolo, riga, k, tutto in self.INTORNO:
            f_ = DA.filtri_momento(b["x"], T, k, tutto)
            n_ = sum(1 for x_ in tutte if DA.passa(x_, f_))      # quante partite simili, accanto: si sceglie sapendo quante ne restano
            m.voce(titolo, riga, lambda k=k, tutto=tutto: self.filtri_dal_momento(k, tutto), destra=f"{n_} games")
        m.posa(sotto=self.b_momento)
        self._menu_momento = m
        return m

    def filtri_dal_momento(self, intorno=None, tutto=False):
        """I filtri di questo momento del replay al posto di quelli di prima (DA.filtri_momento), e Advanced filters aperta sul Board dell'Hero: ogni pezzo e'
        un filtro con la sua x, da togliere per allargare. -> i filtri messi."""
        b = getattr(self, "_board", None)
        if not b:
            return {}
        T = b["passi"][b["i"]][2]
        nuovi = DA.filtri_momento(b["x"], T, intorno, tutto)
        self.filtri = dict(nuovi)
        self._righe_ui = {}
        self.disegna()
        j = next(j_ for j_, (n_, _s) in enumerate(AVANZATI["io"]) if n_ == "Board")
        self.apri_avanzati("io", j, 0)
        return nuovi

    def apri_nota_board(self):
        """R3: la nota sulla partita aperta nel replayer, e sullo spot se e' segnato: una finestrella con le due caselle, Save e Delete."""
        tk, F = self.tk, self.F
        b = getattr(self, "_board", None)
        if not b:
            return None
        pid, modo, i = b["x"].get("partita"), b.get("modo", "momenti"), b["i"]
        f = getattr(self, "fin_nota", None)
        if f is not None and f.winfo_exists():
            f.destroy()
        f = self.fin_nota = tk.Toplevel(self.fin_board)
        f.title("The board · note")
        f.configure(bg=C["scheda"])
        try:
            from tema import barra_scura
            f.after(60, lambda f=f: f.winfo_exists() and barra_scura(f, C["testa"], C["titolo"], C["filo"]))
        except Exception:      # noqa: BLE001
            pass
        f.transient(self.fin_board)
        caselle = {}
        voci = [("partita", "YOUR NOTE ON THIS GAME", DA.nota_partita(pid))]
        sn = DA.nota_segnalibro(pid, modo, i)
        if sn is not None:
            voci.append(("spot", "YOUR NOTE ON THIS BOOKMARKED SPOT", sn))
        for k, tit, testo in voci:
            tk.Label(f, text=tit, bg=C["scheda"], fg=C["muto"], font=F(7, True), anchor="w").pack(fill="x", padx=14, pady=(12, 4))
            t = tk.Text(f, height=5, width=60, bg=C["fondo"], fg=C["titolo"], insertbackground=C["titolo"], relief="flat", font=F(9), wrap="word")
            t.insert("1.0", testo or "")
            t.pack(fill="x", padx=14)
            caselle[k] = t
        if sn is None:
            tk.Label(f, text="Bookmark this spot (B) to write a note on it too.", bg=C["scheda"], fg=C["grigio"], font=F(8), anchor="w").pack(fill="x", padx=14, pady=(6, 0))
        riga = tk.Frame(f, bg=C["scheda"]); riga.pack(fill="x", padx=14, pady=12)

        def salva(cancella=False):
            DA.salva_nota_partita(pid, "" if cancella else caselle["partita"].get("1.0", "end"))
            if "spot" in caselle:
                DA.nota_segnalibro(pid, modo, i, "" if cancella else caselle["spot"].get("1.0", "end"))
            f.destroy()
            self.disegna_board()
            if "mine" in self.visibili():
                self.disegna_miei()
        b1 = pulsante_solido(tk, F, riga, "Save", False, salva, alto=30, bg=C["scheda"]); b1.configure(width=110); b1.pack(side="left")
        b2 = pulsante_solido(tk, F, riga, "Delete", False, lambda: salva(True), alto=30, bg=C["scheda"], colori=("#303034", "#3c3c42", "#26262a"))
        b2.configure(width=110); b2.pack(side="left", padx=8)
        f.bind("<Escape>", lambda e: f.destroy())
        f.salva = salva
        f.caselle = caselle
        caselle["partita"].focus_set()
        return f

    def apri_quiz(self):
        """R9, «cosa faresti qui?» (13 nov 2026, come chess.com e lichess, «impara dai tuoi errori»): le tue decisioni rosse (attacchi e difese) delle partite
        della situazione, una alla volta. La situazione prima della decisione (vite, il campo, le sue terre aperte, le carte in mano; «See the board» apre
        il replayer sul momento prima), scegli; poi cosa hai fatto davvero, quanto ti e' costato, e quanto ha reso ogni scelta nelle tue partite in quella
        fase (DEC.medie_opzioni). Le magie no: «tenerla» non ha un dato da confrontare."""
        tk, F = self.tk, self.F
        base = [x for x in self.righe if x["tipo"] == self.tipo]
        self._quiz = dict(voci=[z for z in DEC.costi(self.scelte(), base) if z["colore"] == "rosso" and z["tipo"] in ("attacco", "blocco")], i=0, scelta=None,
                          base=base, giuste=0, fatte=0)
        if not self._quiz["voci"]:
            return None
        f = getattr(self, "fin_quiz", None)
        if f is None or not f.winfo_exists():
            f = self.fin_quiz = tk.Toplevel(self.fr)
            f.title("Leak Finder · What would you do?")
            f.configure(bg=C["scheda"])
            try:
                from tema import barra_scura
                f.after(60, lambda f=f: f.winfo_exists() and barra_scura(f, C["testa"], C["titolo"], C["filo"]))      # a finestra comparsa
            except Exception:      # noqa: BLE001
                pass
            f.geometry("760x560"); f.update_idletasks()
            f.bind("<Escape>", lambda e: f.destroy())
            self.cv_quiz = tk.Canvas(f, bg=C["scheda"], highlightthickness=0, bd=0)
            self.cv_quiz.pack(fill="both", expand=True)
            self.cv_quiz.bind("<Configure>", lambda e: self.disegna_quiz())
            self.cv_quiz.bind("<Button-1>", self.clic_quiz)
        self.disegna_quiz()
        f.lift()
        return f

    def disegna_quiz(self):
        c = getattr(self, "cv_quiz", None)
        q = getattr(self, "_quiz", None)
        if c is None or not c.winfo_exists() or not q:
            return
        F = self.F
        c.delete("all")
        c._box = []
        W = max(c.winfo_width(), 600)
        z = q["voci"][q["i"]]
        x_ = next((x for x in self.righe if x["partita"] == z["partita"]), {})
        d = DA._MANA.get(z["partita"]) or {}
        seat = x_.get("seat") or 1
        m = next((m_ for m_ in d.get("momenti") or [] if m_[0] == "comb" and m_[1] == z["t"]), None)
        prima = m[3] if m and isinstance(m[3], dict) else {}
        a, b = seat - 1, 2 - seat
        att = z["tipo"] == "attacco"
        c.create_text(16, 18, text=f"WHAT WOULD YOU DO? · {q['i'] + 1} of {len(q['voci'])}" + (f" · {q['giuste']} of {q['fatte']} like your best line" if q["fatte"] else ""),
                      anchor="w", fill=C["azzurro"], font=F(9, True))
        c.create_text(W - 16, 18, text=f"{x_.get('quando'):%d %b} · {(x_.get('mio') or '-').strip()[:24]} vs {(x_.get('suo') or '-')[:20]}" if x_ else "",
                      anchor="e", fill=C["grigio"], font=F(8))
        c.create_text(16, 48, text=(f"Your turn {z['turno']} · you are about to attack" if att else f"Their turn {z['turno']} · they attack with {z['attaccanti']}"),
                      anchor="w", fill=C["titolo"], font=F(13, True))
        forza = lambda lato: sum(max(0, cc_[3] or 0) for cc_ in lato or [] if len(cc_) > 3 and cc_[3] is not None)
        terre_ap = lambda lato: sum(1 for cc_ in lato or [] if not cc_[1] and DA.e_terra(DA.nome_grp(cc_[0]) or "")) if lato else 0
        cl_ = prima.get("c") or [[], []]
        vv = prima.get("v") or [None, None]
        righe = [("Life", f"you {vv[a]} · opponent {vv[b]}"),
                 ("Battlefield", f"you {sum(1 for cc_ in cl_[a] if cc_[3] is not None)} creatures, power {forza(cl_[a])} · opponent "
                                 f"{sum(1 for cc_ in cl_[b] if cc_[3] is not None)} creatures, power {forza(cl_[b])}"),
                 ("Their untapped lands", str(z.get("aperte") if att and z.get("aperte") is not None else terre_ap(cl_[b]))),
                 ("Cards in hand", f"you {len((prima.get('m') or [[], []])[a])} · opponent {(prima.get('n') or [0, 0])[b]}")]
        y = 84
        for k, v in righe:
            c.create_text(16, y, text=k.upper(), anchor="w", fill=C["muto"], font=F(7, True))
            c.create_text(190, y, text=v, anchor="w", fill=C["testo"], font=F(9))
            y += 24
        c.create_rectangle(16, y + 4, 176, y + 28, fill="#1e2431", outline="")
        c.create_text(96, y + 16, text="See the board ›", fill="#ffffff", font=F(8, True))
        c._box.append((16, y + 4, 176, y + 28, ("vedi",)))
        y += 48
        opz = DEC.OPZIONI[z["tipo"]]
        if q["scelta"] is None:
            c.create_text(16, y, text="YOUR CHOICE", anchor="w", fill=C["muto"], font=F(7, True))
            y += 16
            xb = 16
            for k, n in opz:
                disegna_s3(c, xb, y, xb + 210, y + 34, n, F(9, True), icona=False)
                c._box.append((xb, y, xb + 210, y + 34, ("scegli", k)))
                xb += 222
            return
        # la risposta: cosa hai fatto, quanto e' costato, quanto ha reso ogni scelta nelle tue partite in quella fase
        fatta = DEC.scelta_fatta(z)
        medie = DEC.medie_opzioni(q["base"], z["tipo"], DEC._fascia_turno(z["turno"]))
        nomi = dict(opz)
        c.create_text(16, y, text=f"You chose: {nomi[q['scelta']]}", anchor="w", fill=C["titolo"], font=F(10, True))
        y += 24
        c.create_text(16, y, text=f"In the game you did: {nomi[fatta]} · gain {z['guadagno']:+.0f} · {z['costo']:+.1f} vs your average", anchor="w",
                      fill=COLORI_COSTO[z["colore"]], font=F(10, True))
        y += 30
        c.create_text(16, y, text=f"IN YOUR GAMES, {DEC._fascia_turno(z['turno']).upper()}: WHAT EACH CHOICE GAINED ON AVERAGE", anchor="w", fill=C["muto"], font=F(7, True))
        y += 18
        validi = {k: v for k, v in medie.items() if v[1] >= 10}
        meglio = max(validi, key=lambda k: validi[k][0]) if validi else None
        for k, n in opz:
            v = medie.get(k)
            t_ = (f"{v[0]:+.1f}  ·  {v[1]} combats" if v else ("no data: not attacking is not a combat in the log" if k == "niente" else "no data")) + (
                "  ← your best line" if k == meglio else "")
            c.create_text(30, y, text=n, anchor="w", fill=C["testo"], font=F(9, k == q["scelta"]))
            c.create_text(250, y, text=t_, anchor="w", fill=C["verde"] if k == meglio else C["grigio"], font=F(9))
            y += 22
        y += 8
        c.create_text(16, y, text="Your average, not a rule: a clue to look at the spot again.", anchor="w", fill=C["grigio"], font=F(7))
        y += 24
        if q["i"] + 1 < len(q["voci"]):
            disegna_s3(c, 16, y, 196, y + 32, "Next spot ›", F(9, True), icona=False)
            c._box.append((16, y, 196, y + 32, ("avanti",)))

    def clic_quiz(self, e):
        q = getattr(self, "_quiz", None)
        c = self.cv_quiz
        bx = next((b_ for b_ in getattr(c, "_box", []) if b_[0] <= e.x <= b_[2] and b_[1] <= e.y <= b_[3]), None)
        if not q or bx is None:
            return None
        z = q["voci"][q["i"]]
        if bx[4][0] == "scegli":
            q["scelta"] = bx[4][1]
            medie = DEC.medie_opzioni(q["base"], z["tipo"], DEC._fascia_turno(z["turno"]))
            validi = {k: v for k, v in medie.items() if v[1] >= 10}
            q["fatte"] += 1
            if validi and max(validi, key=lambda k: validi[k][0]) == q["scelta"]:
                q["giuste"] += 1
        elif bx[4][0] == "avanti":
            q["i"] += 1
            q["scelta"] = None
        elif bx[4][0] == "vedi":       # il replayer sul momento prima della decisione
            i = self.apri_decisione(z["partita"], z["t"], z["tipo"])
            if i:
                self.vai_board(i - 1)
            return "vedi"
        self.disegna_quiz()
        return bx[4]

    def apri_decisione(self, partita, t, tipo, nome=None):
        """Il replayer sul momento di una decisione (R8, R14): il combattimento del turno t, o la magia di quel turno."""
        x_ = next((x for x in self.righe or [] if x["partita"] == partita), None)
        if x_ is None:
            return None
        self.apri_board(x_)
        b = getattr(self, "_board", None)
        if not b or b.get("x") is not x_:       # una partita senza log non apre il replayer
            return None
        if b.get("modo") != "momenti":
            self.cambia_modo_board("momenti")
        ps = b["passi"]
        if tipo == "magia":
            i = next((i for i, p_ in enumerate(ps) if p_[2] == t and isinstance(p_[3], dict) and p_[3].get("tipo") == "spell" and p_[3].get("nome") == nome), None)
        else:
            i = next((i for i, p_ in enumerate(ps) if p_[2] == t and p_is_comb(p_)), None)
        if i is None:
            i = next((i for i, p_ in enumerate(ps) if p_[2] == t), 0)
        self.vai_board(i)
        return i

    def disegna_mulligan(self, c, r, W):
        F = self.F
        m = DEC.mulligan(r)
        wr = lambda t: f"{100 * t[1] / t[0]:.0f}%" if t and t[0] else "-"
        c.create_text(14, 14, text=f"YOUR MULLIGANS · {len(r)} GAMES · to read your improvement: fewer risky hands kept, and a better win rate after a mulligan",
                      anchor="w", fill=C["muto"], font=F(7, True))
        y = 36
        for i, (nome, t, nota) in enumerate((("AFTER A MULLIGAN", m["dopo"], "games where you sent at least one hand back"),
                                             ("RISKY KEEPS", m["rischiose"], "7 cards kept with 0-1 or 6+ lands (the 60-card rule says mulligan)" if self.tipo == "Constructed"
                                              else "7 cards kept with 0 or 6+ lands (the measured table says mulligan)"),
                                             ("NORMAL KEEPS", m["normali"], "7 cards kept with 2-4 lands"))):
            x = 14 + i * 300
            c.create_line(x, y, x, y + 54, fill=C["azzurro"], width=2)
            c.create_text(x + 12, y + 4, text=nome, anchor="nw", fill=C["muto"], font=F(7, True))
            c.create_text(x + 12, y + 30, text=wr(t), anchor="w", fill=C["titolo"], font=F(15, True))
            c.create_text(x + 82, y + 30, text=f"{t[1]}-{t[0] - t[1]} · {t[0]} games", anchor="w", fill=C["grigio"], font=F(8))
            c.create_text(x + 12, y + 48, text=nota, anchor="w", fill=C["muto"], font=F(7))
        y += 76
        c.create_text(14, y, text="THE HANDS YOU KEPT · click a cell: Lands in hand and Start as filters", anchor="w", fill=C["azzurro"], font=F(8, True))
        y += 20
        for x, t in ((14, "LANDS"), (120, "WIN RATE ON THE PLAY"), (300, "WIN RATE ON THE DRAW"), (480, "WIN RATE · ALL"), (620, "HANDS YOU SENT BACK")):
            c.create_text(x, y, text=t, anchor="w", fill=C["titolo"], font=F(7, True))
        y += 16
        for i, terre in enumerate(range(0, 8)):
            d_ = m["tenute"].get(terre, {})
            pl, dr = d_.get("Play", (0, 0)), d_.get("Draw", (0, 0))
            tot = (pl[0] + dr[0], pl[1] + dr[1])
            c.create_rectangle(8, y, 800, y + 22, fill="#161b25" if i % 2 == 0 else "#131820", outline="")
            c.create_text(14, y + 11, text=f"{terre}{'+' if terre == 7 else ''}", anchor="w", fill=C["titolo"], font=F(8, True))
            for x, t, part in ((120, pl, "Play"), (300, dr, "Draw"), (480, tot, None)):
                testo = f"{wr(t)}  ·  {t[0]} games" if t[0] else "-"
                c.create_text(x, y + 11, text=testo, anchor="w", fill=C["testo"] if t[0] >= 5 else C["muto"], font=F(8))
                if part and t[0]:
                    c._box.append((x - 4, y, x + 170, y + 22, ("mano", str(terre), part)))
            c.create_text(620, y + 11, text=str(m["scartate"].get(terre, 0) or "-"), anchor="w", fill=C["testo"], font=F(8))
            y += 24
        y += 14
        c.create_text(14, y, text="WEEK BY WEEK", anchor="w", fill=C["azzurro"], font=F(8, True))
        y += 20
        cols = ((14, "WEEK OF"), (130, "GAMES"), (210, "MULLIGAN RATE · % games"), (360, "RISKY KEEPS · % of 7s"), (500, "WIN RATE AFTER A MULLIGAN"),
                (700, "WIN RATE OF 7-CARD KEEPS"), (900, "WIN RATE · ALL"))
        for x, t in cols:
            c.create_text(x, y, text=t, anchor="w", fill=C["titolo"], font=F(7, True))
        y += 16
        fmt = lambda v: "-" if v is None else f"{v:.0f}%"
        for i, w in enumerate(DEC.settimane(r)):
            c.create_rectangle(8, y, 1000, y + 22, fill="#161b25" if i % 2 == 0 else "#131820", outline="")
            for x, v in ((14, w["da"].strftime("%d %b")), (130, str(w["partite"])), (210, fmt(w["mull"])), (360, fmt(w["rischiose"])),
                         (500, fmt(w["wr_mull"]) + (f"  · {w['n_mull']} games" if w["n_mull"] else "")), (700, fmt(w["wr_sette"])), (900, fmt(w["wr"]))):
                c.create_text(x, y + 11, text=v, anchor="w", fill=C["testo"], font=F(8))
            y += 24
        c.configure(scrollregion=(0, 0, W, y + 20))

    def clic_decisioni(self, e):
        c = e.widget
        x, y = c.canvasx(e.x), c.canvasy(e.y)
        b = next((b for b in getattr(c, "_box", []) if b[0] <= x <= b[2] and b[1] <= y <= b[3]), None)
        if b is None:
            return None
        cosa = b[4]
        if cosa[0] == "costo":      # R8: il replayer su quel momento
            return self.apri_decisione(*cosa[1:])
        if cosa[0] == "quiz":       # R9: cosa faresti qui?
            return self.apri_quiz()
        if cosa[0] == "leak":       # R10: le partite col leak fra i filtri (di nuovo: tutte)
            k_ = f"leak_{cosa[1]}"
            if self.filtri.get(k_) == "Yes":
                self.filtri.pop(k_, None)
            else:
                self.filtri[k_] = "Yes"
            self.disegna()
            return self.filtri.get(k_)
        if cosa[0] == "cimitero":   # cimitero ed esilio: la situazione fra i filtri (di nuovo: tutte)
            if self.filtri.get(cosa[1]) is not None:
                self.filtri.pop(cosa[1], None)
            else:
                self.filtri[cosa[1]] = cosa[2]
            self.disegna()
            return self.filtri.get(cosa[1])
        if cosa[0] == "guarda_leak":        # R10 + R15: le sue partite nel replayer, sul leak
            import leak as LK
            rr = sorted((x for x in self.scelte() if LK.valore(x, cosa[1]) == "Yes"), key=lambda x: x["quando"], reverse=True)
            return self.apri_playlist(rr, "Leak · " + LK.NOMI[cosa[1]], k="leak")
        if cosa[0] == "testa":      # un titolo: ordina per quella colonna, di nuovo al contrario
            ok_, giu_ = getattr(self, "ord_dec", (None, False))
            self.ord_dec = (cosa[1], not giu_) if ok_ == cosa[1] else (cosa[1], False)
            self.disegna_decisioni()
            return self.ord_dec
        if cosa[0] == "riga":
            nuova = (self.dec_modo, cosa[1])
            self.linea_dec = None if self.linea_dec == nuova or cosa[1].startswith("All ") else nuova
            self.disegna_decisioni()
            if "chart" in self.visibili():
                self.disegna_grafico()
            return self.linea_dec
        if cosa[0] == "mano":
            self.metti_filtro("terre", cosa[1] if cosa[1] != "7" else "7")
            self.metti_filtro("partenza", cosa[2])
            return cosa
        return None

    def apri_righe_carte(self):
        """La finestrella delle righe di Cards: una spunta per riga, raggruppate per categoria (DA.GRUPPI_CARTE: prima il valore delle tue carte, in fondo
        l'Opponent); il clic sulla categoria le accende o le spegne tutte; All e None; si applica subito e resta (DA.salva_righe_carte)."""
        tk = self.tk
        f = getattr(self, "fin_righe", None)
        if f is None or not f.winfo_exists():
            f = self.fin_righe = tk.Toplevel(self.fr)
            f.title("Cards · rows to read")
            f.configure(bg=C["scheda"])
            f.resizable(False, False)
            f.bind("<Escape>", lambda e: f.destroy())
            alto = 44 + sum(34 + 26 * len(kk) for _g, kk in DA.GRUPPI_CARTE) + 44
            c = self.cv_righe = tk.Canvas(f, bg=C["scheda"], highlightthickness=0, bd=0, width=620, height=alto)
            c.pack(padx=8, pady=8)
            c.bind("<Button-1>", self.clic_righe_carte)
            try:
                f.geometry(f"+{self.fr.winfo_pointerx() - 120}+{max(0, self.fr.winfo_pointery() - 200)}")
            except Exception:      # noqa: BLE001
                pass
        self.disegna_righe_carte()
        f.lift()
        return f

    def disegna_righe_carte(self):
        c = getattr(self, "cv_righe", None)
        if c is None or not c.winfo_exists():
            return
        F = self.F
        W = int(c.cget("width"))
        c.delete("all")
        c._box = []
        scelte_r = set(DA.righe_carte_scelte())
        c.create_text(12, 16, text="THE ROWS OF CARDS · tick the ones you want to see", anchor="w", fill=C["titolo"], font=F(9, True))
        y = 40
        for gruppo, kk in DA.GRUPPI_CARTE:
            n_on = sum(1 for k in kk if k in scelte_r)
            c.create_rectangle(6, y, W - 6, y + 26, fill="#161b25", outline="")
            c.create_rectangle(6, y, 9, y + 26, fill=C["azzurro"], outline="")
            c.create_image(18, y + 13, image=DG.spunta(14, n_on == len(kk), C["azzurro"], C["fondo"], C["grigio"], C["fondo"]), anchor="w")
            c.create_text(42, y + 13, text=gruppo, anchor="w", fill=C["azzurro"], font=F(8, True))
            c.create_text(W - 14, y + 13, text=f"{n_on}/{len(kk)}", anchor="e", fill=C["grigio"], font=F(8, True))
            c._box.append((6, y, W - 6, y + 26, ("gruppo", kk)))
            y += 32
            for k in kk:
                on = k in scelte_r
                nome, resto = DA.BREVI_CARTE[k]
                c.create_image(34, y + 10, image=DG.spunta(14, on, C["azzurro"], C["fondo"], C["grigio"], C["fondo"]), anchor="w")
                i_ = c.create_text(58, y + 10, text=nome, anchor="w", fill=C["titolo"] if on else C["grigio"], font=F(9, True))
                bb = c.bbox(i_)
                c.create_text(bb[2] + 8, y + 10, text=resto, anchor="w", fill=C["muto"], font=F(7))
                c._box.append((26, y, W - 6, y + 22, k))
                y += 26
            y += 2
        y += 8
        for x0, testo, k in ((14, "All", "*"), (84, "None", "-")):
            c.create_rectangle(x0, y, x0 + 60, y + 26, fill="#161b25", outline="#2a303b")
            c.create_text(x0 + 30, y + 13, text=testo, fill=C["titolo"], font=F(8, True))
            c._box.append((x0, y, x0 + 60, y + 26, k))

    def clic_righe_carte(self, e):
        c = self.cv_righe
        b = next((b for b in getattr(c, "_box", []) if b[0] <= e.x <= b[2] and b[1] <= e.y <= b[3]), None)
        if b is None:
            return None
        scelte_r = set(DA.righe_carte_scelte())
        k = b[4]
        if k == "*":
            scelte_r = {k_ for k_, _t in DA.RIGHE_CARTE}
        elif k == "-":
            scelte_r = set()
        elif isinstance(k, tuple):      # la categoria: tutte accese se ne manca una, se no tutte spente
            kk = set(k[1])
            scelte_r = scelte_r - kk if kk <= scelte_r else scelte_r | kk
        else:
            scelte_r ^= {k}
        DA.salva_righe_carte(scelte_r)
        self.disegna_righe_carte()
        self.sincronizza()
        if "cards" in self.visibili():
            self.disegna_carte()
        return k

    def apri_coppie(self, chiave, titolo=None):
        """La finestra delle coppie di una riga di Cards: le coppie di carte che stanno insieme nelle partite scelte, dalla piu' vincente (DA.coppie_carte); si
        rifa' coi filtri; il clic su una coppia tiene solo le sue partite, il passaggio mostra la carta grande. Una finestra sola: un'altra riga la riempie."""
        tk = self.tk
        f = getattr(self, "fin_coppie", None)
        if f is None or not f.winfo_exists():
            f = self.fin_coppie = tk.Toplevel(self.fr)
            f.configure(bg=C["scheda"])
            f.geometry("1180x760")
            f.bind("<Escape>", lambda e: f.destroy())
            cv = self.cv_coppie = tk.Canvas(f, bg=C["scheda"], highlightthickness=0, bd=0)
            cv.pack(fill="both", expand=True, padx=8, pady=8)
            cv.bind("<Button-1>", self.clic_carte)
            cv.bind("<Button-3>", self.destro_carte)
            cv.bind("<MouseWheel>", lambda e: (self.via_hover_carte(), e.widget.yview_scroll(-2 if e.delta > 0 else 2, "units")))
            cv.bind("<Motion>", self.sopra_carte)
            cv.bind("<Leave>", lambda e: self.via_hover_carte())
            cv.bind("<Configure>", lambda e: self.disegna_coppie())
        self.coppie_di = (chiave, titolo or dict(DA.RIGHE_CARTE).get(chiave, chiave))
        self.coppie_k = getattr(self, "coppie_k", 2)
        f.title("Leak Finder · Answers" if chiave == "minacce" else "Leak Finder · Pairs · " + self.coppie_di[1].split(" · ")[0].title())
        self.disegna_coppie()
        f.lift()
        return f

    def disegna_coppie(self):
        f = getattr(self, "fin_coppie", None)
        if f is None or not f.winfo_exists() or self.righe is None:
            return
        c = self.cv_coppie
        c.delete("all")
        self.via_hover_carte()
        c._box_carte, c._box_coppie = [], []
        F = self.F
        chiave, titolo = self.coppie_di
        W = max(c.winfo_width(), 600)
        r = self.scelte()
        k_ = DA.conti(r)
        base = k_["wr"]
        if chiave == "minacce":         # C15: le minacce e le tue risposte, non le coppie
            return self.disegna_risposte(c, r, W, base)
        kk = self.coppie_k
        cp = DA.coppie_carte(r, chiave, k=kk)
        quale = "IN YOUR OPENING HAND" if chiave == "pesc1" else "· " + titolo.split(" · ")[0]
        # Pairs e Trios (13 nov 2026, Autore: «nella sezione cards sarebbe bene avere anche oltre alle coppie i tris»): due interruttori in cima
        x_ = 14
        for k2, nome in ((2, "Pairs"), (3, "Trios")):
            x1_ = x_ + 20 + int(c.tk.call("font", "measure", F(9, True), nome))
            chip(c, x_, 4, x1_, 28, nome, kk == k2, F(9, True))
            c._box_coppie.append((x_, 4, x1_, 28, ("k", k2), None))
            x_ = x1_ + 8
        c.create_text(x_ + 8, 16, text=f"{'PAIRS' if kk == 2 else 'TRIOS'} {quale} · {k_['n']} GAMES · by win rate, 5 games together at least", anchor="w",
                      fill=C["azzurro"], font=F(8, True))
        if base is not None:
            c.create_text(W - 14, 42, text=f"win rate of these games {base:.0f}% · click one: only its games", anchor="e", fill=C["grigio"], font=F(7))
        if not cp:
            c.create_text(14, 56, text=f"No {'pair' if kk == 2 else 'trio'} comes together in 5 games or more here.", anchor="w", fill=C["grigio"], font=F(9))
            c.configure(scrollregion=(0, 0, W, 80))
            return
        wc = LARGA_CARTA
        hc = round(wc * 279 / 200)
        larga = wc + round(wc * 0.5) * (kk - 1) + 18
        per_riga = max(1, int((W - 28) // larga))
        y = 56
        for i, cc in enumerate(cp):
            if i and i % per_riga == 0:
                y += hc + 50
            self.metti_carta(c, 14 + (i % per_riga) * larga, y, cc, chiave, base)
        c.configure(scrollregion=(0, 0, W, y + hc + 56))

    def disegna_risposte(self, c, r, W, base):
        """C15, «quale carta mi avrebbe salvato?»: ogni minaccia (le sue carte che stanno piu' nelle tue sconfitte) e accanto le rimozioni che hai nella
        collezione, nei colori dei tuoi mazzi, che dal testo la tolgono (grado C). Il clic su una minaccia tiene le sue partite; il passaggio mostra la carta."""
        import variabili_c as VC
        F = self.F
        craft_ = getattr(self, "risposte_craft", False)
        mm = VC.minacce(r, craft=craft_)
        c.create_text(14, 16, text=f"THE THREATS THAT BEAT YOU · AND WHAT {'ANSWERS' if craft_ else 'YOU OWN THAT ANSWERS'} THEM · {len(r)} games", anchor="w",
                      fill=C["azzurro"], font=F(8, True))
        # la spunta: anche le carte da craftare (18 nov 2026, Autore: «suggerendoci validi counter dalla collezione o craftabili se flagghiamo la spunta»)
        nome_c = "Include craftable"
        x1_ = W - 14
        x0_ = x1_ - 20 - int(c.tk.call("font", "measure", F(9, True), nome_c))
        chip(c, x0_, 4, x1_, 28, nome_c, craft_, F(9, True))
        c._box_coppie.append((x0_, 4, x1_, 28, ("craft", not craft_), None))
        c.create_text(14, 36, text=("Their cards in more of your losses than your wins; on the right the removal in your collection, in your decks' colors (and "
                                    "Standard-legal if you play Standard), that reads like it removes them. Read from the card text: a clue, not a verdict "
                                    "(protection, ward and hexproof are not checked)."), anchor="nw", fill=C["grigio"], font=F(7), width=W - 30)
        if not mm:
            c.create_text(14, 76, text="No card of theirs stands out in your losses here (3 losses at least).", anchor="w", fill=C["grigio"], font=F(9))
            c.configure(scrollregion=(0, 0, W, 100))
            return
        wc = LARGA_CARTA
        hc = round(wc * 279 / 200)
        y = 70
        for cc in mm:
            self.metti_carta(c, 14, y, cc, "minacce", base)
            x_ = 14 + wc + 40
            c.create_text(x_ - 18, y + hc / 2, text="›", fill=C["accento"], font=F(16, True))
            if not cc["risposte"]:
                c.create_text(x_, y + hc / 2, text=("Nothing in these colors reads like an answer, even to craft." if craft_ else
                                                    "Nothing in your collection, in these colors, reads like an answer. Tick «Include craftable» to see what to craft."),
                              anchor="w", fill=C["muto"], font=F(8))
            for nm in cc["risposte"]:
                if x_ + wc > W - 14:
                    break
                self.metti_carta(c, x_, y, dict(nome=nm, n=0, vinte=0, perse=0, wr=0, quota=0, risposta=True, filtro=("lanciate", nm)), "lanciate", None)
                x_ += wc + 10
            y += hc + 50
        c.configure(scrollregion=(0, 0, W, y + 10))

    def destro_carte(self, e):
        """Il tasto destro su una carta di Cards (o delle sue finestre): la sua analisi, nella sotto-scheda Card."""
        sotto = self.carta_sotto(e)
        if sotto is None:
            return None
        return self.apri_analisi_carta(DA.nome_intero(sotto[4]))

    def carte_cercabili(self):
        """Le carte della casella della scheda Card: le tue lanciate, le sue, quelle delle tue liste nelle partite del tipo, dalla piu' frequente."""
        conta = collections.Counter()
        for x in self.righe or []:
            if x.get("tipo") != self.tipo:
                continue
            for n in set(x.get("mie_lanciate") or []) | set(x.get("sue_lanciate") or []) | {k for k, q in (x.get("deck") or {}).items() if q}:
                if n and not DA.e_terra(n):
                    conta[n] += 1
        return [n for n, _k in conta.most_common()]

    def cambia_carte_modo(self, m):
        self.carte_modo = m
        self.sincronizza()
        if "cards" in self.visibili():
            self.disegna_carte()

    def apri_analisi_carta(self, nome, alza=True):
        """La carta sotto la lente: la porta nella sotto-scheda Card di Cards (dal 18 nov 2026 sera non e' piu' una finestra a parte). nome None: la scheda
        chiede la carta. -> la tela di Cards."""
        self.analisi_di = nome
        self.carte_modo = "card"
        if alza and self.vista != "cards" and "cards" not in self.staccate:
            self.cambia_vista("cards")
        self.sincronizza()
        if "cards" in self.visibili():
            self.tela("cards").yview_moveto(0)
            self.disegna_carte()
        return self.tela("cards")

    def disegna_scheda_carta(self, c):
        """La sotto-scheda Card (18 nov 2026, Autore: «Questa analisi deve darci dati diversi se siamo settati in limited o constructed. Per constructed ci
        deve dare statistiche su quante sinergie conosciute ci sono tra lei e altre carte. Sinergie verificate e realizzatesi in campo dalle piu' deboli alle
        piu' forti. Ci deve dire in quanto e' giocata in quanti mazzi appare quanto valore ci genera ecc»). Sulle partite dei filtri:
          in testa la carta, quanto e' giocata (liste, mazzi, copie, lanciata, contro di te) e il valore (EV in campo, meriti, sopravvive);
          Limited: il draft (GIH e ALSA di 17Lands, i tuoi pick dai log); Constructed: le sinergie conosciute dal testo e quelle verificate in campo;
          il meta dei tuoi log, la rosa dei compagni, le partite con lei (il clic apre il replay)."""
        import analisi_carta as AC
        F = self.F
        nome = getattr(self, "analisi_di", None)
        W = max(c.winfo_width(), 900)
        if not nome:
            c.create_text(16, 24, text="CARD · type a card in the box above, or right-click any card in By games", anchor="w", fill=C["grigio"], font=F(10, True))
            c.configure(scrollregion=(0, 0, W, 60))
            return None
        r = self.scelte()
        base_t = [x for x in self.righe if x["tipo"] == self.tipo]
        k_ = DA.conti(r)
        base = k_["wr"]
        wc = LARGA_CARTA
        img = self.immagine_carta(nome, wc + 60, False)
        if img is not None:
            c.create_image(16, 16, image=img, anchor="nw")
            c._box_carte.append((16, 16, 16 + wc + 60, 16 + round((wc + 60) * 279 / 200), nome, None, None, None))
        x0 = 16 + wc + 60 + 24
        cr_ = DA._carta(nome) or {}
        limited = self.tipo == "Limited"
        c.create_text(x0, 18, text=nome, anchor="nw", fill=C["titolo"], font=F(14, True), width=W - x0 - 20)
        c.create_text(x0, 46, text=f"{cr_.get('tipo') or ''} · MV {cr_.get('cmc', 0)} · you own {cr_.get('copie', 0)} · {self.tipo.upper()} ANALYSIS",
                      anchor="nw", fill=C["grigio"], font=F(8))
        u = AC.uso(r, nome)
        yy = 70

        def riga_(testo, col=C["testo"], f_=None):
            nonlocal yy
            i_t = c.create_text(x0, yy, text=testo, anchor="nw", fill=col, font=f_ or F(10, True), width=W - x0 - 20)
            yy = (c.bbox(i_t) or (0, 0, 0, yy + 18))[3] + 5
        riga_(f"In your lists in {u['in_lista']} of these {u['n']} games · {u['mazzi']} deck{'s' if u['mazzi'] != 1 else ''}"
              + (f" · {u['copie']:g} copies on average" if u["copie"] else ""))
        riga_(f"You cast it in {u['lanciata']} games ({u['quota'] or 0:.0f}%)" + (f" · you won {u['wr']:.0f}% (all these games {base:.0f}%)"
                                                                                 if u["wr"] is not None and base is not None else ""))
        if u["contro"]:
            riga_(f"Cast against you in {u['contro']} games · you won {u['wr_contro']:.0f}%", C["grigio"])
        v_ = AC.valore(r, base_t, nome)
        if v_:
            import ev_partita as EV_
            corti = dict(letale="lethal", danno="unblocked hits", vince="combats won", salva="saves", scambio="trades", tiene="blocks held",
                         rimbalza="bounced off", rimossa="removed", chump="chump blocks", assist="assists", perde="died for nothing")
            meriti = ", ".join(f"{corti.get(m) or EV_.NOMI_MERITI.get(m, m)} {n}" for m, n in sorted(v_["conta"].items(), key=lambda kv: -kv[1])[:6])
            riga_(f"VALUE · EV on the battlefield {v_['in_campo']:+.1f} a copy · merits {v_['ev_meriti']:+.1f} a copy"
                  + (f" ({meriti})" if meriti else "") + (f" · survived to the end in {v_['sopr']} of {v_['n']} games" if v_.get("n") else ""),
                  C["verde"] if v_["in_campo"] > 0 else C["rosso"] if v_["in_campo"] < 0 else C["testo"], F(9, True))
        if limited:
            ld = AC.limited(nome)
            g_ = " · ".join(f"17Lands {fmt.capitalize()} GIH {g[0]:.1f}%" if g[0] is not None else f"17Lands {fmt.capitalize()}: {g[1] or 0} games, no GIH yet"
                            for fmt, g in ld["gih"].items())
            alsa = next((g[2] for g in ld["gih"].values() if g[2]), None)
            riga_("DRAFT · " + (g_ or "no 17Lands data for this card") + (f" · ALSA {alsa:.1f}" if alsa else ""), C["azzurro"], F(9, True))
            riga_((f"Your drafts: you saw it {ld['vista']} times, took it {ld['prese']}" + (f" (pick {ld['pick_medio']:g} of the pack on average)"
                                                                                         if ld["pick_medio"] else "") + f", passed it {ld['lasciata']}")
                  if ld["vista"] else "Your drafts: never seen in a pack in your logs", C["grigio"], F(8))
        me = AC.meta(r, nome)
        yy += 6
        colw = (W - x0 - 20) // 3
        for j, (tit_, lst_) in enumerate((("YOUR DECKS WITH IT", me["miei"]), ("YOU CAST IT AGAINST", me["contro"]), ("CAST AGAINST YOU BY", me["suoi"]))):
            xx_ = x0 + j * colw
            c.create_text(xx_, yy, text=tit_, anchor="nw", fill=C["azzurro"], font=F(7, True))
            if not lst_:
                c.create_text(xx_, yy + 18, text="-", anchor="nw", fill=C["muto"], font=F(8))
            for i, (kk, n, w) in enumerate(lst_[:6]):
                c.create_text(xx_, yy + 18 + i * 17, text=f"{kk[:22]} · {n} · {w:.0f}%" if w is not None else f"{kk[:22]} · {n}", anchor="nw",
                              fill=C["testo"] if n >= 5 else C["grigio"], font=F(8))
        y = max(16 + round((wc + 60) * 279 / 200), yy + 18 + 6 * 17) + 24
        hc = round(wc * 279 / 200)
        # le sinergie, solo nel Constructed: quelle note dal testo e quelle che si sono avverate in campo
        if not limited:
            note = AC.sinergie_note(r, nome)
            c.create_line(14, y, W - 14, y, fill="#252b36")
            c.create_text(14, y + 14, text=f"KNOWN SYNERGIES · {len(note)} cards of your lists work with it, from the card text (a clue, not a measure)",
                          anchor="w", fill=C["azzurro"], font=F(8, True))
            y += 30
            if not note:
                c.create_text(14, y + 6, text="No known synergy with the cards of your lists.", anchor="w", fill=C["muto"], font=F(8))
                y += 26
            else:
                colw2 = (W - 28) // 3
                for i, z in enumerate(note[:24]):
                    xx_ = 14 + (i % 3) * colw2
                    yy_ = y + (i // 3) * 18
                    c.create_text(xx_, yy_, text=f"{z['nome'][:30]} · {', '.join(nome_famiglia(f_) for f_ in z['famiglie'][:2])}"
                                  + (f" · in {z['mazzi']} lists" if z["mazzi"] else ""), anchor="nw", fill=C["testo"], font=F(8))
                y += ((min(len(note), 24) + 2) // 3) * 18 + 10
            ic = AC.sinergie_in_campo(r, base_t, nome, note)
            c.create_line(14, y, W - 14, y, fill="#252b36")
            c.create_text(14, y + 14, text=("VERIFIED ON THE BATTLEFIELD · weakest to strongest: the known synergies that met in play, on your side at the end "
                                            "of the same turn; EV = win-probability points those turns made above or below the usual, per game"),
                          anchor="w", fill=C["azzurro"], font=F(8, True), width=W - 28)
            y += 34
            if not ic:
                c.create_text(14, y + 6, text="None of them met it on the battlefield in these games.", anchor="w", fill=C["muto"], font=F(8))
                y += 26
            else:
                for t_, x_c in (("PARTNER", 14), ("WHY", 300), ("GAMES TOGETHER", 520), ("W-L", 650), ("WIN RATE", 720), ("TURNS", 810), ("EV A GAME", 880)):
                    c.create_text(x_c, y, text=t_, anchor="w", fill=C["titolo"], font=F(7, True))
                y += 14
                for i, z in enumerate(ic):
                    c.create_rectangle(8, y, W - 8, y + 22, fill="#161b25" if i % 2 == 0 else "#131820", outline="")
                    tono = C["grigio"] if z["poche"] else C["testo"]
                    col_ev = C["grigio"] if z["poche"] else (C["verde"] if z["ev"] > 0 else C["rosso"] if z["ev"] < 0 else C["testo"])
                    for t_, x_c, col_ in ((z["nome"][:34], 14, tono), (", ".join(nome_famiglia(f_) for f_ in z["famiglie"][:2]), 300, C["grigio"]),
                                          (str(z["n"]), 520, tono), (f"{z['vinte']}-{z['perse']}", 650, tono), (f"{z['wr']:.0f}%", 720, tono),
                                          (str(z["turni"]), 810, tono), (f"{z['ev']:+.1f}", 880, col_ev)):
                        c.create_text(x_c, y + 11, text=t_, anchor="w", fill=col_, font=F(8, True))
                    c._box_carte.append((8, y, 290, y + 22, z["nome"], "verificata", z["filtro"][0], z["filtro"][1]))
                    y += 24
                c.create_text(14, y + 4, text="click a partner: only the games where you cast both · under 3 games in grey", anchor="nw", fill=C["muto"], font=F(7))
                y += 24
        # la rosa
        sn = AC.sinergie(r, nome)
        c.create_line(14, y, W - 14, y, fill="#252b36")
        c.create_text(14, y + 14, text="THE BEST PARTNERS · your cards cast in the same games: win rate together against the games of this card without them",
                      anchor="w", fill=C["azzurro"], font=F(8, True))
        y += 30
        if not sn["rosa"]:
            c.create_text(14, y + 8, text="No partner yet: you never cast it in these games." if not sn["n"] else "No other card of yours cast with it here.",
                          anchor="w", fill=C["muto"], font=F(8))
            y += 34
        else:
            per_riga = max(1, int((W - 28) // (wc + 14)))
            x_ = 14
            for i, cc in enumerate(sn["rosa"]):
                if i and i % per_riga == 0:
                    x_, y = 14, y + hc + 50
                x_ += self.metti_carta(c, x_, y, cc, "lanciate", None) + 14
            y += hc + 50
        # le partite
        pc = AC.partite_con(r, nome, quante=60)
        c.create_line(14, y, W - 14, y, fill="#252b36")
        c.create_text(14, y + 14, text=f"THE GAMES WITH IT · {len(pc)} · click one: its replay", anchor="w", fill=C["azzurro"], font=F(8, True))
        y += 32
        for t_, x_c in (("DATE", 14), ("YOUR DECK", 140), ("OPPONENT", 360), ("CAST BY", 560), ("TURN", 680), ("RESULT", 760)):
            c.create_text(x_c, y, text=t_, anchor="w", fill=C["titolo"], font=F(7, True))
        y += 14
        for i, z in enumerate(pc):
            x = z["x"]
            c.create_rectangle(8, y, W - 8, y + 22, fill="#161b25" if i % 2 == 0 else "#131820", outline="")
            for t_, x_c, col_ in ((f"{x['quando']:%d %b %H:%M}", 14, C["testo"]), ((x.get("mio") or "")[:28], 140, C["testo"]),
                                  ((x.get("suo") or "")[:26], 360, C["testo"]), ({"you": "you", "opponent": "opponent", "both": "both"}[z["chi"]], 560,
                                                                               C["azzurro"] if z["chi"] != "opponent" else "#f0ad4e"),
                                  (f"T{z['giro']}" if z["giro"] is not None else "-", 680, C["testo"]),
                                  ("Won" if x["vinta"] else "Lost", 760, C["verde"] if x["vinta"] else C["rosso"])):
                c.create_text(x_c, y + 11, text=t_, anchor="w", fill=col_, font=F(8, True))
            c._box_partite.append((8, y, W - 8, y + 22, x))
            y += 24
        c.configure(scrollregion=(0, 0, W, y + 20))
        return c

    def clic_analisi_carta(self, e):
        """Nella scheda Card: il clic su un compagno della rosa apre la sua analisi, su un compagno delle sinergie verificate tiene le partite con tutti e
        due, su una partita apre il suo replay."""
        c = e.widget
        x, y = c.canvasx(e.x), c.canvasy(e.y)
        sotto = self.carta_sotto(e)
        if sotto is not None:
            if sotto[5] == "verificata":       # una sinergia verificata: le partite con tutti e due
                self.filtri["lanciate"] = None if self.filtri.get("lanciate") == sotto[7] else sotto[7]
                self.disegna()
                return sotto[7]
            if sotto[4] == getattr(self, "analisi_di", None):
                return None
            return self.apri_analisi_carta(DA.nome_intero(sotto[4]))
        z = next((b for b in getattr(c, "_box_partite", []) if b[0] <= x <= b[2] and b[1] <= y <= b[3]), None)
        if z is not None:
            self.apri_board(z[4])
            return z[4]
        return None

    def carta_sotto(self, e):
        c = e.widget
        x, y = c.canvasx(e.x), c.canvasy(e.y)
        return next((b for b in getattr(c, "_box_carte", []) if b[0] <= x <= b[2] and b[1] <= y <= b[3]), None)

    def clic_carte(self, e):
        """Il clic su una carta: solo le partite in cui c'e', nel senso della sua riga (in mano, pescata in quel turno, lanciata, rimasta in mano); di nuovo
        sulla stessa, tutte. Su «Pairs ›» di una riga: la finestra delle sue coppie. Nella scheda Card: clic_analisi_carta."""
        cv = e.widget
        if self.carte_modo == "card" and cv is self.tela("cards"):
            return self.clic_analisi_carta(e)
        x, y = cv.canvasx(e.x), cv.canvasy(e.y)
        bc = next((b for b in getattr(cv, "_box_coppie", []) if b[0] <= x <= b[2] and b[1] <= y <= b[3]), None)
        if bc is not None:
            if bc[4] == "ev_carte":             # la gerarchia dei meriti (18 nov 2026, il lettore di EV)
                return self.apri_meriti()
            if bc[4] == "ev_sue":               # i mazzi dell'Opponent ricomposti dalle carte viste
                return self.apri_liste()
            if isinstance(bc[4], tuple) and bc[4][0] == "verso":       # le migliori o le piu' deboli per prime
                self.deboli ^= {bc[4][1]}
                self.disegna_carte()
                return bc[4]
            if isinstance(bc[4], tuple) and bc[4][0] == "craft":       # Answers: anche le carte da craftare
                self.risposte_craft = bc[4][1]
                self.disegna_coppie()
                return bc[4]
            if isinstance(bc[4], tuple):        # Pairs o Trios nella finestra delle coppie
                self.coppie_k = bc[4][1]
                self.disegna_coppie()
                return bc[4]
            return self.apri_coppie(bc[4], bc[5])
        sotto = self.carta_sotto(e)
        if sotto is None:
            return None
        fk, fv = sotto[6], sotto[7]
        self.filtri[fk] = None if self.filtri.get(fk) == fv else fv
        self.disegna()
        return fv

    def apri_liste(self, alza=True):
        """Il meta dai nostri dati (18 nov 2026, Autore: «possiamo provare a ricostruire un meta anche se abbiamo poche carte»): per ogni archetipo
        dell'Opponent incontrato nella situazione, le carte che ha mostrato con la frequenza (in quante partite contro di lui), dalle piu' frequenti; il tuo
        record contro di lui. Deduttivo: si vede solo cio' che arriva in campo o si rivela. Una finestra sola, segue i filtri."""
        import ev_partita as EV_
        tk, F = self.tk, self.F
        f = getattr(self, "fin_liste", None)
        if f is None or not f.winfo_exists():
            f = self.fin_liste = tk.Toplevel(self.fr)
            f.title("Leak Finder · Their decks")
            f.configure(bg=C["scheda"])
            f.bind("<Escape>", lambda e: f.destroy())
            f.cv = tk.Canvas(f, bg=C["scheda"], highlightthickness=0, width=980, height=640)
            sb = tk.Scrollbar(f, orient="vertical", command=f.cv.yview)
            f.cv.configure(yscrollcommand=sb.set)
            sb.pack(side="right", fill="y")
            f.cv.pack(fill="both", expand=True)
            f.cv.bind("<MouseWheel>", lambda e: f.cv.yview_scroll(-2 if e.delta > 0 else 2, "units"))
        c = f.cv
        c.delete("all")
        ll = EV_.liste_composite(self.scelte(), base=[x for x in self.righe or [] if x["tipo"] == self.tipo])
        c.create_text(16, 18, text=f"THEIR DECKS, REBUILT FROM WHAT YOU SAW · {self.tipo.upper()}", anchor="w", fill=C["titolo"], font=F(11, True))
        i_d = c.create_text(16, 40, text=("For each deck you met, the cards it showed (cast or revealed) and in how many of your games against it. A few cards a game "
                                          "add up to the deck. On the right, what the card was worth to the opponent in that deck (win-probability points per copy on the "
                                          "battlefield; grey under 15 copies). It only sees what reached the battlefield or was revealed: cards kept in hand stay hidden."),
                            anchor="nw", fill=C["grigio"], font=F(8), width=940)
        y = max(80, (c.bbox(i_d) or (0, 0, 0, 62))[3] + 22)        # la descrizione va a capo: il primo mazzo sotto di lei, mai sopra (19 nov 2026)
        if not ll:
            c.create_text(16, y, text="No deck met in at least 3 of these games.", anchor="w", fill=C["grigio"], font=F(9))
        colw = 310
        for a in ll:
            c.create_text(16, y, text=f"{a['archetipo']} · {a['partite']} games · you {a['vinte']}-{a['partite'] - a['vinte']}", anchor="w",
                          fill=C["azzurro"], font=F(9, True))
            y += 20
            for j, (nome, _q, pc) in enumerate(a["carte"][:24]):
                col_, riga_ = j % 3, j // 3
                c.create_text(16 + col_ * colw, y + riga_ * 18, text=f"{pc:3d}%  {nome[:26]}", anchor="w", fill=C["testo"] if pc >= 30 else C["grigio"],
                              font=F(8))
                # l'EV della carta per l'Opponent in questo mazzo (18 nov 2026): verde se gli rende, rosso se gli costa, grigio con poche copie
                ev_ = (a.get("ev") or {}).get(nome)
                if ev_ is not None:
                    v_, n_ = ev_
                    c.create_text(16 + col_ * colw + colw - 14, y + riga_ * 18, text=f"{v_:+.1f}", anchor="e", font=F(8, True),
                                  fill=C["muto"] if n_ < EV_.MINIMO else C["verde"] if v_ > 0 else C["rosso"] if v_ < 0 else C["grigio"])
            y += ((min(len(a["carte"]), 24) + 2) // 3) * 18 + 16
        c.configure(scrollregion=(0, 0, 980, y + 20))
        if alza:
            f.lift()
        return f

    def apri_meriti(self, alza=True):
        """La gerarchia dei meriti delle carte in campo (18 nov 2026, Autore: «stabilire una gerarchia di punti che ogni carta ambisce a vincere», «il
        valore lo dicono i dati»): ogni merito col suo valore misurato (il controfattuale col modello della P: il tavolo col gesto contro senza), dal piu' alto,
        quante volte in tutte le partite del tipo e nella situazione. Una finestra sola, segue i filtri."""
        import ev_partita as EV_
        tk, F = self.tk, self.F
        f = getattr(self, "fin_meriti", None)
        if f is None or not f.winfo_exists():
            f = self.fin_meriti = tk.Toplevel(self.fr)
            f.title("Leak Finder · Merits")
            f.configure(bg=C["scheda"])
            f.bind("<Escape>", lambda e: f.destroy())
            f.cv = tk.Canvas(f, bg=C["scheda"], highlightthickness=0, width=760, height=520)
            f.cv.pack(fill="both", expand=True)
        c = f.cv
        c.delete("all")
        base = [x for x in self.righe or [] if x["tipo"] == self.tipo]
        qui = self.scelte()
        vm = EV_.valori_meriti(base)
        conta_qui = collections.Counter(e[0] for x in qui for k in EV_._eventi(x) if not k["pedina"] for e in k["eventi"])
        c.create_text(16, 18, text=f"WHAT EACH DEED OF A CARD IS WORTH · {self.tipo.upper()}", anchor="w", fill=C["titolo"], font=F(11, True))
        c.create_text(16, 40, text=("Each deed is measured on your games, not written by hand: the win chance of the board after the deed against the same board "
                                    "without it (the damage not dealt, the combat undone, the removed card still there). The average is its value."),
                      anchor="nw", fill=C["grigio"], font=F(8), width=720)
        y = 84
        for x_, t_ in ((16, "DEED"), (380, "VALUE"), (480, "ALL GAMES"), (590, "THESE GAMES")):
            c.create_text(x_, y, text=t_, anchor="w", fill=C["titolo"], font=F(7, True))
        y += 18
        for i, (mer, v) in enumerate(vm.items()):
            c.create_rectangle(8, y, 750, y + 26, fill="#161b25" if i % 2 == 0 else "#131820", outline="")
            col = C["muto"] if v["n"] < EV_.MINIMO else C["verde"] if v["valore"] >= 1 else C["rosso"] if v["valore"] <= -1 else C["testo"]
            c.create_text(16, y + 13, text=EV_.NOMI_MERITI.get(mer, mer)[:1].upper() + EV_.NOMI_MERITI.get(mer, mer)[1:], anchor="w", fill=C["titolo"], font=F(9, True))
            c.create_text(380, y + 13, text=f"{v['valore']:+.1f} pts", anchor="w", fill=col, font=F(9, True))
            c.create_text(480, y + 13, text=str(v["n"]), anchor="w", fill=C["testo"], font=F(9))
            c.create_text(590, y + 13, text=str(conta_qui.get(mer, 0)), anchor="w", fill=C["testo"], font=F(9))
            y += 28
        if not vm:
            c.create_text(16, y + 10, text="No deeds in these games: they are read from the replays of the games played with the app.", anchor="w",
                          fill=C["grigio"], font=F(9))
            y += 30
        c.create_text(16, y + 12, text=(f"Grey: under {EV_.MINIMO} times, a hint. A deed is worth what it added on its own: when several creatures attack "
                                        "together, each one's lethal is the damage it alone added. The win chance comes from the suggester's model (17Lands public "
                                        "replays, CC BY 4.0, Limited); in Constructed it compares moments."),
                      anchor="nw", fill=C["grigio"], font=F(7), width=720)
        c.configure(height=y + 70)
        if alza:
            f.lift()
        return f

    def sopra_carte(self, e):
        n = (self.carta_sotto(e) or (None,) * 8)[4]
        c = e.widget
        if n == getattr(self, "_hc_nome", None):
            if n is not None and getattr(self, "_hc", None) is not None:
                self.metti_hover_carte(e)
            return
        self.via_hover_carte()
        self._hc_nome = n
        c.configure(cursor="hand2" if n else "")
        img = self.immagine_grande(DA.nome_intero(n)) if n else None
        if img is None:
            return
        h = self._hc = self.tk.Toplevel(c.winfo_toplevel())
        h.overrideredirect(True)
        h.configure(bg="#0b0e14")
        self.tk.Label(h, image=img, bg="#0b0e14", bd=0).pack(padx=2, pady=2)
        self.metti_hover_carte(e)

    def metti_hover_carte(self, e):
        h = self._hc
        w, hh = h.winfo_reqwidth(), h.winfo_reqheight()
        top = e.widget.winfo_toplevel()
        x, y = e.x_root + 24, e.y_root - hh // 2
        if x + w > top.winfo_rootx() + top.winfo_width():
            x = e.x_root - w - 24
        h.geometry(f"+{max(0, x)}+{max(0, min(y, h.winfo_screenheight() - hh - 40))}")

    def via_hover_carte(self):
        h = getattr(self, "_hc", None)
        if h is not None:
            try:
                h.destroy()
            except Exception:      # noqa: BLE001 - gia' chiusa
                pass
        self._hc, self._hc_nome = None, None

    def disegna_miei(self):
        """La cartella My filters: i filtri personali uno sotto l'altro, ognuno coi suoi numeri di adesso (partite, record, win rate con l'intervallo e lo
        scarto da tutte, play e draw); il clic lo mette, la ✕ lo toglie; quello uguale ai filtri di adesso ha il bordo azzurro."""
        c = self.tela("mine")
        c.delete("all")
        c._box_miei = []
        if self.righe is None:
            return
        F = self.F
        W = max(c.winfo_width(), 700)
        sit = DA.situazioni()
        if not sit:
            c.create_text(16, 30, text="No personal filters yet.", anchor="w", fill=C["titolo"], font=F(9, True))
            c.create_text(16, 52, text="Set some smart filters, then press «Save as my filter»: it comes here, with its numbers, ready to be applied again.",
                          anchor="w", fill=C["grigio"], font=F(8))
            self.disegna_segnalibri(c, 84, W)
            return
        corto = lambda t, n: t if len(t) <= n else t[:n - 1] + "…"
        attuali = {k: v for k, v in self.filtri.items() if v is not None}
        y = 4
        for i, s_ in enumerate(sit):
            tipo = s_.get("tipo") or self.tipo
            fl = s_.get("filtri") or {}
            r = DA.filtra(self.righe, fl, tipo)
            k_ = DA.conti(r)
            tot = DA.conti([x for x in self.righe if x["tipo"] == tipo])
            on = tipo == self.tipo and fl == attuali
            c.create_rectangle(0, y, W - 2, y + ALTO_MIO - 6, fill="#0e2238" if on else ("#161b25" if i % 2 == 0 else "#131820"),
                               outline=C["accento"] if on else "#252b36")
            c.create_text(14, y + 16, text=corto(f"{tipo} · " + self.descrivi(fl, tipo), int((W - 640) / 6.4)), anchor="w", fill=C["titolo"], font=F(9, True))
            c.create_text(14, y + 36, text=f"{k_['n']} games · {k_['vinte']}-{k_['perse']}" + (f" · 95% CI {k_['ic'][0]}–{k_['ic'][1]}%" if k_["ic"] else ""),
                          anchor="w", fill=C["grigio"], font=F(7))
            xw = W - 600
            wr = k_["wr"]
            col = C["muto"] if wr is None else (C["verde"] if wr >= 50 else C["rosso"])
            c.create_rectangle(xw, y + 20, xw + 140, y + 32, fill="#252b36", outline="")
            if wr is not None:
                c.create_rectangle(xw, y + 20, xw + 1.4 * wr, y + 32, fill=col, outline="")
            c.create_line(xw + 70, y + 16, xw + 70, y + 36, fill="#d8d8dc")
            c.create_text(xw + 150, y + 26, text=f"{wr:.0f}%" if wr is not None else "-", anchor="w", fill=col, font=F(11, True))
            if wr is not None and tot["wr"] is not None:
                d_ = wr - tot["wr"]
                c.create_text(xw + 215, y + 26, text=f"{d_:+.1f} vs all", anchor="w", fill=C["verde"] if d_ > 0 else C["rosso"] if d_ < 0 else C["testo"],
                              font=F(8, True))
            pc = lambda v: f"{v:.0f}%" if v is not None else "-"
            c.create_text(xw + 310, y + 18, text="PLAY", anchor="w", fill=C["muto"], font=F(6, True))
            c.create_text(xw + 310, y + 34, text=pc(k_["play"]), anchor="w", fill=C["testo"], font=F(8, True))
            c.create_text(xw + 370, y + 18, text="DRAW", anchor="w", fill=C["muto"], font=F(6, True))
            c.create_text(xw + 370, y + 34, text=pc(k_["draw"]), anchor="w", fill=C["testo"], font=F(8, True))
            c.create_text(xw + 430, y + 18, text="TURNS", anchor="w", fill=C["muto"], font=F(6, True))
            c.create_text(xw + 430, y + 34, text=f"T{k_['turni']}" if k_["turni"] else "-", anchor="w", fill=C["testo"], font=F(8, True))
            c.create_text(W - 60, y + 26, text="applied" if on else "apply", anchor="e", fill=C["accento"], font=F(8, True))
            c.create_text(W - 22, y + 26, text="✕", fill=C["grigio"], font=F(10, True))
            c._box_miei.append((0, y, W - 44, y + ALTO_MIO - 6, "metti", i))
            c._box_miei.append((W - 40, y, W - 2, y + ALTO_MIO - 6, "togli", i))
            y += ALTO_MIO
        self.disegna_segnalibri(c, y + 14, W)

    def disegna_segnalibri(self, c, y, W):
        """Sotto i filtri personali, gli spot segnati nel replayer: la partita, il passo, l'esito; il clic la riapre su quel passo, la ✕ lo toglie."""
        F = self.F
        sb = DA.segnalibri()
        c.create_text(4, y + 8, text=f"BOOKMARKED SPOTS · {len(sb)}", anchor="w", fill="#ffd23f", font=F(7, True))
        y += 24
        if not sb:
            c.create_text(14, y + 10, text="In the replayer press Bookmark (or B) on a spot: it comes here, one click to watch it again.", anchor="w",
                          fill=C["grigio"], font=F(8))
            y += 30
        for k, s_ in enumerate(sb):
            c.create_rectangle(0, y, W - 2, y + 38, fill="#161b25" if k % 2 == 0 else "#131820", outline="#3a3220")
            c.create_polygon(12, y + 10, 22, y + 10, 22, y + 28, 17, y + 23, 12, y + 28, fill="#ffd23f", outline="")
            quando = s_.get("quando", "")[:16].replace("T", " ")
            if s_.get("vivo"):     # R13: segnato mentre giocavi, la partita la dicono i log (se non c'e' ancora: «not in your logs yet»)
                x_v = next((x for x in self.righe or [] if x.get("partita") == s_.get("partita")), None)
                if x_v:
                    s_ = dict(s_, mio=(x_v.get("mio") or "").strip(), suo=x_v.get("suo"), vinta=x_v["vinta"])
            esito_ = "not in your logs yet" if s_.get("vinta") is None else ("won" if s_.get("vinta") else "lost")
            c.create_text(34, y + 12, text=f"{s_.get('mio') or '-'} vs {s_.get('suo') or '-'}", anchor="w", fill=C["titolo"], font=F(8, True))
            c.create_text(34, y + 27, text=f"{quando} · {esito_} · {s_.get('passo')}"
                          + (" · every action" if s_.get("modo") == "azioni" else "") + (f"  ·  ✎ {s_['nota'][:60]}" if s_.get("nota") else ""),
                          anchor="w", fill=C["grigio"], font=F(7))
            c.create_text(W - 60, y + 19, text="watch", anchor="e", fill=C["accento"], font=F(8, True))
            c.create_text(W - 22, y + 19, text="✕", fill=C["grigio"], font=F(10, True))
            c._box_miei.append((0, y, W - 44, y + 38, "guarda", k))
            c._box_miei.append((W - 40, y, W - 2, y + 38, "via_sb", k))
            y += 42
        c.configure(scrollregion=(0, 0, W, y + 8))

    def clic_miei(self, e):
        c = getattr(e, "widget", None) or self.tela("mine")
        y = c.canvasy(e.y)
        for x0, y0, x1, y1, cosa, i in getattr(c, "_box_miei", []):
            if x0 <= e.x <= x1 and y0 <= y <= y1:
                sit = DA.situazioni()
                if cosa == "guarda":
                    sb = DA.segnalibri()
                    if i < len(sb):
                        self.apri_segnalibro(sb[i])
                    return
                if cosa == "via_sb":
                    DA.togli_segnalibro(i)
                    self.disegna_miei()
                    return
                if cosa == "togli":
                    DA.togli_situazione(i)
                    self.disegna_miei()
                    if "compare" in self.visibili():
                        self.disegna_confronto()
                elif i < len(sit):
                    self.applica(sit[i])
                return

    def applica(self, s):
        self.tipo = s.get("tipo") or self.tipo
        self.disegna_switch()
        self.filtri = dict(s.get("filtri") or {})
        self.disegna()
