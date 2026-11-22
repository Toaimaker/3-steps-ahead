"""Lo stato informativo dell'avversario, turno per turno (21 nov 2026; Autore: «per una migliore analisi dei range bisognerebbe tenere conto anche di
cosa opponent ha già messo in esilio o nel cimitero o giocato o già sul board / i mazzi reanimator o carte esiliate che sono conosciute o nascoste in mano
a oppo dovrebbero avere un peso negli spot per l'equity / secondo me questa parte va rivista seriamente», poi «vai tutto in ordine preciso e certosino»).

Quello che di lui si sa alla fine di ogni turno di Arena t, in un posto solo (lo leggono il range, l'equity e la win chance):
  noti      le carte della sua mano che Arena ti fa vedere (rivelate, guardate, tornate in mano davanti a te): oggetti della sua mano col nome e il tuo
            posto fra chi li vede (o pubblici), la stessa regola della spalla del 13 ott 2026 (ev_combattimento.mano_vista); escono quando lasciano la mano
  gioca     le carte che puo' giocare dall'esilio o dal cimitero (il permesso di Arena, Qualification 47, letto da replay_log.segni: «gioca»)
  cim, esi  il suo cimitero e il suo esilio (le sue carte)
  usate     le copie di ogni carta che ha gia' lanciato (le magie, da mana_aperto «azioni»), fino al turno t compreso
  rianima   la rianimazione pronta: una creatura nel suo cimitero e un modo di riportarla (una carta nota o giocabile che rianima, una sua carta gia'
            vista nella partita che rianima, o una creatura giocabile dal cimitero); grado C, dal testo

Misurato il 21 nov 2026: sulle 599 partite coi log, carte note nella sua mano in 140 partite Constructed (821 carte) e 26 Limited (48).
La lettura del log costa ~0,1-0,3 s a partita: si tiene in Log_Arena/cache/stato_avversario.marshal, valida finche' l'ambiente (il codice, le regole, il
database) e il dato della partita sono gli stessi.

    py -I -X utf8 Companion/App/Schede/Performance/stato_avversario.py --prova
    py -I -X utf8 Companion/App/Schede/Performance/stato_avversario.py --tutte
"""
import os
import re
import sys
import json
import marshal      # solo dati, mai codice (SICUREZZA.md R2; fino al 22 nov 2026 era un altro formato)
import collections

_casa = os.path.dirname(os.path.abspath(__file__))
while not os.path.isfile(os.path.join(_casa, "percorsi.py")):
    _casa = os.path.dirname(_casa)
if _casa not in sys.path:
    sys.path.insert(0, _casa)
import percorsi  # noqa: E402,F401

RX_RIANIMA = re.compile(r"(return|put) (up to (one|two) )?(target )?(another )?(nonlegendary )?creature cards? (with [^.]*? )?from (a|your|an opponent's) "
                        r"graveyards? (onto|to) the battlefield|reanimate|return (it|that card) to the battlefield", re.I)
_MEM = {}
_F = None


def _file():
    global _F
    if _F is None:
        from ambiente import LOGDIR
        _F = os.path.join(LOGDIR, "cache", "stato_avversario.marshal")
    return _F


def rianima(nome):
    """La carta riporta una creatura dal cimitero al campo (dal testo, grado C)."""
    import dati_analizzatore as DA
    c = DA._carta(nome or "") or {}
    return bool(RX_RIANIMA.search(c.get("testo") or ""))


def _creatura(nome):
    import dati_analizzatore as DA
    return "Creature" in ((DA._carta(nome or "") or {}).get("tipo") or "").split(" // ")[0]


def noti_dal_log(x):
    """{turno di Arena: [grpId delle carte note nella sua mano a fine turno]} dal log grezzo della partita."""
    import dati_analizzatore as DA
    import replay_log as RL
    righe = RL.righe_partita(x["partita"], (DA._MANA.get(x["partita"]) or {}).get("dove")) or []
    me = x.get("seat")
    if me not in (1, 2):
        return {}
    lui = 3 - me
    zone, obj, out, turno = {}, {}, {}, 0
    for r in righe:
        if "gameStateMessage" not in r:
            continue
        i = r.find("{")
        try:
            d = json.loads(r[i:])
        except ValueError:
            continue
        for gm in (d.get("greToClientEvent") or {}).get("greToClientMessages") or []:
            gs = gm.get("gameStateMessage") or {}
            if not gs:
                continue
            if gs.get("type") == "GameStateType_Full":
                zone.clear()
            for z in gs.get("zones") or []:
                zone[z["zoneId"]] = z
            for o in gs.get("gameObjects") or []:
                obj[o["instanceId"]] = o
            for i_ in gs.get("diffDeletedInstanceIds") or []:
                obj.pop(i_, None)
            t = (gs.get("turnInfo") or {}).get("turnNumber")
            if t:
                turno = t
            noti = []
            for zid, z in zone.items():
                if z.get("type") != "ZoneType_Hand" or z.get("ownerSeatId") != lui:
                    continue
                for i_ in z.get("objectInstanceIds") or []:
                    o = obj.get(i_)
                    if (o and o.get("grpId") and o.get("zoneId") == zid and o.get("ownerSeatId") == lui
                            and (me in (o.get("viewers") or []) or o.get("visibility") == "Visibility_Public")):
                        noti.append(o["grpId"])
            if turno:
                out[turno] = noti
    return out


def calcola(x):
    """{turno di Arena: dict(noti, gioca, cim, esi, usate, rianima)} a fine turno, dal suo lato; {} senza dati."""
    import dati_analizzatore as DA
    seat = x.get("seat")
    d = DA._MANA.get(x.get("partita")) or {}
    if seat not in (1, 2) or "azioni" not in d:
        return {}
    lui = 3 - seat
    try:
        noti = noti_dal_log(x)
    except Exception:       # noqa: BLE001 - senza il log niente carte note
        noti = {}
    try:
        passi = DA.azioni_partita(x) or []
    except Exception:       # noqa: BLE001
        passi = []
    fine = {}                # la foto grezza dell'ultimo passo di ogni turno
    for p in passi:
        g = (p[1] or {}).get("_grezza")
        if g is not None:
            fine[p[2]] = g
    usate = collections.Counter()
    lanci_t = collections.defaultdict(list)
    for t, s_, cosa, g, _tp in d["azioni"]:
        if s_ == lui and cosa == "magia" and g:
            lanci_t[t].append(DA.nome_intero(DA.nome_grp(g) or ""))
    viste = set()
    out = {}
    for t in sorted(set(fine) | set(noti) | set(lanci_t)):
        for n in lanci_t.get(t, []):
            if n:
                usate[n] += 1
                viste.add(n)
        g = fine.get(t) or {}
        nomi = lambda lst: [DA.nome_intero(DA.nome_grp(q) or "") for q in lst or [] if q]
        cim = nomi((g.get("g") or [[], []])[lui - 1])
        esi = nomi((g.get("e") or [[], []])[lui - 1])
        gioca = []
        for _i, seg in (g.get("x") or {}).items():
            gi = (seg or {}).get("gioca")
            if gi and gi[1] == lui and gi[0]:
                gioca.append((DA.nome_intero(DA.nome_grp(gi[0]) or ""), gi[2]))
        nn = [n for n in nomi(noti.get(t) or [])]
        viste |= set(nn)
        bersagli = [n for n in cim if _creatura(n)]
        modo = [n for n in set(nn) | {n_ for n_, _z in gioca} | viste if rianima(n)] + [n for n, z in gioca if z == "cim" and _creatura(n)]
        out[t] = dict(noti=nn, gioca=gioca, cim=cim, esi=esi, usate=dict(usate), rianima=bool(bersagli and modo), bersagli=bersagli,
                      modo_rianima=sorted(set(modo)))
    return out


def _chiave(x):
    import dati_analizzatore as DA
    d = DA._MANA.get(x.get("partita")) or {}
    return (x.get("partita"), x.get("seat"), len(d.get("azioni") or []), len(d.get("momenti") or []))


def _carica():
    import dati_analizzatore as DA
    amb = DA._ambiente_righe()
    if _MEM.get("amb") == amb:
        return _MEM["s"]
    try:
        with open(_file(), "rb") as h:
            c = marshal.loads(h.read())
        s = c["s"] if c.get("amb") == amb else {}
    except Exception:       # noqa: BLE001
        s = {}
    _MEM.update(amb=amb, s=s, sporco=False)
    return s


def salva():
    if not _MEM.get("sporco"):
        return
    try:
        f = _file()
        os.makedirs(os.path.dirname(f), exist_ok=True)
        with open(f + ".tmp", "wb") as h:
            marshal.dump(dict(amb=_MEM["amb"], s=_MEM["s"]), h)
        os.replace(f + ".tmp", f)
        _MEM["sporco"] = False
    except OSError:
        pass


def stato(x):
    """Lo stato della partita x (dalla copia, se no dal log)."""
    s = _carica()
    k = _chiave(x)
    if k not in s:
        s[k] = calcola(x)
        _MEM["sporco"] = True
    return s[k]


def al_turno(x, t):
    """Lo stato a fine del turno di Arena t (o del turno prima piu' vicino che c'e'); {} senza."""
    s = stato(x)
    ks = [k for k in s if k <= t]
    return s[max(ks)] if ks else {}


def prova():
    casi = []
    casi.append(("Reanimate rianima", bool(RX_RIANIMA.search("Put target creature card from a graveyard onto the battlefield under your control."))))
    casi.append(("Unearth: ritorno di una creatura dal tuo cimitero", bool(RX_RIANIMA.search("Return target creature card with mana value 3 or less from your graveyard to the battlefield."))))
    casi.append(("negativa: rimettere in mano non e' rianimare", not RX_RIANIMA.search("Return target creature card from your graveyard to your hand.")))
    casi.append(("negativa: una creatura che va al cimitero no", not RX_RIANIMA.search("When this creature dies, draw a card.")))
    # su una partita vera con carte note (se c'e'): le carte note sono nomi, ogni turno ha i campi
    try:
        import dati_analizzatore as DA
        R = DA.righe()
        trovata = None
        for x in reversed(R):
            s = calcola(x)
            if any(v["noti"] for v in s.values()):
                trovata = (x, s)
                break
        if trovata:
            x, s = trovata
            casi.append(("una partita vera: le carte note nella sua mano, coi nomi", all(isinstance(n, str) and n for v in s.values() for n in v["noti"])))
            usate = [v["usate"] for _t, v in sorted(s.items())]
            casi.append(("le copie usate non calano mai turno dopo turno", all(all(b.get(k, 0) >= a_ for k, a_ in a.items()) for a, b in zip(usate, usate[1:]))))
    except Exception as e:      # noqa: BLE001
        casi.append((f"la partita vera: {e}", False))
    for n, ok in casi:
        print(("ok    " if ok else "ROSSO ") + n)
    print(f"{sum(1 for _n, ok in casi if ok)}/{len(casi)}")
    return all(ok for _n, ok in casi)


if __name__ == "__main__":
    if "--prova" in sys.argv:
        sys.exit(0 if prova() else 1)
    if "--tutte" in sys.argv:
        import time
        import dati_analizzatore as DA
        t0 = time.time()
        R = DA.righe()
        c = collections.Counter()
        for j, x in enumerate(R):
            s = stato(x)
            c["partite"] += 1
            c["con carte note"] += any(v["noti"] for v in s.values())
            c["con giocabili dall'esilio o dal cimitero"] += any(v["gioca"] for v in s.values())
            c["con rianimazione pronta"] += any(v["rianima"] for v in s.values())
            if j % 50 == 0:
                salva()
        salva()
        print(dict(c), f"{time.time() - t0:.0f} s")
