"""Il costruttore di righe di filtri (13 nov 2026, Autore, su Advanced filters: «c'è troppa roba a vista, ricostruiamo la UX: Your T1 Cast appare di
default: tendina di default per scegliere cosa castiamo e accanto un + per aggiungere un'altra tendina / sotto mettiamo un add line: tendina Turno e tendina
di cast con + per aggiungere altra tendina ... possiamo aggiungere infinite righe che potranno a loro volta aggiungere infinite tendine», e per Decisions: «i
filtri per decision li imposti costruibili e l'impaginazione la fai come in advanced filters»).

Una riga e' [campo, [voci]]: a sinistra la tendina del campo (il turno, o il filtro di una decisione), poi una tendina per voce, il + che ne aggiunge un'altra,
la ✕ che toglie la riga; sotto «+ Add line». Le righe sono di chi chiama: a ogni cambio il costruttore chiama on_cambio(righe) e chi chiama decide cosa ne
fa (i filtri) e ridisegna. Una voce ancora da scegliere e' None; un campo ancora da scegliere anche.
"""
import os, sys
_casa = os.path.dirname(os.path.abspath(__file__))
while not os.path.isfile(os.path.join(_casa, "percorsi.py")):
    _casa = os.path.dirname(_casa)
if _casa not in sys.path:
    sys.path.insert(0, _casa)
import percorsi  # noqa: E402,F401
from tema import CI as C  # noqa: E402
from widget import Tendina  # noqa: E402

VUOTA = "—"         # la voce di una tendina ancora da scegliere


class Righe:
    def __init__(self, tk, F, padre, righe, campi, nome_campo, voci_di, on_cambio, bg=None, larga_campo=190, larga_voce=170, dopo=None):
        """righe: la lista [[campo, [voci]]] (la modifica); campi: le chiavi del campo; nome_campo(k) come si legge; voci_di(k): le voci di quel campo;
        on_cambio(righe): dopo ogni cambio; dopo: il testo fra il campo e le voci (es. «cast»)."""
        self.tk, self.F, self.righe, self.campi = tk, F, righe, list(campi)
        self.nome_campo, self.voci_di, self.on_cambio, self.dopo = nome_campo, voci_di, on_cambio, dopo
        self.bg = bg or C["scheda"]
        self.lc, self.lv = larga_campo, larga_voce
        self.fr = tk.Frame(padre, bg=self.bg)
        self.tendine = []           # (riga, indice voce o None per il campo, tendina): per le prove
        self.disegna()

    def disegna(self):
        tk, F = self.tk, self.F
        for w in self.fr.winfo_children():
            w.destroy()
        self.tendine = []
        for i, (campo, voci) in enumerate(self.righe):
            riga = tk.Frame(self.fr, bg=self.bg)
            riga.pack(anchor="w", pady=3, fill="x")
            t = self._tendina(riga, self.lc)
            t.opzioni([VUOTA] + self.campi, lambda v, i=i: self.metti_campo(i, v), etichette={VUOTA: VUOTA, **{k: self.nome_campo(k) for k in self.campi}})
            t.set(campo if campo is not None else VUOTA)
            t.fr.pack(side="left")
            self.tendine.append((i, None, t))
            if self.dopo:
                tk.Label(riga, text=self.dopo, bg=self.bg, fg=C["grigio"], font=F(8)).pack(side="left", padx=(6, 2))
            voci_ok = self.voci_di(campo) if campo is not None else []
            sottoriga = tk.Frame(riga, bg=self.bg)
            sottoriga.pack(side="left", fill="x")
            for j, v in enumerate(voci or [None]):
                tv = self._tendina(sottoriga, self.lv)
                tv.opzioni([VUOTA] + list(voci_ok), lambda v_, i=i, j=j: self.metti_voce(i, j, v_))
                tv.set(v if v is not None else VUOTA)
                tv.fr.pack(side="left", padx=(6, 0))
                self.tendine.append((i, j, tv))
            piu = tk.Label(riga, text="+", bg="#161b25", fg=C["accento"], font=F(11, True), width=2, cursor="hand2")
            piu.pack(side="left", padx=(6, 0), ipady=1)
            piu.bind("<Button-1>", lambda e, i=i: self.aggiungi_voce(i))
            via = tk.Label(riga, text="✕", bg=self.bg, fg=C["grigio"], font=F(9, True), cursor="hand2")
            via.pack(side="left", padx=(10, 0))
            via.bind("<Button-1>", lambda e, i=i: self.togli_riga(i))
        add = tk.Label(self.fr, text="+  Add line", bg="#161b25", fg=C["accento"], font=F(8, True), cursor="hand2", padx=10, pady=4)
        add.pack(anchor="w", pady=(6, 2))
        add.bind("<Button-1>", lambda e: self.aggiungi_riga())

    def _tendina(self, padre, larga):
        t = Tendina(self.tk, padre, "", self.F, larga=larga, bg=self.bg)
        t.fr.winfo_children()[0].pack_forget()      # niente nome sopra: il campo dice gia' cos'e'
        t.campo.configure(height=24)
        return t

    def cambiato(self):
        """Dopo un cambio: chi chiama aggiorna i filtri; le tendine si rifanno dopo, non dentro il clic della tendina che ha cambiato."""
        self.on_cambio(self.righe)
        try:
            self.fr.after_idle(lambda: self.fr.winfo_exists() and self.disegna())
        except Exception:      # noqa: BLE001 - chi chiama ha gia' rifatto tutto
            pass

    def metti_campo(self, i, v):
        self.righe[i][0] = None if v == VUOTA else v
        self.righe[i][1] = [x for x in self.righe[i][1] if x is None or x in (self.voci_di(self.righe[i][0]) if self.righe[i][0] else [])] or [None]
        self.cambiato()

    def metti_voce(self, i, j, v):
        voci = self.righe[i][1] or [None]
        while len(voci) <= j:
            voci.append(None)
        voci[j] = None if v == VUOTA else v
        self.righe[i][1] = voci
        self.cambiato()

    def aggiungi_voce(self, i):
        self.righe[i][1] = list(self.righe[i][1] or [None]) + [None]
        self.cambiato()

    def togli_riga(self, i):
        del self.righe[i]
        self.cambiato()

    def aggiungi_riga(self):
        usati = {r[0] for r in self.righe}
        nuovo = next((k for k in self.campi if k not in usati), None)
        self.righe.append([nuovo, [None]])
        self.cambiato()


def prova():
    import tkinter as tk
    casi = []
    root = tk.Tk(); root.geometry("900x400+7000+0")
    F = lambda n, b=False: ("Segoe UI", n, "bold" if b else "normal")
    visti = []
    righe = [["1", [None]]]
    r = Righe(tk, F, root, righe, ["1", "2", "3"], lambda k: f"Your T{k} cast", lambda k: ["Creature", "Instant"], lambda rr: visti.append([list(x) for x in rr]))
    r.fr.pack()
    root.update()
    casi.append(("di partenza una riga: la tendina del campo e una delle voci", [(i, j) for i, j, _t in r.tendine] == [(0, None), (0, 0)]))
    r.metti_voce(0, 0, "Creature"); r.aggiungi_voce(0); r.metti_voce(0, 1, "Instant")
    casi.append(("il + aggiunge una tendina alla riga: due voci", righe == [["1", ["Creature", "Instant"]]] and visti[-1] == [["1", ["Creature", "Instant"]]]))
    r.aggiungi_riga()
    casi.append(("Add line: una riga nuova col primo campo libero", righe[-1] == ["2", [None]]))
    r.metti_campo(1, "3")
    r.togli_riga(0)
    casi.append(("la ✕ toglie la riga; cambiare campo tiene le voci che valgono", righe == [["3", [None]]]))
    r.metti_voce(0, 0, "—")
    casi.append(("negativa: la voce vuota resta da scegliere (None), non diventa un filtro", righe == [["3", [None]]]))
    root.destroy()
    for n, ok in casi:
        print(("ok    " if ok else "ROSSO ") + n)
    print(f"{sum(1 for _n, ok in casi if ok)}/{len(casi)}")
    return all(ok for _n, ok in casi)


if __name__ == "__main__":
    sys.exit(0 if prova() else 1)
