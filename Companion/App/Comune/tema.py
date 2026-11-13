"""I colori e i font: la palette della chat (C) e quella dell'interfaccia nei colori di ArtStation (CI), i colori dei grafici e delle leghe, la barra scura di Windows."""
import os

from ambiente import ASSET


# palette  scuro
C = dict(fondo="#101015", scheda="#17171f", cap="#1a1d25", testa="#141820", filo="#2c3240", filo2="#252a35",
         titolo="#E2E4E9", testo="#ECEAE7", grigio="#9A9794", muto="#7c776f", acciaio="#6FA8D8",
         arancio="#ff5b1f", verde="#1FB877", verde_t="#7fe3b0", rosso="#e5533d", rosso_t="#ff9a8a",
         azzurro="#33BFFF", azzurro_s="#06212E", led="#39FF7A", traccia="#22252e", evidenza="#21222c")
# L'interfaccia (testata, schede, colonna destra, finestra dei mazzi) nei colori di ArtStation (Autore, 17 ott 2026 ~21:30:
# «usiamo i colori di artstation, per l'interfaccia non per la chat, la chat resta cosi'»). Letti dal foglio di stile di
# artstation.com lo stesso giorno: fondi #101014 / #18181c / #202024 / #303034 (gray-900..600), testo #bebec2, titoli bianchi,
# secondario #96969a e #707074, accento #24baff (primary), link #61cdff, verde #5cb85c, rosso #d9534f, giallo #f0ad4e.
# La chat resta sulla palette C qui sopra. Le stesse chiavi di C, piu' capo (titolo di scheda), accento, sel e sopra.
CI = dict(C, fondo="#101014", scheda="#18181c", cap="#202024", testa="#18181c", filo="#303034", filo2="#202024",
          titolo="#ffffff", testo="#bebec2", grigio="#96969a", muto="#707074", acciaio="#61cdff",
          arancio="#f0ad4e", verde="#5cb85c", verde_t="#a9d34f", rosso="#d9534f", rosso_t="#ee8a87",
          azzurro="#24baff", azzurro_s="#0f2a38", led="#24baff", traccia="#303034", evidenza="#202024",
          capo="#ffffff", accento="#24baff", sel="#0f2a38", sopra="#202024")
# i colori del tier del mazzo (S A B C D, rating_mazzi.tier): li usano la finestra grande e quella dei mazzi
COL_TIER = {"S": CI["arancio"], "A": CI["verde"], "B": CI["azzurro"], "C": CI["grigio"], "D": CI["rosso"], "?": CI["muto"]}
VINTA, PERSA = CI["azzurro"], CI["rosso"]   # il grafico delle vinte e delle perse (vedi sopra: controllati per i daltonici)
SALDO = "#f0ad4e"       # la linea del saldo sul Trend: lontana da azzurro, rosso e grigio anche per i daltonici, 13,8 o piu' in OKLab; viola e rosa cadevano sotto 8 sull'azzurro
SFONDO_FASCIA, SFONDO_LINEA = "#1c1c21", "#26262c"   # lo sfondo del grafico: fasce e linee appena visibili sul fondo #18181c
LEGHE = ("Bronze", "Silver", "Gold", "Platinum", "Diamond", "Mythic")
COL_LEGA = {"Bronze": "#c8834e", "Silver": "#b8bcc4", "Gold": "#e8c15a", "Platinum": "#7fd1c7", "Diamond": "#a58cff",
            "Mythic": "#ff7a3d"}   # il colore e' insieme al nome scritto: non e' l'unico segnale


# ---------------------------------------------------------------- le pagine

TEND = dict(campo="#101014", bordo="#3a3a40", sopra="#1c1f26", testo=CI["testo"], muto=CI["muto"])


# ---------------------------------------------------------------- la finestra

def carica_font():
    """Poppins per questo processo soltanto (niente installazione nel sistema)."""
    try:
        import piattaforma      # Windows: AddFontResourceExW; Mac: CoreText, per il solo processo (11 nov 2026)
        return piattaforma.font_del_processo([os.path.join(ASSET, f) for f in ("Poppins-Regular.ttf", "Poppins-Medium.ttf")]) > 0
    except Exception:
        return False


def id_app(nome):
    """L'app nella barra delle applicazioni col suo logo e non con quello di Python (10 nov 2026, Autore: «sull'icona dell'app aperta in basso sulla barra
    vedo il logo python e non il logo dell'app»): Windows raggruppa le finestre per programma, e senza un id suo l'app e' pythonw.exe. Va chiamata prima della
    prima finestra del processo."""
    import re
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("MagicArena." + re.sub(r"\W", "", nome))
    except Exception:       # noqa: BLE001 - fuori da Windows non serve
        pass


def icona_finestra(root, ico):
    """Il logo sulla finestra vera di Windows (10 nov 2026, Autore: «il logo dell'app aperta sulla barra non e' il nostro logo ma una piuma»): iconphoto di Tk
    non arrivava alla finestra che Windows usa per la barra (WM_GETICON vuoto), e la barra prendeva l'icona della classe, la piuma di Tk. Qui il file .ico va
    sulla finestra (WM_SETICON grande e piccola) e sulla classe TkTopLevel, cosi' lo prendono anche le finestre aperte dopo (il mazzo, il Board). -> True se fatto."""
    try:
        import ctypes
        u = ctypes.windll.user32
        u.LoadImageW.restype = ctypes.c_void_p
        u.GetParent.restype = ctypes.c_void_p
        u.SetClassLongPtrW.restype = ctypes.c_void_p
        u.SetClassLongPtrW.argtypes = (ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p)
        u.SendMessageW.argtypes = (ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p, ctypes.c_void_p)
        root.update_idletasks()
        hwnd = u.GetParent(root.winfo_id()) or root.winfo_id()
        grande = u.LoadImageW(None, ico, 1, 256, 256, 0x10)        # IMAGE_ICON, LR_LOADFROMFILE: la misura piu' grande del file, la barra la riduce
        piccola = u.LoadImageW(None, ico, 1, u.GetSystemMetrics(49), u.GetSystemMetrics(50), 0x10)      # SM_CXSMICON, SM_CYSMICON
        if not grande or not piccola:
            return False
        u.SendMessageW(hwnd, 0x80, 1, grande)       # WM_SETICON, ICON_BIG
        u.SendMessageW(hwnd, 0x80, 0, piccola)      # ICON_SMALL
        u.SetClassLongPtrW(hwnd, -14, grande)       # GCLP_HICON
        u.SetClassLongPtrW(hwnd, -34, piccola)      # GCLP_HICONSM
        root._icone_win = (grande, piccola)         # restano vive finche' c'e' la finestra
        return True
    except Exception:       # noqa: BLE001 - fuori da Windows resta l'icona di Tk
        return False


_ICONE = []      # le icone create restano vive finche' vive il processo


def nascondi_titolo(root):
    """La barra del titolo di Windows senza il testo e senza l'icona (SetWindowThemeAttribute, WTNCA_NODRAWCAPTION | WTNCA_NODRAWICON): il nome e il logo li
    disegna la testata della finestra, piu' grandi (Autore, 10 nov 2026). Il titolo resta per la barra delle applicazioni e Alt+Tab."""
    try:
        import ctypes

        class Opzioni(ctypes.Structure):
            _fields_ = [("flag", ctypes.c_uint32), ("maschera", ctypes.c_uint32)]
        root.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(root.winfo_id())
        o = Opzioni(3, 3)
        ok = ctypes.windll.uxtheme.SetWindowThemeAttribute(hwnd, 1, ctypes.byref(o), ctypes.sizeof(o)) == 0
        # su Windows 11 l'icona resta disegnata lo stesso: alla finestra si da' come icona piccola una trasparente (ICON_SMALL); la grande, quella della barra
        # delle applicazioni e di Alt+Tab, resta il logo
        u = ctypes.windll.user32
        u.CreateIcon.restype = ctypes.c_void_p
        u.SendMessageW.argtypes = (ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p, ctypes.c_void_p)
        e = (ctypes.c_ubyte * (16 * 16 // 8))(*([0xFF] * (16 * 16 // 8)))        # la maschera AND tutta a 1: trasparente
        x = (ctypes.c_ubyte * (16 * 16 * 4))()
        vuota = u.CreateIcon(None, 16, 16, 1, 32, e, x)
        if vuota:
            _ICONE.append(vuota)
            u.SendMessageW(hwnd, 0x80, 0, vuota)        # WM_SETICON, ICON_SMALL
        u.SetWindowPos(hwnd, 0, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0004 | 0x0010 | 0x0020)      # NOSIZE NOMOVE NOZORDER NOACTIVATE FRAMECHANGED
        return ok
    except Exception:
        return False


def barra_scura(root, sfondo, testo, bordo):
    """La barra del titolo di Windows nei colori della finestra (Windows 11, DWM): resta la barra vera,
    quindi si sposta, si riduce, si aggancia ai lati e sta nella barra delle applicazioni come prima."""
    try:
        import ctypes
        root.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(root.winfo_id())
        rgb = lambda h: ctypes.c_int(int(h[5:7] + h[3:5] + h[1:3], 16))
        dwm = ctypes.windll.dwmapi.DwmSetWindowAttribute
        uno = ctypes.c_int(1)
        dwm(hwnd, 20, ctypes.byref(uno), 4)                       # tema scuro (pulsanti chiari)
        for att, col in ((35, sfondo), (36, testo), (34, bordo)):  # didascalia, testo, bordo
            c = rgb(col); dwm(hwnd, att, ctypes.byref(c), 4)
        return True
    except Exception:
        return False
