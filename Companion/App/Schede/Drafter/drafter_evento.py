"""La scheda Drafter senza un draft aperto e intorno al draft: la spunta Rare pick, il calendario degli eventi limited, Play limited e Launch, Closed session, il record del draft. Mixin di Finestra (App/finestra.py)."""
import datetime
import json
import os
import subprocess

import piattaforma  # (Windows e Mac: flag dei processi, Python)
import sys
import threading
import time
import tkinter as tk
import tkinter.font as tkfont

import calendario_eventi as CE
import capsule as CAP
import percorsi

import disegni as DG

from ambiente import DIARIO_FISSO, LOGDIR, PY_MUTO, ROOT
from diario import processo_vivo
from tema import CI, FN


class DrafterEvento:
    """La scheda Drafter senza un draft aperto e intorno al draft: la spunta Rare pick, il calendario degli eventi limited, Play limited e Launch, Closed session, il record del draft."""

    def rare_attivo(self):
        try:
            return bool(json.load(open(self.FILE_RARE_PICK, encoding="utf-8")).get("attivo", True))
        except (OSError, ValueError, AttributeError):
            return True


    def disegna_rare(self):
        on = self.rare_attivo()
        for c, l in self.spunte_rare:
            c.delete("all")
            c.create_image(0, 0, image=DG.spunta(13, on, CI["azzurro"], CI["fondo"], CI["grigio"], CI["fondo"]), anchor="nw")
            l.configure(fg=CI["titolo"] if on else CI["grigio"])


    def cambia_rare(self, e=None):
        try:
            with open(self.FILE_RARE_PICK, "w", encoding="utf-8") as f:
                json.dump({"attivo": not self.rare_attivo(), "quando": time.strftime("%Y-%m-%d %H:%M:%S")}, f)
        except OSError as er:
            print("rare pick:", er)
        self.disegna_rare()


    def spunta_rare(self, cap):
        r = tk.Frame(cap, bg=CI["cap"], cursor="hand2"); r.pack(side="right", padx=10)
        c = tk.Canvas(r, width=13, height=13, bg=CI["cap"], highlightthickness=0, cursor="hand2"); c.pack(side="left", padx=(0, 6))
        l = tk.Label(r, text="RARE PICK", bg=CI["cap"], font=self.F(8, True), cursor="hand2"); l.pack(side="left")
        for w in (r, c, l):
            w.bind("<Button-1>", self.cambia_rare)
        self.spunte_rare.append((c, l))
        self.disegna_rare()


    def scegli_cal(self, o=None):
        CE.salva_esclusi(set(self.calen["tipi"]) - set(self.t_cal.get()))
        self.cv_cal.yview_moveto(0)
        self.disegna_calendario()


    def disegna_calendario(self, e=None):
        """Una tela sola, scorre con la rotella: titolo, start, end, giorni rimasti. Aperti in testa, poi i prossimi."""
        c = self.cv_cal; c.delete("all")
        W = c.winfo_width()
        if W < 50:
            return
        x_s, x_e, x_g = W - 214, W - 142, W - 4
        c.create_text(0, 8, text="EVENT", anchor="w", fill=CI["titolo"], font=self.F(7, True))
        for x, t in ((x_s, "START"), (x_e, "END")):
            c.create_text(x, 8, text=t, anchor="w", fill=CI["titolo"], font=self.F(7, True))
        c.create_text(x_g, 8, text="DAYS LEFT", anchor="e", fill=CI["titolo"], font=self.F(7, True))
        y = 20
        f_n = tkfont.Font(font=self.F(9))
        if not self.calen["righe"]:
            c.create_text(0, y + 12, text="The calendar shows up once it has been read", anchor="w", fill=CI["grigio"], font=self.F(9))
        scelti = set(self.t_cal.get())
        for i, r in enumerate(x_ for x_ in self.calen["righe"] if x_["tipo"] in scelti):
            if i % 2 == 0:
                c.create_rectangle(0, y, W, y + 24, fill=CI["fondo"], width=0)
            nome, largo = r["nome"], x_s - 12
            while f_n.measure(nome) > largo and len(nome) > 4:
                nome = nome[:-2].rstrip() + "…" if nome.endswith("…") is False else nome[:-3].rstrip() + "…"
            c.create_text(6, y + 12, text=nome, anchor="w", fill=CI["titolo"] if r["aperto"] else CI["testo"], font=self.F(9))
            for x, d in ((x_s, r["inizio"]), (x_e, r["fine"])):
                c.create_text(x, y + 12, text=f"{d.day} {d:%b}", anchor="w", fill=CI["testo"], font=self.F(9))
            if r["aperto"]:
                t, col = ("last day" if r["giorni"] == 1 else f"{r['giorni']} days"), (CI["rosso"] if r["giorni"] <= 2 else CI["arancio"] if r["giorni"] <= 5 else CI["verde"])
            else:
                t, col = ("tomorrow" if r["giorni"] == 1 else f"opens in {r['giorni']}"), CI["grigio"]
            c.create_text(x_g, y + 12, text=t, anchor="e", fill=col, font=self.F(9, True))
            y += 24
        c.configure(scrollregion=(0, 0, W, y + 4))


    def leggi_calendario(self):
        """Rilegge il file se e' cambiato, o se e' cambiato il giorno: i giorni rimasti scendono da soli."""
        try:
            chiave = (os.path.getmtime(CE.FILE), datetime.date.today())
        except OSError:
            chiave = None
        if chiave != self.calen["file"]:
            self.calen["file"] = chiave
            self.calen["righe"] = CE.righe(CE.carica())
            tipi = CE.tipi(self.calen["righe"])
            if tipi != self.calen["tipi"]:
                self.calen["tipi"] = tipi
                self.t_cal.opzioni(tipi, self.scegli_cal)
                self.t_cal.set([t for t in tipi if t not in CE.leggi_esclusi()] or tipi)
            self.disegna_calendario()


    def rinfresca_calendario(self):
        """Una volta al giorno, in sottofondo; se la pagina non risponde resta il file di prima."""
        try:
            vecchio = time.time() - os.path.getmtime(CE.FILE) > 86400
        except OSError:
            vecchio = True
        if vecchio and "--diario" not in sys.argv:
            threading.Thread(target=CE.aggiorna, daemon=True).start()
        self.root.after(3600000, self.rinfresca_calendario)


    def mazzo_inviato(self, d):
        """[(costo, quante, nome)] del mazzo inviato: le magie per costo, poi le terre (costo 0 per le non base, 99 le basi)."""
        vt = (d or {}).get("voto") or {}
        out = [(c, q, n) for c, carte in vt.get("costi") or [] for q, n in carte]
        out += [(99, q, n) for q, n in vt.get("basi") or []]
        return out


    def draft_attivo(self):
        """C'e' un draft aperto: una riga «=== DRAFT» nel diario di oggi senza «=== FINE DRAFT» dopo, o l'ultimo draft di
        Untapped ancora aperto (meno di 7 vinte e di 3 perse). Senza draft la scheda dei mazzi non mostra dati (Autore,
        17 ott 2026: «non ci sono partite in corso quindi non dovrei vedere dati»)."""
        if self.FORZA_MAZZI:
            return True
        if self.stato["draft_finito"]:
            return False
        lg = self.stato.get("log_limited")           # il log di Arena dice se c'e' un limited a meta', anche a companion spento; senza log resta Untapped
        return self.inviato["da"] > 0 or (lg["aperto"] and not self.finito_su_untapped(lg) if lg else self.stato["untapped_in_corso"])


    def finito_su_untapped(self, lg):
        """Il corso viene dal log della sessione prima (w None) e Untapped dice che l'ultimo draft di quell'evento e' finito (7 vinte o
        3 perse): e' chiuso. Il Player-prev.log tiene l'ultimo stato che Arena ha scritto, spesso CreateMatch prima dell'ultima partita
        (8 nov 2026, Autore: «il drafter continua a restare aperto sull'ultimo quick draft»: QuickDraft_FRA_20261027, 3-3 su Untapped)."""
        if not lg or lg.get("w") is not None:
            return False
        stessi = [x for x in self.stato.get("draft") or [] if x.get("evento") == lg.get("evento")]
        return bool(stessi) and (stessi[-1]["w"] >= 7 or stessi[-1]["l"] >= 3)


    def aggiorna_play(self):
        """This draft o Play limited, secondo se c'e' un evento limited avviato. Finche' i dati del draft non sono arrivati non si cambia niente."""
        if "ora_dati" not in self.stato and "log_limited" not in self.stato and "--play" not in sys.argv:
            return
        giocare = not self.draft_attivo() and self.fase["v"] is None
        if giocare != self.play["mostra"]:
            self.play["mostra"] = giocare
            self.v_ev.tit.configure(text="PLAY LIMITED" if giocare else "THIS DRAFT")
            (self.tela_rec if giocare else self.f_play).pack_forget(); self.f_chiudi.pack_forget()
            (self.f_play if giocare else self.tela_rec).pack(fill="x")
            if not giocare:
                self.f_chiudi.pack(fill="x", after=self.tela_rec)
                self.chiusura["conferma"] = None; self.l_chiudi.configure(text=""); self.b_chiudi.metti("Closed session", False)
            (self.s6 if giocare else self.s_cal).pack_forget()        # senza un evento il calendario al posto dei mazzi, che non ci sono
            (self.s_cal if giocare else self.s6).pack(fill="both", expand=True)
            if giocare:           # un evento appena chiuso: si riparte da Launch
                self.play["stato"] = "fermo"; self.b_play.metti("Launch", False)
        testo = {"fermo": "No limited event running", "avvio": "Getting the limited companion ready…", "pronto": "Ready: join an event in Arena", "errore": "The companion did not start: open Companion.bat"}[self.play["stato"]]
        if self.l_play.cget("text") != testo:
            self.l_play.configure(text=testo, fg=CI["verde"] if self.play["stato"] == "pronto" else CI["rosso"] if self.play["stato"] == "errore" else CI["grigio"])
            self.b_play.metti("Launch", self.play["stato"] == "avvio")


    def chiudi_sessione(self):
        """Closed session: il primo clic chiede conferma per 4 s, il secondo chiude il draft. La finestra torna a Play limited quando legge «=== FINE DRAFT» nel diario."""
        if self.chiusura["conferma"] is None or time.time() - self.chiusura["conferma"] > 4:
            self.chiusura["conferma"] = time.time()
            self.b_chiudi.metti("Click again to close", False)
            self.l_chiudi.configure(text="Closes the draft and starts the post-draft rotation", fg=CI["arancio"])

            def torna(t0=self.chiusura["conferma"]):
                if self.chiusura["conferma"] == t0:
                    self.chiusura["conferma"] = None; self.b_chiudi.metti("Closed session", False); self.l_chiudi.configure(text="")
            self.root.after(4000, torna)
            return
        self.chiusura["conferma"] = 0
        self.b_chiudi.metti("Closing…", True); self.l_chiudi.configure(text="Closing the draft", fg=CI["grigio"])
        ev = self.fase.get("evento") or ""
        cmd = [PY_MUTO, "-I", "-X", "utf8", percorsi.programma("chiudi_draft.py"), "--diario", self.diario.file_oggi(), "--w", str(self.rec["w"]), "--l", str(self.rec["l"])] + (["--evento", ev] if ev else [])
        if "--senza-giro" in sys.argv:        # collaudo: chiude soltanto
            cmd.append("--senza-giro")
        if "--log-limited" in sys.argv:       # collaudo: il log dato, non il Player.log vero
            cmd += ["--log", sys.argv[sys.argv.index("--log-limited") + 1]]
        try:            # il giro dura minuti: va da solo, a priorita' bassa, e resta anche se la finestra si chiude
            subprocess.Popen(cmd, cwd=ROOT, stdout=subprocess.DEVNULL, stderr=open(os.path.join(LOGDIR, "chiudi_draft_errori.txt"), "a", encoding="utf-8"),
                             **piattaforma.flag("sotto", "staccato"))
        except OSError as e:
            print("closed session:", e); self.b_chiudi.metti("Closed session", False); self.l_chiudi.configure(text="Did not start", fg=CI["rosso"])


    def lancia_limited(self):
        """Launch: il companion, se e' spento, poi il controllo dei motori. La riga LIMITED arriva in chat dal diario e dice pronto; il motore lo sceglie il companion dall'evento."""
        if self.play["stato"] == "avvio":
            return
        self.play["stato"] = "avvio"; self.aggiorna_play()
        threading.Thread(target=self.prepara_limited, daemon=True).start()


    def prepara_limited(self):
        """Sul suo filo, senza toccare Tk: la finestra legge play["stato"] al giro dopo."""
        try:
            percorso = DIARIO_FISSO or self.companion_acceso()
            if not percorso:
                self.play["stato"] = "errore"; return
            subprocess.run([PY_MUTO, "-I", "-X", "utf8", percorsi.programma("pronto_limited.py"), "--diario", percorso], cwd=ROOT, stdout=subprocess.DEVNULL,
                           stderr=open(os.path.join(LOGDIR, "pronto_limited_errori.txt"), "a", encoding="utf-8"), timeout=900, **piattaforma.flag("sotto"))
        except (OSError, subprocess.SubprocessError) as e:
            print("launch:", e); self.play["stato"] = "errore"


    def companion_acceso(self):
        """Il diario del companion acceso; se e' spento lo accende nella sua console, come Companion.bat, e aspetta che abbia letto il log. -> il diario, None se non parte."""
        def vivo():
            try:
                a = json.load(open(os.path.join(LOGDIR, "companion_attivo.json"), encoding="utf-8"))
                return a if processo_vivo(a["pid"]) else None
            except (OSError, ValueError, KeyError, TypeError):
                return None
        a = vivo()
        if a:
            return a["diario"]
        t0 = time.strftime("%H:%M:%S")
        subprocess.Popen([piattaforma.python_console(), "-I", "-X", "utf8", percorsi.programma("companion.py")], cwd=ROOT,
                         env=dict(os.environ, PYTHONIOENCODING="utf-8"), **piattaforma.flag("console"))
        for _ in range(240):
            time.sleep(0.5)
            a = vivo()
            if a:
                try:
                    with open(a["diario"], encoding="utf-8", errors="ignore") as f:
                        if any("COMPANION ATTIVO" in r and r[:8] >= t0 for r in f):
                            return a["diario"]
                except OSError:
                    pass
        return None


    def disegna_record(self):
        """Il record del draft: una coppa per ogni vinta, un teschio per ogni persa, i colori e il win rate, in un Canvas sopra l'arte."""
        L = self.tela_rec.winfo_width()
        # la tela si misura mentre la finestra si costruisce (dall'11 nov 2026 la finestra compare prima dei dati): record e mazzo arrivano dopo
        if L < 60 or not hasattr(self, "rec") or not hasattr(self, "inviato"):
            return
        w, l = self.rec["w"], self.rec["l"]
        c = self.tela_rec
        c.delete("all")
        vt = (self.inviato["d"] or {}).get("voto") or {}
        arte = CAP.copertina([(q, n) for _c, cc in vt.get("costi") or [] for q, n in cc], 1)
        c.create_image(0, 0, image=self.liste.fondo_testata(L, arte, self.ALTO_REC, 150), anchor="nw")
        self.liste.chiedi_arte(c, arte, self.disegna_record)

        def scritta(x, y, testo, ancora, col, font):
            c.create_text(x + 1, y + 1, text=testo, anchor=ancora, fill="#000000", font=font)
            c.create_text(x, y, text=testo, anchor=ancora, fill=col, font=font)
        scritta(12, 15, "DRAFT GAMES", "w", CI["titolo"], self.F(7, True))
        scritta(L - 12, 15, "WIN RATE", "e", CI["titolo"], self.F(7, True))
        seq = self.rec["seq"] if len(self.rec["seq"]) == (w or 0) + (l or 0) else (["v"] * w + ["p"] * l if w is not None else [])
        x = 12
        for k in seq:
            if k in self.img_rec:
                c.create_image(x, 45, image=self.img_rec[k], anchor="w"); x += 28
            else:
                scritta(x, 45, "W" if k == "v" else "L", "w", CI["verde_t"] if k == "v" else CI["rosso_t"], self.F(12, True)); x += 18
        if not seq and w is not None:
            scritta(12, 45, "no games yet", "w", CI["grigio"], self.F(9))
        x = L - 12
        if w is not None and w + l:
            wr = round(100 * w / (w + l))
            scritta(L - 12, 34, f"{wr}%", "e", CI["verde_t"] if wr >= 50 else CI["rosso_t"], FN(18))
            scritta(L - 12, 57, f"{w} won, {l} lost", "e", "#d2d2d6", self.F(8))
            x -= 86
        for k in reversed(self.stato["draft_colori"] or ""):
            if k in self.mana:
                c.create_image(x, 36, image=self.mana[k], anchor="e"); x -= 20
