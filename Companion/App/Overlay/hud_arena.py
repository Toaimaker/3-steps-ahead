"""Il Deck HUD sopra Arena (sessione Magic 15, 12 nov 2026, Autore: «Sì, sopra Arena»).

Come l'overlay della costruzione (overlay.py), una finestra trasparente sopra Arena che lascia passare i clic e non prende mai il fuoco (WS_EX_LAYERED |
WS_EX_TRANSPARENT | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW), esclusa dalle catture dello schermo (WDA_EXCLUDEFROMCAPTURE: non finisce negli screenshot ne' nelle
dirette). Un pannello piccolo in alto a sinistra di Arena, la zona del campo dell'avversario che di solito e' vuota: l'archetipo con la confidenza, le carte
probabili, le istantanee che il suo mana aperto paga, il tuo record contro di lui; nel limited la coppia coi numeri di 17Lands. I conti sono quelli della
finestra Deck HUD (hud_mazzo, hud_partita): niente nomi o id dell'avversario, nessun file oltre al pid.

Si vede solo durante una partita, con Arena visibile in quel punto dello schermo (un'altra finestra sopra Arena, Arena ridotta a icona: niente), mai negli
eventi competitivi sanzionati e contro Sparky. La lancia la finestra grande quando «On Arena» e' acceso nella finestra Deck HUD (Log_Arena/hud_arena.json,
acceso di partenza); si chiude da sola quando lo spegni, quando la finestra grande che l'ha lanciata si chiude, e una sola alla volta (Log_Arena/hud_arena.pid).
Solo Windows (Distribuzione/Mac.md: sul Mac l'overlay non c'e').

    py -I -X utf8 Companion/App/Overlay/hud_arena.py --pid N          (la lancia la finestra grande)
    py -I -X utf8 Companion/App/Overlay/hud_arena.py --prova          fuori schermo, su log finti, con le negative
"""
import os, sys
_casa = os.path.dirname(os.path.abspath(__file__))      # si sale fino a percorsi.py, che mette nel sys.path tutte le cartelle del Companion
while not os.path.isfile(os.path.join(_casa, "percorsi.py")):
    _casa = os.path.dirname(_casa)
if _casa not in sys.path:
    sys.path.insert(0, _casa)
import percorsi  # noqa: E402
import ctypes  # noqa: E402
import json  # noqa: E402
import threading  # noqa: E402
import hud_mazzo as HM  # noqa: E402
import hud_partita as HP  # noqa: E402
import matchup_log as ML  # noqa: E402

LOGDIR = os.path.join(percorsi.ROOT, "Log_Arena")
PREF = os.path.join(LOGDIR, "hud_arena.json")
PIDFILE = os.path.join(LOGDIR, "hud_arena.pid")
CHIAVE = "#010203"      # il colore che la finestra rende trasparente
COL = dict(fondo="#101014", filo="#24baff", titolo="#ffffff", testo="#bebec2", grigio="#96969a", azzurro="#24baff", arancio="#f0ad4e", rosso="#ee8a87")
ALFA = 0.9              # il pannello appena trasparente sopra il tavolo
POSTO = (0.012, 0.085)  # in alto a sinistra, in frazioni dell'area di Arena
LARGO = 300             # pixel a 1080 di altezza
OGNI = 700              # ms fra un giro e l'altro


def preferenza():
    """«On Arena» acceso o spento (acceso di partenza: Autore l'ha chiesto)."""
    try:
        with open(PREF, encoding="utf-8") as f:
            return bool(json.load(f).get("acceso", True))
    except (OSError, ValueError):
        return True


def imposta(acceso):
    try:
        os.makedirs(LOGDIR, exist_ok=True)
        with open(PREF, "w", encoding="utf-8") as f:
            json.dump({"acceso": bool(acceso)}, f)
    except OSError:
        pass


# ------------------------------------------------------------------ Arena (solo ctypes: niente messaggi alla finestra di Tk dal filo di lavoro)
if sys.platform == "win32":
    from ctypes import wintypes     # solo Windows: sul Mac il modulo non c'e' (prova_mac.py)
    user32 = ctypes.WinDLL("user32", use_last_error=True)      # una copia sua: gli argtypes qui sotto non toccano ctypes.windll.user32 di chi importa il modulo
    user32.FindWindowW.restype = user32.GetForegroundWindow.restype = user32.WindowFromPoint.restype = user32.GetAncestor.restype = ctypes.c_void_p
    user32.FindWindowW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p]
    user32.IsWindowVisible.argtypes = user32.IsIconic.argtypes = [ctypes.c_void_p]
    user32.GetAncestor.argtypes = [ctypes.c_void_p, ctypes.c_uint]
    user32.GetClientRect.argtypes = [ctypes.c_void_p, ctypes.POINTER(wintypes.RECT)]
    user32.ClientToScreen.argtypes = [ctypes.c_void_p, ctypes.POINTER(wintypes.POINT)]
    user32.WindowFromPoint.argtypes = [wintypes.POINT]
else:
    user32 = None


def finestra_arena():
    """(hwnd, (sinistra, alto, destra, basso) dell'area client) o (None, None); (hwnd, None) se Arena e' ridotta a icona."""
    if user32 is None:
        return None, None
    h = user32.FindWindowW("UnityWndClass", "MTGA") or user32.FindWindowW(None, "MTGA")
    if not h or not user32.IsWindowVisible(h):
        return None, None
    if user32.IsIconic(h):
        return h, None
    r = wintypes.RECT()
    user32.GetClientRect(h, ctypes.byref(r))
    p = wintypes.POINT(0, 0)
    user32.ClientToScreen(h, ctypes.byref(p))
    return h, (p.x, p.y, p.x + r.right - r.left, p.y + r.bottom - r.top)


def arena_in_cima(h, x, y):
    """True se nel punto (x, y) dello schermo la finestra in cima e' Arena (le finestre che lasciano passare i clic, come questa, non contano)."""
    w = user32.WindowFromPoint(wintypes.POINT(int(x), int(y)))
    return bool(w) and user32.GetAncestor(w, 2) == h        # GA_ROOT


def righe(h):
    """Il pannello a righe: [(testo, stile)], stile fra titolo, testo, grigio, azzurro, arancio, rosso. [] se non c'e' niente da mostrare."""
    if not h or h.get("tipo") in (None, "spento") or h.get("finita"):
        return []
    out = []
    if h["tipo"] == "limited":
        cc = h.get("coppie") or []
        if not cc:
            return [("OPPONENT · colors unknown yet", "grigio")]
        out.append((f"{cc[0][1]}  {round(100 * cc[0][2])}%", "titolo"))
        out += [(" · ".join(f"{n} {round(100 * p)}%" for _k, n, p in cc[1:3]), "grigio")] if len(cc) > 1 else []
        x = h.get("l17")
        if x:
            out.append((f"17Lands: wins {x['wr']}% · play {x['play']}% · draw {x['draw']}%", "testo"))
            if x.get("tu_contro"):
                t = x["tu_contro"]
                out.append((f"{t['coppia']} vs it: {t['wr']}%", "azzurro" if t["wr"] >= 50 else "rosso"))
    else:
        aa = h.get("archetipi") or []
        if not aa:
            return []
        n, p = aa[0]
        out.append((f"{n}  {round(100 * p)}%" if p is not None else n, "titolo"))
        if len(aa) > 1 and aa[1][1] is not None:
            out.append(("or " + " · ".join(f"{a} {round(100 * q)}%" for a, q in aa[1:3] if q is not None), "grigio"))
        pr = h.get("probabili") or []
        if pr:
            out.append(("Likely: " + ", ".join(f"{a} {round(100 * q)}%" for a, q, _c in pr[:4]), "testo"))
    ist = h.get("istantanee") or []
    if ist:
        out.append((f"{h.get('aperte', 0)} open: " + ", ".join(x[0] for x in ist[:3]), "arancio"))
    t = (h.get("contro") or {}).get("tutti")
    if t:
        pl, dr = t["play"], t["draw"]
        out.append((f"You {t['vinte']}-{t['perse']} ({t['wr']}%) · play {pl[1]}-{pl[0] - pl[1]} · draw {dr[1]}-{dr[0] - dr[1]}",
                    "grigio" if t["poche"] else ("azzurro" if (t["wr"] or 0) >= 50 else "rosso")))
    return out


class HudArena:
    def __init__(self, file=None, io=None, pid=None, in_cattura=False, area_finta=None, sempre=False, recs=None, meta=None):
        import tkinter as tk
        self.tk = tk
        self.seg = HP.Seguito(file, io)
        self.pid = pid
        self.area_finta, self.sempre = area_finta, sempre     # le prove: un'area di Arena finta, e niente controllo di chi sta in cima
        self.recs, self.meta = recs, meta
        self.h, self.firma, self.disegnato = None, None, None
        self.letto = threading.Event()
        prima = user32.GetForegroundWindow() if user32 else None
        self.root = tk.Tk()
        self.root.withdraw()        # nascosta finche' non ha gli stili: alla prima comparsa Tk prende il fuoco
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-transparentcolor", CHIAVE)
        self.root.attributes("-alpha", ALFA)
        self.root.configure(bg=CHIAVE)
        self.root.geometry("10x10+-3000+0")
        self.cv = tk.Canvas(self.root, bg=CHIAVE, highlightthickness=0)
        self.cv.pack(fill="both", expand=True)
        self.root.update_idletasks()
        self.hwnd = int(self.root.wm_frame(), 16)
        if user32:
            st = user32.GetWindowLongW(self.hwnd, -20)      # GWL_EXSTYLE
            user32.SetWindowLongW(self.hwnd, -20, st | 0x80000 | 0x20 | 0x8000000 | 0x80 | 0x8)     # LAYERED TRANSPARENT NOACTIVATE TOOLWINDOW TOPMOST
        self.root.deiconify()
        self.root.update()
        if user32 and prima and prima != self.hwnd and user32.GetForegroundWindow() == self.hwnd:
            user32.SetForegroundWindow(prima)       # se comparendo si e' presa il fuoco, lo rende
        self.esclusa = bool(user32.SetWindowDisplayAffinity(self.hwnd, 0x11)) if user32 and not in_cattura else False
        threading.Thread(target=self._primo, daemon=True).start()

    def _primo(self):
        self.seg.aggiorna()         # la prima lettura del log intero, in un filo
        if self.recs is None:
            try:
                self.recs = ML.records()
            except Exception:       # noqa: BLE001 - senza le tue partite l'HUD dice solo il mazzo
                self.recs = []
        self.letto.set()

    def da_chiudere(self):
        if self.pid and not _vivo(self.pid):
            return "la finestra grande non c'e' piu'"
        if not self.sempre and not preferenza():
            return "On Arena spento"
        return None

    def giro(self):
        """Un giro: rilegge la partita, decide se il pannello si vede e lo ridisegna se e' cambiato. -> le righe disegnate."""
        if not self.letto.is_set():
            return []
        st = self.seg.aggiorna()
        firma = None if st is None else (st["matchId"], tuple(st["sue"]), st["aperte"], st["turno"], st["finita"], st.get("sul_play"))
        if firma != self.firma:
            if st and st.get("finita") and self.firma and self.firma[4] is False:      # a fine partita le tue partite si rileggono, per il record
                threading.Thread(target=self._rileggi, daemon=True).start()
            self.firma = firma
            self.h = HM.scheda(st, recs=self.recs or [], meta=self.meta) if st else None
        rr = righe(self.h)
        area = self.area_finta
        if area is None:
            h, area = finestra_arena()
            if area is None:
                rr = []
            else:
                W, H = area[2] - area[0], area[3] - area[1]
                if not arena_in_cima(h, area[0] + (POSTO[0] + 0.02) * W, area[1] + (POSTO[1] + 0.02) * H):
                    rr = []
        self.disegna(rr, area)
        return rr

    def _rileggi(self):
        try:
            self.recs = ML.records()
            self.firma = None
        except Exception:       # noqa: BLE001
            pass

    def disegna(self, rr, area):
        chiave = (tuple(rr), area)
        if chiave == self.disegnato:
            return
        self.disegnato = chiave
        self.cv.delete("all")
        if not rr or not area:
            return
        W, H = area[2] - area[0], area[3] - area[1]
        s = max(0.6, H / 1080)
        x0, y0 = int(area[0] + POSTO[0] * W), int(area[1] + POSTO[1] * H)
        larg = int(LARGO * s)
        f_t = ("Segoe UI", -max(12, int(17 * s)), "bold")
        f_r = ("Segoe UI", -max(10, int(12 * s)))
        y = int(8 * s)
        ids = []
        for i, (t, stile) in enumerate([("OPPONENT DECK", "grigio")] + rr):
            f = f_t if stile == "titolo" else ("Segoe UI", -max(9, int(10 * s)), "bold") if i == 0 else f_r
            ids.append(self.cv.create_text(int(10 * s), y, text=t, anchor="nw", width=larg - int(20 * s), font=f, fill=COL[stile], tags="riga"))
            bb = self.cv.bbox(ids[-1])
            y = bb[3] + int(3 * s)
        alto = y + int(6 * s)
        fondo = self.cv.create_rectangle(0, 0, larg - 1, alto - 1, fill=COL["fondo"], outline=COL["filo"])
        self.cv.create_rectangle(0, 0, int(3 * s), alto - 1, fill=COL["filo"], width=0)
        self.cv.tag_lower(fondo)
        self.root.geometry(f"{larg}x{alto}+{x0}+{y0}")

    def testi(self):
        return [self.cv.itemcget(i, "text") for i in self.cv.find_withtag("riga")]

    def vai(self):
        def passo():
            try:
                motivo = self.da_chiudere()
                if motivo:
                    self.root.destroy()
                    return
                self.giro()
            except Exception as e:      # noqa: BLE001 - un giro andato male non chiude il pannello
                print("hud_arena:", f"{type(e).__name__}: {e}", file=sys.stderr)
            self.root.after(OGNI, passo)
        self.root.after(OGNI, passo)
        self.root.mainloop()


def _vivo(pid):
    try:
        import piattaforma
        return piattaforma.processo_vivo(int(pid))
    except Exception:       # noqa: BLE001
        return True


def una_sola():
    """La nuova chiude la vecchia."""
    try:
        vecchio = int(open(PIDFILE).read().strip())
        if vecchio != os.getpid() and _vivo(vecchio):
            h = ctypes.windll.kernel32.OpenProcess(0x0001, False, vecchio)     # PROCESS_TERMINATE
            if h:
                ctypes.windll.kernel32.TerminateProcess(h, 0)
                ctypes.windll.kernel32.CloseHandle(h)
    except (OSError, ValueError):
        pass
    try:
        with open(PIDFILE, "w") as f:
            f.write(str(os.getpid()))
    except OSError:
        pass


# ------------------------------------------------------------------ le prove
def prova():
    import tempfile
    casi = []
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
    meta = [dict(nome="Mono-White Auras", colori="W", quota=10, lista={"Ethereal Armor": 4, "Sheltered by Ghosts": 4, "Seam Rip": 2, "Plains": 20}),
            dict(nome="Izzet Prowess", colori="UR", quota=8, lista={"Opt": 4, "Lightning Strike": 4, "Spell Pierce": 2, "Island": 8})]
    d = tempfile.mkdtemp()
    f1 = os.path.join(d, "c.log")
    open(f1, "w", encoding="utf-8").write(stanza("m1", "Ladder", "Playing") + gs([(5, g("Island"), True), (7, g("Opt"), False), (8, g("Lightning Strike"), False)], 3, 2))
    area = (-3000, 0, -3000 + 1920, 1080)       # un'Arena finta fuori schermo, a 1920x1080
    w = HudArena(file=f1, io=(ME, None), area_finta=area, sempre=True, recs=[], meta=meta, in_cattura=True)
    w.letto.wait(10)
    rr = w.giro(); w.root.update()
    tt = w.testi()
    casi.append(("il pannello: archetipo con la P, probabili, istantanee col mana aperto", tt and tt[0] == "OPPONENT DECK" and tt[1].startswith("Izzet Prowess")
                 and any(x.startswith("Likely:") for x in tt) and any(x.startswith("1 open:") for x in tt)))
    geo = (w.root.winfo_width(), w.root.winfo_x())
    casi.append(("in alto a sinistra di Arena, largo 300 pixel a 1080", geo[0] == LARGO and abs(geo[1] - (area[0] + int(POSTO[0] * 1920))) <= 1))
    casi.append(("negativa: nome e id dell'avversario mai nel pannello", not any("NomeAvversario" in x or "OPPID" in x for x in tt)))
    ex = w.root.tk.call("wm", "attributes", w.root._w, "-topmost")
    casi.append(("sopra le altre finestre, lascia passare i clic e non prende il fuoco", bool(int(ex)) and (user32 is None or (user32.GetWindowLongW(w.hwnd, -20) & 0x8000020) == 0x8000020)))
    casi.append(("niente di nuovo: non si ridisegna", w.disegnato is not None and w.giro() == rr))
    w.pid = os.getpid()
    vivo_padre = w.da_chiudere()
    w.pid = 4 * 10 ** 6 + 7     # un pid che non c'e'
    casi.append(("si chiude quando la finestra che l'ha lanciato non c'e' piu' (negativa: col padre vivo resta)", vivo_padre is None and bool(w.da_chiudere())))
    w.pid = None
    with open(f1, "a", encoding="utf-8") as fh:
        fh.write(stanza("m1", "Ladder", "MatchCompleted"))
    w.giro(); w.root.update()
    casi.append(("negativa: a partita finita il pannello sparisce", w.testi() == []))
    w.root.destroy()
    f2 = os.path.join(d, "q.log")
    open(f2, "w", encoding="utf-8").write(stanza("m2", "Arena_Championship_Qualifier_X", "Playing") + gs([(7, g("Opt"), False)], 3, 2))
    w2 = HudArena(file=f2, io=(ME, None), area_finta=area, sempre=True, recs=[], meta=meta, in_cattura=True)
    w2.letto.wait(10)
    w2.giro(); w2.root.update()
    casi.append(("negativa: evento competitivo, il pannello non c'e'", w2.testi() == []))
    w2.root.destroy()
    if finestra_arena()[1] is None:        # Arena chiusa (le prove non girano con Arena aperta): senza la sua finestra il pannello non c'e'
        w3 = HudArena(file=f1.replace("c.log", "c2.log"), io=(ME, None), sempre=True, recs=[], meta=meta, in_cattura=True)
        open(f1.replace("c.log", "c2.log"), "w", encoding="utf-8").write(stanza("m3", "Ladder", "Playing") + gs([(7, g("Opt"), False)], 3, 2))
        w3.seg.pos = 0
        w3.letto.wait(10)
        casi.append(("negativa: senza la finestra di Arena il pannello non c'e'", w3.giro() == [] and w3.testi() == []))
        w3.root.destroy()
    vecchio = PREF
    globals()["PREF"] = os.path.join(d, "pref.json")
    acceso0 = preferenza()
    imposta(False)
    spento = preferenza()
    globals()["PREF"] = vecchio
    casi.append(("«On Arena»: acceso di partenza, si spegne e resta spento", acceso0 is True and spento is False))
    casi.append(("negativa: nessun file oltre alla preferenza della prova", not set(os.listdir(d)) - {"c.log", "c2.log", "pref.json", "q.log"}))
    for n_, ok in casi:
        print(("ok    " if ok else "ROSSO ") + n_)
    print(f"{sum(ok for _n, ok in casi)}/{len(casi)}")
    return all(ok for _n, ok in casi)


def main():
    a = sys.argv[1:]
    if "--prova" in a:
        sys.exit(0 if prova() else 1)
    if sys.platform != "win32":
        print("hud_arena: solo Windows")
        return
    pid = int(a[a.index("--pid") + 1]) if "--pid" in a else None
    una_sola()
    HudArena(pid=pid, in_cattura="--in-cattura" in a).vai()


if __name__ == "__main__":
    main()
