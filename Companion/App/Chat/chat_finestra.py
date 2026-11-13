"""La chat nella finestra grande: la barra di scorrimento disegnata, il pulsante ultima azione, i messaggi. Mixin di Finestra (App/finestra.py)."""
import tkinter as tk

from chat_testi import FASI_EN, SEP_EN, azione_en, en, ordina_chat, scomponi
from icone import MEDAGLIE, emoji_png, icona_azione
from tema import C


class ChatFinestra:
    """La chat nella finestra grande: la barra di scorrimento disegnata, il pulsante ultima azione, i messaggi."""

    def barra_disegna(self):
        self.barra.delete("all")
        a, b = self.scorri["a"], self.scorri["b"]
        if b - a >= 0.999: return
        h = max(self.barra.winfo_height(), 1); y1 = a * h; y2 = max(b * h, y1 + 24)
        self.barra.create_rectangle(1, y1, 7, y2, fill=C["grigio"] if self.scorri["sopra"] or self.scorri["presa"] else C["muto"], outline="")


    def barra_set(self, a, b):
        self.scorri["a"], self.scorri["b"] = float(a), float(b); self.barra_disegna()
        if self.scorri["a"] > 0.001: self.torna.place(relx=1.0, x=-18, y=6, anchor="ne"); self.torna.lift()
        else: self.torna.place_forget()


    def barra_premi(self, e):
        h = max(self.barra.winfo_height(), 1); a, b = self.scorri["a"], self.scorri["b"]
        if not (a * h <= e.y <= b * h):           # clic fuori dal cursore: lo porta li'
            self.chat.yview_moveto(max(0.0, e.y / h - (b - a) / 2)); a = self.scorri["a"]
        self.scorri["presa"] = (e.y, a)


    def barra_trascina(self, e):
        if self.scorri["presa"]:
            y0, a0 = self.scorri["presa"]; self.chat.yview_moveto(a0 + (e.y - y0) / max(self.barra.winfo_height(), 1))


    def barra_lascia(self, e):
        self.scorri["presa"] = None; self.barra_disegna()


    def disegna_chat(self):
        if len(self.medaglie) > 400:          # gli stemmi disegnati: in una sessione lunga si rifanno quelli che servono (qui, prima di metterli in chat)
            self.medaglie.clear()
        # se hai fatto scorrere la chat per leggere, ci resti; se eri in cima, resti in cima sull'ultima azione (13 ott 2026)
        prima_y = self.chat.yview()[0]; in_cima = prima_y < 0.001
        self.chat.configure(state="normal"); self.chat.delete("1.0", "end"); self.linee.clear()
        ordine, evid = ordina_chat(self.P)
        def corpo(m):
            """Carte coinvolte (bianco, normale) e minidati (azzurro, piccolo), rientrati sotto l'azione."""
            _, carte, dati = scomponi(m)
            if not m.get("claude"):
                carte = [en(c) if isinstance(c, str) else (en(c[0]), en(c[1])) for c in carte]; dati = [en(d) for d in dati]
            g = m.get("grigio") or m["barrato"]
            if m.get("stemmi"):
                # gli stemmi del pick (Autore, 8 nov 2026: «lo stemma deve essere di fuoco per il pick di valore, poi oro argento
                # bronzo»): il fuoco sulla carta da prendere (la prima per stemma, poi quella del drafter quando arriva), poi oro,
                # argento e bronzo alle tre che seguono per stemma
                voci = list(m["stemmi"])
                fuoco = next((v for v in voci if v[0] == m.get("scelta")), voci[0])
                resto = [v for v in voci if v is not fuoco]
                # disegnati nello stile della finestra (Companion/App/Comune/stemmi_icone.py: corona di fuoco sul pick, scudi a fondo piatto), col
                # valore dentro; se il disegno non riesce restano le emoji col valore accanto
                for k, (nome, voto) in zip(("fuoco", "oro", "argento", "bronzo"), [fuoco] + resto):
                    chiave = (k, round(voto, 1), bool(g))
                    if chiave not in self.medaglie:
                        try:
                            import stemmi_icone
                            from PIL import ImageTk
                            self.medaglie[chiave] = ImageTk.PhotoImage(stemmi_icone.disegna(k, voto, 40, spento=bool(g)))
                        except Exception:
                            try:
                                self.medaglie[chiave] = tk.PhotoImage(file=emoji_png(*MEDAGLIE[k], 18)); self.medaglie[chiave].emoji = True
                            except Exception:
                                self.medaglie[chiave] = None
                    img = self.medaglie.get(chiave)
                    self.chat.insert("end", "  ")
                    if img is not None:
                        self.chat.image_create("end", image=img, align="center")
                    self.chat.insert("end", f"  {nome}", ("carta", "fatto") if g else ("carta",))
                    self.chat.insert("end", (f"   {voto:.1f}" if img is None or getattr(img, "emoji", False) else "") + "\n", ("nota", "fatto") if g else ("nota",))
            for c in carte:
                c, def_ = c if isinstance(c, tuple) else (c, "")      # una voce puo' avere la sua definizione sotto, in azzurro
                self.chat.insert("end", c + "\n", ("carta", "sotto", "fatto") if g else ("carta", "sotto"))
                if def_: self.chat.insert("end", def_ + "\n", ("nota", "sotto", "fatto") if g else ("nota", "sotto"))
            if dati:      # i minidati su una riga sola
                self.chat.insert("end", "  ·  ".join(dati) + "\n", ("nota", "sotto", "fatto") if g else ("nota", "sotto"))

        inizio_ev = None
        for m in ordine:
            if m["tipo"] == "msg" and m["id"] == evid: inizio_ev = self.chat.index("end-1c")
            if m["tipo"] == "fase":
                self.chat.insert("end", FASI_EN.get(m["testo"], m["testo"]) + "\n", ("fase", "fatto") if m["grigio"] else ("fase",))
                continue
            if m["tipo"] == "vuota":
                i0 = self.chat.index("end-1c")
                self.chat.insert("end", "NOTHING TO DO\n", ("vuota", "fatto") if m["grigio"] else ("vuota",))
                if m.get("id") == evid: self.chat.tag_add("evidenza", i0, "end-1c")      # la fase in corso e' vuota: si evidenzia questa riga
                continue
            if m["tipo"] == "sep":
                if self.chat.index("end-1c") != "1.0":
                    # la linea fra un turno e l'altro
                    ln = tk.Frame(self.chat, height=1, bg=C["filo"], width=max(self.chat.winfo_width() - 4, 50))
                    self.linee.append(ln)
                    self.chat.insert("end", "\n", "aria")
                    self.chat.window_create("end", window=ln)
                    self.chat.insert("end", "\n", "aria")
                self.chat.image_create("end", image=self.quadri[m["lato"]], padx=0)
                etichetta = " - ".join(x for x in (SEP_EN.get(m["testo"], m["testo"]).upper(), m.get("nome", "")) if x) + (f"   ·   turn {m['t']}" if m.get("t") else "")
                self.chat.insert("end", "  " + etichetta + "\n", "sep_" + m["lato"])
                continue
            if m.get("ico") == "vinta" and m["lato"] == "info":
                # la vittoria (Autore, 12 ott): come il letale, grande, in stampatello, al centro, fra due coppe
                if "coppa" not in self.az:
                    try:
                        self.az["coppa"] = tk.PhotoImage(file=emoji_png("🏆", "coppa", 26))
                    except Exception:
                        self.az["coppa"] = self.quadri["tu"]
                self.chat.insert("end", "\n", "aria")
                inizio = self.chat.index("end-1c")
                self.chat.image_create("end", image=self.az["coppa"]); self.chat.insert("end", "   PARTITA VINTA   ", "vittoria"); self.chat.image_create("end", image=self.az["coppa"])
                self.chat.insert("end", "\n")
                self.chat.tag_add("centro", inizio, "end-1c")
                self.chat.insert("end", "\n", "aria")
                continue
            if m.get("ico") == "letale":
                # il consiglio da non perdere: fuoco ai due lati, verde, grassetto, piu' grande
                if "letale" not in self.az:
                    try:
                        self.az["letale"] = tk.PhotoImage(file=emoji_png("\U0001F525", "fuoco", 20))
                    except Exception:
                        self.az["letale"] = self.quadri["tu"]
                self.chat.insert("end", "\n", "aria")
                self.chat.image_create("end", image=self.az["letale"]); self.chat.insert("end", "  ")
                self.chat.insert("end", "LETALE: ATTACCA CON", ("barrato",) if m["barrato"] else ("letale",))
                self.chat.insert("end", "  "); self.chat.image_create("end", image=self.az["letale"])
                self.chat.insert("end", "\n")
                corpo(m)
                if m["id"] == evid: self.chat.tag_add("evidenza", inizio_ev, "end-1c")
                self.chat.insert("end", "\n", "aria")
                continue
            chiave = (m.get("ico", "gioca"), "grigio" if m.get("grigio") else m["lato"])
            if chiave not in self.az:
                col = C["muto"] if m.get("grigio") else {"tu": C["verde"], "lui": C["rosso"], "info": C["arancio"]}[m["lato"]]
                if m.get("ico") == "vinta":
                    col = C["verde"]
                if m.get("ico") == "persa":
                    col = C["rosso"]
                try:
                    self.az[chiave] = tk.PhotoImage(file=icona_azione(chiave[0], col, 16))
                except Exception:
                    self.az[chiave] = self.quadri[m["lato"]]
            self.chat.image_create("end", image=self.az[chiave])
            tag = ("azione",)
            if m["barrato"]:
                tag = ("azione", "barrato")
            elif m.get("grigio"):
                tag = ("azione", "fatto")
            elif m["lato"] == "info":
                tag = ("vinta",) if m["testo"] == "Partita vinta" else (("persa",) if m["testo"] == "Partita persa" else ("azione", "info"))
            elif m.get("passo") and not m.get("fatto"):
                tag = ("adesso",)                      # il passo da fare: piu' grande, perche' e' l'unico che conta
            self.chat.insert("end", "  ")
            if m["nota"] and m["nota"].startswith("cambio") and not m["barrato"]:
                self.chat.insert("end", "CHANGED PLAN  ", ("nota",))
            self.chat.insert("end", scomponi(m)[0] if m.get("claude") else azione_en(scomponi(m)[0]), tag)
            self.chat.insert("end", "\n")
            corpo(m)
            if m["id"] == evid: self.chat.tag_add("evidenza", inizio_ev, "end-1c")
        self.chat.configure(state="disabled")
        if in_cima:
            self.chat.see("1.0"); self.root.after(300, lambda: self.chat.see("1.0") if self.chat.yview()[0] < 0.05 else None)
        else:
            self.chat.yview_moveto(prima_y)
        self.v_contro.set("" if self.P.avversario else (self.P.evento or ""))      # senza partita niente scritta (Autore, 10 nov 2026: «togli da in alto a sinistra waiting a game»)
        self.v_vite.set(f"you {self.P.vite[0]} · opponent {self.P.vite[1]}" if self.P.vite else "")
        tu, lui = self.P.piano or (None, None)
        mx = max([x for x in (tu, lui) if x] or [1])
        for k, n in (("tu", tu), ("lui", lui)):
            cv, col, lv = self.barre[k]
            lv.set((f"{n} turn" if n == 1 else f"{n} turns") if n else "-")
            q = (1 - (n - 1) / max(mx, 1) * 0.85) if n else 0
            cv.delete("all"); cv.update_idletasks(); cv.create_rectangle(0, 0, cv.winfo_width() * q, 6, fill=col, width=0)
