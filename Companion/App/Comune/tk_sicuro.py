"""Un widget distrutto cancella i suoi `after` ancora in attesa.

Trovato il 10 nov 2026 (sessione Magic 10, il debug della notte): l'errore di Tk «pulsante_solido.<locals>.<lambda>() missing 1 required positional argument: 'e'»
(e lo stesso in `PaginaMazzi.scatola`), visto ogni tanto durante le prove, veniva da qui. In tkinter `w.after(ms, lambda: ...)` registra un comando di Tcl col
nome `<id><lambda>` e lo mette fra i comandi di `w`. Se `w` viene distrutto prima che l'after scatti, tkinter cancella il comando ma l'after resta in Tcl;
quando l'id viene riusato da un `bind(seq, lambda e: ...)` nuovo, il comando del bind ha lo stesso nome, e l'after rimasto lo chiama senza argomenti:
`_substitute` restituisce gli argomenti come sono (zero) e la lambda del bind parte senza l'evento. Senza collisione l'after rimasto da' solo «invalid
command name» in Tcl, che non si vede. Cosi' l'after di un widget distrutto non scatta piu'.

`applica()` si chiama una volta, prima di creare finestre (la chiamano `widget.py` e `finestra.py`); chiamarla di nuovo non fa niente.
`py -I -X utf8 Companion/App/Comune/tk_sicuro.py --prova`: la collisione forzata, che senza la cura chiama il bind senza evento (la negativa)."""
import sys
import tkinter

_FATTO = {"si": False}


def applica():
    if _FATTO["si"]:
        return
    _FATTO["si"] = True
    after0, cancel0, destroy0 = tkinter.Misc.after, tkinter.Misc.after_cancel, tkinter.Misc.destroy

    def after(self, ms, func=None, *args):
        if func is None:
            return after0(self, ms)
        box = {}

        def scatta(*a):
            ids = self.__dict__.get("_after_vivi")
            if ids is not None:
                ids.discard(box.get("id"))
            return func(*a)
        scatta.__name__ = getattr(func, "__name__", type(func).__name__)
        i = after0(self, ms, scatta, *args)
        box["id"] = i
        self.__dict__.setdefault("_after_vivi", set()).add(i)
        return i

    def after_cancel(self, id):
        ids = self.__dict__.get("_after_vivi")
        if ids is not None:
            ids.discard(id)
        return cancel0(self, id)

    def destroy(self):
        ids = self.__dict__.pop("_after_vivi", None)
        if ids:
            for i in ids:
                try:
                    self.tk.call("after", "cancel", i)
                except tkinter.TclError:
                    pass
        return destroy0(self)
    tkinter.Misc.after, tkinter.Misc.after_cancel, tkinter.Misc.destroy = after, after_cancel, destroy


def _collisione():
    """Un after su un widget poi distrutto, e un bind col nome del suo comando (la collisione forzata). -> (bind chiamati senza evento, errori di Tcl)."""
    import time
    errori = []
    root = tkinter.Tk(); root.withdraw()
    root.report_callback_exception = lambda *a: errori.append(str(a[1]))
    root.tk.eval("proc bgerror {msg} {lappend ::bg_prova $msg}; set ::bg_prova {}")
    senza = []
    for _ in range(20):
        w = tkinter.Canvas(root)
        i = w.after(20, lambda: None)
        nome = root.tk.splitlist(root.tk.call("after", "info", i))[0]
        w.destroy()
        c = tkinter.Canvas(root)
        root.tk.createcommand(nome, tkinter.CallWrapper(lambda e: senza.append(e), c._substitute, c).__call__)     # lo stesso nome, come quando l'id si riusa
    fine = time.time() + 0.2
    while time.time() < fine:
        root.update(); time.sleep(0.01)
    bg = int(root.tk.eval("llength $::bg_prova"))
    root.destroy()
    return len([e for e in errori if "missing 1 required positional argument" in e]), bg


def _normale():
    """Gli after dei widget vivi scattano ancora, after_cancel funziona ancora, after senza funzione aspetta."""
    import time
    root = tkinter.Tk(); root.withdraw()
    fatti = []
    w = tkinter.Canvas(root)
    w.after(10, lambda: fatti.append("vivo"))
    j = w.after(10, lambda: fatti.append("cancellato")); w.after_cancel(j)
    w.after_idle(lambda: fatti.append("idle"))
    w.after(10, lambda a, b: fatti.append(a + b), "co", "n argomenti")
    t0 = time.time(); w.after(30); attesa = time.time() - t0
    fine = time.time() + 0.15
    while time.time() < fine:
        root.update(); time.sleep(0.01)
    rimasti = len(w.__dict__.get("_after_vivi", ()))
    root.destroy()
    return sorted(fatti) == ["con argomenti", "idle", "vivo"] and attesa >= 0.025 and rimasti == 0


def prova():
    casi = []
    n0, bg0 = _collisione()
    casi.append(("negativa: senza la cura l'after del widget distrutto chiama il bind senza evento", n0 == 20))
    applica()
    applica()
    n1, bg1 = _collisione()
    casi.append(("con la cura l'after del widget distrutto non scatta: nessun bind senza evento, nessun errore di Tcl", n1 == 0 and bg1 == 0))
    casi.append(("gli after dei widget vivi scattano, after_cancel, after_idle e gli argomenti funzionano, niente resta segnato", _normale()))
    ok = sum(1 for _n, v in casi if v)
    for n, v in casi:
        print(("ok    " if v else "ROSSO ") + n)
    print(f"{ok}/{len(casi)}")
    return ok == len(casi)


if __name__ == "__main__":
    if "--prova" in sys.argv:
        sys.exit(0 if prova() else 1)
    print(__doc__)
