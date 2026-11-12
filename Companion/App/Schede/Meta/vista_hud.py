"""La finestra Deck HUD: il mazzo dell'avversario mentre giochi (sessione Magic 15, 12 nov 2026; i conti in hud_mazzo, la partita in hud_partita).

Una finestra sola, sopra il Companion ma non sopra Arena (niente topmost: Autore, 17 ott 2026, «il fatto che il companion resti sempre in sovraimpressione
e' sbagliato»), disegnata su una tela sola (Note/Motore_Grafico_App.md). La apre il pulsante «Deck HUD» nella barra delle schede, che durante una partita
prende il pallino («Deck HUD ●»). Non si apre da sola: una finestra nuova di Tk prende il fuoco, e in partita lo toglierebbe ad Arena; si apre una volta e
resta sul secondo schermo. Si rilegge ogni 1,5 s, solo i byte nuovi del Player.log. Niente si scrive su disco.

    py -I -X utf8 Companion/App/Schede/Meta/vista_hud.py                   la finestra sulla partita del Player.log
    py -I -X utf8 Companion/App/Schede/Meta/vista_hud.py --prova           fuori schermo, su log finti, con le negative
"""
import os, sys
_casa = os.path.dirname(os.path.abspath(__file__))      # si sale fino a percorsi.py, che mette nel sys.path tutte le cartelle del Companion
while not os.path.isfile(os.path.join(_casa, "percorsi.py")):
    _casa = os.path.dirname(_casa)
if _casa not in sys.path:
    sys.path.insert(0, _casa)
import percorsi  # noqa: E402,F401
import threading  # noqa: E402
import hud_mazzo as HM  # noqa: E402
import hud_partita as HP  # noqa: E402
import matchup_log as ML  # noqa: E402
from tema import CI  # noqa: E402

LARGO, ALTO = 420, 700
OGNI = 1500         # ms fra una lettura e l'altra del Player.log
PIEDE = "Decks only, never players: nothing about the opponent is saved."
_SEGUITO = {}       # file -> Seguito: uno per la finestra grande (il pulsante, la sorveglianza e l'HUD leggono lo stesso)


def seguito(file=None, io=None):
    k = (file or "Player.log", io)
    if k not in _SEGUITO:
        _SEGUITO[k] = HP.Seguito(file, io)
    return _SEGUITO[k]


class FinestraHud:
    """La finestra dell'HUD. APERTA: quella aperta (una sola)."""
    APERTA = None

    def __init__(self, tk, padre, F, file=None, recs=None, fuori=False, ogni=OGNI, io=None, meta=None):
        if FinestraHud.APERTA is not None:
            try:
                FinestraHud.APERTA.f.deiconify(); FinestraHud.APERTA.f.lift()
                return
            except Exception:       # noqa: BLE001 - la finestra di prima e' stata distrutta: se ne fa una nuova
                FinestraHud.APERTA = None
        FinestraHud.APERTA = self
        self.tk, self.F, self.ogni = tk, F, ogni
        self.seg = seguito(file, io)
        self.recs = recs
        self.meta = meta        # le prove: un meta finto al posto del file della pagina Meta
        self.h = None
        self.firma = None
        self.vivo = True
        root = padre.winfo_toplevel()
        f = self.f = tk.Toplevel(root)
        f.title("Deck HUD")
        f.configure(bg=CI["fondo"])
        f.transient(root)
        if fuori:
            f.geometry(f"{LARGO}x{ALTO}+-3000+0")
        else:
            x = root.winfo_rootx() + max(0, root.winfo_width() - LARGO - 300)
            f.geometry(f"{LARGO}x{ALTO}+{x}+{root.winfo_rooty() + 60}")
        f.minsize(340, 300)
        self.c = tk.Canvas(f, bg=CI["scheda"], highlightthickness=0, bd=0)
        self.c.pack(fill="both", expand=True)
        self.c.bind("<Configure>", lambda e: self.disegna())
        self.c.bind("<MouseWheel>", lambda e: self.c.yview_scroll(-1 if e.delta > 0 else 1, "units"))
        f.bind("<Escape>", lambda e: self.chiudi())
        f.protocol("WM_DELETE_WINDOW", self.chiudi)
        self.disegna()
        if self.recs is None:       # le tue partite (banca dati): una volta, in un filo
            threading.Thread(target=self._carica, daemon=True).start()
        f.after(50, self.giro)

    def _carica(self):
        try:
            self.recs = ML.records()
        except Exception:       # noqa: BLE001 - senza le tue partite l'HUD dice solo il mazzo
            self.recs = []
        self.firma = None

    def chiudi(self):
        self.vivo = False
        FinestraHud.APERTA = None
        try:
            self.f.destroy()
        except Exception:       # noqa: BLE001
            pass

    def giro(self):
        if not self.vivo:
            return
        self.aggiorna()
        self.f.after(self.ogni, self.giro)

    def aggiorna(self):
        """Rilegge la partita; ridisegna solo se e' cambiato qualcosa che l'HUD mostra."""
        st = self.seg.aggiorna()
        firma = None if st is None else (st["matchId"], tuple(st["sue"]), st["aperte"], st["turno"], st["finita"], st.get("sul_play"), self.recs is None)
        if firma == self.firma:
            return False
        self.firma = firma
        self.h = HM.scheda(st, recs=self.recs or [], meta=self.meta) if st else None
        self.disegna()
        return True

    # ------------------------------------------------------------------------------------------------- il disegno
    def disegna(self):
        c = self.c
        c.delete("all")
        W = max(300, c.winfo_width() if c.winfo_width() > 1 else LARGO)
        x0, x1 = 16, W - 16
        y = [14]
        F = self.F

        def testo(t, x=x0, f=None, col=None, ancora="nw", tag=None):
            return c.create_text(x, y[0], text=t, anchor=ancora, font=f or F(9), fill=col or CI["testo"], tags=tag or "riga")

        def titolo(t):
            y[0] += 10
            testo(t.upper(), f=F(8, True), col=CI["titolo"], tag="titolo")
            y[0] += 18
            c.create_line(x0, y[0], x1, y[0], fill=CI["filo"])
            y[0] += 6

        def barra(p, col=CI["azzurro"]):
            c.create_rectangle(x0, y[0], x1, y[0] + 3, fill=CI["filo"], width=0)
            if p:
                c.create_rectangle(x0, y[0], x0 + (x1 - x0) * min(1, p), y[0] + 3, fill=col, width=0)
            y[0] += 8

        def riga(sx, dx="", col_dx=None, col_sx=None, f=None, alto=19):
            testo(sx, col=col_sx, f=f)
            if dx:
                testo(dx, x=x1, col=col_dx or CI["titolo"], ancora="ne", f=f)
            y[0] += alto

        h = self.h
        testo("OPPONENT DECK", f=F(11, True), col=CI["titolo"], tag="testa")
        if h and h.get("tipo") != "spento":
            pp = "on the play" if h.get("sul_play") else "on the draw" if h.get("sul_play") is False else ""
            testo(" · ".join(x for x in (f"T{h['turno']}" if h.get("turno") else "", pp, f"{h.get('aperte', 0)} open") if x), x=x1, ancora="ne", col=CI["grigio"])
        y[0] += 26
        if h is None:
            riga("No game in the Arena log yet.", col_sx=CI["grigio"])
        elif h.get("tipo") == "spento":
            riga(h.get("motivo") or "", col_sx=CI["grigio"])
        else:
            if h.get("finita"):
                riga("Last game (finished).", col_sx=CI["muto"])
            riga(f"from {h.get('magie_viste', 0)} spell{'s' if h.get('magie_viste') != 1 else ''} seen", col_sx=CI["muto"], f=F(7), alto=15)
            self._corpo(h, testo, titolo, barra, riga, F, x0, x1, y)
        y[0] += 12
        c.create_text(x0, y[0], text=PIEDE, anchor="nw", font=F(7), fill=CI["muto"], width=x1 - x0, tags="piede")
        y[0] += 30
        c.configure(scrollregion=(0, 0, W, y[0]))

    def _corpo(self, h, testo, titolo, barra, riga, F, x0, x1, y):
        if h["tipo"] == "limited":
            cc = h.get("coppie") or []
            if not cc:
                riga("No spell seen yet: colors unknown.", col_sx=CI["grigio"])
            for i, (_k, nome, p) in enumerate(cc):
                riga(nome, f"{round(100 * p)}%", f=F(14, True) if i == 0 else F(9), col_sx=CI["titolo"] if i == 0 else CI["grigio"],
                     col_dx=CI["azzurro"] if i == 0 else CI["grigio"], alto=26 if i == 0 else 18)
                if i == 0:
                    barra(p)
            x = h.get("l17")
            if x:
                titolo(f"17Lands · {h.get('set')} Premier")
                riga(f"{x['coppia']} wins", f"{x['wr']}%")
                riga("On the play / on the draw", f"{x['play']}% / {x['draw']}%")
                if x.get("chiude"):
                    riga("Its wins end on turn", f"{x['chiude']:.1f}")
                if x.get("tu_contro"):
                    t = x["tu_contro"]
                    riga(f"{t['coppia']} vs {x['coppia']}", f"{t['wr']}%", col_dx=CI["azzurro"] if t["wr"] >= 50 else CI["rosso"])
                c = self.c
                c.create_text(x0, y[0], text=f"{x['partite']:,} games · {h.get('fonte')}", anchor="nw", font=F(7), fill=CI["muto"], tags="fonte")
                y[0] += 16
        else:
            aa = h.get("archetipi") or []
            for i, (nome, p) in enumerate(aa):
                dx = "" if p is None else f"{round(100 * p)}%"
                riga(nome, dx, f=F(14, True) if i == 0 else F(9), col_sx=CI["titolo"] if i == 0 else CI["grigio"],
                     col_dx=CI["azzurro"] if i == 0 else CI["grigio"], alto=26 if i == 0 else 18)
                if i == 0 and p is not None:
                    barra(p)
            if h.get("probabili"):
                titolo("Likely in its 60")
                for n, p, q in h["probabili"]:
                    riga(f"{n}  ·  {q}x" if q else n, f"{round(100 * p)}%", col_dx=CI["azzurro"] if p >= 0.6 else CI["testo"])
            cv = h.get("curva")
            if cv:
                titolo("Its turns 2 · 3 · 4")
                for k in (2, 3, 4):
                    voci = cv.get(k) or []
                    riga(f"T{k}  " + (", ".join(n + (f" {round(100 * q)}%" if q is not None else "") for n, q in voci) or "-"))
                fonte = f"in your {cv['partite']} games against it" if cv["fonte"] == "partite" else "from the meta list (cheapest spells by copies)"
                riga(fonte, col_sx=CI["muto"], f=F(7), alto=15)
        ist = h.get("istantanee")
        titolo(f"With {h.get('aperte', 0)} open, it can have")
        if not ist:
            riga("nothing instant-speed it is likely to hold", col_sx=CI["grigio"])
        for x in ist or []:
            if h["tipo"] == "limited":
                riga(f"{x[0]}  ({x[1]})", f"GIH {x[2]}%" if x[2] else "", col_sx=CI["arancio"], col_dx=CI["grigio"])
            else:
                riga(f"{x[0]}  ({x[1]})", "seen" if x[3] else f"{round(100 * x[2])}%", col_sx=CI["arancio"])
        k = h.get("contro") or {}
        titolo("You vs it")
        t = k.get("tutti")
        if not t:
            riga("no games of yours against it yet", col_sx=CI["grigio"])
        else:
            def conti(etichetta, t):
                pl, dr = t["play"], t["draw"]
                col = CI["muto"] if t["poche"] else (CI["azzurro"] if (t["wr"] or 0) >= 50 else CI["rosso"])
                riga(f"{etichetta}  {t['vinte']}-{t['perse']}", f"{t['wr']}%", col_dx=col)
                riga(f"   play {pl[1]}-{pl[0] - pl[1]} · draw {dr[1]}-{dr[0] - dr[1]}" + ("  (few games)" if t["poche"] else ""), col_sx=CI["grigio"], alto=17)
            conti("All your decks", t)
            if k.get("mazzo"):
                conti("This deck", k["mazzo"])
            if k.get("chiude"):
                riga(f"It beat you on its turn {k['chiude']:.1f} on average ({k['perse']} losses)", col_sx=CI["grigio"], alto=17)

    def testi(self):
        """I testi disegnati (per le prove)."""
        return [self.c.itemcget(i, "text") for i in self.c.find_all() if self.c.type(i) == "text"]


def apri(tk, padre, F, **kw):
    FinestraHud(tk, padre, F, **kw)
    return FinestraHud.APERTA


def pulsante(fin, tk, file=None, io=None):
    """Il pulsante «Deck HUD» nella barra delle schede della finestra grande: apre l'HUD; durante una partita ha il pallino e l'azzurro."""
    lab = tk.Label(fin.barra_schede, text="Deck HUD", bg=CI["fondo"], fg=CI["grigio"], font=fin.F(9, True), padx=12, pady=5, cursor="hand2")
    lab.pack(side="right", padx=(0, 6))
    stato = {"vivo": False}
    lab.bind("<Button-1>", lambda e: apri(tk, fin.root, fin.F, file=file, io=io))
    lab.bind("<Enter>", lambda e: lab.configure(fg=CI["titolo"]))
    lab.bind("<Leave>", lambda e: lab.configure(fg=CI["azzurro"] if stato["vivo"] else CI["grigio"]))
    seg = seguito(file, io)

    def guarda(ancora=True):
        try:
            st = seg.aggiorna() if FinestraHud.APERTA is None else seg.stato()
            vivo = bool(st and not st["finita"] and st["turno"] and not st["competitivo"] and ML.formato(st["evento"]))
            if vivo != stato["vivo"]:
                stato["vivo"] = vivo
                lab.configure(text="Deck HUD  ●" if vivo else "Deck HUD", fg=CI["azzurro"] if vivo else CI["grigio"])
        except Exception as e:      # noqa: BLE001 - la sorveglianza non ferma la finestra
            print("deck hud:", f"{type(e).__name__}: {e}")
        if ancora:
            fin.root.after(3000, guarda)
    lab.guarda = guarda
    threading.Thread(target=seg.aggiorna, daemon=True).start()     # la prima lettura (il log intero) in un filo: poi si leggono solo i byte nuovi
    fin.root.after(5000, guarda)
    return lab


# --------------------------------------------------------------------------------------------------------------- le prove
def prova():
    import tempfile
    import tkinter as tk
    from tema import carica_font
    carica_font()
    root = tk.Tk()
    root.geometry("200x200+-3000+0")
    F = lambda n, b=False: ("Poppins Medium" if b else "Poppins", n)     # noqa: E731
    casi = []
    ME = "AAAAAAAAAAAAAAAAAAAAAAAAAA"
    HP.nome_grp(0)
    nomi = {n.lower(): g for g, n in HP._NOMI.items()}
    g = lambda n: nomi[n.lower()]       # noqa: E731
    posti = ('[{"userId": "%s", "playerName": "Io", "systemSeatId": 1, "teamId": 1, "eventId": "%%s"}, {"userId": "OPPID", "playerName": "NomeAvversario", '
             '"systemSeatId": 2, "teamId": 2, "eventId": "%%s"}]') % ME

    def stanza(mid, ev, tipo):
        return ('{"timestamp": "1", "matchGameRoomStateChangedEvent": {"gameRoomInfo": {"gameRoomConfig": {"reservedPlayers": %s, "matchId": "%s"}, '
                '"stateType": "MatchGameRoomStateType_%s"}}}\n') % (posti % (ev, ev), mid, tipo)

    def gs(oggetti, turno, attivo):
        ids = ", ".join(str(i) for i, _g, _t in oggetti)
        ogg = ", ".join('{ "instanceId": %d, "grpId": %d, "type": "GameObjectType_Card", "zoneId": 10, "ownerSeatId": 2, "controllerSeatId": 2%s }'
                        % (i, gr, ', "cardTypes": ["CardType_Land"]' if t else "") for i, gr, t in oggetti)
        return ('{ "transactionId": "g", "greToClientEvent": { "greToClientMessages": [ { "type": "GREMessageType_GameStateMessage", "gameStateMessage": '
                '{ "zones": [ { "zoneId": 10, "type": "ZoneType_Battlefield", "ownerSeatId": 2, "objectInstanceIds": [ %s ] } ], "gameObjects": [ %s ], '
                '"turnInfo": {"turnNumber": %d, "activePlayer": %d} } } ] } }\n') % (ids, ogg, turno, attivo)
    d = tempfile.mkdtemp()
    # il costruito: Mono-White Auras da un meta finto, due sue carte e due Plains aperte
    f1 = os.path.join(d, "c.log")
    open(f1, "w", encoding="utf-8").write(stanza("m1", "Ladder", "Playing") + gs([(5, g("Plains"), True), (6, g("Plains"), True), (7, g("Ethereal Armor"), False),
                                                                                    (8, g("Sheltered by Ghosts"), False)], 3, 2))
    io = (ME, None)     # il tuo account nel log finto
    meta = [dict(nome="Mono-White Auras", colori="W", quota=10, lista={"Ethereal Armor": 4, "Sheltered by Ghosts": 4, "Seam Rip": 2, "Plains": 20}),
            dict(nome="Izzet Prowess", colori="UR", quota=8, lista={"Opt": 4, "Lightning Strike": 4, "Spell Pierce": 2, "Island": 8})]
    kw = dict(recs=[], fuori=True, ogni=10 ** 6, io=io, meta=meta)
    w = FinestraHud(tk, root, F, file=f1, **kw)
    root.update()
    w.aggiorna(); root.update()
    tt = w.testi()
    casi.append(("costruito: Mono-White Auras in testa con la confidenza", "Mono-White Auras" in tt and w.h["archetipi"][0][0] == "Mono-White Auras"
                 and w.h["archetipi"][0][1] > 0.8))
    casi.append(("le sezioni: probabili, T2-T4, istantanee col mana aperto, tu contro", all(any(s.lower() in x.lower() for x in tt) for s in
                                                                                        ("LIKELY IN ITS 60", "ITS TURNS 2", "WITH 2 OPEN", "YOU VS IT"))))
    casi.append(("negativa: il nome e l'id dell'avversario non sono disegnati", not any("NomeAvversario" in x or "OPPID" in x for x in tt)))
    casi.append(("niente di nuovo nel log: non si ridisegna", w.aggiorna() is False))
    with open(f1, "a", encoding="utf-8") as fh:
        fh.write(gs([(9, g("Lightning Strike"), False)], 4, 1))
    rifatto = w.aggiorna()
    casi.append(("una carta nuova fuori colore: si ridisegna e Mono-White Auras scende sotto Other", rifatto is True and w.h["archetipi"][0][0].startswith("Other ·")
                 and dict(w.h["archetipi"]).get("Mono-White Auras", 0) < 0.3))
    w.chiudi()
    # una seconda finestra mentre c'e' la prima: una sola
    w2 = FinestraHud(tk, root, F, file=f1, **kw)
    FinestraHud(tk, root, F, file=f1, **kw)
    casi.append(("una finestra sola alla volta", FinestraHud.APERTA is w2 and sum(1 for x in root.winfo_children() if isinstance(x, tk.Toplevel)) == 1))
    w2.chiudi()
    # l'evento competitivo: l'HUD tace
    f2 = os.path.join(d, "q.log")
    open(f2, "w", encoding="utf-8").write(stanza("m2", "Arena_Championship_Qualifier_X", "Playing") + gs([(7, g("Ethereal Armor"), False)], 3, 2))
    w3 = FinestraHud(tk, root, F, file=f2, **kw)
    w3.aggiorna(); root.update()
    tt3 = w3.testi()
    casi.append(("negativa: evento competitivo, nessun archetipo ne' carta", any("Competitive" in x for x in tt3) and not any("Auras" in x for x in tt3)))
    w3.chiudi()
    # il limited: un Quick Draft di FRA, due carte verdi e bianche
    f3 = os.path.join(d, "l.log")
    import dati_grafici
    storia = dati_grafici.storia_17lands("FRA")
    verdi = [n for n, i in HM.carte().items() if "FRA" in i["set"] and i["colori"] in ("G", "W") and not i["terra"]][:4]
    open(f3, "w", encoding="utf-8").write(stanza("m3", "QuickDraft_FRA_20261008", "Playing")
                                          + gs([(i + 20, g(n), False) for i, n in enumerate(verdi)] + [(30, g("Forest"), True), (31, g("Plains"), True)], 5, 2))
    w4 = FinestraHud(tk, root, F, file=f3, **kw)
    w4.aggiorna(); root.update()
    tt4 = w4.testi()
    if storia:
        casi.append(("limited: la coppia dai colori visti e i numeri di 17Lands con la fonte", w4.h["tipo"] == "limited" and w4.h["coppie"]
                     and set(w4.h["coppie"][0][0]) >= set(w4.h["colori"]) and any("17Lands" in x for x in tt4) and any("CC BY" in x for x in tt4)))
    else:
        casi.append(("limited senza la storia di 17Lands: la coppia non si dice", w4.h["tipo"] == "limited"))
    w4.chiudi()
    root.destroy()
    scritti = [x for x in os.listdir(d) if not x.endswith(".log")]
    casi.append(("negativa: l'HUD non scrive file", scritti == []))
    # il pulsante nella barra delle schede: il pallino durante una partita, via a partita finita
    root2 = tk.Tk(); root2.geometry("300x60+-3000+0")
    fin = type("Fin", (), {})()
    fin.root, fin.F, fin.barra_schede = root2, F, tk.Frame(root2)
    f4 = os.path.join(d, "p.log")
    open(f4, "w", encoding="utf-8").write(stanza("m4", "Ladder", "Playing") + gs([(7, g("Ethereal Armor"), False)], 2, 2))
    lab = pulsante(fin, tk, file=f4, io=io)
    lab.guarda(False)
    acceso = lab.cget("text")
    with open(f4, "a", encoding="utf-8") as fh:
        fh.write(stanza("m4", "Ladder", "MatchCompleted"))
    lab.guarda(False)
    casi.append(("il pulsante: «Deck HUD ●» in partita, senza il pallino a partita finita", acceso.endswith("●") and lab.cget("text") == "Deck HUD"))
    root2.destroy()
    _SEGUITO.clear()
    for n_, ok in casi:
        print(("ok    " if ok else "ROSSO ") + n_)
    print(f"{sum(ok for _n, ok in casi)}/{len(casi)}")
    return all(ok for _n, ok in casi)


if __name__ == "__main__":
    if "--prova" in sys.argv:
        sys.exit(0 if prova() else 1)
    import tkinter as tk
    from tema import carica_font
    carica_font()
    r = tk.Tk()
    r.withdraw()
    w = FinestraHud(tk, r, lambda n, b=False: ("Poppins Medium" if b else "Poppins", n))
    w.f.protocol("WM_DELETE_WINDOW", lambda: (w.chiudi(), r.destroy()))
    r.mainloop()
