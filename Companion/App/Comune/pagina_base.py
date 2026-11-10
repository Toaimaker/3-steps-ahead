"""La pagina di una scheda: riquadri, griglie, tabelle, il grafico del win rate. Ogni scheda la estende."""
import sys
import tkinter.font as tkfont

import capsule as CAP
import collezione_carte as CC
import disegni as DG
import risorse as RS

from icone import emoji_png, icona_set, logo_lega, nome_set
from tema import CI as C, COL_LEGA, PERSA, SFONDO_FASCIA, SFONDO_LINEA, VINTA
from widget import Tendina


def prepara_capsule(d):
    """Le capsule conoscono anche le carte della collezione. Sono 15.000 voci: lo fa il filo dei dati, e una volta sola per ogni lettura."""
    if d and not d.get("capsule"):
        CAP.aggiungi(CC.per_capsule(d))
        d["capsule"] = True


class Pagina:
    """La base: schede con la cornice della finestra grande, i simboli di mana, i colori e i font.
    Una pagina nascosta non si disegna (Autore, 6 nov 2026: «il companion ora ci mette un po' a caricare»): i dati arrivano all'avvio e ogni 10 minuti, e il disegno delle
    schede che nessuno guardava bloccava la finestra per 1-3 secondi. Si segna e si disegna quando torna a vista."""

    SUBITO = False      # le prove in una finestra nascosta disegnano lo stesso
    # le schede della finestra grande stanno una sopra l'altra, tutte montate alla loro misura (Autore, 9 nov 2026: «quando passo
    # da una scheda a un'altra c'e' un leggero refresh e caricamento degli elementi … fare in modo che aprendo una scheda tutto sia
    # gia' pronto»): una scheda dietro e' «viewable» per Tk ma non si vede. DIETRO tiene i percorsi delle cornici coperte.
    DIETRO = set()
    MOSTRA_SCHEDA = None    # la finestra grande: porta a vista una scheda (il builder apre la Collection)

    def __init__(self, tk, padre, F, mana):
        self.tk, self.F, self.mana = tk, F, mana
        self.fr = tk.Frame(padre, bg=C["fondo"])
        self.sporca = False
        self.al_davanti(lambda e: self.se_sporca())
        # in cima il menu dell'espansione, poi il grafico a tutta larghezza, sotto due colonne (la pagina prende tutta la finestra)
        self.barra_menu = tk.Frame(self.fr, bg=C["fondo"]); self.barra_menu.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        self.alto = tk.Frame(self.fr, bg=C["fondo"]); self.alto.grid(row=1, column=0, columnspan=2, sticky="ew")
        self.col = [tk.Frame(self.fr, bg=C["fondo"]) for _ in range(2)]
        for i, c in enumerate(self.col):
            self.fr.columnconfigure(i, weight=1, uniform="pg")
            c.grid(row=2, column=i, sticky="nsew", padx=(0, 10) if i == 0 else 0)
        self.fr.rowconfigure(2, weight=1)
        # il menu a tendina: «Tutte le espansioni» o un set
        self.esp = Tendina(tk, self.barra_menu, "Set", F, larga=270)
        if "--apri-tendina" in sys.argv:      # collaudo: la tendina dell'espansione si apre da sola dopo il caricamento
            self.fr.after(12000, lambda: self.esp.apri() if self.davanti() else None)
        self.esp.fr.pack(side="left")
        self.opzioni = []
        self.loghi = {}
        self.coppa = {}
        for lato in (16, 20):
            try:
                self.coppa[lato] = tk.PhotoImage(file=emoji_png("\U0001F3C6", "coppa", lato))
            except Exception:
                pass

    def al_davanti(self, f):
        """f quando la pagina torna a vista: <Map> se la pagina era smontata, <<Davanti>> quando la finestra la porta davanti alle altre schede."""
        self.fr.bind("<Map>", f, add="+")
        self.fr.bind("<<Davanti>>", f, add="+")

    def davanti(self):
        """Vero se la pagina si vede: montata e non coperta da un'altra scheda."""
        if not self.fr.winfo_viewable():
            return False
        p = str(self.fr)
        return not any(p == d or p.startswith(d + ".") for d in Pagina.DIETRO)

    def a_vista(self):
        """Vero se la pagina si vede; se no resta segnata per quando torna."""
        if Pagina.SUBITO or self.davanti():
            return True
        self.sporca = True
        return False

    def ridisegna(self):
        if self.a_vista():
            self.sporca = False
            self.disegna()

    def se_sporca(self):
        if self.sporca:
            self.ridisegna()

    def scheda(self, titolo, destra="", espandi=False, col=0):
        tk, F = self.tk, self.F
        cornice = tk.Frame(self.alto if col == "alto" else (self.col[col] if isinstance(col, int) else col), bg=C["filo2"], padx=1, pady=1)
        cornice.pack(fill="both" if espandi else "x", expand=espandi, pady=(0, 8))
        dentro = tk.Frame(cornice, bg=C["scheda"]); dentro.pack(fill="both", expand=True)
        cap = tk.Frame(dentro, bg=C["cap"]); cap.pack(fill="x")
        self.cap_tit = tk.Label(cap, text=titolo.upper(), bg=C["cap"], fg=C["capo"], font=F(8, True)); self.cap_tit.pack(side="left", padx=10, pady=5)
        v = tk.StringVar(value=destra)      # il sottotitolo di recap non si disegna (Autore, 4 nov 2026, vedi finestra_companion)
        tk.Frame(dentro, bg=C["filo"], height=1).pack(fill="x")
        corpo = tk.Frame(dentro, bg=C["scheda"]); corpo.pack(fill="both", expand=True, padx=10, pady=8)
        return corpo, v

    def mana_label(self, padre, colori, bg):
        tk = self.tk
        f = tk.Frame(padre, bg=bg)
        for k in colori:
            if k in self.mana:
                tk.Label(f, image=self.mana[k], bg=bg).pack(side="left", padx=(0, 2))
            else:
                tk.Label(f, text=k, bg=bg, fg=C["testo"], font=self.F(8)).pack(side="left")
        return f

    def etichetta(self, padre, testo, bg=None):
        """Il nome di un dato: sta sopra il dato, in stampatello maiuscolo bianco (Autore, 17 ott 2026)."""
        return self.tk.Label(padre, text=testo.upper(), bg=bg or C["scheda"], fg=C["titolo"], font=self.F(7, True), pady=0, justify="left")

    def riga(self, padre, sx, dx, col=None, forte=True):
        tk = self.tk
        r = tk.Frame(padre, bg=C["scheda"]); r.pack(fill="x", pady=1)
        tk.Label(r, text=sx, bg=C["scheda"], fg=C["testo"], font=self.F(9)).pack(side="left")
        tk.Label(r, text=dx, bg=C["scheda"], fg=col or C["titolo"], font=self.F(9, forte)).pack(side="right")

    def svuota(self, w):
        for x in w.winfo_children():
            x.destroy()

    def barra(self, padre, q, col):
        tk = self.tk
        cv = tk.Canvas(padre, height=6, bg=C["traccia"], highlightthickness=0); cv.pack(side="left", fill="x", expand=True)
        cv.bind("<Configure>", lambda e: (cv.delete("all"), cv.create_rectangle(0, 0, e.width * q, 6, fill=col, width=0)))

    TUTTE = "All sets"

    def opzioni_menu(self, sets, predefinito):
        """Riempie il menu con «Tutte le espansioni» e i set per data di uscita, dal piu' nuovo; la prima volta sceglie il set in corso."""
        tk = self.tk
        sets = RS.ordina_set([x for x in dict.fromkeys(sets) if x])
        opz = [self.TUTTE] + sets
        if opz != self.opzioni:
            self.opzioni = opz
            # accanto a ogni espansione il suo simbolo originale (Autore, 18 ott 2026)
            icone = {}
            for s in sets:
                if ("set", s) not in self.loghi:
                    f = icona_set(s, 16)
                    self.loghi[("set", s)] = tk.PhotoImage(file=f) if f else None
                if self.loghi[("set", s)] is not None:
                    icone[s] = self.loghi[("set", s)]
            self.esp.opzioni(opz, lambda o: (setattr(self, "scelto", True), self.disegna()), icone,
                             {s: f"{nome_set(s)} ({s})" if nome_set(s) else s for s in sets})
        if "--espansione" in sys.argv:          # collaudo: la finestra si apre su un'espansione
            predefinito = sys.argv[sys.argv.index("--espansione") + 1].replace("tutte", self.TUTTE)
        if not getattr(self, "scelto", False) or self.esp.get() not in opz:
            self.esp.set(predefinito if predefinito in opz else self.TUTTE)

    def filtro(self):
        """Il set scelto nel menu, o None per tutte le espansioni."""
        v = self.esp.get()
        return None if not v or v == self.TUTTE else v

    def griglia(self, padre, voci, colonne=3, nota="", grande=16, largo_nota=390, icona=None, stretta=False):
        """I tuoi numeri: un riquadro per dato, tutti uguali e allineati, col nome sopra in maiuscolo bianco e il dato sotto.
        voci: [(nome, valore, colore)]; un valore intero sono coppe (i trofei). Sotto, una nota piccola se serve.
        grande: la misura del dato (piu' piccola dove la colonna e' stretta, come nella scheda di un mazzo); icona: un'immagine
        accanto a ogni dato."""
        tk, F = self.tk, self.F
        self.svuota(padre)
        g = tk.Frame(padre, bg=C["scheda"]); g.pack(fill="x")
        for j in range(colonne):
            g.columnconfigure(j, weight=1, uniform="num")
        for i, voce in enumerate(voci):
            et, val, col = voce[:3]
            c = tk.Frame(g, bg=C["cap"], padx=6 if stretta else 10, pady=4 if stretta else 6)
            c.grid(row=i // colonne, column=i % colonne, sticky="nsew", padx=(0, 6 if i % colonne < colonne - 1 else 0), pady=(0, 6))
            self.etichetta(c, et, C["cap"]).pack(anchor="w")
            if isinstance(val, int) and not isinstance(val, bool):
                self.coppe(c, val, 20, bg=C["cap"]).pack(anchor="w", pady=(4, 0))
            else:
                r_ = tk.Frame(c, bg=C["cap"]); r_.pack(anchor="w")
                ic = voce[4] if len(voce) > 4 else icona      # una voce puo' avere l'icona sua: il ROI e' in gemme anche sull'oro
                if ic:
                    tk.Label(r_, image=ic, bg=C["cap"], pady=0).pack(side="left", padx=(0, 6))
                tk.Label(r_, text=val, bg=C["cap"], fg=col or C["titolo"], font=F(grande if len(str(val)) <= 11 else min(grande, 11), True), pady=0,
                         wraplength=130, justify="left").pack(side="left")
                if len(voce) > 3 and voce[3]:      # una riga piccola sotto il dato: il suo valore in gemme, nelle Risorse
                    tk.Label(c, text=voce[3], bg=C["cap"], fg=C["azzurro"], font=F(7), pady=0).pack(anchor="w")
        if nota:
            tk.Label(padre, text=nota, bg=C["scheda"], fg=C["muto"], font=F(7), anchor="w", justify="left", wraplength=largo_nota).pack(fill="x")

    def logo_rango(self, rango, tipo="constructed", alto=26):
        """Il logo della lega di un rango («Silver 3»), una volta sola, per il riquadro Rank (Autore, 6 nov 2026: «nel pannellino che indica la lega di appartenenza mettici il logo»). None se non c'e'."""
        lega = (rango or "").split(" ")[0]
        chiave = (tipo, lega, alto)
        if chiave not in self.loghi:
            f = logo_lega(tipo, lega, alto) if lega else None
            self.loghi[chiave] = self.tk.PhotoImage(file=f) if f else None
        return self.loghi[chiave]

    def coppe(self, padre, n, lato=16, bg=None):
        """I trofei come «coppa × N» (Autore, 17 ott 2026: «abbiamo la coppa ma non il dato che dice quante: coppa x N
        trofei»); a zero la coppa e' spenta e il numero grigio."""
        tk, F = self.tk, self.F
        bg = bg or C["scheda"]
        f = tk.Frame(padre, bg=bg)
        img = self.coppa.get(lato)
        if img and n:
            tk.Label(f, image=img, bg=bg).pack(side="left")
        tk.Label(f, text=f"× {n}" if (img and n) else str(n), bg=bg, fg=C["titolo"] if n else C["muto"],
                 font=F(16 if lato >= 20 else 9, True), pady=0).pack(side="left", padx=(4, 0) if (img and n) else 0)
        return f

    def tabella(self, padre, intestazioni, righe, allarga=0, evidenzia=(), padx=6):
        """Una tabella a griglia: le intestazioni (maiuscolo bianco) sopra le loro colonne, le righe a fasce alterne perche'
        l'occhio segua la riga. intestazioni: [(testo, allineamento "w" o "e")]; righe: liste di celle, ognuna una funzione
        che riceve il riquadro della cella (il suo colore e' quello della riga: c["bg"]) e ci disegna dentro. La colonna
        «allarga» prende lo spazio in piu'; le righe in «evidenzia» hanno il fondo azzurro scuro. -> le righe (liste di riquadri)."""
        tk, F = self.tk, self.F
        g = tk.Frame(padre, bg=C["scheda"]); g.pack(fill="x")
        g.columnconfigure(allarga, weight=1)
        for j, (t, al) in enumerate(intestazioni):
            h = tk.Frame(g, bg=C["scheda"], padx=padx, pady=3); h.grid(row=0, column=j, sticky="nsew")
            self.etichetta(h, t).pack(side="left" if al == "w" else "right")
        out = []
        for i, celle in enumerate(righe, 1):
            bg = C["sel"] if (i - 1) in evidenzia else (C["cap"] if i % 2 else C["scheda"])
            riga = []
            for j, f in enumerate(celle):
                c = tk.Frame(g, bg=bg, padx=padx, pady=2); c.grid(row=i, column=j, sticky="nsew")
                f(c); riga.append(c)
            out.append(riga)
        return out

    def cella(self, testo, col=None, forte=False, grande=9, lato="right"):
        tk, F = self.tk, self.F
        return lambda c: tk.Label(c, text=testo, bg=c["bg"], fg=col or C["testo"], font=F(grande, forte), pady=0).pack(side=lato)

    def cella_wr(self, w, n):
        """La cella del win rate: la barra da 0 a 100 con la tacca al 50% e il numero."""
        return lambda c: self.barra_wr(c, w, n)

    def barra_wr(self, padre, w, n):
        """Il win rate come barra da 0 a 100 con la tacca al 50%: azzurra sopra il 50, rossa sotto; il numero accanto."""
        tk, F = self.tk, self.F
        q = w / n if n else 0
        tk.Label(padre, text=f"{round(100 * q)}%" if n else "-", width=4, anchor="e", bg=padre["bg"], fg=C["titolo"],
                 font=F(9, True), pady=0).pack(side="right")
        cv = tk.Canvas(padre, height=8, width=80, bg=padre["bg"], highlightthickness=0); cv.pack(side="right", padx=(0, 4))

        def disegna(e=None, cv=cv, q=q):
            cv.delete("all"); W = cv.winfo_width()
            cv.create_rectangle(0, 1, W, 7, fill=C["traccia"], width=0)
            cv.create_rectangle(0, 1, W * q, 7, fill=VINTA if q >= 0.5 else PERSA, width=0)
            cv.create_line(W / 2, 0, W / 2, 8, fill=C["muto"])
        cv.bind("<Configure>", disegna)

    def grafico(self, padre, punti, inizi=(), leghe=(), trofei=(), vuoto="No games", altezza=160, tipo_lega="limited"):
        """Il grafico cartesiano del win rate: in orizzontale le partite, in verticale la percentuale di partite vinte
        dall'inizio, la linea del 50% marcata, le tacche dove comincia un draft (o un giorno), i passaggi di lega e le coppe.
        Il puntatore mostra la partita sotto, con una riga verticale e un punto sulla linea. punti: [(etichetta, % vinte)];
        inizi: [(indice, etichetta)]; leghe: [(indice, testo, lega)]; trofei: [indice]. La scala si regola sulle partite
        dalla sesta in poi (le prime saltano fra 0 e 100%): quelle prima restano tagliate al bordo."""
        tk, F = self.tk, self.F
        self.svuota(padre)
        riposo = f"{punti[-1][1]:.0f}% after {len(punti)} games" if punti else ""
        v_info = tk.StringVar(value=riposo)
        r_info = tk.Frame(padre, bg=C["scheda"]); r_info.pack(fill="x", pady=(0, 4))
        tk.Label(r_info, textvariable=v_info, bg=C["scheda"], fg=C["testo"], font=F(8), anchor="w").pack(side="left")
        segni_lega = {t[0] for _, t, _ in leghe}
        if segni_lega & {"↓", "↺"}:      # sulla riga sotto la testata i segni che ci sono: il logo sulla vetta si legge da solo
            tk.Label(r_info, text=" · ".join(x for s_, x in (("↓", "↓ down"), ("↺", "↺ new season")) if s_ in segni_lega), bg=C["scheda"], fg=C["grigio"], font=F(7)).pack(side="right")
        H = altezza
        cv = tk.Canvas(padre, height=H, bg=C["scheda"], highlightthickness=0); cv.pack(fill="x")
        if not punti:
            cv.configure(height=40); cv.create_text(4, 20, text=vuoto, anchor="w", fill=C["grigio"], font=F(9))
            return
        import math
        scala = [v for _, v in punti[5:]] or [v for _, v in punti]
        alto = min(100, math.ceil(max(scala + [55]) / 10) * 10)
        basso = max(0, math.floor(min(scala + [45]) / 10) * 10)
        geo = {}

        def disegna(e=None):
            cv.delete("all")
            W = cv.winfo_width(); sx, dx_, su, giu = 34, 8, (44 if leghe else 14), 20         # margini: asse y a sinistra, sopra lo spazio per un logo su una vetta alta, date sotto
            larg, alt = W - sx - dx_, H - su - giu
            X = lambda i: sx + larg * (i - 1) / max(len(punti) - 1, 1)     # la prima partita sul bordo sinistro, l'ultima sul destro
            Y = lambda v: su + alt * (alto - max(basso, min(alto, v))) / (alto - basso)
            geo.update(X=X, Y=Y, sx=sx, larg=larg, su=su)
            # lo sfondo: fasce orizzontali alterne ogni 10% e linee leggerissime (Autore, 18 ott 2026), il 50% piu' marcato;
            # i numeri dell'asse a ogni linea
            gradini = list(range(basso, alto + 1, 10))
            for k, v in enumerate(gradini[:-1]):
                if k % 2 == 0:
                    cv.create_rectangle(sx, Y(v + 10), W - dx_, Y(v), fill=SFONDO_FASCIA, width=0)
            for v in gradini:
                cv.create_line(sx, Y(v), W - dx_, Y(v), fill=C["muto"] if v == 50 else SFONDO_LINEA)
                cv.create_text(sx - 6, Y(v), text=f"{v}%", anchor="e", fill=C["grigio"] if v == 50 else C["muto"], font=F(7))
            cv.create_line(sx, su, sx, H - giu, fill=C["filo"])
            ultima_x = -99
            for i, et in inizi:
                x = X(i + 1)                   # i = partite prima del draft: la sua prima partita e' i + 1
                cv.create_line(x, H - giu, x, H - giu + 4, fill=C["muto"])
                if x - ultima_x > 34:                      # le date non si accavallano; l'ultima, vicino al bordo, si allinea a destra
                    cv.create_text(x, H - giu + 6, text=et, anchor="ne" if x > cv.winfo_width() - 20 else "n", fill=C["muto"], font=F(7)); ultima_x = x
            # la linea del win rate, dalla prima partita
            xy = [X(1), Y(punti[0][1])] if len(punti) == 1 else []
            for i, (_, v) in enumerate(punti, 1):
                xy += [X(i), Y(v)]
            # la stagione nuova non e' un livello raggiunto: una linea tratteggiata col segno e la lega in fondo
            fine_st = -999
            for i, testo, lega in leghe:
                if testo.startswith("↺"):
                    x = X(i)
                    cv.create_line(x, su, x, H - giu, fill=C["muto"], dash=(3, 3))
                    if x - fine_st > 56:
                        cv.create_text(x + 3, H - giu - 2, text=testo, anchor="sw", fill=C["muto"], font=F(7, True)); fine_st = x
            linee = [(list(zip(xy[0::2], xy[1::2])), C["accento"], 2, None)]       # la linea, i raccordi e i punti in uno strato nitido (disegni.py), sotto i loghi
            punti_ = []
            # i loghi delle leghe sulle vette (Autore, 6 nov 2026: «i loghi delle leghe li mettiamo proprio sul grafico sulle vette dove il livello e' stato raggiunto»): il logo sta sul
            # punto della linea della partita in cui hai preso la lega, una retrocessione sotto la linea. Due loghi che si toccano si impilano
            posati = []
            for i, testo, lega in leghe:
                if testo.startswith("↺"):
                    continue
                img = self.loghi.get((tipo_lega, lega))
                if img is None:
                    f = logo_lega(tipo_lega, lega, 30)
                    if f:
                        img = self.loghi[(tipo_lega, lega)] = tk.PhotoImage(file=f)
                px, py, col, sale = X(i), Y(punti[i - 1][1]), COL_LEGA.get(lega, C["grigio"]), not testo.startswith("↓")
                w_, h_ = (img.width(), img.height()) if img else (tkfont.Font(font=F(7, True)).measure(lega), 14)
                lx = max(sx + w_ / 2, min(W - dx_ - w_ / 2, px))
                ly = py - 9 - h_ if sale else py + 9
                for _ in range(len(posati)):
                    if not any(abs(lx - a_) < (w_ + b_) / 2 + 2 and abs(ly - c_) < h_ + 2 for a_, b_, c_ in posati):
                        break
                    ly += -(h_ + 3) if sale else h_ + 3
                ly = max(1, min(H - giu - h_, ly))
                posati.append((lx, w_, ly))
                linee.append(([(px, py), (lx, ly + h_ if sale else ly)], col, 1, None))
                punti_.append((px, py, 3.5, col, C["scheda"], 1))
                if img:
                    cv.create_image(lx, ly, image=img, anchor="n", tags="sopra")
                else:
                    cv.create_text(lx, ly, text=lega, anchor="n", fill=col, font=F(7, True), tags="sopra")
            for i in trofei:                         # una coppa sopra la linea alla fine di ogni draft da 7 vinte
                img = self.coppa.get(16)
                if img:
                    cv.create_image(X(i), Y(punti[i - 1][1]) - 12, image=img, tags="sopra")
            punti_.append((X(len(punti)), Y(punti[-1][1]), 5, C["accento"], C["scheda"], 2))
            cv.strato_ = DG.tratti(W, H, linee, punti_)
            cv.create_image(0, 0, image=cv.strato_, anchor="nw")
            cv.tag_raise("sopra")

        def sopra(e):
            if not geo:
                return
            i = round((e.x - geo["sx"]) / geo["larg"] * max(len(punti) - 1, 1)) + 1
            i = max(1, min(len(punti), i))
            et, v = punti[i - 1]
            cv.delete("cursore")
            x, y = geo["X"](i), geo["Y"](v)
            cv.create_line(x, geo["su"], x, H - 20, fill=C["grigio"], tags="cursore")
            cv.create_image(x, y, image=DG.punto(10, C["titolo"], C["scheda"], 2), tags="cursore")
            v_info.set(f"{et} · win rate {v:.0f}%")
        cv.bind("<Configure>", disegna); cv.bind("<Motion>", sopra)
        cv.bind("<Leave>", lambda e: (cv.delete("cursore"), v_info.set(riposo)))
