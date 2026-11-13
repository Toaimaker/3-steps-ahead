"""La roadmap del piano del Farmer."""
import datetime

import disegni as DG
import risorse as RS

from tema import CI as C, VINTA


class Roadmap:
    """La roadmap del piano: Create, Dismiss, estensione, adattamento all'income in piu', il disegno dei giorni."""

    def riprendi(self, p):
        """Rimette nel Farmer goal, voci e pagamenti del piano."""
        if p.get("set"):
            self.g_set.set(p["set"])
        self.modo_cambio = p.get("cambio", "wr")
        self.disegna_spunte_cambio()
        if p.get("mazzo"):
            self.opzioni_mazzi()
            self.g_mazzo.set(p["mazzo"])
        self.goal.metti(p.get("pesi") or p.get("goal") or [], p.get("oro_buste", True) if p.get("spunta_buste") == 2 else False)     # i piani di prima del 9 nov: la spunta spenta voleva dire niente oro in buste
        for k, x in self.numeri_farmer().items():
            x.metti(p["n"][k], True)
        for k, x in self.paga.items():
            x.metti(p["paga"][k])
        self.liberi = None
        self.cambia_goal()

    def crea(self):
        """Create: fissa il piano del Farmer e ne fa la roadmap, dal giorno di oggi."""
        if not self.calcolo or not any(r["volte"] for r in self.calcolo[0]["righe"]):
            return
        e, win, win_c = self.calcolo
        oggi = datetime.date.today()
        self.piano = dict(self.R.roadmap(e, oggi, win, win_c, solo_set=self.solo_roadmap()), goal=self.goal.get(), pesi=self.goal.pesi(), oro_buste=self.goal.oro_buste, spunta_buste=2, cambio=self.modo_cambio, mazzo=self.g_mazzo.get() if "mazzo" in self.goal.get() else None, set=self.g_set.get(), n=self.voci_libere()["n"], paga=self.voci_libere()["paga"], partenza=self.R.fatti(oggi), attese=self.R.attese(e))      # le risorse attese al mese: Roadmap check le confronta con quelle vere
        RS.salva_piano(self.piano, self.FILE_PIANO)
        self.mostra_piano()
        self.disegna_road()

    def solo_roadmap(self):
        """Il set di ogni voce per la roadmap, come l'ha contato il piano del goal (risorse._piano, «solo»): col goal «carte di un set», anche nel mix, i draft di quel set stanno nelle
        sue finestre e non nel primo draft aperto (9 nov 2026). Senza goal carte, o senza goal, None: il primo che si apre."""
        pi = getattr(self, "ultimo_pi", None)
        return (pi or {}).get("solo") if "carte" in (self.goal.get() or []) else None

    def estendi_piano(self):
        """Finiti i 30 giorni il piano va avanti da solo coi soldi e il calendario di adesso, finche' non lo cambi (Autore, 6 nov 2026: «se non cambio piano tra un mese e l'altro, la roadmap va avanti infinita»).
        I giorni nuovi si aggiungono in fondo: la roadmap scorre, quel che hai fatto resta segnato."""
        p, oggi = self.piano, datetime.date.today()
        if not p or oggi.isoformat() <= p["al"] or not self.calcolo or not any(r["volte"] for r in self.calcolo[0]["righe"]):
            return
        e, win, win_c = self.calcolo
        r = self.R.roadmap(e, oggi, win, win_c, solo_set=self.solo_roadmap())
        p["giorni"] += r["giorni"]; p["al"] = r["al"]; p["fuori"] = r["fuori"]; p["totale"] += r["totale"]
        p["cassa"], p["cassa_dal"] = r["cassa"], r["cassa_dal"]
        RS.salva_piano(p, self.FILE_PIANO)

    def adatta_piano(self, oggi=None):
        """L'income in piu' entra nella roadmap (Autore, 9 nov 2026: «fa che la roadmap sappia adattarsi nel caso ci fosse income extra rispetto all'atteso»): se oggi hai almeno il
        prezzo di una busta in piu' della cassa che il piano aspettava (le azioni non ancora fatte contano come gia' spese), il piano si rifa' da oggi coi soldi veri e il goal di prima;
        quel che hai fatto resta. Il Farmer ha gia' il piano coi soldi di adesso (self.calcolo). Un income piu' basso dell'atteso non cambia niente: la roadmap resta e le azioni restano da fare.
        -> il surplus se ha rifatto la roadmap, se no None."""
        p, oggi = self.piano, oggi or datetime.date.today()
        if not p or self.R is None or not self.calcolo or not any(r["volte"] for r in self.calcolo[0]["righe"]):
            return None
        x = self.R.surplus(p, oggi)
        if not x or not x["scatta"]:
            return None
        e, win, win_c = self.calcolo
        r = self.R.roadmap(e, oggi, win, win_c, solo_set=self.solo_roadmap())
        self.R.adatta(p, r, oggi, x)
        RS.salva_piano(p, self.FILE_PIANO)
        return x

    def togli(self):
        """Dismiss: il piano si abbandona e il Farmer riparte da zero, senza goal."""
        self.piano = None
        RS.togli_piano(self.FILE_PIANO)
        self.mostra_piano()
        self.disegna_road()
        self.liberi = None
        for x in self.numeri_farmer().values():
            x.metti(0, True)
        for x in self.paga.values():
            x.metti("oro")
        self.goal_iniziale()
        self.cambia_goal()

    def mostra_piano(self):
        """Create o Dismiss nel Farmer: la roadmap accanto si aggiorna da sola."""
        (self.b_crea if self.piano else self.b_togli).pack_forget()
        (self.b_togli if self.piano else self.b_crea).pack(side="right")

    def disegna_road(self):
        """La roadmap su una tela sola: una riga verticale, i giorni con qualcosa da fare divisi per settimana, a ogni giorno cosa fare, dove, quanto costa e la cassa che resta. Scorre dal giorno del piano."""
        p, R, cv, F = self.piano, self.R, self.cv_r, self.F
        cv.delete("all")
        self.largo_r = cv.winfo_width()
        if not p or R is None:
            self.l_piano.configure(text="No plan yet")
            self.l_stato.configure(text="Set the Farmer and press Create")
            return
        pt = lambda x: f"{round(x):,}"
        oggi = datetime.date.today()
        dal, al = datetime.date.fromisoformat(p["dal"]), datetime.date.fromisoformat(p["al"])
        fatte, tot = R.segna(p, oggi)
        pesi_ = p.get("pesi") or {g: 100 / len(p["goal"]) for g in p.get("goal") or []}
        nomi = " · ".join(f"{self.GOAL_CORTI[g]} {round(x)}%" if len(pesi_) > 1 else self.GOAL_CORTI[g] for g, x in pesi_.items())
        self.l_piano.configure(text=f"Goal: {nomi}" if nomi else "Your own plan")
        ad = (p.get("adattato") or [None])[-1]
        extra = ""
        if ad:      # l'ultimo adattamento all'income in piu'
            d_ = datetime.date.fromisoformat(ad["data"])
            pezzi = [f"+{pt(ad[k])} {n}" for k, n in (("oro", "gold"), ("gemme", "gems")) if ad.get(k, 0) > 0]
            extra = f" · adapted {d_.day} {d_:%b}" + (f" to {', '.join(pezzi)} extra" if pezzi else "")
        self.l_stato.configure(text=f"{dal.day} {dal:%b} - {al.day} {al:%b} · {fatte} of {tot} done{extra}")
        L = max(self.largo_r, 260)
        X0, X1, DX = 8, 28, L - 6
        y, inizio, fine, sett, y_oggi = 8, None, None, None, None
        for g in p["giorni"]:
            d = datetime.date.fromisoformat(g["data"])
            s_ = d - datetime.timedelta(days=d.weekday())
            if s_ != sett:
                sett = s_
                y += 6 if inizio is not None else 0
                cv.create_text(X1, y + 6, text=f"WEEK OF {s_.day} {s_:%b}".upper(), anchor="w", fill=C["titolo"], font=F(7, True))
                cv.create_line(X1 + 96, y + 6, DX, y + 6, fill=C["filo"])
                y += 20
            azioni = g["azioni"]
            tutte = bool(azioni) and all(a["stato"] == "fatta" for a in azioni)
            ritardo = any(a["stato"] == "ritardo" for a in azioni)
            passato = d < oggi
            col = VINTA if tutte else C["arancio"] if ritardo else C["azzurro"] if d == oggi else C["muto"] if passato else C["testo"]
            inizio = y + 8 if inizio is None else inizio
            fine = y + 8
            if y_oggi is None and d >= oggi:
                y_oggi = y
            cv.create_image(X0, y + 8, image=DG.punto(11, col if azioni or d == oggi else C["scheda"], col, 2), tags="punto")
            data = cv.create_text(X1, y + 8, text=f"{d:%a} {d.day} {d:%b}", anchor="w", fill=C["titolo"] if not passato else C["grigio"], font=F(9, True))
            if d == oggi:
                cv.create_text(cv.bbox(data)[2] + 8, y + 8, text="TODAY", anchor="w", fill=C["azzurro"], font=F(7, True))
            # la cassa stimata a fine giornata
            x = DX
            for val, ic in ((g["gemme"], "gemma"), (g["oro"], "oro")):
                t = cv.create_text(x, y + 8, text=pt(val), anchor="e", fill=C["grigio"], font=F(8))
                x = cv.bbox(t)[0] - 4
                img = self.icona(ic, 14)
                if img:
                    cv.create_image(x, y + 8, image=img, anchor="e")
                x -= 24
            y += 22
            if not azioni:
                cv.create_text(X1, y + 4, text="Plan starts: nothing to spend today", anchor="w", fill=C["grigio"], font=F(8))
                y += 18
            for a in azioni:
                fatta = a["stato"] == "fatta"
                nome = a["nome"] + (f" {a['set']}" if a["set"] else "") + (f" x{a['quanti']}" if a["quanti"] > 1 else "")
                prezzo = " + ".join(t for t in (f"{pt(a['oro'])} gold" if a["oro"] else "", f"{pt(a['gemme'])} gems" if a["gemme"] else "", f"{a['token']} token{'s' if a['token'] > 1 else ''}" if a["token"] else "") if t)
                sotto = a["dove"]
                if a["chiude"] and (datetime.date.fromisoformat(a["chiude"]) - d).days <= 7:
                    fin = datetime.date.fromisoformat(a["chiude"])
                    sotto += f" · closes {fin.day} {fin:%b}"
                if a["stato"] == "ritardo":
                    sotto += f" · late, {a['fatte']} of {a['quanti']} done" if a["fatte"] else " · late"
                if fatta:
                    nome = "✓ " + nome
                cv.create_text(X1, y + 7, text=nome, anchor="w", fill=VINTA if fatta else C["testo"], font=F(9))
                cv.create_text(DX, y + 7, text=prezzo, anchor="e", fill=C["grigio"] if fatta else C["titolo"], font=F(9, True))
                cv.create_text(X1, y + 23, text=sotto, anchor="w", fill=C["arancio"] if a["stato"] == "ritardo" else C["grigio"], font=F(7))
                y += 36
            y += 6
        cv.create_line(X0, inizio, X0, fine, fill=C["filo"], width=2)
        cv.tag_raise("punto")
        y += 4
        for x in p["fuori"]:
            q = x["quanti"]
            perche = "no window open by " + f"{al.day} {al:%b}" if x["perche"] == "closed" else f"not enough gold or gems by {al.day} {al:%b}"
            t_ = cv.create_text(X1, y, text=f"{x['nome']} x{q}: {perche}", anchor="nw", fill=C["arancio"], font=F(8, True), width=DX - X1)
            y = cv.bbox(t_)[3] + 6
        t_ = cv.create_text(X1, y, text=f"Plan ends {al.day} {al:%b}. Balances are estimates from your average income.", anchor="nw", fill=C["grigio"], font=F(7), width=DX - X1)
        y = cv.bbox(t_)[3]
        cv.configure(scrollregion=(0, 0, L, y + 24))
        if y_oggi is not None and d >= oggi:     # si apre sul giorno di oggi
            cv.yview_moveto(max(0, y_oggi - 34) / (y + 24))
