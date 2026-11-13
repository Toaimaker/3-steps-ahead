"""La finestra grande del Companion: testata, linguette delle schede, chat a sinistra, colonna social. Companion.bat la apre."""
import os, sys
_casa = os.path.dirname(os.path.abspath(__file__))      # si sale fino a percorsi.py, che mette nel sys.path tutte le cartelle del Companion
while not os.path.isfile(os.path.join(_casa, "percorsi.py")):
    _casa = os.path.dirname(_casa)
if _casa not in sys.path:
    sys.path.insert(0, _casa)
import percorsi  # noqa: E402,F401
import piattaforma  # noqa: E402  (Windows e Mac: flag dei processi, Python, percorsi)
import datetime
import json
import queue
import re
import subprocess
import threading
import time
import tkinter as tk
import tkinter.font as tkfont

import capsule as CAP
import collezione_carte as CC
import finestra_social as SOC
import premi_eventi as PE
import registro_errori
import risorse as RS
import tk_sicuro

from ambiente import ASSET, FUORI_SCHERMO, LOGDIR, POS_JSON, PRODOTTO, PUBBLICA, PY_MUTO, VERSIONE
from chat_finestra import ChatFinestra
from chat_partita import Partita
from chat_testi import ora_riga
from dati_app import SCHEDE, coppie, costruite
from dati_drafter import LOG_ARENA, campo, draft_da_untapped, limited_dal_log
from deck_sheet import DeckSheet
from diario import Diario, e_limited, evento_partita, senza_ora
from drafter_evento import DrafterEvento
from drafter_mazzi import DrafterMazzi
from drafter_partita import DrafterPartita
from icone import emoji_png, icona_azione, icona_omino, icone_mana, logo_lega
from pagina_base import Pagina, prepara_capsule
from pagina_collezione import PaginaCollezione
from pagina_help import PaginaHelp
from pagina_settings import PaginaSettings
from pagina_mazzi import PaginaMazzi
from pagina_meta import PaginaMeta
from pagina_performance import PaginaPerformance
from pagina_risorse import PaginaRisorse
from pescate import Pescate
from tema import C, CI, barra_scura, carica_font
from widget import TendinaMulti, pulsante_solido


GC_PRIMO, GC_OGNI, GC_FERMO = 30, 1800, 5       # secondi: il primo congelamento dopo l'avvio, poi ogni mezz'ora, a mouse e tastiera fermi (congela)


class Finestra(ChatFinestra, DrafterEvento, DrafterMazzi, DeckSheet, DrafterPartita):
    """La finestra grande del Companion: costruita in __init__, aggiornata dal giro. avvia() la crea e accende il ciclo di Tk."""

    def __init__(self):
        # la finestra compare prima, i disegni pesanti dopo (11 nov 2026, sessione Magic 13): il database delle carte si legge in un filo da subito, e finche' la
        # finestra si costruisce nessuna pagina si disegna (Pagina.AVVIO); la scheda davanti si disegna appena la finestra e' a schermo (fine_avvio). Prima la
        # Meta si disegnava dentro la costruzione: 1,9 s senza finestra
        CC.precarica()
        Pagina.AVVIO = True
        self._costruisci_finestra()
        self._passo("Opening the chat…", 0.30)
        self._costruisci_chat()
        self._passo("Loading your decks and the meta…", 0.45)
        self._costruisci_colonna()
        self._costruisci_schede()
        self._passo("Reading your games…", 0.70)
        self._costruisci_avvio()
        self._passo("Drawing the first tab…", 0.85)

    def _costruisci_finestra(self):
        """La finestra: posizione, logo, font, testata, barra delle schede, piede."""
        if not FUORI_SCHERMO:        # pythonw non ha uscite: errori e righe «giro: ...» in Log_Arena/finestra_AAAAMMGG.txt (7 nov 2026)
            registro_errori.installa("finestra")
        carica_font()
        from tema import id_app
        id_app(PRODOTTO)        # il logo nella barra delle applicazioni, non quello di Python (10 nov 2026)
        self.root = tk.Tk()
        registro_errori.lega_tk(self.root)
        self.root.title(PRODOTTO)       # «Companion» fino al 10 nov 2026: il nome dell'app, 3 Steps Ahead
        self.root.configure(bg=CI["fondo"])
        # 960 dal 17 ott 2026: le schede dei tipi di gioco hanno grafico, numeri, mazzi e meta. Si apre dove l'hai lasciata, la prima volta sul secondo schermo
        try:
            pos_salvata = json.load(open(POS_JSON, encoding="utf-8"))
        except (OSError, ValueError):
            pos_salvata = None
        self.geo0, ingrandita = posizione_iniziale(monitor(self.root), pos_salvata)
        self.root.geometry("900x960+5000+20" if FUORI_SCHERMO else self.geo0)
        # la schermata di caricamento, come Steam (13 nov 2026, Autore: «al primo avvio una finestra di caricamento, poi parte l'app»): la finestra grande
        # si costruisce trasparente (a schermo, le pagine si misurano giuste) e compare a prima scheda disegnata (mostra_app). Mai nelle prove fuori schermo,
        # mai se chi l'ha creata l'ha gia' resa invisibile (il metro grafico: trasparente all'1%)
        self.schermata, self._alpha_mio = None, False
        if not FUORI_SCHERMO:
            try:
                if float(self.root.attributes("-alpha")) >= 1.0:
                    self.root.attributes("-alpha", 0.0); self._alpha_mio = True
                    import schermata_avvio as SA
                    m_ = re.match(r"\d+x\d+\+(-?\d+)\+(-?\d+)$", self.geo0)
                    sch = monitor(self.root)
                    z_ = next((x_ for x_ in sch if m_ and x_[0] <= int(m_.group(1)) < x_[2] and x_[1] <= int(m_.group(2)) < x_[3]), sch[0] if sch else None)
                    self.schermata = SA.Schermata(tk, self.root, geo=SA.centro(z_) if z_ else None, versione=VERSIONE)
                    self.schermata.passo("Starting…", 0.12)
            except Exception as e:      # noqa: BLE001 - senza schermata l'app parte lo stesso
                print("schermata:", e)
                self._mostra_subito()
        if ingrandita and not FUORI_SCHERMO:
            self.root.update_idletasks(); self.root.state("zoomed")
        # il logo dell'app, lo stesso del collegamento sul desktop: dal 10 nov 2026 le tre carte di 3 Steps Ahead (Distribuzione/logo.py; fino a quel giorno
        # le due carte con la gemma del 3 nov, «due carte da gioco e le gemme di arena»); se manca, il quadratino di prima
        logo = os.path.join(ASSET, "companion_icona.png")
        try:
            icona = tk.PhotoImage(file=logo)
        except (tk.TclError, OSError):
            icona = tk.PhotoImage(width=32, height=32)
            icona.put(CI["testa"], to=(0, 0, 32, 32)); icona.put(CI["led"], to=(11, 11, 21, 21))
        self.root.iconphoto(True, icona)
        try:        # il file .ico ha tutte le misure: la barra delle applicazioni prende la sua, non la 256 ridotta
            self.root.iconbitmap(default=os.path.join(ASSET, "companion.ico"))
        except (tk.TclError, OSError):
            pass
        from tema import icona_finestra     # e sulla finestra vera di Windows, se no la barra mostra la piuma di Tk (10 nov 2026)
        self.root.after(50, lambda: icona_finestra(self.root, os.path.join(ASSET, "companion.ico")))
        barra_scura(self.root, CI["testa"], CI["titolo"], CI["filo"])
        from tema import nascondi_titolo
        self.root.after(80, lambda: nascondi_titolo(self.root))       # il nome e il logo stanno nella testata, piu' grandi (10 nov 2026)
        fam = "Poppins" if "Poppins" in tkfont.families() else "Segoe UI"
        famm = "Poppins Medium" if "Poppins Medium" in tkfont.families() else fam
        self.F = lambda n, m=False: (famm if m else fam, n)
        self.mana = {k: tk.PhotoImage(file=v) for k, v in icone_mana(16).items()}
        self.quadri = {k: tk.PhotoImage(width=10, height=10) for k in ("tu", "lui", "info")}
        for self.k, self.col in (("tu", C["verde"]), ("lui", C["rosso"]), ("info", C["arancio"])):
            self.quadri[self.k].put(self.col, to=(0, 0, 10, 10))
        for self.k, self.col in (("tu", C["verde"]), ("lui", C["rosso"])):
            try:
                self.quadri[self.k] = tk.PhotoImage(file=icona_omino(self.col, 14))
            except Exception:
                pass

        # la testata: solo il logo e il nome dell'app, un po' piu' grandi (Autore, 10 nov 2026: «su questa barra dell'app non deve apparire mai null'altro che il
        # nome dell'app in alto a sx un po' piu' grande con il suo logo»). La barra di Windows sopra non scrive niente (nascondi_titolo): il nome resta per la barra
        # delle applicazioni. Fino a quel giorno qui c'erano il quadratino, l'evento o «waiting for a game» e le vite: le vite sono nel pannello della partita.
        testa = tk.Frame(self.root, bg=CI["testa"], highlightthickness=0)
        testa.pack(fill="x")
        self.v_contro = tk.StringVar(value="")      # le scrive ancora la chat; non si mostrano piu'
        self.v_vite = tk.StringVar(value="")
        try:
            from PIL import Image, ImageTk
            self.logo_testa = ImageTk.PhotoImage(Image.open(logo).convert("RGBA").resize((24, 24), Image.LANCZOS))
        except Exception:
            self.logo_testa = None
        if self.logo_testa is not None:
            tk.Label(testa, image=self.logo_testa, bg=CI["testa"], bd=0).pack(side="left", padx=(14, 9), pady=7)
        tk.Label(testa, text=PRODOTTO, bg=CI["testa"], fg=CI["titolo"], font=self.F(13, True), bd=0).pack(side="left", padx=(0 if self.logo_testa else 14, 0), pady=7)
        tk.Frame(self.root, bg=CI["filo"], height=1).pack(fill="x")

        # la barra delle schede, come le shelf di Maya: una scheda per tipo di gioco, cambia solo la colonna destra
        self.barra_schede = tk.Frame(self.root, bg=CI["fondo"]); self.barra_schede.pack(fill="x", padx=12, pady=(8, 0))

        tk.Frame(self.root, bg=CI["filo"], height=1).pack(fill="x", padx=12)
        self.linguette = {}

        # il nome del prodotto e la versione, sempre in fondo a destra (Autore, 4 nov 2026): si impacca prima del corpo, che se no si prende tutto lo spazio
        piede = tk.Frame(self.root, bg=CI["fondo"]); piede.pack(side="bottom", fill="x", padx=12, pady=(0, 4))

        # dal 13 nov 2026 la versione e' un pulsante ben visibile (Help/pulsante_versione.py): «Download version X» o «Up to date · latest version X»; nasce
        # quando c'e' la scheda Help, qui il suo posto
        self.piede_versione = tk.Frame(piede, bg=CI["fondo"]); self.piede_versione.pack(side="right", pady=(2, 0))
        tk.Label(piede, text=PRODOTTO, bg=CI["fondo"], fg=CI["muto"], font=self.F(8), pady=0).pack(side="right", padx=(0, 10))
        colonna = self.colonna_social = SOC.ColonnaSocial(tk, self.root, self.F, CI, pulsante_solido, logo_lega)
        colonna.fr.pack(side="right", fill="y", padx=(0, 12), pady=(12, 4))
        self.root.minsize(1014 + SOC.LARGA + 12, 600)       # la larghezza di sempre piu' la colonna: i mazzi non si stringono
        self.corpo = tk.Frame(self.root, bg=CI["fondo"]); self.corpo.pack(fill="both", expand=True, padx=12, pady=(12, 4))

        if "--fuori-schermo" not in sys.argv:       # le carte di Collection si cuociono in sottofondo: finito il lavoro esce subito, e con Arena aperto aspetta
            self.root.after(8000, lambda: subprocess.Popen([PY_MUTO, "-I", "-X", "utf8", percorsi.programma("cuoci_carte.py")], cwd=percorsi.ROOT, **piattaforma.flag("sotto")))
        self.corpo.columnconfigure(0, weight=11, uniform="c"); self.corpo.columnconfigure(1, weight=10, uniform="c"); self.corpo.rowconfigure(0, weight=1)



    def _costruisci_chat(self):
        """A sinistra la mini chat della partita, con la sua barra di scorrimento e il pulsante dell'ultima azione."""

        # ---- sinistra: la mini chat
        self.sx, chat_f, v_part = self.scheda(self.corpo, "Partita")
        v_part.lab.pack_forget()
        # testata della scheda in griglia: sopra omino e numero, sotto i colori giocati che partono sotto il numero, con «vs» in mezzo
        testa_p = tk.Frame(v_part.cap, bg=C["cap"]); testa_p.pack(side="right", padx=10, pady=4)

        self.tp = {}
        self.tp["omino_mio"] = tk.Label(testa_p, image=self.quadri["tu"], bg=C["cap"]); self.tp["omino_mio"].grid(row=0, column=0, padx=(0, 3))

        self.tp["mio"] = tk.Label(testa_p, text="", bg=C["cap"], fg=C["verde_t"], font=self.F(9, True)); self.tp["mio"].grid(row=0, column=1, sticky="w")

        self.tp["vs"] = tk.Label(testa_p, text="", bg=C["cap"], fg=C["grigio"], font=self.F(9)); self.tp["vs"].grid(row=0, column=2, padx=8)

        self.tp["omino_suo"] = tk.Label(testa_p, image=self.quadri["lui"], bg=C["cap"]); self.tp["omino_suo"].grid(row=0, column=3, padx=(0, 3))

        self.tp["suo"] = tk.Label(testa_p, text="", bg=C["cap"], fg=C["rosso_t"], font=self.F(9, True)); self.tp["suo"].grid(row=0, column=4, sticky="w")

        self.tp["d"] = tk.Label(testa_p, text="", bg=C["cap"], fg=C["testo"], font=self.F(9, True)); self.tp["d"].grid(row=0, column=5, padx=(12, 0))

        ventagli = {}
        for self.k, self.col, c in (("tu", C["verde"], 0), ("lui", C["rosso"], 3)):
            try:
                ventagli[self.k] = tk.PhotoImage(file=icona_azione("ventaglio", self.col, 16))
                tk.Label(testa_p, image=ventagli[self.k], bg=C["cap"]).grid(row=1, column=c, padx=(0, 3), pady=(2, 0))
            except Exception:
                pass
        testa_p._ventagli = ventagli  # le immagini devono restare vive
        self.col_mio = tk.Frame(testa_p, bg=C["cap"]); self.col_mio.grid(row=1, column=1, sticky="w", pady=(2, 0))

        self.tp["vs2"] = tk.Label(testa_p, text="vs", bg=C["cap"], fg=C["grigio"], font=self.F(9)); self.tp["vs2"].grid(row=1, column=2, padx=8)

        self.col_suo = tk.Frame(testa_p, bg=C["cap"]); self.col_suo.grid(row=1, column=4, sticky="w", pady=(2, 0))

        # i dati dei due mazzi stanno tutti qui in testata (13 ott 2026): sotto i colori, le carte contate e le viste
        self.tp["n_mio"] = tk.Label(testa_p, text="", bg=C["cap"], fg=C["grigio"], font=self.F(7)); self.tp["n_mio"].grid(row=2, column=1, sticky="w")

        self.tp["n_suo"] = tk.Label(testa_p, text="", bg=C["cap"], fg=C["grigio"], font=self.F(7)); self.tp["n_suo"].grid(row=2, column=4, sticky="w")

        self.tp["nota"] = tk.Label(testa_p, text="", bg=C["cap"], fg=C["grigio"], font=self.F(7)); self.tp["nota"].grid(row=2, column=5, padx=(12, 0))

        self.sx.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        # la testata «Partita» sopra la chat non si mostra (Autore, 17 ott 2026 ~22:30: «sopra la chat togli la scheda partita,
        # ora quei dati li abbiamo a destra»): forza e colori dei mazzi stanno nella scheda «Partita» della colonna destra
        for w in v_part.cap.master.winfo_children()[:2]:
            w.pack_forget()
        # chi chiude prima: non si mostra piu' (Autore, 5 nov 2026: «togli l'area who closes first»); le barre restano costruite e non impacchettate, i conti le aggiornano ancora
        gara = tk.Frame(chat_f, bg=C["scheda"])
        self.barre = {}
        for self.k, self.col in (("tu", C["verde"]), ("lui", C["rosso"])):
            r = tk.Frame(gara, bg=C["scheda"]); r.pack(fill="x", pady=1)
            tk.Label(r, text={"tu": "you", "lui": "opp"}[self.k], width=4, anchor="w", bg=C["scheda"], fg=C["grigio"], font=self.F(8)).pack(side="left")
            lv = tk.StringVar(value=""); tk.Label(r, textvariable=lv, width=9, anchor="e", bg=C["scheda"], fg=C["testo"], font=self.F(8)).pack(side="right")
            cv = tk.Canvas(r, height=6, width=40, bg=C["traccia"], highlightthickness=0); cv.pack(side="left", fill="x", expand=True)
            self.barre[self.k] = (cv, self.col, lv)
        # la chat con la sua barra di scorrimento a destra (Autore, 13 ott 2026): sottile, nei colori della finestra (quella di
        # Windows non si colora), si trascina o si clicca, sparisce quando tutto il testo ci sta
        chat_box = tk.Frame(chat_f, bg=C["scheda"]); chat_box.pack(fill="both", expand=True)

        self.barra = tk.Canvas(chat_box, width=8, bg=C["scheda"], highlightthickness=0, bd=0, cursor="arrow")
        self.barra.pack(side="right", fill="y", padx=(6, 0))
        self.chat = tk.Text(chat_box, bg=C["scheda"], fg=C["testo"], font=self.F(10), wrap="word", bd=0, highlightthickness=0, height=8,
                       padx=0, pady=4, spacing1=3, spacing3=3, cursor="arrow")
        self.chat.pack(side="left", fill="both", expand=True)
        self.scorri = {"a": 0.0, "b": 1.0, "presa": None, "sopra": False}

        # il pulsante per tornare all'ultima azione (in cima): compare solo quando hai fatto scorrere la chat (13 ott 2026)
        self.torna = tk.Label(chat_box, text="↑  LATEST ACTION", bg=C["azzurro_s"], fg=C["azzurro"], font=self.F(8, True), padx=10, pady=3, cursor="hand2")
        self.torna.bind("<Button-1>", lambda e: self.chat.yview_moveto(0.0))
        self.torna.bind("<Enter>", lambda e: self.torna.configure(fg=C["titolo"]))
        self.torna.bind("<Leave>", lambda e: self.torna.configure(fg=C["azzurro"]))

        self.chat.configure(yscrollcommand=self.barra_set)
        self.barra.bind("<Button-1>", self.barra_premi); self.barra.bind("<B1-Motion>", self.barra_trascina); self.barra.bind("<ButtonRelease-1>", self.barra_lascia)


        self.barra.bind("<Configure>", lambda e: self.barra_disegna())
        self.barra.bind("<Enter>", lambda e: (self.scorri.update(sopra=True), self.barra_disegna()))
        self.barra.bind("<Leave>", lambda e: (self.scorri.update(sopra=False), self.barra_disegna()))
        self.barra.bind("<MouseWheel>", lambda e: self.chat.yview_scroll(piattaforma.scatti(e.delta) * 3, "units"))
        self.chat.tag_configure("sep_tu", foreground=C["verde_t"], font=self.F(8, True), spacing1=10)
        self.chat.tag_configure("sep_lui", foreground=C["rosso_t"], font=self.F(8, True), spacing1=10)
        self.chat.tag_configure("sep_info", foreground=C["arancio"], font=self.F(8, True), spacing1=10)
        self.chat.tag_configure("barrato", overstrike=1, foreground=C["muto"])
        self.chat.tag_configure("nota", foreground=C["azzurro"], font=self.F(8))
        self.chat.tag_configure("sotto", lmargin1=30, lmargin2=30, spacing1=0, spacing3=1)   # carte e minidati sotto l'azione, allineati al testo
        self.chat.tag_configure("fase", foreground=C["titolo"], font=self.F(12, True), spacing1=10, spacing3=4)   # la fase del turno: il titolo
        self.chat.tag_configure("azione", foreground=C["testo"], font=self.F(10, True))             # l'azione: stampatello grassetto bianco
        self.chat.tag_configure("carta", foreground=C["testo"], font=self.F(10))                    # le carte coinvolte: bianco, normale
        self.chat.tag_configure("vuota", foreground=C["grigio"], font=self.F(9, True), lmargin1=30, lmargin2=30)   # «niente da fare»
        self.chat.tag_configure("info", foreground=C["arancio"])
        self.chat.tag_configure("vinta", foreground=C["verde_t"], font=self.F(11, True))
        self.chat.tag_configure("persa", foreground=C["rosso_t"], font=self.F(11, True))
        self.chat.tag_configure("aria", font=self.F(4), spacing1=2, spacing3=2)
        self.chat.tag_configure("letale", foreground=C["verde_t"], font=self.F(12, True))
        self.chat.tag_configure("voce", spacing1=1, spacing3=1)
        self.chat.tag_configure("turno", foreground=C["acciaio"], font=self.F(8, True))
        self.chat.tag_configure("fatto", foreground=C["muto"])
        self.chat.tag_configure("adesso", foreground=C["titolo"], font=self.F(11, True))
        self.chat.tag_configure("vittoria", foreground=C["verde_t"], font=self.F(16, True))
        self.chat.tag_configure("centro", justify="center")
        self.chat.tag_configure("evidenza", background=C["evidenza"], lmargincolor=C["evidenza"], rmargincolor=C["evidenza"])
        self.chat.tag_lower("evidenza")
        for self.k in ("sep_tu", "sep_lui", "sep_info"):
            self.chat.tag_configure(self.k, spacing1=2)
        self.linee = []
        self.chat.bind("<Configure>", lambda e: [ln.configure(width=max(e.width - 4, 50)) for ln in self.linee])
        self.chat.configure(state="disabled")

    def _costruisci_colonna(self):
        """Il mazzo a sinistra a pick finiti e la colonna destra della scheda Drafter: Rare pick, record, Play limited, Closed session, partita, mazzi, calendario, fasi."""
        # ---- sinistra, a pick finiti: il mazzo (Autore, 8 nov 2026: «la chat esiste solo per il pick dei mazzi / il mazzo poi alla fine appare a sx e a destra restano i dati
        # del mazzo come una classica scheda mazzo: tier, win turns, grafico archetipo»; in partita la chat dei consigli torna, scelta sua). Si mostra al posto della chat (lato)
        self.sx_m, self.b_m, v_m = self.scheda(self.corpo, "Your deck", P=CI)
        self.lato_v = {"v": None}       # cosa sta a sinistra nel Drafter: "chat", "mazzo" o "niente" (la costruzione: i tre mazzi prendono tutta la larghezza)
        # ---- destra: i dati
        self.dx = tk.Frame(self.corpo, bg=CI["fondo"]); self.dx.grid(row=0, column=1, sticky="nsew")
        # le altre schede, una sopra l'altra a tutta larghezza, sopra la chat e la colonna del Drafter (9 nov 2026): restano montate alla
        # loro misura e il clic porta davanti la scelta, gia' disegnata. «copri» nasconde le schede quando davanti c'e' il Drafter,
        # che fra chat e colonna lascia uno spiraglio
        self.altre = tk.Frame(self.corpo, bg=CI["fondo"]); self.altre.grid(row=0, column=0, columnspan=2, sticky="nsew")
        self.copri = tk.Frame(self.corpo, bg=CI["fondo"]); self.copri.grid(row=0, column=0, columnspan=2, sticky="nsew")
        self.altre.lower(); self.copri.lower()

        self.pag_corso = tk.Frame(self.dx, bg=CI["fondo"])

        self.s1, b1, self.v_ev = self.scheda(self.pag_corso, "This draft", P=CI)
        self.s1.pack(fill="x", pady=(0, 8))
        # la spunta Rare pick (Autore, 8 nov 2026: «sul drafter attiviamo la spunta rare pick cosi' e' una funzione che si puo'
        # attivare o disattivare quando vuole il giocatore»): nella testata di This draft e dei mazzi, cosi' si vede prima, durante e
        # dopo i pick. Scrive Log_Arena/rare_pick.json; il companion la rilegge a ogni pick (pick_predittivo.rare_pick_attivo)
        self.FILE_RARE_PICK = os.path.join(LOGDIR, "rare_pick.json")
        self.spunte_rare = []
        self.spunta_rare(self.v_ev.cap)
        # il record con una coppa per ogni vinta e un teschio per ogni persa, e il win rate del draft (Autore, 17 ott 2026)
        # su un Canvas, con lo stesso fondo dei mazzi (Autore, 5 nov 2026: «diamo uno sfondo pattern dark anche alla sezione this draft»): l'arte della seconda carta del mazzo
        self.ALTO_REC = 72
        self.tela_rec = tk.Canvas(b1, height=self.ALTO_REC, bg=CI["scheda"], highlightthickness=0, bd=0); self.tela_rec.pack(fill="x")

        # senza un evento limited avviato la sezione e' Play limited, col pulsante Launch (Autore, 6 nov 2026: «quando nessun evento limited e' stato avviato, la sezione this draft deve essere:
        # play limited e ci deve essere dentro un pulsante launch»)
        self.f_play = tk.Frame(b1, bg=CI["scheda"])
        self.l_play = tk.Label(self.f_play, text="No limited event running", bg=CI["scheda"], fg=CI["grigio"], font=self.F(9), anchor="w"); self.l_play.pack(side="left", fill="x", expand=True)

        self.b_play = pulsante_solido(tk, self.F, self.f_play, "Launch", False, lambda: self.lancia_limited(), alto=40, bg=CI["scheda"]); self.b_play.configure(width=180); self.b_play.pack(side="right")


        self.play = dict(mostra=None, stato="fermo")       # stato: fermo, avvio, pronto, errore
        # Closed session (Autore, 8 nov 2026: «metti sul drafter un pulsante che dice closed session / il draft si chiude e parte la rotation post draft»): sotto il record, con un draft aperto.
        # Il primo clic chiede conferma, il secondo lancia Companion/App/Schede/Drafter/chiudi_draft.py, che scrive «=== FINE DRAFT» nel diario e fa il giro di fine draft del companion
        self.f_chiudi = tk.Frame(b1, bg=CI["scheda"])
        self.l_chiudi = tk.Label(self.f_chiudi, text="", bg=CI["scheda"], fg=CI["grigio"], font=self.F(9), anchor="w"); self.l_chiudi.pack(side="left", fill="x", expand=True)

        self.b_chiudi = pulsante_solido(tk, self.F, self.f_chiudi, "Closed session", False, lambda: self.chiudi_sessione(), alto=34, bg=CI["scheda"]); self.b_chiudi.configure(width=180); self.b_chiudi.pack(side="right", pady=(6, 0))


        self.chiusura = dict(conferma=None)
        self.img_rec = {}
        for self.k, car, self.nome in (("v", "\U0001F3C6", "coppa"), ("p", "\U0001F480", "teschio")):
            try:
                self.img_rec[self.k] = tk.PhotoImage(file=emoji_png(car, self.nome, 24))
            except Exception:
                pass
        self.tela_rec.bind("<Configure>", lambda e: self.disegna_record())

        # la partita: vite, turno, carte, e la forza del tuo mazzo contro le sue carte viste (GIH medio di 17Lands)
        s7, self.b7, self.v_part_dx = self.scheda(self.pag_corso, "Game", P=CI)

        # i mazzi, in basso a destra (Autore, 18 ott 2026: «i mazzi proposti li mette in basso a destra tutti e 3, una volta
        # inviato il mazzo ne resta solo 1 con sopra tutti i dati»): a fine pick i 3 proposti da rating_mazzi in tre colonne, dopo
        # il cancello il mazzo inviato col voto e l'elenco, con la probabilita' di pescata di ogni carta durante la partita
        self.s6, self.b6, self.v_inv = self.scheda(self.pag_corso, "Suggested decks", P=CI)
        self.s6.pack(fill="both", expand=True)
        self.spunta_rare(self.v_inv.cap)
        # il calendario degli eventi limited, senza un evento avviato: dal sito di Wizards, una riga per evento (Companion/App/Schede/Drafter/calendario_eventi.py)
        self.s_cal, b_cal, _v = self.scheda(self.pag_corso, "Limited events", P=CI)
        # in cima gli eventi che ti interessano (Autore, 6 nov 2026: «mettici in cima una tendina che mi permette di selezionare gli eventi che mi interessano»)
        self.t_cal = TendinaMulti(tk, b_cal, "Show", self.F, larga=240, bg=CI["scheda"]); self.t_cal.parola = "events"; self.t_cal.fr.pack(anchor="w", pady=(0, 8))


        self.cv_cal = tk.Canvas(b_cal, bg=CI["scheda"], highlightthickness=0); self.cv_cal.pack(fill="both", expand=True)

        self.calen = dict(file=None, righe=[], tipi=[])

        self.cv_cal.bind("<Configure>", self.disegna_calendario)
        # la rotella si aggiunge alle altre, mai al loro posto: unbind_all spegneva quelle di tutta la finestra (Farmer, Roadmap, Collection, social; 6 nov 2026, «resources ha i movimenti di scroll bloccati»)
        self.cv_cal.bind_all("<MouseWheel>", lambda ev: self.cv_cal.yview_scroll(-1 if ev.delta > 0 else 1, "units") if str(ev.widget).startswith(str(self.cv_cal)) else None, add="+")
        self.tit_mazzi = self.v_inv.cap.winfo_children()[0]
        self.inviato = {"mtime": None, "da": 0.0, "d": None}
        self.fix = {"per": None, "d": None, "on": None}      # il mazzo inviato corretto per il cancello (Companion/App/Overlay/correggi.py): «per» e' il cancello a cui risponde, «on» quello con l'hud acceso
        self.proposti = {"mtime": None, "d": None}
        # --mazzi proposti|inviato (collaudo): mostra i file di Log_Arena anche fuori da un draft, il mazzo inviato solo se richiesto
        self.FORZA_MAZZI = sys.argv[sys.argv.index("--mazzi") + 1] if "--mazzi" in sys.argv else None
        # le tre fasi della scheda Drafter (Autore, 5 nov 2026: «fase 1: la chat dei pick e i tre mazzi possibili che emergono / fase 2 costruzione del mazzo: sotto
        # le 3 colonne compare il pulsante select deck che invia l'hud in overlay / fase 3 le 3 colonne spariscono e appare l'interfaccia dei dati partita come e' adesso»;
        # «le colonne a destra e la chat a sinistra»). v: "pick", "costruzione" o None, la partita. Le decide il diario.
        self.fase = {"v": sys.argv[sys.argv.index("--fase") + 1] if "--fase" in sys.argv else None, "pick": None, "lanciato": None, "evento": "", "ripartito": False, "scelto": None, "sporco": False}
        self.in_corsa = {"mtime": None, "d": None}
        self.calcolo = {"p": None}
        self.scorri_c = {"y": 0.0}
        self.liste = CAP.Liste(tk, self.F)
        self.pescate = Pescate()
        self.scorri_l = {"y": 0.0}
        self.scorri_p = {"y": 0.0}     # i 3 proposti scorrono per conto loro
        # «Lui · cosa si vede» non entra piu' nella colonna (17 ott 2026: draft, partita, mazzo); resta costruito per disegna_lui
        s5, b5, self.v_lui = self.scheda(self.pag_corso, "Opponent", P=CI)
        self.righe_lui = tk.Frame(b5, bg=CI["scheda"]); self.righe_lui.pack(fill="x")


        self.stato = dict(draft=[], set="FRA", draft_colori="", draft_finito=False, untapped_in_corso=False)

    def _costruisci_schede(self):
        """Le pagine delle schede, le linguette che le aprono e la colonna social."""

        # le pagine dei tipi di gioco (Companion/App/Schede/) e le linguette che le aprono
        PaginaRisorse.PADRE_SALDO = self.barra_schede
        self.pagine = {"meta": PaginaMeta(tk, self.altre, self.F, self.mana), "corso": self.pag_corso, "performance": PaginaPerformance(tk, self.altre, self.F, self.mana), "mazzi": PaginaMazzi(tk, self.altre, self.F, self.mana), "risorse": PaginaRisorse(tk, self.altre, self.F, self.mana), "collezione": PaginaCollezione(tk, self.altre, self.F, self.mana),
                       "settings": PaginaSettings(tk, self.altre, self.F, self.mana),
                       "help": PaginaHelp(tk, self.altre, self.F, self.mana, controlla=not FUORI_SCHERMO)}
        self.perf = self.pagine["performance"]
        for k_, pg_ in self.pagine.items():
            if k_ != "corso":
                pg_.fr.place(x=0, y=0, relwidth=1, relheight=1)
        self.pag_corso.pack(fill="both", expand=True)
        self.scelta = {"v": None, "avviato": False}   # all'avvio il diario vecchio non sposta la scheda
        self.ultimo_input = time.time()
        for ev_ in ("<Motion>", "<Button>", "<Key>", "<MouseWheel>"):
            self.root.bind_all(ev_, lambda e: setattr(self, "ultimo_input", time.time()), add="+")
        self.root.after(1500, self.prepara_dietro)

        Pagina.MOSTRA_SCHEDA = self.mostra      # il builder dei mazzi porta a vista la Collection
        nascoste = {"corso"} if PUBBLICA else set()     # l'app pubblica (account.py): il Drafter vuole il motore del drafter e i suoi dati, non ci sono ancora
        for self.k, self.nome in SCHEDE:
            cella = tk.Frame(self.barra_schede, bg=CI["fondo"])
            if self.k not in nascoste:
                cella.pack(side="left", padx=(0, 2))
            sopra = tk.Frame(cella, bg=CI["fondo"], height=2); sopra.pack(fill="x")
            lab = tk.Label(cella, text=self.nome, bg=CI["fondo"], fg=CI["grigio"], font=self.F(9, True), padx=16, pady=5, cursor="hand2")
            lab.pack()
            lab.bind("<Button-1>", lambda e, k=self.k: self.mostra(k))
            lab.bind("<Enter>", lambda e, k=self.k, lab=lab: lab.configure(fg=CI["titolo"]) if self.scelta["v"] != k else None)
            lab.bind("<Leave>", lambda e, k=self.k, lab=lab: lab.configure(fg=CI["grigio"]) if self.scelta["v"] != k else None)
            self.linguette[self.k] = (lab, sopra)
        self.tendina_conto()
        if not FUORI_SCHERMO:       # l'HUD del mazzo avversario (12 nov 2026, sessione Magic 15): il pulsante e il pallino durante una partita
            import vista_hud
            self.hud = vista_hud.pulsante(self, tk)
        # un aggiornamento dell'app: un pallino sulla linguetta Help (10 nov 2026)
        import pulsante_versione
        self.pulsante_versione = pulsante_versione.PulsanteVersione(tk, self.F, self.piede_versione, self.pagine["help"], bg=CI["fondo"])
        self.pulsante_versione.c.pack()

        def su_agg(nuova):
            self.linguette["help"][0].configure(text="Help  ●" if nuova else "Help")
            self.pulsante_versione.aggiorna()
        self.pagine["help"].su_aggiornamento = su_agg
        self.pagine["help"].mostra_stato()
        scheda0 = sys.argv[sys.argv.index("--scheda") + 1] if "--scheda" in sys.argv else "meta"   # --scheda drafter|performance|limited|standard|risorse; si apre su Meta, la prima scheda (Autore,
        # 10 nov 2026: «il companion vedo che si apre sempre sulla scheda drafter invece che meta»): un draft o una partita che cominciano portano sul Drafter come prima
        if scheda0 in ("limited", "standard"):       # collaudo: Performance gia' sul modo chiesto
            self.perf.scegli(scheda0.capitalize())
        self.mostra({"drafter": "corso", "limited": "performance", "standard": "performance"}.get(scheda0, scheda0))

    def tendina_conto(self):
        """L'account di Arena nella barra delle schede, con la tendina (10 nov 2026, sessione Magic 12: un profilo per ogni account). Di partenza l'account con cui sei
        entrato in Arena, che l'app segue da sola; a mano un altro account o All accounts (numeri sommati, wishlist e Deck building in sola lettura). La scelta resta per
        questo PC (account.py). Anche nell'app di Autore (stesso giorno, Autore: «eh ma manca la tendina con il nome account»): li' c'e' solo il suo account, e
        la scelta non cambia niente."""
        self.t_conto = None
        from widget import Tendina
        t = self.t_conto = Tendina(tk, self.barra_schede, "", self.F, larga=190, bg=CI["fondo"])
        t.fr.winfo_children()[0].pack_forget()       # senza il titolo sopra: la barra delle schede resta bassa
        t.campo.configure(height=28)
        t.fr.pack(side="right", padx=(0, 14), pady=(0, 2))
        import account
        account.applica()       # i file dell'account (e con All accounts le copie unite) prima dei dati
        self.rinfresca_tendina_conto()

    def rinfresca_tendina_conto(self):
        import account
        if getattr(self, "t_conto", None) is None:
            return
        voci = account.conti()
        nomi = {i: n for i, n in voci}
        ultimo = account.leggi().get("ultimo") if PUBBLICA else account.AUTORE["id"]
        etichette = {i: ("●  " if i == ultimo else "     ") + n for i, n in voci}      # il pallino: l'account entrato in Arena
        etichette[account.TUTTI] = "     All accounts"
        self.t_conto.corte = dict({i: n for i, n in nomi.items()}, **{account.TUTTI: "All accounts"})
        self.t_conto.opzioni([i for i, _n in voci] + ([account.TUTTI] if len(voci) > 1 else []), self.scegli_conto, etichette=etichette)
        self.t_conto.set(account.attivo() or account.TUTTI)

    def scegli_conto(self, v):
        """Una voce della tendina: l'account entrato in Arena torna a «segui Arena»; un altro account o All accounts restano finche' Arena non cambia account."""
        import account
        if not PUBBLICA:        # l'app di Autore: un account solo, niente da cambiare
            return
        account.scegli(account.AUTO if v == account.leggi().get("ultimo") else v)
        self.cambia_conto()

    def cambia_conto(self):
        """L'account mostrato e' cambiato (la tendina, o un accesso nuovo ad Arena): i file dell'account, le copie in memoria, e tutti i dati si rileggono."""
        import account
        import dati_app
        import mazzi_salvati
        account.applica()
        mazzi_salvati.VERSIONE[0] += 1
        dati_app._JOLLY.clear(); dati_app._COLL["chiave"] = None
        self.rinfresca_tendina_conto()
        try:        # la colonna social: il profilo e gli amici dell'account
            import social
            self.colonna_social.d = social.Dati()
            self.colonna_social.img = None
            self.colonna_social.mostra_profilo(); self.colonna_social.disegna()
            self.colonna_social.discord.ricarica()      # la sessione di Discord dell'account
        except Exception as e:      # noqa: BLE001 - la colonna non ferma il cambio
            print("social:", f"{type(e).__name__}: {e}")
        self.dati_forza.set(); self.dati_ora.set(); self.risorse_ora.set()

    def _costruisci_avvio(self):
        """Lo stato della partita, il primo disegno, la posizione che si salva, il giro."""

        # ---- disegno della chat e del resto
        self.P = Partita()
        self.az = {}
        self.medaglie = {}
        self.rec = {"w": None, "l": None, "seq": []}

        ico_cancello = {}
        for self.k, self.nome, self.col in (("verde", "controllo", CI["verde"]), ("rosso", "avviso", CI["rosso"])):
            try:
                ico_cancello[self.k] = tk.PhotoImage(file=icona_azione(self.nome, self.col, 16))
            except Exception:
                pass

        if "--clic-chiudi" in sys.argv:       # collaudo: due clic su Closed session, dopo l'arrivo dei dati del draft
            self.root.after(9000, self.chiudi_sessione); self.root.after(9600, self.chiudi_sessione)

        if "--clic-launch" in sys.argv:       # collaudo: come premere Launch
            self.root.after(2500, self.lancia_limited)

        self.scorri_m = {"y": 0.0}

        self.FILE_TURNI = os.path.join(LOGDIR, "turni_chiusura.json")
        self.motore = {"lanciato": None, "mtime": None}
        self.numeri_cache = {}

        self.in_partita = {"v": None}

        self.coda = queue.Queue()

        self.root.after(1500, self.rinfresca_calendario)

        self.dati_ora = threading.Event()
        self.dati_forza = threading.Event()
        self.risorse_ora = threading.Event()       # un account nuovo: saldo e collezione subito (10 nov 2026)
        self.root.after(250, lambda: threading.Thread(target=self.lavoro_dati, daemon=True).start())
        if "--diario" not in sys.argv:
            self.root.after(5000, lambda: threading.Thread(target=self.lavoro_risorse, daemon=True).start())      # prima la finestra, poi i dati: il filo rallenta il primo disegno
        self.diario = Diario()

        self.fuori_limited = {"v": False}

        # la posizione si salva quando smette di cambiare; le finestre di prova non la toccano
        if not FUORI_SCHERMO and "--diario" not in sys.argv:
            timer = {"id": None, "geo": self.root.geometry() if self.root.state() == "normal" else self.geo0}

            def salva_pos():
                st = self.root.state()
                if st == "normal":
                    timer["geo"] = self.root.geometry()
                if st in ("normal", "zoomed"):
                    try:
                        json.dump(dict(geo=timer["geo"], ingrandita=st == "zoomed"), open(POS_JSON, "w", encoding="utf-8"))
                    except OSError:
                        pass

            def mossa(e):
                if e.widget is self.root:
                    if timer["id"]:
                        self.root.after_cancel(timer["id"])
                    timer["id"] = self.root.after(800, salva_pos)
            self.root.bind("<Configure>", mossa, add="+")
        self.assetto()
        self.disegna_record(); self.disegna_dati(); self.disegna_chat(); self.disegna_lui(); self.leggi_inviato(forza=True); self.leggi_proposti(forza=True)





        self.perf.segna(); self.pagine["risorse"].sporca = True      # si disegnano quando le apri

        self.root.after(100, self.giro)
        self.root.after(60, self.fine_avvio)
        self.root.after(15000, self.mostra_app)     # in ogni caso: la finestra non resta mai invisibile
        self.root.after(GC_PRIMO * 1000, self.congela)

    def congela(self):
        """Il garbage collector fuori dai ~210.000 oggetti che restano per sempre (moduli, cache, tabelle delle carte): una raccolta completa fermava la
        finestra 34-41 ms, dopo gc.freeze() 0 (11 nov 2026, sessione Magic 13). Si fa a mouse e tastiera fermi da GC_FERMO secondi, la prima volta dopo
        l'avvio e poi ogni GC_OGNI: si scongela, si raccoglie tutto (cosi' anche un ciclo di oggetti congelato e poi morto se ne va, ~40 ms a finestra ferma),
        si ricongela. Con l'utente al lavoro si riprova fra 10 s."""
        import gc
        if time.time() - getattr(self, "ultimo_input", 0) < GC_FERMO or self.pescate.in_partita:
            self.root.after(10000, self.congela)
            return
        try:
            gc.unfreeze()
            gc.collect()
            gc.freeze()
        finally:
            self.root.after(GC_OGNI * 1000, self.congela)

    def _passo(self, testo, frazione):
        if getattr(self, "schermata", None) is not None:
            self.schermata.passo(testo, frazione)

    def _mostra_subito(self):
        if getattr(self, "_alpha_mio", False):
            try:
                self.root.attributes("-alpha", 1.0)
            except Exception:       # noqa: BLE001
                pass
            self._alpha_mio = False

    def mostra_app(self):
        """La prima scheda e' disegnata: la finestra grande compare, la schermata di caricamento si chiude e, la prima volta per l'account, la finestra di
        benvenuto chiede la condivisione e il link di Untapped (Schede/Settings/benvenuto.py). Si chiama una volta sola."""
        if getattr(self, "_mostrata", False):
            return
        self._mostrata = True
        self._passo("Ready", 1.0)
        self._mostra_subito()
        if getattr(self, "schermata", None) is not None:
            self.root.after(120, self.schermata.chiudi)
            self.schermata = None
        try:
            self.root.lift(); self.root.focus_force()
        except Exception:       # noqa: BLE001
            pass
        if not FUORI_SCHERMO:
            try:
                import pagina_settings as PS
                if not PS.benvenuto_fatto():
                    import benvenuto
                    self.root.after(600, lambda: benvenuto.apri(tk, self.root, self.F, su_fatto=lambda: self.pagine["settings"].se_sporca()))
            except Exception as e:      # noqa: BLE001 - il benvenuto non ferma l'app
                print("benvenuto:", e)

    def fine_avvio(self, attesa=None):
        """La finestra e' a schermo: le pagine tornano a disegnarsi, e la scheda davanti si disegna adesso. Se e' la Meta, i suoi dati (collezione, quaderni delle
        carte, il meta del formato: ~0,7 s dal disco) si leggono prima in un filo, e la pagina si disegna quando sono pronti (11 nov 2026, sessione Magic 13: il
        primo disegno teneva ferma la finestra mezzo secondo appena comparsa). Mai piu' di 4 s di attesa: poi si disegna comunque."""
        k = self.scelta["v"]
        pg = self.pagine.get(k)
        if attesa is None and k == "meta" and pg is not None:
            fatto = threading.Event()
            fmt, rango = pg.t_fmt.get() or "Standard", pg.rango()       # da Tk, qui: il filo non tocca Tk

            def leggi():
                try:
                    import dati_meta
                    dati_meta.meta_mazzi(fmt, rango)
                except Exception:       # noqa: BLE001 - e' solo un anticipo: il disegno rifa' il conto e mostra l'errore
                    pass
                finally:
                    fatto.set()
            threading.Thread(target=leggi, daemon=True).start()
            attesa = (fatto, time.time())
        if attesa is not None and not attesa[0].is_set() and time.time() - attesa[1] < 4:
            self.root.after(30, lambda: self.fine_avvio(attesa))
            return
        Pagina.AVVIO = False
        self.root.after(150, self.mostra_app)       # la finestra compare a prima scheda disegnata
        if k != "corso" and pg is not None:
            try:
                pg.fr.event_generate("<<Davanti>>")
                if hasattr(pg, "se_sporca"):
                    pg.se_sporca()
            except Exception as e:      # noqa: BLE001 - una pagina che cade non ferma la finestra
                print("fine_avvio:", e)



    def scheda(self, padre, titolo, destra="", P=None):
        P = P or C        # la chat sulla palette di sempre, l'interfaccia su CI (ArtStation)
        cornice = tk.Frame(padre, bg=P["filo2"], padx=1, pady=1)
        dentro = tk.Frame(cornice, bg=P["scheda"]); dentro.pack(fill="both", expand=True)
        cap = tk.Frame(dentro, bg=P["cap"]); cap.pack(fill="x")
        tit = tk.Label(cap, text=titolo.upper(), bg=P["cap"], fg=P.get("capo", P["arancio"]), font=self.F(8, True)); tit.pack(side="left", padx=10, pady=5)
        v = tk.StringVar(value=destra)
        v.tit = tit
        # il sottotitolo di recap a destra del titolo non si mostra in nessuna sezione (Autore, 4 nov 2026: «togli i
        # sottotitoletti di recap da ogni sezione di tutto il companion»): il testo resta in v, l'etichetta non si disegna
        v.lab = tk.Label(cap, textvariable=v, bg=P["cap"], fg=P["acciaio"], font=self.F(8))
        v.cap = cap
        tk.Frame(dentro, bg=P["filo"], height=1).pack(fill="x")
        corpo_s = tk.Frame(dentro, bg=P["scheda"]); corpo_s.pack(fill="both", expand=True, padx=10, pady=8)
        return cornice, corpo_s, v


    def mostra(self, k):
        if self.scelta["v"] == k:
            if k in ("mazzi", "meta") and self.pagine[k].aperto:      # di nuovo sulla linguetta: si torna a tutti i mazzi
                self.pagine[k].apri(None)
            elif k == "performance" and self.perf.standard.aperto:
                self.perf.standard.apri(None)
            return
        self.scelta["v"] = k
        # le schede stanno una sopra l'altra, tutte montate alla loro misura: si sceglie chi e' davanti, nessuna si smonta (9 nov 2026).
        # Una scheda con dati nuovi si disegna prima di venire davanti, sotto quella di adesso: compare finita, non pezzo per pezzo
        Pagina.DIETRO = {str(self.altre)} if k == "corso" else {str(pg.fr) for c, pg in self.pagine.items() if c not in ("corso", k)} | {str(self.copri)}
        for c, pg in self.pagine.items():       # le schede dietro restano ferme alla loro misura: ingrandire la finestra non le rifa' tutte
            if c not in ("corso", k):
                self.ferma(pg)
        if k == "corso":
            if self.lato_v["v"] is None:       # la prima volta: la chat, poi lato sceglie (a setup finito: lato legge il draft)
                self.sx.grid(); self.dx.grid(row=0, column=1, columnspan=1); self.lato_v["v"] = "chat"
            self.root.after_idle(lambda: self.lato())
            self.copri.lift()
            for w in (self.sx, self.sx_m, self.dx):
                w.lift()
        else:
            pg = self.pagine[k]
            if self.fuori_misura(pg):        # la finestra ha cambiato misura mentre era dietro: si adegua prima di venire davanti
                pg.fr.place_configure(relwidth=1, relheight=1, width=0, height=0)
                self.root.update_idletasks(); self.root.update()
            pg.fr.place_configure(relwidth=1, relheight=1, width=0, height=0)
            pg.fr.event_generate("<<Davanti>>")      # i lavori lasciati a scheda nascosta, prima che si veda
            pg.fr.lift(); self.altre.lift()
        for chiave, (lab, sopra) in self.linguette.items():
            on = chiave == k
            lab.configure(bg=CI["scheda"] if on else CI["fondo"], fg=CI["titolo"] if on else CI["grigio"])
            sopra.configure(bg=CI["accento"] if on else CI["fondo"])


    def ferma(self, pg):
        """Una scheda dietro tiene la misura che ha: con relwidth seguirebbe ogni ridimensionamento della finestra e si ridisegnerebbe senza che nessuno la guardi."""
        if pg.fr.winfo_width() > 1 and pg.fr.place_info().get("relwidth") not in ("0", "0.0", ""):
            pg.fr.place_configure(relwidth=0, relheight=0, width=pg.fr.winfo_width(), height=pg.fr.winfo_height())

    def fuori_misura(self, pg):
        """Vero se la scheda e' ferma a una misura diversa da quella della finestra di adesso."""
        a, b = self.altre.winfo_width(), self.altre.winfo_height()
        return a > 1 and (pg.fr.winfo_width(), pg.fr.winfo_height()) != (a, b)

    def prepara_dietro(self):
        """Le schede dietro con dati nuovi si disegnano da sole, una alla volta, quando mouse e tastiera sono fermi da 2 s: al clic sono gia' pronte.
        Mai durante una partita limited: un disegno ferma la finestra fino a un secondo e la chat dei consigli non aspetta. Con Arena aperta si' (la si usa
        accanto ad Arena, e il Player.log cambia di continuo)."""
        try:
            # le schede dietro restano ferme alla loro misura (ferma): all'avvio non lo erano mai, perche' la prima scheda si mostra prima che le pagine abbiano una
            # larghezza, e fino al primo cambio di scheda ogni ridimensionamento le rifaceva tutte (11 nov 2026: trascinando il bordo della Meta 1,2 s fermi)
            for k, pg in self.pagine.items():
                if k not in ("corso", self.scelta["v"]):
                    self.ferma(pg)
            if time.time() - self.ultimo_input >= 2.0 and not self.pescate.in_partita:
                ora = time.time()
                riposo = self.__dict__.setdefault("riposo_dietro", {})       # una scheda rimasta segnata dopo un tentativo (senza dati, per esempio) riposa un minuto
                for k, pg in self.pagine.items():
                    if k in ("corso", self.scelta["v"]) or not hasattr(pg, "se_sporca") or ora < riposo.get(k, 0):
                        continue
                    sporca = lambda: (getattr(getattr(pg, "pagine", {}).get(getattr(pg, "modo", None)) if hasattr(pg, "pagine") else pg, "sporca", False)
                                      or getattr(pg, "sporco", False) or getattr(pg, "da_cercare", False))      # Meta, Your decks e Collection tengono i loro segni
                    misura = self.fuori_misura(pg)
                    if not (sporca() or misura):
                        continue
                    p = str(pg.fr)
                    Pagina.DIETRO.discard(p)        # per i suoi conti e' davanti: i lavori che aspettano la vista si fanno
                    try:
                        if misura:      # la finestra ha cambiato misura: la scheda dietro si adegua adesso, non al clic
                            self.ferma(pg)
                            pg.fr.place_configure(width=self.altre.winfo_width(), height=self.altre.winfo_height())
                            self.root.update_idletasks(); self.root.update()
                        pg.fr.event_generate("<<Davanti>>")
                    finally:
                        if self.scelta["v"] != k:
                            Pagina.DIETRO.add(p)
                    if sporca() or self.fuori_misura(pg):
                        riposo[k] = ora + 60
                    break       # una per giro: la finestra resta libera fra l'una e l'altra
        except Exception as e:
            print("prepara_dietro:", e)
        self.root.after(1000, self.prepara_dietro)


    def mana_label(self, padre, colori, bg, imm=None):
        imm = imm or self.mana
        f = tk.Frame(padre, bg=bg)
        for k in colori:
            if k in imm:
                tk.Label(f, image=imm[k], bg=bg).pack(side="left", padx=(0, 2))
            else:
                tk.Label(f, text=k, bg=bg, fg=CI["testo"], font=self.F(8)).pack(side="left")
        return f


    def parti_performance(self):
        """Performance parte da Limited con un draft aperto, se no dal formato dell'ultima partita: serve che draft e partite siano arrivati tutti e due."""
        if "ora_dati" in self.stato and "costruite" in self.stato:
            self.perf.parti(self.stato["draft"], self.stato["costruite"].get("partite"), self.draft_attivo())


    def assetto(self):
        """Nei pick e nella costruzione la colonna destra e' tutta dei mazzi; in partita tornano sopra il draft e i dati della partita."""
        self.s1.pack_forget()
        if self.fase["v"] is None:
            self.s1.pack(fill="x", pady=(0, 8), before=self.s_cal if self.s_cal.winfo_manager() else self.s6)
        # le tre colonne di capsule vogliono spazio: nei pick e nella costruzione la chat ne prende un quarto, a finestra piccola i nomi si leggerebbero a meta'
        self.pesi_colonne()


    def pesi_colonne(self):
        tre = self.fase["v"] is not None
        a, b = (1, 3) if tre else (2, 3) if self.lato_v["v"] == "mazzo" else (11, 10)        # il mazzo a sinistra: una lista, non serve meta' finestra
        self.corpo.columnconfigure(0, weight=a, uniform="c"); self.corpo.columnconfigure(1, weight=b, uniform="c")


    def lato(self):
        """A sinistra nel Drafter: la chat nei pick e in partita, niente alla costruzione (i tre mazzi prendono tutta la larghezza), il mazzo inviato il resto del tempo."""
        if self.scelta["v"] != "corso":
            return
        modo = "niente" if self.fase["v"] == "costruzione" else "mazzo" if self.mazzo_a_sinistra() else "chat"
        if modo == self.lato_v["v"]:
            return
        self.lato_v["v"] = modo
        self.sx.grid_remove(); self.sx_m.grid_remove()
        if modo == "niente":
            self.dx.grid(row=0, column=0, columnspan=2)
        else:
            (self.sx if modo == "chat" else self.sx_m).grid(row=0, column=0, sticky="nsew", padx=(0, 12)); self.dx.grid(row=0, column=1, columnspan=1)
        self.pesi_colonne()


    def area_scorrevole(self, scorri, padre=None):
        """Un riquadro che scorre con la rotella e tiene la posizione a ogni ridisegno. -> (canvas, cornice interna, lega)."""
        cv_l = tk.Canvas(padre or self.b6, bg=CI["scheda"], highlightthickness=0, bd=0); cv_l.pack(fill="both", expand=True)
        dentro = tk.Frame(cv_l, bg=CI["scheda"])
        win_l = cv_l.create_window(0, 0, window=dentro, anchor="nw")

        def misura(e=None):
            cv_l.configure(scrollregion=(0, 0, 0, dentro.winfo_reqheight()))
            cv_l.itemconfigure(win_l, width=cv_l.winfo_width())
            cv_l.yview_moveto(scorri["y"])
        dentro.bind("<Configure>", misura); cv_l.bind("<Configure>", misura)

        def rotella(e):
            if dentro.winfo_reqheight() > cv_l.winfo_height():
                cv_l.yview_scroll(piattaforma.scatti(e.delta) * 2, "units"); scorri["y"] = cv_l.yview()[0]

        def lega(w):
            w.bind("<MouseWheel>", rotella)
            for x in w.winfo_children():
                lega(x)
        return cv_l, dentro, lega


    def num_it(self, x, d=2):
        return "-" if x is None else f"{x:.{d}f}"


    def scalda(self):
        """Quel che la prima finestra di un mazzo legge dal disco, letto in sottofondo dopo l'avvio (11 nov 2026, sessione Magic 13: la prima apertura bloccava
        ~0,6 s, 0,25 di file: le 600 schede di Partite/, i prezzi e i formati di Scryfall, il pool dello Standard, numpy). Ogni cache si riempie una volta sola."""
        import dati_mazzo
        import mazzi_salvati
        import prezzi_carte
        time.sleep(3)
        import numpy_leggero
        for f in (dati_mazzo.schede, prezzi_carte.tutti, lambda: prezzi_carte.carta("Island"), mazzi_salvati.pool_standard,
                  numpy_leggero.carica):      # numpy: le sfumature delle capsule (112 ms la prima volta), senza i 600 MB di OpenBLAS
            try:
                f()
            except Exception as e:      # noqa: BLE001 - scaldare non e' necessario: la finestra li legge da se'
                print("scalda:", f"{type(e).__name__}: {e}")

    def lavoro_dati(self):
        CAP._carte()        # i quaderni di tutti i set: qui, non al primo disegno
        threading.Thread(target=self.scalda, daemon=True).start()
        while True:
            if "--log-limited" in sys.argv:      # collaudo: un log dato
                self.coda.put(("limited", limited_dal_log(tuple(sys.argv[sys.argv.index("--log-limited") + 1].split(",")))))      # «adesso,prima»
            elif "--diario" not in sys.argv:     # le prove leggono il loro diario, non il limited vero
                self.coda.put(("limited", limited_dal_log()))
            try:
                self.coda.put(("risorse", RS.carica()))     # solo dai log di Arena: non aspetta Untapped
            except Exception as e:
                print("risorse:", f"{type(e).__name__}: {e}")
            try:
                d = CC.carica()
                prepara_capsule(d)
                self.coda.put(("collezione", d))
            except Exception as e:
                print("collezione:", f"{type(e).__name__}: {e}")
            untapped_ok = True
            try:
                self.coda.put(("draft", draft_da_untapped(forza=self.dati_forza.is_set(), forza_set=[self.stato["set"]])))
                self.dati_forza.clear()
            except Exception as e:
                self.coda.put(("errore", f"{type(e).__name__}: {e}"))
                untapped_ok = False
            # le schede anche senza Untapped: le partite costruite vengono anche dal Player.log (9 nov 2026)
            try:
                sch = {f: coppie(self.stato["set"], f) for f in ("quick", "premier")}
                sch["costruite"] = costruite()
                try:
                    sch["premi"] = PE.raccogli()     # gemme, buste, rare e mitiche vinte, dai log di Arena
                    if sch["premi"]:        # il farming si conta qui, nel filo dei dati: Performance lo ritrova pronto (dati_app.farming si ricorda; 11 nov 2026)
                        import dati_app
                        dati_app.farming(sch["premi"])
                except Exception as e:
                    print("premi:", f"{type(e).__name__}: {e}"); sch["premi"] = None
                sch["campo"] = campo(self.stato["set"])
                self.coda.put(("schede", sch))
            except Exception as e:
                print("schede:", f"{type(e).__name__}: {e}")
            if not PUBBLICA:        # le partite di Autore nella raccolta dai log, col suo consenso in Settings come tutti (11 nov 2026; l'app pubblica lo fa
                try:                # in avvio_pubblico.condividi_in_fondo): finche' il server dei dati non ha un indirizzo restano in coda sul PC
                    import condividi
                    if condividi.qualcuno():
                        condividi.accoda()
                        condividi.invia(condividi.endpoint())
                except Exception as e:      # noqa: BLE001 - la condivisione non ferma mai la finestra
                    print("condivisione:", f"{type(e).__name__}: {e}")
            if not untapped_ok:
                for _ in range(60):          # Untapped non ha risposto: si tengono i suoi dati di prima e si riprova fra un minuto
                    time.sleep(1)
                continue
            for _ in range(600):
                if self.dati_ora.is_set():
                    break
                time.sleep(1)
            self.dati_ora.clear()


    def lavoro_risorse(self):
        """Il saldo (oro, gemme, jolly, token) piu' spesso dei dati di Untapped (Autore, 8 nov 2026: «vedo che mi segna del gold che non ho, controlla che rilegga
        il log almeno ogni 5 minuti»): ogni 30 s si guarda il Player.log e, se e' cambiato, si rilegge subito; comunque ogni 5 minuti. Una lettura costa 0,1-0,2 s.
        Il saldo e' l'ultima foto del conto che Arena ha scritto (InventoryInfo): se una sessione di Arena non e' finita nei log archiviati, si aggiorna al
        prossimo accesso ad Arena, che la riscrive."""
        prima, ultima, finite_prima = None, 0.0, None
        import collezione_viva as CV
        firma_coll, scaricata = None, 0.0

        def collezione():
            """La collezione la aggiorna l'app (Autore, 8 nov 2026: «si e' fondamentale che l'aggiornamento della collection sia svolto dall'app / direttamente»):
            le carte dei log al massimo ogni 5 minuti, lo scarico di Untapped ogni 20; se cambia, Collection e mazzi si ridisegnano."""
            nonlocal firma_coll, scaricata
            if time.time() - scaricata >= 1200:
                scaricata = time.time()
                CV.aggiorna_scarico()
            st_ = CV.stato()
            f_ = (st_["quando"], st_["soglia"], len(st_["piu"])) if st_ else None
            if f_ != firma_coll:
                if firma_coll is not None:
                    d = CC.carica()
                    prepara_capsule(d)
                    self.coda.put(("collezione", d))
                firma_coll = f_
        import account
        while True:
            try:
                collezione()
            except Exception as e:
                print("collezione:", f"{type(e).__name__}: {e}")
            forzata = self.risorse_ora.wait(30)
            self.risorse_ora.clear()
            try:        # un accesso ad Arena con un altro account: l'app passa a lui da sola (10 nov 2026, Magic 12); il cambio lo fa il giro, nel filo di Tk
                if account.aggiorna():
                    self.coda.put(("conto", None))
            except Exception as e:
                print("account:", f"{type(e).__name__}: {e}")
            if forzata:
                ultima, scaricata = 0.0, 0.0; firma_coll = ("forza",)
            try:
                st = os.stat(LOG_ARENA[0]); firma = (st.st_size, st.st_mtime)
            except OSError:
                firma = None
            if firma != prima or time.time() - ultima >= 300:
                prima, ultima = firma, time.time()
                try:
                    self.coda.put(("risorse", RS.carica()))
                except Exception as e:
                    print("risorse:", f"{type(e).__name__}: {e}")
                # una partita finita nel Player.log: le partite e i mazzi si rileggono subito, anche col companion spento (9 nov 2026, Autore:
                # «ma le devi salvare tu no untapped»; fino a quel giorno si aspettava la riga FINE PARTITA del companion o i 10 minuti)
                try:
                    with open(LOG_ARENA[0], "rb") as fh:
                        finite = fh.read().count(b"MatchGameRoomStateType_MatchCompleted")
                except OSError:
                    finite = None
                if finite is not None and finite != finite_prima and finite_prima is not None:
                    self.dati_ora.set()
                finite_prima = finite


    def giro(self):
        """Il giro della finestra: un errore di una pagina si stampa e basta, la chat deve continuare anche in partita."""
        try:
            self.giro_corpo()
        except Exception as e:
            print("giro:", f"{type(e).__name__}: {e}")
        self.root.after(400, self.giro)


    def giro_corpo(self):
        cambiato = False; cambiato_dx = False
        for r in self.diario.nuove():
            t = senza_ora(r)
            # nella chat e nel pannello della partita solo i limited (Autore, 8 nov 2026: «il drafter chat legge OGNI PARTITA CHE GIOCO, questa cosa non
            # dovrebbe accadere, dovrebbe leggere solo la chat dei limited»): una partita di un evento costruito (DualColorPrecons, Ranked, Play...) si salta fino alla sua fine
            ev_ = evento_partita(t)
            if ev_ is not None:
                self.fuori_limited["v"] = not e_limited(ev_)
            if self.fuori_limited["v"]:
                if t.startswith("=== FINE PARTITA") or t.startswith("COMPANION ATTIVO"):
                    self.fuori_limited["v"] = False
                    if t.startswith("=== FINE PARTITA"):
                        self.dati_forza.set(); self.dati_ora.set()       # Performance e i numeri si rileggono lo stesso
                        continue
                else:
                    continue
            m = re.search(r"COMPANION: (\S+) ora (\d+)-(\d+) \((vittoria|sconfitta)\)", t)
            if m:
                w, l = int(m.group(2)), int(m.group(3))
                if len(self.rec["seq"]) == w + l - 1:
                    self.rec["seq"].append("v" if m.group(4) == "vittoria" else "p")
                self.rec.update(w=w, l=l); self.disegna_record()
                s = m.group(1).split("_"); self.stato["set"] = s[1] if len(s) > 1 else self.stato["set"]
                self.dati_ora.set()
            if t.startswith("LIMITED:"):
                self.play["stato"] = "pronto" if "companion ready" in t else "errore"
            if "=== FINE DRAFT" in t or "=== FINE PARTITA" in t:
                self.dati_forza.set(); self.dati_ora.set()
            if "=== FINE DRAFT" in t:
                self.stato["draft_finito"] = True; self.disegna_mazzi()       # draft chiuso: la scheda dei mazzi si svuota
                if self.stato.get("log_limited"):
                    self.stato["log_limited"] = dict(self.stato["log_limited"], aperto=False)
            if t.startswith("COMPANION ATTIVO"):       # a companion riacceso una riga «=== DRAFT» non vuol dire pick: li dice la riga PICK
                self.fase["ripartito"] = "| draft aperto" in t      # attenzione: «nessun draft aperto» contiene le stesse parole
                if "nessun draft" in t:
                    self.cambia_fase(None)
            m = re.match(r"PICK (\d+-\d+): PRENDI -> ", t)
            if m:
                coppie = ",".join(f"{c}:{x}" for c, x in re.findall(r"\b([WUBRG]{2}) (\d+)%", t))     # gli ultimi pick non hanno coppie: restano quelle di prima
                self.fase["pick"] = (m.group(1), coppie or (self.fase["pick"][1] if self.fase["pick"] else ""))
                self.cambia_fase("pick")
            if t.startswith("=== COSTRUZIONE:"):
                self.fase["scelto"] = None; self.cambia_fase("costruzione")
                if "--clic-select" in sys.argv:       # collaudo: come premere Select deck
                    self.root.after(2500, lambda: self.seleziona_mazzo(int(sys.argv[sys.argv.index("--clic-select") + 1])))
            if t.startswith(("=== CANCELLO", "=== PARTITA:", "=== FINE DRAFT")):
                self.cambia_fase(None)
            m = re.match(r"=== DRAFT: (\S+)", t)
            if m:
                self.fase["evento"] = m.group(1); self.fase["lanciato"] = None
                if not self.fase["ripartito"]:
                    self.cambia_fase("pick"); self.fase["scelto"] = None
                self.fase["ripartito"] = False
                self.rec.update(w=0, l=0, seq=[]); self.disegna_record()
                if self.scelta["avviato"]: self.mostra("corso")
                # un draft nuovo: i mazzi di prima non valgono piu' finche' rating_mazzi e il cancello non scrivono i nuovi
                self.stato["draft_finito"] = False
                self.inviato["da"] = ora_riga(r); self.leggi_inviato(forza=True); self.leggi_proposti(forza=True)
            nomi = {n for _, _, n in self.mazzo_inviato(self.inviato["d"])}
            if t.startswith(("STATO", "MAGIA sua:", "suo campo:")):
                self.P.vedi_sue(t); cambiato_dx = True
            if self.pescate.riga(t, nomi):
                cambiato_dx = True
            if self.P.riga(t):
                cambiato = True
        self.leggi_inviato(); self.leggi_proposti(); self.leggi_in_corsa(); self.guarda_motore()
        self.aggiorna_play(); self.leggi_calendario()
        if self.fase["v"] == "pick" and self.scelta["avviato"]:
            self.calcola_pick()
        if self.fase["sporco"] and self.scelta["v"] == "corso":
            self.disegna_mazzi()
        if cambiato_dx:
            self.disegna_mazzi(); self.disegna_partita()
        if cambiato or getattr(self.P, "suo_cambiato", False):
            self.P.suo_cambiato = False
            self.disegna_chat(); self.disegna_forza(); self.disegna_lui()
        try:
            while True:
                k, v = self.coda.get_nowait()
                self.riposo_dietro = {}       # dati nuovi: le schede dietro si preparano subito, anche quelle provate a vuoto
                try:          # una pagina che cade non ferma le altre ne' la chat
                    if k == "draft":
                        self.stato["draft"] = v; self.stato["ora_dati"] = f"{datetime.datetime.now():%H:%M}"
                        self.disegna_dati(); self.disegna_forza()
                        self.perf.limited.aggiorna(draft=v, set=self.stato["set"], colori=self.stato["draft_colori"])
                        self.pagine["risorse"].aggiorna_draft(v)
                        self.parti_performance()
                    elif k == "schede":
                        self.perf.limited.aggiorna(coppie={f: v[f] for f in ("quick", "premier")}, premi=v.get("premi"), campo=v["campo"])
                        self.perf.standard.premi = v.get("premi")
                        self.perf.standard.aggiorna(v["costruite"])
                        self.pagine["mazzi"].premi = v.get("premi")
                        self.pagine["mazzi"].aggiorna(v["costruite"])
                        self.pagine["risorse"].aggiorna_costruite(v["costruite"])
                        self.stato["costruite"] = v["costruite"] or {}
                        self.parti_performance()
                    elif k == "fix":
                        if v[0] == self.fix["per"]:
                            self.fix["d"] = v[1]; self.disegna_mazzi()
                    elif k == "limited":
                        self.stato["log_limited"] = v
                        if v and v["aperto"] and not self.finito_su_untapped(v):
                            self.stato["draft_finito"] = False
                            if v["w"] is not None and (v["w"], v["l"]) != (self.rec["w"], self.rec["l"]):      # il record dell'evento lasciato a meta': lo dice Arena, anche se e' piu' basso di quello a video
                                self.rec.update(w=v["w"], l=v["l"], seq=[]); self.disegna_record()
                        self.disegna_mazzi()
                    elif k == "risorse":
                        self.pagine["risorse"].aggiorna(v)
                    elif k == "collezione":
                        self.pagine["collezione"].aggiorna(v)
                    elif k == "conto":
                        self.cambia_conto()
                    elif k == "errore":
                        print("Untapped:", v)
                except Exception as e:
                    print(f"pagina {k}: {type(e).__name__}: {e}")
        except queue.Empty:
            pass
        if hasattr(self.pagine.get(self.scelta["v"]), "se_sporca"):     # la scheda a vista con dati nuovi: la finestra era a icona, o sono arrivati mentre si apriva
            self.pagine[self.scelta["v"]].se_sporca()
        self.scelta["avviato"] = True     # dal secondo giro in poi le righe sono nuove: un draft o una partita riportano su «In corso»


def avvia():
    tk_sicuro.applica()        # prima di ogni finestra: un widget distrutto cancella i suoi after
    Finestra().root.mainloop()


def monitor(root=None):
    """-> [(sinistra, alto, destra, basso, primario)] degli schermi di Windows. Fuori da Windows (Mac) lo schermo principale che Tk conosce, se c'e' una
    finestra a cui chiederlo; se no nessuno, e la finestra si apre in alto a sinistra (posizione_iniziale)."""
    if sys.platform != "win32":
        try:
            return [(0, 0, root.winfo_screenwidth(), root.winfo_screenheight(), True)] if root is not None else []
        except Exception:       # noqa: BLE001 - senza schermi si apre comunque
            return []
    import ctypes, ctypes.wintypes as W
    u, out = ctypes.windll.user32, []

    class MI(ctypes.Structure):
        _fields_ = [("s", W.DWORD), ("m", W.RECT), ("w", W.RECT), ("f", W.DWORD)]

    def cb(h, _d, _r, _l):
        mi = MI(); mi.s = ctypes.sizeof(MI)
        if u.GetMonitorInfoW(h, ctypes.byref(mi)):
            out.append((mi.m.left, mi.m.top, mi.m.right, mi.m.bottom, bool(mi.f & 1)))
        return 1
    u.EnumDisplayMonitors(0, 0, ctypes.WINFUNCTYPE(ctypes.c_int, W.HMONITOR, W.HDC, ctypes.POINTER(W.RECT), W.LPARAM)(cb), 0)
    return out


def posizione_iniziale(schermi, pos=None):
    """-> (geometria, ingrandita). Lo schermo dove l'hai lasciata se c'e' ancora, se no il secondo schermo; con uno schermo solo quello. Ingrandita sempre
    (Autore, 12 nov 2026: «l'app ridotta accavalla male le varie parti dell'interfaccia, facciamo che l'app parte sempre a tutto schermo»; fino a quel giorno
    si riapriva ridotta se l'avevi chiusa ridotta). La geometria resta: e' la misura a cui torna se la riduci."""
    m = re.match(r"\d+x\d+\+(-?\d+)\+(-?\d+)$", (pos or {}).get("geo") or "")
    if m and any(a <= int(m.group(1)) < c and b <= int(m.group(2)) < d for a, b, c, d, _ in schermi):
        return pos["geo"], True
    z = next((x for x in schermi if not x[4]), schermi[0] if schermi else (0, 0, 0, 0, True))
    return f"900x960+{z[0] + 20}+{z[1] + 20}", True


if __name__ == "__main__":
    avvia()
