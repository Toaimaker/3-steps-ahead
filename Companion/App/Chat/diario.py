"""Il diario del companion: dove sta, se il companion e' vivo, se la partita e' di un evento limited."""
import datetime
import json
import os
import re

from ambiente import DIARIO_FISSO, LOGDIR


def e_limited(evento):
    """Un evento limited: Draft, Sealed o Cube nel nome, come in Performance."""
    return bool(re.search(r"Draft|Sealed|Cube", evento or "", re.I))


RX_EVENTO_PARTITA = re.compile(r"^=== PARTITA: (\S+) ===|^MANO \(\d+\) contro .+? \[([^\]]+)\]|ultima partita nel log: contro .+? \[([^\]]+)\]")


def evento_partita(t):
    """L'evento della partita che una riga del diario apre o riprende (=== PARTITA, MANO, VIGILANZA ATTIVA a companion ripartito), o None."""
    m = RX_EVENTO_PARTITA.search(t)
    return next((g for g in m.groups() if g), None) if m else None


def processo_vivo(pid):
    """Il processo pid e' ancora acceso? (Windows: OpenProcess e GetExitCodeProcess, 259 = ancora attivo)"""
    import ctypes
    k = ctypes.windll.kernel32
    h = k.OpenProcess(0x1000, False, int(pid))
    if not h:
        return False
    c = ctypes.c_ulong()
    k.GetExitCodeProcess(h, ctypes.byref(c))
    k.CloseHandle(h)
    return c.value == 259


class Diario:
    """Segue il file del giorno, anche quando cambia data."""

    def __init__(self):
        self.path = None; self.pos = 0; self.buf = ""

    def file_oggi(self):
        if DIARIO_FISSO:
            return DIARIO_FISSO
        # il diario del companion acceso (Log_Arena/companion_attivo.json): porta la data del giorno in cui e' partito, e
        # dopo mezzanotte quello di oggi e' vuoto (3 nov 2026). Senza companion vivo, il diario di oggi come prima.
        try:
            a = json.load(open(os.path.join(LOGDIR, "companion_attivo.json"), encoding="utf-8"))
            if os.path.exists(a["diario"]) and processo_vivo(a["pid"]):
                return a["diario"]
        except (OSError, ValueError, KeyError, TypeError):
            pass
        return os.path.join(LOGDIR, f"companion_{datetime.date.today():%Y%m%d}.txt")

    def nuove(self):
        p = self.file_oggi()
        if p != self.path:
            self.path, self.pos, self.buf = p, 0, ""
        if not os.path.exists(p):
            return []
        if os.path.getsize(p) < self.pos:
            self.pos = 0
        with open(p, encoding="utf-8", errors="replace") as f:
            f.seek(self.pos); dati = f.read(); self.pos = f.tell()
        self.buf += dati
        righe = self.buf.split("\n"); self.buf = righe.pop()
        return righe


def senza_ora(r):
    return re.sub(r"^\d\d:\d\d:\d\d ", "", r)
