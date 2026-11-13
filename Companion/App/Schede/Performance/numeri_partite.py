"""I numeri in cima a Performance, da scegliere (13 nov 2026, Autore: «in questa tab in alto a dx creiamo una rotellina di impostazioni con i 6 dati che
vogliamo avere su questa tabella, includi tutti quelli che reputi importanti per i dati delle partite», poi «permetti fino a tutti i valori sulla barra»).

CATALOGO: (chiave, nome, cosa dice). valori(r, tutte) -> {chiave: (testo, tono, riga sotto)}: r le partite della situazione, tutte quelle del tipo (per lo scarto);
tono «su» (sopra il 50% o meglio), «giu», «neutro», «vuoto». La scelta (anche tutti, nell'ordine del catalogo) sta in Log_Arena/performance_numeri.json
dell'account (dati_analizzatore.numeri_scelti).
"""
import os, sys
_casa = os.path.dirname(os.path.abspath(__file__))
while not os.path.isfile(os.path.join(_casa, "percorsi.py")):
    _casa = os.path.dirname(_casa)
if _casa not in sys.path:
    sys.path.insert(0, _casa)
import percorsi  # noqa: E402,F401
import dati_analizzatore as DA  # noqa: E402

PARTENZA = ("wr", "record", "turni", "mull", "play", "draw")
CATALOGO = (("wr", "Win rate", "with its 95% interval"),
            ("record", "Record", "wins and losses, and the gap from all your games"),
            ("partite", "Games", "how many, from the first to the last day"),
            ("turni", "Avg turns", "the length of your wins and your losses"),
            ("mull", "Mulligan", "games where you sent at least one hand back"),
            ("play", "On the play", "win rate when you start"),
            ("draw", "On the draw", "win rate when the opponent starts"),
            ("wr_mull", "After a mulligan", "win rate of the games with a mulligan"),
            ("wr_sette", "Kept 7", "win rate of the games where you kept seven"),
            ("veloci", "Fast wins", "wins by your turn 6, out of all your wins"),
            ("lunghe", "Long games", "win rate of the games past your turn 8"),
            ("concedi", "You conceded", "losses that ended with your concession"),
            ("terre", "Lands kept", "lands in the hand you kept, on average"),
            ("att", "Attack gain", "how much an attack of yours moves the advantage (life + 2 × power)"),
            ("dif", "Defense gain", "the same for your defense, when they attack"),
            ("finisher", "Decided wins", "wins with a decisive play of 2+ cards (Finishers)"))
NOMI = {k: n for k, n, _d in CATALOGO}
MASSIMO = len(CATALOGO)     # tutti (13 nov 2026, Autore: «permetti fino a tutti i valori sulla barra ma ben organizzati»; prima sei)


def _wr(xs):
    return 100 * sum(1 for x in xs if x["vinta"]) / len(xs) if xs else None


def valori(r, tutte):
    import decisioni as DEC
    k = DA.conti(r)
    tot = DA.conti(tutte)
    tono_wr = lambda v: "vuoto" if v is None else ("su" if v >= 50 else "giu")
    pc = lambda v: "-" if v is None else f"{v:.0f}%"
    out = {}
    out["wr"] = (pc(k["wr"]), tono_wr(k["wr"]), f"95% CI {k['ic'][0]}–{k['ic'][1]}%" if k.get("ic") else "")
    out["record"] = (f"{k['vinte']}-{k['perse']}", "neutro", f"Δ {k['wr'] - tot['wr']:+.1f} vs all" if k["wr"] is not None and tot["wr"] is not None
                     and len(r) != len(tutte) else "")
    giorni = sorted(x["quando"] for x in r)
    out["partite"] = (f"{len(r)}", "neutro", f"{giorni[0]:%d %b} – {giorni[-1]:%d %b}" if giorni else "")
    out["turni"] = (f"T{k['turni']}" if k["turni"] else "-", "neutro", f"wins T{k['turni_v'] or '-'} · losses T{k['turni_p'] or '-'}")
    out["mull"] = (pc(k["mull"]), "neutro", "games with a mulligan")
    out["play"] = (pc(k["play"]), tono_wr(k["play"]), f"{k['n_play']} games")
    out["draw"] = (pc(k["draw"]), tono_wr(k["draw"]), f"{k['n_draw']} games")
    mm = [x for x in r if (x.get("mulligan") or 0) > 0]
    out["wr_mull"] = (pc(_wr(mm)), tono_wr(_wr(mm)), f"{len(mm)} games")
    sette = [x for x in r if not (x.get("mulligan") or 0)]
    out["wr_sette"] = (pc(_wr(sette)), tono_wr(_wr(sette)), f"{len(sette)} games")
    vinte = [x for x in r if x["vinta"]]
    veloci = [x for x in vinte if x.get("turno") and x["turno"] <= 6]
    out["veloci"] = (pc(100 * len(veloci) / len(vinte)) if vinte else "-", "neutro", f"{len(veloci)} of {len(vinte)} wins")
    lunghe = [x for x in r if (x.get("turno") or 0) >= 9]
    out["lunghe"] = (pc(_wr(lunghe)), tono_wr(_wr(lunghe)), f"{len(lunghe)} games")
    perse = [x for x in r if not x["vinta"]]
    conc = [x for x in perse if x.get("fine") == "You conceded"]
    out["concedi"] = (pc(100 * len(conc) / len(perse)) if perse else "-", "neutro", f"{len(conc)} of {len(perse)} losses")
    tt = [x["terre"] for x in r if x.get("terre") is not None]
    out["terre"] = (f"{sum(tt) / len(tt):.1f}" if tt else "-", "neutro", f"in {len(tt)} hands")
    for kk, tipo in (("att", "attacco"), ("dif", "blocco")):
        c_ = DEC.tabella(r, tipo)[0]
        b_ = DEC.tabella(tutte, tipo)[0]
        g_, gb = c_.get("guadagno"), b_.get("guadagno")
        tono = "vuoto" if g_ is None else "neutro" if gb is None or len(r) == len(tutte) else ("su" if g_ > gb else "giu")
        out[kk] = (f"{g_:+.1f}" if g_ is not None else "-", tono, f"{c_['n']} combats" + (f" · all {gb:+.1f}" if gb is not None and len(r) != len(tutte) else ""))
    dec = [x for x in vinte if x.get("finisher")]
    out["finisher"] = (pc(100 * len(dec) / len(vinte)) if vinte else "-", "neutro", f"{len(dec)} of {len(vinte)} wins")
    return out


def prova():
    import datetime
    casi = []
    q = datetime.datetime(2026, 11, 1)
    r = [dict(vinta=True, quando=q, turno=5, mulligan=0, terre=3, partenza="Play", fine="Played to the end", finisher=["A", "B"], partita="x1"),
         dict(vinta=False, quando=q, turno=10, mulligan=1, terre=2, partenza="Draw", fine="You conceded", finisher=[], partita="x2"),
         dict(vinta=True, quando=q, turno=9, mulligan=0, terre=4, partenza="Draw", fine="Opponent conceded", finisher=[], partita="x3")]
    v = valori(r, r)
    casi.append(("tutti i numeri del catalogo ci sono", set(v) == {k for k, _n, _d in CATALOGO}))
    casi.append(("dopo il mulligan 0%, tenute a 7 100%, vittorie veloci 1 su 2, partite lunghe 50%, concessioni 1 su 1, terre 3.0, vittorie decise 1 su 2",
                 v["wr_mull"][0] == "0%" and v["wr_sette"][0] == "100%" and v["veloci"][2] == "1 of 2 wins" and v["lunghe"][0] == "50%"
                 and v["concedi"][2] == "1 of 1 losses" and v["terre"][0] == "3.0" and v["finisher"][2] == "1 of 2 wins"))
    v0 = valori([], r)
    casi.append(("negativa: senza partite i numeri sono vuoti, non sbagliati", v0["wr"][0] == "-" and v0["wr_mull"][0] == "-" and v0["veloci"][0] == "-"))
    for n, ok in casi:
        print(("ok    " if ok else "ROSSO ") + n)
    print(f"{sum(1 for _n, ok in casi if ok)}/{len(casi)}")
    return all(ok for _n, ok in casi)


if __name__ == "__main__":
    sys.exit(0 if prova() else 1)
