"""Il Leak Finder come lettore di EV atteso contro EV ottenuto (18 nov 2026, Autore: «il leak finder deve diventare un lettore di EV atteso vs ottenuto»,
«partiamo larghi: prima la partita come wr totale, poi i turni in cui si sono generati i punti vittoria, poi le fasi dei turni ... poi la giocata della
carta», «tutto in mega ordine tutto pulito tutto preciso»). La mappa intera: Note/Gerarchie_Valore.md.

Questo modulo fa i primi due livelli della spina, la PARTITA e i TURNI.

L'EV si misura in punti di probabilita' di vincere (DA.p_foto: il modello del suggeritore, tarato sui replay pubblici di 17Lands, CC BY 4.0; nel Constructed
un'estrapolazione, confronta i momenti fra loro), dal posto dell'Hero.

  PARTITA   parte dalla P della mano tenuta all'inizio del turno 1 e finisce a 100 (vinta) o 0 (persa).
  TURNI     ogni turno (dell'Hero o dell'Opponent) va dalla P a fine del turno prima alla P a fine del suo turno, con le foto di mana_aperto; l'ultimo
            turno, che non ha la foto di fine, finisce all'ultimo stato della partita.
  CHIUSURA  dall'ultimo stato al risultato: il salto della fine (letale, concessione, tempo). Sta a parte, cosi' una concessione non gonfia il turno in
            cui arriva.

I punti si conservano: la somma dei turni piu' la chiusura e' esattamente il risultato meno la partenza (`conserva`).

L'EV ATTESO di un turno e' quanto rende di solito un turno nello stesso spot: chi e' di turno, il giro (1-8, poi 9+) e la situazione all'inizio del turno (la
P in cinque fasce), sulle partite dello stesso tipo (Constructed o Limited). Con poche partite nello spot il valore si avvicina a quello del gradino sopra
(il giro senza la situazione, poi chi e' di turno): la media dello spot pesa n, quella del gradino K_GRADINO (`attese`, `atteso`). Accanto alla media un
valore alto ma ripetibile, il 75° percentile dello spot (mai il massimo, che e' fortuna).
Dal 20 nov 2026 (UpgradePlan01 passo 1, Autore: «ogni mazzo deve confrontarsi con se stesso») il solito viene solo dalle partite dello stesso mazzo
(DA.chiave_mazzo: il nome del mazzo, nel Limited la coppia di colori); sotto DA.MINIMO_MAZZO partite il mazzo non ha ancora un solito.

L'EV OTTENUTO di un turno meno il suo atteso e' lo SCARTO: negativo, il turno ha reso meno del solito; positivo, di piu'. Non e' un errore: un esito che
va male non dice che la scelta era sbagliata (Autore: «su 8 volte 5 volte e' sopravvissuto e in 4 di quelle partite abbiamo vinto»). Le scelte si
leggono ai livelli dopo (fasi, giocate, carte).
"""
import os, sys
_casa = os.path.dirname(os.path.abspath(__file__))
while not os.path.isfile(os.path.join(_casa, "percorsi.py")):
    _casa = os.path.dirname(_casa)
if _casa not in sys.path:
    sys.path.insert(0, _casa)
import percorsi  # noqa: E402,F401
import collections  # noqa: E402
import re  # noqa: E402
import dati_analizzatore as DA  # noqa: E402

GIRO_MAX = 8            # i giri 1-8 uno per uno, poi «9+»
FASCE_P = (20, 40, 60, 80)      # la situazione all'inizio del turno: P sotto 20, 20-40, 40-60, 60-80, sopra 80
K_GRADINO = 20          # quante partite «vale» il gradino sopra quando lo spot ne ha poche
MINIMO = 15             # sotto, un numero e' un indizio (grigio)
ALTO = 75               # il percentile del valore alto ma ripetibile


def fascia_giro(giro):
    return str(giro) if giro <= GIRO_MAX else f"{GIRO_MAX + 1}+"


def fascia_p(p):
    return sum(1 for s in FASCE_P if p >= s)


# Il conto di una partita non dipende dai filtri: si fa una volta finche' il dato della partita (DA._MANA) e' lo stesso oggetto, come in decisioni.
_MEMO = {}


def partita(x):
    """Il conto di una partita dal posto dell'Hero: dict(inizio, fine, chiusura, turni=[dict(t, giro, mio, p0, p1, ev, fase_p)]), o None senza le foto o
    senza sapere posto, chi comincia e il risultato. fine e' 100 o 0; ev = p1 - p0; chiusura = fine - p1 dell'ultimo turno."""
    d = DA._MANA.get(x.get("partita"))
    seat = x.get("seat")
    if not d or seat not in (1, 2) or x.get("vinta") is None or x.get("inizia") is None or not d.get("foto"):
        return None
    k = (x.get("partita"), seat, x.get("inizia"), x.get("mulligan"), x.get("vinta"))
    v = _MEMO.get(k)
    if v is None or v[0] is not d:
        v = _MEMO[k] = (d, _partita(x, d, seat))
    return v[1]


def _p_fine_turno(f, seat, t, att, x, pesca=0):
    """La P a fine del turno t di chi e' di turno (att): tocca all'altro, nel giro del turno dopo (come decisioni._delta_p). pesca: le carte che att deve
    ancora pescare in questo turno (pescata_extra), contate nella sua mano."""
    extra = (0, 0) if not pesca else ((pesca, 0) if att == seat else (0, pesca))
    return DA.p_foto(f, seat, att != seat, (t + 2) // 2, x.get("inizia"), x.get("mulligan"), x.get("tipo"), mano_extra=extra)


# La pescata del turno e il momento del dato (UpgradePlan01 passo 2, 20 nov 2026; la misura: Motore_EV/salti_p.py, Note/UpgradePlan01_Passo2.md). Il modello
# e' tarato su tavoli fotografati PRIMA del turno di chi gioca, cioe' prima della sua pescata. Letta «se il turno finisse qui», una foto presa prima della
# pescata ha una carta in meno di quelle che il dato conta (la P sale di 3-6 punti a ogni pescata, sempre); letta «tocca a chi gioca», una foto presa
# dopo la pescata ne ha una in piu'. Si corregge il solo numero di carte della mano di chi e' di turno. Chi comincia non pesca al suo primo turno.
PRIMA_PESCA = ("Game start", "Untap", "Upkeep", "-")


def pescata_extra(passo_n, t, lettura):
    """Le carte da aggiungere alla mano di chi e' di turno: lettura «fine» (se il turno finisse qui) +1 prima della pescata; «vista» (tocca a chi gioca)
    -1 dopo la pescata. Il turno 1 non ha pescata (lo dice il numero di Arena: t == 1 e' il primo turno di chi comincia)."""
    if t == 1:
        return 0
    prima = passo_n in PRIMA_PESCA
    if lettura == "fine":
        return 1 if prima else 0
    return 0 if prima else -1


FASI = ("main1", "comb", "main2")
NOMI_FASI = {"main1": "main phase 1", "comb": "combat", "main2": "main phase 2", "inizio": "the turn passing"}


def _p_nel_turno(f, seat, t, att, x):
    """La P di una foto presa durante il turno t di att: «se il turno finisse qui» (19 nov 2026, Autore: «guardando la scena in funzione del turno
    successivo»), la stessa lettura della foto di fine turno. Chi ha attaccato resta tappato fino al suo turno dopo e non blocca: fino al 18 nov la foto di
    meta' turno si leggeva come se toccasse ancora a lui, le sue creature tappate contavano come pronte e il suo combattimento valeva -37 punti per te
    con la partita gia' vinta."""
    return _p_fine_turno(f, seat, t, att, x)


def _fasi(t, att, p0, p1, confini, seat, x, f_prima=None):
    """Le fasi di un turno (il terzo livello della spina): la prima fase principale (con stap, mantenimento e pescata) fino alla prima riga del
    combattimento, il combattimento fino alla prima riga della seconda fase principale, la seconda fase principale fino alla fine del turno (col passo
    finale). Una fase che il log non ha (niente combattimento) si fonde con quella prima. La somma delle fasi e' il turno.
    Ogni confine si legge «se il turno finisse qui» (_p_nel_turno). Dal 19 nov 2026 il cambio di chi tocca sta in una voce sua, «inizio» (la foto di fine
    del turno prima letta come se anche questo turno fosse passato senza far niente, meno p0): non e' una scelta di nessuno, cosi' non finisce nella prima
    fase principale."""
    base = _p_fine_turno(f_prima, seat, t, att, x, pescata_extra("Upkeep", t, "fine")) if f_prima is not None else None
    punti = [("main1", base if base is not None else p0)]
    for k in ("comb", "m2"):
        f = confini.get((t, k))
        if f is None:
            continue
        p = _p_nel_turno(f, seat, t, att, x)
        if p is not None:
            punti.append(("comb" if k == "comb" else "main2", p))
    if len(punti) == 1:         # il log non ha i confini di questo turno: una fase sola, «turn», con un atteso suo (non e' una prima fase principale)
        punti = [("turn", p0)]
    elif base is not None:
        punti.insert(0, ("inizio", p0))
    out = []
    for i, (nome, pa) in enumerate(punti):
        pb = punti[i + 1][1] if i + 1 < len(punti) else p1
        out.append(dict(f=nome, p0=round(pa, 2), p1=round(pb, 2), ev=round(pb - pa, 2)))
    return out


def _partita(x, d, seat):
    inizio = DA.p_foto(d.get("mano0"), seat, bool(x["inizia"]), 1, x.get("inizia"), x.get("mulligan"), x.get("tipo")) if d.get("mano0") else None
    if inizio is None:
        return None
    fine = 100.0 if x["vinta"] else 0.0
    confini = {(c_[0], c_[2]): c_[3] for c_ in d.get("confini") or []}
    turni = []
    p = inizio
    f_prima = d.get("mano0")
    for t, att, f in d["foto"]:
        p1 = _p_fine_turno(f, seat, t, att, x)
        if p1 is None:
            return None
        turni.append(dict(t=t, giro=(t + 1) // 2, mio=att == seat, p0=round(p, 2), p1=round(p1, 2), ev=round(p1 - p, 2),
                          fasi=_fasi(t, att, p, p1, confini, seat, x, f_prima)))
        p, f_prima = p1, f
    u = d.get("ultima")
    if u and (not turni or u[0] > turni[-1]["t"]):       # l'ultimo turno non ha la foto di fine: finisce all'ultimo stato
        p1 = _p_fine_turno(u[2], seat, u[0], u[1], x)
        if p1 is not None:
            turni.append(dict(t=u[0], giro=(u[0] + 1) // 2, mio=u[1] == seat, p0=round(p, 2), p1=round(p1, 2), ev=round(p1 - p, 2),
                              fasi=_fasi(u[0], u[1], p, p1, confini, seat, x, f_prima)))
            p = p1
    for z in turni:
        z["fase_p"] = fascia_p(z["p0"])
        if z["fasi"]:       # gli arrotondamenti: l'ultima fase prende il resto, cosi' la somma delle fasi e' il turno al centesimo
            z["fasi"][-1]["ev"] = round(z["ev"] - sum(ph["ev"] for ph in z["fasi"][:-1]), 2)
    return dict(inizio=round(inizio, 2), fine=fine, chiusura=round(fine - p, 2), turni=turni)


def conserva(c):
    """Il controllo dell'incastro: la somma dei turni piu' la chiusura e' il risultato meno la partenza, e in ogni turno la somma delle fasi e' il turno
    (entro gli arrotondamenti)."""
    if c is None:
        return False
    if abs(sum(z["ev"] for z in c["turni"]) + c["chiusura"] - (c["fine"] - c["inizio"])) >= 0.05 * (len(c["turni"]) + 2):
        return False
    return all(abs(sum(ph["ev"] for ph in z.get("fasi") or []) - z["ev"]) < 0.02 for z in c["turni"] if z.get("fasi"))


def _chiavi(z, fase=None):
    """I gradini dello spot di un turno (o di una sua fase), dal piu' preciso al piu' largo."""
    g = fascia_giro(z["giro"])
    k = ((z["mio"], g, z["fase_p"]), (z["mio"], g), (z["mio"],))
    return k if fase is None else tuple(kk + (fase,) for kk in k)


def _percentile(v, q):
    s = sorted(v)
    if not s:
        return None
    i = (len(s) - 1) * q / 100
    a = int(i)
    return s[a] + (s[min(a + 1, len(s) - 1)] - s[a]) * (i - a)


def attese(base):
    """La tabella degli EV attesi dalle partite base (di solito tutte quelle del tipo): {gradino: dict(n, media, alto)}."""
    acc = collections.defaultdict(list)
    for x in base:
        c = partita(x)
        if c is None:
            continue
        for z in c["turni"]:
            for k in _chiavi(z):
                acc[k].append(z["ev"])
            for ph in z.get("fasi") or []:
                for k in _chiavi(z, ph["f"]):
                    acc[k].append(ph["ev"])
    return {k: dict(n=len(v), media=sum(v) / len(v), alto=_percentile(v, ALTO)) for k, v in acc.items()}


def atteso(tab, z, fase=None):
    """L'EV atteso del turno z (o della sua fase) dalla tabella: la media dello spot avvicinata al gradino sopra quando ha poche partite (pesi n e
    K_GRADINO). -> dict(media, alto, n (le partite dello spot), gradino (0 lo spot, 1 senza la situazione, 2 solo chi e' di turno)) o None."""
    ch = _chiavi(z, fase)
    livelli = [tab.get(k) for k in ch]
    if livelli[-1] is None:
        return None
    media, alto = livelli[-1]["media"], livelli[-1]["alto"]
    gradino = 2
    for i in (1, 0):
        L = livelli[i]
        if not L:
            continue
        w = L["n"] / (L["n"] + K_GRADINO)
        media = w * L["media"] + (1 - w) * media
        alto = w * L["alto"] + (1 - w) * alto
        if L["n"] >= MINIMO:
            gradino = i
    return dict(media=media, alto=alto, n=(livelli[0] or {}).get("n", 0), gradino=gradino)


def turni_con_scarto(righe_, base):
    """Ogni turno delle partite righe_ con l'atteso dalle partite base: [dict(partita, vinta, quando, t, giro, mio, p0, p1, ev, atteso, alto, scarto, n,
    gradino, base_n (le partite del suo mazzo che fanno il solito))], nell'ordine delle partite e dei turni. Il solito viene solo dalle partite base dello
    stesso mazzo (DA.chiave_mazzo, UpgradePlan01 passo 1); un mazzo con meno di DA.MINIMO_MAZZO partite non ha ancora un solito e i suoi turni non escono."""
    gruppi = DA.per_mazzo(base)
    tabelle = {}
    out = []
    for x in righe_:
        km = DA.chiave_mazzo(x)
        b = gruppi.get(km) or []
        if len(b) < DA.MINIMO_MAZZO:
            continue
        if km not in tabelle:
            tabelle[km] = attese(b)
        tab = tabelle[km]
        c = partita(x)
        if c is None:
            continue
        for z in c["turni"]:
            a = atteso(tab, z)
            if a is None:
                continue
            fasi = []
            for ph in z.get("fasi") or []:
                af = atteso(tab, z, ph["f"])
                if af is not None:
                    fasi.append(dict(ph, atteso=round(af["media"], 2), scarto=round(ph["ev"] - af["media"], 2), n=af["n"]))
            # l'atteso del turno e' la somma degli attesi delle sue fasi: cosi' lo scarto del turno e' la somma degli scarti delle fasi (l'incastro)
            media = sum(ph["atteso"] for ph in fasi) if fasi and len(fasi) == len(z.get("fasi") or []) else a["media"]
            out.append(dict(z, partita=x.get("partita"), vinta=x.get("vinta"), quando=x.get("quando"), atteso=round(media, 2), alto=round(a["alto"], 2),
                            scarto=round(z["ev"] - media, 2), n=a["n"], gradino=a["gradino"], fasi=fasi, base_n=len(b)))
    return out


def riepilogo(righe_, base):
    """Il quadro della situazione per la cartella EV:
      partite      quante hanno il conto, vinte;
      inizio, fine la P media di partenza e il risultato medio (il win rate);
      chiusura     il salto medio della fine;
      per_turno    per ogni (mio, giro): partite, EV ottenuto medio, atteso medio, scarto medio, alto medio, poche (sotto MINIMO);
      peggiori     i turni con lo scarto piu' negativo (al massimo 40);
      migliori     quelli con lo scarto piu' alto (al massimo 40)."""
    tt = turni_con_scarto(righe_, base)
    conti = [c for c in (partita(x) for x in righe_) if c is not None]
    g = collections.defaultdict(list)
    for z in tt:
        g[(z["mio"], fascia_giro(z["giro"]))].append(z)
    ordine_g = lambda s: int(s.rstrip("+"))
    per_turno = []
    for (mio, gg), zz in sorted(g.items(), key=lambda kv: (ordine_g(kv[0][1]), not kv[0][0])):
        n = len(zz)
        per_turno.append(dict(mio=mio, giro=gg, n=n, ev=sum(z["ev"] for z in zz) / n, atteso=sum(z["atteso"] for z in zz) / n,
                              scarto=sum(z["scarto"] for z in zz) / n, alto=sum(z["alto"] for z in zz) / n, totale=sum(z["scarto"] for z in zz), poche=n < MINIMO))
    return dict(partite=len(conti), vinte=sum(1 for c in conti if c["fine"] == 100.0),
                inizio=sum(c["inizio"] for c in conti) / len(conti) if conti else None,
                fine=sum(c["fine"] for c in conti) / len(conti) if conti else None,
                chiusura=sum(c["chiusura"] for c in conti) / len(conti) if conti else None,
                per_turno=per_turno, peggiori=sorted(tt, key=lambda z: z["scarto"])[:40], migliori=sorted(tt, key=lambda z: -z["scarto"])[:40], turni=len(tt))


_SCARTI = {}


# di quali turni e fasi si legge l'EV sul grafico (la tendina «EV of»)
EV_DI = (("all", "All turns"), ("hero", "Hero's turns"), ("opp", "Opponent's turns"), ("hero_main1", "Hero · main phase 1"),
         ("hero_comb", "Hero · combat (attack)"), ("hero_main2", "Hero · main phase 2"), ("opp_comb", "Opponent · combat (defense)"),
         ("opp_main", "Opponent · main phases"))


def _voci(z, ph=None):
    """In quali voci di EV_DI entra un turno (ph None) o una sua fase."""
    chi = "hero" if z["mio"] else "opp"
    if ph is None:
        return ("all", chi)
    if ph["f"] in ("turn", "inizio"):       # un turno senza i confini delle fasi, o il cambio di chi tocca: contano solo nei totali
        return ()
    if chi == "opp" and ph["f"] in ("main1", "main2"):
        return ("opp_main",)
    return (f"{chi}_{ph['f']}",)


def scarti(base):
    """L'EV di ogni partita contro l'atteso, per la metrica «EV vs expected» del grafico: {partita: dict(ev, atteso, scarto, per={voce di EV_DI: scarto})},
    dove ev e' la somma dei suoi turni (la chiusura no), atteso la somma degli attesi dei suoi turni (dalle partite base) e scarto la differenza; «per» lo
    stesso scarto diviso per chi e' di turno e per fase. Ricordato per l'insieme base."""
    k = tuple(sorted(str(x.get("partita")) for x in base))
    v = _SCARTI.get(k)
    if v is None:
        v = {}
        for z in turni_con_scarto(base, base):
            a = v.setdefault(z["partita"], dict(ev=0.0, atteso=0.0, scarto=0.0, per=collections.defaultdict(float)))
            a["ev"] += z["ev"]; a["atteso"] += z["atteso"]; a["scarto"] += z["scarto"]
            for vv in _voci(z):
                a["per"][vv] += z["scarto"]
            for ph in z["fasi"]:
                for vv in _voci(z, ph):
                    a["per"][vv] += ph["scarto"]
        if len(_SCARTI) > 8:
            _SCARTI.clear()
        _SCARTI[k] = v
    return v


def leva(x, t):
    """Quanto vale 1 vita dell'Opponent a fine del turno t di quella partita, in punti di P: la P con lui a una vita in meno meno la P vera. Dice quanto il
    turno era vicino al letale (i turni vicini al letale hanno leva alta). None senza la foto."""
    d = DA._MANA.get(x.get("partita")) or {}
    seat = x.get("seat")
    f, att = next(((f_, a_) for t_, a_, f_ in d.get("foto") or [] if t_ == t), (None, None))
    if f is None and d.get("ultima") and d["ultima"][0] == t:
        f, att = d["ultima"][2], d["ultima"][1]
    if f is None or seat not in (1, 2):
        return None
    v = list(f.get("v") or [20, 20])
    o = 2 - seat
    if v[o] is None or v[o] <= 1:
        return None
    meno = dict(f, v=[v[i] - 1 if i == o else v[i] for i in range(2)])
    p0, p1 = _p_fine_turno(f, seat, t, att, x), _p_fine_turno(meno, seat, t, att, x)
    return None if p0 is None or p1 is None else round(p1 - p0, 2)


# ---------------------------------------------------------------- i livelli sotto il turno: le carte e le giocate
#
# Le CARTE (il livello piu' micro, Note/Gerarchie_Valore.md sezione 7): ogni permanente non terra dell'Hero dal turno in cui compare in campo al turno in cui
# esce. Cosa ha fatto, dai momenti di mana_aperto (i combattimenti col prima e il dopo del danno, le magie dell'Opponent con cio' che hanno tolto):
MERITI = (("letale", "dealt the lethal damage"), ("danno", "hit the opponent unblocked"), ("vince", "won a combat (killed and survived)"),
          ("salva", "blocked and saved you from lethal"), ("scambio", "traded (killed and died)"), ("tiene", "blocked and survived"),
          ("rimbalza", "attacked, was blocked, nobody died"), ("rimossa", "drew a removal spell"), ("chump", "chump blocked"),
          ("assist", "helped a creature in combat (aura, equipment)"),
          ("perde", "attacked or blocked and died for nothing"))
NOMI_MERITI = dict(MERITI)
# Il valore di ogni evento NON e' scritto a mano: e' il CONTROFATTUALE col modello della P. Il tavolo vero dopo il gesto contro lo stesso tavolo senza
# quel gesto: l'attaccante non bloccato senza il suo danno; quello bloccato (o il bloccante) col suo combattimento disfatto (lui e chi ha ucciso tornano in
# campo); il bloccante che muore senza uccidere coi danni che avrebbe preso l'Hero; la carta rimossa ancora in campo e la magia ancora nella mano
# dell'Opponent. Il valore di un merito e' la media dei suoi eventi su tutte le partite del tipo: la gerarchia la dicono i dati. (Il primo giro del 18 nov
# usava la parte dello scarto della fase: «blocco che salva dal letale» veniva il merito peggiore, perche' misurava la brutta situazione, non il blocco.)


def _ids(f, lato):
    return {c_[5]: c_ for c_ in ((f or {}).get("c") or [[], []])[lato] or []}


def _senza(f, a, b, rimetti_a=(), rimetti_b=(), vite_a=0, vite_b=0, mano_b=0):
    """Una copia della foto f col gesto disfatto: le carte rimesse in campo (dalle foto di prima), le vite e la mano cambiate."""
    c = [list(lato or []) for lato in (f.get("c") or [[], []])]
    gia = [{c_[5] for c_ in c[0]}, {c_[5] for c_ in c[1]}]
    for lato, extra in ((a, rimetti_a), (b, rimetti_b)):
        for c_ in extra:
            if c_[5] not in gia[lato]:
                c[lato].append(c_)
    v = list(f.get("v") or [20, 20])
    n = list(f.get("n") or [0, 0])
    v[a] = (v[a] or 0) + vite_a
    v[b] = (v[b] or 0) + vite_b
    n[b] = (n[b] or 0) + mano_b
    return dict(f, c=c, v=v, n=n)


_TAG = {}


def tag_carta(nome):
    """(produce, vuole) di una carta dal suo testo (le tabelle PRODUCE/VUOLE dello scout, Motore/sinergie_tag.py, come la rete del Board); le terre niente."""
    if nome not in _TAG:
        try:
            import sinergie_tag as ST
        except Exception:       # noqa: BLE001 - senza lo scout niente sinergie
            return set(), set()
        c = DA._carta(nome) or {}
        tipo, testo = c.get("tipo") or "", c.get("testo") or ""
        _TAG[nome] = (set(), set()) if not testo or "Land" in tipo.split(" // ")[0] else ST.tags({"type": tipo, "oracle": testo})
    return _TAG[nome]


def in_sinergia(nome, altri):
    """Se la carta, entrando, ha in campo un partner: un altro permanente dell'Hero che produce quello che lei vuole o vuole quello che lei produce (grado C,
    dal testo). -> la lista delle famiglie in comune, vuota se e' entrata da sola."""
    p, v = tag_carta(nome)
    out = set()
    for o in altri:
        if o == nome:
            continue
        po, vo = tag_carta(o)
        out |= (p & vo) | (po & v)
    return sorted(out)


def eventi_carte(x):
    """I permanenti non terra dell'Hero in una partita: [dict(id, nome, pedina, creatura, entra, esce (None = fino alla fine), eventi=[(merito, turno, fase)])].
    entra ed esce sono turni di Arena; esce e' il primo turno a fine del quale la carta non c'e' piu'. Vuota senza i dati della partita."""
    d = DA._MANA.get(x.get("partita")) or {}
    seat = x.get("seat")
    if not d.get("foto") or seat not in (1, 2):
        return []
    a, b = seat - 1, 2 - seat
    fine = {t: f for t, _att, f in d["foto"]}
    u = d.get("ultima")
    if u and u[0] not in fine:
        fine[u[0]] = u[2]
    turni = sorted(fine)
    ultimo = turni[-1] if turni else None
    conf = {(c_[0], c_[2]): c_[3] for c_ in d.get("confini") or []}
    carte = {}
    for t in turni:
        for i, c_ in _ids(fine[t], a).items():
            nome = DA.nome_grp(c_[0]) if c_[0] not in DA.SENZA_FACCIA else None
            if not nome or DA.e_terra(nome):
                continue
            k = carte.setdefault(i, dict(id=i, nome=DA.nome_intero(nome), pedina=bool(c_[2]), creatura=c_[3] is not None, entra=t, esce=None, eventi=[],
                                         assist=[]))
            k["ultimo"] = t
    for t in turni:         # la sinergia all'entrata: i partner in campo a fine del turno in cui entra (le pedine contano: Healer's Hawk o una pedina)
        nomi_t = [DA.nome_intero(DA.nome_grp(c_[0]) or "") for c_ in (_ids(fine[t], a)).values() if c_[0] not in DA.SENZA_FACCIA]
        for k in carte.values():
            if k["entra"] == t:
                k["sinergia"] = in_sinergia(k["nome"], nomi_t)
    for k in carte.values():
        if k["ultimo"] != ultimo:
            k["esce"] = next((t for t in turni if t > k["ultimo"]), None)
    # i combattimenti
    momenti = d.get("momenti") or []
    combs = [m for m in momenti if m[0] == "comb" and len(m) > 4 and m[4] and m[4].get("att")]
    ultimo_mio = max((m[1] for m in combs if m[2] == seat), default=None)
    def p_di(f, t, att, nel_turno):
        v = f.get("v") or [20, 20]
        if v[a] is not None and v[a] <= 0:       # le vite a zero: la partita e' persa (o vinta), non una stima del modello
            return 0.0
        if v[b] is not None and v[b] <= 0:
            return 100.0
        return (_p_nel_turno if nel_turno else _p_fine_turno)(f, seat, t, att, x)

    def valore(dopo, cf, t, att, nel_turno):
        p1, p0 = p_di(dopo, t, att, nel_turno), p_di(cf, t, att, nel_turno)
        return None if p1 is None or p0 is None else round(p1 - p0, 2)

    for m in combs:
        t, att, prima, info = m[1], m[2], m[3], m[4]
        nel = (t, "m2") in conf
        dopo = conf.get((t, "m2")) or fine.get(t)
        if not prima or not dopo:
            continue
        miei_prima, suoi_prima = _ids(prima, a), _ids(prima, b)
        miei_dopo, suoi_dopo = _ids(dopo, a), _ids(dopo, b)
        blocchi = [(bi, list(aa or [])) for bi, aa in info.get("blocchi") or []]
        if att == seat:
            for ai, _tg in info["att"]:
                if ai not in carte:
                    continue
                bl = [bi for bi, aa in blocchi if ai in aa]
                vivo = ai in miei_dopo
                morti_suoi = [suoi_prima[bi] for bi in bl if bi not in suoi_dopo and bi in suoi_prima]
                if not bl:
                    mer = "letale" if x.get("vinta") and t == ultimo_mio else "danno"
                    pw = (miei_prima.get(ai) or [0, 0, 0, 0])[3] or 0
                    cf = _senza(dopo, a, b, vite_b=pw)          # senza il suo danno
                else:
                    mer = "vince" if vivo and morti_suoi else "scambio" if morti_suoi else "perde" if not vivo else "rimbalza"
                    cf = _senza(dopo, a, b, rimetti_a=[] if vivo or ai not in miei_prima else [miei_prima[ai]], rimetti_b=morti_suoi)
                carte[ai]["eventi"].append((mer, t, "comb", valore(dopo, cf, t, att, nel)))
            # il danno di piu' attaccanti non bloccati diviso alla Shapley (18 nov 2026, il memo: «la divisione del letale fra piu' attaccanti»): ognuno
            # prende la media di quello che aggiunge in tutti gli ordini possibili, e le parti sommano il valore dell'attacco intero; da solo, ognuno
            # valeva solo quello che aggiungeva per ultimo (tre attaccanti oltre il letale: quasi zero a testa). Fino a 6 attaccanti (64 tavoli)
            liberi = [ai for ai, _tg in info["att"] if ai in carte and not any(ai in aa for _bi, aa in blocchi)]
            if 2 <= len(liberi) <= 6:
                pw_ = {ai: (miei_prima.get(ai) or [0, 0, 0, 0])[3] or 0 for ai in liberi}
                v_s = {}
                for mask in range(1 << len(liberi)):
                    fuori = sum(pw_[ai] for j, ai in enumerate(liberi) if not mask >> j & 1)
                    v_s[mask] = p_di(_senza(dopo, a, b, vite_b=fuori), t, att, nel)
                if all(v is not None for v in v_s.values()):
                    import math as _m
                    n_ = len(liberi)
                    for j, ai in enumerate(liberi):
                        sh = 0.0
                        for mask in range(1 << n_):
                            if mask >> j & 1:
                                continue
                            k_ = bin(mask).count("1")
                            sh += _m.factorial(k_) * _m.factorial(n_ - k_ - 1) / _m.factorial(n_) * (v_s[mask | 1 << j] - v_s[mask])
                        ev_ = carte[ai]["eventi"]
                        for q, (mer, t_e, f_e, _v) in enumerate(ev_):
                            if t_e == t and f_e == "comb" and mer in ("danno", "letale"):
                                ev_[q] = (mer, t_e, f_e, round(sh, 2))
        else:
            vite = (prima.get("v") or [20, 20])[a] or 0
            forza = {i_: c_[3] or 0 for i_, c_ in suoi_prima.items()}
            tot = sum(forza.get(ai_, 0) for ai_, _tg in info["att"])
            for bi, aa in blocchi:
                if bi not in carte:
                    continue
                vivo = bi in miei_dopo
                morti_suoi = [suoi_prima[ai] for ai in aa if ai not in suoi_dopo and ai in suoi_prima]
                if vivo:
                    mer = "vince" if morti_suoi else "tiene"
                elif morti_suoi:
                    mer = "scambio"
                else:
                    # il chump che salva: senza quel blocco i danni dei suoi attaccanti (tutti, non solo quelli bloccati) arrivavano alle tue vite
                    mer = "salva" if tot >= vite else "chump"
                # senza il blocco: il bloccante resta, chi ha ucciso resta, e l'Hero prende i danni degli attaccanti che ha fermato
                cf = _senza(dopo, a, b, rimetti_a=[] if vivo or bi not in miei_prima else [miei_prima[bi]], rimetti_b=morti_suoi,
                            vite_a=-sum(forza.get(ai, 0) for ai in aa))
                carte[bi]["eventi"].append((mer, t, "comb", valore(dopo, cf, t, att, nel)))
    # l'assist di aure ed equipaggiamenti (18 nov 2026, il memo: «l'assist di aure ed equipaggiamenti»): una tua aura o un tuo equipaggiamento attaccato a
    # una tua creatura che in quel combattimento ha un merito che vale prende la sua parte, divisa in parti uguali fra la creatura e chi la porta (i punti
    # non si contano due volte); dalle annotazioni Attachment di mana_aperto (VERSIONE 25)
    for m in combs:
        porta = (m[4] or {}).get("porta") or {}
        for cid, sopra in porta.items():
            k = carte.get(cid)
            aiuti = [carte[s_] for s_ in sopra if s_ in carte and s_ != cid]
            if not k or not aiuti:
                continue
            for j, (mer, t_e, f_e, v_e) in enumerate(k["eventi"]):
                if t_e == m[1] and f_e == "comb" and v_e is not None and v_e > 0:
                    quota = round(v_e / (len(aiuti) + 1), 2)
                    k["eventi"][j] = (mer, t_e, f_e, quota)
                    for a_ in aiuti:
                        a_["eventi"].append(("assist", t_e, "comb", quota))
    # le rimozioni dell'Opponent: le sue magie (e abilita') che hanno tolto una tua carta dal campo; senza: la carta in campo e la magia nella sua mano
    for j, m in enumerate(momenti):
        if m[0] != "spell" or len(m) < 5 or not m[4] or m[4].get("chi") in (None, seat) or not isinstance(m[3], dict):
            continue
        dopo_m = next((m2 for m2 in momenti[j + 1:] if isinstance(m2[3], dict)), None)
        for i in DA.colpiti_di(m[4]) or []:
            if i not in carte:
                continue
            v_ = None
            c_prima = _ids(m[3], a).get(i)
            if dopo_m is not None and c_prima is not None:
                v_ = valore(dopo_m[3], _senza(dopo_m[3], a, b, rimetti_a=[c_prima], mano_b=0 if m[4].get("ab") else 1), dopo_m[1], dopo_m[2],
                            dopo_m[0] != "fine")
            carte[i]["eventi"].append(("rimossa", m[1], None, v_))
            nome_r = DA.nome_grp(m[4].get("g")) if m[4].get("g") not in DA.SENZA_FACCIA else None
            carte[i].setdefault("rimossa_da", []).append((m[1], DA.nome_intero(nome_r) if nome_r else "an ability"))
    # l'assist (Note/Gerarchie_Valore.md: «chi l'ha reso possibile prende l'assist»): una tua magia sulla tua creatura nel turno in cui quella creatura ha un
    # merito di combattimento (il trucco, il potenziamento) prende meta' del valore del merito; la creatura tiene l'altra meta' (i punti non si contano due volte)
    for m in momenti:
        if m[0] != "spell" or len(m) < 5 or not m[4] or m[4].get("chi") != seat:
            continue
        nome_m = DA.nome_grp(m[4].get("g")) if m[4].get("g") not in DA.SENZA_FACCIA else None
        if not nome_m:
            continue
        for i in m[4].get("bers") or []:
            k = carte.get(i)
            if not k:
                continue
            for j, (mer, t_e, f_e, v_e) in enumerate(k["eventi"]):
                if t_e == m[1] and f_e == "comb" and v_e is not None and v_e > 0:
                    k["eventi"][j] = (mer, t_e, f_e, round(v_e / 2, 2))
                    k["assist"].append((DA.nome_intero(nome_m), m[1], round(v_e / 2, 2)))
    out = list(carte.values())
    for k in out:
        k.pop("ultimo", None)
        k.setdefault("sinergia", [])
    return out


_MAPPE = {}


def _mappa_turni(base):
    """{(partita, turno): turno col suo scarto e le fasi} dalle partite base, ricordata per l'insieme."""
    k = tuple(sorted(str(x.get("partita")) for x in base))
    if k not in _MAPPE:
        if len(_MAPPE) > 8:
            _MAPPE.clear()
        _MAPPE[k] = {(z["partita"], z["t"]): z for z in turni_con_scarto(base, base)}
    return _MAPPE[k]


# ---------------------------------------------------------------- il voto EV di ogni fase, riga per riga (19 nov 2026)
# Autore: «i voti EV li diamo alla fine di ogni fase: un voto per ogni cosa accaduta piu' i pti guadagnati dagli errori di oppo, ogni riga di punteggio per
# cio' che e' accaduto in quella fase e ogni voto cliccabile per andare al punto esatto della fase in cui si e' generata quell'azione», poi la tabella delle
# etichette: tuo merito, suo errore (punti regalati), sua giocata buona, conseguenza senza scelta.
FASE_PASSO = {"Game start": "main1", "Upkeep": "main1", "Draw": "main1", "Main1": "main1", "BeginCombat": "comb", "DeclareAttack": "comb",
              "DeclareBlock": "comb", "FirstStrikeDamage": "comb", "CombatDamage": "comb", "EndCombat": "comb", "Main2": "main2", "End": "main2",
              "Cleanup": "main2"}
SOGLIA_RIGA = 1.0       # sotto un punto di P una scelta non e' ne' un merito ne' un regalo: grigia
ETICHETTE = {"mio_su": "your play", "mio_giu": "your play", "mio_pari": "your play", "suo_errore": "opponent's mistake",
             "suo_buono": "opponent's good play", "suo_pari": "opponent's play", "risultato": "result"}
_SALTA = ("paid mana for", "resolved", " on the stack", "turn ", "The game begins", "got 1 counter", "attached to", "chose ")
_RIGHE = {}


def _scelta(evs, att_mio):
    """Chi ha scelto in un passo del replay: (True l'Hero / False l'Opponent, testo) o None se il passo e' solo una conseguenza (danni, morti, pescate,
    inneschi). Scelte: lanciare una magia, giocare una terra, attaccare, bloccare (chi difende), il potere di un planeswalker."""
    for _mio, tx in evs:
        if re.match(r"(You|Opponent) (cast|played|attacked with) ", tx):
            return tx.startswith("You"), tx
        if " blocked " in tx:
            return not att_mio, tx
        if re.search(r" (got|lost) \d+ loyalty", tx):
            return att_mio, tx
    return None


def _testo_passo(evs):
    """La frase che dice il passo: la prima che non e' un dettaglio (mana pagato, risoluzione, inneschi in pila)."""
    for _m, tx in evs:
        if not any(k in tx for k in _SALTA):
            return tx
    return evs[0][1] if evs else ""


def _tipo(mio, v):
    if mio:
        return "mio_su" if v >= SOGLIA_RIGA else "mio_giu" if v <= -SOGLIA_RIGA else "mio_pari"
    return "suo_errore" if v >= SOGLIA_RIGA else "suo_buono" if v <= -SOGLIA_RIGA else "suo_pari"


def righe_fasi(x, passi, base=None):
    """Le righe del voto di ogni fase da un replay azione per azione (DA.azioni_partita). Ogni passo vale quanto cambia la probabilita' di vincere
    dell'Hero «se il turno finisse qui» (_p_nel_turno: le creature che hanno attaccato restano tappate, il letale sul tavolo conta); il cambio di chi tocca a
    inizio turno resta fuori (non e' una scelta). Le conseguenze (danni, morti, pescate, inneschi) vanno nella riga della scelta che le ha causate nella
    stessa fase; quelle prima di ogni scelta restano righe loro, grigie; il mana pagato va nella magia che segue.
    -> dict(fasi=[dict(chiave=(t, f), t, f, giro, mio, righe=[dict(i, testo, tipo, ev, incluso)], totale, atteso, scarto, n, primo, ultimo)],
            del_passo={indice del passo: chiave della sua fase}), o None senza le foto dei passi."""
    seat = x.get("seat")
    d = DA._MANA.get(x.get("partita")) or {}
    if not passi or seat not in (1, 2):
        return None
    k = (x.get("partita"), id(passi), id(d), bool(base))
    if k in _RIGHE:
        return _RIGHE[k]
    out, del_passo, cur, p_passo = [], {}, None, {}
    prec_f, prec_t, p_prec = d.get("mano0"), None, None
    in_sospeso = 0.0        # il mana pagato: va alla magia che segue
    for i, p_ in enumerate(passi):
        f_ = p_[1] or {}
        g_ = f_.get("_grezza")
        att = f_.get("_att")
        if g_ is None or att not in (1, 2):
            continue
        t = p_[2]
        fase = FASE_PASSO.get(p_[0].split(" · ")[-1], "main1")
        passo_n = p_[0].split(" · ")[-1]
        if t != prec_t:     # un turno nuovo: si parte dalla foto di prima letta come se anche questo turno fosse passato (il cambio di chi tocca fuori)
            p_prec = _p_fine_turno(prec_f, seat, t, att, x, pescata_extra("Upkeep", t, "fine")) if prec_f is not None else None
        p_ora = _p_fine_turno(g_, seat, t, att, x, pescata_extra(passo_n, t, "fine"))
        # la win chance di adesso (19 nov 2026, in testa al racconto): fino al danno del combattimento chi e' di turno ha ancora la mossa (la sua lettura), dal
        # danno in poi il turno sta finendo (la lettura di fine turno, con le creature tappate). La lettura «se il turno finisse qui» dei punti, a inizio
        # turno, sarebbe come se chi gioca passasse senza far niente (il tuo turno 3 al 10%)
        if fase == "main2" or passo_n in ("CombatDamage", "FirstStrikeDamage", "EndCombat"):
            p_vista = p_ora
        else:
            pv_ = pescata_extra(passo_n, t, "vista")
            p_vista = DA.p_foto(g_, seat, att == seat, (t + 1) // 2, x.get("inizia"), x.get("mulligan"), x.get("tipo"),
                                mano_extra=(0, 0) if not pv_ else ((pv_, 0) if att == seat else (0, pv_)))
        if p_vista is not None:
            p_passo[i] = p_vista
        prec_f, prec_t = g_, t
        if p_ora is None or p_prec is None:
            p_prec = p_ora
            continue
        dv, p_prec = p_ora - p_prec, p_ora
        ch = (t, fase)
        if cur is None or cur["chiave"] != ch:
            cur = dict(chiave=ch, t=t, f=fase, giro=(t + 1) // 2, mio=att == seat, righe=[], primo=i, ultimo=i, resto=0.0)
            out.append(cur)
            in_sospeso = 0.0
        cur["ultimo"] = i
        del_passo[i] = ch
        evs = p_[4] or []
        sc = _scelta(evs, att == seat)
        if sc is None and any("paid mana for" in tx for _m, tx in evs):
            in_sospeso += dv
            continue
        if sc is not None:
            cur["righe"].append(dict(i=i, testo=sc[1], tipo=_tipo(sc[0], 0.0), mio=sc[0], ev=dv + in_sospeso, incluso=False))
            in_sospeso = 0.0
            continue
        tx = _testo_passo(evs)
        utile = bool(tx) and not any(k_ in tx for k_ in _SALTA)
        scelta_prima = next((r_ for r_ in reversed(cur["righe"]) if r_["tipo"] != "risultato"), None)
        # nel combattimento il danno ai giocatori e la fine della partita vanno all'attacco, non al blocco che viene dopo (19 nov 2026, il collaudo: il blocco
        # del Mindseeker Oculus si prendeva -86,9 per un attacco che era letale comunque); le creature morte e il danno alle creature restano al blocco
        # (la partita che finisce nel passo va all'attacco anche col danno misto: Thorin che travolge quattro bloccanti e ti chiude)
        if fase == "comb" and scelta_prima is not None and " blocked " in scelta_prima["testo"] and (any("lost the game" in tx_ for _m, tx_ in evs) or (any(
                re.search(r"dealt \d+ to (you|the opponent)|lost \d+ life", tx_) for _m, tx_ in evs) and not any(
                re.search(r"dealt \d+ to (?!you|the opponent)|died", tx_) for _m, tx_ in evs))):
            scelta_prima = next((r_ for r_ in reversed(cur["righe"]) if r_["tipo"] != "risultato" and "attacked with" in r_["testo"]), scelta_prima)
        if scelta_prima is not None:        # una conseguenza: i suoi punti nella scelta che l'ha causata
            scelta_prima["ev"] += dv
            if utile:
                cur["righe"].append(dict(i=i, testo=tx, tipo="risultato", mio=None, ev=dv, incluso=True))
        elif utile or abs(dv) >= 0.05:
            cur["righe"].append(dict(i=i, testo=tx, tipo="risultato", mio=None, ev=dv, incluso=False))
        else:
            cur["resto"] += dv
    if in_sospeso and cur is not None:
        cur["resto"] += in_sospeso
    # le scelte si etichettano col valore finale (con le conseguenze); il totale, l'atteso e lo scarto della fase
    tt = {(z["t"], ph["f"]): ph for z in (_turni_di(base, x.get("partita")) if base else []) for ph in z.get("fasi") or []}
    for fz in out:
        for r_ in fz["righe"]:
            if r_["tipo"] != "risultato":
                r_["tipo"] = _tipo(r_["mio"], r_["ev"])
        fz["totale"] = sum(r_["ev"] for r_ in fz["righe"] if not r_["incluso"]) + fz["resto"]
        ph = tt.get(fz["chiave"])
        fz["atteso"] = ph.get("atteso") if ph else None
        fz["n"] = ph.get("n") if ph else 0
        fz["scarto"] = fz["totale"] - fz["atteso"] if fz["atteso"] is not None else None
    v = dict(fasi=out, del_passo=del_passo, p_passo=p_passo)
    if len(_RIGHE) > 20:
        _RIGHE.clear()
    _RIGHE[k] = v
    return v


_INDICI = {}


def _turni_di(base, partita):
    """I turni (col loro scarto) di una partita dalla mappa delle partite base: un indice per partita, ricordato con la mappa (la tabella delle partite
    lo chiede per ogni riga)."""
    mappa = _mappa_turni(base)
    ind = _INDICI.get(id(mappa))
    if ind is None or ind[0] is not mappa:
        per = collections.defaultdict(list)
        for (p, _t), z in mappa.items():
            per[p].append(z)
        for v in per.values():
            v.sort(key=lambda z: z["t"])
        if len(_INDICI) > 8:
            _INDICI.clear()
        ind = _INDICI[id(mappa)] = (mappa, per)
    return ind[1].get(partita, [])


_EVENTI = {}


def _eventi(x):
    """eventi_carte ricordato per partita finche' il suo dato di mana_aperto e' lo stesso (il controfattuale chiama il modello)."""
    d = DA._MANA.get(x.get("partita"))
    k = (x.get("partita"), x.get("seat"), x.get("vinta"), x.get("inizia"), x.get("mulligan"), x.get("tipo"))
    v = _EVENTI.get(k)
    if v is None or v[0] is not d:
        v = _EVENTI[k] = (d, eventi_carte(x))
    return v[1]


def valori_meriti(base):
    """Il valore di ogni merito misurato sulle partite base: {merito: dict(n, valore)}; valore = la media del controfattuale dei suoi eventi (punti di P col
    gesto contro senza). Ordinati dal valore piu' alto: e' la gerarchia dei meriti detta dai dati."""
    quote = collections.defaultdict(list)
    for x in base:
        for k in _eventi(x):
            for mer, _t, _f, v in k["eventi"]:
                if v is not None:
                    quote[mer].append(v)
    out = {m: dict(n=len(v), valore=sum(v) / len(v)) for m, v in quote.items() if v}
    return dict(sorted(out.items(), key=lambda kv: -kv[1]["valore"]))


def carte(r, base, quante=40, minimo=5):
    """Le carte dell'Hero nelle partite r col loro EV (le righe di Cards):
      in_campo   lo scarto dei turni in cui la carta e' stata in campo, dal turno in cui entra a quello in cui esce (il «plus-minus»), media per copia;
      meriti     la somma dei controfattuali dei suoi eventi (punti di P col gesto contro senza), media per copia, e quanti di ogni merito;
      sopravvive in quante partite e' rimasta in campo fino alla fine, e il win rate li' e nelle altre (Autore: «su 8 volte 5 volte e' sopravvissuta e
                 in 4 di quelle partite abbiamo vinto»).
    Le pedine no. Da `minimo` copie (sotto, grigie e in fondo). -> [dict(nome, n, vinte, perse, wr, quota, copie, in_campo, ev_meriti, conta, sopr, wr_sopr,
    n_non, wr_non, poche, filtro)]."""
    mappa = _mappa_turni(base)
    acc = {}
    for x in r:
        ev = _eventi(x)
        sopr_qui = collections.defaultdict(bool)
        for k in ev:
            if k["pedina"]:
                continue
            tt_ = _turni_di(base, x.get("partita"))
            fino = k["esce"] if k["esce"] is not None else (tt_[-1]["t"] if tt_ else k["entra"])
            pm = sum((mappa.get((x.get("partita"), t)) or {}).get("scarto", 0.0) for t in range(k["entra"], fino + 1))
            a = acc.setdefault(k["nome"], dict(nome=k["nome"], copie=0, in_campo=0.0, ev_meriti=0.0, conta=collections.Counter(), partite={},
                                               ctx=collections.defaultdict(list)))
            a["copie"] += 1
            a["in_campo"] += pm
            # i contesti: entrata con un partner in campo o da sola; lanciata subito o dopo aver aspettato in mano (x["tempi"]: giro del lancio, giri in mano)
            a["ctx"]["con" if k.get("sinergia") else "sola"].append(pm)
            attesa = ((x.get("tempi") or {}).get(k["nome"]) or (None, None))[1]
            if attesa is not None:
                a["ctx"]["subito" if attesa == 0 else "attesa"].append(pm)
            for mer, _t, _f, v_ in k["eventi"]:
                a["conta"][mer] += 1
                a["ev_meriti"] += v_ or 0.0
            sopr_qui[k["nome"]] |= k["esce"] is None
        # le partite della carta sono tutte quelle in cui l'hai lanciata, lo stesso insieme del suo filtro (il clic): anche quando non e' mai arrivata a fine
        # turno in campo (contrastata, morta nel turno stesso); sopravvive solo se una sua copia e' rimasta fino alla fine
        for nome in set(x.get("mie_lanciate") or []):
            if DA.e_terra(nome):
                continue
            a = acc.setdefault(nome, dict(nome=nome, copie=0, in_campo=0.0, ev_meriti=0.0, conta=collections.Counter(), partite={},
                                          ctx=collections.defaultdict(list)))
            a["partite"][x.get("partita")] = (bool(x.get("vinta")), bool(sopr_qui.get(nome)))
    tot = len(r) or 1
    out = []
    for a in acc.values():
        pp = a["partite"]
        n = len(pp)
        if not n or not a["copie"]:         # mai lanciata (messa in campo da un effetto), o mai rimasta in campo (un istantaneo): niente riga
            continue
        vinte = sum(1 for v, _s in pp.values() if v)
        sopr = [v for v, s_ in pp.values() if s_]
        non = [v for v, s_ in pp.values() if not s_]
        out.append(dict(nome=a["nome"], n=n, vinte=vinte, perse=n - vinte, wr=round(100 * vinte / n, 1) if n else 0.0, quota=round(100 * n / tot, 1),
                        copie=a["copie"], in_campo=round(a["in_campo"] / a["copie"], 2) if a["copie"] else 0.0,
                        ev_meriti=round(a["ev_meriti"] / a["copie"], 2) if a["copie"] else 0.0, conta=dict(a["conta"]),
                        sopr=len(sopr), wr_sopr=round(100 * sum(sopr) / len(sopr)) if sopr else None,
                        n_non=len(non), wr_non=round(100 * sum(non) / len(non)) if non else None,
                        poche=a["copie"] < minimo, filtro=("lanciate", a["nome"]),
                        **{f"{k_}_ev": (round(sum(v_) / len(v_), 2) if v_ else None) for k_, v_ in
                           ((k2, a["ctx"].get(k2) or []) for k2 in ("con", "sola", "subito", "attesa"))},
                        **{f"{k_}_n": len(a["ctx"].get(k_) or []) for k_ in ("con", "sola", "subito", "attesa")}))
    out.sort(key=lambda c: (c["poche"], -c["in_campo"]))
    return out[:quante]


def _ev_lanci(x, con_turno=False):
    """Le giocate dell'Hero di una partita dalle foto dei lanci (mana_aperto VERSIONE 21): [(nome, ev)]. Una magia va dalla foto del lancio (in pila) alla
    foto dopo nello stesso turno (un altro lancio, un confine di fase, la fine del turno): la risposta dell'Opponent e' dentro. Una terra e' il controfattuale:
    la foto con la terra contro la stessa foto senza. [] senza i lanci. Con con_turno: [(turno, grpId, nome, ev)] (il voto per scopo, scopo.py)."""
    d = DA._MANA.get(x.get("partita")) or {}
    seat = x.get("seat")
    lanci = d.get("lanci")
    if seat not in (1, 2) or not lanci:
        return []
    a = seat - 1
    fine = {t: (att, f) for t, att, f in d.get("foto") or []}
    u = d.get("ultima")
    if u and u[0] not in fine:
        fine[u[0]] = (u[1], u[2])
    # le foto di ogni turno in ordine di stato: i lanci e i confini (che hanno lo stato in fondo, dalla VERSIONE 21)
    per_t = collections.defaultdict(list)
    for l_ in lanci:
        per_t[l_[0]].append((l_[5], l_[4]))
    for c_ in d.get("confini") or []:
        if len(c_) > 4:
            per_t[c_[0]].append((c_[4], c_[3]))
    for v in per_t.values():
        v.sort(key=lambda e: e[0])
    out = []
    for t, chi, cosa, g, f, sid in lanci:
        if chi != seat or g in DA.SENZA_FACCIA:
            continue
        nome = DA.nome_grp(g)
        if not nome or t not in fine:
            continue
        att = fine[t][0]
        p0 = _p_nel_turno(f, seat, t, att, x)
        if cosa == "terra":         # la terra: con contro senza (una copia di quella terra tolta dal tuo campo)
            lato = list(((f.get("c") or [[], []])[a]) or [])
            j = next((j for j in range(len(lato) - 1, -1, -1) if lato[j][0] == g), None)
            if j is None:
                continue
            c2 = [list(z) for z in (f.get("c") or [[], []])]
            c2[a] = lato[:j] + lato[j + 1:]
            p1, p0 = p0, _p_nel_turno(dict(f, c=c2), seat, t, att, x)
        else:
            dopo = next((ff for s_, ff in per_t[t] if s_ > sid), None)
            p1 = _p_nel_turno(dopo, seat, t, att, x) if dopo is not None else _p_fine_turno(fine[t][1], seat, t, att, x)
        if p0 is None or p1 is None:
            continue
        out.append((t, g, DA.nome_intero(nome), p1 - p0) if con_turno else (DA.nome_intero(nome), p1 - p0))
    return out


_GIOCATE = {}


def _giocate_partita(x):
    """Le giocate dell'Hero di una partita, [(nome, ev)]: dalle foto dei lanci (_ev_lanci) o, per le partite lette prima, dalle magie coi bersagli dei
    momenti. Ricordate per partita finche' il suo dato di mana_aperto e' lo stesso (18 nov 2026, Autore: «si puo' velocizzare l'apertura di cards?»: la riga
    EV AT CAST rifaceva il modello della P su ogni lancio a ogni disegno, 3,4 s)."""
    d = DA._MANA.get(x.get("partita")) or {}
    seat = x.get("seat")
    k = (x.get("partita"), seat, x.get("vinta"), x.get("inizia"), x.get("mulligan"), x.get("tipo"))
    v = _GIOCATE.get(k)
    if v is not None and v[0] is d and v[2] is d.get("lanci") and v[3] is d.get("momenti"):
        return v[1]
    out = []
    if seat in (1, 2):
        if d.get("lanci") is not None:
            out = list(_ev_lanci(x))
        else:
            mom = d.get("momenti") or []
            for i, m in enumerate(mom):
                if m[0] != "spell" or len(m) < 5 or not m[4] or m[4].get("chi") != seat or m[4].get("ab") or not isinstance(m[3], dict):
                    continue
                dopo = next((m2 for m2 in mom[i + 1:] if isinstance(m2[3], dict)), None)
                if dopo is None:
                    continue
                p0 = _p_nel_turno(m[3], seat, m[1], m[2], x)
                p1 = (_p_fine_turno if dopo[0] == "fine" else _p_nel_turno)(dopo[3], seat, dopo[1], dopo[2], x)
                nome = DA.nome_grp(m[4].get("g")) if m[4].get("g") not in DA.SENZA_FACCIA else None
                if p0 is None or p1 is None or not nome:
                    continue
                out.append((DA.nome_intero(nome), p1 - p0))
    _GIOCATE[k] = (d, out, d.get("lanci"), d.get("momenti"))
    return out


def giocate(r, base, quante=40, minimo=5):
    """Il livello delle giocate: ogni magia lanciata e ogni terra giocata dall'Hero (le foto dei lanci di mana_aperto; per le partite lette prima, le sole
    magie coi bersagli dai momenti), l'EV dal lancio al momento dopo, contro la stessa carta sulle partite base, avvicinata alle carte dello stesso tipo
    quando ha pochi lanci. L'atteso a gradini (18 nov 2026, il memo: «l'atteso dal mazzo e dall'archetipo»): per ogni lancio la stessa carta nello stesso
    mazzo contro lo stesso archetipo, avvicinata alla stessa carta nello stesso mazzo, poi alla carta in tutti i mazzi, poi alle carte dello stesso tipo,
    ogni gradino col peso n/(n+10). -> [dict(nome, n, ev, atteso, scarto, poche, assist, filtro)], dall'EV piu' alto."""
    partite_di = collections.defaultdict(dict)

    def dalle(rr, segna=False):
        out = collections.defaultdict(list)
        for x in rr:
            lanciate = set(x.get("mie_lanciate") or [])
            for nome, v in _giocate_partita(x):
                if nome not in lanciate:        # le terre (non sono magie lanciate) e le carte fuori dal filtro della riga non entrano
                    continue
                out[nome].append((v, x.get("mio"), x.get("suo")))
                if segna:
                    partite_di[nome][x.get("partita")] = bool(x.get("vinta"))
        return out
    qui, tutte = dalle(r, segna=True), dalle(base)
    # l'atteso a gradini: la stessa magia, avvicinata alla media di tutte le tue magie dello stesso tipo (istantaneo, stregoneria, altro) quando ha pochi lanci
    def tipo_di(n):
        t_ = (DA._carta(n) or {}).get("tipo") or ""
        return next((k for k in ("Land", "Creature", "Instant", "Sorcery", "Planeswalker", "Artifact", "Enchantment") if k in t_), "Other")
    per_tipo, per_carta, per_mazzo, per_arch = (collections.defaultdict(list) for _ in range(4))
    for n_, v_ in tutte.items():
        for v1, mz, ar in v_:
            per_tipo[tipo_di(n_)].append(v1)
            per_carta[n_].append(v1)
            per_mazzo[(n_, mz)].append(v1)
            per_arch[(n_, mz, ar)].append(v1)

    def atteso_lancio(n_, mz, ar):
        a_ = None
        for lst in (per_tipo.get(tipo_di(n_)), per_carta.get(n_), per_mazzo.get((n_, mz)), per_arch.get((n_, mz, ar))):
            if not lst:
                continue
            m_ = sum(lst) / len(lst)
            w = len(lst) / (len(lst) + 10)
            a_ = m_ if a_ is None else w * m_ + (1 - w) * a_
        return a_
    assist = collections.defaultdict(float)
    for x in r:
        for k in _eventi(x):
            for nome_a, _t, v_a in k.get("assist") or []:
                assist[nome_a] += v_a
    out = []
    for nome, vv in qui.items():
        v = [z[0] for z in vv]
        media = sum(v) / len(v)
        attesi = [atteso_lancio(nome, mz, ar) for _v, mz, ar in vv]
        attesi = [a_ for a_ in attesi if a_ is not None]
        att = sum(attesi) / len(attesi) if attesi else media
        pp = partite_di[nome]
        vinte = sum(pp.values())
        out.append(dict(nome=nome, n=len(pp), vinte=vinte, perse=len(pp) - vinte, wr=round(100 * vinte / len(pp), 1) if pp else 0.0,
                        quota=round(100 * len(pp) / (len(r) or 1), 1), lanci=len(v), ev=round(media, 2), atteso=round(att, 2), scarto=round(media - att, 2),
                        poche=len(v) < minimo, assist=round(assist.get(nome, 0.0) / len(v), 2), filtro=("lanciate", nome)))
    out.sort(key=lambda c: (c["poche"], -c["ev"]))
    return out[:quante]


# ---------------------------------------------------------------- l'Opponent: le sue carte e il meta dai nostri dati
#
# Autore, 18 nov 2026: «potremmo comunque dedurre le carte e l'ev delle carte dai mazzi che incontriamo», «possiamo provare a ricostruire un meta anche
# se abbiamo poche carte». Lo stesso conto girato dal suo lato: la partita vista dal suo posto (specchio), la sua P e' lo specchio della tua, quindi il
# plus-minus delle sue carte e' lo scarto dei turni col segno cambiato. Si vede solo cio' che arriva in campo: e' deduttivo, una traccia.


def specchio(x):
    """La riga di una partita vista dal posto dell'Opponent: posto, risultato, chi comincia girati; le sue magie lanciate al posto delle tue."""
    if x.get("seat") not in (1, 2):
        return dict(x)
    return dict(x, seat=3 - x["seat"], vinta=None if x.get("vinta") is None else not x["vinta"],
                inizia=None if x.get("inizia") is None else not x["inizia"], mie_lanciate=x.get("sue_lanciate") or [])


def carte_sue(r, base, quante=40, minimo=5):
    """Le carte dell'Opponent nelle partite r col loro EV per lui (le righe di Cards, come `carte` dal suo lato): il plus-minus dei turni in cui erano in
    campo (per lui: lo scarto dell'Hero col segno cambiato), i controfattuali dei loro meriti, quante volte sopravvivono. Le partite di una carta sono
    quelle in cui l'ha lanciata (il filtro «Card the opponent cast»); win rate e record restano dell'Hero, come in tutta la cartella."""
    mappa = _mappa_turni(base)
    acc = {}
    for x in r:
        xs = specchio(x)
        ev = _eventi(xs)
        sopr_qui = collections.defaultdict(bool)
        tt_ = _turni_di(base, x.get("partita"))
        fino_p = tt_[-1]["t"] if tt_ else None
        for k in ev:
            if k["pedina"]:
                continue
            fino = k["esce"] if k["esce"] is not None else (fino_p if fino_p is not None else k["entra"])
            pm = -sum((mappa.get((x.get("partita"), t)) or {}).get("scarto", 0.0) for t in range(k["entra"], fino + 1))
            a = acc.setdefault(k["nome"], dict(nome=k["nome"], copie=0, in_campo=0.0, ev_meriti=0.0, conta=collections.Counter(), partite={}))
            a["copie"] += 1
            a["in_campo"] += pm
            for mer, _t, _f, v_ in k["eventi"]:
                a["conta"][mer] += 1
                a["ev_meriti"] += v_ or 0.0
            sopr_qui[k["nome"]] |= k["esce"] is None
        for nome in set(x.get("sue_lanciate") or []):
            if DA.e_terra(nome):
                continue
            a = acc.setdefault(nome, dict(nome=nome, copie=0, in_campo=0.0, ev_meriti=0.0, conta=collections.Counter(), partite={}))
            a["partite"][x.get("partita")] = (bool(x.get("vinta")), bool(sopr_qui.get(nome)))
    tot = len(r) or 1
    out = []
    for a in acc.values():
        pp = a["partite"]
        n = len(pp)
        if not n or not a["copie"]:
            continue
        vinte = sum(1 for v, _s in pp.values() if v)
        sopr = [v for v, s_ in pp.values() if s_]
        non = [v for v, s_ in pp.values() if not s_]
        out.append(dict(nome=a["nome"], n=n, vinte=vinte, perse=n - vinte, wr=round(100 * vinte / n, 1), quota=round(100 * n / tot, 1), copie=a["copie"],
                        in_campo=round(a["in_campo"] / a["copie"], 2), ev_meriti=round(a["ev_meriti"] / a["copie"], 2), conta=dict(a["conta"]),
                        sopr=len(sopr), wr_sopr=round(100 * sum(sopr) / len(sopr)) if sopr else None,
                        n_non=len(non), wr_non=round(100 * sum(non) / len(non)) if non else None,
                        poche=a["copie"] < minimo, sua=True, filtro=("sue_lanciate", a["nome"])))
    out.sort(key=lambda c: (c["poche"], -c["in_campo"]))
    return out[:quante]


def liste_composite(r, quante=8, minimo=3, base=None):
    """Il meta dai nostri dati: per ogni archetipo dell'Opponent (matchup_log, «suo») incontrato in almeno `minimo` partite, le carte che ha mostrato
    (lanciate o viste) con la frequenza, cioe' in quante delle partite contro quell'archetipo; dalle carte piu' frequenti. Da poche carte per partita si
    ricompone il mazzo. -> [dict(archetipo, partite, vinte, carte=[(nome, partite, quota)], ev={nome: (EV in campo per lui, copie)})], dagli archetipi piu'
    incontrati. Con `base` (le partite del tipo, per gli attesi dei turni) l'EV di ogni carta per l'Opponent DENTRO quell'archetipo (18 nov 2026, il memo:
    «l'EV a gradini carta -> archetipo»): la stessa carta puo' rendere diverso in due mazzi."""
    per = collections.defaultdict(list)
    for x in r:
        if x.get("suo"):
            per[x["suo"]].append(x)
    out = []
    for arch, xx in per.items():
        if len(xx) < minimo or arch == "Unknown":      # senza magie viste non c'e' un mazzo da ricomporre
            continue
        c = collections.Counter(n for x in xx for n in set((x.get("sue_lanciate") or []) + (x.get("sue_viste") or [])) if not DA.e_terra(n))
        ev = {}
        if base:
            ev = {c_["nome"]: (c_["in_campo"], c_["copie"]) for c_ in carte_sue(xx, base, quante=10 ** 6, minimo=1)}
        out.append(dict(archetipo=arch, partite=len(xx), vinte=sum(1 for x in xx if x.get("vinta")),
                        carte=[(n, q, round(100 * q / len(xx))) for n, q in c.most_common(40)], ev=ev))
    out.sort(key=lambda a: -a["partite"])
    return out[:quante]


MORTI_COMB = ("scambio", "perde", "chump", "salva")


def finestra_spot(x, filtri):
    """La finestra dello spot dei filtri in una partita: (t0, tw), dal primo turno di un filtro acceso alla fine del primo turno dell'Opponent dopo (o del
    suo ultimo turno fra gli spot); None senza uno spot o senza le foto."""
    d = DA._MANA.get(x.get("partita")) or {}
    seat = x.get("seat")
    sp = [z for z in DA.spot_filtri(x, filtri) if z.get("t")] if filtri else []
    if not sp or seat not in (1, 2) or not d.get("foto"):
        return None
    chi_di = {t: att for t, att, _f in d["foto"]}
    if d.get("ultima"):
        chi_di.setdefault(d["ultima"][0], d["ultima"][1])
    t0 = min(z["t"] for z in sp)
    suoi = sorted(t for t, att in chi_di.items() if att != seat and t > t0)
    if not suoi:
        return None
    tardi = [z["t"] for z in sp if chi_di.get(z["t"]) not in (None, seat) and z["t"] > t0]
    return t0, (max(tardi) if tardi else suoi[0])


def ev_spot_partita(x, filtri, base):
    """L'EV dello spot in una partita (la colonna SPOT EV della tabella sotto il grafico): lo scarto dei turni della finestra dello spot; senza uno spot, lo
    scarto di tutta la partita. -> (valore, e' uno spot?) o (None, False) senza il conto."""
    fs = finestra_spot(x, filtri)
    tt = _turni_di(base, x.get("partita"))
    if not tt:
        return None, False
    if fs is None:
        return round(sum(z["scarto"] for z in tt), 2), False
    return round(sum(z["scarto"] for z in tt if fs[0] <= z["t"] <= fs[1]), 2), True


def carte_ev_partita(x, base):
    """Le carte dell'Hero in una partita col loro EV in campo (il plus-minus dei turni in cui c'erano), dalla piu' alta: [(nome, ev)]. Le pedine no; una
    carta in piu' copie tiene la copia migliore."""
    mappa = _mappa_turni(base)
    tt = _turni_di(base, x.get("partita"))
    fino_p = tt[-1]["t"] if tt else None
    out = {}
    for k in _eventi(x):
        if k["pedina"]:
            continue
        fino = k["esce"] if k["esce"] is not None else (fino_p if fino_p is not None else k["entra"])
        pm = sum((mappa.get((x.get("partita"), t)) or {}).get("scarto", 0.0) for t in range(k["entra"], fino + 1))
        out[k["nome"]] = max(out.get(k["nome"], pm), pm)
    return sorted(((n, round(v, 2)) for n, v in out.items()), key=lambda t: -t[1])


def esito_spot(r, filtri, base):
    """Dallo spot dei filtri alla conseguenza (18 nov 2026, Autore: «scorporare quante volte esattamente la creatura sopravvive al t3 di oppo quindi
    dedurre le % che oppo abbia removal e poi se vogliamo nello specifico quale removal»). Per ogni partita: lo spot e' il primo turno in cui c'e' un filtro
    acceso (DA.spot_filtri); le creature seguite sono quelle dell'Hero entrate in quel turno (se no tutte quelle in campo a fine turno), le pedine no; la
    finestra arriva alla fine del primo turno dell'Opponent dopo lo spot (o del suo ultimo turno fra gli spot dei filtri). Per ogni creatura: sopravvive,
    rimossa da una sua magia o abilita' (quale), morta in combattimento, uscita altrimenti (sacrificata, rimbalzata da te, la partita finita). Accanto l'EV
    dei turni della finestra contro il solito. -> dict(partite, creature, esiti=Counter, rimozioni=Counter, ev, ev_n) o None senza spot."""
    mappa = _mappa_turni(base)
    esiti, rimozioni = collections.Counter(), collections.Counter()
    partite, ev_t = 0, []
    for x in r:
        fs = finestra_spot(x, filtri)
        if fs is None:
            continue
        t0, tw = fs
        ev = [k for k in _eventi(x) if k["creatura"] and not k["pedina"]]
        seguite = [k for k in ev if k["entra"] == t0] or [k for k in ev if k["entra"] <= t0 and (k["esce"] is None or k["esce"] > t0)]
        if not seguite:
            continue
        partite += 1
        for k in seguite:
            if k["esce"] is None or k["esce"] > tw:
                esiti["survived"] += 1
                continue
            rim = [n_ for t_, n_ in k.get("rimossa_da") or [] if t0 < t_ <= tw or t_ == k["esce"]]
            if rim:
                esiti["removed"] += 1
                rimozioni[rim[0]] += 1
            elif any(m_ in MORTI_COMB and t0 <= t_ <= tw for m_, t_, _f, _v in k["eventi"]):
                esiti["died in combat"] += 1
            else:
                esiti["left otherwise"] += 1
        tot = sum((mappa.get((x.get("partita"), t)) or {}).get("scarto", 0.0) for t in range(t0, tw + 1) if (x.get("partita"), t) in mappa)
        ev_t.append(tot)
    if not partite:
        return None
    return dict(partite=partite, creature=sum(esiti.values()), esiti=esiti, rimozioni=rimozioni,
                ev=round(sum(ev_t) / len(ev_t), 2) if ev_t else None, ev_n=len(ev_t))


def leak_ev(r, base):
    """I leak come spiegazioni dentro gli scarti (Note/Gerarchie_Valore.md: «i leak di oggi diventano spiegazioni»): per ogni leak legato a un turno, lo
    scarto medio dei turni in cui c'e' contro lo scarto medio degli altri turni dello stesso giocatore. {leak: dict(n, scarto, altri)}. I leak di tutta la
    partita (L7, L12, L13) non hanno un turno e non ci sono."""
    mappa = _mappa_turni(base)
    con, senza = collections.defaultdict(list), collections.defaultdict(list)
    for x in r:
        lk = x.get("leak") or {}
        turni = [z for (p, _t), z in mappa.items() if p == x.get("partita") and z["mio"]]
        for k, v in lk.items():
            if not isinstance(v, list):
                continue
            tt = set(v)
            for z in turni:
                (con if z["t"] in tt else senza)[k].append(z["scarto"])
    # il leaker intelligente, passo 2 (18 nov 2026, il memo: «ogni leak tarato sulle vittorie ... si tengono solo i leak che le partite confermano»): la
    # differenza fra i turni col leak e gli altri, col suo errore (Welch), dice se le tue partite lo confermano. «confermato» = i turni col leak rendono
    # meno degli altri oltre 2 errori; «contrario» = rendono di piu' oltre 2 errori (lo fai quando sei avanti, o non e' un errore); «non deciso» il resto,
    # e sotto MINIMO turni sempre «non deciso».
    return {k: verdetto_leak(v, senza[k]) for k, v in con.items() if v}


def costo_leak(r, base):
    """Il costo dei leak in EV (18 nov 2026, Autore: «la scheda leaks e' effettivamente ancora utile visto il nuovo modo di ragionare in ev?», poi «Si',
    tutte e tre»): per ogni leak di leak.ORDINE che c'e' nelle partite r, {leak: dict(livello, n, scarto, altri, diff, err, verdetto, costo, partite)}.
      livello «turno»: i turni col leak contro gli altri tuoi turni (leak_ev);
      livello «partita» (il mulligan, la concessione): lo scarto delle partite col leak contro quello delle altre (scarti).
    costo = quanti punti di probabilita' di vincere ti toglie in media a partita: la differenza per volta x le volte / le partite (positivo = ti costa)."""
    import leak as LK
    turno = leak_ev(r, base)
    sc = scarti(base)
    rr = [x for x in r if x.get("leak") and x.get("partita") in sc]
    tot = len(rr) or 1
    out = {}
    for k in LK.ORDINE:
        if k in turno:
            d = dict(turno[k], livello="turno")
        else:
            con = [sc[x["partita"]]["scarto"] for x in rr if LK.valore(x, k) == "Yes"]
            senza = [sc[x["partita"]]["scarto"] for x in rr if LK.valore(x, k) == "No"]
            if not con:
                continue
            d = dict(verdetto_leak(con, senza), livello="partita")
        d["partite"] = tot
        d["costo"] = None if d["diff"] is None else round(-d["diff"] * d["n"] / tot, 2)
        out[k] = d
    return out


def verdetto_leak(v, s_):
    """Gli scarti dei turni col leak (v) contro quelli degli altri turni (s_): dict(n, scarto, altri, diff, err, verdetto)."""
    def _var(w):
        m = sum(w) / len(w)
        return sum((a_ - m) ** 2 for a_ in w) / (len(w) - 1) if len(w) > 1 else 0.0
    d = dict(n=len(v), scarto=round(sum(v) / len(v), 2), altri=round(sum(s_) / len(s_), 2) if s_ else None, diff=None, err=None, verdetto="non deciso")
    if s_ and len(v) >= 2 and len(s_) >= 2:
        diff = sum(v) / len(v) - sum(s_) / len(s_)
        err = (_var(v) / len(v) + _var(s_) / len(s_)) ** 0.5
        d.update(diff=round(diff, 2), err=round(err, 2))
        if len(v) >= MINIMO and err > 0:
            d["verdetto"] = "confermato" if diff < -2 * err else "contrario" if diff > 2 * err else "non deciso"
    return d


# ---------------------------------------------------------------- prove

def prova_carte():
    """I meriti e il controfattuale su due partite costruite a mano (i nomi delle carte finti)."""
    casi = []
    cr = lambda i, pw=3, tg=3: [100 + i, 0, 0, pw, tg, i]
    vero = (DA.nome_grp, DA.e_terra, DA.nome_intero)
    vecchio = dict(DA._MANA)
    try:
        DA.nome_grp = lambda g: f"Card {g}"
        DA.e_terra = lambda n: False
        DA.nome_intero = lambda n: n
        DA._MANA.clear(); _MEMO.clear(); _EVENTI.clear(); _GIOCATE.clear(); _MAPPE.clear(); _SCARTI.clear()
        F = lambda mie, sue, v, n=(3, 3): dict(c=[mie, sue], v=list(v), n=list(n))
        # g1, Hero posto 1, vinta: al turno 3 attacca con la 1 (3/3) e la 2 (2/2), lui blocca la 2 con la sua 10 (2/2) e muoiono tutte e due (scambio), la
        # 1 passa (danno); al turno 4 lui toglie la carta 3 con una magia; al turno 5 la 1 da sola chiude (letale: l'ultimo attacco della partita vinta)
        a1, a3, a2, s10 = cr(1), cr(3, 1, 1), cr(2, 2, 2), cr(10, 2, 2)
        DA._MANA["g1"] = dict(
            mano0=F([], [], (20, 20), (7, 7)),
            foto=[[1, 1, F([a1], [], (20, 20))], [2, 2, F([a1, a3, a2], [s10], (20, 20))], [3, 1, F([a1, a3], [], (20, 17))],
                  [4, 2, F([a1], [], (20, 17))]],
            ultima=[5, 1, F([a1], [], (20, 0))],
            confini=[[3, 1, "comb", F([a1, a3, a2], [s10], (20, 20))], [3, 1, "m2", F([a1, a3], [], (20, 17))],
                     [5, 1, "comb", F([a1], [], (20, 3))], [5, 1, "m2", F([a1], [], (20, 0))]],
            momenti=[["spell", 3, 1, F([a1, a3, a2], [s10, cr(12)], (20, 20)), dict(g=500, chi=1, ab=False, bers=[12], colpiti=[12])],
                     ["comb", 3, 1, F([a1, a3, a2], [s10], (20, 20)), dict(att=[[1, 2], [2, 2]], blocchi=[[10, [2]]])],
                     ["spell", 4, 2, F([a1, a3], [], (20, 17)), dict(g=999, chi=2, ab=False, bers=[3], colpiti=[3])],
                     ["fine", 4, 2, F([a1], [], (20, 17)), None],
                     ["comb", 5, 1, F([a1], [], (20, 3)), dict(att=[[1, 2]], blocchi=[])]])
        x1 = dict(partita="g1", seat=1, inizia=True, mulligan=0, vinta=True,
                  mie_lanciate=["Card 101", "Card 102", "Card 103", "Card 500", "Card 600", "Card 700", "Card 702"])
        ev = {k["id"]: k for k in eventi_carte(x1)}
        mer = lambda i: [e[0] for e in ev[i]["eventi"]]
        casi.append(("i meriti: la carta 1 fa danno al turno 3 e il letale al 5; la 2 scambia; la 3 tira una rimozione", mer(1) == ["danno", "letale"]
                     and mer(2) == ["scambio"] and mer(3) == ["rimossa"]))
        casi.append(("entra ed esce: la 1 resta fino alla fine, la 2 esce al turno 3, la 3 entra al 2 ed esce al 4", ev[1]["esce"] is None
                     and ev[2]["esce"] == 3 and ev[3]["esce"] == 4 and ev[3]["entra"] == 2))
        val = lambda i, j=0: ev[i]["eventi"][j][3]
        # (20 nov 2026, il modello regolarizzato di UpgradePlan01: uno scambio alla pari, la tua 2/2 per la sua 2/2, vale circa zero nei due sensi; il
        # modello di prima lo dava un filo positivo, quello nuovo -0,7. Il danno e il letale restano chiaramente positivi)
        casi.append(("il controfattuale: il danno e il letale valgono piu' di zero, lo scambio alla pari circa zero, la rimozione subita meno di zero",
                     val(1) > 0 and abs(val(2)) < 2 and val(1, 1) > 0 and val(3) < 0))
        # g2, Hero posto 1 a 6 vite: lui attacca con 10 e 11 (3/3), la carta 1 (1/1) blocca la 10 e muore senza uccidere: senza quel blocco i 6 danni
        # arrivavano alle sue 6 vite -> salva, e il controfattuale e' una partita persa (P zero); al turno 4 lui attacca con la 10 e la carta 2 blocca a 12
        # vite, muore senza uccidere -> chump
        b1, b2, s10, s11 = cr(1, 1, 1), cr(2, 1, 1), cr(10), cr(11)
        DA._MANA["g2"] = dict(
            mano0=F([], [], (20, 20), (7, 7)),
            foto=[[1, 1, F([b1, b2], [], (20, 20))], [2, 2, F([b2], [s10, s11], (3, 20))], [3, 1, F([b2], [s10, s11], (12, 20))],
                  [4, 2, F([], [s10, s11], (12, 20))]],
            ultima=[5, 1, F([], [s10, s11], (0, 20))],
            confini=[[2, 2, "comb", F([b1, b2], [s10, s11], (6, 20))], [2, 2, "m2", F([b2], [s10, s11], (3, 20))],
                     [4, 2, "comb", F([b2], [s10, s11], (12, 20))], [4, 2, "m2", F([], [s10, s11], (12, 20))]],
            momenti=[["comb", 2, 2, F([b1, b2], [s10, s11], (6, 20)), dict(att=[[10, 1], [11, 1]], blocchi=[[1, [10]]])],
                     ["comb", 4, 2, F([b2], [s10, s11], (12, 20)), dict(att=[[10, 1]], blocchi=[[2, [10]]])]])
        x2 = dict(partita="g2", seat=1, inizia=True, mulligan=0, vinta=False, mie_lanciate=["Card 101", "Card 102"])
        ev2 = {k["id"]: k for k in eventi_carte(x2)}
        p_vera = _p_nel_turno(F([b2], [s10, s11], (3, 20)), 1, 2, 2, x2)
        casi.append(("il blocco che salva: senza, l'Hero era a 0 vite (P zero), quindi vale tutta la P che gli resta; il chump a 12 vite e' un chump",
                     ev2[1]["eventi"][0][0] == "salva" and abs(ev2[1]["eventi"][0][3] - round(p_vera, 2)) < 0.02 and ev2[2]["eventi"][0][0] == "chump"))
        casi.append(("negativa: il chump a 12 vite non salva dal letale e vale poco (sotto 5 punti)", abs(ev2[2]["eventi"][0][3]) < 5))
        vm = valori_meriti([x1, x2])
        casi.append(("la gerarchia dei meriti dai dati: ogni merito visto ha il suo valore, ordinati dal piu' alto",
                     set(vm) == {"danno", "letale", "scambio", "rimossa", "salva", "chump"}
                     and list(vm.values()) == sorted(vm.values(), key=lambda v: -v["valore"])))
        cc = {c["nome"]: c for c in carte([x1, x2], [x1, x2], minimo=1)}
        casi.append(("le carte: Card 101 (la 1) in 2 partite, sopravvive nella vinta; i suoi meriti contati", cc["Card 101"]["n"] == 2
                     and cc["Card 101"]["sopr"] == 1 and cc["Card 101"]["conta"].get("letale") == 1))
        casi.append(("negativa: senza le foto della partita niente eventi", eventi_carte(dict(x1, partita="zz")) == []))
        # Shapley: due attaccanti non bloccati da 3 contro 4 vite chiudono insieme; da soli nessuno dei due uccide, insieme si'; le parti sono uguali e
        # sommano il valore dell'attacco; negativa: col valore marginale di prima ognuno valeva quasi tutto (la somma superava il totale)
        a5, a6 = cr(5), cr(6)
        DA._MANA["g5"] = dict(mano0=F([], [], (20, 20), (7, 7)),
                              foto=[[1, 1, F([a5, a6], [], (20, 20))], [2, 2, F([a5, a6], [], (20, 4))]],
                              ultima=[3, 1, F([a5, a6], [], (20, -2))],
                              confini=[[3, 1, "comb", F([a5, a6], [], (20, 4))], [3, 1, "m2", F([a5, a6], [], (20, -2))]],
                              momenti=[["comb", 3, 1, F([a5, a6], [], (20, 4)), dict(att=[[5, 2], [6, 2]], blocchi=[])]])
        x5 = dict(partita="g5", seat=1, inizia=True, mulligan=0, vinta=True)
        e5 = {k["id"]: k for k in eventi_carte(x5)}
        v5, v6 = e5[5]["eventi"][0][3], e5[6]["eventi"][0][3]
        tot5 = 100.0 - _p_nel_turno(F([a5, a6], [], (20, 4)), 1, 3, 1, x5)
        casi.append(("Shapley: i due attaccanti si dividono il letale in parti uguali, e le parti sommano il valore dell'attacco",
                     abs(v5 - v6) < 0.02 and abs(v5 + v6 - tot5) < 0.1))
        # l'assist di un'aura (VERSIONE 25): la 4 (un'aura, non creatura) attaccata alla 1 che fa danno non bloccata: meta' del danno all'aura
        au = [104, 0, 0, None, None, 4]
        DA._MANA["g3"] = dict(mano0=F([], [], (20, 20), (7, 7)),
                              foto=[[1, 1, F([cr(1), au], [], (20, 20))], [2, 2, F([cr(1), au], [], (20, 20))], [3, 1, F([cr(1), au], [], (20, 17))]],
                              ultima=[4, 2, F([cr(1), au], [], (20, 17))],
                              confini=[[3, 1, "comb", F([cr(1), au], [], (20, 20))], [3, 1, "m2", F([cr(1), au], [], (20, 17))]],
                              momenti=[["comb", 3, 1, F([cr(1), au], [], (20, 20)), dict(att=[[1, 2]], blocchi=[], porta={1: [4]})]])
        x3 = dict(partita="g3", seat=1, inizia=True, mulligan=0, vinta=False)
        e3 = {k["id"]: k for k in eventi_carte(x3)}
        casi.append(("l'assist dell'aura: la creatura e l'aura si dividono il valore del danno in parti uguali", e3[4]["eventi"]
                     and e3[4]["eventi"][0][0] == "assist" and e3[1]["eventi"][0][0] == "danno" and abs(e3[4]["eventi"][0][3] - e3[1]["eventi"][0][3]) < 0.02))
        DA._MANA["g4"] = dict(DA._MANA["g3"], momenti=[["comb", 3, 1, F([cr(1), au], [], (20, 20)), dict(att=[[1, 2]], blocchi=[])]])
        _EVENTI.clear(); _GIOCATE.clear()
        casi.append(("negativa: senza l'aura attaccata niente assist, la creatura tiene tutto",
                     not [e for e in {k["id"]: k for k in eventi_carte(dict(x3, partita="g4"))}[4]["eventi"]]))
        # la sinergia all'entrata (dal testo): un partner che fa guadagnare vita accanto a chi la vuole; senza testo, nessuna
        vt_ = dict(_TAG)
        try:
            _TAG.clear(); _TAG["Card 101"] = ({"lifegain"}, set()); _TAG["Card 102"] = (set(), {"lifegain"}); _TAG["Card 103"] = (set(), set())
            casi.append(("la sinergia: la 102 che vuole vita accanto alla 101 che la fa e' in sinergia; negativa: la 103 senza testo no",
                         in_sinergia("Card 102", ["Card 101", "Card 103"]) == ["lifegain"] and in_sinergia("Card 103", ["Card 101"]) == []))
        finally:
            _TAG.clear(); _TAG.update(vt_)
        # l'assist: una tua magia (Card 600) sulla tua 1 nel turno 3, quando la 1 fa danno non bloccata: meta' del merito alla magia, meta' alla creatura
        DA._MANA["g1"]["momenti"].insert(1, ["spell", 3, 1, F([a1, a3, a2], [s10], (20, 20)), dict(g=600, chi=1, ab=False, bers=[1], colpiti=[])])
        _EVENTI.clear(); _GIOCATE.clear()
        ev_a = {k["id"]: k for k in eventi_carte(x1)}
        casi.append(("l'assist: la magia sulla 1 prende meta' del danno della 1, la 1 tiene l'altra meta'", ev_a[1]["assist"]
                     and ev_a[1]["assist"][0][0] == "Card 600" and abs(ev_a[1]["assist"][0][2] - ev_a[1]["eventi"][0][3]) < 0.02
                     and abs(ev_a[1]["eventi"][0][3] * 2 - val(1)) < 0.05))
        casi.append(("negativa: la magia dell'Hero sulla creatura dell'Opponent (Card 500 sulla 12) non e' un assist",
                     not any(a_[0] == "Card 500" for k in ev_a.values() for a_ in k["assist"])))
        gg = {g_["nome"]: g_ for g_ in giocate([x1, x2], [x1, x2], minimo=1)}
        casi.append(("le giocate: la magia dell'Hero che toglie la 12 sale; negativa: la magia dell'Opponent (Card 999) non e' una giocata dell'Hero",
                     "Card 500" in gg and gg["Card 500"]["ev"] > 0 and "Card 999" not in gg))
        casi.append(("l'atteso a gradini: con un lancio solo la Card 500 sta fra la sua media e quella delle tue magie dello stesso tipo (la 600)",
                     min(gg["Card 500"]["ev"], gg["Card 600"]["ev"]) <= gg["Card 500"]["atteso"] <= max(gg["Card 500"]["ev"], gg["Card 600"]["ev"])
                     and gg["Card 600"]["assist"] > 0))
        # le giocate dai lanci (mana_aperto VERSIONE 21): la magia dell'Hero al turno 3 fino alla foto dopo; negativa: il lancio dell'Opponent non c'e'
        DA._MANA["g1"]["lanci"] = [[3, 1, "magia", 700, F([a1, a3], [s10], (20, 20)), 10], [3, 2, "magia", 701, F([a1, a3, a2], [s10], (20, 20)), 13],
                                   [3, 1, "magia", 702, F([a1, a3, a2], [s10], (20, 20)), 12]]
        el_ = dict(_ev_lanci(x1))
        casi.append(("le giocate dai lanci: la 700 va fino al lancio dopo (la 702 col 2/2 in piu' in campo: sale), la 702 fino alla fine del turno; "
                     "negativa: la 701 dell'Opponent non e' una giocata dell'Hero", el_.get("Card 700", 0) > 0 and "Card 702" in el_ and "Card 701" not in el_))
        # dallo spot alla conseguenza: lo spot al turno 2 (dell'Opponent nella g1), la finestra fino al suo turno dopo (il 4): la 3 rimossa da Card 999, la 2
        # morta in combattimento al turno 3; negativa: senza uno spot niente
        vero_sp = DA.spot_filtri
        try:
            DA.spot_filtri = lambda x_, fl_: [dict(t=2)] if fl_ else []
            es = esito_spot([x1], {"finto": 1}, [x1, x2])
            casi.append(("lo spot: due creature seguite, una rimossa (Card 999) e una morta in combattimento, l'EV della finestra c'e'",
                         es is not None and es["creature"] == 2 and es["esiti"] == {"removed": 1, "died in combat": 1}
                         and dict(es["rimozioni"]) == {"Card 999": 1} and es["ev"] is not None))
            casi.append(("negativa: senza un filtro con un turno (nessuno spot) niente risposta", esito_spot([x1], {}, [x1, x2]) is None))
        finally:
            DA.spot_filtri = vero_sp
        # le carte dell'Opponent dal suo lato e i suoi mazzi ricomposti
        y1 = dict(x1, sue_lanciate=["Card 110"], suo="Rakdos")
        y2 = dict(x2, sue_lanciate=["Card 110", "Card 111"], suo="Rakdos")
        cs = {c_["nome"]: c_ for c_ in carte_sue([y1, y2], [y1, y2], minimo=1)}
        casi.append(("le sue carte: la sua 10 (Card 110) in tutte e due le partite, una copia per partita, dal suo lato; il filtro e' «Card the opponent cast»; "
                     "negativa: la tua Card 101 non c'e'", "Card 110" in cs and cs["Card 110"]["n"] == 2 and cs["Card 110"]["copie"] == 2
                     and cs["Card 110"]["sua"] and cs["Card 110"]["filtro"] == ("sue_lanciate", "Card 110") and "Card 101" not in cs))
        sp_ = specchio(y2)
        casi.append(("lo specchio: posto, risultato, chi comincia girati, le sue magie al posto delle tue", sp_["seat"] == 2 and sp_["vinta"] is True
                     and sp_["inizia"] is False and sp_["mie_lanciate"] == ["Card 110", "Card 111"]))
        lc = liste_composite([y1, y2, dict(y2, partita="g9", suo="Unknown")], minimo=2)
        casi.append(("il mazzo ricomposto: Rakdos in 2 partite, Card 110 nel 100%, Card 111 nel 50%; negativa: Unknown (senza magie viste) non si ricompone",
                     len(lc) == 1 and lc[0]["archetipo"] == "Rakdos" and lc[0]["carte"][0] == ("Card 110", 2, 100) and ("Card 111", 1, 50) in lc[0]["carte"]))
        lce = liste_composite([y1, y2], minimo=2, base=[y1, y2])
        casi.append(("l'EV dentro l'archetipo: Card 110 ha l'EV per lui nelle partite contro Rakdos, uguale a quello delle sue carte su quelle partite; "
                     "negativa: senza base niente EV", lce[0]["ev"].get("Card 110") == (cs["Card 110"]["in_campo"], cs["Card 110"]["copie"]) and lc[0]["ev"] == {}))
        # l'atteso dal mazzo (18 nov 2026): la stessa Card 700 in un altro mazzo rende di meno; l'atteso della 700 nel mazzo A sta fra la media di tutti e
        # quella del mazzo A (piu' vicino alla carta nello stesso mazzo); negativa: senza l'altro mazzo l'atteso e' la carta stessa
        DA._MANA["g1z"] = dict(DA._MANA["g1"], lanci=[[3, 1, "magia", 700, F([a1, a3, a2], [s10], (20, 20)), 10],
                                                       [3, 1, "magia", 702, F([a1, a3], [s10], (20, 20)), 12]])
        xa, xb = dict(x1, mio="A"), dict(x1, partita="g1z", mio="B")
        ga = {g_["nome"]: g_ for g_ in giocate([xa], [xa, xb], minimo=1)}
        gsolo = {g_["nome"]: g_ for g_ in giocate([xa], [xa], minimo=1)}
        casi.append(("l'atteso dal mazzo: la 700 nel mazzo A ha un atteso diverso da quello calcolato col solo mazzo A (l'altro mazzo pesa poco ma pesa)",
                     abs(ga["Card 700"]["atteso"] - gsolo["Card 700"]["atteso"]) > 0.01))
        lk = leak_ev([dict(x1, leak={"l1": [3], "l7": True})], [x1, x2])
        casi.append(("i leak dentro gli scarti: L1 al turno 3 ha il suo scarto; negativa: L7 (di tutta la partita) non ha un turno", "l1" in lk
                     and lk["l1"]["n"] == 1 and "l7" not in lk))
        alt = [(-1) ** i * 3.0 for i in range(40)]
        casi.append(("leaker passo 2: 20 turni col leak a -6 contro gli altri intorno a 0 e' confermato; 20 a +6 e' contrario; negative: 20 turni dentro il "
                     "rumore e 5 turni soli (sotto il minimo) restano non decisi",
                     verdetto_leak([-6.0 + (i % 3) for i in range(20)], alt)["verdetto"] == "confermato"
                     and verdetto_leak([6.0 + (i % 3) for i in range(20)], alt)["verdetto"] == "contrario"
                     and verdetto_leak([(-1) ** i * 3.0 for i in range(20)], alt)["verdetto"] == "non deciso"
                     and verdetto_leak([-6.0] * 4 + [-5.0], alt)["verdetto"] == "non deciso"))
    finally:
        DA.nome_grp, DA.e_terra, DA.nome_intero = vero
        DA._MANA.clear(); DA._MANA.update(vecchio)
        _MEMO.clear(); _EVENTI.clear(); _GIOCATE.clear(); _MAPPE.clear(); _SCARTI.clear()
    return casi


def prova_costo_leak():
    """Il costo dei leak in EV (18 nov 2026): un leak di turno e uno di tutta la partita, con leak_ev e scarti finti."""
    global leak_ev, scarti
    veri = leak_ev, scarti
    casi = []
    try:
        r = [dict(partita=f"c{i}", leak={"l2": [3], "l7": i < 10}) for i in range(40)]
        leak_ev = lambda r_, b_: {"l2": dict(n=40, scarto=-4.0, altri=1.0, diff=-5.0, err=1.0, verdetto="confermato")}
        scarti = lambda b_: {f"c{i}": dict(scarto=(-8.0 if i < 10 else 2.0) + (i % 3)) for i in range(40)}
        cl = costo_leak(r, r)
        casi.append(("il costo in EV: L2 di turno, 5 punti a volta x 40 volte / 40 partite = 5 a partita; L7 di partita, le 10 partite contro le 30",
                     cl["l2"]["livello"] == "turno" and cl["l2"]["costo"] == 5.0 and cl["l7"]["livello"] == "partita" and cl["l7"]["n"] == 10
                     and cl["l7"]["costo"] > 0))
        casi.append(("negativa: un leak che non c'e' nelle partite non ha costo", "l1" not in cl and "l12" not in cl or cl.get("l12", {}).get("n", 0) == 0))
    finally:
        leak_ev, scarti = veri
    return casi


def prova_righe_fasi():
    """Il voto per fase su una partita finta (19 nov 2026): le scelte e le loro conseguenze, chi prende i punti, i totali, la win chance."""
    casi = []
    cr = lambda i, pw=3, tap=0: [200 + i, tap, 0, pw, pw, i]
    f_ = lambda mie, sue, v: dict(c=[mie, sue], v=list(v), n=[3, 3])
    vecchio, vecchio_r = dict(DA._MANA), dict(_RIGHE)
    try:
        DA._MANA.clear(); _RIGHE.clear()
        DA._MANA["rf"] = dict(mano0=f_([], [], (20, 20)), foto=[])
        x = dict(partita="rf", seat=1, inizia=True, mulligan=0, vinta=False)
        passo = lambda nome, foto, t, att, evs: (nome, dict(_grezza=foto, _att=att), t, None, [(True, e_) for e_ in evs], [], [])
        f0 = f_([cr(1, 2)], [cr(2, 6)], (6, 20))
        ps = [passo("Opponent T1 · Main1", f0, 2, 2, ["Opponent played Forest"]),
              passo("Opponent T1 · DeclareAttack", f_([cr(1, 2)], [cr(2, 6, 1)], (6, 20)), 2, 2, ["Opponent attacked with Big (6/6)"]),
              passo("Opponent T1 · DeclareBlock", f_([cr(1, 2)], [cr(2, 6, 1)], (6, 20)), 2, 2, ["Small blocked Big"]),
              passo("Opponent T1 · CombatDamage", f_([], [cr(2, 6, 1)], (0, 20)), 2, 2, ["You lost the game at 0 life", "Big dealt 2 to Small", "Small died"])]
        v = righe_fasi(x, ps)
        comb = next((fz for fz in v["fasi"] if fz["f"] == "comb"), None)
        att = next((r_ for r_ in comb["righe"] if "attacked with" in r_["testo"]), None) if comb else None
        blo = next((r_ for r_ in comb["righe"] if " blocked " in r_["testo"]), None) if comb else None
        casi.append(("voto per fase: la fine della partita nel combattimento va all'attacco (sua giocata buona), non al blocco",
                     att is not None and blo is not None and att["tipo"] == "suo_buono" and att["ev"] < -5 and abs(blo["ev"]) < 1))
        casi.append(("voto per fase: le righe sommano il totale della fase; la conseguenza ha i punti nella riga sopra",
                     all(abs(sum(r_["ev"] for r_ in fz["righe"] if not r_["incluso"]) + fz["resto"] - fz["totale"]) < 0.01 for fz in v["fasi"])
                     and any(r_["incluso"] and r_["tipo"] == "risultato" for r_ in comb["righe"])))
        casi.append(("voto per fase: la win chance di ogni passo fra 0 e 100, la fine a 1 (hai perso)", all(0 <= q <= 100 for q in v["p_passo"].values())
                     and v["p_passo"][3] <= 5))
        casi.append(("negativa: le etichette dell'Opponent solo sulle sue scelte, le tue sulle tue",
                     all(r_["tipo"].startswith("suo") == (r_["mio"] is False) for fz in v["fasi"] for r_ in fz["righe"] if r_["tipo"] != "risultato")))
    finally:
        DA._MANA.clear(); DA._MANA.update(vecchio); _RIGHE.clear(); _RIGHE.update(vecchio_r)
    return casi


def prova():
    min_vero = DA.MINIMO_MAZZO
    DA.MINIMO_MAZZO = 1             # le partite finte sono poche: il minimo vero si prova a parte, piu' sotto
    casi = prova_carte() + prova_costo_leak() + prova_righe_fasi()
    cr = lambda i, pw=3: [100 + i, 0, 0, pw, pw, i]
    vuoto = dict(c=[[], []], v=[20, 20], n=[7, 7])
    f_mia = lambda k, v=(20, 20): dict(c=[[cr(i) for i in range(k)], []], v=list(v), n=[4, 4])
    f_sua = lambda k, v=(20, 20): dict(c=[[], [cr(10 + i) for i in range(k)]], v=list(v), n=[4, 4])
    vecchio = dict(DA._MANA)
    try:
        DA._MANA.clear()
        _MEMO.clear()
        # una partita vinta: l'Hero (posto 1) comincia, si sviluppa, attacca; l'ultimo turno (7) non ha la foto di fine, l'ultimo stato si'
        DA._MANA["v1"] = dict(mano0=vuoto, foto=[[1, 1, f_mia(1)], [2, 2, f_mia(1)], [3, 1, f_mia(2, (20, 17))], [4, 2, f_mia(2, (20, 17))],
                                                 [5, 1, f_mia(3, (20, 10))], [6, 2, f_mia(3, (20, 10))]],
                              ultima=[7, 1, f_mia(3, (20, 2))],
                              # il turno 5 con le sue fasi: dopo la prima fase principale 3 creature, dopo il combattimento lui da 17 a 10
                              confini=[[5, 1, "comb", f_mia(3, (20, 17))], [5, 1, "m2", f_mia(3, (20, 10))]])
        xv = dict(partita="v1", seat=1, inizia=True, mulligan=0, vinta=True)
        c = partita(xv)
        casi.append(("la partita vinta: 7 turni, l'ultimo dall'ultimo stato, la fine a 100", c is not None and len(c["turni"]) == 7 and c["fine"] == 100.0
                     and c["turni"][-1]["t"] == 7 and c["turni"][0]["mio"] and not c["turni"][1]["mio"]))
        casi.append(("i punti si conservano: turni + chiusura = fine - inizio", conserva(c)))
        casi.append(("i turni che fanno danno salgono: il turno 5 (lui da 17 a 10) ha EV positivo", c["turni"][4]["ev"] > 0))
        f5 = c["turni"][4]["fasi"]
        casi.append(("le fasi del turno 5: il cambio di chi tocca a parte (inizio), prima principale, combattimento, seconda; il combattimento (7 danni) "
                     "sale; la somma delle fasi e' il turno", [ph["f"] for ph in f5] == ["inizio", "main1", "comb", "main2"] and f5[2]["ev"] > 0
                     and abs(sum(ph["ev"] for ph in f5) - c["turni"][4]["ev"]) < 0.02))
        casi.append(("negativa: un turno senza confini nel log ha una fase sola, tutto il turno", [ph["f"] for ph in c["turni"][2]["fasi"]] == ["turn"]
                     and c["turni"][2]["fasi"][0]["ev"] == c["turni"][2]["ev"]))
        rotta_f = dict(c, turni=[dict(z, fasi=[dict(ph, ev=ph["ev"] + 3) for ph in z["fasi"]]) for z in c["turni"]])
        casi.append(("negativa: fasi con 3 punti in piu' non si conservano", not conserva(rotta_f)))
        # una persa: lui sviluppa, l'Hero va sotto
        DA._MANA["p1"] = dict(mano0=vuoto, foto=[[1, 1, vuoto], [2, 2, f_sua(1)], [3, 1, f_sua(1, (17, 20))], [4, 2, f_sua(2, (12, 20))]],
                              ultima=[6, 2, f_sua(3, (0, 20))])
        xp = dict(partita="p1", seat=1, inizia=True, mulligan=0, vinta=False)
        cp = partita(xp)
        casi.append(("la persa: fine a 0, i punti si conservano, il turno 4 di lui scende", cp["fine"] == 0.0 and conserva(cp) and cp["turni"][3]["ev"] < 0))
        casi.append(("dal posto 2 la stessa partita vinta e' l'opposto: le P si specchiano",
                     partita(dict(xv, seat=2, vinta=False, inizia=False))["turni"][4]["ev"] < 0))
        # l'atteso: lo spot di un turno con poche partite si avvicina al gradino sopra
        tab = attese([xv, xp])
        a = atteso(tab, c["turni"][4])
        casi.append(("l'atteso esiste e dice da quale gradino viene (poche partite: dal gradino largo)", a is not None and a["gradino"] == 2 and a["n"] >= 1))
        tt = turni_con_scarto([xv], [xv, xp])
        casi.append(("lo scarto e' ottenuto meno atteso, turno per turno, ed e' la somma degli scarti delle sue fasi",
                     tt and all(abs(z["scarto"] - (z["ev"] - z["atteso"])) < 0.02 for z in tt)
                     and all(abs(sum(ph["scarto"] for ph in z["fasi"]) - z["scarto"]) < 0.05 for z in tt)))
        # con la stessa partita come unica base ogni spot preciso ha una sola voce: atteso = ottenuto pesato verso il gradino largo
        r = riepilogo([xv, xp], [xv, xp])
        casi.append(("il riepilogo: 2 partite, 1 vinta, win rate 50, per giro e chi e' di turno, sotto MINIMO e' un indizio",
                     r["partite"] == 2 and r["vinte"] == 1 and r["fine"] == 50.0 and r["per_turno"] and all(p_["poche"] for p_ in r["per_turno"])
                     and r["peggiori"][0]["scarto"] <= r["migliori"][0]["scarto"]))
        # ogni mazzo si confronta con se stesso (UpgradePlan01 passo 1): con la persa in un altro mazzo, il solito della vinta viene solo da lei
        xp_b = dict(xp, mio="Altro mazzo")
        tt_solo = turni_con_scarto([xv], [xv])
        tt_due = turni_con_scarto([xv], [xv, xp_b])
        casi.append(("il solito per mazzo: la partita di un altro mazzo non cambia il solito (stessi scarti con e senza)",
                     tt_solo and [z["scarto"] for z in tt_solo] == [z["scarto"] for z in tt_due] and tt_due[0]["base_n"] == 1))
        casi.append(("e con la persa nello stesso mazzo il solito cambia", [z["scarto"] for z in turni_con_scarto([xv], [xv, xp])] != [z["scarto"] for z in tt_solo]))
        DA.MINIMO_MAZZO = 2
        casi.append(("negativa: un mazzo sotto il minimo non ha solito (nessun turno con lo scarto); due partite dello stesso mazzo si'",
                     turni_con_scarto([xv], [xv, xp_b]) == [] and len(turni_con_scarto([xv], [xv, xp])) > 0))
        DA.MINIMO_MAZZO = 1
        sc = scarti([xv, xp])
        casi.append(("la metrica del grafico: per partita la somma dei turni, ottenuto meno atteso", set(sc) == {"v1", "p1"}
                     and abs(sc["v1"]["ev"] - sum(z["ev"] for z in c["turni"])) < 0.05 and abs(sc["v1"]["scarto"] - (sc["v1"]["ev"] - sc["v1"]["atteso"])) < 0.05))
        per_ = sc["v1"]["per"]
        casi.append(("divisa per chi e' di turno: Hero piu' Opponent fa tutti i turni; il combattimento dell'Hero c'e'",
                     abs(per_["hero"] + per_["opp"] - per_["all"]) < 0.05 and "hero_comb" in per_))
        # (19 nov 2026, modello con le carte, Motore_EV: con lui a 2 vite e tre creature la partita e' gia' al 99% e una vita vale poco: la saturazione e'
        # giusta. La prova di prima, «al turno 7 vale di piu' che al turno 1», dipendeva dal modello di prima)
        casi.append(("la leva: una vita sua in meno alza sempre la P (turni 1, 5, 7) e mai oltre il 100",
                     all((leva(xv, t_) or 0) > 0 for t_ in (1, 5, 7)) and all((leva(xv, t_) or 0) < 50 for t_ in (1, 5, 7))))
        # le negative
        casi.append(("negativa: senza le foto, senza il risultato o senza sapere chi comincia niente conto",
                     partita(dict(partita="zz", seat=1, inizia=True, vinta=True)) is None and partita(dict(xv, vinta=None)) is None
                     and partita(dict(xv, inizia=None)) is None))
        rotta = dict(c, chiusura=c["chiusura"] + 5)
        casi.append(("negativa: un conto con 5 punti in piu' nella chiusura non si conserva", not conserva(rotta)))
        DA._MANA["u1"] = dict(mano0=vuoto, foto=[[1, 1, f_mia(2, (20, 1))]])
        casi.append(("negativa: la leva non si calcola con lui a 1 vita (non si scende a 0) ne' in un turno senza foto",
                     leva(dict(xv, partita="u1"), 1) is None and leva(xp, 99) is None))
        # la pescata del turno (UpgradePlan01 passo 2): +1 prima della pescata letta a fine turno, -1 dopo letta «tocca a chi gioca», niente al turno 1
        casi.append(("la pescata in arrivo: a fine turno +1 nel mantenimento, 0 in Main1; «tocca a chi gioca» 0 nel mantenimento, -1 in Main1",
                     pescata_extra("Upkeep", 5, "fine") == 1 and pescata_extra("Main1", 5, "fine") == 0 and pescata_extra("Upkeep", 5, "vista") == 0
                     and pescata_extra("Main1", 5, "vista") == -1))
        casi.append(("negativa: al turno 1 chi comincia non pesca, nessuna correzione", pescata_extra("Upkeep", 1, "fine") == 0
                     and pescata_extra("Main1", 1, "vista") == 0))
        f_p = f_mia(2)
        p0_ = DA.p_foto(f_p, 1, False, 3, True, 0)
        p1_ = DA.p_foto(f_p, 1, False, 3, True, 0, mano_extra=(1, 0))
        p2_ = DA.p_foto(f_p, 1, False, 3, True, 0, mano_extra=(0, 1))
        casi.append(("una carta in piu' nella tua mano alza la P, nella sua la abbassa", p0_ is not None and p1_ > p0_ and p2_ < p0_))
        casi.append(("le fasce della situazione: 10 far behind, 50 even, 95 far ahead", fascia_p(10) == 0 and fascia_p(50) == 2 and fascia_p(95) == 4
                     and fascia_giro(12) == "9+" and fascia_giro(3) == "3"))
    finally:
        DA._MANA.clear(); DA._MANA.update(vecchio)
        _MEMO.clear()
        DA.MINIMO_MAZZO = min_vero
    for n, ok in casi:
        print(("ok    " if ok else "ROSSO ") + n)
    print(f"{sum(1 for _n, ok in casi if ok)}/{len(casi)}")
    return all(ok for _n, ok in casi)


if __name__ == "__main__":
    if "--prova" in sys.argv:
        sys.exit(0 if prova() else 1)
    tipo = "Limited" if "--limited" in sys.argv else "Constructed"
    R = [x for x in DA.righe() if x["tipo"] == tipo]
    r = riepilogo(R, R)
    print(f"{tipo}: {r['partite']} partite col conto su {len(R)}, vinte {r['vinte']}, P media di partenza {r['inizio']:.1f}, chiusura media {r['chiusura']:+.1f}")
    rotte = sum(1 for x in R if partita(x) is not None and not conserva(partita(x)))
    print(f"conti che non si conservano: {rotte}")
    print(f"{'turno':>10s} {'n':>5s} {'ottenuto':>9s} {'atteso':>8s} {'scarto':>8s} {'alto':>7s}")
    for p_ in r["per_turno"]:
        print(f"{('Hero' if p_['mio'] else 'Opp') + ' ' + p_['giro']:>10s} {p_['n']:5d} {p_['ev']:+9.2f} {p_['atteso']:+8.2f} {p_['scarto']:+8.2f} {p_['alto']:+7.2f}")
