"""Il Farmer: il menu dei goal a slider e i metodi della pagina."""
import threading

import disegni as DG
import mazzi_salvati as MS
import risorse as RS

from dati_app import collezione, craft, jolly
from pagina_base import Pagina
from tema import CI as C, TEND


class MenuGoal:
    """Il menu dei goal: uno slider a percentuale per obiettivo (Autore, 8 nov 2026: «se fosse basata su degli slider che mi permettono di alzare o diminuire per % i goal personali che
    voglio raggiungere: es: alzo gold to gems al 80% e poi most rare e mythic al 10 e most pack al 10»). Gli slider si dividono il 100%: quando alzarne uno lo farebbe superare, gli altri
    scendono in proporzione (Autore, stesso giorno: «quando alzo uno slider autocorreggi le % degli altri»; prima c'era un tetto), a passi di 5 e col totale che torna 100; abbassandolo
    gli altri restano. I pallini restano colorati anche a 0 («lascia colorati in idle i pallini degli slider»). Tutti a zero e' No goal. Sotto, la spunta «Spend gold on packs»: accesa, il piano compra anche buste in oro; spenta (di partenza, 9 nov 2026) l'oro va negli eventi o resta oro.
    get() da' gli obiettivi accesi nell'ordine del menu, pesi() {obiettivo: percentuale} per Risorse.piano. Si trascina, o si clicca sulla barra; il piano si rifa' al rilascio."""

    PASSO = 5
    LARGO, ALTO, TESTA = 210, 18, 15

    def __init__(self, tk, padre, voci, F, cb, bg):
        self.voci, self.cb, self.F, self.bg = voci, cb, F, bg
        self.v = {k: 0 for k, _ in voci}
        # la spunta e' il permesso di spendere oro in buste, spenta di partenza (Autore, 9 nov 2026: «vedo che sul finale dei piani spreca gold in buste nonostante non sia flaggato»):
        # fino a quel giorno diceva «Spend as little gold as possible on packs» e spenta lasciava le buste libere, cioe' il contrario di come si legge
        self.oro_buste = False
        self.fr = tk.Frame(padre, bg=bg); self.cv = {}; self.lab = {}; self.num = {}
        testa = tk.Frame(self.fr, bg=bg); testa.pack(fill="x", pady=(0, 4))
        tk.Label(testa, text="GOAL", bg=bg, fg=C["titolo"], font=F(7, True), pady=0).pack(side="left")
        self.l_tot = tk.Label(testa, text="", bg=bg, fg=C["muto"], font=F(7), pady=0); self.l_tot.pack(side="right")
        # un goal e' una tela sola: il nome e la percentuale sopra, la barra sotto (11 nov 2026, sessione Magic 13: prima cinque widget per goal)
        self.nomi = dict(voci)
        for k, nome in voci:
            c = tk.Canvas(self.fr, width=self.LARGO, height=self.TESTA + self.ALTO, bg=bg, highlightthickness=0, cursor="hand2"); c.pack(fill="x", pady=(0, 5))
            l, n = "nome", "pc"
            c.bind("<Button-1>", lambda e, k=k: self.trascina(k, e.x))
            c.bind("<B1-Motion>", lambda e, k=k: self.trascina(k, e.x))
            c.bind("<ButtonRelease-1>", lambda e: self.rilascia())
            c.bind("<Configure>", lambda e, k=k: self.disegna_uno(k))
            self.cv[k], self.lab[k], self.num[k] = c, l, n
        # la spunta delle buste
        rb = tk.Frame(self.fr, bg=bg, cursor="hand2"); rb.pack(anchor="w", pady=(4, 0))
        self.c_oro = tk.Canvas(rb, width=13, height=13, bg=bg, highlightthickness=0, cursor="hand2"); self.c_oro.pack(side="left", padx=(0, 6))
        self.l_oro = tk.Label(rb, text="Spend gold on packs", bg=bg, fg=C["testo"], font=F(8), pady=0, cursor="hand2"); self.l_oro.pack(side="left")
        for w in (rb, self.c_oro, self.l_oro):
            w.bind("<Button-1>", lambda e: self.scambia_oro())
        self.mosso = False
        self.inizio = None
        self.disegna()

    # ---- i valori
    def get(self):
        return [k for k, _ in self.voci if self.v[k] > 0]

    def pesi(self):
        return {k: self.v[k] for k in self.get()}

    def libero(self, k):
        """Quanto puo' salire k: il 100% meno gli altri."""
        return 100 - sum(x for g, x in self.v.items() if g != k)

    def metti(self, pesi, oro_buste=None):
        """Rimette i pesi di un piano salvato: {obiettivo: %} o una lista (i piani di prima dell'8 nov 2026: parti uguali)."""
        if isinstance(pesi, dict):
            pesi = dict(pesi)
            if "buste" in pesi and "buste" not in self.v:      # Most packs e' confluito in Most wildcards (8 nov 2026)
                pesi["jolly"] = pesi.get("jolly", 0) + pesi.pop("buste")
            v = {k: float(x) for k, x in pesi.items() if k in self.v}
        else:
            ks = list(dict.fromkeys("jolly" if k == "buste" and "buste" not in self.v else k for k in (pesi or [])))
            ks = [k for k in ks if k in self.v]
            v = {k: 100.0 / len(ks) for k in ks}
        self.v = {k: v.get(k, 0) for k, _ in self.voci}
        if oro_buste is not None:
            self.oro_buste = bool(oro_buste)
        self.disegna()

    def scegli(self, k):
        """Accende o spegne un obiettivo e divide il 100% in parti uguali fra quelli accesi (le prove, e il clic sul nome)."""
        accesi = [g for g in self.get() if g != k] + ([] if self.v[k] > 0 else [k])
        self.metti(accesi)
        if self.cb:
            self.cb()

    def scambia_oro(self):
        self.oro_buste = not self.oro_buste
        self.disegna()
        if self.cb and self.get():
            self.cb()

    # ---- il trascinamento
    def imposta(self, k, pc, base=None):
        """k a pc. Gli altri accesi si muovono in proporzione perche' il totale resti 100 quando lo era gia', o quando lo passerebbe (Autore, 8 nov 2026: «i pallini non si stanno
        autocalibrando in base al movimento di uno»: abbassandone uno col totale a 100 gli altri restavano fermi). A passi di PASSO, i resti piu' grandi prendono il passo che avanza.
        Con il totale sotto 100 (i primi goal che accendi) gli altri restano."""
        b = dict(base if base is not None else self.v)      # base: i valori di quando hai preso il pallino, cosi' uno slider portato a 0 e poi indietro torna com'era
        pieno = sum(b.values()) >= 100
        self.v = dict(b)
        self.v[k] = pc
        altri = [g for g in b if g != k and b[g] > 0]
        tot = sum(b[g] for g in altri)
        posto = 100 - pc
        if not altri or (tot <= posto and not pieno):
            return
        quote = {g: b[g] * posto / tot for g in altri}
        giu = {g: int(q // self.PASSO) * self.PASSO for g, q in quote.items()}
        resto = int(round((posto - sum(giu.values())) / self.PASSO))
        for g in sorted(altri, key=lambda g: quote[g] - giu[g], reverse=True)[:max(0, resto)]:
            giu[g] += self.PASSO
        self.v.update(giu)

    def trascina(self, k, x):
        """Il pallino segue il mouse al pixel (12 nov 2026, Autore: «gli slider del farmer sarebbero piu' apprezzabili se con movimento piu' fluido»: fino a quel
        giorno saltava a passi di 5, circa 10 pixel, e a ogni movimento si ridisegnavano con PIL tutti gli slider). Gli altri si muovono in proporzione, anche
        loro al pixel; al rilascio tutto torna a passi di PASSO col totale a 100 (rilascia)."""
        L = max(40, self.cv[k].winfo_width())
        pc = max(0.0, min(1.0, (x - 8) / (L - 16))) * 100
        if self.inizio is None:
            self.inizio = dict(self.v)
            self.preso = k
        if abs(pc - self.v[k]) > 1e-9:
            self.imposta_fluido(k, pc, self.inizio); self.mosso = True
            self.aggiorna()

    def imposta_fluido(self, k, pc, base):
        """Come imposta, senza i passi: gli altri accesi in proporzione esatta."""
        b = dict(base)
        pieno = sum(b.values()) >= 100
        self.v = dict(b)
        self.v[k] = pc
        altri = [g for g in b if g != k and b[g] > 0]
        tot = sum(b[g] for g in altri)
        posto = 100 - pc
        if not altri or (tot <= posto and not pieno):
            return
        for g in altri:
            self.v[g] = b[g] * posto / tot

    def rilascia(self):
        k, base = getattr(self, "preso", None), self.inizio
        self.inizio, self.preso = None, None
        if self.mosso and k is not None and base is not None:      # i passi di PASSO e il totale a 100, come prima
            self.imposta(k, round(self.v[k] / self.PASSO) * self.PASSO, base)
            self.disegna()
        if self.mosso and self.cb:
            self.mosso = False
            self.cb()
        self.mosso = False

    # ---- il disegno
    def disegna_uno(self, k):
        """La barra (un'immagine nitida, fatta una volta per larghezza), la parte piena (una linea dritta, nitida da sola), il pallino (un'immagine fatta una volta,
        spostata), il nome e la percentuale. Trascinando cambiano solo coordinate e testi (aggiorna_uno)."""
        c = self.cv[k]; c.delete("all")
        L = max(40, c.winfo_width() if c.winfo_width() > 1 else self.LARGO)
        c.largo_ = L
        x0, x1, y = 8, L - 8, self.ALTO // 2
        c.create_text(0, self.TESTA / 2, text=self.nomi[k], anchor="w", fill=C["testo"], font=self.F(8), tags="nome")
        c.create_text(L, self.TESTA / 2, text="", anchor="e", fill=C["muto"], font=self.F(8, True), tags="pc")
        d = DG.Disegno(L, self.ALTO)
        d.linea([(x0, y), (x1, y)], TEND["bordo"], 4)
        c.foto_ = d.foto()
        c.create_image(0, self.TESTA, image=c.foto_, anchor="nw")
        c.create_line(x0, self.TESTA + y, x0, self.TESTA + y, fill=C["azzurro"], width=4, capstyle="round", tags="pieno")
        c.create_image(x0, self.TESTA + y, image=pomello(), tags="pomello")      # colorato anche a 0
        self.aggiorna_uno(k)

    def aggiorna_uno(self, k):
        c = self.cv[k]
        L = getattr(c, "largo_", None)
        if L is None:
            return self.disegna_uno(k)
        x0, x1, y = 8, L - 8, self.TESTA + self.ALTO // 2
        v = self.v[k]
        xv = x0 + (x1 - x0) * v / 100
        c.coords("pieno", x0, y, xv, y)
        c.itemconfigure("pieno", state="normal" if v > 0.5 else "hidden")
        c.coords("pomello", xv, y)
        c.itemconfigure("nome", fill=C["titolo"] if v > 0 else C["testo"])
        c.itemconfigure("pc", text=f"{round(v)}%", fill=C["azzurro"] if v > 0 else C["muto"])

    def aggiorna(self):
        for k in self.cv:
            self.aggiorna_uno(k)
        tot = round(sum(self.v.values()))
        self.l_tot.configure(text="No goal" if not tot else f"{tot}% assigned", fg=C["azzurro"] if tot == 100 else C["muto"])

    def disegna(self):
        for k in self.cv:
            c = self.cv[k]
            if getattr(c, "largo_", None) == max(40, c.winfo_width() if c.winfo_width() > 1 else self.LARGO):
                self.aggiorna_uno(k)
            else:
                self.disegna_uno(k)
        tot = round(sum(self.v.values()))
        self.l_tot.configure(text="No goal" if not tot else f"{tot}% assigned", fg=C["azzurro"] if tot == 100 else C["muto"])
        c = self.c_oro; c.delete("all"); on = self.oro_buste
        c.create_image(0, 0, image=DG.spunta(13, on, C["azzurro"], TEND["campo"], TEND["bordo"], C["fondo"]), anchor="nw")
        self.l_oro.configure(fg=C["titolo"] if on else C["testo"])


def pomello():
    """Il pallino dello slider: azzurro col bordo chiaro, nitido (disegni.py), fatto una volta."""
    def fa():
        d = DG.Disegno(15, 15)
        d.cerchio(7.5, 7.5, 6.5, riempi=C["azzurro"], bordo=C["titolo"], larghezza=1.5)
        return d
    return DG._icona(("pomello_farmer",), fa)


class Farmer:
    """Il Farmer: goal, voci, cambio dell'oro, soglie di win rate."""

    def applica_cambio(self):
        """Il cambio dell'oro secondo la spunta in testa al Farmer. -> dict(gpo, via)."""
        if self.R is None:
            return dict(gpo=RS.GEMME_PER_ORO, via="busta")
        return self.R.imposta_cambio(self.win_l(), self.win_cc(), busta=self.modo_cambio == "busta")

    def scegli_cambio(self, k):
        if k != self.modo_cambio:
            self.modo_cambio = k
            self.disegna_spunte_cambio()
            if self.R is not None and self.R.foto:
                self.disegna()

    def disegna_spunte_cambio(self, gpo_wr=None):
        """Le due spunte, col cambio scritto accanto: 1.000 oro = N gemme."""
        for k, c in self.c_cambio.items():
            on = k == self.modo_cambio
            c.delete("all")
            c.create_image(0, 0, image=DG.tondo(13, on, C["azzurro"], TEND["campo"], TEND["bordo"], C["fondo"]), anchor="nw")
            if k == "busta":
                testo = "Pack price · 1,000 gold = 200 gems in cards"
            else:
                testo = "My win rate" + (f" · 1,000 gold = {round(1000 * gpo_wr)} gems back" if gpo_wr is not None else "")
            self.l_cambio[k].configure(text=testo, fg=C["titolo"] if on else C["testo"])

    def win_l(self):
        """Il win rate limited dei conti: il tuo, spostato verso la media quando le partite sono poche (RS.win_stimato, 8 nov 2026)."""
        return RS.win_stimato(self.wr["limited"], self.n_wr["limited"])

    def win_cc(self):
        return RS.win_stimato(self.wr["constructed"], self.n_wr["constructed"])

    def mazzi_bersaglio(self):
        """I mazzi che puoi puntare: Wishlist e Laboratory, coi jolly che mancano (manca) e quelli che mancano oltre quelli che hai (oltre)."""
        d = MS.carica()
        coll, _ = collezione()
        jl, _ = jolly()
        out = []
        for sez in ("wish", "build"):
            for m in d.get(sez, []):
                tutte = {}
                for z in ("lista", "side", "comandante", "compagno"):
                    for n, q in (m.get(z) or {}).items():
                        tutte[n] = tutte.get(n, 0) + q
                if not tutte:
                    continue
                manca, _si = craft(tutte, coll, jl)
                oltre = {r: max(0, manca[r] - (jl or {}).get(r, 0)) for r in manca}
                out.append(dict(id=m["id"], nome=m.get("nome") or "Deck", sez=sez, manca=manca, oltre=oltre, jolly=jl))
        return out

    def bisogno(self):
        """Il mazzo scelto e i jolly rari e mitici che gli mancano oltre i tuoi. -> (mazzo, {R, M}) o (None, None)."""
        if "mazzo" not in self.goal.get():
            return None, None
        m = {x["id"]: x for x in self.mazzi_bersaglio()}.get(self.g_mazzo.get())
        return (m, {"R": m["oltre"]["R"], "M": m["oltre"]["M"]}) if m else (None, None)

    def opzioni_mazzi(self):
        """Rifa' la tendina del mazzo: la wishlist o il Laboratory possono essere cambiati."""
        mb = self.mazzi_bersaglio()
        def etich(m):
            o = m["oltre"]
            resto = " ".join(f"{o[r]}{r}" for r in ("M", "R", "U", "C") if o[r])
            coda = f" · {resto} to go" if resto else " · craftable now"
            return ("♥ " if m["sez"] == "wish" else "⚗ ") + m["nome"] + coda
        self.g_mazzo.opzioni([m["id"] for m in mb], lambda o: self.disegna_calcolo(), None, {m["id"]: etich(m) for m in mb})
        if mb and self.g_mazzo.get() not in [m["id"] for m in mb]:
            self.g_mazzo.set(mb[0]["id"])
        return mb

    def goal_iniziale(self):
        """Il Farmer parte dal mazzo da raggiungere, se ne hai uno in Wishlist o nel Laboratory a cui mancano jolly (Autore, 8 nov 2026: «ok» a «metterei questo come goal di base
        del Farmer»); se no da zero, come prima (6 nov 2026: «fai sempre partire il farmer da zero»)."""
        self.goal.metti({}, False)      # da zero, la spunta delle buste spenta (9 nov 2026: senza piu' Reach a deck il Farmer parte sempre da qui)

    def azzera(self, k):
        """Il reset di una voce del Farmer: zero, pagato in oro."""
        if self.R is None or not self.R.foto:
            return
        self.numeri_farmer()[k].metti(0, True)
        self.paga[k].metti("oro")
        self.disegna_calcolo()

    def voci_libere(self):
        return dict(n={k: x.get() for k, x in self.numeri_farmer().items()}, paga={k: x.get() for k, x in self.paga.items()})

    def numeri_farmer(self):
        return dict(quick=self.n_quick, premier=self.n_premier, costruiti=self.n_costruiti, buste=self.n_buste, mitiche=self.n_mitiche)

    def cambia_goal(self):
        """Dal «No goal» si tengono da parte i tuoi numeri; col goal le voci le decide il farmer; tornando a «No goal» tornano i tuoi."""
        libero = not self.goal.get()
        if libero and self.liberi:
            for k, x in self.numeri_farmer().items():
                x.metti(self.liberi["n"][k], True)
            for k, x in self.paga.items():
                x.metti(self.liberi["paga"][k])
            self.liberi = None
        elif not libero and self.liberi is None:
            self.liberi = self.voci_libere()
        for x in list(self.numeri_farmer().values()):
            x.blocca(not libero)
        for x in self.paga.values():
            x.bloccato = not libero
        if "mazzo" in self.goal.get():        # il mazzo da raggiungere: sotto gli slider
            self.opzioni_mazzi()
            self.g_mazzo.fr.pack(anchor="w", pady=(6, 0))
        else:
            self.g_mazzo.fr.pack_forget()
        if "carte" in self.goal.get():        # il set serve solo a questo obiettivo: sotto gli slider
            self.g_set.fr.pack(anchor="w", pady=(6, 0))
        else:
            self.g_set.fr.pack_forget()
        self.disegna_calcolo()

    def applica_goal(self, win):
        """Con un obiettivo il farmer si imposta da solo: le voci vengono dal piano, i draft pagano prima coi token. -> il piano, o None senza obiettivo."""
        obiettivo = self.goal.get()
        if not obiettivo:
            return None
        win_c = self.win_cc()
        _m, need = self.bisogno()
        pi = self.R.piano(self.goal.pesi(), win, self.g_set.get(), win_c=win_c, oro_buste=self.goal.oro_buste, mazzo=need)
        vo = pi["voci"]
        for k, x in self.numeri_farmer().items():
            x.metti(vo[k], True)
        self.paga["quick"].metti("oro"); self.paga["premier"].metti("token" if vo["tp"] else "oro")
        for k in ("costruiti", "buste", "mitiche"):
            self.paga[k].metti("oro")
        pi["buste_gemme"] = vo["buste_gemme"]
        self.ultimo_pi = pi
        return pi

    def righe_soglie(self, win, win_c):
        """Le soglie di win rate del goal, dal filo in sottofondo: [testo] se sono pronte, [] mentre si calcolano. Sono circa 100 piani, ~2 s di calcolo: fino all'8 nov 2026 si facevano
        nel filo della finestra e ogni nuovo goal la fermava fino a 1,7 s (collaudo a tappeto). Il filo calcola soltanto; la finestra guarda ogni 200 ms se sono pronte e ridisegna."""
        R = self.R
        pesi, set_, ob, need = self.goal.pesi(), self.g_set.get(), self.goal.oro_buste, self.bisogno()[1]
        k = (tuple(sorted(pesi.items())), round(win, 4), round(win_c, 4), set_, ob, tuple(sorted((need or {}).items())), round(R.gpo, 6), R.via_cambio)
        cache = self.__dict__.setdefault("_soglie_pronte", {})
        if k in cache:
            return cache[k]
        if Pagina.SUBITO:          # le prove: subito, nello stesso filo
            cache[k] = self._righe_soglie(R.soglie(pesi, win, win_c, set_, oro_buste=ob, mazzo=need), win, win_c)
            return cache[k]
        if getattr(self, "_soglie_filo", None) != k:
            self._soglie_filo = k
            gpo, via = R.gpo, R.via_cambio

            def lavora():
                try:
                    so = R.soglie(pesi, win, win_c, set_, oro_buste=ob, mazzo=need)
                    if (R.gpo, R.via_cambio) == (gpo, via):          # il cambio non e' cambiato a meta': il risultato vale
                        cache[k] = self._righe_soglie(so, win, win_c)
                except Exception as e:
                    print("soglie:", f"{type(e).__name__}: {e}")
                    cache[k] = []

            threading.Thread(target=lavora, daemon=True).start()

            def guarda(n=0):
                if k in cache:
                    if self._soglie_filo == k and self.a_vista():
                        self.disegna_calcolo(grafico=False)
                elif n < 300 and self._soglie_filo == k:
                    self.fr.after(200, lambda: guarda(n + 1))
            self.fr.after(200, guarda)
        return []

    def _righe_soglie(self, so, win, win_c):
        """Le soglie in parole: una riga per tipo di evento, solo se la rotta cambia davvero."""
        nomi = dict(quick="Quick Draft", premier="Premier Draft", costruiti="Constructed", buste="Packs")
        out = []
        for k, tit, tuo in (("limited", "Limited", win), ("constructed", "Constructed", win_c)):
            pezzi = so[k]
            fuse = []
            for da, a, r in pezzi:
                t = nomi[r[0]]          # la voce che prende piu' oro: il modo di reinvestire le gemme cambia di poco e confonde
                if fuse and fuse[-1][2] == t:
                    fuse[-1][1] = a
                else:
                    fuse.append([da, a, t])
            if len(fuse) > 1:
                out.append(f"{tit} WR {round(100 * tuo)}%: " + " · ".join(f"{'up to ' + str(a) + '%' if i == 0 else ('from ' + str(da) + '%' if i == len(fuse) - 1 else str(da) + '-' + str(a) + '%')} {t}" for i, (da, a, t) in enumerate(fuse)))
        return out or ["The best route doesn't change between 30% and 80% win rate"]

    def dati_farmer(self):
        """Il piano del Farmer per il grafico; None senza un piano."""
        if not self.calcolo or not any(r["volte"] for r in self.calcolo[0]["righe"]):
            return None
        return self.R.confronto(self.calcolo[0])
