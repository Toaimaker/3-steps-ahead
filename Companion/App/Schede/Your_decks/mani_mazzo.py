"""Le mani iniziali di un mazzo, carta per carta."""
import capsule as CAP
import dati_mazzo as DM

from tema import CI as C, barra_scura


class ManiMazzo:
    """Le mani iniziali carta per carta, in una finestra sopra quella del mazzo."""

    def finestra_mani(self, titolo, esempi, coppia):
        """Le mani vere dietro una best starting hand o una vittoria veloce, carta per carta (Autore, 8 nov 2026: «la best starting hand: possiamo farla che si apre in una sotto finestra e
        mostra effettivamente le carte che si hanno in mano?»). Una mano alla volta, le frecce (o i tasti) per le altre partite della stessa coppia: prima le vinte, dalla piu' veloce.
        Le due carte della coppia hanno il bordo azzurro. Sopra la finestra del mazzo, transient, si chiude con la X o con Esc."""
        tk, F = self.tk, self.F
        vecchia = getattr(self, "fin_mani", None)
        if vecchia is not None and vecchia.winfo_exists():
            vecchia.destroy()
        padre = self.fin if self.fin is not None and self.fin.winfo_exists() else self.fr.winfo_toplevel()
        f = self.fin_mani = tk.Toplevel(padre, bg=C["fondo"])
        f.transient(padre)
        f.title(f"Starting hand · {titolo}")
        barra_scura(f, C["fondo"], C["titolo"], C["filo"])
        f.bind("<Escape>", lambda e: f.destroy())
        carte = getattr(self, "carte_db", None) or DM.tabella_carte()
        lista = CAP.Liste(tk, F)
        stato = {"i": 0}
        testa = tk.Frame(f, bg=C["cap"]); testa.pack(fill="x")
        tk.Label(testa, text=titolo, bg=C["cap"], fg=C["titolo"], font=F(13, True)).pack(side="left", padx=(14, 10), pady=10)
        info = tk.Label(testa, text="", bg=C["cap"], fg=C["testo"], font=F(10)); info.pack(side="left")
        frecce = tk.Frame(testa, bg=C["cap"]); frecce.pack(side="right", padx=12)
        tk.Frame(f, bg=C["filo"], height=1).pack(fill="x")
        corpo = tk.Frame(f, bg=C["scheda"], padx=14, pady=14); corpo.pack(fill="both", expand=True)

        def ordine(nome):
            c = carte.get(nome) or carte.get(nome.split(" // ")[0].strip()) or {}
            terra = "Land" in (c.get("tipo") or "").split(" // ")[0]
            return (terra, c.get("cmc", 0), nome)

        def mostra():
            for w in corpo.winfo_children():
                w.destroy()
            lista.nuova_pagina()
            x = esempi[stato["i"]]
            esito = (f"won on T{x['turno']}" if x["turno"] else "won") if x["vinta"] else (f"lost on T{x['turno']}" if x["turno"] else "lost")
            parti = [esito, "on the play" if x["primo"] else "on the draw" if x["primo"] is False else None, f"{x['terre']} lands"]
            info.configure(text="  ·  ".join(p for p in parti if p), fg=C["verde_t"] if x["vinta"] else C["rosso_t"])
            nomi = [n for n in sorted(x["mano"], key=ordine) for _ in range(x["mano"][n])]
            riga = tk.Frame(corpo, bg=C["scheda"]); riga.pack()
            for n in nomi:
                cornice = tk.Frame(riga, bg=C["accento"] if n in coppia else C["scheda"], padx=3, pady=3); cornice.pack(side="left", padx=3)
                lista.carta_piena(cornice, n, sotto="", bg=C["scheda"]).pack()
            for w in frecce.winfo_children():
                w.destroy()
            if len(esempi) > 1:
                def vai(d):
                    stato["i"] = (stato["i"] + d) % len(esempi); mostra()
                tk.Label(frecce, text="‹", bg=C["cap"], fg=C["acciaio"], font=F(16, True), cursor="hand2").pack(side="left")
                frecce.winfo_children()[-1].bind("<Button-1>", lambda e: vai(-1))
                tk.Label(frecce, text=f"game {stato['i'] + 1} of {len(esempi)}", bg=C["cap"], fg=C["grigio"], font=F(9)).pack(side="left", padx=8)
                tk.Label(frecce, text="›", bg=C["cap"], fg=C["acciaio"], font=F(16, True), cursor="hand2").pack(side="left")
                frecce.winfo_children()[-1].bind("<Button-1>", lambda e: vai(1))
                f.bind("<Left>", lambda e: vai(-1)); f.bind("<Right>", lambda e: vai(1))
        mostra()
        f.update_idletasks()
        L = max(f.winfo_reqwidth(), 520)
        H = f.winfo_reqheight()
        top = padre
        f.geometry(f"{L}x{H}+{top.winfo_rootx() + max(0, (top.winfo_width() - L) // 2)}+{top.winfo_rooty() + max(0, (top.winfo_height() - H) // 2)}")
        f.lift(); f.focus_set()
        return f
