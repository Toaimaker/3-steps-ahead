"""Le sezioni a tendina della finestra di un mazzo e le sue tessere dei dati (Autore, 10 nov 2026: «riorganizziamo i dati in maniera piu' elegante nelle schede mazzo, parlo
di quelli messi in tesserine non dei grafici / mettiamoli su tendine espandibili»).

Una sezione e' una testata (triangolo, titolo, a destra un riassunto) e un corpo che si apre e si chiude col clic sulla testata; aperta o chiusa resta per tutti i mazzi
(Log_Arena/scheda_sezioni.json, per questo PC; le prove cambiano FILE). Le tessere sono riquadri tutti uguali su una griglia: il nome sopra, piccolo e spento, il dato
grande, sotto una riga grigia; a sinistra un filo del colore del dato (verde sopra il 50%, rosso sotto, grigio se neutro)."""
import json
import os

import disegni as DG

from ambiente import LOGDIR
from tema import CI as C

FILE = [os.path.join(LOGDIR, "scheda_sezioni.json")]


def stato():
    try:
        with open(FILE[0], encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def salva(d):
    try:
        with open(FILE[0], "w", encoding="utf-8") as f:
            json.dump(d, f)
    except OSError:
        pass


class SezioniMazzo:
    """Le sezioni a tendina e le tessere della finestra del mazzo (mixin di PaginaStandard)."""

    def sezione_tendina(self, padre, chiave, titolo, riassunto="", aperta=True, dopo=None, mini=False, spiega=""):
        """Una sezione a tendina: -> il corpo (un Frame), da riempire. aperta: com'e' la prima volta; poi decide l'ultima scelta. dopo: chiamata dopo ogni apertura o
        chiusura (la finestra rifa' la rotella e lo scorrimento). mini: la tendina piccola dentro una sezione (le categorie dell'analisi: Autore, 10 nov 2026, «metti
        ogni categoria in delle mini tendine espandibili così non abbiamo tutti i dati in un colpo solo»), sul fondo della scheda col filo sotto, accesa sotto il
        puntatore; spiega: una riga grigia accanto al titolo."""
        tk, F = self.tk, self.F
        fondo = C["scheda"] if mini else C["cap"]
        box = tk.Frame(padre, bg=C["scheda"]); box.pack(fill="x", pady=(0, 2 if mini else 8))
        testa = tk.Frame(box, bg=fondo, padx=4 if mini else 8, pady=5 if mini else 6, cursor="hand2"); testa.pack(fill="x")
        if mini:
            tk.Frame(box, bg=C["filo"], height=1).pack(fill="x")
        tri = tk.Label(testa, bg=fondo, cursor="hand2"); tri.pack(side="left", padx=(0, 6))
        tk.Label(testa, text=titolo.upper(), bg=fondo, fg=C["titolo"], font=F(8 if mini else 9, True), cursor="hand2", pady=0).pack(side="left")
        if spiega:
            tk.Label(testa, text=spiega, bg=fondo, fg=C["grigio"], font=F(7), cursor="hand2", pady=0).pack(side="left", padx=(8, 0))
        if riassunto:
            tk.Label(testa, text=riassunto, bg=fondo, fg=C["grigio"], font=F(8), cursor="hand2", pady=0).pack(side="right")
        corpo = tk.Frame(box, bg=C["scheda"], pady=4 if mini else 6)
        st = {"aperta": stato().get(chiave, aperta)}
        if mini:        # accesa sotto il puntatore: si vede che si apre
            pezzi = [testa, *testa.winfo_children()]

            def luce(on):
                for w in pezzi:
                    if w.winfo_exists():
                        w.configure(bg=C["cap"] if on else fondo)
            for w in pezzi:
                w.bind("<Enter>", lambda e: luce(True)); w.bind("<Leave>", lambda e: luce(False))

        def mostra():
            tri.configure(image=DG.triangolo(10 if mini else 12, st["aperta"], C["accento"] if st["aperta"] else C["grigio"]))
            if st["aperta"]:
                corpo.pack(fill="x")
            else:
                corpo.pack_forget()

        def cambia(e=None):
            st["aperta"] = not st["aperta"]
            s = stato(); s[chiave] = st["aperta"]; salva(s)
            mostra()
            if dopo:
                dopo()
        for w in [testa, *testa.winfo_children()]:
            w.bind("<Button-1>", cambia)
        mostra()
        corpo.testa_sezione, corpo.cambia_sezione, corpo.aperta_sezione = testa, cambia, (lambda: st["aperta"])
        return corpo

    def tessere(self, padre, voci, colonne=4, clic=None, scelta=None):
        """I dati come tessere: voci [(nome, valore, colore, riga sotto)]; tutte della stessa misura su una griglia, il filo a sinistra del colore del dato.
        clic: {nome: funzione}, le tessere che si premono (puntatore a mano, accese sotto il puntatore); scelta: il nome della tessera premuta, col fondo e il bordo
        azzurri (on the play e on the draw: Autore, 10 nov 2026, «sulle schede del mazzo fai che i dati di analytics varino in base al premere on the draw on the play»)."""
        tk, F = self.tk, self.F
        clic = clic or {}
        g = tk.Frame(padre, bg=C["scheda"]); g.pack(fill="x")
        g.tessere_ = {}
        for j in range(colonne):
            g.columnconfigure(j, weight=1, uniform="tessere")
        for i, voce in enumerate(voci):
            et, val, col = voce[:3]
            sotto = voce[3] if len(voce) > 3 else ""
            accesa = et == scelta
            fondo = C["sel"] if accesa else C["cap"]
            t = tk.Frame(g, bg=fondo, highlightthickness=1 if accesa else 0, highlightbackground=C["accento"])
            t.grid(row=i // colonne, column=i % colonne, sticky="nsew", padx=(0, 6 if i % colonne < colonne - 1 else 0), pady=(0, 6))
            tk.Frame(t, bg=C["accento"] if accesa else col or C["filo"], width=3).pack(side="left", fill="y")
            d = tk.Frame(t, bg=fondo, padx=9, pady=6); d.pack(side="left", fill="both", expand=True)
            tk.Label(d, text=et.upper(), bg=fondo, fg=C["accento"] if accesa else C["muto"], font=F(6, True), pady=0, anchor="w").pack(fill="x")
            v = str(val)
            tk.Label(d, text=v, bg=fondo, fg=col or C["titolo"], font=F(13 if len(v) <= 9 else 10 if len(v) <= 16 else 8, True), pady=0, anchor="w", justify="left",
                     wraplength=150).pack(fill="x")
            if et in clic:
                sotto = (sotto + " · " if sotto else "") + ("click: all games" if accesa else "click: only these")
            tk.Label(d, text=sotto or " ", bg=fondo, fg=C["grigio"], font=F(7), pady=0, anchor="w", justify="left", wraplength=150).pack(fill="x")
            g.tessere_[et] = t
            if et in clic:
                pezzi = [t, d, *d.winfo_children()]

                def luce(on, pezzi=pezzi, fondo=fondo):
                    for w in pezzi:
                        if w.winfo_exists():
                            w.configure(bg=C["sel"] if on else fondo)
                for w in pezzi:
                    w.configure(cursor="hand2")
                    w.bind("<Button-1>", lambda e, f=clic[et]: f())
                    w.bind("<Enter>", lambda e, luce=luce: luce(True))
                    w.bind("<Leave>", lambda e, luce=luce: luce(False))
        return g
