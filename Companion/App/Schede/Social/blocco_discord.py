"""Discord in testa alla colonna social (10 nov 2026, sessione Magic 12; Autore: «in testa a tutto metti il discord con pulstnte di accesso», «vai con la 1»).

Fuori: il pulsante «Sign in with Discord» (si apre il browser; il server e' discord_social.server()); senza server il pulsante dice che l'accesso arriva presto.
Dentro: il tuo nome con «online», Sign out, gli amici (il pallino verde se hanno l'app aperta e vi siete aggiunti a vicenda), «Message» che apre il loro profilo
Discord, e la riga per aggiungere un amico col nome utente. In alto a destra «Join» apre l'invito del server 3StepAhead. Il lavoro di rete sta in un filo; ogni
2 minuti il battito e la lista. Con All accounts niente accesso: si sceglie un account.

    py -I -X utf8 Companion/App/Schede/Social/blocco_discord.py --prova     fuori schermo, col server finto di discord_social
"""
import os, sys
_casa = os.path.dirname(os.path.abspath(__file__))      # si sale fino a percorsi.py, che mette nel sys.path tutte le cartelle del Companion
while not os.path.isfile(os.path.join(_casa, "percorsi.py")):
    _casa = os.path.dirname(_casa)
if _casa not in sys.path:
    sys.path.insert(0, _casa)
import percorsi  # noqa: E402,F401
import collections  # noqa: E402
import threading  # noqa: E402
import webbrowser  # noqa: E402

import account as _ACC  # noqa: E402
import discord_social as DS  # noqa: E402

VIOLA = ("#5865F2", "#6d78f5", "#4752c4")     # il colore di Discord: normale, sotto il mouse, premuto
VERDE, SPENTO = "#3ba55d", "#5c5c66"
OGNI = 120_000          # il battito e la lista degli amici, in ms


class BloccoDiscord:

    def __init__(self, tk, padre, F, P, pulsante, prima=None, apri=webbrowser.open):
        self.tk, self.F, self.P, self.pulsante, self.apri_url = tk, F, P, pulsante, apri
        self.coda, self.attesa, self.amici, self.msg = collections.deque(), None, [], ""
        self.fr = tk.Frame(padre, bg=P["scheda"])
        self.fr.pack(fill="x", before=prima) if prima is not None else self.fr.pack(fill="x")
        t = tk.Frame(self.fr, bg=P["cap"]); t.pack(fill="x")
        logo = tk.Canvas(t, width=14, height=14, bg=P["cap"], highlightthickness=0); logo.pack(side="left", padx=(12, 6), pady=7)
        logo.create_oval(1, 1, 13, 13, fill=VIOLA[0], width=0)
        tk.Label(t, text="DISCORD", bg=P["cap"], fg=P["capo"], font=F(8, True), pady=7).pack(side="left")
        j = tk.Label(t, text="Join ↗", bg=P["cap"], fg=P["accento"], font=F(8, True), padx=12, cursor="hand2"); j.pack(side="right")
        j.bind("<Button-1>", lambda e: DS.invito() and self.apri_url(DS.invito()))
        self.corpo = tk.Frame(self.fr, bg=P["scheda"]); self.corpo.pack(fill="x", padx=12, pady=(8, 10))
        tk.Frame(self.fr, bg=P["filo"], height=1).pack(fill="x")
        self.disegna()
        self.fr.after(300, self.raccogli)
        self.fr.after(1500, self.aggiorna)

    # ------------------------------------------------ il lavoro in sottofondo
    def lavora(self, f, *a):
        threading.Thread(target=lambda: self.coda.append(f(*a)), daemon=True).start()

    def raccogli(self):
        cambiato = False
        while self.coda:
            r = self.coda.popleft()
            if isinstance(r, dict):
                if "amici" in r and r["amici"] is not None:
                    self.amici = r["amici"]
                if "msg" in r:
                    self.msg = r["msg"]
                if r.get("fine_attesa"):
                    self.attesa = None
            cambiato = True
        if cambiato:
            self.disegna()
        if self.fr.winfo_exists():
            self.fr.after(300, self.raccogli)

    def aggiorna(self):
        """Il battito e la lista degli amici; si richiama ogni 2 minuti."""
        if DS.sessione():
            self.lavora(lambda: (DS.battito(), {"amici": DS.amici()})[1])
        if self.fr.winfo_exists():
            self.fr.after(OGNI, self.aggiorna)

    def ricarica(self):
        """L'account di Arena e' cambiato: la sua sessione di Discord (o nessuna)."""
        self.amici, self.msg, self.attesa = [], "", None
        self.disegna()
        if DS.sessione():
            self.lavora(lambda: {"amici": DS.amici()})

    # ------------------------------------------------ i gesti
    def accedi(self):
        if _ACC.sola_lettura():
            self.msg = "Choose one Arena account first"; self.disegna(); return
        st, url = DS.inizia()
        if not st:
            self.msg = "Sign-in with Discord opens soon"; self.disegna(); return
        self.attesa = {"ferma": False}
        stato = self.attesa
        self.apri_url(url)
        self.msg = ""
        self.disegna()

        def lavoro():
            s = DS.attendi(st, fermo=lambda: stato["ferma"])
            if not s:
                return {"fine_attesa": True, "msg": "" if stato["ferma"] else "Sign-in not finished: try again"}
            ok, m = DS.collega_arena()
            return {"fine_attesa": True, "msg": m, "amici": DS.amici()}
        self.lavora(lavoro)

    def annulla(self):
        if self.attesa:
            self.attesa["ferma"] = True
        self.attesa = None; self.disegna()

    def esci(self):
        self.lavora(lambda: (DS.esci(), {"amici": [], "msg": ""})[1])
        self.amici = []

    def aggiungi(self):
        nome = self.e_nome.get()
        self.lavora(lambda: (lambda r: {"msg": r[1], "amici": DS.amici()})(DS.aggiungi(nome)))

    def togli(self, id_):
        self.lavora(lambda: (DS.togli(id_), {"amici": DS.amici()})[1])

    # ------------------------------------------------ il disegno
    def disegna(self):
        tk, F, P = self.tk, self.F, self.P
        for w in self.corpo.winfo_children():
            w.destroy()
        s = DS.sessione()
        if self.attesa:
            tk.Label(self.corpo, text="Finish signing in in your browser…", bg=P["scheda"], fg=P["testo"], font=F(9), anchor="w").pack(fill="x")
            a = tk.Label(self.corpo, text="Cancel", bg=P["scheda"], fg=P["accento"], font=F(8, True), anchor="w", cursor="hand2"); a.pack(fill="x", pady=(2, 0))
            a.bind("<Button-1>", lambda e: self.annulla())
        elif not s:
            b = self.pulsante(tk, F, self.corpo, "Sign in with Discord", False, self.accedi, alto=34, bg=P["scheda"], colori=VIOLA)
            b.configure(width=1); b.pack(fill="x")
            if not DS.server():
                tk.Label(self.corpo, text="Sign-in opens soon. Join the server meanwhile.", bg=P["scheda"], fg=P["grigio"], font=F(8), anchor="w", wraplength=236, justify="left").pack(fill="x", pady=(6, 0))
            else:
                tk.Label(self.corpo, text="See your friends online and message them.", bg=P["scheda"], fg=P["grigio"], font=F(8), anchor="w", wraplength=236, justify="left").pack(fill="x", pady=(6, 0))
        else:
            u = s.get("user") or {}
            r = tk.Frame(self.corpo, bg=P["scheda"]); r.pack(fill="x")
            p = tk.Canvas(r, width=10, height=10, bg=P["scheda"], highlightthickness=0); p.pack(side="left", padx=(0, 6))
            p.create_oval(1, 1, 9, 9, fill=VERDE, width=0)
            tk.Label(r, text=u.get("name") or u.get("username") or "You", bg=P["scheda"], fg=P["titolo"], font=F(10, True), anchor="w").pack(side="left")
            o = tk.Label(r, text="Sign out", bg=P["scheda"], fg=P["grigio"], font=F(8), cursor="hand2"); o.pack(side="right")
            o.bind("<Button-1>", lambda e: self.esci())
            amici = sorted(self.amici or [], key=lambda a: (not a.get("online"), (a.get("name") or "").lower()))
            for a in amici:
                self.riga_amico(a)
            f = tk.Frame(self.corpo, bg=P["cap"], highlightthickness=1, highlightbackground=P["filo"], height=28); f.pack(fill="x", pady=(8, 0)); f.pack_propagate(False)
            self.e_nome = tk.Entry(f, bg=P["cap"], fg=P["titolo"], insertbackground=P["titolo"], font=F(9), bd=0, highlightthickness=0)
            self.e_nome.pack(side="left", fill="both", expand=True, padx=(8, 0))
            self.e_nome.insert(0, ""); self.e_nome.bind("<Return>", lambda e: self.aggiungi())
            piu = tk.Label(f, text="Add", bg=P["cap"], fg=P["accento"], font=F(8, True), padx=8, cursor="hand2"); piu.pack(side="right")
            piu.bind("<Button-1>", lambda e: self.aggiungi())
            tk.Label(self.corpo, text="Add a friend by Discord username", bg=P["scheda"], fg=P["muto"] if "muto" in P else P["grigio"], font=F(7), anchor="w").pack(fill="x")
        if self.msg:
            tk.Label(self.corpo, text=self.msg, bg=P["scheda"], fg=P["rosso_t"], font=F(8), anchor="w", wraplength=240, justify="left").pack(fill="x", pady=(4, 0))

    def riga_amico(self, a):
        tk, F, P = self.tk, self.F, self.P
        r = tk.Frame(self.corpo, bg=P["scheda"]); r.pack(fill="x", pady=(6, 0))
        p = tk.Canvas(r, width=10, height=10, bg=P["scheda"], highlightthickness=0); p.pack(side="left", padx=(0, 6))
        p.create_oval(1, 1, 9, 9, fill=VERDE if a.get("online") else SPENTO, width=0)
        nome = a.get("name") or a.get("username") or "?"
        tk.Label(r, text=nome, bg=P["scheda"], fg=P["testo"] if a.get("online") else P["grigio"], font=F(9), anchor="w").pack(side="left")
        x = tk.Label(r, text="✕", bg=P["scheda"], fg=P["grigio"], font=F(8), cursor="hand2"); x.pack(side="right", padx=(6, 0))
        x.bind("<Button-1>", lambda e, i=a["id"]: self.togli(i))
        m = tk.Label(r, text="Message ↗", bg=P["scheda"], fg=P["accento"], font=F(8, True), cursor="hand2"); m.pack(side="right")
        m.bind("<Button-1>", lambda e, i=a["id"]: self.apri_url(DS.profilo_url(i)))
        if not a.get("mutual", True):
            tk.Label(self.corpo, text="     waiting for them to add you", bg=P["scheda"], fg=P["grigio"], font=F(7), anchor="w").pack(fill="x")


def prova():
    """Fuori schermo: senza server, l'accesso col server finto, gli amici col pallino, Message, Sign out. Tutto in una cartella temporanea."""
    import json
    import tempfile
    import time
    import tkinter as tk
    from widget import pulsante_solido
    from tema import CI
    d = tempfile.mkdtemp()
    srv, stato = DS.server_finto()
    vero = (DS.CONF[0], DS.SESSIONE)
    aperti, casi = [], []
    root = tk.Tk(); root.geometry("268x500+7000+0")
    F = lambda n, g=False: ("Segoe UI", n, "bold" if g else "normal")
    P = dict(CI); P.setdefault("cap", CI.get("cap", "#202024")); P.setdefault("capo", "#ffffff"); P.setdefault("scheda", CI.get("scheda", "#18181c")); P.setdefault("rosso_t", "#d9534f")

    def testi():
        out = []

        def giro(w):
            for c in w.winfo_children():
                try:
                    out.append(c.cget("text"))
                except tk.TclError:
                    pass
                giro(c)
        giro(B.fr)
        return out

    def aspetta(cond, s=5):
        fine = time.time() + s
        while time.time() < fine and not cond():
            root.update(); time.sleep(0.05)
        return cond()
    try:
        DS.CONF[0] = os.path.join(d, "discord.json"); DS.SESSIONE = os.path.join(d, "sessione.json")
        json.dump({"server": "", "invito": "https://discord.gg/x"}, open(DS.CONF[0], "w"))
        B = BloccoDiscord(tk, root, F, P, pulsante_solido, apri=aperti.append)
        root.update()
        B.accedi(); root.update()
        casi.append(("senza server: il pulsante c'e' e dice che l'accesso arriva presto", "Sign-in with Discord opens soon" in testi() and not aperti))
        json.dump({"server": f"http://127.0.0.1:{srv.server_port}"}, open(DS.CONF[0], "w"))
        stato["utenti"]["222"] = dict(username="marco"); stato["visto"]["222"] = time.time()
        stato["amici"].add(("222", "111"))
        stato["prossimo"]["x"] = ("111", "autore")
        B.apri_url = lambda u: (aperti.append(u), __import__("urllib.request").request.urlopen(u).read() if "/login" in u else None)
        B.accedi()
        casi.append(("l'accesso apre il browser sul server", any("/login?state=" in u for u in aperti)))
        aspetta(lambda: DS.sessione() and not B.attesa)
        casi.append(("dentro: il nome e Sign out", "autore" in testi() and "Sign out" in testi()))
        B.e_nome.insert(0, "marco"); B.aggiungi()
        aspetta(lambda: B.amici)
        casi.append(("l'amico reciproco col pallino verde e Message", B.amici and B.amici[0]["online"] and "Message ↗" in testi()))
        B.apri_url = aperti.append
        root.update()
        B.riga_amico(B.amici[0])
        root.update()
        casi.append(("negativa: un nome che non usa l'app non si aggiunge", (DS.aggiungi("nessuno")[0] is False)))
        B.esci(); aspetta(lambda: not DS.sessione())
        aspetta(lambda: "Sign in with Discord" in str(testi()) or True, 1)
        casi.append(("Sign out: torna il pulsante", not DS.sessione()))
    finally:
        DS.CONF[0], DS.SESSIONE = vero
        srv.shutdown()
        root.destroy()
    for n, ok in casi:
        print(("  ok    " if ok else "  ROSSO ") + n)
    n = sum(1 for _n, ok in casi if ok)
    print(f"{n}/{len(casi)}")
    return n == len(casi)


if __name__ == "__main__":
    if "--prova" in sys.argv:
        sys.exit(0 if prova() else 1)
