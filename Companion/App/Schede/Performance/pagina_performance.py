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
import datetime
import math
import os
import threading

import dati_analizzatore as DA
import decisioni as DEC
import numeri_partite as NP
import righe_filtri as R_F
import disegni as DG
from tema import CI as C
from widget import ARANCIO, Tendina, pulsante_solido

LINEE = ("#d8d8dc", "#24baff", "#f0ad4e", "#a58cff", "#5cb85c", "#ee8a87")      # All, poi i valori: lontani fra loro anche per i daltonici (come il resto dell'app)
COLONNE = (("nome", "", 250), ("n", "GAMES", 70), ("wl", "W-L", 80), ("wr", "WIN RATE", 180), ("play", "PLAY", 70), ("draw", "DRAW", 70), ("mull", "MULL.", 70),
           ("turni", "AVG T", 70), ("delta", "Δ VS ALL", 90))
TIPI = ("Constructed", "Limited")
# le ricerche preimpostate di Spots (13 nov 2026, Autore: «spots ... deve dare una combo di filtri preimpostati per risolvere le ricerche fondamentali tra le
# partite / ne schiaccio uno e tutti i filtri si combinano per quella ricerca»): (gruppo, nome, cosa cerca, filtri, vista che risponde, Group by del Report)
PRESET = (
    ("OPENING HAND", "Kept 7 · which cards win", "No mulligan · the Report by card in your opening hand", {"mull": "0"}, "report", "mano"),
    ("OPENING HAND", "After a mulligan · which cards win", "One mulligan · the Report by card in your opening hand", {"mull": "1"}, "report", "mano"),
    ("OPENING HAND", "Kept 7 on the draw", "No mulligan, on the draw · by card in hand", {"mull": "0", "partenza": "Draw"}, "report", "mano"),
    ("OPENING HAND", "You missed a land drop", "By your 4th turn", {"sit:io_terra": "Yes"}, "chart", None),
    ("OPENING HAND", "You curved out", "A spell on each of your turns 2, 3 and 4", {"sit:io_curva": "Yes"}, "chart", None),
    ("ATTACK", "All-in into open mana", "Everything attacked, the opponent had 2+ untapped lands", {"sit:io_tutto_aperto": "Yes"}, "chart", None),
    ("ATTACK", "Held back against open mana", "2+ untapped lands: you never attacked with everything", {"sit:io_tutto_aperto": "No"}, "chart", None),
    ("ATTACK", "Attacked into a tapped-out opponent", "The opponent had no untapped land", {"sit:io_att_chiuso": "Yes"}, "chart", None),
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
                  "turni": lambda x: x.get("turno"), "mano": lambda x: x.get("terre")}
SPOT_MODI = (("preset", "Preset searches"), ("auto", "Auto spots"))
VISTE = (("chart", "Chart"), ("spots", "Spots"), ("report", "Report"), ("matchups", "Matchups"), ("compare", "Compare"), ("cards", "Cards"), ("decisions", "Decisions"),
         ("mine", "My filters"))
DISEGNI = {"chart": "disegna_grafico", "spots": "disegna_spot", "report": "disegna_report", "matchups": "disegna_matchup", "compare": "disegna_confronto",
           "mine": "disegna_miei", "cards": "disegna_carte", "decisions": "disegna_decisioni"}
DEC_MODI = (("attacco", "Attacks"), ("blocco", "Blocks"), ("mull", "Mulligans"))
LARGA_CARTA = 112                               # le carte della cartella Cards
ALTO_MIO = 58                                   # una riga dei filtri personali
GRIGI = ("#2a2a30", "#3a3a42", "#0f86cc")       # i pulsanti a pillola grigi, azzurri se scelti
ALTO_TAB, LARGA_TAB = 34, 132                   # le cartelle
LARGA_DECK = 1000                               # la finestra By deck
ALTO_PARTITA = 24                               # una riga della tabella delle partite
ALTO_CTRL = 158                                 # la barra del replayer della board: il grafico della partita sopra, i comandi sotto
ALTO_GRAF = 92                                  # il grafico della partita nella barra
LARGA_RACCONTO = 300                            # la colonna del racconto a destra della tavola
# per fasi della partita (12 nov 2026, Autore: «il menu a tendine creiamolo per macro fasi partita: formato evento e deck - poi start e mulligan - lands in
# hand / cards in hand possiamo toglierlo, their card anche»): prima della partita (con By deck), l'apertura, l'avversario, com'e' finita, quando.
# «deck» e' il pulsante By deck; Card in hand e Their card non sono tendine (restano in Split by, Group by e negli Spots)
FASI = (("BEFORE THE GAME", ()),      # senza + more (13 nov 2026, Autore: «sezione before the game non serve il pulsante more»): i colori del tuo mazzo stanno in Advanced filters
        ("OPENING AND FIRST TURNS", ("economiche", "crea_mano", "sit:io_terra", "sit:lui_terra", "sit:io_curva", "sit:io_crea2", "sit:lui_crea2")),
        ("THE OPPONENT AND THE FIGHT", ("sit:io_primo", "sit:io_nel_suo", "sit:lui_nel_mio", "sit:lui_bersagli", "sit:io_att_aperto", "sit:io_att_chiuso",
                                        "sit:lui_att_aperto", "sit:io_passa_aperto", "sit:lui_passa_aperto", "sit:io_blocca", "sit:io_difende",
                                        "sit:io_tutto", "sit:io_tutto_aperto")),
        ("THE END OF THE GAME", ("fine", "sit:io_morti", "sit:lui_morti")),
        ("WHEN", ("giorno", "pausa")))      # i filtri in piu' di ogni fase, nel suo +
LARGA_FASE = 780
# i filtri della finestra Advanced filters (13 nov 2026): due schede, You e Opponent, e dentro ognuna le fasi (stesso giorno, Autore: «nei filtri avanzati
# ci mancano le giocate nel turno avversario, le sue nei nostri turni, le fasi di attacco di entrambi e di difesa di entrambi quindi ci devono essere in you e
# opponent delle sotto schede di fasi e you e opponent diventano le macro schede»). {scheda: ((fase, ((titolo, chiavi), ...)), ...)}
AVANZATI = {
    "io": (("Opening hand", (("YOUR DECK", ("miei_colori",)),
                              ("YOUR OPENING HAND", ("crea_in_mano", "ist_mano", "str_mano", "art_mano", "inc_mano", "pw_mano", "bat_mano")))),
           # le pescate (13 nov 2026, Autore: «nei filtri di you e opponent aggiungiamo anche le pescate nel proprio e nel turno avversario più alcuni filtri
           # generali che indicano che sono avvenute 1, 2 o più pescate in almeno uno dei turni»)
           ("Your turns", (("WHAT YOU CAST ON YOUR TURNS", ("@t_io",)),
                           ("YOUR DRAWS ON YOUR TURNS (THE DRAW STEP TOO)", tuple(f"t_pio{n}" for n in range(1, DA.TURNI_FILTRO + 1))),
                           ("EXTRA DRAWS", ("t_peio",)))),
           ("Opponent's turns", (("WHAT YOU CAST ON THE OPPONENT'S TURNS", ("@t_iox",)),
                                 ("YOUR DRAWS ON THE OPPONENT'S TURNS", tuple(f"t_piox{n}" for n in range(1, DA.TURNI_FILTRO + 1))),
                                 ("EXTRA DRAWS", ("t_peio",)))),
           ("Attack", (("YOUR ATTACKS, TURN BY TURN", tuple(f"t_aio{n}" for n in range(1, DA.TURNI_FILTRO + 1))),
                       ("THE OPPONENT'S UNTAPPED LANDS WHEN YOU ATTACK", tuple(f"t_mio{n}" for n in range(1, DA.TURNI_FILTRO + 1))),
                       ("IN THE WHOLE GAME", ("sit:io_primo", "sit:io_tutto", "sit:io_tutto_aperto", "sit:io_att_aperto", "sit:io_att_chiuso")))),
           ("Defense", (("YOUR DEFENSE ON THE OPPONENT'S TURNS", tuple(f"t_dio{n}" for n in range(1, DA.TURNI_FILTRO + 1))),
                        ("IN THE WHOLE GAME", ("sit:io_blocca", "sit:io_difende")))),
           # i filtri situazionali dai replay (13 nov 2026, «sii minuzioso e dettagliato parti dai replay»): terre, vita e campo, rimozioni e interazione
           ("Game", (("LAND DROPS", ("s_terre_io3", "s_terre_io4", "s_terre_io5")),
                     ("LIFE AND BOARD AT THE END OF YOUR TURNS", ("s_vita_io", "s_vita_t3", "s_vita_t5", "s_vita_t7", "s_crea_t3", "s_crea_t5", "s_crea_t7")),
                     ("REMOVAL AND INTERACTION", ("s_rim_io", "s_wipe_io", "s_counter_io", "s_cim_io", "s_magie_io")),
                     ("THE END", ("senza_crea", "fine_entro"))))),
    "lui": (("Opening hand", (("THE OPPONENT", ("suo_mull",)),)),
            ("Their turns", (("WHAT THEY CAST ON THEIR TURNS", ("@t_lui",)),
                             ("THEIR DRAWS ON THEIR TURNS (THE DRAW STEP TOO)", tuple(f"t_plui{n}" for n in range(1, DA.TURNI_FILTRO + 1))),
                             ("EXTRA DRAWS", ("t_pelui",)))),
            ("Your turns", (("WHAT THEY CAST ON YOUR TURNS", ("@t_luix",)),
                            ("THEIR DRAWS ON YOUR TURNS", tuple(f"t_pluix{n}" for n in range(1, DA.TURNI_FILTRO + 1))),
                            ("EXTRA DRAWS", ("t_pelui",)))),
            ("Attack", (("THEIR ATTACKS, TURN BY TURN", tuple(f"t_alui{n}" for n in range(1, DA.TURNI_FILTRO + 1))),
                        ("YOUR UNTAPPED LANDS WHEN THEY ATTACK", tuple(f"t_mlui{n}" for n in range(1, DA.TURNI_FILTRO + 1))),
                        ("IN THE WHOLE GAME", ("sit:lui_att_aperto",)))),
            ("Defense", (("THEIR DEFENSE ON YOUR TURNS", tuple(f"t_dlui{n}" for n in range(1, DA.TURNI_FILTRO + 1))),)),
            ("Game", (("LAND DROPS", ("s_terre_lui3", "s_terre_lui4", "s_terre_lui5")),
                      ("LIFE AND CREATURES", ("s_vita_lui", "senza_lui")),
                      ("REMOVAL AND INTERACTION", ("s_rim_lui", "s_wipe_lui", "s_counter_lui", "s_cim_lui", "s_magie_lui")))))}
VALORI_FISSI = {"mull": ("0", "1", "2+"), "partenza": ("Play", "Draw"), "esito": ("Won", "Lost")}      # le tendine con le voci fisse
SEZIONI_FILTRI = (("formato", "evento", "wr_rif", "deck"), ("partenza", "mull", "terre", "esito"), ("suo", "colori"), ("lunga", "rango"), ("data", "fascia", "sessione"))


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


def _colore_wr(w):
    """Il fondo di una cella della matrice: dal rosso (sotto il 50%) all'azzurro (sopra), scuro vicino al 50."""
    t = max(-1.0, min(1.0, (w - 50) / 25))
    a, b = ((36, 186, 255) if t > 0 else (217, 83, 79)), (32, 32, 38)
    k = abs(t) * 0.75
    return "#%02x%02x%02x" % tuple(round(b[i] + (a[i] - b[i]) * k) for i in range(3))


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


class PaginaPerformance:
    MODI = ("Limited", "Standard")

    def __init__(self, tk, padre, F, mana):
        self.tk, self.F = tk, F
        self.fr = tk.Frame(padre, bg=C["fondo"])
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
        self.mostra_vs_filtro = False   # sotto il grafico: la linea di tutte le partite contro quella filtrata
        self.mostra_guadagno = False    # sotto il grafico: il guadagno delle decisioni contro la media
        self.linea_dec = None           # una riga di Decisions sul grafico: (tipo, nome della riga)
        self.spot_modo = "preset"       # Spots: le ricerche preimpostate (di partenza) o gli spot automatici
        self._lavoro, self.l_carica = None, None
        self.scheda_av = "io"        # la scheda aperta della finestra Advanced filters
        self.ord_partite = ("data", False)        # la tabella delle partite: la colonna e il verso (di partenza dalla piu' recente)
        self.fase_av = {"io": 0, "lui": 0}      # e la fase aperta di ognuna
        self.costruisci()
        self.fr.bind("<<Davanti>>", lambda e: self.se_sporca(), add="+")
        self.fr.bind("<Map>", lambda e: self.se_sporca(), add="+")
        self.ricarica()

    # ------------------------------------------------------------ la finestra grande
    def segna(self):
        self.sporca = True

    def se_sporca(self):
        if self.sporca and self.righe is not None:
            self.disegna()

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
            self.disegna()
            if self._di_nuovo:
                self.ricarica()
        self.fr.after(150, aspetta)

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
        testa = tk.Frame(self.fr, bg=C["cap"]); testa.pack(fill="x")
        tk.Label(testa, text="PERFORMANCE", bg=C["cap"], fg=C["titolo"], font=F(11, True)).pack(side="left", padx=(16, 6), pady=10)
        tk.Label(testa, text="analyzer · games and situations from your Arena logs", bg=C["cap"], fg=C["grigio"], font=F(8)).pack(side="left", padx=(0, 18))
        self.b_tipi = {}
        for t in TIPI:
            b = pulsante_solido(tk, F, testa, t, t == self.tipo, lambda t=t: self.cambia_tipo(t), alto=26, bg=C["cap"],
                                colori=("#2a2a30", "#3a3a42", "#0f86cc"))
            b.configure(width=118); b.pack(side="left", padx=(0, 6), pady=8)
            self.b_tipi[t] = b
        # il reset globale (12 nov 2026, Autore: «aggiungiamo anche un reset global che ci porta a tutte le partite di default»): filtri, situazioni, grafico e
        # vista in basso come all'apertura; Constructed o Limited resta
        self.b_reset = pulsante_solido(tk, F, testa, "Reset all", False, self.reset, alto=26, bg=C["cap"], colori=ARANCIO)      # arancio come gli altri Reset (13 nov 2026)
        self.b_reset.configure(width=100); self.b_reset.pack(side="right", padx=(8, 16), pady=8)
        self.l_info = tk.Label(testa, text="Reading your logs…", bg=C["cap"], fg=C["grigio"], font=F(8))
        self.l_info.pack(side="right", padx=(16, 4))
        corpo = tk.Frame(self.fr, bg=C["fondo"]); corpo.pack(fill="both", expand=True, padx=10, pady=10)
        corpo.columnconfigure(0, weight=0, minsize=300); corpo.columnconfigure(1, weight=1); corpo.rowconfigure(0, weight=1)
        # a sinistra: le variabili e le situazioni salvate, in una colonna che scorre
        sx = tk.Frame(corpo, bg=C["scheda"], highlightthickness=1, highlightbackground=C["filo"]); sx.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        rs = tk.Frame(sx, bg=C["scheda"]); rs.pack(fill="x", padx=12, pady=(10, 4))
        # «Smart filters» (12 nov 2026, Autore: «i filtri a sinistra potremmo chiamarli smart filters»); il pulsante Add filters (le situazioni) non c'e' piu':
        # le situazioni stanno nel + della loro fase
        tk.Label(rs, text="SMART FILTERS", bg=C["scheda"], fg=C["muto"], font=F(7, True)).pack(side="left")
        # la colonna scorre: con la rotella sopra qualunque sua parte, e con la barra sottile a destra (fino al 12 nov la rotella andava solo sul fondo vuoto e
        # le ultime tendine e le situazioni salvate restavano tagliate in fondo: Autore, «la finestra degli smart filters e' tagliata sul fondo»)
        riga_sx = tk.Frame(sx, bg=C["scheda"]); riga_sx.pack(fill="both", expand=True)
        barra = tk.Canvas(riga_sx, width=6, bg=C["traccia"], highlightthickness=0, cursor="hand2"); barra.pack(side="right", fill="y", padx=(0, 4), pady=4)

        def segna(a, b_):
            barra.delete("all"); a, b_ = float(a), float(b_)
            if b_ - a < 0.999:
                H_ = barra.winfo_height(); barra.create_rectangle(0, H_ * a, 6, H_ * b_, fill=C["grigio"], width=0)
        self.cv_sx = tk.Canvas(riga_sx, bg=C["scheda"], highlightthickness=0, bd=0, width=280, yscrollcommand=segna); self.cv_sx.pack(side="left", fill="both", expand=True)
        barra.bind("<Button-1>", lambda e: self.cv_sx.yview_moveto(e.y / max(barra.winfo_height(), 1)))
        barra.bind("<B1-Motion>", lambda e: self.cv_sx.yview_moveto(e.y / max(barra.winfo_height(), 1)))
        self.col_sx = tk.Frame(self.cv_sx, bg=C["scheda"])
        self.cv_sx.create_window(0, 0, window=self.col_sx, anchor="nw")
        self.col_sx.bind("<Configure>", lambda e: self.cv_sx.configure(scrollregion=(0, 0, 0, self.col_sx.winfo_reqheight() + 16)))

        def rotella(e):
            w = str(e.widget)
            if (w.startswith(str(self.cv_sx)) or w.startswith(str(barra))) and self.col_sx.winfo_reqheight() > self.cv_sx.winfo_height():
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
                    self.b_deck = pulsante_solido(tk, F, griglia, "By deck  ·  all decks vs all", False, self.apri_deck, alto=28, bg=C["scheda"])
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
        self.b_salva_sit = pulsante_solido(tk, F, self.col_sx, "Save as my filter", False, self.salva_situazione, alto=28, bg=C["scheda"])
        self.b_salva_sit.configure(width=262); self.b_salva_sit.pack(anchor="w", padx=12, pady=(4, 6))
        self.b_pulisci = pulsante_solido(tk, F, self.col_sx, "Clear all filters", False, self.pulisci, alto=28, bg=C["scheda"],
                                         colori=ARANCIO)      # arancio (13 nov 2026, Autore: «e clear all filter lo fai arancio»)
        self.b_pulisci.configure(width=262); self.b_pulisci.pack(anchor="w", padx=12, pady=(0, 12))
        # a destra: i numeri in alto, sotto le cartelle (12 nov 2026, Autore: «questi falli a modo di cartelle e poi tira via il sotto testo»): Chart, Spots,
        # Report, Matchups e Compare, una alla volta; il segno a destra di ogni linguetta la stacca in una finestra sua («ogni sezione di ogni cartella si puo'
        # staccare dal quadro e renderla una finestra a se stante»), chiusa torna qui
        dx = tk.Frame(corpo, bg=C["fondo"]); dx.grid(row=0, column=1, sticky="nsew")
        dx.columnconfigure(0, weight=1); dx.rowconfigure(2, weight=1)
        self.cv_num = tk.Canvas(dx, bg=C["scheda"], highlightthickness=1, highlightbackground=C["filo"], height=108, bd=0)       # le tessere centrate fra la riga in alto e il fondo, con aria sotto (12 nov 2026, Autore: «le barre toccano la base della tabella, voglio le cose centrate»)
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
        self.cv_gr, self.cv_sp, self.cv_rp, self.cv_mt, self.cv_cf = (o[k]["tela"] for k in ("chart", "spots", "report", "matchups", "compare"))
        self.b_metr = o["chart"]["ctl"]["metr"]
        self.t_asse, self.t_fin, self.t_dividi = (o["chart"]["ctl"][k] for k in ("asse", "fin", "dividi"))
        self.t_per, self.b_meta = o["report"]["ctl"]["per"], o["matchups"]["ctl"]["meta"]
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
        lab = tk.Label(griglia, text="WIN RATE", bg=C["scheda"], fg=C["grigio"], font=F(7, True), anchor="w"); lab.grid(row=i, column=0, sticky="w", pady=2)
        self.lab_filtri = getattr(self, "lab_filtri", {}); self.lab_filtri["wr_rif"] = lab
        fr = tk.Frame(griglia, bg=C["scheda"]); fr.grid(row=i, column=1, sticky="w", pady=2)
        self.wr_segni = {}
        for chiave, segno in (("ge", "≥"), ("le", "≤")):
            b = tk.Label(fr, text=segno, width=2, bg="#101014", fg=C["grigio"], font=F(10, True), cursor="hand2", highlightthickness=1,
                         highlightbackground="#3a3a40")
            b.bind("<Button-1>", lambda e, c_=chiave: self.cambia_segno_wr(c_))
            self.wr_segni[chiave] = b
        self.wr_ge, self.wr_le = False, False
        self.wr_var = tk.StringVar(value="")
        self.e_wr = tk.Entry(fr, textvariable=self.wr_var, width=6, justify="center", bg="#101014", fg=C["titolo"], insertbackground=C["titolo"],
                             relief="flat", font=F(10, True), highlightthickness=1, highlightbackground="#3a3a40", highlightcolor=C["accento"])
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
        self.e_wr.configure(bg="#0f2a38" if on else "#101014", highlightbackground=C["accento"] if on else "#3a3a40")
        for chiave, b in self.wr_segni.items():
            acceso = getattr(self, "wr_" + chiave)
            b.configure(bg=C["accento"] if acceso else "#101014", fg="#101014" if acceso else C["grigio"],
                        highlightbackground=C["accento"] if acceso or on else "#3a3a40")
        self.lab_filtri["wr_rif"].configure(fg=C["accento"] if on else C["grigio"])

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
        lab = tk.Label(griglia, text=corto.upper(), bg=C["scheda"], fg=C["grigio"], font=F(7, True), anchor="w"); lab.grid(row=i, column=0, sticky="w", pady=2)
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
                b.configure(width=104); b.pack(side="left", padx=(0, 6), anchor="s", pady=(0, 2))
                ctl["metr"][m] = b
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
        elif k == "report":
            ctl["per"] = Tendina(tk, riga, "Group by", F, larga=220, bg=C["scheda"]); ctl["per"].fr.pack(side="right")
            ctl["per"].opzioni([k_ for k_, _n, _f in DA.VARIABILI if k_ != "data"] + ["vs"] + [k_ for k_, _n, _f in DA.EXTRA] + sit_k, lambda v: self.cambia("per", v), etichette=et_var)
            ctl["per"].set(self.per)
        elif k == "decisions":       # attacchi, blocchi, mulligan (13 nov 2026), e i filtri delle decisioni
            ctl["dmodo"] = {}
            for m, n in DEC_MODI:
                b = pulsante_solido(tk, F, riga, n, m == self.dec_modo, lambda m=m: self.cambia_dec(m), alto=26, bg=C["scheda"], colori=GRIGI)
                b.configure(width=110); b.pack(side="left", padx=(0, 6), anchor="s", pady=(0, 2))
                ctl["dmodo"][m] = b
            ctl["dfin"] = pulsante_solido(tk, F, riga, "Decision filters", False, self.apri_filtri_dec, alto=26, bg=C["scheda"], colori=GRIGI)
            ctl["dfin"].configure(width=200); ctl["dfin"].pack(side="right", anchor="s", pady=(0, 2))
        elif k == "cards":       # quali righe vedere: la finestrella dei filtri di Cards (13 nov 2026)
            ctl["righe"] = pulsante_solido(tk, F, riga, "Rows", False, self.apri_righe_carte, alto=26, bg=C["scheda"], colori=GRIGI)
            ctl["righe"].configure(width=170); ctl["righe"].pack(side="left", anchor="s", pady=(0, 2))
        elif k == "matchups":
            ctl["meta"] = pulsante_solido(tk, F, riga, "Meta decks only", self.solo_meta, self.cambia_meta, alto=26, bg=C["scheda"], colori=GRIGI)
            ctl["meta"].configure(width=140); ctl["meta"].pack(side="right", anchor="s", pady=(0, 2))
        elif k == "compare":
            ctl["con"] = Tendina(tk, riga, "Compare A with (B)", F, larga=260, bg=C["scheda"]); ctl["con"].fr.pack(side="left")
            ctl["con"].opzioni(["rest"], lambda v: self.cambia("con", v), etichette={"rest": "Everything else"}); ctl["con"].set(self.con)
            asse_e_finestra()
        lista = None
        if k == "chart":       # sotto il grafico le partite della situazione, una per riga, con la mano e la board (12 nov 2026, «proprio come holdem manager»)
            # grafico e partite divisi da una linea da trascinare: allarga uno e stringe l'altro (12 nov 2026, Autore: «tra chart e elenco crea una linea di
            # separazione che possa aumentare la dimensione della lista sotto restringendo lo spazio sopra e viceversa»)
            corpo_ = tk.PanedWindow(fr, orient="vertical", bg="#2c2c34", bd=0, sashwidth=7, sashrelief="flat", sashpad=0, opaqueresize=True,
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
            c.configure(yscrollincrement=24)       # la rotella scorre di una riga intera
            c.bind("<MouseWheel>", lambda e: (e.widget.yview_scroll(-1 if e.delta > 0 else 1, "units"), self.maschera_rp(e.widget)))
        elif k == "decisions":
            c.bind("<Button-1>", self.clic_decisioni)
            c.bind("<MouseWheel>", lambda e: e.widget.yview_scroll(-2 if e.delta > 0 else 2, "units"))
        elif k == "cards":
            c.bind("<Button-1>", self.clic_carte)
            c.bind("<MouseWheel>", lambda e: (self.via_hover_carte(), e.widget.yview_scroll(-2 if e.delta > 0 else 2, "units")))
            c.bind("<Motion>", self.sopra_carte)
            c.bind("<Leave>", lambda e: self.via_hover_carte())
        elif k == "mine":
            c.bind("<Button-1>", self.clic_miei)
            c.bind("<MouseWheel>", lambda e: e.widget.yview_scroll(-2 if e.delta > 0 else 2, "units"))
        elif k == "matchups":
            c.bind("<Button-1>", self.clic_matchup)
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
            for k, v in (("asse", self.asse), ("fin", self.finestra), ("dividi", self.dividi or "None"), ("per", self.per), ("con", self.con)):
                if k in ctl:
                    ctl[k].set(v)
            if "meta" in ctl:
                ctl["meta"].metti("Meta decks only", self.solo_meta)
            if "righe" in ctl:
                n_, tot_ = len(DA.righe_carte_scelte()), len(DA.RIGHE_CARTE)
                ctl["righe"].metti("Rows · all" if n_ == tot_ else f"Rows · {n_} of {tot_}", n_ < tot_)

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
        for k, n in VISTE:
            x0, x1 = x, x + LARGA_TAB
            fuori = k in self.staccate
            top = 3 if k == self.vista else 8
            if k == self.vista:
                att = (x0, x1)
            else:
                pts = _cartella(x0, x1, top, H + 1)
                d.poligono(pts, riempi="#202026" if sopra and sopra[0] == k else "#18181c")
                d.linea(pts, "#2e2e34", 1.0)
            su_segno = sopra == (k, "segno")
            segni.append((x1 - 22, (top + H) / 2, C["titolo"] if su_segno else C["accento"] if fuori else C["muto"], fuori))
            testi.append(((x0 + x1 - 26) / 2, (top + H) / 2 + 1, n + ("  ↗" if fuori else ""), k == self.vista))
            self._box_tab.append((x0, top, x1, H, k, (x1 - 34, top, x1 - 6, H)))
            x = x1 + 3
        if att:
            x0, x1 = att
            d.linea([(0, H - 0.5), (x0 + 0.5, H - 0.5)], C["filo"], 1.0)       # il bordo alto del pannello, aperto sotto la cartella scelta
            d.linea([(x1 - 0.5, H - 0.5), (W, H - 0.5)], C["filo"], 1.0)
            pts = _cartella(x0, x1, 3, H + 1)
            d.poligono(pts, riempi=C["scheda"])
            d.linea(pts, C["filo"], 1.0)
        else:
            d.linea([(0, H - 0.5), (W, H - 0.5)], C["filo"], 1.0)
        for sx_, sy_, col, fuori in segni:        # sopra le cartelle, anche su quella aperta
            _segno_stacca(d, sx_, sy_, col, fuori)
        self._img_tab = d.foto()
        c.create_image(0, 0, image=self._img_tab, anchor="nw")
        for tx, ty, t, on in testi:
            c.create_text(tx, ty, text=t, fill=C["titolo"] if on else C["grigio"], font=F(8, True))

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
        w.title(f"Performance · {nome}")
        w.configure(bg=C["scheda"])
        pw, ph = max(self.pan.winfo_width(), 900), max(self.pan.winfo_height(), 520) + 60
        w.geometry(f"{pw}x{ph}+{self.pan.winfo_rootx() + 40}+{max(0, self.pan.winfo_rooty() - 40)}")
        testa = tk.Frame(w, bg=C["cap"]); testa.pack(fill="x")
        tk.Label(testa, text=f"PERFORMANCE · {nome.upper()}", bg=C["cap"], fg=C["titolo"], font=F(10, True)).pack(side="left", padx=(16, 10), pady=10)
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
    def cambia_tipo(self, t):
        self.tipo = t
        for k, b in self.b_tipi.items():
            b.metti(k, k == t)
        self.filtri = {}
        for tnd in self.tendine.values():
            tnd.set("Any")
        self.disegna()

    def metti_filtro(self, k, v):
        self.filtri[k] = None if v == "Any" else v
        self.disegna()

    def pulisci(self):
        self.filtri = {}
        self._righe_ui = {}
        self.disegna()

    PARTENZA = dict(metrica="wr", asse="games", finestra="20", dividi=None, per="suo", ordina="n", basso="report", solo_meta=False, vista="chart", con="rest", vs_modo="all", dec_modo="attacco",
                    linea_dec=None)

    def reset(self):
        """Tutte le partite, come all'apertura: niente filtri ne' situazioni, il grafico e la cartella di partenza (le finestre staccate restano)."""
        self.filtri = {}
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
        if cosa in ("metrica", "asse", "finestra", "dividi"):
            self.disegna_grafico()
            if cosa in ("asse", "finestra") and "compare" in self.visibili():
                self.disegna_confronto()
        elif cosa == "con":
            self.disegna_confronto()
        else:
            self.disegna_report()

    def cambia_vista(self, k):
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

    def cambia_meta(self):
        self.solo_meta = not self.solo_meta
        self.sincronizza()
        self.disegna_matchup()

    def scelte(self):
        """Le partite del tipo e della situazione."""
        return DA.filtra(self.righe or [], self.filtri, self.tipo)

    # ------------------------------------------------------------ il disegno
    def disegna(self):
        if self.righe is None:
            return
        self.sporca = False
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
            t.opzioni(voci, lambda v, k=k: self.metti_filtro(k, v), etichette={"Any": "Any", **{v: DA.etichetta(k, v) for v, _n in vv}})
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
        bordo = C["accento"] if on else "#3a3a40"
        t.campo.configure(bg="#0f2a38" if on else "#101014", highlightbackground=bordo)
        t.campo.bind("<Leave>", lambda e, b=bordo: t.campo.configure(highlightbackground=b))
        lab = getattr(self, "lab_filtri", {}).get(k)
        if lab is not None:
            lab.configure(fg=C["accento"] if on else C["grigio"])

    def disegna_numeri(self):
        c = self.cv_num
        c.delete("all")
        if self.righe is None:
            return
        F = self.F
        r = self.scelte()
        tot = DA.conti([x for x in self.righe if x["tipo"] == self.tipo])
        k = DA.conti(r)
        W = max(c.winfo_width(), 600)
        n_f = sum(1 for v in self.filtri.values() if v is not None)
        dy = 0
        c.create_text(16, 14, text=(f"THIS SITUATION · {k['n']} GAMES" if n_f else f"ALL {self.tipo.upper()} GAMES · {k['n']}"), anchor="w", fill=C["muto"], font=F(7, True))
        xd = W - 46        # a destra la rotellina dei numeri
        if n_f:
            i_ = c.create_text(xd, 14, text=f"vs all your {self.tipo.lower()} games: {tot['wr'] if tot['wr'] is not None else '-'}%", anchor="e", fill=C["grigio"], font=F(7))
            xd = (c.bbox(i_) or (xd, 0, xd, 0))[0] - 14
        if k["n"] and k["n"] < 30:      # in alto, accanto: in fondo usciva dalla tela
            c.create_text(xd, 14, text="under 30 games: a hint, not a fact", anchor="e", fill=C["arancio"], font=F(7, True))
        # i numeri scelti con la rotellina (13 nov 2026, Autore: «in alto a dx creiamo una rotellina di impostazioni con i 6 dati che vogliamo avere su
        # questa tabella»): numeri_partite.CATALOGO, la scelta in dati_analizzatore.numeri_scelti
        val = NP.valori(r, [x for x in self.righe if x["tipo"] == self.tipo])
        toni = {"su": C["azzurro"], "giu": C["rosso"], "neutro": C["testo"], "vuoto": C["muto"]}
        tess = [(NP.NOMI[k_].upper(), val[k_][0], toni[val[k_][1]], val[k_][2]) for k_ in DA.numeri_scelti() if k_ in val]
        # la rotellina, in alto a destra
        i_r = c.create_text(W - 14, 14, text="⚙", anchor="e", fill=C["accento"], font=F(12, True))
        bb_r = c.bbox(i_r)
        c._box_rotella = (bb_r[0] - 6, bb_r[1] - 4, bb_r[2] + 6, bb_r[3] + 4)
        if not tess:
            c.create_text(16, 60, text="No numbers picked: click ⚙ and tick the ones you want here.", anchor="w", fill=C["grigio"], font=F(9))
            return
        cw = (W - 32) / len(tess)
        for i, (a, v, col, s) in enumerate(tess):
            x = 16 + i * cw
            # piu' aria fra nome, numero e riga sotto (12 nov 2026, Autore: «i testi qui sono tutti incollati, gestisci meglio le spaziature»)
            c.create_line(x, 32 + dy, x, 96 + dy, fill=col, width=2)
            c.create_text(x + 12, 36 + dy, text=a, anchor="nw", fill=C["muto"], font=F(7, True))
            c.create_text(x + 12, 65 + dy, text=v, anchor="w", fill=col, font=F(17, True))
            c.create_text(x + 12, 89 + dy, text=s, anchor="w", fill=C["grigio"], font=F(7))

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
            f.title("Performance · Numbers")
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
        c.create_text(12, 16, text=f"THE NUMBERS ON TOP · {len(scelti)} of {NP.MASSIMO} · tick the ones you want to see", anchor="w", fill=C["azzurro"],
                      font=F(8, True))
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
        else:
            ya, yb = 0.0, max(ys) * 1.15 or 1.0
        xa, xb = min(xs), max(xs) if max(xs) > min(xs) else min(xs) + 1
        c._scala = (x0, y0, x1, y1, xa, xb, ya, yb)
        sx = lambda x: x0 + (x - xa) / (xb - xa) * (x1 - x0)
        sy = lambda y: y1 - (y - ya) / (yb - ya) * (y1 - y0)
        passo = 10 if metrica in ("wr", "mull") else max(1, round((yb - ya) / 5))
        v = ya
        while v <= yb + 1e-9:
            yy = sy(v)
            c.create_line(x0, yy, x1, yy, fill="#3a3a42" if metrica == "wr" and abs(v - 50) < 1e-9 else "#26262c")
            c.create_text(x0 - 8, yy, text=f"{v:.0f}{'%' if metrica in ('wr', 'mull') else ''}", anchor="e", fill=C["muto"], font=F(7))
            v += passo
        etx = (lambda x: f"game {int(x)}") if asse == "games" else (lambda x: datetime.date.fromordinal(int(x)).strftime("%d %b"))
        c.create_text(x0, y1 + 12, text=etx(xa), anchor="w", fill=C["muto"], font=F(7))
        c.create_text(x1, y1 + 12, text=etx(xb), anchor="e", fill=C["muto"], font=F(7))
        tratti, etichette = [], []
        for i, (n, p) in enumerate(lin):
            col = colori[i % len(colori)]
            pts = [(sx(x), sy(y)) for x, y in p]
            if len(pts) == 1:
                pts = [pts[0], (pts[0][0] + 1, pts[0][1])]
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
            c.create_text(x1 + 8, y_et, text=f"{corto(str(n).strip(), 24)}  {v_:.0f}{'%' if metrica in ('wr', 'mull') else ''}", anchor="w", fill=col,
                          font=F(7, True))
        c._img = DG.tratti(W, H, linee=tratti)
        c.create_image(0, 0, image=c._img, anchor="nw")
        c.create_text((x0 + x1) / 2, y0 - 12, text=titolo, anchor="n", fill=C["grigio"], font=F(7))
        return sx, sy

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
        n_f = sum(1 for v in self.filtri.values() if v is not None)
        vs = self.mostra_vs_filtro and n_f
        base_g = [x for x in self.righe if x["tipo"] == self.tipo] if vs else r
        if vs:
            extra.append(("This filter", {x.get("partita") for x in r}))
        if self.linea_dec:          # la riga di Decisions scelta: le sue partite come linea in piu' (ricalcolata coi filtri di adesso)
            riga_ = next((c_ for c_ in DEC.tabella(r, self.linea_dec[0], self.dec_f.get(self.linea_dec[0])) if c_["nome"] == self.linea_dec[1]), None)
            if riga_ and riga_["ids"]:
                extra.append((("Attack: " if self.linea_dec[0] == "attacco" else "Block: ") + self.linea_dec[1], riga_["ids"]))
        lin = [(n, p) for n, p in DA.linee(base_g, self.metrica, self.asse, self.finestra, None if vs else self.dividi, extra=extra) if p]
        if vs and lin:
            lin[0] = ("All games", lin[0][1])
        tit = {"wr": "win rate", "n": "games", "turni": "average length in your turns", "mull": "mulligan rate"}[self.metrica]
        fin = "" if self.metrica == "n" else (", cumulative" if self.finestra == "cum" else f", last {self.finestra} games")
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
                    c.create_line(xx, 16, xx, H - 44 - banda, fill="#3a3a42", dash=(3, 3))
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
        c.create_rectangle(x0, y0, x1, y1, fill="#18181c", outline="#26262c")
        c.create_line(x0, sy(0), x1, sy(0), fill="#3a3a42")
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
        """Le colonne della tabella delle partite: (chiave, titolo, x, larghezza); mano e board si dividono quel che resta."""
        fisse = (("data", "DATE", 96), ("mio", "YOUR DECK", 150), ("suo", "OPPONENT", 150), ("via", "START", 60), ("mull", "MULLIGAN", 76), ("esito", "RESULT", 64), ("turni", "TURNS", 56))
        out, x = [], 8
        for k, t, w in fisse:
            out.append((k, t, x, w)); x += w
        resto = max(300, W - x - 8)
        out.append(("mano", "YOUR OPENING HAND", x, resto * 0.45)); x += resto * 0.45
        out.append(("board", "THE BOARD AT THE END · you / opponent", x, resto * 0.55))
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
        lista.bind("<Leave>", lambda e: e.widget.delete("sopra"))
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
        w.title("Performance · Games")
        w.configure(bg=C["scheda"])
        w.geometry(f"{max(self.pan.winfo_width(), 1000)}x560+{self.pan.winfo_rootx() + 40}+{self.pan.winfo_rooty() + 60}")
        testa = tk.Frame(w, bg=C["cap"]); testa.pack(fill="x")
        tk.Label(testa, text="PERFORMANCE · GAMES", bg=C["cap"], fg=C["titolo"], font=F(10, True)).pack(side="left", padx=(16, 10), pady=10)
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
        chiave = ORDINI_PARTITE[k_o]
        nulli = [x for x in self.scelte() if chiave(x) is None]
        c._partite = sorted([x for x in self.scelte() if chiave(x) is not None], key=chiave, reverse=not cresce) + nulli       # chi non ha il dato in fondo
        c._col = self.colonne_partite(max(c.winfo_width(), 700))
        t = c.testa
        t.delete("all")
        Wt = max(t.winfo_width(), 700)
        t.create_text(2, 10, text=f"GAMES IN THIS SITUATION · {len(c._partite)}", anchor="w", fill=C["muto"], font=F(7, True))
        t.create_text(Wt - 40, 10, text="click a hand or a board: it opens the table of that game, turn by turn", anchor="e",
                      fill=C["muto"], font=F(7))
        d = DG.Disegno(28, 22)       # il segno per staccarla (o rimetterla sotto il grafico), come le cartelle
        _segno_stacca(d, 14, 11, C["accento"] if self.partite_fuori else C["grigio"], bool(self.partite_fuori))
        c._img_segno = d.foto()
        t.create_image(Wt - 30, 0, image=c._img_segno, anchor="nw")
        for k_, tit, x, _w in c._col:
            on = k_ == k_o
            t.create_text(x, 33, text=tit + (("  ↑" if cresce else "  ↓") if on else ""), anchor="w",
                          fill=C["accento"] if on else C["titolo"] if k_ in ORDINI_PARTITE else C["muto"], font=F(7, True))
        t.create_line(0, 43, max(t.winfo_width(), 700), 43, fill=C["filo"])
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
                c.create_rectangle(0, y, W, y + ALTO_PARTITA, fill="#202024", outline="", tags=("riga", "fondo"))
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
                    col, font = (C["azzurro"] if x_["vinta"] else C["rosso"]), F(8, True)
                elif k == "turni":
                    testo = str(x_["turno"]) if x_.get("turno") else "-"
                elif k == "via":
                    testo = x_.get("partenza") or "-"
                elif k == "mull":       # la sua colonna (12 nov 2026, Autore: «aggiungi anche la colonna mulligan cosi' esce dallo start»)
                    n_ = x_.get("mulligan")
                    testo = "-" if n_ is None else str(n_)
                    col = C["muto"] if not n_ else C["arancio"]
                elif k == "mano":
                    testo, col = self.testo_mano(fo), C["titolo"] if fo else C["muto"]
                elif k == "board":
                    testo, col = self.testo_board(fo), C["titolo"] if fo else C["muto"]
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

    def testo_board(self, fo):
        """La board all'ultimo stato: le tue magie in campo, poi quante sue."""
        if not fo or not fo["ultima"] or not fo["ultima"][2]:
            return "not in the logs"
        import mazzi_salvati as MS
        f = fo["ultima"][2]
        mie = [c_[0] for c_ in f["mio"] if not MS.e_terra(c_[0])]
        sue = [c_[0] for c_ in f["suo"] if not MS.e_terra(c_[0])]
        return (", ".join(mie) or "no permanents") + f"  /  opponent: {len(sue)} permanent{'s' if len(sue) != 1 else ''}"

    def partita_a(self, c, e):
        """(partita, colonna) sotto il puntatore, o (None, None)."""
        y = c.canvasy(e.y)
        i = int(y // ALTO_PARTITA)
        partite = getattr(c, "_partite", [])
        if not 0 <= i < len(partite):
            return None, None
        k = next((k for k, _t, x, w in getattr(c, "_col", []) if x <= e.x < x + w), None)
        return partite[i], k

    def sopra_partita(self, e):
        c = e.widget
        c.delete("sopra")
        x_, k = self.partita_a(c, e)
        c.configure(cursor="hand2" if x_ is not None else "")
        if x_ is None:
            return
        # la riga si schiarisce appena, senza cornice e trasparente (12 nov 2026, Autore: «togli la cornice di selezione blu ... evidenziala
        # delicatamente», poi «la selezione sulla riga deve essere trasparente»): un velo bianco al 7% sopra la riga, la mano o la board al 12%
        i = int(c.canvasy(e.y) // ALTO_PARTITA)
        W = max(c.winfo_width(), 700)
        d = DG.Disegno(W, ALTO_PARTITA)
        d.rett(0, 0, W, ALTO_PARTITA, riempi=(255, 255, 255, 18))
        if k in ("mano", "board"):
            x, w = next((x, w) for k_, _t, x, w in c._col if k_ == k)
            d.rett(x - 6, 0, x + w - 4, ALTO_PARTITA, riempi=(255, 255, 255, 14), raggio=3)
        c._img_sopra = d.foto(veloce=True)
        c.create_image(0, i * ALTO_PARTITA, image=c._img_sopra, anchor="nw", tags="sopra")

    def clic_partita(self, e):
        c = getattr(e, "widget", None) or self.tabella_partite()
        x_, k = self.partita_a(c, e)
        if x_ is not None:
            # il replay parte sempre dall'inizio, la mano tenuta (12 nov 2026, Autore: «i replay partono tutti dalla fine e mai dall'inizio»)
            self.apri_board(x_, "inizio")

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
        f = getattr(self, "fin_board", None)
        if f is None or not f.winfo_exists():
            f = self.fin_board = tk.Toplevel(self.fr); f.configure(bg=C["scheda"])
            f.title("The board")
            f.geometry(self.posto_board())
            f.bind("<Escape>", lambda e: self.chiudi_pila() if getattr(self, "_pila_aperta", None) else f.destroy())
            f.bind("<Left>", lambda e: self.passo_board(-1))
            f.bind("<Right>", lambda e: self.passo_board(1))
            testa_b = tk.Frame(f, bg=C["cap"]); testa_b.pack(fill="x")
            self.l_board = tk.Label(testa_b, text="", bg=C["cap"], fg=C["titolo"], font=F(10, True), anchor="w", padx=16, pady=10)
            self.l_board.pack(side="left", fill="x", expand=True)
            # Moments (quello di sempre) o Every action, azione per azione (12 nov 2026, Autore: «il replayer migliore in circolazione ... basta che non
            # perdiamo assolutamente cio' che abbiamo adesso»)
            self.b_modi = {}
            # i salti e il segnalibro (12 nov 2026, «Sì, prosegui» sui salti e i segnalibri): il clic va avanti, col Maiuscolo indietro; tasti C, S, O, B
            self.b_salti = {}
            for k_, n_ in (("comb", "Combat ›"), ("spell", "Spell ›"), ("tappato", "Opp. tapped out ›")):
                b_ = pulsante_solido(tk, F, testa_b, n_, False, lambda k_=k_: self.salta(k_), alto=26, bg=C["cap"], colori=GRIGI)
                b_.configure(width=150 if k_ == "tappato" else 96); b_.pack(side="left", padx=(0, 6), pady=8)
                b_.bind("<Shift-Button-1>", lambda e, k_=k_: (self.salta(k_, -1), "break")[1])
                self.b_salti[k_] = b_
            self.b_segna = pulsante_solido(tk, F, testa_b, "Bookmark", False, self.segna_board, alto=26, bg=C["cap"], colori=("#3a3220", "#4a4028", "#8a6d1c"))
            self.b_segna.configure(width=120); self.b_segna.pack(side="left", padx=(6, 12), pady=8)
            for tasto, k_ in (("c", "comb"), ("s", "spell"), ("o", "tappato")):
                f.bind(f"<{tasto}>", lambda e, k_=k_: self.salta(k_))
                f.bind(f"<{tasto.upper()}>", lambda e, k_=k_: self.salta(k_, -1))
            f.bind("<b>", lambda e: self.segna_board())
            for k_, n_ in (("azioni", "Every action"), ("momenti", "Moments")):
                b_ = pulsante_solido(tk, F, testa_b, n_, False, lambda k_=k_: self.cambia_modo_board(k_), alto=26, bg=C["cap"], colori=GRIGI)
                b_.configure(width=120); b_.pack(side="right", padx=(0, 8), pady=8)
                self.b_modi[k_] = b_
            f.bind("<Prior>", lambda e: self.turno_board(-1))
            f.bind("<Next>", lambda e: self.turno_board(1))
            self.cv_passi = tk.Canvas(f, bg=C["scheda"], highlightthickness=0, bd=0, height=40); self.cv_passi.pack(fill="x", padx=12, pady=(10, 4))
            self.cv_passi.bind("<Button-1>", self.clic_passo)
            # in fondo i comandi di un replayer (12 nov 2026, Autore: «visto che abbiamo costruito una board che e' un player, metti in fondo le classiche
            # funzioni di un replayer»): inizio, indietro, play e pausa, avanti, fine, la timeline da cliccare o trascinare, la velocita'
            self.cv_ctrl = tk.Canvas(f, bg=C["cap"], highlightthickness=0, bd=0, height=ALTO_CTRL, cursor="hand2")
            self.cv_ctrl.pack(side="bottom", fill="x")
            self.cv_ctrl.bind("<Configure>", lambda e: self.disegna_controlli())
            self.cv_ctrl.bind("<Button-1>", self.clic_controlli)
            self.cv_ctrl.bind("<B1-Motion>", self.trascina_timeline)
            f.bind("<space>", lambda e: self.play_board())
            f.bind("<Home>", lambda e: self.vai_board(0))
            f.bind("<End>", lambda e: self.vai_board(10 ** 6))
            f.bind("<t>", lambda e: self.vai_svolta())
            f.bind("<Destroy>", lambda e: e.widget is f and self.via_hover(), add="+")
            f.bind("<Destroy>", lambda e: e.widget is f and self.ferma_board(), add="+")
            self.cv_board = tk.Canvas(f, bg="#141418", highlightthickness=1, highlightbackground=C["filo"], bd=0)
            self.cv_board.pack(fill="both", expand=True, padx=12, pady=(4, 8))
            self.cv_board.bind("<Configure>", lambda e: self.disegna_board())
            self.cv_board.bind("<Button-1>", self.clic_pila)
            self.cv_board.bind("<Motion>", self.sopra_carta_board)
            self.cv_board.bind("<Leave>", self.via_hover)
        self.ferma_board()
        self._pila_aperta = None
        self._board = dict(x=x_, passi=passi, i=len(passi) - 1 if dove == "fine" else 0, play=False, vel=getattr(self, "_vel_board", 1.0), modo="momenti",
                           momenti_passi=passi)
        self._board["svolta"] = self.svolta(passi, x_["vinta"])
        if getattr(self, "_modo_board", "momenti") == "azioni":      # resta la scelta dell'ultima volta
            self.cambia_modo_board("azioni", ridisegna=False)
            if dove != "fine":      # in Every action dalla prima azione
                self._board["i"] = 0
        for k_, b_ in self.b_modi.items():
            b_.metti({"azioni": "Every action", "momenti": "Moments"}[k_], k_ == self._board["modo"])
        esito = "won" if x_["vinta"] else "lost"
        self.l_board.configure(text=f"{x_['quando']:%d %b %Y %H:%M}  ·  {(x_.get('mio') or '-').strip()} vs {x_.get('suo') or '-'}  ·  {esito}"
                               + (f" on turn {x_['turno']}" if x_.get("turno") else "") + (f"  ·  {x_['partenza'].lower()}" if x_.get("partenza") else ""))
        f.title(f"The board · {(x_.get('mio') or '').strip()} vs {x_.get('suo') or ''}")
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
        """Play: un momento ogni 1,6 s diviso la velocita'; arrivato in fondo si ferma. Play in fondo riparte dall'inizio."""
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
        self._play_id = self.fin_board.after(int(1600 / b["vel"]), self.giro_board)

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
        self._play_id = f.after(int(1600 / b["vel"]), self.giro_board)

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
        chiave = (W, id(b["passi"]), b.get("svolta"), b["play"], sopra, b["vel"])
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
                d.cerchio(cx, cy, r, riempi="#2e2e36" if on else "#202026", bordo="#3a3a42", larghezza=1)
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
            d.linea([(t0, sy(0)), (t1, sy(0))], "#3a3a42", 1)
        fmax = max([1] + [max(z["forza"]) for z in m])
        larga_b = max(2, min(10, (t1 - t0) / max(1, n) / 3))
        for i, z in enumerate(m):
            hm, hs = z["forza"][0] / fmax * (f1 - f0), z["forza"][1] / fmax * (f1 - f0)
            if hm:
                d.rett(pos(i) - larga_b - 0.5, f1 - hm, pos(i) - 0.5, f1, riempi=(36, 186, 255, 150))
            if hs:
                d.rett(pos(i) + 0.5, f1 - hs, pos(i) + larga_b + 0.5, f1, riempi=(240, 173, 78, 150))
        if n > 1:
            d.linea([(pos(i), sy(z["vite"][1])) for i, z in enumerate(m)], "#f0ad4e", 1.6)
            d.linea([(pos(i), sy(z["vite"][0])) for i, z in enumerate(m)], "#24baff", 1.8)
        if sv is not None:      # la stella del punto di svolta
            import math as _m
            sx_, sy_ = pos(sv), 10
            pts = [(sx_ + (7 if j % 2 == 0 else 3) * _m.cos(-_m.pi / 2 + j * _m.pi / 5), sy_ + (7 if j % 2 == 0 else 3) * _m.sin(-_m.pi / 2 + j * _m.pi / 5))
                   for j in range(10)]
            d.poligono(pts, riempi="#ffd23f")
        d.linea([(0, ALTO_GRAF), (W, ALTO_GRAF)], "#26262c", 1)
        d.linea([(t0, cy), (t1, cy)], "#3a3a42", 4)
        for i, p_ in enumerate(b["passi"]):
            nome = p_[0]
            mio_ = nome.startswith("You") or nome == "Opening hand"
            d.cerchio(pos(i), cy, 3.2 if n <= 60 else 1.6, riempi="#24baff" if mio_ else "#8a8a92")
            if i == sv:
                d.cerchio(pos(i), cy, 5.5, bordo="#ffd23f", larghezza=1.6)
        # il punto di svolta e la velocita'
        self._box_vel, self._box_svolta = [], None
        vx = W - 150
        for v in (0.5, 1.0, 2.0):
            on = abs(b["vel"] - v) < 1e-9
            d.rett(vx, cy - 12, vx + 42, cy + 12, riempi="#0f86cc" if on else "#202026", bordo="#0f86cc" if on else "#3a3a42", larghezza=1, raggio=4)
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
            if s_.get("partita") == b["x"].get("partita") and s_.get("modo") == b.get("modo", "momenti") and 0 <= s_.get("i", -1) < n:
                xs_ = pos(s_["i"])
                c.create_polygon(xs_ - 5, cy - 20, xs_ + 5, cy - 20, xs_ + 5, cy - 9, xs_, cy - 13, xs_ - 5, cy - 9, fill="#ffd23f", outline="")
        c.create_text(t0 - 10, sy(m[0]["vite"][0]) if m else 20, text="LIFE", anchor="e", fill=grigio, font=F(6, True))
        c.create_text(t0 - 10, (f0 + f1) / 2, text="POWER", anchor="e", fill=grigio, font=F(6, True))
        if m:
            z = m[b["i"]]
            c.create_text(t1 + 14, 20, text=f"you {z['vite'][0]}", anchor="w", fill="#24baff", font=F(8, True))
            c.create_text(t1 + 14, 36, text=f"opponent {z['vite'][1]}", anchor="w", fill="#f0ad4e", font=F(8, True))
            c.create_text(t1 + 14, (f0 + f1) / 2 + 2, text=f"power {z['forza'][0]} vs {z['forza'][1]}", anchor="w", fill=grigio, font=F(7))
        if sv is not None:
            c.create_text(W - 81, 20, text="★ Turning point", fill="#ffd23f", font=F(7, True))
        for x0_, x1_, v in self._box_vel:
            on = abs(b["vel"] - v) < 1e-9
            c.create_text((x0_ + x1_) / 2, cy, text=("0.5×" if v == 0.5 else f"{v:.0f}×"), fill="#ffffff" if on else grigio, font=F(7, True))
        nome = b["passi"][b["i"]][0]
        c.create_text(W - 166, cy - 7, text=nome + ("   ★" if b["i"] == sv else ""), anchor="e", fill=bianco, font=F(9, True))
        c.create_text(W - 166, cy + 10, text=f"{b['i'] + 1} / {n}   ·   keys: space, arrows, PgUp/PgDn turn, Home, End, T", anchor="e", fill=grigio, font=F(7))

    def clic_controlli(self, e):
        b = getattr(self, "_board", None)
        if not b:
            return
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
        else:
            ok = lambda i: self.tappato(ps[i][1]) and not (i > 0 and self.tappato(ps[i - 1][1]))
        i = b["i"] + d
        while 0 <= i < len(ps):
            if ok(i):
                self.ferma_board()
                self.vai_board(i)
                return i
            i += d
        return None

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

    def immagine_carta(self, nome, w, tappata):
        """La carta in piccolo dalla miniatura cotta (capsule.cuoci), girata se tappata; None se la miniatura non c'e'."""
        cache = self.__dict__.setdefault("_img_carte", {})
        k = (nome, w, tappata)
        if k not in cache:
            try:
                import capsule
                from PIL import Image, ImageTk
                im = Image.open(capsule.file_mini(nome)).convert("RGBA")
                im = im.resize((w, round(w * im.height / im.width)), Image.LANCZOS)
                if tappata:
                    im = im.rotate(90, expand=True)
                cache[k] = ImageTk.PhotoImage(im)
            except Exception:      # noqa: BLE001 - senza miniatura il riquadro col nome
                cache[k] = None
        return cache[k]

    def immagine_token(self, w, tappata):
        """Il disegno di default delle pedine, che non hanno un'immagine loro (12 nov 2026, Autore: «i token nei replayer non hanno disegni associati,
        attacca un disegno token di default»): una carta scura col bordo, la barra del nome, nel riquadro dell'arte un emblema d'oro (cerchio e stella a sei
        punte) e sotto lo spazio per il nome; girata se tappata. Disegnata nitida (disegni), una volta per misura."""
        cache = self.__dict__.setdefault("_img_token", {})
        k = (w, tappata)
        if k not in cache:
            h = round(w * 279 / 200)
            d = DG.Disegno(w, h)
            d.rett(0, 0, w, h, riempi="#1b1b22", bordo="#8a8a94", larghezza=1.4, raggio=max(4, w * 0.06))
            m = max(4, w * 0.06)
            d.rett(m, m, w - m, m + h * 0.07, riempi="#2c2c35", raggio=2)                       # la barra del nome
            a0, a1 = m + h * 0.09, h * 0.66                                                     # il riquadro dell'arte
            d.rett(m, a0, w - m, a1, riempi="#24242d", bordo="#3a3a44", larghezza=1, raggio=2)
            cx, cy, r = w / 2, (a0 + a1) / 2, min(w, a1 - a0) * 0.30
            d.cerchio(cx, cy, r, bordo="#c9a24a", larghezza=max(1.2, w * 0.018))
            import math as _m
            punte = lambda fase: [(cx + r * 0.78 * _m.cos(fase + i * 2 * _m.pi / 3), cy + r * 0.78 * _m.sin(fase + i * 2 * _m.pi / 3)) for i in range(3)]
            d.poligono(punte(-_m.pi / 2), riempi="#c9a24a")
            d.poligono(punte(_m.pi / 2), riempi="#a8853a")
            d.rett(m, h * 0.69, w - m, h * 0.76, riempi="#2c2c35", raggio=2)                   # la riga del tipo
            im = d.immagine()
            if tappata:
                im = im.rotate(90, expand=True)
            from PIL import ImageTk
            cache[k] = ImageTk.PhotoImage(im)
        return cache[k]

    def disegna_board(self):
        """La tavola del momento: il campo dell'avversario, il tuo, la tua mano; accanto a ogni campo il cimitero e l'esilio di quel giocatore; le carte arrivate
        dal momento prima col filo azzurro e «NEW»; forza e costituzione sulle creature; a destra il racconto di cosa e' successo (12 nov 2026, Autore:
        «aggiungiamo cimitero e esilio, facciamo un replayer piu' avanzato e migliore degli attuali, di nuova generazione»)."""
        c = getattr(self, "cv_board", None)
        b = getattr(self, "_board", None)
        if c is None or not c.winfo_exists() or not b:
            return
        F = self.F
        import mazzi_salvati as MS
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
            cp.create_rectangle(x, 4, x + w, 32, fill="#0f86cc" if on else "#202024", outline="#ffd23f" if i == b.get("svolta") else
                                ("#0f86cc" if on else ("#3a3a40" if mio_ else "#2c2c32")))
            cp.create_text(x + w / 2, 18, text=nome, fill="#ffffff" if on else (C["testo"] if mio_ else C["grigio"]), font=F(7, True))
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
        prima_pile = None
        anima = getattr(self, "_anima", False)
        self._anima = False
        self.ferma_animazione()
        self._pila_prima, self._pila_ora = getattr(self, "_pila_ora", None), None
        self._box_zona, self._nuove = [], []
        self._box_pile, self._box_carte = [], []
        self.via_hover()
        W, H = max(c.winfo_width(), 900), max(c.winfo_height(), 560)
        Wt = W - LARGA_RACCONTO - 12          # la tavola; a destra il racconto
        nome, f, _t, rel = b["passi"][b["i"]][:4]
        prima = b["passi"][b["i"] - 1][1] if b["i"] > 0 else None
        if getattr(self, "b_segna", None) is not None:
            segnato_ = DA.segnato(b["x"].get("partita"), b.get("modo", "momenti"), b["i"])
            self.b_segna.metti("Bookmarked ★" if segnato_ else "Bookmark", segnato_)
        self._pos_id, self._pos_vita = {}, {}       # dove stanno le carte (per id di Arena) e i cuori delle vite: le frecce partono e arrivano li'
        LARGA_PILE = 150

        def contate(lst):
            out = {}
            for n_ in lst:
                out[n_] = out.get(n_, 0) + 1
            return out

        def pila(x0, y0, larga, alta, tit, carte, colore, chiave):
            """Il cimitero o l'esilio: il titolo col numero, l'ultima carta arrivata, il clic apre tutte."""
            c.create_rectangle(x0, y0, x0 + larga, y0 + alta, fill="#18181e", outline="#2c2c34")
            c.create_text(x0 + 8, y0 + 11, text=f"{tit} · {len(carte)}", anchor="w", fill=colore, font=F(7, True))
            if carte:
                w = max(40, min(larga - 24, int((alta - 30) * 200 / 279)))
                img = self.immagine_carta(carte[0], w, False)       # in cima la piu' recente: Arena scrive la pila dalla carta arrivata per ultima
                cx_ = x0 + larga / 2 - w / 2
                if img is not None:
                    c.create_image(cx_, y0 + 22, image=img, anchor="nw")
                    self._box_carte.append((cx_, y0 + 22, cx_ + w, y0 + 22 + round(w * 1.395), carte[0]))
                else:
                    c.create_rectangle(cx_, y0 + 22, cx_ + w, y0 + 22 + round(w * 1.395), fill="#26262c", outline="#4a4a52")
                    c.create_text(cx_ + w / 2, y0 + 22 + w * 0.7, text=carte[0], width=w - 8, fill=C["titolo"], font=F(7, True), justify="center")
                self._box_pile.append((x0, y0, x0 + larga, y0 + alta, tit, chiave, carte))
            else:
                c.create_text(x0 + larga / 2, y0 + alta / 2 + 6, text="empty", fill=C["muto"], font=F(7))

        def info(xd, y, voci):
            """A destra della testa di una zona: [(icona, testo)] da destra a sinistra, l'icona grigia accanto al numero (12 nov 2026, Autore: «accanto a
            life e cards in hand metti i loghi del cuore e due carte in mano grigetti»)."""
            for voce in voci:
                ic, t_ = voce[0], voce[1]
                i_ = c.create_text(xd, y, text=t_, anchor="e", fill=C["titolo"], font=F(10, True))
                bb = c.bbox(i_)
                xd = (bb[0] if bb else xd - 30) - 6
                c.create_image(xd, y, image=self.icona_board(ic), anchor="e")
                if len(voce) > 2:
                    self._pos_vita[voce[2]] = (xd - 20, y - 10, (bb[2] if bb else xd + 30), y + 10)
                xd -= 30

        def zona(tit, carte, y, alto, colore, destra="", vecchie=None, largo=Wt, zkey=""):
            c.create_text(16, y + 12, text=tit, anchor="w", fill=colore, font=F(8, True))
            if isinstance(destra, list):
                info(largo - 16, y + 12, destra)
            elif destra:
                c.create_text(largo - 16, y + 12, text=destra, anchor="e", fill=C["titolo"], font=F(9, True))
            # le stesse carte insieme, con quante; nuove = piu' copie di prima
            gruppi, ids = {}, {}
            for c_ in carte:
                k = (c_[0], c_[1], c_[2], c_[3] if len(c_) > 3 else None, c_[4] if len(c_) > 4 else None)
                gruppi[k] = gruppi.get(k, 0) + 1
                if len(c_) > 5 and c_[5] is not None:
                    ids.setdefault(k, []).append(c_[5])
            prima_n = contate(vecchie) if vecchie is not None else None
            ora_n = contate([c_[0] for c_ in carte])
            ordine = sorted(gruppi, key=lambda g: (MS.e_terra(g[0]), g[2], g[0]))

            def misura_area(lista, alto_a, larga_a, massimo=150):
                """La carta piu' grande con cui le carte ci stanno tutte nel riquadro, a capo compreso (le tappate occupano l'altezza in larghezza)."""
                for w in range(min(massimo, int((alto_a - 4) * 200 / 279)), 30, -4):
                    h = round(w * 279 / 200)
                    xx, righe_ = 0, 1
                    for g in lista:
                        ww = h if g[1] else w
                        if xx + ww > larga_a and xx > 0:
                            xx, righe_ = 0, righe_ + 1
                        xx += ww + 8
                    if righe_ * (h + 8) <= alto_a:
                        return w
                return 30

            def posa(lista, x0, y0, larga_a, alto_a, massimo=150):
                """Le carte di una lista nel riquadro (x0, y0, larga_a, alto_a), da sinistra, a capo se serve."""
                w_carta = misura_area(lista, alto_a, larga_a, massimo)
                h_carta = round(w_carta * 279 / 200)
                x, yy = x0, y0
                for g in lista:
                    n, tap, ped, pw, th = g
                    ww, hh = (h_carta, w_carta) if tap else (w_carta, h_carta)
                    if x + ww > x0 + larga_a and x > x0:
                        x, yy = x0, yy + h_carta + 8
                    if yy + hh > y0 + alto_a + 2:
                        c.create_text(x0 + larga_a, y0 + alto_a - 6, text="…", anchor="e", fill=C["grigio"], font=F(10, True))
                        break
                    ped = ped or n in DA.SENZA_FACCIA.values()      # a faccia in giu' o sconosciuta: il disegno di default col nome
                    img = self.immagine_token(w_carta, tap) if ped else self.immagine_carta(n, w_carta, tap)
                    cy = yy + (h_carta - hh)        # le tappate appoggiate in basso
                    for id_ in ids.get(g, []):
                        self._pos_id[id_] = (x, cy, x + ww, cy + hh)
                    it_ = None
                    if img is not None:
                        it_ = c.create_image(x, cy, image=img, anchor="nw")
                        self._box_zona.append((zkey, n, (x, cy, x + ww, cy + hh), tap, it_))
                        if not ped:
                            self._box_carte.append((x, cy, x + ww, cy + hh, n))
                        if ped:     # il nome della pedina sul disegno di default (sopra il riquadro della forza, che sta in basso: debug del 12 nov 2026)
                            c.create_text(x + ww / 2, cy + (hh - 16 if tap and pw is None else hh * 0.36 if tap else hh * 0.64 if pw is not None else hh * 0.80),
                                          text=n, width=ww - 8, fill=C["titolo"], font=F(7, True), justify="center")
                    else:
                        c.create_rectangle(x, cy, x + ww, cy + hh, fill="#26262c", outline="#4a4a52")
                        c.create_text(x + ww / 2, cy + hh / 2, text=n, width=ww - 10, fill=C["titolo"], font=F(7, True), justify="center")
                    nuova = prima_n is not None and ora_n.get(n, 0) > prima_n.get(n, 0)
                    if nuova and it_ is not None and not ped:
                        self._nuove.append((zkey, n, (x, cy, x + ww, cy + hh), tap, it_))
                    if nuova:       # arrivata dal momento prima
                        c.create_rectangle(x - 2, cy - 2, x + ww + 2, cy + hh + 2, outline="#24baff", width=2)
                        c.create_rectangle(x + 4, cy + 4, x + 38, cy + 18, fill="#0f86cc", outline="")
                        c.create_text(x + 21, cy + 11, text="NEW", fill="#ffffff", font=F(6, True))
                    if pw is not None and th is not None:      # forza e costituzione
                        c.create_rectangle(x + ww - 38, cy + hh - 22, x + ww - 4, cy + hh - 4, fill="#101014", outline="#e6e6ea")
                        c.create_text(x + ww - 21, cy + hh - 13, text=f"{pw}/{th}", fill="#ffffff", font=F(8, True))
                    if gruppi[g] > 1:
                        c.create_rectangle(x + ww - 28, cy + 4, x + ww - 4, cy + 22, fill="#101014", outline=C["accento"])
                        c.create_text(x + ww - 16, cy + 13, text=f"×{gruppi[g]}", fill=C["titolo"], font=F(7, True))
                    x += ww + 8

            if zkey in ("mio", "suo"):
                # il campo in due righe, come al tavolo (12 nov 2026, Autore: «1 ok, 2 a destra e 3 a sinistra»): davanti, verso il centro del tavolo, le
                # creature; dietro le terre a sinistra e gli altri permanenti (artefatti, incantesimi, planeswalker...) a destra; il suo campo e' speculare
                crea = [g for g in ordine if g[3] is not None]
                terre = [g for g in ordine if g[3] is None and MS.e_terra(g[0])]
                altri = [g for g in ordine if g[3] is None and not MS.e_terra(g[0])]
                y0, A, L = y + 26, alto - 30, largo - 32
                h_cr = A if not (terre or altri) else 0 if not crea else round(A * 0.56)
                h_di = A - h_cr - (6 if crea and (terre or altri) else 0)
                y_cr, y_di = (y0 + h_di + 6, y0) if zkey == "suo" else (y0, y0 + h_cr + 6)
                if crea:
                    posa(crea, 16, y_cr, L, h_cr)
                if terre or altri:
                    if terre and altri:
                        quota = max(0.3, min(0.7, len(terre) / (len(terre) + len(altri))))
                        l_t = round(L * quota) - 8
                        posa(terre, 16, y_di, l_t, h_di, 110)
                        c.create_line(16 + l_t + 8, y_di + 4, 16 + l_t + 8, y_di + h_di - 4, fill="#2c2c34")
                        posa(altri, 16 + l_t + 16, y_di, L - l_t - 16, h_di, 120)
                    else:
                        posa(terre or altri, 16 if terre else 16, y_di, L, h_di, 110 if terre else 120)
            else:
                posa(ordine, 16, y + 28, largo - 32, alto - 30)
            if not carte:
                c.create_text(16, y + 44, text="nothing", anchor="w", fill=C["muto"], font=F(8))
        vite = f.get("vite") or (None, None)
        cim, esi = f.get("cim") or ([], []), f.get("esi") or ([], [])
        terzo = (H - 20) / 3
        largo_campo = Wt - 2 * LARGA_PILE - 20
        c.create_rectangle(0, 0, Wt, terzo, fill="#18161a", outline="")
        vv = lambda v: str(v) if v is not None else "-"
        zona("OPPONENT'S BATTLEFIELD", f["suo"], 4, terzo - 8, C["arancio"], [("carte", str(f["n_suo"])), ("cuore", vv(vite[1]), "vita_suo")],
             [c_[0] for c_ in prima["suo"]] if prima else None, largo_campo, "suo")
        pila(largo_campo + 4, 8, LARGA_PILE - 4, terzo - 16, "GRAVEYARD", cim[1], C["arancio"], "cim_suo")
        pila(largo_campo + LARGA_PILE + 8, 8, LARGA_PILE - 4, terzo - 16, "EXILE", esi[1], C["arancio"], "esi_suo")
        c.create_line(0, terzo, Wt, terzo, fill=C["filo"])
        zona("YOUR BATTLEFIELD", f["mio"], terzo + 4, terzo - 8, C["azzurro"], [("carte", str(len(f["mano"]))), ("cuore", vv(vite[0]), "vita_mio")],
             [c_[0] for c_ in prima["mio"]] if prima else None, largo_campo, "mio")
        pila(largo_campo + 4, terzo + 8, LARGA_PILE - 4, terzo - 16, "GRAVEYARD", cim[0], C["azzurro"], "cim_mio")
        pila(largo_campo + LARGA_PILE + 8, terzo + 8, LARGA_PILE - 4, terzo - 16, "EXILE", esi[0], C["azzurro"], "esi_mio")
        c.create_line(0, 2 * terzo, Wt, 2 * terzo, fill=C["filo"])
        zona("YOUR HAND" + ("  ·  the hand you kept" if nome == "Opening hand" else ""), [(n, False, False) for n in f["mano"]], 2 * terzo + 4, terzo + 12,
             C["titolo"], [("carte", str(len(f["mano"])))], prima["mano"] if prima else None, Wt, "mano")
        # il racconto del momento
        xr = Wt + 12
        c.create_rectangle(xr, 0, W, H, fill="#18181e", outline="")
        c.create_text(xr + 14, 16, text="WHAT HAPPENED", anchor="w", fill=C["muto"], font=F(7, True))
        tit_ = c.create_text(xr + 14, 25, text=nome + ("   ★ turning point" if b["i"] == b.get("svolta") else ""), anchor="nw",
                             fill="#ffd23f" if b["i"] == b.get("svolta") else C["titolo"], font=F(10, True), width=LARGA_RACCONTO - 28)
        y = max(58, (c.bbox(tit_) or (0, 0, 0, 46))[3] + 14)     # un nome lungo va a capo verso il basso, non sopra «WHAT HAPPENED» (debug del 12 nov 2026)
        pila_box = None
        if rel and rel["tipo"] == "spell":      # la magia (o l'abilita') in pila, da cui partono le frecce verso i bersagli
            chi = "You" if rel["mio"] else "Opponent"
            c.create_text(xr + 14, y, text=f"ON THE STACK · {chi.upper()}" + (" · ABILITY OF" if rel["ab"] else ""), anchor="w",
                          fill="#b58cff", font=F(7, True))
            w_p = 130
            img = self.immagine_carta(rel["nome"], w_p, False)
            hp = round(w_p * 279 / 200)
            if img is not None:
                c.create_image(xr + 14, y + 12, image=img, anchor="nw")
                self._box_carte.append((xr + 14, y + 12, xr + 14 + w_p, y + 12 + hp, rel["nome"]))
            else:
                c.create_rectangle(xr + 14, y + 12, xr + 14 + w_p, y + 12 + hp, fill="#26262c", outline="#b58cff")
                c.create_text(xr + 14 + w_p / 2, y + 12 + hp / 2, text=rel["nome"], width=w_p - 10, fill=C["titolo"], font=F(8, True), justify="center")
            pila_box = (xr + 14, y + 12, xr + 14 + w_p, y + 12 + hp)
            self._pila_ora = (pila_box, rel["nome"])
            y += hp + 28
            dove_n = {"cim_mio": "in your graveyard", "cim_suo": "in the opponent's graveyard", "esi_mio": "in your exile", "esi_suo": "in the opponent's exile",
                      "pila": "on the stack", "mano": "in hand", "grimorio": "in the library"}
            for _i, (z_, _l, n_) in (rel.get("fuori") or {}).items():      # i bersagli che non sono in campo: una contromagia, una rianimazione
                c.create_text(xr + 14, y - 6, text=f"→ {n_ or 'a card'} {dove_n.get(z_, '')}", anchor="w", fill="#b58cff", font=F(7, True),
                              width=LARGA_RACCONTO - 28)
                y += 16
            nc = len(rel.get("colpiti") or [])
            if nc:      # l'effetto: quanti permanenti ha tolto
                c.create_text(xr + 14, y - 6, text=f"REMOVED {nc} PERMANENT{'S' if nc > 1 else ''}" + ("  ·  a sweeper" if nc >= 3 else ""), anchor="w",
                              fill="#ff5d5d", font=F(7, True))
                y += 16
        elif rel and rel["tipo"] == "comb":
            nb = len(rel["blocchi"])
            c.create_text(xr + 14, y, text=f"COMBAT · {len(rel['att'])} attacking · {nb} block{'s' if nb != 1 else ''}", anchor="w", fill="#ff6b6b",
                          font=F(7, True))
            y += 22
        self.frecce_board(c, rel, pila_box, W, H)
        if "spalla" not in b:       # cosa diceva la spalla (solo nei limited seguiti dal companion)
            try:
                import replay_log as RL
                b["spalla"] = RL.spalla(b["x"].get("partita"))
            except Exception:      # noqa: BLE001 - senza diario niente spalla
                b["spalla"] = {}
        t_passo = b["passi"][b["i"]][2]
        consigli = [(None, "THE COMPANION SAID")] + [("spalla", s_) for s_ in b["spalla"].get(t_passo, [])] if b["spalla"].get(t_passo) else []
        if b.get("modo") == "azioni":
            self.danni_board(c, b["passi"][b["i"]][5])
            righe_r = [(m_, "▸ " + t_) for m_, t_ in b["passi"][b["i"]][4]]       # quest'azione, in testa, poi la spalla, poi il resto del turno
            prima_ = [ev_ for p_ in b["passi"][:b["i"]] if p_[2] == b["passi"][b["i"]][2] for ev_ in p_[4]]
            righe_r += consigli
            if prima_:
                righe_r += [(None, "EARLIER THIS TURN")] + list(reversed(prima_))
        else:
            righe_r = self.racconto(b["i"])
            if righe_r is not None or consigli:
                righe_r = consigli + (righe_r or [])
        if righe_r is None:
            c.create_text(xr + 14, y, text="No turn record for this game.", anchor="w", fill=C["grigio"], font=F(8))
        elif not righe_r:
            c.create_text(xr + 14, y, text="Nothing cast or attacked.", anchor="w", fill=C["grigio"], font=F(8))
        for mio_, testo in righe_r or []:
            if y > H - 24:
                c.create_text(xr + 14, y, text="…", anchor="w", fill=C["grigio"], font=F(9, True))
                break
            if mio_ is None:        # un titoletto
                c.create_text(xr + 14, y + 6, text=testo, anchor="w", fill=C["muto"], font=F(7, True))
                y += 20
                continue
            sp_ = mio_ == "spalla"
            c.create_oval(xr + 14, y + 4, xr + 22, y + 12, fill="#b58cff" if sp_ else "#24baff" if mio_ else "#f0ad4e", outline="")
            forte = testo.startswith("▸ ")
            i_ = c.create_text(xr + 30, y, text=testo[2:] if forte else testo, anchor="nw", fill="#d6c8ff" if sp_ else C["titolo"] if forte else C["testo"],
                               font=F(7 if sp_ else 8, forte), width=LARGA_RACCONTO - 46)      # dall'alto: a capo non copre la riga dopo
            bb = c.bbox(i_)
            y = (bb[3] if bb else y + 16) + 6
        if anima and prima is not None:
            self.anima_board(c, prima_zone, prima_pile, prima, f)
        self.disegna_pila_aperta(c, f, W, H)
        self.disegna_controlli()

    def ferma_animazione(self):
        for a_ in getattr(self, "_anim_after", []):
            try:
                self.fin_board.after_cancel(a_)
            except Exception:      # noqa: BLE001 - gia' scattato
                pass
        self._anim_after = []
        c = getattr(self, "cv_board", None)
        if c is not None and c.winfo_exists():
            c.delete("anim")
            for it_ in getattr(self, "_nascoste", []):
                c.itemconfigure(it_, state="normal")
        self._nascoste = []

    def anima_board(self, c, prima_zone, prima_pile, prima, f):
        """Le carte che scorrono (12 nov 2026, «le carte che scorrono da una zona all'altra invece di comparire»): una carta arrivata in campo dalla tua mano
        parte da dov'era in mano (dal lato dell'avversario, dalla sua mano); una carta che lascia il campo scivola sul suo cimitero o sul suo esilio, o nella
        tua mano se ci torna. 200 ms, 12 quadri; un altro passo le chiude subito."""
        def centro(r_):
            return ((r_[0] + r_[2]) / 2, (r_[1] + r_[3]) / 2)
        mosse = []
        mano_prima = [z for z in prima_zone if z[0] == "mano"]
        usate = set()
        pila_prima = getattr(self, "_pila_prima", None)
        for zkey, n, box, tap, it_ in self._nuove:        # arrivi
            da = None
            if pila_prima and pila_prima[1] == n:       # dalla pila al campo: la magia risolta
                da = pila_prima[0]
            elif zkey == "mio":
                da = next((z for z in mano_prima if z[1] == n and id(z) not in usate), None)
                if da:
                    usate.add(id(da))
                    da = da[2]
            elif zkey == "suo":
                vs_ = self._pos_vita.get("vita_suo")
                if vs_:
                    da = (vs_[0] - 40, vs_[1], vs_[0] + 20, vs_[3] + 60)
            if da:
                mosse.append((n, tap, da, box, it_))
        ora_conta = {}
        for z in self._box_zona:
            ora_conta[(z[0], z[1])] = ora_conta.get((z[0], z[1]), 0) + 1
        for z in prima_zone:        # partenze dal campo
            if z[0] not in ("mio", "suo"):
                continue
            k_ = (z[0], z[1])
            if ora_conta.get(k_, 0) > 0:
                ora_conta[k_] -= 1
                continue
            lato = 0 if z[0] == "mio" else 1
            dove = None
            if z[1] in ((f.get("cim") or ([], []))[lato])[:3]:
                dove = next((b_[:4] for b_ in self._box_pile if b_[5] == ("cim_mio" if lato == 0 else "cim_suo")), None)
            elif z[1] in ((f.get("esi") or ([], []))[lato])[:3]:
                dove = next((b_[:4] for b_ in self._box_pile if b_[5] == ("esi_mio" if lato == 0 else "esi_suo")), None)
            elif lato == 0 and z[1] in f["mano"]:
                dove = next((zz[2] for zz in self._box_zona if zz[0] == "mano" and zz[1] == z[1]), None)
            if dove:
                mosse.append((z[1], z[3], z[2], dove, None))
        pila_ora = getattr(self, "_pila_ora", None)
        if pila_ora and not (pila_prima and pila_prima[1] == pila_ora[1]):       # una magia appena lanciata: dalla tua mano alla pila
            da = next((z[2] for z in mano_prima if z[1] == pila_ora[1]), None)
            if da:
                mosse.append((pila_ora[1], False, da, pila_ora[0], None))
        if not mosse:
            return
        quadri = 12
        oggetti = []
        for n, tap, da, a_, it_ in mosse:
            w0 = max(30, round(min(da[2] - da[0], da[3] - da[1]) if tap else da[2] - da[0]))
            img = self.immagine_carta(n, int(w0), tap)
            if img is None:
                continue
            if it_ is not None:
                c.itemconfigure(it_, state="hidden")
                self._nascoste.append(it_)
            (x0, y0), (x1, y1) = centro(da), centro(a_)
            g_ = c.create_image(x0, y0, image=img, tags="anim")
            oggetti.append((g_, x0, y0, x1, y1, it_))

        def quadro(k):
            u = k / quadri
            u = 1 - (1 - u) ** 3        # rallenta all'arrivo
            for g_, x0, y0, x1, y1, _it in oggetti:
                c.coords(g_, x0 + (x1 - x0) * u, y0 + (y1 - y0) * u)
            if k < quadri:
                self._anim_after.append(self.fin_board.after(16, lambda: quadro(k + 1)))
            else:
                self.ferma_animazione()
        self._anim_after = [self.fin_board.after(16, lambda: quadro(1))]

    def danni_board(self, c, danni):
        """I danni dell'azione: un tondo rosso col «-N» sulla carta o sul cuore colpito (la carta morta non c'e' piu': lo dice il racconto)."""
        F = self.F
        for bers, q in danni or []:
            r_ = self._pos_id.get(bers) or self._pos_vita.get(bers)
            if not r_ or not q:
                continue
            cx, cy = (r_[0] - 22, (r_[1] + r_[3]) / 2) if bers in ("vita_mio", "vita_suo") else (r_[2] - 4, r_[1] + 4)      # sul cuore: accanto, non sopra
            c.create_oval(cx - 17, cy - 17, cx + 17, cy + 17, fill="#d9534f", outline="#ffffff", width=2)
            c.create_text(cx, cy, text=f"-{q}", fill="#ffffff", font=F(10, True))

    def frecce_board(self, c, rel, pila_box, W, H):
        """Le frecce di chi interagisce con chi (12 nov 2026, Autore: «una freccia che definisce quali carte interagiscono con quali altre, per vedere
        come si e' bloccato in combattimento o contro cosa e' stato lanciato uno spot removal»): nel combattimento dal bloccante all'attaccante (gialle) e
        dall'attaccante non bloccato al giocatore o al planeswalker che attacca (rosse); per una magia o un'abilita' dalla carta in pila ai bersagli (viola).
        Curve nitide in un'immagine sola sopra la tavola; la punta sul bordo della carta."""
        if not rel:
            return
        frecce = []
        dove = lambda k: self._pos_id.get(k) or self._pos_vita.get(k)
        if rel["tipo"] == "comb":
            bloccati = {a_ for _b, aa in rel["blocchi"] for a_ in aa}
            for b_, aa in rel["blocchi"]:
                for a_ in aa:
                    if dove(b_) and dove(a_):
                        frecce.append((dove(b_), dove(a_), "#ffd23f"))
            for a_, tg in rel["att"]:
                if a_ not in bloccati and dove(a_) and dove(tg):
                    frecce.append((dove(a_), dove(tg), "#ff5d5d"))
        elif rel["tipo"] == "spell" and pila_box:
            pile = {k_: (x0, y0, x1, y1) for x0, y0, x1, y1, _t, k_, _c in getattr(self, "_box_pile", [])}
            # una magia che ha per bersaglio un giocatore e toglie i suoi permanenti (Settle the Wreckage, un sacrificio: 13 nov 2026, Autore: «dovrebbe
            # esiliare le creature attaccanti ma nel replayer la freccia punta ai punti vita del giocatore»): le frecce vanno ai permanenti, non alle vite
            sui_permanenti = bool(rel.get("colpiti")) and all(isinstance(tg, str) and tg.startswith("vita") for tg in rel["bers"])
            for tg in rel["bers"]:
                if sui_permanenti:
                    continue
                if dove(tg):
                    frecce.append((pila_box, dove(tg), "#b58cff"))
                elif (rel.get("fuori") or {}).get(tg, (None,))[0] in pile:       # un bersaglio nel cimitero o in esilio: la freccia va alla sua pila
                    frecce.append((pila_box, pile[rel["fuori"][tg][0]], "#b58cff"))
            for k_ in rel.get("colpiti") or []:      # cio' che la magia ha tolto dal campo (un board wipe: tutto quello che spazza)
                if k_ not in rel["bers"] and dove(k_):
                    frecce.append((pila_box, dove(k_), "#ff5d5d"))
            for k_ in rel.get("colpiti") or []:
                r_ = self._pos_id.get(k_)
                if r_:
                    c.create_rectangle(r_[0] - 3, r_[1] - 3, r_[2] + 3, r_[3] + 3, outline="#ff5d5d", width=3)
                    c.create_rectangle(r_[0] + 4, r_[3] - 40, r_[0] + 62, r_[3] - 24, fill="#ff5d5d", outline="")
                    c.create_text(r_[0] + 33, r_[3] - 32, text="REMOVED", fill="#ffffff", font=self.F(6, True))
        if not frecce:
            return
        d = DG.Disegno(W, H)

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
        for a, b, col in frecce:
            ca, cb = ((a[0] + a[2]) / 2, (a[1] + a[3]) / 2), ((b[0] + b[2]) / 2, (b[1] + b[3]) / 2)
            p0, p2 = bordo(a, cb), bordo(b, ca)
            dx, dy = p2[0] - p0[0], p2[1] - p0[1]
            lung = max(1.0, math.hypot(dx, dy))
            ctrl = ((p0[0] + p2[0]) / 2 - dy / lung * lung * 0.18, (p0[1] + p2[1]) / 2 + dx / lung * lung * 0.18)     # un po' curva, si leggono anche sovrapposte
            pts = [((1 - u) ** 2 * p0[0] + 2 * (1 - u) * u * ctrl[0] + u * u * p2[0], (1 - u) ** 2 * p0[1] + 2 * (1 - u) * u * ctrl[1] + u * u * p2[1])
                   for u in (i / 30 for i in range(31))]
            d.linea(pts, (0, 0, 0, 150), 6)       # l'ombra, per staccarla dalle carte
            d.linea(pts, col, 3)
            ux, uy = pts[-1][0] - pts[-3][0], pts[-1][1] - pts[-3][1]
            ul = max(1e-6, math.hypot(ux, uy))
            ux, uy = ux / ul, uy / ul
            tip = pts[-1]
            d.poligono([tip, (tip[0] - 16 * ux + 8 * uy, tip[1] - 16 * uy - 8 * ux), (tip[0] - 16 * ux - 8 * uy, tip[1] - 16 * uy + 8 * ux)], riempi=col)
            d.cerchio(p0[0], p0[1], 5, riempi=col)
        self._img_frecce = d.foto(veloce=True)
        c.create_image(0, 0, image=self._img_frecce, anchor="nw")

    def icona_board(self, k):
        """Le icone grigie della tavola: il cuore delle vite, due carte per la mano. Disegnate nitide, una volta."""
        cache = self.__dict__.setdefault("_icone_board", {})
        if k not in cache:
            L = 20
            d = DG.Disegno(L, L)
            grigio = "#9a9aa2"
            if k == "cuore":
                d.cerchio(L * 0.31, L * 0.36, L * 0.24, riempi=grigio)
                d.cerchio(L * 0.69, L * 0.36, L * 0.24, riempi=grigio)
                d.poligono([(L * 0.09, L * 0.45), (L * 0.91, L * 0.45), (L * 0.5, L * 0.92)], riempi=grigio)
            else:
                d.rett(L * 0.10, L * 0.08, L * 0.62, L * 0.78, riempi="#3a3a42", bordo=grigio, larghezza=1.3, raggio=2)
                d.rett(L * 0.36, L * 0.20, L * 0.90, L * 0.92, riempi=grigio, bordo="#141418", larghezza=1.3, raggio=2)
            cache[k] = d.foto()
        return cache[k]

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
        h.configure(bg="#101014")
        try:
            h.attributes("-topmost", True)
        except Exception:      # noqa: BLE001 - non serve fuori da Windows
            pass
        tk.Label(h, image=img, bg="#101014", bd=0).pack(padx=2, pady=2)
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
                im = Image.open(f if os.path.exists(f) else capsule.file_mini(nome)).convert("RGBA")
                im = im.resize((360, round(360 * im.height / im.width)), Image.LANCZOS)
                cache[nome] = ImageTk.PhotoImage(im)
            except Exception:      # noqa: BLE001 - senza immagine niente hover
                cache[nome] = None
            if len(cache) > 60:
                cache.pop(next(iter(cache)))
        return cache.get(nome)

    def clic_pila(self, e):
        """Il clic sulla tavola: con un cimitero o un esilio aperto, la ✕ o il clic fuori dal riquadro lo chiudono; se no il clic su una pila la apre."""
        if getattr(self, "_pila_aperta", None):
            x0, y0, x1, y1 = getattr(self, "_box_riquadro", (0, 0, 0, 0))
            cx0, cy0, cx1, cy1 = getattr(self, "_box_chiudi", (0, 0, 0, 0))
            if not (x0 <= e.x <= x1 and y0 <= e.y <= y1) or (cx0 <= e.x <= cx1 and cy0 <= e.y <= cy1):
                self.chiudi_pila()
            return None
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
        d.rett(rx0, ry0, rx1, ry1, riempi="#18181e", bordo="#3a3a44", larghezza=1.2, raggio=8)
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
                c.create_rectangle(x, y, x + w, y + h, fill="#26262c", outline="#4a4a52")
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
        pc = "%" if c._metrica in ("wr", "mull") else ""
        for i, (n, p) in enumerate(c._linee):
            q = min(p, key=lambda t: abs(t[0] - xv))
            righe.append((f"{n}: {q[1]:.1f}{pc}", c._colori[i % len(c._colori)]))
        etx = f"game {round(xv)}" if c._asse == "games" else datetime.date.fromordinal(int(round(xv))).strftime("%d %b %Y")
        bx = e.x + 12 if e.x < (x0 + x1) / 2 else e.x - 170
        c.create_rectangle(bx, y0 + 4, bx + 160, y0 + 22 + 15 * len(righe), fill="#101014", outline="#3a3a42", tags="punta")
        c.create_text(bx + 8, y0 + 12, text=etx, anchor="w", fill=C["titolo"], font=self.F(7, True), tags="punta")
        for j, (t, col) in enumerate(righe):
            c.create_text(bx + 8, y0 + 27 + 15 * j, text=t, anchor="w", fill=col, font=self.F(7), tags="punta")

    def disegna_basso(self):
        """Report o Matchups, l'ultima delle due aperta (il nome di prima)."""
        self.disegna_vista(self.basso)

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
                c.create_rectangle(x0, y, x0 + larga, y + alto, fill="#22262c" if on else "#1c1c20", outline=C["azzurro"] if on else "#2c2c32", width=2 if on else 1)
                c.create_text(x0 + 12, y + 15, text=corto(nome, int((larga - 150) / 6.6)), anchor="w", fill=C["azzurro"] if on else C["titolo"], font=F(8, True))
                c.create_text(x0 + 12, y + 32, text=corto(sotto, int((larga - 150) / 5.6)), anchor="w", fill=C["grigio"], font=F(7))
                wr = k.get("wr")
                pochi = len(r) < 15
                c.create_text(x0 + larga - 12, y + 15, text=f"{wr:.0f}%" if wr is not None else "-", anchor="e",
                              fill=C["muto"] if wr is None or pochi else (C["azzurro"] if wr >= 50 else C["rosso"]), font=F(11, True))
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
        alto = 38
        affiancati = W >= 800        # a tutta larghezza: dove vinci a sinistra, dove perdi a destra
        per_lista = max(1, int((H - 22 - 8) // (alto + 4))) if affiancati else max(1, int((H - 2 * 22 - 8) // 2 // (alto + 4)))
        minimo = 15 if len(r) >= 90 else max(6, len(r) // 6)
        meglio, peggio = DA.spot(r, minimo=minimo, quanti=per_lista, gia=self.filtri)
        base = DA.conti(r)["wr"]
        corto = lambda t, n: t if len(t) <= n else t[:n - 1] + "…"
        y = 2
        larga = (W - 12) / 2 if affiancati else W
        for j_, (tit, lista, col) in enumerate((("WHERE YOU WIN MOST", meglio, C["azzurro"]), ("WHERE YOU LOSE MOST", peggio, C["rosso"]))):
            x0 = j_ * (larga + 12) if affiancati else 0
            if affiancati:
                y = 2
            c.create_text(x0 + 4, y + 8, text=tit, anchor="w", fill=col, font=F(7, True))
            c.create_text(x0 + larga - 4, y + 8, text=f"vs {base:.0f}% here" if base is not None else "", anchor="e", fill=C["muto"], font=F(7))
            y += 20
            if not lista:
                c.create_text(x0 + 4, y + 12, text=f"nothing yet: no spot with {minimo}+ games that stands out", anchor="w", fill=C["grigio"], font=F(7))
                y += 28
            for s in lista:
                c.create_rectangle(x0, y, x0 + larga - 1, y + alto, fill="#202024", outline=col if s["forte"] else "#2c2c32")
                c.create_text(x0 + 10, y + 12, text=corto(s["nome"], int((larga - 90) / 6.4)), anchor="w", fill=C["titolo"], font=F(8, True))
                c.create_text(x0 + 10, y + 27, text=f"{s['n']} games · {s['vinte']}-{s['perse']} · 95% CI {s['ic'][0]}–{s['ic'][1]}%"
                              + ("  ·  strong" if s["forte"] else "  ·  a hint"), anchor="w", fill=C["grigio"] if s["forte"] else C["muto"], font=F(7))
                c.create_text(x0 + larga - 12, y + 12, text=f"{s['wr']:.0f}%", anchor="e", fill=col, font=F(11, True))
                c.create_text(x0 + larga - 12, y + 28, text=f"{s['delta']:+.0f}", anchor="e", fill=col, font=F(7, True))
                c._spot_box.append((x0, y, x0 + larga, y + alto, s))
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

    def disegna_matchup(self):
        """La matrice: i tuoi mazzi in riga, gli archetipi incontrati in colonna (o solo quelli del meta), in ogni cella win rate e partite."""
        c = self.tela("matchups")
        c.delete("all")
        c._celle = []
        if self.righe is None:
            return
        F = self.F
        mazzi, archi, celle, per_m, per_a = DA.matrice(self.scelte(), solo_meta=self.solo_meta)
        if not mazzi or not archi:
            c.create_text(12, 30, text="No matchups in this situation" + (" against meta decks" if self.solo_meta else ""), anchor="w", fill=C["grigio"], font=F(8))
            return
        W = max(c.winfo_width(), 700)
        x0, cw, rh = 230, max(70, min(120, (W - 230 - 90) / max(1, len(archi)))), 30
        corto = lambda t, n: t if len(t) <= n else t[:n - 1] + "…"
        for j, a in enumerate(archi):
            x = x0 + j * cw
            # il nome va a capo su due righe invece di tagliarsi (12 nov 2026, Autore: «qui i nomi vengono tagliati, sistema»)
            c.create_text(x + cw / 2, 30, text=corto(a, 2 * int((cw - 8) / 6.2)), width=cw - 8, anchor="s", justify="center", fill=C["titolo"], font=F(7, True))
            n, wr = per_a[a]
            c.create_text(x + cw / 2, 42, text=f"{wr:.0f}% · {n}", anchor="center", fill=C["grigio"], font=F(7))
        c.create_text(x0 + len(archi) * cw + 40, 30, text="ALL", anchor="s", fill=C["titolo"], font=F(7, True))
        y = 54
        for m in mazzi:
            n, wr = per_m[m]
            c.create_text(8, y + rh / 2 - 6, text=corto(m, 30), anchor="w", fill=C["titolo"], font=F(8, True))
            c.create_text(8, y + rh / 2 + 7, text=f"{n} games · {wr:.0f}%", anchor="w", fill=C["grigio"], font=F(7))
            for j, a in enumerate(archi):
                x = x0 + j * cw
                v = celle.get((m, a))
                if v is None:
                    c.create_rectangle(x + 2, y + 2, x + cw - 2, y + rh - 2, fill="#18181c", outline="#26262c")
                    continue
                nn, _vv, w = v
                poche = nn < 5
                fondo = "#26262c" if poche else _colore_wr(w)
                c.create_rectangle(x + 2, y + 2, x + cw - 2, y + rh - 2, fill=fondo, outline="#26262c")
                c.create_text(x + cw / 2, y + rh / 2 - 5, text=f"{w:.0f}%", fill=C["muto"] if poche else C["titolo"], font=F(8, True))
                c.create_text(x + cw / 2, y + rh / 2 + 8, text=f"{nn}", fill=C["muto"] if poche else "#d8d8dc", font=F(6))
                c._celle.append((x, y, x + cw, y + rh, m, a))
            c.create_text(x0 + len(archi) * cw + 40, y + rh / 2, text=f"{wr:.0f}%", fill=C["azzurro"] if wr >= 50 else C["rosso"], font=F(8, True))
            y += rh + 2
        c.create_text(8, y + 12, text="grey: under 5 games, a hint", anchor="w", fill=C["muto"], font=F(7))
        c.configure(scrollregion=(0, 0, W, y + 26))

    def clic_matchup(self, e):
        """Una cella: il tuo mazzo e il suo archetipo fra i filtri."""
        c = getattr(e, "widget", None) or self.tela("matchups")
        y = c.canvasy(e.y)
        for x0, y0, x1, y1, m, a in getattr(c, "_celle", []):
            if x0 <= e.x <= x1 and y0 <= y <= y1:
                self.filtri["mio"], self.filtri["suo"] = m, a
                self.disegna()
                return

    def disegna_report(self):
        c = self.tela("report")
        c.delete("all")
        c._righe_rp, c._n = [], 0
        if self.righe is None:
            return
        F = self.F
        rep = DA.report(self.scelte(), self.per, self.ordina if self.ordina != "wl" else "vinte")
        W = max(c.winfo_width(), 700)
        x = 8
        c._col_x = []
        for k, t, w in COLONNE:
            c.create_text(x, 10, text=t or DA.nome_var(self.per).upper()[:32], anchor="w", fill=C["accento"] if k == self.ordina else C["titolo"], font=F(7, True))
            c._col_x.append((x, x + w, k))
            x += w
        y = 26
        for i, r in enumerate(rep):
            if i % 2 == 0:
                c.create_rectangle(0, y - 2, W, y + 22, fill="#202024", outline="")
            gr_ = r["poche"]
            x = 8
            for k, _t, w in COLONNE:
                if k == "wr":
                    col = C["muto"] if gr_ or r["wr"] is None else (C["azzurro"] if r["wr"] >= 50 else C["rosso"])
                    c.create_rectangle(x, y + 5, x + 120, y + 15, fill="#2c2c32", outline="")
                    if r["wr"] is not None:
                        c.create_rectangle(x, y + 5, x + 1.2 * r["wr"], y + 15, fill=col, outline="")
                    c.create_line(x + 60, y + 2, x + 60, y + 18, fill="#d8d8dc")
                    c.create_text(x + 128, y + 10, text=f"{r['wr']:.0f}%" if r["wr"] is not None else "-", anchor="w", fill=col, font=F(8, True))
                else:
                    v = {"nome": r["nome"], "n": str(r["n"]), "wl": f"{r['vinte']}-{r['perse']}", "play": f"{r['play']:.0f}%" if r["play"] is not None else "-",
                         "draw": f"{r['draw']:.0f}%" if r["draw"] is not None else "-", "mull": f"{r['mull']:.0f}%" if r["mull"] is not None else "-",
                         "turni": f"T{r['turni']}" if r["turni"] else "-", "delta": f"{r['delta']:+.1f}" if r["delta"] is not None else "-"}[k]
                    col = (C["muto"] if gr_ else (C["azzurro"] if (r["delta"] or 0) > 0 else C["rosso"] if (r["delta"] or 0) < 0 else C["testo"])) if k == "delta" \
                        else (C["muto"] if gr_ else C["titolo"] if k == "nome" else C["testo"])
                    if k == "nome" and len(v) > 34:
                        v = v[:33] + "…"
                    c.create_text(x, y + 10, text=v, anchor="w", fill=col, font=F(8, k == "nome"))
                x += w
            c._righe_rp.append((y - 2, y + 22, r["valore"]))
            y += 24
        c._n = len(rep)
        if not rep:
            c.create_text(12, 40, text="No games in this situation", anchor="w", fill=C["grigio"], font=F(8))
        c.create_text(8, y + 10, text="grey: under 15 games, a hint", anchor="w", fill=C["muto"], font=F(7))
        c.configure(scrollregion=(0, 0, W, y + 24))
        self.maschera_rp(c)

    def maschera_rp(self, c=None):
        """La riga che in fondo starebbe a meta' si copre: in vista solo righe intere (12 nov 2026: «tutto non tagliato»); sopra la copertura quante righe restano
        sotto (la riga d'aiuto sotto le cartelle non c'e' piu')."""
        c = c or self.tela("report")
        c.delete("maschera")
        top, h = c.canvasy(0), max(c.winfo_height(), 60)
        fondo = top + h
        W = max(c.winfo_width(), 700)
        ultimo = 24 + int((fondo - 24) // 24) * 24       # le righe cominciano a 24 e sono alte 24
        fine = 24 + 24 * getattr(c, "_n", 0)
        sotto = (fine - ultimo) // 24 if fine > ultimo else 0
        if sotto and fondo - ultimo < 18 and ultimo - 24 > top + 24:       # serve posto per la scritta: si copre una riga in piu'
            ultimo -= 24
            sotto += 1
        if ultimo < fondo:
            c.create_rectangle(0, ultimo, W + 10, fondo + 2, fill=C["scheda"], outline="", tags="maschera")
        if sotto:
            c.create_text(W - 12, (ultimo + fondo) / 2, text=f"{sotto} more row{'s' if sotto > 1 else ''} below · scroll", anchor="e", fill=C["grigio"],
                          font=self.F(7, True), tags="maschera")

    def clic_report(self, e):
        c = getattr(e, "widget", None) or self.tela("report")
        y = c.canvasy(e.y)
        if y < 22:      # le intestazioni: ordina
            for a, b, k in getattr(c, "_col_x", []):
                if a <= e.x < b:
                    self.ordina = "nome" if k == "nome" else k
                    self.disegna_report()
                    return
            return
        for a, b, v in getattr(c, "_righe_rp", []):
            if a <= y < b:
                self.filtri[self.per] = v
                self.disegna()
                return

    # ------------------------------------------------------------ il confronto situazionale (12 nov 2026, «procedi con i confronti situazionali»)
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
        voci = ["rest", "all"] + [f"s{i}" for i in range(len(sal))]
        if self.con not in voci:
            self.con = "rest"
        et = {"rest": "Everything else", "all": f"All {self.tipo.lower()} games", **{f"s{i}": (s_.get("nome") or f"Situation {i + 1}") for i, s_ in enumerate(sal)}}
        for o in self.copie("compare"):
            o["ctl"]["con"].opzioni(voci, lambda v: self.cambia("con", v), etichette=et)
            o["ctl"]["con"].set(self.con)
        W, H = max(c.winfo_width(), 600), max(c.winfo_height(), 240)
        n_f = sum(1 for v in self.filtri.values() if v is not None)
        if not n_f and self.con in ("rest", "all"):
            c.create_text(16, 30, text="A is the situation you build with the smart filters (and the + of each phase).", anchor="w", fill=C["titolo"], font=F(9, True))
            c.create_text(16, 52, text="Set some, then compare it here with everything else, with all your games or with a saved situation.", anchor="w",
                          fill=C["grigio"], font=F(8))
            return
        a = self.scelte()
        b, nome_b, descr_b = self.b_confronto()
        res = DA.confronta(a, b)
        corto = lambda t, n: t if len(t) <= n else t[:n - 1] + "…"
        meta = (W - 16 - 12) / 2
        for i, (lett, tit, descr, k_, col) in enumerate((("A", "THIS SITUATION", self.descrivi(self.filtri), res["a"], C["azzurro"]),
                                                         ("B", nome_b.upper(), descr_b, res["b"], C["arancio"]))):
            x0 = 8 + i * (meta + 12)
            c.create_rectangle(x0, 4, x0 + meta, 52, fill="#202024", outline="#2c2c32")
            c.create_rectangle(x0, 4, x0 + 3, 52, fill=col, outline="")
            c.create_text(x0 + 14, 17, text=corto(f"{lett} · {tit}", int((meta - 150) / 6.6)), anchor="w", fill=col, font=F(8, True))
            c.create_text(x0 + meta - 10, 17, text=f"{k_['n']} games · {k_['vinte']}-{k_['perse']}", anchor="e", fill=C["titolo"], font=F(8, True))
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
                c.create_rectangle(0, y, W, y + 24, fill="#202024", outline="")
            c.create_text(cx[0], y + 12, text=r["nome"], anchor="w", fill=C["titolo"], font=F(8, True))
            for x_, v, n, ic, col in ((cx[1], r["a"], r["na"], r["ic_a"], C["azzurro"]), (cx[2], r["b"], r["nb"], r["ic_b"], C["arancio"])):
                if v is None:
                    t = "-"
                elif r["unita"] == "%":
                    t = f"{v:.0f}%" + (f"  ({ic[0]}–{ic[1]})" if r["k"] == "wr" and ic else "") + f"  · {n} g"
                else:
                    t = f"T{v}  · {n} g"
                c.create_text(x_, y + 12, text=t, anchor="w", fill=col if v is not None else C["muto"], font=F(8))
            d = r["delta"]
            buono = r["k"] in ("wr", "play", "draw")
            if d is None:
                td, cd = "-", C["muto"]
            else:
                td = f"{d:+.1f} pts" if r["unita"] == "%" else f"{d:+.1f} turns"
                cd = (C["azzurro"] if d > 0 else C["rosso"] if d < 0 else C["testo"]) if buono else C["testo"]
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
        if H - y >= 130:        # sotto, il win rate di A e di B nel tempo
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
        c.create_text(0, H - 10, text=nome, anchor="w", fill=C["accento"] if on else C["muto"], font=F(7, True))
        if not chiavi:      # una fase senza filtri in piu': niente + more
            return
        t = f"+ {on} on" if on else "+ more"
        c.create_rectangle(W - 62, H - 19, W - 2, H - 1, fill="#0f86cc" if on else "#202024", outline="#0f86cc" if on else "#3a3a40")
        c.create_text(W - 32, H - 10, text=t, fill="#ffffff" if on else C["grigio"], font=F(7, True))

    # ------------------------------------------------------------ Advanced filters (13 nov 2026, Autore: «io voglio una sezione dove posso ottenere una
    # risposta in base a dei filtri ... mio wr quando ho 3 terre in mano on the draw e chiudo entro T5 senza creature e oppo mulliga», poi «tutta sta roba sta in
    # una nuova sotto finestra / il pulsante per aprirla e' advanced filters», «filtri e domanda ma i filtri per me e per oppo stanno in due schede differenti»)
    def chiavi_scheda_av(self, scheda):
        """I filtri di una scheda di Advanced filters (You o Opponent), le righe delle giocate per turno comprese."""
        return {k2 for _f, sezioni in AVANZATI[scheda] for _t, kk in sezioni for k in kk
                for k2 in ([f"{k[1:]}{n}" for n in range(1, DA.TURNI_FILTRO + 1)] if k.startswith("@") else [k])}

    def reset_scheda_av(self):
        """Il Reset della scheda aperta di Advanced filters: i suoi filtri via, gli altri (le altre schede, gli smart filters) restano."""
        for k in self.chiavi_scheda_av(self.scheda_av):
            self.filtri.pop(k, None)
        for _f, sezioni in AVANZATI[self.scheda_av]:
            for _t, kk in sezioni:
                for k in kk:
                    if k.startswith("@"):
                        self.__dict__.setdefault("_righe_ui", {}).pop(k[1:], None)
        self.disegna()

    def avanzati_on(self):
        """Quanti filtri della finestra Advanced filters sono accesi."""
        chiavi = {k2 for fasi in AVANZATI.values() for _f, sezioni in fasi for _t, kk in sezioni for k in kk
                  for k2 in ([f"{k[1:]}{n}" for n in range(1, DA.TURNI_FILTRO + 1)] if k.startswith("@") else [k])}
        return sum(1 for k, v in self.filtri.items() if v is not None and k in chiavi)

    def aggiorna_bottone_avanzati(self):
        b = getattr(self, "b_avanzati", None)
        if b is not None and b.winfo_exists():
            n = self.avanzati_on()
            b.metti("Advanced filters" + (f"  ·  {n} on" if n else ""), bool(n))

    def apri_avanzati(self, scheda=None, fase=None):
        """La finestra: in cima la domanda (ogni filtro acceso, anche quelli della pagina, con la sua x) e la risposta; sotto due schede, You e Opponent, coi
        filtri avanzati di ognuno. Tutto si applica subito: la pagina (grafico, report, partite) segue la stessa domanda. Una finestra sola."""
        tk, F = self.tk, self.F
        if scheda:
            self.scheda_av = scheda
        if fase is not None:
            self.fase_av[self.scheda_av] = fase
        f = getattr(self, "fin_av", None)
        if f is None or not f.winfo_exists():
            f = self.fin_av = tk.Toplevel(self.fr); f.configure(bg=C["scheda"])
            self._fasi_di = None
            f.transient(self.fr.winfo_toplevel())
            f.title("Advanced filters")
            f.geometry(f"+{self.cv_sx.winfo_rootx() + self.cv_sx.winfo_width() + 16}+{max(0, self.cv_sx.winfo_rooty() - 40)}")
            f.bind("<Escape>", lambda e: f.destroy())
            tk.Label(f, text="ADVANCED FILTERS", bg=C["scheda"], fg=C["titolo"], font=F(10, True)).pack(anchor="w", padx=14, pady=(12, 2))
            tk.Label(f, text="Build your question: every filter adds a piece, the answer is right below and the whole Performance page follows it "
                     "(chart, report, matchups, the games and their replays).", bg=C["scheda"], fg=C["grigio"], font=F(7), wraplength=LARGA_FASE - 20,
                     justify="left").pack(anchor="w", padx=14, pady=(0, 6))
            self.cv_dom = tk.Canvas(f, bg="#17171b", highlightthickness=1, highlightbackground=C["filo"], bd=0, width=LARGA_FASE, height=90)
            self.cv_dom.pack(padx=8, pady=(0, 8))
            self.cv_dom.bind("<Button-1>", self.clic_domanda)
            schede = tk.Frame(f, bg=C["scheda"]); schede.pack(fill="x", padx=8, pady=(2, 4))
            self.b_schede_av = {}
            for k, n in (("io", "You"), ("lui", "Opponent")):
                b = pulsante_solido(tk, F, schede, n, k == self.scheda_av, lambda k=k: self.apri_avanzati(k), alto=28, bg=C["scheda"], colori=GRIGI)
                b.configure(width=150); b.pack(side="left", padx=(0, 6))
                self.b_schede_av[k] = b
            # il Reset della scheda aperta (13 nov 2026, Autore: «per ogni scheda in cui inseriamo valori crea un pulsante reset localizzato, mentre il main
            # reset le resetta tutte contemporaneamente»)
            self.b_reset_av = pulsante_solido(tk, F, schede, "Reset", False, self.reset_scheda_av, alto=28, bg=C["scheda"], colori=ARANCIO)
            self.b_reset_av.configure(width=150); self.b_reset_av.pack(side="right")
            self.fr_fasi_av = tk.Frame(f, bg=C["scheda"]); self.fr_fasi_av.pack(fill="x", padx=8, pady=(2, 4))
            # i filtri scorrono (13 nov 2026, Autore: «caso mai mettiamo uno scroller per scendere alle voci in fondo»): la rotella su tutta la finestra e una
            # barra sottile a destra, da cliccare o trascinare
            corpo = tk.Frame(f, bg=C["scheda"]); corpo.pack(padx=8, pady=(4, 12))
            self.cv_av = tk.Canvas(corpo, bg=C["scheda"], highlightthickness=0, bd=0, width=LARGA_FASE, height=200)
            self.cv_av.pack(side="left")
            self.cv_av.bind("<Button-1>", self.clic_avanzati)
            self.cv_barra_av = tk.Canvas(corpo, bg=C["scheda"], highlightthickness=0, bd=0, width=10, height=200, cursor="hand2")
            self.cv_barra_av.pack(side="left", fill="y", padx=(4, 0))
            self.cv_av.configure(yscrollcommand=self.barra_av)
            self.cv_barra_av.bind("<Button-1>", self.trascina_av)
            self.cv_barra_av.bind("<B1-Motion>", self.trascina_av)
            f.bind("<MouseWheel>", lambda e: (self.cv_av.yview_scroll(-2 if e.delta > 0 else 2, "units"), "break")[1])
        for k, b in self.b_schede_av.items():
            b.metti({"io": "You", "lui": "Opponent"}[k], k == self.scheda_av)
        self.b_reset_av.metti("Reset · " + {"io": "You", "lui": "Opponent"}[self.scheda_av], False)
        # le fasi della scheda: rifatte quando cambia la scheda (You e Opponent ne hanno di diverse)
        if getattr(self, "_fasi_di", None) != self.scheda_av:
            for w in self.fr_fasi_av.winfo_children():
                w.destroy()
            self.b_fasi_av = []
            for j, (nome, _sez) in enumerate(AVANZATI[self.scheda_av]):
                b = pulsante_solido(tk, F, self.fr_fasi_av, nome, False, lambda j=j: self.apri_avanzati(fase=j), alto=24, bg=C["scheda"],
                                    colori=("#202024", "#2c2c32", "#1f3446"))
                b.configure(width=124); b.pack(side="left", padx=(0, 4))
                self.b_fasi_av.append(b)
            self._fasi_di = self.scheda_av
        for j, b in enumerate(self.b_fasi_av):
            b.metti(AVANZATI[self.scheda_av][j][0], j == self.fase_av[self.scheda_av])
        self.disegna_avanzati()
        if scheda or fase is not None:          # un'altra scheda o fase riparte dall'alto
            self.cv_av.yview_moveto(0)
        f.lift()
        return f

    def disegna_avanzati(self):
        """La domanda con la risposta e i filtri della scheda aperta."""
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
        tot = DA.conti([x for x in self.righe if x["tipo"] == self.tipo])
        c.create_text(12, 16, text=f"YOUR QUESTION · {self.tipo.lower()} games when", anchor="w", fill=C["azzurro"], font=F(7, True))
        x, y = 12, 40
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
        col = C["muto"] if wr is None else (C["azzurro"] if wr >= 50 else C["rosso"])
        c.create_text(12, y + 4, text=f"{wr:.0f}%" if wr is not None else "-", anchor="w", fill=col, font=F(18, True))
        info = (f"{k_['n']} games · {k_['vinte']}-{k_['perse']}" + (f" · 95% CI {k_['ic'][0]}–{k_['ic'][1]}%" if k_.get("ic") else "")
                + (f" · vs all your {self.tipo.lower()} games {tot['wr']:.0f}%" if tot["wr"] is not None and accesi else ""))
        c.create_text(100, y - 2, text=info, anchor="w", fill=C["grigio"], font=F(8))
        if 0 < k_["n"] < 30:
            c.create_text(100, y + 14, text="under 30 games: a hint, not a fact", anchor="w", fill=C["arancio"], font=F(7, True))
        elif not k_["n"]:
            c.create_text(100, y + 14, text="no games answer this question: remove a piece", anchor="w", fill=C["arancio"], font=F(7, True))
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
        for titolo, chiavi in AVANZATI[self.scheda_av][self.fase_av[self.scheda_av]][1]:
            ca.create_text(8, y + 10, text=titolo, anchor="w", fill=C["azzurro"], font=F(7, True))
            y += 24
            if len(chiavi) == 1 and chiavi[0].startswith("@"):
                y = self.righe_avanzate(ca, chiavi[0][1:], y, tutte)
                continue
            for k in chiavi:
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
                    ca.create_rectangle(x, y + 2, x + w, y + 24, fill="#0f86cc" if on else "#202024", outline="#0f86cc" if on else "#3a3a40")
                    ca.create_text(x + w / 2, y + 13, text=t, fill="#ffffff" if on else C["grigio"], font=F(7, True))
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
    # per ogni cosa lanciata (tipo, o tipo · costo); piu' tendine nella stessa riga = tutte in quel turno (la scelta multipla di prima). I filtri sono gli
    # stessi («t_io3» = [voci]); le righe ancora senza voci restano solo a video.
    NOMI_RIGHE = {"t_io": ("Your T{}", "cast"), "t_iox": ("Opponent's T{}", "you cast"), "t_lui": ("Their T{}", "cast"), "t_luix": ("Your T{}", "they cast")}

    def _da_righe(self, pre, righe):
        """I filtri di un gruppo dalle sue righe: {«t_io3»: [voci]} (le righe dello stesso turno si uniscono)."""
        nuovi = {}
        for campo, voci in righe:
            vv = [v for v in voci or [] if v]
            if campo and vv:
                k = f"{pre}{campo}"
                nuovi[k] = sorted(set(nuovi.get(k, [])) | set(vv), key=DA.ordine_lancio)
        return nuovi

    def righe_av(self, pre):
        """Le righe del costruttore di un gruppo: quelle a video (con le tendine ancora vuote) se dicono ancora i filtri accesi, se no rifatte dai filtri (Clear
        all, la x di un pezzo della domanda, un tuo filtro salvato); di partenza il turno 1 vuoto."""
        ora = {}
        for n in range(1, DA.TURNI_FILTRO + 1):
            v = self.filtri.get(f"{pre}{n}")
            if v:
                ora[f"{pre}{n}"] = sorted(v if isinstance(v, list) else [v], key=DA.ordine_lancio)
        ui = self.__dict__.setdefault("_righe_ui", {}).get(pre)
        if ui and self._da_righe(pre, ui) == ora:
            return [[c_, list(v_)] for c_, v_ in ui]
        righe = [[k[len(pre):], list(v)] for k, v in sorted(ora.items(), key=lambda kv: int(kv[0][len(pre):]))]
        return righe or [["1", [None]]]

    def righe_avanzate(self, ca, pre, y, tutte):
        """Il costruttore delle righe di un gruppo dentro la tela di Advanced filters, a y. -> la y sotto."""
        tk, F = self.tk, self.F
        nome, dopo = self.NOMI_RIGHE[pre]
        voci = lambda n: sorted(set(DA.ORDINE_TIPI) | {v for x_ in tutte for v in DA.valori_di(f"{pre}{n}", x_) if " · " in v}, key=DA.ordine_lancio)
        b = R_F.Righe(tk, F, ca, self.righe_av(pre), [str(n) for n in range(1, DA.TURNI_FILTRO + 1)], lambda n: nome.format(n), voci,
                      lambda rr, pre=pre: self.metti_righe_av(pre, rr), dopo=dopo, larga_campo=150, larga_voce=170)
        self._costruttori_av[pre] = b
        ca.create_window(8, y, window=b.fr, anchor="nw")
        b.fr.update_idletasks()
        return y + b.fr.winfo_reqheight() + 12

    def metti_righe_av(self, pre, righe):
        """Dalle righe ai filtri del gruppo; le righe restano come sono a video (anche le tendine ancora vuote)."""
        for n in range(1, DA.TURNI_FILTRO + 1):
            self.filtri.pop(f"{pre}{n}", None)
        self.filtri.update(self._da_righe(pre, righe))
        self.__dict__.setdefault("_righe_ui", {})[pre] = [[c_, list(v_ or [None])] for c_, v_ in righe]
        self.fr.after_idle(self.disegna)

    def barra_av(self, a, b):
        """La barra sottile accanto ai filtri: dove sei e quanto si vede; niente se tutto ci sta."""
        c = self.cv_barra_av
        c.delete("all")
        a, b = float(a), float(b)
        if b - a >= 0.999:
            return
        H = max(c.winfo_height(), int(c.cget("height")))
        c.create_rectangle(3, 0, 7, H, fill="#202024", outline="")
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
                c.create_rectangle(x, y + 2, x + w, y + 24, fill="#0f86cc" if on else "#202024", outline="#0f86cc" if on else "#3a3a40")
                c.create_text(x + w / 2, y + 13, text=t, fill="#ffffff" if on else C["grigio"], font=F(7, True))
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
        mio, vs = self.filtri.get("mio"), self.filtri.get("vs")
        t = f"By deck  ·  {(mio or 'all decks').strip()} vs {DA.nome_vs(vs) if vs else 'all'}"
        self.b_deck.metti(t if len(t) <= 40 else t[:39] + "…", bool(mio or vs))

    def apri_deck(self):
        """La finestra By deck: a sinistra il tuo mazzo (o tutti), a destra contro chi: vs all, o vs colors coi colori da spuntare (una variante esatta, dal
        monocolore al pentacolore, o incolore), e sotto il mazzo contro ogni variante di colore incontrata, per gruppi; il clic su una riga la sceglie."""
        tk, F = self.tk, self.F
        f = getattr(self, "fin_deck", None)
        if f is not None and f.winfo_exists():
            f.lift(); return f
        f = self.fin_deck = tk.Toplevel(self.fr); f.title("By deck"); f.configure(bg=C["scheda"])
        f.transient(self.fr.winfo_toplevel())
        f.geometry(f"+{self.cv_sx.winfo_rootx() + self.cv_sx.winfo_width() + 16}+{max(0, self.cv_sx.winfo_rooty() - 80)}")
        f.bind("<Escape>", lambda e: f.destroy())
        tk.Label(f, text="BY DECK", bg=C["scheda"], fg=C["titolo"], font=F(9, True)).pack(anchor="w", padx=14, pady=(12, 2))
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
        mio, vs = self.filtri.get("mio"), self.filtri.get("vs")
        modo = "colors" if vs else self.vs_modo
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
            c.create_rectangle(0, y, 270, y + 42, fill="#0f2a38" if on else "#202024", outline=C["accento"] if on else "#2c2c32")
            c.create_text(10, y + 13, text=corto((v or "All decks").strip(), 26), anchor="w", fill=C["titolo"] if on else C["testo"], font=F(8, True))
            if v is not None:
                for j, ch in enumerate(self.colori_deck(v)):
                    img = self.lista().simbolo(ch, 14)
                    if img is not None:
                        c.create_image(18 + j * 17, y + 30, image=img)
            else:
                c.create_text(10, y + 30, text="every deck", anchor="w", fill=C["muto"], font=F(7))
            wr = k_["wr"]
            c.create_text(262, y + 13, text=pc(wr), anchor="e", fill=C["muto"] if wr is None else (C["azzurro"] if wr >= 50 else C["rosso"]), font=F(9, True))
            c.create_text(262, y + 30, text=f"{k_['n']} games", anchor="e", fill=C["accento"] if on else C["grigio"], font=F(7))
            self._box_deck.append((0, y, 270, y + 42, "mio", v))
            y += 46
        fine_sx = y
        # a destra: contro chi
        X = 296
        y = 4
        c.create_text(X, y + 8, text="AGAINST", anchor="w", fill=C["muto"], font=F(7, True))
        y += 22
        for i, (m, t) in enumerate((("all", "vs all"), ("colors", "vs colors"))):
            x = X + i * 118
            on = modo == m
            c.create_rectangle(x, y, x + 110, y + 28, fill="#0f86cc" if on else "#202024", outline="#0f86cc" if on else "#3a3a40")
            c.create_text(x + 55, y + 14, text=t, fill="#ffffff" if on else C["grigio"], font=F(8, True))
            self._box_deck.append((x, y, x + 110, y + 28, "modo", m))
        y += 40
        flag = set() if not vs else ({"C"} if vs == "C" else set(vs))
        for i, k in enumerate("WUBRGC"):
            x = X + i * 48
            on = k in flag
            c.create_rectangle(x, y, x + 40, y + 36, fill="#0f2a38" if on else "#202024", outline=C["accento"] if on else "#2c2c32", width=2 if on else 1)
            img = self.lista().simbolo(k, 22)
            if img is not None:
                c.create_image(x + 20, y + 18, image=img)
            else:
                c.create_text(x + 20, y + 18, text=k, fill=C["titolo"], font=F(9, True))
            self._box_deck.append((x, y, x + 40, y + 36, "colore", k))
        base_vs = DA.filtra(self.righe, {k: v for k, v in self.filtri.items() if k != "vs"}, self.tipo)
        x = X + 6 * 48 + 8
        if vs:
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
            c.create_rectangle(x, yy + 8, x + 100, yy + 16, fill="#2c2c32", outline="")
            if wr is not None:
                c.create_rectangle(x, yy + 8, x + wr, yy + 16, fill=colore, outline="")
            c.create_line(x + 50, yy + 5, x + 50, yy + 19, fill="#d8d8dc")
            c.create_text(x + 108, yy + 12, text=pc(wr), anchor="w", fill=colore, font=F(8, True))
        for g in gruppi:
            k_ = g["conti"]
            c.create_rectangle(X - 4, y, LARGA_DECK, y + 24, fill="#26262c", outline="")
            c.create_text(col["var"], y + 12, text=g["gruppo"].upper(), anchor="w", fill=C["titolo"], font=F(8, True))
            c.create_text(col["n"], y + 12, text=str(k_["n"]), anchor="w", fill=C["titolo"], font=F(8, True))
            c.create_text(col["wl"], y + 12, text=f"{k_['vinte']}-{k_['perse']}", anchor="w", fill=C["testo"], font=F(8))
            barra(col["wr"], y, k_["wr"], C["azzurro"] if (k_["wr"] or 0) >= 50 else C["rosso"])
            c.create_text(col["play"], y + 12, text=pc(k_["play"]), anchor="w", fill=C["testo"], font=F(8))
            c.create_text(col["draw"], y + 12, text=pc(k_["draw"]), anchor="w", fill=C["testo"], font=F(8))
            y += 26
            for i, (v, k_) in enumerate(g["varianti"]):
                on, poche = v == vs, k_["n"] < 5
                fondo = "#0f2a38" if on else ("#202024" if i % 2 == 0 else C["scheda"])
                c.create_rectangle(X - 4, y, LARGA_DECK, y + 24, fill=fondo, outline=C["accento"] if on else "")
                for j, ch in enumerate(v):
                    img = self.lista().simbolo(ch, 14)
                    if img is not None:
                        c.create_image(col["var"] + 8 + j * 16, y + 12, image=img)
                testo = C["muto"] if poche else C["titolo"]
                c.create_text(col["var"] + 8 + 5 * 16 + 4, y + 12, text=DA.nome_vs(v), anchor="w", fill=testo, font=F(8, on))
                c.create_text(col["n"], y + 12, text=str(k_["n"]), anchor="w", fill=testo, font=F(8))
                c.create_text(col["wl"], y + 12, text=f"{k_['vinte']}-{k_['perse']}", anchor="w", fill=C["muto"] if poche else C["testo"], font=F(8))
                barra(col["wr"], y, k_["wr"], C["muto"] if poche else (C["azzurro"] if (k_["wr"] or 0) >= 50 else C["rosso"]))
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
        c._box_carte, c._box_coppie = [], []
        if self.righe is None:
            return
        F = self.F
        W = max(c.winfo_width(), 600)
        r = self.scelte()
        k_ = DA.conti(r)
        base = k_["wr"]
        c.create_text(14, 14, text=f"THE CARDS OF THESE {k_['n']} GAMES · NO LANDS", anchor="w", fill=C["muto"], font=F(7, True))
        if base is not None:
            c.create_text(W - 14, 14, text=f"win rate of these games {base:.0f}% · click a card: only its games · Pairs: the cards that come together",
                          anchor="e", fill=C["grigio"], font=F(7))
        wc = LARGA_CARTA
        hc = round(wc * 279 / 200)
        per_riga = max(1, int((W - 28) // (wc + 14)))
        per_coppie = max(1, int((W - 28) // (wc + round(wc * 0.5) + 14)))
        y = 34
        scelte_r = set(DA.righe_carte_scelte())
        for o in self.copie("cards"):        # il pulsante Rows dice quante righe sono accese, anche all'apertura
            if "righe" in o["ctl"]:
                o["ctl"]["righe"].metti("Rows · all" if len(scelte_r) == len(DA.RIGHE_CARTE) else f"Rows · {len(scelte_r)} of {len(DA.RIGHE_CARTE)}",
                                        len(scelte_r) < len(DA.RIGHE_CARTE))
        if not scelte_r:
            c.create_text(14, 46, text="No rows picked: open «Rows» and tick the ones you want to see.", anchor="w", fill=C["grigio"], font=F(9))
        for chiave, titolo in DA.RIGHE_CARTE:
            if chiave not in scelte_r:      # solo le righe spuntate in Rows
                continue
            carte = DA.riga_carte(r, chiave, quante=per_coppie if chiave == "finisher" else per_riga)
            c.create_line(14, y, W - 14, y, fill="#2c2c34")
            c.create_text(14, y + 14, text=titolo, anchor="w", fill=C["azzurro"], font=F(8, True))
            # le coppie della riga si aprono in una finestra a parte (13 nov 2026, Autore: «non aggiungere le coppie come righe ma come finestre extra che
            # si aprono dalla riga e mostrano le coppie»)
            i_ = c.create_text(W - 14, y + 14, text="Pairs ›", anchor="e", fill=C["accento"], font=F(8, True))
            bb = c.bbox(i_)
            c._box_coppie.append((bb[0] - 6, bb[1] - 4, bb[2] + 6, bb[3] + 4, chiave, titolo))
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
        c.configure(scrollregion=(0, 0, W, y + 6))

    def metti_carta(self, c, x, y, cc, chiave, base):
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
                c.create_rectangle(xx, y, xx + wc, y + hc, fill="#1b1b22", outline="#3a3a42")
                c.create_text(xx + wc / 2, y + hc / 2, text=nm, fill=C["titolo"], font=F(8, True), width=wc - 12, justify="center")
            # il riquadro di ogni carta: la carta grande al passaggio; il filtro della carta o della coppia al clic
            c._box_carte.append((xx, y, (xx + sopra) if j < len(nomi) - 1 else xx + wc, y + hc + 38, nm, chiave, fk, fv))
        if self.filtri.get(fk) == fv:
            c.create_rectangle(x - 3, y - 3, x + larga_c + 3, y + hc + 3, outline=C["accento"], width=2)
        poche = cc["n"] < 5
        col = C["muto"] if poche or base is None else (C["azzurro"] if cc["wr"] > base else C["rosso"] if cc["wr"] < base else C["testo"])
        xc = x + larga_c / 2
        if "salto" in cc:           # un finisher: quante vittorie ha deciso, il salto di vantaggio medio
            c.create_text(xc, y + hc + 12, text=f"decided {cc['n']} win{'s' * (cc['n'] != 1)}", fill=C["azzurro"], font=F(9, True))
            c.create_text(xc, y + hc + 29, text=f"swing +{cc['salto']:.0f} · {cc['quota']:.0f}% of your wins", fill=C["grigio"], font=F(7))
        elif chiave == "bloccate" and "bloccata" in cc:
            c.create_text(xc, y + hc + 12, text=f"{cc['bloccata']}% stuck", fill=C["rosso"], font=F(9, True))
            c.create_text(xc, y + hc + 29, text=f"{cc['n']} of {cc['mano']} games · {cc['wr']:.0f}%", fill=C["grigio"], font=F(7))
        else:
            c.create_text(xc, y + hc + 12, text=f"{cc['wr']:.0f}%  ·  {cc['vinte']}-{cc['perse']}", fill=col, font=F(9, True))
            c.create_text(xc, y + hc + 29, text=f"in {cc['n']} games · {cc['quota']:.0f}%", fill=C["grigio"], font=F(7))
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
            f.title("Performance · Decision filters")
            f.configure(bg=C["scheda"])
            f.bind("<Escape>", lambda e: f.destroy())
            tk.Label(f, text="DECISION FILTERS", bg=C["scheda"], fg=C["titolo"], font=F(12, True)).pack(anchor="w", padx=16, pady=(14, 2))
            tk.Label(f, text="Only your decisions: what you did and the situation you did it in. Between the values of a filter one is enough, between filters "
                             "all are needed. The Decisions folder and «Gained by decisions» under the Chart follow them.", bg=C["scheda"], fg=C["grigio"],
                     font=F(8), wraplength=780, justify="left").pack(anchor="w", padx=16)
            self.f_dec_tipi = tk.Frame(f, bg=C["scheda"]); self.f_dec_tipi.pack(anchor="w", padx=16, pady=(10, 4))
            self.cv_dec_dom = tk.Canvas(f, bg=C["scheda"], highlightthickness=1, highlightbackground="#2c2c34", bd=0, width=820, height=66)
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
        tab = DEC.tabella(r, self.dec_modo, self.dec_f.get(self.dec_modo))
        tutte_ = tab[0]
        att = self.dec_modo == "attacco"
        f_ = DEC.descrivi(self.dec_f.get(self.dec_modo), self.dec_modo)
        c.create_text(14, 14, text=("YOUR ATTACKS" if att else "THEIR ATTACKS · YOUR DEFENSE") + (f" · {f_}" if f_ else "")
                      + f" · {tutte_['n']} combats in {tutte_['partite']} games · the outcome of the combat, at the end of that turn", anchor="w",
                      fill=C["muto"], font=F(7, True))
        c.create_text(W - 14, 14, text="click a row: its games as a line on the Chart, against All", anchor="e", fill=C["grigio"], font=F(7))
        col = [("nome", "SITUATION", 14), ("n", "COMBATS", 310), ("partite", "GAMES", 385), ("perdi", "YOU LOST A CREATURE", 450),
               ("uccidi", "THEY LOST A CREATURE", 600), ("scambio", "TRADE", 755), ("danno", "DAMAGE TO " + ("THEM" if att else "YOU"), 820),
               ("trucco", "THEIR SPELL BEFORE DMG", 945), ("guadagno", "AVG GAIN", 1105), ("wr", "GAME WIN RATE", 1195)]
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
            fondo = "#0f2a38" if on else ("#202024" if i % 2 == 0 else "#1c1c20")
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
                    colr = C["muto"] if rg["poche"] or i == 0 or base_ is None or abs(v - base_) < 3 else (C["azzurro"] if meglio else C["rosso"])
                elif k == "scambio":
                    testo, colr = f"{v:+.2f}", (C["muto"] if rg["poche"] else C["azzurro"] if v > 0 else C["rosso"] if v < 0 else C["testo"])
                elif k == "danno":
                    testo, colr = f"{v:.1f}", C["testo"] if not rg["poche"] else C["muto"]
                elif k == "guadagno":       # il guadagno medio della decisione (vite + 2 x forza), contro quello di tutte
                    base_ = tutte_[k]
                    testo = f"{v:+.1f}"
                    colr = C["muto"] if rg["poche"] or i == 0 or base_ is None or abs(v - base_) < 0.5 else (C["azzurro"] if v > base_ else C["rosso"])
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

    def disegna_mulligan(self, c, r, W):
        F = self.F
        m = DEC.mulligan(r)
        wr = lambda t: f"{100 * t[1] / t[0]:.0f}%" if t and t[0] else "-"
        c.create_text(14, 14, text=f"YOUR MULLIGANS · {len(r)} GAMES · to read your improvement: fewer risky hands kept, and a better win rate after a mulligan",
                      anchor="w", fill=C["muto"], font=F(7, True))
        y = 36
        for i, (nome, t, nota) in enumerate((("AFTER A MULLIGAN", m["dopo"], "games where you sent at least one hand back"),
                                             ("RISKY KEEPS", m["rischiose"], "7 cards kept with 0-1 or 5+ lands"),
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
        for x, t in ((14, "LANDS"), (120, "ON THE PLAY"), (300, "ON THE DRAW"), (480, "ALL"), (620, "HANDS YOU SENT BACK")):
            c.create_text(x, y, text=t, anchor="w", fill=C["titolo"], font=F(7, True))
        y += 16
        for i, terre in enumerate(range(0, 8)):
            d_ = m["tenute"].get(terre, {})
            pl, dr = d_.get("Play", (0, 0)), d_.get("Draw", (0, 0))
            tot = (pl[0] + dr[0], pl[1] + dr[1])
            c.create_rectangle(8, y, 800, y + 22, fill="#202024" if i % 2 == 0 else "#1c1c20", outline="")
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
        cols = ((14, "WEEK OF"), (130, "GAMES"), (210, "MULLIGAN RATE"), (340, "RISKY KEEPS"), (460, "WIN RATE AFTER A MULLIGAN"), (660, "WIN RATE OF 7-CARD KEEPS"),
                (860, "ALL"))
        for x, t in cols:
            c.create_text(x, y, text=t, anchor="w", fill=C["titolo"], font=F(7, True))
        y += 16
        fmt = lambda v: "-" if v is None else f"{v:.0f}%"
        for i, w in enumerate(DEC.settimane(r)):
            c.create_rectangle(8, y, 960, y + 22, fill="#202024" if i % 2 == 0 else "#1c1c20", outline="")
            for x, v in ((14, w["da"].strftime("%d %b")), (130, str(w["partite"])), (210, fmt(w["mull"])), (340, fmt(w["rischiose"])),
                         (460, fmt(w["wr_mull"]) + (f"  · {w['n_mull']} games" if w["n_mull"] else "")), (660, fmt(w["wr_sette"])), (860, fmt(w["wr"]))):
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
        """La finestrella dei filtri di Cards: una spunta per riga, All e None; si applica subito e resta (DA.salva_righe_carte)."""
        tk = self.tk
        f = getattr(self, "fin_righe", None)
        if f is None or not f.winfo_exists():
            f = self.fin_righe = tk.Toplevel(self.fr)
            f.title("Cards · Rows")
            f.configure(bg=C["scheda"])
            f.resizable(False, False)
            f.bind("<Escape>", lambda e: f.destroy())
            c = self.cv_righe = tk.Canvas(f, bg=C["scheda"], highlightthickness=0, bd=0, width=560, height=40 + 30 * len(DA.RIGHE_CARTE) + 50)
            c.pack(padx=8, pady=8)
            c.bind("<Button-1>", self.clic_righe_carte)
            try:
                f.geometry(f"+{self.fr.winfo_pointerx() - 120}+{self.fr.winfo_pointery() + 16}")
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
        c.delete("all")
        c._box = []
        scelte_r = set(DA.righe_carte_scelte())
        c.create_text(12, 16, text="THE ROWS OF CARDS · tick the ones you want to see", anchor="w", fill=C["azzurro"], font=F(8, True))
        y = 40
        for k, titolo in DA.RIGHE_CARTE:
            on = k in scelte_r
            c.create_image(14, y + 10, image=DG.spunta(14, on, C["azzurro"], C["fondo"], C["grigio"], C["fondo"]), anchor="w")
            nome, _s, resto = titolo.partition(" · ")
            i_ = c.create_text(38, y + 10, text=nome, anchor="w", fill=C["titolo"] if on else C["grigio"], font=F(9, True))
            if resto:
                bb = c.bbox(i_)
                c.create_text(bb[2] + 8, y + 10, text=resto, anchor="w", fill=C["muto"], font=F(7))
            c._box.append((6, y, 552, y + 22, k))
            y += 30
        y += 8
        for x0, testo, k in ((14, "All", "*"), (84, "None", "-")):
            c.create_rectangle(x0, y, x0 + 60, y + 26, fill="#202024", outline="#3a3a40")
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
            cv.bind("<MouseWheel>", lambda e: (self.via_hover_carte(), e.widget.yview_scroll(-2 if e.delta > 0 else 2, "units")))
            cv.bind("<Motion>", self.sopra_carte)
            cv.bind("<Leave>", lambda e: self.via_hover_carte())
            cv.bind("<Configure>", lambda e: self.disegna_coppie())
        self.coppie_di = (chiave, titolo or dict(DA.RIGHE_CARTE).get(chiave, chiave))
        self.coppie_k = getattr(self, "coppie_k", 2)
        f.title("Performance · Pairs · " + self.coppie_di[1].split(" · ")[0].title())
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
        kk = self.coppie_k
        cp = DA.coppie_carte(r, chiave, k=kk)
        quale = "IN YOUR OPENING HAND" if chiave == "pesc1" else "· " + titolo.split(" · ")[0]
        # Pairs e Trios (13 nov 2026, Autore: «nella sezione cards sarebbe bene avere anche oltre alle coppie i tris»): due interruttori in cima
        x_ = 14
        for k2, nome in ((2, "Pairs"), (3, "Trios")):
            i_ = c.create_text(x_ + 10, 16, text=nome, anchor="w", fill="#ffffff" if kk == k2 else C["grigio"], font=F(9, True))
            bb = c.bbox(i_)
            c.create_rectangle(x_, 4, bb[2] + 10, 28, fill="#0f86cc" if kk == k2 else "#202024", outline="#0f86cc" if kk == k2 else "#3a3a40")
            c.tag_raise(i_)
            c._box_coppie.append((x_, 4, bb[2] + 10, 28, ("k", k2), None))
            x_ = bb[2] + 18
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

    def carta_sotto(self, e):
        c = e.widget
        x, y = c.canvasx(e.x), c.canvasy(e.y)
        return next((b for b in getattr(c, "_box_carte", []) if b[0] <= x <= b[2] and b[1] <= y <= b[3]), None)

    def clic_carte(self, e):
        """Il clic su una carta: solo le partite in cui c'e', nel senso della sua riga (in mano, pescata in quel turno, lanciata, rimasta in mano); di nuovo
        sulla stessa, tutte. Su «Pairs ›» di una riga: la finestra delle sue coppie."""
        cv = e.widget
        x, y = cv.canvasx(e.x), cv.canvasy(e.y)
        bc = next((b for b in getattr(cv, "_box_coppie", []) if b[0] <= x <= b[2] and b[1] <= y <= b[3]), None)
        if bc is not None:
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
        h.configure(bg="#101014")
        self.tk.Label(h, image=img, bg="#101014", bd=0).pack(padx=2, pady=2)
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
            c.create_rectangle(0, y, W - 2, y + ALTO_MIO - 6, fill="#0f2a38" if on else ("#202024" if i % 2 == 0 else "#1c1c20"),
                               outline=C["accento"] if on else "#2c2c32")
            c.create_text(14, y + 16, text=corto(f"{tipo} · " + self.descrivi(fl, tipo), int((W - 640) / 6.4)), anchor="w", fill=C["titolo"], font=F(9, True))
            c.create_text(14, y + 36, text=f"{k_['n']} games · {k_['vinte']}-{k_['perse']}" + (f" · 95% CI {k_['ic'][0]}–{k_['ic'][1]}%" if k_["ic"] else ""),
                          anchor="w", fill=C["grigio"], font=F(7))
            xw = W - 600
            wr = k_["wr"]
            col = C["muto"] if wr is None else (C["azzurro"] if wr >= 50 else C["rosso"])
            c.create_rectangle(xw, y + 20, xw + 140, y + 32, fill="#2c2c32", outline="")
            if wr is not None:
                c.create_rectangle(xw, y + 20, xw + 1.4 * wr, y + 32, fill=col, outline="")
            c.create_line(xw + 70, y + 16, xw + 70, y + 36, fill="#d8d8dc")
            c.create_text(xw + 150, y + 26, text=f"{wr:.0f}%" if wr is not None else "-", anchor="w", fill=col, font=F(11, True))
            if wr is not None and tot["wr"] is not None:
                d_ = wr - tot["wr"]
                c.create_text(xw + 215, y + 26, text=f"{d_:+.1f} vs all", anchor="w", fill=C["azzurro"] if d_ > 0 else C["rosso"] if d_ < 0 else C["testo"],
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
            c.create_rectangle(0, y, W - 2, y + 38, fill="#202024" if k % 2 == 0 else "#1c1c20", outline="#3a3220")
            c.create_polygon(12, y + 10, 22, y + 10, 22, y + 28, 17, y + 23, 12, y + 28, fill="#ffd23f", outline="")
            quando = s_.get("quando", "")[:16].replace("T", " ")
            c.create_text(34, y + 12, text=f"{s_.get('mio') or '-'} vs {s_.get('suo') or '-'}", anchor="w", fill=C["titolo"], font=F(8, True))
            c.create_text(34, y + 27, text=f"{quando} · {'won' if s_.get('vinta') else 'lost'} · {s_.get('passo')}"
                          + (" · every action" if s_.get("modo") == "azioni" else ""), anchor="w", fill=C["grigio"], font=F(7))
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
        for k, b in self.b_tipi.items():
            b.metti(k, k == self.tipo)
        self.filtri = dict(s.get("filtri") or {})
        self.disegna()
