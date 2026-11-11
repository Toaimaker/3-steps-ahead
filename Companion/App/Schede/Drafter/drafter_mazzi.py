"""La scheda Drafter coi mazzi: le tre fasi (pick, costruzione, partita), i mazzi possibili nei pick, i tre proposti con Select deck, il mazzo inviato col cancello e il Fix, l'overlay. Mixin di Finestra (App/finestra.py)."""
import json
import os
import subprocess

import piattaforma  # (Windows e Mac: flag dei processi, Python)
import sys
import threading
import time
import tkinter as tk

import capsule as CAP
import percorsi

from ambiente import FIX_JSON, INVIATO_JSON, LOGDIR, MAZZI_JSON, PICK_JSON, PY_MUTO, ROOT
from chat_testi import en
from tema import CI, COL_TIER
from widget import pulsante_solido


class DrafterMazzi:
    """La scheda Drafter coi mazzi: le tre fasi (pick, costruzione, partita), i mazzi possibili nei pick, i tre proposti con Select deck, il mazzo inviato col cancello e il Fix, l'overlay."""

    def avviso_mazzi(self, testo):
        tk.Label(self.b6, text=testo, bg=CI["scheda"], fg=CI["grigio"], font=self.F(9), anchor="w", justify="left",
                 wraplength=380).pack(fill="x")


    def cambia_fase(self, v):
        if self.fase["v"] != v:
            self.fase["v"] = v
            self.assetto(); self.disegna_mazzi()


    def calcola_pick(self):
        """I tre mazzi del pool: un processo a parte a priorita' bassa, acceso al primo pick, che riceve una riga per pick e si chiude con la finestra (o con un draft d'altro set)."""
        if not self.fase["pick"] or self.fase["pick"] == self.fase["lanciato"]:       # lo stesso pick con le coppie nuove si rifa' (la rara obbligata esce prima delle coppie)
            return
        p = self.calcolo["p"]
        if p is None or p.poll() is not None or self.calcolo.get("evento") != self.fase["evento"]:
            if p is not None and p.poll() is None:
                p.stdin.close()
            pz = self.fase["evento"].split("_")
            env = dict(os.environ, **({"MAGIC_SET": pz[1], "MAGIC_FORMATO": "quick" if pz[0].startswith("Quick") else "premier"} if len(pz) > 1 else {}))
            extra = ["--log", sys.argv[sys.argv.index("--draft-log") + 1]] if "--draft-log" in sys.argv else []
            try:
                p = self.calcolo["p"] = subprocess.Popen([PY_MUTO, "-I", "-X", "utf8", percorsi.programma("mazzi_in_corsa.py"), "--servo", "--file", PICK_JSON] + extra,
                                                    cwd=ROOT, env=env, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, text=True, encoding="utf-8", **piattaforma.flag("sotto"),
                                                    stderr=open(os.path.join(LOGDIR, "mazzi_pick_errori.txt"), "a", encoding="utf-8"))
            except OSError as e:
                print("mazzi del pick:", e); return
            self.calcolo["evento"] = self.fase["evento"]
        self.fase["lanciato"] = self.fase["pick"]
        n_pick, coppie = self.fase["pick"]
        try:
            p.stdin.write(f"{n_pick}|{coppie}\n"); p.stdin.flush()
        except OSError as e:          # il processo e' appena caduto: al giro dopo riparte
            print("mazzi del pick:", e); self.calcolo["p"] = None; self.fase["lanciato"] = None


    def leggi_in_corsa(self):
        """Rilegge i tre mazzi del pick se sono cambiati; un file piu' vecchio dell'inizio del draft non vale."""
        try:
            mt = os.path.getmtime(PICK_JSON)
        except OSError:
            mt = None
        if mt == self.in_corsa["mtime"]:
            return
        d = None
        if mt is not None and mt >= self.inviato["da"]:
            try:
                d = json.load(open(PICK_JSON, encoding="utf-8"))
            except (OSError, ValueError):
                return                   # si riprova al giro dopo
        self.in_corsa.update(mtime=mt, d=d)
        if self.fase["v"] == "pick":
            self.disegna_mazzi()


    def lancia_overlay(self, argomenti):
        """L'overlay sopra Arena. Chi lo apre prima chiude quello di prima (Companion/App/Overlay/overlay.py, una_sola). -> True se e' partito.
        Solo su Windows: legge lo schermo con l'OCR di Windows e disegna con una finestra a strati di Windows (Distribuzione/Mac.md)."""
        if not piattaforma.WINDOWS:
            return False
        try:
            att = json.load(open(os.path.join(LOGDIR, "companion_attivo.json"), encoding="utf-8"))
        except (OSError, ValueError):
            att = {}
        cmd = [PY_MUTO, "-I", "-X", "utf8", percorsi.programma("overlay.py"), "--diario", att.get("diario") or self.diario.path] + argomenti
        if att.get("pid"):
            cmd += ["--pid", str(att["pid"])]
        try:
            subprocess.Popen(cmd, cwd=ROOT, stdout=subprocess.DEVNULL, stderr=open(os.path.join(LOGDIR, f"overlay_{time.strftime('%Y%m%d')}.txt"), "a", encoding="utf-8"))
            return True
        except OSError as e:
            print("overlay:", e)
            return False


    def seleziona_mazzo(self, n):
        """Select deck: l'overlay sopra Arena segue il mazzo n."""
        if self.lancia_overlay(["--dopo", f"{self.proposti['mtime'] or time.time():.0f}", "--mazzo", str(n)]):
            self.fase["scelto"] = n
        self.disegna_mazzi()


    def premi_fix(self):
        """Fix: l'overlay torna sopra Arena e segue il mazzo corretto; si chiude da solo al prossimo cancello (Autore, 7 nov 2026: «finche' il gate e' rosso, esiste un pulsante sotto al deck
        che dice fix, se lo premo riappare l'hud che mi aiuta a correggere»)."""
        if self.lancia_overlay(["--dopo", "0", "--mazzi", FIX_JSON, "--mazzo", "1"]):
            self.fix["on"] = self.fix["per"]
        self.disegna_mazzi()


    def calcola_fix(self, ora):
        """Il mazzo corretto si calcola a parte e a priorita' bassa, una volta per cancello (circa 10 s)."""
        self.fix.update(per=ora, d=None)

        def lavoro():
            d = None
            try:
                subprocess.run([piattaforma.python_console(), "-I", "-X", "utf8", percorsi.programma("correggi.py")], cwd=ROOT, stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL, timeout=300, **piattaforma.flag("sotto", "muto"), env=dict(os.environ, PYTHONIOENCODING="utf-8"))
                d = json.load(open(FIX_JSON, encoding="utf-8"))
            except (OSError, ValueError, subprocess.SubprocessError) as e:
                print("fix:", e)
            self.coda.put(("fix", (ora, d)))
        threading.Thread(target=lavoro, daemon=True).start()


    def mazzo_a_sinistra(self):
        """Il mazzo inviato sta a sinistra fuori dai pick, dalla costruzione e dalle partite, finche' il draft e' aperto."""
        if self.fase["v"] is not None or self.pescate.in_partita or self.FORZA_MAZZI == "proposti" or not self.draft_attivo():
            return False
        d_inv, d_pro = self.inviato["d"], self.proposti["d"]
        return bool(d_inv and self.mazzo_inviato(d_inv) and (not d_pro or (self.inviato["mtime"] or 0) >= (self.proposti["mtime"] or 0)))


    def disegna_sinistra(self, d):
        """Il mazzo inviato a sinistra: la testata (arte, nome, carte, colori, curva) e la lista per costo, come in Arena."""
        for w in self.b_m.winfo_children():
            w.destroy()
        vt = d.get("voto") or {}
        voci = [(q, n) for _c, cc in vt.get("costi") or [] for q, n in cc] + [(q, n) for q, n in vt.get("basi") or []]
        self.testata_mazzo(self.b_m, voci, vt.get("coppia", ""), vt.get("splash", ""), d.get("carte", sum(q for q, _ in voci)), 40, CI["scheda"]).pack(fill="x", pady=(0, 6))
        copie = {}
        for _c, q, n in self.mazzo_inviato(d):
            copie[n] = copie.get(n, 0) + q
        cv_l, griglia, lega = self.area_scorrevole(self.scorri_m, self.b_m)
        # una tela per la lista, non una per capsula (11 nov 2026, sessione Magic 13)
        self.liste.elenco(griglia, CAP.ordina(list(copie.items())), bg=CI["scheda"], passo=2).pack(fill="x", pady=1)
        lega(cv_l)


    def disegna_mazzi(self):
        """La scheda in basso a destra, secondo la fase: i tre mazzi possibili durante i pick, i 3 proposti col pulsante Select deck alla costruzione, poi il solo mazzo inviato
        (a sinistra la lista e qui la scheda, in partita qui la lista con le probabilita' di pescata e a sinistra la chat)."""
        self.lato()
        if self.scelta["v"] != "corso":       # distruggere etichette con immagini mai mostrate fa cadere Tk (Balance, 4 nov 2026): si ridisegna quando la scheda torna davanti
            self.fase["sporco"] = True
            return
        self.fase["sporco"] = False
        for w in self.b6.winfo_children():
            w.destroy()
        if self.fase["v"] == "pick":
            d = self.in_corsa["d"]
            self.tit_mazzi.configure(text=f"POSSIBLE DECKS · PICK {d['pick']}" if d else "POSSIBLE DECKS"); self.v_inv.set("")
            if d:
                self.disegna_in_corsa(d)
            else:
                self.avviso_mazzi("Possible decks show up after the first pick.")
            return
        if self.fase["v"] == "costruzione":
            self.tit_mazzi.configure(text="SUGGESTED DECKS"); self.v_inv.set("")
            if self.proposti["d"]:
                self.disegna_proposti(self.proposti["d"], pulsanti=True)
            else:
                self.avviso_mazzi("Building the three decks...")
            return
        d_inv, d_pro = self.inviato["d"], self.proposti["d"]
        if self.FORZA_MAZZI == "proposti":
            d_inv = None
        if not self.draft_attivo():
            self.tit_mazzi.configure(text="SUGGESTED DECKS"); self.v_inv.set("")
            self.avviso_mazzi("Suggested decks show up after the last pick, at deck building.")
            return
        # il mazzo inviato vale se e' arrivato dopo i proposti: prima del cancello restano i tre
        if d_inv and (not d_pro or (self.inviato["mtime"] or 0) >= (self.proposti["mtime"] or 0)):
            if self.lato_v["v"] == "mazzo":
                self.tit_mazzi.configure(text="DECK SHEET")
                self.disegna_sinistra(d_inv); self.disegna_scheda(d_inv)
            else:
                self.tit_mazzi.configure(text="SUBMITTED DECK")
                self.disegna_inviato(d_inv)
        elif d_pro:
            self.tit_mazzi.configure(text="SUGGESTED DECKS")
            self.disegna_proposti(d_pro)
        else:
            self.tit_mazzi.configure(text="SUGGESTED DECKS"); self.v_inv.set("")
            self.avviso_mazzi("Suggested decks show up after the last pick, at deck building.")


    def testata_mazzo(self, padre, voci, coppia, splash, carte, totale, bg):
        """La testata del mazzo, come una lista di Arena: arte, nome, carte, colori, curva di mana."""
        return self.liste.testata(padre, CAP.nome_mazzo(coppia, splash), carte, totale, CAP.curva(voci), CAP.copertina(voci), [x for x in "WUBRG" if x in (coppia or "") + (splash or "")], bg=bg)


    def due_valori(self, padre, sinistra, destra, bg=None, spazio=0):
        """Due dati sulla stessa riga, uno a sinistra e uno a destra (Autore, 5 nov 2026: «expected wins e % value mazzo mettili uno a sinistra uno a destra sulla stessa riga»)."""
        fondo = bg or CI["cap"]
        r = tk.Frame(padre, bg=fondo); r.pack(fill="x", pady=(4, 0))
        for lato, ancora, par in (("left", "w", sinistra), ("right", "e", destra)):
            if par is None:
                continue
            nome, valore = par
            b = tk.Frame(r, bg=fondo); b.pack(side=lato, padx=(spazio, 0) if lato == "right" else 0)
            tk.Label(b, text=nome, bg=fondo, fg=CI["titolo"], font=self.F(7, True), pady=0).pack(anchor=ancora)
            tk.Label(b, text=valore, bg=fondo, fg=CI["titolo"], font=self.F(11, True), pady=0).pack(anchor=ancora)


    def disegna_in_corsa(self, d):
        """I tre mazzi possibili durante i pick: colori, probabilita' data dal drafter, carte su 23, lista per costo. Niente voti: a pool incompleto non vogliono dire niente."""
        cv_l, tre, lega = self.area_scorrevole(self.scorri_c)
        for i, m in enumerate((d.get("mazzi") or [])[:3]):
            tre.columnconfigure(i, weight=1, uniform="mazzi")
            col = tk.Frame(tre, bg=CI["cap"]); col.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 4, 0))
            tk.Frame(col, bg=CI["accento"] if i == 0 else CI["filo"], height=2).pack(fill="x")
            dentro = tk.Frame(col, bg=CI["cap"]); dentro.pack(fill="both", expand=True, padx=8, pady=6)
            voci = [(q, n) for _c, carte in m.get("costi") or [] for q, n in carte]
            self.testata_mazzo(dentro, voci, m.get("coppia", ""), "", m.get("carte", 0), d.get("magie", 23), CI["cap"]).pack(fill="x")
            self.due_valori(dentro, ("CHANCE", "-" if m.get("pct") is None else f"{m['pct']}%"), None)
            tk.Frame(dentro, bg=CI["filo"], height=1).pack(fill="x", pady=(6, 4))
            self.liste.elenco(dentro, CAP.ordina([(n, q) for _c, carte in m.get("costi") or [] for q, n in carte]), bg=CI["cap"], passo=2).pack(fill="x", pady=1)
        lega(cv_l)


    def disegna_proposti(self, d, pulsanti=False):
        """I 3 mazzi di rating_mazzi in tre colonne affiancate: in cima tier, colori, vittorie attese e percentile, sotto la
        lista per costo e le terre base. Il primo, il consigliato, ha il filo azzurro in cima. Alla costruzione, sotto ogni colonna, il pulsante Select deck."""
        self.v_inv.set(f"costruiti alle {d.get('ora', '')[11:16]}")
        if pulsanti:
            barra = tk.Frame(self.b6, bg=CI["scheda"]); barra.pack(side="bottom", fill="x", pady=(6, 0))
            for i, m in enumerate((d.get("mazzi") or [])[:3]):
                barra.columnconfigure(i, weight=1, uniform="mazzi")
                on = self.fase["scelto"] == m.get("n")
                pulsante_solido(tk, self.F, barra, "HUD on Arena" if on else "Select deck", on, lambda n=m.get("n"): self.seleziona_mazzo(n), bg=CI["scheda"]).grid(row=0, column=i, sticky="ew", padx=(0 if i == 0 else 4, 0))
        cv_l, tre, lega = self.area_scorrevole(self.scorri_p)
        for i, m in enumerate((d.get("mazzi") or [])[:3]):
            tre.columnconfigure(i, weight=1, uniform="mazzi")
            col = tk.Frame(tre, bg=CI["cap"]); col.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 4, 0))
            tk.Frame(col, bg=CI["accento"] if i == 0 else CI["filo"], height=2).pack(fill="x")
            dentro = tk.Frame(col, bg=CI["cap"]); dentro.pack(fill="both", expand=True, padx=8, pady=6)
            voci = [(q, n) for _c, cc in m.get("costi") or [] for q, n in cc] + [(q, n) for q, n in m.get("terre") or []]
            self.testata_mazzo(dentro, voci, m.get("coppia", ""), m.get("splash", ""), sum(q for q, _ in voci), 40, CI["cap"]).pack(fill="x", pady=(0, 6))
            self.liste.dati(dentro, m.get("tier", "?"), COL_TIER.get(m.get("tier"), CI["muto"]), "EXPECTED WINS", self.num_it(m.get("vittorie")), bg=CI["cap"]).pack(fill="x")
            tk.Frame(dentro, bg=CI["filo"], height=1).pack(fill="x", pady=(6, 4))
            self.liste.elenco(dentro, CAP.ordina([(n, q) for _c, carte in m.get("costi") or [] for q, n in carte] + [(n, q) for q, n in m.get("terre") or []]),
                              bg=CI["cap"], passo=2).pack(fill="x", pady=1)
            # i nomi lunghi vanno a capo sulla larghezza vera della colonna (con un numero fisso uscivano tagliati)
            dentro.bind("<Configure>", lambda e, d_=dentro: [w.configure(wraplength=max(e.width - 2, 40)) for w in d_.winfo_children()
                                                            if isinstance(w, tk.Label) and int(str(w.cget("wraplength")) or 0)])
        lega(cv_l)


    def cancello_e_fix(self, d, vt, w_):
        """Il cancello rosso e il pulsante Fix sotto il voto del mazzo inviato: nella scheda della partita e nella scheda del mazzo."""
        rosso = d.get("cancello") == "rosso"
        if rosso:
            tk.Label(self.b6, text="gate red", bg=CI["scheda"], fg=CI["rosso_t"], font=self.F(8), anchor="w").pack(fill="x", pady=(4, 0))
        for t in d.get("rossi") or []:      # niente avvisi gialli sui mazzi (Autore, 5 nov 2026: «tira via dai mazzi gli avvisi gialli»), i rossi del cancello restano
            tk.Label(self.b6, text=en(t), bg=CI["scheda"], fg=CI["rosso_t"], font=self.F(8),
                     wraplength=360, justify="left", anchor="w").pack(fill="x")
        fx = self.fix["d"] if rosso and self.fix["per"] == d.get("ora") and not self.pescate.in_partita else None      # in partita il mazzo non si tocca
        if fx and fx.get("cambiato"):
            m = fx["mazzi"][0]
            pulsante_solido(tk, self.F, self.b6, "HUD on Arena" if self.fix["on"] == self.fix["per"] else "Fix", self.fix["on"] == self.fix["per"], self.premi_fix, alto=34, bg=CI["scheda"]).pack(fill="x", pady=(6, 3))
            conta = lambda nomi: ", ".join(f"{nomi.count(n)} {n}" for n in dict.fromkeys(nomi))
            tk.Label(self.b6, text=f"In: {conta([e for _, e in fx['scambi']])}  ·  Out: {conta([u for u, _ in fx['scambi']])}", bg=CI["scheda"], fg=CI["testo"], font=self.F(8), wraplength=360, justify="left", anchor="w").pack(fill="x")
            if m.get("vittorie") is not None and w_ is not None:     # il voto del mazzo corretto accanto a quello di adesso: il cancello verde non vuol dire un mazzo migliore
                tk.Label(self.b6, text=f"After fix: tier {m.get('tier')}, {m['vittorie']:.2f} expected wins  ·  Now: tier {vt.get('tier')}, {w_:.2f}", bg=CI["scheda"], fg=CI["testo"], font=self.F(8),
                         wraplength=360, justify="left", anchor="w").pack(fill="x")
            for t in fx.get("rossi") or []:
                tk.Label(self.b6, text="Still red after fix: " + en(t), bg=CI["scheda"], fg=CI["rosso_t"], font=self.F(8), wraplength=360, justify="left", anchor="w").pack(fill="x")
        elif fx:
            tk.Label(self.b6, text="No fix from your pool", bg=CI["scheda"], fg=CI["grigio"], font=self.F(8), anchor="w").pack(fill="x")


    def disegna_inviato(self, d):
        """Il mazzo inviato: in testa il voto (tier, colori, vittorie attese, cancello, avvisi di mana), sotto l'elenco; durante
        la partita con la probabilita' di pescare ogni carta alla prossima pescata, le carte gia' viste in grigio scuro a 0%."""
        vt = d.get("voto") or {}
        self.v_inv.set(f"cancello delle {d.get('ora', '')[11:16]}")
        voci = [(q, n) for _c, cc in vt.get("costi") or [] for q, n in cc] + [(q, n) for q, n in vt.get("basi") or []]
        self.testata_mazzo(self.b6, voci, vt.get("coppia", ""), vt.get("splash", ""), d.get("carte", sum(q for q, _ in voci)), 40, CI["scheda"]).pack(fill="x", pady=(0, 6))
        w_ = vt.get("vittorie")
        self.liste.dati(self.b6, str(vt.get("tier", "?")), COL_TIER.get(vt.get("tier"), CI["muto"]), "EXPECTED WINS", "-" if w_ is None else f"{w_:.2f}", bg=CI["scheda"]).pack(fill="x")
        self.cancello_e_fix(d, vt, w_)
        tk.Frame(self.b6, bg=CI["filo"], height=1).pack(fill="x", pady=(6, 4))
        mazzo = self.mazzo_inviato(d)
        if not mazzo:
            tk.Label(self.b6, text="List missing: this deck was rated before the list was saved", bg=CI["scheda"],
                     fg=CI["grigio"], font=self.F(8), anchor="w").pack(fill="x")
            return
        # fuori dalla partita l'elenco resta, senza le probabilita' di pescata (Autore, 18 ott 2026: «ne resta solo 1 con
        # sopra tutti i dati»)
        in_gioco = self.pescate.in_partita
        righe, lib = self.pescate.elenco(mazzo) if in_gioco else ([(c, q, n, q, None) for c, q, n in mazzo], sum(q for _, q, _ in mazzo))
        if in_gioco:
            testa_l = tk.Frame(self.b6, bg=CI["scheda"]); testa_l.pack(fill="x")
            tk.Label(testa_l, text=f"DRAW ODDS · {lib} IN LIBRARY", bg=CI["scheda"], fg=CI["titolo"], font=self.F(7, True), pady=0).pack(side="right", padx=(0, 6))
        # l'elenco scorre con la rotella: 15-20 righe non stanno sotto le altre schede. La posizione resta a ogni ridisegno
        cv_l, griglia, lega = self.area_scorrevole(self.scorri_l)
        copie = {n: (rim, q, pc) for _c, q, n, rim, pc in righe}
        voci = []
        for n, _q in CAP.ordina([(n, q) for n, (_r, q, _p) in copie.items()]):
            rim, q, pc = copie[n]
            vista = in_gioco and rim == 0              # gia' vista o pescata: spenta, 0%
            voci.append((n, q, dict(spenta=vista, copie=(f"{rim}/{q}" if in_gioco and q > 1 else None), colonna="100%" if in_gioco else "",
                                    destra="" if pc is None else ("0%" if vista else (f"{pc:.0f}%" if pc >= 1 else "<1%")))))
        self.liste.elenco(griglia, voci, bg=CI["scheda"], passo=2).pack(fill="x", pady=1)      # una tela per la lista (11 nov 2026)
        lega(cv_l)


    def leggi_inviato(self, forza=False):
        """Rilegge Log_Arena/mazzo_inviato.json se e' cambiato; un file piu' vecchio dell'inizio del draft in corso non vale."""
        try:
            mt = os.path.getmtime(INVIATO_JSON)
        except OSError:
            mt = None
        if mt == self.inviato["mtime"] and not forza:
            return
        self.inviato["mtime"] = mt
        d = None
        if mt is not None and mt >= self.inviato["da"]:
            try:
                d = json.load(open(INVIATO_JSON, encoding="utf-8"))
            except ValueError:
                self.inviato["mtime"] = None      # file a meta' o rovinato: si riprova al giro dopo
                return
        self.inviato["d"] = d
        if d and d.get("cancello") == "rosso" and d.get("ora") != self.fix["per"]:
            self.calcola_fix(d.get("ora"))
        self.disegna_mazzi(); self.disegna_partita(); self.disegna_forza()


    def leggi_proposti(self, forza=False):
        """Rilegge Log_Arena/mazzi_costruzione.json (i 3 mazzi di rating_mazzi a fine pick) se e' cambiato; un file piu'
        vecchio dell'inizio del draft in corso non vale."""
        try:
            mt = os.path.getmtime(MAZZI_JSON)
        except OSError:
            mt = None
        if mt == self.proposti["mtime"] and not forza:
            return
        self.proposti["mtime"] = mt
        d = None
        if mt is not None and mt >= self.inviato["da"]:
            try:
                d = json.load(open(MAZZI_JSON, encoding="utf-8"))
            except ValueError:
                self.proposti["mtime"] = None
                return
        self.proposti["d"] = d
        self.disegna_mazzi()
