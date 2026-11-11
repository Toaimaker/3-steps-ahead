"""numpy senza i 600 MB di OpenBLAS (11 nov 2026, sessione Magic 13).

Su questo PC (20 processori) `import numpy` impegnava +620 MB di memoria privata: OpenBLAS, la libreria dei conti fra matrici di numpy, prepara un
buffer per ogni filo di calcolo, uno per processore. Il set di lavoro cresce di 13 MB (le pagine non si toccano), ma la memoria impegnata conta sul
limite di Windows e sul file di paging. La finestra usa numpy solo per le sfumature delle capsule, conti elemento per elemento: un filo basta.

Con OPENBLAS_NUM_THREADS=1 al momento dell'import l'impegno e' +10 MB. La variabile vale solo dentro l'import e poi torna com'era, cosi' i processi
che la finestra lancia (il companion col pulsante Launch, il drafter) non la ereditano: con un numero di fili diverso OpenBLAS somma in un altro ordine,
e i pick del drafter dipendono dall'ultima cifra (8 nov 2026, la prova d'identita' dei futuri su 6 processi).

Chi nella finestra vuole numpy lo chiede qui: `np = numpy_leggero.carica()`.
"""
import os
import sys
import threading

VARIABILI = ("OPENBLAS_NUM_THREADS",)
_LUCCHETTO = threading.Lock()


def carica():
    """numpy, importato con OpenBLAS a un filo se e' la prima volta nel processo. Una variabile gia' scritta dall'utente vince."""
    if "numpy" in sys.modules:
        return sys.modules["numpy"]
    with _LUCCHETTO:
        if "numpy" in sys.modules:
            return sys.modules["numpy"]
        prima = {k: os.environ.get(k) for k in VARIABILI}
        for k in VARIABILI:
            os.environ.setdefault(k, "1")
        try:
            import numpy
        finally:
            for k, v in prima.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v
    return numpy


def prova():
    """In un processo nuovo: carica() impegna meno di 100 MB, l'import nudo (la negativa) di piu' su una macchina con molti processori; la variabile
    non resta nell'ambiente."""
    import subprocess
    codice = r'''
import ctypes, ctypes.wintypes as W, os, sys
sys.path.insert(0, {cartella!r})
class PMC(ctypes.Structure):
    _fields_ = [("cb", W.DWORD), ("PF", W.DWORD), ("P", ctypes.c_size_t), ("WS", ctypes.c_size_t), ("a", ctypes.c_size_t), ("b", ctypes.c_size_t),
                ("c", ctypes.c_size_t), ("d", ctypes.c_size_t), ("PU", ctypes.c_size_t), ("e", ctypes.c_size_t)]
k = ctypes.WinDLL("kernel32"); k.GetCurrentProcess.restype = W.HANDLE
k.K32GetProcessMemoryInfo.argtypes = [W.HANDLE, ctypes.POINTER(PMC), W.DWORD]
def mb():
    p = PMC(); p.cb = ctypes.sizeof(PMC); k.K32GetProcessMemoryInfo(k.GetCurrentProcess(), ctypes.byref(p), p.cb); return p.PU / 2**20
a = mb()
if {leggero}:
    import numpy_leggero; np = numpy_leggero.carica()
else:
    import numpy as np
print(round(mb() - a), "OPENBLAS_NUM_THREADS" in os.environ, float(np.ones(3) @ np.ones(3)))
'''
    cartella = os.path.dirname(os.path.abspath(__file__))
    esiti = {}
    for leggero in (True, False):
        amb = {k: v for k, v in os.environ.items() if k not in VARIABILI}
        r = subprocess.run([sys.executable, "-I", "-c", codice.format(cartella=cartella, leggero=leggero)], capture_output=True, text=True, env=amb, timeout=120)
        piu, resta, conto = r.stdout.split()
        esiti[leggero] = (int(piu), resta == "True", float(conto))
    multi = (os.cpu_count() or 1) >= 8
    casi = [("caricato leggero: meno di 100 MB impegnati", esiti[True][0] < 100),
            ("la variabile non resta nell'ambiente (i processi figli non la ereditano)", not esiti[True][1]),
            ("numpy funziona", esiti[True][2] == 3.0),
            ("negativa: l'import nudo impegna di piu' (solo con 8+ processori)", esiti[False][0] > esiti[True][0] + 50 if multi else True)]
    for nome, ok in casi:
        print(("  ok    " if ok else "  ROSSO ") + nome)
    print(f"  (leggero +{esiti[True][0]} MB, nudo +{esiti[False][0]} MB, {os.cpu_count()} processori)")
    n = sum(1 for _, ok in casi if ok)
    print(f"{n}/{len(casi)}")
    return 0 if n == len(casi) else 1


if __name__ == "__main__":
    if "--prova" in sys.argv:
        sys.exit(prova())
