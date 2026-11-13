"""Il Deck HUD sopra Arena (sessione Magic 15, 12 nov 2026, Autore: «Sì, sopra Arena»).

Come l'overlay della costruzione (overlay.py), una finestra trasparente sopra Arena che lascia passare i clic e non prende mai il fuoco (WS_EX_LAYERED |
WS_EX_TRANSPARENT | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW), esclusa dalle catture dello schermo (WDA_EXCLUDEFROMCAPTURE: non finisce negli screenshot ne' nelle
dirette). Due pannelli a lista sui bordi di Arena (Autore, 12 nov 2026: «l'hud in partita voglio il mio deck sul bordo sinistro il suo sul bordo destro,
belli leggibili nelle liste delle carte / il mio deck deve dirmi quante carte mie ho in quante copie, man mano che scendono mi aggiorna il numero e mi da la %
di trovarle alla prossima pescata»): a sinistra il tuo mazzo, carta per carta, con le copie rimaste su quelle del mazzo e la P di pescarla alla prossima
pescata, le terre in fondo; a destra il suo: l'archetipo con la confidenza, le carte probabili con la P, le istantanee che il suo mana aperto paga, il tuo
record contro di lui (nel limited la coppia coi numeri di 17Lands). I conti sono in hud_mazzo e hud_partita: niente nomi o id
dell'avversario, nessun file oltre al pid.

Si vede solo durante una partita, con Arena visibile in quel punto dello schermo (un'altra finestra sopra Arena, Arena ridotta a icona: niente), mai negli
eventi competitivi sanzionati e contro Sparky. La lancia la finestra grande quando l'HUD e' acceso (la pillola DECK HUD nella barra delle schede, vista_hud.py; l'HUD si vede solo qui, dal 12 nov 2026 sera) (Log_Arena/hud_arena.json,
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
DIARIO = os.path.join(LOGDIR, "hud_arena_diario.txt")     # quando il pannello si accende e si spegne, e perche' (13 nov 2026: «non parte in automatico»)
PIDFILE = os.path.join(LOGDIR, "hud_arena.pid")
CHIAVE = "#010203"      # il colore che la finestra rende trasparente
COL = dict(fondo="#101014", filo="#24baff", titolo="#ffffff", testo="#f0f0f2", grigio="#cacace", azzurro="#3cc4ff", arancio="#ffbe5c", rosso="#ff9a97")
# sullo sfondo trasparente i colori sono piu' chiari di quelli dell'app: il tavolo di Arena sotto puo' essere scuro o chiaro, e l'ombra fa il resto
ALFA = 1.0              # i testi pieni: lo sfondo dei pannelli e' gia' trasparente
OMBRA = "#000000"       # l'ombra dei testi: diversa dal colore chiave, quindi si vede
SEPARA = "#a0a0a6"      # le righe fra le carte, sottili e chiare
SPENTA = "#8a8a90"      # una carta finita
POSTO = (0.002, 0.10)   # dal bordo (sinistro per il tuo mazzo, destro per il suo) e dall'alto, in frazioni dell'area di Arena
LARG_MIN, LARG_MAX = 150, 250     # la larghezza dei pannelli, in pixel a 1080 di altezza: in mezzo quanto chiede il contenuto (13 nov 2026, Autore:
                                  # «ridisegnalo più stretto verso sinistra il mio e verso destra oppo»: era 230-380, a 0,6% dal bordo)
ALTO_MAX = 0.82         # i pannelli non scendono oltre questa frazione di Arena: con piu' carte le righe si stringono
FONDO, FONDO_ALFA = "#08080c", 0.30     # il velo dietro ogni lista (13 nov 2026, Autore: «con sfondo leggerissimo e trasparente»): una finestra a parte,
FONDO_MARGINE = 5                        # semitrasparente, sotto i testi; Tk non sa fare un fondo semitrasparente nella finestra a colore chiave
OGNI = 700              # ms fra un giro e l'altro


def _pref():
    try:
        with open(PREF, encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def preferenza(chi="suo"):
    """«On Arena» di un pannello, «suo» (il suo mazzo, bordo destro di Arena) o «mio» (il tuo, bordo sinistro): acceso di partenza (Autore l'ha chiesto). Il file di
    prima aveva una chiave sola, «acceso», che vale per il suo."""
    d = _pref()
    return bool(d.get(chi, d.get("acceso", True) if chi == "suo" else True))


def acceso():
    """Almeno un pannello acceso: il processo serve."""
    return preferenza("suo") or preferenza("mio")


def imposta(valore, chi="suo"):
    d = _pref()
    d.setdefault("suo", preferenza("suo"))
    d.pop("acceso", None)
    d[chi] = bool(valore)
    try:
        os.makedirs(LOGDIR, exist_ok=True)
        with open(PREF, "w", encoding="utf-8") as f:
            json.dump(d, f)
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
    user32.SetWindowPos.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_uint]
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


def _pct(p):
    return f"{round(100 * p)}%"


def righe(h):
    """Il pannello del suo mazzo, a righe: ("t", testo, stile), ("s", titoletto), ("c", sinistra, carta, destra, stile, spenta). [] se non c'e' niente da mostrare."""
    if not h or h.get("tipo") in (None, "spento") or h.get("finita"):
        return []
    out = []
    if h["tipo"] == "limited":
        cc = h.get("coppie") or []
        if not cc:
            return [("t", "colors unknown yet", "grigio")]
        out.append(("t", f"{cc[0][1]}  {_pct(cc[0][2])}", "titolo"))
        if len(cc) > 1:
            out.append(("t", " · ".join(f"{n} {_pct(p)}" for _k, n, p in cc[1:3]), "grigio"))
        x = h.get("l17")
        if x:
            out.append(("s", "17LANDS"))
            out.append(("t", f"wins {x['wr']}% · play {x['play']}% · draw {x['draw']}%", "testo"))
            if x.get("tu_contro"):
                t = x["tu_contro"]
                out.append(("t", f"{t['coppia']} vs it: {t['wr']}%", "azzurro" if t["wr"] >= 50 else "rosso"))
        ist = h.get("istantanee") or []
        if ist:
            out.append(("s", f"WITH {h.get('aperte', 0)} OPEN"))
            out += [("c", str(cmc), n, f"GIH {g}%" if g else "", "arancio", False) for n, cmc, g in ist[:4]]
    else:
        aa = h.get("archetipi") or []
        if not aa:
            return []
        n, p = aa[0]
        out.append(("t", f"{n}  {_pct(p)}" if p is not None else n, "titolo"))
        if len(aa) > 1 and aa[1][1] is not None:
            out.append(("t", "or " + " · ".join(f"{a} {_pct(q)}" for a, q in aa[1:3] if q is not None), "grigio"))
        pr = h.get("probabili") or []
        if pr:
            out.append(("s", "LIKELY IN ITS 60"))
            out += [("c", f"{q}x" if q else "", a, _pct(q_), "testo", False) for a, q_, q in pr[:8]]
        ist = h.get("istantanee") or []
        if ist:
            out.append(("s", f"WITH {h.get('aperte', 0)} OPEN"))
            out += [("c", str(x[1]), x[0], "seen" if x[3] else _pct(x[2]), "arancio", False) for x in ist[:4]]
    t = (h.get("contro") or {}).get("tutti")
    if t:
        pl, dr = t["play"], t["draw"]
        out.append(("s", "YOU VS IT"))
        out.append(("t", f"{t['vinte']}-{t['perse']} ({t['wr']}%) · play {pl[1]}-{pl[0] - pl[1]} · draw {dr[1]}-{dr[0] - dr[1]}",
                    "grigio" if t["poche"] else ("azzurro" if (t["wr"] or 0) >= 50 else "rosso")))
    return out


def righe_mio(h):
    """Il pannello del tuo mazzo: il nome, il grimorio, poi ogni carta con le copie rimaste su quelle del mazzo e la P di pescarla alla prossima pescata (le
    magie per costo, le terre in fondo; una carta finita resta, spenta), il record del mazzo."""
    if not h or h.get("tipo") in (None, "spento") or h.get("finita") or not h.get("mio"):
        return []
    m = h["mio"]
    out = [("t", m["nome"], "titolo"), ("t", f"{m['grimorio']} cards in library", "grigio"), ("s", "NEXT DRAW")]
    terre = False
    for n, _cmc, rim, tot, p, terra in m.get("lista") or []:
        if terra and not terre:
            out.append(("s", f"LANDS · {m['terre']} left"))
            terre = True
        out.append(("c", f"{rim}/{tot}", n, _pct(p) if rim else "-", "testo", rim == 0))
    r = m.get("record")
    if r:
        out.append(("t", f"Record {r['vinte']}-{r['perse']} ({r['wr']}%)", "grigio" if r["poche"] else ("azzurro" if (r["wr"] or 0) >= 50 else "rosso")))
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
        self._font, self.pannelli = {}, {}
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
        self.fondi = {lato: self._fondo(in_cattura) for lato in ("sinistra", "destra")}
        threading.Thread(target=self._primo, daemon=True).start()

    def _fondo(self, in_cattura):
        """Il velo dietro una lista: una finestra scura semitrasparente, senza bordo, che lascia passare i clic e non prende il fuoco. -> (Toplevel, hwnd)."""
        tk = self.tk
        prima = user32.GetForegroundWindow() if user32 else None
        f = tk.Toplevel(self.root)
        f.withdraw()
        f.overrideredirect(True)
        f.attributes("-topmost", True)
        f.attributes("-alpha", FONDO_ALFA)
        f.configure(bg=FONDO)
        f.geometry("10x10+-3000+0")
        f.update_idletasks()
        h = int(f.wm_frame(), 16)
        if user32:
            st = user32.GetWindowLongW(h, -20)
            user32.SetWindowLongW(h, -20, st | 0x80000 | 0x20 | 0x8000000 | 0x80 | 0x8)
        f.deiconify()
        f.update()
        if user32 and prima and user32.GetForegroundWindow() == h:
            user32.SetForegroundWindow(prima)
        if user32 and not in_cattura:
            user32.SetWindowDisplayAffinity(h, 0x11)
        return f, h

    def metti_fondi(self, area):
        """Ogni velo sotto la sua lista (coi margini), o fuori dallo schermo se la lista non c'e'; poi i testi in cima e i veli subito sotto."""
        self.rett_fondi = {}
        for lato, (f, h) in self.fondi.items():
            p = self.pannelli.get(lato) if area else None
            if p:
                m = FONDO_MARGINE
                x0, y0 = area[0] + p[0] - m, area[1] + p[1] - m
                self.rett_fondi[lato] = (x0, y0, x0 + p[2] - p[0] + 2 * m, y0 + p[3] - p[1] + 2 * m)
                f.geometry(f"{p[2] - p[0] + 2 * m}x{p[3] - p[1] + 2 * m}+{x0}+{y0}")
            else:
                f.geometry("10x10+-3000+0")
        self.root.update_idletasks()    # prima Tk mette le finestre al loro posto: un SetWindowPos con la geometria ancora in attesa gliela fa dimenticare
        # (13 nov 2026: Tk prendeva per buona la posizione vecchia fuori schermo, e il pannello «a vista» restava a x -3000)
        if user32:
            user32.SetWindowPos(self.hwnd, -1, 0, 0, 0, 0, 0x13)        # HWND_TOPMOST, NOMOVE NOSIZE NOACTIVATE
            for _f, h in self.fondi.values():
                user32.SetWindowPos(h, self.hwnd, 0, 0, 0, 0, 0x13)      # subito sotto i testi

    def _primo(self):
        """La prima lettura del log intero, in un filo; poi il pannello puo' gia' comparire. Il record delle tue partite arriva dopo (la prima lettura dei
        log di Arena dopo un aggiornamento puo' durare minuti: fino al 13 nov 2026 il pannello lo aspettava e in quel tempo non compariva)."""
        self.seg.aggiorna()
        self.letto.set()
        self.nota("log read")
        if self.recs is None:
            try:
                self.recs = ML.records()
            except Exception:       # noqa: BLE001 - senza le tue partite l'HUD dice solo il mazzo
                self.recs = []
            self.firma = None       # si rifa' la scheda col record

    def nota(self, cosa):
        """Una riga nel diario del pannello (Log_Arena/hud_arena_diario.txt), solo quando lo stato cambia. Niente nomi ne' id dell'avversario."""
        if cosa == getattr(self, "_ultima", None) or self.area_finta is not None:
            return
        self._ultima = cosa
        try:
            import time
            if os.path.exists(DIARIO) and os.path.getsize(DIARIO) > 1 << 20:
                os.replace(DIARIO, DIARIO + ".1")
            with open(DIARIO, "a", encoding="utf-8") as f:
                f.write(f"{time.strftime('%d/%m %H:%M:%S')} pid {os.getpid()} {cosa}\n")
        except OSError:
            pass

    def da_chiudere(self):
        if self.pid and not _vivo(self.pid):
            return "la finestra grande non c'e' piu'"
        if not self.sempre and not acceso():
            return "On Arena spento in tutti e due i pannelli"
        return None

    def giro(self):
        """Un giro: rilegge la partita, decide quali pannelli si vedono e li ridisegna se sono cambiati. -> (righe del suo, righe del tuo)."""
        if not self.letto.is_set():
            return [], []
        st = self.seg.aggiorna()
        firma = None if st is None else (st["matchId"], tuple(st["sue"]), st["aperte"], st["turno"], st["finita"], st.get("sul_play"),
                                         tuple(sorted((st.get("mie_fuori") or {}).items())), st.get("grimorio"))
        if firma != self.firma:
            if st and st.get("finita") and self.firma and self.firma[4] is False:      # a fine partita le tue partite si rileggono, per il record
                threading.Thread(target=self._rileggi, daemon=True).start()
            self.firma = firma
            self.h = HM.scheda(st, recs=self.recs or [], meta=self.meta) if st else None
        suo = righe(self.h) if self.sempre or preferenza("suo") else []
        mio = righe_mio(self.h) if self.sempre or preferenza("mio") else []
        stato = ("no game" if st is None else "game over" if st.get("finita") else "competitive event: off" if st.get("competitivo")
                 else f"game {self.h.get('tipo') if self.h else '?'}, turn {st.get('turno')}")
        area = self.area_finta
        if area is None:
            h, area = finestra_arena()
            if area is None:
                if suo or mio:
                    stato += ", Arena " + ("minimized" if h else "not found")
                suo = mio = []
            else:       # ogni pannello si vede solo se in quel punto la finestra in cima e' Arena
                W, H = area[2] - area[0], area[3] - area[1]
                if mio and not arena_in_cima(h, area[0] + (POSTO[0] + 0.02) * W, area[1] + (POSTO[1] + 0.02) * H):
                    mio, stato = [], stato + ", left covered"
                if suo and not arena_in_cima(h, area[2] - (POSTO[0] + 0.02) * W, area[1] + (POSTO[1] + 0.02) * H):
                    suo, stato = [], stato + ", right covered"
        self.nota(stato + (f": showing {'yours' if mio else ''}{' + ' if mio and suo else ''}{'theirs' if suo else ''}" if suo or mio else ": hidden"))
        self.disegna(suo, mio, area)
        return suo, mio

    def _rileggi(self):
        try:
            self.recs = ML.records()
            self.firma = None
        except Exception:       # noqa: BLE001
            pass

    def disegna(self, suo, mio, area):
        """La finestra copre Arena (il colore chiave e' trasparente e lascia passare i clic); il tuo mazzo sul bordo sinistro, il suo sul bordo destro."""
        chiave = (tuple(suo), tuple(mio), area)
        if chiave == self.disegnato:
            return
        self.disegnato = chiave
        self.cv.delete("all")
        self.pannelli = {}
        if not area or not (suo or mio):
            self.root.geometry("10x10+-3000+0")
            self.metti_fondi(None)
            return
        W, H = area[2] - area[0], area[3] - area[1]
        s = max(0.6, H / 1080)
        y0 = int(POSTO[1] * H)
        if mio:
            self.pannello("YOUR DECK", mio, "sinistra", W, y0, s, int(ALTO_MAX * H) - y0)
        if suo:
            self.pannello("OPPONENT DECK", suo, "destra", W, y0, s, int(ALTO_MAX * H) - y0)
        self.root.geometry(f"{W}x{H}+{area[0]}+{area[1]}")
        self.metti_fondi(area)      # i veli sotto le liste, e i testi di nuovo in cima alle finestre sempre-sopra

    def font(self, px, grassetto=False):
        """Un font di Tk per misurare e disegnare, ricordato per misura."""
        from tkinter import font as tkfont
        k = (px, grassetto)
        if k not in self._font:
            self._font[k] = tkfont.Font(root=self.root, family="Segoe UI", size=-px, weight="bold" if grassetto else "normal")
        return self._font[k]

    def pannello(self, testa, rr, lato, W, y0, s, alto_max):
        """Un pannello come una tabella di un HUD del poker (Autore, 12 nov 2026: «impaginiamo meglio, holdem manager tiene tutto non tagliato e sulla stessa
        pagina / trova la ux migliore possibile»; prima: «liste con sfondo trasparente carte separate da righe sempre leggere»):
        - tutto sulla stessa pagina: niente «+N more», le righe si stringono quanto serve perche' entri tutto in alto_max (testi mai sotto 10 pixel);
        - niente tagliato e niente a capo nelle carte: tre colonne allineate, copie | carta | %, larghe quanto il contenuto misurato col font vero; il pannello
          e' largo quanto serve (fra LARG_MIN e LARG_MAX), e un nome che non entra rimpicciolisce solo lui;
        - sfondo trasparente, un'ombra scura di un pixel sotto ogni testo, una riga sottile e chiara sotto ogni carta; i nomi normali, i numeri in grassetto.
        lato: «sinistra» (dal bordo sinistro di Arena) o «destra» (dal bordo destro)."""
        cv = self.cv
        alti = {"titolo": 24, "t": 18, "s": 20, "c": 20}
        stima = 18 + sum(alti["titolo"] if r[0] == "t" and r[2] == "titolo" else alti[r[0]] for r in rr)
        k = min(1.0, alto_max / (stima * s))         # tutto sulla stessa pagina
        px = lambda d: max(10, int(d * s * k))      # noqa: E731
        f_nome, f_num, f_t, f_tit, f_sez = (self.font(px(13)), self.font(px(13), True), self.font(px(12), True), self.font(px(17), True),
                                            self.font(px(10), True))
        pad, gap = int(3 * s), int(6 * s)
        carte = [r for r in rr if r[0] == "c"]
        wc = max([f_num.measure(r[1]) for r in carte if r[1]] + [0])
        wp = max([f_num.measure(r[3]) for r in carte if r[3]] + [0])
        wn = max([f_nome.measure(r[2]) for r in carte] + [0])
        wt = max([(f_tit if r[2] == "titolo" else f_t).measure(r[1]) for r in rr if r[0] == "t"] + [f_sez.measure(testa)])
        larg = max(int(LARG_MIN * s), min(int(LARG_MAX * s), max(pad + wc + (gap if wc else 0) + wn + gap + wp + pad, wt + 2 * pad)))
        x0 = int(POSTO[0] * W) if lato == "sinistra" else W - int(POSTO[0] * W) - larg
        xn = x0 + pad + wc + (gap if wc else 0)         # dove comincia il nome
        xp = x0 + larg - pad                            # dove finisce la %
        spazio_n = xp - wp - gap - xn                   # quanto puo' essere largo un nome
        o = 1                                           # l'ombra: un pixel, non impasta il testo

        def scrivi(x, y, testo, font, colore, ancora="nw", larghezza=0):
            cv.create_text(x + o, y + o, text=testo, font=font, fill=OMBRA, anchor=ancora, width=larghezza, tags="ombra")
            return cv.create_text(x, y, text=testo, font=font, fill=colore, anchor=ancora, width=larghezza, tags="riga")
        y = y0
        it = scrivi(x0 + pad, y, testa, f_sez, COL["grigio"])
        y = cv.bbox(it)[3] + int(2 * s * k)
        alto_c = int(alti["c"] * s * k)
        for r in rr:
            if r[0] == "t":
                f = f_tit if r[2] == "titolo" else f_t
                it = scrivi(x0 + pad, y, r[1], f, COL[r[2]], larghezza=larg - 2 * pad)     # una riga di testo puo' andare a capo: lo spazio si conta dal bbox
                y = cv.bbox(it)[3] + int(3 * s * k)
            elif r[0] == "s":
                y += int(6 * s * k)
                it = scrivi(x0 + pad, y, r[1], f_sez, COL["titolo"])
                y = cv.bbox(it)[3] + int(2 * s * k)
                cv.create_line(x0 + pad, y, xp, y, fill=SEPARA, width=1, tags="sep")
            else:
                _t, sx, nome, dx, stile, spenta = r
                cy = y + alto_c // 2
                if sx:
                    scrivi(x0 + pad + wc, cy, sx, f_num, SPENTA if spenta else COL["titolo"], ancora="e")
                fn = f_nome
                while fn.measure(nome) > spazio_n and fn.cget("size") < -10:        # un nome lungo rimpicciolisce lui, non viene tagliato
                    fn = self.font(-fn.cget("size") - 1)
                if fn.measure(nome) > spazio_n:      # neanche a 10 pixel: va a capo dentro la sua colonna, e la riga si allunga (mai tagliato)
                    it = scrivi(xn, y + int(2 * s * k), nome, fn, SPENTA if spenta else COL[stile], larghezza=spazio_n)
                    cy = y + alto_c // 2
                    alto_r = max(alto_c, cv.bbox(it)[3] - y + int(3 * s * k))
                else:
                    scrivi(xn, cy, nome, fn, SPENTA if spenta else COL[stile], ancora="w")
                    alto_r = alto_c
                if dx:
                    p_alta = dx.endswith("%") and dx[:-1].isdigit() and int(dx[:-1]) >= 10
                    scrivi(xp, cy, dx, f_num, SPENTA if spenta else (COL["azzurro"] if p_alta else COL["titolo"]), ancora="e")
                y += alto_r
                cv.create_line(x0 + pad, y, xp, y, fill=SEPARA, width=1, tags="sep")     # la riga fra una carta e l'altra
        cv.tag_raise("riga")
        self.pannelli[lato] = (x0, y0, x0 + larg, y, spazio_n, xn)

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
    connetti = ('{ "greToClientEvent": { "greToClientMessages": [ { "type": "GREMessageType_ConnectResp", "connectResp": { "deckMessage": { "deckCards": [ %s ] } } } ] } }\n'
                % ", ".join(str(g(n)) for n in ["Ethereal Armor"] * 4 + ["Plains"] * 6))
    open(f1, "w", encoding="utf-8").write(connetti + stanza("m1", "Ladder", "Playing") + gs([(5, g("Island"), True), (7, g("Opt"), False), (8, g("Lightning Strike"), False)], 3, 2))
    area = (-3000, 0, -3000 + 1920, 1080)       # un'Arena finta fuori schermo, a 1920x1080
    w = HudArena(file=f1, io=(ME, None), area_finta=area, sempre=True, recs=[], meta=meta, in_cattura=True)
    w.letto.wait(10)
    rr = w.giro(); w.root.update()
    tt = w.testi()
    casi.append(("il suo pannello: archetipo con la P, probabili e istantanee col mana aperto, a lista", "OPPONENT DECK" in tt
                 and any(x.startswith("Izzet Prowess") for x in tt) and "LIKELY IN ITS 60" in tt and "Spell Pierce" in tt and "WITH 1 OPEN" in tt))
    sep = [w.cv.coords(i) for i in w.cv.find_withtag("sep")]
    sx_, dx_ = w.pannelli.get("sinistra"), w.pannelli.get("destra")
    casi.append(("la finestra copre Arena: il tuo mazzo sul bordo sinistro, il suo sul bordo destro", w.root.winfo_width() == 1920 and sx_ and dx_
                 and sx_[0] == int(POSTO[0] * 1920) and dx_[2] == 1920 - int(POSTO[0] * 1920)))
    carte = sum(1 for x in tt if x.endswith("%") or x == "-")
    casi.append(("sfondo trasparente: nessun riquadro; una riga chiara sotto ogni carta, un'ombra sotto ogni testo",
                 not any(w.cv.type(i) == "rectangle" for i in w.cv.find_all()) and len(sep) >= carte and len(w.cv.find_withtag("ombra")) == len(w.cv.find_withtag("riga"))))
    def rett_fondo(lato):
        return w.rett_fondi.get(lato)
    fs, fd = rett_fondo("sinistra"), rett_fondo("destra")
    m = FONDO_MARGINE
    casi.append(("il velo leggero sotto ogni lista, coi margini, e semitrasparente", fs == (area[0] + sx_[0] - m, sx_[1] - m, area[0] + sx_[2] + m, sx_[3] + m)
                 and fd == (area[0] + dx_[0] - m, dx_[1] - m, area[0] + dx_[2] + m, dx_[3] + m)
                 and abs(float(w.fondi["sinistra"][0].attributes("-alpha")) - FONDO_ALFA) < 0.01))
    if user32:
        r_ = wintypes.RECT(); user32.GetWindowRect(ctypes.c_void_p(w.hwnd), ctypes.byref(r_))
        rf = wintypes.RECT(); user32.GetWindowRect(ctypes.c_void_p(w.fondi["sinistra"][1]), ctypes.byref(rf))
        casi.append(("le finestre vere sono davvero dove le mette il disegno (negativa: dopo il SetWindowPos restavano al posto vecchio)",
                     (r_.left, r_.top) == (area[0], area[1]) and (rf.left, rf.top) == fs[:2]))
    casi.append(("piu' strette e attaccate ai bordi: al massimo 250 pixel a 1080, a 4 pixel dal bordo", sx_[2] - sx_[0] <= LARG_MAX and dx_[2] - dx_[0] <= LARG_MAX
                 and sx_[0] <= 4 and 1920 - dx_[2] <= 4))
    sx = min(w.cv.coords(i)[0] for i in w.cv.find_withtag("riga") if w.cv.itemcget(i, "text") == "YOUR DECK")
    casi.append(("il tuo mazzo carta per carta: copie rimaste su quelle del mazzo e la P, le terre in fondo", sx < 960 and "4/4" in tt and "Ethereal Armor" in tt
                 and "40%" in tt and "6/6" in tt and "60%" in tt and tt.index("Ethereal Armor") < tt.index("Plains")))
    casi.append(("negativa: nome e id dell'avversario mai nel pannello", not any("NomeAvversario" in x or "OPPID" in x for x in tt)))
    ex = w.root.tk.call("wm", "attributes", w.root._w, "-topmost")
    casi.append(("sopra le altre finestre, lascia passare i clic e non prende il fuoco", bool(int(ex)) and (user32 is None or (user32.GetWindowLongW(w.hwnd, -20) & 0x8000020) == 0x8000020)))
    casi.append(("niente di nuovo: non si ridisegna", w.disegnato is not None and w.giro() == rr))
    # tutto sulla stessa pagina e niente tagliato: un mazzo con 40 carte diverse e un nome lunghissimo
    lungo = "Questo Nome Di Carta E' Lunghissimo Apposta Per La Prova Dell'Impaginazione"
    righe_tante = [("t", "Big Deck", "titolo"), ("s", "NEXT DRAW")] + [("c", "1/1", f"Card {i}", "2%", "testo", False) for i in range(40)] + [("c", "4/4", lungo, "9%", "testo", False)]
    w.disegnato = None
    w.cv.delete("all")
    w.pannello("YOUR DECK", righe_tante, "sinistra", 1920, int(POSTO[1] * 1080), 1.0, int(ALTO_MAX * 1080) - int(POSTO[1] * 1080))
    tt3 = w.testi()
    fondo = max(w.cv.bbox(i)[3] for i in w.cv.find_withtag("riga"))
    nome_l = next(i for i in w.cv.find_withtag("riga") if w.cv.itemcget(i, "text") == lungo)
    pan = w.pannelli["sinistra"]
    casi.append(("41 carte sulla stessa pagina: nessun «more», tutte dentro l'82% di Arena", not any("more" in x for x in tt3) and all(f"Card {i}" in tt3 for i in range(40))
                 and fondo <= int(ALTO_MAX * 1080)))
    sotto = min((c[1] for c in (w.cv.coords(i) for i in w.cv.find_withtag("sep")) if c[1] > w.cv.bbox(nome_l)[1]), default=0)
    casi.append(("il nome lunghissimo intero dentro la sua colonna, sopra la riga che lo separa (negativa: mai tagliato ne' sovrapposto)",
                 w.cv.bbox(nome_l)[2] <= pan[5] + pan[4] + 2 and w.cv.bbox(nome_l)[3] <= sotto + 1))
    medio = "Brightling of the Starfield"        # un nome lungo vero di Arena e' sotto le 30 lettere
    w.cv.delete("all")
    w.pannello("YOUR DECK", [("c", "1/1", medio, "2%", "testo", False)], "sinistra", 1920, 100, 1.0, 800)
    nm = next(i for i in w.cv.find_withtag("riga") if w.cv.itemcget(i, "text") == medio)
    casi.append(("un nome lungo ma normale sta su una riga, rimpicciolito o col pannello piu' largo", w.cv.itemcget(nm, "width") in ("0", "0.0")))
    w.cv.delete("all")
    w.disegnato = None
    w.giro(); w.root.update()
    pescata = ('{ "transactionId": "g", "greToClientEvent": { "greToClientMessages": [ { "type": "GREMessageType_GameStateMessage", "gameStateMessage": '
               '{ "zones": [ { "zoneId": 31, "type": "ZoneType_Hand", "ownerSeatId": 1, "objectInstanceIds": [ 50 ] }, { "zoneId": 32, "type": "ZoneType_Library", '
               '"ownerSeatId": 1, "objectInstanceIds": [ %s ] } ], "gameObjects": [ { "instanceId": 50, "grpId": %d, "type": "GameObjectType_Card", "zoneId": 31, '
               '"ownerSeatId": 1, "controllerSeatId": 1 } ] } } ] } }\n') % (", ".join(str(60 + i) for i in range(9)), g("Ethereal Armor"))
    with open(f1, "a", encoding="utf-8") as fh:
        fh.write(pescata)
    w.giro(); w.root.update()
    t2 = w.testi()
    casi.append(("hai pescato un Ethereal Armor: 3/4 e 33% (3 su 9 nel grimorio); negativa: 4/4 non c'e' piu'", "3/4" in t2 and "33%" in t2 and "4/4" not in t2))
    vecchio = PREF
    globals()["PREF"] = os.path.join(d, "pref.json")
    w.sempre = False
    imposta(False, "mio")
    w.giro(); w.root.update()
    solo_suo = "YOUR DECK" not in w.testi() and "OPPONENT DECK" in w.testi()
    imposta(True, "mio")
    globals()["PREF"] = vecchio
    w.sempre = True
    casi.append(("spento «mio», resta solo il suo pannello (negativa: il tuo non si disegna)", solo_suo))
    w.pid = os.getpid()
    vivo_padre = w.da_chiudere()
    w.pid = 4 * 10 ** 6 + 7     # un pid che non c'e'
    casi.append(("si chiude quando la finestra che l'ha lanciato non c'e' piu' (negativa: col padre vivo resta)", vivo_padre is None and bool(w.da_chiudere())))
    w.pid = None
    with open(f1, "a", encoding="utf-8") as fh:
        fh.write(stanza("m1", "Ladder", "MatchCompleted"))
    w.giro(); w.root.update()
    casi.append(("negativa: a partita finita i pannelli spariscono, e i veli con loro", w.testi() == [] and w.rett_fondi == {}))
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
        casi.append(("negativa: senza la finestra di Arena il pannello non c'e'", w3.giro() == ([], []) and w3.testi() == []))
        w3.root.destroy()
    vecchio = PREF
    globals()["PREF"] = os.path.join(d, "pref.json")
    os.remove(PREF) if os.path.exists(PREF) else None
    acceso0 = preferenza("suo") and preferenza("mio")
    imposta(False)
    spento = preferenza("suo") is False and preferenza("mio") is True and acceso()
    globals()["PREF"] = vecchio
    casi.append(("«On Arena»: accesi di partenza, il suo si spegne da solo e il processo serve ancora per il tuo", acceso0 and spento))
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
