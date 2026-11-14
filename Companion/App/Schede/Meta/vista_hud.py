"""Il Deck HUD nella finestra grande: il pulsante nella barra delle schede e la sorveglianza del pannello sopra Arena (sessione Magic 15, 12 nov 2026; i
conti in hud_mazzo, la partita in hud_partita, il pannello in Overlay/hud_arena.py).

L'HUD si vede solo sopra Arena, mai in una finestra dell'app (Autore, 12 nov 2026: «il pulsante di hud fallo piu' visibile / l'hud deve caricarsi sempre in
overlay su arena di default e da nessun altra parte solo li»; fino a quel giorno il pulsante apriva una finestra Deck HUD a due colonne). Il pulsante e' una
pillola azzurra piena quando l'HUD e' acceso, grigia quando e' spento, col pallino verde e LIVE durante una partita; il clic apre un menu con due interruttori,
il tuo mazzo (bordo sinistro di Arena) e il suo (bordo destro). Accesi di partenza (Log_Arena/hud_arena.json). Il pannello parte con la finestra grande e, se
cade, la sorveglianza lo rilancia (ogni 3 s guarda Log_Arena/hud_arena.pid). Su Mac il pannello sopra Arena non c'e' (Distribuzione/Mac.md): niente pulsante.

    py -I -X utf8 Companion/App/Schede/Meta/vista_hud.py --prova           fuori schermo, su log finti, con le negative
"""
import os, sys, time
_casa = os.path.dirname(os.path.abspath(__file__))      # si sale fino a percorsi.py, che mette nel sys.path tutte le cartelle del Companion
while not os.path.isfile(os.path.join(_casa, "percorsi.py")):
    _casa = os.path.dirname(_casa)
if _casa not in sys.path:
    sys.path.insert(0, _casa)
import percorsi  # noqa: E402,F401
import threading  # noqa: E402
import hud_arena as HA  # noqa: E402
import hud_partita as HP  # noqa: E402
import matchup_log as ML  # noqa: E402
from tema import CI  # noqa: E402

ARENA = sys.platform == "win32"     # il pannello sopra Arena c'e' solo su Windows (Distribuzione/Mac.md)
ALTO, LARGO = 28, 168               # la pillola nella barra delle schede (alta come la tendina dell'account)
ACCESO = ("#0f86cc", "#2ba3ea")     # la pillola accesa: normale, sotto il mouse (il blu dei pulsanti pieni, widget.pulsante_solido)
SPENTO = ("#303034", "#3c3c42")
VERDE = "#5cdb6a"                   # il pallino LIVE durante una partita
MENU = 380                          # la larghezza del menu
LARGO_SEGNA = 92                    # R13: la pillola «★ MARK» accanto, durante una partita
RILANCIO = 15                       # s: dopo un lancio non se ne fa un altro (il pannello scrive il pid quando parte)
_SEGUITO = {}       # file -> Seguito: uno per la finestra grande
_LANCIO = {"t": 0.0}
VOCI = (("mio", "Your deck", "left edge of Arena: every card, copies left, chance to draw it next"),
        ("suo", "Opponent's deck", "right edge: its archetype, likely cards, instants its open mana pays"))


def seguito(file=None, io=None):
    k = (file or "Player.log", io)
    if k not in _SEGUITO:
        _SEGUITO[k] = HP.Seguito(file, io)
    return _SEGUITO[k]


def avvia_arena():
    """Lancia il pannello sopra Arena (Overlay/hud_arena.py), legato a questa finestra: si chiude quando lei si chiude. Uno solo alla volta (lo fa hud_arena)."""
    if not ARENA:
        return False
    import subprocess
    from ambiente import LOGDIR, PY_MUTO, ROOT
    try:
        subprocess.Popen([PY_MUTO, "-I", "-X", "utf8", percorsi.programma("hud_arena.py"), "--pid", str(os.getpid())], cwd=ROOT, stdout=subprocess.DEVNULL,
                         stderr=open(os.path.join(LOGDIR, "hud_arena_errori.txt"), "a", encoding="utf-8"))
        _LANCIO["t"] = time.time()
        return True
    except OSError as e:
        print("hud_arena:", e)
        return False


def pannello_vivo():
    """Il pannello sopra Arena e' acceso? (il suo pid in Log_Arena/hud_arena.pid, e il processo c'e')."""
    try:
        pid = int(open(HA.PIDFILE).read().strip())
    except (OSError, ValueError):
        return False
    return HA._vivo(pid)


def tieni_vivo(lancia=avvia_arena):
    """Con l'HUD acceso il pannello deve esserci: se non c'e' (mai partito, caduto) lo rilancia, non piu' di una volta ogni RILANCIO secondi. -> True se ha lanciato."""
    if not (ARENA and HA.acceso()) or pannello_vivo() or time.time() - _LANCIO["t"] < RILANCIO:
        return False
    lancia()
    _LANCIO["t"] = time.time()
    return True


class Pulsante:
    """La pillola «DECK HUD» nella barra delle schede e il suo menu coi due interruttori."""

    def __init__(self, fin, tk, file=None, io=None, lancia=avvia_arena):
        import disegni
        self.D, self.tk, self.fin, self.F, self.lancia, self.file = disegni, tk, fin, fin.F, lancia, file
        self.vivo, self.sopra, self.menu = False, False, None
        c = self.c = tk.Canvas(fin.barra_schede, width=LARGO, height=ALTO, bg=CI["fondo"], highlightthickness=0, bd=0, cursor="hand2")
        c.pack(side="right", padx=(0, 10), pady=(0, 2))
        c.bind("<Button-1>", lambda e: self.apri())
        c.bind("<Enter>", lambda e: self.metti_sopra(True))
        c.bind("<Leave>", lambda e: self.metti_sopra(False))
        self.seg = seguito(file, io)
        # R13 (13 nov 2026): «★ MARK», solo durante una partita: segna lo spot (la partita e il turno) e lo ritrovi nel replayer, in My filters
        self.c_segna = tk.Canvas(fin.barra_schede, width=LARGO_SEGNA, height=ALTO, bg=CI["fondo"], highlightthickness=0, bd=0, cursor="hand2")
        self.c_segna.bind("<Button-1>", lambda e: self.segna())
        self.ultimo_segno = None
        self.disegna()

    def metti_sopra(self, v):
        self.sopra = v
        self.disegna()

    def disegna(self):
        """La pillola: azzurra piena con «ON» se almeno un pannello e' acceso, grigia con «OFF» se no; durante una partita il pallino verde e «LIVE»."""
        c, D = self.c, self.D
        c.delete("all")
        on = HA.acceso()
        fondo = (ACCESO if on else SPENTO)[1 if self.sopra else 0]
        self._img = [D.pillola(LARGO, ALTO, fondo, fondo)]
        c.create_image(0, 0, image=self._img[0], anchor="nw")
        x = 14
        if self.vivo and on:
            self._img.append(D.punto(9, VERDE))
            c.create_image(x, ALTO / 2, image=self._img[-1])
            x += 10
        c.create_text(x, ALTO / 2, text="DECK HUD", fill="#ffffff" if on else CI["grigio"], font=self.F(9, True), anchor="w", tags="testo")
        stato = ("LIVE" if self.vivo else "ON") if on else "OFF"
        c.create_text(LARGO - 30, ALTO / 2, text=stato, fill="#ffffff" if on else CI["grigio"], font=self.F(8, True), anchor="e", tags="testo")
        self._img.append(D.chevron(10, self.menu is None, "#ffffff" if on else CI["grigio"]))
        c.create_image(LARGO - 16, ALTO / 2, image=self._img[-1])

    def segna(self):
        """Segna lo spot di adesso (R13). -> True se segnato."""
        st = self.seg.stato() if hasattr(self.seg, "stato") else None
        if not st or not st.get("matchId") or not st.get("turno"):
            return False
        import dati_analizzatore as DA
        ok = DA.segna_vivo(st["matchId"], st["turno"])
        self.ultimo_segno = (st["matchId"], st["turno"])
        self.disegna_segna()
        return ok

    def disegna_segna(self):
        c, D = self.c_segna, self.D
        c.delete("all")
        if not (self.vivo and HA.acceso()):
            c.pack_forget()
            return
        if not c.winfo_manager():
            c.pack(side="right", padx=(0, 6), pady=(0, 2))
        st = self.seg.stato() if hasattr(self.seg, "stato") else None
        fatto = bool(st and self.ultimo_segno == (st.get("matchId"), st.get("turno")))
        self._img_segna = D.pillola(LARGO_SEGNA, ALTO, "#8a6d1c", "#4a4028" if fatto else "#3a3220")
        c.create_image(0, 0, image=self._img_segna, anchor="nw")
        c.create_text(LARGO_SEGNA / 2, ALTO / 2, text="★ MARKED" if fatto else "★ MARK", fill="#e8d28a", font=self.F(8, True), tags="testo")

    def testi(self):
        return [self.c.itemcget(i, "text") for i in self.c.find_withtag("testo")]

    # ------------------------------------------------------------------------------------------------ il menu
    def chiudi(self, e=None):
        if self.menu is not None:
            self.menu.destroy()
            self.menu = None
            self.disegna()

    def apri(self):
        """Il menu sotto la pillola: i due interruttori (si ricordano), e una riga che dice dove si vede l'HUD."""
        tk = self.tk
        if self.menu is not None:
            self.chiudi()
            return
        m = self.menu = tk.Toplevel(self.c)
        m.overrideredirect(True)
        m.configure(bg="#303034")
        L = MENU
        cv = self.cm = tk.Canvas(m, width=L, height=100, bg="#18181c", highlightthickness=0, bd=0)
        cv.pack(padx=1, pady=1)
        A = self.disegna_menu()
        cv.bind("<Button-1>", self.clic_menu)
        self.c.update_idletasks()
        x = self.c.winfo_rootx() + LARGO - L - 2
        y = self.c.winfo_rooty() + ALTO + 4
        m.geometry(f"{L + 2}x{A + 2}+{x}+{y}")
        m.bind("<FocusOut>", self.chiudi)
        m.bind("<Escape>", self.chiudi)
        m.focus_force()
        self.disegna()

    def disegna_menu(self):
        """Il menu, misurato sui testi veri (le righe lunghe vanno a capo, niente si accavalla). -> l'altezza."""
        cv, D, F = self.cm, self.D, self.F
        cv.delete("all")
        self._img_m = []
        largo = MENU - 32

        def scrivi(x, y, t, f, col, w=largo, tag=None):
            i = cv.create_text(x, y, text=t, fill=col, font=f, anchor="nw", width=w, tags=tag)
            return cv.bbox(i)[3]
        y = scrivi(16, 16, "DECK HUD · ON ARENA ONLY", F(9, True), CI["titolo"])
        y = scrivi(16, y + 4, "Shows on top of Arena during your games; clicks pass through.", F(8), CI["grigio"])
        self.zone = {}
        y += 16
        for chi, nome, cosa in VOCI:
            on = HA.preferenza(chi)
            pista = D.pillola(36, 20, ACCESO[0] if on else "#3c3c42", ACCESO[0] if on else "#3c3c42")
            pomo = D.punto(14, "#ffffff" if on else "#9a9aa0")
            self._img_m += [pista, pomo]
            cv.create_image(16, y + 2, image=pista, anchor="nw")
            cv.create_image(16 + (26 if on else 10), y + 12, image=pomo)
            fine = scrivi(64, y, nome, F(9, True), CI["titolo"] if on else CI["grigio"], tag="voce")
            fine = scrivi(64, fine + 2, cosa, F(8), CI["grigio"], w=MENU - 80)
            self.zone[chi] = (8, y - 6, MENU - 8, fine + 6)
            y = fine + 16
        y = scrivi(16, y, "Decks only, never players: nothing about the opponent is saved.", F(8), CI["grigio"])
        cv.configure(height=y + 16)
        return y + 16

    def clic_menu(self, e):
        for chi, (x0, y0, x1, y1) in self.zone.items():
            if x0 <= e.x <= x1 and y0 <= e.y <= y1:
                self.cambia(chi)
                return

    def cambia(self, chi):
        """Accende o spegne un pannello: spenti tutti e due il processo si chiude da solo al suo giro dopo; acceso uno, si lancia se non c'e'."""
        acc = not HA.preferenza(chi)
        HA.imposta(acc, chi)
        if acc:
            _LANCIO["t"] = 0.0
            tieni_vivo(self.lancia)
        if self.menu is not None:
            self.disegna_menu()
        self.disegna()

    # ------------------------------------------------------------------------------------------------ la sorveglianza
    def guarda(self, ancora=True):
        """Ogni 3 s: c'e' una partita (il pallino LIVE)? il pannello sopra Arena e' vivo (se no si rilancia)?"""
        try:
            st = self.seg.aggiorna()
            vivo = bool(st and not st["finita"] and st["turno"] and not st["competitivo"] and ML.formato(st["evento"]))
            if vivo != self.vivo:
                self.vivo = vivo
                self.disegna()
                self.disegna_segna()
            if self.file is None:
                tieni_vivo(self.lancia)
        except Exception as e:      # noqa: BLE001 - la sorveglianza non ferma la finestra
            print("deck hud:", f"{type(e).__name__}: {e}")
        if ancora:
            self.fin.root.after(3000, self.guarda)


def pulsante(fin, tk, file=None, io=None):
    """Il pulsante nella barra delle schede della finestra grande; con l'HUD acceso lancia subito il pannello sopra Arena (si vede solo durante una partita)."""
    if not ARENA:
        return None
    p = Pulsante(fin, tk, file, io)
    if file is None:
        tieni_vivo()
    threading.Thread(target=p.seg.aggiorna, daemon=True).start()     # la prima lettura (il log intero) in un filo: poi si leggono solo i byte nuovi
    fin.root.after(5000, p.guarda)
    return p


# --------------------------------------------------------------------------------------------------------------- le prove
def prova():
    import tempfile
    import tkinter as tk
    from tema import carica_font
    carica_font()
    casi = []
    if not ARENA:
        print("ok    su Mac niente pannello sopra Arena: niente pulsante")
        return True
    ME = "AAAAAAAAAAAAAAAAAAAAAAAAAA"
    HP.nome_grp(0)
    nomi = {n.lower(): g for g, n in HP._NOMI.items()}
    g = lambda n: nomi[n.lower()]       # noqa: E731
    posti = ('[{"userId": "%s", "playerName": "Io", "systemSeatId": 1, "teamId": 1, "eventId": "%%s"}, {"userId": "OPPID", "playerName": "NomeAvversario", '
             '"systemSeatId": 2, "teamId": 2, "eventId": "%%s"}]') % ME

    def stanza(mid, ev, tipo):
        return ('{"timestamp": "1", "matchGameRoomStateChangedEvent": {"gameRoomInfo": {"gameRoomConfig": {"reservedPlayers": %s, "matchId": "%s"}, '
                '"stateType": "MatchGameRoomStateType_%s"}}}\n') % (posti % (ev, ev), mid, tipo)

    def gs(oggetti, turno, attivo):
        ids = ", ".join(str(i) for i, _g, _t in oggetti)
        ogg = ", ".join('{ "instanceId": %d, "grpId": %d, "type": "GameObjectType_Card", "zoneId": 10, "ownerSeatId": 2, "controllerSeatId": 2%s }'
                        % (i, gr, ', "cardTypes": ["CardType_Land"]' if t else "") for i, gr, t in oggetti)
        return ('{ "transactionId": "g", "greToClientEvent": { "greToClientMessages": [ { "type": "GREMessageType_GameStateMessage", "gameStateMessage": '
                '{ "zones": [ { "zoneId": 10, "type": "ZoneType_Battlefield", "ownerSeatId": 2, "objectInstanceIds": [ %s ] } ], "gameObjects": [ %s ], '
                '"turnInfo": {"turnNumber": %d, "activePlayer": %d} } } ] } }\n') % (ids, ogg, turno, attivo)
    d = tempfile.mkdtemp()
    vecchi = (HA.PREF, HA.PIDFILE)
    HA.PREF, HA.PIDFILE = os.path.join(d, "hud_arena.json"), os.path.join(d, "hud_arena.pid")
    lanci = []
    finto = lambda: lanci.append(1) or True     # noqa: E731 - le prove non lanciano processi veri
    root = tk.Tk()
    root.geometry("600x60+-3000+0")
    F = lambda n, b=False: ("Poppins Medium" if b else "Poppins", n)     # noqa: E731
    fin = type("Fin", (), {})()
    fin.root, fin.F, fin.barra_schede = root, F, tk.Frame(root)
    fin.barra_schede.pack(fill="x")
    f = os.path.join(d, "p.log")
    io = (ME, None)
    open(f, "w", encoding="utf-8").write(stanza("m4", "Ladder", "Playing") + gs([(7, g("Ethereal Armor"), False)], 2, 2))
    p = Pulsante(fin, tk, file=f, io=io, lancia=finto)
    root.update()
    casi.append(("di partenza acceso: la pillola dice DECK HUD e ON", p.testi() == ["DECK HUD", "ON"]))
    p.guarda(False)
    casi.append(("in partita: LIVE", p.testi() == ["DECK HUD", "LIVE"]))
    # R13: «★ MARK» durante la partita (i segnalibri in un file temporaneo: i tuoi veri non si toccano)
    import dati_analizzatore as DA
    vecchio_sb = DA.SEGNALIBRI
    DA.SEGNALIBRI = os.path.join(tempfile.mkdtemp(), "s.json")
    try:
        casi.append(("R13: in partita c'e' «★ MARK» accanto a DECK HUD", p.c_segna.winfo_manager() == "pack"))
        ok1, ok2 = p.segna(), p.segna()
        sb_ = DA.segnalibri()
        casi.append(("il clic segna la partita e il turno di Arena; negativa: lo stesso turno una volta sola", ok1 and not ok2 and len(sb_) == 1
                     and sb_[0]["partita"] == "m4" and sb_[0]["t"] == 2 and sb_[0]["i"] is None
                     and [p.c_segna.itemcget(i, "text") for i in p.c_segna.find_withtag("testo")] == ["★ MARKED"]))
    finally:
        DA.SEGNALIBRI = vecchio_sb
    with open(f, "a", encoding="utf-8") as fh:
        fh.write(stanza("m4", "Ladder", "MatchCompleted"))
    p.guarda(False)
    casi.append(("a partita finita torna ON, e «★ MARK» sparisce", p.testi() == ["DECK HUD", "ON"] and not p.c_segna.winfo_manager()))
    casi.append(("negativa: nessuna finestra dell'HUD, il nome dell'avversario da nessuna parte", not any(isinstance(x, tk.Toplevel) for x in root.winfo_children())
                 and not any("NomeAvversario" in x for x in p.testi())))
    p.apri(); root.update()
    voci = [p.cm.itemcget(i, "text") for i in p.cm.find_withtag("voce")]
    casi.append(("il clic apre il menu coi due interruttori, il tuo mazzo e il suo", p.menu is not None and voci == ["Your deck", "Opponent's deck"]))
    x0, y0, _x1, _y1 = p.zone["mio"]
    p.clic_menu(type("E", (), {"x": x0 + 20, "y": y0 + 20})())
    casi.append(("spento il tuo mazzo: resta il suo, la pillola resta ON", HA.preferenza("mio") is False and HA.preferenza("suo") is True and p.testi()[1] == "ON"))
    x0, y0, _x1, _y1 = p.zone["suo"]
    p.clic_menu(type("E", (), {"x": x0 + 20, "y": y0 + 20})())
    casi.append(("spenti tutti e due: OFF, e la sorveglianza non lancia niente", p.testi() == ["DECK HUD", "OFF"] and tieni_vivo(finto) is False and lanci == []))
    p.clic_menu(type("E", (), {"x": 2, "y": 2})())
    casi.append(("negativa: un clic fuori dagli interruttori non cambia niente", HA.preferenza("mio") is False and HA.preferenza("suo") is False))
    x0, y0, _x1, _y1 = p.zone["suo"]
    p.clic_menu(type("E", (), {"x": x0 + 20, "y": y0 + 20})())
    casi.append(("riacceso il suo: il pannello si lancia (non c'era)", HA.preferenza("suo") is True and lanci == [1]))
    casi.append(("negativa: subito dopo un lancio non se ne fa un altro", tieni_vivo(finto) is False and lanci == [1]))
    _LANCIO["t"] = 0.0
    open(HA.PIDFILE, "w").write(str(os.getpid()))
    casi.append(("negativa: col pannello vivo non si rilancia", tieni_vivo(finto) is False and lanci == [1]))
    open(HA.PIDFILE, "w").write(str(4 * 10 ** 6 + 7))
    casi.append(("il pannello caduto (pid che non c'e'): si rilancia", tieni_vivo(finto) is True and lanci == [1, 1]))
    p.chiudi()
    casi.append(("Esc o un clic fuori chiudono il menu", p.menu is None))
    root.destroy()
    HA.PREF, HA.PIDFILE = vecchi
    _SEGUITO.clear()
    _LANCIO["t"] = 0.0
    scritti = sorted(x for x in os.listdir(d) if not x.endswith(".log"))
    casi.append(("negativa: l'HUD scrive solo la preferenza (e il pid della prova)", scritti == ["hud_arena.json", "hud_arena.pid"]))
    for n_, ok in casi:
        print(("ok    " if ok else "ROSSO ") + n_)
    print(f"{sum(ok for _n, ok in casi)}/{len(casi)}")
    return all(ok for _n, ok in casi)


if __name__ == "__main__":
    if "--prova" in sys.argv:
        sys.exit(0 if prova() else 1)
    print(__doc__)
