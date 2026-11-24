"""Le partite del motore di partita nel replayer (24 nov 2026; Autore: «ma è possibile vedere come il motore di magic che abbiamo costruito gioca nel
replayer?», poi «ok dai proviamo»).

Il motore (Motore_Partita/simula.py, effetti.Partita, l'arbitro acceso) gioca una partita fra due mazzi veri di FRA (simula.mazzi_veri, i draft di Autore) coi
suoi giocatori finti (Semplice, il Cercatore); qui a ogni evento del tavolo (una magia, un cambio di zona, le vite, un attacco, un blocco, un danno) si fa una foto
del tavolo nel formato del replayer (dati_analizzatore.azioni_partita: nome del passo, foto, turno, relazioni, racconto, danni) e, sotto, nel formato di
mana_aperto (_grezza), cosi' la WIN CHANCE e il voto delle fasi leggono anche le partite simulate. L'Hero e' il giocatore 0. Il replayer le apre come le partite
vere (DA.azioni_partita e DA.foto_partita guardano il campo «simulata» della riga); niente di questo scrive nei log.

Una simulazione resta una simulazione: i giocatori finti non sono avversari veri, e il replayer lo dice.

    py -I -X utf8 Companion/App/Schede/Performance/partite_motore.py --prova
    py -I -X utf8 Companion/App/Schede/Performance/partite_motore.py A B SEME     (stampa i passi di una partita fra i mazzi A e B)
"""
import os, sys
_casa = os.path.dirname(os.path.abspath(__file__))      # si sale fino a percorsi.py, che mette nel sys.path tutte le cartelle del Companion
while not os.path.isfile(os.path.join(_casa, "percorsi.py")):
    _casa = os.path.dirname(_casa)
if _casa not in sys.path:
    sys.path.insert(0, _casa)
import percorsi  # noqa: E402
import datetime  # noqa: E402

_MP = os.path.join(percorsi.ROOT, "Motore_Partita")
_REG = {}       # id della partita simulata -> dict(passi, mazzi, vincitore, seme)

PASSI = {"stap": "Untap", "mantenimento": "Upkeep", "pescata": "Draw", "inizio_combattimento": "BeginCombat", "dichiara_attaccanti": "DeclareAttack",
         "dichiara_bloccanti": "DeclareBlock", "danno": "CombatDamage", "danno_primo": "FirstStrikeDamage", "fine_combattimento": "EndCombat",
         "fine": "End", "pulizia": "Cleanup"}
FASI = {"principale_1": "Main1", "principale_2": "Main2", "inizio": "Beginning", "combattimento": "Combat", "finale": "Ending"}
VUOTA = dict(mostrate=[], emblemi=([], []), opzioni={}, cima=(None, None), riv=[], mes=[], segni={}, scry=[], mn=[], mnd=None, pc=[], pd={}, pz={},
             mp=([], []), vel=(None, None), pt=[], pf=[], hv=[], info={}, gioc=[])


def _motore():
    if _MP not in sys.path:
        sys.path.insert(0, _MP)
    import simula as S
    import effetti as E
    return S, E


_PEDINE = {}


def _grp(nome, pedina=False):
    """Il grpId di Arena per nome; per una pedina quello della pedina col nome (24 nov 2026: la pedina Jace del motore restava un cerchio vuoto, perche'
    _grp_di_nome salta le pedine; nelle partite vere Arena le da' il suo, 106555)."""
    import dati_analizzatore as DA
    if pedina:
        if not _PEDINE:
            try:
                import db_carte
                tt = db_carte.testi()
                for c in db_carte.carte():
                    if c.get("isToken") and "titleId" in c and tt.get(c["titleId"]):
                        _PEDINE.setdefault(tt[c["titleId"]], c["grpid"])
            except Exception:       # noqa: BLE001
                _PEDINE[""] = None
        if _PEDINE.get(nome):
            return _PEDINE[nome]
    try:
        return DA._grp_di_nome(nome)
    except Exception:       # noqa: BLE001
        return None


def _fp(t, o):
    """(forza, costituzione) di una creatura in campo, o (None, None)."""
    try:
        if "creature" in o.carta.tipi:
            return t.forza_di(o), t.costituzione_di(o)
    except Exception:       # noqa: BLE001 - una carta senza i numeri resta senza
        pass
    return None, None


def foto(t, p, hero=0):
    """La foto del tavolo dal posto dell'Hero: il formato del replayer, con _grezza nel formato di mana_aperto."""
    a, b = hero, 1 - hero
    g = t.giocatori
    campo = {0: [], 1: []}
    grezzo_c = {0: [], 1: []}
    for o in t.campo:
        c = t.controllore_di(o)
        fz, ct = _fp(t, o)
        gr = _grp(o.nome, o.carta.pedina)
        campo[c].append((o.nome, bool(o.tappato), bool(o.carta.pedina), fz, ct, o.n, gr, None))
        grezzo_c[c].append([gr or 0, int(bool(o.tappato)), int(bool(o.carta.pedina)), fz, ct, o.n, None])
    pila = []
    for o in t.pila:
        if getattr(o, "fonte", None) is not None:        # un'abilita': il nome della carta che la fa
            pila.append((o.fonte.nome, o.controllore == hero, True, _grp(o.fonte.nome), o.n))
        else:
            pila.append((o.nome, t.controllore_di(o) == hero, False, _grp(o.nome), o.n))
    esi = {0: [], 1: []}
    for o in t.esilio:
        esi[o.proprietario].append(o.nome)
    f = dict(VUOTA, mio=campo[a], suo=campo[b], mano=[o.nome for o in g[a].mano], n_suo=len(g[b].mano), vite=(g[a].vite, g[b].vite),
             cim=([o.nome for o in g[a].cimitero], [o.nome for o in g[b].cimitero]), esi=(esi[a], esi[b]),
             pila=pila, emblemi=([], []), info={"simulata": True}, grimori=(len(g[a].grimorio.carte), len(g[b].grimorio.carte)))
    f["_grezza"] = dict(c=[grezzo_c[0], grezzo_c[1]], m=[[_grp(o.nome) or 0 for o in g[0].mano], []], n=[len(g[0].mano), len(g[1].mano)],
                        v=[g[0].vite, g[1].vite], g=[[_grp(o.nome) or 0 for o in g[i].cimitero] for i in (0, 1)],
                        e=[[_grp(n) or 0 for n in esi[i]] for i in (0, 1)])
    f["_att"] = (getattr(p, "attivo", 0) or 0) + 1 if p is not None else 1
    return f


def _chi(i, hero=0):
    return "You" if i == hero else "Opponent"


def racconto(e, hero=0):
    """Una riga del racconto per un evento del tavolo, o None."""
    nome = e.carta.nome if e.carta is not None else ""
    i = e.giocatore
    mio = i == hero
    if e.tipo == "lanciata":
        return mio, f"{_chi(i, hero)} cast {nome}"
    if e.tipo == "attivata":
        return mio, f"{_chi(i, hero)} activated {nome}"
    if e.tipo == "attacca":
        return mio, f"{_chi(i, hero)} attacked with {nome}"
    if e.tipo == "blocca":
        return mio, f"{_chi(i, hero)} blocked with {nome}"
    if e.tipo == "vite" and e.quanto:
        return mio, f"{_chi(i, hero)} {'lost' if e.quanto < 0 else 'gained'} {abs(e.quanto)} life"
    if e.tipo == "danno":
        return mio, f"{nome} dealt {e.quanto} to {'you' if e.a == f'G{hero + 1}' else 'the opponent' if str(e.a).startswith('G') else str(e.a).split('#')[0]}"
    if e.tipo in ("perde", "vince"):
        return mio, f"{_chi(i, hero)} {'lost' if e.tipo == 'perde' else 'won'} the game"
    if e.tipo == "zona" and e.carta is not None:
        chi = e.carta.proprietario if i is None else i
        mio = chi == hero
        if e.da == "grimorio" and e.a == "mano":
            return mio, f"You drew {nome}" if mio else "Opponent drew a card"
        if e.da == "mano" and e.a == "campo" and "land" in e.carta.tipi:
            return mio, f"{_chi(chi, hero)} played {nome}"
        if e.da == "pila" and e.a == "campo":
            return mio, f"{nome} resolved"
        if e.da == "campo" and e.a == "cimitero":
            return mio, f"{nome} died" if "creature" in e.carta.tipi else f"{nome} went to the graveyard"
        if e.a == "esilio":
            return mio, f"{nome} was exiled"
        if e.da == "campo" and e.a == "mano":
            return mio, f"{nome} returned to hand"
        if e.da is None and e.a == "campo":
            return mio, f"{_chi(chi, hero)} created {nome}"
        if e.a == "cimitero" and e.da == "pila":
            return mio, f"{nome} resolved"
    return None


def gioca(a, b, seme, hero=0, giocatori=None):
    """Una partita del motore fra i mazzi veri a e b (indici di simula.mazzi_veri), con una foto a ogni evento. -> (passi, partita del motore, mazzi)."""
    S, E = _motore()
    mazzi = S.mazzi_veri()
    reg, tieni = [], {}

    class T(E.TavoloEffetti):
        def _dopo_evento(self, e):
            super()._dopo_evento(e)
            p_ = tieni.get("p")
            if p_ is None or e.tipo in ("tappa", "stappa", "resta"):
                return
            bers = []
            if e.tipo in ("lanciata", "attivata") and self.pila:       # i bersagli della magia o dell'abilita' appena messa in pila (24 nov 2026)
                cima = next((o for o in reversed(self.pila) if getattr(o, "n", None) == e.vecchio), self.pila[-1])
                for gruppo in getattr(cima, "bersagli", None) or []:
                    for b_ in (gruppo if isinstance(gruppo, (list, tuple)) else [gruppo]):
                        if isinstance(b_, int):
                            bers.append("vita_mio" if b_ == hero else "vita_suo")
                        elif hasattr(b_, "zona") and hasattr(b_, "n"):
                            bers.append(b_.n)
                        elif hasattr(b_, "vite") and hasattr(b_, "i"):
                            bers.append("vita_mio" if b_.i == hero else "vita_suo")
            reg.append((e, foto(self, p_, hero), p_.attivo, p_.fase, p_.passo, self.turno_numero, bers,
                        {o.n: tg for o, tg in (getattr(p_, "attaccanti", None) or {}).items()},
                        {o.n: [x.n for x in v] for o, v in (getattr(p_, "bloccanti", None) or {}).items()}))

    class P(E.Partita):
        def __init__(self, t, *aa, **kk):
            super().__init__(t, *aa, **kk)
            tieni["p"] = self
    g0, g1 = giocatori or (S.Semplice(seme), S.Semplice(seme + 100))
    p = S.partita(mazzi[a], mazzi[b], seme, g0, g1, ferma=False, P=P, T=T)
    return passi_da(reg, hero), p, (mazzi[a], mazzi[b])


def passi_da(reg, hero=0):
    """Le foto registrate -> i passi del replayer: (nome, foto, turno, relazioni, racconto, danni, danni con la fonte)."""
    out, turni, ultimo_t = [], {0: 0, 1: 0}, None
    for e, f, att, fase, passo, tn, bers, attacc, blocc in reg:
        if tn != ultimo_t:
            ultimo_t = tn
            if att is not None:
                turni[att] += 1
        if e.tipo in ("passo",):
            continue
        r = racconto(e, hero)
        if e.tipo == "turno":
            r = (att == hero, f"{'Your' if att == hero else 'Opponent' + chr(39) + 's'} turn {turni.get(att, 0)}")
        if r is None:
            continue
        pesca = e.tipo == "zona" and e.da == "grimorio" and e.a == "mano"
        dove = PASSI.get(passo) or FASI.get(fase) or ("Draw" if pesca else "Beginning")     # il motore cambia passo dopo l'evento del turno
        nome = f"{_chi(att if att is not None else 0, hero)} T{max(1, turni.get(att, 1))} · {dove}"
        rel = None
        if e.tipo in ("lanciata", "attivata") and e.carta is not None:
            rel = dict(tipo="spell", nome=e.carta.nome, g=_grp(e.carta.nome), mio=e.giocatore == hero, ab=e.tipo == "attivata", bers=list(bers),
                       colpiti=[], fuori={}, da=[])
        elif attacc and e.tipo in ("attacca", "blocca", "danno"):
            lato = lambda tg: ("vita_mio" if tg == hero else "vita_suo") if tg in (0, 1) else getattr(tg, "n", tg)
            rel = dict(tipo="comb", att=[(i_, lato(tg)) for i_, tg in attacc.items()],
                       blocchi=[(b_, list(a_)) for b_, a_ in blocc.items()])
        danni, danni3 = [], []
        if e.tipo == "danno" and e.quanto:
            bers = ("vita_mio" if e.a == f"G{hero + 1}" else "vita_suo") if str(e.a).startswith("G") else e.nuovo
            danni, danni3 = [(bers, e.quanto)], [(bers, e.quanto, e.vecchio)]
        out.append((nome, f, tn, rel, [r], danni, danni3))
    if out:
        f0 = dict(out[0][1])
        out.insert(0, (out[0][0].split(" · ")[0] + " · Game start", f0, out[0][2], None, [(True, "The game begins")], [], []))
    return out


def registra(a, b, seme, hero=0):
    """Gioca una partita, la tiene in memoria e da' la riga dell'analizzatore che il replayer apre (campo «simulata»)."""
    passi, p, (ma, mb) = gioca(a, b, seme, hero)
    pid = f"sim-{a}-{b}-{seme}"
    vinta = p.t.vincitore == hero
    _REG[pid] = dict(passi=passi, mazzi=(ma, mb), vincitore=p.t.vincitore, seme=seme, errori=list(getattr(p, "err", []) or []))
    deck = {}
    for n in ma["mazzo"]:
        n = n if isinstance(n, str) else n[0]
        deck[n] = deck.get(n, 0) + 1
    return dict(partita=pid, seat=hero + 1, simulata=True, tipo="Limited", formato="Simulation", evento="Engine simulation", quando=datetime.datetime.now(),
                mio=f"{ma.get('nome', '?')} (engine)", suo=f"{mb.get('nome', '?')} (engine)", deck=deck, vinta=vinta, inizia=p.t.primo == hero,
                mulligan=0, turni=p.t.turno_numero, per_turno={})


def azioni(x):
    return (_REG.get(x.get("partita")) or {}).get("passi")


def foto_partita(x):
    """Quello che il replayer chiede per aprire una partita: la prima foto come mano tenuta; i passi vengono da azioni()."""
    ps = azioni(x)
    if not ps:
        return None
    return dict(mano0=ps[0][1], turni=[], ultima=None)


def prova():
    import partite_motore as M      # il modulo come lo importa l'app (lanciato come programma questo e' __main__, con un altro elenco)
    casi = []
    x = M.registra(0, 1, 7)
    ps = M.azioni(x)
    casi.append(("la partita si gioca e da' dei passi", bool(ps) and len(ps) > 20))
    casi.append(("ogni passo ha la forma del replayer (7 campi, foto con mio, suo, mano, vite, pila)",
                 all(len(q) == 7 and all(k in q[1] for k in ("mio", "suo", "mano", "vite", "pila", "cim", "esi", "_grezza")) for q in ps)))
    casi.append(("il primo passo e' l'inizio della partita", ps[0][0].endswith("Game start")))
    casi.append(("ci sono magie lanciate e terre giocate", any("cast" in t for q in ps for _m, t in q[4]) and any("played" in t for q in ps for _m, t in q[4])))
    fine = ps[-1][1]["vite"]
    casi.append(("la partita finisce: qualcuno a 0 vite o una sconfitta nel racconto",
                 min(fine) <= 0 or any("lost the game" in t for q in ps for _m, t in q[4])))
    casi.append(("la mano dell'Opponent non si vede: solo il numero", all(isinstance(q[1]["n_suo"], int) for q in ps)
                 and not any(t.startswith("Opponent drew ") and t != "Opponent drew a card" for q in ps for _m, t in q[4])))
    casi.append(("l'arbitro non ha fischiato", not M._REG[x["partita"]]["errori"]))
    casi.append(("le magie coi bersagli hanno le frecce (bers non vuoto in almeno un lancio)",
                 any(q[3] and q[3].get("tipo") == "spell" and q[3].get("bers") for q in ps)))
    import dati_analizzatore as DA
    casi.append(("il replayer la trova (DA.azioni_partita e DA.foto_partita)", DA.azioni_partita(x) is ps and bool(DA.foto_partita(x))))
    casi.append(("negativa: una partita simulata che non c'e' non da' passi", DA.azioni_partita(dict(x, partita="sim-nessuna")) is None))
    for n, ok in casi:
        print(("ok    " if ok else "ROSSO ") + n)
    print(f"{sum(1 for _n, ok in casi if ok)}/{len(casi)}")
    return all(ok for _n, ok in casi)


def apri(a, b, seme):
    """Apre il replayer vero su una partita del motore, a vista (la finestra del replayer; la pagina del Leak Finder resta nascosta)."""
    import tkinter as tk
    from tema import famiglie
    from pagina_performance import PaginaPerformance
    root = tk.Tk()
    root.withdraw()
    F = lambda n, b=False: (famiglie()[1] if b else famiglie()[0], n)        # i font dell'app (come Distribuzione/anima_sito.py)
    p = PaginaPerformance(tk, root, F, {})
    x = registra(a, b, seme)
    r = _REG[x["partita"]]
    print(f"{r['mazzi'][0].get('nome')} (Hero) contro {r['mazzi'][1].get('nome')}, seme {seme}: "
          f"{'vince Hero' if r['vincitore'] == 0 else 'vince l Opponent' if r['vincitore'] == 1 else 'pari'}, {len(r['passi'])} passi")
    p.apri_board(x, "inizio")
    fb = p.fin_board
    fb.title(f"The board · engine simulation · {r['mazzi'][0].get('nome')} vs {r['mazzi'][1].get('nome')} · seed {seme}")
    # a vista e grande: la pagina qui e' nascosta e il replayer, che prende la misura da lei, nasceva di 176x199 pixel sotto le altre finestre (24 nov 2026,
    # Autore: «non si è mai aperta»); si apre sullo schermo dove sta l'app (Log_Arena/finestra_pos.json), ingrandito e davanti
    try:
        import json
        from ambiente import LOGDIR
        geo = json.load(open(os.path.join(LOGDIR, "finestra_pos.json"), encoding="utf8")).get("geo") or ""
        xy = geo.split("+")[1:3]
        if len(xy) == 2:
            fb.geometry(f"1500x950+{int(xy[0]) + 40}+{int(xy[1]) + 40}")
    except Exception:       # noqa: BLE001 - senza la posizione dell'app: lo schermo principale
        fb.geometry("1500x950+40+40")
    fb.update_idletasks()
    fb.state("zoomed")
    fb.deiconify(); fb.lift(); fb.attributes("-topmost", True)
    fb.after(800, lambda: fb.attributes("-topmost", False))
    fb.focus_force()
    fine = {"fatto": False}

    def chiudi(*_a):        # una volta sola: chiudere la finestra chiude tutto (prima la chiusura passava due volte e Tk scriveva un errore)
        if not fine["fatto"]:
            fine["fatto"] = True
            root.after_idle(root.destroy)
    fb.protocol("WM_DELETE_WINDOW", chiudi)
    fb.bind("<Destroy>", lambda e: chiudi() if e.widget is fb else None, add="+")
    root.mainloop()


if __name__ == "__main__":
    if "--prova" in sys.argv:
        sys.exit(0 if prova() else 1)
    if "--apri" in sys.argv:
        i_ = sys.argv.index("--apri")
        import partite_motore as M      # il modulo come lo vede il replayer (questo, lanciato come programma, e' __main__ con un altro elenco)
        M.apri(*(int(v) for v in sys.argv[i_ + 1:i_ + 4]))
        sys.exit(0)
    import partite_motore as M
    a_, b_, s_ = (int(v) for v in sys.argv[1:4])
    x_ = M.registra(a_, b_, s_)
    for q in M.azioni(x_):
        print(q[0], "|", "; ".join(t for _m, t in q[4]), "|", q[1]["vite"])
