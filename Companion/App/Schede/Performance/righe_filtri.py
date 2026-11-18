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
from tema import CI as C, TEND  # noqa: E402
from widget import Tendina  # noqa: E402

VUOTA = "—"         # la voce di una tendina ancora da scegliere
QUALSIASI = "Any card"      # la tendina della carta senza una carta scelta


class CartaCompleta:
    """La casella del nome della carta (16 nov 2026, Autore: «nelle sezioni any card deve essere una riga di testo autocompletante dove scrivere il nome di
    una carta»): si scrive, sotto escono le carte che combaciano (prima quelle che cominciano cosi', poi quelle che contengono le lettere; al massimo
    MOSTRA), frecce e Invio o un clic scelgono, vuota vuol dire qualunque carta. Una scritta che non e' una carta non diventa un filtro.
    get() -> la carta scelta o QUALSIASI (come la tendina di prima, per le prove)."""
    MOSTRA = 8

    def __init__(self, tk, F, padre, carte, carta, scegli, larga=210):
        self.tk, self.F, self.carte, self.scegli = tk, F, list(carte), scegli
        self.scelta = carta
        self.fr = tk.Frame(padre, bg=TEND["bordo"])
        self.e = tk.Entry(self.fr, bg=TEND["campo"], fg=C["titolo"], insertbackground=C["titolo"], relief="flat", font=F(9), width=max(10, larga // 8),
                          highlightthickness=0, bd=0)
        self.e.pack(padx=1, pady=1, ipady=4, ipadx=6)
        self.lista, self.sel, self.trovate = None, 0, []
        self.metti_testo(carta)
        self.e.bind("<FocusIn>", lambda e: self.entra())
        self.e.bind("<KeyRelease>", self.tasto)
        self.e.bind("<Return>", lambda e: self.conferma())
        self.e.bind("<Escape>", lambda e: (self.chiudi_lista(), self.metti_testo(self.scelta)))
        self.e.bind("<FocusOut>", lambda e: self.e.after(150, self.esci))

    def metti_testo(self, carta):
        self.e.delete(0, "end")
        if carta:
            self.e.insert(0, carta)
            self.e.configure(fg=C["titolo"])
        else:
            self.e.insert(0, "any card")
            self.e.configure(fg=C["grigio"])

    def get(self):
        return self.scelta or QUALSIASI

    def entra(self):
        if not self.scelta:         # il segnaposto se ne va quando scrivi
            self.e.delete(0, "end")
            self.e.configure(fg=C["titolo"])

    def cerca(self, testo):
        """Le carte che combaciano: prima quelle che cominciano col testo, poi quelle che lo contengono (senza maiuscole)."""
        t = testo.strip().lower()
        if not t:
            return []
        inizio = [c for c in self.carte if c.lower().startswith(t)]
        dentro = [c for c in self.carte if t in c.lower() and c not in inizio]
        return (inizio + dentro)[:self.MOSTRA]

    def tasto(self, e):
        if e.keysym in ("Return", "Escape"):
            return
        if e.keysym in ("Down", "Up"):
            if self.trovate:
                self.sel = (self.sel + (1 if e.keysym == "Down" else -1)) % len(self.trovate)
                self.disegna_lista()
            return
        self.trovate, self.sel = self.cerca(self.e.get()), 0
        self.disegna_lista()

    def disegna_lista(self):
        tk = self.tk
        if not self.trovate:
            self.chiudi_lista()
            return
        if self.lista is None or not self.lista.winfo_exists():
            self.lista = tk.Toplevel(self.e)
            self.lista.overrideredirect(True)
            self.lista.configure(bg=TEND["bordo"])
        for w in self.lista.winfo_children():
            w.destroy()
        for j, c in enumerate(self.trovate):
            l_ = tk.Label(self.lista, text=c, anchor="w", padx=8, pady=3, font=self.F(9), cursor="hand2",
                          bg=TEND["sopra"] if j == self.sel else TEND["campo"], fg=C["titolo"] if j == self.sel else TEND["testo"])
            l_.pack(fill="x", padx=1, pady=(1 if j == 0 else 0, 1))
            l_.bind("<Button-1>", lambda e, c=c: self.prendi(c))
        self.lista.update_idletasks()
        self.lista.geometry(f"{max(self.e.winfo_width() + 2, self.lista.winfo_reqwidth())}x{self.lista.winfo_reqheight()}"
                            f"+{self.e.winfo_rootx() - 1}+{self.e.winfo_rooty() + self.e.winfo_height() + 2}")
        self.lista.lift()

    def chiudi_lista(self):
        if self.lista is not None:
            try:
                self.lista.destroy()
            except Exception:      # noqa: BLE001 - gia' chiusa
                pass
        self.lista, self.trovate = None, []

    def prendi(self, c):
        """Una carta scelta (o None: qualunque carta)."""
        self.chiudi_lista()
        cambia = c != self.scelta
        self.scelta = c
        self.metti_testo(c)
        if cambia:
            self.scegli(c or QUALSIASI)

    def conferma(self):
        """Invio: la carta evidenziata; una scritta che e' proprio una carta; vuota = qualunque carta. Il resto non e' un filtro."""
        t = self.e.get().strip()
        if self.trovate:
            return self.prendi(self.trovate[self.sel])
        if not t or t == "any card":
            return self.prendi(None)
        esatta = next((c for c in self.carte if c.lower() == t.lower()), None)
        if esatta:
            return self.prendi(esatta)
        self.metti_testo(self.scelta)

    def esci(self):
        """Il fuoco se ne va: la lista si chiude; una casella svuotata toglie la carta, il resto torna com'era."""
        try:
            if not self.e.winfo_exists() or self.e.focus_get() == self.e:
                return
        except Exception:      # noqa: BLE001 - finestra chiusa
            return
        if self.lista is not None and self.lista.winfo_exists():
            try:
                if str(self.lista.focus_get() or "").startswith(str(self.lista)):
                    return
            except Exception:      # noqa: BLE001
                pass
        self.chiudi_lista()
        t = self.e.get().strip()
        if not t:
            self.prendi(None)
        else:
            esatta = next((c for c in self.carte if c.lower() == t.lower()), None)
            if esatta and esatta != self.scelta:
                self.prendi(esatta)
            else:
                self.metti_testo(self.scelta)


FASE_QUALSIASI = "Any phase"


class Righe:
    def __init__(self, tk, F, padre, righe, campi, nome_campo, voci_di, on_cambio, bg=None, larga_campo=190, larga_voce=170, dopo=None, una_voce=False,
                 carte=None, fasi=None):
        """righe: la lista [[campo, [voci]]] (la modifica); campi: le chiavi del campo; nome_campo(k) come si legge; voci_di(k): le voci di quel campo;
        on_cambio(righe): dopo ogni cambio; dopo: il testo fra il campo e le voci (es. «cast»); una_voce: una voce sola per riga, niente + (le famiglie
        turno per turno con un valore per turno: l'attacco, la difesa, le pescate); carte: una tendina in piu' in fondo alla riga col nome della carta,
        facoltativa (16 nov 2026, Autore: «in ogni tendina in cui possiamo dire di aver castato qualcosa dobbiamo avere una tendina in piu' per inserire il
        nome specifico della carta se vogliamo»): la riga diventa [campo, [voci], carta o None]."""
        # fasi (18 nov 2026, Autore: «una tendina successiva che chiede la fase in cui vogliamo esplorare il turno»): [(codice, nome)]; la riga diventa
        # [campo, [voci], carta, fase]; None = Any phase
        self.una_voce, self.carte, self.fasi = una_voce, carte, fasi
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
        for i, r_ in enumerate(self.righe):
            campo, voci = r_[0], r_[1]
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
            for j, v in enumerate((voci or [None])[:1] if self.una_voce else (voci or [None])):
                tv = self._tendina(sottoriga, self.lv)
                tv.opzioni([VUOTA] + list(voci_ok), lambda v_, i=i, j=j: self.metti_voce(i, j, v_))
                tv.set(v if v is not None else VUOTA)
                tv.fr.pack(side="left", padx=(6, 0))
                self.tendine.append((i, j, tv))
            if not self.una_voce:
                piu = tk.Label(riga, text="+", bg="#161b25", fg=C["accento"], font=F(11, True), width=2, cursor="hand2")
                piu.pack(side="left", padx=(6, 0), ipady=1)
                piu.bind("<Button-1>", lambda e, i=i: self.aggiungi_voce(i))
            if self.carte is not None:      # il nome della carta, facoltativo: una casella che completa (vuota = qualunque carta)
                tk.Label(riga, text="card", bg=self.bg, fg=C["grigio"], font=F(8)).pack(side="left", padx=(10, 2))
                carta = self.righe[i][2] if len(self.righe[i]) > 2 else None
                tc = CartaCompleta(tk, F, riga, self.carte, carta, lambda v_, i=i: self.metti_carta(i, v_))
                tc.fr.pack(side="left", padx=(2, 0))
                self.tendine.append((i, "carta", tc))
            if self.fasi:       # la fase del turno, dopo il resto della riga
                tk.Label(riga, text="in", bg=self.bg, fg=C["grigio"], font=F(8)).pack(side="left", padx=(10, 2))
                tf = self._tendina(riga, 175)
                tf.opzioni([FASE_QUALSIASI] + [c_ for c_, _n in self.fasi], lambda v_, i=i: self.metti_fase(i, v_),
                           etichette={FASE_QUALSIASI: FASE_QUALSIASI, **dict(self.fasi)})
                fase = self.righe[i][3] if len(self.righe[i]) > 3 else None
                tf.set(fase if fase else FASE_QUALSIASI)
                tf.fr.pack(side="left", padx=(2, 0))
                self.tendine.append((i, "fase", tf))
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

    def metti_carta(self, i, v):
        while len(self.righe[i]) < 3:
            self.righe[i].append(None)
        self.righe[i][2] = None if v in (QUALSIASI, VUOTA) else v
        self.cambiato()

    def metti_fase(self, i, v):
        while len(self.righe[i]) < 4:
            self.righe[i].append(None)
        self.righe[i][3] = None if v in (FASE_QUALSIASI, VUOTA) else v
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
        self.righe.append([nuovo, [None]] + ([None] if self.carte is not None or self.fasi else []) + ([None] if self.fasi else []))
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
    r.fr.destroy()
    # la tendina della carta (16 nov 2026): in fondo alla riga, facoltativa
    rc = [["1", ["Creature"], None]]
    r2 = Righe(tk, F, root, rc, ["1", "2"], lambda k: f"Your T{k}", lambda k: ["Creature", "Instant"], lambda rr: None, carte=["Shock", "Opt"])
    r2.fr.pack(); root.update()
    casi.append(("la casella della carta c'e' ed e' vuota («any card»)", [t_.get() for _i, j_, t_ in r2.tendine if j_ == "carta"] == ["Any card"]))
    r2.metti_carta(0, "Opt")
    casi.append(("scelta una carta, la riga la porta; negativa: rimessa «Any card» torna None", rc[0][2] == "Opt"
                 and (r2.metti_carta(0, "Any card") or rc[0][2] is None)))
    # la tendina della fase (18 nov 2026): dopo la riga, «Any phase» di partenza; scelta una fase la riga la porta (quarto posto); Add line ha il posto
    rf = [["2", ["Creature"], None, None]]
    r3 = Righe(tk, F, root, rf, ["1", "2"], lambda k: f"Your T{k}", lambda k: ["Creature", "Instant"], lambda rr: None, carte=["Shock"],
               fasi=[("a", "main phase 1"), ("c", "combat"), ("z", "main phase 2")])
    r3.fr.pack(); root.update()
    casi.append(("la tendina della fase c'e', «Any phase» di partenza", [t_.get() for _i, j_, t_ in r3.tendine if j_ == "fase"] == ["Any phase"]))
    r3.metti_fase(0, "c")
    r3.aggiungi_riga()
    casi.append(("scelta Combat la riga la porta; Add line ha quattro posti; negativa: rimessa Any phase torna None", rf[0][3] == "c" and len(rf[1]) == 4
                 and (r3.metti_fase(0, "Any phase") or rf[0][3] is None)))
    r3.fr.destroy()
    # l'autocompletamento (16 nov 2026): «sh» trova Shock, «o» trova prima Opt (comincia) e poi Shock (contiene); Invio la sceglie; una scritta che non e' una
    # carta non diventa un filtro; svuotata, qualunque carta
    scelte = []
    cc = CartaCompleta(tk, F, root, ["Shock", "Opt", "Duress"], None, scelte.append)
    cc.fr.pack(); root.update()
    casi.append(("autocompleta: «o» -> prima Opt (comincia) poi Shock (contiene); «sh» -> Shock", cc.cerca("o") == ["Opt", "Shock"] and cc.cerca("sh") == ["Shock"]))
    cc.e.delete(0, "end"); cc.e.insert(0, "sh"); cc.trovate, cc.sel = cc.cerca("sh"), 0; cc.conferma()
    casi.append(("Invio sceglie la carta evidenziata", cc.get() == "Shock" and scelte == ["Shock"]))
    cc.e.delete(0, "end"); cc.e.insert(0, "zzz"); cc.trovate = []; cc.conferma()
    casi.append(("negativa: una scritta che non e' una carta non cambia niente", cc.get() == "Shock" and scelte == ["Shock"] and cc.e.get() == "Shock"))
    cc.e.delete(0, "end"); cc.trovate = []; cc.conferma()
    casi.append(("svuotata: qualunque carta", cc.get() == "Any card" and scelte[-1] == "Any card"))
    root.destroy()
    for n, ok in casi:
        print(("ok    " if ok else "ROSSO ") + n)
    print(f"{sum(1 for _n, ok in casi if ok)}/{len(casi)}")
    return all(ok for _n, ok in casi)


if __name__ == "__main__":
    sys.exit(0 if prova() else 1)
