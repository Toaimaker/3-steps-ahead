"""Le sezioni a tendina della finestra di un mazzo e le sue tessere dei dati (Autore, 10 nov 2026: «riorganizziamo i dati in maniera piu' elegante nelle schede mazzo, parlo
di quelli messi in tesserine non dei grafici / mettiamoli su tendine espandibili»).

Una sezione e' una testata (triangolo, titolo, a destra un riassunto) e un corpo che si apre e si chiude col clic sulla testata; aperta o chiusa resta per tutti i mazzi
(Log_Arena/scheda_sezioni.json, per questo PC; le prove cambiano FILE). Le tessere sono riquadri tutti uguali su una griglia: il nome sopra, piccolo e spento, il dato
grande, sotto una riga grigia; a sinistra un filo del colore del dato (verde sopra il 50%, rosso sotto, grigio se neutro)."""
import json
import os

import carta_tela
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
        # la testata e' una tela sola (11 nov 2026, sessione Magic 13): il triangolo, il titolo, la spiegazione e a destra il riassunto, disegnati; prima 4-5 widget
        from tkinter import font as tkfont
        f_tit = F(8 if mini else 9, True)
        px, py = (4, 5) if mini else (8, 6)
        alto = tkfont.Font(font=f_tit).metrics("linespace") + 2 * py
        testa = tk.Canvas(box, height=alto, bg=fondo, highlightthickness=0, bd=0, cursor="hand2"); testa.pack(fill="x")
        testa.titolo = titolo.upper()
        if mini:
            tk.Frame(box, bg=C["filo"], height=1).pack(fill="x")
        corpo = tk.Frame(box, bg=C["scheda"], pady=4 if mini else 6)
        st = {"aperta": stato().get(chiave, aperta)}

        def disegna_testa(e=None):
            testa.delete("all")
            W, ym = max(testa.winfo_width(), 200), alto / 2
            lato = 10 if mini else 12
            testa.create_image(px, ym, image=DG.triangolo(lato, st["aperta"], C["accento"] if st["aperta"] else C["grigio"]), anchor="w")
            t = testa.create_text(px + lato + 6, ym, text=titolo.upper(), anchor="w", fill=C["titolo"], font=f_tit)
            if spiega:
                testa.create_text(testa.bbox(t)[2] + 8, ym, text=spiega, anchor="w", fill=C["grigio"], font=F(7))
            if riassunto:
                testa.create_text(W - px, ym, text=riassunto, anchor="e", fill=C["grigio"], font=F(8))
        testa.bind("<Configure>", disegna_testa)
        if mini:        # accesa sotto il puntatore: si vede che si apre
            testa.bind("<Enter>", lambda e: testa.configure(bg=C["cap"])); testa.bind("<Leave>", lambda e: testa.configure(bg=fondo))

        def mostra():
            disegna_testa()
            if st["aperta"]:
                f, corpo.da_riempire = getattr(corpo, "da_riempire", None), None
                if f is not None:       # il contenuto rimandato si fa alla prima apertura
                    f()
                corpo.pack(fill="x")
            else:
                corpo.pack_forget()

        def poi(f):
            """Il contenuto della sezione si fa adesso se e' aperta, se no alla prima apertura (11 nov 2026, sessione Magic 13: le categorie dell'analisi partono
            chiuse e le loro tabelle costavano widget a ogni finestra del mazzo)."""
            if st["aperta"]:
                f()
            else:
                corpo.da_riempire = f

        def cambia(e=None):
            st["aperta"] = not st["aperta"]
            s = stato(); s[chiave] = st["aperta"]; salva(s)
            mostra()
            if dopo:
                dopo()
        testa.bind("<Button-1>", cambia)
        mostra()
        corpo.testa_sezione, corpo.cambia_sezione, corpo.aperta_sezione = testa, cambia, (lambda: st["aperta"])
        corpo.poi = poi
        return corpo

    def tessere(self, padre, voci, colonne=4, clic=None, scelta=None):
        """I dati come tessere: voci [(nome, valore, colore, riga sotto)]; tutte della stessa misura su una griglia, il filo a sinistra del colore del dato.
        clic: {nome: funzione}, le tessere che si premono (puntatore a mano, accese sotto il puntatore); scelta: il nome della tessera premuta, col fondo e il bordo
        azzurri (on the play e on the draw: Autore, 10 nov 2026, «sulle schede del mazzo fai che i dati di analytics varino in base al premere on the draw on the play»).
        Dall'11 nov 2026 (sessione Magic 13, Note/Motore_Grafico_App.md) le tessere sono disegnate su una tela per gruppo, non 6 widget ciascuna: una finestra
        del mazzo ne aveva ~130 solo per le tessere. -> la tela, con .tessere_ = {nome: la tessera (carta_tela.CartaTela, .accesa)}."""
        tk, F = self.tk, self.F
        clic = clic or {}
        voci = list(voci)
        g = tk.Canvas(padre, bg=C["scheda"], highlightthickness=0, bd=0, height=1); g.pack(fill="x")
        sm = carta_tela.Smistatore(g)
        g.tessere_ = {}

        def disegna(e=None):
            W = g.winfo_width()
            if W < 50:          # non ancora a vista (una sezione chiusa): la larghezza del contenitore, se no una di ripiego; si rifa' quando arriva la vera
                W = padre.winfo_width() if padre.winfo_width() >= 50 else 640
            if W == getattr(g, "fatta", None):
                return
            g.fatta = W
            sm.svuota(); g.delete("all"); g.tessere_.clear()
            lw = (W - 6 * (colonne - 1)) / colonne
            y = 0
            for r0 in range(0, len(voci), colonne):
                fatte = []
                for k, voce in enumerate(voci[r0:r0 + colonne]):
                    et, val, col = voce[:3]
                    sotto = voce[3] if len(voce) > 3 else ""
                    accesa = et == scelta
                    fondo = C["sel"] if accesa else C["cap"]
                    t = carta_tela.CartaTela(g, round(k * (lw + 6)), y, round(lw), 1, sm, cursore="hand2" if et in clic else "")
                    t.accesa = accesa
                    t.create_rectangle(0, 0, round(lw) - 1, 1, fill=fondo, outline=C["accento"] if accesa else "", tags="fondo")
                    t.create_rectangle(0, 0, 3, 1, fill=C["accento"] if accesa else col or C["filo"], outline="", tags="filo")
                    a = t.create_text(12, 6, text=et.upper(), anchor="nw", fill=C["accento"] if accesa else C["muto"], font=F(6, True))
                    v = str(val)
                    b = t.create_text(12, t.bbox(a)[3] + 1, text=v, anchor="nw", fill=col or C["titolo"], font=F(13 if len(v) <= 9 else 10 if len(v) <= 16 else 8, True),
                                      width=round(lw) - 21)
                    if et in clic:
                        sotto = (sotto + " · " if sotto else "") + ("click: all games" if accesa else "click: only these")
                    c_ = t.create_text(12, t.bbox(b)[3] + 1, text=sotto or " ", anchor="nw", fill=C["grigio"], font=F(7), width=round(lw) - 21)
                    fatte.append((t, t.bbox(c_)[3] + 6, fondo))
                    g.tessere_[et] = t
                    if et in clic:
                        t.bind("<Button-1>", lambda e, f=clic[et]: f())
                        t.bind("<Enter>", lambda e, t=t: t.itemconfigure("fondo", fill=C["sel"]))
                        t.bind("<Leave>", lambda e, t=t, fondo=fondo: t.itemconfigure("fondo", fill=fondo))
                h = max(alto for _t, alto, _f in fatte)
                for t, _a, _f in fatte:         # una riga di tessere e' alta come la piu' alta
                    t.alta = h
                    for tg in ("fondo", "filo"):
                        x0, y0, x1, _y1 = g.coords(t.find_withtag(tg)[0])
                        g.coords(t.find_withtag(tg)[0], x0, y0, x1, y0 + h - 1)
                y += h + 6
            g.configure(height=max(1, y - 6))
        g.bind("<Configure>", disegna)
        disegna()       # subito: i numeri ci sono anche in una sezione chiusa (e chi legge tessere_ li trova)
        return g
