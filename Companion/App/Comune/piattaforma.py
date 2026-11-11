"""Quello che cambia fra Windows e Mac, in un posto solo (11 nov 2026, sessione Magic 13; Autore: «lavoriamo per ottenere la versione mac»).

L'app e' nata su Windows: percorsi di Arena scritti a mano, tasklist, msvcrt, la priorita' del processo con windll, pythonw. Qui ogni cosa ha la sua
funzione, e su Windows ogni funzione da' esattamente quello di prima (le stesse stringhe dei percorsi: ci sono cache legate al percorso).

Su Mac (verificato sulle fonti, non su un Mac vero: Distribuzione/Mac.md):
- il log di Arena sta in ~/Library/Logs/Wizards Of The Coast/MTGA (Player.log, Player-prev.log); la pagina di supporto di Wizards indica anche
  ~/Library/Application Support/com.wizards.mtga/Logs/Logs, piu' vecchia: si cerca nelle due, vince quella che ha il Player.log;
- Arena e' il processo «MTGA» (pgrep);
- il lucchetto di un file e' fcntl.flock, la priorita' bassa os.nice, il Python senza console e' lo stesso sys.executable, un link si apre con «open».
Prova: --prova (su Windows: i percorsi uguali a prima; la finzione del Mac: i percorsi del Mac, il lucchetto POSIX dove c'e').
"""
import os
import subprocess
import sys

WINDOWS = sys.platform == "win32"
MAC = sys.platform == "darwin"
SISTEMA = "windows" if WINDOWS else "mac" if MAC else "linux"

_WIN_ARENA = r"%USERPROFILE%\AppData\LocalLow\Wizards Of The Coast\MTGA"
MAC_ARENA = ("~/Library/Logs/Wizards Of The Coast/MTGA", "~/Library/Application Support/com.wizards.mtga/Logs/Logs")
# senza console: CREATE_NO_WINDOW; sotto la norma: BELOW_NORMAL_PRIORITY_CLASS. Su Mac e Linux 0: la priorita' passa da os.nice (sottofondo)
NO_FINESTRA = 0x08000000 if WINDOWS else 0
SOTTO_NORMA = 0x00004000 if WINDOWS else 0


def cartella_arena():
    """La cartella dei log di Arena (Player.log, Player-prev.log). Su Windows la stringa di sempre."""
    if WINDOWS:
        return os.path.expandvars(_WIN_ARENA)
    candidate = [os.path.expanduser(c) for c in MAC_ARENA] if MAC else [os.path.expanduser("~/.local/share/Wizards Of The Coast/MTGA")]
    return next((c for c in candidate if os.path.isfile(os.path.join(c, "Player.log"))), candidate[0])


def player_log():
    return os.path.join(cartella_arena(), "Player.log")


def player_prev_log():
    return os.path.join(cartella_arena(), "Player-prev.log")


def arena_aperta():
    """Arena e' aperta? Su Windows tasklist (MTGA.exe), su Mac pgrep (MTGA). Se il comando non c'e', no."""
    try:
        if WINDOWS:
            r = subprocess.run(["tasklist", "/FI", "IMAGENAME eq MTGA.exe", "/NH"], capture_output=True, creationflags=NO_FINESTRA)     # in byte: Windows risponde nella sua codifica
            return b"mtga.exe" in r.stdout.lower()
        r = subprocess.run(["pgrep", "-x", "MTGA"], capture_output=True)
        return r.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def blocca(f):
    """Il lucchetto esclusivo, senza aspettare, sul file aperto f: True se e' nostro, False se ce l'ha gia' un altro processo."""
    try:
        if WINDOWS:
            import msvcrt
            msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except OSError:
        return False


def priorita_bassa():
    """Questo processo sotto la norma: su Windows BELOW_NORMAL_PRIORITY_CLASS, altrove nice 10."""
    try:
        if WINDOWS:
            import ctypes
            ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), SOTTO_NORMA)
        else:
            os.nice(10)
    except (OSError, AttributeError):
        pass


FLAG_WINDOWS = dict(sotto=0x00004000, muto=0x08000000, staccato=0x00000008, console=0x00000010)     # BELOW_NORMAL_PRIORITY_CLASS, CREATE_NO_WINDOW,
# DETACHED_PROCESS, CREATE_NEW_CONSOLE


def flag(*voci):
    """Gli argomenti di subprocess per un processo figlio. voci: «sotto» priorita' bassa, «muto» senza console, «staccato» che resta se la finestra si
    chiude, «console» in una console sua. Su Windows le flag di sempre (creationflags); su Mac e Linux mai creationflags (Popen lo rifiuta): «sotto» e' nice
    10 nel figlio, «staccato» una sessione sua, «muto» e «console» non servono (niente console da nascondere o da aprire)."""
    sconosciute = set(voci) - set(FLAG_WINDOWS)
    if sconosciute:
        raise ValueError(f"flag sconosciute: {sorted(sconosciute)}")
    if WINDOWS:
        f = 0
        for v in voci:
            f |= FLAG_WINDOWS[v]
        return dict(creationflags=f)
    out = {}
    if "sotto" in voci:
        out["preexec_fn"] = _nice
    if "staccato" in voci:
        out["start_new_session"] = True
    return out


def _nice():
    try:
        os.nice(10)
    except OSError:
        pass


def sottofondo(console=False):
    """Priorita' bassa, senza console se console e' False: flag("sotto", "muto")."""
    return flag("sotto") if console else flag("sotto", "muto")


def processo_vivo(pid):
    """Il processo pid e' ancora acceso? Windows: OpenProcess e GetExitCodeProcess (259 = ancora attivo); altrove os.kill(pid, 0)."""
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return False
    if WINDOWS:
        import ctypes
        k = ctypes.windll.kernel32
        h = k.OpenProcess(0x1000, False, pid)
        if not h:
            return False
        c = ctypes.c_ulong()
        k.GetExitCodeProcess(h, ctypes.byref(c))
        k.CloseHandle(h)
        return c.value == 259
    try:
        os.kill(pid, 0)
        return True
    except PermissionError:
        return True         # c'e', ma di un altro utente
    except OSError:
        return False


def font_del_processo(file):
    """I font .ttf per questo processo soltanto, niente installazione nel sistema: su Windows AddFontResourceExW (FR_PRIVATE), su Mac CTFontManager di
    CoreText con lo scope del processo (non provato su un Mac vero: Distribuzione/Mac.md). -> quanti font caricati."""
    n = 0
    if WINDOWS:
        import ctypes
        for f in file:
            n += bool(ctypes.windll.gdi32.AddFontResourceExW(f, 0x10, 0))
        return n
    if MAC:
        import ctypes
        try:
            cf = ctypes.cdll.LoadLibrary("/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation")
            ct = ctypes.cdll.LoadLibrary("/System/Library/Frameworks/CoreText.framework/CoreText")
            cf.CFURLCreateFromFileSystemRepresentation.restype = ctypes.c_void_p
            cf.CFURLCreateFromFileSystemRepresentation.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_long, ctypes.c_bool]
            ct.CTFontManagerRegisterFontsForURL.restype = ctypes.c_bool
            ct.CTFontManagerRegisterFontsForURL.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_void_p]
            cf.CFRelease.argtypes = [ctypes.c_void_p]
            for f in file:
                b = os.fsencode(f)
                url = cf.CFURLCreateFromFileSystemRepresentation(None, b, len(b), False)
                if url:
                    n += bool(ct.CTFontManagerRegisterFontsForURL(url, 1, None))      # kCTFontManagerScopeProcess
                    cf.CFRelease(url)
        except (OSError, AttributeError):
            pass
    return n


def scatti(delta):
    """Gli scatti della rotella da un evento <MouseWheel>, col segno di yview_scroll (in giu' positivo). Windows: multipli di 120, int(-delta/120) come
    sempre; Mac: Tk da' il numero di righe (1, 2...) e il trackpad tanti valori piccoli, al massimo 3 per evento."""
    if WINDOWS:
        return int(-delta / 120)
    return max(-3, min(3, -int(delta))) if delta else 0


def python_console():
    """Il Python con la console (python.exe) accanto a quello che gira, anche se gira pythonw; fuori da Windows sys.executable."""
    if WINDOWS:
        return os.path.join(os.path.dirname(sys.executable), "python.exe")
    return sys.executable


def python_grafico():
    """Il Python che apre finestre senza console: pythonw.exe accanto a python.exe su Windows, sys.executable altrove."""
    if WINDOWS:
        w = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
        return w if os.path.exists(w) else sys.executable
    return sys.executable


def apri(percorso):
    """Un file, una cartella o un link col programma del sistema."""
    if WINDOWS:
        os.startfile(percorso)
    elif MAC:
        subprocess.Popen(["open", percorso])
    else:
        subprocess.Popen(["xdg-open", percorso])


def prova():
    import tempfile
    casi = []
    if WINDOWS:
        casi.append(("Windows: la cartella di Arena e' la stringa di sempre",
                     cartella_arena() == os.path.expandvars(r"%USERPROFILE%\AppData\LocalLow\Wizards Of The Coast\MTGA")))
        casi.append(("Windows: Player.log e Player-prev.log nella cartella", player_log().endswith("MTGA\\Player.log") and player_prev_log().endswith("MTGA\\Player-prev.log")))
        casi.append(("Windows: sottofondo senza console e sotto la norma", sottofondo() == dict(creationflags=0x08004000)))
    f = open(os.path.join(tempfile.mkdtemp(), "blocco"), "w")
    g = open(f.name, "w")
    casi.append(("il lucchetto e' di chi lo prende per primo", blocca(f) and (not blocca(g) if not WINDOWS else True)))
    casi.append(("Arena aperta: risponde si' o no senza cadere", arena_aperta() in (True, False)))
    # la finzione del Mac: le funzioni del Mac con sys.platform «darwin», in un processo a parte
    codice = (f"import sys; sys.platform = 'darwin'; sys.path.insert(0, {os.path.dirname(os.path.abspath(__file__))!r})\n"
              "import os, piattaforma as P\n"
              "print(P.SISTEMA, P.cartella_arena() == os.path.expanduser('~/Library/Logs/Wizards Of The Coast/MTGA'), P.NO_FINESTRA, 'creationflags' in P.sottofondo(),"
              " [P.scatti(d) for d in (1, -2, 40, 0)])")
    r = subprocess.run([sys.executable, "-I", "-c", codice], capture_output=True, text=True)
    casi.append(("finto Mac: il sistema, la cartella dei log del Mac, niente flag di Windows", r.stdout.split()[:4] == ["mac", "True", "0", "False"]))
    casi.append(("finto Mac: la rotella a righe (1 -> -1, -2 -> 2, 40 -> -3 al massimo)", r.stdout.strip().endswith("[-1, 2, -3, 0]")))
    if WINDOWS:
        casi.append(("Windows: la rotella come sempre, int(-delta/120)", [scatti(d) for d in (120, -120, 240, -360, 0)] == [-1, 1, -2, 3, 0]))
    casi.append(("negativa: su Windows la cartella non e' quella del Mac", not WINDOWS or "Library" not in cartella_arena()))
    for nome, ok in casi:
        print(("  ok    " if ok else "  ROSSO ") + nome)
    n = sum(1 for _, ok in casi if ok)
    print(f"{n}/{len(casi)}")
    return 0 if n == len(casi) else 1


if __name__ == "__main__":
    if "--prova" in sys.argv:
        sys.exit(prova())
