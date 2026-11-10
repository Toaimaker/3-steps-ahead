"""La finestra dei 3 mazzi alla costruzione (Autore, 17 ott 2026: «i mazzi non li da nella chat ma crea una finestra a 3
colonne: in cima i dati dei mazzi e il tier, sotto l'elenco di ognuno»).

Legge Log_Arena/mazzi_costruzione.json, che scrive Companion/Drafter/rating_mazzi.py (il companion lo lancia con --finestra
alla COSTRUZIONE e la finestra si apre da sola). Una colonna per mazzo: in cima il tier, la coppia coi simboli di mana, le
vittorie attese, i percentili, lo splash e gli avvisi di mana; sotto la lista per costo e le terre. Se il file cambia (un
draft nuovo) la finestra si ridisegna da sola.

Tier dal percentile sui pool di 17Lands: S 95+, A 85+, B 70+, C 50+, D sotto (rating_mazzi.tier).

    python -I -X utf8 Companion/App/Schede/Drafter/finestra_mazzi.py           la finestra
    python -I -X utf8 Companion/App/Schede/Drafter/finestra_mazzi.py --prova   controlla il file e stampa le colonne, senza finestra
"""
import os, sys
_casa = os.path.dirname(os.path.abspath(__file__))      # si sale fino a percorsi.py, che mette nel sys.path tutte le cartelle del Companion
while not os.path.isfile(os.path.join(_casa, "percorsi.py")):
    _casa = os.path.dirname(_casa)
if _casa not in sys.path:
    sys.path.insert(0, _casa)
import percorsi  # noqa: E402
import json

from icone import icone_mana  # palette, font, barra scura e simboli di mana: gli stessi della finestra grande
from tema import CI, COL_TIER, barra_scura, carica_font

C = CI   # nei colori di ArtStation, come l'interfaccia della finestra grande (17 ott 2026)
FILE = os.path.join(percorsi.ROOT, "Log_Arena", "mazzi_costruzione.json")
COL_TIER = COL_TIER  # S A B C D: gli stessi colori della scheda del mazzo inviato nella finestra grande


def leggi():
    with open(FILE, encoding="utf-8") as f:
        return json.load(f)


def num(x, d=2):
    return "?" if x is None else f"{x:.{d}f}"


def prova():
    d = leggi()
    print(d["ora"], "|", d["titolo"])
    for m in d["mazzi"]:
        print(f"\n[{m['tier']}] {m['n']}. {m['coppia']}{' + splash ' + m['splash'] if m['splash'] else ''}: "
              f"{num(m['vittorie'])} vittorie attese, meglio del {m['percentile']}% dei pool, trofei {m['trofei']}°")
        for c, carte in m["costi"]:
            print(f"   {c if c < 99 else '?'}: " + " · ".join((f"{q} " if q > 1 else "") + n for q, n in carte))
        print("   terre: " + " · ".join(f"{q} {n}" for q, n in m["terre"]))
        for a in m["mana"]:
            print("   mana:", a)
    n = sum(sum(q for q, _ in carte) for m in d["mazzi"][:1] for _, carte in m["costi"]) + sum(q for q, _ in d["mazzi"][0]["terre"])
    print("\ncarte del primo mazzo:", n)
    return 0 if n == 40 else 1


def avvia():
    import tkinter as tk
    import tkinter.font as tkfont
    carica_font()
    root = tk.Tk()
    root.title("Decks")
    root.configure(bg=C["fondo"])
    root.geometry("1180x960+80+30")
    barra_scura(root, C["testa"], C["titolo"], C["filo"])
    fam = "Poppins" if "Poppins" in tkfont.families() else "Segoe UI"
    famm = "Poppins Medium" if "Poppins Medium" in tkfont.families() else fam
    F = lambda n, m=False: (famm if m else fam, n)
    mana = {k: tk.PhotoImage(file=v) for k, v in icone_mana(16).items()}
    mana_g = {k: tk.PhotoImage(file=v) for k, v in icone_mana(22).items()}

    testa = tk.Frame(root, bg=C["testa"]); testa.pack(fill="x")
    v_testa = tk.StringVar()
    tk.Label(testa, textvariable=v_testa, bg=C["testa"], fg=C["testo"], font=F(10, True)).pack(side="left", padx=14, pady=8)
    v_ora = tk.StringVar()
    tk.Label(testa, textvariable=v_ora, bg=C["testa"], fg=C["acciaio"], font=F(9)).pack(side="right", padx=14)
    tk.Frame(root, bg=C["filo"], height=1).pack(fill="x")
    corpo = tk.Frame(root, bg=C["fondo"]); corpo.pack(fill="both", expand=True, padx=12, pady=12)
    for i in range(3):
        corpo.grid_columnconfigure(i, weight=1, uniform="col")
    corpo.grid_rowconfigure(0, weight=1)

    def riga_mana(padre, colori, imm, bg):
        f = tk.Frame(padre, bg=bg)
        for k in colori:
            if k in imm:
                tk.Label(f, image=imm[k], bg=bg).pack(side="left", padx=(0, 3))
            else:
                tk.Label(f, text=k, bg=bg, fg=C["testo"], font=F(10, True)).pack(side="left", padx=(0, 3))
        return f

    def colonna(m, i):
        primo = i == 0
        cornice = tk.Frame(corpo, bg=C["accento"] if primo else C["filo2"], padx=1, pady=1)
        cornice.grid(row=0, column=i, sticky="nsew", padx=6)
        dentro = tk.Frame(cornice, bg=C["scheda"]); dentro.pack(fill="both", expand=True)

        # in cima: i dati del mazzo
        cap = tk.Frame(dentro, bg=C["cap"]); cap.pack(fill="x")
        tk.Label(cap, text=str(m["tier"]), bg=C["cap"], fg=COL_TIER.get(m["tier"], C["muto"]),
                 font=F(34, True), width=2).pack(side="left", padx=(12, 6), pady=8)
        dati = tk.Frame(cap, bg=C["cap"]); dati.pack(side="left", fill="x", expand=True, pady=8)
        r1 = tk.Frame(dati, bg=C["cap"]); r1.pack(anchor="w")
        tk.Label(r1, text=f"{m['n']}.", bg=C["cap"], fg=C["muto"], font=F(11, True)).pack(side="left", padx=(0, 6))
        riga_mana(r1, m["coppia"], mana_g, C["cap"]).pack(side="left")
        if m["splash"]:
            tk.Label(r1, text="+", bg=C["cap"], fg=C["muto"], font=F(11, True)).pack(side="left", padx=4)
            riga_mana(r1, m["splash"], mana, C["cap"]).pack(side="left")
        tk.Label(dati, text=f"{num(m['vittorie'])} expected wins", bg=C["cap"], fg=C["titolo"],
                 font=F(14, True)).pack(anchor="w", pady=(4, 0))
        tk.Label(dati, text=f"better than {m['percentile']}% of pools · cards at trophy percentile {m['trofei']}",
                 bg=C["cap"], fg=C["grigio"], font=F(9)).pack(anchor="w")
        tk.Label(dati, text=f"S {num(m['S'], 1)}" + ("" if primo else f"  ({num(m['dal_primo'], 1)} from the first)"),
                 bg=C["cap"], fg=C["acciaio"], font=F(9)).pack(anchor="w")
        tk.Frame(dentro, bg=C["filo"], height=1).pack(fill="x")
        avvisi = tk.Frame(dentro, bg=C["scheda"]); avvisi.pack(fill="x", padx=12, pady=(6, 0))
        if m["splash"]:
            tk.Label(avvisi, text=f"splash {m['splash']}: {m['nsplash']} cards, {m['fonti_splash']} sources, "
                                  f"cost {num(m['prezzo'], 1)} points", bg=C["scheda"], fg=C["acciaio"],
                     font=F(9), wraplength=340, justify="left").pack(anchor="w")
        for a in m["mana"]:
            tk.Label(avvisi, text=f"⚠ mana {a}", bg=C["scheda"], fg=C["rosso_t"], font=F(9),
                     wraplength=340, justify="left").pack(anchor="w")

        # sotto: la lista per costo
        lista = tk.Frame(dentro, bg=C["scheda"]); lista.pack(fill="both", expand=True, padx=12, pady=(8, 6))
        for c, carte in m["costi"]:
            blocco = tk.Frame(lista, bg=C["scheda"]); blocco.pack(fill="x", pady=(0, 3))
            tk.Label(blocco, text=str(c) if c < 99 else "?", bg=C["evidenza"], fg=C["accento"], font=F(10, True),
                     width=3).pack(side="left", anchor="n", padx=(0, 8))
            nomi = tk.Frame(blocco, bg=C["scheda"]); nomi.pack(side="left", fill="x", expand=True)
            for q, n in carte:
                r = tk.Frame(nomi, bg=C["scheda"]); r.pack(anchor="w")
                tk.Label(r, text=f"{q}" if q > 1 else "", bg=C["scheda"], fg=C["accento"], font=F(10, True),
                         width=2, anchor="e").pack(side="left")
                tk.Label(r, text=n, bg=C["scheda"], fg=C["testo"], font=F(10), pady=0).pack(side="left", padx=(4, 0))
        tk.Frame(lista, bg=C["filo"], height=1).pack(fill="x", pady=(4, 6))
        terre = tk.Frame(lista, bg=C["scheda"]); terre.pack(fill="x")
        tk.Label(terre, text="lands", bg=C["scheda"], fg=C["muto"], font=F(9, True)).pack(side="left", padx=(0, 8))
        for q, n in m["terre"]:
            k = {v: k for k, v in {"W": "Plains", "U": "Island", "B": "Swamp", "R": "Mountain", "G": "Forest"}.items()}.get(n)
            if k in mana:
                tk.Label(terre, image=mana[k], bg=C["scheda"]).pack(side="left")
            tk.Label(terre, text=f"{q} {n}", bg=C["scheda"], fg=C["testo"], font=F(10)).pack(side="left", padx=(3, 10))
        n_tot = sum(q for _, cc in m["costi"] for q, _ in cc) + sum(q for q, _ in m["terre"])
        tk.Label(lista, text=f"{n_tot} cards", bg=C["scheda"], fg=C["muto"], font=F(8)).pack(anchor="e", pady=(6, 0))

    stato = {"mtime": None}

    def disegna():
        try:
            mt = os.path.getmtime(FILE)
            if mt != stato["mtime"]:
                stato["mtime"] = mt
                d = leggi()
                for w in corpo.winfo_children():
                    w.destroy()
                v_testa.set("COSTRUZIONE · i 3 mazzi migliori del pool")
                v_ora.set(d["ora"])
                for i, m in enumerate(d["mazzi"][:3]):
                    colonna(m, i)
        except FileNotFoundError:
            v_testa.set("COSTRUZIONE · nessun mazzo ancora")
        except Exception as e:
            v_testa.set(f"COSTRUZIONE · file dei mazzi illeggibile ({type(e).__name__})")
        root.after(2000, disegna)

    disegna()
    root.mainloop()


if __name__ == "__main__":
    if "--prova" in sys.argv:
        sys.exit(prova())
    avvia()
