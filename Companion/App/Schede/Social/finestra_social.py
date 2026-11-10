"""La colonna fissa a destra, in ogni scheda: il profilo e l'elenco degli amici in stile Battle.net (Autore, 6 nov 2026: «colonna fissa a destra», «a elenco», «stile battlenet»).
In cima il profilo con la sua immagine, sotto gli amici divisi per gruppi: avatar quadrato, barra di stato a sinistra, nome azzurro per chi ha giocato da poco, una riga grigia sotto.
I dati stanno in social.py. L'elenco e' disegnato su una tela sola, senza widget per riga: si ridisegna spesso e la tela non ha il problema delle etichette tolte a pagina nascosta.

    py -I -X utf8 Companion/App/Schede/Social/finestra_social.py --prova     fuori schermo
"""
import os, sys
_casa = os.path.dirname(os.path.abspath(__file__))      # si sale fino a percorsi.py, che mette nel sys.path tutte le cartelle del Companion
while not os.path.isfile(os.path.join(_casa, "percorsi.py")):
    _casa = os.path.dirname(_casa)
if _casa not in sys.path:
    sys.path.insert(0, _casa)
import percorsi  # noqa: E402
import collections, threading, webbrowser, zlib
import capsule as CAP
import collezione_carte as CC
import social as SO

LARGA, LATO, RIGA, GRUPPO = 268, 60, 46, 26
TINTE = ("#2f6f9f", "#7a4fa3", "#3d8a5f", "#a3573d", "#8a7a3d", "#a33d6b", "#3d8a8a", "#5a64a8")


def fa_avatar(sorgente, uscita, lato=LATO * 2):
    """Un quadrato al centro dell'immagine, con gli angoli un po' arrotondati."""
    from PIL import Image, ImageDraw
    im = Image.open(sorgente).convert("RGBA")
    q = min(im.size)
    x, y = (im.width - q) // 2, (im.height - q) // 2
    im = im.crop((x, y, x + q, y + q)).resize((lato, lato), Image.LANCZOS)
    m = Image.new("L", (lato * 3, lato * 3), 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, m.width - 1, m.height - 1), radius=lato // 3, fill=255)
    im.putalpha(m.resize(im.size, Image.LANCZOS))
    os.makedirs(os.path.dirname(uscita), exist_ok=True)      # la cartella di un account nuovo (10 nov 2026)
    im.save(uscita)


class ColonnaSocial:

    def __init__(self, tk, padre, F, P, pulsante, logo, cartella=None):
        self.tk, self.F, self.P, self.logo = tk, F, P, logo
        self.d = SO.Dati(cartella) if cartella else SO.Dati()
        self.pronte, self.lavoro, self.righe, self.sopra, self.img, self.leghe = collections.deque(), False, [], None, None, {}
        self.fr = tk.Frame(padre, bg=P["scheda"], width=LARGA, highlightthickness=1, highlightbackground=P["filo"]); self.fr.pack_propagate(False)
        # Discord in testa a tutto, col pulsante di accesso (Autore, 10 nov 2026: «in testa a tutto metti il discord con pulstnte di accesso»; blocco_discord.py)
        from blocco_discord import BloccoDiscord
        self.discord = BloccoDiscord(tk, self.fr, F, P, pulsante)
        b = tk.Frame(self.fr, bg=P["scheda"]); b.pack(fill="x", padx=12, pady=(12, 8))
        self.cv_av = tk.Canvas(b, width=LATO, height=LATO, bg=P["scheda"], highlightthickness=0, cursor="hand2"); self.cv_av.pack(side="left")
        self.cv_av.bind("<Button-1>", lambda e: self.apri(self.f_av))
        t = tk.Frame(b, bg=P["scheda"]); t.pack(side="left", fill="x", expand=True, padx=(10, 0))
        self.l_nome = tk.Label(t, text=self.d.profilo["nome"], bg=P["scheda"], fg=P["acciaio"], font=F(12, True), anchor="w", pady=0); self.l_nome.pack(fill="x")
        self.l_stato = tk.Label(t, text="", bg=P["scheda"], fg=P["grigio"], font=F(8), anchor="w", pady=0); self.l_stato.pack(fill="x")
        self.ranghi = {}
        g = tk.Frame(self.fr, bg=P["scheda"]); g.pack(fill="x", padx=12, pady=(0, 8))
        g.columnconfigure(0, weight=1, uniform="r"); g.columnconfigure(1, weight=1, uniform="r")
        for i, (k, nome) in enumerate((("constructed", "Constructed"), ("limited", "Limited"))):
            c = tk.Frame(g, bg=P["cap"], padx=8, pady=6); c.grid(row=0, column=i, sticky="ew", padx=(0, 4) if i == 0 else 0)
            tk.Label(c, text=nome.upper(), bg=P["cap"], fg=P["titolo"], font=F(7, True), pady=0, anchor="w").pack(fill="x")
            l = tk.Label(c, text="-", bg=P["cap"], fg=P["testo"], font=F(9, True), anchor="w", compound="left", padx=0, pady=2); l.pack(fill="x")
            self.ranghi[k] = l
        # la scelta dell'immagine: si apre cliccando l'avatar
        self.f_av = f = tk.Frame(self.fr, bg=P["scheda"])
        tk.Label(f, text="CARD NAME", bg=P["scheda"], fg=P["titolo"], font=F(7, True), pady=0, anchor="w").pack(fill="x", padx=12)
        self.e_carta = self.campo(f)
        self.e_carta.bind("<Return>", lambda e: self.usa_carta())
        r = tk.Frame(f, bg=P["scheda"]); r.pack(fill="x", padx=12, pady=(0, 6))
        r.columnconfigure(0, weight=1, uniform="b"); r.columnconfigure(1, weight=1, uniform="b")
        self.b_carta = pulsante(tk, F, r, "Use card", False, self.usa_carta, alto=30, bg=P["scheda"]); self.b_carta.configure(width=1); self.b_carta.grid(row=0, column=0, sticky="ew", padx=(0, 4))
        self.b_file = pulsante(tk, F, r, "From file", False, self.usa_file, alto=30, bg=P["scheda"]); self.b_file.configure(width=1); self.b_file.grid(row=0, column=1, sticky="ew")
        self.v_av = tk.StringVar()
        tk.Label(f, textvariable=self.v_av, bg=P["scheda"], fg=P["rosso_t"], font=F(8), anchor="w", pady=0).pack(fill="x", padx=12, pady=(0, 6))
        tk.Frame(self.fr, bg=P["filo"], height=1).pack(fill="x")
        self.sotto_profilo = self.fr.winfo_children()[-1]
        # gli amici
        c = tk.Frame(self.fr, bg=P["cap"]); c.pack(fill="x")
        self.l_amici = tk.Label(c, text="FRIENDS", bg=P["cap"], fg=P["capo"], font=F(8, True), pady=7, padx=12); self.l_amici.pack(side="left")
        piu = tk.Label(c, text="+", bg=P["cap"], fg=P["accento"], font=F(13, True), padx=12, pady=0, cursor="hand2"); piu.pack(side="right")
        piu.bind("<Button-1>", lambda e: self.apri(self.f_add))
        self.testa_amici = c
        self.f_add = f = tk.Frame(self.fr, bg=P["scheda"])
        tk.Label(f, text="NAME", bg=P["scheda"], fg=P["titolo"], font=F(7, True), pady=0, anchor="w").pack(fill="x", padx=12, pady=(8, 0))
        self.e_nome = self.campo(f)
        tk.Label(f, text="UNTAPPED PROFILE LINK", bg=P["scheda"], fg=P["titolo"], font=F(7, True), pady=0, anchor="w").pack(fill="x", padx=12)
        self.e_link = self.campo(f)
        self.e_link.bind("<Return>", lambda e: self.aggiungi())
        self.b_add = pulsante(tk, F, f, "Add friend", False, self.aggiungi, alto=30, bg=P["scheda"]); self.b_add.configure(width=1); self.b_add.pack(fill="x", padx=12, pady=(0, 6))
        self.v_add = tk.StringVar()
        tk.Label(f, textvariable=self.v_add, bg=P["scheda"], fg=P["rosso_t"], font=F(8), anchor="w", pady=0, wraplength=LARGA - 24, justify="left").pack(fill="x", padx=12, pady=(0, 6))
        self.cv = cv = tk.Canvas(self.fr, bg=P["scheda"], highlightthickness=0, height=1, width=1); cv.pack(fill="both", expand=True)
        cv.bind("<Configure>", lambda e: self.disegna())
        cv.bind("<Motion>", self.muovi); cv.bind("<Leave>", lambda e: self.muovi(None)); cv.bind("<Button-1>", self.clic)
        cv.bind_all("<MouseWheel>", self.rotella, add="+")
        self.mostra_profilo()
        self.fr.after(1500, self.giro)

    def campo(self, padre):
        P = self.P
        c = self.tk.Frame(padre, bg=P["cap"], highlightthickness=1, highlightbackground=P["filo"], height=30); c.pack(fill="x", padx=12, pady=(3, 8)); c.pack_propagate(False)
        e = self.tk.Entry(c, bg=P["cap"], fg=P["titolo"], insertbackground=P["titolo"], font=self.F(9), bd=0, highlightthickness=0); e.pack(fill="both", expand=True, padx=8)
        return e

    def apri(self, f):
        """Apre un modulo, o lo chiude se era aperto: stanno sotto il loro titolo."""
        aperto = f.winfo_manager() != ""
        self.f_av.pack_forget(); self.f_add.pack_forget()
        self.v_av.set(""); self.v_add.set("")
        if not aperto:
            f.pack(fill="x", before=self.sotto_profilo if f is self.f_av else self.cv)
            (self.e_carta if f is self.f_av else self.e_nome).focus_set()

    # ------------------------------------------------ il profilo
    def mostra_profilo(self):
        P, v, cv = self.P, self.d.profilo, self.cv_av
        cv.delete("all")
        if os.path.exists(self.d.avatar):
            try:
                self.img = self.tk.PhotoImage(file=self.d.avatar).subsample(2)
                cv.create_image(0, 0, image=self.img, anchor="nw")
            except self.tk.TclError:
                self.img = None
        if self.img is None:
            cv.create_rectangle(0, 0, LATO - 1, LATO - 1, fill=self.tinta(v["nome"]), outline="")
            cv.create_text(LATO / 2, LATO / 2, text=v["nome"][:1].upper(), fill="#ffffff", font=self.F(20, True))
        cv.create_rectangle(0, LATO - 4, LATO, LATO, fill=P["verde"], outline="")
        # niente win rate nella colonna social (Autore, 10 nov 2026: «dalla barra social togli il % win rate»): le partite si'
        self.l_stato.configure(text=f"{v['partite']:,} games" if v.get("partite") else "")
        for k, chiave in (("constructed", "costruito"), ("limited", "limited")):
            r = v.get(chiave)
            lega = r.split()[0] if r else None
            if lega and (k, lega) not in self.leghe:
                f = self.logo(k, lega, 18)
                self.leghe[(k, lega)] = self.tk.PhotoImage(file=f) if f else None
            img = self.leghe.get((k, lega))
            self.ranghi[k].configure(text=(" " if img else "") + (r or "-"), image=img or "")

    def usa_carta(self):
        testo = self.e_carta.get().strip().lower()
        if not testo:
            return
        d = CC.carica()
        nomi = [c["nome"] for c in d["carte"]] if d else []
        trovate = [n for n in nomi if n.lower() == testo] or [n for n in nomi if n.lower().startswith(testo)]
        if not trovate:
            self.v_av.set("No card with that name")
            return
        self.v_av.set("Loading...")
        threading.Thread(target=self.prendi_carta, args=(trovate[0],), daemon=True).start()
        self.ascolta()

    def prendi_carta(self, nome):
        f = CAP.file_immagine(nome, True)
        if not os.path.exists(f):
            CAP.scarica_immagine(nome, True)
        self.pronte.append(("avatar", f))

    def usa_file(self):
        from tkinter import filedialog
        f = filedialog.askopenfilename(parent=self.fr, title="Profile image", filetypes=[("Images", "*.png *.jpg *.jpeg *.webp *.bmp")])
        if f:
            self.pronte.append(("avatar", f))
            self.ascolta()

    def metti_avatar(self, sorgente):
        try:
            fa_avatar(sorgente, self.d.avatar)
        except Exception:
            self.v_av.set("Could not read that image")
            return
        self.img = None
        self.mostra_profilo()
        self.f_av.pack_forget()
        self.v_av.set("")

    # ------------------------------------------------ gli amici
    def aggiungi(self):
        r = self.d.aggiungi(self.e_nome.get(), self.e_link.get())
        if isinstance(r, str):
            self.v_add.set(r)
            return
        self.e_nome.delete(0, "end"); self.e_link.delete(0, "end")
        self.apri(self.f_add)
        self.disegna()
        self.leggi([r])

    def giro(self):
        """Ogni ora guarda chi ha dati vecchi."""
        vecchi = self.d.da_rileggere()
        if vecchi:
            self.leggi(vecchi)
        self.fr.after(3600000, self.giro)

    def leggi(self, voci):
        def lavora():
            for v in voci:
                SO.aggiorna(v)
                self.pronte.append(("dati", v))
            self.pronte.append(("fine", None))
        threading.Thread(target=lavora, daemon=True).start()
        self.ascolta()

    def ascolta(self):
        if not self.lavoro:
            self.lavoro = True
            self.fr.after(200, self.raccogli)

    def raccogli(self):
        ancora = True
        while self.pronte:
            tipo, x = self.pronte.popleft()
            if tipo == "avatar":
                self.metti_avatar(x); ancora = False
            elif tipo == "fine":
                self.d.salva(); ancora = False
            else:
                self.mostra_profilo(); self.disegna()
        if ancora:
            self.fr.after(200, self.raccogli)
        else:
            self.lavoro = False

    def tinta(self, nome):
        return TINTE[zlib.crc32(nome.lower().encode("utf-8")) % len(TINTE)]

    def disegna(self):
        P, F, cv = self.P, self.F, self.cv
        cv.delete("all")
        self.righe, self.sopra = [], None
        w = max(cv.winfo_width(), 2)
        amici = sorted(self.d.amici, key=lambda v: (-(v.get("ultima") or 0), v["nome"].lower()))
        self.l_amici.configure(text=f"FRIENDS · {len(amici)}" if amici else "FRIENDS")
        if not amici:
            cv.create_text(w / 2, 40, text="Press + to add a friend", fill=P["grigio"], font=F(9))
        y = 0
        gruppi = (("RECENT", [v for v in amici if SO.recente(v)]), ("OTHERS", [v for v in amici if not SO.recente(v)]))
        for titolo, voci in gruppi:
            if not voci:
                continue
            cv.create_text(12, y + GRUPPO / 2, text=f"{titolo} · {len(voci)}", anchor="w", fill=P["grigio"], font=F(7, True))
            y += GRUPPO
            for v in voci:
                on = titolo == "RECENT"
                t = f"r{len(self.righe)}"
                cv.create_rectangle(0, y, w, y + RIGA, fill=P["scheda"], outline="", tags=(t, f"{t}f"))
                cv.create_rectangle(0, y + 5, 3, y + RIGA - 5, fill=P["verde"] if on else P["muto"], outline="")
                cv.create_rectangle(10, y + 7, 42, y + 39, fill=self.tinta(v["nome"]) if on else P["filo"], outline="")
                cv.create_text(26, y + 23, text=v["nome"][:1].upper(), fill="#ffffff" if on else P["grigio"], font=F(12, True))
                cv.create_text(52, y + 15, text=v["nome"], anchor="w", fill=P["acciaio"] if on else P["testo"], font=F(10, True))
                cv.create_text(52, y + 32, text=SO.riga_sotto(v), anchor="w", fill=P["grigio"], font=F(8))
                cv.create_text(w - 14, y + 23, text="✕", fill=P["grigio"], font=F(9, True), state="hidden", tags=f"{t}x")
                self.righe.append((y, y + RIGA, v))
                y += RIGA
        cv.configure(scrollregion=(0, 0, 0, y))

    def riga_a(self, e):
        y = self.cv.canvasy(e.y)
        return next((i for i, (a, b, _) in enumerate(self.righe) if a <= y < b), None)

    def muovi(self, e):
        i = self.riga_a(e) if e is not None else None
        if i == self.sopra:
            return
        if self.sopra is not None:
            self.cv.itemconfigure(f"r{self.sopra}f", fill=self.P["scheda"]); self.cv.itemconfigure(f"r{self.sopra}x", state="hidden")
        self.sopra = i
        self.cv.configure(cursor="hand2" if i is not None else "")
        if i is not None:
            self.cv.itemconfigure(f"r{i}f", fill=self.P["cap"]); self.cv.itemconfigure(f"r{i}x", state="normal")

    def clic(self, e):
        i = self.riga_a(e)
        if i is None:
            return
        v = self.righe[i][2]
        if e.x > self.cv.winfo_width() - 28:
            self.d.togli(v)
            self.disegna()
        else:
            webbrowser.open(SO.url_profilo(v))

    def rotella(self, e):
        if e.widget == self.cv and self.righe and self.righe[-1][1] > self.cv.winfo_height():
            self.cv.yview_scroll(-3 if e.delta > 0 else 3, "units")


def prova():
    import tempfile, time, tkinter as tk
    from icone import logo_lega
    from tema import CI
    from widget import pulsante_solido
    from PIL import Image
    amico = "11111111-2222-3333-4444-555555555555"
    with tempfile.TemporaryDirectory() as cart:
        root = tk.Tk(); root.geometry("300x900+7000+0")
        S = ColonnaSocial(tk, root, lambda n, b=False: ("Segoe UI", n, "bold" if b else "normal"), CI, pulsante_solido, logo_lega, cart)
        S.fr.pack(side="right", fill="y")
        root.update()
        casi = [("larghezza fissa", S.fr.winfo_width() == LARGA), ("il nome", S.l_nome.cget("text") == "Player1"), ("elenco vuoto: lo dice", not S.righe),
                ("i moduli partono chiusi", S.f_add.winfo_manager() == "" and S.f_av.winfo_manager() == "")]
        S.apri(S.f_add); root.update()
        casi.append(("il + apre il modulo", S.f_add.winfo_ismapped()))
        S.e_nome.insert(0, "Tizio"); S.e_link.insert(0, "https://altro.it/x"); S.aggiungi(); root.update()
        casi.append(("un link sbagliato si dice e il modulo resta", "link" in S.v_add.get() and S.f_add.winfo_ismapped() and not S.d.amici))
        S.e_link.delete(0, "end"); S.e_link.insert(0, f"mtga.untapped.gg/profile/{amico}/ABCDEFGHIJ"); S.aggiungi(); root.update()
        casi.append(("si aggiunge e il modulo si chiude", len(S.righe) == 1 and not S.f_add.winfo_ismapped()))
        t0 = time.time()
        while time.time() - t0 < 12 and S.lavoro:
            root.update(); time.sleep(0.02)
        root.update()
        casi.append(("il profilo sparito finisce nell'elenco e si dice", S.d.amici[0].get("errore") is True))
        ora = time.time()
        S.d.amici.append(dict(nome="Caio", user=amico, player="BBBBBBBBBB", agg=ora, costruito="Gold 2", wr=54, ultima=ora - 7200))
        S.d.amici.append(dict(nome="Sempronio", user=amico, player="CCCCCCCCCC", agg=ora, limited="Silver 4", wr=48, ultima=ora - 900000))
        S.disegna(); root.update()
        casi.append(("chi ha giocato da poco in cima, gli altri sotto", S.righe[0][2]["nome"] == "Caio" and S.righe[1][2]["nome"] == "Sempronio"))
        testi = [S.cv.itemcget(i, "text") for i in S.cv.find_all() if S.cv.type(i) == "text"]
        casi.append(("i gruppi, senza win rate", "RECENT · 1" in testi and "OTHERS · 2" in testi and "Gold 2 · 2h ago" in testi and not any("54%" in t for t in testi)))
        class Ev:
            def __init__(self, x, y): self.x, self.y = x, y
        y1 = GRUPPO + 10
        S.muovi(Ev(50, y1)); root.update()
        casi.append(("sopra una riga compare la X", S.sopra == 0 and S.cv.itemcget("r0x", "state") == "normal"))
        S.muovi(None); root.update()
        casi.append(("uscendo sparisce", S.sopra is None and S.cv.itemcget("r0x", "state") == "hidden"))
        S.clic(Ev(S.cv.winfo_width() - 10, y1)); root.update()
        casi.append(("la X toglie l'amico giusto", [v["nome"] for v in S.d.amici if v["nome"] == "Caio"] == [] and len(S.righe) == 2))
        f = os.path.join(cart, "prova.png")
        Image.new("RGB", (300, 200), "#884422").save(f)
        S.metti_avatar(f); root.update()
        casi.append(("un'immagine diventa l'avatar", os.path.exists(S.d.avatar) and S.img is not None and Image.open(S.d.avatar).size == (LATO * 2, LATO * 2)))
        S.v_av.set(""); S.metti_avatar(os.path.join(cart, "non_esiste.png")); root.update()
        casi.append(("un file che non si legge si dice", "image" in S.v_av.get() and S.img is not None))
        S.apri(S.f_av); root.update(); S.e_carta.insert(0, "zzzqqq"); S.usa_carta(); root.update()
        casi.append(("una carta che non c'e' si dice", "No card" in S.v_av.get()))
        S.v_av.set(""); S.e_carta.delete(0, "end"); S.e_carta.insert(0, "icy recep"); S.usa_carta()
        t0 = time.time()
        while time.time() - t0 < 10 and S.lavoro:
            root.update(); time.sleep(0.02)
        root.update()
        casi.append(("anche l'arte di una carta", S.v_av.get() == "" and not S.f_av.winfo_ismapped()))
        S.d.profilo.update(costruito="Gold 2", limited="Silver 4", wr=52, partite=434); S.mostra_profilo(); root.update()
        casi.append(("i dati del profilo, senza win rate", "Gold 2" in S.ranghi["constructed"].cget("text") and "%" not in S.l_stato.cget("text")
                     and "434 games" in S.l_stato.cget("text") and S.ranghi["limited"].cget("image") != ""))
        root.destroy()
    for nome, ok in casi:
        print(("  ok    " if ok else "  ROSSO ") + nome)
    n = sum(1 for _, ok in casi if ok)
    print(f"{n}/{len(casi)}")
    return 0 if n == len(casi) else 1


if __name__ == "__main__":
    sys.exit(prova() if "--prova" in sys.argv else 0)
