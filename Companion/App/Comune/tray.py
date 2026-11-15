"""L'icona nella barra di sistema (tray, «Mostra icone nascoste» di Windows): chiusa la finestra l'app resta accesa (15 nov 2026, Autore: «quella funzione
che quando lanci un app e poi la chiudi lei continua ad andare in mostra icone nascoste»).

Senza dipendenze nuove: le API di Windows (Shell_NotifyIcon) con ctypes, in un filo con la sua finestra nascosta e il suo ciclo di messaggi. Il filo non
tocca Tk: mette in una coda i comandi («mostra», «esci», «nel_tray») e li legge la finestra grande dal suo ciclo (`Finestra._tray_giro`).

- clic sull'icona: la finestra torna (se era nascosta, la porta davanti); tasto destro: il menu (Open, «Close button keeps it running», Quit);
- la preferenza «la X nasconde la finestra» sta in Log_Arena/tray.json (di partenza accesa), con «avvisato»: la prima volta che la X nasconde la finestra
  un fumetto dice dov'e' finita;
- Explorer che riparte (TaskbarCreated) rimette l'icona; Mac e Linux: nessuna icona (`avvia()` da' False) e la X chiude come prima.

    py -I -X utf8 Companion/App/Comune/tray.py --prova
"""
import os
import sys
_casa = os.path.dirname(os.path.abspath(__file__))      # si sale fino a percorsi.py, che mette nel sys.path tutte le cartelle del Companion
while not os.path.isfile(os.path.join(_casa, "percorsi.py")):
    _casa = os.path.dirname(_casa)
if _casa not in sys.path:
    sys.path.insert(0, _casa)
import percorsi  # noqa: E402,F401
import piattaforma  # noqa: E402
import json  # noqa: E402
import queue  # noqa: E402
import threading  # noqa: E402

WINDOWS = piattaforma.WINDOWS
PREF = [None]       # il percorso del file: None finche' non serve, poi Log_Arena/tray.json (le prove lo cambiano)


def preferenza_file():
    """Il file delle preferenze (Log_Arena/tray.json); ambiente si importa solo qui, cosi' le prove lo cambiano senza importarlo."""
    if PREF[0] is None:
        from ambiente import LOGDIR
        PREF[0] = os.path.join(LOGDIR, "tray.json")
    return PREF[0]


def leggi():
    try:
        d = json.load(open(preferenza_file(), encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def scrivi(**campi):
    d = leggi()
    d.update(campi)
    try:
        os.makedirs(os.path.dirname(preferenza_file()), exist_ok=True)
        tmp = preferenza_file() + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(d, f)
        os.replace(tmp, preferenza_file())
    except OSError:
        pass


def nel_tray():
    """La X nasconde la finestra invece di chiudere l'app? Di partenza si'."""
    return bool(leggi().get("nel_tray", True))


# ------------------------------------------------------------------ Windows
if WINDOWS:
    import ctypes
    from ctypes import wintypes as W

    WM_USER, WM_NULL, WM_DESTROY, WM_CLOSE = 0x0400, 0x0000, 0x0002, 0x0010
    WM_TRAY = WM_USER + 20
    WM_LBUTTONUP, WM_LBUTTONDBLCLK, WM_RBUTTONUP = 0x0202, 0x0203, 0x0205
    NIM_ADD, NIM_MODIFY, NIM_DELETE = 0, 1, 2
    NIF_MESSAGE, NIF_ICON, NIF_TIP, NIF_INFO = 0x1, 0x2, 0x4, 0x10
    NIIF_INFO = 0x1
    MF_STRING, MF_CHECKED, MF_SEPARATOR = 0x0, 0x8, 0x800
    TPM_RIGHTBUTTON, TPM_BOTTOMALIGN, TPM_RETURNCMD = 0x2, 0x20, 0x100
    HWND_MESSAGE = -3
    IMAGE_ICON, LR_LOADFROMFILE = 1, 0x10
    SM_CXSMICON = 49
    IDI_APPLICATION = 32512
    LRESULT = ctypes.c_ssize_t
    WNDPROC = ctypes.WINFUNCTYPE(LRESULT, W.HWND, W.UINT, W.WPARAM, W.LPARAM)

    class NOTIFYICONDATAW(ctypes.Structure):
        _fields_ = [("cbSize", W.DWORD), ("hWnd", W.HWND), ("uID", W.UINT), ("uFlags", W.UINT), ("uCallbackMessage", W.UINT), ("hIcon", W.HICON),
                    ("szTip", W.WCHAR * 128), ("dwState", W.DWORD), ("dwStateMask", W.DWORD), ("szInfo", W.WCHAR * 256), ("uTimeout", W.UINT),
                    ("szInfoTitle", W.WCHAR * 64), ("dwInfoFlags", W.DWORD), ("guidItem", ctypes.c_byte * 16), ("hBalloonIcon", W.HICON)]

    class WNDCLASSW(ctypes.Structure):
        _fields_ = [("style", W.UINT), ("lpfnWndProc", WNDPROC), ("cbClsExtra", ctypes.c_int), ("cbWndExtra", ctypes.c_int), ("hInstance", W.HINSTANCE),
                    ("hIcon", W.HICON), ("hCursor", W.HANDLE), ("hbrBackground", W.HBRUSH), ("lpszMenuName", W.LPCWSTR), ("lpszClassName", W.LPCWSTR)]

    def _api():
        """Le DLL con le loro firme, tutte nostre: pyglet (il Board) mette i suoi argtypes su ctypes.windll.user32, e qui non devono incrociarsi."""
        u = ctypes.WinDLL("user32", use_last_error=True)
        s = ctypes.WinDLL("shell32", use_last_error=True)
        k = ctypes.WinDLL("kernel32", use_last_error=True)
        u.DefWindowProcW.argtypes, u.DefWindowProcW.restype = [W.HWND, W.UINT, W.WPARAM, W.LPARAM], LRESULT
        u.RegisterClassW.argtypes, u.RegisterClassW.restype = [ctypes.POINTER(WNDCLASSW)], W.ATOM
        u.UnregisterClassW.argtypes, u.UnregisterClassW.restype = [W.LPCWSTR, W.HINSTANCE], W.BOOL
        u.CreateWindowExW.argtypes = [W.DWORD, W.LPCWSTR, W.LPCWSTR, W.DWORD, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, W.HWND, W.HMENU,
                                      W.HINSTANCE, W.LPVOID]
        u.CreateWindowExW.restype = W.HWND
        u.DestroyWindow.argtypes, u.DestroyWindow.restype = [W.HWND], W.BOOL
        u.GetMessageW.argtypes, u.GetMessageW.restype = [ctypes.POINTER(W.MSG), W.HWND, W.UINT, W.UINT], ctypes.c_int
        u.TranslateMessage.argtypes = [ctypes.POINTER(W.MSG)]
        u.DispatchMessageW.argtypes, u.DispatchMessageW.restype = [ctypes.POINTER(W.MSG)], LRESULT
        u.PostMessageW.argtypes, u.PostMessageW.restype = [W.HWND, W.UINT, W.WPARAM, W.LPARAM], W.BOOL
        u.PostQuitMessage.argtypes = [ctypes.c_int]
        u.RegisterWindowMessageW.argtypes, u.RegisterWindowMessageW.restype = [W.LPCWSTR], W.UINT
        u.LoadImageW.argtypes, u.LoadImageW.restype = [W.HINSTANCE, W.LPCWSTR, W.UINT, ctypes.c_int, ctypes.c_int, W.UINT], W.HANDLE
        u.LoadIconW.argtypes, u.LoadIconW.restype = [W.HINSTANCE, ctypes.c_void_p], W.HICON
        u.DestroyIcon.argtypes = [W.HICON]
        u.GetSystemMetrics.argtypes, u.GetSystemMetrics.restype = [ctypes.c_int], ctypes.c_int
        u.CreatePopupMenu.restype = W.HMENU
        u.AppendMenuW.argtypes, u.AppendMenuW.restype = [W.HMENU, W.UINT, ctypes.c_size_t, W.LPCWSTR], W.BOOL
        u.DestroyMenu.argtypes = [W.HMENU]
        u.GetCursorPos.argtypes = [ctypes.POINTER(W.POINT)]
        u.SetForegroundWindow.argtypes = [W.HWND]
        u.TrackPopupMenu.argtypes, u.TrackPopupMenu.restype = [W.HMENU, W.UINT, ctypes.c_int, ctypes.c_int, ctypes.c_int, W.HWND, ctypes.c_void_p], W.BOOL
        s.Shell_NotifyIconW.argtypes, s.Shell_NotifyIconW.restype = [W.DWORD, ctypes.POINTER(NOTIFYICONDATAW)], W.BOOL
        k.GetModuleHandleW.argtypes, k.GetModuleHandleW.restype = [W.LPCWSTR], W.HMODULE
        return u, s, k


class Tray:
    """L'icona. `Tray(ico, nome).avvia()` -> True se c'e'; poi `eventi` (una coda di stringhe) la legge chi guida la finestra; `chiudi()` la toglie.
    Il menu si rifa' a ogni tasto destro con la preferenza di adesso (`nel_tray()`)."""

    def __init__(self, ico, nome, preferenza=nel_tray):
        self.ico, self.nome, self.preferenza = ico, nome, preferenza
        self.eventi = queue.Queue()
        self.hwnd = None
        self._pronto = threading.Event()
        self._ok = False
        self._filo = None
        self._classe = "TreStepsAhead_Tray_%d" % os.getpid()

    # -- ciclo di messaggi, nel suo filo
    def avvia(self, attesa=4.0):
        if not WINDOWS:
            return False
        self._filo = threading.Thread(target=self._ciclo, daemon=True, name="tray")
        self._filo.start()
        self._pronto.wait(attesa)
        return self._ok

    def _icona(self):
        u = self._u
        if self.ico and os.path.isfile(self.ico):
            lato = u.GetSystemMetrics(SM_CXSMICON) or 16
            h = u.LoadImageW(None, self.ico, IMAGE_ICON, lato, lato, LR_LOADFROMFILE)
            if h:
                self._propria = True
                return h
        self._propria = False
        return u.LoadIconW(None, ctypes.c_void_p(IDI_APPLICATION))

    def _dati(self, bandiere):
        d = NOTIFYICONDATAW()
        d.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
        d.hWnd, d.uID, d.uFlags, d.uCallbackMessage, d.hIcon = self.hwnd, 1, bandiere, WM_TRAY, self._hicon
        d.szTip = self.nome[:127]
        return d

    def _aggiungi(self):
        return bool(self._s.Shell_NotifyIconW(NIM_ADD, ctypes.byref(self._dati(NIF_MESSAGE | NIF_ICON | NIF_TIP))))

    def _ciclo(self):
        try:
            u, s, k = _api()
            self._u, self._s, self._k = u, s, k
            self._hicon = self._icona()
            self._riavvio = u.RegisterWindowMessageW("TaskbarCreated")
            self._wp = WNDPROC(self._proc)                  # tenuta in vita: se Python la raccoglie, Windows chiama il vuoto
            classe = WNDCLASSW()
            classe.lpfnWndProc, classe.hInstance, classe.lpszClassName = self._wp, k.GetModuleHandleW(None), self._classe
            if not u.RegisterClassW(ctypes.byref(classe)):
                return
            self.hwnd = u.CreateWindowExW(0, self._classe, self.nome, 0, 0, 0, 0, 0, HWND_MESSAGE, None, classe.hInstance, None)
            if not self.hwnd:
                return
            self._ok = self._aggiungi()
        except Exception as e:      # noqa: BLE001 - senza icona l'app funziona come prima
            print("tray:", type(e).__name__, e)
            self._ok = False
        finally:
            self._pronto.set()
        if not self._ok:
            self._smonta()
            return
        msg = W.MSG()
        while u.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            u.TranslateMessage(ctypes.byref(msg))
            u.DispatchMessageW(ctypes.byref(msg))
        self._smonta()

    def _smonta(self):
        u = self._u
        try:
            if self.hwnd:
                self._s.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(self._dati(NIF_MESSAGE)))
                u.DestroyWindow(self.hwnd)
                self.hwnd = None
            u.UnregisterClassW(self._classe, self._k.GetModuleHandleW(None))
            if getattr(self, "_propria", False) and self._hicon:
                u.DestroyIcon(self._hicon)
        except Exception as e:      # noqa: BLE001
            print("tray:", type(e).__name__, e)

    def _proc(self, hwnd, msg, wp, lp):
        try:
            if msg == WM_TRAY:
                mouse = lp & 0xFFFF
                if mouse in (WM_LBUTTONUP, WM_LBUTTONDBLCLK):
                    self.eventi.put("mostra")
                elif mouse == WM_RBUTTONUP:
                    self._menu(hwnd)
                return 0
            if msg == self._riavvio:                       # Explorer e' ripartito: le icone sono sparite, si rimette
                self._aggiungi()
                return 0
            if msg == WM_CLOSE:
                self._u.DestroyWindow(hwnd)
                return 0
            if msg == WM_DESTROY:
                self._u.PostQuitMessage(0)
                return 0
        except Exception as e:      # noqa: BLE001 - mai un'eccezione dentro il ciclo di Windows
            print("tray:", type(e).__name__, e)
        return self._u.DefWindowProcW(hwnd, msg, wp, lp)

    def _menu(self, hwnd):
        u = self._u
        m = u.CreatePopupMenu()
        u.AppendMenuW(m, MF_STRING, 1, "Open " + self.nome)
        u.AppendMenuW(m, MF_STRING | (MF_CHECKED if self.preferenza() else 0), 2, "Close button keeps it running here")
        u.AppendMenuW(m, MF_SEPARATOR, 0, None)
        u.AppendMenuW(m, MF_STRING, 3, "Quit")
        p = W.POINT()
        u.GetCursorPos(ctypes.byref(p))
        u.SetForegroundWindow(hwnd)                        # se no il menu non si chiude con un clic fuori
        scelta = u.TrackPopupMenu(m, TPM_RETURNCMD | TPM_RIGHTBUTTON | TPM_BOTTOMALIGN, p.x, p.y, 0, hwnd, None)
        u.PostMessageW(hwnd, WM_NULL, 0, 0)
        u.DestroyMenu(m)
        self.comando(scelta)

    def comando(self, scelta):
        """Il comando scelto nel menu -> la coda (e la preferenza). Separato dal menu per poterlo provare senza un clic vero."""
        if scelta == 1:
            self.eventi.put("mostra")
        elif scelta == 2:
            scrivi(nel_tray=not self.preferenza())
            self.eventi.put("nel_tray")
        elif scelta == 3:
            self.eventi.put("esci")

    # -- dalla finestra grande (qualunque filo: Shell_NotifyIcon va bene da tutti)
    def avviso(self, titolo, testo):
        """Il fumetto vicino all'icona."""
        if not self._ok or not self.hwnd:
            return
        d = self._dati(NIF_INFO)
        d.szInfoTitle, d.szInfo, d.dwInfoFlags = titolo[:63], testo[:255], NIIF_INFO
        self._s.Shell_NotifyIconW(NIM_MODIFY, ctypes.byref(d))

    def chiudi(self):
        if self._ok and self.hwnd:
            self._u.PostMessageW(self.hwnd, WM_CLOSE, 0, 0)
            if self._filo is not None:
                self._filo.join(2.0)
        self._ok = False


# ------------------------------------------------------------------ prova
def prova():
    import tempfile
    import time
    ok = fallite = 0

    def verifica(nome, cond):
        nonlocal ok, fallite
        print(("ok    " if cond else "ROSSO ") + nome)
        ok, fallite = ok + bool(cond), fallite + (not cond)

    vecchio = PREF[0]
    with tempfile.TemporaryDirectory() as d:
        PREF[0] = os.path.join(d, "tray.json")
        verifica("di partenza la X nasconde la finestra", nel_tray() is True)
        scrivi(nel_tray=False)
        verifica("la preferenza si salva e si rilegge", nel_tray() is False and leggi() == {"nel_tray": False})
        scrivi(avvisato=True)
        verifica("scrivere un altro campo non perde il primo", leggi() == {"nel_tray": False, "avvisato": True})
        open(PREF[0], "w").write("{rotto")
        verifica("un file rotto vale la preferenza di partenza", nel_tray() is True and leggi() == {})
        scrivi(nel_tray=True)

        if WINDOWS:
            ico = os.path.join(percorsi.ROOT, "Companion", "Grafica", "companion.ico")
            t = Tray(ico, "3 Steps Ahead (prova)")
            verifica("l'icona nasce (Shell_NotifyIcon ADD)", t.avvia() is True and bool(t.hwnd))
            # il clic sull'icona e il doppio clic: la finestra deve tornare
            t._u.PostMessageW(t.hwnd, WM_TRAY, 1, WM_LBUTTONUP)
            t._u.PostMessageW(t.hwnd, WM_TRAY, 1, WM_LBUTTONDBLCLK)
            tempo = time.time()
            visti = []
            while len(visti) < 2 and time.time() - tempo < 3:
                try:
                    visti.append(t.eventi.get(timeout=0.2))
                except queue.Empty:
                    pass
            verifica("clic e doppio clic sull'icona -> «mostra»", visti == ["mostra", "mostra"])
            # il tasto destro apre il menu: non si prova col clic (fermerebbe la prova su un menu); i comandi si
            t.comando(1); t.comando(3)
            verifica("Open e Quit del menu -> «mostra» e «esci»", [t.eventi.get_nowait(), t.eventi.get_nowait()] == ["mostra", "esci"])
            t.comando(2)
            verifica("«Close button keeps it running» gira la preferenza e lo dice", nel_tray() is False and t.eventi.get_nowait() == "nel_tray")
            t.comando(2)
            verifica("e di nuovo la rigira", nel_tray() is True and t.eventi.get_nowait() == "nel_tray")
            t.comando(99)
            verifica("un comando che non c'e' non fa niente", t.eventi.empty())
            t.avviso("prova", "fumetto")
            hwnd = t.hwnd
            t.chiudi()
            tempo = time.time()
            while t._filo.is_alive() and time.time() - tempo < 3:
                time.sleep(0.05)
            verifica("chiudi() toglie l'icona e ferma il filo", not t._filo.is_alive() and t.hwnd is None)
            d_ = NOTIFYICONDATAW()
            d_.cbSize, d_.hWnd, d_.uID, d_.uFlags = ctypes.sizeof(NOTIFYICONDATAW), hwnd, 1, NIF_TIP
            verifica("l'icona non c'e' piu' (MODIFY risponde no)", not t._s.Shell_NotifyIconW(NIM_MODIFY, ctypes.byref(d_)))
            # senza il .ico l'icona di sistema, senza fermarsi
            t2 = Tray(os.path.join(d, "non_c_e.ico"), "3 Steps Ahead (prova 2)")
            verifica("senza il file .ico l'icona nasce lo stesso", t2.avvia() is True)
            t2.chiudi()
            # le negative: dove non e' Windows non c'e' icona e la X chiude come prima
            globals()["WINDOWS"] = False
            try:
                verifica("negativa: fuori da Windows `avvia()` da' False", Tray("x.ico", "x").avvia() is False)
            finally:
                globals()["WINDOWS"] = True
    PREF[0] = vecchio
    print(f"\n{ok}/{ok + fallite}")
    return 0 if not fallite else 1


if __name__ == "__main__":
    if "--prova" in sys.argv:
        sys.exit(prova())
    print(__doc__)
