"""Le tre spine del motore dell'EV: i punti della partita attribuiti in modo esclusivo a una carta sola (la spina del mazzo) e a una linea sola (la spina del
giocatore), cosi' che anche li' la somma dei figli torni il padre (sessione Magic 24, 21 nov 2026).

Autore, 21 nov 2026: «anche il mazzo e il player dovrebbero essere altre due spine», poi «Sì, falla». La mappa: Note/Gerarchie_Valore.md, sezione 1.bis.

Da dove partono i punti. La spina del tempo (ev_partita.partita) taglia la partita in turni e fasi; il voto per fase (ev_partita.righe_fasi) taglia ogni
fase in righe: le scelte (lanciare, giocare una terra, attaccare, bloccare, il potere di un planeswalker) con le loro conseguenze dentro, e le righe senza
scelta (pescate, inneschi, risultati). Qui ogni riga va a una foglia sola delle due spine; quello che le righe non coprono (il cambio di chi tocca a
inizio turno, una fase senza log, gli arrotondamenti, la chiusura dopo l'ultima foto) va a una foglia «nessuno» dichiarata. Per costruzione:
    somma delle foglie = fine - inizio della partita (100 o 0 meno la P della mano tenuta).

La spina del mazzo (cosa): lato (Hero, Opponent, nessuno) > meccanica > tipo > carta.
  - una magia, una terra, un potere: la carta;
  - un attacco: diviso fra gli attaccanti per il danno che ognuno ha fatto nella fase (le righe «X dealt N to ...» incluse nella fase); senza danno, per
    la forza scritta nella riga; senza forza, in parti uguali (grado C: e' una Shapley con la funzione «danno», additiva, non quella della P);
  - un blocco: il bloccante;
  - una pescata: un'occasione della partita, foglia «partita» (dal 21 nov 2026: i tre livelli, Gerarchie_Valore 1.ter);
  - la meccanica e' la prima famiglia che la carta produce secondo le tabelle dello scout (ev_partita.tag_carta, in ordine alfabetico: una sola, grado C),
    «nessuna» senza.
La spina del giocatore (chi e perche'): chi (Hero, Opponent, nessuno) > stato (sotto pressione, tranquillo: psicologia.spot_partita) > linea > scelta.
  - le linee sono quelle di psicologia.py, lette sul turno dell'Hero e sul turno dell'Opponent che segue; una riga ne prende una sola, nell'ordine
    PRECEDENZA (la prima che vale per il suo tipo di riga), se no «nessuna linea»;
  - le non-azioni (no_corsa, aspetta, bluff) prendono i punti senza scelta della fase in cui non e' successo niente: il combattimento dell'Hero (no_corsa),
    l'ultima fase del suo turno (aspetta), il combattimento dell'Opponent che segue (bluff);
  - le righe dell'Opponent stanno sotto «Opponent» (sua scelta), quelle senza scelta sotto «nessuno».

Limiti dichiarati: le conseguenze vanno alla scelta che le precede nella fase (la regola di righe_fasi); i punti sono EV ottenuto (punti di P), non lo
scarto dal solito; solo le partite coi log (il replay azione per azione).

    py -I -X utf8 Companion/App/Schede/Performance/spine.py --misura [--limited]
    py -I -X utf8 Companion/App/Schede/Performance/spine.py --prova
"""
import os
import re
import sys
import json
import math
import collections

_casa = os.path.dirname(os.path.abspath(__file__))
while not os.path.isfile(os.path.join(_casa, "percorsi.py")):
    _casa = os.path.dirname(_casa)
if _casa not in sys.path:
    sys.path.insert(0, _casa)
import percorsi  # noqa: E402,F401
import dati_analizzatore as DA  # noqa: E402
import ev_partita as EV  # noqa: E402

PRECEDENZA = ("chump", "tappato", "trappola", "bluff", "no_corsa", "corsa", "aspetta_catena", "catena", "aspetta")
CANDIDATE = {               # il tipo di riga -> le linee che puo' prendere
    "lancio_mio": ("tappato", "aspetta_catena", "catena"),
    "terra_mio": ("tappato",),
    "attacco_mio": ("corsa",),
    "blocco_mio": ("chump",),
    "lancio_suo_turno": ("trappola",),
}
TIPI = ("Creature", "Planeswalker", "Battle", "Instant", "Sorcery", "Enchantment", "Artifact", "Land")
_ATT = re.compile(r"(?:, )?([^,(]+?) \((-?\d+)/(-?\d+)\)")
_DANNO = re.compile(r"^(.+?) dealt (\d+) to ")
NOTA = os.path.join(percorsi.ROOT, "Note", "Spine_Mazzo_Giocatore.md")


# ---------------------------------------------------------------- la carta di una riga
def _tipo_carta(nome):
    c = DA._carta(nome) or {}
    tp = (c.get("tipo") or "").split(" // ")[0].split()
    return next((t for t in TIPI if t in tp), "Other" if c else "?")


def _meccanica(nome):
    try:
        prod, _vuole = EV.tag_carta(nome)
    except Exception:       # noqa: BLE001
        return "nessuna"
    return sorted(prod)[0] if prod else "nessuna"


def foglia_carta(lato, nome):
    if lato in ("nessuno", "partita"):
        return (lato, "-", "-", nome)
    return (lato, _meccanica(nome), _tipo_carta(nome), nome)


def carte_riga(r, danni):
    """-> (lato, [(carta, peso)]) di una riga non inclusa. danni: {carta: danno fatto nella fase}."""
    t = r["testo"]
    m = re.match(r"(You|Opponent) (cast|played) (.+)$", t)
    if m:
        return ("Hero" if m.group(1) == "You" else "Opponent"), [(m.group(3).strip(), 1.0)]
    m = re.match(r"(You|Opponent) attacked with (.+)$", t)
    if m:
        lato = "Hero" if m.group(1) == "You" else "Opponent"
        att = [(n.strip(), max(0, int(p))) for n, p, _c in _ATT.findall(m.group(2))]
        if not att:
            return lato, [(m.group(2).strip(), 1.0)]
        nomi = [n for n, _p in att]
        w = [danni.get(n, 0) for n in nomi]
        if sum(w) <= 0:
            w = [p for _n, p in att]
        if sum(w) <= 0:
            w = [1.0] * len(att)
        s = float(sum(w))
        acc = collections.Counter()
        for n, x in zip(nomi, w):
            acc[n] += x / s
        return lato, list(acc.items())
    m = re.match(r"(.+?) blocked (.+)$", t)
    if m and r.get("mio") is not None:
        return ("Hero" if r["mio"] else "Opponent"), [(m.group(1).strip(), 1.0)]
    m = re.match(r"(.+?) (got|lost) \d+ loyalty", t)
    if m and r.get("mio") is not None:
        return ("Hero" if r["mio"] else "Opponent"), [(m.group(1).strip(), 1.0)]
    m = re.match(r"(You|Opponent) drew (.+)$", t)
    if m:           # la pescata e' un'occasione della partita, non un merito della carta (21 nov 2026, i tre livelli)
        return "partita", [("pescata Hero" if m.group(1) == "You" else "pescata Opponent", 1.0)]
    if r.get("mio") is not None:          # una scelta che non so leggere: resta del suo lato, senza carta
        return ("Hero" if r["mio"] else "Opponent"), [("scelta senza carta", 1.0)]
    return "nessuno", [("senza carta", 1.0)]


def tipo_riga(r):
    t = r["testo"]
    if r.get("tipo") == "risultato":
        return "pescata" if " drew " in t else "risultato"
    if " cast " in t:
        return "lancio"
    if " played " in t:
        return "terra"
    if " attacked with " in t:
        return "attacco"
    if " blocked " in t:
        return "blocco"
    return "potere"


# ---------------------------------------------------------------- una partita
def spine_partita(x, passi=None, spot=None):
    """-> dict(mazzo={foglia: punti}, giocatore={foglia: punti}, inizio, fine, totale, errore, pezzi) o None senza i dati. Le foglie sono tuple (vedi
    sopra). pezzi: [(turno, fase, foglia del giocatore, punti, testo della riga o None)] nell'ordine della partita, per chi somma solo fino a un momento
    (il segnapunti del replayer, 21 nov 2026); la fine ha turno None."""
    c = EV.partita(x)
    if c is None:
        return None
    passi = passi if passi is not None else DA.azioni_partita(x)
    v = EV.righe_fasi(x, passi) if passi else None
    if spot is None:
        import psicologia as PS
        spot = PS.spot_partita(x)
    sp = {s["t"]: s for s in spot}
    righe = collections.defaultdict(list)          # turno -> [fase delle righe]
    for fz in (v or {}).get("fasi") or []:
        righe[fz["t"]].append(fz)
    M, G = collections.Counter(), collections.Counter()
    pezzi = []
    dove = [None, None]         # il turno e la fase del pezzo che si sta contando

    def gg(k, ev, testo=None):
        G[k] += ev
        pezzi.append((dove[0], dove[1], k, ev, testo))

    def nessuno(motivo, ev):
        M[("nessuno", "-", "-", motivo)] += ev
        gg(("nessuno", "-", "nessuna scelta", motivo), ev)

    for z in c["turni"]:
        t, mio_turno = z["t"], z["mio"]
        t_spot = t if mio_turno else t - 1
        s = sp.get(t_spot)
        compo = (s or {}).get("compo") or set()
        compo_prima = (sp.get(t - 2) or {}).get("compo") or set() if mio_turno else set()
        stato = ("sotto pressione" if s["pressione"] else "tranquillo") if s else "?"
        fasi_ev = [ph for ph in z.get("fasi") or []]
        nomi_ev = [ph["f"] for ph in fasi_ev]
        # le fasi delle righe agganciate alle fasi della spina: stessa fase; una fase delle righe che la spina non ha va alla fase della spina prima
        ordine = ("main1", "comb", "main2")
        per_fase = collections.defaultdict(list)
        for fz in righe.get(t, []):
            if "turn" in nomi_ev:
                per_fase["turn"].append(fz)
                continue
            f = fz["f"]
            while f not in nomi_ev and f in ordine and ordine.index(f) > 0:
                f = ordine[ordine.index(f) - 1]
            per_fase[f if f in nomi_ev else (nomi_ev[-1] if nomi_ev else "turn")].append(fz)
        ultima_fase = nomi_ev[-1] if nomi_ev else None
        for ph in fasi_ev:
            ev = ph["ev"]
            dove[0], dove[1] = t, ph["f"]
            if ph["f"] == "inizio":
                # la posta del turno (21 nov 2026, il ritmo misurato: Note/Occasioni_Partita.md): la P che chi e' di turno perde se passa senza fare
                # niente; la riprende col gioco (Spearman -0,74 col gioco dell'Hero). Non predice il risultato da sola (AUC 0,41 / 0,50): non e' fortuna,
                # e' il valore della mossa che il tavolo gli da'. Va a chi ha la mossa, come base del suo gioco
                chi = "Hero" if mio_turno else "Opponent"
                M[(chi, "-", "-", "la mossa")] += ev
                gg((chi, stato if mio_turno else "-", "la mossa", "posta del turno"), ev)
                continue
            fzs = per_fase.get(ph["f"]) or []
            if not fzs:
                # una fase senza righe: una non-azione dell'Hero se c'e', se no nessuno
                lin = _non_azione(ph["f"], mio_turno, compo, ultima_fase)
                if lin:
                    gg(("Hero", stato, lin, "non-azione"), ev)
                    M[("nessuno", "-", "-", "non-azione")] += ev
                else:
                    nessuno("fase senza scelte" if v else "fase senza log", ev)
                continue
            usato = 0.0
            for fz in fzs:
                danni = collections.Counter()
                for r_ in fz["righe"]:
                    if r_["incluso"]:
                        m = _DANNO.match(r_["testo"])
                        if m:
                            danni[m.group(1).strip()] += int(m.group(2))
                for r_ in fz["righe"]:
                    if r_["incluso"]:
                        continue
                    e = r_["ev"]
                    usato += e
                    lato, pesi = carte_riga(r_, danni)
                    for nome, w in pesi:
                        M[foglia_carta(lato, nome)] += e * w
                    gg(_foglia_giocatore(r_, lato, mio_turno, fz["f"], stato, compo, compo_prima, ultima_fase), e, r_["testo"])
            resto = ev - usato
            lin = _non_azione(ph["f"], mio_turno, compo, ultima_fase)
            if lin and abs(resto) > 0:
                gg(("Hero", stato, lin, "non-azione"), resto)
                M[("nessuno", "-", "-", "non-azione")] += resto
            else:
                nessuno("resto della fase", resto)
    dove[0], dove[1] = None, "fine"
    nessuno("la fine", c["chiusura"])       # dall'ultima foto al risultato: il colpo finale o la concessione (dice il risultato da sola, AUC 0,98)
    tot = c["fine"] - c["inizio"]
    err = max(abs(sum(M.values()) - tot), abs(sum(G.values()) - tot))
    return dict(mazzo=dict(M), giocatore=dict(G), inizio=c["inizio"], fine=c["fine"], totale=tot, errore=err, pezzi=pezzi)


def _non_azione(f, mio_turno, compo, ultima_fase):
    """La linea di una non-azione che prende i punti senza scelta della fase f, o None."""
    if mio_turno and f == "comb" and "no_corsa" in compo:
        return "no_corsa"
    if mio_turno and f == ultima_fase and "aspetta" in compo:
        return "aspetta"
    if not mio_turno and f == "comb" and "bluff" in compo:
        return "bluff"
    return None


def _foglia_giocatore(r, lato, mio_turno, f, stato, compo, compo_prima, ultima_fase):
    tr = tipo_riga(r)
    if r.get("tipo") == "risultato":
        if tr == "pescata":
            return ("partita", "-", "occasione", "pescata Hero" if r["testo"].startswith("You") else "pescata Opponent")
        lin = _non_azione(f, mio_turno, compo, ultima_fase)
        if lin:
            return ("Hero", stato, lin, "non-azione")
        return ("nessuno", "-", "nessuna scelta", "risultato")
    if lato != "Hero":
        return ("Opponent", "-", "sua scelta", tr)
    if tr in ("lancio", "potere"):
        tipo = "lancio_mio" if mio_turno else "lancio_suo_turno"
    elif tr == "terra":
        tipo = "terra_mio"
    elif tr == "attacco":
        tipo = "attacco_mio"
    elif tr == "blocco":
        tipo = "blocco_mio"
    else:
        tipo = None
    cand = set(CANDIDATE.get(tipo, ()))
    if tipo == "lancio_suo_turno" and f != "comb":
        cand.discard("trappola")
    valide = set(compo) - {"aspetta_catena"}         # aspetta_catena si legge sul turno dell'attesa: la catena e' due turni dopo
    if "aspetta_catena" in compo_prima:
        valide.add("aspetta_catena")
    lin = next((L for L in PRECEDENZA if L in cand and L in valide), "nessuna linea")
    return ("Hero", stato, lin, tr)


# ---------------------------------------------------------------- le tre spine su tutte le partite
def misura(limited=False, log=print):
    import psicologia as PS
    r = [x for x in DA.righe() if x.get("seat") in (1, 2) and bool(x.get("tipo") == "Limited") == limited]
    M, G = collections.Counter(), collections.Counter()
    n, err_max, assoluto = 0, 0.0, 0.0
    per_carta = collections.defaultdict(lambda: [0.0, 0])         # carta dell'Hero -> [punti, partite]
    lin_n = collections.Counter()
    for i, x in enumerate(r):
        passi = DA.azioni_partita(x)
        if not passi:
            continue
        s = spine_partita(x, passi, PS.spot_partita(x))
        if s is None:
            continue
        n += 1
        err_max = max(err_max, s["errore"])
        for k, v in s["mazzo"].items():
            M[k] += v
            assoluto += abs(v)
        for k, v in s["giocatore"].items():
            G[k] += v
            lin_n[k[:3]] += 1
        for k, v in s["mazzo"].items():
            if k[0] == "Hero":
                per_carta[k[3]][0] += v
        for nome in {k[3] for k in s["mazzo"] if k[0] == "Hero"}:
            per_carta[nome][1] += 1
        if i % 100 == 0:
            log(f"  {i}/{len(r)} partite, {n} con le spine")
    # le quote assolute per lato e per chi
    def quota(D, livello):
        acc = collections.Counter()
        for k, v in D.items():
            acc[k[:livello]] += abs(v)
        tot = sum(acc.values()) or 1
        return {" > ".join(k): round(100 * v / tot, 1) for k, v in acc.most_common()}
    # il controllo coi meriti delle carte (ev_partita.carte): stessa direzione?
    try:
        base = [x for x in DA.righe() if x.get("seat") in (1, 2) and bool(x.get("tipo") == "Limited") == limited]
        cm = {c_["nome"]: c_["ev_meriti"] for c_ in EV.carte(base, base, quante=400, minimo=5) if not c_["poche"]}
    except Exception:       # noqa: BLE001
        cm = {}
    xs, ys = [], []
    for nome, (pt, k) in per_carta.items():
        if nome in cm and k >= 5:
            xs.append(pt / k); ys.append(cm[nome])
    rho = _spearman(xs, ys) if len(xs) >= 10 else None
    carte_top = sorted(((nome, round(pt / k, 2), k) for nome, (pt, k) in per_carta.items() if k >= 10), key=lambda z: -z[1])
    linee = collections.defaultdict(lambda: [0.0, 0])
    for k, v in G.items():
        linee[k[:3]][0] += v
    for k, c_ in lin_n.items():
        linee[k][1] += c_
    out = dict(tipo="limited" if limited else "costruito", partite=n, errore_max=round(err_max, 4),
               quota_mazzo=quota(M, 1), quota_giocatore=quota(G, 1), quota_linee=quota({k: v for k, v in G.items() if k[0] == "Hero"}, 3),
               meccaniche={" > ".join(k): round(v / max(n, 1), 2) for k, v in sorted(_somma(M, 2).items(), key=lambda z: -abs(z[1])) if k[0] == "Hero"},
               linee={" > ".join(k): dict(punti_partita=round(v[0] / max(n, 1), 2), foglie=v[1]) for k, v in
                      sorted(linee.items(), key=lambda z: -abs(z[1][0]))},
               carte_migliori=carte_top[:12], carte_peggiori=carte_top[-12:][::-1],
               spearman_meriti=None if rho is None else round(rho, 3), carte_confrontate=len(xs))
    f = os.path.join(_casa, "App", "Schede", "Performance", f"spine_{out['tipo']}.json")
    with open(f, "w", encoding="utf8") as fh:
        json.dump(out, fh, indent=1, ensure_ascii=False)
    log(f"  {out['tipo']}: {n} partite, errore massimo {out['errore_max']}, Spearman coi meriti {out['spearman_meriti']} su {len(xs)} carte")
    return out


def _somma(D, livello):
    acc = collections.Counter()
    for k, v in D.items():
        acc[k[:livello]] += v
    return acc


def _spearman(a, b):
    def rk(v):
        o = sorted(range(len(v)), key=lambda i: v[i])
        r_ = [0.0] * len(v)
        for i, j in enumerate(o):
            r_[j] = i
        return r_
    ra, rb = rk(a), rk(b)
    ma, mb = sum(ra) / len(ra), sum(rb) / len(rb)
    num = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    den = math.sqrt(sum((x - ma) ** 2 for x in ra) * sum((y - mb) ** 2 for y in rb))
    return num / den if den else 0.0


# ---------------------------------------------------------------- le prove
def prova():
    ok, tot = 0, 0

    def chk(nome, c_):
        nonlocal ok, tot
        tot += 1
        ok += bool(c_)
        print(("  ok  " if c_ else "  ROSSO ") + nome)
    # 1. un attacco diviso per il danno, poi per la forza
    lato, p = carte_riga(dict(testo="You attacked with Alfa (3/3), Beta (1/1)", tipo="mio_su", mio=True), {"Alfa": 3, "Beta": 1})
    d = dict(p)
    chk("attacco: diviso per il danno 3 a 1", lato == "Hero" and abs(d["Alfa"] - 0.75) < 1e-9 and abs(d["Beta"] - 0.25) < 1e-9)
    _l, p = carte_riga(dict(testo="Opponent attacked with Alfa (2/2), Beta (2/1)", tipo="suo_buono", mio=False), {})
    chk("attacco senza danno: diviso per la forza", abs(dict(p)["Alfa"] - 0.5) < 1e-9)
    # 2. negativa: le parti sommano sempre 1, anche con forza 0 e nomi uguali
    _l, p = carte_riga(dict(testo="You attacked with Wall (0/4), Wall (0/4)", tipo="mio_su", mio=True), {})
    chk("negativa: forza 0 e due copie, una foglia sola col peso 1", len(p) == 1 and abs(p[0][1] - 1.0) < 1e-9)
    # 3. il blocco va al bloccante, del lato di chi sceglie
    lato, p = carte_riga(dict(testo="Faerie blocked Ajani's Pridemate", tipo="suo_errore", mio=False), {})
    chk("blocco: il bloccante dell'Opponent", lato == "Opponent" and p == [("Faerie", 1.0)])
    lato, p = carte_riga(dict(testo="Opponent drew a card", tipo="risultato", mio=None), {})
    chk("la pescata e' un'occasione della partita", lato == "partita" and p[0][0] == "pescata Opponent")
    # 4. una linea sola: chump batte corsa, ma su un attacco vale solo corsa
    g = _foglia_giocatore(dict(testo="Faerie blocked X", tipo="mio_giu", mio=True), "Hero", False, "comb", "sotto pressione", {"chump", "corsa"}, set(), "main2")
    chk("blocco con chump e corsa nel turno: chump", g[2] == "chump")
    g = _foglia_giocatore(dict(testo="You attacked with A (2/2)", tipo="mio_su", mio=True), "Hero", True, "comb", "tranquillo", {"chump", "corsa"}, set(), "main2")
    chk("attacco con chump e corsa nel turno: corsa (il chump non e' un attacco)", g[2] == "corsa")
    g = _foglia_giocatore(dict(testo="You cast X", tipo="mio_su", mio=True), "Hero", False, "main1", "tranquillo", {"trappola"}, set(), "main2")
    chk("negativa: una magia nel suo turno fuori dal combattimento non e' trappola", g[2] == "nessuna linea")
    # 5. la conservazione su una partita vera (se ci sono i log)
    try:
        r = [x for x in DA.righe() if x.get("seat") in (1, 2)]
        fatte = 0
        for x in reversed(r):
            passi = DA.azioni_partita(x)
            s = spine_partita(x, passi) if passi else None
            if s:
                chk(f"conservazione su una partita vera: errore {s['errore']:.4f}", s["errore"] < 0.05)
                fatte += 1
                if fatte >= 2:
                    break
    except Exception as e:      # noqa: BLE001
        chk(f"conservazione su una partita vera: {e}", False)
    print(f"  {ok}/{tot}")
    return ok == tot


if __name__ == "__main__":
    if "--prova" in sys.argv:
        sys.exit(0 if prova() else 1)
    if "--misura" in sys.argv:
        misura(limited="--limited" in sys.argv)
