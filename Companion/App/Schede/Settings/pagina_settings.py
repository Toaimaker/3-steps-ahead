"""La scheda Settings (13 nov 2026, Autore: «Facciamo che si apre come si apre steam, al primo avvio una finestra di caricamento, poi parte l'app e una
finestra chiede il turn on dell'upload dati log e il link alla collezione di untapped gg / queste funzioni le sposti dall'help in una nuova scheda settings»).

Due blocchi, gli stessi della finestra di benvenuto (benvenuto.py), che li costruisce con le stesse funzioni:
- DATA SHARING: l'interruttore on/off (condividi.consenso, imposta_consenso), quante partite aspettano, il codice pseudonimo per i diritti;
- YOUR COLLECTION: il link del profilo pubblico di Untapped (account.collega_untapped), poi lo scarico della collezione (collezione_viva.aggiorna_scarico).
Fino a quel giorno stavano in Help (pagina_help.riquadro_condivisione e riquadro_untapped). La finestra di benvenuto si apre una volta per account:
benvenuto_fatto / segna_benvenuto, nel file degli account (utente.json, campo «benvenuto»).
"""
import os, sys
_casa = os.path.dirname(os.path.abspath(__file__))
while not os.path.isfile(os.path.join(_casa, "percorsi.py")):
    _casa = os.path.dirname(_casa)
if _casa not in sys.path:
    sys.path.insert(0, _casa)
import percorsi  # noqa: E402,F401
import threading  # noqa: E402
import webbrowser  # noqa: E402

import disegni as DG  # noqa: E402
from tema import CI as C  # noqa: E402
from widget import pulsante_solido  # noqa: E402


def privacy_url():
    """L'informativa: canale.json dell'app pubblica («privacy»), nell'app di Autore Distribuzione/config.json; "" se non c'e'."""
    import json
    for f, k in ((os.path.join(percorsi.ROOT, "canale.json"), "privacy"), (os.path.join(percorsi.ROOT, "Distribuzione", "config.json"), "url_privacy")):
        try:
            u = (json.load(open(f, encoding="utf-8")) or {}).get(k) or ""
            if u.startswith(("https://", "http://")):
                return u
        except (OSError, ValueError):
            pass
    return ""


# ------------------------------------------------ Arena: Detailed Logs
def log_dettagliato(f=None):
    """Arena scrive all'avvio, nel Player.log, «DETAILED LOGS: ENABLED» o «DISABLED» (Options › Account › Detailed Logs (Plugin Support)): senza, il log non ha
    partite, mazzi e mani e l'app vede quasi niente. -> "on", "off", "nessun_log" (Arena mai aperta su questo PC) o "sconosciuto" (la riga non c'e')."""
    import re
    try:
        if f is None:
            import piattaforma
            f = piattaforma.player_log()
        with open(f, "rb") as g:
            testa = g.read(8 * 1024 * 1024)
    except (OSError, TypeError):
        return "nessun_log"
    tutte = re.findall(rb"DETAILED LOGS: (ENABLED|DISABLED)", testa)
    if not tutte:
        return "sconosciuto"
    return "on" if tutte[-1] == b"ENABLED" else "off"


# ------------------------------------------------ la finestra di benvenuto: una volta per account
def benvenuto_fatto(conto=None):
    """Il benvenuto si fa una volta per questo PC (13 nov 2026, Autore: «al secondo avvio siamo sicuri che questi messaggi non riappaiono vero?»): il segno
    sta in cima al file degli account («benvenuto») e, per i file di prima, anche sull'account. Fino a quel giorno era solo sull'account, scritto sotto
    «?» e letto sotto None quando l'account di Arena non si sapeva ancora (Arena mai aperta dopo l'installazione): il benvenuto tornava a ogni avvio."""
    import account
    import condividi
    d = account.leggi()
    if d.get("benvenuto"):
        return True
    return bool((d["conti"].get(condividi._chi(conto) or "?") or {}).get("benvenuto"))


def segna_benvenuto(conto=None):
    import account
    import condividi
    d = account.leggi()
    d["benvenuto"] = True
    d["conti"].setdefault(condividi._chi(conto) or "?", {})["benvenuto"] = True
    account.salva(d)


# ------------------------------------------------ i due blocchi
class Condivisione:
    """DATA SHARING: il titolo, l'interruttore on/off, lo stato, la riga sotto. b.aggiorna() lo rilegge."""

    def __init__(self, tk, F, padre, bg=None, larga=900, codice=True):
        import account
        import condividi
        self.tk, self.F = tk, F
        self.bg = bg or C["scheda"]
        self.fr = tk.Frame(padre, bg=self.bg)
        tk.Label(self.fr, text="Data sharing", bg=self.bg, fg=C["titolo"], font=F(16, True)).pack(anchor="w", pady=(0, 6))      # titoli grandi (13 nov 2026)
        riga = tk.Frame(self.fr, bg=self.bg); riga.pack(fill="x", pady=(0, 6))
        self.l_stato = tk.Label(riga, text="", bg=self.bg, fg=C["testo"], font=F(10, True), anchor="w", justify="left"); self.l_stato.pack(side="left")
        # un interruttore on/off, non un pulsante (13 nov 2026, Autore: «fai in modo che il pulsante di datasharing sia uno switcher on off»)
        self.leva = tk.Canvas(riga, width=118, height=30, bg=self.bg, highlightthickness=0, bd=0, cursor="hand2"); self.leva.pack(side="right")
        self.leva.bind("<Button-1>", lambda e: self.cambia())
        testo = "Your finished games go to our server to build shared stats: only cards, results, mulligans and turns. Never your name, your account or " \
                "your opponents' names. Recommended: it gives you the best, most complete experience. Off unless you turn it on."
        if codice:
            testo += f" Your code for any privacy request: {condividi.codice(account.account().get('id') or '?')}"
        tk.Label(self.fr, text=testo, bg=self.bg, fg=C["grigio"], font=F(8), anchor="w", justify="left", wraplength=larga).pack(fill="x")
        url = privacy_url()
        if url:
            l_ = tk.Label(self.fr, text="Privacy notice ↗", bg=self.bg, fg=C["accento"], font=F(8), cursor="hand2"); l_.pack(anchor="w", pady=(4, 0))
            l_.bind("<Button-1>", lambda e: webbrowser.open(url))
        self.aggiorna()

    def aggiorna(self):
        import condividi
        si = condividi.consenso() is True
        coda = os.path.join(condividi.CARTELLA[0], "coda.jsonl")
        try:
            n = sum(1 for r in open(coda, encoding="utf-8") if r.strip()) if os.path.exists(coda) else 0
        except OSError:
            n = 0
        self.l_stato.configure(text=("Sharing your games" if si else "Not sharing · recommended: turn it on for the full experience") + (f" · {n} game{'s' if n != 1 else ''} waiting to be sent" if si and n else ""),
                               fg=C["verde_t"] if si else C["testo"])
        c = self.leva
        c.delete("all")
        c.create_text(0, 15, text="ON" if si else "OFF", anchor="w", fill=C["verde_t"] if si else C["muto"], font=self.F(9, True), tags="testo")
        c.create_image(118, 15, anchor="e", tags="leva", image=DG.interruttore(52, 26, si, C["verde"], C["fondo"], C["filo"], "#ffffff", C["grigio"]))
        c.stato = si

    def cambia(self):
        import condividi
        condividi.imposta_consenso(condividi.consenso() is not True)
        self.aggiorna()
        for f in list(ALTRI):       # la scheda Settings e la finestra di benvenuto dicono la stessa cosa
            if f is not self:
                try:
                    f.aggiorna()
                except Exception:       # noqa: BLE001 - un blocco gia' chiuso
                    ALTRI.discard(f)


ALTRI = set()


class Collezione:
    """YOUR COLLECTION: il link del profilo pubblico di Untapped, Link, lo stato."""

    def __init__(self, tk, F, padre, bg=None, larga=900):
        import account
        self.tk, self.F = tk, F
        self.bg = bg or C["scheda"]
        self.fr = tk.Frame(padre, bg=self.bg)
        tk.Label(self.fr, text="Your collection", bg=self.bg, fg=C["titolo"], font=F(16, True)).pack(anchor="w", pady=(0, 2))
        tk.Label(self.fr, text="from your public Untapped.gg profile", bg=self.bg, fg=C["grigio"], font=F(9)).pack(anchor="w", pady=(0, 8))
        riga = tk.Frame(self.fr, bg=self.bg); riga.pack(fill="x", pady=(0, 4))
        self.v_link = tk.StringVar()
        self.e = tk.Entry(riga, textvariable=self.v_link, bg=C["fondo"], fg=C["titolo"], insertbackground=C["titolo"], relief="flat", font=F(9))
        self.e.pack(side="left", fill="x", expand=True, ipady=5, padx=(0, 8))
        self.e.bind("<Return>", lambda e: self.collega())
        b = pulsante_solido(tk, F, riga, "Link", False, self.collega, alto=30, bg=self.bg); b.configure(width=110); b.pack(side="right")
        self.l_link = tk.Label(self.fr, text="", bg=self.bg, fg=C["grigio"], font=F(8), anchor="w", justify="left", wraplength=larga)
        self.l_link.pack(fill="x")
        a = account.account()
        self.collegato = bool(a.get("untapped_player"))
        self.l_link.configure(text=("Linked to your Untapped profile. " if self.collegato else "Not linked. ")
                              + "Arena's log does not list your whole collection: paste the link of your public Untapped.gg profile "
                              "(mtga.untapped.gg/profile/...) to see the cards you own and the wildcards your decks need.",
                              fg=C["verde_t"] if self.collegato else C["grigio"])

    def collega(self):
        import account
        if not account.collega_untapped(self.v_link.get()):
            self.l_link.configure(text="That is not an Untapped profile link. It looks like https://mtga.untapped.gg/profile/<id>/<id>", fg=C["rosso_t"])
            return False
        self.collegato = True
        self.l_link.configure(text="Linked. Downloading your collection…", fg=C["testo"])

        def lavoro():
            try:
                import collezione_viva as CV
                esito = CV.aggiorna_scarico()
            except Exception:       # noqa: BLE001
                esito = None
            msg = {True: "Collection downloaded. Restart the app to see limited games and your profile.", False: "Linked; the collection did not change.",
                   None: "Linked, but Untapped did not answer. The app tries again in a few minutes."}[esito]
            try:
                self.fr.after(0, lambda: self.l_link.configure(text=msg, fg=C["verde_t"] if esito else C["testo"]))
            except Exception:       # noqa: BLE001 - la finestra chiusa nel frattempo
                pass
        threading.Thread(target=lavoro, daemon=True).start()
        return True


class Arena:
    """ARENA · DETAILED LOGS: se Arena scrive il log dettagliato (log_dettagliato), con i passi per accenderlo e Check again."""
    TESTI = {"on": ("✓  Detailed Logs is ON in your Arena log.", "verde_t"),
             "off": ("✗  Detailed Logs is OFF: in Arena, Options › Account › tick Detailed Logs (Plugin Support), then restart Arena.", "arancio"),
             "nessun_log": ("No Arena log on this PC yet: start Arena once.", "grigio"),
             "sconosciuto": ("Arena's log does not say yet: start Arena (or restart it).", "grigio")}

    def __init__(self, tk, F, padre, bg=None, larga=900):
        self.tk, self.F = tk, F
        self.bg = bg or C["scheda"]
        self.fr = tk.Frame(padre, bg=self.bg)
        tk.Label(self.fr, text="Arena", bg=self.bg, fg=C["titolo"], font=F(16, True)).pack(anchor="w", pady=(0, 2))
        tk.Label(self.fr, text="the app reads the log Arena writes for trackers: it needs Detailed Logs (Plugin Support) on", bg=self.bg, fg=C["grigio"],
                 font=F(9)).pack(anchor="w", pady=(0, 8))
        riga = tk.Frame(self.fr, bg=self.bg); riga.pack(fill="x")
        self.l_stato = tk.Label(riga, text="", bg=self.bg, fg=C["testo"], font=F(10, True), anchor="w", justify="left", wraplength=larga - 160)
        self.l_stato.pack(side="left")
        b = pulsante_solido(tk, F, riga, "Check again", False, self.aggiorna, alto=30, bg=self.bg); b.configure(width=130); b.pack(side="right")
        self.aggiorna()

    def aggiorna(self):
        self.stato = log_dettagliato()
        t, col = self.TESTI[self.stato]
        self.l_stato.configure(text=t, fg=C[col])
        return self.stato


def riquadro(tk, padre, F):
    """Un riquadro col filo, come in Help: -> il Frame dentro."""
    box = tk.Frame(padre, bg=C["filo"], padx=1, pady=1); box.pack(fill="x", padx=16, pady=(0, 12))
    d = tk.Frame(box, bg=C["scheda"]); d.pack(fill="x")
    return d


class PaginaSettings:
    def __init__(self, tk, padre, F, mana=None):
        self.tk, self.F = tk, F
        self.fr = tk.Frame(padre, bg=C["fondo"])
        testa = tk.Frame(self.fr, bg=C["fondo"]); testa.pack(fill="x", padx=16, pady=(14, 10))
        tk.Label(testa, text="SETTINGS", bg=C["fondo"], fg=C["titolo"], font=F(13, True)).pack(side="left")
        tk.Label(testa, text="what Arena must do, what the app shares, where it reads your collection", bg=C["fondo"], fg=C["grigio"], font=F(9)).pack(side="left", padx=12, pady=(4, 0))
        self.arena = Arena(tk, F, riquadro(tk, self.fr, F)); self.arena.fr.pack(fill="x", padx=12, pady=10)
        self.cond = Condivisione(tk, F, riquadro(tk, self.fr, F)); self.cond.fr.pack(fill="x", padx=12, pady=10)
        ALTRI.add(self.cond)
        self.coll = Collezione(tk, F, riquadro(tk, self.fr, F)); self.coll.fr.pack(fill="x", padx=12, pady=10)

    def se_sporca(self):
        try:
            self.cond.aggiorna()
            self.arena.aggiorna()
        except Exception:       # noqa: BLE001
            pass


def prova():
    """Fuori schermo, col consenso e gli account in memoria: l'interruttore, il link sbagliato e quello giusto, il benvenuto una volta."""
    import tkinter as tk
    import account
    import condividi
    casi = []
    root = tk.Tk(); root.geometry("1100x700+7000+0")
    F = lambda n, g=False: ("Segoe UI", n, "bold" if g else "normal")
    vero = (condividi.consenso, condividi.imposta_consenso, account.leggi, account.salva, account.collega_untapped)
    mem = {"si": None, "d": {"conti": {}}, "link": []}
    try:
        condividi.consenso = lambda conto=None: mem["si"]
        condividi.imposta_consenso = lambda si, conto=None: mem.update(si=bool(si))
        account.leggi = lambda: __import__("json").loads(__import__("json").dumps(mem["d"]))
        account.salva = lambda d: mem.update(d=d)
        account.collega_untapped = lambda l: ("mtga.untapped.gg/profile/" in (l or "")) and (mem["link"].append(l) or True)
        vero_log = globals()["log_dettagliato"]
        globals()["log_dettagliato"] = lambda f=None: mem.get("log", "off")
        p = PaginaSettings(tk, root, F); p.fr.pack(fill="both", expand=True); root.update()
        casi.append(("Arena: Detailed Logs spento lo dice coi passi, in arancio", "is OFF" in p.arena.l_stato.cget("text") and "Plugin Support" in p.arena.l_stato.cget("text")))
        mem["log"] = "on"
        casi.append(("Check again: acceso, in verde; negativa: senza log di Arena non dice ON", p.arena.aggiorna() == "on" and "is ON" in p.arena.l_stato.cget("text")
                     and (mem.update(log="nessun_log") or p.arena.aggiorna() == "nessun_log") and "ON" not in p.arena.l_stato.cget("text")))
        globals()["log_dettagliato"] = vero_log
        lv = p.cond.leva
        testo = lambda: lv.itemcget(lv.find_withtag("testo")[0], "text")
        casi.append(("mai scelto: OFF, «Not sharing»", testo() == "OFF" and p.cond.l_stato.cget("text").startswith("Not sharing · recommended") and lv.stato is False))
        lv.event_generate("<Button-1>", x=100, y=15); root.update()
        casi.append(("il clic sull'interruttore lo accende: ON, consenso si'", testo() == "ON" and mem["si"] is True
                     and p.cond.l_stato.cget("text").startswith("Sharing")))
        b2 = Condivisione(tk, F, root); ALTRI.add(b2)
        lv.event_generate("<Button-1>", x=100, y=15); root.update()
        casi.append(("un altro clic lo spegne, e l'altro blocco (la finestra di benvenuto) lo segue", mem["si"] is False and b2.leva.stato is False))
        p.coll.v_link.set("https://example.org/nope")
        casi.append(("negativa: un link che non e' di Untapped non si collega e lo dice", p.coll.collega() is False and "not an Untapped" in p.coll.l_link.cget("text")))
        import tempfile
        d_ = tempfile.mkdtemp()
        for nome, testo in (("a.log", "x\nDETAILED LOGS: ENABLED\ny"), ("b.log", "DETAILED LOGS: DISABLED\n"), ("c.log", "niente\n")):
            open(os.path.join(d_, nome), "w").write(testo)
        casi.append(("il lettore del log: ENABLED on, DISABLED off, niente sconosciuto, file assente nessun_log",
                     [log_dettagliato(os.path.join(d_, n)) for n in ("a.log", "b.log", "c.log", "manca.log")] == ["on", "off", "sconosciuto", "nessun_log"]))
        vero_leggi, vero_salva, vero_file, vero_chi = account.leggi, account.salva, list(account.FILE), condividi._chi
        try:
            account.leggi, account.salva = vero[2], vero[3]
            account.FILE[0] = os.path.join(d_, "utente.json")
            account._C.clear()
            condividi._chi = lambda conto=None: conto        # l'account di Arena non si sa ancora: None
            primo = benvenuto_fatto()
            segna_benvenuto()
            account._C.clear()                                # il secondo avvio: il file si rilegge da capo
            secondo = benvenuto_fatto()
            condividi._chi = lambda conto=None: conto or "acc-123"     # poi Arena dice l'account
            terzo = benvenuto_fatto()
            os.remove(account.FILE[0]); account._C.clear()
            casi.append(("il file vero: al primo avvio no, fatto il benvenuto al secondo avvio non riappare, nemmeno quando poi l'account di Arena si sa",
                         primo is False and secondo is True and terzo is True))
            casi.append(("negativa: un PC senza il file degli account il benvenuto lo mostra", benvenuto_fatto() is False))
        finally:
            account.leggi, account.salva, condividi._chi = vero_leggi, vero_salva, vero_chi
            account.FILE[0] = vero_file[0]
            account._C.clear()
        casi.append(("benvenuto: non fatto, poi fatto, e vale per tutto il PC (anche un altro account di Arena non lo rivede)", not benvenuto_fatto("x1")
                     and (segna_benvenuto("x1") or True) and benvenuto_fatto("x1") and benvenuto_fatto("x2")))
    finally:
        condividi.consenso, condividi.imposta_consenso, account.leggi, account.salva, account.collega_untapped = vero
        root.destroy()
    for n, ok in casi:
        print(("ok    " if ok else "ROSSO ") + n)
    print(f"{sum(1 for _n, ok in casi if ok)}/{len(casi)}")
    return all(ok for _n, ok in casi)


if __name__ == "__main__":
    sys.exit(0 if prova() else 1)
