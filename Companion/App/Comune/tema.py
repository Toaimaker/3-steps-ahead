"""I colori e i font: la palette della chat (C) e quella dell'interfaccia nei colori di ArtStation (CI), i colori dei grafici e delle leghe, la barra scura di Windows."""
import os

from ambiente import ASSET


# palette  scuro
C = dict(fondo="#101015", scheda="#17171f", cap="#1a1d25", testa="#141820", filo="#2c3240", filo2="#252a35",
         titolo="#E2E4E9", testo="#ECEAE7", grigio="#9A9794", muto="#7c776f", acciaio="#6FA8D8",
         arancio="#ff5b1f", verde="#1FB877", verde_t="#7fe3b0", rosso="#e5533d", rosso_t="#ff9a8a",
         azzurro="#33BFFF", azzurro_s="#06212E", led="#39FF7A", traccia="#22252e", evidenza="#21222c")
# il redesign del 14 nov 2026 (Autore: «ogni scheda dell'app deve essere restylata»): anche la chat prende i fondi e i bordi blu notte; i colori dei suoi
# messaggi (verde, rosso, arancio, azzurro) restano quelli di sempre
C.update(fondo="#090b0f", scheda="#10141b", cap="#161b25", testa="#0d1016", filo="#222833", filo2="#181d26", traccia="#1e2431", evidenza="#181d28")
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
# Il redesign grafico del 14 nov 2026 (Autore: «piu' esport», poi «piu' realistico», mockup approvati in Note/Redesign_Grafico): fondi blu notte da #090b0f a
# #1e2431, bordi bianchi al 6-10% (qui gia' mescolati sul fondo, Tk non ha la trasparenza), testo #d7dce5, secondario #9099a8 e #5f6878, accento #2f9bff, vinto
# #3ccf8e, perso #ff5d63. Cambia solo lo stile: le stesse chiavi, gli stessi usi. RD tiene i toni in piu' del redesign (le due facce della sfumatura dei
# pannelli, il filo di luce in cima, il campo delle tendine, le fasce delle tabelle).
CI.update(fondo="#090b0f", scheda="#10141b", cap="#161b25", testa="#0d1016", filo="#222833", filo2="#181d26",
          titolo="#ffffff", testo="#d7dce5", grigio="#9099a8", muto="#5f6878", acciaio="#6fb6ff",
          arancio="#f0a23a", verde="#3ccf8e", verde_t="#7fe3b0", rosso="#ff5d63", rosso_t="#ff9a9c",
          azzurro="#2f9bff", azzurro_s="#0e2238", led="#2f9bff", traccia="#1e2431", evidenza="#181d28",
          capo="#ffffff", accento="#2f9bff", sel="#0e2238", sopra="#181d28")
RD = dict(p0="#0e1117", p1="#131720", p2="#181d28", p3="#1e2431", campo="#0b0e14", luce="#20262f", ombra="#050608",
          filo="#1d222b", filo2="#2a303b", riga="#121620", riga2="#0f131a", oro="#e9b949", vinto="#3ccf8e", perso="#ff5d63",
          acc2="#1a6fd6", glow="#2f9bff")
# i colori del tier del mazzo (S A B C D, rating_mazzi.tier): li usano la finestra grande e quella dei mazzi
COL_TIER = {"S": CI["arancio"], "A": CI["verde"], "B": CI["azzurro"], "C": CI["grigio"], "D": CI["rosso"], "?": CI["muto"]}
VINTA, PERSA = CI["azzurro"], CI["rosso"]   # il grafico delle vinte e delle perse (vedi sopra: controllati per i daltonici)
SALDO = "#f0ad4e"       # la linea del saldo sul Trend: lontana da azzurro, rosso e grigio anche per i daltonici, 13,8 o piu' in OKLab; viola e rosa cadevano sotto 8 sull'azzurro
SFONDO_FASCIA, SFONDO_LINEA = "#12161e", "#1b2029"   # lo sfondo del grafico: fasce e linee appena visibili sul fondo dei pannelli (redesign del 14 nov 2026)
LEGHE = ("Bronze", "Silver", "Gold", "Platinum", "Diamond", "Mythic")
COL_LEGA = {"Bronze": "#c8834e", "Silver": "#b8bcc4", "Gold": "#e8c15a", "Platinum": "#7fd1c7", "Diamond": "#a58cff",
            "Mythic": "#ff7a3d"}   # il colore e' insieme al nome scritto: non e' l'unico segnale


# ---------------------------------------------------------------- le pagine

TEND = dict(campo="#0b0e14", bordo="#2a303b", sopra="#181d28", testo=CI["testo"], muto=CI["muto"])


# ---------------------------------------------------------------- i font del redesign (14 nov 2026)
# Testo in Segoe UI, numeri grandi in Bahnschrift (Windows 10 e 11); dove non ci sono (Mac) il Poppins dell'app, come prima.

def famiglie():
    """(testo, testo medio, numeri, numeri medi): i nomi delle famiglie che Tk conosce in questo processo."""
    if "_FAM" not in globals():
        try:
            from tkinter import font as tkfont
            ci = set(tkfont.families())
        except Exception:       # noqa: BLE001 - prima di una finestra di Tk: si richiede dopo
            return ("Segoe UI", "Segoe UI Semibold", "Bahnschrift", "Bahnschrift SemiBold")
        t = "Segoe UI" if "Segoe UI" in ci else ("Poppins" if "Poppins" in ci else "TkDefaultFont")
        tm = "Segoe UI Semibold" if "Segoe UI Semibold" in ci else ("Poppins Medium" if "Poppins Medium" in ci else t)
        n = "Bahnschrift" if "Bahnschrift" in ci else t
        nm = "Bahnschrift SemiBold" if "Bahnschrift SemiBold" in ci else (n if n != t else tm)
        globals()["_FAM"] = (t, tm, n, nm)
    return globals()["_FAM"]


def FN(n, medio=True):
    """Il font dei numeri grandi (Bahnschrift), per Tk."""
    f = famiglie()
    return (f[3] if medio else f[2], n)


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
