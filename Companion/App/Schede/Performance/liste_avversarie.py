"""Le liste avversarie e il loro ritratto, turno per turno (21 nov 2026; Autore: «aprissimo un secondo calcolo che elimina noi come giocatori e considera
solo avversario suo mazzo suo cimitero e suo board per ogni turno per tutte le partite che abbiamo vs un determinato mazzo», poi «i confronti devono essere
intelligenti e fatti vs mazzi specifici, potremmo avere incontrato due liste diverse di rakdos e quindi in base alle carte che scendono il confronto va
fatto con la lista che man mano emerge come definitiva, mentre se la lista è sconosciuta? anche il confronto deve aggiornarsi in maniera dinamica se alcune
liste evolvono cambiando alcune carte, ma il confronto va fatto sempre per mazzo», «vai»).

1. Le liste. Le partite Constructed contro lo stesso archetipo (matchup_log) si dividono in liste per le magie viste (le terre no): una partita entra nella
   lista con cui ha piu' magie in comune (Jaccard, almeno SOGLIA), se no apre una lista nuova. Una lista che cambia qualche carta resta la stessa lista
   in una versione nuova: ogni carta pesa di piu' quanto piu' e' recente (mezza vita MEZZA_VITA giorni dall'ultima partita della lista).
2. Il riconoscimento, carta dopo carta (Bayes, come il Deck HUD): la probabilita' di ogni lista dell'archetipo date le magie che ha mostrato fin li',
   piu' «la lista sconosciuta», che e' l'archetipo intero (e senza archetipo, i suoi colori). Il prior di una lista e' quante partite ha; quello della
   sconosciuta e' SCONOSCIUTA partite finte. Le probabilita' si stringono sulla lista definitiva man mano che scendono le carte.
3. Il ritratto: per ogni suo turno (1..TURNI) cosa ha fatto nelle partite di quella lista (lanciato una creatura, una rimozione, qualcosa; le terre
   lasciate aperte a fine turno; quando ha passato con 2+ aperte, se poi nel tuo turno ha lanciato qualcosa a velocita' istantanea, e cosa). Il ritratto
   di una partita in corso e' la media dei ritratti pesata dalle probabilita' delle liste in quel momento.
4. Il confronto (misura): per ogni partita, lasciata fuori, si prevede il suo turno n con la lista riconosciuta dalle carte viste PRIMA di quel turno,
   contro l'archetipo intero e contro tutti i mazzi; log-loss e Brier, per archetipo, con la negativa (le liste rimescolate dentro l'archetipo).

Limiti: noi non spariamo davvero (lui reagisce al nostro tavolo); la sua mano si vede solo quando gioca le carte, quindi «cosa aveva quando passava aperto»
e' un minimo; le partite per lista sono poche (Rakdos 22, quasi tutte le altre una).

    py -I -X utf8 Companion/App/Schede/Performance/liste_avversarie.py            (le liste e il confronto)
    py -I -X utf8 Companion/App/Schede/Performance/liste_avversarie.py --prova
"""
import os
import sys
import json
import math
import random
import collections

_casa = os.path.dirname(os.path.abspath(__file__))
while not os.path.isfile(os.path.join(_casa, "percorsi.py")):
    _casa = os.path.dirname(_casa)
if _casa not in sys.path:
    sys.path.insert(0, _casa)
import percorsi  # noqa: E402,F401
import dati_analizzatore as DA  # noqa: E402

SOGLIA = 0.35           # Jaccard delle magie viste per stare nella stessa lista (grado C: due Rakdos con 20 carte su 25 in comune si', con 12 no)
MEZZA_VITA = 30.0       # giorni: il peso di una carta della lista dimezza ogni MEZZA_VITA giorni prima dell'ultima partita della lista
SCONOSCIUTA = 2.0       # partite finte della «lista sconosciuta» (l'archetipo intero) nel prior
LISCIA = 0.03           # la probabilita' minima di vedere una carta in una lista che non l'ha mai mostrata
LISCIA_NUOVA = 0.15     # la stessa per la lista sconosciuta: una carta mai vista e' di una lista nuova piu' che di una nota (grado C)
TURNI = 8
M = 8.0                 # partite finte del livello sopra in ogni ritratto (la forza della scala a gradini: tarata dal confronto)
FAMIGLIE = ("Creature", "Removal", "Counterspell", "Card draw", "Combat trick", "Other spell")


# ---------------------------------------------------------------- una partita dal lato dell'avversario
_EV = {}


def eventi(x):
    """Il lato dell'avversario di una partita: dict(magie={suo turno n: [(nome, istantanea, ruolo)]}, nel_tuo={tuo turno dopo il suo n: [...]},
    aperte={suo turno n: terre stappate a fine turno}, ordine=[(t di Arena, nome)] le sue magie nell'ordine). {} senza i dati di mana_aperto."""
    k = x.get("partita")
    if k in _EV:
        return _EV[k]
    d = DA._MANA.get(k) or {}
    seat, inizia = x.get("seat"), x.get("inizia")
    if seat not in (1, 2) or inizia is None or "azioni" not in d:
        _EV[k] = {}
        return {}
    lui = 3 - seat
    suo_t = (lambda t: t % 2 == 0) if inizia else (lambda t: t % 2 == 1)
    import psicologia as PS
    out = dict(magie=collections.defaultdict(list), nel_tuo=collections.defaultdict(list), aperte={}, ordine=[])
    for t, s_, cosa, g, _tp in d["azioni"]:
        if s_ != lui or cosa != "magia":
            continue
        n = DA.nome_intero(DA.nome_grp(g) or "")
        if not n:
            continue
        voce = (n, PS.istantanea(g), DA.ruolo_magia(n))
        out["ordine"].append((t, n))
        if suo_t(t):
            out["magie"][(t + 1) // 2].append(voce)
        else:       # nel tuo turno: riferito al suo turno prima
            nn = (t - 1) // 2 if inizia else t // 2      # il tuo turno subito dopo il suo turno nn
            out["nel_tuo"][nn].append(voce)
    for t, chi, s, _n in d.get("fine") or []:
        if chi == lui and suo_t(t):
            out["aperte"][(t + 1) // 2] = s
    out["turni"] = max(out["aperte"]) if out["aperte"] else 0
    _EV[k] = out
    return out


def magie_viste(x):
    return {n for n in (x.get("sue_viste") or []) if not DA.e_terra(n)}


# ---------------------------------------------------------------- 1. le liste
def costruisci(righe, escludi=None):
    """{archetipo: [lista]}; lista = dict(id, archetipo, partite=[x], carte={nome: peso recente}, versioni, ultima). Le partite in ordine di tempo; escludi:
    l'id di una partita da lasciare fuori (il confronto)."""
    per = collections.defaultdict(list)
    for x in sorted(righe, key=lambda z: z["quando"]):
        if x.get("tipo") != "Constructed" or x.get("partita") == escludi:
            continue
        c = magie_viste(x)
        if len(c) < 2:
            continue
        a = x.get("suo") or "?"
        if a in ("Unknown", "?"):
            continue
        best, bj = None, 0.0
        for li in per[a]:
            u = set(li["carte_tutte"])
            j = len(c & u) / len(c | u)
            if j > bj:
                best, bj = li, j
        if best is not None and bj >= SOGLIA:
            nuove = c - set(best["carte_tutte"])
            if len(nuove) >= 2 and best["partite"]:
                best["versioni"] += 1
            best["partite"].append(x)
            for n in c:
                best["carte_tutte"][n] = x["quando"]
        else:
            per[a].append(dict(id=f"{a} #{len(per[a]) + 1}", archetipo=a, partite=[x], carte_tutte={n: x["quando"] for n in c}, versioni=1))
    for a, ls in per.items():
        for li in ls:
            ultima = li["partite"][-1]["quando"]
            li["ultima"] = ultima
            # il peso di ogni carta: le partite che l'hanno mostrata, ognuna pesata dalla sua eta' (la versione recente conta di piu')
            peso_p = {id(x): 0.5 ** (max(0.0, (ultima - x["quando"]).total_seconds() / 86400) / MEZZA_VITA) for x in li["partite"]}
            tot = sum(peso_p.values()) or 1.0
            pc = collections.Counter()
            for x in li["partite"]:
                for n in magie_viste(x):
                    pc[n] += peso_p[id(x)]
            li["carte"] = {n: v / tot for n, v in pc.items()}
            li["n"] = len(li["partite"])
    return dict(per)


def _arch_carte(ls):
    """Le carte dell'archetipo intero (la «lista sconosciuta»): la frequenza su tutte le sue partite."""
    pc, tot = collections.Counter(), 0
    for li in ls:
        for x in li["partite"]:
            tot += 1
            for n in magie_viste(x):
                pc[n] += 1
    return {n: v / tot for n, v in pc.items()} if tot else {}


# ---------------------------------------------------------------- 2. il riconoscimento
def riconosci(viste, archetipo, liste):
    """[(lista o None per la sconosciuta, probabilita')] dalle magie viste (nomi) fin li'. Senza liste dell'archetipo: [(None, 1.0)]."""
    ls = liste.get(archetipo) or []
    if not ls:
        return [(None, 1.0)]
    arch = _arch_carte(ls)
    logp = []
    for li in ls:
        lp = math.log(li["n"])
        for n in viste:
            lp += math.log(max(LISCIA, min(1 - LISCIA, li["carte"].get(n, 0.0))))
        logp.append((li, lp))
    lp_s = math.log(SCONOSCIUTA)
    for n in viste:
        lp_s += math.log(max(LISCIA_NUOVA, min(1 - LISCIA, arch.get(n, 0.0) * 0.5)))     # la sconosciuta: l'archetipo, meno sicura di ogni lista;
        # una carta mai vista e' piu' probabile in una lista nuova che in una nota
    logp.append((None, lp_s))
    m = max(v for _l, v in logp)
    ws = [(li, math.exp(v - m)) for li, v in logp]
    s = sum(w for _l, w in ws)
    return sorted(((li, w / s) for li, w in ws), key=lambda z: -z[1])


# ---------------------------------------------------------------- 3. il ritratto
def _ritratto_partite(xs):
    """Il ritratto da un gruppo di partite: {n: dict(n_partite, crea, rimoz, qualcosa, aperte (media), passa_aperto, spiegate, cosa=Counter)}."""
    out = {}
    for n in range(1, TURNI + 1):
        v = dict(partite=0, crea=0, rimoz=0, qualcosa=0, aperte=0.0, passa_aperto=0, spiegate=0, cosa=collections.Counter())
        for x in xs:
            e = eventi(x)
            if not e or e["turni"] < n:
                continue
            v["partite"] += 1
            m = e["magie"].get(n) or []
            v["crea"] += any(r == "Creature" for _n, _i, r in m)
            v["rimoz"] += any(r == "Removal" for _n, _i, r in m)
            v["qualcosa"] += bool(m)
            ap = e["aperte"].get(n)
            v["aperte"] += ap or 0
            if (ap or 0) >= 2:
                v["passa_aperto"] += 1
                nt = [z for z in e["nel_tuo"].get(n) or [] if z[1]]
                if nt:
                    v["spiegate"] += 1
                    for r in {z[2] for z in nt}:       # ogni tipo di risposta una volta per turno
                        v["cosa"][r] += 1
        if v["partite"]:
            v["aperte"] /= v["partite"]
        out[n] = v
    return out


def ritratto(pesi, base=None, m=None):
    """Il ritratto pesato dalle probabilita' delle liste: pesi = [(lista o insieme di partite, p)]. -> {n: dict(p_crea, p_rimoz, p_qualcosa, aperte,
    p_passa, p_spiegata, cosa {ruolo: quota}, partite)}. base: il ritratto del livello sopra (l'archetipo per una lista, tutti i mazzi per l'archetipo):
    ogni probabilita' parte da li' e se ne allontana quanto le sue partite permettono (m partite finte del livello sopra: la scala a gradini, 21 nov
    2026, il confronto: una lista con 3 partite da sola prevede peggio dell'archetipo e di tutti i mazzi)."""
    m = M if m is None else m
    acc = collections.defaultdict(lambda: collections.Counter())
    for xs, p in pesi:
        if p <= 0:
            continue
        r = _ritratto_partite(xs)
        for n in range(1, TURNI + 1):
            v = r.get(n) or dict(partite=0, crea=0, rimoz=0, qualcosa=0, aperte=0.0, passa_aperto=0, spiegate=0, cosa=collections.Counter())
            b_ = (base or {}).get(n)
            if not v["partite"] and not b_:
                continue
            k = m if b_ else 0
            a = acc[n]
            a["peso"] += p
            a["partite"] += p * v["partite"]
            for k_, kb in (("crea", "p_crea"), ("rimoz", "p_rimoz"), ("qualcosa", "p_qualcosa")):
                a[k_] += p * (v[k_] + k * (b_[kb] if b_ else 0)) / (v["partite"] + k)
            a["aperte"] += p * ((v["aperte"] * v["partite"] + k * (b_["aperte"] if b_ else 0)) / (v["partite"] + k))
            a["passa"] += p * ((v["passa_aperto"] + k * (b_["p_passa"] if b_ else 0)) / (v["partite"] + k))
            ks = m if (b_ and b_.get("p_spiegata") is not None) else 0
            if v["passa_aperto"] or ks:
                a["peso_sp"] += p
                a["spiegata"] += p * (v["spiegate"] + ks * (b_["p_spiegata"] if ks else 0)) / (v["passa_aperto"] + ks)
                base_c = (b_ or {}).get("cosa") or {}
                for r_ in set(v["cosa"]) | set(base_c):      # la quota di ogni tipo di risposta, agganciata come il resto
                    a["cosa:" + r_] += p * (v["cosa"].get(r_, 0) + ks * base_c.get(r_, 0.0)) / (v["passa_aperto"] + ks)
    out = {}
    for n, a in acc.items():
        w = a["peso"]
        out[n] = dict(p_crea=a["crea"] / w, p_rimoz=a["rimoz"] / w, p_qualcosa=a["qualcosa"] / w, aperte=a["aperte"] / w, p_passa=a["passa"] / w,
                      p_spiegata=(a["spiegata"] / a["peso_sp"]) if a["peso_sp"] else None,
                      cosa={k_[5:]: v / a["peso_sp"] for k_, v in a.items() if k_.startswith("cosa:")} if a["peso_sp"] else {},
                      partite=a["partite"] / w)
    return out


def pesi_partita(x, liste, fino_a=None, righe=None):
    """Le liste di una partita mentre va avanti: le magie che ha mostrato prima del suo turno fino_a (tutte se None) -> [(partite, p)] per ritratto()."""
    e = eventi(x)
    if fino_a is None:
        viste = magie_viste(x)
    else:
        t_n = 2 * fino_a if x.get("inizia") else 2 * fino_a - 1      # il suo turno fino_a in Arena
        viste = {n for t, n in (e or {}).get("ordine", []) if t < t_n and not DA.e_terra(n)}
    a = x.get("suo") or "?"
    ric = riconosci(viste, a, liste)
    tutte_arch = [y for li in liste.get(a) or [] for y in li["partite"]]
    out = []
    for li, p in ric:
        if li is None:
            out.append((tutte_arch or [y for y in (righe or []) if y.get("tipo") == "Constructed" and y.get("partita") != x.get("partita")], p))
        else:
            out.append((li["partite"], p))
    return out, ric


# ---------------------------------------------------------------- 4. il confronto: la lista batte l'archetipo?
def confronto(righe, log=print, seme=7):
    R = [x for x in righe if x.get("tipo") == "Constructed" and eventi(x)]
    rng = random.Random(seme)
    ll = collections.defaultdict(lambda: collections.Counter())
    per_arch = collections.defaultdict(lambda: collections.Counter())

    def lossb(p, y):
        p = min(0.98, max(0.02, p))
        return -math.log(p if y else 1 - p), (p - y) ** 2
    tutte_c = {}
    for x in R:
        a = x.get("suo") or "?"
        if a in ("Unknown", "?"):
            continue
        liste = costruisci(R, escludi=x["partita"])
        if not liste.get(a):
            continue
        e = eventi(x)
        arch_xs = [y for li in liste[a] for y in li["partite"]]
        tutte = [y for y in R if y["partita"] != x["partita"]]
        k_t = len(tutte)
        if k_t not in tutte_c:
            tutte_c.clear(); tutte_c[k_t] = ritratto([(tutte, 1.0)])
        rt_tutte = tutte_c[k_t]
        rt_arch = ritratto([(arch_xs, 1.0)], base=rt_tutte)
        # la negativa: le stesse liste con le partite rimescolate fra le liste dell'archetipo (stesse misure)
        mesc = [y for y in arch_xs]
        rng.shuffle(mesc)
        liste_m, i0 = dict(liste), 0
        nuove = []
        for li in liste[a]:
            nuove.append(dict(li, partite=mesc[i0:i0 + li["n"]]))
            i0 += li["n"]
        liste_m[a] = nuove
        for n in range(2, min(e["turni"], 6) + 1):
            y_c = any(r == "Creature" for _n, _i, r in e["magie"].get(n) or [])
            ap = e["aperte"].get(n) or 0
            y_s = bool([z for z in e["nel_tuo"].get(n) or [] if z[1]]) if ap >= 2 else None
            pesi, _r = pesi_partita(x, liste, fino_a=n)
            rt_l = ritratto(pesi, base=rt_arch)
            pesi_m, _r = pesi_partita(x, liste_m, fino_a=n)
            rt_m = ritratto(pesi_m, base=rt_arch)
            for nome_, rt in (("lista", rt_l), ("archetipo", rt_arch), ("tutti", rt_tutte), ("negativa", rt_m)):
                v = rt.get(n)
                if not v:
                    continue
                l_, b_ = lossb(v["p_crea"], y_c)
                ll[("crea", nome_)].update(n=1, l=l_, b=b_)
                per_arch[(a, nome_)].update(n=1, l=l_)
                if y_s is not None and v["p_spiegata"] is not None:
                    l_, b_ = lossb(v["p_spiegata"], y_s)
                    ll[("risposta", nome_)].update(n=1, l=l_, b=b_)
    log("Il confronto, partita per partita lasciata fuori, la lista riconosciuta dalle carte viste prima di quel turno (Constructed, suoi turni 2-6):")
    for cosa in ("crea", "risposta"):
        titolo = "lancia una creatura nel suo turno" if cosa == "crea" else "passa con 2+ aperte e poi risponde nel tuo turno"
        log(f"  {titolo}:")
        for nome_ in ("lista", "archetipo", "tutti", "negativa"):
            c = ll[(cosa, nome_)]
            if c["n"]:
                log(f"    {nome_:10} {int(c['n']):5} previsioni  log-loss {c['l'] / c['n']:.4f}  Brier {c['b'] / c['n']:.4f}")
    log("  per archetipo (log-loss di «lancia una creatura»: lista contro archetipo; sotto 20 previsioni un indizio):")
    archi = sorted({a for a, _n in per_arch}, key=lambda a: -per_arch[(a, "lista")]["n"])
    for a in archi[:12]:
        cl, ca = per_arch[(a, "lista")], per_arch[(a, "archetipo")]
        if cl["n"]:
            log(f"    {a[:26]:26} {int(cl['n']):4}  lista {cl['l'] / cl['n']:.3f}  archetipo {ca['l'] / ca['n']:.3f}")
    return ll


_CACHE = {}
INTERFERISCE = ("Removal", "Counterspell", "Combat trick", "Creature")      # le risposte che fermano una tua giocata (la pescata a fine turno no)
NOMI_RUOLO = {"Removal": "removal", "Combat trick": "a trick", "Creature": "a flash creature", "Counterspell": "a counterspell", "Card draw": "card draw",
              "Other spell": "another spell"}


def risposta(x, t, righe):
    """L'equity contro il range, per il tuo turno t (di Arena) della partita x (21 nov 2026, Autore: «posso stimare un range di carte e scoprire se in %
    quella tale giocata passa vs quel range quante volte»): se lui ha passato il suo turno prima con 2+ terre aperte, quanto spesso il suo mazzo (la lista
    riconosciuta dalle carte viste prima di questo turno, agganciata all'archetipo e a tutti i mazzi) in quel caso risponde nel tuo turno a velocita'
    istantanea, e con cosa. -> dict(aperte, p, cosa [(ruolo, quota)], lista, p_lista, archetipo, partite) o None (Limited, niente dati, lui tappato:
    allora dict(aperte, p=0))."""
    if x.get("tipo") != "Constructed":
        return None
    e = eventi(x)
    if not e or x.get("inizia") is None:
        return None
    n = (t - 1) // 2 if x.get("inizia") else t // 2       # il suo turno subito prima del tuo turno t
    ap = e["aperte"].get(n)
    if ap is None:
        return None
    if ap < 2:
        out = dict(aperte=ap, p=0.0, cosa=[], lista=None, p_lista=None, archetipo=x.get("suo"), partite=0, esatta=None)
        if ap == 1:         # una terra aperta paga le risposte da 1 mana: solo con la lista esatta (il ritratto e' misurato da 2 aperte)
            out["esatta"] = _esatta(x, t, n, ap)
        return out
    k = (len(righe), x.get("partita"))
    if k not in _CACHE:
        if len(_CACHE) > 40:
            _CACHE.clear()
        R = [y for y in righe if y.get("tipo") == "Constructed" and y.get("partita") != x.get("partita")]
        liste = costruisci(R)
        a = x.get("suo") or "?"
        arch_xs = [y for li in liste.get(a) or [] for y in li["partite"]]
        rt_t = ritratto([(R, 1.0)])
        rt_a = ritratto([(arch_xs, 1.0)], base=rt_t) if arch_xs else rt_t
        _CACHE[k] = (liste, rt_a, len(arch_xs))
    liste, rt_a, n_arch = _CACHE[k]
    pesi, ric = pesi_partita(x, liste, fino_a=n + 1)
    rt = ritratto(pesi, base=rt_a) if n_arch else rt_a
    v = rt.get(n)
    if not v or v.get("p_spiegata") is None:
        return None
    cosa = sorted((v.get("cosa") or {}).items(), key=lambda z: -z[1])
    li0, p0 = ric[0] if ric else (None, None)
    out = dict(aperte=ap, p=v["p_spiegata"], cosa=cosa, lista=li0["id"] if li0 else None, lista_n=li0["n"] if li0 else 0, p_lista=p0,
               archetipo=x.get("suo"), partite=n_arch, esatta=None)
    out["esatta"] = _esatta(x, t, n, ap)
    return out


def _esatta(x, t, n, ap):
    """La lista esatta del meta (21 nov 2026, misurata: log-loss 0,451 contro 0,530 del ritratto, sei divisioni su sei, negativa a zero): l'archetipo
    riconosciuto dalle carte viste fino alla fine del suo turno, le sue risposte pagabili con ap terre meno quelle usate, fra le carte che non vedi.
    -> dict o None (nessuna lista del meta, nessuna taratura)."""
    tar = taratura()
    try:
        a_t = archetipo_al_turno(x, t)
        lista = lista_meta(x, a_t) if a_t else None
        if not (lista and tar):
            return None
        import dati_analizzatore as DA
        import stato_avversario as SA
        t_suo = t - 1
        k_f = ("foto", x.get("partita"))
        if k_f not in _CACHE:
            fine = {}
            for p_ in DA.azioni_partita(x) or []:
                g_ = (p_[1] or {}).get("_grezza")
                if g_ is not None:
                    fine[p_[2]] = g_
            _CACHE[k_f] = fine
        th = tiene_risposta(x, n, ap, SA.al_turno(x, t_suo).get("usate"), _CACHE[k_f].get(t_suo), lista=lista)
        if not th:
            return None
        q = min(0.98, max(0.02, th[0]))
        p_l = 1 / (1 + math.exp(-(tar["a"] + tar["b"] * math.log(q / (1 - q))))) if th[1] else 0.0
        return dict(archetipo=a_t, tiene=th[0], lancia=p_l, A=th[1], N=th[2], H=th[3], nomi=th[4])
    except Exception:       # noqa: BLE001 - senza la lista esatta resta il ritratto
        return None


def inventario(xs):
    """Le risposte a velocita' istantanea che una lista ha mostrato: {nome: copie}, il massimo di copie lanciate in una partita sola (un minimo: le copie
    mai lanciate non si vedono)."""
    inv = collections.Counter()
    for x in xs:
        e = eventi(x)
        if not e:
            continue
        per = collections.Counter(n for vv in list(e["magie"].values()) + list(e["nel_tuo"].values()) for n, ist, r in vv if ist and r in INTERFERISCE)
        for n, q in per.items():
            inv[n] = max(inv[n], q)
    return dict(inv)


K_RESTO = 2.0       # copie finte che non si vedono mai (le risposte tenute e mai lanciate): la quota rimasta non scende mai a zero


def quota_rimasta(inv, usate):
    """La quota delle sue risposte ancora nel mazzo o in mano: (copie mostrate dalla lista meno quelle gia' usate + K_RESTO) / (copie mostrate + K_RESTO)."""
    tot = sum(inv.values())
    resto = sum(max(0, q - (usate or {}).get(n, 0)) for n, q in inv.items())
    return (resto + K_RESTO) / (tot + K_RESTO)


def testo_risposta(r):
    """La riga del replayer, in inglese."""
    if not r:
        return None
    if r["p"] == 0 and r["aperte"] < 2 and not r.get("esatta"):
        return f"VS HIS RANGE · he passed with {r['aperte']} untapped land{'s' * (r['aperte'] != 1)}: nothing at instant speed to fear"
    chi = r.get("archetipo") or "his deck"
    if r.get("lista") and (r.get("p_lista") or 0) >= 0.5 and r.get("lista_n", 0) >= 2:
        chi += f" (a list seen in {r['lista_n']} games, {100 * r['p_lista']:.0f}% sure)"
    cosa = ", ".join(f"{NOMI_RUOLO.get(r_, r_)} {100 * q:.0f}%" for r_, q in r["cosa"][:3] if q >= 0.01)
    es = r.get("esatta")
    if es:
        risp = ", ".join(f"{n} ×{q}" for n, q in es["nomi"][:3]) + (" …" if len(es["nomi"]) > 3 else "")
        return (f"VS HIS RANGE · {es['archetipo']} (meta list), {r['aperte']} open: {es['A']} answer{'s' * (es['A'] != 1)} he can pay for still in his "
                f"{es['N']} unseen cards" + (f" ({risp})" if risp else "") + f", he holds one {100 * es['tiene']:.0f}% of the time"
                f" · your plays go through {100 * (1 - es['lancia']):.0f}%")
    ferma = min(r["p"], sum(q for r_, q in r["cosa"] if r_ in INTERFERISCE))
    return (f"VS HIS RANGE · {chi}, {r['aperte']} open: it answers on your turn {100 * r['p']:.0f}% of the time"
            + (f" ({cosa})" if cosa else "") + f" · your plays go through {100 * (1 - ferma):.0f}%")


def misura_usate(righe, log=print, seme=5):
    """Togliere le risposte gia' usate migliora la previsione? Per ogni sua passata con 2+ aperte: y = nel tuo turno dopo lancia una risposta che ferma
    (INTERFERISCE); p = la quota del ritratto dell'archetipo (partita lasciata fuori); p' = p per la quota rimasta (inventario della lista riconosciuta, o
    dell'archetipo, meno le copie che ha gia' usato prima del tuo turno); negativa: le copie usate di un'altra passata a caso."""
    import stato_avversario as SA
    R = [x for x in righe if x.get("tipo") == "Constructed" and eventi(x)]
    rng = random.Random(seme)
    eventi_ = []
    for x in R:
        a = x.get("suo") or "?"
        if a in ("Unknown", "?"):
            continue
        e = eventi(x)
        for n in range(1, min(e["turni"], 12) + 1):
            if (e["aperte"].get(n) or 0) >= 2:
                t_tuo = 2 * n + 1 if x.get("inizia") else 2 * n      # il tuo turno dopo il suo turno n
                y = any(z[1] and z[2] in INTERFERISCE for z in e["nel_tuo"].get(n) or [])
                st = SA.al_turno(x, t_tuo - 1)      # a fine del suo turno
                eventi_.append((x, n, y, dict(st.get("usate") or {})))
    acc = collections.defaultdict(list)
    cache = {}
    for x, n, y, usate in eventi_:
        a = x.get("suo")
        k = x["partita"]
        if k not in cache:
            R_ = [z for z in R if z["partita"] != k]
            liste = costruisci(R_)
            arch_xs = [z for li in liste.get(a) or [] for z in li["partite"]]
            rt_t = ritratto([(R_, 1.0)])
            rt_a = ritratto([(arch_xs, 1.0)], base=rt_t) if arch_xs else rt_t
            cache = {k: (rt_a, inventario(arch_xs))}
        rt_a, inv = cache[k]
        v = rt_a.get(n)
        if not v or v.get("p_spiegata") is None:
            continue
        p0 = min(v["p_spiegata"], sum(q for r_, q in (v.get("cosa") or {}).items() if r_ in INTERFERISCE)) or 0.0
        altro = eventi_[rng.randrange(len(eventi_))][3]
        for nome, us in (("ritratto", None), ("meno le usate", usate), ("negativa", altro)):
            p = p0 if us is None else p0 * quota_rimasta(inv, us)
            p = min(0.98, max(0.02, p))
            acc[nome].append(-math.log(p if y else 1 - p))
    log(f"Togliere le risposte gia' usate (Constructed, {len(acc['ritratto'])} passate con 2+ aperte, y = una risposta che ferma nel tuo turno):")
    import statistics as ST
    for nome in ("ritratto", "meno le usate", "negativa"):
        log(f"  {nome:14} log-loss {ST.mean(acc[nome]):.4f}")
    for nome in ("meno le usate", "negativa"):
        d = [b_ - a_ for a_, b_ in zip(acc["ritratto"], acc[nome])]
        log(f"  {nome} meno ritratto: {ST.mean(d):+.4f} ±{ST.stdev(d) / math.sqrt(len(d)):.4f} (negativo = meglio)")
    return acc


_META = {}
F_TARATURA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lista_esatta.json")
_TAR = {}


def taratura():
    if "t" not in _TAR:
        try:
            with open(F_TARATURA, encoding="utf-8") as h:
                _TAR["t"] = json.load(h)
        except (OSError, ValueError):
            _TAR["t"] = None
    return _TAR["t"]


def lista_meta(x, archetipo=None):
    """La lista intera del suo archetipo (quello della partita, o quello dato), se e' uno del meta del formato: {nome: copie} (il mazzo), o None."""
    import matchup_log as MU
    fmt = x.get("formato")
    if fmt not in _META:
        _META[fmt] = {}
        try:
            import dati_meta
            with open(dati_meta.file_meta(MU.META_FMT[fmt]), encoding="utf-8") as f:
                for a_ in json.load(f) or []:
                    if a_.get("nome") and a_.get("lista"):
                        _META[fmt][a_["nome"]] = dict(a_["lista"])
        except Exception:       # noqa: BLE001 - un formato senza meta: nessuna lista
            pass
    return _META[fmt].get(archetipo or x.get("suo"))


def archetipo_al_turno(x, t):
    """L'archetipo riconosciuto dalle sole magie che ha mostrato prima del turno di Arena t (matchup_log.riconosci), mai dal resto della partita."""
    import matchup_log as MU
    e = eventi(x)
    nomi = [n for t_, n in (e or {}).get("ordine", []) if t_ < t]
    return MU.riconosci(nomi, x.get("formato"))[0] if nomi else None


def _comb(n, k):
    return math.comb(n, k) if 0 <= k <= n else 0


def p_tiene(N, A, H):
    """P(almeno una delle A carte fra le H in mano), con N carte che non vedi (ipergeometrica esatta)."""
    if A <= 0 or H <= 0 or N <= 0:
        return 0.0
    A, H = min(A, N), min(H, N)
    return 1 - _comb(N - A, H) / _comb(N, H)


def tiene_risposta(x, n, aperte, usate=None, foto=None, lista=None):
    """La lista esatta (21 nov 2026, Autore: «può avere al massimo 4 carte dello stesso tipo e dalle liste sappiamo la quantità di carte per tipo
    nella lista se la lista è conosciuta»): P che a fine del suo turno n tenga in mano almeno una risposta che ferma (INTERFERISCE, a velocita' istantanea)
    pagabile con le terre aperte, dalle copie della sua lista meno quelle gia' usate, fra le carte che non vedi. -> (p, A, N, H) o None senza lista."""
    import dati_analizzatore as DA
    import psicologia as PS
    lista = lista if lista is not None else lista_meta(x)
    if not lista or foto is None:
        return None
    lui = 3 - x["seat"]
    vis = 0
    for lato, chiave in ((lui - 1, "c"), (lui - 1, "g"), (lui - 1, "e")):
        z = (foto.get(chiave) or [[], []])[lato] or []
        vis += sum(1 for c_ in z if not (isinstance(c_, list) and len(c_) > 2 and c_[2]))     # le pedine no
    H = (foto.get("n") or [0, 0])[lui - 1] or 0
    N = max(H, 60 - vis)
    A = 0
    nomi_r = []
    for nome, q in lista.items():
        c = DA._carta(nome) or {}
        if (c.get("cmc") or 99) > aperte or DA.ruolo_magia(nome) not in INTERFERISCE:
            continue
        tipo, testo = (c.get("tipo") or "").split(" // ")[0], c.get("testo") or ""
        if not ("Instant" in tipo or testo.startswith("Flash")):
            continue
        resto = max(0, min(4, int(q)) - (usate or {}).get(nome, 0))
        A += resto
        if resto:
            nomi_r.append((nome, resto))
    return p_tiene(N, A, H), A, N, H, sorted(nomi_r, key=lambda z: -z[1])


def misura_lista_esatta(righe, log=print, seme=5):
    """La lista esatta contro il ritratto: per ogni sua passata con 2+ aperte contro un archetipo del meta, y = nel tuo turno dopo lancia una risposta che
    ferma. Predittori: il ritratto dell'archetipo (partita fuori), la probabilita' ipergeometrica che tenga una risposta pagabile (lista meno usate), e i
    due insieme; ognuno ricalibrato (logistica) su meta' partite e misurato sull'altra meta'. Negativa: la probabilita' di un'altra passata a caso."""
    import stato_avversario as SA
    import numpy as np
    R = [x for x in righe if x.get("tipo") == "Constructed" and eventi(x) and lista_meta(x)]
    rng = random.Random(seme)
    ev_ = []
    cache = {}
    for x in R:
        e = eventi(x)
        passi = None
        for n in range(1, min(e["turni"], 12) + 1):
            ap = e["aperte"].get(n) or 0
            if ap < 2:
                continue
            if passi is None:
                import dati_analizzatore as DA
                fine = {}
                for p_ in DA.azioni_partita(x) or []:
                    g_ = (p_[1] or {}).get("_grezza")
                    if g_ is not None:
                        fine[p_[2]] = g_
                passi = fine
            t_suo = 2 * n if x.get("inizia") else 2 * n - 1
            st = SA.al_turno(x, t_suo)
            a_t = archetipo_al_turno(x, t_suo + 1)          # dalle carte viste fino alla fine del suo turno, non dal resto della partita
            th = tiene_risposta(x, n, ap, st.get("usate"), passi.get(t_suo), lista=lista_meta(x, a_t) if a_t else None)
            if th is None:
                continue
            k = x["partita"]
            if k not in cache:
                R_ = [z for z in righe if z.get("tipo") == "Constructed" and z["partita"] != k and eventi(z)]
                liste = costruisci(R_)
                arch_xs = [z for li in liste.get(x.get("suo")) or [] for z in li["partite"]]
                rt_t = ritratto([(R_, 1.0)])
                cache = {k: ritratto([(arch_xs, 1.0)], base=rt_t) if arch_xs else rt_t}
            v = cache[k].get(n) or {}
            pr = min(v.get("p_spiegata") or 0.0, sum(q for r_, q in (v.get("cosa") or {}).items() if r_ in INTERFERISCE))
            y = any(z[1] and z[2] in INTERFERISCE for z in e["nel_tuo"].get(n) or [])
            ev_.append(dict(g=k, y=1.0 if y else 0.0, pr=pr, ph=th[0]))
    if len(ev_) < 30:
        log(f"troppo poche passate contro un archetipo del meta: {len(ev_)}")
        return None
    lg = lambda p: math.log(min(0.98, max(0.02, p)) / (1 - min(0.98, max(0.02, p))))
    altro = [ev_[rng.randrange(len(ev_))]["ph"] for _ in ev_]
    for i, z in enumerate(ev_):
        z["neg"] = altro[i]
    giochi = sorted({z["g"] for z in ev_})
    risultati = collections.defaultdict(list)
    for s_ in range(6):
        r_ = random.Random(s_)
        gg = giochi[:]
        r_.shuffle(gg)
        A_ = set(gg[: len(gg) // 2])
        for nome, cols in (("ritratto", ("pr",)), ("lista esatta", ("ph",)), ("tutti e due", ("pr", "ph")), ("ritratto + negativa", ("pr", "neg"))):
            Xa = np.array([[1.0] + [lg(z[c]) for c in cols] for z in ev_ if z["g"] in A_]); ya = np.array([z["y"] for z in ev_ if z["g"] in A_])
            Xb = np.array([[1.0] + [lg(z[c]) for c in cols] for z in ev_ if z["g"] not in A_]); yb = np.array([z["y"] for z in ev_ if z["g"] not in A_])
            w = np.zeros(Xa.shape[1])
            for _ in range(40):
                pp = 1 / (1 + np.exp(-(Xa @ w)))
                H_ = (Xa.T * (pp * (1 - pp))) @ Xa + 1e-3 * np.eye(len(w))
                w -= np.linalg.solve(H_, Xa.T @ (pp - ya) + 1e-3 * w)
            pb = np.clip(1 / (1 + np.exp(-(Xb @ w))), 1e-6, 1 - 1e-6)
            risultati[nome].append(float(np.mean(-(yb * np.log(pb) + (1 - yb) * np.log(1 - pb)))))
    # la taratura per il replayer: «tiene» -> «lancia nel tuo turno», su tutte le passate (si rifa' con --esatta)
    Xt = np.array([[1.0, lg(z["ph"])] for z in ev_]); yt = np.array([z["y"] for z in ev_])
    wt = np.zeros(2)
    for _ in range(40):
        pp = 1 / (1 + np.exp(-(Xt @ wt)))
        H_ = (Xt.T * (pp * (1 - pp))) @ Xt + 1e-3 * np.eye(2)
        wt -= np.linalg.solve(H_, Xt.T @ (pp - yt) + 1e-3 * wt)
    import datetime as _dt
    with open(F_TARATURA, "w", encoding="utf-8") as h:
        json.dump(dict(a=float(wt[0]), b=float(wt[1]), passate=len(ev_), partite=len(giochi), data=_dt.date.today().isoformat(),
                       nota="P(lancia una risposta che ferma nel tuo turno) = sigmoide(a + b logit(P tiene)), liste_avversarie.misura_lista_esatta"), h, indent=1)
    log(f"La lista esatta del meta contro il ritratto ({len(ev_)} passate con 2+ aperte contro un archetipo del meta, {len(giochi)} partite; "
        f"risponde nel {100 * sum(z['y'] for z in ev_) / len(ev_):.0f}%): log-loss sulla meta' non vista, media e spread su 6 divisioni")
    base = np.array(risultati["ritratto"])
    for nome in ("ritratto", "lista esatta", "tutti e due", "ritratto + negativa"):
        v = np.array(risultati[nome])
        log(f"  {nome:20} {v.mean():.4f}  (meno il ritratto {np.mean(v - base):+.4f}, da {np.min(v - base):+.4f} a {np.max(v - base):+.4f})")
    return risultati


def prova():
    import datetime as dt
    casi = []
    t0 = dt.datetime(2026, 11, 1)
    mk = lambda i, a, carte, giorni: dict(partita=f"p{i}", tipo="Constructed", suo=a, sue_viste=list(carte), quando=t0 + dt.timedelta(days=giorni))
    e_t = DA.e_terra
    DA.e_terra = lambda n: n.startswith("Land")
    try:
        R = [mk(1, "Rakdos", "ABCDEF", 0), mk(2, "Rakdos", "ABCDEG", 1), mk(3, "Rakdos", "ABCDXY", 2), mk(4, "Rakdos", "PQRSTU", 3),
             mk(5, "Rakdos", "PQRSTV", 4), mk(6, "Azorius", "MNOPQR", 5), mk(7, "Rakdos", "ABCDHI", 40)]
        L = costruisci(R)
        casi.append(("due liste di Rakdos, una di Azorius", len(L["Rakdos"]) == 2 and len(L["Azorius"]) == 1))
        casi.append(("le partite nella lista giusta", sorted(x["partita"] for x in L["Rakdos"][0]["partite"]) == ["p1", "p2", "p3", "p7"]))
        casi.append(("la versione nuova: due carte nuove insieme", L["Rakdos"][0]["versioni"] >= 2))
        casi.append(("la carta recente pesa di piu' della vecchia", L["Rakdos"][0]["carte"]["H"] > L["Rakdos"][0]["carte"]["E"]))
        r1 = riconosci({"A", "B"}, "Rakdos", L)
        casi.append(("le carte A e B: la prima lista", r1[0][0] is not None and r1[0][0]["id"] == L["Rakdos"][0]["id"] and r1[0][1] > 0.6))
        r2 = riconosci({"P", "Q", "R"}, "Rakdos", L)
        casi.append(("le carte P Q R: la seconda lista", r2[0][0] is not None and r2[0][0]["id"] == L["Rakdos"][1]["id"]))
        r0 = riconosci(set(), "Rakdos", L)
        casi.append(("negativa: senza carte nessuna lista e' sicura", r0[0][1] < 0.6))
        r3 = riconosci({"Z1", "Z2", "Z3"}, "Rakdos", L)
        casi.append(("negativa: carte mai viste, vince la lista sconosciuta", r3[0][0] is None))
        casi.append(("negativa: un archetipo senza liste e' la sconosciuta", riconosci({"A"}, "Gruul", L) == [(None, 1.0)]))
        # la lista esatta (21 nov 2026): l'ipergeometrica
        casi.append(("p_tiene: 4 risposte in 40 carte, 7 in mano = 1 - C(36,7)/C(40,7)", abs(p_tiene(40, 4, 7) - (1 - math.comb(36, 7) / math.comb(40, 7))) < 1e-12))
        casi.append(("negativa: nessuna risposta rimasta, nessuna mano", p_tiene(40, 0, 7) == 0.0 and p_tiene(40, 4, 0) == 0.0))
        casi.append(("tutte le carte che non vedi sono risposte: le tiene per forza", p_tiene(5, 5, 2) == 1.0))
    finally:
        DA.e_terra = e_t
    for n, ok in casi:
        print(("ok    " if ok else "ROSSO ") + n)
    print(f"{sum(1 for _n, ok in casi if ok)}/{len(casi)}")
    return all(ok for _n, ok in casi)


if __name__ == "__main__":
    if "--prova" in sys.argv:
        sys.exit(0 if prova() else 1)
    if "--m" in sys.argv:
        M = float(sys.argv[sys.argv.index("--m") + 1])
    if "--esatta" in sys.argv:
        misura_lista_esatta(DA.righe())
        sys.exit(0)
    if "--usate" in sys.argv:
        misura_usate(DA.righe())
        sys.exit(0)
    R = DA.righe()
    L = costruisci(R)
    for a, ls in sorted(L.items(), key=lambda kv: -sum(li["n"] for li in kv[1]))[:10]:
        print(a, [(li["n"], li["versioni"]) for li in ls if li["n"] >= 2])
    confronto(R)
