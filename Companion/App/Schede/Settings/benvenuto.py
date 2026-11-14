"""La finestra di benvenuto, dopo la schermata di caricamento (13 nov 2026, Autore: «come si apre steam, al primo avvio una finestra di caricamento, poi parte
l'app e una finestra chiede il turn on dell'upload dati log e il link alla collezione di untapped gg», poi «ok ma con un design migliore e le come due step
fondamentali per procedere»).

Una procedura in due passi, coi pallini in testa (1 Data sharing — 2 Your collection):
1. la condivisione: due riquadri da scegliere, «Share my games» o «Keep them private»; Continue si accende solo dopo una scelta (il consenso deve essere
   libero: tutte e due le scelte vanno avanti, e l'app funziona lo stesso);
2. la collezione: il link del profilo pubblico di Untapped, Link; Finish quando e' collegato, «Skip for now» se no.
Le scelte passano dalle stesse funzioni della scheda Settings (condividi.imposta_consenso, account.collega_untapped via pagina_settings.Collezione).
Finish o Skip segnano il benvenuto fatto per l'account (pagina_settings.segna_benvenuto); chiusa con la X a meta' si richiede al prossimo avvio. Sta sopra la
finestra grande (transient, grab: si fa prima di usare l'app), non sopra Arena.
"""
import os, sys
_casa = os.path.dirname(os.path.abspath(__file__))
while not os.path.isfile(os.path.join(_casa, "percorsi.py")):
    _casa = os.path.dirname(_casa)
if _casa not in sys.path:
    sys.path.insert(0, _casa)
import percorsi  # noqa: E402,F401
import webbrowser  # noqa: E402

import disegni as DG  # noqa: E402
import pagina_settings as PS  # noqa: E402
from ambiente import ASSET, PRODOTTO  # noqa: E402
from tema import CI as C, FN  # noqa: E402

LARGA, ALTA = 700, 560
PASSI = ("Arena", "Data sharing", "Collection", "Ready")
AZZURRO = ("#0f86cc", "#2ba3ea", "#ffffff")       # normale, sotto il mouse, scritta
GRIGIO = ("#303034", "#3c3c42", "#e6e6ea")
SPENTO = ("#222227", "#222227", "#5c5c64")        # Continue prima di una scelta: non si preme


class Bottone:
    """Un pulsante arrotondato in antialias (la tela di Tk non arrotonda): metti(testo, colori); spento non risponde."""

    def __init__(self, tk, F, padre, larga, alta, bg, azione):
        self.F, self.larga, self.alta, self.azione = F, larga, alta, azione
        self.c = tk.Canvas(padre, width=larga, height=alta, bg=bg, highlightthickness=0, bd=0)
        self.testo, self.colori, self.sopra = "", AZZURRO, False
        self.c.bind("<Button-1>", lambda e: self.azione() if self.colori is not SPENTO else None)
        self.c.bind("<Enter>", lambda e: self._sopra(True))
        self.c.bind("<Leave>", lambda e: self._sopra(False))

    def _sopra(self, v):
        self.sopra = v
        self.disegna()

    def metti(self, testo, colori):
        self.testo, self.colori = testo, colori
        self.disegna()

    def disegna(self):
        """Stile S3 dei pulsanti (14 nov 2026, widget.disegna_s3): satinato, filo chiaro in cima, il blocco icona dove il testo ne ha una (Link)."""
        from widget import disegna_s3, _mischia
        c = self.c
        c.delete("all"); c._s3 = []
        nor, su, scritta = self.colori
        spento = self.colori is SPENTO
        disegna_s3(c, 0, 0, self.larga, self.alta, self.testo, self.F(10, True), (nor, su, _mischia(nor, "#000000", 0.25)), self.sopra and not spento,
                   icona=False if spento else None, scritta=scritta)
        c.configure(cursor="arrow" if spento else "hand2")

    def place(self, **k):
        self.c.place(**k)

    def place_forget(self):
        self.c.place_forget()

    def winfo_manager(self):
        return self.c.winfo_manager()


def _riquadro(l, h, bordo, fondo, larghezza=1.2, raggio=10):
    def fa():
        d = DG.Disegno(l, h)
        d.rett(0.6, 0.6, l - 0.6, h - 0.6, riempi=fondo, bordo=bordo, larghezza=larghezza, raggio=raggio)
        return d
    return DG._icona(("riquadro_benv", l, h, bordo, fondo, larghezza, raggio), fa)


def _icona_scelta(lato, tipo, colore):
    """Il segno dei due riquadri: una freccia che sale in un cerchio (condividi), un lucchetto (privato)."""
    if tipo == "privato":
        return DG.lucchetto(lato, True, colore)

    def fa():
        d = DG.Disegno(lato, lato)
        r = lato / 2
        d.cerchio(r, r, r - 1.2, bordo=colore, larghezza=1.8)
        d.linea([(r, lato * 0.72), (r, lato * 0.3)], colore, larghezza=2.2)
        d.linea([(lato * 0.33, lato * 0.46), (r, lato * 0.28), (lato * 0.67, lato * 0.46)], colore, larghezza=2.2)
        return d
    return DG._icona(("su_benv", lato, colore), fa)


def _pallino(lato, n, stato):
    """Il pallino del passo: «fatto» verde con la spunta, «qui» azzurro pieno, «dopo» col solo bordo."""
    def fa():
        d = DG.Disegno(lato, lato)
        r = lato / 2
        if stato == "fatto":
            d.cerchio(r, r, r - 0.6, riempi=C["verde"])
            k = lato / 13
            d.linea([(3.6 * k, 6.7 * k), (5.7 * k, 8.9 * k), (9.6 * k, 4.3 * k)], "#ffffff", larghezza=max(1.8, 1.6 * k))
        elif stato == "qui":
            d.cerchio(r, r, r - 0.6, riempi=C["accento"])
        else:
            d.cerchio(r, r, r - 1, riempi=C["fondo"], bordo=C["filo"], larghezza=1.6)
        return d
    return DG._icona(("pallino_benv", lato, stato), fa)


class Benvenuto:
    def __init__(self, tk, root, F, su_fatto=None, x=None, y=None, grab=True):
        import condividi
        import account
        self.tk, self.root, self.F, self.su_fatto = tk, root, F, su_fatto
        self.passo = 1
        self.log = PS.log_dettagliato()
        c0 = condividi.consenso()
        self.scelta = c0 if c0 in (True, False) else None        # la scelta di prima, se c'e' (l'app di Autore: gia' accesa)
        self.collegato = bool(account.account().get("untapped_player"))
        f = self.f = tk.Toplevel(root)
        f.withdraw()
        f.title(f"Welcome to {PRODOTTO}")
        f.configure(bg=C["fondo"])
        f.resizable(False, False)
        try:
            f.transient(root)
            from tema import barra_scura
            barra_scura(f, C["testa"], C["titolo"], C["filo"])
        except Exception:       # noqa: BLE001
            pass
        self.c = tk.Canvas(f, width=LARGA, height=ALTA, bg=C["fondo"], highlightthickness=0, bd=0)
        self.c.pack()
        self.c.bind("<Button-1>", self.clic)
        self.c.bind("<Motion>", self.muovi)
        self.sopra = None
        self.logo = None
        try:
            from PIL import Image, ImageTk
            self.logo = ImageTk.PhotoImage(Image.open(os.path.join(ASSET, "companion_icona.png")).convert("RGBA").resize((40, 40), Image.LANCZOS), master=f)
        except Exception:       # noqa: BLE001
            pass
        # i pezzi di Tk sopra la tela: il campo del link e i pulsanti
        self.v_link = tk.StringVar()
        self.e = tk.Entry(f, textvariable=self.v_link, bg=C["scheda"], fg=C["titolo"], insertbackground=C["titolo"], relief="flat", font=F(10),
                          highlightthickness=1, highlightbackground=C["filo"], highlightcolor=C["accento"])
        self.e.bind("<Return>", lambda e: self.collega())
        self.b_link = Bottone(tk, F, f, 110, 36, C["scheda"], self.collega)
        self.b_avanti = Bottone(tk, F, f, 160, 40, C["fondo"], self.avanti)
        self.b_indietro = Bottone(tk, F, f, 110, 40, C["fondo"], self.indietro)
        self.b_controlla = Bottone(tk, F, f, 150, 36, C["fondo"], self.ricontrolla)
        self.b_link.metti("Link", AZZURRO)
        self.b_indietro.metti("Back", GRIGIO)
        self.b_controlla.metti("Check again", GRIGIO)
        f.after(3000, self.guarda_log)
        self.msg_link, self.msg_col = "", C["grigio"]
        f.protocol("WM_DELETE_WINDOW", self.chiudi_senza)
        f.bind("<Escape>", lambda e: self.chiudi_senza())
        if x is None:
            try:
                x = root.winfo_rootx() + (root.winfo_width() - LARGA) // 2
                y = root.winfo_rooty() + max(40, (root.winfo_height() - ALTA) // 3)
            except Exception:       # noqa: BLE001
                x, y = 200, 120
        f.geometry(f"{LARGA}x{ALTA}+{x}+{y}")
        self.disegna()
        f.deiconify(); f.lift()
        try:
            f.focus_force()
            if grab:
                f.grab_set()
        except Exception:       # noqa: BLE001
            pass

    # ------------------------------------------------ il disegno
    def disegna(self):
        c, F = self.c, self.F
        c.delete("all")
        self.box = []
        if self.logo:
            c.create_image(32, 34, image=self.logo, anchor="w")
        c.create_text(84, 26, text=f"Welcome to {PRODOTTO}", anchor="w", fill=C["titolo"], font=FN(17))
        c.create_text(84, 50, text="Four steps and you're in: what to do in Arena, what the app shares, your collection, how to use it.", anchor="w",
                      fill=C["grigio"], font=F(9))
        # i passi: i pallini e le linee fra loro
        yp = 98
        xs = [100 + i * 166 for i in range(len(PASSI))]
        for i in range(len(PASSI) - 1):
            c.create_line(xs[i] + 15, yp, xs[i + 1] - 15, yp, fill=C["verde"] if self.passo > i + 1 else C["filo"], width=2)
        for n, (nome, x) in enumerate(zip(PASSI, xs), 1):
            st = "fatto" if n < self.passo else "qui" if n == self.passo else "dopo"
            c.create_image(x, yp, image=_pallino(26, n, st))
            if st != "fatto":
                c.create_text(x, yp, text=str(n), fill="#ffffff" if st == "qui" else C["grigio"], font=F(9, True))
            c.create_text(x, yp + 26, text=nome, fill=C["titolo"] if st == "qui" else C["grigio"], font=F(9, st == "qui"))
        c.create_line(28, 146, LARGA - 28, 146, fill=C["filo"])
        for w in (self.e, self.b_link, self.b_controlla):
            w.place_forget()
        (self.disegna_arena, self.disegna_condivisione, self.disegna_collezione, self.disegna_pronto)[self.passo - 1]()
        self.disegna_piede()

    def disegna_arena(self):
        c, F = self.c, self.F
        c.create_text(32, 176, text="Arena: turn on Detailed Logs", anchor="w", fill=C["titolo"], font=FN(22))
        c.create_text(32, 206, text="Without it, Arena's log has no games, decks or hands: the app would see almost nothing.",
                      anchor="w", fill=C["testo"], font=F(10))
        c.create_image(32, 226, image=_riquadro(LARGA - 64, 140, C["filo"], C["scheda"], 1.2), anchor="nw")
        for i, (t1, t2) in enumerate((("In MTG Arena open ", "Options (the gear at the top right)"), ("Go to ", "Account"),
                                      ("Tick ", "Detailed Logs (Plugin Support)"), ("Restart Arena once, ", "so the new log starts with the details"))):
            y = 250 + i * 30
            c.create_image(54, y, image=_pallino(20, i, "qui"))
            c.create_text(54, y, text=str(i + 1), fill="#ffffff", font=F(8, True))
            i1 = c.create_text(76, y, text=t1, anchor="w", fill=C["testo"], font=F(10))
            c.create_text(c.bbox(i1)[2], y, text=t2, anchor="w", fill=C["titolo"], font=F(10, True))
        stato = {"on": ("✓  Detailed Logs is ON in your Arena log. All set.", C["verde_t"], C["verde"]),
                 "off": ("✗  Detailed Logs is OFF in your last Arena log: do the steps above, restart Arena, then Check again.", C["arancio"], C["arancio"]),
                 "nessun_log": ("No Arena log on this PC yet: start Arena once, then Check again.", C["grigio"], C["filo"]),
                 "sconosciuto": ("Arena's log does not say yet: start Arena (or restart it), then Check again.", C["grigio"], C["filo"])}[self.log]
        c.create_image(32, 382, image=_riquadro(LARGA - 64 - 162, 48, stato[2], C["fondo"], 1.4), anchor="nw")
        c.create_text(48, 406, text=stato[0], anchor="w", fill=stato[1], font=F(9, True), width=LARGA - 64 - 162 - 30, tags="stato_log")
        self.b_controlla.place(x=LARGA - 32 - 150, y=388)
        c.create_text(32, 450, text="Allowed like every Arena tracker: the app never reads Arena's memory, never changes its files, never clicks in the game.",
                      anchor="w", fill=C["grigio"], font=F(8))

    def disegna_pronto(self):
        c, F = self.c, self.F
        c.create_text(32, 176, text="You're ready", anchor="w", fill=C["titolo"], font=FN(22))
        c.create_text(32, 206, text="How to get the most out of the app:", anchor="w", fill=C["testo"], font=F(10))
        righe = (("Keep the app open while you play.", "Arena overwrites its log at every start: the app saves each finished game within 30 s."),
                 ("Everything fills in by itself.", "Meta, Your decks, Performance, Resources and Collection read your games, no import needed."),
                 ("Limited: open the Drafter tab.", "It follows your picks, your deck and your games on its own."),
                 ("Close the app in sanctioned competitive events", "(Arena Championship and its qualifiers): outside help is not allowed there."),
                 ("Settings and Help are always there.", "Settings changes these choices, Help explains every tab; bottom right, the version button."))
        for i, (t1, t2) in enumerate(righe):
            y = 240 + i * 46
            c.create_image(40, y + 8, image=DG.punto(8, C["accento"]))
            c.create_text(56, y, text=t1, anchor="w", fill=C["titolo"], font=F(10, True))
            c.create_text(56, y + 19, text=t2, anchor="w", fill=C["grigio"], font=F(9))

    def disegna_condivisione(self):
        c, F = self.c, self.F
        c.create_text(32, 176, text="Data sharing", anchor="w", fill=C["titolo"], font=FN(22))
        c.create_text(32, 206, text="We recommend sharing: it gives you the best, most complete experience. Pick one to continue.", anchor="w",
                      fill=C["testo"], font=F(10))
        c.create_text(32, 448, text="Either way the app works the same, and you can change it any time in Settings.", anchor="w",
                      fill=C["grigio"], font=F(8))
        for k, titolo, righe, x in ((True, "Share my games", ("The full experience: meta, matchups and", "advice built from everyone's games.",
                                                            "Only cards, results, mulligans, turns.", "Never your name or your opponents'."), 32),
                                    (False, "Keep them private", ("Nothing leaves your PC.", "Everything in the app still works on",
                                                                 "your own games.", ""), 358)):
            on = self.scelta is k
            sopra = self.sopra == ("scelta", k)
            bordo = C["accento"] if on else ("#4a4a52" if sopra else C["filo"])
            fondo = "#0f2433" if on else ("#1d1d22" if sopra else C["scheda"])
            larga, alta, y0 = 310, 196, 232
            c.create_image(x, y0, image=_riquadro(larga, alta, bordo, fondo, 2.0 if on else 1.2), anchor="nw")
            c.create_image(x + 22, y0 + 34, image=_icona_scelta(28, "condividi" if k else "privato", C["accento"] if on else C["grigio"]), anchor="w")
            c.create_text(x + 62, y0 + 34, text=titolo, anchor="w", fill=C["titolo"], font=F(11, True))
            c.create_image(x + larga - 22, y0 + 34, image=DG.tondo(16, on, C["accento"], C["fondo"], "#55555c", "#ffffff"), anchor="e")
            for i, r in enumerate(righe):
                c.create_text(x + 22, y0 + 78 + i * 20, text=r, anchor="w", fill=C["testo"] if on else C["grigio"], font=F(9))
            if k:       # il bollino sul bordo alto del riquadro consigliato
                c.create_image(x + 20, y0, image=DG.pillola(118, 22, C["verde"], C["verde"]), anchor="w")
                c.create_text(x + 79, y0, text="★ RECOMMENDED", fill="#ffffff", font=F(7, True), tags="consigliata")
            self.box.append((x, y0, x + larga, y0 + alta, ("scelta", k)))
        url = PS.privacy_url()
        if url:
            i_ = c.create_text(LARGA - 32, 448, text="Privacy notice ↗", anchor="e", fill=C["accento"], font=F(9))
            bb = c.bbox(i_)
            self.box.append((bb[0] - 2, bb[1] - 2, bb[2] + 2, bb[3] + 2, ("privacy", url)))

    def disegna_collezione(self):
        c, F = self.c, self.F
        c.create_text(32, 176, text="Your collection", anchor="w", fill=C["titolo"], font=FN(22))
        c.create_text(32, 206, text="Link your Untapped.gg profile: Arena's log does not list every card you own, your public profile does.", anchor="w",
                      fill=C["testo"], font=F(10))
        c.create_image(32, 232, image=_riquadro(LARGA - 64, 200, C["verde"] if self.collegato else C["filo"], C["scheda"], 1.4), anchor="nw")
        c.create_text(54, 260, text="YOUR PUBLIC PROFILE LINK", anchor="w", fill=C["muto"], font=F(7, True))
        self.e.place(x=54, y=276, width=LARGA - 64 - 22 - 22 - 120, height=36)
        self.b_link.place(x=LARGA - 32 - 22 - 110, y=276)
        stato = self.msg_link or ("✓  Linked to your Untapped profile: you can continue, or paste another link." if self.collegato else
                                  "On mtga.untapped.gg open your profile, copy the address (mtga.untapped.gg/profile/…) and paste it here.")
        col = self.msg_col if self.msg_link else (C["verde_t"] if self.collegato else C["grigio"])
        c.create_text(54, 336, text=stato, anchor="nw", fill=col, font=F(9), width=LARGA - 120)
        c.create_text(54, 392, text="With it: the cards you own, the wildcards each deck needs, your collection in the Collection tab.", anchor="nw",
                      fill=C["grigio"], font=F(8), width=LARGA - 120)

    def disegna_piede(self):
        c, F = self.c, self.F
        c.create_line(28, ALTA - 88, LARGA - 28, ALTA - 88, fill=C["filo"])
        c.create_text(32, ALTA - 46, text=f"Step {self.passo} of {len(PASSI)}", anchor="w", fill=C["grigio"], font=F(9))
        if self.passo == 1:         # Arena: avanti anche senza (si puo' accendere dopo), ma il pulsante dice che manca
            self.b_avanti.metti("Continue  →" if self.log == "on" else "Continue anyway", AZZURRO if self.log == "on" else GRIGIO)
        elif self.passo == 2:       # la condivisione: una scelta, si' o no, prima di andare avanti
            self.b_avanti.metti("Continue  →", AZZURRO if self.scelta is not None else SPENTO)
        elif self.passo == 3:
            self.b_avanti.metti("Continue  →" if self.collegato else "Skip for now", AZZURRO if self.collegato else GRIGIO)
        else:
            self.b_avanti.metti("Start", AZZURRO)
        if self.passo > 1:
            self.b_indietro.place(x=LARGA - 32 - 160 - 12 - 110, y=ALTA - 66)
        else:
            self.b_indietro.place_forget()
        self.b_avanti.place(x=LARGA - 32 - 160, y=ALTA - 66)

    # ------------------------------------------------ i gesti
    def _dove(self, e):
        return next((b[4] for b in self.box if b[0] <= e.x <= b[2] and b[1] <= e.y <= b[3]), None)

    def muovi(self, e):
        k = self._dove(e)
        self.c.configure(cursor="hand2" if k else "")
        if k != self.sopra:
            self.sopra = k
            if self.passo == 2:
                self.disegna()

    def clic(self, e):
        k = self._dove(e)
        if not k:
            return None
        if k[0] == "scelta":
            import condividi
            self.scelta = k[1]
            condividi.imposta_consenso(k[1])
            for b in list(PS.ALTRI):        # la scheda Settings dice la stessa cosa
                try:
                    b.aggiorna()
                except Exception:       # noqa: BLE001
                    PS.ALTRI.discard(b)
            self.disegna()
        elif k[0] == "privacy":
            webbrowser.open(k[1])
        return k

    def avanti(self):
        if self.passo == 2 and self.scelta is None:
            return False
        if self.passo == len(PASSI):
            self.fine()
            return True
        self.passo += 1
        self.msg_link = ""
        self.disegna()
        if self.passo == 3:
            try:
                self.e.focus_set()
            except Exception:       # noqa: BLE001
                pass
        return True

    def indietro(self):
        self.passo = max(1, self.passo - 1)
        self.msg_link = ""
        self.disegna()

    def ricontrolla(self):
        self.log = PS.log_dettagliato()
        if self.passo == 1:
            self.disegna()
        return self.log

    def guarda_log(self):
        """Al passo di Arena il log si riguarda da solo ogni 3 s: acceso Detailed Logs e riavviata Arena, la riga diventa verde senza clic."""
        try:
            if not self.f.winfo_exists():
                return
        except Exception:       # noqa: BLE001
            return
        if self.passo == 1 and PS.log_dettagliato() != self.log:
            self.ricontrolla()
        self.f.after(3000, self.guarda_log)

    def collega(self):
        """Lo stesso collegamento della scheda Settings (pagina_settings.Collezione.collega): link giusto, poi lo scarico in un filo."""
        import account
        if not account.collega_untapped(self.v_link.get()):
            self.msg_link, self.msg_col = "That is not an Untapped profile link. It looks like https://mtga.untapped.gg/profile/<id>/<id>", C["rosso_t"]
            self.disegna()
            return False
        self.collegato = True
        self.msg_link, self.msg_col = "✓  Linked. Downloading your collection in the background: you can continue.", C["verde_t"]
        self.disegna()

        def lavoro():
            try:
                import collezione_viva as CV
                CV.aggiorna_scarico()
            except Exception:       # noqa: BLE001 - riprova la finestra grande fra qualche minuto
                pass
        import threading
        threading.Thread(target=lavoro, daemon=True).start()
        return True

    def fine(self):
        try:
            PS.segna_benvenuto()
        except Exception:       # noqa: BLE001 - il file degli account non si scrive: la finestra si richiedera'
            pass
        self._via()

    def chiudi_senza(self):
        """La X a meta': niente di segnato, si richiede al prossimo avvio (la scelta del passo 1, se fatta, resta)."""
        self._via()

    def _via(self):
        try:
            self.f.grab_release()
        except Exception:       # noqa: BLE001
            pass
        self.f.destroy()
        if self.su_fatto:
            self.su_fatto()


def apri(tk, root, F, su_fatto=None, x=None, y=None, grab=True):
    return Benvenuto(tk, root, F, su_fatto=su_fatto, x=x, y=y, grab=grab)


def prova():
    """Fuori schermo, con consenso, account e log di Arena in memoria: Arena (spento, acceso, senza log), la condivisione (non va avanti senza scelta),
    il link (sbagliato e giusto), Ready; Start segna il benvenuto, la X a meta' no."""
    import json
    import tkinter as tk
    import account
    import condividi
    root = tk.Tk(); root.geometry("900x700+7000+0")
    F = lambda n, g=False: ("Segoe UI", n, "bold" if g else "normal")
    vero = (condividi.consenso, condividi.imposta_consenso, account.leggi, account.salva, account.collega_untapped, account.account)
    mem = {"si": None, "d": {"conti": {}}, "link": None}
    casi, fatti = [], []
    try:
        condividi.consenso = lambda conto=None: mem["si"]
        condividi.imposta_consenso = lambda si, conto=None: mem.update(si=bool(si))
        account.leggi = lambda: json.loads(json.dumps(mem["d"]))
        account.salva = lambda d: mem.update(d=d)
        account.collega_untapped = lambda l: ("mtga.untapped.gg/profile/" in (l or "")) and (mem.update(link=l) or True)
        account.account = lambda: dict(id="x1", untapped_player=None)
        import collezione_viva as CV
        vero_s = CV.aggiorna_scarico
        CV.aggiorna_scarico = lambda: None
        vero_log = PS.log_dettagliato
        PS.log_dettagliato = lambda f=None: mem.get("log", "off")
        b = apri(tk, root, F, su_fatto=lambda: fatti.append(1), x=7100, y=50, grab=False); root.update()
        testi = lambda: [b.c.itemcget(i, "text") for i in b.c.find_all() if b.c.type(i) == "text"]
        bott = lambda: b.b_avanti.c.itemcget(b.b_avanti.c.find_withtag("testo")[0], "text")
        casi.append(("passo 1, Arena: i passi di Detailed Logs, «Step 1 of 4»; spento lo dice in arancio e il pulsante e' «Continue anyway»",
                     "Arena: turn on Detailed Logs" in testi() and "Detailed Logs (Plugin Support)" in testi() and "Step 1 of 4" in testi()
                     and any("is OFF" in t for t in testi()) and bott() == "Continue anyway"))
        mem["log"] = "on"
        b.ricontrolla(); root.update()
        casi.append(("acceso in Arena (Check again): verde e «Continue»", any("is ON" in t for t in testi()) and bott().startswith("Continue  ")))
        mem["log"] = "nessun_log"; b.ricontrolla(); root.update()
        casi.append(("negativa: senza log di Arena non dice ON, dice di aprire Arena", not any("is ON" in t for t in testi()) and any("start Arena once" in t for t in testi())))
        b.avanti(); root.update()
        casi.append(("passo 2: i due riquadri, «Share my games» consigliata (il bollino) ma non scelta di partenza", b.passo == 2 and "Share my games" in testi()
                     and "Keep them private" in testi() and "Step 2 of 4" in testi() and "★ RECOMMENDED" in testi() and b.scelta is None
                     and any("We recommend sharing" in t for t in testi())))
        casi.append(("negativa: senza una scelta Continue non va avanti", b.avanti() is False and b.passo == 2))
        dove = next(x for x in b.box if x[4] == ("scelta", True))
        b.c.event_generate("<Button-1>", x=dove[0] + 40, y=dove[1] + 40); root.update()
        casi.append(("il clic su «Share my games» accende la condivisione", mem["si"] is True and b.scelta is True))
        dove = next(x for x in b.box if x[4] == ("scelta", False))
        b.c.event_generate("<Button-1>", x=dove[0] + 40, y=dove[1] + 40); root.update()
        casi.append(("«Keep them private» la spegne, e si va avanti lo stesso (consenso libero)", mem["si"] is False and b.avanti() and b.passo == 3))
        casi.append(("passo 3: il campo del link, «Skip for now» finche' non e' collegato", "Your collection" in testi()
                     and b.e.winfo_manager() == "place" and bott() == "Skip for now"))
        b.v_link.set("https://example.org/x")
        casi.append(("negativa: un link sbagliato non collega e lo dice", b.collega() is False and not b.collegato and any("not an Untapped" in t for t in testi())))
        b.v_link.set("https://mtga.untapped.gg/profile/aaa/bbb")
        casi.append(("il link giusto collega", b.collega() and b.collegato and mem["link"]))
        b.avanti(); root.update()
        casi.append(("passo 4, Ready: come si usa l'app (app aperta, Drafter, eventi competitivi), «Start»", b.passo == 4 and "You're ready" in testi()
                     and any("Close the app in sanctioned" in t for t in testi()) and bott() == "Start" and b.e.winfo_manager() == ""))
        casi.append(("negativa: prima di Start il benvenuto non e' fatto", not PS.benvenuto_fatto()))
        b.avanti(); root.update()
        casi.append(("Start: benvenuto fatto, finestra chiusa, la finestra grande avvisata", PS.benvenuto_fatto() and not b.f.winfo_exists() and fatti == [1]))
        mem["d"] = {"conti": {}}
        b2 = apri(tk, root, F, x=7100, y=50, grab=False); root.update()
        b2.chiudi_senza(); root.update()
        casi.append(("negativa: chiusa con la X a meta' non e' fatto (si richiede al prossimo avvio)", not PS.benvenuto_fatto()))
        CV.aggiorna_scarico = vero_s
        PS.log_dettagliato = vero_log
    finally:
        condividi.consenso, condividi.imposta_consenso, account.leggi, account.salva, account.collega_untapped, account.account = vero
        root.destroy()
    for n, ok in casi:
        print(("ok    " if ok else "ROSSO ") + n)
    print(f"{sum(1 for _n, ok in casi if ok)}/{len(casi)}")
    return all(ok for _n, ok in casi)


if __name__ == "__main__":
    sys.exit(0 if prova() else 1)
