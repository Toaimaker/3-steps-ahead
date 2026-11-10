"""L'overlay della costruzione: bordi verdi e rossi sulle carte, sopra MTG Arena (3 nov 2026, sessione Magic 07).

Autore, 2 nov 2026: «possiamo evolvere l'app per fare in modo che vada in sovrimpressione al gioco e che evidenzi le
carte da tenere e da scartare per la costruzione del mazzo? In stile Untapped.» Il 17 ott 2026 aveva tolto ogni finestra
in primo piano dal companion; questa e' l'eccezione che ha chiesto (CLAUDE.md, «Le finestre del companion»).

Cosa fa: segue la finestra di Arena, la fotografa ogni 1,5 s (solo pixel: niente memoria del client, niente file suoi,
niente clic), riconosce le carte (riconosci.py), le confronta col mazzo 1 dei proposti (confronto.py) e disegna.
Dal 6 nov 2026 l'OCR da' il primo sguardo e conferma a schermo fermo; quando cambia il contatore «NN/40 Cards» i bordi si rifanno dalle
immagini delle barre (impronte.py), senza OCR, in un filo a parte. Questo e' quel che disegna:
VERDE tieni / aggiungi, ROSSO togli, GIALLO tieni N di M o terre da portare a N, e un riquadro in basso a destra con le
terre da cambiare e le carte del mazzo 1 che non vede. La finestra e' senza bordo, trasparente, sempre sopra, non prende
il fuoco e lascia passare i clic (WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_NOACTIVATE), ed e' esclusa dalle catture
dello schermo (SetWindowDisplayAffinity, WDA_EXCLUDEFROMCAPTURE): la foto che legge non contiene i suoi bordi.
- Disegna solo se Arena e' la finestra in primo piano e la schermata e' quella della costruzione (la barra «NN/40 Cards»
  o almeno 8 barre lette).
- Il companion la lancia a «=== COSTRUZIONE» (companion.py, costruzione); si chiude da sola alla riga di fase successiva
  del diario (CANCELLO, PARTITA, DRAFT, FINE DRAFT) o a «COMPANION ATTIVO», se il companion non c'e' piu', se Arena resta
  chiusa per un minuto, e dopo due ore. Una sola alla volta: la nuova chiude la vecchia (Log_Arena/overlay.pid).
- Limite: con Arena a schermo intero esclusivo una finestra sopra non si vede (Untapped disegna dentro il gioco con
  Overwolf). In finestra o a schermo intero senza bordo si'. Da verificare dal vivo.

    py -I -X utf8 Companion/App/Overlay/overlay.py --campione [IMMAGINE]   i bordi disegnati sul campione -> campioni/*_segnata.png
    py -I -X utf8 Companion/App/Overlay/overlay.py --diario FILE --pid N    dal vivo (lo lancia il companion)
    py -I -X utf8 Companion/App/Overlay/overlay.py --prova-rapido           il filo della lettura rapida, senza finestra e senza Arena
"""
import os, sys
_casa = os.path.dirname(os.path.abspath(__file__))      # si sale fino a percorsi.py, che mette nel sys.path tutte le cartelle del Companion
while not os.path.isfile(os.path.join(_casa, "percorsi.py")):
    _casa = os.path.dirname(_casa)
if _casa not in sys.path:
    sys.path.insert(0, _casa)
import percorsi  # noqa: E402
import ctypes
import datetime
import queue
import re
import threading
import time

QUI = os.path.dirname(os.path.abspath(__file__))
RADICE = percorsi.ROOT
LOGDIR = os.path.join(RADICE, "Log_Arena")

try:        # pixel veri: la foto dello schermo e la finestra parlano la stessa misura anche col ridimensionamento di Windows
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

import numpy as np  # noqa: E402
from PIL import Image, ImageDraw, ImageFont, ImageGrab  # noqa: E402

import confronto as CF  # noqa: E402
import impronte as IM  # noqa: E402
import riconosci as R  # noqa: E402
from ocr import Ocr  # noqa: E402

# i colori della palette CI di Companion/App/finestra.py (17 ott 2026, colori di ArtStation)
_EN = (("Il mazzo a schermo e' il mazzo 1.", "The deck on screen is deck 1."), ("A schermo nel mazzo", "On screen in deck"), ("NON VISTE (scorri il mazzo)", "NOT SEEN (scroll the deck)"),
       ("dall'alto (verdi)", "from the top (green)"), ("(rosse)", "(red)"), ("MAZZO", "DECK"), ("AGGIUNGI", "ADD"), ("TOGLI", "CUT"), ("TIENI", "KEEP"), ("PORTA A", "SET TO"), ("TERRE", "LANDS"),
       ("Aggiungi", "Add"), ("aggiungi", "add"), ("Togli", "Cut"), ("togli", "cut"), ("Tieni", "Keep"), ("tieni", "keep"), ("porta a", "set to"), ("carte", "cards"))


def testo_en(t):
    """Quello che si legge sopra Arena, in inglese (Autore, 4 nov 2026): il confronto resta sulle sue parole."""
    for a, b in _EN:
        t = t.replace(a, b)
    return t


COL = dict(verde="#5cb85c", rosso="#d9534f", giallo="#f0ad4e", fondo="#101014", filo="#303034", testo="#bebec2",
           titolo="#ffffff", azzurro="#24baff")
CHIAVE = "#010203"      # il colore trasparente della finestra
PIDFILE = os.path.join(LOGDIR, "overlay.pid")
OGGI = datetime.date.today().strftime("%Y%m%d")
FILE_LOG = os.path.join(LOGDIR, f"overlay_{OGGI}.txt")
FINE = re.compile(r"=== (CANCELLO|PARTITA|DRAFT|FINE DRAFT)\b|COMPANION ATTIVO")
PASSO_RAPIDO = 0.05     # ogni quanto si guarda il contatore «NN/40 Cards»


def scrivi(r):
    t = datetime.datetime.now().strftime("%H:%M:%S")
    try:
        with open(FILE_LOG, "a", encoding="utf-8") as f:
            f.write(f"{t} {r}\n")
    except OSError:
        pass


# ------------------------------------------------------------------ dove si disegna
def rettangolo(seg, let):
    """Il riquadro di una carta, in pixel della schermata letta."""
    s, b = let["scala"], seg["barra"]
    if seg["zona"] == "fuori":      # la carta intera: il titolo sta 14 px sotto il bordo, la carta e' 233x328 (campione)
        x0, y0 = b["x"] - 16 * s, b["y"] - 14 * s
        return x0, y0, x0 + 233 * s, y0 + 328 * s
    passo = let["passo"]
    stessa = sorted(q["y"] for q in let["mazzo"] if q.get("colonna") == b.get("colonna") and q["y"] > b["y"] + 4 * s)
    alto = min(stessa[0] - b["y"], 2 * passo) if stessa else (2 * passo if b["copie"] > 1 else passo)
    x0, y0 = b["cx"] - 8 * s, b["y"] - 7 * s
    return x0, y0, x0 + 180 * s, y0 + alto - 1 * s


def segni_da_disegnare(let, desc, voluto):
    segni, rie = CF.decidi(let, voluto)
    out = []
    for g in segni:
        x0, y0, x1, y1 = rettangolo(g, let)
        out.append(dict(r=(x0, y0, x1, y1), colore=COL[g["colore"]], etichetta=g["etichetta"].upper(), zona=g["zona"]))
    return out, CF.testo_riepilogo(desc, rie), rie


def riquadro(let, W):
    s = let["scala"]
    return 0.818 * W, let["divisorio"] + 20 * s, 0.976 * W


def _font(dim, grassetto=True):
    for f in (("segoeuib.ttf" if grassetto else "segoeui.ttf"), "arialbd.ttf", "arial.ttf"):
        p = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", f)
        if os.path.exists(p):
            return ImageFont.truetype(p, dim)
    return ImageFont.load_default()


def disegna_pil(img, segni, righe, let):
    """Gli stessi segni dell'overlay, disegnati su una copia della schermata (per il campione e per i collaudi)."""
    out = img.convert("RGB").copy()
    d = ImageDraw.Draw(out)
    s = let["scala"]
    fe = _font(max(10, int(12 * s)))
    for g in segni:
        x0, y0, x1, y1 = g["r"]
        d.rectangle((x0, y0, x1, y1), outline=g["colore"], width=max(2, int(3 * s)))
        tw = d.textlength(g["etichetta"], font=fe)
        if g["zona"] == "fuori":
            tx0, ty0 = x0 + (x1 - x0 - tw) / 2 - 6 * s, y0 - 22 * s
        else:
            tx0, ty0 = x1 - tw - 12 * s, y0 + 1 * s
        d.rectangle((tx0, ty0, tx0 + tw + 10 * s, ty0 + 17 * s), fill=g["colore"])
        d.text((tx0 + 5 * s, ty0 + 1 * s), g["etichetta"], fill="#101014", font=fe)
    bx0, by0, bx1 = riquadro(let, out.width)
    fr, ft = _font(max(10, int(13 * s)), False), _font(max(10, int(13 * s)))
    alto = (len(righe) * 19 + 12) * s
    d.rectangle((bx0, by0, bx1, by0 + alto), fill=COL["fondo"], outline=COL["filo"])
    for i, r in enumerate(righe):
        f = ft if i == 0 else fr
        while d.textlength(r, font=f) > bx1 - bx0 - 14 * s and len(r) > 4:     # la riga lunga si accorcia
            r = r[:-2].rstrip() + "…"
        d.text((bx0 + 8 * s, by0 + (6 + i * 19) * s), r, fill=COL["titolo"] if i == 0 else COL["testo"], font=f)
    return out


# ------------------------------------------------------------------ Arena
user32 = ctypes.windll.user32
user32.FindWindowW.restype = ctypes.c_void_p
user32.GetForegroundWindow.restype = ctypes.c_void_p
user32.FindWindowW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p]
user32.InternalGetWindowText.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_int]
user32.IsWindowVisible.argtypes = user32.IsIconic.argtypes = [ctypes.c_void_p]
user32.WindowFromPoint.restype = user32.GetAncestor.restype = ctypes.c_void_p
user32.GetAncestor.argtypes = [ctypes.c_void_p, ctypes.c_uint]


def finestra_arena():
    """-> (hwnd, (sinistra, alto, destra, basso) dell'area client in pixel dello schermo) o (None, None).
    FindWindow e non EnumWindows + GetWindowText: GetWindowText su una finestra di questo processo manda un messaggio al
    filo di Tk, e dal filo di lavoro si bloccava tutto (3 nov 2026, prima prova dal vivo)."""
    import win32gui
    h = user32.FindWindowW("UnityWndClass", "MTGA") or user32.FindWindowW(None, "MTGA")
    if not h or not user32.IsWindowVisible(h):
        return None, None
    if user32.IsIconic(h):
        return h, None
    l, t, r, b = win32gui.GetClientRect(h)
    x, y = win32gui.ClientToScreen(h, (0, 0))
    return h, (x, y, x + r - l, y + b - t)


def _firma(img):
    """L'impronta dello schermo per vedere se e' cambiato: grigio a un ottavo."""
    return np.asarray(img.convert("L").resize((max(1, img.width // 8), max(1, img.height // 8)))).astype(np.int16)


def sopra_arena(h, area):
    """None se in tre punti di Arena (centro, mazzo, carte fuori) la finestra in cima e' Arena; se no quella finestra."""
    from ctypes import wintypes
    W, H = area[2] - area[0], area[3] - area[1]
    for fx, fy in ((0.5, 0.5), (0.4, 0.85), (0.3, 0.3)):
        p = wintypes.POINT(int(area[0] + fx * W), int(area[1] + fy * H))
        w = user32.WindowFromPoint(p)
        r = user32.GetAncestor(w, 2) if w else None        # GA_ROOT
        if r and r != h:
            return r
    return None


def _titolo(h):
    b = ctypes.create_unicode_buffer(256)
    user32.InternalGetWindowText(h, b, 256)      # senza messaggi alla finestra (vedi finestra_arena)
    return b.value[:40]


def vivo(pid):
    if not pid:
        return True
    h = ctypes.windll.kernel32.OpenProcess(0x1000, False, int(pid))     # PROCESS_QUERY_LIMITED_INFORMATION
    if not h:
        return False
    codice = ctypes.c_ulong()
    ctypes.windll.kernel32.GetExitCodeProcess(h, ctypes.byref(codice))
    ctypes.windll.kernel32.CloseHandle(h)
    return codice.value == 259      # STILL_ACTIVE


# ------------------------------------------------------------------ la finestra
class Overlay:
    def __init__(self, diario=None, pid=None, dopo=None, mazzi=CF.MAZZI_JSON, in_cattura=False, n=1):
        import tkinter as tk
        self.tk = tk
        self.diario, self.pid, self.mazzi, self.n = diario, pid, mazzi, n      # n: il mazzo scelto col pulsante Select deck della finestra
        self.dopo = time.time() if dopo is None else dopo     # 0 = vanno bene anche i mazzi gia' scritti
        self.diario_pos = os.path.getsize(diario) if diario and os.path.exists(diario) else 0
        self.inizio = time.time()
        self.senza_arena = None
        self.coda = queue.Queue()
        self.fermo = threading.Event()
        prima = user32.GetForegroundWindow()
        self.root = tk.Tk()
        self.root.withdraw()        # nascosta finche' non ha gli stili: Tk alla prima comparsa si prende il fuoco
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-transparentcolor", CHIAVE)
        self.root.configure(bg=CHIAVE)
        self.root.geometry("10x10+0+0")
        self.cv = tk.Canvas(self.root, bg=CHIAVE, highlightthickness=0)
        self.cv.pack(fill="both", expand=True)
        self.root.update_idletasks()
        self.hwnd = int(self.root.wm_frame(), 16)
        GWL_EXSTYLE = -20
        st = user32.GetWindowLongW(self.hwnd, GWL_EXSTYLE)
        user32.SetWindowLongW(self.hwnd, GWL_EXSTYLE, st | 0x80000 | 0x20 | 0x8000000 | 0x80 | 0x8)
        # WDA_EXCLUDEFROMCAPTURE (Windows 10 2004+): la foto dello schermo non vede l'overlay. Se non c'e', la finestra si
        # nasconde per un attimo a ogni foto (self.nascondi_per_foto)
        self.root.deiconify()
        self.root.update()
        self.rendi_fuoco(prima)
        # --in-cattura (solo collaudo): la finestra resta nelle foto, per controllare da una foto che si veda sopra Arena
        self.esclusa = False if in_cattura else bool(user32.SetWindowDisplayAffinity(self.hwnd, 0x11))
        self.nascondi_per_foto = not self.esclusa
        scrivi(f"OVERLAY acceso (pid {os.getpid()}, esclusa dalla cattura: {'si' if self.esclusa else 'no'})")
        self.area = None
        self.mostrati = False
        self.I = IM.Impronte()
        self.base, self.ultimo, self.pausa, self.gen = None, None, True, 0
        self.lavoro = threading.Thread(target=self.ciclo, daemon=True)
        self.lavoro.start()
        if self.esclusa:        # senza esclusione dalla cattura i bordi finirebbero nelle foto: resta la lettura lenta
            threading.Thread(target=self.rapido, daemon=True).start()
        self.root.after(30, self.aggiorna)

    def rendi_fuoco(self, prima):
        """Se la finestra si e' presa il fuoco comparendo, lo rende a chi l'aveva (3 nov 2026: all'avvio lo prendeva, e
        con Arena non piu' in primo piano l'overlay non disegnava)."""
        if prima and prima != self.hwnd and user32.GetForegroundWindow() == self.hwnd:
            user32.SetForegroundWindow(prima)
            scrivi(f"OVERLAY: il fuoco torna a «{_titolo(prima)}»")

    # --- il lavoro: foto, lettura, confronto (in un filo a parte, la finestra resta libera)
    def foto(self, area):
        if self.nascondi_per_foto and self.mostrati:
            ev = threading.Event()
            self.coda.put(("nascondi", ev))
            ev.wait(1)
            time.sleep(0.05)
            img = ImageGrab.grab(bbox=area, all_screens=True)
            self.coda.put(("mostra", None))
            return img
        return ImageGrab.grab(bbox=area, all_screens=True)

    def rapido(self):
        """La lettura rapida (impronte.py): il contatore ogni 50 ms, le barre quando cambia. Niente OCR: la conferma la fa ciclo() a schermo fermo."""
        seg = IM.Seguito(self.I)
        while not self.fermo.is_set():
            time.sleep(PASSO_RAPIDO)
            b = self.base
            ge = self.I.geo
            c = ge["let"].get("contatore") if ge else None
            if b is None or self.pausa or not c or not self.I.pronte():
                seg.rif = None
                continue
            try:
                t0 = time.perf_counter()
                a, s = b["area"], ge["s"]
                box = (int(a[0] + c[0] - 4 * s), int(a[1] + c[1] - 3 * s), int(a[0] + c[0] + c[2] + 16 * s), int(a[1] + c[1] + c[3] + 3 * s))
                rit = np.asarray(ImageGrab.grab(bbox=box, all_screens=True).convert("L"))
                esito = seg.passo(b, rit, time.time(), lambda: ImageGrab.grab(bbox=a, all_screens=True), lambda l: segni_da_disegnare(l, b["desc"], b["voluto"]))
                if esito and self.base is b:
                    let, segni, righe, rie = esito
                    self.gen += 1
                    self.base = dict(b, n=rie["nel_mazzo"], firma=IM.impronta_lettura(let))
                    self.ultimo = (a, segni, righe, let)
                    self.coda.put(("disegna", self.ultimo))
                    scrivi(f"OVERLAY rapido in {1000 * (time.perf_counter() - t0):.0f} ms: {len(let['mazzo'])} barre, {rie['nel_mazzo']} carte, togli {sum(q for _, q in rie['togli'])}")
            except Exception as e:
                scrivi(f"OVERLAY rapido, errore: {type(e).__name__}: {e}")
                time.sleep(1)

    def ciclo(self):
        try:
            ocr = Ocr()
        except Exception as e:
            scrivi(f"OVERLAY: OCR di Windows non partito ({e}): mi chiudo")
            self.coda.put(("esci", None))
            return
        _ev, pool = R.pool_dal_log()
        nomi = R.Nomi(pool)
        scrivi(f"OVERLAY: pool dal log {_ev}, {sum(pool.values())} carte; OCR {ocr.lingua}")
        letta, mt_mazzi, ultima_firma, stato = None, None, None, None
        mostrato, coperta = False, None
        while not self.fermo.is_set():
            t0 = time.time()
            if t0 - getattr(self, "battito", 0) > 60:
                self.battito = t0
                scrivi(f"OVERLAY vivo ({stato or 'avvio'})")
            try:
                motivo = self.da_chiudere()
                if motivo:
                    scrivi(f"OVERLAY spento: {motivo}")
                    self.coda.put(("esci", None))
                    break
                h, area = finestra_arena()
                # Arena deve essere davvero davanti: in tre punti dello schermo di Arena la finestra in cima deve essere
                # lei (la nostra non conta, i clic la attraversano). Il 3 nov 2026 guardavo solo la finestra attiva, ma
                # una finestra non attiva puo' coprire Arena e l'overlay le avrebbe disegnato sopra; e con due schermi il
                # fuoco sta spesso sull'altro mentre si guarda Arena.
                coperta_da = sopra_arena(h, area) if area else None
                fg = h if area and coperta_da is None else (coperta_da or user32.GetForegroundWindow())
                if not area or fg != h or area[2] - area[0] < 400:
                    perche = ("Arena non trovata" if not h else "Arena ridotta a icona" if not area else
                              f"Arena coperta da «{_titolo(fg)}»" if fg != h else "finestra di Arena troppo piccola")
                    if perche != stato:
                        scrivi(f"OVERLAY non disegna: {perche}")
                        stato = perche
                    self.pausa = True
                    if mostrato:
                        self.coda.put(("vuoto", area))
                        mostrato = False
                    time.sleep(0.5)     # l'ultima lettura buona resta: al ritorno su Arena, se lo schermo e' uguale, si ridisegna subito
                    continue
                if not os.path.exists(self.mazzi) or os.path.getmtime(self.mazzi) < self.dopo - 5:
                    self.coda.put(("solo_riquadro", (area, ["Aspetto i mazzi proposti…"])))
                    time.sleep(1.0)
                    continue
                if os.path.getmtime(self.mazzi) != mt_mazzi:
                    mt_mazzi = os.path.getmtime(self.mazzi)
                    desc, voluto = CF.mazzo_obiettivo(self.mazzi, self.n)
                    letta = None
                if stato not in ("arena", "altra"):
                    scrivi(f"OVERLAY: Arena davanti {area}, leggo lo schermo")
                    stato = "arena"
                self.pausa = False
                g0 = self.gen
                img = self.foto(area)
                firma = _firma(img)
                if letta is not None and ultima_firma is not None and firma.shape == ultima_firma.shape and                         float(np.abs(firma - ultima_firma).mean()) < 2.0 and area == letta[0]:
                    if not mostrato and self.ultimo:
                        self.coda.put(("disegna", self.ultimo))
                        mostrato = True
                    time.sleep(max(0.2, 1.5 - (time.time() - t0)))
                    continue
                # lo schermo e' cambiato: i bordi vecchi restano finche' la lettura nuova e' pronta (Autore, 3 nov 2026:
                # «a ogni pick lampeggia o si ricarica, possiamo stabilizzare?»). Prima si aspetta che stia fermo: una
                # carta trascinata o ingrandita sotto il mouse non si legge a meta'.
                for _ in range(8):
                    time.sleep(0.35)
                    img2 = self.foto(area)
                    f2 = _firma(img2)
                    fermo = f2.shape == firma.shape and float(np.abs(f2 - firma).mean()) < 1.5
                    img, firma = img2, f2
                    if fermo:
                        break
                let = R.leggi_schermo(img, ocr, nomi)
                ultima_firma = firma
                costruzione = let["divisorio"] != 0.635 * img.height or len(let["mazzo"]) >= 8
                if not costruzione:
                    if stato != "altra":
                        scrivi("OVERLAY non disegna: la schermata non e' quella della costruzione")
                        stato = "altra"
                    self.coda.put(("vuoto", area))
                    mostrato, self.ultimo, self.base = False, None, None
                    letta = (area, None)
                    continue
                segni, righe, rie = segni_da_disegnare(let, desc, voluto)
                # una lettura che non torna col contatore di Arena («NN/40 Cards») ha carte coperte (la carta ingrandita
                # sotto il mouse): non sostituisce quella buona, e si rilegge al giro dopo
                # (due letture coperte uguali di fila si accettano: e' lo schermo com'e', non un passaggio del mouse)
                intera = let.get("contate") is None or abs(rie["nel_mazzo"] - let["contate"]) <= 1
                if not intera and coperta != (rie["nel_mazzo"], let["contate"]):
                    coperta = (rie["nel_mazzo"], let["contate"])
                    ultima_firma = None
                    scrivi(f"OVERLAY lettura coperta ({rie['nel_mazzo']} carte lette su {let['contate']}): tengo i bordi di prima")
                    continue
                coperta = None
                self.I.impara(img, let)
                if self.gen != g0:      # mentre l'OCR leggeva hai cambiato il mazzo: la lettura e' vecchia, serve solo a imparare
                    ultima_firma = None
                    continue
                letta = (area, let)
                self.ultimo = (area, segni, righe, let)
                self.base = dict(area=area, desc=desc, voluto=voluto, n=rie["nel_mazzo"], firma=IM.impronta_lettura(let))
                self.coda.put(("disegna", self.ultimo))
                mostrato = True
                scrivi(f"OVERLAY letto in {let['secondi']} s: {len(let['mazzo'])} barre ({rie['nel_mazzo']} carte su "
                       f"{let.get('contate')}) nel mazzo, "
                       f"{len(let['fuori'])} fuori; aggiungi {len(rie['aggiungi'])}, togli {sum(q for _, q in rie['togli'])}, "
                       f"terre {rie['terre']}, non viste {rie['non_viste']}")
            except Exception as e:
                scrivi(f"OVERLAY errore: {type(e).__name__}: {e}")
                time.sleep(2)
        ocr.chiudi()

    def da_chiudere(self):
        if time.time() - self.inizio > 2 * 3600:
            return "due ore passate"
        if not vivo(self.pid):
            return "il companion non c'e' piu'"
        if self.diario and os.path.exists(self.diario):
            n = os.path.getsize(self.diario)
            if n > self.diario_pos:
                with open(self.diario, encoding="utf-8", errors="ignore") as f:
                    f.seek(self.diario_pos)
                    nuovo = f.read()
                self.diario_pos = n
                m = FINE.search(nuovo)
                if m:
                    return f"riga del diario «{m.group(0)}»"
        h, area = finestra_arena()
        if not h:
            self.senza_arena = self.senza_arena or time.time()
            if time.time() - self.senza_arena > 60:
                return "Arena chiusa da un minuto"
        else:
            self.senza_arena = None
        return None

    # --- la finestra (filo principale)
    def posiziona(self, area):
        if area and area != self.area:
            self.area = area
            self.root.geometry(f"{area[2] - area[0]}x{area[3] - area[1]}+{area[0]}+{area[1]}")

    def aggiorna(self):
        try:
            while True:
                cosa, dati = self.coda.get_nowait()
                if cosa == "esci":
                    self.fermo.set()
                    self.root.destroy()
                    return
                if cosa == "nascondi":
                    self.root.withdraw()
                    self.root.update_idletasks()
                    dati.set()
                elif cosa == "mostra":
                    prima = user32.GetForegroundWindow()
                    self.root.deiconify()
                    self.rendi_fuoco(prima)
                    self.root.attributes("-topmost", True)
                elif cosa == "vuoto":
                    if self.mostrati:
                        self.cv.delete("all")
                    self.mostrati = False
                elif cosa == "solo_riquadro":
                    area, righe = dati
                    self.posiziona(area)
                    self.cv.delete("all")
                    self.disegna_riquadro(righe, area[2] - area[0], area[3] - area[1], (area[3] - area[1]) / 1080, None)
                    self.mostrati = True
                elif cosa == "disegna":
                    area, segni, righe, let = dati
                    impronta = (area, tuple((tuple(round(v) for v in g["r"]), g["colore"], g["etichetta"]) for g in segni),
                                tuple(righe))
                    if impronta != getattr(self, "impronta", None) or not self.mostrati:
                        self.impronta = impronta
                        self.posiziona(area)
                        self.cv.delete("all")
                        self.disegna(segni, righe, let, area[2] - area[0])
                    self.mostrati = True
        except queue.Empty:
            pass
        self.root.after(30, self.aggiorna)

    def disegna(self, segni, righe, let, W):
        s = let["scala"]
        fe = ("Segoe UI", -max(10, int(12 * s)), "bold")
        for g in segni:
            x0, y0, x1, y1 = g["r"]
            self.cv.create_rectangle(x0, y0, x1, y1, outline=g["colore"], width=max(2, int(3 * s)))
            t = self.cv.create_text(0, 0, text=testo_en(g["etichetta"]), font=fe, anchor="nw", fill="#101014")
            bx = self.cv.bbox(t)
            tw = bx[2] - bx[0]
            if g["zona"] == "fuori":
                tx0, ty0 = x0 + (x1 - x0 - tw) / 2 - 6 * s, y0 - 22 * s
            else:
                tx0, ty0 = x1 - tw - 12 * s, y0 + 1 * s
            fondo = self.cv.create_rectangle(tx0, ty0, tx0 + tw + 10 * s, ty0 + 17 * s, fill=g["colore"], outline=g["colore"])
            self.cv.coords(t, tx0 + 5 * s, ty0)
            self.cv.tag_raise(t, fondo)
        self.disegna_riquadro(righe, W, None, s, let)

    def disegna_riquadro(self, righe, W, H, s, let):
        if let is not None:
            bx0, by0, bx1 = riquadro(let, W)
        else:
            bx0, by0, bx1 = 0.818 * W, 0.65 * H, 0.976 * W
        alto = (len(righe) * 19 + 12) * s
        self.cv.create_rectangle(bx0, by0, bx1, by0 + alto, fill=COL["fondo"], outline=COL["filo"])
        for i, r in enumerate(righe):
            self.cv.create_text(bx0 + 8 * s, by0 + (6 + i * 19) * s, text=testo_en(r), anchor="nw",
                                fill=COL["titolo"] if i == 0 else COL["testo"],
                                font=("Segoe UI", -max(10, int(13 * s)), "bold" if i == 0 else "normal"))

    def vai(self):
        self.root.mainloop()
        self.fermo.set()


def una_sola():
    """La nuova chiude la vecchia: un overlay alla volta."""
    try:
        vecchio = int(open(PIDFILE).read().strip())
        if vecchio != os.getpid() and vivo(vecchio):
            h = ctypes.windll.kernel32.OpenProcess(0x0001, False, vecchio)     # PROCESS_TERMINATE
            if h:
                ctypes.windll.kernel32.TerminateProcess(h, 0)
                ctypes.windll.kernel32.CloseHandle(h)
                scrivi(f"OVERLAY: chiuso il vecchio (pid {vecchio})")
    except (OSError, ValueError):
        pass
    try:
        open(PIDFILE, "w").write(str(os.getpid()))
    except OSError:
        pass


def campione(f=None):
    f = f or R.CAMPIONE
    mj = os.path.join(QUI, "campioni", "mazzi_costruzione_20261102_2354.json")
    desc, voluto = CF.mazzo_obiettivo(mj if os.path.exists(mj) else CF.MAZZI_JSON)
    import confronto
    pool = confronto.pool_campione() if f == R.CAMPIONE else R.pool_dal_log()[1]      # il campione col suo pool, non con l'ultimo draft del log (7 nov 2026)
    img = Image.open(f)
    with Ocr() as o:
        let = R.leggi_schermo(img, o, R.Nomi(pool))
    segni, righe, rie = segni_da_disegnare(let, desc, voluto)
    out = disegna_pil(img, segni, righe, let)
    dest = os.path.splitext(f)[0] + "_segnata.png"
    out.save(dest)
    print(f"{len(segni)} segni ({let['secondi']} s di lettura) -> {dest}")
    for r in righe:
        print("  " + r)


def prova_rapido():
    """Il filo rapido dall'inizio alla fine, senza finestra e senza Arena: le foto vengono dal campione. Il mouse sopra una carta non deve cambiare niente; una carta tolta
    deve arrivare in coda da disegnare, col tempo misurato dal cambio del contatore."""
    global ImageGrab
    img = Image.open(R.CAMPIONE).convert("RGB")
    mj = os.path.join(QUI, "campioni", "mazzi_costruzione_20261102_2354.json")
    desc, voluto = CF.mazzo_obiettivo(mj)
    with Ocr() as o:
        let = R.leggi_schermo(img, o, R.Nomi(list(voluto) + ["Gallia, Tragic Host", "Void Extrapolator"]))
    ov = Overlay.__new__(Overlay)
    ov.fermo, ov.coda, ov.I, ov.gen, ov.ultimo, ov.pausa = threading.Event(), queue.Queue(), IM.Impronte(), 0, None, False
    ov.I.impara(img, let)
    segni, righe, rie = segni_da_disegnare(let, desc, voluto)
    area = (0, 0) + img.size
    ov.base = dict(area=area, desc=desc, voluto=voluto, n=rie["nel_mazzo"], firma=IM.impronta_lettura(let))
    finta = IM.togli_barra(img, let, "Gallia, Tragic Host")
    c = let["contatore"]
    np_f = np.array(finta); np_f[int(c[1]):int(c[1] + c[3]), int(c[0]):int(c[0] + c[2])] = 200      # il contatore cambia
    tolta = Image.fromarray(np_f)
    mouse = np.array(img); mouse[700:900, 320:480] = 90     # la carta ingrandita sotto il mouse: lo schermo cambia, il contatore no
    sul_mouse = Image.fromarray(mouse)
    stato = dict(foto=img)

    class Finto:
        @staticmethod
        def grab(bbox=None, all_screens=True):
            return stato["foto"].crop(bbox)
    vero, ImageGrab = ImageGrab, Finto
    try:
        filo = threading.Thread(target=ov.rapido, daemon=True); filo.start()
        time.sleep(0.2)
        stato["foto"] = sul_mouse
        time.sleep(0.4)
        mouse_ok = ov.coda.empty() and ov.gen == 0
        t0 = time.perf_counter()
        stato["foto"] = tolta
        fine = time.perf_counter() + 2
        while ov.coda.empty() and time.perf_counter() < fine:
            time.sleep(0.005)
        ms = 1000 * (time.perf_counter() - t0)
        arrivo = not ov.coda.empty()
        ok_nomi = False
        if arrivo:
            _c, (_a, sg, _r, le) = ov.coda.get()
            ok_nomi = "Gallia, Tragic Host" not in {b["nome"] for b in le["mazzo"]} and ov.base["n"] == rie["nel_mazzo"] - 1
    finally:
        ov.fermo.set(); ImageGrab = vero
    casi = [("il mouse sopra una carta non ridisegna", mouse_ok), ("la carta tolta arriva da disegnare", arrivo), ("tolta la carta giusta, una in meno", ok_nomi), ("in meno di 300 ms", ms < 300)]
    print(f"  dal cambio del contatore alla coda: {ms:.0f} ms (lo schermo finto non costa i 50 ms della foto)")
    for n, v in casi:
        print(("  ok   " if v else "  ROSSO ") + n)
    print(f"{sum(1 for _, v in casi if v)}/{len(casi)}")
    return 0 if all(v for _, v in casi) else 1


def main():
    a = sys.argv[1:]
    if "--prova-rapido" in a:
        sys.exit(prova_rapido())

    def arg(nome, default=None):
        return a[a.index(nome) + 1] if nome in a and a.index(nome) + 1 < len(a) else default
    if "--campione" in a:
        resto = [x for x in a if not x.startswith("--")]
        campione(resto[0] if resto else None)
        return
    una_sola()
    try:
        Overlay(diario=arg("--diario"), pid=arg("--pid"), dopo=float(arg("--dopo", time.time())),
                in_cattura="--in-cattura" in a, n=int(arg("--mazzo", 1)), mazzi=arg("--mazzi", CF.MAZZI_JSON)).vai()
    finally:
        try:
            if int(open(PIDFILE).read().strip()) == os.getpid():
                os.remove(PIDFILE)
        except (OSError, ValueError):
            pass
        scrivi("OVERLAY chiuso")


if __name__ == "__main__":
    main()
