"""La Deck sheet del mazzo inviato: tier, Expected wins, WIN TURNS (dalle partite del draft o dal motore), ARCHETYPE. Mixin di Finestra (App/finestra.py)."""
import datetime
import json
import os
import subprocess

import piattaforma  # (Windows e Mac: flag dei processi, Python)
import tkinter as tk
import types

from ambiente import LOGDIR, PY_MUTO, ROOT
from pagina_standard import PaginaStandard
from tema import CI, COL_TIER


class DeckSheet:
    """La Deck sheet del mazzo inviato: tier, Expected wins, WIN TURNS (dalle partite del draft o dal motore), ARCHETYPE."""

    def firma_mazzo(self, voci):
        """La firma di Motore_Partita/turni_chiusura.firma (la stessa stringa: chi scrive e chi legge devono trovarsi). Copiata per non caricare il motore nella finestra."""
        conta = {}
        for q, n in voci:
            conta[n] = conta.get(n, 0) + q
        return "|".join(f"{q} {n}" for n, q in sorted(conta.items()))


    def turni_motore(self, voci):
        """Il turno di chiusura stimato col motore (120 partite simulate contro i tuoi 10 mazzi, arbitro acceso, grado C). Se manca, la misura parte una volta, a parte e a priorita'
        bassa, fuori dalle partite (circa 20 s): la scheda si ridisegna quando il file cambia. -> dict(turno, vinte, partite) o dict(turno=None, perche), None se non c'e' ancora."""
        k = self.firma_mazzo(voci)
        try:
            r = json.load(open(self.FILE_TURNI, encoding="utf-8")).get(k)
        except (OSError, ValueError):
            r = None
        if r is None and self.motore["lanciato"] != k and not self.pescate.in_partita:
            self.motore["lanciato"] = k
            try:
                subprocess.Popen([PY_MUTO, "-I", "-X", "utf8", os.path.join(ROOT, "Motore_Partita", "turni_chiusura.py")], cwd=ROOT, stdout=subprocess.DEVNULL,
                                 stderr=open(os.path.join(LOGDIR, "turni_chiusura_errori.txt"), "a", encoding="utf-8"), **piattaforma.flag("sotto", "muto"))
            except OSError as e:
                print("turni del motore:", e)
        return r


    def guarda_motore(self):
        """Il file del motore e' cambiato: la scheda del mazzo si ridisegna coi turni nuovi."""
        try:
            mt = os.path.getmtime(self.FILE_TURNI)
        except OSError:
            mt = None
        if mt != self.motore["mtime"]:
            primo = self.motore["mtime"] is None and mt is not None and not self.motore["lanciato"]
            self.motore["mtime"] = mt
            if not primo and self.lato_v["v"] == "mazzo":
                self.numeri_cache.clear(); self.disegna_mazzi()


    def partite_del_draft(self):
        """Le partite di questo draft su Untapped: l'ultimo draft, se non e' cominciato prima della riga «=== DRAFT» (tutti i Quick di un set hanno lo stesso evento: decide l'ora)."""
        D = self.stato.get("draft") or []
        if not D:
            return []
        u = D[-1]
        if self.inviato["da"]:
            if u["quando"] < datetime.datetime.fromtimestamp(self.inviato["da"]) - datetime.timedelta(minutes=5):
                return []
        elif u["w"] >= 7 or u["l"] >= 3:
            return []
        return u.get("partite") or []


    def numeri_mazzo(self, d):
        """-> dict(an, motore, arch, n): i numeri veri del draft (dati_mazzo.analizza), il motore, l'archetipo (dati_mazzo.archetipo, grado C)."""
        vt = d.get("voto") or {}
        voci = [(q, n) for _c, cc in vt.get("costi") or [] for q, n in cc] + [(q, n) for q, n in vt.get("basi") or []]
        partite = self.partite_del_draft()
        k = (d.get("ora"), len(partite), self.motore["mtime"])
        if k in self.numeri_cache:
            return self.numeri_cache[k]
        import dati_mazzo as DM
        carte = DM.tabella_carte()
        an = DM.analizza(partite, carte) if partite else None
        main = {}
        for q, n in voci:
            main[n] = main.get(n, 0) + q
        r = dict(an=an, motore=self.turni_motore(voci), arch=DM.archetipo(main, carte, an["chiude"] if an else None), n=len(partite))
        self.numeri_cache.clear(); self.numeri_cache[k] = r
        return r


    def riquadri(self, padre, voci):
        """Una riga di numeri: ogni numero nel suo riquadro, il nome sopra in maiuscolo bianco, una nota grigia sotto."""
        g = tk.Frame(padre, bg=CI["scheda"]); g.pack(fill="x", pady=(8, 0))
        for i, (nome, valore, nota) in enumerate(voci):
            g.columnconfigure(i, weight=1, uniform="num")
            b = tk.Frame(g, bg=CI["cap"], padx=8, pady=6); b.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 4, 0))
            tk.Label(b, text=nome, bg=CI["cap"], fg=CI["titolo"], font=self.F(7, True), anchor="w", pady=0).pack(fill="x")
            tk.Label(b, text=valore, bg=CI["cap"], fg=CI["titolo"], font=self.F(13, True), anchor="w", pady=0).pack(fill="x")
            tk.Label(b, text=nota, bg=CI["cap"], fg=CI["grigio"], font=self.F(7), anchor="w", pady=0, justify="left", wraplength=150).pack(fill="x")


    def disegna_scheda(self, d):
        """La scheda del mazzo inviato, a destra quando il mazzo sta a sinistra: tier e vittorie attese, il cancello, i turni (le partite vere del draft, prima il motore) e l'archetipo."""
        vt = d.get("voto") or {}
        self.v_inv.set(f"cancello delle {d.get('ora', '')[11:16]}")
        w_ = vt.get("vittorie")
        self.liste.dati(self.b6, str(vt.get("tier", "?")), COL_TIER.get(vt.get("tier"), CI["muto"]), "EXPECTED WINS", "-" if w_ is None else f"{w_:.2f}", bg=CI["scheda"]).pack(fill="x")
        self.cancello_e_fix(d, vt, w_)
        try:
            nm = self.numeri_mazzo(d)
        except Exception as e:
            print("scheda del mazzo:", f"{type(e).__name__}: {e}")
            nm = dict(an=None, motore=None, arch=None, n=0)
        an, mo = nm["an"], nm["motore"]
        rec = lambda x: "-" if not x or not x[1] else f"{x[0]}-{x[1] - x[0]}"
        if an and an["chiude"]:
            chiude = (f"T{an['chiude'][0]:.1f}", f"{an['chiude'][1]} {'win' if an['chiude'][1] == 1 else 'wins'} in this draft")
        elif mo and mo.get("turno"):
            chiude = (f"≈T{mo['turno']:.1f}", f"engine estimate, {mo['vinte']} of {mo['partite']} simulated games won")
        elif mo:
            chiude = ("-", "engine: " + ("only FRA cards" if "NonCoperto" in str(mo.get("perche")) or "non" in str(mo.get("perche", "")).lower() else str(mo.get("perche", ""))[:40]))
        else:
            chiude = ("…", "engine estimate running" if self.motore["lanciato"] else "no wins yet")
        perde = (f"T{an['perde'][0]:.1f}", f"{an['perde'][1]} {'loss' if an['perde'][1] == 1 else 'losses'}") if an and an["perde"] else ("-", "no losses with turn data" if nm["n"] else "no games yet")
        tk.Label(self.b6, text="WIN TURNS", bg=CI["scheda"], fg=CI["titolo"], font=self.F(8, True), anchor="w").pack(fill="x", pady=(12, 0))
        self.riquadri(self.b6, [("CLOSES ON", *chiude), ("LOSES ON", *perde),
                      ("ON THE PLAY", rec(an and an["play"]), "won-lost"), ("ON THE DRAW", rec(an and an["draw"]), "won-lost")])
        tk.Label(self.b6, text="ARCHETYPE", bg=CI["scheda"], fg=CI["titolo"], font=self.F(8, True), anchor="w").pack(fill="x", pady=(12, 0))
        arch = nm["arch"]
        box = tk.Frame(self.b6, bg=CI["cap"], padx=8, pady=6); box.pack(fill="x", pady=(4, 0))
        if arch:
            tk.Label(box, text=arch[0], bg=CI["cap"], fg=CI["acciaio"], font=self.F(10, True), anchor="w").pack(fill="x")
            PaginaStandard.radar(types.SimpleNamespace(tk=tk, F=self.F), box, arch[1], lato=150).pack()
        else:
            tk.Label(box, text="-", bg=CI["cap"], fg=CI["grigio"], font=self.F(9), anchor="w").pack(fill="x")
