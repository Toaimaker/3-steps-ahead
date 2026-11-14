"""L'analisi per decisione (13 nov 2026, Autore: «ok costruiamo l'analisi per decisione», «se imposto il filtro play on draw il win rate assoluto scende e
l'unica risorsa che avrei a disposizione per capire come migliorare in quella fase è analizzare il mulligan ma non so cosa dovrei inserire per leggere il mio
miglioramento al mulligan», «quando analizziamo i roi di giocata, li dobbiamo vedere anche sul grafico aggiungendo una linea sul grafico vs quella totale ...
tipo holdem manager»).

Fino a quel giorno Performance guardava la partita: «hai attaccato contro 2 terre stappate» diceva come e' finita la partita, non come e' andato quell'attacco.
Qui ogni combattimento e' una decisione col suo esito immediato, dai momenti di mana_aperto (lo stato prima del danno e quello a fine turno):

  attacco (tuo) / blocco (suo attacco, la tua difesa): quante creature attaccano e quante potevano, le terre stappate di chi difende, i blocchi; l'esito: le
  creature che attaccavano o bloccavano e non ci sono piu' a fine turno (tue e sue), le vite perse da chi difende, se chi difende ha giocato una magia nel
  turno prima del danno (un trucco, o una rimozione in combattimento) e se l'ha giocata chi attacca.

Limiti dichiarati: «a fine turno» comprende anche quel che succede dopo il combattimento (una rimozione nella seconda fase principale); le magie si sanno
nel turno, non il passo esatto (il trucco e' una magia di chi difende fra l'inizio del turno e il danno). Le vite sono quelle a fine turno: comprendono
anche un'altra perdita dopo il combattimento.

E i mulligan: le mani tenute per numero di terre sul play e sul draw, le mani rimandate indietro, le mani rischiose tenute (0-1 o 5+ terre), settimana per
settimana, cosi' si legge se le decisioni al mulligan migliorano.
"""
import os, sys
_casa = os.path.dirname(os.path.abspath(__file__))
while not os.path.isfile(os.path.join(_casa, "percorsi.py")):
    _casa = os.path.dirname(_casa)
if _casa not in sys.path:
    sys.path.insert(0, _casa)
import percorsi  # noqa: E402,F401
import collections  # noqa: E402
import datetime  # noqa: E402
import dati_analizzatore as DA  # noqa: E402

MINIMO = 10         # sotto, una riga e' un indizio (grigia)


def _ids(foto, lato):
    """Le creature (forza non vuota) di un lato della foto: {instanceId: [grp, tappata, pedina, forza, costituzione, id]}."""
    return {c[5]: c for c in ((foto or {}).get("c") or [[], []])[lato] or [] if c[3] is not None}


def _tutti_id(foto):
    return {c[5] for lato in ((foto or {}).get("c") or [[], []]) for c in lato or []}


def _istantaneo(g):
    nm = DA.nome_grp(g) if g not in DA.SENZA_FACCIA else None
    return "Instant" in ((DA._carta(nm) or {}).get("tipo") or "") if nm else False


# Le decisioni di una partita non dipendono dai filtri: si calcolano una volta (14 nov 2026, Autore: «quando setto filtri in performance ... ci mette piu'
# di ieri»). Ogni filtro rifaceva i numeri in cima, e «Attack/Defense gain» rifaceva le decisioni di tutte le partite quattro volte, col modello della P
# (R8, ~12.000 valutazioni): 7-17 s a filtro col profilo acceso. La copia vale finche' il dato della partita (DA._MANA) e' lo stesso oggetto.
_MEMO = {}


def _ricorda(nome, x, d, fai):
    k = (nome, x.get("partita"), x.get("seat"), x.get("inizia"), x.get("mulligan"), x.get("vinta"), x.get("quando"))
    v = _MEMO.get(k)
    if v is None or v[0] is not d:
        v = _MEMO[k] = (d, fai())
    return [dict(z) for z in v[1]]      # copie: chi le riceve puo' aggiungere campi


def per_partita(x):
    """Le decisioni di combattimento di una partita (riga dell'analizzatore): [dict]. Vuota senza i momenti di mana_aperto o senza sapere il tuo posto."""
    d = DA._MANA.get(x.get("partita")) or {}
    if not d:
        return []
    return _ricorda("comb", x, d, lambda: _per_partita(x, d))


def _per_partita(x, d):
    seat = x.get("seat")
    mom = d.get("momenti") or []
    if seat not in (1, 2) or not mom:
        return []
    out = []
    for i, m in enumerate(mom):
        if m[0] != "comb" or len(m) < 5 or not m[4] or not m[4].get("att"):
            continue
        t, att, prima, info = m[1], m[2], m[3], m[4]
        dif = 2 if att == 1 else 1
        dopo = next((m2[3] for m2 in mom[i + 1:] if m2[0] == "fine" and m2[1] == t), None)
        if dopo is None and d.get("ultima"):
            dopo = d["ultima"][-1]
        resta = _tutti_id(dopo)
        att_ids = [a[0] for a in info["att"]]
        blk_ids = [b[0] for b in info.get("blocchi") or []]
        persi_att = sum(1 for a in att_ids if a not in resta)
        persi_blk = sum(1 for b in blk_ids if b not in resta)
        v0 = ((prima or {}).get("v") or [None, None])
        v1 = ((dopo or {}).get("v") or [None, None])
        danno = (v0[dif - 1] - v1[dif - 1]) if v0[dif - 1] is not None and v1[dif - 1] is not None else None
        # le magie del turno prima del danno: di chi difende tutte (nel turno dell'altro si lanciano solo istantanei e flash); di chi e' di turno solo gli
        # istantanei, se no conterebbero le magie della prima fase principale
        magie = [m2[4].get("chi") for m2 in mom[:i] if m2[0] == "spell" and m2[1] == t and m2[4] and not m2[4].get("ab")
                 and (m2[4].get("chi") != att or _istantaneo(m2[4].get("g")))]
        mio = att == seat
        pot = info.get("pot")
        out.append(dict(
            tipo="attacco" if mio else "blocco", t=t, turno=(t + 1) // 2, partita=x.get("partita"), vinta=x["vinta"], quando=x["quando"],
            attaccanti=len(att_ids), potevano=pot, tutto=bool(pot) and len(att_ids) >= pot, aperte=info.get("aperte"),
            blocchi=len(blk_ids), bloccato=bool(blk_ids),
            persi_miei=persi_att if mio else persi_blk, persi_suoi=persi_blk if mio else persi_att,
            danno=danno, trucco_suo=(dif if mio else att) in magie, trucco_mio=(att if mio else dif) in magie,
            # il guadagno della decisione (13 nov 2026, Autore: «lo esprimiamo come guadagno per spots e non per win rate perché qui analizziamo le azioni
            # non l'esito del game»): quanto cambia il tuo vantaggio (vite di differenza piu' due volte la forza in campo di differenza, DA.vantaggio) dallo
            # stato prima del danno a fine turno
            guadagno=DA.vantaggio(dopo, seat) - DA.vantaggio(prima, seat) if prima and dopo else None,
            guadagno_p=_delta_p(prima, dopo, seat, t, att, x)))
    return out


def _delta_p(prima, dopo, seat, t, att, x):
    """R8: quanto cambia la probabilita' di vincere (punti percentuali, DA.p_foto) dalla foto prima alla foto dopo. Tutte e due lette come all'inizio del
    turno dopo (tocca a chi non e' di turno ora, il giro del turno dopo): cosi' cambia solo il tavolo, non chi tocca. None se manca una delle due."""
    if not prima or not dopo:
        return None
    tocca = att != seat
    giro = (t + 2) // 2
    p0 = DA.p_foto(prima, seat, tocca, giro, x.get("inizia"), x.get("mulligan"))
    p1 = DA.p_foto(dopo, seat, tocca, giro, x.get("inizia"), x.get("mulligan"))
    return None if p0 is None or p1 is None else round(p1 - p0, 2)


def per_partita_magie(x):
    """Le tue magie coi bersagli (e i board wipe) come decisioni (R8, 13 nov 2026): il guadagno e' quanto cambia il vantaggio dallo stato con la magia in
    pila al momento dopo. [dict(tipo="magia", t, turno, partita, nome, guadagno)]."""
    d = DA._MANA.get(x.get("partita")) or {}
    if not d:
        return []
    return _ricorda("magie", x, d, lambda: _per_partita_magie(x, d))


def _per_partita_magie(x, d):
    seat = x.get("seat")
    mom = d.get("momenti") or []
    if seat not in (1, 2):
        return []
    out = []
    for i, m in enumerate(mom):
        if m[0] != "spell" or len(m) < 5 or not m[4] or m[4].get("chi") != seat or m[4].get("ab"):
            continue
        dopo = next((m2[3] for m2 in mom[i + 1:] if isinstance(m2[3], dict)), None)
        prima = m[3] if isinstance(m[3], dict) else None
        nome = DA.nome_grp(m[4].get("g")) if m[4].get("g") not in DA.SENZA_FACCIA else None
        out.append(dict(tipo="magia", t=m[1], turno=(m[1] + 1) // 2, partita=x.get("partita"), vinta=x.get("vinta"), quando=x.get("quando"), nome=nome or "a spell",
                        guadagno=DA.vantaggio(dopo, seat) - DA.vantaggio(prima, seat) if prima and dopo else None,
                        guadagno_p=_delta_p(prima, dopo, seat, m[1], m[2], x)))
    return out


# R8, il costo delle decisioni (13 nov 2026, come GTO Wizard): il guadagno di ogni tua decisione contro la media delle tue decisioni dello stesso tipo nella
# stessa fase della partita; rosso sotto COSTO_ROSSO, giallo sotto COSTO_GIALLO, verde il resto; senza il dato «not estimable». Dal 13 nov 2026 sera
# (Autore: «Sì, con la citazione») il guadagno di R8 e' in punti di probabilita' di vincere (guadagno_p, DA.p_foto: il modello del suggeritore tarato sui
# replay pubblici di 17Lands); le altre viste di Decisions restano sul vantaggio (vite + 2 × forza), come chiesto il 13 nov («guadagno per spots e non per win
# rate»). Un indizio, mai una sentenza; il numero vero sta sempre accanto al colore.
COSTO_ROSSO, COSTO_GIALLO = -5.0, -2.0               # col vantaggio
# con la P (punti percentuali): tarate sui log del 13 nov perche' i colori tengano le quote di prima (rosso il 15% piu' costoso, giallo fino al 40%; col
# vantaggio erano -5 e -2): con -5 e -2 sulla P i rossi erano il 31%
COSTO_ROSSO_P, COSTO_GIALLO_P = -7.0, -3.5


def colore_costo(v, campo="guadagno"):
    rosso, giallo = (COSTO_ROSSO_P, COSTO_GIALLO_P) if campo == "guadagno_p" else (COSTO_ROSSO, COSTO_GIALLO)
    return "nd" if v is None else "rosso" if v <= rosso else "giallo" if v <= giallo else "verde"


def costi(r, base_r, campo="guadagno_p"):
    """Le decisioni delle partite r (i tuoi attacchi e blocchi, le tue magie coi bersagli) col costo contro la media di base_r (di solito tutte le partite
    del tipo). -> [dict(..., media, costo, colore)], dalla piu' costosa."""
    def tutte_d(rr):
        out = []
        for x in rr:
            out += [dd for dd in per_partita(x) if dd["tipo"] in ("attacco", "blocco")] + per_partita_magie(x)
        return out
    somme = {}
    for dd in tutte_d(base_r):
        if dd.get(campo) is not None:
            k = (dd["tipo"], _fascia_turno(dd["turno"]))
            s_, n_ = somme.get(k, (0.0, 0))
            somme[k] = (s_ + dd[campo], n_ + 1)
    out = []
    for dd in tutte_d(r):
        s_, n_ = somme.get((dd["tipo"], _fascia_turno(dd["turno"])), (0.0, 0))
        media = s_ / n_ if n_ else None
        costo = dd[campo] - media if dd.get(campo) is not None and media is not None else None
        out.append(dict(dd, media=media, costo=costo, colore=colore_costo(costo, campo), guadagno_r8=dd.get(campo)))
    out.sort(key=lambda z: (z["costo"] is None, z["costo"] if z["costo"] is not None else 0))
    return out


# R9, «cosa faresti qui?» (13 nov 2026, come chess.com e lichess): le scelte di una decisione e quanto hanno reso nelle tue partite
OPZIONI = {"attacco": (("tutto", "Attack with everything"), ("parte", "Attack with some"), ("niente", "Don't attack")),
           "blocco": (("blocca", "Block"), ("lascia", "Don't block"))}


def scelta_fatta(dd):
    """La scelta che hai fatto davvero in una decisione di combattimento."""
    if dd["tipo"] == "attacco":
        return "tutto" if dd.get("tutto") else "parte"
    return "blocca" if dd.get("bloccato") else "lascia"


def medie_opzioni(base_r, tipo, fascia):
    """Quanto ha reso ogni scelta nelle tue partite (base_r), nella stessa fase: {scelta: (guadagno medio, quante)}. «Don't attack» non e' un combattimento:
    nel log non c'e', quindi non ha media."""
    acc = {}
    for x in base_r:
        for dd in per_partita(x):
            if dd["tipo"] != tipo or dd["guadagno"] is None or _fascia_turno(dd["turno"]) != fascia:
                continue
            s_, n_ = acc.get(scelta_fatta(dd), (0.0, 0))
            acc[scelta_fatta(dd)] = (s_ + dd["guadagno"], n_ + 1)
    return {k: (s_ / n_, n_) for k, (s_, n_) in acc.items() if n_}


def tutte(r):
    """Le decisioni delle partite r, in ordine di tempo."""
    out = []
    for x in r:
        out += per_partita(x)
    return out


def _fascia_turno(n):
    return "Turns 1-3" if n <= 3 else "Turns 4-6" if n <= 6 else "Turns 7+"


def _aperte(a):
    return None if a is None else "0 untapped lands" if a == 0 else "1 untapped land" if a == 1 else "2+ untapped lands"


# le righe delle tabelle: (nome, condizione sulla decisione); la prima e' tutte
RIGHE_ATTACCO = [("All your attacks", lambda d: True),
                 ("Into 0 untapped lands", lambda d: d["aperte"] == 0), ("Into 1 untapped land", lambda d: d["aperte"] == 1),
                 ("Into 2+ untapped lands", lambda d: (d["aperte"] or 0) >= 2),
                 ("With everything that could", lambda d: d["tutto"]), ("Holding some back", lambda d: d["potevano"] and not d["tutto"]),
                 ("With everything, into 2+ untapped lands", lambda d: d["tutto"] and (d["aperte"] or 0) >= 2),
                 ("They blocked", lambda d: d["bloccato"]), ("Not blocked", lambda d: not d["bloccato"]),
                 ("They cast a spell before damage", lambda d: d["trucco_suo"]),
                 ("Turns 1-3", lambda d: d["turno"] <= 3), ("Turns 4-6", lambda d: 4 <= d["turno"] <= 6), ("Turns 7+", lambda d: d["turno"] >= 7)]
RIGHE_BLOCCO = [("All their attacks", lambda d: True),
                ("You blocked", lambda d: d["bloccato"]), ("You didn't block", lambda d: not d["bloccato"]),
                ("You blocked with 2+ creatures", lambda d: d["blocchi"] >= 2),
                ("They attacked into your 2+ untapped lands", lambda d: (d["aperte"] or 0) >= 2),
                ("They attacked with everything", lambda d: d["tutto"]),
                ("You cast a spell before damage", lambda d: d["trucco_mio"]), ("They cast a spell before damage", lambda d: d["trucco_suo"]),
                ("Turns 1-3", lambda d: d["turno"] <= 3), ("Turns 4-6", lambda d: 4 <= d["turno"] <= 6), ("Turns 7+", lambda d: d["turno"] >= 7)]


def guadagni(r, tipi, ff, base):
    """Il guadagno delle decisioni contro la media (13 nov 2026, Autore: «voglio vedere il gained by decisions vs la media delle partite: positivo linea
    verde negativo linea rossa»): per ogni partita di r (in ordine di tempo) la somma, sulle sue decisioni dei tipi `tipi` che passano f, di guadagno meno il
    guadagno medio delle stesse decisioni in tutte le partite `base`. ff: {tipo: filtri delle decisioni}. -> ({partita: scarto della partita}, {tipo: media}).
    Le partite senza decisioni scelte non ci sono."""
    medie = {}
    for t_ in tipi:
        g_ = [d["guadagno"] for d in scegli([d for d in tutte(base) if d["tipo"] == t_], (ff or {}).get(t_)) if d["guadagno"] is not None]
        medie[t_] = sum(g_) / len(g_) if g_ else 0.0
    per = {}
    for x in r:
        dd = [d for t_ in tipi for d in scegli([d for d in per_partita(x) if d["tipo"] == t_], (ff or {}).get(t_)) if d["guadagno"] is not None]
        if dd:
            per[x.get("partita")] = sum(d["guadagno"] - medie[d["tipo"]] for d in dd)
    return per, medie


def conti(dd):
    """I conti di un gruppo di decisioni: quante, in quante partite, % in cui hai perso almeno una creatura, % in cui lui ha perso, lo scambio medio (sue perse
    meno tue), il danno medio a chi difende, % col suo trucco, il win rate delle partite (ognuna una volta)."""
    n = len(dd)
    if not n:
        return dict(n=0, partite=0, perdi=None, uccidi=None, scambio=None, danno=None, trucco=None, wr=None, guadagno=None, ids=set())
    ids = {d["partita"] for d in dd}
    vinte = {d["partita"] for d in dd if d["vinta"]}
    danni = [d["danno"] for d in dd if d["danno"] is not None]
    gg = [d["guadagno"] for d in dd if d.get("guadagno") is not None]
    return dict(n=n, partite=len(ids), guadagno=round(sum(gg) / len(gg), 1) if gg else None, perdi=round(100 * sum(1 for d in dd if d["persi_miei"]) / n, 1),
                uccidi=round(100 * sum(1 for d in dd if d["persi_suoi"]) / n, 1),
                scambio=round(sum(d["persi_suoi"] - d["persi_miei"] for d in dd) / n, 2),
                danno=round(sum(danni) / len(danni), 1) if danni else None,
                trucco=round(100 * sum(1 for d in dd if d["trucco_suo"]) / n, 1),
                wr=round(100 * len(vinte) / len(ids), 1), ids=ids)


# i filtri delle decisioni (13 nov 2026, Autore: «Credo che decisions dovrebbe settarsi in base ai filtri che esprimo ... se io volessi sapere quanto
# perdo in difesa a T3 non ho possibilita' di settarlo», poi «i filtri per decision li imposti costruibili», «ovviamente tieni solo i filtri per noi "Player"
# perche' non possiamo valutare le decisioni di opponent»): solo le tue scelte e la situazione in cui le hai fatte. (chiave, nome, voci), per tipo.
TURNI_DEC = ("1", "2", "3", "4", "5", "6", "7", "8", "9+")
FILTRI = {"attacco": (("turno", "Turn", TURNI_DEC), ("aperte", "Their untapped lands", ("0", "1", "2+")),
                      ("tutto", "You attacked with everything", ("Yes", "No")), ("trucco_mio", "Your spell before damage", ("Yes", "No"))),
          "blocco": (("turno", "Turn", TURNI_DEC), ("aperte", "Your untapped lands", ("0", "1", "2+")), ("bloccato", "You blocked", ("Yes", "No")),
                     ("blocchi", "You blocked with", ("1 creature", "2+ creatures")), ("trucco_mio", "Your spell before damage", ("Yes", "No")))}


def valore(d, k):
    """La voce di un filtro delle decisioni per la decisione d (None: non si sa, o non vale per quel tipo di decisione)."""
    if k == "turno":
        return str(d["turno"]) if d["turno"] < 9 else "9+"
    if k == "aperte":
        return None if d["aperte"] is None else str(d["aperte"]) if d["aperte"] < 2 else "2+"
    if k == "blocchi":
        return None if not d["blocchi"] else "1 creature" if d["blocchi"] == 1 else "2+ creatures"
    return "Yes" if d[k] else "No"


def scegli(dd, f):
    """Le decisioni che passano i filtri f ({chiave: [voci]}; una voce sola vale come lista): fra le voci di un filtro basta una (turno 3 o 4), fra filtri
    diversi servono tutti."""
    f = {k: ([v] if isinstance(v, str) else list(v)) for k, v in (f or {}).items() if v}
    return [d for d in dd if all(valore(d, k) in v for k, v in f.items())]


def descrivi(f, tipo):
    """I filtri delle decisioni in parole: «turn 3 or 4 · you blocked yes»."""
    nomi = {k: n for k, n, _v in FILTRI.get(tipo, ())}
    out = []
    for k, v in (f or {}).items():
        if v:
            vv = [v] if isinstance(v, str) else v
            out.append(f"{nomi.get(k, k).lower()} {' or '.join(vv)}")
    return " · ".join(out)


def tabella(r, tipo, f=None):
    """Le righe della tabella degli attacchi («attacco») o dei blocchi («blocco») sulle partite r e coi filtri delle decisioni f: [dict(nome, **conti, poche)]."""
    dd = scegli([d for d in tutte(r) if d["tipo"] == tipo], f)
    out = []
    for nome, cond in (RIGHE_ATTACCO if tipo == "attacco" else RIGHE_BLOCCO):
        c = conti([d for d in dd if cond(d)])
        c.update(nome=nome, poche=c["n"] < MINIMO)
        out.append(c)
    return out


# ------------------------------------------------------------------ i mulligan
def _rischiosa(terre):
    return terre is not None and (terre <= 1 or terre >= 5)


def mulligan(r):
    """I mulligan delle partite r (righe dell'analizzatore, coi campi «terre», «partenza», «mulligan», «scartate»):
    tenute: {terre: {"Play": (partite, vinte), "Draw": (...)}} delle mani tenute (le terre 0-7);
    scartate: {terre: quante} delle mani rimandate indietro;
    dopo: (partite, vinte) di chi ha fatto almeno un mulligan; rischiose: (partite, vinte) delle mani tenute con 0-1 o 5+ terre senza mulligan; normali:
    (partite, vinte) delle altre tenute a 7."""
    ten = collections.defaultdict(lambda: {"Play": [0, 0], "Draw": [0, 0]})
    scart = collections.Counter()
    dopo, risc, norm = [0, 0], [0, 0], [0, 0]
    for x in r:
        if x.get("terre") is not None and x.get("partenza"):
            ten[min(x["terre"], 7)][x["partenza"]][0] += 1
            ten[min(x["terre"], 7)][x["partenza"]][1] += 1 if x["vinta"] else 0
        for s_ in x.get("scartate") or []:
            scart[min(s_, 7)] += 1
        if (x.get("mulligan") or 0) > 0:
            dopo[0] += 1; dopo[1] += 1 if x["vinta"] else 0
        elif x.get("terre") is not None:
            b = risc if _rischiosa(x["terre"]) else norm
            b[0] += 1; b[1] += 1 if x["vinta"] else 0
    return dict(tenute={k: {p: tuple(v) for p, v in d.items()} for k, d in ten.items()}, scartate=dict(scart), dopo=tuple(dopo), rischiose=tuple(risc),
                normali=tuple(norm))


def settimane(r, quante=8):
    """Il mulligan settimana per settimana (le ultime `quante` con partite): [dict(da, partite, mull %, rischiose %, wr dopo il mulligan, wr delle tenute a 7,
    wr di tutte)]. Cosi' si legge il miglioramento: meno mani rischiose tenute, e chi fa mulligan che vince di piu'."""
    per = collections.defaultdict(list)
    for x in r:
        q = x["quando"].date()
        per[q - datetime.timedelta(days=q.weekday())].append(x)
    out = []
    for da in sorted(per)[-quante:]:
        g = per[da]
        mull = [x for x in g if (x.get("mulligan") or 0) > 0]
        sette = [x for x in g if not (x.get("mulligan") or 0) and x.get("terre") is not None]
        risc = [x for x in sette if _rischiosa(x["terre"])]
        wr = lambda xs: round(100 * sum(1 for x in xs if x["vinta"]) / len(xs), 1) if xs else None
        out.append(dict(da=da, partite=len(g), mull=round(100 * len(mull) / len(g), 1), rischiose=round(100 * len(risc) / len(sette), 1) if sette else None,
                        wr_mull=wr(mull), wr_sette=wr(sette), wr=wr(g), n_mull=len(mull)))
    return out


def prova_opzioni():
    casi = []
    casi.append(("R9: la scelta fatta", scelta_fatta(dict(tipo="attacco", tutto=True)) == "tutto" and scelta_fatta(dict(tipo="attacco", tutto=False)) == "parte"
                 and scelta_fatta(dict(tipo="blocco", bloccato=False)) == "lascia"))
    vero = per_partita
    try:
        dd = {"a": [dict(tipo="attacco", turno=2, guadagno=4.0, tutto=True)], "b": [dict(tipo="attacco", turno=3, guadagno=-2.0, tutto=False)],
              "c": [dict(tipo="attacco", turno=3, guadagno=2.0, tutto=True)], "d": [dict(tipo="attacco", turno=9, guadagno=9.0, tutto=True)]}
        globals()["per_partita"] = lambda x: dd[x["partita"]]
        m = medie_opzioni([dict(partita=k) for k in dd], "attacco", "Turns 1-3")
        casi.append(("R9: le medie delle scelte nella stessa fase (con tutto 3 su 2, con una parte -2 su 1); negativa: il turno 9 non entra, «Don't attack» non ha media",
                     m == {"tutto": (3.0, 2), "parte": (-2.0, 1)}))
    finally:
        globals()["per_partita"] = vero
    return casi


def prova_memo():
    """Le decisioni tenute a mente (14 nov 2026): la seconda volta non si rifanno, sono copie, e un dato nuovo della partita le rifa'."""
    casi, conta = [], [0]
    x = dict(partita="memo1", seat=1, vinta=True)
    d1, d2 = {"momenti": []}, {"momenti": []}
    fai = lambda: (conta.__setitem__(0, conta[0] + 1), [dict(tipo="attacco", guadagno=1.0)])[1]
    a = _ricorda("prova", x, d1, fai)
    a[0]["costo"] = 9          # chi la riceve la cambia: la copia tenuta a mente no
    b_ = _ricorda("prova", x, d1, fai)
    casi.append(("le decisioni di una partita si fanno una volta; chi le riceve ha una copia", conta[0] == 1 and "costo" not in b_[0]))
    _ricorda("prova", x, d2, fai)
    casi.append(("negativa: col dato della partita riletto (un altro oggetto) si rifanno", conta[0] == 2))
    _ricorda("prova", dict(x, seat=2), d2, fai)
    casi.append(("negativa: un altro posto e' un'altra partita", conta[0] == 3))
    for k in [k for k in _MEMO if k[0] == "prova"]:
        del _MEMO[k]
    return casi


def prova_costi():
    """R8: il costo contro la media dello stesso tipo e fase; i colori; senza il dato «nd»."""
    casi = []
    casi.append(("i colori: -6 rosso, -3 giallo, 0 verde, None non stimabile", [colore_costo(v) for v in (-6, -3, 0, None)] == ["rosso", "giallo", "verde", "nd"]))
    casi.append(("con la P: -6 punti e' giallo, -8 rosso, -3 verde", [colore_costo(v, "guadagno_p") for v in (-6, -8, -3)] == ["giallo", "rosso", "verde"]))
    vero = (per_partita, per_partita_magie)
    try:
        dd = {"a": [dict(tipo="attacco", turno=2, guadagno=4.0)], "b": [dict(tipo="attacco", turno=3, guadagno=-4.0)],
              "c": [dict(tipo="attacco", turno=8, guadagno=-10.0)]}
        globals()["per_partita"] = lambda x: [dict(z, partita=x["partita"], t=2 * z["turno"]) for z in dd[x["partita"]]]
        globals()["per_partita_magie"] = lambda x: []
        tutte_ = [dict(partita=k) for k in dd]
        cc = costi(tutte_, tutte_, campo="guadagno")
        b_ = next(z for z in cc if z["partita"] == "b")
        casi.append(("il costo: -4 contro la media dei primi turni (0) = -4, giallo; il turno 8 ha la sua media (nessun confronto coi primi turni)",
                     abs(b_["costo"] + 4) < 1e-9 and b_["colore"] == "giallo" and next(z for z in cc if z["partita"] == "c")["costo"] == 0))
        casi.append(("in ordine dalla piu' costosa", cc[0]["partita"] == "b"))
        casi.append(("negativa: senza il campo (guadagno_p assente) il costo non si stima", all(z["colore"] == "nd" for z in costi(tutte_, tutte_))))
    finally:
        globals()["per_partita"], globals()["per_partita_magie"] = vero
    return casi


def prova_p():
    """R8 col modello della P: piu' creature tue, piu' P; il delta dalla foto prima alla foto dopo."""
    casi = []
    cr = lambda i, pw=3: [100 + i, 0, 0, pw, pw, i]
    t1 = dict(c=[[cr(1)], [cr(2)]], v=[20, 20], n=[4, 4])
    t2 = dict(c=[[cr(1), cr(3)], []], v=[20, 20], n=[4, 4])
    p1, p2 = DA.p_foto(t1, 1, True, 4, True), DA.p_foto(t2, 1, True, 4, True)
    casi.append(("R8: la P sale se tu hai due creature e lui nessuna", p1 is not None and p2 is not None and p2 > p1))
    casi.append(("negativa: la P di lui dallo stesso tavolo e' l'opposto (sopra il 50% tu, sotto lui)", p2 > 50 and DA.p_foto(t2, 2, False, 4, False) < 50))
    d_ = _delta_p(t1, t2, 1, 7, 1, dict(inizia=True, mulligan=0))
    casi.append(("il delta e' P dopo meno P prima, coi due tavoli letti nello stesso turno", d_ is not None and d_ > 0 and _delta_p(None, t2, 1, 7, 1, {}) is None))
    return casi


def prova():
    casi = []
    q = datetime.datetime(2026, 11, 10)
    cr = lambda i, pw=2: [100 + i, 0, 0, pw, 2, i]
    foto = lambda mie, sue, v: dict(c=[mie, sue], v=v)
    vecchio = dict(DA._MANA)
    try:
        DA._MANA.clear()
        # tu (posto 1) attacchi al turno 3 con due creature contro 2 sue terre stappate; lui blocca con una, gioca un trucco: perdi un attaccante, lui niente;
        # poi lui attacca al turno 4 e tu non blocchi: 3 danni
        DA._MANA["g1"] = dict(momenti=[
            ["spell", 3, 1, None, dict(g=9, chi=2, ab=False)],
            ["spell", 3, 1, None, dict(g=8, chi=1, ab=False)],      # la tua magia di prima fase principale (non un istantaneo): non e' un tuo trucco
            ["comb", 3, 1, foto([cr(1), cr(2)], [cr(5)], [20, 20]), dict(att=[[1, 2], [2, 2]], blocchi=[[5, [1]]], pot=2, aperte=2)],
            ["fine", 3, 1, foto([cr(2)], [cr(5)], [20, 18])],
            ["comb", 4, 2, foto([cr(2)], [cr(5, 3)], [20, 18]), dict(att=[[5, 1]], blocchi=[], pot=1, aperte=0)],
            ["fine", 4, 2, foto([cr(2)], [cr(5, 3)], [17, 18])]])
        x = dict(partita="g1", seat=1, vinta=False, quando=q)
        dd = per_partita(x)
        a, b = dd
        casi.append(("l'attacco: 2 su 2 contro 2 terre stappate, bloccato, il suo trucco prima del danno, perdi un attaccante, lui niente, 2 danni",
                     a["tipo"] == "attacco" and a["tutto"] and a["aperte"] == 2 and a["bloccato"] and a["trucco_suo"] and a["persi_miei"] == 1
                     and a["persi_suoi"] == 0 and a["danno"] == 2 and not a["trucco_mio"]))
        casi.append(("il blocco: lui attacca, tu non blocchi, 3 danni a te, nessuno perde creature", b["tipo"] == "blocco" and not b["bloccato"] and b["danno"] == 3
                     and b["persi_miei"] == 0 and b["persi_suoi"] == 0 and b["turno"] == 2))
        casi.append(("il guadagno della decisione: il vantaggio a fine turno meno quello prima del danno (tu perdi un 2/2 e lui 2 vite: -4 + 2 = -2)",
                     a["guadagno"] == -2 and b["guadagno"] == -3))
        casi.append(("i filtri delle decisioni: turno 2 tiene tutte e due, terre stappate 2+ l'attacco, «hai bloccato: No» il blocco; turno 5 o 2 (una delle due)",
                     scegli(dd, {"turno": "2"}) == [a, b] and scegli(dd, {"aperte": ["2+"]}) == [a] and scegli(dd, {"bloccato": ["No"]}) == [b]
                     and scegli(dd, {"turno": ["5", "2"]}) == [a, b] and scegli(dd, {}) == dd))
        casi.append(("negativa: turno 5 niente; due filtri insieme li vogliono tutti e due (terre 2+ e hai bloccato No: nessuna)",
                     scegli(dd, {"turno": ["5"]}) == [] and scegli(dd, {"aperte": ["2+"], "bloccato": ["No"]}) == []
                     and descrivi({"turno": ["3", "4"]}, "blocco") == "turn 3 or 4"))
        pg, md = guadagni([x], ("attacco",), None, [x])
        casi.append(("il guadagno contro la media: una partita sola fa la media, lo scarto e' 0", md == {"attacco": -2.0} and pg == {"g1": 0.0}))
        ta = tabella([x], "attacco")
        casi.append(("la tabella degli attacchi: tutte, contro 2+ terre, con tutto; poche partite = indizio", ta[0]["n"] == 1 and ta[0]["perdi"] == 100.0
                     and next(t_ for t_ in ta if t_["nome"] == "Into 0 untapped lands")["n"] == 0 and ta[0]["poche"] and ta[0]["ids"] == {"g1"}))
        DA._MANA["g2"] = dict(momenti=[["comb", 3, 1, None, dict(att=[], blocchi=[])]])
        casi.append(("negativa: senza i momenti nessuna decisione; un combattimento senza attaccanti non conta",
                     per_partita(dict(partita="gx", seat=1, vinta=True, quando=q)) == [] and per_partita(dict(x, partita="g2")) == []))
    finally:
        DA._MANA.clear(); DA._MANA.update(vecchio)
    # i mulligan
    rr = [dict(quando=q, terre=3, partenza="Play", mulligan=0, vinta=True, scartate=[]),
          dict(quando=q, terre=1, partenza="Draw", mulligan=0, vinta=False, scartate=[]),
          dict(quando=q + datetime.timedelta(days=7), terre=2, partenza="Play", mulligan=1, vinta=True, scartate=[0]),
          dict(quando=q + datetime.timedelta(days=7), terre=6, partenza="Draw", mulligan=0, vinta=False, scartate=[])]
    m = mulligan(rr)
    casi.append(("i mulligan: tenute per terre e play/draw, una scartata a 0 terre, dopo il mulligan 1-0, rischiose (1 e 6 terre) 0-2, normali 1-0",
                 m["tenute"][3]["Play"] == (1, 1) and m["tenute"][1]["Draw"] == (1, 0) and m["scartate"] == {0: 1} and m["dopo"] == (1, 1)
                 and m["rischiose"] == (2, 0) and m["normali"] == (1, 1)))
    st = settimane(rr)
    casi.append(("settimana per settimana: due settimane, la seconda col mulligan al 50% e una rischiosa su una tenuta", len(st) == 2 and st[1]["mull"] == 50.0
                 and st[1]["rischiose"] == 100.0 and st[0]["rischiose"] == 50.0 and st[1]["wr_mull"] == 100.0))
    casi.append(("negativa: una mano a 2-4 terre non e' rischiosa", not _rischiosa(2) and not _rischiosa(4) and _rischiosa(1) and _rischiosa(5)))
    casi += prova_memo()
    casi += prova_costi()
    casi += prova_p()
    casi += prova_opzioni()
    for n, ok in casi:
        print(("ok    " if ok else "ROSSO ") + n)
    print(f"{sum(1 for _n, ok in casi if ok)}/{len(casi)}")
    return all(ok for _n, ok in casi)


if __name__ == "__main__":
    if "--prova" in sys.argv:
        sys.exit(0 if prova() else 1)
    R = [x for x in DA.righe() if x["tipo"] == "Constructed"]
    for tipo in ("attacco", "blocco"):
        print(tipo.upper())
        for c in tabella(R, tipo):
            print(f"  {c['nome']:42s} {c['n']:4d} dec · {c['partite']:3d} games · lost {c['perdi']}% · killed {c['uccidi']}% · trade {c['scambio']} · "
                  f"dmg {c['danno']} · trick {c['trucco']}% · wr {c['wr']}%")
